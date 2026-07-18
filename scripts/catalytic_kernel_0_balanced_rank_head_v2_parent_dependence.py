#!/usr/bin/env python3
"""Two-arm binding-2 parent-dependence replay for rank-head CK0 v2.

The static surface verifies the completed binding-2 full-information archive,
reconstructs exactly two transform-only interventions, and preregisters their
authority and evidence law.  The live surface remains closed unless one fresh
external authority binds the exact protected commit and both arms.  Each arm
can start at most one model generation; a started request without an exact
capture is terminally inconclusive and is never retried.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Iterator, Mapping, Sequence

import catalytic_kernel_0 as kernel
import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2 as v2
import catalytic_kernel_0_balanced_rank_head_v2_authority as source_authority
import catalytic_kernel_0_balanced_rank_head_v2_evidence as source_evidence
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration
import catalytic_kernel_0_balanced_rank_head_v2_parent_dependence_scientific as scientific
import catalytic_kernel_0_balanced_rank_head_v2_publication as publication
import catalytic_kernel_0_balanced_rank_head_v2_run_design as run_design
import catalytic_inference_bench_0_runtime as runtime_support


ParentDependenceError = scientific.ScientificSurfaceError


class CapturedResponseInvalidError(ParentDependenceError):
    """Authenticated captured model data is scientifically invalid."""


class RestartCustodyInvalidError(ParentDependenceError):
    """A restart could not reconstruct the required custody boundary."""


EXPERIMENT_ID = "ck0-balanced-v2-rank-head-b2-parent-dependence-r1"
STARTING_PROTECTED_MAIN = "720b434d1e2a6e54754d305aed89289cf707c545"
SOURCE_RUN_ID = integration.BINDING_2_RUN_ID
SOURCE_ARCHIVE_SHA256 = (
    "EBD8F01971C0D4BEE945A516D515645EF9F8F7BDC16F03D15BE7990F476536ED"
)
SOURCE_ARCHIVE_PATH = (
    Path("state/catalytic_kernel_0_rank_head_v2_evidence_archive")
    / "v1"
    / SOURCE_RUN_ID
    / SOURCE_ARCHIVE_SHA256
)
SOURCE_HASHES = {
    "receipt": "425828C3CB0819F05BA556A8CCBA1602C90F45311FDB677200DB14F3BC42A19B",
    "manifest": "23186EB4F48ABD262B3FF20933E0B1737D582B929AAC1E0048D16533EFAFD7A6",
    "result": "D7BFE06CED70B7544EB5F6D81EC64AE901CE6CD86DE82C72BCC4C5E395290BD9",
    "closure": "B09E6233720950648037C674E42C920F27150532D5FB957A55586F0DC9303CB5",
    "archive": SOURCE_ARCHIVE_SHA256,
}
SOURCE_PUBLICATION_ID = "neo-exp-0041"
SOURCE_PUBLICATION_SHA256 = (
    "D6DF5C9B4FFF825F236AB616EE8292CEAEC8F9905E9C47CF57B29F70F68F87EE"
)
SOURCE_PUBLICATION_LINE = 54
SOURCE_RUN_KEY_COMMITMENT = (
    "FEC400325777606A697687F990A24968B6AE787EDF444339A1639AE9BCFA8AC1"
)
CROSS_BINDING_PATH = Path(
    "lab/ck0_balanced_opaque_rank_head_v2_cross_binding_adjudication_1.json"
)
CROSS_BINDING_SHA256 = (
    "9473E1052DBE72CEABCB70EBA7787266DDF350843F01774A3F363213F29D4961"
)
BINDING_1_CAUSAL_PATH = Path("lab/ck0_balanced_opaque_causal_adjudication_1.md")
BINDING_1_CAUSAL_SHA256 = (
    "B4742B61F0654C8300676AA1F867813487532A99A901FDCFE2B5046E4A8751EF"
)
BINDING_1_PACKAGE_PATH = Path("lab/ck0_balanced_opaque_relational_carrier_v1.json")
BINDING_1_PACKAGE_SHA256 = (
    "D6FEC8B0477A198216ECDDDD8DE11AD2734410A640A69B37017394D9454643B7"
)
MODEL_SHA256 = "31AEFA25B7E1EDBDE436E643E2B5E3F6E57820A4811D97B131130E48FF0772C2"
BINARY_SHA256 = "5D0C5F7CE5CEBE35B564C21521ECD426F809445521D3C55C0581A9543F15541B"
CARRIER_ROOT_SHA256 = (
    "4B82F399ACE797BDF40012ABB4D1254021F838B58BAED66153D4042EF3C7585C"
)

ARM_SPECS = (
    {
        "arm_id": "delete-parent-0",
        "deleted_parent_role": "parent-0",
        "retained_parent_role": "parent-1",
        "supported_classification": (
            "BINDING_2_PARENT_A_INFORMATION_DEPENDENCE_SUPPORTED"
        ),
        "not_shown_classification": (
            "BINDING_2_PARENT_A_INFORMATION_DEPENDENCE_NOT_SHOWN"
        ),
    },
    {
        "arm_id": "delete-parent-1",
        "deleted_parent_role": "parent-1",
        "retained_parent_role": "parent-0",
        "supported_classification": (
            "BINDING_2_PARENT_B_INFORMATION_DEPENDENCE_SUPPORTED"
        ),
        "not_shown_classification": (
            "BINDING_2_PARENT_B_INFORMATION_DEPENDENCE_NOT_SHOWN"
        ),
    },
)
ARM_IDS = tuple(str(item["arm_id"]) for item in ARM_SPECS)
ARM_BY_ID = {str(item["arm_id"]): item for item in ARM_SPECS}
INCONCLUSIVE_CLASSIFICATION = "INCONCLUSIVE"

STATE_ROOT = Path("state/catalytic_kernel_0/rank_head_v2_parent_dependence")
ARCHIVE_ROOT = Path(
    "state/catalytic_kernel_0/rank_head_v2_parent_dependence_evidence_archive/v1"
)
RECEIPT_TEMPLATE = (
    "state/catalytic_kernel_0_authority.parent-dependence."
    "<experiment-id>.authority.consumed.json"
)
PREREGISTRATION_PATH = (
    "lab/ck0_balanced_opaque_rank_head_v2_binding_2_parent_dependence_1.json"
)
REPAIRABLE_CONTROLLER_PATHS = (
    "scripts/baseline_harness.py",
    "scripts/catalytic_inference_bench_0_runtime.py",
    "scripts/catalytic_kernel_0.py",
    "scripts/catalytic_kernel_0_balanced_opaque.py",
    "scripts/catalytic_kernel_0_balanced_rank_head_v2.py",
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_authority.py",
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_evidence.py",
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_integration.py",
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_publication.py",
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_run_design.py",
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_parent_dependence.py",
    "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_parent_dependence.py",
)
ALLOWED_CONTROLLER_REPAIR_PATHS = frozenset(
    set(REPAIRABLE_CONTROLLER_PATHS)
    | {
        "scripts/test_catalytic_kernel_0_balanced_rank_head_v2.py",
        "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_authority.py",
        "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_cli.py",
        "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_core.py",
        "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_entrypoint.py",
        "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_evidence.py",
        "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_integration.py",
        "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_live.py",
        "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_publication.py",
        "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_run_design.py",
        "TASKS.md",
        "lab/GOAL.md",
        "lab/CHECKPOINT.md",
        "lab/EVALUATOR.lock.json",
    }
)
MAXIMUM_CONTROLLER_REPAIR_COMMITS = 3

EXPERIMENT_KEY_DOMAIN = b"ck0-rank-head-v2/parent-dependence/experiment-key-v1\0"
ARM_KEY_DOMAIN = b"ck0-rank-head-v2/parent-dependence/arm-key-v1\0"
AUTHORITY_ID_DOMAIN = b"ck0-rank-head-v2/parent-dependence/authority-id-v1\0"
AUTHORITY_HMAC_DOMAIN = b"ck0-rank-head-v2/parent-dependence/authority-hmac-v1\0"
JOURNAL_HMAC_DOMAIN = b"ck0-rank-head-v2/parent-dependence/journal-hmac-v1\0"
CAPTURE_HMAC_DOMAIN = b"ck0-rank-head-v2/parent-dependence/capture-hmac-v1\0"
AUTHORITY_SCHEMA_VERSION = "rank-head-v2-parent-dependence-authority-v1"
RECEIPT_SCHEMA_VERSION = "rank-head-v2-parent-dependence-consumption-v1"
AUTHORITY_KIND = "external-one-shot-two-arm-parent-dependence"
JOURNAL_SCHEMA_VERSION = 1
CAPTURE_SCHEMA_VERSION = scientific.CAPTURE_SCHEMA_VERSION
ARCHIVE_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
EXPERIMENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
AUTHORITY_ID_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
GENESIS_HASH = "0" * 64
MAX_CAPTURE_BYTES = 256 * 1024
MAX_RAW_RESPONSE_BYTES = 128 * 1024
MAX_STATE_BYTES = 1024 * 1024

LOCKED_CLAIMS = {
    "BINDING_2_PARENT_DEPENDENCE": "LOCKED_UNTIL_EXECUTED",
    "CAUSAL_REPLICATION_ACROSS_BINDINGS": "LOCKED_UNTIL_BOTH_ARMS_SUPPORT",
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

_CAPTURE_EXECUTION_FIELDS = scientific.CAPTURE_EXECUTION_FIELDS


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
        raise ParentDependenceError(message)


def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ParentDependenceError(f"{label} is not an uppercase SHA-256")
    return value


def _relative(repository: Path, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(
            repository.resolve(strict=False)
        ).as_posix()
    except ValueError as exc:
        raise ParentDependenceError("path escapes repository") from exc


def _require_regular(path: Path, label: str, *, maximum: int = MAX_STATE_BYTES) -> bytes:
    if (
        not path.is_file()
        or balanced._is_reparse(path)
        or path.stat().st_size > maximum
    ):
        raise ParentDependenceError(f"{label} is missing or unsafe")
    return path.read_bytes()


def _json_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ParentDependenceError(f"{label} is invalid JSON") from exc
    if not isinstance(value, dict):
        raise ParentDependenceError(f"{label} is not an object")
    return value


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        raise ParentDependenceError("git custody query failed")
    return completed.stdout.strip()


def _require_ignored(repository: Path, path: Path) -> None:
    completed = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", _relative(repository, path)],
        cwd=repository,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise ParentDependenceError("runtime evidence path is not ignored")


def _exclusive_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
        stat.S_IRUSR | stat.S_IWUSR,
    )
    try:
        written = os.write(descriptor, data)
        if written != len(data):
            raise ParentDependenceError("exclusive write was incomplete")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_or_require_identical(path: Path, data: bytes) -> None:
    if path.exists() or path.is_symlink():
        if (
            not path.is_file()
            or balanced._is_reparse(path)
            or path.read_bytes() != data
        ):
            raise ParentDependenceError("existing evidence differs")
        return
    _exclusive_write(path, data)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    balanced.validate_metadata_only(value)
    data = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        indent=2,
    ).encode("utf-8") + b"\n"
    if len(data) > MAX_STATE_BYTES:
        raise ParentDependenceError("state object exceeds byte ceiling")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        _exclusive_write(temporary, data)
        os.replace(temporary, path)
    finally:
        if temporary.is_file() and not balanced._is_reparse(temporary):
            temporary.unlink()


def _file_binding(repository: Path, paths: Sequence[str]) -> dict[str, Any]:
    files = []
    for relative in paths:
        data = _require_regular(repository / relative, relative)
        files.append(
            {"path": relative, "byte_size": len(data), "sha256": sha256_bytes(data)}
        )
    body = {"files": files}
    return {**body, "sha256": json_sha256(body)}


def _scientific_contract(repository: Path) -> dict[str, Any]:
    source = verify_source_evidence(repository)
    return {
        "experiment_id": EXPERIMENT_ID,
        "source_binding": "binding-2",
        "source_run_id": SOURCE_RUN_ID,
        "source_archive_sha256": SOURCE_ARCHIVE_SHA256,
        "source_publication_record_sha256": SOURCE_PUBLICATION_SHA256,
        "source_evidence_sha256": dict(SOURCE_HASHES),
        "experiment_run_key_commitment": source["experiment_run_key_commitment"],
        "intervention": {
            "construction": "exactly-one-retained-parent-plus-one-commitment-only-projection",
            "deleted_parent_projection_mode": "commitment-only",
            "retained_parent_byte_exact": True,
        },
        "arm_ids": list(ARM_IDS),
        "arm_ordering": list(ARM_IDS),
        "model_sha256": MODEL_SHA256,
        "binary_sha256": BINARY_SHA256,
        "carrier_root_sha256": CARRIER_ROOT_SHA256,
        "seeds": {arm_id: arm_seed(arm_id) for arm_id in ARM_IDS},
        "response_schema_sha256": json_sha256(v2.v2_response_schema("transform")),
        "maximum_model_generations_per_arm": 1,
        "maximum_total_model_generations": 2,
        "request_dispatch": "frozen-scientific-module-exact-hash-gate-before-contact",
        "raw_response_recording": "exclusive-fsynced-capture-before-controller-parse",
    }


def _frozen_scientific_binding(repository: Path) -> dict[str, Any]:
    payloads = {arm_id: build_arm_request(repository, arm_id) for arm_id in ARM_IDS}
    return scientific.frozen_scientific_binding(
        repository,
        contract=_scientific_contract(repository),
        payloads=payloads,
    )


def _repairable_controller_binding(repository: Path) -> dict[str, Any]:
    return _file_binding(repository, REPAIRABLE_CONTROLLER_PATHS)


def _implementation_binding(repository: Path) -> dict[str, Any]:
    frozen = _frozen_scientific_binding(repository)
    controller = _repairable_controller_binding(repository)
    body = {
        "frozen_scientific_execution": frozen,
        "repairable_controller": controller,
    }
    return {**body, "sha256": json_sha256(body)}


def source_archive_path(repository: Path) -> Path:
    return repository.resolve(strict=False) / SOURCE_ARCHIVE_PATH


def _source_payloads(repository: Path) -> dict[str, bytes]:
    root = source_archive_path(repository)
    return {
        "receipt": _require_regular(root / "authority-receipt.json", "source receipt"),
        "manifest": _require_regular(root / "manifest.json", "source manifest"),
        "result": _require_regular(root / "result.json", "source result"),
        "closure": _require_regular(root / "closure.json", "source closure"),
    }


def _source_runtime(repository: Path) -> integration.RankHeadV2Runtime:
    spec = integration.run_spec(SOURCE_RUN_ID)
    source_private = balanced._private_binding_from_repository(
        repository,
        balanced.BINDING_2,
    )
    private = integration.runtime_private_from_source(source_private, spec)
    return integration.RankHeadV2Runtime(
        repository=repository,
        spec=spec,
        private=private,
        run_design=run_design.validate_run_design(repository),
    )


def _experiment_key(source_runtime: integration.RankHeadV2Runtime) -> bytes:
    return hmac.new(
        source_runtime.run_key,
        EXPERIMENT_KEY_DOMAIN + EXPERIMENT_ID.encode("ascii"),
        hashlib.sha256,
    ).digest()


def experiment_run_key_commitment(source_runtime: integration.RankHeadV2Runtime) -> str:
    return sha256_bytes(
        b"ck0-rank-head-v2/parent-dependence/experiment-key-commitment-v1\0"
        + _experiment_key(source_runtime)
    )


def _arm_runtime(
    repository: Path,
    source_runtime: integration.RankHeadV2Runtime,
    arm_id: str,
) -> integration.RankHeadV2Runtime:
    spec_body = ARM_BY_ID.get(arm_id)
    if spec_body is None:
        raise ParentDependenceError("unknown parent-dependence arm")
    experiment_key = _experiment_key(source_runtime)
    arm_key = hmac.new(
        experiment_key,
        ARM_KEY_DOMAIN + arm_id.encode("ascii"),
        hashlib.sha256,
    ).digest()
    configuration = balanced.PrivateBindingConfiguration(
        profile_id=f"rank-head-v2-parent-dependence:{arm_id}",
        preregistration_path=PREREGISTRATION_PATH,
        secret_path=balanced.BINDING_2.secret_path,
        creation_receipt_path=balanced.BINDING_2.creation_receipt_path,
        run_modes={arm_id: arm_id},
        domain_separation_identity=f"rank-head-v2-parent-dependence-v1:{arm_id}",
        protected_starting_sha=STARTING_PROTECTED_MAIN,
    )
    private = replace(
        source_runtime.private,
        configuration=configuration,
        run_keys={arm_id: arm_key},
    )
    spec = integration.V2RunSpec(
        run_id=arm_id,
        ordinal=ARM_IDS.index(arm_id) + 1,
        source_binding="binding-2",
        source_profile_id=balanced.BINDING_2_PROFILE_ID,
        source_full_run_id=SOURCE_RUN_ID,
        authorization_state="single-shared-external-authority-required",
    )
    return integration.RankHeadV2Runtime(
        repository=repository,
        spec=spec,
        private=private,
        run_design={"experiment_id": EXPERIMENT_ID},
    )


def verify_source_evidence(repository: Path) -> dict[str, Any]:
    """Verify the exact archived b2 full run and return no private aliases."""
    repository = repository.resolve(strict=False)
    verified_archive = source_evidence.verify_archive(
        repository,
        source_archive_path(repository),
    )
    _require(
        verified_archive.get("bundle_sha256") == SOURCE_ARCHIVE_SHA256,
        "source archive identity changed",
    )
    payloads = _source_payloads(repository)
    for name, expected in SOURCE_HASHES.items():
        if name != "archive":
            _require(sha256_bytes(payloads[name]) == expected, f"source {name} changed")
    source_receipt = source_authority.verify_authority_receipt_bytes_for_run(
        repository,
        SOURCE_RUN_ID,
        payloads["receipt"],
        require_current_static=False,
    )
    result = _json_object(payloads["result"], "source result")
    closure = _json_object(payloads["closure"], "source closure")
    _require(
        result.get("run_id") == SOURCE_RUN_ID
        and result.get("status") == "complete"
        and result.get("terminal_classification")
        == integration.VISIBLE_CLASSIFICATION
        and closure.get("manifest_sha256") == SOURCE_HASHES["manifest"]
        and closure.get("result_sha256") == SOURCE_HASHES["result"]
        and closure.get("run_lock_absent") is True,
        "source terminal chain changed",
    )
    source_runtime = _source_runtime(repository)
    branch_a = result.get("branch_a")
    branch_b = result.get("branch_b")
    transform = result.get("transform")
    extraction = result.get("deterministic_extraction")
    try:
        source_runtime.verify_branch_artifact(branch_a)
        source_runtime.verify_branch_artifact(branch_b)
        source_runtime.verify_transform_artifact(transform)
        v2.verify_deterministic_extraction_receipt(
            source_runtime,
            extraction,
            transform,
        )
    except (TypeError, balanced.BalancedOpaqueError, v2.RankHeadDesignError) as exc:
        raise ParentDependenceError("source private artifacts failed verification") from exc
    publication_projection = publication.validate_publication(repository, SOURCE_RUN_ID)
    _require(
        publication_projection.get("record_id") == SOURCE_PUBLICATION_ID
        and publication_projection.get("record_sha256") == SOURCE_PUBLICATION_SHA256
        and publication_projection.get("ledger_line") == SOURCE_PUBLICATION_LINE,
        "source publication identity changed",
    )
    for relative, expected in (
        (CROSS_BINDING_PATH, CROSS_BINDING_SHA256),
        (BINDING_1_CAUSAL_PATH, BINDING_1_CAUSAL_SHA256),
        (BINDING_1_PACKAGE_PATH, BINDING_1_PACKAGE_SHA256),
    ):
        _require(
            sha256_bytes(_require_regular(repository / relative, relative.as_posix()))
            == expected,
            f"tracked predecessor changed: {relative.as_posix()}",
        )
    return {
        "source_run_id": SOURCE_RUN_ID,
        "source_terminal_classification": integration.VISIBLE_CLASSIFICATION,
        "source_hashes": dict(SOURCE_HASHES),
        "source_publication": {
            "record_id": SOURCE_PUBLICATION_ID,
            "record_sha256": SOURCE_PUBLICATION_SHA256,
            "ledger_line": SOURCE_PUBLICATION_LINE,
        },
        "source_run_key_commitment": SOURCE_RUN_KEY_COMMITMENT,
        "experiment_run_key_commitment": experiment_run_key_commitment(source_runtime),
        "source_branch_commitments": {
            "parent-0": str(branch_a["artifact_commitment"]),
            "parent-1": str(branch_b["artifact_commitment"]),
        },
        "reference_transform_commitment": str(transform["artifact_commitment"]),
        "reference_extraction_commitment": str(extraction["artifact_commitment"]),
        "cross_binding_adjudication_sha256": CROSS_BINDING_SHA256,
        "binding_1_causal_adjudication_sha256": BINDING_1_CAUSAL_SHA256,
        "binding_1_package_sha256": BINDING_1_PACKAGE_SHA256,
        "model_sha256": MODEL_SHA256,
        "binary_sha256": BINARY_SHA256,
        "carrier_root_sha256": CARRIER_ROOT_SHA256,
        "archive_verified": True,
        "private_artifacts_verified": True,
        "publication_verified": True,
        "authority_receipt_verified": source_receipt.get("consumed") is True,
    }


def _source_parent_artifacts(repository: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    payloads = _source_payloads(repository)
    result = _json_object(payloads["result"], "source result")
    branch_a = result.get("branch_a")
    branch_b = result.get("branch_b")
    if not isinstance(branch_a, dict) or not isinstance(branch_b, dict):
        raise ParentDependenceError("source parent artifacts are missing")
    runtime = _source_runtime(repository)
    runtime.verify_branch_artifact(branch_a)
    runtime.verify_branch_artifact(branch_b)
    return branch_a, branch_b


def arm_assignment(repository: Path, arm_id: str) -> dict[str, Any]:
    source_runtime = _source_runtime(repository)
    branch_a, branch_b = _source_parent_artifacts(repository)
    parents: list[dict[str, Any]] = [branch_a, branch_b]
    deleted_index = ARM_IDS.index(arm_id)
    parents[deleted_index] = source_runtime.deletion_receipt(parents[deleted_index])
    assignment = {
        "stage": "transform",
        "instruction": (
            "Operate only on the supplied opaque parent relations. Author one "
            "allowed operator and one opaque candidate ranking."
        ),
        "parent_artifacts": parents,
    }
    _validate_arm_assignment(repository, arm_id, assignment)
    return assignment


def _validate_arm_assignment(
    repository: Path,
    arm_id: str,
    assignment: Mapping[str, Any],
) -> dict[str, Any]:
    if arm_id not in ARM_BY_ID:
        raise ParentDependenceError("unknown arm")
    source_runtime = _source_runtime(repository)
    branch_a, branch_b = _source_parent_artifacts(repository)
    expected_complete = [branch_a, branch_b]
    deleted_index = ARM_IDS.index(arm_id)
    expected = [dict(branch_a), dict(branch_b)]
    expected[deleted_index] = source_runtime.deletion_receipt(expected[deleted_index])
    _require(
        set(assignment) == {"stage", "instruction", "parent_artifacts"}
        and assignment.get("stage") == "transform"
        and assignment.get("parent_artifacts") == expected,
        "arm assignment differs from exact source projection",
    )
    parents = assignment["parent_artifacts"]
    receipt = parents[deleted_index]
    retained = parents[1 - deleted_index]
    _require(
        set(receipt) == balanced.DELETION_RECEIPT_FIELDS
        and receipt.get("projection_mode") == "commitment-only"
        and receipt.get("informative_content_withheld") is True,
        "deleted parent projection smuggled informative content",
    )
    _require(
        retained == expected_complete[1 - deleted_index],
        "retained parent differs from archived complete parent",
    )
    balanced._assert_no_internal_identity(assignment)
    balanced.validate_metadata_only(assignment)
    return {
        "arm_id": arm_id,
        "deleted_parent_role": ARM_BY_ID[arm_id]["deleted_parent_role"],
        "retained_parent_role": ARM_BY_ID[arm_id]["retained_parent_role"],
        "complete_parent_count": 1,
        "commitment_only_parent_count": 1,
        "deleted_parent_fields_exact": sorted(balanced.DELETION_RECEIPT_FIELDS),
        "retained_parent_byte_exact": True,
        "no_smuggle_verified": True,
    }


def arm_seed(arm_id: str) -> int:
    if arm_id not in ARM_IDS:
        raise ParentDependenceError("unknown arm seed identity")
    digest = hashlib.sha256(
        b"ck0-rank-head-v2/parent-dependence/arm-seed-v1\0"
        + arm_id.encode("ascii")
    ).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def build_arm_request(repository: Path, arm_id: str) -> dict[str, Any]:
    assignment = arm_assignment(repository, arm_id)
    carrier = v2.build_v2_carrier()
    payload = {
        "model": balanced.MODEL_ALIAS,
        "messages": [
            {"role": "system", "content": carrier["carrier_root"]},
            {"role": "user", "content": canonical_json_text(assignment)},
        ],
        "temperature": 0.0,
        "seed": arm_seed(arm_id),
        "max_tokens": 64,
        "stream": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": f"ck0_rank_head_v2_parent_dependence_{arm_id.replace('-', '_')}",
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
    _require(
        carrier["carrier_root_sha256"] == CARRIER_ROOT_SHA256,
        "carrier root identity changed",
    )
    _require(
        json.loads(payload["messages"][1]["content"]) == assignment,
        "arm request assignment changed",
    )
    balanced._assert_no_internal_identity(payload)
    balanced.validate_metadata_only(assignment)
    return payload


def request_isolation_report(repository: Path) -> dict[str, Any]:
    payloads = {arm_id: build_arm_request(repository, arm_id) for arm_id in ARM_IDS}
    reversed_payloads = {
        arm_id: build_arm_request(repository, arm_id) for arm_id in reversed(ARM_IDS)
    }
    hashes = {arm_id: json_sha256(payloads[arm_id]) for arm_id in ARM_IDS}
    _require(
        hashes
        == {arm_id: json_sha256(reversed_payloads[arm_id]) for arm_id in ARM_IDS},
        "arm payload identity depends on execution order",
    )
    assignments = {
        arm_id: json.loads(payloads[arm_id]["messages"][1]["content"])
        for arm_id in ARM_IDS
    }
    return {
        "parallelism": 1,
        "physical_slots": 1,
        "sidecar_epochs_maximum": 1,
        "arm_request_sha256": hashes,
        "execution_order_independent": True,
        "cross_arm_response_visible": False,
        "request_self_contained": True,
        "model_authored_restore_required": False,
        "model_visible_carrier_mutation_present": False,
        "arm_projections": {
            arm_id: _validate_arm_assignment(repository, arm_id, assignments[arm_id])
            for arm_id in ARM_IDS
        },
    }


def authority_object_schema() -> dict[str, Any]:
    """Stable schema; experiment identity is data and is validated separately."""
    sha = {"type": "string", "pattern": "^[0-9A-F]{64}$"}
    commit = {"type": "string", "pattern": "^[0-9a-f]{40}$"}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "authority_kind",
            "authority_id_sha256",
            "authorized_commit",
            "original_authorized_execution_commit",
            "experiment_id",
            "source_binding",
            "source_run_id",
            "source_run_key_commitment",
            "experiment_run_key_commitment",
            "source_evidence_sha256",
            "source_publication_record_id",
            "source_publication_record_sha256",
            "cross_binding_adjudication_sha256",
            "binding_1_causal_adjudication_sha256",
            "arm_ids",
            "maximum_model_generations_per_arm",
            "maximum_total_model_generations",
            "model_sha256",
            "binary_sha256",
            "carrier_root_sha256",
            "frozen_scientific_execution_binding_sha256",
            "arm_request_sha256",
            "repairable_controller_initial_binding_sha256",
            "implementation_binding_sha256",
            "preregistration_artifact_sha256",
            "preregistration_document_sha256",
            "journal_schema_sha256",
            "capture_schema_sha256",
            "archive_schema_sha256",
            "maximum_controller_repair_commits",
            "current_commit_must_descend_from_original",
            "controller_repair_cannot_reset_arm_consumption",
            "retry_count",
            "automatic_follow_on",
        ],
        "properties": {
            "schema_version": {"const": AUTHORITY_SCHEMA_VERSION},
            "authority_kind": {"const": AUTHORITY_KIND},
            "authority_id_sha256": sha,
            "authorized_commit": commit,
            "original_authorized_execution_commit": commit,
            "experiment_id": {
                "type": "string",
                "pattern": "^[a-z0-9][a-z0-9._-]{0,127}$",
            },
            "source_binding": {"type": "string"},
            "source_run_id": {"type": "string"},
            "source_run_key_commitment": sha,
            "experiment_run_key_commitment": sha,
            "source_evidence_sha256": {
                "type": "object",
                "additionalProperties": False,
                "required": sorted(SOURCE_HASHES),
                "properties": {name: sha for name in sorted(SOURCE_HASHES)},
            },
            "source_publication_record_id": {"type": "string"},
            "source_publication_record_sha256": sha,
            "cross_binding_adjudication_sha256": sha,
            "binding_1_causal_adjudication_sha256": sha,
            "arm_ids": {
                "type": "array",
                "minItems": 1,
                "maxItems": 8,
                "uniqueItems": True,
                "items": {
                    "type": "string",
                    "pattern": "^[a-z0-9][a-z0-9._-]{0,63}$",
                },
            },
            "maximum_model_generations_per_arm": {"type": "integer", "minimum": 0},
            "maximum_total_model_generations": {"type": "integer", "minimum": 0},
            "model_sha256": sha,
            "binary_sha256": sha,
            "carrier_root_sha256": sha,
            "frozen_scientific_execution_binding_sha256": sha,
            "arm_request_sha256": {
                "type": "object",
                "additionalProperties": False,
                "required": list(ARM_IDS),
                "properties": {arm_id: sha for arm_id in ARM_IDS},
            },
            "repairable_controller_initial_binding_sha256": sha,
            "implementation_binding_sha256": sha,
            "preregistration_artifact_sha256": sha,
            "preregistration_document_sha256": sha,
            "journal_schema_sha256": sha,
            "capture_schema_sha256": sha,
            "archive_schema_sha256": sha,
            "maximum_controller_repair_commits": {"const": 3},
            "current_commit_must_descend_from_original": {"const": True},
            "controller_repair_cannot_reset_arm_consumption": {"const": True},
            "retry_count": {"type": "integer", "minimum": 0},
            "automatic_follow_on": {"type": "boolean"},
        },
    }


def authority_receipt_schema() -> dict[str, Any]:
    sha = {"type": "string", "pattern": "^[0-9A-F]{64}$"}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "authority",
            "authority_object_schema_sha256",
            "authority_receipt_schema_sha256",
            "authority_hmac",
            "consumed",
        ],
        "properties": {
            "schema_version": {"const": RECEIPT_SCHEMA_VERSION},
            "authority": authority_object_schema(),
            "authority_object_schema_sha256": sha,
            "authority_receipt_schema_sha256": sha,
            "authority_hmac": sha,
            "consumed": {"const": True},
        },
    }


def journal_event_schema() -> dict[str, Any]:
    return {
        "schema_version": JOURNAL_SCHEMA_VERSION,
        "required_fields": [
            "schema_version",
            "sequence",
            "experiment_id",
            "state",
            "arm_id",
            "observed_at",
            "previous_event_sha256",
            "facts",
            "event_sha256",
            "event_hmac_sha256",
        ],
        "states": [
            "prepared",
            "authority-consumed",
            "controller-repair-observed",
            "request-started",
            "response-captured",
            "request-custody-observed",
            "finalization-observed",
            "adjudicated",
            "terminal-written",
            "archived",
        ],
        "hash_law": "SHA-256 hash chain plus experiment-key HMAC of each canonical event",
        "append_only": True,
    }


def capture_schema() -> dict[str, Any]:
    return scientific.capture_schema()


def archive_schema() -> dict[str, Any]:
    return {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "content_address": "SHA-256 of canonical bundle",
        "required_core_files": [
            "authority-receipt.json",
            "manifest.json",
            "journal.jsonl",
            "result.json",
            "closure.json",
        ],
        "capture_files": [f"capture-{arm_id}.json" for arm_id in ARM_IDS],
        "partial_capture_files": [
            f"partial-capture-{arm_id}.raw" for arm_id in ARM_IDS
        ],
        "restore_policy": "missing-or-byte-identical-only",
        "overwrite_allowed": False,
    }


AUTHORITY_OBJECT_SCHEMA_SHA256 = json_sha256(authority_object_schema())
AUTHORITY_RECEIPT_SCHEMA_SHA256 = json_sha256(authority_receipt_schema())
JOURNAL_SCHEMA_SHA256 = json_sha256(journal_event_schema())


def authority_id_sha256(raw_authority_id: str) -> str:
    if not isinstance(raw_authority_id, str) or AUTHORITY_ID_RE.fullmatch(
        raw_authority_id
    ) is None:
        raise ParentDependenceError("authority ID must be exactly 64 hex characters")
    return sha256_bytes(AUTHORITY_ID_DOMAIN + bytes.fromhex(raw_authority_id))


def receipt_path(repository: Path, experiment_id: str = EXPERIMENT_ID) -> Path:
    if EXPERIMENT_ID_RE.fullmatch(experiment_id) is None:
        raise ParentDependenceError("experiment ID is unsafe")
    return repository.resolve(strict=False) / RECEIPT_TEMPLATE.replace(
        "<experiment-id>", experiment_id
    )


def state_paths(repository: Path) -> dict[str, Path]:
    run_root = repository.resolve(strict=False) / STATE_ROOT / EXPERIMENT_ID
    captures = run_root / "captures"
    return {
        "run_root": run_root,
        "manifest": run_root / "manifest.json",
        "journal": run_root / "journal.jsonl",
        "result": run_root / "result.json",
        "closure": run_root / "closure.json",
        "run_lock": run_root / "run.lock",
        "capture-delete-parent-0": captures / "delete-parent-0.json",
        "capture-delete-parent-1": captures / "delete-parent-1.json",
        "partial-capture-delete-parent-0": captures / "delete-parent-0.raw.partial",
        "partial-capture-delete-parent-1": captures / "delete-parent-1.raw.partial",
        "receipt": receipt_path(repository),
    }


def _runtime_allowed_paths(paths: Mapping[str, Path]) -> tuple[Path, ...]:
    """Return only exact mutable files below the custody-authorized run root."""
    return tuple(
        path
        for key, path in paths.items()
        if key not in {"run_root", "receipt"}
    )


def build_external_authority(
    repository: Path,
    *,
    raw_authority_id: str,
    authorized_commit: str,
    current_commit: str,
    expected_model_sha256: str,
    expected_binary_sha256: str,
) -> dict[str, Any]:
    repository = repository.resolve(strict=False)
    if (
        GIT_COMMIT_RE.fullmatch(authorized_commit) is None
        or GIT_COMMIT_RE.fullmatch(current_commit) is None
    ):
        raise ParentDependenceError("authority commit identity is malformed")
    if expected_model_sha256 != MODEL_SHA256 or expected_binary_sha256 != BINARY_SHA256:
        raise ParentDependenceError("authority model or binary identity changed")
    source = verify_source_evidence(repository)
    preregistration = validate_preregistration(
        repository,
        require_current_controller=current_commit == authorized_commit,
    )
    frozen = _frozen_scientific_binding(repository)
    isolation = request_isolation_report(repository)
    authority = {
        "schema_version": AUTHORITY_SCHEMA_VERSION,
        "authority_kind": AUTHORITY_KIND,
        "authority_id_sha256": authority_id_sha256(raw_authority_id),
        "authorized_commit": authorized_commit,
        "original_authorized_execution_commit": authorized_commit,
        "experiment_id": EXPERIMENT_ID,
        "source_binding": "binding-2",
        "source_run_id": SOURCE_RUN_ID,
        "source_run_key_commitment": SOURCE_RUN_KEY_COMMITMENT,
        "experiment_run_key_commitment": source["experiment_run_key_commitment"],
        "source_evidence_sha256": dict(SOURCE_HASHES),
        "source_publication_record_id": SOURCE_PUBLICATION_ID,
        "source_publication_record_sha256": SOURCE_PUBLICATION_SHA256,
        "cross_binding_adjudication_sha256": CROSS_BINDING_SHA256,
        "binding_1_causal_adjudication_sha256": BINDING_1_CAUSAL_SHA256,
        "arm_ids": list(ARM_IDS),
        "maximum_model_generations_per_arm": 1,
        "maximum_total_model_generations": 2,
        "model_sha256": MODEL_SHA256,
        "binary_sha256": BINARY_SHA256,
        "carrier_root_sha256": CARRIER_ROOT_SHA256,
        "frozen_scientific_execution_binding_sha256": frozen["sha256"],
        "arm_request_sha256": dict(isolation["arm_request_sha256"]),
        "repairable_controller_initial_binding_sha256": preregistration[
            "repairable_controller_initial_binding_sha256"
        ],
        "implementation_binding_sha256": preregistration[
            "implementation_binding_sha256"
        ],
        "preregistration_artifact_sha256": preregistration["artifact_sha256"],
        "preregistration_document_sha256": preregistration["document_sha256"],
        "journal_schema_sha256": JOURNAL_SCHEMA_SHA256,
        "capture_schema_sha256": json_sha256(capture_schema()),
        "archive_schema_sha256": json_sha256(archive_schema()),
        "maximum_controller_repair_commits": MAXIMUM_CONTROLLER_REPAIR_COMMITS,
        "current_commit_must_descend_from_original": True,
        "controller_repair_cannot_reset_arm_consumption": True,
        "retry_count": 0,
        "automatic_follow_on": False,
    }
    validate_external_authority(
        repository,
        authority,
        current_commit=current_commit,
        expected_model_sha256=expected_model_sha256,
        expected_binary_sha256=expected_binary_sha256,
    )
    return authority


def _expected_authority_body(
    repository: Path,
    authority: Mapping[str, Any],
    *,
    require_current_controller: bool = True,
) -> dict[str, Any]:
    source = verify_source_evidence(repository)
    preregistration = validate_preregistration(
        repository,
        require_current_controller=require_current_controller,
    )
    frozen = _frozen_scientific_binding(repository)
    isolation = request_isolation_report(repository)
    return {
        "schema_version": AUTHORITY_SCHEMA_VERSION,
        "authority_kind": AUTHORITY_KIND,
        "authority_id_sha256": authority.get("authority_id_sha256"),
        "authorized_commit": authority.get("authorized_commit"),
        "original_authorized_execution_commit": authority.get(
            "authorized_commit"
        ),
        "experiment_id": EXPERIMENT_ID,
        "source_binding": "binding-2",
        "source_run_id": SOURCE_RUN_ID,
        "source_run_key_commitment": SOURCE_RUN_KEY_COMMITMENT,
        "experiment_run_key_commitment": source["experiment_run_key_commitment"],
        "source_evidence_sha256": dict(SOURCE_HASHES),
        "source_publication_record_id": SOURCE_PUBLICATION_ID,
        "source_publication_record_sha256": SOURCE_PUBLICATION_SHA256,
        "cross_binding_adjudication_sha256": CROSS_BINDING_SHA256,
        "binding_1_causal_adjudication_sha256": BINDING_1_CAUSAL_SHA256,
        "arm_ids": list(ARM_IDS),
        "maximum_model_generations_per_arm": 1,
        "maximum_total_model_generations": 2,
        "model_sha256": MODEL_SHA256,
        "binary_sha256": BINARY_SHA256,
        "carrier_root_sha256": CARRIER_ROOT_SHA256,
        "frozen_scientific_execution_binding_sha256": frozen["sha256"],
        "arm_request_sha256": dict(isolation["arm_request_sha256"]),
        "repairable_controller_initial_binding_sha256": preregistration[
            "repairable_controller_initial_binding_sha256"
        ],
        "implementation_binding_sha256": preregistration[
            "implementation_binding_sha256"
        ],
        "preregistration_artifact_sha256": preregistration["artifact_sha256"],
        "preregistration_document_sha256": preregistration["document_sha256"],
        "journal_schema_sha256": JOURNAL_SCHEMA_SHA256,
        "capture_schema_sha256": json_sha256(capture_schema()),
        "archive_schema_sha256": json_sha256(archive_schema()),
        "maximum_controller_repair_commits": MAXIMUM_CONTROLLER_REPAIR_COMMITS,
        "current_commit_must_descend_from_original": True,
        "controller_repair_cannot_reset_arm_consumption": True,
        "retry_count": 0,
        "automatic_follow_on": False,
    }


def validate_external_authority(
    repository: Path,
    authority: Mapping[str, Any],
    *,
    current_commit: str,
    expected_model_sha256: str,
    expected_binary_sha256: str,
) -> None:
    if not isinstance(authority, Mapping):
        raise ParentDependenceError("authority is not an object")
    if set(authority) != set(authority_object_schema()["required"]):
        raise ParentDependenceError("authority field set changed")
    _require_sha(authority.get("authority_id_sha256"), "authority ID hash")
    original = str(authority.get("authorized_commit", ""))
    is_controller_repair = current_commit != original
    expected = _expected_authority_body(
        repository,
        authority,
        require_current_controller=not is_controller_repair,
    )
    _require(
        dict(authority) == expected
        and authority.get("original_authorized_execution_commit")
        == original
        and expected_model_sha256 == MODEL_SHA256
        and expected_binary_sha256 == BINARY_SHA256,
        "external authority scope mismatch",
    )
    if is_controller_repair:
        _controller_repair_report(
            repository,
            authority,
            current_commit=current_commit,
            events=None,
        )
    else:
        _require(original == current_commit, "external authority scope mismatch")
    # The stable schema deliberately does not enumerate this experiment ID.
    experiment_schema = authority_object_schema()["properties"]["experiment_id"]
    _require(
        "const" not in experiment_schema and "enum" not in experiment_schema,
        "authority schema was versioned per experiment",
    )


def authority_hmac(repository: Path, authority: Mapping[str, Any]) -> str:
    runtime = _source_runtime(repository)
    return hmac.new(
        _experiment_key(runtime),
        AUTHORITY_HMAC_DOMAIN + canonical_json_bytes(authority),
        hashlib.sha256,
    ).hexdigest().upper()


def _receipt_document(repository: Path, authority: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "authority": dict(authority),
        "authority_object_schema_sha256": AUTHORITY_OBJECT_SCHEMA_SHA256,
        "authority_receipt_schema_sha256": AUTHORITY_RECEIPT_SCHEMA_SHA256,
        "authority_hmac": authority_hmac(repository, authority),
        "consumed": True,
    }


def verify_authority_receipt_bytes(
    repository: Path,
    payload: bytes,
    *,
    require_current_static: bool = True,
) -> dict[str, Any]:
    if not isinstance(payload, bytes) or len(payload) > 64 * 1024:
        raise ParentDependenceError("authority receipt is unsafe")
    document = _json_object(payload, "authority receipt")
    authority = document.get("authority")
    if not isinstance(authority, dict):
        raise ParentDependenceError("authority receipt body is malformed")
    expected = _receipt_document(repository, authority)
    _require(document == expected, "authority receipt binding changed")
    if require_current_static:
        try:
            current_commit = _git(repository, "rev-parse", "HEAD")
        except ParentDependenceError:
            current_commit = str(authority.get("authorized_commit", ""))
        if current_commit == authority.get("authorized_commit"):
            validate_external_authority(
                repository,
                authority,
                current_commit=current_commit,
                expected_model_sha256=str(authority.get("model_sha256", "")),
                expected_binary_sha256=str(authority.get("binary_sha256", "")),
            )
        else:
            _controller_repair_report(
                repository,
                authority,
                current_commit=current_commit,
                events=None,
            )
    return {
        "authority": authority,
        "authority_receipt_sha256": sha256_bytes(payload),
        "authority_hmac": document["authority_hmac"],
        "consumed": True,
        "maximum_model_generations_per_arm": 1,
        "maximum_total_model_generations": 2,
        "retry_allowed": False,
    }


def _git_is_ancestor(repository: Path, ancestor: str, descendant: str) -> bool:
    process = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
    )
    if process.returncode not in {0, 1}:
        raise ParentDependenceError("Git ancestry verification failed")
    return process.returncode == 0


def _controller_repair_report(
    repository: Path,
    authority: Mapping[str, Any],
    *,
    current_commit: str,
    events: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Validate a descendant-only controller repair without using new authority."""
    repository = repository.resolve(strict=False)
    _require(
        isinstance(authority, Mapping)
        and set(authority) == set(authority_object_schema()["required"]),
        "consumed authority field set changed",
    )
    original = str(authority.get("original_authorized_execution_commit", ""))
    _require(
        GIT_COMMIT_RE.fullmatch(original) is not None
        and GIT_COMMIT_RE.fullmatch(current_commit) is not None
        and _git_is_ancestor(repository, original, current_commit),
        "controller repair commit is not a descendant of the original execution commit",
    )
    _require(
        authority.get("model_sha256") == MODEL_SHA256
        and authority.get("authorized_commit") == original
        and authority.get("binary_sha256") == BINARY_SHA256
        and authority.get("carrier_root_sha256") == CARRIER_ROOT_SHA256
        and authority.get("source_evidence_sha256") == SOURCE_HASHES
        and authority.get("source_publication_record_sha256")
        == SOURCE_PUBLICATION_SHA256
        and authority.get("arm_ids") == list(ARM_IDS)
        and authority.get("arm_request_sha256")
        == scientific.EXPECTED_ARM_REQUEST_SHA256
        and authority.get("maximum_model_generations_per_arm") == 1
        and authority.get("maximum_total_model_generations") == 2
        and authority.get("maximum_controller_repair_commits")
        == MAXIMUM_CONTROLLER_REPAIR_COMMITS
        and authority.get("current_commit_must_descend_from_original") is True
        and authority.get("controller_repair_cannot_reset_arm_consumption") is True
        and authority.get("automatic_follow_on") is False
        and authority.get("retry_count") == 0,
        "controller repair changed the scientific authority",
    )
    preregistration = validate_preregistration(
        repository,
        require_current_controller=False,
    )
    frozen = _frozen_scientific_binding(repository)
    isolation = request_isolation_report(repository)
    _require(
        frozen["sha256"]
        == authority.get("frozen_scientific_execution_binding_sha256")
        == preregistration["frozen_scientific_execution_binding_sha256"]
        and isolation["arm_request_sha256"]
        == authority.get("arm_request_sha256")
        == scientific.EXPECTED_ARM_REQUEST_SHA256
        and preregistration["artifact_sha256"]
        == authority.get("preregistration_artifact_sha256")
        and preregistration["document_sha256"]
        == authority.get("preregistration_document_sha256")
        and preregistration["implementation_binding_sha256"]
        == authority.get("implementation_binding_sha256")
        and preregistration["repairable_controller_initial_binding_sha256"]
        == authority.get("repairable_controller_initial_binding_sha256"),
        "controller repair crossed an immutable binding",
    )
    commits = (
        []
        if current_commit == original
        else _git(
            repository,
            "rev-list",
            "--reverse",
            "--ancestry-path",
            f"{original}..{current_commit}",
        ).splitlines()
    )
    _require(
        len(commits) <= MAXIMUM_CONTROLLER_REPAIR_COMMITS,
        "controller repair budget exceeded",
    )
    changed_paths: set[str] = set()
    for commit in commits:
        parents = _git(repository, "rev-list", "--parents", "-n", "1", commit).split()
        _require(len(parents) == 2, "controller repair history must remain linear")
        paths = _git(
            repository,
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit,
        ).splitlines()
        changed_paths.update(path.replace("\\", "/") for path in paths if path)
    _require(
        changed_paths <= ALLOWED_CONTROLLER_REPAIR_PATHS,
        "controller repair changed a path outside the repair policy",
    )
    repair_events = (
        []
        if events is None
        else [
            event
            for event in events
            if event.get("state") == "controller-repair-observed"
            and event.get("arm_id") is None
        ]
    )
    _require(
        len(repair_events) <= MAXIMUM_CONTROLLER_REPAIR_COMMITS,
        "journal controller repair budget exceeded",
    )
    previous = (
        str(repair_events[-1]["facts"]["current_replay_commit"])
        if repair_events
        else original
    )
    _require(
        _git_is_ancestor(repository, previous, current_commit),
        "controller repair replay history diverged",
    )
    transition_paths = sorted(
        path.replace("\\", "/")
        for path in _git(
            repository,
            "diff",
            "--name-only",
            previous,
            current_commit,
        ).splitlines()
        if path
    )
    previous_tree = _git(repository, "rev-parse", f"{previous}^{{tree}}")
    current_tree = _git(repository, "rev-parse", f"{current_commit}^{{tree}}")
    diff_body = {
        "previous_replay_commit": previous,
        "previous_tree": previous_tree,
        "current_replay_commit": current_commit,
        "current_tree": current_tree,
        "changed_paths": transition_paths,
    }
    controller = _repairable_controller_binding(repository)
    return {
        "original_execution_commit": original,
        "previous_replay_commit": previous,
        "current_replay_commit": current_commit,
        "changed_tree_diff_sha256": json_sha256(diff_body),
        "changed_paths": transition_paths,
        "frozen_scientific_execution_binding_sha256": frozen["sha256"],
        "repairable_controller_binding_sha256": controller["sha256"],
        "arm_request_sha256": dict(isolation["arm_request_sha256"]),
        "controller_repair_commit_count": len(commits),
        "model_generations_issued": 0,
        "already_observed": previous == current_commit,
    }


