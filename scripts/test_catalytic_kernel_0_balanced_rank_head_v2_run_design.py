#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import catalytic_kernel_0_balanced_rank_head_v2_integration as integration
import catalytic_kernel_0_balanced_rank_head_v2_run_design as design


class RankHeadV2RunDesignTests(unittest.TestCase):
    def test_exact_twelve_file_binding(self) -> None:
        design.require_exact_implementation_paths(
            design.REQUIRED_IMPLEMENTATION_PATHS
        )
        self.assertEqual(len(design.REQUIRED_IMPLEMENTATION_PATHS), 12)
        with self.assertRaisesRegex(
            design.RankHeadV2RunDesignError,
            "exactly twelve files",
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
            root = repository / design.STATE_ROOT / integration.BINDING_1_RUN_ID
            root.mkdir(parents=True)
            manifest = {"run_id": integration.BINDING_1_RUN_ID}
            result = {
                "run_id": integration.BINDING_1_RUN_ID,
                "status": "complete",
                "terminal_classification": integration.VISIBLE_CLASSIFICATION,
            }
            manifest_path = root / "manifest.json"
            result_path = root / "result.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result_path.write_text(json.dumps(result), encoding="utf-8")
            closure = {
                "run_id": integration.BINDING_1_RUN_ID,
                "manifest_sha256": design.sha256_bytes(
                    manifest_path.read_bytes()
                ),
                "result_sha256": design.sha256_bytes(result_path.read_bytes()),
                "run_lock_absent": True,
            }
            (root / "closure.json").write_text(
                json.dumps(closure),
                encoding="utf-8",
            )
            admitted = design.require_binding_1_v2_terminal_visible(repository)
            self.assertEqual(
                admitted["terminal_classification"],
                integration.VISIBLE_CLASSIFICATION,
            )

    def test_nonvisible_predecessor_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            root = repository / design.STATE_ROOT / integration.BINDING_1_RUN_ID
            root.mkdir(parents=True)
            manifest_path = root / "manifest.json"
            result_path = root / "result.json"
            manifest_path.write_text(
                json.dumps({"run_id": integration.BINDING_1_RUN_ID}),
                encoding="utf-8",
            )
            result_path.write_text(
                json.dumps(
                    {
                        "run_id": integration.BINDING_1_RUN_ID,
                        "status": "complete",
                        "terminal_classification": (
                            integration.COLLAPSED_CLASSIFICATION
                        ),
                    }
                ),
                encoding="utf-8",
            )
            (root / "closure.json").write_text(
                json.dumps(
                    {
                        "run_id": integration.BINDING_1_RUN_ID,
                        "manifest_sha256": design.sha256_bytes(
                            manifest_path.read_bytes()
                        ),
                        "result_sha256": design.sha256_bytes(
                            result_path.read_bytes()
                        ),
                        "run_lock_absent": True,
                    }
                ),
                encoding="utf-8",
            )
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
        self.assertEqual(first.authorization_state, "separately-authorizable")
        self.assertEqual(second.predecessor_run_id, first.run_id)
        self.assertIn("unauthorized", second.authorization_state)

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

    def test_complete_surface_contains_authority_and_live_modules(self) -> None:
        paths = set(design.REQUIRED_IMPLEMENTATION_PATHS)
        self.assertIn(
            "scripts/catalytic_kernel_0_balanced_rank_head_v2_authority.py",
            paths,
        )
        self.assertIn(
            "scripts/catalytic_kernel_0_balanced_rank_head_v2_live.py",
            paths,
        )


if __name__ == "__main__":
    unittest.main()
