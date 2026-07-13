#!/usr/bin/env python3
from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import holostate_live as live
from catalytic_swarm_1_v6_post_request_closure import (
    BOUNDARY_ORDER,
    BoundaryObservation,
    CompletedResponsePersistenceError,
    CompletedResponseRejected,
)
from catalytic_swarm_1_v6_protocol import (
    EXPECTED_V6_CONTRACT_SHA256,
    build_catalytic_swarm_1_v6_contract,
)
from catalytic_swarm_1_v6_runtime_binding import (
    V5_PARTIAL_EXECUTION_BOUNDARY_SHA256,
    V6_CLAIM_CONTRACT_SHA256,
    build_v6_runtime_binding,
)
from catalytic_swarm_1_v6_runtime_binding_protocol import (
    EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256,
    build_v6_runtime_evidence_contract,
)


AUTHORIZED_MAIN = "a" * 40


class FakeLedger:
    def __init__(self, *, sync_error: BaseException | None = None) -> None:
        self.rows: list[dict[str, object]] = []
        self.envelopes: list[tuple[str, int]] = []
        self.sync_error = sync_error

    def append(
        self,
        record: dict[str, object],
        *,
        request_label: str,
        request_sequence_index: int,
    ) -> None:
        self.rows.append(dict(record))
        self.envelopes.append((request_label, request_sequence_index))

    def sync(self) -> None:
        if self.sync_error is not None:
            raise live.LedgerPersistenceAbsent(self.sync_error)

    def append_durable(
        self,
        record: dict[str, object],
        *,
        request_label: str,
        request_sequence_index: int,
    ) -> None:
        if self.sync_error is not None:
            raise live.LedgerPersistenceAbsent(self.sync_error)
        self.append(
            record,
            request_label=request_label,
            request_sequence_index=request_sequence_index,
        )


def runtime_stats() -> dict[str, object]:
    return {
        "post_request_groups_started": 0,
        "post_request_attempts": {name: 0 for name in BOUNDARY_ORDER},
        "post_request_observations_completed": {
            name: 0 for name in BOUNDARY_ORDER
        },
        "post_request_passes": {name: 0 for name in BOUNDARY_ORDER},
        "post_request_blocked": {name: 0 for name in BOUNDARY_ORDER},
        "v6_lease_released_count": 0,
    }


def warm_metadata() -> dict[str, object]:
    return {
        "task_id": "cs1-task-01",
        "arm": "common-root-warm",
        "turn_id": "cs1-task-01-warm",
        "phase": "warm",
        "role": "root",
        "assigned_parents": [],
        "candidate_id": "",
        "public_pass_count": None,
        "content_sha256": "0" * 64,
        "prompt_tokens": 10,
        "cached_prompt_tokens": 0,
        "required_cached_prompt_tokens": 0,
        "fresh_prompt_tokens": 10,
        "completion_tokens": 1,
        "token_evidence_scope": "visible",
        "wddm_freshness_boundary": "post-request-deferred-to-v6-closure",
        "lease_id": 0,
        "request_started_at": "2026-07-13T00:00:00+00:00",
        "request_finished_at": "2026-07-13T00:00:01+00:00",
    }


def comparison_metadata() -> dict[str, object]:
    value = warm_metadata()
    value.update({
        "arm": "serial-chain",
        "turn_id": "cs1-chain-t01",
        "phase": "generate",
        "role": "generator",
        "candidate_id": "C00",
        "public_pass_count": 1,
        "prompt_tokens": 6,
        "cached_prompt_tokens": 4,
        "required_cached_prompt_tokens": 4,
        "fresh_prompt_tokens": 2,
        "public_root_terminal_token_index": 4,
        "common_prefix_tokens": 4,
        "response_completed": True,
        "transport_passed": True,
        "token_evidence_passed": True,
    })
    return value


def warm_gates(**changes: bool) -> dict[str, bool]:
    value = {
        "result_accepted": True,
        "resource_gate_passed": True,
        "finish_reason_stop": True,
        "reasoning_absent": True,
        "tool_calls_empty": True,
        "token_evidence_accepted": True,
        "logical_prompt_count_matches": True,
    }
    value.update(changes)
    return value


def comparison_gates(**changes: bool) -> dict[str, bool]:
    value = {
        "candidate_parse_passed": True,
        "transport_accepted": True,
        "finish_reason_stop": True,
        "reasoning_absent": True,
        "tool_calls_empty": True,
        "token_evidence_accepted": True,
        "prompt_token_identity_matches": True,
        "root_terminal_admitted": True,
    }
    value.update(changes)
    return value


