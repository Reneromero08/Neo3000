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
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2 as v2
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration
import catalytic_kernel_0_balanced_rank_head_v2_run_design as run_design

AUTHORITY_SCHEMA_VERSION = "rank-head-v2-external-one-shot-v3"
AUTHORITY_KIND = "external-one-shot"
RECEIPT_SCHEMA_VERSION = "rank-head-v2-authority-consumption-v3"
HISTORICAL_V1_AUTHORITY_OBJECT_SCHEMA_SHA256 = (
    "8CDE8477F324E9E72C89F14908333937643675C2F42F92E67062DFE92F4A0CB3"
)
HISTORICAL_V1_AUTHORITY_RECEIPT_SCHEMA_SHA256 = (
    "709552F6DDC2F31DC154C1C65F895F55637B7088B4F548FDFA1F771381E55411"
)
UNVERSIONED_R2_AUTHORITY_OBJECT_SCHEMA_SHA256 = (
    "2F171672C66EB845681A2934A717863355E2388D856DC5725BBB70154B7D2D52"
)
UNVERSIONED_R2_AUTHORITY_RECEIPT_SCHEMA_SHA256 = (
    "C56B30ED4E356BD1C914C6DE35BFC4B384FA89E2B3577959AC5A5855AA89B591"
)
HISTORICAL_V2_AUTHORITY_SCHEMA_VERSION = "rank-head-v2-external-one-shot-v2"
HISTORICAL_V2_RECEIPT_SCHEMA_VERSION = "rank-head-v2-authority-consumption-v2"
HISTORICAL_V2_AUTHORITY_OBJECT_SCHEMA_SHA256 = (
    "279BABE4626FEE8F69B178A0CBC23AECD58B9BFDC5579BE633B75B337797CE72"
)
HISTORICAL_V2_AUTHORITY_RECEIPT_SCHEMA_SHA256 = (
    "898DE481CE8F896F7B6D006E7BB1357AF507597BE2EE9B31F0D3DC6337723CC5"
)
EXPECTED_ACTIVE_AUTHORITY_OBJECT_SCHEMA_SHA256 = (
    "5616C6D5ACEDD569D9DBF052890C48A44B9C2600FC5C536A2B18F4F5F02A07BB"
)
EXPECTED_ACTIVE_AUTHORITY_RECEIPT_SCHEMA_SHA256 = (
    "7E44D619F5BCC4FC24F41E7CFE81946B7073C35349F6322F892AE0C5BC396A52"
)
HISTORICAL_CONSUMED_AUTHORITY_ID_SHA256 = (
    "541C7E61EBB30366D7007D8BA5EC30DB720B0817FA29CABB1625536D6B720A66"
)
HISTORICAL_R2_CONSUMED_AUTHORITY_ID_SHA256 = (
    "94D435C48B32649A0F049D4BBB951D17F2A44D32B2893E74F437245FE0A09C3E"
)
HISTORICAL_CONSUMED_AUTHORITY_ID_BLACKLIST = frozenset(
    {
        HISTORICAL_CONSUMED_AUTHORITY_ID_SHA256,
        HISTORICAL_R2_CONSUMED_AUTHORITY_ID_SHA256,
    }
)
AUTHORITY_ID_DOMAIN = b"ck0-balanced-rank-head-v2/external-authority-id-v1\0"
AUTHORITY_RECEIPT_DOMAIN = b"ck0-balanced-rank-head-v2/external-authority-v1\0"
RECEIPT_TEMPLATE = (
    "state/catalytic_kernel_0_rank_head_v2_authority."
    "<run-id>.authority.consumed.json"
)
SHA256_RE = balanced.SHA256_RE
AUTHORITY_ID_RE = balanced.AUTHORITY_ID_RE
GIT_COMMIT_RE = balanced.GIT_COMMIT_RE
TEST_PROCESS_ENV = "NEO3000_RANK_HEAD_V2_TEST_PROCESS"
TEST_REPOSITORY_ENV = "NEO3000_RANK_HEAD_V2_TEST_REPOSITORY"
SOURCE_REPOSITORY = Path(__file__).resolve().parents[1]


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
    predecessor_run_id: str | None
    predecessor_publication_commit: str | None
    predecessor_publication_record_sha256: str | None
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
            "predecessor_run_id": self.predecessor_run_id,
            "predecessor_publication_commit": self.predecessor_publication_commit,
            "predecessor_publication_record_sha256": (
                self.predecessor_publication_record_sha256
            ),
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


