#!/usr/bin/env python3
"""CPU-only tests for the checked HoloState listener probe."""

from __future__ import annotations

import subprocess
import unittest
from collections import deque
from types import SimpleNamespace
from unittest import mock

import listener_probe as probe


class NetstatParserTests(unittest.TestCase):
    def test_ipv4_and_ipv6_exact_listener_rows(self) -> None:
        output = """
          TCP    0.0.0.0:9292          0.0.0.0:0              LISTENING       32684
          TCP    [::]:9292             [::]:0                 LISTENING       32684
          TCP    127.0.0.1:9494        0.0.0.0:0              LISTENING       37804
        """
        self.assertEqual(probe.parse_netstat_listener_pids(output, 9292), {32684})
        self.assertEqual(probe.parse_netstat_listener_pids(output, 9494), {37804})

    def test_non_listening_and_other_ports_are_ignored(self) -> None:
        output = """
          TCP    127.0.0.1:9292        127.0.0.1:50000        ESTABLISHED     32684
          TCP    0.0.0.0:9293          0.0.0.0:0              LISTENING       111
          UDP    0.0.0.0:9292          *:*                                    222
        """
        self.assertEqual(probe.parse_netstat_listener_pids(output, 9292), set())

    def test_multiple_listener_rows_return_distinct_owners(self) -> None:
        output = """
          TCP    0.0.0.0:9494          0.0.0.0:0              LISTENING       101
          TCP    [::]:9494             [::]:0                 LISTENING       101
          TCP    127.0.0.1:9494        0.0.0.0:0              LISTENING       202
        """
        self.assertEqual(probe.parse_netstat_listener_pids(output, 9494), {101, 202})

    def test_malformed_relevant_pid_rejects(self) -> None:
        output = "TCP 127.0.0.1:9494 0.0.0.0:0 LISTENING nope"
        with self.assertRaises(ValueError):
            probe.parse_netstat_listener_pids(output, 9494)

    def test_exact_numeric_port_not_suffix_match(self) -> None:
        output = "TCP 127.0.0.1:19494 0.0.0.0:0 LISTENING 123"
        self.assertEqual(probe.parse_netstat_listener_pids(output, 9494), set())


class ListenerSampleTests(unittest.TestCase):
    def test_successful_sample(self) -> None:
        completed = SimpleNamespace(
            returncode=0,
            stdout="TCP 127.0.0.1:9494 0.0.0.0:0 LISTENING 123\n",
            stderr="",
        )
        with mock.patch("listener_probe.subprocess.run", return_value=completed):
            sample = probe.listener_pid_sample(9494)
        self.assertTrue(sample.available)
        self.assertEqual(sample.pids, frozenset({123}))
        self.assertEqual(sample.backend, "netstat")

    def test_timeout_is_explicit_unavailability(self) -> None:
        with mock.patch(
            "listener_probe.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["netstat"], 5),
        ):
            sample = probe.listener_pid_sample(9494)
        self.assertFalse(sample.available)
        self.assertEqual(sample.error, "listener-query-timeout")

    def test_nonzero_exit_is_explicit_unavailability(self) -> None:
        completed = SimpleNamespace(returncode=1, stdout="", stderr="failed")
        with mock.patch("listener_probe.subprocess.run", return_value=completed):
            sample = probe.listener_pid_sample(9494)
        self.assertFalse(sample.available)
        self.assertIn("listener-query-exit-1", sample.error or "")


class ListenerQualificationTests(unittest.TestCase):
    @staticmethod
    def sample(
        *,
        available: bool,
        pids: set[int] | None = None,
        error: str | None = None,
        elapsed: float = 0.01,
    ) -> probe.ListenerPidSample:
        return probe.ListenerPidSample(
            available,
            frozenset(pids or set()),
            "netstat",
            elapsed,
            error,
        )

    def test_timeout_then_success(self) -> None:
        samples = deque([
            self.sample(available=False, error="listener-query-timeout"),
            self.sample(available=True, pids={32684}),
        ])
        result = probe.qualify_listener_ownership(
            9292,
            {32684},
            sample_fn=lambda _port, _timeout: samples.popleft(),
            sleep_fn=lambda _delay: None,
        )
        self.assertTrue(result.passed)
        self.assertFalse(result.hard_mismatch)
        self.assertEqual(result.attempt_count, 2)
        self.assertEqual(result.timeout_count, 1)

    def test_wrong_pid_is_hard_failure_without_retry(self) -> None:
        calls = 0

        def sample_fn(_port: int, _timeout: float) -> probe.ListenerPidSample:
            nonlocal calls
            calls += 1
            return self.sample(available=True, pids={999})

        result = probe.qualify_listener_ownership(
            9292,
            {32684},
            sample_fn=sample_fn,
            sleep_fn=lambda _delay: None,
        )
        self.assertFalse(result.passed)
        self.assertTrue(result.hard_mismatch)
        self.assertEqual(result.final_error, "listener-pid-mismatch")
        self.assertEqual(calls, 1)

    def test_all_transient_attempts_exhaust(self) -> None:
        result = probe.qualify_listener_ownership(
            9292,
            {32684},
            max_attempts=3,
            sample_fn=lambda _port, _timeout: self.sample(
                available=False,
                error="listener-query-timeout",
            ),
            sleep_fn=lambda _delay: None,
        )
        self.assertFalse(result.passed)
        self.assertFalse(result.hard_mismatch)
        self.assertEqual(result.attempt_count, 3)
        self.assertEqual(result.timeout_count, 3)
        self.assertEqual(result.final_error, "listener-query-unavailable")

    def test_evidence_serializes_sets_as_sorted_lists(self) -> None:
        result = probe.qualify_listener_ownership(
            9494,
            {202, 101},
            sample_fn=lambda _port, _timeout: self.sample(
                available=True,
                pids={101, 202},
            ),
            sleep_fn=lambda _delay: None,
        )
        payload = result.to_dict()
        self.assertEqual(payload["expected_pids"], [101, 202])
        self.assertEqual(payload["actual_pids"], [101, 202])


if __name__ == "__main__":
    unittest.main()
