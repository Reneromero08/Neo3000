#!/usr/bin/env python3
"""Prepare, validate, or run the frozen two-shard semantic-XOR evaluation."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import inspect
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import catalytic_inference_bench_0_runtime as runtime_support
import catalytic_kernel_0 as kernel
import catalytic_kernel_0_balanced_parent_dependence_cross_binding_asymmetry_audit as asymmetry
import catalytic_kernel_0_balanced_rank_head_v2_authority as source_authority
import catalytic_kernel_0_balanced_rank_head_v2_joint_condition_intersection_replication as source_binding
import catalytic_kernel_0_balanced_rank_head_v2_parent_dependence as transaction
import catalytic_kernel_0_two_shard_semantic_xor_worker_baseline_evaluation_scientific as scientific


class SemanticXorEvaluationError(ValueError):
    """The semantic-XOR design, custody, or one-shot contract changed."""


FAMILY_ID = "two-shard-semantic-xor-worker-synthesis-family-v1"
DESIGN_ID = scientific.DESIGN_ID
STARTING_PROTECTED_MAIN = "b025114ba23a34ebdc9d5e635e0a03ee91311286"
DESIGN_PATH = Path("lab/two_shard_semantic_xor_worker_synthesis_family_v1_design.json")
DESIGN_SHA256 = "ED63ED4C75F9D6CE8DB4177E1137D02CFED7B385E20B2D29B434206DAD5C7B1F"
PUBLIC_CORPUS_PATH = Path("lab/two_shard_semantic_xor_worker_synthesis_family_v1_public_tasks.json")
PUBLIC_CORPUS_SHA256 = "DE4D822424EFE5B6B5FAB1A65F5D2A1E5A87FC60D64A2DD84812BC300A246C41"
CORPUS_BINDING_PATH = Path("lab/two_shard_semantic_xor_worker_synthesis_family_v1_corpus_binding_1.json")
CORPUS_BINDING_SHA256 = "5EBFF4979CD8E60E814F05C8B5E8413523DFB244E4396548A4A595253020EF5F"
PROTECTED_EVALUATOR_PATH = Path(
    "state/catalytic_kernel_0_private/two_shard_semantic_xor_worker_synthesis_family_v1_evaluator.json"
)
PROTECTED_EVALUATOR_SHA256 = "437112DC9A06E4CB3CF1824A738BB13887212B23A38E2AF12A94374A9259D163"
PROTECTED_EVALUATOR_SIZE = 968
PREREGISTRATION_PATH = Path("lab/ck0_two_shard_semantic_xor_worker_baseline_evaluation_v1.json")
PRIVATE_ROOT_PATH = source_binding.PRIVATE_ROOT_PATH
EXPECTED_EVIDENCE_ROOT_COMMITMENT = "7999FE7862527BE08589EFF15B8AD7CFBC9F81C44C1FB7804E0AF31F34BD72FD"
STATE_ROOT = Path("state/catalytic_kernel_0/two_shard_semantic_xor_worker_baseline_evaluation_v1")
ARCHIVE_ROOT = Path("state/catalytic_kernel_0/two_shard_semantic_xor_worker_baseline_evidence_archive/v1")
AUTHORITY_RECEIPT_PATH = Path(
    "state/catalytic_kernel_0_authority.two-shard-semantic-xor-worker-baseline-v1.authority.consumed.json"
)
TASK_IDS = scientific.TASK_IDS
REQUEST_IDS = scientific.REQUEST_IDS
FIXED_REQUEST_IDS = scientific.FIXED_REQUEST_IDS
DERIVED_REQUEST_IDS = scientific.DERIVED_REQUEST_IDS
ROLE_ORDER_BY_TASK = scientific.ROLE_ORDER_BY_TASK
WORKER_ROLES = ("worker-A", "worker-B")
REQUEST_ROLES = ("worker-A", "worker-B", "synthesis", "baseline")
MAXIMUM_TOTAL_MODEL_GENERATIONS = 16
MAXIMUM_MODEL_GENERATIONS_PER_REQUEST = 1
MAXIMUM_COMPLETION_TOKENS = 8
MODEL_SHA256 = asymmetry.EXPECTED_MODEL_SHA256
BINARY_SHA256 = transaction.BINARY_SHA256

WORKER_SYSTEM_PROMPT = (
    "Read the passage and decide whether it entails the claim. Return strict JSON only. "
    "Use bit 1 when entailed and bit 0 when the passage decisively contradicts the claim."
)
SYNTHESIS_SYSTEM_PROMPT = (
    "Apply the supplied XOR rule to the two worker bits. Return strict JSON only."
)
BASELINE_SYSTEM_PROMPT = (
    "Solve both entailment questions, apply the supplied XOR rule to their bits, "
    "and return the final label as strict JSON only."
)

SOURCE_CAPTURE_DOMAIN = b"ck0/semantic-xor-worker-baseline/source-capture-v1\0"
EXPERIMENT_KEY_DOMAIN = b"ck0/semantic-xor-worker-baseline/experiment-key-v1\0"
AUTHORITY_ID_DOMAIN = b"ck0/semantic-xor-worker-baseline/authority-id-v1\0"
AUTHORITY_HMAC_DOMAIN = b"ck0/semantic-xor-worker-baseline/authority-hmac-v1\0"
JOURNAL_HMAC_DOMAIN = b"ck0/semantic-xor-worker-baseline/journal-hmac-v1\0"
AUTHORITY_SCHEMA_VERSION = "semantic-xor-worker-baseline-authority-v1"
AUTHORITY_RECEIPT_SCHEMA_VERSION = "semantic-xor-worker-baseline-consumption-v1"
AUTHORITY_KIND = "external-one-shot-semantic-xor-worker-baseline"
GENESIS_HASH = "0" * 64
SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
AUTHORITY_ID_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")

CAPABILITY_SUPPORTED = "NON_CONTROLLER_RECONSTRUCTIBLE_SEMANTIC_XOR_WORKER_SYNTHESIS_SUPPORTED"
WORKER_NOT_SUPPORTED = "SEMANTIC_WORKER_JUDGMENT_NOT_SUPPORTED"
SYNTHESIS_NOT_SUPPORTED = "SEMANTIC_XOR_SYNTHESIS_NOT_SUPPORTED"
ADVANTAGE_SUPPORTED = "SEMANTIC_XOR_WORKER_SYNTHESIS_FRESH_INFERENCE_ADVANTAGE_SUPPORTED"
ADVANTAGE_NOT_SUPPORTED = "SEMANTIC_XOR_WORKER_SYNTHESIS_ADVANTAGE_NOT_SUPPORTED"

LOCKED_CLAIMS = {
    "general_worker_synthesis": "locked",
    "general_semantic_reasoning": "locked",
    "transfer_beyond_four_tasks": "locked",
    "compute_amplification": "locked",
    "reduced_wall_clock_latency": "locked",
    "prompt_cache_advantage": "locked",
    "persistent_blackboard_value": "locked",
    "complete_catalytic_lifecycle": "locked",
    "general_catalytic_inference": "locked",
    "superiority": "locked",
    "sota": "locked",
    "automatic_promotion": False,
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


def json_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SemanticXorEvaluationError(message)


def _regular_bytes(
    path: Path,
    label: str,
    maximum: int = 8 * 1024 * 1024,
    *,
    exact: int | None = None,
) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise SemanticXorEvaluationError(f"{label} is not a regular file")
        data = path.read_bytes()
    except OSError as exc:
        raise SemanticXorEvaluationError(f"{label} is unreadable") from exc
    if exact is None:
        _require(0 < len(data) <= maximum, f"{label} has an unsafe size")
    else:
        _require(len(data) == exact, f"{label} byte length changed")
    return data


def _json_object(path: Path, label: str, maximum: int = 8 * 1024 * 1024) -> dict[str, Any]:
    try:
        value = json.loads(_regular_bytes(path, label, maximum))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SemanticXorEvaluationError(f"{label} is malformed") from exc
    _require(isinstance(value, dict), f"{label} is not an object")
    return value


def _exclusive_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def _write_or_require_identical(path: Path, data: bytes) -> None:
    if path.exists() or path.is_symlink():
        _require(_regular_bytes(path, path.name) == data, f"{path.name} differs from frozen bytes")
        return
    _exclusive_write(path, data)


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _assert_public_no_smuggle(value: Any) -> None:
    data = canonical_json_bytes(value).lower()
    for forbidden in (
        b'"expected_worker_a_bit"',
        b'"expected_worker_b_bit"',
        b'"expected_label"',
        b'"private_salt_hex"',
        b'"task_to_cell"',
        b'"raw_authority_id"',
    ):
        _require(forbidden not in data, "protected answer material entered tracked metadata")


def worker_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["bit"],
        "properties": {"bit": {"type": "integer", "enum": [0, 1]}},
    }


def label_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["label"],
        "properties": {"label": {"type": "string", "enum": ["SAME", "DIFFERENT"]}},
    }


def _task_body(task: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in task.items() if key != "task_id"}


def _derived_task_id(task: Mapping[str, Any]) -> str:
    return "sx-" + hashlib.sha256(canonical_json_bytes(_task_body(task))).hexdigest()[:12]


def load_public_tasks(repository: Path) -> dict[str, Any]:
    repository = repository.resolve(strict=False)
    design_data = _regular_bytes(repository / DESIGN_PATH, "semantic-XOR design")
    corpus_data = _regular_bytes(repository / PUBLIC_CORPUS_PATH, "semantic-XOR public corpus")
    binding_data = _regular_bytes(repository / CORPUS_BINDING_PATH, "semantic-XOR corpus binding")
    _require(sha256_bytes(design_data) == DESIGN_SHA256, "design artifact identity changed")
    _require(sha256_bytes(corpus_data) == PUBLIC_CORPUS_SHA256, "public corpus identity changed")
    _require(sha256_bytes(binding_data) == CORPUS_BINDING_SHA256, "corpus binding identity changed")
    try:
        corpus = json.loads(corpus_data)
        binding = json.loads(binding_data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SemanticXorEvaluationError("frozen public source is malformed") from exc
    _require(canonical_json_bytes(corpus) + b"\n" == corpus_data, "public corpus is not canonical")
    _require(isinstance(corpus, dict) and set(corpus) == {
        "schema_version", "family_id", "design_artifact_sha256", "tasks",
        "worker_bit_semantics", "xor_mapping",
    }, "public corpus schema changed")
    _require(corpus["family_id"] == FAMILY_ID and corpus["design_artifact_sha256"] == DESIGN_SHA256, "public corpus source binding changed")
    tasks = corpus.get("tasks")
    _require(isinstance(tasks, list) and len(tasks) == 4, "public task count changed")
    _require(tuple(task.get("task_id") for task in tasks) == TASK_IDS, "public task order changed")
    for task in tasks:
        _require(isinstance(task, dict) and set(task) == {
            "task_id", "shard_a_passage", "shard_a_question",
            "shard_b_passage", "shard_b_question",
        }, "public task fields changed")
        _require(task["task_id"] == _derived_task_id(task), "public task ID derivation changed")
        for key in ("shard_a_passage", "shard_a_question", "shard_b_passage", "shard_b_question"):
            _require(isinstance(task[key], str) and task[key].strip() == task[key] and task[key], "public task text changed")
    _require(isinstance(binding, dict), "corpus binding is not an object")
    _require(
        binding.get("protected_evaluator") == {
            "path": PROTECTED_EVALUATOR_PATH.as_posix(),
            "path_ignored": True,
            "sha256": PROTECTED_EVALUATOR_SHA256,
            "size_bytes": PROTECTED_EVALUATOR_SIZE,
        },
        "protected evaluator tracked binding changed",
    )
    return corpus


def validate_protected_evaluator_custody(repository: Path) -> dict[str, Any]:
    """Verify public custody metadata without opening or hashing evaluator bytes."""
    repository = repository.resolve(strict=False)
    path = repository / PROTECTED_EVALUATOR_PATH
    try:
        stat = path.lstat()
    except OSError as exc:
        raise SemanticXorEvaluationError("protected evaluator is unavailable") from exc
    _require(not path.is_symlink() and path.is_file(), "protected evaluator is not a regular file")
    _require(stat.st_size == PROTECTED_EVALUATOR_SIZE, "protected evaluator size changed")
    completed = subprocess.run(
        ["git", "-C", str(repository), "check-ignore", "--quiet", "--", PROTECTED_EVALUATOR_PATH.as_posix()],
        check=False,
        capture_output=True,
    )
    _require(completed.returncode == 0, "protected evaluator is not ignored")
    return {
        "path": PROTECTED_EVALUATOR_PATH.as_posix(),
        "size_bytes": PROTECTED_EVALUATOR_SIZE,
        "expected_sha256_from_tracked_binding": PROTECTED_EVALUATOR_SHA256,
        "regular_non_link": True,
        "ignored": True,
        "bytes_opened": False,
        "bytes_hashed": False,
    }


def _load_evidence_root(repository: Path) -> bytes:
    root, private = source_binding._load_private(repository.resolve(strict=False))
    _require(len(root) == 32, "private evidence root length changed")
    _require(private.secret_commitment == EXPECTED_EVIDENCE_ROOT_COMMITMENT, "private evidence-root custody changed")
    return root


def derive_seed(task_id: str, request_role: str) -> int:
    _require(task_id in TASK_IDS and request_role in REQUEST_ROLES, "seed input changed")
    material = (
        DESIGN_ID
        + STARTING_PROTECTED_MAIN
        + PUBLIC_CORPUS_SHA256
        + task_id
        + request_role
        + "seed-v1"
    ).encode("utf-8")
    digest = hashlib.sha256(material).digest()
    return 1 + int.from_bytes(digest[:8], "big") % ((1 << 31) - 2)


SEEDS = {
    f"{task_id}-{role}": derive_seed(task_id, role)
    for task_id in TASK_IDS
    for role in REQUEST_ROLES
}


def _payload(system_prompt: str, assignment: Mapping[str, Any], schema_name: str, schema: Mapping[str, Any], seed: int) -> dict[str, Any]:
    return {
        "model": "agents-a1",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": canonical_json_text(assignment)},
        ],
        "temperature": 0.0,
        "seed": seed,
        "max_tokens": MAXIMUM_COMPLETION_TOKENS,
        "stream": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": dict(schema)},
        },
        "stream_options": {"include_usage": True},
        "cache_prompt": False,
        "return_tokens": True,
        "return_progress": True,
        "verbose": True,
    }


def build_worker_request(corpus: Mapping[str, Any], task: Mapping[str, Any], worker_role: str) -> dict[str, Any]:
    _require(worker_role in WORKER_ROLES, "worker role changed")
    suffix = "a" if worker_role == "worker-A" else "b"
    assignment = {
        "family_id": FAMILY_ID,
        "task_id": task["task_id"],
        "worker_role": worker_role,
        "passage": task[f"shard_{suffix}_passage"],
        "question": task[f"shard_{suffix}_question"],
        "bit_semantics": dict(corpus["worker_bit_semantics"]),
    }
    return _payload(
        WORKER_SYSTEM_PROMPT,
        assignment,
        "semantic_worker_bit",
        worker_response_schema(),
        SEEDS[f"{task['task_id']}-{worker_role}"],
    )


def build_direct_baseline_request(corpus: Mapping[str, Any], task: Mapping[str, Any]) -> dict[str, Any]:
    assignment = {
        "family_id": FAMILY_ID,
        "task_id": task["task_id"],
        "shard_a": {"passage": task["shard_a_passage"], "question": task["shard_a_question"]},
        "shard_b": {"passage": task["shard_b_passage"], "question": task["shard_b_question"]},
        "bit_semantics": dict(corpus["worker_bit_semantics"]),
        "xor_mapping": dict(corpus["xor_mapping"]),
        "final_label_schema": label_response_schema(),
    }
    return _payload(
        BASELINE_SYSTEM_PROMPT,
        assignment,
        "semantic_xor_direct_label",
        label_response_schema(),
        SEEDS[f"{task['task_id']}-baseline"],
    )


def source_capture_commitment(
    root: bytes,
    *,
    task_id: str,
    worker_role: str,
    worker_request_sha256: str,
    authenticated_capture_sha256: str,
    captured_bit: int,
    generation_ordinal: int,
) -> str:
    _require(len(root) == 32, "evidence root changed")
    _require(task_id in TASK_IDS and worker_role in WORKER_ROLES, "worker source identity changed")
    _require(SHA256_RE.fullmatch(worker_request_sha256) is not None, "worker request hash changed")
    _require(SHA256_RE.fullmatch(authenticated_capture_sha256) is not None, "worker capture hash changed")
    _require(captured_bit in (0, 1), "captured worker bit changed")
    _require(1 <= generation_ordinal <= 16, "worker generation ordinal changed")
    body = {
        "design_id": DESIGN_ID,
        "task_id": task_id,
        "worker_role": worker_role,
        "worker_request_sha256": worker_request_sha256,
        "authenticated_capture_sha256": authenticated_capture_sha256,
        "captured_bit": captured_bit,
        "generation_ordinal": generation_ordinal,
    }
    return hmac.new(
        root,
        SOURCE_CAPTURE_DOMAIN + canonical_json_bytes(body),
        hashlib.sha256,
    ).hexdigest().upper()


def build_worker_artifact(
    root: bytes,
    *,
    task_id: str,
    worker_role: str,
    worker_request_sha256: str,
    authenticated_capture_sha256: str,
    captured_bit: int,
    generation_ordinal: int,
) -> dict[str, Any]:
    return {
        "worker_role": worker_role,
        "captured_bit": captured_bit,
        "source_capture_commitment_sha256": source_capture_commitment(
            root,
            task_id=task_id,
            worker_role=worker_role,
            worker_request_sha256=worker_request_sha256,
            authenticated_capture_sha256=authenticated_capture_sha256,
            captured_bit=captured_bit,
            generation_ordinal=generation_ordinal,
        ),
    }


def _validate_worker_artifacts(artifacts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    _require(isinstance(artifacts, Sequence) and len(artifacts) == 2, "synthesis worker artifacts changed")
    values = [dict(item) for item in artifacts]
    _require([item.get("worker_role") for item in values] == list(WORKER_ROLES), "synthesis worker order changed")
    for item in values:
        _require(set(item) == {"worker_role", "captured_bit", "source_capture_commitment_sha256"}, "synthesis artifact fields changed")
        _require(item["captured_bit"] in (0, 1), "synthesis worker bit changed")
        _require(SHA256_RE.fullmatch(str(item["source_capture_commitment_sha256"])) is not None, "synthesis source commitment changed")
    return values


def build_synthesis_request(
    corpus: Mapping[str, Any],
    task_id: str,
    worker_artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    _require(task_id in TASK_IDS, "synthesis task identity changed")
    artifacts = _validate_worker_artifacts(worker_artifacts)
    assignment = {
        "family_id": FAMILY_ID,
        "task_id": task_id,
        "worker_artifacts": artifacts,
        "xor_mapping": dict(corpus["xor_mapping"]),
        "final_label_schema": label_response_schema(),
    }
    return _payload(
        SYNTHESIS_SYSTEM_PROMPT,
        assignment,
        "semantic_xor_synthesis_label",
        label_response_schema(),
        SEEDS[f"{task_id}-synthesis"],
    )


def synthesis_derivation_law(corpus: Mapping[str, Any]) -> dict[str, Any]:
    body = {
        "constructor_source_sha256": sha256_bytes(inspect.getsource(build_synthesis_request).encode("utf-8")),
        "canonical_assignment_fields": [
            "family_id", "final_label_schema", "task_id", "worker_artifacts", "xor_mapping",
        ],
        "worker_artifact_fields": [
            "captured_bit", "source_capture_commitment_sha256", "worker_role",
        ],
        "worker_roles": list(WORKER_ROLES),
        "response_schema_sha256": json_sha256(label_response_schema()),
        "system_prompt_sha256": sha256_bytes(SYNTHESIS_SYSTEM_PROMPT.encode("utf-8")),
        "xor_mapping": dict(corpus["xor_mapping"]),
        "temperature": 0.0,
        "maximum_completion_tokens": MAXIMUM_COMPLETION_TOKENS,
        "seed_by_task": {task_id: SEEDS[f"{task_id}-synthesis"] for task_id in TASK_IDS},
        "cache_prompt": False,
        "source_capture_commitment_law": {
            "algorithm": "HMAC-SHA-256",
            "domain": "ck0/semantic-xor-worker-baseline/source-capture-v1",
            "binds": [
                "design_id", "task_id", "worker_role", "worker_request_sha256",
                "authenticated_capture_sha256", "captured_bit", "generation_ordinal",
            ],
        },
        "request_canonicalization": "UTF-8 canonical JSON; sorted keys; compact separators; no NaN",
        "derived_hash_recorded_before_contact": True,
    }
    return {**body, "sha256": json_sha256(body)}


def verify_synthesis_payload(
    corpus: Mapping[str, Any],
    task_id: str,
    worker_artifacts: Sequence[Mapping[str, Any]],
    payload: Mapping[str, Any],
) -> str:
    expected = build_synthesis_request(corpus, task_id, worker_artifacts)
    _require(dict(payload) == expected, "synthesis payload violates frozen derivation law")
    text = canonical_json_text(payload).lower()
    for forbidden in ("passage", "question", "expected_", "private_salt", "evaluator"):
        _require(forbidden not in text, "synthesis payload received forbidden evidence")
    return json_sha256(payload)


def build_fixed_payloads(corpus: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    tasks = {task["task_id"]: task for task in corpus["tasks"]}
    payloads: dict[str, dict[str, Any]] = {}
    for task_id in TASK_IDS:
        task = tasks[task_id]
        for worker_role in WORKER_ROLES:
            payloads[f"{task_id}-{worker_role}"] = build_worker_request(corpus, task, worker_role)
        payloads[f"{task_id}-baseline"] = build_direct_baseline_request(corpus, task)
    _require(set(payloads) == set(FIXED_REQUEST_IDS), "fixed request set changed")
    return payloads


def request_role(request_id: str) -> str:
    for role in ("worker-A", "worker-B", "synthesis", "baseline"):
        if request_id.endswith(f"-{role}"):
            return role
    raise SemanticXorEvaluationError("request role changed")


def request_task_id(request_id: str) -> str:
    role = request_role(request_id)
    task_id = request_id[: -(len(role) + 1)]
    _require(task_id in TASK_IDS, "request task identity changed")
    return task_id


def parse_worker_output(structured_content: str) -> int:
    try:
        value = json.loads(structured_content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise SemanticXorEvaluationError("worker output is invalid JSON") from exc
    _require(isinstance(value, dict) and set(value) == {"bit"} and value["bit"] in (0, 1), "worker output schema changed")
    return int(value["bit"])


def parse_label_output(structured_content: str) -> str:
    try:
        value = json.loads(structured_content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise SemanticXorEvaluationError("label output is invalid JSON") from exc
    _require(isinstance(value, dict) and set(value) == {"label"} and value["label"] in {"SAME", "DIFFERENT"}, "label output schema changed")
    return str(value["label"])


def score_protected_outcomes(
    repository: Path,
    outcomes: Mapping[str, Mapping[str, Any]],
    *,
    completed_capture_ids: Sequence[str],
    cleanup_passed: bool,
    postflight_passed: bool,
) -> dict[str, Any]:
    """Open the protected evaluator only after complete capture and lifecycle closure."""
    _require(tuple(completed_capture_ids) == REQUEST_IDS, "protected scoring requires all sixteen captures")
    _require(cleanup_passed and postflight_passed, "protected scoring requires cleanup and postflight")
    _require(set(outcomes) == set(TASK_IDS), "protected scoring task set changed")
    for task_id, outcome in outcomes.items():
        _require(set(outcome) == {"worker_a_bit", "worker_b_bit", "synthesis_label", "baseline_label"}, "protected scoring input fields changed")
        _require(outcome["worker_a_bit"] in (0, 1) and outcome["worker_b_bit"] in (0, 1), "protected scoring worker bit changed")
        _require(outcome["synthesis_label"] in {"SAME", "DIFFERENT"}, "protected scoring synthesis label changed")
        _require(outcome["baseline_label"] in {"SAME", "DIFFERENT"}, "protected scoring baseline label changed")
        _require(task_id in TASK_IDS, "protected scoring task identity changed")

    data = _regular_bytes(
        repository.resolve(strict=False) / PROTECTED_EVALUATOR_PATH,
        "protected semantic-XOR evaluator",
        exact=PROTECTED_EVALUATOR_SIZE,
    )
    _require(sha256_bytes(data) == PROTECTED_EVALUATOR_SHA256, "protected evaluator hash changed")
    try:
        evaluator = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SemanticXorEvaluationError("protected evaluator is malformed") from exc
    _require(isinstance(evaluator, dict) and set(evaluator) == {
        "schema_version", "family_id", "public_corpus_sha256", "private_salt_hex",
        "entries", "cell_coverage_validation", "created_before_model_contact",
    }, "protected evaluator schema changed")
    _require(evaluator["family_id"] == FAMILY_ID and evaluator["public_corpus_sha256"] == PUBLIC_CORPUS_SHA256, "protected evaluator source binding changed")
    _require(isinstance(evaluator["private_salt_hex"], str) and len(evaluator["private_salt_hex"]) == 64, "protected evaluator salt changed")
    _require(evaluator["created_before_model_contact"] is True, "protected evaluator freeze law changed")
    entries = evaluator.get("entries")
    _require(isinstance(entries, list) and len(entries) == 4, "protected evaluator entry count changed")
    by_task: dict[str, Mapping[str, Any]] = {}
    for entry in entries:
        _require(isinstance(entry, dict) and set(entry) == {
            "task_id", "expected_worker_a_bit", "expected_worker_b_bit", "expected_label",
        }, "protected evaluator entry schema changed")
        task_id = entry["task_id"]
        _require(task_id in TASK_IDS and task_id not in by_task, "protected evaluator task identity changed")
        _require(entry["expected_worker_a_bit"] in (0, 1) and entry["expected_worker_b_bit"] in (0, 1), "protected evaluator bit changed")
        _require(entry["expected_label"] in {"SAME", "DIFFERENT"}, "protected evaluator label changed")
        by_task[task_id] = entry
    _require(set(by_task) == set(TASK_IDS), "protected evaluator coverage changed")
    coverage = evaluator["cell_coverage_validation"]
    _require(
        isinstance(coverage, dict)
        and coverage.get("exact_four_cell_coverage") is True
        and coverage.get("cells_present_once") is True
        and coverage.get("worker_a_bit_balance") == {"0": 2, "1": 2}
        and coverage.get("worker_b_bit_balance") == {"0": 2, "1": 2}
        and coverage.get("final_label_balance") == {"DIFFERENT": 2, "SAME": 2},
        "protected evaluator aggregate balance changed",
    )

    per_task = []
    for task_id in TASK_IDS:
        observed = outcomes[task_id]
        expected = by_task[task_id]
        relation_label = "SAME" if observed["worker_a_bit"] == observed["worker_b_bit"] else "DIFFERENT"
        per_task.append(
            {
                "task_id": task_id,
                "worker_a_bit_correct": observed["worker_a_bit"] == expected["expected_worker_a_bit"],
                "worker_b_bit_correct": observed["worker_b_bit"] == expected["expected_worker_b_bit"],
                "synthesis_label_equals_captured_bit_xor": observed["synthesis_label"] == relation_label,
                "worker_route_final_label_correct": observed["synthesis_label"] == expected["expected_label"],
                "direct_baseline_label_correct": observed["baseline_label"] == expected["expected_label"],
            }
        )
    aggregate = {
        "worker_a_correct": sum(item["worker_a_bit_correct"] for item in per_task),
        "worker_b_correct": sum(item["worker_b_bit_correct"] for item in per_task),
        "semantic_worker_bits_correct": sum(item["worker_a_bit_correct"] + item["worker_b_bit_correct"] for item in per_task),
        "xor_relation_fidelity": sum(item["synthesis_label_equals_captured_bit_xor"] for item in per_task),
        "worker_route_final_correct": sum(item["worker_route_final_label_correct"] for item in per_task),
        "baseline_final_correct": sum(item["direct_baseline_label_correct"] for item in per_task),
    }
    return {
        "per_task": per_task,
        "aggregate": aggregate,
        "task_count": 4,
        "protected_evaluator_verified_after_cleanup_and_postflight": True,
        "protected_values_disclosed": False,
    }


def capability_classification(scoring: Mapping[str, Any], *, evidence_complete: bool, cleanup_passed: bool, postflight_passed: bool) -> str:
    if not evidence_complete or not cleanup_passed or not postflight_passed:
        return "INCONCLUSIVE"
    aggregate = scoring["aggregate"]
    if aggregate["semantic_worker_bits_correct"] != 8:
        return WORKER_NOT_SUPPORTED
    if aggregate["xor_relation_fidelity"] != 4 or aggregate["worker_route_final_correct"] != 4:
        return SYNTHESIS_NOT_SUPPORTED
    return CAPABILITY_SUPPORTED


def _token_ratio(total_tokens: int, correct: int) -> dict[str, Any]:
    return (
        {"kind": "infinity", "numerator": None, "denominator": 0}
        if correct == 0
        else {"kind": "exact-ratio", "numerator": total_tokens, "denominator": correct}
    )


def account_resources(
    request_records: Sequence[Mapping[str, Any]],
    scoring: Mapping[str, Any],
    capability: str,
) -> dict[str, Any]:
    _require(len(request_records) == 16, "resource accounting requires sixteen requests")
    _require([record.get("request_id") for record in request_records] == list(REQUEST_IDS), "resource request order changed")
    normalized = []
    for position, record in enumerate(request_records, start=1):
        _require(set(record) == {
            "request_id", "logical_prompt_tokens", "cached_prompt_tokens", "completion_tokens",
            "maximum_output_tokens", "generation_count", "maximum_request_context",
        }, "resource record fields changed")
        logical = record["logical_prompt_tokens"]
        cached = record["cached_prompt_tokens"]
        completion = record["completion_tokens"]
        _require(isinstance(logical, int) and logical > 0, "logical prompt token evidence changed")
        _require(cached == 0, "cached prompt tokens must be zero")
        _require(isinstance(completion, int) and completion > 0, "completion token evidence changed")
        _require(record["maximum_output_tokens"] == 8 and record["generation_count"] == 1, "request resource ceiling changed")
        _require(record["maximum_request_context"] == logical + 8, "maximum request context changed")
        normalized.append(
            {
                **dict(record),
                "fresh_prompt_tokens": logical,
                "fresh_prompt_plus_completion_tokens": logical + completion,
                "sequential_request_position": position,
            }
        )

    def route_summary(route: str, selected: Sequence[Mapping[str, Any]], correct: int) -> dict[str, Any]:
        logical = sum(item["logical_prompt_tokens"] for item in selected)
        fresh = sum(item["fresh_prompt_tokens"] for item in selected)
        cached = sum(item["cached_prompt_tokens"] for item in selected)
        completion = sum(item["completion_tokens"] for item in selected)
        total = fresh + completion
        return {
            "route": route,
            "request_count": len(selected),
            "generation_count": sum(item["generation_count"] for item in selected),
            "logical_prompt_tokens": logical,
            "fresh_prompt_tokens": fresh,
            "cached_prompt_tokens": cached,
            "completion_tokens": completion,
            "fresh_prompt_plus_completion_tokens": total,
            "correct_final_labels": correct,
            "tokens_per_correct_final_label": _token_ratio(total, correct),
            "maximum_per_request_context": max(item["maximum_request_context"] for item in selected),
        }

    worker_records = [item for item in normalized if request_role(item["request_id"]) != "baseline"]
    baseline_records = [item for item in normalized if request_role(item["request_id"]) == "baseline"]
    aggregate = scoring["aggregate"]
    worker = route_summary("worker-synthesis", worker_records, aggregate["worker_route_final_correct"])
    baseline = route_summary("direct-baseline", baseline_records, aggregate["baseline_final_correct"])
    worker_correct = worker["correct_final_labels"]
    baseline_correct = baseline["correct_final_labels"]
    worker_total = worker["fresh_prompt_plus_completion_tokens"]
    baseline_total = baseline["fresh_prompt_plus_completion_tokens"]
    if worker_correct == 0:
        strictly_lower = False
        cross_products = None
    elif baseline_correct == 0:
        strictly_lower = True
        cross_products = {"worker_tokens_x_baseline_correct": 0, "baseline_tokens_x_worker_correct": baseline_total * worker_correct}
    else:
        left = worker_total * baseline_correct
        right = baseline_total * worker_correct
        strictly_lower = left < right
        cross_products = {"worker_tokens_x_baseline_correct": left, "baseline_tokens_x_worker_correct": right}
    eligible = (
        capability == CAPABILITY_SUPPORTED
        and worker_correct >= baseline_correct
        and len(normalized) == 16
    )
    advantage = ADVANTAGE_SUPPORTED if eligible and strictly_lower else ADVANTAGE_NOT_SUPPORTED
    return {
        "requests": normalized,
        "worker_route": worker,
        "direct_route": baseline,
        "exact_integer_cross_products": cross_products,
        "worker_tokens_per_correct_strictly_lower": strictly_lower,
        "advantage_eligible": eligible,
        "advantage_classification": advantage,
        "wall_clock_excluded": True,
        "hypothetical_parallelism_excluded": True,
    }


def _file_binding(repository: Path, paths: Sequence[str]) -> dict[str, Any]:
    files = []
    for relative in paths:
        data = _regular_bytes(repository / relative, f"implementation file {relative}", 2 * 1024 * 1024)
        files.append({"path": relative, "byte_size": len(data), "sha256": sha256_bytes(data)})
    body = {"files": files}
    return {**body, "sha256": json_sha256(body)}


def _callable_binding(value: Any) -> dict[str, Any]:
    source = inspect.getsource(value).encode("utf-8")
    body = {
        "qualified_name": (
            "catalytic_kernel_0_two_shard_semantic_xor_worker_baseline_evaluation."
            f"{value.__qualname__}"
        ),
        "source_sha256": sha256_bytes(source),
    }
    return {**body, "sha256": json_sha256(body)}


def _scientific_contract(
    fixed_request_hashes: Mapping[str, str],
    derivation_law: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "design_id": DESIGN_ID,
        "task_ids": list(TASK_IDS),
        "request_ids": list(REQUEST_IDS),
        "execution_order": list(REQUEST_IDS),
        "fixed_request_sha256": dict(fixed_request_hashes),
        "synthesis_derivation_law_sha256": derivation_law["sha256"],
        "seed_by_request": dict(SEEDS),
        "source_identities": {
            "design": {"path": DESIGN_PATH.as_posix(), "sha256": DESIGN_SHA256},
            "public_corpus": {"path": PUBLIC_CORPUS_PATH.as_posix(), "sha256": PUBLIC_CORPUS_SHA256},
            "corpus_binding": {"path": CORPUS_BINDING_PATH.as_posix(), "sha256": CORPUS_BINDING_SHA256},
            "protected_evaluator": {"path": PROTECTED_EVALUATOR_PATH.as_posix(), "expected_size": PROTECTED_EVALUATOR_SIZE, "expected_sha256": PROTECTED_EVALUATOR_SHA256, "ignored": True},
        },
        "system_prompt_sha256": {
            "worker": sha256_bytes(WORKER_SYSTEM_PROMPT.encode("utf-8")),
            "synthesis": sha256_bytes(SYNTHESIS_SYSTEM_PROMPT.encode("utf-8")),
            "baseline": sha256_bytes(BASELINE_SYSTEM_PROMPT.encode("utf-8")),
        },
        "response_schema_sha256": {
            "worker": json_sha256(worker_response_schema()),
            "synthesis": json_sha256(label_response_schema()),
            "baseline": json_sha256(label_response_schema()),
        },
        "cache_prompt": False,
        "model_sha256": MODEL_SHA256,
        "binary_sha256": BINARY_SHA256,
        "physical_slots": 1,
        "sidecar_epochs": 1,
        "maximum_model_generations_per_request": 1,
        "maximum_total_model_generations": 16,
        "request_dispatch": "fixed-hash gate for workers and baselines; frozen derivation-law gate for synthesis",
        "raw_response_recording": "authenticated raw capture before parse for all sixteen requests",
    }


def build_preregistration_document(repository: Path, model_path: Path) -> dict[str, Any]:
    repository = repository.resolve(strict=False)
    corpus = load_public_tasks(repository)
    evaluator_custody = validate_protected_evaluator_custody(repository)
    _load_evidence_root(repository)
    fixed_payloads = build_fixed_payloads(corpus)
    fixed_hashes = {request_id: json_sha256(payload) for request_id, payload in fixed_payloads.items()}
    derivation_law = synthesis_derivation_law(corpus)
    contract = _scientific_contract(fixed_hashes, derivation_law)
    frozen = scientific.frozen_scientific_binding(repository, contract=contract, fixed_payloads=fixed_payloads)
    controller = _file_binding(
        repository,
        ["scripts/catalytic_kernel_0_two_shard_semantic_xor_worker_baseline_evaluation.py"],
    )
    scorer = _callable_binding(score_protected_outcomes)
    resource = _callable_binding(account_resources)
    tokenizer = asymmetry.OfflineTokenizer(model_path.resolve())
    fixed_payload_token_lengths = {
        request_id: tokenizer.length(canonical_json_text(payload))
        for request_id, payload in fixed_payloads.items()
    }
    valid_output_token_lengths = {
        "worker_bit_0": tokenizer.length('{"bit":0}'),
        "worker_bit_1": tokenizer.length('{"bit":1}'),
        "label_same": tokenizer.length('{"label":"SAME"}'),
        "label_different": tokenizer.length('{"label":"DIFFERENT"}'),
    }
    _require(max(valid_output_token_lengths.values()) <= MAXIMUM_COMPLETION_TOKENS, "valid schema output exceeds eight-token ceiling")
    body = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "family_id": FAMILY_ID,
        "starting_protected_main": STARTING_PROTECTED_MAIN,
        "scientific_questions": {
            "capability": "Can isolated semantic-bit workers and a separate XOR synthesis solve all four frozen tasks without controller-readable answers?",
            "resource": "Does the worker-synthesis route use fewer fresh prompt-plus-completion tokens per correct label than one same-evidence direct request?",
        },
        "frozen_sources": contract["source_identities"],
        "task_ids": list(TASK_IDS),
        "execution_order": list(REQUEST_IDS),
        "route_first_counterbalance": {"baseline_first_tasks": [TASK_IDS[0], TASK_IDS[2]], "worker_route_first_tasks": [TASK_IDS[1], TASK_IDS[3]]},
        "seed_law": {
            "canonical_material": "design ID + starting commit + public corpus SHA-256 + task ID + request role + seed-v1",
            "mapping": "1 + first-eight-byte big-endian integer modulo 2^31-2",
            "seed_by_request": dict(SEEDS),
            "outcome_independent": True,
        },
        "request_bindings": {
            "fixed_worker_and_baseline_request_sha256": fixed_hashes,
            "derived_synthesis_request_ids": list(DERIVED_REQUEST_IDS),
            "synthesis_derivation_law": derivation_law,
            "falsely_preknown_synthesis_hashes": False,
        },
        "prompts_and_schemas": {
            "system_prompt_sha256": contract["system_prompt_sha256"],
            "response_schema_sha256": contract["response_schema_sha256"],
            "maximum_completion_tokens": 8,
            "valid_output_token_lengths": valid_output_token_lengths,
            "maximum_valid_output_tokens": max(valid_output_token_lengths.values()),
            "fixed_payload_canonical_token_lengths": fixed_payload_token_lengths,
            "cache_prompt": False,
            "thinking_disabled": True,
            "temperature": 0.0,
        },
        "capture_and_execution_law": {
            "maximum_generations": 16,
            "maximum_generations_per_request": 1,
            "physical_slots": 1,
            "sidecar_epochs": 1,
            "no_retry_after_request_start": True,
            "no_adaptive_routing": True,
            "no_semantic_early_stop": True,
            "authenticated_capture_before_parse": True,
            "append_only_authenticated_journal": True,
            "content_addressed_terminal_archive": True,
            "zero_contact_replay": True,
        },
        "protected_scoring_law": {
            **evaluator_custody,
            "first_open_after_all_sixteen_captures": True,
            "first_open_after_cleanup": True,
            "first_open_after_postflight": True,
            "public_result_contains_only_correctness_booleans_and_aggregate_metrics": True,
        },
        "resource_accounting_law": {
            "fresh_prompt_tokens_equal_logical_prompt_tokens": True,
            "cached_prompt_tokens_required": 0,
            "comparison": "exact integer cross-products over fresh prompt-plus-completion tokens per correct final label",
            "zero_correct_labels": "infinity",
            "wall_clock_excluded": True,
            "hypothetical_parallelism_excluded": True,
        },
        "decision_laws": {
            "capability_supported": CAPABILITY_SUPPORTED,
            "worker_not_supported": WORKER_NOT_SUPPORTED,
            "synthesis_not_supported": SYNTHESIS_NOT_SUPPORTED,
            "inconclusive": "INCONCLUSIVE only for incomplete, invalid, infrastructure, custody, cleanup, postflight, or inadmissible evidence",
            "advantage_supported": ADVANTAGE_SUPPORTED,
            "advantage_not_supported": ADVANTAGE_NOT_SUPPORTED,
        },
        "bindings": {
            "frozen_scientific": frozen,
            "controller": controller,
            "protected_scorer": scorer,
            "resource_accounting": resource,
        },
        "private_evidence_authentication": {
            "existing_verified_32_byte_root_reused": True,
            "new_private_mapping_created": False,
            "root_bytes_published": False,
            "use": "domain-separated HMAC for evidence only",
        },
        "claim_locks": dict(LOCKED_CLAIMS),
        "execution_state": {
            "authority_created": False,
            "authority_consumed": False,
            "sidecar_launched": False,
            "model_requests_issued": 0,
            "model_generations": 0,
            "captures_created": 0,
            "result_created": False,
            "closure_created": False,
            "archive_created": False,
            "publication_record_created": False,
            "follow_on_designed": False,
        },
        "future_live_command_shape": (
            "python scripts/catalytic_kernel_0_two_shard_semantic_xor_worker_baseline_evaluation.py run "
            "--repository <repository> --binary <verified-binary> --model <verified-model> "
            f"--design-id {DESIGN_ID} --external-authority-id <fresh-64-hex> "
            "--authorized-commit <published-static-commit>"
        ),
    }
    _assert_public_no_smuggle(body)
    return {**body, "artifact_sha256": json_sha256(body)}


def write_preregistration(repository: Path, model_path: Path) -> Path:
    document = build_preregistration_document(repository, model_path)
    _write_or_require_identical(repository / PREREGISTRATION_PATH, canonical_json_bytes(document) + b"\n")
    return repository / PREREGISTRATION_PATH


def validate_preregistration(repository: Path, model_path: Path) -> dict[str, Any]:
    expected = build_preregistration_document(repository, model_path)
    data = _regular_bytes(repository / PREREGISTRATION_PATH, "semantic-XOR preregistration", 4 * 1024 * 1024)
    _require(data == canonical_json_bytes(expected) + b"\n", "preregistration exact reconstruction changed")
    _require(all(value in (False, 0) for value in expected["execution_state"].values()), "static execution state changed")
    return expected


def authority_id_sha256(raw_authority_id: str) -> str:
    _require(AUTHORITY_ID_RE.fullmatch(raw_authority_id) is not None, "authority ID is malformed")
    return sha256_bytes(AUTHORITY_ID_DOMAIN + bytes.fromhex(raw_authority_id))


def build_external_authority(
    repository: Path,
    model_path: Path,
    *,
    raw_authority_id: str,
    authorized_commit: str,
    current_commit: str,
    observed_model_sha256: str,
    observed_binary_sha256: str,
) -> dict[str, Any]:
    prereg = validate_preregistration(repository, model_path)
    _require(GIT_COMMIT_RE.fullmatch(authorized_commit) is not None, "authority commit is malformed")
    _require(current_commit == authorized_commit, "authority commit does not match protected main")
    _require(observed_model_sha256 == MODEL_SHA256 and observed_binary_sha256 == BINARY_SHA256, "live identity changed")
    return {
        "schema_version": AUTHORITY_SCHEMA_VERSION,
        "authority_kind": AUTHORITY_KIND,
        "design_id": DESIGN_ID,
        "authority_id_sha256": authority_id_sha256(raw_authority_id),
        "authorized_commit": authorized_commit,
        "preregistration_artifact_sha256": prereg["artifact_sha256"],
        "frozen_scientific_binding_sha256": prereg["bindings"]["frozen_scientific"]["sha256"],
        "controller_binding_sha256": prereg["bindings"]["controller"]["sha256"],
        "protected_scorer_binding_sha256": prereg["bindings"]["protected_scorer"]["sha256"],
        "resource_accounting_binding_sha256": prereg["bindings"]["resource_accounting"]["sha256"],
        "fixed_request_sha256": prereg["request_bindings"]["fixed_worker_and_baseline_request_sha256"],
        "synthesis_derivation_law_sha256": prereg["request_bindings"]["synthesis_derivation_law"]["sha256"],
        "execution_order": list(REQUEST_IDS),
        "model_sha256": MODEL_SHA256,
        "binary_sha256": BINARY_SHA256,
        "maximum_model_generations": 16,
        "retry_allowed": False,
    }


def _experiment_key(root: bytes) -> bytes:
    return hmac.new(root, EXPERIMENT_KEY_DOMAIN + DESIGN_ID.encode("utf-8"), hashlib.sha256).digest()


def consume_authority_once(repository: Path, root: bytes, authority: Mapping[str, Any]) -> dict[str, Any]:
    path = repository / AUTHORITY_RECEIPT_PATH
    _require(not path.exists() and not path.is_symlink(), "authority already consumed")
    body = {
        "schema_version": AUTHORITY_RECEIPT_SCHEMA_VERSION,
        "authority": dict(authority),
        "consumed_once": True,
        "consumed_at_utc": _utc_now(),
        "raw_authority_id_persisted": False,
    }
    receipt = {
        **body,
        "receipt_hmac_sha256": hmac.new(
            root, AUTHORITY_HMAC_DOMAIN + canonical_json_bytes(body), hashlib.sha256
        ).hexdigest().upper(),
    }
    _exclusive_write(path, canonical_json_bytes(receipt) + b"\n")
    return receipt


def verify_authority_receipt(repository: Path, root: bytes) -> dict[str, Any]:
    data = _regular_bytes(repository / AUTHORITY_RECEIPT_PATH, "semantic-XOR authority receipt")
    try:
        receipt = json.loads(data)
    except json.JSONDecodeError as exc:
        raise SemanticXorEvaluationError("authority receipt is malformed") from exc
    _require(isinstance(receipt, dict), "authority receipt is not an object")
    observed_hmac = receipt.get("receipt_hmac_sha256")
    body = {key: value for key, value in receipt.items() if key != "receipt_hmac_sha256"}
    expected_hmac = hmac.new(
        root, AUTHORITY_HMAC_DOMAIN + canonical_json_bytes(body), hashlib.sha256
    ).hexdigest().upper()
    _require(
        receipt.get("schema_version") == AUTHORITY_RECEIPT_SCHEMA_VERSION
        and receipt.get("consumed_once") is True
        and hmac.compare_digest(str(observed_hmac), expected_hmac),
        "authority receipt binding changed",
    )
    return {**receipt, "receipt_sha256": sha256_bytes(data)}


def state_paths(repository: Path) -> dict[str, Path]:
    root = repository / STATE_ROOT
    values = {
        "run_root": root,
        "run_lock": root / ".run.lock",
        "manifest": root / "manifest.json",
        "journal": root / "journal.jsonl",
        "result": root / "result.json",
        "closure": root / "closure.json",
        "receipt": repository / AUTHORITY_RECEIPT_PATH,
    }
    for request_id in REQUEST_IDS:
        values[f"capture-{request_id}"] = root / "captures" / f"{request_id}.json"
        values[f"partial-{request_id}"] = root / "captures" / f".{request_id}.raw.partial"
    return values


def _runtime_allowed_paths(paths: Mapping[str, Path]) -> tuple[Path, ...]:
    return tuple(path for name, path in paths.items() if name not in {"run_root", "receipt"})


class JournalWriter:
    def __init__(self, path: Path, key: bytes) -> None:
        self.path = path
        self.key = key
        self.events: list[dict[str, Any]] = []

    def append(
        self,
        state: str,
        *,
        request_id: str | None = None,
        facts: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        _require(request_id is None or request_id in REQUEST_IDS, "journal request identity changed")
        body = {
            "schema_version": 1,
            "design_id": DESIGN_ID,
            "event_index": len(self.events) + 1,
            "timestamp_utc": _utc_now(),
            "state": state,
            "request_id": request_id,
            "facts": dict(facts or {}),
            "previous_event_sha256": self.events[-1]["event_sha256"] if self.events else GENESIS_HASH,
        }
        without_hmac = {**body, "event_sha256": json_sha256(body)}
        event = {
            **without_hmac,
            "event_hmac_sha256": hmac.new(
                self.key,
                JOURNAL_HMAC_DOMAIN + canonical_json_bytes(without_hmac),
                hashlib.sha256,
            ).hexdigest().upper(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            with os.fdopen(descriptor, "ab", closefd=False) as handle:
                handle.write(canonical_json_bytes(event) + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(descriptor)
        self.events.append(event)
        return event


def verify_journal(path: Path, key: bytes) -> list[dict[str, Any]]:
    events = []
    previous = GENESIS_HASH
    for index, line in enumerate(_regular_bytes(path, "semantic-XOR journal").splitlines(), start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SemanticXorEvaluationError("semantic-XOR journal is malformed") from exc
        _require(isinstance(event, dict), "semantic-XOR journal event is malformed")
        observed_hmac = event.pop("event_hmac_sha256", None)
        observed_sha = event.get("event_sha256")
        body = {name: value for name, value in event.items() if name != "event_sha256"}
        _require(
            event.get("event_index") == index
            and event.get("design_id") == DESIGN_ID
            and event.get("previous_event_sha256") == previous
            and observed_sha == json_sha256(body),
            "semantic-XOR journal hash chain changed",
        )
        expected_hmac = hmac.new(
            key, JOURNAL_HMAC_DOMAIN + canonical_json_bytes(event), hashlib.sha256
        ).hexdigest().upper()
        _require(hmac.compare_digest(str(observed_hmac), expected_hmac), "semantic-XOR journal authentication changed")
        event["event_hmac_sha256"] = observed_hmac
        events.append(event)
        previous = str(observed_sha)
    return events


def assert_can_start(started: Sequence[str], request_id: str) -> None:
    _require(request_id in REQUEST_IDS, "generation request identity changed")
    _require(len(started) < 16, "sixteen-generation ceiling reached")
    _require(request_id not in started, "duplicate generation rejected")
    _require(request_id == REQUEST_IDS[len(started)], "generation order changed")


def _rendered_tokens(events: Sequence[Mapping[str, Any]], request_id: str) -> int:
    matches = [event for event in events if event.get("state") == "request-started" and event.get("request_id") == request_id]
    _require(len(matches) == 1, "request-start journal multiplicity changed")
    value = matches[0].get("facts", {}).get("rendered_prompt_tokens")
    _require(isinstance(value, int) and value > 0, "rendered token evidence changed")
    return value


def _structured_from_capture(capture: Mapping[str, Any], rendered_tokens: int) -> str:
    transport = kernel._normalized_transport(
        scientific.replay_capture(capture),
        rendered_tokens=rendered_tokens,
        max_tokens=MAXIMUM_COMPLETION_TOKENS,
    )
    structured = transport.get("structured_content")
    _require(isinstance(structured, str), "captured structured content changed")
    return structured


def _resource_record(capture: Mapping[str, Any], request_id: str) -> dict[str, Any]:
    execution = capture.get("execution")
    _require(isinstance(execution, Mapping), "capture resource evidence changed")
    prompt = execution.get("prompt_tokens")
    cached = execution.get("cached_prompt_tokens")
    completion = execution.get("completion_tokens")
    _require(isinstance(prompt, int) and prompt > 0, "capture prompt tokens changed")
    _require(cached == 0, "cache-disabled request reported cached tokens")
    _require(isinstance(completion, int) and completion > 0, "capture completion tokens changed")
    return {
        "request_id": request_id,
        "logical_prompt_tokens": prompt,
        "cached_prompt_tokens": cached,
        "completion_tokens": completion,
        "maximum_output_tokens": 8,
        "generation_count": 1,
        "maximum_request_context": prompt + 8,
    }


def verify_worker_artifacts_before_synthesis(
    *,
    paths: Mapping[str, Path],
    experiment_key: bytes,
    root: bytes,
    task_id: str,
    artifacts: Mapping[str, Mapping[str, Any]],
    outcome: Mapping[str, Any],
    fixed_request_hashes: Mapping[str, str],
) -> list[dict[str, Any]]:
    _require(set(artifacts) == set(WORKER_ROLES), "synthesis workers are incomplete")
    verified = []
    for worker_role in WORKER_ROLES:
        request_id = f"{task_id}-{worker_role}"
        ordinal = REQUEST_IDS.index(request_id) + 1
        request_sha = fixed_request_hashes[request_id]
        capture = scientific.verify_capture(
            paths[f"capture-{request_id}"],
            experiment_key=experiment_key,
            request_id=request_id,
            model_request_sha256=request_sha,
            generation_ordinal=ordinal,
        )
        captured_bit = outcome["worker_a_bit" if worker_role == "worker-A" else "worker_b_bit"]
        expected = build_worker_artifact(
            root,
            task_id=task_id,
            worker_role=worker_role,
            worker_request_sha256=request_sha,
            authenticated_capture_sha256=capture["capture_sha256"],
            captured_bit=captured_bit,
            generation_ordinal=ordinal,
        )
        _require(dict(artifacts[worker_role]) == expected, "worker artifact no longer binds authenticated capture")
        verified.append(expected)
    return verified


def _archive_terminal(repository: Path, paths: Mapping[str, Path]) -> dict[str, Any]:
    files = {
        "authority-receipt.json": paths["receipt"],
        "manifest.json": paths["manifest"],
        "journal.jsonl": paths["journal"],
        "result.json": paths["result"],
        "closure.json": paths["closure"],
    }
    for request_id in REQUEST_IDS:
        if paths[f"capture-{request_id}"].is_file():
            files[f"captures/{request_id}.json"] = paths[f"capture-{request_id}"]
    entries = []
    for name, path in sorted(files.items()):
        data = _regular_bytes(path, f"archive source {name}")
        entries.append({"path": name, "byte_size": len(data), "sha256": sha256_bytes(data)})
    body = {"schema_version": 1, "design_id": DESIGN_ID, "files": entries, "content_addressed": True}
    bundle_sha = json_sha256(body)
    destination = repository / ARCHIVE_ROOT / DESIGN_ID / bundle_sha
    _require(not destination.exists(), "archive destination already exists")
    destination.mkdir(parents=True)
    for name, source in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        _exclusive_write(target, _regular_bytes(source, f"archive source {name}"))
    _exclusive_write(destination / "bundle.json", canonical_json_bytes({**body, "bundle_sha256": bundle_sha}) + b"\n")
    for name, source in files.items():
        _require(
            _regular_bytes(destination / name, f"archived member {name}")
            == _regular_bytes(source, f"archive source {name}"),
            "archived evidence member changed",
        )
    return {
        "bundle_sha256": bundle_sha,
        "file_count": len(entries),
        "relative_path": destination.relative_to(repository).as_posix(),
        "verified": True,
    }


def run_evaluation(
    args: Any,
    *,
    repository_root: str | os.PathLike[str],
    adapter: Any | None = None,
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=False)
    source_authority.assert_test_repository_isolated(repository)
    _require(str(getattr(args, "design_id", "")) == DESIGN_ID, "live command design identity changed")
    raw_authority_id = getattr(args, "external_authority_id", None)
    authorized_commit = getattr(args, "authorized_commit", None)
    _require(isinstance(raw_authority_id, str) and isinstance(authorized_commit, str), "live evaluation requires external authority")
    model_path = Path(str(getattr(args, "model"))).resolve()
    prereg = validate_preregistration(repository, model_path)
    corpus = load_public_tasks(repository)
    tasks = {task["task_id"]: task for task in corpus["tasks"]}
    validate_protected_evaluator_custody(repository)
    root = _load_evidence_root(repository)
    fixed_payloads = build_fixed_payloads(corpus)
    fixed_hashes = prereg["request_bindings"]["fixed_worker_and_baseline_request_sha256"]
    derivation_hash = prereg["request_bindings"]["synthesis_derivation_law"]["sha256"]
    paths = state_paths(repository)
    _require(not paths["receipt"].exists() and not paths["run_root"].exists(), "semantic-XOR live state already exists")
    for name, path in paths.items():
        if name != "run_root":
            transaction._require_ignored(repository, path)
    live = adapter or kernel.CatalyticKernel0Adapter(repository)
    full_preflight = live.preflight(
        args=args,
        repository_root=repository,
        run_root=paths["run_root"],
        allowed_paths=_runtime_allowed_paths(paths),
    )
    public_preflight = runtime_support._public_preflight(full_preflight)
    authority = build_external_authority(
        repository,
        model_path,
        raw_authority_id=raw_authority_id,
        authorized_commit=authorized_commit,
        current_commit=str(public_preflight.get("stable", {}).get("head", "")),
        observed_model_sha256=str(public_preflight.get("model_identity", {}).get("sha256", "")),
        observed_binary_sha256=str(public_preflight.get("binary_identity", {}).get("sha256", "")),
    )
    manifest = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "authority": authority,
        "preregistration_artifact_sha256": prereg["artifact_sha256"],
        "fixed_request_sha256": fixed_hashes,
        "synthesis_derivation_law_sha256": derivation_hash,
        "execution_order": list(REQUEST_IDS),
        "preflight": public_preflight,
        "claiming": False,
    }
    paths["run_root"].mkdir(parents=True)
    manifest_data = canonical_json_bytes(manifest) + b"\n"
    _exclusive_write(paths["manifest"], manifest_data)
    consume_authority_once(repository, root, authority)
    verify_authority_receipt(repository, root)
    experiment_key = _experiment_key(root)
    journal = JournalWriter(paths["journal"], experiment_key)
    journal.append(
        "authority-consumed",
        facts={"authority_receipt_sha256": sha256_bytes(_regular_bytes(paths["receipt"], "authority receipt"))},
    )
    started: list[str] = []
    captures: dict[str, dict[str, Any]] = {}
    artifacts: dict[str, dict[str, dict[str, Any]]] = {task_id: {} for task_id in TASK_IDS}
    outcomes: dict[str, dict[str, Any]] = {task_id: {} for task_id in TASK_IDS}
    failure: dict[str, Any] | None = None
    cleanup: dict[str, Any] = {"passed": False}
    postflight: dict[str, Any] = {"passed": False}
    sidecar: Any | None = None
    with transaction.run_lock(paths["run_lock"]):
        pool = live.create_lease_pool(1)
        try:
            sidecar, _readiness = live.launch_sidecar(preflight=full_preflight, run_id=DESIGN_ID)
            for request_id in REQUEST_IDS:
                assert_can_start(started, request_id)
                task_id = request_task_id(request_id)
                role = request_role(request_id)
                if role == "synthesis":
                    worker_artifacts = verify_worker_artifacts_before_synthesis(
                        paths=paths,
                        experiment_key=experiment_key,
                        root=root,
                        task_id=task_id,
                        artifacts=artifacts[task_id],
                        outcome=outcomes[task_id],
                        fixed_request_hashes=fixed_hashes,
                    )
                    payload = build_synthesis_request(corpus, task_id, worker_artifacts)
                    expected_hash = verify_synthesis_payload(corpus, task_id, worker_artifacts, payload)
                    hash_mode = "derived-synthesis"
                else:
                    payload = fixed_payloads[request_id]
                    expected_hash = fixed_hashes[request_id]
                    hash_mode = "fixed"
                started.append(request_id)
                capture = scientific.execute_and_capture_request(
                    experiment_key=experiment_key,
                    frozen_binding_sha256=authority["frozen_scientific_binding_sha256"],
                    synthesis_derivation_law_sha256=derivation_hash,
                    payload=payload,
                    request_id=request_id,
                    expected_request_sha256=expected_hash,
                    generation_ordinal=len(started),
                    request_hash_mode=hash_mode,
                    live=live,
                    sidecar=sidecar,
                    pool=pool,
                    full_preflight=full_preflight,
                    capture_path=paths[f"capture-{request_id}"],
                    partial_path=paths[f"partial-{request_id}"],
                    append_event=journal.append,
                )
                captures[request_id] = capture
                structured = _structured_from_capture(capture, _rendered_tokens(journal.events, request_id))
                if role in WORKER_ROLES:
                    bit = parse_worker_output(structured)
                    outcomes[task_id]["worker_a_bit" if role == "worker-A" else "worker_b_bit"] = bit
                    artifacts[task_id][role] = build_worker_artifact(
                        root,
                        task_id=task_id,
                        worker_role=role,
                        worker_request_sha256=expected_hash,
                        authenticated_capture_sha256=capture["capture_sha256"],
                        captured_bit=bit,
                        generation_ordinal=len(started),
                    )
                    journal.append(
                        "worker-output-admitted",
                        request_id=request_id,
                        facts={
                            "authenticated_capture_sha256": capture["capture_sha256"],
                            "source_capture_commitment_sha256": artifacts[task_id][role]["source_capture_commitment_sha256"],
                            "semantic_correctness_consulted": False,
                        },
                    )
                else:
                    label = parse_label_output(structured)
                    outcomes[task_id]["synthesis_label" if role == "synthesis" else "baseline_label"] = label
                    journal.append(
                        "label-output-admitted",
                        request_id=request_id,
                        facts={
                            "authenticated_capture_sha256": capture["capture_sha256"],
                            "semantic_correctness_consulted": False,
                        },
                    )
        except BaseException as exc:
            failure = {
                "failure_sha256": sha256_bytes(str(exc).encode("utf-8")),
                "retry_allowed": False,
            }
            journal.append(
                "lifecycle-failed",
                request_id=started[-1] if started else None,
                facts=failure,
            )
        finally:
            try:
                cleanup = dict(live.cleanup(sidecar=sidecar, preflight=full_preflight))
            except BaseException as exc:
                cleanup = {"passed": False, "failure_sha256": sha256_bytes(str(exc).encode("utf-8"))}
            try:
                postflight = dict(live.postflight(preflight=full_preflight))
            except BaseException as exc:
                postflight = {"passed": False, "failure_sha256": sha256_bytes(str(exc).encode("utf-8"))}

    scoring: dict[str, Any] | None = None
    resources: dict[str, Any] | None = None
    classification = "INCONCLUSIVE"
    if failure is None and tuple(captures) == REQUEST_IDS:
        try:
            scoring = score_protected_outcomes(
                repository,
                outcomes,
                completed_capture_ids=tuple(captures),
                cleanup_passed=cleanup.get("passed") is True,
                postflight_passed=postflight.get("passed") is True,
            )
            classification = capability_classification(
                scoring,
                evidence_complete=True,
                cleanup_passed=cleanup.get("passed") is True,
                postflight_passed=postflight.get("passed") is True,
            )
            request_records = [_resource_record(captures[request_id], request_id) for request_id in REQUEST_IDS]
            resources = account_resources(request_records, scoring, classification)
        except BaseException as exc:
            failure = {
                "failure_sha256": sha256_bytes(str(exc).encode("utf-8")),
                "retry_allowed": False,
            }
            classification = "INCONCLUSIVE"
    if cleanup.get("passed") is not True or postflight.get("passed") is not True:
        classification = "INCONCLUSIVE"
    status = (
        "complete"
        if classification != "INCONCLUSIVE"
        and tuple(captures) == REQUEST_IDS
        and cleanup.get("passed") is True
        and postflight.get("passed") is True
        else "inconclusive"
    )
    result = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "status": status,
        "terminal_classification": classification,
        "advantage_classification": resources["advantage_classification"] if resources else ADVANTAGE_NOT_SUPPORTED,
        "completed_model_generations": len(started),
        "maximum_model_generations": 16,
        "request_dispositions": [
            {
                "request_id": request_id,
                "disposition": (
                    "captured" if request_id in captures else "started-no-capture" if request_id in started else "not-started"
                ),
            }
            for request_id in REQUEST_IDS
        ],
        "capture_sha256": {request_id: capture["capture_sha256"] for request_id, capture in captures.items()},
        "protected_scoring": scoring,
        "resource_accounting": resources,
        "failure": failure,
        "cleanup": cleanup,
        "postflight": postflight,
        "claims": dict(LOCKED_CLAIMS),
        "claiming": False,
        "automatic_follow_on": False,
    }
    _assert_public_no_smuggle(result)
    result_data = canonical_json_bytes(result) + b"\n"
    _exclusive_write(paths["result"], result_data)
    closure = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "status": status,
        "manifest_sha256": sha256_bytes(manifest_data),
        "result_sha256": sha256_bytes(result_data),
        "authority_receipt_sha256": sha256_bytes(_regular_bytes(paths["receipt"], "authority receipt")),
        "run_lock_absent_at_terminal_publication": not paths["run_lock"].exists(),
        "retry_allowed": False,
        "claiming": False,
    }
    closure_data = canonical_json_bytes(closure) + b"\n"
    _exclusive_write(paths["closure"], closure_data)
    journal.append(
        "terminal-written",
        facts={
            "result_sha256": sha256_bytes(result_data),
            "closure_sha256": sha256_bytes(closure_data),
            "status": status,
        },
    )
    verify_journal(paths["journal"], experiment_key)
    archive = _archive_terminal(repository, paths)
    return {**result, "evidence_archive_sha256": archive["bundle_sha256"]}


def validate_static(repository: Path, model_path: Path) -> dict[str, Any]:
    prereg = validate_preregistration(repository, model_path)
    paths = state_paths(repository)
    _require(not paths["receipt"].exists() and not paths["run_root"].exists(), "live semantic-XOR state already exists")
    return {
        "status": "pass",
        "design_id": DESIGN_ID,
        "preregistration_artifact_sha256": prereg["artifact_sha256"],
        "frozen_scientific_binding_sha256": prereg["bindings"]["frozen_scientific"]["sha256"],
        "controller_binding_sha256": prereg["bindings"]["controller"]["sha256"],
        "protected_scorer_binding_sha256": prereg["bindings"]["protected_scorer"]["sha256"],
        "resource_accounting_binding_sha256": prereg["bindings"]["resource_accounting"]["sha256"],
        "fixed_request_count": 12,
        "derived_synthesis_request_count": 4,
        "future_model_generations": 16,
        "authority_created": False,
        "authority_consumed": False,
        "model_requests_issued": 0,
        "sidecar_launched": False,
        "live_execution_performed": False,
        "scientific_result_created": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "validate", "run"))
    parser.add_argument("--repository", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--model", required=True)
    parser.add_argument("--binary")
    parser.add_argument("--design-id", default=DESIGN_ID)
    parser.add_argument("--external-authority-id")
    parser.add_argument("--authorized-commit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository = Path(args.repository).resolve()
    model_path = Path(args.model).resolve()
    if args.command == "prepare":
        path = write_preregistration(repository, model_path)
        print(canonical_json_text({"status": "prepared", "path": path.relative_to(repository).as_posix()}))
        return 0
    if args.command == "validate":
        print(canonical_json_text(validate_static(repository, model_path)))
        return 0
    _require(args.binary is not None, "live run requires binary")
    print(canonical_json_text(run_evaluation(args, repository_root=repository)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
