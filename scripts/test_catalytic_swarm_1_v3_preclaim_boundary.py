#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

from catalytic_swarm_1_v3_preclaim_boundary import (
    EXPECTED_V3_PRECLAIM_BOUNDARY_SHA256,
    build_catalytic_swarm_1_v3_preclaim_boundary,
    sha256_object,
    validate_catalytic_swarm_1_v3_preclaim_boundary,
)


ROOT = Path(__file__).resolve().parents[1]


class V3PreclaimBoundaryTests(unittest.TestCase):
    def test_canonical_boundary_hash_is_exact(self) -> None:
        value = build_catalytic_swarm_1_v3_preclaim_boundary()
        self.assertEqual(sha256_object(value), EXPECTED_V3_PRECLAIM_BOUNDARY_SHA256)
        validate_catalytic_swarm_1_v3_preclaim_boundary(value)

    def test_evaluator_binding_is_exact(self) -> None:
        evaluator = json.loads((ROOT / "lab/EVALUATOR.json").read_text(encoding="utf-8"))
        value = evaluator["catalytic_swarm_1_v3_preclaim_boundary"]
        validate_catalytic_swarm_1_v3_preclaim_boundary(value)

    def test_raw_control_artifact_is_exact_and_immutable(self) -> None:
        value = build_catalytic_swarm_1_v3_preclaim_boundary()
        path = ROOT / value["artifact"]["path"]
        self.assertEqual(path.stat().st_size, 960)
        import hashlib
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest().upper(), value["artifact"]["sha256"])

    def test_other_v3_artifacts_remain_absent(self) -> None:
        value = build_catalytic_swarm_1_v3_preclaim_boundary()
        self.assertTrue(all(not (ROOT / path).exists() for path in value["absent_artifact_paths"]))

    def test_boundary_records_zero_live_work_and_locked_claims(self) -> None:
        value = build_catalytic_swarm_1_v3_preclaim_boundary()
        self.assertTrue(value["command"]["authority_consumed"])
        self.assertTrue(value["command"]["no_retry"])
        self.assertEqual(value["runtime"]["model_requests"], 0)
        self.assertEqual(value["runtime"]["sidecar_launches"], 0)
        self.assertEqual(value["runtime"]["wddm_sampling"], "not-started")
        self.assertEqual(value["claims"]["SOTA_SWARM_CLAIM"], "LOCKED")
        self.assertFalse(value["claims"]["automatic_promotion"])


if __name__ == "__main__":
    unittest.main()
