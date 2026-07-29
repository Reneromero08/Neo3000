from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_linux_cuda_identity_qualifier as qualifier


class LinuxCudaIdentityQualifierTests(unittest.TestCase):
    def test_authenticated_windows_identity_is_predeclared_and_reusable(self):
        result = qualifier.classify_identity(
            answer="C",
            prompt_tokens=543,
            generated_sha256=qualifier.WINDOWS_GENERATED_SHA256,
            retained_tokens=qualifier.WINDOWS_RETAINED_TOKENS,
            schema_valid=True,
            eos_observed=True,
        )
        self.assertEqual(
            result["classification"],
            "HISTORICAL_WINDOWS_TASK_A_TRAJECTORY_RECOVERED",
        )
        self.assertTrue(result["prospectively_reusable_for_next_experiment"])

    def test_consumed_0088_linux_identity_is_predeclared_and_reusable(self):
        result = qualifier.classify_identity(
            answer="C",
            prompt_tokens=543,
            generated_sha256=qualifier.LINUX_0088_GENERATED_SHA256,
            retained_tokens=qualifier.LINUX_0088_RETAINED_TOKENS,
            schema_valid=True,
            eos_observed=True,
        )
        self.assertEqual(
            result["classification"],
            "NATIVE_LINUX_0088_TASK_A_TRAJECTORY_REPLICATED",
        )
        self.assertTrue(result["prospectively_reusable_for_next_experiment"])

    def test_novel_correct_identity_requires_a_future_replication(self):
        result = qualifier.classify_identity(
            answer="C",
            prompt_tokens=543,
            generated_sha256="0" * 64,
            retained_tokens=601,
            schema_valid=True,
            eos_observed=True,
        )
        self.assertEqual(
            result["classification"],
            "NEW_CORRECT_LINUX_TRAJECTORY_REQUIRES_PROSPECTIVE_REPLICATION",
        )
        self.assertFalse(result["prospectively_reusable_for_next_experiment"])

    def test_utility_failure_cannot_be_reused(self):
        result = qualifier.classify_identity(
            answer="A",
            prompt_tokens=543,
            generated_sha256=qualifier.WINDOWS_GENERATED_SHA256,
            retained_tokens=qualifier.WINDOWS_RETAINED_TOKENS,
            schema_valid=True,
            eos_observed=True,
        )
        self.assertEqual(
            result["classification"],
            "TASK_A_UTILITY_OR_PROMPT_IDENTITY_FAILED",
        )
        self.assertFalse(result["prospectively_reusable_for_next_experiment"])

    def test_missing_eos_is_a_utility_failure(self):
        result = qualifier.classify_identity(
            answer="C",
            prompt_tokens=543,
            generated_sha256=qualifier.LINUX_0088_GENERATED_SHA256,
            retained_tokens=qualifier.LINUX_0088_RETAINED_TOKENS,
            schema_valid=True,
            eos_observed=False,
        )
        self.assertEqual(
            result["classification"],
            "TASK_A_UTILITY_OR_PROMPT_IDENTITY_FAILED",
        )

    def test_controller_has_one_model_request_and_no_root_or_live_route(self):
        source = Path(qualifier.__file__).read_text(encoding="utf-8")
        runtime = source[: source.index("def static_audit(")]
        self.assertEqual(runtime.count("harness.run_completion("), 1)
        self.assertNotIn("root_action(", runtime)
        self.assertNotIn("run_live_sequence", runtime)
        self.assertIn('"NO_RESTORATION_CLAIM"', runtime)

    def test_result_is_persisted_only_after_process_cleanup(self):
        source = Path(qualifier.__file__).read_text(encoding="utf-8")
        cleanup_index = source.index("cleanup = sidecar.stop()")
        output_index = source.index(
            "terminal.write_exclusive_json(output, result)",
        )
        self.assertLess(cleanup_index, output_index)

    def test_precontact_properties_and_failure_capture_are_ordered(self):
        source = Path(qualifier.__file__).read_text(encoding="utf-8")
        self.assertLess(
            source.index("props = codec.props()"),
            source.index('run_root / "scientific-contact.json"'),
        )
        self.assertLess(
            source.index("task = harness.run_completion("),
            source.index('progress["task_a_capture"]'),
        )
        self.assertIn('progress["retained_root_capture"]', source)
        self.assertEqual(qualifier.ATTEMPT_ID, "frontier-attempt-0129")

    def test_precontact_failure_does_not_consume_canonical_output(self):
        source = Path(qualifier.__file__).read_text(encoding="utf-8")
        self.assertIn(
            'f"{EXPERIMENT_ID}-precontact-{time.time_ns()}.json"',
            source,
        )
        self.assertIn('if progress["scientific_contact"]', source)


if __name__ == "__main__":
    unittest.main()
