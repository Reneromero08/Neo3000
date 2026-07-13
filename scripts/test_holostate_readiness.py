#!/usr/bin/env python3
"""CPU-only tests for HoloState readiness admission."""

from __future__ import annotations

import unittest
from collections import deque

import holostate_readiness as readiness
from listener_probe import ListenerOwnershipEvidence


def ownership(
    *,
    passed: bool,
    expected: set[int],
    actual: set[int] | None = None,
    hard_mismatch: bool = False,
    final_error: str | None = None,
) -> ListenerOwnershipEvidence:
    return ListenerOwnershipEvidence(
        passed=passed,
        hard_mismatch=hard_mismatch,
        port=0,
        expected_pids=frozenset(expected),
        actual_pids=frozenset(actual if actual is not None else expected),
        backend="netstat",
        attempt_count=1,
        successful_sample_count=1 if passed or hard_mismatch else 0,
        timeout_count=0,
        unavailable_count=0 if passed or hard_mismatch else 1,
        latencies_seconds=(0.01,),
        errors=(),
        final_error=final_error,
    )


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, delay: float) -> None:
        self.value += delay


class ReadinessTests(unittest.TestCase):
    def test_long_model_load_does_not_query_listeners_in_poll_loop(self) -> None:
        sidecar_health = deque([False] * 30 + [True])
        qualifier_calls: list[tuple[int, frozenset[int]]] = []

        def sidecar_health_ok() -> bool:
            return sidecar_health.popleft() if sidecar_health else True

        def qualifier(port: int, expected: set[int], **_kwargs):
            qualifier_calls.append((port, frozenset(expected)))
            return ownership(passed=True, expected=expected)

        ticks = iter([index * 0.25 for index in range(40)])
        result = readiness.wait_for_holostate_readiness(
            sidecar_pid=37804,
            stable_pids={32684},
            stable_port=9292,
            sidecar_port=9494,
            deadline_seconds=30,
            process_alive=lambda: True,
            stable_health_ok=lambda: True,
            sidecar_health_ok=sidecar_health_ok,
            wddm_has_valid_sample=lambda: True,
            wddm_failure_reason=lambda: None,
            listener_qualifier=qualifier,
            monotonic=lambda: next(ticks),
            sleep_fn=lambda _delay: None,
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.poll_count, 31)
        self.assertEqual(
            qualifier_calls,
            [
                (9292, frozenset({32684})),
                (9494, frozenset({37804})),
                (9292, frozenset({32684})),
            ],
        )

    def test_stable_health_loss_fails_before_listener_queries(self) -> None:
        calls = 0

        def qualifier(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            return ownership(passed=True, expected={1})

        with self.assertRaisesRegex(readiness.HoloStateReadinessError, "stable-health-lost"):
            readiness.wait_for_holostate_readiness(
                sidecar_pid=2,
                stable_pids={1},
                stable_port=9292,
                sidecar_port=9494,
                deadline_seconds=5,
                process_alive=lambda: True,
                stable_health_ok=lambda: False,
                sidecar_health_ok=lambda: False,
                wddm_has_valid_sample=lambda: False,
                wddm_failure_reason=lambda: None,
                listener_qualifier=qualifier,
            )
        self.assertEqual(calls, 0)

    def test_wddm_failure_fails_before_listener_queries(self) -> None:
        calls = 0

        def qualifier(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            return ownership(passed=True, expected={1})

        with self.assertRaisesRegex(readiness.HoloStateReadinessError, "candidate-vram-telemetry-lost"):
            readiness.wait_for_holostate_readiness(
                sidecar_pid=2,
                stable_pids={1},
                stable_port=9292,
                sidecar_port=9494,
                deadline_seconds=5,
                process_alive=lambda: True,
                stable_health_ok=lambda: True,
                sidecar_health_ok=lambda: False,
                wddm_has_valid_sample=lambda: False,
                wddm_failure_reason=lambda: "candidate-vram-telemetry-lost",
                listener_qualifier=qualifier,
            )
        self.assertEqual(calls, 0)

    def test_sidecar_process_exit_fails_before_listener_queries(self) -> None:
        calls = 0

        def qualifier(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            return ownership(passed=True, expected={1})

        with self.assertRaisesRegex(readiness.HoloStateReadinessError, "sidecar-process-exited"):
            readiness.wait_for_holostate_readiness(
                sidecar_pid=2,
                stable_pids={1},
                stable_port=9292,
                sidecar_port=9494,
                deadline_seconds=5,
                process_alive=lambda: False,
                stable_health_ok=lambda: True,
                sidecar_health_ok=lambda: False,
                wddm_has_valid_sample=lambda: False,
                wddm_failure_reason=lambda: None,
                listener_qualifier=qualifier,
            )
        self.assertEqual(calls, 0)

    def test_wrong_stable_pid_is_hard_failure_and_sidecar_is_not_queried(self) -> None:
        calls: list[int] = []

        def qualifier(port: int, expected: set[int], **_kwargs):
            calls.append(port)
            if port == 9292:
                return ownership(
                    passed=False,
                    expected=expected,
                    actual={999},
                    hard_mismatch=True,
                    final_error="listener-pid-mismatch",
                )
            return ownership(passed=True, expected=expected)

        with self.assertRaisesRegex(readiness.HoloStateReadinessError, "stable-listener-pid-mismatch"):
            readiness.wait_for_holostate_readiness(
                sidecar_pid=37804,
                stable_pids={32684},
                stable_port=9292,
                sidecar_port=9494,
                deadline_seconds=5,
                process_alive=lambda: True,
                stable_health_ok=lambda: True,
                sidecar_health_ok=lambda: True,
                wddm_has_valid_sample=lambda: True,
                wddm_failure_reason=lambda: None,
                listener_qualifier=qualifier,
            )
        self.assertEqual(calls, [9292])

    def test_wrong_sidecar_pid_is_hard_failure(self) -> None:
        calls: list[int] = []

        def qualifier(port: int, expected: set[int], **_kwargs):
            calls.append(port)
            if port == 9494:
                return ownership(
                    passed=False,
                    expected=expected,
                    actual={999},
                    hard_mismatch=True,
                    final_error="listener-pid-mismatch",
                )
            return ownership(passed=True, expected=expected)

        with self.assertRaisesRegex(readiness.HoloStateReadinessError, "sidecar-listener-pid-mismatch") as caught:
            readiness.wait_for_holostate_readiness(
                sidecar_pid=37804,
                stable_pids={32684},
                stable_port=9292,
                sidecar_port=9494,
                deadline_seconds=5,
                process_alive=lambda: True,
                stable_health_ok=lambda: True,
                sidecar_health_ok=lambda: True,
                wddm_has_valid_sample=lambda: True,
                wddm_failure_reason=lambda: None,
                listener_qualifier=qualifier,
            )
        self.assertEqual(calls, [9292, 9494])
        self.assertTrue(caught.exception.evidence["sidecar_listener"]["hard_mismatch"])

    def test_listener_unavailability_is_not_misreported_as_empty_pid_set(self) -> None:
        def qualifier(port: int, expected: set[int], **_kwargs):
            return ownership(
                passed=False,
                expected=expected,
                actual=set(),
                final_error="listener-query-unavailable",
            )

        with self.assertRaisesRegex(readiness.HoloStateReadinessError, "stable-listener-query-unavailable") as caught:
            readiness.wait_for_holostate_readiness(
                sidecar_pid=37804,
                stable_pids={32684},
                stable_port=9292,
                sidecar_port=9494,
                deadline_seconds=5,
                process_alive=lambda: True,
                stable_health_ok=lambda: True,
                sidecar_health_ok=lambda: True,
                wddm_has_valid_sample=lambda: True,
                wddm_failure_reason=lambda: None,
                listener_qualifier=qualifier,
            )
        self.assertEqual(caught.exception.evidence["poll_count"], 1)
        listener = caught.exception.evidence["stable_listener"]
        self.assertFalse(listener["passed"])
        self.assertEqual(listener["attempt_count"], 1)
        self.assertEqual(listener["actual_pids"], [])

    def test_successful_readiness_serializes_listener_evidence(self) -> None:
        def qualifier(_port: int, expected: set[int], **_kwargs):
            return ownership(passed=True, expected=expected)

        result = readiness.wait_for_holostate_readiness(
            sidecar_pid=37804,
            stable_pids={32684},
            stable_port=9292,
            sidecar_port=9494,
            deadline_seconds=5,
            process_alive=lambda: True,
            stable_health_ok=lambda: True,
            sidecar_health_ok=lambda: True,
            wddm_has_valid_sample=lambda: True,
            wddm_failure_reason=lambda: None,
            listener_qualifier=qualifier,
        )
        payload = result.to_dict()
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["stable_listener"]["expected_pids"], [32684])
        self.assertEqual(payload["sidecar_listener"]["expected_pids"], [37804])
        self.assertEqual(payload["stable_listener_confirmation"]["expected_pids"], [32684])

    def test_listener_qualification_windows_are_bounded_by_readiness_deadline(self) -> None:
        windows: list[float] = []

        def qualifier(_port: int, expected: set[int], **kwargs):
            windows.append(float(kwargs["max_window_seconds"]))
            return ownership(passed=True, expected=expected)

        ticks = iter([0.0, 0.25, 0.5, 0.75, 1.0, 1.25])
        result = readiness.wait_for_holostate_readiness(
            sidecar_pid=37804,
            stable_pids={32684},
            stable_port=9292,
            sidecar_port=9494,
            deadline_seconds=5.0,
            process_alive=lambda: True,
            stable_health_ok=lambda: True,
            sidecar_health_ok=lambda: True,
            wddm_has_valid_sample=lambda: True,
            wddm_failure_reason=lambda: None,
            listener_qualifier=qualifier,
            listener_kwargs={"max_window_seconds": 15.0},
            monotonic=lambda: next(ticks),
        )
        self.assertTrue(result.passed)
        self.assertEqual(windows, [4.5, 4.25, 4.0])

    def test_stable_query_consumes_shared_boundary_window(self) -> None:
        clock = [0.0]
        windows: list[tuple[int, float]] = []

        def qualifier(port: int, expected: set[int], **kwargs):
            windows.append((port, float(kwargs["max_window_seconds"])))
            if port == 9292 and len(windows) == 1:
                clock[0] += 4.0
            return ownership(passed=True, expected=expected)

        stable, sidecar = readiness.qualify_runtime_ownership(
            stable_port=9292,
            stable_pids={32684},
            sidecar_port=9494,
            sidecar_pid=37804,
            listener_qualifier=qualifier,
            listener_kwargs={
                "max_window_seconds": 15.0,
                "maximum_total_query_window_seconds": 5.0,
            },
            monotonic=lambda: clock[0],
        )
        self.assertTrue(stable.passed and sidecar.passed)
        self.assertEqual(windows, [(9292, 5.0), (9494, 1.0)])

    def test_resilient_readiness_waits_for_fresh_wddm_before_listener_queries(self) -> None:
        fresh = deque([False, False, True, True, True])
        clock = [0.0]
        qualifier_calls: list[int] = []

        def qualifier(port: int, expected: set[int], **_kwargs):
            qualifier_calls.append(port)
            return ownership(passed=True, expected=expected)

        result = readiness.wait_for_holostate_readiness(
            sidecar_pid=44748,
            stable_pids={32684},
            stable_port=9292,
            sidecar_port=9494,
            deadline_seconds=30.0,
            process_alive=lambda: True,
            stable_health_ok=lambda: True,
            sidecar_health_ok=lambda: True,
            wddm_has_valid_sample=lambda: True,
            wddm_has_fresh_valid_sample=lambda: fresh.popleft() if fresh else True,
            wddm_failure_reason=lambda: None,
            wddm_snapshot=lambda: {"consecutive_failures": 0},
            listener_qualifier=qualifier,
            monotonic=lambda: clock[0],
            sleep_fn=lambda delay: clock.__setitem__(0, clock[0] + delay),
        )
        self.assertTrue(result.passed)
        self.assertEqual(qualifier_calls, [9292, 9494, 9292])
        self.assertGreaterEqual(result.poll_count, 4)

    def test_transient_gap_during_listener_query_forces_full_requalification(self) -> None:
        # Fresh at the first listener boundary, stale immediately afterward,
        # then recovered.  Admission must use a new stable/sidecar pair.
        fresh = deque([True, False, True, True, True])
        clock = [0.0]
        qualifier_calls: list[int] = []

        def qualifier(port: int, expected: set[int], **_kwargs):
            qualifier_calls.append(port)
            return ownership(passed=True, expected=expected)

        result = readiness.wait_for_holostate_readiness(
            sidecar_pid=44748,
            stable_pids={32684},
            stable_port=9292,
            sidecar_port=9494,
            deadline_seconds=30.0,
            process_alive=lambda: True,
            stable_health_ok=lambda: True,
            sidecar_health_ok=lambda: True,
            wddm_has_valid_sample=lambda: True,
            wddm_has_fresh_valid_sample=lambda: fresh.popleft() if fresh else True,
            wddm_failure_reason=lambda: None,
            listener_qualifier=qualifier,
            monotonic=lambda: clock[0],
            sleep_fn=lambda delay: clock.__setitem__(0, clock[0] + delay),
        )
        self.assertTrue(result.passed)
        self.assertEqual(qualifier_calls, [9292, 9494, 9292, 9494, 9292])

    def test_resilient_readiness_still_fails_on_hard_wddm_loss(self) -> None:
        failures = deque([None, "candidate-vram-telemetry-lost"])
        clock = [0.0]
        qualifier_calls = 0

        def qualifier(_port: int, expected: set[int], **_kwargs):
            nonlocal qualifier_calls
            qualifier_calls += 1
            return ownership(passed=True, expected=expected)

        with self.assertRaisesRegex(
            readiness.HoloStateReadinessError,
            "candidate-vram-telemetry-lost",
        ):
            readiness.wait_for_holostate_readiness(
                sidecar_pid=44748,
                stable_pids={32684},
                stable_port=9292,
                sidecar_port=9494,
                deadline_seconds=30.0,
                process_alive=lambda: True,
                stable_health_ok=lambda: True,
                sidecar_health_ok=lambda: True,
                wddm_has_valid_sample=lambda: True,
                wddm_has_fresh_valid_sample=lambda: False,
                wddm_failure_reason=lambda: failures.popleft() if failures else "candidate-vram-telemetry-lost",
                listener_qualifier=qualifier,
                monotonic=lambda: clock[0],
                sleep_fn=lambda delay: clock.__setitem__(0, clock[0] + delay),
            )
        self.assertEqual(qualifier_calls, 0)


class StableHealthRecoveryTests(unittest.TestCase):
    def test_one_transient_failed_stable_health_probe_recovers(self) -> None:
        clock = FakeClock()
        health = deque([False, True, True, True, True, True])

        result = readiness.wait_for_holostate_readiness(
            sidecar_pid=2,
            stable_pids={1},
            stable_port=9292,
            sidecar_port=9494,
            deadline_seconds=5,
            process_alive=lambda: True,
            stable_process_alive=lambda: True,
            stable_listener_ownership=lambda: ownership(passed=True, expected={1}),
            stable_health_ok=lambda: health.popleft() if health else True,
            sidecar_health_ok=lambda: True,
            wddm_has_valid_sample=lambda: True,
            wddm_failure_reason=lambda: None,
            listener_qualifier=lambda _port, expected, **_kwargs: ownership(
                passed=True, expected=expected
            ),
            stable_health_recovery_policy=readiness.StableHealthRecoveryPolicy(
                maximum_consecutive_failure_seconds=1.0,
                required_consecutive_successes=3,
            ),
            monotonic=clock.monotonic,
            sleep_fn=clock.sleep,
        )

        evidence = result.stable_health_recovery
        self.assertEqual(evidence["failed_stable_health_probes"], 1)
        self.assertEqual(evidence["recovery_events"], 1)
        self.assertTrue(evidence["final_stable_health_ok"])

    def test_several_failures_inside_grace_window_recover(self) -> None:
        clock = FakeClock()
        health = deque([False, False, False, True, True, True, True, True])

        result = readiness.wait_for_holostate_readiness(
            sidecar_pid=2,
            stable_pids={1},
            stable_port=9292,
            sidecar_port=9494,
            deadline_seconds=5,
            process_alive=lambda: True,
            stable_process_alive=lambda: True,
            stable_listener_ownership=lambda: ownership(passed=True, expected={1}),
            stable_health_ok=lambda: health.popleft() if health else True,
            sidecar_health_ok=lambda: True,
            wddm_has_valid_sample=lambda: True,
            wddm_failure_reason=lambda: None,
            listener_qualifier=lambda _port, expected, **_kwargs: ownership(
                passed=True, expected=expected
            ),
            stable_health_recovery_policy=readiness.StableHealthRecoveryPolicy(
                maximum_consecutive_failure_seconds=2.0,
                required_consecutive_successes=3,
            ),
            monotonic=clock.monotonic,
            sleep_fn=clock.sleep,
        )

        evidence = result.stable_health_recovery
        self.assertEqual(evidence["failed_stable_health_probes"], 3)
        self.assertEqual(evidence["recovery_events"], 1)
        self.assertLessEqual(
            evidence["maximum_consecutive_failure_duration_seconds"], 2.0
        )

    def test_health_recovery_grace_deadline_is_fatal(self) -> None:
        clock = FakeClock()

        with self.assertRaisesRegex(
            readiness.HoloStateReadinessError,
            "stable-health-recovery-timeout",
        ) as caught:
            readiness.wait_for_holostate_readiness(
                sidecar_pid=2,
                stable_pids={1},
                stable_port=9292,
                sidecar_port=9494,
                deadline_seconds=5,
                process_alive=lambda: True,
                stable_process_alive=lambda: True,
                stable_listener_ownership=lambda: ownership(
                    passed=True, expected={1}
                ),
                stable_health_ok=lambda: False,
                sidecar_health_ok=lambda: True,
                wddm_has_valid_sample=lambda: True,
                wddm_failure_reason=lambda: None,
                listener_qualifier=lambda _port, expected, **_kwargs: ownership(
                    passed=True, expected=expected
                ),
                stable_health_recovery_policy=readiness.StableHealthRecoveryPolicy(
                    maximum_consecutive_failure_seconds=0.5,
                    required_consecutive_successes=3,
                ),
                monotonic=clock.monotonic,
                sleep_fn=clock.sleep,
            )

        evidence = caught.exception.evidence["stable_health_recovery"]
        self.assertGreater(
            evidence["maximum_consecutive_failure_duration_seconds"], 0.5
        )
        self.assertFalse(evidence["final_stable_health_ok"])

    def test_stable_pid_loss_is_immediately_fatal(self) -> None:
        clock = FakeClock()

        with self.assertRaisesRegex(
            readiness.HoloStateReadinessError,
            "stable-pid-lost-before-readiness",
        ) as caught:
            readiness.wait_for_holostate_readiness(
                sidecar_pid=2,
                stable_pids={1},
                stable_port=9292,
                sidecar_port=9494,
                deadline_seconds=5,
                process_alive=lambda: True,
                stable_process_alive=lambda: False,
                stable_listener_ownership=lambda: ownership(
                    passed=True, expected={1}
                ),
                stable_health_ok=lambda: True,
                sidecar_health_ok=lambda: True,
                wddm_has_valid_sample=lambda: True,
                wddm_failure_reason=lambda: None,
                stable_health_recovery_policy=readiness.StableHealthRecoveryPolicy(),
                monotonic=clock.monotonic,
                sleep_fn=clock.sleep,
            )

        evidence = caught.exception.evidence["stable_health_recovery"]
        self.assertEqual(evidence["stable_pid_checks"], 1)
        self.assertEqual(evidence["stable_health_probe_attempts"], 0)

    def test_stable_listener_ownership_change_is_immediately_fatal(self) -> None:
        clock = FakeClock()

        with self.assertRaisesRegex(
            readiness.HoloStateReadinessError,
            "stable_startup-listener-pid-mismatch",
        ) as caught:
            readiness.wait_for_holostate_readiness(
                sidecar_pid=2,
                stable_pids={1},
                stable_port=9292,
                sidecar_port=9494,
                deadline_seconds=5,
                process_alive=lambda: True,
                stable_process_alive=lambda: True,
                stable_listener_ownership=lambda: ownership(
                    passed=False,
                    expected={1},
                    actual={9},
                    hard_mismatch=True,
                    final_error="listener-pid-mismatch",
                ),
                stable_health_ok=lambda: True,
                sidecar_health_ok=lambda: True,
                wddm_has_valid_sample=lambda: True,
                wddm_failure_reason=lambda: None,
                stable_health_recovery_policy=readiness.StableHealthRecoveryPolicy(),
                monotonic=clock.monotonic,
                sleep_fn=clock.sleep,
            )

        evidence = caught.exception.evidence["stable_health_recovery"]
        self.assertEqual(evidence["stable_listener_checks"], 1)
        self.assertEqual(evidence["stable_health_probe_attempts"], 0)

    def test_readiness_waits_for_required_consecutive_health_successes(self) -> None:
        clock = FakeClock()
        health_attempts = 0
        qualification_health_counts: list[int] = []

        def health_ok() -> bool:
            nonlocal health_attempts
            health_attempts += 1
            return True

        def qualifier(_port: int, expected: set[int], **_kwargs):
            qualification_health_counts.append(health_attempts)
            return ownership(passed=True, expected=expected)

        result = readiness.wait_for_holostate_readiness(
            sidecar_pid=2,
            stable_pids={1},
            stable_port=9292,
            sidecar_port=9494,
            deadline_seconds=5,
            process_alive=lambda: True,
            stable_process_alive=lambda: True,
            stable_listener_ownership=lambda: ownership(passed=True, expected={1}),
            stable_health_ok=health_ok,
            sidecar_health_ok=lambda: True,
            wddm_has_valid_sample=lambda: True,
            wddm_failure_reason=lambda: None,
            listener_qualifier=qualifier,
            stable_health_recovery_policy=readiness.StableHealthRecoveryPolicy(
                required_consecutive_successes=3
            ),
            monotonic=clock.monotonic,
            sleep_fn=clock.sleep,
        )

        self.assertTrue(result.passed)
        self.assertGreaterEqual(min(qualification_health_counts), 3)
        self.assertGreaterEqual(
            result.stable_health_recovery[
                "consecutive_successes_before_admission"
            ],
            3,
        )


if __name__ == "__main__":
    unittest.main()
