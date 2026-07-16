#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import hmac
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0 as kernel


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_BINDING_1_ROOT = bytes(range(32))
SYNTHETIC_BINDING_2_ROOT = bytes(reversed(range(32)))
SYNTHETIC_COMMIT = "1" * 40
SYNTHETIC_SHA = "A" * 64


def private_binding(
    configuration: balanced.PrivateBindingConfiguration = balanced.BINDING_2,
) -> balanced.PrivateBinding:
    secret = (
        SYNTHETIC_BINDING_2_ROOT
        if configuration is balanced.BINDING_2
        else SYNTHETIC_BINDING_1_ROOT
    )
    return balanced.PrivateBinding.from_secret(secret, configuration)


def authority(
    *,
    run_id: str = balanced.BINDING_2_FULL_RUN_ID,
    authority_id: str = "B" * 64,
    authorized_commit: str = SYNTHETIC_COMMIT,
    current_commit: str = SYNTHETIC_COMMIT,
    private: balanced.PrivateBinding | None = None,
    carrier_profile: str = balanced.BINDING_2_PROFILE_ID,
) -> balanced.ExternalLiveAuthority:
    selected = private or private_binding()
    return balanced.build_external_live_authority(
        private=selected,
        external_authority_id=authority_id,
        authorized_commit=authorized_commit,
        current_commit=current_commit,
        run_id=run_id,
        carrier_profile=carrier_profile,
        preregistration_artifact_sha256=SYNTHETIC_SHA,
        implementation_binding_sha256="C" * 64,
        model_sha256="D" * 64,
        binary_sha256="E" * 64,
        carrier_root_sha256="F" * 64,
    )


def prepare_authority_repository(repository: Path) -> None:
    (repository / "state").mkdir()
    secret = repository / balanced.BINDING_2.secret_path
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_bytes(SYNTHETIC_BINDING_2_ROOT)


