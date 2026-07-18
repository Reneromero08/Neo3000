#!/usr/bin/env python3
"""Within-binding presentation-position x seed crossover for CK0 rank-head v2.

Static preparation creates one ignored, first-match private binding and a
tracked zero-execution preregistration.  The live path remains closed unless a
later external one-shot authority binds the published static commit, exact
preregistration, scientific surface, and all twelve request hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

import catalytic_inference_bench_0_runtime as runtime_support
import catalytic_kernel_0 as kernel
import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_parent_dependence_cross_binding_asymmetry_audit as asymmetry
import catalytic_kernel_0_balanced_rank_head_v2 as v2
import catalytic_kernel_0_balanced_rank_head_v2_authority as source_authority
import catalytic_kernel_0_balanced_rank_head_v2_parent_dependence as parent_transaction
import catalytic_kernel_0_balanced_rank_head_v2_parent_dependence_forensic_recovery as recovery
import catalytic_kernel_0_balanced_rank_head_v2_position_seed_crossover_scientific as scientific


class PositionSeedCrossoverError(ValueError):
    """The panel design, private custody, or execution contract changed."""


DESIGN_ID = scientific.DESIGN_ID
STARTING_PROTECTED_MAIN = "c4ca8760c2ce307dbd3fb445bf6f2a624667000b"
PREREGISTRATION_PATH = Path(
    "lab/ck0_balanced_opaque_rank_head_v2_position_seed_crossover_1.json"
)
SELECTION_SEED_PATH = Path(
    "state/catalytic_kernel_0_private/.balanced-opaque-position-seed-crossover-v1.selection.secret"
)
PRIVATE_ROOT_PATH = Path(
    "state/catalytic_kernel_0_private/.balanced-opaque-position-seed-crossover-v1.secret"
)
PRIVATE_RECEIPT_PATH = Path(
    "state/catalytic_kernel_0_private/.balanced-opaque-position-seed-crossover-v1.creation.json"
)
STATE_ROOT = Path("state/catalytic_kernel_0/position_seed_crossover_v1")
ARCHIVE_ROOT = Path(
    "state/catalytic_kernel_0/position_seed_crossover_evidence_archive/v1"
)
AUTHORITY_RECEIPT_PATH = Path(
    "state/catalytic_kernel_0_authority.position-seed-crossover-v1.authority.consumed.json"
)

PRESENTATIONS = scientific.PRESENTATIONS
SEED_BLOCKS = {"S0": 1851550238, "S1": 1669860413}
ARMS = scientific.ARMS
REQUEST_IDS = scientific.REQUEST_IDS
CELLS = tuple(
    f"{presentation}-{seed_block}"
    for presentation in PRESENTATIONS
    for seed_block in SEED_BLOCKS
)
EXECUTION_ORDER = (
    "P0-S0-full-information",
    "P1-S1-full-information",
    "P0-S0-delete-parent-0",
    "P1-S1-delete-parent-1",
    "P1-S0-full-information",
    "P0-S1-full-information",
    "P1-S0-delete-parent-1",
    "P0-S1-delete-parent-0",
    "P0-S0-delete-parent-1",
    "P1-S1-delete-parent-0",
    "P1-S0-delete-parent-0",
    "P0-S1-delete-parent-1",
)

PANEL_PROFILE_ID = DESIGN_ID
PANEL_CONFIGURATION = balanced.PrivateBindingConfiguration(
    profile_id=PANEL_PROFILE_ID,
    preregistration_path=PREREGISTRATION_PATH.as_posix(),
    secret_path=PRIVATE_ROOT_PATH.as_posix(),
    creation_receipt_path=PRIVATE_RECEIPT_PATH.as_posix(),
    run_modes={
        f"{presentation}-{seed_block}-{arm}": arm
        for presentation in PRESENTATIONS
        for seed_block in SEED_BLOCKS
        for arm in ARMS
    },
    domain_separation_identity="ck0-rank-head-v2-position-seed-crossover-v1",
    protected_starting_sha=STARTING_PROTECTED_MAIN,
)

MODEL_SHA256 = asymmetry.EXPECTED_MODEL_SHA256
BINARY_SHA256 = parent_transaction.BINARY_SHA256
CARRIER_ROOT_SHA256 = parent_transaction.CARRIER_ROOT_SHA256
FORENSIC_ARTIFACT_SHA256 = (
    "110DAE908E4C1F01747C2CBBEA9F3A34BB2ACA61397D55B0648D82453A3DD975"
)
ASYMMETRY_ARTIFACT_SHA256 = (
    "47B6790A05F98051EA10BBA5EA4944C3DCE37A68CF6E64B7BF7A26A464E891B7"
)
ASYMMETRY_ARTIFACT_PATH = asymmetry.ARTIFACT_PATH
SUPPORTED_CLAIM = asymmetry.CORRECTED_SUPPORTED_CLAIM
SUPPORTED_QUALIFICATION = asymmetry.CORRECTED_QUALIFICATION

CENTRAL_ORDINALS = (32, 33)
MAXIMUM_SELECTION_ATTEMPTS = 4096
SELECTION_DERIVATION_DOMAIN = b"ck0-rank-head-v2/position-seed-crossover/selection-candidate-v1\0"
SELECTION_SEED_COMMITMENT_DOMAIN = b"ck0-rank-head-v2/position-seed-crossover/selection-seed-v1\0"
SELECTION_RECEIPT_HMAC_DOMAIN = b"ck0-rank-head-v2/position-seed-crossover/selection-receipt-v1\0"
SEMANTIC_PARENT_DOMAIN = b"ck0-rank-head-v2/position-seed-crossover/semantic-parent-v1\0"
PRESENTATION_PROOF_DOMAIN = b"ck0-rank-head-v2/position-seed-crossover/presentation-proof-v1\0"
EXPERIMENT_KEY_DOMAIN = b"ck0-rank-head-v2/position-seed-crossover/experiment-key-v1\0"
EXPERIMENT_KEY_COMMITMENT_DOMAIN = b"ck0-rank-head-v2/position-seed-crossover/experiment-key-commitment-v1\0"
AUTHORITY_ID_DOMAIN = b"ck0-rank-head-v2/position-seed-crossover/authority-id-v1\0"
AUTHORITY_HMAC_DOMAIN = b"ck0-rank-head-v2/position-seed-crossover/authority-hmac-v1\0"
JOURNAL_HMAC_DOMAIN = b"ck0-rank-head-v2/position-seed-crossover/journal-hmac-v1\0"

AUTHORITY_SCHEMA_VERSION = "rank-head-v2-position-seed-crossover-authority-v1"
AUTHORITY_RECEIPT_SCHEMA_VERSION = "rank-head-v2-position-seed-crossover-consumption-v1"
AUTHORITY_KIND = "external-one-shot-position-seed-crossover"
JOURNAL_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
MAXIMUM_CONTROLLER_REPAIR_COMMITS = 3
SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
AUTHORITY_ID_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
FORBIDDEN_PUBLIC_ID_RE = re.compile(rb'"(?:K|C)[0-9]{2}"')
GENESIS_HASH = "0" * 64

REPAIRABLE_CONTROLLER_PATHS = (
    "scripts/baseline_harness.py",
    "scripts/catalytic_inference_bench_0_runtime.py",
    "scripts/catalytic_kernel_0.py",
    "scripts/catalytic_kernel_0_balanced_opaque.py",
    "scripts/catalytic_kernel_0_balanced_rank_head_v2.py",
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_integration.py",
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_position_seed_crossover.py",
)
ALLOWED_CONTROLLER_REPAIR_PATHS = frozenset(
    set(REPAIRABLE_CONTROLLER_PATHS)
    | {
        "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_position_seed_crossover.py",
        "TASKS.md",
        "lab/GOAL.md",
        "lab/CHECKPOINT.md",
        "lab/EVALUATOR.json",
        "lab/EVALUATOR.lock.json",
    }
)

LOCKED_CLAIMS = {
    "PURE_BINDING_ONLY_REPLICATION_UNDER_IDENTICAL_END_TO_END_PROCESS": "LOCKED",
    "PARENT_B_CROSS_BINDING_REPLICATION": "LOCKED",
    "BILATERAL_DEPENDENCE": "LOCKED_UNTIL_EXECUTED_AND_ADJUDICATED",
    "GENERAL_TWO_PARENT_NECESSITY": "LOCKED",
    "TRANSFER": "LOCKED",
    "GENERAL_CATALYTIC_INFERENCE": "LOCKED",
    "TASK_ADVANTAGE": "LOCKED",
    "SUPERIORITY": "LOCKED",
    "SOTA": "LOCKED",
    "BROADER_PROCESS_LOCAL_HOLOSTATE": "LOCKED",
    "RESTART_PERSISTENCE": "LOCKED",
    "DEEP": "DISABLED",
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
        raise PositionSeedCrossoverError(message)


def _require_regular(path: Path, label: str, *, exact: int | None = None, maximum: int = 4 * 1024 * 1024) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise PositionSeedCrossoverError(f"{label} is not a regular file")
        mode = path.lstat().st_mode
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        reparse = attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        _require(stat.S_ISREG(mode) and not reparse, f"{label} is unsafe")
        data = path.read_bytes()
    except OSError as exc:
        raise PositionSeedCrossoverError(f"{label} is unreadable") from exc
    if exact is not None:
        _require(len(data) == exact, f"{label} size changed")
    _require(len(data) <= maximum, f"{label} exceeds its byte ceiling")
    return data


def _json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(_require_regular(path, label))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PositionSeedCrossoverError(f"{label} is malformed") from exc
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


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    data = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        indent=2,
    ).encode("utf-8") + b"\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        _exclusive_write(temporary, data)
        os.replace(temporary, path)
    finally:
        if temporary.is_file() and not temporary.is_symlink():
            temporary.unlink()


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _assert_public_no_smuggle(value: Any) -> None:
    data = canonical_json_bytes(value)
    _require(not FORBIDDEN_PUBLIC_ID_RE.search(data), "private symbol or internal identity entered public metadata")
    lowered = data.lower()
    for forbidden in (
        b'"alias_mapping"',
        b'"private_root"',
        b'"selection_seed"',
        b'"support_aliases"',
        b'"ranking"',
        b'"raw_response"',
    ):
        _require(forbidden not in lowered, "private or model-authored data entered public metadata")


def _candidate_root(selection_seed: bytes, counter: int) -> bytes:
    _require(len(selection_seed) == 32, "private selection seed length changed")
    _require(0 <= counter < MAXIMUM_SELECTION_ATTEMPTS, "selection counter exceeds the frozen ceiling")
    return hmac.new(
        selection_seed,
        SELECTION_DERIVATION_DOMAIN + counter.to_bytes(8, "big"),
        hashlib.sha256,
    ).digest()


def _panel_binding(root: bytes) -> balanced.PrivateBinding:
    return balanced.PrivateBinding.from_secret(root, PANEL_CONFIGURATION)


def _semantic_parent_body(
    private: balanced.PrivateBinding,
    role: str,
) -> dict[str, Any]:
    branch = "branch-a" if role == "parent-0" else "branch-b"
    support = sorted(private.internal_to_alias[item] for item in balanced.EXPECTED_SUPPORTS[branch])
    _require(len(support) == 5 and len(set(support)) == 5, "semantic parent support changed")
    return {
        "artifact_role": role,
        "canonical_sorted_five_member_support": support,
        "tied_top_score": balanced.EXPECTED_TOP_SCORE,
        "pass_equivalence_class": list(balanced.EXPECTED_PASS_VECTOR),
        "panel_identity": DESIGN_ID,
    }


def _semantic_parent(
    root: bytes,
    private: balanced.PrivateBinding,
    role: str,
) -> dict[str, Any]:
    body = _semantic_parent_body(private, role)
    commitment = hmac.new(
        root,
        SEMANTIC_PARENT_DOMAIN + canonical_json_bytes(body),
        hashlib.sha256,
    ).hexdigest().upper()
    return {**body, "semantic_set_commitment": commitment}


def _presentation_projection(
    root: bytes,
    private: balanced.PrivateBinding,
    role: str,
    presentation: str,
) -> dict[str, Any]:
    _require(presentation in PRESENTATIONS, "presentation identity changed")
    semantic = _semantic_parent(root, private, role)
    singleton = private.internal_to_alias[balanced.EXPECTED_FULL_SUPPORT[0]]
    others = sorted(
        alias
        for alias in semantic["canonical_sorted_five_member_support"]
        if alias != singleton
    )
    support = [singleton, *others] if presentation == "P0" else [*others, singleton]
    projection = {
        "artifact_role": role,
        "support_aliases": support,
        "tied_top_score": semantic["tied_top_score"],
        "pass_equivalence_class": semantic["pass_equivalence_class"],
        "semantic_set_commitment": semantic["semantic_set_commitment"],
    }
    _require(
        set(projection) == {
            "artifact_role",
            "support_aliases",
            "tied_top_score",
            "pass_equivalence_class",
            "semantic_set_commitment",
        }
        and len(support) == 5
        and set(support) == set(semantic["canonical_sorted_five_member_support"]),
        "model-visible presentation projection changed semantic support",
    )
    balanced._assert_no_internal_identity(projection)
    balanced.validate_metadata_only(projection)
    return projection


def _deletion_receipt(root: bytes, private: balanced.PrivateBinding, role: str) -> dict[str, Any]:
    semantic = _semantic_parent(root, private, role)
    return {
        "artifact_role": role,
        "semantic_set_commitment": semantic["semantic_set_commitment"],
        "projection_mode": "commitment-only",
        "informative_content_withheld": True,
    }


def _request_parts(request_id: str) -> tuple[str, str, str]:
    _require(request_id in REQUEST_IDS, "request identity changed")
    presentation, seed_block, arm = request_id.split("-", 2)
    return presentation, seed_block, arm


def build_assignment(
    root: bytes,
    private: balanced.PrivateBinding,
    request_id: str,
) -> dict[str, Any]:
    presentation, _seed_block, arm = _request_parts(request_id)
    parents = [
        _presentation_projection(root, private, "parent-0", presentation),
        _presentation_projection(root, private, "parent-1", presentation),
    ]
    if arm == "delete-parent-0":
        parents[0] = _deletion_receipt(root, private, "parent-0")
    elif arm == "delete-parent-1":
        parents[1] = _deletion_receipt(root, private, "parent-1")
    else:
        _require(arm == "full-information", "arm identity changed")
    assignment = {
        "stage": "transform",
        "instruction": (
            "Operate only on the supplied opaque parent relations. Author one "
            "allowed operator and one opaque candidate ranking."
        ),
        "parent_artifacts": parents,
    }
    text = canonical_json_text(assignment).lower()
    for forbidden in (
        "singleton first",
        "singleton last",
        "low position",
        "high position",
        "target",
        "correct",
        "private winner",
    ):
        _require(forbidden not in text, "presentation condition leaked into model-visible labels")
    balanced._assert_no_internal_identity(assignment)
    balanced.validate_metadata_only(assignment)
    return assignment


def build_request(
    root: bytes,
    private: balanced.PrivateBinding,
    request_id: str,
) -> dict[str, Any]:
    _presentation, seed_block, _arm = _request_parts(request_id)
    carrier = v2.build_v2_carrier()
    _require(carrier["carrier_root_sha256"] == CARRIER_ROOT_SHA256, "carrier root changed")
    assignment = build_assignment(root, private, request_id)
    payload = {
        "model": balanced.MODEL_ALIAS,
        "messages": [
            {"role": "system", "content": carrier["carrier_root"]},
            {"role": "user", "content": canonical_json_text(assignment)},
        ],
        "temperature": 0.0,
        "seed": SEED_BLOCKS[seed_block],
        "max_tokens": 64,
        "stream": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "ck0_rank_head_v2_position_seed_crossover_transform",
                "strict": True,
                "schema": v2.v2_response_schema("transform"),
            },
        },
        "stream_options": {"include_usage": True},
        "cache_prompt": True,
        "return_tokens": True,
        "return_progress": True,
        "verbose": True,
    }
    _require(json.loads(payload["messages"][1]["content"]) == assignment, "request assignment changed")
    balanced._assert_no_internal_identity(payload)
    return payload


def _token_sequence(tokenizer: asymmetry.OfflineTokenizer, value: Any) -> dict[str, Any]:
    data = canonical_json_bytes(value)
    ids = tokenizer.ids(data.decode("utf-8"))
    return {
        "serialized_bytes": len(data),
        "token_ids": len(ids),
        "token_sequence_sha256": json_sha256(ids),
    }


def _candidate_eligibility(
    root: bytes,
    tokenizer: asymmetry.OfflineTokenizer,
) -> dict[str, Any]:
    private = _panel_binding(root)
    singleton = private.internal_to_alias[balanced.EXPECTED_FULL_SUPPORT[0]]
    ordinal = sorted(balanced.ALIASES).index(singleton) + 1
    roles: dict[str, Any] = {}
    all_equal = True
    only_order_differs = True
    for role in ("parent-0", "parent-1"):
        p0 = _presentation_projection(root, private, role, "P0")
        p1 = _presentation_projection(root, private, role, "P1")
        p0_sequence = _token_sequence(tokenizer, p0)
        p1_sequence = _token_sequence(tokenizer, p1)
        equal_lengths = (
            p0_sequence["serialized_bytes"] == p1_sequence["serialized_bytes"]
            and p0_sequence["token_ids"] == p1_sequence["token_ids"]
        )
        same_set = set(p0["support_aliases"]) == set(p1["support_aliases"])
        same_fields = set(p0) == set(p1)
        same_nonorder = {
            key: value for key, value in p0.items() if key != "support_aliases"
        } == {
            key: value for key, value in p1.items() if key != "support_aliases"
        }
        all_equal = all_equal and equal_lengths
        only_order_differs = only_order_differs and same_set and same_fields and same_nonorder
        proof_body = {
            "role": role,
            "semantic_set_commitment": p0["semantic_set_commitment"],
            "p0_singleton_ordinal": 1,
            "p1_singleton_ordinal": 5,
            "same_support_set": same_set,
            "same_field_set": same_fields,
            "only_list_order_differs": same_nonorder,
            "serialized_bytes_equal": equal_lengths,
            "tokenizer_lengths_equal": p0_sequence["token_ids"] == p1_sequence["token_ids"],
            "p0_projection": p0_sequence,
            "p1_projection": p1_sequence,
        }
        roles[role] = {
            **proof_body,
            "private_validation_commitment": hmac.new(
                root,
                PRESENTATION_PROOF_DOMAIN + canonical_json_bytes(proof_body),
                hashlib.sha256,
            ).hexdigest().upper(),
        }
    opaque_lengths = {tokenizer.length(alias) for alias in balanced.ALIASES}
    request_length_pairs: dict[str, bool] = {}
    for seed_block in SEED_BLOCKS:
        for arm in ARMS:
            p0_id = f"P0-{seed_block}-{arm}"
            p1_id = f"P1-{seed_block}-{arm}"
            p0 = _token_sequence(tokenizer, build_assignment(root, private, p0_id))
            p1 = _token_sequence(tokenizer, build_assignment(root, private, p1_id))
            request_length_pairs[f"{seed_block}-{arm}"] = (
                p0["serialized_bytes"] == p1["serialized_bytes"]
                and p0["token_ids"] == p1["token_ids"]
            )
    supports_exact = all(
        set(_semantic_parent_body(private, role)["canonical_sorted_five_member_support"])
        == {
            private.internal_to_alias[item]
            for item in balanced.EXPECTED_SUPPORTS[
                "branch-a" if role == "parent-0" else "branch-b"
            ]
        }
        for role in ("parent-0", "parent-1")
    )
    eligible = (
        ordinal in CENTRAL_ORDINALS
        and opaque_lengths == {3}
        and supports_exact
        and all_equal
        and only_order_differs
        and all(request_length_pairs.values())
    )
    return {
        "eligible": eligible,
        "private_singleton_global_lexical_ordinal_1_based": ordinal,
        "required_central_ordinals": list(CENTRAL_ORDINALS),
        "opaque_symbol_token_id_lengths_all_three": opaque_lengths == {3},
        "both_five_member_supports_exact": supports_exact,
        "presentation_roles": roles,
        "all_p0_p1_serialized_byte_lengths_equal": all_equal,
        "all_p0_p1_tokenizer_lengths_equal": all_equal,
        "only_support_list_order_differs": only_order_differs,
        "all_p0_p1_assignment_lengths_equal": all(request_length_pairs.values()),
        "assignment_length_pair_gates": request_length_pairs,
    }


def _selection_seed_commitment(seed: bytes) -> str:
    return sha256_bytes(SELECTION_SEED_COMMITMENT_DOMAIN + seed)


def _selection_receipt_hmac(seed: bytes, body: Mapping[str, Any]) -> str:
    return hmac.new(
        seed,
        SELECTION_RECEIPT_HMAC_DOMAIN + canonical_json_bytes(body),
        hashlib.sha256,
    ).hexdigest().upper()


def _selection_receipt(
    seed: bytes,
    root: bytes,
    counter: int,
    eligibility: Mapping[str, Any],
) -> dict[str, Any]:
    private = _panel_binding(root)
    body = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "selection_law": "first eligible domain-separated counter before any model outcome",
        "candidate_derivation_domain_sha256": sha256_bytes(SELECTION_DERIVATION_DOMAIN),
        "selection_seed_commitment_sha256": _selection_seed_commitment(seed),
        "selected_counter": counter,
        "attempt_count": counter + 1,
        "attempt_ceiling": MAXIMUM_SELECTION_ATTEMPTS,
        "root_commitment_sha256": private.secret_commitment,
        "profile_binding_sha256": private.profile_binding_sha256,
        "alias_map_commitment_sha256": private.alias_map_commitment,
        "branch_alias_map_commitment_sha256": dict(private.branch_alias_map_commitments),
        "eligibility": dict(eligibility),
        "model_outputs_inspected": 0,
        "authority_created": False,
        "private_root_persisted_in_tracked_files": False,
        "private_mapping_persisted_in_tracked_files": False,
        "rejected_candidates_persisted": False,
    }
    return {**body, "selection_receipt_hmac_sha256": _selection_receipt_hmac(seed, body)}


def select_first_eligible(
    selection_seed: bytes,
    tokenizer: asymmetry.OfflineTokenizer,
    *,
    attempt_ceiling: int = MAXIMUM_SELECTION_ATTEMPTS,
) -> tuple[int, bytes, dict[str, Any]]:
    _require(
        1 <= attempt_ceiling <= MAXIMUM_SELECTION_ATTEMPTS,
        "private selection attempt ceiling is invalid",
    )
    for counter in range(attempt_ceiling):
        root = _candidate_root(selection_seed, counter)
        eligibility = _candidate_eligibility(root, tokenizer)
        if eligibility["eligible"]:
            return counter, root, eligibility
    raise PositionSeedCrossoverError(
        "no eligible private binding found before attempt ceiling; stop before authority"
    )


def prepare_private_binding(repository: Path, model_path: Path) -> dict[str, Any]:
    repository = repository.resolve(strict=False)
    tokenizer = asymmetry.OfflineTokenizer(model_path.resolve())
    paths = [repository / SELECTION_SEED_PATH, repository / PRIVATE_ROOT_PATH, repository / PRIVATE_RECEIPT_PATH]
    for path in paths:
        parent_transaction._require_ignored(repository, path)
    existence = [path.exists() or path.is_symlink() for path in paths]
    if any(existence):
        _require(all(existence), "partial private selection state exists")
        return validate_private_binding(repository, model_path)
    seed = secrets.token_bytes(32)
    counter, root, eligibility = select_first_eligible(seed, tokenizer)
    receipt = _selection_receipt(seed, root, counter, eligibility)
    _exclusive_write(repository / SELECTION_SEED_PATH, seed)
    _exclusive_write(repository / PRIVATE_ROOT_PATH, root)
    _exclusive_write(
        repository / PRIVATE_RECEIPT_PATH,
        json.dumps(receipt, sort_keys=True, indent=2).encode("utf-8") + b"\n",
    )
    return validate_private_binding(repository, model_path)


def validate_private_binding(repository: Path, model_path: Path) -> dict[str, Any]:
    repository = repository.resolve(strict=False)
    tokenizer = asymmetry.OfflineTokenizer(model_path.resolve())
    seed_path = repository / SELECTION_SEED_PATH
    root_path = repository / PRIVATE_ROOT_PATH
    receipt_path = repository / PRIVATE_RECEIPT_PATH
    for path in (seed_path, root_path, receipt_path):
        parent_transaction._require_ignored(repository, path)
    seed = _require_regular(seed_path, "private selection seed", exact=32)
    root = _require_regular(root_path, "selected private binding root", exact=32)
    receipt = _json_object(receipt_path, "private selection receipt")
    hmac_value = str(receipt.get("selection_receipt_hmac_sha256", ""))
    body = {key: value for key, value in receipt.items() if key != "selection_receipt_hmac_sha256"}
    _require(hmac.compare_digest(hmac_value, _selection_receipt_hmac(seed, body)), "private selection receipt authentication changed")
    counter = receipt.get("selected_counter")
    _require(isinstance(counter, int) and 0 <= counter < MAXIMUM_SELECTION_ATTEMPTS, "selected counter changed")
    _require(_candidate_root(seed, counter) == root, "selected root is not counter-derived")
    for prior in range(counter):
        _require(
            not _candidate_eligibility(_candidate_root(seed, prior), tokenizer)["eligible"],
            "selected binding is not the deterministic first eligible candidate",
        )
    eligibility = _candidate_eligibility(root, tokenizer)
    expected = _selection_receipt(seed, root, counter, eligibility)
    _require(receipt == expected and eligibility["eligible"], "private selection receipt differs from exact reconstruction")
    private = _panel_binding(root)
    return {
        "status": "pass",
        "selected_counter": counter,
        "attempt_count": counter + 1,
        "attempt_ceiling": MAXIMUM_SELECTION_ATTEMPTS,
        "selection_seed_commitment_sha256": receipt["selection_seed_commitment_sha256"],
        "root_commitment_sha256": private.secret_commitment,
        "profile_binding_sha256": private.profile_binding_sha256,
        "alias_map_commitment_sha256": private.alias_map_commitment,
        "branch_alias_map_commitment_sha256": dict(private.branch_alias_map_commitments),
        "eligibility": eligibility,
        "first_match_verified": True,
        "model_outputs_inspected": 0,
        "authority_created": False,
    }


def _load_private(repository: Path) -> tuple[bytes, balanced.PrivateBinding]:
    root = _require_regular(repository / PRIVATE_ROOT_PATH, "selected private binding root", exact=32)
    return root, _panel_binding(root)


def _experiment_key(root: bytes) -> bytes:
    return hmac.new(root, EXPERIMENT_KEY_DOMAIN + DESIGN_ID.encode("ascii"), hashlib.sha256).digest()


def _experiment_key_commitment(root: bytes) -> str:
    return sha256_bytes(EXPERIMENT_KEY_COMMITMENT_DOMAIN + _experiment_key(root))


def _file_binding(repository: Path, paths: Sequence[str]) -> dict[str, Any]:
    files = []
    for relative in paths:
        data = _require_regular(repository / relative, relative)
        files.append({"path": relative, "byte_size": len(data), "sha256": sha256_bytes(data)})
    body = {"files": files}
    return {**body, "sha256": json_sha256(body)}


def verify_source_custody(repository: Path) -> dict[str, Any]:
    forensic = repository / recovery.ARTIFACT_PATH
    audit = repository / ASYMMETRY_ARTIFACT_PATH
    _require(sha256_bytes(_require_regular(forensic, "forensic recovery artifact")) == FORENSIC_ARTIFACT_SHA256, "forensic recovery artifact changed")
    _require(sha256_bytes(_require_regular(audit, "asymmetry audit artifact")) == ASYMMETRY_ARTIFACT_SHA256, "asymmetry audit artifact changed")
    recovered = recovery.validate_forensic_recovery(repository)
    _require(recovered["artifact_sha256"] == FORENSIC_ARTIFACT_SHA256, "forensic recovery no longer reconstructs")
    return {
        "original_terminal_status": "INCONCLUSIVE",
        "original_terminal_reason": "durable-finalization-custody-gate-failed",
        "original_archive_sha256": recovery.ORIGINAL_ARCHIVE_SHA256,
        "forensic_artifact_sha256": FORENSIC_ARTIFACT_SHA256,
        "asymmetry_audit_sha256": ASYMMETRY_ARTIFACT_SHA256,
        "supported_claim": SUPPORTED_CLAIM,
        "qualification": SUPPORTED_QUALIFICATION,
        "execution_evidence_rewritten": False,
    }


def request_isolation_report(
    root: bytes,
    private: balanced.PrivateBinding,
    tokenizer: asymmetry.OfflineTokenizer,
) -> dict[str, Any]:
    payloads = {request_id: build_request(root, private, request_id) for request_id in REQUEST_IDS}
    request_hashes = {request_id: json_sha256(payloads[request_id]) for request_id in REQUEST_IDS}
    assignments = {
        request_id: json.loads(payloads[request_id]["messages"][1]["content"])
        for request_id in REQUEST_IDS
    }
    projection_identity: dict[str, dict[str, str]] = {role: {} for role in ("parent-0", "parent-1")}
    projection_proofs: dict[str, Any] = {}
    for role in projection_identity:
        for presentation in PRESENTATIONS:
            projection = _presentation_projection(root, private, role, presentation)
            projection_identity[role][presentation] = json_sha256(projection)
        eligibility = _candidate_eligibility(root, tokenizer)["presentation_roles"][role]
        projection_proofs[role] = eligibility
    deletion_receipts = {
        role: {
            "sha256": json_sha256(_deletion_receipt(root, private, role)),
            **_token_sequence(tokenizer, _deletion_receipt(root, private, role)),
        }
        for role in ("parent-0", "parent-1")
    }
    per_request = {}
    for request_id in REQUEST_IDS:
        presentation, seed_block, arm = _request_parts(request_id)
        assignment_tokens = _token_sequence(tokenizer, assignments[request_id])
        per_request[request_id] = {
            "cell_id": f"{presentation}-{seed_block}",
            "presentation": presentation,
            "seed_block": seed_block,
            "seed": SEED_BLOCKS[seed_block],
            "arm": arm,
            "request_sha256": request_hashes[request_id],
            "model_visible_assignment_serialized_bytes": assignment_tokens["serialized_bytes"],
            "model_visible_assignment_token_ids": assignment_tokens["token_ids"],
        }
    return {
        "physical_slots": 1,
        "sidecar_epochs": 1,
        "sidecar_epoch_justification": (
            "Each request is self-contained and independently seeded; no response enters a later "
            "prompt; cache reuse is restricted to the immutable common carrier prefix."
        ),
        "request_ids": list(REQUEST_IDS),
        "request_sha256": request_hashes,
        "execution_order": list(EXECUTION_ORDER),
        "unique_request_count": len(set(request_hashes.values())),
        "requests_transform_only": True,
        "borrow_requests": 0,
        "branch_requests": 0,
        "extraction_requests": 0,
        "restore_requests": 0,
        "cross_response_state_visible": False,
        "request_self_contained": True,
        "cache_reuse_scope": "immutable-common-carrier-prefix-only",
        "response_captured_before_parsing": True,
        "projection_sha256_private_validation": projection_identity,
        "presentation_proofs": projection_proofs,
        "deletion_receipts": deletion_receipts,
        "per_request": per_request,
    }


def authority_object_schema() -> dict[str, Any]:
    sha = {"type": "string", "pattern": "^[0-9A-F]{64}$"}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "authority_kind",
            "design_id",
            "authorized_commit",
            "authority_id_sha256",
            "preregistration_artifact_sha256",
            "frozen_scientific_binding_sha256",
            "repairable_controller_initial_binding_sha256",
            "request_sha256",
            "model_sha256",
            "binary_sha256",
            "journal_schema_sha256",
            "capture_schema_sha256",
            "maximum_generations_per_cell_arm",
            "maximum_total_generations",
            "physical_slots",
            "sidecar_epochs",
            "maximum_controller_repair_commits",
            "automatic_follow_on",
        ],
        "properties": {
            "schema_version": {"const": AUTHORITY_SCHEMA_VERSION},
            "authority_kind": {"const": AUTHORITY_KIND},
            "design_id": {"const": DESIGN_ID},
            "authorized_commit": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            "authority_id_sha256": sha,
            "preregistration_artifact_sha256": sha,
            "frozen_scientific_binding_sha256": sha,
            "repairable_controller_initial_binding_sha256": sha,
            "request_sha256": {
                "type": "object",
                "minProperties": 12,
                "maxProperties": 12,
                "additionalProperties": sha,
            },
            "model_sha256": {"const": MODEL_SHA256},
            "binary_sha256": {"const": BINARY_SHA256},
            "journal_schema_sha256": sha,
            "capture_schema_sha256": sha,
            "maximum_generations_per_cell_arm": {"const": 1},
            "maximum_total_generations": {"const": 12},
            "physical_slots": {"const": 1},
            "sidecar_epochs": {"const": 1},
            "maximum_controller_repair_commits": {"const": MAXIMUM_CONTROLLER_REPAIR_COMMITS},
            "automatic_follow_on": {"const": False},
        },
    }


def authority_receipt_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "design_id",
            "consumed",
            "authority",
            "consumed_at",
            "consuming_commit",
            "authority_hmac_sha256",
        ],
        "properties": {
            "schema_version": {"const": AUTHORITY_RECEIPT_SCHEMA_VERSION},
            "design_id": {"const": DESIGN_ID},
            "consumed": {"const": True},
            "authority": authority_object_schema(),
            "consumed_at": {"type": "string"},
            "consuming_commit": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            "authority_hmac_sha256": {"type": "string", "pattern": "^[0-9A-F]{64}$"},
        },
    }


def journal_event_schema() -> dict[str, Any]:
    return {
        "schema_version": JOURNAL_SCHEMA_VERSION,
        "required_fields": [
            "schema_version",
            "design_id",
            "sequence",
            "state",
            "request_id",
            "facts",
            "previous_event_sha256",
            "event_sha256",
            "event_hmac_sha256",
        ],
        "states": [
            "authority-consumed",
            "controller-repair-observed",
            "request-started",
            "response-captured",
            "request-custody-observed",
            "request-inconclusive",
            "adjudicated",
            "finalization-observed",
            "terminal-written",
            "archived",
        ],
        "append_only": True,
        "authenticated": True,
        "duplicate_generation_rejected": True,
    }


AUTHORITY_OBJECT_SCHEMA_SHA256 = json_sha256(authority_object_schema())
AUTHORITY_RECEIPT_SCHEMA_SHA256 = json_sha256(authority_receipt_schema())
JOURNAL_SCHEMA_SHA256 = json_sha256(journal_event_schema())
CAPTURE_SCHEMA_SHA256 = json_sha256(scientific.capture_schema())


def _scientific_contract(
    root: bytes,
    private: balanced.PrivateBinding,
    isolation: Mapping[str, Any],
) -> dict[str, Any]:
    semantic_commitments = {
        role: _semantic_parent(root, private, role)["semantic_set_commitment"]
        for role in ("parent-0", "parent-1")
    }
    presentation_commitments = {
        role: {
            presentation: isolation["presentation_proofs"][role][
                "private_validation_commitment"
            ]
            for presentation in PRESENTATIONS
        }
        for role in ("parent-0", "parent-1")
    }
    return {
        "design_id": DESIGN_ID,
        "request_ids": list(REQUEST_IDS),
        "execution_order": list(EXECUTION_ORDER),
        "request_sha256": dict(isolation["request_sha256"]),
        "binding_commitments": {
            "root_commitment_sha256": private.secret_commitment,
            "profile_binding_sha256": private.profile_binding_sha256,
            "alias_map_commitment_sha256": private.alias_map_commitment,
            "experiment_key_commitment_sha256": _experiment_key_commitment(root),
        },
        "semantic_parent_commitments": semantic_commitments,
        "presentation_proof_commitments": presentation_commitments,
        "seeds": dict(SEED_BLOCKS),
        "model_sha256": MODEL_SHA256,
        "binary_sha256": BINARY_SHA256,
        "carrier_root_sha256": CARRIER_ROOT_SHA256,
        "response_schema_sha256": json_sha256(v2.v2_response_schema("transform")),
        "physical_slots": 1,
        "sidecar_epochs": 1,
        "maximum_model_generations_per_request": 1,
        "maximum_total_model_generations": 12,
        "request_dispatch": "frozen-scientific-module-exact-hash-gate-before-contact",
        "raw_response_recording": "exclusive-fsynced-capture-before-controller-parse",
    }


def _repairable_controller_binding(repository: Path) -> dict[str, Any]:
    return _file_binding(repository, REPAIRABLE_CONTROLLER_PATHS)


def _implementation_binding(
    repository: Path,
    root: bytes,
    private: balanced.PrivateBinding,
    isolation: Mapping[str, Any],
) -> dict[str, Any]:
    payloads = {
        request_id: build_request(root, private, request_id)
        for request_id in REQUEST_IDS
    }
    frozen = scientific.frozen_scientific_binding(
        repository,
        contract=_scientific_contract(root, private, isolation),
        payloads=payloads,
    )
    controller = _repairable_controller_binding(repository)
    body = {
        "frozen_scientific_execution": frozen,
        "repairable_controller": controller,
    }
    return {**body, "sha256": json_sha256(body)}


def _public_selection(selection: Mapping[str, Any]) -> dict[str, Any]:
    eligibility = selection["eligibility"]
    return {
        "law": "first eligible domain-separated counter before outcomes",
        "selection_seed_commitment_sha256": selection[
            "selection_seed_commitment_sha256"
        ],
        "selected_counter": selection["selected_counter"],
        "attempt_count": selection["attempt_count"],
        "attempt_ceiling": selection["attempt_ceiling"],
        "central_lexical_ordinal_interval": list(CENTRAL_ORDINALS),
        "selected_singleton_global_lexical_ordinal_1_based": eligibility[
            "private_singleton_global_lexical_ordinal_1_based"
        ],
        "opaque_symbol_token_id_lengths_all_three": eligibility[
            "opaque_symbol_token_id_lengths_all_three"
        ],
        "both_five_member_supports_exact": eligibility[
            "both_five_member_supports_exact"
        ],
        "first_match_verified": selection["first_match_verified"],
        "model_outputs_inspected": 0,
        "rejected_candidates_published": False,
        "failure_law": "stop-before-authority-if-no-candidate-qualifies",
    }


def build_preregistration_document(
    repository: Path,
    model_path: Path,
) -> dict[str, Any]:
    repository = repository.resolve(strict=False)
    source = verify_source_custody(repository)
    selection = validate_private_binding(repository, model_path)
    tokenizer = asymmetry.OfflineTokenizer(model_path.resolve())
    root, private = _load_private(repository)
    isolation = request_isolation_report(root, private, tokenizer)
    implementation = _implementation_binding(repository, root, private, isolation)
    semantic_parent_commitments = {
        role: _semantic_parent(root, private, role)["semantic_set_commitment"]
        for role in ("parent-0", "parent-1")
    }
    cells = []
    for presentation in PRESENTATIONS:
        for seed_block, seed in SEED_BLOCKS.items():
            request_ids = [
                f"{presentation}-{seed_block}-{arm}" for arm in ARMS
            ]
            cells.append(
                {
                    "cell_id": f"{presentation}-{seed_block}",
                    "presentation": presentation,
                    "seed_block": seed_block,
                    "fixed_transform_seed": seed,
                    "arm_order_independent": True,
                    "request_ids": request_ids,
                    "request_sha256": {
                        request_id: isolation["request_sha256"][request_id]
                        for request_id in request_ids
                    },
                    "full_information_required_before_claiming": True,
                }
            )
    document = {
        "schema_version": PREREGISTRATION_SCHEMA_VERSION,
        "status": "static-preregistered-unexecuted",
        "design_id": DESIGN_ID,
        "protected_starting_main": STARTING_PROTECTED_MAIN,
        "supersession": {
            "historical_asymmetry_audit_preserved": True,
            "historical_audit_sha256": ASYMMETRY_ARTIFACT_SHA256,
            "superseded_future_design": "two-private-bindings-by-two-seeds-by-three-arms",
            "reason": (
                "Private-binding identity, alias mapping, lexical identity, and commitment "
                "token sequence were confounded with singleton presentation position."
            ),
            "replacement_design": DESIGN_ID,
            "historical_diagnostics_rewritten": False,
        },
        "source_custody": source,
        "hypothesis": (
            "Within one independently selected private binding, controlled singleton "
            "presentation position and fixed transform seed distinguish presentation luck, "
            "deterministic seed interaction, and matched Parent-A/Parent-B asymmetry."
        ),
        "factorization": {
            "fresh_private_bindings": 1,
            "controlled_presentations": 2,
            "fixed_seed_blocks": 2,
            "transform_only_arms_per_cell": 3,
            "future_model_generations": 12,
            "derivation": "1 binding x 2 presentations x 2 seeds x 3 arms",
            "second_private_binding_in_minimum_experiment": False,
        },
        "binding_selection": _public_selection(selection),
        "panel_binding_commitments": {
            "root_commitment_sha256": private.secret_commitment,
            "profile_binding_sha256": private.profile_binding_sha256,
            "alias_map_commitment_sha256": private.alias_map_commitment,
            "branch_alias_map_commitment_sha256": dict(
                private.branch_alias_map_commitments
            ),
            "experiment_key_commitment_sha256": _experiment_key_commitment(root),
            "private_root_published": False,
            "private_mapping_published": False,
        },
        "canonical_semantic_parents": {
            "commitments": semantic_parent_commitments,
            "commitment_inputs": [
                "artifact role",
                "canonical sorted five-member support",
                "tied score",
                "pass-equivalence class",
                "panel identity",
            ],
            "presentation_invariant": True,
            "seed_invariant": True,
            "arm_invariant_when_parent_complete": True,
            "request_order_invariant": True,
        },
        "presentation_contract": {
            "P0": "private singleton ordinal one; other four ordered by public lexical order",
            "P1": "private singleton ordinal five; other four ordered by public lexical order",
            "private_validation_only": True,
            "model_visible_condition_labels": False,
            "same_support_sets": True,
            "same_semantic_commitments": True,
            "same_field_sets": True,
            "same_serialized_byte_lengths": True,
            "same_tokenizer_lengths": True,
            "only_support_list_order_differs": True,
            "exact_request_hash_binds_order": True,
            "proofs": isolation["presentation_proofs"],
        },
        "deletion_receipt_contract": {
            "per_parent": isolation["deletion_receipts"],
            "byte_identical_across_relevant_cells": True,
            "token_identical_across_relevant_cells": True,
            "presentation_invariant": True,
            "seed_invariant": True,
        },
        "seed_contract": {
            "seed_blocks": dict(SEED_BLOCKS),
            "same_seed_for_all_three_arms_within_cell": True,
            "independently_seeded_requests": True,
        },
        "cells": cells,
        "request_isolation": isolation,
        "transaction_contract": {
            "journal_schema": journal_event_schema(),
            "journal_schema_sha256": JOURNAL_SCHEMA_SHA256,
            "capture_schema": scientific.capture_schema(),
            "capture_schema_sha256": CAPTURE_SCHEMA_SHA256,
            "one_generation_maximum_per_cell_arm": True,
            "maximum_total_generations": 12,
            "request_started_without_capture": "terminal-inconclusive-no-retry",
            "duplicate_generation": "rejected",
            "captured_response_replay_without_model_contact": True,
            "unexpected_controller_failure": "repairable-with-capture-and-consumption-preserved",
            "captured_data_invalidity": "cell-arm-inconclusive",
            "append_only_authenticated_journal": True,
            "raw_sse_capture_before_parsing": True,
        },
        "authority_contract": {
            "schema_version": AUTHORITY_SCHEMA_VERSION,
            "authority_kind": AUTHORITY_KIND,
            "object_schema_sha256": AUTHORITY_OBJECT_SCHEMA_SHA256,
            "receipt_schema_version": AUTHORITY_RECEIPT_SCHEMA_VERSION,
            "receipt_schema_sha256": AUTHORITY_RECEIPT_SCHEMA_SHA256,
            "authority_created": False,
            "authority_consumed": False,
            "exact_published_commit_required": True,
            "exact_preregistration_artifact_required": True,
            "exact_twelve_request_hashes_required": True,
            "maximum_controller_repair_commits": MAXIMUM_CONTROLLER_REPAIR_COMMITS,
            "descendant_only_controller_repairs": True,
            "controller_repair_cannot_change_scientific_surface": True,
            "controller_repair_cannot_reset_consumption": True,
            "automatic_follow_on": False,
        },
        "scientific_decision_law": {
            "valid_full_information_baseline": [
                "rank zero selects the private singleton",
                "private score is 5/5",
                "transform and deterministic extraction verify",
                "custody passes",
            ],
            "invalid_full_information_cell": "INCONCLUSIVE",
            "deletion_supports_dependence_when": (
                "its full-information cell is valid and rank zero does not recover "
                "the private singleton at 5/5"
            ),
            "presentation_effect": "SINGLETON_PRESENTATION_POSITION_EFFECT_SUPPORTED",
            "seed_effect": "DETERMINISTIC_TRANSFORM_SEED_INTERACTION_SUPPORTED",
            "directional_asymmetry": "PARENT_DIRECTIONAL_ASYMMETRY_STRENGTHENED_WITHIN_MATCHED_BINDING",
            "bilateral_dependence": "BILATERAL_PARENT_DEPENDENCE_SUPPORTED_WITHIN_MATCHED_POSITION_SEED_CROSSOVER",
            "generalization_beyond_binding": False,
        },
        "implementation_binding": implementation,
        "execution_state": {
            "private_binding_created": True,
            "authority_created": False,
            "authority_consumed": False,
            "journal_created": False,
            "model_requests_issued": 0,
            "sidecar_launched": False,
            "live_execution_performed": False,
            "scientific_retry": False,
        },
        "locked_claims": dict(LOCKED_CLAIMS),
        "future_live_command_shape": (
            "python scripts/catalytic_kernel_0_balanced_rank_head_v2_position_seed_crossover.py "
            "run --repository <repository> --binary <server-binary> --model <pinned-gguf> "
            f"--design-id {DESIGN_ID} --external-authority-id <fresh-64-hex-id> "
            "--authorized-commit <published-static-commit>"
        ),
        "next_action": (
            "Separately authorize exactly one live execution with a fresh external authority "
            "bound to the published static commit and exact preregistration artifact."
        ),
    }
    _assert_public_no_smuggle(document)
    balanced.validate_metadata_only(document)
    return document


def write_preregistration(repository: Path, model_path: Path) -> Path:
    repository = repository.resolve(strict=False)
    path = repository / PREREGISTRATION_PATH
    document = build_preregistration_document(repository, model_path)
    if path.exists() or path.is_symlink():
        _require_regular(path, "position-seed preregistration")
    _atomic_json(path, document)
    return path


def validate_preregistration(repository: Path, model_path: Path) -> dict[str, Any]:
    repository = repository.resolve(strict=False)
    path = repository / PREREGISTRATION_PATH
    data = _require_regular(path, "position-seed preregistration")
    observed = _json_object(path, "position-seed preregistration")
    expected = build_preregistration_document(repository, model_path)
    _require(observed == expected, "preregistration differs from exact private reconstruction")
    _assert_public_no_smuggle(observed)
    implementation = observed["implementation_binding"]
    frozen = implementation["frozen_scientific_execution"]
    controller = implementation["repairable_controller"]
    _require(
        observed["execution_state"]["model_requests_issued"] == 0
        and observed["execution_state"]["authority_created"] is False
        and observed["execution_state"]["authority_consumed"] is False
        and observed["status"] == "static-preregistered-unexecuted",
        "observed execution entered immutable preregistration",
    )
    return {
        "status": "pass",
        "design_id": DESIGN_ID,
        "relative_path": PREREGISTRATION_PATH.as_posix(),
        "artifact_sha256": sha256_bytes(data),
        "document_sha256": json_sha256(observed),
        "future_model_generations": 12,
        "request_sha256": dict(observed["request_isolation"]["request_sha256"]),
        "frozen_scientific_execution_binding_sha256": frozen["sha256"],
        "repairable_controller_binding_sha256": controller["sha256"],
        "implementation_binding_sha256": implementation["sha256"],
        "authority_object_schema_sha256": AUTHORITY_OBJECT_SCHEMA_SHA256,
        "authority_receipt_schema_sha256": AUTHORITY_RECEIPT_SCHEMA_SHA256,
        "journal_schema_sha256": JOURNAL_SCHEMA_SHA256,
        "capture_schema_sha256": CAPTURE_SCHEMA_SHA256,
        "authority_created": False,
        "authority_consumed": False,
        "model_requests_issued": 0,
        "sidecar_launched": False,
        "live_execution_performed": False,
    }


def authority_id_sha256(raw_authority_id: str) -> str:
    _require(
        isinstance(raw_authority_id, str)
        and AUTHORITY_ID_RE.fullmatch(raw_authority_id) is not None,
        "external authority ID must be exactly 64 hexadecimal characters",
    )
    return sha256_bytes(AUTHORITY_ID_DOMAIN + bytes.fromhex(raw_authority_id))


def build_external_authority(
    repository: Path,
    model_path: Path,
    *,
    raw_authority_id: str,
    authorized_commit: str,
    current_commit: str,
    expected_model_sha256: str,
    expected_binary_sha256: str,
) -> dict[str, Any]:
    _require(
        GIT_COMMIT_RE.fullmatch(authorized_commit) is not None
        and GIT_COMMIT_RE.fullmatch(current_commit) is not None,
        "authority commit identity is malformed",
    )
    _require(current_commit == authorized_commit, "initial execution requires the exact authorized commit")
    _require(
        expected_model_sha256.upper() == MODEL_SHA256
        and expected_binary_sha256.upper() == BINARY_SHA256,
        "authority model or binary identity changed",
    )
    prereg = validate_preregistration(repository, model_path)
    return {
        "schema_version": AUTHORITY_SCHEMA_VERSION,
        "authority_kind": AUTHORITY_KIND,
        "design_id": DESIGN_ID,
        "authorized_commit": authorized_commit,
        "authority_id_sha256": authority_id_sha256(raw_authority_id),
        "preregistration_artifact_sha256": prereg["artifact_sha256"],
        "frozen_scientific_binding_sha256": prereg[
            "frozen_scientific_execution_binding_sha256"
        ],
        "repairable_controller_initial_binding_sha256": prereg[
            "repairable_controller_binding_sha256"
        ],
        "request_sha256": prereg["request_sha256"],
        "model_sha256": MODEL_SHA256,
        "binary_sha256": BINARY_SHA256,
        "journal_schema_sha256": JOURNAL_SCHEMA_SHA256,
        "capture_schema_sha256": CAPTURE_SCHEMA_SHA256,
        "maximum_generations_per_cell_arm": 1,
        "maximum_total_generations": 12,
        "physical_slots": 1,
        "sidecar_epochs": 1,
        "maximum_controller_repair_commits": MAXIMUM_CONTROLLER_REPAIR_COMMITS,
        "automatic_follow_on": False,
    }


def validate_controller_repair_policy(
    *,
    changed_paths: Iterable[str],
    repair_commit_count: int,
    frozen_scientific_changed: bool,
    request_hashes_changed: bool,
    consumption_reset: bool,
) -> dict[str, Any]:
    changed = sorted(set(changed_paths))
    _require(1 <= repair_commit_count <= MAXIMUM_CONTROLLER_REPAIR_COMMITS, "controller repair budget exceeded")
    _require(set(changed) <= ALLOWED_CONTROLLER_REPAIR_PATHS, "controller repair changed an unauthorized path")
    _require(not frozen_scientific_changed, "controller repair changed the frozen scientific surface")
    _require(not request_hashes_changed, "controller repair changed exact requests")
    _require(not consumption_reset, "controller repair reset cell-arm consumption")
    return {
        "status": "pass",
        "repair_commit_count": repair_commit_count,
        "changed_paths": changed,
        "frozen_scientific_preserved": True,
        "request_hashes_preserved": True,
        "consumption_preserved": True,
        "model_generations_during_repair": 0,
    }


def _controller_repair_report(
    repository: Path,
    authority: Mapping[str, Any],
    current_commit: str,
) -> dict[str, Any]:
    original = str(authority.get("authorized_commit", ""))
    if current_commit == original:
        return {
            "status": "pass",
            "repair_commit_count": 0,
            "changed_paths": [],
            "frozen_scientific_preserved": True,
            "request_hashes_preserved": True,
            "consumption_preserved": True,
            "model_generations_during_repair": 0,
        }
    _require(
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", original, current_commit],
            cwd=repository,
            check=False,
            capture_output=True,
        ).returncode
        == 0,
        "controller repair is not a descendant of the original execution commit",
    )
    commits = _git(repository, "rev-list", "--reverse", f"{original}..{current_commit}").splitlines()
    changed = _git(repository, "diff", "--name-only", original, current_commit).splitlines()
    prereg = _json_object(repository / PREREGISTRATION_PATH, "position-seed preregistration")
    frozen = prereg["implementation_binding"]["frozen_scientific_execution"]
    request_hashes = prereg["request_isolation"]["request_sha256"]
    return validate_controller_repair_policy(
        changed_paths=changed,
        repair_commit_count=len(commits),
        frozen_scientific_changed=(
            frozen["sha256"] != authority.get("frozen_scientific_binding_sha256")
        ),
        request_hashes_changed=(request_hashes != authority.get("request_sha256")),
        consumption_reset=False,
    )


def _authority_hmac(root: bytes, body: Mapping[str, Any]) -> str:
    return hmac.new(
        _experiment_key(root),
        AUTHORITY_HMAC_DOMAIN + canonical_json_bytes(body),
        hashlib.sha256,
    ).hexdigest().upper()


def consume_authority_once(
    repository: Path,
    authority: Mapping[str, Any],
    *,
    consuming_commit: str,
) -> dict[str, Any]:
    path = repository / AUTHORITY_RECEIPT_PATH
    parent_transaction._require_ignored(repository, path)
    _require(not path.exists() and not path.is_symlink(), "position-seed authority was already consumed")
    root, _private = _load_private(repository)
    body = {
        "schema_version": AUTHORITY_RECEIPT_SCHEMA_VERSION,
        "design_id": DESIGN_ID,
        "consumed": True,
        "authority": dict(authority),
        "consumed_at": _utc_now(),
        "consuming_commit": consuming_commit,
    }
    receipt = {**body, "authority_hmac_sha256": _authority_hmac(root, body)}
    _exclusive_write(
        path,
        json.dumps(receipt, sort_keys=True, indent=2).encode("utf-8") + b"\n",
    )
    return verify_authority_receipt(repository)


def verify_authority_receipt(repository: Path) -> dict[str, Any]:
    receipt = _json_object(repository / AUTHORITY_RECEIPT_PATH, "position-seed authority receipt")
    _require(set(receipt) == set(authority_receipt_schema()["required"]), "authority receipt field set changed")
    hmac_value = str(receipt.get("authority_hmac_sha256", ""))
    body = {key: value for key, value in receipt.items() if key != "authority_hmac_sha256"}
    root, _private = _load_private(repository)
    _require(hmac.compare_digest(hmac_value, _authority_hmac(root, body)), "authority receipt authentication changed")
    _require(receipt.get("consumed") is True and receipt.get("design_id") == DESIGN_ID, "authority receipt identity changed")
    return receipt


def _journal_hmac(key: bytes, event: Mapping[str, Any]) -> str:
    return hmac.new(
        key,
        JOURNAL_HMAC_DOMAIN + canonical_json_bytes(event),
        hashlib.sha256,
    ).hexdigest().upper()


def _journal_counts(events: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str | None], int]:
    counts: dict[tuple[str, str | None], int] = {}
    for event in events:
        key = (str(event["state"]), event.get("request_id"))
        counts[key] = counts.get(key, 0) + 1
    return counts


def _validate_transition(events: Sequence[Mapping[str, Any]], state: str, request_id: str | None) -> None:
    counts = _journal_counts(events)
    _require(state in journal_event_schema()["states"], "journal state changed")
    if state == "authority-consumed":
        _require(not events and request_id is None, "authority must be the genesis event")
        return
    _require(counts.get(("authority-consumed", None), 0) == 1, "work requires consumed authority")
    if state == "request-started":
        _require(request_id in REQUEST_IDS, "journal request identity changed")
        started = [
            event["request_id"] for event in events if event["state"] == "request-started"
        ]
        _require(
            len(started) < 12
            and request_id == EXECUTION_ORDER[len(started)]
            and counts.get(("request-started", request_id), 0) == 0,
            "duplicate or out-of-order model generation is forbidden",
        )
    elif state == "response-captured":
        _require(
            request_id in REQUEST_IDS
            and counts.get(("request-started", request_id), 0) == 1
            and counts.get(("response-captured", request_id), 0) == 0,
            "response capture transition is invalid",
        )
    elif state == "request-custody-observed":
        _require(
            request_id in REQUEST_IDS
            and counts.get(("response-captured", request_id), 0) == 1
            and counts.get(("request-custody-observed", request_id), 0) == 0,
            "request custody transition is invalid",
        )
    elif state == "request-inconclusive":
        _require(
            request_id in REQUEST_IDS
            and counts.get(("request-started", request_id), 0) == 1
            and counts.get(("response-captured", request_id), 0) == 0
            and counts.get(("request-inconclusive", request_id), 0) == 0,
            "inconclusive request transition is invalid",
        )
    elif state == "adjudicated":
        _require(
            request_id in REQUEST_IDS
            and (
                counts.get(("response-captured", request_id), 0) == 1
                or counts.get(("request-inconclusive", request_id), 0) == 1
            )
            and counts.get(("adjudicated", request_id), 0) == 0,
            "adjudication transition is invalid",
        )
    elif state == "controller-repair-observed":
        _require(request_id is None, "controller repair cannot target a request")
    elif state == "finalization-observed":
        _require(
            request_id is None
            and counts.get(("finalization-observed", None), 0) == 0,
            "finalization may be recorded exactly once",
        )
    elif state == "terminal-written":
        _require(
            request_id is None
            and counts.get(("finalization-observed", None), 0) == 1
            and counts.get(("terminal-written", None), 0) == 0,
            "terminal publication may be recorded exactly once after finalization",
        )
    elif state == "archived":
        _require(
            request_id is None
            and counts.get(("terminal-written", None), 0) == 1
            and counts.get(("archived", None), 0) == 0,
            "terminal archive may be recorded exactly once after publication",
        )


def read_journal(path: Path, key: bytes) -> list[dict[str, Any]]:
    if not path.exists() and not path.is_symlink():
        return []
    data = _require_regular(path, "position-seed journal", maximum=8 * 1024 * 1024)
    events: list[dict[str, Any]] = []
    previous = GENESIS_HASH
    for index, line in enumerate(data.splitlines()):
        try:
            event = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PositionSeedCrossoverError("journal is malformed") from exc
        _require(isinstance(event, dict), "journal event is not an object")
        _require(set(event) == set(journal_event_schema()["required_fields"]), "journal event fields changed")
        hmac_value = str(event["event_hmac_sha256"])
        event_without_hmac = {key_name: value for key_name, value in event.items() if key_name != "event_hmac_sha256"}
        event_sha = str(event_without_hmac["event_sha256"])
        hash_body = {key_name: value for key_name, value in event_without_hmac.items() if key_name != "event_sha256"}
        _require(
            event["schema_version"] == JOURNAL_SCHEMA_VERSION
            and event["design_id"] == DESIGN_ID
            and event["sequence"] == index
            and event["previous_event_sha256"] == previous
            and event_sha == json_sha256(hash_body)
            and hmac.compare_digest(hmac_value, _journal_hmac(key, event_without_hmac)),
            "journal chain or authentication changed",
        )
        _validate_transition(events, str(event["state"]), event.get("request_id"))
        events.append(event)
        previous = event_sha
    return events


def append_journal_event(
    path: Path,
    key: bytes,
    state: str,
    *,
    request_id: str | None = None,
    facts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    events = read_journal(path, key)
    _validate_transition(events, state, request_id)
    hash_body = {
        "schema_version": JOURNAL_SCHEMA_VERSION,
        "design_id": DESIGN_ID,
        "sequence": len(events),
        "state": state,
        "request_id": request_id,
        "facts": dict(facts or {}),
        "previous_event_sha256": events[-1]["event_sha256"] if events else GENESIS_HASH,
    }
    event_without_hmac = {**hash_body, "event_sha256": json_sha256(hash_body)}
    event = {**event_without_hmac, "event_hmac_sha256": _journal_hmac(key, event_without_hmac)}
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        with os.fdopen(descriptor, "ab", closefd=False) as handle:
            handle.write(canonical_json_bytes(event) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    return event


def state_paths(repository: Path) -> dict[str, Path]:
    run_root = repository.resolve(strict=False) / STATE_ROOT / DESIGN_ID
    captures = run_root / "captures"
    paths: dict[str, Path] = {
        "run_root": run_root,
        "manifest": run_root / "manifest.json",
        "journal": run_root / "journal.jsonl",
        "result": run_root / "result.json",
        "closure": run_root / "closure.json",
        "run_lock": run_root / "run.lock",
        "controller_lock": run_root / ".controller.lock",
        "receipt": repository.resolve(strict=False) / AUTHORITY_RECEIPT_PATH,
    }
    for request_id in REQUEST_IDS:
        paths[f"capture-{request_id}"] = captures / f"{request_id}.json"
        paths[f"partial-{request_id}"] = captures / f"{request_id}.raw.partial"
    return paths


def _runtime_allowed_paths(paths: Mapping[str, Path]) -> tuple[Path, ...]:
    return tuple(
        path
        for name, path in paths.items()
        if name not in {"run_root", "receipt"}
    )


def _runtime_for_request(
    repository: Path,
    private: balanced.PrivateBinding,
    request_id: str,
) -> Any:
    runtime_private = replace(
        private,
        run_keys={request_id: private.run_key(request_id)},
    )
    spec = parent_transaction.integration.V2RunSpec(
        run_id=request_id,
        ordinal=EXECUTION_ORDER.index(request_id) + 1,
        source_binding="within-binding-position-seed-crossover",
        source_profile_id=PANEL_PROFILE_ID,
        source_full_run_id=request_id,
        authorization_state="external-one-shot-panel-authority-required",
    )
    return parent_transaction.integration.RankHeadV2Runtime(
        repository=repository,
        spec=spec,
        private=runtime_private,
        run_design={"design_id": DESIGN_ID},
    )


def _capture_outcome(
    repository: Path,
    private: balanced.PrivateBinding,
    request_id: str,
    capture: Mapping[str, Any],
    rendered_tokens: int,
) -> dict[str, Any]:
    runtime = _runtime_for_request(repository, private, request_id)
    try:
        transport = kernel._normalized_transport(
            scientific.replay_capture(capture),
            rendered_tokens=rendered_tokens,
            max_tokens=64,
        )
        structured = runtime.parse_response("transform", transport["structured_content"])
        transform = runtime.normalize_transform(structured["operator"], structured["ranking"])
        frozen = v2.freeze_rank_head_selection(runtime, transform)
        extraction = v2.build_deterministic_extraction_receipt(runtime, transform, frozen=frozen)
    except (
        runtime_support.CatalyticInferenceRuntimeError,
        balanced.BalancedOpaqueError,
        parent_transaction.integration.RankHeadV2IntegrationError,
        v2.RankHeadDesignError,
    ) as exc:
        raise PositionSeedCrossoverError("captured transform is scientifically invalid") from exc
    evaluation = extraction["controller_private_evaluation"]
    presentation, seed_block, arm = _request_parts(request_id)
    return {
        "request_id": request_id,
        "cell_id": f"{presentation}-{seed_block}",
        "presentation": presentation,
        "seed_block": seed_block,
        "arm": arm,
        "transform_operator": transform["operator"],
        "transform_artifact_commitment": transform["artifact_commitment"],
        "transform_ranking_length": len(transform["ranking"]),
        "selected_rank": 0,
        "selection_frozen_before_private_mapping": True,
        "private_mapping_consulted_before_selection": False,
        "selected_private_singleton": bool(evaluation["mapped_to_full_public_support"]),
        "private_public_score": int(evaluation["full_public_score"]),
        "private_public_total": int(evaluation["full_public_total"]),
        "deterministic_extraction_commitment": extraction["artifact_commitment"],
    }


def adjudicate_outcomes(outcomes: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    _require(set(outcomes) == set(REQUEST_IDS), "adjudication requires all twelve cell-arms")
    cells: dict[str, Any] = {}
    for presentation in PRESENTATIONS:
        for seed_block in SEED_BLOCKS:
            cell_id = f"{presentation}-{seed_block}"
            full = outcomes[f"{cell_id}-full-information"]
            valid_full = (
                full.get("selected_private_singleton") is True
                and full.get("private_public_score") == 5
                and full.get("private_public_total") == 5
                and full.get("selection_frozen_before_private_mapping") is True
            )
            parents: dict[str, Any] = {}
            for arm, parent_name in (
                ("delete-parent-0", "Parent-A"),
                ("delete-parent-1", "Parent-B"),
            ):
                outcome = outcomes[f"{cell_id}-{arm}"]
                recovered = (
                    outcome.get("selected_private_singleton") is True
                    and outcome.get("private_public_score") == 5
                    and outcome.get("private_public_total") == 5
                )
                parents[parent_name] = {
                    "dependence_supported": bool(valid_full and not recovered),
                    "private_singleton_recovered": bool(recovered),
                    "classification": (
                        "DEPENDENCE_SUPPORTED"
                        if valid_full and not recovered
                        else "DEPENDENCE_NOT_SHOWN"
                        if valid_full
                        else "INCONCLUSIVE"
                    ),
                }
            cells[cell_id] = {
                "valid_full_information_baseline": valid_full,
                "Parent-A": parents["Parent-A"],
                "Parent-B": parents["Parent-B"],
            }
    valid_cells = all(cell["valid_full_information_baseline"] for cell in cells.values())
    parent_b_differences = []
    for seed_block in SEED_BLOCKS:
        p0 = cells[f"P0-{seed_block}"]["Parent-B"]["dependence_supported"]
        p1 = cells[f"P1-{seed_block}"]["Parent-B"]["dependence_supported"]
        parent_b_differences.append((p0, p1))
    presentation_effect = (
        valid_cells
        and all(left != right for left, right in parent_b_differences)
        and len(set(parent_b_differences)) == 1
    )
    seed_effect = valid_cells and any(
        cells[f"{presentation}-S0"][parent]["dependence_supported"]
        != cells[f"{presentation}-S1"][parent]["dependence_supported"]
        for presentation in PRESENTATIONS
        for parent in ("Parent-A", "Parent-B")
    )
    parent_a_all = all(cell["Parent-A"]["dependence_supported"] for cell in cells.values())
    parent_b_all = all(cell["Parent-B"]["dependence_supported"] for cell in cells.values())
    parent_b_none = all(not cell["Parent-B"]["dependence_supported"] for cell in cells.values())
    claims = []
    if presentation_effect:
        claims.append("SINGLETON_PRESENTATION_POSITION_EFFECT_SUPPORTED")
    if seed_effect:
        claims.append("DETERMINISTIC_TRANSFORM_SEED_INTERACTION_SUPPORTED")
    if valid_cells and parent_a_all and parent_b_none:
        claims.append("PARENT_DIRECTIONAL_ASYMMETRY_STRENGTHENED_WITHIN_MATCHED_BINDING")
    if valid_cells and parent_a_all and parent_b_all:
        claims.append("BILATERAL_PARENT_DEPENDENCE_SUPPORTED_WITHIN_MATCHED_POSITION_SEED_CROSSOVER")
    return {
        "all_full_information_baselines_valid": valid_cells,
        "cells": cells,
        "supported_panel_classifications": claims,
        "generalization_beyond_matched_binding": False,
        "cross_binding_claim_created": False,
    }


def _write_or_require_identical(path: Path, data: bytes) -> None:
    if path.exists() or path.is_symlink():
        _require(_require_regular(path, path.name, maximum=8 * 1024 * 1024) == data, f"existing {path.name} differs")
    else:
        _exclusive_write(path, data)


def _manifest(
    prereg: Mapping[str, Any],
    authority: Mapping[str, Any],
    public_preflight: Mapping[str, Any],
) -> dict[str, Any]:
    manifest = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "status": "prepared",
        "protected_commit": authority["authorized_commit"],
        "preregistration_artifact_sha256": prereg["artifact_sha256"],
        "frozen_scientific_binding_sha256": authority[
            "frozen_scientific_binding_sha256"
        ],
        "request_sha256": dict(authority["request_sha256"]),
        "execution_order": list(EXECUTION_ORDER),
        "future_model_generations": 12,
        "maximum_generations_per_cell_arm": 1,
        "physical_slots": 1,
        "sidecar_epochs": 1,
        "authority_id_sha256": authority["authority_id_sha256"],
        "authority_object_schema_sha256": AUTHORITY_OBJECT_SCHEMA_SHA256,
        "authority_receipt_schema_sha256": AUTHORITY_RECEIPT_SCHEMA_SHA256,
        "journal_schema_sha256": JOURNAL_SCHEMA_SHA256,
        "capture_schema_sha256": CAPTURE_SCHEMA_SHA256,
        "public_preflight": dict(public_preflight),
        "claiming": False,
        "automatic_follow_on": False,
    }
    _assert_public_no_smuggle(manifest)
    return manifest


def _recover_or_mark_started_request(
    paths: Mapping[str, Path],
    key: bytes,
    request_id: str,
    expected_request_sha256: str,
) -> None:
    events = read_journal(paths["journal"], key)
    counts = _journal_counts(events)
    if counts.get(("request-started", request_id), 0) == 0:
        return
    if counts.get(("response-captured", request_id), 0) == 1 or counts.get(("request-inconclusive", request_id), 0) == 1:
        return
    capture_path = paths[f"capture-{request_id}"]
    if capture_path.is_file() and not capture_path.is_symlink():
        capture = scientific.verify_capture(
            capture_path,
            experiment_key=key,
            request_id=request_id,
            model_request_sha256=expected_request_sha256,
        )
        append_journal_event(
            paths["journal"],
            key,
            "response-captured",
            request_id=request_id,
            facts={
                "capture_sha256": capture["capture_sha256"],
                "model_request_sha256": expected_request_sha256,
                "captured_before_parsing": True,
                "restart_reconciled": True,
            },
        )
    else:
        append_journal_event(
            paths["journal"],
            key,
            "request-inconclusive",
            request_id=request_id,
            facts={
                "classification": "INCONCLUSIVE",
                "reason": "request-started-without-exact-capture",
                "retry_allowed": False,
            },
        )


def _public_preflight(full_preflight: Mapping[str, Any]) -> dict[str, Any]:
    public = {
        "stable": dict(full_preflight.get("stable", {})),
        "candidate": dict(full_preflight.get("candidate", {})),
        "model_identity": dict(full_preflight.get("model_identity", {})),
        "binary_identity": dict(full_preflight.get("binary_identity", {})),
        "port_9494_free": full_preflight.get("port_9494_free"),
        "run_lock_absent": full_preflight.get("run_lock_absent", True),
    }
    return public


def _archive_terminal(repository: Path, paths: Mapping[str, Path]) -> dict[str, Any]:
    files = {
        "authority-receipt.json": paths["receipt"],
        "manifest.json": paths["manifest"],
        "journal.jsonl": paths["journal"],
        "result.json": paths["result"],
        "closure.json": paths["closure"],
    }
    for request_id in REQUEST_IDS:
        capture = paths[f"capture-{request_id}"]
        if capture.is_file() and not capture.is_symlink():
            files[f"captures/{request_id}.json"] = capture
    entries = []
    for name, path in sorted(files.items()):
        data = _require_regular(path, f"archive source {name}", maximum=8 * 1024 * 1024)
        entries.append({"path": name, "byte_size": len(data), "sha256": sha256_bytes(data)})
    bundle_body = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "files": entries,
        "content_addressed": True,
    }
    bundle_sha = json_sha256(bundle_body)
    destination = repository / ARCHIVE_ROOT / DESIGN_ID / bundle_sha
    if destination.exists() or destination.is_symlink():
        observed = _json_object(destination / "bundle.json", "archive bundle manifest")
        _require(observed == {**bundle_body, "bundle_sha256": bundle_sha}, "existing archive differs")
    else:
        destination.mkdir(parents=True)
        for name, source in files.items():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            _exclusive_write(target, _require_regular(source, f"archive source {name}", maximum=8 * 1024 * 1024))
        _exclusive_write(
            destination / "bundle.json",
            json.dumps({**bundle_body, "bundle_sha256": bundle_sha}, sort_keys=True, indent=2).encode("utf-8") + b"\n",
        )
    return {
        "bundle_sha256": bundle_sha,
        "file_count": len(entries),
        "relative_path": destination.relative_to(repository).as_posix(),
        "verified": True,
    }


def _verify_existing_archive(repository: Path, bundle_sha256: str) -> dict[str, Any]:
    _require(re.fullmatch(r"[0-9A-F]{64}", bundle_sha256) is not None, "archive commitment changed")
    destination = repository / ARCHIVE_ROOT / DESIGN_ID / bundle_sha256
    bundle = _json_object(destination / "bundle.json", "archive bundle manifest")
    _require(
        bundle.get("bundle_sha256") == bundle_sha256
        and bundle.get("design_id") == DESIGN_ID
        and bundle.get("content_addressed") is True,
        "archive bundle identity changed",
    )
    body = {key: value for key, value in bundle.items() if key != "bundle_sha256"}
    _require(json_sha256(body) == bundle_sha256, "archive bundle commitment changed")
    entries = bundle.get("files")
    _require(isinstance(entries, list) and entries, "archive bundle entries changed")
    for entry in entries:
        _require(isinstance(entry, dict), "archive bundle entry changed")
        relative = str(entry.get("path", ""))
        _require(relative and ".." not in Path(relative).parts, "archive bundle path changed")
        data = _require_regular(
            destination / relative,
            f"archived {relative}",
            maximum=8 * 1024 * 1024,
        )
        _require(
            entry.get("byte_size") == len(data)
            and entry.get("sha256") == sha256_bytes(data),
            f"archived {relative} differs from its commitment",
        )
    return {
        "bundle_sha256": bundle_sha256,
        "file_count": len(entries),
        "relative_path": destination.relative_to(repository).as_posix(),
        "verified": True,
    }


def run_panel(
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
    _require(isinstance(raw_authority_id, str) and isinstance(authorized_commit, str), "live panel requires explicit external authority")
    model_path = Path(str(getattr(args, "model"))).resolve()
    prereg = validate_preregistration(repository, model_path)
    root, private = _load_private(repository)
    key = _experiment_key(root)
    paths = state_paths(repository)
    for name, path in paths.items():
        if name != "run_root":
            parent_transaction._require_ignored(repository, path)
    live = adapter or kernel.CatalyticKernel0Adapter(repository)
    full_preflight = live.preflight(
        args=args,
        repository_root=repository,
        run_root=paths["run_root"],
        allowed_paths=_runtime_allowed_paths(paths),
    )
    public_preflight = _public_preflight(full_preflight)
    current_commit = str(public_preflight.get("stable", {}).get("head", ""))
    model_sha = str(public_preflight.get("model_identity", {}).get("sha256", ""))
    binary_sha = str(public_preflight.get("binary_identity", {}).get("sha256", ""))
    if paths["receipt"].exists() or paths["receipt"].is_symlink():
        receipt = verify_authority_receipt(repository)
        authority = dict(receipt["authority"])
        _require(
            authority["authorized_commit"] == authorized_commit
            and authority["authority_id_sha256"] == authority_id_sha256(raw_authority_id),
            "resume authority differs from consumed authority",
        )
        repair = _controller_repair_report(repository, authority, current_commit)
    else:
        authority = build_external_authority(
            repository,
            model_path,
            raw_authority_id=raw_authority_id,
            authorized_commit=authorized_commit,
            current_commit=current_commit,
            expected_model_sha256=model_sha,
            expected_binary_sha256=binary_sha,
        )
        receipt = None
        repair = _controller_repair_report(repository, authority, current_commit)
    manifest_data = json.dumps(
        _manifest(prereg, authority, public_preflight),
        sort_keys=True,
        indent=2,
    ).encode("utf-8") + b"\n"
    paths["run_root"].mkdir(parents=True, exist_ok=True)
    with parent_transaction.controller_lock(paths["controller_lock"]):
        with parent_transaction.run_lock(paths["run_lock"]):
            _write_or_require_identical(paths["manifest"], manifest_data)
            if receipt is None:
                receipt = consume_authority_once(
                    repository,
                    authority,
                    consuming_commit=current_commit,
                )
            events = read_journal(paths["journal"], key)
            if not events:
                append_journal_event(
                    paths["journal"],
                    key,
                    "authority-consumed",
                    facts={
                        "authority_receipt_sha256": sha256_bytes(
                            _require_regular(paths["receipt"], "authority receipt")
                        ),
                        "authorized_commit": authority["authorized_commit"],
                    },
                )
            if repair["repair_commit_count"] > 0 and not any(
                event["state"] == "controller-repair-observed"
                and event["facts"].get("repair_commit_count") == repair["repair_commit_count"]
                for event in read_journal(paths["journal"], key)
            ):
                append_journal_event(
                    paths["journal"],
                    key,
                    "controller-repair-observed",
                    facts=repair,
                )
            events = read_journal(paths["journal"], key)
            finalization_events = [
                event for event in events if event["state"] == "finalization-observed"
            ]
            _require(len(finalization_events) <= 1, "finalization journal multiplicity changed")
            if finalization_events:
                cleanup = dict(finalization_events[0]["facts"]["cleanup"])
                postflight = dict(finalization_events[0]["facts"]["postflight"])
            else:
                for request_id in EXECUTION_ORDER:
                    _recover_or_mark_started_request(
                        paths,
                        key,
                        request_id,
                        authority["request_sha256"][request_id],
                    )
                events = read_journal(paths["journal"], key)
                remaining = [
                    request_id
                    for request_id in EXECUTION_ORDER
                    if _journal_counts(events).get(("request-started", request_id), 0) == 0
                ]
                cleanup = {"passed": True, "no_sidecar_required": not remaining}
                postflight = {"passed": True, "no_sidecar_required": not remaining}
                if remaining:
                    pool = live.create_lease_pool(1)
                    sidecar: Any | None = None
                    try:
                        sidecar, _readiness = live.launch_sidecar(
                            preflight=full_preflight,
                            run_id=DESIGN_ID,
                        )
                        for request_id in EXECUTION_ORDER:
                            events = read_journal(paths["journal"], key)
                            if _journal_counts(events).get(("request-started", request_id), 0):
                                continue
                            payload = build_request(root, private, request_id)
                            try:
                                scientific.execute_and_capture_request(
                                    experiment_key=key,
                                    frozen_binding_sha256=authority[
                                        "frozen_scientific_binding_sha256"
                                    ],
                                    payload=payload,
                                    request_id=request_id,
                                    expected_request_sha256=authority["request_sha256"][request_id],
                                    generation_ordinal=EXECUTION_ORDER.index(request_id) + 1,
                                    live=live,
                                    sidecar=sidecar,
                                    pool=pool,
                                    full_preflight=full_preflight,
                                    capture_path=paths[f"capture-{request_id}"],
                                    partial_path=paths[f"partial-{request_id}"],
                                    append_event=lambda state, **kwargs: append_journal_event(
                                        paths["journal"], key, state, **kwargs
                                    ),
                                )
                            except BaseException as exc:
                                if not paths[f"capture-{request_id}"].is_file():
                                    append_journal_event(
                                        paths["journal"],
                                        key,
                                        "request-inconclusive",
                                        request_id=request_id,
                                        facts={
                                            "classification": "INCONCLUSIVE",
                                            "reason_sha256": sha256_bytes(str(exc).encode("utf-8")),
                                            "retry_allowed": False,
                                        },
                                    )
                                else:
                                    raise
                    finally:
                        try:
                            cleanup = dict(live.cleanup(sidecar=sidecar, preflight=full_preflight))
                        except BaseException as exc:
                            cleanup = {"passed": False, "failure_sha256": sha256_bytes(str(exc).encode("utf-8"))}
                        try:
                            postflight = dict(live.postflight(preflight=full_preflight))
                        except BaseException as exc:
                            postflight = {"passed": False, "failure_sha256": sha256_bytes(str(exc).encode("utf-8"))}
                append_journal_event(
                    paths["journal"],
                    key,
                    "finalization-observed",
                    facts={"cleanup": cleanup, "postflight": postflight},
                )
        events = read_journal(paths["journal"], key)
        terminal_events = [event for event in events if event["state"] == "terminal-written"]
        archived_events = [event for event in events if event["state"] == "archived"]
        _require(len(terminal_events) <= 1 and len(archived_events) <= 1, "terminal journal multiplicity changed")
        if terminal_events:
            result_data = _require_regular(paths["result"], "terminal result", maximum=8 * 1024 * 1024)
            closure_data = _require_regular(paths["closure"], "terminal closure", maximum=8 * 1024 * 1024)
            terminal_facts = terminal_events[0]["facts"]
            _require(
                terminal_facts.get("result_sha256") == sha256_bytes(result_data)
                and terminal_facts.get("closure_sha256") == sha256_bytes(closure_data),
                "terminal files differ from their journal commitments",
            )
            result = _json_object(paths["result"], "terminal result")
            if archived_events:
                archive = _verify_existing_archive(
                    repository,
                    str(archived_events[0]["facts"].get("archive_sha256", "")),
                )
            else:
                archive = _archive_terminal(repository, paths)
                append_journal_event(
                    paths["journal"],
                    key,
                    "archived",
                    facts={"archive_sha256": archive["bundle_sha256"], "claiming": False},
                )
            return {**result, "evidence_archive_sha256": archive["bundle_sha256"]}
        counts = _journal_counts(events)
        outcomes: dict[str, dict[str, Any]] = {}
        for request_id in REQUEST_IDS:
            if counts.get(("response-captured", request_id), 0) != 1:
                continue
            started = next(
                event
                for event in events
                if event["state"] == "request-started" and event["request_id"] == request_id
            )
            capture = scientific.verify_capture(
                paths[f"capture-{request_id}"],
                experiment_key=key,
                request_id=request_id,
                model_request_sha256=authority["request_sha256"][request_id],
            )
            try:
                outcome = _capture_outcome(
                    repository,
                    private,
                    request_id,
                    capture,
                    int(started["facts"]["rendered_prompt_tokens"]),
                )
            except PositionSeedCrossoverError as exc:
                outcome = {
                    "request_id": request_id,
                    "classification": "INCONCLUSIVE",
                    "reason_sha256": sha256_bytes(str(exc).encode("utf-8")),
                }
            outcomes[request_id] = outcome
            if counts.get(("adjudicated", request_id), 0) == 0:
                append_journal_event(
                    paths["journal"],
                    key,
                    "adjudicated",
                    request_id=request_id,
                    facts=outcome,
                )
        panel = adjudicate_outcomes(outcomes) if set(outcomes) == set(REQUEST_IDS) and all("selected_private_singleton" in item for item in outcomes.values()) else {
            "all_full_information_baselines_valid": False,
            "cells": {},
            "supported_panel_classifications": [],
            "generalization_beyond_matched_binding": False,
            "cross_binding_claim_created": False,
        }
        result = {
            "schema_version": 1,
            "design_id": DESIGN_ID,
            "status": "complete" if len(outcomes) == 12 and cleanup.get("passed") is True and postflight.get("passed") is True else "inconclusive",
            "completed_model_generations": sum(
                1 for event in events if event["state"] == "request-started"
            ),
            "maximum_model_generations": 12,
            "request_outcomes": [outcomes[request_id] for request_id in REQUEST_IDS if request_id in outcomes],
            "panel_adjudication": panel,
            "cleanup": cleanup,
            "postflight": postflight,
            "claims": dict(LOCKED_CLAIMS),
            "claiming": False,
            "automatic_follow_on": False,
        }
        _assert_public_no_smuggle(result)
        result_data = json.dumps(result, sort_keys=True, indent=2).encode("utf-8") + b"\n"
        _write_or_require_identical(paths["result"], result_data)
        closure = {
            "schema_version": 1,
            "design_id": DESIGN_ID,
            "status": result["status"],
            "manifest_sha256": sha256_bytes(manifest_data),
            "result_sha256": sha256_bytes(result_data),
            "authority_receipt_sha256": sha256_bytes(_require_regular(paths["receipt"], "authority receipt")),
            "journal_head_before_terminal": read_journal(paths["journal"], key)[-1]["event_sha256"],
            "run_lock_absent_at_terminal_publication": not paths["run_lock"].exists(),
            "retry_allowed": False,
            "claiming": False,
        }
        _assert_public_no_smuggle(closure)
        closure_data = json.dumps(closure, sort_keys=True, indent=2).encode("utf-8") + b"\n"
        _write_or_require_identical(paths["closure"], closure_data)
        append_journal_event(
            paths["journal"],
            key,
            "terminal-written",
            facts={
                "result_sha256": sha256_bytes(result_data),
                "closure_sha256": sha256_bytes(closure_data),
                "status": result["status"],
            },
        )
        archive = _archive_terminal(repository, paths)
        append_journal_event(
            paths["journal"],
            key,
            "archived",
            facts={"archive_sha256": archive["bundle_sha256"], "claiming": False},
        )
        return {**result, "evidence_archive_sha256": archive["bundle_sha256"]}


def validate_static(repository: Path, model_path: Path) -> dict[str, Any]:
    selection = validate_private_binding(repository, model_path)
    prereg = validate_preregistration(repository, model_path)
    source = verify_source_custody(repository)
    return {
        "status": "pass",
        "design_id": DESIGN_ID,
        "selected_counter": selection["selected_counter"],
        "first_match_verified": selection["first_match_verified"],
        "future_model_generations": 12,
        "request_count": 12,
        "preregistration": prereg,
        "source_custody": source,
        "authority_created": False,
        "authority_consumed": False,
        "model_requests_issued": 0,
        "sidecar_launched": False,
        "live_execution_performed": False,
        "scientific_retry": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="operation", required=True)
    for name in ("prepare-private", "generate", "validate"):
        command = subparsers.add_parser(name)
        command.add_argument("--repository", required=True)
        command.add_argument("--model", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--repository", required=True)
    run.add_argument("--binary", required=True)
    run.add_argument("--model", required=True)
    run.add_argument("--design-id", required=True)
    run.add_argument("--external-authority-id", required=True)
    run.add_argument("--authorized-commit", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository = Path(args.repository).resolve(strict=False)
    model_path = Path(args.model).resolve()
    try:
        if args.operation == "prepare-private":
            result = prepare_private_binding(repository, model_path)
        elif args.operation == "generate":
            prepare_private_binding(repository, model_path)
            path = write_preregistration(repository, model_path)
            result = {
                "status": "written",
                "path": path.relative_to(repository).as_posix(),
                "artifact_sha256": sha256_bytes(path.read_bytes()),
                "future_model_generations": 12,
                "authority_created": False,
                "model_requests_issued": 0,
            }
        elif args.operation == "validate":
            result = validate_static(repository, model_path)
        else:
            result = run_panel(args, repository_root=repository)
    except (
        OSError,
        subprocess.SubprocessError,
        PositionSeedCrossoverError,
        scientific.ScientificSurfaceError,
        balanced.BalancedOpaqueError,
        v2.RankHeadDesignError,
    ) as exc:
        print(canonical_json_text({"status": "fail", "error": str(exc)}))
        return 1
    print(canonical_json_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
