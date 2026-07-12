#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest

from catalytic_swarm_1_v3_runtime_binding_protocol import (
    EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256,
    build_v3_runtime_evidence_contract,
    sha256_object,
    validate_v3_runtime_evidence_contract,
)


class V3RuntimeEvidenceProtocolTests(unittest.TestCase):
    def test_complete_object_hash_is_exact(self) -> None:
        contract = build_v3_runtime_evidence_contract()
        self.assertEqual(
            sha256_object(contract),
            EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256,
        )
        validate_v3_runtime_evidence_contract(contract)

    def test_runtime_identity_is_v3(self) -> None:
        identity = build_v3_runtime_evidence_contract()["runtime_identity"]
        self.assertEqual(identity["runtime_version"], "v3")
        self.assertEqual(identity["artifact_schema_version"], 3)
        self.assertEqual(identity["verdict_key"], "catalytic_swarm_1_v3")
        self.assertEqual(identity["state_root"], "state/catalytic_swarm_1_v3")

    def test_claim_and_scheduler_authorities_are_explicit(self) -> None:
        contract = build_v3_runtime_evidence_contract()
        self.assertEqual(
            contract["claim_contract"]["sha256"],
            "433b4d4e418614c2e9c2b177f46b68d24710921b11d8d7e848a226da22c1fd27",
        )
        self.assertEqual(
            contract["scheduler_contract"]["sha256"],
            "fe455e7b049f4fb0b1ab1a13899e3da18b4b2bbec824a664a38599d0a4fd2a3e",
        )

    def test_persistence_law_forbids_late_rename(self) -> None:
        law = build_v3_runtime_evidence_contract()["evidence_law"]
        self.assertTrue(law["v3_verdict_key_present_before_first_persist"])
        self.assertTrue(law["post_persistence_verdict_rename_forbidden"])
        self.assertTrue(law["wrapper_return_identity_equals_persisted_identity"])

    def test_schedule_and_claim_limits_remain_frozen(self) -> None:
        contract = build_v3_runtime_evidence_contract()
        self.assertEqual(contract["execution_geometry"]["total_model_requests"], 1032)
        self.assertEqual(contract["execution_geometry"]["custody_checks"], 2064)
        self.assertEqual(contract["execution_geometry"]["host_checks"], 1032)
        self.assertEqual(contract["execution_geometry"]["task_parity_checks"], 8)
        self.assertEqual(contract["claim_limits"]["SOTA_SWARM_CLAIM"], "LOCKED")
        self.assertFalse(contract["claim_limits"]["automatic_promotion"])

    def test_mutation_changes_hash_and_rejects(self) -> None:
        contract = build_v3_runtime_evidence_contract()
        changed = copy.deepcopy(contract)
        changed["runtime_identity"]["verdict_key"] = "catalytic_swarm_1"
        self.assertNotEqual(
            sha256_object(changed),
            EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256,
        )
        with self.assertRaises(ValueError):
            validate_v3_runtime_evidence_contract(changed)


if __name__ == "__main__":
    unittest.main()
