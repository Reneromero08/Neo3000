#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import json
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import holostate_live as holo
from catalytic_swarm_1_v5_completion_closure import (
    WARM_GATE_ORDER,
    CompletedResponseRejected,
)
from catalytic_swarm_1_v5_protocol import build_catalytic_swarm_1_v5_contract
from catalytic_swarm_1_v5_runtime_binding import build_v5_runtime_binding


ROOT = Path(__file__).resolve().parents[1]


class FakeLedger:
    def __init__(self) -> None:
        self.rows: list[dict[str, object]] = []
        self.events: list[str] = []

    def append(self, record: dict[str, object], **_: object) -> None:
        self.events.append("append")
        self.rows.append(dict(record))

    def sync(self) -> None:
        self.events.append("sync")


def warm_metadata(lease_id: int = 0) -> dict[str, object]:
    return {
        "task_id": "cs1-task-07", "arm": "common-root-warm",
        "turn_id": "cs1-task-07-warm", "phase": "warm", "role": "root",
        "assigned_parents": [], "candidate_id": "", "public_pass_count": None,
        "content_sha256": "A" * 64, "prompt_tokens": 10,
        "cached_prompt_tokens": 0, "required_cached_prompt_tokens": 0,
        "fresh_prompt_tokens": 10, "completion_tokens": 4,
        "token_evidence_scope": "metadata", "wddm_freshness_boundary": "post",
        "lease_id": lease_id, "request_started_at": "start", "request_finished_at": "finish",
    }


