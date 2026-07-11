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
            "TOKEN ARRAY CANARY": [10, 20, 30, 40, 50],
            "HOLOSTATE FAST A1": [101, 102, 103, 104, 105, 106],
            "": [],
        }
        return list(fixtures[text])

    def test_native_ids_remain_authoritative(self) -> None:
        result = build_chat_token_evidence(
            native_token_ids=[1, 2, 3],
            completion_tokens=3,
            visible_content="TOKEN ARRAY CANARY",
            reasoning_content="",
            tool_calls=[],
            thinking_disabled=True,
            tokenize_visible_content=self.tokenize,
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.source, "server-native")
        self.assertFalse(result.reconstructed)
        self.assertEqual(result.token_ids, [1, 2, 3])

    def test_native_count_mismatch_fails_closed(self) -> None:
        result = build_chat_token_evidence(
            native_token_ids=[1, 2],
            completion_tokens=3,
            visible_content="TOKEN ARRAY CANARY",
            reasoning_content="",
            tool_calls=[],
            thinking_disabled=True,
            tokenize_visible_content=self.tokenize,
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "native-token-count-mismatch")

    def test_empty_native_array_reconstructs_thinking_disabled_visible_text(self) -> None:
        result = build_chat_token_evidence(
            native_token_ids=[],
            completion_tokens=5,
            visible_content="TOKEN ARRAY CANARY",
            reasoning_content="",
            tool_calls=[],
            thinking_disabled=True,
            tokenize_visible_content=self.tokenize,
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.source, "visible-content-retokenization")
        self.assertTrue(result.reconstructed)
        self.assertEqual(result.token_ids, [10, 20, 30, 40, 50])
        self.assertTrue(result.count_match)

    def test_absent_native_array_reconstructs_thinking_disabled_visible_text(self) -> None:
        result = build_chat_token_evidence(
            native_token_ids=None,
            completion_tokens=6,
            visible_content="HOLOSTATE FAST A1",
            reasoning_content="",
            tool_calls=[],
            thinking_disabled=True,
            tokenize_visible_content=self.tokenize,
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.token_count, 6)

    def test_reconstruction_count_mismatch_fails_closed(self) -> None:
        result = build_chat_token_evidence(
            native_token_ids=[],
            completion_tokens=4,
            visible_content="TOKEN ARRAY CANARY",
            reasoning_content="",
            tool_calls=[],
            thinking_disabled=True,
            tokenize_visible_content=self.tokenize,
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "reconstructed-token-count-mismatch")

    def test_reconstruction_is_forbidden_when_reasoning_is_present(self) -> None:
        result = build_chat_token_evidence(
            native_token_ids=[],
            completion_tokens=5,
            visible_content="TOKEN ARRAY CANARY",
            reasoning_content="opaque reasoning",
            tool_calls=[],
            thinking_disabled=True,
            tokenize_visible_content=self.tokenize,
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "reconstruction-forbidden-for-reasoning-or-tools")

    def test_reconstruction_is_forbidden_when_thinking_is_enabled(self) -> None:
        result = build_chat_token_evidence(
            native_token_ids=[],
            completion_tokens=5,
            visible_content="TOKEN ARRAY CANARY",
            reasoning_content="",
            tool_calls=[],
            thinking_disabled=False,
            tokenize_visible_content=self.tokenize,
        )
        self.assertFalse(result.accepted)

    def test_reconstruction_is_forbidden_for_tool_calls(self) -> None:
        result = build_chat_token_evidence(
            native_token_ids=[],
            completion_tokens=5,
            visible_content="TOKEN ARRAY CANARY",
            reasoning_content="",
            tool_calls=[{"type": "function"}],
            thinking_disabled=True,
            tokenize_visible_content=self.tokenize,
        )
        self.assertFalse(result.accepted)

    def test_malformed_native_ids_raise(self) -> None:
        with self.assertRaises(ChatTokenEvidenceError):
            build_chat_token_evidence(
                native_token_ids=[1, True],
                completion_tokens=2,
                visible_content="TOKEN ARRAY CANARY",
                reasoning_content="",
                tool_calls=[],
                thinking_disabled=True,
                tokenize_visible_content=self.tokenize,
            )

    def test_malformed_reconstructed_ids_raise(self) -> None:
        with self.assertRaises(ChatTokenEvidenceError):
            build_chat_token_evidence(
                native_token_ids=[],
                completion_tokens=1,
                visible_content="TOKEN ARRAY CANARY",
                reasoning_content="",
                tool_calls=[],
                thinking_disabled=True,
                tokenize_visible_content=lambda _: [True],
            )

    def test_token_hash_is_canonical(self) -> None:
        self.assertEqual(token_ids_sha256([1, 2, 3]), token_ids_sha256([1, 2, 3]))
        self.assertNotEqual(token_ids_sha256([1, 2, 3]), token_ids_sha256([1, 3, 2]))


if __name__ == "__main__":
    unittest.main()
