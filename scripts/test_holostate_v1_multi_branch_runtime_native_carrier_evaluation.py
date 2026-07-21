#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import holostate_v1_multi_branch_runtime_native_carrier_evaluation as probe


class FakeCodec:
    EOG = 999

    @staticmethod
    def render_messages(messages, _kwargs):
        rendered = ""
        for item in messages:
            if item["role"] == "assistant":
                rendered += f"{item['content']}<eos>"
            else:
                rendered += f"<{item['role']}>{item['content']}</{item['role']}>"
        return rendered

    @classmethod
    def tokenize(cls, value):
        if value == "<eos>":
            return [cls.EOG]
        if value.startswith("<eos>"):
            return [cls.EOG, *value[len("<eos>"):].encode("utf-8")]
        return list(value.encode("utf-8"))

    @classmethod
    def detokenize(cls, token_ids):
        if list(token_ids) == [cls.EOG]:
            return "<eos>"
        return bytes(token_ids).decode("utf-8")


def generation_execution(
    *,
    prompt=100,
    cached=0,
    completion=5,
    http_status=200,
    observed=True,
    stop=True,
    finish_reason="eos",
    generated_token_ids=None,
    generated_token_count=None,
    completion_token_count_match=True,
    generated_token_sha256=None,
    content="A",
):
    generated = list(range(100, 100 + completion)) if generated_token_ids is None else generated_token_ids
    count = len(generated) if generated_token_count is None else generated_token_count
    generated_hash = (
        probe.sha256_bytes(probe.canonical_json_bytes(generated))
        if generated_token_sha256 is None
        else generated_token_sha256
    )
    return {
        "content": content,
        "reasoning_content": "",
        "tool_calls": [],
        "prompt_tokens": prompt,
        "cached_prompt_tokens": cached,
        "completion_tokens": completion,
        "generated_token_ids": generated,
        "generated_token_count": count,
        "completion_token_count_match": completion_token_count_match,
        "generated_token_sha256": generated_hash,
        "nonempty_token_array_event_count": 1 if generated else 0,
        "empty_token_array_event_count": 1,
        "token_merge_modes": ["append"] if generated else [],
        "terminal_stop_evidence": {"observed": observed, "stop": stop},
        "finish_reason": finish_reason,
        "http_status": http_status,
        "event_count": 2,
    }


def task_a_capture(prompt_tokens):
    text = '{"state":["one","two","three","four"],"answer":"A"}'
    generated = [*text.encode("utf-8"), FakeCodec.EOG]
    execution = generation_execution(
        prompt=len(prompt_tokens),
        completion=len(generated),
        generated_token_ids=generated,
        content=text,
    )
    return {
        "model_request_sha256": "A" * 64,
        "capture_sha256": "B" * 64,
        "execution": execution,
    }


def generation_capture(**kwargs):
    return {"execution": generation_execution(**kwargs)}


def readdress_execution(*, http_status=200, observed=True, stop=True, finish_reason="limit", cached=3):
    return SimpleNamespace(
        prompt_tokens=4,
        cached_prompt_tokens=cached,
        completion_tokens=0,
        generated_token_ids=[],
        generated_token_count=0,
        completion_token_count_match=True,
        generated_token_sha256=probe.sha256_bytes(probe.canonical_json_bytes([])),
        terminal_stop_evidence={"observed": observed, "stop": stop},
        finish_reason=finish_reason,
        http_status=http_status,
    )


def raw_sse_fixture(*, stop=True, stop_type="eos", tokens=(100, 101, 102, 103, 104)):
    first = probe.canonical_json_bytes({"content": "A", "tokens": list(tokens)})
    terminal = probe.canonical_json_bytes({
        "content": "",
        "tokens": [],
        "stop": stop,
        "stop_type": stop_type,
        "timings": {"predicted_n": len(tokens)},
    })
    return b"data: " + first + b"\n" + b"data: " + terminal + b"\n"


def capture_with_raw_sse(base, execution, *, raw=None):
    request_id = probe.REQUEST_ORDER[0]
    raw_bytes = raw_sse_fixture() if raw is None else raw

    def invoke(recorder):
        for line in raw_bytes.splitlines(keepends=True):
            recorder(line)
        return SimpleNamespace(**execution)

    return probe.capture_request_once(
        base / "capture.json",
        base / ".capture.raw.partial",
        experiment_key=b"k" * 32,
        request_id=request_id,
        model_request_sha256="D" * 64,
        generation_ordinal=1,
        invoke=invoke,
    )


