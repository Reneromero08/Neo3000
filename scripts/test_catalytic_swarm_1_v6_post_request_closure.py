#!/usr/bin/env python3
"""Focused unit tests for the pure CS1-v6 post-request closure."""

from __future__ import annotations

import copy
import unittest

from catalytic_swarm_1_v6_post_request_closure import (
    BOUNDARY_ORDER,
    BoundaryObservation,
    CatalyticSwarm1V6ClosureError,
    CompletedResponseClosure,
    CompletedResponsePersistenceError,
    CompletedResponseRejected,
    PostRequestBoundaryGroup,
    TerminalReconciliationError,
    reconcile_terminal,
)


def warm_gates(**changes: bool) -> dict[str, bool]:
    gates = {
        "result_accepted": True,
        "resource_gate_passed": True,
        "finish_reason_stop": True,
        "reasoning_absent": True,
        "tool_calls_empty": True,
        "token_evidence_accepted": True,
        "logical_prompt_count_matches": True,
    }
    gates.update(changes)
    return gates


class Clock:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"2026-07-13T00:00:{self.value:02d}.000000+00:00"


def pass_observers() -> dict[str, object]:
    return {
        name: (lambda name=name: BoundaryObservation.passed({"witness": name}))
        for name in BOUNDARY_ORDER
    }


def make_closure(
    *,
    observers: dict[str, object] | None = None,
    sequence: int = 1,
    gates: dict[str, bool] | None = None,
) -> CompletedResponseClosure:
    closure = CompletedResponseClosure(f"request-{sequence}", sequence, "warm")
    closure.mark_model_completed()
    closure.capture({"transport": "complete"}, gates or warm_gates())
    closure.observe_post_request_boundaries(observers or pass_observers(), clock=Clock())
    return closure


def persist_ledger(closure: CompletedResponseClosure) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    record = closure.persist(
        append_ledger=rows.append,
        sync_ledger=lambda: None,
        persist_result_fallback=lambda _record, _reason: None,
    )
    closure.mark_lease_released()
    return record