@dataclass(frozen=True)
class HistoricalRankHeadV2ExternalAuthority:
    """Exact consumed v2 authority shape retained only for r2 verification."""

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
            field: getattr(self, field)
            for field in self.__dataclass_fields__
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
            "predecessor_run_id",
            "predecessor_publication_commit",
            "predecessor_publication_record_sha256",
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
            "predecessor_run_id": {
                "enum": [None, integration.BINDING_1_RUN_ID]
            },
            "predecessor_publication_commit": {
                "anyOf": [
                    {"type": "null"},
                    {"type": "string", "pattern": "^[0-9a-f]{40}$"},
                ]
            },
            "predecessor_publication_record_sha256": {
                "anyOf": [{"type": "null"}, sha]
            },
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
if (
    AUTHORITY_OBJECT_SCHEMA_SHA256
    != EXPECTED_ACTIVE_AUTHORITY_OBJECT_SCHEMA_SHA256
    or AUTHORITY_RECEIPT_SCHEMA_SHA256
    != EXPECTED_ACTIVE_AUTHORITY_RECEIPT_SCHEMA_SHA256
):
    raise RuntimeError(
        "active v2 authority schema identity changed: "
        f"{AUTHORITY_OBJECT_SCHEMA_SHA256} "
        f"{AUTHORITY_RECEIPT_SCHEMA_SHA256}"
    )


def _test_process_active() -> bool:
    argv0 = Path(sys.argv[0]).name.lower() if sys.argv else ""
    return (
        os.environ.get(TEST_PROCESS_ENV) == "1"
        or argv0.startswith("test_")
        or any(
            name.rsplit(".", 1)[-1].startswith("test_")
            for name in sys.modules
        )
    )


def assert_test_repository_isolated(repository: Path) -> None:
    """Fail before any v2 state access when a test targets the real repository."""
    if not _test_process_active():
        return
    resolved = repository.resolve(strict=False)
    if resolved == SOURCE_REPOSITORY:
        raise RankHeadV2AuthorityError(
            "test process cannot access real rank-head v2 state"
        )
    expected = os.environ.get(TEST_REPOSITORY_ENV)
    if os.environ.get(TEST_PROCESS_ENV) == "1" and (
        not expected or resolved != Path(expected).resolve(strict=False)
    ):
        raise RankHeadV2AuthorityError(
            "test process repository differs from its isolated repository"
        )


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


def assert_authority_id_not_retired(authority_id_hash: str) -> None:
    value = _require_sha(authority_id_hash, "authority ID hash")
    if any(
        hmac.compare_digest(value, blocked)
        for blocked in HISTORICAL_CONSUMED_AUTHORITY_ID_BLACKLIST
    ):
        raise RankHeadV2AuthorityError(
            "external authority ID was already consumed"
        )


def require_active_schema_identities(
    authority_object_schema_sha256: str,
    authority_receipt_schema_sha256: str,
) -> None:
    pair = (
        _require_sha(authority_object_schema_sha256, "authority object schema"),
        _require_sha(authority_receipt_schema_sha256, "authority receipt schema"),
    )
    if pair == (
        UNVERSIONED_R2_AUTHORITY_OBJECT_SCHEMA_SHA256,
        UNVERSIONED_R2_AUTHORITY_RECEIPT_SCHEMA_SHA256,
    ):
        raise RankHeadV2AuthorityError(
            "unversioned replacement-run authority schemas are forbidden"
        )
    if pair == (
        HISTORICAL_V1_AUTHORITY_OBJECT_SCHEMA_SHA256,
        HISTORICAL_V1_AUTHORITY_RECEIPT_SCHEMA_SHA256,
    ):
        raise RankHeadV2AuthorityError(
            "historical v1 authority schemas are inactive"
        )
    if pair == (
        HISTORICAL_V2_AUTHORITY_OBJECT_SCHEMA_SHA256,
        HISTORICAL_V2_AUTHORITY_RECEIPT_SCHEMA_SHA256,
    ):
        raise RankHeadV2AuthorityError(
            "historical consumed r2 authority schemas are inactive"
        )
    if pair != (
        AUTHORITY_OBJECT_SCHEMA_SHA256,
        AUTHORITY_RECEIPT_SCHEMA_SHA256,
    ):
        raise RankHeadV2AuthorityError("active v2 authority schema identity mismatch")


