#!/usr/bin/env python3
"""Focused CPU-only tests for typed Catalytic Inference Bench 0 artifacts."""

from __future__ import annotations

import copy
import dataclasses
import json
import unittest
from collections import Counter
from typing import Any
from unittest import mock

import catalytic_inference_bench_0 as bench_module

from catalytic_advantage_tasks import (
    build_frozen_task_suite,
    render_public_task,
    score_candidate,
    validate_public_projection,
)
from catalytic_inference_bench_0 import (
    CANDIDATE_IDS,
    CHECKED_CLAIMS,
    DIRECT_ID,
    EXTRACT_ID,
    EXTRACTION_REASON_CODES,
    MECHANISM_COLLAPSED,
    MECHANISM_INCONCLUSIVE,
    MECHANISM_VISIBLE,
    MECHANISM_WEAK,
    PHYSICAL_SLOT,
    PUBLIC_EVIDENCE_REFS,
    RELATION_EFFECT_BY_OPERATOR,
    REQUEST_IDS,
    RESTORE_ID,
    SEED_IDS,
    STRUCTURAL_REASON_CODES,
    TRANSFORM_IDS,
    VERIFIER_REASON_CODES,
    VERIFY_IDS,
    WARM_ID,
    CatalyticInferenceBench0Error,
    build_catalytic_inference_bench_0_plan,
    build_bound_assignment,
    bind_runtime_restoration,
    build_dynamic_parent_context,
    build_model_request,
    canonical_json_text,
    canonical_json_bytes,
    classify_catalytic_inference_bench_0,
    compute_mechanism_metrics,
    normalize_observation,
    normalize_observation_from_metadata,
    parse_structured_response,
    score_extraction,
    sha256_bytes,
    summarize_catalytic_inference_bench_0,
    validate_catalytic_inference_bench_0_plan,
    validate_dag,
    validate_lineage,
    validate_model_request,
    validate_restoration_request,
    validate_structured_response,
)


VISIBLE_RANKINGS = {
    DIRECT_ID: ["C00", "C01", "C02"],
    "seed-1": ["C00", "C01", "C02"],
    "seed-2": ["C01", "C03", "C04"],
    "seed-3": ["C02", "C04", "C05"],
    "transform-1": ["C01", "C00", "C03"],
    "transform-2": ["C04", "C02", "C01"],
    "transform-3": ["C02", "C05", "C00"],
    "verify-1": ["C01", "C04", "C00"],
    "verify-2": ["C02", "C04", "C05"],
    "verify-3": ["C00", "C02", "C01"],
}

VISIBLE_REJECTED = {
    "verify-1": ["C02", "C03"],
    "verify-2": ["C00", "C01"],
    "verify-3": ["C03", "C05"],
}


