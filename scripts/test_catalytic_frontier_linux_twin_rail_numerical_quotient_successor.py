#!/usr/bin/env python3
"""Zero-contact tests for the neo-exp-0097 numerical quotient successor."""

from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_linux_twin_rail_numerical_quotient_successor as candidate


class TwinRailNumericalQuotientSuccessorTests(unittest.TestCase):
    def test_identity_is_distinct_and_schedule_is_frozen(self) -> None:
        self.assertEqual(candidate.EXPERIMENT_ID, "neo-exp-0097")
        self.assertEqual(candidate.ATTEMPT_ID, "frontier-attempt-0145")
        self.assertEqual(
            candidate.PREREGISTRATION_ATTEMPT_ID,
            "frontier-attempt-0144",
        )
        self.assertEqual(
            candidate.parent.parent.parent.EXPECTED_MODEL_CALLBACKS,
            38,
        )
        self.assertEqual(
            candidate.parent.parent.parent.EXPECTED_DIRECT_PROTOCOL_ACTIONS,
            29,
        )

    def test_import_does_not_mutate_consumed_predecessors(self) -> None:
        self.assertEqual(candidate.parent.EXPERIMENT_ID, "neo-exp-0096")
        self.assertEqual(candidate.parent.parent.EXPERIMENT_ID, "neo-exp-0095")
        self.assertEqual(
            candidate.parent.parent.parent.EXPERIMENT_ID,
            "neo-exp-0094",
        )

    def test_install_and_restore_identity_are_exact(self) -> None:
        candidate.install_identity()
        try:
            for module in (
                candidate.parent,
                candidate.parent.parent,
                candidate.parent.parent.parent,
            ):
                self.assertEqual(module.EXPERIMENT_ID, "neo-exp-0097")
                self.assertEqual(module.ATTEMPT_ID, "frontier-attempt-0145")
            self.assertEqual(
                candidate.parent.parent.parent.DEFAULT_RUNTIME_MANIFEST,
                candidate.DEFAULT_RUNTIME_MANIFEST,
            )
        finally:
            candidate.restore_identity()
        self.assertEqual(candidate.parent.EXPERIMENT_ID, "neo-exp-0096")
        self.assertEqual(candidate.parent.parent.EXPERIMENT_ID, "neo-exp-0095")
        self.assertEqual(
            candidate.parent.parent.parent.EXPERIMENT_ID,
            "neo-exp-0094",
        )

    def test_manifest_freezes_route_scope_classes_and_no_hidden_scores(self) -> None:
        original = candidate._BASE_RUNTIME_MANIFEST_TEMPLATE
        candidate._BASE_RUNTIME_MANIFEST_TEMPLATE = lambda _commit: {
            "capture_progress_counter_reset_before_first_progress": True,
            "one_token_control_projection_terminal_class": {
                "finish_reason": "limit",
                "generated_tokens": 1,
                "generic_model_generation_eos_only": True,
                "route_scope": ["dephased", "reordered-forward"],
            },
        }
        try:
            manifest = candidate.runtime_manifest_template("source-commit")
        finally:
            candidate._BASE_RUNTIME_MANIFEST_TEMPLATE = original
        quotient = manifest["reordered_canonical_numerical_quotient"]
        self.assertEqual(quotient["route_variant"], 2)
        self.assertEqual(
            quotient["restoration_class"],
            "INVERSE_PLUS_CANONICAL_NUMERICAL_QUOTIENT",
        )
        self.assertFalse(quotient["raw_scores_logged_or_returned"])
        self.assertEqual(
            manifest["primary_nondegenerate_margin_guard"][
                "top_two_margin_exclusive"
            ],
            2.0e-12,
        )

    def test_successor_bypasses_consumed_result_validators_but_keeps_closure(self) -> None:
        self.assertIs(
            candidate._BASE_VALIDATE_RUNTIME_MANIFEST,
            candidate.parent._BASE_VALIDATE_RUNTIME_MANIFEST,
        )

    def test_static_audit_adds_quotient_without_contact(self) -> None:
        candidate.install_identity()
        try:
            value = candidate.static_audit()
        finally:
            candidate.restore_identity()
        self.assertTrue(all(value["gates"].values()))
        self.assertTrue(
            value["gates"]["route_scoped_canonical_numerical_quotient"]
        )
        self.assertTrue(value["gates"]["numerical_quotient_exact_oracle"])
        self.assertTrue(value["numerical_quotient_oracle"]["passed"])
        self.assertEqual(value["id"], "neo-exp-0097")
        self.assertFalse(value["scientific_contact"])


if __name__ == "__main__":
    unittest.main()
