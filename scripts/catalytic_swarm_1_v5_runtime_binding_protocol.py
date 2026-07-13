#!/usr/bin/env python3
"""Frozen complete-object contract for CS1-v5 runtime evidence identity."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from catalytic_swarm_1_v4_partial_execution_boundary import EXPECTED_V4_PARTIAL_EXECUTION_BOUNDARY_SHA256
from catalytic_swarm_1_v5_runtime_binding import (
    STAGE_BINDINGS,
    V1_SCHEDULER_CONTRACT_SHA256,
    V5_ATTEMPT_VERSION,
    V5_CLAIM_CONTRACT_SHA256,
    V5_OPERATION,
    V5_RUNTIME_VERSION,
    V5_SCHEMA_VERSION,
    V5_STATE_ROOT,
    V5_VERDICT_KEY,
)


EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256 = (
    "2b2bcfaadf80d15d2972a4952f4b66026f2dd6979427f6cc32f197c6692903d9"
)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_object(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(dict(value))).hexdigest()


def build_v5_runtime_evidence_contract() -> dict[str, Any]:
    return {
        "id": "catalytic_swarm_1_v5_runtime_evidence_binding",
        "schema_version": 1,
        "purpose": "bind CS1-v5 completed-response evidence closure to v5 claim identity while preserving the immutable CS1-v1 evaluation geometry",
        "predecessor": {
            "id": "catalytic_swarm_1_v4_partial_execution_boundary",
            "sha256": EXPECTED_V4_PARTIAL_EXECUTION_BOUNDARY_SHA256,
            "authority_consumed": True,
            "no_retry": True,
        },
        "runtime_identity": {
            "runtime_version": V5_RUNTIME_VERSION,
            "artifact_schema_version": V5_SCHEMA_VERSION,
            "attempt_version": V5_ATTEMPT_VERSION,
            "operation": V5_OPERATION,
            "verdict_key": V5_VERDICT_KEY,
            "state_root": V5_STATE_ROOT,
        },
        "claim_contract": {
            "evaluator_key": "catalytic_swarm_1_v5",
            "lock_key": "catalytic_swarm_1_v5_sha256",
            "sha256": V5_CLAIM_CONTRACT_SHA256,
            "authoritative_for": ["completed-response closure", "v5 namespace", "artifact identity", "claim limits", "successor version"],
        },
        "scheduler_contract": {
            "evaluator_key": "catalytic_swarm_1",
            "lock_key": "catalytic_swarm_1_sha256",
            "sha256": V1_SCHEDULER_CONTRACT_SHA256,
            "authoritative_for": ["task suite", "four arm plans", "counterbalanced execution order", "request and token budgets", "hidden scoring", "advantage gate"],
        },
        "stage_bindings": {name: dict(value) for name, value in STAGE_BINDINGS.items()},
        "evidence_law": {
            "claim_contract_hash_recorded_in_every_artifact": True,
            "scheduler_contract_hash_recorded_in_every_artifact": True,
            "v5_verdict_key_present_before_first_persist": True,
            "predecessor_verdict_keys_forbidden_in_v5_artifacts": True,
            "post_persistence_verdict_rename_forbidden": True,
            "wrapper_return_identity_equals_persisted_identity": True,
            "empty_ledger_claimed_before_first_model_request": True,
            "every_completed_response_identity_bound_before_append": True,
            "ledger_record_fsynced_before_acceptance_enforcement": True,
            "completed_rejection_reason_persisted": True,
            "post_request_boundary_outcome_persisted": True,
            "partial_v4_evidence_preserved": True,
            "automatic_promotion": False,
        },
        "execution_geometry": {
            "common_root_warm_requests": 8,
            "comparison_requests": 1024,
            "total_model_requests": 1032,
            "custody_checks": 2064,
            "host_checks": 1032,
            "task_parity_checks": 8,
            "physical_slots": 1,
            "deep_requests": 0,
        },
        "claim_limits": {
            "CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN": "LOCKED until exact v5 advantage gate",
            "SOTA_SWARM_CLAIM": "LOCKED",
            "PROCESS_LOCAL_HOLOSTATE_AVAILABLE": "LOCKED",
            "RESTART_PERSISTENT_HOLOSTATE_AVAILABLE": "LOCKED",
            "automatic_promotion": False,
        },
    }


def validate_v5_runtime_evidence_contract(value: Mapping[str, Any]) -> None:
    expected = build_v5_runtime_evidence_contract()
    if canonical_json_bytes(dict(value)) != canonical_json_bytes(expected):
        raise ValueError("CS1-v5 runtime evidence contract differs from canonical")
    if sha256_object(value) != EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256:
        raise ValueError("CS1-v5 runtime evidence contract hash drifted")
