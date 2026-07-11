#!/usr/bin/env python3
"""Bounded resilience for exact-PID WDDM telemetry.

The existing Neo3000 sampler obtains exact per-process WDDM dedicated-memory
samples from ``GPU Process Memory(*)\\Dedicated Usage``.  The underlying
``Get-Counter`` query is an external Windows telemetry surface and can
occasionally time out even after several valid exact-PID samples.

This module does not weaken attribution, replace WDDM with aggregate GPU
measurements, or permit admission without a fresh exact-PID sample.  It only
separates one transient query failure from sustained telemetry loss.
"""

from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class WddmTelemetryPolicy:
    """Fail-closed timing law for one exact-PID telemetry stream."""

    initial_grace_seconds: float = 60.0
    max_consecutive_failures: int = 2
    max_valid_sample_gap_seconds: float = 30.0
    admission_freshness_seconds: float = 5.0

    def validate(self) -> None:
        if self.initial_grace_seconds < 0:
            raise ValueError("initial_grace_seconds must be non-negative")
        if self.max_consecutive_failures < 0:
            raise ValueError("max_consecutive_failures must be non-negative")
        if self.max_valid_sample_gap_seconds <= 0:
            raise ValueError("max_valid_sample_gap_seconds must be positive")
        if self.admission_freshness_seconds <= 0:
            raise ValueError("admission_freshness_seconds must be positive")
        if self.admission_freshness_seconds > self.max_valid_sample_gap_seconds:
            raise ValueError(
                "admission_freshness_seconds cannot exceed max_valid_sample_gap_seconds"
            )