def _runtime_private(
    repository: Path,
    spec: integration.V2RunSpec,
    *,
    allow_historical: bool = False,
) -> balanced.PrivateBinding:
    """Reconstruct the only admissible private binding from repository custody."""
    expected_spec = (
        integration.known_run_spec(spec.run_id)
        if allow_historical
        else integration.run_spec(spec.run_id)
    )
    if spec != expected_spec:
        raise RankHeadV2AuthorityError("v2 authority run specification changed")
    source = integration.source_configuration(spec)
    source_private = balanced._private_binding_from_repository(repository, source)
    private = integration.runtime_private_from_source(source_private, spec)
    configuration = private.configuration
    expected_profile = f"{v2.DESIGN_ID}:{spec.source_binding}"
    expected_domain = f"{v2.DESIGN_ID}:{spec.source_binding}:runtime-v1"
    if not all(
        (
            configuration.profile_id == expected_profile,
            configuration.preregistration_path == integration.RUN_DESIGN_PATH,
            configuration.secret_path == source.secret_path,
            configuration.creation_receipt_path == source.creation_receipt_path,
            configuration.run_modes == {spec.run_id: "full-information"},
            configuration.domain_separation_identity == expected_domain,
            configuration.protected_starting_sha == integration.STARTING_PROTECTED_MAIN,
            private.creation_receipt_commitment is not None,
        )
    ):
        raise RankHeadV2AuthorityError("v2 authority private binding scope changed")
    if not all(
        (
            private.secret_commitment == source_private.secret_commitment,
            private.alias_map_commitment == source_private.alias_map_commitment,
            dict(private.branch_alias_map_commitments)
            == dict(source_private.branch_alias_map_commitments),
            private.creation_receipt_commitment
            == source_private.creation_receipt_commitment,
            dict(private.alias_to_internal) == dict(source_private.alias_to_internal),
            dict(private.branch_alias_to_internal)
            == dict(source_private.branch_alias_to_internal),
            hmac.compare_digest(
                private.run_key(spec.run_id),
                integration.derive_v2_run_key(source_private, spec),
            ),
        )
    ):
        raise RankHeadV2AuthorityError("v2 source private custody changed")
    return private


def _projection_fields(
    run_projection: Mapping[str, Any],
    static_projection: Mapping[str, Any],
) -> tuple[str, str, str, str, str, str]:
    return (
        _require_sha(str(run_projection.get("artifact_sha256", "")), "run design artifact"),
        _require_sha(str(run_projection.get("document_sha256", "")), "run design document"),
        _require_sha(
            str(run_projection.get("implementation_binding_sha256", "")),
            "run design implementation binding",
        ),
        _require_sha(
            str(static_projection.get("artifact_sha256", "")),
            "static preregistration artifact",
        ),
        _require_sha(
            str(static_projection.get("document_sha256", "")),
            "static preregistration document",
        ),
        _require_sha(
            str(static_projection.get("design_contract_sha256", "")),
            "static design contract",
        ),
    )


def _predecessor_binding(
    repository: Path,
    spec: integration.V2RunSpec,
) -> tuple[str | None, str | None, str | None]:
    if spec.predecessor_run_id is None:
        return None, None, None
    publication = run_design.require_binding_1_v2_terminal_visible(
        repository
    ).get("publication", {})
    commit = publication.get("commit")
    record_sha256 = publication.get("record_sha256")
    if (
        publication.get("layout") != "split-experiment-record"
        or publication.get("run_id") != spec.predecessor_run_id
        or not isinstance(commit, str)
        or GIT_COMMIT_RE.fullmatch(commit) is None
        or not isinstance(record_sha256, str)
        or SHA256_RE.fullmatch(record_sha256) is None
    ):
        raise RankHeadV2AuthorityError(
            "v2 predecessor publication identity is invalid"
        )
    return spec.predecessor_run_id, commit, record_sha256


