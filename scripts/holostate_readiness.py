#!/usr/bin/env python3
"""HoloState readiness control without repeated listener-query subprocesses."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Callable

from listener_probe import ListenerOwnershipEvidence, qualify_listener_ownership


class HoloStateReadinessError(RuntimeError):
    """Raised when protected sidecar admission cannot be established."""

    def __init__(self, message: str, *, evidence: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.evidence = dict(evidence or {})


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

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["stable_pids"] = sorted(self.stable_pids)
        payload["stable_listener"] = self.stable_listener.to_dict()
        payload["sidecar_listener"] = self.sidecar_listener.to_dict()
        payload["stable_listener_confirmation"] = self.stable_listener_confirmation.to_dict()
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
    listener_qualifier: Callable[..., ListenerOwnershipEvidence] = qualify_listener_ownership,
    listener_kwargs: dict[str, Any] | None = None,
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
