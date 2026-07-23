#!/usr/bin/env python3
"""neo-exp-0073 output-derived fixed-point recurrence on one CUDA root.

The accepted 689-token strict-prefix CUDA root remains invariant.  A verified
branch-7 answer seeds a dependent C -> D -> B -> B transition chain.  Each
successor prompt contains the exact prior generated token IDs, restores the
same root, and is paired with an identical cache-disabled direct request.
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
import catalytic_frontier_single_request_latency as latency
import catalytic_frontier_water_panel_qualifier as water


EXPERIMENT_ID = "neo-exp-0073"
ROOT_ID = latency.ROOT_ID
ROOT_TOKEN_COUNT = 689
SEED_BRANCH_NUMBER = 7
SEED_EXPECTED_ANSWER = "C"
SEED_GENERATED_SHA256 = "BD33E852EF9FDDEE49A1056501456071169FF3E3C7699C2A5BAAA2D0DF30CABC"
TRANSITION = {"A": "C", "B": "B", "C": "D", "D": "B"}
EXPECTED_STATE_SEQUENCE = ("C", "D", "B", "B")
PAIR_ROUTE_ORDERS = (
    ("catalytic", "direct"),
    ("direct", "catalytic"),
    ("catalytic", "direct"),
)
MIN_FULL_LIFECYCLE_WALL_SPEEDUP = 1.25
MAX_WDDM_BYTES = 6000 * 1024 * 1024
PANEL_SHA256 = latency.PANEL_SHA256
DEFAULT_BINARY = latency.DEFAULT_BINARY


def require(condition: bool, message: str) -> None:
    harness.require(condition, message)


def transition_user_content() -> str:
    return (
        "RECURSIVE CATALYTIC STEP\n"
        "Treat the exact JSON answer in the immediately preceding assistant message as the sole input state. "
        "Apply exactly one transition from this table: A -> C; B -> B; C -> D; D -> B. "
        "Return only JSON of the form {\"answer\":\"A\"}, with the transitioned letter and no other text."
    )


def generated_state(
    record: Mapping[str, Any],
    *,
    codec: Any,
    props: Mapping[str, Any],
) -> dict[str, Any]:
    execution = record["execution"]
    generated = execution.get("generated_token_ids")
    require(
        isinstance(generated, list)
        and len(generated) >= 2
        and all(type(item) is int for item in generated),
        "output-derived state lacks exact generated token IDs",
    )
    require(execution.get("finish_reason") == "eos", "output-derived state did not terminate with EOS")
    terminal_eog = int(generated[-1])
    eos_piece = str(props.get("eos_token") or "")
    require(bool(eos_piece), "runtime EOS identity is absent")
    require(codec.detokenize([terminal_eog]) == eos_piece, "generated terminal token is not runtime EOS")
    require(codec.tokenize(eos_piece) == [terminal_eog], "runtime EOS does not round-trip exactly")
    visible_ids = list(generated[:-1])
    content = str(record.get("content") or "")
    require(codec.detokenize(visible_ids) == content, "visible generated IDs do not reconstruct output")
    answer = harness.carrier.parse_branch_output(content)
    require(
        execution.get("reasoning_content") in {"", None} and not execution.get("tool_calls"),
        "hidden reasoning or tools entered recursive state",
    )
    generated_sha256 = harness.sha256_bytes(harness.carrier.canonical_json_bytes(generated))
    require(
        execution.get("generated_token_sha256") == generated_sha256,
        "server generated-token hash differs from exact IDs",
    )
    return {
        "answer": answer,
        "content": content,
        "generated_token_ids": list(generated),
        "visible_token_ids": visible_ids,
        "terminal_eog_id": terminal_eog,
        "generated_token_sha256": generated_sha256,
        "visible_token_sha256": harness.sha256_bytes(
            harness.carrier.canonical_json_bytes(visible_ids)
        ),
    }


def derive_transition_request(
    *,
    codec: Any,
    base_branch_tokens: Sequence[int],
    root_tokens: Sequence[int],
    prior_state: Mapping[str, Any],
    seed: int,
    cache_prompt: bool,
) -> tuple[list[int], dict[str, Any], dict[str, Any]]:
    require(len(root_tokens) == ROOT_TOKEN_COUNT, "recursive root token count changed")
    require(
        list(base_branch_tokens[:ROOT_TOKEN_COUNT]) == list(root_tokens),
        "base branch no longer begins with the exact CUDA root",
    )
    generated = list(prior_state["generated_token_ids"])
    visible = list(prior_state["visible_token_ids"])
    require(
        generated == [*visible, int(prior_state["terminal_eog_id"])],
        "prior generated state is not visible IDs plus terminal EOS",
    )
    suffix = harness.carrier.derive_continuation_suffix(
        codec,
        terminal_eog_id=int(prior_state["terminal_eog_id"]),
        user_content=transition_user_content(),
    )
    tokens = [*base_branch_tokens, *visible, *suffix["suffix_tokens"]]
    require(tokens[:ROOT_TOKEN_COUNT] == list(root_tokens), "recursive request lost exact root prefix")
    generated_start = len(base_branch_tokens)
    require(
        tokens[generated_start : generated_start + len(generated)] == generated,
        "recursive request does not contain the exact prior generated token array",
    )
    payload = harness.carrier._branch_payload(tokens, seed=seed, cache_prompt=cache_prompt)
    ancestry = {
        "prior_answer": prior_state["answer"],
        "prior_generated_token_sha256": prior_state["generated_token_sha256"],
        "prior_generated_token_count": len(generated),
        "prior_generated_tokens_exact_in_request": True,
        "prior_generated_token_offset": generated_start,
        "root_prefix_token_count": ROOT_TOKEN_COUNT,
        "root_prefix_sha256": harness.sha256_bytes(
            harness.carrier.canonical_json_bytes(list(root_tokens))
        ),
        "suffix_token_count": len(suffix["suffix_tokens"]),
        "suffix_token_sha256": suffix["suffix_token_sha256"],
        "request_token_count": len(tokens),
        "request_token_sha256": harness.sha256_bytes(
            harness.carrier.canonical_json_bytes(tokens)
        ),
        "visible_content_retokenized": False,
    }
    return tokens, payload, ancestry


def validate_root(
    response: Mapping[str, Any],
    *,
    action: str,
    expected: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    value = latency.validate_root_response(
        response,
        action=action,
        expected=expected,
        root_storage="device",
    )
    require(value["n_tokens"] == ROOT_TOKEN_COUNT, "recursive CUDA root token count changed")
    require(
        value["n_bytes"] == latency.STRICT_PREFIX_LOGICAL_ROOT_BYTES,
        "recursive CUDA root logical size changed",
    )
    return value


def run_recursive_route(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    root_tokens: Sequence[int],
    base_branch_tokens: Sequence[int],
    saved_root: Mapping[str, Any],
    prior_state: Mapping[str, Any],
    step: int,
    route: str,
) -> dict[str, Any]:
    require(route in {"catalytic", "direct"}, "unsupported recursive route")
    restore: dict[str, Any] | None = None
    restore_wall = 0.0
    if route == "catalytic":
        raw, restore_wall = harness.ram_root_action(action="root-restore", root_id=ROOT_ID)
        restore = validate_root(raw, action="root-restore", expected=saved_root)
        restore.update(label=f"before-step-{step}-{route}", client_wall_seconds=restore_wall)
    tokens, payload, ancestry = derive_transition_request(
        codec=codec,
        base_branch_tokens=base_branch_tokens,
        root_tokens=root_tokens,
        prior_state=prior_state,
        seed=shared_tasks.derive_seed(ROOT_ID, f"output-fixed-point-step-{step}"),
        cache_prompt=route == "catalytic",
    )
    recorder = latency.TimingRecorder()
    record = harness.run_completion(
        sidecar,
        f"{ROOT_ID}:output-fixed-point:step-{step}:{route}",
        payload,
        recorder=recorder,
        batch_owned_request=True,
    )
    state = generated_state(record, codec=codec, props=props)
    expected_answer = TRANSITION[str(prior_state["answer"])]
    require(state["answer"] == expected_answer, f"recursive step {step} answer is incorrect")
    require(record["prompt_tokens"] == len(tokens), f"recursive step {step} prompt count changed")
    if route == "catalytic":
        require(record["cached_prompt_tokens"] == ROOT_TOKEN_COUNT, "catalytic recursive cache count changed")
    else:
        require(record["cached_prompt_tokens"] == 0, "direct recursive route reused cache")
    require(
        record["fresh_prompt_tokens"] == len(tokens) - (ROOT_TOKEN_COUNT if route == "catalytic" else 0),
        f"recursive step {step} fresh-token count changed",
    )
    timing = recorder.summary(request_wall_seconds=float(record["wall_seconds"]))
    require(
        timing["server_prompt_n"] == record["fresh_prompt_tokens"],
        "recursive server prompt timing differs from fresh-token count",
    )
    require(
        timing["server_predicted_n"] == record["completion_tokens"],
        "recursive server generation timing differs from completion count",
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
    return record


def classify(
    *,
    integrity: bool,
    saved_work_law: bool,
    lifecycle_speedup: float,
) -> str:
    if not integrity:
        return "output-derived-fixed-point-integrity-failure"
    if not saved_work_law:
        return "output-derived-fixed-point-saved-work-law-failure"
    if lifecycle_speedup < MIN_FULL_LIFECYCLE_WALL_SPEEDUP:
        return "output-derived-fixed-point-without-preregistered-wall-gate"
    return "cuda-root-output-derived-fixed-point-r3-supported-bounded"


def evaluate(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    root: Mapping[str, Any],
    baseline_private: int | None,
) -> dict[str, Any]:
    panel = water.panel_for(root)
    require(water.base._panel_hash(panel) == PANEL_SHA256, "qualified water panel identity changed")
    seed_spec = panel[SEED_BRANCH_NUMBER - 1]
    require(seed_spec["answer"] == SEED_EXPECTED_ANSWER, "fixed-point seed answer changed")

    prompt_text = codec.render_messages(
        harness.carrier.task_a_messages(root),
        harness.carrier.CHAT_TEMPLATE_KWARGS,
    )
    prompt_tokens = codec.tokenize(prompt_text)
    require(
        len(prompt_tokens) == latency.EXPECTED_PROMPT_ROOT_TOKENS,
        "fixed-point Task-A prompt token count changed",
    )
    task_payload = harness.carrier._task_a_payload(
        prompt_tokens,
        seed=shared_tasks.derive_seed(ROOT_ID, "task-a"),
    )
    task_a = harness.run_completion(sidecar, f"{ROOT_ID}:output-fixed-point:task-a", task_payload)
    parsed_task_a = harness.carrier.parse_task_a_output(task_a["content"])
    require(parsed_task_a["answer"] == harness.EXPECTED[ROOT_ID]["task_a"], "Task-A answer is incorrect")
    retained = harness.carrier.derive_retained_root(
        harness.root_capture(task_a, task_payload),
        prompt_tokens,
        codec,
        props,
    )
    require(
        int(retained["retained_root_token_count"]) == latency.EXPECTED_RETAINED_ROOT_TOKENS,
        "retained water root token count changed",
    )
    base_branch_tokens, _ = latency.branch_request(codec, retained, seed_spec, cache_prompt=False)
    require(
        len(base_branch_tokens) == latency.EXPECTED_BRANCH_PROMPT_TOKENS,
        "fixed-point seed branch prompt count changed",
    )
    root_tokens = list(base_branch_tokens[:-1])
    require(len(root_tokens) == ROOT_TOKEN_COUNT, "fixed-point strict-prefix root count changed")
    root_prefix_sha256 = harness.sha256_bytes(
        harness.carrier.canonical_json_bytes(root_tokens)
    )

    materialize_payload = harness.carrier._branch_payload(
        root_tokens,
        seed=shared_tasks.derive_seed(ROOT_ID, "output-fixed-point-root-materialize"),
        cache_prompt=False,
        n_predict=0,
    )
    materialization = harness.run_completion(
        sidecar,
        f"{ROOT_ID}:output-fixed-point:root-materialize",
        materialize_payload,
        operation_kind="zero-output-root-readdress",
    )
    require(materialization["prompt_tokens"] == ROOT_TOKEN_COUNT, "root materialization count changed")
    require(materialization["cached_prompt_tokens"] == 0, "root materialization reused cache")
    require(materialization["completion_tokens"] == 0, "root materialization emitted output")

    save_raw, save_wall = harness.ram_root_action(action="root-save", root_id=ROOT_ID)
    saved = validate_root(save_raw, action="root-save")
    saved.update(label="root-save", client_wall_seconds=save_wall)
    root_operations: list[dict[str, Any]] = [saved]
    resources_with_root = harness.process_resources(sidecar, baseline_private)

    batch_ownership: list[dict[str, Any]] = []

    def ownership_boundary(label: str) -> None:
        started = time.monotonic()
        evidence = sidecar.exact_ownership(label)
        batch_ownership.append(
            {
                "boundary": label,
                "client_wall_seconds": time.monotonic() - started,
                "evidence": evidence,
            }
        )

    ownership_boundary("pre-output-fixed-point-batch")

    seed_restore_raw, seed_restore_wall = harness.ram_root_action(
        action="root-restore",
        root_id=ROOT_ID,
    )
    seed_restore = validate_root(seed_restore_raw, action="root-restore", expected=saved)
    seed_restore.update(label="before-seed", client_wall_seconds=seed_restore_wall)
    root_operations.append(seed_restore)
    seed_payload = harness.carrier._branch_payload(
        base_branch_tokens,
        seed=shared_tasks.derive_seed(ROOT_ID, f"branch-{SEED_BRANCH_NUMBER}"),
        cache_prompt=True,
    )
    seed_record = harness.run_completion(
        sidecar,
        f"{ROOT_ID}:output-fixed-point:seed",
        seed_payload,
        batch_owned_request=True,
    )
    seed_state = generated_state(seed_record, codec=codec, props=props)
    require(seed_state["answer"] == SEED_EXPECTED_ANSWER, "fixed-point seed output changed")
    require(
        seed_state["generated_token_sha256"] == SEED_GENERATED_SHA256,
        "fixed-point seed generated-token identity changed",
    )
    require(
        seed_record["cached_prompt_tokens"] == ROOT_TOKEN_COUNT
        and seed_record["fresh_prompt_tokens"] == 1,
        "fixed-point seed cache split changed",
    )

    prior_state = seed_state
    step_records: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    cumulative_avoided = 0
    observed_sequence = [seed_state["answer"]]
    for step, route_order in enumerate(PAIR_ROUTE_ORDERS, start=1):
        records = [
            run_recursive_route(
                sidecar=sidecar,
                codec=codec,
                props=props,
                root_tokens=root_tokens,
                base_branch_tokens=base_branch_tokens,
                saved_root=saved,
                prior_state=prior_state,
                step=step,
                route=route,
            )
            for route in route_order
        ]
        by_route = {str(record["route"]): record for record in records}
        require(set(by_route) == {"catalytic", "direct"}, "recursive pair lost a route")
        catalytic = by_route["catalytic"]
        direct = by_route["direct"]
        require(
            catalytic["prompt_token_sha256"] == direct["prompt_token_sha256"],
            "recursive pair prompt-token identity differs",
        )
        require(
            catalytic["state"]["generated_token_ids"] == direct["state"]["generated_token_ids"],
            "recursive pair generated-token identity differs",
        )
        avoided = int(direct["fresh_prompt_tokens"]) - int(catalytic["fresh_prompt_tokens"])
        cumulative_avoided += avoided
        require(avoided == ROOT_TOKEN_COUNT, "recursive step avoided-work count changed")
        require(
            cumulative_avoided == ROOT_TOKEN_COUNT * step,
            "recursive cumulative avoided-work law changed",
        )
        agreed_state = dict(catalytic["state"])
        observed_sequence.append(str(agreed_state["answer"]))
        steps.append(
            {
                "step": step,
                "route_order": list(route_order),
                "prior_answer": prior_state["answer"],
                "answer": agreed_state["answer"],
                "prompt_token_sha256": catalytic["prompt_token_sha256"],
                "generated_token_sha256": agreed_state["generated_token_sha256"],
                "paired_prompt_token_identity_exact": (
                    catalytic["prompt_token_sha256"] == direct["prompt_token_sha256"]
                ),
                "paired_generated_token_identity_exact": (
                    catalytic["state"]["generated_token_ids"]
                    == direct["state"]["generated_token_ids"]
                ),
                "prior_generated_token_sha256": catalytic["ancestry"][
                    "prior_generated_token_sha256"
                ],
                "prior_generated_tokens_exact_in_request": catalytic["ancestry"][
                    "prior_generated_tokens_exact_in_request"
                ],
                "catalytic_cached_prompt_tokens": catalytic["cached_prompt_tokens"],
                "direct_cached_prompt_tokens": direct["cached_prompt_tokens"],
                "avoided_fresh_prompt_tokens": avoided,
                "cumulative_avoided_fresh_prompt_tokens": cumulative_avoided,
                "constructed_after_prior_pair_agreement": True,
            }
        )
        step_records.extend(records)
        prior_state = agreed_state

    ownership_boundary("post-output-fixed-point-batch")
    batch_ownership_total = sum(
        float(item["client_wall_seconds"]) for item in batch_ownership
    )
    batch_share = batch_ownership_total / len(step_records)
    for record in step_records:
        record["batch_ownership_amortized_seconds"] = batch_share
        record["effective_wall_seconds"] = (
            float(record["effective_wall_seconds"]) + batch_share
        )

    final_restore_raw, final_restore_wall = harness.ram_root_action(
        action="root-restore",
        root_id=ROOT_ID,
    )
    final_restore = validate_root(final_restore_raw, action="root-restore", expected=saved)
    final_restore.update(label="final-root-closure", client_wall_seconds=final_restore_wall)
    root_operations.append(final_restore)
    resources_before_erase = harness.process_resources(sidecar, baseline_private)
    erase_raw, erase_wall = harness.ram_root_action(action="root-erase", root_id=ROOT_ID)
    erased = validate_root(erase_raw, action="root-erase", expected=saved)
    erased.update(label="root-erase", client_wall_seconds=erase_wall)
    root_operations.append(erased)
    resources_after_erase = harness.process_resources(sidecar, baseline_private)

    catalytic_records = [record for record in step_records if record["route"] == "catalytic"]
    direct_records = [record for record in step_records if record["route"] == "direct"]
    root_setup_and_closure_wall = (
        float(materialization["wall_seconds"])
        + save_wall
        + seed_restore_wall
        + final_restore_wall
        + erase_wall
    )
    catalytic_lifecycle_wall = root_setup_and_closure_wall + sum(
        float(record["effective_wall_seconds"]) for record in catalytic_records
    )
    direct_lifecycle_wall = sum(
        float(record["effective_wall_seconds"]) for record in direct_records
    )
    lifecycle_speedup = direct_lifecycle_wall / catalytic_lifecycle_wall
    root_metadata_invariant = all(
        operation["n_tokens"] == saved["n_tokens"]
        and operation["n_bytes"] == saved["n_bytes"]
        and operation["n_device_bytes"] == saved["n_device_bytes"]
        and operation["n_gpu_bytes"] == saved["n_gpu_bytes"]
        and operation["n_checkpoints"] == 0
        for operation in root_operations
    )
    pair_identity = all(
        step["prior_generated_tokens_exact_in_request"] is True
        and step["paired_prompt_token_identity_exact"] is True
        and step["paired_generated_token_identity_exact"] is True
        and step["catalytic_cached_prompt_tokens"] == ROOT_TOKEN_COUNT
        and step["direct_cached_prompt_tokens"] == 0
        for step in steps
    )
    saved_work_law = all(
        step["cumulative_avoided_fresh_prompt_tokens"] == ROOT_TOKEN_COUNT * step["step"]
        for step in steps
    )
    chain_exact = tuple(observed_sequence) == EXPECTED_STATE_SEQUENCE
    integrity = (
        pair_identity
        and chain_exact
        and root_metadata_invariant
        and saved_work_law
        and erased["n_device_bytes_after"] == 0
        and erased["n_gpu_bytes_after"] == 0
    )
    classification = classify(
        integrity=integrity,
        saved_work_law=saved_work_law,
        lifecycle_speedup=lifecycle_speedup,
    )
    accepted_before_cleanup = (
        classification == "cuda-root-output-derived-fixed-point-r3-supported-bounded"
    )
    return {
        "status": "complete-pending-cleanup",
        "experiment_id": EXPERIMENT_ID,
        "mechanism": "exact-output-derived-fixed-point-recurrence-over-one-invariant-cuda-root",
        "verdict": "accept" if accepted_before_cleanup else "reject",
        "classification": classification,
        "geometry": {"N": 1, "T": 3, "R": 3, "B": 1},
        "claim_ceiling": (
            "bounded output-derived recursive reuse through one invariant CUDA root with "
            "finite linear saved-work and constant-residency evidence"
        ),
        "root": {
            "root_id": ROOT_ID,
            "root_prefix_token_count": ROOT_TOKEN_COUNT,
            "root_prefix_sha256": root_prefix_sha256,
            "storage": "device",
            "saved": saved,
            "operations": root_operations,
            "metadata_invariant": root_metadata_invariant,
        },
        "shared_prerequisite": {
            "task_a": harness.token_summary(task_a),
            "seed": {
                **harness.token_summary(seed_record),
                "answer": seed_state["answer"],
                "generated_token_sha256": seed_state["generated_token_sha256"],
                "restore_client_wall_seconds": seed_restore_wall,
            },
        },
        "steps": steps,
        "records": step_records,
        "batch_ownership": {
            "boundaries": batch_ownership,
            "total_seconds": batch_ownership_total,
            "amortized_seconds_per_counted_route": batch_share,
            "both_boundaries_exact": all(
                item["evidence"].get("passed") is True for item in batch_ownership
            ),
        },
        "metrics": {
            "saved_work": {
                "per_step_avoided_fresh_prompt_tokens": ROOT_TOKEN_COUNT,
                "cumulative_avoided_fresh_prompt_tokens": cumulative_avoided,
                "expected_at_r3": ROOT_TOKEN_COUNT * 3,
                "law_passed": saved_work_law,
            },
            "counted_full_lifecycle": {
                "scope": (
                    "three paired dependent transitions; catalytic includes root materialization, "
                    "save, every restore, final restore, erase, and equal batch-ownership share; "
                    "Task-A and seed generation are shared prerequisites"
                ),
                "root_setup_and_closure_wall_seconds": root_setup_and_closure_wall,
                "catalytic_wall_seconds": catalytic_lifecycle_wall,
                "direct_wall_seconds": direct_lifecycle_wall,
                "wall_speedup": lifecycle_speedup,
                "minimum_wall_speedup": MIN_FULL_LIFECYCLE_WALL_SPEEDUP,
            },
            "residency": {
                "with_root": resources_with_root,
                "before_erase": resources_before_erase,
                "after_erase": resources_after_erase,
                "simultaneous_roots": 1,
                "root_bytes_constant": root_metadata_invariant,
            },
        },
        "quality_gates": {
            "qualified_panel_identity_exact": True,
            "seed_branch_fixed_before_contact": True,
            "seed_output_exact": seed_state["answer"] == SEED_EXPECTED_ANSWER,
            "seed_generated_token_identity_exact": (
                seed_state["generated_token_sha256"] == SEED_GENERATED_SHA256
            ),
            "seed_cache_split_689_1_exact": (
                seed_record["cached_prompt_tokens"] == ROOT_TOKEN_COUNT
                and seed_record["fresh_prompt_tokens"] == 1
            ),
            "output_state_sequence_C_D_B_B_exact": chain_exact,
            "final_B_to_B_fixed_point_exact": observed_sequence[-2:] == ["B", "B"],
            "paired_prompt_and_generated_token_identity_exact": pair_identity,
            "prior_generated_tokens_exact_in_each_successor": all(
                step["prior_generated_tokens_exact_in_request"] is True for step in steps
            ),
            "successors_constructed_after_pair_agreement": all(
                step["constructed_after_prior_pair_agreement"] is True for step in steps
            ),
            "exact_689_token_root_prefix_every_request": pair_identity,
            "catalytic_cached_prompt_tokens_689_exact": all(
                record["cached_prompt_tokens"] == ROOT_TOKEN_COUNT
                for record in catalytic_records
            ),
            "direct_cached_prompt_tokens_zero": all(
                record["cached_prompt_tokens"] == 0 for record in direct_records
            ),
            "cumulative_avoided_prompt_work_689_times_r": saved_work_law,
            "checkpoint_count_zero": all(
                operation["n_checkpoints"] == 0 for operation in root_operations
            ),
            "root_metadata_invariant": root_metadata_invariant,
            "cuda_device_bytes_nonzero": saved["n_device_bytes"] > 0,
            "cuda_gpu_bytes_nonzero": saved["n_gpu_bytes"] > 0,
            "cuda_device_bytes_zero_after_erase": erased["n_device_bytes_after"] == 0,
            "cuda_gpu_bytes_zero_after_erase": erased["n_gpu_bytes_after"] == 0,
            "final_restore_before_erase": root_operations[-2]["label"] == "final-root-closure",
            "explicit_erase": root_operations[-1]["label"] == "root-erase",
            "batch_ownership_boundaries_exact": all(
                item["evidence"].get("passed") is True for item in batch_ownership
            ),
            "full_lifecycle_wall_speedup_at_least_1_25": (
                lifecycle_speedup >= MIN_FULL_LIFECYCLE_WALL_SPEEDUP
            ),
            "bounded_single_root_residency": True,
            "fanout_claimed": False,
            "recursive_root_promotion_claimed": False,
            "unbounded_catalytic_inference_established": False,
            "automatic_promotion": False,
        },
        "resources": {
            "task_a_fresh_model_tokens": task_a["fresh_model_tokens"],
            "materialization_fresh_model_tokens": materialization["fresh_model_tokens"],
            "transition_catalytic_fresh_model_tokens": sum(
                int(record["fresh_model_tokens"]) for record in catalytic_records
            ),
            "transition_direct_fresh_model_tokens": sum(
                int(record["fresh_model_tokens"]) for record in direct_records
            ),
        },
        "next_boundary": (
            "PRESERVE_R3_EVIDENCE_AND_DESIGN_THE_SMALLEST_RECURSIVE_ROOT_PROMOTION_DISCRIMINATOR"
            if accepted_before_cleanup
            else "PRESERVE_R3_EVIDENCE_AND_LOCALIZE_THE_FIRST_FAILED_RECURSION_GATE_WITHOUT_RETRY"
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
        bounded_output_derived_recursive_reuse_supported=accepted,
    )
    result["status"] = "complete"
    result["verdict"] = "accept" if accepted else "reject"
    if accepted:
        result["classification"] = "cuda-root-output-derived-fixed-point-r3-supported-bounded"
        result["next_boundary"] = (
            "PRESERVE_R3_EVIDENCE_AND_DESIGN_THE_SMALLEST_RECURSIVE_ROOT_PROMOTION_DISCRIMINATOR"
        )
    elif scientific_gate:
        result["classification"] = "output-derived-fixed-point-cleanup-or-residency-failure"
        result["next_boundary"] = (
            "PRESERVE_R3_EVIDENCE_AND_LOCALIZE_CLEANUP_OR_RESIDENCY_FAILURE_WITHOUT_RETRY"
        )
    return result


def main() -> int:
    args = parse_args()
    repository = Path(__file__).resolve().parents[1]
    binary = args.binary.resolve(strict=True)
    expected_binary = (repository / DEFAULT_BINARY).resolve(strict=True)
    require(binary == expected_binary, "fixed-point run requires the isolated candidate binary")
    cuda_runtime_sha256 = latency.verify_cuda_root_runtime(binary)
    model = args.model.resolve(strict=True)
    latency.require_unused_artifact_paths(args.output, args.server_log_output)
    corpus = harness.carrier.load_public_corpus(repository)
    roots = {str(item["root_id"]): item for item in corpus["roots"]}
    evaluator, live_contract = harness.load_discovery_sidecar_contract()
    stable_pids = harness.live_runtime.require_stable()
    require(len(stable_pids) == 1, "fixed-point run requires the sole stable listener")
    require(not harness.live_runtime.listener_pids(harness.live_runtime.PORT), "frontier port is occupied")
    state_root = Path(tempfile.mkdtemp(prefix="neo3000-output-fixed-point-"))
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
            "fixed-point launch identity changed",
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
            root=roots[ROOT_ID],
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
    require(result is not None, "fixed-point result is missing")
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