def build_external_authority(
    *,
    repository: Path,
    spec: integration.V2RunSpec,
    raw_authority_id: str,
    authorized_commit: str,
    current_commit: str,
    model_sha256: str,
    binary_sha256: str,
) -> RankHeadV2ExternalAuthority:
    repository = repository.absolute()
    derived_authority_id_sha256 = authority_id_sha256(raw_authority_id)
    assert_authority_id_not_retired(derived_authority_id_sha256)
    private = _runtime_private(repository, spec)
    if (
        not isinstance(authorized_commit, str)
        or not GIT_COMMIT_RE.fullmatch(authorized_commit)
        or authorized_commit != current_commit
    ):
        raise RankHeadV2AuthorityError("v2 authorized commit mismatch")
    run_design_projection = run_design.validate_run_design(repository)
    static_preregistration_projection = v2.validate_preregistration(repository)
    (
        run_artifact,
        run_document,
        run_implementation,
        static_artifact,
        static_document,
        static_contract,
    ) = _projection_fields(run_design_projection, static_preregistration_projection)
    predecessor = _predecessor_binding(repository, spec)
    carrier = v2.build_v2_carrier()
    authority = RankHeadV2ExternalAuthority(
        schema_version=AUTHORITY_SCHEMA_VERSION,
        authority_kind=AUTHORITY_KIND,
        authority_id_sha256=derived_authority_id_sha256,
        authorized_commit=authorized_commit,
        run_id=spec.run_id,
        run_ordinal=spec.ordinal,
        source_binding=spec.source_binding,
        predecessor_run_id=predecessor[0],
        predecessor_publication_commit=predecessor[1],
        predecessor_publication_record_sha256=predecessor[2],
        run_design_artifact_sha256=run_artifact,
        run_design_document_sha256=run_document,
        run_design_implementation_binding_sha256=run_implementation,
        static_preregistration_artifact_sha256=static_artifact,
        static_preregistration_document_sha256=static_document,
        static_design_contract_sha256=static_contract,
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
    repository: Path,
    authority: RankHeadV2ExternalAuthority,
) -> str:
    spec = integration.run_spec(authority.run_id)
    private = _runtime_private(repository.absolute(), spec)
    return hmac.new(
        private.run_key(authority.run_id),
        AUTHORITY_RECEIPT_DOMAIN
        + balanced.canonical_json_bytes(authority.body()),
        hashlib.sha256,
    ).hexdigest().upper()