class ExternalAuthorityBridgeTests(unittest.TestCase):
    def test_01_static_preregistration_remains_non_self_authorizing(self) -> None:
        document = json.loads(
            (ROOT / balanced.BINDING_2.preregistration_path).read_bytes()
        )
        boundary = document["future_authorization_boundary"]
        self.assertFalse(boundary["live_authority_granted"])
        self.assertFalse(boundary["embedded_live_authority_granted"])
        self.assertTrue(boundary["external_live_authority_required"])
        private = balanced._private_binding_from_repository(ROOT, balanced.BINDING_2)
        projection = balanced.validate_preregistration(
            ROOT,
            private,
            run_id=balanced.BINDING_2_FULL_RUN_ID,
            require_final=False,
            configuration=balanced.BINDING_2,
            for_execution=False,
        )
        self.assertEqual(projection["status"], "validated-static-preregistered")

    def test_02_tracked_live_authority_true_is_rejected(self) -> None:
        boundary = balanced.binding_2_authorization_boundary()
        boundary["live_authority_granted"] = True
        with self.assertRaises(balanced.BalancedOpaqueError):
            balanced.validate_binding_2_authorization_boundary(boundary)

    def test_03_binding_2_execution_without_external_authority_fails_before_mutation(self) -> None:
        def snapshot_leaf(path: Path) -> dict[str, object]:
            if not path.exists() and not path.is_symlink():
                return {"state": "absent"}
            self.assertFalse(path.is_symlink())
            self.assertTrue(path.is_file())
            data = path.read_bytes()
            return {
                "state": "regular-file",
                "bytes": data,
                "size": path.stat().st_size,
                "sha256": hashlib.sha256(data).hexdigest().upper(),
            }

        def snapshot_tree(path: Path) -> dict[str, object]:
            if not path.exists() and not path.is_symlink():
                return {"state": "absent"}
            self.assertFalse(path.is_symlink())
            self.assertTrue(path.is_dir())
            entries: list[dict[str, object]] = []
            for item in sorted(
                path.rglob("*"), key=lambda candidate: candidate.relative_to(path).as_posix()
            ):
                self.assertFalse(item.is_symlink())
                relative = item.relative_to(path).as_posix()
                if item.is_dir():
                    entries.append({"path": relative + "/", "kind": "directory"})
                    continue
                self.assertTrue(item.is_file())
                data = item.read_bytes()
                entries.append(
                    {
                        "path": relative,
                        "kind": "regular-file",
                        "bytes": data,
                        "size": item.stat().st_size,
                        "sha256": hashlib.sha256(data).hexdigest().upper(),
                    }
                )
            return {"state": "directory", "entries": entries}

        private = balanced._private_binding_from_repository(ROOT, balanced.BINDING_2)
        receipt = balanced.authority_receipt_path(
            ROOT, balanced.BINDING_2_FULL_RUN_ID
        )
        runtime_root = (
            ROOT
            / "state"
            / "catalytic_kernel_0"
            / balanced.BINDING_2_FULL_RUN_ID
        )
        run_lock = runtime_root / "run.lock"
        receipt_before = snapshot_leaf(receipt)
        runtime_before = snapshot_tree(runtime_root)
        run_lock_before = snapshot_leaf(run_lock)
        with mock.patch.object(
            kernel.CatalyticKernel0Adapter,
            "launch_sidecar",
            side_effect=AssertionError("sidecar launch reached"),
        ) as launch_sidecar, mock.patch.object(
            kernel.CatalyticKernel0Adapter,
            "execute_request",
            side_effect=AssertionError("live model request reached"),
        ) as execute_request, mock.patch.object(
            balanced,
            "consume_external_live_authority_once",
            side_effect=AssertionError("authority consumption reached"),
        ) as consume_authority:
            with self.assertRaisesRegex(
                balanced.BalancedOpaqueError, "requires external one-shot authority"
            ):
                balanced.validate_preregistration(
                    ROOT,
                    private,
                    run_id=balanced.BINDING_2_FULL_RUN_ID,
                    require_final=False,
                    configuration=balanced.BINDING_2,
                    for_execution=True,
                )
        launch_sidecar.assert_not_called()
        execute_request.assert_not_called()
        consume_authority.assert_not_called()
        self.assertEqual(snapshot_leaf(receipt), receipt_before)
        self.assertEqual(snapshot_tree(runtime_root), runtime_before)
        self.assertEqual(snapshot_leaf(run_lock), run_lock_before)

    def test_04_malformed_authority_id_fails(self) -> None:
        for malformed in ("", "0" * 63, "0" * 65, "Z" * 64):
            with self.subTest(malformed_length=len(malformed)):
                with self.assertRaises(balanced.BalancedOpaqueError):
                    authority(authority_id=malformed)

    def test_05_authorized_commit_mismatch_fails(self) -> None:
        with self.assertRaisesRegex(
            balanced.BalancedOpaqueError, "commit mismatch"
        ):
            authority(authorized_commit="2" * 40)

    def test_06_run_id_mismatch_fails(self) -> None:
        selected = private_binding()
        full = authority(private=selected)
        with self.assertRaisesRegex(
            balanced.BalancedOpaqueError, "scope mismatch"
        ):
            balanced.validate_external_live_authority(
                selected,
                full,
                run_id=balanced.BINDING_2_DELETE_A_RUN_ID,
                carrier_profile=balanced.BINDING_2_PROFILE_ID,
                current_commit=SYNTHETIC_COMMIT,
            )

    def test_07_profile_and_binding_mismatch_fail(self) -> None:
        with self.assertRaisesRegex(
            balanced.BalancedOpaqueError, "carrier profile mismatch"
        ):
            authority(carrier_profile=balanced.BINDING_1_PROFILE_ID)
        with self.assertRaisesRegex(
            balanced.BalancedOpaqueError, "binding-2 only"
        ):
            authority(private=private_binding(balanced.BINDING_1))
        instance = balanced.BalancedOpaqueRuntime(
            repository=ROOT,
            run_id=balanced.BINDING_2_FULL_RUN_ID,
            private=private_binding(),
        )
        with self.assertRaisesRegex(
            kernel.CatalyticKernel0Error, "run ID and carrier profile"
        ):
            kernel._validate_balanced_profile_selection(
                balanced.BINDING_1_PROFILE_ID, instance
            )

    def test_08_authority_body_and_hmac_recompute_exactly(self) -> None:
        selected = private_binding()
        external = authority(private=selected)
        body = external.body()
        expected = hmac.new(
            selected.run_key(external.run_id),
            b"ck0-balanced/external-live-authority-v1\0"
            + balanced.canonical_json_bytes(body),
            hashlib.sha256,
        ).hexdigest().upper()
        actual = balanced.external_authority_receipt_hmac(selected, external)
        self.assertEqual(actual, expected)
        balanced.validate_external_live_authority(
            selected,
            external,
            run_id=external.run_id,
            carrier_profile=external.carrier_profile,
            current_commit=SYNTHETIC_COMMIT,
            receipt_hmac=actual,
        )

    def test_09_tampered_authority_receipt_fails(self) -> None:
        selected = private_binding()
        external = authority(private=selected)
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            prepare_authority_repository(repository)
            with mock.patch.object(
                balanced.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=0),
            ):
                balanced.consume_external_live_authority_once(
                    repository, selected, external
                )
            path = balanced.authority_receipt_path(repository, external.run_id)
            document = json.loads(path.read_bytes())
            document["authority"]["binary_sha256"] = "0" * 64
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(
                balanced.BalancedOpaqueError, "binding changed"
            ):
                balanced.verify_external_live_authority_receipt(
                    repository, selected, external
                )

    def test_10_authority_fields_cannot_enter_model_visible_payloads(self) -> None:
        selected = private_binding()
        external = authority(private=selected)
        receipt_hmac = balanced.external_authority_receipt_hmac(selected, external)
        forbidden = {
            "authority_kind",
            "authority_id_sha256",
            "authorized_commit",
            "preregistration_artifact_sha256",
            "run_key_commitment",
            "maximum_invocations",
            "automatic_follow_on",
            external.authority_id_sha256,
            external.authorized_commit,
            receipt_hmac,
        }
        for run_id in balanced.BINDING_2.run_modes:
            for payload in balanced.static_model_visible_payloads(
                SYNTHETIC_BINDING_2_ROOT, run_id, balanced.BINDING_2
            ).values():
                text = balanced.canonical_json_text(payload)
                self.assertTrue(all(value not in text for value in forbidden))

    def test_11_authority_receipt_is_atomically_consumed_once(self) -> None:
        selected = private_binding()
        external = authority(private=selected)
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            prepare_authority_repository(repository)
            with mock.patch.object(
                balanced.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=0),
            ):
                evidence = balanced.consume_external_live_authority_once(
                    repository, selected, external
                )
            path = balanced.authority_receipt_path(repository, external.run_id)
            self.assertTrue(path.is_file())
            self.assertFalse(path.is_symlink())
            self.assertTrue(evidence["consumed"])
            self.assertTrue(evidence["consumption_occurred_before_live_mutation"])
            self.assertEqual(
                path.read_bytes(),
                balanced.canonical_json_bytes(json.loads(path.read_bytes())),
            )
        replacement = authority(private=selected, authority_id="C" * 64)
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            prepare_authority_repository(repository)
            with mock.patch.object(
                balanced.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=0),
            ), mock.patch.object(
                balanced,
                "verify_external_live_authority_receipt",
                side_effect=balanced.BalancedOpaqueError(
                    "synthetic post-consumption crash"
                ),
            ):
                with self.assertRaisesRegex(
                    balanced.BalancedOpaqueError, "post-consumption crash"
                ):
                    balanced.consume_external_live_authority_once(
                        repository, selected, external
                    )
            path = balanced.authority_receipt_path(repository, external.run_id)
            self.assertTrue(path.is_file())
            with mock.patch.object(
                balanced.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=0),
            ):
                with self.assertRaisesRegex(
                    balanced.BalancedOpaqueError, "already attempted"
                ):
                    balanced.consume_external_live_authority_once(
                        repository, selected, replacement
                    )

    def test_12_existing_consumed_receipt_prevents_reuse(self) -> None:
        selected = private_binding()
        first = authority(private=selected, authority_id="B" * 64)
        replacement = authority(private=selected, authority_id="C" * 64)
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            prepare_authority_repository(repository)
            barrier = threading.Barrier(2)

            def attempt() -> str:
                barrier.wait()
                try:
                    balanced.consume_external_live_authority_once(
                        repository, selected, first
                    )
                    return "consumed"
                except balanced.BalancedOpaqueError:
                    return "blocked"

            with mock.patch.object(
                balanced.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=0),
            ):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    outcomes = list(executor.map(lambda _: attempt(), range(2)))
                self.assertEqual(sorted(outcomes), ["blocked", "consumed"])
                receipt = balanced.authority_receipt_path(
                    repository, first.run_id
                )
                self.assertTrue(receipt.is_file())
                self.assertFalse(
                    (repository / "state" / "catalytic_kernel_0").exists()
                )
                with self.assertRaisesRegex(
                    balanced.BalancedOpaqueError, "already attempted"
                ):
                    balanced.consume_external_live_authority_once(
                        repository, selected, replacement
                    )

    def test_13_failure_before_consumption_creates_no_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / "state").mkdir()
            path = balanced.authority_receipt_path(
                repository, balanced.BINDING_2_FULL_RUN_ID
            )
            with self.assertRaises(balanced.BalancedOpaqueError):
                authority(authorized_commit="2" * 40)
            self.assertFalse(path.exists())

    def test_14_full_run_authority_cannot_authorize_deletion_controls(self) -> None:
        selected = private_binding()
        full = authority(private=selected)
        for deletion_run in (
            balanced.BINDING_2_DELETE_A_RUN_ID,
            balanced.BINDING_2_DELETE_B_RUN_ID,
        ):
            with self.subTest(run_id=deletion_run):
                with self.assertRaisesRegex(
                    balanced.BalancedOpaqueError, "scope mismatch"
                ):
                    balanced.validate_external_live_authority(
                        selected,
                        full,
                        run_id=deletion_run,
                        carrier_profile=balanced.BINDING_2_PROFILE_ID,
                        current_commit=SYNTHETIC_COMMIT,
                    )

    def test_15_deletions_keep_terminal_full_and_separate_authority_gates(self) -> None:
        selected = private_binding()
        full = authority(private=selected, authority_id="B" * 64)
        reused_delete_a = authority(
            private=selected,
            run_id=balanced.BINDING_2_DELETE_A_RUN_ID,
            authority_id="B" * 64,
        )
        fresh_delete_a = authority(
            private=selected,
            run_id=balanced.BINDING_2_DELETE_A_RUN_ID,
            authority_id="C" * 64,
        )
        self.assertEqual(
            full.authority_id_sha256, reused_delete_a.authority_id_sha256
        )
        self.assertNotEqual(
            full.authority_id_sha256, fresh_delete_a.authority_id_sha256
        )
        boundary = balanced.binding_2_authorization_boundary()
        self.assertFalse(boundary["delete_a_authorized"])
        self.assertFalse(boundary["delete_b_authorized"])
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            prepare_authority_repository(repository)
            secret_path = repository / balanced.BINDING_2.secret_path
            private_bytes_before = secret_path.read_bytes()
            (repository / "state" / "catalytic_kernel_0").mkdir()
            barrier = threading.Barrier(2)

            def attempt(
                external: balanced.ExternalLiveAuthority,
            ) -> str:
                barrier.wait()
                try:
                    balanced.consume_external_live_authority_once(
                        repository, selected, external
                    )
                    return "consumed"
                except balanced.BalancedOpaqueError:
                    return "blocked"

            with mock.patch.object(
                balanced.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=0),
            ):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    outcomes = list(
                        executor.map(attempt, (full, reused_delete_a))
                    )
            self.assertEqual(sorted(outcomes), ["blocked", "consumed"])
            receipts = [
                balanced.authority_receipt_path(repository, run_id)
                for run_id in (
                    balanced.BINDING_2_FULL_RUN_ID,
                    balanced.BINDING_2_DELETE_A_RUN_ID,
                )
            ]
            self.assertEqual(sum(path.is_file() for path in receipts), 1)
            self.assertEqual(secret_path.read_bytes(), private_bytes_before)
            with self.assertRaisesRegex(
                balanced.BalancedOpaqueError, "full-information run"
            ):
                balanced._require_terminal_full_run(repository, balanced.BINDING_2)

    def test_16_binding_1_history_commands_commitments_and_payloads_are_unchanged(self) -> None:
        path = ROOT / balanced.BINDING_1.preregistration_path
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest().upper(),
            "D6FEC8B0477A198216ECDDDD8DE11AD2734410A640A69B37017394D9454643B7",
        )
        document = json.loads(path.read_bytes())
        self.assertNotIn("future_command_bindings", document)
        selected = private_binding(balanced.BINDING_1)
        self.assertEqual(
            selected.secret_commitment,
            "20D9FC77E337E773BE7CD7164AA1807D3248C56AE149B02E96D46B4D9969C296",
        )
        self.assertEqual(
            selected.alias_map_commitment,
            "2C7F2F868FCF53151CD9AEC164E1C6B2EB2AEEC3153FABA317E44AE78DCAB61B",
        )
        expected_borrow = "24E87CE8707F0F8F7168BBA4D6B55EC3AF3573E3640606BB2430BE425332BCB0"
        for run_id in balanced.BINDING_1.run_modes:
            payloads = balanced.static_model_visible_payloads(
                SYNTHETIC_BINDING_1_ROOT, run_id, balanced.BINDING_1
            )
            self.assertEqual(
                balanced.json_sha256(payloads["borrow"]), expected_borrow
            )


if __name__ == "__main__":
    unittest.main()
