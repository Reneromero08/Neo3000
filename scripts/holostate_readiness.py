#!/usr/bin/env python3
"""HoloState readiness control without repeated listener-query subprocesses."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Callable

from listener_probe import ListenerOwnershipEvidence, qualify_listener_ownership


class HoloStateReadinessError(RuntimeError):
    """Raised when protected sidecar admission cannot be established."""


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

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["stable_pids"] = sorted(self.stable_pids)
        payload["stable_listener"] = self.stable_listener.to_dict()
        payload["sidecar_listener"] = self.sidecar_listener.to_dict()
        return payload


def _require_listener_evidence(label: str, evidence: ListenerOwnershipEvidence) -> None:
    if evidence.passed:
        return
    if evidence.hard_mismatch:
        raise HoloStateReadinessError(
            f"{label}-listener-pid-mismatch: expected {sorted(evidence.expected_pids)}, "
            f"actual {sorted(evidence.actual_pids)}"
        )
    raise HoloStateReadinessError(
        f"{label}-listener-query-unavailable: {evidence.final_error or 'unknown'}"
    )


def qualify_runtime_ownership(
    *,
    stable_port: int,
    stable_pids: set[int] | frozenset[int],
    sidecar_port: int,
    sidecar_pid: int,
    listener_qualifier: Callable[..., ListenerOwnershipEvidence] = qualify_listener_ownership,
    listener_kwargs: dict[str, Any] | None = None,
) -> tuple[ListenerOwnershipEvidence, ListenerOwnershipEvidence]:
    """Take fresh exact ownership samples at a meaningful control boundary."""
    options = dict(listener_kwargs or {})
    stable = listener_qualifier(stable_port, set(stable_pids), **options)
    _require_listener_evidence("stable", stable)
    sidecar = listener_qualifier(sidecar_port, {sidecar_pid}, **options)
    _require_listener_evidence("sidecar", sidecar)
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

    while True:
        polls += 1
        last_process_alive = process_alive()
        if not last_process_alive:
            raise HoloStateReadinessError("sidecar-process-exited-before-readiness")

        last_stable_health = stable_health_ok()
        if not last_stable_health:
            raise HoloStateReadinessError("stable-health-lost-before-readiness")

        failure = wddm_failure_reason()
        if failure:
            raise HoloStateReadinessError(failure)

        last_sidecar_health = sidecar_health_ok()
        last_wddm_attributed = wddm_has_valid_sample()
        if last_sidecar_health and last_wddm_attributed:
            break

        now = monotonic()
        if now >= deadline:
            raise HoloStateReadinessError("holostate-sidecar-readiness-timeout")
        sleep_fn(min(poll_interval_seconds, max(0.0, deadline - now)))

    stable_listener, sidecar_listener = qualify_runtime_ownership(
        stable_port=stable_port,
        stable_pids=stable,
        sidecar_port=sidecar_port,
        sidecar_pid=sidecar_pid,
        listener_qualifier=listener_qualifier,
        listener_kwargs=listener_kwargs,
    )
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
    )
