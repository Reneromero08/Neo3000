#!/usr/bin/env python3
"""CPU-only tests for CatalyticSwarm-1 live stop-law helpers."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from catalytic_swarm_1_runtime_safety import (
    ArmedCleanup,
    CatalyticSwarm1RuntimeSafetyError,
    require_custody_snapshot,
    require_host_memory_growth,
    require_task_budget_parity,
)


class CustodyTests(unittest.TestCase):
    def test_exact_snapshot_passes(self) -> None:
        value = {"stable": "stable-v2", "candidate": "candidate-v2"}
        result = require_custody_snapshot(value, dict(value), boundary="post-request")
        self.assertTrue(result["passed"])

    def test_stable_change_fails(self) -> None:
        with self.assertRaisesRegex(CatalyticSwarm1RuntimeSafetyError, "stable-custody-changed"):
            require_custody_snapshot(
                {"stable": "before", "candidate": "same"},
                {"stable": "after", "candidate": "same"},
                boundary="post-request",
            )

    def test_candidate_change_fails(self) -> None:
        with self.assertRaisesRegex(CatalyticSwarm1RuntimeSafetyError, "candidate-custody-changed"):
            require_custody_snapshot(
                {"stable": "same", "candidate": "before"},
                {"stable": "same", "candidate": "after"},
                boundary="post-request",
            )


class HostMemoryTests(unittest.TestCase):
    def test_growth_at_ceiling_passes(self) -> None:
        result = require_host_memory_growth(
            baseline_private_bytes=100,
            current_private_bytes=150,
            ceiling_bytes=50,
            boundary="post-request",
        )
        self.assertEqual(result["growth_bytes"], 50)

    def test_growth_above_ceiling_fails(self) -> None:
        with self.assertRaisesRegex(CatalyticSwarm1RuntimeSafetyError, "exceeded ceiling"):
            require_host_memory_growth(
                baseline_private_bytes=100,
                current_private_bytes=151,
                ceiling_bytes=50,
                boundary="post-request",
            )

    def test_lower_current_private_memory_has_zero_growth(self) -> None:
        result = require_host_memory_growth(
            baseline_private_bytes=100,
            current_private_bytes=90,
            ceiling_bytes=0,
            boundary="post-request",
        )
        self.assertEqual(result["growth_bytes"], 0)


class ParityTests(unittest.TestCase):
    def _comparison(self, **changes: object) -> SimpleNamespace:
        values: dict[str, object] = {
            "budget_parity_passed": True,
            "budget_parity_reasons": (),
            "fresh_prompt_ratio": 1.01,
            "completion_ratio": 1.02,
            "total_model_token_ratio": 1.03,
        }
        values.update(changes)
        return SimpleNamespace(**values)

    def test_passing_parity_is_accepted(self) -> None:
        result = require_task_budget_parity(self._comparison(), ratio_limit=1.10)
        self.assertTrue(result["passed"])

    def test_false_parity_flag_fails(self) -> None:
        with self.assertRaisesRegex(CatalyticSwarm1RuntimeSafetyError, "parity failed"):
            require_task_budget_parity(
                self._comparison(
                    budget_parity_passed=False,
                    budget_parity_reasons=("request-count parity failed",),
                ),
                ratio_limit=1.10,
            )

    def test_ratio_above_limit_fails_even_with_forged_true_flag(self) -> None:
        with self.assertRaisesRegex(CatalyticSwarm1RuntimeSafetyError, "fresh_prompt_ratio-exceeded"):
            require_task_budget_parity(
                self._comparison(fresh_prompt_ratio=1.10001), ratio_limit=1.10
            )


class CleanupTests(unittest.TestCase):
    def test_armed_guard_cleans_on_exception(self) -> None:
        calls: list[str] = []
        with self.assertRaisesRegex(RuntimeError, "boom"):
            with ArmedCleanup(lambda: calls.append("cleanup")):
                raise RuntimeError("boom")
        self.assertEqual(calls, ["cleanup"])

    def test_disarmed_guard_transfers_cleanup_ownership(self) -> None:
        calls: list[str] = []
        with ArmedCleanup(lambda: calls.append("cleanup")) as guard:
            guard.disarm()
        self.assertEqual(calls, [])

    def test_cleanup_failure_does_not_replace_original_exception(self) -> None:
        def fail_cleanup() -> None:
            raise RuntimeError("cleanup failed")

        with self.assertRaisesRegex(ValueError, "primary"):
            with ArmedCleanup(fail_cleanup):
                raise ValueError("primary")


if __name__ == "__main__":
    unittest.main()
