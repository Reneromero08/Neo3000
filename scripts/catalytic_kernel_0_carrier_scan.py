#!/usr/bin/env python3
"""Deterministic public-only unresolved-support carrier selection for CK0.

The selector accepts public task projections only. It never consumes task
answers, hidden examples, hidden scores, or evaluator material.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from functools import lru_cache
from typing import Any, Mapping, Sequence

from catalytic_advantage_tasks import EXPECTED_SUITE_SHA256, build_frozen_task_suite


PROFILE_ID = "complementary-unresolved-public-v1"
SCAN_SCHEMA_VERSION = 1
FORBIDDEN_FIELDS = frozenset(
    {"hidden_examples", "answer_candidate_id", "hidden_score", "private_evaluator_data"}
)


class PublicCarrierScanError(ValueError):
    """The public carrier scan input or deterministic result is invalid."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest().upper()


def _reject_protected(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in FORBIDDEN_FIELDS:
                raise PublicCarrierScanError("protected data entered the public carrier scan")
            _reject_protected(item)
    elif isinstance(value, list):
        for item in value:
            _reject_protected(item)


def _execute(instructions: Sequence[Mapping[str, Any]], x: int) -> int:
    y = x
    for instruction in instructions:
        if not isinstance(instruction, Mapping):
            raise PublicCarrierScanError("candidate instruction is not an object")
        op = instruction.get("op")
        arg = instruction.get("arg")
        if op == "ADD" and isinstance(arg, int):
            y += arg
        elif op == "MUL" and isinstance(arg, int):
            y *= arg
        elif op == "NEG" and set(instruction) == {"op"}:
            y = -y
        elif op == "ABS" and set(instruction) == {"op"}:
            y = abs(y)
        elif op == "MOD" and isinstance(arg, int) and arg > 0:
            y %= arg
        else:
            raise PublicCarrierScanError("candidate instruction is outside the public DSL")
    return y


def _task_rows(projection: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    _reject_protected(projection)
    if set(projection) != {
        "task_id",
        "semantics",
        "public_examples",
        "candidates",
        "response_schema",
    }:
        raise PublicCarrierScanError("public task projection field set changed")
    examples = projection["public_examples"]
    candidates = projection["candidates"]
    if not isinstance(examples, list) or len(examples) != 5:
        raise PublicCarrierScanError("public task must contain exactly five examples")
    if not isinstance(candidates, list) or len(candidates) != 64:
        raise PublicCarrierScanError("public task must contain exactly 64 candidates")
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping) or set(candidate) != {
            "candidate_id",
            "instructions",
            "display",
        }:
            raise PublicCarrierScanError("public candidate projection field set changed")
        candidate_id = candidate["candidate_id"]
        if not isinstance(candidate_id, str):
            raise PublicCarrierScanError("public candidate ID is invalid")
        passes = []
        for example in examples:
            if not isinstance(example, Mapping) or set(example) != {"x", "y"}:
                raise PublicCarrierScanError("public example projection is invalid")
            passes.append(_execute(candidate["instructions"], example["x"]) == example["y"])
        rows.append({"candidate_id": candidate_id, "public_pass_vector": passes})
    rows.sort(key=lambda item: item["candidate_id"])
    if len({item["candidate_id"] for item in rows}) != 64:
        raise PublicCarrierScanError("public candidate IDs are not unique")
    return tuple(rows)


def _scores(
    rows: Sequence[Mapping[str, Any]], indices: Sequence[int]
) -> tuple[int, ...]:
    return tuple(sum(bool(row["public_pass_vector"][index]) for index in indices) for row in rows)


def _argmax_set(
    candidate_ids: Sequence[str], scores: Sequence[int]
) -> tuple[str, ...]:
    top = max(scores)
    return tuple(candidate_id for candidate_id, score in zip(candidate_ids, scores) if score == top)


def _plateau_gap(scores: Sequence[int]) -> int:
    top = max(scores)
    lower = [score for score in scores if score < top]
    return top - max(lower) if lower else 0


def _exclusive_contribution(
    *,
    rows: Sequence[Mapping[str, Any]],
    full_winner: str,
    other_branch_support: Sequence[str],
    exclusive_indices: Sequence[int],
) -> bool:
    by_id = {row["candidate_id"]: row for row in rows}
    winner_vector = by_id[full_winner]["public_pass_vector"]
    winner_score = sum(bool(winner_vector[index]) for index in exclusive_indices)
    return any(
        candidate_id != full_winner
        and winner_score
        > sum(
            bool(by_id[candidate_id]["public_pass_vector"][index])
            for index in exclusive_indices
        )
        for candidate_id in other_branch_support
    )


def _scan_profile(
    *,
    task_index: int,
    task_id: str,
    rows: Sequence[Mapping[str, Any]],
    branch_a: tuple[int, int, int],
    branch_b: tuple[int, int, int],
) -> dict[str, Any]:
    candidate_ids = tuple(row["candidate_id"] for row in rows)
    shared = tuple(sorted(set(branch_a) & set(branch_b)))
    if len(shared) != 1 or set(branch_a) | set(branch_b) != set(range(5)):
        raise PublicCarrierScanError("branch shard geometry is invalid")
    branch_a_scores = _scores(rows, branch_a)
    branch_b_scores = _scores(rows, branch_b)
    full_scores = _scores(rows, range(5))
    shared_scores = _scores(rows, shared)
    joint_scores = tuple(
        left + right - overlap
        for left, right, overlap in zip(branch_a_scores, branch_b_scores, shared_scores)
    )
    if joint_scores != full_scores:
        raise PublicCarrierScanError("deduplicated joint evidence differs from full public evidence")

    support_a = _argmax_set(candidate_ids, branch_a_scores)
    support_b = _argmax_set(candidate_ids, branch_b_scores)
    full_support = _argmax_set(candidate_ids, full_scores)
    joint_support = _argmax_set(candidate_ids, joint_scores)
    intersection = tuple(sorted(set(support_a) & set(support_b)))
    union = tuple(sorted(set(support_a) | set(support_b)))
    symmetric_difference = tuple(sorted(set(support_a) ^ set(support_b)))
    a_only = tuple(sorted(set(support_a) - set(support_b)))
    b_only = tuple(sorted(set(support_b) - set(support_a)))
    gap_a = _plateau_gap(branch_a_scores)
    gap_b = _plateau_gap(branch_b_scores)
    full_margin = _plateau_gap(full_scores)
    full_winner = full_support[0] if len(full_support) == 1 else None

    common_eligible = all(
        (
            2 <= len(support_a) <= 3,
            2 <= len(support_b) <= 3,
            support_a != support_b,
            bool(a_only),
            bool(b_only),
            len(full_support) == 1,
            full_winner in support_a if full_winner is not None else False,
            full_winner in support_b if full_winner is not None else False,
            gap_a > 0,
            gap_b > 0,
            branch_a_scores != branch_b_scores,
        )
    )
    tier: int | None = None
    contribution_a = False
    contribution_b = False
    if common_eligible and full_winner is not None:
        contribution_a = _exclusive_contribution(
            rows=rows,
            full_winner=full_winner,
            other_branch_support=support_b,
            exclusive_indices=tuple(sorted(set(branch_a) - set(branch_b))),
        )
        contribution_b = _exclusive_contribution(
            rows=rows,
            full_winner=full_winner,
            other_branch_support=support_a,
            exclusive_indices=tuple(sorted(set(branch_b) - set(branch_a))),
        )
        if intersection == full_support:
            tier = 1
        elif (
            set(full_support) < set(intersection)
            and joint_support == full_support
            and contribution_a
            and contribution_b
        ):
            tier = 2

    score_matrix = [
        {
            "candidate_id": candidate_id,
            "branch_a_score": branch_a_score,
            "branch_b_score": branch_b_score,
            "full_public_score": full_score,
            "public_pass_vector": list(row["public_pass_vector"]),
        }
        for row, candidate_id, branch_a_score, branch_b_score, full_score in zip(
            rows, candidate_ids, branch_a_scores, branch_b_scores, full_scores
        )
    ]
    return {
        "task_index": task_index,
        "task_id": task_id,
        "branch_a_indices": list(branch_a),
        "branch_b_indices": list(branch_b),
        "shared_index": shared[0],
        "support_a": list(support_a),
        "support_b": list(support_b),
        "full_support": list(full_support),
        "support_intersection": list(intersection),
        "support_union": list(union),
        "support_symmetric_difference": list(symmetric_difference),
        "support_a_only": list(a_only),
        "support_b_only": list(b_only),
        "branch_a_top_score": max(branch_a_scores),
        "branch_b_top_score": max(branch_b_scores),
        "branch_a_plateau_gap": gap_a,
        "branch_b_plateau_gap": gap_b,
        "full_public_margin": full_margin,
        "joint_public_support": list(joint_support),
        "branch_a_exclusive_contributes": contribution_a,
        "branch_b_exclusive_contributes": contribution_b,
        "score_vectors_differ": branch_a_scores != branch_b_scores,
        "public_score_matrix_sha256": _sha256(score_matrix),
        "eligible_tier": tier,
    }


def scan_public_projections(
    projections: Sequence[Mapping[str, Any]], *, task_suite_sha256: str
) -> dict[str, Any]:
    if task_suite_sha256 != EXPECTED_SUITE_SHA256:
        raise PublicCarrierScanError("task-suite identity drift")
    if len(projections) != 8:
        raise PublicCarrierScanError("frozen public scan requires exactly eight tasks")
    records: list[dict[str, Any]] = []
    task_rows: dict[str, tuple[dict[str, Any], ...]] = {}
    for task_index, projection in enumerate(projections):
        _reject_protected(projection)
        task_id = projection.get("task_id")
        if not isinstance(task_id, str) or task_id in task_rows:
            raise PublicCarrierScanError("public task identity is invalid")
        rows = _task_rows(projection)
        task_rows[task_id] = rows
        for branch_a in itertools.combinations(range(5), 3):
            missing = tuple(index for index in range(5) if index not in branch_a)
            for shared in branch_a:
                branch_b = tuple(sorted((shared, *missing)))
                records.append(
                    _scan_profile(
                        task_index=task_index,
                        task_id=task_id,
                        rows=rows,
                        branch_a=branch_a,
                        branch_b=branch_b,
                    )
                )
    if len(records) != 240:
        raise PublicCarrierScanError("public scan did not cover all 240 ordered shard pairs")

    scan_binding = {
        "schema_version": SCAN_SCHEMA_VERSION,
        "profile_id": PROFILE_ID,
        "task_suite_sha256": task_suite_sha256,
        "records": records,
    }
    eligible = [record for record in records if record["eligible_tier"] in {1, 2}]
    eligible.sort(
        key=lambda record: (
            record["eligible_tier"],
            len(record["support_a"]) + len(record["support_b"]),
            -len(record["support_symmetric_difference"]),
            -record["full_public_margin"],
            -min(record["branch_a_plateau_gap"], record["branch_b_plateau_gap"]),
            record["task_index"],
            tuple(record["branch_a_indices"]),
            tuple(record["branch_b_indices"]),
        )
    )
    if not eligible:
        raise PublicCarrierScanError("no eligible unresolved public carrier profile exists")
    selected = eligible[0]
    if selected["eligible_tier"] == 2 and any(
        record["eligible_tier"] == 1 for record in records
    ):
        raise PublicCarrierScanError("Tier 2 selected while a Tier-1 profile exists")

    profile = {
        "profile_id": PROFILE_ID,
        "task_suite_sha256": task_suite_sha256,
        "task_index": selected["task_index"],
        "task_id": selected["task_id"],
        "branch_shards": {
            "branch-a": [f"public-example-{index + 1}" for index in selected["branch_a_indices"]],
            "branch-b": [f"public-example-{index + 1}" for index in selected["branch_b_indices"]],
        },
        "branch_indices": {
            "branch-a": list(selected["branch_a_indices"]),
            "branch-b": list(selected["branch_b_indices"]),
        },
        "shared_calibration_example_id": f"public-example-{selected['shared_index'] + 1}",
        "eligibility_tier": selected["eligible_tier"],
        "public_argmax_sets": {
            "branch-a": list(selected["support_a"]),
            "branch-b": list(selected["support_b"]),
        },
        "full_public_argmax_set": list(selected["full_support"]),
        "public_top_scores": {
            "branch-a": selected["branch_a_top_score"],
            "branch-b": selected["branch_b_top_score"],
        },
        "public_plateau_gaps": {
            "branch-a": selected["branch_a_plateau_gap"],
            "branch-b": selected["branch_b_plateau_gap"],
        },
        "full_public_margin": selected["full_public_margin"],
        "support_intersection": list(selected["support_intersection"]),
        "support_union": list(selected["support_union"]),
        "support_symmetric_difference": list(selected["support_symmetric_difference"]),
        "support_exclusive": {
            "branch-a": list(selected["support_a_only"]),
            "branch-b": list(selected["support_b_only"]),
        },
        "joint_public_argmax_set": list(selected["joint_public_support"]),
        "branch_exclusive_contribution": {
            "branch-a": selected["branch_a_exclusive_contributes"],
            "branch-b": selected["branch_b_exclusive_contributes"],
        },
        "public_score_matrix_sha256": selected["public_score_matrix_sha256"],
        "scan_sha256": _sha256(scan_binding),
        "scan_population": {
            "tasks": len(projections),
            "ordered_shard_pairs": len(records),
            "tier_1_eligible": sum(record["eligible_tier"] == 1 for record in records),
            "tier_2_eligible": sum(record["eligible_tier"] == 2 for record in records),
        },
    }
    return {"profile": profile, "scan_sha256": profile["scan_sha256"]}


@lru_cache(maxsize=1)
def _frozen_selection_json() -> str:
    suite = build_frozen_task_suite()
    if suite.suite_sha256 != EXPECTED_SUITE_SHA256:
        raise PublicCarrierScanError("task-suite identity drift")
    projections = tuple(task.public_projection() for task in suite.tasks)
    selected = scan_public_projections(
        projections,
        task_suite_sha256=suite.suite_sha256,
    )
    return _canonical_bytes(selected).decode("utf-8")


def selected_unresolved_public_profile() -> dict[str, Any]:
    """Return a fresh copy of the one deterministic public-only selection."""
    return json.loads(_frozen_selection_json())["profile"]


__all__ = [
    "PROFILE_ID",
    "PublicCarrierScanError",
    "scan_public_projections",
    "selected_unresolved_public_profile",
]
