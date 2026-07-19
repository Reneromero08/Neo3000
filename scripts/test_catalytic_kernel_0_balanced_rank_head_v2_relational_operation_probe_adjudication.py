#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_kernel_0_balanced_rank_head_v2_relational_operation_probe_adjudication as adjudication


def sample_outcomes() -> list[dict[str, object]]:
    outcomes = []
    for request_id in adjudication.probe.REQUEST_IDS:
        geometry_id, order = request_id.split("-")
        outcomes.append(
            {
                "request_id": request_id,
                "geometry_id": geometry_id,
                "presentation_order": order,
                "transform_operator": "reconcile",
                "selected_rank": 0,
                "selection_frozen_before_private_mapping": True,
                "private_mapping_consulted_before_selection": False,
                "selected_from_parent_union": True,
                "mechanism_matches": dict(adjudication.EXPECTED_MECHANISM_MATCHES),
            }
        )
    return outcomes


def sample_adjudication() -> dict[str, object]:
    return {
        "classification": adjudication.SUPPORTED_CLASSIFICATION,
        "mechanism_matches_all_four": dict(adjudication.EXPECTED_MECHANISM_MATCHES),
        "semantic_selection_order_invariant_by_geometry": dict(
            adjudication.EXPECTED_ORDER_INVARIANCE
        ),
        "transferred_across_two_matched_geometries": True,
        "formal_algebra_claimed": False,
        "scope": "two-matched-geometries-one-private-binding-one-fixed-seed-transform-only",
    }


class RelationalOperationAdjudicationTests(unittest.TestCase):
    def test_exact_pattern_supports_bounded_intersection_like_interpretation(self) -> None:
        adjudication._require_exact_scientific_pattern(
            sample_outcomes(), sample_adjudication()
        )
        self.assertEqual(
            adjudication.SCIENTIFIC_INTERPRETATION,
            "JOINT_PARENT_TRANSFORM_SELECTS_THE_UNIQUE_RELATIONAL_INVARIANT_"
            "INDEPENDENT_OF_PARENT_PRESENTATION_ORDER_ACROSS_TWO_MATCHED_PRIVATE_GEOMETRIES",
        )

    def test_changed_competing_mechanism_is_rejected(self) -> None:
        outcomes = sample_outcomes()
        outcomes[2]["mechanism_matches"]["lexical-first"] = True
        with self.assertRaisesRegex(
            adjudication.RelationalOperationAdjudicationError,
            "frozen mechanism comparison changed",
        ):
            adjudication._require_exact_scientific_pattern(
                outcomes, sample_adjudication()
            )

    def test_lost_order_invariance_is_rejected(self) -> None:
        changed = sample_adjudication()
        changed["semantic_selection_order_invariant_by_geometry"]["G1"] = False
        with self.assertRaisesRegex(
            adjudication.RelationalOperationAdjudicationError,
            "order invariance changed",
        ):
            adjudication._require_exact_scientific_pattern(sample_outcomes(), changed)

    def test_rank_or_private_freeze_drift_is_rejected(self) -> None:
        outcomes = sample_outcomes()
        outcomes[0]["selected_rank"] = 1
        with self.assertRaisesRegex(
            adjudication.RelationalOperationAdjudicationError,
            "rank-zero transform law changed",
        ):
            adjudication._require_exact_scientific_pattern(
                outcomes, sample_adjudication()
            )

    def test_locked_claims_preserve_broad_boundary(self) -> None:
        for claim in (
            "FORMAL_ALGEBRA",
            "ASSOCIATIVITY",
            "REPLICATION_ACROSS_SEEDS",
            "REPLICATION_ACROSS_BINDINGS",
            "GENERAL_CATALYTIC_INFERENCE",
            "TASK_ADVANTAGE",
        ):
            self.assertEqual(adjudication.LOCKED_CLAIMS[claim], "LOCKED")
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
                (
                    adjudication.RelationalOperationAdjudicationError,
                    adjudication.probe.RelationalOperationProbeError,
                )
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
            original_artifact = adjudication.render_adjudication
            original_record = adjudication.render_record
            try:
                adjudication.render_adjudication = lambda _repository: copy.deepcopy(
                    artifact
                )
                adjudication.render_record = (
                    lambda _repository, _artifact=None: copy.deepcopy(record)
                )
                result = adjudication.validate_publication(repository)
            finally:
                adjudication.render_adjudication = original_artifact
                adjudication.render_record = original_record
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
            original_artifact = adjudication.render_adjudication
            original_record = adjudication.render_record
            try:
                adjudication.render_adjudication = lambda _repository: copy.deepcopy(
                    artifact
                )
                adjudication.render_record = (
                    lambda _repository, _artifact=None: copy.deepcopy(record)
                )
                with self.assertRaisesRegex(
                    adjudication.RelationalOperationAdjudicationError,
                    "exactly one adjudication record",
                ):
                    adjudication.validate_publication(repository)
            finally:
                adjudication.render_adjudication = original_artifact
                adjudication.render_record = original_record


if __name__ == "__main__":
    unittest.main()
