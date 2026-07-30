"""Validation helpers shared by declarative calibration specifications."""
from __future__ import annotations

from typing import Any


RESTORATION_SCOPE_KEYS = frozenset(
    {
        "cells",
        "metadata",
        "allocator",
        "model",
        "host_evidence",
        "cuda_kv",
        "closed_or_discarded",
    }
)


class SpecValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SpecValidationError(message)


def validate_restoration_scope(scope: Any) -> None:
    require(isinstance(scope, dict), "restoration_scope must be an object")
    require(
        set(scope) == RESTORATION_SCOPE_KEYS,
        "restoration_scope must name cells, metadata, allocator, model, "
        "host_evidence, cuda_kv, and closed_or_discarded",
    )
    require(
        all(isinstance(value, str) and value for value in scope.values()),
        "every restoration scope value must be explicit text",
    )


def validate_schedule(schedule: Any, expected_total: int, label: str) -> None:
    require(isinstance(schedule, list) and schedule, f"{label} must be a list")
    total = 0
    seen: set[str] = set()
    for entry in schedule:
        require(isinstance(entry, dict), f"{label} entry must be an object")
        require(
            set(entry) == {"label", "count", "route"},
            f"{label} entries require label/count/route",
        )
        require(
            isinstance(entry["label"], str) and entry["label"],
            f"{label} label is invalid",
        )
        require(entry["label"] not in seen, f"{label} labels must be unique")
        seen.add(entry["label"])
        require(
            isinstance(entry["count"], int) and entry["count"] > 0,
            f"{label} count is invalid",
        )
        require(
            isinstance(entry["route"], str) and entry["route"],
            f"{label} route is invalid",
        )
        total += entry["count"]
    require(total == expected_total, f"{label} total {total} != {expected_total}")