def verify_authority_receipt(
    repository: Path,
    *,
    require_current_static: bool = True,
) -> dict[str, Any]:
    path = receipt_path(repository)
    return verify_authority_receipt_bytes(
        repository,
        _require_regular(path, "authority receipt", maximum=64 * 1024),
        require_current_static=require_current_static,
    )


@contextmanager
def _authority_lock(repository: Path) -> Iterator[None]:
    lock = repository.resolve(strict=False) / STATE_ROOT / ".authority.lock"
    balanced._assert_safe_ancestry(repository, lock)
    _require_ignored(repository, lock)
    lock.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock, os.O_RDWR | os.O_CREAT, stat.S_IRUSR | stat.S_IWUSR)
    try:
        if os.name == "nt":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ParentDependenceError("authority consumption is already active") from exc
        else:
            import fcntl

            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ParentDependenceError("authority consumption is already active") from exc
        yield
    finally:
        if os.name == "nt":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def consume_authority_once(
    repository: Path,
    authority: Mapping[str, Any],
    *,
    current_commit: str,
    expected_model_sha256: str,
    expected_binary_sha256: str,
) -> dict[str, Any]:
    repository = repository.resolve(strict=False)
    source_authority.assert_test_repository_isolated(repository)
    validate_external_authority(
        repository,
        authority,
        current_commit=current_commit,
        expected_model_sha256=expected_model_sha256,
        expected_binary_sha256=expected_binary_sha256,
    )
    target = receipt_path(repository)
    _require_ignored(repository, target)
    balanced._assert_safe_ancestry(repository, target)
    payload = canonical_json_bytes(_receipt_document(repository, authority))
    with _authority_lock(repository):
        if target.exists() or target.is_symlink():
            raise ParentDependenceError("parent-dependence authority was already consumed")
        _exclusive_write(target, payload)
    return verify_authority_receipt(repository)


