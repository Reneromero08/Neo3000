#!/usr/bin/env python3
"""Public-only availability scan for the two-worker synthesis mini-swarm.

The frozen corpus is inspected before tokenizer, hidden-utility, private-binding,
authority, or runtime construction.  If no exact two-worker geometry exists, the
module emits only the bounded availability diagnostic required by the design.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import catalytic_advantage_tasks as task_suite
import catalytic_kernel_0_balanced_three_worker_to_synthesis_mini_swarm_scan as public_scan


DESIGN_ID = "balanced-opaque-two-worker-to-synthesis-mini-swarm-v1"
SCAN_ID = f"{DESIGN_ID}-public-geometry-scan-1"
STARTING_COMMIT = "c8942f7b4ecf7ab555b54393fc63c4cbb5a366b3"
EXPECTED_SUITE_SHA256 = (
    "4B9961D5054BE5D98EF315D2DEAE9D1604E0042A69CB02A8B81FDF513BC1FC92"
)
CLASSIFICATION = "EXISTING_CORPUS_TWO_WORKER_GEOMETRY_UNAVAILABLE"
ARTIFACT_RELATIVE_PATH = (
    "lab/ck0_balanced_opaque_two_worker_to_synthesis_mini_swarm_v1_"
    "geometry_scan_1.json"
)
NEXT_BOUNDARY = (
    "SEPARATELY_AUTHORIZE_A_STATIC_SCIENTIFIC_DECISION_ON_TWO_WORKER_"
    "PROFILE_COMPATIBILITY"
)
SHARD_SIZE = 3
PUBLIC_EXAMPLE_COUNT = 5
REQUIRED_SUPPORT_CARDINALITY = 3


class TwoWorkerGeometryScanError(RuntimeError):
    """The frozen public scan or diagnostic boundary changed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TwoWorkerGeometryScanError(message)


