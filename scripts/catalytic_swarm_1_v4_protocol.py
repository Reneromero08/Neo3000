#!/usr/bin/env python3
"""Frozen CS1-v4 successor with semantic one-shot mapping admission only."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping

from catalytic_swarm_1_v3_preclaim_boundary import (
    EXPECTED_V3_PRECLAIM_BOUNDARY_SHA256,
)
from catalytic_swarm_1_v3_protocol import (
    EXPECTED_V3_CONTRACT_SHA256,
    build_catalytic_swarm_1_v3_contract,
)


EXPECTED_V4_CONTRACT_SHA256 = "2ba862a097da4b3c6bb2e2fbececa49296b38a8c9b5b047f6c281b84c3111ece"
V4_OVERLAY_SHA256 = "264594a24b430f780303150884673289d35868d3eb6aabbac05846512d794a82"


class CatalyticSwarm1V4ProtocolError(RuntimeError):
    """The v3 predecessor or v4 semantic-order successor changed."""


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


def build_catalytic_swarm_1_v4_overlay() -> dict[str, Any]:
    return {
        "id": "catalytic_swarm_1_v4_overlay",
        "schema_version": 1,
        "base_contract": {
            "id": "catalytic_swarm_1_v3",
            "sha256": EXPECTED_V3_CONTRACT_SHA256,
            "status": "COMMAND INVOCATION CONSUMED / PRECLAIM FAIL-CLOSED / ONE CONTROL ARTIFACT / NO RETRY",
        },
        "predecessor_boundary": {
            "id": "catalytic_swarm_1_v3_preclaim_boundary",
            "sha256": EXPECTED_V3_PRECLAIM_BOUNDARY_SHA256,
        },
        "effective_version": {
            "id": "catalytic_swarm_1_v4",
            "schema_version": 4,
            "attempt_version": 4,
        },
        "causal_intervention": {
            "only_change": "replace insertion-order-sensitive one-shot mapping admission with exact semantic key-set validation followed by explicit canonical stage-order projection",
            "source_mapping_insertion_order_authoritative": False,
            "canonical_stage_order_explicit": True,
            "path_to_stage_identity_unchanged": True,
            "root_terminal_cache_law_unchanged": True,
            "task_suite_arms_budgets_and_thresholds_unchanged": True,
            "runtime_safety_laws_unchanged": True,
        },
        "one_shot": {
            "paths": {
                "control": "state/catalytic_swarm_1_v4/control-qualification-v4.json",
                "readiness": "state/catalytic_swarm_1_v4/readiness-v4.json",
                "parser_canary": "state/catalytic_swarm_1_v4/parser-canary-v4.json",
                "attempt": "state/catalytic_swarm_1_v4/attempt-v4.json",
                "result": "state/catalytic_swarm_1_v4/result-v4.json",
                "ledger": "state/catalytic_swarm_1_v4/ledger-v4.jsonl",
                "task_results": "state/catalytic_swarm_1_v4/task-results-v4.json",
            },
            "no_retry": True,
            "partial_evidence_preserved": True,
        },
        "namespace_law": {
            "required_namespace": "state/catalytic_swarm_1_v4",
            "forbidden_namespaces": [
                "state/catalytic_swarm_1",
                "state/catalytic_swarm_1_cache_diagnostic",
                "state/catalytic_swarm_1_v2",
                "state/catalytic_swarm_1_v3",
            ],
            "semantic_key_set_exact": True,
            "explicit_canonical_projection": True,
            "active_artifact_tuple_compared_by_named_stage": True,
            "inherited_predecessor_map_consulted": False,
            "qualification_after_invocation_claim_before_sidecar": True,
        },
        "execution_geometry": {
            "common_root_warm_requests": 8,
            "comparison_requests": 1024,
            "total_model_requests": 1032,
            "task_count": 8,
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


def validate_v4_overlay(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = build_catalytic_swarm_1_v4_overlay()
    if canonical_json_bytes(dict(value)) != canonical_json_bytes(expected):
        raise CatalyticSwarm1V4ProtocolError("v4 overlay differs from canonical")
    if sha256_object(value) != V4_OVERLAY_SHA256:
        raise CatalyticSwarm1V4ProtocolError("v4 overlay hash drifted")
    return expected


def apply_v4_overlay_unchecked(
    v3_contract: Mapping[str, Any],
    overlay: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    active = copy.deepcopy(dict(v3_contract))
    frozen = validate_v4_overlay(
        build_catalytic_swarm_1_v4_overlay() if overlay is None else overlay
    )
    active["id"] = frozen["effective_version"]["id"]
    active["schema_version"] = frozen["effective_version"]["schema_version"]
    active["attempt_version"] = frozen["effective_version"]["attempt_version"]
    active["objective"] = (
        str(active["objective"])
        + " The v4 successor repairs only insertion-order-sensitive one-shot mapping admission."
    )
    active["one_shot"] = copy.deepcopy(frozen["one_shot"])
    predecessors = copy.deepcopy(active.get("predecessors", {}))
    predecessors["catalytic_swarm_1_v3_preclaim"] = {
        **copy.deepcopy(frozen["predecessor_boundary"]),
        "authority_consumed": True,
        "no_retry": True,
        "artifacts_claimed": 1,
        "model_requests": 0,
        "sidecar_launches": 0,
    }
    active["predecessors"] = predecessors
    active["semantic_mapping_repair"] = {
        "base_contract_sha256": frozen["base_contract"]["sha256"],
        "overlay_sha256": V4_OVERLAY_SHA256,
        **copy.deepcopy(frozen["causal_intervention"]),
        **copy.deepcopy(frozen["namespace_law"]),
    }
    active.pop("versioned_namespace_repair", None)
    return active


def build_catalytic_swarm_1_v4_contract(
    v3_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if v3_contract is None:
        v3_contract = build_catalytic_swarm_1_v3_contract()
    if sha256_object(v3_contract) != EXPECTED_V3_CONTRACT_SHA256:
        raise CatalyticSwarm1V4ProtocolError("CS1-v3 base contract hash changed")
    return apply_v4_overlay_unchecked(v3_contract)


def effective_v4_contract_sha256() -> str:
    return sha256_object(build_catalytic_swarm_1_v4_contract())
