#!/usr/bin/env python3

from __future__ import annotations

import copy
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2 as rank_head


class RankHeadV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.configuration = balanced.PrivateBindingConfiguration(
            profile_id="rank-head-v2-test-binding",
            preregistration_path="unused.json",
            secret_path="unused.secret",
            creation_receipt_path="unused.creation.json",
            run_modes={"rank-head-v2-test-run": "full-information"},
            domain_separation_identity="rank-head-v2-test-binding",
            protected_starting_sha="0" * 40,
        )
        cls.private = balanced.PrivateBinding.from_secret(
            bytes(range(32)),
            cls.configuration,
        )
        cls.runtime = balanced.BalancedOpaqueRuntime(
            repository=Path("."),
            run_id="rank-head-v2-test-run",
            private=cls.private,
        )
        cls.winner_alias = cls.private.internal_to_alias[
            balanced.EXPECTED_FULL_SUPPORT[0]
        ]
        alternatives = [
            alias for alias in balanced.ALIASES if alias != cls.winner_alias
        ]
        cls.winner_transform = cls.runtime.normalize_transform(
            "refine",
            [cls.winner_alias, *alternatives[:2]],
        )
        cls.nonwinner_transform = cls.runtime.normalize_transform(
            "reconcile",
            [alternatives[0], cls.winner_alias, alternatives[1]],
        )

    @staticmethod
    def _populate_temp_repository(temp_root: Path) -> None:
        repository = Path(__file__).resolve().parents[1]
        (temp_root / "lab").mkdir()
        for relative in (
            rank_head.ADJUDICATION_PATH,
            rank_head.COUNTERFACTUAL_PATH,
            rank_head.FORENSIC_PATH,
            rank_head.FROZEN_RUNTIME_PATH,
            rank_head.BINDING_1_PREREGISTRATION_PATH,
            rank_head.BINDING_2_PREREGISTRATION_PATH,
        ):
            source = repository / relative
            target = temp_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        copied = {
            "scripts/catalytic_kernel_0_balanced_rank_head_v2.py": Path(rank_head.__file__),
            "scripts/catalytic_kernel_0_balanced_rank_head_v2_core.py": Path(rank_head._core.__file__),
            "scripts/test_catalytic_kernel_0_balanced_rank_head_v2.py": Path(__file__).with_name("test_catalytic_kernel_0_balanced_rank_head_v2.py"),
            "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_core.py": Path(__file__).with_name("test_catalytic_kernel_0_balanced_rank_head_v2_core.py"),
        }
        for relative, source in copied.items():
            target = temp_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())

    def test_contract_has_six_logical_stages_and_five_model_requests(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        contract = rank_head.build_design_contract(repository)
        mechanism = contract["frozen_mechanism"]
        extraction = contract["extraction_contract"]
        self.assertEqual(mechanism["logical_stages"], list(rank_head.LOGICAL_STAGES))
        self.assertEqual(
            mechanism["model_request_stages"],
            list(rank_head.MODEL_REQUEST_STAGES),
        )
        self.assertEqual(mechanism["model_request_count"], 5)
        self.assertNotIn("extract", mechanism["model_request_stages"])
        self.assertEqual(mechanism["task_suite_sha256"], balanced.EXPECTED_SUITE_SHA256)
        self.assertEqual(mechanism["task_index"], 2)
        self.assertEqual(mechanism["task_id"], "cs1-task-03")
        self.assertEqual(mechanism["parent_order"], ["parent-0", "parent-1"])
        self.assertEqual(
            mechanism["allowed_transform_operators"],
            sorted(balanced.ALLOWED_OPERATORS),
        )
        self.assertEqual(mechanism["physical_slots"], 1)
        self.assertEqual(mechanism["sidecar_epochs"], 1)
        self.assertFalse(extraction["model_request_present"])
        self.assertEqual(extraction["selection_order"], list(rank_head.SELECTION_ORDER))
        self.assertEqual(
            contract["published_adjudication"]["forensic_path"],
            rank_head.FORENSIC_PATH,
        )
        self.assertEqual(
            contract["published_adjudication"]["selected_lane"],
            rank_head.SELECTED_LANE,
        )
        for key in (
            "selection_uses_private_identity",
            "selection_uses_private_score",
            "selection_uses_support_intersection",
            "selection_uses_branch_identities",
            "selection_uses_mode",
            "selection_uses_binding_identity",
            "selection_uses_expected_classification",
            "selection_uses_historical_result",
            "selection_uses_counterfactual_result",
        ):
            self.assertFalse(contract["no_smuggle_invariants"][key])
        self.assertEqual(contract["static_boundary"]["run_reservations"], [])

    def test_v2_carrier_removes_model_authored_extraction(self) -> None:
        carrier = rank_head.build_v2_carrier()
        root = __import__("json").loads(carrier["carrier_root"])
        self.assertEqual(carrier["carrier_id"], rank_head.V2_CARRIER_ID)
        self.assertNotEqual(carrier["carrier_id"], balanced.CARRIER_ID)
        self.assertNotEqual(
            carrier["carrier_root_sha256"],
            balanced.build_carrier()["carrier_root_sha256"],
        )
        self.assertTrue(rank_head.v2_carrier_is_pristine(carrier))
        self.assertEqual(root["candidate_aliases"], list(balanced.ALIASES))
        self.assertEqual(root["candidate_aliases"], [f"K{index:02d}" for index in range(64)])
        self.assertEqual(
            root["task_semantics"],
            dict(
                balanced.build_frozen_task_suite()
                .tasks[balanced.TASK_INDEX]
                .public_projection()["semantics"]
            ),
        )
        self.assertEqual(
            set(root["response_schemas"]),
            set(rank_head.MODEL_REQUEST_STAGES),
        )
        self.assertNotIn("extract", root["response_schemas"])
        self.assertEqual(
            root["kernel_instructions"]["cycle"],
            list(rank_head.LOGICAL_STAGES),
        )
        self.assertFalse(
            root["kernel_instructions"]["extraction_contract"][
                "model_request_present"
            ]
        )
        instructions = root["kernel_instructions"]
        self.assertEqual(instructions["parent_order"], ["parent-0", "parent-1"])
        self.assertEqual(
            instructions["allowed_transform_operators"],
            sorted(balanced.ALLOWED_OPERATORS),
        )
        self.assertEqual(
            instructions["future_runtime_law"],
            {"physical_slots": 1, "sidecar_epochs": 1},
        )
        self.assertNotIn("extracted opaque alias", json.dumps(root, sort_keys=True))
        for request_id in rank_head.MODEL_REQUEST_STAGES:
            schema = rank_head.v2_response_schema(request_id)
            if request_id in {"borrow", "restore"}:
                self.assertEqual(
                    schema["properties"]["carrier_id"]["const"],
                    rank_head.V2_CARRIER_ID,
                )
            else:
                self.assertEqual(schema, balanced.response_schema(request_id))
        with self.assertRaises(rank_head.RankHeadDesignError):
            rank_head.v2_response_schema("extract")

    def test_rank_head_winner_is_frozen_and_scored_after_selection(self) -> None:
        frozen = rank_head.freeze_rank_head_selection(
            self.runtime,
            self.winner_transform,
        )
        self.assertEqual(frozen.candidate_alias, self.winner_alias)
        receipt = rank_head.build_deterministic_extraction_receipt(
            self.runtime,
            self.winner_transform,
            frozen=frozen,
        )
        self.assertTrue(receipt["selection_frozen_before_private_mapping"])
        self.assertFalse(receipt["private_mapping_consulted_before_selection"])
        self.assertEqual(receipt["selected_rank"], 0)
        self.assertEqual(receipt["stage_id"], rank_head.RECEIPT_STAGE_ID)
        self.assertTrue(
            receipt["controller_private_evaluation"][
                "mapped_to_full_public_support"
            ]
        )
        self.assertEqual(
            receipt["controller_private_evaluation"]["full_public_score"],
            5,
        )

    def test_nonwinner_rank_head_remains_nonwinner(self) -> None:
        receipt = rank_head.build_deterministic_extraction_receipt(
            self.runtime,
            self.nonwinner_transform,
        )
        self.assertFalse(
            receipt["controller_private_evaluation"][
                "mapped_to_full_public_support"
            ]
        )
        self.assertLess(
            receipt["controller_private_evaluation"]["full_public_score"],
            5,
        )

    def test_transform_shape_and_run_bound_commitment_are_verified_before_selection(self) -> None:
        malformed = dict(self.winner_transform)
        malformed["extra"] = True
        with self.assertRaisesRegex(
            balanced.BalancedOpaqueError,
            "field set changed",
        ):
            rank_head.freeze_rank_head_selection(self.runtime, malformed)
        uncommitted = dict(self.winner_transform)
        uncommitted["artifact_commitment"] = "0" * 64
        with self.assertRaisesRegex(
            balanced.BalancedOpaqueError,
            "commitment is invalid",
        ):
            rank_head.freeze_rank_head_selection(self.runtime, uncommitted)

    def test_tampered_receipt_is_rejected(self) -> None:
        receipt = rank_head.build_deterministic_extraction_receipt(
            self.runtime,
            self.winner_transform,
        )
        other_alias = self.winner_transform["ranking"][1]
        cases = {
            "rank": {"selected_rank": 1},
            "candidate-alias": {"candidate_alias": other_alias},
            "ranking-length": {"transform_ranking_length": 2},
            "transform-commitment": {
                "transform_artifact_commitment_consumed": "0" * 64
            },
            "selection-law": {"selection_law": "changed"},
            "selection-frozen-flag": {
                "selection_frozen_before_private_mapping": False
            },
            "private-mapping-flag": {
                "private_mapping_consulted_before_selection": True
            },
            "stage-id": {"stage_id": "changed"},
            "receipt-commitment": {"artifact_commitment": "0" * 64},
        }
        for name, changes in cases.items():
            with self.subTest(name=name):
                tampered = copy.deepcopy(receipt)
                tampered.update(changes)
                with self.assertRaises(rank_head.RankHeadDesignError):
                    rank_head.verify_deterministic_extraction_receipt(
                        self.runtime,
                        tampered,
                        self.winner_transform,
                    )
        tampered = copy.deepcopy(receipt)
        tampered["controller_private_evaluation"]["full_public_score"] = 4
        with self.assertRaisesRegex(
            rank_head.RankHeadDesignError,
            "private evaluation changed",
        ):
            rank_head.verify_deterministic_extraction_receipt(
                self.runtime,
                tampered,
                self.winner_transform,
            )

    def test_preregistration_exact_reconstruction_and_zero_authority(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            temp_root = Path(temporary)
            self._populate_temp_repository(temp_root)
            audits = {
                "rank_head_no_smuggle_auditor": "PASS",
                "historical_compatibility_auditor": "PASS",
            }
            verification = {"status": "pass", "live_model_requests": 0}
            document = rank_head.build_preregistration_document(
                repository=temp_root,
                implementation_paths=list(rank_head.REQUIRED_IMPLEMENTATION_PATHS),
                audit_outcomes=audits,
                static_verification=verification,
            )
            path = rank_head.write_preregistration(temp_root, document)
            projection = rank_head.validate_preregistration(temp_root)
            self.assertEqual(
                projection["relative_path"],
                rank_head.PREREGISTRATION_PATH,
            )
            self.assertEqual(projection["run_ids_reserved"], [])
            self.assertFalse(projection["live_execution_authorized"])
            self.assertTrue(path.is_file())

    def test_incomplete_extra_and_duplicate_implementation_bindings_are_rejected(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        cases = {
            "missing": list(rank_head.REQUIRED_IMPLEMENTATION_PATHS[:-1]),
            "extra": [*rank_head.REQUIRED_IMPLEMENTATION_PATHS, "scripts/extra.py"],
            "duplicate": [
                *rank_head.REQUIRED_IMPLEMENTATION_PATHS,
                rank_head.REQUIRED_IMPLEMENTATION_PATHS[0],
            ],
        }
        for name, paths in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(
                    rank_head.RankHeadDesignError,
                    "exactly the four authorized files",
                ):
                    rank_head.build_preregistration_document(
                        repository=repository,
                        implementation_paths=paths,
                    )

    def test_builder_rejects_changed_audits_and_non_pass_verification(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        with self.assertRaisesRegex(rank_head.RankHeadDesignError, "audit names"):
            rank_head.build_preregistration_document(
                repository=repository,
                implementation_paths=rank_head.REQUIRED_IMPLEMENTATION_PATHS,
                audit_outcomes={"changed": "PASS"},
                static_verification={"status": "pass"},
            )
        with self.assertRaisesRegex(rank_head.RankHeadDesignError, "terminal PASS"):
            rank_head.build_preregistration_document(
                repository=repository,
                implementation_paths=rank_head.REQUIRED_IMPLEMENTATION_PATHS,
                audit_outcomes=rank_head.REQUIRED_AUDITS,
                static_verification={"status": "pending"},
            )

    def test_core_preregistration_surface_is_fail_closed(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        cases = {
            "missing": list(rank_head.REQUIRED_IMPLEMENTATION_PATHS[:-1]),
            "extra": [*rank_head.REQUIRED_IMPLEMENTATION_PATHS, "scripts/extra.py"],
            "duplicate": [
                *rank_head.REQUIRED_IMPLEMENTATION_PATHS,
                rank_head.REQUIRED_IMPLEMENTATION_PATHS[0],
            ],
        }
        for name, paths in cases.items():
            with self.subTest(name=name), self.assertRaisesRegex(
                rank_head.RankHeadDesignError,
                "authoritative rank-head v2 wrapper",
            ):
                rank_head._core.build_preregistration_document(
                    repository=repository,
                    implementation_paths=paths,
                    audit_outcomes=rank_head.REQUIRED_AUDITS,
                    static_verification={"status": "pass"},
                )
        with self.assertRaisesRegex(
            rank_head.RankHeadDesignError,
            "authoritative rank-head v2 wrapper",
        ):
            rank_head._core.validate_preregistration(repository)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(rank_head._core.main(), 1)
        self.assertIn("authoritative", output.getvalue())

    def test_validator_rejects_final_boundary_drift(self) -> None:
        cases = {
            "changed-audit-name": lambda document: document.__setitem__(
                "audits", {"changed": "PASS"}
            ),
            "non-pass-static-verification": lambda document: document.__setitem__(
                "static_verification", {"status": "pending"}
            ),
            "run-reservation": lambda document: document["execution_state"].__setitem__(
                "run_ids_reserved", ["forbidden"]
            ),
            "live-authority": lambda document: document["execution_state"].__setitem__(
                "live_authority_created", True
            ),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                temp_root = Path(temporary)
                self._populate_temp_repository(temp_root)
                document = rank_head.build_preregistration_document(
                    repository=temp_root,
                    implementation_paths=rank_head.REQUIRED_IMPLEMENTATION_PATHS,
                    audit_outcomes=rank_head.REQUIRED_AUDITS,
                    static_verification={"status": "pass"},
                )
                mutate(document)
                rank_head.write_preregistration(temp_root, document)
                with self.assertRaises(rank_head.RankHeadDesignError):
                    rank_head.validate_preregistration(temp_root)

    def test_receipt_schema_is_exact_and_metadata_only(self) -> None:
        schema = rank_head.deterministic_extraction_receipt_schema()
        self.assertEqual(
            set(schema["required"]),
            set(rank_head.DETERMINISTIC_RECEIPT_FIELDS),
        )
        self.assertEqual(schema["properties"]["selected_rank"]["const"], 0)
        self.assertEqual(
            schema["properties"]["stage_id"]["const"],
            rank_head.RECEIPT_STAGE_ID,
        )
        self.assertEqual(
            schema["properties"][
                "private_mapping_consulted_before_selection"
            ]["const"],
            False,
        )


if __name__ == "__main__":
    unittest.main()
