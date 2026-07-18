#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

import catalytic_kernel_0_balanced_rank_head_v2_parent_dependence_forensic_recovery as recovery


REPOSITORY = Path(__file__).resolve().parent.parent


class ParentDependenceForensicRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(recovery.__file__)),
                "render",
                "--repository",
                str(REPOSITORY),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        cls.rendered = json.loads(completed.stdout)

    def test_original_terminal_truth_remains_inconclusive(self) -> None:
        original = self.rendered["original_execution_truth"]
        self.assertEqual(original["status"], "INCONCLUSIVE")
        self.assertEqual(
            original["reason"],
            "durable-finalization-custody-gate-failed",
        )
        self.assertFalse(original["result_and_archive_rewritten"])
        self.assertEqual(
            original["archive_sha256"],
            recovery.ORIGINAL_ARCHIVE_SHA256,
        )

    def test_exact_failure_reproduction_and_sole_cause_are_bound(self) -> None:
        failure = self.rendered["failure_isolation"]
        self.assertEqual(
            failure["original_exception_sha256"],
            recovery.ORIGINAL_FAILURE_SHA256,
        )
        self.assertEqual(
            failure["bounded_failure_classification"],
            "CONTROLLER_OWNED_ZERO_BYTE_LOCK_READ_DENIED_DURING_POSTCLAIM_INVENTORY",
        )
        self.assertTrue(failure["controller_lock_sole_illegal_changed_path"])
        self.assertTrue(failure["removing_only_controller_lock_made_original_validator_pass"])
        self.assertTrue(failure["unrelated_file_removal_did_not_change_failure_identity"])
        self.assertTrue(failure["corrected_postflight_custody_passed"])
        self.assertEqual(
            failure["commitment_sha256"],
            "9DE13A4272F0628065A274C32374E01FE6533B910CDC9FD3CA4CBD79A01BBF51",
        )

    def test_archive_capture_and_tamper_gates_pass(self) -> None:
        failure = self.rendered["failure_isolation"]
        self.assertTrue(failure["source_archive_verified"])
        self.assertTrue(failure["source_publication_verified"])
        self.assertTrue(all(failure["tamper_rejections"].values()))
        replay = self.rendered["forensic_replay"]
        self.assertEqual(replay["request_started_event_count"], 2)
        self.assertEqual(replay["response_captured_event_count"], 2)
        self.assertFalse(replay["duplicate_generation_detected"])
        self.assertTrue(replay["both_responses_durably_captured_before_parsing"])
        self.assertTrue(replay["both_rank_heads_frozen_before_any_private_mapping"])

    def test_zero_contact_replay_recovers_only_directional_parent_a(self) -> None:
        replay = self.rendered["forensic_replay"]
        self.assertEqual(replay["model_generations_during_recovery"], 0)
        self.assertEqual(replay["http_requests_during_recovery"], 0)
        self.assertEqual(replay["sidecar_launches_during_recovery"], 0)
        self.assertFalse(replay["authority_created_or_consumed_during_recovery"])
        arms = {item["arm_id"]: item for item in replay["arms"]}
        self.assertEqual(
            arms["delete-parent-0"]["classification"],
            "BINDING_2_PARENT_A_INFORMATION_DEPENDENCE_SUPPORTED",
        )
        self.assertEqual(
            arms["delete-parent-1"]["classification"],
            "BINDING_2_PARENT_B_INFORMATION_DEPENDENCE_NOT_SHOWN",
        )
        self.assertEqual(
            arms["delete-parent-0"]["transform_artifact_commitment"],
            "39F1EB95FD0120196D09904136AF6535B571DFDF66F94926CCEB5019FFFBE3D9",
        )
        self.assertEqual(
            arms["delete-parent-1"]["transform_artifact_commitment"],
            "826AB08226CEF708B9577257C13EB8C12C7BD0EE0EADB9E36072B163D671C30C",
        )
        self.assertEqual([item["transform_ranking_length"] for item in arms.values()], [3, 3])
        self.assertEqual([item["selected_rank"] for item in arms.values()], [0, 0])
        self.assertEqual([item["private_public_score"] for item in arms.values()], [3, 5])
        self.assertEqual([item["private_public_total"] for item in arms.values()], [5, 5])

    def test_claim_boundary_and_no_smuggle_are_fail_closed(self) -> None:
        adjudication = self.rendered["cross_binding_causal_adjudication"]
        self.assertEqual(adjudication["supported_claims"], list(recovery.SUPPORTED_CLAIMS))
        self.assertFalse(adjudication["bilateral_replication_supported"])
        self.assertEqual(adjudication["locked_claims"], recovery.LOCKED_CLAIMS)
        self.assertTrue(all(value is False for key, value in self.rendered["no_smuggle"].items() if key != "bounded_metadata_only"))
        self.assertTrue(self.rendered["no_smuggle"]["bounded_metadata_only"])

    def test_tracked_artifact_equals_fresh_independent_render(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(recovery.__file__)),
                "validate",
                "--repository",
                str(REPOSITORY),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(completed.stdout)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["artifact_id"], recovery.ARTIFACT_ID)
        self.assertEqual(report["model_generations_during_recovery"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
