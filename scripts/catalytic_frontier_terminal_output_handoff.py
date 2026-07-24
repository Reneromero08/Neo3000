#!/usr/bin/env python3
"""neo-exp-0085: terminal-seeded output-bearing CUDA capsule handoff.

This composes two already accepted primitives without changing the server:

1. the exact 690-token CUDA root plus host-F32 terminal logits samples the
   seed answer with zero fresh prompt tokens; and
2. that live answer-bearing state is saved as the exact 695-token CUDA child
   used by the accepted fixed-size recurrence.

The sole measured edge is C -> D.  The catalytic route restores the child and
evaluates 87 fresh suffix tokens.  The matched control inserts the identical
token IDs into the identical 782-token request with cache disabled.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import time
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import baseline_harness
import catalytic_frontier_fanout as shared_tasks
import catalytic_frontier_fixed_size_rebase as rebase
import catalytic_frontier_harness as harness
import catalytic_frontier_output_fixed_point as fixed
import catalytic_frontier_recursive_root_promotion as rolling
import catalytic_frontier_single_request_latency as latency
import catalytic_frontier_terminal_logits_continuation as terminal
import catalytic_frontier_water_panel_qualifier as water


EXPERIMENT_ID = "neo-exp-0085"
ATTEMPT_ID = "frontier-attempt-0119"
ROOT_ID = water.ROOT_ID
BASE_ROOT_ID = "neo-exp-0085-base-689"
TERMINAL_ROOT_ID = "neo-exp-0085-terminal-690"
WARMUP_PAIRS = 1
COUNTED_PAIRS = 4
PAIR_ORDERS = (
    ("catalytic", "direct"),
    ("direct", "catalytic"),
    ("catalytic", "direct"),
    ("direct", "catalytic"),
)
MIN_HANDOFF_LIFECYCLE_SPEEDUP = 1.25
MIN_PAIR_DOMINANCE = 0.75
MAX_WDDM_BYTES = 6000 * 1024 * 1024
EXPECTED_BASE_TOKENS = 689
EXPECTED_TERMINAL_TOKENS = 690
EXPECTED_CHILD_TOKENS = 695
EXPECTED_SUCCESSOR_TOKENS = 782
EXPECTED_SUCCESSOR_FRESH_TOKENS = 87
EXPECTED_BASE_DEVICE_BYTES = 79_974_400
EXPECTED_TERMINAL_DEVICE_BYTES = 79_994_880
EXPECTED_CHILD_DEVICE_BYTES = 80_097_280
EXPECTED_TWO_ROOT_DEVICE_BYTES = (
    EXPECTED_BASE_DEVICE_BYTES + EXPECTED_TERMINAL_DEVICE_BYTES
)
EXPECTED_THREE_ROOT_DEVICE_BYTES = (
    EXPECTED_TWO_ROOT_DEVICE_BYTES + EXPECTED_CHILD_DEVICE_BYTES
)
EXPECTED_SEED_ANSWER = "C"
EXPECTED_SUCCESSOR_ANSWER = "D"
EXPECTED_BRANCH_TOKEN_SHA256 = (
    "A454640FCAE18925F9A4B54672C0A1F681721E9CF72BC19220C940E64B629B12"
)
EXPECTED_SEED_GENERATED_SHA256 = (
    "BD33E852EF9FDDEE49A1056501456071169FF3E3C7699C2A5BAAA2D0DF30CABC"
)
EXPECTED_CHILD_TOKEN_SHA256 = (
    "1F956F9C177106F0775B3DAA054CA7BF046F980277C8E2CE6029AD78C7E90395"
)
EXPECTED_SUCCESSOR_REQUEST_SHA256 = (
    "5F80CECB28FC4336A9630C092A215F75C52EFFE03EBB8CECAE6D63832341B962"
)
EXPECTED_SUCCESSOR_GENERATED_SHA256 = (
    "0CA13167369ED1835BB8938644A7CCEF6EDE0BD65AE31C256931C54D3FA9FB31"
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BINARY = terminal.DEFAULT_BINARY
DEFAULT_MODEL = terminal.DEFAULT_MODEL
DEFAULT_OUTPUT = ROOT / "lab" / f"{EXPERIMENT_ID}.local.json"
DEFAULT_LOG = ROOT / "lab" / f"{EXPERIMENT_ID}.server.local.log"
DEFAULT_MARKER = ROOT / "lab" / f"{EXPERIMENT_ID}.consumed.local.json"


class ExperimentError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ExperimentError(message)


def canonical_sha256(value: Any) -> str:
    return terminal.canonical_sha256(value)


def distribution(values: Sequence[float]) -> dict[str, float]:
    return terminal.distribution(values)


def child_root_id(pair_label: str) -> str:
    require(pair_label and all(ch.isalnum() or ch == "-" for ch in pair_label), "invalid pair label")
    return f"{EXPERIMENT_ID}-child-{pair_label}"


def create_consumed_marker(path: Path, expected_commit: str) -> dict[str, Any]:
    marker = {
        "id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "expected_commit": expected_commit,
        "retry_allowed": False,
        "automatic_promotion": False,
        "scientific_boundary": "before-first-task-a-request",
    }
    return terminal.write_exclusive_json(path, marker)


def validate_terminal_root(
    response: Mapping[str, Any],
    *,
    action: str,
    root_id: str,
    n_tokens: int,
    terminal_logits: bool,
    expected: Mapping[str, Any] | None = None,
    expected_roots_after: int,
    expected_total_device_bytes_after: int,
) -> dict[str, Any]:
    record = terminal.validate_root(
        response,
        action=action,
        root_id=root_id,
        n_tokens=n_tokens,
        expected=expected,
        terminal=terminal_logits,
    )
    require(record["n_roots_capacity"] == 5, "root-bank capacity changed")
    require(record["n_roots_after"] == expected_roots_after, "root-bank count changed")
    require(
        record["n_total_device_bytes_after"] == expected_total_device_bytes_after,
        "aggregate device-root bytes changed",
    )
    require(
        record["n_total_gpu_bytes_after"] == expected_total_device_bytes_after,
        "aggregate GPU-root bytes changed",
    )
    return record


def terminal_root_action(
    *,
    action: str,
    root_id: str,
    n_tokens: int,
    terminal_logits: bool,
    expected_roots_after: int,
    expected_total_device_bytes_after: int,
    expected: Mapping[str, Any] | None = None,
    include_terminal_logits: bool = False,
    require_terminal_logits: bool = False,
) -> tuple[dict[str, Any], float]:
    raw, wall = harness.ram_root_action(
        action=action,
        root_id=root_id,
        storage="device" if action == "root-save" else "default",
        include_terminal_logits=include_terminal_logits,
        require_terminal_logits=require_terminal_logits,
    )
    return (
        validate_terminal_root(
            raw,
            action=action,
            root_id=root_id,
            n_tokens=n_tokens,
            terminal_logits=terminal_logits,
            expected=expected,
            expected_roots_after=expected_roots_after,
            expected_total_device_bytes_after=expected_total_device_bytes_after,
        ),
        wall,
    )


def child_root_action(
    *,
    action: str,
    root_id: str,
    expected_roots_after: int,
    expected_total_device_bytes_after: int,
    expected: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    raw, wall = harness.ram_root_action(
        action=action,
        root_id=root_id,
        storage="device" if action == "root-save" else "default",
    )
    require(raw.get("has_terminal_logits") is False, "child accidentally retained terminal logits")
    require(raw.get("n_terminal_logits") == 0, "child terminal-logit count is nonzero")
    require(raw.get("n_terminal_logits_bytes") == 0, "child terminal-logit bytes are nonzero")
    record = rebase.validate_root(
        raw,
        action=action,
        root_id=root_id,
        storage="device",
        expected=expected,
        expected_tokens=EXPECTED_CHILD_TOKENS,
        expected_roots_after=expected_roots_after,
        expected_total_device_bytes_after=expected_total_device_bytes_after,
        expected_root_capacity=5,
    )
    require(record["n_device_bytes"] == EXPECTED_CHILD_DEVICE_BYTES, "child device bytes changed")
    record.update(
        client_wall_seconds=wall,
        has_terminal_logits=False,
        n_terminal_logits=0,
        n_terminal_logits_bytes=0,
    )
    return record


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
        retained["retained_root_token_count"] == terminal.EXPECTED_RETAINED_TOKENS,
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


def run_seed(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    branch_tokens: Sequence[int],
    terminal_saved: Mapping[str, Any],
    label: str,
) -> tuple[dict[str, Any], dict[str, Any], list[int]]:
    restored, restore_wall = terminal_root_action(
        action="root-restore",
        root_id=TERMINAL_ROOT_ID,
        n_tokens=EXPECTED_TERMINAL_TOKENS,
        terminal_logits=True,
        expected=terminal_saved,
        require_terminal_logits=True,
        expected_roots_after=2,
        expected_total_device_bytes_after=EXPECTED_TWO_ROOT_DEVICE_BYTES,
    )
    payload = terminal.completion_payload(branch_tokens, cache_prompt=True)
    payload.update(
        neo3000_use_terminal_logits=True,
        neo3000_terminal_root_id=TERMINAL_ROOT_ID,
        neo3000_terminal_logits_fnv64=terminal_saved["terminal_logits_fnv64"],
    )
    recorder = latency.TimingRecorder()
    record = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:{label}:terminal-seed",
        payload,
        recorder=recorder,
        batch_owned_request=True,
    )
    timing = recorder.summary(request_wall_seconds=float(record["wall_seconds"]))
    require(record["prompt_tokens"] == EXPECTED_TERMINAL_TOKENS, "terminal seed prompt changed")
    require(
        record["cached_prompt_tokens"] == EXPECTED_TERMINAL_TOKENS
        and record["fresh_prompt_tokens"] == 0,
        "terminal seed cache split changed",
    )
    require(timing["server_prompt_n"] == 0, "terminal seed prompt timing changed")
    state = fixed.generated_state(record, codec=codec, props=props)
    require(state["answer"] == EXPECTED_SEED_ANSWER, "terminal seed answer changed")
    require(
        state["generated_token_sha256"] == EXPECTED_SEED_GENERATED_SHA256,
        "terminal seed generated-token identity changed",
    )
    child_tokens = rebase.compact_child_tokens(branch_tokens, state)
    require(len(child_tokens) == EXPECTED_CHILD_TOKENS, "output-bearing child token count changed")
    require(
        canonical_sha256(child_tokens) == EXPECTED_CHILD_TOKEN_SHA256,
        "output-bearing child token identity changed",
    )
    record.update(
        route="terminal-seed",
        state=state,
        input_token_sha256=canonical_sha256(list(branch_tokens)),
        generated_token_sha256=state["generated_token_sha256"],
        restore=restored,
        restore_client_wall_seconds=restore_wall,
        effective_wall_seconds=float(record["wall_seconds"]) + restore_wall,
        timing=timing,
    )
    return record, state, child_tokens


def run_successor(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    child_root: Mapping[str, Any],
    child_tokens: Sequence[int],
    seed_state: Mapping[str, Any],
    label: str,
    route: str,
    contract: rebase.RecurrenceContract,
) -> dict[str, Any]:
    require(route in {"catalytic", "direct"}, "successor route changed")
    restore: dict[str, Any] | None = None
    restore_wall = 0.0
    if route == "catalytic":
        restore = child_root_action(
            action="root-restore",
            root_id=str(child_root["root_id"]),
            expected=child_root,
            expected_roots_after=3,
            expected_total_device_bytes_after=EXPECTED_THREE_ROOT_DEVICE_BYTES,
        )
        restore_wall = float(restore["client_wall_seconds"])

    tokens, payload, ancestry = rolling.derive_promoted_successor(
        codec=codec,
        root_tokens=child_tokens,
        prior_state=seed_state,
        seed=shared_tasks.derive_seed(ROOT_ID, "fixed-size-rebase-step-1"),
        cache_prompt=route == "catalytic",
        transition_content=contract.transition_content,
    )
    require(len(tokens) == EXPECTED_SUCCESSOR_TOKENS, "successor token count changed")
    require(
        ancestry["request_token_sha256"] == EXPECTED_SUCCESSOR_REQUEST_SHA256,
        "successor request identity changed",
    )
    recorder = latency.TimingRecorder()
    record = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:{label}:{route}",
        payload,
        recorder=recorder,
        batch_owned_request=True,
    )
    state = fixed.generated_state(record, codec=codec, props=props)
    require(state["answer"] == EXPECTED_SUCCESSOR_ANSWER, "C-to-D successor answer changed")
    require(
        state["generated_token_sha256"] == EXPECTED_SUCCESSOR_GENERATED_SHA256,
        "C-to-D successor generated-token identity changed",
    )
    expected_cached = EXPECTED_CHILD_TOKENS if route == "catalytic" else 0
    expected_fresh = EXPECTED_SUCCESSOR_FRESH_TOKENS if route == "catalytic" else EXPECTED_SUCCESSOR_TOKENS
    require(record["prompt_tokens"] == EXPECTED_SUCCESSOR_TOKENS, "successor prompt count changed")
    require(record["cached_prompt_tokens"] == expected_cached, f"{route} cached split changed")
    require(record["fresh_prompt_tokens"] == expected_fresh, f"{route} fresh split changed")
    timing = recorder.summary(request_wall_seconds=float(record["wall_seconds"]))
    require(timing["server_prompt_n"] == expected_fresh, f"{route} prompt timing count changed")
    record.update(
        route=route,
        state=state,
        ancestry=ancestry,
        restore=restore,
        restore_client_wall_seconds=restore_wall,
        effective_wall_seconds=float(record["wall_seconds"]) + restore_wall,
        input_token_sha256=ancestry["request_token_sha256"],
        timing=timing,
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


def run_pair(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    branch_tokens: Sequence[int],
    terminal_saved: Mapping[str, Any],
    pair_label: str,
    route_order: Sequence[str],
    contract: rebase.RecurrenceContract,
    baseline_private: int | None,
) -> dict[str, Any]:
    require(set(route_order) == {"catalytic", "direct"}, "pair route order changed")
    seed, seed_state, child_tokens = run_seed(
        sidecar=sidecar,
        codec=codec,
        props=props,
        branch_tokens=branch_tokens,
        terminal_saved=terminal_saved,
        label=pair_label,
    )
    root_id = child_root_id(pair_label)
    child_save = child_root_action(
        action="root-save",
        root_id=root_id,
        expected_roots_after=3,
        expected_total_device_bytes_after=EXPECTED_THREE_ROOT_DEVICE_BYTES,
    )
    resources_with_child = harness.process_resources(sidecar, baseline_private)
    routes: dict[str, dict[str, Any]] = {}
    for route in route_order:
        routes[route] = run_successor(
            sidecar=sidecar,
            codec=codec,
            props=props,
            child_root=child_save,
            child_tokens=child_tokens,
            seed_state=seed_state,
            label=pair_label,
            route=route,
            contract=contract,
        )
    require(
        routes["catalytic"]["input_token_sha256"] == routes["direct"]["input_token_sha256"],
        "paired successor inputs differ",
    )
    require(
        routes["catalytic"]["state"]["generated_token_ids"]
        == routes["direct"]["state"]["generated_token_ids"],
        "paired successor outputs differ",
    )
    child_erase = child_root_action(
        action="root-erase",
        root_id=root_id,
        expected=child_save,
        expected_roots_after=2,
        expected_total_device_bytes_after=EXPECTED_TWO_ROOT_DEVICE_BYTES,
    )
    catalytic_lifecycle = (
        float(child_save["client_wall_seconds"])
        + float(routes["catalytic"]["effective_wall_seconds"])
        + float(child_erase["client_wall_seconds"])
    )
    direct_lifecycle = float(routes["direct"]["effective_wall_seconds"])
    return {
        "pair_label": pair_label,
        "route_order": list(route_order),
        "seed": seed,
        "seed_state": seed_state,
        "child_tokens": list(child_tokens),
        "child_token_sha256": canonical_sha256(child_tokens),
        "child_save": child_save,
        "resources_with_child": resources_with_child,
        "routes": routes,
        "child_erase": child_erase,
        "catalytic_handoff_lifecycle_seconds": catalytic_lifecycle,
        "direct_materialized_lifecycle_seconds": direct_lifecycle,
        "catalytic_won": catalytic_lifecycle < direct_lifecycle,
        "avoided_fresh_prompt_tokens": (
            int(routes["direct"]["fresh_prompt_tokens"])
            - int(routes["catalytic"]["fresh_prompt_tokens"])
        ),
    }


def evaluate(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    prepared: Mapping[str, Any],
    baseline_private: int | None,
) -> dict[str, Any]:
    task, branch_tokens, retained = task_and_branch(
        sidecar,
        codec,
        props,
        prepared,
    )
    require(len(branch_tokens) == EXPECTED_TERMINAL_TOKENS, "branch prompt changed")
    require(
        canonical_sha256(branch_tokens) == EXPECTED_BRANCH_TOKEN_SHA256,
        "branch prompt identity changed",
    )
    base_tokens = list(branch_tokens[:-1])
    require(len(base_tokens) == EXPECTED_BASE_TOKENS, "base prompt changed")
    base_payload = terminal.completion_payload(base_tokens, cache_prompt=False, n_predict=0)
    base_materialization = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:base-689-materialize",
        base_payload,
        operation_kind="zero-output-root-readdress",
    )
    require(
        base_materialization["cached_prompt_tokens"] == 0
        and base_materialization["fresh_prompt_tokens"] == EXPECTED_BASE_TOKENS,
        "base materialization geometry changed",
    )
    base_raw, base_save_wall = harness.ram_root_action(
        action="root-save",
        root_id=BASE_ROOT_ID,
        storage="device",
    )
    base_saved = validate_terminal_root(
        base_raw,
        action="root-save",
        root_id=BASE_ROOT_ID,
        n_tokens=EXPECTED_BASE_TOKENS,
        terminal_logits=False,
        expected_roots_after=1,
        expected_total_device_bytes_after=EXPECTED_BASE_DEVICE_BYTES,
    )
    require(base_saved["n_device_bytes"] == EXPECTED_BASE_DEVICE_BYTES, "base device bytes changed")

    base_restore, base_restore_wall = terminal_root_action(
        action="root-restore",
        root_id=BASE_ROOT_ID,
        n_tokens=EXPECTED_BASE_TOKENS,
        terminal_logits=False,
        expected=base_saved,
        expected_roots_after=1,
        expected_total_device_bytes_after=EXPECTED_BASE_DEVICE_BYTES,
    )
    promotion_payload = terminal.completion_payload(
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
    terminal_raw, terminal_save_wall = harness.ram_root_action(
        action="root-save",
        root_id=TERMINAL_ROOT_ID,
        storage="device",
        include_terminal_logits=True,
    )
    terminal_saved = validate_terminal_root(
        terminal_raw,
        action="root-save",
        root_id=TERMINAL_ROOT_ID,
        n_tokens=EXPECTED_TERMINAL_TOKENS,
        terminal_logits=True,
        expected_roots_after=2,
        expected_total_device_bytes_after=EXPECTED_TWO_ROOT_DEVICE_BYTES,
    )
    require(
        terminal_saved["n_device_bytes"] == EXPECTED_TERMINAL_DEVICE_BYTES,
        "terminal device bytes changed",
    )

    missing_negative = terminal.expect_http_error(
        f"http://127.0.0.1:{harness.live_runtime.PORT}/slots/0?action=root-restore",
        {"root_id": BASE_ROOT_ID, "require_terminal_logits": True},
        "RAM root has no exact terminal-logits boundary",
    )
    terminal_restore, _ = terminal_root_action(
        action="root-restore",
        root_id=TERMINAL_ROOT_ID,
        n_tokens=EXPECTED_TERMINAL_TOKENS,
        terminal_logits=True,
        expected=terminal_saved,
        require_terminal_logits=True,
        expected_roots_after=2,
        expected_total_device_bytes_after=EXPECTED_TWO_ROOT_DEVICE_BYTES,
    )
    mismatch_payload = terminal.completion_payload(branch_tokens, cache_prompt=True)
    mismatch_payload.update(
        neo3000_use_terminal_logits=True,
        neo3000_terminal_root_id=TERMINAL_ROOT_ID,
        neo3000_terminal_logits_fnv64="0" * 16,
    )
    mismatch_negative = terminal.expect_http_error(
        f"http://127.0.0.1:{harness.live_runtime.PORT}/completion",
        mismatch_payload,
        "Terminal-logits continuation identity mismatch",
    )

    contract = rebase.validate_contract(
        replace(rebase.absorbing_contract(3), root_bank_capacity=5)
    )
    ownership: list[dict[str, Any]] = []

    def ownership_boundary(label: str) -> None:
        started = time.monotonic()
        evidence = sidecar.exact_ownership(label)
        ownership.append(
            {
                "boundary": label,
                "client_wall_seconds": time.monotonic() - started,
                "evidence": evidence,
            }
        )

    ownership_boundary("pre-terminal-output-handoff-batch")
    warmup = run_pair(
        sidecar=sidecar,
        codec=codec,
        props=props,
        branch_tokens=branch_tokens,
        terminal_saved=terminal_saved,
        pair_label="warmup-1",
        route_order=("catalytic", "direct"),
        contract=contract,
        baseline_private=baseline_private,
    )
    counted: list[dict[str, Any]] = []
    for index, route_order in enumerate(PAIR_ORDERS, start=1):
        counted.append(
            run_pair(
                sidecar=sidecar,
                codec=codec,
                props=props,
                branch_tokens=branch_tokens,
                terminal_saved=terminal_saved,
                pair_label=f"pair-{index}",
                route_order=route_order,
                contract=contract,
                baseline_private=baseline_private,
            )
        )
    ownership_boundary("post-terminal-output-handoff-batch")
    tool_canary = run_tool_canary(sidecar)

    terminal_erased, terminal_erase_wall = terminal_root_action(
        action="root-erase",
        root_id=TERMINAL_ROOT_ID,
        n_tokens=EXPECTED_TERMINAL_TOKENS,
        terminal_logits=True,
        expected=terminal_saved,
        expected_roots_after=1,
        expected_total_device_bytes_after=EXPECTED_BASE_DEVICE_BYTES,
    )
    base_erased, base_erase_wall = terminal_root_action(
        action="root-erase",
        root_id=BASE_ROOT_ID,
        n_tokens=EXPECTED_BASE_TOKENS,
        terminal_logits=False,
        expected=base_saved,
        expected_roots_after=0,
        expected_total_device_bytes_after=0,
    )
    require(
        base_erased["n_total_bytes_after"] == 0
        and base_erased["n_total_device_bytes_after"] == 0
        and base_erased["n_total_gpu_bytes_after"] == 0,
        "root bank did not close",
    )
    resources_after_erase = harness.process_resources(sidecar, baseline_private)

    ownership_total = sum(float(item["client_wall_seconds"]) for item in ownership)
    ownership_share = ownership_total / (2 * COUNTED_PAIRS)
    for pair in counted:
        pair["catalytic_handoff_lifecycle_seconds"] += ownership_share
        pair["direct_materialized_lifecycle_seconds"] += ownership_share
        pair["catalytic_won"] = (
            pair["catalytic_handoff_lifecycle_seconds"]
            < pair["direct_materialized_lifecycle_seconds"]
        )

    catalytic_lifecycle = [
        float(pair["catalytic_handoff_lifecycle_seconds"]) for pair in counted
    ]
    direct_lifecycle = [
        float(pair["direct_materialized_lifecycle_seconds"]) for pair in counted
    ]
    lifecycle_speedup = (
        sum(direct_lifecycle) / sum(catalytic_lifecycle)
    )
    pair_dominance = sum(bool(pair["catalytic_won"]) for pair in counted) / COUNTED_PAIRS
    avoided = [int(pair["avoided_fresh_prompt_tokens"]) for pair in counted]

    log_path = Path(str(sidecar.readiness["log_path"]))
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    capture_markers = log_text.count("neo3000 terminal-logits boundary captured")
    sample_markers = log_text.count("neo3000 terminal-logits continuation sampled before decode")
    full_reprocess_markers = log_text.count("forcing full prompt re-processing")

    all_pairs = [warmup, *counted]
    all_routes = [
        route
        for pair in all_pairs
        for route in pair["routes"].values()
    ]
    gates = {
        "task_a_correct": (
            harness.carrier.parse_task_a_output(task["content"])["answer"]
            == harness.EXPECTED[ROOT_ID]["task_a"]
        ),
        "terminal_seed_690_cached_0_fresh_exact": all(
            pair["seed"]["cached_prompt_tokens"] == EXPECTED_TERMINAL_TOKENS
            and pair["seed"]["fresh_prompt_tokens"] == 0
            and pair["seed_state"]["generated_token_sha256"]
            == EXPECTED_SEED_GENERATED_SHA256
            for pair in all_pairs
        ),
        "branch_prompt_identity_exact": canonical_sha256(branch_tokens)
        == EXPECTED_BRANCH_TOKEN_SHA256,
        "output_bearing_child_695_exact": all(
            pair["child_token_sha256"] == EXPECTED_CHILD_TOKEN_SHA256
            and pair["child_save"]["n_tokens"] == EXPECTED_CHILD_TOKENS
            and pair["child_save"]["n_device_bytes"] == EXPECTED_CHILD_DEVICE_BYTES
            for pair in all_pairs
        ),
        "child_contains_no_terminal_logits": all(
            pair["child_save"]["has_terminal_logits"] is False
            and pair["child_save"]["n_terminal_logits"] == 0
            and pair["child_save"]["n_terminal_logits_bytes"] == 0
            for pair in all_pairs
        ),
        "successor_prompt_and_output_identity_exact": all(
            route["input_token_sha256"] == EXPECTED_SUCCESSOR_REQUEST_SHA256
            and route["state"]["generated_token_sha256"]
            == EXPECTED_SUCCESSOR_GENERATED_SHA256
            for route in all_routes
        ),
        "catalytic_695_cached_87_fresh": all(
            pair["routes"]["catalytic"]["cached_prompt_tokens"] == EXPECTED_CHILD_TOKENS
            and pair["routes"]["catalytic"]["fresh_prompt_tokens"]
            == EXPECTED_SUCCESSOR_FRESH_TOKENS
            for pair in all_pairs
        ),
        "direct_0_cached_782_fresh": all(
            pair["routes"]["direct"]["cached_prompt_tokens"] == 0
            and pair["routes"]["direct"]["fresh_prompt_tokens"] == EXPECTED_SUCCESSOR_TOKENS
            for pair in all_pairs
        ),
        "paired_successor_generated_arrays_exact": all(
            pair["routes"]["catalytic"]["state"]["generated_token_ids"]
            == pair["routes"]["direct"]["state"]["generated_token_ids"]
            for pair in all_pairs
        ),
        "avoided_fresh_prompt_tokens_695_each": avoided == [695] * COUNTED_PAIRS,
        "counted_avoided_fresh_prompt_tokens_2780": sum(avoided) == 2_780,
        "handoff_lifecycle_speedup_at_least_1_25": (
            lifecycle_speedup >= MIN_HANDOFF_LIFECYCLE_SPEEDUP
        ),
        "pair_dominance_at_least_0_75": pair_dominance >= MIN_PAIR_DOMINANCE,
        "capture_marker_exactly_one": capture_markers == 1,
        "predecode_sample_marker_count_exact": sample_markers == WARMUP_PAIRS + COUNTED_PAIRS,
        "zero_full_reprocess_markers": full_reprocess_markers == 0,
        "missing_terminal_rejected_pre_model": missing_negative["http_status"] == 400,
        "mismatched_terminal_rejected_pre_model": mismatch_negative["http_status"] == 400,
        "maximum_three_device_roots_exact": (
            all(
                pair["resources_with_child"].get("peak_wddm_bytes") is not None
                for pair in all_pairs
            )
            and all(
                pair["child_save"]["n_total_device_bytes_after"]
                == EXPECTED_THREE_ROOT_DEVICE_BYTES
                for pair in all_pairs
            )
        ),
        "child_erase_returns_to_two_roots": all(
            pair["child_erase"]["n_roots_after"] == 2
            and pair["child_erase"]["n_total_device_bytes_after"]
            == EXPECTED_TWO_ROOT_DEVICE_BYTES
            for pair in all_pairs
        ),
        "root_bank_closed_to_zero": base_erased["n_total_bytes_after"] == 0,
        "wddm_at_or_below_6000_mib": (
            all(
                type(pair["resources_with_child"].get("peak_wddm_bytes")) is int
                and int(pair["resources_with_child"]["peak_wddm_bytes"]) <= MAX_WDDM_BYTES
                for pair in all_pairs
            )
        ),
        "batch_ownership_boundaries_exact": (
            len(ownership) == 2
            and all(item["evidence"].get("passed") is True for item in ownership)
        ),
        "pi_tool_call_valid": tool_canary["validation"].get("passed") is True,
        "automatic_promotion": False,
        "unbounded_catalytic_inference_established": False,
    }
    accepted = all(
        value is True
        for key, value in gates.items()
        if key not in {"automatic_promotion", "unbounded_catalytic_inference_established"}
    )

    return {
        "id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "complete",
        "verdict": "accept" if accepted else "reject",
        "classification": (
            "terminal-seeded-output-bearing-cuda-capsule-handoff-c-to-d-supported-bounded"
            if accepted
            else "terminal-output-handoff-without-preregistered-speed-or-integrity-gate"
        ),
        "hypothesis": (
            "A zero-fresh terminal-logits seed can be promoted directly into the exact "
            "output-bearing CUDA capsule used by a dependent C-to-D successor while "
            "preserving exact utility and positive fully charged handoff advantage."
        ),
        "trial_design": {
            "axis": "R",
            "R": 1,
            "fanout": False,
            "warmup_pairs": WARMUP_PAIRS,
            "counted_pairs": COUNTED_PAIRS,
            "pair_orders": [list(order) for order in PAIR_ORDERS],
            "seed": "690-token CUDA root plus host-F32 terminal logits at 690/0",
            "handoff": "save exact live 695-token output-bearing CUDA child",
            "catalytic_successor": "restore 695-token child and evaluate 87-token suffix",
            "control": "identical 782-token materialized request with cache disabled",
            "metric_scope": (
                "post-seed marginal handoff only: child save + catalytic restore/request + "
                "child erase versus the direct 782-token request; Task-A, base/terminal "
                "preparation, and the common terminal seed are reported but excluded from "
                "both sides of this ratio"
            ),
        },
        "identities": {
            "task_a_prompt_sha256": canonical_sha256(prepared["prompt_tokens"]),
            "branch_prompt_sha256": canonical_sha256(branch_tokens),
            "seed_generated_token_sha256": EXPECTED_SEED_GENERATED_SHA256,
            "child_token_sha256": EXPECTED_CHILD_TOKEN_SHA256,
            "successor_request_sha256": EXPECTED_SUCCESSOR_REQUEST_SHA256,
            "successor_generated_token_sha256": EXPECTED_SUCCESSOR_GENERATED_SHA256,
            "terminal_logits_fnv64": terminal_saved["terminal_logits_fnv64"],
            "terminal_prompt_fnv64": terminal_saved["terminal_prompt_fnv64"],
            "terminal_sampler_fnv64": terminal_saved["terminal_sampler_fnv64"],
        },
        "setup": {
            "task_a": harness.token_summary(task),
            "retained_root_token_count": retained["retained_root_token_count"],
            "base_materialization": harness.token_summary(base_materialization),
            "base_save": base_saved,
            "base_save_client_wall_seconds": base_save_wall,
            "base_restore": base_restore,
            "base_restore_client_wall_seconds": base_restore_wall,
            "terminal_promotion": harness.token_summary(promotion),
            "terminal_save": terminal_saved,
            "terminal_save_client_wall_seconds": terminal_save_wall,
            "terminal_negative_restore": terminal_restore,
        },
        "negative_controls": {
            "missing_terminal": missing_negative,
            "mismatched_digest": mismatch_negative,
        },
        "warmup": warmup,
        "counted_pairs": counted,
        "metrics": {
            "catalytic_handoff_lifecycle_seconds": distribution(catalytic_lifecycle),
            "direct_materialized_lifecycle_seconds": distribution(direct_lifecycle),
            "aggregate_catalytic_handoff_lifecycle_seconds": sum(catalytic_lifecycle),
            "aggregate_direct_materialized_lifecycle_seconds": sum(direct_lifecycle),
            "handoff_lifecycle_speedup": lifecycle_speedup,
            "pair_dominance": pair_dominance,
            "counted_avoided_fresh_prompt_tokens": sum(avoided),
        },
        "runtime_markers": {
            "capture_count": capture_markers,
            "predecode_sample_count": sample_markers,
            "full_reprocess_count": full_reprocess_markers,
        },
        "resources": {
            "with_three_roots": [
                pair["resources_with_child"]
                for pair in all_pairs
            ],
            "after_erase": resources_after_erase,
        },
        "root_closure": {
            "terminal_erase": terminal_erased,
            "terminal_erase_client_wall_seconds": terminal_erase_wall,
            "base_erase": base_erased,
            "base_erase_client_wall_seconds": base_erase_wall,
        },
        "batch_ownership": {
            "boundaries": ownership,
            "total_seconds": ownership_total,
            "amortized_seconds_per_counted_route": ownership_share,
        },
        "tool_canary": tool_canary,
        "quality_gates": gates,
        "claim_ceiling": (
            "One bounded process-local Agents-A1 C-to-D post-seed marginal handoff from "
            "a zero-fresh terminal-logits seed into an exact output-bearing CUDA child; "
            "the speed ratio excludes common seed and shared setup, and supports no "
            "recursive terminal pipeline, canonical .holo, restart persistence, weight "
            "catalysis, general recurrence, or unbounded-compute claim."
        ),
        "automatic_promotion": False,
        "research_goal_blocked": False,
        "next_boundary": (
            "IF_ACCEPTED_PREREGISTER_R2_UNIQUE_DESCENDANT_SUCCESSOR_TERMINAL_PIPELINE; "
            "IF_REJECTED_LOCALIZE_THE_TERMINAL_TO_CHILD_SEAM_WITHOUT_NEW_SERVER_MECHANISM"
        ),
    }


def static_audit(binary: Path) -> dict[str, Any]:
    source = Path(__file__).read_text(encoding="utf-8")
    terminal_source = Path(terminal.__file__).read_text(encoding="utf-8")
    rebase_source = Path(rebase.__file__).read_text(encoding="utf-8")
    gates = {
        "server_runtime_unchanged": "neo3000 terminal-logits continuation sampled before decode" in (
            ROOT / "tools" / "server" / "server-context.cpp"
        ).read_text(encoding="utf-8"),
        "terminal_seed_reused": "neo3000_use_terminal_logits=True" in source,
        "exact_live_output_child_saved": "child_root_action(" in source,
        "accepted_successor_derivation_reused": "rolling.derive_promoted_successor(" in source,
        "three_root_accounting_bound": "EXPECTED_THREE_ROOT_DEVICE_BYTES" in source,
        "cache_disabled_direct_control_present": "cache_prompt=route == \"catalytic\"" in source,
        "child_has_no_terminal_logits_gate": "child accidentally retained terminal logits" in source,
        "terminal_capture_primitive_present": "neo3000_capture_terminal_logits" in terminal_source,
        "fixed_child_primitive_present": "def compact_child_tokens(" in rebase_source,
        "no_automatic_promotion": '"automatic_promotion": False' in source,
        "bounded_claim_present": (
            "One bounded process-local Agents-A1 C-to-D post-seed marginal handoff"
            in source
        ),
    }
    require(all(gates.values()), "0085 static source audit failed")
    return {
        "gates": gates,
        "binary": {
            "path": str(binary),
            "sha256": harness.live_runtime.sha256_file(binary),
            "runtime_bundle": terminal.runtime_bundle(binary),
        },
        "controller_sha256": harness.live_runtime.sha256_file(Path(__file__)),
        "terminal_controller_sha256": harness.live_runtime.sha256_file(Path(terminal.__file__)),
        "fixed_rebase_controller_sha256": harness.live_runtime.sha256_file(Path(rebase.__file__)),
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
        require(not path.exists(), f"0085 artifact already exists: {path}")
    require(len({output, log_output, marker}) == 3, "0085 artifact paths collide")
    terminal.require_clean_head(ROOT, args.expected_commit)
    before_bundle = terminal.runtime_bundle(binary)
    static = static_audit(binary)

    corpus = harness.carrier.load_public_corpus(ROOT)
    roots = {str(item["root_id"]): item for item in corpus["roots"]}
    evaluator, live_contract = harness.load_discovery_sidecar_contract()
    stable_pids = harness.live_runtime.require_stable()
    require(len(stable_pids) == 1, "0085 requires one protected stable listener")
    require(
        not harness.live_runtime.listener_pids(harness.live_runtime.PORT),
        "candidate port is occupied",
    )

    state_root = Path(tempfile.mkdtemp(prefix="neo3000-terminal-output-handoff-"))
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
            and launch.get("server_launch_args")
            == list(water.checkpoint_control.CUDA_ROOT_SERVER_ARGS)
            and launch.get("moe_server_args")
            == list(water.checkpoint_control.DEFAULT_MOE_SERVER_ARGS)
            and launch.get("root_storage") == "device"
            and launch.get("speculative_type") == "none",
            "0085 launch identity changed",
        )
        baseline_private = None
        process_memory = readiness.get("process_memory")
        if (
            isinstance(process_memory, Mapping)
            and type(process_memory.get("private_bytes")) is int
        ):
            baseline_private = int(process_memory["private_bytes"])
        codec = harness.carrier.SidecarPromptCodec(harness.live_runtime.PORT)
        prepared = terminal.prepare_task_and_branch(codec, roots[ROOT_ID])
        props = codec.props()
        marker_receipt = create_consumed_marker(marker, args.expected_commit)
        result = evaluate(
            sidecar=sidecar,
            codec=codec,
            props=props,
            prepared=prepared,
            baseline_private=baseline_private,
        )
        result["consumption_marker"] = marker_receipt
        result["candidate_commit"] = args.expected_commit
        result["runtime_bundle_before"] = before_bundle
        result["runtime_bundle_after"] = terminal.runtime_bundle(binary)
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
            source_log = Path(
                str((getattr(sidecar, "readiness", {}) or {}).get("log_path") or "")
            )
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
        terminal.write_exclusive_json(output, failure)
        raise ExperimentError(
            f"{EXPERIMENT_ID} failed; evidence preserved at {output}"
        ) from caught

    require(result is not None, "0085 result is missing")
    result["cleanup"] = cleanup
    cleanup_gate = harness.live_runtime.cleanup_integrity(cleanup, set(stable_pids))
    result["cleanup_gate"] = cleanup_gate
    if cleanup_gate.get("passed") is not True:
        result["verdict"] = "reject"
        result["classification"] = "terminal-output-handoff-cleanup-failure"
    result["artifact"] = terminal.write_exclusive_json(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
