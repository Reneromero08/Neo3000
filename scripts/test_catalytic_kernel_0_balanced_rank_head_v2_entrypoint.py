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


RUN_ID = integration.BINDING_1_RUN_ID
VERIFIED_EVIDENCE = {
    "authority": {
        "authority_id_sha256": "A" * 64,
        "run_id": RUN_ID,
        "source_binding": "binding-1",
    },
    "authority_receipt_hmac": "B" * 64,
    "authority_receipt_sha256": "C" * 64,
    "consumed": True,
    "consumption_occurred_before_live_mutation": True,
    "maximum_invocations": 1,
    "retry_allowed": False,
}


class RankHeadV2EntrypointTests(unittest.TestCase):
    def _receipt(self, repository: Path) -> Path:
        path = authority.authority_receipt_path(repository, RUN_ID)
        path.write_bytes(b'{"synthetic_fixture":true}\n')
        return path

    def test_preconsumption_failure_creates_no_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / "state").mkdir()
            with mock.patch.object(
                live_core,
                "_run_rank_head_v2_protected",
                side_effect=RuntimeError("preconsumption"),
            ):
                with self.assertRaisesRegex(RuntimeError, "preconsumption"):
                    entrypoint.run_rank_head_v2(
                        {"run_id": RUN_ID},
                        repository_root=repository,
                    )
            self.assertFalse(
                (repository / "state" / "catalytic_kernel_0_rank_head_v2").exists()
            )

    def test_postconsumption_failure_requires_crypto_and_closes_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / "state").mkdir()
            receipt = self._receipt(repository)
            before = receipt.read_bytes()
            with (
                mock.patch.object(
                    authority,
                    "verify_authority_receipt_for_run",
                    return_value=VERIFIED_EVIDENCE,
                ) as verify,
                mock.patch.object(
                    live_core,
                    "_run_rank_head_v2_protected",
                    side_effect=RuntimeError("postconsumption raw secret text"),
                ),
            ):
                result = entrypoint.run_rank_head_v2(
                    {"run_id": RUN_ID},
                    repository_root=repository,
                )
            self.assertGreaterEqual(verify.call_count, 2)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(
                result["terminal_classification"],
                integration.INCONCLUSIVE_CLASSIFICATION,
            )
            paths = live_core.state_paths(repository, RUN_ID)
            self.assertTrue(paths["manifest.json"].is_file())
            self.assertTrue(paths["result.json"].is_file())
            self.assertTrue(paths["closure.json"].is_file())
            self.assertFalse(paths["run.lock"].exists())
            self.assertEqual(receipt.read_bytes(), before)
            persisted = (
                paths["manifest.json"].read_text(encoding="utf-8")
                + paths["result.json"].read_text(encoding="utf-8")
                + paths["closure.json"].read_text(encoding="utf-8")
            )
            self.assertNotIn("postconsumption raw secret text", persisted)
            self.assertNotIn("external_live_authority_id", persisted)
            self.assertIn('"authority_receipt_cryptographically_verified": true', persisted)

    def test_unverified_or_malformed_receipt_cannot_authorize_failure_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / "state").mkdir()
            self._receipt(repository)
            with (
                mock.patch.object(
                    authority,
                    "verify_authority_receipt_for_run",
                    side_effect=authority.RankHeadV2AuthorityError("bad receipt"),
                ),
                mock.patch.object(
                    live_core,
                    "_run_rank_head_v2_protected",
                    side_effect=RuntimeError("postconsumption"),
                ),
            ):
                with self.assertRaisesRegex(
                    entrypoint.RankHeadV2EntrypointError,
                    "cryptographic verification",
                ):
                    entrypoint.run_rank_head_v2(
                        {"run_id": RUN_ID},
                        repository_root=repository,
                    )
            self.assertFalse(
                (repository / "state" / "catalytic_kernel_0_rank_head_v2").exists()
            )

    def test_existing_regular_lock_is_removed_after_verified_consumed_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / "state").mkdir()
            receipt = self._receipt(repository)
            before = receipt.read_bytes()
            paths = live_core.state_paths(repository, RUN_ID)
            paths["run.lock"].parent.mkdir(parents=True)
            paths["run.lock"].write_text("locked\n", encoding="ascii")
            with mock.patch.object(
                authority,
                "verify_authority_receipt_for_run",
                return_value=VERIFIED_EVIDENCE,
            ):
                closed = entrypoint.close_post_consumption_failure(
                    repository,
                    RUN_ID,
                    RuntimeError("failure"),
                )
            self.assertIsNotNone(closed)
            self.assertFalse(paths["run.lock"].exists())
            self.assertEqual(receipt.read_bytes(), before)

    def test_every_named_postconsumption_boundary_gets_bounded_terminal_trail(self) -> None:
        boundaries = (
            "before-runtime-root",
            "after-manifest",
            "sidecar-launch",
            "model-request",
            "controller-extraction",
            "cleanup",
            "postflight",
            "authority-verification",
            "result-write",
            "final-postflight",
            "closure-write",
        )
        for boundary in boundaries:
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as temporary:
                repository = Path(temporary)
                (repository / "state").mkdir()
                receipt = self._receipt(repository)
                paths = live_core.state_paths(repository, RUN_ID)
                if boundary != "before-runtime-root":
                    paths["manifest.json"].parent.mkdir(parents=True)
                    paths["manifest.json"].write_text(
                        json.dumps({"run_id": RUN_ID, "status": "started"}),
                        encoding="utf-8",
                    )
                with mock.patch.object(
                    authority,
                    "verify_authority_receipt_for_run",
                    return_value=VERIFIED_EVIDENCE,
                ):
                    result = entrypoint.close_post_consumption_failure(
                        repository,
                        RUN_ID,
                        RuntimeError(boundary),
                    )
                self.assertEqual(
                    result["terminal_classification"],
                    integration.INCONCLUSIVE_CLASSIFICATION,
                )
                self.assertTrue(paths["closure.json"].is_file())
                self.assertFalse(paths["run.lock"].exists())
                self.assertTrue(receipt.is_file())


if __name__ == "__main__":
    unittest.main()
