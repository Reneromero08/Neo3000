#!/usr/bin/env python3
"""neo-exp-0086: two-edge unique-descendant successor-terminal pipeline.

The experiment starts from the exact output-bearing C capsule accepted by
neo-exp-0085 and executes C -> D -> B through three matched routes:

* terminal: evaluate each 87-token suffix once, save its exact 782-token CUDA
  root plus terminal logits, then consume that root exactly once at 782/0;
* root-only: restore the identical 695-token child and evaluate the same
  87-token suffix live; and
* materialized: submit the identical 782-token request with cache disabled.

Every terminal or root-only edge rebases the generated output into the next
exact 695-token executable CUDA child, including the final B child.  This keeps
the fully charged fresh-prompt law at 93 tokens per edge versus 782 direct.
Terminal capture does not eliminate the 87-token evaluation; it moves that
work before the consumer boundary.  Consumer TTFT and fully charged lifecycle
are therefore adjudicated separately.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
import time
from dataclasses import asdict
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


EXPERIMENT_ID = "neo-exp-0086"
ATTEMPT_ID = "frontier-attempt-0121"
ROOT_ID = water.ROOT_ID
BASE_ROOT_ID = "neo-exp-0086-base-689"
SEED_TERMINAL_ROOT_ID = "neo-exp-0086-seed-terminal-690"
WARMUP_TRIALS = 1
COUNTED_TRIALS = 3
ROUTES = ("terminal", "root-only", "materialized")
TRIAL_ROUTE_ORDERS = (
    ("terminal", "root-only", "materialized"),
    ("root-only", "materialized", "terminal"),
    ("materialized", "terminal", "root-only"),
)
EXPECTED_STATES = ("C", "D", "B")
EDGE_PRIORS = ("C", "D")
EDGE_SUCCESSORS = ("D", "B")
EXPECTED_BASE_TOKENS = 689
EXPECTED_BRANCH_TOKENS = 690
EXPECTED_CHILD_TOKENS = 695
EXPECTED_SUCCESSOR_TOKENS = 782
EXPECTED_SUCCESSOR_FRESH_TOKENS = 87
EXPECTED_REBASE_FRESH_TOKENS = 6
EXPECTED_BASE_DEVICE_BYTES = 79_974_400
EXPECTED_SEED_TERMINAL_DEVICE_BYTES = 79_994_880
EXPECTED_CHILD_DEVICE_BYTES = 80_097_280
EXPECTED_SUCCESSOR_TERMINAL_DEVICE_BYTES = 81_879_040
EXPECTED_BASE_CHILD_DEVICE_BYTES = (
    EXPECTED_BASE_DEVICE_BYTES + EXPECTED_CHILD_DEVICE_BYTES
)
EXPECTED_MAX_PIPELINE_DEVICE_BYTES = (
    EXPECTED_BASE_CHILD_DEVICE_BYTES + EXPECTED_SUCCESSOR_TERMINAL_DEVICE_BYTES
)
EXPECTED_SETUP_THREE_ROOT_DEVICE_BYTES = (
    EXPECTED_BASE_DEVICE_BYTES
    + EXPECTED_SEED_TERMINAL_DEVICE_BYTES
    + EXPECTED_CHILD_DEVICE_BYTES
)
EXPECTED_TERMINAL_LOGITS = 248_320
EXPECTED_TERMINAL_LOGITS_BYTES = 993_280
EXPECTED_FRESH_PER_CATALYTIC_EDGE = (
    EXPECTED_SUCCESSOR_FRESH_TOKENS + EXPECTED_REBASE_FRESH_TOKENS
)
EXPECTED_AVOIDED_PER_EDGE = (
    EXPECTED_SUCCESSOR_TOKENS - EXPECTED_FRESH_PER_CATALYTIC_EDGE
)
EXPECTED_AVOIDED_PER_TRIAL = EXPECTED_AVOIDED_PER_EDGE * 2
MIN_CONSUMER_TTFT_SPEEDUP = 5.0
MIN_TERMINAL_VS_MATERIALIZED_WALL_SPEEDUP = 2.5
MIN_TERMINAL_VS_ROOT_ONLY_WALL_RATIO = 0.80
MIN_CONSUMER_TTFT_DOMINANCE = 1.0
MAX_WDDM_BYTES = 6000 * 1024 * 1024

EXPECTED_BRANCH_SHA256 = (
    "A454640FCAE18925F9A4B54672C0A1F681721E9CF72BC19220C940E64B629B12"
)
EXPECTED_SUFFIX_SHA256 = (
    "7A0CC84CF953A11BA7780E5660346598117372EB71F460CF8DA3B545E6499BA0"
)
EXPECTED_GENERATED_SHA256 = {
    "C": "BD33E852EF9FDDEE49A1056501456071169FF3E3C7699C2A5BAAA2D0DF30CABC",
    "D": "0CA13167369ED1835BB8938644A7CCEF6EDE0BD65AE31C256931C54D3FA9FB31",
    "B": "4553BBC00B6AF27C3EBDE8F36EA9237A37B5D9C1AA182FBC65CDA71411A4B888",
}
EXPECTED_CHILD_SHA256 = {
    "C": "1F956F9C177106F0775B3DAA054CA7BF046F980277C8E2CE6029AD78C7E90395",
    "D": "5AC4DD8C73E3D4958F9A93C3A9D78B05C0C6C4E6D17A06DA7CF8C72E10FA495B",
    "B": "D636ABA44A0F7DA74C1CA03CD2D0B064D6A2469FA6EBB0BC8F42A0CE9426DEB8",
}
EXPECTED_REQUEST_SHA256 = {
    "C": "5F80CECB28FC4336A9630C092A215F75C52EFFE03EBB8CECAE6D63832341B962",
    "D": "D7ACDEE41EDF7366F98154246E17A54CD13D4DB1830FB295CF8E02DB10D87862",
}

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


def create_consumed_marker(path: Path, expected_commit: str) -> dict[str, Any]:
    return terminal.write_exclusive_json(
        path,
        {
            "id": EXPERIMENT_ID,
            "attempt_id": ATTEMPT_ID,
            "expected_commit": expected_commit,
            "created_unix_ns": time.time_ns(),
            "meaning": "Task-A is next; neo-exp-0086 is scientifically consumed",
            "retry_allowed": False,
            "automatic_promotion": False,
        },
    )


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
    require(parsed["answer"] == harness.EXPECTED[ROOT_ID]["task_a"], "Task-A answer changed")
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
    require(len(branch_tokens) == EXPECTED_BRANCH_TOKENS, "branch token count changed")
    require(canonical_sha256(branch_tokens) == EXPECTED_BRANCH_SHA256, "branch identity changed")
    return task, branch_tokens, retained


def validate_device_root(
    response: Mapping[str, Any],
    *,
    action: str,
    root_id: str,
    n_tokens: int,
    n_device_bytes: int,
    terminal_logits: bool,
    expected_roots_after: int,
    expected_total_device_bytes_after: int,
    expected: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    record = rebase.validate_root(
        response,
        action=action,
        root_id=root_id,
        storage="device",
        expected=expected,
        expected_tokens=n_tokens,
        expected_roots_after=expected_roots_after,
        expected_total_device_bytes_after=expected_total_device_bytes_after,
        expected_root_capacity=5,
    )
    require(record["n_device_bytes"] == n_device_bytes, f"{root_id} device bytes changed")
    require(response.get("has_terminal_logits") is terminal_logits, f"{root_id} terminal flag changed")
    if terminal_logits:
        require(
            response.get("n_terminal_logits") == EXPECTED_TERMINAL_LOGITS,
            f"{root_id} terminal vocabulary changed",
        )
        require(
            response.get("n_terminal_logits_bytes") == EXPECTED_TERMINAL_LOGITS_BYTES,
            f"{root_id} terminal byte geometry changed",
        )
        require(response.get("terminal_position") == n_tokens - 1, f"{root_id} terminal position changed")
        for key in (
            "terminal_logits_fnv64",
            "terminal_prompt_fnv64",
            "terminal_sampler_fnv64",
        ):
            require(
                isinstance(response.get(key), str)
                and bool(re.fullmatch(r"[0-9a-f]{16}", str(response[key]))),
                f"{root_id} {key} changed",
            )
    else:
        require(response.get("n_terminal_logits") == 0, f"{root_id} retained terminal logits")
        require(response.get("n_terminal_logits_bytes") == 0, f"{root_id} terminal bytes changed")
        require(response.get("terminal_position") == -1, f"{root_id} terminal position changed")
    if expected is not None:
        for key in (
            "has_terminal_logits",
            "n_terminal_logits",
            "n_terminal_logits_bytes",
            "terminal_logits_fnv64",
            "terminal_prompt_fnv64",
            "terminal_sampler_fnv64",
            "terminal_position",
        ):
            require(response.get(key) == expected.get(key), f"{root_id} {key} drifted")
    record.update(
        has_terminal_logits=terminal_logits,
        n_terminal_logits=int(response["n_terminal_logits"]),
        n_terminal_logits_bytes=int(response["n_terminal_logits_bytes"]),
        terminal_logits_fnv64=str(response.get("terminal_logits_fnv64") or ""),
        terminal_prompt_fnv64=str(response.get("terminal_prompt_fnv64") or ""),
        terminal_sampler_fnv64=str(response.get("terminal_sampler_fnv64") or ""),
        terminal_position=int(response.get("terminal_position", -1)),
    )
    return record


def root_action(
    *,
    action: str,
    root_id: str,
    n_tokens: int,
    n_device_bytes: int,
    terminal_logits: bool,
    expected_roots_after: int,
    expected_total_device_bytes_after: int,
    expected: Mapping[str, Any] | None = None,
    include_terminal_logits: bool = False,
    require_terminal_logits: bool = False,
) -> dict[str, Any]:
    raw, wall = harness.ram_root_action(
        action=action,
        root_id=root_id,
        storage="device" if action == "root-save" else "default",
        include_terminal_logits=include_terminal_logits,
        require_terminal_logits=require_terminal_logits,
    )
    record = validate_device_root(
        raw,
        action=action,
        root_id=root_id,
        n_tokens=n_tokens,
        n_device_bytes=n_device_bytes,
        terminal_logits=terminal_logits,
        expected_roots_after=expected_roots_after,
        expected_total_device_bytes_after=expected_total_device_bytes_after,
        expected=expected,
    )
    record["client_wall_seconds"] = wall
    return record


def child_root_id(trial_label: str, route: str, generation: int) -> str:
    require(route in {"terminal", "root-only"}, "child route changed")
    require(generation in {0, 1, 2}, "child generation changed")
    return f"{EXPERIMENT_ID}-{trial_label}-{route}-child-{generation}"


def terminal_root_id(trial_label: str, edge: int) -> str:
    require(edge in {1, 2}, "terminal edge changed")
    return f"{EXPERIMENT_ID}-{trial_label}-terminal-edge-{edge}"


def derive_successor(
    *,
    codec: Any,
    child_tokens: Sequence[int],
    prior_state: Mapping[str, Any],
    edge: int,
    cache_prompt: bool,
) -> tuple[list[int], dict[str, Any], dict[str, Any]]:
    tokens, payload, ancestry = rolling.derive_promoted_successor(
        codec=codec,
        root_tokens=child_tokens,
        prior_state=prior_state,
        seed=shared_tasks.derive_seed(ROOT_ID, f"fixed-size-rebase-step-{edge}"),
        cache_prompt=cache_prompt,
        transition_content=fixed.transition_user_content(),
    )
    prior = EDGE_PRIORS[edge - 1]
    require(prior_state["answer"] == prior, f"edge {edge} prior state changed")
    require(len(tokens) == EXPECTED_SUCCESSOR_TOKENS, f"edge {edge} request count changed")
    require(
        ancestry["request_token_sha256"] == EXPECTED_REQUEST_SHA256[prior],
        f"edge {edge} request identity changed",
    )
    require(
        ancestry["suffix_token_count"] == EXPECTED_SUCCESSOR_FRESH_TOKENS
        and ancestry["suffix_token_sha256"] == EXPECTED_SUFFIX_SHA256,
        f"edge {edge} suffix identity changed",
    )
    return tokens, payload, ancestry


def validate_generated_state(
    record: Mapping[str, Any],
    *,
    codec: Any,
    props: Mapping[str, Any],
    expected_answer: str,
) -> dict[str, Any]:
    state = fixed.generated_state(record, codec=codec, props=props)
    require(state["answer"] == expected_answer, f"expected {expected_answer} output changed")
    require(
        state["generated_token_sha256"] == EXPECTED_GENERATED_SHA256[expected_answer],
        f"{expected_answer} generated identity changed",
    )
    return state


def consume_terminal(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    root: Mapping[str, Any],
    tokens: Sequence[int],
    payload: Mapping[str, Any],
    expected_answer: str,
    label: str,
) -> dict[str, Any]:
    restored = root_action(
        action="root-restore",
        root_id=str(root["root_id"]),
        n_tokens=EXPECTED_SUCCESSOR_TOKENS,
        n_device_bytes=EXPECTED_SUCCESSOR_TERMINAL_DEVICE_BYTES,
        terminal_logits=True,
        expected_roots_after=3,
        expected_total_device_bytes_after=EXPECTED_MAX_PIPELINE_DEVICE_BYTES,
        expected=root,
        require_terminal_logits=True,
    )
    request_payload = dict(payload)
    request_payload.update(
        neo3000_use_terminal_logits=True,
        neo3000_terminal_root_id=root["root_id"],
        neo3000_terminal_logits_fnv64=root["terminal_logits_fnv64"],
    )
    recorder = latency.TimingRecorder()
    record = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:{label}:consumer",
        request_payload,
        recorder=recorder,
        batch_owned_request=True,
    )
    timing = recorder.summary(request_wall_seconds=float(record["wall_seconds"]))
    require(
        record["prompt_tokens"] == EXPECTED_SUCCESSOR_TOKENS
        and record["cached_prompt_tokens"] == EXPECTED_SUCCESSOR_TOKENS
        and record["fresh_prompt_tokens"] == 0,
        "terminal consumer geometry changed",
    )
    require(timing["server_prompt_n"] == 0, "terminal consumer prompt timing changed")
    state = validate_generated_state(
        record,
        codec=codec,
        props=props,
        expected_answer=expected_answer,
    )
    record.update(
        route="terminal",
        state=state,
        timing=timing,
        restore=restored,
        restore_client_wall_seconds=float(restored["client_wall_seconds"]),
        restore_inclusive_ttft_seconds=(
            float(restored["client_wall_seconds"])
            + float(timing["ttft_seconds"])
        ),
        effective_wall_seconds=(
            float(restored["client_wall_seconds"])
            + float(record["wall_seconds"])
        ),
        input_token_sha256=canonical_sha256(list(tokens)),
    )
    return record


def run_root_only_successor(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    child_root: Mapping[str, Any],
    child_tokens: Sequence[int],
    prior_state: Mapping[str, Any],
    edge: int,
    label: str,
) -> dict[str, Any]:
    restored = root_action(
        action="root-restore",
        root_id=str(child_root["root_id"]),
        n_tokens=EXPECTED_CHILD_TOKENS,
        n_device_bytes=EXPECTED_CHILD_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=2,
        expected_total_device_bytes_after=EXPECTED_BASE_CHILD_DEVICE_BYTES,
        expected=child_root,
    )
    tokens, payload, ancestry = derive_successor(
        codec=codec,
        child_tokens=child_tokens,
        prior_state=prior_state,
        edge=edge,
        cache_prompt=True,
    )
    recorder = latency.TimingRecorder()
    record = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:{label}:root-only",
        payload,
        recorder=recorder,
        batch_owned_request=True,
    )
    timing = recorder.summary(request_wall_seconds=float(record["wall_seconds"]))
    require(
        record["cached_prompt_tokens"] == EXPECTED_CHILD_TOKENS
        and record["fresh_prompt_tokens"] == EXPECTED_SUCCESSOR_FRESH_TOKENS,
        "root-only successor geometry changed",
    )
    require(
        timing["server_prompt_n"] == EXPECTED_SUCCESSOR_FRESH_TOKENS,
        "root-only prompt timing changed",
    )
    state = validate_generated_state(
        record,
        codec=codec,
        props=props,
        expected_answer=EDGE_SUCCESSORS[edge - 1],
    )
    record.update(
        route="root-only",
        state=state,
        ancestry=ancestry,
        timing=timing,
        restore=restored,
        restore_client_wall_seconds=float(restored["client_wall_seconds"]),
        restore_inclusive_ttft_seconds=(
            float(restored["client_wall_seconds"])
            + float(timing["ttft_seconds"])
        ),
        effective_wall_seconds=(
            float(restored["client_wall_seconds"])
            + float(record["wall_seconds"])
        ),
        input_token_sha256=ancestry["request_token_sha256"],
    )
    return record


def run_direct_successor(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    child_tokens: Sequence[int],
    prior_state: Mapping[str, Any],
    edge: int,
    label: str,
) -> dict[str, Any]:
    tokens, payload, ancestry = derive_successor(
        codec=codec,
        child_tokens=child_tokens,
        prior_state=prior_state,
        edge=edge,
        cache_prompt=False,
    )
    recorder = latency.TimingRecorder()
    record = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:{label}:materialized",
        payload,
        recorder=recorder,
        batch_owned_request=True,
    )
    timing = recorder.summary(request_wall_seconds=float(record["wall_seconds"]))
    require(
        record["cached_prompt_tokens"] == 0
        and record["fresh_prompt_tokens"] == EXPECTED_SUCCESSOR_TOKENS,
        "materialized successor geometry changed",
    )
    state = validate_generated_state(
        record,
        codec=codec,
        props=props,
        expected_answer=EDGE_SUCCESSORS[edge - 1],
    )
    record.update(
        route="materialized",
        state=state,
        ancestry=ancestry,
        timing=timing,
        restore_inclusive_ttft_seconds=float(timing["ttft_seconds"]),
        effective_wall_seconds=float(record["wall_seconds"]),
        input_token_sha256=ancestry["request_token_sha256"],
    )
    return record


def materialize_child(
    *,
    sidecar: Any,
    base_root: Mapping[str, Any],
    branch_tokens: Sequence[int],
    state: Mapping[str, Any],
    root_id: str,
    label: str,
) -> tuple[dict[str, Any], list[int], dict[str, Any]]:
    restored = root_action(
        action="root-restore",
        root_id=BASE_ROOT_ID,
        n_tokens=EXPECTED_BASE_TOKENS,
        n_device_bytes=EXPECTED_BASE_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=1,
        expected_total_device_bytes_after=EXPECTED_BASE_DEVICE_BYTES,
        expected=base_root,
    )
    child_tokens = rebase.compact_child_tokens(branch_tokens, state)
    answer = str(state["answer"])
    require(canonical_sha256(child_tokens) == EXPECTED_CHILD_SHA256[answer], "child hash changed")
    payload = harness.carrier._branch_payload(
        child_tokens,
        seed=shared_tasks.derive_seed(ROOT_ID, f"{label}:materialize-child"),
        cache_prompt=True,
        n_predict=0,
    )
    materialized = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:{label}:materialize-child",
        payload,
        operation_kind="zero-output-root-readdress",
        batch_owned_request=True,
    )
    require(
        materialized["prompt_tokens"] == EXPECTED_CHILD_TOKENS
        and materialized["cached_prompt_tokens"] == EXPECTED_BASE_TOKENS
        and materialized["fresh_prompt_tokens"] == EXPECTED_REBASE_FRESH_TOKENS
        and materialized["completion_tokens"] == 0,
        "child rebase geometry changed",
    )
    saved = root_action(
        action="root-save",
        root_id=root_id,
        n_tokens=EXPECTED_CHILD_TOKENS,
        n_device_bytes=EXPECTED_CHILD_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=2,
        expected_total_device_bytes_after=EXPECTED_BASE_CHILD_DEVICE_BYTES,
    )
    lifecycle = {
        "base_restore": restored,
        "materialization": harness.token_summary(materialized),
        "materialization_wall_seconds": float(materialized["wall_seconds"]),
        "child_save": saved,
        "wall_seconds": (
            float(restored["client_wall_seconds"])
            + float(materialized["wall_seconds"])
            + float(saved["client_wall_seconds"])
        ),
        "fresh_prompt_tokens": EXPECTED_REBASE_FRESH_TOKENS,
    }
    return saved, child_tokens, lifecycle


def erase_child(
    child: Mapping[str, Any],
    *,
    expected_roots_after: int = 1,
    expected_total_device_bytes_after: int = EXPECTED_BASE_DEVICE_BYTES,
) -> dict[str, Any]:
    return root_action(
        action="root-erase",
        root_id=str(child["root_id"]),
        n_tokens=EXPECTED_CHILD_TOKENS,
        n_device_bytes=EXPECTED_CHILD_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=expected_roots_after,
        expected_total_device_bytes_after=expected_total_device_bytes_after,
        expected=child,
    )


def run_terminal_sequence(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    base_root: Mapping[str, Any],
    branch_tokens: Sequence[int],
    seed_state: Mapping[str, Any],
    trial_label: str,
    baseline_private: int | None,
    run_successor_negative: bool,
) -> dict[str, Any]:
    child, child_tokens, reset = materialize_child(
        sidecar=sidecar,
        base_root=base_root,
        branch_tokens=branch_tokens,
        state=seed_state,
        root_id=child_root_id(trial_label, "terminal", 0),
        label=f"{trial_label}:terminal:initial",
    )
    prior_state = dict(seed_state)
    edges: list[dict[str, Any]] = []
    total_wall = 0.0
    total_fresh = 0
    terminal_prompt_digests: list[str] = []
    terminal_root_ids: list[str] = []
    negative: dict[str, Any] | None = None
    max_resources: list[dict[str, Any]] = []

    for edge in (1, 2):
        restored_child = root_action(
            action="root-restore",
            root_id=str(child["root_id"]),
            n_tokens=EXPECTED_CHILD_TOKENS,
            n_device_bytes=EXPECTED_CHILD_DEVICE_BYTES,
            terminal_logits=False,
            expected_roots_after=2,
            expected_total_device_bytes_after=EXPECTED_BASE_CHILD_DEVICE_BYTES,
            expected=child,
        )
        tokens, payload, ancestry = derive_successor(
            codec=codec,
            child_tokens=child_tokens,
            prior_state=prior_state,
            edge=edge,
            cache_prompt=True,
        )
        capture_payload = dict(payload)
        capture_payload["n_predict"] = 0
        capture_payload["neo3000_capture_terminal_logits"] = True
        capture = harness.run_completion(
            sidecar,
            f"{EXPERIMENT_ID}:{trial_label}:terminal:edge-{edge}:capture",
            capture_payload,
            operation_kind="zero-output-root-readdress",
            batch_owned_request=True,
        )
        require(
            capture["prompt_tokens"] == EXPECTED_SUCCESSOR_TOKENS
            and capture["cached_prompt_tokens"] == EXPECTED_CHILD_TOKENS
            and capture["fresh_prompt_tokens"] == EXPECTED_SUCCESSOR_FRESH_TOKENS
            and capture["completion_tokens"] == 0,
            f"terminal edge {edge} capture geometry changed",
        )
        root_id = terminal_root_id(trial_label, edge)
        terminal_saved = root_action(
            action="root-save",
            root_id=root_id,
            n_tokens=EXPECTED_SUCCESSOR_TOKENS,
            n_device_bytes=EXPECTED_SUCCESSOR_TERMINAL_DEVICE_BYTES,
            terminal_logits=True,
            expected_roots_after=3,
            expected_total_device_bytes_after=EXPECTED_MAX_PIPELINE_DEVICE_BYTES,
            include_terminal_logits=True,
        )
        max_resources.append(harness.process_resources(sidecar, baseline_private))
        terminal_prompt_digests.append(str(terminal_saved["terminal_prompt_fnv64"]))
        terminal_root_ids.append(root_id)
        if run_successor_negative and edge == 1:
            mismatch = dict(payload)
            mismatch.update(
                neo3000_use_terminal_logits=True,
                neo3000_terminal_root_id=root_id,
                neo3000_terminal_logits_fnv64="0" * 16,
            )
            negative = terminal.expect_http_error(
                f"http://127.0.0.1:{harness.live_runtime.PORT}/completion",
                mismatch,
                "Terminal-logits continuation identity mismatch",
            )
        consumer = consume_terminal(
            sidecar=sidecar,
            codec=codec,
            props=props,
            root=terminal_saved,
            tokens=tokens,
            payload=payload,
            expected_answer=EDGE_SUCCESSORS[edge - 1],
            label=f"{trial_label}:terminal:edge-{edge}",
        )
        terminal_erased = root_action(
            action="root-erase",
            root_id=root_id,
            n_tokens=EXPECTED_SUCCESSOR_TOKENS,
            n_device_bytes=EXPECTED_SUCCESSOR_TERMINAL_DEVICE_BYTES,
            terminal_logits=True,
            expected_roots_after=2,
            expected_total_device_bytes_after=EXPECTED_BASE_CHILD_DEVICE_BYTES,
            expected=terminal_saved,
        )
        child_erased = erase_child(child)
        next_child, next_child_tokens, rebase_lifecycle = materialize_child(
            sidecar=sidecar,
            base_root=base_root,
            branch_tokens=branch_tokens,
            state=consumer["state"],
            root_id=child_root_id(trial_label, "terminal", edge),
            label=f"{trial_label}:terminal:edge-{edge}:next",
        )
        edge_wall = (
            float(restored_child["client_wall_seconds"])
            + float(capture["wall_seconds"])
            + float(terminal_saved["client_wall_seconds"])
            + float(consumer["effective_wall_seconds"])
            + float(terminal_erased["client_wall_seconds"])
            + float(child_erased["client_wall_seconds"])
            + float(rebase_lifecycle["wall_seconds"])
        )
        total_wall += edge_wall
        total_fresh += (
            EXPECTED_SUCCESSOR_FRESH_TOKENS + EXPECTED_REBASE_FRESH_TOKENS
        )
        edges.append(
            {
                "edge": edge,
                "transition": f"{EDGE_PRIORS[edge - 1]}->{EDGE_SUCCESSORS[edge - 1]}",
                "child_root": child,
                "child_token_sha256": canonical_sha256(child_tokens),
                "child_restore": restored_child,
                "ancestry": ancestry,
                "capture": harness.token_summary(capture),
                "capture_wall_seconds": float(capture["wall_seconds"]),
                "terminal_root": terminal_saved,
                "consumer": consumer,
                "terminal_erase": terminal_erased,
                "child_erase": child_erased,
                "next_child": next_child,
                "next_child_token_sha256": canonical_sha256(next_child_tokens),
                "rebase": rebase_lifecycle,
                "fully_charged_edge_wall_seconds": edge_wall,
                "fully_charged_edge_fresh_prompt_tokens": (
                    EXPECTED_SUCCESSOR_FRESH_TOKENS
                    + EXPECTED_REBASE_FRESH_TOKENS
                ),
                "consumer_count": 1,
            }
        )
        child = next_child
        child_tokens = next_child_tokens
        prior_state = consumer["state"]

    final_erase = erase_child(child)
    total_wall += float(final_erase["client_wall_seconds"])
    require(prior_state["answer"] == "B", "terminal sequence final state changed")
    return {
        "route": "terminal",
        "trial_label": trial_label,
        "initial_child_reset": reset,
        "edges": edges,
        "observed_states": [
            str(seed_state["answer"]),
            *[str(edge_record["consumer"]["state"]["answer"]) for edge_record in edges],
        ],
        "terminal_root_ids": terminal_root_ids,
        "terminal_prompt_digests": terminal_prompt_digests,
        "successor_negative": negative,
        "resources_with_three_roots": max_resources,
        "final_child_erase": final_erase,
        "fully_charged_wall_seconds": total_wall,
        "fully_charged_fresh_prompt_tokens": total_fresh,
    }


def run_root_only_sequence(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    base_root: Mapping[str, Any],
    branch_tokens: Sequence[int],
    seed_state: Mapping[str, Any],
    trial_label: str,
) -> dict[str, Any]:
    child, child_tokens, reset = materialize_child(
        sidecar=sidecar,
        base_root=base_root,
        branch_tokens=branch_tokens,
        state=seed_state,
        root_id=child_root_id(trial_label, "root-only", 0),
        label=f"{trial_label}:root-only:initial",
    )
    prior_state = dict(seed_state)
    edges: list[dict[str, Any]] = []
    total_wall = 0.0
    total_fresh = 0
    for edge in (1, 2):
        successor = run_root_only_successor(
            sidecar=sidecar,
            codec=codec,
            props=props,
            child_root=child,
            child_tokens=child_tokens,
            prior_state=prior_state,
            edge=edge,
            label=f"{trial_label}:edge-{edge}",
        )
        child_erased = erase_child(child)
        next_child, next_child_tokens, rebase_lifecycle = materialize_child(
            sidecar=sidecar,
            base_root=base_root,
            branch_tokens=branch_tokens,
            state=successor["state"],
            root_id=child_root_id(trial_label, "root-only", edge),
            label=f"{trial_label}:root-only:edge-{edge}:next",
        )
        edge_wall = (
            float(successor["effective_wall_seconds"])
            + float(child_erased["client_wall_seconds"])
            + float(rebase_lifecycle["wall_seconds"])
        )
        total_wall += edge_wall
        total_fresh += (
            EXPECTED_SUCCESSOR_FRESH_TOKENS + EXPECTED_REBASE_FRESH_TOKENS
        )
        edges.append(
            {
                "edge": edge,
                "transition": f"{EDGE_PRIORS[edge - 1]}->{EDGE_SUCCESSORS[edge - 1]}",
                "child_root": child,
                "child_token_sha256": canonical_sha256(child_tokens),
                "successor": successor,
                "child_erase": child_erased,
                "next_child": next_child,
                "next_child_token_sha256": canonical_sha256(next_child_tokens),
                "rebase": rebase_lifecycle,
                "fully_charged_edge_wall_seconds": edge_wall,
                "fully_charged_edge_fresh_prompt_tokens": (
                    EXPECTED_SUCCESSOR_FRESH_TOKENS
                    + EXPECTED_REBASE_FRESH_TOKENS
                ),
            }
        )
        child = next_child
        child_tokens = next_child_tokens
        prior_state = successor["state"]
    final_erase = erase_child(child)
    total_wall += float(final_erase["client_wall_seconds"])
    require(prior_state["answer"] == "B", "root-only sequence final state changed")
    return {
        "route": "root-only",
        "trial_label": trial_label,
        "initial_child_reset": reset,
        "edges": edges,
        "observed_states": [
            str(seed_state["answer"]),
            *[str(edge_record["successor"]["state"]["answer"]) for edge_record in edges],
        ],
        "final_child_erase": final_erase,
        "fully_charged_wall_seconds": total_wall,
        "fully_charged_fresh_prompt_tokens": total_fresh,
    }


def run_materialized_sequence(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    branch_tokens: Sequence[int],
    seed_state: Mapping[str, Any],
    trial_label: str,
) -> dict[str, Any]:
    prior_state = dict(seed_state)
    child_tokens = rebase.compact_child_tokens(branch_tokens, prior_state)
    edges: list[dict[str, Any]] = []
    total_wall = 0.0
    total_fresh = 0
    for edge in (1, 2):
        successor = run_direct_successor(
            sidecar=sidecar,
            codec=codec,
            props=props,
            child_tokens=child_tokens,
            prior_state=prior_state,
            edge=edge,
            label=f"{trial_label}:edge-{edge}",
        )
        next_child_tokens = rebase.compact_child_tokens(
            branch_tokens,
            successor["state"],
        )
        require(
            canonical_sha256(next_child_tokens)
            == EXPECTED_CHILD_SHA256[EDGE_SUCCESSORS[edge - 1]],
            "materialized next-child identity changed",
        )
        edge_wall = float(successor["effective_wall_seconds"])
        total_wall += edge_wall
        total_fresh += EXPECTED_SUCCESSOR_TOKENS
        edges.append(
            {
                "edge": edge,
                "transition": f"{EDGE_PRIORS[edge - 1]}->{EDGE_SUCCESSORS[edge - 1]}",
                "child_token_sha256": canonical_sha256(child_tokens),
                "successor": successor,
                "next_child_token_sha256": canonical_sha256(next_child_tokens),
                "fully_charged_edge_wall_seconds": edge_wall,
                "fully_charged_edge_fresh_prompt_tokens": EXPECTED_SUCCESSOR_TOKENS,
            }
        )
        prior_state = successor["state"]
        child_tokens = next_child_tokens
    require(prior_state["answer"] == "B", "materialized sequence final state changed")
    return {
        "route": "materialized",
        "trial_label": trial_label,
        "edges": edges,
        "observed_states": [
            str(seed_state["answer"]),
            *[str(edge_record["successor"]["state"]["answer"]) for edge_record in edges],
        ],
        "fully_charged_wall_seconds": total_wall,
        "fully_charged_fresh_prompt_tokens": total_fresh,
    }


def run_sequence(
    route: str,
    **kwargs: Any,
) -> dict[str, Any]:
    if route == "terminal":
        return run_terminal_sequence(**kwargs)
    terminal_only = {
        key: value
        for key, value in kwargs.items()
        if key not in {"baseline_private", "run_successor_negative"}
    }
    if route == "root-only":
        return run_root_only_sequence(**terminal_only)
    if route == "materialized":
        direct_only = {
            key: value
            for key, value in terminal_only.items()
            if key not in {"base_root"}
        }
        return run_materialized_sequence(**direct_only)
    raise ExperimentError(f"unsupported route: {route}")


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


def evaluate(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    prepared: Mapping[str, Any],
    baseline_private: int | None,
) -> dict[str, Any]:
    task, branch_tokens, retained = task_and_branch(sidecar, codec, props, prepared)
    base_tokens = list(branch_tokens[:EXPECTED_BASE_TOKENS])
    base_materialization = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:base-materialize",
        terminal.completion_payload(base_tokens, cache_prompt=False, n_predict=0),
        operation_kind="zero-output-root-readdress",
    )
    require(
        base_materialization["cached_prompt_tokens"] == 0
        and base_materialization["fresh_prompt_tokens"] == EXPECTED_BASE_TOKENS,
        "base materialization geometry changed",
    )
    base_root = root_action(
        action="root-save",
        root_id=BASE_ROOT_ID,
        n_tokens=EXPECTED_BASE_TOKENS,
        n_device_bytes=EXPECTED_BASE_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=1,
        expected_total_device_bytes_after=EXPECTED_BASE_DEVICE_BYTES,
    )

    base_restore = root_action(
        action="root-restore",
        root_id=BASE_ROOT_ID,
        n_tokens=EXPECTED_BASE_TOKENS,
        n_device_bytes=EXPECTED_BASE_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=1,
        expected_total_device_bytes_after=EXPECTED_BASE_DEVICE_BYTES,
        expected=base_root,
    )
    seed_capture_payload = terminal.completion_payload(
        branch_tokens,
        cache_prompt=True,
        n_predict=0,
    )
    seed_capture_payload["neo3000_capture_terminal_logits"] = True
    seed_capture = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:seed-terminal-capture",
        seed_capture_payload,
        operation_kind="zero-output-root-readdress",
    )
    require(
        seed_capture["cached_prompt_tokens"] == EXPECTED_BASE_TOKENS
        and seed_capture["fresh_prompt_tokens"] == 1
        and seed_capture["completion_tokens"] == 0,
        "seed terminal capture geometry changed",
    )
    seed_terminal = root_action(
        action="root-save",
        root_id=SEED_TERMINAL_ROOT_ID,
        n_tokens=EXPECTED_BRANCH_TOKENS,
        n_device_bytes=EXPECTED_SEED_TERMINAL_DEVICE_BYTES,
        terminal_logits=True,
        expected_roots_after=2,
        expected_total_device_bytes_after=(
            EXPECTED_BASE_DEVICE_BYTES + EXPECTED_SEED_TERMINAL_DEVICE_BYTES
        ),
        include_terminal_logits=True,
    )
    missing_terminal = terminal.expect_http_error(
        f"http://127.0.0.1:{harness.live_runtime.PORT}/slots/0?action=root-restore",
        {"root_id": BASE_ROOT_ID, "require_terminal_logits": True},
        "RAM root has no exact terminal-logits boundary",
    )
    seed_restore = root_action(
        action="root-restore",
        root_id=SEED_TERMINAL_ROOT_ID,
        n_tokens=EXPECTED_BRANCH_TOKENS,
        n_device_bytes=EXPECTED_SEED_TERMINAL_DEVICE_BYTES,
        terminal_logits=True,
        expected_roots_after=2,
        expected_total_device_bytes_after=(
            EXPECTED_BASE_DEVICE_BYTES + EXPECTED_SEED_TERMINAL_DEVICE_BYTES
        ),
        expected=seed_terminal,
        require_terminal_logits=True,
    )
    seed_payload = terminal.completion_payload(branch_tokens, cache_prompt=True)
    seed_payload.update(
        neo3000_use_terminal_logits=True,
        neo3000_terminal_root_id=SEED_TERMINAL_ROOT_ID,
        neo3000_terminal_logits_fnv64=seed_terminal["terminal_logits_fnv64"],
    )
    seed_recorder = latency.TimingRecorder()
    seed_record = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:seed-terminal-consumer",
        seed_payload,
        recorder=seed_recorder,
        batch_owned_request=True,
    )
    seed_timing = seed_recorder.summary(
        request_wall_seconds=float(seed_record["wall_seconds"])
    )
    require(
        seed_record["cached_prompt_tokens"] == EXPECTED_BRANCH_TOKENS
        and seed_record["fresh_prompt_tokens"] == 0,
        "seed terminal consumer geometry changed",
    )
    seed_state = validate_generated_state(
        seed_record,
        codec=codec,
        props=props,
        expected_answer="C",
    )
    lineage_child_tokens = rebase.compact_child_tokens(branch_tokens, seed_state)
    require(
        canonical_sha256(lineage_child_tokens) == EXPECTED_CHILD_SHA256["C"],
        "seed lineage child identity changed",
    )
    lineage_child = root_action(
        action="root-save",
        root_id=f"{EXPERIMENT_ID}-lineage-child-C",
        n_tokens=EXPECTED_CHILD_TOKENS,
        n_device_bytes=EXPECTED_CHILD_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=3,
        expected_total_device_bytes_after=EXPECTED_SETUP_THREE_ROOT_DEVICE_BYTES,
    )
    setup_resources = harness.process_resources(sidecar, baseline_private)
    missing_successor_terminal = terminal.expect_http_error(
        f"http://127.0.0.1:{harness.live_runtime.PORT}/slots/0?action=root-restore",
        {
            "root_id": lineage_child["root_id"],
            "require_terminal_logits": True,
        },
        "RAM root has no exact terminal-logits boundary",
    )
    lineage_child_erased = root_action(
        action="root-erase",
        root_id=str(lineage_child["root_id"]),
        n_tokens=EXPECTED_CHILD_TOKENS,
        n_device_bytes=EXPECTED_CHILD_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=2,
        expected_total_device_bytes_after=(
            EXPECTED_BASE_DEVICE_BYTES + EXPECTED_SEED_TERMINAL_DEVICE_BYTES
        ),
        expected=lineage_child,
    )
    seed_terminal_erased = root_action(
        action="root-erase",
        root_id=SEED_TERMINAL_ROOT_ID,
        n_tokens=EXPECTED_BRANCH_TOKENS,
        n_device_bytes=EXPECTED_SEED_TERMINAL_DEVICE_BYTES,
        terminal_logits=True,
        expected_roots_after=1,
        expected_total_device_bytes_after=EXPECTED_BASE_DEVICE_BYTES,
        expected=seed_terminal,
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

    ownership_boundary("pre-successor-terminal-pipeline-batch")
    common_kwargs = {
        "sidecar": sidecar,
        "codec": codec,
        "props": props,
        "base_root": base_root,
        "branch_tokens": branch_tokens,
        "seed_state": seed_state,
        "baseline_private": baseline_private,
    }
    warmup: dict[str, dict[str, Any]] = {}
    for route in ROUTES:
        warmup[route] = run_sequence(
            route,
            **common_kwargs,
            trial_label=f"warmup-{route}",
            run_successor_negative=route == "terminal",
        )

    counted: list[dict[str, Any]] = []
    for trial, order in enumerate(TRIAL_ROUTE_ORDERS, start=1):
        routes: dict[str, dict[str, Any]] = {}
        for route in order:
            routes[route] = run_sequence(
                route,
                **common_kwargs,
                trial_label=f"trial-{trial}-{route}",
                run_successor_negative=False,
            )
        counted.append(
            {
                "trial": trial,
                "route_order": list(order),
                "routes": routes,
            }
        )
    ownership_boundary("post-successor-terminal-pipeline-batch")
    tool_canary = run_tool_canary(sidecar)

    base_erased = root_action(
        action="root-erase",
        root_id=BASE_ROOT_ID,
        n_tokens=EXPECTED_BASE_TOKENS,
        n_device_bytes=EXPECTED_BASE_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=0,
        expected_total_device_bytes_after=0,
        expected=base_root,
    )
    require(
        base_erased["n_total_bytes_after"] == 0
        and base_erased["n_total_device_bytes_after"] == 0
        and base_erased["n_total_gpu_bytes_after"] == 0,
        "root bank did not close",
    )
    resources_after_erase = harness.process_resources(sidecar, baseline_private)

    ownership_total = sum(float(item["client_wall_seconds"]) for item in ownership)
    ownership_share = ownership_total / (COUNTED_TRIALS * len(ROUTES))
    for trial in counted:
        for route in ROUTES:
            trial["routes"][route]["batch_ownership_amortized_seconds"] = ownership_share
            trial["routes"][route]["fully_charged_wall_seconds"] += ownership_share

    terminal_walls = [
        float(trial["routes"]["terminal"]["fully_charged_wall_seconds"])
        for trial in counted
    ]
    root_walls = [
        float(trial["routes"]["root-only"]["fully_charged_wall_seconds"])
        for trial in counted
    ]
    direct_walls = [
        float(trial["routes"]["materialized"]["fully_charged_wall_seconds"])
        for trial in counted
    ]
    terminal_ttft = [
        float(edge["consumer"]["restore_inclusive_ttft_seconds"])
        for trial in counted
        for edge in trial["routes"]["terminal"]["edges"]
    ]
    root_ttft = [
        float(edge["successor"]["restore_inclusive_ttft_seconds"])
        for trial in counted
        for edge in trial["routes"]["root-only"]["edges"]
    ]
    require(len(terminal_ttft) == len(root_ttft) == COUNTED_TRIALS * 2, "TTFT sample count changed")
    ttft_speedup = sum(root_ttft) / sum(terminal_ttft)
    ttft_dominance = sum(
        terminal_value < root_value
        for terminal_value, root_value in zip(terminal_ttft, root_ttft)
    ) / len(terminal_ttft)
    terminal_vs_materialized = sum(direct_walls) / sum(terminal_walls)
    terminal_vs_root = sum(root_walls) / sum(terminal_walls)

    all_terminal = [
        warmup["terminal"],
        *[trial["routes"]["terminal"] for trial in counted],
    ]
    terminal_prompt_digest_pairs = [
        tuple(route["terminal_prompt_digests"])
        for route in all_terminal
    ]
    terminal_root_ids = [
        root_id
        for route in all_terminal
        for root_id in route["terminal_root_ids"]
    ]
    all_routes = [
        warmup[route]
        for route in ROUTES
    ] + [
        trial["routes"][route]
        for trial in counted
        for route in ROUTES
    ]
    all_route_edges = [
        (route, edge)
        for route in all_routes
        for edge in route["edges"]
    ]

    log_text = Path(str(sidecar.readiness["log_path"])).read_text(
        encoding="utf-8",
        errors="replace",
    )
    capture_markers = log_text.count("neo3000 terminal-logits boundary captured")
    sample_markers = log_text.count(
        "neo3000 terminal-logits continuation sampled before decode"
    )
    full_reprocess_markers = log_text.count("forcing full prompt re-processing")
    expected_terminal_sequences = WARMUP_TRIALS + COUNTED_TRIALS
    expected_capture_markers = 1 + expected_terminal_sequences * 2
    expected_sample_markers = 1 + expected_terminal_sequences * 2

    gates = {
        "task_a_correct": (
            harness.carrier.parse_task_a_output(task["content"])["answer"]
            == harness.EXPECTED[ROOT_ID]["task_a"]
        ),
        "seed_terminal_lineage_exact": (
            seed_record["cached_prompt_tokens"] == EXPECTED_BRANCH_TOKENS
            and seed_record["fresh_prompt_tokens"] == 0
            and seed_state["generated_token_sha256"] == EXPECTED_GENERATED_SHA256["C"]
            and canonical_sha256(lineage_child_tokens) == EXPECTED_CHILD_SHA256["C"]
        ),
        "all_route_state_sequences_C_D_B_exact": all(
            route["observed_states"] == list(EXPECTED_STATES)
            for route in all_routes
        ),
        "all_request_and_generated_identities_exact": all(
            edge["child_token_sha256"] == EXPECTED_CHILD_SHA256[EDGE_PRIORS[edge["edge"] - 1]]
            and edge["next_child_token_sha256"]
            == EXPECTED_CHILD_SHA256[EDGE_SUCCESSORS[edge["edge"] - 1]]
            and (
                (
                    route["route"] == "terminal"
                    and edge["ancestry"]["request_token_sha256"]
                    == EXPECTED_REQUEST_SHA256[EDGE_PRIORS[edge["edge"] - 1]]
                    and edge["consumer"]["state"]["generated_token_sha256"]
                    == EXPECTED_GENERATED_SHA256[EDGE_SUCCESSORS[edge["edge"] - 1]]
                )
                or (
                    route["route"] != "terminal"
                    and edge["successor"]["ancestry"]["request_token_sha256"]
                    == EXPECTED_REQUEST_SHA256[EDGE_PRIORS[edge["edge"] - 1]]
                    and edge["successor"]["state"]["generated_token_sha256"]
                    == EXPECTED_GENERATED_SHA256[EDGE_SUCCESSORS[edge["edge"] - 1]]
                )
            )
            for route, edge in all_route_edges
        ),
        "terminal_consumers_782_cached_0_fresh": all(
            edge["consumer"]["cached_prompt_tokens"] == EXPECTED_SUCCESSOR_TOKENS
            and edge["consumer"]["fresh_prompt_tokens"] == 0
            for route in all_terminal
            for edge in route["edges"]
        ),
        "root_only_successors_695_cached_87_fresh": all(
            edge["successor"]["cached_prompt_tokens"] == EXPECTED_CHILD_TOKENS
            and edge["successor"]["fresh_prompt_tokens"]
            == EXPECTED_SUCCESSOR_FRESH_TOKENS
            for route in [
                warmup["root-only"],
                *[trial["routes"]["root-only"] for trial in counted],
            ]
            for edge in route["edges"]
        ),
        "materialized_successors_0_cached_782_fresh": all(
            edge["successor"]["cached_prompt_tokens"] == 0
            and edge["successor"]["fresh_prompt_tokens"] == EXPECTED_SUCCESSOR_TOKENS
            for route in [
                warmup["materialized"],
                *[trial["routes"]["materialized"] for trial in counted],
            ]
            for edge in route["edges"]
        ),
        "rebase_689_cached_6_fresh_each_terminal_and_root_edge": all(
            edge["rebase"]["materialization"]["cached_prompt_tokens"]
            == EXPECTED_BASE_TOKENS
            and edge["rebase"]["materialization"]["fresh_prompt_tokens"]
            == EXPECTED_REBASE_FRESH_TOKENS
            for route in all_routes
            if route["route"] != "materialized"
            for edge in route["edges"]
        ),
        "charged_fresh_law_186_186_1564_each_trial": all(
            trial["routes"]["terminal"]["fully_charged_fresh_prompt_tokens"] == 186
            and trial["routes"]["root-only"]["fully_charged_fresh_prompt_tokens"] == 186
            and trial["routes"]["materialized"]["fully_charged_fresh_prompt_tokens"] == 1564
            for trial in counted
        ),
        "counted_avoided_fresh_prompt_tokens_4134": (
            COUNTED_TRIALS * EXPECTED_AVOIDED_PER_TRIAL == 4_134
        ),
        "two_unique_descendant_terminal_prompt_digests": (
            all(len(pair) == 2 and pair[0] != pair[1] for pair in terminal_prompt_digest_pairs)
            and len({pair[0] for pair in terminal_prompt_digest_pairs}) == 1
            and len({pair[1] for pair in terminal_prompt_digest_pairs}) == 1
        ),
        "one_consumer_per_unique_terminal_root": (
            len(terminal_root_ids) == len(set(terminal_root_ids))
            and all(
                edge["consumer_count"] == 1
                for route in all_terminal
                for edge in route["edges"]
            )
        ),
        "consumer_ttft_speedup_at_least_5": ttft_speedup >= MIN_CONSUMER_TTFT_SPEEDUP,
        "consumer_ttft_terminal_wins_all_edges": (
            ttft_dominance >= MIN_CONSUMER_TTFT_DOMINANCE
        ),
        "terminal_vs_materialized_fully_charged_speedup_at_least_2_5": (
            terminal_vs_materialized
            >= MIN_TERMINAL_VS_MATERIALIZED_WALL_SPEEDUP
        ),
        "terminal_vs_root_only_fully_charged_ratio_at_least_0_80": (
            terminal_vs_root >= MIN_TERMINAL_VS_ROOT_ONLY_WALL_RATIO
        ),
        "capture_marker_count_exact": capture_markers == expected_capture_markers,
        "sample_marker_count_exact": sample_markers == expected_sample_markers,
        "zero_full_reprocess_markers": full_reprocess_markers == 0,
        "missing_seed_terminal_rejected": missing_terminal["http_status"] == 400,
        "missing_successor_terminal_rejected": (
            missing_successor_terminal["http_status"] == 400
        ),
        "mismatched_successor_terminal_rejected": (
            warmup["terminal"]["successor_negative"] is not None
            and warmup["terminal"]["successor_negative"]["http_status"] == 400
        ),
        "maximum_three_pipeline_roots_and_device_bytes_exact": all(
            edge["terminal_root"]["n_roots_after"] == 3
            and edge["terminal_root"]["n_total_device_bytes_after"]
            == EXPECTED_MAX_PIPELINE_DEVICE_BYTES
            for route in all_terminal
            for edge in route["edges"]
        ),
        "wddm_at_or_below_6000_mib": all(
            type(resource.get("peak_wddm_bytes")) is int
            and int(resource["peak_wddm_bytes"]) <= MAX_WDDM_BYTES
            for route in all_terminal
            for resource in route["resources_with_three_roots"]
        ),
        "root_bank_closed_to_zero": base_erased["n_total_bytes_after"] == 0,
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
            "r2-unique-descendant-successor-terminal-pipeline-supported-bounded"
            if accepted
            else "successor-terminal-pipeline-without-all-preregistered-gates"
        ),
        "hypothesis": (
            "Two distinct output-derived descendants can each create an exact "
            "one-consumer terminal root that materially lowers consumer TTFT while "
            "preserving exact C-to-D-to-B utility, constant active residency, positive "
            "fully charged wall versus materialization, and near-root-only lifecycle."
        ),
        "trial_design": {
            "axis": "R",
            "R": 2,
            "fanout": False,
            "warmup_trials": WARMUP_TRIALS,
            "counted_trials": COUNTED_TRIALS,
            "routes": list(ROUTES),
            "trial_route_orders": [list(order) for order in TRIAL_ROUTE_ORDERS],
            "state_sequence": list(EXPECTED_STATES),
            "terminal_route": "87-token capture -> exact terminal root -> one 782/0 consumer -> 6-token rebase",
            "root_only_control": "695-token child -> one live 695/87 successor -> 6-token rebase",
            "materialized_control": "identical cache-disabled 0/782 successor",
            "metric_scope": (
                "given the exact initial C child; per-edge terminal/root routes charge "
                "successor work, root operations, and final executable-child rebase. "
                "Task-A, base/seed setup, and per-route experimental reset are reported "
                "outside all compared route lifecycles"
            ),
        },
        "identities": {
            "branch_sha256": EXPECTED_BRANCH_SHA256,
            "suffix_sha256": EXPECTED_SUFFIX_SHA256,
            "generated_sha256": EXPECTED_GENERATED_SHA256,
            "child_sha256": EXPECTED_CHILD_SHA256,
            "request_sha256": EXPECTED_REQUEST_SHA256,
            "terminal_prompt_digest_pairs": terminal_prompt_digest_pairs,
        },
        "setup": {
            "task_a": harness.token_summary(task),
            "retained_root_token_count": retained["retained_root_token_count"],
            "base_materialization": harness.token_summary(base_materialization),
            "base_root": base_root,
            "base_restore": base_restore,
            "seed_capture": harness.token_summary(seed_capture),
            "seed_terminal": seed_terminal,
            "seed_restore": seed_restore,
            "seed_record": seed_record,
            "seed_timing": seed_timing,
            "seed_state": seed_state,
            "lineage_child": lineage_child,
            "lineage_child_sha256": canonical_sha256(lineage_child_tokens),
            "lineage_child_erase": lineage_child_erased,
            "seed_terminal_erase": seed_terminal_erased,
            "resources_with_setup_three_roots": setup_resources,
        },
        "negative_controls": {
            "missing_seed_terminal": missing_terminal,
            "missing_successor_terminal": missing_successor_terminal,
            "mismatched_successor_terminal": warmup["terminal"]["successor_negative"],
        },
        "warmup": warmup,
        "counted_trials": counted,
        "metrics": {
            "terminal_fully_charged_wall_seconds": distribution(terminal_walls),
            "root_only_fully_charged_wall_seconds": distribution(root_walls),
            "materialized_fully_charged_wall_seconds": distribution(direct_walls),
            "aggregate_terminal_fully_charged_wall_seconds": sum(terminal_walls),
            "aggregate_root_only_fully_charged_wall_seconds": sum(root_walls),
            "aggregate_materialized_fully_charged_wall_seconds": sum(direct_walls),
            "terminal_vs_materialized_wall_speedup": terminal_vs_materialized,
            "terminal_vs_root_only_wall_ratio": terminal_vs_root,
            "terminal_consumer_restore_inclusive_ttft_seconds": distribution(terminal_ttft),
            "root_only_restore_inclusive_ttft_seconds": distribution(root_ttft),
            "consumer_ttft_speedup": ttft_speedup,
            "consumer_ttft_dominance": ttft_dominance,
            "counted_terminal_fresh_prompt_tokens": COUNTED_TRIALS * 186,
            "counted_root_only_fresh_prompt_tokens": COUNTED_TRIALS * 186,
            "counted_materialized_fresh_prompt_tokens": COUNTED_TRIALS * 1564,
            "counted_avoided_fresh_prompt_tokens": (
                COUNTED_TRIALS * EXPECTED_AVOIDED_PER_TRIAL
            ),
        },
        "runtime_markers": {
            "capture_count": capture_markers,
            "expected_capture_count": expected_capture_markers,
            "predecode_sample_count": sample_markers,
            "expected_predecode_sample_count": expected_sample_markers,
            "full_reprocess_count": full_reprocess_markers,
        },
        "resources": {
            "after_erase": resources_after_erase,
        },
        "root_closure": {
            "base_erase": base_erased,
        },
        "batch_ownership": {
            "boundaries": ownership,
            "total_seconds": ownership_total,
            "amortized_seconds_per_counted_sequence_route": ownership_share,
        },
        "tool_canary": tool_canary,
        "quality_gates": gates,
        "claim_ceiling": (
            "One bounded process-local Agents-A1 R2 C-to-D-to-B successor-terminal "
            "pipeline with two distinct terminal prompt identities and one consumer per "
            "root. Terminal capture moves 87-token evaluation before each consumer; it "
            "does not eliminate that compute. No canonical .holo, arbitrary recurrence, "
            "restart persistence, weight catalysis, or unbounded-compute claim."
        ),
        "automatic_promotion": False,
        "research_goal_blocked": False,
        "next_boundary": (
            "IF_ACCEPTED_SCALE_UNIQUE_DESCENDANT_TERMINAL_PIPELINE_TO_R4_WITH_CONSTANT_ACTIVE_RESIDENCY; "
            "IF_REJECTED_LOCALIZE_TTFT_OR_FULLY_CHARGED_FAILURE_WITHOUT_NEW_MECHANISM"
        ),
    }


def static_audit(binary: Path) -> dict[str, Any]:
    source = Path(__file__).read_text(encoding="utf-8")
    gates = {
        "no_server_or_cuda_mechanism_change": (
            "neo3000 terminal-logits continuation sampled before decode"
            in (ROOT / "tools" / "server" / "server-context.cpp").read_text(
                encoding="utf-8"
            )
        ),
        "two_edge_sequence_exact": 'EXPECTED_STATES = ("C", "D", "B")' in source,
        "three_matched_routes": 'ROUTES = ("terminal", "root-only", "materialized")' in source,
        "terminal_capture_present": "neo3000_capture_terminal_logits" in source,
        "terminal_consumer_present": "neo3000_use_terminal_logits" in source,
        "one_consumer_gate_present": "one_consumer_per_unique_terminal_root" in source,
        "output_derived_child_rebase_present": "rebase.compact_child_tokens(" in source,
        "consumer_ttft_separate_from_lifecycle": (
            "consumer_ttft_speedup" in source
            and "terminal_vs_root_only_wall_ratio" in source
        ),
        "fresh_work_law_exact": "EXPECTED_AVOIDED_PER_EDGE" in source,
        "maximum_three_root_accounting": "EXPECTED_MAX_PIPELINE_DEVICE_BYTES" in source,
        "cache_disabled_materialized_control": "cache_prompt=False" in source,
        "no_answer_conditioned_root_ids": (
            'f"{EXPERIMENT_ID}-{trial_label}-terminal-edge-{edge}"' in source
            and 'f"{EXPERIMENT_ID}-{trial_label}-{route}-child-{generation}"' in source
        ),
        "no_automatic_promotion": '"automatic_promotion": False' in source,
        "bounded_claim_present": "One bounded process-local Agents-A1 R2" in source,
    }
    require(all(gates.values()), "0086 static audit failed")
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
        require(not path.exists(), f"0086 artifact already exists: {path}")
    require(len({output, log_output, marker}) == 3, "0086 artifact paths collide")
    terminal.require_clean_head(ROOT, args.expected_commit)
    before_bundle = terminal.runtime_bundle(binary)
    static = static_audit(binary)

    corpus = harness.carrier.load_public_corpus(ROOT)
    roots = {str(item["root_id"]): item for item in corpus["roots"]}
    evaluator, live_contract = harness.load_discovery_sidecar_contract()
    stable_pids = harness.live_runtime.require_stable()
    require(len(stable_pids) == 1, "0086 requires one protected stable listener")
    require(
        not harness.live_runtime.listener_pids(harness.live_runtime.PORT),
        "candidate port is occupied",
    )

    state_root = Path(tempfile.mkdtemp(prefix="neo3000-successor-terminal-pipeline-"))
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
            "0086 launch identity changed",
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

    require(result is not None, "0086 result is missing")
    result["cleanup"] = cleanup
    cleanup_gate = harness.live_runtime.cleanup_integrity(cleanup, set(stable_pids))
    result["cleanup_gate"] = cleanup_gate
    if cleanup_gate.get("passed") is not True:
        result["verdict"] = "reject"
        result["classification"] = "successor-terminal-pipeline-cleanup-failure"
    result["artifact"] = terminal.write_exclusive_json(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
