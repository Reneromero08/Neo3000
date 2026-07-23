#!/usr/bin/env python3
"""Checkpoint-free N=1 catalytic latency discriminator on the qualified water root.

The scientific intervention is only exact prompt-root reuse versus identical
cache-disabled prefill.  One matched warmup pair is reported but excluded from
the decision gate.  Four counted pairs use ABBA route order; RAM-root restore
time is charged to every catalytic request.  This controller adds no runtime
mechanism and makes no fanout claim.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import catalytic_frontier_fanout as shared_tasks
import catalytic_frontier_harness as harness
import catalytic_frontier_water_panel_qualifier as water


ROOT_ID = water.ROOT_ID
BRANCH_NUMBER = 7
PAIR_ROUTE_ORDERS = (
    ("catalytic", "direct"),
    ("direct", "catalytic"),
    ("direct", "catalytic"),
    ("catalytic", "direct"),
)
COUNTED_PAIRS = len(PAIR_ROUTE_ORDERS)
WARMUP_ROUTE_ORDER = ("catalytic", "direct")
PANEL_SHA256 = "47DD356BA39422EF58019CE60B84A69FCAEC455FE11B758103935CE65DE33841"
EXPECTED_ANSWER = "C"
EXPECTED_PROMPT_ROOT_TOKENS = 543
EXPECTED_RETAINED_ROOT_TOKENS = 612
EXPECTED_BRANCH_PROMPT_TOKENS = 690
MIN_PAIRED_WINS = 3
MIN_MEDIAN_SPEEDUP = 1.25
MAX_DIRECT_CONTROL_DRIFT_FRACTION = 0.10
SPECULATIVE_MODES = ("none", "ngram-cache")
ROOT_STORAGE_MODES = ("host", "device")
RUNTIME_IDENTITY_MODES = ("canonical", "cuda-bundle")
STRICT_PREFIX_NO_SPEC_MEDIANS = {
    "predicted_ms": 225.1865,
    "effective_wall_seconds_including_restore": 0.46100000001024455,
}
STRICT_PREFIX_NO_SPEC_DIRECT_MEDIANS = {
    "prompt_ms": 10414.7795,
    "ttft_seconds": 10.4845000000059,
    "effective_wall_seconds": 10.7734999999957,
}
STRICT_PREFIX_NGRAM_MIN_SPEEDUP = 1.25
MAX_NGRAM_PRIVATE_GROWTH_BYTES = 128 * 1024 * 1024
STRICT_PREFIX_NO_SPEC_AFTER_ERASE_PRIVATE_GROWTH_BYTES = 109_101_056
STRICT_PREFIX_NO_SPEC_DIRECT_LIFECYCLE_WALL_SECONDS = 58.123999999981606
STRICT_PREFIX_NO_SPEC_DIRECT_LIFECYCLE_FRESH_TOKENS = 3397
STRICT_PREFIX_HOST_ROOT_RESTORE_SERVER_MEDIAN_MS = 13.9525
CUDA_ROOT_MIN_RESTORE_SPEEDUP = 2.0
CUDA_ROOT_MIN_EFFECTIVE_WALL_SPEEDUP = 1.02
STRICT_PREFIX_LOGICAL_ROOT_BYTES = 79_991_940
CUDA_ROOT_RUNTIME_SHA256 = {
    "ggml-base.dll": "F648098AB0FCECA45A1EEC2AE147022383DCC6CD31392199F5CD6E5A5277AF3F",
    "ggml-cpu.dll": "64B9D97113CC0AB57C8DA0E3237B4EFC0271B4E0AA377080295D138BCABC92A1",
    "ggml-cuda.dll": "C4BCC1C7AF82475E1C1CD3A56C3AF9CDA3EE50AE8C7819D9A314C6B6F62DC787",
    "ggml.dll": "6E6A8BE1DAFA42356C15DDA9C0A39CC7BA34E4ABA8D402693F0EFCB57CD9E2D1",
    "llama-common.dll": "EBB25179767CAFB6EBDEEA0A1E7A16490CD66C7D6645083F853DE63D371FC6AE",
    "llama-server-impl.dll": "0D5C4FDBDBB894F25075D347C74798C8A9648F58C34A96560670A9179672E27D",
    "llama-server.exe": "98F9795C04A50305D09042230950F0F657EA7140EAF945CDD36C58291E965346",
    "llama.dll": "2D92EC62987EA9BA4EA82FD68C0631A0A95E62BCB3058E715100FF5AA19BAA14",
    "mtmd.dll": "712AF620E960154C6F9CA72FA29670B155763E67C0837ED18B1FDFF97DF9C62B",
}
CUDA_ROOT_BINARY_SHA256 = CUDA_ROOT_RUNTIME_SHA256["llama-server.exe"]
DEFAULT_BINARY = Path("build/candidate/bin/Release/llama-server.exe")
ROOT_BOUNDARIES: dict[str, dict[str, Any]] = {
    "task-a": {
        "expected_root_tokens": EXPECTED_PROMPT_ROOT_TOKENS,
        "expected_cached_prompt_tokens": EXPECTED_PROMPT_ROOT_TOKENS,
        "expected_fresh_prompt_tokens": EXPECTED_BRANCH_PROMPT_TOKENS - EXPECTED_PROMPT_ROOT_TOKENS,
        "predecessor_medians": None,
        "predecessor_direct_medians": None,
    },
    "full-prompt": {
        "expected_root_tokens": EXPECTED_BRANCH_PROMPT_TOKENS,
        # server-context.cpp TAG_PROMPT_LOGITS deliberately re-evaluates one token
        # when an active slot exactly matches the submitted prompt.
        "expected_cached_prompt_tokens": EXPECTED_BRANCH_PROMPT_TOKENS - 1,
        "expected_fresh_prompt_tokens": 1,
        "predecessor_medians": {
            "prompt_ms": 2498.008,
            "ttft_seconds_including_restore": 2.6165000000037253,
            "effective_wall_seconds_including_restore": 2.9130000000077416,
        },
        "predecessor_direct_medians": {
            "prompt_ms": 10185.8015,
            "ttft_seconds": 10.25800000000163,
            "effective_wall_seconds": 10.57050000000163,
        },
    },
    "strict-prefix": {
        "expected_root_tokens": EXPECTED_BRANCH_PROMPT_TOKENS - 1,
        "expected_cached_prompt_tokens": EXPECTED_BRANCH_PROMPT_TOKENS - 1,
        "expected_fresh_prompt_tokens": 1,
        "predecessor_medians": {
            "prompt_ms": 2498.008,
            "ttft_seconds_including_restore": 2.6165000000037253,
            "effective_wall_seconds_including_restore": 2.9130000000077416,
        },
        "predecessor_direct_medians": {
            "prompt_ms": 10185.8015,
            "ttft_seconds": 10.25800000000163,
            "effective_wall_seconds": 10.57050000000163,
        },
    },
}


def select_root_boundary(name: str, *, prompt_tokens: Sequence[int], branch_tokens: Sequence[int]) -> dict[str, Any]:
    harness.require(name in ROOT_BOUNDARIES, f"unsupported latency root boundary: {name}")
    selected = dict(ROOT_BOUNDARIES[name])
    selected["name"] = name
    if name == "full-prompt":
        selected["tokens"] = list(branch_tokens)
    elif name == "strict-prefix":
        selected["tokens"] = list(branch_tokens[:-1])
    else:
        selected["tokens"] = list(prompt_tokens)
    harness.require(len(selected["tokens"]) == selected["expected_root_tokens"], "latency root-boundary token count changed")
    return selected


class TimingRecorder:
    """Capture client-observed SSE milestones and terminal server timings."""

    def __init__(self, *, origin: float | None = None) -> None:
        self.origin = time.monotonic() if origin is None else float(origin)
        self.first_event_seconds: float | None = None
        self.first_generated_seconds: float | None = None
        self.terminal_event_seconds: float | None = None
        self.server_timings: dict[str, float] = {}
        self.event_count = 0

    def __call__(self, line: bytes) -> None:
        stripped = line.decode("utf-8", errors="replace").strip()
        if not stripped.startswith("data:"):
            return
        data = stripped[5:].strip()
        if not data or data == "[DONE]":
            return
        event = json.loads(data)
        now = time.monotonic() - self.origin
        self.event_count += 1
        if self.first_event_seconds is None:
            self.first_event_seconds = now
        tokens = event.get("tokens")
        generated = (
            "prompt_progress" not in event
            and (
                (isinstance(tokens, list) and bool(tokens))
                or (isinstance(event.get("content"), str) and bool(event["content"]))
            )
        )
        if generated and self.first_generated_seconds is None:
            self.first_generated_seconds = now
        if event.get("stop") is True:
            self.terminal_event_seconds = now
            timings = event.get("timings")
            if isinstance(timings, Mapping):
                self.server_timings = {
                    str(key): float(value)
                    for key, value in timings.items()
                    if isinstance(value, (int, float)) and not isinstance(value, bool)
                }

    def summary(self, *, request_wall_seconds: float) -> dict[str, Any]:
        harness.require(self.event_count > 0, "timed completion emitted no SSE events")
        harness.require(self.first_event_seconds is not None, "first SSE event timing is missing")
        harness.require(self.first_generated_seconds is not None, "first generated token timing is missing")
        harness.require(self.terminal_event_seconds is not None, "terminal SSE timing is missing")
        prompt_ms = self.server_timings.get("prompt_ms")
        harness.require(prompt_ms is not None and prompt_ms > 0, "terminal prompt_ms is missing")
        harness.require(
            self.first_generated_seconds <= request_wall_seconds + 0.25,
            "first generated event occurs after measured request wall",
        )
        return {
            "event_count": self.event_count,
            "first_event_seconds": self.first_event_seconds,
            "ttft_seconds": self.first_generated_seconds,
            "terminal_event_seconds": self.terminal_event_seconds,
            "prompt_ms": prompt_ms,
            "prompt_per_second": self.server_timings.get("prompt_per_second"),
            "predicted_ms": self.server_timings.get("predicted_ms"),
            "predicted_per_second": self.server_timings.get("predicted_per_second"),
            "server_prompt_n": self.server_timings.get("prompt_n"),
            "server_predicted_n": self.server_timings.get("predicted_n"),
            "draft_n": self.server_timings.get("draft_n"),
            "draft_n_accepted": self.server_timings.get("draft_n_accepted"),
        }


def verify_cuda_root_runtime(binary: Path) -> dict[str, str]:
    harness.require(binary.name == "llama-server.exe", "CUDA-root runtime entrypoint changed")
    observed: dict[str, str] = {}
    for name, expected_sha256 in CUDA_ROOT_RUNTIME_SHA256.items():
        runtime_file = (binary.parent / name).resolve(strict=True)
        harness.require(runtime_file.parent == binary.parent, f"CUDA-root runtime path escaped for {name}")
        observed_sha256 = harness.live_runtime.sha256_file(runtime_file)
        harness.require(
            observed_sha256 == expected_sha256,
            f"CUDA-root runtime identity drifted for {name}: {observed_sha256}",
        )
        observed[name] = observed_sha256
    return observed


def validate_root_response(
    response: Mapping[str, Any],
    *,
    action: str,
    expected: Mapping[str, Any] | None = None,
    root_storage: str = "host",
) -> dict[str, Any]:
    harness.require(root_storage in ROOT_STORAGE_MODES, "unsupported RAM-root storage mode")
    harness.require(response.get("action") == action, f"RAM-root action mismatch for {action}")
    harness.require(response.get("root_id") == ROOT_ID, f"RAM-root identity mismatch for {action}")
    harness.require(type(response.get("id_slot")) is int, f"RAM-root slot missing for {action}")
    for key in ("n_tokens", "n_bytes", "n_checkpoints"):
        harness.require(type(response.get(key)) is int, f"RAM-root {key} missing for {action}")
        harness.require(int(response[key]) >= 0, f"RAM-root {key} is negative for {action}")
    harness.require(int(response["n_tokens"]) > 0, f"RAM-root is empty for {action}")
    harness.require(int(response["n_bytes"]) > 0, f"RAM-root has no state bytes for {action}")
    harness.require(int(response["n_checkpoints"]) == 0, f"RAM-root checkpoint count changed for {action}")
    if root_storage == "device":
        for key in ("n_host_bytes", "n_device_bytes", "n_device_bytes_after", "n_gpu_bytes", "n_gpu_bytes_after"):
            harness.require(type(response.get(key)) is int, f"RAM-root {key} missing for {action}")
            harness.require(int(response[key]) >= 0, f"RAM-root {key} is negative for {action}")
        harness.require(
            int(response["n_bytes"]) == int(response["n_host_bytes"]) + int(response["n_device_bytes"]),
            f"RAM-root logical byte accounting changed for {action}",
        )
        harness.require(int(response["n_device_bytes"]) > 0, f"RAM-root has no device tensor bytes for {action}")
        harness.require(int(response["n_gpu_bytes"]) > 0, f"RAM-root has no GPU-backed tensor bytes for {action}")
        harness.require(
            int(response["n_gpu_bytes"]) <= int(response["n_device_bytes"]),
            f"RAM-root GPU byte accounting exceeds device state for {action}",
        )
        expected_after = 0 if action == "root-erase" else int(response["n_device_bytes"])
        harness.require(
            int(response["n_device_bytes_after"]) == expected_after,
            f"RAM-root device-state closure changed for {action}",
        )
        expected_gpu_after = 0 if action == "root-erase" else int(response["n_gpu_bytes"])
        harness.require(
            int(response["n_gpu_bytes_after"]) == expected_gpu_after,
            f"RAM-root GPU-state closure changed for {action}",
        )
    if expected is not None:
        for key in ("root_id", "n_tokens", "n_bytes", "n_checkpoints"):
            harness.require(response.get(key) == expected.get(key), f"RAM-root {key} changed at {action}")
        if root_storage == "device":
            for key in ("n_host_bytes", "n_device_bytes", "n_gpu_bytes"):
                harness.require(response.get(key) == expected.get(key), f"RAM-root {key} changed at {action}")
    timings = response.get("timings")
    harness.require(
        isinstance(timings, Mapping) and isinstance(timings.get("root_ms"), (int, float)),
        f"RAM-root timing missing for {action}",
    )
    return {
        "action": action,
        "root_id": response["root_id"],
        "id_slot": response["id_slot"],
        "n_tokens": response["n_tokens"],
        "n_bytes": response["n_bytes"],
        "n_host_bytes": response.get("n_host_bytes"),
        "n_device_bytes": response.get("n_device_bytes"),
        "n_device_bytes_after": response.get("n_device_bytes_after"),
        "n_gpu_bytes": response.get("n_gpu_bytes"),
        "n_gpu_bytes_after": response.get("n_gpu_bytes_after"),
        "n_checkpoints": response["n_checkpoints"],
        "server_root_ms": float(timings["root_ms"]),
    }


def percentile(values: Sequence[float], quantile: float) -> float:
    harness.require(bool(values), "percentile input is empty")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def distribution(values: Sequence[float]) -> dict[str, float]:
    harness.require(bool(values), "latency distribution is empty")
    return {
        "minimum": min(values),
        "median": statistics.median(values),
        "p95": percentile(values, 0.95),
        "maximum": max(values),
    }


def draft_acceptance_metrics(
    catalytic: Sequence[Mapping[str, Any]],
    control: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    def totals(records: Sequence[Mapping[str, Any]]) -> tuple[int, int]:
        drafted = sum(int(record["timing"].get("draft_n") or 0) for record in records)
        accepted = sum(int(record["timing"].get("draft_n_accepted") or 0) for record in records)
        return drafted, accepted

    catalytic_drafted, catalytic_accepted = totals(catalytic)
    control_drafted, control_accepted = totals(control)
    every_catalytic_request_accepted = bool(catalytic) and all(
        int(record["timing"].get("draft_n_accepted") or 0) > 0
        for record in catalytic
    )
    return {
        "catalytic_draft_tokens": catalytic_drafted,
        "catalytic_accepted_draft_tokens": catalytic_accepted,
        "catalytic_accepted_fraction": catalytic_accepted / catalytic_drafted if catalytic_drafted else None,
        "control_draft_tokens": control_drafted,
        "control_accepted_draft_tokens": control_accepted,
        "every_catalytic_request_accepted_a_draft": every_catalytic_request_accepted,
        "gate": catalytic_drafted > 0
        and catalytic_accepted > 0
        and catalytic_accepted <= catalytic_drafted
        and every_catalytic_request_accepted,
    }


def generated_token_hash(record: Mapping[str, Any]) -> str:
    generated = record["execution"].get("generated_token_ids")
    harness.require(
        isinstance(generated, list) and generated and all(type(item) is int for item in generated),
        "generated-token evidence is unavailable",
    )
    return harness.sha256_bytes(harness.carrier.canonical_json_bytes(generated))


def branch_request(codec: Any, retained: Mapping[str, Any], spec: Mapping[str, Any], *, cache_prompt: bool) -> tuple[list[int], dict[str, Any]]:
    suffix = harness.carrier.derive_continuation_suffix(
        codec,
        terminal_eog_id=int(retained["terminal_stop_identity"]["token_id"]),
        user_content=shared_tasks.branch_user_content(spec),
    )
    tokens = [*retained["retained_root_tokens"], *suffix["suffix_tokens"]]
    payload = harness.carrier._branch_payload(
        tokens,
        seed=shared_tasks.derive_seed(ROOT_ID, f"branch-{BRANCH_NUMBER}"),
        cache_prompt=cache_prompt,
    )
    return tokens, payload


def run_timed_branch(
    *,
    sidecar: Any,
    codec: Any,
    retained: Mapping[str, Any],
    spec: Mapping[str, Any],
    route: str,
    label: str,
) -> dict[str, Any]:
    harness.require(route in {"catalytic", "direct"}, "unsupported latency route")
    tokens, payload = branch_request(codec, retained, spec, cache_prompt=route == "catalytic")
    recorder = TimingRecorder()
    record = harness.run_completion(sidecar, label, payload, recorder=recorder)
    timing = recorder.summary(request_wall_seconds=float(record["wall_seconds"]))
    harness.require(record["prompt_tokens"] == len(tokens), "timed route prompt token count changed")
    harness.require(
        timing["server_prompt_n"] == record["fresh_prompt_tokens"],
        "server prompt timing identity differs from fresh prompt tokens",
    )
    harness.require(
        timing["server_predicted_n"] == record["completion_tokens"],
        "server predicted timing identity differs from completion tokens",
    )
    answer = harness.carrier.parse_branch_output(record["content"])
    record.update(
        route=route,
        answer=answer,
        expected=str(spec["answer"]),
        correct=answer == spec["answer"],
        input_token_sha256=harness.sha256_bytes(harness.carrier.canonical_json_bytes(tokens)),
        generated_token_sha256=generated_token_hash(record),
        timing=timing,
    )
    return record


def classify_result(
    *,
    utility_exact: bool,
    paired_wins: int,
    prompt_speedup: float,
    ttft_speedup: float,
    effective_wall_speedup: float,
    full_lifecycle_wall_advantage: bool,
    full_lifecycle_fresh_advantage: bool,
    predecessor_improvement_gate: bool = True,
    direct_control_drift_gate: bool = True,
) -> str:
    if not utility_exact:
        return "single-request-utility-or-identity-failure"
    if (
        paired_wins >= MIN_PAIRED_WINS
        and prompt_speedup >= MIN_MEDIAN_SPEEDUP
        and ttft_speedup >= MIN_MEDIAN_SPEEDUP
        and effective_wall_speedup >= MIN_MEDIAN_SPEEDUP
        and full_lifecycle_wall_advantage
        and full_lifecycle_fresh_advantage
        and predecessor_improvement_gate
        and direct_control_drift_gate
    ):
        return "fast-single-request-catalytic-latency-supported-bounded"
    return "exact-reuse-without-preregistered-latency-gate"


def evaluate(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    root: Mapping[str, Any],
    baseline_private: int | None,
    root_boundary: str = "task-a",
    speculative_mode: str = "none",
    root_storage: str = "host",
) -> dict[str, Any]:
    harness.require(speculative_mode in SPECULATIVE_MODES, "unsupported latency speculative mode")
    harness.require(root_storage in ROOT_STORAGE_MODES, "unsupported latency root storage mode")
    harness.require(speculative_mode == "none" or root_storage == "host", "speculation and device root cannot be combined")
    panel = water.panel_for(root)
    harness.require(water.base._panel_hash(panel) == PANEL_SHA256, "qualified water panel identity changed")
    spec = panel[BRANCH_NUMBER - 1]
    harness.require(spec["answer"] == EXPECTED_ANSWER, "latency branch key changed")

    prompt_text = codec.render_messages(
        harness.carrier.task_a_messages(root),
        harness.carrier.CHAT_TEMPLATE_KWARGS,
    )
    prompt_tokens = codec.tokenize(prompt_text)
    harness.require(len(prompt_tokens) == EXPECTED_PROMPT_ROOT_TOKENS, "prompt-root token count changed")
    task_payload = harness.carrier._task_a_payload(
        prompt_tokens,
        seed=shared_tasks.derive_seed(ROOT_ID, "task-a"),
    )
    task_a = harness.run_completion(sidecar, f"{ROOT_ID}:latency:task-a", task_payload)
    parsed = harness.carrier.parse_task_a_output(task_a["content"])
    harness.require(parsed["answer"] == harness.EXPECTED[ROOT_ID]["task_a"], "latency Task-A answer is incorrect")
    retained = harness.carrier.derive_retained_root(
        harness.root_capture(task_a, task_payload),
        prompt_tokens,
        codec,
        props,
    )
    harness.require(
        int(retained["retained_root_token_count"]) == EXPECTED_RETAINED_ROOT_TOKENS,
        "retained water root token count changed",
    )
    branch_tokens, _ = branch_request(codec, retained, spec, cache_prompt=False)
    harness.require(len(branch_tokens) == EXPECTED_BRANCH_PROMPT_TOKENS, "latency branch prompt count changed")
    boundary = select_root_boundary(root_boundary, prompt_tokens=prompt_tokens, branch_tokens=branch_tokens)
    root_tokens = list(boundary["tokens"])

    materialization_payload = harness.carrier._branch_payload(
        root_tokens,
        seed=shared_tasks.derive_seed(ROOT_ID, "single-request-latency-prompt-root-materialize"),
        cache_prompt=False,
        n_predict=0,
    )
    materialization = harness.run_completion(
        sidecar,
        f"{ROOT_ID}:latency:{root_boundary}-root-materialize",
        materialization_payload,
        operation_kind="zero-output-root-readdress",
    )
    harness.require(materialization["prompt_tokens"] == len(root_tokens), "materialized root-boundary prompt count changed")
    harness.require(materialization["cached_prompt_tokens"] == 0, "prompt-root materialization reused cache")
    harness.require(materialization["completion_tokens"] == 0, "prompt-root materialization emitted output")

    save_raw, save_wall = harness.ram_root_action(action="root-save", root_id=ROOT_ID)
    saved = validate_root_response(save_raw, action="root-save", root_storage=root_storage)
    harness.require(saved["n_tokens"] == len(root_tokens), "saved root-boundary token count changed")
    if root_storage == "device":
        harness.require(
            saved["n_bytes"] == STRICT_PREFIX_LOGICAL_ROOT_BYTES,
            "CUDA RAM-root logical state size differs from canonical strict-prefix root",
        )
    root_operations: list[dict[str, Any]] = [{**saved, "client_wall_seconds": save_wall}]

    def restore(label: str) -> dict[str, Any]:
        response_raw, wall = harness.ram_root_action(action="root-restore", root_id=ROOT_ID)
        response = validate_root_response(response_raw, action="root-restore", expected=saved, root_storage=root_storage)
        response.update(label=label, client_wall_seconds=wall)
        root_operations.append(response)
        return response

    def execute_route(route: str, label: str, *, counted: bool, pair: int) -> dict[str, Any]:
        restore_wall = 0.0
        restore_record: dict[str, Any] | None = None
        if route == "catalytic":
            restore_record = restore(f"before-{label}")
            restore_wall = float(restore_record["client_wall_seconds"])
        record = run_timed_branch(
            sidecar=sidecar,
            codec=codec,
            retained=retained,
            spec=spec,
            route=route,
            label=f"{ROOT_ID}:latency:{label}:{route}",
        )
        if route == "catalytic":
            harness.require(
                record["cached_prompt_tokens"] == boundary["expected_cached_prompt_tokens"],
                "catalytic route cached-prompt split changed",
            )
            harness.require(record["fresh_prompt_tokens"] == boundary["expected_fresh_prompt_tokens"], "catalytic route fresh-prompt split changed")
        else:
            harness.require(record["cached_prompt_tokens"] == 0, "direct route reused prompt cache")
            harness.require(record["fresh_prompt_tokens"] == len(branch_tokens), "direct route fresh-prompt count changed")
        record.update(
            counted=counted,
            pair=pair,
            restore=restore_record,
            restore_client_wall_seconds=restore_wall,
            effective_wall_seconds=float(record["wall_seconds"]) + restore_wall,
        )
        record["reported_route"] = (
            "catalytic"
            if route == "catalytic"
            else "ngram-only-control"
            if speculative_mode == "ngram-cache"
            else "direct"
        )
        return record

    resources_before_learning = (
        harness.process_resources(sidecar, baseline_private)
        if speculative_mode == "ngram-cache"
        else None
    )
    resources_after_learning = None
    warmup: list[dict[str, Any]] = []
    for index, route in enumerate(WARMUP_ROUTE_ORDER, start=1):
        warmup.append(execute_route(route, f"warmup-{index}", counted=False, pair=0))
        if speculative_mode == "ngram-cache" and route == "catalytic":
            harness.require(resources_after_learning is None, "ngram learning sample was captured twice")
            resources_after_learning = harness.process_resources(sidecar, baseline_private)
    harness.require(
        speculative_mode != "ngram-cache" or resources_after_learning is not None,
        "ngram post-learning resource sample is missing",
    )
    resources_after_all_learning_warmups = (
        harness.process_resources(sidecar, baseline_private)
        if speculative_mode == "ngram-cache"
        else None
    )
    pairs: list[dict[str, Any]] = []
    counted_records: list[dict[str, Any]] = []
    for pair_index, route_order in enumerate(PAIR_ROUTE_ORDERS, start=1):
        records = [
            execute_route(route, f"pair-{pair_index}-route-{ordinal}", counted=True, pair=pair_index)
            for ordinal, route in enumerate(route_order, start=1)
        ]
        by_route = {str(record["route"]): record for record in records}
        harness.require(set(by_route) == {"catalytic", "direct"}, "counted pair lost a route")
        pairs.append(
            {
                "pair": pair_index,
                "route_order": list(route_order),
                "catalytic_effective_wall_seconds": by_route["catalytic"]["effective_wall_seconds"],
                "direct_wall_seconds": by_route["direct"]["effective_wall_seconds"],
                "control_type": "cache-disabled-ngram-only" if speculative_mode == "ngram-cache" else "cache-disabled-no-spec",
                "control_effective_wall_seconds": by_route["direct"]["effective_wall_seconds"],
                "catalytic_won": by_route["catalytic"]["effective_wall_seconds"] < by_route["direct"]["effective_wall_seconds"],
            }
        )
        counted_records.extend(records)

    final_restore = restore("final-root-closure")
    resources_after_trials_with_root = harness.process_resources(sidecar, baseline_private)
    erase_raw, erase_wall = harness.ram_root_action(action="root-erase", root_id=ROOT_ID)
    erased = validate_root_response(erase_raw, action="root-erase", expected=saved, root_storage=root_storage)
    erased.update(client_wall_seconds=erase_wall)
    root_operations.append(erased)
    resources_after_erase = harness.process_resources(sidecar, baseline_private)

    all_routes = [*warmup, *counted_records]
    catalytic = [record for record in counted_records if record["route"] == "catalytic"]
    direct = [record for record in counted_records if record["route"] == "direct"]
    harness.require(len(catalytic) == COUNTED_PAIRS and len(direct) == COUNTED_PAIRS, "counted route cardinality changed")
    input_hashes = {record["input_token_sha256"] for record in all_routes}
    generated_hashes = {record["generated_token_sha256"] for record in all_routes}
    utility_exact = (
        all(bool(record["correct"]) for record in all_routes)
        and len(input_hashes) == 1
        and len(generated_hashes) == 1
        and all(record["cached_prompt_tokens"] == boundary["expected_cached_prompt_tokens"] for record in catalytic)
        and all(record["fresh_prompt_tokens"] == boundary["expected_fresh_prompt_tokens"] for record in catalytic)
        and all(record["cached_prompt_tokens"] == 0 for record in direct)
    )

    catalytic_prompt_ms = [float(record["timing"]["prompt_ms"]) for record in catalytic]
    direct_prompt_ms = [float(record["timing"]["prompt_ms"]) for record in direct]
    catalytic_ttft = [float(record["timing"]["ttft_seconds"]) + float(record["restore_client_wall_seconds"]) for record in catalytic]
    direct_ttft = [float(record["timing"]["ttft_seconds"]) for record in direct]
    catalytic_effective_wall = [float(record["effective_wall_seconds"]) for record in catalytic]
    direct_effective_wall = [float(record["effective_wall_seconds"]) for record in direct]
    catalytic_predicted_ms = [float(record["timing"]["predicted_ms"]) for record in catalytic]
    draft_metrics = draft_acceptance_metrics(catalytic, direct)
    draft_acceptance_gate = (
        speculative_mode == "none"
        or bool(draft_metrics["gate"])
    )
    strict_prefix_ngram_speedups = None
    strict_prefix_ngram_speed_gate = True
    prompt_speedup = statistics.median(direct_prompt_ms) / statistics.median(catalytic_prompt_ms)
    ttft_speedup = statistics.median(direct_ttft) / statistics.median(catalytic_ttft)
    effective_wall_speedup = statistics.median(direct_effective_wall) / statistics.median(catalytic_effective_wall)
    if speculative_mode == "ngram-cache":
        strict_prefix_ngram_speedups = {
            "predicted": STRICT_PREFIX_NO_SPEC_MEDIANS["predicted_ms"] / statistics.median(catalytic_predicted_ms),
            "effective_wall_including_restore": STRICT_PREFIX_NO_SPEC_MEDIANS["effective_wall_seconds_including_restore"] / statistics.median(catalytic_effective_wall),
        }
        strict_prefix_ngram_speed_gate = all(value >= STRICT_PREFIX_NGRAM_MIN_SPEEDUP for value in strict_prefix_ngram_speedups.values())
    predecessor_speedups: dict[str, float] | None = None
    predecessor_improvement_gate = True
    predecessor = boundary.get("predecessor_medians")
    if isinstance(predecessor, Mapping):
        predecessor_speedups = {
            "prompt": float(predecessor["prompt_ms"]) / statistics.median(catalytic_prompt_ms),
            "ttft_including_restore": float(predecessor["ttft_seconds_including_restore"]) / statistics.median(catalytic_ttft),
            "effective_wall_including_restore": float(predecessor["effective_wall_seconds_including_restore"])
            / statistics.median(catalytic_effective_wall),
        }
        predecessor_improvement_gate = all(value >= MIN_MEDIAN_SPEEDUP for value in predecessor_speedups.values())
    direct_control_drift: dict[str, float] | None = None
    direct_control_drift_gate = True
    predecessor_direct = (
        STRICT_PREFIX_NO_SPEC_DIRECT_MEDIANS
        if speculative_mode == "ngram-cache"
        else boundary.get("predecessor_direct_medians")
    )
    if isinstance(predecessor_direct, Mapping):
        observed_direct = {
            "prompt_ms": statistics.median(direct_prompt_ms),
            "ttft_seconds": statistics.median(direct_ttft),
            "effective_wall_seconds": statistics.median(direct_effective_wall),
        }
        direct_control_drift = {
            key: abs(float(observed_direct[key]) / float(reference) - 1.0)
            for key, reference in predecessor_direct.items()
        }
        direct_control_drift_gate = all(
            value <= MAX_DIRECT_CONTROL_DRIFT_FRACTION for value in direct_control_drift.values()
        )
    control_metric_label = "ngram_only_control" if speculative_mode == "ngram-cache" else "direct"
    control_drift_metric_name = "ngram_only_control_change_vs_neo_exp_0064_no_spec" if speculative_mode == "ngram-cache" else "direct_control_drift_vs_neo_exp_0062"
    paired_wins = sum(int(pair["catalytic_won"]) for pair in pairs)
    ngram_branch_phase_private_change: dict[str, int] | None = None
    after_erase_private_growth_delta_vs_no_spec: int | None = None
    ngram_private_growth_gate = True
    if speculative_mode == "ngram-cache":
        resource_samples = (
            resources_before_learning,
            resources_after_learning,
            resources_after_all_learning_warmups,
            resources_after_trials_with_root,
            resources_after_erase,
        )
        harness.require(all(isinstance(sample, Mapping) for sample in resource_samples), "ngram resource samples are incomplete")
        before_private = int(resources_before_learning["host_private_bytes"])
        ngram_branch_phase_private_change = {
            "after_catalytic_warmup": int(resources_after_learning["host_private_bytes"]) - before_private,
            "after_all_warmups": int(resources_after_all_learning_warmups["host_private_bytes"]) - before_private,
            "after_counted_trials_with_root": int(resources_after_trials_with_root["host_private_bytes"]) - before_private,
            "after_root_erase_with_ngram_resident": int(resources_after_erase["host_private_bytes"]) - before_private,
        }
        after_erase_private_growth_delta_vs_no_spec = (
            int(resources_after_erase["host_private_growth_bytes"])
            - STRICT_PREFIX_NO_SPEC_AFTER_ERASE_PRIVATE_GROWTH_BYTES
        )
        ngram_private_growth_gate = max(ngram_branch_phase_private_change.values()) <= MAX_NGRAM_PRIVATE_GROWTH_BYTES and after_erase_private_growth_delta_vs_no_spec <= MAX_NGRAM_PRIVATE_GROWTH_BYTES

    median_direct_wall = statistics.median(direct_effective_wall)
    median_catalytic_wall = statistics.median(catalytic_effective_wall)
    marginal_wall_savings = median_direct_wall - median_catalytic_wall
    closure_wall = float(final_restore["client_wall_seconds"]) + float(erase_wall)
    preparation_and_closure_wall = float(materialization["wall_seconds"]) + float(save_wall) + closure_wall
    wall_break_even = math.ceil(preparation_and_closure_wall / marginal_wall_savings) if marginal_wall_savings > 0 else None
    median_direct_fresh = statistics.median([int(record["fresh_model_tokens"]) for record in direct])
    median_catalytic_fresh = statistics.median([int(record["fresh_model_tokens"]) for record in catalytic])
    marginal_fresh_savings = median_direct_fresh - median_catalytic_fresh
    preparation_and_closure_fresh = int(materialization["fresh_model_tokens"])
    fresh_break_even = math.ceil(preparation_and_closure_fresh / marginal_fresh_savings) if marginal_fresh_savings > 0 else None
    shared_task_a_wall = float(task_a["wall_seconds"])
    shared_task_a_fresh = int(task_a["fresh_model_tokens"])
    learning_wall = sum(float(record["effective_wall_seconds"]) for record in warmup) if speculative_mode == "ngram-cache" else 0.0
    learning_fresh = sum(int(record["fresh_model_tokens"]) for record in warmup) if speculative_mode == "ngram-cache" else 0
    counted_catalytic_lifecycle_wall = shared_task_a_wall + preparation_and_closure_wall + sum(catalytic_effective_wall)
    counted_direct_lifecycle_wall = shared_task_a_wall + sum(direct_effective_wall)
    counted_catalytic_lifecycle_fresh = shared_task_a_fresh + preparation_and_closure_fresh + sum(int(record["fresh_model_tokens"]) for record in catalytic)
    counted_direct_lifecycle_fresh = shared_task_a_fresh + sum(int(record["fresh_model_tokens"]) for record in direct)
    if speculative_mode == "ngram-cache":
        counted_catalytic_lifecycle_wall += learning_wall
        counted_catalytic_lifecycle_fresh += learning_fresh
        counted_direct_lifecycle_wall = STRICT_PREFIX_NO_SPEC_DIRECT_LIFECYCLE_WALL_SECONDS
        counted_direct_lifecycle_fresh = STRICT_PREFIX_NO_SPEC_DIRECT_LIFECYCLE_FRESH_TOKENS
    full_lifecycle_wall_advantage = counted_catalytic_lifecycle_wall < counted_direct_lifecycle_wall
    full_lifecycle_fresh_advantage = counted_catalytic_lifecycle_fresh < counted_direct_lifecycle_fresh
    counted_restore_server_ms = [float(record["restore"]["server_root_ms"]) for record in catalytic]
    cuda_root_metrics: dict[str, Any] | None = None
    cuda_root_gate = True
    if root_storage == "device":
        restore_distribution = distribution(counted_restore_server_ms)
        restore_speedup = STRICT_PREFIX_HOST_ROOT_RESTORE_SERVER_MEDIAN_MS / restore_distribution["median"]
        wall_speedup_vs_host = STRICT_PREFIX_NO_SPEC_MEDIANS["effective_wall_seconds_including_restore"] / median_catalytic_wall
        device_accounting_gate = (
            int(saved["n_host_bytes"]) > 0
            and int(saved["n_device_bytes"]) > 0
            and int(saved["n_gpu_bytes"]) > 0
            and int(saved["n_gpu_bytes"]) <= int(saved["n_device_bytes"])
            and int(saved["n_host_bytes"]) < int(saved["n_bytes"])
            and int(erased["n_device_bytes_after"]) == 0
            and int(erased["n_gpu_bytes_after"]) == 0
        )
        cuda_root_gate = (
            restore_speedup >= CUDA_ROOT_MIN_RESTORE_SPEEDUP
            and wall_speedup_vs_host >= CUDA_ROOT_MIN_EFFECTIVE_WALL_SPEEDUP
            and device_accounting_gate
        )
        cuda_root_metrics = {
            "canonical_host_restore_server_median_ms": STRICT_PREFIX_HOST_ROOT_RESTORE_SERVER_MEDIAN_MS,
            "counted_device_restore_server_ms": restore_distribution,
            "restore_server_speedup": restore_speedup,
            "minimum_restore_server_speedup": CUDA_ROOT_MIN_RESTORE_SPEEDUP,
            "effective_wall_speedup_vs_neo_exp_0064_host_root": wall_speedup_vs_host,
            "minimum_effective_wall_speedup": CUDA_ROOT_MIN_EFFECTIVE_WALL_SPEEDUP,
            "device_accounting_gate": device_accounting_gate,
            "gate": cuda_root_gate,
        }
    classification = classify_result(
        utility_exact=utility_exact,
        paired_wins=paired_wins,
        prompt_speedup=prompt_speedup,
        ttft_speedup=ttft_speedup,
        effective_wall_speedup=effective_wall_speedup,
        full_lifecycle_wall_advantage=full_lifecycle_wall_advantage,
        full_lifecycle_fresh_advantage=full_lifecycle_fresh_advantage,
        predecessor_improvement_gate=predecessor_improvement_gate,
        direct_control_drift_gate=direct_control_drift_gate,
    )
    if speculative_mode == "ngram-cache":
        classification = (
            "strict-prefix-plus-ngram-cache-latency-supported-bounded"
            if classification == "fast-single-request-catalytic-latency-supported-bounded"
            and draft_acceptance_gate
            and strict_prefix_ngram_speed_gate
            and ngram_private_growth_gate
            else "strict-prefix-plus-ngram-cache-without-preregistered-latency-gate"
        )
    if root_storage == "device":
        classification = (
            "cuda-resident-strict-prefix-root-latency-supported-bounded"
            if classification == "fast-single-request-catalytic-latency-supported-bounded"
            and cuda_root_gate
            else "cuda-resident-strict-prefix-root-without-preregistered-latency-gate"
        )
    accepted = classification in {
        "fast-single-request-catalytic-latency-supported-bounded",
        "strict-prefix-plus-ngram-cache-latency-supported-bounded",
        "cuda-resident-strict-prefix-root-latency-supported-bounded",
    }
    all_request_records = [task_a, materialization, *all_routes]

    return {
        "status": "complete",
        "mechanism": (
            f"checkpoint-free-{root_boundary}-CUDA-resident-root-single-request-latency"
            if root_storage == "device"
            else f"checkpoint-free-{root_boundary}-root-{speculative_mode}-single-request-latency"
            if speculative_mode != "none"
            else f"checkpoint-free-{root_boundary}-root-single-request-latency"
        ),
        "verdict": "accept" if accepted else "reject",
        "classification": classification,
        "model": "Agents-A1",
        "root_id": ROOT_ID,
        "branch": {
            "number": BRANCH_NUMBER,
            "expected": EXPECTED_ANSWER,
            "panel_sha256": PANEL_SHA256,
            "prompt_tokens": len(branch_tokens),
            "task_a_prompt_tokens": len(prompt_tokens),
            "prompt_root_tokens": len(root_tokens),
            "root_boundary": root_boundary,
            "retained_root_tokens": int(retained["retained_root_token_count"]),
            "input_token_sha256": next(iter(input_hashes)),
            "generated_token_sha256": next(iter(generated_hashes)) if len(generated_hashes) == 1 else None,
        },
        "trial_design": {
            "fanout": 1,
            "temporal_counted_pairs": COUNTED_PAIRS,
            "warmup_route_order": list(WARMUP_ROUTE_ORDER),
            "pair_route_orders": [list(order) for order in PAIR_ROUTE_ORDERS],
            "minimum_paired_wins": MIN_PAIRED_WINS,
            "minimum_median_speedup": MIN_MEDIAN_SPEEDUP,
            "context_checkpoints": 0,
            "root_boundary": root_boundary,
            "root_storage": root_storage,
            "speculative_mode": speculative_mode,
            "cache_disabled_route_label": "ngram-only" if speculative_mode == "ngram-cache" else "direct",
            "learning_warmup_charged": speculative_mode == "ngram-cache",
            "control_type": "cache-disabled-ngram-only" if speculative_mode == "ngram-cache" else "cache-disabled-no-spec",
            "second_carrier_closure": "process-retirement" if speculative_mode == "ngram-cache" else None,
            "learning_warmup_requests_charged": len(warmup) if speculative_mode == "ngram-cache" else 0,
            "expected_catalytic_cached_prompt_tokens": boundary["expected_cached_prompt_tokens"],
            "expected_catalytic_fresh_prompt_tokens": boundary["expected_fresh_prompt_tokens"],
        },
        "metrics": {
            "paired_wins": paired_wins,
            "prompt_speedup": prompt_speedup,
            "ttft_speedup_including_restore": ttft_speedup,
            "effective_wall_speedup_including_restore": effective_wall_speedup,
            "prompt_ms": {"catalytic": distribution(catalytic_prompt_ms), control_metric_label: distribution(direct_prompt_ms)},
            "ttft_seconds": {"catalytic": distribution(catalytic_ttft), control_metric_label: distribution(direct_ttft)},
            "effective_wall_seconds": {"catalytic": distribution(catalytic_effective_wall), control_metric_label: distribution(direct_effective_wall)},
            "fresh_model_tokens_per_request": {"catalytic_median": median_catalytic_fresh, f"{control_metric_label}_median": median_direct_fresh},
            "speedup_vs_neo_exp_0062_543_root": predecessor_speedups,
            "cuda_root": cuda_root_metrics,
            "ngram_cache": {
                "catalytic_counted_draft_tokens": draft_metrics["catalytic_draft_tokens"],
                "catalytic_counted_accepted_draft_tokens": draft_metrics["catalytic_accepted_draft_tokens"],
                "catalytic_accepted_fraction": draft_metrics["catalytic_accepted_fraction"],
                "control_counted_draft_tokens": draft_metrics["control_draft_tokens"],
                "control_counted_accepted_draft_tokens": draft_metrics["control_accepted_draft_tokens"],
                "every_catalytic_request_accepted_a_draft": draft_metrics["every_catalytic_request_accepted_a_draft"],
                "draft_acceptance_gate": draft_acceptance_gate,
                "speedup_vs_neo_exp_0064_strict_prefix_no_spec": strict_prefix_ngram_speedups,
                "strict_prefix_speed_gate": strict_prefix_ngram_speed_gate,
                "observed_branch_phase_host_private_change_bytes": ngram_branch_phase_private_change,
                "canonical_no_spec_after_erase_host_private_growth_bytes": STRICT_PREFIX_NO_SPEC_AFTER_ERASE_PRIVATE_GROWTH_BYTES,
                "after_erase_host_private_growth_delta_vs_no_spec_bytes": after_erase_private_growth_delta_vs_no_spec,
                "maximum_allowed_host_private_growth_bytes": MAX_NGRAM_PRIVATE_GROWTH_BYTES,
                "host_private_growth_gate": ngram_private_growth_gate,
            },
            control_drift_metric_name: {
                "maximum_allowed_fraction": MAX_DIRECT_CONTROL_DRIFT_FRACTION,
                "absolute_fraction_by_metric": direct_control_drift,
                "gate": direct_control_drift_gate,
            },
            "break_even": {
                "preparation_and_closure_wall_seconds": preparation_and_closure_wall,
                "closure_wall_seconds": closure_wall,
                "marginal_wall_savings_seconds": marginal_wall_savings,
                "wall_requests": wall_break_even,
                "preparation_and_closure_fresh_model_tokens": preparation_and_closure_fresh,
                "marginal_fresh_model_token_savings": marginal_fresh_savings,
                "fresh_compute_requests": fresh_break_even,
            },
            "counted_full_lifecycle": {
                "scope": (
                    "shared Task-A plus root preparation, both charged launch-global ngram-mutating warmups, four N=1 requests, every restore, final root closure and erase, and process-retirement ngram closure"
                    if speculative_mode == "ngram-cache"
                    else "shared Task-A plus carrier preparation, four N=1 requests, every restore, final closure, and erase; warmup excluded symmetrically from decision"
                ),
                "direct_baseline": "canonical-neo-exp-0064-no-spec" if speculative_mode == "ngram-cache" else "contemporaneous-cache-disabled",
                "learning_warmup_wall_seconds": learning_wall,
                "learning_warmup_fresh_model_tokens": learning_fresh,
                "shared_task_a_wall_seconds": shared_task_a_wall,
                "shared_task_a_fresh_model_tokens": shared_task_a_fresh,
                "catalytic_wall_seconds": counted_catalytic_lifecycle_wall,
                "direct_wall_seconds": counted_direct_lifecycle_wall,
                "wall_speedup": counted_direct_lifecycle_wall / counted_catalytic_lifecycle_wall,
                "catalytic_fresh_model_tokens": counted_catalytic_lifecycle_fresh,
                "direct_fresh_model_tokens": counted_direct_lifecycle_fresh,
                "fresh_compute_amplification": counted_direct_lifecycle_fresh / counted_catalytic_lifecycle_fresh,
            },
            "full_experiment": {
                "model_requests": len(all_request_records),
                "fresh_model_tokens": sum(int(record["fresh_model_tokens"]) for record in all_request_records),
                "request_wall_seconds": sum(float(record["wall_seconds"]) for record in all_request_records),
                "root_operation_client_wall_seconds": sum(float(record["client_wall_seconds"]) for record in root_operations),
            },
        },
        "task_a": harness.token_summary(task_a),
        "root_materialization": harness.token_summary(materialization),
        "saved_root": saved,
        "warmup": warmup,
        "counted_records": counted_records,
        "pairs": pairs,
        "root_operations": root_operations,
        "final_restore": final_restore,
        "resources": (
            {
                "after_task_a_and_root_preparation_before_branch_warmups": resources_before_learning,
                "immediately_after_catalytic_learning_warmup": resources_after_learning,
                "after_all_learning_warmups_before_counted_trials": resources_after_all_learning_warmups,
                "after_complete_trial_with_root": resources_after_trials_with_root,
                "after_root_erase_with_ngram_resident": resources_after_erase,
            }
            if speculative_mode == "ngram-cache"
            else {"with_root": resources_after_trials_with_root, "after_erase": resources_after_erase}
        ),
        "quality_gates": {
            "qualified_panel_identity_exact": True,
            "branch_fixed_before_successor_contact": True,
            "task_a_correct": True,
            "all_warmup_and_counted_outputs_correct": all(bool(record["correct"]) for record in all_routes),
            "all_input_token_arrays_identical": len(input_hashes) == 1,
            "all_generated_token_hashes_identical": len(generated_hashes) == 1,
            "catalytic_cached_prompt_tokens_exact": all(record["cached_prompt_tokens"] == boundary["expected_cached_prompt_tokens"] for record in catalytic),
            "catalytic_fresh_prompt_tokens_exact": all(record["fresh_prompt_tokens"] == boundary["expected_fresh_prompt_tokens"] for record in catalytic),
            "direct_cached_prompt_tokens_zero": all(record["cached_prompt_tokens"] == 0 for record in direct),
            "predecessor_543_root_median_speedup_gate": predecessor_improvement_gate,
            "cache_disabled_control_change_within_10_percent": direct_control_drift_gate,
            "checkpoint_count_zero": saved["n_checkpoints"] == 0,
            "root_metadata_invariant": all(
                record.get("n_tokens") == saved["n_tokens"]
                and record.get("n_bytes") == saved["n_bytes"]
                and (root_storage != "device" or record.get("n_host_bytes") == saved["n_host_bytes"])
                and (root_storage != "device" or record.get("n_device_bytes") == saved["n_device_bytes"])
                and (root_storage != "device" or record.get("n_gpu_bytes") == saved["n_gpu_bytes"])
                and record.get("n_checkpoints") == 0
                for record in root_operations
            ),
            "cuda_device_bytes_nonzero": root_storage != "device" or int(saved["n_device_bytes"]) > 0,
            "cuda_gpu_bytes_nonzero": root_storage != "device" or int(saved["n_gpu_bytes"]) > 0,
            "cuda_device_bytes_zero_after_erase": root_storage != "device" or int(erased["n_device_bytes_after"]) == 0,
            "cuda_gpu_bytes_zero_after_erase": root_storage != "device" or int(erased["n_gpu_bytes_after"]) == 0,
            "cuda_restore_speedup_gate": root_storage != "device" or bool(cuda_root_metrics and cuda_root_metrics["restore_server_speedup"] >= CUDA_ROOT_MIN_RESTORE_SPEEDUP),
            "cuda_effective_wall_speedup_gate": root_storage != "device" or bool(cuda_root_metrics and cuda_root_metrics["effective_wall_speedup_vs_neo_exp_0064_host_root"] >= CUDA_ROOT_MIN_EFFECTIVE_WALL_SPEEDUP),
            "final_restore_before_erase": final_restore["action"] == "root-restore",
            "explicit_erase": erased["action"] == "root-erase",
            "paired_win_gate": paired_wins >= MIN_PAIRED_WINS,
            "prompt_speedup_gate": prompt_speedup >= MIN_MEDIAN_SPEEDUP,
            "ttft_speedup_gate": ttft_speedup >= MIN_MEDIAN_SPEEDUP,
            "effective_wall_speedup_gate": effective_wall_speedup >= MIN_MEDIAN_SPEEDUP,
            "ngram_draft_acceptance_gate": draft_acceptance_gate,
            "strict_prefix_ngram_speedup_gate": strict_prefix_ngram_speed_gate,
            "learning_warmup_charged": speculative_mode != "ngram-cache" or learning_wall > 0,
            "ngram_second_carrier_declared": speculative_mode != "ngram-cache" or resources_after_learning is not None,
            "ngram_host_private_growth_bounded": ngram_private_growth_gate,
            "ngram_process_retirement_closure": None if speculative_mode == "ngram-cache" else True,
            "counted_full_lifecycle_wall_advantage": full_lifecycle_wall_advantage,
            "counted_full_lifecycle_fresh_compute_advantage": full_lifecycle_fresh_advantage,
            "fast_single_request_catalytic_inference_supported": accepted,
            "fanout_claimed": False,
            "unbounded_catalytic_inference_established": False,
            "automatic_promotion": False,
        },
        "next_boundary": (
            "PROFILE_NEXT_CUDA_CATALYTIC_HOT_PATH_AFTER_ACCEPTED_DEVICE_ROOT"
            if accepted and root_storage == "device"
            else "PRESERVE_DEVICE_ROOT_EVIDENCE_AND_LOCALIZE_FAILED_CUDA_GATE_WITHOUT_RETRY"
            if root_storage == "device"
            else
            (
                "PROFILE_REMAINING_STRICT_PREFIX_PLUS_NGRAM_CACHE_N1_LATENCY_WITH_THE_SAME_EXACT_CONTROL"
                if root_boundary == "strict-prefix" and speculative_mode == "ngram-cache"
                else
                "PROFILE_DECODE_AND_RESTORE_OVERHEAD_AFTER_STRICT_PREFIX_ROOT_WITH_THE_SAME_N1_CONTROL"
                if root_boundary == "strict-prefix"
                else "PROFILE_DECODE_AND_RESTORE_OVERHEAD_AFTER_FULL_PROMPT_ROOT_WITH_THE_SAME_N1_CONTROL"
                if root_boundary == "full-prompt"
                else "PROFILE_AND_CAUSALLY_LOCALIZE_THE_DOMINANT_REMAINING_SINGLE_REQUEST_HOT_PATH_WITH_THE_SAME_EXACT_CONTROL"
            )
            if accepted
            else "PRESERVE_EXACT_REUSE_AND_LOCALIZE_WHICH_LATENCY_COMPONENT_FAILED_BEFORE_ANY_RUNTIME_INTERVENTION"
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--model", type=Path, default=harness.DEFAULT_MODEL)
    parser.add_argument("--ctx-checkpoints", type=int, choices=(0,), default=0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--server-log-output", type=Path)
    return parser.parse_args()


def require_unused_artifact_paths(*paths: Path | None) -> None:
    resolved = [path.resolve(strict=False) for path in paths if path is not None]
    harness.require(len(resolved) == len(set(resolved)), "latency artifact paths must be distinct")
    for path in paths:
        if path is not None:
            harness.require(not path.resolve(strict=False).exists(), f"latency artifact path already exists: {path}")


def cleanup_peak_wddm_bytes(cleanup: Mapping[str, Any]) -> int | None:
    wddm = cleanup.get("wddm")
    if not isinstance(wddm, Mapping):
        return None
    for key in ("peak_dedicated_bytes", "peak_bytes"):
        value = wddm.get(key)
        if type(value) is int:
            return int(value)
    return None


def readiness_peak_wddm_bytes(readiness: Mapping[str, Any]) -> int | None:
    wddm = readiness.get("wddm")
    if not isinstance(wddm, Mapping):
        return None
    for key in ("peak_dedicated_bytes", "peak_bytes"):
        value = wddm.get(key)
        if type(value) is int:
            return int(value)
    return None


def finalize_result_after_cleanup(
    result: dict[str, Any],
    *,
    cleanup: Mapping[str, Any],
    cleanup_wall_seconds: float,
    stable_pids: set[int],
) -> dict[str, Any]:
    cleanup_record = dict(cleanup)
    cleanup_record["retirement_wall_seconds"] = cleanup_wall_seconds
    result["cleanup"] = cleanup_record
    cleanup_gate = harness.live_runtime.cleanup_integrity(cleanup_record, stable_pids)
    result["cleanup_gate"] = cleanup_gate
    root_storage = result.get("trial_design", {}).get("root_storage")
    if root_storage == "device":
        peak_wddm_bytes = cleanup_peak_wddm_bytes(cleanup_record)
        wddm_gate = type(peak_wddm_bytes) is int and int(peak_wddm_bytes) <= 6000 * 1024 * 1024
        result["metrics"]["cuda_root"]["peak_wddm_bytes"] = peak_wddm_bytes
        result["metrics"]["cuda_root"]["maximum_wddm_bytes"] = 6000 * 1024 * 1024
        result["metrics"]["cuda_root"]["wddm_gate"] = wddm_gate
        quality_gates = result["quality_gates"]
        quality_gates["cuda_wddm_at_or_below_6000_mib"] = wddm_gate
        quality_gates["candidate_process_retired"] = cleanup_gate["passed"] is True
        accepted = result.get("verdict") == "accept" and cleanup_gate["passed"] is True and wddm_gate
        quality_gates["fast_single_request_catalytic_inference_supported"] = accepted
        if not accepted:
            result["verdict"] = "reject"
            result["classification"] = "cuda-resident-strict-prefix-root-without-preregistered-latency-gate"
            result["next_boundary"] = "PRESERVE_DEVICE_ROOT_EVIDENCE_AND_LOCALIZE_FAILED_CUDA_GATE_WITHOUT_RETRY"
        return result

    if result.get("trial_design", {}).get("speculative_mode") != "ngram-cache":
        return result

    result["resources"]["after_process_retirement"] = {
        "process_stopped": cleanup_record.get("process_stopped"),
        "runtime_removed": cleanup_record.get("runtime_removed"),
        "port_free": cleanup_record.get("port_free"),
        "retirement_samples": cleanup_record.get("retirement_samples"),
        "stable_after": cleanup_record.get("stable_after"),
    }
    lifecycle = result["metrics"]["counted_full_lifecycle"]
    before_retirement = float(lifecycle["catalytic_wall_seconds"])
    after_retirement = before_retirement + cleanup_wall_seconds
    direct_wall = float(lifecycle["direct_wall_seconds"])
    wall_advantage = after_retirement < direct_wall
    lifecycle.update(
        catalytic_wall_seconds_before_process_retirement=before_retirement,
        process_retirement_wall_seconds=cleanup_wall_seconds,
        catalytic_wall_seconds=after_retirement,
        wall_speedup=direct_wall / after_retirement,
        wall_advantage=wall_advantage,
    )
    quality_gates = result["quality_gates"]
    quality_gates["ngram_process_retirement_closure"] = cleanup_gate["passed"] is True
    quality_gates["counted_full_lifecycle_wall_advantage"] = wall_advantage
    accepted = result.get("verdict") == "accept" and cleanup_gate["passed"] is True and wall_advantage
    quality_gates["fast_single_request_catalytic_inference_supported"] = accepted
    if not accepted:
        result["verdict"] = "reject"
        result["classification"] = "strict-prefix-plus-ngram-cache-without-preregistered-latency-gate"
        if cleanup_gate["passed"] is not True:
            result["next_boundary"] = "ANALYZE_NEO_EXP_0065_PROCESS_RETIREMENT_CLOSURE_FAILURE_WITHOUT_RETRY"
        elif not wall_advantage:
            result["next_boundary"] = "ANALYZE_NEO_EXP_0065_FULL_LIFECYCLE_LATENCY_FAILURE_WITHOUT_RETRY"
    return result


def main(
    *,
    root_boundary: str = "task-a",
    speculative_mode: str = "none",
    root_storage: str = "host",
    runtime_identity: str = "canonical",
    moe_server_args: tuple[str, ...] = water.checkpoint_control.DEFAULT_MOE_SERVER_ARGS,
) -> int:
    args = parse_args()
    harness.require(speculative_mode in SPECULATIVE_MODES, "unsupported latency speculative mode")
    harness.require(root_storage in ROOT_STORAGE_MODES, "unsupported latency root storage mode")
    harness.require(runtime_identity in RUNTIME_IDENTITY_MODES, "unsupported latency runtime identity")
    moe_server_args = water.checkpoint_control.normalize_moe_server_args(moe_server_args)
    harness.require(speculative_mode == "none" or root_storage == "host", "speculation and device root cannot be combined")
    harness.require(root_storage != "device" or runtime_identity == "cuda-bundle", "device root requires the CUDA runtime bundle")
    repository = Path(__file__).resolve().parents[1]
    binary = args.binary.resolve(strict=True)
    expected_candidate = (repository / DEFAULT_BINARY).resolve(strict=True)
    harness.require(
        binary == expected_candidate,
        "latency discriminator requires the isolated frontier candidate binary path",
    )
    if runtime_identity == "cuda-bundle":
        cuda_runtime_sha256 = verify_cuda_root_runtime(binary)
    else:
        cuda_runtime_sha256 = None
        water.require_pinned_binary(binary)
    model = args.model.resolve(strict=True)
    require_unused_artifact_paths(args.output, args.server_log_output)
    corpus = harness.carrier.load_public_corpus(repository)
    roots = {str(item["root_id"]): item for item in corpus["roots"]}
    evaluator, live_contract = harness.load_discovery_sidecar_contract()
    stable_pids = harness.live_runtime.require_stable()
    harness.require(len(stable_pids) == 1, "latency discriminator requires the sole stable listener")
    harness.require(not harness.live_runtime.listener_pids(harness.live_runtime.PORT), "frontier port is occupied")
    state_root = Path(tempfile.mkdtemp(prefix="neo3000-single-request-latency-"))
    sidecar: Any | None = None
    result: dict[str, Any] | None = None
    cleanup: Mapping[str, Any] | None = None
    cleanup_wall_seconds = 0.0
    error: BaseException | None = None
    if args.server_log_output is not None:
        os.environ["LLAMA_ARG_LOG_VERBOSITY"] = "1000"
        os.environ["LLAMA_SERVER_SLOTS_DEBUG"] = "1"
    try:
        sidecar = water.build_sidecar(
            binary=binary,
            model=model,
            evaluator=evaluator,
            live_contract=live_contract,
            stable_pids=set(stable_pids),
            state_root=state_root,
            context_checkpoints=args.ctx_checkpoints,
            server_launch_args=(
                water.checkpoint_control.CUDA_ROOT_SERVER_ARGS
                if root_storage == "device"
                else water.checkpoint_control.NGRAM_CACHE_SERVER_ARGS
                if speculative_mode == "ngram-cache"
                else ()
            ),
            moe_server_args=moe_server_args,
        )
        readiness = sidecar.launch()
        launch_configuration = readiness.get("launch_configuration")
        expected_launch_args = (
            list(water.checkpoint_control.CUDA_ROOT_SERVER_ARGS)
            if root_storage == "device"
            else list(water.checkpoint_control.NGRAM_CACHE_SERVER_ARGS)
            if speculative_mode == "ngram-cache"
            else []
        )
        harness.require(
            isinstance(launch_configuration, Mapping)
            and launch_configuration.get("server_launch_args") == expected_launch_args
            and launch_configuration.get("moe_server_args") == list(moe_server_args)
            and launch_configuration.get("speculative_type") == speculative_mode
            and launch_configuration.get("root_storage") == root_storage,
            "sidecar launch identity differs from the preregistered storage and speculative modes",
        )
        if moe_server_args in (
            water.checkpoint_control.PARTIAL_MOE_26_SERVER_ARGS,
            water.checkpoint_control.PARTIAL_MOE_33_SERVER_ARGS,
        ):
            readiness_wddm_bytes = readiness_peak_wddm_bytes(readiness)
            harness.require(
                type(readiness_wddm_bytes) is int and readiness_wddm_bytes <= 6000 * 1024 * 1024,
                "partial-MoE readiness WDDM is missing or above 6000 MiB",
            )
        baseline_private = None
        process_memory = readiness.get("process_memory")
        if isinstance(process_memory, Mapping) and isinstance(process_memory.get("private_bytes"), int):
            baseline_private = int(process_memory["private_bytes"])
        codec = harness.carrier.SidecarPromptCodec(harness.live_runtime.PORT)
        result = evaluate(
            sidecar=sidecar,
            codec=codec,
            props=codec.props(),
            root=roots[ROOT_ID],
            baseline_private=baseline_private,
            root_boundary=root_boundary,
            speculative_mode=speculative_mode,
            root_storage=root_storage,
        )
        result["launch_configuration"] = readiness.get("launch_configuration")
        result["cuda_runtime_sha256"] = cuda_runtime_sha256
        result["runtime_identity"] = runtime_identity
        result["moe_server_args"] = list(moe_server_args)
        result["readiness"] = {
            "pid": readiness.get("pid"),
            "readiness_seconds": readiness.get("readiness_seconds"),
            "binary": readiness.get("binary"),
            "model": readiness.get("model"),
            "baseline_private_bytes": baseline_private,
            "launch_configuration": readiness.get("launch_configuration"),
            "wddm": readiness.get("wddm"),
        }
    except BaseException as exc:
        error = exc
    finally:
        cleanup_started = time.monotonic()
        cleanup = dict(harness.live_runtime.safe_sidecar_cleanup(sidecar))
        cleanup_wall_seconds = time.monotonic() - cleanup_started
        if args.server_log_output is not None:
            trace_record: dict[str, Any] = {"requested": str(args.server_log_output)}
            try:
                log_path = Path(str(sidecar.readiness.get("log_path"))) if sidecar is not None else None
                if log_path is None or not log_path.is_file():
                    raise FileNotFoundError("sidecar log is unavailable")
                args.server_log_output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(log_path, args.server_log_output)
                trace_record.update(copied=True, bytes=args.server_log_output.stat().st_size)
            except BaseException as exc:
                trace_record.update(copied=False, error=f"{type(exc).__name__}: {exc}")
            cleanup["server_log_copy"] = trace_record
        shutil.rmtree(state_root, ignore_errors=True)

    if error is not None:
        print(json.dumps({"status": "engineering-failure", "error_type": type(error).__name__, "error": str(error), "cleanup": cleanup}, ensure_ascii=False, indent=2))
        return 1
    harness.require(result is not None, "single-request latency result is missing")
    result = finalize_result_after_cleanup(
        result,
        cleanup=dict(cleanup or {}),
        cleanup_wall_seconds=cleanup_wall_seconds,
        stable_pids=set(stable_pids),
    )
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