class BoundaryGroupTests(unittest.TestCase):
    def test_all_pass_attempt_is_recorded_before_each_callback(self) -> None:
        closure = CompletedResponseClosure("request-1", 1, "warm")
        closure.mark_model_completed()
        closure.capture({}, warm_gates())
        seen: list[tuple[str, bool, str | None]] = []
        closure.observe_post_request_boundaries(
            pass_observers(),
            clock=Clock(),
            before_callback=lambda name, entry: seen.append(
                (name, bool(entry["attempted"]), entry["attempted_at"])
            ),
        )
        self.assertEqual([item[0] for item in seen], list(BOUNDARY_ORDER))
        self.assertTrue(all(item[1] and item[2] for item in seen))
        group = closure.post_request_group
        assert group is not None
        self.assertEqual(group.ordered_reason_codes, [])
        self.assertTrue(closure.accepted)
        self.assertEqual(
            [entry["attempt_ordinal"] for entry in group.as_record()["sub_boundaries"]],
            [1, 2, 3, 4],
        )

    def test_group_cannot_begin_before_model_completion(self) -> None:
        with self.assertRaisesRegex(CatalyticSwarm1V6ClosureError, "before model completion"):
            PostRequestBoundaryGroup.begin_after_model_completion(
                request_label="request-1",
                request_sequence_index=1,
                kind="warm",
                model_completed=False,
            )

    def test_before_callback_interruption_is_durable_and_blocks_later_entries(self) -> None:
        closure = CompletedResponseClosure("request-1", 1, "warm")
        closure.mark_model_completed()
        closure.capture({}, warm_gates())

        def before(name, _entry):
            if name == "stable_custody":
                raise KeyboardInterrupt()

        record = closure.observe_post_request_boundaries(
            pass_observers(), before_callback=before
        )
        self.assertEqual(
            [entry["state"] for entry in record["sub_boundaries"]],
            ["passed", "interrupted", "blocked", "blocked"],
        )

    def test_each_single_failed_invariant_is_independent_and_ordered(self) -> None:
        for failed_name in BOUNDARY_ORDER:
            with self.subTest(failed_name=failed_name):
                called: list[str] = []
                observers = pass_observers()
                for name in BOUNDARY_ORDER:
                    base = observers[name]
                    observers[name] = lambda name=name, base=base: (
                        called.append(name),
                        BoundaryObservation.failed("ceiling-breached", {"actual": 2, "limit": 1})
                        if name == failed_name
                        else base(),
                    )[1]
                closure = make_closure(observers=observers)
                self.assertEqual(called, list(BOUNDARY_ORDER))
                group = closure.post_request_group
                assert group is not None
                self.assertEqual(group.primary_reason_code, f"{failed_name}-ceiling-breached")
                failed = next(e for e in group.boundaries if e["name"] == failed_name)
                self.assertTrue(failed["observation_completed"])
                self.assertIs(failed["passed"], False)

    def test_each_single_error_continues_without_raw_exception_message(self) -> None:
        for error_name in BOUNDARY_ORDER:
            with self.subTest(error_name=error_name):
                called: list[str] = []
                observers = pass_observers()

                def observer(name: str):
                    called.append(name)
                    if name == error_name:
                        raise RuntimeError("secret local path and diagnostic")
                    return BoundaryObservation.passed()

                observers = {name: (lambda name=name: observer(name)) for name in BOUNDARY_ORDER}
                closure = make_closure(observers=observers)
                self.assertEqual(called, list(BOUNDARY_ORDER))
                group = closure.post_request_group
                assert group is not None
                entry = next(e for e in group.boundaries if e["name"] == error_name)
                self.assertEqual(entry["state"], "observation-error")
                self.assertEqual(entry["exception_type"], "RuntimeError")
                self.assertEqual(len(entry["exception_message_sha256"]), 64)
                self.assertNotIn("secret", str(group.as_record()))

    def test_each_single_unavailable_continues_without_false_measurement(self) -> None:
        for unavailable_name in BOUNDARY_ORDER:
            with self.subTest(unavailable_name=unavailable_name):
                called: list[str] = []

                def observer(name: str):
                    called.append(name)
                    if name == unavailable_name:
                        return BoundaryObservation.unavailable("telemetry-missing")
                    return BoundaryObservation.passed()

                observers = {name: (lambda name=name: observer(name)) for name in BOUNDARY_ORDER}
                closure = make_closure(observers=observers)
                self.assertEqual(called, list(BOUNDARY_ORDER))
                group = closure.post_request_group
                assert group is not None
                entry = next(e for e in group.boundaries if e["name"] == unavailable_name)
                self.assertEqual(entry["state"], "unavailable")
                self.assertFalse(entry["observation_completed"])
                self.assertIsNone(entry["passed"])

    def test_multiple_failures_keep_complete_fixed_order_and_primary(self) -> None:
        observers = pass_observers()
        observers["wddm"] = lambda: BoundaryObservation.failed("stale")
        observers["stable_custody"] = lambda: (_ for _ in ()).throw(OSError("private"))
        observers["candidate_custody"] = lambda: BoundaryObservation.unavailable("missing")
        closure = make_closure(observers=observers)
        group = closure.post_request_group
        assert group is not None
        self.assertEqual(group.ordered_reason_codes, [
            "wddm-stale",
            "stable_custody-observation-error",
            "candidate_custody-missing",
        ])
        self.assertEqual(group.primary_reason_code, "wddm-stale")

    def test_interruption_at_each_position_blocks_only_later_entries(self) -> None:
        for position, interrupted_name in enumerate(BOUNDARY_ORDER):
            with self.subTest(interrupted_name=interrupted_name):
                called: list[str] = []

                def observer(name: str):
                    called.append(name)
                    if name == interrupted_name:
                        raise KeyboardInterrupt("do not serialize me")
                    return BoundaryObservation.passed()

                observers = {name: (lambda name=name: observer(name)) for name in BOUNDARY_ORDER}
                closure = make_closure(observers=observers)
                self.assertEqual(called, list(BOUNDARY_ORDER[: position + 1]))
                group = closure.post_request_group
                assert group is not None
                states = [entry["state"] for entry in group.boundaries]
                self.assertEqual(states[:position], ["passed"] * position)
                self.assertEqual(states[position], "interrupted")
                self.assertEqual(states[position + 1 :], ["blocked"] * (3 - position))
                record = persist_ledger(closure)
                self.assertEqual(record["response_disposition"], "rejected")
                with self.assertRaises(KeyboardInterrupt):
                    closure.enforce()


