#!/usr/bin/env python3
"""Canonical tracked binding for the consumed partial CS1-v5 execution."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


EXPECTED_V5_PARTIAL_EXECUTION_BOUNDARY_SHA256 = (
    "897148680e426caf58b9581f06224f904cb8ff5cd1a389b83c1ceedfc427f9d9"
)


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


def build_catalytic_swarm_1_v5_partial_execution_boundary() -> dict[str, Any]:
    v5_artifacts = [
        ("control", "state/catalytic_swarm_1_v5/control-qualification-v5.json", 18868, "5A4C7DECF1190E6CD1BEF8205E40420ED16FA28DBC021D504E5F666892A366E2"),
        ("readiness", "state/catalytic_swarm_1_v5/readiness-v5.json", 14342, "05B090E6B97C00934D6628137064E897B68E86876ECB3FB2A89FE72695127621"),
        ("parser_canary", "state/catalytic_swarm_1_v5/parser-canary-v5.json", 9426, "3C7F1CDF0AC50D4E140A048018F50C37690E42BB006F5A1E3EDD6AEFCB27D558"),
        ("attempt", "state/catalytic_swarm_1_v5/attempt-v5.json", 1629, "3C589B32730CDD213163F46053B3AF4E697F44977102493F2F0CC2F282EC7567"),
        ("result", "state/catalytic_swarm_1_v5/result-v5.json", 258394, "23B47854746FDE825DCF2EA1681960EE8BFBB69693DDBD0645C9D9F728ADC97B"),
        ("ledger", "state/catalytic_swarm_1_v5/ledger-v5.jsonl", 1292013, "49213BA77829A3ACE0E445DD9177A3114972BCCBCFD91E130A5FF369667FB9F9"),
        ("task_results", "state/catalytic_swarm_1_v5/task-results-v5.json", 784226, "191FDA69F019BD20607816ED7B31592EA03C0B1D860319E3B330255619B42938"),
    ]
    v4_artifacts = [
        ("control", "state/catalytic_swarm_1_v4/control-qualification-v4.json", 18868, "E1AF7889F052F5E2EC05F9C289E99BBBFAF009F974FBFDB85C74619086080FED"),
        ("readiness", "state/catalytic_swarm_1_v4/readiness-v4.json", 14390, "97AF7C671A0933090FCADF16DE6BE2387E87AB51E4FBAF3ED113FE89628CBE6A"),
        ("parser_canary", "state/catalytic_swarm_1_v4/parser-canary-v4.json", 16223, "152612378EBC0DE30B7DB0479D7F51EE6ECB1543DB09FBC1B882027E5F544C7F"),
        ("attempt", "state/catalytic_swarm_1_v4/attempt-v4.json", 1629, "AD9E044EAA3F445DBC6008D8D40DB636BC4E2108E5F0398A3AF9EBDF06DA5924"),
        ("result", "state/catalytic_swarm_1_v4/result-v4.json", 258105, "B109AAE9FDC251FE53675610C6D7C3E0BFDEC8C677F2C1F1B27ADEA012BFF6E2"),
        ("ledger", "state/catalytic_swarm_1_v4/ledger-v4.jsonl", 931098, "26FC4168D7C21AF42E87D1C6E7580813C30EB73A6C8664145E38FC053679532B"),
        ("task_results", "state/catalytic_swarm_1_v4/task-results-v4.json", 784226, "4F78999CB3F30EC52D25A49204FD6557E66B8399DFA9B6C3A5A67AD8C06BB394"),
    ]
    completed_order = [
        ["serial-chain", "best-of-n", "sparse-swarm", "verified-swarm"],
        ["best-of-n", "sparse-swarm", "verified-swarm", "serial-chain"],
        ["sparse-swarm", "verified-swarm", "serial-chain", "best-of-n"],
        ["verified-swarm", "serial-chain", "best-of-n", "sparse-swarm"],
        ["serial-chain", "best-of-n", "sparse-swarm", "verified-swarm"],
        ["best-of-n", "sparse-swarm", "verified-swarm", "serial-chain"],
    ]
    return {
        "id": "catalytic_swarm_1_v5_partial_execution_boundary",
        "schema_version": 1,
        "protected_execution_commit": "241d99e403926b8ef7814c894808922b7cb8cd8e",
        "command": {
            "name": "audit-catalytic-swarm-1-v5",
            "exact": "python -B scripts/holostate_live.py audit-catalytic-swarm-1-v5 --binary \"D:\\CCC 2.0\\AI\\Neo3000\\build\\stable\\bin\\Release\\llama-server.exe\" --model \"D:\\Reneshizzle\\Apps\\LM Studio\\InternScience\\Agents-A1-Q4_K_M-GGUF\\Agents-A1-Q4_K_M.gguf\" --authorized-main 241d99e403926b8ef7814c894808922b7cb8cd8e",
            "invocation_count": 1,
            "authority_consumed": True,
            "retry_count": 0,
            "no_retry": True,
            "retired": True,
        },
        "timestamps": {
            "shell_start_utc": "2026-07-13T00:15:41.0829727Z",
            "authority_claimed_utc": "2026-07-13T00:15:41.502650Z",
            "controller_start_utc": "2026-07-13T00:18:27.456767Z",
            "controller_finish_utc": "2026-07-13T01:44:24.217572Z",
            "shell_finish_utc": "2026-07-13T01:44:24.5435092Z",
            "controller_duration": "1:25:56.760805",
            "shell_duration": "1:28:43.460537",
        },
        "identities": {
            "model": {
                "path": "D:\\Reneshizzle\\Apps\\LM Studio\\InternScience\\Agents-A1-Q4_K_M-GGUF\\Agents-A1-Q4_K_M.gguf",
                "size_bytes": 21166757632,
                "sha256": "31AEFA25B7E1EDBDE436E643E2B5E3F6E57820A4811D97B131130E48FF0772C2",
            },
            "binary": {
                "path": "D:\\CCC 2.0\\AI\\Neo3000\\build\\stable\\bin\\Release\\llama-server.exe",
                "version": "13 (417e1d6)",
                "sha256": "5D0C5F7CE5CEBE35B564C21521ECD426F809445521D3C55C0581A9543F15541B",
            },
            "v5_claim_contract_sha256": "6238ff09ba290e55ad6c5cc2c93b4cbc239d573644192cf101696416a7083e3c",
            "v5_runtime_evidence_binding_sha256": "2b2bcfaadf80d15d2972a4952f4b66026f2dd6979427f6cc32f197c6692903d9",
            "immutable_scheduler_sha256": "fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e",
            "consumed_v2_boundary_sha256": "dc64c8dff9dc129a3002629bdf97dd9114fc89f7fa01bd0744af7b8fbd3adb1e",
            "consumed_v3_boundary_sha256": "fb8d4270320f73e9307da5b67325cc30edeaab04e7e1ac4a01068a5a94107e14",
            "consumed_v4_boundary_sha256": "5305192d4509028dbf4cf71d42af04d9703e3320d47cf1000cd60358f8a5044a",
        },
        "outcome": {
            "process_exit_code": 1,
            "classification": "inconclusive",
            "verdict": "inconclusive",
            "error": "cs1-task-07:common-root-warm: completed response rejected: post-request-custody-or-host-boundary-failed",
            "stop_request_label": "cs1-task-07:common-root-warm",
            "suite_advantage": None,
            "task_advantage_adjudicated": False,
        },
        "request_accounting": {
            "full_schedule_requests": 1032,
            "completed_model_responses": 775,
            "ledger_records": 775,
            "result_fallback_records": 0,
            "common_root_warms_completed": 7,
            "common_root_warms_scheduled": 8,
            "comparison_requests_completed": 768,
            "comparison_requests_scheduled": 1024,
            "completed_tasks": 6,
            "scheduled_tasks": 8,
            "completed_arms": 24,
            "scheduled_arms": 32,
            "remaining_requests": 257,
            "task_7": {
                "warm_model_response_completed": True,
                "warm_ledger_record": 775,
                "comparison_requests_started": 0,
            },
            "task_8_started": False,
        },
        "completion_reconciliation": {
            "completed_responses": 775,
            "ledger_records": 775,
            "fallback_records": 0,
            "durable_equation_passed": True,
            "ledger_record_range": [1, 775],
            "ledger_records_contiguous": True,
            "accepted_records": 774,
            "rejected_records": 1,
            "duplicate_records": 0,
            "all_runtime_version": "v5",
            "all_artifact_schema_version": 5,
            "all_lease_ids": [0],
            "all_model_boundary_completed": True,
            "claim_identity_mismatches": 0,
            "scheduler_identity_mismatches": 0,
        },
        "post_request_reconciliation": {
            "custody_checks": 1550,
            "expected_custody_checks": 1550,
            "host_memory_checks": 774,
            "expected_host_memory_checks": 775,
            "pre_request_freshness_boundaries": 775,
            "post_request_freshness_boundaries": 775,
            "task_parity_checks": 6,
            "expected_task_parity_checks": 6,
            "terminal_reason": "host_memory_checks-mismatch",
            "passed": False,
            "record_775": {
                "model_boundary_completed": True,
                "result_accepted": True,
                "finish_reason_stop": True,
                "reasoning_absent": True,
                "tool_calls_empty": True,
                "token_evidence_accepted": True,
                "logical_prompt_count_matches": True,
                "resource_gate_passed": False,
                "wddm_passed": True,
                "custody_passed": False,
                "host_memory_passed": False,
                "response_disposition": "rejected",
                "response_reason_code": "post-request-custody-or-host-boundary-failed",
                "completion_persistence": "ledger",
                "lease_id": 0,
            },
        },
        "completed_latin_square_prefix": [
            {"task_id": f"cs1-task-{index:02d}", "arms": arms}
            for index, arms in enumerate(completed_order, start=1)
        ],
        "parity": {
            "completed_tasks_passed": 6,
            "ratio_limit": 1.10,
            "maximum_completion_ratio": 1.0,
            "maximum_fresh_prompt_ratio": 1.045611827618748,
            "maximum_total_model_token_ratio": 1.0436352693349382,
        },
        "partial_hidden_observations": {
            "scope": "six-completed-tasks-only",
            "per_task_final_hidden_passed": {
                "cs1-task-01": {"serial-chain": 0, "best-of-n": 0, "sparse-swarm": 0, "verified-swarm": 0},
                "cs1-task-02": {"serial-chain": 7, "best-of-n": 7, "sparse-swarm": 7, "verified-swarm": 7},
                "cs1-task-03": {"serial-chain": 0, "best-of-n": 0, "sparse-swarm": 0, "verified-swarm": 0},
                "cs1-task-04": {"serial-chain": 3, "best-of-n": 3, "sparse-swarm": 3, "verified-swarm": 3},
                "cs1-task-05": {"serial-chain": 0, "best-of-n": 0, "sparse-swarm": 0, "verified-swarm": 0},
                "cs1-task-06": {"serial-chain": 10, "best-of-n": 16, "sparse-swarm": 10, "verified-swarm": 10},
            },
            "verified_swarm_exact_hidden_successes": 0,
            "best_of_n_exact_hidden_successes": 1,
            "best_of_n_success_task": "cs1-task-06",
            "not_extrapolatable_to_tasks": ["cs1-task-07", "cs1-task-08"],
        },
        "resource_evidence": {
            "host_private_growth_bytes": 4160516096,
            "host_private_growth_mib": 3967.77734375,
            "host_private_ceiling_mib": 4096,
            "host_private_margin_bytes": 134451200,
            "host_private_margin_mib": 128.22265625,
            "observed_values_below_ceiling": True,
            "missing_775th_host_accounting_record": True,
            "wddm": {
                "sidecar_pid": 53184,
                "valid_samples": 1907,
                "first_valid_sample_seconds": 2.187000000005355,
                "peak_dedicated_bytes": 2364416000,
                "peak_dedicated_mib": 2254.88,
                "ceiling_mib": 6000,
                "maximum_valid_sample_gap_seconds": 3.422000000020489,
                "maximum_freshness_age_seconds": 3.312000000005355,
                "freshness_boundaries_passed": 2337,
                "freshness_boundaries_total": 2337,
                "unavailable_events": 0,
                "telemetry_failures": 0,
                "recovery_events": 0,
            },
            "leases": {
                "physical_slots": 1,
                "acquisitions": 775,
                "persisted_lease_ids": [0],
                "maximum_concurrency": 1,
                "active_after_cleanup": 0,
            },
        },
        "gates": {
            "control_qualification": True,
            "readiness": True,
            "parser_canary": True,
            "frozen_stage": True,
            "freshness": True,
            "isolation": True,
            "cleanup": True,
            "terminal_wddm": True,
            "metadata_ledger": True,
            "request_law": False,
            "live_boundaries": False,
            "protocol_safety": False,
        },
        "cleanup_and_custody": {
            "sidecar_pid": 53184,
            "sidecar_stopped": True,
            "runtime_state_removed": True,
            "port_9494_free": True,
            "retirement_samples_without_pid_instance": 5,
            "sampler_stopped_cleanly": True,
            "stable": {"pid": 32684, "port": 9292, "healthy": True, "sole_listener": True},
            "candidate": {"path": "D:\\CCC 2.0\\AI\\Neo3000-candidate", "commit": "14de9c71593e5aea4fcfcadeda47ba5c623fadcf", "clean": True},
            "candidate_port_9393_free": True,
            "protected_repository_unchanged": True,
        },
        "artifacts": [
            {"stage": stage, "path": path, "size_bytes": size, "sha256": digest}
            for stage, path, size, digest in v5_artifacts
        ],
        "predecessor_preservation": {
            "v3": {
                "artifact": {"path": "state/catalytic_swarm_1_v3/control-qualification-v3.json", "size_bytes": 960, "sha256": "FCAD4C71807DCC61409A09720A092DD50D8DD96AB76A8946BF418EEBF74DE8A6"},
                "other_artifacts_present": 0,
            },
            "v4_artifacts": [
                {"stage": stage, "path": path, "size_bytes": size, "sha256": digest}
                for stage, path, size, digest in v4_artifacts
            ],
        },
        "ledger_safety": {
            "metadata_only": True,
            "raw_sse_persisted": False,
            "reasoning_fields_present": False,
            "hidden_data_fields_present": False,
            "answer_key_fields_present": False,
        },
        "causal_diagnosis": {
            "directly_observed": "record 775 durably represents a structurally accepted task-7 warm rejected by one combined post-request custody/host boundary; host accounting reconciles only 774 of 775 completed responses",
            "statically_proved": "v5 invokes one compound after callback; any exception marks both custody and host false, and host_memory_checks increments only after the complete host observation succeeds",
            "inferred": "one operation inside the compound custody/host path failed or raised before successful host-accounting completion",
            "unavailable": "which substantive custody or host-memory invariant, query, or observation failed; no narrower live cause is established",
            "defect": "compound-post-request-sub-boundary-accounting-and-diagnosability",
            "host_ceiling_breach_proved": False,
            "repository_mutation_proved": False,
            "candidate_mutation_proved": False,
            "stable_mutation_proved": False,
        },
        "live_authority_constraints": {
            "deep_requests": 0,
            "automatic_promotion": False,
            "code_repair_during_live_authority": False,
            "contract_repair_during_live_authority": False,
        },
        "claims": {
            "NEO3000_BASELINE_OPERATIONAL": "UNLOCKED",
            "PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE": "UNLOCKED",
            "STRUCTURED_HOLOSTATE_MICROWORKER_AVAILABLE": "UNLOCKED",
            "CATALYTIC_SWARM_CONTROL_AVAILABLE": "UNLOCKED",
            "CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN": "LOCKED",
            "PROCESS_LOCAL_HOLOSTATE_AVAILABLE": "LOCKED",
            "RESTART_PERSISTENT_HOLOSTATE_AVAILABLE": "LOCKED",
            "SOTA_SWARM_CLAIM": "LOCKED",
            "automatic_promotion": False,
        },
    }


def validate_catalytic_swarm_1_v5_partial_execution_boundary(
    value: Mapping[str, Any],
) -> None:
    expected = build_catalytic_swarm_1_v5_partial_execution_boundary()
    if canonical_json_bytes(dict(value)) != canonical_json_bytes(expected):
        raise ValueError("CS1-v5 partial execution boundary differs from canonical")
    if sha256_object(value) != EXPECTED_V5_PARTIAL_EXECUTION_BOUNDARY_SHA256:
        raise ValueError("CS1-v5 partial execution boundary hash drifted")
