#!/usr/bin/env python3
"""CPU-only end-to-end custody checks for the prospective CS1-v4 path."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import holostate_live as holo
from catalytic_swarm_1_v3_namespace import (
    VersionedPathLawError as V3VersionedPathLawError,
    qualify_versioned_one_shot_paths as qualify_v3_one_shot_paths,
)
from catalytic_swarm_1_v4_namespace import ONE_SHOT_KEYS, qualify_versioned_one_shot_paths
from catalytic_swarm_1_v4_protocol import build_catalytic_swarm_1_v4_contract
from catalytic_swarm_1_v4_runtime_binding import (
    V1_SCHEDULER_CONTRACT_SHA256,
    V4_CLAIM_CONTRACT_SHA256,
    build_v4_runtime_binding,
    validate_persisted_v4_record,
)


ROOT = Path(__file__).resolve().parents[1]


class V4ControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = build_catalytic_swarm_1_v4_contract()
        self.binding = build_v4_runtime_binding()

    def test_real_evaluator_sorted_mapping_and_runtime_tuple_pass(self) -> None:
        evaluator = json.loads((ROOT / "lab/EVALUATOR.json").read_text(encoding="utf-8"))
        declared = evaluator["catalytic_swarm_1_v4"]["one_shot"]["paths"]
        result = qualify_versioned_one_shot_paths(
            repo_root=ROOT,
            contract_paths=declared,
            active_artifact_paths=holo.CATALYTIC_SWARM_1_V4_ARTIFACT_PATHS,
            required_namespace="state/catalytic_swarm_1_v4",
            forbidden_namespaces=("state/catalytic_swarm_1", "state/catalytic_swarm_1_cache_diagnostic", "state/catalytic_swarm_1_v2", "state/catalytic_swarm_1_v3"),
        )
        self.assertTrue(result["passed"])
        self.assertEqual(tuple(result["relative_paths"]), ONE_SHOT_KEYS)

    def test_real_sorted_v3_mapping_reproduces_consumed_failure(self) -> None:
        evaluator = json.loads((ROOT / "lab/EVALUATOR.json").read_text(encoding="utf-8"))
        declared = evaluator["catalytic_swarm_1_v3"]["one_shot"]["paths"]
        with self.assertRaisesRegex(V3VersionedPathLawError, "key order"):
            qualify_v3_one_shot_paths(
                repo_root=ROOT,
                contract_paths=declared,
                active_artifact_paths=holo.CATALYTIC_SWARM_1_V3_ARTIFACT_PATHS,
                required_namespace="state/catalytic_swarm_1_v3",
            )

    def test_active_control_qualification_uses_v4_paths(self) -> None:
        base = holo.load_json(ROOT / "lab/EVALUATOR.json")["catalytic_swarm_1"]
        with holo.catalytic_swarm_1_v4_runtime_namespace(self.contract, self.binding), mock.patch.object(
            holo, "qualify_catalytic_swarm_1_control", return_value={"passed": True}
        ) as qualify:
            holo.qualify_active_catalytic_swarm_1_control(base, stable_tokenizer=True)
        kwargs = qualify.call_args.kwargs
        self.assertEqual(kwargs["contract_paths"], self.contract["one_shot"]["paths"])
        self.assertEqual(tuple(kwargs["active_artifact_paths"]), holo.CATALYTIC_SWARM_1_V4_ARTIFACT_PATHS)
        self.assertIn("state/catalytic_swarm_1_v3", kwargs["forbidden_namespaces"])

    def test_every_prospective_artifact_is_v4_labelled_before_write(self) -> None:
        stages = (
            (holo.CATALYTIC_SWARM_1_V4_CONTROL_PATH, "control", "control_qualification_v1"),
            (holo.CATALYTIC_SWARM_1_V4_READINESS_PATH, "readiness", "readiness_v1"),
            (holo.CATALYTIC_SWARM_1_V4_PARSER_CANARY_PATH, "parser_canary", "parser_canary_v1"),
            (holo.CATALYTIC_SWARM_1_V4_ATTEMPT_PATH, "attempt", "catalytic_swarm_1"),
            (holo.CATALYTIC_SWARM_1_V4_RESULT_PATH, "result", "catalytic_swarm_1"),
            (holo.CATALYTIC_SWARM_1_V4_TASK_RESULTS_PATH, "task_results", "catalytic_swarm_1"),
        )
        for path, stage, legacy in stages:
            with self.subTest(stage=stage):
                record = holo.bind_catalytic_swarm_1_runtime_record(path, {"status": "running", legacy: "inconclusive"}, self.binding)
                validate_persisted_v4_record(record, stage)
                self.assertEqual(record["contract_sha256"], V4_CLAIM_CONTRACT_SHA256)
                self.assertNotIn("catalytic_swarm_1_v3", record)

    def test_first_ledger_record_is_v4_identity_bound_at_creation(self) -> None:
        base = {key: 0 for key in holo.CATALYTIC_SWARM_1_LEDGER_FIELDS}
        base.update({"task_id":"cs1-task-01","arm":"common-root-warm","assigned_parents":[],"candidate_id":None,"public_pass_count":None,"content_sha256":"x","token_evidence_scope":"metadata","wddm_freshness_boundary":"x","lease_id":0,"request_started_at":"x","request_finished_at":"x"})
        record = holo.bind_catalytic_swarm_1_ledger_record(base, self.binding)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); path = root / "ledger-v4.jsonl"
            ledger = holo.BoundedStreamLedger(
                path, max_bytes=1024 * 1024, max_records=10, state_root=root,
                record_transform=lambda value: holo.bind_catalytic_swarm_1_ledger_record(value, self.binding),
                initial_record=record, initial_request_label="first", initial_request_sequence_index=1,
            )
            ledger.close(); persisted = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["runtime_version"], "v4")
        self.assertEqual(persisted["claim_contract_sha256"], V4_CLAIM_CONTRACT_SHA256)
        self.assertEqual(persisted["scheduler_contract_sha256"], V1_SCHEDULER_CONTRACT_SHA256)

    def test_returned_result_identity_equals_persisted_identity(self) -> None:
        persisted = holo.bind_catalytic_swarm_1_runtime_record(
            holo.CATALYTIC_SWARM_1_V4_RESULT_PATH,
            {"status": "complete", "catalytic_swarm_1": "inconclusive"},
            self.binding,
        )
        returned = dict(persisted)
        self.assertEqual(returned, persisted)
        validate_persisted_v4_record(returned, "result")

    def test_zero_request_early_preclaim_failure_persists_consumed_control(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); control = root / "control-qualification-v4.json"
            with mock.patch.object(holo, "catalytic_swarm_1_v4_runtime_namespace", return_value=nullcontext()), mock.patch.object(
                holo, "CATALYTIC_SWARM_1_STATE_ROOT", root
            ), mock.patch.object(holo, "CATALYTIC_SWARM_1_CONTROL_PATH", control), mock.patch.object(
                holo, "_catalytic_swarm_1_runtime_stage", return_value="control"
            ), mock.patch.object(
                holo, "prepare_catalytic_swarm_1_v4_claim", side_effect=holo.NeoLoopError("static preclaim failed")
            ) as prepare, mock.patch.object(holo, "LiveSidecar") as sidecar:
                with self.assertRaisesRegex(holo.NeoLoopError, "static preclaim failed"):
                    holo.run_catalytic_swarm_1_v4_audit(SimpleNamespace(authorized_main="a" * 40, model="model.gguf"))
                with self.assertRaisesRegex(holo.NeoLoopError, "already claimed"):
                    holo.run_catalytic_swarm_1_v4_audit(SimpleNamespace(authorized_main="a" * 40, model="model.gguf"))
            value = json.loads(control.read_text(encoding="utf-8"))
        self.assertTrue(value["command_invocation_consumed"])
        self.assertEqual(value["live_model_requests"], 0)
        self.assertEqual(value["sidecar_launches"], 0)
        self.assertEqual(prepare.call_count, 1)
        self.assertEqual(value["failure_stage"], "preclaim")
        sidecar.assert_not_called()

    def test_contract_construction_failure_occurs_after_consumed_control_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); control = root / "control-qualification-v4.json"

            def fail_during_prepare(*_args: object, **_kwargs: object) -> object:
                return holo.build_catalytic_swarm_1_v4_contract()

            with mock.patch.object(
                holo, "catalytic_swarm_1_v4_runtime_namespace", return_value=nullcontext()
            ), mock.patch.object(
                holo, "CATALYTIC_SWARM_1_STATE_ROOT", root
            ), mock.patch.object(
                holo, "CATALYTIC_SWARM_1_CONTROL_PATH", control
            ), mock.patch.object(
                holo, "_catalytic_swarm_1_runtime_stage", return_value="control"
            ), mock.patch.object(
                holo,
                "build_catalytic_swarm_1_v4_contract",
                side_effect=holo.NeoLoopError("contract construction failed"),
            ), mock.patch.object(
                holo,
                "prepare_catalytic_swarm_1_v4_claim",
                side_effect=fail_during_prepare,
            ), mock.patch.object(holo, "LiveSidecar") as sidecar:
                with self.assertRaisesRegex(holo.NeoLoopError, "contract construction failed"):
                    holo.run_catalytic_swarm_1_v4_audit(
                        SimpleNamespace(authorized_main="a" * 40, model="model.gguf")
                    )
            value = json.loads(control.read_text(encoding="utf-8"))
        self.assertTrue(value["command_invocation_consumed"])
        self.assertEqual(value["failure_stage"], "preclaim")
        self.assertEqual(value["live_model_requests"], 0)
        self.assertEqual(value["sidecar_launches"], 0)
        sidecar.assert_not_called()

    def test_preclaim_namespace_mismatch_is_persisted_after_consumption(self) -> None:
        mismatched = json.loads(json.dumps(self.contract))
        mismatched["one_shot"]["paths"]["control"] = (
            "state/catalytic_swarm_1_v4/not-the-control-path.json"
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); control = root / "control-qualification-v4.json"
            with mock.patch.object(
                holo, "catalytic_swarm_1_v4_runtime_namespace", return_value=nullcontext()
            ), mock.patch.object(
                holo, "CATALYTIC_SWARM_1_STATE_ROOT", root
            ), mock.patch.object(
                holo, "CATALYTIC_SWARM_1_CONTROL_PATH", control
            ), mock.patch.object(
                holo, "_catalytic_swarm_1_runtime_stage", return_value="control"
            ), mock.patch.object(
                holo,
                "prepare_catalytic_swarm_1_v4_claim",
                return_value=(mismatched, self.binding),
            ), mock.patch.object(holo, "run_catalytic_swarm_1_audit") as shared:
                with self.assertRaisesRegex(holo.NeoLoopError, "preclaim namespace differs"):
                    holo.run_catalytic_swarm_1_v4_audit(
                        SimpleNamespace(authorized_main="a" * 40, model="model.gguf")
                    )
            value = json.loads(control.read_text(encoding="utf-8"))
        self.assertTrue(value["command_invocation_consumed"])
        self.assertEqual(value["failure_stage"], "preclaim")
        self.assertIn("preclaim namespace differs", value["error"])
        shared.assert_not_called()

    def test_v3_public_command_is_hard_retired(self) -> None:
        with self.assertRaisesRegex(holo.NeoLoopError, "consumed / no retry"):
            holo.command_audit_catalytic_swarm_1_v3(object())

    def test_all_earlier_cs1_commands_are_retired(self) -> None:
        for command in (holo.command_audit_catalytic_swarm_1, holo.command_audit_catalytic_swarm_1_cache_diagnostic, holo.command_audit_catalytic_swarm_1_v2):
            with self.assertRaises(holo.NeoLoopError):
                command(object())

    def test_v4_cli_requires_model_and_authorized_main(self) -> None:
        parser = holo.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["audit-catalytic-swarm-1-v4"])
        with self.assertRaises(SystemExit):
            parser.parse_args(["audit-catalytic-swarm-1-v4", "--model", "model.gguf"])

    def test_v4_preclaim_rejects_missing_model_before_live_access(self) -> None:
        with mock.patch.object(holo, "LiveSidecar") as sidecar:
            with self.assertRaisesRegex(holo.NeoLoopError, "requires --model"):
                holo.prepare_catalytic_swarm_1_v4_claim(
                    SimpleNamespace(authorized_main="a" * 40, model="")
                )
        sidecar.assert_not_called()

    def test_v4_preclaim_rejects_nonexact_authorized_main_before_live_access(self) -> None:
        with mock.patch.object(holo, "git_read", return_value="b" * 40), mock.patch.object(
            holo, "LiveSidecar"
        ) as sidecar:
            with self.assertRaisesRegex(holo.NeoLoopError, "equal protected main"):
                holo.prepare_catalytic_swarm_1_v4_claim(
                    SimpleNamespace(authorized_main="a" * 40, model="model.gguf")
                )
        sidecar.assert_not_called()

    def test_v4_state_root_and_all_artifacts_are_absent(self) -> None:
        self.assertFalse(holo.CATALYTIC_SWARM_1_V4_STATE_ROOT.exists())
        self.assertFalse(any(path.exists() for path in holo.CATALYTIC_SWARM_1_V4_ARTIFACT_PATHS))

    def test_all_v4_runtime_artifacts_are_ignored_raw_state(self) -> None:
        for path in holo.CATALYTIC_SWARM_1_V4_ARTIFACT_PATHS:
            relative = path.relative_to(ROOT).as_posix()
            with self.subTest(path=relative):
                completed = subprocess.run(
                    ["git", "check-ignore", "--quiet", relative],
                    cwd=ROOT,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0)

    def test_existing_v4_root_or_artifact_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); root.mkdir(exist_ok=True)
            with mock.patch.object(holo, "CATALYTIC_SWARM_1_V4_STATE_ROOT", root), mock.patch.object(
                holo, "CATALYTIC_SWARM_1_V4_ARTIFACT_PATHS", tuple(root / path.name for path in holo.CATALYTIC_SWARM_1_V4_ARTIFACT_PATHS)
            ):
                with self.assertRaisesRegex(holo.NeoLoopError, "state already exists"):
                    holo.assert_catalytic_swarm_1_v4_artifacts_absent()

    def test_existing_individual_v4_artifact_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); paths = tuple(root / path.name for path in holo.CATALYTIC_SWARM_1_V4_ARTIFACT_PATHS)
            paths[3].write_text("{}", encoding="utf-8")
            with mock.patch.object(holo, "ROOT", root), mock.patch.object(holo, "CATALYTIC_SWARM_1_V4_STATE_ROOT", root), mock.patch.object(
                holo, "CATALYTIC_SWARM_1_V4_ARTIFACT_PATHS", paths
            ):
                with self.assertRaisesRegex(holo.NeoLoopError, "attempt-v4.json"):
                    holo.assert_catalytic_swarm_1_v4_artifacts_absent()

    def test_frozen_geometry_is_exact(self) -> None:
        evaluator = holo.load_json(ROOT / "lab/EVALUATOR.json")
        v3 = evaluator["catalytic_swarm_1_v3"]; v4 = evaluator["catalytic_swarm_1_v4"]
        self.assertEqual(v4["frozen_geometry"], v3["frozen_geometry"])
        self.assertEqual(v4["cache_admission_law"], v3["cache_admission_law"])
        self.assertEqual(v4["frozen_geometry"]["total_model_requests"], 1032)

    def test_runtime_transport_uses_unchanged_root_terminal_law(self) -> None:
        with holo.catalytic_swarm_1_v4_runtime_namespace(self.contract, self.binding):
            transport = holo.adapt_catalytic_swarm_1_transport_for_scheduler({
                "content":"{}","prompt_tokens":4825,"cached_prompt_tokens":4822,
                "required_cached_prompt_tokens":4825,"fresh_prompt_tokens":3,"completion_tokens":2,
                "finish_reason":"stop","reasoning_content":"","tool_calls":[],"transport_passed":True,
                "token_evidence_scope":"metadata","public_root_terminal_token_index":4820,
                "common_prefix_tokens":4822,"cache_admission":{"admitted":True},
            })
        self.assertEqual(transport["required_cached_prompt_tokens"], 4820)


if __name__ == "__main__":
    unittest.main()
