#!/usr/bin/env python3
"""CPU-only custody and root-law checks for the unexecuted CS1-v2 runner."""

from __future__ import annotations

import unittest
from pathlib import Path

from catalytic_swarm_1_v2_protocol import (
    build_cache_diagnostic_evidence_binding,
    build_catalytic_swarm_1_v2_contract,
)
from catalytic_swarm_1_v2_root_law import (
    RootCacheObservation,
    adjudicate_root_cache,
)


ROOT = Path(__file__).resolve().parents[1]


def observation(**changes: object) -> RootCacheObservation:
    values: dict[str, object] = {
        "public_root_terminal_token_index": 4820,
        "common_prefix_tokens": 4825,
        "legacy_required_cached_prompt_tokens": 4825,
        "actual_cached_prompt_tokens": 4822,
        "branch_prompt_tokens": 4848,
        "fresh_prompt_tokens": 26,
        "completion_tokens": 9,
        "response_completed": True,
        "transport_passed": True,
        "token_evidence_passed": True,
    }
    values.update(changes)
    return RootCacheObservation(**values)  # type: ignore[arg-type]


class CatalyticSwarm1V2ControllerTests(unittest.TestCase):
    def test_minimal_diagnostic_observation_passes_root_law(self) -> None:
        self.assertTrue(adjudicate_root_cache(observation()).admitted)

    def test_realistic_diagnostic_observation_passes_root_law(self) -> None:
        self.assertTrue(adjudicate_root_cache(observation(branch_prompt_tokens=5020, fresh_prompt_tokens=198)).admitted)

    def test_same_observation_fails_legacy_threshold(self) -> None:
        value = observation()
        self.assertLess(value.actual_cached_prompt_tokens, value.legacy_required_cached_prompt_tokens)

    def test_cache_below_root_rejects(self) -> None:
        self.assertFalse(adjudicate_root_cache(observation(actual_cached_prompt_tokens=4819, fresh_prompt_tokens=29)).admitted)

    def test_prefix_before_root_rejects(self) -> None:
        self.assertFalse(adjudicate_root_cache(observation(
            common_prefix_tokens=4819,
            legacy_required_cached_prompt_tokens=4819,
        )).admitted)

    def test_incomplete_response_rejects(self) -> None:
        self.assertFalse(adjudicate_root_cache(observation(response_completed=False)).admitted)

    def test_transport_failure_rejects(self) -> None:
        self.assertFalse(adjudicate_root_cache(observation(transport_passed=False)).admitted)

    def test_token_evidence_failure_rejects(self) -> None:
        self.assertFalse(adjudicate_root_cache(observation(token_evidence_passed=False)).admitted)

    def test_legacy_threshold_is_provenance_only(self) -> None:
        result = adjudicate_root_cache(observation())
        self.assertEqual(result.legacy_threshold_delta_tokens, -3)
        self.assertEqual(result.legacy_threshold_overreach_tokens, 5)

    def test_successor_paths_are_separate(self) -> None:
        paths = build_catalytic_swarm_1_v2_contract()["one_shot"]["paths"]
        self.assertTrue(all(path.startswith("state/catalytic_swarm_1_v2/") for path in paths.values()))

    def test_real_v2_state_root_remains_absent(self) -> None:
        self.assertFalse((ROOT / "state" / "catalytic_swarm_1_v2").exists())

    def test_v1_and_diagnostic_remain_retired(self) -> None:
        source = (ROOT / "scripts" / "holostate_live.py").read_text(encoding="utf-8")
        self.assertIn("CatalyticSwarm-1 v1 is executed and must not be rerun", source)
        self.assertIn("cache diagnostic is executed and must not be rerun", source)

    def test_v2_command_requires_explicit_model_and_main(self) -> None:
        source = (ROOT / "scripts" / "holostate_live.py").read_text(encoding="utf-8")
        self.assertIn('"audit-catalytic-swarm-1-v2"', source)
        self.assertIn('catalytic_swarm_1_v2.add_argument("--model", required=True)', source)
        self.assertIn('catalytic_swarm_1_v2.add_argument("--authorized-main", required=True)', source)

    def test_frozen_suite_and_arm_hashes_are_unchanged(self) -> None:
        geometry = build_catalytic_swarm_1_v2_contract()["frozen_geometry"]
        self.assertEqual(geometry["task_suite_sha256"], "4B9961D5054BE5D98EF315D2DEAE9D1604E0042A69CB02A8B81FDF513BC1FC92")
        self.assertEqual(len(geometry["arm_plan_hashes"]), 4)

    def test_full_terminal_counts_are_frozen(self) -> None:
        geometry = build_catalytic_swarm_1_v2_contract()["frozen_geometry"]
        self.assertEqual((2 * geometry["total_model_requests"], geometry["total_model_requests"], geometry["task_count"]), (2064, 1032, 8))

    def test_claim_limits_remain_locked(self) -> None:
        contract = build_catalytic_swarm_1_v2_contract()
        self.assertEqual(contract["claim_limits"]["SOTA_SWARM_CLAIM"], "LOCKED")
        self.assertFalse(contract["claim_limits"]["automatic_promotion"])


if __name__ == "__main__":
    unittest.main()
