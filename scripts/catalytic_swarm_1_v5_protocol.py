#!/usr/bin/env python3
"""CS1-v5 successor repairing completed-response evidence closure only."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping

from catalytic_swarm_1_v4_partial_execution_boundary import (
    EXPECTED_V4_PARTIAL_EXECUTION_BOUNDARY_SHA256,
)
from catalytic_swarm_1_v4_protocol import (
    EXPECTED_V4_CONTRACT_SHA256,
    build_catalytic_swarm_1_v4_contract,
)


EXPECTED_V5_CONTRACT_SHA256 = "6238ff09ba290e55ad6c5cc2c93b4cbc239d573644192cf101696416a7083e3c"
V5_OVERLAY_SHA256 = "37fb4c0985dcaed270122ec5e1ee4d0302a714a0368a14e4014c8426ce9fb680"


class CatalyticSwarm1V5ProtocolError(RuntimeError):
    """The consumed v4 boundary or v5 evidence-closure successor changed."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_object(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(dict(value))).hexdigest()


def build_catalytic_swarm_1_v5_overlay() -> dict[str, Any]:
    return {
        "id": "catalytic_swarm_1_v5_overlay",
        "schema_version": 1,
        "base_contract": {
            "id": "catalytic_swarm_1_v4",
            "sha256": EXPECTED_V4_CONTRACT_SHA256,
            "status": "EXECUTED ONCE / PARTIAL / INCONCLUSIVE / AUTHORITY CONSUMED / NO RETRY",
        },
        "predecessor_boundary": {
            "id": "catalytic_swarm_1_v4_partial_execution_boundary",
            "sha256": EXPECTED_V4_PARTIAL_EXECUTION_BOUNDARY_SHA256,
        },
        "effective_version": {"id": "catalytic_swarm_1_v5", "schema_version": 5, "attempt_version": 5},
        "causal_intervention": {
            "only_change": "close one bounded identity-bound observation, post-request resource boundary, and durable ledger record for every completed model response before enforcing response acceptance",
            "accepted_model_behavior_unchanged": True,
            "task_suite_prompts_hidden_data_unchanged": True,
            "candidate_programs_and_arm_plans_unchanged": True,
            "latin_square_order_unchanged": True,
            "request_and_token_budgets_unchanged": True,
            "root_terminal_cache_law_unchanged": True,
            "scoring_parity_and_acceptance_thresholds_unchanged": True,
        },
        "completed_response_closure": {
            "sequence": [
                "pre-request-custody-and-freshness",
                "acquire-one-physical-lease",
                "execute-model-request",
                "mark-model-completion-exactly-once",
                "capture-bounded-metadata-only-observation",
                "run-post-request-custody-wddm-and-host-private-boundary",
                "append-one-identity-bound-durable-ledger-record",
                "persist-bounded-reason-codes-and-gate-outcomes",
                "release-lease",
                "enforce-acceptance-or-stop",
            ],
            "states": [
                "request-never-reached-model-completion",
                "completed-and-accepted",
                "completed-and-rejected",
                "post-response-instrumentation-failed",
                "post-request-resource-boundary-failed",
            ],
            "normal_equality_law": "completed_model_requests == host_memory_boundaries == ledger_records",
            "rejected_response_remains_rejected": True,
            "no_next_request_after_failed_gate": True,
            "ledger_fsync_before_acceptance_enforcement": True,
            "result_fallback_only_for_adjudicated_ledger_persistence_failure": True,
            "metadata_only": True,
            "raw_sse_persisted": False,
            "raw_payloads_persisted": False,
            "reasoning_text_persisted": False,
            "hidden_examples_persisted": False,
            "answer_keys_persisted": False,
        },
        "one_shot": {
            "paths": {
                "control": "state/catalytic_swarm_1_v5/control-qualification-v5.json",
                "readiness": "state/catalytic_swarm_1_v5/readiness-v5.json",
                "parser_canary": "state/catalytic_swarm_1_v5/parser-canary-v5.json",
                "attempt": "state/catalytic_swarm_1_v5/attempt-v5.json",
                "result": "state/catalytic_swarm_1_v5/result-v5.json",
                "ledger": "state/catalytic_swarm_1_v5/ledger-v5.jsonl",
                "task_results": "state/catalytic_swarm_1_v5/task-results-v5.json",
            },
            "no_retry": True,
            "partial_evidence_preserved": True,
        },
        "namespace_law": {
            "required_namespace": "state/catalytic_swarm_1_v5",
            "forbidden_namespaces": [
                "state/catalytic_swarm_1",
                "state/catalytic_swarm_1_cache_diagnostic",
                "state/catalytic_swarm_1_v2",
                "state/catalytic_swarm_1_v3",
                "state/catalytic_swarm_1_v4",
            ],
            "semantic_key_set_exact": True,
            "explicit_canonical_projection": True,
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
            "CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN": "LOCKED until exact v5 advantage gate",
            "SOTA_SWARM_CLAIM": "LOCKED",
            "PROCESS_LOCAL_HOLOSTATE_AVAILABLE": "LOCKED",
            "RESTART_PERSISTENT_HOLOSTATE_AVAILABLE": "LOCKED",
            "automatic_promotion": False,
        },
    }


