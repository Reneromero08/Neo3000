#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import unittest

from catalytic_blackboard import (
    AppendOnlyBlackboard,
    BlackboardError,
    PHASES,
    phase_dot,
    verify_phase_codes,
)
from catalytic_swarm import (
    PhysicalLeasePool,
    SwarmError,
    VerificationReceipt,
    build_catalytic_swarm_0_plan,
    parse_contribution,
    run_swarm,
)
from holostate_swarm_adapter import (
    HoloStateSwarmAdapterError,
    build_worker_messages,
    compact_blackboard_context,
    parse_structured_fast_result,
    validate_fast_transport,
)


class BlackboardTests(unittest.TestCase):
    def test_phase_codes_are_pairwise_orthogonal(self) -> None:
        self.assertTrue(verify_phase_codes())
        for phase in PHASES:
            self.assertEqual(phase_dot(phase, phase), 4)
        for index, left in enumerate(PHASES):
            for right in PHASES[index + 1:]:
                self.assertEqual(phase_dot(left, right), 0)

    def test_append_only_hash_chain(self) -> None:
        board = AppendOnlyBlackboard()
        first = board.append(
            phase="proposal",
            kind="proposal",
            author_worker_id="w1",
            body={"claim": "a"},
        )
        second = board.append(
            phase="evidence",
            kind="evidence",
            author_worker_id="w2",
            body={"claim": "b"},
            parent_ids=[first.entry_id],
        )
        self.assertTrue(board.verify_chain())
        self.assertEqual(second.previous_hash, first.entry_hash)
        snapshot = board.snapshot()
        altered = copy.deepcopy(snapshot)
        altered["entries"][0]["body"]["claim"] = "tampered"
        self.assertNotEqual(altered, snapshot)

    def test_same_phase_parent_is_forbidden(self) -> None:
        board = AppendOnlyBlackboard()
        first = board.append(
            phase="proposal",
            kind="proposal",
            author_worker_id="w1",
            body={"claim": "a"},
        )
        with self.assertRaises(BlackboardError):
            board.append(
                phase="proposal",
                kind="proposal",
                author_worker_id="w2",
                body={"claim": "b"},
                parent_ids=[first.entry_id],
            )

    def test_verified_filter_prevents_unverified_synthesis_context(self) -> None:
        board = AppendOnlyBlackboard()
        critique = board.append(
            phase="critique",
            kind="critique",
            author_worker_id="w1",
            body={"claim": "a"},
        )
        selected = board.select_entries(
            phase="synthesis",
            parent_ids=[critique.entry_id],
            limit=1,
            include_verified_only=True,
            verified_entry_ids=[],
        )
        self.assertEqual(selected, ())


class CatalyticSwarmPlanTests(unittest.TestCase):
    def test_plan_has_32_logical_workers_and_one_physical_slot(self) -> None:
        plan = build_catalytic_swarm_0_plan()
        self.assertEqual(len(plan.logical_workers), 32)
        self.assertEqual(plan.physical_slots, 1)
        self.assertEqual(plan.max_worker_tokens, 64)
        self.assertFalse(plan.automatic_promotion)
        counts = {}
        for worker in plan.logical_workers:
            counts[worker.phase] = counts.get(worker.phase, 0) + 1
            self.assertTrue(worker.thinking_disabled)
            self.assertEqual(worker.max_tokens, 64)
        self.assertEqual(
            counts,
            {"proposal": 16, "evidence": 8, "critique": 6, "synthesis": 2},
        )

    def test_plan_is_deterministic(self) -> None:
        left = build_catalytic_swarm_0_plan()
        right = build_catalytic_swarm_0_plan()
        self.assertEqual(left.plan_sha256, right.plan_sha256)
        self.assertEqual(left.logical_workers, right.logical_workers)

    def test_contribution_rejects_unassigned_targets(self) -> None:
        plan = build_catalytic_swarm_0_plan()
        evidence = next(item for item in plan.logical_workers if item.phase == "evidence")
        with self.assertRaises(SwarmError):
            parse_contribution(
                {
                    "kind": "evidence",
                    "claim": "x",
                    "target_ids": ["not-assigned"],
                    "references": [],
                    "artifact_refs": [],
                    "decision": "reject",
                },
                evidence,
            )


class PhysicalLeasePoolTests(unittest.TestCase):
    def test_one_slot_is_reused_without_overlap(self) -> None:
        pool = PhysicalLeasePool(1)
        with pool.lease() as first:
            self.assertEqual(first, 0)
            self.assertEqual(pool.active_count, 1)
        with pool.lease() as second:
            self.assertEqual(second, 0)
        self.assertEqual(pool.max_concurrent, 1)
        self.assertEqual(pool.lease_count, 2)
        self.assertEqual(pool.active_count, 0)


