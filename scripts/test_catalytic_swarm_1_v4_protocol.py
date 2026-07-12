#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest

from catalytic_swarm_1_v3_protocol import build_catalytic_swarm_1_v3_contract
from catalytic_swarm_1_v4_protocol import (
    EXPECTED_V4_CONTRACT_SHA256,
    V4_OVERLAY_SHA256,
    CatalyticSwarm1V4ProtocolError,
    build_catalytic_swarm_1_v4_contract,
    build_catalytic_swarm_1_v4_overlay,
    sha256_object,
    validate_v4_overlay,
)


class V4ProtocolTests(unittest.TestCase):
    def test_overlay_hash_is_exact(self) -> None:
        overlay = build_catalytic_swarm_1_v4_overlay()
        self.assertEqual(sha256_object(overlay), V4_OVERLAY_SHA256)
        validate_v4_overlay(overlay)

    def test_complete_contract_hash_is_exact(self) -> None:
        self.assertEqual(sha256_object(build_catalytic_swarm_1_v4_contract()), EXPECTED_V4_CONTRACT_SHA256)

    def test_v3_consumed_boundary_is_required(self) -> None:
        predecessor = build_catalytic_swarm_1_v4_contract()["predecessors"]["catalytic_swarm_1_v3_preclaim"]
        self.assertTrue(predecessor["authority_consumed"])
        self.assertTrue(predecessor["no_retry"])
        self.assertEqual(predecessor["artifacts_claimed"], 1)
        self.assertEqual(predecessor["model_requests"], 0)

    def test_frozen_scientific_geometry_is_identical(self) -> None:
        v3 = build_catalytic_swarm_1_v3_contract(); v4 = build_catalytic_swarm_1_v4_contract(v3)
        for key in ("frozen_geometry", "cache_admission_law", "causal_intervention", "execution_safety", "advantage_gate", "verdicts"):
            self.assertEqual(v4[key], v3[key])

    def test_only_v4_paths_are_declared(self) -> None:
        values = build_catalytic_swarm_1_v4_contract()["one_shot"]["paths"].values()
        self.assertTrue(all(path.startswith("state/catalytic_swarm_1_v4/") for path in values))

    def test_claims_no_deep_and_promotion_remain_frozen(self) -> None:
        contract = build_catalytic_swarm_1_v4_contract()
        self.assertEqual(contract["frozen_geometry"]["deep_requests"], 0)
        self.assertEqual(contract["frozen_geometry"]["total_model_requests"], 1032)
        self.assertFalse(contract["claim_limits"]["automatic_promotion"])

    def test_overlay_mutation_rejects(self) -> None:
        changed = copy.deepcopy(build_catalytic_swarm_1_v4_overlay())
        changed["execution_geometry"]["total_model_requests"] = 1031
        with self.assertRaises(CatalyticSwarm1V4ProtocolError):
            validate_v4_overlay(changed)

    def test_semantic_order_is_the_only_successor_change(self) -> None:
        repair = build_catalytic_swarm_1_v4_contract()["semantic_mapping_repair"]
        self.assertTrue(repair["semantic_key_set_exact"])
        self.assertTrue(repair["explicit_canonical_projection"])
        self.assertFalse(repair["source_mapping_insertion_order_authoritative"])
        self.assertTrue(repair["task_suite_arms_budgets_and_thresholds_unchanged"])


if __name__ == "__main__":
    unittest.main()
