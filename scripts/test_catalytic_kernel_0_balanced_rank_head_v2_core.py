#!/usr/bin/env python3

from __future__ import annotations

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
        self.assertFalse(extraction["model_request_present"])
        self.assertEqual(contract["static_boundary"]["run_reservations"], [])

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

    def test_tampered_receipt_is_rejected(self) -> None:
        receipt = rank_head.build_deterministic_extraction_receipt(
            self.runtime,
            self.winner_transform,
        )
        tampered = dict(receipt)
        tampered["selected_rank"] = 1
        with self.assertRaisesRegex(
            rank_head.RankHeadDesignError,
            "selection law changed",
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
            (temp_root / "lab").mkdir()
            for relative in (
                rank_head.ADJUDICATION_PATH,
                rank_head.COUNTERFACTUAL_PATH,
                rank_head.FROZEN_RUNTIME_PATH,
                rank_head.BINDING_1_PREREGISTRATION_PATH,
                rank_head.BINDING_2_PREREGISTRATION_PATH,
            ):
                source = repository / relative
                target = temp_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            scripts = temp_root / "scripts"
            scripts.mkdir(exist_ok=True)
            module_path = scripts / "catalytic_kernel_0_balanced_rank_head_v2.py"
            test_path = scripts / "test_catalytic_kernel_0_balanced_rank_head_v2.py"
            module_path.write_bytes(Path(rank_head.__file__).read_bytes())
            test_path.write_bytes(Path(__file__).read_bytes())
            audits = {
                "rank_head_no_smuggle_auditor": "PASS",
                "historical_compatibility_auditor": "PASS",
            }
            verification = {"status": "pass", "live_model_requests": 0}
            document = rank_head.build_preregistration_document(
                repository=temp_root,
                implementation_paths=[
                    "scripts/catalytic_kernel_0_balanced_rank_head_v2.py",
                    "scripts/test_catalytic_kernel_0_balanced_rank_head_v2.py",
                ],
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

    def test_receipt_schema_is_exact_and_metadata_only(self) -> None:
        schema = rank_head.deterministic_extraction_receipt_schema()
        self.assertEqual(
            set(schema["required"]),
            set(rank_head.DETERMINISTIC_RECEIPT_FIELDS),
        )
        self.assertEqual(schema["properties"]["selected_rank"]["const"], 0)
        self.assertEqual(
            schema["properties"][
                "private_mapping_consulted_before_selection"
            ]["const"],
            False,
        )


if __name__ == "__main__":
    unittest.main()
