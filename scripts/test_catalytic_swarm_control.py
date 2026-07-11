#!/usr/bin/env python3
from __future__ import annotations

import ast
import copy
import json
import math
import unittest
from dataclasses import replace
from pathlib import Path

from catalytic_blackboard import (
    AppendOnlyBlackboard,
    BlackboardError,
    PHASES,
    canonical_json_bytes,
    phase_dot,
    sha256_bytes,
    verify_blackboard_snapshot,
    verify_phase_codes,
)
from catalytic_swarm import (
    PHASE_COUNTS,
    REQUIRED_VERIFICATION_CHECKS,
    VERIFIER_ID,
    PhysicalLeasePool,
    SwarmError,
    VerificationReceipt,
    build_catalytic_swarm_0_plan,
    contribution_payload_schema,
    expected_control_content,
    expected_control_contribution,
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


def passing_receipt(spec) -> VerificationReceipt:
    return VerificationReceipt(
        worker_id=spec.worker_id,
        passed=True,
        checks=REQUIRED_VERIFICATION_CHECKS,
        artifact_refs=(),
        verifier=VERIFIER_ID,
    )


def exact_runner(spec, context):
    return expected_control_contribution(spec).to_dict()


class BlackboardTests(unittest.TestCase):
    def test_phase_codes_are_pairwise_orthogonal(self) -> None:
        self.assertTrue(verify_phase_codes())
        for phase in PHASES:
            self.assertEqual(phase_dot(phase, phase), 4)
        for index, left in enumerate(PHASES):
            for right in PHASES[index + 1:]:
                self.assertEqual(phase_dot(left, right), 0)

    def test_append_only_chain_and_snapshot_are_independently_valid(self) -> None:
        board = AppendOnlyBlackboard()
        first = board.append(
            phase="proposal", kind="proposal", author_worker_id="w1", body={"claim": "a"}
        )
        second = board.append(
            phase="evidence",
            kind="evidence",
            author_worker_id="w2",
            body={"claim": "b"},
            parent_ids=[first.entry_id],
        )
        self.assertEqual(second.previous_hash, first.entry_hash)
        self.assertTrue(board.verify_chain())
        self.assertTrue(verify_blackboard_snapshot(board.snapshot()))

    def test_entry_body_is_deeply_immutable(self) -> None:
        board = AppendOnlyBlackboard()
        entry = board.append(
            phase="proposal",
            kind="proposal",
            author_worker_id="w1",
            body={"nested": {"items": [1, 2]}},
        )
        with self.assertRaises(TypeError):
            entry.body["new"] = "tamper"  # type: ignore[index]
        with self.assertRaises(TypeError):
            entry.body["nested"]["new"] = "tamper"  # type: ignore[index]
        self.assertIsInstance(entry.body["nested"]["items"], tuple)
        self.assertTrue(board.verify_chain())

    def test_complete_entry_not_only_body_is_bounded(self) -> None:
        board = AppendOnlyBlackboard(max_entry_bytes=512)
        with self.assertRaises(BlackboardError):
            board.append(
                phase="proposal",
                kind="k" * 600,
                author_worker_id="w",
                body={},
            )

    def test_strict_json_rejects_nan(self) -> None:
        board = AppendOnlyBlackboard()
        with self.assertRaises(BlackboardError):
            board.append(
                phase="proposal",
                kind="proposal",
                author_worker_id="w",
                body={"value": math.nan},
            )

    def test_same_phase_parent_is_forbidden(self) -> None:
        board = AppendOnlyBlackboard()
        first = board.append(
            phase="proposal", kind="proposal", author_worker_id="w1", body={"claim": "a"}
        )
        with self.assertRaises(BlackboardError):
            board.append(
                phase="proposal",
                kind="proposal",
                author_worker_id="w2",
                body={"claim": "b"},
                parent_ids=[first.entry_id],
            )

    def test_unverified_synthesis_parent_fails_hard(self) -> None:
        board = AppendOnlyBlackboard()
        critique = board.append(
            phase="critique", kind="critique", author_worker_id="w1", body={"claim": "a"}
        )
        with self.assertRaises(BlackboardError):
            board.select_entries(
                phase="synthesis",
                parent_ids=[critique.entry_id],
                limit=1,
                include_verified_only=True,
                verified_entry_ids=[],
            )

    def test_context_limit_never_silently_truncates_parents(self) -> None:
        board = AppendOnlyBlackboard()
        one = board.append(
            phase="proposal", kind="proposal", author_worker_id="w1", body={"claim": "a"}
        )
        two = board.append(
            phase="proposal", kind="proposal", author_worker_id="w2", body={"claim": "b"}
        )
        with self.assertRaises(BlackboardError):
            board.select_entries(
                phase="evidence", parent_ids=[one.entry_id, two.entry_id], limit=1
            )

    def test_snapshot_tampering_is_detected(self) -> None:
        board = AppendOnlyBlackboard()
        board.append(
            phase="proposal", kind="proposal", author_worker_id="w1", body={"claim": "a"}
        )
        for field, value in (
            ("entry_id", "bb-0001-forged"),
            ("entry_hash", "A" * 64),
            ("phase_code", [9, 9, 9, 9]),
        ):
            snapshot = copy.deepcopy(board.snapshot())
            snapshot["entries"][0][field] = value
            self.assertFalse(verify_blackboard_snapshot(snapshot), field)
        snapshot = copy.deepcopy(board.snapshot())
        snapshot["entries"][0]["body"]["claim"] = "tampered"
        self.assertFalse(verify_blackboard_snapshot(snapshot))


class CatalyticSwarmPlanTests(unittest.TestCase):
    def test_plan_is_exact_and_hash_locked(self) -> None:
        plan = build_catalytic_swarm_0_plan()
        self.assertEqual(plan.plan_sha256, "7AE101BA52CE0C8F00EC649646D6B44D25EDAC2466A730EFF30BF3FD7FDCF78A")
        self.assertEqual(len(plan.logical_workers), 32)
        self.assertEqual(plan.physical_slots, 1)
        self.assertEqual(
            [worker.worker_id for worker in plan.logical_workers],
            [f"cs0-w{ordinal:02d}" for ordinal in range(1, 33)],
        )
        counts = {phase: 0 for phase in PHASES}
        for worker in plan.logical_workers:
            counts[worker.phase] += 1
            self.assertEqual(worker.root_name, "A")
            self.assertEqual(worker.max_tokens, 64)
            self.assertTrue(worker.thinking_disabled)
            self.assertNotIn("deep", worker.role.lower())
        self.assertEqual(counts, PHASE_COUNTS)
        self.assertEqual(plan, build_catalytic_swarm_0_plan())

    def test_non_one_slot_plan_cannot_be_built(self) -> None:
        for value in (0, 2, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_catalytic_swarm_0_plan(physical_slots=value)

    def test_every_exact_worker_output_uses_the_locked_textual_key_order(self) -> None:
        expected_order = [
            "kind", "claim", "target_ids", "references", "artifact_refs", "decision",
        ]
        for spec in build_catalytic_swarm_0_plan().logical_workers:
            pairs = json.loads(
                expected_control_content(spec),
                object_pairs_hook=lambda items: items,
            )
            self.assertEqual([key for key, _ in pairs], expected_order, spec.worker_id)

    def test_complete_plan_drift_is_rejected_before_execution(self) -> None:
        plan = build_catalytic_swarm_0_plan()
        first = plan.logical_workers[0]
        mutations = {
            "schema": replace(plan, schema_version=99),
            "hash": replace(plan, plan_sha256="0" * 64),
            "fail-fast": replace(plan, fail_fast=False),
            "slots": replace(plan, physical_slots=2),
            "worker-budget": replace(
                plan,
                logical_workers=(replace(first, max_tokens=128),) + plan.logical_workers[1:],
            ),
            "deep-role": replace(
                plan,
                logical_workers=(replace(first, role="deep"),) + plan.logical_workers[1:],
            ),
            "worker-id": replace(
                plan,
                logical_workers=(replace(first, worker_id="cs0-forged"),)
                + plan.logical_workers[1:],
            ),
            "worker-ordinal": replace(
                plan,
                logical_workers=(replace(first, ordinal=99),) + plan.logical_workers[1:],
            ),
            "root": replace(
                plan,
                logical_workers=(replace(first, root_name="B"),) + plan.logical_workers[1:],
            ),
            "thinking": replace(
                plan,
                logical_workers=(replace(first, thinking_disabled=False),)
                + plan.logical_workers[1:],
            ),
            "seed": replace(
                plan,
                logical_workers=(replace(first, seed=0),) + plan.logical_workers[1:],
            ),
            "phase-code": replace(
                plan,
                logical_workers=(replace(first, phase_code=(9, 9, 9, 9)),)
                + plan.logical_workers[1:],
            ),
            "context-limit": replace(
                plan,
                logical_workers=(replace(first, context_limit=1),) + plan.logical_workers[1:],
            ),
            "parent-graph": replace(
                plan,
                logical_workers=plan.logical_workers[:16]
                + (replace(plan.logical_workers[16], parent_worker_ids=("cs0-w01",)),)
                + plan.logical_workers[17:],
            ),
            "worker-count": replace(plan, logical_workers=plan.logical_workers[:-1]),
        }
        for label, mutated in mutations.items():
            with self.subTest(label=label), self.assertRaises(SwarmError):
                run_swarm(mutated, worker_runner=exact_runner, verifier=lambda s, c, x: passing_receipt(s))

    def test_contribution_requires_exact_six_key_control_value(self) -> None:
        plan = build_catalytic_swarm_0_plan()
        for spec in (plan.logical_workers[0], plan.logical_workers[16], plan.logical_workers[24], plan.logical_workers[30]):
            exact = expected_control_contribution(spec).to_dict()
            self.assertEqual(parse_contribution(exact, spec), expected_control_contribution(spec))
            missing = dict(exact)
            missing.pop("references")
            with self.assertRaises(SwarmError):
                parse_contribution(missing, spec)
            wrong = dict(exact)
            wrong["target_ids"] = list(spec.parent_worker_ids[:1])
            if list(spec.parent_worker_ids) != wrong["target_ids"]:
                with self.assertRaises(SwarmError):
                    parse_contribution(wrong, spec)
            wrong_decision = dict(exact)
            wrong_decision["decision"] = "support"
            if exact["decision"] != "support":
                with self.assertRaises(SwarmError):
                    parse_contribution(wrong_decision, spec)

    def test_worker_specific_schema_is_exact(self) -> None:
        spec = build_catalytic_swarm_0_plan().logical_workers[-1]
        expected = expected_control_contribution(spec).to_dict()
        properties = contribution_payload_schema(spec)["properties"]
        self.assertEqual({key: value["const"] for key, value in properties.items()}, expected)


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
    def test_full_run_closes_every_exact_acceptance_invariant(self) -> None:
        board = AppendOnlyBlackboard(max_entries=32)
        events: list[tuple[str, dict]] = []
        result = run_swarm(
            build_catalytic_swarm_0_plan(),
            worker_runner=exact_runner,
            verifier=lambda spec, contribution, context: passing_receipt(spec),
            blackboard=board,
            execution_observer=lambda name, payload: events.append((name, dict(payload))),
        )
        self.assertEqual(result.verdict, "reviewable-accept")
        self.assertEqual(len(result.executions), 32)
        self.assertEqual(result.verified_execution_count, 32)
        self.assertEqual(result.lease_count, 32)
        self.assertEqual(result.max_concurrent_leases, 1)
        self.assertEqual(result.active_leases_after, 0)
        self.assertEqual({execution.lease_id for execution in result.executions}, {0})
        self.assertEqual(dict(result.phase_execution_counts), PHASE_COUNTS)
        self.assertEqual(len(result.synthesis_entry_ids), 2)
        self.assertEqual(result.blackboard_entry_count, 32)
        self.assertTrue(result.blackboard_chain_valid)
        self.assertTrue(board.verify_chain())
        self.assertTrue(verify_blackboard_snapshot(board.snapshot()))
        self.assertEqual(sum(name == "worker-start" for name, _ in events), 32)
        self.assertEqual(sum(name == "worker-complete" for name, _ in events), 32)

    def test_context_is_exact_assigned_verified_prior_phase_only(self) -> None:
        observed = {}

        def runner(spec, context):
            observed[spec.worker_id] = tuple(
                (entry.author_worker_id, entry.phase) for entry in context
            )
            return exact_runner(spec, context)

        result = run_swarm(
            build_catalytic_swarm_0_plan(),
            worker_runner=runner,
            verifier=lambda spec, contribution, context: passing_receipt(spec),
        )
        self.assertEqual(result.verdict, "reviewable-accept")
        for execution in result.executions:
            self.assertEqual(
                tuple(author for author, _ in observed[execution.spec.worker_id]),
                execution.spec.parent_worker_ids,
            )
            self.assertNotIn(
                execution.spec.phase,
                tuple(phase for _, phase in observed[execution.spec.worker_id]),
            )

    def test_failed_verifier_stops_before_publication(self) -> None:
        board = AppendOnlyBlackboard(max_entries=32)

        def verifier(spec, contribution, context):
            if spec.ordinal == 3:
                return VerificationReceipt(
                    worker_id=spec.worker_id,
                    passed=False,
                    checks=REQUIRED_VERIFICATION_CHECKS,
                    artifact_refs=(),
                    verifier=VERIFIER_ID,
                    reason="forced rejection",
                )
            return passing_receipt(spec)

        result = run_swarm(
            build_catalytic_swarm_0_plan(),
            worker_runner=exact_runner,
            verifier=verifier,
            blackboard=board,
        )
        self.assertEqual(result.verdict, "reject")
        self.assertEqual(result.stopped_worker_id, "cs0-w03")
        self.assertEqual(len(board), 2)
        self.assertEqual(result.lease_count, 3)
        self.assertEqual(result.active_leases_after, 0)

    def test_receipt_truthiness_or_identity_cannot_pass(self) -> None:
        def verifier(spec, contribution, context):
            return VerificationReceipt(
                worker_id=spec.worker_id,
                passed="true",  # type: ignore[arg-type]
                checks=REQUIRED_VERIFICATION_CHECKS,
                artifact_refs=(),
                verifier=VERIFIER_ID,
            )

        result = run_swarm(
            build_catalytic_swarm_0_plan(), worker_runner=exact_runner, verifier=verifier
        )
        self.assertEqual(result.verdict, "reject")
        self.assertEqual(result.stopped_worker_id, "cs0-w01")

    def test_supplied_empty_board_is_not_discarded(self) -> None:
        board = AppendOnlyBlackboard(max_entries=1)
        result = run_swarm(
            build_catalytic_swarm_0_plan(),
            worker_runner=exact_runner,
            verifier=lambda spec, contribution, context: passing_receipt(spec),
            blackboard=board,
        )
        self.assertEqual(result.verdict, "reject")
        self.assertEqual(len(board), 1)

    def test_prepopulated_board_is_rejected(self) -> None:
        board = AppendOnlyBlackboard()
        board.append(
            phase="proposal", kind="proposal", author_worker_id="foreign", body={"claim": "x"}
        )
        with self.assertRaises(SwarmError):
            run_swarm(
                build_catalytic_swarm_0_plan(),
                worker_runner=exact_runner,
                verifier=lambda spec, contribution, context: passing_receipt(spec),
                blackboard=board,
            )


class HoloStateSwarmAdapterTests(unittest.TestCase):
    def measurement(self, spec, content: str | None = None):
        content = expected_control_content(spec) if content is None else content
        token_ids = [101, 202]
        terminal = {
            "observed": True,
            "stop": True,
            "stop_type": "eos",
            "stopping_word": "",
            "verbose_token_array_length": 0,
            "event_index": 9,
        }
        return {
            "accepted": True,
            "http_status": 200,
            "root_name": "A",
            "lane": "F",
            "configured_max_tokens": 64,
            "request_contract": {
                "worker_id": spec.worker_id,
                "root_name": "A",
                "max_tokens": 64,
                "thinking_disabled": True,
                "temperature": 0.0,
                "seed": spec.seed,
                "cache_prompt": True,
                "stop_sequences_configured": False,
            },
            "expected_content": expected_control_content(spec),
            "assistant_content": {
                "text": content,
                "characters": len(content),
                "sha256": sha256_bytes(content.encode("utf-8")),
                "first_256": content[:256],
                "last_256": content[-256:] if content else "",
            },
            "reasoning_content": {
                "present": False,
                "characters": 0,
                "sha256": sha256_bytes(b""),
            },
            "tool_calls": [],
            "tool_call_count": 0,
            "tool_calls_sha256": sha256_bytes(canonical_json_bytes([])),
            "finish_reason": "stop",
            "completion_tokens": 3,
            "logical_prompt_tokens": 100,
            "cached_prompt_tokens": 90,
            "fresh_prompt_tokens": 10,
            "prompt_token_identity_matches": True,
            "visible_token_evidence": {
                "accepted": True,
                "classification": "accepted",
                "source": "visible-content-retokenization-plus-terminal-control",
                "claim_scope": "exact-visible-content-tokenization-plus-one-terminal-eos-token",
                "token_ids": token_ids,
                "token_count": len(token_ids),
                "token_sha256": sha256_bytes(canonical_json_bytes(token_ids)),
                "completion_tokens": 3,
                "count_match": False,
                "usage_delta": 1,
                "usage_reconciled": True,
                "terminal_control_token_count": 1,
                "terminal_control_token_id_known": False,
                "terminal_eos_id_known": False,
                "terminal_stop_type": "eos",
                "terminal_stopping_word": "",
                "full_generated_sequence_known": False,
                "native_array_present": False,
                "reconstructed": True,
                "reason": None,
                "terminal_eos_gate": {"passed": True, "reasons": [], "evidence": terminal},
                "tokenizer_repeat": {
                    "performed": True,
                    "equal": True,
                    "first": token_ids,
                    "second": token_ids,
                },
            },
        }

    def test_exact_v4_fast_transport_and_structure_pass(self) -> None:
        spec = build_catalytic_swarm_0_plan().logical_workers[0]
        measurement = self.measurement(spec)
        transport, contribution = parse_structured_fast_result(measurement, spec)
        self.assertTrue(transport.accepted)
        self.assertEqual(contribution, expected_control_contribution(spec))

    def test_transport_fails_closed_on_request_channel_or_token_drift(self) -> None:
        spec = build_catalytic_swarm_0_plan().logical_workers[0]
        mutations = {}
        value = self.measurement(spec)
        value["accepted"] = False
        mutations["top-accepted"] = value
        value = self.measurement(spec)
        value["reasoning_content"]["characters"] = 1
        mutations["reasoning"] = value
        value = self.measurement(spec)
        value["tool_calls"] = [{"name": "forbidden"}]
        mutations["tools"] = value
        value = self.measurement(spec)
        value["request_contract"]["max_tokens"] = 65
        mutations["request-budget"] = value
        value = self.measurement(spec)
        value["completion_tokens"] = 65
        mutations["completion-budget"] = value
        value = self.measurement(spec)
        value["visible_token_evidence"]["terminal_eos_gate"]["evidence"]["stop_type"] = "limit"
        mutations["terminal-eos"] = value
        value = self.measurement(spec)
        value["visible_token_evidence"]["token_sha256"] = "0" * 64
        mutations["token-hash"] = value
        value = self.measurement(spec)
        value["visible_token_evidence"]["source"] = "forged"
        mutations["token-source"] = value
        value = self.measurement(spec)
        value["cached_prompt_tokens"] = 0
        mutations["reuse"] = value
        value = self.measurement(spec)
        value["logical_prompt_tokens"] = True
        mutations["boolean-usage"] = value
        for label, measurement in mutations.items():
            with self.subTest(label=label):
                self.assertFalse(validate_fast_transport(measurement, spec).accepted)
                with self.assertRaises(HoloStateSwarmAdapterError):
                    parse_structured_fast_result(measurement, spec)

    def test_noncanonical_visible_content_rejects_even_if_json_equivalent(self) -> None:
        spec = build_catalytic_swarm_0_plan().logical_workers[0]
        equivalent = json.dumps(expected_control_contribution(spec).to_dict(), indent=2)
        measurement = self.measurement(spec, equivalent)
        self.assertFalse(validate_fast_transport(measurement, spec).accepted)

    def test_messages_expose_only_exact_assignment_context_and_output(self) -> None:
        plan = build_catalytic_swarm_0_plan()
        spec = plan.logical_workers[16]
        board = AppendOnlyBlackboard()
        proposals = [
            board.append(
                phase="proposal",
                kind="proposal",
                author_worker_id=worker_id,
                body=expected_control_contribution(plan.logical_workers[index]).to_dict(),
            )
            for index, worker_id in enumerate(spec.parent_worker_ids)
        ]
        messages = build_worker_messages(
            objective="test objective", spec=spec, context_entries=proposals
        )
        self.assertEqual([item["role"] for item in messages], ["system", "user"])
        self.assertIn(expected_control_content(spec), messages[1]["content"])
        for proposal in proposals:
            self.assertIn(proposal.entry_id, messages[1]["content"])

    def test_blackboard_context_ceiling(self) -> None:
        board = AppendOnlyBlackboard()
        entry = board.append(
            phase="proposal", kind="proposal", author_worker_id="w", body={"claim": "x" * 100}
        )
        with self.assertRaises(HoloStateSwarmAdapterError):
            compact_blackboard_context([entry], max_bytes=10)


class StaticNoIOTests(unittest.TestCase):
    def test_generic_connector_has_no_io_network_subprocess_or_git_mutation(self) -> None:
        scripts = Path(__file__).resolve().parent
        forbidden_imports = {
            "aiohttp", "http", "httpx", "os", "pathlib", "requests", "shutil",
            "socket", "subprocess", "tempfile", "urllib",
        }
        forbidden_calls = {
            "open", "Popen", "run", "call", "check_call", "check_output", "system",
            "urlopen", "request", "connect", "create_connection", "write_text",
            "write_bytes", "mkdir", "unlink", "rename", "replace", "rmdir",
        }
        for name in (
            "catalytic_blackboard.py",
            "catalytic_swarm.py",
            "holostate_swarm_adapter.py",
        ):
            tree = ast.parse((scripts / name).read_text(encoding="utf-8"), filename=name)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = {alias.name.split(".", 1)[0] for alias in node.names}
                    self.assertFalse(roots & forbidden_imports, (name, roots))
                elif isinstance(node, ast.ImportFrom) and node.module:
                    self.assertNotIn(node.module.split(".", 1)[0], forbidden_imports, name)
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        called = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        called = node.func.attr
                    else:
                        called = ""
                    self.assertNotIn(called, forbidden_calls, (name, called))


if __name__ == "__main__":
    unittest.main()
