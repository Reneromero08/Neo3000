#!/usr/bin/env python3
"""Prepare, validate, or run the bounded HoloState warm-trajectory evaluation."""
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
import stat as stat_module
import subprocess
import time
import urllib.request
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Sequence

import catalytic_inference_bench_0_runtime as runtime_support
import catalytic_kernel_0 as kernel
import catalytic_kernel_0_balanced_rank_head_v2_joint_condition_intersection_replication as private_binding


class WarmTrajectoryEvaluationError(ValueError):
    """The frozen design, live custody, or scientific decision law changed."""


DESIGN_ID = "holostate-v1-warm-trajectory-related-task-evaluation-v1"
FAMILY_ID = "holostate-v1-warm-trajectory-related-task-family-v1"
STARTING_PROTECTED_MAIN = "1a07ca0cc366d53e682e13440810716533f60f98"
PUBLIC_CORPUS_PATH = Path(
    "lab/holostate_v1_warm_trajectory_related_task_family_v1_public_tasks.json"
)
PUBLIC_CORPUS_SHA256 = "A45FF0A6DCD8E3E75CBE0B0F7A572DB023B0E7CE81093F7C82155D0A4DC3D4A9"
PROTECTED_EVALUATOR_PATH = Path(
    "state/catalytic_kernel_0_private/"
    "holostate_v1_warm_trajectory_related_task_family_v1_evaluator.json"
)
PROTECTED_EVALUATOR_SHA256 = "AAC8CC0DEE3C748F92A9BA350E8EF32063171F5AF9B24754D55B1A7E71B0BE3E"
PROTECTED_EVALUATOR_SIZE = 1895
PREREGISTRATION_PATH = Path(
    "lab/holostate_v1_warm_trajectory_related_task_evaluation_v1.json"
)
STATE_ROOT = Path(
    "state/catalytic_kernel_0/holostate_v1_warm_trajectory_related_task_evaluation_v1"
)
ARCHIVE_ROOT = Path(
    "state/catalytic_kernel_0/holostate_v1_warm_trajectory_related_task_evidence_archive/v1"
)
AUTHORITY_RECEIPT_PATH = Path(
    "state/catalytic_kernel_0_authority."
    "holostate-v1-warm-trajectory-related-task-evaluation-v1.authority.consumed.json"
)
EXPECTED_EVIDENCE_ROOT_COMMITMENT = (
    "7999FE7862527BE08589EFF15B8AD7CFBC9F81C44C1FB7804E0AF31F34BD72FD"
)
MODEL_SHA256 = "31AEFA25B7E1EDBDE436E643E2B5E3F6E57820A4811D97B131130E48FF0772C2"
BINARY_SHA256 = "5D0C5F7CE5CEBE35B564C21521ECD426F809445521D3C55C0581A9543F15541B"
PAIR_IDS = (
    "warm-trajectory-archive-01",
    "warm-trajectory-refuge-02",
    "warm-trajectory-observatory-03",
    "warm-trajectory-clinic-04",
)
ROUTE_ORDER = {
    PAIR_IDS[0]: ("catalytic", "direct"),
    PAIR_IDS[1]: ("direct", "catalytic"),
    PAIR_IDS[2]: ("catalytic", "direct"),
    PAIR_IDS[3]: ("direct", "catalytic"),
}
REQUEST_ORDER = tuple(
    request_id
    for pair_id in PAIR_IDS
    for request_id in (
        f"{pair_id}-task-a",
        *(f"{pair_id}-task-b-{route}" for route in ROUTE_ORDER[pair_id]),
    )
)
TASK_A_MAX_TOKENS = 512
TASK_B_MAX_TOKENS = 128
MAXIMUM_GENERATIONS = 12
CHAT_TEMPLATE_KWARGS = {"enable_thinking": False}
ALLOWED_ANSWERS = ("A", "B", "C", "D")
MAX_CAPTURE_BYTES = 8 * 1024 * 1024
MAX_STATE_BYTES = 16 * 1024 * 1024
PRIVATE_FORBIDDEN_PUBLIC_KEYS = {
    "expected_answer",
    "answer_key",
    "state_required_concepts",
    "task_a_answer",
    "task_b_answer",
    "raw_authority_id",
    "evidence_root",
}
POST_HOC_XOR_ACCOUNTING = {
    "classification": "POST_HOC_WORKER_PLUS_CONTROLLER_XOR_ACCOUNTING_DIAGNOSTIC",
    "source_record_id": "neo-exp-0047",
    "source_record_sha256": "B253E5AD9C4861CCCBF05AD1F67F5ED28E097A06418F113A4F123E220E0D21D4",
    "source_attempt": 3,
    "model_synthesis_requests_excluded": 4,
    "worker_plus_controller_route": {
        "request_count": 8,
        "generation_count": 8,
        "logical_prompt_tokens": 1668,
        "reused_prompt_tokens": 0,
        "fresh_prompt_tokens": 1668,
        "completion_tokens": 83,
        "fresh_prompt_plus_completion_tokens": 1751,
        "correct_final_labels": 4,
        "tokens_per_correct": {"numerator": 1751, "denominator": 4},
        "maximum_request_context": 244,
    },
    "direct_baseline_route": {
        "request_count": 4,
        "generation_count": 4,
        "logical_prompt_tokens": 1373,
        "reused_prompt_tokens": 0,
        "fresh_prompt_tokens": 1373,
        "completion_tokens": 57,
        "fresh_prompt_plus_completion_tokens": 1430,
        "correct_final_labels": 3,
        "tokens_per_correct": {"numerator": 1430, "denominator": 3},
        "maximum_request_context": 380,
    },
    "integer_cross_products": {
        "worker_tokens_x_direct_correct": 5253,
        "direct_tokens_x_worker_correct": 5720,
    },
    "strict_post_hoc_fresh_token_advantage": True,
    "scientific_status": "post-hoc-not-confirmatory",
    "line_closed": True,
}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_json_text(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise WarmTrajectoryEvaluationError(message)


def _regular_bytes(path: Path, label: str, maximum: int = MAX_STATE_BYTES) -> bytes:
    _require(path.is_file() and not path.is_symlink(), f"{label} is missing or unsafe")
    data = path.read_bytes()
    _require(0 < len(data) <= maximum, f"{label} size is outside its bound")
    return data


def _exclusive_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _write_or_require_identical(path: Path, data: bytes) -> None:
    if path.exists():
        _require(path.is_file() and not path.is_symlink(), f"unsafe existing path: {path}")
        _require(path.read_bytes() == data, f"existing file differs: {path}")
        return
    _exclusive_write(path, data)


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repository, capture_output=True, text=True, timeout=60
    )
    _require(completed.returncode == 0, f"Git query failed: {' '.join(args)}")
    return completed.stdout.strip()


def _assert_public_no_smuggle(value: Any) -> None:
    def visit(node: Any) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                _require(str(key).lower() not in PRIVATE_FORBIDDEN_PUBLIC_KEYS, "private key entered public data")
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)


def load_public_corpus(repository: Path) -> dict[str, Any]:
    path = repository / PUBLIC_CORPUS_PATH
    data = _regular_bytes(path, "public warm-trajectory corpus", 128 * 1024)
    _require(sha256_bytes(data) == PUBLIC_CORPUS_SHA256, "public corpus hash changed")
    value = json.loads(data)
    _require(isinstance(value, dict), "public corpus is not an object")
    _assert_public_no_smuggle(value)
    pairs = value.get("task_pairs")
    _require(isinstance(pairs, list) and len(pairs) == 4, "public corpus must contain four task pairs")
    _require(tuple(item.get("pair_id") for item in pairs) == PAIR_IDS, "task-pair order changed")
    for item in pairs:
        _require(set(item) == {"pair_id", "evidence", "task_a", "task_b"}, "task-pair surface changed")
        words = re.findall(r"\b[\w’'-]+\b", str(item["evidence"]), flags=re.UNICODE)
        _require(500 <= len(words) <= 1000, f"{item['pair_id']} evidence must contain 500-1000 words")
        for task_name in ("task_a", "task_b"):
            task = item[task_name]
            _require(
                isinstance(task, Mapping)
                and set(task) == {"question", "choices"}
                and tuple(task["choices"]) == ALLOWED_ANSWERS,
                f"{item['pair_id']} {task_name} surface changed",
            )
    return value


