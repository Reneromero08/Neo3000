#!/usr/bin/env python3
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import catalytic_kernel_0_balanced_rank_head_v2_three_parent_global_invariant_probe_adjudication as adjudication


def sample_outcomes() -> list[dict[str, object]]:
    return [
        {
            "request_id": request_id,
            "transform_operator": "reconcile",
            "transform_ranking_length": 3,
            "selected_rank": 0,
            "selection_frozen_before_private_mapping": True,
            "private_mapping_consulted_before_selection": False,
            "selected_from_parent_union": True,
            "selected_candidate_commitment": request_id,
            "mechanism_matches": dict(adjudication.EXPECTED_MECHANISM_MATCHES),
        }
        for request_id in adjudication.probe.REQUEST_IDS
    ]


def sample_adjudication() -> dict[str, object]:
    return {
        "classification": adjudication.SUPPORTED_CLASSIFICATION,
        "supported_interpretation": adjudication.BOUNDED_INTERPRETATION,
        "mechanism_matches_all_six": dict(adjudication.EXPECTED_MECHANISM_MATCHES),
        "semantic_selection_order_invariant_by_geometry": dict(
            adjudication.EXPECTED_ORDER_INVARIANCE
        ),
        "full_commutativity_claimed": False,
        "associativity_claimed": False,
        "general_n_parent_claimed": False,
        "general_transfer_claimed": False,
        "automatic_follow_on": False,
    }


class ThreeParentGlobalInvariantAdjudicationTests(unittest.TestCase):
    def test_exact_pattern_supports_only_the_bounded_classification(self) -> None:
        outcomes = sample_outcomes()
        expected = {str(item["request_id"]): str(item["request_id"]) for item in outcomes}
        adjudication._require_exact_pattern(outcomes, sample_adjudication(), expected)

    def test_mechanism_drift_is_rejected(self) -> None:
        outcomes = sample_outcomes()
        outcomes[0]["mechanism_matches"]["lexical-first"] = True
        with self.assertRaisesRegex(
            adjudication.ThreeParentGlobalInvariantAdjudicationError,
            "mechanism comparison changed",
        ):
            adjudication._require_exact_pattern(outcomes, sample_adjudication())

    def test_order_invariance_drift_is_rejected(self) -> None:
        changed = sample_adjudication()
        changed["semantic_selection_order_invariant_by_geometry"]["T1"] = False
        with self.assertRaisesRegex(
            adjudication.ThreeParentGlobalInvariantAdjudicationError,
            "classification changed",
        ):
            adjudication._require_exact_pattern(sample_outcomes(), changed)

    def test_frozen_three_way_commitment_drift_is_rejected(self) -> None:
        outcomes = sample_outcomes()
        expected = {str(item["request_id"]): str(item["request_id"]) for item in outcomes}
        expected["T1-CAB"] = "different"
        with self.assertRaisesRegex(
            adjudication.ThreeParentGlobalInvariantAdjudicationError,
            "frozen three-way invariant",
        ):
            adjudication._require_exact_pattern(outcomes, sample_adjudication(), expected)

    def test_broader_claims_remain_locked(self) -> None:
        for claim in (
            "FULL_COMMUTATIVITY",
            "ASSOCIATIVITY",
            "ARBITRARY_N_PARENT_GENERALIZATION",
            "WORKER_SYNTHESIS",
            "GENERAL_CATALYTIC_INFERENCE",
            "REDUCED_FRESH_COMPUTATION",
            "COMPUTE_AMPLIFICATION",
        ):
            with self.subTest(claim=claim):
                self.assertEqual(adjudication.LOCKED_CLAIMS[claim], "LOCKED")

    def test_disclosure_boundary_rejects_private_material(self) -> None:
        for field in (
            "private_root",
            "raw_authority_id",
            "ranking",
            "alias_map",
            "candidate_identity",
        ):
            with self.subTest(field=field), self.assertRaises(
                (
                    adjudication.probe.ThreeParentGlobalInvariantProbeError,
                    adjudication.ThreeParentGlobalInvariantAdjudicationError,
                )
            ):
                adjudication.validate_disclosure_boundary({field: "hidden"})

    @staticmethod
    def _publication_fixture(repository: Path) -> tuple[dict[str, object], dict[str, object]]:
        (repository / "lab").mkdir()
        artifact = {"schema_version": 1, "safe": True}
        record = {"id": adjudication.RECORD_ID, "safe": True}
        (repository / adjudication.ARTIFACT_PATH).write_bytes(
            adjudication.canonical_json_bytes(artifact) + b"\n"
        )
        lines = [
            adjudication.canonical_json_text({"id": f"fixture-{index:04d}"})
            for index in range(1, adjudication.EXPECTED_LEDGER_LINE - 1)
        ]
        lines.append(adjudication.canonical_json_text({"id": adjudication.PREDECESSOR_RECORD_ID}))
        lines.append(adjudication.canonical_json_text(record))
        (repository / adjudication.RESULTS_PATH).write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
        return artifact, record

    def test_publication_requires_exact_record_at_line_58(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            artifact, record = self._publication_fixture(repository)
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
            self.assertEqual(result["ledger_line"], 58)

    def test_duplicate_publication_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            artifact, record = self._publication_fixture(repository)
            path = repository / adjudication.RESULTS_PATH
            path.write_text(
                path.read_text(encoding="utf-8")
                + adjudication.canonical_json_text(record)
                + "\n",
                encoding="utf-8",
            )
            original_artifact = adjudication.render_adjudication
            original_record = adjudication.render_record
            try:
                adjudication.render_adjudication = lambda _repository: copy.deepcopy(artifact)
                adjudication.render_record = (
                    lambda _repository, _artifact=None: copy.deepcopy(record)
                )
                with self.assertRaisesRegex(
                    adjudication.ThreeParentGlobalInvariantAdjudicationError,
                    "ledger predecessor or expected line changed",
                ):
                    adjudication.validate_publication(repository)
            finally:
                adjudication.render_adjudication = original_artifact
                adjudication.render_record = original_record


if __name__ == "__main__":
    unittest.main(verbosity=2)
