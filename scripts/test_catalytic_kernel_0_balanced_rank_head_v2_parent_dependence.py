#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration
import catalytic_kernel_0_balanced_rank_head_v2_parent_dependence as parent
import baseline_harness as harness


class FakeExecution:
    def __init__(self, content: str, *, prompt_tokens: int = 12) -> None:
        self.content = content
        self.reasoning_content = ""
        self.tool_calls: list[object] = []
        self.prompt_tokens = prompt_tokens
        self.cached_prompt_tokens = 0
        self.completion_tokens = 1
        self.generated_token_ids = [42]
        self.generated_token_count = 1
        self.completion_token_count_match = True
        self.generated_token_sha256 = parent.json_sha256([42])
        self.nonempty_token_array_event_count = 1
        self.empty_token_array_event_count = 0
        self.token_merge_modes = {"initial": 1}
        self.terminal_stop_evidence = {
            "observed": True,
            "stop": True,
            "stop_type": "eos",
            "stopping_word": "",
            "verbose_token_array_length": 1,
            "event_index": 1,
        }
        self.finish_reason = "stop"
        self.http_status = 200
        self.event_count = 2


class FakePool:
    class Lease:
        def __enter__(self) -> int:
            return 0

        def __exit__(self, *_args: object) -> None:
            return None

    def lease(self) -> "FakePool.Lease":
        return self.Lease()


class FakeAdapter:
    def __init__(
        self,
        responses: dict[str, str],
        *,
        cleanup_passed: bool = True,
        postflight_passed: bool = True,
    ) -> None:
        self.responses = responses
        self.cleanup_passed = cleanup_passed
        self.postflight_passed = postflight_passed
        self.request_ids: list[str] = []
        self.launches = 0
        self.cleanup_calls = 0

    def create_lease_pool(self, slots: int) -> FakePool:
        if slots != 1:
            raise AssertionError("parallelism changed")
        return FakePool()

    def launch_sidecar(self, **_kwargs: object) -> tuple[object, dict[str, object]]:
        self.launches += 1
        return object(), {"sidecar_pid": 123, "readiness_seconds": 0.1}

    def prompt_geometry(self, **_kwargs: object) -> dict[str, object]:
        return {"token_ids": list(range(12)), "public_root_terminal_token_index": 5}

    def boundary_custody(self, **_kwargs: object) -> dict[str, object]:
        return {"passed": True}

    def execute_request(self, *, request: object, **kwargs: object) -> FakeExecution:
        request_id = str(getattr(request, "request_id"))
        self.request_ids.append(request_id)
        recorder = kwargs.get("raw_line_recorder")
        if not callable(recorder):
            raise AssertionError("raw response recorder was not supplied")
        recorder(b"data: {}\n\n")
        recorder(b"data: [DONE]\n\n")
        return FakeExecution(self.responses[request_id])

    def cleanup(self, **_kwargs: object) -> dict[str, object]:
        self.cleanup_calls += 1
        return {
            "passed": self.cleanup_passed,
            "port_free": self.cleanup_passed,
            "stable_preserved": self.cleanup_passed,
        }

    def postflight(self, **_kwargs: object) -> dict[str, object]:
        return {"passed": self.postflight_passed}


class ParentDependenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary.name).resolve()
        (self.repository / "state").mkdir()
        (self.repository / ".gitignore").write_text(
            "/state/catalytic_kernel_0/\n"
            "/state/catalytic_kernel_0_authority.*.authority.consumed.json\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=self.repository,
            check=True,
            capture_output=True,
        )
        source_private = balanced.PrivateBinding.from_secret(
            b"P" * 32,
            balanced.BINDING_2,
        )
        spec = integration.run_spec(parent.SOURCE_RUN_ID)
        private = integration.runtime_private_from_source(source_private, spec)
        self.source_runtime = integration.RankHeadV2Runtime(
            repository=self.repository,
            spec=spec,
            private=private,
            run_design={"test": True},
        )
        aliases = list(balanced.ALIASES[:3])
        self.branch_a = self.source_runtime.normalize_branch("branch-a", aliases)
        self.branch_b = self.source_runtime.normalize_branch("branch-b", aliases)
        original_verify_receipt = parent.verify_authority_receipt

        def verify_receipt_fixture(
            repository: Path,
            *,
            require_current_static: bool = True,
        ) -> dict[str, object]:
            if parent.receipt_path(repository).is_file():
                return original_verify_receipt(
                    repository,
                    require_current_static=require_current_static,
                )
            return {
                "authority_receipt_sha256": "9" * 64,
                "consumed": True,
            }

        self.source_patches = (
            mock.patch.object(parent, "_source_runtime", return_value=self.source_runtime),
            mock.patch.object(
                parent,
                "_source_parent_artifacts",
                return_value=(self.branch_a, self.branch_b),
            ),
            mock.patch.object(
                parent,
                "verify_authority_receipt",
                side_effect=verify_receipt_fixture,
            ),
            mock.patch.object(
                parent,
                "verify_source_evidence",
                return_value={
                    "source_hashes": {"archive": "A" * 64},
                    "source_publication": {"record_sha256": "B" * 64},
                    "experiment_run_key_commitment": "C" * 64,
                },
            ),
        )
        for patcher in self.source_patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.source_patches):
            patcher.stop()
        self.temporary.cleanup()

    def journal_path(self) -> Path:
        return parent.state_paths(self.repository)["journal"]

    def start_journal(self) -> Path:
        path = self.journal_path()
        parent.append_journal_event(path, "prepared", facts={"manifest_sha256": "A" * 64})
        parent.append_journal_event(
            path,
            "authority-consumed",
            facts={"authority_receipt_sha256": "B" * 64},
        )
        return path

    def start_arm(self, path: Path, arm_id: str) -> None:
        parent.append_journal_event(
            path,
            "request-started",
            arm_id=arm_id,
            facts={
                "model_request_sha256": "C" * 64,
                "generation_ordinal": parent.ARM_IDS.index(arm_id) + 1,
                "maximum_generations_for_arm": 1,
                "rendered_prompt_tokens": 12,
            },
        )

    def capture_arm(self, path: Path, arm_id: str, capture_sha: str = "D" * 64) -> None:
        parent.append_journal_event(
            path,
            "response-captured",
            arm_id=arm_id,
            facts={
                "capture_sha256": capture_sha,
                "captured_before_parsing": True,
            },
        )
        parent.append_journal_event(
            path,
            "request-custody-observed",
            arm_id=arm_id,
            facts={"passed": True, "custody_sha256": "8" * 64},
        )

    def adjudicate_arm(self, path: Path, arm_id: str) -> None:
        parent.append_journal_event(
            path,
            "adjudicated",
            arm_id=arm_id,
            facts={
                "arm_id": arm_id,
                "status": "adjudicated",
                "classification": str(parent.ARM_BY_ID[arm_id]["supported_classification"]),
                "selection_frozen_before_private_mapping": True,
                "private_mapping_consulted_before_selection": False,
            },
        )

    def finalize(self, path: Path, *, passed: bool = True) -> None:
        cleanup = {"passed": passed, "request_custody_passed": passed}
        postflight = {"passed": passed}
        parent.append_journal_event(
            path,
            "finalization-observed",
            facts=parent._finalization_facts(cleanup, postflight),
        )

    def valid_transform_response(self, *, own_head: bool = True) -> str:
        own = self.source_runtime.private.internal_to_alias[
            balanced.EXPECTED_FULL_SUPPORT[0]
        ]
        head = own if own_head else next(
            alias for alias in balanced.ALIASES if alias != own
        )
        ranking = [head] + [
            alias for alias in balanced.ALIASES if alias != head
        ][:2]
        return json.dumps(
            {"operator": "reconcile", "ranking": ranking},
            separators=(",", ":"),
        )

    def captured_arm(
        self,
        path: Path,
        arm_id: str,
        content: str,
        *,
        custody: bool = True,
    ) -> dict[str, object]:
        self.start_arm(path, arm_id)
        capture = parent.capture_execution(
            parent.state_paths(self.repository)[f"capture-{arm_id}"],
            arm_id=arm_id,
            model_request_sha256="C" * 64,
            execution=FakeExecution(content),
            raw_response_bytes=b"data: {}\n\n",
        )
        parent.append_journal_event(
            path,
            "response-captured",
            arm_id=arm_id,
            facts={
                "capture_sha256": capture["capture_sha256"],
                "captured_before_parsing": True,
            },
        )
        if custody:
            parent.append_journal_event(
                path,
                "request-custody-observed",
                arm_id=arm_id,
                facts={"passed": True, "custody_sha256": "8" * 64},
            )
        return capture

    def complete_journal(self) -> Path:
        path = self.start_journal()
        for arm_id in parent.ARM_IDS:
            self.start_arm(path, arm_id)
            self.capture_arm(path, arm_id)
        self.finalize(path)
        for arm_id in parent.ARM_IDS:
            self.adjudicate_arm(path, arm_id)
        parent.append_journal_event(
            path,
            "terminal-written",
            facts={"result_sha256": "E" * 64, "closure_sha256": "F" * 64},
        )
        return path

    def commit_repair_fixture(self, label: str, *, initialize: bool = False) -> str:
        controller = self.repository / (
            "scripts/catalytic_kernel_0_balanced_rank_head_v2_parent_dependence.py"
        )
        if initialize:
            for relative in parent.REPAIRABLE_CONTROLLER_PATHS:
                path = self.repository / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"initial:{relative}\n", encoding="utf-8")
        controller.parent.mkdir(parents=True, exist_ok=True)
        controller.write_text(f"controller:{label}\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "-A"],
            cwd=self.repository,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Neo Test",
                "-c",
                "user.email=neo@example.invalid",
                "commit",
                "--quiet",
                "-m",
                label,
            ],
            cwd=self.repository,
            check=True,
            capture_output=True,
        )
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def repair_policy_fixture(self) -> tuple[dict[str, object], dict[str, str], tuple[object, ...]]:
        original = self.commit_repair_fixture("commit-a", initialize=True)
        request_hashes = {
            arm_id: parent.json_sha256(parent.build_arm_request(self.repository, arm_id))
            for arm_id in parent.ARM_IDS
        }
        frozen = {"sha256": "A" * 64}
        initial_controller = parent._file_binding(
            self.repository,
            ("scripts/catalytic_kernel_0_balanced_rank_head_v2_parent_dependence.py",),
        )
        implementation_body = {
            "frozen_scientific_execution": frozen,
            "repairable_controller": initial_controller,
        }
        implementation = {
            **implementation_body,
            "sha256": parent.json_sha256(implementation_body),
        }
        preregistration = {
            "artifact_sha256": "B" * 64,
            "document_sha256": "C" * 64,
            "implementation_binding_sha256": implementation["sha256"],
            "frozen_scientific_execution_binding_sha256": frozen["sha256"],
            "repairable_controller_initial_binding_sha256": initial_controller["sha256"],
        }

        def current_controller(repository: Path) -> dict[str, object]:
            return parent._file_binding(
                repository,
                (
                    "scripts/catalytic_kernel_0_balanced_rank_head_v2_parent_dependence.py",
                ),
            )

        patches = (
            mock.patch.object(parent, "_frozen_scientific_binding", return_value=frozen),
            mock.patch.object(
                parent,
                "_repairable_controller_binding",
                side_effect=current_controller,
            ),
            mock.patch.object(
                parent,
                "_implementation_binding",
                return_value=implementation,
            ),
            mock.patch.object(
                parent,
                "validate_preregistration",
                return_value=preregistration,
            ),
            mock.patch.object(
                parent,
                "request_isolation_report",
                return_value={"arm_request_sha256": request_hashes},
            ),
            mock.patch.object(
                parent.scientific,
                "EXPECTED_ARM_REQUEST_SHA256",
                request_hashes,
            ),
        )
        for patcher in patches:
            patcher.start()
        authority = parent._expected_authority_body(
            self.repository,
            {
                "authority_id_sha256": "D" * 64,
                "authorized_commit": original,
            },
        )
        return authority, request_hashes, patches

    def initialize_consumed_repair_evidence(
        self,
        authority: dict[str, object],
        request_hashes: dict[str, str],
    ) -> tuple[Path, dict[str, bytes]]:
        paths = parent.state_paths(self.repository)
        receipt = parent.canonical_json_bytes(
            parent._receipt_document(self.repository, authority)
        )
        parent._exclusive_write(paths["receipt"], receipt)
        journal = paths["journal"]
        parent.append_journal_event(
            journal,
            "prepared",
            facts={"manifest_sha256": "E" * 64},
        )
        parent.append_journal_event(
            journal,
            "authority-consumed",
            facts={"authority_receipt_sha256": parent.sha256_bytes(receipt)},
        )
        first = parent.ARM_IDS[0]
        parent.append_journal_event(
            journal,
            "request-started",
            arm_id=first,
            facts={
                "model_request_sha256": request_hashes[first],
                "generation_ordinal": 1,
                "maximum_generations_for_arm": 1,
                "rendered_prompt_tokens": 12,
            },
        )
        capture = parent.capture_execution(
            paths[f"capture-{first}"],
            arm_id=first,
            model_request_sha256=request_hashes[first],
            execution=FakeExecution(self.valid_transform_response()),
            raw_response_bytes=b"data: {}\n\n",
        )
        parent.append_journal_event(
            journal,
            "response-captured",
            arm_id=first,
            facts={
                "capture_sha256": capture["capture_sha256"],
                "captured_before_parsing": True,
            },
        )
        parent.append_journal_event(
            journal,
            "request-custody-observed",
            arm_id=first,
            facts={"passed": True, "custody_sha256": "F" * 64},
        )
        return journal, {
            "receipt": paths["receipt"].read_bytes(),
            first: paths[f"capture-{first}"].read_bytes(),
        }

    def test_exact_two_arm_projection_and_no_smuggle(self) -> None:
        report = parent.request_isolation_report(self.repository)
        self.assertEqual(tuple(report["arm_request_sha256"]), parent.ARM_IDS)
        self.assertTrue(report["execution_order_independent"])
        self.assertFalse(report["cross_arm_response_visible"])
        self.assertFalse(report["model_authored_restore_required"])
        for arm_id in parent.ARM_IDS:
            assignment = parent.arm_assignment(self.repository, arm_id)
            deleted_index = parent.ARM_IDS.index(arm_id)
            receipt = assignment["parent_artifacts"][deleted_index]
            retained = assignment["parent_artifacts"][1 - deleted_index]
            self.assertEqual(set(receipt), balanced.DELETION_RECEIPT_FIELDS)
            self.assertEqual(retained, (self.branch_a, self.branch_b)[1 - deleted_index])

    def test_arm_projection_rejects_any_extra_deleted_parent_field(self) -> None:
        assignment = parent.arm_assignment(self.repository, parent.ARM_IDS[0])
        assignment["parent_artifacts"][0]["support_aliases"] = []
        with self.assertRaisesRegex(parent.ParentDependenceError, "exact source projection"):
            parent._validate_arm_assignment(self.repository, parent.ARM_IDS[0], assignment)

    def test_arm_payloads_are_order_independent_with_distinct_fixed_seeds(self) -> None:
        first = [parent.build_arm_request(self.repository, arm) for arm in parent.ARM_IDS]
        second = {
            arm: parent.build_arm_request(self.repository, arm)
            for arm in reversed(parent.ARM_IDS)
        }
        self.assertEqual(
            [parent.json_sha256(item) for item in first],
            [parent.json_sha256(second[arm]) for arm in parent.ARM_IDS],
        )
        self.assertNotEqual(first[0]["seed"], first[1]["seed"])

    def test_public_output_scanner_rejects_correspondence_and_rankings(self) -> None:
        for value in (
            {"candidate_alias": "redacted"},
            {"ranking": []},
            {"private_root": "redacted"},
            {"raw_authority_id": "redacted"},
        ):
            with self.assertRaises(parent.ParentDependenceError):
                parent._assert_public_no_smuggle(value)

    def test_authority_schema_accepts_identity_data_without_run_specific_const(self) -> None:
        schema = parent.authority_object_schema()
        identity = schema["properties"]["experiment_id"]
        self.assertNotIn("const", identity)
        self.assertNotIn("enum", identity)
        self.assertEqual(parent.AUTHORITY_SCHEMA_VERSION, "rank-head-v2-parent-dependence-authority-v1")
        self.assertEqual(parent.authority_id_sha256("A" * 64), parent.authority_id_sha256("a" * 64))

    def test_capture_is_exclusive_and_replayable_before_parse(self) -> None:
        path = self.repository / "captures" / "response.json"
        capture = parent.capture_execution(
            path,
            arm_id=parent.ARM_IDS[0],
            model_request_sha256="A" * 64,
            execution=FakeExecution("not-json"),
            raw_response_bytes=b"data: {}\n\n",
        )
        self.assertTrue(capture["captured_before_parsing"])
        self.assertEqual(capture["raw_response_capture"]["byte_size"], len(b"data: {}\n\n"))
        self.assertEqual(parent.replay_capture(capture).content, "not-json")
        with self.assertRaises(FileExistsError):
            parent.capture_execution(
                path,
                arm_id=parent.ARM_IDS[0],
                model_request_sha256="A" * 64,
                execution=FakeExecution("not-json"),
                raw_response_bytes=b"data: {}\n\n",
            )

    def test_raw_sse_line_is_recorded_before_transport_parse(self) -> None:
        raw = b"data: {not-json}\n\n"
        recorded: list[bytes] = []
        with self.assertRaises(harness.HarnessError):
            list(harness.iter_sse([raw], raw_line_recorder=recorded.append))
        self.assertEqual(recorded, [raw])

    def test_capture_tamper_or_request_mismatch_is_rejected(self) -> None:
        paths = parent.state_paths(self.repository)
        journal = self.start_journal()
        arm_id = parent.ARM_IDS[0]
        self.start_arm(journal, arm_id)
        path = paths[f"capture-{arm_id}"]
        captured = parent.capture_execution(
            path,
            arm_id=arm_id,
            model_request_sha256="C" * 64,
            execution=FakeExecution("{}"),
            raw_response_bytes=b"data: {}\n\n",
        )
        with self.assertRaises(parent.ParentDependenceError):
            parent.verify_capture(
                path,
                arm_id=arm_id,
                model_request_sha256="B" * 64,
            )
        self.capture_arm(journal, arm_id, captured["capture_sha256"])
        body = json.loads(path.read_bytes())
        body["execution"]["content"] = "changed"
        path.write_bytes(parent.canonical_json_bytes(body))
        with self.assertRaisesRegex(parent.ParentDependenceError, "authentication"):
            parent._recover_request_prefix(self.repository, paths, arm_id)

    def test_journal_complete_hash_chain_and_every_required_transition(self) -> None:
        path = self.complete_journal()
        parent.append_journal_event(
            path,
            "archived",
            facts={"archive_sha256": "9" * 64},
        )
        events = parent.read_journal(path)
        self.assertEqual(
            [event["state"] for event in events],
            [
                "prepared",
                "authority-consumed",
                "request-started",
                "response-captured",
                "request-custody-observed",
                "request-started",
                "response-captured",
                "request-custody-observed",
                "finalization-observed",
                "adjudicated",
                "adjudicated",
                "terminal-written",
                "archived",
            ],
        )
        self.assertEqual(events[0]["previous_event_sha256"], parent.GENESIS_HASH)

    def test_journal_duplicate_generation_is_rejected(self) -> None:
        path = self.start_journal()
        self.start_arm(path, parent.ARM_IDS[0])
        with self.assertRaisesRegex(parent.ParentDependenceError, "duplicate model generation"):
            self.start_arm(path, parent.ARM_IDS[0])

    def test_journal_rejects_torn_corrupt_reordered_and_skipped_records(self) -> None:
        path = self.start_journal()
        original = path.read_bytes()
        for damaged in (
            original[:-1],
            original.replace(b'"sequence":2', b'"sequence":3', 1),
            b"\n".join(reversed(original.splitlines())) + b"\n",
        ):
            with self.subTest(damaged=hashlib.sha256(damaged).hexdigest()):
                with self.assertRaises(parent.ParentDependenceError):
                    parent.verify_journal_bytes(damaged, repository=self.repository)

    def test_coordinated_unkeyed_journal_rewrite_is_rejected(self) -> None:
        path = self.start_journal()
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        events[0]["facts"]["manifest_sha256"] = "9" * 64
        previous = parent.GENESIS_HASH
        for event in events:
            event["previous_event_sha256"] = previous
            body = {
                key: value
                for key, value in event.items()
                if key not in {"event_sha256", "event_hmac_sha256"}
            }
            event["event_sha256"] = parent.json_sha256(body)
            previous = event["event_sha256"]
        rewritten = b"".join(parent.canonical_json_bytes(event) + b"\n" for event in events)
        with self.assertRaisesRegex(parent.ParentDependenceError, "authentication"):
            parent.verify_journal_bytes(rewritten, repository=self.repository)

    def test_started_without_capture_becomes_inconclusive_and_never_restarts(self) -> None:
        path = self.start_journal()
        self.start_arm(path, parent.ARM_IDS[0])
        parent._recover_request_prefix(
            self.repository,
            parent.state_paths(self.repository),
            parent.ARM_IDS[0],
        )
        event = parent._event_for(parent.read_journal(path), "adjudicated", parent.ARM_IDS[0])
        self.assertEqual(event["facts"]["classification"], parent.INCONCLUSIVE_CLASSIFICATION)
        with self.assertRaises(parent.ParentDependenceError):
            self.start_arm(path, parent.ARM_IDS[0])

    def test_capture_file_without_event_is_recovered_without_model_contact(self) -> None:
        path = self.start_journal()
        arm_id = parent.ARM_IDS[0]
        self.start_arm(path, arm_id)
        capture_path = parent.state_paths(self.repository)[f"capture-{arm_id}"]
        parent.capture_execution(
            capture_path,
            arm_id=arm_id,
            model_request_sha256="C" * 64,
            execution=FakeExecution("{}"),
            raw_response_bytes=b"data: {}\n\n",
        )
        parent._recover_request_prefix(
            self.repository,
            parent.state_paths(self.repository),
            arm_id,
        )
        events = parent.read_journal(path)
        self.assertIsNotNone(parent._event_for(events, "response-captured", arm_id))

    def test_both_heads_freeze_before_either_private_mapping(self) -> None:
        path = self.start_journal()
        paths = parent.state_paths(self.repository)
        for arm_id in parent.ARM_IDS:
            self.start_arm(path, arm_id)
            capture = parent.capture_execution(
                paths[f"capture-{arm_id}"],
                arm_id=arm_id,
                model_request_sha256="C" * 64,
                execution=FakeExecution("{}"),
                raw_response_bytes=b"data: {}\n\n",
            )
            self.capture_arm(path, arm_id, capture["capture_sha256"])
        self.finalize(path)
        order: list[str] = []

        def freeze(_repository: Path, arm_id: str, *_args: object):
            order.append("freeze:" + arm_id)
            return object(), {}, object(), {
                "http_status": 200,
                "prompt_tokens": 12,
                "cached_prompt_tokens": 0,
                "fresh_prompt_tokens": 12,
                "completion_tokens": 1,
                "finish_reason": "stop",
                "generated_token_evidence_mode": "exact-count-match",
            }

        def adjudicate(_runtime: object, _transform: object, _frozen: object, arm_id: str):
            order.append("map:" + arm_id)
            return {
                "arm_id": arm_id,
                "status": "adjudicated",
                "classification": parent.ARM_BY_ID[arm_id]["supported_classification"],
                "selection_frozen_before_private_mapping": True,
                "private_mapping_consulted_before_selection": False,
            }

        with mock.patch.object(parent, "_freeze_captured_arm", side_effect=freeze), mock.patch.object(
            parent, "_adjudicate_frozen_arm", side_effect=adjudicate
        ):
            parent._freeze_then_adjudicate_all(self.repository, paths)
        self.assertEqual(
            order,
            [
                "freeze:delete-parent-0",
                "freeze:delete-parent-1",
                "map:delete-parent-0",
                "map:delete-parent-1",
            ],
        )

    def test_known_captured_response_invalidity_prevents_all_private_mapping(self) -> None:
        path = self.start_journal()
        paths = parent.state_paths(self.repository)
        for arm_id in parent.ARM_IDS:
            self.start_arm(path, arm_id)
            capture = parent.capture_execution(
                paths[f"capture-{arm_id}"],
                arm_id=arm_id,
                model_request_sha256="C" * 64,
                execution=FakeExecution("{}"),
                raw_response_bytes=b"data: {}\n\n",
            )
            self.capture_arm(path, arm_id, capture["capture_sha256"])
        self.finalize(path)
        mapped: list[str] = []

        def freeze(_repository: Path, arm_id: str, *_args: object):
            if arm_id == parent.ARM_IDS[0]:
                raise parent.CapturedResponseInvalidError(
                    "synthetic captured-response invalidity"
                )
            return object(), {}, object(), {}

        def adjudicate(*_args: object):
            mapped.append("mapped")
            raise AssertionError("private mapping must not run")

        with mock.patch.object(parent, "_freeze_captured_arm", side_effect=freeze), mock.patch.object(
            parent, "_adjudicate_frozen_arm", side_effect=adjudicate
        ):
            parent._freeze_then_adjudicate_all(self.repository, paths)
        self.assertEqual(mapped, [])
        outcomes = parent._journal_adjudications(parent.read_journal(path))
        self.assertEqual(
            {facts["classification"] for facts in outcomes.values()},
            {parent.INCONCLUSIVE_CLASSIFICATION},
        )

    def test_unexpected_controller_failure_preserves_captures_without_adjudication(self) -> None:
        path = self.start_journal()
        before: dict[str, bytes] = {}
        for arm_id in parent.ARM_IDS:
            self.captured_arm(path, arm_id, self.valid_transform_response())
            capture_path = parent.state_paths(self.repository)[f"capture-{arm_id}"]
            before[arm_id] = capture_path.read_bytes()
        self.finalize(path)
        with mock.patch.object(
            parent,
            "_freeze_captured_arm",
            side_effect=AssertionError("synthetic controller defect"),
        ):
            with self.assertRaisesRegex(AssertionError, "synthetic controller defect"):
                parent._freeze_then_adjudicate_all(
                    self.repository,
                    parent.state_paths(self.repository),
                )
        events = parent.read_journal(path)
        self.assertEqual(parent._journal_adjudications(events), {})
        self.assertEqual(events[-1]["state"], "finalization-observed")
        for arm_id, expected in before.items():
            self.assertEqual(
                parent.state_paths(self.repository)[f"capture-{arm_id}"].read_bytes(),
                expected,
            )

    def test_repaired_controller_replays_same_captures_with_zero_model_calls(self) -> None:
        path = self.start_journal()
        before: dict[str, bytes] = {}
        for arm_id in parent.ARM_IDS:
            self.captured_arm(path, arm_id, self.valid_transform_response())
            capture_path = parent.state_paths(self.repository)[f"capture-{arm_id}"]
            before[arm_id] = capture_path.read_bytes()
        self.finalize(path)
        adapter = FakeAdapter({})
        parent._freeze_then_adjudicate_all(
            self.repository,
            parent.state_paths(self.repository),
        )
        self.assertEqual(adapter.request_ids, [])
        self.assertEqual(
            set(parent._journal_adjudications(parent.read_journal(path))),
            set(parent.ARM_IDS),
        )
        for arm_id, expected in before.items():
            self.assertEqual(
                parent.state_paths(self.repository)[f"capture-{arm_id}"].read_bytes(),
                expected,
            )

    def test_malformed_model_json_becomes_inconclusive(self) -> None:
        path = self.start_journal()
        self.captured_arm(path, parent.ARM_IDS[0], "{malformed")
        self.captured_arm(
            path,
            parent.ARM_IDS[1],
            self.valid_transform_response(),
        )
        self.finalize(path)
        parent._freeze_then_adjudicate_all(
            self.repository,
            parent.state_paths(self.repository),
        )
        outcomes = parent._journal_adjudications(parent.read_journal(path))
        self.assertEqual(
            {facts["classification"] for facts in outcomes.values()},
            {parent.INCONCLUSIVE_CLASSIFICATION},
        )

    def test_schema_invalid_transform_becomes_inconclusive(self) -> None:
        path = self.start_journal()
        invalid = json.dumps(
            {"operator": "invent", "ranking": list(balanced.ALIASES[:3])},
            separators=(",", ":"),
        )
        self.captured_arm(path, parent.ARM_IDS[0], invalid)
        self.captured_arm(
            path,
            parent.ARM_IDS[1],
            self.valid_transform_response(),
        )
        self.finalize(path)
        parent._freeze_then_adjudicate_all(
            self.repository,
            parent.state_paths(self.repository),
        )
        outcomes = parent._journal_adjudications(parent.read_journal(path))
        self.assertEqual(
            {facts["classification"] for facts in outcomes.values()},
            {parent.INCONCLUSIVE_CLASSIFICATION},
        )

    def test_authenticated_capture_corruption_becomes_inconclusive(self) -> None:
        path = self.start_journal()
        for arm_id in parent.ARM_IDS:
            self.captured_arm(path, arm_id, self.valid_transform_response())
        self.finalize(path)
        corrupted = parent.state_paths(self.repository)[
            f"capture-{parent.ARM_IDS[0]}"
        ]
        data = bytearray(corrupted.read_bytes())
        data[-1] ^= 1
        corrupted.write_bytes(bytes(data))
        parent._freeze_then_adjudicate_all(
            self.repository,
            parent.state_paths(self.repository),
        )
        outcomes = parent._journal_adjudications(parent.read_journal(path))
        self.assertEqual(
            {facts["classification"] for facts in outcomes.values()},
            {parent.INCONCLUSIVE_CLASSIFICATION},
        )

    def test_real_rank_head_scoring_supports_and_not_shown_outcomes(self) -> None:
        source = self.source_runtime
        own = source.private.internal_to_alias[balanced.EXPECTED_FULL_SUPPORT[0]]
        other = next(alias for alias in balanced.ALIASES if alias != own)
        for arm_id, head, expected in (
            (parent.ARM_IDS[0], own, parent.ARM_BY_ID[parent.ARM_IDS[0]]["not_shown_classification"]),
            (parent.ARM_IDS[1], other, parent.ARM_BY_ID[parent.ARM_IDS[1]]["supported_classification"]),
        ):
            runtime = parent._arm_runtime(self.repository, source, arm_id)
            ranking = [head] + [alias for alias in balanced.ALIASES if alias != head][:2]
            transform = runtime.normalize_transform("reconcile", ranking)
            frozen = parent.v2.freeze_rank_head_selection(runtime, transform)
            facts = parent._adjudicate_frozen_arm(runtime, transform, frozen, arm_id)
            self.assertEqual(facts["classification"], expected)
            self.assertTrue(facts["selection_frozen_before_private_mapping"])

    def test_one_shared_receipt_is_cryptographic_exclusive_and_raw_id_free(self) -> None:
        authority = {"authorized_commit": "1" * 40, "experiment_id": parent.EXPERIMENT_ID}
        raw = "A" * 64
        with mock.patch.object(parent, "validate_external_authority", return_value=None):
            evidence = parent.consume_authority_once(
                self.repository,
                authority,
                current_commit="1" * 40,
                expected_model_sha256=parent.MODEL_SHA256,
                expected_binary_sha256=parent.BINARY_SHA256,
            )
            self.assertTrue(evidence["consumed"])
            self.assertNotIn(raw, parent.receipt_path(self.repository).read_text(encoding="utf-8"))
            with self.assertRaises(parent.ParentDependenceError):
                parent.consume_authority_once(
                    self.repository,
                    authority,
                    current_commit="1" * 40,
                    expected_model_sha256=parent.MODEL_SHA256,
                    expected_binary_sha256=parent.BINARY_SHA256,
                )
        lock = self.repository / parent.STATE_ROOT / ".authority.lock"
        ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", "--", str(lock.relative_to(self.repository))],
            cwd=self.repository,
            check=False,
        )
        self.assertEqual(ignored.returncode, 0)

    def _terminal_archive_fixture(self) -> tuple[dict[str, Path], dict[str, object]]:
        paths = parent.state_paths(self.repository)
        authority = {"authorized_commit": "1" * 40, "experiment_id": parent.EXPERIMENT_ID}
        parent._exclusive_write(
            paths["receipt"],
            parent.canonical_json_bytes(parent._receipt_document(self.repository, authority)),
        )
        parent._write_or_require_identical(paths["manifest"], b"{}\n")
        path = self.start_journal()
        for arm_id in parent.ARM_IDS:
            self.start_arm(path, arm_id)
            capture = parent.capture_execution(
                paths[f"capture-{arm_id}"],
                arm_id=arm_id,
                model_request_sha256="C" * 64,
                execution=FakeExecution("{}"),
                raw_response_bytes=b"data: {}\n\n",
            )
            self.capture_arm(path, arm_id, capture["capture_sha256"])
        self.finalize(path)
        for arm_id in parent.ARM_IDS:
            self.adjudicate_arm(path, arm_id)
        result = {"experiment_id": parent.EXPERIMENT_ID, "status": "complete"}
        result_data = json.dumps(result, sort_keys=True, indent=2).encode() + b"\n"
        parent._write_or_require_identical(paths["result"], result_data)
        closure = {
            "experiment_id": parent.EXPERIMENT_ID,
            "result_sha256": parent.sha256_bytes(result_data),
            "manifest_sha256": parent.sha256_bytes(paths["manifest"].read_bytes()),
            "authority_receipt_sha256": parent.sha256_bytes(paths["receipt"].read_bytes()),
        }
        closure_data = json.dumps(closure, sort_keys=True, indent=2).encode() + b"\n"
        parent._write_or_require_identical(paths["closure"], closure_data)
        parent.append_journal_event(
            path,
            "terminal-written",
            facts={
                "result_sha256": parent.sha256_bytes(result_data),
                "closure_sha256": parent.sha256_bytes(closure_data),
            },
        )
        return paths, authority

    def test_content_addressed_archive_verifies_and_restores_exact_bytes(self) -> None:
        paths, _authority = self._terminal_archive_fixture()
        with mock.patch.object(parent, "validate_external_authority", return_value=None):
            archived = parent.archive_terminal_evidence(self.repository)
            archive = (
                self.repository
                / parent.ARCHIVE_ROOT
                / parent.EXPERIMENT_ID
                / archived["bundle_sha256"]
            )
            self.assertEqual(parent.verify_archive(self.repository, archive)["bundle_sha256"], archived["bundle_sha256"])
            for destination in parent._archive_source_files(paths).values():
                destination.unlink()
            restored = parent.restore_archive(self.repository, archive)
            self.assertEqual(len(restored["restored"]), 7)
            self.assertEqual(parent.read_journal(paths["journal"])[-1]["state"], "terminal-written")

    def test_archive_rejects_tamper_and_restore_refuses_differing_destination(self) -> None:
        paths, _authority = self._terminal_archive_fixture()
        with mock.patch.object(parent, "validate_external_authority", return_value=None):
            archived = parent.archive_terminal_evidence(self.repository)
            archive = self.repository / parent.ARCHIVE_ROOT / parent.EXPERIMENT_ID / archived["bundle_sha256"]
            paths["result"].write_bytes(b"different\n")
            with self.assertRaisesRegex(parent.ParentDependenceError, "differing evidence"):
                parent.restore_archive(self.repository, archive)
            archived_result = archive / "result.json"
            archived_result.write_bytes(b"tampered\n")
            with self.assertRaises(parent.ParentDependenceError):
                parent.verify_archive(self.repository, archive)

    def test_no_capture_inconclusive_terminal_archives_without_placeholder(self) -> None:
        paths = parent.state_paths(self.repository)
        authority = {"authorized_commit": "1" * 40, "experiment_id": parent.EXPERIMENT_ID}
        parent._exclusive_write(
            paths["receipt"],
            parent.canonical_json_bytes(parent._receipt_document(self.repository, authority)),
        )
        parent._write_or_require_identical(paths["manifest"], b"{}\n")
        journal = self.start_journal()
        first, second = parent.ARM_IDS
        self.start_arm(journal, first)
        parent._recover_request_prefix(self.repository, paths, first)
        self.start_arm(journal, second)
        capture = parent.capture_execution(
            paths[f"capture-{second}"],
            arm_id=second,
            model_request_sha256="C" * 64,
            execution=FakeExecution("{}"),
            raw_response_bytes=b"data: {}\n\n",
        )
        self.capture_arm(journal, second, capture["capture_sha256"])
        self.finalize(journal)
        self.adjudicate_arm(journal, second)
        result = parent._write_terminal(
            self.repository,
            paths,
            receipt={},
            cleanup={"passed": True, "request_custody_passed": True},
            postflight={"passed": True},
        )
        self.assertEqual(result["status"], "inconclusive")
        with mock.patch.object(parent, "validate_external_authority", return_value=None):
            archived = parent.archive_terminal_evidence(self.repository)
            names = {item["name"] for item in archived["bundle"]["files"]}
        self.assertNotIn(f"capture-{first}", names)
        self.assertIn(f"capture-{second}", names)
        self.assertEqual(len(names), 6)

    def test_failed_cleanup_or_postflight_forces_terminal_inconclusive(self) -> None:
        paths = parent.state_paths(self.repository)
        parent._exclusive_write(paths["receipt"], b"{}\n")
        parent._write_or_require_identical(paths["manifest"], b"{}\n")
        journal = self.start_journal()
        for arm_id in parent.ARM_IDS:
            self.start_arm(journal, arm_id)
            capture = parent.capture_execution(
                paths[f"capture-{arm_id}"],
                arm_id=arm_id,
                model_request_sha256="C" * 64,
                execution=FakeExecution("{}"),
                raw_response_bytes=b"data: {}\n\n",
            )
            self.capture_arm(journal, arm_id, capture["capture_sha256"])
        self.finalize(journal, passed=False)
        for arm_id in parent.ARM_IDS:
            parent.append_journal_event(
                journal,
                "adjudicated",
                arm_id=arm_id,
                facts=parent._inconclusive_facts(
                    arm_id,
                    "durable-finalization-custody-gate-failed",
                ),
            )
        result = parent._write_terminal(
            self.repository,
            paths,
            receipt={},
            cleanup={"passed": False, "request_custody_passed": False},
            postflight={"passed": False},
        )
        self.assertEqual(result["status"], "inconclusive")
        self.assertFalse(result["custody_gates_passed"])

    def test_both_captures_restart_reconciles_and_adjudicates_without_model_calls(self) -> None:
        paths = parent.state_paths(self.repository)
        journal = self.start_journal()
        for arm_id in parent.ARM_IDS:
            self.captured_arm(
                journal,
                arm_id,
                self.valid_transform_response(),
            )
        adapter = FakeAdapter({arm_id: "{}" for arm_id in parent.ARM_IDS})
        cleanup, postflight = parent._execute_unstarted_arms(
            self.repository,
            paths,
            live=adapter,
            full_preflight={},
        )
        self.assertTrue(cleanup["passed"])
        self.assertTrue(postflight["passed"])
        self.assertEqual(cleanup["mode"], "restart-custody-reconciliation")
        self.assertEqual(adapter.launches, 0)
        self.assertEqual(adapter.request_ids, [])
        parent.append_journal_event(
            journal,
            "finalization-observed",
            facts=parent._finalization_facts(cleanup, postflight),
        )
        parent._freeze_then_adjudicate_all(self.repository, paths)
        outcomes = parent._journal_adjudications(parent.read_journal(journal))
        self.assertEqual(
            set(outcomes),
            set(parent.ARM_IDS),
        )

    def test_missing_request_custody_is_restart_reconciled_before_arm_two(self) -> None:
        paths = parent.state_paths(self.repository)
        journal = self.start_journal()
        first, second = parent.ARM_IDS
        self.start_arm(journal, first)
        capture = parent.capture_execution(
            paths[f"capture-{first}"],
            arm_id=first,
            model_request_sha256="C" * 64,
            execution=FakeExecution("{}"),
            raw_response_bytes=b"data: {}\n\n",
        )
        parent.append_journal_event(
            journal,
            "response-captured",
            arm_id=first,
            facts={
                "capture_sha256": capture["capture_sha256"],
                "captured_before_parsing": True,
            },
        )
        adapter = FakeAdapter({second: "{}"})
        cleanup, postflight = parent._execute_unstarted_arms(
            self.repository,
            paths,
            live=adapter,
            full_preflight={},
        )
        self.assertEqual(adapter.request_ids, [second])
        self.assertTrue(cleanup["request_custody_passed"])
        custody = parent._event_for(
            parent.read_journal(journal),
            "request-custody-observed",
            first,
        )
        self.assertEqual(custody["facts"]["mode"], "restart-reconciled")
        self.assertRegex(
            custody["facts"]["reconciliation_commitment"],
            r"^[0-9A-F]{64}$",
        )
        parent.append_journal_event(
            journal,
            "finalization-observed",
            facts=parent._finalization_facts(cleanup, postflight),
        )
        parent._freeze_then_adjudicate_all(self.repository, paths)
        outcomes = parent._journal_adjudications(parent.read_journal(journal))
        self.assertEqual(
            set(outcomes),
            set(parent.ARM_IDS),
        )

    def test_crash_after_arm_one_capture_executes_only_arm_two(self) -> None:
        paths = parent.state_paths(self.repository)
        journal = self.start_journal()
        first, second = parent.ARM_IDS
        self.captured_arm(
            journal,
            first,
            self.valid_transform_response(),
        )
        adapter = FakeAdapter({second: self.valid_transform_response()})
        cleanup, postflight = parent._execute_unstarted_arms(
            self.repository,
            paths,
            live=adapter,
            full_preflight={},
        )
        self.assertTrue(cleanup["passed"])
        self.assertTrue(postflight["passed"])
        self.assertEqual(adapter.request_ids, [second])
        self.assertEqual(adapter.launches, 1)

    def test_capture_without_event_is_reconciled_without_model_regeneration(self) -> None:
        paths = parent.state_paths(self.repository)
        journal = self.start_journal()
        first, second = parent.ARM_IDS
        self.start_arm(journal, first)
        capture = parent.capture_execution(
            paths[f"capture-{first}"],
            arm_id=first,
            model_request_sha256="C" * 64,
            execution=FakeExecution(self.valid_transform_response()),
            raw_response_bytes=b"data: {}\n\n",
        )
        adapter = FakeAdapter({second: self.valid_transform_response()})
        cleanup, postflight = parent._execute_unstarted_arms(
            self.repository,
            paths,
            live=adapter,
            full_preflight={},
        )
        self.assertTrue(cleanup["passed"])
        self.assertTrue(postflight["passed"])
        self.assertEqual(adapter.request_ids, [second])
        captured = parent._event_for(
            parent.read_journal(journal), "response-captured", first
        )
        self.assertEqual(captured["facts"]["capture_sha256"], capture["capture_sha256"])
        custody = parent._event_for(
            parent.read_journal(journal), "request-custody-observed", first
        )
        self.assertEqual(custody["facts"]["mode"], "restart-reconciled")

    def test_failed_restart_custody_is_inconclusive_without_regeneration(self) -> None:
        paths = parent.state_paths(self.repository)
        journal = self.start_journal()
        for arm_id in parent.ARM_IDS:
            self.captured_arm(
                journal,
                arm_id,
                self.valid_transform_response(),
                custody=False,
            )
        adapter = FakeAdapter({}, cleanup_passed=False)
        cleanup, postflight = parent._execute_unstarted_arms(
            self.repository,
            paths,
            live=adapter,
            full_preflight={},
        )
        self.assertFalse(cleanup["passed"])
        self.assertTrue(postflight["passed"])
        self.assertEqual(adapter.request_ids, [])
        self.assertEqual(adapter.launches, 0)
        parent.append_journal_event(
            journal,
            "finalization-observed",
            facts=parent._finalization_facts(cleanup, postflight),
        )
        parent._freeze_then_adjudicate_all(self.repository, paths)
        outcomes = parent._journal_adjudications(parent.read_journal(journal))
        self.assertEqual(
            {facts["classification"] for facts in outcomes.values()},
            {parent.INCONCLUSIVE_CLASSIFICATION},
        )

    def test_repeated_resume_never_generates_an_arm_twice(self) -> None:
        paths = parent.state_paths(self.repository)
        journal = self.start_journal()
        first, second = parent.ARM_IDS
        self.captured_arm(
            journal,
            first,
            self.valid_transform_response(),
        )
        adapter = FakeAdapter({second: self.valid_transform_response()})
        parent._execute_unstarted_arms(
            self.repository,
            paths,
            live=adapter,
            full_preflight={},
        )
        parent._execute_unstarted_arms(
            self.repository,
            paths,
            live=adapter,
            full_preflight={},
        )
        self.assertEqual(adapter.request_ids, [second])
        events = parent.read_journal(journal)
        for arm_id in parent.ARM_IDS:
            self.assertEqual(
                sum(
                    event["state"] == "request-started"
                    and event.get("arm_id") == arm_id
                    for event in events
                ),
                1,
            )

    def test_execute_surface_uses_one_generation_per_arm_and_one_sidecar(self) -> None:
        paths = parent.state_paths(self.repository)
        self.start_journal()
        own = self.source_runtime.private.internal_to_alias[balanced.EXPECTED_FULL_SUPPORT[0]]
        ranking = [own] + [alias for alias in balanced.ALIASES if alias != own][:2]
        response = json.dumps({"operator": "reconcile", "ranking": ranking}, separators=(",", ":"))
        adapter = FakeAdapter({arm_id: response for arm_id in parent.ARM_IDS})
        cleanup, postflight = parent._execute_unstarted_arms(
            self.repository,
            paths,
            live=adapter,
            full_preflight={},
        )
        self.assertEqual(adapter.request_ids, list(parent.ARM_IDS))
        self.assertEqual(adapter.launches, 1)
        self.assertEqual(adapter.cleanup_calls, 1)
        self.assertTrue(cleanup["passed"])
        self.assertTrue(postflight["passed"])
        parent.append_journal_event(
            paths["journal"],
            "finalization-observed",
            facts=parent._finalization_facts(cleanup, postflight),
        )
        parent._freeze_then_adjudicate_all(self.repository, paths)
        self.assertEqual(set(parent._journal_adjudications(parent.read_journal(paths["journal"]))), set(parent.ARM_IDS))

    def test_transport_parse_failure_binds_partial_raw_response(self) -> None:
        paths = parent.state_paths(self.repository)
        self.start_journal()
        adapter = FakeAdapter({arm_id: "{}" for arm_id in parent.ARM_IDS})
        ordinary_execute = adapter.execute_request

        def execute(*, request: object, **kwargs: object) -> FakeExecution:
            if str(getattr(request, "request_id")) == parent.ARM_IDS[0]:
                recorder = kwargs.get("raw_line_recorder")
                if not callable(recorder):
                    raise AssertionError("raw response recorder was not supplied")
                recorder(b"data: {malformed}\n\n")
                raise harness.HarnessError("synthetic transport parse failure")
            return ordinary_execute(request=request, **kwargs)

        adapter.execute_request = execute  # type: ignore[method-assign]
        parent._execute_unstarted_arms(
            self.repository,
            paths,
            live=adapter,
            full_preflight={},
        )
        event = parent._event_for(
            parent.read_journal(paths["journal"]),
            "adjudicated",
            parent.ARM_IDS[0],
        )
        self.assertEqual(event["facts"]["classification"], parent.INCONCLUSIVE_CLASSIFICATION)
        partial = paths[f"partial-capture-{parent.ARM_IDS[0]}"]
        self.assertEqual(
            event["facts"]["partial_response_sha256"],
            parent.sha256_bytes(partial.read_bytes()),
        )

    def test_real_commit_chain_resumes_only_unstarted_arm_then_replays_zero_contact(self) -> None:
        authority, request_hashes, patches = self.repair_policy_fixture()
        try:
            journal, before = self.initialize_consumed_repair_evidence(
                authority,
                request_hashes,
            )
            original = str(authority["authorized_commit"])
            commit_b = self.commit_repair_fixture("commit-b")
            report_b = parent._observe_controller_repair(
                self.repository,
                parent.state_paths(self.repository),
                authority=authority,
                current_commit=commit_b,
            )
            self.assertEqual(report_b["original_execution_commit"], original)
            self.assertEqual(report_b["controller_repair_commit_count"], 1)
            second = parent.ARM_IDS[1]
            adapter_b = FakeAdapter({second: self.valid_transform_response()})
            cleanup_b, postflight_b = parent._execute_unstarted_arms(
                self.repository,
                parent.state_paths(self.repository),
                live=adapter_b,
                full_preflight={},
            )
            self.assertTrue(cleanup_b["passed"])
            self.assertTrue(postflight_b["passed"])
            self.assertEqual(adapter_b.request_ids, [second])
            self.assertEqual(adapter_b.launches, 1)
            second_before = parent.state_paths(self.repository)[
                f"capture-{second}"
            ].read_bytes()

            commit_c = self.commit_repair_fixture("commit-c")
            report_c = parent._observe_controller_repair(
                self.repository,
                parent.state_paths(self.repository),
                authority=authority,
                current_commit=commit_c,
            )
            self.assertEqual(report_c["previous_replay_commit"], commit_b)
            self.assertEqual(report_c["controller_repair_commit_count"], 2)
            adapter_c = FakeAdapter({})
            cleanup_c, postflight_c = parent._execute_unstarted_arms(
                self.repository,
                parent.state_paths(self.repository),
                live=adapter_c,
                full_preflight={},
            )
            self.assertEqual(adapter_c.request_ids, [])
            self.assertEqual(adapter_c.launches, 0)
            parent.append_journal_event(
                journal,
                "finalization-observed",
                facts=parent._finalization_facts(cleanup_c, postflight_c),
            )
            parent._freeze_then_adjudicate_all(
                self.repository,
                parent.state_paths(self.repository),
            )
            events = parent.read_journal(journal)
            self.assertEqual(
                set(parent._journal_adjudications(events)),
                set(parent.ARM_IDS),
            )
            for arm_id in parent.ARM_IDS:
                starts = [
                    event
                    for event in events
                    if event["state"] == "request-started"
                    and event.get("arm_id") == arm_id
                ]
                self.assertEqual(len(starts), 1)
                self.assertEqual(
                    starts[0]["facts"]["model_request_sha256"],
                    request_hashes[arm_id],
                )
            repairs = [
                event for event in events if event["state"] == "controller-repair-observed"
            ]
            self.assertEqual(len(repairs), 2)
            self.assertTrue(
                all(event["facts"]["model_generations_issued"] == 0 for event in repairs)
            )
            paths = parent.state_paths(self.repository)
            self.assertEqual(paths["receipt"].read_bytes(), before["receipt"])
            self.assertEqual(
                paths[f"capture-{parent.ARM_IDS[0]}"].read_bytes(),
                before[parent.ARM_IDS[0]],
            )
            self.assertEqual(paths[f"capture-{second}"].read_bytes(), second_before)
        finally:
            for patcher in reversed(patches):
                patcher.stop()

    def test_repair_resume_rejects_scientific_mutations_before_model_contact(self) -> None:
        authority, request_hashes, patches = self.repair_policy_fixture()
        try:
            self.initialize_consumed_repair_evidence(authority, request_hashes)
            commit_b = self.commit_repair_fixture("commit-b")
            changed_requests = dict(request_hashes)
            changed_requests[parent.ARM_IDS[0]] = "0" * 64
            with mock.patch.object(
                parent,
                "request_isolation_report",
                return_value={"arm_request_sha256": changed_requests},
            ):
                with self.assertRaisesRegex(
                    parent.ParentDependenceError,
                    "immutable binding",
                ):
                    parent._controller_repair_report(
                        self.repository,
                        authority,
                        current_commit=commit_b,
                        events=parent.read_journal(self.journal_path()),
                    )
            for surface in (
                "intervention",
                "seed",
                "model-schema",
                "dispatch",
                "capture-recording",
            ):
                with self.subTest(surface=surface), mock.patch.object(
                    parent,
                    "_frozen_scientific_binding",
                    return_value={"sha256": "0" * 64},
                ):
                    with self.assertRaisesRegex(
                        parent.ParentDependenceError,
                        "immutable binding",
                    ):
                        parent._controller_repair_report(
                            self.repository,
                            authority,
                            current_commit=commit_b,
                            events=parent.read_journal(self.journal_path()),
                        )
            adapter = FakeAdapter({})
            self.assertEqual(adapter.request_ids, [])
            self.assertEqual(adapter.launches, 0)
        finally:
            for patcher in reversed(patches):
                patcher.stop()

    def test_non_descendant_and_fourth_controller_repair_commit_are_rejected(self) -> None:
        authority, request_hashes, patches = self.repair_policy_fixture()
        try:
            self.initialize_consumed_repair_evidence(authority, request_hashes)
            tree = subprocess.run(
                ["git", "rev-parse", f"{authority['authorized_commit']}^{{tree}}"],
                cwd=self.repository,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            orphan = subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Neo Test",
                    "-c",
                    "user.email=neo@example.invalid",
                    "commit-tree",
                    tree,
                ],
                cwd=self.repository,
                check=True,
                capture_output=True,
                text=True,
                input="orphan\n",
            ).stdout.strip()
            with self.assertRaisesRegex(
                parent.ParentDependenceError,
                "not a descendant",
            ):
                parent._controller_repair_report(
                    self.repository,
                    authority,
                    current_commit=orphan,
                    events=parent.read_journal(self.journal_path()),
                )
            for ordinal in range(1, 4):
                commit = self.commit_repair_fixture(f"repair-{ordinal}")
                parent._observe_controller_repair(
                    self.repository,
                    parent.state_paths(self.repository),
                    authority=authority,
                    current_commit=commit,
                )
            fourth = self.commit_repair_fixture("repair-4")
            journal_before = self.journal_path().read_bytes()
            with self.assertRaisesRegex(
                parent.ParentDependenceError,
                "budget exceeded",
            ):
                parent._observe_controller_repair(
                    self.repository,
                    parent.state_paths(self.repository),
                    authority=authority,
                    current_commit=fourth,
                )
            self.assertEqual(self.journal_path().read_bytes(), journal_before)
        finally:
            for patcher in reversed(patches):
                patcher.stop()

    def test_test_process_guard_rejects_real_repository_state(self) -> None:
        real = Path(__file__).resolve().parents[1]
        with self.assertRaises(parent.source_authority.RankHeadV2AuthorityError):
            parent.source_authority.assert_test_repository_isolated(real)


if __name__ == "__main__":
    unittest.main()
