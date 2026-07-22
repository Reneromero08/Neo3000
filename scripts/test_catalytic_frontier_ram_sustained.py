#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalytic_frontier_ram_sustained as sustained


class CatalyticFrontierSustainedTests(unittest.TestCase):
    def test_phase_family_is_defined_for_arbitrarily_large_finite_ticks(self) -> None:
        expected = {0: "A", 1: "C", 2: "D", 3: "B", 4: "A", 10: "D", 1_000_003: "B"}
        for tick, phase in expected.items():
            self.assertEqual(sustained.phase_at(tick), phase)
            self.assertEqual(sustained.branch_spec(tick)["answer"], phase)

    def test_negative_tick_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            sustained.phase_at(-1)

    def test_route_failure_classification_separates_carrier_from_task(self) -> None:
        self.assertEqual(sustained.classify_route_failure("D", "C", "D"), "carrier-route-divergence")
        self.assertEqual(sustained.classify_route_failure("D", "C", "C"), "task-or-model-utility-failure")
        self.assertEqual(sustained.classify_route_failure("D", "C", "B"), "independent-route-disagreement")
        self.assertEqual(sustained.classify_route_failure("D", "D", "D"), "no-failure")

    def test_geometric_milestones_cover_every_power_of_two(self) -> None:
        self.assertEqual(sustained.geometric_milestones(2), (2,))
        self.assertEqual(sustained.geometric_milestones(16), (2, 4, 8, 16))
        self.assertEqual(sustained.geometric_milestones(128), (2, 4, 8, 16, 32, 64, 128))
        with self.assertRaises(ValueError):
            sustained.geometric_milestones(12)

    def test_branch_questions_are_distinct_without_panel_storage(self) -> None:
        questions = {sustained.branch_spec(tick)["question"] for tick in range(1, 257)}
        self.assertEqual(len(questions), 256)
        self.assertFalse(hasattr(sustained, "PANEL"))

    def test_online_stats_use_constant_scalar_state(self) -> None:
        stats = sustained.OnlineStats()
        for value in (3.0, 7.0, 5.0):
            stats.add(value)
        self.assertEqual(set(vars(stats)), {"count", "total", "minimum", "maximum"})
        self.assertEqual(
            stats.as_dict(),
            {"count": 3, "mean": 5.0, "minimum": 3.0, "maximum": 7.0},
        )

    def test_saved_root_checkpoint_count_tracks_launch_control(self) -> None:
        self.assertEqual(
            sustained.validate_saved_root_checkpoint_count(
                {"n_checkpoints": 0},
                context_checkpoints=0,
            ),
            0,
        )
        self.assertEqual(
            sustained.validate_saved_root_checkpoint_count(
                {"n_checkpoints": 1},
                context_checkpoints=8,
            ),
            1,
        )
        for context_checkpoints, observed in ((0, 1), (8, 0), (7, 0)):
            with self.subTest(context_checkpoints=context_checkpoints, observed=observed):
                with self.assertRaises(sustained.harness.FrontierHarnessError):
                    sustained.validate_saved_root_checkpoint_count(
                        {"n_checkpoints": observed},
                        context_checkpoints=context_checkpoints,
                    )

    def test_checkpoint_cli_exposes_zero_control(self) -> None:
        with mock.patch.object(
            sys,
            "argv",
            ["catalytic_frontier_ram_sustained.py", "--ctx-checkpoints", "0"],
        ):
            args = sustained.parse_args()
        self.assertEqual(args.ctx_checkpoints, 0)

    def test_sustained_acceptance_requires_both_routes_and_exact_generated_tokens(self) -> None:
        self.assertEqual(
            sustained.classify_sustained_result(
                catalytic_correct=16,
                direct_correct=16,
                fanout_count=16,
                answer_digests_equal=True,
                generated_digests_equal=True,
            ),
            "accepted-exact-sustained-reuse",
        )

    def test_sustained_acceptance_preserves_direct_control_failure(self) -> None:
        self.assertEqual(
            sustained.classify_sustained_result(
                catalytic_correct=16,
                direct_correct=15,
                fanout_count=16,
                answer_digests_equal=False,
                generated_digests_equal=False,
            ),
            "direct-control-utility-failure",
        )

    def test_sustained_acceptance_preserves_carrier_failure(self) -> None:
        self.assertEqual(
            sustained.classify_sustained_result(
                catalytic_correct=15,
                direct_correct=16,
                fanout_count=16,
                answer_digests_equal=False,
                generated_digests_equal=False,
            ),
            "carrier-route-utility-failure",
        )

    def test_sustained_acceptance_rejects_generated_token_divergence(self) -> None:
        self.assertEqual(
            sustained.classify_sustained_result(
                catalytic_correct=16,
                direct_correct=16,
                fanout_count=16,
                answer_digests_equal=True,
                generated_digests_equal=False,
            ),
            "generated-token-divergence",
        )


if __name__ == "__main__":
    unittest.main()
