#!/usr/bin/env python3
from __future__ import annotations

import unittest

from catalytic_swarm_1_cache_diagnostic import (
    CacheDiagnosticError,
    CacheProbeObservation,
    classify_diagnostic,
    classify_probe,
)


def obs(label: str, seq: int, **changes):
    values = dict(
        label=label,
        request_sequence_index=seq,
        warm_prompt_tokens=4846,
        branch_prompt_tokens=4864,
        public_root_terminal_token_index=4800,
        common_prefix_tokens=4820,
        required_cached_prompt_tokens=4820,
        actual_cached_prompt_tokens=4810,
        fresh_prompt_tokens=54,
        completion_tokens=4,
        cache_checkpoint_min_step=512,
        response_completed=True,
        transport_passed=True,
        token_evidence_passed=True,
    )
    values.update(changes)
    return CacheProbeObservation(**values)


class CacheProbeTests(unittest.TestCase):
    def test_exact_root_reuse(self):
        item = classify_probe(obs("minimal-branch", 2))
        self.assertEqual(item.classification, "proof-threshold-overextended")
        self.assertTrue(item.root_reuse_proven)

    def test_exact_threshold(self):
        item = classify_probe(obs(
            "minimal-branch", 2,
            actual_cached_prompt_tokens=4820,
            fresh_prompt_tokens=44,
        ))
        self.assertEqual(item.classification, "exact-root-reuse-proven")

    def test_checkpoint_shortfall(self):
        item = classify_probe(obs(
            "minimal-branch", 2,
            actual_cached_prompt_tokens=4700,
            fresh_prompt_tokens=164,
        ))
        self.assertEqual(item.classification, "checkpoint-shortfall")
        self.assertEqual(item.shortfall_tokens, 100)

    def test_zero_cache(self):
        item = classify_probe(obs(
            "minimal-branch", 2,
            actual_cached_prompt_tokens=0,
            fresh_prompt_tokens=4864,
        ))
        self.assertEqual(item.classification, "cache-session-reuse-failed")

    def test_prompt_divergence_precedes_cache_class(self):
        item = classify_probe(obs(
            "minimal-branch", 2,
            common_prefix_tokens=4700,
            required_cached_prompt_tokens=4700,
            actual_cached_prompt_tokens=4600,
            fresh_prompt_tokens=264,
        ))
        self.assertEqual(item.classification, "prompt-prefix-diverged-before-root-end")

    def test_invalid_accounting(self):
        with self.assertRaises(CacheDiagnosticError):
            classify_probe(obs("minimal-branch", 2, fresh_prompt_tokens=1))


class DiagnosticTests(unittest.TestCase):
    def test_two_exact_probes_accept(self):
        result = classify_diagnostic([
            obs("minimal-branch", 2, actual_cached_prompt_tokens=4820, fresh_prompt_tokens=44),
            obs("realistic-first-turn", 3, actual_cached_prompt_tokens=4820, fresh_prompt_tokens=44),
        ])
        self.assertEqual(result.verdict, "reviewable-accept")
        self.assertEqual(result.cache_admission, "exact-root-reuse-proven")

    def test_proof_overreach_accepts_diagnostic_only(self):
        result = classify_diagnostic([
            obs("minimal-branch", 2),
            obs("realistic-first-turn", 3),
        ])
        self.assertEqual(
            result.cache_admission,
            "root-reuse-proven-proof-law-repair-required",
        )

    def test_stable_checkpoint_shortfall(self):
        result = classify_diagnostic([
            obs("minimal-branch", 2, actual_cached_prompt_tokens=4700, fresh_prompt_tokens=164),
            obs("realistic-first-turn", 3, actual_cached_prompt_tokens=4700, fresh_prompt_tokens=164),
        ])
        self.assertEqual(result.verdict, "reviewable-accept")
        self.assertEqual(result.cache_admission, "stable-checkpoint-shortfall")

    def test_zero_cache_rejects(self):
        result = classify_diagnostic([
            obs("minimal-branch", 2, actual_cached_prompt_tokens=0, fresh_prompt_tokens=4864),
            obs("realistic-first-turn", 3, actual_cached_prompt_tokens=0, fresh_prompt_tokens=4864),
        ])
        self.assertEqual(result.verdict, "reject")

    def test_mixed_classes_are_inconclusive(self):
        result = classify_diagnostic([
            obs("minimal-branch", 2, actual_cached_prompt_tokens=4820, fresh_prompt_tokens=44),
            obs("realistic-first-turn", 3, actual_cached_prompt_tokens=4700, fresh_prompt_tokens=164),
        ])
        self.assertEqual(result.verdict, "inconclusive")
        self.assertEqual(result.cache_admission, "unstable-or-geometry-dependent-reuse")

    def test_probe_order_is_frozen(self):
        with self.assertRaises(CacheDiagnosticError):
            classify_diagnostic([
                obs("realistic-first-turn", 3),
                obs("minimal-branch", 2),
            ])


if __name__ == "__main__":
    unittest.main()
