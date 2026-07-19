#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import catalytic_kernel_0_balanced_rank_head_v2_joint_condition_intersection_replication as source
import catalytic_kernel_0_balanced_rank_head_v2_three_parent_global_invariant_probe as probe
import catalytic_kernel_0_balanced_rank_head_v2_three_parent_global_invariant_probe_scientific as scientific


REPOSITORY = Path(__file__).resolve().parent.parent
MODEL_ENV = "NEO3000_TOKENIZER_MODEL"


class ThreeParentGlobalInvariantProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        model = os.environ.get(MODEL_ENV)
        if not model:
            raise unittest.SkipTest(
                f"{MODEL_ENV} is required for offline tokenizer reconstruction"
            )
        cls.model_path = Path(model)
        cls.root, cls.private = probe._load_private(REPOSITORY)
        cls.tokenizer = probe.asymmetry.OfflineTokenizer(cls.model_path)
        cls.selection = probe.select_first_eligible(cls.root, cls.tokenizer)
        cls.geometries = cls.selection["geometries"]
        cls.payloads = {
            request_id: probe.build_request(
                cls.root, cls.geometries, request_id
            )
            for request_id in probe.REQUEST_IDS
        }
        cls.artifact_path = REPOSITORY / probe.PREREGISTRATION_PATH
        cls.artifact = json.loads(cls.artifact_path.read_bytes())

    def test_01_exactly_six_transform_only_requests_are_frozen(self) -> None:
        self.assertEqual(
            probe.REQUEST_IDS,
            (
                "T0-ABC",
                "T0-BCA",
                "T0-CAB",
                "T1-ABC",
                "T1-BCA",
                "T1-CAB",
            ),
        )
        request_set = self.artifact["request_set"]
        self.assertEqual(request_set["request_count"], 6)
        self.assertEqual(request_set["maximum_total_generations"], 6)
        self.assertTrue(request_set["transform_only"])
        self.assertEqual(request_set["borrow_requests"], 0)
        self.assertEqual(request_set["branch_requests"], 0)
        self.assertEqual(request_set["model_authored_extraction_requests"], 0)
        self.assertEqual(request_set["restore_requests"], 0)

    def test_02_source_private_root_alias_universe_and_seed_are_reused(self) -> None:
        source_root, source_private = source._load_private(REPOSITORY)
        self.assertEqual(self.root, source_root)
        self.assertEqual(self.private.secret_commitment, source_private.secret_commitment)
        self.assertEqual(
            self.private.alias_map_commitment, source_private.alias_map_commitment
        )
        self.assertEqual(probe.PRIVATE_ROOT_PATH, source.PRIVATE_ROOT_PATH)
        self.assertEqual(probe.FIXED_TRANSFORM_SEED, source.FIXED_TRANSFORM_SEED)
        private_binding = self.artifact["private_binding"]
        self.assertFalse(private_binding["fresh_private_root_created"])
        self.assertTrue(private_binding["source_private_root_path_reused"])
        self.assertTrue(private_binding["source_opaque_alias_correspondence_reused"])

    def test_03_each_geometry_has_exact_three_parent_intersection_law(self) -> None:
        for geometry in self.geometries.values():
            a = set(geometry["parent-a"])
            b = set(geometry["parent-b"])
            c = set(geometry["parent-c"])
            x_value = geometry["unique-three-way-intersection"]
            self.assertEqual(len(a), 5)
            self.assertEqual(len(b), 5)
            self.assertEqual(len(c), 5)
            self.assertEqual(a & b, {x_value, geometry["pair-decoys"]["AB"]})
            self.assertEqual(a & c, {x_value, geometry["pair-decoys"]["CA"]})
            self.assertEqual(b & c, {x_value, geometry["pair-decoys"]["BC"]})
            self.assertEqual(a & b & c, {x_value})
            self.assertEqual(geometry["parent-a"][3], x_value)
            self.assertEqual(geometry["parent-b"][2], x_value)
            self.assertEqual(geometry["parent-c"][1], x_value)

    def test_04_geometries_are_identity_disjoint(self) -> None:
        unions = []
        for geometry_id in probe.GEOMETRY_IDS:
            geometry = self.geometries[geometry_id]
            unions.append(
                set(geometry["parent-a"])
                | set(geometry["parent-b"])
                | set(geometry["parent-c"])
            )
        self.assertEqual(len(unions[0]), 10)
        self.assertEqual(len(unions[1]), 10)
        self.assertTrue(unions[0].isdisjoint(unions[1]))

    def test_05_cyclic_orders_change_only_parent_presentation(self) -> None:
        expected_roles = {
            "ABC": ["parent-a", "parent-b", "parent-c"],
            "BCA": ["parent-b", "parent-c", "parent-a"],
            "CAB": ["parent-c", "parent-a", "parent-b"],
        }
        for geometry_id in probe.GEOMETRY_IDS:
            assignments = {
                order: probe.build_assignment(
                    self.root, self.geometries, f"{geometry_id}-{order}"
                )
                for order in probe.PRESENTATION_ORDERS
            }
            for order, assignment in assignments.items():
                self.assertEqual(
                    [value["artifact_role"] for value in assignment["parent_artifacts"]],
                    expected_roles[order],
                )
                self.assertEqual(assignment["stage"], "transform")
            self.assertEqual(
                len({value["instruction"] for value in assignments.values()}), 1
            )

    def test_06_lengths_requests_and_seed_are_exactly_matched(self) -> None:
        self.assertEqual(self.selection["counter"], 0)
        self.assertEqual(
            len(set(self.selection["serialized_assignment_byte_lengths"].values())),
            1,
        )
        self.assertEqual(
            len(set(self.selection["tokenizer_assignment_lengths"].values())),
            1,
        )
        hashes = {
            request_id: probe.json_sha256(payload)
            for request_id, payload in self.payloads.items()
        }
        self.assertEqual(hashes, self.artifact["request_set"]["request_sha256"])
        self.assertEqual(len(set(hashes.values())), 6)
        self.assertEqual(
            {payload["seed"] for payload in self.payloads.values()},
            {633514649},
        )

    def test_07_competing_predictions_and_pair_decoys_are_frozen(self) -> None:
        contrast = probe._contrast_report(self.root, self.geometries)
        self.assertEqual(tuple(contrast["mechanisms"]), probe.MECHANISMS)
        self.assertTrue(contrast["global_invariant_distinct_from_every_competitor"])
        for geometry_id in probe.GEOMETRY_IDS:
            geometry = self.geometries[geometry_id]
            expected = {"ABC": "AB", "BCA": "BC", "CAB": "CA"}
            for order, pair in expected.items():
                request_id = f"{geometry_id}-{order}"
                predictions = probe._private_predictions(geometry, request_id)
                self.assertEqual(
                    predictions["first-presented-pair-decoy"],
                    geometry["pair-decoys"][pair],
                )
                self.assertNotIn(
                    predictions["unique-three-way-intersection"],
                    [
                        value
                        for mechanism, value in predictions.items()
                        if mechanism != "unique-three-way-intersection"
                    ],
                )

    def test_08_one_generation_each_and_six_total_are_enforced(self) -> None:
        started: list[str] = []
        for request_id in probe.REQUEST_IDS:
            probe.assert_can_start(started, request_id)
            started.append(request_id)
        with self.assertRaisesRegex(
            probe.ThreeParentGlobalInvariantProbeError, "duplicate"
        ):
            probe.assert_can_start(started[:1], started[0])
        with self.assertRaisesRegex(
            probe.ThreeParentGlobalInvariantProbeError, "ceiling"
        ):
            probe.assert_can_start(started, probe.REQUEST_IDS[-1])

    def test_09_authenticated_capture_replays_without_model_contact(self) -> None:
        execution = {name: None for name in scientific.CAPTURE_EXECUTION_FIELDS}
        execution.update(
            {"content": "{}", "finish_reason": "stop", "http_status": 200, "event_count": 1}
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

    def _outcomes_for(self, mechanism: str) -> tuple[dict, dict]:
        outcomes = {}
        selections = {}
        for request_id in probe.REQUEST_IDS:
            geometry_id, order = probe._request_parts(request_id)
            predictions = probe._private_predictions(
                self.geometries[geometry_id], request_id
            )
            selected = predictions[mechanism]
            selections[request_id] = selected
            outcomes[request_id] = {
                "request_id": request_id,
                "geometry_id": geometry_id,
                "presentation_order": order,
                "mechanism_matches": {
                    name: selected == value for name, value in predictions.items()
                },
            }
        return outcomes, selections

    def test_10_decision_law_supports_global_invariant_only(self) -> None:
        outcomes, selections = self._outcomes_for(
            "unique-three-way-intersection"
        )
        result = probe.adjudicate_outcomes(outcomes, selections)
        self.assertEqual(
            result["classification"],
            "THREE_PARENT_GLOBAL_RELATIONAL_INVARIANT_EXTRACTION_SUPPORTED_"
            "ON_TWO_MATCHED_GEOMETRIES",
        )
        self.assertEqual(
            result["supported_interpretation"],
            "TRANSFORM_SELECTS_AN_INVARIANT_IDENTIFIABLE_ONLY_FROM_THE_COMPLETE_"
            "THREE_PARENT_RELATION_AND_NOT_FROM_ANY_SINGLE_PARENT_OR_PARENT_PAIR",
        )
        self.assertFalse(result["full_commutativity_claimed"])
        self.assertFalse(result["associativity_claimed"])

    def test_11_decision_law_identifies_pair_and_surface_alternatives(self) -> None:
        pair_outcomes, pair_selections = self._outcomes_for(
            "first-presented-pair-decoy"
        )
        self.assertEqual(
            probe.adjudicate_outcomes(pair_outcomes, pair_selections)["classification"],
            "PAIR_COLLAPSE_MECHANISM_SUPPORTED",
        )
        lexical_outcomes, lexical_selections = self._outcomes_for("lexical-first")
        self.assertEqual(
            probe.adjudicate_outcomes(
                lexical_outcomes, lexical_selections
            )["classification"],
            "PARENT_OR_SURFACE_HEURISTIC_SUPPORTED",
        )

    def test_12_preregistration_reconstructs_with_zero_live_state(self) -> None:
        validation = probe.validate_preregistration(REPOSITORY, self.model_path)
        self.assertEqual(validation["status"], "pass")
        self.assertEqual(validation["future_model_generations"], 6)
        self.assertFalse(validation["authority_created"])
        self.assertFalse(validation["authority_consumed"])
        self.assertEqual(validation["model_requests_issued"], 0)
        self.assertFalse(validation["sidecar_launched"])
        self.assertFalse(validation["live_execution_performed"])

    def test_13_future_command_requires_separate_external_authority(self) -> None:
        command = self.artifact["future_live_command_shape"]
        self.assertIn(" run ", command)
        self.assertIn("--external-authority-id <fresh-64-hex>", command)
        self.assertIn("--authorized-commit <published-static-commit>", command)
        paths = probe.state_paths(REPOSITORY)
        self.assertFalse(paths["receipt"].exists())
        self.assertFalse(paths["run_root"].exists())

    def test_14_private_identities_do_not_enter_tracked_design_files(self) -> None:
        tracked_paths = (
            REPOSITORY / probe.PREREGISTRATION_PATH,
            REPOSITORY
            / "scripts/catalytic_kernel_0_balanced_rank_head_v2_three_parent_global_invariant_probe.py",
            REPOSITORY
            / "scripts/catalytic_kernel_0_balanced_rank_head_v2_three_parent_global_invariant_probe_scientific.py",
            Path(__file__),
            REPOSITORY / "TASKS.md",
            REPOSITORY / "ROADMAP.md",
            REPOSITORY / "lab/GOAL.md",
            REPOSITORY / "lab/CHECKPOINT.md",
            REPOSITORY / "lab/EVALUATOR.json",
            REPOSITORY / "lab/EVALUATOR.lock.json",
        )
        haystack = b"\n".join(path.read_bytes() for path in tracked_paths)
        aliases = set()
        for geometry in self.geometries.values():
            aliases.update(geometry["parent-a"])
            aliases.update(geometry["parent-b"])
            aliases.update(geometry["parent-c"])
        for alias in aliases:
            self.assertNotIn(json.dumps(alias).encode("ascii"), haystack)
        self.assertNotIn(self.root, haystack)


if __name__ == "__main__":
    unittest.main(verbosity=2)
