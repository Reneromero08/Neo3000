#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from catalytic_swarm_1_v4_partial_execution_boundary import (
    EXPECTED_V4_PARTIAL_EXECUTION_BOUNDARY_SHA256,
    build_catalytic_swarm_1_v4_partial_execution_boundary,
    sha256_object,
    validate_catalytic_swarm_1_v4_partial_execution_boundary,
)


ROOT = Path(__file__).resolve().parents[1]


class V4PartialExecutionBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.boundary = build_catalytic_swarm_1_v4_partial_execution_boundary()

    def test_boundary_hash_and_validation_are_exact(self) -> None:
        self.assertEqual(sha256_object(self.boundary), EXPECTED_V4_PARTIAL_EXECUTION_BOUNDARY_SHA256)
        validate_catalytic_swarm_1_v4_partial_execution_boundary(self.boundary)

    def test_all_seven_raw_artifacts_match(self) -> None:
        for artifact in self.boundary["artifacts"]:
            with self.subTest(path=artifact["path"]):
                path = ROOT / artifact["path"]
                self.assertEqual(path.stat().st_size, artifact["size_bytes"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest().upper(), artifact["sha256"])

    def test_request_gap_and_claim_ceiling_are_explicit(self) -> None:
        accounting = self.boundary["request_accounting"]
        reconciliation = self.boundary["reconciliation"]
        self.assertEqual(accounting["completed_model_requests"], 775)
        self.assertEqual(reconciliation["ledger_records"], 774)
        self.assertEqual(reconciliation["host_memory_checks"], 774)
        self.assertFalse(self.boundary["outcome"]["task_advantage_adjudicated"])
        self.assertEqual(self.boundary["claims"]["CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN"], "LOCKED")

    def test_exact_failed_predicate_remains_unavailable(self) -> None:
        diagnosis = self.boundary["causal_diagnosis"]
        self.assertEqual(diagnosis["defect"], "completed-response-evidence-closure")
        self.assertIn("exact failed warm predicate", diagnosis["unavailable"])


if __name__ == "__main__":
    unittest.main()
