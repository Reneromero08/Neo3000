#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import catalytic_kernel_0_balanced_parent_dependence_cross_binding_asymmetry_audit as asymmetry
import catalytic_kernel_0_balanced_rank_head_v2_position_seed_crossover as panel
import catalytic_kernel_0_balanced_rank_head_v2_position_seed_crossover_scientific as scientific


REPOSITORY = Path(__file__).resolve().parent.parent
MODEL_ENV = "NEO3000_TOKENIZER_MODEL"


class PositionSeedCrossoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        model = os.environ.get(MODEL_ENV)
        if not model:
            raise unittest.SkipTest(
                f"{MODEL_ENV} is required for the offline tokenizer reconstruction"
            )
        cls.model_path = Path(model)
        cls.tokenizer = asymmetry.OfflineTokenizer(cls.model_path)
        cls.root, cls.private = panel._load_private(REPOSITORY)
        cls.selection = panel.validate_private_binding(REPOSITORY, cls.model_path)
        cls.eligibility = panel._candidate_eligibility(cls.root, cls.tokenizer)
        cls.payloads = {
            request_id: panel.build_request(cls.root, cls.private, request_id)
            for request_id in panel.REQUEST_IDS
        }
        cls.artifact_path = REPOSITORY / panel.PREREGISTRATION_PATH
        cls.artifact = json.loads(cls.artifact_path.read_bytes())

    def test_01_one_fresh_binding_is_first_match_before_outcomes(self) -> None:
        self.assertEqual(self.selection["selected_counter"], 49)
        self.assertEqual(self.selection["attempt_count"], 50)
        self.assertTrue(self.selection["first_match_verified"])
        self.assertEqual(self.selection["model_outputs_inspected"], 0)
        self.assertFalse(self.selection["authority_created"])
        self.assertIn(
            self.eligibility["private_singleton_global_lexical_ordinal_1_based"],
            (32, 33),
        )

    def test_02_selection_root_is_counter_derived_and_every_prior_candidate_fails(self) -> None:
        seed = (REPOSITORY / panel.SELECTION_SEED_PATH).read_bytes()
        counter = self.selection["selected_counter"]
        self.assertEqual(panel._candidate_root(seed, counter), self.root)
        for prior in range(counter):
            self.assertFalse(
                panel._candidate_eligibility(
                    panel._candidate_root(seed, prior), self.tokenizer
                )["eligible"]
            )

    def test_03_failure_to_match_stops_before_authority(self) -> None:
        with mock.patch.object(
            panel,
            "_candidate_eligibility",
            return_value={"eligible": False},
        ):
            with self.assertRaisesRegex(
                panel.PositionSeedCrossoverError,
                "stop before authority",
            ):
                panel.select_first_eligible(
                    b"x" * 32,
                    self.tokenizer,
                    attempt_ceiling=3,
                )

    def test_04_p0_p1_support_sets_and_semantic_commitments_are_identical(self) -> None:
        for role in ("parent-0", "parent-1"):
            p0 = panel._presentation_projection(
                self.root, self.private, role, "P0"
            )
            p1 = panel._presentation_projection(
                self.root, self.private, role, "P1"
            )
            self.assertEqual(set(p0["support_aliases"]), set(p1["support_aliases"]))
            self.assertEqual(
                p0["semantic_set_commitment"],
                p1["semantic_set_commitment"],
            )
            self.assertEqual(set(p0), set(p1))

    def test_05_p0_p1_equal_bytes_and_token_lengths_only_order_differs(self) -> None:
        for role in ("parent-0", "parent-1"):
            p0 = panel._presentation_projection(
                self.root, self.private, role, "P0"
            )
            p1 = panel._presentation_projection(
                self.root, self.private, role, "P1"
            )
            p0_tokens = panel._token_sequence(self.tokenizer, p0)
            p1_tokens = panel._token_sequence(self.tokenizer, p1)
            self.assertEqual(
                p0_tokens["serialized_bytes"], p1_tokens["serialized_bytes"]
            )
            self.assertEqual(p0_tokens["token_ids"], p1_tokens["token_ids"])
            self.assertEqual(
                {key: value for key, value in p0.items() if key != "support_aliases"},
                {key: value for key, value in p1.items() if key != "support_aliases"},
            )
            self.assertEqual(p0["support_aliases"][0], p1["support_aliases"][-1])
            self.assertNotEqual(p0["support_aliases"], p1["support_aliases"])

    def test_06_projection_token_sequences_are_constant_in_every_relevant_cell(self) -> None:
        for presentation in panel.PRESENTATIONS:
            for role, parent_index, complete_arm in (
                ("parent-0", 0, "delete-parent-1"),
                ("parent-1", 1, "delete-parent-0"),
            ):
                reference = panel._presentation_projection(
                    self.root, self.private, role, presentation
                )
                for seed_block in panel.SEED_BLOCKS:
                    full = panel.build_assignment(
                        self.root,
                        self.private,
                        f"{presentation}-{seed_block}-full-information",
                    )["parent_artifacts"][parent_index]
                    retained = panel.build_assignment(
                        self.root,
                        self.private,
                        f"{presentation}-{seed_block}-{complete_arm}",
                    )["parent_artifacts"][parent_index]
                    self.assertEqual(full, reference)
                    self.assertEqual(retained, reference)

    def test_07_deletion_receipts_are_byte_and_token_identical_across_cells(self) -> None:
        for role in ("parent-0", "parent-1"):
            receipt = panel._deletion_receipt(self.root, self.private, role)
            reference_bytes = panel.canonical_json_bytes(receipt)
            reference_tokens = self.tokenizer.ids(reference_bytes.decode("utf-8"))
            arm = "delete-parent-0" if role == "parent-0" else "delete-parent-1"
            parent_index = 0 if role == "parent-0" else 1
            for presentation in panel.PRESENTATIONS:
                for seed_block in panel.SEED_BLOCKS:
                    observed = panel.build_assignment(
                        self.root,
                        self.private,
                        f"{presentation}-{seed_block}-{arm}",
                    )["parent_artifacts"][parent_index]
                    self.assertEqual(panel.canonical_json_bytes(observed), reference_bytes)
                    self.assertEqual(
                        self.tokenizer.ids(panel.canonical_json_text(observed)),
                        reference_tokens,
                    )

    def test_08_model_visible_labels_do_not_reveal_private_condition(self) -> None:
        forbidden = (
            "singleton first",
            "singleton last",
            "low position",
            "high position",
            "target",
            "correct",
            "private winner",
        )
        for payload in self.payloads.values():
            text = payload["messages"][1]["content"].lower()
            self.assertFalse(any(item in text for item in forbidden))
            self.assertNotIn("P0", text)
            self.assertNotIn("P1", text)

    def test_09_each_cell_uses_exact_seed_for_all_three_arms(self) -> None:
        for presentation in panel.PRESENTATIONS:
            for seed_block, seed in panel.SEED_BLOCKS.items():
                observed = {
                    self.payloads[f"{presentation}-{seed_block}-{arm}"]["seed"]
                    for arm in panel.ARMS
                }
                self.assertEqual(observed, {seed})

    def test_10_exactly_twelve_unique_transform_only_requests_exist(self) -> None:
        hashes = {
            request_id: panel.json_sha256(payload)
            for request_id, payload in self.payloads.items()
        }
        self.assertEqual(set(hashes), set(panel.REQUEST_IDS))
        self.assertEqual(len(hashes), 12)
        self.assertEqual(len(set(hashes.values())), 12)
        for payload in self.payloads.values():
            assignment = json.loads(payload["messages"][1]["content"])
            self.assertEqual(assignment["stage"], "transform")
            self.assertNotIn("borrow", assignment)
            self.assertNotIn("extract", assignment)
            self.assertNotIn("restore", assignment)

    def test_11_requests_are_self_contained_and_order_independent(self) -> None:
        rebuilt = {
            request_id: panel.build_request(self.root, self.private, request_id)
            for request_id in reversed(panel.REQUEST_IDS)
        }
        self.assertEqual(rebuilt, self.payloads)
        for payload in self.payloads.values():
            text = payload["messages"][1]["content"].lower()
            self.assertNotIn("previous response", text)
            self.assertNotIn("prior ranking", text)
            self.assertNotIn("prior score", text)

    def test_12_execution_order_counterbalances_presentation_seed_and_arm(self) -> None:
        self.assertEqual(len(panel.EXECUTION_ORDER), 12)
        self.assertEqual(set(panel.EXECUTION_ORDER), set(panel.REQUEST_IDS))
        presentations = [item.split("-", 1)[0] for item in panel.EXECUTION_ORDER]
        seeds = [item.split("-", 2)[1] for item in panel.EXECUTION_ORDER]
        self.assertEqual(presentations.count("P0"), 6)
        self.assertEqual(presentations.count("P1"), 6)
        self.assertEqual(seeds.count("S0"), 6)
        self.assertEqual(seeds.count("S1"), 6)
        self.assertGreater(len(set(presentations[:4])), 1)
        self.assertGreater(len(set(seeds[:4])), 1)
        for cell in panel.CELLS:
            full_index = panel.EXECUTION_ORDER.index(f"{cell}-full-information")
            self.assertLess(
                full_index,
                panel.EXECUTION_ORDER.index(f"{cell}-delete-parent-0"),
            )
            self.assertLess(
                full_index,
                panel.EXECUTION_ORDER.index(f"{cell}-delete-parent-1"),
            )

    def test_13_duplicate_generation_is_rejected_per_cell_arm(self) -> None:
        key = b"j" * 32
        with tempfile.TemporaryDirectory() as temporary:
            journal = Path(temporary) / "journal.jsonl"
            panel.append_journal_event(
                journal, key, "authority-consumed", facts={"synthetic": True}
            )
            first = panel.EXECUTION_ORDER[0]
            panel.append_journal_event(
                journal,
                key,
                "request-started",
                request_id=first,
                facts={"model_request_sha256": "A" * 64},
            )
            with self.assertRaisesRegex(
                panel.PositionSeedCrossoverError,
                "duplicate or out-of-order",
            ):
                panel.append_journal_event(
                    journal,
                    key,
                    "request-started",
                    request_id=first,
                    facts={"model_request_sha256": "A" * 64},
                )

    def test_14_started_without_capture_becomes_inconclusive_and_never_restarts(self) -> None:
        key = b"r" * 32
        request_id = panel.EXECUTION_ORDER[0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = {
                "journal": root / "journal.jsonl",
                f"capture-{request_id}": root / "capture.json",
            }
            panel.append_journal_event(
                paths["journal"], key, "authority-consumed", facts={}
            )
            panel.append_journal_event(
                paths["journal"],
                key,
                "request-started",
                request_id=request_id,
                facts={"model_request_sha256": "B" * 64},
            )
            panel._recover_or_mark_started_request(
                paths, key, request_id, "B" * 64
            )
            events = panel.read_journal(paths["journal"], key)
            self.assertEqual(
                panel._journal_counts(events)[("request-inconclusive", request_id)],
                1,
            )
            panel._recover_or_mark_started_request(
                paths, key, request_id, "B" * 64
            )
            self.assertEqual(panel.read_journal(paths["journal"], key), events)

    def test_15_authenticated_capture_replays_without_model_contact(self) -> None:
        execution = SimpleNamespace(
            **{name: None for name in scientific.CAPTURE_EXECUTION_FIELDS}
        )
        execution.content = '{"operator":"refine","ranking":["K00"]}'
        key = b"c" * 32
        request_id = panel.REQUEST_IDS[0]
        request_sha = panel.json_sha256(self.payloads[request_id])
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "capture.json"
            capture = scientific.capture_execution(
                path,
                experiment_key=key,
                request_id=request_id,
                model_request_sha256=request_sha,
                execution=execution,
                raw_response_bytes=b"data: synthetic\n\n",
            )
            replay = scientific.replay_capture(capture)
            self.assertEqual(replay.content, execution.content)
            self.assertTrue(capture["captured_before_parsing"])

    def test_16_controller_repairs_cannot_mutate_science_or_consumption(self) -> None:
        passed = panel.validate_controller_repair_policy(
            changed_paths=[
                "scripts/catalytic_kernel_0_balanced_rank_head_v2_position_seed_crossover.py"
            ],
            repair_commit_count=1,
            frozen_scientific_changed=False,
            request_hashes_changed=False,
            consumption_reset=False,
        )
        self.assertTrue(passed["frozen_scientific_preserved"])
        for kwargs in (
            {"frozen_scientific_changed": True},
            {"request_hashes_changed": True},
            {"consumption_reset": True},
        ):
            values = {
                "changed_paths": [
                    "scripts/catalytic_kernel_0_balanced_rank_head_v2_position_seed_crossover.py"
                ],
                "repair_commit_count": 1,
                "frozen_scientific_changed": False,
                "request_hashes_changed": False,
                "consumption_reset": False,
                **kwargs,
            }
            with self.assertRaises(panel.PositionSeedCrossoverError):
                panel.validate_controller_repair_policy(**values)

    def test_17_scientific_decision_law_requires_valid_full_baseline(self) -> None:
        outcomes = {}
        for request_id in panel.REQUEST_IDS:
            presentation, seed_block, arm = panel._request_parts(request_id)
            selected = arm != "delete-parent-0"
            score = 5 if selected else 3
            outcomes[request_id] = {
                "request_id": request_id,
                "cell_id": f"{presentation}-{seed_block}",
                "presentation": presentation,
                "seed_block": seed_block,
                "arm": arm,
                "selected_private_singleton": selected,
                "private_public_score": score,
                "private_public_total": 5,
                "selection_frozen_before_private_mapping": True,
            }
        adjudication = panel.adjudicate_outcomes(outcomes)
        self.assertIn(
            "PARENT_DIRECTIONAL_ASYMMETRY_STRENGTHENED_WITHIN_MATCHED_BINDING",
            adjudication["supported_panel_classifications"],
        )
        outcomes["P0-S0-full-information"]["private_public_score"] = 3
        invalid = panel.adjudicate_outcomes(outcomes)
        self.assertFalse(invalid["all_full_information_baselines_valid"])
        self.assertEqual(
            invalid["cells"]["P0-S0"]["Parent-A"]["classification"],
            "INCONCLUSIVE",
        )

    def test_18_presentation_and_seed_decision_laws_are_exact(self) -> None:
        outcomes = {}
        for request_id in panel.REQUEST_IDS:
            presentation, seed_block, arm = panel._request_parts(request_id)
            if arm == "full-information":
                selected = True
            elif arm == "delete-parent-0":
                selected = False
            else:
                selected = presentation == "P1"
            outcomes[request_id] = {
                "request_id": request_id,
                "cell_id": f"{presentation}-{seed_block}",
                "presentation": presentation,
                "seed_block": seed_block,
                "arm": arm,
                "selected_private_singleton": selected,
                "private_public_score": 5 if selected else 3,
                "private_public_total": 5,
                "selection_frozen_before_private_mapping": True,
            }
        adjudication = panel.adjudicate_outcomes(outcomes)
        self.assertIn(
            "SINGLETON_PRESENTATION_POSITION_EFFECT_SUPPORTED",
            adjudication["supported_panel_classifications"],
        )
        outcomes["P0-S1-delete-parent-0"]["selected_private_singleton"] = True
        outcomes["P0-S1-delete-parent-0"]["private_public_score"] = 5
        seed = panel.adjudicate_outcomes(outcomes)
        self.assertIn(
            "DETERMINISTIC_TRANSFORM_SEED_INTERACTION_SUPPORTED",
            seed["supported_panel_classifications"],
        )

    def test_19_public_preregistration_contains_no_private_smuggle(self) -> None:
        panel._assert_public_no_smuggle(self.artifact)
        raw = self.artifact_path.read_bytes()
        self.assertIsNone(panel.FORBIDDEN_PUBLIC_ID_RE.search(raw))
        self.assertFalse(self.artifact["panel_binding_commitments"]["private_root_published"])
        self.assertFalse(self.artifact["panel_binding_commitments"]["private_mapping_published"])

    def test_20_preregistration_is_zero_execution_and_exactly_reconstructs(self) -> None:
        scripts = (REPOSITORY / "scripts").resolve()
        code = (
            "import sys;"
            "from pathlib import Path;"
            f"sys.path.insert(0, {str(scripts)!r});"
            "import catalytic_kernel_0_balanced_rank_head_v2_position_seed_crossover as panel;"
            f"repository=Path({str(REPOSITORY.resolve())!r});"
            f"model=Path({str(self.model_path.resolve())!r});"
            "print(panel.canonical_json_text("
            "panel.build_preregistration_document(repository, model)))"
        )
        environment = os.environ.copy()
        environment.pop("PYTEST_CURRENT_TEST", None)
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPOSITORY,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        expected = json.loads(completed.stdout)
        self.assertEqual(self.artifact, expected)
        state = self.artifact["execution_state"]
        self.assertEqual(state["model_requests_issued"], 0)
        self.assertFalse(state["authority_created"])
        self.assertFalse(state["authority_consumed"])
        self.assertFalse(state["sidecar_launched"])
        self.assertFalse(state["live_execution_performed"])

    def test_21_frozen_binding_binds_exact_requests_and_generation_ceiling(self) -> None:
        frozen = self.artifact["implementation_binding"][
            "frozen_scientific_execution"
        ]
        self.assertEqual(
            frozen["request_sha256"],
            self.artifact["request_isolation"]["request_sha256"],
        )
        self.assertTrue(frozen["one_generation_maximum_per_cell_arm"])
        self.assertTrue(frozen["twelve_generations_maximum_overall"])

    def test_22_historical_science_and_corrected_claim_are_preserved(self) -> None:
        source = self.artifact["source_custody"]
        self.assertEqual(source["original_terminal_status"], "INCONCLUSIVE")
        self.assertEqual(
            source["forensic_artifact_sha256"], panel.FORENSIC_ARTIFACT_SHA256
        )
        self.assertEqual(
            source["asymmetry_audit_sha256"], panel.ASYMMETRY_ARTIFACT_SHA256
        )
        self.assertEqual(source["supported_claim"], panel.SUPPORTED_CLAIM)
        self.assertEqual(source["qualification"], panel.SUPPORTED_QUALIFICATION)
        self.assertFalse(source["execution_evidence_rewritten"])

    def test_23_finalization_terminal_and_archive_events_are_singletons(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            journal = Path(temporary) / "journal.jsonl"
            key = b"position-seed-journal-test-key"
            panel.append_journal_event(
                journal,
                key,
                "authority-consumed",
                facts={"authorized_commit": "a" * 40},
            )
            panel.append_journal_event(
                journal,
                key,
                "finalization-observed",
                facts={"cleanup": {"passed": True}, "postflight": {"passed": True}},
            )
            with self.assertRaisesRegex(panel.PositionSeedCrossoverError, "exactly once"):
                panel.append_journal_event(
                    journal,
                    key,
                    "finalization-observed",
                    facts={"cleanup": {"passed": True}, "postflight": {"passed": True}},
                )
            panel.append_journal_event(
                journal,
                key,
                "terminal-written",
                facts={"result_sha256": "B" * 64, "closure_sha256": "C" * 64},
            )
            with self.assertRaisesRegex(panel.PositionSeedCrossoverError, "exactly once"):
                panel.append_journal_event(
                    journal,
                    key,
                    "terminal-written",
                    facts={"result_sha256": "B" * 64, "closure_sha256": "C" * 64},
                )
            panel.append_journal_event(
                journal,
                key,
                "archived",
                facts={"archive_sha256": "D" * 64},
            )
            with self.assertRaisesRegex(panel.PositionSeedCrossoverError, "exactly once"):
                panel.append_journal_event(
                    journal,
                    key,
                    "archived",
                    facts={"archive_sha256": "D" * 64},
                )

    def test_24_existing_content_addressed_archive_is_reverified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            body_data = b"terminal evidence\n"
            entries = [
                {
                    "path": "result.json",
                    "byte_size": len(body_data),
                    "sha256": panel.sha256_bytes(body_data),
                }
            ]
            body = {
                "schema_version": 1,
                "design_id": panel.DESIGN_ID,
                "files": entries,
                "content_addressed": True,
            }
            commitment = panel.json_sha256(body)
            archive = repository / panel.ARCHIVE_ROOT / panel.DESIGN_ID / commitment
            archive.mkdir(parents=True)
            (archive / "result.json").write_bytes(body_data)
            (archive / "bundle.json").write_text(
                json.dumps({**body, "bundle_sha256": commitment}),
                encoding="utf-8",
            )
            verified = panel._verify_existing_archive(repository, commitment)
            self.assertTrue(verified["verified"])
            self.assertEqual(verified["bundle_sha256"], commitment)
            (archive / "result.json").write_bytes(b"mutated\n")
            with self.assertRaisesRegex(panel.PositionSeedCrossoverError, "differs"):
                panel._verify_existing_archive(repository, commitment)


if __name__ == "__main__":
    unittest.main(verbosity=2)
