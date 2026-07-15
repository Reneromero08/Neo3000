#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import catalytic_kernel_0_balanced_opaque as balanced


ROOT = Path(__file__).resolve().parents[1]
CXX_RE = re.compile(r"(?<![A-Za-z0-9])C\d{2}(?![A-Za-z0-9])")
SYNTHETIC_BINDING_1_ROOT = bytes(range(32))
SYNTHETIC_BINDING_2_ROOT = bytes(reversed(range(32)))


def private_pair() -> tuple[balanced.PrivateBinding, balanced.PrivateBinding]:
    return (
        balanced.PrivateBinding.from_secret(
            SYNTHETIC_BINDING_1_ROOT, balanced.BINDING_1
        ),
        balanced.PrivateBinding.from_secret(
            SYNTHETIC_BINDING_2_ROOT, balanced.BINDING_2
        ),
    )


def runtime(
    configuration: balanced.PrivateBindingConfiguration,
    run_id: str,
    secret: bytes,
) -> balanced.BalancedOpaqueRuntime:
    return balanced.BalancedOpaqueRuntime(
        repository=ROOT,
        run_id=run_id,
        private=balanced.PrivateBinding.from_secret(secret, configuration),
    )


class BalancedOpaqueBinding2Tests(unittest.TestCase):
    def test_01_binding_1_commitment_construction_remains_exact(self) -> None:
        private = balanced.PrivateBinding.from_secret(
            SYNTHETIC_BINDING_1_ROOT, balanced.BINDING_1
        )
        self.assertEqual(
            private.secret_commitment,
            "20D9FC77E337E773BE7CD7164AA1807D3248C56AE149B02E96D46B4D9969C296",
        )
        self.assertEqual(
            private.alias_map_commitment,
            "2C7F2F868FCF53151CD9AEC164E1C6B2EB2AEEC3153FABA317E44AE78DCAB61B",
        )
        self.assertEqual(
            dict(private.branch_alias_map_commitments),
            {
                "branch-a": "F9284EF72BCCC8561EC76FF4EAECE04852106B4DE488600793F050846B641CDE",
                "branch-b": "F92BB1239F781D9FD37796395BACA437A444E20F9982964B75D6D2F0A2963E18",
            },
        )
        self.assertEqual(
            {
                run_id: balanced.run_key_commitment(
                    private.run_key(run_id), balanced.BINDING_1
                )
                for run_id in balanced.BINDING_1.run_modes
            },
            {
                balanced.FULL_RUN_ID: "7C6A517A9469C3DF7D398BA64C99EF5C37D1811B55B216A10FB289FD13622A20",
                balanced.DELETE_A_RUN_ID: "60894F8C4574C5552D9F9A07B28DC9891FCFE659A8C0813C0BB06CF306916165",
                balanced.DELETE_B_RUN_ID: "0A2F3A747C6F8C11CB7DB51FB6D91F5765DD8E67825A88831A6B9F770D680BF8",
            },
        )

    def test_02_binding_1_model_payload_hashes_remain_exact(self) -> None:
        expected = {
            balanced.FULL_RUN_ID: {
                "borrow": "24E87CE8707F0F8F7168BBA4D6B55EC3AF3573E3640606BB2430BE425332BCB0",
                "branch-a": "1478019EDF68FC1D904877E2B2ED9039BF710E540C084CFEE052BB706E2CFF6A",
                "branch-b": "84FCC735293141245A49705268677CCEDE907119A1E38E41AA61400BC5F9668D",
                "transform": "CB346824C860FB55804D64E1E1411E9D2B37E94EA2A3F0BE6F143D4824F9E2D2",
                "extract": "010A24307C6E4059C1F10E8D0A24FDC16A1A3BF03A5D344365E3780F71840A8B",
                "restore": "2D7F56D9D275C46DDF5CCC63E44B6F33B9125D7D38EF2E5AD56EC7D18D54BE6E",
            },
            balanced.DELETE_A_RUN_ID: {
                "borrow": "24E87CE8707F0F8F7168BBA4D6B55EC3AF3573E3640606BB2430BE425332BCB0",
                "branch-a": "1478019EDF68FC1D904877E2B2ED9039BF710E540C084CFEE052BB706E2CFF6A",
                "branch-b": "84FCC735293141245A49705268677CCEDE907119A1E38E41AA61400BC5F9668D",
                "transform": "03451314A3FF8A6D95424F7343628637B813A9520D7846C143F2F9EE62DD3476",
                "extract": "BADDFA19E3F551F7E4A9F047E47C8BA0B3F8A030AC40E9970C93F10B2763DA30",
                "restore": "2D7F56D9D275C46DDF5CCC63E44B6F33B9125D7D38EF2E5AD56EC7D18D54BE6E",
            },
            balanced.DELETE_B_RUN_ID: {
                "borrow": "24E87CE8707F0F8F7168BBA4D6B55EC3AF3573E3640606BB2430BE425332BCB0",
                "branch-a": "1478019EDF68FC1D904877E2B2ED9039BF710E540C084CFEE052BB706E2CFF6A",
                "branch-b": "84FCC735293141245A49705268677CCEDE907119A1E38E41AA61400BC5F9668D",
                "transform": "ADDCE122F2BDF282EC4DB051EE1E3CDD54608367D0AD674666AA69C5C2482B1D",
                "extract": "BEF37D3B7EC3633C1112FC0168674E41A9A48F7C6FC951F450D3D2852705771E",
                "restore": "2D7F56D9D275C46DDF5CCC63E44B6F33B9125D7D38EF2E5AD56EC7D18D54BE6E",
            },
        }
        actual = {
            run_id: {
                request_id: balanced.json_sha256(payload)
                for request_id, payload in balanced.static_model_visible_payloads(
                    SYNTHETIC_BINDING_1_ROOT, run_id, balanced.BINDING_1
                ).items()
            }
            for run_id in balanced.BINDING_1.run_modes
        }
        self.assertEqual(actual, expected)

    def test_03_binding_2_private_paths_are_ignored_regular_and_once_only(self) -> None:
        for relative in (
            balanced.BINDING_2.secret_path,
            balanced.BINDING_2.creation_receipt_path,
        ):
            ignored = subprocess.run(
                ["git", "check-ignore", "--quiet", relative],
                cwd=ROOT,
                check=False,
            )
            self.assertEqual(ignored.returncode, 0)
            path = ROOT / relative
            self.assertTrue(path.is_file())
            self.assertFalse(path.is_symlink())
        with tempfile.TemporaryDirectory(dir=ROOT / "state") as temporary:
            repository = Path(temporary)
            (repository / "state").mkdir()
            path = balanced.create_private_secret_once(repository, balanced.BINDING_2)
            self.assertEqual(path.stat().st_size, 32)
            with self.assertRaises(balanced.BalancedOpaqueError):
                balanced.create_private_secret_once(repository, balanced.BINDING_2)
        with tempfile.TemporaryDirectory(dir=ROOT / "state") as temporary:
            repository = Path(temporary)
            receipt = repository / balanced.BINDING_2.creation_receipt_path
            receipt.parent.mkdir(parents=True)
            receipt.write_text("inconsistent-state", encoding="utf-8")
            with self.assertRaises(balanced.BalancedOpaqueError):
                balanced.create_private_secret_once(repository, balanced.BINDING_2)
            self.assertFalse(
                (repository / balanced.BINDING_2.secret_path).exists()
            )

    def test_04_binding_2_alias_derivation_is_deterministic(self) -> None:
        _, profile = balanced.build_profile_binding(balanced.BINDING_2)
        first = balanced.derive_alias_mapping(
            SYNTHETIC_BINDING_2_ROOT, profile, balanced.BINDING_2
        )
        second = balanced.derive_alias_mapping(
            SYNTHETIC_BINDING_2_ROOT, profile, balanced.BINDING_2
        )
        self.assertTrue(first == second)
        self.assertEqual(set(first), set(balanced.ALIASES))
        self.assertEqual(set(first.values()), {f"C{index:02d}" for index in range(64)})

    def test_05_complete_binding_2_alias_map_differs(self) -> None:
        first, second = private_pair()
        self.assertTrue(dict(first.alias_to_internal) != dict(second.alias_to_internal))
        self.assertNotEqual(first.alias_map_commitment, second.alias_map_commitment)

    def test_06_private_singleton_alias_differs(self) -> None:
        first, second = private_pair()
        winner = balanced.EXPECTED_FULL_SUPPORT[0]
        self.assertTrue(first.internal_to_alias[winner] != second.internal_to_alias[winner])

    def test_07_both_ordered_support_tuples_differ(self) -> None:
        first, second = private_pair()
        for branch in ("branch-a", "branch-b"):
            one = tuple(
                sorted(first.internal_to_alias[item] for item in balanced.EXPECTED_SUPPORTS[branch])
            )
            two = tuple(
                sorted(second.internal_to_alias[item] for item in balanced.EXPECTED_SUPPORTS[branch])
            )
            self.assertTrue(one != two)

    def test_08_both_branch_presentations_differ(self) -> None:
        first, second = private_pair()
        winner = balanced.EXPECTED_FULL_SUPPORT[0]
        for branch in ("branch-a", "branch-b"):
            self.assertNotEqual(
                first.branch_alias_map_commitments[branch],
                second.branch_alias_map_commitments[branch],
            )
            one = {value: key for key, value in first.branch_alias_to_internal[branch].items()}
            two = {value: key for key, value in second.branch_alias_to_internal[branch].items()}
            self.assertTrue(one[winner] != two[winner])

    def test_09_binding_2_run_keys_are_independent_and_run_bound(self) -> None:
        first, second = private_pair()
        one = {
            balanced.run_key_commitment(first.run_key(run_id), balanced.BINDING_1)
            for run_id in balanced.BINDING_1.run_modes
        }
        two = {
            balanced.run_key_commitment(second.run_key(run_id), balanced.BINDING_2)
            for run_id in balanced.BINDING_2.run_modes
        }
        self.assertEqual(len(two), 3)
        self.assertTrue(one.isdisjoint(two))

    def test_10_carrier_prompts_schemas_and_seeds_are_binding_invariant(self) -> None:
        first, second = private_pair()
        report = balanced.static_payload_invariance_report(first, second)
        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["immutable_carrier_root_exact"])
        self.assertEqual(
            balanced.build_carrier()["carrier_root_sha256"],
            "E66846DC5097C5E9D6CFE5DC8679660CC193648DAE7A555AAA2587BE8A371033",
        )
        self.assertEqual(report["schemas_exact"], balanced.response_schema_hashes())

    def test_11_binding_identity_and_correspondence_never_enter_payloads(self) -> None:
        first, second = private_pair()
        forbidden = {
            balanced.BINDING_2.profile_id,
            first.secret_commitment,
            second.secret_commitment,
            first.alias_map_commitment,
            second.alias_map_commitment,
            *first.branch_alias_map_commitments.values(),
            *second.branch_alias_map_commitments.values(),
        }
        for run_id in balanced.BINDING_2.run_modes:
            for payload in balanced.static_model_visible_payloads(
                SYNTHETIC_BINDING_2_ROOT, run_id, balanced.BINDING_2
            ).values():
                text = balanced.canonical_json_text(payload)
                self.assertIsNone(CXX_RE.search(text))
                self.assertTrue(all(value not in text for value in forbidden))

    def test_12_binding_2_deletion_receipt_shape_is_frozen(self) -> None:
        for run_id, deleted_role in (
            (balanced.BINDING_2_DELETE_A_RUN_ID, "parent-0"),
            (balanced.BINDING_2_DELETE_B_RUN_ID, "parent-1"),
        ):
            instance = runtime(
                balanced.BINDING_2, run_id, SYNTHETIC_BINDING_2_ROOT
            )
            artifacts = {
                "branch-a": instance.normalize_branch("branch-a", ["K00"]),
                "branch-b": instance.normalize_branch("branch-b", ["K01"]),
            }
            parents = instance.assignment("transform", artifacts)["parent_artifacts"]
            self.assertEqual([item["artifact_role"] for item in parents], ["parent-0", "parent-1"])
            receipt = next(item for item in parents if item["artifact_role"] == deleted_role)
            self.assertEqual(set(receipt), set(balanced.DELETION_RECEIPT_FIELDS))

    def test_13_three_binding_2_run_ids_are_reserved_and_unconsumed(self) -> None:
        document = json.loads((ROOT / balanced.BINDING_2.preregistration_path).read_bytes())
        runs = document["future_runs"]["runs"]
        self.assertEqual({item["run_id"] for item in runs}, set(balanced.BINDING_2.run_modes))
        self.assertTrue(all(item["authorized_invocations"] == 0 for item in runs))
        self.assertTrue(all(item["reservation_state"] == "reserved-unconsumed" for item in runs))
        self.assertTrue(
            all(
                not (ROOT / "state" / "catalytic_kernel_0" / run_id).exists()
                for run_id in balanced.BINDING_2.run_modes
            )
        )

    def test_14_full_first_boundary_blocks_both_deletion_controls(self) -> None:
        document = json.loads((ROOT / balanced.BINDING_2.preregistration_path).read_bytes())
        boundary = document["future_authorization_boundary"]
        self.assertFalse(boundary["live_authority_granted"])
        self.assertFalse(boundary["delete_a_authorized"])
        self.assertFalse(boundary["delete_b_authorized"])
        self.assertEqual(
            boundary["only_next_separately_authorizable_action"],
            balanced.BINDING_2_FULL_RUN_ID,
        )
        with self.assertRaises(balanced.BalancedOpaqueError):
            balanced._require_terminal_full_run(ROOT, balanced.BINDING_2)


if __name__ == "__main__":
    unittest.main()
