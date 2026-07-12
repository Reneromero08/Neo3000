#!/usr/bin/env python3
"""Insertion-order-independent one-shot path custody for CS1-v4."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence


ONE_SHOT_KEYS = (
    "control",
    "readiness",
    "parser_canary",
    "attempt",
    "result",
    "ledger",
    "task_results",
)


class VersionedPathLawError(RuntimeError):
    """The active version's declared and runtime path maps do not agree."""


def normalized_relative_paths(value: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise VersionedPathLawError("one-shot paths must be a mapping")
    expected_keys = set(ONE_SHOT_KEYS)
    observed_keys = set(value)
    if len(value) != len(ONE_SHOT_KEYS) or observed_keys != expected_keys:
        missing = sorted(expected_keys - observed_keys)
        extra = sorted(str(key) for key in observed_keys - expected_keys)
        raise VersionedPathLawError(
            f"one-shot semantic key set changed: missing={missing}, extra={extra}"
        )
    result: dict[str, str] = {}
    for key in ONE_SHOT_KEYS:
        path = value[key]
        if not isinstance(path, str) or not path:
            raise VersionedPathLawError(f"one-shot path is invalid: {key}")
        normalized = path.replace("\\", "/")
        if normalized.startswith("/") or ".." in Path(normalized).parts:
            raise VersionedPathLawError(f"one-shot path escapes repository: {key}")
        result[key] = normalized
    return result


def qualify_versioned_one_shot_paths(
    *,
    repo_root: Path,
    contract_paths: Mapping[str, str],
    active_artifact_paths: Sequence[Path],
    required_namespace: str,
    forbidden_namespaces: Sequence[str] = (),
) -> dict[str, object]:
    declared = normalized_relative_paths(contract_paths)
    if len(active_artifact_paths) != len(ONE_SHOT_KEYS):
        raise VersionedPathLawError("active artifact path cardinality changed")

    namespace = required_namespace.replace("\\", "/").rstrip("/") + "/"
    forbidden = tuple(
        item.replace("\\", "/").rstrip("/") + "/"
        for item in forbidden_namespaces
    )
    for key in ONE_SHOT_KEYS:
        relative = declared[key]
        if not relative.startswith(namespace):
            raise VersionedPathLawError(
                f"active one-shot path is outside required namespace: {key}"
            )
        if any(relative.startswith(item) for item in forbidden):
            raise VersionedPathLawError(
                f"active one-shot path overlaps consumed namespace: {key}"
            )

    expected = {
        key: (repo_root / declared[key]).resolve()
        for key in ONE_SHOT_KEYS
    }
    actual = {
        key: Path(path).resolve()
        for key, path in zip(ONE_SHOT_KEYS, active_artifact_paths, strict=True)
    }
    if expected != actual:
        mismatches = [
            key for key in ONE_SHOT_KEYS if expected[key] != actual[key]
        ]
        raise VersionedPathLawError(
            "active one-shot runtime paths differ from active contract: "
            + ",".join(mismatches)
        )

    return {
        "passed": True,
        "namespace": namespace[:-1],
        "keys": list(ONE_SHOT_KEYS),
        "relative_paths": declared,
        "resolved_paths": {key: str(actual[key]) for key in ONE_SHOT_KEYS},
        "source_mapping_order_authoritative": False,
        "canonical_projection_order": list(ONE_SHOT_KEYS),
        "inherited_predecessor_map_consulted": False,
    }