def validate_external_authority(
    repository: Path,
    authority: RankHeadV2ExternalAuthority,
    *,
    spec: integration.V2RunSpec,
    current_commit: str,
    receipt_hmac: str | None = None,
    expected_model_sha256: str | None = None,
    expected_binary_sha256: str | None = None,
    require_current_static: bool = True,
) -> None:
    repository = repository.absolute()
    active_spec = integration.run_spec(authority.run_id)
    if spec != active_spec:
        raise RankHeadV2AuthorityError("v2 authority run specification changed")
    assert_authority_id_not_retired(authority.authority_id_sha256)
    private = _runtime_private(repository, spec)
    expected_predecessor = (
        _predecessor_binding(repository, spec)
        if require_current_static
        else None
    )
    projections = (
        _projection_fields(
            run_design.validate_run_design(repository),
            v2.validate_preregistration(repository),
        )
        if require_current_static
        else (
            authority.run_design_artifact_sha256,
            authority.run_design_document_sha256,
            authority.run_design_implementation_binding_sha256,
            authority.static_preregistration_artifact_sha256,
            authority.static_preregistration_document_sha256,
            authority.static_design_contract_sha256,
        )
    )
    sha_values = (
        authority.authority_id_sha256,
        authority.run_design_artifact_sha256,
        authority.run_design_document_sha256,
        authority.run_design_implementation_binding_sha256,
        authority.static_preregistration_artifact_sha256,
        authority.static_preregistration_document_sha256,
        authority.static_design_contract_sha256,
        authority.carrier_root_sha256,
        authority.model_sha256,
            authority.binary_sha256,
        authority.run_key_commitment,
    )
    expected = all(
        (
            spec == integration.run_spec(authority.run_id),
            authority.schema_version == AUTHORITY_SCHEMA_VERSION,
            authority.authority_kind == AUTHORITY_KIND,
            all(isinstance(value, str) and SHA256_RE.fullmatch(value) for value in sha_values),
            isinstance(authority.authorized_commit, str)
            and GIT_COMMIT_RE.fullmatch(authority.authorized_commit) is not None,
            authority.run_id == spec.run_id,
            authority.run_ordinal == spec.ordinal,
            authority.source_binding == spec.source_binding,
            (
                (
                    authority.predecessor_run_id,
                    authority.predecessor_publication_commit,
                    authority.predecessor_publication_record_sha256,
                )
                == expected_predecessor
                if expected_predecessor is not None
                else (
                    authority.predecessor_run_id == spec.predecessor_run_id
                    and (
                        spec.predecessor_run_id is None
                        and authority.predecessor_publication_commit is None
                        and authority.predecessor_publication_record_sha256 is None
                        or spec.predecessor_run_id is not None
                        and isinstance(
                            authority.predecessor_publication_commit, str
                        )
                        and GIT_COMMIT_RE.fullmatch(
                            authority.predecessor_publication_commit
                        )
                        is not None
                        and isinstance(
                            authority.predecessor_publication_record_sha256,
                            str,
                        )
                        and SHA256_RE.fullmatch(
                            authority.predecessor_publication_record_sha256
                        )
                        is not None
                    )
                )
            ),
            authority.authorized_commit == current_commit,
            authority.carrier_id == v2.V2_CARRIER_ID,
            authority.carrier_root_sha256
            == v2.build_v2_carrier()["carrier_root_sha256"],
            authority.state_root == run_design.STATE_ROOT,
            (
                expected_model_sha256 is None
                or authority.model_sha256
                == _require_sha(expected_model_sha256, "expected model")
            ),
            (
                expected_binary_sha256 is None
                or authority.binary_sha256
                == _require_sha(expected_binary_sha256, "expected binary")
            ),
            (
                authority.run_design_artifact_sha256,
                authority.run_design_document_sha256,
                authority.run_design_implementation_binding_sha256,
                authority.static_preregistration_artifact_sha256,
                authority.static_preregistration_document_sha256,
                authority.static_design_contract_sha256,
            )
            == projections,
            authority.run_key_commitment
            == balanced.run_key_commitment(
                private.run_key(spec.run_id),
                private.configuration,
            ),
            type(authority.maximum_invocations) is int
            and authority.maximum_invocations == 1,
            type(authority.retry_count) is int and authority.retry_count == 0,
            authority.automatic_follow_on is False,
        )
    )
    if not expected:
        raise RankHeadV2AuthorityError("v2 external authority scope mismatch")
    authority.body()
    if receipt_hmac is not None and not hmac.compare_digest(
        receipt_hmac,
        authority_receipt_hmac(repository, authority),
    ):
        raise RankHeadV2AuthorityError("v2 external authority HMAC mismatch")


def authority_receipt_path(repository: Path, run_id: str) -> Path:
    integration.known_run_spec(run_id)
    assert_test_repository_isolated(repository)
    return repository.absolute() / RECEIPT_TEMPLATE.replace("<run-id>", run_id)


def _is_reparse(path: Path) -> bool:
    return balanced._is_reparse(path)


def _assert_safe_ancestry(repository: Path, target: Path) -> None:
    balanced._assert_safe_ancestry(repository, target)


