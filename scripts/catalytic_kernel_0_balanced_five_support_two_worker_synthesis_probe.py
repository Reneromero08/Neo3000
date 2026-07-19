#!/usr/bin/env python3
"""Three-request five-support worker-relation synthesis probe.

The static path reconstructs the frozen bilateral profile from public
projections, admits hidden utility only after that freeze, reuses the existing
private shared alias namespace, and binds two worker requests plus one
rank-head-v2 synthesis request.  The live path remains closed until a later
external one-shot authority binds the published static commit.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import catalytic_inference_bench_0_runtime as runtime_support
import catalytic_kernel_0 as kernel
import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_parent_dependence_cross_binding_asymmetry_audit as asymmetry
import catalytic_kernel_0_balanced_rank_head_v2 as v2
import catalytic_kernel_0_balanced_rank_head_v2_authority as source_authority
import catalytic_kernel_0_balanced_rank_head_v2_joint_condition_intersection_replication as source_binding
import catalytic_kernel_0_balanced_rank_head_v2_parent_dependence as transaction
import catalytic_kernel_0_balanced_five_support_two_worker_synthesis_probe_scientific as scientific


class FiveSupportWorkerSynthesisError(ValueError):
    """The frozen profile, private binding, or one-shot contract changed."""


DESIGN_ID = scientific.DESIGN_ID
STARTING_PROTECTED_MAIN = "38e1aac0fd88d839089919c6f3d0de20d749a7be"
PREREGISTRATION_PATH = Path(
    "lab/ck0_balanced_opaque_five_support_two_worker_synthesis_probe_1.json"
)
PRIVATE_ROOT_PATH = source_binding.PRIVATE_ROOT_PATH
PRIVATE_RECEIPT_PATH = source_binding.PRIVATE_RECEIPT_PATH
STATE_ROOT = Path("state/catalytic_kernel_0/five_support_two_worker_synthesis_probe_v1")
ARCHIVE_ROOT = Path(
    "state/catalytic_kernel_0/five_support_two_worker_synthesis_evidence_archive/v1"
)
AUTHORITY_RECEIPT_PATH = Path(
    "state/catalytic_kernel_0_authority.five-support-two-worker-synthesis-v1.authority.consumed.json"
)
REQUEST_IDS = scientific.REQUEST_IDS
EXECUTION_ORDER = REQUEST_IDS
WORKER_IDS = ("worker-A", "worker-B")
WORKER_INDICES = {"worker-A": (0, 1, 2), "worker-B": (2, 3, 4)}
WORKER_ROLES = {"worker-A": "parent-0", "worker-B": "parent-1"}
WORKER_INSTRUCTION = (
    "Return every opaque candidate whose sealed outputs exactly satisfy all "
    "three supplied public examples. Return no other candidate."
)
SYNTHESIS_SEED = 633514649
MODEL_SHA256 = asymmetry.EXPECTED_MODEL_SHA256
BINARY_SHA256 = transaction.BINARY_SHA256
SYNTHESIS_CARRIER = v2.build_v2_carrier()
SYNTHESIS_CARRIER_ROOT_SHA256 = SYNTHESIS_CARRIER["carrier_root_sha256"]
EXPECTED_ROOT_COMMITMENT = "7999FE7862527BE08589EFF15B8AD7CFBC9F81C44C1FB7804E0AF31F34BD72FD"
EXPECTED_ALIAS_MAP_COMMITMENT = "535DDE006301B618155CC7613EC32628C4020BB43BA1363E93540F3EDB69A21D"
EXPECTED_SUITE_SHA256 = "4B9961D5054BE5D98EF315D2DEAE9D1604E0042A69CB02A8B81FDF513BC1FC92"
EXPECTED_PROFILE_BINDING_SHA256 = "44F2CC29268F5ED2086DB91491296F51B51FE9D891F84BFC807B99D4D492A7A0"
EXPECTED_TASK_INDEX = 2
EXPECTED_TASK_ID = "cs1-task-03"
WORKER_SEED_DOMAIN = b"ck0/five-support-two-worker-synthesis/worker-seed-v1\0"
PROFILE_COMMITMENT_DOMAIN = b"ck0/five-support-two-worker-synthesis/profile-v1\0"
SHARD_COMMITMENT_DOMAIN = b"ck0/five-support-two-worker-synthesis/shard-v1\0"
SUPPORT_COMMITMENT_DOMAIN = b"ck0/five-support-two-worker-synthesis/support-v1\0"
INTERSECTION_COMMITMENT_DOMAIN = b"ck0/five-support-two-worker-synthesis/intersection-v1\0"
NORMALIZATION_DOMAIN = b"ck0/five-support-two-worker-synthesis/normalization-v1\0"
PASS_CLASS_DOMAIN = b"ck0/five-support-two-worker-synthesis/pass-class-v1\0"
CAPTURE_SOURCE_DOMAIN = b"ck0/five-support-two-worker-synthesis/capture-source-v1\0"
ARTIFACT_DOMAIN = b"ck0/five-support-two-worker-synthesis/artifact-v1\0"
TRANSFORM_DOMAIN = b"ck0/five-support-two-worker-synthesis/transform-v1\0"
EXPERIMENT_KEY_DOMAIN = b"ck0/five-support-two-worker-synthesis/experiment-key-v1\0"
AUTHORITY_ID_DOMAIN = b"ck0/five-support-two-worker-synthesis/authority-id-v1\0"
AUTHORITY_HMAC_DOMAIN = b"ck0/five-support-two-worker-synthesis/authority-hmac-v1\0"
JOURNAL_HMAC_DOMAIN = b"ck0/five-support-two-worker-synthesis/journal-hmac-v1\0"
AUTHORITY_SCHEMA_VERSION = "five-support-two-worker-synthesis-authority-v1"
AUTHORITY_RECEIPT_SCHEMA_VERSION = "five-support-two-worker-synthesis-consumption-v1"
AUTHORITY_KIND = "external-one-shot-five-support-two-worker-synthesis"
GENESIS_HASH = "0" * 64
SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
AUTHORITY_ID_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
INTERNAL_ID_RE = re.compile(r"(?<![A-Za-z0-9])C\d{2}(?![A-Za-z0-9])")
LOCKED_CLAIMS = {
    "three_worker_synthesis": "locked",
    "general_worker_synthesis": "locked",
    "multi_task_transfer": "locked",
    "equal_budget_advantage": "locked",
    "reduced_fresh_computation": "locked",
    "compute_amplification": "locked",
    "complete_borrow_transform_extract_restore": "locked",
    "persistent_blackboard_value": "locked",
    "adaptive_population": "locked",
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


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FiveSupportWorkerSynthesisError(message)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _regular_bytes(path: Path, label: str, maximum: int = 4 * 1024 * 1024) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise FiveSupportWorkerSynthesisError(f"{label} is not a regular file")
        data = path.read_bytes()
    except OSError as exc:
        raise FiveSupportWorkerSynthesisError(f"{label} is unreadable") from exc
    _require(0 < len(data) <= maximum, f"{label} has an unsafe size")
    return data


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
        _require(_regular_bytes(path, "existing preregistration") == data, "preregistration bytes changed")
        return
    _exclusive_write(path, data)


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    _require(completed.returncode == 0, f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def _private_hmac(root: bytes, domain: bytes, value: Any) -> str:
    _require(len(root) == 32, "private root length changed")
    return hmac.new(root, domain + canonical_json_bytes(value), hashlib.sha256).hexdigest().upper()


def _tracked_no_smuggle(value: Any) -> None:
    text = canonical_json_text(value)
    _require(EXPECTED_TASK_ID not in text, "stable task identity entered tracked evidence")
    _require(not INTERNAL_ID_RE.search(text), "internal candidate identity entered tracked evidence")
    _require(not re.search(r'"K\d{2}"', text), "opaque alias entered tracked evidence")
    forbidden_keys = {
        "answer_candidate_id",
        "alias_to_internal",
        "hidden_examples",
        "private_root_bytes",
        "cross_binding_correspondence",
    }

    def walk(item: Any) -> None:
        if isinstance(item, Mapping):
            _require(not (set(item) & forbidden_keys), "forbidden field entered tracked evidence")
            for nested in item.values():
                walk(nested)
        elif isinstance(item, (list, tuple)):
            for nested in item:
                walk(nested)

    walk(value)


def derive_worker_seed() -> int:
    material = (
        DESIGN_ID.encode("utf-8")
        + b"\0"
        + STARTING_PROTECTED_MAIN.encode("ascii")
        + b"\0worker-seed-v1"
    )
    digest = hashlib.sha256(WORKER_SEED_DOMAIN + material).digest()
    return 1 + int.from_bytes(digest[:8], "big") % ((1 << 31) - 2)


WORKER_SEED = derive_worker_seed()


def _load_private(repository: Path) -> tuple[bytes, balanced.PrivateBinding]:
    root, private = source_binding._load_private(repository)
    _require(private.secret_commitment == EXPECTED_ROOT_COMMITMENT, "private root commitment changed")
    _require(private.alias_map_commitment == EXPECTED_ALIAS_MAP_COMMITMENT, "shared alias map commitment changed")
    _require(private.profile_binding_sha256 == EXPECTED_PROFILE_BINDING_SHA256, "private profile binding changed")
    return root, private


def public_profile_admission() -> dict[str, Any]:
    profile, profile_sha = balanced.build_profile_binding(source_binding.PROBE_CONFIGURATION)
    _require(profile_sha == EXPECTED_PROFILE_BINDING_SHA256, "public profile binding changed")
    _require(profile["task_index"] == EXPECTED_TASK_INDEX, "frozen task index changed")
    _require(profile["branch_indices"] == {"branch-a": [0, 1, 2], "branch-b": [2, 3, 4]}, "frozen shards changed")
    supports = profile["support_sets"]
    intersection = sorted(set(supports["branch-a"]) & set(supports["branch-b"]))
    _require(len(supports["branch-a"]) == len(supports["branch-b"]) == 5, "worker support cardinality changed")
    _require(intersection == profile["full_public_support"] and len(intersection) == 1, "support intersection changed")
    _require(profile["top_scores"] == {"branch-a": 3, "branch-b": 3}, "local top scores changed")
    _require(profile["plateau_gaps"] == {"branch-a": 1, "branch-b": 1}, "local plateau gaps changed")
    _require(
        profile["support_pass_vectors"] == {"branch-a": [True, True, True], "branch-b": [True, True, True]},
        "local pass equivalence changed",
    )
    return {
        "profile": profile,
        "profile_binding_sha256": profile_sha,
        "frozen_before_hidden_utility": True,
        "shard_union_cardinality": 5,
        "shard_overlap_cardinality": 1,
        "support_intersection_cardinality": 1,
    }


def protected_utility_gate(admission: Mapping[str, Any]) -> dict[str, Any]:
    _require(admission.get("frozen_before_hidden_utility") is True, "hidden utility preceded profile freeze")
    task = balanced.build_frozen_task_suite().tasks[EXPECTED_TASK_INDEX]
    internal = admission["profile"]["full_public_support"][0]
    candidate = next(item for item in task.candidates if item.candidate_id == internal)
    hidden_score = sum(
        balanced.execute_program(candidate, example.x) == example.y
        for example in task.hidden_examples
    )
    _require(hidden_score == len(task.hidden_examples) == 16, "FROZEN_BALANCED_PROFILE_NOT_HIDDEN_EXACT")
    return {
        "classification": "FROZEN_BALANCED_PROFILE_HIDDEN_EXACT",
        "profile_frozen_before_hidden_consultation": True,
        "unique_full_public_support_equals_protected_answer": internal == task.answer_candidate_id,
        "hidden_exact": True,
        "hidden_score": 16,
        "hidden_total": 16,
        "answer_disclosed": False,
    }


def worker_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["support_aliases"],
        "properties": {
            "support_aliases": {
                "type": "array",
                "items": {"type": "string", "enum": list(balanced.ALIASES)},
                "minItems": 5,
                "maxItems": 5,
                "uniqueItems": True,
            }
        },
    }


def synthesis_response_schema() -> dict[str, Any]:
    return balanced.response_schema("transform")


def _sealed_projection(
    private: balanced.PrivateBinding,
    worker_id: str,
) -> dict[str, Any]:
    _require(worker_id in WORKER_IDS, "worker identity changed")
    task = balanced.build_frozen_task_suite().tasks[EXPECTED_TASK_INDEX]
    indices = WORKER_INDICES[worker_id]
    candidates = {item.candidate_id: item for item in task.candidates}
    raw_values = [task.public_examples[index].y for index in indices]
    for alias in balanced.ALIASES:
        candidate = candidates[private.alias_to_internal[alias]]
        raw_values.extend(
            balanced.execute_program(candidate, task.public_examples[index].x)
            for index in indices
        )
    unique = sorted({canonical_json_text(value) for value in raw_values})
    _require(len(unique) <= 999, "sealed output vocabulary exceeded")
    labels = {value: f"V{ordinal:03d}" for ordinal, value in enumerate(unique)}
    examples = [
        {
            "example_id": f"E{ordinal}",
            "sealed_expected_output": labels[canonical_json_text(task.public_examples[index].y)],
        }
        for ordinal, index in enumerate(indices)
    ]
    projected_candidates = []
    for alias in balanced.ALIASES:
        candidate = candidates[private.alias_to_internal[alias]]
        projected_candidates.append(
            {
                "candidate_alias": alias,
                "sealed_extensional_outputs": [
                    {
                        "example_id": f"E{ordinal}",
                        "sealed_output": labels[
                            canonical_json_text(
                                balanced.execute_program(candidate, task.public_examples[index].x)
                            )
                        ],
                    }
                    for ordinal, index in enumerate(indices)
                ],
            }
        )
    return {
        "carrier_kind": "opaque-worker-relation-carrier-v1",
        "worker_role": WORKER_ROLES[worker_id],
        "generic_dsl_semantics": dict(task.public_projection()["semantics"]),
        "public_examples": examples,
        "opaque_candidates": projected_candidates,
        "response_schema": worker_response_schema(),
        "instruction": WORKER_INSTRUCTION,
    }


def build_worker_request(private: balanced.PrivateBinding, worker_id: str) -> dict[str, Any]:
    carrier = _sealed_projection(private, worker_id)
    return {
        "model": "agents-a1",
        "messages": [
            {
                "role": "system",
                "content": "Use only the supplied sealed extensional relation and return strict JSON.",
            },
            {"role": "user", "content": canonical_json_text(carrier)},
        ],
        "temperature": 0.0,
        "seed": WORKER_SEED,
        "max_tokens": 64,
        "stream": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "five_support_worker_relation",
                "strict": True,
                "schema": worker_response_schema(),
            },
        },
        "stream_options": {"include_usage": True},
        "cache_prompt": True,
        "return_tokens": True,
        "return_progress": True,
        "verbose": True,
    }


def _objective_support_aliases(
    private: balanced.PrivateBinding,
    admission: Mapping[str, Any],
    worker_id: str,
) -> tuple[str, ...]:
    branch = "branch-a" if worker_id == "worker-A" else "branch-b"
    return tuple(
        private.internal_to_alias[internal]
        for internal in admission["profile"]["support_sets"][branch]
    )


def _normalized_support(root: bytes, worker_id: str, aliases: Sequence[str]) -> list[str]:
    return sorted(
        aliases,
        key=lambda alias: (
            hmac.new(root, NORMALIZATION_DOMAIN + worker_id.encode("ascii") + b"\0" + alias.encode("ascii"), hashlib.sha256).digest(),
            alias,
        ),
    )


def validate_worker_relation(
    root: bytes,
    private: balanced.PrivateBinding,
    admission: Mapping[str, Any],
    worker_id: str,
    structured_content: str,
) -> tuple[list[str], list[str]]:
    try:
        value = json.loads(structured_content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise FiveSupportWorkerSynthesisError("worker relation is invalid JSON") from exc
    _require(isinstance(value, dict) and set(value) == {"support_aliases"}, "worker response fields changed")
    authored = value["support_aliases"]
    _require(
        isinstance(authored, list)
        and len(authored) == 5
        and len(set(authored)) == 5
        and all(alias in balanced.ALIASES for alias in authored),
        "worker relation schema changed",
    )
    objective = _objective_support_aliases(private, admission, worker_id)
    _require(set(authored) == set(objective), "FIVE_SUPPORT_WORKER_RELATION_GENERATION_NOT_SUPPORTED")
    return [str(alias) for alias in authored], _normalized_support(root, worker_id, authored)


def build_worker_artifact(
    root: bytes,
    worker_id: str,
    authored_order: Sequence[str],
    normalized_order: Sequence[str],
    source_capture_commitment_sha256: str,
) -> dict[str, Any]:
    _require(worker_id in WORKER_IDS and len(authored_order) == len(normalized_order) == 5, "worker artifact input changed")
    _require(set(authored_order) == set(normalized_order), "worker normalization changed relation membership")
    body = {
        "worker_role": WORKER_ROLES[worker_id],
        "support_aliases": list(normalized_order),
        "tied_top_score": "3/3",
        "pass_equivalence_class_commitment_sha256": _private_hmac(
            root,
            PASS_CLASS_DOMAIN,
            {"worker_id": worker_id, "pass_vector": [True, True, True], "support_cardinality": 5},
        ),
        "source_worker_capture_commitment_sha256": source_capture_commitment_sha256,
    }
    return {**body, "artifact_commitment": _private_hmac(root, ARTIFACT_DOMAIN, body)}


def build_synthesis_request(artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    _require(set(artifacts) == set(WORKER_IDS), "synthesis parents are incomplete")
    assignment = {
        "stage": "transform",
        "instruction": (
            "Operate only on the two supplied opaque worker relations. Return one "
            "allowed operator and an ordered ranking of exactly three shared opaque aliases."
        ),
        "parent_artifacts": [dict(artifacts[worker_id]) for worker_id in WORKER_IDS],
    }
    return {
        "model": "agents-a1",
        "messages": [
            {"role": "system", "content": SYNTHESIS_CARRIER["carrier_root"]},
            {"role": "user", "content": canonical_json_text(assignment)},
        ],
        "temperature": 0.0,
        "seed": SYNTHESIS_SEED,
        "max_tokens": 64,
        "stream": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "five_support_synthesis",
                "strict": True,
                "schema": synthesis_response_schema(),
            },
        },
        "stream_options": {"include_usage": True},
        "cache_prompt": True,
        "return_tokens": True,
        "return_progress": True,
        "verbose": True,
    }


def _source_capture_commitment(
    root: bytes,
    worker_id: str,
    model_request_sha256: str,
) -> str:
    _require(worker_id in WORKER_IDS and SHA256_RE.fullmatch(model_request_sha256) is not None, "capture source identity changed")
    return _private_hmac(
        root,
        CAPTURE_SOURCE_DOMAIN,
        {
            "worker_id": worker_id,
            "model_request_sha256": model_request_sha256,
            "generation_ordinal": EXECUTION_ORDER.index(worker_id) + 1,
            "authenticated_capture_required": True,
        },
    )


def _placeholder_artifacts(
    root: bytes,
    private: balanced.PrivateBinding,
    admission: Mapping[str, Any],
    worker_request_hashes: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    artifacts = {}
    for worker_id in WORKER_IDS:
        objective = _objective_support_aliases(private, admission, worker_id)
        normalized = _normalized_support(root, worker_id, objective)
        artifacts[worker_id] = build_worker_artifact(
            root,
            worker_id,
            objective,
            normalized,
            _source_capture_commitment(root, worker_id, worker_request_hashes[worker_id]),
        )
    return artifacts


def build_payloads(
    root: bytes,
    private: balanced.PrivateBinding,
    admission: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    workers = {
        worker_id: build_worker_request(private, worker_id) for worker_id in WORKER_IDS
    }
    worker_request_hashes = {
        worker_id: json_sha256(payload) for worker_id, payload in workers.items()
    }
    artifacts = _placeholder_artifacts(
        root, private, admission, worker_request_hashes
    )
    return {
        **workers,
        "synthesis-AB": build_synthesis_request(artifacts),
    }


def request_isolation_report(payloads: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    _require(set(payloads) == set(REQUEST_IDS), "request payload set changed")
    worker_text = {worker_id: canonical_json_text(payloads[worker_id]) for worker_id in WORKER_IDS}
    synthesis_text = canonical_json_text(payloads["synthesis-AB"])
    forbidden_synthesis = (
        "public_examples",
        "opaque_candidates",
        "sealed_output",
        "generic_dsl_semantics",
        "controller_computed_intersection",
        "hidden",
        "answer",
    )
    _require(not any(value in synthesis_text for value in forbidden_synthesis), "synthesis request received forbidden task evidence")
    return {
        "worker_payload_byte_lengths": {key: len(value.encode("utf-8")) for key, value in worker_text.items()},
        "synthesis_receives_only_validated_artifacts": True,
        "workers_share_candidate_alias_namespace": True,
        "workers_receive_only_local_anonymous_examples": True,
        "synthesis_forbidden_fields_absent": True,
    }


class _SynthesisRuntime:
    def __init__(self, root: bytes) -> None:
        self.root = root

    def normalize_transform(self, operator: str, ranking: Sequence[str]) -> dict[str, Any]:
        _require(operator in balanced.ALLOWED_OPERATORS, "synthesis operator changed")
        values = list(ranking)
        _require(len(values) == 3 and len(set(values)) == 3 and all(item in balanced.ALIASES for item in values), "synthesis ranking changed")
        body = {"operator": operator, "ranking": values}
        return {**body, "artifact_commitment": _private_hmac(self.root, TRANSFORM_DOMAIN, body)}

    def verify_transform_artifact(self, transform: Mapping[str, Any]) -> None:
        body = {"operator": transform.get("operator"), "ranking": transform.get("ranking")}
        _require(
            transform.get("artifact_commitment") == _private_hmac(self.root, TRANSFORM_DOMAIN, body),
            "synthesis transform commitment changed",
        )


def parse_synthesis(root: bytes, structured_content: str) -> tuple[dict[str, Any], Any]:
    try:
        value = json.loads(structured_content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise FiveSupportWorkerSynthesisError("synthesis response is invalid JSON") from exc
    _require(isinstance(value, dict) and set(value) == {"operator", "ranking"}, "synthesis response fields changed")
    runtime = _SynthesisRuntime(root)
    transform = runtime.normalize_transform(str(value["operator"]), value["ranking"])
    frozen = v2.freeze_rank_head_selection(runtime, transform)
    return transform, frozen


def _commitments(
    root: bytes,
    private: balanced.PrivateBinding,
    admission: Mapping[str, Any],
) -> dict[str, Any]:
    profile = admission["profile"]
    support_aliases = {
        worker_id: _objective_support_aliases(private, admission, worker_id)
        for worker_id in WORKER_IDS
    }
    intersection = sorted(set(support_aliases["worker-A"]) & set(support_aliases["worker-B"]))
    _require(len(intersection) == 1, "private support intersection changed")
    return {
        "frozen_profile_commitment_sha256": sha256_bytes(
            PROFILE_COMMITMENT_DOMAIN + canonical_json_bytes(profile)
        ),
        "worker_shard_commitments": {
            worker_id: sha256_bytes(
                SHARD_COMMITMENT_DOMAIN + worker_id.encode("ascii") + canonical_json_bytes(list(indices))
            )
            for worker_id, indices in WORKER_INDICES.items()
        },
        "worker_support_commitments": {
            worker_id: _private_hmac(root, SUPPORT_COMMITMENT_DOMAIN, {"worker_id": worker_id, "aliases": list(aliases)})
            for worker_id, aliases in support_aliases.items()
        },
        "unique_intersection_commitment_sha256": _private_hmac(
            root, INTERSECTION_COMMITMENT_DOMAIN, {"aliases": intersection}
        ),
    }


def _file_binding(repository: Path, paths: Sequence[str]) -> dict[str, Any]:
    files = []
    for relative in paths:
        data = _regular_bytes(repository / relative, f"implementation file {relative}", 2 * 1024 * 1024)
        files.append({"path": relative, "byte_size": len(data), "sha256": sha256_bytes(data)})
    body = {"files": files}
    return {**body, "sha256": json_sha256(body)}


def _scientific_contract(
    commitments: Mapping[str, Any],
    request_hashes: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "design_id": DESIGN_ID,
        "request_ids": list(REQUEST_IDS),
        "execution_order": list(EXECUTION_ORDER),
        "request_sha256": dict(request_hashes),
        "private_binding_commitments": {
            "root_commitment_sha256": EXPECTED_ROOT_COMMITMENT,
            "alias_map_commitment_sha256": EXPECTED_ALIAS_MAP_COMMITMENT,
            "profile_binding_sha256": EXPECTED_PROFILE_BINDING_SHA256,
        },
        "frozen_profile_commitment_sha256": commitments["frozen_profile_commitment_sha256"],
        "worker_shard_commitments": commitments["worker_shard_commitments"],
        "worker_support_commitments": commitments["worker_support_commitments"],
        "unique_intersection_commitment_sha256": commitments["unique_intersection_commitment_sha256"],
        "worker_seed": WORKER_SEED,
        "synthesis_seed": SYNTHESIS_SEED,
        "model_sha256": MODEL_SHA256,
        "binary_sha256": BINARY_SHA256,
        "synthesis_carrier_root_sha256": SYNTHESIS_CARRIER_ROOT_SHA256,
        "response_schema_sha256": {
            "worker": json_sha256(worker_response_schema()),
            "synthesis": json_sha256(synthesis_response_schema()),
        },
        "physical_slots": 1,
        "sidecar_epochs": 1,
        "maximum_model_generations_per_request": 1,
        "maximum_total_model_generations": 3,
        "request_dispatch": "frozen-scientific-module-exact-hash-gate-before-contact",
        "raw_response_recording": "authenticated-capture-before-controller-parse",
    }


def build_preregistration_document(repository: Path, model_path: Path) -> dict[str, Any]:
    admission = public_profile_admission()
    utility = protected_utility_gate(admission)
    root, private = _load_private(repository)
    tokenizer = asymmetry.OfflineTokenizer(model_path.resolve())
    payloads = build_payloads(root, private, admission)
    isolation = request_isolation_report(payloads)
    worker_bytes = isolation["worker_payload_byte_lengths"]
    worker_tokens = {
        worker_id: tokenizer.length(canonical_json_text(payloads[worker_id]))
        for worker_id in WORKER_IDS
    }
    _require(len(set(worker_bytes.values())) == 1, "worker request canonical byte lengths differ")
    _require(len(set(worker_tokens.values())) == 1, "worker request pinned-tokenizer lengths differ")
    request_hashes = {request_id: json_sha256(payloads[request_id]) for request_id in REQUEST_IDS}
    commitments = _commitments(root, private, admission)
    contract = _scientific_contract(commitments, request_hashes)
    frozen = scientific.frozen_scientific_binding(repository, contract=contract, payloads=payloads)
    controller = _file_binding(
        repository,
        ["scripts/catalytic_kernel_0_balanced_five_support_two_worker_synthesis_probe.py"],
    )
    body = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "starting_protected_main": STARTING_PROTECTED_MAIN,
        "scientific_question": (
            "Can two isolated worker requests generate complete five-member local ambiguity relations "
            "that the evidenced pairwise transform synthesizes into their unique shared candidate?"
        ),
        "frozen_suite": {"suite_sha256": EXPECTED_SUITE_SHA256, "task_count": 8},
        "public_profile": {
            "task_index": 2,
            "worker_shards_zero_based": {"worker-A": [0, 1, 2], "worker-B": [2, 3, 4]},
            "shard_union_cardinality": 5,
            "shard_overlap_cardinality": 1,
            "worker_support_cardinality": {"worker-A": 5, "worker-B": 5},
            "support_intersection_cardinality": 1,
            "full_public_support_cardinality": 1,
            "local_top_scores": {"worker-A": "3/3", "worker-B": "3/3"},
            "local_plateau_gaps": {"worker-A": 1, "worker-B": 1},
            "all_support_pass_vectors_exact": True,
            **commitments,
            "selected_from_public_projections_only": True,
        },
        "protected_utility_gate": utility,
        "private_binding": {
            "root_commitment_sha256": EXPECTED_ROOT_COMMITMENT,
            "alias_map_commitment_sha256": EXPECTED_ALIAS_MAP_COMMITMENT,
            "profile_binding_sha256": EXPECTED_PROFILE_BINDING_SHA256,
            "existing_root_reused": True,
            "new_private_root_created": False,
            "private_mapping_published": False,
        },
        "worker_carrier": {
            "shared_candidate_alias_namespace": True,
            "local_sealed_extensional_outputs_only": True,
            "worker_schema_sha256": json_sha256(worker_response_schema()),
            "exact_return_cardinality": 5,
            "model_return_cannot_be_controller_repaired": True,
            "original_model_order_authenticated": True,
            "normalization_after_exact_validation_only": True,
            "canonical_payload_byte_lengths": worker_bytes,
            "pinned_tokenizer_payload_lengths": worker_tokens,
            "lengths_matched": True,
        },
        "synthesis_surface": {
            "carrier_root_sha256": SYNTHESIS_CARRIER_ROOT_SHA256,
            "response_schema_sha256": json_sha256(synthesis_response_schema()),
            "validated_artifacts_only": True,
            "controller_computed_intersection_visible": False,
            "raw_task_evidence_visible": False,
            "rank_zero_frozen_before_private_mapping": True,
        },
        "request_set": {
            "execution_order": list(EXECUTION_ORDER),
            "request_sha256": request_hashes,
            "worker_seed": WORKER_SEED,
            "worker_seed_derivation": "SHA-256(design ID + starting commit + worker-seed-v1)",
            "synthesis_seed": SYNTHESIS_SEED,
            "maximum_generations_per_request": 1,
            "maximum_total_generations": 3,
            "physical_slots": 1,
            "sidecar_epochs": 1,
            "retry_after_started_request": False,
        },
        "bindings": {
            "frozen_scientific": frozen,
            "controller": controller,
        },
        "decision_law": {
            "supported": "FIVE_SUPPORT_TWO_WORKER_RELATIONAL_SYNTHESIS_SUPPORTED_ON_ONE_FROZEN_TASK",
            "worker_relation_failure": "FIVE_SUPPORT_WORKER_RELATION_GENERATION_NOT_SUPPORTED",
            "synthesis_failure": "FIVE_SUPPORT_TWO_WORKER_RELATIONAL_SYNTHESIS_NOT_SUPPORTED",
            "utility_failure": "SYNTHESIS_SELECTED_PUBLIC_INTERSECTION_BUT_HIDDEN_UTILITY_NOT_SUPPORTED",
            "inconclusive": "incomplete execution, infrastructure, capture, custody, cleanup, or postflight failure",
        },
        "claim_limits": dict(LOCKED_CLAIMS),
        "execution_state": {
            "authority_created": False,
            "authority_consumed": False,
            "sidecar_launched": False,
            "model_requests_issued": 0,
            "model_generations": 0,
            "captures_created": 0,
            "result_created": False,
            "archive_created": False,
            "follow_on_designed": False,
        },
        "future_live_command_shape": (
            "python scripts/catalytic_kernel_0_balanced_five_support_two_worker_synthesis_probe.py run "
            "--repository <repository> --binary <verified-binary> --model <verified-model> "
            f"--design-id {DESIGN_ID} --external-authority-id <fresh-64-hex> "
            "--authorized-commit <published-static-commit>"
        ),
    }
    _tracked_no_smuggle(body)
    return {**body, "artifact_sha256": json_sha256(body)}


def write_preregistration(repository: Path, model_path: Path) -> Path:
    document = build_preregistration_document(repository, model_path)
    data = canonical_json_bytes(document) + b"\n"
    _write_or_require_identical(repository / PREREGISTRATION_PATH, data)
    return repository / PREREGISTRATION_PATH


def validate_preregistration(repository: Path, model_path: Path) -> dict[str, Any]:
    expected = build_preregistration_document(repository, model_path)
    path = repository / PREREGISTRATION_PATH
    data = _regular_bytes(path, "worker-synthesis preregistration", 2 * 1024 * 1024)
    _require(data == canonical_json_bytes(expected) + b"\n", "preregistration exact reconstruction changed")
    _require(expected["execution_state"] == {
        "authority_created": False,
        "authority_consumed": False,
        "sidecar_launched": False,
        "model_requests_issued": 0,
        "model_generations": 0,
        "captures_created": 0,
        "result_created": False,
        "archive_created": False,
        "follow_on_designed": False,
    }, "static execution state changed")
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
        "request_sha256": prereg["request_set"]["request_sha256"],
        "execution_order": list(EXECUTION_ORDER),
        "model_sha256": MODEL_SHA256,
        "binary_sha256": BINARY_SHA256,
        "maximum_model_generations": 3,
        "retry_allowed": False,
    }


def _experiment_key(root: bytes) -> bytes:
    return hmac.new(root, EXPERIMENT_KEY_DOMAIN + DESIGN_ID.encode("ascii"), hashlib.sha256).digest()


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
    data = _regular_bytes(repository / AUTHORITY_RECEIPT_PATH, "authority receipt")
    try:
        receipt = json.loads(data)
    except json.JSONDecodeError as exc:
        raise FiveSupportWorkerSynthesisError("authority receipt is malformed") from exc
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

    def append(self, state: str, *, request_id: str | None = None, facts: Mapping[str, Any] | None = None) -> dict[str, Any]:
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
                self.key, JOURNAL_HMAC_DOMAIN + canonical_json_bytes(without_hmac), hashlib.sha256
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
    for index, line in enumerate(_regular_bytes(path, "worker-synthesis journal").splitlines(), start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FiveSupportWorkerSynthesisError("worker-synthesis journal is malformed") from exc
        _require(isinstance(event, dict), "worker-synthesis journal event is malformed")
        observed_hmac = event.pop("event_hmac_sha256", None)
        observed_sha = event.get("event_sha256")
        body = {name: value for name, value in event.items() if name != "event_sha256"}
        _require(
            event.get("event_index") == index
            and event.get("design_id") == DESIGN_ID
            and event.get("previous_event_sha256") == previous
            and observed_sha == json_sha256(body),
            "worker-synthesis journal hash chain changed",
        )
        expected_hmac = hmac.new(
            key, JOURNAL_HMAC_DOMAIN + canonical_json_bytes(event), hashlib.sha256
        ).hexdigest().upper()
        _require(hmac.compare_digest(str(observed_hmac), expected_hmac), "worker-synthesis journal authentication changed")
        event["event_hmac_sha256"] = observed_hmac
        events.append(event)
        previous = str(observed_sha)
    return events


def assert_can_start(started: Sequence[str], request_id: str) -> None:
    _require(request_id in REQUEST_IDS, "generation request identity changed")
    _require(len(started) < 3, "three-generation ceiling reached")
    _require(request_id not in started, "duplicate generation rejected")
    _require(request_id == EXECUTION_ORDER[len(started)], "generation order changed")


def _rendered_tokens(events: Sequence[Mapping[str, Any]], request_id: str) -> int:
    matches = [event for event in events if event.get("state") == "request-started" and event.get("request_id") == request_id]
    _require(len(matches) == 1, "request-start journal multiplicity changed")
    value = matches[0].get("facts", {}).get("rendered_prompt_tokens")
    _require(isinstance(value, int) and value > 0, "rendered token evidence changed")
    return value


def _structured_from_capture(capture: Mapping[str, Any], rendered_tokens: int) -> str:
    transport = kernel._normalized_transport(
        scientific.replay_capture(capture), rendered_tokens=rendered_tokens, max_tokens=64
    )
    structured = transport.get("structured_content")
    _require(isinstance(structured, str), "captured structured content changed")
    return structured


def _score_frozen_selection(private: balanced.PrivateBinding, alias: str) -> dict[str, Any]:
    task = balanced.build_frozen_task_suite().tasks[EXPECTED_TASK_INDEX]
    internal = private.alias_to_internal[alias]
    candidate = next(item for item in task.candidates if item.candidate_id == internal)
    public_score = sum(balanced.execute_program(candidate, example.x) == example.y for example in task.public_examples)
    hidden_score = sum(balanced.execute_program(candidate, example.x) == example.y for example in task.hidden_examples)
    return {"public_score": public_score, "public_total": 5, "hidden_score": hidden_score, "hidden_total": 16}


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
    return {"bundle_sha256": bundle_sha, "file_count": len(entries), "relative_path": destination.relative_to(repository).as_posix(), "verified": True}


def run_probe(args: Any, *, repository_root: str | os.PathLike[str], adapter: Any | None = None) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=False)
    source_authority.assert_test_repository_isolated(repository)
    _require(str(getattr(args, "design_id", "")) == DESIGN_ID, "live command design identity changed")
    raw_authority_id = getattr(args, "external_authority_id", None)
    authorized_commit = getattr(args, "authorized_commit", None)
    _require(isinstance(raw_authority_id, str) and isinstance(authorized_commit, str), "live probe requires external authority")
    model_path = Path(str(getattr(args, "model"))).resolve()
    prereg = validate_preregistration(repository, model_path)
    admission = public_profile_admission()
    root, private = _load_private(repository)
    paths = state_paths(repository)
    _require(not paths["receipt"].exists() and not paths["run_root"].exists(), "worker-synthesis live state already exists")
    for name, path in paths.items():
        if name != "run_root":
            transaction._require_ignored(repository, path)
    live = adapter or kernel.CatalyticKernel0Adapter(repository)
    full_preflight = live.preflight(args=args, repository_root=repository, run_root=paths["run_root"], allowed_paths=_runtime_allowed_paths(paths))
    public_preflight = runtime_support._public_preflight(full_preflight)
    current_commit = str(public_preflight.get("stable", {}).get("head", ""))
    authority = build_external_authority(
        repository,
        model_path,
        raw_authority_id=raw_authority_id,
        authorized_commit=authorized_commit,
        current_commit=current_commit,
        observed_model_sha256=str(public_preflight.get("model_identity", {}).get("sha256", "")),
        observed_binary_sha256=str(public_preflight.get("binary_identity", {}).get("sha256", "")),
    )
    manifest = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "authority": authority,
        "preregistration_artifact_sha256": prereg["artifact_sha256"],
        "request_sha256": prereg["request_set"]["request_sha256"],
        "execution_order": list(EXECUTION_ORDER),
        "preflight": public_preflight,
        "claiming": False,
    }
    paths["run_root"].mkdir(parents=True)
    manifest_data = canonical_json_bytes(manifest) + b"\n"
    _exclusive_write(paths["manifest"], manifest_data)
    consume_authority_once(repository, root, authority)
    verify_authority_receipt(repository, root)
    journal = JournalWriter(paths["journal"], _experiment_key(root))
    journal.append("authority-consumed", facts={"authority_receipt_sha256": sha256_bytes(_regular_bytes(paths["receipt"], "authority receipt"))})
    started: list[str] = []
    captures: dict[str, dict[str, Any]] = {}
    artifacts: dict[str, dict[str, Any]] = {}
    worker_authored_orders: dict[str, list[str]] = {}
    failure: dict[str, Any] | None = None
    classification = "INCONCLUSIVE"
    cleanup: dict[str, Any] = {"passed": False}
    postflight: dict[str, Any] = {"passed": False}
    sidecar: Any | None = None
    with transaction.run_lock(paths["run_lock"]):
        pool = live.create_lease_pool(1)
        try:
            sidecar, _readiness = live.launch_sidecar(preflight=full_preflight, run_id=DESIGN_ID)
            for request_id in EXECUTION_ORDER:
                if request_id == "synthesis-AB" and set(artifacts) != set(WORKER_IDS):
                    break
                assert_can_start(started, request_id)
                payload = (
                    build_worker_request(private, request_id)
                    if request_id in WORKER_IDS
                    else build_synthesis_request(artifacts)
                )
                started.append(request_id)
                capture = scientific.execute_and_capture_request(
                    experiment_key=_experiment_key(root),
                    frozen_binding_sha256=authority["frozen_scientific_binding_sha256"],
                    payload=payload,
                    request_id=request_id,
                    expected_request_sha256=authority["request_sha256"][request_id],
                    generation_ordinal=len(started),
                    live=live,
                    sidecar=sidecar,
                    pool=pool,
                    full_preflight=full_preflight,
                    capture_path=paths[f"capture-{request_id}"],
                    partial_path=paths[f"partial-{request_id}"],
                    append_event=journal.append,
                )
                captures[request_id] = capture
                if request_id in WORKER_IDS:
                    structured = _structured_from_capture(capture, _rendered_tokens(journal.events, request_id))
                    authored, normalized = validate_worker_relation(root, private, admission, request_id, structured)
                    worker_authored_orders[request_id] = authored
                    artifacts[request_id] = build_worker_artifact(
                        root,
                        request_id,
                        authored,
                        normalized,
                        _source_capture_commitment(
                            root, request_id, authority["request_sha256"][request_id]
                        ),
                    )
                    journal.append(
                        "worker-relation-validated",
                        request_id=request_id,
                        facts={
                            "support_cardinality": 5,
                            "artifact_commitment": artifacts[request_id]["artifact_commitment"],
                            "authenticated_capture_sha256": capture["capture_sha256"],
                            "source_capture_commitment_sha256": artifacts[request_id]["source_worker_capture_commitment_sha256"],
                        },
                    )
        except FiveSupportWorkerSynthesisError as exc:
            failure = {"failure_sha256": sha256_bytes(str(exc).encode("utf-8")), "retry_allowed": False}
            classification = (
                "FIVE_SUPPORT_WORKER_RELATION_GENERATION_NOT_SUPPORTED"
                if len(started) <= 2
                else "FIVE_SUPPORT_TWO_WORKER_RELATIONAL_SYNTHESIS_NOT_SUPPORTED"
            )
            journal.append("scientific-stop", request_id=started[-1] if started else None, facts={**failure, "classification": classification})
        except BaseException as exc:
            failure = {"failure_sha256": sha256_bytes(str(exc).encode("utf-8")), "retry_allowed": False}
            classification = "INCONCLUSIVE"
            journal.append("lifecycle-failed", request_id=started[-1] if started else None, facts=failure)
        finally:
            try:
                cleanup = dict(live.cleanup(sidecar=sidecar, preflight=full_preflight))
            except BaseException as exc:
                cleanup = {"passed": False, "failure_sha256": sha256_bytes(str(exc).encode("utf-8"))}
            try:
                postflight = dict(live.postflight(preflight=full_preflight))
            except BaseException as exc:
                postflight = {"passed": False, "failure_sha256": sha256_bytes(str(exc).encode("utf-8"))}
    synthesis_outcome: dict[str, Any] | None = None
    if failure is None and set(captures) == set(REQUEST_IDS):
        try:
            structured = _structured_from_capture(captures["synthesis-AB"], _rendered_tokens(journal.events, "synthesis-AB"))
            transform, frozen = parse_synthesis(root, structured)
            objective = set(_objective_support_aliases(private, admission, "worker-A")) & set(_objective_support_aliases(private, admission, "worker-B"))
            selected_matches = frozen.candidate_alias in objective
            utility = _score_frozen_selection(private, frozen.candidate_alias)
            if selected_matches and utility == {"public_score": 5, "public_total": 5, "hidden_score": 16, "hidden_total": 16}:
                classification = "FIVE_SUPPORT_TWO_WORKER_RELATIONAL_SYNTHESIS_SUPPORTED_ON_ONE_FROZEN_TASK"
            elif selected_matches:
                classification = "SYNTHESIS_SELECTED_PUBLIC_INTERSECTION_BUT_HIDDEN_UTILITY_NOT_SUPPORTED"
            else:
                classification = "FIVE_SUPPORT_TWO_WORKER_RELATIONAL_SYNTHESIS_NOT_SUPPORTED"
            synthesis_outcome = {
                "transform_operator": transform["operator"],
                "transform_artifact_commitment": transform["artifact_commitment"],
                "transform_ranking_length": 3,
                "selected_rank": 0,
                "rank_zero_frozen_before_private_mapping": True,
                "private_mapping_consulted_before_selection": False,
                "selected_unique_intersection": selected_matches,
                **utility,
            }
        except FiveSupportWorkerSynthesisError as exc:
            failure = {"failure_sha256": sha256_bytes(str(exc).encode("utf-8")), "retry_allowed": False}
            classification = "FIVE_SUPPORT_TWO_WORKER_RELATIONAL_SYNTHESIS_NOT_SUPPORTED"
    if cleanup.get("passed") is not True or postflight.get("passed") is not True:
        classification = "INCONCLUSIVE"
    status = "complete" if classification != "INCONCLUSIVE" and cleanup.get("passed") is True and postflight.get("passed") is True else "inconclusive"
    result = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "status": status,
        "terminal_classification": classification,
        "completed_model_generations": len(started),
        "maximum_model_generations": 3,
        "request_dispositions": [
            {"request_id": request_id, "disposition": "captured" if request_id in captures else "started-no-capture" if request_id in started else "not-started"}
            for request_id in REQUEST_IDS
        ],
        "worker_relations": {worker_id: {"validated_exact_support": worker_id in artifacts, "support_cardinality": 5 if worker_id in artifacts else None, "model_authored_order_preserved_in_capture": worker_id in worker_authored_orders} for worker_id in WORKER_IDS},
        "synthesis": synthesis_outcome,
        "failure": failure,
        "cleanup": cleanup,
        "postflight": postflight,
        "claims": dict(LOCKED_CLAIMS),
        "claiming": False,
        "automatic_follow_on": False,
    }
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
    journal.append("terminal-written", facts={"result_sha256": sha256_bytes(result_data), "closure_sha256": sha256_bytes(closure_data), "status": status})
    verify_journal(paths["journal"], _experiment_key(root))
    archive = _archive_terminal(repository, paths)
    return {**result, "evidence_archive_sha256": archive["bundle_sha256"]}


def validate_static(repository: Path, model_path: Path) -> dict[str, Any]:
    prereg = validate_preregistration(repository, model_path)
    paths = state_paths(repository)
    _require(not paths["receipt"].exists() and not paths["run_root"].exists(), "live worker-synthesis state already exists")
    return {
        "status": "pass",
        "design_id": DESIGN_ID,
        "preregistration_artifact_sha256": prereg["artifact_sha256"],
        "frozen_scientific_binding_sha256": prereg["bindings"]["frozen_scientific"]["sha256"],
        "controller_binding_sha256": prereg["bindings"]["controller"]["sha256"],
        "request_count": 3,
        "future_model_generations": 3,
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
    print(canonical_json_text(run_probe(args, repository_root=repository)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
