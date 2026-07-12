#!/usr/bin/env python3
"""Frozen connector substrate for CatalyticSwarm-1 v2.

The successor preserves the exact eight-task/four-arm comparison and changes
only cache admission: actual cached tokens must cover the exact public-root
terminal token index. The disproven legacy common-prefix threshold remains
recorded as provenance and is not an admission authority.

The canonical contract hash was recomputed from the final object after the
initial stale pre-finalization constant was rejected by the protected agent.
This module performs no live execution.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

DIAGNOSTIC_EVIDENCE_SHA256 = "a32b0b08e67e3e219a709c9493bddb31aa195392a92714f8f0be99ed48555031"
EXPECTED_CONTRACT_SHA256 = "911242c74509f1d2d8c6a3c8aa82948c452dac5f4646dd97d70d7b27b750e984"

_DIAGNOSTIC_EVIDENCE_JSON = r'''{"artifacts": {"attempt": "CDF1F383C567D26584D86053099B28D2A14E389E1BFCA7F5E33DE5B82A342FD2", "control": "7E32C00378A9F5118982F465A40257B518C54C9A2A34410D5E1931C17DB255D2", "ledger": "D1EF5502EBDC627BD23A0667B726C4F313B8C78BD5A8DC145D9F36ED6E5C0D7F", "readiness": "B4C8A1F126F3636016542331ED1A615E2100595249D554450048A5D730BEF4C7", "result": "9926CACF5E9F28FBD2A01DFA1BCBD4895F9E727A40301E9906A4B374854FB6A3"}, "authorization": {"authority_consumed": true, "invocation_count": 1, "process_exit_code": 0, "retry_count": 0}, "causal_finding": {"actual_cache_margin_over_root_tokens": 2, "actual_cache_shortfall_to_legacy_threshold_tokens": 3, "complete_public_root_reuse_proven": true, "legacy_threshold_overreach_tokens": 5, "successor_law": "admit when actual_cached_prompt_tokens >= public_root_terminal_token_index after exact prompt-prefix identity and transport/token evidence pass"}, "claims": {"CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN": "LOCKED", "PROCESS_LOCAL_HOLOSTATE_AVAILABLE": "LOCKED", "RESTART_PERSISTENT_HOLOSTATE_AVAILABLE": "LOCKED", "SOTA_SWARM_CLAIM": "LOCKED", "automatic_promotion": false, "deep_requests": 0}, "contract_sha256": "be66da770d4396e6f825f51bc0bca2abee5c03f6c03d9ef74e932c09ca330f7b", "id": "catalytic_swarm_1_cache_diagnostic_evidence", "probes": {"minimal-branch": {"actual_cached_prompt_tokens": 4822, "branch_prompt_tokens": 4848, "classification": "proof-threshold-overextended", "completion_tokens": 9, "fresh_prompt_tokens": 26, "legacy_required_cached_prompt_tokens": 4825, "public_root_terminal_token_index": 4820}, "realistic-first-turn": {"actual_cached_prompt_tokens": 4822, "branch_prompt_tokens": 5020, "classification": "proof-threshold-overextended", "completion_tokens": 9, "fresh_prompt_tokens": 198, "legacy_required_cached_prompt_tokens": 4825, "public_root_terminal_token_index": 4820}}, "protocol_commit": "95f869136efbe8921c15933a792b911ad40997d6", "result": {"cache_admission": "root-reuse-proven-proof-law-repair-required", "cache_diagnostic": "reviewable-accept", "final_safety_passed": true, "model_request_count": 3}, "runtime": {"cleanup_passed": true, "custody_checks": 6, "host_memory_checks": 3, "isolation_passed": true, "ledger_records": 3, "maximum_concurrent_leases": 1, "maximum_host_private_growth_bytes": 385134592, "physical_slots": 1, "post_request_freshness_boundaries": 3, "pre_request_freshness_boundaries": 3, "wddm_failures": 0, "wddm_peak_mib": 2252.88}, "schema_version": 1}'''

_CONTRACT_JSON = r'''{"advantage_gate": {"all_8_tasks_and_4_arms_complete": true, "all_budget_parity_required": true, "paired_hidden_score_wins_must_exceed_losses": true, "verified_exact_hidden_success_minimum": 6, "verified_success_margin_over_each_baseline": 2}, "cache_admission_law": {"actual_cache_must_cover_root_terminal": true, "legacy_common_prefix_threshold_is_not_admission_authority": true, "negative_admission_persisted_before_stop": true, "record_fields": ["public_root_terminal_token_index", "common_prefix_tokens", "legacy_required_cached_prompt_tokens", "actual_cached_prompt_tokens", "fresh_prompt_tokens", "completion_tokens", "transport_passed", "token_evidence_passed"], "root_terminal_authority": "smallest exact rendered token prefix whose detokenized text reaches the final character of the complete system/reference/public-root message", "warm_branch_terminal_indices_must_agree": true, "warm_branch_token_prefix_must_cover_root_terminal": true}, "causal_intervention": {"diagnostic_measurements": {"actual_cache_margin_over_root_tokens": 2, "actual_cache_shortfall_to_legacy_threshold_tokens": 3, "actual_cached_prompt_tokens": 4822, "legacy_required_cached_prompt_tokens": 4825, "legacy_threshold_overreach_tokens": 5, "public_root_terminal_token_index": 4820}, "legacy_gate": "actual_cached_prompt_tokens >= legacy_required_cached_prompt_tokens", "legacy_threshold_retained_as_provenance_only": true, "only_change": "replace the legacy full warm/branch common-prefix cache threshold with the exact public-root terminal token threshold", "persist_completed_response_before_gate": true, "successor_gate": "actual_cached_prompt_tokens >= public_root_terminal_token_index"}, "claim_limits": {"CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN": "unlock only on exact advantage gate", "PROCESS_LOCAL_HOLOSTATE_AVAILABLE": "LOCKED", "RESTART_PERSISTENT_HOLOSTATE_AVAILABLE": "LOCKED", "SOTA_SWARM_CLAIM": "LOCKED", "automatic_promotion": false}, "execution_safety": {"cleanup_owned_across_complete_live_lifetime": true, "hidden_data_persisted": false, "host_growth_ceiling_mib": 4096, "host_private_check_after_every_completed_request": true, "metadata_only_ledger": true, "raw_sse_persisted": false, "stable_candidate_custody_before_and_after_every_request": true, "task_budget_parity_before_next_task": true, "wddm_ceiling_mib": 6000, "wddm_freshness_before_and_after_every_request": true}, "frozen_geometry": {"actual_budget_ratio_max": 1.1, "arm_order": "unchanged four-position Latin square repeated over eight tasks", "arm_plan_hashes": {"best-of-n": "E989ECB8A53E9AD24885759627D3E3BA9A16E76A41A770E70784644A9A96696A", "serial-chain": "99FE4402A487EEAF07FAEE7A64CAB241A888E1CB916D09C62BDA493AB08EEF53", "sparse-swarm": "9289DE195D12AB93A9A9DD70949C92FC55D40E0D930CAD521605FC1707E116DE", "verified-swarm": "46A2CEADA66217AC2DD3E0BD6D1C20A052EFE9D76EE236887AF18428409A772C"}, "candidate_count_per_task": 64, "common_root_warm_requests": 8, "comparison_requests": 1024, "deep_requests": 0, "maximum_completion_tokens_per_arm_per_task": 1024, "maximum_fresh_prompt_tokens_per_arm_per_task": 8192, "maximum_tokens_per_request": 32, "one_physical_slot": true, "requests_per_arm_per_task": 32, "task_count": 8, "task_suite_sha256": "4B9961D5054BE5D98EF315D2DEAE9D1604E0042A69CB02A8B81FDF513BC1FC92", "temperature": 0, "thinking_disabled": true, "total_model_requests": 1032}, "id": "catalytic_swarm_1_v2", "objective": "Run the unchanged equal-budget CatalyticSwarm task-advantage comparison with cache admission corrected to the exact public-root terminal token law proven by the separately authorized diagnostic.", "one_shot": {"no_retry": true, "partial_evidence_preserved": true, "paths": {"attempt": "state/catalytic_swarm_1_v2/attempt-v2.json", "control": "state/catalytic_swarm_1_v2/control-qualification-v2.json", "ledger": "state/catalytic_swarm_1_v2/ledger-v2.jsonl", "parser_canary": "state/catalytic_swarm_1_v2/parser-canary-v2.json", "readiness": "state/catalytic_swarm_1_v2/readiness-v2.json", "result": "state/catalytic_swarm_1_v2/result-v2.json", "task_results": "state/catalytic_swarm_1_v2/task-results-v2.json"}}, "predecessors": {"cache_diagnostic": {"authority_consumed": true, "cache_admission": "root-reuse-proven-proof-law-repair-required", "contract_sha256": "be66da770d4396e6f825f51bc0bca2abee5c03f6c03d9ef74e932c09ca330f7b", "evidence_object_sha256": "a32b0b08e67e3e219a709c9493bddb31aa195392a92714f8f0be99ed48555031", "integration_commit": "95f869136efbe8921c15933a792b911ad40997d6", "no_retry": true, "verdict": "reviewable-accept"}, "catalytic_swarm_1_v1": {"authority_consumed": true, "contract_sha256": "fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e", "evidence_commit": "ca99f5560b9bf7a5a745c1156c43a64c3733fca9", "evidence_object_sha256": "e308b5953b90d5a28b902b728292440443a9299e58db8049f756557d5693a3d5", "no_retry": true, "protocol_commit": "556bb4d57a05bb81fa101a98092472170b50c0dd", "verdict": "inconclusive"}}, "schema_version": 2, "attempt_version": 2, "verdicts": ["reviewable-accept", "no-advantage", "instrumentation-reject", "inconclusive"]}'''


class CatalyticSwarm1V2ProtocolError(RuntimeError):
    """The successor contract or diagnostic evidence differs from canonical."""


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


def build_cache_diagnostic_evidence_binding() -> dict[str, Any]:
    return json.loads(_DIAGNOSTIC_EVIDENCE_JSON)


def build_catalytic_swarm_1_v2_contract() -> dict[str, Any]:
    return json.loads(_CONTRACT_JSON)


def validate_cache_diagnostic_evidence_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CatalyticSwarm1V2ProtocolError("diagnostic evidence must be an object")
    expected = build_cache_diagnostic_evidence_binding()
    if canonical_json_bytes(value) != canonical_json_bytes(expected):
        raise CatalyticSwarm1V2ProtocolError(
            "diagnostic evidence binding differs from canonical"
        )
    if sha256_object(value) != DIAGNOSTIC_EVIDENCE_SHA256:
        raise CatalyticSwarm1V2ProtocolError(
            "diagnostic evidence binding hash drifted"
        )
    return expected


def validate_catalytic_swarm_1_v2_contract(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CatalyticSwarm1V2ProtocolError("CS1-v2 contract must be an object")
    expected = build_catalytic_swarm_1_v2_contract()
    if canonical_json_bytes(value) != canonical_json_bytes(expected):
        raise CatalyticSwarm1V2ProtocolError(
            "CS1-v2 contract differs from canonical"
        )
    if sha256_object(value) != EXPECTED_CONTRACT_SHA256:
        raise CatalyticSwarm1V2ProtocolError("CS1-v2 contract hash drifted")
    law = value["causal_intervention"]
    if law["successor_gate"] != (
        "actual_cached_prompt_tokens >= public_root_terminal_token_index"
    ):
        raise CatalyticSwarm1V2ProtocolError("exact root-terminal law changed")
    if law["legacy_threshold_retained_as_provenance_only"] is not True:
        raise CatalyticSwarm1V2ProtocolError("legacy threshold regained authority")
    if value["frozen_geometry"]["task_suite_sha256"] != "4B9961D5054BE5D98EF315D2DEAE9D1604E0042A69CB02A8B81FDF513BC1FC92":
        raise CatalyticSwarm1V2ProtocolError("task suite changed")
    if value["frozen_geometry"]["arm_plan_hashes"] != {
        "serial-chain": "99FE4402A487EEAF07FAEE7A64CAB241A888E1CB916D09C62BDA493AB08EEF53",
        "best-of-n": "E989ECB8A53E9AD24885759627D3E3BA9A16E76A41A770E70784644A9A96696A",
        "sparse-swarm": "9289DE195D12AB93A9A9DD70949C92FC55D40E0D930CAD521605FC1707E116DE",
        "verified-swarm": "46A2CEADA66217AC2DD3E0BD6D1C20A052EFE9D76EE236887AF18428409A772C",
    }:
        raise CatalyticSwarm1V2ProtocolError("arm plans changed")
    if value["frozen_geometry"]["total_model_requests"] != 1032:
        raise CatalyticSwarm1V2ProtocolError("request geometry changed")
    if value["claim_limits"]["automatic_promotion"] is not False:
        raise CatalyticSwarm1V2ProtocolError("automatic promotion enabled")
    return expected
