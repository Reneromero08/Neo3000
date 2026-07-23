#!/usr/bin/env python3
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalytic_frontier_full_prompt_latency as full_prompt
import catalytic_frontier_single_request_latency as latency


class CatalyticFrontierFullPromptLatencyTests(unittest.TestCase):
    def test_full_prompt_boundary_is_exactly_690_with_forced_one_token_reevaluation(self) -> None:
        selected = latency.select_root_boundary(
            "full-prompt",
            prompt_tokens=list(range(543)),
            branch_tokens=list(range(690)),
        )
        self.assertEqual(selected["tokens"], list(range(690)))
        self.assertEqual(selected["expected_root_tokens"], 690)
        self.assertEqual(selected["expected_cached_prompt_tokens"], 689)
        self.assertEqual(selected["expected_fresh_prompt_tokens"], 1)

    def test_task_a_boundary_remains_backward_compatible(self) -> None:
        selected = latency.select_root_boundary(
            "task-a",
            prompt_tokens=list(range(543)),
            branch_tokens=list(range(690)),
        )
        self.assertEqual(selected["tokens"], list(range(543)))
        self.assertEqual(selected["expected_cached_prompt_tokens"], 543)
        self.assertEqual(selected["expected_fresh_prompt_tokens"], 147)
        self.assertIsNone(selected["predecessor_medians"])

    def test_full_prompt_reference_is_bound_to_neo_exp_0062_medians(self) -> None:
        reference = latency.ROOT_BOUNDARIES["full-prompt"]["predecessor_medians"]
        self.assertEqual(reference["prompt_ms"], 2498.008)
        self.assertEqual(reference["ttft_seconds_including_restore"], 2.6165000000037253)
        self.assertEqual(reference["effective_wall_seconds_including_restore"], 2.9130000000077416)
        direct = latency.ROOT_BOUNDARIES["full-prompt"]["predecessor_direct_medians"]
        self.assertEqual(direct["prompt_ms"], 10185.8015)
        self.assertEqual(direct["ttft_seconds"], 10.25800000000163)
        self.assertEqual(direct["effective_wall_seconds"], 10.57050000000163)
        self.assertEqual(latency.MAX_DIRECT_CONTROL_DRIFT_FRACTION, 0.10)

    def test_predecessor_improvement_gate_is_required(self) -> None:
        verdict = latency.classify_result(
            utility_exact=True,
            paired_wins=4,
            prompt_speedup=10.0,
            ttft_speedup=10.0,
            effective_wall_speedup=10.0,
            full_lifecycle_wall_advantage=True,
            full_lifecycle_fresh_advantage=True,
            predecessor_improvement_gate=False,
        )
        self.assertEqual(verdict, "exact-reuse-without-preregistered-latency-gate")

    def test_direct_control_drift_gate_is_required(self) -> None:
        verdict = latency.classify_result(
            utility_exact=True,
            paired_wins=4,
            prompt_speedup=10.0,
            ttft_speedup=10.0,
            effective_wall_speedup=10.0,
            full_lifecycle_wall_advantage=True,
            full_lifecycle_fresh_advantage=True,
            predecessor_improvement_gate=True,
            direct_control_drift_gate=False,
        )
        self.assertEqual(verdict, "exact-reuse-without-preregistered-latency-gate")

    def test_dedicated_entrypoint_selects_only_full_prompt_boundary(self) -> None:
        source = inspect.getsource(full_prompt)
        self.assertIn('latency.main(root_boundary="full-prompt")', source)
        self.assertNotIn("fanout", source.lower())
        self.assertEqual(inspect.signature(latency.main).parameters["root_boundary"].default, "task-a")

    def test_server_forces_one_token_reevaluation_on_exact_match(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        source = (repository / "tools/server/server-context.cpp").read_text(encoding="utf-8")
        marker = "if (n_past == slot.task->n_tokens() && n_past > 0)"
        start = source.index(marker)
        block = source[start : start + 400]
        self.assertIn("n_past--;", block)
        self.assertLess(block.index(marker), block.index("n_past--;"))

    def test_unknown_boundary_fails_closed(self) -> None:
        with self.assertRaises(latency.harness.FrontierHarnessError):
            latency.select_root_boundary(
                "unknown",
                prompt_tokens=list(range(543)),
                branch_tokens=list(range(690)),
            )


if __name__ == "__main__":
    unittest.main()
