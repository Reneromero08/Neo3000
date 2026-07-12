#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest

from catalytic_swarm_1_v4_runtime_binding import (
    V1_SCHEDULER_CONTRACT_SHA256,
    V4_CLAIM_CONTRACT_SHA256,
    V4RuntimeBindingError,
    apply_stage_identity,
    build_v4_runtime_binding,
    rename_v4_result_after_persistence,
    stage_identity,
    validate_persisted_v4_record,
    validate_runtime_contract_bindings,
)


class V4RuntimeBindingTests(unittest.TestCase):
    def test_claim_and_scheduler_hashes_are_separate(self) -> None:
        binding = build_v4_runtime_binding()
        self.assertEqual(binding.claim_contract_sha256, V4_CLAIM_CONTRACT_SHA256)
        self.assertEqual(binding.scheduler_contract_sha256, V1_SCHEDULER_CONTRACT_SHA256)
        self.assertNotEqual(binding.claim_contract_sha256, binding.scheduler_contract_sha256)

    def test_every_stage_is_v4_before_persistence(self) -> None:
        for stage in ("control", "readiness", "parser_canary", "attempt", "result", "task_results"):
            record = apply_stage_identity({"status": "running"}, stage)
            validate_persisted_v4_record(record, stage)
            self.assertEqual(record["schema_version"], 4)
            self.assertFalse(record["automatic_promotion"])

    def test_predecessor_verdict_leakage_rejects(self) -> None:
        for key in ("catalytic_swarm_1", "catalytic_swarm_1_v2", "catalytic_swarm_1_v3"):
            record = apply_stage_identity({"status": "running"}, "result")
            record[key] = "inconclusive"
            with self.assertRaises(V4RuntimeBindingError):
                validate_persisted_v4_record(record, "result")

    def test_predecessor_stage_verdict_leakage_rejects(self) -> None:
        with self.assertRaises(V4RuntimeBindingError):
            apply_stage_identity({"control_qualification_v3": "inconclusive"}, "control")

    def test_claim_scheduler_conflation_rejects(self) -> None:
        record = apply_stage_identity({"status": "running"}, "result")
        record["claim_contract_sha256"] = V1_SCHEDULER_CONTRACT_SHA256
        with self.assertRaises(V4RuntimeBindingError):
            validate_persisted_v4_record(record, "result")

    def test_post_persistence_rename_is_forbidden(self) -> None:
        with self.assertRaises(V4RuntimeBindingError):
            rename_v4_result_after_persistence({})

    def test_lock_resolution_requires_both_contracts(self) -> None:
        evaluator = {"catalytic_swarm_1": {"kind": "scheduler"}, "catalytic_swarm_1_v4": {"kind": "claim"}}
        hashes = {id(evaluator["catalytic_swarm_1"]): V1_SCHEDULER_CONTRACT_SHA256, id(evaluator["catalytic_swarm_1_v4"]): V4_CLAIM_CONTRACT_SHA256}
        lock = {"catalytic_swarm_1_sha256": V1_SCHEDULER_CONTRACT_SHA256, "catalytic_swarm_1_v4_sha256": V4_CLAIM_CONTRACT_SHA256}
        validate_runtime_contract_bindings(evaluator, lock, object_sha256=lambda value: hashes[id(value)])
        broken = copy.deepcopy(lock); broken["catalytic_swarm_1_v4_sha256"] = "0" * 64
        with self.assertRaises(V4RuntimeBindingError):
            validate_runtime_contract_bindings(evaluator, broken, object_sha256=lambda value: hashes[id(value)])

    def test_stage_operations_are_v4(self) -> None:
        self.assertEqual(stage_identity("control")["operation"], "catalytic-swarm-1-v4-control-qualification-v4")
        self.assertEqual(stage_identity("result")["operation"], "catalytic-swarm-1-v4")


if __name__ == "__main__":
    unittest.main()
