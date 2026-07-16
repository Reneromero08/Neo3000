#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest import mock

import catalytic_kernel_0_balanced_rank_head_v2_authority as authority
import catalytic_kernel_0_balanced_rank_head_v2_evidence as evidence
import catalytic_kernel_0_balanced_rank_head_v2_entrypoint as entrypoint
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration
import catalytic_kernel_0_balanced_rank_head_v2_live as live_core
import catalytic_kernel_0_balanced_rank_head_v2_run_design as run_design


RUN_ID = integration.BINDING_1_RUN_ID
VERIFIED_EVIDENCE = {
    "authority": {
        "authority_id_sha256": "A" * 64,
        "authorized_commit": "1" * 40,
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
    def setUp(self) -> None:
        patcher = mock.patch.object(
            evidence,
            "archive_terminal_evidence",
            return_value={"status": "verified", "bundle_sha256": "D" * 64},
        )
        self.archive_terminal_evidence = patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def _roots(repository: Path) -> tuple[Path, Path]:
        state = repository / "state"
        state.mkdir(exist_ok=True)
        state_root = repository / run_design.STATE_ROOT
        return repository, state_root

    def _receipt(self, repository: Path) -> Path:
        path = authority.authority_receipt_path(repository, RUN_ID)
        path.write_bytes(b'{"synthetic_fixture":true}\n')
        return path

    def test_preconsumption_failure_creates_no_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            repository, state_root = self._roots(repository)
            with mock.patch.object(
                live_core,
                "_run_rank_head_v2_protected",
                side_effect=RuntimeError("preconsumption"),
            ):
                with self.assertRaisesRegex(RuntimeError, "preconsumption"):
                    entrypoint.run_rank_head_v2(
                        {"run_id": RUN_ID},
                        repository_root=repository,
                        state_root=state_root,
                    )
            self.assertFalse(
                (repository / "state" / "catalytic_kernel_0_rank_head_v2").exists()
            )

    def test_original_duplicate_main_module_code_object_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository, state_root = self._roots(Path(temporary))
            scripts = repository / "scripts"
            scripts.mkdir()
            copied = scripts / Path(entrypoint.__file__).name
            shutil.copyfile(entrypoint.__file__, copied)
            duplicate = runpy.run_path(
                copied,
                run_name="rank_head_v2_duplicate_entrypoint",
            )
            with self.assertRaisesRegex(
                live_core.RankHeadV2LiveError,
                "callable only by the authoritative fail-closed entrypoint",
            ):
                duplicate["run_rank_head_v2"](
                    {"run_id": RUN_ID},
                    repository_root=repository,
                    state_root=state_root,
                )

    def test_direct_entrypoint_script_rejects_before_argument_admission(self) -> None:
        temporary_context = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_context.cleanup)
        repository, _ = self._roots(Path(temporary_context.name))
        scripts = repository / "scripts"
        scripts.mkdir()
        copied = scripts / Path(entrypoint.__file__).name
        shutil.copyfile(entrypoint.__file__, copied)
        runtime_root = repository / "state" / "catalytic_kernel_0_rank_head_v2"
        receipts_before = sorted(
            path.name
            for path in (repository / "state").glob(
                "catalytic_kernel_0_rank_head_v2_authority.*.authority.consumed.json"
            )
        )
        marker = "SYNTHETIC-AUTHORITY-MARKER-MUST-NOT-ECHO"
        environment = dict(os.environ)
        environment[authority.TEST_PROCESS_ENV] = "1"
        environment[authority.TEST_REPOSITORY_ENV] = str(repository)
        existing_pythonpath = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = os.pathsep.join(
            part
            for part in (
                str(Path(entrypoint.__file__).resolve().parent),
                existing_pythonpath,
            )
            if part
        )
        completed = subprocess.run(
            [
                sys.executable,
                copied,
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
            env=environment,
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
            repository, state_root = self._roots(repository)
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
                    state_root=state_root,
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
            self.archive_terminal_evidence.assert_called_once_with(
                repository,
                RUN_ID,
                protected_commit="1" * 40,
            )

    def test_unverified_or_malformed_receipt_cannot_authorize_failure_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            repository, state_root = self._roots(repository)
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
                        state_root=state_root,
                    )
            self.assertFalse(
                (repository / "state" / "catalytic_kernel_0_rank_head_v2").exists()
            )

    def test_existing_regular_lock_is_removed_after_verified_consumed_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            repository, state_root = self._roots(repository)
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
                    state_root,
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
                repository, state_root = self._roots(repository)
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
                        state_root,
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

    def test_real_repository_is_rejected_before_live_or_state_access(self) -> None:
        repository = Path(entrypoint.__file__).resolve().parents[1]
        with mock.patch.object(
            live_core,
            "_run_rank_head_v2_protected",
        ) as protected:
            with self.assertRaisesRegex(
                authority.RankHeadV2AuthorityError,
                "test process cannot access real rank-head v2 state",
            ):
                entrypoint.run_rank_head_v2(
                    {"run_id": RUN_ID},
                    repository_root=repository,
                    state_root=repository / run_design.STATE_ROOT,
                )
        protected.assert_not_called()

    def test_terminal_evidence_cannot_be_downgraded(self) -> None:
        for status in ("complete", "failed"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temporary:
                repository, state_root = self._roots(Path(temporary))
                receipt = self._receipt(repository)
                paths = live_core.state_paths(repository, RUN_ID, state_root)
                paths["manifest.json"].parent.mkdir(parents=True)
                manifest = b'{"run_id":"' + RUN_ID.encode("ascii") + b'"}\n'
                result = json.dumps(
                    {"run_id": RUN_ID, "status": status},
                    sort_keys=True,
                ).encode("utf-8") + b"\n"
                closure = json.dumps(
                    {
                        "run_id": RUN_ID,
                        "status": status,
                        "run_lock_absent": True,
                        "manifest_sha256": authority.sha256_bytes(manifest),
                        "result_sha256": authority.sha256_bytes(result),
                    },
                    sort_keys=True,
                ).encode("utf-8") + b"\n"
                paths["manifest.json"].write_bytes(manifest)
                paths["result.json"].write_bytes(result)
                paths["closure.json"].write_bytes(closure)
                before = {
                    "receipt": receipt.read_bytes(),
                    "manifest": manifest,
                    "result": result,
                    "closure": closure,
                }
                with self.assertRaisesRegex(
                    entrypoint.RankHeadV2EntrypointError,
                    "refusing to overwrite terminal v2 evidence",
                ):
                    entrypoint.close_post_consumption_failure(
                        repository,
                        state_root,
                        RUN_ID,
                        RuntimeError("synthetic failure after terminal closure"),
                    )
                self.assertEqual(receipt.read_bytes(), before["receipt"])
                self.assertEqual(
                    paths["manifest.json"].read_bytes(), before["manifest"]
                )
                self.assertEqual(paths["result.json"].read_bytes(), before["result"])
                self.assertEqual(
                    paths["closure.json"].read_bytes(), before["closure"]
                )


if __name__ == "__main__":
    unittest.main()
