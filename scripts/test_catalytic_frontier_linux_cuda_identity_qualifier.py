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
            source.index('run_root / "request-intent.json"'),
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
        self.assertIn('if contact_adjudication["observed"]', source)

    def test_runtime_identity_comparison_rejects_one_byte_mutation(self):
        with self.assertRaisesRegex(
            qualifier.ExperimentError,
            "test artifact identity changed",
        ):
            qualifier.require_exact_identity(
                {"bytes": 7, "sha256": "a" * 64},
                {"bytes": 7, "sha256": "b" * 64},
                "test artifact",
            )

    def test_manifest_gate_precedes_all_scientific_contact(self):
        source = Path(qualifier.__file__).read_text(encoding="utf-8")
        main = source[source.rindex("def main() -> int:") :]
        self.assertLess(
            main.index("static = static_audit("),
            main.index("lock = acquire_lock("),
        )
        self.assertIn("linked_library_identities(binary)", source)
        self.assertIn("compiler_semantics_probe(compiler_contract", source)
        self.assertIn("binary_version_identity(binary)", source)
        self.assertIn("gpu_identity()", source)
        self.assertLess(
            main.index("require_pushed_frontier_head(args.expected_commit)"),
            main.index("readiness = sidecar.launch()"),
        )

    def test_request_intent_alone_is_not_scientific_contact(self):
        source = Path(qualifier.__file__).read_text(encoding="utf-8")
        self.assertNotIn('or "request_intent" in progress', source)
        self.assertFalse(
            qualifier.scientific_contact_from_evidence(
                response_bytes=0,
                server_prompt_evaluations=0,
                transport_attempted=False,
            )
        )
        self.assertTrue(
            qualifier.scientific_contact_from_evidence(
                response_bytes=1,
                server_prompt_evaluations=0,
                transport_attempted=False,
            )
        )
        self.assertTrue(
            qualifier.scientific_contact_from_evidence(
                response_bytes=0,
                server_prompt_evaluations=1,
                transport_attempted=False,
            )
        )
        self.assertTrue(
            qualifier.scientific_contact_from_evidence(
                response_bytes=0,
                server_prompt_evaluations=0,
                transport_attempted=True,
            )
        )

    def test_closure_requires_process_port_lock_and_no_errors(self):
        good_cleanup = {"candidate_stopped": True, "port_free": True}
        good_lock = {"released": True}
        self.assertTrue(
            qualifier.closure_evidence_passed(
                cleanup=good_cleanup,
                lock_release=good_lock,
                cleanup_errors=[],
            )
        )
        self.assertFalse(
            qualifier.closure_evidence_passed(
                cleanup=good_cleanup,
                lock_release=good_lock,
                cleanup_errors=[{"operation": "stop"}],
            )
        )

    def test_prompt_and_manifest_path_are_exactly_bound(self):
        self.assertEqual(
            qualifier.EXPECTED_PROMPT_TOKEN_SHA256,
            "17CC9100104C5C2C91E2BB3AA14143515F465B584427B91C4B757F5CB35336D2",
        )
        self.assertEqual(
            qualifier.EXPECTED_PAYLOAD_SHA256,
            "6D24B032682CEF73CA257694CB93EF73E24981B50D15F220B1F777DAC0E674B6",
        )
        self.assertEqual(
            qualifier.EXPECTED_TASK_A_CONTRACT["payload_sha256"],
            qualifier.EXPECTED_PAYLOAD_SHA256,
        )
        source = Path(qualifier.__file__).read_text(encoding="utf-8")
        self.assertIn(
            "manifest_file == DEFAULT_RUNTIME_MANIFEST.resolve(strict=True)",
            source,
        )
        self.assertIn(
            '["git", "show", f"HEAD:{relative_manifest}"]',
            source,
        )
        for name in (
            "carrier_source",
            "fanout_source",
            "harness_source",
            "inherited_source",
            "kernel_source",
            "terminal_source",
            "water_source",
            "warm_source",
        ):
            self.assertIn(f'"{name}"', source)

    def test_transport_raw_file_and_lock_order_fail_closed(self):
        source = Path(qualifier.__file__).read_text(encoding="utf-8")
        main = source[source.rindex("def main() -> int:") :]
        self.assertIn('progress["transport_attempted"] = True', source)
        self.assertIn(
            'self.sidecar.run_root / "request-transport-attempt.json"',
            source,
        )
        self.assertIn(
            "persisted_raw_bytes = raw_path.stat().st_size",
            source,
        )
        self.assertLess(
            main.index("sidecar = linux_sidecar.LinuxSidecar("),
            main.index("lock = acquire_lock("),
        )


if __name__ == "__main__":
    unittest.main()
