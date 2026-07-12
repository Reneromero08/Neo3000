#!/usr/bin/env python3
"""Frozen complete-object contract for the CS1-v3 runtime evidence binding."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from catalytic_swarm_1_v3_runtime_binding import (
    STAGE_BINDINGS,
    V1_SCHEDULER_CONTRACT_SHA256,
    V3_ATTEMPT_VERSION,
    V3_CLAIM_CONTRACT_SHA256,
    V3_EVALUATOR_KEY,
    V3_LOCK_KEY,
    V3_OPERATION,
    V3_RUNTIME_VERSION,
    V3_SCHEMA_VERSION,
    V3_STATE_ROOT,
    V3_VERDICT_KEY,
)

SCHEMA_VERSION = 1


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_object(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(dict(value))).hexdigest()


def build_v3_runtime_evidence_contract() -> dict[str, Any]:
    return {
        "id": "catalytic_swarm_1_v3_runtime_evidence_binding",
        "schema_version": SCHEMA_VERSION,
        "purpose": (
            "bind the unexecuted CS1-v3 scheduler to v3-labelled claim evidence "
            "while preserving the immutable CS1-v1 evaluation geometry"
        ),
        "runtime_identity": {
            "runtime_version": V3_RUNTIME_VERSION,
            "artifact_schema_version": V3_SCHEMA_VERSION,
            "attempt_version": V3_ATTEMPT_VERSION,
            "operation": V3_OPERATION,
            "verdict_key": V3_VERDICT_KEY,
            "state_root": V3_STATE_ROOT,
        },
        "claim_contract": {
            "evaluator_key": V3_EVALUATOR_KEY,
            "lock_key": V3_LOCK_KEY,
            "sha256": V3_CLAIM_CONTRACT_SHA256,
            "authoritative_for": [
                "one-shot namespace",
                "root-terminal cache admission",
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
        "stage_bindings": {
            name: dict(value) for name, value in STAGE_BINDINGS.items()
        },
        "evidence_law": {
            "claim_contract_hash_recorded_in_every_artifact": True,
            "scheduler_contract_hash_recorded_in_every_artifact": True,
            "v3_verdict_key_present_before_first_persist": True,
            "v1_and_v2_verdict_keys_forbidden_in_v3_artifacts": True,
            "post_persistence_verdict_rename_forbidden": True,
            "wrapper_return_identity_equals_persisted_identity": True,
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
            "CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN": "LOCKED until exact v3 advantage gate",
            "SOTA_SWARM_CLAIM": "LOCKED",
            "PROCESS_LOCAL_HOLOSTATE_AVAILABLE": "LOCKED",
            "RESTART_PERSISTENT_HOLOSTATE_AVAILABLE": "LOCKED",
            "automatic_promotion": False,
        },
    }


EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256 = (
    "09d3c7753d3840b568d85642791425931dedc7bd34c017a16e84e606b7d3d681"
)


def validate_v3_runtime_evidence_contract(value: Mapping[str, Any]) -> None:
    expected = build_v3_runtime_evidence_contract()
    if canonical_json_bytes(dict(value)) != canonical_json_bytes(expected):
        raise ValueError("CS1-v3 runtime evidence contract differs from canonical")
    if sha256_object(value) != EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256:
        raise ValueError("CS1-v3 runtime evidence contract hash drifted")
