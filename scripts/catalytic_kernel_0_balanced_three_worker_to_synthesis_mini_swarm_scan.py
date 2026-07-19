#!/usr/bin/env python3
"""Public-only availability scan for the three-worker synthesis mini-swarm.

This module deliberately stops before private binding, tokenizer, hidden utility,
authority, or runtime construction when the frozen CatalyticSwarm-1 corpus lacks
the required three-worker support geometry.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import catalytic_advantage_tasks as task_suite


DESIGN_ID = "balanced-opaque-three-worker-to-synthesis-mini-swarm-v1"
SCAN_ID = f"{DESIGN_ID}-public-geometry-scan-1"
STARTING_COMMIT = "6c760b2d5f8296f795724d061f1d91a0e4171c27"
EXPECTED_SUITE_SHA256 = (
    "4B9961D5054BE5D98EF315D2DEAE9D1604E0042A69CB02A8B81FDF513BC1FC92"
)
CLASSIFICATION = "EXISTING_CORPUS_THREE_WORKER_GEOMETRY_UNAVAILABLE"
ARTIFACT_RELATIVE_PATH = (
    "lab/ck0_balanced_opaque_three_worker_to_synthesis_mini_swarm_v1_"
    "geometry_scan_1.json"
)
NEXT_BOUNDARY = (
    "SEPARATELY_AUTHORIZE_A_STATIC_SCIENTIFIC_DECISION_ON_WORKER_GEOMETRY_"
    "CORPUS_COMPATIBILITY"
)
WORKER_ROLES = ("worker-A", "worker-B", "worker-C")
SHARD_SIZE = 3
REQUIRED_LOCAL_SHARDS = 3
_INTERNAL_CANDIDATE_PATTERN = re.compile(r"\bC\d{2}\b")
_FORBIDDEN_PUBLIC_KEYS = {
    "answer_candidate_id",
    "candidate_id",
    "candidates",
    "hidden_examples",
    "private_alias",
    "private_mapping",
    "private_root",
    "public_examples",
    "selected_task_id",
    "support_candidate_ids",
    "worker_support_identities",
}


class WorkerGeometryScanError(RuntimeError):
    """The frozen public scan or diagnostic boundary changed."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_json_text(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def json_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise WorkerGeometryScanError(message)


def _execute_public_program(candidate: Mapping[str, Any], x: int) -> int:
    """Execute only the candidate body supplied by the public projection."""
    instructions = candidate.get("instructions")
    _require(isinstance(instructions, list) and len(instructions) == 5, "public program changed")
    value = x
    for instruction in instructions:
        _require(isinstance(instruction, dict), "public instruction changed")
        op = instruction.get("op")
        arg = instruction.get("arg")
        if op == "ADD" and isinstance(arg, int) and not isinstance(arg, bool):
            value += arg
        elif op == "MUL" and isinstance(arg, int) and not isinstance(arg, bool):
            value *= arg
        elif op == "NEG" and set(instruction) == {"op"}:
            value = -value
        elif op == "ABS" and set(instruction) == {"op"}:
            value = abs(value)
        elif op == "MOD" and isinstance(arg, int) and not isinstance(arg, bool) and arg > 0:
            value %= arg
        else:
            raise WorkerGeometryScanError("public instruction is invalid")
        _require(abs(value) <= 1_000_000, "public program escaped bounded range")
    return value


def _score_rows(
    projection: Mapping[str, Any], example_indices: Sequence[int]
) -> list[dict[str, Any]]:
    examples = projection.get("public_examples")
    candidates = projection.get("candidates")
    _require(isinstance(examples, list) and len(examples) == 5, "public examples changed")
    _require(isinstance(candidates, list) and len(candidates) == 64, "public candidates changed")
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        _require(isinstance(candidate, dict), "public candidate changed")
        candidate_id = candidate.get("candidate_id")
        _require(
            isinstance(candidate_id, str) and _INTERNAL_CANDIDATE_PATTERN.fullmatch(candidate_id),
            "public candidate identity changed",
        )
        pass_vector = []
        for index in example_indices:
            example = examples[index]
            _require(
                isinstance(example, dict)
                and set(example) == {"x", "y"}
                and isinstance(example["x"], int)
                and isinstance(example["y"], int),
                "public example changed",
            )
            pass_vector.append(
                _execute_public_program(candidate, example["x"]) == example["y"]
            )
        rows.append(
            {
                "candidate_id": candidate_id,
                "pass_vector": tuple(pass_vector),
                "score": sum(pass_vector),
            }
        )
    return rows


