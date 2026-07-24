#!/usr/bin/env python3
"""Pinned-base fixed-output CUDA capsule rebase experiment engine.

The executed default remains the C -> D -> B -> B recurrence.  One immutable
689-token host root pins the expensive base state.  One replaceable 695-token
CUDA root contains the complete 690-token branch prefix followed by the five
exact visible IDs of the latest output.  After every verified transition the
old CUDA child is erased, the base is restored, exactly six tokens are
materialized, and a same-size replacement child is saved.

The default R=3 path is the executed 0075 contract.  R=16 with the same
absorbing transition is the executed 0076 contract.  A caller may supply one
fully bound recurrence contract while preserving the carrier, paired controls,
accounting, and closure gates.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
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
DEPTH_SCALING_EXPERIMENT_ID = "neo-exp-0076"
SUPPORTED_RECURSIVE_DEPTHS = (3, 16)
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


@dataclass(frozen=True)
class RecurrenceContract:
    experiment_id: str
    recurrence_id: str
    recursive_depth: int
    transition: tuple[tuple[str, str], ...]
    transition_content: str
    expected_state_sequence: tuple[str, ...]
    accepted_classification: str
    next_boundary: str
    claim_ceiling: str
    minimum_wall_speedup: float = MIN_FULL_LIFECYCLE_WALL_SPEEDUP
    maximum_catalytic_wall_seconds: float | None = None
    exact_cycle_period: int | None = None
    expected_base_branch_sha256: str | None = None
    expected_suffix_token_count: int | None = None
    expected_suffix_sha256: str | None = None
    expected_generated_sha256: tuple[tuple[str, str], ...] = ()
    expected_child_sha256: tuple[tuple[str, str], ...] = ()
    expected_request_sha256: tuple[tuple[str, str], ...] = ()
    root_bank_capacity: int = 2
    phase_root_ring: bool = False
    maximum_root_and_rebase_wall_seconds: float | None = None
    maximum_ring_overhead_seconds: float | None = None
    expected_cuda_runtime_sha256: tuple[tuple[str, str], ...] = ()

    def transition_map(self) -> dict[str, str]:
        return dict(self.transition)

    def generated_hash_map(self) -> dict[str, str]:
        return dict(self.expected_generated_sha256)

    def child_hash_map(self) -> dict[str, str]:
        return dict(self.expected_child_sha256)

    def request_hash_map(self) -> dict[str, str]:
        return dict(self.expected_request_sha256)


def validate_contract(contract: RecurrenceContract) -> RecurrenceContract:
    transition = contract.transition_map()
    require(set(transition) == {"A", "B", "C", "D"}, "recurrence transition domain changed")
    require(
        all(answer in transition for answer in transition.values()),
        "recurrence transition leaves the four-state domain",
    )
    require(contract.recursive_depth > 0, "recurrence depth must be positive")
    require(
        len(contract.expected_state_sequence) == contract.recursive_depth + 1,
        "recurrence state sequence length changed",
    )
    require(
        contract.expected_state_sequence[0] == fixed.SEED_EXPECTED_ANSWER,
        "recurrence seed state changed",
    )
    for prior, successor in zip(
        contract.expected_state_sequence,
        contract.expected_state_sequence[1:],
    ):
        require(transition[prior] == successor, "recurrence state sequence violates transition law")
    require(contract.minimum_wall_speedup > 0.0, "recurrence speed gate must be positive")
    require(contract.root_bank_capacity >= 2, "recurrence root-bank capacity is too small")
    if contract.maximum_catalytic_wall_seconds is not None:
        require(
            contract.maximum_catalytic_wall_seconds > 0.0,
            "recurrence catalytic-wall ceiling must be positive",
        )
    if contract.exact_cycle_period is not None:
        require(contract.exact_cycle_period > 1, "recurrence cycle period must exceed one")
        require(
            contract.recursive_depth % contract.exact_cycle_period == 0,
            "recurrence depth must contain whole exact cycles",
        )
        require(
            contract.expected_base_branch_sha256 is not None,
            "periodic recurrence base-branch hash is unbound",
        )
        require(
            contract.expected_suffix_token_count is not None
            and contract.expected_suffix_sha256 is not None,
            "periodic recurrence suffix identity is unbound",
        )
        for pairs, label in (
            (contract.expected_generated_sha256, "generated"),
            (contract.expected_child_sha256, "child"),
            (contract.expected_request_sha256, "request"),
        ):
            mapping = dict(pairs)
            require(set(mapping) == set(transition), f"{label} hash domain changed")
            require(len(set(mapping.values())) == len(transition), f"{label} hashes are not distinct")
    if contract.phase_root_ring:
        require(contract.exact_cycle_period is not None, "phase-root ring lacks an exact cycle")
        require(
            contract.root_bank_capacity == len(transition) + 1,
            "phase-root ring capacity must equal base plus one root per phase",
        )
        require(
            contract.maximum_root_and_rebase_wall_seconds is not None
            and contract.maximum_root_and_rebase_wall_seconds > 0.0,
            "phase-root ring root/rebase wall gate is unbound",
        )
        require(
            contract.maximum_ring_overhead_seconds is not None
            and contract.maximum_ring_overhead_seconds > 0.0,
            "phase-root ring overhead gate is unbound",
        )
        require(
            set(dict(contract.expected_cuda_runtime_sha256))
            == set(latency.CUDA_ROOT_RUNTIME_SHA256),
            "phase-root ring CUDA runtime identity is incompletely bound",
        )
    return contract


def verify_cuda_runtime(
    binary: Path,
    contract: RecurrenceContract,
) -> dict[str, str]:
    expected = dict(contract.expected_cuda_runtime_sha256)
    if not expected:
        return latency.verify_cuda_root_runtime(binary)
    require(binary.name == "llama-server.exe", "CUDA-root runtime entrypoint changed")
    observed: dict[str, str] = {}
    for name, expected_sha256 in expected.items():
        runtime_file = (binary.parent / name).resolve(strict=True)
        require(
            runtime_file.parent == binary.parent,
            f"CUDA-root runtime path escaped for {name}",
        )
        observed_sha256 = harness.live_runtime.sha256_file(runtime_file)
        require(
            observed_sha256 == expected_sha256,
            f"phase-root runtime identity drifted for {name}: {observed_sha256}",
        )
        observed[name] = observed_sha256
    return observed


def absorbing_contract(recursive_depth: int) -> RecurrenceContract:
    return validate_contract(
        RecurrenceContract(
            experiment_id=experiment_id_for_depth(recursive_depth),
            recurrence_id="absorbing-fixed-point",
            recursive_depth=recursive_depth,
            transition=tuple(fixed.TRANSITION.items()),
            transition_content=fixed.transition_user_content(),
            expected_state_sequence=expected_state_sequence_for_depth(recursive_depth),
            accepted_classification=accepted_classification_for_depth(recursive_depth),
            next_boundary=next_boundary_for_depth(recursive_depth),
            claim_ceiling=(
                f"exact fixed-size recursive state rebase through R={recursive_depth} for the "
                "bounded finite-state recurrence; "
                "not arbitrary-history semantic compaction or unbounded inference"
            ),
        )
    )


def recurrence_evidence(
    contract: RecurrenceContract,
    observed_sequence: Sequence[str],
    steps: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    active = validate_contract(contract)
    transition = active.transition_map()
    cycle_period = active.exact_cycle_period
    generated_hash_sequence = [str(step["generated_token_sha256"]) for step in steps]
    child_hash_sequence = [str(step["child_token_sha256"]) for step in steps]
    request_hash_sequence = [str(step["prompt_token_sha256"]) for step in steps]

    def exact_period(values: Sequence[str], period: int) -> bool:
        return (
            len(values) >= period
            and len(set(values)) == period
            and all(value == values[index % period] for index, value in enumerate(values))
        )

    def orbit(start: str, period: int) -> list[str]:
        values = [start]
        for _unused in range(period):
            values.append(transition[values[-1]])
        return values

    fixed_point_child_hash_invariant = (
        len(steps) >= 2
        and len({str(step["child_token_sha256"]) for step in steps[1:]}) == 1
    )
    transition_bijective = len(set(transition.values())) == len(transition)
    transition_has_no_fixed_point = all(source != target for source, target in transition.items())
    transition_cycle_identity = cycle_period is not None and all(
        orbit(answer, cycle_period)[-1] == answer
        for answer in transition
    )
    transition_no_early_collision = cycle_period is not None and all(
        len(set(orbit(answer, cycle_period)[:-1])) == cycle_period
        for answer in transition
    )
    state_sequence_period_exact = (
        cycle_period is not None
        and exact_period(observed_sequence[:-1], cycle_period)
        and observed_sequence[-1] == observed_sequence[0]
    )
    generated_hash_period_exact = cycle_period is not None and exact_period(
        generated_hash_sequence,
        cycle_period,
    )
    child_hash_period_exact = cycle_period is not None and exact_period(
        child_hash_sequence,
        cycle_period,
    )
    request_hash_period_exact = cycle_period is not None and exact_period(
        request_hash_sequence,
        cycle_period,
    )
    reversible_cycle_integrity = (
        cycle_period is not None
        and transition_bijective
        and transition_has_no_fixed_point
        and transition_cycle_identity
        and transition_no_early_collision
        and state_sequence_period_exact
        and generated_hash_period_exact
        and child_hash_period_exact
        and request_hash_period_exact
    )
    recurrence_hash_invariant = (
        fixed_point_child_hash_invariant
        if cycle_period is None
        else reversible_cycle_integrity
    )
    return {
        "cycle_period": cycle_period,
        "generated_hash_sequence": generated_hash_sequence,
        "child_hash_sequence": child_hash_sequence,
        "request_hash_sequence": request_hash_sequence,
        "fixed_point_child_hash_invariant": fixed_point_child_hash_invariant,
        "transition_bijective": transition_bijective,
        "transition_has_no_fixed_point": transition_has_no_fixed_point,
        "transition_cycle_identity": transition_cycle_identity,
        "transition_no_early_collision": transition_no_early_collision,
        "state_sequence_period_exact": state_sequence_period_exact,
        "generated_hash_period_exact": generated_hash_period_exact,
        "child_hash_period_exact": child_hash_period_exact,
        "request_hash_period_exact": request_hash_period_exact,
        "reversible_cycle_integrity": reversible_cycle_integrity,
        "recurrence_hash_invariant": recurrence_hash_invariant,
    }


def experiment_id_for_depth(recursive_depth: int) -> str:
    require(recursive_depth in SUPPORTED_RECURSIVE_DEPTHS, "unsupported recursive depth")
    return EXPERIMENT_ID if recursive_depth == 3 else DEPTH_SCALING_EXPERIMENT_ID


def pair_route_orders_for_depth(recursive_depth: int) -> tuple[tuple[str, str], ...]:
    require(recursive_depth in SUPPORTED_RECURSIVE_DEPTHS, "unsupported recursive depth")
    return tuple(PAIR_ROUTE_ORDERS[index % len(PAIR_ROUTE_ORDERS)] for index in range(recursive_depth))


def expected_state_sequence_for_depth(recursive_depth: int) -> tuple[str, ...]:
    require(recursive_depth in SUPPORTED_RECURSIVE_DEPTHS, "unsupported recursive depth")
    return ("C", "D", *(["B"] * (recursive_depth - 1)))


def accepted_classification_for_depth(recursive_depth: int) -> str:
    require(recursive_depth in SUPPORTED_RECURSIVE_DEPTHS, "unsupported recursive depth")
    return f"pinned-base-fixed-output-cuda-capsule-rebase-r{recursive_depth}-supported-bounded"


def next_boundary_for_depth(recursive_depth: int) -> str:
    require(recursive_depth in SUPPORTED_RECURSIVE_DEPTHS, "unsupported recursive depth")
    if recursive_depth == 3:
        return "PRESERVE_FIXED_SIZE_R3_AND_SCALE_RECURSIVE_DEPTH_WITH_CONSTANT_CARRIER"
    return "PRESERVE_FIXED_SIZE_R16_AND_SELECT_NEXT_FAST_CATALYTIC_N_T_R_B_BOUNDARY"


def child_root_id(
    step: int,
    answer: str,
    *,
    valid_states: Sequence[str] | None = None,
) -> str:
    require(type(step) is int and step >= 0, "capsule step is out of range")
    require(
        answer in set(valid_states or fixed.TRANSITION),
        "capsule answer is invalid",
    )
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
    expected_root_capacity: int = 2,
) -> dict[str, Any]:
    require(action in {"root-save", "root-restore", "root-erase"}, "unsupported root action")
    require(storage in {"host", "device"}, "unsupported root storage")
    require(response.get("action") == action, f"root action mismatch for {action}")
    require(response.get("root_id") == root_id, f"root identity mismatch for {action}")
    require(
        type(response.get("device_storage_key")) is int,
        f"root device storage key is missing for {action}",
    )
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
    require(
        int(response["n_roots_capacity"]) == expected_root_capacity,
        "root bank capacity changed",
    )
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
        require(
            int(response["device_storage_key"]) == 0,
            f"host root gained a device storage key at {action}",
        )
        require(int(response["n_device_bytes"]) == 0, f"host root gained device bytes at {action}")
        require(int(response["n_gpu_bytes"]) == 0, f"host root gained GPU bytes at {action}")
    else:
        require(
            int(response["device_storage_key"]) < 0,
            f"device root storage key is not isolated at {action}",
        )
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
            "device_storage_key",
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
            "device_storage_key",
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
    expected_root_capacity: int = 2,
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
        expected_root_capacity=expected_root_capacity,
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
    contract: RecurrenceContract,
    expected_bank_roots: int = 2,
    expected_bank_device_bytes: int = EXPECTED_CHILD_DEVICE_BYTES,
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
            expected_roots_after=expected_bank_roots,
            expected_total_device_bytes_after=expected_bank_device_bytes,
            expected_root_capacity=contract.root_bank_capacity,
            label=f"step-{step}:restore-child",
        )
        restore_wall = float(restore["client_wall_seconds"])
    tokens, payload, ancestry = rolling.derive_promoted_successor(
        codec=codec,
        root_tokens=child_tokens,
        prior_state=prior_state,
        seed=shared_tasks.derive_seed(fixed.ROOT_ID, f"fixed-size-rebase-step-{step}"),
        cache_prompt=route == "catalytic",
        transition_content=contract.transition_content,
    )
    require(len(tokens) == EXPECTED_DIRECT_FRESH_TOKENS, "fixed-size successor prompt changed")
    if contract.expected_suffix_token_count is not None:
        require(
            ancestry["suffix_token_count"] == contract.expected_suffix_token_count,
            "recurrence suffix token count changed",
        )
    if contract.expected_suffix_sha256 is not None:
        require(
            ancestry["suffix_token_sha256"] == contract.expected_suffix_sha256,
            "recurrence suffix token hash changed",
        )
    request_hashes = contract.request_hash_map()
    if request_hashes:
        require(
            ancestry["request_token_sha256"] == request_hashes[str(prior_state["answer"])],
            "recurrence request token hash changed",
        )
    recorder = latency.TimingRecorder()
    record = harness.run_completion(
        sidecar,
        f"{fixed.ROOT_ID}:fixed-size-rebase:step-{step}:{route}",
        payload,
        recorder=recorder,
        batch_owned_request=True,
    )
    state = fixed.generated_state(record, codec=codec, props=props)
    expected_answer = contract.transition_map()[str(prior_state["answer"])]
    require(state["answer"] == expected_answer, f"fixed-size step {step} answer is incorrect")
    generated_hashes = contract.generated_hash_map()
    if generated_hashes:
        require(
            state["generated_token_sha256"] == generated_hashes[expected_answer],
            "recurrence generated-token hash changed",
        )
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
    contract: RecurrenceContract,
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
        expected_root_capacity=contract.root_bank_capacity,
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
        expected_root_capacity=contract.root_bank_capacity,
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
        operation_kind="zero-output-root-readdress",
        batch_owned_request=True,
    )
    require(materialized["prompt_tokens"] == EXPECTED_CHILD_TOKENS, "rebase prompt count changed")
    require(materialized["cached_prompt_tokens"] == EXPECTED_BASE_TOKENS, "rebase base cache changed")
    require(materialized["fresh_prompt_tokens"] == EXPECTED_REBASE_FRESH_TOKENS, "rebase fresh count changed")
    require(materialized["completion_tokens"] == 0, "rebase emitted output")
    next_child = root_action(
        action="root-save",
        root_id=child_root_id(
            step,
            str(next_state["answer"]),
            valid_states=contract.transition_map(),
        ),
        storage="device",
        expected_tokens=EXPECTED_CHILD_TOKENS,
        expected_roots_after=2,
        expected_total_device_bytes_after=EXPECTED_CHILD_DEVICE_BYTES,
        expected_root_capacity=contract.root_bank_capacity,
        label=f"step-{step}:save-rebased-child",
    )
    child_hashes = contract.child_hash_map()
    if child_hashes:
        require(
            harness.sha256_bytes(harness.carrier.canonical_json_bytes(child_tokens))
            == child_hashes[str(next_state["answer"])],
            "recurrence child token hash changed",
        )
    operations.append(next_child)
    return next_child, child_tokens, operations, materialized


def cold_fill_phase_child(
    *,
    sidecar: Any,
    base_root: Mapping[str, Any],
    base_branch_tokens: Sequence[int],
    next_state: Mapping[str, Any],
    step: int,
    contract: RecurrenceContract,
    roots_before: int,
    device_roots_before: int,
) -> tuple[dict[str, Any], list[int], list[dict[str, Any]], dict[str, Any]]:
    require(contract.phase_root_ring, "cold phase fill requires a phase-root ring contract")
    require(
        roots_before == device_roots_before + 1,
        "phase-root ring lost its sole host base",
    )
    live_device_bytes = device_roots_before * EXPECTED_CHILD_DEVICE_BYTES
    operations: list[dict[str, Any]] = []
    restored_base = root_action(
        action="root-restore",
        root_id=BASE_ROOT_ID,
        storage="host",
        expected=base_root,
        expected_tokens=EXPECTED_BASE_TOKENS,
        expected_roots_after=roots_before,
        expected_total_device_bytes_after=live_device_bytes,
        expected_root_capacity=contract.root_bank_capacity,
        label=f"step-{step}:restore-base-for-cold-phase-fill",
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
        f"{fixed.ROOT_ID}:phase-root-ring:materialize-{step}",
        payload,
        operation_kind="zero-output-root-readdress",
        batch_owned_request=True,
    )
    require(materialized["prompt_tokens"] == EXPECTED_CHILD_TOKENS, "phase fill prompt changed")
    require(materialized["cached_prompt_tokens"] == EXPECTED_BASE_TOKENS, "phase fill base cache changed")
    require(materialized["fresh_prompt_tokens"] == EXPECTED_REBASE_FRESH_TOKENS, "phase fill fresh count changed")
    require(materialized["completion_tokens"] == 0, "phase fill emitted output")
    next_child = root_action(
        action="root-save",
        root_id=child_root_id(
            step,
            str(next_state["answer"]),
            valid_states=contract.transition_map(),
        ),
        storage="device",
        expected_tokens=EXPECTED_CHILD_TOKENS,
        expected_roots_after=roots_before + 1,
        expected_total_device_bytes_after=(
            (device_roots_before + 1) * EXPECTED_CHILD_DEVICE_BYTES
        ),
        expected_root_capacity=contract.root_bank_capacity,
        label=f"step-{step}:save-cold-phase-child",
    )
    child_hashes = contract.child_hash_map()
    require(bool(child_hashes), "phase-root ring child hashes are unbound")
    require(
        harness.sha256_bytes(harness.carrier.canonical_json_bytes(child_tokens))
        == child_hashes[str(next_state["answer"])],
        "phase-root ring child token hash changed",
    )
    operations.append(next_child)
    return next_child, child_tokens, operations, materialized


def classify(
    *,
    integrity: bool,
    fixed_size: bool,
    saved_work_law: bool,
    speedup: float,
    recursive_depth: int = 3,
    catalytic_wall_seconds: float | None = None,
    root_and_rebase_wall_seconds: float | None = None,
    ring_overhead_seconds: float | None = None,
    contract: RecurrenceContract | None = None,
) -> str:
    active = validate_contract(contract or absorbing_contract(recursive_depth))
    if not integrity:
        return "fixed-size-rebase-integrity-failure"
    if not fixed_size:
        return "fixed-size-rebase-growth-failure"
    if not saved_work_law:
        return "fixed-size-rebase-saved-work-law-failure"
    if speedup < active.minimum_wall_speedup:
        return "fixed-size-rebase-without-preregistered-wall-gate"
    if active.maximum_catalytic_wall_seconds is not None and (
        catalytic_wall_seconds is None
        or catalytic_wall_seconds > active.maximum_catalytic_wall_seconds
    ) and not active.phase_root_ring:
        return "fixed-size-rebase-above-preregistered-catalytic-wall-ceiling"
    if active.maximum_root_and_rebase_wall_seconds is not None and (
        root_and_rebase_wall_seconds is None
        or root_and_rebase_wall_seconds > active.maximum_root_and_rebase_wall_seconds
    ):
        return "phase-root-ring-above-preregistered-root-rebase-wall-ceiling"
    if active.maximum_ring_overhead_seconds is not None and (
        ring_overhead_seconds is None
        or ring_overhead_seconds > active.maximum_ring_overhead_seconds
    ):
        return "phase-root-ring-above-preregistered-overhead-ceiling"
    if active.maximum_catalytic_wall_seconds is not None and (
        catalytic_wall_seconds is None
        or catalytic_wall_seconds > active.maximum_catalytic_wall_seconds
    ):
        return "fixed-size-rebase-above-preregistered-catalytic-wall-ceiling"
    return active.accepted_classification


def evaluate(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    root: Mapping[str, Any],
    baseline_private: int | None,
    recursive_depth: int = 3,
    contract: RecurrenceContract | None = None,
) -> dict[str, Any]:
    active = validate_contract(contract or absorbing_contract(recursive_depth))
    require(
        active.recursive_depth == recursive_depth,
        "recurrence contract depth differs from requested depth",
    )
    experiment_id = active.experiment_id
    route_orders = pair_route_orders_for_depth(recursive_depth)
    expected_sequence = active.expected_state_sequence
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
    if active.expected_base_branch_sha256 is not None:
        require(
            harness.sha256_bytes(harness.carrier.canonical_json_bytes(base_branch_tokens))
            == active.expected_base_branch_sha256,
            "complete branch token hash changed",
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
        operation_kind="zero-output-root-readdress",
    )
    require(parent_materialization["fresh_prompt_tokens"] == EXPECTED_BASE_TOKENS, "base replay changed")
    base_saved = root_action(
        action="root-save",
        root_id=BASE_ROOT_ID,
        storage="host",
        expected_tokens=EXPECTED_BASE_TOKENS,
        expected_roots_after=1,
        expected_total_device_bytes_after=0,
        expected_root_capacity=active.root_bank_capacity,
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
        expected_root_capacity=active.root_bank_capacity,
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
    seed_child_hashes = active.child_hash_map()
    if seed_child_hashes:
        require(
            harness.sha256_bytes(harness.carrier.canonical_json_bytes(child_tokens))
            == seed_child_hashes[str(seed_state["answer"])],
            "seed child token hash changed",
        )
    child_root = root_action(
        action="root-save",
        root_id=child_root_id(
            0,
            seed_state["answer"],
            valid_states=active.transition_map(),
        ),
        storage="device",
        expected_tokens=EXPECTED_CHILD_TOKENS,
        expected_roots_after=2,
        expected_total_device_bytes_after=EXPECTED_CHILD_DEVICE_BYTES,
        expected_root_capacity=active.root_bank_capacity,
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
    phase_roots: dict[str, tuple[str, dict[str, Any], list[int]]] = {}
    phase_cold_fills = 0
    phase_ring_hits = 0
    if active.phase_root_ring:
        seed_child_checksum = harness.sha256_bytes(
            harness.carrier.canonical_json_bytes(child_tokens)
        )
        require(
            seed_child_checksum == seed_child_hashes[str(seed_state["answer"])],
            "seed phase-root checksum address changed",
        )
        phase_roots[seed_child_checksum] = (
            str(seed_state["answer"]),
            child_root,
            child_tokens,
        )
    for step, route_order in enumerate(route_orders, start=1):
        bank_device_roots = len(phase_roots) if active.phase_root_ring else 1
        bank_roots = bank_device_roots + 1
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
                contract=active,
                expected_bank_roots=bank_roots,
                expected_bank_device_bytes=(
                    bank_device_roots * EXPECTED_CHILD_DEVICE_BYTES
                ),
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
        next_answer = str(agreed_state["answer"])
        candidate_next_child_tokens = compact_child_tokens(
            base_branch_tokens,
            agreed_state,
        )
        candidate_next_child_checksum = harness.sha256_bytes(
            harness.carrier.canonical_json_bytes(candidate_next_child_tokens)
        )
        if active.phase_root_ring:
            require(
                candidate_next_child_checksum
                == active.child_hash_map()[next_answer],
                "phase-root checksum address changed",
            )
        if active.phase_root_ring and candidate_next_child_checksum in phase_roots:
            stored_answer, next_child, next_child_tokens = phase_roots[
                candidate_next_child_checksum
            ]
            require(stored_answer == next_answer, "phase-root checksum resolved the wrong state")
            require(
                next_child_tokens == candidate_next_child_tokens,
                "phase-root checksum resolved different child tokens",
            )
            rebase_ops = []
            materialized = None
            phase_ring_hits += 1
            lifecycle = "phase-ring-hit"
            avoided = int(direct["fresh_prompt_tokens"]) - int(
                catalytic["fresh_prompt_tokens"]
            )
            require(
                avoided == EXPECTED_CHILD_TOKENS,
                "phase-root ring hit avoided work changed",
            )
        elif active.phase_root_ring:
            next_child, next_child_tokens, rebase_ops, materialized = cold_fill_phase_child(
                sidecar=sidecar,
                base_root=base_saved,
                base_branch_tokens=base_branch_tokens,
                next_state=agreed_state,
                step=step,
                contract=active,
                roots_before=bank_roots,
                device_roots_before=bank_device_roots,
            )
            require(
                next_child_tokens == candidate_next_child_tokens,
                "cold-filled phase root differs from checksum-addressed child",
            )
            phase_roots[candidate_next_child_checksum] = (
                next_answer,
                next_child,
                next_child_tokens,
            )
            phase_cold_fills += 1
            lifecycle = "phase-cold-fill"
            avoided = int(direct["fresh_prompt_tokens"]) - (
                int(catalytic["fresh_prompt_tokens"])
                + int(materialized["fresh_prompt_tokens"])
            )
            require(
                avoided == EXPECTED_BASE_TOKENS,
                "phase-root cold-fill avoided work changed",
            )
        else:
            next_child, next_child_tokens, rebase_ops, materialized = rebase_child(
                sidecar=sidecar,
                base_root=base_saved,
                old_child=child_root,
                base_branch_tokens=base_branch_tokens,
                next_state=agreed_state,
                step=step,
                contract=active,
            )
            lifecycle = "replaceable-child-rebase"
            avoided = int(direct["fresh_prompt_tokens"]) - (
                int(catalytic["fresh_prompt_tokens"])
                + int(materialized["fresh_prompt_tokens"])
            )
            require(avoided == EXPECTED_BASE_TOKENS, "charged avoided work changed")
        root_operations.extend(rebase_ops)
        if materialized is not None:
            rebases.append(materialized)
        cumulative_avoided += avoided
        observed_sequence.append(str(agreed_state["answer"]))
        steps.append(
            {
                "step": step,
                "route_order": list(route_order),
                "prior_answer": prior_state["answer"],
                "answer": agreed_state["answer"],
                "child_lifecycle": lifecycle,
                "next_child_checksum_address": candidate_next_child_checksum,
                "parent_child_root_id": child_root["root_id"],
                "next_child_root_id": next_child["root_id"],
                "child_root_tokens": len(child_tokens),
                "next_child_root_tokens": len(next_child_tokens),
                "child_device_bytes": child_root["n_device_bytes"],
                "next_child_device_bytes": next_child["n_device_bytes"],
                "successor_fresh_tokens": catalytic["fresh_prompt_tokens"],
                "rebase_fresh_tokens": (
                    materialized["fresh_prompt_tokens"]
                    if materialized is not None
                    else 0
                ),
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
        expected_roots_after=(len(phase_roots) + 1 if active.phase_root_ring else 2),
        expected_total_device_bytes_after=(
            len(phase_roots) * EXPECTED_CHILD_DEVICE_BYTES
            if active.phase_root_ring
            else EXPECTED_CHILD_DEVICE_BYTES
        ),
        expected_root_capacity=active.root_bank_capacity,
        label="final-child-restore",
    )
    root_operations.append(final_child_restore)
    resources_before_closure = harness.process_resources(sidecar, baseline_private)
    if active.phase_root_ring:
        require(
            {
                answer
                for answer, _root_record, _tokens in phase_roots.values()
            }
            == set(active.transition_map()),
            "phase-root ring did not fill all exact states",
        )
        remaining_device_roots = len(phase_roots)
        for phase_checksum in sorted(phase_roots):
            answer, phase_root, _phase_tokens = phase_roots[phase_checksum]
            remaining_device_roots -= 1
            erased_phase = root_action(
                action="root-erase",
                root_id=str(phase_root["root_id"]),
                storage="device",
                expected=phase_root,
                expected_tokens=EXPECTED_CHILD_TOKENS,
                expected_roots_after=remaining_device_roots + 1,
                expected_total_device_bytes_after=(
                    remaining_device_roots * EXPECTED_CHILD_DEVICE_BYTES
                ),
                expected_root_capacity=active.root_bank_capacity,
                label=f"final-phase-{answer}-erase",
            )
            root_operations.append(erased_phase)
    else:
        final_child_erase = root_action(
            action="root-erase",
            root_id=str(child_root["root_id"]),
            storage="device",
            expected=child_root,
            expected_tokens=EXPECTED_CHILD_TOKENS,
            expected_roots_after=1,
            expected_total_device_bytes_after=0,
            expected_root_capacity=active.root_bank_capacity,
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
        expected_root_capacity=active.root_bank_capacity,
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
    ring_overhead_wall = (
        sum(float(item["wall_seconds"]) for item in rebases)
        + sum(float(operation["client_wall_seconds"]) for operation in root_operations)
    )
    catalytic_wall = root_and_rebase_wall + sum(
        float(record["effective_wall_seconds"]) for record in catalytic_records
    )
    direct_wall = sum(float(record["effective_wall_seconds"]) for record in direct_records)
    lifecycle_speedup = direct_wall / catalytic_wall
    exact_sequence = tuple(observed_sequence) == expected_sequence
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
    expected_cumulative_avoided = 0
    saved_work_law = True
    for step_record in steps:
        expected_step_avoided = (
            EXPECTED_CHILD_TOKENS
            if step_record["child_lifecycle"] == "phase-ring-hit"
            else EXPECTED_BASE_TOKENS
        )
        expected_cumulative_avoided += expected_step_avoided
        saved_work_law = (
            saved_work_law
            and step_record["avoided_fresh_prompt_tokens_after_rebase_charge"]
            == expected_step_avoided
            and step_record["cumulative_avoided_fresh_prompt_tokens"]
            == expected_cumulative_avoided
        )
    transition = active.transition_map()
    recurrence = recurrence_evidence(active, observed_sequence, steps)
    cycle_period = recurrence["cycle_period"]
    generated_hash_sequence = recurrence["generated_hash_sequence"]
    child_hash_sequence = recurrence["child_hash_sequence"]
    request_hash_sequence = recurrence["request_hash_sequence"]
    fixed_point_child_hash_invariant = recurrence["fixed_point_child_hash_invariant"]
    transition_bijective = recurrence["transition_bijective"]
    transition_has_no_fixed_point = recurrence["transition_has_no_fixed_point"]
    transition_cycle_identity = recurrence["transition_cycle_identity"]
    transition_no_early_collision = recurrence["transition_no_early_collision"]
    state_sequence_period_exact = recurrence["state_sequence_period_exact"]
    generated_hash_period_exact = recurrence["generated_hash_period_exact"]
    child_hash_period_exact = recurrence["child_hash_period_exact"]
    request_hash_period_exact = recurrence["request_hash_period_exact"]
    recurrence_hash_invariant = recurrence["recurrence_hash_invariant"]
    base_invariant = all(
        operation["n_tokens"] == EXPECTED_BASE_TOKENS
        and operation["n_bytes"] == EXPECTED_BASE_HOST_BYTES
        and operation["n_device_bytes"] == 0
        for operation in root_operations
        if operation["root_id"] == BASE_ROOT_ID
    )
    expected_device_totals = {
        count * EXPECTED_CHILD_DEVICE_BYTES
        for count in range(active.root_bank_capacity)
    }
    bank_invariant = all(
        operation["n_roots_capacity"] == active.root_bank_capacity
        and operation["n_roots_after"] <= active.root_bank_capacity
        and operation["n_total_device_bytes_after"] in expected_device_totals
        for operation in root_operations
    )
    phase_ring_exact = (
        not active.phase_root_ring
        or (
            phase_cold_fills == len(active.transition_map()) - 1
            and phase_ring_hits == recursive_depth - phase_cold_fills
            and len(phase_roots) == len(active.transition_map())
            and len(
                {
                    int(root_record["device_storage_key"])
                    for _answer, root_record, _tokens in phase_roots.values()
                }
            )
            == len(active.transition_map())
            and len(rebases) == phase_cold_fills
            and cumulative_avoided
            == (
                phase_cold_fills * EXPECTED_BASE_TOKENS
                + phase_ring_hits * EXPECTED_CHILD_TOKENS
            )
        )
    )
    integrity = (
        exact_sequence
        and paired_identity
        and recurrence_hash_invariant
        and phase_ring_exact
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
        recursive_depth=recursive_depth,
        catalytic_wall_seconds=catalytic_wall,
        root_and_rebase_wall_seconds=root_and_rebase_wall,
        ring_overhead_seconds=ring_overhead_wall,
        contract=active,
    )
    accepted_before_cleanup = classification == active.accepted_classification
    if cycle_period is None:
        recurrence_quality_gates = {
            "final_B_to_B_fixed_point_exact": observed_sequence[-2:] == ["B", "B"],
            "B_fixed_point_stable_after_entry": (
                observed_sequence[2:] == ["B"] * (recursive_depth - 1)
            ),
            "fixed_point_child_hash_invariant": fixed_point_child_hash_invariant,
        }
    else:
        recurrence_quality_gates = {
            "transition_bijection_exact": transition_bijective,
            "transition_has_no_fixed_point": transition_has_no_fixed_point,
            "transition_fourth_power_identity": (
                cycle_period == 4 and transition_cycle_identity
            ),
            "transition_no_early_collision": transition_no_early_collision,
            "period4_state_sequence_exact": (
                cycle_period == 4 and state_sequence_period_exact
            ),
            "period4_generated_hash_invariant": (
                cycle_period == 4 and generated_hash_period_exact
            ),
            "period4_request_hash_invariant": (
                cycle_period == 4 and request_hash_period_exact
            ),
            "period4_child_hash_invariant": (
                cycle_period == 4 and child_hash_period_exact
            ),
            "four_distinct_states_exact": (
                len(set(observed_sequence[:-1])) == cycle_period
            ),
        }
    maximum_device_roots = (
        len(active.transition_map()) if active.phase_root_ring else 1
    )
    maximum_roots = maximum_device_roots + 1
    lifecycle_scope = (
        "base materialization/save, seed base restore/child save, every child restore, "
        "three cold phase fills, every phase-ring hit, final restore, all phase-root/base "
        "erases, and equal batch-ownership share; Task-A and seed generation shared"
        if active.phase_root_ring
        else (
            "base materialization/save, seed base restore/child save, every child restore, "
            "every child erase/base restore/six-token rebase/child save, final restores and "
            "erases, and equal batch-ownership share; Task-A and seed generation shared"
        )
    )
    phase_ring_metrics = {
        "enabled": active.phase_root_ring,
        "cold_fills": phase_cold_fills,
        "hits": phase_ring_hits,
        "phase_count": len(phase_roots),
        "bank_mutation_and_rebase_wall_seconds": ring_overhead_wall,
        "maximum_root_and_rebase_wall_seconds": (
            active.maximum_root_and_rebase_wall_seconds
        ),
        "maximum_ring_overhead_seconds": active.maximum_ring_overhead_seconds,
        "post_fill_device_bytes": (
            len(active.transition_map()) * EXPECTED_CHILD_DEVICE_BYTES
            if active.phase_root_ring
            else EXPECTED_CHILD_DEVICE_BYTES
        ),
        "device_storage_keys": sorted(
            int(root_record["device_storage_key"])
            for _answer, root_record, _tokens in phase_roots.values()
        ),
    }
    return {
        "status": "complete-pending-cleanup",
        "experiment_id": experiment_id,
        "mechanism": (
            "pinned-host-base-plus-checksum-addressed-cuda-phase-root-ring"
            if active.phase_root_ring
            else "pinned-host-base-plus-fixed-output-cuda-capsule-rebase"
        ),
        "verdict": "accept" if accepted_before_cleanup else "reject",
        "classification": classification,
        "geometry": {"N": 1, "T": recursive_depth, "R": recursive_depth, "B": 1},
        "claim_ceiling": active.claim_ceiling,
        "recurrence": {
            "id": active.recurrence_id,
            "transition": transition,
            "seed": expected_sequence[0],
            "period": cycle_period,
            "expected_sequence": list(expected_sequence),
            "observed_sequence": observed_sequence,
            "bijective": transition_bijective,
            "has_no_fixed_point": transition_has_no_fixed_point,
            "cycle_identity": transition_cycle_identity if cycle_period is not None else None,
            "no_early_collision": (
                transition_no_early_collision if cycle_period is not None else None
            ),
        },
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
                "root_id": child_root_id(
                    0,
                    seed_state["answer"],
                    valid_states=active.transition_map(),
                ),
                "n_tokens": EXPECTED_CHILD_TOKENS,
            },
            "final_child": child_root,
            "phase_children_by_checksum": {
                checksum: {"answer": answer, **root}
                for checksum, (answer, root, _tokens) in sorted(phase_roots.items())
            },
            "operations": root_operations,
            "maximum_simultaneous_roots": maximum_roots,
            "maximum_simultaneous_device_roots": maximum_device_roots,
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
                "expected_charged_avoided_fresh_prompt_tokens": (
                    phase_cold_fills * EXPECTED_BASE_TOKENS
                    + phase_ring_hits * EXPECTED_CHILD_TOKENS
                    if active.phase_root_ring
                    else EXPECTED_BASE_TOKENS * len(steps)
                ),
            },
            "counted_full_lifecycle": {
                "scope": lifecycle_scope,
                "root_and_rebase_wall_seconds": root_and_rebase_wall,
                "bank_mutation_and_rebase_wall_seconds": ring_overhead_wall,
                "catalytic_wall_seconds": catalytic_wall,
                "direct_wall_seconds": direct_wall,
                "wall_speedup": lifecycle_speedup,
                "minimum_wall_speedup": active.minimum_wall_speedup,
                "maximum_catalytic_wall_seconds": active.maximum_catalytic_wall_seconds,
            },
            "recurrence_law": {
                "generated_token_sha256_each_step": generated_hash_sequence,
                "child_token_sha256_each_step": child_hash_sequence,
                "request_token_sha256_each_step": request_hash_sequence,
                "exact_cycle_period": cycle_period,
                "generated_hash_period_exact": generated_hash_period_exact,
                "child_hash_period_exact": child_hash_period_exact,
                "request_hash_period_exact": request_hash_period_exact,
            },
            "phase_root_ring": phase_ring_metrics,
            "residency": {
                "with_base": resources_with_base,
                "with_two_roots": resources_with_two_roots,
                "before_closure": resources_before_closure,
                "after_closure": resources_after_closure,
                "maximum_simultaneous_roots": maximum_roots,
                "maximum_simultaneous_device_roots": maximum_device_roots,
            },
        },
        "quality_gates": {
            "qualified_panel_identity_exact": True,
            "seed_output_and_generated_token_identity_exact": True,
            "state_sequence_exact": exact_sequence,
            **recurrence_quality_gates,
            "preregistered_pair_route_order_exact": tuple(
                tuple(step["route_order"]) for step in steps
            )
            == route_orders,
            "paired_prompt_and_generated_identity_exact": paired_identity,
            "base_root_metadata_invariant": base_invariant,
            "root_bank_capacity_exact": bank_invariant,
            "maximum_device_roots_exact": (
                bank_invariant
                and (
                    not active.phase_root_ring
                    or len(phase_roots) == maximum_device_roots
                )
            ),
            "child_token_count_slope_zero": fixed_size,
            "child_device_byte_slope_zero": fixed_size,
            "successor_fresh_tokens_87_each_step": all(
                step["successor_fresh_tokens"] == EXPECTED_SUCCESSOR_FRESH_TOKENS
                for step in steps
            ),
            "rebase_geometry_exact": (
                (
                    phase_cold_fills == 3
                    and phase_ring_hits == 13
                    and [step["rebase_fresh_tokens"] for step in steps].count(
                        EXPECTED_REBASE_FRESH_TOKENS
                    )
                    == 3
                    and [step["rebase_fresh_tokens"] for step in steps].count(0)
                    == 13
                )
                if active.phase_root_ring
                else all(
                    step["rebase_fresh_tokens"] == EXPECTED_REBASE_FRESH_TOKENS
                    for step in steps
                )
            ),
            "direct_fresh_tokens_782_each_step": all(
                step["direct_fresh_tokens"] == EXPECTED_DIRECT_FRESH_TOKENS for step in steps
            ),
            "charged_saved_work_exact": saved_work_law,
            "phase_root_ring_exact": phase_ring_exact,
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
            "fully_counted_wall_speedup_at_least_preregistered_minimum": (
                lifecycle_speedup >= active.minimum_wall_speedup
            ),
            "catalytic_wall_at_or_below_preregistered_ceiling": (
                active.maximum_catalytic_wall_seconds is None
                or catalytic_wall <= active.maximum_catalytic_wall_seconds
            ),
            "root_and_rebase_wall_at_or_below_preregistered_ceiling": (
                active.maximum_root_and_rebase_wall_seconds is None
                or root_and_rebase_wall <= active.maximum_root_and_rebase_wall_seconds
            ),
            "bank_mutation_and_rebase_wall_at_or_below_preregistered_ceiling": (
                active.maximum_ring_overhead_seconds is None
                or ring_overhead_wall <= active.maximum_ring_overhead_seconds
            ),
            "fanout_claimed": False,
            "arbitrary_history_compaction_claimed": False,
            "unbounded_catalytic_inference_established": False,
            "automatic_promotion": False,
        },
        "next_boundary": active.next_boundary
        if accepted_before_cleanup
        else "PRESERVE_EXECUTED_EVIDENCE_AND_LOCALIZE_THE_FIRST_FAILED_GATE_WITHOUT_RETRY",
    }


def parse_args(
    *,
    recursive_depth_choices: Sequence[int] = SUPPORTED_RECURSIVE_DEPTHS,
    recursive_depth_default: int = 3,
) -> argparse.Namespace:
    require(
        recursive_depth_default in recursive_depth_choices,
        "recursive-depth default is not admitted",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--model", type=Path, default=harness.DEFAULT_MODEL)
    parser.add_argument("--ctx-checkpoints", type=int, choices=(0,), default=0)
    parser.add_argument(
        "--recursive-depth",
        type=int,
        choices=tuple(recursive_depth_choices),
        default=recursive_depth_default,
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--server-log-output", type=Path)
    return parser.parse_args()


def finalize_after_cleanup(
    result: dict[str, Any],
    *,
    cleanup: Mapping[str, Any],
    cleanup_wall_seconds: float,
    stable_pids: set[int],
    recursive_depth: int = 3,
    contract: RecurrenceContract | None = None,
) -> dict[str, Any]:
    active = validate_contract(contract or absorbing_contract(recursive_depth))
    require(
        active.recursive_depth == recursive_depth,
        "cleanup recurrence contract depth changed",
    )
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
    if active.exact_cycle_period == 4:
        result["quality_gates"]["reversible_period4_fixed_size_recurrence_supported"] = accepted
    if active.phase_root_ring:
        result["quality_gates"]["checksum_addressed_cuda_phase_root_ring_supported"] = accepted
    result["status"] = "complete"
    result["verdict"] = "accept" if accepted else "reject"
    if accepted:
        result["classification"] = active.accepted_classification
        result["next_boundary"] = active.next_boundary
    elif scientific_gate:
        result["classification"] = "fixed-size-rebase-cleanup-or-residency-failure"
        result["next_boundary"] = (
            "PRESERVE_EXECUTED_EVIDENCE_AND_LOCALIZE_CLEANUP_OR_RESIDENCY_FAILURE_WITHOUT_RETRY"
        )
    return result


def main(*, contract: RecurrenceContract | None = None) -> int:
    active = validate_contract(contract) if contract is not None else None
    args = parse_args(
        recursive_depth_choices=(
            (active.recursive_depth,) if active is not None else SUPPORTED_RECURSIVE_DEPTHS
        ),
        recursive_depth_default=active.recursive_depth if active is not None else 3,
    )
    active = active or absorbing_contract(args.recursive_depth)
    experiment_id = active.experiment_id
    repository = Path(__file__).resolve().parents[1]
    binary = args.binary.resolve(strict=True)
    require(
        binary == (repository / DEFAULT_BINARY).resolve(strict=True),
        "fixed-size rebase requires the isolated candidate binary",
    )
    cuda_runtime_sha256 = verify_cuda_runtime(binary, active)
    model = args.model.resolve(strict=True)
    latency.require_unused_artifact_paths(args.output, args.server_log_output)
    corpus = harness.carrier.load_public_corpus(repository)
    roots = {str(item["root_id"]): item for item in corpus["roots"]}
    evaluator, live_contract = harness.load_discovery_sidecar_contract()
    stable_pids = harness.live_runtime.require_stable()
    require(len(stable_pids) == 1, "fixed-size rebase requires the sole stable listener")
    require(not harness.live_runtime.listener_pids(harness.live_runtime.PORT), "frontier port is occupied")
    state_root = Path(
        tempfile.mkdtemp(
            prefix=(
                f"neo3000-fixed-size-rebase-{active.recurrence_id}-"
                f"r{args.recursive_depth}-"
            )
        )
    )
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
            recursive_depth=args.recursive_depth,
            contract=active,
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
                    "experiment_id": experiment_id,
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
        recursive_depth=args.recursive_depth,
        contract=active,
    )
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
