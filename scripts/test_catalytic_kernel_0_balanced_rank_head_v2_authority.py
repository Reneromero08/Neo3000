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
PREDECESSOR_COMMIT = "5" * 40
PREDECESSOR_RECORD_SHA = "6" * 64
PREDECESSOR_GATE = {
    "publication": {
        "layout": "split-experiment-record",
        "run_id": integration.BINDING_1_RUN_ID,
        "commit": PREDECESSOR_COMMIT,
        "record_sha256": PREDECESSOR_RECORD_SHA,
    }
}


def synthetic_private(run_id: str) -> balanced.PrivateBinding:
    spec = integration.known_run_spec(run_id)
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
            side_effect=lambda _repository, spec, **_kwargs: synthetic_private(spec.run_id),
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
        mock.patch.object(
            run_design,
            "require_binding_1_v2_terminal_visible",
            return_value=PREDECESSOR_GATE,
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
                side_effect=lambda _repository, spec, **_kwargs: synthetic_private(spec.run_id),
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
            mock.patch.object(
                run_design,
                "require_binding_1_v2_terminal_visible",
                return_value=PREDECESSOR_GATE,
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
            self.assertIsNone(value.predecessor_run_id)
            self.assertIsNone(value.predecessor_publication_commit)
            self.assertIsNone(value.predecessor_publication_record_sha256)
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

    def test_binding_2_authority_binds_published_predecessor_identity(self) -> None:
        with self.scoped():
            value = self.build(run_id=integration.BINDING_2_RUN_ID)
            self.assertEqual(
                value.predecessor_run_id,
                integration.BINDING_1_RUN_ID,
            )
            self.assertEqual(
                value.predecessor_publication_commit,
                PREDECESSOR_COMMIT,
            )
            self.assertEqual(
                value.predecessor_publication_record_sha256,
                PREDECESSOR_RECORD_SHA,
            )
            for tampered in (
                dataclasses.replace(
                    value,
                    predecessor_publication_commit="0" * 40,
                ),
                dataclasses.replace(
                    value,
                    predecessor_publication_record_sha256="0" * 64,
                ),
            ):
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

    def test_final_run_key_commitments_are_exact(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        expected = {
            integration.BINDING_1_RUN_ID: (
                "7B7E30422A76FFE057B381B586F21AF6F9A68563F5A2282136F3E217F1B8392C"
            ),
            integration.BINDING_2_RUN_ID: (
                "FEC400325777606A697687F990A24968B6AE787EDF444339A1639AE9BCFA8AC1"
            ),
        }
        for run_id, commitment in expected.items():
            with self.subTest(run_id=run_id):
                private = integration.runtime_private_from_repository(
                    repository,
                    run_id,
                )
                self.assertEqual(
                    balanced.run_key_commitment(
                        private.run_key(run_id),
                        private.configuration,
                    ),
                    commitment,
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
        source_private = balanced.PrivateBinding.from_secret(
            bytes(range(32)),
            balanced.BINDING_1,
        )
        with (
            mock.patch.object(
                balanced,
                "_private_binding_from_repository",
                return_value=source_private,
            ),
            mock.patch.object(
                integration,
                "runtime_private_from_source",
                return_value=substitute,
            ),
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
                authority.AUTHORITY_SCHEMA_VERSION,
                "rank-head-v2-external-one-shot-v3",
            )
            self.assertEqual(
                authority.RECEIPT_SCHEMA_VERSION,
                "rank-head-v2-authority-consumption-v3",
            )
            self.assertEqual(
                set(authority.authority_object_schema()["required"]),
                set(value.body()),
            )
            self.assertEqual(authority.authority_from_body(value.body()), value)
            with self.assertRaises(authority.RankHeadV2AuthorityError):
                authority.authority_from_body({**value.body(), "extra": True})
            self.assertEqual(
                authority.AUTHORITY_OBJECT_SCHEMA_SHA256,
                "5616C6D5ACEDD569D9DBF052890C48A44B9C2600FC5C536A2B18F4F5F02A07BB",
            )
            self.assertEqual(
                authority.AUTHORITY_RECEIPT_SCHEMA_SHA256,
                "7E44D619F5BCC4FC24F41E7CFE81946B7073C35349F6322F892AE0C5BC396A52",
            )
            self.assertEqual(
                authority.authority_object_schema()["properties"]["run_id"]["enum"],
                list(integration.RUN_ORDER),
            )

    def test_historical_and_unversioned_schema_identities_are_inactive(self) -> None:
        self.assertEqual(
            authority.HISTORICAL_V1_AUTHORITY_OBJECT_SCHEMA_SHA256,
            "8CDE8477F324E9E72C89F14908333937643675C2F42F92E67062DFE92F4A0CB3",
        )
        self.assertEqual(
            authority.HISTORICAL_V1_AUTHORITY_RECEIPT_SCHEMA_SHA256,
            "709552F6DDC2F31DC154C1C65F895F55637B7088B4F548FDFA1F771381E55411",
        )
        with self.assertRaisesRegex(
            authority.RankHeadV2AuthorityError,
            "historical v1.*inactive",
        ):
            authority.require_active_schema_identities(
                authority.HISTORICAL_V1_AUTHORITY_OBJECT_SCHEMA_SHA256,
                authority.HISTORICAL_V1_AUTHORITY_RECEIPT_SCHEMA_SHA256,
            )
        with self.assertRaisesRegex(
            authority.RankHeadV2AuthorityError,
            "unversioned replacement-run",
        ):
            authority.require_active_schema_identities(
                authority.UNVERSIONED_R2_AUTHORITY_OBJECT_SCHEMA_SHA256,
                authority.UNVERSIONED_R2_AUTHORITY_RECEIPT_SCHEMA_SHA256,
            )
        with self.assertRaisesRegex(
            authority.RankHeadV2AuthorityError,
            "historical consumed r2.*inactive",
        ):
            authority.require_active_schema_identities(
                authority.HISTORICAL_V2_AUTHORITY_OBJECT_SCHEMA_SHA256,
                authority.HISTORICAL_V2_AUTHORITY_RECEIPT_SCHEMA_SHA256,
            )
        self.assertEqual(
            authority.AUTHORITY_ID_DOMAIN,
            b"ck0-balanced-rank-head-v2/external-authority-id-v1\0",
        )
        self.assertEqual(
            authority.AUTHORITY_RECEIPT_DOMAIN,
            b"ck0-balanced-rank-head-v2/external-authority-v1\0",
        )

    def test_unversioned_receipt_is_rejected_by_verification_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.prepare_repository(repository)
            with self.scoped():
                value = self.build()
                document = authority._receipt_document(repository, value)
                document["authority_object_schema_sha256"] = (
                    authority.UNVERSIONED_R2_AUTHORITY_OBJECT_SCHEMA_SHA256
                )
                document["authority_receipt_schema_sha256"] = (
                    authority.UNVERSIONED_R2_AUTHORITY_RECEIPT_SCHEMA_SHA256
                )
                path = authority.authority_receipt_path(repository, value.run_id)
                path.write_bytes(balanced.canonical_json_bytes(document))
                with self.assertRaisesRegex(
                    authority.RankHeadV2AuthorityError,
                    "unversioned replacement-run",
                ):
                    authority.verify_authority_receipt(repository, value)

    def test_all_consumed_authority_hashes_are_blacklisted_for_all_runs(self) -> None:
        for run_id in integration.RUN_ORDER:
            for blocked in authority.HISTORICAL_CONSUMED_AUTHORITY_ID_BLACKLIST:
                with (
                    self.subTest(run_id=run_id, blocked=blocked),
                    self.scoped(),
                    mock.patch.object(
                        authority,
                        "authority_id_sha256",
                        return_value=blocked,
                    ),
                ):
                    with self.assertRaisesRegex(
                        authority.RankHeadV2AuthorityError,
                        "already consumed",
                    ):
                        self.build(run_id=run_id, raw="A" * 64)

    def test_consumption_rejects_blacklist_before_runtime_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.prepare_repository(repository)
            for run_id in integration.RUN_ORDER:
                with self.subTest(run_id=run_id), self.scoped():
                    value = dataclasses.replace(
                        self.build(run_id=run_id),
                        authority_id_sha256=(
                            authority.HISTORICAL_CONSUMED_AUTHORITY_ID_SHA256
                        ),
                    )
                    with self.assertRaisesRegex(
                        authority.RankHeadV2AuthorityError,
                        "already consumed",
                    ):
                        authority.consume_authority_once(
                            repository,
                            value,
                            expected_model_sha256=MODEL_SHA,
                            expected_binary_sha256=BINARY_SHA,
                        )
            self.assertFalse((repository / run_design.STATE_ROOT).exists())
            self.assertEqual(
                list(repository.glob("state/*rank_head_v2_authority*")),
                [],
            )

    def test_retired_r1_is_rejected_by_authority_and_receipt_surfaces(self) -> None:
        active = integration.run_spec(integration.BINDING_1_RUN_ID)
        retired = dataclasses.replace(
            active,
            run_id=integration.RETIRED_BINDING_1_RUN_ID,
        )
        with self.scoped(), self.assertRaisesRegex(
            integration.RankHeadV2IntegrationError,
            "RETIRED_PRECONSUMPTION_COMMAND_INVOKED",
        ):
            authority.build_external_authority(
                repository=Path("."),
                spec=retired,
                raw_authority_id="A" * 64,
                authorized_commit=COMMIT,
                current_commit=COMMIT,
                model_sha256=MODEL_SHA,
                binary_sha256=BINARY_SHA,
            )
        with self.assertRaisesRegex(
            integration.RankHeadV2IntegrationError,
            "RETIRED_PRECONSUMPTION_COMMAND_INVOKED",
        ):
            authority.authority_receipt_path(
                Path("."),
                integration.RETIRED_BINDING_1_RUN_ID,
            )

    def test_consumed_r2_is_historical_only_and_receipt_still_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.prepare_repository(repository)
            spec = integration.known_run_spec(
                integration.LOST_CUSTODY_BINDING_1_RUN_ID
            )
            private = synthetic_private(spec.run_id)
            value = authority.HistoricalRankHeadV2ExternalAuthority(
                schema_version=authority.HISTORICAL_V2_AUTHORITY_SCHEMA_VERSION,
                authority_kind=authority.AUTHORITY_KIND,
                authority_id_sha256=(
                    authority.HISTORICAL_R2_CONSUMED_AUTHORITY_ID_SHA256
                ),
                authorized_commit=COMMIT,
                run_id=spec.run_id,
                run_ordinal=spec.ordinal,
                source_binding=spec.source_binding,
                run_design_artifact_sha256="A" * 64,
                run_design_document_sha256="B" * 64,
                run_design_implementation_binding_sha256="C" * 64,
                static_preregistration_artifact_sha256="D" * 64,
                static_preregistration_document_sha256="E" * 64,
                static_design_contract_sha256="F" * 64,
                carrier_id=v2.V2_CARRIER_ID,
                carrier_root_sha256=v2.build_v2_carrier()["carrier_root_sha256"],
                state_root=run_design.STATE_ROOT,
                model_sha256=MODEL_SHA,
                binary_sha256=BINARY_SHA,
                run_key_commitment=balanced.run_key_commitment(
                    private.run_key(spec.run_id),
                    private.configuration,
                ),
            )
            with self.scoped():
                document = {
                    "schema_version": authority.HISTORICAL_V2_RECEIPT_SCHEMA_VERSION,
                    "authority": value.body(),
                    "authority_object_schema_sha256": (
                        authority.HISTORICAL_V2_AUTHORITY_OBJECT_SCHEMA_SHA256
                    ),
                    "authority_receipt_schema_sha256": (
                        authority.HISTORICAL_V2_AUTHORITY_RECEIPT_SCHEMA_SHA256
                    ),
                    "authority_receipt_hmac": (
                        authority._historical_v2_receipt_hmac(repository, value)
                    ),
                    "consumed": True,
                    "consumption_occurred_before_live_mutation": True,
                    "maximum_invocations": 1,
                    "retry_allowed": False,
                }
                path = authority.authority_receipt_path(repository, spec.run_id)
                path.write_bytes(balanced.canonical_json_bytes(document))
                evidence = authority.verify_authority_receipt_for_run(
                    repository,
                    spec.run_id,
                    require_current_static=False,
                )
                self.assertEqual(evidence["authority"], value.body())
                with self.assertRaisesRegex(
                    authority.RankHeadV2AuthorityError,
                    "cannot authorize execution",
                ):
                    authority.verify_authority_receipt_for_run(
                        repository,
                        spec.run_id,
                    )
                with self.assertRaisesRegex(
                    integration.RankHeadV2IntegrationError,
                    "SUCCESS_REPORTED_EVIDENCE_CUSTODY_LOST_AFTER_TEST_OVERWRITE",
                ):
                    integration.run_spec(spec.run_id)

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
                path.write_bytes(b"not-the-archived-receipt\n")
                from_bytes = authority.verify_authority_receipt_bytes_for_run(
                    repository,
                    value.run_id,
                    before,
                )
                self.assertEqual(from_bytes, evidence)
                path.write_bytes(before)
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
