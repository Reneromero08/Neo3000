#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping

from catalytic_kernel_0 import (
    CARRIER_ID,
    PARENT_A_INFORMATION_DELETION_CONTROL,
    PARENT_B_INFORMATION_DELETION_CONTROL,
    PARENT_B_CONTROL_RUN_ID,
    REQUEST_IDS,
    CatalyticKernel0Error,
    build_carrier,
    build_model_request,
    build_parent_a_commitment_receipt,
    build_parent_b_commitment_receipt,
    build_public_shard,
    classify_kernel,
    classify_parent_a_information_control,
    classify_parent_b_information_control,
    derive_rank_delta,
    normalize_branch,
    normalize_extraction,
    normalize_transform,
    parse_response,
    run_catalytic_kernel_0,
    unresolved_relation_observables,
    validate_parent_a_information_deletion_projection,
    validate_parent_b_information_deletion_projection,
)
from catalytic_kernel_0_carrier_scan import (
    PROFILE_ID,
    PublicCarrierScanError,
    _scan_profile,
    scan_public_projections,
    selected_unresolved_public_profile,
)
from catalytic_advantage_tasks import EXPECTED_SUITE_SHA256, build_frozen_task_suite
from catalytic_swarm import PhysicalLeasePool


ROOT = Path(__file__).resolve().parents[1]


class FakeExecution:
    def __init__(self, content: str, *, warm: bool) -> None:
        self.content = content
        self.reasoning_content = ""
        self.tool_calls: list[Any] = []
        self.prompt_tokens = 7
        self.cached_prompt_tokens = 0 if warm else 5
        self.completion_tokens = 1
        self.generated_token_ids = [42]
        self.generated_token_count = 1
        self.completion_token_count_match = True
        self.generated_token_sha256 = hashlib.sha256(b"[42]").hexdigest().upper()
        self.nonempty_token_array_event_count = 1
        self.empty_token_array_event_count = 1
        self.token_merge_modes = {"initial": 1, "ignored-empty": 1}
        self.terminal_stop_evidence = {
            "observed": True,
            "stop": True,
            "stop_type": "eos",
            "stopping_word": "",
            "verbose_token_array_length": 0,
            "event_index": 1,
        }
        self.finish_reason = "stop"
        self.http_status = 200
        self.event_count = 3
        self.total_time_s = 0.01
        self.raw_sse = "RAW_SENTINEL"


