#!/usr/bin/env python3
"""neo-exp-0075 pinned-base fixed-output CUDA capsule rebase.

The accepted C -> D -> B -> B recurrence remains fixed.  One immutable
689-token host root pins the expensive base state.  One replaceable 695-token
CUDA root contains the complete 690-token branch prefix followed by the five
exact visible IDs of the latest output.  After every verified transition the
old CUDA child is erased, the base is restored, exactly six tokens are
materialized, and a same-size replacement child is saved.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import catalytic_frontier_checkpoint_control as checkpoint
import catalytic_frontier_fanout as shared_tasks
import catalytic_frontier_harness as harness
import catalytic_frontier_output_fixed_point as fixed
import catalytic_frontier_recursive_root_promotion as rolling
import catalytic_frontier_single_request_latency as latency
import catalytic_frontier_water_panel_qualifier as water


EXPERIMENT_ID = "neo-exp-0075"
BASE_ROOT_ID = f"{fixed.ROOT_ID}-fixed-base"
EXPECTED_BASE_TOKENS = 689
EXPECTED_COMPLETE_BRANCH_TOKENS = 690
EXPECTED_VISIBLE_OUTPUT_TOKENS = 5
EXPECTED_CHILD_TOKENS = 695
EXPECTED_REBASE_FRESH_TOKENS = 6
EXPECTED_SUCCESSOR_FRESH_TOKENS = 87
EXPECTED_DIRECT_FRESH_TOKENS = 782
EXPECTED_CHILD_DEVICE_BYTES = 80_097_280
EXPECTED_BASE_HOST_BYTES = 79_991_940
PAIR_ROUTE_ORDERS = rolling.PAIR_ROUTE_ORDERS
EXPECTED_STATE_SEQUENCE = fixed.EXPECTED_STATE_SEQUENCE
MIN_FULL_LIFECYCLE_WALL_SPEEDUP = 1.25
MAX_WDDM_BYTES = fixed.MAX_WDDM_BYTES
DEFAULT_BINARY = fixed.DEFAULT_BINARY


def require(condition: bool, message: str) -> None:
    harness.require(condition, message)


def child_root_id(step: int, answer: str) -> str:
    require(step in range(0, 4), "capsule step is out of range")
    require(answer in fixed.TRANSITION, "capsule answer is invalid")
    return f"{fixed.ROOT_ID}-fixed-capsule-r{step}-{answer}"


def compact_child_tokens(
    base_branch_tokens: Sequence[int],
    state: Mapping[str, Any],
) -> list[int]:
    visible = list(state["visible_token_ids"])
    require(
        len(base_branch_tokens) == EXPECTED_COMPLETE_BRANCH_TOKENS,
        "complete branch token count changed",
    )
    require(
        len(visible) == EXPECTED_VISIBLE_OUTPUT_TOKENS,
        "visible output token count changed",
    )
    generated = list(state["generated_token_ids"])
    require(
        generated == [*visible, int(state["terminal_eog_id"])],
        "generated state is not visible IDs plus terminal EOS",
    )
    tokens = [*base_branch_tokens, *visible]
    require(len(tokens) == EXPECTED_CHILD_TOKENS, "fixed child token count changed")
    require(tokens[-EXPECTED_VISIBLE_OUTPUT_TOKENS:] == visible, "fixed child lost exact output IDs")
    return tokens


def validate_root(
    response: Mapping[str, Any],
    *,
    action: str,
    root_id: str,
    storage: str,
    expected: Mapping[str, Any] | None = None,
    expected_tokens: int,
    expected_roots_after: int,
    expected_total_device_bytes_after: int,
) -> dict[str, Any]:
    require(action in {"root-save", "root-restore", "root-erase"}, "unsupported root action")
    require(storage in {"host", "device"}, "unsupported root storage")
    require(response.get("action") == action, f"root action mismatch for {action}")
    require(response.get("root_id") == root_id, f"root identity mismatch for {action}")
    for key in (
        "id_slot",
        "id_slot_source",
        "n_tokens",
        "n_bytes",
        "n_host_bytes",
        "n_device_bytes",
        "n_device_bytes_after",
        "n_gpu_bytes",
        "n_gpu_bytes_after",
        "n_checkpoints",
        "n_roots_after",
        "n_roots_capacity",
        "n_total_bytes_after",
        "n_total_device_bytes_after",
        "n_total_gpu_bytes_after",
    ):
        require(type(response.get(key)) is int, f"root {key} is missing for {action}")
        require(int(response[key]) >= 0, f"root {key} is negative for {action}")
    require(int(response["n_tokens"]) == expected_tokens, f"root token count changed for {action}")
    require(int(response["n_checkpoints"]) == 0, f"root checkpoint count changed for {action}")
    require(int(response["n_roots_capacity"]) == 2, "root bank capacity changed")
    require(
        int(response["n_roots_after"]) == expected_roots_after,
        f"root bank count changed for {action}",
    )
    require(
        int(response["n_total_device_bytes_after"]) == expected_total_device_bytes_after,
        f"root bank live device bytes changed for {action}",
    )
    require(
        int(response["n_total_gpu_bytes_after"]) == expected_total_device_bytes_after,
        f"root bank live GPU bytes changed for {action}",
    )
    require(
        int(response["n_bytes"])
        == int(response["n_host_bytes"]) + int(response["n_device_bytes"]),
        f"root byte accounting changed for {action}",
    )
    if storage == "host":
        require(int(response["n_device_bytes"]) == 0, f"host root gained device bytes at {action}")
        require(int(response["n_gpu_bytes"]) == 0, f"host root gained GPU bytes at {action}")
    else:
        require(int(response["n_device_bytes"]) > 0, f"device root lost device bytes at {action}")
        require(int(response["n_gpu_bytes"]) > 0, f"device root lost GPU bytes at {action}")
        require(
            int(response["n_gpu_bytes"]) == int(response["n_device_bytes"]),
            f"device root is not wholly GPU-resident at {action}",
        )
    expected_after = 0 if action == "root-erase" else int(response["n_device_bytes"])
    expected_gpu_after = 0 if action == "root-erase" else int(response["n_gpu_bytes"])
    require(
        int(response["n_device_bytes_after"]) == expected_after,
        f"root device closure changed for {action}",
    )
    require(
        int(response["n_gpu_bytes_after"]) == expected_gpu_after,
        f"root GPU closure changed for {action}",
    )
    if expected is not None:
        for key in (
            "root_id",
            "id_slot_source",
            "n_tokens",
            "n_bytes",
            "n_host_bytes",
            "n_device_bytes",
            "n_gpu_bytes",
            "n_checkpoints",
        ):
            require(response.get(key) == expected.get(key), f"root {key} changed at {action}")
    timings = response.get("timings")
    require(
        isinstance(timings, Mapping) and isinstance(timings.get("root_ms"), (int, float)),
        f"root timing is missing for {action}",
    )
    return {
        key: response[key]
        for key in (
            "action",
            "root_id",
            "id_slot",
            "id_slot_source",
            "n_tokens",
            "n_bytes",
            "n_host_bytes",
            "n_device_bytes",
            "n_device_bytes_after",
            "n_gpu_bytes",
            "n_gpu_bytes_after",
            "n_checkpoints",
            "n_roots_after",
            "n_roots_capacity",
            "n_total_bytes_after",
            "n_total_device_bytes_after",
            "n_total_gpu_bytes_after",
        )
    } | {"server_root_ms": float(timings["root_ms"])}


def root_action(
    *,
    action: str,
    root_id: str,
    storage: str,
    expected_tokens: int,
    expected_roots_after: int,
    expected_total_device_bytes_after: int,
    label: str,
    expected: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    raw, wall = harness.ram_root_action(
        action=action,
        root_id=root_id,
        storage=storage if action == "root-save" else "default",
    )
    record = validate_root(
        raw,
        action=action,
        root_id=root_id,
        storage=storage,
        expected=expected,
        expected_tokens=expected_tokens,
        expected_roots_after=expected_roots_after,
        expected_total_device_bytes_after=expected_total_device_bytes_after,
    )
    record.update(label=label, storage=storage, client_wall_seconds=wall)
    return record


def run_successor_route(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    child_root: Mapping[str, Any],
    child_tokens: Sequence[int],
    prior_state: Mapping[str, Any],
    step: int,
    route: str,
) -> dict[str, Any]:
    require(route in {"catalytic", "direct"}, "unsupported fixed-size route")
    restore: dict[str, Any] | None = None
    restore_wall = 0.0
    if route == "catalytic":
        restore = root_action(
            action="root-restore",
            root_id=str(child_root["root_id"]),
            storage="device",
            expected=child_root,
            expected_tokens=EXPECTED_CHILD_TOKENS,
            expected_roots_after=2,
            expected_total_device_bytes_after=EXPECTED_CHILD_DEVICE_BYTES,
            label=f"step-{step}:restore-child",
        )
        restore_wall = float(restore["client_wall_seconds"])
    tokens, payload, ancestry = rolling.derive_promoted_successor(
        codec=codec,
        root_tokens=child_tokens,
        prior_state=prior_state,
        seed=shared_tasks.derive_seed(fixed.ROOT_ID, f"fixed-size-rebase-step-{step}"),
        cache_prompt=route == "catalytic",
    )
    require(len(tokens) == EXPECTED_DIRECT_FRESH_TOKENS, "fixed-size successor prompt changed")
    recorder = latency.TimingRecorder()
    record = harness.run_completion(
        sidecar,
        f"{fixed.ROOT_ID}:fixed-size-rebase:step-{step}:{route}",
        payload,
        recorder=recorder,
        batch_owned_request=True,
    )
    state = fixed.generated_state(record, codec=codec, props=props)
    expected_answer = fixed.TRANSITION[str(prior_state["answer"])]
    require(state["answer"] == expected_answer, f"fixed-size step {step} answer is incorrect")
    require(record["prompt_tokens"] == len(tokens), f"fixed-size step {step} prompt count changed")
    expected_cached = EXPECTED_CHILD_TOKENS if route == "catalytic" else 0
    expected_fresh = EXPECTED_SUCCESSOR_FRESH_TOKENS if route == "catalytic" else EXPECTED_DIRECT_FRESH_TOKENS
    require(record["cached_prompt_tokens"] == expected_cached, f"{route} cache count changed")
    require(record["fresh_prompt_tokens"] == expected_fresh, f"{route} fresh count changed")
    timing = recorder.summary(request_wall_seconds=float(record["wall_seconds"]))
    require(timing["server_prompt_n"] == expected_fresh, "server prompt timing changed")
    require(timing["server_predicted_n"] == record["completion_tokens"], "generation timing changed")
    record.update(
        route=route,
        step=step,
        expected_answer=expected_answer,
        correct=True,
        state=state,
        ancestry=ancestry,
        restore=restore,
        restore_client_wall_seconds=restore_wall,
        effective_wall_seconds=float(record["wall_seconds"]) + restore_wall,
        prompt_token_sha256=ancestry["request_token_sha256"],
        timing=timing,
    )
    return record


def rebase_child(
    *,
    sidecar: Any,
    base_root: Mapping[str, Any],
    old_child: Mapping[str, Any],
    base_branch_tokens: Sequence[int],
    next_state: Mapping[str, Any],
    step: int,
) -> tuple[dict[str, Any], list[int], list[dict[str, Any]], dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    erased = root_action(
        action="root-erase",
        root_id=str(old_child["root_id"]),
        storage="device",
        expected=old_child,
        expected_tokens=EXPECTED_CHILD_TOKENS,
        expected_roots_after=1,
        expected_total_device_bytes_after=0,
        label=f"step-{step}:erase-stale-child",
    )
    operations.append(erased)
    restored_base = root_action(
        action="root-restore",
        root_id=BASE_ROOT_ID,
        storage="host",
        expected=base_root,
        expected_tokens=EXPECTED_BASE_TOKENS,
        expected_roots_after=1,
        expected_total_device_bytes_after=0,
        label=f"step-{step}:restore-base",
    )
    operations.append(restored_base)
    child_tokens = compact_child_tokens(base_branch_tokens, next_state)
    payload = harness.carrier._branch_payload(
        child_tokens,
        seed=shared_tasks.derive_seed(fixed.ROOT_ID, f"fixed-size-rebase-materialize-{step}"),
        cache_prompt=True,
        n_predict=0,
    )
    materialized = harness.run_completion(
        sidecar,
        f"{fixed.ROOT_ID}:fixed-size-rebase:materialize-{step}",
        payload,
        operation_kind="fixed-output-capsule-rebase",
        batch_owned_request=True,
    )
    require(materialized["prompt_tokens"] == EXPECTED_CHILD_TOKENS, "rebase prompt count changed")
    require(materialized["cached_prompt_tokens"] == EXPECTED_BASE_TOKENS, "rebase base cache changed")
    require(materialized["fresh_prompt_tokens"] == EXPECTED_REBASE_FRESH_TOKENS, "rebase fresh count changed")
    require(materialized["completion_tokens"] == 0, "rebase emitted output")
    next_child = root_action(
        action="root-save",
        root_id=child_root_id(step, str(next_state["answer"])),
        storage="device",
        expected_tokens=EXPECTED_CHILD_TOKENS,
        expected_roots_after=2,
        expected_total_device_bytes_after=EXPECTED_CHILD_DEVICE_BYTES,
        label=f"step-{step}:save-rebased-child",
    )
    operations.append(next_child)
    return next_child, child_tokens, operations, materialized


def classify(*, integrity: bool, fixed_size: bool, saved_work_law: bool, speedup: float) -> str:
    if not integrity:
        return "fixed-size-rebase-integrity-failure"
    if not fixed_size:
        return "fixed-size-rebase-growth-failure"
    if not saved_work_law:
        return "fixed-size-rebase-saved-work-law-failure"
    if speedup < MIN_FULL_LIFECYCLE_WALL_SPEEDUP:
        return "fixed-size-rebase-without-preregistered-wall-gate"
    return "pinned-base-fixed-output-cuda-capsule-rebase-r3-supported-bounded"


def evaluate(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    root: Mapping[str, Any],
    baseline_private: int | None,
) -> dict[str, Any]:
    panel = water.panel_for(root)
    require(water.base._panel_hash(panel) == fixed.PANEL_SHA256, "water panel identity changed")
    seed_spec = panel[fixed.SEED_BRANCH_NUMBER - 1]
    require(seed_spec["answer"] == fixed.SEED_EXPECTED_ANSWER, "seed answer changed")

    prompt_text = codec.render_messages(
        harness.carrier.task_a_messages(root),
        harness.carrier.CHAT_TEMPLATE_KWARGS,
    )
    prompt_tokens = codec.tokenize(prompt_text)
    require(len(prompt_tokens) == latency.EXPECTED_PROMPT_ROOT_TOKENS, "Task-A prompt changed")
    task_payload = harness.carrier._task_a_payload(
        prompt_tokens,
        seed=shared_tasks.derive_seed(fixed.ROOT_ID, "task-a"),
    )
    task_a = harness.run_completion(sidecar, f"{fixed.ROOT_ID}:fixed-size:task-a", task_payload)
    parsed_task_a = harness.carrier.parse_task_a_output(task_a["content"])
    require(parsed_task_a["answer"] == harness.EXPECTED[fixed.ROOT_ID]["task_a"], "Task-A changed")
    retained = harness.carrier.derive_retained_root(
        harness.root_capture(task_a, task_payload),
        prompt_tokens,
        codec,
        props,
    )
    require(
        int(retained["retained_root_token_count"]) == latency.EXPECTED_RETAINED_ROOT_TOKENS,
        "retained root changed",
    )
    base_branch_tokens, _ = latency.branch_request(codec, retained, seed_spec, cache_prompt=False)
    require(
        len(base_branch_tokens) == EXPECTED_COMPLETE_BRANCH_TOKENS,
        "complete branch prompt count changed",
    )
    parent_tokens = list(base_branch_tokens[:EXPECTED_BASE_TOKENS])
    materialize_payload = harness.carrier._branch_payload(
        parent_tokens,
        seed=shared_tasks.derive_seed(fixed.ROOT_ID, "fixed-base-materialize"),
        cache_prompt=False,
        n_predict=0,
    )
    parent_materialization = harness.run_completion(
        sidecar,
        f"{fixed.ROOT_ID}:fixed-size:base-materialize",
        materialize_payload,
        operation_kind="zero-output-fixed-base-materialization",
    )
    require(parent_materialization["fresh_prompt_tokens"] == EXPECTED_BASE_TOKENS, "base replay changed")
    base_saved = root_action(
        action="root-save",
        root_id=BASE_ROOT_ID,
        storage="host",
        expected_tokens=EXPECTED_BASE_TOKENS,
        expected_roots_after=1,
        expected_total_device_bytes_after=0,
        label="save-immutable-host-base",
    )
    require(base_saved["n_bytes"] == EXPECTED_BASE_HOST_BYTES, "host base bytes changed")
    root_operations: list[dict[str, Any]] = [base_saved]
    resources_with_base = harness.process_resources(sidecar, baseline_private)

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

    ownership_boundary("pre-fixed-size-rebase-batch")

    base_restore = root_action(
        action="root-restore",
        root_id=BASE_ROOT_ID,
        storage="host",
        expected=base_saved,
        expected_tokens=EXPECTED_BASE_TOKENS,
        expected_roots_after=1,
        expected_total_device_bytes_after=0,
        label="restore-base-before-seed",
    )
    root_operations.append(base_restore)
    seed_payload = harness.carrier._branch_payload(
        base_branch_tokens,
        seed=shared_tasks.derive_seed(fixed.ROOT_ID, f"branch-{fixed.SEED_BRANCH_NUMBER}"),
        cache_prompt=True,
    )
    seed_record = harness.run_completion(
        sidecar,
        f"{fixed.ROOT_ID}:fixed-size:seed",
        seed_payload,
        batch_owned_request=True,
    )
    seed_state = fixed.generated_state(seed_record, codec=codec, props=props)
    require(seed_state["answer"] == fixed.SEED_EXPECTED_ANSWER, "seed output changed")
    require(seed_state["generated_token_sha256"] == fixed.SEED_GENERATED_SHA256, "seed hash changed")
    require(
        seed_record["cached_prompt_tokens"] == EXPECTED_BASE_TOKENS
        and seed_record["fresh_prompt_tokens"] == 1,
        "seed cache split changed",
    )
    child_tokens = compact_child_tokens(base_branch_tokens, seed_state)
    child_root = root_action(
        action="root-save",
        root_id=child_root_id(0, seed_state["answer"]),
        storage="device",
        expected_tokens=EXPECTED_CHILD_TOKENS,
        expected_roots_after=2,
        expected_total_device_bytes_after=EXPECTED_CHILD_DEVICE_BYTES,
        label="save-seed-cuda-child",
    )
    require(child_root["n_device_bytes"] == EXPECTED_CHILD_DEVICE_BYTES, "seed child bytes changed")
    root_operations.append(child_root)
    resources_with_two_roots = harness.process_resources(sidecar, baseline_private)

    records: list[dict[str, Any]] = []
    rebases: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    observed_sequence = [seed_state["answer"]]
    prior_state = seed_state
    cumulative_avoided = 0
    for step, route_order in enumerate(PAIR_ROUTE_ORDERS, start=1):
        pair: dict[str, dict[str, Any]] = {}
        for route in route_order:
            record = run_successor_route(
                sidecar=sidecar,
                codec=codec,
                props=props,
                child_root=child_root,
                child_tokens=child_tokens,
                prior_state=prior_state,
                step=step,
                route=route,
            )
            pair[route] = record
            records.append(record)
        require(set(pair) == {"catalytic", "direct"}, "fixed-size pair lost a route")
        catalytic = pair["catalytic"]
        direct = pair["direct"]
        require(catalytic["prompt_token_sha256"] == direct["prompt_token_sha256"], "prompt hashes differ")
        require(
            catalytic["state"]["generated_token_ids"] == direct["state"]["generated_token_ids"],
            "generated arrays differ",
        )
        agreed_state = dict(catalytic["state"])
        next_child, next_child_tokens, rebase_ops, materialized = rebase_child(
            sidecar=sidecar,
            base_root=base_saved,
            old_child=child_root,
            base_branch_tokens=base_branch_tokens,
            next_state=agreed_state,
            step=step,
        )
        root_operations.extend(rebase_ops)
        rebases.append(materialized)
        avoided = int(direct["fresh_prompt_tokens"]) - (
            int(catalytic["fresh_prompt_tokens"]) + int(materialized["fresh_prompt_tokens"])
        )
        require(avoided == EXPECTED_BASE_TOKENS, "charged avoided work changed")
        cumulative_avoided += avoided
        observed_sequence.append(str(agreed_state["answer"]))
        steps.append(
            {
                "step": step,
                "route_order": list(route_order),
                "prior_answer": prior_state["answer"],
                "answer": agreed_state["answer"],
                "parent_child_root_id": child_root["root_id"],
                "next_child_root_id": next_child["root_id"],
                "child_root_tokens": len(child_tokens),
                "next_child_root_tokens": len(next_child_tokens),
                "child_device_bytes": child_root["n_device_bytes"],
                "next_child_device_bytes": next_child["n_device_bytes"],
                "successor_fresh_tokens": catalytic["fresh_prompt_tokens"],
                "rebase_fresh_tokens": materialized["fresh_prompt_tokens"],
                "direct_fresh_tokens": direct["fresh_prompt_tokens"],
                "avoided_fresh_prompt_tokens_after_rebase_charge": avoided,
                "cumulative_avoided_fresh_prompt_tokens": cumulative_avoided,
                "prompt_token_sha256": catalytic["prompt_token_sha256"],
                "generated_token_sha256": agreed_state["generated_token_sha256"],
                "child_token_sha256": harness.sha256_bytes(
                    harness.carrier.canonical_json_bytes(next_child_tokens)
                ),
                "paired_prompt_identity_exact": True,
                "paired_generated_identity_exact": True,
                "visible_output_ids_copied_without_retokenization": True,
            }
        )
        child_root = next_child
        child_tokens = next_child_tokens
        prior_state = agreed_state

    ownership_boundary("post-fixed-size-rebase-batch")
    ownership_total = sum(float(item["client_wall_seconds"]) for item in ownership)
    ownership_share = ownership_total / len(records)
    for record in records:
        record["batch_ownership_amortized_seconds"] = ownership_share
        record["effective_wall_seconds"] = float(record["effective_wall_seconds"]) + ownership_share

    final_child_restore = root_action(
        action="root-restore",
        root_id=str(child_root["root_id"]),
        storage="device",
        expected=child_root,
        expected_tokens=EXPECTED_CHILD_TOKENS,
        expected_roots_after=2,
        expected_total_device_bytes_after=EXPECTED_CHILD_DEVICE_BYTES,
        label="final-child-restore",
    )
    root_operations.append(final_child_restore)
    resources_before_closure = harness.process_resources(sidecar, baseline_private)
    final_child_erase = root_action(
        action="root-erase",
        root_id=str(child_root["root_id"]),
        storage="device",
        expected=child_root,
        expected_tokens=EXPECTED_CHILD_TOKENS,
        expected_roots_after=1,
        expected_total_device_bytes_after=0,
        label="final-child-erase",
    )
    root_operations.append(final_child_erase)
    final_base_erase = root_action(
        action="root-erase",
        root_id=BASE_ROOT_ID,
        storage="host",
        expected=base_saved,
        expected_tokens=EXPECTED_BASE_TOKENS,
        expected_roots_after=0,
        expected_total_device_bytes_after=0,
        label="final-base-erase",
    )
    root_operations.append(final_base_erase)
    require(final_base_erase["n_total_bytes_after"] == 0, "root bank did not close")
    resources_after_closure = harness.process_resources(sidecar, baseline_private)

    catalytic_records = [record for record in records if record["route"] == "catalytic"]
    direct_records = [record for record in records if record["route"] == "direct"]
    root_and_rebase_wall = (
        float(parent_materialization["wall_seconds"])
        + sum(float(item["wall_seconds"]) for item in rebases)
        + sum(float(operation["client_wall_seconds"]) for operation in root_operations)
    )
    catalytic_wall = root_and_rebase_wall + sum(
        float(record["effective_wall_seconds"]) for record in catalytic_records
    )
    direct_wall = sum(float(record["effective_wall_seconds"]) for record in direct_records)
    lifecycle_speedup = direct_wall / catalytic_wall
    exact_sequence = tuple(observed_sequence) == EXPECTED_STATE_SEQUENCE
    paired_identity = all(
        step["paired_prompt_identity_exact"]
        and step["paired_generated_identity_exact"]
        and step["visible_output_ids_copied_without_retokenization"]
        for step in steps
    )
    fixed_size = all(
        step["child_root_tokens"] == EXPECTED_CHILD_TOKENS
        and step["next_child_root_tokens"] == EXPECTED_CHILD_TOKENS
        and step["child_device_bytes"] == EXPECTED_CHILD_DEVICE_BYTES
        and step["next_child_device_bytes"] == EXPECTED_CHILD_DEVICE_BYTES
        for step in steps
    )
    saved_work_law = all(
        step["avoided_fresh_prompt_tokens_after_rebase_charge"] == EXPECTED_BASE_TOKENS
        and step["cumulative_avoided_fresh_prompt_tokens"] == EXPECTED_BASE_TOKENS * step["step"]
        for step in steps
    )
    base_invariant = all(
        operation["n_tokens"] == EXPECTED_BASE_TOKENS
        and operation["n_bytes"] == EXPECTED_BASE_HOST_BYTES
        and operation["n_device_bytes"] == 0
        for operation in root_operations
        if operation["root_id"] == BASE_ROOT_ID
    )
    bank_invariant = all(
        operation["n_roots_after"] <= 2
        and operation["n_total_device_bytes_after"] in {0, EXPECTED_CHILD_DEVICE_BYTES}
        for operation in root_operations
    )
    integrity = (
        exact_sequence
        and paired_identity
        and base_invariant
        and bank_invariant
        and final_base_erase["n_roots_after"] == 0
        and final_base_erase["n_total_bytes_after"] == 0
    )
    classification = classify(
        integrity=integrity,
        fixed_size=fixed_size,
        saved_work_law=saved_work_law,
        speedup=lifecycle_speedup,
    )
    accepted_before_cleanup = (
        classification == "pinned-base-fixed-output-cuda-capsule-rebase-r3-supported-bounded"
    )
    return {
        "status": "complete-pending-cleanup",
        "experiment_id": EXPERIMENT_ID,
        "mechanism": "pinned-host-base-plus-fixed-output-cuda-capsule-rebase",
        "verdict": "accept" if accepted_before_cleanup else "reject",
        "classification": classification,
        "geometry": {"N": 1, "T": 3, "R": 3, "B": 1},
        "claim_ceiling": (
            "exact fixed-size recursive state rebase for the bounded finite-state recurrence; "
            "not arbitrary-history semantic compaction or unbounded inference"
        ),
        "shared_prerequisite": {
            "task_a": harness.token_summary(task_a),
            "seed": {
                **harness.token_summary(seed_record),
                "answer": seed_state["answer"],
                "generated_token_sha256": seed_state["generated_token_sha256"],
            },
        },
        "steps": steps,
        "records": records,
        "rebases": [harness.token_summary(item) for item in rebases],
        "roots": {
            "base": base_saved,
            "seed_child": {
                "root_id": child_root_id(0, seed_state["answer"]),
                "n_tokens": EXPECTED_CHILD_TOKENS,
            },
            "final_child": child_root,
            "operations": root_operations,
            "maximum_simultaneous_roots": 2,
            "maximum_simultaneous_device_roots": 1,
        },
        "batch_ownership": {
            "boundaries": ownership,
            "total_seconds": ownership_total,
            "amortized_seconds_per_counted_route": ownership_share,
            "both_boundaries_exact": all(
                item["evidence"].get("passed") is True for item in ownership
            ),
        },
        "metrics": {
            "fixed_size_law": {
                "base_tokens": EXPECTED_BASE_TOKENS,
                "child_tokens_each_step": [step["next_child_root_tokens"] for step in steps],
                "child_device_bytes_each_step": [step["next_child_device_bytes"] for step in steps],
                "successor_fresh_tokens_each_step": [
                    step["successor_fresh_tokens"] for step in steps
                ],
                "rebase_fresh_tokens_each_step": [step["rebase_fresh_tokens"] for step in steps],
                "direct_fresh_tokens_each_step": [step["direct_fresh_tokens"] for step in steps],
                "charged_avoided_fresh_prompt_tokens": cumulative_avoided,
                "expected_689_times_r": EXPECTED_BASE_TOKENS * len(steps),
            },
            "counted_full_lifecycle": {
                "scope": (
                    "base materialization/save, seed base restore/child save, every child restore, "
                    "every child erase/base restore/six-token rebase/child save, final restores and "
                    "erases, and equal batch-ownership share; Task-A and seed generation shared"
                ),
                "root_and_rebase_wall_seconds": root_and_rebase_wall,
                "catalytic_wall_seconds": catalytic_wall,
                "direct_wall_seconds": direct_wall,
                "wall_speedup": lifecycle_speedup,
                "minimum_wall_speedup": MIN_FULL_LIFECYCLE_WALL_SPEEDUP,
            },
            "residency": {
                "with_base": resources_with_base,
                "with_two_roots": resources_with_two_roots,
                "before_closure": resources_before_closure,
                "after_closure": resources_after_closure,
                "maximum_simultaneous_roots": 2,
                "maximum_simultaneous_device_roots": 1,
            },
        },
        "quality_gates": {
            "qualified_panel_identity_exact": True,
            "seed_output_and_generated_token_identity_exact": True,
            "state_sequence_C_D_B_B_exact": exact_sequence,
            "final_B_to_B_fixed_point_exact": observed_sequence[-2:] == ["B", "B"],
            "paired_prompt_and_generated_identity_exact": paired_identity,
            "base_root_metadata_invariant": base_invariant,
            "root_bank_capacity_two_exact": bank_invariant,
            "only_one_device_root_resident": bank_invariant,
            "child_token_count_slope_zero": fixed_size,
            "child_device_byte_slope_zero": fixed_size,
            "successor_fresh_tokens_87_each_step": all(
                step["successor_fresh_tokens"] == EXPECTED_SUCCESSOR_FRESH_TOKENS
                for step in steps
            ),
            "rebase_fresh_tokens_6_each_step": all(
                step["rebase_fresh_tokens"] == EXPECTED_REBASE_FRESH_TOKENS for step in steps
            ),
            "direct_fresh_tokens_782_each_step": all(
                step["direct_fresh_tokens"] == EXPECTED_DIRECT_FRESH_TOKENS for step in steps
            ),
            "charged_saved_work_689_times_r": saved_work_law,
            "checkpoint_count_zero": all(
                operation["n_checkpoints"] == 0 for operation in root_operations
            ),
            "final_root_bank_closure_zero": final_base_erase["n_total_bytes_after"] == 0,
            "batch_ownership_boundaries_exact": all(
                item["evidence"].get("passed") is True for item in ownership
            ),
            "fully_counted_wall_speedup_at_least_1_25": (
                lifecycle_speedup >= MIN_FULL_LIFECYCLE_WALL_SPEEDUP
            ),
            "fanout_claimed": False,
            "arbitrary_history_compaction_claimed": False,
            "unbounded_catalytic_inference_established": False,
            "automatic_promotion": False,
        },
        "next_boundary": (
            "PRESERVE_FIXED_SIZE_R3_AND_SCALE_RECURSIVE_DEPTH_WITH_CONSTANT_CARRIER"
            if accepted_before_cleanup
            else "PRESERVE_EXECUTED_EVIDENCE_AND_LOCALIZE_THE_FIRST_FAILED_GATE_WITHOUT_RETRY"
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


def finalize_after_cleanup(
    result: dict[str, Any],
    *,
    cleanup: Mapping[str, Any],
    cleanup_wall_seconds: float,
    stable_pids: set[int],
) -> dict[str, Any]:
    cleanup_record = dict(cleanup)
    cleanup_record["retirement_wall_seconds"] = cleanup_wall_seconds
    cleanup_gate = harness.live_runtime.cleanup_integrity(cleanup_record, stable_pids)
    peak_wddm = latency.cleanup_peak_wddm_bytes(cleanup_record)
    wddm_gate = type(peak_wddm) is int and int(peak_wddm) <= MAX_WDDM_BYTES
    scientific_gate = result["verdict"] == "accept"
    accepted = scientific_gate and cleanup_gate["passed"] is True and wddm_gate
    result["cleanup"] = cleanup_record
    result["cleanup_gate"] = cleanup_gate
    result["metrics"]["residency"].update(
        peak_wddm_bytes=peak_wddm,
        maximum_wddm_bytes=MAX_WDDM_BYTES,
        wddm_gate=wddm_gate,
    )
    result["quality_gates"].update(
        cuda_wddm_at_or_below_6000_mib=wddm_gate,
        candidate_process_retired=cleanup_gate["passed"] is True,
        stable_listener_healthy=cleanup_record.get("stable_after", {}).get("healthy") is True,
        frontier_port_free=cleanup_record.get("port_free") is True,
        fixed_size_recursive_cuda_capsule_rebase_supported=accepted,
    )
    result["status"] = "complete"
    result["verdict"] = "accept" if accepted else "reject"
    if accepted:
        result["classification"] = (
            "pinned-base-fixed-output-cuda-capsule-rebase-r3-supported-bounded"
        )
        result["next_boundary"] = (
            "PRESERVE_FIXED_SIZE_R3_AND_SCALE_RECURSIVE_DEPTH_WITH_CONSTANT_CARRIER"
        )
    elif scientific_gate:
        result["classification"] = "fixed-size-rebase-cleanup-or-residency-failure"
        result["next_boundary"] = (
            "PRESERVE_EXECUTED_EVIDENCE_AND_LOCALIZE_CLEANUP_OR_RESIDENCY_FAILURE_WITHOUT_RETRY"
        )
    return result


def main() -> int:
    args = parse_args()
    repository = Path(__file__).resolve().parents[1]
    binary = args.binary.resolve(strict=True)
    require(
        binary == (repository / DEFAULT_BINARY).resolve(strict=True),
        "fixed-size rebase requires the isolated candidate binary",
    )
    cuda_runtime_sha256 = latency.verify_cuda_root_runtime(binary)
    model = args.model.resolve(strict=True)
    latency.require_unused_artifact_paths(args.output, args.server_log_output)
    corpus = harness.carrier.load_public_corpus(repository)
    roots = {str(item["root_id"]): item for item in corpus["roots"]}
    evaluator, live_contract = harness.load_discovery_sidecar_contract()
    stable_pids = harness.live_runtime.require_stable()
    require(len(stable_pids) == 1, "fixed-size rebase requires the sole stable listener")
    require(not harness.live_runtime.listener_pids(harness.live_runtime.PORT), "frontier port is occupied")
    state_root = Path(tempfile.mkdtemp(prefix="neo3000-fixed-size-rebase-"))
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
            server_launch_args=checkpoint.CUDA_ROOT_SERVER_ARGS,
            moe_server_args=checkpoint.DEFAULT_MOE_SERVER_ARGS,
        )
        readiness = sidecar.launch()
        launch_configuration = readiness.get("launch_configuration")
        require(
            isinstance(launch_configuration, Mapping)
            and launch_configuration.get("server_launch_args")
            == list(checkpoint.CUDA_ROOT_SERVER_ARGS)
            and launch_configuration.get("moe_server_args")
            == list(checkpoint.DEFAULT_MOE_SERVER_ARGS)
            and launch_configuration.get("root_storage") == "device"
            and launch_configuration.get("speculative_type") == "none",
            "fixed-size rebase launch identity changed",
        )
        baseline_private = None
        process_memory = readiness.get("process_memory")
        if isinstance(process_memory, Mapping) and type(process_memory.get("private_bytes")) is int:
            baseline_private = int(process_memory["private_bytes"])
        codec = harness.carrier.SidecarPromptCodec(harness.live_runtime.PORT)
        result = evaluate(
            sidecar=sidecar,
            codec=codec,
            props=codec.props(),
            root=roots[fixed.ROOT_ID],
            baseline_private=baseline_private,
        )
        result["runtime_identity"] = {
            "binary_runtime_version": harness.live_runtime.binary_version(binary),
            "cuda_runtime_sha256": cuda_runtime_sha256,
            "model_sha256": harness.live_runtime.sha256_file(model),
            "context_checkpoints": args.ctx_checkpoints,
            "launch_configuration": launch_configuration,
        }
        result["readiness"] = {
            "pid": readiness.get("pid"),
            "readiness_seconds": readiness.get("readiness_seconds"),
            "baseline_private_bytes": baseline_private,
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
        print(
            json.dumps(
                {
                    "status": "engineering-failure",
                    "experiment_id": EXPERIMENT_ID,
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "cleanup": cleanup,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    require(result is not None, "fixed-size result is missing")
    result = finalize_after_cleanup(
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
