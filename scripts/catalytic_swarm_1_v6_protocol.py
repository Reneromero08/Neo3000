#!/usr/bin/env python3
"""CS1-v6 successor for independent post-request sub-boundary closure."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping

from catalytic_swarm_1_v5_partial_execution_boundary import (
    EXPECTED_V5_PARTIAL_EXECUTION_BOUNDARY_SHA256,
)
from catalytic_swarm_1_v5_protocol import (
    EXPECTED_V5_CONTRACT_SHA256,
    build_catalytic_swarm_1_v5_contract,
)


EXPECTED_V6_CONTRACT_SHA256 = "8136be5c402497b539595eeccf1329807eba59fab9813891f0293fd1d271acd8"
V6_OVERLAY_SHA256 = "6f55a0ae5a75da3f0bef9f8e9b77e604b252305728fe8312f60288859b9d705b"


class CatalyticSwarm1V6ProtocolError(RuntimeError):
    """The consumed v5 boundary or v6 independent closure changed."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_object(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(dict(value))).hexdigest()


def build_catalytic_swarm_1_v6_overlay() -> dict[str, Any]:
    return {
        "id": "catalytic_swarm_1_v6_overlay",
        "schema_version": 1,
        "base_contract": {
            "id": "catalytic_swarm_1_v5",
            "sha256": EXPECTED_V5_CONTRACT_SHA256,
            "status": "EXECUTED ONCE / PARTIAL / INCONCLUSIVE / AUTHORITY CONSUMED / NO RETRY",
        },
        "predecessor_boundary": {
            "id": "catalytic_swarm_1_v5_partial_execution_boundary",
            "sha256": EXPECTED_V5_PARTIAL_EXECUTION_BOUNDARY_SHA256,
            "authority_consumed": True,
            "no_retry": True,
        },
        "effective_version": {
            "id": "catalytic_swarm_1_v6",
            "schema_version": 6,
            "attempt_version": 6,
        },
        "causal_intervention": {
            "only_change": "independently close WDDM, stable custody, candidate custody, and host memory after every completed model response",
            "accepted_model_behavior_unchanged": True,
            "v5_persistence_and_result_fallback_law_preserved": True,
            "rejected_response_remains_rejected": True,
            "task_suite_prompts_hidden_data_unchanged": True,
            "candidate_programs_and_arm_plans_unchanged": True,
            "latin_square_order_unchanged": True,
            "request_and_token_budgets_unchanged": True,
            "root_terminal_cache_law_unchanged": True,
            "scoring_parity_and_acceptance_thresholds_unchanged": True,
        },
        "independent_post_request_closure": {
            "ordered_sub_boundaries": [
                "wddm",
                "stable_custody",
                "candidate_custody",
                "host_memory",
            ],
            "required_fields": [
                "name",
                "required",
                "attempted",
                "attempt_ordinal",
                "attempted_at",
                "observation_completed",
                "state",
                "blocked",
                "passed",
                "reason_code",
                "blocked_by",
                "exception_type",
                "exception_message_sha256",
                "measurement",
            ],
            "states": [
                "passed",
                "failed-invariant",
                "observation-error",
                "unavailable",
                "interrupted",
                "blocked",
            ],
            "attempt_counter_advances_before_observer_call": True,
            "later_safe_observations_continue_after_earlier_nonpass": True,
            "unattempted_or_unavailable_never_encoded_as_false": True,
            "complete_ordered_reason_list_preserved": True,
            "deterministic_primary_reason_uses_sub_boundary_order": True,
            "groups_started_counter_required": True,
            "per_sub_boundary_attempt_observation_and_pass_counters_required": True,
            "normal_equality_law": "completed_model_requests == post_request_groups_started == attempts[wddm] == attempts[stable_custody] == attempts[candidate_custody] == attempts[host_memory] == ledger_records + result_fallback_records",
            "representation_law": "attempts[sub_boundary] + blocked_before_attempt[sub_boundary] == post_request_groups_started",
            "observation_law": "passes[sub_boundary] <= observations_completed[sub_boundary] <= attempts[sub_boundary]",
            "persistence_before_lease_release_and_enforcement": True,
            "no_next_request_after_required_nonpass": True,
            "metadata_only": True,
            "raw_sse_persisted": False,
            "raw_payloads_persisted": False,
            "reasoning_text_persisted": False,
            "hidden_examples_persisted": False,
            "answer_keys_persisted": False,
        },
        "one_shot": {
            "paths": {
                "control": "state/catalytic_swarm_1_v6/control-qualification-v6.json",
                "readiness": "state/catalytic_swarm_1_v6/readiness-v6.json",
                "parser_canary": "state/catalytic_swarm_1_v6/parser-canary-v6.json",
                "attempt": "state/catalytic_swarm_1_v6/attempt-v6.json",
                "result": "state/catalytic_swarm_1_v6/result-v6.json",
                "ledger": "state/catalytic_swarm_1_v6/ledger-v6.jsonl",
                "task_results": "state/catalytic_swarm_1_v6/task-results-v6.json",
            },
            "no_retry": True,
            "partial_evidence_preserved": True,
        },
        "namespace_law": {
            "required_namespace": "state/catalytic_swarm_1_v6",
            "forbidden_namespaces": [
                "state/catalytic_swarm_1",
                "state/catalytic_swarm_1_cache_diagnostic",
                "state/catalytic_swarm_1_v2",
                "state/catalytic_swarm_1_v3",
                "state/catalytic_swarm_1_v4",
                "state/catalytic_swarm_1_v5",
            ],
            "semantic_key_set_exact": True,
            "explicit_canonical_projection": True,
            "runtime_identity_bound_before_any_persistence": True,
        },
        "execution_geometry": {
            "common_root_warm_requests": 8,
            "comparison_requests": 1024,
            "total_model_requests": 1032,
            "task_count": 8,
            "candidate_count": 64,
            "arm_count": 4,
            "arm_runs": 32,
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


def validate_v6_overlay(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = build_catalytic_swarm_1_v6_overlay()
    if canonical_json_bytes(dict(value)) != canonical_json_bytes(expected):
        raise CatalyticSwarm1V6ProtocolError("v6 overlay differs from canonical")
    if sha256_object(value) != V6_OVERLAY_SHA256:
        raise CatalyticSwarm1V6ProtocolError("v6 overlay hash drifted")
    return expected


def apply_v6_overlay_unchecked(
    v5_contract: Mapping[str, Any], overlay: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    active = copy.deepcopy(dict(v5_contract))
    frozen = validate_v6_overlay(build_catalytic_swarm_1_v6_overlay() if overlay is None else overlay)
    active["id"] = frozen["effective_version"]["id"]
    active["schema_version"] = frozen["effective_version"]["schema_version"]
    active["attempt_version"] = frozen["effective_version"]["attempt_version"]
    active["objective"] = str(active["objective"]) + " The v6 successor independently closes each post-request sub-boundary."
    active["one_shot"] = copy.deepcopy(frozen["one_shot"])
    predecessors = copy.deepcopy(active.get("predecessors", {}))
    predecessors["catalytic_swarm_1_v5_partial_execution"] = {
        **copy.deepcopy(frozen["predecessor_boundary"]),
        "artifacts_claimed": 7,
        "completed_model_requests": 775,
        "ledger_records": 775,
        "result_fallback_records": 0,
        "host_memory_success_accounting": 774,
        "task_advantage_adjudicated": False,
        "exact_compound_failure_cause_available": False,
    }
    active["predecessors"] = predecessors
    active["independent_post_request_sub_boundary_closure"] = {
        "base_contract_sha256": frozen["base_contract"]["sha256"],
        "overlay_sha256": V6_OVERLAY_SHA256,
        **copy.deepcopy(frozen["causal_intervention"]),
        **copy.deepcopy(frozen["independent_post_request_closure"]),
        **copy.deepcopy(frozen["namespace_law"]),
    }
    active.pop("completed_response_closure_repair", None)
    return active


def build_catalytic_swarm_1_v6_contract(
    v5_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if v5_contract is None:
        v5_contract = build_catalytic_swarm_1_v5_contract()
    if sha256_object(v5_contract) != EXPECTED_V5_CONTRACT_SHA256:
        raise CatalyticSwarm1V6ProtocolError("CS1-v5 base contract hash changed")
    return apply_v6_overlay_unchecked(v5_contract)


def effective_v6_contract_sha256() -> str:
    return sha256_object(build_catalytic_swarm_1_v6_contract())
