#!/usr/bin/env python3
from __future__ import annotations

import unittest

from catalytic_swarm_1_v6_runtime_binding_protocol import (
    EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256,
    build_v6_runtime_evidence_contract,
    sha256_object,
    validate_v6_runtime_evidence_contract,
)


class V6RuntimeBindingProtocolTests(unittest.TestCase):
    def test_complete_contract_hash_is_exact(self) -> None:
        contract = build_v6_runtime_evidence_contract()
        self.assertEqual(sha256_object(contract), EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256)
        validate_v6_runtime_evidence_contract(contract)

    def test_identity_is_bound_before_any_persistence(self) -> None:
        law = build_v6_runtime_evidence_contract()["evidence_law"]
        self.assertTrue(law["v6_runtime_identity_present_before_first_persist"])
        self.assertTrue(law["every_completed_response_identity_bound_before_append"])
        self.assertTrue(law["ledger_or_result_fallback_persisted_before_lease_release"])
        self.assertTrue(law["ledger_or_result_fallback_persisted_before_acceptance_enforcement"])
        self.assertTrue(law["predecessor_verdict_and_stage_keys_v1_through_v5_forbidden"])

    def test_four_sub_boundaries_are_independent_and_ordered(self) -> None:
        law = build_v6_runtime_evidence_contract()["post_request_boundary_law"]
        self.assertEqual(
            law["ordered_sub_boundaries"],
            ["wddm", "stable_custody", "candidate_custody", "host_memory"],
        )
        self.assertTrue(law["attempt_recorded_before_each_observer_call"])
        self.assertTrue(law["later_safe_observations_do_not_short_circuit"])
        self.assertTrue(law["attempt_observation_and_pass_counts_are_distinct"])

    def test_scheduler_geometry_and_claim_limits_remain_frozen(self) -> None:
        contract = build_v6_runtime_evidence_contract()
        geometry = contract["execution_geometry"]
        self.assertEqual(geometry["common_root_warm_requests"], 8)
        self.assertEqual(geometry["comparison_requests"], 1024)
        self.assertEqual(geometry["total_model_requests"], 1032)
        self.assertEqual(geometry["physical_slots"], 1)
        self.assertEqual(geometry["max_tokens_per_request"], 32)
        self.assertEqual(geometry["deep_requests"], 0)
        self.assertFalse(contract["claim_limits"]["automatic_promotion"])


if __name__ == "__main__":
    unittest.main()
