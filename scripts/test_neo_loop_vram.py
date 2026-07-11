#!/usr/bin/env python3
"""Narrow unit tests for PID-filtered WDDM candidate VRAM accounting."""

from __future__ import annotations

import importlib.util
import sys
import threading
import time
import unittest
from unittest import mock


spec = importlib.util.spec_from_file_location("neo_loop_under_test", "scripts/neo_loop.py")
neo_loop = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = neo_loop
assert spec.loader is not None
spec.loader.exec_module(neo_loop)


def row(pid: int, value: object, status: int = 0, suffix: str = "phys_0") -> dict[str, object]:
    return {"instance": f"pid_{pid}_luid_0x0_0x1_{suffix}", "value": value, "status": status}


class WddmPidMemoryTests(unittest.TestCase):
    @staticmethod
    def resilient_sampler(samples: list[object]) -> object:
        values = iter(samples)
        with mock.patch.object(neo_loop.time, "monotonic", return_value=0.0):
            return neo_loop.CandidateVramSampler(
                22,
                6000,
                1,
                60,
                lambda _: next(values),
                wddm_policy=neo_loop.WddmTelemetryPolicy(
                    initial_grace_seconds=60,
                    max_consecutive_failures=2,
                    max_valid_sample_gap_seconds=30,
                    admission_freshness_seconds=5,
                ),
            )

    @staticmethod
    def sample_at(sampler: object, now: float) -> None:
        with mock.patch.object(neo_loop.time, "monotonic", return_value=now):
            sampler.sample_once()

    @staticmethod
    def failure_at(sampler: object, now: float) -> str | None:
        with mock.patch.object(neo_loop.time, "monotonic", return_value=now):
            return sampler.failure_reason()

    @staticmethod
    def fresh_at(sampler: object, now: float) -> bool:
        with mock.patch.object(neo_loop.time, "monotonic", return_value=now):
            return sampler.has_fresh_valid_sample()

    @staticmethod
    def snapshot_at(sampler: object, now: float) -> dict[str, object]:
        with mock.patch.object(neo_loop.time, "monotonic", return_value=now):
            return sampler.telemetry_snapshot()

    def test_sums_multiple_candidate_instances_and_excludes_stable(self) -> None:
        sample = neo_loop.select_wddm_pid_memory([row(22, 100), row(22, 200, suffix="phys_1"), row(11, 999)], 22)
        self.assertTrue(sample.available)
        self.assertEqual(sample.bytes, 300)
        self.assertEqual(len(sample.instances), 2)
        self.assertNotIn("pid_11_", " ".join(sample.instances))

    def test_rejects_nonnumeric_and_counter_errors(self) -> None:
        self.assertFalse(neo_loop.select_wddm_pid_memory([row(22, "[N/A]")], 22).available)
        self.assertFalse(neo_loop.select_wddm_pid_memory([row(22, 1, status=1)], 22).available)

    def test_rejects_missing_pid_after_grace(self) -> None:
        sampler = neo_loop.CandidateVramSampler(22, 6000, 1, 0, lambda _: neo_loop.ProcessVramSample(False, None, [], "no-matching-pid-instance"))
        sampler.sample_once()
        self.assertEqual(sampler.failure_reason(), "candidate-vram-telemetry-unavailable")

    def test_enforces_ceiling_and_accepts_below_it(self) -> None:
        below = neo_loop.CandidateVramSampler(22, 6000, 1, 60, lambda _: neo_loop.ProcessVramSample(True, 5999 * 1024 * 1024, ["pid_22_luid_0x0_0x1_phys_0"]))
        below.sample_once()
        self.assertIsNone(below.failure_reason())
        above = neo_loop.CandidateVramSampler(22, 6000, 1, 60, lambda _: neo_loop.ProcessVramSample(True, 6001 * 1024 * 1024, ["pid_22_luid_0x0_0x1_phys_0"]))
        above.sample_once()
        self.assertEqual(above.failure_reason(), "candidate-memory-ceiling")

    def test_legacy_mode_still_rejects_first_disappearance_after_valid_sample(self) -> None:
        values = iter([
            neo_loop.ProcessVramSample(True, 100, ["pid_22_luid_0x0_0x1_phys_0"]),
            neo_loop.ProcessVramSample(False, None, [], "no-matching-pid-instance"),
        ])
        sampler = neo_loop.CandidateVramSampler(22, 6000, 1, 60, lambda _: next(values))
        sampler.sample_once()
        sampler.sample_once()
        self.assertEqual(sampler.failure_reason(), "candidate-vram-telemetry-lost")

    def test_resilient_one_unavailable_query_is_transient(self) -> None:
        sampler = self.resilient_sampler([
            neo_loop.ProcessVramSample(True, 100, ["pid_22_luid_0x0_0x1_phys_0"]),
            neo_loop.ProcessVramSample(False, None, [], "timeout-1"),
        ])
        self.sample_at(sampler, 1.0)
        self.sample_at(sampler, 2.0)
        self.assertIsNone(self.failure_at(sampler, 2.0))
        self.assertFalse(self.fresh_at(sampler, 2.0))
        snapshot = self.snapshot_at(sampler, 2.0)
        self.assertEqual(snapshot["consecutive_failures"], 1)
        self.assertTrue(snapshot["transient_gap_active"])

    def test_resilient_two_unavailable_queries_remain_transient(self) -> None:
        sampler = self.resilient_sampler([
            neo_loop.ProcessVramSample(True, 100, ["pid_22_luid_0x0_0x1_phys_0"]),
            neo_loop.ProcessVramSample(False, None, [], "timeout-1"),
            neo_loop.ProcessVramSample(False, None, [], "timeout-2"),
        ])
        self.sample_at(sampler, 1.0)
        self.sample_at(sampler, 2.0)
        self.sample_at(sampler, 3.0)
        self.assertIsNone(self.failure_at(sampler, 3.0))
        snapshot = self.snapshot_at(sampler, 3.0)
        self.assertEqual(snapshot["consecutive_failures"], 2)
        self.assertEqual(snapshot["maximum_consecutive_failures"], 2)
        self.assertEqual(snapshot["total_failures"], 2)

    def test_resilient_third_unavailable_query_fails_closed(self) -> None:
        sampler = self.resilient_sampler([
            neo_loop.ProcessVramSample(True, 100, ["pid_22_luid_0x0_0x1_phys_0"]),
            neo_loop.ProcessVramSample(False, None, [], "timeout-1"),
            neo_loop.ProcessVramSample(False, None, [], "timeout-2"),
            neo_loop.ProcessVramSample(False, None, [], "timeout-3"),
        ])
        for observed_at in (1.0, 2.0, 3.0, 4.0):
            self.sample_at(sampler, observed_at)
        self.assertEqual(
            self.failure_at(sampler, 4.0),
            "candidate-vram-telemetry-lost",
        )

    def test_resilient_valid_recovery_resets_streak_and_records_gap(self) -> None:
        sampler = self.resilient_sampler([
            neo_loop.ProcessVramSample(True, 100, ["pid_22_luid_0x0_0x1_phys_0"]),
            neo_loop.ProcessVramSample(False, None, [], "timeout-1"),
            neo_loop.ProcessVramSample(False, None, [], "timeout-2"),
            neo_loop.ProcessVramSample(True, 200, ["pid_22_luid_0x0_0x1_phys_0"]),
        ])
        for observed_at in (1.0, 2.0, 3.0, 4.0):
            self.sample_at(sampler, observed_at)
        self.assertTrue(self.fresh_at(sampler, 4.0))
        snapshot = self.snapshot_at(sampler, 4.0)
        self.assertEqual(snapshot["consecutive_failures"], 0)
        self.assertEqual(snapshot["maximum_consecutive_failures"], 2)
        self.assertEqual(snapshot["recovered_gap_count"], 1)
        self.assertEqual(snapshot["maximum_valid_sample_gap_seconds"], 3.0)
        self.assertEqual(snapshot["peak_bytes"], 200)

    def test_resilient_stale_sample_cannot_admit_readiness(self) -> None:
        sampler = self.resilient_sampler([
            neo_loop.ProcessVramSample(True, 100, ["pid_22_luid_0x0_0x1_phys_0"]),
        ])
        self.sample_at(sampler, 1.0)
        self.assertTrue(sampler.has_valid_sample())
        self.assertFalse(self.fresh_at(sampler, 6.1))
        self.assertIsNone(self.failure_at(sampler, 6.1))

    def test_resilient_valid_sample_gap_over_thirty_seconds_fails_closed(self) -> None:
        sampler = self.resilient_sampler([
            neo_loop.ProcessVramSample(True, 100, ["pid_22_luid_0x0_0x1_phys_0"]),
        ])
        self.sample_at(sampler, 1.0)
        self.assertEqual(
            self.failure_at(sampler, 31.1),
            "candidate-vram-telemetry-lost",
        )

    def test_resilient_ceiling_violation_is_immediate(self) -> None:
        sampler = self.resilient_sampler([
            neo_loop.ProcessVramSample(
                True,
                6001 * 1024 * 1024,
                ["pid_22_luid_0x0_0x1_phys_0"],
            ),
        ])
        self.sample_at(sampler, 1.0)
        self.assertEqual(self.failure_at(sampler, 1.0), "candidate-memory-ceiling")

    def test_resilient_snapshot_contains_complete_transition_ledger(self) -> None:
        sampler = self.resilient_sampler([
            neo_loop.ProcessVramSample(True, 100, ["pid_22_luid_0x0_0x1_phys_0"]),
            neo_loop.ProcessVramSample(False, None, [], "timeout-1"),
            neo_loop.ProcessVramSample(True, 200, ["pid_22_luid_0x0_0x1_phys_0"]),
        ])
        for observed_at in (1.0, 2.0, 3.0):
            self.sample_at(sampler, observed_at)
        snapshot = self.snapshot_at(sampler, 3.0)
        self.assertEqual(snapshot["transition_event_count"], 3)
        self.assertEqual(
            [event["kind"] for event in snapshot["transition_events"]],
            ["gap-start", "unavailable", "recovery"],
        )
        self.assertEqual(snapshot["unavailable_event_count"], 1)
        self.assertEqual(snapshot["recovery_event_count"], 1)
        self.assertEqual(len(snapshot["transition_ledger_sha256"]), 64)
        self.assertFalse(snapshot["sampler_stop_attempted"])
        with mock.patch.object(neo_loop.time, "monotonic", return_value=3.0):
            evidence_snapshot = sampler.evidence(6000)["telemetry_snapshot"]
        self.assertEqual(evidence_snapshot["mode"], "resilient")
        self.assertEqual(evidence_snapshot["transition_events"], snapshot["transition_events"])
        self.assertIn("policy", evidence_snapshot)
        self.assertIn("sampler_thread_alive", evidence_snapshot)

    def test_stop_waits_through_query_timeout_and_fails_closed_if_thread_lives(self) -> None:
        entered = threading.Event()
        release = threading.Event()

        def blocking_sample(_: int) -> object:
            entered.set()
            release.wait(timeout=2.0)
            return neo_loop.ProcessVramSample(
                True,
                100,
                ["pid_22_luid_0x0_0x1_phys_0"],
            )

        sampler = neo_loop.CandidateVramSampler(
            22,
            6000,
            1,
            60,
            blocking_sample,
            wddm_policy=neo_loop.WddmTelemetryPolicy(),
        )
        sampler.start()
        self.assertTrue(entered.wait(timeout=1.0))
        try:
            with (
                mock.patch.object(neo_loop, "WDDM_QUERY_TIMEOUT_SECONDS", 0.04),
                mock.patch.object(neo_loop, "WDDM_SAMPLER_STOP_MARGIN_SECONDS", 0.02),
            ):
                started = time.monotonic()
                stopped = sampler.stop()
                elapsed = time.monotonic() - started
                snapshot = sampler.telemetry_snapshot()
            self.assertFalse(stopped)
            self.assertGreaterEqual(elapsed, 0.05)
            self.assertEqual(
                sampler.failure_reason(),
                "candidate-vram-telemetry-sampler-stop-timeout",
            )
            self.assertTrue(snapshot["sampler_stop_attempted"])
            self.assertTrue(snapshot["sampler_stop_timed_out"])
            self.assertTrue(snapshot["sampler_thread_alive"])
            self.assertEqual(snapshot["sampler_stop_timeout_seconds"], 0.06)
            self.assertEqual(
                snapshot["sampler_stop_failure_reason"],
                "candidate-vram-telemetry-sampler-stop-timeout",
            )
            self.assertEqual(
                snapshot["transition_events"][-1]["kind"],
                "hard-failure",
            )
            self.assertEqual(
                snapshot["transition_events"][-1]["trigger_kind"],
                "sampler-stop",
            )
        finally:
            release.set()
            if sampler._thread is not None:
                sampler._thread.join(timeout=1.0)
                self.assertFalse(sampler._thread.is_alive())

    def test_default_stop_window_exceeds_get_counter_timeout(self) -> None:
        self.assertGreater(
            neo_loop.WDDM_QUERY_TIMEOUT_SECONDS
            + neo_loop.WDDM_SAMPLER_STOP_MARGIN_SECONDS,
            neo_loop.WDDM_QUERY_TIMEOUT_SECONDS,
        )

    def test_legacy_stop_and_evidence_surface_remain_unchanged(self) -> None:
        sampler = neo_loop.CandidateVramSampler(
            22,
            6000,
            3,
            60,
            lambda _: neo_loop.ProcessVramSample(False, None, [], "unused"),
        )
        thread = mock.Mock()
        sampler._thread = thread

        self.assertIsNone(sampler.stop())
        thread.join.assert_called_once_with(timeout=6)
        self.assertIsNone(sampler.failure_reason())
        snapshot = sampler.telemetry_snapshot()
        evidence = sampler.evidence(6000)
        self.assertNotIn("sampler_stop_attempted", snapshot)
        self.assertNotIn("sampler_stop_timed_out", snapshot)
        self.assertNotIn("sampler_thread_alive", snapshot)
        self.assertNotIn("sampler_stop_attempted", evidence)
        self.assertNotIn("sampler_stop_timed_out", evidence)
        self.assertNotIn("sampler_thread_alive", evidence)


if __name__ == "__main__":
    unittest.main()
