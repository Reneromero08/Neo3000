#!/usr/bin/env python3
from __future__ import annotations

import unittest

from catalytic_swarm_1_v5_completion_closure import (
    COMPARISON_GATE_ORDER,
    WARM_GATE_ORDER,
    CatalyticSwarm1V5ClosureError,
    CompletedResponseClosure,
    CompletedResponsePersistenceError,
    CompletedResponseRejected,
)


def gates(order: tuple[str, ...], failed: str | None = None) -> dict[str, bool]:
    return {name: name != failed for name in order}


class CompletionClosureTests(unittest.TestCase):
    def closure(self, kind: str = "warm") -> CompletedResponseClosure:
        value = CompletedResponseClosure("cs1-task-07:common-root-warm", 775, kind)
        value.mark_model_completed()
        return value

    def persist(self, value: CompletedResponseClosure) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        value.persist(append_ledger=lambda row: rows.append(row), sync_ledger=lambda: None, persist_result_fallback=lambda row, error: None)
        value.mark_lease_released()
        return rows

    def test_task_7_fixture_closes_each_warm_rejection_reason(self) -> None:
        for failed in WARM_GATE_ORDER:
            with self.subTest(failed=failed):
                value = self.closure()
                value.capture({"lease_id": 0}, gates(WARM_GATE_ORDER, failed))
                value.record_post_request_boundary(wddm_passed=True, custody_passed=True, host_memory_passed=True)
                rows = self.persist(value)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["response_disposition"], "rejected")
                with self.assertRaises(CompletedResponseRejected):
                    value.enforce()

    def test_completed_warm_accepts_only_after_sync_and_release(self) -> None:
        events: list[str] = []
        value = self.closure()
        value.capture({"lease_id": 0}, gates(WARM_GATE_ORDER))
        value.record_post_request_boundary(wddm_passed=True, custody_passed=True, host_memory_passed=True)
        value.persist(append_ledger=lambda row: events.append("append"), sync_ledger=lambda: events.append("sync"), persist_result_fallback=lambda row, error: events.append("fallback"))
        with self.assertRaisesRegex(CatalyticSwarm1V5ClosureError, "lease release"):
            value.enforce()
        value.mark_lease_released()
        value.enforce()
        self.assertEqual(events, ["append", "sync"])

    def test_comparison_rejections_obey_same_closure_law(self) -> None:
        for failed in ("candidate_parse_passed", "transport_accepted", "root_terminal_admitted"):
            with self.subTest(failed=failed):
                value = self.closure("comparison")
                value.capture({"lease_id": 0}, gates(COMPARISON_GATE_ORDER, failed))
                value.record_post_request_boundary(wddm_passed=True, custody_passed=True, host_memory_passed=True)
                rows = self.persist(value)
                self.assertEqual(len(rows), 1)
                with self.assertRaises(CompletedResponseRejected):
                    value.enforce()

    def test_post_request_failure_persists_before_stop(self) -> None:
        value = self.closure()
        value.capture({"lease_id": 0}, gates(WARM_GATE_ORDER))
        value.record_post_request_boundary(wddm_passed=False, custody_passed=True, host_memory_passed=True, reason_code="post-request-wddm-failed")
        rows = self.persist(value)
        self.assertFalse(rows[0]["post_request_boundary"]["passed"])
        with self.assertRaises(CompletedResponseRejected):
            value.enforce()

    def test_ledger_failure_uses_result_fallback_once(self) -> None:
        value = self.closure()
        value.capture({"lease_id": 0}, gates(WARM_GATE_ORDER))
        value.record_post_request_boundary(wddm_passed=True, custody_passed=True, host_memory_passed=True)
        fallback: list[dict[str, object]] = []
        with self.assertRaises(CompletedResponsePersistenceError):
            value.persist(append_ledger=lambda row: (_ for _ in ()).throw(OSError("disk")), sync_ledger=lambda: None, persist_result_fallback=lambda row, error: fallback.append({"row": row, "error": error}))
        self.assertEqual(len(fallback), 1)
        self.assertEqual(fallback[0]["row"]["completion_persistence"], "result-fallback")
        with self.assertRaisesRegex(CatalyticSwarm1V5ClosureError, "more than once"):
            value.persist(append_ledger=lambda row: None, sync_ledger=lambda: None, persist_result_fallback=lambda row, error: None)

    def test_precompletion_failure_claims_no_completed_observation(self) -> None:
        value = CompletedResponseClosure("request", 1, "warm")
        with self.assertRaisesRegex(CatalyticSwarm1V5ClosureError, "preceded model completion"):
            value.capture({}, gates(WARM_GATE_ORDER))
        self.assertFalse(value.model_completed)
        self.assertFalse(value.persisted)

    def test_completion_and_observation_are_exactly_once(self) -> None:
        value = self.closure()
        with self.assertRaisesRegex(CatalyticSwarm1V5ClosureError, "more than once"):
            value.mark_model_completed()
        value.capture({}, gates(WARM_GATE_ORDER))
        with self.assertRaisesRegex(CatalyticSwarm1V5ClosureError, "more than once"):
            value.capture({}, gates(WARM_GATE_ORDER))

    def test_keyboard_and_process_style_interruptions_can_be_classified(self) -> None:
        for reason in ("post-response-keyboard-interruption", "post-response-process-interruption", "post-response-cleanup-interruption"):
            with self.subTest(reason=reason):
                value = self.closure()
                value.capture_instrumentation_failure({"lease_id": 0}, reason_code=reason)
                value.record_post_request_boundary(wddm_passed=True, custody_passed=True, host_memory_passed=True)
                rows = self.persist(value)
                self.assertEqual(rows[0]["response_reason_code"], reason)


if __name__ == "__main__":
    unittest.main()
