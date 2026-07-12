#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest

from catalytic_swarm_1_cache_diagnostic_protocol import (
    build_cache_diagnostic_contract,
    contract_sha256,
    validate_cache_diagnostic_contract,
)


class ProtocolTests(unittest.TestCase):
    def test_contract_is_canonical(self):
        contract = build_cache_diagnostic_contract()
        validate_cache_diagnostic_contract(contract)
        self.assertEqual(len(contract_sha256(contract)), 64)

    def test_three_request_limit(self):
        contract = build_cache_diagnostic_contract()
        self.assertEqual(contract["request_law"]["maximum_model_requests"], 3)
        self.assertEqual(len(contract["sequence"]), 3)

    def test_task_advantage_remains_locked(self):
        claims = build_cache_diagnostic_contract()["claims"]
        self.assertEqual(claims["task_advantage"], "LOCKED")
        self.assertFalse(claims["automatic_promotion"])

    def test_measurements_persist_before_gate(self):
        fields = build_cache_diagnostic_contract()["measurement_law"]["persist_before_gate"]
        for required in (
            "public_root_terminal_token_index",
            "common_prefix_tokens",
            "required_cached_prompt_tokens",
            "actual_cached_prompt_tokens",
            "fresh_prompt_tokens",
        ):
            self.assertIn(required, fields)

    def test_terminal_reconciler_is_cs1_specific(self):
        terminal = build_cache_diagnostic_contract()["terminal_reconciliation"]
        self.assertTrue(terminal["use_cs1_request_boundary_namespace"])
        self.assertTrue(terminal["accept_exact_observed_request_count_on_early_stop"])

    def test_drift_rejected(self):
        contract = build_cache_diagnostic_contract()
        mutated = copy.deepcopy(contract)
        mutated["request_law"]["maximum_model_requests"] = 4
        with self.assertRaises(ValueError):
            validate_cache_diagnostic_contract(mutated)


if __name__ == "__main__":
    unittest.main()