def _argmax(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    _require(bool(rows), "score table is empty")
    top_score = max(int(row["score"]) for row in rows)
    top = [row for row in rows if row["score"] == top_score]
    lower_scores = sorted(
        {int(row["score"]) for row in rows if int(row["score"]) < top_score},
        reverse=True,
    )
    plateau_gap = top_score - lower_scores[0] if lower_scores else top_score + 1
    return {
        "candidate_ids": frozenset(str(row["candidate_id"]) for row in top),
        "pass_vectors": frozenset(tuple(row["pass_vector"]) for row in top),
        "plateau_gap": plateau_gap,
        "top_score": top_score,
    }


def _local_shards(projection: Mapping[str, Any]) -> list[dict[str, Any]]:
    shards: list[dict[str, Any]] = []
    for indices in itertools.combinations(range(5), SHARD_SIZE):
        top = _argmax(_score_rows(projection, indices))
        if (
            len(top["candidate_ids"]) == 3
            and len(top["pass_vectors"]) == 1
            and top["plateau_gap"] >= 1
        ):
            shards.append({"indices": indices, "support": top["candidate_ids"]})
    return shards


def _structural_profiles(
    projection: Mapping[str, Any], local_shards: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    full = _argmax(_score_rows(projection, tuple(range(5))))
    profiles: list[dict[str, Any]] = []
    for worker_a in local_shards:
        for worker_b in local_shards:
            for worker_c in local_shards:
                shard_indices = (
                    tuple(worker_a["indices"]),
                    tuple(worker_b["indices"]),
                    tuple(worker_c["indices"]),
                )
                if len(set(shard_indices)) != 3 or set().union(*map(set, shard_indices)) != set(range(5)):
                    continue
                supports = (
                    frozenset(worker_a["support"]),
                    frozenset(worker_b["support"]),
                    frozenset(worker_c["support"]),
                )
                if len(set(supports)) != 3:
                    continue
                pairwise = (
                    supports[0] & supports[1],
                    supports[0] & supports[2],
                    supports[1] & supports[2],
                )
                triple = supports[0] & supports[1] & supports[2]
                if (
                    [len(value) for value in pairwise] != [2, 2, 2]
                    or len(triple) != 1
                    or full["candidate_ids"] != triple
                ):
                    continue
                profiles.append(
                    {
                        "worker_shards": shard_indices,
                        "supports": supports,
                        "pairwise": pairwise,
                        "triple": triple,
                    }
                )
    return profiles


def select_first_profile(profiles: Iterable[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    ordered = sorted(profiles, key=lambda item: tuple(item["lexical_key"]))
    return ordered[0] if ordered else None


def scan_public_projections(
    projections: Sequence[Mapping[str, Any]], *, suite_sha256: str
) -> dict[str, Any]:
    _require(suite_sha256 == EXPECTED_SUITE_SHA256, "task suite identity changed")
    _require(len(projections) == 8, "task count changed")
    counts: list[int] = []
    profiles: list[dict[str, Any]] = []
    for task_index, projection in enumerate(projections):
        _require(
            set(projection) == {"task_id", "semantics", "public_examples", "candidates", "response_schema"},
            "public projection shape changed",
        )
        local = _local_shards(projection)
        counts.append(len(local))
        for profile in _structural_profiles(projection, local):
            profiles.append({**profile, "lexical_key": (task_index, *profile["worker_shards"])})
    selected = select_first_profile(profiles)
    return {
        "public_projection_sha256": json_sha256(list(projections)),
        "locally_eligible_shard_counts_by_task_index": counts,
        "maximum_locally_eligible_shards_for_any_task": max(counts),
        "structurally_eligible_profile_count": len(profiles),
        "selected_profile": selected,
    }


def _assert_public_no_smuggle(value: Any) -> None:
    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            _require(not (_FORBIDDEN_PUBLIC_KEYS & set(item)), "diagnostic contains protected keys")
            for key, child in item.items():
                visit(key)
                visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)
        elif isinstance(item, str):
            _require(not _INTERNAL_CANDIDATE_PATTERN.search(item), "diagnostic contains candidate identity")

    visit(value)


def build_diagnostic() -> dict[str, Any]:
    suite = task_suite.build_frozen_task_suite()
    _require(suite.suite_sha256 == EXPECTED_SUITE_SHA256, "frozen suite hash changed")
    projections = [task.public_projection() for task in suite.tasks]
    scan = scan_public_projections(projections, suite_sha256=suite.suite_sha256)
    _require(scan["selected_profile"] is None, "valid worker geometry requires the full design path")
    _require(
        scan["maximum_locally_eligible_shards_for_any_task"] < REQUIRED_LOCAL_SHARDS,
        "no-geometry stop reason changed",
    )
    diagnostic = {
        "schema_version": 1,
        "scan_id": SCAN_ID,
        "design_id": DESIGN_ID,
        "source_commit": STARTING_COMMIT,
        "status": CLASSIFICATION,
        "frozen_suite": {
            "suite_id": task_suite.SUITE_ID,
            "suite_sha256": suite.suite_sha256,
            "task_count": len(projections),
            "candidate_count_per_task": 64,
            "public_examples_per_task": 5,
            "worker_shard_size": SHARD_SIZE,
        },
        "public_scan": {
            "public_projection_sha256": scan["public_projection_sha256"],
            "task_scan_count": len(projections),
            "possible_shards_per_task": 10,
            "locally_eligible_shard_counts_by_task_index": scan[
                "locally_eligible_shard_counts_by_task_index"
            ],
            "maximum_locally_eligible_shards_for_any_task": scan[
                "maximum_locally_eligible_shards_for_any_task"
            ],
            "required_distinct_worker_shards": REQUIRED_LOCAL_SHARDS,
            "structurally_eligible_profile_count": 0,
            "selected_profile": None,
            "selection_law": "task index, worker-A shard indices, worker-B shard indices, worker-C shard indices",
        },
        "unreached_gates": {
            "tokenizer_length_gate_consulted": False,
            "protected_hidden_gate_consulted": False,
            "private_binding_loaded": False,
            "hidden_score_computed": False,
        },
        "omitted_design_surfaces": {
            "worker_carrier_created": False,
            "worker_requests_created": 0,
            "synthesis_request_created": False,
            "preregistration_created": False,
            "controller_created": False,
            "future_live_command_created": False,
        },
        "live_state": {
            "authority_created": False,
            "authority_reserved": False,
            "sidecar_launches": 0,
            "model_requests": 0,
            "model_generations": 0,
            "captures_created": 0,
            "results_created": 0,
            "publication_records_created": 0,
        },
        "claim_state": {
            "worker_synthesis": "LOCKED",
            "general_catalytic_inference": "LOCKED",
            "task_advantage": "LOCKED",
            "reduced_fresh_computation": "LOCKED",
            "compute_amplification": "LOCKED",
            "automatic_promotion": False,
        },
        "next_boundary": NEXT_BOUNDARY,
    }
    _assert_public_no_smuggle(diagnostic)
    return diagnostic


def artifact_bytes() -> bytes:
    return canonical_json_bytes(build_diagnostic()) + b"\n"


def validate_artifact(repository: Path) -> dict[str, Any]:
    path = repository / ARTIFACT_RELATIVE_PATH
    _require(path.is_file() and not path.is_symlink(), "geometry diagnostic is absent")
    actual = path.read_bytes()
    expected = artifact_bytes()
    _require(actual == expected, "geometry diagnostic differs from reconstruction")
    return {
        "status": "pass",
        "classification": CLASSIFICATION,
        "artifact": ARTIFACT_RELATIVE_PATH,
        "artifact_sha256": sha256_bytes(actual),
        "selected_profile": None,
        "hidden_gate_consulted": False,
        "private_binding_loaded": False,
        "preregistration_created": False,
        "controller_created": False,
        "model_requests": 0,
        "sidecar_launches": 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("render", "validate"))
    parser.add_argument("--repository", default=str(Path.cwd()))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.operation == "render":
            print(canonical_json_text(build_diagnostic()))
        else:
            print(canonical_json_text(validate_artifact(Path(args.repository).resolve())))
    except (OSError, task_suite.AdvantageTaskError, WorkerGeometryScanError) as exc:
        print(canonical_json_text({"status": "fail", "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
