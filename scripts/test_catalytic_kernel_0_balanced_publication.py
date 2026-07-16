#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import catalytic_kernel_0_balanced_publication as publication


class BalancedPublicationValidatorTests(unittest.TestCase):
    def test_observed_result_keys_are_rejected(self) -> None:
        self.assertEqual(
            publication.forbidden_observed_result_keys(
                {
                    "status": "static-preregistered",
                    "full_information_observed_result": {},
                    "delete_a_observed_result": {},
                }
            ),
            ["delete_a_observed_result", "full_information_observed_result"],
        )
        self.assertEqual(
            publication.forbidden_observed_result_keys(
                {"status": "static-preregistered"}
            ),
            [],
        )

    def test_terminal_raw_evidence_validates_hash_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            root = repository / "state" / "catalytic_kernel_0" / "run-1"
            root.mkdir(parents=True)
            manifest = {"schema_version": 1, "run_id": "run-1"}
            result = {
                "status": "complete",
                "run_id": "run-1",
                "balanced_classification": "BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
                "request_outcomes": [],
            }
            manifest_path = root / "manifest.json"
            result_path = root / "result.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result_path.write_text(json.dumps(result), encoding="utf-8")
            closure = {
                "run_id": "run-1",
                "manifest_sha256": publication.sha256_bytes(manifest_path.read_bytes()),
                "result_sha256": publication.sha256_bytes(result_path.read_bytes()),
                "run_lock_absent": True,
            }
            (root / "closure.json").write_text(json.dumps(closure), encoding="utf-8")
            validated = publication.validate_terminal_raw_evidence(
                repository,
                run_id="run-1",
                expected_classification="BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
                carrier_profile=None,
            )
            self.assertEqual(
                validated["classification"],
                "BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
            )

    def test_terminal_raw_evidence_rejects_bad_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            root = repository / "state" / "catalytic_kernel_0" / "run-1"
            root.mkdir(parents=True)
            (root / "manifest.json").write_text("{}", encoding="utf-8")
            (root / "result.json").write_text(
                json.dumps(
                    {
                        "status": "complete",
                        "balanced_classification": "BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
                    }
                ),
                encoding="utf-8",
            )
            (root / "closure.json").write_text(
                json.dumps({"result_sha256": "0" * 64, "run_lock_absent": True}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                publication.PublicationEvidenceError, "result binding mismatch"
            ):
                publication.validate_terminal_raw_evidence(
                    repository,
                    run_id="run-1",
                    expected_classification="BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
                    carrier_profile=None,
                )

    def test_results_ledger_accepts_split_experiment_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            lab = repository / "lab"
            lab.mkdir()
            (lab / "results.jsonl").write_text(
                json.dumps(
                    {
                        "id": "neo-exp-test",
                        "configuration": {"run_id": "run-1"},
                        "metrics_after": {
                            "terminal_classification": "BALANCED_OPAQUE_RELATIONAL_COLLAPSED"
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            result = publication.validate_results_ledger(
                repository,
                run_id="run-1",
                expected_classification="BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
            )
            self.assertEqual(result["match"]["line"], 1)
            self.assertEqual(result["match"]["layout"], "split-experiment-record")

    def test_results_ledger_accepts_legacy_co_located_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            lab = repository / "lab"
            lab.mkdir()
            (lab / "results.jsonl").write_text(
                json.dumps(
                    {
                        "result": {
                            "run_id": "run-1",
                            "terminal_classification": "BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            result = publication.validate_results_ledger(
                repository,
                run_id="run-1",
                expected_classification="BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
            )
            self.assertEqual(result["match"]["layout"], "legacy-co-located")

    def test_package_composes_three_independent_gates(self) -> None:
        with mock.patch.object(
            publication,
            "validate_static_preregistration",
            return_value={"status": "pass"},
        ), mock.patch.object(
            publication,
            "validate_terminal_raw_evidence",
            return_value={"classification": "BALANCED_OPAQUE_RELATIONAL_COLLAPSED"},
        ), mock.patch.object(
            publication,
            "validate_results_ledger",
            return_value={"status": "pass"},
        ):
            result = publication.validate_publication_package(
                Path("."),
                run_id="run-1",
                carrier_profile="profile-1",
                expected_classification="BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
            )
        self.assertEqual(result["status"], "pass")


if __name__ == "__main__":
    unittest.main()