def _receipt_document(
    repository: Path,
    authority: RankHeadV2ExternalAuthority,
) -> dict[str, Any]:
    require_active_schema_identities(
        AUTHORITY_OBJECT_SCHEMA_SHA256,
        AUTHORITY_RECEIPT_SCHEMA_SHA256,
    )
    document = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "authority": authority.body(),
        "authority_object_schema_sha256": AUTHORITY_OBJECT_SCHEMA_SHA256,
        "authority_receipt_schema_sha256": AUTHORITY_RECEIPT_SCHEMA_SHA256,
        "authority_receipt_hmac": authority_receipt_hmac(repository, authority),
        "consumed": True,
        "consumption_occurred_before_live_mutation": True,
        "maximum_invocations": 1,
        "retry_allowed": False,
    }
    balanced.validate_metadata_only(document)
    return document


def _historical_v2_authority_from_body(
    repository: Path,
    body: Mapping[str, Any],
) -> HistoricalRankHeadV2ExternalAuthority:
    expected_fields = set(
        HistoricalRankHeadV2ExternalAuthority.__dataclass_fields__
    )
    if not isinstance(body, Mapping) or set(body) != expected_fields:
        raise RankHeadV2AuthorityError("historical r2 authority body is malformed")
    try:
        value = HistoricalRankHeadV2ExternalAuthority(**dict(body))
    except (TypeError, ValueError) as exc:
        raise RankHeadV2AuthorityError("historical r2 authority body is malformed") from exc
    spec = integration.known_run_spec(integration.LOST_CUSTODY_BINDING_1_RUN_ID)
    private = _runtime_private(repository, spec, allow_historical=True)
    sha_values = (
        value.authority_id_sha256,
        value.run_design_artifact_sha256,
        value.run_design_document_sha256,
        value.run_design_implementation_binding_sha256,
        value.static_preregistration_artifact_sha256,
        value.static_preregistration_document_sha256,
        value.static_design_contract_sha256,
        value.carrier_root_sha256,
        value.model_sha256,
        value.binary_sha256,
        value.run_key_commitment,
    )
    if not all(
        (
            value.body() == dict(body),
            value.schema_version == HISTORICAL_V2_AUTHORITY_SCHEMA_VERSION,
            value.authority_kind == AUTHORITY_KIND,
            value.authority_id_sha256
            == HISTORICAL_R2_CONSUMED_AUTHORITY_ID_SHA256,
            all(isinstance(item, str) and SHA256_RE.fullmatch(item) for item in sha_values),
            isinstance(value.authorized_commit, str)
            and GIT_COMMIT_RE.fullmatch(value.authorized_commit) is not None,
            value.run_id == spec.run_id,
            value.run_ordinal == spec.ordinal,
            value.source_binding == spec.source_binding,
            value.carrier_id == v2.V2_CARRIER_ID,
            value.carrier_root_sha256
            == v2.build_v2_carrier()["carrier_root_sha256"],
            value.state_root == run_design.STATE_ROOT,
            value.run_key_commitment
            == balanced.run_key_commitment(
                private.run_key(spec.run_id),
                private.configuration,
            ),
            type(value.maximum_invocations) is int
            and value.maximum_invocations == 1,
            type(value.retry_count) is int and value.retry_count == 0,
            value.automatic_follow_on is False,
        )
    ):
        raise RankHeadV2AuthorityError("historical r2 authority scope mismatch")
    return value


def _historical_v2_receipt_hmac(
    repository: Path,
    authority_value: HistoricalRankHeadV2ExternalAuthority,
) -> str:
    spec = integration.known_run_spec(authority_value.run_id)
    private = _runtime_private(repository, spec, allow_historical=True)
    return hmac.new(
        private.run_key(spec.run_id),
        AUTHORITY_RECEIPT_DOMAIN
        + balanced.canonical_json_bytes(authority_value.body()),
        hashlib.sha256,
    ).hexdigest().upper()


