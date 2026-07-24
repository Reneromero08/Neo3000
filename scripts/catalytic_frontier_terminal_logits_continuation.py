#!/usr/bin/env python3
"""neo-exp-0084: CUDA root plus host terminal-logits continuation at T=64.

The primary promotes the accepted 689-token CUDA KV/recurrent root by evaluating
only token 690 once, captures the resulting full-vocabulary F32 logits row, and
then restores that 690-token executable boundary for zero-fresh-prompt live
sampling.  The matched control restores the unchanged 689-token CUDA root and
evaluates token 690 normally. Relative to accepted 0083, this exact successor
changes only counted temporal reuse from 16 to 64. No answer text or sampled
token is stored.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import baseline_harness
import catalytic_frontier_fanout as shared_tasks
import catalytic_frontier_harness as harness
import catalytic_frontier_single_request_latency as latency
import catalytic_frontier_water_panel_qualifier as water


EXPERIMENT_ID = "neo-exp-0084"
ATTEMPT_ID = "frontier-attempt-0117"
ROOT_ID = water.ROOT_ID
BASE_ROOT_ID = "neo-exp-0084-base-689"
TERMINAL_ROOT_ID = "neo-exp-0084-terminal-690"
BRANCH_NUMBER = 7
EXPECTED_ANSWER = "C"
EXPECTED_TASK_A_TOKENS = 543
EXPECTED_RETAINED_TOKENS = 612
EXPECTED_BASE_TOKENS = 689
EXPECTED_TERMINAL_TOKENS = 690
COUNTED_PAIRS = 64
PAIR_ORDERS = tuple(
    ("primary", "control") if index % 2 == 0 else ("control", "primary")
    for index in range(COUNTED_PAIRS)
)
WARMUP_ORDER = ("primary", "control")
MIN_PROMPT_SPEEDUP = 1.50
MIN_TTFT_SPEEDUP = 1.08
MIN_WALL_SPEEDUP = 1.05
MIN_PAIR_DOMINANCE = 0.70
MAX_GENERATION_REGRESSION = 0.05
MAX_WDDM_BYTES = 6000 * 1024 * 1024
BRANCH_PANEL_SHA256 = "47DD356BA39422EF58019CE60B84A69FCAEC455FE11B758103935CE65DE33841"

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BINARY = ROOT / "build" / "candidate" / "bin" / "Release" / "llama-server.exe"
DEFAULT_MODEL = harness.DEFAULT_MODEL
DEFAULT_OUTPUT = ROOT / "lab" / f"{EXPERIMENT_ID}.local.json"
DEFAULT_LOG = ROOT / "lab" / f"{EXPERIMENT_ID}.server.local.log"
DEFAULT_MARKER = ROOT / "lab" / f"{EXPERIMENT_ID}.consumed.local.json"

# Final no-op Release build, pinned before live execution.
RUNTIME_SHA256: dict[str, str] = {
    "ggml-base.dll": "F648098AB0FCECA45A1EEC2AE147022383DCC6CD31392199F5CD6E5A5277AF3F",
    "ggml-cpu.dll": "64B9D97113CC0AB57C8DA0E3237B4EFC0271B4E0AA377080295D138BCABC92A1",
    "ggml-cuda.dll": "4997B33C4DE7EC63830C9C1F7BB5B4B0E394B29DBC795022048DF78046FCC3A2",
    "ggml.dll": "6E6A8BE1DAFA42356C15DDA9C0A39CC7BA34E4ABA8D402693F0EFCB57CD9E2D1",
    "llama-common.dll": "073D24688A09741B94238270E7ACDFB86D372B8757BEEA98132CF96BF36EC5A8",
    "llama-server-impl.dll": "B4DE9F2562FE81714F9CFCD03B0B4EEE4D75A1010BDC96F72AF7136F4712D958",
    "llama-server.exe": "BBD79BE6B1E1A708209B217049AE4F01AD2A89FB0159C0FF75228E1EC16BF00D",
    "llama.dll": "E22AD97978A6E88F4D4D1D0E26DD43216BE8F05EB6C39F5D96199B286A56F08B",
    "mtmd.dll": "61B837FC6C8160602EFE3E6831CB9794F51E7BF64BFD06762F8406629D0291A2",
}


class ExperimentError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ExperimentError(message)


def canonical_sha256(value: Any) -> str:
    return harness.sha256_bytes(harness.carrier.canonical_json_bytes(value))


def percentile(values: Sequence[float], quantile: float) -> float:
    require(bool(values), "empty percentile input")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def distribution(values: Sequence[float]) -> dict[str, float]:
    require(bool(values), "empty distribution")
    return {
        "minimum": min(values),
        "median": statistics.median(values),
        "p95": percentile(values, 0.95),
        "maximum": max(values),
    }


def runtime_bundle(binary: Path) -> dict[str, str]:
    require(binary.name == "llama-server.exe", "runtime entrypoint changed")
    require(bool(RUNTIME_SHA256), "0084 runtime bundle is not pinned")
    observed: dict[str, str] = {}
    for name, expected in RUNTIME_SHA256.items():
        path = (binary.parent / name).resolve(strict=True)
        require(path.parent == binary.parent, f"runtime path escaped for {name}")
        digest = harness.live_runtime.sha256_file(path)
        require(digest == expected, f"runtime identity drifted for {name}: {digest}")
        observed[name] = digest
    return observed


def current_head(repository: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        text=True,
    ).strip()


def require_clean_head(repository: Path, expected_commit: str) -> None:
    require(
        bool(re.fullmatch(r"[0-9a-f]{40}", expected_commit)),
        "expected commit is malformed",
    )
    require(current_head(repository) == expected_commit, "0084 commit identity changed")
    status = subprocess.check_output(
        ["git", "status", "--porcelain"],
        cwd=repository,
        text=True,
    )
    require(not status.strip(), "0084 worktree is not clean")


def write_exclusive_json(path: Path, value: Mapping[str, Any]) -> dict[str, Any]:
    encoded = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ExperimentError(f"artifact already exists: {path}") from exc
    return {
        "path": str(path),
        "bytes": len(encoded),
        "sha256": harness.sha256_bytes(encoded),
    }


def create_consumed_marker(path: Path, expected_commit: str) -> dict[str, Any]:
    marker = {
        "id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "expected_commit": expected_commit,
        "created_unix_ns": time.time_ns(),
        "meaning": "Task-A is next; neo-exp-0084 is scientifically consumed",
        "retry_allowed": False,
    }
    return write_exclusive_json(path, marker)


def validate_root(
    response: Mapping[str, Any],
    *,
    action: str,
    root_id: str,
    n_tokens: int,
    expected: Mapping[str, Any] | None = None,
    terminal: bool,
) -> dict[str, Any]:
    require(response.get("action") == action, f"{root_id} action changed")
    require(response.get("root_id") == root_id, f"{root_id} identity changed")
    require(response.get("n_tokens") == n_tokens, f"{root_id} token count changed")
    require(response.get("n_checkpoints") == 0, f"{root_id} gained checkpoints")
    for key in (
        "n_bytes",
        "n_host_bytes",
        "n_device_bytes",
        "n_device_bytes_after",
        "n_gpu_bytes",
        "n_gpu_bytes_after",
        "n_roots_after",
        "n_total_bytes_after",
        "n_total_device_bytes_after",
        "n_total_gpu_bytes_after",
    ):
        require(type(response.get(key)) is int and int(response[key]) >= 0, f"{root_id} {key} is invalid")
    require(
        int(response["n_bytes"]) ==
        int(response["n_host_bytes"]) + int(response["n_device_bytes"]),
        f"{root_id} byte accounting changed",
    )
    require(int(response["n_device_bytes"]) > 0, f"{root_id} has no device state")
    require(int(response["n_gpu_bytes"]) > 0, f"{root_id} has no GPU state")
    expected_after = 0 if action == "root-erase" else int(response["n_device_bytes"])
    expected_gpu_after = 0 if action == "root-erase" else int(response["n_gpu_bytes"])
    require(response["n_device_bytes_after"] == expected_after, f"{root_id} device closure changed")
    require(response["n_gpu_bytes_after"] == expected_gpu_after, f"{root_id} GPU closure changed")
    require(response.get("has_terminal_logits") is terminal, f"{root_id} terminal presence changed")

    if terminal:
        require(
            type(response.get("n_terminal_logits")) is int
            and int(response["n_terminal_logits"]) > 0,
            f"{root_id} terminal vocabulary is absent",
        )
        require(
            response.get("n_terminal_logits_bytes") ==
            int(response["n_terminal_logits"]) * 4,
            f"{root_id} terminal F32 byte geometry changed",
        )
        for key in (
            "terminal_logits_fnv64",
            "terminal_prompt_fnv64",
            "terminal_sampler_fnv64",
        ):
            require(
                isinstance(response.get(key), str)
                and bool(re.fullmatch(r"[0-9a-f]{16}", str(response[key]))),
                f"{root_id} {key} is invalid",
            )
        require(
            response.get("terminal_position") == EXPECTED_TERMINAL_TOKENS - 1,
            f"{root_id} terminal position changed",
        )
    else:
        require(response.get("n_terminal_logits") == 0, f"{root_id} unexpectedly stores logits")
        require(response.get("n_terminal_logits_bytes") == 0, f"{root_id} terminal bytes are nonzero")

    if expected is not None:
        for key in (
            "root_id",
            "n_tokens",
            "n_bytes",
            "n_host_bytes",
            "n_device_bytes",
            "n_gpu_bytes",
            "n_checkpoints",
            "has_terminal_logits",
            "n_terminal_logits",
            "n_terminal_logits_bytes",
            "terminal_logits_fnv64",
            "terminal_prompt_fnv64",
            "terminal_sampler_fnv64",
            "terminal_position",
        ):
            require(response.get(key) == expected.get(key), f"{root_id} {key} drifted")
    timings = response.get("timings")
    require(
        isinstance(timings, Mapping)
        and isinstance(timings.get("root_ms"), (int, float)),
        f"{root_id} timing is absent",
    )
    return dict(response)


def expect_http_error(url: str, payload: Mapping[str, Any], expected_text: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=harness.carrier.canonical_json_bytes(payload),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8", errors="replace")
            raise ExperimentError(f"negative control unexpectedly returned {response.status}: {body}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        require(exc.code == 400, f"negative control status changed: {exc.code}")
        require(expected_text in body, f"negative control error changed: {body}")
        return {
            "http_status": exc.code,
            "body_sha256": harness.sha256_bytes(body.encode("utf-8")),
            "expected_text": expected_text,
        }


def prepare_task_and_branch(codec: Any, root: Mapping[str, Any]) -> dict[str, Any]:
    panel = water.panel_for(root)
    require(water.base._panel_hash(panel) == BRANCH_PANEL_SHA256, "water panel changed")
    spec = panel[BRANCH_NUMBER - 1]
    require(spec["answer"] == EXPECTED_ANSWER, "water branch answer changed")
    prompt_text = codec.render_messages(
        harness.carrier.task_a_messages(root),
        harness.carrier.CHAT_TEMPLATE_KWARGS,
    )
    prompt_tokens = codec.tokenize(prompt_text)
    require(len(prompt_tokens) == EXPECTED_TASK_A_TOKENS, "Task-A prompt count changed")
    payload = harness.carrier._task_a_payload(
        prompt_tokens,
        seed=shared_tasks.derive_seed(ROOT_ID, "task-a"),
    )
    return {"spec": spec, "prompt_tokens": prompt_tokens, "payload": payload}


def task_and_branch(
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    prepared: Mapping[str, Any],
) -> tuple[dict[str, Any], list[int], Mapping[str, Any]]:
    task = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:task-a",
        prepared["payload"],
    )
    parsed = harness.carrier.parse_task_a_output(task["content"])
    require(parsed["answer"] == harness.EXPECTED[ROOT_ID]["task_a"], "Task-A answer is wrong")
    retained = harness.carrier.derive_retained_root(
        harness.root_capture(task, prepared["payload"]),
        prepared["prompt_tokens"],
        codec,
        props,
    )
    require(
        retained["retained_root_token_count"] == EXPECTED_RETAINED_TOKENS,
        "retained root count changed",
    )
    branch_tokens, _ = latency.branch_request(
        codec,
        retained,
        prepared["spec"],
        cache_prompt=False,
    )
    require(len(branch_tokens) == EXPECTED_TERMINAL_TOKENS, "branch prompt count changed")
    return task, branch_tokens, retained


def completion_payload(
    tokens: Sequence[int],
    *,
    cache_prompt: bool,
    n_predict: int | None = None,
) -> dict[str, Any]:
    payload = harness.carrier._branch_payload(
        list(tokens),
        seed=shared_tasks.derive_seed(ROOT_ID, f"branch-{BRANCH_NUMBER}"),
        cache_prompt=cache_prompt,
        **({"n_predict": n_predict} if n_predict is not None else {}),
    )
    # The carrier helper omits grammar for zero-output requests, but terminal
    # capture and live reuse must bind the exact same normalized sampler
    # contract. Keep grammar explicit even when n_predict == 0.
    payload.setdefault("grammar", harness.carrier.branch_grammar())
    payload["backend_sampling"] = False
    return payload


def root_action(
    *,
    action: str,
    root_id: str,
    storage: str = "default",
    include_terminal_logits: bool = False,
    require_terminal_logits: bool = False,
) -> tuple[dict[str, Any], float]:
    return harness.ram_root_action(
        action=action,
        root_id=root_id,
        storage=storage,
        include_terminal_logits=include_terminal_logits,
        require_terminal_logits=require_terminal_logits,
    )


def run_route(
    *,
    sidecar: Any,
    route: str,
    label: str,
    tokens: Sequence[int],
    terminal_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    require(route in {"primary", "control", "direct"}, "route changed")
    if route == "primary":
        restore_raw, restore_wall = root_action(
            action="root-restore",
            root_id=TERMINAL_ROOT_ID,
            require_terminal_logits=True,
        )
        restore = validate_root(
            restore_raw,
            action="root-restore",
            root_id=TERMINAL_ROOT_ID,
            n_tokens=EXPECTED_TERMINAL_TOKENS,
            expected=terminal_receipt,
            terminal=True,
        )
        payload = completion_payload(tokens, cache_prompt=True)
        payload.update(
            neo3000_use_terminal_logits=True,
            neo3000_terminal_root_id=TERMINAL_ROOT_ID,
            neo3000_terminal_logits_fnv64=terminal_receipt["terminal_logits_fnv64"],
        )
    elif route == "control":
        restore_raw, restore_wall = root_action(
            action="root-restore",
            root_id=BASE_ROOT_ID,
        )
        restore = validate_root(
            restore_raw,
            action="root-restore",
            root_id=BASE_ROOT_ID,
            n_tokens=EXPECTED_BASE_TOKENS,
            terminal=False,
        )
        payload = completion_payload(tokens, cache_prompt=True)
    else:
        restore_wall = 0.0
        restore = None
        payload = completion_payload(tokens, cache_prompt=False)

    recorder = latency.TimingRecorder()
    record = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:{label}:{route}",
        payload,
        recorder=recorder,
        batch_owned_request=route != "direct",
    )
    timing = recorder.summary(request_wall_seconds=float(record["wall_seconds"]))
    expected_cached = (
        EXPECTED_TERMINAL_TOKENS if route == "primary"
        else EXPECTED_BASE_TOKENS if route == "control"
        else 0
    )
    require(record["cached_prompt_tokens"] == expected_cached, f"{route} cached split changed")
    require(
        record["fresh_prompt_tokens"] == EXPECTED_TERMINAL_TOKENS - expected_cached,
        f"{route} fresh split changed",
    )
    require(timing["server_prompt_n"] == record["fresh_prompt_tokens"], f"{route} prompt timing changed")
    answer = harness.carrier.parse_branch_output(record["content"])
    generated = record["execution"]["generated_token_ids"]
    require(isinstance(generated, list) and generated, f"{route} token array is absent")
    record.update(
        route=route,
        answer=answer,
        correct=answer == EXPECTED_ANSWER,
        input_token_sha256=canonical_sha256(list(tokens)),
        generated_token_sha256=canonical_sha256(generated),
        timing=timing,
        restore=restore,
        restore_client_wall_seconds=restore_wall,
        effective_wall_seconds=float(record["wall_seconds"]) + restore_wall,
    )
    return record


def run_tool_canary(sidecar: Any) -> dict[str, Any]:
    payload = baseline_harness.build_request_payload(
        "agents-a1-holostate",
        "",
        0.0,
        64,
        False,
        True,
        True,
    )
    measurement = sidecar.guarded(
        f"{EXPERIMENT_ID}:pi-tool-canary",
        lambda: baseline_harness.stream_completion(
            f"http://127.0.0.1:{harness.live_runtime.PORT}/v1/chat/completions",
            payload,
            repeat=1,
            timeout=1_000,
            request_label=f"{EXPERIMENT_ID}:pi-tool-canary",
        ),
        timeout=1_000,
    )
    validation = baseline_harness.validate_tool_call(measurement)
    require(validation.get("passed") is True, "Pi tool-call canary failed")
    require(len(measurement.tool_calls) == 1 and not measurement.content, "Pi tool-call shape changed")
    return {
        "validation": validation,
        "tool_calls_sha256": canonical_sha256(measurement.tool_calls),
        "generated_token_sha256": measurement.generated_token_sha256,
        "measurement": asdict(measurement),
    }


def apply_ownership_amortization(
    *,
    warmup: Sequence[dict[str, Any]],
    counted: Sequence[dict[str, Any]],
    pairs: Sequence[dict[str, Any]],
    ownership_total: float,
) -> float:
    request_count = len(warmup) + len(counted)
    require(request_count > 0, "batch-owned request count is zero")
    ownership_amortized = ownership_total / request_count
    for record in [*warmup, *counted]:
        record["batch_ownership_amortized_seconds"] = ownership_amortized
        record["effective_wall_seconds"] += ownership_amortized

    for pair_record in pairs:
        pair_number = int(pair_record["pair"])
        records = [
            record
            for record in counted
            if record["label"].startswith(
                f"{EXPERIMENT_ID}:pair-{pair_number}-"
            )
        ]
        by_route = {record["route"]: record for record in records}
        require(
            set(by_route) == {"primary", "control"},
            f"pair {pair_number} route evidence is incomplete",
        )
        pair_record["primary_effective_wall_seconds"] = (
            by_route["primary"]["effective_wall_seconds"]
        )
        pair_record["control_effective_wall_seconds"] = (
            by_route["control"]["effective_wall_seconds"]
        )
        pair_record["primary_won"] = (
            by_route["primary"]["effective_wall_seconds"]
            < by_route["control"]["effective_wall_seconds"]
        )
    return ownership_amortized


def evaluate(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    root: Mapping[str, Any],
    prepared: Mapping[str, Any],
    baseline_private: int | None,
) -> dict[str, Any]:
    task, branch_tokens, retained = task_and_branch(sidecar, codec, props, prepared)

    base_tokens = branch_tokens[:-1]
    require(len(base_tokens) == EXPECTED_BASE_TOKENS, "base token count changed")
    base_materialization = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:base-689-materialize",
        completion_payload(base_tokens, cache_prompt=False, n_predict=0),
        operation_kind="zero-output-root-readdress",
    )
    require(
        base_materialization["cached_prompt_tokens"] == 0
        and base_materialization["fresh_prompt_tokens"] == EXPECTED_BASE_TOKENS
        and base_materialization["completion_tokens"] == 0,
        "base materialization changed",
    )
    base_save_raw, base_save_wall = root_action(
        action="root-save",
        root_id=BASE_ROOT_ID,
        storage="device",
    )
    base_saved = validate_root(
        base_save_raw,
        action="root-save",
        root_id=BASE_ROOT_ID,
        n_tokens=EXPECTED_BASE_TOKENS,
        terminal=False,
    )

    base_restore_raw, base_restore_wall = root_action(
        action="root-restore",
        root_id=BASE_ROOT_ID,
    )
    validate_root(
        base_restore_raw,
        action="root-restore",
        root_id=BASE_ROOT_ID,
        n_tokens=EXPECTED_BASE_TOKENS,
        expected=base_saved,
        terminal=False,
    )
    promotion_payload = completion_payload(
        branch_tokens,
        cache_prompt=True,
        n_predict=0,
    )
    promotion_payload["neo3000_capture_terminal_logits"] = True
    promotion = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:promote-689-to-690-and-capture",
        promotion_payload,
        operation_kind="zero-output-root-readdress",
    )
    require(
        promotion["cached_prompt_tokens"] == EXPECTED_BASE_TOKENS
        and promotion["fresh_prompt_tokens"] == 1
        and promotion["completion_tokens"] == 0,
        "terminal promotion geometry changed",
    )
    terminal_save_raw, terminal_save_wall = root_action(
        action="root-save",
        root_id=TERMINAL_ROOT_ID,
        storage="device",
        include_terminal_logits=True,
    )
    terminal_saved = validate_root(
        terminal_save_raw,
        action="root-save",
        root_id=TERMINAL_ROOT_ID,
        n_tokens=EXPECTED_TERMINAL_TOKENS,
        terminal=True,
    )

    missing_negative = sidecar.guarded(
        f"{EXPERIMENT_ID}:missing-terminal-negative",
        lambda: expect_http_error(
            f"http://127.0.0.1:{harness.live_runtime.PORT}/slots/0?action=root-restore",
            {"root_id": BASE_ROOT_ID, "require_terminal_logits": True},
            "RAM root has no exact terminal-logits boundary",
        ),
        timeout=60,
    )
    terminal_restore_raw, _ = root_action(
        action="root-restore",
        root_id=TERMINAL_ROOT_ID,
        require_terminal_logits=True,
    )
    validate_root(
        terminal_restore_raw,
        action="root-restore",
        root_id=TERMINAL_ROOT_ID,
        n_tokens=EXPECTED_TERMINAL_TOKENS,
        expected=terminal_saved,
        terminal=True,
    )
    wrong_payload = completion_payload(branch_tokens, cache_prompt=True)
    wrong_payload.update(
        stream=False,
        neo3000_use_terminal_logits=True,
        neo3000_terminal_root_id=TERMINAL_ROOT_ID,
        neo3000_terminal_logits_fnv64="0" * 16,
    )
    mismatch_negative = sidecar.guarded(
        f"{EXPERIMENT_ID}:mismatched-terminal-negative",
        lambda: expect_http_error(
            f"http://127.0.0.1:{harness.live_runtime.PORT}/completion",
            wrong_payload,
            "Terminal-logits continuation identity mismatch",
        ),
        timeout=60,
    )

    direct_pre = run_route(
        sidecar=sidecar,
        route="direct",
        label="direct-pre",
        tokens=branch_tokens,
        terminal_receipt=terminal_saved,
    )

    ownership: list[dict[str, Any]] = []
    for boundary in ("pre-t64-batch",):
        started = time.monotonic()
        evidence = sidecar.exact_ownership(boundary)
        ownership.append(
            {
                "boundary": boundary,
                "client_wall_seconds": time.monotonic() - started,
                "evidence": evidence,
            }
        )

    warmup = [
        run_route(
            sidecar=sidecar,
            route=route,
            label=f"warmup-{index}",
            tokens=branch_tokens,
            terminal_receipt=terminal_saved,
        )
        for index, route in enumerate(WARMUP_ORDER, start=1)
    ]
    counted: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    for pair, order in enumerate(PAIR_ORDERS, start=1):
        records = [
            run_route(
                sidecar=sidecar,
                route=route,
                label=f"pair-{pair}-route-{index}",
                tokens=branch_tokens,
                terminal_receipt=terminal_saved,
            )
            for index, route in enumerate(order, start=1)
        ]
        counted.extend(records)
        by_route = {record["route"]: record for record in records}
        pairs.append(
            {
                "pair": pair,
                "order": list(order),
                "primary_effective_wall_seconds": by_route["primary"]["effective_wall_seconds"],
                "control_effective_wall_seconds": by_route["control"]["effective_wall_seconds"],
                "primary_won": (
                    by_route["primary"]["effective_wall_seconds"]
                    < by_route["control"]["effective_wall_seconds"]
                ),
            }
        )

    started = time.monotonic()
    post_evidence = sidecar.exact_ownership("post-t64-batch")
    ownership.append(
        {
            "boundary": "post-t64-batch",
            "client_wall_seconds": time.monotonic() - started,
            "evidence": post_evidence,
        }
    )
    ownership_total = sum(float(item["client_wall_seconds"]) for item in ownership)
    ownership_amortized = apply_ownership_amortization(
        warmup=warmup,
        counted=counted,
        pairs=pairs,
        ownership_total=ownership_total,
    )

    direct_post = run_route(
        sidecar=sidecar,
        route="direct",
        label="direct-post",
        tokens=branch_tokens,
        terminal_receipt=terminal_saved,
    )
    tool_canary = run_tool_canary(sidecar)
    resources_with_roots = harness.process_resources(sidecar, baseline_private)

    terminal_erase_raw, terminal_erase_wall = root_action(
        action="root-erase",
        root_id=TERMINAL_ROOT_ID,
    )
    terminal_erased = validate_root(
        terminal_erase_raw,
        action="root-erase",
        root_id=TERMINAL_ROOT_ID,
        n_tokens=EXPECTED_TERMINAL_TOKENS,
        expected=terminal_saved,
        terminal=True,
    )
    base_erase_raw, base_erase_wall = root_action(
        action="root-erase",
        root_id=BASE_ROOT_ID,
    )
    base_erased = validate_root(
        base_erase_raw,
        action="root-erase",
        root_id=BASE_ROOT_ID,
        n_tokens=EXPECTED_BASE_TOKENS,
        expected=base_saved,
        terminal=False,
    )
    require(
        base_erased["n_roots_after"] == 0
        and base_erased["n_total_bytes_after"] == 0
        and base_erased["n_total_device_bytes_after"] == 0
        and base_erased["n_total_gpu_bytes_after"] == 0,
        "root bank did not close to zero",
    )
    resources_after_erase = harness.process_resources(sidecar, baseline_private)

    primary = [record for record in counted if record["route"] == "primary"]
    control = [record for record in counted if record["route"] == "control"]
    require(len(primary) == COUNTED_PAIRS and len(control) == COUNTED_PAIRS, "T64 cardinality changed")
    all_generation = [direct_pre, *warmup, *counted, direct_post]
    generated_hashes = {record["generated_token_sha256"] for record in all_generation}
    input_hashes = {record["input_token_sha256"] for record in all_generation}
    utility_exact = (
        len(generated_hashes) == 1
        and len(input_hashes) == 1
        and all(record["correct"] for record in all_generation)
    )

    primary_prompt = [float(record["timing"]["prompt_ms"]) for record in primary]
    control_prompt = [float(record["timing"]["prompt_ms"]) for record in control]
    primary_ttft = [
        float(record["timing"]["ttft_seconds"])
        + float(record["restore_client_wall_seconds"])
        + ownership_amortized
        for record in primary
    ]
    control_ttft = [
        float(record["timing"]["ttft_seconds"])
        + float(record["restore_client_wall_seconds"])
        + ownership_amortized
        for record in control
    ]
    primary_wall = [float(record["effective_wall_seconds"]) for record in primary]
    control_wall = [float(record["effective_wall_seconds"]) for record in control]
    primary_generation = [float(record["timing"]["predicted_ms"]) for record in primary]
    control_generation = [float(record["timing"]["predicted_ms"]) for record in control]
    prompt_speedup = statistics.median(control_prompt) / statistics.median(primary_prompt)
    ttft_speedup = statistics.median(control_ttft) / statistics.median(primary_ttft)
    wall_speedup = statistics.median(control_wall) / statistics.median(primary_wall)
    dominance = sum(bool(pair["primary_won"]) for pair in pairs) / len(pairs)
    generation_regression = (
        statistics.median(primary_generation) /
        statistics.median(control_generation) - 1.0
    )

    primary_lifecycle_wall = (
        base_restore_wall
        + float(promotion["wall_seconds"])
        + terminal_save_wall
        + sum(float(record["effective_wall_seconds"]) for record in primary)
        + terminal_erase_wall
        + base_erase_wall
    )
    control_lifecycle_wall = (
        sum(float(record["effective_wall_seconds"]) for record in control)
        + base_erase_wall
    )
    primary_lifecycle_fresh = (
        int(promotion["fresh_model_tokens"])
        + sum(int(record["fresh_model_tokens"]) for record in primary)
    )
    control_lifecycle_fresh = sum(int(record["fresh_model_tokens"]) for record in control)

    log_path = Path(str(sidecar.readiness["log_path"]))
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    capture_markers = log_text.count("neo3000 terminal-logits boundary captured")
    sample_markers = log_text.count("neo3000 terminal-logits continuation sampled before decode")
    full_reprocess_markers = log_text.count("forcing full prompt re-processing")
    expected_primary_uses = 1 + COUNTED_PAIRS

    gates = {
        "task_a_correct": harness.carrier.parse_task_a_output(task["content"])["answer"] == harness.EXPECTED[ROOT_ID]["task_a"],
        "utility_and_generated_tokens_exact": utility_exact,
        "primary_690_cached_0_fresh": all(
            record["cached_prompt_tokens"] == 690 and record["fresh_prompt_tokens"] == 0
            for record in [warmup[0], *primary]
        ),
        "control_689_cached_1_fresh": all(
            record["cached_prompt_tokens"] == 689 and record["fresh_prompt_tokens"] == 1
            for record in [warmup[1], *control]
        ),
        "capture_marker_exactly_one": capture_markers == 1,
        "predecode_sample_marker_count_exact": sample_markers == expected_primary_uses,
        "zero_full_reprocess_markers": full_reprocess_markers == 0,
        "missing_terminal_rejected_pre_model": missing_negative["http_status"] == 400,
        "mismatched_terminal_rejected_pre_model": mismatch_negative["http_status"] == 400,
        "terminal_f32_geometry_exact": terminal_saved["n_terminal_logits_bytes"] == terminal_saved["n_terminal_logits"] * 4,
        "terminal_root_digest_invariant": all(
            record["restore"]["terminal_logits_fnv64"] == terminal_saved["terminal_logits_fnv64"]
            for record in [warmup[0], *primary]
        ),
        "prompt_speedup_at_least_1_50": prompt_speedup >= MIN_PROMPT_SPEEDUP,
        "ttft_speedup_at_least_1_08": ttft_speedup >= MIN_TTFT_SPEEDUP,
        "wall_speedup_at_least_1_05": wall_speedup >= MIN_WALL_SPEEDUP,
        "pair_dominance_at_least_0_70": dominance >= MIN_PAIR_DOMINANCE,
        "generation_regression_at_most_5_percent": generation_regression <= MAX_GENERATION_REGRESSION,
        "t64_lifecycle_wall_advantage": primary_lifecycle_wall < control_lifecycle_wall,
        "t64_lifecycle_fresh_advantage": primary_lifecycle_fresh < control_lifecycle_fresh,
        "root_bank_closed_to_zero": base_erased["n_total_bytes_after"] == 0,
        "wddm_at_or_below_6000_mib": (
            type(resources_with_roots.get("peak_wddm_bytes")) is int
            and int(resources_with_roots["peak_wddm_bytes"]) <= MAX_WDDM_BYTES
        ),
        "batch_ownership_boundaries_exact": (
            len(ownership) == 2
            and all(item["evidence"].get("passed") is True for item in ownership)
        ),
        "pi_tool_call_valid": tool_canary["validation"].get("passed") is True,
        "automatic_promotion": False,
        "unbounded_catalytic_inference_established": False,
    }
    accepted = all(value is True for key, value in gates.items() if key not in {
        "automatic_promotion",
        "unbounded_catalytic_inference_established",
    })

    return {
        "id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "complete",
        "verdict": "accept" if accepted else "reject",
        "classification": (
            "cuda-root-plus-host-terminal-logits-continuation-t64-supported-bounded"
            if accepted
            else "terminal-logits-continuation-without-preregistered-speed-or-integrity-gate"
        ),
        "hypothesis": (
            "An exact 690-token CUDA KV/recurrent root plus its host F32 terminal-logits row "
            "can sample live with zero fresh prompt tokens and beat the identical 689/1 route."
        ),
        "trial_design": {
            "axis": "T",
            "T": COUNTED_PAIRS,
            "warmup_order": list(WARMUP_ORDER),
            "pair_orders": [list(order) for order in PAIR_ORDERS],
            "primary": "690-token CUDA KV/recurrent root plus host F32 terminal logits",
            "control": "689-token CUDA KV/recurrent root plus one live prompt token",
            "base_promotion_geometry": "restore qualified 689 root then evaluate only token 690",
            "fanout": False,
        },
        "identities": {
            "task_a_prompt_sha256": canonical_sha256(prepared["prompt_tokens"]),
            "branch_prompt_sha256": canonical_sha256(branch_tokens),
            "generated_token_sha256": next(iter(generated_hashes)),
            "terminal_logits_fnv64": terminal_saved["terminal_logits_fnv64"],
            "terminal_prompt_fnv64": terminal_saved["terminal_prompt_fnv64"],
            "terminal_sampler_fnv64": terminal_saved["terminal_sampler_fnv64"],
        },
        "setup": {
            "task_a": harness.token_summary(task),
            "base_materialization": harness.token_summary(base_materialization),
            "base_save": base_saved,
            "base_save_client_wall_seconds": base_save_wall,
            "base_restore_client_wall_seconds": base_restore_wall,
            "promotion": harness.token_summary(promotion),
            "terminal_save": terminal_saved,
            "terminal_save_client_wall_seconds": terminal_save_wall,
        },
        "negative_controls": {
            "missing_terminal": missing_negative,
            "mismatched_digest": mismatch_negative,
        },
        "direct_drift_checks": [direct_pre, direct_post],
        "warmup": warmup,
        "counted_pairs": pairs,
        "counted_records": counted,
        "metrics": {
            "primary_prompt_ms": distribution(primary_prompt),
            "control_prompt_ms": distribution(control_prompt),
            "primary_ttft_seconds": distribution(primary_ttft),
            "control_ttft_seconds": distribution(control_ttft),
            "primary_effective_wall_seconds": distribution(primary_wall),
            "control_effective_wall_seconds": distribution(control_wall),
            "primary_generation_ms": distribution(primary_generation),
            "control_generation_ms": distribution(control_generation),
            "prompt_speedup": prompt_speedup,
            "ttft_speedup": ttft_speedup,
            "wall_speedup": wall_speedup,
            "pair_dominance": dominance,
            "generation_regression_fraction": generation_regression,
            "counted_lifecycle": {
                "primary_wall_seconds": primary_lifecycle_wall,
                "control_wall_seconds": control_lifecycle_wall,
                "wall_speedup": control_lifecycle_wall / primary_lifecycle_wall,
                "primary_fresh_model_tokens": primary_lifecycle_fresh,
                "control_fresh_model_tokens": control_lifecycle_fresh,
            },
        },
        "runtime_markers": {
            "capture_count": capture_markers,
            "predecode_sample_count": sample_markers,
            "full_reprocess_count": full_reprocess_markers,
        },
        "root_closure": {
            "terminal_erase": terminal_erased,
            "base_erase": base_erased,
        },
        "resources": {
            "with_roots": resources_with_roots,
            "after_erase": resources_after_erase,
        },
        "batch_ownership": {
            "boundaries": ownership,
            "total_seconds": ownership_total,
            "amortized_seconds_per_timed_request": ownership_amortized,
        },
        "tool_canary": tool_canary,
        "quality_gates": gates,
        "claim_ceiling": (
            "One process-local Agents-A1 CUDA KV/recurrent root plus host-F32 terminal-logits "
            "continuation through T=64; no canonical .holo, restart persistence, general "
            "recurrence, weight catalysis, or unbounded-compute claim."
        ),
        "automatic_promotion": False,
        "research_goal_blocked": False,
        "next_boundary": (
            "IF_ACCEPTED_SCALE_USEFUL_TERMINAL_CONTINUATION_OR_COMPOSE_WITH_OUTPUT_BEARING_REBASE; "
            "IF_REJECTED_RETIRE_TERMINAL_LOGITS_AND_SELECT_A_LARGER_GENERATION_STATE_BOUNDARY"
        ),
    }


def static_audit(binary: Path) -> dict[str, Any]:
    sources = {
        "server_context": ROOT / "tools" / "server" / "server-context.cpp",
        "server_task": ROOT / "tools" / "server" / "server-task.h",
        "server_schema": ROOT / "tools" / "server" / "server-schema.cpp",
        "sampling_header": ROOT / "common" / "sampling.h",
        "sampling_source": ROOT / "common" / "sampling.cpp",
        "harness": ROOT / "scripts" / "catalytic_frontier_harness.py",
        "controller": Path(__file__).resolve(),
    }
    text = {name: path.read_text(encoding="utf-8") for name, path in sources.items()}
    boundary = text["server_context"].split(
        "struct server_terminal_logits_boundary {", 1
    )[1].split("};", 1)[0]
    checks = {
        "external_logits_sampler_present": "common_sampler_sample_from_logits" in text["sampling_source"],
        "capture_before_zero_output_release": "neo3000 terminal-logits boundary captured" in text["server_context"],
        "predecode_fast_path_present": "sampled before decode" in text["server_context"],
        "root_host_accounting_includes_terminal": "terminal_logits.size()" in text["server_context"],
        "missing_and_mismatch_controls_present": (
            "missing-terminal-negative" in text["controller"]
            and "mismatched-terminal-negative" in text["controller"]
        ),
        "answer_or_sample_not_stored_in_boundary": (
            "llama_token" not in boundary
            and "answer" not in boundary
        ),
        "bounded_claim_text_present": "host-F32 terminal-logits" in text["controller"],
    }
    require(all(checks.values()), f"static 0084 audit failed: {checks}")
    return {
        "checks": checks,
        "source_sha256": {
            name: harness.live_runtime.sha256_file(path)
            for name, path in sources.items()
        },
        "runtime_sha256": runtime_bundle(binary),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--static-only", action="store_true")
    mode.add_argument("--execute-once", action="store_true")
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--expected-commit")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--server-log-output", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--consumed-marker", type=Path, default=DEFAULT_MARKER)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    binary = args.binary.resolve(strict=True)
    if args.static_only:
        print(json.dumps(static_audit(binary), indent=2, sort_keys=True))
        return 0

    require(args.expected_commit is not None, "--expected-commit is required")
    output = args.output.resolve(strict=False)
    log_output = args.server_log_output.resolve(strict=False)
    marker = args.consumed_marker.resolve(strict=False)
    for path in (output, log_output, marker):
        require(not path.exists(), f"0084 artifact already exists: {path}")
    require(len({output, log_output, marker}) == 3, "0084 artifact paths collide")
    require_clean_head(ROOT, args.expected_commit)
    before_bundle = runtime_bundle(binary)
    static = static_audit(binary)

    corpus = harness.carrier.load_public_corpus(ROOT)
    roots = {str(item["root_id"]): item for item in corpus["roots"]}
    evaluator, live_contract = harness.load_discovery_sidecar_contract()
    stable_pids = harness.live_runtime.require_stable()
    require(len(stable_pids) == 1, "0084 requires one protected stable listener")
    require(not harness.live_runtime.listener_pids(harness.live_runtime.PORT), "candidate port is occupied")

    state_root = Path(tempfile.mkdtemp(prefix="neo3000-terminal-logits-"))
    sidecar: Any | None = None
    result: dict[str, Any] | None = None
    cleanup: dict[str, Any] = {}
    caught: BaseException | None = None
    marker_receipt: dict[str, Any] | None = None
    os.environ["LLAMA_ARG_LOG_VERBOSITY"] = "1000"
    os.environ["LLAMA_SERVER_SLOTS_DEBUG"] = "1"
    try:
        sidecar = water.build_sidecar(
            binary=binary,
            model=args.model.resolve(strict=True),
            evaluator=evaluator,
            live_contract=live_contract,
            stable_pids=set(stable_pids),
            state_root=state_root,
            context_checkpoints=0,
            server_launch_args=water.checkpoint_control.CUDA_ROOT_SERVER_ARGS,
            moe_server_args=water.checkpoint_control.DEFAULT_MOE_SERVER_ARGS,
        )
        readiness = sidecar.launch()
        launch = readiness.get("launch_configuration")
        require(
            isinstance(launch, Mapping)
            and launch.get("server_launch_args") == list(water.checkpoint_control.CUDA_ROOT_SERVER_ARGS)
            and launch.get("moe_server_args") == list(water.checkpoint_control.DEFAULT_MOE_SERVER_ARGS)
            and launch.get("root_storage") == "device"
            and launch.get("speculative_type") == "none",
            "0084 launch identity changed",
        )
        baseline_private = None
        process_memory = readiness.get("process_memory")
        if isinstance(process_memory, Mapping) and type(process_memory.get("private_bytes")) is int:
            baseline_private = int(process_memory["private_bytes"])
        codec = harness.carrier.SidecarPromptCodec(harness.live_runtime.PORT)
        prepared = prepare_task_and_branch(codec, roots[ROOT_ID])
        props = codec.props()
        marker_receipt = create_consumed_marker(marker, args.expected_commit)
        result = evaluate(
            sidecar=sidecar,
            codec=codec,
            props=props,
            root=roots[ROOT_ID],
            prepared=prepared,
            baseline_private=baseline_private,
        )
        result["consumption_marker"] = marker_receipt
        result["candidate_commit"] = args.expected_commit
        result["runtime_bundle_before"] = before_bundle
        result["runtime_bundle_after"] = runtime_bundle(binary)
        result["static_evidence"] = static
        result["readiness"] = {
            "pid": readiness.get("pid"),
            "readiness_seconds": readiness.get("readiness_seconds"),
            "binary": readiness.get("binary"),
            "model": readiness.get("model"),
            "wddm": readiness.get("wddm"),
            "launch_configuration": launch,
        }
    except BaseException as exc:
        caught = exc
    finally:
        cleanup = dict(harness.live_runtime.safe_sidecar_cleanup(sidecar))
        if sidecar is not None:
            source_log = Path(str((getattr(sidecar, "readiness", {}) or {}).get("log_path") or ""))
            if source_log.is_file():
                log_output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_log, log_output)
                cleanup["server_log_copy"] = {
                    "path": str(log_output),
                    "bytes": log_output.stat().st_size,
                    "sha256": harness.live_runtime.sha256_file(log_output),
                }
        shutil.rmtree(state_root, ignore_errors=True)
        os.environ.pop("LLAMA_ARG_LOG_VERBOSITY", None)
        os.environ.pop("LLAMA_SERVER_SLOTS_DEBUG", None)

    if caught is not None:
        failure = {
            "id": EXPERIMENT_ID,
            "attempt_id": ATTEMPT_ID,
            "status": "failed-after-consumption" if marker_receipt else "pre-science-failure",
            "error_type": type(caught).__name__,
            "error": str(caught),
            "consumption_marker": marker_receipt,
            "cleanup": cleanup,
            "automatic_promotion": False,
            "research_goal_blocked": False,
        }
        write_exclusive_json(output, failure)
        raise ExperimentError(f"{EXPERIMENT_ID} failed; evidence preserved at {output}") from caught

    require(result is not None, "0084 result is missing")
    result["cleanup"] = cleanup
    cleanup_gate = harness.live_runtime.cleanup_integrity(cleanup, set(stable_pids))
    result["cleanup_gate"] = cleanup_gate
    if cleanup_gate.get("passed") is not True:
        result["verdict"] = "reject"
        result["classification"] = "terminal-logits-continuation-cleanup-failure"
    result["artifact"] = write_exclusive_json(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
