#!/usr/bin/env python3

from __future__ import annotations

import copy
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import catalytic_kernel_0_balanced_opaque as balanced
from catalytic_kernel_0 import (
    PARENT_A_CONTROL_CLASSIFICATIONS,
    PARENT_B_CONTROL_CLASSIFICATIONS,
    build_carrier as build_historical_carrier,
)
from catalytic_kernel_0_carrier_scan import selected_unresolved_public_profile


ROOT = Path(__file__).resolve().parents[1]
CXX_RE = re.compile(r"(?<![A-Za-z0-9])C\d{2}(?![A-Za-z0-9])")


def runtime(run_id: str, secret: bytes = b"A" * 32) -> balanced.BalancedOpaqueRuntime:
    return balanced.BalancedOpaqueRuntime(
        repository=ROOT,
        run_id=run_id,
        private=balanced.PrivateBinding.from_secret(secret),
    )


def complete_artifacts(instance: balanced.BalancedOpaqueRuntime) -> dict[str, dict]:
    branch_a = instance.normalize_branch("branch-a", ["K00"])
    branch_b = instance.normalize_branch("branch-b", ["K01"])
    winner = instance.private.internal_to_alias["C34"]
    alternatives = sorted(
        (set(branch_a["support_aliases"]) | set(branch_b["support_aliases"]))
        - {winner}
    )
    transform = instance.normalize_transform("combine", [winner, *alternatives[:2]])
    extraction = instance.normalize_extraction(winner, transform)
    return {
        "branch-a": branch_a,
        "branch-b": branch_b,
        "transform": transform,
        "extract": extraction,
    }