def public_pair_sha256(pair: Mapping[str, Any]) -> str:
    return json_sha256(pair)


def protected_evaluator_custody(repository: Path) -> dict[str, Any]:
    path = repository / PROTECTED_EVALUATOR_PATH
    _require(path.exists(), "protected evaluator is missing or unsafe")
    metadata = path.lstat()
    file_attributes = int(getattr(metadata, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    _require(
        stat_module.S_ISREG(metadata.st_mode)
        and not path.is_symlink()
        and file_attributes & reparse_flag == 0,
        "protected evaluator is missing or unsafe",
    )
    _require(metadata.st_size == PROTECTED_EVALUATOR_SIZE, "protected evaluator size changed")
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", PROTECTED_EVALUATOR_PATH.as_posix()],
        cwd=repository,
        timeout=30,
    )
    _require(ignored.returncode == 0, "protected evaluator must remain ignored")
    tracked = _git(repository, "ls-files", "--", PROTECTED_EVALUATOR_PATH.as_posix())
    _require(not tracked, "protected evaluator must remain untracked")
    return {
        "path": PROTECTED_EVALUATOR_PATH.as_posix(),
        "expected_sha256_from_tracked_binding": PROTECTED_EVALUATOR_SHA256,
        "expected_size_bytes_from_tracked_binding": PROTECTED_EVALUATOR_SIZE,
        "size_bytes_from_filesystem_metadata": int(metadata.st_size),
        "regular": True,
        "symlink": False,
        "reparse_point": False,
        "ignored": True,
        "tracked": False,
        "bytes_opened": False,
        "bytes_hashed": False,
        "bytes_parsed": False,
        "sha256_verified": False,
    }


def _load_private_root(repository: Path) -> bytes:
    root, private = private_binding._load_private(repository.resolve(strict=False))
    _require(len(root) == 32, "private evidence-root length changed")
    _require(
        private.secret_commitment == EXPECTED_EVIDENCE_ROOT_COMMITMENT,
        "private evidence-root custody changed",
    )
    return root


def derive_seed(pair_id: str, request_role: str) -> int:
    _require(pair_id in PAIR_IDS, "unknown pair for seed derivation")
    _require(request_role in {"task-a", "task-b"}, "unknown role for seed derivation")
    digest = hashlib.sha256(
        f"{DESIGN_ID}|{PUBLIC_CORPUS_SHA256}|{pair_id}|{request_role}|seed-v1".encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def task_a_response_schema() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "warm_trajectory_task_a",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["state", "answer"],
                "properties": {
                    "state": {
                        "type": "array",
                        "minItems": 4,
                        "maxItems": 8,
                        "items": {"type": "string", "maxLength": 192},
                    },
                    "answer": {"type": "string", "enum": list(ALLOWED_ANSWERS)},
                },
            },
        },
    }


def task_b_response_schema() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "warm_trajectory_task_b",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["answer"],
                "properties": {"answer": {"type": "string", "enum": list(ALLOWED_ANSWERS)}},
            },
        },
    }


def _choice_text(task: Mapping[str, Any]) -> str:
    return "\n".join(f"{label}. {task['choices'][label]}" for label in ALLOWED_ANSWERS)


