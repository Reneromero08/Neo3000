#!/usr/bin/env python3
from __future__ import annotations

import unittest

from catalytic_swarm_1_v5_runtime_binding import (
    V1_SCHEDULER_CONTRACT_SHA256,
    V5_CLAIM_CONTRACT_SHA256,
    V5RuntimeBindingError,
    apply_stage_identity,
    build_v5_runtime_binding,
    validate_persisted_v5_record,
)


class V5RuntimeBindingTests(unittest.TestCase):
    def test_claim_and_scheduler_identities_are_separate(self) -> None:
        binding = build_v5_runtime_binding()
        self.assertEqual(binding.claim_contract_sha256, V5_CLAIM_CONTRACT_SHA256)
        self.assertEqual(binding.scheduler_contract_sha256, V1_SCHEDULER_CONTRACT_SHA256)
        self.assertNotEqual(binding.claim_contract_sha256, binding.scheduler_contract_sha256)

    def test_every_stage_is_v5_before_persistence(self) -> None:
        for stage in ("control", "readiness", "parser_canary", "attempt", "result", "task_results"):
            record = apply_stage_identity({"status": "running"}, stage)
            validate_persisted_v5_record(record, stage)
            self.assertEqual(record["schema_version"], 5)

    def test_predecessor_identity_leakage_rejects(self) -> None:
        with self.assertRaises(V5RuntimeBindingError):
            apply_stage_identity({"catalytic_swarm_1_v4": "inconclusive"}, "result")
        with self.assertRaises(V5RuntimeBindingError):
            apply_stage_identity({"readiness_v4": "pass"}, "readiness")


if __name__ == "__main__":
    unittest.main()
