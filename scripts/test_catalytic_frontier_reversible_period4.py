from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_fixed_size_rebase as fixed_size
import catalytic_frontier_reversible_period4 as period4


class ReversiblePeriod4Tests(unittest.TestCase):
    def steps(self) -> list[dict[str, str]]:
        generated = dict(period4.EXPECTED_GENERATED_SHA256)
        child = dict(period4.EXPECTED_CHILD_SHA256)
        request = dict(period4.EXPECTED_REQUEST_SHA256)
        sequence = period4.EXPECTED_STATE_SEQUENCE
        return [
            {
                "generated_token_sha256": generated[sequence[index]],
                "child_token_sha256": child[sequence[index]],
                "prompt_token_sha256": request[sequence[index - 1]],
            }
            for index in range(1, len(sequence))
        ]

    def test_transition_is_one_exact_reversible_period_four_cycle(self):
        transition = period4.transition_map()
        self.assertEqual(set(transition), {"A", "B", "C", "D"})
        self.assertEqual(set(transition.values()), set(transition))
        self.assertTrue(all(source != target for source, target in transition.items()))
        for start in transition:
            value = start
            seen = []
            for _unused in range(4):
                seen.append(value)
                value = transition[value]
            self.assertEqual(value, start)
            self.assertEqual(len(set(seen)), 4)
        self.assertEqual(
            period4.EXPECTED_STATE_SEQUENCE,
            ("C", "D", "A", "B", "C", "D", "A", "B", "C", "D", "A", "B", "C", "D", "A", "B", "C"),
        )

    def test_static_suffix_and_generated_token_hashes_are_self_consistent(self):
        period4.validate_static_binding()
        self.assertEqual(
            len(period4.EXPECTED_SUFFIX_TOKEN_IDS),
            fixed_size.EXPECTED_SUCCESSOR_FRESH_TOKENS,
        )
        self.assertEqual(
            len(period4.BASE_BRANCH_TOKEN_IDS),
            fixed_size.EXPECTED_COMPLETE_BRANCH_TOKENS,
        )
        self.assertEqual(
            len(set(dict(period4.EXPECTED_GENERATED_SHA256).values())),
            4,
        )
        self.assertEqual(len(set(dict(period4.EXPECTED_CHILD_SHA256).values())), 4)
        self.assertEqual(len(set(dict(period4.EXPECTED_REQUEST_SHA256).values())), 4)

    def test_recurrence_evidence_requires_all_three_period_four_hash_laws(self):
        evidence = fixed_size.recurrence_evidence(
            period4.CONTRACT,
            period4.EXPECTED_STATE_SEQUENCE,
            self.steps(),
        )
        self.assertTrue(evidence["recurrence_hash_invariant"])
        self.assertTrue(evidence["transition_bijective"])
        self.assertTrue(evidence["transition_cycle_identity"])
        self.assertTrue(evidence["transition_no_early_collision"])
        self.assertTrue(evidence["generated_hash_period_exact"])
        self.assertTrue(evidence["child_hash_period_exact"])
        self.assertTrue(evidence["request_hash_period_exact"])

        mutated = self.steps()
        mutated[7] = {**mutated[7], "child_token_sha256": "0" * 64}
        rejected = fixed_size.recurrence_evidence(
            period4.CONTRACT,
            period4.EXPECTED_STATE_SEQUENCE,
            mutated,
        )
        self.assertFalse(rejected["child_hash_period_exact"])
        self.assertFalse(rejected["recurrence_hash_invariant"])

    def test_classifier_enforces_both_relative_and_absolute_speed_gates(self):
        accepted = period4.CONTRACT.accepted_classification
        self.assertEqual(
            fixed_size.classify(
                integrity=True,
                fixed_size=True,
                saved_work_law=True,
                speedup=period4.MINIMUM_FULLY_COUNTED_WALL_SPEEDUP,
                catalytic_wall_seconds=period4.MAXIMUM_CATALYTIC_WALL_SECONDS,
                recursive_depth=16,
                contract=period4.CONTRACT,
            ),
            accepted,
        )
        self.assertNotEqual(
            fixed_size.classify(
                integrity=True,
                fixed_size=True,
                saved_work_law=True,
                speedup=period4.MINIMUM_FULLY_COUNTED_WALL_SPEEDUP - 0.001,
                catalytic_wall_seconds=period4.MAXIMUM_CATALYTIC_WALL_SECONDS,
                recursive_depth=16,
                contract=period4.CONTRACT,
            ),
            accepted,
        )
        self.assertNotEqual(
            fixed_size.classify(
                integrity=True,
                fixed_size=True,
                saved_work_law=True,
                speedup=period4.MINIMUM_FULLY_COUNTED_WALL_SPEEDUP,
                catalytic_wall_seconds=period4.MAXIMUM_CATALYTIC_WALL_SECONDS + 0.001,
                recursive_depth=16,
                contract=period4.CONTRACT,
            ),
            accepted,
        )

    def test_cleanup_finalization_preserves_0077_identity(self):
        result = {
            "verdict": "accept",
            "quality_gates": {},
            "metrics": {"residency": {}},
        }
        cleanup = {
            "stable_after": {"healthy": True},
            "port_free": True,
        }
        with (
            mock.patch.object(
                fixed_size.harness.live_runtime,
                "cleanup_integrity",
                return_value={"passed": True},
            ),
            mock.patch.object(
                fixed_size.latency,
                "cleanup_peak_wddm_bytes",
                return_value=1,
            ),
        ):
            finalized = fixed_size.finalize_after_cleanup(
                result,
                cleanup=cleanup,
                cleanup_wall_seconds=0.1,
                stable_pids={3860},
                recursive_depth=16,
                contract=period4.CONTRACT,
            )
        self.assertEqual(finalized["classification"], period4.CONTRACT.accepted_classification)
        self.assertEqual(finalized["next_boundary"], period4.CONTRACT.next_boundary)
        self.assertTrue(
            finalized["quality_gates"]["reversible_period4_fixed_size_recurrence_supported"]
        )


if __name__ == "__main__":
    unittest.main()
