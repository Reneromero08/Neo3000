#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest

from catalytic_swarm_1_v4_protocol import build_catalytic_swarm_1_v4_contract
from catalytic_swarm_1_v5_protocol import (
    EXPECTED_V5_CONTRACT_SHA256,
    V5_OVERLAY_SHA256,
    CatalyticSwarm1V5ProtocolError,
    build_catalytic_swarm_1_v5_contract,
    build_catalytic_swarm_1_v5_overlay,
    sha256_object,
    validate_v5_overlay,
)


class V5ProtocolTests(unittest.TestCase):
    def test_overlay_and_complete_contract_hashes_are_exact(self) -> None:
        overlay = build_catalytic_swarm_1_v5_overlay()
        self.assertEqual(sha256_object(overlay), V5_OVERLAY_SHA256)
        validate_v5_overlay(overlay)
        self.assertEqual(sha256_object(build_catalytic_swarm_1_v5_contract()), EXPECTED_V5_CONTRACT_SHA256)

    def test_frozen_scientific_geometry_is_identical(self) -> None:
        v4 = build_catalytic_swarm_1_v4_contract()
        v5 = build_catalytic_swarm_1_v5_contract(v4)
        for key in ("frozen_geometry", "cache_admission_law", "causal_intervention", "execution_safety", "advantage_gate", "verdicts"):
            self.assertEqual(v5[key], v4[key])

    def test_only_v5_paths_and_completed_response_closure_change(self) -> None:
        contract = build_catalytic_swarm_1_v5_contract()
        self.assertTrue(all(path.startswith("state/catalytic_swarm_1_v5/") for path in contract["one_shot"]["paths"].values()))
        repair = contract["completed_response_closure_repair"]
        self.assertTrue(repair["accepted_model_behavior_unchanged"])
        self.assertTrue(repair["ledger_fsync_before_acceptance_enforcement"])
        self.assertTrue(repair["no_next_request_after_failed_gate"])

    def test_v4_consumed_partial_boundary_is_required(self) -> None:
        predecessor = build_catalytic_swarm_1_v5_contract()["predecessors"]["catalytic_swarm_1_v4_partial_execution"]
        self.assertTrue(predecessor["authority_consumed"])
        self.assertTrue(predecessor["no_retry"])
        self.assertEqual(predecessor["completed_model_requests"], 775)
        self.assertEqual(predecessor["ledger_records"], 774)

    def test_overlay_mutation_rejects(self) -> None:
        changed = copy.deepcopy(build_catalytic_swarm_1_v5_overlay())
        changed["execution_geometry"]["total_model_requests"] = 1031
        with self.assertRaises(CatalyticSwarm1V5ProtocolError):
            validate_v5_overlay(changed)


if __name__ == "__main__":
    unittest.main()
