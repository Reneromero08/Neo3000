#!/usr/bin/env python3
"""Complete static contract for CatalyticSwarm-1 task advantage.

This module freezes the experiment identity, predecessor evidence, task suite,
arm plans, counterbalanced execution order, budgets, isolation law, one-shot
artifact paths, and verdict thresholds. It performs no live execution.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from catalytic_advantage_tasks import (
    CANDIDATE_COUNT,
    EXPECTED_SUITE_SHA256,
    HIDDEN_EXAMPLE_COUNT,
    PUBLIC_EXAMPLE_COUNT,
    SUITE_ID,
    TASK_COUNT,
    build_frozen_task_suite,
)
from catalytic_swarm_advantage import (
    ARMS,
    BUDGET_RATIO_LIMIT,
    MAX_COMPLETION_TOKENS_PER_ARM,
    MAX_FRESH_PROMPT_TOKENS_PER_ARM,
    MAX_TOKENS_PER_REQUEST,
    REQUESTS_PER_ARM,
    build_all_arm_plans,
)

CONTRACT_ID = "catalytic_swarm_1"
SCHEMA_VERSION = 1
ATTEMPT_VERSION = 1
PREDECESSOR_MAIN = "7cad4a9d8181c160da712c3474d66a4fbf8a1ba3"
PREDECESSOR_INTEGRATION = "cf61f90ff5544f2f8bc546e5d661ea72cdda8666"
PREDECESSOR_CONTRACT_SHA256 = "eadea6e1c6d66e50d85803c4cc96ad6a703b4964799251977ff1288eabc24cf1"
PREDECESSOR_EVIDENCE_SHA256 = "02a62f72245d6651a9a5ac39f0f56dc3ec717b9e43577481936706102eec794b"
PREDECESSOR_ARTIFACTS = {
    "control": "1FC67796F436E69B1B2C2F132345C0335FADF6D1452E7F98D8A92D78CB616CE3",
    "readiness": "129FD883FD03BBEF8B216AC67F77CBE854CA798A86BBC18A11D4DCDF010E7124",
    "parser_canary": "9282D7F8AE195C866E767A7F0D3BCB0A366E3FC3C1509A7DB1F99F1C541191B5",
    "attempt": "0E9A839B7AD9D50AE6FD82DD3C63A93D23596C4A32FAF515BAC67A68EFEE8866",
    "result": "AF491153D98877CAACAF5ED89F3446A80AD8ED12D3FAD2CDE22C2AF77CE5BEC7",
    "ledger": "C523EF77C80CDD4783D2E41103FCD72490A4C837DA2B3988B29F8D7A97E1F7F9",
    "blackboard": "197929DF8DF62A24480A64C071651CED43E16D82F0B6DA5A9AB740C6C1236964",
}
ARM_PLAN_HASHES = {
    "serial-chain": "99FE4402A487EEAF07FAEE7A64CAB241A888E1CB916D09C62BDA493AB08EEF53",
    "best-of-n": "E989ECB8A53E9AD24885759627D3E3BA9A16E76A41A770E70784644A9A96696A",
    "sparse-swarm": "9289DE195D12AB93A9A9DD70949C92FC55D40E0D930CAD521605FC1707E116DE",
    "verified-swarm": "46A2CEADA66217AC2DD3E0BD6D1C20A052EFE9D76EE236887AF18428409A772C",
}
ONE_SHOT_PATHS = {
    "control": "state/catalytic_swarm_1/control-qualification-v1.json",
    "readiness": "state/catalytic_swarm_1/readiness-v1.json",
    "parser_canary": "state/catalytic_swarm_1/parser-canary-v1.json",
    "attempt": "state/catalytic_swarm_1/attempt-v1.json",
    "result": "state/catalytic_swarm_1/result-v1.json",
    "ledger": "state/catalytic_swarm_1/ledger-v1.jsonl",
    "task_results": "state/catalytic_swarm_1/task-results-v1.json",
}


class AdvantageProtocolError(RuntimeError):
    """The CatalyticSwarm-1 contract differs from the frozen protocol."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def contract_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest().lower()


