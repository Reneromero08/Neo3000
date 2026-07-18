#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import catalytic_kernel_0_balanced_parent_dependence_cross_binding_asymmetry_audit as audit


REPOSITORY = Path(__file__).resolve().parent.parent
MODEL_ENV = "NEO3000_TOKENIZER_MODEL"


class CrossBindingAsymmetryAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        model = os.environ.get(MODEL_ENV)
        if not model:
            raise unittest.SkipTest(
                f"{MODEL_ENV} is required for the offline GGUF tokenizer reconstruction"
            )
        cls.model = Path(model)
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(audit.__file__)),
                "render",
                "--repository",
                str(REPOSITORY),
                "--model",
                str(cls.model),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        cls.rendered = json.loads(completed.stdout)

    def test_original_forensic_truth_is_preserved(self) -> None:
        binding_2 = self.rendered["source_evidence"]["binding_2"]
        self.assertEqual(binding_2["original_terminal_status"], "INCONCLUSIVE")
        self.assertEqual(
            binding_2["original_terminal_reason"],
            "durable-finalization-custody-gate-failed",
        )
        self.assertEqual(
            binding_2["archive_sha256"],
            "7BDA5B9EF4CEAA8EEB4157DF2D47644554F11551EB10DF354B4DD59F55693E1C",
        )
        self.assertEqual(
            binding_2["forensic_artifact_sha256"],
            "110DAE908E4C1F01747C2CBBEA9F3A34BB2ACA61397D55B0648D82453A3DD975",
        )
        self.assertFalse(binding_2["execution_evidence_rewritten"])

    def test_cross_binding_claim_is_narrowed_to_shared_endpoint(self) -> None:
        correction = self.rendered["claim_correction"]
        self.assertEqual(
            correction["supported_claim"],
            audit.CORRECTED_SUPPORTED_CLAIM,
        )
        self.assertEqual(correction["qualification"], audit.CORRECTED_QUALIFICATION)
        self.assertTrue(correction["prior_wording_narrowed"])
        self.assertFalse(correction["pure_binding_only_replication_supported"])

    def test_private_diagnostics_reconstruct_expected_positions(self) -> None:
        bindings = {
            item["binding"]: item
            for item in self.rendered["bounded_private_diagnostics"]
        }
        b1 = {item["parent_role"]: item for item in bindings["binding-1"]["parents"]}
        b2 = {item["parent_role"]: item for item in bindings["binding-2"]["parents"]}
        self.assertEqual(
            [b1["parent-0"]["private_singleton_transform_serialization_ordinal_1_based"],
             b1["parent-1"]["private_singleton_transform_serialization_ordinal_1_based"]],
            [3, 4],
        )
        self.assertEqual(
            [b2["parent-0"]["private_singleton_transform_serialization_ordinal_1_based"],
             b2["parent-1"]["private_singleton_transform_serialization_ordinal_1_based"]],
            [1, 1],
        )
        self.assertEqual(
            [b1["parent-0"]["private_singleton_global_lexical_ordinal_1_based"],
             b2["parent-0"]["private_singleton_global_lexical_ordinal_1_based"]],
            [43, 2],
        )

    def test_shared_rank_head_outcomes_are_exact(self) -> None:
        records = {
            (binding["binding"], item["parent_role"]): item
            for binding in self.rendered["bounded_private_diagnostics"]
            for item in binding["parents"]
        }
        self.assertEqual(records[("binding-1", "parent-1")]["rank_zero_private_public_score"], 3)
        self.assertEqual(records[("binding-1", "parent-0")]["rank_zero_private_public_score"], 3)
        self.assertEqual(records[("binding-2", "parent-1")]["rank_zero_private_public_score"], 3)
        self.assertEqual(records[("binding-2", "parent-0")]["rank_zero_private_public_score"], 5)
        self.assertFalse(records[("binding-2", "parent-1")]["rank_zero_selected_private_singleton"])
        self.assertTrue(records[("binding-2", "parent-0")]["rank_zero_selected_private_singleton"])

    def test_token_and_receipt_shape_diagnostics_are_bounded(self) -> None:
        tokenizer = self.rendered["source_evidence"]["tokenizer"]
        self.assertTrue(tokenizer["opaque_symbol_token_id_lengths_all_equal"])
        self.assertEqual(tokenizer["opaque_symbol_token_id_length_min"], 3)
        self.assertEqual(tokenizer["opaque_symbol_token_id_length_max"], 3)
        for binding in self.rendered["bounded_private_diagnostics"]:
            for item in binding["parents"]:
                self.assertEqual(item["commitment_receipt_serialized_bytes"], 189)
                self.assertEqual(item["complete_retained_parent_serialized_bytes"], 265)
                self.assertEqual(len(item["commitment_receipt_field_shape"]), 4)

    def test_mechanistic_adjudication_does_not_force_one_cause(self) -> None:
        explanations = self.rendered["mechanistic_adjudication"]["explanations"]
        self.assertEqual(
            explanations["SINGLETON_PRESENTATION_POSITION_CONFOUND_PLAUSIBLE"],
            "PLAUSIBLE_AND_DIAGNOSTICALLY_ALIGNED",
        )
        self.assertEqual(
            explanations["TRUE_DIRECTIONAL_PARENT_ASYMMETRY_PLAUSIBLE"],
            "PLAUSIBLE",
        )
        self.assertTrue(explanations["INSUFFICIENT_EVIDENCE_TO_DISTINGUISH"])

    def test_minimum_follow_on_is_two_by_two_by_three(self) -> None:
        design = self.rendered["minimum_follow_on"]
        self.assertFalse(design["one_new_binding_scientifically_adequate"])
        self.assertEqual(design["fresh_private_binding_count"], 2)
        self.assertEqual(len(design["seed_blocks"]), 2)
        self.assertEqual(len(design["arms_per_binding_seed_cell"]), 3)
        self.assertEqual(design["future_model_generations"], 12)
        self.assertFalse(design["implementation_in_this_operation"])
        self.assertFalse(design["authority_created_or_consumed"])

    def test_tracked_artifact_equals_fresh_private_reconstruction(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(audit.__file__)),
                "validate",
                "--repository",
                str(REPOSITORY),
                "--model",
                str(self.model),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(completed.stdout)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["supported_claim"], audit.CORRECTED_SUPPORTED_CLAIM)
        self.assertEqual(report["future_model_generations"], 12)
        self.assertEqual(report["model_generations_during_audit"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
