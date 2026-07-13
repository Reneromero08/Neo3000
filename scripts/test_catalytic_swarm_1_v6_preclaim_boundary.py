#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from catalytic_swarm_1_v3_preclaim_boundary import (
    EXPECTED_V3_PRECLAIM_BOUNDARY_SHA256,
    build_catalytic_swarm_1_v3_preclaim_boundary,
)
from catalytic_swarm_1_v4_partial_execution_boundary import (
    EXPECTED_V4_PARTIAL_EXECUTION_BOUNDARY_SHA256,
    build_catalytic_swarm_1_v4_partial_execution_boundary,
)
from catalytic_swarm_1_v5_partial_execution_boundary import (
    EXPECTED_V5_PARTIAL_EXECUTION_BOUNDARY_SHA256,
    build_catalytic_swarm_1_v5_partial_execution_boundary,
)
from catalytic_swarm_1_v6_preclaim_boundary import (
    EXPECTED_V6_PRECLAIM_BOUNDARY_SHA256,
    V6_CONTROL_ARTIFACT_PATH,
    V6_CONTROL_ARTIFACT_SHA256,
    V6_CONTROL_ARTIFACT_SIZE_BYTES,
    V6_CLAIM_CONTRACT_SHA256,
    V6_CLASSIFICATION,
    V6_EXACT_COMMAND_ARGV_SHA256,
    V6_PROTECTED_MAIN,
    V6_RUNTIME_EVIDENCE_BINDING_SHA256,
    V6_SCHEDULER_CONTRACT_SHA256,
    build_catalytic_swarm_1_v6_preclaim_boundary,
    sha256_object,
    validate_catalytic_swarm_1_v6_preclaim_boundary,
)


ROOT = Path(__file__).resolve().parents[1]


