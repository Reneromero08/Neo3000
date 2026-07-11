#!/usr/bin/env python3
"""CPU-only tests for bounded Chat Completions terminal-stop evidence."""

from __future__ import annotations

import json
import unittest
from unittest import mock

import baseline_harness as harness

from chat_stream_terminal_evidence import (
    TerminalEvidenceError,
    extract_terminal_stop_evidence,
    merge_terminal_stop_evidence,
    terminal_eos_gate,
)


class TerminalStopEvidenceTests(unittest.TestCase):
    def eos_event(self, **overrides):
        verbose = {
            "stop": True,
            "stop_type": "eos",
            "stopping_word": "",
            "tokens": [],
        }
        verbose.update(overrides)
        return {
            "choices": [{"finish_reason": "stop", "delta": {}}],
            "__verbose": verbose,
        }

    def test_event_without_verbose_terminal_metadata_is_absent(self) -> None:
        self.assertIsNone(
            extract_terminal_stop_evidence(
                {"choices": [{"delta": {"content": "visible"}}]},
                event_index=1,
            )
        )

    def test_present_nonobject_verbose_metadata_rejects(self) -> None:
        with self.assertRaises(TerminalEvidenceError):
            extract_terminal_stop_evidence(
                {"__verbose": "malformed"},
                event_index=1,
            )

    def test_present_verbose_tokens_without_stop_metadata_rejects(self) -> None:
        with self.assertRaises(TerminalEvidenceError):
            extract_terminal_stop_evidence(
                {"__verbose": {"tokens": []}},
                event_index=1,
            )

    def test_valid_eos_record_is_extracted_and_passes(self) -> None:
        evidence = extract_terminal_stop_evidence(self.eos_event(), event_index=7)
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertTrue(evidence.stop)
        self.assertEqual(evidence.stop_type, "eos")
        self.assertEqual(evidence.stopping_word, "")
        self.assertEqual(evidence.verbose_token_array_length, 0)
        self.assertEqual(evidence.event_index, 7)
        self.assertTrue(terminal_eos_gate(evidence)["passed"])

    def test_word_stop_is_rejected_by_eos_gate(self) -> None:
        evidence = extract_terminal_stop_evidence(
            self.eos_event(stop_type="word"), event_index=1
        )
        gate = terminal_eos_gate(evidence)
        self.assertFalse(gate["passed"])
        self.assertIn("terminal-stop-type-not-eos", gate["reasons"])

    def test_nonempty_stopping_word_is_rejected(self) -> None:
        evidence = extract_terminal_stop_evidence(
            self.eos_event(stopping_word="STOP"), event_index=1
        )
        gate = terminal_eos_gate(evidence)
        self.assertFalse(gate["passed"])
        self.assertIn("terminal-stopping-word-not-empty", gate["reasons"])

    def test_nonempty_terminal_token_array_is_rejected(self) -> None:
        evidence = extract_terminal_stop_evidence(
            self.eos_event(tokens=[123]), event_index=1
        )
        gate = terminal_eos_gate(evidence)
        self.assertFalse(gate["passed"])
        self.assertIn("terminal-stream-token-array-not-empty", gate["reasons"])

    def test_false_stop_flag_is_rejected(self) -> None:
        evidence = extract_terminal_stop_evidence(
            self.eos_event(stop=False), event_index=1
        )
        gate = terminal_eos_gate(evidence)
        self.assertFalse(gate["passed"])
        self.assertIn("terminal-stop-flag-not-true", gate["reasons"])

    def test_malformed_stop_flag_rejects(self) -> None:
        with self.assertRaises(TerminalEvidenceError):
            extract_terminal_stop_evidence(
                self.eos_event(stop="true"), event_index=1
            )

    def test_malformed_stop_type_rejects(self) -> None:
        with self.assertRaises(TerminalEvidenceError):
            extract_terminal_stop_evidence(
                self.eos_event(stop_type=42), event_index=1
            )
        with self.assertRaises(TerminalEvidenceError):
            extract_terminal_stop_evidence(
                self.eos_event(stop_type="mystery"), event_index=1
            )

    def test_malformed_stopping_word_rejects(self) -> None:
        with self.assertRaises(TerminalEvidenceError):
            extract_terminal_stop_evidence(
                self.eos_event(stopping_word=None), event_index=1
            )

    def test_malformed_token_array_rejects(self) -> None:
        with self.assertRaises(TerminalEvidenceError):
            extract_terminal_stop_evidence(
                self.eos_event(tokens="[]"), event_index=1
            )

    def test_identical_duplicate_terminal_records_merge(self) -> None:
        first = extract_terminal_stop_evidence(self.eos_event(), event_index=4)
        second = extract_terminal_stop_evidence(self.eos_event(), event_index=5)
        merged = merge_terminal_stop_evidence(first, second)
        self.assertEqual(merged, first)

    def test_conflicting_duplicate_terminal_records_reject(self) -> None:
        first = extract_terminal_stop_evidence(self.eos_event(), event_index=4)
        second = extract_terminal_stop_evidence(
            self.eos_event(stop_type="word"), event_index=5
        )
        with self.assertRaises(TerminalEvidenceError):
            merge_terminal_stop_evidence(first, second)

    def test_terminal_record_contains_no_generated_or_reasoning_text(self) -> None:
        event = self.eos_event()
        event["choices"][0]["delta"] = {
            "content": "visible secret",
            "reasoning_content": "hidden secret",
        }
        evidence = extract_terminal_stop_evidence(event, event_index=9)
        rendered = repr(evidence.to_dict()) if evidence is not None else ""
        self.assertNotIn("visible secret", rendered)
        self.assertNotIn("hidden secret", rendered)


