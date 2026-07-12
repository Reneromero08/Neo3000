#!/usr/bin/env python3
"""Frozen overlay contract for the separately versioned CatalyticSwarm-1 v3 repair.

V3 inherits the exact CS1-v2 task-advantage contract and changes only versioned
one-shot namespace qualification. This module performs no live execution.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping

V2_CONTRACT_SHA256 = "911242c74509f1d2d8c6a3c8aa82948c452dac5f4646dd97d70d7b27b750e984"
V2_PRECLAIM_BOUNDARY_SHA256 = "dc64c8dff9dc129a3002629bdf97dd9114fc89f7fa01bd0744af7b8fbd3adb1e"
V3_OVERLAY_SHA256 = "4381a5926cbae84e00f138145547e0e44e2cae814b0bcc6b44b936b7c847525a"
EXPECTED_V3_CONTRACT_SHA256 = "433b4d4e418614c2e9c2b177f46b68d24710921b11d8d7e848a226da22c1fd27"

_PRECLAIM_JSON = r'''{"id": "catalytic_swarm_1_v2_preclaim_boundary", "schema_version": 1, "protected_main": "68754b95104a55fead6e13d2cb69e9e328a07092", "contract_sha256": "911242c74509f1d2d8c6a3c8aa82948c452dac5f4646dd97d70d7b27b750e984", "command": "audit-catalytic-swarm-1-v2", "authority": {"command_attempt_consumed": true, "retry_count": 0, "no_retry": true}, "stop": {"stage": "preclaim-before-artifact", "message": "CatalyticSwarm-1 one-shot path law changed", "cause": "inherited v1 control qualification compared the active v2 contract and runtime paths against the immutable v1 one-shot path map", "fail_closed": true}, "runtime": {"model_requests": 0, "sidecar_launches": 0, "v2_artifacts_claimed": 0, "v2_state_root_absent": true, "port_9494_free": true, "stable_health_ok": true}, "custody": {"head_main_origin_remote_equal": true, "head": "68754b95104a55fead6e13d2cb69e9e328a07092", "candidate_head": "14de9c71593e5aea4fcfcadeda47ba5c623fadcf", "candidate_clean": true, "cs1_v1_artifacts_exact": true, "cache_diagnostic_artifacts_exact": true}, "claims": {"CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN": "LOCKED", "SOTA_SWARM_CLAIM": "LOCKED", "PROCESS_LOCAL_HOLOSTATE_AVAILABLE": "LOCKED", "RESTART_PERSISTENT_HOLOSTATE_AVAILABLE": "LOCKED", "automatic_promotion": false}}'''
_OVERLAY_JSON = r'''{"id": "catalytic_swarm_1_v3_overlay", "schema_version": 1, "base_contract": {"id": "catalytic_swarm_1_v2", "sha256": "911242c74509f1d2d8c6a3c8aa82948c452dac5f4646dd97d70d7b27b750e984", "status": "COMMAND ATTEMPT CONSUMED / PRECLAIM FAIL-CLOSED / NO ARTIFACTS"}, "predecessor_boundary": {"id": "catalytic_swarm_1_v2_preclaim_boundary", "sha256": "dc64c8dff9dc129a3002629bdf97dd9114fc89f7fa01bd0744af7b8fbd3adb1e"}, "effective_version": {"id": "catalytic_swarm_1_v3", "schema_version": 3, "attempt_version": 3}, "causal_intervention": {"only_change": "qualify one-shot paths against the active version contract and active version artifact tuple instead of immutable v1 path constants", "root_terminal_cache_law_unchanged": true, "task_suite_arms_budgets_and_thresholds_unchanged": true, "runtime_safety_laws_unchanged": true}, "one_shot": {"paths": {"control": "state/catalytic_swarm_1_v3/control-qualification-v3.json", "readiness": "state/catalytic_swarm_1_v3/readiness-v3.json", "parser_canary": "state/catalytic_swarm_1_v3/parser-canary-v3.json", "attempt": "state/catalytic_swarm_1_v3/attempt-v3.json", "result": "state/catalytic_swarm_1_v3/result-v3.json", "ledger": "state/catalytic_swarm_1_v3/ledger-v3.jsonl", "task_results": "state/catalytic_swarm_1_v3/task-results-v3.json"}, "no_retry": true, "partial_evidence_preserved": true}, "namespace_law": {"required_namespace": "state/catalytic_swarm_1_v3", "forbidden_namespaces": ["state/catalytic_swarm_1", "state/catalytic_swarm_1_cache_diagnostic", "state/catalytic_swarm_1_v2"], "contract_path_map_compared_to_active_version_artifact_tuple": true, "inherited_v1_path_map_consulted": false, "qualification_before_artifact_claim": true}, "execution_geometry": {"common_root_warm_requests": 8, "comparison_requests": 1024, "total_model_requests": 1032, "task_count": 8, "physical_slots": 1, "deep_requests": 0}, "claim_limits": {"CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN": "LOCKED until exact v3 advantage gate", "SOTA_SWARM_CLAIM": "LOCKED", "PROCESS_LOCAL_HOLOSTATE_AVAILABLE": "LOCKED", "RESTART_PERSISTENT_HOLOSTATE_AVAILABLE": "LOCKED", "automatic_promotion": false}}'''


class CatalyticSwarm1V3ProtocolError(RuntimeError):
    """The v2 base, preclaim boundary, or v3 overlay differs from canonical."""


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


def build_v2_preclaim_boundary() -> dict[str, Any]:
    return json.loads(_PRECLAIM_JSON)


def build_catalytic_swarm_1_v3_overlay() -> dict[str, Any]:
    return json.loads(_OVERLAY_JSON)


def validate_v2_preclaim_boundary(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = build_v2_preclaim_boundary()
    if canonical_json_bytes(value) != canonical_json_bytes(expected):
        raise CatalyticSwarm1V3ProtocolError("v2 preclaim boundary differs from canonical")
    if sha256_object(value) != V2_PRECLAIM_BOUNDARY_SHA256:
        raise CatalyticSwarm1V3ProtocolError("v2 preclaim boundary hash drifted")
    return expected


def validate_v3_overlay(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = build_catalytic_swarm_1_v3_overlay()
    if canonical_json_bytes(value) != canonical_json_bytes(expected):
        raise CatalyticSwarm1V3ProtocolError("v3 overlay differs from canonical")
    if sha256_object(value) != V3_OVERLAY_SHA256:
        raise CatalyticSwarm1V3ProtocolError("v3 overlay hash drifted")
    return expected


def apply_v3_overlay_unchecked(
    v2_contract: Mapping[str, Any],
    overlay: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply the frozen overlay after the caller has established v2 identity."""
    active = copy.deepcopy(dict(v2_contract))
    frozen = validate_v3_overlay(
        build_catalytic_swarm_1_v3_overlay() if overlay is None else overlay
    )
    active["id"] = frozen["effective_version"]["id"]
    active["schema_version"] = frozen["effective_version"]["schema_version"]
    active["attempt_version"] = frozen["effective_version"]["attempt_version"]
    active["objective"] = (
        str(active["objective"])
        + " The v3 successor repairs only active-version one-shot namespace qualification."
    )
    active["one_shot"] = copy.deepcopy(frozen["one_shot"])
    predecessors = copy.deepcopy(active.get("predecessors", {}))
    predecessors["catalytic_swarm_1_v2_preclaim"] = {
        **copy.deepcopy(frozen["predecessor_boundary"]),
        "authority_consumed": True,
        "no_retry": True,
        "artifacts_claimed": 0,
        "model_requests": 0,
        "sidecar_launches": 0,
    }
    active["predecessors"] = predecessors
    active["versioned_namespace_repair"] = {
        "base_contract_sha256": frozen["base_contract"]["sha256"],
        "overlay_sha256": V3_OVERLAY_SHA256,
        **copy.deepcopy(frozen["causal_intervention"]),
        **copy.deepcopy(frozen["namespace_law"]),
    }
    return active


def build_catalytic_swarm_1_v3_contract(
    v2_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if v2_contract is None:
        from catalytic_swarm_1_v2_protocol import (
            build_catalytic_swarm_1_v2_contract,
        )
        v2_contract = build_catalytic_swarm_1_v2_contract()
    if sha256_object(v2_contract) != V2_CONTRACT_SHA256:
        raise CatalyticSwarm1V3ProtocolError("CS1-v2 base contract hash changed")
    return apply_v3_overlay_unchecked(v2_contract)


def effective_v3_contract_sha256(
    v2_contract: Mapping[str, Any] | None = None,
) -> str:
    return sha256_object(build_catalytic_swarm_1_v3_contract(v2_contract))
