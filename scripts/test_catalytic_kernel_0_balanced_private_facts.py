#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import catalytic_kernel_0_balanced_private_facts as private_facts


EXPECTED = {
    "transform_operator": "reconcile",
    "transform_artifact_commitment": "A" * 64,
    "transform_ranking_length": 3,
    "transform_top_matched_private_singleton": True,
    "extraction_selected_private_singleton": False,
    "private_public_score": 3,
    "private_public_total": 5,
}


class PrivateOutcomePublicationTests(unittest.TestCase):
    def write_split_ledger(self, repository: Path, *, top_matched: bool = True) -> None:
        lab = repository / "lab"
        lab.mkdir()
        (lab / "results.jsonl").write_text(
            json.dumps(
                {
                    "id": "neo-exp-test",
                    "configuration": {"run_id": "run-1"},
                    "metrics_after": {
                        "terminal_classification": "BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
                        "transform": {
                            "operator": "reconcile",
                            "artifact_commitment": "A" * 64,
                            "ranking_length": 3,
                            "top_matched_private_singleton": top_matched,
                        },
                        "extraction": {
                            "selected_private_singleton": False,
                            "full_public_score": 3,
                            "full_public_total": 5,
                        },
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def write_legacy_ledger(self, repository: Path) -> None:
        lab = repository / "lab"
        lab.mkdir()
        (lab / "results.jsonl").write_text(
            json.dumps(
                {
                    "result": {
                        "run_id": "run-1",
                        "terminal_classification": "BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
                        "transform": {
                            "operator": "reconcile",
                            "artifact_commitment": "A" * 64,
                            "ranking_length": 3,
                            "top_matched_private_singleton": True,
                        },
                        "extraction": {
                            "selected_private_singleton": False,
                            "full_public_score": 3,
                            "full_public_total": 5,
                        },
                    }
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_tracked_outcome_facts_normalize_nested_fields(self) -> None:
        observed = private_facts.tracked_outcome_facts(
            {
                "transform": {
                    "operator": "reconcile",
                    "artifact_commitment": "A" * 64,
                    "ranking_length": 3,
                    "top_matched_private_singleton": True,
                },
                "extraction": {
                    "selected_private_singleton": False,
                    "full_public_score": 3,
                    "full_public_total": 5,
                },
            }
        )
        self.assertEqual(observed, EXPECTED)

    def test_results_ledger_accepts_split_private_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.write_split_ledger(repository)
            result = private_facts.validate_results_ledger_facts(
                repository,
                run_id="run-1",
                expected_classification="BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
                expected_facts=EXPECTED,
            )
            self.assertEqual(result["match"]["facts"], EXPECTED)
            self.assertEqual(result["match"]["layout"], "split-experiment-record")

    def test_results_ledger_accepts_legacy_private_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.write_legacy_ledger(repository)
            result = private_facts.validate_results_ledger_facts(
                repository,
                run_id="run-1",
                expected_classification="BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
                expected_facts=EXPECTED,
            )
            self.assertEqual(result["match"]["layout"], "legacy-co-located")

    def test_results_ledger_rejects_transform_top_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.write_split_ledger(repository, top_matched=False)
            with self.assertRaisesRegex(
                private_facts.PrivateOutcomeEvidenceError,
                "transform_top_matched_private_singleton",
            ):
                private_facts.validate_results_ledger_facts(
                    repository,
                    run_id="run-1",
                    expected_classification="BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
                    expected_facts=EXPECTED,
                )

    def test_raw_private_facts_distinguish_transform_hit_from_extraction_miss(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            root = repository / "state" / "catalytic_kernel_0" / "run-1"
            root.mkdir(parents=True)
            result = {
                "status": "complete",
                "balanced_classification": "BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
                "completed_model_responses": 6,
                "branch_a": {},
                "branch_b": {},
                "transform": {
                    "operator": "reconcile",
                    "ranking": ["K07", "K08", "K09"],
                    "artifact_commitment": "A" * 64,
                },
                "extraction": {
                    "candidate_alias": "K08",
                    "controller_private_evaluation": {
                        "mapped_to_full_public_support": False,
                        "full_public_score": 3,
                        "full_public_total": 5,
                    },
                },
                "restoration": {"passed": True},
            }
            (root / "result.json").write_text(json.dumps(result), encoding="utf-8")
            private = SimpleNamespace(internal_to_alias={"C34": "K07"})
            runtime = mock.Mock()
            runtime.classify.return_value = "BALANCED_OPAQUE_RELATIONAL_COLLAPSED"
            configuration = SimpleNamespace(run_modes={"run-1": "full-information"})
            with mock.patch.object(
                private_facts.balanced,
                "binding_configuration",
                return_value=configuration,
            ), mock.patch.object(
                private_facts.balanced,
                "_private_binding_from_repository",
                return_value=private,
            ), mock.patch.object(
                private_facts.balanced,
                "BalancedOpaqueRuntime",
                return_value=runtime,
            ), mock.patch.object(
                private_facts.balanced,
                "EXPECTED_FULL_SUPPORT",
                ("C34",),
            ):
                facts = private_facts.extract_private_outcome_facts(
                    repository,
                    run_id="run-1",
                    carrier_profile="profile-1",
                    expected_classification="BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
                )
            self.assertTrue(facts["transform_top_matched_private_singleton"])
            self.assertFalse(facts["extraction_selected_private_singleton"])
            self.assertEqual(facts["private_public_score"], 3)

    def test_package_composes_raw_and_tracked_fact_gates(self) -> None:
        with mock.patch.object(
            private_facts,
            "extract_private_outcome_facts",
            return_value=EXPECTED,
        ), mock.patch.object(
            private_facts,
            "validate_results_ledger_facts",
            return_value={"status": "pass"},
        ) as ledger:
            result = private_facts.validate_private_outcome_publication(
                Path("."),
                run_id="run-1",
                carrier_profile="profile-1",
                expected_classification="BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
            )
        self.assertEqual(result["private_outcome_facts"], EXPECTED)
        ledger.assert_called_once_with(
            Path("."),
            run_id="run-1",
            expected_classification="BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
            expected_facts=EXPECTED,
        )


if __name__ == "__main__":
    unittest.main()
