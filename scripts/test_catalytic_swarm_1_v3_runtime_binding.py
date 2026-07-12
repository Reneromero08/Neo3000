#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest

from catalytic_swarm_1_v3_runtime_binding import (
    V1_SCHEDULER_CONTRACT_SHA256,
    V3_CLAIM_CONTRACT_SHA256,
    V3RuntimeBindingError,
    apply_stage_identity,
    build_v3_runtime_binding,
    rename_v3_result_after_persistence,
    stage_identity,
    validate_persisted_v3_record,
    validate_runtime_contract_bindings,
)


class V3RuntimeBindingTests(unittest.TestCase):
    def test_binding_separates_claim_and_scheduler_contracts(self) -> None:
        value = build_v3_runtime_binding()
        self.assertEqual(value.claim_contract_sha256, V3_CLAIM_CONTRACT_SHA256)
        self.assertEqual(value.scheduler_contract_sha256, V1_SCHEDULER_CONTRACT_SHA256)
        self.assertNotEqual(value.claim_contract_sha256, value.scheduler_contract_sha256)

    def test_result_identity_is_v3_before_persistence(self) -> None:
        record = apply_stage_identity({"status": "running"}, "result")
        self.assertEqual(record["schema_version"], 3)
        self.assertEqual(record["operation"], "catalytic-swarm-1-v3")
        self.assertIn("catalytic_swarm_1_v3", record)
        self.assertNotIn("catalytic_swarm_1", record)
        validate_persisted_v3_record(record, "result")

    def test_v1_labelled_result_is_rejected(self) -> None:
        record = apply_stage_identity({"status": "running"}, "result")
        record["catalytic_swarm_1"] = "inconclusive"
        with self.assertRaises(V3RuntimeBindingError):
            validate_persisted_v3_record(record, "result")

    def test_v1_contract_in_claim_hash_field_is_rejected(self) -> None:
        record = apply_stage_identity({"status": "running"}, "attempt")
        record["claim_contract_sha256"] = V1_SCHEDULER_CONTRACT_SHA256
        with self.assertRaises(V3RuntimeBindingError):
            validate_persisted_v3_record(record, "attempt")

    def test_post_persistence_rename_is_forbidden(self) -> None:
        with self.assertRaises(V3RuntimeBindingError):
            rename_v3_result_after_persistence({})

    def test_every_stage_has_v3_schema_and_dual_contract_binding(self) -> None:
        for stage in (
            "control", "readiness", "parser_canary",
            "attempt", "result", "task_results",
        ):
            identity = stage_identity(stage)
            self.assertEqual(identity["schema_version"], 3)
            self.assertEqual(identity["attempt_version"], 3)
            self.assertEqual(identity["claim_contract_sha256"], V3_CLAIM_CONTRACT_SHA256)
            self.assertEqual(
                identity["scheduler_contract_sha256"],
                V1_SCHEDULER_CONTRACT_SHA256,
            )
            self.assertFalse(identity["automatic_promotion"])

    def test_lock_resolution_requires_both_exact_contracts(self) -> None:
        evaluator = {
            "catalytic_swarm_1": {"kind": "scheduler"},
            "catalytic_swarm_1_v3": {"kind": "claim"},
        }
        hashes = {
            id(evaluator["catalytic_swarm_1"]): V1_SCHEDULER_CONTRACT_SHA256,
            id(evaluator["catalytic_swarm_1_v3"]): V3_CLAIM_CONTRACT_SHA256,
        }
        lock = {
            "catalytic_swarm_1_sha256": V1_SCHEDULER_CONTRACT_SHA256,
            "catalytic_swarm_1_v3_sha256": V3_CLAIM_CONTRACT_SHA256,
        }
        result = validate_runtime_contract_bindings(
            evaluator,
            lock,
            object_sha256=lambda value: hashes[id(value)],
        )
        self.assertEqual(
            result["binding"]["claim_contract_sha256"],
            V3_CLAIM_CONTRACT_SHA256,
        )
        broken = copy.deepcopy(lock)
        broken["catalytic_swarm_1_v3_sha256"] = "0" * 64
        with self.assertRaises(V3RuntimeBindingError):
            validate_runtime_contract_bindings(
                evaluator,
                broken,
                object_sha256=lambda value: hashes[id(value)],
            )


if __name__ == "__main__":
    unittest.main()