class CompletionPersistenceTests(unittest.TestCase):
    def test_gate_failure_remains_primary_but_boundary_reasons_are_preserved(self) -> None:
        observers = pass_observers()
        observers["wddm"] = lambda: BoundaryObservation.failed("stale")
        closure = make_closure(
            observers=observers,
            gates=warm_gates(finish_reason_stop=False),
        )
        record = persist_ledger(closure)
        self.assertEqual(record["response_reason_code"], "finish-reason-not-stop")
        self.assertEqual(
            record["all_reason_codes"],
            ["finish-reason-not-stop", "wddm-stale"],
        )
        with self.assertRaises(CompletedResponseRejected):
            closure.enforce()

    def test_ledger_success_is_exactly_once_and_lease_precedes_enforcement(self) -> None:
        closure = make_closure()
        rows: list[dict[str, object]] = []
        record = closure.persist(
            append_ledger=rows.append,
            sync_ledger=lambda: None,
            persist_result_fallback=lambda _record, _reason: self.fail("unexpected fallback"),
        )
        self.assertEqual(rows, [record])
        with self.assertRaisesRegex(CatalyticSwarm1V6ClosureError, "before lease release"):
            closure.enforce()
        closure.mark_lease_released()
        closure.enforce()
        with self.assertRaisesRegex(CatalyticSwarm1V6ClosureError, "more than once"):
            closure.persist(
                append_ledger=rows.append,
                sync_ledger=lambda: None,
                persist_result_fallback=lambda _record, _reason: None,
            )

    def test_ledger_failure_uses_one_fallback_with_bounded_error(self) -> None:
        closure = make_closure()
        fallbacks: list[tuple[dict[str, object], str]] = []

        class ProvenAbsentError(OSError):
            fallback_safe = True

        def fail(_record: dict[str, object]) -> None:
            raise ProvenAbsentError("sensitive machine path")

        with self.assertRaises(CompletedResponsePersistenceError):
            closure.persist(
                append_ledger=fail,
                sync_ledger=lambda: None,
                persist_result_fallback=lambda record, reason: fallbacks.append((record, reason)),
            )
        self.assertEqual(len(fallbacks), 1)
        record, reason = fallbacks[0]
        self.assertEqual(record["completion_persistence"], "result-fallback")
        self.assertTrue(reason.startswith("ProvenAbsentError:"))
        self.assertNotIn("sensitive", str(record) + reason)
        closure.mark_lease_released()
        closure.enforce()

    def test_indeterminate_ledger_durability_forbids_fallback(self) -> None:
        class IndeterminateError(OSError):
            fallback_safe = False

        closure = make_closure()
        fallbacks: list[dict[str, object]] = []
        with self.assertRaisesRegex(
            CompletedResponsePersistenceError, "indeterminate"
        ):
            closure.persist(
                append_ledger=lambda _record: (_ for _ in ()).throw(
                    IndeterminateError("unknown commit state")
                ),
                sync_ledger=lambda: None,
                persist_result_fallback=lambda record, _reason: fallbacks.append(record),
            )
        self.assertEqual(fallbacks, [])
        self.assertFalse(closure.persisted)


