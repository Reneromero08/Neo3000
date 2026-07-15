#!/usr/bin/env python3
"""Leakage-resistant bilateral information architecture for Catalytic Kernel 0.

This module changes only the model-visible carrier and artifact projections.  The
existing CK0 runner continues to own sidecar launch, cache admission, physical
leases, custody, cleanup, and restoration.  No function in this module launches
a process or contacts a model.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from catalytic_advantage_tasks import (
    EXPECTED_SUITE_SHA256,
    build_frozen_task_suite,
    execute_program,
)
from catalytic_inference_bench_0 import validate_metadata_only
from catalytic_inference_bench_0_runtime import MODEL_ALIAS


BINDING_1_PROFILE_ID = "balanced-opaque-relational-carrier-v1"
BINDING_2_PROFILE_ID = "balanced-opaque-relational-carrier-v1-binding-2"
PROFILE_ID = BINDING_1_PROFILE_ID
CARRIER_ID = "ck0:balanced-opaque-relational-carrier-v1"
STARTING_PROTECTED_MAIN = "9eb024d9f664b5592997aac90081d083e75adbd1"
PREREGISTRATION_PATH = "lab/ck0_balanced_opaque_relational_carrier_v1.json"
BINDING_2_STARTING_PROTECTED_MAIN = "234bce73cff600879f0ff9c3e02f176f32f6626c"
BINDING_2_PREREGISTRATION_PATH = (
    "lab/ck0_balanced_opaque_relational_carrier_v1_binding_2.json"
)
PRIVATE_SECRET_PATH = (
    "state/catalytic_kernel_0_private/"
    "balanced-opaque-relational-carrier-v1.secret"
)
PRIVATE_CREATION_RECEIPT_PATH = (
    "state/catalytic_kernel_0_private/"
    "balanced-opaque-relational-carrier-v1.creation.json"
)
BINDING_2_PRIVATE_SECRET_PATH = (
    "state/catalytic_kernel_0_private/"
    "balanced-opaque-relational-carrier-v1-binding-2.secret"
)
BINDING_2_PRIVATE_CREATION_RECEIPT_PATH = (
    "state/catalytic_kernel_0_private/"
    "balanced-opaque-relational-carrier-v1-binding-2.creation.json"
)

TASK_INDEX = 2
TASK_ID = "cs1-task-03"
BRANCH_INDICES = {"branch-a": (0, 1, 2), "branch-b": (2, 3, 4)}
PARENT_ROLES = {"branch-a": "parent-0", "branch-b": "parent-1"}
EXPECTED_SUPPORTS = {
    "branch-a": ("C02", "C31", "C34", "C38", "C53"),
    "branch-b": ("C16", "C34", "C46", "C51", "C60"),
}
EXPECTED_FULL_SUPPORT = ("C34",)
EXPECTED_EXCLUSIVES = {
    "branch-a": ("C02", "C31", "C38", "C53"),
    "branch-b": ("C16", "C46", "C51", "C60"),
}
EXPECTED_TOP_SCORE = 3
EXPECTED_PLATEAU_GAP = 1
EXPECTED_PASS_VECTOR = (True, True, True)

REQUEST_IDS = ("borrow", "branch-a", "branch-b", "transform", "extract", "restore")
ALLOWED_OPERATORS = frozenset({"combine", "oppose", "eliminate", "refine", "reconcile"})
ALIASES = tuple(f"K{index:02d}" for index in range(64))
INTERNAL_CANDIDATE_RE = re.compile(r"(?<![A-Za-z0-9])C\d{2}(?![A-Za-z0-9])")
SHA256_RE = re.compile(r"^[0-9A-F]{64}$")

FULL_RUN_ID = "ck0-balanced-v1-full-r1"
DELETE_A_RUN_ID = "ck0-balanced-v1-delete-a-r1"
DELETE_B_RUN_ID = "ck0-balanced-v1-delete-b-r1"
RUN_MODES = {
    FULL_RUN_ID: "full-information",
    DELETE_A_RUN_ID: "delete-parent-0",
    DELETE_B_RUN_ID: "delete-parent-1",
}
BINDING_2_FULL_RUN_ID = "ck0-balanced-v1b2-full-r1"
BINDING_2_DELETE_A_RUN_ID = "ck0-balanced-v1b2-delete-a-r1"
BINDING_2_DELETE_B_RUN_ID = "ck0-balanced-v1b2-delete-b-r1"
BINDING_2_RUN_MODES = {
    BINDING_2_FULL_RUN_ID: "full-information",
    BINDING_2_DELETE_A_RUN_ID: "delete-parent-0",
    BINDING_2_DELETE_B_RUN_ID: "delete-parent-1",
}
DELETED_PARENT_BY_MODE = {
    "delete-parent-0": "parent-0",
    "delete-parent-1": "parent-1",
}


@dataclass(frozen=True)
class PrivateBindingConfiguration:
    """Controller-private binding selector; never serialized into model payloads."""

    profile_id: str
    preregistration_path: str
    secret_path: str
    creation_receipt_path: str
    run_modes: Mapping[str, str] = field(repr=False)
    domain_separation_identity: str = field(repr=False)
    protected_starting_sha: str
    legacy_domain_compatibility: bool = False


BINDING_1 = PrivateBindingConfiguration(
    profile_id=BINDING_1_PROFILE_ID,
    preregistration_path=PREREGISTRATION_PATH,
    secret_path=PRIVATE_SECRET_PATH,
    creation_receipt_path=PRIVATE_CREATION_RECEIPT_PATH,
    run_modes=RUN_MODES,
    domain_separation_identity=BINDING_1_PROFILE_ID,
    protected_starting_sha=STARTING_PROTECTED_MAIN,
    legacy_domain_compatibility=True,
)
BINDING_2 = PrivateBindingConfiguration(
    profile_id=BINDING_2_PROFILE_ID,
    preregistration_path=BINDING_2_PREREGISTRATION_PATH,
    secret_path=BINDING_2_PRIVATE_SECRET_PATH,
    creation_receipt_path=BINDING_2_PRIVATE_CREATION_RECEIPT_PATH,
    run_modes=BINDING_2_RUN_MODES,
    domain_separation_identity=BINDING_2_PROFILE_ID,
    protected_starting_sha=BINDING_2_STARTING_PROTECTED_MAIN,
)
BINDING_CONFIGURATIONS = {
    BINDING_1.profile_id: BINDING_1,
    BINDING_2.profile_id: BINDING_2,
}
RUN_CONFIGURATION_BY_ID = {
    run_id: configuration
    for configuration in BINDING_CONFIGURATIONS.values()
    for run_id in configuration.run_modes
}

SECRET_COMMITMENT_DOMAIN = b"ck0-balanced-v1/secret-commitment\0"
CREATION_RECEIPT_DOMAIN = b"ck0-balanced-v1/creation-receipt\0"
ALIAS_ORDER_DOMAIN = b"ck0-balanced-v1/alias-order\0"
ALIAS_MAP_DOMAIN = b"ck0-balanced-v1/alias-map\0"
BRANCH_ALIAS_ORDER_DOMAIN = b"ck0-balanced-v1/branch-alias-order\0"
BRANCH_ALIAS_MAP_DOMAIN = b"ck0-balanced-v1/branch-alias-map\0"
RUN_KEY_DOMAIN = b"ck0-balanced-v1/run-key\0"
RUN_KEY_COMMITMENT_DOMAIN = b"ck0-balanced-v1/run-key-commitment\0"
ARTIFACT_DOMAIN = b"ck0-balanced-v1/artifact\0"

BRANCH_ARTIFACT_FIELDS = frozenset(
    {
        "artifact_role",
        "support_aliases",
        "tied_top_score",
        "pass_equivalence_class",
        "artifact_commitment",
    }
)
DELETION_RECEIPT_FIELDS = frozenset(
    {
        "artifact_role",
        "artifact_commitment",
        "projection_mode",
        "informative_content_withheld",
    }
)
TRANSFORM_ARTIFACT_FIELDS = frozenset({"operator", "ranking", "artifact_commitment"})
EXTRACTION_ARTIFACT_FIELDS = frozenset(
    {
        "candidate_alias",
        "transform_artifact_commitment_consumed",
        "controller_private_evaluation",
        "artifact_commitment",
    }
)

MODEL_IDENTITY = {
    "filename": "Agents-A1-Q4_K_M.gguf",
    "size_bytes": 21166757632,
    "sha256": "31AEFA25B7E1EDBDE436E643E2B5E3F6E57820A4811D97B131130E48FF0772C2",
}
BINARY_IDENTITY = {
    "filename": "llama-server.exe",
    "version": "13 (417e1d6)",
    "sha256": "5D0C5F7CE5CEBE35B564C21521ECD426F809445521D3C55C0581A9543F15541B",
}

FULL_CLASSIFICATIONS = (
    "BALANCED_OPAQUE_RELATIONAL_VISIBLE",
    "BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
    "INCONCLUSIVE",
)
DELETE_A_CLASSIFICATIONS = (
    "PARENT_A_INFORMATION_DEPENDENCE_SUPPORTED",
    "PARENT_A_UNAIDED_EXCHANGEABLE_HIT",
    "CAUSAL_CONTROL_INCONCLUSIVE",
)
DELETE_B_CLASSIFICATIONS = (
    "PARENT_B_INFORMATION_DEPENDENCE_SUPPORTED",
    "PARENT_B_UNAIDED_EXCHANGEABLE_HIT",
    "CAUSAL_CONTROL_INCONCLUSIVE",
)

FORBIDDEN_MODEL_VISIBLE_KEYS = frozenset(
    {
        "task_id",
        "profile_id",
        "task_suite_sha256",
        "scan_sha256",
        "public_score_matrix_sha256",
        "branch_shards",
        "shared_calibration_example_id",
        "full_public_winner",
        "alias_mapping",
        "internal_candidate_id",
        "model_ranking",
        "public_argmax_set",
        "public_shard_ids",
        "public_examples",
        "pass_vectors",
        "artifact_sha256",
    }
)


class BalancedOpaqueError(ValueError):
    """The balanced opaque carrier boundary is malformed or unsafe."""


def binding_configuration(profile_id: str) -> PrivateBindingConfiguration:
    try:
        return BINDING_CONFIGURATIONS[profile_id]
    except KeyError as exc:
        raise BalancedOpaqueError("unknown private binding configuration") from exc


def binding_configuration_for_run(run_id: str) -> PrivateBindingConfiguration:
    try:
        return RUN_CONFIGURATION_BY_ID[run_id]
    except KeyError as exc:
        raise BalancedOpaqueError("run ID is not preregistered") from exc


def _domain(
    base: bytes,
    configuration: PrivateBindingConfiguration,
) -> bytes:
    if configuration.legacy_domain_compatibility:
        return base
    return (
        base
        + b"binding-identity\0"
        + configuration.domain_separation_identity.encode("ascii")
        + b"\0"
    )


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


def _normalized_text_sha256(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return sha256_bytes(data)


def _is_reparse(path: Path) -> bool:
    details = path.lstat()
    attributes = getattr(details, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(details.st_mode) or bool(attributes & reparse_flag)


def _assert_safe_ancestry(repository: Path, target: Path) -> None:
    repository = repository.absolute()
    target = target.absolute()
    try:
        relative = target.relative_to(repository)
    except ValueError as exc:
        raise BalancedOpaqueError("private state must remain below the repository") from exc
    current = repository
    if not current.is_dir() or _is_reparse(current):
        raise BalancedOpaqueError("repository ancestry is unsafe")
    for part in relative.parts[:-1]:
        current = current / part
        if current.exists() and (not current.is_dir() or _is_reparse(current)):
            raise BalancedOpaqueError("private state ancestry is unsafe")


def private_secret_path(
    repository: Path,
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> Path:
    return repository.absolute() / Path(configuration.secret_path)


def _private_creation_receipt_path(
    repository: Path,
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> Path:
    return repository.absolute() / Path(configuration.creation_receipt_path)


def _creation_receipt_body(
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "secret_relative_path": configuration.secret_path,
        "generation_source": "secrets.token_bytes",
        "generated_bytes": 32,
        "generation_count": 1,
        "publication_law": "exclusive-once-atomic-publish",
    }


def _write_private_creation_receipt_once(
    repository: Path,
    secret: bytes,
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> Path:
    if len(secret) != 32:
        raise BalancedOpaqueError("private state has the wrong length")
    target = _private_creation_receipt_path(repository, configuration)
    _assert_safe_ancestry(repository, target)
    if target.exists() or target.is_symlink():
        raise BalancedOpaqueError("balanced opaque creation receipt already exists")
    body = _creation_receipt_body(configuration)
    receipt = {
        **body,
        "receipt_hmac_sha256": hmac.new(
            secret,
            _domain(CREATION_RECEIPT_DOMAIN, configuration)
            + canonical_json_bytes(body),
            hashlib.sha256,
        ).hexdigest().upper(),
    }
    fd, temporary_name = tempfile.mkstemp(prefix=".balanced-opaque-", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        payload = canonical_json_bytes(receipt)
        written = os.write(fd, payload)
        if written != len(payload):
            raise BalancedOpaqueError("private creation receipt write was incomplete")
        os.fsync(fd)
        os.close(fd)
        fd = -1
        try:
            os.link(temporary, target, follow_symlinks=False)
        except FileExistsError as exc:
            raise BalancedOpaqueError(
                "balanced opaque creation receipt appeared during creation"
            ) from exc
        os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)
    finally:
        if fd >= 0:
            os.close(fd)
        if temporary.exists():
            temporary.unlink()
    return target


def create_private_secret_once(
    repository: Path,
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> Path:
    """Create the 32-byte private root exactly once without exposing its value."""
    repository = repository.absolute()
    target = private_secret_path(repository, configuration)
    receipt = _private_creation_receipt_path(repository, configuration)
    _assert_safe_ancestry(repository, receipt)
    if receipt.exists() or receipt.is_symlink():
        raise BalancedOpaqueError(
            "balanced opaque creation receipt already exists"
        )
    _assert_safe_ancestry(repository, target)
    if target.exists() or target.is_symlink():
        raise BalancedOpaqueError("balanced opaque private state already exists")
    parent = target.parent
    state_root = repository / "state"
    if not state_root.is_dir() or _is_reparse(state_root):
        raise BalancedOpaqueError("state root is missing or unsafe")
    if not parent.exists():
        parent.mkdir(mode=0o700)
    _assert_safe_ancestry(repository, receipt)
    if receipt.exists() or receipt.is_symlink():
        raise BalancedOpaqueError(
            "balanced opaque creation receipt appeared during creation"
        )
    _assert_safe_ancestry(repository, target)
    if target.exists() or target.is_symlink():
        raise BalancedOpaqueError("balanced opaque private state appeared during creation")

    fd, temporary_name = tempfile.mkstemp(prefix=".balanced-opaque-", dir=parent)
    temporary = Path(temporary_name)
    try:
        secret = secrets.token_bytes(32)
        if len(secret) != 32:
            raise BalancedOpaqueError("secure random source returned the wrong length")
        if hasattr(os, "fchmod"):
            os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        written = os.write(fd, secret)
        if written != 32:
            raise BalancedOpaqueError("private state write was incomplete")
        os.fsync(fd)
        os.close(fd)
        fd = -1
        if target.exists() or target.is_symlink():
            raise BalancedOpaqueError("balanced opaque private state appeared during creation")
        try:
            os.link(temporary, target, follow_symlinks=False)
        except FileExistsError as exc:
            raise BalancedOpaqueError(
                "balanced opaque private state appeared during creation"
            ) from exc
        os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)
        _write_private_creation_receipt_once(repository, secret, configuration)
    finally:
        if fd >= 0:
            os.close(fd)
        if temporary.exists():
            temporary.unlink()
    _assert_safe_secret_file(repository, target)
    return target


def _assert_safe_secret_file(repository: Path, path: Path) -> None:
    _assert_safe_ancestry(repository, path)
    if not path.is_file() or _is_reparse(path):
        raise BalancedOpaqueError("balanced opaque private state is missing or unsafe")
    if path.stat().st_size != 32:
        raise BalancedOpaqueError("balanced opaque private state has the wrong length")


def _validate_private_creation_receipt(
    repository: Path,
    secret: bytes,
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> str:
    path = _private_creation_receipt_path(repository, configuration)
    _assert_safe_ancestry(repository, path)
    if not path.is_file() or _is_reparse(path) or path.stat().st_size > 4096:
        raise BalancedOpaqueError("balanced opaque creation receipt is missing or unsafe")
    try:
        receipt = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        raise BalancedOpaqueError("balanced opaque creation receipt is invalid") from exc
    body = _creation_receipt_body(configuration)
    expected = hmac.new(
        secret,
        _domain(CREATION_RECEIPT_DOMAIN, configuration)
        + canonical_json_bytes(body),
        hashlib.sha256,
    ).hexdigest().upper()
    if (
        not isinstance(receipt, dict)
        or {key: value for key, value in receipt.items() if key != "receipt_hmac_sha256"}
        != body
        or not hmac.compare_digest(
            str(receipt.get("receipt_hmac_sha256", "")), expected
        )
    ):
        raise BalancedOpaqueError("balanced opaque creation receipt binding changed")
    return expected


def _private_binding_from_repository(
    repository: Path,
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> "PrivateBinding":
    path = private_secret_path(repository, configuration)
    _assert_safe_secret_file(repository.absolute(), path)
    secret = path.read_bytes()
    if len(secret) != 32:
        raise BalancedOpaqueError("balanced opaque private state has the wrong length")
    try:
        receipt_commitment = _validate_private_creation_receipt(
            repository, secret, configuration
        )
        return replace(
            PrivateBinding.from_secret(secret, configuration),
            creation_receipt_commitment=receipt_commitment,
        )
    finally:
        del secret


def _score_candidates(task: Any, indices: Sequence[int]) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for candidate in task.candidates:
        vector = tuple(
            execute_program(candidate, task.public_examples[index].x)
            == task.public_examples[index].y
            for index in indices
        )
        rows.append(
            {
                "candidate_id": candidate.candidate_id,
                "score": sum(vector),
                "pass_vector": list(vector),
            }
        )
    return tuple(rows)


def _support(rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    top = max(int(row["score"]) for row in rows)
    return tuple(str(row["candidate_id"]) for row in rows if row["score"] == top)


def _plateau_gap(rows: Sequence[Mapping[str, Any]]) -> int:
    values = [int(row["score"]) for row in rows]
    top = max(values)
    lower = [value for value in values if value < top]
    return top - max(lower) if lower else 0


def build_profile_binding(
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> tuple[dict[str, Any], str]:
    """Reconstruct the frozen profile from public data only."""
    suite = build_frozen_task_suite()
    if suite.suite_sha256 != EXPECTED_SUITE_SHA256 or len(suite.tasks) != 8:
        raise BalancedOpaqueError("frozen public suite identity drift")
    task = suite.tasks[TASK_INDEX]
    if task.task_id != TASK_ID or len(task.public_examples) != 5 or len(task.candidates) != 64:
        raise BalancedOpaqueError("balanced public task identity drift")
    projection = task.public_projection()
    if any(key in projection for key in ("hidden_examples", "answer_candidate_id")):
        raise BalancedOpaqueError("protected task data entered the public profile binding")

    branch_rows = {
        branch: _score_candidates(task, indices)
        for branch, indices in BRANCH_INDICES.items()
    }
    full_rows = _score_candidates(task, range(5))
    supports = {branch: _support(rows) for branch, rows in branch_rows.items()}
    full_support = _support(full_rows)
    if supports != EXPECTED_SUPPORTS or full_support != EXPECTED_FULL_SUPPORT:
        raise BalancedOpaqueError("balanced support geometry drift")
    for branch, rows in branch_rows.items():
        by_id = {str(row["candidate_id"]): row for row in rows}
        if max(int(row["score"]) for row in rows) != EXPECTED_TOP_SCORE:
            raise BalancedOpaqueError("balanced branch top score drift")
        if _plateau_gap(rows) != EXPECTED_PLATEAU_GAP:
            raise BalancedOpaqueError("balanced branch plateau gap drift")
        if any(
            tuple(bool(item) for item in by_id[candidate_id]["pass_vector"])
            != EXPECTED_PASS_VECTOR
            for candidate_id in supports[branch]
        ):
            raise BalancedOpaqueError("balanced branch pass equivalence drift")
    if tuple(sorted(set(supports["branch-a"]) & set(supports["branch-b"]))) != full_support:
        raise BalancedOpaqueError("balanced support intersection drift")
    if {
        branch: tuple(sorted(set(supports[branch]) - set(supports[other])))
        for branch, other in (("branch-a", "branch-b"), ("branch-b", "branch-a"))
    } != EXPECTED_EXCLUSIVES:
        raise BalancedOpaqueError("balanced exclusive support drift")

    selection_audit = {
        "source": "frozen-public-only",
        "frozen_tasks": 8,
        "ordered_shard_pairs_per_task": 30,
        "total_profiles": 240,
        "singleton_full_public_support_profiles": 240,
        "strict_relational_geometry_profiles": 26,
        "geometry_and_pass_equivalence_profiles": 26,
        "strict_current_carrier_profiles": 0,
        "balance_tie_break": [
            "equal-support-cardinality",
            "equal-plateau-gaps",
            "equal-exclusive-counts",
            "smaller-supports",
            "lower-task-index",
            "lexicographically-lower-shards",
        ],
        "selected_task_index": TASK_INDEX,
        "selected_branch_indices": {
            branch: list(indices) for branch, indices in BRANCH_INDICES.items()
        },
    }
    selection_audit["public_selection_audit_sha256"] = json_sha256(selection_audit)
    body = {
        "profile_id": configuration.profile_id,
        "task_suite_sha256": EXPECTED_SUITE_SHA256,
        "task_index": TASK_INDEX,
        "task_id": TASK_ID,
        "branch_indices": {
            branch: list(indices) for branch, indices in BRANCH_INDICES.items()
        },
        "shared_public_example_index": 2,
        "support_sets": {
            branch: list(values) for branch, values in EXPECTED_SUPPORTS.items()
        },
        "full_public_support": list(EXPECTED_FULL_SUPPORT),
        "exclusive_support": {
            branch: list(values) for branch, values in EXPECTED_EXCLUSIVES.items()
        },
        "top_scores": {"branch-a": 3, "branch-b": 3},
        "plateau_gaps": {"branch-a": 1, "branch-b": 1},
        "support_pass_vectors": {
            "branch-a": [True, True, True],
            "branch-b": [True, True, True],
        },
        "selection_audit": selection_audit,
    }
    validate_metadata_only(body)
    return body, json_sha256(body)


def secret_commitment(
    secret: bytes,
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> str:
    if len(secret) != 32:
        raise BalancedOpaqueError("private state has the wrong length")
    return sha256_bytes(_domain(SECRET_COMMITMENT_DOMAIN, configuration) + secret)


def derive_alias_mapping(
    secret: bytes,
    profile_binding_sha256: str,
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> dict[str, str]:
    if len(secret) != 32 or not SHA256_RE.fullmatch(profile_binding_sha256):
        raise BalancedOpaqueError("private alias derivation input is invalid")
    candidate_ids = tuple(f"C{index:02d}" for index in range(64))
    ordered = sorted(
        candidate_ids,
        key=lambda candidate_id: (
            hmac.new(
                secret,
                _domain(ALIAS_ORDER_DOMAIN, configuration)
                + profile_binding_sha256.encode("ascii")
                + candidate_id.encode("ascii"),
                hashlib.sha256,
            ).digest(),
            candidate_id,
        ),
    )
    return {alias: candidate_id for alias, candidate_id in zip(ALIASES, ordered)}


def derive_branch_alias_mapping(
    secret: bytes,
    profile_binding_sha256: str,
    branch_id: str,
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> dict[str, str]:
    """Derive a request-local diagnostic namespace unrelated to carrier aliases."""
    if (
        len(secret) != 32
        or not SHA256_RE.fullmatch(profile_binding_sha256)
        or branch_id not in BRANCH_INDICES
    ):
        raise BalancedOpaqueError("private branch alias derivation input is invalid")
    candidate_ids = tuple(f"C{index:02d}" for index in range(64))
    ordered = sorted(
        candidate_ids,
        key=lambda candidate_id: (
            hmac.new(
                secret,
                _domain(BRANCH_ALIAS_ORDER_DOMAIN, configuration)
                + profile_binding_sha256.encode("ascii")
                + branch_id.encode("ascii")
                + b"\0"
                + candidate_id.encode("ascii"),
                hashlib.sha256,
            ).digest(),
            candidate_id,
        ),
    )
    return {alias: candidate_id for alias, candidate_id in zip(ALIASES, ordered)}


def alias_map_commitment(
    alias_to_internal: Mapping[str, str],
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> str:
    if tuple(sorted(alias_to_internal)) != ALIASES:
        raise BalancedOpaqueError("private alias map key set changed")
    values = tuple(alias_to_internal[alias] for alias in ALIASES)
    if set(values) != {f"C{index:02d}" for index in range(64)}:
        raise BalancedOpaqueError("private alias map is not a permutation")
    mapping_bytes = canonical_json_bytes(
        {alias: alias_to_internal[alias] for alias in ALIASES}
    )
    return sha256_bytes(_domain(ALIAS_MAP_DOMAIN, configuration) + mapping_bytes)


def branch_alias_map_commitment(
    branch_id: str,
    alias_to_internal: Mapping[str, str],
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> str:
    if branch_id not in BRANCH_INDICES:
        raise BalancedOpaqueError("private branch alias map scope changed")
    if tuple(sorted(alias_to_internal)) != ALIASES:
        raise BalancedOpaqueError("private branch alias map key set changed")
    values = tuple(alias_to_internal[alias] for alias in ALIASES)
    if set(values) != {f"C{index:02d}" for index in range(64)}:
        raise BalancedOpaqueError("private branch alias map is not a permutation")
    mapping_bytes = canonical_json_bytes(
        {alias: alias_to_internal[alias] for alias in ALIASES}
    )
    return sha256_bytes(
        _domain(BRANCH_ALIAS_MAP_DOMAIN, configuration)
        + branch_id.encode("ascii")
        + b"\0"
        + mapping_bytes
    )


def derive_run_key(
    secret: bytes,
    profile_binding_sha256: str,
    run_id: str,
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> bytes:
    if run_id not in configuration.run_modes:
        raise BalancedOpaqueError("run ID is not preregistered")
    return hmac.new(
        secret,
        _domain(RUN_KEY_DOMAIN, configuration)
        + profile_binding_sha256.encode("ascii")
        + run_id.encode("ascii"),
        hashlib.sha256,
    ).digest()


def run_key_commitment(
    run_key: bytes,
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> str:
    if len(run_key) != 32:
        raise BalancedOpaqueError("run key has the wrong length")
    return sha256_bytes(_domain(RUN_KEY_COMMITMENT_DOMAIN, configuration) + run_key)


def artifact_commitment(
    run_key: bytes,
    stage_id: str,
    body: Mapping[str, Any],
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> str:
    if len(run_key) != 32 or not stage_id or "\0" in stage_id:
        raise BalancedOpaqueError("artifact commitment input is invalid")
    return hmac.new(
        run_key,
        _domain(ARTIFACT_DOMAIN, configuration)
        + stage_id.encode("ascii")
        + b"\0"
        + canonical_json_bytes(body),
        hashlib.sha256,
    ).hexdigest().upper()


def verify_artifact_commitment(
    run_key: bytes,
    stage_id: str,
    body: Mapping[str, Any],
    commitment: str,
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> bool:
    if not isinstance(commitment, str) or not SHA256_RE.fullmatch(commitment):
        return False
    expected = artifact_commitment(run_key, stage_id, body, configuration)
    return hmac.compare_digest(expected, commitment)


def _request_seed(request_id: str) -> int:
    if request_id not in REQUEST_IDS:
        raise BalancedOpaqueError("unknown balanced request")
    return int.from_bytes(
        hashlib.sha256(f"ck0-balanced-v1:{request_id}".encode("ascii")).digest()[:4],
        "big",
    )


def response_schema(request_id: str) -> dict[str, Any]:
    alias_item = {"enum": list(ALIASES), "type": "string"}
    if request_id in {"borrow", "restore"}:
        properties = {
            "accepted": {"const": True, "type": "boolean"},
            "carrier_id": {"const": CARRIER_ID, "type": "string"},
        }
        required = ["accepted", "carrier_id"]
    elif request_id in {"branch-a", "branch-b"}:
        properties = {
            "ranking": {
                "items": alias_item,
                "minItems": 1,
                "maxItems": 3,
                "type": "array",
                "uniqueItems": True,
            }
        }
        required = ["ranking"]
    elif request_id == "transform":
        properties = {
            "operator": {"enum": sorted(ALLOWED_OPERATORS), "type": "string"},
            "ranking": {
                "items": alias_item,
                "minItems": 1,
                "maxItems": 3,
                "type": "array",
                "uniqueItems": True,
            },
        }
        required = ["operator", "ranking"]
    elif request_id == "extract":
        properties = {"candidate_alias": alias_item}
        required = ["candidate_alias"]
    else:
        raise BalancedOpaqueError("unknown balanced request")
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def response_schema_hashes() -> dict[str, str]:
    return {request_id: json_sha256(response_schema(request_id)) for request_id in REQUEST_IDS}


def build_carrier() -> dict[str, Any]:
    suite = build_frozen_task_suite()
    if suite.suite_sha256 != EXPECTED_SUITE_SHA256:
        raise BalancedOpaqueError("frozen public suite identity drift")
    semantics = dict(suite.tasks[TASK_INDEX].public_projection()["semantics"])
    content = {
        "carrier_id": CARRIER_ID,
        "task_semantics": semantics,
        "candidate_aliases": list(ALIASES),
        "response_schemas": {
            request_id: response_schema(request_id) for request_id in REQUEST_IDS
        },
        "kernel_instructions": {
            "cycle": list(REQUEST_IDS),
            "law": "borrow -> transform -> extract -> restore",
            "model_authorship": [
                "diagnostic branch rankings",
                "transform operator and opaque ranking",
                "extracted opaque alias",
                "carrier acknowledgements",
            ],
            "controller_authorship": (
                "private mapping, support geometry, keyed commitments, scoring, "
                "bindings, custody, and restoration"
            ),
        },
    }
    content_sha256 = json_sha256(content)
    root_object = {**content, "carrier_content_sha256": content_sha256}
    root = canonical_json_text(root_object)
    _assert_no_internal_identity(root_object)
    return {
        "carrier_id": CARRIER_ID,
        "carrier_content_sha256": content_sha256,
        "carrier_root": root,
        "carrier_root_sha256": sha256_bytes(root.encode("utf-8")),
    }


def carrier_is_pristine(carrier: Mapping[str, Any]) -> bool:
    expected = build_carrier()
    return dict(carrier) == expected


def _assert_no_internal_identity(value: Any) -> None:
    text = canonical_json_text(value)
    if INTERNAL_CANDIDATE_RE.search(text) or TASK_ID in text:
        raise BalancedOpaqueError("internal carrier identity entered model-visible state")
    if EXPECTED_SUITE_SHA256 in text:
        raise BalancedOpaqueError("suite identity entered model-visible state")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in FORBIDDEN_MODEL_VISIBLE_KEYS:
                raise BalancedOpaqueError("forbidden field entered model-visible state")
            _assert_no_internal_identity(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_no_internal_identity(item)


def _require_alias_ranking(value: Any) -> list[str]:
    if (
        not isinstance(value, list)
        or not 1 <= len(value) <= 3
        or len(set(value)) != len(value)
        or any(alias not in ALIASES for alias in value)
    ):
        raise BalancedOpaqueError("opaque ranking is invalid")
    return [str(alias) for alias in value]


@dataclass(frozen=True, repr=False)
class PrivateBinding:
    configuration: PrivateBindingConfiguration = field(repr=False)
    profile: Mapping[str, Any] = field(repr=False)
    profile_binding_sha256: str
    alias_to_internal: Mapping[str, str] = field(repr=False)
    internal_to_alias: Mapping[str, str] = field(repr=False)
    branch_alias_to_internal: Mapping[str, Mapping[str, str]] = field(repr=False)
    run_keys: Mapping[str, bytes] = field(repr=False)
    secret_commitment: str
    alias_map_commitment: str
    branch_alias_map_commitments: Mapping[str, str]
    creation_receipt_commitment: str | None = None

    @classmethod
    def from_secret(
        cls,
        secret: bytes,
        configuration: PrivateBindingConfiguration = BINDING_1,
    ) -> "PrivateBinding":
        profile, profile_sha256 = build_profile_binding(configuration)
        alias_to_internal = derive_alias_mapping(
            secret, profile_sha256, configuration
        )
        internal_to_alias = {
            internal: alias for alias, internal in alias_to_internal.items()
        }
        branch_alias_to_internal = {
            branch_id: derive_branch_alias_mapping(
                secret, profile_sha256, branch_id, configuration
            )
            for branch_id in BRANCH_INDICES
        }
        run_keys = {
            run_id: derive_run_key(
                secret, profile_sha256, run_id, configuration
            )
            for run_id in configuration.run_modes
        }
        return cls(
            configuration=configuration,
            profile=profile,
            profile_binding_sha256=profile_sha256,
            alias_to_internal=alias_to_internal,
            internal_to_alias=internal_to_alias,
            branch_alias_to_internal=branch_alias_to_internal,
            run_keys=run_keys,
            secret_commitment=secret_commitment(secret, configuration),
            alias_map_commitment=alias_map_commitment(
                alias_to_internal, configuration
            ),
            branch_alias_map_commitments={
                branch_id: branch_alias_map_commitment(
                    branch_id, mapping, configuration
                )
                for branch_id, mapping in branch_alias_to_internal.items()
            },
        )

    def __repr__(self) -> str:
        return "PrivateBinding(<redacted>)"

    def run_key(self, run_id: str) -> bytes:
        try:
            return self.run_keys[run_id]
        except KeyError as exc:
            raise BalancedOpaqueError("run ID is not preregistered") from exc


class BalancedOpaqueRuntime:
    """Pure carrier/request hooks consumed by the existing CK0 lifecycle."""

    def __init__(
        self,
        *,
        repository: Path,
        run_id: str,
        private: PrivateBinding,
        preregistration: Mapping[str, Any] | None = None,
    ) -> None:
        configuration = private.configuration
        if run_id not in configuration.run_modes:
            raise BalancedOpaqueError("run ID is not preregistered")
        self.repository = repository.absolute()
        self.run_id = run_id
        self.configuration = configuration
        self.mode = configuration.run_modes[run_id]
        self.private = private
        self.run_key = private.run_key(run_id)
        self.carrier = build_carrier()
        self.preregistration = dict(preregistration or {})

    def carrier_is_pristine(self, carrier: Mapping[str, Any]) -> bool:
        return carrier_is_pristine(carrier)

    @classmethod
    def from_repository(
        cls,
        repository: Path,
        run_id: str,
        *,
        require_final_preregistration: bool = True,
    ) -> "BalancedOpaqueRuntime":
        configuration = binding_configuration_for_run(run_id)
        private = _private_binding_from_repository(repository, configuration)
        preregistration = validate_preregistration(
            repository,
            private,
            run_id=run_id,
            require_final=require_final_preregistration,
            configuration=configuration,
        )
        return cls(
            repository=repository,
            run_id=run_id,
            private=private,
            preregistration=preregistration,
        )

    def _branch_assignment(self, request_id: str) -> dict[str, Any]:
        if request_id not in BRANCH_INDICES:
            raise BalancedOpaqueError("unknown branch request")
        task = build_frozen_task_suite().tasks[TASK_INDEX]
        evidence = [
            task.public_examples[index].to_dict()
            for index in BRANCH_INDICES[request_id]
        ]
        by_id = {candidate.candidate_id: candidate for candidate in task.candidates}
        programs = []
        for alias in ALIASES:
            candidate = by_id[self.private.branch_alias_to_internal[request_id][alias]]
            programs.append(
                {
                    "candidate_alias": alias,
                    "branch_local_program": {
                        "kind": "sealed-extensional-projection-v1",
                        "ordered_outputs": [
                            execute_program(candidate, task.public_examples[index].x)
                            for index in BRANCH_INDICES[request_id]
                        ],
                    },
                }
            )
        return {
            "stage": "branch",
            "artifact_role": PARENT_ROLES[request_id],
            "alias_scope": "request-local-diagnostic",
            "instruction": (
                "Rank one to three request-local opaque candidates using only this "
                "evidence and the sealed branch-local program projections."
            ),
            "evidence": evidence,
            "candidate_programs": programs,
        }

    def deletion_receipt(self, artifact: Mapping[str, Any]) -> dict[str, Any]:
        self.verify_branch_artifact(artifact)
        receipt = {
            "artifact_role": artifact["artifact_role"],
            "artifact_commitment": artifact["artifact_commitment"],
            "projection_mode": "commitment-only",
            "informative_content_withheld": True,
        }
        if set(receipt) != DELETION_RECEIPT_FIELDS:
            raise BalancedOpaqueError("deletion receipt field set changed")
        _assert_no_internal_identity(receipt)
        return receipt

    def assignment(
        self,
        request_id: str,
        artifacts: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        if request_id == "borrow":
            return {
                "stage": "borrow",
                "carrier_id": CARRIER_ID,
                "instruction": "Acknowledge the immutable opaque carrier exactly.",
            }
        if request_id in BRANCH_INDICES:
            return self._branch_assignment(request_id)
        if request_id == "transform":
            if not all(branch in artifacts for branch in BRANCH_INDICES):
                raise BalancedOpaqueError("balanced transform parents are incomplete")
            parents = [artifacts["branch-a"], artifacts["branch-b"]]
            deleted = DELETED_PARENT_BY_MODE.get(self.mode)
            if deleted is not None:
                index = 0 if deleted == "parent-0" else 1
                parents[index] = self.deletion_receipt(parents[index])
            assignment = {
                "stage": "transform",
                "instruction": (
                    "Operate only on the supplied opaque parent relations. Author one "
                    "allowed operator and one opaque candidate ranking."
                ),
                "parent_artifacts": parents,
            }
            self.validate_transform_assignment(assignment)
            return assignment
        if request_id == "extract":
            transform = artifacts.get("transform")
            if not isinstance(transform, Mapping):
                raise BalancedOpaqueError("balanced extraction parent is missing")
            self.verify_transform_artifact(transform)
            return {
                "stage": "extract",
                "instruction": "Select one opaque candidate from the supplied ranking.",
                "transform_artifact": {
                    "ranking": list(transform["ranking"]),
                    "artifact_commitment": transform["artifact_commitment"],
                },
            }
        if request_id == "restore":
            return {
                "stage": "restore",
                "carrier_id": CARRIER_ID,
                "instruction": "Acknowledge the original immutable opaque carrier only.",
            }
        raise BalancedOpaqueError("unknown balanced request")

    def build_model_request(
        self,
        request_id: str,
        artifacts: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        assignment = self.assignment(request_id, artifacts)
        payload = {
            "model": MODEL_ALIAS,
            "messages": [
                {"role": "system", "content": self.carrier["carrier_root"]},
                {"role": "user", "content": canonical_json_text(assignment)},
            ],
            "temperature": 0.0,
            "seed": _request_seed(request_id),
            "max_tokens": 64,
            "stream": True,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": f"ck0_balanced_{request_id.replace('-', '_')}",
                    "strict": True,
                    "schema": response_schema(request_id),
                },
            },
            "stream_options": {"include_usage": True},
            "cache_prompt": True,
            "return_tokens": True,
            "return_progress": True,
            "verbose": True,
        }
        self.validate_model_request(request_id, payload, artifacts)
        return payload

    def validate_model_request(
        self,
        request_id: str,
        payload: Mapping[str, Any],
        artifacts: Mapping[str, Mapping[str, Any]],
    ) -> None:
        if not carrier_is_pristine(self.carrier):
            raise BalancedOpaqueError("balanced carrier root is not pristine")
        messages = payload.get("messages")
        if not isinstance(messages, list) or len(messages) != 2:
            raise BalancedOpaqueError("balanced model request message shape changed")
        if messages[0] != {"role": "system", "content": self.carrier["carrier_root"]}:
            raise BalancedOpaqueError("balanced model request changed the immutable root")
        try:
            assignment = json.loads(messages[1]["content"])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise BalancedOpaqueError("balanced model assignment is invalid") from exc
        if assignment != self.assignment(request_id, artifacts):
            raise BalancedOpaqueError("balanced model assignment differs from its projection")
        if request_id == "transform":
            self.validate_transform_assignment(assignment)
        if request_id == "extract":
            if set(assignment) != {"stage", "instruction", "transform_artifact"}:
                raise BalancedOpaqueError("extraction received extra model-visible state")
        if payload.get("chat_template_kwargs") != {"enable_thinking": False}:
            raise BalancedOpaqueError("balanced requests must remain thinking-disabled")
        _assert_no_internal_identity(payload)
        validate_metadata_only(assignment)

    def parse_response(
        self,
        request_id: str,
        text: str,
        *,
        transform_artifact: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise BalancedOpaqueError("balanced response is invalid JSON") from exc
        if not isinstance(value, dict):
            raise BalancedOpaqueError("balanced response is not an object")
        if request_id in {"borrow", "restore"}:
            if value != {"accepted": True, "carrier_id": CARRIER_ID}:
                raise BalancedOpaqueError("balanced carrier acknowledgement is invalid")
        elif request_id in {"branch-a", "branch-b"}:
            if set(value) != {"ranking"}:
                raise BalancedOpaqueError("balanced branch response field set changed")
            value["ranking"] = _require_alias_ranking(value["ranking"])
        elif request_id == "transform":
            if set(value) != {"operator", "ranking"} or value.get("operator") not in ALLOWED_OPERATORS:
                raise BalancedOpaqueError("balanced transform response is invalid")
            value["ranking"] = _require_alias_ranking(value["ranking"])
        elif request_id == "extract":
            if set(value) != {"candidate_alias"} or value.get("candidate_alias") not in ALIASES:
                raise BalancedOpaqueError("balanced extraction response is invalid")
            if (
                not isinstance(transform_artifact, Mapping)
                or value["candidate_alias"] not in transform_artifact.get("ranking", [])
            ):
                raise BalancedOpaqueError("extraction alias is absent from transform ranking")
        else:
            raise BalancedOpaqueError("unknown balanced request")
        _assert_no_internal_identity(value)
        validate_metadata_only(value)
        return value

    def normalize_branch(self, request_id: str, ranking: Sequence[str]) -> dict[str, Any]:
        _require_alias_ranking(list(ranking))
        support = sorted(
            self.private.internal_to_alias[candidate_id]
            for candidate_id in EXPECTED_SUPPORTS[request_id]
        )
        body = {
            "artifact_role": PARENT_ROLES[request_id],
            "support_aliases": support,
            "tied_top_score": {"passed": 3, "total": 3},
            "pass_equivalence_class": "all-three-public-examples-pass",
        }
        artifact = {
            **body,
            "artifact_commitment": artifact_commitment(
                self.run_key,
                PARENT_ROLES[request_id],
                body,
                self.configuration,
            ),
        }
        self.verify_branch_artifact(artifact)
        return artifact

    def verify_branch_artifact(self, artifact: Mapping[str, Any]) -> None:
        if set(artifact) != BRANCH_ARTIFACT_FIELDS:
            raise BalancedOpaqueError("normalized branch artifact field set changed")
        role = artifact.get("artifact_role")
        if role not in PARENT_ROLES.values():
            raise BalancedOpaqueError("normalized branch artifact role is invalid")
        support = artifact.get("support_aliases")
        if (
            not isinstance(support, list)
            or len(support) != 5
            or support != sorted(support)
            or len(set(support)) != 5
            or any(alias not in ALIASES for alias in support)
        ):
            raise BalancedOpaqueError("normalized opaque support is invalid")
        if artifact.get("tied_top_score") != {"passed": 3, "total": 3}:
            raise BalancedOpaqueError("normalized tied score changed")
        if artifact.get("pass_equivalence_class") != "all-three-public-examples-pass":
            raise BalancedOpaqueError("normalized pass equivalence class changed")
        body = {key: artifact[key] for key in artifact if key != "artifact_commitment"}
        if not verify_artifact_commitment(
            self.run_key,
            str(role),
            body,
            str(artifact.get("artifact_commitment")),
            self.configuration,
        ):
            raise BalancedOpaqueError("normalized branch artifact commitment is invalid")
        _assert_no_internal_identity(artifact)

    def validate_transform_assignment(self, assignment: Mapping[str, Any]) -> dict[str, Any]:
        if set(assignment) != {"stage", "instruction", "parent_artifacts"}:
            raise BalancedOpaqueError("balanced transform assignment field set changed")
        if assignment.get("stage") != "transform":
            raise BalancedOpaqueError("balanced transform stage changed")
        parents = assignment.get("parent_artifacts")
        if not isinstance(parents, list) or len(parents) != 2:
            raise BalancedOpaqueError("balanced transform parent count changed")
        roles = []
        receipt_count = 0
        for parent in parents:
            if not isinstance(parent, Mapping):
                raise BalancedOpaqueError("balanced transform parent is invalid")
            roles.append(parent.get("artifact_role"))
            if set(parent) == BRANCH_ARTIFACT_FIELDS:
                self.verify_branch_artifact(parent)
            elif set(parent) == DELETION_RECEIPT_FIELDS:
                receipt_count += 1
                if (
                    parent.get("projection_mode") != "commitment-only"
                    or parent.get("informative_content_withheld") is not True
                    or not isinstance(parent.get("artifact_commitment"), str)
                    or not SHA256_RE.fullmatch(parent["artifact_commitment"])
                ):
                    raise BalancedOpaqueError("balanced deletion receipt is invalid")
            else:
                raise BalancedOpaqueError("balanced transform parent exposes extra state")
        if roles != ["parent-0", "parent-1"]:
            raise BalancedOpaqueError("balanced transform parent ordering changed")
        expected_receipts = 0 if self.mode == "full-information" else 1
        if receipt_count != expected_receipts:
            raise BalancedOpaqueError("balanced transform deletion geometry changed")
        deleted = DELETED_PARENT_BY_MODE.get(self.mode)
        if deleted is not None:
            for parent in parents:
                if parent.get("artifact_role") == deleted and set(parent) != DELETION_RECEIPT_FIELDS:
                    raise BalancedOpaqueError("deleted parent informative state remained visible")
        _assert_no_internal_identity(assignment)
        projection = {
            "mode": self.mode,
            "parent_roles": roles,
            "complete_parent_count": 2 - receipt_count,
            "commitment_only_parent_count": receipt_count,
            "projection_verified": True,
        }
        validate_metadata_only(projection)
        return projection

    def normalize_transform(self, operator: str, ranking: Sequence[str]) -> dict[str, Any]:
        if operator not in ALLOWED_OPERATORS:
            raise BalancedOpaqueError("balanced transform operator is invalid")
        normalized_ranking = _require_alias_ranking(list(ranking))
        body = {"operator": operator, "ranking": normalized_ranking}
        artifact = {
            **body,
            "artifact_commitment": artifact_commitment(
                self.run_key, "transform", body, self.configuration
            ),
        }
        self.verify_transform_artifact(artifact)
        return artifact

    def verify_transform_artifact(self, artifact: Mapping[str, Any]) -> None:
        if set(artifact) != TRANSFORM_ARTIFACT_FIELDS:
            raise BalancedOpaqueError("balanced transform artifact field set changed")
        if artifact.get("operator") not in ALLOWED_OPERATORS:
            raise BalancedOpaqueError("balanced transform artifact operator is invalid")
        _require_alias_ranking(artifact.get("ranking"))
        body = {"operator": artifact["operator"], "ranking": artifact["ranking"]}
        if not verify_artifact_commitment(
            self.run_key,
            "transform",
            body,
            str(artifact.get("artifact_commitment")),
            self.configuration,
        ):
            raise BalancedOpaqueError("balanced transform artifact commitment is invalid")
        _assert_no_internal_identity(artifact)

    def normalize_extraction(
        self,
        candidate_alias: str,
        transform: Mapping[str, Any],
    ) -> dict[str, Any]:
        self.verify_transform_artifact(transform)
        if candidate_alias not in transform["ranking"]:
            raise BalancedOpaqueError("extraction alias is absent from transform ranking")
        task = build_frozen_task_suite().tasks[TASK_INDEX]
        internal = self.private.alias_to_internal[candidate_alias]
        candidate = next(item for item in task.candidates if item.candidate_id == internal)
        score = sum(
            execute_program(candidate, example.x) == example.y
            for example in task.public_examples
        )
        visible_body = {
            "candidate_alias": candidate_alias,
            "transform_artifact_commitment_consumed": transform["artifact_commitment"],
        }
        controller_private_evaluation = {
                "mapped_to_full_public_support": internal == EXPECTED_FULL_SUPPORT[0],
                "full_public_score": score,
                "full_public_total": 5,
        }
        commitment_body = {
            **visible_body,
            "controller_private_evaluation": controller_private_evaluation,
        }
        artifact = {
            **commitment_body,
            "artifact_commitment": artifact_commitment(
                self.run_key,
                "extract",
                commitment_body,
                self.configuration,
            ),
        }
        self.verify_extraction_artifact(artifact, transform)
        validate_metadata_only(artifact)
        return artifact

    def verify_extraction_artifact(
        self,
        artifact: Mapping[str, Any],
        transform: Mapping[str, Any],
    ) -> None:
        self.verify_transform_artifact(transform)
        if set(artifact) != EXTRACTION_ARTIFACT_FIELDS:
            raise BalancedOpaqueError("balanced extraction artifact field set changed")
        candidate_alias = artifact.get("candidate_alias")
        if candidate_alias not in transform["ranking"]:
            raise BalancedOpaqueError("balanced extraction alias is absent from transform")
        if (
            artifact.get("transform_artifact_commitment_consumed")
            != transform["artifact_commitment"]
        ):
            raise BalancedOpaqueError("balanced extraction parent binding changed")
        task = build_frozen_task_suite().tasks[TASK_INDEX]
        internal = self.private.alias_to_internal[str(candidate_alias)]
        candidate = next(item for item in task.candidates if item.candidate_id == internal)
        score = sum(
            execute_program(candidate, example.x) == example.y
            for example in task.public_examples
        )
        expected_evaluation = {
            "mapped_to_full_public_support": internal == EXPECTED_FULL_SUPPORT[0],
            "full_public_score": score,
            "full_public_total": 5,
        }
        if artifact.get("controller_private_evaluation") != expected_evaluation:
            raise BalancedOpaqueError("balanced private extraction evaluation changed")
        commitment_body = {
            "candidate_alias": candidate_alias,
            "transform_artifact_commitment_consumed": transform["artifact_commitment"],
            "controller_private_evaluation": expected_evaluation,
        }
        if not verify_artifact_commitment(
            self.run_key,
            "extract",
            commitment_body,
            str(artifact.get("artifact_commitment")),
            self.configuration,
        ):
            raise BalancedOpaqueError("balanced extraction artifact commitment is invalid")
        _assert_no_internal_identity(artifact)

    def classify(
        self,
        artifacts: Mapping[str, Mapping[str, Any]],
        *,
        completed_request_count: int,
        restoration_passed: bool,
    ) -> str:
        inconclusive = (
            "INCONCLUSIVE"
            if self.mode == "full-information"
            else "CAUSAL_CONTROL_INCONCLUSIVE"
        )
        if completed_request_count != 6 or not restoration_passed:
            return inconclusive
        try:
            branch_a = artifacts["branch-a"]
            branch_b = artifacts["branch-b"]
            transform = artifacts["transform"]
            extraction = artifacts["extract"]
            self.verify_branch_artifact(branch_a)
            self.verify_branch_artifact(branch_b)
            self.verify_transform_artifact(transform)
            self.verify_extraction_artifact(extraction, transform)
        except (KeyError, BalancedOpaqueError):
            return inconclusive
        winner_alias = self.private.internal_to_alias[EXPECTED_FULL_SUPPORT[0]]
        selected_alias = extraction.get("candidate_alias")
        selected_private = extraction.get("controller_private_evaluation", {})
        correct = all(
            (
                transform["ranking"][0] == winner_alias,
                selected_alias == winner_alias,
                selected_private.get("mapped_to_full_public_support") is True,
                selected_private.get("full_public_score") == 5,
                selected_private.get("full_public_total") == 5,
            )
        )
        if self.mode == "full-information":
            intersection = set(branch_a["support_aliases"]) & set(branch_b["support_aliases"])
            geometry = all(
                (
                    len(branch_a["support_aliases"]) == 5,
                    len(branch_b["support_aliases"]) == 5,
                    intersection == {winner_alias},
                )
            )
            return (
                "BALANCED_OPAQUE_RELATIONAL_VISIBLE"
                if geometry and correct
                else "BALANCED_OPAQUE_RELATIONAL_COLLAPSED"
            )
        if self.mode == "delete-parent-0":
            return (
                "PARENT_A_UNAIDED_EXCHANGEABLE_HIT"
                if correct
                else "PARENT_A_INFORMATION_DEPENDENCE_SUPPORTED"
            )
        return (
            "PARENT_B_UNAIDED_EXCHANGEABLE_HIT"
            if correct
            else "PARENT_B_INFORMATION_DEPENDENCE_SUPPORTED"
        )

    def build_result_projection(
        self,
        *,
        implementation_sha: str | None,
        preflight: Mapping[str, Any],
        cib0_snapshot: Mapping[str, Any],
        ck0_snapshot: Mapping[str, Any],
        readiness: Mapping[str, Any] | None,
        outcomes: Sequence[Mapping[str, Any]],
        artifacts: Mapping[str, Mapping[str, Any]],
        completed_responses: int,
        cleanup: Mapping[str, Any],
        postflight: Mapping[str, Any],
        lease: Mapping[str, Any],
        restoration: Mapping[str, Any] | None,
        failure: Mapping[str, Any] | None,
        intervention: Mapping[str, Any] | None,
        claims: Mapping[str, Any],
    ) -> dict[str, Any]:
        restoration_passed = (
            isinstance(restoration, Mapping) and restoration.get("passed") is True
        )
        classification = self.classify(
            artifacts,
            completed_request_count=len(outcomes),
            restoration_passed=restoration_passed,
        )
        inconclusive = (
            "INCONCLUSIVE"
            if self.mode == "full-information"
            else "CAUSAL_CONTROL_INCONCLUSIVE"
        )
        complete = (
            len(outcomes) == 6
            and completed_responses == 6
            and failure is None
            and classification != inconclusive
        )
        result = {
            "schema_version": 1,
            "kernel_id": "catalytic-kernel-0",
            "carrier_profile": self.configuration.profile_id,
            "run_id": self.run_id,
            "run_mode": self.mode,
            "implementation_sha": implementation_sha,
            "status": "complete" if complete else "failed",
            "balanced_classification": classification if complete else inconclusive,
            "carrier": {
                "carrier_id": self.carrier["carrier_id"],
                "carrier_content_sha256": self.carrier["carrier_content_sha256"],
                "carrier_root_sha256": self.carrier["carrier_root_sha256"],
            },
            "preregistration": dict(self.preregistration),
            "historical_cib0": dict(cib0_snapshot),
            "historical_ck0": dict(ck0_snapshot),
            "preflight": dict(preflight),
            "readiness": dict(readiness) if isinstance(readiness, Mapping) else None,
            "request_count_required": 6,
            "completed_model_responses": completed_responses,
            "request_outcomes": [dict(item) for item in outcomes],
            "branch_a": artifacts.get("branch-a"),
            "branch_b": artifacts.get("branch-b"),
            "transform": artifacts.get("transform"),
            "extraction": artifacts.get("extract"),
            "control_intervention": dict(intervention) if isinstance(intervention, Mapping) else None,
            "restoration": dict(restoration) if isinstance(restoration, Mapping) else None,
            "lease_accounting": dict(lease),
            "cleanup": dict(cleanup),
            "postflight_custody": dict(postflight),
            "failure": dict(failure) if isinstance(failure, Mapping) else None,
            "persistence_mode": "bounded-normalized-metadata-only",
            "transport_retention": "none",
            "claims": dict(claims),
            "claiming": False,
            "automatic_promotion": False,
        }
        validate_metadata_only(result)
        return result


def implementation_binding(repository: Path, relative_paths: Sequence[str]) -> dict[str, Any]:
    files = []
    for relative in sorted(set(relative_paths)):
        path = repository / relative
        if not path.is_file() or path.is_symlink():
            raise BalancedOpaqueError("implementation source is missing or unsafe")
        files.append({"path": relative, "sha256": _normalized_text_sha256(path)})
    body = {"kind": "normalized-source-bundle-sha256-v1", "files": files}
    return {**body, "sha256": json_sha256(body)}


def _internal_to_branch_alias(
    private: PrivateBinding,
    branch_id: str,
) -> dict[str, str]:
    return {
        internal: alias
        for alias, internal in private.branch_alias_to_internal[branch_id].items()
    }


def binding_independence_checks(
    binding_1: PrivateBinding,
    binding_2: PrivateBinding,
    *,
    roots_differ: bool,
) -> dict[str, bool]:
    if binding_1.configuration is not BINDING_1 or binding_2.configuration is not BINDING_2:
        raise BalancedOpaqueError("binding independence comparison scope changed")
    binding_1_runs = {
        run_key_commitment(binding_1.run_key(run_id), BINDING_1)
        for run_id in BINDING_1.run_modes
    }
    binding_2_runs = {
        run_key_commitment(binding_2.run_key(run_id), BINDING_2)
        for run_id in BINDING_2.run_modes
    }
    binding_1_commitments = {
        binding_1.secret_commitment,
        binding_1.alias_map_commitment,
        *binding_1.branch_alias_map_commitments.values(),
        *binding_1_runs,
        binding_1.creation_receipt_commitment,
    }
    binding_2_commitments = {
        binding_2.secret_commitment,
        binding_2.alias_map_commitment,
        *binding_2.branch_alias_map_commitments.values(),
        *binding_2_runs,
        binding_2.creation_receipt_commitment,
    }
    winner = EXPECTED_FULL_SUPPORT[0]
    checks = {
        "private_root_differs": roots_differ,
        "root_commitment_differs": (
            binding_2.secret_commitment != binding_1.secret_commitment
        ),
        "canonical_alias_map_commitment_differs": (
            binding_2.alias_map_commitment != binding_1.alias_map_commitment
        ),
        "complete_canonical_alias_map_differs": (
            dict(binding_2.alias_to_internal) != dict(binding_1.alias_to_internal)
        ),
        "private_singleton_opaque_alias_differs": (
            binding_2.internal_to_alias[winner]
            != binding_1.internal_to_alias[winner]
        ),
        "parent_0_ordered_opaque_support_tuple_differs": (
            tuple(sorted(binding_2.internal_to_alias[item] for item in EXPECTED_SUPPORTS["branch-a"]))
            != tuple(sorted(binding_1.internal_to_alias[item] for item in EXPECTED_SUPPORTS["branch-a"]))
        ),
        "parent_1_ordered_opaque_support_tuple_differs": (
            tuple(sorted(binding_2.internal_to_alias[item] for item in EXPECTED_SUPPORTS["branch-b"]))
            != tuple(sorted(binding_1.internal_to_alias[item] for item in EXPECTED_SUPPORTS["branch-b"]))
        ),
        "parent_0_branch_presentation_commitment_differs": (
            binding_2.branch_alias_map_commitments["branch-a"]
            != binding_1.branch_alias_map_commitments["branch-a"]
        ),
        "parent_1_branch_presentation_commitment_differs": (
            binding_2.branch_alias_map_commitments["branch-b"]
            != binding_1.branch_alias_map_commitments["branch-b"]
        ),
        "private_singleton_parent_0_presentation_differs": (
            _internal_to_branch_alias(binding_2, "branch-a")[winner]
            != _internal_to_branch_alias(binding_1, "branch-a")[winner]
        ),
        "private_singleton_parent_1_presentation_differs": (
            _internal_to_branch_alias(binding_2, "branch-b")[winner]
            != _internal_to_branch_alias(binding_1, "branch-b")[winner]
        ),
        "all_three_run_key_commitments_differ_from_binding_1": (
            binding_2_runs.isdisjoint(binding_1_runs)
        ),
        "binding_2_run_key_commitments_pairwise_distinct": (
            len(binding_2_runs) == 3
        ),
        "no_binding_1_commitment_reused": (
            binding_2_commitments.isdisjoint(binding_1_commitments)
        ),
    }
    if not all(checks.values()):
        raise BalancedOpaqueError("binding independence gate failed; resampling forbidden")
    return checks


def _payload_invariant_projection(
    request_id: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    projection = json.loads(canonical_json_text(payload))
    assignment = json.loads(projection["messages"][1]["content"])
    if request_id in BRANCH_INDICES:
        for item in assignment["candidate_programs"]:
            item["branch_local_program"]["ordered_outputs"] = [
                "<binding-local-extensional-value>"
            ] * 3
    elif request_id == "transform":
        for parent in assignment["parent_artifacts"]:
            parent["artifact_commitment"] = "<binding-and-run-local-commitment>"
            if "support_aliases" in parent:
                parent["support_aliases"] = ["<binding-local-support>"] * 5
    elif request_id == "extract":
        assignment["transform_artifact"]["ranking"] = [
            "<binding-local-ranking>"
        ] * len(assignment["transform_artifact"]["ranking"])
        assignment["transform_artifact"]["artifact_commitment"] = (
            "<binding-and-run-local-commitment>"
        )
    projection["messages"][1]["content"] = canonical_json_text(assignment)
    _assert_no_internal_identity(projection)
    return projection


def static_payload_invariance_report(
    binding_1: PrivateBinding,
    binding_2: PrivateBinding,
) -> dict[str, Any]:
    forbidden_binding_values = {
        BINDING_2.profile_id,
        binding_1.profile_binding_sha256,
        binding_2.profile_binding_sha256,
        binding_1.secret_commitment,
        binding_2.secret_commitment,
        binding_1.alias_map_commitment,
        binding_2.alias_map_commitment,
        *binding_1.branch_alias_map_commitments.values(),
        *binding_2.branch_alias_map_commitments.values(),
        *(
            run_key_commitment(binding_1.run_key(run_id), BINDING_1)
            for run_id in BINDING_1.run_modes
        ),
        *(
            run_key_commitment(binding_2.run_key(run_id), BINDING_2)
            for run_id in BINDING_2.run_modes
        ),
    }
    if binding_1.creation_receipt_commitment is not None:
        forbidden_binding_values.add(binding_1.creation_receipt_commitment)
    if binding_2.creation_receipt_commitment is not None:
        forbidden_binding_values.add(binding_2.creation_receipt_commitment)
    by_mode: dict[str, Any] = {}
    for mode in ("full-information", "delete-parent-0", "delete-parent-1"):
        run_1 = next(run for run, value in BINDING_1.run_modes.items() if value == mode)
        run_2 = next(run for run, value in BINDING_2.run_modes.items() if value == mode)
        payloads_1 = _static_model_visible_payloads_from_private(binding_1, run_1)
        payloads_2 = _static_model_visible_payloads_from_private(binding_2, run_2)
        stage_hashes: dict[str, str] = {}
        for request_id in REQUEST_IDS:
            projected_1 = _payload_invariant_projection(request_id, payloads_1[request_id])
            projected_2 = _payload_invariant_projection(request_id, payloads_2[request_id])
            if projected_1 != projected_2:
                raise BalancedOpaqueError("cross-binding model-visible invariant changed")
            stage_hashes[request_id] = json_sha256(projected_1)
            payload_text_1 = canonical_json_text(payloads_1[request_id])
            payload_text_2 = canonical_json_text(payloads_2[request_id])
            for forbidden in forbidden_binding_values:
                if forbidden in payload_text_1 or forbidden in payload_text_2:
                    raise BalancedOpaqueError("private binding identity entered a model payload")
        by_mode[mode] = {
            "status": "pass",
            "invariant_projection_sha256": stage_hashes,
        }
    report = {
        "status": "pass",
        "modes": by_mode,
        "immutable_carrier_root_exact": (
            build_carrier()["carrier_root_sha256"]
            == "E66846DC5097C5E9D6CFE5DC8679660CC193648DAE7A555AAA2587BE8A371033"
        ),
        "schemas_exact": response_schema_hashes(),
        "request_seeds_exact": {
            request_id: _request_seed(request_id) for request_id in REQUEST_IDS
        },
        "request_order_exact": list(REQUEST_IDS),
        "parent_order_exact": ["parent-0", "parent-1"],
        "temperature_exact": 0.0,
        "thinking_setting_exact": {"enable_thinking": False},
        "prompt_and_instruction_identity_bound_by_invariant_projection": True,
        "deletion_receipt_fields_exact": sorted(DELETION_RECEIPT_FIELDS),
        "extraction_boundary_exact": [
            "stage",
            "instruction",
            "transform_artifact",
        ],
        "restoration_boundary_exact": "original-immutable-carrier-only",
        "binding_identity_model_visible": False,
        "cross_binding_correspondence_table_persisted": False,
        "allowed_differences_only": True,
    }
    validate_metadata_only(report)
    return report


def build_preregistration_document(
    *,
    repository: Path,
    implementation_paths: Sequence[str],
    audit_outcomes: Mapping[str, str] | None = None,
    static_verification: Mapping[str, Any] | None = None,
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> dict[str, Any]:
    private = _private_binding_from_repository(repository, configuration)
    carrier = build_carrier()
    run_bindings = []
    for run_id, mode in configuration.run_modes.items():
        key = private.run_key(run_id)
        item = {
            "run_id": run_id,
            "mode": mode,
            "run_key_commitment": run_key_commitment(key, configuration),
            "authorized_invocations": (
                1 if configuration is BINDING_1 else 0
            ),
            "retry_count": 0,
        }
        if configuration is BINDING_2:
            item["reservation_state"] = "reserved-unconsumed"
            item["authorization_state"] = (
                "separately-authorizable"
                if mode == "full-information"
                else "unauthorized-until-full-terminal-visible"
            )
        run_bindings.append(item)
    schemas = response_schema_hashes()
    document = {
        "schema_version": 1,
        "status": "static-preregistered",
        "protected_starting_sha": configuration.protected_starting_sha,
        "implementation_binding": implementation_binding(
            repository, implementation_paths
        ),
        "visibility_legend": {
            "controller_private_preregistered": (
                "committed controller-only binding; forbidden from every model request"
            ),
            "model_visible": "exact bounded content allowed in model requests",
            "forbidden_from_model": "must fail closed if present in a model request",
        },
        "profile_binding": {
            "visibility": "controller_private_preregistered",
            "profile_binding_sha256": private.profile_binding_sha256,
            **private.profile,
        },
        "private_state": {
            "visibility": "forbidden_from_model",
            "relative_path": configuration.secret_path,
            "size_bytes": 32,
            "generation_law": {
                "source": "secrets.token_bytes",
                "requested_bytes": 32,
                "create_mode": "exclusive-once-atomic-publish",
                "existing_file_policy": "fail-closed",
            },
            "creation_receipt": {
                "relative_path": configuration.creation_receipt_path,
                "receipt_hmac_sha256": private.creation_receipt_commitment,
                "committed": False,
            },
            "secret_commitment": private.secret_commitment,
            "alias_map_commitment": private.alias_map_commitment,
            "branch_alias_map_commitments": dict(
                private.branch_alias_map_commitments
            ),
            "secret_committed": False,
            "alias_map_committed": False,
        },
        "future_runs": {
            "visibility": "controller_private_preregistered",
            "runs": run_bindings,
            "next_separately_authorized_live_action": next(
                run_id
                for run_id, mode in configuration.run_modes.items()
                if mode == "full-information"
            ),
            "deletion_controls_locked_until_full_terminal_visible": True,
        },
        "model_visible_carrier": {
            "visibility": "model_visible",
            "carrier_id": CARRIER_ID,
            "carrier_content_sha256": carrier["carrier_content_sha256"],
            "carrier_root_sha256": carrier["carrier_root_sha256"],
            "allowed_root_content": [
                "generic carrier identity",
                "abstract task DSL semantics",
                "opaque aliases K00 through K63",
                "strict response schemas",
                "six-stage lifecycle law",
                "model/controller authorship boundary",
            ],
        },
        "response_schemas": {
            "visibility": "model_visible",
            "sha256": schemas,
        },
        "request_seeds": {
            "visibility": "controller_private_preregistered",
            "values": {request_id: _request_seed(request_id) for request_id in REQUEST_IDS},
        },
        "runtime_identities": {
            "visibility": "controller_private_preregistered",
            "model": dict(MODEL_IDENTITY),
            "binary": dict(BINARY_IDENTITY),
            "physical_slots": 1,
            "sidecar_epochs": 1,
            "deep_requests": 0,
            "automatic_promotion": False,
        },
        "classification_law": {
            "visibility": "controller_private_preregistered",
            "full_information": list(FULL_CLASSIFICATIONS),
            "delete_parent_0": list(DELETE_A_CLASSIFICATIONS),
            "delete_parent_1": list(DELETE_B_CLASSIFICATIONS),
            "bilateral_status": (
                "BILATERAL_PARENT_INFORMATION_DEPENDENCE_SUPPORTED_ON_BALANCED_OPAQUE_CARRIER"
            ),
            "bilateral_requires": [
                "full-information-visible",
                "parent-0-deletion-dependence-supported",
                "parent-1-deletion-dependence-supported",
                "all-three-runs-safely-terminal",
                "no-private-mapping-or-winner-leakage",
                "restoration-passed-in-all-three-runs",
            ],
        },
        "disclosure_law": {
            "visibility": "controller_private_preregistered",
            "automatic_disclosure": False,
            "terminal_condition": list(configuration.run_modes),
            "alternative": "explicit-user-retirement",
        },
        "audits": {
            "carrier_leakage_auditor": (audit_outcomes or {}).get(
                "carrier_leakage_auditor", "pending"
            ),
            "private_commitment_auditor": (audit_outcomes or {}).get(
                "private_commitment_auditor", "pending"
            ),
        },
        "static_verification": dict(static_verification or {"status": "pending"}),
        "historical_claims": {
            "branch_a_information_dependence": (
                "BRANCH_A_INFORMATION_DEPENDENCE_SUPPORTED_ON_FROZEN_CARRIER"
            ),
            "branch_b_information_dependence": "LOCKED",
            "bilateral_parent_dependence": "LOCKED",
            "general_two_parent_necessity": "LOCKED",
            "transfer": "LOCKED",
            "general_catalytic_inference": "LOCKED",
            "task_advantage": "LOCKED",
            "superiority": "LOCKED",
            "sota": "LOCKED",
            "broader_process_local_holostate": "LOCKED",
            "restart_persistence": "LOCKED",
            "deep": "DISABLED",
            "automatic_promotion": False,
        },
        "execution_state": {
            "live_execution_performed": False,
            "sidecar_launched": False,
            "model_requests_issued": 0,
            "synthetic_live_evidence": False,
        },
    }
    if configuration is BINDING_2:
        binding_1 = _private_binding_from_repository(repository, BINDING_1)
        root_1 = private_secret_path(repository, BINDING_1).read_bytes()
        root_2 = private_secret_path(repository, BINDING_2).read_bytes()
        try:
            independence = binding_independence_checks(
                binding_1,
                private,
                roots_differ=not hmac.compare_digest(root_1, root_2),
            )
            payload_invariance = static_payload_invariance_report(
                binding_1, private
            )
        finally:
            del root_1
            del root_2
        document["authoritative_adjudication"] = {
            "commit": BINDING_2_STARTING_PROTECTED_MAIN,
            "relative_path": "lab/ck0_balanced_opaque_causal_adjudication_1.md",
            "artifact_sha256": "B4742B61F0654C8300676AA1F867813487532A99A901FDCFE2B5046E4A8751EF",
            "status": "CAUSAL_PACKAGE_VALID_WITH_RESIDUAL_LIMITATIONS",
            "selected_outcome": "REPLICATE_TRIAD_UNDER_FRESH_PRIVATE_BINDING",
            "selected_lane": "Lane A",
        }
        document["binding_1_package"] = {
            "implementation_commit": "38abb3ca54f16083206f33b10103b3311c1eafd5",
            "full_information_commit": "ea757e7afb4ddf832ee7e9e050ac03bc34c2c065",
            "delete_a_commit": "3133af3b60aabe05608f51874071955467f3b6d0",
            "delete_b_and_bilateral_commit": "9193e2a42212dbc1c1fab1de8fc5eff7d7b3ce31",
            "public_commitments": {
                "secret_commitment": binding_1.secret_commitment,
                "alias_map_commitment": binding_1.alias_map_commitment,
                "branch_presentation_commitments": dict(
                    binding_1.branch_alias_map_commitments
                ),
                "run_key_commitments": {
                    run_id: run_key_commitment(binding_1.run_key(run_id), BINDING_1)
                    for run_id in BINDING_1.run_modes
                },
            },
            "evidence": {
                "full_information": {
                    "run_id": FULL_RUN_ID,
                    "manifest_sha256": "A129BBD9BA9DEF0842144178B94A0269F66022EF82DB60D517CDD0C423CC2E1D",
                    "result_sha256": "B57FE3598A03F7CBB2765F77CE702293F72BBF900424F9592D719CF02DA458F8",
                    "closure_sha256": "FE918337A82C7D9D2C59DE56514D284C736A239226F03C91E8025811E92E8DDA",
                },
                "delete_parent_0": {
                    "run_id": DELETE_A_RUN_ID,
                    "manifest_sha256": "03508F7AE5E5F4A812C43F02FD31A3EE4009530B1CB17E61056213AE1079E74E",
                    "result_sha256": "7AE2578A6D48831B5335CE2826424EA375EB169A218502B404BD031507635846",
                    "closure_sha256": "4A2DD55ECC2DD03AE272F08FEB611F97E714EB587A28BD0660673E116286C873",
                },
                "delete_parent_1": {
                    "run_id": DELETE_B_RUN_ID,
                    "manifest_sha256": "EF2160E9CA719A4120FF7F7F226A1AD76F0BF08FE6A5C58CFFADCBCE2AB8B782",
                    "result_sha256": "F0E24AAA61A2E8D0EC567F93444E08FD81EB8AFE36E2C01D7397A4D06FD46CB6",
                    "closure_sha256": "880E238B877602AE3A869E2071DBDF1B0D3EE0FAF3D0D019C2D133D05C57BF90",
                },
            },
            "private_state_preserved": True,
            "published_statuses_preserved": True,
        }
        document["controller_private_binding"] = {
            "visibility": "controller_private_preregistered",
            "design_name": BINDING_2.profile_id,
            "domain_separation_identity": BINDING_2.domain_separation_identity,
            "binding_selector_model_visible": False,
        }
        document["binding_independence_checks"] = {
            "visibility": "controller_private_preregistered",
            "status": "pass",
            "generation_count": 1,
            "resampling_performed": False,
            "checks": independence,
        }
        document["no_correspondence_validation"] = {
            "visibility": "controller_private_preregistered",
            **payload_invariance,
        }
        document["frozen_mechanism"] = {
            "task_id": TASK_ID,
            "parent_0_public_examples": [1, 2, 3],
            "parent_1_public_examples": [3, 4, 5],
            "shared_calibration_example": 3,
            "parent_order": ["parent-0", "parent-1"],
            "support_cardinalities": [5, 5],
            "exclusive_alternatives": [4, 4],
            "relational_intersection_cardinality": 1,
            "branch_local_tied_score": "3/3",
            "branch_local_plateau_gap": 1,
            "support_pass_vectors": [[True, True, True], [True, True, True]],
            "request_lifecycle": list(REQUEST_IDS),
            "physical_slots": 1,
            "sidecar_epochs": 1,
        }
        document["frozen_runtime_and_custody_law"] = {
            "cache_root_admission": "exact-carrier-root-sha256",
            "lease_discipline": {
                "physical_slots": 1,
                "required_total_leases": 6,
                "maximum_concurrent_leases": 1,
                "required_terminal_active_leases": 0,
            },
            "resource_telemetry": {
                "mode": "exact-sidecar-pid-wddm",
                "wddm_mib_ceiling": 6000,
                "valid_measured_ceiling_breach": "fail-closed",
            },
            "cleanup": {
                "sidecar_stopped": True,
                "runtime_removed": True,
                "port_9494_free": True,
            },
            "restoration": {
                "carrier_identity_unchanged": True,
                "carrier_root_unchanged": True,
                "carrier_terminal_identity_unchanged": True,
                "cache_root_reuse_admitted": True,
                "branch_state_absent_from_carrier": True,
                "cleanup_passed": True,
            },
            "custody": {
                "stable_preserved": True,
                "candidate_preserved": True,
                "historical_cib0_preserved": True,
                "historical_ck0_preserved": True,
                "binding_1_package_preserved": True,
            },
            "tracked_persistence": {
                "mode": "bounded-normalized-metadata-only",
                "sse_events_persisted": False,
                "model_response_text_persisted": False,
                "reasoning_text_persisted": False,
                "private_mapping_persisted": False,
            },
        }
        document["future_command_bindings"] = {
            run_id: [
                "python",
                "scripts/holostate_live.py",
                "run-catalytic-kernel-0",
                "--binary",
                "<frozen-binary-path>",
                "--model",
                "<frozen-model-path>",
                "--run-id",
                run_id,
                "--carrier-profile",
                BINDING_2.profile_id,
            ]
            for run_id in BINDING_2.run_modes
        }
        document["future_authorization_boundary"] = {
            "live_authority_granted": False,
            "only_next_separately_authorizable_action": BINDING_2_FULL_RUN_ID,
            "delete_a_authorized": False,
            "delete_b_authorized": False,
            "deletion_controls_require_full_terminal_visible": True,
            "collapsed_or_inconclusive_full_does_not_authorize_controls": True,
        }
        document["classification_law"]["potential_cross_binding_status"] = {
            "status": "LOCKED",
            "label": "BILATERAL_PARENT_INFORMATION_DEPENDENCE_REPLICATED_ACROSS_PRIVATE_BINDINGS_ON_FROZEN_GEOMETRY",
            "requires_complete_successful_second_triad": True,
        }
        document["audits"] = {
            "binding_independence_auditor": (audit_outcomes or {}).get(
                "binding_independence_auditor", "pending"
            ),
            "cross_binding_no_correspondence_auditor": (audit_outcomes or {}).get(
                "cross_binding_no_correspondence_auditor", "pending"
            ),
        }
        document["historical_claims"] = {
            "binding_1_full_information": "BALANCED_OPAQUE_RELATIONAL_FULL_INFORMATION_VISIBLE",
            "binding_1_branch_a_information_dependence": "BRANCH_A_INFORMATION_DEPENDENCE_SUPPORTED_ON_BALANCED_OPAQUE_CARRIER",
            "binding_1_branch_b_information_dependence": "BRANCH_B_INFORMATION_DEPENDENCE_SUPPORTED_ON_BALANCED_OPAQUE_CARRIER",
            "binding_1_bilateral_parent_dependence": "BILATERAL_PARENT_INFORMATION_DEPENDENCE_SUPPORTED_ON_BALANCED_OPAQUE_CARRIER",
            "cross_binding_replication": "LOCKED",
            "general_two_parent_necessity": "LOCKED",
            "transfer": "LOCKED",
            "general_catalytic_inference": "LOCKED",
            "task_advantage": "LOCKED",
            "superiority": "LOCKED",
            "sota": "LOCKED",
            "broader_process_local_holostate": "LOCKED",
            "restart_persistence": "LOCKED",
            "deep": "DISABLED",
            "automatic_promotion": False,
        }
    validate_metadata_only(document)
    return document


def validate_preregistration(
    repository: Path,
    private: PrivateBinding,
    *,
    run_id: str,
    require_final: bool,
    configuration: PrivateBindingConfiguration | None = None,
    for_execution: bool = True,
) -> dict[str, Any]:
    selected = configuration or private.configuration
    if selected is not private.configuration or run_id not in selected.run_modes:
        raise BalancedOpaqueError("private binding configuration mismatch")
    path = repository / selected.preregistration_path
    if not path.is_file() or path.is_symlink():
        raise BalancedOpaqueError("balanced preregistration is missing or unsafe")
    try:
        document = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        raise BalancedOpaqueError("balanced preregistration is invalid JSON") from exc
    if not isinstance(document, dict) or document.get("status") != "static-preregistered":
        raise BalancedOpaqueError("balanced preregistration status changed")
    if document.get("protected_starting_sha") != selected.protected_starting_sha:
        raise BalancedOpaqueError("balanced preregistration starting boundary changed")
    profile = document.get("profile_binding", {})
    if (
        profile.get("profile_binding_sha256") != private.profile_binding_sha256
        or {key: value for key, value in profile.items() if key not in {"visibility", "profile_binding_sha256"}}
        != dict(private.profile)
    ):
        raise BalancedOpaqueError("balanced private profile binding changed")
    private_state = document.get("private_state", {})
    if (
        private_state.get("relative_path") != selected.secret_path
        or private_state.get("secret_commitment") != private.secret_commitment
        or private_state.get("alias_map_commitment") != private.alias_map_commitment
        or private_state.get("branch_alias_map_commitments")
        != dict(private.branch_alias_map_commitments)
        or private_state.get("secret_committed") is not False
        or private_state.get("alias_map_committed") is not False
        or private_state.get("generation_law")
        != {
            "source": "secrets.token_bytes",
            "requested_bytes": 32,
            "create_mode": "exclusive-once-atomic-publish",
            "existing_file_policy": "fail-closed",
        }
        or private_state.get("creation_receipt")
        != {
            "relative_path": selected.creation_receipt_path,
            "receipt_hmac_sha256": private.creation_receipt_commitment,
            "committed": False,
        }
    ):
        raise BalancedOpaqueError("balanced private commitment binding changed")
    if document.get("disclosure_law") != {
        "visibility": "controller_private_preregistered",
        "automatic_disclosure": False,
        "terminal_condition": list(selected.run_modes),
        "alternative": "explicit-user-retirement",
    }:
        raise BalancedOpaqueError("balanced private disclosure law changed")
    expected_runs = {
        item["run_id"]: item for item in document.get("future_runs", {}).get("runs", [])
        if isinstance(item, dict) and "run_id" in item
    }
    if set(expected_runs) != set(selected.run_modes) or run_id not in expected_runs:
        raise BalancedOpaqueError("balanced future run reservation changed")
    for expected_run_id, mode in selected.run_modes.items():
        item = expected_runs[expected_run_id]
        expected_item = {
            "run_id": expected_run_id,
            "mode": mode,
            "run_key_commitment": run_key_commitment(
                private.run_key(expected_run_id), selected
            ),
            "authorized_invocations": 1 if selected is BINDING_1 else 0,
            "retry_count": 0,
        }
        if selected is BINDING_2:
            expected_item["reservation_state"] = "reserved-unconsumed"
            expected_item["authorization_state"] = (
                "separately-authorizable"
                if mode == "full-information"
                else "unauthorized-until-full-terminal-visible"
            )
        if item != expected_item:
            raise BalancedOpaqueError("balanced future run binding changed")
    carrier = build_carrier()
    carrier_binding = document.get("model_visible_carrier", {})
    if (
        carrier_binding.get("carrier_id") != CARRIER_ID
        or carrier_binding.get("carrier_content_sha256") != carrier["carrier_content_sha256"]
        or carrier_binding.get("carrier_root_sha256") != carrier["carrier_root_sha256"]
    ):
        raise BalancedOpaqueError("balanced carrier preregistration changed")
    if document.get("response_schemas", {}).get("sha256") != response_schema_hashes():
        raise BalancedOpaqueError("balanced response schema binding changed")
    if document.get("request_seeds", {}).get("values") != {
        request_id: _request_seed(request_id) for request_id in REQUEST_IDS
    }:
        raise BalancedOpaqueError("balanced request seed binding changed")
    runtime = document.get("runtime_identities", {})
    if runtime.get("model") != MODEL_IDENTITY or runtime.get("binary") != BINARY_IDENTITY:
        raise BalancedOpaqueError("balanced runtime identity binding changed")
    source_binding = document.get("implementation_binding", {})
    paths = [item.get("path") for item in source_binding.get("files", []) if isinstance(item, dict)]
    if not paths or source_binding != implementation_binding(repository, paths):
        raise BalancedOpaqueError("balanced implementation source binding changed")
    if selected is BINDING_2:
        expected_document = build_preregistration_document(
            repository=repository,
            implementation_paths=paths,
            audit_outcomes=document.get("audits", {}),
            static_verification=document.get("static_verification", {}),
            configuration=BINDING_2,
        )
        if document != expected_document:
            raise BalancedOpaqueError(
                "binding-2 preregistration differs from its exact reconstruction"
            )
    if require_final:
        expected_audits = (
            {
                "carrier_leakage_auditor": "PASS",
                "private_commitment_auditor": "PASS",
            }
            if selected is BINDING_1
            else {
                "binding_independence_auditor": "PASS",
                "cross_binding_no_correspondence_auditor": "PASS",
            }
        )
        if document.get("audits") != expected_audits:
            raise BalancedOpaqueError("balanced read-only audits are not terminal PASS")
        if document.get("static_verification", {}).get("status") != "pass":
            raise BalancedOpaqueError("balanced static verification is not terminal PASS")
    if selected is BINDING_2:
        binding_1 = _private_binding_from_repository(repository, BINDING_1)
        root_1 = private_secret_path(repository, BINDING_1).read_bytes()
        root_2 = private_secret_path(repository, BINDING_2).read_bytes()
        try:
            expected_independence = binding_independence_checks(
                binding_1,
                private,
                roots_differ=not hmac.compare_digest(root_1, root_2),
            )
        finally:
            del root_1
            del root_2
        if document.get("binding_independence_checks") != {
            "visibility": "controller_private_preregistered",
            "status": "pass",
            "generation_count": 1,
            "resampling_performed": False,
            "checks": expected_independence,
        }:
            raise BalancedOpaqueError("binding independence preregistration changed")
        expected_correspondence = {
            "visibility": "controller_private_preregistered",
            **static_payload_invariance_report(binding_1, private),
        }
        if document.get("no_correspondence_validation") != expected_correspondence:
            raise BalancedOpaqueError("cross-binding no-correspondence validation changed")
        boundary = document.get("future_authorization_boundary", {})
        if (
            boundary.get("only_next_separately_authorizable_action")
            != BINDING_2_FULL_RUN_ID
            or boundary.get("delete_a_authorized") is not False
            or boundary.get("delete_b_authorized") is not False
            or boundary.get("deletion_controls_require_full_terminal_visible") is not True
        ):
            raise BalancedOpaqueError("binding-2 future authorization boundary changed")
        if for_execution and boundary.get("live_authority_granted") is not True:
            raise BalancedOpaqueError(
                "binding-2 live execution requires separate exact authorization"
            )
    if selected.run_modes[run_id] != "full-information":
        _require_terminal_full_run(repository, selected)
    projection = {
        "relative_path": selected.preregistration_path,
        "artifact_sha256": sha256_bytes(path.read_bytes()),
        "document_sha256": json_sha256(document),
        "profile_binding_sha256": private.profile_binding_sha256,
        "run_id": run_id,
        "mode": selected.run_modes[run_id],
        "status": "validated-static-preregistered",
    }
    validate_metadata_only(projection)
    return projection


def _require_terminal_full_run(
    repository: Path,
    configuration: PrivateBindingConfiguration = BINDING_1,
) -> None:
    full_run_id = next(
        run_id
        for run_id, mode in configuration.run_modes.items()
        if mode == "full-information"
    )
    root = repository / "state" / "catalytic_kernel_0" / full_run_id
    paths = {name: root / name for name in ("manifest.json", "result.json", "closure.json")}
    if any(not path.is_file() or path.is_symlink() for path in paths.values()):
        raise BalancedOpaqueError("full-information run is not terminally bound")
    if (root / "run.lock").exists():
        raise BalancedOpaqueError("full-information run still has an active lock")
    result = json.loads(paths["result.json"].read_bytes())
    closure = json.loads(paths["closure.json"].read_bytes())
    if (
        result.get("status") != "complete"
        or result.get("balanced_classification") != "BALANCED_OPAQUE_RELATIONAL_VISIBLE"
        or closure.get("run_lock_absent") is not True
        or closure.get("result_sha256") != sha256_bytes(paths["result.json"].read_bytes())
    ):
        raise BalancedOpaqueError("full-information run is not terminal visible evidence")


def static_model_visible_payloads(
    secret: bytes,
    run_id: str,
    configuration: PrivateBindingConfiguration | None = None,
) -> dict[str, dict[str, Any]]:
    """Generate all six payloads without I/O, sidecars, or model requests."""
    selected = configuration or binding_configuration_for_run(run_id)
    if run_id not in selected.run_modes:
        raise BalancedOpaqueError("run ID does not belong to the private binding")
    private = PrivateBinding.from_secret(secret, selected)
    return _static_model_visible_payloads_from_private(private, run_id)


def _static_model_visible_payloads_from_private(
    private: PrivateBinding,
    run_id: str,
) -> dict[str, dict[str, Any]]:
    if run_id not in private.configuration.run_modes:
        raise BalancedOpaqueError("run ID does not belong to the private binding")
    runtime = BalancedOpaqueRuntime(
        repository=Path.cwd(),
        run_id=run_id,
        private=private,
    )
    artifacts: dict[str, dict[str, Any]] = {}
    payloads: dict[str, dict[str, Any]] = {}
    for request_id in REQUEST_IDS:
        payloads[request_id] = runtime.build_model_request(request_id, artifacts)
        if request_id in BRANCH_INDICES:
            artifacts[request_id] = runtime.normalize_branch(
                request_id, ["K00", "K01", "K02"]
            )
        elif request_id == "transform":
            winner = private.internal_to_alias[EXPECTED_FULL_SUPPORT[0]]
            alternatives = sorted(
                (set(artifacts["branch-a"]["support_aliases"]) | set(artifacts["branch-b"]["support_aliases"]))
                - {winner}
            )
            artifacts["transform"] = runtime.normalize_transform(
                "combine", [winner, *alternatives[:2]]
            )
        elif request_id == "extract":
            artifacts["extract"] = runtime.normalize_extraction(
                artifacts["transform"]["ranking"][0], artifacts["transform"]
            )
    return payloads


__all__ = [
    "ALIASES",
    "ALIAS_MAP_DOMAIN",
    "BINDING_1",
    "BINDING_1_PROFILE_ID",
    "BINDING_2",
    "BINDING_2_DELETE_A_RUN_ID",
    "BINDING_2_DELETE_B_RUN_ID",
    "BINDING_2_FULL_RUN_ID",
    "BINDING_2_PROFILE_ID",
    "BINDING_CONFIGURATIONS",
    "BalancedOpaqueError",
    "BalancedOpaqueRuntime",
    "CARRIER_ID",
    "DELETE_A_RUN_ID",
    "DELETE_B_RUN_ID",
    "FULL_RUN_ID",
    "PRIVATE_SECRET_PATH",
    "PREREGISTRATION_PATH",
    "PROFILE_ID",
    "PrivateBinding",
    "PrivateBindingConfiguration",
    "RUN_MODES",
    "alias_map_commitment",
    "artifact_commitment",
    "build_carrier",
    "build_preregistration_document",
    "build_profile_binding",
    "binding_configuration",
    "binding_configuration_for_run",
    "binding_independence_checks",
    "carrier_is_pristine",
    "create_private_secret_once",
    "derive_alias_mapping",
    "derive_branch_alias_mapping",
    "derive_run_key",
    "implementation_binding",
    "response_schema",
    "response_schema_hashes",
    "run_key_commitment",
    "secret_commitment",
    "static_model_visible_payloads",
    "static_payload_invariance_report",
    "validate_preregistration",
    "verify_artifact_commitment",
]
