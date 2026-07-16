#!/usr/bin/env python3
from __future__ import annotations

import dataclasses
import inspect
import json
import multiprocessing
import os
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2 as v2
import catalytic_kernel_0_balanced_rank_head_v2_authority as authority
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration
import catalytic_kernel_0_balanced_rank_head_v2_run_design as run_design


RUN_PROJECTION = {
    "artifact_sha256": "A" * 64,
    "document_sha256": "B" * 64,
    "implementation_binding_sha256": "C" * 64,
}
STATIC_PROJECTION = {
    "artifact_sha256": "D" * 64,
    "document_sha256": "E" * 64,
    "design_contract_sha256": "F" * 64,
}
COMMIT = "1" * 40
MODEL_SHA = "3" * 64
BINARY_SHA = "4" * 64


def synthetic_private(run_id: str) -> balanced.PrivateBinding:
    spec = integration.run_spec(run_id)
    source = integration.source_configuration(spec)
    secret = bytes(range(32)) if spec.ordinal == 1 else bytes(reversed(range(32)))
    return integration.runtime_private_from_source(
        balanced.PrivateBinding.from_secret(secret, source),
        spec,
    )


def _consume_worker(
    repository_name: str,
    authority_body: dict,
    start: multiprocessing.synchronize.Event,
    output: multiprocessing.queues.Queue,
) -> None:
    repository = Path(repository_name)
    value = authority.authority_from_body(authority_body)
    start.wait(10)
    with (
        mock.patch.object(
            authority,
            "_runtime_private",
            side_effect=lambda _repository, spec: synthetic_private(spec.run_id),
        ),
        mock.patch.object(
            run_design,
            "validate_run_design",
            return_value=RUN_PROJECTION,
        ),
        mock.patch.object(
            v2,
            "validate_preregistration",
            return_value=STATIC_PROJECTION,
        ),
    ):
        try:
            authority.consume_authority_once(
                repository,
                value,
                expected_model_sha256=MODEL_SHA,
                expected_binary_sha256=BINARY_SHA,
            )
        except BaseException:
            output.put("fail")
        else:
            output.put("pass")


def _lock_and_die(repository_name: str) -> None:
    with authority.authority_consumption_lock(Path(repository_name)):
        os._exit(0)


