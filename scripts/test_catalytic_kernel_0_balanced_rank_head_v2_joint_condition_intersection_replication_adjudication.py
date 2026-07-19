#!/usr/bin/env python3
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import catalytic_kernel_0_balanced_rank_head_v2_joint_condition_intersection_replication_adjudication as adjudication


def sample_outcomes() -> list[dict[str, object]]:
    return [
        {
            "request_id": request_id,
            "transform_operator": "reconcile",
            "selected_rank": 0,
            "selection_frozen_before_private_mapping": True,
            "private_mapping_consulted_before_selection": False,
            "selected_from_parent_union": True,
            "mechanism_matches": dict(adjudication.EXPECTED_MECHANISM_MATCHES),
        }
        for request_id in adjudication.probe.REQUEST_IDS
    ]


def sample_adjudication() -> dict[str, object]:
    return {
        "classification": adjudication.SUPPORTED_CLASSIFICATION,
        "mechanism_matches_all_four": dict(adjudication.EXPECTED_MECHANISM_MATCHES),
        "semantic_selection_order_invariant_by_geometry": dict(
            adjudication.EXPECTED_ORDER_INVARIANCE
        ),
        "reproduced_under_combined_new_condition": True,
        "seed_invariance_independently_established": False,
        "binding_invariance_independently_established": False,
        "formal_algebra_claimed": False,
        "general_transfer_claimed": False,
    }


class JointConditionAdjudicationTests(unittest.TestCase):
    def test_exact_pattern_supports_only_the_bounded_classification(self) -> None:
        adjudication._require_exact_pattern(sample_outcomes(), sample_adjudication())

    def test_mechanism_drift_is_rejected(self) -> None:
        outcomes = sample_outcomes()
        outcomes[0]["mechanism_matches"]["lexical-first"] = True
        with self.assertRaisesRegex(
            adjudication.JointConditionAdjudicationError,
            "mechanism comparison changed",
        ):
            adjudication._require_exact_pattern(outcomes, sample_adjudication())

    def test_order_invariance_drift_is_rejected(self) -> None:
        changed = sample_adjudication()
        changed["semantic_selection_order_invariant_by_geometry"]["R1"] = False
        with self.assertRaisesRegex(
            adjudication.JointConditionAdjudicationError,
            "classification changed",
        ):
            adjudication._require_exact_pattern(sample_outcomes(), changed)

    def test_separate_seed_and_binding_claims_remain_locked(self) -> None:
        self.assertEqual(adjudication.LOCKED_CLAIMS["SEED_INVARIANCE"], "LOCKED")
        self.assertEqual(adjudication.LOCKED_CLAIMS["BINDING_INVARIANCE"], "LOCKED")
        self.assertEqual(
            adjudication.LOCKED_CLAIMS["GENERAL_CATALYTIC_INFERENCE"], "LOCKED"
        )

    def test_disclosure_boundary_rejects_private_material(self) -> None:
        for field in ("private_root", "raw_authority_id", "ranking", "alias_map"):
            with self.subTest(field=field), self.assertRaises(
                adjudication.probe.JointConditionIntersectionReplicationError
            ):
                adjudication.validate_disclosure_boundary({field: "hidden"})

    def test_publication_requires_one_exact_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / "lab").mkdir()
            artifact = {"schema_version": 1, "safe": True}
            record = {"id": adjudication.RECORD_ID, "safe": True}
            (repository / adjudication.ARTIFACT_PATH).write_bytes(
                adjudication.canonical_json_bytes(artifact) + b"\n"
            )
            (repository / adjudication.RESULTS_PATH).write_text(
                adjudication.canonical_json_text(record) + "\n", encoding="utf-8"
            )
            original_artifact = adjudication.render_adjudication
            original_record = adjudication.render_record
            try:
                adjudication.render_adjudication = lambda _repository: copy.deepcopy(artifact)
                adjudication.render_record = (
                    lambda _repository, _artifact=None: copy.deepcopy(record)
                )
                result = adjudication.validate_publication(repository)
            finally:
                adjudication.render_adjudication = original_artifact
                adjudication.render_record = original_record
            self.assertEqual(result["status"], "pass")

    def test_duplicate_publication_is_rejected(self) -> None:
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
                line + "\n" + line + "\n", encoding="utf-8"
            )
            original_artifact = adjudication.render_adjudication
            original_record = adjudication.render_record
            try:
                adjudication.render_adjudication = lambda _repository: copy.deepcopy(artifact)
                adjudication.render_record = (
                    lambda _repository, _artifact=None: copy.deepcopy(record)
                )
                with self.assertRaisesRegex(
                    adjudication.JointConditionAdjudicationError,
                    "exactly one record",
                ):
                    adjudication.validate_publication(repository)
            finally:
                adjudication.render_adjudication = original_artifact
                adjudication.render_record = original_record


if __name__ == "__main__":
    unittest.main(verbosity=2)
