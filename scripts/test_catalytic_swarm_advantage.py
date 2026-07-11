#!/usr/bin/env python3
"""CPU-only tests for CatalyticSwarm-1 equal-budget task advantage."""

from __future__ import annotations

import dataclasses
import json
import unittest
from pathlib import Path
from typing import Any

from catalytic_advantage_tasks import (
    AdvantageTaskError,
    candidate_is_exact,
    build_frozen_task_suite,
    render_public_task,
    score_candidate,
    validate_public_projection,
)
from catalytic_swarm_advantage import (
    ARMS,
    AdvantageControlError,
    ArmOutcome,
    BUDGET_RATIO_LIMIT,
    MAX_COMPLETION_TOKENS_PER_ARM,
    MAX_TOKENS_PER_REQUEST,
    REQUESTS_PER_ARM,
    TaskComparison,
    TurnObservation,
    build_advantage_arm_plan,
    build_all_arm_plans,
    classify_suite_advantage,
    compare_task_outcomes,
    parse_candidate_content,
    render_turn_assignment,
    run_advantage_arm,
    select_final_candidate,
)

ROOT = Path(__file__).resolve().parent


class TaskSuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.suite = build_frozen_task_suite()

    def test_suite_is_frozen_and_unique(self) -> None:
        self.assertEqual(len(self.suite.tasks), 8)
        self.assertEqual(len(self.suite.suite_sha256), 64)
        self.assertEqual(
            [task.task_id for task in self.suite.tasks],
            [f"cs1-task-{index:02d}" for index in range(1, 9)],
        )
        for task in self.suite.tasks:
            public_exact = [
                candidate.candidate_id
                for candidate in task.candidates
                if candidate_is_exact(task, candidate.candidate_id, hidden=False)
            ]
            self.assertEqual(public_exact, [task.answer_candidate_id])
            self.assertTrue(
                candidate_is_exact(
                    task, task.answer_candidate_id, hidden=True
                )
            )

    def test_public_prompt_excludes_hidden_fields(self) -> None:
        task = self.suite.tasks[0]
        rendered = render_public_task(task)
        validate_public_projection(task, rendered)
        self.assertNotIn("hidden_examples", rendered)
        self.assertNotIn("answer_candidate_id", rendered)
        payload = json.loads(rendered)
        self.assertEqual(payload["task_id"], task.task_id)
        self.assertEqual(len(payload["candidates"]), 64)

    def test_hidden_score_is_external_only(self) -> None:
        task = self.suite.tasks[0]
        public = score_candidate(
            task, task.answer_candidate_id, hidden=False
        )
        hidden = score_candidate(
            task, task.answer_candidate_id, hidden=True
        )
        self.assertEqual(public, (5, 5))
        self.assertEqual(hidden, (16, 16))

    def test_suite_hash_is_exact(self) -> None:
        self.assertEqual(
            self.suite.suite_sha256,
            "4B9961D5054BE5D98EF315D2DEAE9D1604E0042A69CB02A8B81FDF513BC1FC92",
        )


class ArmPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.suite = build_frozen_task_suite()
        cls.task = cls.suite.tasks[0]

    def test_all_arms_share_exact_budget_role_and_seed_sequence(self) -> None:
        plans = build_all_arm_plans()
        self.assertEqual(tuple(plan.arm for plan in plans), ARMS)
        role_seed = {
            tuple((turn.role, turn.seed) for turn in plan.turns)
            for plan in plans
        }
        self.assertEqual(len(role_seed), 1)
        for plan in plans:
            self.assertEqual(plan.request_count, REQUESTS_PER_ARM)
            self.assertEqual(len(plan.turns), REQUESTS_PER_ARM)
            self.assertEqual(plan.physical_slots, 1)
            self.assertEqual(
                plan.max_completion_tokens,
                MAX_COMPLETION_TOKENS_PER_ARM,
            )
            self.assertFalse(plan.hidden_feedback_visible)
            self.assertFalse(plan.automatic_promotion)
            self.assertTrue(
                all(
                    turn.max_tokens == MAX_TOKENS_PER_REQUEST
                    for turn in plan.turns
                )
            )

    def test_topologies_are_distinct_and_locked(self) -> None:
        chain = build_advantage_arm_plan("serial-chain")
        best_of_n = build_advantage_arm_plan("best-of-n")
        sparse = build_advantage_arm_plan("sparse-swarm")
        verified = build_advantage_arm_plan("verified-swarm")
        self.assertEqual(chain.turns[0].parent_turn_ids, ())
        self.assertEqual(
            chain.turns[1].parent_turn_ids,
            (chain.turns[0].turn_id,),
        )
        self.assertTrue(
            all(not turn.parent_turn_ids for turn in best_of_n.turns)
        )

        def parent_ordinals(plan):
            ordinal_by_id = {turn.turn_id: turn.ordinal for turn in plan.turns}
            return [
                tuple(ordinal_by_id[parent] for parent in turn.parent_turn_ids)
                for turn in plan.turns
            ]

        self.assertEqual(parent_ordinals(sparse), parent_ordinals(verified))
        self.assertTrue(
            all(not turn.verifier_feedback_visible for turn in sparse.turns)
        )
        self.assertTrue(
            all(turn.verifier_feedback_visible for turn in verified.turns)
        )
        self.assertEqual(
            sum(turn.phase == "proposal" for turn in sparse.turns), 16
        )
        self.assertEqual(
            sum(turn.phase == "evidence" for turn in sparse.turns), 8
        )
        self.assertEqual(
            sum(turn.phase == "critique" for turn in sparse.turns), 6
        )
        self.assertEqual(
            sum(turn.phase == "synthesis" for turn in sparse.turns), 2
        )

    def observation(
        self,
        turn,
        candidate_id: str = "C00",
        public_passed: int = 3,
    ) -> TurnObservation:
        return TurnObservation(
            turn_id=turn.turn_id,
            ordinal=turn.ordinal,
            arm=turn.arm,
            phase=turn.phase,
            role=turn.role,
            parent_turn_ids=turn.parent_turn_ids,
            candidate_id=candidate_id,
            public_passed=public_passed,
            public_total=5,
            content_sha256="A" * 64,
            prompt_tokens=100,
            cached_prompt_tokens=80,
            fresh_prompt_tokens=20,
            completion_tokens=8,
            finish_reason="stop",
            token_evidence_scope="exact-visible-content-tokenization-plus-one-terminal-eos-token",
        )

    def test_assignment_uses_six_fixed_slots_and_no_hidden_data(self) -> None:
        verified = build_advantage_arm_plan("verified-swarm")
        turn = verified.turns[16]
        parents = tuple(
            self.observation(
                next(item for item in verified.turns if item.turn_id == parent)
            )
            for parent in turn.parent_turn_ids
        )
        rendered = render_turn_assignment(self.task, turn, parents)
        payload = json.loads(rendered)
        self.assertEqual(len(payload["parent_slots"]), 6)
        self.assertEqual(
            [slot["public_score"] for slot in payload["parent_slots"][:2]],
            ["03", "03"],
        )
        self.assertNotIn("hidden_examples", rendered)
        self.assertNotIn("answer_candidate_id", rendered)

        sparse = build_advantage_arm_plan("sparse-swarm")
        sparse_turn = sparse.turns[16]
        sparse_parents = tuple(
            self.observation(
                next(item for item in sparse.turns if item.turn_id == parent)
            )
            for parent in sparse_turn.parent_turn_ids
        )
        sparse_rendered = render_turn_assignment(
            self.task, sparse_turn, sparse_parents
        )
        sparse_payload = json.loads(sparse_rendered)
        self.assertEqual(
            [slot["public_score"] for slot in sparse_payload["parent_slots"][:2]],
            ["--", "--"],
        )

    def test_best_of_n_uses_public_verifier_score_with_earliest_tie_break(self) -> None:
        plan = build_advantage_arm_plan("best-of-n")
        observations = [
            self.observation(
                plan.turns[index],
                candidate_id=f"C{index:02d}",
                public_passed=score,
            )
            for index, score in enumerate([1, 5, 5] + [0] * 29)
        ]
        self.assertEqual(select_final_candidate(plan, observations), "C01")

    def test_wrong_parent_context_is_rejected(self) -> None:
        chain = build_advantage_arm_plan("serial-chain")
        turn = chain.turns[1]
        with self.assertRaises(AdvantageControlError):
            render_turn_assignment(self.task, turn, ())

    def test_response_parser_is_exact(self) -> None:
        self.assertEqual(
            parse_candidate_content('{"candidate_id":"C00"}', self.task),
            "C00",
        )
        with self.assertRaises(AdvantageControlError):
            parse_candidate_content(
                '{"candidate_id":"C00","extra":1}', self.task
            )
        with self.assertRaises(AdvantageControlError):
            parse_candidate_content('{"candidate_id": "C00"}', self.task)
        with self.assertRaises(AdvantageTaskError):
            parse_candidate_content('{"candidate_id":"C99"}', self.task)


class RunnerAndComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.suite = build_frozen_task_suite()

    def fake_runner(self, answer_id: str):
        def run(turn, public_root: str, assignment: str) -> dict[str, Any]:
            self.assertNotIn("hidden_examples", public_root)
            self.assertNotIn("answer_candidate_id", public_root)
            self.assertNotIn("hidden_examples", assignment)
            return {
                "content": json.dumps(
                    {"candidate_id": answer_id},
                    separators=(",", ":"),
                ),
                "prompt_tokens": 100,
                "cached_prompt_tokens": 80,
                "fresh_prompt_tokens": 20,
                "completion_tokens": 8,
                "finish_reason": "stop",
                "reasoning_content": "",
                "tool_calls": [],
                "transport_passed": True,
                "token_evidence_scope": "exact-visible-content-tokenization-plus-one-terminal-eos-token",
            }
        return run

    def test_runner_completes_32_turns_under_budget(self) -> None:
        task = self.suite.tasks[0]
        plan = build_advantage_arm_plan("verified-swarm")
        outcome = run_advantage_arm(
            plan,
            task,
            worker_runner=self.fake_runner(task.answer_candidate_id),
        )
        self.assertEqual(outcome.verdict, "complete")
        self.assertEqual(outcome.request_count, 32)
        self.assertEqual(len(outcome.observations), 32)
        self.assertTrue(outcome.exact_hidden_success)
        self.assertEqual(outcome.total_fresh_prompt_tokens, 640)
        self.assertEqual(outcome.total_completion_tokens, 256)
        self.assertFalse(outcome.automatic_promotion)

    def test_runner_fails_closed_on_reasoning_or_budget(self) -> None:
        task = self.suite.tasks[0]
        plan = build_advantage_arm_plan("serial-chain")

        def bad_runner(turn, public_root, assignment):
            result = self.fake_runner(task.answer_candidate_id)(
                turn, public_root, assignment
            )
            result["reasoning_content"] = "hidden"
            return result

        outcome = run_advantage_arm(plan, task, worker_runner=bad_runner)
        self.assertEqual(outcome.verdict, "inconclusive")
        self.assertEqual(outcome.request_count, 0)

        def over_budget(turn, public_root, assignment):
            result = self.fake_runner(task.answer_candidate_id)(
                turn, public_root, assignment
            )
            result["completion_tokens"] = 33
            return result

        outcome = run_advantage_arm(plan, task, worker_runner=over_budget)
        self.assertEqual(outcome.verdict, "inconclusive")
        self.assertEqual(outcome.request_count, 0)

    def complete_outcome(
        self,
        task,
        arm: str,
        *,
        success: bool,
        hidden_passed: int | None = None,
        fresh: int = 640,
        completion: int = 256,
    ) -> ArmOutcome:
        answer = task.answer_candidate_id
        wrong = next(
            item.candidate_id
            for item in task.candidates
            if item.candidate_id != answer
        )
        candidate = answer if success else wrong
        if hidden_passed is None:
            hidden_passed = 16 if success else 0
        return ArmOutcome(
            task_id=task.task_id,
            arm=arm,
            plan_sha256="A" * 64,
            public_root_sha256="B" * 64,
            observations=(),
            final_candidate_id=candidate,
            final_public_passed=5 if success else 0,
            final_public_total=5,
            final_hidden_passed=hidden_passed,
            final_hidden_total=16,
            exact_hidden_success=success,
            request_count=32,
            total_prompt_tokens=3200,
            total_cached_prompt_tokens=2560,
            total_fresh_prompt_tokens=fresh,
            total_completion_tokens=completion,
            total_model_tokens=fresh + completion,
            completion_budget_ceiling=1024,
            fresh_prompt_budget_ceiling=8192,
            automatic_promotion=False,
            verdict="complete",
            reasons=(),
        )

    def test_budget_parity_accepts_equal_and_rejects_skew(self) -> None:
        task = self.suite.tasks[0]
        equal = [
            self.complete_outcome(task, arm, success=True)
            for arm in ARMS
        ]
        comparison = compare_task_outcomes(task, equal)
        self.assertTrue(comparison.budget_parity_passed)
        self.assertEqual(comparison.total_model_token_ratio, 1.0)

        skewed = list(equal)
        skewed[-1] = dataclasses.replace(
            skewed[-1],
            total_fresh_prompt_tokens=800,
            total_model_tokens=1056,
        )
        comparison = compare_task_outcomes(task, skewed)
        self.assertFalse(comparison.budget_parity_passed)
        self.assertGreater(comparison.fresh_prompt_ratio, BUDGET_RATIO_LIMIT)

    def make_comparisons(self, verified_successes: int, baseline_successes: int):
        comparisons = []
        for index, task in enumerate(self.suite.tasks):
            outcomes = []
            for arm in ARMS:
                success = (
                    index < verified_successes
                    if arm == "verified-swarm"
                    else index < baseline_successes
                )
                outcomes.append(
                    self.complete_outcome(
                        task,
                        arm,
                        success=success,
                        hidden_passed=16 if success else 2,
                    )
                )
            comparisons.append(compare_task_outcomes(task, outcomes))
        return comparisons

    def test_suite_advantage_requires_locked_margin(self) -> None:
        accepted = classify_suite_advantage(
            self.make_comparisons(verified_successes=7, baseline_successes=4)
        )
        self.assertEqual(accepted.verdict, "reviewable-accept")
        self.assertEqual(
            accepted.task_advantage, "reviewable-accept"
        )
        self.assertFalse(accepted.automatic_promotion)

        no_advantage = classify_suite_advantage(
            self.make_comparisons(verified_successes=6, baseline_successes=5)
        )
        self.assertEqual(no_advantage.verdict, "no-advantage")
        self.assertEqual(no_advantage.task_advantage, "LOCKED")

    def test_suite_is_inconclusive_on_budget_failure(self) -> None:
        comparisons = self.make_comparisons(7, 4)
        first = comparisons[0]
        comparisons[0] = dataclasses.replace(
            first,
            budget_parity_passed=False,
            budget_parity_reasons=("forced",),
        )
        result = classify_suite_advantage(comparisons)
        self.assertEqual(result.verdict, "inconclusive")
        self.assertEqual(result.task_advantage, "LOCKED")


class StaticSafetyTests(unittest.TestCase):
    def test_control_modules_have_no_network_or_subprocess_surface(self) -> None:
        for filename in (
            "catalytic_advantage_tasks.py",
            "catalytic_swarm_advantage.py",
        ):
            source = (ROOT / filename).read_text(encoding="utf-8")
            for forbidden in (
                "import subprocess",
                "import socket",
                "import urllib",
                "import requests",
                "os.system",
                "Popen(",
            ):
                self.assertNotIn(forbidden, source, filename)


if __name__ == "__main__":
    unittest.main()
