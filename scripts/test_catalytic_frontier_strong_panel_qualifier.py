#!/usr/bin/env python3
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalytic_frontier_strong_panel_qualifier as qualifier


class CatalyticFrontierStrongPanelQualifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        repository = Path(__file__).resolve().parents[1]
        corpus = qualifier.harness.carrier.load_public_corpus(repository)
        cls.roots = {str(item["root_id"]): item for item in corpus["roots"]}

    def test_strong_panels_preserve_original_eight_and_freeze_sixteen(self) -> None:
        for root_id in qualifier.ROOT_IDS:
            with self.subTest(root_id=root_id):
                original = qualifier.fanout.panel_for(self.roots[root_id])
                panel = qualifier.strong_panel_for(self.roots[root_id])
                self.assertEqual(panel[:8], original)
                self.assertEqual(len(panel), 16)
                self.assertEqual(len({item["question"] for item in panel}), 16)
                self.assertEqual(
                    set(qualifier.PANEL_ORDERS[root_id]),
                    set(range(1, 17)),
                )

    def test_frozen_answer_sequences_and_label_distribution(self) -> None:
        expected = {
            "mb-runtime-datacenter-01": "ACBADCABCBDA CBDD".replace(" ", ""),
            "mb-runtime-coldchain-02": "BAD CABDCCBDACBDA".replace(" ", ""),
        }
        for root_id in qualifier.ROOT_IDS:
            panel = qualifier.strong_panel_for(self.roots[root_id])
            sequence = "".join(panel[number - 1]["answer"] for number in qualifier.PANEL_ORDERS[root_id])
            self.assertEqual(sequence, expected[root_id])
            counts = {label: sequence.count(label) for label in "ABCD"}
            self.assertEqual(counts, {"A": 4, "B": 4, "C": 4, "D": 4})

    def test_direct_qualification_requires_exact_sixteen(self) -> None:
        self.assertEqual(
            qualifier.classify_direct_panel(correct=16, total=16),
            "exact-direct-baseline-qualified",
        )
        self.assertEqual(
            qualifier.classify_direct_panel(correct=15, total=16),
            "direct-baseline-rejected",
        )
        with self.assertRaises(qualifier.harness.FrontierHarnessError):
            qualifier.classify_direct_panel(correct=16, total=15)

    def test_evaluate_panel_hashes_inputs_and_retains_wrong_answers(self) -> None:
        root_id = "mb-runtime-datacenter-01"
        root = self.roots[root_id]
        panel = qualifier.strong_panel_for(root)
        order = qualifier.PANEL_ORDERS[root_id]
        answers = [str(panel[number - 1]["answer"]) for number in order]
        answers[-1] = "A" if answers[-1] != "A" else "B"

        class FakeCodec:
            def render_messages(self, *_args: object, **_kwargs: object) -> str:
                return "rendered-task-a"

            def tokenize(self, _text: str) -> list[int]:
                return [101, 102]

        task_a = {
            "content": "task-a",
            "prompt_tokens": 2,
            "cached_prompt_tokens": 0,
            "fresh_prompt_tokens": 2,
            "completion_tokens": 1,
            "fresh_model_tokens": 3,
            "wall_seconds": 0.25,
            "execution": {"generated_token_sha256": "0" * 64},
        }
        branch_records = [
            {
                "content": answer,
                "prompt_tokens": 4,
                "cached_prompt_tokens": 0,
                "fresh_prompt_tokens": 4,
                "completion_tokens": 1,
                "fresh_model_tokens": 5,
                "wall_seconds": 0.5,
                "execution": {"generated_token_sha256": f"{index:064x}"},
            }
            for index, answer in enumerate(answers, start=1)
        ]
        with (
            mock.patch.object(qualifier.harness, "run_completion", side_effect=[task_a, *branch_records]),
            mock.patch.object(
                qualifier.harness.carrier,
                "parse_task_a_output",
                return_value={"answer": qualifier.harness.EXPECTED[root_id]["task_a"]},
            ),
            mock.patch.object(qualifier.harness, "root_capture", return_value={}),
            mock.patch.object(
                qualifier.harness.carrier,
                "derive_retained_root",
                return_value={
                    "retained_root_tokens": [101, 102, 103],
                    "retained_root_token_count": 3,
                    "terminal_stop_identity": {"token_id": 999},
                },
            ),
            mock.patch.object(
                qualifier.harness.carrier,
                "derive_continuation_suffix",
                side_effect=[{"suffix_tokens": [200 + index]} for index in range(16)],
            ),
            mock.patch.object(qualifier.harness.carrier, "_branch_payload", return_value={}),
            mock.patch.object(qualifier.harness.carrier, "parse_branch_output", side_effect=lambda value: value),
            mock.patch.object(qualifier.harness, "process_resources", return_value={}),
        ):
            result = qualifier.evaluate_panel(
                sidecar=object(),
                codec=FakeCodec(),
                props={},
                root=root,
                baseline_private=None,
            )

        self.assertEqual(result["correct"], 15)
        self.assertEqual(result["classification"], "direct-baseline-rejected")
        self.assertEqual(len(result["branches"]), 16)
        self.assertFalse(result["branches"][-1]["correct"])
        self.assertTrue(result["all_branches_cache_disabled"])
        self.assertTrue(all(len(item["input_token_sha256"]) == 64 for item in result["branches"]))

    def test_controller_has_no_carrier_or_snapshot_operation(self) -> None:
        source = inspect.getsource(qualifier)
        self.assertNotIn("ram_root_action", source)
        self.assertNotIn("snapshot_action", source)
        self.assertNotIn("cache_prompt=True", source)
        self.assertIn("cache_prompt=False", source)
        self.assertNotIn('record["input_token_sha256"]', source)
        self.assertIn("input_token_hash = harness.sha256_bytes(token_bytes)", source)

    def test_checkpoint_cli_exposes_zero_control(self) -> None:
        with mock.patch.object(
            sys,
            "argv",
            ["catalytic_frontier_strong_panel_qualifier.py", "--ctx-checkpoints", "0"],
        ):
            args = qualifier.parse_args()
        self.assertEqual(args.ctx_checkpoints, 0)


if __name__ == "__main__":
    unittest.main()
