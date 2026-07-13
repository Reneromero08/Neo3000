#!/usr/bin/env python3
"""HoloState readiness control without repeated listener-query subprocesses."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from listener_probe import ListenerOwnershipEvidence, qualify_listener_ownership


class HoloStateReadinessError(RuntimeError):
    """Raised when protected sidecar admission cannot be established."""

    def __init__(self, message: str, *, evidence: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.evidence = dict(evidence or {})


@dataclass(frozen=True)
class StableHealthRecoveryPolicy:
    """Optional startup-only recovery for bounded stable HTTP probe loss."""

    maximum_consecutive_failure_seconds: float = 15.0
    required_consecutive_successes: int = 3

    def __post_init__(self) -> None:
        if self.maximum_consecutive_failure_seconds <= 0:
            raise ValueError("stable-health recovery window must be positive")
        if self.required_consecutive_successes <= 0:
            raise ValueError("stable-health recovery success count must be positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HoloStateReadinessEvidence:
    passed: bool
    sidecar_pid: int
    stable_pids: frozenset[int]
    poll_count: int
    readiness_seconds: float
    process_alive: bool
    stable_health_ok: bool
    sidecar_health_ok: bool
    wddm_attributed: bool
    stable_listener: ListenerOwnershipEvidence
    sidecar_listener: ListenerOwnershipEvidence
    stable_listener_confirmation: ListenerOwnershipEvidence
    stable_health_recovery: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["stable_pids"] = sorted(self.stable_pids)
        payload["stable_listener"] = self.stable_listener.to_dict()
        payload["sidecar_listener"] = self.sidecar_listener.to_dict()
        payload["stable_listener_confirmation"] = self.stable_listener_confirmation.to_dict()
        if not self.stable_health_recovery:
            payload.pop("stable_health_recovery", None)
        return payload


def _require_listener_evidence(label: str, evidence: ListenerOwnershipEvidence) -> None:
    if evidence.passed:
        return
    if evidence.hard_mismatch:
        raise HoloStateReadinessError(
            f"{label}-listener-pid-mismatch: expected {sorted(evidence.expected_pids)}, "
            f"actual {sorted(evidence.actual_pids)}",
            evidence={f"{label}_listener": evidence.to_dict()},
        )
    raise HoloStateReadinessError(
        f"{label}-listener-query-unavailable: {evidence.final_error or 'unknown'}",
        evidence={f"{label}_listener": evidence.to_dict()},
    )


def qualify_runtime_ownership(
    *,
    stable_port: int,
    stable_pids: set[int] | frozenset[int],
    sidecar_port: int,
    sidecar_pid: int | None = None,
    sidecar_pids: set[int] | frozenset[int] | None = None,
    listener_qualifier: Callable[..., ListenerOwnershipEvidence] = qualify_listener_ownership,
    listener_kwargs: dict[str, Any] | None = None,
    deadline_at: float | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> tuple[ListenerOwnershipEvidence, ListenerOwnershipEvidence]:
    """Take fresh exact ownership samples at a meaningful control boundary."""
    if (sidecar_pid is None) == (sidecar_pids is None):
        raise ValueError("provide exactly one of sidecar_pid or sidecar_pids")
    expected_sidecar = {sidecar_pid} if sidecar_pid is not None else set(sidecar_pids or set())
    if any(pid is None or pid <= 0 for pid in expected_sidecar):
        raise ValueError("sidecar PID set must contain only positive integers")
    base_options = dict(listener_kwargs or {})
    total_window = base_options.pop("maximum_total_query_window_seconds", None)
    if total_window is not None:
        total_window = float(total_window)
        if total_window <= 0:
            raise ValueError("maximum total listener-query window must be positive")
        total_deadline = monotonic() + total_window
        deadline_at = total_deadline if deadline_at is None else min(deadline_at, total_deadline)

    def bounded_options() -> dict[str, Any]:
        options = dict(base_options)
        if deadline_at is not None:
            remaining = deadline_at - monotonic()
            if remaining <= 0:
                raise HoloStateReadinessError("holostate-listener-qualification-timeout")
            configured = float(options.get("max_window_seconds", remaining))
            options["max_window_seconds"] = min(configured, remaining)
        return options

    stable = listener_qualifier(stable_port, set(stable_pids), **bounded_options())
    _require_listener_evidence("stable", stable)
    try:
        sidecar = listener_qualifier(sidecar_port, expected_sidecar, **bounded_options())
        _require_listener_evidence("sidecar", sidecar)
    except HoloStateReadinessError as exc:
        raise HoloStateReadinessError(
            str(exc),
            evidence={"stable_listener": stable.to_dict(), **exc.evidence},
        ) from exc
    return stable, sidecar


def wait_for_holostate_readiness(
    *,
    sidecar_pid: int,
    stable_pids: set[int] | frozenset[int],
    stable_port: int,
    sidecar_port: int,
    deadline_seconds: float,
    process_alive: Callable[[], bool],
    stable_health_ok: Callable[[], bool],
    sidecar_health_ok: Callable[[], bool],
    wddm_has_valid_sample: Callable[[], bool],
    wddm_failure_reason: Callable[[], str | None],
    wddm_has_fresh_valid_sample: Callable[[], bool] | None = None,
    wddm_snapshot: Callable[[], dict[str, Any]] | None = None,
    listener_qualifier: Callable[..., ListenerOwnershipEvidence] = qualify_listener_ownership,
    listener_kwargs: dict[str, Any] | None = None,
    stable_health_recovery_policy: StableHealthRecoveryPolicy | None = None,
    stable_process_alive: Callable[[], bool] | None = None,
    stable_listener_ownership: Callable[[], ListenerOwnershipEvidence] | None = None,
    poll_interval_seconds: float = 0.25,
    monotonic: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> HoloStateReadinessEvidence:
    """Wait for load/health/WDDM, then perform one fresh listener qualification.

    Listener ownership is deliberately absent from the high-frequency loading
    loop. Exact listener samples are taken only after every cheaper readiness
    condition is satisfied.
    """
    if sidecar_pid <= 0:
        raise ValueError("sidecar_pid must be positive")
    stable = frozenset(stable_pids)
    if not stable or any(pid <= 0 for pid in stable):
        raise ValueError("stable_pids must contain positive integers")
    if deadline_seconds <= 0 or poll_interval_seconds <= 0:
        raise ValueError("readiness timing values must be positive")

    if stable_health_recovery_policy is not None:
        if stable_process_alive is None or stable_listener_ownership is None:
            raise ValueError(
                "startup stable-health recovery requires stable process and listener checks"
            )
        if wddm_has_fresh_valid_sample is not None:
            raise ValueError(
                "startup stable-health recovery is not defined for resilient WDDM readiness"
            )
        return _wait_for_startup_health_recovery_readiness(
            sidecar_pid=sidecar_pid,
            stable_pids=stable,
            stable_port=stable_port,
            sidecar_port=sidecar_port,
            deadline_seconds=deadline_seconds,
            process_alive=process_alive,
            stable_process_alive=stable_process_alive,
            stable_listener_ownership=stable_listener_ownership,
            stable_health_ok=stable_health_ok,
            sidecar_health_ok=sidecar_health_ok,
            wddm_has_valid_sample=wddm_has_valid_sample,
            wddm_failure_reason=wddm_failure_reason,
            listener_qualifier=listener_qualifier,
            listener_kwargs=listener_kwargs,
            policy=stable_health_recovery_policy,
            poll_interval_seconds=poll_interval_seconds,
            monotonic=monotonic,
            sleep_fn=sleep_fn,
        )

    if wddm_has_fresh_valid_sample is not None:
        return _wait_for_resilient_holostate_readiness(
            sidecar_pid=sidecar_pid,
            stable_pids=stable,
            stable_port=stable_port,
            sidecar_port=sidecar_port,
            deadline_seconds=deadline_seconds,
            process_alive=process_alive,
            stable_health_ok=stable_health_ok,
            sidecar_health_ok=sidecar_health_ok,
            wddm_has_fresh_valid_sample=wddm_has_fresh_valid_sample,
            wddm_failure_reason=wddm_failure_reason,
            wddm_snapshot=wddm_snapshot,
            listener_qualifier=listener_qualifier,
            listener_kwargs=listener_kwargs,
            poll_interval_seconds=poll_interval_seconds,
            monotonic=monotonic,
            sleep_fn=sleep_fn,
        )

    started = monotonic()
    deadline = started + deadline_seconds
    polls = 0
    last_process_alive = False
    last_stable_health = False
    last_sidecar_health = False
    last_wddm_attributed = False

    def fail(reason: str, *, extra: dict[str, Any] | None = None) -> None:
        raise HoloStateReadinessError(
            reason,
            evidence={
                "poll_count": polls,
                "readiness_seconds": max(0.0, monotonic() - started),
                "process_alive": last_process_alive,
                "stable_health_ok": last_stable_health,
                "sidecar_health_ok": last_sidecar_health,
                "wddm_attributed": last_wddm_attributed,
                **(extra or {}),
            },
        )

    while True:
        polls += 1
        last_process_alive = process_alive()
        if not last_process_alive:
            fail("sidecar-process-exited-before-readiness")

        last_stable_health = stable_health_ok()
        if not last_stable_health:
            fail("stable-health-lost-before-readiness")

        failure = wddm_failure_reason()
        if failure:
            fail(failure)

        last_sidecar_health = sidecar_health_ok()
        last_wddm_attributed = wddm_has_valid_sample()
        now = monotonic()
        if last_sidecar_health and last_wddm_attributed:
            if now >= deadline:
                fail("holostate-sidecar-readiness-timeout")
            break
        if now >= deadline:
            fail("holostate-sidecar-readiness-timeout")
        sleep_fn(min(poll_interval_seconds, max(0.0, deadline - now)))

    listener_options = dict(listener_kwargs or {})
    maximum_total_window = listener_options.pop("maximum_total_query_window_seconds", None)
    ownership_deadline = deadline
    if maximum_total_window is not None:
        maximum_total_window = float(maximum_total_window)
        if maximum_total_window <= 0:
            raise ValueError("maximum total listener-query window must be positive")
        ownership_deadline = min(deadline, monotonic() + maximum_total_window)

    try:
        stable_listener, sidecar_listener = qualify_runtime_ownership(
            stable_port=stable_port,
            stable_pids=stable,
            sidecar_port=sidecar_port,
            sidecar_pid=sidecar_pid,
            listener_qualifier=listener_qualifier,
            listener_kwargs=listener_options,
            deadline_at=ownership_deadline,
            monotonic=monotonic,
        )
    except HoloStateReadinessError as exc:
        fail(str(exc), extra=exc.evidence)

    last_process_alive = process_alive()
    last_stable_health = stable_health_ok()
    last_sidecar_health = sidecar_health_ok()
    failure = wddm_failure_reason()
    last_wddm_attributed = wddm_has_valid_sample()
    if not last_process_alive:
        fail("sidecar-process-exited-during-listener-qualification")
    if not last_stable_health:
        fail("stable-health-lost-during-listener-qualification")
    if not last_sidecar_health:
        fail("sidecar-health-lost-during-listener-qualification")
    if failure:
        fail(failure)
    if not last_wddm_attributed:
        fail("candidate-vram-attribution-lost-during-listener-qualification")

    remaining = ownership_deadline - monotonic()
    if remaining <= 0:
        fail("holostate-listener-qualification-timeout")
    confirmation_options = dict(listener_options)
    confirmation_options["max_window_seconds"] = min(
        float(confirmation_options.get("max_window_seconds", remaining)),
        remaining,
    )
    stable_listener_confirmation = listener_qualifier(
        stable_port,
        set(stable),
        **confirmation_options,
    )
    try:
        _require_listener_evidence("stable_confirmation", stable_listener_confirmation)
    except HoloStateReadinessError as exc:
        fail(
            str(exc),
            extra={
                "stable_listener": stable_listener.to_dict(),
                "sidecar_listener": sidecar_listener.to_dict(),
                **exc.evidence,
            },
        )

    last_process_alive = process_alive()
    last_stable_health = stable_health_ok()
    last_sidecar_health = sidecar_health_ok()
    failure = wddm_failure_reason()
    last_wddm_attributed = wddm_has_valid_sample()
    if not last_process_alive:
        fail("sidecar-process-exited-after-listener-qualification")
    if not last_stable_health:
        fail("stable-health-lost-after-listener-qualification")
    if not last_sidecar_health:
        fail("sidecar-health-lost-after-listener-qualification")
    if failure:
        fail(failure)
    if not last_wddm_attributed:
        fail("candidate-vram-attribution-lost-after-listener-qualification")
    return HoloStateReadinessEvidence(
        True,
        sidecar_pid,
        stable,
        polls,
        max(0.0, monotonic() - started),
        last_process_alive,
        last_stable_health,
        last_sidecar_health,
        last_wddm_attributed,
        stable_listener,
        sidecar_listener,
        stable_listener_confirmation,
    )


def _wait_for_startup_health_recovery_readiness(
    *,
    sidecar_pid: int,
    stable_pids: frozenset[int],
    stable_port: int,
    sidecar_port: int,
    deadline_seconds: float,
    process_alive: Callable[[], bool],
    stable_process_alive: Callable[[], bool],
    stable_listener_ownership: Callable[[], ListenerOwnershipEvidence],
    stable_health_ok: Callable[[], bool],
    sidecar_health_ok: Callable[[], bool],
    wddm_has_valid_sample: Callable[[], bool],
    wddm_failure_reason: Callable[[], str | None],
    listener_qualifier: Callable[..., ListenerOwnershipEvidence],
    listener_kwargs: dict[str, Any] | None,
    policy: StableHealthRecoveryPolicy,
    poll_interval_seconds: float,
    monotonic: Callable[[], float],
    sleep_fn: Callable[[float], None],
) -> HoloStateReadinessEvidence:
    """Keep identity strict while allowing only bounded startup HTTP recovery."""

    started = monotonic()
    deadline = started + deadline_seconds
    polls = 0
    stable_pid_checks = 0
    stable_listener_checks = 0
    health_attempts = 0
    failed_health_probes = 0
    recovery_events = 0
    consecutive_successes = 0
    first_failure_elapsed: float | None = None
    last_failure_elapsed: float | None = None
    failure_streak_started: float | None = None
    maximum_failure_duration = 0.0
    last_recovery_duration = 0.0
    last_process_alive = False
    last_stable_process_alive = False
    last_stable_listener: ListenerOwnershipEvidence | None = None
    last_stable_health = False
    last_sidecar_health = False
    last_wddm_attributed = False

    def recovery_metadata(now: float | None = None) -> dict[str, Any]:
        observed = monotonic() if now is None else now
        current_duration = (
            max(0.0, observed - failure_streak_started)
            if failure_streak_started is not None
            else 0.0
        )
        return {
            "enabled": True,
            "policy": policy.to_dict(),
            "stable_health_probe_attempts": health_attempts,
            "failed_stable_health_probes": failed_health_probes,
            "recovery_events": recovery_events,
            "first_failure_elapsed_seconds": (
                round(first_failure_elapsed, 6)
                if first_failure_elapsed is not None
                else None
            ),
            "last_failure_elapsed_seconds": (
                round(last_failure_elapsed, 6)
                if last_failure_elapsed is not None
                else None
            ),
            "maximum_consecutive_failure_duration_seconds": round(
                max(maximum_failure_duration, current_duration), 6
            ),
            "last_recovery_duration_seconds": round(last_recovery_duration, 6),
            "consecutive_successes_before_admission": consecutive_successes,
            "stable_pid_checks": stable_pid_checks,
            "stable_listener_checks": stable_listener_checks,
            "stable_pid_preserved": last_stable_process_alive,
            "stable_listener_preserved": bool(
                last_stable_listener is not None and last_stable_listener.passed
            ),
            "final_stable_health_ok": last_stable_health,
        }

    def fail(reason: str, *, extra: dict[str, Any] | None = None) -> None:
        raise HoloStateReadinessError(
            reason,
            evidence={
                "poll_count": polls,
                "readiness_seconds": max(0.0, monotonic() - started),
                "process_alive": last_process_alive,
                "stable_health_ok": last_stable_health,
                "sidecar_health_ok": last_sidecar_health,
                "wddm_attributed": last_wddm_attributed,
                "stable_health_recovery": recovery_metadata(),
                **(extra or {}),
            },
        )

    def check_stable_identity() -> None:
        nonlocal stable_pid_checks, stable_listener_checks
        nonlocal last_stable_process_alive, last_stable_listener
        stable_pid_checks += 1
        last_stable_process_alive = stable_process_alive()
        if not last_stable_process_alive:
            fail("stable-pid-lost-before-readiness")
        stable_listener_checks += 1
        try:
            last_stable_listener = stable_listener_ownership()
            _require_listener_evidence("stable_startup", last_stable_listener)
        except HoloStateReadinessError as exc:
            fail(str(exc), extra=exc.evidence)

    def probe_stable_health() -> bool:
        nonlocal health_attempts, failed_health_probes, recovery_events
        nonlocal consecutive_successes, first_failure_elapsed, last_failure_elapsed
        nonlocal failure_streak_started, maximum_failure_duration
        nonlocal last_recovery_duration, last_stable_health
        health_attempts += 1
        probe_started = monotonic()
        last_stable_health = stable_health_ok()
        now = monotonic()
        if last_stable_health:
            if failure_streak_started is not None:
                duration = max(0.0, now - failure_streak_started)
                maximum_failure_duration = max(maximum_failure_duration, duration)
                last_recovery_duration = duration
                recovery_events += 1
                failure_streak_started = None
            consecutive_successes += 1
            return True

        failed_health_probes += 1
        consecutive_successes = 0
        elapsed = max(0.0, probe_started - started)
        if first_failure_elapsed is None:
            first_failure_elapsed = elapsed
        last_failure_elapsed = max(0.0, now - started)
        if failure_streak_started is None:
            failure_streak_started = probe_started
        duration = max(0.0, now - failure_streak_started)
        maximum_failure_duration = max(maximum_failure_duration, duration)
        if duration > policy.maximum_consecutive_failure_seconds:
            fail("stable-health-recovery-timeout")
        return False

    def refresh_loading_conditions() -> float:
        nonlocal polls, last_process_alive, last_sidecar_health, last_wddm_attributed
        polls += 1
        last_process_alive = process_alive()
        if not last_process_alive:
            fail("sidecar-process-exited-before-readiness")
        check_stable_identity()
        stable_health = probe_stable_health()
        failure = wddm_failure_reason()
        if failure:
            fail(failure)
        last_sidecar_health = sidecar_health_ok()
        last_wddm_attributed = wddm_has_valid_sample()
        now = monotonic()
        if now >= deadline:
            fail("holostate-sidecar-readiness-timeout")
        if (
            stable_health
            and last_sidecar_health
            and last_wddm_attributed
            and consecutive_successes >= policy.required_consecutive_successes
        ):
            return now
        sleep_fn(min(poll_interval_seconds, max(0.0, deadline - now)))
        return now

    listener_options = dict(listener_kwargs or {})
    maximum_total_window = listener_options.pop(
        "maximum_total_query_window_seconds", None
    )
    while True:
        while True:
            refresh_loading_conditions()
            if (
                last_stable_health
                and last_sidecar_health
                and last_wddm_attributed
                and consecutive_successes >= policy.required_consecutive_successes
            ):
                break

        ownership_deadline = deadline
        if maximum_total_window is not None:
            total_window = float(maximum_total_window)
            if total_window <= 0:
                raise ValueError("maximum total listener-query window must be positive")
            ownership_deadline = min(deadline, monotonic() + total_window)
        try:
            stable_listener, sidecar_listener = qualify_runtime_ownership(
                stable_port=stable_port,
                stable_pids=stable_pids,
                sidecar_port=sidecar_port,
                sidecar_pid=sidecar_pid,
                listener_qualifier=listener_qualifier,
                listener_kwargs=listener_options,
                deadline_at=ownership_deadline,
                monotonic=monotonic,
            )
        except HoloStateReadinessError as exc:
            fail(str(exc), extra=exc.evidence)

        last_process_alive = process_alive()
        if not last_process_alive:
            fail("sidecar-process-exited-during-listener-qualification")
        check_stable_identity()
        if not probe_stable_health():
            continue
        last_sidecar_health = sidecar_health_ok()
        last_wddm_attributed = wddm_has_valid_sample()
        failure = wddm_failure_reason()
        if not last_sidecar_health:
            fail("sidecar-health-lost-during-listener-qualification")
        if failure:
            fail(failure)
        if not last_wddm_attributed:
            fail("candidate-vram-attribution-lost-during-listener-qualification")

        remaining = ownership_deadline - monotonic()
        if remaining <= 0:
            fail("holostate-listener-qualification-timeout")
        confirmation_options = dict(listener_options)
        confirmation_options["max_window_seconds"] = min(
            float(confirmation_options.get("max_window_seconds", remaining)),
            remaining,
        )
        stable_listener_confirmation = listener_qualifier(
            stable_port,
            set(stable_pids),
            **confirmation_options,
        )
        try:
            _require_listener_evidence(
                "stable_confirmation", stable_listener_confirmation
            )
        except HoloStateReadinessError as exc:
            fail(
                str(exc),
                extra={
                    "stable_listener": stable_listener.to_dict(),
                    "sidecar_listener": sidecar_listener.to_dict(),
                    **exc.evidence,
                },
            )

        last_process_alive = process_alive()
        if not last_process_alive:
            fail("sidecar-process-exited-after-listener-qualification")
        check_stable_identity()
        if not probe_stable_health():
            continue
        last_sidecar_health = sidecar_health_ok()
        last_wddm_attributed = wddm_has_valid_sample()
        failure = wddm_failure_reason()
        if not last_sidecar_health:
            fail("sidecar-health-lost-after-listener-qualification")
        if failure:
            fail(failure)
        if not last_wddm_attributed:
            fail("candidate-vram-attribution-lost-after-listener-qualification")
        if consecutive_successes < policy.required_consecutive_successes:
            continue
        recovery = recovery_metadata()
        recovery["stable_pid_preserved"] = True
        recovery["stable_listener_preserved"] = True
        recovery["final_stable_health_ok"] = True
        return HoloStateReadinessEvidence(
            True,
            sidecar_pid,
            stable_pids,
            polls,
            max(0.0, monotonic() - started),
            last_process_alive,
            last_stable_health,
            last_sidecar_health,
            last_wddm_attributed,
            stable_listener,
            sidecar_listener,
            stable_listener_confirmation,
            recovery,
        )


def _wait_for_resilient_holostate_readiness(
    *,
    sidecar_pid: int,
    stable_pids: frozenset[int],
    stable_port: int,
    sidecar_port: int,
    deadline_seconds: float,
    process_alive: Callable[[], bool],
    stable_health_ok: Callable[[], bool],
    sidecar_health_ok: Callable[[], bool],
    wddm_has_fresh_valid_sample: Callable[[], bool],
    wddm_failure_reason: Callable[[], str | None],
    wddm_snapshot: Callable[[], dict[str, Any]] | None,
    listener_qualifier: Callable[..., ListenerOwnershipEvidence],
    listener_kwargs: dict[str, Any] | None,
    poll_interval_seconds: float,
    monotonic: Callable[[], float],
    sleep_fn: Callable[[float], None],
) -> HoloStateReadinessEvidence:
    """Admit only a fresh exact-PID sample and requalify after transient gaps.

    Listener subprocesses remain outside the model-load poll loop.  If WDDM
    freshness is lost while the bounded listener queries are running, the
    method waits for recovery using cheap health/process checks and repeats the
    complete listener qualification before admission.
    """

    started = monotonic()
    deadline = started + deadline_seconds
    polls = 0
    last_process_alive = False
    last_stable_health = False
    last_sidecar_health = False
    last_wddm_fresh = False

    def fail(reason: str, *, extra: dict[str, Any] | None = None) -> None:
        snapshot: dict[str, Any] | None = None
        if wddm_snapshot is not None:
            try:
                snapshot = dict(wddm_snapshot())
            except Exception as exc:  # pragma: no cover - defensive evidence path
                snapshot = {"snapshot_error": str(exc)}
        raise HoloStateReadinessError(
            reason,
            evidence={
                "poll_count": polls,
                "readiness_seconds": max(0.0, monotonic() - started),
                "process_alive": last_process_alive,
                "stable_health_ok": last_stable_health,
                "sidecar_health_ok": last_sidecar_health,
                "wddm_attributed": last_wddm_fresh,
                "wddm_fresh": last_wddm_fresh,
                "wddm_snapshot": snapshot,
                **(extra or {}),
            },
        )

    def refresh_cheap_conditions() -> float:
        nonlocal polls, last_process_alive, last_stable_health
        nonlocal last_sidecar_health, last_wddm_fresh
        polls += 1
        last_process_alive = process_alive()
        if not last_process_alive:
            fail("sidecar-process-exited-before-readiness")
        last_stable_health = stable_health_ok()
        if not last_stable_health:
            fail("stable-health-lost-before-readiness")
        failure = wddm_failure_reason()
        if failure:
            fail(failure)
        last_sidecar_health = sidecar_health_ok()
        last_wddm_fresh = wddm_has_fresh_valid_sample()
        return monotonic()

    def wait_until_fresh() -> None:
        while True:
            now = refresh_cheap_conditions()
            if last_sidecar_health and last_wddm_fresh:
                if now >= deadline:
                    fail("holostate-sidecar-readiness-timeout")
                return
            if now >= deadline:
                fail("holostate-sidecar-readiness-timeout")
            sleep_fn(min(poll_interval_seconds, max(0.0, deadline - now)))

    listener_options = dict(listener_kwargs or {})
    maximum_total_window = listener_options.pop(
        "maximum_total_query_window_seconds", None
    )
    while True:
        wait_until_fresh()
        ownership_deadline = deadline
        if maximum_total_window is not None:
            total_window = float(maximum_total_window)
            if total_window <= 0:
                raise ValueError("maximum total listener-query window must be positive")
            ownership_deadline = min(deadline, monotonic() + total_window)

        try:
            stable_listener, sidecar_listener = qualify_runtime_ownership(
                stable_port=stable_port,
                stable_pids=stable_pids,
                sidecar_port=sidecar_port,
                sidecar_pid=sidecar_pid,
                listener_qualifier=listener_qualifier,
                listener_kwargs=listener_options,
                deadline_at=ownership_deadline,
                monotonic=monotonic,
            )
        except HoloStateReadinessError as exc:
            fail(str(exc), extra=exc.evidence)

        refresh_cheap_conditions()
        if not last_sidecar_health:
            fail("sidecar-health-lost-during-listener-qualification")
        if not last_wddm_fresh:
            # A bounded transient gap is not a rejection.  Recover first, then
            # repeat both listener samples so admission evidence is fresh as a
            # single boundary.
            continue

        remaining = ownership_deadline - monotonic()
        if remaining <= 0:
            fail("holostate-listener-qualification-timeout")
        confirmation_options = dict(listener_options)
        confirmation_options["max_window_seconds"] = min(
            float(confirmation_options.get("max_window_seconds", remaining)),
            remaining,
        )
        stable_listener_confirmation = listener_qualifier(
            stable_port,
            set(stable_pids),
            **confirmation_options,
        )
        try:
            _require_listener_evidence(
                "stable_confirmation", stable_listener_confirmation
            )
        except HoloStateReadinessError as exc:
            fail(
                str(exc),
                extra={
                    "stable_listener": stable_listener.to_dict(),
                    "sidecar_listener": sidecar_listener.to_dict(),
                    **exc.evidence,
                },
            )

        refresh_cheap_conditions()
        if not last_sidecar_health:
            fail("sidecar-health-lost-after-listener-qualification")
        if not last_wddm_fresh:
            continue
        return HoloStateReadinessEvidence(
            True,
            sidecar_pid,
            stable_pids,
            polls,
            max(0.0, monotonic() - started),
            last_process_alive,
            last_stable_health,
            last_sidecar_health,
            True,
            stable_listener,
            sidecar_listener,
            stable_listener_confirmation,
        )
