#!/usr/bin/env python3
"""External one-shot authority bridge for deterministic-rank-head CK0 v2.

Tracked design files remain non-self-authorizing. A future live command must
supply one raw 64-hex authority ID and the exact protected commit. Consumption
is serialized across both reserved runs and occurs immediately before the first
live runtime mutation. This module creates no authority unless explicitly called.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import stat
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2 as v2
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration
import catalytic_kernel_0_balanced_rank_head_v2_run_design as run_design

AUTHORITY_SCHEMA_VERSION = "rank-head-v2-external-one-shot-v1"
AUTHORITY_KIND = "external-one-shot"
RECEIPT_SCHEMA_VERSION = "rank-head-v2-authority-consumption-v1"
AUTHORITY_ID_DOMAIN = b"ck0-balanced-rank-head-v2/external-authority-id-v1\0"
AUTHORITY_RECEIPT_DOMAIN = b"ck0-balanced-rank-head-v2/external-authority-v1\0"
RECEIPT_TEMPLATE = (
    "state/catalytic_kernel_0_rank_head_v2_authority."
    "<run-id>.authority.consumed.json"
)
SHA256_RE = balanced.SHA256_RE
AUTHORITY_ID_RE = balanced.AUTHORITY_ID_RE
GIT_COMMIT_RE = balanced.GIT_COMMIT_RE


class RankHeadV2AuthorityError(ValueError):
    pass


@dataclass(frozen=True)
class RankHeadV2ExternalAuthority:
    schema_version: str
    authority_kind: str
    authority_id_sha256: str
    authorized_commit: str
    run_id: str
    run_ordinal: int
    source_binding: str
    run_design_artifact_sha256: str
    run_design_document_sha256: str
    run_design_implementation_binding_sha256: str
    static_preregistration_artifact_sha256: str
    static_preregistration_document_sha256: str
    static_design_contract_sha256: str
    carrier_id: str
    carrier_root_sha256: str
    state_root: str
    model_sha256: str
    binary_sha256: str
    run_key_commitment: str
    maximum_invocations: int = 1
    retry_count: int = 0
    automatic_follow_on: bool = False

    def body(self) -> dict[str, Any]:
        body = {
            "schema_version": self.schema_version,
            "authority_kind": self.authority_kind,
            "authority_id_sha256": self.authority_id_sha256,
            "authorized_commit": self.authorized_commit,
            "run_id": self.run_id,
            "run_ordinal": self.run_ordinal,
            "source_binding": self.source_binding,
            "run_design_artifact_sha256": self.run_design_artifact_sha256,
            "run_design_document_sha256": self.run_design_document_sha256,
            "run_design_implementation_binding_sha256": (
                self.run_design_implementation_binding_sha256
            ),
            "static_preregistration_artifact_sha256": (
                self.static_preregistration_artifact_sha256
            ),
            "static_preregistration_document_sha256": (
                self.static_preregistration_document_sha256
            ),
            "static_design_contract_sha256": self.static_design_contract_sha256,
            "carrier_id": self.carrier_id,
            "carrier_root_sha256": self.carrier_root_sha256,
            "state_root": self.state_root,
            "model_sha256": self.model_sha256,
            "binary_sha256": self.binary_sha256,
            "run_key_commitment": self.run_key_commitment,
            "maximum_invocations": self.maximum_invocations,
            "retry_count": self.retry_count,
            "automatic_follow_on": self.automatic_follow_on,
        }
        balanced.validate_metadata_only(body)
        return body


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def json_sha256(value: Any) -> str:
    return sha256_bytes(balanced.canonical_json_bytes(value))


def authority_object_schema() -> dict[str, Any]:
    sha = {"type": "string", "pattern": "^[0-9A-F]{64}$"}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "authority_kind",
            "authority_id_sha256",
            "authorized_commit",
            "run_id",
            "run_ordinal",
            "source_binding",
            "run_design_artifact_sha256",
            "run_design_document_sha256",
            "run_design_implementation_binding_sha256",
            "static_preregistration_artifact_sha256",
            "static_preregistration_document_sha256",
            "static_design_contract_sha256",
            "carrier_id",
            "carrier_root_sha256",
            "state_root",
            "model_sha256",
            "binary_sha256",
            "run_key_commitment",
            "maximum_invocations",
            "retry_count",
            "automatic_follow_on",
        ],
        "properties": {
            "schema_version": {"const": AUTHORITY_SCHEMA_VERSION},
            "authority_kind": {"const": AUTHORITY_KIND},
            "authority_id_sha256": sha,
            "authorized_commit": {
                "type": "string",
                "pattern": "^[0-9a-f]{40}$",
            },
            "run_id": {"enum": list(integration.RUN_ORDER)},
            "run_ordinal": {"enum": [1, 2]},
            "source_binding": {"enum": ["binding-1", "binding-2"]},
            "run_design_artifact_sha256": sha,
            "run_design_document_sha256": sha,
            "run_design_implementation_binding_sha256": sha,
            "static_preregistration_artifact_sha256": sha,
            "static_preregistration_document_sha256": sha,
            "static_design_contract_sha256": sha,
            "carrier_id": {"const": v2.V2_CARRIER_ID},
            "carrier_root_sha256": sha,
            "state_root": {"const": run_design.STATE_ROOT},
            "model_sha256": sha,
            "binary_sha256": sha,
            "run_key_commitment": sha,
            "maximum_invocations": {"const": 1},
            "retry_count": {"const": 0},
            "automatic_follow_on": {"const": False},
        },
    }


def authority_receipt_schema() -> dict[str, Any]:
    sha = {"type": "string", "pattern": "^[0-9A-F]{64}$"}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "authority",
            "authority_object_schema_sha256",
            "authority_receipt_schema_sha256",
            "authority_receipt_hmac",
            "consumed",
            "consumption_occurred_before_live_mutation",
            "maximum_invocations",
            "retry_allowed",
        ],
        "properties": {
            "schema_version": {"const": RECEIPT_SCHEMA_VERSION},
            "authority": authority_object_schema(),
            "authority_object_schema_sha256": sha,
            "authority_receipt_schema_sha256": sha,
            "authority_receipt_hmac": sha,
            "consumed": {"const": True},
            "consumption_occurred_before_live_mutation": {"const": True},
            "maximum_invocations": {"const": 1},
            "retry_allowed": {"const": False},
        },
    }


AUTHORITY_OBJECT_SCHEMA_SHA256 = json_sha256(authority_object_schema())
AUTHORITY_RECEIPT_SCHEMA_SHA256 = json_sha256(authority_receipt_schema())


def authority_id_sha256(raw_authority_id: str) -> str:
    if (
        not isinstance(raw_authority_id, str)
        or not AUTHORITY_ID_RE.fullmatch(raw_authority_id)
    ):
        raise RankHeadV2AuthorityError(
            "v2 authority ID must be exactly 64 hexadecimal characters"
        )
    return sha256_bytes(
        AUTHORITY_ID_DOMAIN + bytes.fromhex(raw_authority_id)
    )


def _require_sha(value: str, label: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise RankHeadV2AuthorityError(f"{label} is not a SHA-256 identity")
    return value


def build_external_authority(
    *,
    private: balanced.PrivateBinding,
    spec: integration.V2RunSpec,
    raw_authority_id: str,
    authorized_commit: str,
    current_commit: str,
    run_design_projection: Mapping[str, Any],
    static_preregistration_projection: Mapping[str, Any],
    model_sha256: str,
    binary_sha256: str,
) -> RankHeadV2ExternalAuthority:
    if private.configuration.run_modes != {spec.run_id: "full-information"}:
        raise RankHeadV2AuthorityError("v2 authority private run scope changed")
    if (
        not isinstance(authorized_commit, str)
        or not GIT_COMMIT_RE.fullmatch(authorized_commit)
        or authorized_commit != current_commit
    ):
        raise RankHeadV2AuthorityError("v2 authorized commit mismatch")
    carrier = v2.build_v2_carrier()
    authority = RankHeadV2ExternalAuthority(
        schema_version=AUTHORITY_SCHEMA_VERSION,
        authority_kind=AUTHORITY_KIND,
        authority_id_sha256=authority_id_sha256(raw_authority_id),
        authorized_commit=authorized_commit,
        run_id=spec.run_id,
        run_ordinal=spec.ordinal,
        source_binding=spec.source_binding,
        run_design_artifact_sha256=_require_sha(
            str(run_design_projection.get("artifact_sha256", "")),
            "run design artifact",
        ),
        run_design_document_sha256=_require_sha(
            str(run_design_projection.get("document_sha256", "")),
            "run design document",
        ),
        run_design_implementation_binding_sha256=_require_sha(
            str(run_design_projection.get("implementation_binding_sha256", "")),
            "run design implementation binding",
        ),
        static_preregistration_artifact_sha256=_require_sha(
            str(static_preregistration_projection.get("artifact_sha256", "")),
            "static preregistration artifact",
        ),
        static_preregistration_document_sha256=_require_sha(
            str(static_preregistration_projection.get("document_sha256", "")),
            "static preregistration document",
        ),
        static_design_contract_sha256=_require_sha(
            str(static_preregistration_projection.get("design_contract_sha256", "")),
            "static design contract",
        ),
        carrier_id=carrier["carrier_id"],
        carrier_root_sha256=carrier["carrier_root_sha256"],
        state_root=run_design.STATE_ROOT,
        model_sha256=_require_sha(model_sha256, "model"),
        binary_sha256=_require_sha(binary_sha256, "binary"),
        run_key_commitment=balanced.run_key_commitment(
            private.run_key(spec.run_id),
            private.configuration,
        ),
    )
    authority.body()
    return authority


def authority_receipt_hmac(
    private: balanced.PrivateBinding,
    authority: RankHeadV2ExternalAuthority,
) -> str:
    if authority.run_id not in private.configuration.run_modes:
        raise RankHeadV2AuthorityError("v2 authority run scope mismatch")
    return hmac.new(
        private.run_key(authority.run_id),
        AUTHORITY_RECEIPT_DOMAIN
        + balanced.canonical_json_bytes(authority.body()),
        hashlib.sha256,
    ).hexdigest().upper()


def validate_external_authority(
    private: balanced.PrivateBinding,
    authority: RankHeadV2ExternalAuthority,
    *,
    spec: integration.V2RunSpec,
    current_commit: str,
    receipt_hmac: str | None = None,
) -> None:
    expected = all(
        (
            authority.schema_version == AUTHORITY_SCHEMA_VERSION,
            authority.authority_kind == AUTHORITY_KIND,
            authority.run_id == spec.run_id,
            authority.run_ordinal == spec.ordinal,
            authority.source_binding == spec.source_binding,
            authority.authorized_commit == current_commit,
            authority.carrier_id == v2.V2_CARRIER_ID,
            authority.carrier_root_sha256
            == v2.build_v2_carrier()["carrier_root_sha256"],
            authority.state_root == run_design.STATE_ROOT,
            authority.run_key_commitment
            == balanced.run_key_commitment(
                private.run_key(spec.run_id),
                private.configuration,
            ),
            authority.maximum_invocations == 1,
            authority.retry_count == 0,
            authority.automatic_follow_on is False,
        )
    )
    if not expected:
        raise RankHeadV2AuthorityError("v2 external authority scope mismatch")
    authority.body()
    if receipt_hmac is not None and not hmac.compare_digest(
        receipt_hmac,
        authority_receipt_hmac(private, authority),
    ):
        raise RankHeadV2AuthorityError("v2 external authority HMAC mismatch")


def authority_receipt_path(repository: Path, run_id: str) -> Path:
    integration.run_spec(run_id)
    return repository.absolute() / RECEIPT_TEMPLATE.replace("<run-id>", run_id)


def _is_reparse(path: Path) -> bool:
    return balanced._is_reparse(path)


def _assert_safe_ancestry(repository: Path, target: Path) -> None:
    balanced._assert_safe_ancestry(repository, target)


def _receipt_document(
    private: balanced.PrivateBinding,
    authority: RankHeadV2ExternalAuthority,
) -> dict[str, Any]:
    document = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "authority": authority.body(),
        "authority_object_schema_sha256": AUTHORITY_OBJECT_SCHEMA_SHA256,
        "authority_receipt_schema_sha256": AUTHORITY_RECEIPT_SCHEMA_SHA256,
        "authority_receipt_hmac": authority_receipt_hmac(private, authority),
        "consumed": True,
        "consumption_occurred_before_live_mutation": True,
        "maximum_invocations": 1,
        "retry_allowed": False,
    }
    balanced.validate_metadata_only(document)
    return document


def assert_authority_unconsumed(
    repository: Path,
    run_id: str,
    authority_id_hash: str | None = None,
) -> None:
    repository = repository.absolute()
    if authority_id_hash is not None:
        _require_sha(authority_id_hash, "authority ID hash")
    target = authority_receipt_path(repository, run_id)
    _assert_safe_ancestry(repository, target)
    ignored = subprocess.run(
        [
            "git",
            "check-ignore",
            "--quiet",
            "--",
            target.relative_to(repository).as_posix(),
        ],
        cwd=repository,
        check=False,
        timeout=30,
    )
    if ignored.returncode != 0:
        raise RankHeadV2AuthorityError(
            "v2 authority receipt path is not ignored"
        )
    if target.exists() or target.is_symlink():
        raise RankHeadV2AuthorityError("v2 run was already attempted")
    if authority_id_hash is None:
        return
    for other_run_id in integration.RUN_ORDER:
        other = authority_receipt_path(repository, other_run_id)
        if not other.exists() and not other.is_symlink():
            continue
        _assert_safe_ancestry(repository, other)
        if (
            not other.is_file()
            or _is_reparse(other)
            or other.stat().st_size > 32768
        ):
            raise RankHeadV2AuthorityError(
                "v2 authority receipt inventory is unsafe"
            )
        try:
            document = json.loads(other.read_bytes())
        except json.JSONDecodeError as exc:
            raise RankHeadV2AuthorityError(
                "v2 authority receipt inventory is invalid"
            ) from exc
        if (
            document.get("authority", {}).get("authority_id_sha256")
            == authority_id_hash
        ):
            raise RankHeadV2AuthorityError(
                "v2 authority ID was already consumed"
            )


@contextmanager
def authority_consumption_lock(repository: Path):
    lock_path = repository.absolute() / v2.PREREGISTRATION_PATH
    _assert_safe_ancestry(repository, lock_path)
    if (
        not lock_path.is_file()
        or _is_reparse(lock_path)
        or lock_path.stat().st_size > 2_000_000
    ):
        raise RankHeadV2AuthorityError("v2 authority lock file is unsafe")
    descriptor = os.open(
        lock_path,
        os.O_RDWR | getattr(os, "O_BINARY", 0),
    )
    locked = False
    try:
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RankHeadV2AuthorityError(
                    "another v2 authority consumption is in progress"
                ) from exc
        else:
            import fcntl

            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RankHeadV2AuthorityError(
                    "another v2 authority consumption is in progress"
                ) from exc
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


def consume_authority_once(
    repository: Path,
    private: balanced.PrivateBinding,
    authority: RankHeadV2ExternalAuthority,
) -> dict[str, Any]:
    repository = repository.absolute()
    spec = integration.run_spec(authority.run_id)
    validate_external_authority(
        private,
        authority,
        spec=spec,
        current_commit=authority.authorized_commit,
    )
    state_root = repository / "state"
    if not state_root.is_dir() or _is_reparse(state_root):
        raise RankHeadV2AuthorityError("state root is missing or unsafe")
    target = authority_receipt_path(repository, authority.run_id)
    payload = balanced.canonical_json_bytes(_receipt_document(private, authority))
    with authority_consumption_lock(repository):
        assert_authority_unconsumed(
            repository,
            authority.run_id,
            authority.authority_id_sha256,
        )
        _assert_safe_ancestry(repository, target)
        try:
            descriptor = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                stat.S_IRUSR | stat.S_IWUSR,
            )
        except FileExistsError as exc:
            raise RankHeadV2AuthorityError("v2 run was already attempted") from exc
        try:
            if hasattr(os, "fchmod"):
                os.fchmod(descriptor, stat.S_IRUSR | stat.S_IWUSR)
            written = os.write(descriptor, payload)
            if written != len(payload):
                raise RankHeadV2AuthorityError(
                    "v2 authority receipt write was incomplete"
                )
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
    return verify_authority_receipt(repository, private, authority)


def verify_authority_receipt(
    repository: Path,
    private: balanced.PrivateBinding,
    authority: RankHeadV2ExternalAuthority,
) -> dict[str, Any]:
    target = authority_receipt_path(repository, authority.run_id)
    _assert_safe_ancestry(repository, target)
    if (
        not target.is_file()
        or _is_reparse(target)
        or target.stat().st_size > 32768
    ):
        raise RankHeadV2AuthorityError(
            "v2 authority receipt is missing or unsafe"
        )
    try:
        document = json.loads(target.read_bytes())
    except json.JSONDecodeError as exc:
        raise RankHeadV2AuthorityError("v2 authority receipt is invalid") from exc
    expected = _receipt_document(private, authority)
    if document != expected:
        raise RankHeadV2AuthorityError("v2 authority receipt binding changed")
    validate_external_authority(
        private,
        authority,
        spec=integration.run_spec(authority.run_id),
        current_commit=authority.authorized_commit,
        receipt_hmac=str(document.get("authority_receipt_hmac", "")),
    )
    evidence = {
        "authority": authority.body(),
        "authority_receipt_hmac": document["authority_receipt_hmac"],
        "authority_receipt_sha256": sha256_bytes(target.read_bytes()),
        "consumed": True,
        "consumption_occurred_before_live_mutation": True,
        "maximum_invocations": 1,
        "retry_allowed": False,
    }
    balanced.validate_metadata_only(evidence)
    return evidence