def _event_body(
    *,
    sequence: int,
    state: str,
    arm_id: str | None,
    previous_event_sha256: str,
    facts: Mapping[str, Any],
    observed_at: str | None = None,
) -> dict[str, Any]:
    body = {
        "schema_version": JOURNAL_SCHEMA_VERSION,
        "sequence": sequence,
        "experiment_id": EXPERIMENT_ID,
        "state": state,
        "arm_id": arm_id,
        "observed_at": observed_at or _utc_now(),
        "previous_event_sha256": previous_event_sha256,
        "facts": dict(facts),
    }
    balanced.validate_metadata_only(body)
    return body


def _repository_from_evidence_path(path: Path) -> Path:
    resolved = path.resolve(strict=False)
    for candidate in (resolved, *resolved.parents):
        marker = candidate / ".git"
        if marker.exists() or marker.is_symlink():
            return candidate
    raise ParentDependenceError("evidence path is not inside a repository")


def _evidence_hmac(repository: Path, domain: bytes, body: Mapping[str, Any]) -> str:
    return hmac.new(
        _experiment_key(_source_runtime(repository.resolve(strict=False))),
        domain + canonical_json_bytes(body),
        hashlib.sha256,
    ).hexdigest().upper()


def _validate_journal_transition(
    prior: Sequence[Mapping[str, Any]],
    state: str,
    arm_id: str | None,
    facts: Mapping[str, Any],
) -> None:
    allowed = set(journal_event_schema()["states"])
    _require(state in allowed, "unknown journal state")
    counts: dict[tuple[str, str | None], int] = {}
    for event in prior:
        key = (str(event["state"]), event.get("arm_id"))
        counts[key] = counts.get(key, 0) + 1
    if not prior:
        _require(state == "prepared" and arm_id is None, "journal must start prepared")
        return
    _require(state != "prepared", "prepared may occur only once")
    if state == "authority-consumed":
        _require(
            len(prior) == 1
            and prior[0]["state"] == "prepared"
            and arm_id is None,
            "authority-consumed transition is invalid",
        )
        return
    _require(
        counts.get(("authority-consumed", None), 0) == 1,
        "arm work requires consumed authority",
    )
    if state == "controller-repair-observed":
        _require(
            arm_id is None
            and counts.get(("controller-repair-observed", None), 0)
            < MAXIMUM_CONTROLLER_REPAIR_COMMITS
            and counts.get(("terminal-written", None), 0) == 0
            and counts.get(("archived", None), 0) == 0,
            "controller repair transition is invalid",
        )
        required = {
            "original_execution_commit",
            "previous_replay_commit",
            "current_replay_commit",
            "changed_tree_diff_sha256",
            "changed_paths",
            "frozen_scientific_execution_binding_sha256",
            "repairable_controller_binding_sha256",
            "arm_request_sha256",
            "controller_repair_commit_count",
            "model_generations_issued",
        }
        _require(
            set(facts) == required
            and facts.get("model_generations_issued") == 0
            and isinstance(facts.get("changed_paths"), list)
            and 1 <= int(facts.get("controller_repair_commit_count", 0))
            <= MAXIMUM_CONTROLLER_REPAIR_COMMITS,
            "controller repair facts are malformed",
        )
        for key in (
            "changed_tree_diff_sha256",
            "frozen_scientific_execution_binding_sha256",
            "repairable_controller_binding_sha256",
        ):
            _require_sha(facts.get(key), key)
        _require(
            facts.get("arm_request_sha256")
            == scientific.EXPECTED_ARM_REQUEST_SHA256,
            "controller repair request binding changed",
        )
        return
    if state == "request-started":
        _require(arm_id in ARM_IDS, "request-started arm is invalid")
        _require(
            counts.get(("request-started", arm_id), 0) == 0,
            "duplicate model generation is forbidden",
        )
        arm_index = ARM_IDS.index(str(arm_id))
        for earlier in ARM_IDS[:arm_index]:
            _require(
                counts.get(("response-captured", earlier), 0) == 1
                or counts.get(("adjudicated", earlier), 0) == 1,
                "arm order or prior disposition changed",
            )
        _require(
            facts.get("generation_ordinal") == arm_index + 1
            and facts.get("maximum_generations_for_arm") == 1,
            "request-started generation accounting changed",
        )
        return
    if state == "response-captured":
        _require(
            arm_id in ARM_IDS
            and counts.get(("request-started", arm_id), 0) == 1
            and counts.get(("response-captured", arm_id), 0) == 0
            and counts.get(("adjudicated", arm_id), 0) == 0,
            "response capture transition is invalid",
        )
        _require_sha(facts.get("capture_sha256"), "capture hash")
        _require(facts.get("captured_before_parsing") is True, "capture order changed")
        return
    if state == "request-custody-observed":
        _require(
            arm_id in ARM_IDS
            and counts.get(("response-captured", arm_id), 0) == 1
            and counts.get(("request-custody-observed", arm_id), 0) == 0
            and counts.get(("adjudicated", arm_id), 0) == 0
            and facts.get("passed") is True,
            "request custody transition is invalid",
        )
        return
    if state == "finalization-observed":
        _require(
            arm_id is None
            and counts.get(("finalization-observed", None), 0) == 0
            and all(
                counts.get(("response-captured", candidate), 0) == 1
                or counts.get(("adjudicated", candidate), 0) == 1
                for candidate in ARM_IDS
            ),
            "finalization transition is invalid",
        )
        _require(
            isinstance(facts.get("cleanup"), dict)
            and isinstance(facts.get("postflight"), dict)
            and isinstance(facts.get("gates_passed"), bool),
            "finalization facts are malformed",
        )
        if facts.get("gates_passed") is True:
            _require(
                all(
                    counts.get(("response-captured", candidate), 0) == 0
                    or counts.get(("request-custody-observed", candidate), 0) == 1
                    for candidate in ARM_IDS
                ),
                "passing finalization lacks per-arm request custody",
            )
        return
    if state == "adjudicated":
        _require(
            arm_id in ARM_IDS
            and counts.get(("request-started", arm_id), 0) == 1
            and counts.get(("adjudicated", arm_id), 0) == 0,
            "adjudication transition is invalid",
        )
        captured = counts.get(("response-captured", arm_id), 0) == 1
        _require(
            captured or facts.get("classification") == INCONCLUSIVE_CLASSIFICATION,
            "uncaptured response may only be inconclusive",
        )
        if captured:
            for candidate in ARM_IDS:
                _require(
                    counts.get(("response-captured", candidate), 0) == 1
                    or counts.get(("adjudicated", candidate), 0) == 1,
                    "private adjudication began before both arm selections froze",
                )
        if facts.get("classification") != INCONCLUSIVE_CLASSIFICATION:
            finalization = _event_for(prior, "finalization-observed")
            _require(
                finalization is not None
                and counts.get(("request-custody-observed", arm_id), 0) == 1
                and finalization["facts"].get("gates_passed") is True,
                "scientific adjudication requires passed durable finalization",
            )
        return
    if state == "terminal-written":
        _require(
            arm_id is None
            and all(counts.get(("adjudicated", candidate), 0) == 1 for candidate in ARM_IDS)
            and counts.get(("finalization-observed", None), 0) == 1
            and counts.get(("terminal-written", None), 0) == 0,
            "terminal transition is invalid",
        )
        _require_sha(facts.get("result_sha256"), "terminal result hash")
        _require_sha(facts.get("closure_sha256"), "terminal closure hash")
        return
    if state == "archived":
        _require(
            arm_id is None
            and counts.get(("terminal-written", None), 0) == 1
            and counts.get(("archived", None), 0) == 0,
            "archive transition is invalid",
        )
        _require_sha(facts.get("archive_sha256"), "archive hash")
        return
    raise ParentDependenceError("journal transition was not handled")


