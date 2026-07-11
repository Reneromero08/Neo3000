#!/usr/bin/env python3
"""CPU-only tests for Chat Completions token evidence reconstruction."""

from __future__ import annotations

import unittest

from chat_token_evidence import (
    ChatTokenEvidenceError,
    build_chat_token_evidence,
    token_ids_sha256,
)


class ChatTokenEvidenceTests(unittest.TestCase):
    def tokenize(self, text: str) -> list[int]:
        fixtures = {
            "TOKEN ARRAY CANARY": [60738, 30094, 18916, 8378],
            "HOLOSTATE FAST A1": [101, 102, 103, 104, 105, 106],
            "": [],
        }
        return list(fixtures[text])

    def build(self, **overrides):
        values = {
            "native_token_ids": [],
            "completion_tokens": 6,
            "visible_content": "HOLOSTATE FAST A1",
            "reasoning_content": "",
            "tool_calls": [],
            "thinking_disabled": True,
            "tokenize_visible_content": self.tokenize,
            "finish_reason": "stop",
            "terminal_stop_type": "eos",
            "terminal_stopping_word": "",
            "stop_sequences_configured": False,
            "allow_terminal_control_accounting": False,
        }
        values.update(overrides)
        return build_chat_token_evidence(**values)

    def test_native_ids_remain_authoritative(self) -> None:
        result = self.build(native_token_ids=[1, 2, 3], completion_tokens=3)
        self.assertTrue(result.accepted)
        self.assertEqual(result.source, "server-native")
        self.assertEqual(result.claim_scope, "exact-generated-token-sequence")
        self.assertTrue(result.full_generated_sequence_known)
        self.assertFalse(result.reconstructed)

    def test_native_count_mismatch_fails_closed(self) -> None:
        result = self.build(native_token_ids=[1, 2], completion_tokens=3)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "native-token-count-mismatch")

    def test_exact_visible_count_reconstructs_without_terminal_allowance(self) -> None:
        result = self.build()
        self.assertTrue(result.accepted)
        self.assertEqual(result.source, "visible-content-retokenization")
        self.assertEqual(result.claim_scope, "exact-visible-content-tokenization")
        self.assertEqual(result.usage_delta, 0)
        self.assertEqual(result.terminal_control_token_count, 0)

    def test_v3_canary_reconciles_four_visible_plus_one_terminal_eos(self) -> None:
        result = self.build(
            visible_content="TOKEN ARRAY CANARY",
            completion_tokens=5,
            allow_terminal_control_accounting=True,
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.token_ids, [60738, 30094, 18916, 8378])
        self.assertEqual(result.token_count, 4)
        self.assertEqual(result.usage_delta, 1)
        self.assertEqual(result.terminal_control_token_count, 1)
        self.assertFalse(result.terminal_control_token_id_known)
        self.assertFalse(result.full_generated_sequence_known)
        self.assertEqual(result.terminal_stop_type, "eos")
        self.assertEqual(
            result.claim_scope,
            "exact-visible-content-tokenization-plus-one-terminal-eos-token",
        )

    def test_one_token_surplus_requires_explicit_source_authorization(self) -> None:
        result = self.build(
            visible_content="TOKEN ARRAY CANARY",
            completion_tokens=5,
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "terminal-eos-accounting-not-proven")

    def test_one_token_surplus_requires_eos_stop_type(self) -> None:
        result = self.build(
            visible_content="TOKEN ARRAY CANARY",
            completion_tokens=5,
            terminal_stop_type="word",
            allow_terminal_control_accounting=True,
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "terminal-eos-accounting-not-proven")

    def test_one_token_surplus_requires_empty_stopping_word(self) -> None:
        result = self.build(
            visible_content="TOKEN ARRAY CANARY",
            completion_tokens=5,
            terminal_stopping_word="STOP",
            allow_terminal_control_accounting=True,
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "terminal-eos-accounting-not-proven")

    def test_one_token_surplus_requires_normal_stop(self) -> None:
        result = self.build(
            visible_content="TOKEN ARRAY CANARY",
            completion_tokens=5,
            finish_reason="length",
            allow_terminal_control_accounting=True,
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "terminal-eos-accounting-not-proven")

    def test_one_token_surplus_rejects_configured_stop_sequences(self) -> None:
        result = self.build(
            visible_content="TOKEN ARRAY CANARY",
            completion_tokens=5,
            stop_sequences_configured=True,
            allow_terminal_control_accounting=True,
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "terminal-eos-accounting-not-proven")

    def test_more_than_one_hidden_token_fails_closed(self) -> None:
        result = self.build(
            visible_content="TOKEN ARRAY CANARY",
            completion_tokens=6,
            allow_terminal_control_accounting=True,
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "reconstructed-token-count-mismatch")

    def test_completion_count_is_required_for_reconstruction(self) -> None:
        result = self.build(completion_tokens=None)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "completion-count-unavailable")

    def test_reconstruction_is_forbidden_when_reasoning_is_present(self) -> None:
        result = self.build(reasoning_content="opaque reasoning")
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "reconstruction-forbidden-for-reasoning-or-tools")

    def test_reconstruction_is_forbidden_when_thinking_is_enabled(self) -> None:
        result = self.build(thinking_disabled=False)
        self.assertFalse(result.accepted)

    def test_reconstruction_is_forbidden_for_tool_calls(self) -> None:
        result = self.build(tool_calls=[{"type": "function"}])
        self.assertFalse(result.accepted)

    def test_malformed_native_ids_raise(self) -> None:
        with self.assertRaises(ChatTokenEvidenceError):
            self.build(native_token_ids=[1, True], completion_tokens=2)

    def test_malformed_reconstructed_ids_raise(self) -> None:
        with self.assertRaises(ChatTokenEvidenceError):
            self.build(tokenize_visible_content=lambda _: [True], completion_tokens=1)

    def test_token_hash_is_canonical(self) -> None:
        self.assertEqual(token_ids_sha256([1, 2, 3]), token_ids_sha256([1, 2, 3]))
        self.assertNotEqual(token_ids_sha256([1, 2, 3]), token_ids_sha256([1, 3, 2]))


if __name__ == "__main__":
    unittest.main()