def _pair_profiles(
    projection: Mapping[str, Any],
    local_shards: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Enumerate exact ordered A/B profiles using public evidence only."""
    full = public_scan._argmax(
        public_scan._score_rows(projection, tuple(range(PUBLIC_EXAMPLE_COUNT)))
    )
    profiles: list[dict[str, Any]] = []
    ordered_distinct_pairs = 0
    coverage_overlap_pairs = 0
    unique_support_intersection_pairs = 0
    shard_union_cardinalities: list[int] = []
    shard_overlap_cardinalities: list[int] = []
    support_intersection_cardinalities: list[int] = []

    for worker_a in local_shards:
        for worker_b in local_shards:
            indices_a = tuple(worker_a["indices"])
            indices_b = tuple(worker_b["indices"])
            if indices_a == indices_b:
                continue
            ordered_distinct_pairs += 1
            shard_a = set(indices_a)
            shard_b = set(indices_b)
            shard_union_cardinalities.append(len(shard_a | shard_b))
            shard_overlap_cardinalities.append(len(shard_a & shard_b))

            support_a = frozenset(worker_a["support"])
            support_b = frozenset(worker_b["support"])
            support_intersection = support_a & support_b
            support_intersection_cardinalities.append(len(support_intersection))

            covers_public = shard_a | shard_b == set(range(PUBLIC_EXAMPLE_COUNT))
            overlaps_once = len(shard_a & shard_b) == 1
            if covers_public and overlaps_once:
                coverage_overlap_pairs += 1
            if len(support_intersection) == 1:
                unique_support_intersection_pairs += 1

            if not (covers_public and overlaps_once):
                continue
            if support_a == support_b:
                continue
            if len(support_a) != REQUIRED_SUPPORT_CARDINALITY:
                continue
            if len(support_b) != REQUIRED_SUPPORT_CARDINALITY:
                continue
            if len(support_intersection) != 1:
                continue
            if len(support_a | support_b) != 5:
                continue
            if full["candidate_ids"] != support_intersection:
                continue
            profiles.append(
                {
                    "worker_shards": (indices_a, indices_b),
                    "supports": (support_a, support_b),
                    "intersection": support_intersection,
                }
            )

    return profiles, {
        "ordered_distinct_local_shard_pairs": ordered_distinct_pairs,
        "pairs_covering_all_five_examples_with_one_example_overlap": coverage_overlap_pairs,
        "pairs_with_unique_support_intersection": unique_support_intersection_pairs,
        "maximum_shard_union_cardinality": max(shard_union_cardinalities, default=0),
        "minimum_shard_overlap_cardinality": min(shard_overlap_cardinalities, default=None),
        "minimum_support_intersection_cardinality": min(
            support_intersection_cardinalities, default=None
        ),
    }


def select_first_profile(
    profiles: Iterable[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    ordered = sorted(profiles, key=lambda item: tuple(item["lexical_key"]))
    return ordered[0] if ordered else None


def scan_public_projections(
    projections: Sequence[Mapping[str, Any]], *, suite_sha256: str
) -> dict[str, Any]:
    _require(suite_sha256 == EXPECTED_SUITE_SHA256, "task suite identity changed")
    _require(len(projections) == 8, "task count changed")
    local_counts: list[int] = []
    pair_counts: list[int] = []
    coverage_counts: list[int] = []
    unique_support_counts: list[int] = []
    max_unions: list[int] = []
    min_overlaps: list[int] = []
    min_support_intersections: list[int] = []
    profiles: list[dict[str, Any]] = []

    for task_index, projection in enumerate(projections):
        _require(
            set(projection)
            == {"task_id", "semantics", "public_examples", "candidates", "response_schema"},
            "public projection shape changed",
        )
        local = public_scan._local_shards(projection)
        local_counts.append(len(local))
        task_profiles, observations = _pair_profiles(projection, local)
        pair_counts.append(observations["ordered_distinct_local_shard_pairs"])
        coverage_counts.append(
            observations["pairs_covering_all_five_examples_with_one_example_overlap"]
        )
        unique_support_counts.append(
            observations["pairs_with_unique_support_intersection"]
        )
        max_unions.append(observations["maximum_shard_union_cardinality"])
        if observations["minimum_shard_overlap_cardinality"] is not None:
            min_overlaps.append(observations["minimum_shard_overlap_cardinality"])
        if observations["minimum_support_intersection_cardinality"] is not None:
            min_support_intersections.append(
                observations["minimum_support_intersection_cardinality"]
            )
        for profile in task_profiles:
            profiles.append(
                {
                    **profile,
                    "lexical_key": (task_index, *profile["worker_shards"]),
                }
            )

    return {
        "public_projection_sha256": public_scan.json_sha256(list(projections)),
        "locally_eligible_shard_counts_by_task_index": local_counts,
        "ordered_distinct_local_shard_pair_counts_by_task_index": pair_counts,
        "coverage_overlap_pair_counts_by_task_index": coverage_counts,
        "unique_support_intersection_pair_counts_by_task_index": unique_support_counts,
        "ordered_distinct_local_shard_pair_count": sum(pair_counts),
        "maximum_shard_union_cardinality": max(max_unions),
        "minimum_shard_overlap_cardinality": min(min_overlaps, default=None),
        "minimum_support_intersection_cardinality": min(
            min_support_intersections, default=None
        ),
        "structurally_eligible_profile_count": len(profiles),
        "selected_profile": select_first_profile(profiles),
    }


def build_diagnostic() -> dict[str, Any]:
    suite = task_suite.build_frozen_task_suite()
    _require(suite.suite_sha256 == EXPECTED_SUITE_SHA256, "frozen suite hash changed")
    projections = [task.public_projection() for task in suite.tasks]
    scan = scan_public_projections(projections, suite_sha256=suite.suite_sha256)
    _require(scan["selected_profile"] is None, "valid profile requires the full design path")
    _require(
        scan["structurally_eligible_profile_count"] == 0,
        "two-worker no-geometry stop reason changed",
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
            "public_examples_per_task": PUBLIC_EXAMPLE_COUNT,
            "worker_shard_size": SHARD_SIZE,
        },
        "public_scan": {
            "public_projection_sha256": scan["public_projection_sha256"],
            "task_scan_count": len(projections),
            "possible_shards_per_task": 10,
            "locally_eligible_shard_counts_by_task_index": scan[
                "locally_eligible_shard_counts_by_task_index"
            ],
            "ordered_distinct_local_shard_pair_counts_by_task_index": scan[
                "ordered_distinct_local_shard_pair_counts_by_task_index"
            ],
            "coverage_overlap_pair_counts_by_task_index": scan[
                "coverage_overlap_pair_counts_by_task_index"
            ],
            "unique_support_intersection_pair_counts_by_task_index": scan[
                "unique_support_intersection_pair_counts_by_task_index"
            ],
            "ordered_distinct_local_shard_pair_count": scan[
                "ordered_distinct_local_shard_pair_count"
            ],
            "maximum_shard_union_cardinality": scan[
                "maximum_shard_union_cardinality"
            ],
            "minimum_shard_overlap_cardinality": scan[
                "minimum_shard_overlap_cardinality"
            ],
            "minimum_support_intersection_cardinality": scan[
                "minimum_support_intersection_cardinality"
            ],
            "required_shard_union_cardinality": PUBLIC_EXAMPLE_COUNT,
            "required_shard_overlap_cardinality": 1,
            "required_support_cardinality_per_worker": REQUIRED_SUPPORT_CARDINALITY,
            "required_support_intersection_cardinality": 1,
            "structurally_eligible_profile_count": 0,
            "selected_profile": None,
            "selection_law": "task index, worker-A shard indices, worker-B shard indices",
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
            "three_worker_geometry_diagnostic": "UNCHANGED",
            "worker_synthesis": "LOCKED",
            "general_catalytic_inference": "LOCKED",
            "task_advantage": "LOCKED",
            "reduced_fresh_computation": "LOCKED",
            "compute_amplification": "LOCKED",
            "automatic_promotion": False,
        },
        "next_boundary": NEXT_BOUNDARY,
    }
    public_scan._assert_public_no_smuggle(diagnostic)
    return diagnostic


def artifact_bytes() -> bytes:
    return public_scan.canonical_json_bytes(build_diagnostic()) + b"\n"


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
        "artifact_sha256": public_scan.sha256_bytes(actual),
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
            print(public_scan.canonical_json_text(build_diagnostic()))
        else:
            print(
                public_scan.canonical_json_text(
                    validate_artifact(Path(args.repository).resolve())
                )
            )
    except (
        OSError,
        task_suite.AdvantageTaskError,
        public_scan.WorkerGeometryScanError,
        TwoWorkerGeometryScanError,
    ) as exc:
        print(public_scan.canonical_json_text({"status": "fail", "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