class CatalyticSwarmRunTests(unittest.TestCase):
    def worker_runner(self, spec, context):
        if spec.phase == "proposal":
            targets = []
            decision = None
        elif spec.phase == "synthesis":
            targets = [spec.parent_worker_ids[0]]
            decision = "select"
        else:
            targets = [spec.parent_worker_ids[0]]
            decision = "support"
        return {
            "kind": {
                "proposal": "proposal",
                "evidence": "evidence",
                "critique": "critique",
                "synthesis": "selection",
            }[spec.phase],
            "claim": f"{spec.worker_id} compact contribution",
            "target_ids": targets,
            "references": [],
            "artifact_refs": [],
            "decision": decision,
        }

    def verifier(self, spec, contribution, context):
        return VerificationReceipt(
            worker_id=spec.worker_id,
            passed=True,
            checks=("schema", "identity"),
            artifact_refs=(),
            verifier="unit-test",
        )

    def test_full_run_multiplexes_32_workers_over_one_slot(self) -> None:
        result = run_swarm(
            build_catalytic_swarm_0_plan(),
            worker_runner=self.worker_runner,
            verifier=self.verifier,
        )
        self.assertEqual(result.verdict, "reviewable-accept")
        self.assertEqual(len(result.executions), 32)
        self.assertEqual(result.lease_count, 32)
        self.assertEqual(result.max_concurrent_leases, 1)
        self.assertEqual(len(result.synthesis_entry_ids), 2)
        self.assertFalse(result.automatic_promotion)

    def test_same_phase_workers_do_not_receive_same_phase_context(self) -> None:
        plan = build_catalytic_swarm_0_plan()
        observed = {}

        def runner(spec, context):
            observed[spec.worker_id] = tuple(entry.phase for entry in context)
            return self.worker_runner(spec, context)

        result = run_swarm(plan, worker_runner=runner, verifier=self.verifier)
        self.assertEqual(result.verdict, "reviewable-accept")
        for execution in result.executions:
            self.assertNotIn(
                execution.spec.phase,
                observed[execution.spec.worker_id],
            )

    def test_verifier_failure_stops_fail_fast(self) -> None:
        plan = build_catalytic_swarm_0_plan()

        def verifier(spec, contribution, context):
            return VerificationReceipt(
                worker_id=spec.worker_id,
                passed=spec.ordinal != 3,
                checks=("schema",),
                artifact_refs=(),
                verifier="unit-test",
                reason="forced rejection" if spec.ordinal == 3 else None,
            )

        result = run_swarm(plan, worker_runner=self.worker_runner, verifier=verifier)
        self.assertEqual(result.verdict, "reject")
        self.assertEqual(result.stopped_worker_id, plan.logical_workers[2].worker_id)


class HoloStateSwarmAdapterTests(unittest.TestCase):
    def measurement(self, content: str):
        return {
            "assistant_content": {"text": content},
            "reasoning_content": {"present": False},
            "tool_calls": [],
            "tool_call_count": 0,
            "finish_reason": "stop",
            "prompt_tokens": 100,
            "cached_prompt_tokens": 90,
            "fresh_prompt_tokens": 10,
            "token_evidence": {
                "accepted": True,
                "source": "visible-content-retokenization-plus-terminal-control",
                "claim_scope": "exact-visible-content-tokenization-plus-one-terminal-eos-token",
                "terminal_stop_type": "eos",
            },
        }

    def test_transport_accepts_v4_like_fast_evidence(self) -> None:
        self.assertTrue(validate_fast_transport(self.measurement("{}")).accepted)

    def test_transport_rejects_reasoning(self) -> None:
        measurement = self.measurement("{}")
        measurement["reasoning_content"] = {"present": True}
        self.assertFalse(validate_fast_transport(measurement).accepted)

    def test_structured_result_parses_contribution(self) -> None:
        spec = build_catalytic_swarm_0_plan().logical_workers[0]
        payload = {
            "kind": "proposal",
            "claim": "compact",
            "target_ids": [],
            "references": [],
            "artifact_refs": [],
            "decision": None,
        }
        transport, contribution = parse_structured_fast_result(
            self.measurement(json.dumps(payload)),
            spec,
        )
        self.assertTrue(transport.accepted)
        self.assertEqual(contribution.claim, "compact")

    def test_invalid_json_rejects(self) -> None:
        spec = build_catalytic_swarm_0_plan().logical_workers[0]
        with self.assertRaises(HoloStateSwarmAdapterError):
            parse_structured_fast_result(self.measurement("not-json"), spec)

    def test_messages_keep_assignment_and_blackboard_separate(self) -> None:
        plan = build_catalytic_swarm_0_plan()
        spec = plan.logical_workers[16]
        board = AppendOnlyBlackboard()
        proposal = board.append(
            phase="proposal",
            kind="proposal",
            author_worker_id=spec.parent_worker_ids[0],
            body={"claim": "a"},
        )
        messages = build_worker_messages(
            objective="test objective",
            spec=spec,
            context_entries=[proposal],
        )
        self.assertEqual([item["role"] for item in messages], ["system", "user"])
        self.assertIn("test objective", messages[1]["content"])
        self.assertIn(proposal.entry_id, messages[1]["content"])

    def test_blackboard_context_ceiling(self) -> None:
        board = AppendOnlyBlackboard()
        entry = board.append(
            phase="proposal",
            kind="proposal",
            author_worker_id="w",
            body={"claim": "x" * 100},
        )
        with self.assertRaises(HoloStateSwarmAdapterError):
            compact_blackboard_context([entry], max_bytes=10)


if __name__ == "__main__":
    unittest.main()
