#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest

from catalytic_swarm_1_v2_protocol import (
    DIAGNOSTIC_EVIDENCE_SHA256,
    EXPECTED_CONTRACT_SHA256,
    CatalyticSwarm1V2ProtocolError,
    build_cache_diagnostic_evidence_binding,
    build_catalytic_swarm_1_v2_contract,
    sha256_object,
    validate_cache_diagnostic_evidence_binding,
    validate_catalytic_swarm_1_v2_contract,
)


class DiagnosticEvidenceBindingTests(unittest.TestCase):
    def test_reported_diagnostic_evidence_hash_is_exact(self):
        evidence = build_cache_diagnostic_evidence_binding()
        self.assertEqual(sha256_object(evidence), DIAGNOSTIC_EVIDENCE_SHA256)
        validate_cache_diagnostic_evidence_binding(evidence)

    def test_both_reported_probes_cover_the_root(self):
        evidence = build_cache_diagnostic_evidence_binding()
        for probe in evidence["probes"].values():
            self.assertGreaterEqual(
                probe["actual_cached_prompt_tokens"],
                probe["public_root_terminal_token_index"],
            )
            self.assertLess(
                probe["actual_cached_prompt_tokens"],
                probe["legacy_required_cached_prompt_tokens"],
            )

    def test_artifact_mutation_changes_evidence_hash(self):
        evidence = build_cache_diagnostic_evidence_binding()
        evidence["artifacts"]["result"] = "0" * 64
        with self.assertRaises(CatalyticSwarm1V2ProtocolError):
            validate_cache_diagnostic_evidence_binding(evidence)


class CatalyticSwarm1V2ContractTests(unittest.TestCase):
    def test_contract_hash_is_exact(self):
        contract = build_catalytic_swarm_1_v2_contract()
        self.assertEqual(
            EXPECTED_CONTRACT_SHA256,
            "911242c74509f1d2d8c6a3c8aa82948c452dac5f4646dd97d70d7b27b750e984",
        )
        self.assertEqual(sha256_object(contract), EXPECTED_CONTRACT_SHA256)
        validate_catalytic_swarm_1_v2_contract(contract)

    def test_only_cache_admission_authority_changes(self):
        contract = build_catalytic_swarm_1_v2_contract()
        intervention = contract["causal_intervention"]
        self.assertEqual(
            intervention["successor_gate"],
            "actual_cached_prompt_tokens >= public_root_terminal_token_index",
        )
        self.assertTrue(
            intervention["legacy_threshold_retained_as_provenance_only"]
        )
        self.assertEqual(
            intervention["only_change"],
            "replace the legacy full warm/branch common-prefix cache threshold with the exact public-root terminal token threshold",
        )

    def test_equal_budget_geometry_is_preserved(self):
        geometry = build_catalytic_swarm_1_v2_contract()["frozen_geometry"]
        self.assertEqual(geometry["task_count"], 8)
        self.assertEqual(geometry["candidate_count_per_task"], 64)
        self.assertEqual(geometry["requests_per_arm_per_task"], 32)
        self.assertEqual(geometry["common_root_warm_requests"], 8)
        self.assertEqual(geometry["comparison_requests"], 1024)
        self.assertEqual(geometry["total_model_requests"], 1032)
        self.assertEqual(geometry["actual_budget_ratio_max"], 1.10)

    def test_successor_has_separate_one_shot_paths(self):
        paths = build_catalytic_swarm_1_v2_contract()["one_shot"]["paths"]
        self.assertEqual(len(paths), 7)
        self.assertTrue(
            all(path.startswith("state/catalytic_swarm_1_v2/") for path in paths.values())
        )
        self.assertTrue(
            all("catalytic_swarm_1/" not in path for path in paths.values())
        )

    def test_task_and_plan_mutations_reject(self):
        for mutate in (
            lambda c: c["frozen_geometry"].__setitem__("task_suite_sha256", "0" * 64),
            lambda c: c["frozen_geometry"]["arm_plan_hashes"].__setitem__(
                "serial-chain", "0" * 64
            ),
            lambda c: c["frozen_geometry"].__setitem__("total_model_requests", 1031),
        ):
            contract = copy.deepcopy(build_catalytic_swarm_1_v2_contract())
            mutate(contract)
            with self.assertRaises(CatalyticSwarm1V2ProtocolError):
                validate_catalytic_swarm_1_v2_contract(contract)

    def test_legacy_threshold_cannot_regain_admission_authority(self):
        contract = build_catalytic_swarm_1_v2_contract()
        contract["causal_intervention"][
            "legacy_threshold_retained_as_provenance_only"
        ] = False
        with self.assertRaises(CatalyticSwarm1V2ProtocolError):
            validate_catalytic_swarm_1_v2_contract(contract)

    def test_claim_ceiling_remains_locked(self):
        limits = build_catalytic_swarm_1_v2_contract()["claim_limits"]
        self.assertEqual(limits["SOTA_SWARM_CLAIM"], "LOCKED")
        self.assertEqual(limits["PROCESS_LOCAL_HOLOSTATE_AVAILABLE"], "LOCKED")
        self.assertEqual(
            limits["RESTART_PERSISTENT_HOLOSTATE_AVAILABLE"], "LOCKED"
        )
        self.assertFalse(limits["automatic_promotion"])


if __name__ == "__main__":
    unittest.main()
