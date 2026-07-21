#!/usr/bin/env python3
from __future__ import annotations

import unittest
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalytic_frontier_fanout as fanout
import catalytic_frontier_harness as harness


class CatalyticFrontierFanoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        repository = Path(__file__).resolve().parents[1]
        corpus = harness.carrier.load_public_corpus(repository)
        cls.roots = {str(item["root_id"]): item for item in corpus["roots"]}

    def test_two_panels_have_eight_distinct_well_formed_projections(self) -> None:
        for root_id in fanout.EXTRA_PANELS:
            panel = fanout.panel_for(self.roots[root_id])
            self.assertEqual(len(panel), 8)
            self.assertEqual(len({item["question"] for item in panel}), 8)
            for item in panel:
                self.assertEqual(tuple(item["choices"]), ("A", "B", "C", "D"))
                self.assertIn(item["answer"], item["choices"])

    def test_branch_prompt_does_not_emit_the_scoring_field(self) -> None:
        spec = fanout.panel_for(self.roots["mb-runtime-datacenter-01"])[2]
        prompt = fanout.branch_user_content(spec)
        self.assertIn("TASK B", prompt)
        self.assertNotIn(f'"expected":"{spec["answer"]}"', prompt)
        self.assertNotIn(f'"correct":"{spec["answer"]}"', prompt)

    def test_seed_is_stable_and_role_distinct(self) -> None:
        first = fanout.derive_seed("mb-runtime-datacenter-01", "branch-3")
        self.assertEqual(first, fanout.derive_seed("mb-runtime-datacenter-01", "branch-3"))
        self.assertNotEqual(first, fanout.derive_seed("mb-runtime-datacenter-01", "branch-4"))

    def test_prefix_accounting_counts_carrier_and_recurrent_closures(self) -> None:
        task_a = {"fresh_model_tokens": 100}
        catalytic = {number: {"fresh_model_tokens": 20} for number in range(1, 9)}
        direct = {number: {"fresh_model_tokens": 100} for number in range(1, 9)}
        closures = {2: {"fresh_model_tokens": 5}, 4: {"fresh_model_tokens": 5}, 8: {"fresh_model_tokens": 5}}
        metrics = fanout.prefix_metrics(
            task_a=task_a,
            catalytic=catalytic,
            direct=direct,
            closures=closures,
            branch_order=list(range(1, 9)),
            milestones=(2, 4, 8),
        )
        self.assertEqual(metrics["2"]["catalytic_total"], 145)
        self.assertEqual(metrics["4"]["catalytic_total"], 190)
        self.assertEqual(metrics["8"]["catalytic_total"], 275)
        self.assertEqual(metrics["8"]["closure_compute"], 15)
        self.assertTrue(metrics["4"]["average_decreased"])
        self.assertTrue(metrics["8"]["average_decreased"])
        self.assertGreater(metrics["8"]["compute_amplification"], metrics["4"]["compute_amplification"])

    def test_minimal_closure_accepts_exactly_one_hashed_token(self) -> None:
        generated = [4754]
        digest = harness.carrier.sha256_bytes(harness.carrier.canonical_json_bytes(generated))
        execution = {
            "http_status": 200,
            "terminal_stop_evidence": {"observed": True, "stop": True},
            "finish_reason": "limit",
            "completion_tokens": 1,
            "generated_token_count": 1,
            "generated_token_ids": generated,
            "generated_token_sha256": digest,
            "completion_token_count_match": True,
        }
        terminal = harness.validate_minimal_closure_terminal(execution)
        self.assertEqual(terminal["operation_kind"], "minimal-output-root-readdress")
        self.assertEqual(terminal["completion_tokens"], 1)

        invalid = dict(execution, completion_tokens=2)
        with self.assertRaises(harness.FrontierHarnessError):
            harness.validate_minimal_closure_terminal(invalid)

    def test_discovery_loader_does_not_verify_one_shot_governance_lock(self) -> None:
        with mock.patch.object(
            harness.live_runtime,
            "verify_lock",
            side_effect=AssertionError("one-shot governance lock was consulted"),
        ):
            evaluator, contract = harness.load_discovery_sidecar_contract()
        self.assertEqual(evaluator["model"]["sha256"], harness.live_runtime.EXPECTED_MODEL_SHA256)
        self.assertEqual(contract["binary_identity"]["sha256"], harness.live_runtime.EXPECTED_BINARY_SHA256)


if __name__ == "__main__":
    unittest.main()
