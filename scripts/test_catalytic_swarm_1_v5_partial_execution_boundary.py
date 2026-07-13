#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from catalytic_swarm_1_v5_partial_execution_boundary import (
    EXPECTED_V5_PARTIAL_EXECUTION_BOUNDARY_SHA256,
    build_catalytic_swarm_1_v5_partial_execution_boundary,
    sha256_object,
    validate_catalytic_swarm_1_v5_partial_execution_boundary,
)


ROOT = Path(__file__).resolve().parents[1]


class V5PartialExecutionBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.boundary = build_catalytic_swarm_1_v5_partial_execution_boundary()

    def test_boundary_hash_and_validation_are_exact(self) -> None:
        self.assertEqual(
            sha256_object(self.boundary),
            EXPECTED_V5_PARTIAL_EXECUTION_BOUNDARY_SHA256,
        )
        validate_catalytic_swarm_1_v5_partial_execution_boundary(self.boundary)

    def test_all_seven_v5_raw_artifacts_match(self) -> None:
        for artifact in self.boundary["artifacts"]:
            with self.subTest(path=artifact["path"]):
                path = ROOT / artifact["path"]
                self.assertEqual(path.stat().st_size, artifact["size_bytes"])
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest().upper(),
                    artifact["sha256"],
                )

    def test_all_declared_v3_and_v4_artifacts_match(self) -> None:
        predecessor = self.boundary["predecessor_preservation"]
        v3 = predecessor["v3"]["artifact"]
        v3_path = ROOT / v3["path"]
        self.assertEqual(v3_path.stat().st_size, v3["size_bytes"])
        self.assertEqual(hashlib.sha256(v3_path.read_bytes()).hexdigest().upper(), v3["sha256"])
        self.assertEqual(predecessor["v3"]["other_artifacts_present"], 0)
        for artifact in predecessor["v4_artifacts"]:
            with self.subTest(path=artifact["path"]):
                path = ROOT / artifact["path"]
                self.assertEqual(path.stat().st_size, artifact["size_bytes"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest().upper(), artifact["sha256"])

    def test_record_775_matches_the_canonical_compound_fixture(self) -> None:
        ledger_path = ROOT / "state/catalytic_swarm_1_v5/ledger-v5.jsonl"
        with ledger_path.open(encoding="utf-8") as handle:
            records = [json.loads(line) for line in handle if line.strip()]
        self.assertEqual(len(records), 775)
        record = records[-1]
        expected = self.boundary["post_request_reconciliation"]["record_775"]
        self.assertEqual(record["global_record_index"], 775)
        self.assertEqual(record["request_sequence_index"], 775)
        self.assertEqual(record["request_label"], "cs1-task-07:common-root-warm")
        for key, value in expected.items():
            if key in record:
                self.assertEqual(record[key], value, key)
            elif key in record.get("gate_outcomes", {}):
                self.assertEqual(record["gate_outcomes"][key], value, key)
            elif key.endswith("_passed") and key in record.get("post_request_boundary", {}):
                self.assertEqual(record["post_request_boundary"][key], value, key)
            else:
                self.fail(f"record 775 lacks canonical field: {key}")

    def test_completed_response_is_durable_but_host_accounting_is_short(self) -> None:
        completion = self.boundary["completion_reconciliation"]
        post = self.boundary["post_request_reconciliation"]
        self.assertEqual(completion["completed_responses"], 775)
        self.assertEqual(completion["ledger_records"], 775)
        self.assertTrue(completion["durable_equation_passed"])
        self.assertEqual(post["host_memory_checks"], 774)
        self.assertEqual(post["expected_host_memory_checks"], 775)
        self.assertFalse(post["passed"])

    def test_causal_limit_does_not_invent_a_narrow_failure(self) -> None:
        diagnosis = self.boundary["causal_diagnosis"]
        self.assertEqual(
            diagnosis["defect"],
            "compound-post-request-sub-boundary-accounting-and-diagnosability",
        )
        self.assertIn("no narrower live cause", diagnosis["unavailable"])
        self.assertFalse(diagnosis["host_ceiling_breach_proved"])
        self.assertFalse(diagnosis["repository_mutation_proved"])


if __name__ == "__main__":
    unittest.main()
