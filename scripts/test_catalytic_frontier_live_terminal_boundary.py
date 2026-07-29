from __future__ import annotations

import json
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_live_terminal_boundary as live


CONTEXT = ROOT / "tools" / "server" / "server-context.cpp"
CONTEXT_HEADER = ROOT / "tools" / "server" / "server-context.h"
SERVER_ENTRYPOINT = ROOT / "tools" / "server" / "server.cpp"
SCHEMA = ROOT / "tools" / "server" / "server-schema.cpp"
TASK = ROOT / "tools" / "server" / "server-task.h"


class LiveTerminalBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.context = CONTEXT.read_text(encoding="utf-8")
        cls.context_header = CONTEXT_HEADER.read_text(encoding="utf-8")
        cls.server_entrypoint = SERVER_ENTRYPOINT.read_text(encoding="utf-8")
        cls.schema = SCHEMA.read_text(encoding="utf-8")
        cls.task = TASK.read_text(encoding="utf-8")

    def test_contract_binds_every_owner_port_and_causal_identity(self):
        for field in (
            "boundary_id",
            "carrier_id",
            "outer_lease",
            "generation",
            "port_owner",
            "port_type",
            "module_id",
            "module_variant",
            "module_ordinal",
            "input_boundary_id",
            "projection_policy",
            "restoration_policy",
        ):
            self.assertIn(field, self.task)
            self.assertIn(f'"{field}"', self.schema)

    def test_capture_is_single_slot_and_declared_closure_only(self):
        admission = self.context[
            self.context.index("if (capture_terminal) {") :
            self.context.index("slot.terminal_logits_pending_use = true;")
        ]
        self.assertIn("slots.size() != 1", admission)
        self.assertIn("slot.id != 0", admission)
        self.assertIn('"DECLARED_CLOSURE"', admission)
        self.assertIn("task.params.n_predict != 0", admission)

    def test_live_use_is_immediate_exact_and_rootless(self):
        admission = self.context[
            self.context.index("const auto & live = slot.terminal_logits.live;") :
            self.context.index("slot.terminal_logits_pending_use = true;")
        ]
        self.assertIn(
            "live.capture_request_epoch + 1 == task.neo3000_request_epoch",
            admission,
        )
        self.assertIn("neo3000_live_terminal_contract_equal(", admission)
        self.assertIn("live.n_vocab == n_vocab", admission)
        self.assertIn("slot.terminal_logits.root_id.empty()", admission)
        self.assertIn("exact_prompt_matches()", admission)
        self.assertIn("slot.terminal_logits.sampler_fnv64 == sampler_fnv64", admission)
        self.assertIn("slot.terminal_logits.position == position", admission)

    def test_mismatch_poison_precedes_error(self):
        mismatch = self.context[
            self.context.index("if (!terminal_exact) {") :
            self.context.index("slot.terminal_logits_pending_use = true;")
        ]
        self.assertLess(
            mismatch.index("slot.prompt_clear(false);"),
            mismatch.index("send_error(task,"),
        )
        self.assertIn("identity or causal-order mismatch", mismatch)

    def test_consumption_closes_before_any_final_projection(self):
        sample_start = self.context.index("const bool live_source =")
        sample = self.context[
            sample_start :
            self.context.index("slot.handle_last_sampled_token(batch);", sample_start)
        ]
        self.assertLess(
            sample.index("slot.terminal_logits.clear();"),
            sample.index("process_token(result, slot)"),
        )
        self.assertIn("sampled and declared-closed", sample)
        live_log = sample[
            sample.index("sampled and declared-closed") :
            sample.index(");", sample.index("sampled and declared-closed"))
        ]
        self.assertNotIn("logits=", live_log)

    def test_live_capture_log_does_not_expose_logit_fingerprint(self):
        start = self.context.index(
            '"neo3000 one-use live terminal boundary captured'
        )
        capture_log = self.context[start : self.context.index(");", start)]
        self.assertNotIn("logits=", capture_log)

    def test_capture_receipt_rejects_output_bearing_wire_surface(self):
        final_event = {
            "content": "",
            "tokens": [],
            "stop": True,
            "tokens_predicted": 0,
            "tokens_evaluated": 777,
            "stop_type": "limit",
            "tokens_cached": 690,
            "timings": {
                "cache_n": 690,
                "prompt_n": 87,
                "prompt_ms": 1.0,
                "prompt_per_token_ms": 0.01,
                "prompt_per_second": 100.0,
                "predicted_n": 0,
                "predicted_ms": 0.0,
                "predicted_per_token_ms": 0.0,
                "predicted_per_second": 0.0,
            },
        }
        recorder = live.LiveCaptureWireRecorder()
        recorder(
            b"data: "
            + json.dumps(final_event, separators=(",", ":")).encode()
            + b"\n"
        )
        record = {
            "content": "",
            "execution": {
                name: None for name in live.harness.carrier.CAPTURE_EXECUTION_FIELDS
            },
        }
        record["execution"].update(
            content="",
            reasoning_content="",
            tool_calls=[],
            completion_tokens=0,
            generated_token_ids=[],
            generated_token_count=0,
            nonempty_token_array_event_count=0,
        )
        receipt = live.validate_capture_receipt(record, recorder)
        self.assertTrue(receipt["hidden_value_fields_absent"])
        self.assertFalse(recorder.lines)
        leaking = live.LiveCaptureWireRecorder()
        leaking_event = dict(final_event, logits_hash="secret")
        leaking(
            b"data: "
            + json.dumps(leaking_event, separators=(",", ":")).encode()
            + b"\n"
        )
        with self.assertRaisesRegex(
            live.ExperimentError,
            "final response surface changed",
        ):
            live.validate_capture_receipt(record, leaking)
        self.assertFalse(leaking.lines)
        nested = live.LiveCaptureWireRecorder()
        nested_event = dict(final_event)
        nested_event["timings"] = {
            **final_event["timings"],
            "hidden_scores": [1.0],
        }
        nested(
            b"data: "
            + json.dumps(nested_event, separators=(",", ":")).encode()
            + b"\n"
        )
        with self.assertRaisesRegex(
            live.ExperimentError,
            "unapproved timings field",
        ):
            live.validate_capture_receipt(record, nested)
        self.assertFalse(nested.lines)

    def test_capture_payload_requests_only_empty_public_receipt_fields(self):
        payload = live.capture_payload(
            {"prompt": [1, 2, 3], "stream": True},
            {
                "boundary_id": "b",
                "carrier_id": "c",
                "outer_lease": 1,
                "generation": 1,
                "port_owner": "o",
                "port_type": "t",
                "module_id": "m",
                "module_variant": 0,
                "module_ordinal": 1,
                "input_boundary_id": "i",
                "projection_policy": "p",
                "restoration_policy": "r",
            },
        )
        self.assertEqual(
            payload["response_fields"],
            [
                "content",
                "tokens",
                "stop",
                "tokens_predicted",
                "tokens_evaluated",
                "stop_type",
                "tokens_cached",
                "timings",
            ],
        )
        self.assertNotIn("generation_settings", payload["response_fields"])
        self.assertNotIn("prompt", payload["response_fields"])

    def test_capture_receipt_rejects_non_data_wire_line_and_clears_it(self):
        recorder = live.LiveCaptureWireRecorder()
        recorder(b"event: message\n")
        record = {
            "content": "",
            "execution": {
                name: None
                for name in live.harness.carrier.CAPTURE_EXECUTION_FIELDS
            },
        }
        record["execution"].update(
            content="",
            reasoning_content="",
            tool_calls=[],
            completion_tokens=0,
            generated_token_ids=[],
            generated_token_count=0,
            nonempty_token_array_event_count=0,
        )
        with self.assertRaisesRegex(
            live.ExperimentError,
            "non-SSE data line",
        ):
            live.validate_capture_receipt(record, recorder)
        self.assertFalse(recorder.lines)

    def test_intervening_stateful_actions_are_denied(self):
        for action in (
            "slot-save",
            "slot-restore",
            "slot-erase",
            "root-save",
            "root-restore",
            "root-erase",
            "set-lora",
        ):
            self.assertIn(
                f'reject_intervening_slot_action(task, "{action}")',
                self.context,
            )
        self.assertIn(
            "Intervening or malformed inference rejected while a one-use live terminal boundary is resident",
            self.context,
        )

    def test_live_preflight_bypasses_prompt_cache_slot_selection(self):
        dispatch = self.context[
            self.context.index("case SERVER_TASK_TYPE_COMPLETION:") :
            self.context.index("case SERVER_TASK_TYPE_SLOT_SAVE:")
        ]
        self.assertLess(
            dispatch.index("preflight_live_terminal_before_slot_selection"),
            dispatch.index("get_available_slot(task)"),
        )
        start = self.context.index(
            "server_slot * preflight_live_terminal_before_slot_selection"
        )
        preflight = self.context[
            start :
            self.context.index(
                "std::vector<common_adapter_lora_info> construct_lora_list",
                start,
            )
        ]
        self.assertIn("return &slot;", preflight)
        self.assertIn("slot.prompt_clear(false);", preflight)
        self.assertIn(
            "live.capture_request_epoch == neo3000_request_epoch",
            preflight,
        )
        self.assertIn("neo3000_live_terminal_contract_equal", preflight)

    def test_disconnect_or_cancel_poison_pending_live_boundary(self):
        release_start = self.context.index("void release() {")
        release = self.context[
            release_start :
            self.context.index("result_timings get_timings() const", release_start)
        ]
        self.assertIn(
            "terminal_logits_pending_use && terminal_logits.live.valid()",
            release,
        )
        self.assertIn("prompt_clear(false);", release)
        self.assertIn("poisoned on release", release)

    def test_shutdown_poisons_idle_live_boundary_before_backend_free(self):
        start = self.context.index(
            "void poison_live_terminal_boundaries_for_shutdown()"
        )
        method = self.context[
            start : self.context.index("void handle_sleeping_state", start)
        ]
        self.assertIn("slot.terminal_logits_pending_use", method)
        self.assertIn("slot.terminal_logits.live.valid()", method)
        self.assertNotIn(
            "if (!slot.terminal_logits_pending_use",
            method,
        )
        self.assertIn("slot.prompt_clear(false);", method)
        self.assertIn("slot.release();", method)
        self.assertIn("std::count_if(", method)
        self.assertIn(
            "shutdown custody poisoned=%zu unresolved=%zu",
            method,
        )
        self.assertIn(
            "void poison_live_terminal_boundaries_for_shutdown();",
            self.context_header,
        )
        cleanup_start = self.server_entrypoint.index(
            "clean_up = [&ctx_http, &ctx_server]()"
        )
        cleanup = self.server_entrypoint[
            cleanup_start :
            self.server_entrypoint.index(
                "llama_backend_free();",
                cleanup_start,
            )
        ]
        self.assertLess(
            cleanup.index("ctx_http.stop();"),
            cleanup.index(
                "ctx_server.poison_live_terminal_boundaries_for_shutdown();"
            ),
        )

    def test_live_boundary_cannot_enter_ram_root_terminal_receipt(self):
        root_save = self.context[
            self.context.index("case SERVER_TASK_TYPE_SLOT_ROOT_SAVE:") :
            self.context.index("case SERVER_TASK_TYPE_SLOT_ROOT_RESTORE:")
        ]
        self.assertLess(
            root_save.index('reject_intervening_slot_action(task, "root-save")'),
            root_save.index("root->terminal_logits = slot->terminal_logits;"),
        )

    def test_public_contract_is_deterministic_and_pre_output(self):
        request_id = live.predecessor.EXPECTED_REQUEST_SHA256["C"]
        first = live.public_contract(
            trial_label="trial-1-terminal",
            edge=1,
            input_boundary_id=request_id,
        )
        second = live.public_contract(
            trial_label="trial-1-terminal",
            edge=1,
            input_boundary_id=request_id,
        )
        self.assertEqual(first, second)
        self.assertEqual(first["generation"], 1)
        self.assertEqual(first["module_ordinal"], 1)
        self.assertEqual(first["restoration_policy"], "DECLARED_CLOSURE")
        self.assertNotIn("answer", first)
        self.assertNotIn("output", first)

    def test_wrong_owner_changes_only_owner_and_capture_use_share_contract(self):
        contract = live.public_contract(
            trial_label="warmup-terminal",
            edge=2,
            input_boundary_id=live.predecessor.EXPECTED_REQUEST_SHA256["D"],
        )
        wrong = live.wrong_owner_contract(contract)
        changed = {
            key
            for key in contract
            if contract[key] != wrong[key]
        }
        self.assertEqual(changed, {"port_owner"})

        base = {"prompt": [1, 2, 3], "n_predict": 1}
        capture = live.capture_payload(base, contract)
        consume = live.consumer_payload(base, contract)
        self.assertEqual(
            capture["neo3000_live_terminal"],
            consume["neo3000_live_terminal"],
        )
        self.assertEqual(capture["n_predict"], 0)
        self.assertTrue(capture["neo3000_capture_live_terminal_boundary"])
        self.assertTrue(consume["neo3000_use_live_terminal_boundary"])


if __name__ == "__main__":
    unittest.main()
