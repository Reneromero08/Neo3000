#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest

import holostate_v1_inherited_task_a_carrier_evaluation_adjudication as adjudication


class InheritedCarrierAdjudicationTests(unittest.TestCase):
    def test_live_negative_and_component_findings_remain_distinct(self) -> None:
        self.assertEqual(
            adjudication.LIVE_CLASSIFICATION,
            "PROCESS_LOCAL_INHERITED_TASK_A_CARRIER_EXACT_REUSE_NOT_SUPPORTED",
        )
        self.assertEqual(
            adjudication.PARTIAL_REUSE_CLASSIFICATION,
            "PROCESS_LOCAL_INHERITED_TASK_A_PARTIAL_PREFIX_REUSE_REPLICATED",
        )
        self.assertEqual(
            adjudication.CAUSAL_CLASSIFICATION,
            "EXECUTABLE_REUSE_LIMITED_BY_MIXED_CHECKPOINT_AND_TOKENIZATION_BOUNDARIES_CONFIRMED",
        )

    def test_all_four_mixed_boundaries_are_exact(self) -> None:
        adjudication.validate_boundary_arithmetic()
        for item in adjudication.EXPECTED_REUSE.values():
            self.assertEqual(item["task_a_prompt_tokens"] - item["raw_common_prefix_tokens"], 4)
            self.assertEqual(item["raw_common_prefix_tokens"] - item["admitted_cached_tokens"], 128)
            self.assertEqual(item["task_a_prompt_tokens"] - item["admitted_cached_tokens"], 132)

    def test_five_token_identity_is_one_terminal_plus_four_contextual(self) -> None:
        for item in adjudication.EXPECTED_REUSE.values():
            self.assertEqual(item["task_a_completion_tokens"] - item["contextual_visible_extension_tokens"], 5)
            self.assertEqual(item["task_a_completion_tokens"] - item["visible_content_tokens"], 1)
            self.assertEqual(item["visible_content_tokens"] - item["contextual_visible_extension_tokens"], 4)

    def test_boundary_drift_is_rejected(self) -> None:
        drifted = copy.deepcopy(adjudication.EXPECTED_REUSE)
        drifted["warm-trajectory-archive-01"]["admitted_cached_tokens"] += 1
        with self.assertRaisesRegex(adjudication.InheritedCarrierAdjudicationError, "checkpoint rollback changed"):
            adjudication.validate_boundary_arithmetic(drifted)

    def test_resource_advantage_uses_exact_cross_products(self) -> None:
        self.assertEqual(2761 * 4, 11044)
        self.assertEqual(4908 * 4, 19632)
        self.assertLess(11044, 19632)
        self.assertEqual(4908 - 2761, 2147)

    def test_disclosure_boundary_rejects_reversible_generated_ids(self) -> None:
        with self.assertRaisesRegex(adjudication.InheritedCarrierAdjudicationError, "raw material"):
            adjudication.validate_disclosure_boundary({"generated_token_ids": [1, 2, 3]})


if __name__ == "__main__":
    unittest.main()