def pass_observers(called: list[str] | None = None):
    def observe(name: str):
        if called is not None:
            called.append(name)
        return BoundaryObservation.passed({"name": name})

    return {name: (lambda name=name: observe(name)) for name in BOUNDARY_ORDER}


class V6CompletedRequestControllerTests(unittest.TestCase):
    def run_completed(
        self,
        *,
        kind: str = "warm",
        observers=None,
        ledger: FakeLedger | None = None,
        gates: dict[str, bool] | None = None,
        capture: dict[str, object] | None = None,
    ):
        label = (
            "cs1-task-01:common-root-warm"
            if kind == "warm"
            else "cs1-task-01:serial-chain:cs1-chain-t01"
        )
        stats = runtime_stats()
        groups: list[dict[str, object]] = []
        ledger_records: list[dict[str, object]] = []
        fallbacks: list[dict[str, object]] = []
        fallback_receipts: list[tuple[dict[str, object], str]] = []
        completed: list[str] = []
        active_ledger = ledger or FakeLedger()
        lease_pool = live.PhysicalLeasePool(1)
        if capture is not None:
            capture.update({
                "stats": stats,
                "groups": groups,
                "ledger_records": ledger_records,
                "fallbacks": fallbacks,
                "fallback_receipts": fallback_receipts,
                "ledger": active_ledger,
                "lease_pool": lease_pool,
            })

        def request(_lease_id: int, mark) -> object:
            mark(label)
            if kind == "warm":
                return (
                    {"summary": True},
                    warm_metadata(),
                    "system",
                    {"identity": True},
                    gates or warm_gates(),
                )
            transport = {
                "content": '{"candidate_id":"C00"}',
                "prompt_tokens": 6,
                "cached_prompt_tokens": 4,
                "required_cached_prompt_tokens": 4,
                "fresh_prompt_tokens": 2,
                "completion_tokens": 1,
                "finish_reason": "stop",
                "reasoning_content": "",
                "tool_calls": [],
                "transport_passed": True,
                "token_evidence_scope": "visible",
                "public_root_terminal_token_index": 4,
                "common_prefix_tokens": 4,
                "cache_admission": {"admitted": True},
            }
            return transport, comparison_metadata(), gates or comparison_gates()

        def persist_fallback(record, error):
            fallback_receipts.append((record, error))
            return record

        with patch.object(live, "CATALYTIC_SWARM_1_RUNTIME_VERSION", "v6"):
            value = live.run_catalytic_swarm_1_v6_completed_request(
                kind=kind,
                request_label=label,
                request_sequence_index=1,
                lease_pool=lease_pool,
                before=lambda: None,
                request=request,
                observers=observers or pass_observers(),
                on_model_completed=completed.append,
                failure_metadata=lambda _lease: (
                    warm_metadata() if kind == "warm" else comparison_metadata()
                ),
                ledger=active_ledger,  # type: ignore[arg-type]
                runtime_binding=build_v6_runtime_binding(),
                persist_result_fallback=persist_fallback,
                runtime_stats=stats,
                group_records=groups,  # type: ignore[arg-type]
                ledger_records=ledger_records,  # type: ignore[arg-type]
                fallback_records=fallbacks,  # type: ignore[arg-type]
            )
        return {
            "value": value,
            "stats": stats,
            "groups": groups,
            "ledger_records": ledger_records,
            "fallbacks": fallbacks,
            "fallback_receipts": fallback_receipts,
            "ledger": active_ledger,
            "completed": completed,
        }

    def test_pass_persists_identity_before_release_and_counts_every_boundary(self) -> None:
        result = self.run_completed()
        self.assertEqual(result["completed"], ["cs1-task-01:common-root-warm"])
        self.assertEqual(len(result["ledger_records"]), 1)
        row = result["ledger_records"][0]
        self.assertEqual(row["claim_contract_sha256"], V6_CLAIM_CONTRACT_SHA256)
        self.assertEqual(
            row["predecessor_boundary_sha256"],
            V5_PARTIAL_EXECUTION_BOUNDARY_SHA256,
        )
        self.assertNotIn("catalytic_swarm_1_v5", row)
        self.assertEqual(result["stats"]["post_request_groups_started"], 1)
        self.assertEqual(
            result["stats"]["post_request_attempts"],
            {name: 1 for name in BOUNDARY_ORDER},
        )
        self.assertEqual(
            result["stats"]["post_request_observations_completed"],
            {name: 1 for name in BOUNDARY_ORDER},
        )
        self.assertEqual(result["stats"]["v6_lease_released_count"], 1)

    def test_failure_error_and_multiple_nonpasses_do_not_short_circuit(self) -> None:
        called: list[str] = []

        def observe(name: str):
            called.append(name)
            if name == "wddm":
                return BoundaryObservation.failed("stale")
            if name == "stable_custody":
                raise OSError("private diagnostic")
            if name == "candidate_custody":
                return BoundaryObservation.unavailable("missing")
            return BoundaryObservation.passed()

        observers = {
            name: (lambda name=name: observe(name)) for name in BOUNDARY_ORDER
        }
        with self.assertRaises(CompletedResponseRejected):
            self.run_completed(observers=observers)
        self.assertEqual(called, list(BOUNDARY_ORDER))

    def test_interruption_at_each_boundary_persists_then_releases(self) -> None:
        for interrupted_name in BOUNDARY_ORDER:
            with self.subTest(interrupted_name=interrupted_name):
                called: list[str] = []

                def observe(name: str):
                    called.append(name)
                    if name == interrupted_name:
                        raise KeyboardInterrupt("bounded")
                    return BoundaryObservation.passed()

                observers = {
                    name: (lambda name=name: observe(name))
                    for name in BOUNDARY_ORDER
                }
                with self.assertRaises(KeyboardInterrupt):
                    captured: dict[str, object] = {}
                    self.run_completed(observers=observers, capture=captured)
                expected_count = list(BOUNDARY_ORDER).index(interrupted_name) + 1
                self.assertEqual(len(called), expected_count)
                self.assertEqual(len(captured["groups"]), 1)
                self.assertEqual(captured["stats"]["v6_lease_released_count"], 1)
                self.assertEqual(captured["lease_pool"].active_count, 0)

    def test_ledger_failure_uses_one_fallback_and_releases(self) -> None:
        ledger = FakeLedger(sync_error=OSError("private path"))
        captured: dict[str, object] = {}
        with self.assertRaises(CompletedResponsePersistenceError):
            self.run_completed(ledger=ledger, capture=captured)
        self.assertEqual(len(ledger.rows), 0)
        self.assertEqual(len(captured["groups"]), 1)
        self.assertEqual(len(captured["fallbacks"]), 1)
        self.assertEqual(len(captured["fallback_receipts"]), 1)
        self.assertEqual(captured["stats"]["v6_lease_released_count"], 1)
        self.assertEqual(captured["lease_pool"].active_count, 0)

    def test_stream_ledger_sync_failure_rolls_back_before_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = live.BoundedStreamLedger(
                root / "ledger-v6.jsonl",
                max_bytes=4096,
                max_records=8,
                state_root=root,
            )
            real_fsync = live.os.fsync
            calls = 0

            def fail_first_fsync(descriptor: int) -> None:
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise OSError("simulated durability failure")
                real_fsync(descriptor)

            with patch.object(live.os, "fsync", side_effect=fail_first_fsync):
                with self.assertRaises(live.LedgerPersistenceAbsent) as raised:
                    ledger.append_durable(
                        {"bounded": True},
                        request_label="request-1",
                        request_sequence_index=1,
                    )
            self.assertIsInstance(raised.exception.original_exception, OSError)
            self.assertEqual(ledger.record_count, 0)
            self.assertEqual(ledger.bytes_written, 0)
            self.assertEqual((root / "ledger-v6.jsonl").read_bytes(), b"")
            ledger.close()

    def test_warm_and_comparison_share_boundary_order_and_counter_law(self) -> None:
        called_warm: list[str] = []
        called_comparison: list[str] = []
        warm = self.run_completed(observers=pass_observers(called_warm))
        comparison = self.run_completed(
            kind="comparison", observers=pass_observers(called_comparison)
        )
        self.assertEqual(called_warm, list(BOUNDARY_ORDER))
        self.assertEqual(called_comparison, list(BOUNDARY_ORDER))
        for result in (warm, comparison):
            entries = result["groups"][0]["post_request_boundary"]["sub_boundaries"]
            self.assertEqual([entry["name"] for entry in entries], list(BOUNDARY_ORDER))
            self.assertEqual([entry["state"] for entry in entries], ["passed"] * 4)


