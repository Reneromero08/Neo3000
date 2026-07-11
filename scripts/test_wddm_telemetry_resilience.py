#!/usr/bin/env python3
"""CPU-only tests for bounded exact-PID WDDM telemetry resilience."""

from __future__ import annotations

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
        self.assertEqual(snapshot.failure_reason, "candidate-vram-telemetry-lost")


if __name__ == "__main__":
    unittest.main()
