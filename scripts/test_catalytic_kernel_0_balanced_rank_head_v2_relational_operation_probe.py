#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import catalytic_kernel_0_balanced_rank_head_v2_relational_operation_probe as probe
import catalytic_kernel_0_balanced_rank_head_v2_relational_operation_probe_scientific as scientific


REPOSITORY = Path(__file__).resolve().parent.parent
MODEL_ENV = "NEO3000_TOKENIZER_MODEL"


class RelationalOperationProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        model = os.environ.get(MODEL_ENV)
        if not model:
            raise unittest.SkipTest(
                f"{MODEL_ENV} is required for the offline tokenizer reconstruction"
            )
        cls.model_path = Path(model)
        cls.root, cls.private = probe._load_private(REPOSITORY)
        cls.tokenizer = probe.asymmetry.OfflineTokenizer(cls.model_path)
        cls.selection = probe.select_first_eligible(cls.root, cls.tokenizer)
        cls.geometries = cls.selection["geometries"]
        cls.payloads = {
            request_id: probe.build_request(cls.root, cls.geometries, request_id)
            for request_id in probe.REQUEST_IDS
        }
        cls.artifact_path = REPOSITORY / probe.PREREGISTRATION_PATH
        cls.artifact = json.loads(cls.artifact_path.read_bytes())

    def test_01_exactly_four_transform_only_requests_exist(self) -> None:
        self.assertEqual(
            probe.REQUEST_IDS,
            ("G0-AB", "G0-BA", "G1-AB", "G1-BA"),
        )
        self.assertEqual(self.artifact["request_set"]["request_count"], 4)
        self.assertTrue(self.artifact["request_set"]["transform_only"])
        self.assertEqual(self.artifact["request_set"]["borrow_requests"], 0)
        self.assertEqual(self.artifact["request_set"]["branch_requests"], 0)
        self.assertEqual(
            self.artifact["request_set"]["model_authored_extraction_requests"], 0
        )
        self.assertEqual(self.artifact["request_set"]["restore_requests"], 0)

    def test_02_ab_and_ba_swap_only_parent_presentation_order(self) -> None:
        for geometry_id in probe.GEOMETRY_IDS:
            ab = probe.build_assignment(
                self.root, self.geometries, f"{geometry_id}-AB"
            )
            ba = probe.build_assignment(
                self.root, self.geometries, f"{geometry_id}-BA"
            )
            self.assertEqual(ab["parent_artifacts"], list(reversed(ba["parent_artifacts"])))
            self.assertEqual(ab["instruction"], ba["instruction"])
            self.assertEqual(ab["stage"], "transform")

    def test_03_geometries_have_different_shared_candidates_and_decoys(self) -> None:
        g0 = self.geometries["G0"]
        g1 = self.geometries["G1"]
        self.assertNotEqual(g0["unique-intersection"], g1["unique-intersection"])
        g0_union = set(g0["parent-a"]) | set(g0["parent-b"])
        g1_union = set(g1["parent-a"]) | set(g1["parent-b"])
        self.assertTrue(g0_union.isdisjoint(g1_union))
        for geometry in (g0, g1):
            self.assertEqual(len(set(geometry["parent-a"]) & set(geometry["parent-b"])), 1)
            self.assertEqual(geometry["parent-a"][3], geometry["unique-intersection"])
            self.assertEqual(geometry["parent-b"][2], geometry["unique-intersection"])

    def test_04_all_competing_predictions_are_frozen_and_discriminating(self) -> None:
        contrast = probe._contrast_report(self.root, self.geometries)
        self.assertEqual(tuple(contrast["mechanisms"]), probe.MECHANISMS)
        self.assertTrue(contrast["intersection_vs_parent_order_and_surface_discriminated"])
        for request_id in probe.REQUEST_IDS:
            report = contrast["per_request"][request_id]
            self.assertEqual(report["unique_prediction_count"], 4)
            self.assertEqual(
                set(report["prediction_commitments"]), set(probe.MECHANISMS)
            )
            self.assertTrue(
                report["intersection_distinct_from_all_surface_and_parent_priorities"]
            )

    def test_05_first_match_and_length_gates_are_exact(self) -> None:
        self.assertEqual(self.selection["counter"], self.artifact["geometry_selection"]["selected_counter"])
        for counter in range(self.selection["counter"]):
            self.assertFalse(
                probe._selection_candidate(self.root, counter, self.tokenizer)["eligible"]
            )
        self.assertEqual(
            len(set(self.selection["serialized_assignment_byte_lengths"].values())), 1
        )
        self.assertEqual(
            len(set(self.selection["tokenizer_assignment_lengths"].values())), 1
        )

    def test_06_exact_request_hashes_and_order_are_stable(self) -> None:
        observed = {
            request_id: probe.json_sha256(self.payloads[request_id])
            for request_id in probe.REQUEST_IDS
        }
        self.assertEqual(observed, self.artifact["request_set"]["request_sha256"])
        self.assertEqual(self.artifact["request_set"]["execution_order"], list(probe.REQUEST_IDS))
        self.assertEqual(len(set(observed.values())), 4)
        self.assertEqual(
            {payload["seed"] for payload in self.payloads.values()},
            {probe.FIXED_TRANSFORM_SEED},
        )

    def test_07_one_generation_each_and_four_total_are_enforced(self) -> None:
        started: list[str] = []
        for request_id in probe.REQUEST_IDS:
            probe.assert_can_start(started, request_id)
            started.append(request_id)
        with self.assertRaisesRegex(probe.RelationalOperationProbeError, "duplicate"):
            probe.assert_can_start(started[:1], started[0])
        with self.assertRaisesRegex(probe.RelationalOperationProbeError, "ceiling"):
            probe.assert_can_start(started, probe.REQUEST_IDS[-1])

    def test_08_private_geometry_identities_do_not_enter_tracked_artifacts(self) -> None:
        tracked_paths = (
            REPOSITORY / probe.PREREGISTRATION_PATH,
            REPOSITORY
            / "scripts/catalytic_kernel_0_balanced_rank_head_v2_relational_operation_probe.py",
            REPOSITORY
            / "scripts/catalytic_kernel_0_balanced_rank_head_v2_relational_operation_probe_scientific.py",
            Path(__file__),
            REPOSITORY / "TASKS.md",
            REPOSITORY / "ROADMAP.md",
            REPOSITORY / "lab/GOAL.md",
            REPOSITORY / "lab/CHECKPOINT.md",
            REPOSITORY / "lab/EVALUATOR.json",
            REPOSITORY / "lab/EVALUATOR.lock.json",
        )
        haystack = b"\n".join(path.read_bytes() for path in tracked_paths)
        private_aliases = set()
        for geometry in self.geometries.values():
            private_aliases.update(geometry["parent-a"])
            private_aliases.update(geometry["parent-b"])
        for alias in private_aliases:
            self.assertNotIn(json.dumps(alias).encode("ascii"), haystack)
        self.assertNotIn(self.root, haystack)

    def test_09_authenticated_capture_replays_without_model_contact(self) -> None:
        execution = {
            name: None for name in scientific.CAPTURE_EXECUTION_FIELDS
        }
        execution.update(
            {
                "content": "{}",
                "finish_reason": "stop",
                "http_status": 200,
                "event_count": 1,
            }
        )
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "capture.json"
            capture = scientific.capture_execution(
                path,
                experiment_key=b"x" * 32,
                request_id=probe.REQUEST_IDS[0],
                model_request_sha256="A" * 64,
                execution=SimpleNamespace(**execution),
                raw_response_bytes=b"data: {}\n\n",
            )
            replay = scientific.replay_capture(capture)
            self.assertEqual(replay.content, "{}")
            self.assertEqual(replay.http_status, 200)

    def test_10_decision_law_supports_only_the_matching_operation(self) -> None:
        selections = {}
        outcomes = {}
        for request_id in probe.REQUEST_IDS:
            geometry_id, order = probe._request_parts(request_id)
            predictions = probe._private_predictions(
                self.geometries[geometry_id], request_id
            )
            selected = predictions["unique-intersection"]
            selections[request_id] = selected
            outcomes[request_id] = {
                "request_id": request_id,
                "geometry_id": geometry_id,
                "presentation_order": order,
                "selected_from_parent_union": True,
                "mechanism_matches": {
                    mechanism: selected == prediction
                    for mechanism, prediction in predictions.items()
                },
            }
        result = probe.adjudicate_outcomes(outcomes, selections)
        self.assertEqual(
            result["classification"],
            "COMMUTATIVE_UNIQUE_INTERSECTION_LIKE_TRANSFORM_SUPPORTED_ON_TWO_MATCHED_GEOMETRIES",
        )
        self.assertFalse(result["formal_algebra_claimed"])

    def test_11_preregistration_reconstructs_with_zero_live_state(self) -> None:
        validation = probe.validate_preregistration(REPOSITORY, self.model_path)
        self.assertEqual(validation["status"], "pass")
        self.assertEqual(validation["future_model_generations"], 4)
        self.assertFalse(validation["authority_created"])
        self.assertFalse(validation["authority_consumed"])
        self.assertEqual(validation["model_requests_issued"], 0)
        self.assertFalse(validation["sidecar_launched"])
        self.assertFalse(validation["live_execution_performed"])

    def test_12_future_command_requires_separate_external_authority(self) -> None:
        command = self.artifact["future_live_command_shape"]
        self.assertIn(" run ", command)
        self.assertIn("--external-authority-id <fresh-64-hex>", command)
        self.assertIn("--authorized-commit <published-static-commit>", command)
        self.assertFalse(self.artifact["execution_state"]["authority_created"])
        self.assertFalse(self.artifact["execution_state"]["scientific_result_created"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
