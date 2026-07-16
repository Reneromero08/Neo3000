#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2_authority as authority
import catalytic_kernel_0_balanced_rank_head_v2_evidence as evidence
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration


class RankHeadV2EvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        def verify_bytes(_repository, run_id, payload, **_kwargs):
            document = json.loads(payload)
            body = document.get("authority", {})
            if body.get("run_id") != run_id or document.get("consumed") is not True:
                raise authority.RankHeadV2AuthorityError("fixture receipt mismatch")
            return {"authority": body, "consumed": True}

        patcher = mock.patch.object(
            authority,
            "verify_authority_receipt_bytes_for_run",
            side_effect=verify_bytes,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _fixture(self, root: str) -> tuple[Path, str, str, dict[str, bytes]]:
        repository = Path(root)
        state = repository / "state"
        state.mkdir()
        (state / ".gitignore").write_text(
            "/catalytic_kernel_0_rank_head_v2/\n"
            "/catalytic_kernel_0_rank_head_v2_authority.*.authority.consumed.json\n"
            "/catalytic_kernel_0_rank_head_v2_evidence_archive/\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=repository,
            check=True,
            capture_output=True,
            timeout=30,
        )
        run_id = integration.BINDING_1_RUN_ID
        protected_commit = "1" * 40
        receipt = balanced.canonical_json_bytes(
            {
                "authority": {
                    "authorized_commit": protected_commit,
                    "run_id": run_id,
                },
                "consumed": True,
            }
        )
        manifest = balanced.canonical_json_bytes({"run_id": run_id, "status": "started"})
        result = balanced.canonical_json_bytes({"run_id": run_id, "status": "complete"})
        closure = balanced.canonical_json_bytes(
            {
                "run_id": run_id,
                "status": "complete",
                "run_lock_absent": True,
                "manifest_sha256": balanced.sha256_bytes(manifest),
                "result_sha256": balanced.sha256_bytes(result),
            }
        )
        paths = evidence._source_paths(repository, run_id)
        paths["receipt"].write_bytes(receipt)
        paths["manifest"].parent.mkdir(parents=True)
        paths["manifest"].write_bytes(manifest)
        paths["result"].write_bytes(result)
        paths["closure"].write_bytes(closure)
        return repository, run_id, protected_commit, {
            "receipt": receipt,
            "manifest": manifest,
            "result": result,
            "closure": closure,
        }

    def _archive(self, repository: Path, run_id: str, protected_commit: str):
        projection = evidence.archive_terminal_evidence(
            repository,
            run_id,
            protected_commit=protected_commit,
        )
        return projection, repository / projection["archive_path"]

    def test_archive_is_content_addressed_and_fully_verifiable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository, run_id, commit, payloads = self._fixture(temporary)
            projection, archive = self._archive(repository, run_id, commit)
            verified = evidence.verify_archive(repository, archive)
            self.assertEqual(archive.name, projection["bundle_sha256"])
            self.assertEqual(verified["bundle_sha256"], projection["bundle_sha256"])
            self.assertEqual(
                {item["name"] for item in projection["files"]},
                set(payloads),
            )
            for item in projection["files"]:
                self.assertEqual(item["byte_size"], len(payloads[item["name"]]))
                self.assertEqual(
                    item["sha256"],
                    balanced.sha256_bytes(payloads[item["name"]]),
                )

    def test_archive_refuses_to_overwrite_existing_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository, run_id, commit, _ = self._fixture(temporary)
            self._archive(repository, run_id, commit)
            with self.assertRaisesRegex(
                evidence.RankHeadV2EvidenceError,
                "already exists",
            ):
                evidence.archive_terminal_evidence(
                    repository,
                    run_id,
                    protected_commit=commit,
                )

    def test_verifier_rejects_any_archived_byte_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository, run_id, commit, _ = self._fixture(temporary)
            _, archive = self._archive(repository, run_id, commit)
            (archive / "result.json").write_bytes(b"tampered\n")
            with self.assertRaisesRegex(
                evidence.RankHeadV2EvidenceError,
                "hash or size changed",
            ):
                evidence.verify_archive(repository, archive)

    def test_restore_round_trips_exact_bytes_when_destinations_are_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository, run_id, commit, payloads = self._fixture(temporary)
            _, archive = self._archive(repository, run_id, commit)
            paths = evidence._source_paths(repository, run_id)
            for path in paths.values():
                path.unlink()
            restored = evidence.restore_archive(repository, archive)
            self.assertEqual(restored["status"], "restored-byte-exact")
            self.assertEqual(
                {name: path.read_bytes() for name, path in paths.items()},
                payloads,
            )

    def test_restore_leaves_identical_existing_evidence_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository, run_id, commit, payloads = self._fixture(temporary)
            _, archive = self._archive(repository, run_id, commit)
            restored = evidence.restore_archive(repository, archive)
            self.assertEqual(restored["restored"], [])
            self.assertEqual(len(restored["unchanged"]), 4)
            self.assertEqual(
                {
                    name: path.read_bytes()
                    for name, path in evidence._source_paths(repository, run_id).items()
                },
                payloads,
            )

    def test_restore_refuses_differing_evidence_without_replacing_any_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository, run_id, commit, payloads = self._fixture(temporary)
            _, archive = self._archive(repository, run_id, commit)
            paths = evidence._source_paths(repository, run_id)
            paths["result"].write_bytes(b"different\n")
            before = {name: path.read_bytes() for name, path in paths.items()}
            with self.assertRaisesRegex(
                evidence.RankHeadV2EvidenceError,
                "refuses to replace differing",
            ):
                evidence.restore_archive(repository, archive)
            self.assertEqual(
                {name: path.read_bytes() for name, path in paths.items()},
                before,
            )

    def test_restore_verifies_complete_archive_before_creating_any_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository, run_id, commit, _ = self._fixture(temporary)
            _, archive = self._archive(repository, run_id, commit)
            paths = evidence._source_paths(repository, run_id)
            for path in paths.values():
                path.unlink()
            (archive / "closure.json").write_bytes(b"tampered\n")
            with self.assertRaises(evidence.RankHeadV2EvidenceError):
                evidence.restore_archive(repository, archive)
            self.assertTrue(all(not path.exists() for path in paths.values()))

    def test_restore_rolls_back_new_files_if_atomic_publish_is_interrupted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository, run_id, commit, _ = self._fixture(temporary)
            _, archive = self._archive(repository, run_id, commit)
            paths = evidence._source_paths(repository, run_id)
            for path in paths.values():
                path.unlink()
            real_link = evidence.os.link
            calls = 0

            def interrupted(source, destination):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("synthetic restore interruption")
                return real_link(source, destination)

            with mock.patch.object(evidence.os, "link", side_effect=interrupted):
                with self.assertRaisesRegex(OSError, "synthetic restore interruption"):
                    evidence.restore_archive(repository, archive)
            self.assertTrue(all(not path.exists() for path in paths.values()))

    def test_archive_verification_uses_archived_receipt_not_live_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository, run_id, commit, _ = self._fixture(temporary)
            _, archive = self._archive(repository, run_id, commit)
            evidence._source_paths(repository, run_id)["receipt"].write_bytes(
                b"changed-live-receipt\n"
            )
            self.assertEqual(
                evidence.verify_archive(repository, archive)["bundle_sha256"],
                archive.name,
            )

    def test_terminal_chain_mismatch_is_rejected_before_archive_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository, run_id, commit, _ = self._fixture(temporary)
            paths = evidence._source_paths(repository, run_id)
            closure = json.loads(paths["closure"].read_bytes())
            closure["result_sha256"] = "0" * 64
            paths["closure"].write_bytes(balanced.canonical_json_bytes(closure))
            with self.assertRaisesRegex(
                evidence.RankHeadV2EvidenceError,
                "terminal evidence chain",
            ):
                evidence.archive_terminal_evidence(
                    repository,
                    run_id,
                    protected_commit=commit,
                )


if __name__ == "__main__":
    unittest.main()