class GuardedDeferralTests(unittest.TestCase):
    def make_sidecar(self, *, resilient: bool):
        sidecar = object.__new__(live.LiveSidecar)
        sidecar.wddm_policy = (
            SimpleNamespace(max_valid_sample_gap_seconds=5.0)
            if resilient
            else None
        )
        sidecar.process = None
        calls: list[str] = []
        sidecar.wait_for_fresh_wddm = lambda boundary, *_args, **_kwargs: (
            calls.append(f"wddm:{boundary}") or {"passed": True}
        )
        sidecar.require_active = lambda *args, **kwargs: calls.append("active")
        sidecar.exact_ownership = lambda boundary, **kwargs: (
            calls.append(f"ownership:{boundary}") or {"passed": True}
        )
        return sidecar, calls

    def test_v6_deferral_skips_internal_post_wddm_and_legacy_ownership(self) -> None:
        sidecar, calls = self.make_sidecar(resilient=True)
        value = sidecar.guarded(
            "cs1-task-01:common-root-warm",
            lambda: "complete",
            request_completed=lambda: True,
            defer_post_request_wddm=True,
        )
        self.assertEqual(value, "complete")
        self.assertEqual(
            calls,
            ["wddm:pre-request:cs1-task-01:common-root-warm"],
        )

    def test_non_deferred_resilient_and_legacy_paths_are_unchanged(self) -> None:
        resilient, resilient_calls = self.make_sidecar(resilient=True)
        resilient.guarded("v5-request", lambda: "complete")
        self.assertEqual(
            resilient_calls,
            ["wddm:pre-request:v5-request", "wddm:post-request:v5-request"],
        )
        legacy, legacy_calls = self.make_sidecar(resilient=False)
        legacy.guarded("v1-request", lambda: "complete")
        self.assertEqual(
            legacy_calls,
            [
                "active",
                "ownership:pre-request:v1-request",
                "active",
                "ownership:post-request:v1-request",
            ],
        )


