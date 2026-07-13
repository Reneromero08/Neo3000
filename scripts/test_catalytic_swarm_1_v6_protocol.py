#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest

from catalytic_swarm_1_v5_partial_execution_boundary import EXPECTED_V5_PARTIAL_EXECUTION_BOUNDARY_SHA256
from catalytic_swarm_1_v5_protocol import build_catalytic_swarm_1_v5_contract
from catalytic_swarm_1_v6_protocol import (
    EXPECTED_V6_CONTRACT_SHA256,
    V6_OVERLAY_SHA256,
    CatalyticSwarm1V6ProtocolError,
    build_catalytic_swarm_1_v6_contract,
    build_catalytic_swarm_1_v6_overlay,
    sha256_object,
    validate_v6_overlay,
)


class V6ProtocolTests(unittest.TestCase):
    def test_overlay_and_complete_contract_hashes_are_exact(self) -> None:
        overlay = build_catalytic_swarm_1_v6_overlay()
        self.assertEqual(sha256_object(overlay), V6_OVERLAY_SHA256)
        validate_v6_overlay(overlay)
        self.assertEqual(sha256_object(build_catalytic_swarm_1_v6_contract()), EXPECTED_V6_CONTRACT_SHA256)

    def test_consumed_v5_boundary_is_exact(self) -> None:
        predecessor = build_catalytic_swarm_1_v6_overlay()["predecessor_boundary"]
        self.assertEqual(
            predecessor["sha256"],
            "897148680e426caf58b9581f06224f904cb8ff5cd1a389b83c1ceedfc427f9d9",
        )
        self.assertEqual(predecessor["sha256"], EXPECTED_V5_PARTIAL_EXECUTION_BOUNDARY_SHA256)
        self.assertTrue(predecessor["authority_consumed"])
        self.assertTrue(predecessor["no_retry"])

    def test_frozen_scientific_geometry_is_identical(self) -> None:
        v5 = build_catalytic_swarm_1_v5_contract()
        v6 = build_catalytic_swarm_1_v6_contract(v5)
        for key in (
            "frozen_geometry",
            "cache_admission_law",
            "causal_intervention",
            "execution_safety",
            "advantage_gate",
            "verdicts",
        ):
            self.assertEqual(v6[key], v5[key])

    def test_only_independent_post_request_closure_changes(self) -> None:
        contract = build_catalytic_swarm_1_v6_contract()
        self.assertTrue(all(path.startswith("state/catalytic_swarm_1_v6/") for path in contract["one_shot"]["paths"].values()))
        self.assertEqual(len(contract["one_shot"]["paths"]), 7)
        closure = contract["independent_post_request_sub_boundary_closure"]
        self.assertEqual(
            closure["ordered_sub_boundaries"],
            ["wddm", "stable_custody", "candidate_custody", "host_memory"],
        )
        self.assertTrue(closure["attempt_counter_advances_before_observer_call"])
        self.assertTrue(closure["later_safe_observations_continue_after_earlier_nonpass"])
        self.assertTrue(closure["v5_persistence_and_result_fallback_law_preserved"])
        self.assertTrue(closure["rejected_response_remains_rejected"])

    def test_exact_geometry_and_claim_ceiling_remain_frozen(self) -> None:
        overlay = build_catalytic_swarm_1_v6_overlay()
        geometry = overlay["execution_geometry"]
        self.assertEqual(
            geometry,
            {
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
        )
        self.assertFalse(overlay["claim_limits"]["automatic_promotion"])

    def test_overlay_mutation_rejects(self) -> None:
        changed = copy.deepcopy(build_catalytic_swarm_1_v6_overlay())
        changed["independent_post_request_closure"]["ordered_sub_boundaries"].reverse()
        with self.assertRaises(CatalyticSwarm1V6ProtocolError):
            validate_v6_overlay(changed)


if __name__ == "__main__":
    unittest.main()
