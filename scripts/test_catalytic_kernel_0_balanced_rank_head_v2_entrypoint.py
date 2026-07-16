#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import catalytic_kernel_0_balanced_rank_head_v2_authority as authority
import catalytic_kernel_0_balanced_rank_head_v2_entrypoint as entrypoint
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration
import catalytic_kernel_0_balanced_rank_head_v2_live as live_core


class RankHeadV2EntrypointTests(unittest.TestCase):
    def test_preconsumption_failure_creates_no_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / "state").mkdir()
            with mock.patch.object(
                live_core,
                "run_rank_head_v2",
                side_effect=RuntimeError("preconsumption"),
            ):
                with self.assertRaisesRegex(RuntimeError, "preconsumption"):
                    entrypoint.run_rank_head_v2(
                        {"run_id": integration.BINDING_1_RUN_ID},
                        repository_root=repository,
                    )
            self.assertFalse(
                (
                    repository
                    / "state"
                    / "catalytic_kernel_0_rank_head_v2"
                ).exists()
            )

    def test_postconsumption_failure_closes_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            state = repository / "state"
            state.mkdir()
            receipt = authority.authority_receipt_path(
                repository,
                integration.BINDING_1_RUN_ID,
            )
            receipt.write_text(
                json.dumps(
                    {
                        "authority": {"run_id": integration.BINDING_1_RUN_ID},
                        "authority_receipt_hmac": "A" * 64,
                        "consumed": True,
                        "retry_allowed": False,
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(
                live_core,
                "run_rank_head_v2",
                side_effect=RuntimeError("postconsumption"),
            ):
                result = entrypoint.run_rank_head_v2(
                    {"run_id": integration.BINDING_1_RUN_ID},
                    repository_root=repository,
                )
            self.assertEqual(result["status"], "failed")
            self.assertEqual(
                result["terminal_classification"],
                integration.INCONCLUSIVE_CLASSIFICATION,
            )
            paths = live_core.state_paths(
                repository,
                integration.BINDING_1_RUN_ID,
            )
            self.assertTrue(paths["manifest.json"].is_file())
            self.assertTrue(paths["result.json"].is_file())
            self.assertTrue(paths["closure.json"].is_file())
            self.assertFalse(paths["run.lock"].exists())
            self.assertTrue(receipt.is_file())

    def test_existing_lock_is_removed_after_consumed_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / "state").mkdir()
            receipt = authority.authority_receipt_path(
                repository,
                integration.BINDING_1_RUN_ID,
            )
            receipt.write_text(
                json.dumps(
                    {
                        "authority": {"run_id": integration.BINDING_1_RUN_ID},
                        "authority_receipt_hmac": "B" * 64,
                        "consumed": True,
                        "retry_allowed": False,
                    }
                ),
                encoding="utf-8",
            )
            paths = live_core.state_paths(
                repository,
                integration.BINDING_1_RUN_ID,
            )
            paths["run.lock"].parent.mkdir(parents=True)
            paths["run.lock"].write_text("locked\n", encoding="ascii")
            closed = entrypoint.close_post_consumption_failure(
                repository,
                integration.BINDING_1_RUN_ID,
                RuntimeError("failure"),
            )
            self.assertIsNotNone(closed)
            self.assertFalse(paths["run.lock"].exists())


if __name__ == "__main__":
    unittest.main()
