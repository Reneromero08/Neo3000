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

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Iterable


# The final result artifact is capped at 2 MiB.  Transitions cover only gaps,
# unavailable queries, recoveries, and hard failures, so 512 leaves ample
# envelope space while remaining far above the normal fail-closed path.
DEFAULT_TRANSITION_EVENT_LIMIT = 512
MAX_TRANSITION_REASON_CHARACTERS = 256


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
class WddmTelemetryTransition:
    """One ordered, bounded exact-PID telemetry state transition."""

    sequence: int
    kind: str
    observed_monotonic_seconds_since_start: float
    consecutive_failures: int
    total_failures: int
    sample_count: int
    last_valid_sample_age_seconds: float | None
    reason: str | None
    reason_sha256: str | None
    reason_truncated: bool
    recovered_failure_count: int | None = None
    trigger_kind: str | None = None


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
    maximum_valid_sample_gap_seconds: float | None
    consecutive_failures: int
    maximum_consecutive_failures: int
    total_failures: int
    recovered_gap_count: int
    transient_gap_active: bool
    exact_instances: tuple[str, ...]
    recent_failures: tuple[str, ...]
    transition_events: tuple[WddmTelemetryTransition, ...]
    transition_event_count: int
    transition_event_limit: int
    transition_event_attempt_count: int
    transition_events_omitted: int
    transition_overflowed: bool
    transition_ledger_sha256: str
    gap_start_event_count: int
    unavailable_event_count: int
    recovery_event_count: int
    hard_failure_event_count: int

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
        transition_event_limit: int = DEFAULT_TRANSITION_EVENT_LIMIT,
    ) -> None:
        policy.validate()
        if ceiling_bytes <= 0:
            raise ValueError("ceiling_bytes must be positive")
        if recent_failure_limit <= 0:
            raise ValueError("recent_failure_limit must be positive")
        if transition_event_limit < 2:
            raise ValueError("transition_event_limit must be at least 2")

        self.ceiling_bytes = int(ceiling_bytes)
        self.policy = policy
        self.started_at = time.monotonic() if started_at is None else float(started_at)
        self.recent_failure_limit = int(recent_failure_limit)
        self.transition_event_limit = int(transition_event_limit)

        self.first_valid_at: float | None = None
        self.last_valid_at: float | None = None
        self.maximum_valid_sample_gap_seconds = 0.0
        self.sample_count = 0
        self.peak_bytes = 0
        self.instances: set[str] = set()

        self.consecutive_failures = 0
        self.maximum_consecutive_failures = 0
        self.total_failures = 0
        self.recovered_gap_count = 0
        self.recent_failures: list[str] = []
        self._failure_reason: str | None = None
        self._hard_failure_reasons: set[str] = set()
        self.transition_events: list[WddmTelemetryTransition] = []
        self.transition_event_attempt_count = 0
        self.transition_events_omitted = 0
        self.transition_overflowed = False

    @staticmethod
    def _normalize_instances(instances: Iterable[Any]) -> tuple[str, ...]:
        values = tuple(sorted({str(value) for value in instances if str(value)}))
        if not values:
            raise ValueError("valid exact-PID sample did not include counter instances")
        return values

    @staticmethod
    def _bounded_reason(reason: str | None) -> tuple[str | None, str | None, bool]:
        if reason is None:
            return None, None, False
        full_reason = str(reason)
        encoded = full_reason.encode("utf-8", errors="replace")
        return (
            full_reason[:MAX_TRANSITION_REASON_CHARACTERS],
            hashlib.sha256(encoded).hexdigest(),
            len(full_reason) > MAX_TRANSITION_REASON_CHARACTERS,
        )

    def _make_transition(
        self,
        *,
        sequence: int,
        kind: str,
        now: float,
        reason: str | None = None,
        recovered_failure_count: int | None = None,
        trigger_kind: str | None = None,
    ) -> WddmTelemetryTransition:
        bounded_reason, reason_sha256, reason_truncated = self._bounded_reason(reason)
        return WddmTelemetryTransition(
            sequence=sequence,
            kind=kind,
            observed_monotonic_seconds_since_start=round(
                max(0.0, now - self.started_at), 6
            ),
            consecutive_failures=self.consecutive_failures,
            total_failures=self.total_failures,
            sample_count=self.sample_count,
            last_valid_sample_age_seconds=self._last_valid_age(now),
            reason=bounded_reason,
            reason_sha256=reason_sha256,
            reason_truncated=reason_truncated,
            recovered_failure_count=recovered_failure_count,
            trigger_kind=trigger_kind,
        )

    def _append_transition(
        self,
        kind: str,
        *,
        now: float,
        reason: str | None = None,
        recovered_failure_count: int | None = None,
        trigger_kind: str | None = None,
    ) -> bool:
        """Append one transition or fail closed with a final overflow sentinel.

        One slot is reserved for the overflow sentinel.  Once that sentinel is
        written, later transition attempts are counted as omitted and the
        telemetry stream remains permanently failed.
        """

        self.transition_event_attempt_count += 1
        sequence = self.transition_event_attempt_count
        if self.transition_overflowed:
            self.transition_events_omitted += 1
            return False

        if len(self.transition_events) >= self.transition_event_limit - 1:
            overflow_reason = "candidate-vram-telemetry-transition-overflow"
            overflow_detail = (
                overflow_reason
                if reason is None
                else f"{overflow_reason}; omitted-{kind}: {reason}"
            )
            self.transition_events.append(
                self._make_transition(
                    sequence=sequence,
                    kind="hard-failure",
                    now=now,
                    reason=overflow_detail,
                    trigger_kind=kind,
                )
            )
            self.transition_overflowed = True
            self.transition_events_omitted += 1
            self._hard_failure_reasons.add(overflow_reason)
            if self._failure_reason is None:
                self._failure_reason = overflow_reason
            return False

        self.transition_events.append(
            self._make_transition(
                sequence=sequence,
                kind=kind,
                now=now,
                reason=reason,
                recovered_failure_count=recovered_failure_count,
                trigger_kind=trigger_kind,
            )
        )
        return True

    def _record_hard_failure(
        self,
        reason: str,
        *,
        now: float,
        trigger_kind: str,
    ) -> None:
        if reason not in self._hard_failure_reasons:
            self._hard_failure_reasons.add(reason)
            self._append_transition(
                "hard-failure",
                now=now,
                reason=reason,
                trigger_kind=trigger_kind,
            )
        if self._failure_reason is None:
            self._failure_reason = reason

    def fail_closed(
        self,
        reason: str,
        *,
        now: float | None = None,
        trigger_kind: str = "external",
    ) -> None:
        """Permanently fail the telemetry stream and retain the transition."""

        observed_at = time.monotonic() if now is None else float(now)
        self._record_hard_failure(str(reason), now=observed_at, trigger_kind=trigger_kind)

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

        # A late valid result must not erase a gap that already crossed the
        # fail-closed bound while the external counter query was stalled.
        self._refresh_failure(observed_at)
        if self.last_valid_at is not None:
            self.maximum_valid_sample_gap_seconds = max(
                self.maximum_valid_sample_gap_seconds,
                max(0.0, observed_at - self.last_valid_at),
            )

        recovered_failure_count = self.consecutive_failures
        if recovered_failure_count:
            self.recovered_gap_count += 1
            self._append_transition(
                "recovery",
                now=observed_at,
                reason="valid-exact-pid-sample",
                recovered_failure_count=recovered_failure_count,
            )
        self.consecutive_failures = 0

        self.sample_count += 1
        self.peak_bytes = max(self.peak_bytes, bytes_used)
        self.instances.update(exact_instances)
        if self.first_valid_at is None:
            self.first_valid_at = observed_at
        self.last_valid_at = observed_at

        if bytes_used > self.ceiling_bytes:
            self._record_hard_failure(
                "candidate-memory-ceiling",
                now=observed_at,
                trigger_kind="memory-ceiling",
            )

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
        bounded_reason, _, _ = self._bounded_reason(reason)
        self.recent_failures.append(bounded_reason or "telemetry-unavailable")
        if len(self.recent_failures) > self.recent_failure_limit:
            del self.recent_failures[:-self.recent_failure_limit]

        # Before the first exact-PID sample, unavailable queries belong to the
        # separate initial-attribution grace window.  They remain complete
        # evidence but cannot contaminate the post-attribution gap streak or
        # manufacture a recovery when attribution first appears.
        if self.first_valid_at is not None:
            self.consecutive_failures += 1
            self.maximum_consecutive_failures = max(
                self.maximum_consecutive_failures,
                self.consecutive_failures,
            )
            if self.consecutive_failures == 1:
                self._append_transition("gap-start", now=observed_at, reason=reason)
        self._append_transition("unavailable", now=observed_at, reason=reason)

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
        if self.first_valid_at is None:
            if now - self.started_at >= self.policy.initial_grace_seconds:
                self._record_hard_failure(
                    "candidate-vram-telemetry-unavailable",
                    now=now,
                    trigger_kind="initial-grace-expired",
                )
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
            triggers = []
            if too_many_failures:
                triggers.append("failure-streak")
            if gap_expired:
                triggers.append("valid-sample-gap")
            self._record_hard_failure(
                "candidate-vram-telemetry-lost",
                now=now,
                trigger_kind="+".join(triggers),
            )
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
        maximum_gap = (
            max(self.maximum_valid_sample_gap_seconds, gap or 0.0)
            if self.last_valid_at is not None
            else None
        )
        transition_events = tuple(self.transition_events)
        transition_payload = json.dumps(
            [asdict(event) for event in transition_events],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        event_counts = {
            kind: sum(1 for event in transition_events if event.kind == kind)
            for kind in ("gap-start", "unavailable", "recovery", "hard-failure")
        }
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
            maximum_valid_sample_gap_seconds=maximum_gap,
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
            transition_events=transition_events,
            transition_event_count=len(transition_events),
            transition_event_limit=self.transition_event_limit,
            transition_event_attempt_count=self.transition_event_attempt_count,
            transition_events_omitted=self.transition_events_omitted,
            transition_overflowed=self.transition_overflowed,
            transition_ledger_sha256=hashlib.sha256(transition_payload).hexdigest(),
            gap_start_event_count=event_counts["gap-start"],
            unavailable_event_count=event_counts["unavailable"],
            recovery_event_count=event_counts["recovery"],
            hard_failure_event_count=event_counts["hard-failure"],
        )
