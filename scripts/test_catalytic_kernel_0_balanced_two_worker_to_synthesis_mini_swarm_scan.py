#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import catalytic_kernel_0_balanced_two_worker_to_synthesis_mini_swarm_scan as scan


class TwoWorkerGeometryScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.suite = scan.task_suite.build_frozen_task_suite()
        cls.projections = [task.public_projection() for task in cls.suite.tasks]
        cls.result = scan.scan_public_projections(
            cls.projections, suite_sha256=cls.suite.suite_sha256
        )

    def test_01_frozen_suite_identity_is_exact(self) -> None:
        self.assertEqual(self.suite.suite_sha256, scan.EXPECTED_SUITE_SHA256)
        self.assertEqual(len(self.projections), 8)

    def test_02_scan_uses_only_public_projections(self) -> None:
        self.assertTrue(
            all(
                set(item)
                == {
                    "task_id",
                    "semantics",
                    "public_examples",
                    "candidates",
                    "response_schema",
                }
                for item in self.projections
            )
        )
        encoded = json.dumps(self.projections, sort_keys=True)
        self.assertNotIn("hidden_examples", encoded)
        self.assertNotIn("answer_candidate_id", encoded)

    def test_03_local_shard_and_pair_counts_are_exact(self) -> None:
        self.assertEqual(
            self.result["locally_eligible_shard_counts_by_task_index"],
            [2, 2, 0, 0, 2, 1, 1, 0],
        )
        self.assertEqual(
            self.result["ordered_distinct_local_shard_pair_counts_by_task_index"],
            [2, 2, 0, 0, 2, 0, 0, 0],
        )
        self.assertEqual(self.result["ordered_distinct_local_shard_pair_count"], 6)

    def test_04_distinct_pairs_fail_before_support_geometry(self) -> None:
        self.assertEqual(
            self.result["coverage_overlap_pair_counts_by_task_index"],
            [0, 0, 0, 0, 0, 0, 0, 0],
        )
        self.assertEqual(
            self.result["unique_support_intersection_pair_counts_by_task_index"],
            [0, 0, 0, 0, 0, 0, 0, 0],
        )
        self.assertEqual(self.result["maximum_shard_union_cardinality"], 4)
        self.assertEqual(self.result["minimum_shard_overlap_cardinality"], 2)
        self.assertEqual(self.result["minimum_support_intersection_cardinality"], 3)

    def test_05_required_two_worker_geometry_is_unavailable(self) -> None:
        self.assertEqual(self.result["structurally_eligible_profile_count"], 0)
        self.assertIsNone(self.result["selected_profile"])
        self.assertEqual(scan.build_diagnostic()["status"], scan.CLASSIFICATION)

    def test_06_first_profile_selection_is_lexical(self) -> None:
        profiles = [
            {"lexical_key": (2, (0, 1, 2), (2, 3, 4)), "marker": "later"},
            {"lexical_key": (0, (0, 1, 2), (2, 3, 4)), "marker": "first"},
        ]
        self.assertEqual(scan.select_first_profile(reversed(profiles))["marker"], "first")

    def test_07_hidden_private_and_tokenizer_gates_are_unreached(self) -> None:
        self.assertEqual(
            scan.build_diagnostic()["unreached_gates"],
            {
                "tokenizer_length_gate_consulted": False,
                "protected_hidden_gate_consulted": False,
                "private_binding_loaded": False,
                "hidden_score_computed": False,
            },
        )

    def test_08_no_live_or_executable_surface_is_created(self) -> None:
        diagnostic = scan.build_diagnostic()
        self.assertEqual(diagnostic["omitted_design_surfaces"]["worker_requests_created"], 0)
        self.assertFalse(diagnostic["omitted_design_surfaces"]["controller_created"])
        self.assertFalse(diagnostic["omitted_design_surfaces"]["preregistration_created"])
        self.assertEqual(diagnostic["live_state"]["model_requests"], 0)

    def test_09_public_diagnostic_contains_no_protected_identity(self) -> None:
        encoded = scan.public_scan.canonical_json_text(scan.build_diagnostic())
        self.assertIsNone(scan.public_scan._INTERNAL_CANDIDATE_PATTERN.search(encoded))
        self.assertNotIn("answer_candidate_id", encoded)
        self.assertNotIn("hidden_examples", encoded)
        self.assertNotIn("private_mapping", encoded)

    def test_10_suite_drift_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            scan.TwoWorkerGeometryScanError, "task suite identity changed"
        ):
            scan.scan_public_projections(self.projections, suite_sha256="0" * 64)

    def test_11_artifact_requires_exact_canonical_reconstruction(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repository = Path(raw)
            path = repository / scan.ARTIFACT_RELATIVE_PATH
            path.parent.mkdir(parents=True)
            path.write_bytes(scan.artifact_bytes())
            self.assertEqual(scan.validate_artifact(repository)["status"], "pass")
            value = copy.deepcopy(scan.build_diagnostic())
            value["public_scan"]["maximum_shard_union_cardinality"] = 5
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(
                scan.TwoWorkerGeometryScanError, "differs"
            ):
                scan.validate_artifact(repository)


if __name__ == "__main__":
    unittest.main(verbosity=2)
