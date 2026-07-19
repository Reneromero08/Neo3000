#!/usr/bin/env python3
from __future__ import annotations

import inspect
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import catalytic_kernel_0_two_shard_semantic_xor_worker_baseline_evaluation as probe
import catalytic_kernel_0_two_shard_semantic_xor_worker_baseline_evaluation_scientific as scientific


REPOSITORY = Path(__file__).resolve().parent.parent
MODEL_ENV = "NEO3000_TOKENIZER_MODEL"


class SemanticXorWorkerBaselineEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        model = os.environ.get(MODEL_ENV)
        if not model:
            raise unittest.SkipTest(f"{MODEL_ENV} is required for offline tokenizer reconstruction")
        cls.model_path = Path(model)
        cls.corpus = probe.load_public_tasks(REPOSITORY)
        cls.tasks = {task["task_id"]: task for task in cls.corpus["tasks"]}
        cls.fixed_payloads = probe.build_fixed_payloads(cls.corpus)
        cls.artifact = json.loads((REPOSITORY / probe.PREREGISTRATION_PATH).read_bytes())
        cls.root = probe._load_evidence_root(REPOSITORY)

    def test_01_frozen_public_sources_reconstruct_exactly(self) -> None:
        self.assertEqual(tuple(self.tasks), probe.TASK_IDS)
        self.assertEqual(
            probe.sha256_bytes((REPOSITORY / probe.DESIGN_PATH).read_bytes()),
            probe.DESIGN_SHA256,
        )
        self.assertEqual(
            probe.sha256_bytes((REPOSITORY / probe.PUBLIC_CORPUS_PATH).read_bytes()),
            probe.PUBLIC_CORPUS_SHA256,
        )
        self.assertEqual(
            probe.sha256_bytes((REPOSITORY / probe.CORPUS_BINDING_PATH).read_bytes()),
            probe.CORPUS_BINDING_SHA256,
        )

    def test_02_task_ids_derive_from_public_bodies_and_are_sorted(self) -> None:
        self.assertEqual(
            [probe._derived_task_id(task) for task in self.corpus["tasks"]],
            list(probe.TASK_IDS),
        )
        self.assertEqual(list(probe.TASK_IDS), sorted(probe.TASK_IDS))

    def test_03_protected_evaluator_public_custody_does_not_open_bytes(self) -> None:
        original = Path.read_bytes

        def guarded(path: Path):
            if path.resolve(strict=False) == (REPOSITORY / probe.PROTECTED_EVALUATOR_PATH).resolve(strict=False):
                raise AssertionError("public custody opened protected evaluator")
            return original(path)

        with mock.patch.object(Path, "read_bytes", guarded):
            custody = probe.validate_protected_evaluator_custody(REPOSITORY)
        self.assertFalse(custody["bytes_opened"])
        self.assertFalse(custody["bytes_hashed"])
        self.assertTrue(custody["ignored"])

    def test_04_public_request_constructors_do_not_access_evaluator(self) -> None:
        for value in (
            probe.build_worker_request,
            probe.build_synthesis_request,
            probe.build_direct_baseline_request,
        ):
            source = inspect.getsource(value).lower()
            self.assertNotIn("protected_evaluator", source)
            self.assertNotIn("expected_worker", source)
            self.assertNotIn("expected_label", source)

    def test_05_all_eight_workers_receive_exactly_one_shard(self) -> None:
        for task_id in probe.TASK_IDS:
            task = self.tasks[task_id]
            for worker_role, own, other in (
                ("worker-A", "a", "b"),
                ("worker-B", "b", "a"),
            ):
                payload = self.fixed_payloads[f"{task_id}-{worker_role}"]
                assignment = json.loads(payload["messages"][1]["content"])
                self.assertEqual(
                    set(assignment),
                    {"family_id", "task_id", "worker_role", "passage", "question", "bit_semantics"},
                )
                self.assertEqual(assignment["passage"], task[f"shard_{own}_passage"])
                self.assertEqual(assignment["question"], task[f"shard_{own}_question"])
                text = probe.canonical_json_text(payload)
                self.assertNotIn(task[f"shard_{other}_passage"], text)
                self.assertNotIn(task[f"shard_{other}_question"], text)

    def test_06_all_four_baselines_receive_both_exact_shards(self) -> None:
        for task_id in probe.TASK_IDS:
            task = self.tasks[task_id]
            assignment = json.loads(
                self.fixed_payloads[f"{task_id}-baseline"]["messages"][1]["content"]
            )
            self.assertEqual(assignment["shard_a"], {
                "passage": task["shard_a_passage"], "question": task["shard_a_question"],
            })
            self.assertEqual(assignment["shard_b"], {
                "passage": task["shard_b_passage"], "question": task["shard_b_question"],
            })

    def test_07_synthesis_contains_no_passage_question_or_evaluator_data(self) -> None:
        artifacts = [
            {"worker_role": "worker-A", "captured_bit": 0, "source_capture_commitment_sha256": "A" * 64},
            {"worker_role": "worker-B", "captured_bit": 1, "source_capture_commitment_sha256": "B" * 64},
        ]
        payload = probe.build_synthesis_request(self.corpus, probe.TASK_IDS[0], artifacts)
        text = probe.canonical_json_text(payload).lower()
        for forbidden in ("passage", "question", "expected_", "private_salt", "evaluator"):
            self.assertNotIn(forbidden, text)
        assignment = json.loads(payload["messages"][1]["content"])
        self.assertEqual(set(assignment), {
            "family_id", "task_id", "worker_artifacts", "xor_mapping", "final_label_schema",
        })

    def test_08_every_captured_bit_pair_constructs_a_valid_synthesis(self) -> None:
        hashes = set()
        for bit_a in (0, 1):
            for bit_b in (0, 1):
                artifacts = [
                    {"worker_role": "worker-A", "captured_bit": bit_a, "source_capture_commitment_sha256": "A" * 64},
                    {"worker_role": "worker-B", "captured_bit": bit_b, "source_capture_commitment_sha256": "B" * 64},
                ]
                payload = probe.build_synthesis_request(self.corpus, probe.TASK_IDS[0], artifacts)
                hashes.add(probe.verify_synthesis_payload(self.corpus, probe.TASK_IDS[0], artifacts, payload))
        self.assertEqual(len(hashes), 4)

    def test_09_source_commitment_binds_actual_capture_hash_and_bit(self) -> None:
        common = {
            "task_id": probe.TASK_IDS[0],
            "worker_role": "worker-A",
            "worker_request_sha256": "1" * 64,
            "generation_ordinal": 2,
        }
        first = probe.source_capture_commitment(
            self.root, authenticated_capture_sha256="2" * 64, captured_bit=0, **common
        )
        changed_capture = probe.source_capture_commitment(
            self.root, authenticated_capture_sha256="3" * 64, captured_bit=0, **common
        )
        changed_bit = probe.source_capture_commitment(
            self.root, authenticated_capture_sha256="2" * 64, captured_bit=1, **common
        )
        self.assertEqual(len({first, changed_capture, changed_bit}), 3)

    def test_10_synthesis_artifact_has_exactly_three_public_fields(self) -> None:
        artifact = probe.build_worker_artifact(
            self.root,
            task_id=probe.TASK_IDS[0],
            worker_role="worker-A",
            worker_request_sha256="4" * 64,
            authenticated_capture_sha256="5" * 64,
            captured_bit=1,
            generation_ordinal=2,
        )
        self.assertEqual(set(artifact), {
            "worker_role", "captured_bit", "source_capture_commitment_sha256",
        })

    def test_10b_synthesis_path_reverifies_worker_captures(self) -> None:
        source = inspect.getsource(probe.run_evaluation)
        self.assertLess(
            source.index("verify_worker_artifacts_before_synthesis"),
            source.index("build_synthesis_request"),
        )
        helper = inspect.getsource(probe.verify_worker_artifacts_before_synthesis)
        self.assertIn("scientific.verify_capture", helper)
        self.assertIn("worker artifact no longer binds authenticated capture", helper)

    def test_11_fixed_worker_and_baseline_hashes_reconstruct_exactly(self) -> None:
        observed = {
            request_id: probe.json_sha256(payload)
            for request_id, payload in self.fixed_payloads.items()
        }
        self.assertEqual(
            observed,
            self.artifact["request_bindings"]["fixed_worker_and_baseline_request_sha256"],
        )
        self.assertEqual(len(observed), 12)

    def test_12_synthesis_is_bound_by_derivation_law_not_placeholder_hash(self) -> None:
        bindings = self.artifact["request_bindings"]
        self.assertEqual(bindings["derived_synthesis_request_ids"], list(scientific.DERIVED_REQUEST_IDS))
        self.assertFalse(bindings["falsely_preknown_synthesis_hashes"])
        self.assertEqual(
            probe.synthesis_derivation_law(self.corpus),
            bindings["synthesis_derivation_law"],
        )

    def test_13_all_sixteen_seeds_reconstruct_answer_independently(self) -> None:
        observed = {
            f"{task_id}-{role}": probe.derive_seed(task_id, role)
            for task_id in probe.TASK_IDS
            for role in probe.REQUEST_ROLES
        }
        self.assertEqual(observed, probe.SEEDS)
        self.assertEqual(observed, self.artifact["seed_law"]["seed_by_request"])
        self.assertNotIn("evaluator", inspect.getsource(probe.derive_seed).lower())
        self.assertEqual(len(set(observed.values())), 16)

    def test_14_cache_is_disabled_uniformly(self) -> None:
        self.assertTrue(all(payload["cache_prompt"] is False for payload in self.fixed_payloads.values()))
        artifacts = [
            {"worker_role": "worker-A", "captured_bit": 0, "source_capture_commitment_sha256": "A" * 64},
            {"worker_role": "worker-B", "captured_bit": 0, "source_capture_commitment_sha256": "B" * 64},
        ]
        self.assertFalse(probe.build_synthesis_request(self.corpus, probe.TASK_IDS[0], artifacts)["cache_prompt"])

    def test_15_valid_schema_outputs_fit_eight_token_ceiling(self) -> None:
        lengths = self.artifact["prompts_and_schemas"]["valid_output_token_lengths"]
        self.assertLessEqual(max(lengths.values()), 8)
        self.assertEqual(self.artifact["prompts_and_schemas"]["maximum_completion_tokens"], 8)

    def test_16_execution_order_and_route_first_balance_are_exact(self) -> None:
        expected = []
        for task_id, roles in zip(probe.TASK_IDS, probe.ROLE_ORDER_BY_TASK, strict=True):
            expected.extend(f"{task_id}-{role}" for role in roles)
        self.assertEqual(tuple(expected), probe.REQUEST_IDS)
        self.assertEqual(sum(roles[0] == "baseline" for roles in probe.ROLE_ORDER_BY_TASK), 2)
        self.assertEqual(sum(roles[0] == "worker-A" for roles in probe.ROLE_ORDER_BY_TASK), 2)

    def test_17_sixteen_generation_ceiling_duplicate_and_order_are_enforced(self) -> None:
        started = []
        for request_id in probe.REQUEST_IDS:
            probe.assert_can_start(started, request_id)
            started.append(request_id)
        with self.assertRaisesRegex(probe.SemanticXorEvaluationError, "ceiling"):
            probe.assert_can_start(started, probe.REQUEST_IDS[-1])
        with self.assertRaisesRegex(probe.SemanticXorEvaluationError, "order"):
            probe.assert_can_start([], probe.REQUEST_IDS[1])
        with self.assertRaisesRegex(probe.SemanticXorEvaluationError, "duplicate"):
            probe.assert_can_start([probe.REQUEST_IDS[0]], probe.REQUEST_IDS[0])

    def test_18_semantically_wrong_bits_are_schema_admissible_without_repair(self) -> None:
        self.assertEqual(probe.parse_worker_output('{"bit":0}'), 0)
        self.assertEqual(probe.parse_worker_output('{"bit":1}'), 1)
        scoring = {"aggregate": {
            "semantic_worker_bits_correct": 7,
            "xor_relation_fidelity": 4,
            "worker_route_final_correct": 3,
        }}
        self.assertEqual(
            probe.capability_classification(scoring, evidence_complete=True, cleanup_passed=True, postflight_passed=True),
            probe.WORKER_NOT_SUPPORTED,
        )

    def test_19_protected_evaluator_is_not_opened_before_lifecycle_closure(self) -> None:
        with mock.patch.object(probe, "_regular_bytes", side_effect=AssertionError("opened")) as reader:
            with self.assertRaisesRegex(probe.SemanticXorEvaluationError, "sixteen captures"):
                probe.score_protected_outcomes(
                    REPOSITORY,
                    {},
                    completed_capture_ids=(),
                    cleanup_passed=False,
                    postflight_passed=False,
                )
        reader.assert_not_called()

    def test_20_protected_scorer_returns_only_correctness_not_expected_values(self) -> None:
        fake_tasks = ("fake-0", "fake-1", "fake-2", "fake-3")
        fake_roles = (
            ("baseline", "worker-A", "worker-B", "synthesis"),
            ("worker-A", "worker-B", "synthesis", "baseline"),
            ("baseline", "worker-A", "worker-B", "synthesis"),
            ("worker-A", "worker-B", "synthesis", "baseline"),
        )
        fake_requests = tuple(
            f"{task}-{role}"
            for task, roles in zip(fake_tasks, fake_roles, strict=True)
            for role in roles
        )
        cells = ((0, 0), (0, 1), (1, 0), (1, 1))
        entries = [
            {
                "task_id": task,
                "expected_worker_a_bit": bits[0],
                "expected_worker_b_bit": bits[1],
                "expected_label": "SAME" if bits[0] == bits[1] else "DIFFERENT",
            }
            for task, bits in zip(fake_tasks, cells, strict=True)
        ]
        evaluator = {
            "schema_version": 1,
            "family_id": "fake-family",
            "public_corpus_sha256": "C" * 64,
            "private_salt_hex": "D" * 64,
            "entries": entries,
            "cell_coverage_validation": {
                "cells_present_once": True,
                "exact_four_cell_coverage": True,
                "worker_a_bit_balance": {"0": 2, "1": 2},
                "worker_b_bit_balance": {"0": 2, "1": 2},
                "final_label_balance": {"DIFFERENT": 2, "SAME": 2},
            },
            "created_before_model_contact": True,
        }
        outcomes = {
            task: {
                "worker_a_bit": bits[0],
                "worker_b_bit": bits[1],
                "synthesis_label": "SAME" if bits[0] == bits[1] else "DIFFERENT",
                "baseline_label": "SAME" if bits[0] == bits[1] else "DIFFERENT",
            }
            for task, bits in zip(fake_tasks, cells, strict=True)
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = probe.canonical_json_bytes(evaluator) + b"\n"
            (root / "evaluator.json").write_bytes(data)
            with mock.patch.multiple(
                probe,
                TASK_IDS=fake_tasks,
                REQUEST_IDS=fake_requests,
                FAMILY_ID="fake-family",
                PUBLIC_CORPUS_SHA256="C" * 64,
                PROTECTED_EVALUATOR_PATH=Path("evaluator.json"),
                PROTECTED_EVALUATOR_SIZE=len(data),
                PROTECTED_EVALUATOR_SHA256=probe.sha256_bytes(data),
            ):
                scored = probe.score_protected_outcomes(
                    root,
                    outcomes,
                    completed_capture_ids=fake_requests,
                    cleanup_passed=True,
                    postflight_passed=True,
                )
        text = probe.canonical_json_text(scored)
        self.assertNotIn("expected_", text)
        self.assertNotIn("private_salt", text)
        self.assertFalse(scored["protected_values_disclosed"])
        self.assertEqual(scored["aggregate"]["semantic_worker_bits_correct"], 8)

    def test_21_resource_accounting_uses_exact_integer_cross_products(self) -> None:
        records = [
            {
                "request_id": request_id,
                "logical_prompt_tokens": 10 if probe.request_role(request_id) != "baseline" else 40,
                "cached_prompt_tokens": 0,
                "completion_tokens": 2,
                "maximum_output_tokens": 8,
                "generation_count": 1,
                "maximum_request_context": 18 if probe.request_role(request_id) != "baseline" else 48,
            }
            for request_id in probe.REQUEST_IDS
        ]
        scoring = {"aggregate": {"worker_route_final_correct": 4, "baseline_final_correct": 4}}
        accounted = probe.account_resources(records, scoring, probe.CAPABILITY_SUPPORTED)
        worker = accounted["worker_route"]["fresh_prompt_plus_completion_tokens"]
        baseline = accounted["direct_route"]["fresh_prompt_plus_completion_tokens"]
        self.assertEqual(accounted["exact_integer_cross_products"], {
            "worker_tokens_x_baseline_correct": worker * 4,
            "baseline_tokens_x_worker_correct": baseline * 4,
        })
        self.assertEqual(accounted["advantage_classification"], probe.ADVANTAGE_SUPPORTED)

    def test_22_zero_correct_route_is_infinity(self) -> None:
        records = [
            {
                "request_id": request_id,
                "logical_prompt_tokens": 10,
                "cached_prompt_tokens": 0,
                "completion_tokens": 1,
                "maximum_output_tokens": 8,
                "generation_count": 1,
                "maximum_request_context": 18,
            }
            for request_id in probe.REQUEST_IDS
        ]
        scoring = {"aggregate": {"worker_route_final_correct": 0, "baseline_final_correct": 1}}
        accounted = probe.account_resources(records, scoring, probe.WORKER_NOT_SUPPORTED)
        self.assertEqual(accounted["worker_route"]["tokens_per_correct_final_label"]["kind"], "infinity")
        self.assertEqual(accounted["advantage_classification"], probe.ADVANTAGE_NOT_SUPPORTED)

    def test_23_capture_occurs_before_parse_and_replays_without_contact(self) -> None:
        execution = {name: None for name in scientific.CAPTURE_EXECUTION_FIELDS}
        execution.update({"content": "{}", "finish_reason": "stop", "http_status": 200, "event_count": 1})
        request_id = probe.REQUEST_IDS[0]
        with tempfile.TemporaryDirectory() as temp:
            capture = scientific.capture_execution(
                Path(temp) / "capture.json",
                experiment_key=b"x" * 32,
                request_id=request_id,
                model_request_sha256="A" * 64,
                generation_ordinal=1,
                execution=SimpleNamespace(**execution),
                raw_response_bytes=b"data: {}\n\n",
            )
        self.assertTrue(capture["captured_before_parsing"])
        self.assertEqual(scientific.replay_capture(capture).http_status, 200)
        self.assertNotIn("execute_request", inspect.getsource(scientific.replay_capture))

    def test_24_derived_synthesis_hash_is_journaled_before_request_start(self) -> None:
        source = inspect.getsource(scientific.execute_and_capture_request)
        self.assertLess(source.index("derived-synthesis-request-bound"), source.index("request-started"))
        self.assertLess(source.index("derived-synthesis-request-bound"), source.index("live.execute_request"))

    def test_25_delayed_scoring_occurs_after_cleanup_and_postflight_in_controller(self) -> None:
        source = inspect.getsource(probe.run_evaluation)
        self.assertLess(source.index("live.cleanup"), source.index("score_protected_outcomes"))
        self.assertLess(source.index("live.postflight"), source.index("score_protected_outcomes"))

    def test_26_exact_preregistration_reconstruction_passes(self) -> None:
        self.assertEqual(
            probe.validate_preregistration(REPOSITORY, self.model_path),
            self.artifact,
        )

    def test_27_no_authority_runtime_result_or_archive_exists(self) -> None:
        paths = probe.state_paths(REPOSITORY)
        self.assertFalse(paths["receipt"].exists())
        self.assertFalse(paths["run_root"].exists())
        self.assertTrue(all(value in (False, 0) for value in self.artifact["execution_state"].values()))

    def test_28_results_ledger_remains_unchanged_at_59_records(self) -> None:
        lines = (REPOSITORY / "lab" / "results.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 59)
        self.assertEqual(sum('"id":"neo-exp-0046"' in line for line in lines), 1)

    def test_29_authenticated_journal_verifies_and_tampering_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "journal.jsonl"
            writer = probe.JournalWriter(path, b"j" * 32)
            writer.append("authority-consumed")
            writer.append("request-started", request_id=probe.REQUEST_IDS[0])
            self.assertEqual(len(probe.verify_journal(path, b"j" * 32)), 2)
            path.write_bytes(path.read_bytes().replace(b"request-started", b"request-stopped"))
            with self.assertRaises(probe.SemanticXorEvaluationError):
                probe.verify_journal(path, b"j" * 32)

    def test_30_claim_locks_and_zero_live_state_are_complete(self) -> None:
        self.assertEqual(self.artifact["claim_locks"], probe.LOCKED_CLAIMS)
        self.assertFalse(self.artifact["claim_locks"]["automatic_promotion"])
        self.assertEqual(self.artifact["capture_and_execution_law"]["maximum_generations"], 16)


if __name__ == "__main__":
    unittest.main(verbosity=2)