class FakeLive:
    h = SimpleNamespace(PORT=9494)

    @staticmethod
    def resource_summary(**_kwargs):
        return {"rss_bytes": 123}


class MultiBranchCarrierPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = probe.load_public_corpus(ROOT)
        cls.by_id = {item["root_id"]: item for item in cls.corpus["roots"]}

    def test_01_new_corpus_and_private_custody(self):
        self.assertEqual(tuple(self.by_id), probe.ROOT_IDS)
        branch_ids = [item["branch_id"] for root in self.corpus["roots"] for item in root["branches"]]
        self.assertEqual(tuple(branch_ids), probe.BRANCH_IDS)
        self.assertEqual(len(set(branch_ids)), 8)
        self.assertGreaterEqual(len({item["reasoning_type"] for root in self.corpus["roots"] for item in root["branches"]}), 4)
        text = probe.canonical_json_text(self.corpus)
        self.assertFalse(any(pair_id in text for pair_id in probe.predecessor.PAIR_IDS))
        self.assertFalse(any(key in text for key in ("task_a_answer", "branch_answers", "task_a_state_required_concepts")))
        custody = probe.protected_evaluator_custody(ROOT)
        self.assertTrue(custody["regular"] and custody["ignored"])
        self.assertFalse(custody["tracked"] or custody["bytes_opened"])

    def test_02_exact_preregistration_reconstruction(self):
        value = probe.validate_preregistration(ROOT)
        self.assertEqual(value["family_id"], probe.FAMILY_ID)
        self.assertEqual(value["design_id"], probe.DESIGN_ID)
        self.assertEqual(value["next_action"], "AUTHORIZE_ONE_LIVE_MULTI_BRANCH_RUNTIME_NATIVE_CARRIER_EVALUATION")
        self.assertEqual(value["execution_absences"]["model_requests"], 0)

    def test_03_frozen_order_and_ceilings(self):
        self.assertEqual(len(probe.REQUEST_ORDER), probe.MAXIMUM_GENERATIONS, 20)
        self.assertEqual(len(probe.INFERENCE_ORDER), probe.MAXIMUM_INFERENCE_REQUESTS, 24)
        self.assertEqual(len(probe.SNAPSHOT_CONTROL_ORDER), probe.SNAPSHOT_CONTROL_COUNT, 12)
        self.assertEqual(sum(item.endswith("snapshot-save") for item in probe.SNAPSHOT_CONTROL_ORDER), 4)
        self.assertEqual(sum("snapshot-restore" in item for item in probe.SNAPSHOT_CONTROL_ORDER), 8)
        for root_id in probe.ROOT_IDS:
            offset = probe.ROOT_IDS.index(root_id) * 6
            self.assertEqual(probe.INFERENCE_ORDER[offset], f"{root_id}-task-a")
            self.assertEqual(probe.INFERENCE_ORDER[offset + 3], f"{root_id}-root-readdress")
        self.assertEqual([probe.FIRST_BRANCH[item] for item in probe.ROOT_IDS], [1, 2, 1, 2])

    def test_04_task_a_uses_exact_integer_tokens_and_exact_capture_flags(self):
        payload = probe._task_a_payload([11, 12, 13], seed=7)
        self.assertEqual(payload["prompt"], [11, 12, 13])
        self.assertTrue(payload["return_tokens"] and payload["return_progress"])
        self.assertFalse(payload["cache_prompt"])
        self.assertEqual(payload["id_slot"], probe.kernel.PHYSICAL_SLOT)
        self.assertIn("state", payload["grammar"])

    def test_05_retained_root_uses_emitted_ids_and_omits_only_eog(self):
        prompt = [10, 20, 30]
        value = probe.derive_retained_root(
            task_a_capture(prompt), prompt, FakeCodec(), {"eos_token": "<eos>"}
        )
        emitted = task_a_capture(prompt)["execution"]["generated_token_ids"]
        self.assertEqual(value["retained_root_tokens"], [*prompt, *emitted[:-1]])
        self.assertEqual(value["generated_token_count"], len(emitted))
        self.assertFalse(value["visible_content_retokenized"])
        self.assertFalse(value["terminal_stop_identity"]["decoded_into_retained_state"])

    def test_06_retained_root_fails_closed_on_missing_or_non_eos_tokens(self):
        prompt = [1, 2]
        missing = task_a_capture(prompt)
        missing["execution"]["generated_token_ids"] = []
        with self.assertRaises(probe.MultiBranchCarrierEvaluationError):
            probe.derive_retained_root(missing, prompt, FakeCodec(), {"eos_token": "<eos>"})
        wrong = task_a_capture(prompt)
        wrong["execution"]["finish_reason"] = "length"
        with self.assertRaisesRegex(probe.MultiBranchCarrierEvaluationError, "canonical EOS"):
            probe.derive_retained_root(wrong, prompt, FakeCodec(), {"eos_token": "<eos>"})

    def test_07_suffix_and_derivation_are_exact_strict_extensions(self):
        root_id = probe.ROOT_IDS[0]
        root = self.by_id[root_id]
        root_tokens = [1, 2, 3, 4]
        root_record = {
            "retained_root_tokens": root_tokens,
            "retained_root_token_sha256": probe.sha256_bytes(probe.canonical_json_bytes(root_tokens)),
        }
        first = probe.derive_continuation_suffix(
            FakeCodec(), terminal_eog_id=FakeCodec.EOG,
            user_content=probe.branch_user_content(root, 1),
        )
        second = probe.derive_continuation_suffix(
            FakeCodec(), terminal_eog_id=FakeCodec.EOG,
            user_content=probe.branch_user_content(root, 2),
        )
        self.assertNotEqual(first["suffix_token_sha256"], second["suffix_token_sha256"])
        derived = probe.build_branch_derivation(
            root_record=root_record,
            suffix_record=first,
            branch_id=f"{root_id}-branch-1",
            route="live-root",
            snapshot_identity=None,
        )
        self.assertEqual(derived["complete_branch_tokens"], [*root_tokens, *first["suffix_tokens"]])
        self.assertEqual(derived["raw_common_prefix_count"], len(root_tokens))
        self.assertEqual(
            probe._branch_payload(derived["complete_branch_tokens"], seed=probe.derive_seed(root_id, "branch-1"), cache_prompt=False)["prompt"],
            derived["complete_branch_tokens"],
        )
        self.assertFalse(derived["observed_cache_telemetry_used"])

    def test_08_boundary_predictor_preserves_full_root_or_fails_closed(self):
        full = probe.predict_runtime_native_boundary(
            retained_root_tokens=[1, 2, 3],
            requested_tokens=[1, 2, 3, 4],
            retained_pos_min=2,
            retained_pos_next=3,
            n_swa=0,
            memory_removal_capability="full-only",
        )
        self.assertEqual(full["predicted_executable_carrier_count"], 3)
        self.assertFalse(full["rollback_required"])
        self.assertFalse(full["observed_cache_telemetry_used"])
        rolled = probe.predict_runtime_native_boundary(
            retained_root_tokens=[1, 2, 3],
            requested_tokens=[1, 2, 3, 4],
            retained_pos_min=2,
            retained_pos_next=3,
            n_swa=1,
            memory_removal_capability="full-only",
        )
        self.assertTrue(rolled["rollback_required"])
        self.assertEqual(rolled["predicted_executable_carrier_count"], 0)
        with self.assertRaises(probe.MultiBranchCarrierEvaluationError):
            probe.predict_runtime_native_boundary(
                retained_root_tokens=[1, 2, 3],
                requested_tokens=[1, 2, 3],
                retained_pos_min=2,
                retained_pos_next=3,
                n_swa=0,
                memory_removal_capability="full-only",
            )

    def test_09_snapshot_save_restore_authenticates_raw_controls_and_bytes(self):
        root_id = probe.ROOT_IDS[0]
        key = b"k" * 32
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            snapshot = base / f"{root_id}.bin"
            data = b"snapshot-state"
            calls = []

            def request(_method, url, payload, _timeout=120):
                calls.append((url, dict(payload)))
                if "action=save" in url:
                    snapshot.write_bytes(data)
                    response = {"id_slot": 0, "filename": snapshot.name, "n_saved": 9, "n_written": len(data)}
                else:
                    response = {"id_slot": 0, "filename": snapshot.name, "n_restored": 9, "n_read": len(data)}
                raw = probe.canonical_json_bytes(response)
                return response, {"byte_size": len(raw), "sha256": probe.sha256_bytes(raw)}

            with mock.patch.object(probe, "_request_json_with_identity", side_effect=request):
                saved = probe.save_snapshot(
                    live=FakeLive(), sidecar=object(), path=snapshot, filename=snapshot.name,
                    root_id=root_id, retained_root_count=9, experiment_key=key,
                    record_path=base / "save.json",
                )
                restored = probe.restore_snapshot(
                    live=FakeLive(), sidecar=object(), path=snapshot, filename=snapshot.name,
                    root_id=root_id, ordinal=1, retained_root_count=9,
                    expected_sha256=saved["snapshot_sha256"], experiment_key=key,
                    record_path=base / "restore.json",
                )
                with self.assertRaisesRegex(probe.MultiBranchCarrierEvaluationError, "already exists"):
                    probe.save_snapshot(
                        live=FakeLive(), sidecar=object(), path=snapshot, filename=snapshot.name,
                        root_id=root_id, retained_root_count=9, experiment_key=key,
                        record_path=base / "again.json",
                    )
            self.assertEqual(len(calls), 2)
            self.assertEqual(saved["raw_response"]["sha256"], probe.sha256_bytes(probe.canonical_json_bytes(saved["response"])))
            self.assertTrue(restored["snapshot_bytes_unchanged"])
            self.assertEqual(restored["snapshot_sha256_after"], saved["snapshot_sha256"])

    def test_10_zero_output_readdress_is_counted_as_fresh_inference(self):
        payload = probe._branch_payload([1, 2, 3, 4], seed=1, cache_prompt=True, n_predict=0)
        execution = readdress_execution()
        value = probe.root_readdress_record(
            execution,
            root_id=probe.ROOT_IDS[0],
            payload=payload,
            predicted_boundary=3,
            snapshot_sha256="A" * 64,
        )
        self.assertTrue(value["root_readdress_gate"])
        self.assertTrue(value["terminal_evidence_passed"])
        self.assertEqual(value["terminal_finish_reason"], "limit")
        self.assertEqual(value["generation_count"], 0)
        self.assertEqual(value["inference_request_count"], 1)
        self.assertEqual(value["fresh_prompt_tokens"], 1)

    def test_11_resource_accounting_includes_readdress_and_separates_snapshots(self):
        records = []
        for request_id in probe.REQUEST_ORDER:
            cached = 60 if request_id.endswith("-catalytic") else 0
            records.append(probe.resource_record(generation_capture(prompt=100, cached=cached), request_id))
        readdresses = [
            {
                "operation_id": f"{root_id}-root-readdress",
                "request_count": 1,
                "generation_count": 0,
                "logical_prompt_tokens": 100,
                "reused_prompt_tokens": 90,
                "fresh_prompt_tokens": 10,
                "completion_tokens": 0,
                "fresh_prompt_plus_completion_tokens": 10,
                "maximum_request_context": 100,
            }
            for root_id in probe.ROOT_IDS
        ]
        controls = []
        for operation_id in probe.SNAPSHOT_CONTROL_ORDER:
            save = operation_id.endswith("snapshot-save")
            controls.append({
                "operation_id": operation_id,
                "operation_kind": "snapshot-control-save" if save else "snapshot-control-restore",
                "filesystem_bytes_written": 100 if save else 0,
                "filesystem_bytes_read": 0 if save else 100,
                "wall_clock_ms": 1.0,
                "host_memory_before": {"available": False},
            })
        scoring = {
            "task_a_answer_accuracy": {"correct": 4},
            "aggregate_catalytic_branch_accuracy": {"correct": 8},
            "aggregate_direct_branch_accuracy": {"correct": 8},
        }
        value = probe.account_resources(
            records, readdresses, scoring, controls,
            [{"deleted": True} for _ in probe.ROOT_IDS],
        )
        self.assertEqual(value["primary_catalytic_route"]["request_count"], 12)
        self.assertEqual(value["primary_catalytic_route"]["generation_count"], 8)
        self.assertEqual(value["primary_direct_route"]["request_count"], 8)
        self.assertEqual(value["snapshot_resources"]["save_count"], 4)
        self.assertEqual(value["snapshot_resources"]["restore_count"], 8)
        self.assertFalse(value["snapshot_resources"]["included_in_fresh_token_accounting"])
        self.assertFalse(value["historical_projection"]["decision_authority"])

    def test_12_decision_law_preserves_all_four_scientific_outcomes(self):
        scoring = {}
        resources = {
            "catalytic_accuracy_at_least_direct": True,
            "catalytic_fresh_tokens_per_correct_strictly_lower": True,
        }
        reports = {
            branch_id: {
                "route": "live-root" if probe.FIRST_BRANCH[branch_id.rsplit("-branch-", 1)[0]] == int(branch_id[-1]) else "snapshot-restored-root",
                "runtime_native_carrier_gate": True,
            }
            for branch_id in probe.BRANCH_IDS
        }
        readdresses = [
            {"root_readdress_gate": True, "terminal_evidence_passed": True}
            for _ in probe.ROOT_IDS
        ]
        direct = {branch_id: True for branch_id in probe.BRANCH_IDS}
        common = dict(
            scoring=scoring, resources=resources, reuse_reports=reports,
            readdress_records=readdresses, direct_freshness=direct,
            complete_panel=True, snapshot_custody_passed=True,
            cleanup_passed=True, postflight_passed=True,
        )
        self.assertEqual(probe.classify_result(**common), "PROCESS_LOCAL_MULTI_BRANCH_RUNTIME_NATIVE_CARRIER_FRESH_TOKEN_ADVANTAGE_SUPPORTED")
        resources["catalytic_fresh_tokens_per_correct_strictly_lower"] = False
        self.assertEqual(probe.classify_result(**common), "PROCESS_LOCAL_MULTI_BRANCH_RUNTIME_NATIVE_CARRIER_REUSE_SUPPORTED_WITHOUT_FRESH_TOKEN_ADVANTAGE")
        restored = next(value for value in reports.values() if value["route"] == "snapshot-restored-root")
        restored["runtime_native_carrier_gate"] = False
        self.assertEqual(probe.classify_result(**common), "PROCESS_LOCAL_LIVE_ROOT_STRICT_EXTENSION_SUPPORTED_WITHOUT_SNAPSHOT_BRANCH_ISOLATION")
        restored["runtime_native_carrier_gate"] = True
        live = next(value for value in reports.values() if value["route"] == "live-root")
        live["runtime_native_carrier_gate"] = False
        self.assertEqual(probe.classify_result(**common), "PROCESS_LOCAL_MULTI_BRANCH_RUNTIME_NATIVE_CARRIER_REUSE_NOT_SUPPORTED")
        common["cleanup_passed"] = False
        self.assertEqual(probe.classify_result(**common), "INCONCLUSIVE")

    def test_13_protected_evaluator_cannot_open_before_terminal_gates(self):
        with mock.patch.object(probe, "_load_protected_evaluator_after_terminal_gates") as loader:
            with self.assertRaises(probe.MultiBranchCarrierEvaluationError):
                probe.score_protected(
                    ROOT, {},
                    completed_capture_ids=(),
                    completed_readdress_ids=(),
                    completed_snapshot_control_ids=(),
                    cleanup_passed=False,
                    postflight_passed=False,
                )
            loader.assert_not_called()

    def test_14_authority_surface_never_persists_raw_id(self):
        raw = "a" * 64
        authority = probe.build_external_authority(
            raw,
            authorized_commit="b" * 40,
            current_commit="b" * 40,
            preregistration_sha256="C" * 64,
        )
        self.assertNotIn(raw, probe.canonical_json_text(authority))
        self.assertFalse(authority["raw_authority_id_persisted"])
        self.assertEqual(authority["maximum_model_generations"], 20)
        self.assertEqual(authority["maximum_snapshot_controls"], 12)

    def test_15_source_has_no_materialization_retry_or_engine_rewrite(self):
        text = (ROOT / "scripts/holostate_v1_multi_branch_runtime_native_carrier_evaluation.py").read_text(encoding="utf-8")
        run_source = text[text.index("def run_evaluation"):text.index("def _source_text")]
        self.assertNotIn("materialization-", run_source.casefold())
        self.assertNotIn("perform_warm", run_source)
        self.assertNotIn("retry(", run_source.casefold())
        self.assertEqual(run_source.count("with pool.lease() as lease_id"), 1)
        self.assertIn('"continue_panel": True', text)
        self.assertFalse(any((ROOT / path).is_file() and (ROOT / path) in [] for path in probe.SOURCE_LAW_PATHS))

    def test_16_launcher_seam_is_optional_and_path_bound(self):
        live_source = (ROOT / "scripts/holostate_live.py").read_text(encoding="utf-8")
        adapter_source = (ROOT / "scripts/catalytic_kernel_0.py").read_text(encoding="utf-8")
        self.assertIn("slot_save_path: Path | None = None", live_source)
        self.assertIn('args.extend(["--slot-save-path", str(self.slot_save_path)])', live_source)
        self.assertIn("_require_safe_state_ancestry(self.repository_root, resolved_slot_path)", adapter_source)
        self.assertIn("slot-save path escaped the owned run root", adapter_source)

    def test_17_static_validation_proves_zero_contact_preparation(self):
        value = probe.validate_static(ROOT)
        self.assertEqual(value["status"], "pass")
        self.assertEqual(value["proofs"]["maximum_generations"], 20)
        self.assertEqual(value["proofs"]["maximum_inference_requests"], 24)
        self.assertTrue(value["proofs"]["runtime_artifacts_absent"])
        self.assertEqual(value["model_requests_issued"], 0)
        self.assertEqual(value["ledger_records_appended"], 0)
        self.assertEqual(value["next_action"], "AUTHORIZE_ONE_LIVE_MULTI_BRANCH_RUNTIME_NATIVE_CARRIER_EVALUATION")


    def test_18_generation_rejects_non_200_http_status(self):
        with self.assertRaisesRegex(probe.MultiBranchCarrierEvaluationError, "HTTP"):
            probe.validate_inference_terminal_evidence(
                generation_execution(http_status=503),
                operation_kind="model-generation",
            )

    def test_19_generation_rejects_missing_observed_terminal_sse(self):
        execution = generation_execution(observed=False, stop=None, finish_reason="stop")
        raw = b'data: {"content":"A","tokens":[100,101,102,103,104]}\n'
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(probe.MultiBranchCarrierEvaluationError, "observed terminal"):
                capture_with_raw_sse(Path(temporary), execution, raw=raw)

    def test_20_generation_rejects_stop_false(self):
        with self.assertRaisesRegex(probe.MultiBranchCarrierEvaluationError, "observed terminal"):
            probe.validate_inference_terminal_evidence(
                generation_execution(stop=False),
                operation_kind="model-generation",
            )

    def test_21_generation_rejects_missing_emitted_ids(self):
        with self.assertRaisesRegex(probe.MultiBranchCarrierEvaluationError, "emitted-token array"):
            probe.validate_inference_terminal_evidence(
                generation_execution(generated_token_ids=[]),
                operation_kind="model-generation",
            )

    def test_22_generation_rejects_completion_token_mismatch(self):
        with self.assertRaisesRegex(probe.MultiBranchCarrierEvaluationError, "counts differ"):
            probe.validate_inference_terminal_evidence(
                generation_execution(
                    completion=5,
                    generated_token_ids=[100, 101, 102, 103],
                    completion_token_count_match=False,
                ),
                operation_kind="model-generation",
            )

    def test_23_generation_rejects_incorrect_generated_token_hash(self):
        with self.assertRaisesRegex(probe.MultiBranchCarrierEvaluationError, "token hash"):
            probe.validate_inference_terminal_evidence(
                generation_execution(generated_token_sha256="0" * 64),
                operation_kind="model-generation",
            )

    def test_24_valid_task_a_eos_evidence_still_passes(self):
        prompt = [1, 2, 3]
        capture = task_a_capture(prompt)
        terminal = probe.validate_inference_terminal_evidence(
            capture["execution"],
            operation_kind="model-generation",
        )
        self.assertTrue(terminal["terminal_evidence_passed"])
        self.assertEqual(terminal["terminal_finish_reason"], "eos")
        root = probe.derive_retained_root(capture, prompt, FakeCodec(), {"eos_token": "<eos>"})
        self.assertEqual(root["generated_token_count"], len(capture["execution"]["generated_token_ids"]))

    def test_25_valid_branch_terminal_capture_passes(self):
        execution = generation_execution()
        with tempfile.TemporaryDirectory() as temporary:
            capture = capture_with_raw_sse(Path(temporary), execution)
        self.assertTrue(capture["terminal_evidence"]["terminal_evidence_passed"])
        self.assertEqual(capture["terminal_evidence"]["terminal_finish_reason"], "eos")
        self.assertEqual(
            capture["terminal_evidence"]["generated_token_sha256"],
            probe.sha256_bytes(probe.canonical_json_bytes(execution["generated_token_ids"])),
        )

    def test_26_zero_output_readdress_rejects_missing_terminal_stop(self):
        with self.assertRaisesRegex(probe.MultiBranchCarrierEvaluationError, "observed terminal"):
            probe.validate_inference_terminal_evidence(
                readdress_execution(observed=False, stop=None),
                operation_kind="zero-output-root-readdress",
            )

    def test_27_zero_output_readdress_rejects_invalid_http_status(self):
        with self.assertRaisesRegex(probe.MultiBranchCarrierEvaluationError, "HTTP"):
            probe.validate_inference_terminal_evidence(
                readdress_execution(http_status=500),
                operation_kind="zero-output-root-readdress",
            )

    def test_28_valid_zero_output_readdress_passes_before_cache_gate(self):
        payload = probe._branch_payload([1, 2, 3, 4], seed=1, cache_prompt=True, n_predict=0)
        record = probe.root_readdress_record(
            readdress_execution(),
            root_id=probe.ROOT_IDS[0],
            payload=payload,
            predicted_boundary=3,
            snapshot_sha256="A" * 64,
        )
        self.assertEqual(record["terminal_http_status"], 200)
        self.assertEqual(record["terminal_stop_evidence"], {"observed": True, "stop": True})
        self.assertEqual(record["terminal_finish_reason"], "limit")
        self.assertTrue(record["terminal_evidence_passed"])
        self.assertTrue(record["root_readdress_gate"])

    def test_29_terminal_failure_cannot_enter_resources_or_protected_scoring(self):
        invalid = generation_capture(observed=False, stop=None, finish_reason="stop")
        with self.assertRaises(probe.MultiBranchCarrierEvaluationError):
            probe.resource_record(invalid, probe.REQUEST_ORDER[0])
        captures = {request_id: invalid for request_id in probe.REQUEST_ORDER}
        with mock.patch.object(probe, "_load_protected_evaluator_after_terminal_gates") as loader:
            with self.assertRaises(probe.MultiBranchCarrierEvaluationError):
                probe.score_protected(
                    ROOT,
                    captures,
                    completed_capture_ids=probe.REQUEST_ORDER,
                    completed_readdress_ids=probe.READDRESS_ORDER,
                    completed_snapshot_control_ids=probe.SNAPSHOT_CONTROL_ORDER,
                    cleanup_passed=True,
                    postflight_passed=True,
                )
            loader.assert_not_called()

    def test_30_valid_scientifically_false_reuse_gate_continues_panel(self):
        capture = generation_capture(prompt=10, cached=2)
        report = probe.evaluate_reuse(
            {
                "branch_id": probe.BRANCH_IDS[0],
                "route": "live-root",
                "source_predicted_executable_boundary": {
                    "predicted_executable_carrier_count": 3,
                },
            },
            capture,
        )
        self.assertFalse(report["runtime_native_carrier_gate"])
        self.assertTrue(report["continue_panel"])

    def test_31_terminal_law_and_exact_preregistration_reconstruct(self):
        preregistration = probe.validate_preregistration(ROOT)
        law = preregistration["terminal_evidence_law"]
        self.assertEqual(law["model_generation"]["allowed_finish_reasons"], ["eos"])
        self.assertEqual(law["root_readdress"]["allowed_finish_reasons"], ["limit"])
        self.assertEqual(law["failure"]["classification"], "INCONCLUSIVE")
        self.assertFalse(law["failure"]["retry"])

    def test_32_terminal_repair_creates_no_authority_or_live_state(self):
        value = probe.validate_static(ROOT)
        self.assertTrue(value["authority_receipt_absent"])
        self.assertEqual(value["sidecar_launches"], 0)
        self.assertEqual(value["model_requests_issued"], 0)
        self.assertEqual(value["model_generations"], 0)
        self.assertEqual(value["captures_created"], 0)
        self.assertEqual(value["results_created"], 0)
        self.assertEqual(value["archives_created"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
