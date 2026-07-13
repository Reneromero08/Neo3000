#!/usr/bin/env python3
"""Frozen complete-object contract for CS1-v6 runtime evidence identity."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from catalytic_swarm_1_v6_runtime_binding import (
    ARTIFACT_PATHS,
    STAGE_BINDINGS,
    V1_SCHEDULER_CONTRACT_SHA256,
    V5_PARTIAL_EXECUTION_BOUNDARY_SHA256,
    V6_ATTEMPT_VERSION,
    V6_CLAIM_CONTRACT_SHA256,
    V6_OPERATION,
    V6_RUNTIME_VERSION,
    V6_SCHEMA_VERSION,
    V6_STATE_ROOT,
    V6_VERDICT_KEY,
)


EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256 = (
    "3ccb810684824a5935c89150e0f84ca820f8402f7650d3fdcf027e84ac9f9ad3"
)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_object(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(dict(value))).hexdigest()


def build_v6_runtime_evidence_contract() -> dict[str, Any]:
    return {
        "id": "catalytic_swarm_1_v6_runtime_evidence_binding",
        "schema_version": 1,
        "purpose": "bind CS1-v6 independent post-request sub-boundary closure before persistence while preserving immutable CS1-v1 evaluation geometry",
        "predecessor": {
            "id": "catalytic_swarm_1_v5_partial_execution_boundary",
            "sha256": V5_PARTIAL_EXECUTION_BOUNDARY_SHA256,
            "authority_consumed": True,
            "no_retry": True,
            "completed_model_requests": 775,
            "ledger_records": 775,
            "result_fallback_records": 0,
        },
        "runtime_identity": {
            "runtime_version": V6_RUNTIME_VERSION,
            "artifact_schema_version": V6_SCHEMA_VERSION,
            "attempt_version": V6_ATTEMPT_VERSION,
            "operation": V6_OPERATION,
            "verdict_key": V6_VERDICT_KEY,
            "state_root": V6_STATE_ROOT,
        },
        "claim_contract": {
            "evaluator_key": "catalytic_swarm_1_v6",
            "lock_key": "catalytic_swarm_1_v6_sha256",
            "sha256": V6_CLAIM_CONTRACT_SHA256,
            "authoritative_for": [
                "independent post-request sub-boundary closure",
                "v6 namespace",
                "artifact identity",
                "claim limits",
                "successor version",
            ],
        },
        "scheduler_contract": {
            "evaluator_key": "catalytic_swarm_1",
            "lock_key": "catalytic_swarm_1_sha256",
            "sha256": V1_SCHEDULER_CONTRACT_SHA256,
            "authoritative_for": [
                "task suite",
                "four arm plans",
                "counterbalanced execution order",
                "request and token budgets",
                "hidden scoring",
                "advantage gate",
            ],
        },
        "artifact_paths": dict(ARTIFACT_PATHS),
        "stage_bindings": {name: dict(value) for name, value in STAGE_BINDINGS.items()},
        "post_request_boundary_law": {
            "ordered_sub_boundaries": ["wddm", "stable_custody", "candidate_custody", "host_memory"],
            "states": ["passed", "failed-invariant", "observation-error", "unavailable", "interrupted", "blocked"],
            "group_started_before_first_observer": True,
            "attempt_recorded_before_each_observer_call": True,
            "later_safe_observations_do_not_short_circuit": True,
            "attempt_observation_and_pass_counts_are_distinct": True,
            "bounded_exception_identity_required_for_errors": True,
            "measured_fields_preserved_when_available": True,
            "full_ordered_reason_list_preserved": True,
            "rejected_response_remains_rejected": True,
        },
        "evidence_law": {
            "claim_contract_hash_recorded_in_every_artifact": True,
            "scheduler_contract_hash_recorded_in_every_artifact": True,
            "predecessor_boundary_hash_recorded_in_every_artifact": True,
            "v6_runtime_identity_present_before_first_persist": True,
            "predecessor_verdict_and_stage_keys_v1_through_v5_forbidden": True,
            "post_persistence_verdict_rename_forbidden": True,
            "wrapper_return_identity_equals_persisted_identity": True,
            "empty_ledger_claimed_before_first_model_request": True,
            "every_completed_response_identity_bound_before_append": True,
            "ledger_or_result_fallback_persisted_before_lease_release": True,
            "ledger_or_result_fallback_persisted_before_acceptance_enforcement": True,
            "v5_persistence_and_result_fallback_law_preserved": True,
            "partial_v5_evidence_preserved": True,
            "automatic_promotion": False,
        },
        "execution_geometry": {
            "common_root_warm_requests": 8,
            "comparison_requests": 1024,
            "total_model_requests": 1032,
            "post_request_groups": 1032,
            "wddm_attempts": 1032,
            "stable_custody_attempts": 1032,
            "candidate_custody_attempts": 1032,
            "host_memory_attempts": 1032,
            "task_parity_checks": 8,
            "physical_slots": 1,
            "max_tokens_per_request": 32,
            "deep_requests": 0,
        },
        "claim_limits": {
            "CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN": "LOCKED until exact v6 advantage gate",
            "SOTA_SWARM_CLAIM": "LOCKED",
            "PROCESS_LOCAL_HOLOSTATE_AVAILABLE": "LOCKED",
            "RESTART_PERSISTENT_HOLOSTATE_AVAILABLE": "LOCKED",
            "automatic_promotion": False,
        },
    }


def validate_v6_runtime_evidence_contract(value: Mapping[str, Any]) -> None:
    expected = build_v6_runtime_evidence_contract()
    if canonical_json_bytes(dict(value)) != canonical_json_bytes(expected):
        raise ValueError("CS1-v6 runtime evidence contract differs from canonical")
    if sha256_object(value) != EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256:
        raise ValueError("CS1-v6 runtime evidence contract hash drifted")
