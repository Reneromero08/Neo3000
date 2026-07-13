#!/usr/bin/env python3
"""Canonical tracked binding for the consumed partial CS1-v4 execution."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


EXPECTED_V4_PARTIAL_EXECUTION_BOUNDARY_SHA256 = (
    "5305192d4509028dbf4cf71d42af04d9703e3320d47cf1000cd60358f8a5044a"
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


def build_catalytic_swarm_1_v4_partial_execution_boundary() -> dict[str, Any]:
    artifacts = [
        ("control", "state/catalytic_swarm_1_v4/control-qualification-v4.json", 18868, "E1AF7889F052F5E2EC05F9C289E99BBBFAF009F974FBFDB85C74619086080FED"),
        ("readiness", "state/catalytic_swarm_1_v4/readiness-v4.json", 14390, "97AF7C671A0933090FCADF16DE6BE2387E87AB51E4FBAF3ED113FE89628CBE6A"),
        ("parser_canary", "state/catalytic_swarm_1_v4/parser-canary-v4.json", 16223, "152612378EBC0DE30B7DB0479D7F51EE6ECB1543DB09FBC1B882027E5F544C7F"),
        ("attempt", "state/catalytic_swarm_1_v4/attempt-v4.json", 1629, "AD9E044EAA3F445DBC6008D8D40DB636BC4E2108E5F0398A3AF9EBDF06DA5924"),
        ("result", "state/catalytic_swarm_1_v4/result-v4.json", 258105, "B109AAE9FDC251FE53675610C6D7C3E0BFDEC8C677F2C1F1B27ADEA012BFF6E2"),
        ("ledger", "state/catalytic_swarm_1_v4/ledger-v4.jsonl", 931098, "26FC4168D7C21AF42E87D1C6E7580813C30EB73A6C8664145E38FC053679532B"),
        ("task_results", "state/catalytic_swarm_1_v4/task-results-v4.json", 784226, "4F78999CB3F30EC52D25A49204FD6557E66B8399DFA9B6C3A5A67AD8C06BB394"),
    ]
    return {
        "id": "catalytic_swarm_1_v4_partial_execution_boundary",
        "schema_version": 1,
        "protected_protocol_commit": "cc3f43579d6abf05e10e6c52484a9e6b3eee8fb8",
        "command": {
            "name": "audit-catalytic-swarm-1-v4",
            "invocation_count": 1,
            "authority_consumed": True,
            "retry_count": 0,
            "no_retry": True,
            "retired": True,
        },
        "timestamps": {
            "shell_start_utc": "2026-07-12T21:50:31.2495785Z",
            "controller_start_utc": "2026-07-12T21:55:16.129172Z",
            "controller_finish_utc": "2026-07-12T23:16:06.649642Z",
            "shell_finish_utc": "2026-07-12T23:16:06.9776785Z",
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
            "claim_contract_sha256": "2ba862a097da4b3c6bb2e2fbececa49296b38a8c9b5b047f6c281b84c3111ece",
            "runtime_evidence_binding_sha256": "d7949912512316d551bf6466895fe7d52b44fe568590782b85e23c4cbd6e53e4",
            "scheduler_contract_sha256": "fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e",
            "consumed_v2_boundary_sha256": "dc64c8dff9dc129a3002629bdf97dd9114fc89f7fa01bd0744af7b8fbd3adb1e",
            "consumed_v3_boundary_sha256": "fb8d4270320f73e9307da5b67325cc30edeaab04e7e1ac4a01068a5a94107e14",
        },
        "outcome": {
            "process_exit_code": 1,
            "classification": "inconclusive",
            "verdict": "inconclusive",
            "error": "CatalyticSwarm-1 common root warm failed: cs1-task-07",
            "failure_stage": "task-7-common-root-warm-after-model-completion-before-ledger-and-post-request-host-memory",
            "suite_advantage": None,
            "task_advantage_adjudicated": False,
        },
        "request_accounting": {
            "full_schedule_requests": 1032,
            "completed_model_requests": 775,
            "common_root_warms_completed_at_model_boundary": 7,
            "common_root_warms_scheduled": 8,
            "comparison_requests": 768,
            "comparison_requests_scheduled": 1024,
            "completed_tasks": 6,
            "scheduled_tasks": 8,
            "completed_arms": 24,
            "scheduled_arms": 32,
            "remaining_requests": 257,
            "incomplete_model_requests_reported": 0,
            "task_7": {
                "warm_attempted": True,
                "model_response_completed": True,
                "comparison_arms_started": 0,
                "ledger_record_775_present": False,
                "post_request_host_memory_record_775_present": False,
            },
            "task_8_started": False,
        },
        "completed_latin_square_prefix": [
            {"task_id": "cs1-task-01", "arms": ["serial-chain", "best-of-n", "sparse-swarm", "verified-swarm"]},
            {"task_id": "cs1-task-02", "arms": ["best-of-n", "sparse-swarm", "verified-swarm", "serial-chain"]},
            {"task_id": "cs1-task-03", "arms": ["sparse-swarm", "verified-swarm", "serial-chain", "best-of-n"]},
            {"task_id": "cs1-task-04", "arms": ["verified-swarm", "serial-chain", "best-of-n", "sparse-swarm"]},
            {"task_id": "cs1-task-05", "arms": ["serial-chain", "best-of-n", "sparse-swarm", "verified-swarm"]},
            {"task_id": "cs1-task-06", "arms": ["best-of-n", "sparse-swarm", "verified-swarm", "serial-chain"]},
        ],
        "parity": {
            "completed_tasks_passed": 6,
            "ratio_limit": 1.10,
            "maximum_completion_ratio": 1.0,
            "maximum_fresh_prompt_ratio": 1.045611827618748,
            "maximum_total_model_token_ratio": 1.0436352693349382,
            "per_completed_arm": {
                "requests": 32,
                "completion_tokens": 288,
                "fresh_prompt_tokens_minimum": 6358,
                "fresh_prompt_tokens_maximum": 6648,
                "completion_token_ceiling": 1024,
                "fresh_prompt_token_ceiling": 8192,
            },
        },
        "partial_task_observations": {
            "scope": "six-completed-tasks-only",
            "verified_swarm_exact_hidden_successes": 0,
            "best_of_n_exact_hidden_successes": 1,
            "best_of_n_success_task": "cs1-task-06",
            "not_extrapolatable_to_tasks": ["cs1-task-07", "cs1-task-08"],
        },
        "resource_evidence": {
            "host_private_growth_bytes": 4160815104,
            "host_private_growth_mib": 3968.0625,
            "host_private_ceiling_mib": 4096,
            "host_private_margin_mib": 127.9375,
            "wddm": {
                "sidecar_pid": 38564,
                "valid_samples": 1846,
                "first_valid_sample_seconds": 2.828,
                "peak_dedicated_bytes": 2364416000,
                "peak_dedicated_mib": 2254.88,
                "ceiling_mib": 6000,
                "unavailable_transitions": 0,
                "telemetry_failures": 0,
                "maximum_valid_sample_gap_seconds": 5.64,
                "freshness_boundaries_passed": 2337,
                "freshness_boundaries_total": 2337,
                "maximum_freshness_age_seconds": 2.922,
            },
            "leases": {
                "physical_slots": 1,
                "completed_path_acquisitions": 775,
                "persisted_records": 774,
                "persisted_lease_ids": [0],
                "maximum_concurrency": 1,
                "active_after_cleanup": 0,
            },
        },
        "reconciliation": {
            "frozen_stage_gate": True,
            "freshness_gate": True,
            "isolation_gate": True,
            "cleanup_gate": True,
            "terminal_wddm_gate": True,
            "protocol_safety_gate": False,
            "completed_model_requests": 775,
            "host_memory_checks": 774,
            "ledger_records": 774,
            "ledger_record_range": [1, 774],
            "ledger_metadata_only": True,
            "raw_sse_persisted": False,
            "reason": "completed-response evidence closure missing for request 775",
        },
        "cleanup_and_custody": {
            "sidecar_pid": 38564,
            "sidecar_stopped": True,
            "retirement_samples_without_pid_instance": 5,
            "runtime_state_removed": True,
            "port_9494_free": True,
            "stable": {"pid": 32684, "port": 9292, "healthy": True, "sole_listener": True},
            "candidate": {"path": "D:\\CCC 2.0\\AI\\Neo3000-candidate", "commit": "14de9c71593e5aea4fcfcadeda47ba5c623fadcf", "clean": True},
            "candidate_port_9393_free": True,
            "protected_repository_unchanged": True,
        },
        "artifacts": [
            {"stage": stage, "path": path, "size_bytes": size, "sha256": digest}
            for stage, path, size, digest in artifacts
        ],
        "v3_preservation": {
            "artifact": {
                "path": "state/catalytic_swarm_1_v3/control-qualification-v3.json",
                "size_bytes": 960,
                "sha256": "FCAD4C71807DCC61409A09720A092DD50D8DD96AB76A8946BF418EEBF74DE8A6",
            },
            "other_artifacts_present": 0,
        },
        "causal_diagnosis": {
            "directly_observed": "the task-7 warm model response completed and completed-request accounting advanced to 775, but the 775th ledger and host-memory records did not commit",
            "statically_proved": "the v4 warm path raises one generic error from a compound acceptance predicate before constructing its bounded summary and metadata",
            "inferred": "one or more members of that compound predicate failed",
            "unavailable": "the exact failed warm predicate and any more specific model, cache, memory, token, grammar, or transport cause",
            "defect": "completed-response-evidence-closure",
            "scientific_interpretation": "controller evidence closure defect; not a task-advantage result",
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


def validate_catalytic_swarm_1_v4_partial_execution_boundary(
    value: Mapping[str, Any],
) -> None:
    expected = build_catalytic_swarm_1_v4_partial_execution_boundary()
    if canonical_json_bytes(dict(value)) != canonical_json_bytes(expected):
        raise ValueError("CS1-v4 partial execution boundary differs from canonical")
    if sha256_object(value) != EXPECTED_V4_PARTIAL_EXECUTION_BOUNDARY_SHA256:
        raise ValueError("CS1-v4 partial execution boundary hash drifted")
