#!/usr/bin/env python3
"""Static source-contract tests for pinned Chat Completions token accounting.

These tests do not claim runtime behavior by themselves.  They bind the narrow
source law used by HoloState Fast evidence:

- ``n_decoded`` increments immediately after sampling and before stop handling;
- EOS is recognized only inside ``process_token`` after that increment;
- OAI usage reports ``completion_tokens = n_decoded``;
- OAI Chat partial chunks omit internal token arrays, while the stream final
  verbose record carries an intentionally empty token array plus stop metadata.
"""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTEXT = ROOT / "tools" / "server" / "server-context.cpp"
TASK = ROOT / "tools" / "server" / "server-task.cpp"


def function_slice(source: str, start_marker: str, end_marker: str) -> str:
    start = source.find(start_marker)
    if start < 0:
        raise AssertionError(f"missing source marker: {start_marker}")
    end = source.find(end_marker, start + len(start_marker))
    if end < 0:
        raise AssertionError(f"missing source end marker: {end_marker}")
    return source[start:end]


class ChatCompletionAccountingSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.context = CONTEXT.read_text(encoding="utf-8")
        cls.task = TASK.read_text(encoding="utf-8")

    def test_decoded_count_increments_before_process_token_stop_handling(self) -> None:
        post_decode = function_slice(
            self.context,
            "void post_decode(",
            "// speculative decoding - main model sample and accept",
        )
        increment = post_decode.find("slot.n_decoded += 1;")
        process = post_decode.find("if (!process_token(result, slot))")
        self.assertGreaterEqual(increment, 0)
        self.assertGreater(process, increment)

    def test_process_token_counts_and_streams_before_eos_stop(self) -> None:
        process_token = function_slice(
            self.context,
            "bool process_token(",
            "void populate_token_probs(",
        )
        add_token = process_token.find("slot.add_token(result);")
        send_partial = process_token.find("send_partial_response(slot, result, false);")
        eos_check = process_token.find("if (llama_vocab_is_eog(vocab, result.tok))")
        eos_stop = process_token.find("slot.stop           = STOP_TYPE_EOS;", eos_check)
        self.assertGreaterEqual(add_token, 0)
        self.assertGreater(send_partial, add_token)
        self.assertGreater(eos_check, send_partial)
        self.assertGreater(eos_stop, eos_check)

    def test_oai_usage_counts_n_decoded(self) -> None:
        usage = function_slice(
            self.task,
            "json server_task_result_cmpl_final::usage_json_oaicompat()",
            "json server_task_result_cmpl_final::to_json_oaicompat()",
        )
        self.assertIn('{"completion_tokens", n_decoded}', usage)
        self.assertIn('{"total_tokens",      n_decoded + n_prompt_tokens}', usage)

    def test_stream_final_tokens_are_empty_but_stop_metadata_remains(self) -> None:
        send_final = function_slice(
            self.context,
            "void send_final_response(",
            "void send_embedding(",
        )
        self.assertIn("if (slot.task->params.stream)", send_final)
        self.assertIn("res->tokens      = llama_tokens{};", send_final)
        self.assertIn("res->stopping_word", send_final)
        self.assertIn("res->stop", send_final)

    def test_non_oai_verbose_serializer_exposes_complete_terminal_gate(self) -> None:
        verbose = function_slice(
            self.task,
            "json server_task_result_cmpl_final::to_json_non_oaicompat()",
            "json server_task_result_cmpl_final::usage_json_oaicompat()",
        )
        self.assertIn('{"tokens",              tokens}', verbose)
        self.assertIn('{"stop",                true}', verbose)
        self.assertIn('{"stop_type",           stop_type_to_str(stop)}', verbose)
        self.assertIn('{"stopping_word",       stopping_word}', verbose)

    def test_partial_internal_result_contains_sampled_token(self) -> None:
        send_partial = function_slice(
            self.context,
            "void send_partial_response(",
            "void send_final_response(",
        )
        self.assertIn("res->tokens  = { tkn.tok };", send_partial)

    def test_oai_chat_partial_serializer_omits_verbose_token_array(self) -> None:
        partial_chat = function_slice(
            self.task,
            "json server_task_result_cmpl_partial::to_json_oaicompat_chat()",
            "json server_task_result_cmpl_partial::to_json_oaicompat_resp()",
        )
        self.assertNotIn("__verbose", partial_chat)
        self.assertNotIn('"tokens"', partial_chat)

    def test_oai_chat_stream_final_attaches_verbose_final_record(self) -> None:
        final_chat_stream = function_slice(
            self.task,
            "json server_task_result_cmpl_final::to_json_oaicompat_chat_stream()",
            "json server_task_result_cmpl_final::to_json_oaicompat_resp()",
        )
        self.assertIn('if (verbose && !deltas.empty())', final_chat_stream)
        self.assertIn('deltas.front()["__verbose"] = to_json_non_oaicompat();', final_chat_stream)

    def test_verbose_terminal_delta_precedes_optional_usage_only_delta(self) -> None:
        final_chat_stream = function_slice(
            self.task,
            "json server_task_result_cmpl_final::to_json_oaicompat_chat_stream()",
            "json server_task_result_cmpl_final::to_json_oaicompat_resp()",
        )
        self.assertIn('deltas.front()["__verbose"] = to_json_non_oaicompat();', final_chat_stream)
        self.assertIn('{"choices", json::array()}', final_chat_stream)
        self.assertIn('{"usage",              usage_json_oaicompat()}', final_chat_stream)
        self.assertIn('deltas.back().push_back({"timings", timings.to_json()});', final_chat_stream)


if __name__ == "__main__":
    unittest.main()
