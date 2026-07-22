#!/usr/bin/env python3
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalytic_frontier_water_panel_qualifier as qualifier


class CatalyticFrontierWaterPanelQualifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        repository = Path(__file__).resolve().parents[1]
        corpus = qualifier.harness.carrier.load_public_corpus(repository)
        cls.root = next(item for item in corpus["roots"] if item["root_id"] == qualifier.ROOT_ID)

    def test_water_panel_preserves_public_branches_and_freezes_sixteen(self) -> None:
        panel = qualifier.panel_for(self.root)
        self.assertEqual(len(panel), 16)
        self.assertEqual(len({item["question"] for item in panel}), 16)
        self.assertEqual(panel[0]["question"], self.root["branches"][0]["question"])
        self.assertEqual(panel[1]["question"], self.root["branches"][1]["question"])

    def test_frozen_sequence_is_balanced(self) -> None:
        panel = qualifier.panel_for(self.root)
        sequence = "".join(panel[number - 1]["answer"] for number in qualifier.PANEL_ORDER)
        self.assertEqual(sequence, "BACDABCDABCDABCD")
        self.assertEqual({label: sequence.count(label) for label in "ABCD"}, {"A": 4, "B": 4, "C": 4, "D": 4})

    def test_evaluate_uses_only_water_panel_and_exact_gate(self) -> None:
        panel_result = {"qualified": True, "correct": 16}
        with mock.patch.object(qualifier.base, "evaluate_panel", return_value=panel_result) as evaluate_panel:
            result = qualifier.evaluate(
                sidecar=object(),
                codec=object(),
                props={},
                root=self.root,
                baseline_private=None,
            )
        self.assertEqual(result["verdict"], "accept")
        self.assertEqual(result["classification"], "water-direct-panel-qualified")
        self.assertEqual(result["carrier_operations"], 0)
        self.assertEqual(result["snapshot_operations"], 0)
        self.assertEqual(result["cache_enabled_branches"], 0)
        self.assertEqual(evaluate_panel.call_count, 1)
        kwargs = evaluate_panel.call_args.kwargs
        self.assertEqual(kwargs["branch_order_override"], qualifier.PANEL_ORDER)
        self.assertEqual(len(kwargs["panel_override"]), 16)

    def test_controller_has_no_carrier_snapshot_retry_or_cache_enabled_path(self) -> None:
        source = inspect.getsource(qualifier)
        self.assertNotIn("ram_root_action", source)
        self.assertNotIn("snapshot_action", source)
        self.assertNotIn("cache_prompt=True", source)
        self.assertNotIn("retry", source.lower().replace("non-retry", ""))

    def test_checkpoint_cli_is_fixed_to_zero(self) -> None:
        with mock.patch.object(sys, "argv", ["catalytic_frontier_water_panel_qualifier.py"]):
            args = qualifier.parse_args()
        self.assertEqual(args.ctx_checkpoints, 0)


if __name__ == "__main__":
    unittest.main()