def counterbalanced_arm_order() -> dict[str, list[str]]:
    """Four-position Latin-square order repeated over eight fixed tasks."""
    arms = list(ARMS)
    return {
        f"cs1-task-{task_index + 1:02d}": [
            arms[(position + task_index) % len(arms)]
            for position in range(len(arms))
        ]
        for task_index in range(TASK_COUNT)
    }


def build_catalytic_swarm_1_contract() -> dict[str, Any]:
    suite = build_frozen_task_suite()
    plans = build_all_arm_plans()
    return {
        "id": CONTRACT_ID,
        "schema_version": SCHEMA_VERSION,
        "attempt_version": ATTEMPT_VERSION,
        "objective": (
            "Measure whether verified sparse CatalyticSwarm communication improves "
            "hidden executable-task success over serial, best-of-N, and unverified "
            "sparse controls under equal total request and token budgets."
        ),
        "predecessor": {
            "main_commit": PREDECESSOR_MAIN,
            "integration_commit": PREDECESSOR_INTEGRATION,
            "contract_sha256": PREDECESSOR_CONTRACT_SHA256,
            "evidence_sha256": PREDECESSOR_EVIDENCE_SHA256,
            "artifacts": dict(PREDECESSOR_ARTIFACTS),
            "required_availability": {
                "PROCESS_LOCAL_HOLOSTATE_MICROWORKER_AVAILABLE": "UNLOCKED",
                "STRUCTURED_HOLOSTATE_MICROWORKER_AVAILABLE": "UNLOCKED",
                "CATALYTIC_SWARM_CONTROL_AVAILABLE": "UNLOCKED",
            },
        },
        "task_suite": {
            "module": "scripts/catalytic_advantage_tasks.py",
            "suite_id": SUITE_ID,
            "suite_sha256": suite.suite_sha256,
            "expected_suite_sha256": EXPECTED_SUITE_SHA256,
            "task_count": TASK_COUNT,
            "candidate_count_per_task": CANDIDATE_COUNT,
            "program_length": 5,
            "public_examples_per_task": PUBLIC_EXAMPLE_COUNT,
            "hidden_examples_per_task": HIDDEN_EXAMPLE_COUNT,
            "hidden_examples_visible_to_model": False,
            "answer_key_visible_to_model": False,
            "hidden_scoring_timing": "after all four arms for a task complete",
            "hidden_scores_reused_as_context": False,
            "public_projection_identity_required_across_arms": True,
        },
        "arms": {
            plan.arm: {
                "plan_sha256": plan.plan_sha256,
                "request_count": plan.request_count,
                "physical_slots": plan.physical_slots,
                "max_tokens_per_request": plan.max_tokens_per_request,
                "max_completion_tokens": plan.max_completion_tokens,
                "max_fresh_prompt_tokens": plan.max_fresh_prompt_tokens,
                "role_seed_sequence": [
                    {"ordinal": turn.ordinal, "role": turn.role, "seed": turn.seed}
                    for turn in plan.turns
                ],
                "parent_graph": {
                    turn.turn_id: list(turn.parent_turn_ids)
                    for turn in plan.turns
                },
                "verifier_feedback_visible": plan.arm == "verified-swarm",
                "hidden_feedback_visible": False,
                "automatic_promotion": False,
            }
            for plan in plans
        },
        "arm_semantics": {
            "serial-chain": "one 32-turn sequential trajectory; final turn selected",
            "best-of-n": (
                "32 independent candidates; highest public-example score selected, "
                "earliest turn breaks ties"
            ),
            "sparse-swarm": (
                "16/8/6/2 parent graph; parent candidate IDs visible, verifier scores hidden"
            ),
            "verified-swarm": (
                "same 16/8/6/2 graph; bounded public-example verifier scores visible"
            ),
        },
        "execution_order": counterbalanced_arm_order(),
        "counterbalancing": {
            "method": "four-position Latin square repeated across eight tasks",
            "purpose": "bound arm-order, cache-warmth, and runtime-drift effects",
        },
        "shared_transport": {
            "one_sidecar": True,
            "one_physical_lease": True,
            "thinking_disabled": True,
            "deep_requests": 0,
            "temperature": 0,
            "strict_response_schema": {"candidate_id": "C00"},
            "empty_reasoning_required": True,
            "tool_calls_forbidden": True,
            "finish_reason": "stop",
            "accepted_v4_token_evidence_required": True,
            "wddm_policy": "inherit catalytic_swarm_0_v2 exact-PID resilience and freshness",
            "fresh_wddm_boundary_required_before_and_after_each_request": True,
        },
        "budget_law": {
            "requests_per_arm_per_task": REQUESTS_PER_ARM,
            "maximum_tokens_per_request": MAX_TOKENS_PER_REQUEST,
            "maximum_completion_tokens_per_arm_per_task": MAX_COMPLETION_TOKENS_PER_ARM,
            "maximum_fresh_prompt_tokens_per_arm_per_task": MAX_FRESH_PROMPT_TOKENS_PER_ARM,
            "actual_fresh_prompt_ratio_max": BUDGET_RATIO_LIMIT,
            "actual_completion_ratio_max": BUDGET_RATIO_LIMIT,
            "actual_total_model_token_ratio_max": BUDGET_RATIO_LIMIT,
            "parity_failure_verdict": "inconclusive",
        },
        "isolation_law": {
            "arm_outputs_visible_only_within_same_arm": True,
            "task_outputs_visible_only_within_same_task": True,
            "hidden_examples_forbidden_in_requests_and_ledger": True,
            "hidden_scores_forbidden_in_later_model_context": True,
            "fresh_arm_state_required": True,
            "common_public_root_reuse_permitted": True,
            "arm_namespace_required": True,
        },
        "advantage_gate": {
            "task_count": 8,
            "verified_exact_hidden_success_minimum": 6,
            "verified_success_margin_over_each_baseline": 2,
            "paired_hidden_score_wins_must_exceed_losses": True,
            "all_budget_parity_required": True,
            "reviewable_accept_unlock": "CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN",
            "no_advantage_keeps_locked": True,
        },
        "one_shot": {
            "paths": dict(ONE_SHOT_PATHS),
            "control_and_readiness_before_attempt": True,
            "parser_canary_before_attempt": True,
            "task_root_qualification_before_attempt": True,
            "no_retry": True,
            "partial_evidence_preserved": True,
        },
        "verdicts": {
            "catalytic_swarm_1": [
                "reviewable-accept",
                "no-advantage",
                "instrumentation-reject",
                "inconclusive",
            ],
            "CATALYTIC_SWARM_TASK_ADVANTAGE": [
                "reviewable-accept",
                "LOCKED",
            ],
        },
        "claim_limits": {
            "task_advantage_scope": (
                "only this exact eight-task executable suite, model, transport, "
                "budget law, and four-arm comparison"
            ),
            "SOTA_SWARM_CLAIM": "LOCKED",
            "PROCESS_LOCAL_HOLOSTATE_AVAILABLE": "LOCKED",
            "RESTART_PERSISTENT_HOLOSTATE_AVAILABLE": "LOCKED",
            "automatic_promotion": False,
        },
    }


