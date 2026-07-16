#!/usr/bin/env python3
from __future__ import annotations

import unittest
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

import catalytic_kernel_0_balanced_rank_head_v2_cli as cli
import catalytic_kernel_0_balanced_rank_head_v2_entrypoint as entrypoint
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration
import catalytic_kernel_0_balanced_rank_head_v2_live as live_core
import catalytic_kernel_0_balanced_rank_head_v2_run_design as run_design


class RankHeadV2CliBootstrapTests(unittest.TestCase):
    def test_bootstrap_delegates_to_canonical_entrypoint_module(self) -> None:
        repository = Path("synthetic-repository")
        state_root = repository / run_design.STATE_ROOT
        with mock.patch.object(entrypoint, "main", return_value=0) as canonical_main:
            self.assertEqual(
                cli.main(repository_root=repository, state_root=state_root),
                0,
            )
        canonical_main.assert_called_once_with(
            repository_root=repository,
            state_root=state_root,
        )

    def test_bootstrap_passes_live_core_caller_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / "state").mkdir()
            state_root = repository / run_design.STATE_ROOT
            output = StringIO()
            with (
                mock.patch.object(
                    entrypoint,
                    "parse_args",
                    return_value={"run_id": integration.BINDING_1_RUN_ID},
                ),
                mock.patch.object(
                    live_core,
                    "_predecessor_and_runtime",
                    side_effect=RuntimeError("after-caller-gate"),
                ) as predecessor,
                redirect_stdout(output),
            ):
                self.assertEqual(
                    cli.main(repository_root=repository, state_root=state_root),
                    1,
                )
            predecessor.assert_called_once()
            self.assertNotIn(
                "protected live core is callable only by the authoritative fail-closed entrypoint",
                output.getvalue(),
            )
            self.assertFalse(state_root.exists())


if __name__ == "__main__":
    unittest.main()