@dataclass(frozen=True)
class WddmTelemetrySnapshot:
    """Bounded state returned to readiness and resource gates."""

    failure_reason: str | None
    admission_ready: bool
    has_valid_sample: bool
    sample_count: int
    peak_bytes: int | None
    first_valid_sample_seconds: float | None
    last_valid_sample_age_seconds: float | None
    consecutive_failures: int
    maximum_consecutive_failures: int
    total_failures: int
    recovered_gap_count: int
    transient_gap_active: bool
    exact_instances: tuple[str, ...]
    recent_failures: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ResilientWddmTelemetry:
    """Track exact-PID WDDM samples with a bounded transient-failure window.

    Safety properties:

    * a memory-ceiling violation fails immediately;
    * attribution never falls back to aggregate GPU memory;
    * admission requires a currently fresh valid exact-PID sample;
    * a single unavailable query after valid samples is recorded but tolerated;
    * sustained failures or an excessive valid-sample gap fail closed.
    """

    def __init__(
        self,
        *,
        ceiling_bytes: int,
        policy: WddmTelemetryPolicy,
        started_at: float | None = None,
        recent_failure_limit: int = 16,
    ) -> None:
        policy.validate()
        if ceiling_bytes <= 0:
            raise ValueError("ceiling_bytes must be positive")
        if recent_failure_limit <= 0:
            raise ValueError("recent_failure_limit must be positive")

        self.ceiling_bytes = int(ceiling_bytes)
        self.policy = policy
        self.started_at = time.monotonic() if started_at is None else float(started_at)
        self.recent_failure_limit = int(recent_failure_limit)

        self.first_valid_at: float | None = None
        self.last_valid_at: float | None = None
        self.sample_count = 0
        self.peak_bytes = 0
        self.instances: set[str] = set()

        self.consecutive_failures = 0
        self.maximum_consecutive_failures = 0
        self.total_failures = 0
        self.recovered_gap_count = 0
        self.recent_failures: list[str] = []
        self._failure_reason: str | None = None

    @staticmethod
    def _normalize_instances(instances: Iterable[Any]) -> tuple[str, ...]:
        values = tuple(sorted({str(value) for value in instances if str(value)}))
        if not values:
            raise ValueError("valid exact-PID sample did not include counter instances")
        return values

    def observe_valid(
        self,
        *,
        bytes_used: int,
        instances: Iterable[Any],
        now: float | None = None,
    ) -> None:
        """Record one valid exact-PID sample."""

        observed_at = time.monotonic() if now is None else float(now)
        if isinstance(bytes_used, bool) or not isinstance(bytes_used, int):
            raise ValueError("bytes_used must be an integer")
        if bytes_used < 0:
            raise ValueError("bytes_used must be non-negative")
        exact_instances = self._normalize_instances(instances)

        if self.consecutive_failures:
            self.recovered_gap_count += 1
        self.consecutive_failures = 0

        self.sample_count += 1
        self.peak_bytes = max(self.peak_bytes, bytes_used)
        self.instances.update(exact_instances)
        if self.first_valid_at is None:
            self.first_valid_at = observed_at
        self.last_valid_at = observed_at

        if bytes_used > self.ceiling_bytes:
            self._failure_reason = "candidate-memory-ceiling"

    def observe_unavailable(
        self,
        error: str | None,
        *,
        now: float | None = None,
    ) -> None:
        """Record one unavailable counter query without immediately overreacting."""

        observed_at = time.monotonic() if now is None else float(now)
        reason = str(error or "telemetry-unavailable")
        self.total_failures += 1
        self.consecutive_failures += 1
        self.maximum_consecutive_failures = max(
            self.maximum_consecutive_failures,
            self.consecutive_failures,
        )
        self.recent_failures.append(reason)
        if len(self.recent_failures) > self.recent_failure_limit:
            del self.recent_failures[:-self.recent_failure_limit]

        self._refresh_failure(observed_at)

    def observe_sample(self, sample: Any, *, now: float | None = None) -> None:
        """Accept a ``ProcessVramSample``-like object without importing neo_loop."""

        available = bool(getattr(sample, "available", False))
        bytes_used = getattr(sample, "bytes", None)
        instances = getattr(sample, "instances", ())
        error = getattr(sample, "error", None)
        if available and isinstance(bytes_used, int) and not isinstance(bytes_used, bool):
            self.observe_valid(bytes_used=bytes_used, instances=instances, now=now)
        else:
            self.observe_unavailable(error, now=now)

    def _last_valid_age(self, now: float) -> float | None:
        if self.last_valid_at is None:
            return None
        return max(0.0, now - self.last_valid_at)

    def _refresh_failure(self, now: float) -> str | None:
        if self._failure_reason == "candidate-memory-ceiling":
            return self._failure_reason

        if self.first_valid_at is None:
            if now - self.started_at >= self.policy.initial_grace_seconds:
                self._failure_reason = "candidate-vram-telemetry-unavailable"
            return self._failure_reason

        gap = self._last_valid_age(now)
        too_many_failures = (
            self.consecutive_failures > self.policy.max_consecutive_failures
        )
        gap_expired = (
            gap is not None
            and gap > self.policy.max_valid_sample_gap_seconds
        )
        if too_many_failures or gap_expired:
            self._failure_reason = "candidate-vram-telemetry-lost"
        return self._failure_reason

    def failure_reason(self, *, now: float | None = None) -> str | None:
        observed_at = time.monotonic() if now is None else float(now)
        return self._refresh_failure(observed_at)

    def has_valid_sample(self) -> bool:
        return self.first_valid_at is not None

    def has_fresh_valid_sample(self, *, now: float | None = None) -> bool:
        observed_at = time.monotonic() if now is None else float(now)
        if self.failure_reason(now=observed_at) is not None:
            return False
        gap = self._last_valid_age(observed_at)
        return (
            gap is not None
            and gap <= self.policy.admission_freshness_seconds
            and self.consecutive_failures == 0
        )

    def snapshot(self, *, now: float | None = None) -> WddmTelemetrySnapshot:
        observed_at = time.monotonic() if now is None else float(now)
        failure = self.failure_reason(now=observed_at)
        gap = self._last_valid_age(observed_at)
        return WddmTelemetrySnapshot(
            failure_reason=failure,
            admission_ready=self.has_fresh_valid_sample(now=observed_at),
            has_valid_sample=self.has_valid_sample(),
            sample_count=self.sample_count,
            peak_bytes=self.peak_bytes if self.sample_count else None,
            first_valid_sample_seconds=(
                max(0.0, self.first_valid_at - self.started_at)
                if self.first_valid_at is not None
                else None
            ),
            last_valid_sample_age_seconds=gap,
            consecutive_failures=self.consecutive_failures,
            maximum_consecutive_failures=self.maximum_consecutive_failures,
            total_failures=self.total_failures,
            recovered_gap_count=self.recovered_gap_count,
            transient_gap_active=(
                failure is None
                and self.first_valid_at is not None
                and self.consecutive_failures > 0
            ),
            exact_instances=tuple(sorted(self.instances)),
            recent_failures=tuple(self.recent_failures),
        )
