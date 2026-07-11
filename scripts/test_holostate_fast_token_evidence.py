#!/usr/bin/env python3
"""CPU-only tests for the HoloState Fast token evidence adapter."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from holostate_fast_token_evidence import (
    FastTokenEvidenceError,
    evaluate_fast_worker,
    resolve_fast_token_evidence,
)


class FastTokenEvidenceAdapterTests(unittest.TestCase):
    def tokenize(self, text: str) -> list[int]:
        values = {
            "TOKEN ARRAY CANARY": [60738, 30094, 18916, 8378],
            "HOLOSTATE FAST A1": [10, 11, 12, 13, 14, 15],
        }
        return list(values[text])

    def measurement(self, **overrides):
        base = {
            "generated_token_ids": [],
            "completion_tokens": 6,
            "content": "HOLOSTATE FAST A1",
            "reasoning_content": "",
            "tool_calls": [],
            "finish_reason": "stop",
            "stop_type": "eos",
            "stopping_word": "",
            "terminal_stop_evidence": {
                "observed": True,
                "stop": True,
                "stop_type": "eos",
                "stopping_word": "",
                "verbose_token_array_length": 0,
                "event_index": 7,
            },
            "prompt_tokens": 100,
            "cached_prompt_tokens": 90,
        }
        base.update(overrides)
        return SimpleNamespace(**base)

    def test_missing_native_ids_use_visible_content_retokenization(self) -> None:
        result = resolve_fast_token_evidence(
            self.measurement(),
            tokenize_visible_content=self.tokenize,
            thinking_disabled=True,
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["source"], "visible-content-retokenization")
        self.assertEqual(result["claim_scope"], "exact-visible-content-tokenization")

    def test_v3_canary_accepts_unknown_terminal_eos(self) -> None:
        result = resolve_fast_token_evidence(
            self.measurement(content="TOKEN ARRAY CANARY", completion_tokens=5),
            tokenize_visible_content=self.tokenize,
            thinking_disabled=True,
            allow_terminal_control_accounting=True,
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["token_count"], 4)
        self.assertEqual(result["completion_tokens"], 5)
        self.assertEqual(result["usage_delta"], 1)
        self.assertEqual(result["terminal_control_token_count"], 1)
        self.assertFalse(result["terminal_control_token_id_known"])
        self.assertFalse(result["full_generated_sequence_known"])
        self.assertEqual(result["terminal_stop_type"], "eos")
        self.assertEqual(
            result["claim_scope"],
            "exact-visible-content-tokenization-plus-one-terminal-eos-token",
        )

    def test_native_ids_preserve_generated_sequence_claim(self) -> None:
        result = resolve_fast_token_evidence(
            self.measurement(generated_token_ids=[20, 21, 22, 23, 24, 25]),
            tokenize_visible_content=self.tokenize,
            thinking_disabled=True,
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["source"], "server-native")
        self.assertEqual(result["claim_scope"], "exact-generated-token-sequence")

    def test_full_fast_gate_accepts_reconstructed_evidence(self) -> None:
        result = evaluate_fast_worker(
            self.measurement(),
            expected_content="HOLOSTATE FAST A1",
            logical_prompt_tokens=100,
            tokenize_visible_content=self.tokenize,
        )
        self.assertTrue(result["accepted"], result["reasons"])
        self.assertEqual(result["fresh_prompt_tokens"], 10)

    def test_full_fast_gate_accepts_terminal_eos_reconciliation(self) -> None:
        result = evaluate_fast_worker(
            self.measurement(content="TOKEN ARRAY CANARY", completion_tokens=5),
            expected_content="TOKEN ARRAY CANARY",
            logical_prompt_tokens=100,
            tokenize_visible_content=self.tokenize,
            allow_terminal_control_accounting=True,
        )
        self.assertTrue(result["accepted"], result["reasons"])
        self.assertEqual(result["token_evidence"]["terminal_control_token_count"], 1)

    def test_terminal_eos_reconciliation_requires_metadata(self) -> None:
        result = evaluate_fast_worker(
            self.measurement(
                content="TOKEN ARRAY CANARY",
                completion_tokens=5,
                stop_type=None,
                terminal_stop_evidence=None,
            ),
            expected_content="TOKEN ARRAY CANARY",
            logical_prompt_tokens=100,
            tokenize_visible_content=self.tokenize,
            allow_terminal_control_accounting=True,
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(result["classification"], "instrumentation-reject")
        self.assertIn("terminal-eos-accounting-not-proven", result["reasons"])

    def test_terminal_eos_reconciliation_requires_true_stop_flag(self) -> None:
        terminal = dict(self.measurement().terminal_stop_evidence)
        terminal["stop"] = False
        result = evaluate_fast_worker(
            self.measurement(
                content="TOKEN ARRAY CANARY",
                completion_tokens=5,
                terminal_stop_evidence=terminal,
            ),
            expected_content="TOKEN ARRAY CANARY",
            logical_prompt_tokens=100,
            tokenize_visible_content=self.tokenize,
            allow_terminal_control_accounting=True,
        )
        self.assertFalse(result["accepted"])
        self.assertIn("terminal-eos-accounting-not-proven", result["reasons"])

    def test_terminal_eos_reconciliation_requires_empty_final_token_array(self) -> None:
        terminal = dict(self.measurement().terminal_stop_evidence)
        terminal["verbose_token_array_length"] = 1
        result = evaluate_fast_worker(
            self.measurement(
                content="TOKEN ARRAY CANARY",
                completion_tokens=5,
                terminal_stop_evidence=terminal,
            ),
            expected_content="TOKEN ARRAY CANARY",
            logical_prompt_tokens=100,
            tokenize_visible_content=self.tokenize,
            allow_terminal_control_accounting=True,
        )
        self.assertFalse(result["accepted"])
        self.assertIn("terminal-eos-accounting-not-proven", result["reasons"])

    def test_visible_retokenization_requires_repeat_determinism(self) -> None:
        calls = 0

        def unstable(_: str) -> list[int]:
            nonlocal calls
            calls += 1
            return [1] if calls == 1 else [2]

        with self.assertRaises(FastTokenEvidenceError):
            resolve_fast_token_evidence(
                self.measurement(completion_tokens=1),
                tokenize_visible_content=unstable,
                thinking_disabled=True,
            )

    def test_valid_visible_retokenization_records_repeat_equality(self) -> None:
        result = resolve_fast_token_evidence(
            self.measurement(),
            tokenize_visible_content=self.tokenize,
            thinking_disabled=True,
        )
        self.assertTrue(result["tokenizer_repeat"]["performed"])
        self.assertTrue(result["tokenizer_repeat"]["equal"])

    def test_configured_stop_sequence_disables_terminal_reconciliation(self) -> None:
        result = evaluate_fast_worker(
            self.measurement(content="TOKEN ARRAY CANARY", completion_tokens=5),
            expected_content="TOKEN ARRAY CANARY",
            logical_prompt_tokens=100,
            tokenize_visible_content=self.tokenize,
            allow_terminal_control_accounting=True,
            stop_sequences_configured=True,
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(result["classification"], "instrumentation-reject")

    def test_count_mismatch_larger_than_one_is_instrumentation_reject(self) -> None:
        result = evaluate_fast_worker(
            self.measurement(content="TOKEN ARRAY CANARY", completion_tokens=6),
            expected_content="TOKEN ARRAY CANARY",
            logical_prompt_tokens=100,
            tokenize_visible_content=self.tokenize,
            allow_terminal_control_accounting=True,
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(result["classification"], "instrumentation-reject")
        self.assertIn("reconstructed-token-count-mismatch", result["reasons"])

    def test_wrong_visible_content_is_capability_reject(self) -> None:
        result = evaluate_fast_worker(
            self.measurement(content="TOKEN ARRAY CANARY", completion_tokens=4),
            expected_content="HOLOSTATE FAST A1",
            logical_prompt_tokens=100,
            tokenize_visible_content=self.tokenize,
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(result["classification"], "capability-reject")
        self.assertIn("exact-content-failed", result["reasons"])

    def test_reasoning_channel_forbids_reconstruction(self) -> None:
        result = evaluate_fast_worker(
            self.measurement(reasoning_content="hidden"),
            expected_content="HOLOSTATE FAST A1",
            logical_prompt_tokens=100,
            tokenize_visible_content=self.tokenize,
        )
        self.assertFalse(result["accepted"])
        self.assertIn("reasoning-channel-not-empty", result["reasons"])
        self.assertIn("reconstruction-forbidden-for-reasoning-or-tools", result["reasons"])

    def test_tool_call_forbids_reconstruction(self) -> None:
        result = evaluate_fast_worker(
            self.measurement(tool_calls=[{"type": "function"}]),
            expected_content="HOLOSTATE FAST A1",
            logical_prompt_tokens=100,
            tokenize_visible_content=self.tokenize,
        )
        self.assertFalse(result["accepted"])
        self.assertIn("unexpected-tool-call", result["reasons"])

    def test_fresh_prompt_work_is_required(self) -> None:
        result = evaluate_fast_worker(
            self.measurement(cached_prompt_tokens=100),
            expected_content="HOLOSTATE FAST A1",
            logical_prompt_tokens=100,
            tokenize_visible_content=self.tokenize,
        )
        self.assertFalse(result["accepted"])
        self.assertIn("fresh-prompt-work-not-demonstrated", result["reasons"])

    def test_logical_prompt_count_must_match(self) -> None:
        result = evaluate_fast_worker(
            self.measurement(),
            expected_content="HOLOSTATE FAST A1",
            logical_prompt_tokens=101,
            tokenize_visible_content=self.tokenize,
        )
        self.assertFalse(result["accepted"])
        self.assertIn("logical-prompt-token-count-mismatch", result["reasons"])

    def test_malformed_native_evidence_raises_adapter_error(self) -> None:
        with self.assertRaises(FastTokenEvidenceError):
            resolve_fast_token_evidence(
                self.measurement(generated_token_ids=[1, True]),
                tokenize_visible_content=self.tokenize,
                thinking_disabled=True,
            )


if __name__ == "__main__":
    unittest.main()
