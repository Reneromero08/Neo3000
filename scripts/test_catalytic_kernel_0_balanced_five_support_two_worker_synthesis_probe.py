#!/usr/bin/env python3
from __future__ import annotations

import inspect
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import catalytic_kernel_0_balanced_five_support_two_worker_synthesis_probe as probe
import catalytic_kernel_0_balanced_five_support_two_worker_synthesis_probe_scientific as scientific


REPOSITORY = Path(__file__).resolve().parent.parent
MODEL_ENV = "NEO3000_TOKENIZER_MODEL"


class FiveSupportWorkerSynthesisProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        model = os.environ.get(MODEL_ENV)
        if not model:
            raise unittest.SkipTest(f"{MODEL_ENV} is required for offline tokenizer reconstruction")
        cls.model_path = Path(model)
        cls.root, cls.private = probe._load_private(REPOSITORY)
        cls.admission = probe.public_profile_admission()
        cls.payloads = probe.build_payloads(cls.root, cls.private, cls.admission)
        cls.artifact = json.loads((REPOSITORY / probe.PREREGISTRATION_PATH).read_bytes())
        cls.tokenizer = probe.asymmetry.OfflineTokenizer(cls.model_path)

    def test_01_frozen_profile_reconstructs_from_public_projection(self) -> None:
        profile = self.admission["profile"]
        self.assertEqual(profile["task_index"], 2)
        self.assertEqual(self.admission["profile_binding_sha256"], probe.EXPECTED_PROFILE_BINDING_SHA256)
        self.assertTrue(self.admission["frozen_before_hidden_utility"])

    def test_02_shards_are_exactly_012_and_234(self) -> None:
        self.assertEqual(probe.WORKER_INDICES, {"worker-A": (0, 1, 2), "worker-B": (2, 3, 4)})
        self.assertEqual(self.admission["profile"]["branch_indices"], {"branch-a": [0, 1, 2], "branch-b": [2, 3, 4]})

    def test_03_shard_union_and_overlap_are_exact(self) -> None:
        a = set(probe.WORKER_INDICES["worker-A"])
        b = set(probe.WORKER_INDICES["worker-B"])
        self.assertEqual(len(a | b), 5)
        self.assertEqual(len(a & b), 1)

    def test_04_each_objective_support_has_five_candidates(self) -> None:
        supports = self.admission["profile"]["support_sets"]
        self.assertEqual({name: len(value) for name, value in supports.items()}, {"branch-a": 5, "branch-b": 5})

    def test_05_every_support_candidate_passes_all_local_examples(self) -> None:
        profile = self.admission["profile"]
        self.assertEqual(profile["support_pass_vectors"], {"branch-a": [True, True, True], "branch-b": [True, True, True]})

    def test_06_each_local_plateau_gap_is_one(self) -> None:
        self.assertEqual(self.admission["profile"]["plateau_gaps"], {"branch-a": 1, "branch-b": 1})

    def test_07_support_intersection_is_exactly_one(self) -> None:
        supports = self.admission["profile"]["support_sets"]
        self.assertEqual(len(set(supports["branch-a"]) & set(supports["branch-b"])), 1)

    def test_08_full_public_support_equals_intersection(self) -> None:
        profile = self.admission["profile"]
        intersection = sorted(set(profile["support_sets"]["branch-a"]) & set(profile["support_sets"]["branch-b"]))
        self.assertEqual(intersection, profile["full_public_support"])

    def test_09_hidden_utility_is_consulted_after_profile_freeze(self) -> None:
        utility = probe.protected_utility_gate(self.admission)
        self.assertTrue(utility["profile_frozen_before_hidden_consultation"])
        self.assertNotIn("hidden_examples", self.admission)

    def test_10_unique_candidate_is_hidden_exact_16_of_16(self) -> None:
        utility = probe.protected_utility_gate(self.admission)
        self.assertEqual((utility["hidden_score"], utility["hidden_total"]), (16, 16))
        self.assertTrue(utility["unique_full_public_support_equals_protected_answer"])

    def test_11_workers_use_one_shared_opaque_namespace(self) -> None:
        carriers = {
            worker_id: json.loads(self.payloads[worker_id]["messages"][1]["content"])
            for worker_id in probe.WORKER_IDS
        }
        aliases = [
            {item["candidate_alias"] for item in carrier["opaque_candidates"]}
            for carrier in carriers.values()
        ]
        self.assertEqual(aliases[0], aliases[1])
        self.assertEqual(aliases[0], set(probe.balanced.ALIASES))

    def test_12_worker_requests_expose_only_local_anonymous_examples(self) -> None:
        for worker_id in probe.WORKER_IDS:
            carrier = json.loads(self.payloads[worker_id]["messages"][1]["content"])
            self.assertEqual([item["example_id"] for item in carrier["public_examples"]], ["E0", "E1", "E2"])
            self.assertNotIn("task_id", carrier)
            self.assertNotIn("profile_id", carrier)
            self.assertNotIn("hidden_examples", carrier)

    def test_13_worker_prompts_have_matched_byte_and_token_lengths(self) -> None:
        texts = {worker_id: probe.canonical_json_text(self.payloads[worker_id]) for worker_id in probe.WORKER_IDS}
        self.assertEqual(len({len(text.encode("utf-8")) for text in texts.values()}), 1)
        self.assertEqual(len({self.tokenizer.length(text) for text in texts.values()}), 1)

    def test_14_worker_schema_requires_exactly_five_unique_aliases(self) -> None:
        relation = probe.worker_response_schema()["properties"]["support_aliases"]
        self.assertEqual((relation["minItems"], relation["maxItems"]), (5, 5))
        self.assertTrue(relation["uniqueItems"])

    def test_15_model_returned_support_cannot_be_controller_repaired(self) -> None:
        objective = list(probe._objective_support_aliases(self.private, self.admission, "worker-A"))
        authored, normalized = probe.validate_worker_relation(
            self.root,
            self.private,
            self.admission,
            "worker-A",
            json.dumps({"support_aliases": objective}),
        )
        self.assertEqual(authored, objective)
        self.assertEqual(set(normalized), set(objective))
        with self.assertRaisesRegex(probe.FiveSupportWorkerSynthesisError, "GENERATION_NOT_SUPPORTED"):
            probe.validate_worker_relation(
                self.root,
                self.private,
                self.admission,
                "worker-A",
                json.dumps({"support_aliases": objective[:-1] + [next(alias for alias in probe.balanced.ALIASES if alias not in objective)]}),
            )

    def test_16_synthesis_receives_only_two_validated_artifacts(self) -> None:
        request = self.payloads["synthesis-AB"]
        assignment = json.loads(request["messages"][1]["content"])
        self.assertEqual(set(assignment), {"stage", "instruction", "parent_artifacts"})
        self.assertEqual(len(assignment["parent_artifacts"]), 2)
        self.assertEqual({item["worker_role"] for item in assignment["parent_artifacts"]}, {"parent-0", "parent-1"})

    def test_17_synthesis_forbidden_task_evidence_is_absent(self) -> None:
        text = probe.canonical_json_text(self.payloads["synthesis-AB"])
        for forbidden in ("public_examples", "opaque_candidates", "sealed_output", "task_id", "answer", "hidden", "intersection"):
            self.assertNotIn(forbidden, text)

    def test_18_rank_zero_freezes_before_private_mapping(self) -> None:
        ranking = list(probe.balanced.ALIASES[:3])
        transform, frozen = probe.parse_synthesis(
            self.root,
            json.dumps({"operator": "reconcile", "ranking": ranking}),
        )
        self.assertEqual(frozen.candidate_alias, ranking[0])
        self.assertEqual(frozen.selected_rank, 0)
        self.assertEqual(frozen.transform_artifact_commitment_consumed, transform["artifact_commitment"])

    def test_19_exact_three_requests_and_generations_are_enforced(self) -> None:
        self.assertEqual(probe.REQUEST_IDS, ("worker-A", "worker-B", "synthesis-AB"))
        self.assertEqual(scientific.MAXIMUM_TOTAL_MODEL_GENERATIONS, 3)
        self.assertEqual(scientific.MAXIMUM_MODEL_GENERATIONS_PER_REQUEST, 1)

    def test_20_duplicate_and_out_of_order_starts_fail(self) -> None:
        with self.assertRaisesRegex(probe.FiveSupportWorkerSynthesisError, "order"):
            probe.assert_can_start([], "worker-B")
        with self.assertRaisesRegex(probe.FiveSupportWorkerSynthesisError, "duplicate"):
            probe.assert_can_start(["worker-A"], "worker-A")

    def test_21_capture_occurs_before_parsing(self) -> None:
        execution = {name: None for name in scientific.CAPTURE_EXECUTION_FIELDS}
        execution.update({"content": "{}", "finish_reason": "stop", "http_status": 200, "event_count": 1})
        with tempfile.TemporaryDirectory() as temp:
            capture = scientific.capture_execution(
                Path(temp) / "capture.json",
                experiment_key=b"x" * 32,
                request_id="worker-A",
                model_request_sha256="A" * 64,
                execution=SimpleNamespace(**execution),
                raw_response_bytes=b"data: {}\n\n",
            )
            self.assertTrue(capture["captured_before_parsing"])

    def test_22_no_retry_can_occur_after_request_start(self) -> None:
        started = []
        for request_id in probe.REQUEST_IDS:
            probe.assert_can_start(started, request_id)
            started.append(request_id)
        with self.assertRaisesRegex(probe.FiveSupportWorkerSynthesisError, "ceiling"):
            probe.assert_can_start(started, "synthesis-AB")

    def test_23_zero_contact_capture_replay_is_supported(self) -> None:
        execution = {name: None for name in scientific.CAPTURE_EXECUTION_FIELDS}
        execution.update({"content": "{}", "finish_reason": "stop", "http_status": 200, "event_count": 1})
        with tempfile.TemporaryDirectory() as temp:
            capture = scientific.capture_execution(
                Path(temp) / "capture.json",
                experiment_key=b"y" * 32,
                request_id="worker-B",
                model_request_sha256="B" * 64,
                execution=SimpleNamespace(**execution),
                raw_response_bytes=b"data: {}\n\n",
            )
            replay = scientific.replay_capture(capture)
            self.assertEqual(replay.http_status, 200)
            self.assertNotIn("execute_request", inspect.getsource(scientific.replay_capture))

    def test_24_no_authority_or_runtime_state_exists(self) -> None:
        paths = probe.state_paths(REPOSITORY)
        self.assertFalse(paths["receipt"].exists())
        self.assertFalse(paths["run_root"].exists())
        self.assertEqual(self.artifact["execution_state"]["model_generations"], 0)
        self.assertFalse(self.artifact["execution_state"]["authority_created"])

    def test_25_exact_reconstruction_bindings_and_hashes_pass(self) -> None:
        observed = probe.validate_preregistration(REPOSITORY, self.model_path)
        self.assertEqual(observed, self.artifact)
        self.assertEqual(
            {request_id: probe.json_sha256(self.payloads[request_id]) for request_id in probe.REQUEST_IDS},
            self.artifact["request_set"]["request_sha256"],
        )
        self.assertEqual(
            probe._source_capture_commitment(self.root, "worker-A", self.artifact["request_set"]["request_sha256"]["worker-A"]),
            json.loads(self.payloads["synthesis-AB"]["messages"][1]["content"])["parent_artifacts"][0]["source_worker_capture_commitment_sha256"],
        )

    def test_26_exact_model_relations_reconstruct_frozen_synthesis_request(self) -> None:
        artifacts = {}
        for worker_id in probe.WORKER_IDS:
            objective = list(
                probe._objective_support_aliases(
                    self.private, self.admission, worker_id
                )
            )
            authored = list(reversed(objective))
            _preserved, normalized = probe.validate_worker_relation(
                self.root,
                self.private,
                self.admission,
                worker_id,
                json.dumps({"support_aliases": authored}),
            )
            artifacts[worker_id] = probe.build_worker_artifact(
                self.root,
                worker_id,
                authored,
                normalized,
                probe._source_capture_commitment(
                    self.root,
                    worker_id,
                    self.artifact["request_set"]["request_sha256"][worker_id],
                ),
            )
        self.assertEqual(
            probe.json_sha256(probe.build_synthesis_request(artifacts)),
            self.artifact["request_set"]["request_sha256"]["synthesis-AB"],
        )

    def test_27_authenticated_journal_verifies_and_tampering_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "journal.jsonl"
            writer = probe.JournalWriter(path, b"j" * 32)
            writer.append("authority-consumed")
            writer.append("request-started", request_id="worker-A")
            self.assertEqual(len(probe.verify_journal(path, b"j" * 32)), 2)
            data = path.read_bytes()
            path.write_bytes(data.replace(b"request-started", b"request-stopped"))
            with self.assertRaises(probe.FiveSupportWorkerSynthesisError):
                probe.verify_journal(path, b"j" * 32)


if __name__ == "__main__":
    unittest.main(verbosity=2)