class V5ControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.binding = build_v5_runtime_binding()

    def test_real_evaluator_contract_and_paths_are_exact(self) -> None:
        evaluator = json.loads((ROOT / "lab/EVALUATOR.json").read_text(encoding="utf-8"))
        self.assertEqual(evaluator["catalytic_swarm_1_v5"], build_catalytic_swarm_1_v5_contract())
        declared = evaluator["catalytic_swarm_1_v5"]["one_shot"]["paths"]
        self.assertEqual(
            {key: declared[key] for key in ("control", "readiness", "parser_canary", "attempt", "result", "ledger", "task_results")},
            dict(zip(
                ("control", "readiness", "parser_canary", "attempt", "result", "ledger", "task_results"),
                (path.relative_to(ROOT).as_posix() for path in holo.CATALYTIC_SWARM_1_V5_ARTIFACT_PATHS),
                strict=True,
            )),
        )

    def test_v4_public_command_is_hard_retired(self) -> None:
        with self.assertRaisesRegex(holo.NeoLoopError, "consumed / no retry"):
            holo.command_audit_catalytic_swarm_1_v4(object())

    def test_v5_cli_requires_model_and_authorized_main(self) -> None:
        parser = holo.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["audit-catalytic-swarm-1-v5"])
        with self.assertRaises(SystemExit):
            parser.parse_args(["audit-catalytic-swarm-1-v5", "--model", "model.gguf"])

    def test_v5_state_is_absent_and_ignored(self) -> None:
        self.assertFalse(holo.CATALYTIC_SWARM_1_V5_STATE_ROOT.exists())
        for path in holo.CATALYTIC_SWARM_1_V5_ARTIFACT_PATHS:
            relative = path.relative_to(ROOT).as_posix()
            self.assertEqual(
                subprocess.run(["git", "check-ignore", "--quiet", relative], cwd=ROOT, check=False).returncode,
                0,
            )

    def test_task_7_rejection_is_fsynced_before_lease_release_and_stop(self) -> None:
        events: list[str] = []
        ledger = FakeLedger()
        pool = holo.PhysicalLeasePool(1)
        failed = {name: True for name in WARM_GATE_ORDER}
        failed["result_accepted"] = False

        def request(lease_id: int, completed: object) -> object:
            events.append("request")
            completed("cs1-task-07:common-root-warm")  # type: ignore[operator]
            return ({"summary": True}, warm_metadata(lease_id), "system", {}, failed)

        with self.assertRaises(CompletedResponseRejected):
            holo.run_catalytic_swarm_1_v5_completed_request(
                kind="warm", request_label="cs1-task-07:common-root-warm",
                request_sequence_index=775, lease_pool=pool,
                before=lambda: events.append("before"), request=request,
                after=lambda: events.append("after"),
                on_model_completed=lambda label: events.append("completed"),
                failure_metadata=lambda lease_id: warm_metadata(lease_id),
                ledger=ledger, runtime_binding=self.binding,
                persist_result_fallback=lambda row, error: events.append("fallback"),
            )
        self.assertEqual(events, ["before", "request", "completed", "after"])
        self.assertEqual(ledger.events, ["append", "sync"])
        self.assertEqual(len(ledger.rows), 1)
        self.assertEqual(ledger.rows[0]["response_reason_code"], "response-not-accepted")
        self.assertEqual(pool.active_count, 0)
        self.assertEqual(pool.lease_count, 1)

    def test_precompletion_failure_has_no_normal_completed_record(self) -> None:
        ledger = FakeLedger()
        pool = holo.PhysicalLeasePool(1)
        after: list[str] = []
        with self.assertRaisesRegex(holo.NeoLoopError, "before completion"):
            holo.run_catalytic_swarm_1_v5_completed_request(
                kind="warm", request_label="request", request_sequence_index=1,
                lease_pool=pool, before=lambda: None,
                request=lambda lease_id, completed: (_ for _ in ()).throw(holo.NeoLoopError("before completion")),
                after=lambda: after.append("after"), on_model_completed=lambda label: None,
                failure_metadata=lambda lease_id: warm_metadata(lease_id),
                ledger=ledger, runtime_binding=self.binding,
                persist_result_fallback=lambda row, error: None,
            )
        self.assertEqual(after, ["after"])
        self.assertEqual(ledger.rows, [])
        self.assertEqual(pool.active_count, 0)

    def test_post_request_failure_is_persisted_before_stop(self) -> None:
        ledger = FakeLedger()
        pool = holo.PhysicalLeasePool(1)
        accepted = {name: True for name in WARM_GATE_ORDER}
        with self.assertRaises(CompletedResponseRejected):
            holo.run_catalytic_swarm_1_v5_completed_request(
                kind="warm", request_label="request", request_sequence_index=1,
                lease_pool=pool, before=lambda: None,
                request=lambda lease_id, completed: (
                    completed("request"),
                    ({}, warm_metadata(lease_id), "system", {}, accepted),
                )[1],
                after=lambda: (_ for _ in ()).throw(holo.NeoLoopError("host boundary")),
                on_model_completed=lambda label: None,
                failure_metadata=lambda lease_id: warm_metadata(lease_id),
                ledger=ledger, runtime_binding=self.binding,
                persist_result_fallback=lambda row, error: None,
            )
        self.assertEqual(len(ledger.rows), 1)
        self.assertFalse(ledger.rows[0]["post_request_boundary"]["passed"])

    def test_actual_warm_function_exposes_all_eight_gate_cases(self) -> None:
        task = holo.build_frozen_task_suite().tasks[0]
        readiness = {
            "binary": {"sha256": "B" * 64},
            "model": {"sha256": "M" * 64},
            "chat_template_sha256": "C" * 64,
        }
        base = {
            "accepted": True,
            "finish_reason": "stop",
            "reasoning_content": {"present": False},
            "tool_calls": [],
            "visible_token_evidence": {"accepted": True, "claim_scope": "metadata"},
            "logical_prompt_tokens": 3,
            "cached_prompt_tokens": 0,
            "fresh_prompt_tokens": 3,
            "completion_tokens": 4,
            "assistant_content": {"sha256": "A" * 64},
        }
        cases = (
            ("result_accepted", {"accepted": False}, True),
            ("resource_gate_passed", {}, False),
            ("finish_reason_stop", {"finish_reason": "length"}, True),
            ("reasoning_absent", {"reasoning_content": {"present": True}}, True),
            ("tool_calls_empty", {"tool_calls": [{"id": "x"}]}, True),
            ("token_evidence_accepted", {"visible_token_evidence": {"accepted": False, "claim_scope": "metadata"}}, True),
            ("logical_prompt_count_matches", {"logical_prompt_tokens": 2}, True),
            (None, {}, True),
        )
        for failed_gate, changes, resource_passed in cases:
            with self.subTest(failed_gate=failed_gate):
                result = dict(base)
                result.update(changes)
                sidecar = SimpleNamespace(
                    wddm_freshness_boundaries=[{"boundary": "post-request:warm"}],
                    guarded=lambda name, call, request_completed=None: call(),
                )
                completed: list[str] = []
                def worker(*args: object, **kwargs: object) -> dict[str, object]:
                    kwargs["request_completed"]()
                    return result
                with mock.patch.object(holo, "CATALYTIC_SWARM_1_RUNTIME_VERSION", "v5"), mock.patch.object(
                    holo, "catalytic_swarm_1_public_root", return_value=("system", {"public_root_sha256":"p","system_message_sha256":"s","state_id":"state"}, "root")
                ), mock.patch.object(holo, "build_worker_chat_payload", return_value={"messages": []}), mock.patch.object(
                    holo, "render_messages", return_value="rendered"
                ), mock.patch.object(holo, "tokenize", return_value=[1, 2, 3]), mock.patch.object(
                    holo, "locate_public_root_terminal_token_index", return_value=2
                ), mock.patch.object(holo, "run_worker_v4_chat_request", side_effect=worker), mock.patch.object(
                    holo, "worker_resource_gate", return_value={"passed": resource_passed}
                ):
                    observed = holo.catalytic_swarm_1_warm_request(
                        sidecar, {}, {}, readiness, task,
                        request_sequence_index=775, lease_id=0,
                        model_request_completed=completed.append,
                    )
                self.assertEqual(len(observed), 5)
                gate_outcomes = observed[4]
                if failed_gate is None:
                    self.assertTrue(all(gate_outcomes.values()))
                else:
                    self.assertFalse(gate_outcomes[failed_gate])
                self.assertEqual(completed, [f"{task.task_id}:common-root-warm"])

    def test_actual_comparison_function_preserves_negative_observations(self) -> None:
        task = holo.build_frozen_task_suite().tasks[0]
        turn = holo.build_all_arm_plans()[0].turns[0]
        protocol = {"endpoint": "/v1/chat/completions", "model_alias": "agents-a1"}
        payload = {
            "messages": [], "model": "agents-a1", "max_tokens": 32,
            "temperature": 0.0, "seed": turn.seed, "cache_prompt": True,
            "stream": True, "chat_template_kwargs": {"enable_thinking": False},
        }
        identity = {
            "_warm_rendered_prompt": "warm", "_warm_prompt_token_ids": [1, 2, 3],
            "public_root_terminal_token_index": 2,
        }
        compact = {
            "logical_prompt_tokens": 4, "cached_prompt_tokens": 2,
            "fresh_prompt_tokens": 2, "completion_tokens": 2,
            "finish_reason": "stop", "reasoning_content": {"present": False},
            "tool_calls": [], "prompt_token_identity_matches": True,
        }
        cases = ("parse", "transport", "admission")
        for failure in cases:
            with self.subTest(failure=failure):
                completed: list[str] = []
                admission = SimpleNamespace(to_dict=lambda: {"admitted": failure != "admission"})
                parse_effect = ValueError("malformed") if failure == "parse" else None
                with mock.patch.object(holo, "CATALYTIC_SWARM_1_RUNTIME_VERSION", "v5"), mock.patch.object(
                    holo, "build_worker_chat_payload", return_value=payload
                ), mock.patch.object(holo, "render_messages", return_value="rendered"), mock.patch.object(
                    holo, "tokenize", return_value=[1, 2, 3, 4]
                ), mock.patch.object(holo, "catalytic_swarm_1_required_cached_prefix", return_value=3), mock.patch.object(
                    holo, "locate_public_root_terminal_token_index", return_value=2
                ), mock.patch.object(holo, "exact_common_token_prefix", return_value=2), mock.patch.object(
                    holo, "stream_completion", return_value=SimpleNamespace(content='{"candidate_id":"C00"}')
                ), mock.patch.object(holo, "compact_worker_v4_measurement", return_value=dict(compact)), mock.patch.object(
                    holo, "resolve_worker_v4_visible_token_evidence", return_value={"visible_token_evidence":{"accepted":True,"claim_scope":"metadata"}}
                ), mock.patch.object(
                    holo, "classify_worker_v4_channels", return_value="rejected" if failure == "transport" else "accepted"
                ), mock.patch.object(
                    holo, "parse_candidate_content", side_effect=parse_effect, return_value="C00"
                ), mock.patch.object(holo, "adjudicate_root_cache", return_value=admission), mock.patch.object(
                    holo, "catalytic_swarm_1_public_pass_for_ledger", return_value=1
                ):
                    observed = holo.stream_catalytic_swarm_1_candidate(
                        protocol, task, turn, "system", identity, "assignment",
                        request_sequence_index=2, lease_id=0,
                        model_request_completed=completed.append,
                    )
                self.assertEqual(len(observed), 3)
                gates = observed[2]
                expected_gate = {
                    "parse": "candidate_parse_passed",
                    "transport": "transport_accepted",
                    "admission": "root_terminal_admitted",
                }[failure]
                self.assertFalse(gates[expected_gate])
                self.assertEqual(len(completed), 1)

    def test_v5_terminal_wddm_order_places_ledger_backed_warm_after_canary(self) -> None:
        captured: dict[str, object] = {}
        def reconcile(policy: object, cleanup: object, *, required_boundaries: object) -> dict[str, object]:
            captured["boundaries"] = required_boundaries
            return {"passed": True, "reasons": []}
        with mock.patch.object(holo, "CATALYTIC_SWARM_1_RUNTIME_VERSION", "v5"), mock.patch.object(
            holo, "reconcile_terminal_wddm", side_effect=reconcile
        ):
            result = holo.reconcile_catalytic_swarm_1_terminal_wddm(
                {"readiness_control": {"wddm_transient_gap_policy": {}}},
                {},
                completed_model_requests=1,
            )
        boundaries = captured["boundaries"]
        self.assertEqual(
            boundaries[:4],
            ["readiness-admission", "before-parser-canary", "after-parser-canary", "before-capability-attempt"],
        )
        self.assertTrue(boundaries[4].startswith("pre-request:cs1-task-01:common-root-warm"))
        self.assertTrue(result["passed"])


if __name__ == "__main__":
    unittest.main()
