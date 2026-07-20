#!/usr/bin/env python3
"""Prepare, validate, or run the inherited Task-A carrier evaluation.

The scientific intervention is deliberately narrow: Task B follows the
authenticated Task-A generation on the same physical slot without a fresh
checkpoint-materialization request.  This module reuses the established
warm-trajectory corpus, schemas, capture normalization, lifecycle adapter,
and protected evaluator while owning a new authority and evidence domain.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import inspect
import json
import os
import re
import shutil
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Sequence

import catalytic_inference_bench_0_runtime as runtime_support
import catalytic_kernel_0 as kernel
import holostate_v1_warm_trajectory_related_task_evaluation as source


class InheritedCarrierEvaluationError(ValueError):
    """The frozen design, evidence custody, or decision law changed."""


DESIGN_ID = "holostate-v1-inherited-task-a-carrier-evaluation-v1"
STARTING_PROTECTED_MAIN = "fc5123325558b89f15c83b9d41484b1bf5da7615"
SOURCE_SELECTION_PATH = Path("lab/holostate_v1_warm_trajectory_successor_selection_1.json")
SOURCE_SELECTION_SHA256 = "C14F334F95D5100FBBA0CD690388D1DD1BAA17DC5351C9E6773F82E6D05E6B92"
SOURCE_ADJUDICATION_PATH = Path(
    "lab/holostate_v1_warm_trajectory_related_task_evaluation_v1_attempt_7_adjudication_1.json"
)
SOURCE_ADJUDICATION_SHA256 = "2E7399FA57EE31E6B83A8B76F8065D6F5E1682BA91EB561C9EDB2439DB58A925"
SOURCE_RECORD_ID = "neo-exp-0048"
SOURCE_RECORD_LINE = 61
SOURCE_RECORD_SHA256 = "DE406303E7DBAB2D8E8E95B94A5ED17DD52F1FFF5E3141112077833C58ED0A6E"
PUBLIC_CORPUS_PATH = source.PUBLIC_CORPUS_PATH
PUBLIC_CORPUS_SHA256 = source.PUBLIC_CORPUS_SHA256
PROTECTED_EVALUATOR_PATH = source.PROTECTED_EVALUATOR_PATH
PROTECTED_EVALUATOR_SHA256 = source.PROTECTED_EVALUATOR_SHA256
PROTECTED_EVALUATOR_SIZE = source.PROTECTED_EVALUATOR_SIZE
PREREGISTRATION_PATH = Path("lab/holostate_v1_inherited_task_a_carrier_evaluation_v1.json")
STATE_ROOT = Path("state/catalytic_kernel_0/holostate_v1_inherited_task_a_carrier_evaluation_v1")
ARCHIVE_ROOT = Path("state/catalytic_kernel_0/holostate_v1_inherited_task_a_carrier_evidence_archive/v1")
AUTHORITY_RECEIPT_PATH = Path(
    "state/catalytic_kernel_0_authority."
    "holostate-v1-inherited-task-a-carrier-evaluation-v1.authority.consumed.json"
)
MODEL_SHA256 = source.MODEL_SHA256
BINARY_SHA256 = source.BINARY_SHA256
RUNTIME_VERSION = source.RUNTIME_VERSION
EXPECTED_EVIDENCE_ROOT_COMMITMENT = source.EXPECTED_EVIDENCE_ROOT_COMMITMENT
PAIR_IDS = source.PAIR_IDS
TASK_A_MAX_TOKENS = source.TASK_A_MAX_TOKENS
TASK_B_MAX_TOKENS = source.TASK_B_MAX_TOKENS
MAXIMUM_GENERATIONS = 12
MAXIMUM_INFERENCE_REQUESTS = 16
CHAT_TEMPLATE_KWARGS = source.CHAT_TEMPLATE_KWARGS
MAX_CAPTURE_BYTES = source.MAX_CAPTURE_BYTES
MAX_STATE_BYTES = source.MAX_STATE_BYTES
HISTORICAL_PREFIX_COUNTS = (1004, 1052, 1031, 1098)
HISTORICAL_PROJECTION_TOKENS = 1251

REQUEST_ORDER = tuple(
    request_id
    for pair_id in PAIR_IDS
    for request_id in (
        f"{pair_id}-task-a",
        f"{pair_id}-task-b-inherited",
        f"{pair_id}-task-b-direct",
    )
)
CLOSURE_OPERATION_ORDER = tuple(
    f"{pair_id}-carrier-closure-readdress" for pair_id in PAIR_IDS
)
INFERENCE_ORDER = tuple(
    operation_id
    for pair_id in PAIR_IDS
    for operation_id in (
        f"{pair_id}-task-a",
        f"{pair_id}-task-b-inherited",
        f"{pair_id}-carrier-closure-readdress",
        f"{pair_id}-task-b-direct",
    )
)

canonical_json_bytes = source.canonical_json_bytes
canonical_json_text = source.canonical_json_text
sha256_bytes = source.sha256_bytes
sha256_file = source.sha256_file
json_sha256 = source.json_sha256
load_public_corpus = source.load_public_corpus
public_pair_sha256 = source.public_pair_sha256
protected_evaluator_custody = source.protected_evaluator_custody
parse_task_a_output = source.parse_task_a_output
parse_task_b_output = source.parse_task_b_output
task_a_messages = source.task_a_messages
task_a_payload = source.task_a_payload
task_b_messages = source.task_b_messages
structured_content_from_capture = source.structured_content_from_capture
normalized_capture_execution = source.normalized_capture_execution
RunLock = source.RunLock


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InheritedCarrierEvaluationError(message)


def _regular_bytes(path: Path, label: str, maximum: int = MAX_STATE_BYTES) -> bytes:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise InheritedCarrierEvaluationError(f"{label} is missing") from exc
    _require(path.is_file() and not path.is_symlink(), f"{label} is not a regular file")
    _require(metadata.st_size <= maximum, f"{label} exceeds its byte ceiling")
    return path.read_bytes()


def _exclusive_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _write_or_require_identical(path: Path, data: bytes) -> None:
    if path.exists():
        _require(_regular_bytes(path, str(path)) == data, f"{path} differs from exact reconstruction")
        return
    _exclusive_write(path, data)


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repository, check=True, capture_output=True, text=True, timeout=60
    )
    return completed.stdout.strip()


def _contains_exact_mapping_key(value: Any, forbidden_key: str) -> bool:
    return source._contains_exact_mapping_key(value, forbidden_key)


def _assert_public_no_smuggle(value: Any) -> None:
    source._assert_public_no_smuggle(value)


def _load_private_root(repository: Path) -> bytes:
    return source._load_private_root(repository)


def derive_seed(pair_id: str, request_role: str) -> int:
    """Preserve the exact selected source seeds rather than deriving new ones."""
    return source.derive_seed(pair_id, request_role)


def task_b_request_template(pair: Mapping[str, Any], route: str) -> dict[str, Any]:
    _require(route in {"inherited", "direct"}, "unknown Task-B route")
    sentinel = canonical_json_text(
        {"state": ["captured-state-1", "captured-state-2", "captured-state-3", "captured-state-4"], "answer": "A"}
    )
    return {
        "route": route,
        "messages": task_b_messages(pair, sentinel),
        "temperature": 0,
        "seed": derive_seed(str(pair["pair_id"]), "task-b"),
        "maximum_completion_tokens": TASK_B_MAX_TOKENS,
        "cache_prompt": route == "inherited",
        "response_schema": source.task_b_response_schema(),
        "dynamic_input": "exact authenticated Task-A JSON capture",
    }


def fixed_request_templates(corpus: Mapping[str, Any]) -> dict[str, str]:
    by_id = {str(item["pair_id"]): item for item in corpus["task_pairs"]}
    result: dict[str, str] = {}
    for pair_id in PAIR_IDS:
        pair = by_id[pair_id]
        result[f"{pair_id}-task-a"] = json_sha256(task_a_payload(pair))
        result[f"{pair_id}-task-b-inherited"] = json_sha256(
            task_b_request_template(pair, "inherited")
        )
        result[f"{pair_id}-task-b-direct"] = json_sha256(task_b_request_template(pair, "direct"))
    return result


def _callable_binding(values: Sequence[Callable[..., Any]]) -> dict[str, Any]:
    entries = [{"qualname": value.__qualname__, "source": inspect.getsource(value)} for value in values]
    return {"algorithm": "sha256-canonical-callable-source-v1", "sha256": json_sha256(entries)}


def _prompt_codec_request(port: int, endpoint: str, payload: Mapping[str, Any]) -> Any:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{endpoint}",
        data=canonical_json_bytes(payload),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


class SidecarPromptCodec:
    """Non-generating prompt renderer/tokenizer bound to the live sidecar."""

    def __init__(self, port: int) -> None:
        self.port = port

    def render_messages(self, messages: Sequence[Mapping[str, str]], kwargs: Mapping[str, Any]) -> str:
        response = _prompt_codec_request(
            self.port,
            "/apply-template",
            {"messages": list(messages), "chat_template_kwargs": dict(kwargs)},
        )
        prompt = response.get("prompt") if isinstance(response, Mapping) else None
        _require(isinstance(prompt, str), "sidecar chat template returned no prompt")
        return prompt

    def tokenize(self, value: str) -> list[int]:
        response = _prompt_codec_request(
            self.port,
            "/tokenize",
            {"content": value, "add_special": False, "parse_special": True},
        )
        tokens = response.get("tokens") if isinstance(response, Mapping) else None
        _require(isinstance(tokens, list) and all(isinstance(item, int) for item in tokens), "sidecar tokenizer returned invalid tokens")
        return list(tokens)

    def detokenize(self, token_ids: Sequence[int]) -> str:
        response = _prompt_codec_request(self.port, "/detokenize", {"tokens": list(token_ids)})
        content = response.get("content") if isinstance(response, Mapping) else None
        _require(isinstance(content, str), "sidecar detokenizer returned no content")
        return content


def _minimal_terminal_prefix_index(
    full_prompt: str,
    token_ids: Sequence[int],
    task_a_json: str,
    detokenize: Callable[[Sequence[int]], str],
) -> int:
    _require(full_prompt.count(task_a_json) == 1, "exact Task-A JSON is not unique in full Task-B prompt")
    terminal_character = full_prompt.index(task_a_json) + len(task_a_json)
    low, high = 1, len(token_ids)
    while low < high:
        middle = (low + high) // 2
        if len(detokenize(token_ids[:middle])) >= terminal_character:
            high = middle
        else:
            low = middle + 1
    index = low
    rendered = detokenize(token_ids[:index])
    _require(rendered[:terminal_character] == full_prompt[:terminal_character], "terminal prefix detokenization changed")
    if index > 1:
        _require(len(detokenize(token_ids[: index - 1])) < terminal_character, "terminal prefix is not minimal")
    return index


def derive_inherited_prefix(
    codec: Any,
    pair: Mapping[str, Any],
    task_a_json: str,
    *,
    task_a_capture_sha256: str,
) -> dict[str, Any]:
    """Purely derive the inherited prefix and dynamic Task-B request identity."""
    parse_task_a_output(task_a_json)
    _require(bool(re.fullmatch(r"[0-9A-F]{64}", task_a_capture_sha256)), "Task-A capture hash is malformed")
    messages = task_b_messages(pair, task_a_json)
    full_prompt = codec.render_messages(messages, CHAT_TEMPLATE_KWARGS)
    full_ids = codec.tokenize(full_prompt)
    _require(bool(full_ids), "full Task-B prompt tokenization is empty")
    terminal_index = _minimal_terminal_prefix_index(
        full_prompt, full_ids, task_a_json, codec.detokenize
    )
    prefix_ids = full_ids[:terminal_index]
    suffix_ids = full_ids[terminal_index:]
    prefix_prompt = codec.detokenize(prefix_ids)
    payload = source._raw_completion_payload(
        full_prompt,
        seed=derive_seed(str(pair["pair_id"]), "task-b"),
        cache_prompt=True,
        n_predict=TASK_B_MAX_TOKENS,
    )
    body = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "pair_id": str(pair["pair_id"]),
        "task_a_capture_sha256": task_a_capture_sha256,
        "task_a_json_sha256": sha256_bytes(task_a_json.encode("utf-8")),
        "full_task_b_prompt_sha256": sha256_bytes(full_prompt.encode("utf-8")),
        "full_token_sha256": sha256_bytes(canonical_json_bytes(full_ids)),
        "full_token_count": len(full_ids),
        "inherited_terminal_prefix_sha256": sha256_bytes(prefix_prompt.encode("utf-8")),
        "inherited_terminal_prefix_token_sha256": sha256_bytes(canonical_json_bytes(prefix_ids)),
        "expected_inherited_prefix_token_count": terminal_index,
        "suffix_token_sha256": sha256_bytes(canonical_json_bytes(suffix_ids)),
        "suffix_token_count": len(suffix_ids),
        "dynamic_task_b_request_sha256": json_sha256(payload),
        "cache_prompt": True,
        "maximum_completion_tokens": TASK_B_MAX_TOKENS,
        "historical_count_used_as_live_expectation": False,
    }
    return {
        **body,
        "derivation_sha256": json_sha256(body),
        "_full_prompt": full_prompt,
        "_prefix_prompt": prefix_prompt,
        "_payload": payload,
    }


def public_derivation(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if not key.startswith("_")}


def inherited_prefix_derivation_binding() -> dict[str, Any]:
    return _callable_binding(
        [_prompt_codec_request, SidecarPromptCodec.render_messages, SidecarPromptCodec.tokenize,
         SidecarPromptCodec.detokenize, _minimal_terminal_prefix_index, derive_inherited_prefix,
         public_derivation]
    )


def evaluate_inherited_reuse(
    derivation: Mapping[str, Any],
    inherited_capture: Mapping[str, Any],
    direct_capture: Mapping[str, Any],
) -> dict[str, Any]:
    inherited = normalized_capture_execution(inherited_capture)
    direct = normalized_capture_execution(direct_capture)
    expected = int(derivation["expected_inherited_prefix_token_count"])
    inherited_cached = int(inherited.get("cached_prompt_tokens") or 0)
    inherited_logical = int(inherited.get("prompt_tokens") or 0)
    direct_cached = int(direct.get("cached_prompt_tokens") or 0)
    _require(inherited_logical >= expected, "inherited Task-B prompt is shorter than its derived prefix")
    return {
        "expected_inherited_prefix_token_count": expected,
        "observed_inherited_cached_prompt_tokens": inherited_cached,
        "observed_inherited_logical_prompt_tokens": inherited_logical,
        "exact_inherited_prefix_reuse": inherited_cached == expected,
        "partial_inherited_prefix_reuse": 0 < inherited_cached < expected,
        "inherited_reuse_fraction": {"numerator": min(inherited_cached, expected), "denominator": expected},
        "direct_cached_prompt_tokens": direct_cached,
        "direct_freshness_passed": direct_cached == 0,
        "false_reuse_stops_panel": False,
    }


def closure_operation_record(
    execution: Any,
    *,
    pair_id: str,
    payload: Mapping[str, Any],
    derivation: Mapping[str, Any],
    operation_ordinal: int,
) -> dict[str, Any]:
    operation_id = f"{pair_id}-carrier-closure-readdress"
    _require(pair_id in PAIR_IDS, "closure pair changed")
    _require(CLOSURE_OPERATION_ORDER[operation_ordinal - 1] == operation_id, "closure order changed")
    _require(payload.get("cache_prompt") is True and payload.get("n_predict") == 0, "closure payload changed")
    logical = int(source._capture_value(execution, "prompt_tokens") or 0)
    reused = int(source._capture_value(execution, "cached_prompt_tokens") or 0)
    completion = int(source._capture_value(execution, "completion_tokens") or 0)
    expected = int(derivation["expected_inherited_prefix_token_count"])
    stop = source._capture_value(execution, "terminal_stop_evidence")
    _require(logical > 0 and 0 <= reused <= logical and completion == 0, "closure accounting is invalid")
    _require(
        int(source._capture_value(execution, "http_status") or 0) == 200
        and isinstance(stop, Mapping) and stop.get("observed") is True and stop.get("stop") is True,
        "closure terminal evidence is invalid",
    )
    fresh = logical - reused
    return {
        "operation_id": operation_id,
        "pair_id": pair_id,
        "operation_kind": "carrier-closure-readdress",
        "operation_ordinal": operation_ordinal,
        "derivation_sha256": derivation["derivation_sha256"],
        "payload_sha256": json_sha256(payload),
        "cache_prompt": True,
        "n_predict": 0,
        "inference_request_count": 1,
        "generation_count": 0,
        "logical_prompt_tokens": logical,
        "reused_prompt_tokens": reused,
        "fresh_prompt_tokens": fresh,
        "completion_tokens": 0,
        "fresh_prompt_plus_completion_tokens": fresh,
        "maximum_request_context": logical,
        "expected_inherited_prefix_token_count": expected,
        "exact_closure": logical == expected and reused == expected and fresh == 0,
        "partial_readdress": reused > 0 and not (logical == expected and reused == expected),
        "terminal_http_status": 200,
        "terminal_stop_evidence": dict(stop),
    }


def resource_record(capture: Mapping[str, Any], request_id: str) -> dict[str, Any]:
    execution = normalized_capture_execution(capture)
    logical = int(execution.get("prompt_tokens") or 0)
    reused = int(execution.get("cached_prompt_tokens") or 0)
    completion = int(execution.get("completion_tokens") or 0)
    _require(logical > 0 and 0 <= reused <= logical and completion > 0, "capture resource data is invalid")
    return {
        "request_id": request_id,
        "operation_id": request_id,
        "operation_kind": "model-generation",
        "inference_request_count": 1,
        "generation_count": 1,
        "logical_prompt_tokens": logical,
        "reused_prompt_tokens": reused,
        "fresh_prompt_tokens": logical - reused,
        "completion_tokens": completion,
        "fresh_prompt_plus_completion_tokens": logical - reused + completion,
        "maximum_request_context": logical + (TASK_A_MAX_TOKENS if request_id.endswith("task-a") else TASK_B_MAX_TOKENS),
    }


def exact_ratio(tokens: int, correct: int) -> dict[str, Any]:
    return {"numerator": tokens, "denominator": correct, "defined": correct > 0}


def account_resources(
    records: Sequence[Mapping[str, Any]],
    closure_operations: Sequence[Mapping[str, Any]],
    scoring: Mapping[str, Any],
) -> dict[str, Any]:
    def summarize(name: str, selected: Sequence[Mapping[str, Any]], correct: int) -> dict[str, Any]:
        fresh_prompt = sum(int(item["fresh_prompt_tokens"]) for item in selected)
        completion = sum(int(item["completion_tokens"]) for item in selected)
        total = fresh_prompt + completion
        return {
            "route": name,
            "request_count": sum(int(item["inference_request_count"]) for item in selected),
            "generation_count": sum(int(item["generation_count"]) for item in selected),
            "logical_prompt_tokens": sum(int(item["logical_prompt_tokens"]) for item in selected),
            "reused_prompt_tokens": sum(int(item["reused_prompt_tokens"]) for item in selected),
            "fresh_prompt_tokens": fresh_prompt,
            "completion_tokens": completion,
            "fresh_prompt_plus_completion_tokens": total,
            "maximum_request_context": max(int(item["maximum_request_context"]) for item in selected),
            "correct_answers": correct,
            "fresh_tokens_per_correct": exact_ratio(total, correct),
        }

    _require(tuple(item["request_id"] for item in records) == REQUEST_ORDER, "generation resource order changed")
    _require(tuple(item["operation_id"] for item in closure_operations) == CLOSURE_OPERATION_ORDER, "closure resource order changed")
    shared = [item for item in records if str(item["request_id"]).endswith("task-a")]
    inherited = [item for item in records if str(item["request_id"]).endswith("task-b-inherited")]
    direct = [item for item in records if str(item["request_id"]).endswith("task-b-direct")]
    _require(len(shared) == len(inherited) == len(direct) == len(closure_operations) == 4, "resource geometry changed")
    inherited_correct = int(scoring["inherited_task_b_correct"])
    direct_correct = int(scoring["direct_task_b_correct"])
    shared_summary = summarize("shared-task-a", shared, int(scoring["task_a_correct"]))
    inherited_b_summary = summarize("inherited-task-b-continuation", inherited, inherited_correct)
    closure_summary = summarize("immediate-closure-readdress", closure_operations, inherited_correct)
    inherited_marginal = summarize("inherited-marginal-with-closure", [*inherited, *closure_operations], inherited_correct)
    direct_summary = summarize("direct-task-b-replay", direct, direct_correct)
    all_records = [*records, *closure_operations]
    total = summarize("complete-sequence", all_records, int(scoring["inherited_task_b_correct"]) + direct_correct)
    cross = {
        "inherited_tokens_x_direct_correct": inherited_marginal["fresh_prompt_plus_completion_tokens"] * direct_correct,
        "direct_tokens_x_inherited_correct": direct_summary["fresh_prompt_plus_completion_tokens"] * inherited_correct,
    }
    strict = inherited_correct > 0 and direct_correct > 0 and cross["inherited_tokens_x_direct_correct"] < cross["direct_tokens_x_inherited_correct"]
    return {
        "shared_task_a_counted_once": shared_summary,
        "inherited_task_b": inherited_b_summary,
        "closure_readdress": closure_summary,
        "primary_inherited_marginal_including_closure": inherited_marginal,
        "direct_task_b": direct_summary,
        "total_sequence": total,
        "integer_cross_products": cross,
        "inherited_fresh_tokens_per_correct_strictly_lower": strict,
        "materialization_request_count": 0,
        "historical_projection": {"tokens": HISTORICAL_PROJECTION_TOKENS, "decision_authority": False},
    }


def classify_result(
    scoring: Mapping[str, Any],
    resources: Mapping[str, Any],
    reuse_reports: Mapping[str, Mapping[str, Any]],
    *,
    complete_panel: bool,
    cleanup_passed: bool,
    postflight_passed: bool,
) -> str:
    direct_fresh = all(item.get("direct_freshness_passed") is True for item in reuse_reports.values())
    if not (complete_panel and cleanup_passed and postflight_passed and direct_fresh):
        return "INCONCLUSIVE"
    exact_all = all(item.get("exact_inherited_prefix_reuse") is True for item in reuse_reports.values())
    if not exact_all:
        return "PROCESS_LOCAL_INHERITED_TASK_A_CARRIER_EXACT_REUSE_NOT_SUPPORTED"
    inherited_correct = int(scoring.get("inherited_task_b_correct") or 0)
    direct_correct = int(scoring.get("direct_task_b_correct") or 0)
    if inherited_correct >= direct_correct and resources.get("inherited_fresh_tokens_per_correct_strictly_lower") is True:
        return "PROCESS_LOCAL_INHERITED_TASK_A_CARRIER_FRESH_TOKEN_ADVANTAGE_SUPPORTED"
    return "PROCESS_LOCAL_INHERITED_TASK_A_CARRIER_REUSE_SUPPORTED_WITHOUT_FRESH_TOKEN_ADVANTAGE"


def scientific_binding(corpus: Mapping[str, Any]) -> dict[str, Any]:
    body = {
        "design_id": DESIGN_ID,
        "source_selection_sha256": SOURCE_SELECTION_SHA256,
        "source_adjudication_sha256": SOURCE_ADJUDICATION_SHA256,
        "source_record_sha256": SOURCE_RECORD_SHA256,
        "corpus_sha256": PUBLIC_CORPUS_SHA256,
        "pair_sha256": {str(item["pair_id"]): public_pair_sha256(item) for item in corpus["task_pairs"]},
        "request_order": list(REQUEST_ORDER),
        "inference_order": list(INFERENCE_ORDER),
        "route_order": ["task-a", "task-b-inherited", "closure-readdress", "task-b-direct"],
        "seeds": {pair_id: {"task_a": derive_seed(pair_id, "task-a"), "task_b_shared": derive_seed(pair_id, "task-b")} for pair_id in PAIR_IDS},
        "maximum_generations": MAXIMUM_GENERATIONS,
        "maximum_inference_requests": MAXIMUM_INFERENCE_REQUESTS,
        "materialization_operations": 0,
        "one_physical_slot": True,
        "one_sidecar_epoch": True,
        "one_generation_maximum_per_request": True,
        "no_retry_after_start": True,
        "fixed_request_template_sha256": fixed_request_templates(corpus),
        "request_constructor_binding": _callable_binding([task_b_request_template, source.task_a_payload, source.task_b_messages]),
        "parsers_binding": _callable_binding([source.parse_task_a_output, source.parse_task_b_output]),
    }
    return {"algorithm": "sha256-canonical-scientific-surface-v1", "sha256": json_sha256(body), "body": body}


def controller_binding() -> dict[str, Any]:
    return _callable_binding([
        build_external_authority, consume_authority_once, verify_authority_receipt,
        JournalWriter.append, capture_request_once, verify_capture,
        write_derivation_record, verify_derivation_record, _stream_raw_completion,
        closure_operation_record, evaluate_inherited_reuse, _archive_terminal,
        run_evaluation,
    ])


def scorer_binding() -> dict[str, Any]:
    return _callable_binding([
        source.protected_evaluator_custody,
        _load_protected_evaluator_after_terminal_gates,
        score_protected,
        classify_result,
    ])


def resource_binding() -> dict[str, Any]:
    return _callable_binding([resource_record, exact_ratio, account_resources])


def closure_binding() -> dict[str, Any]:
    return _callable_binding([closure_operation_record])


def build_preregistration_document(repository: Path) -> dict[str, Any]:
    corpus = load_public_corpus(repository)
    evaluator = protected_evaluator_custody(repository)
    scientific = scientific_binding(corpus)
    derivation = inherited_prefix_derivation_binding()
    controller = controller_binding()
    scorer = scorer_binding()
    resources = resource_binding()
    closure = closure_binding()
    body = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "status": "statically-preregistered-unexecuted",
        "starting_protected_main": STARTING_PROTECTED_MAIN,
        "selection_classification": "INHERITED_TASK_A_CARRIER_SELECTED",
        "source_bindings": {
            "successor_decision": {"path": SOURCE_SELECTION_PATH.as_posix(), "sha256": SOURCE_SELECTION_SHA256},
            "attempt_7_adjudication": {"path": SOURCE_ADJUDICATION_PATH.as_posix(), "sha256": SOURCE_ADJUDICATION_SHA256},
            "published_record": {"id": SOURCE_RECORD_ID, "line": SOURCE_RECORD_LINE, "sha256": SOURCE_RECORD_SHA256},
            "public_corpus": {"path": PUBLIC_CORPUS_PATH.as_posix(), "sha256": PUBLIC_CORPUS_SHA256},
            "protected_evaluator": evaluator,
        },
        "runtime_identity": {
            "model_sha256": MODEL_SHA256,
            "binary_sha256": BINARY_SHA256,
            "runtime_version": RUNTIME_VERSION,
            "physical_slot": kernel.PHYSICAL_SLOT,
        },
        "intervention": "Continue directly from the executable slot state left by Task A, without a separate fresh checkpoint-materialization request.",
        "execution": {
            "physical_slots": 1,
            "sidecar_epochs": 1,
            "pair_ids": list(PAIR_IDS),
            "pair_sequence": ["task-a", "task-b-inherited", "closure-readdress", "task-b-direct"],
            "request_order": list(REQUEST_ORDER),
            "closure_operation_order": list(CLOSURE_OPERATION_ORDER),
            "inference_order": list(INFERENCE_ORDER),
            "maximum_model_generations": MAXIMUM_GENERATIONS,
            "maximum_inference_requests": MAXIMUM_INFERENCE_REQUESTS,
            "materialization_operations": 0,
            "task_a": {"cache_prompt": False, "temperature": 0, "maximum_completion_tokens": TASK_A_MAX_TOKENS},
            "task_b_inherited": {"cache_prompt": True, "temperature": 0, "maximum_completion_tokens": TASK_B_MAX_TOKENS},
            "closure": {"cache_prompt": True, "n_predict": 0},
            "task_b_direct": {"cache_prompt": False, "temperature": 0, "maximum_completion_tokens": TASK_B_MAX_TOKENS},
            "seeds": scientific["body"]["seeds"],
            "fixed_request_template_sha256": fixed_request_templates(corpus),
            "no_inference_between_task_a_and_inherited_task_b": True,
            "fixed_route_order_not_counterbalanced": True,
            "one_generation_maximum_per_request": True,
            "scientific_retry_allowed": False,
        },
        "inherited_prefix_law": {
            "derived_after_authenticated_task_a_capture": True,
            "bound_fields": [
                "task_a_capture_sha256", "full_task_b_prompt_sha256", "full_token_sha256",
                "inherited_terminal_prefix_sha256", "inherited_terminal_prefix_token_sha256",
                "expected_inherited_prefix_token_count", "suffix_token_count",
                "dynamic_task_b_request_sha256",
            ],
            "live_gate": "cached_prompt_tokens == derived expected_inherited_prefix_token_count",
            "exact_equality_justification": "The inherited request follows a fresh Task A on one slot; the derived prefix is the maximal admissible prior sequence, so larger reuse cannot be attributed to this intervention.",
            "historical_prefix_counts": list(HISTORICAL_PREFIX_COUNTS),
            "historical_counts_are_prior_feasibility_only": True,
            "false_gate_continues_panel": True,
            "fallback_materialization": False,
            "rematerialization": False,
            "semantic_retry": False,
        },
        "resource_law": {
            "shared_task_a_reported_once": True,
            "primary_inherited_marginal": ["task-b-inherited", "closure-readdress"],
            "materialization_cost": 0,
            "actual_closure_cost_included": True,
            "historical_projection": {"tokens": HISTORICAL_PROJECTION_TOKENS, "decision_authority": False},
            "comparison": "exact integer cross-products of fresh prompt-plus-completion tokens per correct Task-B answer",
        },
        "decision_law": {
            "advantage_supported": "PROCESS_LOCAL_INHERITED_TASK_A_CARRIER_FRESH_TOKEN_ADVANTAGE_SUPPORTED",
            "reuse_without_advantage": "PROCESS_LOCAL_INHERITED_TASK_A_CARRIER_REUSE_SUPPORTED_WITHOUT_FRESH_TOKEN_ADVANTAGE",
            "exact_reuse_not_supported": "PROCESS_LOCAL_INHERITED_TASK_A_CARRIER_EXACT_REUSE_NOT_SUPPORTED",
            "inconclusive": "infrastructure, custody, incomplete panel, direct-cache contamination, evaluator, cleanup, or postflight failure only",
            "task_a_textual_latent_accuracy_is_admission_gate": False,
        },
        "protected_scoring": {
            "required_before_open": {"captures": 12, "closures": 4, "cleanup_passed": True, "postflight_passed": True},
            "read_count": 1,
            "duplicate_keys_rejected": True,
            "protected_answers_disclosed": False,
        },
        "bindings": {
            "scientific": scientific,
            "inherited_prefix_derivation": derivation,
            "controller": controller,
            "protected_scorer": scorer,
            "resource_accounting": resources,
            "closure": closure,
        },
        "authority": {"required_for_live_execution": True, "fresh_external_one_shot": True, "maximum_generations": MAXIMUM_GENERATIONS, "retry_allowed": False},
        "evidence": {
            "authenticated_captures": 12,
            "authenticated_inherited_prefix_derivations": 4,
            "closure_operation_records": 4,
            "append_only_authenticated_journal": True,
            "terminal_documents": ["receipt", "manifest", "result", "closure", "archive"],
        },
        "claim_locks": {
            "general_catalytic_inference": "LOCKED",
            "complete_catalytic_lifecycle": "LOCKED",
            "exact_restoration": "LOCKED",
            "restart_persistent_state": "LOCKED",
            "transfer_beyond_four_pairs": "LOCKED",
            "superiority": "LOCKED",
            "sota": "LOCKED",
            "automatic_promotion": False,
        },
        "runtime_artifacts_created": False,
        "model_contact": False,
        "next_action": "AUTHORIZE_ONE_LIVE_INHERITED_TASK_A_CARRIER_EVALUATION",
    }
    return {**body, "artifact_sha256": json_sha256(body)}


def write_preregistration(repository: Path) -> Path:
    path = repository / PREREGISTRATION_PATH
    data = json.dumps(build_preregistration_document(repository), ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    _write_or_require_identical(path, data)
    return path


def validate_preregistration(repository: Path) -> dict[str, Any]:
    expected = build_preregistration_document(repository)
    path = repository / PREREGISTRATION_PATH
    observed = json.loads(_regular_bytes(path, "inherited-carrier preregistration", 512 * 1024))
    _require(observed == expected, "inherited-carrier preregistration differs from exact reconstruction")
    return expected


def authority_id_sha256(raw_authority_id: str) -> str:
    _require(bool(re.fullmatch(r"[0-9a-f]{64}", raw_authority_id)), "authority ID must be lowercase 64-hex")
    return sha256_bytes(
        b"neo3000/holostate-inherited-task-a-carrier/authority-id/v1\0"
        + bytes.fromhex(raw_authority_id)
    )


def build_external_authority(
    raw_authority_id: str,
    *,
    authorized_commit: str,
    current_commit: str,
    preregistration_sha256: str,
) -> dict[str, Any]:
    _require(bool(re.fullmatch(r"[0-9a-f]{40}", authorized_commit)), "authority commit is malformed")
    _require(authorized_commit == current_commit, "authority commit differs from protected main")
    _require(bool(re.fullmatch(r"[0-9A-F]{64}", preregistration_sha256)), "preregistration hash is malformed")
    return {
        "schema_version": 1,
        "authority_kind": "external-one-shot-holostate-inherited-task-a-carrier-v1",
        "design_id": DESIGN_ID,
        "authorized_commit": authorized_commit,
        "authority_id_sha256": authority_id_sha256(raw_authority_id),
        "preregistration_file_sha256": preregistration_sha256,
        "maximum_model_generations": MAXIMUM_GENERATIONS,
        "maximum_inference_requests": MAXIMUM_INFERENCE_REQUESTS,
        "retry_allowed": False,
        "raw_authority_id_persisted": False,
    }


def _experiment_key(root: bytes) -> bytes:
    return hmac.new(
        root,
        b"neo3000/holostate-inherited-task-a-carrier/experiment-key/v1\0" + DESIGN_ID.encode("utf-8"),
        hashlib.sha256,
    ).digest()


def _authority_hmac(root: bytes, body: Mapping[str, Any]) -> str:
    return hmac.new(
        root,
        b"neo3000/holostate-inherited-task-a-carrier/authority-receipt/v1\0"
        + canonical_json_bytes(body),
        hashlib.sha256,
    ).hexdigest().upper()


def consume_authority_once(repository: Path, root: bytes, authority: Mapping[str, Any]) -> dict[str, Any]:
    path = repository / AUTHORITY_RECEIPT_PATH
    _require(not os.path.lexists(path), "inherited-carrier authority is already consumed")
    body = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "authority": dict(authority),
        "consumed_at": _utc_now(),
        "raw_authority_id_persisted": False,
    }
    document = {**body, "receipt_hmac_sha256": _authority_hmac(root, body)}
    _exclusive_write(path, canonical_json_bytes(document) + b"\n")
    return verify_authority_receipt(repository, root)


def verify_authority_receipt(repository: Path, root: bytes) -> dict[str, Any]:
    path = repository / AUTHORITY_RECEIPT_PATH
    data = _regular_bytes(path, "inherited-carrier authority receipt", 64 * 1024)
    value = json.loads(data)
    _require(isinstance(value, dict), "authority receipt is not an object")
    supplied = str(value.get("receipt_hmac_sha256", ""))
    body = {key: item for key, item in value.items() if key != "receipt_hmac_sha256"}
    _require(hmac.compare_digest(supplied, _authority_hmac(root, body)), "authority receipt HMAC changed")
    _require(
        value.get("design_id") == DESIGN_ID
        and isinstance(value.get("authority"), Mapping)
        and value["authority"].get("raw_authority_id_persisted") is False
        and value.get("raw_authority_id_persisted") is False
        and not _contains_exact_mapping_key(value, "raw_authority_id"),
        "authority receipt disclosure boundary changed",
    )
    return {**value, "receipt_sha256": sha256_bytes(data)}


class JournalWriter:
    def __init__(self, path: Path, key: bytes) -> None:
        self.path = path
        self.key = key
        self.previous = "0" * 64
        self.count = 0

    def append(
        self,
        state: str,
        *,
        request_id: str | None = None,
        facts: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = {
            "schema_version": 1,
            "design_id": DESIGN_ID,
            "ordinal": self.count + 1,
            "observed_at": _utc_now(),
            "state": state,
            "request_id": request_id,
            "facts": dict(facts or {}),
            "previous_event_sha256": self.previous,
        }
        event_sha = hmac.new(
            self.key,
            b"neo3000/holostate-inherited-task-a-carrier/journal-event/v1\0"
            + canonical_json_bytes(body),
            hashlib.sha256,
        ).hexdigest().upper()
        event = {**body, "event_sha256": event_sha}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab") as handle:
            handle.write(canonical_json_bytes(event) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.previous = event_sha
        self.count += 1
        return event


def _capture_hmac(key: bytes, body: Mapping[str, Any]) -> str:
    return hmac.new(
        key,
        b"neo3000/holostate-inherited-task-a-carrier/capture-hmac/v1\0"
        + canonical_json_bytes(body),
        hashlib.sha256,
    ).hexdigest().upper()


def capture_request_once(
    path: Path,
    partial_path: Path,
    *,
    experiment_key: bytes,
    request_id: str,
    model_request_sha256: str,
    generation_ordinal: int,
    invoke: Callable[[Callable[[bytes], None]], Any],
) -> dict[str, Any]:
    _require(request_id in REQUEST_ORDER, "capture request is outside frozen order")
    _require(1 <= generation_ordinal <= MAXIMUM_GENERATIONS, "capture ordinal changed")
    _require(not path.exists() and not partial_path.exists(), "request evidence already exists")
    partial_path.parent.mkdir(parents=True, exist_ok=True)
    byte_count = 0
    with partial_path.open("xb") as raw_handle:
        def record(line: bytes) -> None:
            nonlocal byte_count
            _require(isinstance(line, bytes) and bool(line), "raw response line is invalid")
            byte_count += len(line)
            _require(byte_count <= MAX_CAPTURE_BYTES, "raw response exceeds capture ceiling")
            raw_handle.write(line)
            raw_handle.flush()
            os.fsync(raw_handle.fileno())

        execution = invoke(record)
    raw = _regular_bytes(partial_path, "raw response spool", MAX_CAPTURE_BYTES)
    body = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "request_id": request_id,
        "model_request_sha256": model_request_sha256,
        "generation_ordinal": generation_ordinal,
        "captured_before_parsing": True,
        "raw_response_capture": {
            "encoding": "base64",
            "byte_size": len(raw),
            "sha256": sha256_bytes(raw),
            "bytes": base64.b64encode(raw).decode("ascii"),
        },
        "execution": {
            name: source._capture_value(execution, name)
            for name in source.CAPTURE_EXECUTION_FIELDS
        },
    }
    body["execution"] = normalized_capture_execution(body)
    document = {**body, "capture_hmac_sha256": _capture_hmac(experiment_key, body)}
    _exclusive_write(path, canonical_json_bytes(document) + b"\n")
    partial_path.unlink()
    return verify_capture(
        path,
        experiment_key=experiment_key,
        request_id=request_id,
        model_request_sha256=model_request_sha256,
        generation_ordinal=generation_ordinal,
    )


def verify_capture(
    path: Path,
    *,
    experiment_key: bytes,
    request_id: str,
    model_request_sha256: str,
    generation_ordinal: int,
) -> dict[str, Any]:
    data = _regular_bytes(path, "authenticated response capture", MAX_CAPTURE_BYTES)
    value = json.loads(data)
    _require(isinstance(value, dict), "capture is not an object")
    body = {key: item for key, item in value.items() if key != "capture_hmac_sha256"}
    _require(
        value.get("design_id") == DESIGN_ID
        and value.get("request_id") == request_id
        and value.get("model_request_sha256") == model_request_sha256
        and value.get("generation_ordinal") == generation_ordinal
        and value.get("captured_before_parsing") is True,
        "capture identity changed",
    )
    _require(
        hmac.compare_digest(str(value.get("capture_hmac_sha256", "")), _capture_hmac(experiment_key, body)),
        "capture HMAC changed",
    )
    raw = value.get("raw_response_capture")
    _require(isinstance(raw, Mapping), "capture raw response is malformed")
    raw_bytes = base64.b64decode(str(raw.get("bytes", "")), validate=True)
    _require(
        raw.get("encoding") == "base64"
        and raw.get("byte_size") == len(raw_bytes)
        and raw.get("sha256") == sha256_bytes(raw_bytes)
        and bool(raw_bytes),
        "capture raw response identity changed",
    )
    execution = value.get("execution")
    _require(
        isinstance(execution, Mapping) and set(execution) == set(source.CAPTURE_EXECUTION_FIELDS),
        "capture execution surface changed",
    )
    return {**value, "capture_sha256": sha256_bytes(data)}


def _derivation_hmac(key: bytes, body: Mapping[str, Any]) -> str:
    return hmac.new(
        key,
        b"neo3000/holostate-inherited-task-a-carrier/derivation-hmac/v1\0"
        + canonical_json_bytes(body),
        hashlib.sha256,
    ).hexdigest().upper()


def write_derivation_record(path: Path, key: bytes, derivation: Mapping[str, Any]) -> dict[str, Any]:
    body = public_derivation(derivation)
    document = {**body, "derivation_hmac_sha256": _derivation_hmac(key, body)}
    _exclusive_write(path, canonical_json_bytes(document) + b"\n")
    return verify_derivation_record(path, key)


def verify_derivation_record(path: Path, key: bytes) -> dict[str, Any]:
    data = _regular_bytes(path, "inherited-prefix derivation record", 128 * 1024)
    value = json.loads(data)
    _require(isinstance(value, dict), "derivation record is not an object")
    body = {key_name: item for key_name, item in value.items() if key_name != "derivation_hmac_sha256"}
    _require(
        value.get("design_id") == DESIGN_ID
        and hmac.compare_digest(str(value.get("derivation_hmac_sha256", "")), _derivation_hmac(key, body)),
        "derivation authentication changed",
    )
    _require(value.get("derivation_sha256") == json_sha256({key_name: item for key_name, item in body.items() if key_name != "derivation_sha256"}), "derivation identity changed")
    return {**value, "record_sha256": sha256_bytes(data)}


def _load_protected_evaluator_after_terminal_gates(
    repository: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    custody = protected_evaluator_custody(repository)
    path = repository / PROTECTED_EVALUATOR_PATH
    data = path.read_bytes()
    _require(len(data) == PROTECTED_EVALUATOR_SIZE, "protected evaluator byte size changed")
    observed_sha256 = sha256_bytes(data)
    _require(observed_sha256 == PROTECTED_EVALUATOR_SHA256, "protected evaluator hash changed")

    def reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            _require(key not in value, "protected evaluator contains a duplicate JSON key")
            value[key] = item
        return value

    value = json.loads(data, object_pairs_hook=reject_duplicate_keys)
    _require(
        isinstance(value, dict)
        and value.get("evaluator_id") == f"{source.FAMILY_ID}-protected-evaluator"
        and value.get("corpus_id") == source.FAMILY_ID,
        "protected evaluator identity changed",
    )
    custody.update({
        "observed_size_bytes": len(data),
        "observed_sha256": observed_sha256,
        "bytes_opened": True,
        "bytes_hashed": True,
        "bytes_parsed": True,
        "sha256_verified": True,
    })
    return value, custody


def score_protected(
    repository: Path,
    corpus: Mapping[str, Any],
    outcomes: Mapping[str, Mapping[str, Any]],
    *,
    completed_capture_ids: Sequence[str],
    completed_closure_ids: Sequence[str],
    cleanup_passed: bool,
    postflight_passed: bool,
) -> dict[str, Any]:
    _require(tuple(completed_capture_ids) == REQUEST_ORDER, "protected evaluator opened before all 12 captures")
    _require(tuple(completed_closure_ids) == CLOSURE_OPERATION_ORDER, "protected evaluator opened before all four closures")
    _require(cleanup_passed and postflight_passed, "protected evaluator opened before cleanup/postflight")
    evaluator, custody = _load_protected_evaluator_after_terminal_gates(repository)
    answers = evaluator.get("task_pairs")
    _require(isinstance(answers, Mapping) and set(answers) == set(PAIR_IDS), "protected task inventory changed")
    by_id = {str(item["pair_id"]): item for item in corpus["task_pairs"]}
    per_pair: dict[str, Any] = {}
    task_a_correct = task_a_state_correct = inherited_correct = direct_correct = 0
    for pair_id in PAIR_IDS:
        protected = answers[pair_id]
        observed = outcomes[pair_id]
        _require(protected.get("public_pair_sha256") == public_pair_sha256(by_id[pair_id]), f"protected public-pair binding changed: {pair_id}")
        task_a = observed.get("task_a")
        _require(isinstance(task_a, Mapping), f"Task-A outcome missing: {pair_id}")
        combined_state = " ".join(str(item).lower() for item in task_a.get("state", []))
        requirements = protected.get("state_required_concepts")
        _require(isinstance(requirements, list) and len(requirements) == 4, "protected state requirements changed")
        concept_matches = [any(str(term).lower() in combined_state for term in group) for group in requirements]
        state_correct = all(concept_matches)
        a_correct = task_a.get("answer") == protected.get("task_a_answer")
        i_correct = observed.get("inherited_answer") == protected.get("task_b_answer")
        d_correct = observed.get("direct_answer") == protected.get("task_b_answer")
        task_a_correct += int(a_correct)
        task_a_state_correct += int(state_correct)
        inherited_correct += int(i_correct)
        direct_correct += int(d_correct)
        per_pair[pair_id] = {
            "task_a_schema_valid": True,
            "task_a_answer_correct": a_correct,
            "task_a_state_concepts_correct": state_correct,
            "task_a_state_requirement_matches": concept_matches,
            "inherited_task_b_correct": i_correct,
            "direct_task_b_correct": d_correct,
        }
    return {
        "task_a_correct": task_a_correct,
        "task_a_textual_latent_state_correct": task_a_state_correct,
        "inherited_task_b_correct": inherited_correct,
        "direct_task_b_correct": direct_correct,
        "per_pair": per_pair,
        "textual_latent_state_is_executable_reuse_gate": False,
        "protected_evaluator_sha256": PROTECTED_EVALUATOR_SHA256,
        "protected_evaluator_custody": custody,
        "protected_answers_disclosed": False,
    }


def state_paths(repository: Path) -> dict[str, Path]:
    root = repository / STATE_ROOT
    paths = {
        "run_root": root,
        "run_lock": root / ".run.lock",
        "manifest": root / "manifest.json",
        "journal": root / "journal.jsonl",
        "result": root / "result.json",
        "closure": root / "closure.json",
        "receipt": repository / AUTHORITY_RECEIPT_PATH,
    }
    for request_id in REQUEST_ORDER:
        paths[f"capture-{request_id}"] = root / "captures" / f"{request_id}.json"
        paths[f"partial-{request_id}"] = root / "captures" / f".{request_id}.raw.partial"
    for pair_id in PAIR_IDS:
        paths[f"derivation-{pair_id}"] = root / "derivations" / f"{pair_id}.json"
    return paths


def _runtime_allowed_paths(paths: Mapping[str, Path]) -> tuple[Path, ...]:
    return tuple(path for key, path in paths.items() if key not in {"run_root", "receipt"})


def _public_preflight(full: Mapping[str, Any]) -> dict[str, Any]:
    return runtime_support._public_preflight(full)


def _raw_completion_payload(prompt: str, *, seed: int, cache_prompt: bool, n_predict: int) -> dict[str, Any]:
    return source._raw_completion_payload(prompt, seed=seed, cache_prompt=cache_prompt, n_predict=n_predict)


def _stream_raw_completion(
    *,
    port: int,
    payload: Mapping[str, Any],
    recorder: Callable[[bytes], None],
    timeout: float = 900,
) -> SimpleNamespace:
    return source._stream_raw_completion(port=port, payload=payload, recorder=recorder, timeout=timeout)


def _archive_terminal(repository: Path, paths: Mapping[str, Path]) -> dict[str, Any]:
    members: list[dict[str, Any]] = []
    source_paths: dict[str, Path] = {}
    for key in ("receipt", "manifest", "journal", "result", "closure"):
        path = paths[key]
        if path.is_file() and not path.is_symlink():
            data = path.read_bytes()
            relative = path.name
            members.append({"source": key, "path": relative, "bytes": len(data), "sha256": sha256_bytes(data)})
            source_paths[key] = path
    for request_id in REQUEST_ORDER:
        key = f"capture-{request_id}"
        path = paths[key]
        if path.is_file() and not path.is_symlink():
            data = path.read_bytes()
            relative = f"captures/{request_id}.json"
            members.append({"source": key, "path": relative, "bytes": len(data), "sha256": sha256_bytes(data)})
            source_paths[key] = path
    for pair_id in PAIR_IDS:
        key = f"derivation-{pair_id}"
        path = paths[key]
        if path.is_file() and not path.is_symlink():
            data = path.read_bytes()
            relative = f"derivations/{pair_id}.json"
            members.append({"source": key, "path": relative, "bytes": len(data), "sha256": sha256_bytes(data)})
            source_paths[key] = path
    members.sort(key=lambda item: str(item["path"]))
    body = {"schema_version": 1, "design_id": DESIGN_ID, "members": members}
    archive_sha = json_sha256(body)
    archive = repository / ARCHIVE_ROOT / archive_sha
    _require(not archive.exists(), "terminal archive content address already exists")
    for item in members:
        target = archive / str(item["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source_paths[str(item["source"])].read_bytes())
    bundle = {**body, "bundle_sha256": archive_sha}
    (archive / "bundle.json").write_bytes(canonical_json_bytes(bundle) + b"\n")
    return {
        "archive_sha256": archive_sha,
        "evidence_member_count": len(members),
        "physical_file_count": len(members) + 1,
        "path": str(archive),
    }


def _finalize_scientific_result(
    repository: Path,
    corpus: Mapping[str, Any],
    outcomes: Mapping[str, Mapping[str, Any]],
    captured: Sequence[str],
    resource_records: Sequence[Mapping[str, Any]],
    closure_records: Sequence[Mapping[str, Any]],
    derivation_records: Mapping[str, Mapping[str, Any]],
    reuse_reports: Mapping[str, Mapping[str, Any]],
    cleanup: Mapping[str, Any],
    postflight: Mapping[str, Any],
    receipt: Mapping[str, Any],
    manifest_path: Path,
    journal_head: str,
    captures: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    scoring = score_protected(
        repository,
        corpus,
        outcomes,
        completed_capture_ids=captured,
        completed_closure_ids=[str(item["operation_id"]) for item in closure_records],
        cleanup_passed=cleanup.get("passed") is True,
        postflight_passed=postflight.get("passed") is True,
    )
    resources = account_resources(resource_records, closure_records, scoring)
    classification = classify_result(
        scoring,
        resources,
        reuse_reports,
        complete_panel=tuple(captured) == REQUEST_ORDER and len(closure_records) == 4,
        cleanup_passed=cleanup.get("passed") is True,
        postflight_passed=postflight.get("passed") is True,
    )
    return {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "status": "complete",
        "terminal_classification": classification,
        "completed_model_generations": len(captured),
        "completed_inference_requests": len(captured) + len(closure_records),
        "completed_materialization_operations": 0,
        "retry_count": 0,
        "request_dispositions": {request_id: "captured" for request_id in REQUEST_ORDER},
        "closure_dispositions": {operation_id: "captured" for operation_id in CLOSURE_OPERATION_ORDER},
        "scoring": scoring,
        "resources": resources,
        "inherited_prefix_reports": dict(reuse_reports),
        "derivation_records": {
            pair_id: {
                "record_sha256": value["record_sha256"],
                "derivation_sha256": value["derivation_sha256"],
                "expected_inherited_prefix_token_count": value["expected_inherited_prefix_token_count"],
                "dynamic_task_b_request_sha256": value["dynamic_task_b_request_sha256"],
            }
            for pair_id, value in derivation_records.items()
        },
        "closure_records": list(closure_records),
        "cleanup": dict(cleanup),
        "postflight": dict(postflight),
        "authority_receipt_sha256": receipt["receipt_sha256"],
        "manifest_sha256": sha256_file(manifest_path),
        "journal_head_sha256": journal_head,
        "capture_sha256": {key: value["capture_sha256"] for key, value in captures.items()},
        "claims": {
            "bounded_inherited_carrier_efficiency": classification,
            "general_catalytic_inference": "LOCKED",
            "complete_catalytic_lifecycle": "LOCKED",
            "automatic_promotion": False,
        },
    }


def run_evaluation(args: argparse.Namespace, *, repository_root: Path | None = None) -> dict[str, Any]:
    repository = (repository_root or Path(args.repository)).resolve(strict=False)
    _require(str(args.design_id) == DESIGN_ID, "design ID changed")
    preregistration = validate_preregistration(repository)
    preregistration_file_sha = sha256_file(repository / PREREGISTRATION_PATH)
    corpus = load_public_corpus(repository)
    by_id = {str(item["pair_id"]): item for item in corpus["task_pairs"]}
    paths = state_paths(repository)
    _require(not paths["run_root"].exists(), "inherited-carrier runtime root already exists")
    _require(not paths["receipt"].exists(), "inherited-carrier authority receipt already exists")

    live = kernel.CatalyticKernel0Adapter(repository)
    args.expected_binary_sha256 = BINARY_SHA256
    args.expected_runtime_version = RUNTIME_VERSION
    full_preflight = live.preflight(
        args=args,
        repository_root=repository,
        run_root=paths["run_root"],
        allowed_paths=_runtime_allowed_paths(paths),
    )
    public_preflight = _public_preflight(full_preflight)
    current_commit = str(public_preflight["stable"]["head"])
    authority = build_external_authority(
        str(args.external_authority_id),
        authorized_commit=str(args.authorized_commit),
        current_commit=current_commit,
        preregistration_sha256=preregistration_file_sha,
    )
    root = _load_private_root(repository)
    experiment_key = _experiment_key(root)
    receipt = consume_authority_once(repository, root, authority)
    paths["run_root"].mkdir(parents=True, exist_ok=False)
    journal = JournalWriter(paths["journal"], experiment_key)
    templates = fixed_request_templates(corpus)
    manifest = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "authorized_commit": current_commit,
        "authority_receipt_sha256": receipt["receipt_sha256"],
        "authority_id_sha256": authority["authority_id_sha256"],
        "preregistration_artifact_sha256": preregistration["artifact_sha256"],
        "preregistration_file_sha256": preregistration_file_sha,
        "public_corpus_sha256": PUBLIC_CORPUS_SHA256,
        "protected_evaluator_sha256": PROTECTED_EVALUATOR_SHA256,
        "request_order": list(REQUEST_ORDER),
        "closure_operation_order": list(CLOSURE_OPERATION_ORDER),
        "inference_order": list(INFERENCE_ORDER),
        "fixed_request_template_sha256": templates,
        "maximum_model_generations": MAXIMUM_GENERATIONS,
        "maximum_inference_requests": MAXIMUM_INFERENCE_REQUESTS,
        "materialization_operations": 0,
        "route_order": ["task-a", "task-b-inherited", "closure-readdress", "task-b-direct"],
        "preflight": public_preflight,
        "retry_allowed": False,
        "raw_authority_id_persisted": False,
    }
    _exclusive_write(paths["manifest"], canonical_json_bytes(manifest) + b"\n")

    started: list[str] = []
    captured: list[str] = []
    captures: dict[str, dict[str, Any]] = {}
    outcomes: dict[str, dict[str, Any]] = {pair_id: {} for pair_id in PAIR_IDS}
    resource_records: list[dict[str, Any]] = []
    closure_records: list[dict[str, Any]] = []
    derivation_records: dict[str, dict[str, Any]] = {}
    reuse_reports: dict[str, dict[str, Any]] = {}
    sidecar: Any | None = None
    cleanup: Mapping[str, Any] = {"passed": False}
    postflight: Mapping[str, Any] = {"passed": False}
    terminal_error: BaseException | None = None

    with RunLock(paths["run_lock"]):
        journal.append("authority-consumed", facts={"authority_id_sha256": authority["authority_id_sha256"]})
        try:
            sidecar, readiness = live.launch_sidecar(preflight=full_preflight, run_id=DESIGN_ID)
            pool = live.create_lease_pool(1)
            codec = SidecarPromptCodec(live.h.PORT)
            journal.append("sidecar-ready", facts=dict(readiness))
            generation_ordinal = 0
            for pair_index, pair_id in enumerate(PAIR_IDS, start=1):
                pair = by_id[pair_id]
                task_a_id = f"{pair_id}-task-a"
                inherited_id = f"{pair_id}-task-b-inherited"
                closure_id = f"{pair_id}-carrier-closure-readdress"
                direct_id = f"{pair_id}-task-b-direct"
                with pool.lease() as lease_id:
                    _require(lease_id == kernel.PHYSICAL_SLOT, "physical slot changed")
                    _require(INFERENCE_ORDER[(pair_index - 1) * 4] == task_a_id, "Task-A order changed")
                    payload_a = task_a_payload(pair)
                    request_hash_a = json_sha256(payload_a)
                    _require(request_hash_a == templates[task_a_id], "fixed Task-A request changed")
                    before = live.boundary_custody(preflight=full_preflight, sidecar=sidecar, boundary=f"before:{task_a_id}")
                    _require(before.get("passed") is True, "Task-A pre-request custody failed")
                    generation_ordinal += 1
                    journal.append("request-started", request_id=task_a_id, facts={
                        "generation_ordinal": generation_ordinal,
                        "model_request_sha256": request_hash_a,
                        "cache_prompt": False,
                        "maximum_generations_for_request": 1,
                    })
                    started.append(task_a_id)

                    def invoke_task_a(recorder: Callable[[bytes], None]) -> Any:
                        return live.execute_request(
                            sidecar=sidecar,
                            payload=payload_a,
                            request=kernel.KernelRequest(request_id=task_a_id, ordinal=generation_ordinal),
                            raw_line_recorder=recorder,
                        )

                    capture_a = capture_request_once(
                        paths[f"capture-{task_a_id}"], paths[f"partial-{task_a_id}"],
                        experiment_key=experiment_key, request_id=task_a_id,
                        model_request_sha256=request_hash_a, generation_ordinal=generation_ordinal,
                        invoke=invoke_task_a,
                    )
                    captured.append(task_a_id)
                    captures[task_a_id] = capture_a
                    resource_records.append(resource_record(capture_a, task_a_id))
                    task_a_json = structured_content_from_capture(capture_a)
                    outcomes[pair_id]["task_a"] = parse_task_a_output(task_a_json)
                    journal.append("request-captured", request_id=task_a_id, facts={"capture_sha256": capture_a["capture_sha256"]})
                    after_task_a = live.boundary_custody(
                        preflight=full_preflight, sidecar=sidecar, boundary=f"after:{task_a_id}"
                    )
                    _require(after_task_a.get("passed") is True, "Task-A post-request custody failed")

                    # Only deterministic capture authentication, parsing, prompt rendering,
                    # and tokenization occur here; no inference request can intervene.
                    derivation = derive_inherited_prefix(
                        codec, pair, task_a_json, task_a_capture_sha256=capture_a["capture_sha256"]
                    )
                    derivation_record = write_derivation_record(
                        paths[f"derivation-{pair_id}"], experiment_key, derivation
                    )
                    derivation_records[pair_id] = derivation_record
                    journal.append("inherited-prefix-derived", request_id=inherited_id, facts={
                        "record_sha256": derivation_record["record_sha256"],
                        "derivation_sha256": derivation_record["derivation_sha256"],
                        "dynamic_task_b_request_sha256": derivation_record["dynamic_task_b_request_sha256"],
                        "expected_inherited_prefix_token_count": derivation_record["expected_inherited_prefix_token_count"],
                    })

                    _require(INFERENCE_ORDER[(pair_index - 1) * 4 + 1] == inherited_id, "inherited Task-B order changed")
                    _require(REQUEST_ORDER[len(started)] == inherited_id, "generation order changed before inherited Task B")
                    inherited_payload = derivation["_payload"]
                    inherited_hash = json_sha256(inherited_payload)
                    _require(inherited_hash == derivation_record["dynamic_task_b_request_sha256"], "dynamic inherited request changed after binding")
                    before_inherited = live.boundary_custody(
                        preflight=full_preflight, sidecar=sidecar, boundary=f"before:{inherited_id}"
                    )
                    _require(before_inherited.get("passed") is True, "inherited Task-B pre-request custody failed")
                    generation_ordinal += 1
                    journal.append("request-started", request_id=inherited_id, facts={
                        "generation_ordinal": generation_ordinal,
                        "model_request_sha256": inherited_hash,
                        "request_template_sha256": templates[inherited_id],
                        "derivation_record_sha256": derivation_record["record_sha256"],
                        "maximum_generations_for_request": 1,
                    })
                    started.append(inherited_id)

                    def invoke_inherited(recorder: Callable[[bytes], None]) -> Any:
                        return sidecar.guarded(
                            f"inherited-task-a-carrier:{inherited_id}",
                            lambda: _stream_raw_completion(port=live.h.PORT, payload=inherited_payload, recorder=recorder),
                            timeout=1_000,
                        )

                    capture_inherited = capture_request_once(
                        paths[f"capture-{inherited_id}"], paths[f"partial-{inherited_id}"],
                        experiment_key=experiment_key, request_id=inherited_id,
                        model_request_sha256=inherited_hash, generation_ordinal=generation_ordinal,
                        invoke=invoke_inherited,
                    )
                    captured.append(inherited_id)
                    captures[inherited_id] = capture_inherited
                    resource_records.append(resource_record(capture_inherited, inherited_id))
                    outcomes[pair_id]["inherited_answer"] = parse_task_b_output(structured_content_from_capture(capture_inherited))
                    journal.append("request-captured", request_id=inherited_id, facts={"capture_sha256": capture_inherited["capture_sha256"]})
                    after_inherited = live.boundary_custody(
                        preflight=full_preflight, sidecar=sidecar, boundary=f"after:{inherited_id}"
                    )
                    _require(after_inherited.get("passed") is True, "inherited Task-B post-request custody failed")

                    _require(INFERENCE_ORDER[(pair_index - 1) * 4 + 2] == closure_id, "closure order changed")
                    closure_payload = _raw_completion_payload(
                        str(derivation["_prefix_prompt"]),
                        seed=derive_seed(pair_id, "task-b"),
                        cache_prompt=True,
                        n_predict=0,
                    )
                    before_closure = live.boundary_custody(
                        preflight=full_preflight, sidecar=sidecar, boundary=f"before:{closure_id}"
                    )
                    _require(before_closure.get("passed") is True, "closure pre-request custody failed")
                    closure_execution = sidecar.guarded(
                        f"inherited-task-a-carrier:{closure_id}",
                        lambda: _stream_raw_completion(port=live.h.PORT, payload=closure_payload, recorder=lambda _line: None),
                        timeout=1_000,
                    )
                    closure_record = closure_operation_record(
                        closure_execution, pair_id=pair_id, payload=closure_payload,
                        derivation=derivation_record, operation_ordinal=pair_index,
                    )
                    closure_records.append(closure_record)
                    journal.append("closure-operation-captured", request_id=closure_id, facts=closure_record)
                    after_closure = live.boundary_custody(
                        preflight=full_preflight, sidecar=sidecar, boundary=f"after:{closure_id}"
                    )
                    _require(after_closure.get("passed") is True, "closure post-request custody failed")

                    _require(INFERENCE_ORDER[(pair_index - 1) * 4 + 3] == direct_id, "direct Task-B order changed")
                    _require(REQUEST_ORDER[len(started)] == direct_id, "generation order changed before direct Task B")
                    direct_payload = _raw_completion_payload(
                        str(derivation["_full_prompt"]),
                        seed=derive_seed(pair_id, "task-b"),
                        cache_prompt=False,
                        n_predict=TASK_B_MAX_TOKENS,
                    )
                    direct_hash = json_sha256(direct_payload)
                    before_direct = live.boundary_custody(
                        preflight=full_preflight, sidecar=sidecar, boundary=f"before:{direct_id}"
                    )
                    _require(before_direct.get("passed") is True, "direct Task-B pre-request custody failed")
                    generation_ordinal += 1
                    journal.append("request-started", request_id=direct_id, facts={
                        "generation_ordinal": generation_ordinal,
                        "model_request_sha256": direct_hash,
                        "request_template_sha256": templates[direct_id],
                        "dynamic_task_a_capture_sha256": capture_a["capture_sha256"],
                        "maximum_generations_for_request": 1,
                    })
                    started.append(direct_id)

                    def invoke_direct(recorder: Callable[[bytes], None]) -> Any:
                        return sidecar.guarded(
                            f"inherited-task-a-carrier:{direct_id}",
                            lambda: _stream_raw_completion(port=live.h.PORT, payload=direct_payload, recorder=recorder),
                            timeout=1_000,
                        )

                    capture_direct = capture_request_once(
                        paths[f"capture-{direct_id}"], paths[f"partial-{direct_id}"],
                        experiment_key=experiment_key, request_id=direct_id,
                        model_request_sha256=direct_hash, generation_ordinal=generation_ordinal,
                        invoke=invoke_direct,
                    )
                    captured.append(direct_id)
                    captures[direct_id] = capture_direct
                    resource_records.append(resource_record(capture_direct, direct_id))
                    outcomes[pair_id]["direct_answer"] = parse_task_b_output(structured_content_from_capture(capture_direct))
                    journal.append("request-captured", request_id=direct_id, facts={"capture_sha256": capture_direct["capture_sha256"]})
                    after_direct = live.boundary_custody(
                        preflight=full_preflight, sidecar=sidecar, boundary=f"after:{direct_id}"
                    )
                    _require(after_direct.get("passed") is True, "direct Task-B post-request custody failed")

                    reuse = evaluate_inherited_reuse(derivation_record, capture_inherited, capture_direct)
                    reuse_reports[pair_id] = reuse
                    journal.append("pair-closed", facts={
                        "pair_id": pair_id,
                        "exact_inherited_prefix_reuse": reuse["exact_inherited_prefix_reuse"],
                        "partial_inherited_prefix_reuse": reuse["partial_inherited_prefix_reuse"],
                        "continued_after_scientific_gate_failure": not reuse["exact_inherited_prefix_reuse"],
                        "direct_freshness_passed": reuse["direct_freshness_passed"],
                        "exact_closure": closure_record["exact_closure"],
                        "partial_readdress": closure_record["partial_readdress"],
                    })
            _require(tuple(started) == REQUEST_ORDER and tuple(captured) == REQUEST_ORDER, "execution did not complete exact frozen generation order")
            _require(tuple(item["operation_id"] for item in closure_records) == CLOSURE_OPERATION_ORDER, "execution did not complete exact closure order")
            _require(len(captured) == MAXIMUM_GENERATIONS and len(captured) + len(closure_records) == MAXIMUM_INFERENCE_REQUESTS, "execution ceilings changed")
        except BaseException as exc:
            terminal_error = exc
        finally:
            try:
                cleanup = live.cleanup(sidecar=sidecar, preflight=full_preflight)
            except BaseException as exc:
                cleanup = {"passed": False, "error_sha256": sha256_bytes(str(exc).encode("utf-8"))}
                if terminal_error is None:
                    terminal_error = exc
            try:
                postflight = live.postflight(preflight=full_preflight)
            except BaseException as exc:
                postflight = {"passed": False, "error_sha256": sha256_bytes(str(exc).encode("utf-8"))}
                if terminal_error is None:
                    terminal_error = exc

        if terminal_error is None:
            try:
                result = _finalize_scientific_result(
                    repository, corpus, outcomes, captured, resource_records, closure_records,
                    derivation_records, reuse_reports, cleanup, postflight, receipt,
                    paths["manifest"], journal.previous, captures,
                )
            except BaseException as exc:
                terminal_error = exc
        if terminal_error is not None:
            result = {
                "schema_version": 1,
                "design_id": DESIGN_ID,
                "status": "inconclusive",
                "terminal_classification": "INCONCLUSIVE",
                "completed_model_generations": len(captured),
                "completed_inference_requests": len(captured) + len(closure_records),
                "completed_materialization_operations": 0,
                "retry_count": 0,
                "started_requests": list(started),
                "captured_requests": list(captured),
                "failure": {"type": type(terminal_error).__name__, "message_sha256": sha256_bytes(str(terminal_error).encode("utf-8"))},
                "cleanup": dict(cleanup),
                "postflight": dict(postflight),
                "authority_receipt_sha256": receipt["receipt_sha256"],
                "manifest_sha256": sha256_file(paths["manifest"]),
                "journal_head_sha256": journal.previous,
                "claims": {"general_catalytic_inference": "LOCKED", "automatic_promotion": False},
            }
        _exclusive_write(paths["result"], canonical_json_bytes(result) + b"\n")
        closure_document = {
            "schema_version": 1,
            "design_id": DESIGN_ID,
            "status": result["status"],
            "result_sha256": sha256_file(paths["result"]),
            "manifest_sha256": sha256_file(paths["manifest"]),
            "authority_receipt_sha256": receipt["receipt_sha256"],
            "journal_sha256": sha256_file(paths["journal"]),
            "journal_head_sha256": journal.previous,
            "run_lock_owned_during_terminal_write": True,
            "retry_allowed": False,
        }
        _exclusive_write(paths["closure"], canonical_json_bytes(closure_document) + b"\n")

    archive = _archive_terminal(repository, paths)
    return {**result, "closure_sha256": sha256_file(paths["closure"]), "archive": archive}


class _OfflineByteCodec:
    """Synthetic deterministic codec for zero-contact capture replay."""

    @staticmethod
    def render_messages(messages: Sequence[Mapping[str, str]], _kwargs: Mapping[str, Any]) -> str:
        return "".join(f"<{item['role']}>{item['content']}</{item['role']}>\n" for item in messages)

    @staticmethod
    def tokenize(value: str) -> list[int]:
        return list(value.encode("utf-8"))

    @staticmethod
    def detokenize(token_ids: Sequence[int]) -> str:
        return bytes(token_ids).decode("utf-8")


def _verify_source_bindings(repository: Path) -> dict[str, Any]:
    _require(sha256_file(repository / SOURCE_SELECTION_PATH) == SOURCE_SELECTION_SHA256, "successor selection artifact changed")
    _require(sha256_file(repository / SOURCE_ADJUDICATION_PATH) == SOURCE_ADJUDICATION_SHA256, "Attempt-7 adjudication changed")
    selection = json.loads(_regular_bytes(repository / SOURCE_SELECTION_PATH, "successor selection", 256 * 1024))
    _require(selection.get("selection_classification") == "INHERITED_TASK_A_CARRIER_SELECTED", "successor selection classification changed")
    lines = (repository / "lab/results.jsonl").read_text(encoding="utf-8").splitlines()
    _require(len(lines) >= SOURCE_RECORD_LINE, "source result record is missing")
    record = json.loads(lines[SOURCE_RECORD_LINE - 1])
    _require(record.get("id") == SOURCE_RECORD_ID, "source result record ID changed")
    _require(json_sha256(record) == SOURCE_RECORD_SHA256, "source result record hash changed")
    return {
        "selection_sha256": SOURCE_SELECTION_SHA256,
        "adjudication_sha256": SOURCE_ADJUDICATION_SHA256,
        "record_id": SOURCE_RECORD_ID,
        "record_line": SOURCE_RECORD_LINE,
        "record_sha256": SOURCE_RECORD_SHA256,
    }


def offline_replay_attempt_7_task_a_captures(repository: Path) -> dict[str, Any]:
    """Authenticate real Attempt-7 Task-A captures and exercise all derivations offline."""
    corpus = load_public_corpus(repository)
    by_id = {str(item["pair_id"]): item for item in corpus["task_pairs"]}
    root = _load_private_root(repository)
    source_key = source._experiment_key(root)
    source_paths = source.state_paths(repository)
    source_templates = source.fixed_request_templates(corpus)
    replay: dict[str, Any] = {}
    for pair_id in PAIR_IDS:
        request_id = f"{pair_id}-task-a"
        ordinal = source.REQUEST_ORDER.index(request_id) + 1
        capture = source.verify_capture(
            source_paths[f"capture-{request_id}"],
            experiment_key=source_key,
            request_id=request_id,
            model_request_sha256=source_templates[request_id],
            generation_ordinal=ordinal,
        )
        task_a_json = structured_content_from_capture(capture)
        derivation = derive_inherited_prefix(
            _OfflineByteCodec(),
            by_id[pair_id],
            task_a_json,
            task_a_capture_sha256=capture["capture_sha256"],
        )
        replay[pair_id] = {
            "source_capture_sha256": capture["capture_sha256"],
            "derivation_sha256": derivation["derivation_sha256"],
            "synthetic_prefix_token_count": derivation["expected_inherited_prefix_token_count"],
            "synthetic_suffix_token_count": derivation["suffix_token_count"],
            "raw_task_a_output_disclosed": False,
        }
    return replay


def validate_static(repository: Path) -> dict[str, Any]:
    preregistration = validate_preregistration(repository)
    source_bindings = _verify_source_bindings(repository)
    corpus = load_public_corpus(repository)
    replay = offline_replay_attempt_7_task_a_captures(repository)
    paths = state_paths(repository)
    _require(len(REQUEST_ORDER) == MAXIMUM_GENERATIONS == 12, "generation ceiling changed")
    _require(len(INFERENCE_ORDER) == MAXIMUM_INFERENCE_REQUESTS == 16, "inference-request ceiling changed")
    _require(len(CLOSURE_OPERATION_ORDER) == 4, "closure geometry changed")
    _require(not any("material" in item.lower() for item in INFERENCE_ORDER), "materialization request exists")
    for pair_id in PAIR_IDS:
        expected = (
            f"{pair_id}-task-a",
            f"{pair_id}-task-b-inherited",
            f"{pair_id}-carrier-closure-readdress",
            f"{pair_id}-task-b-direct",
        )
        offset = PAIR_IDS.index(pair_id) * 4
        _require(INFERENCE_ORDER[offset : offset + 4] == expected, f"pair order changed: {pair_id}")
    _require(not paths["run_root"].exists(), "live runtime root exists")
    _require(not paths["receipt"].exists(), "live authority receipt exists")
    _require(not (repository / ARCHIVE_ROOT).exists(), "live archive root exists")
    _require(len(replay) == 4, "Attempt-7 offline derivation replay is incomplete")
    return {
        "status": "pass",
        "design_id": DESIGN_ID,
        "source_bindings": source_bindings,
        "artifact_sha256": preregistration["artifact_sha256"],
        "preregistration_file_sha256": sha256_file(repository / PREREGISTRATION_PATH),
        "public_corpus_sha256": PUBLIC_CORPUS_SHA256,
        "protected_evaluator_sha256": PROTECTED_EVALUATOR_SHA256,
        "pair_ids": list(PAIR_IDS),
        "request_order": list(REQUEST_ORDER),
        "inference_order": list(INFERENCE_ORDER),
        "seeds": preregistration["execution"]["seeds"],
        "fixed_request_template_sha256": fixed_request_templates(corpus),
        "bindings": {key: value["sha256"] for key, value in preregistration["bindings"].items()},
        "offline_attempt_7_task_a_replay": replay,
        "proofs": {
            "materialization_operations": 0,
            "maximum_generations": 12,
            "maximum_inference_requests": 16,
            "same_slot_and_no_intervening_inference": True,
            "dynamic_identity_bound_before_contact": True,
            "false_reuse_continues_panel": True,
            "retry_paths": 0,
            "direct_cache_prompt": False,
            "actual_closure_cost_counted": True,
            "historical_projection_has_decision_authority": False,
            "textual_latent_scoring_is_reuse_gate": False,
            "protected_evaluator_delayed": True,
        },
        "runtime_artifacts_absent": True,
        "authority_receipt_absent": True,
        "archive_absent": True,
        "model_requests_issued": 0,
        "sidecar_launches": 0,
        "model_generations": 0,
        "next_action": "AUTHORIZE_ONE_LIVE_INHERITED_TASK_A_CARRIER_EVALUATION",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write-preregistration", "validate", "run"))
    parser.add_argument("--repository", required=True)
    parser.add_argument("--binary")
    parser.add_argument("--model")
    parser.add_argument("--design-id", default=DESIGN_ID)
    parser.add_argument("--external-authority-id")
    parser.add_argument("--authorized-commit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository = Path(args.repository).resolve(strict=False)
    try:
        if args.action == "write-preregistration":
            result: Any = {"status": "written", "path": str(write_preregistration(repository))}
        elif args.action == "validate":
            result = validate_static(repository)
        else:
            _require(
                all((args.binary, args.model, args.external_authority_id, args.authorized_commit)),
                "live run arguments are incomplete",
            )
            result = run_evaluation(args, repository_root=repository)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(canonical_json_text({"status": "fail", "error": str(exc)}))
        return 1
    print(canonical_json_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
