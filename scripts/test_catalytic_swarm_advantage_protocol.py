#!/usr/bin/env python3
"""CPU-only contract tests for CatalyticSwarm-1."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from catalytic_swarm_advantage import ARMS
from catalytic_swarm_advantage_protocol import (
    ARM_PLAN_HASHES,
    EXPECTED_CONTRACT_SHA256,
    ONE_SHOT_PATHS,
    PREDECESSOR_ARTIFACTS,
    AdvantageProtocolError,
    build_catalytic_swarm_1_contract,
    contract_sha256,
    counterbalanced_arm_order,
    validate_catalytic_swarm_1_contract,
)

ROOT = Path(__file__).resolve().parent


class CatalyticSwarmAdvantageProtocolTests(unittest.TestCase):
    def test_complete_contract_validates_and_hashes(self) -> None:
        contract = build_catalytic_swarm_1_contract()
        self.assertEqual(validate_catalytic_swarm_1_contract(contract), contract)
        self.assertEqual(contract_sha256(contract), EXPECTED_CONTRACT_SHA256)
        self.assertEqual(
            contract["task_suite"]["suite_sha256"],
            "4B9961D5054BE5D98EF315D2DEAE9D1604E0042A69CB02A8B81FDF513BC1FC92",
        )
        self.assertEqual(
            {arm: contract["arms"][arm]["plan_sha256"] for arm in ARMS},
            ARM_PLAN_HASHES,
        )

    def test_counterbalanced_order_is_latin_square(self) -> None:
        order = counterbalanced_arm_order()
        self.assertEqual(len(order), 8)
        for task_order in order.values():
            self.assertEqual(set(task_order), set(ARMS))
        first_four = list(order.values())[:4]
        for position in range(4):
            self.assertEqual({row[position] for row in first_four}, set(ARMS))
        self.assertEqual(list(order.values())[4:], first_four)

    def test_predecessor_and_one_shot_paths_are_complete(self) -> None:
        contract = build_catalytic_swarm_1_contract()
        self.assertEqual(contract["predecessor"]["artifacts"], PREDECESSOR_ARTIFACTS)
        self.assertEqual(contract["one_shot"]["paths"], ONE_SHOT_PATHS)
        self.assertTrue(
            all(
                path.startswith("state/catalytic_swarm_1/")
                for path in ONE_SHOT_PATHS.values()
            )
        )
        self.assertTrue(contract["one_shot"]["no_retry"])

    def test_all_one_shot_paths_are_ignored_and_absent(self) -> None:
        repository = ROOT.parent
        ignore_lines = {
            line.strip()
            for line in (repository / ".gitignore").read_text(
                encoding="utf-8"
            ).splitlines()
        }
        self.assertIn("state/catalytic_swarm_1/", ignore_lines)
        for relative in ONE_SHOT_PATHS.values():
            self.assertFalse((repository / relative).exists(), relative)

    def test_hidden_feedback_and_deep_are_forbidden(self) -> None:
        contract = build_catalytic_swarm_1_contract()
        self.assertFalse(contract["task_suite"]["hidden_examples_visible_to_model"])
        self.assertFalse(contract["task_suite"]["answer_key_visible_to_model"])
        self.assertFalse(contract["task_suite"]["hidden_scores_reused_as_context"])
        self.assertEqual(contract["shared_transport"]["deep_requests"], 0)
        self.assertTrue(
            contract["isolation_law"]
            ["hidden_examples_forbidden_in_requests_and_ledger"]
        )

    def test_common_root_warm_is_outside_arm_budgets(self) -> None:
        contract = build_catalytic_swarm_1_contract()
        warm = contract["task_root_warm"]
        self.assertEqual(warm["warm_request_count"], 8)
        self.assertTrue(warm["occurs_before_any_arm_for_task"])
        self.assertTrue(warm["same_public_root_for_all_four_arms"])
        self.assertTrue(warm["warm_cost_excluded_from_arm_comparison_budgets"])
        self.assertTrue(warm["all_arms_require_observed_root_cache_reuse"])
        transport = contract["shared_transport"]
        self.assertEqual(transport["comparison_request_count"], 1024)
        self.assertEqual(transport["task_root_warm_request_count"], 8)
        self.assertEqual(transport["total_live_request_count"], 1032)

    def test_equal_budget_law_is_exact(self) -> None:
        budget = build_catalytic_swarm_1_contract()["budget_law"]
        self.assertEqual(budget["requests_per_arm_per_task"], 32)
        self.assertEqual(budget["maximum_tokens_per_request"], 32)
        self.assertEqual(
            budget["maximum_completion_tokens_per_arm_per_task"], 1024
        )
        self.assertEqual(budget["actual_total_model_token_ratio_max"], 1.10)
        self.assertEqual(budget["parity_failure_verdict"], "inconclusive")

    def test_advantage_gate_is_narrow_and_no_promotion(self) -> None:
        contract = build_catalytic_swarm_1_contract()
        gate = contract["advantage_gate"]
        self.assertEqual(gate["verified_exact_hidden_success_minimum"], 6)
        self.assertEqual(gate["verified_success_margin_over_each_baseline"], 2)
        self.assertTrue(gate["paired_hidden_score_wins_must_exceed_losses"])
        self.assertEqual(contract["claim_limits"]["SOTA_SWARM_CLAIM"], "LOCKED")
        self.assertFalse(contract["claim_limits"]["automatic_promotion"])

    def test_any_contract_drift_rejects(self) -> None:
        contract = build_catalytic_swarm_1_contract()
        changed = copy.deepcopy(contract)
        changed["budget_law"]["maximum_tokens_per_request"] = 64
        with self.assertRaises(AdvantageProtocolError):
            validate_catalytic_swarm_1_contract(changed)

    def test_protocol_module_has_no_live_execution_surface(self) -> None:
        source = (ROOT / "catalytic_swarm_advantage_protocol.py").read_text(
            encoding="utf-8"
        )
        for forbidden in (
            "import subprocess",
            "import socket",
            "import urllib",
            "import requests",
            "Popen(",
            "os.system",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
