#!/usr/bin/env python3
"""Static tests for the exact CatalyticSwarm-1 runner repair transformer."""

from __future__ import annotations

import ast
import unittest

import apply_catalytic_swarm_1_runtime_safety_patch as patcher


class RuntimePatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = patcher.TARGET.read_text(encoding="utf-8")
        cls.patched = patcher.transform(cls.source)
        cls.tree = ast.parse(cls.patched)

    def test_transform_is_deterministic(self) -> None:
        self.assertEqual(self.patched, patcher.transform(self.source))

    def test_source_is_changed_without_mutating_disk(self) -> None:
        self.assertNotEqual(self.source, self.patched)
        self.assertEqual(patcher.TARGET.read_text(encoding="utf-8"), self.source)

    def test_per_request_boundary_counts_are_terminally_required(self) -> None:
        self.assertIn('"expected_custody_checks": 2064', self.patched)
        self.assertIn('"expected_host_memory_checks": 1032', self.patched)
        self.assertIn('"expected_task_parity_checks": 8', self.patched)

    def test_task_parity_is_enforced_inside_task_loop(self) -> None:
        self.assertIn("parity_evidence = require_task_budget_parity", self.patched)
        parity = self.patched.index("parity_evidence = require_task_budget_parity")
        suite = self.patched.index("suite_result = classify_suite_advantage")
        self.assertLess(parity, suite)

    def test_cleanup_guard_spans_post_parser_pre_attempt_gap(self) -> None:
        guard = self.patched.index("with ArmedCleanup(cleanup_post_parser_pre_attempt)")
        attempt = self.patched.index(
            "claim_catalytic_swarm_1_runtime_json_once(\n            CATALYTIC_SWARM_1_ATTEMPT_PATH"
        )
        self.assertLess(guard, attempt)
        self.assertIn("post_parser_cleanup.disarm()", self.patched[guard:attempt])

    def test_no_new_live_or_mutating_command_is_added(self) -> None:
        forbidden = {"push", "commit", "merge", "rebase", "reset", "checkout", "switch"}
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "git_read":
                literals = {
                    arg.value
                    for arg in node.args
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                }
                self.assertFalse(forbidden.intersection(literals))


if __name__ == "__main__":
    unittest.main()
