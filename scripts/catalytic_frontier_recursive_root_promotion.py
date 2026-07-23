#!/usr/bin/env python3
"""neo-exp-0074 rolling output-bearing CUDA-root promotion.

The accepted C -> D -> B -> B recurrence remains fixed.  The only new
mechanism replaces the saved root after each catalytic output: erase the old
root while preserving the live slot, then save that exact output-bearing state
under a new identity.  No two roots coexist.
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
import catalytic_frontier_single_request_latency as latency
import catalytic_frontier_water_panel_qualifier as water


EXPERIMENT_ID = "neo-exp-0074"
PARENT_ROOT_ID = f"{fixed.ROOT_ID}-parent-r0"
PAIR_ROUTE_ORDERS = (
    ("direct", "catalytic"),
    ("catalytic", "direct"),
    ("direct", "catalytic"),
)
EXPECTED_STATE_SEQUENCE = fixed.EXPECTED_STATE_SEQUENCE
MIN_FULL_LIFECYCLE_WALL_SPEEDUP = 1.25
MAX_WDDM_BYTES = fixed.MAX_WDDM_BYTES
DEFAULT_BINARY = fixed.DEFAULT_BINARY


def require(condition: bool, message: str) -> None:
    harness.require(condition, message)


def child_root_id(step: int, answer: str) -> str:
    require(step in range(0, 4), "rolling root step is out of range")
    require(answer in fixed.TRANSITION, "rolling root answer is invalid")
    return f"{fixed.ROOT_ID}-output-r{step}-{answer}"


def validate_named_root(
    response: Mapping[str, Any],
    *,
    action: str,
    root_id: str,
    expected: Mapping[str, Any] | None = None,
    expected_tokens: int | None = None,
) -> dict[str, Any]:
    require(action in {"root-save", "root-restore", "root-erase"}, "unsupported root action")
    require(response.get("action") == action, f"root action mismatch for {action}")
    require(response.get("root_id") == root_id, f"root identity mismatch for {action}")
    require(type(response.get("id_slot")) is int, f"root slot is missing for {action}")
    for key in (
        "n_tokens",
        "n_bytes",
        "n_host_bytes",
        "n_device_bytes",
        "n_device_bytes_after",
        "n_gpu_bytes",
        "n_gpu_bytes_after",
        "n_checkpoints",
    ):
        require(type(response.get(key)) is int, f"root {key} is missing for {action}")
        require(int(response[key]) >= 0, f"root {key} is negative for {action}")
    require(int(response["n_tokens"]) > 0, f"root is empty for {action}")
    require(int(response["n_bytes"]) > 0, f"root has no logical bytes for {action}")
    require(
        int(response["n_bytes"])
        == int(response["n_host_bytes"]) + int(response["n_device_bytes"]),
        f"root byte accounting changed for {action}",
    )
    require(int(response["n_device_bytes"]) > 0, f"root has no device state for {action}")
    require(int(response["n_gpu_bytes"]) > 0, f"root has no GPU state for {action}")
    require(
        int(response["n_gpu_bytes"]) <= int(response["n_device_bytes"]),
        f"root GPU bytes exceed device bytes for {action}",
    )
    require(int(response["n_checkpoints"]) == 0, f"root checkpoint count changed for {action}")
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
    if expected_tokens is not None:
        require(int(response["n_tokens"]) == expected_tokens, f"root token count changed for {action}")
    if expected is not None:
        for key in (
            "root_id",
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
        "action": action,
        "root_id": root_id,
        "id_slot": response["id_slot"],
        "n_tokens": response["n_tokens"],
        "n_bytes": response["n_bytes"],
        "n_host_bytes": response["n_host_bytes"],
        "n_device_bytes": response["n_device_bytes"],
        "n_device_bytes_after": response["n_device_bytes_after"],
        "n_gpu_bytes": response["n_gpu_bytes"],
        "n_gpu_bytes_after": response["n_gpu_bytes_after"],
        "n_checkpoints": response["n_checkpoints"],
        "server_root_ms": float(timings["root_ms"]),
    }


def derive_promoted_successor(
    *,
    codec: Any,
    root_tokens: Sequence[int],
    prior_state: Mapping[str, Any],
    seed: int,
    cache_prompt: bool,
    transition_content: str | None = None,
) -> tuple[list[int], dict[str, Any], dict[str, Any]]:
    visible = list(prior_state["visible_token_ids"])
    generated = list(prior_state["generated_token_ids"])
    require(
        len(root_tokens) >= len(visible)
        and list(root_tokens[-len(visible) :]) == visible,
        "promoted root does not end with exact prior visible generated IDs",
    )
    suffix = harness.carrier.derive_continuation_suffix(
        codec,
        terminal_eog_id=int(prior_state["terminal_eog_id"]),
        user_content=(
            fixed.transition_user_content()
            if transition_content is None
            else transition_content
        ),
    )
    require(
        generated == [*visible, int(prior_state["terminal_eog_id"])],
        "prior generated-token terminal identity changed",
    )
    require(
        [*root_tokens[-len(visible) :], suffix["suffix_tokens"][0]] == generated,
        "promoted successor does not reconstruct exact prior generated IDs across the root boundary",
    )
    tokens = [*root_tokens, *suffix["suffix_tokens"]]
    payload = harness.carrier._branch_payload(tokens, seed=seed, cache_prompt=cache_prompt)
    ancestry = {
        "prior_answer": prior_state["answer"],
        "root_token_count": len(root_tokens),
        "root_token_sha256": harness.sha256_bytes(
            harness.carrier.canonical_json_bytes(list(root_tokens))
        ),
        "prior_generated_token_sha256": prior_state["generated_token_sha256"],
        "prior_generated_tokens_exact_across_root_boundary": True,
        "suffix_token_count": len(suffix["suffix_tokens"]),
        "suffix_token_sha256": suffix["suffix_token_sha256"],
        "request_token_count": len(tokens),
        "request_token_sha256": harness.sha256_bytes(
            harness.carrier.canonical_json_bytes(tokens)
        ),
        "visible_output_retokenized": False,
    }
    return tokens, payload, ancestry


def root_action(
    *,
    action: str,
    root_id: str,
    expected: Mapping[str, Any] | None = None,
    expected_tokens: int | None = None,
    label: str,
) -> dict[str, Any]:
    raw, wall = harness.ram_root_action(action=action, root_id=root_id)
    record = validate_named_root(
        raw,
        action=action,
        root_id=root_id,
        expected=expected,
        expected_tokens=expected_tokens,
    )
    record.update(label=label, client_wall_seconds=wall)
    return record


def promote_live_root(
    *,
    current_root: Mapping[str, Any],
    next_root_id: str,
    next_root_tokens: Sequence[int],
    label: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    erased = root_action(
        action="root-erase",
        root_id=str(current_root["root_id"]),
        expected=current_root,
        expected_tokens=int(current_root["n_tokens"]),
        label=f"{label}:erase-parent",
    )
    require(
        erased["n_device_bytes_after"] == 0 and erased["n_gpu_bytes_after"] == 0,
        "parent root did not close before child save",
    )
    saved = root_action(
        action="root-save",
        root_id=next_root_id,
        expected_tokens=len(next_root_tokens),
        label=f"{label}:save-child",
    )
    return saved, [erased, saved]


def run_route(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    current_root: Mapping[str, Any],
    current_root_tokens: Sequence[int],
    prior_state: Mapping[str, Any],
    step: int,
    route: str,
) -> tuple[dict[str, Any], list[int]]:
    require(route in {"catalytic", "direct"}, "unsupported rolling route")
    restore: dict[str, Any] | None = None
    restore_wall = 0.0
    if route == "catalytic":
        restore = root_action(
            action="root-restore",
            root_id=str(current_root["root_id"]),
            expected=current_root,
            expected_tokens=len(current_root_tokens),
            label=f"step-{step}:restore-current-root",
        )
        restore_wall = float(restore["client_wall_seconds"])
    tokens, payload, ancestry = derive_promoted_successor(
        codec=codec,
        root_tokens=current_root_tokens,
        prior_state=prior_state,
        seed=shared_tasks.derive_seed(fixed.ROOT_ID, f"rolling-root-step-{step}"),
        cache_prompt=route == "catalytic",
    )
    recorder = latency.TimingRecorder()
    record = harness.run_completion(
        sidecar,
        f"{fixed.ROOT_ID}:rolling-root:step-{step}:{route}",
        payload,
        recorder=recorder,
        batch_owned_request=True,
    )
    state = fixed.generated_state(record, codec=codec, props=props)
    expected_answer = fixed.TRANSITION[str(prior_state["answer"])]
    require(state["answer"] == expected_answer, f"rolling step {step} answer is incorrect")
    require(record["prompt_tokens"] == len(tokens), f"rolling step {step} prompt count changed")
    expected_cached = len(current_root_tokens) if route == "catalytic" else 0
    require(record["cached_prompt_tokens"] == expected_cached, f"rolling step {step} cache count changed")
    require(
        record["fresh_prompt_tokens"] == len(tokens) - expected_cached,
        f"rolling step {step} fresh-token count changed",
    )
    timing = recorder.summary(request_wall_seconds=float(record["wall_seconds"]))
    require(
        timing["server_prompt_n"] == record["fresh_prompt_tokens"],
        "rolling server prompt timing differs from fresh-token count",
    )
    require(
        timing["server_predicted_n"] == record["completion_tokens"],
        "rolling generation timing differs from completion count",
    )
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
    next_root_tokens = [*tokens, *state["visible_token_ids"]]
    return record, next_root_tokens


def classify(*, integrity: bool, boundary_growth: bool, lifecycle_speedup: float) -> str:
    if not integrity:
        return "rolling-output-root-promotion-integrity-failure"
    if not boundary_growth:
        return "rolling-output-root-promotion-without-boundary-growth"
    if lifecycle_speedup < MIN_FULL_LIFECYCLE_WALL_SPEEDUP:
        return "rolling-output-root-promotion-without-preregistered-wall-gate"
    return "rolling-output-bearing-cuda-root-promotion-r3-supported-bounded"


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
    require(seed_spec["answer"] == fixed.SEED_EXPECTED_ANSWER, "rolling seed answer changed")

    prompt_text = codec.render_messages(
        harness.carrier.task_a_messages(root),
        harness.carrier.CHAT_TEMPLATE_KWARGS,
    )
    prompt_tokens = codec.tokenize(prompt_text)
    require(len(prompt_tokens) == latency.EXPECTED_PROMPT_ROOT_TOKENS, "Task-A prompt count changed")
    task_payload = harness.carrier._task_a_payload(
        prompt_tokens,
        seed=shared_tasks.derive_seed(fixed.ROOT_ID, "task-a"),
    )
    task_a = harness.run_completion(sidecar, f"{fixed.ROOT_ID}:rolling-root:task-a", task_payload)
    parsed_task_a = harness.carrier.parse_task_a_output(task_a["content"])
    require(parsed_task_a["answer"] == harness.EXPECTED[fixed.ROOT_ID]["task_a"], "Task-A answer changed")
    retained = harness.carrier.derive_retained_root(
        harness.root_capture(task_a, task_payload),
        prompt_tokens,
        codec,
        props,
    )
    require(
        int(retained["retained_root_token_count"]) == latency.EXPECTED_RETAINED_ROOT_TOKENS,
        "retained root count changed",
    )
    base_branch_tokens, _ = latency.branch_request(codec, retained, seed_spec, cache_prompt=False)
    require(len(base_branch_tokens) == latency.EXPECTED_BRANCH_PROMPT_TOKENS, "seed prompt count changed")
    parent_tokens = list(base_branch_tokens[:-1])
    require(len(parent_tokens) == fixed.ROOT_TOKEN_COUNT, "parent strict-prefix count changed")

    materialize_payload = harness.carrier._branch_payload(
        parent_tokens,
        seed=shared_tasks.derive_seed(fixed.ROOT_ID, "rolling-parent-materialize"),
        cache_prompt=False,
        n_predict=0,
    )
    materialization = harness.run_completion(
        sidecar,
        f"{fixed.ROOT_ID}:rolling-root:parent-materialize",
        materialize_payload,
        operation_kind="zero-output-root-readdress",
    )
    require(materialization["prompt_tokens"] == len(parent_tokens), "parent materialization count changed")
    require(materialization["cached_prompt_tokens"] == 0, "parent materialization reused cache")
    require(materialization["completion_tokens"] == 0, "parent materialization emitted output")
    parent_saved = root_action(
        action="root-save",
        root_id=PARENT_ROOT_ID,
        expected_tokens=len(parent_tokens),
        label="initial-parent-save",
    )
    root_operations: list[dict[str, Any]] = [parent_saved]
    resources_with_parent = harness.process_resources(sidecar, baseline_private)

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

    ownership_boundary("pre-rolling-output-root-batch")

    seed_restore = root_action(
        action="root-restore",
        root_id=PARENT_ROOT_ID,
        expected=parent_saved,
        expected_tokens=len(parent_tokens),
        label="before-seed",
    )
    root_operations.append(seed_restore)
    seed_payload = harness.carrier._branch_payload(
        base_branch_tokens,
        seed=shared_tasks.derive_seed(fixed.ROOT_ID, f"branch-{fixed.SEED_BRANCH_NUMBER}"),
        cache_prompt=True,
    )
    seed_record = harness.run_completion(
        sidecar,
        f"{fixed.ROOT_ID}:rolling-root:seed",
        seed_payload,
        batch_owned_request=True,
    )
    seed_state = fixed.generated_state(seed_record, codec=codec, props=props)
    require(seed_state["answer"] == fixed.SEED_EXPECTED_ANSWER, "rolling seed output changed")
    require(
        seed_state["generated_token_sha256"] == fixed.SEED_GENERATED_SHA256,
        "rolling seed token identity changed",
    )
    require(
        seed_record["cached_prompt_tokens"] == fixed.ROOT_TOKEN_COUNT
        and seed_record["fresh_prompt_tokens"] == 1,
        "rolling seed cache split changed",
    )
    seed_child_tokens = [*base_branch_tokens, *seed_state["visible_token_ids"]]
    current_root, promotion = promote_live_root(
        current_root=parent_saved,
        next_root_id=child_root_id(0, seed_state["answer"]),
        next_root_tokens=seed_child_tokens,
        label="seed-promotion",
    )
    root_operations.extend(promotion)
    current_root_tokens = seed_child_tokens
    prior_state = seed_state
    resources_after_seed_promotion = harness.process_resources(sidecar, baseline_private)

    step_records: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    observed_sequence = [seed_state["answer"]]
    cumulative_avoided = 0
    for step, route_order in enumerate(PAIR_ROUTE_ORDERS, start=1):
        pair: dict[str, dict[str, Any]] = {}
        promoted_root: dict[str, Any] | None = None
        promoted_tokens: list[int] | None = None
        promotion_records: list[dict[str, Any]] = []
        for route in route_order:
            record, next_tokens = run_route(
                sidecar=sidecar,
                codec=codec,
                props=props,
                current_root=current_root,
                current_root_tokens=current_root_tokens,
                prior_state=prior_state,
                step=step,
                route=route,
            )
            pair[route] = record
            step_records.append(record)
            if route == "catalytic":
                promoted_tokens = next_tokens
                promoted_root, promotion_records = promote_live_root(
                    current_root=current_root,
                    next_root_id=child_root_id(step, record["state"]["answer"]),
                    next_root_tokens=promoted_tokens,
                    label=f"step-{step}-promotion",
                )
                root_operations.extend(promotion_records)
        require(set(pair) == {"catalytic", "direct"}, "rolling pair lost a route")
        catalytic = pair["catalytic"]
        direct = pair["direct"]
        require(
            catalytic["prompt_token_sha256"] == direct["prompt_token_sha256"],
            "rolling pair prompt hashes differ",
        )
        require(
            catalytic["state"]["generated_token_ids"] == direct["state"]["generated_token_ids"],
            "rolling pair generated-token arrays differ",
        )
        require(promoted_root is not None and promoted_tokens is not None, "rolling child promotion is missing")
        require(
            promoted_root["n_tokens"] == len(promoted_tokens),
            "promoted child root token count differs from exact output-bearing state",
        )
        avoided = int(direct["fresh_prompt_tokens"]) - int(catalytic["fresh_prompt_tokens"])
        require(avoided == len(current_root_tokens), "rolling avoided-work count differs from root size")
        cumulative_avoided += avoided
        agreed_state = dict(catalytic["state"])
        observed_sequence.append(str(agreed_state["answer"]))
        steps.append(
            {
                "step": step,
                "route_order": list(route_order),
                "prior_answer": prior_state["answer"],
                "answer": agreed_state["answer"],
                "parent_root_id": current_root["root_id"],
                "parent_root_tokens": len(current_root_tokens),
                "child_root_id": promoted_root["root_id"],
                "child_root_tokens": len(promoted_tokens),
                "root_growth_tokens": len(promoted_tokens) - len(current_root_tokens),
                "fresh_suffix_tokens": catalytic["fresh_prompt_tokens"],
                "direct_prompt_tokens": direct["fresh_prompt_tokens"],
                "avoided_fresh_prompt_tokens": avoided,
                "cumulative_avoided_fresh_prompt_tokens": cumulative_avoided,
                "prompt_token_sha256": catalytic["prompt_token_sha256"],
                "generated_token_sha256": agreed_state["generated_token_sha256"],
                "prior_generated_token_sha256": catalytic["ancestry"][
                    "prior_generated_token_sha256"
                ],
                "prior_generated_tokens_exact_across_root_boundary": catalytic["ancestry"][
                    "prior_generated_tokens_exact_across_root_boundary"
                ],
                "paired_prompt_identity_exact": True,
                "paired_generated_identity_exact": True,
                "parent_erased_before_child_save": (
                    promotion_records[0]["action"] == "root-erase"
                    and promotion_records[1]["action"] == "root-save"
                ),
            }
        )
        current_root = promoted_root
        current_root_tokens = promoted_tokens
        prior_state = agreed_state

    ownership_boundary("post-rolling-output-root-batch")
    ownership_total = sum(float(item["client_wall_seconds"]) for item in ownership)
    ownership_share = ownership_total / len(step_records)
    for record in step_records:
        record["batch_ownership_amortized_seconds"] = ownership_share
        record["effective_wall_seconds"] = float(record["effective_wall_seconds"]) + ownership_share

    final_restore = root_action(
        action="root-restore",
        root_id=str(current_root["root_id"]),
        expected=current_root,
        expected_tokens=len(current_root_tokens),
        label="final-promoted-root-restore",
    )
    root_operations.append(final_restore)
    resources_before_final_erase = harness.process_resources(sidecar, baseline_private)
    final_erase = root_action(
        action="root-erase",
        root_id=str(current_root["root_id"]),
        expected=current_root,
        expected_tokens=len(current_root_tokens),
        label="final-promoted-root-erase",
    )
    root_operations.append(final_erase)
    resources_after_final_erase = harness.process_resources(sidecar, baseline_private)

    catalytic_records = [record for record in step_records if record["route"] == "catalytic"]
    direct_records = [record for record in step_records if record["route"] == "direct"]
    non_request_root_wall = float(materialization["wall_seconds"]) + sum(
        float(operation["client_wall_seconds"])
        for operation in root_operations
        if operation["action"] != "root-restore"
    )
    seed_restore_wall = float(seed_restore["client_wall_seconds"])
    final_restore_wall = float(final_restore["client_wall_seconds"])
    root_setup_promotion_closure_wall = (
        non_request_root_wall + seed_restore_wall + final_restore_wall
    )
    catalytic_lifecycle_wall = root_setup_promotion_closure_wall + sum(
        float(record["effective_wall_seconds"]) for record in catalytic_records
    )
    direct_lifecycle_wall = sum(
        float(record["effective_wall_seconds"]) for record in direct_records
    )
    lifecycle_speedup = direct_lifecycle_wall / catalytic_lifecycle_wall
    root_counts = [int(step["parent_root_tokens"]) for step in steps]
    child_counts = [int(step["child_root_tokens"]) for step in steps]
    boundary_growth = all(child > parent for parent, child in zip(root_counts, child_counts))
    exact_sequence = tuple(observed_sequence) == EXPECTED_STATE_SEQUENCE
    paired_identity = all(
        step["paired_prompt_identity_exact"] is True
        and step["paired_generated_identity_exact"] is True
        and step["prior_generated_tokens_exact_across_root_boundary"] is True
        for step in steps
    )
    promotion_order = all(step["parent_erased_before_child_save"] is True for step in steps)
    root_restore_invariants = all(
        operation["n_checkpoints"] == 0
        and operation["n_device_bytes"] > 0
        and operation["n_gpu_bytes"] > 0
        for operation in root_operations
    )
    integrity = (
        exact_sequence
        and paired_identity
        and promotion_order
        and root_restore_invariants
        and final_erase["n_device_bytes_after"] == 0
        and final_erase["n_gpu_bytes_after"] == 0
    )
    classification = classify(
        integrity=integrity,
        boundary_growth=boundary_growth,
        lifecycle_speedup=lifecycle_speedup,
    )
    accepted_before_cleanup = (
        classification == "rolling-output-bearing-cuda-root-promotion-r3-supported-bounded"
    )
    return {
        "status": "complete-pending-cleanup",
        "experiment_id": EXPERIMENT_ID,
        "mechanism": "rolling-single-slot-output-bearing-cuda-root-promotion",
        "verdict": "accept" if accepted_before_cleanup else "reject",
        "classification": classification,
        "geometry": {"N": 1, "T": 3, "R": 3, "B": 1},
        "claim_ceiling": (
            "bounded rolling output-bearing CUDA-root promotion with growing exact cached boundary"
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
        "records": step_records,
        "roots": {
            "initial_parent": parent_saved,
            "seed_output_root": {
                "root_id": child_root_id(0, seed_state["answer"]),
                "n_tokens": len(seed_child_tokens),
                "token_sha256": harness.sha256_bytes(
                    harness.carrier.canonical_json_bytes(seed_child_tokens)
                ),
            },
            "final_root": current_root,
            "final_root_token_count": len(current_root_tokens),
            "final_root_token_sha256": harness.sha256_bytes(
                harness.carrier.canonical_json_bytes(current_root_tokens)
            ),
            "operations": root_operations,
            "maximum_simultaneous_roots": 1,
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
            "boundary_growth": {
                "parent_root_tokens": root_counts,
                "child_root_tokens": child_counts,
                "per_step_growth_tokens": [
                    child - parent for parent, child in zip(root_counts, child_counts)
                ],
                "all_steps_grew": boundary_growth,
                "cumulative_avoided_fresh_prompt_tokens": cumulative_avoided,
            },
            "counted_full_lifecycle": {
                "scope": (
                    "three paired dependent transitions; catalytic includes initial materialization/save, "
                    "seed restore and promotion, every request restore, every parent erase/child save, "
                    "final restore/erase, and equal batch-ownership share; Task-A and seed generation shared"
                ),
                "root_setup_promotion_closure_wall_seconds": root_setup_promotion_closure_wall,
                "catalytic_wall_seconds": catalytic_lifecycle_wall,
                "direct_wall_seconds": direct_lifecycle_wall,
                "wall_speedup": lifecycle_speedup,
                "minimum_wall_speedup": MIN_FULL_LIFECYCLE_WALL_SPEEDUP,
            },
            "residency": {
                "with_parent": resources_with_parent,
                "after_seed_promotion": resources_after_seed_promotion,
                "before_final_erase": resources_before_final_erase,
                "after_final_erase": resources_after_final_erase,
                "maximum_simultaneous_roots": 1,
            },
        },
        "quality_gates": {
            "qualified_panel_identity_exact": True,
            "seed_output_and_generated_token_identity_exact": True,
            "state_sequence_C_D_B_B_exact": exact_sequence,
            "final_B_to_B_fixed_point_exact": observed_sequence[-2:] == ["B", "B"],
            "paired_prompt_and_generated_identity_exact": paired_identity,
            "prior_generated_tokens_exact_across_each_root_boundary": paired_identity,
            "parent_erased_before_every_child_save": promotion_order,
            "every_promoted_root_token_count_exact": all(
                step["child_root_tokens"] == step["parent_root_tokens"] + step["root_growth_tokens"]
                for step in steps
            ),
            "cached_boundary_grew_each_step": boundary_growth,
            "catalytic_cached_tokens_equal_current_root": all(
                record["cached_prompt_tokens"] == record["ancestry"]["root_token_count"]
                for record in catalytic_records
            ),
            "direct_cached_prompt_tokens_zero": all(
                record["cached_prompt_tokens"] == 0 for record in direct_records
            ),
            "checkpoint_count_zero": all(
                operation["n_checkpoints"] == 0 for operation in root_operations
            ),
            "root_restore_metadata_invariant": root_restore_invariants,
            "maximum_one_root_resident": True,
            "final_device_and_gpu_bytes_zero_after_erase": (
                final_erase["n_device_bytes_after"] == 0
                and final_erase["n_gpu_bytes_after"] == 0
            ),
            "batch_ownership_boundaries_exact": all(
                item["evidence"].get("passed") is True for item in ownership
            ),
            "fully_counted_wall_speedup_at_least_1_25": (
                lifecycle_speedup >= MIN_FULL_LIFECYCLE_WALL_SPEEDUP
            ),
            "fanout_claimed": False,
            "multi_root_bank_claimed": False,
            "restart_persistence_claimed": False,
            "unbounded_catalytic_inference_established": False,
            "automatic_promotion": False,
        },
        "next_boundary": (
            "PRESERVE_R3_PROMOTION_EVIDENCE_AND_DESIGN_LONGER_DEPTH_SCALING_WITH_CONTEXT_BOUND_ACCOUNTING"
            if accepted_before_cleanup
            else "PRESERVE_R3_PROMOTION_EVIDENCE_AND_LOCALIZE_THE_FIRST_FAILED_GATE_WITHOUT_RETRY"
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
        rolling_output_bearing_cuda_root_promotion_supported=accepted,
    )
    result["status"] = "complete"
    result["verdict"] = "accept" if accepted else "reject"
    if accepted:
        result["classification"] = "rolling-output-bearing-cuda-root-promotion-r3-supported-bounded"
        result["next_boundary"] = (
            "PRESERVE_R3_PROMOTION_EVIDENCE_AND_DESIGN_LONGER_DEPTH_SCALING_WITH_CONTEXT_BOUND_ACCOUNTING"
        )
    elif scientific_gate:
        result["classification"] = "rolling-output-root-promotion-cleanup-or-residency-failure"
        result["next_boundary"] = (
            "PRESERVE_R3_PROMOTION_EVIDENCE_AND_LOCALIZE_CLEANUP_OR_RESIDENCY_FAILURE_WITHOUT_RETRY"
        )
    return result


def main() -> int:
    args = parse_args()
    repository = Path(__file__).resolve().parents[1]
    binary = args.binary.resolve(strict=True)
    require(
        binary == (repository / DEFAULT_BINARY).resolve(strict=True),
        "rolling promotion requires the isolated candidate binary",
    )
    cuda_runtime_sha256 = latency.verify_cuda_root_runtime(binary)
    model = args.model.resolve(strict=True)
    latency.require_unused_artifact_paths(args.output, args.server_log_output)
    corpus = harness.carrier.load_public_corpus(repository)
    roots = {str(item["root_id"]): item for item in corpus["roots"]}
    evaluator, live_contract = harness.load_discovery_sidecar_contract()
    stable_pids = harness.live_runtime.require_stable()
    require(len(stable_pids) == 1, "rolling promotion requires the sole stable listener")
    require(not harness.live_runtime.listener_pids(harness.live_runtime.PORT), "frontier port is occupied")
    state_root = Path(tempfile.mkdtemp(prefix="neo3000-rolling-root-promotion-"))
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
            "rolling promotion launch identity changed",
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
    require(result is not None, "rolling promotion result is missing")
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
