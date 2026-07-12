#!/usr/bin/env python3
from __future__ import annotations

import unittest

from catalytic_swarm_1_v3_protocol import (
    EXPECTED_V3_CONTRACT_SHA256,
    V2_CONTRACT_SHA256,
    V2_PRECLAIM_BOUNDARY_SHA256,
    V3_OVERLAY_SHA256,
    CatalyticSwarm1V3ProtocolError,
    apply_v3_overlay_unchecked,
    build_catalytic_swarm_1_v3_contract,
    build_catalytic_swarm_1_v3_overlay,
    build_v2_preclaim_boundary,
    sha256_object,
    validate_v2_preclaim_boundary,
    validate_v3_overlay,
)


def synthetic_v2() -> dict:
    return {
        "id": "catalytic_swarm_1_v2",
        "schema_version": 2,
        "attempt_version": 2,
        "objective": "unchanged equal-budget task-advantage comparison",
        "one_shot": {
            "paths": {
                "control": "state/catalytic_swarm_1_v2/control-qualification-v2.json",
                "readiness": "state/catalytic_swarm_1_v2/readiness-v2.json",
                "parser_canary": "state/catalytic_swarm_1_v2/parser-canary-v2.json",
                "attempt": "state/catalytic_swarm_1_v2/attempt-v2.json",
                "result": "state/catalytic_swarm_1_v2/result-v2.json",
                "ledger": "state/catalytic_swarm_1_v2/ledger-v2.jsonl",
                "task_results": "state/catalytic_swarm_1_v2/task-results-v2.json",
            },
            "no_retry": True,
        },
        "predecessors": {"cache_diagnostic": {"verdict": "reviewable-accept"}},
        "frozen_geometry": {
            "task_count": 8,
            "total_model_requests": 1032,
            "arm_plan_hashes": {
                "serial-chain": "A",
                "best-of-n": "B",
                "sparse-swarm": "C",
                "verified-swarm": "D",
            },
        },
        "claim_limits": {
            "SOTA_SWARM_CLAIM": "LOCKED",
            "PROCESS_LOCAL_HOLOSTATE_AVAILABLE": "LOCKED",
            "RESTART_PERSISTENT_HOLOSTATE_AVAILABLE": "LOCKED",
            "automatic_promotion": False,
        },
        "causal_intervention": {
            "successor_gate": "actual_cached_prompt_tokens >= public_root_terminal_token_index",
        },
    }


class PreclaimBoundaryTests(unittest.TestCase):
    def test_preclaim_boundary_hash_is_exact(self) -> None:
        value = build_v2_preclaim_boundary()
        self.assertEqual(sha256_object(value), V2_PRECLAIM_BOUNDARY_SHA256)
        validate_v2_preclaim_boundary(value)

    def test_boundary_records_zero_live_execution(self) -> None:
        value = build_v2_preclaim_boundary()
        self.assertEqual(value["runtime"]["model_requests"], 0)
        self.assertEqual(value["runtime"]["sidecar_launches"], 0)
        self.assertEqual(value["runtime"]["v2_artifacts_claimed"], 0)
        self.assertTrue(value["runtime"]["v2_state_root_absent"])
        self.assertTrue(value["stop"]["fail_closed"])

    def test_boundary_mutation_rejects(self) -> None:
        value = build_v2_preclaim_boundary()
        value["runtime"]["model_requests"] = 1
        with self.assertRaises(CatalyticSwarm1V3ProtocolError):
            validate_v2_preclaim_boundary(value)


class OverlayTests(unittest.TestCase):
    def test_overlay_hash_is_exact(self) -> None:
        value = build_catalytic_swarm_1_v3_overlay()
        self.assertEqual(sha256_object(value), V3_OVERLAY_SHA256)
        validate_v3_overlay(value)

    def test_overlay_changes_only_versioned_custody_surface(self) -> None:
        base = synthetic_v2()
        successor = apply_v3_overlay_unchecked(base)
        self.assertEqual(successor["id"], "catalytic_swarm_1_v3")
        self.assertEqual(successor["schema_version"], 3)
        self.assertEqual(successor["attempt_version"], 3)
        self.assertEqual(successor["frozen_geometry"], base["frozen_geometry"])
        self.assertEqual(successor["claim_limits"], base["claim_limits"])
        self.assertEqual(successor["causal_intervention"], base["causal_intervention"])
        self.assertTrue(
            all(
                path.startswith("state/catalytic_swarm_1_v3/")
                for path in successor["one_shot"]["paths"].values()
            )
        )

    def test_v2_preclaim_is_added_without_erasing_prior_predecessors(self) -> None:
        base = synthetic_v2()
        successor = apply_v3_overlay_unchecked(base)
        self.assertIn("cache_diagnostic", successor["predecessors"])
        boundary = successor["predecessors"]["catalytic_swarm_1_v2_preclaim"]
        self.assertEqual(boundary["sha256"], V2_PRECLAIM_BOUNDARY_SHA256)
        self.assertEqual(boundary["model_requests"], 0)
        self.assertEqual(boundary["artifacts_claimed"], 0)
        self.assertTrue(boundary["no_retry"])

    def test_namespace_repair_forbids_inherited_v1_map(self) -> None:
        successor = apply_v3_overlay_unchecked(synthetic_v2())
        repair = successor["versioned_namespace_repair"]
        self.assertFalse(repair["inherited_v1_path_map_consulted"])
        self.assertTrue(
            repair["contract_path_map_compared_to_active_version_artifact_tuple"]
        )
        self.assertEqual(repair["base_contract_sha256"], V2_CONTRACT_SHA256)

    def test_overlay_mutation_rejects(self) -> None:
        value = build_catalytic_swarm_1_v3_overlay()
        value["execution_geometry"]["total_model_requests"] = 1031
        with self.assertRaises(CatalyticSwarm1V3ProtocolError):
            validate_v3_overlay(value)

    def test_unverified_base_contract_rejects(self) -> None:
        with self.assertRaisesRegex(
            CatalyticSwarm1V3ProtocolError, "base contract hash changed"
        ):
            build_catalytic_swarm_1_v3_contract(synthetic_v2())

    def test_claim_limits_remain_locked(self) -> None:
        overlay = build_catalytic_swarm_1_v3_overlay()
        self.assertEqual(overlay["claim_limits"]["SOTA_SWARM_CLAIM"], "LOCKED")
        self.assertEqual(
            overlay["claim_limits"]["PROCESS_LOCAL_HOLOSTATE_AVAILABLE"],
            "LOCKED",
        )
        self.assertFalse(overlay["claim_limits"]["automatic_promotion"])

    def test_complete_effective_contract_hash_is_frozen_independently(self) -> None:
        from catalytic_swarm_1_v3_protocol import effective_v3_contract_sha256

        self.assertEqual(
            effective_v3_contract_sha256(), EXPECTED_V3_CONTRACT_SHA256
        )


if __name__ == "__main__":
    unittest.main()