def task_a_messages(pair: Mapping[str, Any]) -> list[dict[str, str]]:
    system = (
        "Use only the supplied evidence. Derive a compact reusable latent state, then answer the "
        "multiple-choice question. Return only the required JSON. The state must contain four to "
        "eight atomic invariant strings, each at most 24 words. Do not add rationale outside JSON."
    )
    user = (
        f"EVIDENCE\n{pair['evidence']}\n\nTASK A\n{pair['task_a']['question']}\n"
        f"{_choice_text(pair['task_a'])}\n\nReturn exactly the declared Task-A JSON schema."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def task_a_payload(pair: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "model": "neo3000-holostate",
        "messages": task_a_messages(pair),
        "temperature": 0,
        "seed": derive_seed(str(pair["pair_id"]), "task-a"),
        "max_tokens": TASK_A_MAX_TOKENS,
        "stream": True,
        "cache_prompt": False,
        "chat_template_kwargs": CHAT_TEMPLATE_KWARGS,
        "response_format": task_a_response_schema(),
    }


def parse_task_a_output(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise WarmTrajectoryEvaluationError("Task-A output is not JSON") from exc
    _require(isinstance(value, dict) and set(value) == {"state", "answer"}, "Task-A output shape changed")
    state = value["state"]
    _require(isinstance(state, list) and 4 <= len(state) <= 8, "Task-A state count is outside 4-8")
    for item in state:
        _require(isinstance(item, str) and item.strip() == item and item, "Task-A state item is invalid")
        _require(len(item.split()) <= 24, "Task-A state item exceeds 24 words")
    _require(value["answer"] in ALLOWED_ANSWERS, "Task-A answer is invalid")
    return {"state": list(state), "answer": value["answer"]}


def checkpoint_messages(pair: Mapping[str, Any], task_a_json: str) -> list[dict[str, str]]:
    parse_task_a_output(task_a_json)
    return [*task_a_messages(pair), {"role": "assistant", "content": task_a_json}]


def task_b_user_message(pair: Mapping[str, Any]) -> dict[str, str]:
    task = pair["task_b"]
    content = (
        "TASK B\nTransform the preserved Task-A state for this different question. "
        "Use the same evidence and return only JSON of the form {\"answer\":\"A\"}.\n"
        f"{task['question']}\n{_choice_text(task)}"
    )
    return {"role": "user", "content": content}


def task_b_messages(pair: Mapping[str, Any], task_a_json: str) -> list[dict[str, str]]:
    return [*checkpoint_messages(pair, task_a_json), task_b_user_message(pair)]


def task_b_request_template(pair: Mapping[str, Any], route: str) -> dict[str, Any]:
    _require(route in {"catalytic", "direct"}, "unknown Task-B route")
    sentinel = canonical_json_text(
        {"state": ["captured-state-1", "captured-state-2", "captured-state-3", "captured-state-4"], "answer": "A"}
    )
    return {
        "route": route,
        "messages": task_b_messages(pair, sentinel),
        "temperature": 0,
        "seed": derive_seed(str(pair["pair_id"]), "task-b"),
        "maximum_completion_tokens": TASK_B_MAX_TOKENS,
        "cache_prompt": route == "catalytic",
        "response_schema": task_b_response_schema(),
        "dynamic_input": "exact authenticated Task-A JSON capture",
    }


def parse_task_b_output(text: str) -> str:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise WarmTrajectoryEvaluationError("Task-B output is not JSON") from exc
    _require(
        isinstance(value, dict) and set(value) == {"answer"} and value["answer"] in ALLOWED_ANSWERS,
        "Task-B output shape changed",
    )
    return str(value["answer"])


def fixed_request_templates(corpus: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    by_id = {str(item["pair_id"]): item for item in corpus["task_pairs"]}
    for pair_id in PAIR_IDS:
        pair = by_id[pair_id]
        result[f"{pair_id}-task-a"] = json_sha256(task_a_payload(pair))
        for route in ROUTE_ORDER[pair_id]:
            result[f"{pair_id}-task-b-{route}"] = json_sha256(task_b_request_template(pair, route))
    return result


def _callable_binding(values: Sequence[Callable[..., Any]]) -> dict[str, Any]:
    entries = [
        {"qualname": value.__qualname__, "source": inspect.getsource(value)}
        for value in values
    ]
    return {"algorithm": "sha256-canonical-callable-source-v1", "sha256": json_sha256(entries)}


def scientific_binding(corpus: Mapping[str, Any]) -> dict[str, Any]:
    body = {
        "design_id": DESIGN_ID,
        "corpus_sha256": PUBLIC_CORPUS_SHA256,
        "pair_sha256": {
            str(item["pair_id"]): public_pair_sha256(item) for item in corpus["task_pairs"]
        },
        "request_order": list(REQUEST_ORDER),
        "route_order": {key: list(value) for key, value in ROUTE_ORDER.items()},
        "seeds": {
            pair_id: {
                "task_a": derive_seed(pair_id, "task-a"),
                "task_b_shared": derive_seed(pair_id, "task-b"),
            }
            for pair_id in PAIR_IDS
        },
        "maximum_generations": MAXIMUM_GENERATIONS,
        "one_generation_maximum_per_request": True,
        "no_retry_after_start": True,
        "task_a_shared_between_routes": True,
        "fixed_request_template_sha256": fixed_request_templates(corpus),
        "request_constructor_binding": _callable_binding(
            [task_a_messages, task_a_payload, checkpoint_messages, task_b_user_message, task_b_messages]
        ),
        "parsers_binding": _callable_binding([parse_task_a_output, parse_task_b_output]),
    }
    return {"algorithm": "sha256-canonical-scientific-surface-v1", "sha256": json_sha256(body), "body": body}


def controller_binding() -> dict[str, Any]:
    return _callable_binding(
        [
            build_external_authority,
            consume_authority_once,
            capture_request_once,
            render_checkpoint_and_task_b,
            checkpoint_identity,
            evaluate_checkpoint_reuse,
            run_evaluation,
        ]
    )


def scorer_binding() -> dict[str, Any]:
    return _callable_binding(
        [
            protected_evaluator_custody,
            _load_protected_evaluator_after_terminal_gates,
            score_protected,
            classify_result,
        ]
    )


def resource_binding() -> dict[str, Any]:
    return _callable_binding([resource_record, account_resources, exact_ratio])


def closure_binding() -> dict[str, Any]:
    return _callable_binding([checkpoint_identity, verify_checkpoint_closure])


def build_preregistration_document(repository: Path) -> dict[str, Any]:
    corpus = load_public_corpus(repository)
    evaluator = protected_evaluator_custody(repository)
    scientific = scientific_binding(corpus)
    controller = controller_binding()
    scorer = scorer_binding()
    resources = resource_binding()
    closure = closure_binding()
    artifact = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "status": "statically-preregistered-unexecuted",
        "starting_protected_main": STARTING_PROTECTED_MAIN,
        "hypothesis": (
            "Executable state created during Task A can be borrowed and transformed for a related "
            "Task B with no worse accuracy and fewer fresh marginal tokens than equal-information replay, "
            "while the canonical Task-A state remains exact and lawfully closable."
        ),
        "post_hoc_semantic_xor_accounting": POST_HOC_XOR_ACCOUNTING,
        "corpus": {
            "path": PUBLIC_CORPUS_PATH.as_posix(),
            "sha256": PUBLIC_CORPUS_SHA256,
            "pair_ids": list(PAIR_IDS),
            "pair_sha256": scientific["body"]["pair_sha256"],
            "evidence_word_bounds": [500, 1000],
            "all_pairs_retained": True,
            "outcome_based_selection": False,
        },
        "protected_evaluator": evaluator,
        "execution": {
            "request_order": list(REQUEST_ORDER),
            "route_order": {key: list(value) for key, value in ROUTE_ORDER.items()},
            "seeds": scientific["body"]["seeds"],
            "fixed_request_template_sha256": scientific["body"]["fixed_request_template_sha256"],
            "task_a_generations": 4,
            "catalytic_task_b_generations": 4,
            "direct_task_b_generations": 4,
            "maximum_generations": MAXIMUM_GENERATIONS,
            "one_physical_slot": True,
            "one_sidecar_epoch": True,
            "temperature": 0,
            "thinking_disabled": True,
            "task_a_maximum_completion_tokens": TASK_A_MAX_TOKENS,
            "task_b_maximum_completion_tokens": TASK_B_MAX_TOKENS,
            "one_generation_maximum_per_request": True,
            "no_retry_after_request_start": True,
            "no_semantic_early_stop": True,
        },
        "holostate_law": {
            "carrier": "HoloState-v1 Live Prefix Lattice",
            "scope": "process-local",
            "checkpoint_contains": [
                "shared evidence",
                "Task-A request",
                "exact model-generated Task-A state and answer",
            ],
            "catalytic_suffix_contains": ["Task-B question", "Task-B choices", "Task-B response schema"],
            "direct_replay_contains": [
                "complete shared evidence",
                "Task-A question",
                "exact captured Task-A JSON",
                "Task-B question and choices",
                "Task-B response schema",
            ],
            "checkpoint_reuse_required": True,
            "checkpoint_materialization_reads_prior_cache": False,
            "checkpoint_readdress_required_immediately_after_catalytic_branch": True,
            "direct_route_cannot_feed_catalytic_cache": True,
            "direct_cached_prompt_tokens_required": 0,
            "restart_persistence_claimed": False,
        },
        "resource_law": {
            "shared_task_a_reported_separately": True,
            "primary_comparison": "marginal catalytic Task B versus direct replay Task B",
            "fresh_prompt_plus_completion_tokens": True,
            "exact_tokens_per_correct": True,
            "integer_cross_products": True,
            "wall_clock_separate": True,
        },
        "decision_law": {
            "supported": "PROCESS_LOCAL_WARM_TRAJECTORY_CATALYTIC_INFERENCE_SUPPORTED",
            "capability_without_token_advantage": (
                "PROCESS_LOCAL_WARM_TRAJECTORY_CAPABILITY_GAIN_SUPPORTED_WITHOUT_FRESH_TOKEN_ADVANTAGE"
            ),
            "reuse_only": "PROCESS_LOCAL_WARM_TRAJECTORY_REUSE_SUPPORTED_WITHOUT_TASK_ADVANTAGE",
            "not_supported": "PROCESS_LOCAL_WARM_TRAJECTORY_CATALYTIC_INFERENCE_NOT_SUPPORTED",
            "inconclusive": "INCONCLUSIVE",
        },
        "claim_locks": [
            "restart-persistent state",
            "general catalytic inference",
            "arbitrary task transfer",
            "compute amplification beyond observed accounting",
            "reduced wall-clock latency unless separately measured",
            "persistent blackboard value",
            "adaptive swarms",
            "superiority",
            "SOTA",
            "automatic promotion",
        ],
        "bindings": {
            "frozen_scientific": scientific,
            "controller": controller,
            "protected_scorer": scorer,
            "resource_accounting": resources,
            "checkpoint_closure": closure,
        },
        "authority": {
            "required": True,
            "fresh_external_authority_id": True,
            "raw_authority_id_persisted": False,
            "authorized_commit_must_equal_protected_main": True,
            "maximum_model_generations": MAXIMUM_GENERATIONS,
            "retry_allowed": False,
        },
        "runtime_artifacts_absent": not (repository / STATE_ROOT).exists(),
        "authority_receipt_absent": not (repository / AUTHORITY_RECEIPT_PATH).exists(),
        "model_contact_during_preparation": False,
    }
    body = dict(artifact)
    artifact["artifact_sha256"] = json_sha256(body)
    _assert_public_no_smuggle(artifact)
    return artifact


def write_preregistration(repository: Path) -> Path:
    value = build_preregistration_document(repository)
    path = repository / PREREGISTRATION_PATH
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"
    path.write_bytes(data)
    return path


def validate_preregistration(repository: Path) -> dict[str, Any]:
    expected = build_preregistration_document(repository)
    path = repository / PREREGISTRATION_PATH
    actual = json.loads(_regular_bytes(path, "warm-trajectory preregistration", 512 * 1024))
    _require(actual == expected, "preregistration differs from exact reconstruction")
    _require(actual.get("runtime_artifacts_absent") is True, "runtime root already exists")
    _require(actual.get("authority_receipt_absent") is True, "authority receipt already exists")
    return actual


def authority_id_sha256(raw_authority_id: str) -> str:
    _require(bool(re.fullmatch(r"[0-9a-f]{64}", raw_authority_id)), "authority ID must be lowercase 64-hex")
    return sha256_bytes(
        b"neo3000/holostate-warm-trajectory/authority-id/v1\0"
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
        "authority_kind": "external-one-shot-holostate-warm-trajectory-v1",
        "design_id": DESIGN_ID,
        "authorized_commit": authorized_commit,
        "authority_id_sha256": authority_id_sha256(raw_authority_id),
        "preregistration_file_sha256": preregistration_sha256,
        "maximum_model_generations": MAXIMUM_GENERATIONS,
        "retry_allowed": False,
        "raw_authority_id_persisted": False,
    }


def _experiment_key(root: bytes) -> bytes:
    return hmac.new(
        root,
        b"neo3000/holostate-warm-trajectory/experiment-key/v1\0" + DESIGN_ID.encode("utf-8"),
        hashlib.sha256,
    ).digest()


def _authority_hmac(root: bytes, body: Mapping[str, Any]) -> str:
    return hmac.new(
        root,
        b"neo3000/holostate-warm-trajectory/authority-receipt/v1\0" + canonical_json_bytes(body),
        hashlib.sha256,
    ).hexdigest().upper()


def consume_authority_once(repository: Path, root: bytes, authority: Mapping[str, Any]) -> dict[str, Any]:
    path = repository / AUTHORITY_RECEIPT_PATH
    _require(not os.path.lexists(path), "warm-trajectory authority is already consumed")
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
    value = json.loads(_regular_bytes(path, "warm-trajectory authority receipt", 64 * 1024))
    _require(isinstance(value, dict), "authority receipt is not an object")
    supplied = str(value.get("receipt_hmac_sha256", ""))
    body = {key: item for key, item in value.items() if key != "receipt_hmac_sha256"}
    _require(hmac.compare_digest(supplied, _authority_hmac(root, body)), "authority receipt HMAC changed")
    _require(
        value.get("design_id") == DESIGN_ID
        and value.get("raw_authority_id_persisted") is False
        and "raw_authority_id" not in canonical_json_text(value),
        "authority receipt disclosure boundary changed",
    )
    return {**value, "receipt_sha256": sha256_file(path)}


class RunLock(AbstractContextManager["RunLock"]):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: Any | None = None

    def __enter__(self) -> "RunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("xb")
        self.handle.write(f"{os.getpid()}\n".encode("ascii"))
        self.handle.flush()
        os.fsync(self.handle.fileno())
        return self

    def __exit__(self, *_args: object) -> None:
        if self.handle is not None:
            self.handle.close()
            self.handle = None
        if self.path.exists():
            self.path.unlink()


class JournalWriter:
    def __init__(self, path: Path, key: bytes) -> None:
        self.path = path
        self.key = key
        self.previous = "0" * 64
        self.count = 0

    def append(self, state: str, *, request_id: str | None = None, facts: Mapping[str, Any] | None = None) -> dict[str, Any]:
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
            b"neo3000/holostate-warm-trajectory/journal-event/v1\0" + canonical_json_bytes(body),
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


CAPTURE_EXECUTION_FIELDS = (
    "content",
    "reasoning_content",
    "tool_calls",
    "prompt_tokens",
    "cached_prompt_tokens",
    "completion_tokens",
    "generated_token_ids",
    "generated_token_count",
    "completion_token_count_match",
    "generated_token_sha256",
    "nonempty_token_array_event_count",
    "empty_token_array_event_count",
    "token_merge_modes",
    "terminal_stop_evidence",
    "finish_reason",
    "http_status",
    "event_count",
)


def _capture_value(execution: Any, name: str) -> Any:
    if isinstance(execution, Mapping):
        return execution.get(name)
    return getattr(execution, name, None)


def _capture_hmac(key: bytes, body: Mapping[str, Any]) -> str:
    return hmac.new(
        key,
        b"neo3000/holostate-warm-trajectory/capture-hmac/v1\0" + canonical_json_bytes(body),
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
        "execution": {name: _capture_value(execution, name) for name in CAPTURE_EXECUTION_FIELDS},
    }
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
    _require(isinstance(execution, Mapping) and set(execution) == set(CAPTURE_EXECUTION_FIELDS), "capture execution surface changed")
    return {**value, "capture_sha256": sha256_bytes(data)}


def raw_sse_bytes(capture: Mapping[str, Any]) -> bytes:
    raw = capture.get("raw_response_capture")
    _require(isinstance(raw, Mapping), "capture raw response is missing")
    return base64.b64decode(str(raw["bytes"]), validate=True)


def structured_content_from_capture(capture: Mapping[str, Any]) -> str:
    execution = capture.get("execution")
    _require(isinstance(execution, Mapping), "capture execution is missing")
    content = execution.get("content")
    _require(isinstance(content, str) and content.strip(), "capture contains no structured content")
    return content.strip()


def _stream_raw_completion(
    *,
    port: int,
    payload: Mapping[str, Any],
    recorder: Callable[[bytes], None],
    timeout: float = 900,
) -> SimpleNamespace:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/completion",
        data=canonical_json_bytes(payload),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    content_parts: list[str] = []
    token_ids: list[int] = []
    merge_modes: list[str] = []
    progress: list[dict[str, Any]] = []
    final: dict[str, Any] = {}
    event_count = 0
    nonempty_arrays = 0
    empty_arrays = 0
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = int(response.status)
        for line in response:
            recorder(line)
            stripped = line.decode("utf-8", errors="replace").strip()
            if not stripped.startswith("data:"):
                continue
            data = stripped[5:].strip()
            if not data or data == "[DONE]":
                continue
            event = json.loads(data)
            event_count += 1
            if isinstance(event.get("content"), str):
                content_parts.append(event["content"])
            if isinstance(event.get("prompt_progress"), Mapping):
                progress.append(dict(event["prompt_progress"]))
            tokens = event.get("tokens")
            if isinstance(tokens, list):
                if tokens:
                    nonempty_arrays += 1
                    token_ids.extend(int(item) for item in tokens)
                    merge_modes.append("append")
                else:
                    empty_arrays += 1
            if event.get("stop") is True:
                final = event
    timings = final.get("timings") if isinstance(final.get("timings"), Mapping) else {}
    last_progress = progress[-1] if progress else {}
    completion = int(timings.get("predicted_n") or final.get("tokens_predicted") or len(token_ids))
    prompt_tokens = int(last_progress.get("total") or final.get("tokens_evaluated") or 0)
    cached = int(last_progress.get("cache") or 0)
    return SimpleNamespace(
        content="".join(content_parts),
        reasoning_content="",
        tool_calls=[],
        prompt_tokens=prompt_tokens,
        cached_prompt_tokens=cached,
        completion_tokens=completion,
        generated_token_ids=token_ids,
        generated_token_count=len(token_ids),
        completion_token_count_match=(completion == len(token_ids) or not token_ids),
        generated_token_sha256=sha256_bytes(canonical_json_bytes(token_ids)),
        nonempty_token_array_event_count=nonempty_arrays,
        empty_token_array_event_count=empty_arrays,
        token_merge_modes=merge_modes,
        terminal_stop_evidence={"observed": bool(final), "stop": final.get("stop")},
        finish_reason=str(final.get("stop_type") or "stop"),
        http_status=status,
        event_count=event_count,
    )


def resource_record(capture: Mapping[str, Any], request_id: str) -> dict[str, Any]:
    execution = capture.get("execution")
    _require(isinstance(execution, Mapping), "capture resource data is missing")
    logical = int(execution.get("prompt_tokens") or 0)
    cached = int(execution.get("cached_prompt_tokens") or 0)
    completion = int(execution.get("completion_tokens") or 0)
    _require(logical > 0 and 0 <= cached <= logical and completion > 0, "capture resource data is invalid")
    return {
        "request_id": request_id,
        "logical_prompt_tokens": logical,
        "reused_prompt_tokens": cached,
        "fresh_prompt_tokens": logical - cached,
        "completion_tokens": completion,
        "fresh_prompt_plus_completion_tokens": logical - cached + completion,
        "maximum_request_context": logical + (TASK_A_MAX_TOKENS if request_id.endswith("task-a") else TASK_B_MAX_TOKENS),
        "generation_count": 1,
    }


def exact_ratio(tokens: int, correct: int) -> dict[str, Any]:
    return {"numerator": tokens, "denominator": correct, "defined": correct > 0}


def account_resources(records: Sequence[Mapping[str, Any]], scoring: Mapping[str, Any]) -> dict[str, Any]:
    def summarize(name: str, selected: Sequence[Mapping[str, Any]], correct: int) -> dict[str, Any]:
        fresh_prompt = sum(int(item["fresh_prompt_tokens"]) for item in selected)
        completion = sum(int(item["completion_tokens"]) for item in selected)
        total = fresh_prompt + completion
        return {
            "route": name,
            "request_count": len(selected),
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

    shared = [item for item in records if str(item["request_id"]).endswith("task-a")]
    catalytic = [item for item in records if str(item["request_id"]).endswith("task-b-catalytic")]
    direct = [item for item in records if str(item["request_id"]).endswith("task-b-direct")]
    _require(len(shared) == len(catalytic) == len(direct) == 4, "resource route geometry changed")
    catalytic_summary = summarize("catalytic-task-b", catalytic, int(scoring["catalytic_task_b_correct"]))
    direct_summary = summarize("direct-replay-task-b", direct, int(scoring["direct_task_b_correct"]))
    shared_summary = summarize("shared-task-a", shared, int(scoring["task_a_correct"]))
    total_sequence = {
        "request_count": 12,
        "generation_count": 12,
        "logical_prompt_tokens": sum(int(item["logical_prompt_tokens"]) for item in records),
        "reused_prompt_tokens": sum(int(item["reused_prompt_tokens"]) for item in records),
        "fresh_prompt_tokens": sum(int(item["fresh_prompt_tokens"]) for item in records),
        "completion_tokens": sum(int(item["completion_tokens"]) for item in records),
    }
    total_sequence["fresh_prompt_plus_completion_tokens"] = (
        total_sequence["fresh_prompt_tokens"] + total_sequence["completion_tokens"]
    )
    cross = {
        "catalytic_tokens_x_direct_correct": (
            catalytic_summary["fresh_prompt_plus_completion_tokens"] * direct_summary["correct_answers"]
        ),
        "direct_tokens_x_catalytic_correct": (
            direct_summary["fresh_prompt_plus_completion_tokens"] * catalytic_summary["correct_answers"]
        ),
    }
    return {
        "shared_task_a": shared_summary,
        "catalytic_task_b": catalytic_summary,
        "direct_task_b": direct_summary,
        "total_sequence_shared_task_a_counted_once": total_sequence,
        "integer_cross_products": cross,
        "catalytic_fresh_tokens_per_correct_strictly_lower": (
            catalytic_summary["correct_answers"] > 0
            and direct_summary["correct_answers"] > 0
            and cross["catalytic_tokens_x_direct_correct"] < cross["direct_tokens_x_catalytic_correct"]
        ),
    }


def render_checkpoint_and_task_b(
    holostate: Any,
    pair: Mapping[str, Any],
    task_a_json: str,
) -> dict[str, Any]:
    prefix_candidate = holostate.render_messages(
        checkpoint_messages(pair, task_a_json), CHAT_TEMPLATE_KWARGS
    )
    full_prompt = holostate.render_messages(
        task_b_messages(pair, task_a_json), CHAT_TEMPLATE_KWARGS
    )
    prefix_ids = holostate.tokenize(prefix_candidate)
    full_ids = holostate.tokenize(full_prompt)
    common_count = holostate.exact_common_token_prefix(prefix_ids, full_ids)
    _require(common_count > 0, "Task-A checkpoint has no exact Task-B prefix")
    checkpoint_ids = full_ids[:common_count]
    checkpoint_prompt = holostate.cache_diagnostic_detokenize(checkpoint_ids)
    _require(task_a_json in checkpoint_prompt, "Task-A capture is absent from checkpoint prefix")
    _require(full_ids[: len(checkpoint_ids)] == checkpoint_ids, "checkpoint token prefix changed")
    suffix_ids = full_ids[len(checkpoint_ids) :]
    _require(bool(suffix_ids), "Task-B suffix is empty")
    return {
        "checkpoint_prompt": checkpoint_prompt,
        "checkpoint_token_ids": checkpoint_ids,
        "full_prompt": full_prompt,
        "full_token_ids": full_ids,
        "suffix_token_ids": suffix_ids,
        "checkpoint_token_count": len(checkpoint_ids),
        "full_prompt_token_count": len(full_ids),
        "suffix_token_count": len(suffix_ids),
        "checkpoint_prompt_sha256": sha256_bytes(checkpoint_prompt.encode("utf-8")),
        "checkpoint_token_sha256": sha256_bytes(canonical_json_bytes(checkpoint_ids)),
        "full_prompt_sha256": sha256_bytes(full_prompt.encode("utf-8")),
        "full_token_sha256": sha256_bytes(canonical_json_bytes(full_ids)),
        "suffix_token_sha256": sha256_bytes(canonical_json_bytes(suffix_ids)),
    }


def checkpoint_identity(
    geometry: Mapping[str, Any],
    *,
    pair_id: str,
    task_a_capture_sha256: str,
    preflight_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    model = preflight_metadata.get("model_identity")
    binary = preflight_metadata.get("binary_identity")
    stable = preflight_metadata.get("stable")
    _require(isinstance(model, Mapping) and isinstance(binary, Mapping) and isinstance(stable, Mapping), "checkpoint runtime identity is incomplete")
    body = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "pair_id": pair_id,
        "task_a_capture_sha256": task_a_capture_sha256,
        "checkpoint_prompt_sha256": geometry["checkpoint_prompt_sha256"],
        "checkpoint_token_sha256": geometry["checkpoint_token_sha256"],
        "checkpoint_token_count": geometry["checkpoint_token_count"],
        "model_sha256": model.get("sha256"),
        "binary_sha256": binary.get("sha256"),
        "chat_template_sha256": stable.get("chat_template_sha256"),
        "scope": "process-local",
    }
    _require(body["model_sha256"] == MODEL_SHA256, "checkpoint model identity changed")
    _require(body["binary_sha256"] == BINARY_SHA256, "checkpoint binary identity changed")
    return {**body, "checkpoint_id": f"warm-trajectory-{json_sha256(body)[:24].lower()}"}


def evaluate_checkpoint_reuse(
    identity: Mapping[str, Any],
    *,
    warm_execution: Any,
    catalytic_capture: Mapping[str, Any],
    direct_capture: Mapping[str, Any],
    readdress_execution: Any,
) -> dict[str, Any]:
    checkpoint_tokens = int(identity["checkpoint_token_count"])
    warm_prompt = int(_capture_value(warm_execution, "prompt_tokens") or 0)
    warm_cached = int(_capture_value(warm_execution, "cached_prompt_tokens") or 0)
    catalytic_execution = catalytic_capture["execution"]
    direct_execution = direct_capture["execution"]
    readdress_prompt = int(_capture_value(readdress_execution, "prompt_tokens") or 0)
    readdress_cached = int(_capture_value(readdress_execution, "cached_prompt_tokens") or 0)
    catalytic_cached = int(catalytic_execution.get("cached_prompt_tokens") or 0)
    direct_cached = int(direct_execution.get("cached_prompt_tokens") or 0)
    result = {
        "checkpoint_id": identity["checkpoint_id"],
        "checkpoint_token_count": checkpoint_tokens,
        "warm_prompt_tokens": warm_prompt,
        "warm_cached_prompt_tokens": warm_cached,
        "catalytic_cached_prompt_tokens": catalytic_cached,
        "direct_cached_prompt_tokens": direct_cached,
        "readdress_prompt_tokens": readdress_prompt,
        "readdress_cached_prompt_tokens": readdress_cached,
        "exact_checkpoint_reuse_observed": catalytic_cached >= checkpoint_tokens,
        "checkpoint_freshly_materialized": warm_cached == 0,
        "direct_route_fresh": direct_cached == 0,
        "root_readdressable_immediately_after_catalytic": readdress_cached >= checkpoint_tokens,
    }
    result["passed"] = all(
        (
            warm_prompt >= checkpoint_tokens,
            result["checkpoint_freshly_materialized"],
            result["exact_checkpoint_reuse_observed"],
            result["direct_route_fresh"],
            result["root_readdressable_immediately_after_catalytic"],
        )
    )
    return result


def verify_checkpoint_closure(
    original: Mapping[str, Any],
    reconstructed: Mapping[str, Any],
    reuse: Mapping[str, Any],
) -> dict[str, Any]:
    immutable_fields = (
        "checkpoint_id",
        "pair_id",
        "task_a_capture_sha256",
        "checkpoint_prompt_sha256",
        "checkpoint_token_sha256",
        "checkpoint_token_count",
        "model_sha256",
        "binary_sha256",
        "chat_template_sha256",
        "scope",
    )
    unchanged = all(original.get(key) == reconstructed.get(key) for key in immutable_fields)
    result = {
        "checkpoint_identity_unchanged": unchanged,
        "model_configuration_prefix_identity_unchanged": unchanged,
        "branch_did_not_overwrite_root_before_closure": unchanged,
        "root_readdressable_immediately_after_catalytic": reuse.get("root_readdressable_immediately_after_catalytic") is True,
        "checkpoint_freshly_materialized_before_catalytic": reuse.get("checkpoint_freshly_materialized") is True,
        "direct_route_did_not_read_checkpoint": reuse.get("direct_route_fresh") is True,
        "temporary_branch_state_retired_by_final_cleanup": True,
        "restart_persistence_claimed": False,
    }
    result["passed"] = all(value is True for key, value in result.items() if key != "restart_persistence_claimed")
    return result


def _task_b_grammar() -> str:
    return (
        'root ::= "{" ws "\\\"answer\\\"" ws ":" ws answer ws "}"\n'
        'answer ::= "\\\"A\\\"" | "\\\"B\\\"" | "\\\"C\\\"" | "\\\"D\\\""\n'
        'ws ::= [ \\t\\n\\r]*'
    )


def _raw_completion_payload(prompt: str, *, seed: int, cache_prompt: bool, n_predict: int) -> dict[str, Any]:
    payload = {
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": 0,
        "seed": seed,
        "stream": True,
        "cache_prompt": cache_prompt,
        "id_slot": 0,
        "return_tokens": True,
        "return_progress": True,
    }
    if n_predict > 0:
        payload["grammar"] = _task_b_grammar()
    return payload


def _pair_by_id(corpus: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(item["pair_id"]): item for item in corpus["task_pairs"]}


def _load_protected_evaluator_after_terminal_gates(
    repository: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    custody = protected_evaluator_custody(repository)
    path = repository / PROTECTED_EVALUATOR_PATH
    data = path.read_bytes()
    _require(len(data) == PROTECTED_EVALUATOR_SIZE, "protected evaluator byte size changed")
    observed_sha256 = sha256_bytes(data)
    _require(
        observed_sha256 == PROTECTED_EVALUATOR_SHA256,
        "protected evaluator hash changed",
    )

    def reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            _require(key not in value, "protected evaluator contains a duplicate JSON key")
            value[key] = item
        return value

    value = json.loads(data, object_pairs_hook=reject_duplicate_keys)
    _require(
        isinstance(value, dict)
        and value.get("evaluator_id") == f"{FAMILY_ID}-protected-evaluator"
        and value.get("corpus_id") == FAMILY_ID,
        "protected evaluator identity changed",
    )
    custody.update(
        {
            "observed_size_bytes": len(data),
            "observed_sha256": observed_sha256,
            "bytes_opened": True,
            "bytes_hashed": True,
            "bytes_parsed": True,
            "sha256_verified": True,
        }
    )
    return value, custody


def score_protected(
    repository: Path,
    corpus: Mapping[str, Any],
    outcomes: Mapping[str, Mapping[str, Any]],
    *,
    completed_capture_ids: Sequence[str],
    cleanup_passed: bool,
    postflight_passed: bool,
) -> dict[str, Any]:
    _require(tuple(completed_capture_ids) == REQUEST_ORDER, "protected evaluator opened before all captures")
    _require(cleanup_passed and postflight_passed, "protected evaluator opened before cleanup/postflight")
    evaluator, evaluator_custody = _load_protected_evaluator_after_terminal_gates(repository)
    answers = evaluator.get("task_pairs")
    _require(isinstance(answers, Mapping) and set(answers) == set(PAIR_IDS), "protected task inventory changed")
    by_id = _pair_by_id(corpus)
    per_pair: dict[str, Any] = {}
    task_a_correct = 0
    task_a_state_correct = 0
    catalytic_correct = 0
    direct_correct = 0
    for pair_id in PAIR_IDS:
        protected = answers[pair_id]
        observed = outcomes[pair_id]
        _require(
            protected.get("public_pair_sha256") == public_pair_sha256(by_id[pair_id]),
            f"protected public-pair binding changed: {pair_id}",
        )
        task_a = observed.get("task_a")
        _require(isinstance(task_a, Mapping), f"Task-A outcome missing: {pair_id}")
        combined_state = " ".join(str(item).lower() for item in task_a.get("state", []))
        requirements = protected.get("state_required_concepts")
        _require(isinstance(requirements, list) and len(requirements) == 4, "protected state requirements changed")
        concept_matches = [
            any(str(term).lower() in combined_state for term in group)
            for group in requirements
        ]
        state_correct = all(concept_matches)
        a_correct = task_a.get("answer") == protected.get("task_a_answer")
        c_correct = observed.get("catalytic_answer") == protected.get("task_b_answer")
        d_correct = observed.get("direct_answer") == protected.get("task_b_answer")
        task_a_correct += int(a_correct)
        task_a_state_correct += int(state_correct)
        catalytic_correct += int(c_correct)
        direct_correct += int(d_correct)
        per_pair[pair_id] = {
            "task_a_schema_valid": True,
            "task_a_answer_correct": a_correct,
            "task_a_state_concepts_correct": state_correct,
            "task_a_state_requirement_matches": concept_matches,
            "catalytic_task_b_correct": c_correct,
            "direct_task_b_correct": d_correct,
        }
    return {
        "task_a_correct": task_a_correct,
        "task_a_state_correct": task_a_state_correct,
        "catalytic_task_b_correct": catalytic_correct,
        "direct_task_b_correct": direct_correct,
        "per_pair": per_pair,
        "protected_evaluator_sha256": PROTECTED_EVALUATOR_SHA256,
        "protected_evaluator_custody": evaluator_custody,
        "protected_answers_disclosed": False,
    }


def classify_result(
    scoring: Mapping[str, Any],
    resources: Mapping[str, Any],
    *,
    reuse_closure_passed: bool,
    cleanup_passed: bool,
    postflight_passed: bool,
) -> str:
    if not (reuse_closure_passed and cleanup_passed and postflight_passed):
        return "INCONCLUSIVE"
    task_a_all = scoring.get("task_a_correct") == 4 and scoring.get("task_a_state_correct") == 4
    catalytic = int(scoring.get("catalytic_task_b_correct") or 0)
    direct = int(scoring.get("direct_task_b_correct") or 0)
    advantage = resources.get("catalytic_fresh_tokens_per_correct_strictly_lower") is True
    if task_a_all and catalytic >= direct and advantage:
        return "PROCESS_LOCAL_WARM_TRAJECTORY_CATALYTIC_INFERENCE_SUPPORTED"
    if task_a_all and catalytic > direct and not advantage:
        return "PROCESS_LOCAL_WARM_TRAJECTORY_CAPABILITY_GAIN_SUPPORTED_WITHOUT_FRESH_TOKEN_ADVANTAGE"
    if task_a_all and catalytic == direct and not advantage:
        return "PROCESS_LOCAL_WARM_TRAJECTORY_REUSE_SUPPORTED_WITHOUT_TASK_ADVANTAGE"
    return "PROCESS_LOCAL_WARM_TRAJECTORY_CATALYTIC_INFERENCE_NOT_SUPPORTED"


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
    return paths


def _runtime_allowed_paths(paths: Mapping[str, Path]) -> tuple[Path, ...]:
    return tuple(path for key, path in paths.items() if key not in {"run_root", "receipt"})


def _public_preflight(full: Mapping[str, Any]) -> dict[str, Any]:
    return runtime_support._public_preflight(full)


def _finalize_scientific_result(
    repository: Path,
    corpus: Mapping[str, Any],
    outcomes: Mapping[str, Mapping[str, Any]],
    captured: Sequence[str],
    resource_records: Sequence[Mapping[str, Any]],
    checkpoint_reports: Mapping[str, Mapping[str, Any]],
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
        cleanup_passed=cleanup.get("passed") is True,
        postflight_passed=postflight.get("passed") is True,
    )
    resources = account_resources(resource_records, scoring)
    closure_passed = all(report["closure"]["passed"] for report in checkpoint_reports.values())
    classification = classify_result(
        scoring,
        resources,
        reuse_closure_passed=closure_passed,
        cleanup_passed=cleanup.get("passed") is True,
        postflight_passed=postflight.get("passed") is True,
    )
    return {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "status": "complete",
        "terminal_classification": classification,
        "completed_model_generations": len(captured),
        "retry_count": 0,
        "request_dispositions": {request_id: "captured" for request_id in REQUEST_ORDER},
        "scoring": scoring,
        "resources": resources,
        "checkpoint_reports": dict(checkpoint_reports),
        "cleanup": dict(cleanup),
        "postflight": dict(postflight),
        "authority_receipt_sha256": receipt["receipt_sha256"],
        "manifest_sha256": sha256_file(manifest_path),
        "journal_head_sha256": journal_head,
        "capture_sha256": {key: value["capture_sha256"] for key, value in captures.items()},
        "claims": {"general_catalytic_inference": "LOCKED", "automatic_promotion": False},
    }


def _archive_terminal(repository: Path, paths: Mapping[str, Path]) -> dict[str, Any]:
    members: list[dict[str, Any]] = []
    for key in ("receipt", "manifest", "journal", "result", "closure"):
        path = paths[key]
        if path.is_file() and not path.is_symlink():
            data = path.read_bytes()
            members.append({"source": key, "path": path.name, "bytes": len(data), "sha256": sha256_bytes(data)})
    for request_id in REQUEST_ORDER:
        path = paths[f"capture-{request_id}"]
        if path.is_file() and not path.is_symlink():
            data = path.read_bytes()
            members.append(
                {
                    "source": f"capture-{request_id}",
                    "path": f"captures/{request_id}.json",
                    "bytes": len(data),
                    "sha256": sha256_bytes(data),
                }
            )
    members.sort(key=lambda item: item["path"])
    body = {"schema_version": 1, "design_id": DESIGN_ID, "members": members}
    archive_sha = json_sha256(body)
    archive = repository / ARCHIVE_ROOT / archive_sha
    _require(not archive.exists(), "terminal archive content address already exists")
    for item in members:
        target = archive / str(item["path"])
        source_key = str(item["source"])
        source = paths[source_key]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    bundle = {**body, "bundle_sha256": archive_sha}
    (archive / "bundle.json").write_bytes(canonical_json_bytes(bundle) + b"\n")
    return {
        "archive_sha256": archive_sha,
        "evidence_member_count": len(members),
        "physical_file_count": len(members) + 1,
        "path": str(archive),
    }


def run_evaluation(args: argparse.Namespace, *, repository_root: Path | None = None) -> dict[str, Any]:
    repository = (repository_root or Path(args.repository)).resolve(strict=False)
    _require(str(args.design_id) == DESIGN_ID, "design ID changed")
    preregistration = validate_preregistration(repository)
    preregistration_file_sha = sha256_file(repository / PREREGISTRATION_PATH)
    corpus = load_public_corpus(repository)
    by_id = _pair_by_id(corpus)
    paths = state_paths(repository)
    _require(not paths["run_root"].exists(), "warm-trajectory runtime root already exists")
    _require(not paths["receipt"].exists(), "warm-trajectory authority receipt already exists")

    live = kernel.CatalyticKernel0Adapter(repository)
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
        "route_order": {key: list(value) for key, value in ROUTE_ORDER.items()},
        "fixed_request_template_sha256": fixed_request_templates(corpus),
        "preflight": public_preflight,
        "maximum_model_generations": MAXIMUM_GENERATIONS,
        "retry_allowed": False,
        "raw_authority_id_persisted": False,
    }
    _exclusive_write(paths["manifest"], canonical_json_bytes(manifest) + b"\n")

    started: list[str] = []
    captured: list[str] = []
    captures: dict[str, dict[str, Any]] = {}
    outcomes: dict[str, dict[str, Any]] = {pair_id: {} for pair_id in PAIR_IDS}
    checkpoint_reports: dict[str, dict[str, Any]] = {}
    resource_records: list[dict[str, Any]] = []
    sidecar: Any | None = None
    readiness: Mapping[str, Any] | None = None
    cleanup: Mapping[str, Any] = {"passed": False}
    postflight: Mapping[str, Any] = {"passed": False}
    pool: Any | None = None
    terminal_error: BaseException | None = None

    with RunLock(paths["run_lock"]):
        journal.append("authority-consumed", facts={"authority_id_sha256": authority["authority_id_sha256"]})
        try:
            sidecar, readiness = live.launch_sidecar(preflight=full_preflight, run_id=DESIGN_ID)
            pool = live.create_lease_pool(1)
            journal.append("sidecar-ready", facts=dict(readiness))
            generation_ordinal = 0
            for pair_id in PAIR_IDS:
                pair = by_id[pair_id]
                task_a_id = f"{pair_id}-task-a"
                _require(REQUEST_ORDER[len(started)] == task_a_id, "Task-A order changed")
                payload_a = task_a_payload(pair)
                request_hash_a = json_sha256(payload_a)
                _require(
                    request_hash_a == fixed_request_templates(corpus)[task_a_id],
                    "fixed Task-A request changed",
                )
                before = live.boundary_custody(
                    preflight=full_preflight, sidecar=sidecar, boundary=f"before:{task_a_id}"
                )
                _require(before.get("passed") is True, "Task-A pre-request custody failed")
                generation_ordinal += 1
                journal.append(
                    "request-started",
                    request_id=task_a_id,
                    facts={
                        "generation_ordinal": generation_ordinal,
                        "model_request_sha256": request_hash_a,
                        "maximum_generations_for_request": 1,
                    },
                )
                started.append(task_a_id)

                def invoke_task_a(recorder: Callable[[bytes], None]) -> Any:
                    _require(pool is not None, "lease pool unavailable")
                    with pool.lease() as lease_id:
                        _require(lease_id == kernel.PHYSICAL_SLOT, "physical slot changed")
                        return live.execute_request(
                            sidecar=sidecar,
                            payload=payload_a,
                            request=kernel.KernelRequest(request_id=task_a_id, ordinal=generation_ordinal),
                            raw_line_recorder=recorder,
                        )

                capture_a = capture_request_once(
                    paths[f"capture-{task_a_id}"],
                    paths[f"partial-{task_a_id}"],
                    experiment_key=experiment_key,
                    request_id=task_a_id,
                    model_request_sha256=request_hash_a,
                    generation_ordinal=generation_ordinal,
                    invoke=invoke_task_a,
                )
                after = live.boundary_custody(
                    preflight=full_preflight, sidecar=sidecar, boundary=f"after:{task_a_id}"
                )
                _require(after.get("passed") is True, "Task-A post-request custody failed")
                captured.append(task_a_id)
                captures[task_a_id] = capture_a
                resource_records.append(resource_record(capture_a, task_a_id))
                task_a_json = structured_content_from_capture(capture_a)
                parsed_a = parse_task_a_output(task_a_json)
                outcomes[pair_id]["task_a"] = parsed_a
                journal.append(
                    "request-captured",
                    request_id=task_a_id,
                    facts={"capture_sha256": capture_a["capture_sha256"]},
                )

                geometry = render_checkpoint_and_task_b(live.h, pair, task_a_json)
                identity = checkpoint_identity(
                    geometry,
                    pair_id=pair_id,
                    task_a_capture_sha256=capture_a["capture_sha256"],
                    preflight_metadata=full_preflight["metadata"],
                )
                warm_payload = _raw_completion_payload(
                    str(geometry["checkpoint_prompt"]),
                    seed=derive_seed(pair_id, "task-b"),
                    cache_prompt=False,
                    n_predict=0,
                )
                readdress_payload = _raw_completion_payload(
                    str(geometry["checkpoint_prompt"]),
                    seed=derive_seed(pair_id, "task-b"),
                    cache_prompt=True,
                    n_predict=0,
                )

                def perform_warm() -> Any:
                    _require(pool is not None, "lease pool unavailable")
                    with pool.lease() as lease_id:
                        _require(lease_id == kernel.PHYSICAL_SLOT, "physical slot changed")
                        return sidecar.guarded(
                            f"warm-trajectory-checkpoint:{pair_id}",
                            lambda: _stream_raw_completion(
                                port=live.h.PORT,
                                payload=warm_payload,
                                recorder=lambda _line: None,
                            ),
                            timeout=1_000,
                        )

                warm_execution: Any | None = None
                readdress_execution: Any | None = None
                for route in ROUTE_ORDER[pair_id]:
                    request_id = f"{pair_id}-task-b-{route}"
                    _require(REQUEST_ORDER[len(started)] == request_id, "Task-B route order changed")
                    if route == "catalytic" and warm_execution is None:
                        warm_execution = perform_warm()
                        journal.append(
                            "checkpoint-warmed",
                            request_id=request_id,
                            facts={
                                "checkpoint_id": identity["checkpoint_id"],
                                "checkpoint_token_count": identity["checkpoint_token_count"],
                                "prompt_tokens": _capture_value(warm_execution, "prompt_tokens"),
                                "cached_prompt_tokens": _capture_value(warm_execution, "cached_prompt_tokens"),
                            },
                        )
                    raw_payload = _raw_completion_payload(
                        str(geometry["full_prompt"]),
                        seed=derive_seed(pair_id, "task-b"),
                        cache_prompt=(route == "catalytic"),
                        n_predict=TASK_B_MAX_TOKENS,
                    )
                    request_hash = json_sha256(raw_payload)
                    before = live.boundary_custody(
                        preflight=full_preflight, sidecar=sidecar, boundary=f"before:{request_id}"
                    )
                    _require(before.get("passed") is True, "Task-B pre-request custody failed")
                    generation_ordinal += 1
                    journal.append(
                        "request-started",
                        request_id=request_id,
                        facts={
                            "generation_ordinal": generation_ordinal,
                            "model_request_sha256": request_hash,
                            "request_template_sha256": fixed_request_templates(corpus)[request_id],
                            "dynamic_task_a_capture_sha256": capture_a["capture_sha256"],
                            "maximum_generations_for_request": 1,
                        },
                    )
                    started.append(request_id)

                    def invoke_task_b(
                        recorder: Callable[[bytes], None],
                        *,
                        current_payload: Mapping[str, Any] = raw_payload,
                        current_id: str = request_id,
                    ) -> Any:
                        _require(pool is not None, "lease pool unavailable")
                        with pool.lease() as lease_id:
                            _require(lease_id == kernel.PHYSICAL_SLOT, "physical slot changed")
                            return sidecar.guarded(
                                f"warm-trajectory:{current_id}",
                                lambda: _stream_raw_completion(
                                    port=live.h.PORT,
                                    payload=current_payload,
                                    recorder=recorder,
                                ),
                                timeout=1_000,
                            )

                    capture_b = capture_request_once(
                        paths[f"capture-{request_id}"],
                        paths[f"partial-{request_id}"],
                        experiment_key=experiment_key,
                        request_id=request_id,
                        model_request_sha256=request_hash,
                        generation_ordinal=generation_ordinal,
                        invoke=invoke_task_b,
                    )
                    after = live.boundary_custody(
                        preflight=full_preflight, sidecar=sidecar, boundary=f"after:{request_id}"
                    )
                    _require(after.get("passed") is True, "Task-B post-request custody failed")
                    captured.append(request_id)
                    captures[request_id] = capture_b
                    resource_records.append(resource_record(capture_b, request_id))
                    answer = parse_task_b_output(structured_content_from_capture(capture_b))
                    outcomes[pair_id][f"{route}_answer"] = answer
                    journal.append(
                        "request-captured",
                        request_id=request_id,
                        facts={"capture_sha256": capture_b["capture_sha256"]},
                    )

                    if route == "catalytic":
                        readdress_execution = sidecar.guarded(
                            f"warm-trajectory-readdress:{pair_id}",
                            lambda: _stream_raw_completion(
                                port=live.h.PORT,
                                payload=readdress_payload,
                                recorder=lambda _line: None,
                            ),
                            timeout=1_000,
                        )
                        journal.append(
                            "checkpoint-readdressed",
                            request_id=request_id,
                            facts={
                                "checkpoint_id": identity["checkpoint_id"],
                                "prompt_tokens": _capture_value(readdress_execution, "prompt_tokens"),
                                "cached_prompt_tokens": _capture_value(readdress_execution, "cached_prompt_tokens"),
                                "immediately_after_catalytic": True,
                                "direct_route_completed_before_checkpoint_materialization": ROUTE_ORDER[pair_id][0] == "direct",
                            },
                        )

                _require(warm_execution is not None, "checkpoint was never warmed")
                _require(readdress_execution is not None, "checkpoint was not readdressed after catalytic Task B")
                catalytic_capture = captures[f"{pair_id}-task-b-catalytic"]
                direct_capture = captures[f"{pair_id}-task-b-direct"]
                reuse = evaluate_checkpoint_reuse(
                    identity,
                    warm_execution=warm_execution,
                    catalytic_capture=catalytic_capture,
                    direct_capture=direct_capture,
                    readdress_execution=readdress_execution,
                )
                reconstructed_geometry = render_checkpoint_and_task_b(live.h, pair, task_a_json)
                reconstructed_identity = checkpoint_identity(
                    reconstructed_geometry,
                    pair_id=pair_id,
                    task_a_capture_sha256=capture_a["capture_sha256"],
                    preflight_metadata=full_preflight["metadata"],
                )
                closure = verify_checkpoint_closure(identity, reconstructed_identity, reuse)
                _require(reuse["passed"] and closure["passed"], f"checkpoint reuse/closure failed: {pair_id}")
                checkpoint_reports[pair_id] = {
                    "identity": identity,
                    "geometry": {key: value for key, value in geometry.items() if not key.endswith("_prompt") and not key.endswith("_ids")},
                    "reuse": reuse,
                    "closure": closure,
                }
                journal.append(
                    "pair-closed",
                    request_id=None,
                    facts={
                        "pair_id": pair_id,
                        "checkpoint_id": identity["checkpoint_id"],
                        "reuse_passed": True,
                        "closure_passed": True,
                    },
                )
            _require(tuple(started) == REQUEST_ORDER and tuple(captured) == REQUEST_ORDER, "execution did not complete exact frozen order")
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
                    repository,
                    corpus,
                    outcomes,
                    captured,
                    resource_records,
                    checkpoint_reports,
                    cleanup,
                    postflight,
                    receipt,
                    paths["manifest"],
                    journal.previous,
                    captures,
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
                "retry_count": 0,
                "started_requests": list(started),
                "captured_requests": list(captured),
                "failure": {
                    "type": type(terminal_error).__name__,
                    "message_sha256": sha256_bytes(str(terminal_error).encode("utf-8")),
                },
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


def validate_static(repository: Path) -> dict[str, Any]:
    preregistration = validate_preregistration(repository)
    corpus = load_public_corpus(repository)
    diagnostic = preregistration["post_hoc_semantic_xor_accounting"]
    worker = diagnostic["worker_plus_controller_route"]
    direct = diagnostic["direct_baseline_route"]
    _require(worker["fresh_prompt_tokens"] == 1668 and worker["completion_tokens"] == 83, "post-hoc worker totals changed")
    _require(worker["fresh_prompt_plus_completion_tokens"] == 1751 and worker["correct_final_labels"] == 4, "post-hoc worker result changed")
    _require(direct["fresh_prompt_plus_completion_tokens"] == 1430 and direct["correct_final_labels"] == 3, "post-hoc baseline changed")
    _require(1751 * 3 == 5253 and 1430 * 4 == 5720 and 5253 < 5720, "post-hoc cross-product changed")
    _require(len(REQUEST_ORDER) == 12 and len(set(REQUEST_ORDER)) == 12, "request geometry changed")
    _require(not (repository / STATE_ROOT).exists(), "live runtime root exists")
    _require(not (repository / AUTHORITY_RECEIPT_PATH).exists(), "live authority receipt exists")
    return {
        "status": "pass",
        "design_id": DESIGN_ID,
        "artifact_sha256": preregistration["artifact_sha256"],
        "preregistration_file_sha256": sha256_file(repository / PREREGISTRATION_PATH),
        "public_corpus_sha256": PUBLIC_CORPUS_SHA256,
        "protected_evaluator_sha256": PROTECTED_EVALUATOR_SHA256,
        "pair_ids": list(PAIR_IDS),
        "request_order": list(REQUEST_ORDER),
        "seeds": preregistration["execution"]["seeds"],
        "fixed_request_template_sha256": fixed_request_templates(corpus),
        "bindings": {
            key: value["sha256"] for key, value in preregistration["bindings"].items()
        },
        "post_hoc_worker_plus_controller": POST_HOC_XOR_ACCOUNTING,
        "runtime_artifacts_absent": True,
        "authority_receipt_absent": True,
        "model_requests_issued": 0,
        "sidecar_launches": 0,
        "model_generations": 0,
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
            _require(all((args.binary, args.model, args.external_authority_id, args.authorized_commit)), "live run arguments are incomplete")
            result = run_evaluation(args, repository_root=repository)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(canonical_json_text({"status": "fail", "error": str(exc)}))
        return 1
    print(canonical_json_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
