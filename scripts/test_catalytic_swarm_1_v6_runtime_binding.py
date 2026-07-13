#!/usr/bin/env python3
from __future__ import annotations

import unittest

from catalytic_swarm_1_v6_runtime_binding import (
    ARTIFACT_PATHS,
    V1_SCHEDULER_CONTRACT_SHA256,
    V5_PARTIAL_EXECUTION_BOUNDARY_SHA256,
    V6_CLAIM_CONTRACT_SHA256,
    V6RuntimeBindingError,
    apply_stage_identity,
    build_v6_runtime_binding,
    validate_persisted_v6_record,
)


class V6RuntimeBindingTests(unittest.TestCase):
    def test_claim_scheduler_and_predecessor_identities_are_separate(self) -> None:
        binding = build_v6_runtime_binding()
        self.assertEqual(binding.claim_contract_sha256, V6_CLAIM_CONTRACT_SHA256)
        self.assertEqual(binding.scheduler_contract_sha256, V1_SCHEDULER_CONTRACT_SHA256)
        self.assertEqual(binding.predecessor_boundary_sha256, V5_PARTIAL_EXECUTION_BOUNDARY_SHA256)
        self.assertEqual(
            binding.predecessor_boundary_sha256,
            "897148680e426caf58b9581f06224f904cb8ff5cd1a389b83c1ceedfc427f9d9",
        )
        self.assertEqual(len({binding.claim_contract_sha256, binding.scheduler_contract_sha256, binding.predecessor_boundary_sha256}), 3)

    def test_all_seven_paths_are_v6(self) -> None:
        self.assertEqual(len(ARTIFACT_PATHS), 7)
        for path in ARTIFACT_PATHS.values():
            self.assertTrue(path.startswith("state/catalytic_swarm_1_v6/"))
            self.assertIn("-v6.", path)

    def test_every_stage_is_v6_before_persistence(self) -> None:
        for stage in ARTIFACT_PATHS:
            record = apply_stage_identity({"status": "running"}, stage)
            validate_persisted_v6_record(record, stage)
            self.assertEqual(record["runtime_version"], "v6")
            self.assertEqual(record["schema_version"], 6)
            self.assertEqual(record["attempt_version"], 6)

    def test_predecessor_identity_leakage_v1_through_v5_rejects(self) -> None:
        forbidden = [
            "catalytic_swarm_1",
            "catalytic_swarm_1_v2",
            "catalytic_swarm_1_v3",
            "catalytic_swarm_1_v4",
            "catalytic_swarm_1_v5",
            "control_qualification_v1",
            "readiness_v3",
            "parser_canary_v5",
        ]
        for key in forbidden:
            with self.subTest(key=key), self.assertRaises(V6RuntimeBindingError):
                apply_stage_identity({key: "inconclusive"}, "result")


if __name__ == "__main__":
    unittest.main()
