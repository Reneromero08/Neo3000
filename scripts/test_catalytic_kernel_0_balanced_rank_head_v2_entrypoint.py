#!/usr/bin/env python3
from __future__ import annotations

import json
import runpy
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
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

    def test_original_duplicate_main_module_code_object_is_rejected(self) -> None:
        duplicate = runpy.run_path(
            entrypoint.__file__,
            run_name="rank_head_v2_duplicate_entrypoint",
        )
        with self.assertRaisesRegex(
            live_core.RankHeadV2LiveError,
            "callable only by the authoritative fail-closed entrypoint",
        ):
            duplicate["run_rank_head_v2"]({"run_id": RUN_ID})

    def test_direct_entrypoint_script_rejects_before_argument_admission(self) -> None:
        repository = Path(entrypoint.__file__).resolve().parents[1]
        runtime_root = repository / "state" / "catalytic_kernel_0_rank_head_v2"
        receipts_before = sorted(
            path.name
            for path in (repository / "state").glob(
                "catalytic_kernel_0_rank_head_v2_authority.*.authority.consumed.json"
            )
        )
        marker = "SYNTHETIC-AUTHORITY-MARKER-MUST-NOT-ECHO"
        completed = subprocess.run(
            [
                sys.executable,
                entrypoint.__file__,
                "run",
                "--run-id",
                RUN_ID,
                "--external-live-authority-id",
                marker,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn(
            "catalytic_kernel_0_balanced_rank_head_v2_cli.py",
            completed.stdout,
        )
        self.assertNotIn(marker, completed.stdout + completed.stderr)
        self.assertFalse(runtime_root.exists())
        self.assertEqual(
            sorted(
                path.name
                for path in (repository / "state").glob(
                    "catalytic_kernel_0_rank_head_v2_authority.*.authority.consumed.json"
                )
            ),
            receipts_before,
        )

    def test_retired_r1_is_rejected_by_canonical_argument_parser(self) -> None:
        stderr = StringIO()
        with (
            mock.patch.object(
                sys,
                "argv",
                [
                    "rank-head-v2-cli",
                    "run",
                    "--binary",
                    "synthetic-binary",
                    "--model",
                    "synthetic-model",
                    "--run-id",
                    integration.RETIRED_BINDING_1_RUN_ID,
                    "--external-live-authority-id",
                    "A" * 64,
                    "--authorized-commit",
                    "1" * 40,
                ],
            ),
            redirect_stderr(stderr),
            self.assertRaises(SystemExit),
        ):
            entrypoint.parse_args()
        self.assertIn("invalid choice", stderr.getvalue())

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
