#!/usr/bin/env python3
"""Focused regression tests for split transport, reasoning, and warm-performance gates."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


harness = load_module("baseline_harness_under_test", ROOT / "scripts" / "baseline_harness.py")
neo_loop = load_module("neo_loop_gates_under_test", ROOT / "scripts" / "neo_loop.py")
EVALUATOR = json.loads((ROOT / "lab" / "EVALUATOR.json").read_text(encoding="utf-8"))


def payload(disable_thinking: bool = False, tool_test: bool = False):
    return harness.build_request_payload(
        "agents-a1", "Reply with exactly: NEO3000 ONLINE", 0.0, 64, False, tool_test, disable_thinking
    )


def report(*, exact: bool = True, reasoning: str = "reason", content: str = "NEO3000 ONLINE", tps: float = 12.0):
    return {
        "summary": {"all_http_200": True, "all_streamed_multiple_events": True, "median_reported_tokens_per_second": tps},
        "exact_response_passed": exact,
        "measurements": [{"reasoning_content": reasoning, "content": content}],
    }


class HarnessTransportTests(unittest.TestCase):
    def test_disable_thinking_inserts_only_the_documented_override(self) -> None:
        request = payload(disable_thinking=True)
        self.assertEqual(request["chat_template_kwargs"], {"enable_thinking": False})
        self.assertEqual(request["model"], "agents-a1")
        self.assertEqual(request["max_tokens"], 64)
        self.assertTrue(request["stream"])

    def test_default_mode_has_no_override(self) -> None:
        request = payload()
        self.assertNotIn("chat_template_kwargs", request)
        self.assertEqual(harness.thinking_metadata(request)["thinking_mode"], "auto")

    def test_tool_mode_stays_unchanged_without_explicit_override(self) -> None:
        request = payload(tool_test=True)
        self.assertEqual(request["tool_choice"], "required")
        self.assertIn("tools", request)
        self.assertNotIn("chat_template_kwargs", request)

    def test_effective_mode_metadata_is_recordable(self) -> None:
        self.assertEqual(harness.thinking_metadata(payload(disable_thinking=True)), {
            "thinking_mode": "disabled", "chat_template_kwargs": {"enable_thinking": False},
        })


class EvaluatorGateTests(unittest.TestCase):
    def test_full_canonical_gate_identity_changes_hash(self) -> None:
        baseline = neo_loop.gate_definition_hashes(EVALUATOR)
        mutations = [
            ("transport", "max_tokens", 65),
            ("transport", "expected_content", "WRONG"),
            ("transport", "thinking_mode", "auto"),
            ("transport", "chat_template_kwargs", None),
            ("reasoning", "reasoning_required", False),
            ("warm_performance", "performance_scored", False),
            ("warm_performance", "warmup_count", 2),
            ("warm_performance", "min_decode_tps", 9.0),
        ]
        for gate, field, value in mutations:
            changed = copy.deepcopy(EVALUATOR)
            changed["gates"][gate][field] = value
            self.assertNotEqual(baseline, neo_loop.gate_definition_hashes(changed), field)

    def test_reasoning_gate_rejects_empty_reasoning_and_missing_final_content(self) -> None:
        gate = EVALUATOR["gates"]["reasoning"]
        self.assertFalse(neo_loop.validate_gate(report(reasoning=""), gate, False)[0])
        self.assertFalse(neo_loop.validate_gate(report(exact=False, content=""), gate, False)[0])

    def test_transport_rejects_reasoning_only_or_wrong_final_content(self) -> None:
        gate = EVALUATOR["gates"]["transport"]
        self.assertFalse(neo_loop.validate_gate(report(exact=False, reasoning="reason", content=""), gate, False)[0])
        self.assertFalse(neo_loop.validate_gate(report(exact=False, content="WRONG"), gate, False)[0])

    def test_repeat_uses_disabled_thinking_while_reasoning_keeps_auto(self) -> None:
        repeat_args = neo_loop.gate_harness_args(EVALUATOR["gates"]["repeat"], 3, 300)
        reasoning_args = neo_loop.gate_harness_args(EVALUATOR["gates"]["reasoning"], 1, 300)
        self.assertIn("--disable-thinking", repeat_args)
        self.assertNotIn("--disable-thinking", reasoning_args)

    def test_warmup_is_unscored_but_counted_run_keeps_ten_tps_floor(self) -> None:
        gate = EVALUATOR["gates"]["warm_performance"]
        slow = report(tps=9.9)
        self.assertTrue(neo_loop.validate_gate(slow, gate, False)[0])
        self.assertFalse(neo_loop.validate_gate(slow, gate, True)[0])
        self.assertEqual(gate["min_decode_tps"], 10.0)


if __name__ == "__main__":
    unittest.main()