def _verify_historical_v2_receipt_bytes(
    repository: Path,
    run_id: str,
    payload: bytes,
) -> dict[str, Any]:
    if run_id != integration.LOST_CUSTODY_BINDING_1_RUN_ID:
        raise RankHeadV2AuthorityError("unknown historical v2 receipt")
    if not isinstance(payload, bytes) or len(payload) > 32768:
        raise RankHeadV2AuthorityError("historical r2 authority receipt is unsafe")
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RankHeadV2AuthorityError("historical r2 authority receipt is invalid") from exc
    if not isinstance(document, Mapping):
        raise RankHeadV2AuthorityError("historical r2 authority receipt root is malformed")
    value = _historical_v2_authority_from_body(
        repository,
        document.get("authority", {}),
    )
    expected = {
        "schema_version": HISTORICAL_V2_RECEIPT_SCHEMA_VERSION,
        "authority": value.body(),
        "authority_object_schema_sha256": (
            HISTORICAL_V2_AUTHORITY_OBJECT_SCHEMA_SHA256
        ),
        "authority_receipt_schema_sha256": (
            HISTORICAL_V2_AUTHORITY_RECEIPT_SCHEMA_SHA256
        ),
        "authority_receipt_hmac": _historical_v2_receipt_hmac(repository, value),
        "consumed": True,
        "consumption_occurred_before_live_mutation": True,
        "maximum_invocations": 1,
        "retry_allowed": False,
    }
    if document != expected:
        raise RankHeadV2AuthorityError("historical r2 authority receipt binding changed")
    evidence = {
        "authority": value.body(),
        "authority_receipt_hmac": document["authority_receipt_hmac"],
        "authority_receipt_sha256": sha256_bytes(payload),
        "consumed": True,
        "consumption_occurred_before_live_mutation": True,
        "maximum_invocations": 1,
        "retry_allowed": False,
    }
    balanced.validate_metadata_only(evidence)
    return evidence


def _verify_historical_v2_receipt(
    repository: Path,
    run_id: str,
) -> dict[str, Any]:
    target = authority_receipt_path(repository, run_id)
    _assert_safe_ancestry(repository, target)
    if (
        not target.is_file()
        or _is_reparse(target)
        or target.stat().st_size > 32768
    ):
        raise RankHeadV2AuthorityError(
            "historical r2 authority receipt is missing or unsafe"
        )
    return _verify_historical_v2_receipt_bytes(
        repository,
        run_id,
        target.read_bytes(),
    )


def assert_authority_unconsumed(
    repository: Path,
    run_id: str,
    authority_id_hash: str | None = None,
) -> None:
    repository = repository.absolute()
    if authority_id_hash is not None:
        assert_authority_id_not_retired(authority_id_hash)
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
    for other_run_id in integration.RECEIPT_INVENTORY_RUN_IDS:
        other = authority_receipt_path(repository, other_run_id)
        if not other.exists() and not other.is_symlink():
            continue
        try:
            evidence = verify_authority_receipt_for_run(
                repository,
                other_run_id,
                require_current_static=False,
            )
        except (OSError, json.JSONDecodeError, RankHeadV2AuthorityError) as exc:
            raise RankHeadV2AuthorityError(
                "v2 authority receipt inventory is invalid"
            ) from exc
        if (
            evidence.get("authority", {}).get("authority_id_sha256")
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
    authority: RankHeadV2ExternalAuthority,
    *,
    expected_model_sha256: str,
    expected_binary_sha256: str,
) -> dict[str, Any]:
    repository = repository.absolute()
    spec = integration.run_spec(authority.run_id)
    validate_external_authority(
        repository,
        authority,
        spec=spec,
        current_commit=authority.authorized_commit,
        expected_model_sha256=expected_model_sha256,
        expected_binary_sha256=expected_binary_sha256,
    )
    state_root = repository / "state"
    if not state_root.is_dir() or _is_reparse(state_root):
        raise RankHeadV2AuthorityError("state root is missing or unsafe")
    target = authority_receipt_path(repository, authority.run_id)
    payload = balanced.canonical_json_bytes(_receipt_document(repository, authority))
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
    return verify_authority_receipt(repository, authority)


