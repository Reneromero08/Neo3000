#!/usr/bin/env python3
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import catalytic_kernel_0_two_shard_semantic_xor_worker_baseline_evaluation_adjudication as adjudication


class SemanticXorAdjudicationTests(unittest.TestCase):
    def test_source_terminal_and_forensic_classifications_are_distinct(self) -> None:
        self.assertEqual(
            adjudication.ATTEMPT_HISTORIES[2]["terminal_classification"],
            "INCONCLUSIVE",
        )
        self.assertEqual(
            adjudication.CAPABILITY_CLASSIFICATION,
            "NON_CONTROLLER_RECONSTRUCTIBLE_SEMANTIC_XOR_WORKER_SYNTHESIS_SUPPORTED",
        )

    def test_scientific_summary_accepts_only_exact_aggregates_and_resources(self) -> None:
        resources = {
            **copy.deepcopy(adjudication.EXPECTED_ROUTE_RESOURCES),
            "advantage_classification": adjudication.ADVANTAGE_CLASSIFICATION,
            "worker_tokens_per_correct_strictly_lower": False,
        }
        adjudication.validate_scientific_summary(
            adjudication.EXPECTED_AGGREGATE, resources
        )

    def test_aggregate_drift_is_rejected(self) -> None:
        aggregate = dict(adjudication.EXPECTED_AGGREGATE)
        aggregate["baseline_final_correct"] = 4
        resources = {
            **copy.deepcopy(adjudication.EXPECTED_ROUTE_RESOURCES),
            "advantage_classification": adjudication.ADVANTAGE_CLASSIFICATION,
            "worker_tokens_per_correct_strictly_lower": False,
        }
        with self.assertRaisesRegex(
            adjudication.SemanticXorAdjudicationError,
            "aggregate changed",
        ):
            adjudication.validate_scientific_summary(aggregate, resources)

    def test_negative_efficiency_result_is_exact(self) -> None:
        cross = adjudication.EXPECTED_ROUTE_RESOURCES[
            "exact_integer_cross_products"
        ]
        self.assertEqual(cross["worker_tokens_x_baseline_correct"], 9015)
        self.assertEqual(cross["baseline_tokens_x_worker_correct"], 5720)
        self.assertGreater(9015, 5720)
        self.assertEqual(
            adjudication.ADVANTAGE_CLASSIFICATION,
            "SEMANTIC_XOR_WORKER_SYNTHESIS_ADVANTAGE_NOT_SUPPORTED",
        )

    def test_original_failure_hash_is_frozen(self) -> None:
        self.assertEqual(
            adjudication.probe.sha256_bytes(
                b"protected evaluator aggregate balance changed"
            ),
            adjudication.SOURCE_EVIDENCE["live_scorer_failure_sha256"],
        )

    def test_disclosure_boundary_rejects_protected_material(self) -> None:
        for field in (
            "expected_worker_a_bit",
            "expected_worker_b_bit",
            "expected_label",
            "private_salt_hex",
            "task_to_cell",
            "per_task",
            "private_root",
            "rationale",
        ):
            with self.subTest(field=field), self.assertRaises(Exception):
                adjudication.validate_disclosure_boundary({field: "hidden"})

    def test_publication_requires_one_exact_record_at_line_sixty(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / "lab").mkdir()
            artifact = {"schema_version": 1, "safe": True}
            record = {"id": adjudication.RECORD_ID, "safe": True}
            (repository / adjudication.ARTIFACT_PATH).write_bytes(
                adjudication.canonical_json_bytes(artifact) + b"\n"
            )
            prior = [
                adjudication.canonical_json_text({"id": f"prior-record-{index:04d}"})
                for index in range(1, 60)
            ]
            prior.append(adjudication.canonical_json_text(record))
            (repository / adjudication.RESULTS_PATH).write_text(
                "\n".join(prior) + "\n", encoding="utf-8"
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
            self.assertEqual(result["ledger_line"], 60)

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
                (line + "\n") * 2, encoding="utf-8"
            )
            original_artifact = adjudication.render_adjudication
            original_record = adjudication.render_record
            try:
                adjudication.render_adjudication = lambda _repository: copy.deepcopy(artifact)
                adjudication.render_record = (
                    lambda _repository, _artifact=None: copy.deepcopy(record)
                )
                with self.assertRaisesRegex(
                    adjudication.SemanticXorAdjudicationError,
                    "exactly one record",
                ):
                    adjudication.validate_publication(repository)
            finally:
                adjudication.render_adjudication = original_artifact
                adjudication.render_record = original_record


if __name__ == "__main__":
    unittest.main(verbosity=2)
