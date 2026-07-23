#!/usr/bin/env python3
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalytic_frontier_single_request_latency as latency
import catalytic_frontier_strict_prefix_latency as strict_prefix


class CatalyticFrontierStrictPrefixLatencyTests(unittest.TestCase):
    def test_boundary_is_exactly_the_frozen_prompt_minus_its_last_token(self) -> None:
        branch = list(range(690))
        selected = latency.select_root_boundary(
            "strict-prefix",
            prompt_tokens=list(range(543)),
            branch_tokens=branch,
        )
        self.assertEqual(selected["tokens"], branch[:-1])
        self.assertEqual(selected["tokens"][-1], branch[-2])
        self.assertNotIn(branch[-1], selected["tokens"])
        self.assertEqual(selected["expected_root_tokens"], 689)
        self.assertEqual(selected["expected_cached_prompt_tokens"], 689)
        self.assertEqual(selected["expected_fresh_prompt_tokens"], 1)

    def test_submitted_branch_contract_remains_690_tokens(self) -> None:
        self.assertEqual(latency.EXPECTED_BRANCH_PROMPT_TOKENS, 690)
        self.assertEqual(
            latency.ROOT_BOUNDARIES["strict-prefix"]["expected_root_tokens"] + 1,
            latency.EXPECTED_BRANCH_PROMPT_TOKENS,
        )

    def test_materialization_seed_path_is_shared_with_predecessors(self) -> None:
        source = inspect.getsource(latency.evaluate)
        self.assertEqual(source.count('derive_seed(ROOT_ID, "single-request-latency-prompt-root-materialize")'), 1)
        self.assertNotIn("strict-prefix-materialize", source)

    def test_dedicated_entrypoint_selects_only_strict_prefix(self) -> None:
        source = inspect.getsource(strict_prefix)
        self.assertIn('latency.main(root_boundary="strict-prefix")', source)
        self.assertNotIn("fanout", source.lower())

    def test_successor_label_names_strict_prefix_not_full_prompt(self) -> None:
        source = inspect.getsource(latency.evaluate)
        self.assertIn("PROFILE_DECODE_AND_RESTORE_OVERHEAD_AFTER_STRICT_PREFIX_ROOT", source)
        self.assertIn('if root_boundary == "strict-prefix"', source)

    def test_source_geometry_distinguishes_new_token_from_exact_match(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        source = (repository / "tools/server/server-context.cpp").read_text(encoding="utf-8")
        self.assertIn("const bool has_new_tokens = (n_past < slot.task->n_tokens());", source)
        self.assertIn("pos_next - n_swa - (has_new_tokens ? 0 : 1)", source)
        self.assertIn("if (n_past == slot.task->n_tokens() && n_past > 0)", source)

    def test_predecessor_and_direct_drift_gates_are_inherited(self) -> None:
        selected = latency.ROOT_BOUNDARIES["strict-prefix"]
        self.assertEqual(selected["predecessor_medians"], latency.ROOT_BOUNDARIES["full-prompt"]["predecessor_medians"])
        self.assertEqual(
            selected["predecessor_direct_medians"],
            latency.ROOT_BOUNDARIES["full-prompt"]["predecessor_direct_medians"],
        )
        self.assertEqual(latency.MAX_DIRECT_CONTROL_DRIFT_FRACTION, 0.10)

    def test_default_and_rejected_boundaries_remain_unchanged(self) -> None:
        task_a = latency.ROOT_BOUNDARIES["task-a"]
        full = latency.ROOT_BOUNDARIES["full-prompt"]
        self.assertEqual((task_a["expected_root_tokens"], task_a["expected_cached_prompt_tokens"]), (543, 543))
        self.assertEqual((full["expected_root_tokens"], full["expected_cached_prompt_tokens"]), (690, 689))
        self.assertEqual(inspect.signature(latency.main).parameters["root_boundary"].default, "task-a")


if __name__ == "__main__":
    unittest.main()