def verify_authority_receipt(
    repository: Path,
    authority: RankHeadV2ExternalAuthority | HistoricalRankHeadV2ExternalAuthority,
    *,
    require_current_static: bool = True,
) -> dict[str, Any]:
    repository = repository.absolute()
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
    evidence = verify_authority_receipt_bytes_for_run(
        repository,
        authority.run_id,
        target.read_bytes(),
        require_current_static=require_current_static,
    )
    if evidence.get("authority") != authority.body():
        raise RankHeadV2AuthorityError("v2 authority receipt body changed")
    return evidence


def authority_from_body(body: Mapping[str, Any]) -> RankHeadV2ExternalAuthority:
    expected_fields = set(RankHeadV2ExternalAuthority.__dataclass_fields__)
    if not isinstance(body, Mapping) or set(body) != expected_fields:
        raise RankHeadV2AuthorityError("v2 authority body is malformed")
    try:
        value = RankHeadV2ExternalAuthority(**dict(body))
    except (TypeError, ValueError) as exc:
        raise RankHeadV2AuthorityError("v2 authority body is malformed") from exc
    if value.body() != dict(body):
        raise RankHeadV2AuthorityError("v2 authority body changed during reconstruction")
    if value.schema_version != AUTHORITY_SCHEMA_VERSION:
        raise RankHeadV2AuthorityError("inactive v2 authority schema version")
    integration.run_spec(value.run_id)
    assert_authority_id_not_retired(value.authority_id_sha256)
    return value


def verify_authority_receipt_bytes_for_run(
    repository: Path,
    run_id: str,
    payload: bytes,
    *,
    require_current_static: bool = True,
) -> dict[str, Any]:
    """Verify receipt bytes directly, independent of the live receipt path."""
    repository = repository.absolute()
    integration.known_run_spec(run_id)
    if not isinstance(payload, bytes) or len(payload) > 32768:
        raise RankHeadV2AuthorityError("v2 authority receipt is unsafe")
    if run_id == integration.LOST_CUSTODY_BINDING_1_RUN_ID:
        if require_current_static:
            raise RankHeadV2AuthorityError(
                "historical consumed r2 authority cannot authorize execution"
            )
        return _verify_historical_v2_receipt_bytes(
            repository,
            run_id,
            payload,
        )
    spec = integration.run_spec(run_id)
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RankHeadV2AuthorityError("v2 authority receipt is invalid") from exc
    if not isinstance(document, Mapping):
        raise RankHeadV2AuthorityError("v2 authority receipt root is malformed")
    require_active_schema_identities(
        str(document.get("authority_object_schema_sha256", "")),
        str(document.get("authority_receipt_schema_sha256", "")),
    )
    authority_value = authority_from_body(document.get("authority", {}))
    if authority_value.run_id != spec.run_id:
        raise RankHeadV2AuthorityError("v2 authority receipt run changed")
    expected = _receipt_document(repository, authority_value)
    if document != expected:
        raise RankHeadV2AuthorityError("v2 authority receipt binding changed")
    validate_external_authority(
        repository,
        authority_value,
        spec=spec,
        current_commit=authority_value.authorized_commit,
        receipt_hmac=str(document.get("authority_receipt_hmac", "")),
        require_current_static=require_current_static,
    )
    evidence = {
        "authority": authority_value.body(),
        "authority_receipt_hmac": document["authority_receipt_hmac"],
        "authority_receipt_sha256": sha256_bytes(payload),
        "consumed": True,
        "consumption_occurred_before_live_mutation": True,
        "maximum_invocations": 1,
        "retry_allowed": False,
    }
    balanced.validate_metadata_only(evidence)
    return evidence


def verify_authority_receipt_for_run(
    repository: Path,
    run_id: str,
    *,
    require_current_static: bool = True,
) -> dict[str, Any]:
    """Cryptographically reconstruct and verify one consumed receipt by run ID."""
    repository = repository.absolute()
    target = authority_receipt_path(repository, run_id)
    _assert_safe_ancestry(repository, target)
    if (
        not target.is_file()
        or _is_reparse(target)
        or target.stat().st_size > 32768
    ):
        raise RankHeadV2AuthorityError("v2 authority receipt is missing or unsafe")
    return verify_authority_receipt_bytes_for_run(
        repository,
        run_id,
        target.read_bytes(),
        require_current_static=require_current_static,
    )