def validate_v5_overlay(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = build_catalytic_swarm_1_v5_overlay()
    if canonical_json_bytes(dict(value)) != canonical_json_bytes(expected):
        raise CatalyticSwarm1V5ProtocolError("v5 overlay differs from canonical")
    if sha256_object(value) != V5_OVERLAY_SHA256:
        raise CatalyticSwarm1V5ProtocolError("v5 overlay hash drifted")
    return expected


def apply_v5_overlay_unchecked(
    v4_contract: Mapping[str, Any], overlay: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    active = copy.deepcopy(dict(v4_contract))
    frozen = validate_v5_overlay(build_catalytic_swarm_1_v5_overlay() if overlay is None else overlay)
    active["id"] = frozen["effective_version"]["id"]
    active["schema_version"] = frozen["effective_version"]["schema_version"]
    active["attempt_version"] = frozen["effective_version"]["attempt_version"]
    active["objective"] = str(active["objective"]) + " The v5 successor repairs completed-response evidence closure only."
    active["one_shot"] = copy.deepcopy(frozen["one_shot"])
    predecessors = copy.deepcopy(active.get("predecessors", {}))
    predecessors["catalytic_swarm_1_v4_partial_execution"] = {
        **copy.deepcopy(frozen["predecessor_boundary"]),
        "authority_consumed": True,
        "no_retry": True,
        "artifacts_claimed": 7,
        "completed_model_requests": 775,
        "ledger_records": 774,
        "host_memory_checks": 774,
        "task_advantage_adjudicated": False,
    }
    active["predecessors"] = predecessors
    active["completed_response_closure_repair"] = {
        "base_contract_sha256": frozen["base_contract"]["sha256"],
        "overlay_sha256": V5_OVERLAY_SHA256,
        **copy.deepcopy(frozen["causal_intervention"]),
        **copy.deepcopy(frozen["completed_response_closure"]),
        **copy.deepcopy(frozen["namespace_law"]),
    }
    active.pop("semantic_mapping_repair", None)
    return active


def build_catalytic_swarm_1_v5_contract(
    v4_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if v4_contract is None:
        v4_contract = build_catalytic_swarm_1_v4_contract()
    if sha256_object(v4_contract) != EXPECTED_V4_CONTRACT_SHA256:
        raise CatalyticSwarm1V5ProtocolError("CS1-v4 base contract hash changed")
    return apply_v5_overlay_unchecked(v4_contract)


def effective_v5_contract_sha256() -> str:
    return sha256_object(build_catalytic_swarm_1_v5_contract())