class CatalyticInferenceBench0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = build_catalytic_inference_bench_0_plan()

    def _ranking(
        self,
        request_id: str,
        mode: str,
    ) -> list[str]:
        if mode == "collapsed":
            return ["C00"]
        return list(VISIBLE_RANKINGS[request_id])

    def _response_for(
        self,
        request_id: str,
        observations: tuple[Any, ...],
        *,
        mode: str = "visible",
        extraction_scope: str = "full",
        restoration_status: str = "restored",
        operator_mode: str = "varied",
    ) -> dict[str, Any]:
        request = self.plan.request(request_id)
        by_id = {item.request_id: item for item in observations}
        if request_id == WARM_ID:
            return {
                "artifact_id": WARM_ID,
                "root_status": "ready",
                "public_system_root_sha256": request.system_root_sha256,
            }
        if request_id in (DIRECT_ID, *SEED_IDS):
            return {
                "artifact_id": request_id,
                "candidate_ranking": self._ranking(request_id, mode),
                "confidence_bucket": "medium",
                "public_evidence_refs": [
                    PUBLIC_EVIDENCE_REFS[0],
                    PUBLIC_EVIDENCE_REFS[2],
                ],
            }
        if request_id in TRANSFORM_IDS:
            ranking = self._ranking(request_id, mode)
            parent_rankings = [
                list(by_id[parent].artifact["candidate_ranking"])
                for parent in request.parent_ids
            ]
            relational_changes = []
            for candidate_id in ranking:
                relational_changes.append(
                    {
                        "candidate_id": candidate_id,
                        "public_evidence_refs": [
                            PUBLIC_EVIDENCE_REFS[0],
                            PUBLIC_EVIDENCE_REFS[2],
                        ],
                    }
                )
            relation_operator = (
                "oppose"
                if operator_mode == "uniform"
                else {
                "transform-1": "combine",
                "transform-2": "eliminate",
                "transform-3": "refine",
                }[request_id]
            )
            parent_union = [
                candidate
                for parent_ranking in parent_rankings
                for candidate in parent_ranking
            ]
            relation_edges = []
            for candidate_id in ranking:
                alternatives = [
                    candidate
                    for candidate in (*ranking, *parent_union)
                    if candidate != candidate_id
                ]
                object_candidate_id = (
                    alternatives[0] if alternatives else candidate_id
                )
                relation_edges.append(
                    {
                        "subject_candidate_id": candidate_id,
                        "object_candidate_id": object_candidate_id,
                        "public_evidence_refs": [
                            PUBLIC_EVIDENCE_REFS[0],
                            PUBLIC_EVIDENCE_REFS[2],
                        ],
                    }
                )
            binding = build_bound_assignment(request, observations)["binding"]
            return {
                "artifact_id": request_id,
                "parent_artifact_ids": list(request.parent_ids),
                "relation_operator": relation_operator,
                "candidate_ranking": ranking,
                "confidence_bucket": "high" if mode == "visible" else "low",
                "public_evidence_refs": [
                    PUBLIC_EVIDENCE_REFS[0],
                    PUBLIC_EVIDENCE_REFS[2],
                ],
                "structural_reason_codes": [
                    STRUCTURAL_REASON_CODES[5],
                    STRUCTURAL_REASON_CODES[9],
                ],
                "relational_changes": relational_changes,
                "relation_edges": relation_edges,
                "assignment_body_sha256": binding["assignment_body_sha256"],
            }
        if request_id in VERIFY_IDS:
            ranking = self._ranking(request_id, mode)
            rejected = (
                [] if mode == "collapsed" else list(VISIBLE_REJECTED[request_id])
            )
            passed, total = score_candidate(
                build_frozen_task_suite().tasks[5],
                ranking[0],
                hidden=False,
            )
            return {
                "artifact_id": request_id,
                "parent_artifact_ids": list(request.parent_ids),
                "checked_claims": [
                    CHECKED_CLAIMS[0],
                    CHECKED_CLAIMS[2],
                    CHECKED_CLAIMS[3],
                ],
                "surviving_candidates": ranking,
                "rejected_candidates": rejected,
                "public_test_summary": {"passed": passed, "total": total},
                "reason_codes": [
                    VERIFIER_REASON_CODES[0],
                    VERIFIER_REASON_CODES[5],
                    VERIFIER_REASON_CODES[7],
                ],
                "candidate_ranking": ranking,
                "assignment_body_sha256": build_bound_assignment(
                    request, observations
                )["binding"]["assignment_body_sha256"],
            }
        if request_id == EXTRACT_ID:
            selected = "C00" if mode == "collapsed" else "C01"
            if extraction_scope == "partial":
                transforms_used = ["transform-1", "transform-2"]
                verifiers_used = ["verify-1"]
            else:
                transforms_used = list(TRANSFORM_IDS)
                verifiers_used = list(VERIFY_IDS)
            relation_edge_ids_used = [
                edge["edge_id"]
                for transform_id in transforms_used
                for edge in by_id[transform_id].artifact["relation_edges"]
            ]
            return {
                "artifact_id": EXTRACT_ID,
                "selected_candidate_id": selected,
                "complete_parent_lineage": list(request.ancestor_ids),
                "transformation_ids_used": transforms_used,
                "verifier_ids_used": verifiers_used,
                "final_confidence_bucket": "high" if mode == "visible" else "low",
                "extraction_reason_codes": [
                    EXTRACTION_REASON_CODES[0],
                    EXTRACTION_REASON_CODES[1],
                    EXTRACTION_REASON_CODES[3],
                ],
                "relation_edge_ids_used": relation_edge_ids_used,
                "assignment_body_sha256": build_bound_assignment(
                    request, observations
                )["binding"]["assignment_body_sha256"],
            }
        if request_id == RESTORE_ID:
            return {
                "artifact_id": RESTORE_ID,
                "restoration_status": restoration_status,
                "restored_public_system_root_sha256": request.system_root_sha256,
                "slot": PHYSICAL_SLOT,
                "slot_state": "public-root",
            }
        raise AssertionError(request_id)

    def _observations_for(
        self,
        *,
        mode: str = "visible",
        extraction_scope: str = "full",
        restoration_status: str = "restored",
        root_reuse_failure_id: str | None = None,
        safety_failure_id: str | None = None,
        hidden_leak_id: str | None = None,
        restoration_receipt_passed: bool = True,
        operator_mode: str = "varied",
    ) -> tuple[tuple[Any, ...], dict[str, dict[str, Any]]]:
        observations: list[Any] = []
        payloads: dict[str, dict[str, Any]] = {}
        for request in self.plan.requests:
            payloads[request.request_id] = build_model_request(
                request,
                parent_observations=tuple(observations),
                model="agents-a1.gguf",
            )
            response = self._response_for(
                request.request_id,
                tuple(observations),
                mode=mode,
                extraction_scope=extraction_scope,
                restoration_status=restoration_status,
                operator_mode=operator_mode,
            )
            is_warm = request.request_id == WARM_ID
            root_reused = (
                not is_warm and request.request_id != root_reuse_failure_id
            )
            cached = 0 if is_warm else (8 if root_reused else 3)
            observations.append(
                normalize_observation(
                    request,
                    response,
                    parent_observations=tuple(observations),
                    completed=True,
                    safety_passed=True,
                    root_reused=root_reused,
                    public_root_terminal_token_index=4,
                    hidden_leak_detected=False,
                    prompt_tokens=10,
                    cached_prompt_tokens=cached,
                    fresh_prompt_tokens=10 - cached,
                    completion_tokens=8,
                    finish_reason="stop",
                )
            )
        observations[-1] = bind_runtime_restoration(
            observations[-1],
            run_id="focused-test",
            root_identity_passed=restoration_receipt_passed,
            cache_terminal_admitted=restoration_receipt_passed,
            active_leases=0,
            cleanup_passed=restoration_receipt_passed,
            custody_passed=restoration_receipt_passed,
            sidecar_port_free=restoration_receipt_passed,
            stable_preserved=restoration_receipt_passed,
        )
        if safety_failure_id is not None:
            index = REQUEST_IDS.index(safety_failure_id)
            observations[index] = dataclasses.replace(
                observations[index],
                safety_passed=False,
            )
        if hidden_leak_id is not None:
            index = REQUEST_IDS.index(hidden_leak_id)
            observations[index] = dataclasses.replace(
                observations[index],
                hidden_leak_detected=True,
            )
        return tuple(observations), payloads

    def _model_transform_fixture(
        self,
        request_id: str = "transform-1",
    ) -> tuple[tuple[Any, ...], dict[str, Any]]:
        observations, _ = self._observations_for()
        artifact = copy.deepcopy(
            next(
                item.artifact
                for item in observations
                if item.request_id == request_id
            )
        )
        artifact.pop("changed_from_parents")
        for item in artifact["relational_changes"]:
            for key in (
                "parent_rank_positions",
                "resulting_rank_position",
                "change_kind",
            ):
                item.pop(key)
        for edge in artifact["relation_edges"]:
            for key in (
                "edge_id",
                "relation_operator",
                "structural_effect",
                "parent_artifact_ids",
            ):
                edge.pop(key)
        return observations, artifact

    def test_plan_schemas_dag_and_dynamic_actual_parent_context(self) -> None:
        self.assertEqual(
            REQUEST_IDS,
            (
                "warm",
                "direct",
                "seed-1",
                "seed-2",
                "seed-3",
                "transform-1",
                "transform-2",
                "transform-3",
                "verify-1",
                "verify-2",
                "verify-3",
                "extract",
                "restore",
            ),
        )
        self.assertEqual(self.plan.request_count, 13)
        self.assertEqual(self.plan.physical_slot_count, 1)
        self.assertEqual(
            Counter(item.phase for item in self.plan.requests),
            {
                "warm": 1,
                "direct": 1,
                "seed": 3,
                "transform": 3,
                "verify": 3,
                "extract": 1,
                "restore": 1,
            },
        )
        task = build_frozen_task_suite().tasks[5]
        self.assertEqual(task.task_id, "cs1-task-06")
        self.assertEqual(self.plan.public_system_root, render_public_task(task))
        validate_public_projection(task, self.plan.public_system_root)
        self.assertEqual(
            {item.system_root for item in self.plan.requests},
            {self.plan.public_system_root},
        )
        self.assertNotIn(
            "hidden_examples",
            canonical_json_text(
                self.plan.to_dict(include_public_system_root=True)
            ),
        )

        for seed_id in SEED_IDS:
            seed = self.plan.request(seed_id)
            self.assertEqual(seed.parent_ids, ())
            self.assertEqual(seed.ancestor_ids, ())
            self.assertEqual(seed.required_context_ids, ())
            self.assertEqual(
                set(seed.response_schema["properties"]),
                {
                    "artifact_id",
                    "candidate_ranking",
                    "confidence_bucket",
                    "public_evidence_refs",
                },
            )
        self.assertEqual(
            tuple(self.plan.request(item).parent_ids for item in TRANSFORM_IDS),
            (
                ("seed-1", "seed-2"),
                ("seed-2", "seed-3"),
                ("seed-1", "seed-3"),
            ),
        )
        self.assertEqual(
            tuple(self.plan.request(item).parent_ids for item in VERIFY_IDS),
            (
                ("transform-1", "transform-2"),
                ("transform-2", "transform-3"),
                ("transform-1", "transform-3"),
            ),
        )
        transform_fields = {
            "artifact_id",
            "parent_artifact_ids",
            "relation_operator",
            "candidate_ranking",
            "confidence_bucket",
            "public_evidence_refs",
            "structural_reason_codes",
            "changed_from_parents",
            "relational_changes",
            "relation_edges",
            "assignment_body_sha256",
        }
        verifier_fields = {
            "artifact_id",
            "parent_artifact_ids",
            "checked_claims",
            "surviving_candidates",
            "rejected_candidates",
            "public_test_summary",
            "reason_codes",
            "candidate_ranking",
            "assignment_body_sha256",
        }
        self.assertTrue(
            all(
                set(self.plan.request(item).response_schema["properties"])
                == transform_fields
                for item in TRANSFORM_IDS
            )
        )
        self.assertTrue(
            all(
                set(self.plan.request(item).response_schema["properties"])
                == verifier_fields
                for item in VERIFY_IDS
            )
        )
        self.assertEqual(
            set(self.plan.request(EXTRACT_ID).response_schema["properties"]),
            {
                "artifact_id",
                "selected_candidate_id",
                "complete_parent_lineage",
                "transformation_ids_used",
                "verifier_ids_used",
                "final_confidence_bucket",
                "extraction_reason_codes",
                "relation_edge_ids_used",
                "assignment_body_sha256",
            },
        )
        for request in self.plan.requests:
            self.assertIs(request.response_schema["additionalProperties"], False)
            expected_required = set(request.response_schema["properties"])
            if request.request_id in TRANSFORM_IDS:
                expected_required.remove("changed_from_parents")
                change_items = request.response_schema["properties"][
                    "relational_changes"
                ]["items"]
                edge_items = request.response_schema["properties"][
                    "relation_edges"
                ]["items"]
                self.assertEqual(
                    set(change_items["required"]),
                    {"candidate_id", "public_evidence_refs"},
                )
                self.assertEqual(
                    set(edge_items["required"]),
                    {
                        "subject_candidate_id",
                        "object_candidate_id",
                        "public_evidence_refs",
                    },
                )
            self.assertEqual(set(request.response_schema["required"]), expected_required)
        report = validate_dag(self.plan)
        self.assertTrue(report.valid)
        self.assertEqual(report.max_depth, 4)
        validate_catalytic_inference_bench_0_plan(self.plan)
        suite = build_frozen_task_suite()
        with mock.patch.object(
            bench_module,
            "build_frozen_task_suite",
            return_value=dataclasses.replace(suite, suite_sha256="0" * 64),
        ):
            with self.assertRaisesRegex(
                CatalyticInferenceBench0Error, "task-suite identity drift"
            ):
                bench_module.frozen_task()
        self.assertEqual(
            self.plan.plan_sha256,
            build_catalytic_inference_bench_0_plan().plan_sha256,
        )

        observations, payloads = self._observations_for()
        transform_context = json.loads(
            payloads["transform-1"]["messages"][1]["content"]
        )["actual_parent_context"]
        self.assertEqual(
            [item["request_id"] for item in transform_context],
            ["seed-1", "seed-2"],
        )
        self.assertEqual(
            transform_context[0]["artifact"]["candidate_ranking"],
            VISIBLE_RANKINGS["seed-1"],
        )
        verify_context = json.loads(
            payloads["verify-1"]["messages"][1]["content"]
        )["actual_parent_context"]
        self.assertEqual(
            [item["request_id"] for item in verify_context],
            ["transform-1", "transform-2"],
        )
        self.assertIn("relation_operator", verify_context[0]["artifact"])
        extraction_context = json.loads(
            payloads[EXTRACT_ID]["messages"][1]["content"]
        )["actual_parent_context"]
        self.assertEqual(
            [item["request_id"] for item in extraction_context],
            list(self.plan.request(EXTRACT_ID).ancestor_ids),
        )
        self.assertEqual(len(extraction_context), 9)
        restoration_context = json.loads(
            payloads[RESTORE_ID]["messages"][1]["content"]
        )["actual_parent_context"]
        self.assertEqual(restoration_context, [])
        self.assertEqual(
            build_dynamic_parent_context(
                self.plan.request(RESTORE_ID), observations
            ),
            (),
        )
        validate_restoration_request(self.plan.request(RESTORE_ID))
        restoration_schema = canonical_json_text(
            self.plan.request(RESTORE_ID).response_schema
        ).casefold()
        for forbidden in (
            "candidate",
            "ranking",
            "selected",
            "surviving",
            "rejected",
        ):
            self.assertNotIn(forbidden, restoration_schema)
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "required actual artifact unavailable",
        ):
            build_model_request(self.plan.request("transform-1"))

    def test_reordered_relational_changes_canonicalize_to_output_ranking(self) -> None:
        observations, transform = self._model_transform_fixture()
        transform["relational_changes"].reverse()
        normalized = validate_structured_response(
            self.plan.request("transform-1"),
            transform,
            parent_observations=observations,
        )
        self.assertEqual(
            [item["candidate_id"] for item in normalized["relational_changes"]],
            normalized["candidate_ranking"],
        )

    def test_missing_relational_change_candidate_rejects(self) -> None:
        observations, transform = self._model_transform_fixture()
        transform["relational_changes"].pop()
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "exactly cover",
        ):
            validate_structured_response(
                self.plan.request("transform-1"),
                transform,
                parent_observations=observations,
            )

    def test_extra_relational_change_candidate_rejects(self) -> None:
        observations, transform = self._model_transform_fixture()
        transform["relational_changes"][-1]["candidate_id"] = "C63"
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "exactly cover",
        ):
            validate_structured_response(
                self.plan.request("transform-1"),
                transform,
                parent_observations=observations,
            )

    def test_duplicate_relational_change_candidate_rejects(self) -> None:
        observations, transform = self._model_transform_fixture()
        transform["relational_changes"][-1]["candidate_id"] = transform[
            "relational_changes"
        ][0]["candidate_id"]
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "duplicate candidate",
        ):
            validate_structured_response(
                self.plan.request("transform-1"),
                transform,
                parent_observations=observations,
            )

    def test_parent_rank_positions_are_derived_from_actual_parents(self) -> None:
        observations, transform = self._model_transform_fixture()
        for item in transform["relational_changes"]:
            item["parent_rank_positions"] = []
        normalized = validate_structured_response(
            self.plan.request("transform-1"),
            transform,
            parent_observations=observations,
        )
        self.assertEqual(
            normalized["relational_changes"][0]["parent_rank_positions"],
            [
                {"parent_artifact_id": "seed-1", "rank_position": 2},
                {"parent_artifact_id": "seed-2", "rank_position": 1},
            ],
        )

    def test_result_positions_and_change_kinds_are_derived(self) -> None:
        observations, transform = self._model_transform_fixture()
        for item in transform["relational_changes"]:
            item["resulting_rank_position"] = 3
            item["change_kind"] = "introduced"
        normalized = validate_structured_response(
            self.plan.request("transform-1"),
            transform,
            parent_observations=observations,
        )
        self.assertEqual(
            [
                (item["resulting_rank_position"], item["change_kind"])
                for item in normalized["relational_changes"]
            ],
            [(1, "reconciled"), (2, "demoted"), (3, "demoted")],
        )

    def test_semantic_edges_canonicalize_independently_of_source_order(self) -> None:
        observations, transform = self._model_transform_fixture()
        first = validate_structured_response(
            self.plan.request("transform-1"),
            transform,
            parent_observations=observations,
        )
        transform["relation_edges"].reverse()
        for edge in transform["relation_edges"]:
            edge["edge_id"] = "transform-1-edge-3"
            edge["parent_artifact_ids"] = []
            edge["structural_effect"] = "opposition"
        second = validate_structured_response(
            self.plan.request("transform-1"),
            transform,
            parent_observations=observations,
        )
        self.assertEqual(second["relation_edges"], first["relation_edges"])
        self.assertEqual(
            [edge["edge_id"] for edge in second["relation_edges"]],
            ["transform-1-edge-1", "transform-1-edge-2", "transform-1-edge-3"],
        )
        self.assertTrue(
            all(
                edge["parent_artifact_ids"] == ["seed-1", "seed-2"]
                and edge["relation_operator"] == second["relation_operator"]
                and edge["structural_effect"]
                == RELATION_EFFECT_BY_OPERATOR[second["relation_operator"]]
                for edge in second["relation_edges"]
            )
        )

    def test_missing_edge_coverage_rejects_without_inventing_an_edge(self) -> None:
        observations, transform = self._model_transform_fixture()
        transform["relation_edges"].pop()
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "do not cover",
        ) as caught:
            validate_structured_response(
                self.plan.request("transform-1"),
                transform,
                parent_observations=observations,
            )
        diagnostic = caught.exception.semantic_diagnostic
        self.assertEqual(diagnostic["failed_semantic_gate"], "relation-edge-coverage")
        self.assertEqual(len(diagnostic["relation_edge_pairs"]), 2)

        no_edges = copy.deepcopy(transform)
        no_edges["relation_edges"] = []
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "relation edges are malformed",
        ) as empty_caught:
            validate_structured_response(
                self.plan.request("transform-1"),
                no_edges,
                parent_observations=observations,
            )
        self.assertEqual(no_edges["relation_edges"], [])
        self.assertEqual(
            empty_caught.exception.semantic_diagnostic["relation_edge_pairs"],
            [],
        )

    def test_strict_artifact_validation_normalization_and_hidden_boundaries(self) -> None:
        observations, payloads = self._observations_for()
        by_id = {item.request_id: item for item in observations}
        for observation in observations:
            self.assertEqual(
                validate_structured_response(
                    self.plan.request(observation.request_id),
                    observation.artifact,
                    parent_observations=observations,
                ),
                observation.artifact,
            )

        seed = copy.deepcopy(by_id["seed-1"].artifact)
        seed["candidate_ranking"] = ["C00", "C00"]
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "bounded and unique",
        ):
            validate_structured_response(self.plan.request("seed-1"), seed)
        seed["candidate_ranking"] = ["C64"]
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "invalid candidate",
        ):
            validate_structured_response(self.plan.request("seed-1"), seed)

        transform = copy.deepcopy(by_id["transform-1"].artifact)
        transform["changed_from_parents"] = not transform["changed_from_parents"]
        normalized_transform = validate_structured_response(
            self.plan.request("transform-1"),
            transform,
            parent_observations=observations,
        )
        self.assertEqual(
            normalized_transform["changed_from_parents"],
            by_id["transform-1"].artifact["changed_from_parents"],
        )
        transform = copy.deepcopy(by_id["transform-1"].artifact)
        transform["assignment_body_sha256"] = "A" * 64
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "consumption binding",
        ):
            validate_structured_response(
                self.plan.request("transform-1"),
                transform,
                parent_observations=observations,
            )
        substituted = list(observations)
        seed_two_index = REQUEST_IDS.index("seed-2")
        altered_seed = copy.deepcopy(by_id["seed-2"].artifact)
        altered_seed["candidate_ranking"] = list(
            reversed(altered_seed["candidate_ranking"])
        )
        substituted[seed_two_index] = dataclasses.replace(
            substituted[seed_two_index],
            artifact=altered_seed,
            artifact_sha256=sha256_bytes(canonical_json_bytes(altered_seed)),
        )
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "parent ranks|consumption binding",
        ):
            validate_structured_response(
                self.plan.request("transform-1"),
                by_id["transform-1"].artifact,
                parent_observations=substituted,
            )
        transform = copy.deepcopy(by_id["transform-1"].artifact)
        transform["parent_artifact_ids"] = ["seed-1", "seed-3"]
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "parent artifacts mismatch",
        ):
            validate_structured_response(
                self.plan.request("transform-1"),
                transform,
                parent_observations=observations,
            )

        verifier = copy.deepcopy(by_id["verify-1"].artifact)
        verifier["rejected_candidates"] = verifier["rejected_candidates"][:-1]
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "partition actual parent rankings",
        ):
            validate_structured_response(
                self.plan.request("verify-1"),
                verifier,
                parent_observations=observations,
            )
        verifier = copy.deepcopy(by_id["verify-1"].artifact)
        verifier["public_test_summary"]["passed"] = (
            verifier["public_test_summary"]["passed"] + 1
        ) % (verifier["public_test_summary"]["total"] + 1)
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "actual public score",
        ):
            validate_structured_response(
                self.plan.request("verify-1"),
                verifier,
                parent_observations=observations,
            )

        extraction = copy.deepcopy(by_id[EXTRACT_ID].artifact)
        extraction["complete_parent_lineage"] = extraction[
            "complete_parent_lineage"
        ][1:]
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "lineage is incomplete",
        ):
            validate_structured_response(
                self.plan.request(EXTRACT_ID),
                extraction,
                parent_observations=observations,
            )
        extraction = copy.deepcopy(by_id[EXTRACT_ID].artifact)
        extraction["transformation_ids_used"] = ["transform-1"]
        extraction["verifier_ids_used"] = ["verify-1"]
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "omitted a transform parent",
        ):
            validate_structured_response(
                self.plan.request(EXTRACT_ID),
                extraction,
                parent_observations=observations,
            )
        extraction = copy.deepcopy(by_id[EXTRACT_ID].artifact)
        extraction["selected_candidate_id"] = "C63"
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "absent from used transforms",
        ):
            validate_structured_response(
                self.plan.request(EXTRACT_ID),
                extraction,
                parent_observations=observations,
            )

        restoration = copy.deepcopy(by_id[RESTORE_ID].artifact)
        restoration["selected_candidate_id"] = "C00"
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "key set mismatch",
        ):
            validate_structured_response(
                self.plan.request(RESTORE_ID),
                restoration,
            )
        self.assertTrue(by_id[RESTORE_ID].restoration_model_acknowledged)
        self.assertTrue(by_id[RESTORE_ID].restoration_passed)
        self.assertEqual(
            by_id[RESTORE_ID].restoration_receipt["run_id"],
            "focused-test",
        )
        self.assertIsNotNone(by_id[RESTORE_ID].restoration_receipt_sha256)
        forged_restoration = dataclasses.replace(
            by_id[RESTORE_ID],
            restoration_passed=True,
            restoration_receipt=None,
            restoration_receipt_sha256="A" * 64,
        )
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error, "receipt"
        ):
            classify_catalytic_inference_bench_0(
                self.plan,
                (*observations[:-1], forged_restoration),
            )
        forged_warm = dataclasses.replace(
            by_id[WARM_ID],
            public_system_root_sha256="A" * 64,
        )
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error, "frozen root"
        ):
            classify_catalytic_inference_bench_0(
                self.plan,
                (forged_warm, *observations[1:]),
            )

        canonical_seed = canonical_json_text(by_id["seed-1"].artifact)
        self.assertEqual(
            parse_structured_response(
                self.plan.request("seed-1"), canonical_seed
            ),
            by_id["seed-1"].artifact,
        )
        self.assertEqual(
            parse_structured_response(
                self.plan.request("seed-1"),
                json.dumps(by_id["seed-1"].artifact, indent=2),
            ),
            by_id["seed-1"].artifact,
        )

        normalized = by_id["transform-1"].to_dict()
        self.assertEqual(
            normalized["artifact"]["candidate_ranking"],
            VISIBLE_RANKINGS["transform-1"],
        )
        self.assertEqual(
            normalized["artifact"]["parent_artifact_ids"],
            ["seed-1", "seed-2"],
        )
        for forbidden in (
            "raw_sse",
            "reasoning",
            "reasoning_content",
            "freeform_output",
            "content",
        ):
            self.assertNotIn(forbidden, normalized)
        seed_observation = by_id["seed-1"]
        metadata = {
            "completed": True,
            "safety_passed": True,
            "root_reused": True,
            "public_root_terminal_token_index": 4,
            "hidden_leak_detected": False,
            "physical_slot": PHYSICAL_SLOT,
            "public_system_root_sha256": self.plan.public_system_root_sha256,
            "prompt_tokens": 10,
            "cached_prompt_tokens": 8,
            "fresh_prompt_tokens": 2,
            "completion_tokens": 8,
            "finish_reason": "stop",
        }
        self.assertEqual(
            normalize_observation_from_metadata(
                self.plan.request("seed-1"),
                seed_observation.artifact,
                metadata,
            ),
            seed_observation,
        )
        leaked_metadata = dict(metadata, raw_sse="forbidden")
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "raw output or reasoning",
        ):
            normalize_observation_from_metadata(
                self.plan.request("seed-1"),
                seed_observation.artifact,
                leaked_metadata,
            )

        leaked_payload = copy.deepcopy(payloads[DIRECT_ID])
        leaked_payload["answer_key"] = "C00"
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "protected evaluator",
        ):
            validate_model_request(self.plan.request(DIRECT_ID), leaked_payload)
        score = score_extraction(by_id[EXTRACT_ID])
        self.assertEqual(
            (
                score["public_score"]["passed"],
                score["public_score"]["total"],
            ),
            score_candidate(
                build_frozen_task_suite().tasks[5],
                "C01",
                hidden=False,
            ),
        )
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "only after completed extraction",
        ):
            score_extraction(by_id[DIRECT_ID])
        summary = summarize_catalytic_inference_bench_0(
            self.plan,
            observations,
        )
        self.assertTrue(summary["metadata_only"])
        self.assertEqual(summary["direct_baseline_score"]["candidate_id"], "C00")
        self.assertEqual(summary["final_catalytic_score"]["candidate_id"], "C01")
        self.assertEqual(
            summary["direct_to_catalytic_score_difference"]["hidden_passed"],
            summary["final_catalytic_score"]["post_extraction_hidden_diagnostic"]["passed"]
            - summary["direct_baseline_score"]["post_extraction_hidden_diagnostic"]["passed"],
        )
        self.assertEqual(len(summary["artifact_trace"]), 13)
        self.assertEqual(
            next(
                item
                for item in summary["artifact_trace"]
                if item["request_id"] == "transform-1"
            )["artifact"]["candidate_ranking"],
            VISIBLE_RANKINGS["transform-1"],
        )
        encoded = canonical_json_text(summary)
        for forbidden in (
            "hidden_examples",
            "answer_candidate_id",
            "answer_key",
            "raw_sse",
            "reasoning_content",
            "freeform_output",
        ):
            self.assertNotIn(forbidden, encoded)
        assessment = classify_catalytic_inference_bench_0(
            self.plan,
            observations,
        )
        forged = dataclasses.replace(
            assessment,
            mechanism_classification=MECHANISM_COLLAPSED,
        )
        with self.assertRaisesRegex(
            CatalyticInferenceBench0Error,
            "assessment differs",
        ):
            summarize_catalytic_inference_bench_0(
                self.plan,
                observations,
                forged,
            )

    def test_metrics_and_exact_classification_matrix(self) -> None:
        visible, _ = self._observations_for()
        visible_assessment = classify_catalytic_inference_bench_0(
            self.plan,
            visible,
        )
        self.assertEqual(visible_assessment.status, "complete")
        self.assertEqual(
            visible_assessment.mechanism_classification,
            MECHANISM_VISIBLE,
        )
        for gate in (
            "complete_13_requests",
            "root_reuse_requests_2_13",
            "valid_lineage",
            "artifact_parent_integrity",
            "at_least_two_candidate_ids",
            "transform_change",
            "extraction_uses_transforms",
            "restoration_pass",
            "no_hidden_leak",
        ):
            self.assertTrue(visible_assessment.gate_map[gate], gate)
        metrics = compute_mechanism_metrics(self.plan, visible)
        self.assertGreater(metrics.candidate_entropy_bits, 0.0)
        self.assertGreater(metrics.candidate_diversity_ratio, 0.0)
        self.assertGreater(metrics.ranking_diversity_ratio, 0.0)
        self.assertEqual(metrics.transform_changed_artifact_count, 3)
        self.assertEqual(metrics.transform_parent_edge_count, 6)
        self.assertEqual(metrics.transform_changed_parent_edge_count, 6)
        self.assertEqual(metrics.ranking_edge_count, 12)
        self.assertGreater(metrics.ranking_change_edge_count, 0)
        self.assertGreater(metrics.verifier_rejected_candidate_count, 0)
        self.assertEqual(metrics.extraction_transform_count, 3)
        self.assertEqual(metrics.extraction_verifier_count, 3)
        self.assertEqual(
            metrics,
            compute_mechanism_metrics(self.plan, visible),
        )

        collapsed, _ = self._observations_for(mode="collapsed")
        collapsed_assessment = classify_catalytic_inference_bench_0(
            self.plan,
            collapsed,
        )
        self.assertEqual(
            collapsed_assessment.mechanism_classification,
            MECHANISM_COLLAPSED,
        )
        self.assertEqual(collapsed_assessment.distinct_candidate_count, 1)
        self.assertEqual(
            collapsed_assessment.metrics.candidate_entropy_bits,
            0.0,
        )
        self.assertEqual(collapsed_assessment.transform_change_count, 0)
        self.assertIn("no-relational-effect", collapsed_assessment.reasons)

        uniform_operator, _ = self._observations_for(operator_mode="uniform")
        uniform_assessment = classify_catalytic_inference_bench_0(
            self.plan, uniform_operator
        )
        self.assertEqual(
            uniform_assessment.mechanism_classification,
            MECHANISM_WEAK,
        )
        self.assertFalse(
            uniform_assessment.gate_map["relation_operator_diversity"]
        )

        partial_extraction, _ = self._observations_for(
            extraction_scope="partial"
        )
        root_partial, _ = self._observations_for(
            root_reuse_failure_id="verify-3"
        )
        restoration_failed, _ = self._observations_for(
            restoration_status="failed"
        )
        core_failure_cases = {
            "partial-extraction": partial_extraction,
            "root-reuse": root_partial,
            "restoration": restoration_failed,
        }
        for name, observations in core_failure_cases.items():
            with self.subTest(classification=name):
                assessment = classify_catalytic_inference_bench_0(
                    self.plan,
                    observations,
                )
                self.assertEqual(assessment.status, "complete")
                self.assertEqual(
                    assessment.mechanism_classification,
                    MECHANISM_INCONCLUSIVE,
                )
                self.assertGreater(
                    assessment.metrics.candidate_entropy_bits,
                    0.0,
                )

        invalid_lineage = list(visible)
        verify_index = REQUEST_IDS.index("verify-1")
        invalid_lineage[verify_index] = dataclasses.replace(
            invalid_lineage[verify_index],
            parent_ids=("transform-1", "transform-3"),
        )
        lineage = validate_lineage(self.plan, invalid_lineage)
        self.assertFalse(lineage.valid)
        self.assertFalse(lineage.parent_order_valid)
        self.assertEqual(
            classify_catalytic_inference_bench_0(
                self.plan,
                invalid_lineage,
            ).mechanism_classification,
            MECHANISM_INCONCLUSIVE,
        )

        safety_failed, _ = self._observations_for(
            safety_failure_id="verify-2"
        )
        hidden_leak, _ = self._observations_for(
            hidden_leak_id="transform-2"
        )
        receipt_failed, _ = self._observations_for(
            restoration_receipt_passed=False
        )
        inconclusive_cases = {
            "incomplete": visible[:-1],
            "safety": safety_failed,
            "hidden": hidden_leak,
            "trusted-restoration": receipt_failed,
        }
        for name, observations in inconclusive_cases.items():
            with self.subTest(classification=name):
                assessment = classify_catalytic_inference_bench_0(
                    self.plan,
                    observations,
                )
                self.assertEqual(
                    assessment.mechanism_classification,
                    MECHANISM_INCONCLUSIVE,
                )
                if name == "incomplete":
                    self.assertEqual(assessment.status, "incomplete")
                else:
                    self.assertEqual(assessment.status, "complete")
                    if name in {"safety", "hidden"}:
                        self.assertFalse(assessment.gate_map["safety"])
                    if name == "trusted-restoration":
                        self.assertFalse(assessment.gate_map["restoration_pass"])


if __name__ == "__main__":
    unittest.main()
