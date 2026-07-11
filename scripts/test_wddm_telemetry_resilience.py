#!/usr/bin/env python3
"""CPU-only tests for bounded exact-PID WDDM telemetry resilience."""

from __future__ import annotations

import hashlib
import json
import unittest
from types import SimpleNamespace

from wddm_telemetry_resilience import (
    ResilientWddmTelemetry,
    WddmTelemetryPolicy,
)


MIB = 1024 * 1024
INSTANCE = "pid_44748_luid_0x0_0x1_phys_0"


class WddmTelemetryResilienceTests(unittest.TestCase):
    def tracker(
        self,
        *,
        started_at: float = 0.0,
        max_failures: int = 2,
        max_gap: float = 30.0,
        freshness: float = 5.0,
        grace: float = 60.0,
        transition_event_limit: int = 512,
    ) -> ResilientWddmTelemetry:
        return ResilientWddmTelemetry(
            ceiling_bytes=6000 * MIB,
            started_at=started_at,
            policy=WddmTelemetryPolicy(
                initial_grace_seconds=grace,
                max_consecutive_failures=max_failures,
                max_valid_sample_gap_seconds=max_gap,
                admission_freshness_seconds=freshness,
            ),
            transition_event_limit=transition_event_limit,
        )

    def test_initial_unavailable_remains_inside_grace(self) -> None:
        tracker = self.tracker()
        tracker.observe_unavailable("no-matching-pid-instance", now=10.0)
        self.assertIsNone(tracker.failure_reason(now=10.0))
        self.assertFalse(tracker.has_fresh_valid_sample(now=10.0))

    def test_initial_grace_expiry_fails_closed(self) -> None:
        tracker = self.tracker(grace=60.0)
        tracker.observe_unavailable("counter-timeout", now=61.0)
        self.assertEqual(
            tracker.failure_reason(now=61.0),
            "candidate-vram-telemetry-unavailable",
        )

    def test_initial_unavailable_samples_do_not_pollute_post_valid_gap_state(self) -> None:
        tracker = self.tracker()
        for observed_at in range(1, 6):
            tracker.observe_unavailable(
                f"no-matching-pid-instance-{observed_at}",
                now=float(observed_at),
            )
        tracker.observe_valid(
            bytes_used=100 * MIB,
            instances=[INSTANCE],
            now=6.0,
        )

        snapshot = tracker.snapshot(now=6.0)
        self.assertEqual(snapshot.total_failures, 5)
        self.assertEqual(snapshot.consecutive_failures, 0)
        self.assertEqual(snapshot.maximum_consecutive_failures, 0)
        self.assertEqual(snapshot.recovered_gap_count, 0)
        self.assertEqual(snapshot.gap_start_event_count, 0)
        self.assertEqual(snapshot.unavailable_event_count, 5)
        self.assertEqual(snapshot.recovery_event_count, 0)
        self.assertEqual(
            [event.kind for event in snapshot.transition_events],
            ["unavailable"] * 5,
        )
        self.assertTrue(snapshot.admission_ready)

    def test_valid_sample_is_admission_ready_when_fresh(self) -> None:
        tracker = self.tracker()
        tracker.observe_valid(bytes_used=100 * MIB, instances=[INSTANCE], now=2.0)
        self.assertIsNone(tracker.failure_reason(now=3.0))
        self.assertTrue(tracker.has_fresh_valid_sample(now=3.0))

    def test_one_timeout_after_valid_sample_is_transient(self) -> None:
        tracker = self.tracker()
        tracker.observe_valid(bytes_used=100 * MIB, instances=[INSTANCE], now=2.0)
        tracker.observe_unavailable("counter-query-failed: timeout", now=12.0)
        self.assertIsNone(tracker.failure_reason(now=12.0))
        self.assertFalse(tracker.has_fresh_valid_sample(now=12.0))
        snapshot = tracker.snapshot(now=12.0)
        self.assertTrue(snapshot.transient_gap_active)
        self.assertEqual(snapshot.consecutive_failures, 1)

    def test_valid_recovery_resets_failure_streak_and_restores_admission(self) -> None:
        tracker = self.tracker()
        tracker.observe_valid(bytes_used=100 * MIB, instances=[INSTANCE], now=2.0)
        tracker.observe_unavailable("counter-timeout", now=12.0)
        tracker.observe_valid(bytes_used=110 * MIB, instances=[INSTANCE], now=13.0)
        snapshot = tracker.snapshot(now=13.0)
        self.assertIsNone(snapshot.failure_reason)
        self.assertTrue(snapshot.admission_ready)
        self.assertEqual(snapshot.consecutive_failures, 0)
        self.assertEqual(snapshot.recovered_gap_count, 1)
        self.assertEqual(snapshot.peak_bytes, 110 * MIB)
        self.assertEqual(snapshot.maximum_valid_sample_gap_seconds, 11.0)

    def test_failure_streak_exceeding_bound_fails_closed(self) -> None:
        tracker = self.tracker(max_failures=2, max_gap=60.0)
        tracker.observe_valid(bytes_used=100 * MIB, instances=[INSTANCE], now=1.0)
        tracker.observe_unavailable("timeout-1", now=10.0)
        tracker.observe_unavailable("timeout-2", now=20.0)
        self.assertIsNone(tracker.failure_reason(now=20.0))
        tracker.observe_unavailable("timeout-3", now=30.0)
        self.assertEqual(
            tracker.failure_reason(now=30.0),
            "candidate-vram-telemetry-lost",
        )

    def test_valid_sample_gap_expiry_fails_even_before_failure_count_bound(self) -> None:
        tracker = self.tracker(max_failures=10, max_gap=30.0)
        tracker.observe_valid(bytes_used=100 * MIB, instances=[INSTANCE], now=1.0)
        tracker.observe_unavailable("counter-timeout", now=32.1)
        self.assertEqual(
            tracker.failure_reason(now=32.1),
            "candidate-vram-telemetry-lost",
        )

    def test_stale_valid_sample_never_satisfies_admission(self) -> None:
        tracker = self.tracker(freshness=5.0, max_gap=30.0)
        tracker.observe_valid(bytes_used=100 * MIB, instances=[INSTANCE], now=1.0)
        self.assertFalse(tracker.has_fresh_valid_sample(now=7.0))
        self.assertIsNone(tracker.failure_reason(now=7.0))

    def test_memory_ceiling_is_immediate_and_permanent(self) -> None:
        tracker = self.tracker()
        tracker.observe_valid(bytes_used=6001 * MIB, instances=[INSTANCE], now=1.0)
        self.assertEqual(tracker.failure_reason(now=1.0), "candidate-memory-ceiling")
        tracker.observe_valid(bytes_used=100 * MIB, instances=[INSTANCE], now=2.0)
        self.assertEqual(tracker.failure_reason(now=2.0), "candidate-memory-ceiling")

    def test_process_vram_sample_shape_is_supported(self) -> None:
        tracker = self.tracker()
        sample = SimpleNamespace(
            available=True,
            bytes=250 * MIB,
            instances=[INSTANCE],
            error=None,
        )
        tracker.observe_sample(sample, now=1.0)
        self.assertEqual(tracker.snapshot(now=1.0).sample_count, 1)

    def test_unavailable_sample_shape_is_recorded(self) -> None:
        tracker = self.tracker()
        sample = SimpleNamespace(
            available=False,
            bytes=None,
            instances=[],
            error="counter-query-failed: timeout",
        )
        tracker.observe_sample(sample, now=1.0)
        snapshot = tracker.snapshot(now=1.0)
        self.assertEqual(snapshot.total_failures, 1)
        self.assertIn("counter-query-failed: timeout", snapshot.recent_failures)

    def test_exact_instance_is_required_for_valid_sample(self) -> None:
        tracker = self.tracker()
        with self.assertRaises(ValueError):
            tracker.observe_valid(bytes_used=100, instances=[], now=1.0)

    def test_policy_rejects_unsafe_or_incoherent_values(self) -> None:
        with self.assertRaises(ValueError):
            WddmTelemetryPolicy(max_consecutive_failures=-1).validate()
        with self.assertRaises(ValueError):
            WddmTelemetryPolicy(max_valid_sample_gap_seconds=0).validate()
        with self.assertRaises(ValueError):
            WddmTelemetryPolicy(
                max_valid_sample_gap_seconds=5,
                admission_freshness_seconds=6,
            ).validate()

    def test_snapshot_is_bounded_and_auditable(self) -> None:
        tracker = self.tracker()
        tracker.observe_valid(bytes_used=100 * MIB, instances=[INSTANCE], now=1.0)
        for index in range(20):
            tracker.observe_unavailable(f"failure-{index}", now=2.0 + index)
        snapshot = tracker.snapshot(now=21.0)
        self.assertLessEqual(len(snapshot.recent_failures), 16)
        self.assertEqual(snapshot.maximum_consecutive_failures, 20)
        self.assertEqual(snapshot.total_failures, 20)
        self.assertEqual(snapshot.maximum_valid_sample_gap_seconds, 20.0)
        self.assertEqual(snapshot.failure_reason, "candidate-vram-telemetry-lost")

    def test_transition_ledger_records_every_gap_unavailable_recovery_and_hard_fail(self) -> None:
        tracker = self.tracker(max_failures=5, max_gap=60.0)
        tracker.observe_valid(bytes_used=100 * MIB, instances=[INSTANCE], now=1.0)
        tracker.observe_unavailable("timeout-a", now=2.0)
        tracker.observe_unavailable("timeout-b", now=3.0)
        tracker.observe_valid(bytes_used=110 * MIB, instances=[INSTANCE], now=4.0)
        tracker.observe_unavailable("timeout-c", now=5.0)
        tracker.observe_valid(bytes_used=120 * MIB, instances=[INSTANCE], now=6.0)
        tracker.observe_valid(bytes_used=6001 * MIB, instances=[INSTANCE], now=7.0)

        snapshot = tracker.snapshot(now=7.0)
        self.assertEqual(
            [event.kind for event in snapshot.transition_events],
            [
                "gap-start",
                "unavailable",
                "unavailable",
                "recovery",
                "gap-start",
                "unavailable",
                "recovery",
                "hard-failure",
            ],
        )
        self.assertEqual(
            [event.sequence for event in snapshot.transition_events],
            list(range(1, 9)),
        )
        self.assertEqual(snapshot.transition_event_count, 8)
        self.assertEqual(snapshot.transition_event_attempt_count, 8)
        self.assertEqual(snapshot.transition_events_omitted, 0)
        self.assertFalse(snapshot.transition_overflowed)
        self.assertEqual(snapshot.gap_start_event_count, 2)
        self.assertEqual(snapshot.unavailable_event_count, 3)
        self.assertEqual(snapshot.recovery_event_count, 2)
        self.assertEqual(snapshot.hard_failure_event_count, 1)
        self.assertEqual(snapshot.recovered_gap_count, 2)
        self.assertEqual(snapshot.failure_reason, "candidate-memory-ceiling")
        self.assertEqual(len(snapshot.transition_ledger_sha256), 64)

    def test_transition_reasons_are_bounded_but_hash_the_complete_value(self) -> None:
        tracker = self.tracker()
        tracker.observe_valid(bytes_used=100 * MIB, instances=[INSTANCE], now=1.0)
        full_reason = "x" * 500
        tracker.observe_unavailable(full_reason, now=2.0)
        snapshot = tracker.snapshot(now=2.0)
        unavailable = snapshot.transition_events[1]
        self.assertEqual(unavailable.kind, "unavailable")
        self.assertEqual(len(unavailable.reason or ""), 256)
        self.assertTrue(unavailable.reason_truncated)
        self.assertEqual(
            unavailable.reason_sha256,
            hashlib.sha256(full_reason.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(len(snapshot.recent_failures[0]), 256)

    def test_transition_ledger_overflow_fails_closed_with_final_sentinel(self) -> None:
        tracker = self.tracker(transition_event_limit=4)
        tracker.observe_valid(bytes_used=100 * MIB, instances=[INSTANCE], now=1.0)
        tracker.observe_unavailable("timeout-a", now=2.0)
        tracker.observe_valid(bytes_used=110 * MIB, instances=[INSTANCE], now=3.0)
        tracker.observe_unavailable("timeout-b", now=4.0)

        snapshot = tracker.snapshot(now=4.0)
        self.assertEqual(
            snapshot.failure_reason,
            "candidate-vram-telemetry-transition-overflow",
        )
        self.assertTrue(snapshot.transition_overflowed)
        self.assertEqual(snapshot.transition_event_count, 4)
        self.assertEqual(snapshot.transition_event_limit, 4)
        self.assertEqual(snapshot.transition_event_attempt_count, 5)
        self.assertEqual(snapshot.transition_events_omitted, 2)
        sentinel = snapshot.transition_events[-1]
        self.assertEqual(sentinel.kind, "hard-failure")
        self.assertEqual(sentinel.trigger_kind, "gap-start")
        self.assertIn("omitted-gap-start: timeout-b", sentinel.reason or "")

    def test_transition_event_limit_cannot_omit_overflow_sentinel_capacity(self) -> None:
        with self.assertRaises(ValueError):
            self.tracker(transition_event_limit=1)

    def test_default_transition_ledger_stays_below_one_mib_at_capacity(self) -> None:
        tracker = self.tracker(max_failures=1000, max_gap=1000.0)
        tracker.observe_valid(bytes_used=100 * MIB, instances=[INSTANCE], now=0.0)
        for index in range(200):
            now = 1.0 + index * 2.0
            tracker.observe_unavailable("x" * 500, now=now)
            if tracker.snapshot(now=now).transition_overflowed:
                break
            tracker.observe_valid(
                bytes_used=100 * MIB,
                instances=[INSTANCE],
                now=now + 1.0,
            )
        snapshot = tracker.snapshot(now=now)
        encoded = json.dumps(
            snapshot.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertTrue(snapshot.transition_overflowed)
        self.assertEqual(snapshot.transition_event_limit, 512)
        self.assertEqual(snapshot.transition_event_count, 512)
        self.assertLess(len(encoded), 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