def validate_catalytic_swarm_1_contract(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdvantageProtocolError("CatalyticSwarm-1 contract must be an object")
    expected = build_catalytic_swarm_1_contract()
    if canonical_json_bytes(value) != canonical_json_bytes(expected):
        raise AdvantageProtocolError("CatalyticSwarm-1 contract differs from canonical")
    if value["task_suite"]["suite_sha256"] != EXPECTED_SUITE_SHA256:
        raise AdvantageProtocolError("task-suite hash drift")
    actual_hashes = {
        arm: value["arms"][arm]["plan_sha256"]
        for arm in ARMS
    }
    if actual_hashes != ARM_PLAN_HASHES:
        raise AdvantageProtocolError("arm plan hashes drifted")
    return dict(value)


__all__ = [
    "ARM_PLAN_HASHES",
    "ATTEMPT_VERSION",
    "CONTRACT_ID",
    "ONE_SHOT_PATHS",
    "PREDECESSOR_ARTIFACTS",
    "PREDECESSOR_CONTRACT_SHA256",
    "PREDECESSOR_EVIDENCE_SHA256",
    "SCHEMA_VERSION",
    "AdvantageProtocolError",
    "build_catalytic_swarm_1_contract",
    "contract_sha256",
    "counterbalanced_arm_order",
    "validate_catalytic_swarm_1_contract",
]