class SharedStreamParserTerminalTests(unittest.TestCase):
    class FakeResponse:
        status = 200

        def __init__(self, events):
            self.lines = [f"data: {json.dumps(event)}\n".encode() for event in events]
            self.lines.append(b"data: [DONE]\n")

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def __iter__(self):
            return iter(self.lines)

    def test_terminal_metadata_preceding_usage_only_event_is_preserved(self) -> None:
        events = [
            {
                "choices": [{"finish_reason": "stop", "delta": {"content": "TOKEN ARRAY CANARY"}}],
                "__verbose": {
                    "stop": True,
                    "stop_type": "eos",
                    "stopping_word": "",
                    "tokens": [],
                },
            },
            {
                "choices": [],
                "usage": {
                    "prompt_tokens": 7,
                    "completion_tokens": 5,
                    "prompt_tokens_details": {"cached_tokens": 0},
                },
            },
        ]
        records = []
        with mock.patch.object(
            harness.urllib.request,
            "urlopen",
            return_value=self.FakeResponse(events),
        ):
            measurement = harness.stream_completion(
                "http://127.0.0.1:9494/v1/chat/completions",
                {"stream": True},
                repeat=1,
                timeout=1,
                event_recorder=records.append,
                request_label="canary",
            )
        self.assertEqual(measurement.stop_type, "eos")
        self.assertEqual(measurement.stopping_word, "")
        self.assertEqual(measurement.terminal_stop_evidence["event_index"], 1)
        self.assertEqual(measurement.completion_tokens, 5)
        self.assertTrue(records[0]["terminal_stop_observed"])
        self.assertFalse(records[1]["terminal_stop_observed"])

    def test_malformed_verbose_metadata_poisoning_exact_count_stream_rejects(self) -> None:
        events = [
            {
                "choices": [{"finish_reason": "stop", "delta": {"content": "OK"}}],
                "__verbose": {"tokens": []},
                "usage": {"completion_tokens": 1},
            },
        ]
        with mock.patch.object(
            harness.urllib.request,
            "urlopen",
            return_value=self.FakeResponse(events),
        ):
            with self.assertRaises(harness.HarnessError):
                harness.stream_completion(
                    "http://127.0.0.1:9494/v1/chat/completions",
                    {"stream": True},
                    repeat=1,
                    timeout=1,
                )


if __name__ == "__main__":
    unittest.main()
