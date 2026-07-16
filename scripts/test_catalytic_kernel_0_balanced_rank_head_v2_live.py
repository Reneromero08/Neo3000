#!/usr/bin/env python3
from __future__ import annotations

import inspect
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

import catalytic_kernel_0_balanced_rank_head_v2_authority as authority
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration
import catalytic_kernel_0_balanced_rank_head_v2_live as live
import catalytic_kernel_0_balanced_rank_head_v2_run_design as run_design


class RankHeadV2LiveTests(unittest.TestCase):
    def test_logical_plan_has_six_stages_five_leases(self) -> None:
        plan = live.logical_execution_plan()
        self.assertEqual([item["stage"] for item in plan], list(integration.LOGICAL_STAGES))
        self.assertEqual(sum(item["model_request_issued"] for item in plan), 5)
        self.assertEqual(sum(item["physical_lease_required"] for item in plan), 5)
        extraction = next(item for item in plan if item["stage"] == "extract")
        self.assertEqual(extraction["execution_mode"], "controller-deterministic")
        self.assertFalse(extraction["model_request_issued"])
        self.assertFalse(extraction["physical_lease_required"])

    def test_state_paths_are_versioned_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            paths = live.state_paths(repository, integration.BINDING_1_RUN_ID)
            root = repository / run_design.STATE_ROOT / integration.BINDING_1_RUN_ID
            self.assertEqual(paths["manifest.json"], root / "manifest.json")
            self.assertEqual(set(paths), set(run_design.STATE_FILENAMES))

    def test_state_path_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as repository_name, tempfile.TemporaryDirectory() as outside_name:
            with self.assertRaises(live.RankHeadV2LiveError):
                live.state_paths(
                    Path(repository_name),
                    integration.BINDING_1_RUN_ID,
                    Path(outside_name),
                )

    def test_retired_r1_has_no_runtime_state_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                integration.RankHeadV2IntegrationError,
                "RETIRED_PRECONSUMPTION_COMMAND_INVOKED",
            ):
                live.state_paths(
                    Path(temporary),
                    integration.RETIRED_BINDING_1_RUN_ID,
                )

    def test_cli_requires_authority_and_exact_run(self) -> None:
        parser = live.parse_args
        self.assertTrue(callable(parser))
        self.assertIn(integration.BINDING_1_RUN_ID, integration.RUN_ORDER)
        self.assertIn(integration.BINDING_2_RUN_ID, integration.RUN_ORDER)

    def test_direct_live_core_cli_rejects_before_admission(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = live.main()
        self.assertEqual(code, 1)
        self.assertIn("direct live-core execution is forbidden", output.getvalue())

    def test_direct_runner_has_no_authority_default_or_environment_fallback(self) -> None:
        with self.assertRaisesRegex(
            live.RankHeadV2LiveError,
            "direct live-core invocation is forbidden",
        ):
            live.run_rank_head_v2(
                {"run_id": integration.BINDING_1_RUN_ID},
                repository_root=Path.cwd(),
            )
        with self.assertRaisesRegex(
            live.RankHeadV2LiveError,
            "callable only by the authoritative fail-closed entrypoint",
        ):
            live._run_rank_head_v2_protected(
                {"run_id": integration.BINDING_1_RUN_ID},
                repository_root=Path.cwd(),
                state_root=Path.cwd() / run_design.STATE_ROOT,
            )
        protected_parameters = inspect.signature(
            live._run_rank_head_v2_protected
        ).parameters
        self.assertNotIn("adapter", protected_parameters)
        self.assertNotIn("_entrypoint_capability", protected_parameters)
        self.assertNotIn("_ENTRYPOINT_CAPABILITY", vars(live))

    def test_restoration_law_requires_exactly_five_leases_and_zero_active(self) -> None:
        source = Path(live.__file__).read_text(encoding="utf-8")
        self.assertIn('restoration_body["lease_count"] == 5', source)
        self.assertIn('restoration_body["maximum_concurrent_leases"] == 1', source)
        self.assertIn('restoration_body["active_leases"] == 0', source)

    def test_claims_remain_locked(self) -> None:
        self.assertFalse(live.CLAIMS["automatic_promotion"])
        self.assertEqual(live.CLAIMS["DEEP"], "DISABLED")
        for key, value in live.CLAIMS.items():
            if key not in {"automatic_promotion", "DEEP"}:
                self.assertEqual(value, "LOCKED")

    def test_authority_receipt_namespace_is_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            receipt = authority.authority_receipt_path(
                repository,
                integration.BINDING_1_RUN_ID,
            )
            run_root = repository / run_design.STATE_ROOT / integration.BINDING_1_RUN_ID
            self.assertNotEqual(receipt.parent / receipt.name, run_root)
            self.assertIn("authority", receipt.name)


if __name__ == "__main__":
    unittest.main()
