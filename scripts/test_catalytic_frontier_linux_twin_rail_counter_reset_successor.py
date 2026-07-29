#!/usr/bin/env python3
"""Zero-contact tests for the neo-exp-0095 counter-reset successor."""

from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_linux_twin_rail_counter_reset_successor as candidate


class TwinRailCounterResetSuccessorTests(unittest.TestCase):
    def test_identity_is_distinct_and_schedule_is_frozen(self) -> None:
        self.assertEqual(candidate.EXPERIMENT_ID, "neo-exp-0095")
        self.assertEqual(candidate.ATTEMPT_ID, "frontier-attempt-0141")
        self.assertEqual(
            candidate.PREREGISTRATION_ATTEMPT_ID,
            "frontier-attempt-0140",
        )
        self.assertEqual(candidate.parent.EXPECTED_MODEL_CALLBACKS, 38)
        self.assertEqual(candidate.parent.EXPECTED_DIRECT_PROTOCOL_ACTIONS, 29)

    def test_import_does_not_mutate_consumed_parent_identity(self) -> None:
        self.assertEqual(candidate.parent.EXPERIMENT_ID, "neo-exp-0094")
        self.assertEqual(candidate.parent.ATTEMPT_ID, "frontier-attempt-0139")

    def test_install_and_restore_identity_are_exact(self) -> None:
        candidate.install_identity()
        try:
            self.assertEqual(candidate.parent.EXPERIMENT_ID, "neo-exp-0095")
            self.assertEqual(
                candidate.parent.DEFAULT_RUNTIME_MANIFEST,
                candidate.DEFAULT_RUNTIME_MANIFEST,
            )
            self.assertEqual(
                candidate.parent.DEFAULT_OUTPUT,
                candidate.DEFAULT_OUTPUT,
            )
        finally:
            candidate.restore_identity()
        self.assertEqual(candidate.parent.EXPERIMENT_ID, "neo-exp-0094")

    def test_counter_reset_precedes_initial_progress_and_late_reset(self) -> None:
        self.assertTrue(candidate.counter_reset_source_gate())

    def test_receipt_v2_remains_strict_about_prediction_count(self) -> None:
        source = (
            candidate.ROOT
            / "scripts"
            / "catalytic_frontier_live_terminal_boundary.py"
        ).read_text(encoding="utf-8")
        self.assertIn('value.get("tokens_predicted") == 0', source)

    def test_static_audit_adds_counter_gate_without_contact(self) -> None:
        original = candidate.DEFAULT_RUNTIME_MANIFEST
        candidate.DEFAULT_RUNTIME_MANIFEST = (
            candidate.ROOT
            / "lab"
            / "neo-exp-0095-consumed-manifest-not-current-for-static-test.json"
        )
        candidate.install_identity()
        try:
            value = candidate.static_audit()
        finally:
            candidate.restore_identity()
            candidate.DEFAULT_RUNTIME_MANIFEST = original
        self.assertTrue(all(value["gates"].values()))
        self.assertTrue(
            value["gates"]["capture_progress_current_request_counter_reset"]
        )
        self.assertEqual(value["id"], "neo-exp-0095")
        self.assertFalse(value["scientific_contact"])


if __name__ == "__main__":
    unittest.main()
