#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalytic_frontier_linux_chain_identity_qualifier as qualifier


class LinuxChainIdentityQualifierTests(unittest.TestCase):
    def test_exact_linux_geometry_is_frozen(self):
        self.assertEqual(qualifier.EXPECTED_RETAINED_COUNT, 607)
        self.assertEqual(qualifier.EXPECTED_BASE_COUNT, 684)
        self.assertEqual(qualifier.EXPECTED_BRANCH_COUNT, 685)
        self.assertEqual(qualifier.EXPECTED_SUCCESSOR_COUNT, 777)
        self.assertEqual(qualifier.EXPECTED_SUFFIX_COUNT, 87)

    def test_output_hashes_are_positional_expectations(self):
        self.assertEqual(qualifier.EXPECTED_ANSWERS, ("C", "D", "B"))
        self.assertEqual(
            qualifier.EXPECTED_GENERATED_SHA256["C"],
            "BD33E852EF9FDDEE49A1056501456071169FF3E3C7699C2A5BAAA2D0DF30CABC",
        )
        self.assertEqual(
            qualifier.EXPECTED_GENERATED_SHA256["D"],
            "0CA13167369ED1835BB8938644A7CCEF6EDE0BD65AE31C256931C54D3FA9FB31",
        )
        self.assertEqual(
            qualifier.EXPECTED_GENERATED_SHA256["B"],
            "4553BBC00B6AF27C3EBDE8F36EA9237A37B5D9C1AA182FBC65CDA71411A4B888",
        )

    def test_classification_stops_at_first_nonexact_stage(self):
        exact = [
            {
                "state": {
                    "answer": answer,
                    "generated_token_sha256": qualifier.EXPECTED_GENERATED_SHA256[
                        answer
                    ],
                }
            }
            for answer in qualifier.EXPECTED_ANSWERS
        ]
        self.assertEqual(
            qualifier.classify_stages(exact),
            "NATIVE_LINUX_607_BOUND_C_TO_D_TO_B_IDENTITIES_QUALIFIED",
        )
        novel = list(exact)
        novel[1] = {
            "state": {
                "answer": "D",
                "generated_token_sha256": "A" * 64,
            }
        }
        self.assertEqual(
            qualifier.classify_stages(novel[:2]),
            "STAGE_1_NOVEL_CORRECT_IDENTITY_REQUIRES_REPLICATION",
        )
        malformed = [{"state": None}]
        self.assertEqual(
            qualifier.classify_stages(malformed),
            "STAGE_0_UTILITY_OR_TERMINAL_FAILURE",
        )

    def test_static_contract_is_fully_materialized_and_root_free(self):
        source = Path(qualifier.__file__).read_text(encoding="utf-8")
        runtime_source = source[: source.index("def static_audit()")]
        self.assertIn("cache_prompt=False", runtime_source)
        self.assertNotIn("root_action(", runtime_source)
        self.assertNotIn("run_live_sequence", runtime_source)
        self.assertIn(
            "if not stage_exact(stages[-1], ordinal - 1):",
            runtime_source,
        )

    def test_output_follows_process_and_lock_closure(self):
        source = Path(qualifier.__file__).read_text(encoding="utf-8")
        main = source[source.rindex("def main() -> int:") :]
        self.assertLess(
            main.index("cleanup = sidecar.stop()"),
            main.index("terminal.write_exclusive_json(output, result)"),
        )
        self.assertLess(
            main.index("lock_release = release_lock(lock_path)"),
            main.index("terminal.write_exclusive_json(output, result)"),
        )

    def test_transport_marker_precedes_callback(self):
        source = Path(qualifier.__file__).read_text(encoding="utf-8")
        self.assertLess(
            source.index('self.progress["consumption_marker"]'),
            source.index("return callback()"),
        )
        self.assertLess(
            source.index("attempts.append(marker)"),
            source.index("return callback()"),
        )

    def test_output_and_consumption_paths_are_identity_canonical(self):
        source = Path(qualifier.__file__).read_text(encoding="utf-8")
        main = source[source.rindex("def main() -> int:") :]
        self.assertIn(
            "output == DEFAULT_OUTPUT.resolve(strict=False)",
            main,
        )
        self.assertIn(
            "consumed_marker "
            "== DEFAULT_CONSUMED_MARKER.resolve(strict=False)",
            main,
        )
        admission = main[: main.index("run_root = (")]
        self.assertIn("cannot be overridden", admission)

    def test_runtime_is_revalidated_immediately_before_launch(self):
        source = Path(qualifier.__file__).read_text(encoding="utf-8")
        main = source[source.rindex("def main() -> int:") :]
        first = main.index("static = static_audit()")
        second = main.index("prelaunch_static = static_audit()")
        launch = main.index("readiness = sidecar.launch()")
        self.assertLess(first, second)
        self.assertLess(second, launch)
        self.assertNotIn("sidecar.", main[second + 1 : launch])

    def test_failed_closure_withholds_stage_outcomes(self):
        source = Path(qualifier.__file__).read_text(encoding="utf-8")
        self.assertIn('"status": "poisoned-before-closure"', source)
        self.assertIn('"outcome_projection_withheld": True', source)
        custody = source[
            source.index("custody_failure = {") :
            source.index("failure = full_failure if closure else custody_failure")
        ]
        self.assertNotIn("result_before_cleanup", custody)
        self.assertNotIn("stage_captures", custody)

    def test_no_permanent_removal_api(self):
        source = Path(qualifier.__file__).read_text(encoding="utf-8")
        runtime_source = source[: source.index("def static_audit()")]
        for token in ("rmtree", ".unlink(", "os.remove", "rmdir("):
            self.assertNotIn(token, runtime_source)


if __name__ == "__main__":
    unittest.main()
