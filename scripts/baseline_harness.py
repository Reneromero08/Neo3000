#!/usr/bin/env python3
"""Verify and smoke-benchmark a running Neo3000 OpenAI-compatible server.

This script has no third-party Python dependencies. It validates the runtime
surface Pi depends on, measures streaming latency, and writes a compact local
JSON result. It does not benchmark model quality or authorize Checkpoint 0.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "lab" / "results.local.json"
DEFAULT_PROMPT = "Reply with exactly: NEO3000 ONLINE"
TOOL_NAME = "neo3000_probe"


class HarnessError(RuntimeError):
    pass


@dataclass
class StreamMeasurement:
    repeat: int
    http_status: int
    time_to_first_event_s: float | None
    time_to_first_token_s: float | None
    time_to_first_content_s: float | None
    total_time_s: float
    event_count: int
    content: str
    reasoning_content: str
    tool_calls: list[dict[str, Any]]
    completion_tokens: int | None
    prompt_tokens: int | None
    cached_prompt_tokens: int | None
    reported_tokens_per_second: float | None
    timings: dict[str, Any]
    finish_reason: str | None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_head() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> tuple[int, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HarnessError(f"{method} {url} returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise HarnessError(f"cannot reach {url}: {exc.reason}") from exc


def normalize_base_url(value: str) -> str:
    value = value.rstrip("/")
    if value.endswith("/v1"):
        return value[:-3]
    return value


def extract_model_ids(models_payload: Any) -> list[str]:
    if not isinstance(models_payload, dict):
        return []
    data = models_payload.get("data")
    if not isinstance(data, list):
        return []
    return [str(item["id"]) for item in data if isinstance(item, dict) and "id" in item]


def merge_tool_call(accumulator: dict[int, dict[str, Any]], fragment: dict[str, Any]) -> None:
    index = int(fragment.get("index", 0))
    current = accumulator.setdefault(
        index,
        {"index": index, "id": None, "type": None, "function": {"name": "", "arguments": ""}},
    )
    if fragment.get("id"):
        current["id"] = fragment["id"]
    if fragment.get("type"):
        current["type"] = fragment["type"]
    function = fragment.get("function")
    if isinstance(function, dict):
        if function.get("name"):
            current["function"]["name"] += str(function["name"])
        if function.get("arguments"):
            current["function"]["arguments"] += str(function["arguments"])


def iter_sse(response: Any) -> Iterable[dict[str, Any]]:
    for raw_line in response:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line or line.startswith(":") or not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            return
        try:
            event = json.loads(data)
        except json.JSONDecodeError as exc:
            raise HarnessError(f"invalid SSE JSON: {data[:300]}") from exc
        if isinstance(event, dict):
            yield event


def stream_completion(
    endpoint: str,
    payload: dict[str, Any],
    repeat: int,
    timeout: float,
) -> StreamMeasurement:
    encoded = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=encoded,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )

    start = time.perf_counter()
    first_event: float | None = None
    first_token: float | None = None
    first_content: float | None = None
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_fragments: dict[int, dict[str, Any]] = {}
    usage: dict[str, Any] = {}
    timings: dict[str, Any] = {}
    finish_reason: str | None = None
    event_count = 0

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
            for event in iter_sse(response):
                now = time.perf_counter()
                event_count += 1
                if first_event is None:
                    first_event = now - start

                if isinstance(event.get("usage"), dict):
                    usage.update(event["usage"])
                if isinstance(event.get("timings"), dict):
                    timings.update(event["timings"])

                choices = event.get("choices")
                if not isinstance(choices, list) or not choices:
                    continue
                choice = choices[0] if isinstance(choices[0], dict) else {}
                if choice.get("finish_reason") is not None:
                    finish_reason = str(choice["finish_reason"])
                delta = choice.get("delta")
                if not isinstance(delta, dict):
                    continue

                text = delta.get("content")
                if isinstance(text, str) and text:
                    if first_token is None:
                        first_token = now - start
                    if first_content is None:
                        first_content = now - start
                    content_parts.append(text)

                reasoning = delta.get("reasoning_content")
                if isinstance(reasoning, str) and reasoning:
                    if first_token is None:
                        first_token = now - start
                    reasoning_parts.append(reasoning)

                fragments = delta.get("tool_calls")
                if isinstance(fragments, list) and fragments:
                    if first_token is None:
                        first_token = now - start
                    for fragment in fragments:
                        if isinstance(fragment, dict):
                            merge_tool_call(tool_fragments, fragment)

            elapsed = time.perf_counter() - start
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HarnessError(f"stream request returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise HarnessError(f"stream request failed: {exc.reason}") from exc

    completion_tokens = usage.get("completion_tokens")
    prompt_tokens = usage.get("prompt_tokens")
    prompt_details = usage.get("prompt_tokens_details")
    cached_prompt_tokens = prompt_details.get("cached_tokens") if isinstance(prompt_details, dict) else None

    if not isinstance(completion_tokens, int):
        completion_tokens = None
    if not isinstance(prompt_tokens, int):
        prompt_tokens = None
    if not isinstance(cached_prompt_tokens, int):
        cached_prompt_tokens = None

    server_tps = timings.get("predicted_per_second")
    if isinstance(server_tps, (int, float)):
        tps = float(server_tps)
    elif completion_tokens and first_token is not None and elapsed > first_token:
        tps = completion_tokens / (elapsed - first_token)
    else:
        tps = None

    return StreamMeasurement(
        repeat=repeat,
        http_status=status,
        time_to_first_event_s=first_event,
        time_to_first_token_s=first_token,
        time_to_first_content_s=first_content,
        total_time_s=elapsed,
        event_count=event_count,
        content="".join(content_parts),
        reasoning_content="".join(reasoning_parts),
        tool_calls=[tool_fragments[key] for key in sorted(tool_fragments)],
        completion_tokens=completion_tokens,
        prompt_tokens=prompt_tokens,
        cached_prompt_tokens=cached_prompt_tokens,
        reported_tokens_per_second=tps,
        timings=timings,
        finish_reason=finish_reason,
    )


def summarize(measurements: list[StreamMeasurement]) -> dict[str, Any]:
    def median(values: list[float | None]) -> float | None:
        present = [value for value in values if value is not None]
        return statistics.median(present) if present else None

    return {
        "repeat_count": len(measurements),
        "median_time_to_first_event_s": median([item.time_to_first_event_s for item in measurements]),
        "median_time_to_first_token_s": median([item.time_to_first_token_s for item in measurements]),
        "median_time_to_first_content_s": median([item.time_to_first_content_s for item in measurements]),
        "median_total_time_s": median([item.total_time_s for item in measurements]),
        "median_reported_tokens_per_second": median(
            [item.reported_tokens_per_second for item in measurements]
        ),
        "median_cached_prompt_tokens": median([
            float(item.cached_prompt_tokens) if item.cached_prompt_tokens is not None else None
            for item in measurements
        ]),
        "all_http_200": all(item.http_status == 200 for item in measurements),
        "all_streamed_multiple_events": all(item.event_count > 1 for item in measurements),
    }


def validate_tool_call(measurement: StreamMeasurement) -> dict[str, Any]:
    matching = [
        call for call in measurement.tool_calls
        if call.get("function", {}).get("name") == TOOL_NAME
    ]
    if not matching:
        return {"passed": False, "reason": f"no {TOOL_NAME} tool call found"}
    arguments = matching[0].get("function", {}).get("arguments", "")
    try:
        decoded = json.loads(arguments)
    except json.JSONDecodeError:
        return {"passed": False, "reason": "tool arguments were not valid JSON", "arguments": arguments}
    passed = decoded == {"status": "ok"}
    return {"passed": passed, "arguments": decoded}


def write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def build_request_payload(
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    cache_prompt: bool,
    tool_test: bool,
    disable_thinking: bool,
) -> dict[str, Any]:
    """Build the narrow locked request surface used by every harness probe."""
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
        "cache_prompt": cache_prompt,
    }
    if disable_thinking:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    if tool_test:
        payload["messages"] = [{
            "role": "user",
            "content": (
                f"Call the {TOOL_NAME} tool exactly once with status set to ok. "
                "Do not answer in plain text."
            ),
        }]
        payload["tools"] = [{
            "type": "function",
            "function": {
                "name": TOOL_NAME,
                "description": "Harmless Neo3000 tool-call compatibility probe.",
                "parameters": {
                    "type": "object",
                    "properties": {"status": {"type": "string", "enum": ["ok"]}},
                    "required": ["status"],
                    "additionalProperties": False,
                },
            },
        }]
        payload["tool_choice"] = "required"
    return payload


def thinking_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    kwargs = payload.get("chat_template_kwargs")
    return {
        "thinking_mode": "disabled" if kwargs == {"enable_thinking": False} else "auto",
        "chat_template_kwargs": kwargs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:9292/v1")
    parser.add_argument("--model", default="agents-a1")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--expect-content", help="required substring in each streamed final-content response")
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--cache-prompt", action="store_true")
    parser.add_argument("--tool-test", action="store_true")
    parser.add_argument(
        "--disable-thinking",
        action="store_true",
        help="send only chat_template_kwargs.enable_thinking=false for final-content transport probes",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if args.repeat < 1:
        raise HarnessError("--repeat must be at least 1")
    if args.max_tokens < 1:
        raise HarnessError("--max-tokens must be at least 1")

    root_url = normalize_base_url(args.base_url)
    api_url = root_url + "/v1"
    prompt = args.prompt_file.read_text(encoding="utf-8") if args.prompt_file else args.prompt

    health_status, health = request_json("GET", root_url + "/health", timeout=30.0)
    models_status, models = request_json("GET", api_url + "/models", timeout=30.0)
    model_ids = extract_model_ids(models)
    if args.model not in model_ids:
        raise HarnessError(f"model {args.model!r} not found; server reported {model_ids}")

    payload = build_request_payload(
        args.model,
        prompt,
        args.temperature,
        args.max_tokens,
        args.cache_prompt,
        args.tool_test,
        args.disable_thinking,
    )

    measurements: list[StreamMeasurement] = []
    for repeat in range(1, args.repeat + 1):
        print(f"stream run {repeat}/{args.repeat} ...", flush=True)
        measurement = stream_completion(
            api_url + "/chat/completions",
            payload,
            repeat=repeat,
            timeout=args.timeout,
        )
        measurements.append(measurement)
        print(
            f"  events={measurement.event_count} "
            f"ttft={measurement.time_to_first_token_s!r} "
            f"ttfc={measurement.time_to_first_content_s!r} "
            f"prompt_tps={measurement.timings.get('prompt_per_second')!r} "
            f"decode_tps={measurement.reported_tokens_per_second!r} "
            f"cached={measurement.cached_prompt_tokens!r}"
        )

    result: dict[str, Any] = {
        "schema_version": 3,
        "captured_at": utc_now(),
        "neo3000_commit": git_head(),
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "processor": platform.processor(),
        },
        "server": {
            "base_url": api_url,
            "model": args.model,
            "health_http_status": health_status,
            "health": health,
            "models_http_status": models_status,
            "model_ids": model_ids,
        },
        "request": {
            "prompt_source": str(args.prompt_file) if args.prompt_file else "inline",
            "prompt": payload["messages"][0]["content"],
            "prompt_characters": len(prompt),
            "max_tokens": args.max_tokens,
            "temperature": args.temperature,
            "cache_prompt": args.cache_prompt,
            "tool_test": args.tool_test,
            **thinking_metadata(payload),
        },
        "measurements": [asdict(item) for item in measurements],
        "summary": summarize(measurements),
    }

    if args.tool_test:
        result["tool_call_validation"] = [validate_tool_call(item) for item in measurements]
        result["tool_call_passed"] = all(
            item["passed"] for item in result["tool_call_validation"]
        )
    else:
        expected = args.expect_content or (DEFAULT_PROMPT.split(":", 1)[-1].strip() if prompt == DEFAULT_PROMPT else None)
        result["expected_content"] = expected
        result["request"]["expected_content"] = expected
        result["exact_response_passed"] = all(
            expected in item.content for item in measurements
        ) if expected else None

    write_result(args.output, result)
    print(f"wrote {args.output}")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))

    if not result["summary"]["all_http_200"]:
        return 2
    if not result["summary"]["all_streamed_multiple_events"]:
        return 3
    if args.tool_test and not result["tool_call_passed"]:
        return 4
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HarnessError, OSError, json.JSONDecodeError) as exc:
        print(f"baseline_harness: {exc}", file=sys.stderr)
        raise SystemExit(1)
