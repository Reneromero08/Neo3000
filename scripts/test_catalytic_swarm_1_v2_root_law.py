#!/usr/bin/env python3
from __future__ import annotations

import unittest

from catalytic_swarm_1_v2_root_law import (
    RootCacheLawError,
    RootCacheObservation,
    adjudicate_root_cache,
)


def observation(**changes):
    values = dict(
        public_root_terminal_token_index=4820,
        common_prefix_tokens=4825,
        legacy_required_cached_prompt_tokens=4825,
        actual_cached_prompt_tokens=4822,
        branch_prompt_tokens=4848,
        fresh_prompt_tokens=26,
        completion_tokens=9,
        response_completed=True,
        transport_passed=True,
        token_evidence_passed=True,
    )
    values.update(changes)
    return RootCacheObservation(**values)


class RootCacheLawTests(unittest.TestCase):
    def test_diagnostic_minimal_branch_is_admitted(self):
        result = adjudicate_root_cache(observation())
        self.assertTrue(result.admitted)
        self.assertEqual(
            result.classification,
            "admit-root-covered-legacy-threshold-overextended",
        )
        self.assertEqual(result.root_margin_tokens, 2)
        self.assertEqual(result.legacy_threshold_delta_tokens, -3)
        self.assertEqual(result.legacy_threshold_overreach_tokens, 5)

    def test_diagnostic_realistic_branch_is_admitted(self):
        result = adjudicate_root_cache(
            observation(branch_prompt_tokens=5020, fresh_prompt_tokens=198)
        )
        self.assertTrue(result.admitted)
        self.assertEqual(result.root_margin_tokens, 2)

    def test_exact_legacy_threshold_also_admits(self):
        result = adjudicate_root_cache(
            observation(actual_cached_prompt_tokens=4825, fresh_prompt_tokens=23)
        )
        self.assertTrue(result.admitted)
        self.assertEqual(result.classification, "admit-exact-public-root-covered")

    def test_cache_shortfall_rejects(self):
        result = adjudicate_root_cache(
            observation(actual_cached_prompt_tokens=4819, fresh_prompt_tokens=29)
        )
        self.assertFalse(result.admitted)
        self.assertEqual(result.classification, "reject-public-root-cache-shortfall")

    def test_prefix_divergence_rejects_before_cache_claim(self):
        result = adjudicate_root_cache(
            observation(
                common_prefix_tokens=4810,
                legacy_required_cached_prompt_tokens=4810,
                actual_cached_prompt_tokens=4800,
                fresh_prompt_tokens=48,
            )
        )
        self.assertFalse(result.admitted)
        self.assertEqual(
            result.classification,
            "reject-prompt-prefix-diverged-before-root-end",
        )

    def test_incomplete_response_is_instrumentation_reject(self):
        result = adjudicate_root_cache(observation(response_completed=False))
        self.assertFalse(result.admitted)
        self.assertTrue(result.classification.startswith("instrumentation-reject"))

    def test_transport_failure_is_instrumentation_reject(self):
        result = adjudicate_root_cache(observation(transport_passed=False))
        self.assertFalse(result.admitted)
        self.assertTrue(result.classification.startswith("instrumentation-reject"))

    def test_fresh_prompt_accounting_is_exact(self):
        with self.assertRaises(RootCacheLawError):
            adjudicate_root_cache(observation(fresh_prompt_tokens=25))

    def test_legacy_threshold_cannot_exceed_common_prefix(self):
        with self.assertRaises(RootCacheLawError):
            adjudicate_root_cache(
                observation(
                    common_prefix_tokens=4824,
                    legacy_required_cached_prompt_tokens=4825,
                )
            )


if __name__ == "__main__":
    unittest.main()