class RankHeadV2AuthorityTests(unittest.TestCase):
    @contextmanager
    def scoped(self):
        with (
            mock.patch.object(
                authority,
                "_runtime_private",
                side_effect=lambda _repository, spec: synthetic_private(spec.run_id),
            ),
            mock.patch.object(
                run_design,
                "validate_run_design",
                return_value=RUN_PROJECTION,
            ),
            mock.patch.object(
                v2,
                "validate_preregistration",
                return_value=STATIC_PROJECTION,
            ),
        ):
            yield

    def build(
        self,
        *,
        run_id: str = integration.BINDING_1_RUN_ID,
        raw: str = "2" * 64,
        current_commit: str = COMMIT,
    ) -> authority.RankHeadV2ExternalAuthority:
        return authority.build_external_authority(
            repository=Path("."),
            spec=integration.run_spec(run_id),
            raw_authority_id=raw,
            authorized_commit=COMMIT,
            current_commit=current_commit,
            model_sha256=MODEL_SHA,
            binary_sha256=BINARY_SHA,
        )

    def prepare_repository(self, repository: Path) -> None:
        (repository / "state").mkdir()
        preregistration = repository / v2.PREREGISTRATION_PATH
        preregistration.parent.mkdir()
        preregistration.write_text("{}\n", encoding="utf-8")
        (repository / ".gitignore").write_text(
            "/state/catalytic_kernel_0_rank_head_v2/\n"
            "/state/catalytic_kernel_0_rank_head_v2_authority.*.authority.consumed.json\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=repository,
            check=True,
            capture_output=True,
        )

    def concurrent_outcomes(
        self,
        repository: Path,
        values: tuple[authority.RankHeadV2ExternalAuthority, ...],
    ) -> list[str]:
        context = multiprocessing.get_context("spawn")
        start = context.Event()
        output = context.Queue()
        processes = [
            context.Process(
                target=_consume_worker,
                args=(str(repository), value.body(), start, output),
            )
            for value in values
        ]
        for process in processes:
            process.start()
        start.set()
        for process in processes:
            process.join(20)
            self.assertEqual(process.exitcode, 0)
        return sorted(output.get(timeout=5) for _ in processes)

    def test_authority_binds_exact_run_design_static_model_and_binary(self) -> None:
        with self.scoped():
            value = self.build()
            self.assertEqual(value.run_id, integration.BINDING_1_RUN_ID)
            self.assertEqual(value.run_ordinal, 1)
            self.assertEqual(value.source_binding, "binding-1")
            self.assertEqual(value.carrier_id, v2.V2_CARRIER_ID)
            self.assertEqual(value.state_root, run_design.STATE_ROOT)
            authority.validate_external_authority(
                Path("."),
                value,
                spec=integration.run_spec(value.run_id),
                current_commit=COMMIT,
                receipt_hmac=authority.authority_receipt_hmac(Path("."), value),
                expected_model_sha256=MODEL_SHA,
                expected_binary_sha256=BINARY_SHA,
            )

    def test_wrong_commit_and_malformed_authority_id_are_rejected(self) -> None:
        with self.scoped():
            with self.assertRaisesRegex(
                authority.RankHeadV2AuthorityError,
                "commit mismatch",
            ):
                self.build(current_commit="0" * 40)
            for raw in ("", "0" * 63, "0" * 65, "Z" * 64):
                with self.assertRaises(authority.RankHeadV2AuthorityError):
                    self.build(raw=raw)

    def test_source_binding_scope_and_caller_private_substitution_fail(self) -> None:
        self.assertNotIn(
            "private",
            inspect.signature(authority.build_external_authority).parameters,
        )
        with self.scoped():
            value = self.build()
            tampered = dataclasses.replace(value, source_binding="binding-2")
            with self.assertRaisesRegex(
                authority.RankHeadV2AuthorityError,
                "scope mismatch",
            ):
                authority.validate_external_authority(
                    Path("."),
                    tampered,
                    spec=integration.run_spec(value.run_id),
                    current_commit=COMMIT,
                )
        spec = integration.run_spec(integration.BINDING_1_RUN_ID)
        private = synthetic_private(spec.run_id)
        changed_configuration = dataclasses.replace(
            private.configuration,
            profile_id="caller-constructed-substitute",
            domain_separation_identity="wrong-domain",
            secret_path="state/wrong.secret",
        )
        substitute = dataclasses.replace(
            private,
            configuration=changed_configuration,
        )
        with mock.patch.object(
            integration,
            "runtime_private_from_repository",
            return_value=substitute,
        ):
            with self.assertRaisesRegex(
                authority.RankHeadV2AuthorityError,
                "private binding scope changed",
            ):
                authority._runtime_private(Path("."), spec)

    def test_run_design_static_model_binary_and_hmac_tampering_fail(self) -> None:
        with self.scoped():
            value = self.build()
            cases = (
                dataclasses.replace(value, run_design_document_sha256="0" * 64),
                dataclasses.replace(value, static_design_contract_sha256="0" * 64),
                dataclasses.replace(value, model_sha256="0" * 64),
                dataclasses.replace(value, binary_sha256="0" * 64),
            )
            for tampered in cases:
                with self.assertRaisesRegex(
                    authority.RankHeadV2AuthorityError,
                    "scope mismatch",
                ):
                    authority.validate_external_authority(
                        Path("."),
                        tampered,
                        spec=integration.run_spec(value.run_id),
                        current_commit=COMMIT,
                        expected_model_sha256=MODEL_SHA,
                        expected_binary_sha256=BINARY_SHA,
                    )
            with self.assertRaisesRegex(
                authority.RankHeadV2AuthorityError,
                "HMAC mismatch",
            ):
                authority.validate_external_authority(
                    Path("."),
                    value,
                    spec=integration.run_spec(value.run_id),
                    current_commit=COMMIT,
                    receipt_hmac="0" * 64,
                )

    def test_receipt_schema_hashes_and_reconstruction_are_exact(self) -> None:
        with self.scoped():
            value = self.build()
            self.assertEqual(
                set(authority.authority_object_schema()["required"]),
                set(value.body()),
            )
            self.assertEqual(authority.authority_from_body(value.body()), value)
            with self.assertRaises(authority.RankHeadV2AuthorityError):
                authority.authority_from_body({**value.body(), "extra": True})
            self.assertRegex(
                authority.AUTHORITY_OBJECT_SCHEMA_SHA256,
                r"^[0-9A-F]{64}$",
            )
            self.assertRegex(
                authority.AUTHORITY_RECEIPT_SCHEMA_SHA256,
                r"^[0-9A-F]{64}$",
            )

    def test_consumed_receipt_verifies_cryptographically_and_is_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.prepare_repository(repository)
            with self.scoped():
                value = self.build()
                evidence = authority.consume_authority_once(
                    repository,
                    value,
                    expected_model_sha256=MODEL_SHA,
                    expected_binary_sha256=BINARY_SHA,
                )
                path = authority.authority_receipt_path(repository, value.run_id)
                before = path.read_bytes()
                self.assertEqual(
                    authority.verify_authority_receipt_for_run(
                        repository, value.run_id
                    ),
                    evidence,
                )
                self.assertEqual(path.read_bytes(), before)
                with self.assertRaisesRegex(
                    authority.RankHeadV2AuthorityError,
                    "already attempted",
                ):
                    authority.consume_authority_once(
                        repository,
                        value,
                        expected_model_sha256=MODEL_SHA,
                        expected_binary_sha256=BINARY_SHA,
                    )

    def test_same_authority_reuse_across_runs_and_different_id_same_run_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.prepare_repository(repository)
            with self.scoped():
                first = self.build(raw="A" * 64)
                authority.consume_authority_once(
                    repository,
                    first,
                    expected_model_sha256=MODEL_SHA,
                    expected_binary_sha256=BINARY_SHA,
                )
                second_run = self.build(
                    run_id=integration.BINDING_2_RUN_ID,
                    raw="a" * 64,
                )
                with self.assertRaisesRegex(
                    authority.RankHeadV2AuthorityError,
                    "already consumed",
                ):
                    authority.consume_authority_once(
                        repository,
                        second_run,
                        expected_model_sha256=MODEL_SHA,
                        expected_binary_sha256=BINARY_SHA,
                    )
                different_id = self.build(raw="B" * 64)
                with self.assertRaisesRegex(
                    authority.RankHeadV2AuthorityError,
                    "already attempted",
                ):
                    authority.consume_authority_once(
                        repository,
                        different_id,
                        expected_model_sha256=MODEL_SHA,
                        expected_binary_sha256=BINARY_SHA,
                    )
            self.assertFalse(
                (
                    repository
                    / run_design.STATE_ROOT
                    / integration.BINDING_2_RUN_ID
                ).exists()
            )

    def test_concurrent_process_consumption_has_exactly_one_winner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.prepare_repository(repository)
            with self.scoped():
                value = self.build()
            outcomes = self.concurrent_outcomes(repository, (value, value))
            self.assertEqual(outcomes, ["fail", "pass"])
            self.assertFalse(
                (repository / run_design.STATE_ROOT).exists()
            )

    def test_concurrent_cross_run_same_id_and_same_run_different_ids_each_have_one_winner(self) -> None:
        cases = (
            (
                lambda: self.build(
                    run_id=integration.BINDING_1_RUN_ID,
                    raw="A" * 64,
                ),
                lambda: self.build(
                    run_id=integration.BINDING_2_RUN_ID,
                    raw="a" * 64,
                ),
            ),
            (
                lambda: self.build(raw="B" * 64),
                lambda: self.build(raw="C" * 64),
            ),
        )
        for builders in cases:
            with self.subTest(case=builders), tempfile.TemporaryDirectory() as temporary:
                repository = Path(temporary)
                self.prepare_repository(repository)
                with self.scoped():
                    values = tuple(builder() for builder in builders)
                self.assertEqual(
                    self.concurrent_outcomes(repository, values),
                    ["fail", "pass"],
                )
                self.assertFalse((repository / run_design.STATE_ROOT).exists())

    def test_process_death_releases_lock_and_malformed_inventory_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.prepare_repository(repository)
            context = multiprocessing.get_context("spawn")
            process = context.Process(target=_lock_and_die, args=(str(repository),))
            process.start()
            process.join(20)
            self.assertEqual(process.exitcode, 0)
            with authority.authority_consumption_lock(repository):
                pass
            malformed = authority.authority_receipt_path(
                repository,
                integration.BINDING_1_RUN_ID,
            )
            malformed.write_text('{"malformed":true}\n', encoding="utf-8")
            with self.scoped():
                with self.assertRaisesRegex(
                    authority.RankHeadV2AuthorityError,
                    "inventory is invalid",
                ):
                    authority.assert_authority_unconsumed(
                        repository,
                        integration.BINDING_2_RUN_ID,
                        "A" * 64,
                    )
            source = inspect.getsource(authority.authority_consumption_lock)
            self.assertIn("msvcrt", source)
            self.assertIn("fcntl", source)

    def test_receipt_path_is_per_run_versioned_and_raw_id_not_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = authority.authority_receipt_path(
                root, integration.BINDING_1_RUN_ID
            )
            second = authority.authority_receipt_path(
                root, integration.BINDING_2_RUN_ID
            )
            self.assertNotEqual(first, second)
            self.assertIn("rank_head_v2_authority", first.name)
        with self.scoped():
            raw = "0123456789abcdef" * 4
            value = self.build(raw=raw)
            self.assertNotIn(raw, json.dumps(value.body()))
            self.assertEqual(
                authority.authority_id_sha256("A" * 64),
                authority.authority_id_sha256("a" * 64),
            )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    unittest.main()