def verify_journal_bytes(
    data: bytes,
    *,
    repository: Path,
    allow_archived: bool = True,
) -> list[dict[str, Any]]:
    if not isinstance(data, bytes) or len(data) > MAX_STATE_BYTES:
        raise ParentDependenceError("journal is unsafe")
    if not data:
        return []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParentDependenceError("journal is not UTF-8") from exc
    if not text.endswith("\n"):
        raise ParentDependenceError("journal has a torn final record")
    events: list[dict[str, Any]] = []
    previous = GENESIS_HASH
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line:
            raise ParentDependenceError("journal contains an empty record")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ParentDependenceError("journal contains invalid JSON") from exc
        if not isinstance(event, dict) or line != canonical_json_text(event):
            raise ParentDependenceError("journal record is not canonical")
        expected_fields = set(journal_event_schema()["required_fields"])
        if set(event) != expected_fields:
            raise ParentDependenceError("journal event field set changed")
        body = {
            key: event[key]
            for key in event
            if key not in {"event_sha256", "event_hmac_sha256"}
        }
        event_sha256 = json_sha256(body)
        authenticated = {**body, "event_sha256": event_sha256}
        _require(
            event.get("schema_version") == JOURNAL_SCHEMA_VERSION
            and event.get("sequence") == line_number
            and event.get("experiment_id") == EXPERIMENT_ID
            and event.get("previous_event_sha256") == previous
            and event.get("event_sha256") == event_sha256
            and hmac.compare_digest(
                str(event.get("event_hmac_sha256", "")),
                _evidence_hmac(repository, JOURNAL_HMAC_DOMAIN, authenticated),
            ),
            "journal hash chain or authentication changed",
        )
        facts = event.get("facts")
        if not isinstance(facts, dict):
            raise ParentDependenceError("journal facts are malformed")
        _validate_journal_transition(
            events,
            str(event.get("state")),
            event.get("arm_id"),
            facts,
        )
        previous = str(event["event_sha256"])
        events.append(event)
    if not allow_archived and any(event["state"] == "archived" for event in events):
        raise ParentDependenceError("archived event is outside terminal archive prefix")
    return events


def read_journal(path: Path) -> list[dict[str, Any]]:
    if not path.exists() and not path.is_symlink():
        return []
    return verify_journal_bytes(
        _require_regular(path, "journal"),
        repository=_repository_from_evidence_path(path),
    )


