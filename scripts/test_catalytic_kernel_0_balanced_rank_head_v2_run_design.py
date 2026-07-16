#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2 as v2
import catalytic_kernel_0_balanced_rank_head_v2_authority as authority
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration
import catalytic_kernel_0_balanced_rank_head_v2_run_design as design


class RankHeadV2RunDesignTests(unittest.TestCase):
    def _fixture(self, repository: Path, *, classification: str, published: bool, tamper: bool = False):
        source_private = balanced.PrivateBinding.from_secret(
            bytes(range(32)), balanced.BINDING_1
        )
        spec = integration.run_spec(integration.BINDING_1_RUN_ID)
        private = integration.runtime_private_from_source(source_private, spec)
        runtime = integration.RankHeadV2Runtime(
            repository=repository, spec=spec, private=private
        )
        branch_a = runtime.normalize_branch("branch-a", ["K00", "K01", "K02"])
        branch_b = runtime.normalize_branch("branch-b", ["K00", "K01", "K02"])
        winner = private.internal_to_alias[balanced.EXPECTED_FULL_SUPPORT[0]]
        alternatives = [alias for alias in balanced.ALIASES if alias != winner]
        transform = runtime.normalize_transform(
            "reconcile", [winner, alternatives[0], alternatives[1]]
        )
        extraction = runtime.deterministic_extract(transform)
        if tamper:
            transform = dict(transform)
            transform["artifact_commitment"] = "0" * 64
        run_projection = {
            "artifact_sha256": "A" * 64,
            "document_sha256": "B" * 64,
            "implementation_binding_sha256": "C" * 64,
        }
        static_projection = {
            "artifact_sha256": "D" * 64,
            "document_sha256": "E" * 64,
            "design_contract_sha256": "F" * 64,
        }
        carrier = v2.build_v2_carrier()
        authority_body = {
            "authorized_commit": "1" * 40,
            "run_design_artifact_sha256": run_projection["artifact_sha256"],
            "run_design_document_sha256": run_projection["document_sha256"],
            "run_design_implementation_binding_sha256": run_projection[
                "implementation_binding_sha256"
            ],
            "static_preregistration_artifact_sha256": static_projection[
                "artifact_sha256"
            ],
            "static_preregistration_document_sha256": static_projection[
                "document_sha256"
            ],
            "static_design_contract_sha256": static_projection[
                "design_contract_sha256"
            ],
            "carrier_id": carrier["carrier_id"],
            "carrier_root_sha256": carrier["carrier_root_sha256"],
            "model_sha256": "2" * 64,
            "binary_sha256": "3" * 64,
        }
        authority_evidence = {
            "authority": authority_body,
            "authority_receipt_hmac": "4" * 64,
            "authority_receipt_sha256": "5" * 64,
            "consumed": True,
            "retry_allowed": False,
        }
        historical_cib0 = "6" * 64
        historical_ck0 = "7" * 64
        root = repository / design.STATE_ROOT / integration.BINDING_1_RUN_ID
        root.mkdir(parents=True)
        manifest = {
            "run_id": integration.BINDING_1_RUN_ID,
            "run_ordinal": 1,
            "source_binding": "binding-1",
            "run_design": run_projection,
            "static_preregistration": static_projection,
            "carrier": {
                "carrier_id": carrier["carrier_id"],
                "carrier_content_sha256": carrier["carrier_content_sha256"],
                "carrier_root_sha256": carrier["carrier_root_sha256"],
            },
            "external_live_authority": authority_evidence,
            "preflight": {
                "stable": {"head": "1" * 40},
                "model_identity": {"sha256": "2" * 64},
                "binary_identity": {"sha256": "3" * 64},
            },
            "historical_cib0_tree_sha256": historical_cib0,
            "historical_ck0_tree_sha256": historical_ck0,
        }
        result = {
            "run_id": integration.BINDING_1_RUN_ID,
            "run_ordinal": 1,
            "source_binding": "binding-1",
            "status": "complete",
            "terminal_classification": classification,
            "completed_model_responses": 5,
            "branch_a": branch_a,
            "branch_b": branch_b,
            "transform": transform,
            "deterministic_extraction": extraction,
            "restoration": {
                "passed": True,
                "historical_cib0_preserved": True,
                "historical_ck0_preserved": True,
            },
            "cleanup": {"passed": True},
            "postflight_custody": {"passed": True},
            "lease_accounting": {
                "lease_count": 5,
                "maximum_concurrent_leases": 1,
                "active_leases": 0,
            },
            "external_live_authority": authority_evidence,
        }
        manifest_path = root / "manifest.json"
        result_path = root / "result.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        result_path.write_text(json.dumps(result), encoding="utf-8")
        closure = {
            "run_id": integration.BINDING_1_RUN_ID,
            "terminal_classification": classification,
            "manifest_sha256": design.sha256_bytes(manifest_path.read_bytes()),
            "result_sha256": design.sha256_bytes(result_path.read_bytes()),
            "run_lock_absent": True,
            "run_design_document_sha256": run_projection["document_sha256"],
            "static_preregistration_document_sha256": static_projection[
                "document_sha256"
            ],
            "external_live_authority": authority_evidence,
            "terminal_custody": {"passed": True},
            "historical_cib0_tree_sha256": historical_cib0,
            "historical_ck0_tree_sha256": historical_ck0,
        }
        closure_path = root / "closure.json"
        closure_path.write_text(json.dumps(closure), encoding="utf-8")
        if published:
            lab = repository / "lab"
            lab.mkdir(exist_ok=True)
            record = {
                "configuration": {"run_id": integration.BINDING_1_RUN_ID},
                "metrics_after": {
                    "terminal_classification": classification,
                    "manifest_sha256": design.sha256_bytes(manifest_path.read_bytes()),
                    "result_sha256": design.sha256_bytes(result_path.read_bytes()),
                    "closure_sha256": design.sha256_bytes(closure_path.read_bytes()),
                },
            }
            (lab / "results.jsonl").write_text(
                json.dumps(record) + "\n", encoding="utf-8"
            )
            subprocess.run(
                ["git", "init", "--quiet"],
                cwd=repository,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "add", "--", "lab/results.jsonl"],
                cwd=repository,
                check=True,
                capture_output=True,
            )
        patches = (
            mock.patch.object(design, "validate_run_design", return_value=run_projection),
            mock.patch.object(v2, "validate_preregistration", return_value=static_projection),
            mock.patch.object(
                integration, "runtime_private_from_repository", return_value=private
            ),
            mock.patch.object(
                authority,
                "verify_authority_receipt_for_run",
                return_value=authority_evidence,
            ),
        )
        return patches

    def test_exact_sixteen_file_binding(self) -> None:
        design.require_exact_implementation_paths(
            design.REQUIRED_IMPLEMENTATION_PATHS
        )
        self.assertEqual(len(design.REQUIRED_IMPLEMENTATION_PATHS), 16)
        with self.assertRaisesRegex(
            design.RankHeadV2RunDesignError,
            "exactly sixteen files",
        ):
            design.require_exact_implementation_paths(
                design.REQUIRED_IMPLEMENTATION_PATHS[:-1]
            )

    def test_binding_2_runtime_is_fail_closed_without_predecessor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            with self.assertRaisesRegex(
                design.RankHeadV2RunDesignError,
                "predecessor evidence is absent",
            ):
                design.require_binding_1_v2_terminal_visible(repository)

    def test_binding_1_visible_predecessor_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            patches = self._fixture(
                repository,
                classification=integration.VISIBLE_CLASSIFICATION,
                published=True,
            )
            with patches[0], patches[1], patches[2], patches[3]:
                admitted = design.require_binding_1_v2_terminal_visible(repository)
            self.assertEqual(
                admitted["terminal_classification"],
                integration.VISIBLE_CLASSIFICATION,
            )
            self.assertTrue(admitted["authority_receipt_verified"])
            self.assertEqual(admitted["publication"]["layout"], "split-experiment-record")

    def test_unpublished_predecessor_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            patches = self._fixture(
                repository,
                classification=integration.VISIBLE_CLASSIFICATION,
                published=False,
            )
            with patches[0], patches[1], patches[2], patches[3]:
                with self.assertRaisesRegex(
                    design.RankHeadV2RunDesignError,
                    "publication ledger is absent",
                ):
                    design.require_binding_1_v2_terminal_visible(repository)

    def test_malformed_predecessor_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            patches = self._fixture(
                repository,
                classification=integration.VISIBLE_CLASSIFICATION,
                published=True,
                tamper=True,
            )
            with patches[0], patches[1], patches[2], patches[3]:
                with self.assertRaisesRegex(
                    design.RankHeadV2RunDesignError,
                    "artifacts do not verify",
                ):
                    design.require_binding_1_v2_terminal_visible(repository)

    def test_duplicate_publication_records_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            patches = self._fixture(
                repository,
                classification=integration.VISIBLE_CLASSIFICATION,
                published=True,
            )
            ledger = repository / "lab" / "results.jsonl"
            ledger.write_text(
                ledger.read_text(encoding="utf-8") * 2,
                encoding="utf-8",
            )
            with patches[0], patches[1], patches[2], patches[3]:
                with self.assertRaisesRegex(
                    design.RankHeadV2RunDesignError,
                    "exactly one published visible record",
                ):
                    design.require_binding_1_v2_terminal_visible(repository)

    def test_legacy_colocated_publication_record_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            patches = self._fixture(
                repository,
                classification=integration.VISIBLE_CLASSIFICATION,
                published=True,
            )
            ledger = repository / "lab" / "results.jsonl"
            split = json.loads(ledger.read_text(encoding="utf-8"))
            ledger.write_text(
                json.dumps(
                    {
                        "run_id": split["configuration"]["run_id"],
                        **split["metrics_after"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with patches[0], patches[1], patches[2], patches[3]:
                with self.assertRaisesRegex(
                    design.RankHeadV2RunDesignError,
                    "requires a split experiment record",
                ):
                    design.require_binding_1_v2_terminal_visible(repository)

    def test_nonvisible_predecessor_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            patches = self._fixture(
                repository,
                classification=integration.COLLAPSED_CLASSIFICATION,
                published=True,
            )
            with patches[0], patches[1], patches[2], patches[3]:
                with self.assertRaisesRegex(
                    design.RankHeadV2RunDesignError,
                    "not terminal visible",
                ):
                    design.require_binding_1_v2_terminal_visible(repository)

    def test_run_design_reserves_only_ordered_full_runs(self) -> None:
        self.assertEqual(
            integration.RUN_ORDER,
            (
                integration.BINDING_1_RUN_ID,
                integration.BINDING_2_RUN_ID,
            ),
        )
        first = integration.RUN_SPECS[integration.BINDING_1_RUN_ID]
        second = integration.RUN_SPECS[integration.BINDING_2_RUN_ID]
        self.assertEqual(
            first.run_id,
            "ck0-balanced-v2-rank-head-b1-full-r2",
        )
        self.assertEqual(first.authorization_state, "separately-authorizable")
        self.assertEqual(second.predecessor_run_id, first.run_id)
        self.assertEqual(
            second.authorization_state,
            "unauthorized-until-binding-1-v2-r2-terminal-visible-and-published",
        )
        self.assertNotIn(
            integration.RETIRED_BINDING_1_RUN_ID,
            integration.RUN_ORDER,
        )

    def test_state_and_authority_namespaces_are_versioned(self) -> None:
        self.assertEqual(
            design.STATE_ROOT,
            "state/catalytic_kernel_0_rank_head_v2",
        )
        self.assertEqual(
            set(design.STATE_FILENAMES),
            {"manifest.json", "result.json", "closure.json", "run.lock"},
        )
        self.assertIn("rank_head_v2_authority", design.AUTHORITY_RECEIPT_TEMPLATE)
        self.assertIn("<run-id>", design.AUTHORITY_RECEIPT_TEMPLATE)

    def test_complete_surface_contains_authority_live_and_entrypoint(self) -> None:
        paths = set(design.REQUIRED_IMPLEMENTATION_PATHS)
        self.assertIn(
            "scripts/catalytic_kernel_0_balanced_rank_head_v2_authority.py",
            paths,
        )
        self.assertIn(
            "scripts/catalytic_kernel_0_balanced_rank_head_v2_live.py",
            paths,
        )
        self.assertIn(
            "scripts/catalytic_kernel_0_balanced_rank_head_v2_entrypoint.py",
            paths,
        )
        self.assertIn(
            "scripts/catalytic_kernel_0_balanced_rank_head_v2_cli.py",
            paths,
        )
        self.assertIn(
            "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_cli.py",
            paths,
        )

    def test_preconsumption_incident_reconstructs_exactly(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        incident = design.validate_preconsumption_incident(repository)
        self.assertEqual(
            incident["historical_run_id"],
            integration.RETIRED_BINDING_1_RUN_ID,
        )
        self.assertEqual(
            incident["replacement_run_id"],
            integration.BINDING_1_RUN_ID,
        )
        self.assertFalse(incident["runtime_authority_consumed"])
        self.assertFalse(incident["scientific_observation_performed"])


if __name__ == "__main__":
    unittest.main()