class BalancedOpaqueCarrierTests(unittest.TestCase):
    def test_01_exact_task_03_geometry(self) -> None:
        profile, binding = balanced.build_profile_binding()
        self.assertEqual(profile["task_id"], "cs1-task-03")
        self.assertEqual(profile["branch_indices"], {"branch-a": [0, 1, 2], "branch-b": [2, 3, 4]})
        self.assertEqual(profile["support_sets"], {
            "branch-a": ["C02", "C31", "C34", "C38", "C53"],
            "branch-b": ["C16", "C34", "C46", "C51", "C60"],
        })
        self.assertEqual(profile["full_public_support"], ["C34"])
        self.assertEqual(profile["top_scores"], {"branch-a": 3, "branch-b": 3})
        self.assertEqual(profile["plateau_gaps"], {"branch-a": 1, "branch-b": 1})
        self.assertTrue(balanced.SHA256_RE.fullmatch(binding))

    def test_02_private_secret_path_and_reparse_rejection(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "state") as temporary:
            repository = Path(temporary)
            (repository / "state").mkdir()
            path = balanced.create_private_secret_once(repository)
            self.assertEqual(path.relative_to(repository).as_posix(), balanced.PRIVATE_SECRET_PATH)
            self.assertTrue(path.is_file())
            self.assertEqual(path.stat().st_size, 32)
            receipt = repository / balanced.PRIVATE_CREATION_RECEIPT_PATH
            self.assertTrue(receipt.is_file())
            self.assertLess(receipt.stat().st_size, 4096)
            binding = balanced._private_binding_from_repository(repository)
            self.assertTrue(
                balanced.SHA256_RE.fullmatch(
                    str(binding.creation_receipt_commitment)
                )
            )
            with self.assertRaises(balanced.BalancedOpaqueError):
                balanced.create_private_secret_once(repository)
        with tempfile.TemporaryDirectory(dir=ROOT / "state") as temporary:
            repository = Path(temporary)
            (repository / "state").mkdir()
            original = balanced._is_reparse

            def mark_state_as_reparse(path: Path) -> bool:
                return path == repository / "state" or original(path)

            with patch.object(balanced, "_is_reparse", side_effect=mark_state_as_reparse):
                with self.assertRaises(balanced.BalancedOpaqueError):
                    balanced.create_private_secret_once(repository)

    def test_03_alias_permutation_is_deterministic(self) -> None:
        _, profile_sha = balanced.build_profile_binding()
        first = balanced.derive_alias_mapping(b"B" * 32, profile_sha)
        second = balanced.derive_alias_mapping(b"B" * 32, profile_sha)
        self.assertEqual(first, second)
        self.assertEqual(set(first), set(balanced.ALIASES))
        self.assertEqual(set(first.values()), {f"C{index:02d}" for index in range(64)})
        self.assertEqual(
            balanced.derive_branch_alias_mapping(b"B" * 32, profile_sha, "branch-a"),
            balanced.derive_branch_alias_mapping(b"B" * 32, profile_sha, "branch-a"),
        )

    def test_04_different_secrets_produce_different_mappings(self) -> None:
        _, profile_sha = balanced.build_profile_binding()
        self.assertNotEqual(
            balanced.derive_alias_mapping(b"C" * 32, profile_sha),
            balanced.derive_alias_mapping(b"D" * 32, profile_sha),
        )

    def test_05_immutable_root_contains_no_private_profile_data(self) -> None:
        carrier = balanced.build_carrier()
        root = json.loads(carrier["carrier_root"])
        text = balanced.canonical_json_text(root)
        self.assertIsNone(CXX_RE.search(text))
        for forbidden in (
            "cs1-task-03", "profile_id", "task_id", "branch_shards",
            "candidate_programs", "public_examples", "support_sets",
            "full_public_winner", "task_suite_sha256", "scan_sha256",
            "public_score_matrix_sha256",
        ):
            self.assertNotIn(forbidden, text)

    def test_06_branch_assignments_are_opaque_and_branch_local(self) -> None:
        instance = runtime(balanced.FULL_RUN_ID)
        branch_a = instance.assignment("branch-a", {})
        branch_b = instance.assignment("branch-b", {})
        self.assertEqual(len(branch_a["evidence"]), 3)
        self.assertEqual(len(branch_b["evidence"]), 3)
        self.assertEqual(branch_a["evidence"][2], branch_b["evidence"][0])
        self.assertNotEqual(branch_a["evidence"][:2], branch_b["evidence"][:2])
        self.assertNotEqual(
            instance.private.branch_alias_to_internal["branch-a"],
            instance.private.alias_to_internal,
        )
        self.assertNotEqual(
            instance.private.branch_alias_to_internal["branch-a"],
            instance.private.branch_alias_to_internal["branch-b"],
        )
        for branch_id, assignment in (("branch-a", branch_a), ("branch-b", branch_b)):
            self.assertEqual(len(assignment["candidate_programs"]), 64)
            self.assertEqual(
                {item["candidate_alias"] for item in assignment["candidate_programs"]},
                set(balanced.ALIASES),
            )
            by_alias = {
                item["candidate_alias"]: item["branch_local_program"]["ordered_outputs"]
                for item in assignment["candidate_programs"]
            }
            internal_to_local = {
                internal: alias
                for alias, internal in instance.private.branch_alias_to_internal[branch_id].items()
            }
            support_outputs = {
                tuple(by_alias[internal_to_local[internal]])
                for internal in balanced.EXPECTED_SUPPORTS[branch_id]
            }
            self.assertEqual(len(support_outputs), 1)
            self.assertEqual(
                next(iter(support_outputs)),
                tuple(item["y"] for item in assignment["evidence"]),
            )
            self.assertNotIn("instructions", balanced.canonical_json_text(assignment))
            self.assertIsNone(CXX_RE.search(balanced.canonical_json_text(assignment)))

    def test_07_no_internal_candidate_enters_any_model_request(self) -> None:
        for run_id in balanced.RUN_MODES:
            payloads = balanced.static_model_visible_payloads(b"E" * 32, run_id)
            self.assertEqual(set(payloads), set(balanced.REQUEST_IDS))
            for payload in payloads.values():
                self.assertIsNone(CXX_RE.search(balanced.canonical_json_text(payload)))

    def test_08_normalized_artifacts_have_only_minimal_fields(self) -> None:
        instance = runtime(balanced.FULL_RUN_ID)
        branch = instance.normalize_branch("branch-a", ["K63", "K01"])
        transform = instance.normalize_transform("reconcile", ["K03", "K02"])
        self.assertEqual(set(branch), set(balanced.BRANCH_ARTIFACT_FIELDS))
        self.assertEqual(set(transform), set(balanced.TRANSFORM_ARTIFACT_FIELDS))
        self.assertEqual(branch["support_aliases"], sorted(branch["support_aliases"]))

    def test_09_model_rankings_and_programs_do_not_reach_transform(self) -> None:
        instance = runtime(balanced.FULL_RUN_ID)
        first = instance.normalize_branch("branch-a", ["K00"])
        second = instance.normalize_branch("branch-a", ["K63", "K62", "K61"])
        self.assertEqual(first, second)
        artifacts = {
            "branch-a": first,
            "branch-b": instance.normalize_branch("branch-b", ["K10"]),
        }
        assignment = instance.assignment("transform", artifacts)
        text = balanced.canonical_json_text(assignment)
        for forbidden in ("candidate_programs", "instructions", "evidence", "model_ranking"):
            self.assertNotIn(forbidden, text)
        self.assertEqual(assignment["parent_artifacts"], [artifacts["branch-a"], artifacts["branch-b"]])

    def test_10_commitments_are_run_and_stage_bound(self) -> None:
        private = balanced.PrivateBinding.from_secret(b"F" * 32)
        body = {"opaque": ["K00", "K01"]}
        keys = {run_id: private.run_key(run_id) for run_id in balanced.RUN_MODES}
        self.assertEqual(len(set(keys.values())), 3)
        full_key = keys[balanced.FULL_RUN_ID]
        delete_key = keys[balanced.DELETE_A_RUN_ID]
        self.assertNotEqual(
            balanced.artifact_commitment(full_key, "parent-0", body),
            balanced.artifact_commitment(delete_key, "parent-0", body),
        )
        self.assertNotEqual(
            balanced.artifact_commitment(full_key, "parent-0", body),
            balanced.artifact_commitment(full_key, "parent-1", body),
        )

    def test_11_commitment_verification_detects_tampering(self) -> None:
        instance = runtime(balanced.FULL_RUN_ID)
        artifact = instance.normalize_branch("branch-a", ["K00"])
        tampered = copy.deepcopy(artifact)
        replacement = next(alias for alias in balanced.ALIASES if alias not in tampered["support_aliases"])
        tampered["support_aliases"][0] = replacement
        tampered["support_aliases"].sort()
        with self.assertRaises(balanced.BalancedOpaqueError):
            instance.verify_branch_artifact(tampered)
        artifacts = complete_artifacts(instance)
        tampered_extraction = copy.deepcopy(artifacts["extract"])
        tampered_extraction["controller_private_evaluation"]["full_public_score"] = 0
        with self.assertRaises(balanced.BalancedOpaqueError):
            instance.verify_extraction_artifact(
                tampered_extraction, artifacts["transform"]
            )
        self.assertEqual(
            instance.classify(
                {**artifacts, "extract": tampered_extraction},
                completed_request_count=6,
                restoration_passed=True,
            ),
            "INCONCLUSIVE",
        )

    def test_12_deletion_receipts_are_exact_and_noninformative(self) -> None:
        for run_id, deleted_role in (
            (balanced.DELETE_A_RUN_ID, "parent-0"),
            (balanced.DELETE_B_RUN_ID, "parent-1"),
        ):
            instance = runtime(run_id)
            artifacts = {
                "branch-a": instance.normalize_branch("branch-a", ["K00"]),
                "branch-b": instance.normalize_branch("branch-b", ["K01"]),
            }
            parents = instance.assignment("transform", artifacts)["parent_artifacts"]
            receipt = next(parent for parent in parents if parent["artifact_role"] == deleted_role)
            self.assertEqual(set(receipt), set(balanced.DELETION_RECEIPT_FIELDS))
            self.assertEqual(receipt["projection_mode"], "commitment-only")
            self.assertTrue(receipt["informative_content_withheld"])

    def test_13_extraction_receives_only_opaque_transform_artifact(self) -> None:
        instance = runtime(balanced.FULL_RUN_ID)
        transform = instance.normalize_transform("refine", ["K04", "K05"])
        assignment = instance.assignment("extract", {"transform": transform})
        self.assertEqual(set(assignment), {"stage", "instruction", "transform_artifact"})
        self.assertEqual(
            assignment["transform_artifact"],
            {
                "ranking": transform["ranking"],
                "artifact_commitment": transform["artifact_commitment"],
            },
        )
        text = balanced.canonical_json_text(assignment)
        for forbidden in ("alias_mapping", "internal_candidate_id", "candidate_programs", "evidence"):
            self.assertNotIn(forbidden, text)
        self.assertIsNone(CXX_RE.search(text))

    def test_14_full_information_classification_law(self) -> None:
        instance = runtime(balanced.FULL_RUN_ID)
        artifacts = complete_artifacts(instance)
        self.assertEqual(
            instance.classify(artifacts, completed_request_count=6, restoration_passed=True),
            "BALANCED_OPAQUE_RELATIONAL_VISIBLE",
        )
        wrong = next(alias for alias in balanced.ALIASES if alias != instance.private.internal_to_alias["C34"])
        collapsed_transform = instance.normalize_transform("combine", [wrong])
        collapsed = {
            **artifacts,
            "transform": collapsed_transform,
            "extract": instance.normalize_extraction(wrong, collapsed_transform),
        }
        self.assertEqual(
            instance.classify(collapsed, completed_request_count=6, restoration_passed=True),
            "BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
        )
        self.assertEqual(
            instance.classify(artifacts, completed_request_count=5, restoration_passed=True),
            "INCONCLUSIVE",
        )

    def test_15_deletion_hit_and_dependence_classification_law(self) -> None:
        for run_id, hit, dependence in (
            (balanced.DELETE_A_RUN_ID, "PARENT_A_UNAIDED_EXCHANGEABLE_HIT", "PARENT_A_INFORMATION_DEPENDENCE_SUPPORTED"),
            (balanced.DELETE_B_RUN_ID, "PARENT_B_UNAIDED_EXCHANGEABLE_HIT", "PARENT_B_INFORMATION_DEPENDENCE_SUPPORTED"),
        ):
            instance = runtime(run_id)
            artifacts = complete_artifacts(instance)
            self.assertEqual(instance.classify(artifacts, completed_request_count=6, restoration_passed=True), hit)
            winner = instance.private.internal_to_alias["C34"]
            wrong = next(alias for alias in balanced.ALIASES if alias != winner)
            transform = instance.normalize_transform("combine", [wrong])
            changed = {
                **artifacts,
                "transform": transform,
                "extract": instance.normalize_extraction(wrong, transform),
            }
            self.assertEqual(instance.classify(changed, completed_request_count=6, restoration_passed=True), dependence)
            self.assertEqual(instance.classify(changed, completed_request_count=6, restoration_passed=False), "CAUSAL_CONTROL_INCONCLUSIVE")

    def test_16_historical_ck0_identities_and_classifications_are_unchanged(self) -> None:
        from holostate_live import _catalytic_kernel_0_result_succeeded

        default = build_historical_carrier()
        unresolved = build_historical_carrier(selected_unresolved_public_profile())
        self.assertEqual(default["carrier_content_sha256"], "5A5C9AAF6B7830986957D8D4D6EEF6EE133B1FC320A706E5ADF315BDCCE37454")
        self.assertEqual(default["carrier_root_sha256"], "48E9EDDF63D9EF5B355C2EBEB150A451E43B8C28C3917A08D1CC4D6965209123")
        self.assertEqual(unresolved["carrier_root_sha256"], "14EA07DE66F16D44FAAF6D7ADFF70E1B11953CB940133449B7B962F56C50221C")
        self.assertEqual(PARENT_A_CONTROL_CLASSIFICATIONS, (
            "PARENT_A_INFORMATION_NECESSITY_SUPPORTED",
            "PARENT_A_INFORMATION_NOT_SHOWN_NECESSARY",
            "CAUSAL_CONTROL_INCONCLUSIVE",
        ))
        self.assertEqual(PARENT_B_CONTROL_CLASSIFICATIONS, (
            "PARENT_B_INFORMATION_NECESSITY_SUPPORTED",
            "PARENT_B_INFORMATION_NOT_SHOWN_NECESSARY",
            "CAUSAL_CONTROL_INCONCLUSIVE",
        ))
        for classification in (
            "BALANCED_OPAQUE_RELATIONAL_VISIBLE",
            "BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
            "PARENT_A_INFORMATION_DEPENDENCE_SUPPORTED",
            "PARENT_A_UNAIDED_EXCHANGEABLE_HIT",
            "PARENT_B_INFORMATION_DEPENDENCE_SUPPORTED",
            "PARENT_B_UNAIDED_EXCHANGEABLE_HIT",
        ):
            self.assertTrue(
                _catalytic_kernel_0_result_succeeded(
                    {"status": "complete", "balanced_classification": classification},
                    balanced.PROFILE_ID,
                )
            )
        self.assertFalse(
            _catalytic_kernel_0_result_succeeded(
                {"status": "failed", "balanced_classification": "INCONCLUSIVE"},
                balanced.PROFILE_ID,
            )
        )


if __name__ == "__main__":
    unittest.main()
