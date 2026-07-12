#!/usr/bin/env python3
"""Pure version-aware one-shot path qualification for CatalyticSwarm successors.

This module performs no filesystem writes, network access, model requests, process
launches, Git mutations, or claim changes.
"""

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
    if not isinstance(value, Mapping) or tuple(value) != ONE_SHOT_KEYS:
        raise VersionedPathLawError("one-shot key order or cardinality changed")
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
    """Validate the active contract against the active version's runtime paths.

    The caller must pass the path map and artifact tuple for the same version.
    No inherited v1 constant is consulted.
    """
    declared = normalized_relative_paths(contract_paths)
    if len(active_artifact_paths) != len(ONE_SHOT_KEYS):
        raise VersionedPathLawError("active artifact path cardinality changed")

    namespace = required_namespace.replace("\\", "/").rstrip("/") + "/"
    forbidden = tuple(
        item.replace("\\", "/").rstrip("/") + "/" for item in forbidden_namespaces
    )
    for key, relative in declared.items():
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
        "resolved_paths": {key: str(value) for key, value in actual.items()},
        "inherited_v1_map_consulted": False,
    }
