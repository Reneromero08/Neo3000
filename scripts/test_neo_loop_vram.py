#!/usr/bin/env python3
"""Narrow unit tests for PID-filtered WDDM candidate VRAM accounting."""

from __future__ import annotations

import importlib.util
import sys
import unittest


spec = importlib.util.spec_from_file_location("neo_loop_under_test", "scripts/neo_loop.py")
neo_loop = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = neo_loop
assert spec.loader is not None
spec.loader.exec_module(neo_loop)


def row(pid: int, value: object, status: int = 0, suffix: str = "phys_0") -> dict[str, object]:
    return {"instance": f"pid_{pid}_luid_0x0_0x1_{suffix}", "value": value, "status": status}


class WddmPidMemoryTests(unittest.TestCase):
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

    def test_rejects_counter_disappearance_after_valid_sample(self) -> None:
        values = iter([
            neo_loop.ProcessVramSample(True, 100, ["pid_22_luid_0x0_0x1_phys_0"]),
            neo_loop.ProcessVramSample(False, None, [], "no-matching-pid-instance"),
        ])
        sampler = neo_loop.CandidateVramSampler(22, 6000, 1, 60, lambda _: next(values))
        sampler.sample_once()
        sampler.sample_once()
        self.assertEqual(sampler.failure_reason(), "candidate-vram-telemetry-lost")


if __name__ == "__main__":
    unittest.main()