class FakeAdapter:
    def __init__(self, *, unresolved_profile: bool = False) -> None:
        self.request_ids: list[str] = []
        self.payloads: list[dict[str, Any]] = []
        self.pool_sizes: list[int] = []
        self.cleanup_calls = 0
        self.unresolved_profile = unresolved_profile

    def preflight(
        self,
        *,
        args: Any,
        repository_root: Path,
        run_root: Path,
        allowed_paths: Any,
    ) -> Mapping[str, Any]:
        return {
            "metadata": {
                "binary_identity": {"sha256": "B" * 64},
                "model_identity": {"sha256": "A" * 64},
                "stable": {"head": "1" * 40},
                "candidate": {"head": "2" * 40},
                "historical_cs1_sha256": "C" * 64,
            },
            "runtime": {},
        }

    def create_lease_pool(self, physical_slots: int) -> PhysicalLeasePool:
        self.pool_sizes.append(physical_slots)
        return PhysicalLeasePool(physical_slots)

    def launch_sidecar(
        self, *, preflight: Mapping[str, Any], run_id: str
    ) -> tuple[object, Mapping[str, Any]]:
        return object(), {"sidecar_pid": 1234, "readiness_seconds": 0.1}

    def prompt_geometry(
        self, *, sidecar: Any, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        assignment = json.loads(payload["messages"][1]["content"])
        ordinal = REQUEST_IDS.index(assignment["request_id"]) + 1
        return {
            "rendered_prompt": "IN_MEMORY_ONLY",
            "token_ids": [1, 2, 3, 4, 5, ordinal, 99],
            "public_root_terminal_token_index": 4,
        }

    def execute_request(
        self, *, sidecar: Any, payload: Mapping[str, Any], request: Any
    ) -> FakeExecution:
        self.request_ids.append(request.request_id)
        self.payloads.append(json.loads(json.dumps(payload)))
        carrier_id = payload["response_format"]["json_schema"]["schema"].get(
            "properties", {}
        ).get("carrier_id", {}).get("const", CARRIER_ID)
        if self.unresolved_profile:
            values = {
                "borrow": {"carrier_id": carrier_id},
                "branch-a": {"ranking": ["C42", "C56"]},
                "branch-b": {"ranking": ["C09", "C34", "C42"]},
                "transform": {"operator": "reconcile", "ranking": ["C42", "C56", "C09"]},
                "extract": {"candidate_id": "C42"},
                "restore": {"carrier_id": carrier_id},
            }
        else:
            values = {
                "borrow": {"carrier_id": carrier_id},
                "branch-a": {"ranking": ["C00", "C01", "C02"]},
                "branch-b": {"ranking": ["C01", "C00", "C02"]},
                "transform": {"operator": "reconcile", "ranking": ["C01", "C02", "C00"]},
                "extract": {"candidate_id": "C01"},
                "restore": {"carrier_id": carrier_id},
            }
        return FakeExecution(
            json.dumps(values[request.request_id], separators=(",", ":")),
            warm=request.request_id == "borrow",
        )

    def boundary_custody(
        self,
        *,
        preflight: Mapping[str, Any],
        sidecar: Any,
        boundary: str,
    ) -> Mapping[str, Any]:
        return {"passed": True, "boundary_sha256": hashlib.sha256(boundary.encode()).hexdigest().upper()}

    def resource_summary(
        self, *, sidecar: Any, boundary: str
    ) -> Mapping[str, Any]:
        return {
            "boundary": boundary,
            "observation_state": "unavailable",
            "observed_at": "2026-07-13T00:00:00+00:00",
        }

    def cleanup(
        self, *, sidecar: Any | None, preflight: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        self.cleanup_calls += 1
        return {
            "passed": True,
            "process_stopped": True,
            "port_free": True,
            "runtime_removed": True,
            "temporary_state_removed": True,
            "stable_preserved": True,
        }

    def postflight(self, *, preflight: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "passed": True,
            "candidate_head": "2" * 40,
            "candidate_status_sha256": "D" * 64,
        }


class CatalyticKernel0Tests(unittest.TestCase):
    def test_branch_schemas(self) -> None:
        self.assertEqual(
            parse_response("branch-a", '{"ranking":["C00","C01"]}'),
            {"ranking": ["C00", "C01"]},
        )
        for invalid in (
            '{"ranking":[]}',
            '{"ranking":["C00","C00"]}',
            '{"ranking":["C64"]}',
            '{"ranking":["C00"],"reason":"x"}',
        ):
            with self.assertRaises(CatalyticKernel0Error):
                parse_response("branch-a", invalid)
        profile = selected_unresolved_public_profile()
        carrier = build_carrier(profile)
        self.assertEqual(
            parse_response(
                "borrow",
                json.dumps({"carrier_id": carrier["carrier_id"]}),
                profile=profile,
                carrier_id=carrier["carrier_id"],
            ),
            {"carrier_id": carrier["carrier_id"]},
        )

    def test_complementary_shard_isolation(self) -> None:
        historical = build_carrier()
        self.assertEqual(
            historical["carrier_content_sha256"],
            "5A5C9AAF6B7830986957D8D4D6EEF6EE133B1FC320A706E5ADF315BDCCE37454",
        )
        self.assertEqual(
            historical["carrier_root_sha256"],
            "48E9EDDF63D9EF5B355C2EBEB150A451E43B8C28C3917A08D1CC4D6965209123",
        )
        carrier = json.loads(historical["carrier_root"])
        encoded = json.dumps(carrier, sort_keys=True)
        self.assertEqual(
            set(carrier),
            {
                "carrier_id",
                "task_definition",
                "candidate_ids",
                "candidate_programs",
                "kernel_instructions",
                "carrier_content_sha256",
            },
        )
        self.assertNotIn("public_examples", encoded)
        self.assertTrue(all("display" not in item for item in carrier["candidate_programs"]))
        left, right = build_public_shard("branch-a"), build_public_shard("branch-b")
        self.assertEqual(left["example_ids"], ["public-example-1", "public-example-2", "public-example-3"])
        self.assertEqual(right["example_ids"], ["public-example-3", "public-example-4", "public-example-5"])
        self.assertEqual(left["public_examples"][2], right["public_examples"][0])
        profile = selected_unresolved_public_profile()
        profile_left = build_public_shard("branch-a", profile)
        profile_right = build_public_shard("branch-b", profile)
        self.assertEqual(profile_left["example_ids"], ["public-example-1", "public-example-2", "public-example-4"])
        self.assertEqual(profile_right["example_ids"], ["public-example-2", "public-example-3", "public-example-5"])
        self.assertEqual(
            set(profile_left["example_ids"]) & set(profile_right["example_ids"]),
            {"public-example-2"},
        )

    def test_no_protected_data_leak(self) -> None:
        profile = selected_unresolved_public_profile()
        carrier = build_carrier(profile)
        artifacts: dict[str, dict[str, Any]] = {}
        payloads: dict[str, dict[str, Any]] = {}
        for request_id in ("borrow", "branch-a", "branch-b"):
            payload = build_model_request(request_id, carrier=carrier, artifacts=artifacts)
            payloads[request_id] = payload
            lowered = json.dumps(payload, sort_keys=True).casefold()
            self.assertNotIn("hidden_examples", lowered)
            self.assertNotIn("answer_candidate_id", lowered)
            if request_id == "branch-a":
                artifacts[request_id] = normalize_branch(request_id, ["C42", "C56"], profile)
            if request_id == "branch-b":
                artifacts[request_id] = normalize_branch(request_id, ["C09", "C34", "C42"], profile)
        transform = normalize_transform(
            artifacts["branch-a"],
            artifacts["branch-b"],
            operator="reconcile",
            ranking=["C42", "C56", "C09"],
            profile=profile,
        )
        artifacts["transform"] = transform
        artifacts["extract"] = normalize_extraction("C42", transform, profile)
        for request_id in ("transform", "extract", "restore"):
            payloads[request_id] = build_model_request(
                request_id, carrier=carrier, artifacts=artifacts
            )
        for request_id, payload in payloads.items():
            lowered = json.dumps(payload, sort_keys=True).casefold()
            self.assertNotIn("hidden_examples", lowered, request_id)
            self.assertNotIn("answer_candidate_id", lowered, request_id)
            self.assertNotIn("full_public_argmax_set", lowered, request_id)
            self.assertNotIn("unique_full_public_winner", lowered, request_id)
        branch_a_assignment = json.loads(payloads["branch-a"]["messages"][1]["content"])
        branch_b_assignment = json.loads(payloads["branch-b"]["messages"][1]["content"])
        restore_assignment = json.loads(payloads["restore"]["messages"][1]["content"])
        transform_assignment = json.loads(
            payloads["transform"]["messages"][1]["content"]
        )
        self.assertEqual(set(branch_a_assignment), {"request_id", "instruction", "evidence_shard"})
        self.assertEqual(set(branch_b_assignment), {"request_id", "instruction", "evidence_shard"})
        self.assertEqual(set(restore_assignment), {"request_id", "carrier_id", "instruction"})
        self.assertEqual(
            transform_assignment["parent_artifacts"],
            [artifacts["branch-a"], artifacts["branch-b"]],
        )
        suite = build_frozen_task_suite()
        projections = [task.public_projection() for task in suite.tasks]
        projections[0] = {**projections[0], "hidden_examples": []}
        with self.assertRaises(PublicCarrierScanError):
            scan_public_projections(
                projections,
                task_suite_sha256=EXPECTED_SUITE_SHA256,
            )

    def test_parent_a_commitment_only_projection(self) -> None:
        profile = selected_unresolved_public_profile()
        carrier = build_carrier(profile)
        branch_a = normalize_branch("branch-a", ["C00", "C01", "C02"], profile)
        branch_b = normalize_branch("branch-b", ["C00", "C01", "C02"], profile)
        artifacts = {"branch-a": branch_a, "branch-b": branch_b}
        receipt = build_parent_a_commitment_receipt(branch_a, profile)
        self.assertEqual(
            set(receipt),
            {
                "artifact_id",
                "artifact_sha256",
                "carrier_profile_id",
                "projection_mode",
                "informative_content_withheld",
            },
        )
        self.assertNotIn(
            "C42",
            [value for key, value in receipt.items() if key != "artifact_sha256"],
        )
        payload = build_model_request(
            "transform",
            carrier=carrier,
            artifacts=artifacts,
            control=PARENT_A_INFORMATION_DELETION_CONTROL,
        )
        assignment = json.loads(payload["messages"][1]["content"])
        self.assertEqual(assignment["parent_artifacts"][0], receipt)
        self.assertEqual(assignment["parent_artifacts"][1], branch_b)
        self.assertNotEqual(assignment["parent_artifacts"][0], branch_a)
        evidence = validate_parent_a_information_deletion_projection(
            payload,
            carrier=carrier,
            artifacts=artifacts,
        )
        self.assertTrue(evidence["projection_verified"])
        self.assertTrue(evidence["branch_b_full_artifact_unchanged"])
        self.assertEqual(
            hashlib.sha256(
                json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest().upper(),
            "C34B70F9F574DBC33BD2ED47644032C9976375680615180DDA6721383A6CF1BA",
        )
        self.assertEqual(
            evidence["blinded_parent_receipt_sha256"],
            "714789D52A0AB4A1E465789C681E9ACDB7CB1BCE97BA45ED323E9CE07437FED7",
        )
        self.assertEqual(
            evidence["model_visible_parent_projection_sha256"],
            "0CA75F828ABEE5874A5D951555CBC87EA2CF4BB7352BEE0D67D2DB8C56DB411E",
        )

        branch_b_receipt = build_parent_b_commitment_receipt(branch_b, profile)
        self.assertEqual(set(branch_b_receipt), set(receipt))
        self.assertEqual(branch_b_receipt["artifact_id"], "branch-b")
        for forbidden in (
            "ranking",
            "public_argmax_set",
            "shard_scores",
            "public_top_score",
            "public_plateau_gap",
            "public_shard_ids",
            "public_argmax_evidence",
        ):
            self.assertNotIn(forbidden, branch_b_receipt)
        self.assertNotIn(
            "C42",
            [
                value
                for key, value in branch_b_receipt.items()
                if key != "artifact_sha256"
            ],
        )
        branch_b_payload = build_model_request(
            "transform",
            carrier=carrier,
            artifacts=artifacts,
            control=PARENT_B_INFORMATION_DELETION_CONTROL,
        )
        branch_b_assignment = json.loads(
            branch_b_payload["messages"][1]["content"]
        )
        self.assertEqual(branch_b_assignment["parent_artifacts"][0], branch_a)
        self.assertEqual(
            branch_b_assignment["parent_artifacts"][1], branch_b_receipt
        )
        self.assertNotEqual(
            branch_b_assignment["parent_artifacts"][1], branch_b
        )
        branch_b_evidence = validate_parent_b_information_deletion_projection(
            branch_b_payload,
            carrier=carrier,
            artifacts=artifacts,
        )
        self.assertTrue(branch_b_evidence["projection_verified"])
        self.assertTrue(branch_b_evidence["branch_a_full_artifact_unchanged"])
        self.assertTrue(
            branch_b_evidence["branch_b_informative_content_withheld"]
        )

    def test_exact_two_parent_transform_binding(self) -> None:
        left = normalize_branch("branch-a", ["C00", "C01", "C02"])
        right = normalize_branch("branch-b", ["C01", "C00", "C02"])
        transform = normalize_transform(left, right, operator="reconcile", ranking=["C01", "C02", "C00"])
        self.assertEqual(transform["parent_artifact_sha256"], [left["artifact_sha256"], right["artifact_sha256"]])
        self.assertEqual(len(transform["dag_edges"]), 6)
        self.assertEqual({item["parent_artifact_id"] for item in transform["dag_edges"]}, {"branch-a", "branch-b"})

    def test_parent_a_control_classification(self) -> None:
        profile = selected_unresolved_public_profile()
        carrier = build_carrier(profile)
        branch_a = normalize_branch("branch-a", ["C00", "C01", "C02"], profile)
        branch_b = normalize_branch("branch-b", ["C00", "C01", "C02"], profile)
        artifacts = {"branch-a": branch_a, "branch-b": branch_b}
        payload = build_model_request(
            "transform",
            carrier=carrier,
            artifacts=artifacts,
            control=PARENT_A_INFORMATION_DELETION_CONTROL,
        )
        intervention = validate_parent_a_information_deletion_projection(
            payload, carrier=carrier, artifacts=artifacts
        )
        recovered_transform = normalize_transform(
            branch_a,
            branch_b,
            operator="combine",
            ranking=["C42", "C56", "C09"],
            profile=profile,
        )
        recovered_extract = normalize_extraction("C42", recovered_transform, profile)
        self.assertEqual(
            classify_parent_a_information_control(
                branch_a,
                branch_b,
                recovered_transform,
                recovered_extract,
                intervention,
                restoration_passed=True,
                completed_request_count=6,
                profile=profile,
            ),
            "PARENT_A_INFORMATION_NOT_SHOWN_NECESSARY",
        )
        blocked_transform = normalize_transform(
            branch_a,
            branch_b,
            operator="combine",
            ranking=["C09", "C34", "C42"],
            profile=profile,
        )
        blocked_extract = normalize_extraction("C09", blocked_transform, profile)
        self.assertEqual(
            classify_parent_a_information_control(
                branch_a,
                branch_b,
                blocked_transform,
                blocked_extract,
                intervention,
                restoration_passed=True,
                completed_request_count=6,
                profile=profile,
            ),
            "PARENT_A_INFORMATION_NECESSITY_SUPPORTED",
        )
        self.assertEqual(
            classify_parent_a_information_control(
                branch_a,
                branch_b,
                blocked_transform,
                blocked_extract,
                {**intervention, "projection_verified": False},
                restoration_passed=True,
                completed_request_count=6,
                profile=profile,
            ),
            "CAUSAL_CONTROL_INCONCLUSIVE",
        )
        branch_b_payload = build_model_request(
            "transform",
            carrier=carrier,
            artifacts=artifacts,
            control=PARENT_B_INFORMATION_DELETION_CONTROL,
        )
        branch_b_intervention = validate_parent_b_information_deletion_projection(
            branch_b_payload,
            carrier=carrier,
            artifacts=artifacts,
        )
        self.assertEqual(
            classify_parent_b_information_control(
                branch_a,
                branch_b,
                recovered_transform,
                recovered_extract,
                branch_b_intervention,
                restoration_passed=True,
                completed_request_count=6,
                profile=profile,
            ),
            "PARENT_B_INFORMATION_NOT_SHOWN_NECESSARY",
        )
        self.assertEqual(
            classify_parent_b_information_control(
                branch_a,
                branch_b,
                blocked_transform,
                blocked_extract,
                branch_b_intervention,
                restoration_passed=True,
                completed_request_count=6,
                profile=profile,
            ),
            "PARENT_B_INFORMATION_NECESSITY_SUPPORTED",
        )
        self.assertEqual(
            classify_parent_b_information_control(
                branch_a,
                branch_b,
                blocked_transform,
                blocked_extract,
                {
                    **branch_b_intervention,
                    "branch_a_full_artifact_unchanged": False,
                },
                restoration_passed=True,
                completed_request_count=6,
                profile=profile,
            ),
            "CAUSAL_CONTROL_INCONCLUSIVE",
        )

    def test_deterministic_rank_delta_derivation(self) -> None:
        delta = derive_rank_delta(["C00", "C01", "C02"], ["C01", "C03", "C00"])
        self.assertEqual(delta["promoted"], ["C01"])
        self.assertEqual(delta["demoted"], ["C00"])
        self.assertEqual(delta["introduced"], ["C03"])
        self.assertEqual(delta["removed"], ["C02"])
        self.assertEqual(delta, derive_rank_delta(["C00", "C01", "C02"], ["C01", "C03", "C00"]))
        tier_2 = _scan_profile(
            task_index=0,
            task_id="score-fixture-only",
            rows=(
                {"candidate_id": "C00", "public_pass_vector": [True, True, False, True, True]},
                {"candidate_id": "C01", "public_pass_vector": [True, False, True, True, False]},
                {"candidate_id": "C02", "public_pass_vector": [True, True, False, False, False]},
                {"candidate_id": "C03", "public_pass_vector": [False, False, False, True, True]},
            ),
            branch_a=(0, 1, 2),
            branch_b=(2, 3, 4),
        )
        self.assertEqual(tier_2["eligible_tier"], 2)
        self.assertEqual(tier_2["support_intersection"], ["C00", "C01"])
        self.assertEqual(tier_2["full_support"], ["C00"])
        self.assertEqual(tier_2["joint_public_support"], ["C00"])
        self.assertTrue(tier_2["branch_a_exclusive_contributes"])
        self.assertTrue(tier_2["branch_b_exclusive_contributes"])

    def test_extraction_must_select_from_transform(self) -> None:
        left = normalize_branch("branch-a", ["C00", "C01", "C02"])
        right = normalize_branch("branch-b", ["C01", "C00", "C02"])
        transform = normalize_transform(left, right, operator="refine", ranking=["C01", "C02", "C00"])
        extraction = normalize_extraction("C01", transform)
        self.assertEqual(extraction["transform_artifact_sha256_consumed"], transform["artifact_sha256"])
        with self.assertRaises(CatalyticKernel0Error):
            parse_response("extract", '{"candidate_id":"C03"}', transform_artifact=transform)
        first = selected_unresolved_public_profile()
        second = selected_unresolved_public_profile()
        self.assertEqual(first, second)
        self.assertEqual(first["eligibility_tier"], 1)
        self.assertGreater(first["scan_population"]["tier_1_eligible"], 0)

    def test_public_unresolved_profile_selection(self) -> None:
        profile = selected_unresolved_public_profile()
        self.assertEqual(profile["profile_id"], PROFILE_ID)
        self.assertEqual(profile["task_id"], "cs1-task-05")
        self.assertEqual(profile["eligibility_tier"], 1)
        self.assertEqual(profile["public_argmax_sets"]["branch-a"], ["C42", "C56"])
        self.assertEqual(profile["public_argmax_sets"]["branch-b"], ["C09", "C34", "C42"])
        self.assertEqual(profile["support_intersection"], ["C42"])
        self.assertEqual(profile["full_public_argmax_set"], ["C42"])
        self.assertTrue(profile["support_exclusive"]["branch-a"])
        self.assertTrue(profile["support_exclusive"]["branch-b"])
        self.assertTrue(all(2 <= len(value) <= 3 for value in profile["public_argmax_sets"].values()))
        self.assertEqual(profile["full_public_margin"], 1)
        self.assertEqual(min(profile["public_plateau_gaps"].values()), 1)
        self.assertEqual(
            profile["scan_sha256"],
            "77B7306249DDE9188C327B615CBE95DAC3A5AC7D778AAB189CFFD203A6D40DF2",
        )
        self.assertEqual(
            profile["public_score_matrix_sha256"],
            "F2758458B3302F9CCE4A0BB719A14B1130299A31FDA2201FB12CBEED1BD20A63",
        )

    def test_unresolved_branch_metadata_projection(self) -> None:
        profile = selected_unresolved_public_profile()
        left = normalize_branch("branch-a", ["C42", "C56"], profile)
        right = normalize_branch("branch-b", ["C09", "C34", "C42"], profile)
        for branch_id, artifact in (("branch-a", left), ("branch-b", right)):
            self.assertEqual(artifact["public_argmax_set"], profile["public_argmax_sets"][branch_id])
            self.assertEqual(artifact["public_top_score"], 3)
            self.assertEqual(artifact["public_plateau_gap"], 1)
            self.assertTrue(artifact["model_ranking_contains_public_argmax_set"])
            self.assertEqual(
                [item["candidate_id"] for item in artifact["public_argmax_evidence"]],
                artifact["public_argmax_set"],
            )
        transform = normalize_transform(
            left,
            right,
            operator="reconcile",
            ranking=["C42", "C56", "C09"],
            profile=profile,
        )
        extraction = normalize_extraction("C42", transform, profile)
        relation = unresolved_relation_observables(profile, left, right, transform, extraction)
        self.assertEqual(relation["branch_support_intersection"], ["C42"])
        self.assertEqual(relation["uncertainty_before"]["branch_a_support_size"], 2)
        self.assertEqual(relation["uncertainty_before"]["branch_b_support_size"], 3)
        self.assertEqual(relation["uncertainty_after"]["resolved_support_size"], 1)
        self.assertTrue(relation["relational_uncertainty_reduced"])

    def test_carrier_restoration_and_six_request_runtime(self) -> None:
        from holostate_live import build_parser

        parsed = build_parser().parse_args(
            [
                "run-catalytic-kernel-0",
                "--model",
                "model.gguf",
                "--run-id",
                "ck0-parser",
                "--carrier-profile",
                PROFILE_ID,
            ]
        )
        self.assertEqual(parsed.handler.__name__, "command_run_catalytic_kernel_0")
        self.assertEqual(parsed.carrier_profile, PROFILE_ID)
        control_parsed = build_parser().parse_args(
            [
                "run-catalytic-kernel-0",
                "--model",
                "model.gguf",
                "--run-id",
                "ck0-control-parser",
                "--carrier-profile",
                PROFILE_ID,
                "--control",
                PARENT_A_INFORMATION_DELETION_CONTROL,
            ]
        )
        self.assertEqual(
            control_parsed.control, PARENT_A_INFORMATION_DELETION_CONTROL
        )
        branch_b_control_parsed = build_parser().parse_args(
            [
                "run-catalytic-kernel-0",
                "--model",
                "model.gguf",
                "--run-id",
                "ck0-branch-b-control-parser",
                "--carrier-profile",
                PROFILE_ID,
                "--control",
                PARENT_B_INFORMATION_DELETION_CONTROL,
            ]
        )
        self.assertEqual(
            branch_b_control_parsed.control,
            PARENT_B_INFORMATION_DELETION_CONTROL,
        )
        adapter = FakeAdapter(unresolved_profile=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "state") as temporary:
            result = run_catalytic_kernel_0(
                {
                    "run_id": "ck0-test-complete",
                    "binary": "X",
                    "model": "Y",
                    "carrier_profile": PROFILE_ID,
                },
                adapter=adapter,
                repository_root=ROOT,
                state_root=temporary,
            )
            result_path = Path(temporary) / "ck0-test-complete" / "result.json"
            persisted = result_path.read_text(encoding="utf-8")
        self.assertEqual(adapter.pool_sizes, [1])
        self.assertEqual(adapter.request_ids, list(REQUEST_IDS))
        self.assertEqual(result["completed_model_responses"], 6)
        self.assertTrue(result["restoration"]["passed"])
        self.assertEqual(result["lease_accounting"]["active_leases"], 0)
        self.assertEqual(result["lease_accounting"]["lease_count"], 6)
        self.assertEqual(result["lease_accounting"]["maximum_concurrent_leases"], 1)
        self.assertEqual(result["mechanism_classification"], "CATALYTIC_KERNEL_VISIBLE")
        self.assertFalse(any(key.startswith("control_") for key in result))
        self.assertNotIn("non_production", result)
        self.assertEqual(result["carrier"]["profile"]["profile_id"], PROFILE_ID)
        self.assertTrue(result["restoration"]["historical_ck0_preserved"])
        self.assertIn("RELATIONAL_UNCERTAINTY_REDUCED", result["diagnostics"])
        self.assertNotIn("RAW_SENTINEL", persisted)
        control_adapter = FakeAdapter(unresolved_profile=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "state") as temporary:
            control_result = run_catalytic_kernel_0(
                {
                    "run_id": PARENT_B_CONTROL_RUN_ID,
                    "binary": "X",
                    "model": "Y",
                    "carrier_profile": PROFILE_ID,
                    "control": PARENT_B_INFORMATION_DELETION_CONTROL,
                },
                adapter=control_adapter,
                repository_root=ROOT,
                state_root=temporary,
            )
        self.assertEqual(control_adapter.request_ids, list(REQUEST_IDS))
        self.assertIsNone(control_result["mechanism_classification"])
        self.assertEqual(
            control_result["control_classification"],
            "PARENT_B_INFORMATION_NOT_SHOWN_NECESSARY",
        )
        self.assertIsNone(control_result["relational_observables"])
        self.assertTrue(
            control_result["control_intervention"]["projection_verified"]
        )
        self.assertEqual(
            control_result["control_preregistration"]["execution_run_id"],
            PARENT_B_CONTROL_RUN_ID,
        )
        transform_payload = control_adapter.payloads[3]
        transform_assignment = json.loads(
            transform_payload["messages"][1]["content"]
        )
        self.assertEqual(
            transform_assignment["parent_artifacts"][0]["artifact_id"],
            "branch-a",
        )
        self.assertIn("ranking", transform_assignment["parent_artifacts"][0])
        self.assertEqual(
            set(transform_assignment["parent_artifacts"][1]),
            {
                "artifact_id",
                "artifact_sha256",
                "carrier_profile_id",
                "projection_mode",
                "informative_content_withheld",
            },
        )

    def test_collapse_versus_visible_classification(self) -> None:
        historical_a = normalize_branch("branch-a", ["C58", "C56", "C08"])
        historical_b = normalize_branch("branch-b", ["C58", "C56", "C41"])
        historical_transform = normalize_transform(
            historical_a,
            historical_b,
            operator="combine",
            ranking=["C58", "C08", "C56"],
        )
        historical_extract = normalize_extraction("C58", historical_transform)
        self.assertEqual(
            classify_kernel(
                historical_a,
                historical_b,
                historical_transform,
                historical_extract,
                restoration_passed=True,
                completed_request_count=6,
            ),
            "CATALYTIC_KERNEL_COLLAPSED",
        )
        profile = selected_unresolved_public_profile()
        left = normalize_branch("branch-a", ["C42", "C56"], profile)
        right = normalize_branch("branch-b", ["C09", "C34", "C42"], profile)
        resolved = normalize_transform(
            left,
            right,
            operator="reconcile",
            ranking=["C42", "C56", "C09"],
            profile=profile,
        )
        extracted = normalize_extraction("C42", resolved, profile)
        self.assertEqual(
            classify_kernel(
                left,
                right,
                resolved,
                extracted,
                restoration_passed=True,
                completed_request_count=6,
                profile=profile,
            ),
            "CATALYTIC_KERNEL_VISIBLE",
        )
        unresolved = normalize_transform(
            left,
            right,
            operator="reconcile",
            ranking=["C56", "C42", "C09"],
            profile=profile,
        )
        wrong_extract = normalize_extraction("C56", unresolved, profile)
        self.assertEqual(
            classify_kernel(
                left,
                right,
                unresolved,
                wrong_extract,
                restoration_passed=True,
                completed_request_count=6,
                profile=profile,
            ),
            "CATALYTIC_KERNEL_COLLAPSED",
        )


if __name__ == "__main__":
    unittest.main()
