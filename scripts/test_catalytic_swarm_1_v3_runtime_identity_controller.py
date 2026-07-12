#!/usr/bin/env python3
"""CPU-only controller checks for CS1-v3 persisted runtime identity."""

from __future__ import annotations

import json
import unittest
from unittest import mock
from pathlib import Path

import holostate_live as holo
from catalytic_swarm_1_v3_runtime_binding import (
    V1_SCHEDULER_CONTRACT_SHA256,
    V3_CLAIM_CONTRACT_SHA256,
    build_v3_runtime_binding,
    validate_persisted_v3_record,
)


ROOT = Path(__file__).resolve().parents[1]


class V3RuntimeIdentityControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.binding = build_v3_runtime_binding()

    def record(self, path: Path, *, verdict: str = "inconclusive") -> dict:
        legacy = {
            holo.CATALYTIC_SWARM_1_V3_CONTROL_PATH: "control_qualification_v1",
            holo.CATALYTIC_SWARM_1_V3_READINESS_PATH: "readiness_v1",
            holo.CATALYTIC_SWARM_1_V3_PARSER_CANARY_PATH: "parser_canary_v1",
            holo.CATALYTIC_SWARM_1_V3_ATTEMPT_PATH: "catalytic_swarm_1",
            holo.CATALYTIC_SWARM_1_V3_RESULT_PATH: "catalytic_swarm_1",
            holo.CATALYTIC_SWARM_1_V3_TASK_RESULTS_PATH: "catalytic_swarm_1",
        }[path]
        return holo.bind_catalytic_swarm_1_runtime_record(
            path, {"status": "running", legacy: verdict, "contract_sha256": V1_SCHEDULER_CONTRACT_SHA256}, self.binding
        )

    def test_evaluator_and_lock_bind_distinct_exact_contracts(self) -> None:
        evaluator = json.loads((ROOT / "lab" / "EVALUATOR.json").read_text())
        lock = json.loads((ROOT / "lab" / "EVALUATOR.lock.json").read_text())
        self.assertEqual(evaluator["catalytic_swarm_1_v3"]["id"], "catalytic_swarm_1_v3")
        self.assertEqual(lock["catalytic_swarm_1_sha256"], V1_SCHEDULER_CONTRACT_SHA256)
        self.assertEqual(lock["catalytic_swarm_1_v3_sha256"], V3_CLAIM_CONTRACT_SHA256)

    def test_scheduler_and_claim_hashes_are_not_interchangeable(self) -> None:
        self.assertNotEqual(V1_SCHEDULER_CONTRACT_SHA256, V3_CLAIM_CONTRACT_SHA256)
        record = self.record(holo.CATALYTIC_SWARM_1_V3_RESULT_PATH)
        self.assertEqual(record["claim_contract_sha256"], V3_CLAIM_CONTRACT_SHA256)
        self.assertEqual(record["scheduler_contract_sha256"], V1_SCHEDULER_CONTRACT_SHA256)

    def test_every_artifact_is_v3_labelled_before_write(self) -> None:
        stages = (
            (holo.CATALYTIC_SWARM_1_V3_CONTROL_PATH, "control"),
            (holo.CATALYTIC_SWARM_1_V3_READINESS_PATH, "readiness"),
            (holo.CATALYTIC_SWARM_1_V3_PARSER_CANARY_PATH, "parser_canary"),
            (holo.CATALYTIC_SWARM_1_V3_ATTEMPT_PATH, "attempt"),
            (holo.CATALYTIC_SWARM_1_V3_RESULT_PATH, "result"),
            (holo.CATALYTIC_SWARM_1_V3_TASK_RESULTS_PATH, "task_results"),
        )
        for path, stage in stages:
            with self.subTest(stage=stage):
                record = self.record(path)
                validate_persisted_v3_record(record, stage)
                self.assertNotIn("catalytic_swarm_1", record)
                self.assertNotIn("catalytic_swarm_1_v2", record)

    def test_ledger_envelope_is_bounded_and_identity_bound(self) -> None:
        base = {key: 0 for key in holo.CATALYTIC_SWARM_1_LEDGER_FIELDS}
        base.update({"task_id": "cs1-task-01", "arm": "common-root-warm", "assigned_parents": [], "candidate_id": None, "public_pass_count": None, "content_sha256": "x", "token_evidence_scope": "metadata", "wddm_freshness_boundary": "x", "lease_id": 0, "request_started_at": "x", "request_finished_at": "x"})
        record = holo.bind_catalytic_swarm_1_ledger_record(base, self.binding)
        holo.validate_catalytic_swarm_1_ledger_record(record, runtime_binding=self.binding)
        self.assertEqual(record["runtime_version"], "v3")

    def test_mocked_end_to_end_identity_path_never_writes_runtime_state(self) -> None:
        before = tuple(path.exists() for path in holo.CATALYTIC_SWARM_1_V3_ARTIFACT_PATHS)
        persisted = [self.record(path, verdict="reviewable-accept") for path in (
            holo.CATALYTIC_SWARM_1_V3_CONTROL_PATH,
            holo.CATALYTIC_SWARM_1_V3_READINESS_PATH,
            holo.CATALYTIC_SWARM_1_V3_PARSER_CANARY_PATH,
            holo.CATALYTIC_SWARM_1_V3_ATTEMPT_PATH,
            holo.CATALYTIC_SWARM_1_V3_RESULT_PATH,
            holo.CATALYTIC_SWARM_1_V3_TASK_RESULTS_PATH,
        )]
        returned = dict(persisted[4])
        self.assertEqual(returned, persisted[4])
        self.assertTrue(all(item["schema_version"] == 3 for item in persisted))
        self.assertFalse(any(before))
        self.assertFalse(any(path.exists() for path in holo.CATALYTIC_SWARM_1_V3_ARTIFACT_PATHS))

    def test_runtime_root_remains_absent(self) -> None:
        self.assertFalse(holo.CATALYTIC_SWARM_1_V3_STATE_ROOT.exists())

    def test_schedule_and_promotion_remain_frozen(self) -> None:
        evaluator = json.loads((ROOT / "lab" / "EVALUATOR.json").read_text())
        geometry = evaluator["catalytic_swarm_1_v3"]["frozen_geometry"]
        self.assertEqual((2 * geometry["total_model_requests"], geometry["total_model_requests"], geometry["task_count"]), (2064, 1032, 8))
        self.assertFalse(evaluator["catalytic_swarm_1_v3"]["claim_limits"]["automatic_promotion"])

    def test_control_operation_is_v3(self) -> None:
        self.assertEqual(self.record(holo.CATALYTIC_SWARM_1_V3_CONTROL_PATH)["operation"], "catalytic-swarm-1-v3-control-qualification-v3")

    def test_readiness_operation_is_v3(self) -> None:
        self.assertEqual(self.record(holo.CATALYTIC_SWARM_1_V3_READINESS_PATH)["operation"], "catalytic-swarm-1-v3-readiness-v3")

    def test_parser_operation_is_v3(self) -> None:
        self.assertEqual(self.record(holo.CATALYTIC_SWARM_1_V3_PARSER_CANARY_PATH)["operation"], "catalytic-swarm-1-v3-parser-canary-v3")

    def test_attempt_operation_is_v3(self) -> None:
        self.assertEqual(self.record(holo.CATALYTIC_SWARM_1_V3_ATTEMPT_PATH)["operation"], "catalytic-swarm-1-v3")

    def test_result_operation_is_v3(self) -> None:
        self.assertEqual(self.record(holo.CATALYTIC_SWARM_1_V3_RESULT_PATH)["operation"], "catalytic-swarm-1-v3")

    def test_task_results_operation_is_v3(self) -> None:
        self.assertEqual(self.record(holo.CATALYTIC_SWARM_1_V3_TASK_RESULTS_PATH)["operation"], "catalytic-swarm-1-v3-task-results")

    def test_primary_contract_hash_is_the_claim_hash(self) -> None:
        record = self.record(holo.CATALYTIC_SWARM_1_V3_RESULT_PATH)
        self.assertEqual(record["contract_sha256"], V3_CLAIM_CONTRACT_SHA256)

    def test_attempt_and_result_use_the_v3_verdict_key(self) -> None:
        for path in (holo.CATALYTIC_SWARM_1_V3_ATTEMPT_PATH, holo.CATALYTIC_SWARM_1_V3_RESULT_PATH):
            self.assertIn("catalytic_swarm_1_v3", self.record(path))

    def test_control_readiness_and_parser_use_v3_stage_keys(self) -> None:
        self.assertIn("control_qualification_v3", self.record(holo.CATALYTIC_SWARM_1_V3_CONTROL_PATH))
        self.assertIn("readiness_v3", self.record(holo.CATALYTIC_SWARM_1_V3_READINESS_PATH))
        self.assertIn("parser_canary_v3", self.record(holo.CATALYTIC_SWARM_1_V3_PARSER_CANARY_PATH))

    def test_no_v3_artifact_contains_a_predecessor_verdict_key(self) -> None:
        for path in holo.CATALYTIC_SWARM_1_V3_ARTIFACT_PATHS:
            if path == holo.CATALYTIC_SWARM_1_V3_LEDGER_PATH:
                continue
            record = self.record(path)
            self.assertNotIn("catalytic_swarm_1", record)
            self.assertNotIn("catalytic_swarm_1_v2", record)

    def test_runtime_binding_is_immutable_v3(self) -> None:
        self.assertEqual(self.binding.runtime_version, "v3")
        self.assertEqual(self.binding.schema_version, 3)
        self.assertEqual(self.binding.attempt_version, 3)

    def test_cpu_only_identity_checks_do_not_construct_a_sidecar(self) -> None:
        with mock.patch.object(holo, "LiveSidecar") as sidecar:
            self.record(holo.CATALYTIC_SWARM_1_V3_RESULT_PATH)
        sidecar.assert_not_called()

    def test_root_terminal_law_is_unchanged(self) -> None:
        evaluator = json.loads((ROOT / "lab" / "EVALUATOR.json").read_text())
        self.assertEqual(
            evaluator["catalytic_swarm_1_v2"]["cache_admission_law"],
            evaluator["catalytic_swarm_1_v3"]["cache_admission_law"],
        )


if __name__ == "__main__":
    unittest.main()
