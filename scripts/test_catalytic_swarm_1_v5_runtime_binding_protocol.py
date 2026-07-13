#!/usr/bin/env python3
from __future__ import annotations

import unittest

from catalytic_swarm_1_v5_runtime_binding_protocol import (
    EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256,
    build_v5_runtime_evidence_contract,
    sha256_object,
    validate_v5_runtime_evidence_contract,
)


class V5RuntimeBindingProtocolTests(unittest.TestCase):
    def test_complete_contract_hash_is_exact(self) -> None:
        contract = build_v5_runtime_evidence_contract()
        self.assertEqual(sha256_object(contract), EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256)
        validate_v5_runtime_evidence_contract(contract)

    def test_completion_closure_is_bound_before_enforcement(self) -> None:
        law = build_v5_runtime_evidence_contract()["evidence_law"]
        self.assertTrue(law["empty_ledger_claimed_before_first_model_request"])
        self.assertTrue(law["every_completed_response_identity_bound_before_append"])
        self.assertTrue(law["ledger_record_fsynced_before_acceptance_enforcement"])


if __name__ == "__main__":
    unittest.main()
