#!/usr/bin/env python3
"""Checked Windows listener ownership probes for protected runtime control.

The existing controllers historically queried ``Get-NetTCPConnection`` through
PowerShell on every readiness poll. That is correct but heavyweight enough to
become the failure source during long model loads. This module provides a
small, testable ``netstat``-based primitive with explicit availability,
latency, retry, and hard PID-mismatch semantics.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import asdict, dataclass
from typing import Callable, Sequence


class ListenerProbeError(RuntimeError):
    """Raised for invalid listener evidence or a hard ownership mismatch."""


@dataclass(frozen=True)
class ListenerPidSample:
    available: bool
    pids: frozenset[int]
    backend: str
    elapsed_seconds: float
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["pids"] = sorted(self.pids)
        return payload


@dataclass(frozen=True)
class ListenerOwnershipEvidence:
    passed: bool
    hard_mismatch: bool
    port: int
    expected_pids: frozenset[int]
    actual_pids: frozenset[int]
    backend: str
    attempt_count: int
    successful_sample_count: int
    timeout_count: int
    unavailable_count: int
    latencies_seconds: tuple[float, ...]
    errors: tuple[str, ...]
    final_error: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["expected_pids"] = sorted(self.expected_pids)
        payload["actual_pids"] = sorted(self.actual_pids)
        payload["latencies_seconds"] = list(self.latencies_seconds)
        payload["errors"] = list(self.errors)
        return payload


def _validate_port(port: int) -> None:
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise ValueError(f"invalid TCP port: {port!r}")


def _endpoint_port(endpoint: str) -> int | None:
    """Return the numeric final port component from IPv4 or bracketed IPv6."""
    if ":" not in endpoint:
        return None
    _, raw_port = endpoint.rsplit(":", 1)
    if not raw_port.isdigit():
        return None
    value = int(raw_port)
    return value if 0 <= value <= 65535 else None


def parse_netstat_listener_pids(output: str, port: int) -> set[int]:
    """Parse exact TCP LISTENING owners from ``netstat -ano -p TCP`` output.

    Non-listening rows and other ports are ignored. A malformed PID on a row
    that otherwise identifies the requested listener is rejected rather than
    silently converted into an empty set.
    """
    _validate_port(port)
    owners: set[int] = set()
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        protocol, local_endpoint, _foreign_endpoint, state, pid_text = parts[:5]
        if protocol.upper() != "TCP" or state.upper() != "LISTENING":
            continue
        if _endpoint_port(local_endpoint) != port:
            continue
        if not pid_text.isdigit():
            raise ValueError(f"malformed listener PID for port {port}: {pid_text!r}")
        pid = int(pid_text)
        if pid <= 0:
            raise ValueError(f"invalid listener PID for port {port}: {pid}")
        owners.add(pid)
    return owners


def listener_pid_sample(
    port: int,
    timeout_seconds: float = 5.0,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    monotonic: Callable[[], float] = time.monotonic,
) -> ListenerPidSample:
    """Return one checked listener sample without raising transient failures."""
    _validate_port(port)
    if timeout_seconds <= 0:
        raise ValueError("listener query timeout must be positive")
    started = monotonic()
    try:
        completed = runner(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return ListenerPidSample(
            False,
            frozenset(),
            "netstat",
            max(0.0, monotonic() - started),
            "listener-query-timeout",
        )
    except OSError as exc:
        return ListenerPidSample(
            False,
            frozenset(),
            "netstat",
            max(0.0, monotonic() - started),
            f"listener-query-os-error: {exc}",
        )

    elapsed = max(0.0, monotonic() - started)
    if completed.returncode:
        detail = (completed.stderr or completed.stdout or "").strip()[:300]
        return ListenerPidSample(
            False,
            frozenset(),
            "netstat",
            elapsed,
            f"listener-query-exit-{completed.returncode}: {detail}",
        )
    try:
        pids = parse_netstat_listener_pids(completed.stdout, port)
    except ValueError as exc:
        return ListenerPidSample(
            False,
            frozenset(),
            "netstat",
            elapsed,
            f"listener-query-parse-error: {exc}",
        )
    return ListenerPidSample(True, frozenset(pids), "netstat", elapsed)


def qualify_listener_ownership(
    port: int,
    expected_pids: set[int] | frozenset[int],
    *,
    max_attempts: int = 4,
    timeout_seconds: float = 5.0,
    backoff_seconds: Sequence[float] = (0.25, 0.5, 1.0),
    max_window_seconds: float = 15.0,
    sample_fn: Callable[[int, float], ListenerPidSample] = listener_pid_sample,
    sleep_fn: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> ListenerOwnershipEvidence:
    """Qualify exact listener ownership with bounded transient retries.

    Unavailable samples may be retried inside the declared window. A successful
    sample returning the wrong PID set is a hard safety failure and stops
    immediately.
    """
    _validate_port(port)
    expected = frozenset(expected_pids)
    if not expected or any(not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0 for pid in expected):
        raise ValueError("expected listener PID set must contain positive integers")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")
    if timeout_seconds <= 0 or max_window_seconds <= 0:
        raise ValueError("listener retry timeouts must be positive")
    if any(delay < 0 for delay in backoff_seconds):
        raise ValueError("listener retry backoff cannot be negative")

    started = monotonic()
    attempts = 0
    successful = 0
    timeouts = 0
    unavailable = 0
    latencies: list[float] = []
    errors: list[str] = []
    actual = frozenset()

    while attempts < max_attempts and monotonic() - started <= max_window_seconds:
        attempts += 1
        sample = sample_fn(port, timeout_seconds)
        latencies.append(sample.elapsed_seconds)
        actual = sample.pids
        if sample.available:
            successful += 1
            if sample.pids != expected:
                return ListenerOwnershipEvidence(
                    False,
                    True,
                    port,
                    expected,
                    sample.pids,
                    sample.backend,
                    attempts,
                    successful,
                    timeouts,
                    unavailable,
                    tuple(latencies),
                    tuple(errors),
                    "listener-pid-mismatch",
                )
            return ListenerOwnershipEvidence(
                True,
                False,
                port,
                expected,
                sample.pids,
                sample.backend,
                attempts,
                successful,
                timeouts,
                unavailable,
                tuple(latencies),
                tuple(errors),
            )

        unavailable += 1
        error = sample.error or "listener-query-unavailable"
        errors.append(error)
        if error == "listener-query-timeout":
            timeouts += 1
        if attempts >= max_attempts:
            break
        delay = backoff_seconds[min(attempts - 1, len(backoff_seconds) - 1)] if backoff_seconds else 0.0
        remaining = max_window_seconds - (monotonic() - started)
        if remaining <= 0:
            break
        sleep_fn(min(delay, remaining))

    return ListenerOwnershipEvidence(
        False,
        False,
        port,
        expected,
        actual,
        "netstat",
        attempts,
        successful,
        timeouts,
        unavailable,
        tuple(latencies),
        tuple(errors),
        "listener-query-unavailable",
    )