class V6ClaimAndCommandTests(unittest.TestCase):
    def test_checked_in_evaluator_lock_verifies_v6_identities(self) -> None:
        evaluator = live.load_json(live.EVALUATOR_PATH)
        lock = live.verify_lock(evaluator)
        self.assertEqual(
            lock["catalytic_swarm_1_v5_partial_execution_boundary_sha256"],
            V5_PARTIAL_EXECUTION_BOUNDARY_SHA256,
        )
        self.assertEqual(
            lock["catalytic_swarm_1_v6_sha256"],
            EXPECTED_V6_CONTRACT_SHA256,
        )
        self.assertEqual(
            lock["catalytic_swarm_1_v6_runtime_evidence_binding_sha256"],
            EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256,
        )

    def test_active_v6_control_uses_order_insensitive_v4_path_qualification(self) -> None:
        active = build_catalytic_swarm_1_v6_contract()
        scheduler = live.load_json(live.EVALUATOR_PATH)["catalytic_swarm_1"]
        binding = build_v6_runtime_binding()
        qualified = {"passed": True}
        with live.catalytic_swarm_1_v6_runtime_namespace(active, binding):
            with patch.object(
                live, "qualify_v4_one_shot_paths", return_value=qualified
            ) as qualifier:
                result = live.qualify_active_catalytic_swarm_1_control(
                    scheduler, stable_tokenizer=False
                )
        self.assertEqual(result["one_shot_path_qualification"], qualified)
        qualifier.assert_called_once()

    def test_corrected_canonical_identities_are_the_only_v6_identities(self) -> None:
        self.assertEqual(
            EXPECTED_V6_CONTRACT_SHA256,
            "8136be5c402497b539595eeccf1329807eba59fab9813891f0293fd1d271acd8",
        )
        self.assertEqual(EXPECTED_V6_CONTRACT_SHA256, V6_CLAIM_CONTRACT_SHA256)
        self.assertEqual(
            EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256,
            "3ccb810684824a5935c89150e0f84ca820f8402f7650d3fdcf027e84ac9f9ad3",
        )

    def test_parser_dispatches_retired_v6_and_v5_commands(self) -> None:
        args = live.build_parser().parse_args([
            "audit-catalytic-swarm-1-v6",
            "--model",
            "model.gguf",
            "--authorized-main",
            AUTHORIZED_MAIN,
        ])
        self.assertIs(args.handler, live.command_audit_catalytic_swarm_1_v6)
        with self.assertRaisesRegex(live.NeoLoopError, "consumed / no retry"):
            live.command_audit_catalytic_swarm_1_v5(SimpleNamespace())
        with (
            patch.object(
                live,
                "run_catalytic_swarm_1_v6_audit",
                side_effect=AssertionError("retired runner must stay unreachable"),
            ),
            self.assertRaisesRegex(live.NeoLoopError, "consumed / no retry"),
        ):
            live.command_audit_catalytic_swarm_1_v6(SimpleNamespace())

    def test_invocation_is_claimed_before_fallible_preclaim(self) -> None:
        events: list[str] = []
        claimed: list[dict[str, object]] = []
        custody = object()

        def claim(_path, record, **_kwargs):
            events.append("claim")
            claimed.append(dict(record))

        def fail_prepare(*_args, **_kwargs):
            events.append("prepare")
            raise live.NeoLoopError("preclaim failed")

        with (
            patch.object(
                live,
                "capture_preclaim_custody",
                side_effect=lambda *_args, **_kwargs: events.append(
                    "capture-custody"
                ) or custody,
            ),
            patch.object(live, "claim_catalytic_swarm_1_runtime_json_once", claim),
            patch.object(
                live,
                "validate_postclaim_custody",
                side_effect=lambda observed: events.append("validate-custody")
                if observed is custody
                else (_ for _ in ()).throw(AssertionError("wrong custody")),
            ),
            patch.object(live, "prepare_catalytic_swarm_1_v6_claim", fail_prepare),
            patch.object(live, "write_catalytic_swarm_1_runtime_json"),
        ):
            with self.assertRaisesRegex(live.NeoLoopError, "preclaim failed"):
                live.run_catalytic_swarm_1_v6_audit(SimpleNamespace(
                    authorized_main=AUTHORIZED_MAIN,
                    model="model.gguf",
                    binary="server.exe",
                ))
        self.assertEqual(
            events,
            ["capture-custody", "claim", "validate-custody", "prepare"],
        )
        self.assertEqual(claimed[0]["supplied_model_path"], "model.gguf")
        self.assertEqual(claimed[0]["supplied_binary_path"], "server.exe")
        self.assertEqual(
            claimed[0]["expected_model_identity"]["sha256"],
            live.EXPECTED_MODEL_SHA256,
        )
        self.assertEqual(
            claimed[0]["expected_binary_identity"]["sha256"],
            live.EXPECTED_BINARY_SHA256,
        )

    def test_prepare_v6_uses_canonical_boundary_and_contracts_without_live_io(self) -> None:
        evaluator = {
            "catalytic_swarm_1_v6": build_catalytic_swarm_1_v6_contract(),
            "catalytic_swarm_1_v6_runtime_evidence_binding": (
                build_v6_runtime_evidence_contract()
            ),
        }
        lock = {
            "catalytic_swarm_1_v6_sha256": EXPECTED_V6_CONTRACT_SHA256,
            "catalytic_swarm_1_v6_runtime_evidence_binding_sha256": (
                EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256
            ),
        }
        events: list[str] = []

        def git_read(_root, *args):
            events.append("git")
            if args and args[0] == "ls-remote":
                return f"{AUTHORIZED_MAIN}\trefs/heads/main"
            return AUTHORIZED_MAIN

        with (
            patch.object(live, "assert_catalytic_swarm_1_v6_artifacts_absent"),
            patch.object(live, "load_json", return_value=evaluator),
            patch.object(live, "verify_lock", return_value=lock),
            patch.object(
                live,
                "validate_consumed_catalytic_swarm_1_v5_boundary",
                side_effect=lambda *_args: events.append("v5-boundary") or {},
            ),
            patch.object(live, "catalytic_swarm_1_v6_hash", return_value=EXPECTED_V6_CONTRACT_SHA256),
            patch.object(
                live,
                "catalytic_swarm_1_v6_runtime_evidence_binding_hash",
                return_value=EXPECTED_RUNTIME_EVIDENCE_CONTRACT_SHA256,
            ),
            patch.object(live, "validate_v6_runtime_contract_bindings"),
            patch.object(live, "git_read", side_effect=git_read),
            patch.object(live, "qualify_v4_one_shot_paths"),
        ):
            contract, binding = live.prepare_catalytic_swarm_1_v6_claim(
                SimpleNamespace(
                    authorized_main=AUTHORIZED_MAIN,
                    model="model.gguf",
                )
            )
        self.assertEqual(events[0], "v5-boundary")
        self.assertEqual(contract["id"], "catalytic_swarm_1_v6")
        self.assertEqual(binding.claim_contract_sha256, EXPECTED_V6_CONTRACT_SHA256)


if __name__ == "__main__":
    unittest.main()
