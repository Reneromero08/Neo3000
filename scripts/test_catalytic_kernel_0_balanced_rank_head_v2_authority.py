#!/usr/bin/env python3
from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path

import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2 as v2
import catalytic_kernel_0_balanced_rank_head_v2_authority as authority
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration
import catalytic_kernel_0_balanced_rank_head_v2_run_design as run_design


class RankHeadV2AuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spec = integration.RUN_SPECS[integration.BINDING_1_RUN_ID]
        cls.source_private = balanced.PrivateBinding.from_secret(
            bytes(range(32)),
            balanced.BINDING_1,
        )
        cls.private = integration.runtime_private_from_source(
            cls.source_private,
            cls.spec,
        )
        cls.run_design_projection = {
            "artifact_sha256": "A" * 64,
            "document_sha256": "B" * 64,
            "implementation_binding_sha256": "C" * 64,
        }
        cls.static_projection = {
            "artifact_sha256": "D" * 64,
            "document_sha256": "E" * 64,
            "design_contract_sha256": "F" * 64,
        }
        cls.commit = "1" * 40

    def build(self, raw: str = "2" * 64):
        return authority.build_external_authority(
            private=self.private,
            spec=self.spec,
            raw_authority_id=raw,
            authorized_commit=self.commit,
            current_commit=self.commit,
            run_design_projection=self.run_design_projection,
            static_preregistration_projection=self.static_projection,
            model_sha256="3" * 64,
            binary_sha256="4" * 64,
        )

    def test_authority_binds_exact_run_and_design(self) -> None:
        value = self.build()
        self.assertEqual(value.run_id, self.spec.run_id)
        self.assertEqual(value.run_ordinal, 1)
        self.assertEqual(value.source_binding, "binding-1")
        self.assertEqual(value.carrier_id, v2.V2_CARRIER_ID)
        self.assertEqual(value.state_root, run_design.STATE_ROOT)
        authority.validate_external_authority(
            self.private,
            value,
            spec=self.spec,
            current_commit=self.commit,
            receipt_hmac=authority.authority_receipt_hmac(self.private, value),
        )

    def test_wrong_commit_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            authority.RankHeadV2AuthorityError,
            "commit mismatch",
        ):
            authority.build_external_authority(
                private=self.private,
                spec=self.spec,
                raw_authority_id="2" * 64,
                authorized_commit=self.commit,
                current_commit="0" * 40,
                run_design_projection=self.run_design_projection,
                static_preregistration_projection=self.static_projection,
                model_sha256="3" * 64,
                binary_sha256="4" * 64,
            )

    def test_malformed_authority_id_is_rejected(self) -> None:
        for raw in ("", "0" * 63, "0" * 65, "Z" * 64):
            with self.assertRaises(authority.RankHeadV2AuthorityError):
                self.build(raw)

    def test_tampered_scope_or_hmac_is_rejected(self) -> None:
        value = self.build()
        tampered = dataclasses.replace(value, source_binding="binding-2")
        with self.assertRaisesRegex(
            authority.RankHeadV2AuthorityError,
            "scope mismatch",
        ):
            authority.validate_external_authority(
                self.private,
                tampered,
                spec=self.spec,
                current_commit=self.commit,
            )
        with self.assertRaisesRegex(
            authority.RankHeadV2AuthorityError,
            "HMAC mismatch",
        ):
            authority.validate_external_authority(
                self.private,
                value,
                spec=self.spec,
                current_commit=self.commit,
                receipt_hmac="0" * 64,
            )

    def test_receipt_schema_and_hashes_are_exact(self) -> None:
        self.assertEqual(
            set(authority.authority_object_schema()["required"]),
            set(self.build().body()),
        )
        self.assertRegex(authority.AUTHORITY_OBJECT_SCHEMA_SHA256, r"^[0-9A-F]{64}$")
        self.assertRegex(authority.AUTHORITY_RECEIPT_SCHEMA_SHA256, r"^[0-9A-F]{64}$")

    def test_receipt_path_is_per_run_and_versioned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = authority.authority_receipt_path(
                root,
                integration.BINDING_1_RUN_ID,
            )
            second = authority.authority_receipt_path(
                root,
                integration.BINDING_2_RUN_ID,
            )
            self.assertNotEqual(first, second)
            self.assertIn("rank_head_v2_authority", first.name)

    def test_same_raw_authority_hash_is_global_across_runs(self) -> None:
        self.assertEqual(
            authority.authority_id_sha256("A" * 64),
            authority.authority_id_sha256("a" * 64),
        )


if __name__ == "__main__":
    unittest.main()
