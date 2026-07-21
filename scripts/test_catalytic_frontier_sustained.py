#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalytic_frontier_sustained as sustained


class CatalyticFrontierSustainedTests(unittest.TestCase):
    def test_phase_family_is_defined_for_arbitrarily_large_finite_ticks(self) -> None:
        expected = {0: "A", 1: "C", 2: "D", 3: "B", 4: "A", 10: "D", 1_000_003: "B"}
        for tick, phase in expected.items():
            self.assertEqual(sustained.phase_at(tick), phase)
            self.assertEqual(sustained.branch_spec(tick)["answer"], phase)

    def test_negative_tick_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            sustained.phase_at(-1)

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


if __name__ == "__main__":
    unittest.main()
