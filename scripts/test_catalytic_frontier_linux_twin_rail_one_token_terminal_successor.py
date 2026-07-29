#!/usr/bin/env python3
"""Zero-contact tests for the neo-exp-0096 one-token terminal successor."""

from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_harness as harness
import catalytic_frontier_linux_twin_rail_one_token_terminal_successor as candidate


def exact_fixture() -> dict:
    generated = [32]
    return {
        "http_status": 200,
        "terminal_stop_evidence": {"observed": True, "stop": True},
        "finish_reason": "limit",
        "completion_tokens": 1,
        "generated_token_count": 1,
        "generated_token_ids": generated,
        "completion_token_count_match": True,
        "generated_token_sha256": harness.carrier.sha256_bytes(
            harness.carrier.canonical_json_bytes(generated)
        ),
    }


class TwinRailOneTokenTerminalSuccessorTests(unittest.TestCase):
    def test_identity_is_distinct_and_schedule_is_frozen(self) -> None:
        self.assertEqual(candidate.EXPERIMENT_ID, "neo-exp-0096")
        self.assertEqual(candidate.ATTEMPT_ID, "frontier-attempt-0143")
        self.assertEqual(
            candidate.PREREGISTRATION_ATTEMPT_ID,
            "frontier-attempt-0142",
        )
        self.assertEqual(candidate.parent.parent.EXPECTED_MODEL_CALLBACKS, 38)
        self.assertEqual(
            candidate.parent.parent.EXPECTED_DIRECT_PROTOCOL_ACTIONS,
            29,
        )

    def test_import_does_not_mutate_consumed_predecessors(self) -> None:
        self.assertEqual(candidate.parent.EXPERIMENT_ID, "neo-exp-0095")
        self.assertEqual(candidate.parent.parent.EXPERIMENT_ID, "neo-exp-0094")

    def test_install_and_restore_identity_are_exact(self) -> None:
        candidate.install_identity()
        try:
            self.assertEqual(candidate.parent.EXPERIMENT_ID, "neo-exp-0096")
            self.assertEqual(
                candidate.parent.parent.EXPERIMENT_ID,
                "neo-exp-0096",
            )
            self.assertEqual(
                candidate.parent.parent.DEFAULT_RUNTIME_MANIFEST,
                candidate.DEFAULT_RUNTIME_MANIFEST,
            )
        finally:
            candidate.restore_identity()
        self.assertEqual(candidate.parent.EXPERIMENT_ID, "neo-exp-0095")
        self.assertEqual(candidate.parent.parent.EXPERIMENT_ID, "neo-exp-0094")

    def test_exact_one_token_limit_terminal_passes(self) -> None:
        terminal = harness.validate_one_token_control_terminal(exact_fixture())
        self.assertEqual(
            terminal["operation_kind"],
            "one-token-control-projection",
        )
        self.assertEqual(terminal["generated_token_count"], 1)
        self.assertEqual(terminal["terminal_finish_reason"], "limit")

    def test_terminal_classifier_fails_closed_and_generic_stays_eos_only(self) -> None:
        invalid = []
        for key, value in (
            ("http_status", 500),
            ("finish_reason", "eos"),
            ("completion_tokens", 0),
            ("completion_tokens", True),
            ("generated_token_count", 0),
            ("generated_token_count", True),
            ("completion_token_count_match", False),
            ("generated_token_sha256", "0" * 64),
        ):
            fixture = exact_fixture()
            fixture[key] = value
            invalid.append((key, fixture))
        for name, tokens in (
            ("zero-token", []),
            ("two-token", [32, 33]),
            ("malformed-token", ["32"]),
        ):
            fixture = exact_fixture()
            fixture["generated_token_ids"] = tokens
            invalid.append((name, fixture))
        missing_stop = exact_fixture()
        missing_stop["terminal_stop_evidence"] = {
            "observed": True,
            "stop": False,
        }
        invalid.append(("missing-stop", missing_stop))
        for name, fixture in invalid:
            with self.subTest(name=name):
                with self.assertRaises(Exception):
                    harness.validate_one_token_control_terminal(fixture)
        with self.assertRaises(Exception):
            harness.carrier.validate_inference_terminal_evidence(
                exact_fixture(),
                operation_kind="model-generation",
            )

    def test_manifest_successor_skips_consumed_predecessor_result_validator(self) -> None:
        self.assertIs(
            candidate._BASE_VALIDATE_RUNTIME_MANIFEST,
            candidate.parent._BASE_VALIDATE_RUNTIME_MANIFEST,
        )
        original = candidate._BASE_RUNTIME_MANIFEST_TEMPLATE
        candidate._BASE_RUNTIME_MANIFEST_TEMPLATE = lambda _commit: {
            "capture_progress_counter_reset_before_first_progress": True,
        }
        try:
            manifest = candidate.runtime_manifest_template("source-commit")
        finally:
            candidate._BASE_RUNTIME_MANIFEST_TEMPLATE = original
        self.assertEqual(manifest["predecessor_experiment"], "neo-exp-0095")
        self.assertTrue(
            manifest["capture_progress_counter_reset_before_first_progress"]
        )
        self.assertEqual(
            manifest["one_token_control_projection_terminal_class"][
                "route_scope"
            ],
            ["dephased", "reordered-forward"],
        )

    def test_static_audit_adds_route_scope_without_contact(self) -> None:
        original = candidate.DEFAULT_RUNTIME_MANIFEST
        candidate.DEFAULT_RUNTIME_MANIFEST = (
            candidate.ROOT
            / "lab"
            / "neo-exp-0096-consumed-manifest-not-current-for-static-test.json"
        )
        candidate.install_identity()
        try:
            value = candidate.static_audit()
        finally:
            candidate.restore_identity()
            candidate.DEFAULT_RUNTIME_MANIFEST = original
        self.assertTrue(all(value["gates"].values()))
        self.assertTrue(
            value["gates"]["route_scoped_one_token_terminal_class"]
        )
        self.assertEqual(value["id"], "neo-exp-0096")
        self.assertFalse(value["scientific_contact"])


if __name__ == "__main__":
    unittest.main()