class V6PreclaimBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.boundary = build_catalytic_swarm_1_v6_preclaim_boundary()

    def test_canonical_boundary_hash_is_exact_and_lowercase(self) -> None:
        observed = sha256_object(self.boundary)
        self.assertEqual(observed, EXPECTED_V6_PRECLAIM_BOUNDARY_SHA256)
        self.assertEqual(observed, observed.lower())
        validate_catalytic_swarm_1_v6_preclaim_boundary(self.boundary)
        evaluator = json.loads(
            (ROOT / "lab" / "EVALUATOR.json").read_text(encoding="utf-8")
        )
        lock = json.loads(
            (ROOT / "lab" / "EVALUATOR.lock.json").read_text(encoding="utf-8")
        )
        lock_key = "catalytic_swarm_1_v6_preclaim_boundary_sha256"
        # EVALUATOR integration belongs to another worker.  Once that worker
        # publishes the lock entry, require its object and hash to be exact;
        # do not make this owned unit test fail on an in-flight unlocked draft.
        if lock_key in lock:
            self.assertEqual(
                evaluator["catalytic_swarm_1_v6_preclaim_boundary"], self.boundary
            )
            self.assertEqual(lock[lock_key], observed)

    def test_raw_v6_control_artifact_is_exact_without_rewrite(self) -> None:
        path = ROOT / V6_CONTROL_ARTIFACT_PATH
        self.assertEqual(path.stat().st_size, V6_CONTROL_ARTIFACT_SIZE_BYTES)
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest().upper(),
            V6_CONTROL_ARTIFACT_SHA256,
        )
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(raw["authorized_main"], "ef8caa5c0132d1581321d8ba9fd9643a8d246fbb")
        self.assertEqual(
            raw["error"],
            "NeoLoopError: CatalyticSwarm-1 requires a clean stable worktree",
        )
        self.assertTrue(raw["command_invocation_consumed"])
        self.assertTrue(raw["no_retry"])
        self.assertEqual(self.boundary["artifact"]["started_at"], raw["started_at"])
        self.assertEqual(self.boundary["artifact"]["finished_at"], raw["finished_at"])

    def test_other_six_v6_artifacts_remain_absent(self) -> None:
        self.assertEqual(len(self.boundary["absent_artifact_paths"]), 6)
        self.assertTrue(
            all(
                not (ROOT / path).exists()
                for path in self.boundary["absent_artifact_paths"]
            )
        )

    def test_exact_command_timestamps_and_exit_are_frozen(self) -> None:
        self.assertEqual(
            self.boundary["command"]["exact_argv_sha256"],
            V6_EXACT_COMMAND_ARGV_SHA256,
        )
        self.assertFalse(self.boundary["command"]["local_path_values_committed"])
        self.assertNotIn("D:\\\\", json.dumps(self.boundary, sort_keys=True))
        self.assertEqual(
            self.boundary["timestamps"],
            {
                "shell_start_utc": "2026-07-13T05:06:47.9147053Z",
                "controller_start_utc": "2026-07-13T05:06:48.342436+00:00",
                "controller_finish_utc": "2026-07-13T05:07:07.630329+00:00",
                "shell_finish_utc": "2026-07-13T05:07:07.6718445Z",
            },
        )
        self.assertEqual(self.boundary["outcome"]["process_exit_code"], 1)

    def test_boundary_is_non_adjudicating_and_records_zero_live_work(self) -> None:
        outcome = self.boundary["outcome"]
        runtime = self.boundary["runtime"]
        self.assertEqual(
            outcome["classification"],
            V6_CLASSIFICATION,
        )
        self.assertFalse(outcome["experiment_adjudicated"])
        self.assertEqual(runtime["model_requests"], 0)
        self.assertEqual(runtime["live_model_requests"], 0)
        self.assertEqual(runtime["completed_model_responses"], 0)
        self.assertEqual(runtime["sidecar_launches"], 0)
        self.assertEqual(self.boundary["custody"]["stable"]["pid"], 32684)
        self.assertEqual(
            self.boundary["custody"]["candidate"]["commit"],
            "14de9c71593e5aea4fcfcadeda47ba5c623fadcf",
        )

    def test_protected_main_and_three_contracts_are_exact(self) -> None:
        self.assertEqual(self.boundary["protected_main"], V6_PROTECTED_MAIN)
        self.assertEqual(
            self.boundary["protected_execution_commit"], V6_PROTECTED_MAIN
        )
        self.assertEqual(
            self.boundary["contracts"],
            {
                "claim_contract_sha256": V6_CLAIM_CONTRACT_SHA256,
                "runtime_evidence_binding_sha256": V6_RUNTIME_EVIDENCE_BINDING_SHA256,
                "scheduler_contract_sha256": V6_SCHEDULER_CONTRACT_SHA256,
            },
        )

    def test_model_and_binary_identities_are_supplied_but_unverified(self) -> None:
        identities = self.boundary["identities"]
        raw = json.loads((ROOT / V6_CONTROL_ARTIFACT_PATH).read_text(encoding="utf-8"))
        self.assertEqual(identities["status"], "supplied-but-unverified")
        self.assertFalse(identities["verification_reached"])
        for name, raw_name in (
            ("model", "expected_model_identity"),
            ("binary", "expected_binary_identity"),
        ):
            identity = identities[name]
            self.assertEqual(identity["status"], "supplied-but-unverified")
            self.assertTrue(identity["path_supplied"])
            self.assertFalse(identity["verified_during_v6"])
            for key, expected in raw[raw_name].items():
                self.assertEqual(identity[key], expected)

    def test_causal_diagnosis_is_specific_and_epistemically_bounded(self) -> None:
        diagnosis = self.boundary["causal_diagnosis"]
        self.assertEqual(
            diagnosis["defect"],
            "runtime-marker-claim-before-preclaim-cleanliness-capture",
        )
        self.assertIn("claims the V6 control artifact before", diagnosis["statically_proved"])
        self.assertIn("protected ignore policy ended at V5", diagnosis["cause"])
        self.assertEqual(diagnosis["scientific_interpretation"], V6_CLASSIFICATION)

    def test_full_v3_v4_v5_preservation_hashes_are_included(self) -> None:
        preservation = self.boundary["predecessor_preservation"]
        v3 = build_catalytic_swarm_1_v3_preclaim_boundary()
        v4 = build_catalytic_swarm_1_v4_partial_execution_boundary()
        v5 = build_catalytic_swarm_1_v5_partial_execution_boundary()
        self.assertEqual(
            preservation["v3"]["boundary_sha256"],
            EXPECTED_V3_PRECLAIM_BOUNDARY_SHA256,
        )
        self.assertEqual(preservation["v3"]["artifact"], v3["artifact"])
        self.assertEqual(
            preservation["v3"]["absent_artifact_paths"],
            v3["absent_artifact_paths"],
        )
        self.assertEqual(
            preservation["v4"]["boundary_sha256"],
            EXPECTED_V4_PARTIAL_EXECUTION_BOUNDARY_SHA256,
        )
        self.assertEqual(preservation["v4"]["artifacts"], v4["artifacts"])
        self.assertEqual(
            preservation["v5"]["boundary_sha256"],
            EXPECTED_V5_PARTIAL_EXECUTION_BOUNDARY_SHA256,
        )
        self.assertEqual(preservation["v5"]["artifacts"], v5["artifacts"])
        self.assertEqual(len(preservation["v4"]["artifacts"]), 7)
        self.assertEqual(len(preservation["v5"]["artifacts"]), 7)

    def test_all_present_v3_v4_v5_raw_artifact_hashes_remain_exact(self) -> None:
        preservation = self.boundary["predecessor_preservation"]
        artifacts = [preservation["v3"]["artifact"]]
        artifacts.extend(preservation["v4"]["artifacts"])
        artifacts.extend(preservation["v5"]["artifacts"])
        for artifact in artifacts:
            with self.subTest(path=artifact["path"]):
                path = ROOT / artifact["path"]
                self.assertEqual(path.stat().st_size, artifact["size_bytes"])
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest().upper(),
                    artifact["sha256"],
                )


if __name__ == "__main__":
    unittest.main()