class TerminalReconciliationTests(unittest.TestCase):
    def make_records(self, count: int = 2):
        closures = [make_closure(sequence=index) for index in range(1, count + 1)]
        records = [persist_ledger(closure) for closure in closures]
        return closures, records

    def test_normal_terminal_equations(self) -> None:
        _closures, records = self.make_records()
        result = reconcile_terminal(
            completed_response_count=2,
            groups=records,
            ledger_records=records,
            fallback_records=[],
            lease_acquired_count=2,
            lease_released_count=2,
        )
        self.assertTrue(result["normal_completion"])
        self.assertEqual(result["attempts"], {name: 2 for name in BOUNDARY_ORDER})
        self.assertEqual(result["observations_completed"], {name: 2 for name in BOUNDARY_ORDER})
        self.assertEqual(result["passes"], {name: 2 for name in BOUNDARY_ORDER})

    def test_interrupted_terminal_uses_attempt_plus_blocked_equation(self) -> None:
        observers = pass_observers()
        observers["stable_custody"] = lambda: (_ for _ in ()).throw(SystemExit(9))
        closure = make_closure(observers=observers)
        record = persist_ledger(closure)
        result = reconcile_terminal(
            completed_response_count=1,
            groups=[record],
            ledger_records=[record],
            fallback_records=[],
            lease_acquired_count=1,
            lease_released_count=1,
        )
        self.assertFalse(result["normal_completion"])
        self.assertEqual(result["attempts"]["candidate_custody"], 0)
        self.assertEqual(result["blocked"]["candidate_custody"], 1)

    def test_last_boundary_interruption_is_not_normal_completion(self) -> None:
        observers = pass_observers()
        observers["host_memory"] = lambda: (_ for _ in ()).throw(KeyboardInterrupt())
        closure = make_closure(observers=observers)
        record = persist_ledger(closure)
        result = reconcile_terminal(
            completed_response_count=1,
            groups=[record],
            ledger_records=[record],
            fallback_records=[],
            lease_acquired_count=1,
            lease_released_count=1,
        )
        self.assertFalse(result["normal_completion"])
        self.assertEqual(result["interrupted"]["host_memory"], 1)

    def test_completion_identity_and_runtime_counter_drift_are_rejected(self) -> None:
        _closures, records = self.make_records(1)
        tampered = copy.deepcopy(records[0])
        tampered["completion_id"] = "0" * 64
        with self.assertRaisesRegex(TerminalReconciliationError, "does not recompute"):
            reconcile_terminal(
                completed_response_count=1,
                groups=[tampered],
                ledger_records=[tampered],
                fallback_records=[],
                lease_acquired_count=1,
                lease_released_count=1,
            )
        counters = {
            "post_request_groups_started": 1,
            "post_request_attempts": {name: 1 for name in BOUNDARY_ORDER},
            "post_request_observations_completed": {name: 1 for name in BOUNDARY_ORDER},
            "post_request_passes": {name: 1 for name in BOUNDARY_ORDER},
            "post_request_blocked": {name: 0 for name in BOUNDARY_ORDER},
        }
        counters["post_request_attempts"]["host_memory"] = 0
        with self.assertRaisesRegex(TerminalReconciliationError, "runtime counter"):
            reconcile_terminal(
                completed_response_count=1,
                groups=records,
                ledger_records=records,
                fallback_records=[],
                lease_acquired_count=1,
                lease_released_count=1,
                runtime_counters=counters,
            )

    def test_duplicate_or_overlapping_persistence_is_rejected(self) -> None:
        _closures, records = self.make_records(1)
        duplicate = copy.deepcopy(records[0])
        duplicate["completion_persistence"] = "result-fallback"
        with self.assertRaisesRegex(TerminalReconciliationError, "ledger plus fallback|duplicate"):
            reconcile_terminal(
                completed_response_count=1,
                groups=records,
                ledger_records=records,
                fallback_records=[duplicate],
                lease_acquired_count=1,
                lease_released_count=1,
            )

    def test_duplicate_group_is_rejected(self) -> None:
        _closures, records = self.make_records(1)
        with self.assertRaises(TerminalReconciliationError):
            reconcile_terminal(
                completed_response_count=2,
                groups=[records[0], copy.deepcopy(records[0])],
                ledger_records=[records[0]],
                fallback_records=[],
                lease_acquired_count=2,
                lease_released_count=2,
            )

    def test_invalid_order_pass_without_observation_and_lease_mismatch_are_rejected(self) -> None:
        _closures, records = self.make_records(1)
        bad_order = copy.deepcopy(records[0])
        entries = bad_order["post_request_boundary"]["sub_boundaries"]
        entries[0], entries[1] = entries[1], entries[0]
        invalid_pass = copy.deepcopy(records[0])
        invalid_pass["post_request_boundary"]["sub_boundaries"][0]["observation_completed"] = False
        cases = [
            ([bad_order], 1, 1),
            ([invalid_pass], 1, 1),
            (records, 1, 0),
        ]
        for groups, acquired, released in cases:
            with self.subTest(groups=groups, released=released):
                with self.assertRaises(TerminalReconciliationError):
                    reconcile_terminal(
                        completed_response_count=1,
                        groups=groups,
                        ledger_records=records,
                        fallback_records=[],
                        lease_acquired_count=acquired,
                        lease_released_count=released,
                    )


if __name__ == "__main__":
    unittest.main()
