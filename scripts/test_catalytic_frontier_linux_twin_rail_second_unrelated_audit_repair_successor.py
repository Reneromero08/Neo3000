#!/usr/bin/env python3
"""Zero-contact identity and binding tests for neo-exp-0101."""

from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_linux_twin_rail_second_unrelated_audit_repair_successor as candidate


class TwinRailSecondUnrelatedAuditRepairTests(unittest.TestCase):
    def test_identity_propagates_and_restores(self) -> None:
        candidate.install_identity()
        try:
            for module in candidate._IDENTITY_MODULES:
                self.assertEqual(module.EXPERIMENT_ID, "neo-exp-0101")
            self.assertEqual(candidate.BASE.EXPECTED_MODEL_CALLBACKS, 48)
            self.assertEqual(
                candidate.BASE.EXPECTED_DIRECT_PROTOCOL_ACTIONS,
                29,
            )
        finally:
            candidate.restore_identity()
        self.assertEqual(candidate.parent.EXPERIMENT_ID, "neo-exp-0100")

    def test_source_gate_binds_both_public_audit_repairs(self) -> None:
        self.assertTrue(candidate.controller_audit_repair_source_gate())

    def test_manifest_changes_no_model_facing_work(self) -> None:
        original = candidate._BASE_RUNTIME_MANIFEST_TEMPLATE
        candidate._BASE_RUNTIME_MANIFEST_TEMPLATE = lambda _commit: {}
        try:
            manifest = candidate.runtime_manifest_template("source")
        finally:
            candidate._BASE_RUNTIME_MANIFEST_TEMPLATE = original
        repair = manifest["controller_audit_repair"]
        self.assertFalse(repair["capture_dictionary_exact_equality"])
        self.assertEqual(repair["model_facing_requests_changed"], 0)
        self.assertEqual(repair["model_callbacks_changed"], 0)
        self.assertEqual(repair["direct_protocol_actions_changed"], 0)
        self.assertEqual(repair["configured_cuda_units_changed"], 0)

    @unittest.skip(
        "LEGACY_PROVENANCE_CHECK: retired controller binds historical runtime artifacts"
    )
    def test_static_audit_is_zero_contact(self) -> None:
        candidate.install_identity()
        try:
            value = candidate.static_audit()
        finally:
            candidate.restore_identity()
        self.assertTrue(all(value["gates"].values()))
        self.assertEqual(value["id"], "neo-exp-0101")
        self.assertFalse(value["scientific_contact"])


if __name__ == "__main__":
    unittest.main()
