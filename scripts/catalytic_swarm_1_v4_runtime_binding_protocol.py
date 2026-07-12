#!/usr/bin/env python3
"""Frozen complete-object contract for CS1-v4 runtime evidence identity."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from catalytic_swarm_1_v3_preclaim_boundary import EXPECTED_V3_PRECLAIM_BOUNDARY_SHA256
from catalytic_swarm_1_v4_runtime_binding import (
    STAGE_BINDINGS,
    V1_SCHEDULER_CONTRACT_SHA256,
    V4_ATTEMPT_VERSION,
    V4_CLAIM_CONTRACT_SHA256,
    V4_OPERATION,
    V4_RUNTIME_VERSION,
    V4_SCHEMA_VERSION,
    V4_STATE_ROOT,
    V4_VERDICT_KEY,
)


EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256 = (
    "d7949912512316d551bf6466895fe7d52b44fe568590782b85e23c4cbd6e53e4"
)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_object(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(dict(value))).hexdigest()


def build_v4_runtime_evidence_contract() -> dict[str, Any]:
    return {
        "id": "catalytic_swarm_1_v4_runtime_evidence_binding",
        "schema_version": 1,
        "purpose": "bind the unexecuted CS1-v4 scheduler to v4-labelled claim evidence while preserving the immutable CS1-v1 evaluation geometry",
        "predecessor": {
            "id": "catalytic_swarm_1_v3_preclaim_boundary",
            "sha256": EXPECTED_V3_PRECLAIM_BOUNDARY_SHA256,
            "authority_consumed": True,
            "no_retry": True,
        },
        "runtime_identity": {
            "runtime_version": V4_RUNTIME_VERSION,
            "artifact_schema_version": V4_SCHEMA_VERSION,
            "attempt_version": V4_ATTEMPT_VERSION,
            "operation": V4_OPERATION,
            "verdict_key": V4_VERDICT_KEY,
            "state_root": V4_STATE_ROOT,
        },
        "claim_contract": {
            "evaluator_key": "catalytic_swarm_1_v4",
            "lock_key": "catalytic_swarm_1_v4_sha256",
            "sha256": V4_CLAIM_CONTRACT_SHA256,
            "authoritative_for": ["semantic one-shot namespace", "root-terminal cache admission", "artifact identity", "claim limits", "successor version"],
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
            "v4_verdict_key_present_before_first_persist": True,
            "predecessor_verdict_keys_forbidden_in_v4_artifacts": True,
            "post_persistence_verdict_rename_forbidden": True,
            "wrapper_return_identity_equals_persisted_identity": True,
            "first_ledger_record_identity_bound_at_exclusive_creation": True,
            "partial_evidence_preserved": True,
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
            "CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN": "LOCKED until exact v4 advantage gate",
            "SOTA_SWARM_CLAIM": "LOCKED",
            "PROCESS_LOCAL_HOLOSTATE_AVAILABLE": "LOCKED",
            "RESTART_PERSISTENT_HOLOSTATE_AVAILABLE": "LOCKED",
            "automatic_promotion": False,
        },
    }


def validate_v4_runtime_evidence_contract(value: Mapping[str, Any]) -> None:
    expected = build_v4_runtime_evidence_contract()
    if canonical_json_bytes(dict(value)) != canonical_json_bytes(expected):
        raise ValueError("CS1-v4 runtime evidence contract differs from canonical")
    if sha256_object(value) != EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256:
        raise ValueError("CS1-v4 runtime evidence contract hash drifted")
