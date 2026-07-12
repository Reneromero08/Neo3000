#!/usr/bin/env python3
"""Frozen static contract for the CS1 cache-admission diagnostic."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from catalytic_swarm_1_cache_diagnostic import DIAGNOSTIC_ID, MAX_MODEL_REQUESTS, PROBE_LABELS

SCHEMA_VERSION = 1
PREDECESSOR_MAIN = "ca99f5560b9bf7a5a745c1156c43a64c3733fca9"
PREDECESSOR_PROTOCOL_COMMIT = "556bb4d57a05bb81fa101a98092472170b50c0dd"
PREDECESSOR_CONTRACT_SHA256 = "fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e"
PREDECESSOR_EVIDENCE_SHA256 = "e308b5953b90d5a28b902b728292440443a9299e58db8049f756557d5693a3d5"
TASK_SUITE_SHA256 = "4B9961D5054BE5D98EF315D2DEAE9D1604E0042A69CB02A8B81FDF513BC1FC92"
TASK_ID = "cs1-task-01"
CHECKPOINT_MIN_STEP = 512

PREDECESSOR_ARTIFACTS = {
    "control": "F9C8032340655EBBE5E41867D8C4C426940E6B7D2236ACDA9019EE9E24F8733D",
    "readiness": "F6DF670C7CE1659E78D4B51F5CD45FAF4087DD46ABE87D8AD529AB45F6FE9C95",
    "parser_canary": "0B2749F3F864CB93FB003EA68A41AD364C56360C270506DB3684C1738E221680",
    "attempt": "593D013494064F10FF9ECF732942EE114E1DC91E14A3290210C8801684A48A40",
    "result": "D37CBF79BC867D927C01C7977D4432A29B2CA40E59ED5C10CCF6EF9A5F3AACAB",
    "ledger": "5E016B7554E57564833BAA3B5B1250C6EE6FB73CFE204BDCBC4EEB902C1E40B8",
}

ONE_SHOT_PATHS = {
    "control": "state/catalytic_swarm_1_cache_diagnostic/control-qualification-v1.json",
    "readiness": "state/catalytic_swarm_1_cache_diagnostic/readiness-v1.json",
    "attempt": "state/catalytic_swarm_1_cache_diagnostic/attempt-v1.json",
    "result": "state/catalytic_swarm_1_cache_diagnostic/result-v1.json",
    "ledger": "state/catalytic_swarm_1_cache_diagnostic/ledger-v1.jsonl",
}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def build_cache_diagnostic_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "id": DIAGNOSTIC_ID,
        "purpose": "classify the failed CS1 complete-public-root cache admission before any task-advantage successor",
        "predecessor": {
            "evidence_commit": PREDECESSOR_MAIN,
            "protocol_commit": PREDECESSOR_PROTOCOL_COMMIT,
            "contract_sha256": PREDECESSOR_CONTRACT_SHA256,
            "evidence_object_sha256": PREDECESSOR_EVIDENCE_SHA256,
            "artifacts": dict(PREDECESSOR_ARTIFACTS),
            "task_results_absent": True,
            "authority_consumed": True,
            "no_retry": True,
        },
        "task": {
            "suite_sha256": TASK_SUITE_SHA256,
            "task_id": TASK_ID,
            "public_root_only": True,
            "hidden_data_visible": False,
        },
        "sequence": [
            {"ordinal": 1, "label": "common-root-warm", "kind": "warm"},
            {"ordinal": 2, "label": PROBE_LABELS[0], "kind": "minimal-branch"},
            {"ordinal": 3, "label": PROBE_LABELS[1], "kind": "realistic-first-turn"},
        ],
        "request_law": {
            "maximum_model_requests": MAX_MODEL_REQUESTS,
            "thinking_disabled": True,
            "temperature": 0,
            "one_physical_slot": True,
            "deep_requests": 0,
            "automatic_promotion": False,
        },
        "measurement_law": {
            "persist_before_gate": [
                "warm_prompt_tokens",
                "branch_prompt_tokens",
                "public_root_terminal_token_index",
                "common_prefix_tokens",
                "required_cached_prompt_tokens",
                "actual_cached_prompt_tokens",
                "fresh_prompt_tokens",
                "completion_tokens",
                "cache_checkpoint_min_step",
                "response_completed",
                "transport_passed",
                "token_evidence_passed",
            ],
            "checkpoint_min_step": CHECKPOINT_MIN_STEP,
            "raw_sse_persisted": False,
            "reasoning_text_persisted": False,
            "hidden_data_persisted": False,
        },
        "classification_law": [
            "exact-root-reuse-proven",
            "proof-threshold-overextended",
            "checkpoint-shortfall",
            "cache-session-reuse-failed",
            "prompt-prefix-diverged-before-root-end",
            "unstable-or-geometry-dependent-reuse",
            "transport-or-token-evidence-failed",
        ],
        "terminal_reconciliation": {
            "use_cs1_request_boundary_namespace": True,
            "accept_exact_observed_request_count_on_early_stop": True,
            "full_schedule_counts_not_required_for_diagnostic": True,
        },
        "one_shot": {
            "paths": dict(ONE_SHOT_PATHS),
            "no_retry": True,
        },
        "claims": {
            "cache_diagnostic_only": True,
            "task_advantage": "LOCKED",
            "sota": "LOCKED",
            "process_local_holostate": "LOCKED",
            "restart_persistence": "LOCKED",
            "automatic_promotion": False,
        },
    }


def contract_sha256(contract: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(dict(contract))).hexdigest()


def validate_cache_diagnostic_contract(contract: Mapping[str, Any]) -> None:
    if not isinstance(contract, Mapping):
        raise ValueError("cache diagnostic contract must be an object")
    expected = build_cache_diagnostic_contract()
    if canonical_json_bytes(dict(contract)) != canonical_json_bytes(expected):
        raise ValueError("cache diagnostic contract differs from canonical")
