#!/usr/bin/env python3
"""Fail-closed runtime boundary helpers for CatalyticSwarm-1.

This module is deliberately pure. It performs no Git, process, model, network,
or filesystem operations. The protected controller supplies observations and
callbacks at the exact live boundaries.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Mapping, TypeVar


T = TypeVar("T")


class CatalyticSwarm1RuntimeSafetyError(RuntimeError):
    """A live CatalyticSwarm-1 stop law failed."""


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise CatalyticSwarm1RuntimeSafetyError(f"{label} is not text")
    return value


def require_custody_snapshot(
    expected: Mapping[str, Any],
    observed: Mapping[str, Any],
    *,
    boundary: str,
) -> dict[str, Any]:
    """Require exact stable and candidate custody at one live boundary."""
    required = ("stable", "candidate")
    if set(expected) != set(required) or set(observed) != set(required):
        raise CatalyticSwarm1RuntimeSafetyError(
            f"{boundary}: custody snapshot field set changed"
        )
    reasons: list[str] = []
    evidence: dict[str, str] = {}
    for name in required:
        expected_value = _required_text(expected[name], f"expected {name} custody")
        observed_value = _required_text(observed[name], f"observed {name} custody")
        evidence[f"{name}_snapshot"] = observed_value
        if observed_value != expected_value:
            reasons.append(f"{name}-custody-changed")
    result = {"passed": not reasons, "boundary": boundary, "reasons": reasons, **evidence}
    if reasons:
        raise CatalyticSwarm1RuntimeSafetyError(
            f"{boundary}: CatalyticSwarm-1 custody failed: {', '.join(reasons)}"
        )
    return result


def require_host_memory_growth(
    *,
    baseline_private_bytes: int,
    current_private_bytes: int,
    ceiling_bytes: int,
    boundary: str,
) -> dict[str, Any]:
    """Require bounded process-private growth after one live request."""
    for label, value in (
        ("baseline_private_bytes", baseline_private_bytes),
        ("current_private_bytes", current_private_bytes),
        ("ceiling_bytes", ceiling_bytes),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise CatalyticSwarm1RuntimeSafetyError(f"{boundary}: {label} is invalid")
    growth = max(0, current_private_bytes - baseline_private_bytes)
    result = {
        "passed": growth <= ceiling_bytes,
        "boundary": boundary,
        "baseline_private_bytes": baseline_private_bytes,
        "current_private_bytes": current_private_bytes,
        "growth_bytes": growth,
        "ceiling_bytes": ceiling_bytes,
    }
    if result["passed"] is not True:
        raise CatalyticSwarm1RuntimeSafetyError(
            f"{boundary}: host-private growth exceeded ceiling: {growth} > {ceiling_bytes}"
        )
    return result


def require_task_budget_parity(
    comparison: Any,
    *,
    ratio_limit: float,
) -> dict[str, Any]:
    """Require the already-computed per-task parity gate before another task."""
    if not isinstance(ratio_limit, (int, float)) or isinstance(ratio_limit, bool):
        raise CatalyticSwarm1RuntimeSafetyError("task parity ratio limit is invalid")
    ratio_limit = float(ratio_limit)
    if not math.isfinite(ratio_limit) or ratio_limit < 1.0:
        raise CatalyticSwarm1RuntimeSafetyError("task parity ratio limit is invalid")

    if isinstance(comparison, Mapping):
        getter = comparison.get
    else:
        getter = lambda name, default=None: getattr(comparison, name, default)

    passed = getter("budget_parity_passed")
    reasons = getter("budget_parity_reasons")
    ratios = {
        "fresh_prompt_ratio": getter("fresh_prompt_ratio"),
        "completion_ratio": getter("completion_ratio"),
        "total_model_token_ratio": getter("total_model_token_ratio"),
    }
    if type(passed) is not bool:
        raise CatalyticSwarm1RuntimeSafetyError("task parity flag is not boolean")
    if not isinstance(reasons, (list, tuple)) or any(
        not isinstance(item, str) for item in reasons
    ):
        raise CatalyticSwarm1RuntimeSafetyError("task parity reasons are malformed")
    malformed = [
        name
        for name, value in ratios.items()
        if not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or float(value) < 1.0
    ]
    if malformed:
        raise CatalyticSwarm1RuntimeSafetyError(
            "task parity ratios are malformed: " + ", ".join(malformed)
        )
    ratio_failures = [
        name for name, value in ratios.items() if float(value) > ratio_limit
    ]
    result = {
        "passed": passed and not ratio_failures and not reasons,
        "reasons": list(reasons),
        "ratio_limit": ratio_limit,
        **{name: float(value) for name, value in ratios.items()},
    }
    if result["passed"] is not True:
        detail = list(reasons) + [f"{name}-exceeded" for name in ratio_failures]
        raise CatalyticSwarm1RuntimeSafetyError(
            "CatalyticSwarm-1 task budget parity failed: "
            + ", ".join(detail or ["parity-flag-false"])
        )
    return result


def run_request_with_boundaries(
    *,
    before: Callable[[], Any],
    request: Callable[[], T],
    after: Callable[[], Any],
) -> T:
    """Run one request between mandatory pre/post observations.

    The post observation runs even when the request raises. If both operations
    fail, the request exception remains authoritative and the boundary failure
    is attached as a note rather than replacing completed-request evidence.
    """
    before()
    try:
        value = request()
    except BaseException as request_exc:
        try:
            after()
        except BaseException as boundary_exc:
            if hasattr(request_exc, "add_note"):
                request_exc.add_note(
                    "CatalyticSwarm-1 post-request boundary also failed: "
                    f"{boundary_exc}"
                )
        raise
    after()
    return value


def live_boundary_gate(
    stats: Mapping[str, Any],
    *,
    expected_custody_checks: int = 2064,
    expected_host_memory_checks: int = 1032,
    expected_task_parity_checks: int = 8,
) -> dict[str, Any]:
    """Reconcile exact successful-run boundary counts for terminal safety."""
    expected = {
        "custody_checks": expected_custody_checks,
        "host_memory_checks": expected_host_memory_checks,
        "task_parity_checks": expected_task_parity_checks,
    }
    observed: dict[str, int | None] = {}
    reasons: list[str] = []
    for name, required in expected.items():
        value = stats.get(name)
        if isinstance(required, bool) or not isinstance(required, int) or required < 0:
            raise CatalyticSwarm1RuntimeSafetyError(
                f"terminal expected count is invalid: {name}"
            )
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            observed[name] = None
            reasons.append(f"{name}-invalid")
        else:
            observed[name] = value
            if value != required:
                reasons.append(f"{name}-mismatch")
    return {
        "passed": not reasons,
        "reasons": reasons,
        "expected_custody_checks": expected_custody_checks,
        "expected_host_memory_checks": expected_host_memory_checks,
        "expected_task_parity_checks": expected_task_parity_checks,
        **stats,
        "observed_counts": observed,
    }


@dataclass
class ArmedCleanup:
    """Run one cleanup callback unless ownership transfers to a later finally."""

    cleanup: Callable[[], Any]
    armed: bool = True
    cleanup_result: Any = None

    def arm(self) -> None:
        self.armed = True

    def disarm(self) -> None:
        self.armed = False

    def run(self) -> Any:
        """Run the callback at most once and disarm before calling it."""
        if not self.armed:
            return self.cleanup_result
        self.armed = False
        self.cleanup_result = self.cleanup()
        return self.cleanup_result

    def __enter__(self) -> "ArmedCleanup":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        if self.armed:
            try:
                self.run()
            except BaseException as cleanup_exc:
                if exc is None:
                    raise CatalyticSwarm1RuntimeSafetyError(
                        f"CatalyticSwarm-1 cleanup callback failed: {cleanup_exc}"
                    ) from cleanup_exc
                if hasattr(exc, "add_note"):
                    exc.add_note(
                        f"CatalyticSwarm-1 cleanup callback also failed: {cleanup_exc}"
                    )
        return False
