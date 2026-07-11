#!/usr/bin/env python3
"""CPU-only tests for CatalyticSwarm-1 equal-budget task advantage."""

from __future__ import annotations

import dataclasses
import json
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from catalytic_advantage_tasks import (
    AdvantageTaskError,
    candidate_is_exact,
    build_frozen_task_suite,
    render_public_task,
    score_candidate,
    validate_public_projection,
)
from catalytic_swarm_advantage import (
    ACCEPTED_V4_TOKEN_EVIDENCE_SCOPES,
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
    canonical_json_bytes,
    classify_suite_advantage,
    compare_task_outcomes,
    parse_candidate_content,
    render_turn_assignment,
    run_advantage_arm,
    select_final_candidate,
    sha256_bytes,
    validate_advantage_arm_plan,
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
        payload["hidden_examples"] = [{"input": 0, "output": 0}]
        with self.assertRaises(AdvantageTaskError):
            validate_public_projection(
                task,
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
            )

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

    def test_public_suite_serialization_excludes_all_protected_answers(self) -> None:
        self.assertEqual(
            self.suite.to_dict(),
            self.suite.to_dict(include_answers=False),
        )
        rendered = json.dumps(self.suite.to_dict(), sort_keys=True)
        self.assertNotIn("hidden_examples", rendered)
        self.assertNotIn("answer_candidate_id", rendered)
        protected = self.suite.to_dict(include_answers=True)
        self.assertIn("hidden_examples", protected["tasks"][0])
        self.assertIn("answer_candidate_id", protected["tasks"][0])

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

    def test_plan_validation_rejects_boolean_numeric_substitution(self) -> None:
        plan = build_advantage_arm_plan("serial-chain")
        with self.assertRaises(AdvantageControlError):
            validate_advantage_arm_plan(
                dataclasses.replace(plan, physical_slots=True)
            )
        forged_turns = list(plan.turns)
        forged_turns[0] = dataclasses.replace(forged_turns[0], ordinal=True)
        with self.assertRaises(AdvantageControlError):
            validate_advantage_arm_plan(
                dataclasses.replace(plan, turns=tuple(forged_turns))
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
        public_passed: int | None = None,
    ) -> TurnObservation:
        if public_passed is None:
            public_passed = score_candidate(
                self.task, candidate_id, hidden=False
            )[0]
        return TurnObservation(
            turn_id=turn.turn_id,
            ordinal=turn.ordinal,
            arm=turn.arm,
            task_id=self.task.task_id,
            public_root_sha256=sha256_bytes(
                render_public_task(self.task).encode("utf-8")
            ),
            phase=turn.phase,
            role=turn.role,
            parent_turn_ids=turn.parent_turn_ids,
            candidate_id=candidate_id,
            public_passed=public_passed,
            public_total=5,
            content_sha256="A" * 64,
            prompt_tokens=100,
            cached_prompt_tokens=80,
            required_cached_prompt_tokens=60,
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
            [f"{item.public_passed:02d}" for item in parents],
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

        for slot in payload["parent_slots"]:
            slot["public_score"] = "--"
        self.assertEqual(payload, sparse_payload)

    def test_parent_observations_are_task_root_and_score_bound(self) -> None:
        verified = build_advantage_arm_plan("verified-swarm")
        turn = verified.turns[16]
        parents = tuple(
            self.observation(
                next(item for item in verified.turns if item.turn_id == parent)
            )
            for parent in turn.parent_turn_ids
        )
        other_task = self.suite.tasks[1]
        with self.assertRaises(AdvantageControlError):
            render_turn_assignment(other_task, turn, parents)
        forged = (
            dataclasses.replace(
                parents[0], public_passed=parents[0].public_passed + 1
            ),
            *parents[1:],
        )
        with self.assertRaises(AdvantageControlError):
            render_turn_assignment(self.task, turn, forged)

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
                "required_cached_prompt_tokens": 60,
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
        self.assertIsNone(outcome.final_hidden_passed)
        self.assertIsNone(outcome.final_hidden_total)
        self.assertIsNone(outcome.exact_hidden_success)
        self.assertEqual(outcome.total_fresh_prompt_tokens, 640)
        self.assertEqual(outcome.total_completion_tokens, 256)
        self.assertFalse(outcome.automatic_promotion)

    def test_hidden_scoring_waits_for_all_four_complete_arms(self) -> None:
        task = self.suite.tasks[0]
        outcomes = [
            run_advantage_arm(
                build_advantage_arm_plan(arm),
                task,
                worker_runner=self.fake_runner(task.answer_candidate_id),
            )
            for arm in ARMS
        ]
        self.assertTrue(
            all(item.final_hidden_passed is None for item in outcomes)
        )
        self.assertTrue(
            all(item.exact_hidden_success is None for item in outcomes)
        )
        comparison = compare_task_outcomes(task, outcomes)
        self.assertTrue(
            all(item.exact_hidden_success is True for item in comparison.outcomes)
        )

    def test_comparison_does_not_hidden_score_an_incomplete_task(self) -> None:
        task = self.suite.tasks[0]
        outcomes = [
            self.complete_outcome(task, arm, success=True)
            for arm in ARMS
        ]
        incomplete = dataclasses.replace(
            outcomes[0],
            observations=outcomes[0].observations[:-1],
            request_count=31,
            total_prompt_tokens=3100,
            total_cached_prompt_tokens=2480,
            total_fresh_prompt_tokens=620,
            total_completion_tokens=248,
            total_model_tokens=868,
            verdict="inconclusive",
            reasons=("request failed",),
        )
        comparison = compare_task_outcomes(task, [incomplete, *outcomes[1:]])
        self.assertFalse(comparison.budget_parity_passed)
        for outcome in comparison.outcomes:
            self.assertIsNone(outcome.final_hidden_passed)
            self.assertIsNone(outcome.final_hidden_total)
            self.assertIsNone(outcome.exact_hidden_success)

    def test_runner_requires_observed_common_root_reuse(self) -> None:
        task = self.suite.tasks[0]
        plan = build_advantage_arm_plan("serial-chain")

        def no_root_reuse(turn, public_root, assignment):
            result = self.fake_runner(task.answer_candidate_id)(
                turn, public_root, assignment
            )
            result["cached_prompt_tokens"] = 0
            result["fresh_prompt_tokens"] = result["prompt_tokens"]
            return result

        outcome = run_advantage_arm(plan, task, worker_runner=no_root_reuse)
        self.assertEqual(outcome.verdict, "inconclusive")
        self.assertEqual(outcome.request_count, 0)

    def test_runner_requires_complete_common_root_reuse(self) -> None:
        task = self.suite.tasks[0]
        plan = build_advantage_arm_plan("serial-chain")

        def partial_root_reuse(turn, public_root, assignment):
            result = self.fake_runner(task.answer_candidate_id)(
                turn, public_root, assignment
            )
            result["required_cached_prompt_tokens"] = 81
            return result

        outcome = run_advantage_arm(
            plan, task, worker_runner=partial_root_reuse
        )
        self.assertEqual(outcome.verdict, "inconclusive")
        self.assertEqual(outcome.request_count, 0)

    def test_runner_requires_accepted_v4_token_evidence_scope(self) -> None:
        task = self.suite.tasks[0]
        plan = build_advantage_arm_plan("serial-chain")

        def false_token_evidence(turn, public_root, assignment):
            result = self.fake_runner(task.answer_candidate_id)(
                turn, public_root, assignment
            )
            result["token_evidence_scope"] = "self-asserted"
            return result

        outcome = run_advantage_arm(plan, task, worker_runner=false_token_evidence)
        self.assertEqual(outcome.verdict, "inconclusive")
        self.assertEqual(outcome.request_count, 0)

        for scope in ACCEPTED_V4_TOKEN_EVIDENCE_SCOPES:
            def accepted_token_evidence(turn, public_root, assignment, scope=scope):
                result = self.fake_runner(task.answer_candidate_id)(
                    turn, public_root, assignment
                )
                result["token_evidence_scope"] = scope
                return result

            outcome = run_advantage_arm(
                plan, task, worker_runner=accepted_token_evidence
            )
            self.assertEqual(outcome.verdict, "complete", scope)

    def test_runner_fails_closed_on_reasoning(self) -> None:
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

    def test_best_of_n_public_verifier_waits_for_all_responses(self) -> None:
        task = self.suite.tasks[0]
        plan = build_advantage_arm_plan("best-of-n")
        public_score_calls: list[str] = []
        original_score = score_candidate

        def observed_score(task_value, candidate_id, *, hidden):
            if hidden is False:
                public_score_calls.append(candidate_id)
            return original_score(task_value, candidate_id, hidden=hidden)

        def runner(turn, public_root, assignment):
            self.assertEqual(public_score_calls, [])
            return self.fake_runner(task.answer_candidate_id)(
                turn, public_root, assignment
            )

        with mock.patch(
            "catalytic_swarm_advantage.score_candidate",
            side_effect=observed_score,
        ):
            outcome = run_advantage_arm(plan, task, worker_runner=runner)
        self.assertEqual(outcome.verdict, "complete")
        self.assertGreaterEqual(len(public_score_calls), 32)

    def test_runner_fails_closed_on_completion_budget(self) -> None:
        task = self.suite.tasks[0]
        plan = build_advantage_arm_plan("serial-chain")

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
    ) -> ArmOutcome:
        answer = task.answer_candidate_id
        wrong = next(
            item.candidate_id
            for item in task.candidates
            if item.candidate_id != answer
        )
        candidate = answer if success else wrong
        plan = build_advantage_arm_plan(arm)
        root_hash = sha256_bytes(render_public_task(task).encode("utf-8"))
        public_passed, public_total = score_candidate(
            task, candidate, hidden=False
        )
        observations = tuple(
            TurnObservation(
                turn_id=turn.turn_id,
                ordinal=turn.ordinal,
                arm=arm,
                task_id=task.task_id,
                public_root_sha256=root_hash,
                phase=turn.phase,
                role=turn.role,
                parent_turn_ids=turn.parent_turn_ids,
                candidate_id=candidate,
                public_passed=public_passed,
                public_total=public_total,
                content_sha256=sha256_bytes(
                    canonical_json_bytes({"candidate_id": candidate})
                ),
                prompt_tokens=100,
                cached_prompt_tokens=80,
                required_cached_prompt_tokens=60,
                fresh_prompt_tokens=20,
                completion_tokens=8,
                finish_reason="stop",
                token_evidence_scope=(
                    "exact-visible-content-tokenization-plus-one-terminal-eos-token"
                ),
            )
            for turn in plan.turns
        )
        return ArmOutcome(
            task_id=task.task_id,
            arm=arm,
            plan_sha256=plan.plan_sha256,
            public_root_sha256=root_hash,
            observations=observations,
            final_candidate_id=candidate,
            final_public_passed=public_passed,
            final_public_total=public_total,
            final_hidden_passed=None,
            final_hidden_total=None,
            exact_hidden_success=None,
            request_count=32,
            total_prompt_tokens=3200,
            total_cached_prompt_tokens=2560,
            total_fresh_prompt_tokens=640,
            total_completion_tokens=256,
            total_model_tokens=896,
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
        skewed_observations = list(skewed[-1].observations)
        skewed_observations[-1] = dataclasses.replace(
            skewed_observations[-1],
            prompt_tokens=260,
            fresh_prompt_tokens=180,
        )
        skewed[-1] = dataclasses.replace(
            skewed[-1],
            observations=tuple(skewed_observations),
            total_prompt_tokens=3360,
            total_fresh_prompt_tokens=800,
            total_model_tokens=1056,
        )
        comparison = compare_task_outcomes(task, skewed)
        self.assertFalse(comparison.budget_parity_passed)
        self.assertGreater(comparison.fresh_prompt_ratio, BUDGET_RATIO_LIMIT)

    def test_comparison_rejects_forged_or_duplicate_outcomes(self) -> None:
        task = self.suite.tasks[0]
        outcomes = [
            self.complete_outcome(task, arm, success=True)
            for arm in ARMS
        ]
        with self.assertRaises(AdvantageControlError):
            compare_task_outcomes(
                task,
                [outcomes[0], outcomes[0], outcomes[2], outcomes[3]],
            )
        with self.assertRaises(AdvantageControlError):
            compare_task_outcomes(
                task,
                [dataclasses.replace(outcomes[0], task_id="wrong"), *outcomes[1:]],
            )
        with self.assertRaises(AdvantageControlError):
            compare_task_outcomes(
                task,
                [dataclasses.replace(outcomes[0], reasons=None), *outcomes[1:]],
            )
        with self.assertRaises(AdvantageControlError):
            compare_task_outcomes(
                task,
                [
                    dataclasses.replace(
                        outcomes[0], observations=list(outcomes[0].observations)
                    ),
                    *outcomes[1:],
                ],
            )
        with self.assertRaises(AdvantageControlError):
            compare_task_outcomes(
                task,
                [
                    dataclasses.replace(
                        outcomes[0],
                        final_hidden_passed=16,
                        final_hidden_total=16,
                        exact_hidden_success=True,
                    ),
                    *outcomes[1:],
                ],
            )
        with self.assertRaises(AdvantageControlError):
            compare_task_outcomes(
                task,
                [
                    dataclasses.replace(
                        outcomes[0],
                        total_fresh_prompt_tokens=641,
                        total_model_tokens=897,
                    ),
                    *outcomes[1:],
                ],
            )
        reordered = dataclasses.replace(
            outcomes[0],
            observations=tuple(reversed(outcomes[0].observations)),
        )
        with self.assertRaises(AdvantageControlError):
            compare_task_outcomes(task, [reordered, *outcomes[1:]])
        forged_final = dataclasses.replace(
            outcomes[0], final_candidate_id="C63"
        )
        with self.assertRaises(AdvantageControlError):
            compare_task_outcomes(task, [forged_final, *outcomes[1:]])

        over_fresh_observations = list(outcomes[0].observations)
        over_fresh_observations[-1] = dataclasses.replace(
            over_fresh_observations[-1],
            prompt_tokens=8280,
            cached_prompt_tokens=80,
            fresh_prompt_tokens=8200,
        )
        over_fresh = dataclasses.replace(
            outcomes[0],
            observations=tuple(over_fresh_observations),
            total_prompt_tokens=11380,
            total_fresh_prompt_tokens=8820,
            total_model_tokens=9076,
        )
        with self.assertRaises(AdvantageControlError):
            compare_task_outcomes(task, [over_fresh, *outcomes[1:]])

        negative_completion_observations = list(outcomes[0].observations)
        negative_completion_observations[-1] = dataclasses.replace(
            negative_completion_observations[-1],
            completion_tokens=-1,
        )
        negative_completion = dataclasses.replace(
            outcomes[0],
            observations=tuple(negative_completion_observations),
            total_completion_tokens=247,
            total_model_tokens=887,
        )
        with self.assertRaises(AdvantageControlError):
            compare_task_outcomes(
                task, [negative_completion, *outcomes[1:]]
            )

        forged_content_hash_observations = list(outcomes[0].observations)
        forged_content_hash_observations[-1] = dataclasses.replace(
            forged_content_hash_observations[-1],
            content_sha256="A" * 64,
        )
        forged_content_hash = dataclasses.replace(
            outcomes[0], observations=tuple(forged_content_hash_observations)
        )
        with self.assertRaises(AdvantageControlError):
            compare_task_outcomes(
                task, [forged_content_hash, *outcomes[1:]]
            )

        boolean_token_observations = list(outcomes[0].observations)
        boolean_token_observations[-1] = dataclasses.replace(
            boolean_token_observations[-1],
            prompt_tokens=2,
            cached_prompt_tokens=True,
            fresh_prompt_tokens=True,
            completion_tokens=True,
        )
        boolean_tokens = dataclasses.replace(
            outcomes[0],
            observations=tuple(boolean_token_observations),
            total_prompt_tokens=3102,
            total_cached_prompt_tokens=2481,
            total_fresh_prompt_tokens=621,
            total_completion_tokens=249,
            total_model_tokens=870,
        )
        with self.assertRaises(AdvantageControlError):
            compare_task_outcomes(task, [boolean_tokens, *outcomes[1:]])

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
        self.assertIn(
            "CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN",
            accepted.to_dict(),
        )
        self.assertNotIn("CATALYTIC_SWARM_TASK_ADVANTAGE", accepted.to_dict())
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

    def test_suite_rejects_boolean_numeric_comparison_fields(self) -> None:
        comparisons = self.make_comparisons(7, 4)
        comparisons[0] = dataclasses.replace(
            comparisons[0],
            budget_parity_passed=1,
            fresh_prompt_ratio=True,
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
