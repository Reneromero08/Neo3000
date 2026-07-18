#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_kernel_0_balanced_rank_head_v2_position_seed_crossover_adjudication as adjudication


def sample_outcomes() -> dict[str, dict[str, object]]:
    outcomes: dict[str, dict[str, object]] = {}
    for presentation in adjudication.crossover.PRESENTATIONS:
        for seed_block in adjudication.crossover.SEED_BLOCKS:
            cell = f"{presentation}-{seed_block}"
            for arm in adjudication.crossover.ARMS:
                recovered = arm == "full-information" or presentation == "P0"
                outcomes[f"{cell}-{arm}"] = {
                    "selected_private_singleton": recovered,
                    "private_public_score": 5 if recovered else 3,
                    "private_public_total": 5,
                    "selected_rank": 0,
                    "selection_frozen_before_private_mapping": True,
                }
    return outcomes


class PositionSeedAdjudicationTests(unittest.TestCase):
    def test_exact_matrix_supports_position_conditional_interpretation(self) -> None:
        matrix = adjudication._matrix(sample_outcomes())
        adjudication._require_exact_scientific_pattern(matrix)
        self.assertEqual(len(matrix), 4)
        self.assertEqual(
            adjudication.SUPPORTED_CLAIMS,
            (
                "SINGLETON_PRESENTATION_POSITION_EFFECT_SUPPORTED",
                "PARENT_INFORMATION_DEPENDENCE_IS_SINGLETON_PRESENTATION_POSITION_CONDITIONAL_WITHIN_MATCHED_BINDING",
                "JOINT_PARENT_INFORMATION_OVERCOMES_UNFAVORABLE_SINGLETON_PRESENTATION_POSITION_ACROSS_TWO_FIXED_SEEDS",
            ),
        )

    def test_changed_deletion_outcome_is_rejected(self) -> None:
        outcomes = sample_outcomes()
        outcomes["P1-S1-delete-parent-1"]["selected_private_singleton"] = True
        outcomes["P1-S1-delete-parent-1"]["private_public_score"] = 5
        with self.assertRaisesRegex(
            adjudication.PositionSeedAdjudicationError,
            "position-conditional deletion pattern changed",
        ):
            adjudication._require_exact_scientific_pattern(
                adjudication._matrix(outcomes)
            )

    def test_invalid_full_information_baseline_is_rejected(self) -> None:
        outcomes = sample_outcomes()
        outcomes["P0-S0-full-information"]["private_public_score"] = 3
        with self.assertRaisesRegex(
            adjudication.PositionSeedAdjudicationError,
            "full-information baseline is invalid",
        ):
            adjudication._require_exact_scientific_pattern(
                adjudication._matrix(outcomes)
            )

    def test_locked_claims_preserve_broad_boundary(self) -> None:
        self.assertEqual(
            adjudication.LOCKED_CLAIMS["GENERAL_CATALYTIC_INFERENCE"],
            "LOCKED",
        )
        self.assertEqual(
            adjudication.LOCKED_CLAIMS["POSITION_INDEPENDENT_BILATERAL_DEPENDENCE"],
            "LOCKED",
        )
        self.assertFalse(adjudication.LOCKED_CLAIMS["automatic_promotion"])

    def test_disclosure_boundary_rejects_private_fields(self) -> None:
        for field in (
            "raw_authority_id",
            "private_root",
            "ranking",
            "alias_map",
            "run_key",
            "cross_binding_correspondence",
        ):
            with self.subTest(field=field), self.assertRaises(
                (adjudication.PositionSeedAdjudicationError,
                 adjudication.crossover.PositionSeedCrossoverError)
            ):
                adjudication.validate_disclosure_boundary({field: "hidden"})

    def test_publication_requires_one_canonical_exact_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / "lab").mkdir()
            artifact = {"schema_version": 1, "safe": True}
            record = {"id": adjudication.RECORD_ID, "safe": True}
            (repository / adjudication.ARTIFACT_PATH).write_bytes(
                adjudication.canonical_json_bytes(artifact) + b"\n"
            )
            (repository / adjudication.RESULTS_PATH).write_text(
                adjudication.canonical_json_text(record) + "\n",
                encoding="utf-8",
            )
            original_render_artifact = adjudication.render_adjudication
            original_render_record = adjudication.render_record
            try:
                adjudication.render_adjudication = lambda _repository: copy.deepcopy(artifact)
                adjudication.render_record = lambda _repository, _artifact=None: copy.deepcopy(record)
                result = adjudication.validate_publication(repository)
            finally:
                adjudication.render_adjudication = original_render_artifact
                adjudication.render_record = original_render_record
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["ledger_line"], 1)

    def test_duplicate_record_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / "lab").mkdir()
            artifact = {"schema_version": 1, "safe": True}
            record = {"id": adjudication.RECORD_ID, "safe": True}
            (repository / adjudication.ARTIFACT_PATH).write_bytes(
                adjudication.canonical_json_bytes(artifact) + b"\n"
            )
            line = adjudication.canonical_json_text(record)
            (repository / adjudication.RESULTS_PATH).write_text(
                line + "\n" + line + "\n",
                encoding="utf-8",
            )
            original_render_artifact = adjudication.render_adjudication
            original_render_record = adjudication.render_record
            try:
                adjudication.render_adjudication = lambda _repository: copy.deepcopy(artifact)
                adjudication.render_record = lambda _repository, _artifact=None: copy.deepcopy(record)
                with self.assertRaisesRegex(
                    adjudication.PositionSeedAdjudicationError,
                    "exactly one adjudication record",
                ):
                    adjudication.validate_publication(repository)
            finally:
                adjudication.render_adjudication = original_render_artifact
                adjudication.render_record = original_render_record


if __name__ == "__main__":
    unittest.main()