def append_journal_event(
    path: Path,
    state: str,
    *,
    arm_id: str | None = None,
    facts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    events = read_journal(path)
    fact_body = dict(facts or {})
    _validate_journal_transition(events, state, arm_id, fact_body)
    previous = events[-1]["event_sha256"] if events else GENESIS_HASH
    body = _event_body(
        sequence=len(events) + 1,
        state=state,
        arm_id=arm_id,
        previous_event_sha256=str(previous),
        facts=fact_body,
    )
    event_sha256 = json_sha256(body)
    authenticated = {**body, "event_sha256": event_sha256}
    event = {
        **authenticated,
        "event_hmac_sha256": _evidence_hmac(
            _repository_from_evidence_path(path),
            JOURNAL_HMAC_DOMAIN,
            authenticated,
        ),
    }
    line = canonical_json_bytes(event) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    balanced._assert_safe_ancestry(path.parents[3], path)
    mode = "r+b" if path.exists() else "x+b"
    with path.open(mode) as handle:
        handle.seek(0, os.SEEK_END)
        prior_size = handle.tell()
        try:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            handle.truncate(prior_size)
            handle.flush()
            os.fsync(handle.fileno())
            raise
    verified = read_journal(path)
    if verified[-1] != event:
        raise ParentDependenceError("journal append did not verify")
    return event


def _event_for(
    events: Sequence[Mapping[str, Any]],
    state: str,
    arm_id: str | None = None,
) -> Mapping[str, Any] | None:
    matches = [
        event
        for event in events
        if event.get("state") == state and event.get("arm_id") == arm_id
    ]
    if len(matches) > 1:
        raise ParentDependenceError("journal contains duplicate state")
    return matches[0] if matches else None


def _observe_controller_repair(
    repository: Path,
    paths: Mapping[str, Path],
    *,
    authority: Mapping[str, Any],
    current_commit: str,
) -> dict[str, Any]:
    """Authenticate and append one zero-generation repair transition."""
    events = read_journal(paths["journal"])
    report = _controller_repair_report(
        repository,
        authority,
        current_commit=current_commit,
        events=events,
    )
    for event in events:
        if event.get("state") != "request-started":
            continue
        arm_id = str(event.get("arm_id", ""))
        _require(
            arm_id in ARM_IDS
            and event.get("facts", {}).get("model_request_sha256")
            == scientific.EXPECTED_ARM_REQUEST_SHA256[arm_id],
            "started request differs from the frozen arm request",
        )
    receipt_before = _require_regular(paths["receipt"], "authority receipt")
    journal_before = _require_regular(paths["journal"], "journal")
    capture_before: dict[str, bytes] = {}
    experiment_key = _experiment_key(_source_runtime(repository))
    for arm_id in ARM_IDS:
        captured = _event_for(events, "response-captured", arm_id)
        if captured is None:
            continue
        started = _event_for(events, "request-started", arm_id)
        _require(started is not None, "captured arm lacks request-started custody")
        path = _capture_path(paths, arm_id)
        capture_before[arm_id] = _require_regular(path, "response capture")
        verified = scientific.verify_capture(
            path,
            experiment_key=experiment_key,
            arm_id=arm_id,
            model_request_sha256=str(started["facts"]["model_request_sha256"]),
        )
        _require(
            verified["capture_sha256"] == captured["facts"].get("capture_sha256"),
            "captured response differs from its journal binding",
        )
    if current_commit == authority["authorized_commit"] or report["already_observed"]:
        return report
    facts = {key: value for key, value in report.items() if key != "already_observed"}
    append_journal_event(
        paths["journal"],
        "controller-repair-observed",
        facts=facts,
    )
    _require(
        _require_regular(paths["receipt"], "authority receipt") == receipt_before,
        "controller repair rewrote the authority receipt",
    )
    journal_after = _require_regular(paths["journal"], "journal")
    _require(
        journal_after.startswith(journal_before) and len(journal_after) > len(journal_before),
        "controller repair did not preserve the exact journal prefix",
    )
    for arm_id, before in capture_before.items():
        _require(
            _require_regular(_capture_path(paths, arm_id), "response capture") == before,
            "controller repair rewrote a captured response",
        )
    return report


def _capture_value(execution: Any, name: str) -> Any:
    if isinstance(execution, Mapping):
        return execution.get(name)
    return getattr(execution, name, None)


class _RawResponseSpool:
    """Durably record each raw SSE line before the harness parses it."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: Any | None = None
        self.byte_size = 0

    def __enter__(self) -> "_RawResponseSpool":
        repository = _repository_from_evidence_path(self.path)
        _require_ignored(repository, self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        balanced._assert_safe_ancestry(repository, self.path)
        self.handle = self.path.open("xb")
        return self

    def record(self, raw_line: bytes) -> None:
        if self.handle is None or not isinstance(raw_line, bytes):
            raise ParentDependenceError("raw response recorder is not active")
        if self.byte_size + len(raw_line) > MAX_RAW_RESPONSE_BYTES:
            raise ParentDependenceError("raw response capture exceeds byte ceiling")
        self.handle.write(raw_line)
        self.handle.flush()
        os.fsync(self.handle.fileno())
        self.byte_size += len(raw_line)

    def __exit__(self, *_args: object) -> None:
        if self.handle is not None:
            self.handle.close()
            self.handle = None


def capture_execution(
    path: Path,
    *,
    arm_id: str,
    model_request_sha256: str,
    execution: Any,
    raw_response_bytes: bytes,
) -> dict[str, Any]:
    if arm_id not in ARM_IDS:
        raise ParentDependenceError("capture arm changed")
    if not isinstance(raw_response_bytes, bytes) or not raw_response_bytes:
        raise ParentDependenceError("raw response capture is empty")
    if len(raw_response_bytes) > MAX_RAW_RESPONSE_BYTES:
        raise ParentDependenceError("raw response capture exceeds byte ceiling")
    body = {
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "arm_id": arm_id,
        "model_request_sha256": _require_sha(
            model_request_sha256,
            "capture model request",
        ),
        "captured_before_parsing": True,
        "raw_response_capture": {
            "encoding": "base64",
            "byte_size": len(raw_response_bytes),
            "sha256": sha256_bytes(raw_response_bytes),
            "bytes": base64.b64encode(raw_response_bytes).decode("ascii"),
        },
        "execution": {name: _capture_value(execution, name) for name in _CAPTURE_EXECUTION_FIELDS},
    }
    authenticated = {
        **body,
        "capture_hmac_sha256": _evidence_hmac(
            _repository_from_evidence_path(path),
            CAPTURE_HMAC_DOMAIN,
            body,
        ),
    }
    data = canonical_json_bytes(authenticated)
    if len(data) > MAX_CAPTURE_BYTES:
        raise ParentDependenceError("response capture exceeds byte ceiling")
    _exclusive_write(path, data)
    verified = verify_capture(path, arm_id=arm_id, model_request_sha256=model_request_sha256)
    return verified


def verify_capture(
    path: Path,
    *,
    arm_id: str,
    model_request_sha256: str,
) -> dict[str, Any]:
    try:
        data = _require_regular(path, "response capture", maximum=MAX_CAPTURE_BYTES)
        body = _json_object(data, "response capture")
    except ParentDependenceError as exc:
        raise CapturedResponseInvalidError(
            "response capture is missing, unsafe, or malformed"
        ) from exc
    if not (
        set(body) == {
            "schema_version",
            "experiment_id",
            "arm_id",
            "model_request_sha256",
            "captured_before_parsing",
            "raw_response_capture",
            "execution",
            "capture_hmac_sha256",
        }
        and body.get("schema_version") == CAPTURE_SCHEMA_VERSION
        and body.get("experiment_id") == EXPERIMENT_ID
        and body.get("arm_id") == arm_id
        and body.get("model_request_sha256") == model_request_sha256
        and body.get("captured_before_parsing") is True
    ):
        raise CapturedResponseInvalidError("response capture identity changed")
    authenticated = {key: value for key, value in body.items() if key != "capture_hmac_sha256"}
    if not hmac.compare_digest(
            str(body.get("capture_hmac_sha256", "")),
            _evidence_hmac(
                _repository_from_evidence_path(path),
                CAPTURE_HMAC_DOMAIN,
                authenticated,
            ),
        ):
        raise CapturedResponseInvalidError(
            "response capture authentication changed"
        )
    execution = body.get("execution")
    if not (
        isinstance(execution, dict)
        and set(execution) == set(_CAPTURE_EXECUTION_FIELDS)
    ):
        raise CapturedResponseInvalidError(
            "response capture execution field set changed"
        )
    raw = body.get("raw_response_capture")
    if not isinstance(raw, dict):
        raise CapturedResponseInvalidError("raw response capture is malformed")
    try:
        raw_bytes = base64.b64decode(str(raw.get("bytes", "")), validate=True)
    except (ValueError, TypeError) as exc:
        raise CapturedResponseInvalidError(
            "raw response capture encoding changed"
        ) from exc
    if not (
        set(raw) == {"encoding", "byte_size", "sha256", "bytes"}
        and raw.get("encoding") == "base64"
        and raw.get("byte_size") == len(raw_bytes)
        and raw.get("sha256") == sha256_bytes(raw_bytes)
        and bool(raw_bytes)
    ):
        raise CapturedResponseInvalidError(
            "raw response capture identity changed"
        )
    return {**body, "capture_sha256": sha256_bytes(data)}


def replay_capture(capture: Mapping[str, Any]) -> SimpleNamespace:
    execution = capture.get("execution")
    if not isinstance(execution, Mapping):
        raise ParentDependenceError("capture cannot be replayed")
    return SimpleNamespace(**dict(execution))


def _freeze_captured_arm(
    repository: Path,
    arm_id: str,
    capture: Mapping[str, Any],
    rendered_tokens: int,
) -> tuple[integration.RankHeadV2Runtime, dict[str, Any], Any, dict[str, Any]]:
    source_runtime = _source_runtime(repository)
    runtime = _arm_runtime(repository, source_runtime, arm_id)
    try:
        transport = kernel._normalized_transport(
            replay_capture(capture),
            rendered_tokens=rendered_tokens,
            max_tokens=64,
        )
        structured = runtime.parse_response(
            "transform",
            transport["structured_content"],
        )
        transform = runtime.normalize_transform(
            structured["operator"],
            structured["ranking"],
        )
        frozen = v2.freeze_rank_head_selection(runtime, transform)
    except (
        runtime_support.CatalyticInferenceRuntimeError,
        balanced.BalancedOpaqueError,
        integration.RankHeadV2IntegrationError,
        v2.RankHeadDesignError,
    ) as exc:
        raise CapturedResponseInvalidError(
            "captured transform response failed its frozen data contract"
        ) from exc
    return runtime, transform, frozen, transport["metadata"]


def _adjudicate_frozen_arm(
    runtime: integration.RankHeadV2Runtime,
    transform: Mapping[str, Any],
    frozen: Any,
    arm_id: str,
) -> dict[str, Any]:
    extraction = v2.build_deterministic_extraction_receipt(
        runtime,
        transform,
        frozen=frozen,
    )
    evaluation = extraction["controller_private_evaluation"]
    reproduced = bool(
        evaluation["mapped_to_full_public_support"] is True
        and evaluation["full_public_score"] == 5
        and evaluation["full_public_total"] == 5
    )
    spec = ARM_BY_ID[arm_id]
    classification = (
        spec["not_shown_classification"]
        if reproduced
        else spec["supported_classification"]
    )
    return {
        "arm_id": arm_id,
        "classification": classification,
        "status": "adjudicated",
        "transform_operator": transform["operator"],
        "transform_artifact_commitment": transform["artifact_commitment"],
        "transform_ranking_length": len(transform["ranking"]),
        "selection_frozen_before_private_mapping": True,
        "private_mapping_consulted_before_selection": False,
        "selected_rank": 0,
        "selected_own_private_singleton": bool(
            evaluation["mapped_to_full_public_support"]
        ),
        "private_public_score": int(evaluation["full_public_score"]),
        "private_public_total": int(evaluation["full_public_total"]),
        "deterministic_extraction_commitment": extraction["artifact_commitment"],
        "claiming": False,
    }


def build_preregistration_document(repository: Path) -> dict[str, Any]:
    repository = repository.resolve(strict=False)
    source = verify_source_evidence(repository)
    isolation = request_isolation_report(repository)
    implementation = _implementation_binding(repository)
    document = {
        "schema_version": PREREGISTRATION_SCHEMA_VERSION,
        "status": "static-preregistered-unexecuted",
        "experiment_id": EXPERIMENT_ID,
        "protected_starting_main": STARTING_PROTECTED_MAIN,
        "hypothesis": (
            "Under the independently keyed binding-2 replay, replacing either "
            "complete transform parent with its exact commitment-only projection "
            "changes whether deterministic rank-zero extraction recovers the frozen "
            "private singleton."
        ),
        "source_custody": source,
        "intervention": {
            "arms": [dict(item) for item in ARM_SPECS],
            "source_of_complete_parents": SOURCE_ARCHIVE_PATH.as_posix(),
            "branch_requests_reexecuted": False,
            "borrow_request_reexecuted": False,
            "full_information_request_reexecuted": False,
            "transform_requests": 2,
            "model_generations_per_arm": 1,
            "total_future_model_generations": 2,
            "deterministic_rank_head": 0,
            "selection_frozen_before_private_mapping": True,
            "private_mapping_or_score_model_visible": False,
        },
        "request_isolation": isolation,
        "authority_contract": {
            "schema_version": AUTHORITY_SCHEMA_VERSION,
            "authority_kind": AUTHORITY_KIND,
            "object_schema_sha256": AUTHORITY_OBJECT_SCHEMA_SHA256,
            "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
            "receipt_schema_sha256": AUTHORITY_RECEIPT_SCHEMA_SHA256,
            "receipt_path_template": RECEIPT_TEMPLATE,
            "one_authority_for_exact_arm_set": True,
            "per_arm_consumption_record": "request-started journal event",
            "original_execution_commit_bound": True,
            "frozen_scientific_execution_binding_bound": True,
            "exact_arm_request_hashes_bound": True,
            "repairable_controller_initial_binding_bound": True,
            "maximum_controller_repair_commits": MAXIMUM_CONTROLLER_REPAIR_COMMITS,
            "current_commit_must_descend_from_original": True,
            "repair_transition_model_generations": 0,
            "controller_repair_resets_arm_consumption": False,
            "raw_authority_id_persisted": False,
            "schema_accepts_generic_experiment_identity": True,
            "automatic_follow_on": False,
        },
        "transaction_contract": {
            "journal_schema": journal_event_schema(),
            "journal_schema_sha256": JOURNAL_SCHEMA_SHA256,
            "capture_schema": capture_schema(),
            "capture_schema_sha256": json_sha256(capture_schema()),
            "archive_schema": archive_schema(),
            "archive_schema_sha256": json_sha256(archive_schema()),
            "response_captured_before_transport_parsing": True,
            "captured_response_replay_without_model_contact": True,
            "expected_captured_response_invalidity": (
                "scientific-inconclusive-under-explicit-domain-exception"
            ),
            "unexpected_controller_exception": (
                "raise-with-captures-and-finalization-preserved-no-adjudication"
            ),
            "restart_custody_reconciliation": (
                "no-sidecar-no-model-contact-before-deterministic-replay"
            ),
            "missing_request_custody_event": (
                "append-only-after-passed-restart-reconciliation"
            ),
            "controller_repair_event": "authenticated-append-only-before-resume",
            "controller_repair_rejects_before_model_contact": True,
            "existing_receipt_journal_and_captures_rewritten": False,
            "request_started_without_exact_capture": "terminal-inconclusive-no-retry",
            "duplicate_request_started": "rejected",
            "terminal_archive_content_addressed": True,
            "restore_policy": "missing-or-byte-identical-only",
        },
        "classification_contract": {
            "per_arm": {
                item["arm_id"]: {
                    "supported": item["supported_classification"],
                    "not_shown": item["not_shown_classification"],
                    "malformed_inconsistent_or_transport_invalid": INCONCLUSIVE_CLASSIFICATION,
                }
                for item in ARM_SPECS
            },
            "no_prejudgment": True,
            "replicated_directional_or_bilateral_claim_requires": [
                "both binding-2 arms support",
                "binding-1 causal package remains byte-exact and verified",
            ],
        },
        "implementation_binding": implementation,
        "execution_state": {
            "authority_created": False,
            "authority_consumed": False,
            "journal_created": False,
            "model_requests_issued": 0,
            "sidecar_launched": False,
            "live_execution_performed": False,
            "binding_2_full_information_consumed": True,
            "parent_dependence_replay_consumed": False,
        },
        "locked_claims": dict(LOCKED_CLAIMS),
        "next_action": (
            "Separately authorize ck0-balanced-v2-rank-head-b2-parent-"
            "dependence-r1 with one fresh external authority bound to the exact "
            "publication commit and this preregistration."
        ),
    }
    balanced.validate_metadata_only(document)
    return document


def write_preregistration(repository: Path) -> Path:
    repository = repository.resolve(strict=False)
    document = build_preregistration_document(repository)
    path = repository / PREREGISTRATION_PATH
    _atomic_json(path, document)
    return path


def validate_preregistration(
    repository: Path,
    *,
    require_current_controller: bool = True,
) -> dict[str, Any]:
    repository = repository.resolve(strict=False)
    path = repository / PREREGISTRATION_PATH
    data = _require_regular(path, "parent-dependence preregistration")
    document = _json_object(data, "parent-dependence preregistration")
    expected = build_preregistration_document(repository)
    implementation = document.get("implementation_binding")
    _require(isinstance(implementation, dict), "implementation binding is malformed")
    frozen = implementation.get("frozen_scientific_execution")
    controller = implementation.get("repairable_controller")
    _require(
        isinstance(frozen, dict)
        and isinstance(controller, dict)
        and implementation.get("sha256")
        == json_sha256(
            {
                "frozen_scientific_execution": frozen,
                "repairable_controller": controller,
            }
        ),
        "implementation binding is not self-consistent",
    )
    if not require_current_controller:
        current_frozen = expected["implementation_binding"][
            "frozen_scientific_execution"
        ]
        _require(frozen == current_frozen, "frozen scientific execution changed")
        expected["implementation_binding"] = implementation
    _require(document == expected, "preregistration differs from exact reconstruction")
    _require(
        document.get("execution_state", {}).get("model_requests_issued") == 0
        and document.get("execution_state", {}).get("authority_consumed") is False
        and document.get("status") == "static-preregistered-unexecuted",
        "observed result entered immutable preregistration",
    )
    current_controller = _repairable_controller_binding(repository)
    return {
        "status": "pass",
        "relative_path": PREREGISTRATION_PATH,
        "artifact_sha256": sha256_bytes(data),
        "document_sha256": json_sha256(document),
        "implementation_binding_sha256": implementation["sha256"],
        "frozen_scientific_execution_binding_sha256": frozen["sha256"],
        "repairable_controller_initial_binding_sha256": controller["sha256"],
        "repairable_controller_current_binding_sha256": current_controller["sha256"],
        "controller_repair_mode": not require_current_controller,
        "experiment_id": EXPERIMENT_ID,
        "arm_ids": list(ARM_IDS),
        "future_model_generations": 2,
        "authority_created": False,
        "authority_consumed": False,
        "live_execution_performed": False,
    }


def _manifest(
    repository: Path,
    public_preflight: Mapping[str, Any],
    authority: Mapping[str, Any],
) -> dict[str, Any]:
    current_commit = _git(repository, "rev-parse", "HEAD")
    preregistration = validate_preregistration(
        repository,
        require_current_controller=current_commit == authority["authorized_commit"],
    )
    preregistration = {
        key: value
        for key, value in preregistration.items()
        if key
        not in {
            "repairable_controller_current_binding_sha256",
            "controller_repair_mode",
        }
    }
    source = verify_source_evidence(repository)
    isolation = request_isolation_report(repository)
    manifest = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": "prepared",
        "protected_commit": authority["authorized_commit"],
        "source_custody": source,
        "preregistration": preregistration,
        "public_preflight": dict(public_preflight),
        "arm_ids": list(ARM_IDS),
        "arm_request_sha256": isolation["arm_request_sha256"],
        "frozen_scientific_execution_binding_sha256": authority[
            "frozen_scientific_execution_binding_sha256"
        ],
        "repairable_controller_initial_binding_sha256": authority[
            "repairable_controller_initial_binding_sha256"
        ],
        "maximum_controller_repair_commits": authority[
            "maximum_controller_repair_commits"
        ],
        "maximum_model_generations_per_arm": 1,
        "maximum_total_model_generations": 2,
        "physical_slots": 1,
        "parallelism": 1,
        "sidecar_epochs_maximum": 1,
        "response_capture_before_parsing": True,
        "captured_response_replay_without_model_contact": True,
        "request_started_without_capture": "inconclusive-no-retry",
        "authority_id_sha256": authority["authority_id_sha256"],
        "authority_object_schema_sha256": AUTHORITY_OBJECT_SCHEMA_SHA256,
        "authority_receipt_schema_sha256": AUTHORITY_RECEIPT_SCHEMA_SHA256,
        "journal_schema_sha256": JOURNAL_SCHEMA_SHA256,
        "claiming": False,
        "automatic_promotion": False,
    }
    _assert_public_no_smuggle(manifest)
    return manifest


def _forbidden_public_key(key: str) -> bool:
    lowered = key.lower()
    exact = {
        "candidate_alias",
        "support_aliases",
        "ranking",
        "alias_map",
        "alias_to_internal",
        "internal_to_alias",
        "private_root",
        "secret",
        "raw_authority_id",
        "cross_binding_correspondence",
    }
    return lowered in exact or lowered.endswith("_ranking")


def _assert_public_no_smuggle(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _forbidden_public_key(str(key)):
                raise ParentDependenceError("private correspondence entered public evidence")
            _assert_public_no_smuggle(item)
    elif isinstance(value, list):
        for item in value:
            _assert_public_no_smuggle(item)
    balanced.validate_metadata_only(value)


def _process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


@contextmanager
def run_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if not path.is_file() or balanced._is_reparse(path):
            raise ParentDependenceError("run lock is unsafe")
        try:
            prior_pid = int(path.read_text(encoding="ascii").strip())
        except (OSError, ValueError) as exc:
            raise ParentDependenceError("run lock is malformed") from exc
        if _process_exists(prior_pid):
            raise ParentDependenceError("another controller owns the run lock")
        path.unlink()
    _exclusive_write(path, f"{os.getpid()}\n".encode("ascii"))
    try:
        yield
    finally:
        if path.is_file() and not balanced._is_reparse(path):
            try:
                if int(path.read_text(encoding="ascii").strip()) == os.getpid():
                    path.unlink()
            except (OSError, ValueError):
                pass


@contextmanager
def controller_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, stat.S_IRUSR | stat.S_IWUSR)
    locked = False
    try:
        if os.name == "nt":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ParentDependenceError("another replay controller is active") from exc
        else:
            import fcntl

            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ParentDependenceError("another replay controller is active") from exc
        locked = True
        yield
    finally:
        if locked:
            if os.name == "nt":
                import msvcrt

                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
        if path.is_file() and not balanced._is_reparse(path):
            try:
                path.unlink()
            except OSError:
                pass


def _journal_adjudications(events: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    outcomes: dict[str, dict[str, Any]] = {}
    for arm_id in ARM_IDS:
        event = _event_for(events, "adjudicated", arm_id)
        if event is not None:
            facts = event.get("facts")
            if not isinstance(facts, dict):
                raise ParentDependenceError("adjudication facts are malformed")
            outcomes[arm_id] = dict(facts)
    return outcomes


def _inconclusive_facts(arm_id: str, reason: str) -> dict[str, Any]:
    return {
        "arm_id": arm_id,
        "status": "inconclusive",
        "classification": INCONCLUSIVE_CLASSIFICATION,
        "reason": reason,
        "selection_frozen_before_private_mapping": False,
        "private_mapping_consulted_before_selection": False,
        "claiming": False,
    }


def _capture_path(paths: Mapping[str, Path], arm_id: str) -> Path:
    return paths[f"capture-{arm_id}"]


def _partial_capture_path(paths: Mapping[str, Path], arm_id: str) -> Path:
    return paths[f"partial-capture-{arm_id}"]


def _partial_capture_facts(paths: Mapping[str, Path], arm_id: str) -> dict[str, Any]:
    path = _partial_capture_path(paths, arm_id)
    if not path.exists() and not path.is_symlink():
        return {}
    data = _require_regular(path, "partial raw response", maximum=MAX_RAW_RESPONSE_BYTES)
    return {
        "partial_response_sha256": sha256_bytes(data),
        "partial_response_byte_size": len(data),
    }


def _remove_bound_partial_capture(
    paths: Mapping[str, Path],
    arm_id: str,
    capture: Mapping[str, Any],
) -> None:
    path = _partial_capture_path(paths, arm_id)
    if not path.exists() and not path.is_symlink():
        return
    data = _require_regular(path, "partial raw response", maximum=MAX_RAW_RESPONSE_BYTES)
    raw = capture.get("raw_response_capture")
    _require(
        isinstance(raw, Mapping)
        and raw.get("byte_size") == len(data)
        and raw.get("sha256") == sha256_bytes(data),
        "raw response spool differs from the exact capture",
    )
    path.unlink()


def _recover_request_prefix(
    repository: Path,
    paths: Mapping[str, Path],
    arm_id: str,
) -> None:
    events = read_journal(paths["journal"])
    started = _event_for(events, "request-started", arm_id)
    captured = _event_for(events, "response-captured", arm_id)
    adjudicated = _event_for(events, "adjudicated", arm_id)
    if started is None or adjudicated is not None:
        return
    facts = started["facts"]
    request_sha = str(facts["model_request_sha256"])
    capture_path = _capture_path(paths, arm_id)
    if captured is None and capture_path.is_file() and not balanced._is_reparse(capture_path):
        capture = verify_capture(
            capture_path,
            arm_id=arm_id,
            model_request_sha256=request_sha,
        )
        append_journal_event(
            paths["journal"],
            "response-captured",
            arm_id=arm_id,
            facts={
                "capture_sha256": capture["capture_sha256"],
                "model_request_sha256": request_sha,
                "captured_before_parsing": True,
            },
        )
        _remove_bound_partial_capture(paths, arm_id, capture)
        return
    if captured is None:
        facts = _inconclusive_facts(arm_id, "request-started-without-exact-capture")
        facts.update(_partial_capture_facts(paths, arm_id))
        append_journal_event(
            paths["journal"],
            "adjudicated",
            arm_id=arm_id,
            facts=facts,
        )
        return
    verified = verify_capture(
        capture_path,
        arm_id=arm_id,
        model_request_sha256=request_sha,
    )
    _require(
        verified["capture_sha256"] == captured["facts"].get("capture_sha256"),
        "captured response bytes changed after journaling",
    )
    _remove_bound_partial_capture(paths, arm_id, verified)


def _write_terminal(
    repository: Path,
    paths: Mapping[str, Path],
    *,
    receipt: Mapping[str, Any],
    cleanup: Mapping[str, Any],
    postflight: Mapping[str, Any],
) -> dict[str, Any]:
    events = read_journal(paths["journal"])
    outcomes = _journal_adjudications(events)
    _require(set(outcomes) == set(ARM_IDS), "both arms must be adjudicated")
    finalization = _event_for(events, "finalization-observed")
    _require(
        finalization is not None
        and finalization["facts"].get("cleanup") == dict(cleanup)
        and finalization["facts"].get("postflight") == dict(postflight),
        "terminal custody differs from durable finalization",
    )
    receipt_data = _require_regular(paths["receipt"], "authority receipt")
    manifest_data = _require_regular(paths["manifest"], "manifest")
    journal_head_before_terminal = events[-1]["event_sha256"]
    classifications = {arm_id: outcomes[arm_id]["classification"] for arm_id in ARM_IDS}
    custody_gates_passed = (
        cleanup.get("passed") is True
        and cleanup.get("request_custody_passed", True) is True
        and postflight.get("passed") is True
    )
    result = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": (
            "complete"
            if custody_gates_passed
            and all(value != INCONCLUSIVE_CLASSIFICATION for value in classifications.values())
            else "inconclusive"
        ),
        "arm_order": list(ARM_IDS),
        "completed_model_generations": sum(
            1 for arm_id in ARM_IDS if _event_for(events, "request-started", arm_id)
        ),
        "maximum_model_generations": 2,
        "arm_outcomes": [outcomes[arm_id] for arm_id in ARM_IDS],
        "all_rank_heads_frozen_before_any_private_mapping": all(
            outcome.get("selection_frozen_before_private_mapping") is True
            for outcome in outcomes.values()
        ),
        "authority_receipt_sha256": sha256_bytes(receipt_data),
        "manifest_sha256": sha256_bytes(manifest_data),
        "journal_head_before_terminal": journal_head_before_terminal,
        "source_evidence_sha256": dict(SOURCE_HASHES),
        "source_publication_record_id": SOURCE_PUBLICATION_ID,
        "source_publication_record_sha256": SOURCE_PUBLICATION_SHA256,
        "cleanup": dict(cleanup),
        "postflight_custody": dict(postflight),
        "custody_gates_passed": custody_gates_passed,
        "claims": dict(LOCKED_CLAIMS),
        "claiming": False,
        "automatic_follow_on": False,
        "automatic_promotion": False,
    }
    _assert_public_no_smuggle(result)
    result_data = json.dumps(
        result, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2
    ).encode("utf-8") + b"\n"
    _write_or_require_identical(paths["result"], result_data)
    closure = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": result["status"],
        "result_sha256": sha256_bytes(result_data),
        "manifest_sha256": sha256_bytes(manifest_data),
        "authority_receipt_sha256": sha256_bytes(receipt_data),
        "journal_head_before_terminal": journal_head_before_terminal,
        "run_lock_absent_at_terminal_publication": not paths["run_lock"].exists(),
        "cleanup_passed": cleanup.get("passed") is True,
        "postflight_passed": postflight.get("passed") is True,
        "retry_allowed": False,
        "claiming": False,
    }
    _assert_public_no_smuggle(closure)
    closure_data = json.dumps(
        closure, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2
    ).encode("utf-8") + b"\n"
    _write_or_require_identical(paths["closure"], closure_data)
    if _event_for(events, "terminal-written") is None:
        append_journal_event(
            paths["journal"],
            "terminal-written",
            facts={
                "result_sha256": sha256_bytes(result_data),
                "closure_sha256": sha256_bytes(closure_data),
                "status": result["status"],
                "claiming": False,
            },
        )
    else:
        terminal = _event_for(read_journal(paths["journal"]), "terminal-written")
        _require(
            terminal is not None
            and terminal["facts"]["result_sha256"] == sha256_bytes(result_data)
            and terminal["facts"]["closure_sha256"] == sha256_bytes(closure_data),
            "terminal journal binding changed",
        )
    return result


def _archive_source_files(
    paths: Mapping[str, Path],
    events: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Path]:
    sources = {
        "receipt": paths["receipt"],
        "manifest": paths["manifest"],
        "journal": paths["journal"],
        "result": paths["result"],
        "closure": paths["closure"],
    }
    capture_arms = ARM_IDS if events is None else tuple(
        arm_id
        for arm_id in ARM_IDS
        if _event_for(events, "response-captured", arm_id) is not None
    )
    for arm_id in capture_arms:
        sources[f"capture-{arm_id}"] = paths[f"capture-{arm_id}"]
    if events is not None:
        for arm_id in ARM_IDS:
            adjudicated = _event_for(events, "adjudicated", arm_id)
            facts = adjudicated.get("facts") if adjudicated is not None else None
            if isinstance(facts, Mapping) and "partial_response_sha256" in facts:
                sources[f"partial-capture-{arm_id}"] = paths[
                    f"partial-capture-{arm_id}"
                ]
    return sources


def _archive_filename(name: str) -> str:
    mapping = {
        "receipt": "authority-receipt.json",
        "manifest": "manifest.json",
        "journal": "journal.jsonl",
        "result": "result.json",
        "closure": "closure.json",
        "capture-delete-parent-0": "capture-delete-parent-0.json",
        "capture-delete-parent-1": "capture-delete-parent-1.json",
        "partial-capture-delete-parent-0": "partial-capture-delete-parent-0.raw",
        "partial-capture-delete-parent-1": "partial-capture-delete-parent-1.raw",
    }
    return mapping[name]


def archive_terminal_evidence(repository: Path) -> dict[str, Any]:
    repository = repository.resolve(strict=False)
    source_authority.assert_test_repository_isolated(repository)
    paths = state_paths(repository)
    events = read_journal(paths["journal"])
    archived = _event_for(events, "archived")
    if archived is not None:
        bundle_sha = str(archived["facts"].get("archive_sha256", ""))
        _require_sha(bundle_sha, "existing archive hash")
        existing = repository / ARCHIVE_ROOT / EXPERIMENT_ID / bundle_sha
        verified = verify_archive(repository, existing)
        _require(verified["bundle_sha256"] == bundle_sha, "existing archive differs")
        return {"status": "verified-existing", **verified}
    _require(
        events and events[-1]["state"] == "terminal-written",
        "archive requires the terminal journal prefix",
    )
    sources = _archive_source_files(paths, events)
    payloads = {
        name: _require_regular(
            path,
            name,
            maximum=(
                MAX_RAW_RESPONSE_BYTES
                if name.startswith("partial-capture-")
                else MAX_CAPTURE_BYTES
                if name.startswith("capture-")
                else MAX_STATE_BYTES
            ),
        )
        for name, path in sources.items()
    }
    receipt = verify_authority_receipt_bytes(repository, payloads["receipt"])
    result = _json_object(payloads["result"], "terminal result")
    closure = _json_object(payloads["closure"], "terminal closure")
    _require(
        result.get("experiment_id") == EXPERIMENT_ID
        and closure.get("experiment_id") == EXPERIMENT_ID
        and closure.get("result_sha256") == sha256_bytes(payloads["result"])
        and closure.get("manifest_sha256") == sha256_bytes(payloads["manifest"])
        and closure.get("authority_receipt_sha256") == sha256_bytes(payloads["receipt"])
        and receipt.get("consumed") is True,
        "terminal evidence chain changed",
    )
    files = [
        {
            "name": name,
            "archive_filename": _archive_filename(name),
            "source_path": _relative(repository, sources[name]),
            "byte_size": len(payloads[name]),
            "sha256": sha256_bytes(payloads[name]),
        }
        for name in sorted(payloads)
    ]
    bundle = {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "protected_commit": receipt["authority"]["authorized_commit"],
        "source_archive_sha256": SOURCE_ARCHIVE_SHA256,
        "journal_terminal_event_sha256": events[-1]["event_sha256"],
        "files": files,
    }
    bundle_sha = json_sha256(bundle)
    target = repository / ARCHIVE_ROOT / EXPERIMENT_ID / bundle_sha
    _require_ignored(repository, target)
    balanced._assert_safe_ancestry(repository, target)
    if target.exists() or target.is_symlink():
        verified = verify_archive(repository, target)
        _require(verified["bundle_sha256"] == bundle_sha, "existing archive differs")
        return {"status": "verified-existing", **verified}
    target.parent.mkdir(parents=True, exist_ok=True)
    staging_parent = target.parent / f".{bundle_sha}.staging.{os.getpid()}"
    if staging_parent.exists() or staging_parent.is_symlink():
        raise ParentDependenceError("archive staging path already exists")
    staging_target = staging_parent / bundle_sha
    try:
        staging_target.mkdir(parents=True)
        for item in files:
            _exclusive_write(
                staging_target / str(item["archive_filename"]),
                payloads[str(item["name"])],
            )
        _exclusive_write(
            staging_target / "archive.json",
            canonical_json_bytes({"bundle": bundle, "bundle_sha256": bundle_sha}),
        )
        verify_archive(repository, staging_target, allow_staging=True)
        os.rename(staging_target, target)
    finally:
        if staging_parent.is_dir() and not balanced._is_reparse(staging_parent):
            shutil.rmtree(staging_parent)
    verified = verify_archive(repository, target)
    return {"status": "verified", **verified}


def verify_archive(
    repository: Path,
    archive_path: Path,
    *,
    allow_staging: bool = False,
) -> dict[str, Any]:
    repository = repository.resolve(strict=False)
    target = archive_path.resolve(strict=False)
    root = (repository / ARCHIVE_ROOT).resolve(strict=False)
    if not allow_staging:
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ParentDependenceError("archive path escapes archive root") from exc
    _require(target.is_dir() and not balanced._is_reparse(target), "archive is unsafe")
    document = _json_object(
        _require_regular(target / "archive.json", "archive manifest"),
        "archive manifest",
    )
    _require(set(document) == {"bundle", "bundle_sha256"}, "archive fields changed")
    bundle = document.get("bundle")
    bundle_sha = document.get("bundle_sha256")
    _require(
        isinstance(bundle, dict)
        and isinstance(bundle_sha, str)
        and json_sha256(bundle) == bundle_sha
        and target.name == bundle_sha,
        "archive content address changed",
    )
    files = bundle.get("files")
    _require(
        bundle.get("schema_version") == ARCHIVE_SCHEMA_VERSION
        and bundle.get("experiment_id") == EXPERIMENT_ID
        and bundle.get("source_archive_sha256") == SOURCE_ARCHIVE_SHA256
        and isinstance(files, list),
        "archive bundle contract changed",
    )
    payloads: dict[str, bytes] = {}
    expected_names = {"archive.json"}
    for item in files:
        if not isinstance(item, dict):
            raise ParentDependenceError("archive file entry is malformed")
        name = str(item.get("name", ""))
        filename = str(item.get("archive_filename", ""))
        _require(filename == _archive_filename(name), "archive filename changed")
        data = _require_regular(
            target / filename,
            f"archived {name}",
            maximum=(
                MAX_RAW_RESPONSE_BYTES
                if name.startswith("partial-capture-")
                else MAX_CAPTURE_BYTES
                if name.startswith("capture-")
                else MAX_STATE_BYTES
            ),
        )
        _require(
            item.get("byte_size") == len(data)
            and item.get("sha256") == sha256_bytes(data),
            "archived file bytes changed",
        )
        payloads[name] = data
        expected_names.add(filename)
    _require(
        {path.name for path in target.iterdir()} == expected_names,
        "archive contains unexpected paths",
    )
    core_names = {"receipt", "manifest", "journal", "result", "closure"}
    allowed_names = (
        core_names
        | {f"capture-{arm_id}" for arm_id in ARM_IDS}
        | {f"partial-capture-{arm_id}" for arm_id in ARM_IDS}
    )
    _require(
        set(payloads) <= allowed_names and core_names <= set(payloads),
        "archive evidence member set changed",
    )
    events = verify_journal_bytes(
        payloads["journal"],
        repository=repository,
        allow_archived=False,
    )
    expected_capture_names = {
        f"capture-{arm_id}"
        for arm_id in ARM_IDS
        if _event_for(events, "response-captured", arm_id) is not None
    }
    expected_partial_names: set[str] = set()
    for arm_id in ARM_IDS:
        adjudicated = _event_for(events, "adjudicated", arm_id)
        facts = adjudicated.get("facts") if adjudicated is not None else None
        if isinstance(facts, Mapping) and "partial_response_sha256" in facts:
            expected_partial_names.add(f"partial-capture-{arm_id}")
    _require(
        set(payloads) == core_names | expected_capture_names | expected_partial_names,
        "archive capture set does not match the terminal journal",
    )
    for arm_id in ARM_IDS:
        capture_name = f"capture-{arm_id}"
        if capture_name not in payloads:
            continue
        started = _event_for(events, "request-started", arm_id)
        captured = _event_for(events, "response-captured", arm_id)
        _require(started is not None and captured is not None, "archive capture lacks journal custody")
        verified_capture = verify_capture(
            target / _archive_filename(capture_name),
            arm_id=arm_id,
            model_request_sha256=str(started["facts"]["model_request_sha256"]),
        )
        _require(
            verified_capture["capture_sha256"] == captured["facts"].get("capture_sha256"),
            "archive capture differs from the journal binding",
        )
    for arm_id in ARM_IDS:
        partial_name = f"partial-capture-{arm_id}"
        if partial_name not in payloads:
            continue
        adjudicated = _event_for(events, "adjudicated", arm_id)
        facts = adjudicated.get("facts") if adjudicated is not None else None
        _require(
            isinstance(facts, Mapping)
            and facts.get("partial_response_sha256") == sha256_bytes(payloads[partial_name])
            and facts.get("partial_response_byte_size") == len(payloads[partial_name]),
            "partial response differs from the journal binding",
        )
    _require(
        events
        and events[-1]["state"] == "terminal-written"
        and events[-1]["event_sha256"] == bundle["journal_terminal_event_sha256"],
        "archived journal terminal binding changed",
    )
    receipt = verify_authority_receipt_bytes(
        repository,
        payloads["receipt"],
        require_current_static=False,
    )
    result = _json_object(payloads["result"], "archived result")
    closure = _json_object(payloads["closure"], "archived closure")
    _require(
        receipt["authority"]["authorized_commit"] == bundle["protected_commit"]
        and closure.get("result_sha256") == sha256_bytes(payloads["result"])
        and closure.get("manifest_sha256") == sha256_bytes(payloads["manifest"])
        and result.get("experiment_id") == EXPERIMENT_ID,
        "archived terminal chain changed",
    )
    return {"bundle": bundle, "bundle_sha256": bundle_sha}


def restore_archive(repository: Path, archive_path: Path) -> dict[str, Any]:
    repository = repository.resolve(strict=False)
    source_authority.assert_test_repository_isolated(repository)
    verified = verify_archive(repository, archive_path)
    target = archive_path.resolve(strict=False)
    paths = state_paths(repository)
    destination_by_name = _archive_source_files(paths)
    for arm_id in ARM_IDS:
        destination_by_name[f"partial-capture-{arm_id}"] = paths[
            f"partial-capture-{arm_id}"
        ]
    restored: list[str] = []
    unchanged: list[str] = []
    staged: list[tuple[Path, Path, str]] = []
    for item in verified["bundle"]["files"]:
        name = str(item["name"])
        destination = destination_by_name[name]
        data = (target / str(item["archive_filename"])).read_bytes()
        if destination.exists() or destination.is_symlink():
            if name == "journal" and destination.is_file() and not balanced._is_reparse(destination):
                live = destination.read_bytes()
                archived = data
                if live.startswith(archived):
                    suffix = live[len(archived) :]
                    if suffix:
                        live_events = verify_journal_bytes(live, repository=repository)
                        if live_events[-1]["state"] == "archived":
                            unchanged.append(_relative(repository, destination))
                            continue
            if (
                not destination.is_file()
                or balanced._is_reparse(destination)
                or destination.read_bytes() != data
            ):
                raise ParentDependenceError("restore refuses differing evidence")
            unchanged.append(_relative(repository, destination))
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(
            f".{destination.name}.restore.{verified['bundle_sha256']}.{os.getpid()}"
        )
        _exclusive_write(temporary, data)
        staged.append((temporary, destination, str(item["sha256"])))
    created: list[tuple[Path, str]] = []
    try:
        for temporary, destination, expected_sha in staged:
            if sha256_bytes(temporary.read_bytes()) != expected_sha:
                raise ParentDependenceError("staged restore bytes changed")
            os.link(temporary, destination)
            created.append((destination, expected_sha))
            temporary.unlink()
            restored.append(_relative(repository, destination))
    except BaseException:
        for destination, expected_sha in reversed(created):
            if (
                destination.is_file()
                and not balanced._is_reparse(destination)
                and sha256_bytes(destination.read_bytes()) == expected_sha
            ):
                destination.unlink()
        raise
    finally:
        for temporary, _, _ in staged:
            if temporary.is_file() and not balanced._is_reparse(temporary):
                temporary.unlink()
    return {
        "status": "restored-byte-exact",
        "bundle_sha256": verified["bundle_sha256"],
        "restored": restored,
        "unchanged": unchanged,
    }


def _arg(args: Any, name: str) -> Any:
    return args.get(name) if isinstance(args, Mapping) else getattr(args, name, None)


def _public_preflight(preflight: Mapping[str, Any]) -> dict[str, Any]:
    return kernel._public_preflight(preflight)


def _prepare_or_resume(
    repository: Path,
    paths: Mapping[str, Path],
    *,
    public_preflight: Mapping[str, Any],
    authority: Mapping[str, Any],
) -> dict[str, Any]:
    if not paths["run_root"].exists():
        paths["run_root"].mkdir(parents=True)
    elif not paths["run_root"].is_dir() or balanced._is_reparse(paths["run_root"]):
        raise ParentDependenceError("runtime root is unsafe")
    if paths["manifest"].exists() or paths["manifest"].is_symlink():
        manifest_data = _require_regular(paths["manifest"], "manifest")
        expected_manifest = _json_object(manifest_data, "manifest")
        _require(
            expected_manifest.get("experiment_id") == EXPERIMENT_ID
            and expected_manifest.get("protected_commit")
            == authority["authorized_commit"]
            and expected_manifest.get("authority_id_sha256")
            == authority["authority_id_sha256"]
            and expected_manifest.get("arm_request_sha256")
            == authority["arm_request_sha256"]
            and expected_manifest.get(
                "frozen_scientific_execution_binding_sha256"
            )
            == authority["frozen_scientific_execution_binding_sha256"]
            and expected_manifest.get("maximum_model_generations_per_arm") == 1
            and expected_manifest.get("maximum_total_model_generations") == 2,
            "existing manifest differs from the consumed scientific authority",
        )
    else:
        expected_manifest = _manifest(repository, public_preflight, authority)
        manifest_data = json.dumps(
            expected_manifest,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        ).encode("utf-8") + b"\n"
        _write_or_require_identical(paths["manifest"], manifest_data)
    events = read_journal(paths["journal"])
    if not events:
        append_journal_event(
            paths["journal"],
            "prepared",
            facts={
                "manifest_sha256": sha256_bytes(manifest_data),
                "protected_commit": authority["authorized_commit"],
                "future_model_generations": 2,
                "claiming": False,
            },
        )
    else:
        _require(
            events[0]["state"] == "prepared"
            and events[0]["facts"]["manifest_sha256"] == sha256_bytes(manifest_data),
            "prepared journal identity changed",
        )
    return expected_manifest


def _consume_or_verify_authority(
    repository: Path,
    paths: Mapping[str, Path],
    authority: Mapping[str, Any],
    *,
    current_commit: str,
    expected_model_sha256: str,
    expected_binary_sha256: str,
) -> dict[str, Any]:
    events = read_journal(paths["journal"])
    consumed_event = _event_for(events, "authority-consumed")
    if paths["receipt"].exists() or paths["receipt"].is_symlink():
        receipt = verify_authority_receipt(repository)
        _require(receipt["authority"] == dict(authority), "consumed authority differs")
    else:
        receipt = consume_authority_once(
            repository,
            authority,
            current_commit=current_commit,
            expected_model_sha256=expected_model_sha256,
            expected_binary_sha256=expected_binary_sha256,
        )
    if consumed_event is None:
        append_journal_event(
            paths["journal"],
            "authority-consumed",
            facts={
                "authority_receipt_sha256": receipt["authority_receipt_sha256"],
                "authority_id_sha256": authority["authority_id_sha256"],
                "arm_ids": list(ARM_IDS),
                "maximum_total_model_generations": 2,
            },
        )
    else:
        _require(
            consumed_event["facts"]["authority_receipt_sha256"]
            == receipt["authority_receipt_sha256"],
            "journal authority binding changed",
        )
    return receipt


def _remaining_unstarted_arms(events: Sequence[Mapping[str, Any]]) -> list[str]:
    return [
        arm_id
        for arm_id in ARM_IDS
        if _event_for(events, "request-started", arm_id) is None
    ]


def _all_captured_requests_have_custody(
    events: Sequence[Mapping[str, Any]],
) -> bool:
    return all(
        _event_for(events, "response-captured", arm_id) is None
        or _event_for(events, "request-custody-observed", arm_id) is not None
        for arm_id in ARM_IDS
    )


def _captured_requests_missing_custody(
    events: Sequence[Mapping[str, Any]],
) -> list[str]:
    return [
        arm_id
        for arm_id in ARM_IDS
        if _event_for(events, "response-captured", arm_id) is not None
        and _event_for(events, "request-custody-observed", arm_id) is None
        and _event_for(events, "adjudicated", arm_id) is None
    ]


def _validate_restart_runtime_paths(
    repository: Path,
    paths: Mapping[str, Path],
) -> list[str]:
    run_root = paths["run_root"]
    allowed = {
        path.resolve(strict=False)
        for key, path in paths.items()
        if key not in {"run_root", "receipt"}
    }
    allowed.add((run_root / ".controller.lock").resolve(strict=False))
    observed: list[str] = []
    if not run_root.is_dir() or balanced._is_reparse(run_root):
        raise RestartCustodyInvalidError("restart runtime root is unsafe")
    for path in run_root.rglob("*"):
        if balanced._is_reparse(path):
            raise RestartCustodyInvalidError("restart runtime path is a reparse point")
        if path.is_dir():
            continue
        if not path.is_file() or path.resolve(strict=False) not in allowed:
            raise RestartCustodyInvalidError(
                "restart runtime root contains an unauthorized path"
            )
        observed.append(_relative(repository, path))
    return sorted(observed)


def _restart_custody_reconciliation(
    repository: Path,
    paths: Mapping[str, Path],
    *,
    live: Any,
    full_preflight: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Reconstruct restart custody without launching or contacting a model."""
    try:
        receipt = verify_authority_receipt(repository)
        source = verify_source_evidence(repository)
        events = read_journal(paths["journal"])
        observed_paths = _validate_restart_runtime_paths(repository, paths)
        captures: dict[str, str] = {}
        partials: dict[str, str] = {}
        for arm_id in ARM_IDS:
            started = _event_for(events, "request-started", arm_id)
            captured = _event_for(events, "response-captured", arm_id)
            if captured is not None:
                if started is None:
                    raise RestartCustodyInvalidError(
                        "captured response lacks request-started custody"
                    )
                verified = verify_capture(
                    _capture_path(paths, arm_id),
                    arm_id=arm_id,
                    model_request_sha256=str(
                        started["facts"]["model_request_sha256"]
                    ),
                )
                if verified["capture_sha256"] != captured["facts"].get(
                    "capture_sha256"
                ):
                    raise RestartCustodyInvalidError(
                        "captured response differs from its journal event"
                    )
                captures[arm_id] = str(verified["capture_sha256"])
            partial = _partial_capture_path(paths, arm_id)
            if partial.exists() or partial.is_symlink():
                partial_data = _require_regular(
                    partial,
                    "partial raw response",
                    maximum=MAX_RAW_RESPONSE_BYTES,
                )
                partials[arm_id] = sha256_bytes(partial_data)
        cleanup = dict(live.cleanup(sidecar=None, preflight=full_preflight))
        postflight = dict(live.postflight(preflight=full_preflight))
    except (
        OSError,
        ParentDependenceError,
        balanced.BalancedOpaqueError,
        source_authority.RankHeadV2AuthorityError,
        source_evidence.RankHeadV2EvidenceError,
        publication.RankHeadV2PublicationError,
    ) as exc:
        if isinstance(exc, RestartCustodyInvalidError):
            raise
        raise RestartCustodyInvalidError(
            "restart custody evidence could not be verified"
        ) from exc
    cleanup["mode"] = "restart-custody-reconciliation"
    cleanup["request_custody_passed"] = cleanup.get("passed") is True
    postflight["mode"] = "restart-custody-reconciliation"
    passed = cleanup.get("passed") is True and postflight.get("passed") is True
    body = {
        "mode": "restart-custody-reconciliation",
        "gates_passed": passed,
        "authority_receipt_sha256": receipt["authority_receipt_sha256"],
        "journal_head_sha256": events[-1]["event_sha256"],
        "source_archive_sha256": source["source_hashes"]["archive"],
        "source_publication_record_sha256": source["source_publication"][
            "record_sha256"
        ],
        "captures": captures,
        "partial_captures": partials,
        "observed_runtime_paths": observed_paths,
        "cleanup": cleanup,
        "postflight": postflight,
        "model_requests_issued": 0,
        "sidecar_launched": False,
        "claiming": False,
    }
    balanced.validate_metadata_only(body)
    return cleanup, postflight, json_sha256(body)


def _finalization_facts(
    cleanup: Mapping[str, Any],
    postflight: Mapping[str, Any],
) -> dict[str, Any]:
    facts = {
        "cleanup": dict(cleanup),
        "postflight": dict(postflight),
        "mode": (
            "restart-custody-reconciliation"
            if cleanup.get("mode") == "restart-custody-reconciliation"
            and postflight.get("mode") == "restart-custody-reconciliation"
            else "live-cleanup-postflight"
        ),
        "gates_passed": (
            cleanup.get("passed") is True
            and cleanup.get("request_custody_passed", True) is True
            and postflight.get("passed") is True
        ),
    }
    balanced.validate_metadata_only(facts)
    return facts


def _execute_unstarted_arms(
    repository: Path,
    paths: Mapping[str, Path],
    *,
    live: Any,
    full_preflight: Mapping[str, Any],
    frozen_scientific_binding_sha256: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    enforce_exact_request = frozen_scientific_binding_sha256 is not None
    frozen_binding = frozen_scientific_binding_sha256 or ("F" * 64)
    for arm_id in ARM_IDS:
        try:
            _recover_request_prefix(repository, paths, arm_id)
        except CapturedResponseInvalidError as exc:
            events = read_journal(paths["journal"])
            if _event_for(events, "adjudicated", arm_id) is None:
                append_journal_event(
                    paths["journal"],
                    "adjudicated",
                    arm_id=arm_id,
                    facts=_inconclusive_facts(
                        arm_id,
                        "captured-response-invalid:"
                        + sha256_bytes(str(exc).encode("utf-8")),
                    ),
                )
    events = read_journal(paths["journal"])
    remaining = _remaining_unstarted_arms(events)
    missing_custody = _captured_requests_missing_custody(events)
    reconciliation: tuple[dict[str, Any], dict[str, Any], str] | None = None
    if missing_custody or not remaining:
        try:
            reconciliation = _restart_custody_reconciliation(
                repository,
                paths,
                live=live,
                full_preflight=full_preflight,
            )
        except RestartCustodyInvalidError as exc:
            failure_sha = sha256_bytes(str(exc).encode("utf-8"))
            cleanup = {
                "passed": False,
                "request_custody_passed": False,
                "mode": "restart-custody-reconciliation",
                "failure_sha256": failure_sha,
            }
            postflight = {
                "passed": False,
                "mode": "restart-custody-reconciliation",
                "failure_sha256": failure_sha,
            }
            for arm_id in missing_custody:
                if _event_for(
                    read_journal(paths["journal"]), "adjudicated", arm_id
                ) is None:
                    append_journal_event(
                        paths["journal"],
                        "adjudicated",
                        arm_id=arm_id,
                        facts=_inconclusive_facts(
                            arm_id,
                            "restart-custody-reconciliation-failed:" + failure_sha,
                        ),
                    )
            return cleanup, postflight
        cleanup, postflight, reconciliation_commitment = reconciliation
        reconciliation_passed = (
            cleanup.get("passed") is True and postflight.get("passed") is True
        )
        if reconciliation_passed:
            for arm_id in missing_custody:
                append_journal_event(
                    paths["journal"],
                    "request-custody-observed",
                    arm_id=arm_id,
                    facts={
                        "passed": True,
                        "mode": "restart-reconciled",
                        "reconciliation_commitment": reconciliation_commitment,
                    },
                )
        else:
            for arm_id in missing_custody:
                append_journal_event(
                    paths["journal"],
                    "adjudicated",
                    arm_id=arm_id,
                    facts=_inconclusive_facts(
                        arm_id,
                        "restart-custody-reconciliation-gates-failed:"
                        + reconciliation_commitment,
                    ),
                )
            return cleanup, postflight
        events = read_journal(paths["journal"])
        remaining = _remaining_unstarted_arms(events)
    if not remaining:
        if reconciliation is None:
            raise ParentDependenceError("restart reconciliation was not performed")
        return reconciliation[0], reconciliation[1]
    pool = live.create_lease_pool(1)
    sidecar: Any | None = None
    cleanup: dict[str, Any] = {"passed": False}
    postflight: dict[str, Any] = {"passed": False}
    request_custody_passed = _all_captured_requests_have_custody(events)
    try:
        sidecar, _readiness = live.launch_sidecar(
            preflight=full_preflight,
            run_id=EXPERIMENT_ID,
        )
        for arm_id in ARM_IDS:
            _recover_request_prefix(repository, paths, arm_id)
            events = read_journal(paths["journal"])
            if not _all_captured_requests_have_custody(events):
                request_custody_passed = False
            if _event_for(events, "request-started", arm_id) is not None:
                continue
            payload = build_arm_request(repository, arm_id)
            try:
                scientific.execute_and_capture_arm(
                    experiment_key=_experiment_key(_source_runtime(repository)),
                    frozen_binding_sha256=frozen_binding,
                    payload=payload,
                    arm_id=arm_id,
                    live=live,
                    sidecar=sidecar,
                    pool=pool,
                    full_preflight=full_preflight,
                    capture_path=_capture_path(paths, arm_id),
                    partial_path=_partial_capture_path(paths, arm_id),
                    append_event=lambda state, **kwargs: append_journal_event(
                        paths["journal"], state, **kwargs
                    ),
                    enforce_expected_request_hash=enforce_exact_request,
                )
            except BaseException as exc:
                if not _capture_path(paths, arm_id).is_file():
                    facts = _inconclusive_facts(
                        arm_id,
                        "request-failed-without-exact-capture:"
                        + sha256_bytes(str(exc).encode("utf-8")),
                    )
                    facts.update(_partial_capture_facts(paths, arm_id))
                    append_journal_event(
                        paths["journal"],
                        "adjudicated",
                        arm_id=arm_id,
                        facts=facts,
                    )
                else:
                    _recover_request_prefix(repository, paths, arm_id)
                    raise
                continue
    finally:
        try:
            cleanup = dict(live.cleanup(sidecar=sidecar, preflight=full_preflight))
        except BaseException as exc:
            cleanup = {
                "passed": False,
                "failure_sha256": sha256_bytes(str(exc).encode("utf-8")),
            }
        cleanup["request_custody_passed"] = request_custody_passed
        try:
            postflight = dict(live.postflight(preflight=full_preflight))
        except BaseException as exc:
            postflight = {
                "passed": False,
                "failure_sha256": sha256_bytes(str(exc).encode("utf-8")),
            }
    return cleanup, postflight


def _freeze_then_adjudicate_all(
    repository: Path,
    paths: Mapping[str, Path],
) -> None:
    recovery_failures: dict[str, str] = {}
    for arm_id in ARM_IDS:
        try:
            _recover_request_prefix(repository, paths, arm_id)
        except CapturedResponseInvalidError as exc:
            recovery_failures[arm_id] = sha256_bytes(
                str(exc).encode("utf-8")
            )
    events = read_journal(paths["journal"])
    finalization = _event_for(events, "finalization-observed")
    if finalization is None:
        raise ParentDependenceError("private adjudication requires durable finalization")
    if finalization["facts"].get("gates_passed") is not True:
        for arm_id in ARM_IDS:
            events = read_journal(paths["journal"])
            if _event_for(events, "adjudicated", arm_id) is None:
                append_journal_event(
                    paths["journal"],
                    "adjudicated",
                    arm_id=arm_id,
                    facts=_inconclusive_facts(
                        arm_id,
                        "durable-finalization-custody-gate-failed",
                    ),
                )
        return
    frozen: dict[str, tuple[Any, dict[str, Any], Any, dict[str, Any]]] = {}
    freeze_failures: dict[str, str] = dict(recovery_failures)
    # Freeze every available rank head before any private mapping/scoring.
    for arm_id in ARM_IDS:
        if _event_for(events, "adjudicated", arm_id) is not None:
            continue
        started = _event_for(events, "request-started", arm_id)
        captured = _event_for(events, "response-captured", arm_id)
        if started is None or captured is None:
            continue
        if arm_id in freeze_failures:
            continue
        request_sha = str(started["facts"]["model_request_sha256"])
        try:
            capture = verify_capture(
                _capture_path(paths, arm_id),
                arm_id=arm_id,
                model_request_sha256=request_sha,
            )
            frozen[arm_id] = _freeze_captured_arm(
                repository,
                arm_id,
                capture,
                int(started["facts"]["rendered_prompt_tokens"]),
            )
        except CapturedResponseInvalidError as exc:
            freeze_failures[arm_id] = sha256_bytes(str(exc).encode("utf-8"))
    events = read_journal(paths["journal"])
    preexisting_inconclusive = any(
        isinstance((event := _event_for(events, "adjudicated", arm_id)), Mapping)
        and isinstance(event.get("facts"), Mapping)
        and event["facts"].get("classification") == INCONCLUSIVE_CLASSIFICATION
        for arm_id in ARM_IDS
    )
    if freeze_failures or preexisting_inconclusive or set(frozen) != {
        arm_id
        for arm_id in ARM_IDS
        if _event_for(events, "adjudicated", arm_id) is None
    }:
        for arm_id in ARM_IDS:
            events = read_journal(paths["journal"])
            if _event_for(events, "adjudicated", arm_id) is not None:
                continue
            failure = freeze_failures.get(arm_id)
            reason = (
                "captured-response-invalid:" + failure
                if failure is not None
                else "global-freeze-barrier-not-satisfied"
            )
            append_journal_event(
                paths["journal"],
                "adjudicated",
                arm_id=arm_id,
                facts=_inconclusive_facts(arm_id, reason),
            )
        return
    for arm_id in ARM_IDS:
        events = read_journal(paths["journal"])
        if _event_for(events, "adjudicated", arm_id) is not None:
            continue
        value = frozen.get(arm_id)
        if value is None:
            raise ParentDependenceError("arm lacks a terminal request disposition")
        runtime, transform, selected, transport = value
        facts = _adjudicate_frozen_arm(runtime, transform, selected, arm_id)
        facts["transport"] = {
            "http_status": transport["http_status"],
            "prompt_tokens": transport["prompt_tokens"],
            "cached_prompt_tokens": transport["cached_prompt_tokens"],
            "fresh_prompt_tokens": transport["fresh_prompt_tokens"],
            "completion_tokens": transport["completion_tokens"],
            "finish_reason": transport["finish_reason"],
            "generated_token_evidence_mode": transport[
                "generated_token_evidence_mode"
            ],
        }
        _assert_public_no_smuggle(facts)
        append_journal_event(
            paths["journal"],
            "adjudicated",
            arm_id=arm_id,
            facts=facts,
        )


def run_parent_dependence(
    args: Any,
    *,
    repository_root: str | os.PathLike[str],
    adapter: Any | None = None,
) -> dict[str, Any]:
    """Execute or resume the exact two-arm replay under one consumed authority."""
    repository = Path(repository_root).resolve(strict=False)
    source_authority.assert_test_repository_isolated(repository)
    experiment_id = str(_arg(args, "experiment_id") or "")
    if experiment_id != EXPERIMENT_ID:
        raise ParentDependenceError("live command experiment ID changed")
    raw_authority_id = _arg(args, "external_authority_id")
    authorized_commit = _arg(args, "authorized_commit")
    if not isinstance(raw_authority_id, str) or not isinstance(authorized_commit, str):
        raise ParentDependenceError("live replay requires explicit external authority")
    paths = state_paths(repository)
    for path in paths.values():
        if path != paths["run_root"]:
            _require_ignored(repository, path)
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
        existing_receipt = verify_authority_receipt(
            repository,
            require_current_static=False,
        )
        authority = dict(existing_receipt["authority"])
        _require(
            authority.get("authorized_commit") == authorized_commit
            and authority.get("authority_id_sha256")
            == authority_id_sha256(raw_authority_id),
            "resume authority differs from the original consumed authority",
        )
        _controller_repair_report(
            repository,
            authority,
            current_commit=current_commit,
            events=None,
        )
    else:
        authority = build_external_authority(
            repository,
            raw_authority_id=raw_authority_id,
            authorized_commit=authorized_commit,
            current_commit=current_commit,
            expected_model_sha256=model_sha,
            expected_binary_sha256=binary_sha,
        )
    controller_path = paths["run_root"] / ".controller.lock"
    with controller_lock(controller_path):
        with run_lock(paths["run_lock"]):
            _prepare_or_resume(
                repository,
                paths,
                public_preflight=public_preflight,
                authority=authority,
            )
            receipt = _consume_or_verify_authority(
                repository,
                paths,
                authority,
                current_commit=current_commit,
                expected_model_sha256=model_sha,
                expected_binary_sha256=binary_sha,
            )
            _observe_controller_repair(
                repository,
                paths,
                authority=authority,
                current_commit=current_commit,
            )
            events = read_journal(paths["journal"])
            terminal = _event_for(events, "terminal-written")
            cleanup: dict[str, Any] = {"passed": False}
            postflight: dict[str, Any] = {"passed": False}
            if terminal is None:
                finalization = _event_for(events, "finalization-observed")
                if finalization is None:
                    cleanup, postflight = _execute_unstarted_arms(
                        repository,
                        paths,
                        live=live,
                        full_preflight=full_preflight,
                        frozen_scientific_binding_sha256=str(
                            authority[
                                "frozen_scientific_execution_binding_sha256"
                            ]
                        ),
                    )
                    append_journal_event(
                        paths["journal"],
                        "finalization-observed",
                        facts=_finalization_facts(cleanup, postflight),
                    )
                else:
                    cleanup = dict(finalization["facts"]["cleanup"])
                    postflight = dict(finalization["facts"]["postflight"])
        # The process lock remains held, but the externally visible run lock is
        # absent before private adjudication, terminal publication, and archive.
        events = read_journal(paths["journal"])
        terminal = _event_for(events, "terminal-written")
        if terminal is None:
            _freeze_then_adjudicate_all(repository, paths)
            result = _write_terminal(
                repository,
                paths,
                receipt=receipt,
                cleanup=cleanup,
                postflight=postflight,
            )
        else:
            result = _json_object(_require_regular(paths["result"], "result"), "result")
            _assert_public_no_smuggle(result)
        archive = archive_terminal_evidence(repository)
        events = read_journal(paths["journal"])
        if _event_for(events, "archived") is None:
            append_journal_event(
                paths["journal"],
                "archived",
                facts={
                    "archive_sha256": archive["bundle_sha256"],
                    "archive_verified": True,
                    "claiming": False,
                },
            )
        return {**result, "evidence_archive_sha256": archive["bundle_sha256"]}


def validate_static(repository: Path) -> dict[str, Any]:
    repository = repository.resolve(strict=False)
    preregistration = validate_preregistration(repository)
    source = verify_source_evidence(repository)
    isolation = request_isolation_report(repository)
    implementation = _implementation_binding(repository)
    return {
        "status": "pass",
        "experiment_id": EXPERIMENT_ID,
        "arm_ids": list(ARM_IDS),
        "future_model_generations": 2,
        "source_archive_sha256": source["source_hashes"]["archive"],
        "source_publication_record_sha256": source["source_publication"][
            "record_sha256"
        ],
        "preregistration": preregistration,
        "request_isolation": isolation,
        "frozen_scientific_execution_binding": implementation[
            "frozen_scientific_execution"
        ],
        "repairable_controller_binding": implementation[
            "repairable_controller"
        ],
        "authority_repair_policy": {
            "maximum_controller_repair_commits": MAXIMUM_CONTROLLER_REPAIR_COMMITS,
            "descendant_only": True,
            "frozen_scientific_surface_may_change": False,
            "arm_request_hashes_may_change": False,
            "controller_repair_resets_arm_consumption": False,
            "repair_transition_model_generations": 0,
            "automatic_follow_on": False,
        },
        "authority_object_schema_sha256": AUTHORITY_OBJECT_SCHEMA_SHA256,
        "authority_receipt_schema_sha256": AUTHORITY_RECEIPT_SCHEMA_SHA256,
        "authority_created": False,
        "authority_consumed": False,
        "live_execution_performed": False,
        "model_requests_issued": 0,
        "sidecar_launched": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="operation", required=True)
    generate = subparsers.add_parser("generate")
    generate.add_argument("--repository", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--repository", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--repository", required=True)
    run.add_argument("--binary", required=True)
    run.add_argument("--model", required=True)
    run.add_argument("--experiment-id", required=True)
    run.add_argument("--external-authority-id", required=True)
    run.add_argument("--authorized-commit", required=True)
    verify = subparsers.add_parser("verify-archive")
    verify.add_argument("--repository", required=True)
    verify.add_argument("--archive", required=True)
    restore = subparsers.add_parser("restore-archive")
    restore.add_argument("--repository", required=True)
    restore.add_argument("--archive", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository = Path(args.repository).resolve(strict=False)
    try:
        if args.operation == "generate":
            path = write_preregistration(repository)
            result = {
                "status": "written",
                "path": _relative(repository, path),
                "artifact_sha256": sha256_bytes(path.read_bytes()),
            }
        elif args.operation == "validate":
            result = validate_static(repository)
        elif args.operation == "run":
            result = run_parent_dependence(args, repository_root=repository)
        elif args.operation == "verify-archive":
            result = {"status": "pass", **verify_archive(repository, Path(args.archive))}
        else:
            result = restore_archive(repository, Path(args.archive))
    except (
        OSError,
        ParentDependenceError,
        balanced.BalancedOpaqueError,
        v2.RankHeadDesignError,
        integration.RankHeadV2IntegrationError,
        source_authority.RankHeadV2AuthorityError,
        source_evidence.RankHeadV2EvidenceError,
        publication.RankHeadV2PublicationError,
        run_design.RankHeadV2RunDesignError,
    ) as exc:
        print(canonical_json_text({"status": "fail", "error": str(exc)}))
        return 1
    print(canonical_json_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
