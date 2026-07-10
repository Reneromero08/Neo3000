#!/usr/bin/env python3
"""CPU-only safety tests for neo_trace_diagnostic.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from neo_loop import CandidateVramSampler, ProcessVramSample
from neo_trace_diagnostic import (
    PhaseRecorder,
    cleanup_candidate,
    readiness_state,
    stable_integrity,
    wait_for_readiness,
)


class FakeProcess:
    def __init__(self, pid: int = 42, exit_code=None):
        self.pid = pid
        self.exit_code = exit_code

    def poll(self):
        return self.exit_code


class FakeSampler:
    def __init__(self, valid=False, failure=None):
        self.valid = valid
        self.failure = failure

    def has_valid_sample(self):
        return self.valid

    def failure_reason(self):
        return self.failure


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, amount):
        self.value += amount


class TraceDiagnosticTests(unittest.TestCase):
    def test_delayed_first_valid_sample_is_accepted(self):
        clock = FakeClock()
        sampler = FakeSampler()
        calls = 0

        def sleep(amount):
            nonlocal calls
            calls += 1
            clock.advance(amount)
            if calls == 3:
                sampler.valid = True

        state = wait_for_readiness(FakeProcess(), sampler, 9393, 2, lambda _: True,
                                   lambda _: {42}, clock, sleep, 0.25)
        self.assertTrue(state.ready)
        self.assertEqual(calls, 3)

    def test_pre_attribution_misses_are_retained(self):
        samples = iter([
            ProcessVramSample(False, None, [], "miss-one"),
            ProcessVramSample(False, None, [], "miss-two"),
            ProcessVramSample(True, 1, ["pid_42_luid_0"]),
        ])
        sampler = CandidateVramSampler(42, 6000, 1, 60, lambda _: next(samples))
        sampler.sample_once(); sampler.sample_once(); sampler.sample_once()
        self.assertEqual(sampler.failures, ["miss-one", "miss-two"])
        self.assertTrue(sampler.has_valid_sample())

    def test_grace_expiry_rejects(self):
        with self.assertRaisesRegex(Exception, "telemetry-unavailable"):
            wait_for_readiness(FakeProcess(), FakeSampler(failure="candidate-vram-telemetry-unavailable"),
                               9393, 2, lambda _: True, lambda _: {42})

    def test_listener_mismatch_and_multiple_listeners_reject_readiness(self):
        for listeners in ({41}, {42, 43}):
            state = readiness_state(FakeProcess(), 9393, 42, FakeSampler(True),
                                    lambda _: True, lambda _: listeners)
            self.assertFalse(state.listener_matches)
            self.assertFalse(state.ready)

    def test_process_exit_rejects(self):
        with self.assertRaisesRegex(Exception, "process-exited"):
            wait_for_readiness(FakeProcess(exit_code=9), FakeSampler(True), 9393, 2,
                               lambda _: True, lambda _: {42})

    def test_telemetry_loss_after_attribution_rejects(self):
        samples = iter([ProcessVramSample(True, 1, ["pid_42_luid_0"]),
                        ProcessVramSample(False, None, [], "lost")])
        sampler = CandidateVramSampler(42, 6000, 1, 60, lambda _: next(samples))
        sampler.sample_once(); sampler.sample_once()
        self.assertEqual(sampler.failure_reason(), "candidate-vram-telemetry-lost")

    def test_memory_over_6000_mib_rejects(self):
        sampler = CandidateVramSampler(42, 6000, 1, 60,
                                       lambda _: ProcessVramSample(True, 6001 * 1024 * 1024, ["pid_42_luid_0"]))
        sampler.sample_once()
        state = readiness_state(FakeProcess(), 9393, 42, sampler, lambda _: True, lambda _: {42})
        self.assertEqual(sampler.failure_reason(), "candidate-memory-ceiling")
        self.assertFalse(state.ready)

    def test_readiness_requires_full_conjunction(self):
        cases = [
            (FakeProcess(exit_code=1), FakeSampler(True), True, {42}),
            (FakeProcess(), FakeSampler(True), False, {42}),
            (FakeProcess(), FakeSampler(True), True, {41}),
            (FakeProcess(), FakeSampler(False), True, {42}),
        ]
        for process, sampler, health, listeners in cases:
            self.assertFalse(readiness_state(process, 9393, 42, sampler,
                                             lambda _, h=health: h, lambda _, p=listeners: p).ready)
        self.assertTrue(readiness_state(FakeProcess(), 9393, 42, FakeSampler(True),
                                        lambda _: True, lambda _: {42}).ready)

    def test_cleanup_stops_only_launched_process(self):
        process = FakeProcess(77)
        stop = Mock(return_value={"candidate_process_stopped": True, "pid": 77})
        with tempfile.TemporaryDirectory() as parent:
            runtime = Path(parent) / "runtime"
            runtime.mkdir()
            result = cleanup_candidate(process, runtime, stop)
        stop.assert_called_once_with(process)
        self.assertEqual(result["launched_pid"], 77)

    def test_stable_mismatch_after_teardown_rejects(self):
        ok, evidence = stable_integrity(9292, {100}, lambda _: True, lambda _: {101})
        self.assertFalse(ok)
        self.assertEqual(evidence["listener_pids"], [101])

    def test_phase_windows_are_monotonic_and_nonoverlapping(self):
        clock = FakeClock()
        recorder = PhaseRecorder(clock)
        first = recorder.start("startup")
        clock.advance(1)
        recorder.end(first)
        clock.advance(0.5)
        second = recorder.start("cold_reasoning")
        clock.advance(2)
        recorder.end(second)
        self.assertLessEqual(first.end_monotonic, second.start_monotonic)
        with self.assertRaisesRegex(Exception, "still open"):
            recorder.start("warm_transport")
            recorder.start("warm_reasoning")


if __name__ == "__main__":
    unittest.main()
