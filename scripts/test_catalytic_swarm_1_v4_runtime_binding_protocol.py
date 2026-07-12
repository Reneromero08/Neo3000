#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest

from catalytic_swarm_1_v4_runtime_binding_protocol import (
    EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256,
    build_v4_runtime_evidence_contract,
    sha256_object,
    validate_v4_runtime_evidence_contract,
)


class V4RuntimeEvidenceProtocolTests(unittest.TestCase):
    def test_complete_object_hash_is_exact(self) -> None:
        value = build_v4_runtime_evidence_contract()
        self.assertEqual(sha256_object(value), EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256)
        validate_v4_runtime_evidence_contract(value)

    def test_runtime_identity_and_predecessor_are_v4_exact(self) -> None:
        value = build_v4_runtime_evidence_contract()
        self.assertEqual(value["runtime_identity"]["runtime_version"], "v4")
        self.assertEqual(value["runtime_identity"]["state_root"], "state/catalytic_swarm_1_v4")
        self.assertTrue(value["predecessor"]["authority_consumed"])

    def test_frozen_geometry_and_claim_limits(self) -> None:
        value = build_v4_runtime_evidence_contract()
        self.assertEqual(value["execution_geometry"]["total_model_requests"], 1032)
        self.assertEqual(value["execution_geometry"]["custody_checks"], 2064)
        self.assertEqual(value["claim_limits"]["SOTA_SWARM_CLAIM"], "LOCKED")
        self.assertFalse(value["claim_limits"]["automatic_promotion"])

    def test_mutation_rejects(self) -> None:
        changed = copy.deepcopy(build_v4_runtime_evidence_contract())
        changed["runtime_identity"]["verdict_key"] = "catalytic_swarm_1_v3"
        with self.assertRaises(ValueError):
            validate_v4_runtime_evidence_contract(changed)


if __name__ == "__main__":
    unittest.main()
