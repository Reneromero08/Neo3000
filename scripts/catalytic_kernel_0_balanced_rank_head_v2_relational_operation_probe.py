#!/usr/bin/env python3
"""Four-request contrastive probe for the CK0 transform's relational operation.

The static path derives two outcome-independent private geometries from the
existing position-crossover root, freezes five competing predictions, and
writes one zero-execution preregistration.  The live path remains closed until
a later external one-shot authority binds the published static commit.
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
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import catalytic_inference_bench_0_runtime as runtime_support
import catalytic_kernel_0 as kernel
import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_parent_dependence_cross_binding_asymmetry_audit as asymmetry
import catalytic_kernel_0_balanced_rank_head_v2 as v2
import catalytic_kernel_0_balanced_rank_head_v2_authority as source_authority
import catalytic_kernel_0_balanced_rank_head_v2_parent_dependence as transaction
import catalytic_kernel_0_balanced_rank_head_v2_position_seed_crossover as crossover
import catalytic_kernel_0_balanced_rank_head_v2_relational_operation_probe_scientific as scientific


class RelationalOperationProbeError(ValueError):
    """The probe geometry, private custody, or one-shot contract changed."""


DESIGN_ID = scientific.DESIGN_ID
STARTING_PROTECTED_MAIN = "b6600c2800a80c0892bef15bca5ee2ce577ef34f"
PREREGISTRATION_PATH = Path(
    "lab/ck0_balanced_opaque_rank_head_v2_relational_operation_probe_1.json"
)
PRIVATE_ROOT_PATH = crossover.PRIVATE_ROOT_PATH
PRIVATE_RECEIPT_PATH = crossover.PRIVATE_RECEIPT_PATH
STATE_ROOT = Path("state/catalytic_kernel_0/relational_operation_probe_v1")
ARCHIVE_ROOT = Path("state/catalytic_kernel_0/relational_operation_probe_evidence_archive/v1")
AUTHORITY_RECEIPT_PATH = Path(
    "state/catalytic_kernel_0_authority.relational-operation-probe-v1.authority.consumed.json"
)

REQUEST_IDS = scientific.REQUEST_IDS
EXECUTION_ORDER = REQUEST_IDS
GEOMETRY_IDS = ("G0", "G1")
PRESENTATION_ORDERS = ("AB", "BA")
MECHANISMS = (
    "unique-intersection",
    "lexical-first",
    "first-listed",
    "parent-a-priority",
    "parent-b-priority",
)
FIXED_TRANSFORM_SEED = 830800182
MAXIMUM_SELECTION_ATTEMPTS = 4096
MODEL_SHA256 = asymmetry.EXPECTED_MODEL_SHA256
BINARY_SHA256 = transaction.BINARY_SHA256
CARRIER_ROOT_SHA256 = transaction.CARRIER_ROOT_SHA256
SOURCE_ADJUDICATION_PATH = Path(
    "lab/ck0_balanced_opaque_rank_head_v2_position_seed_crossover_adjudication_1.json"
)
SOURCE_ADJUDICATION_SHA256 = (
    "DD829AE6C4F38EDA325462AD24D030AA7DF3E74FC69D54C80DE1F9996C820B53"
)
SOURCE_RESULT_RECORD_ID = "neo-exp-0042"
SOURCE_RESULT_RECORD_SHA256 = (
    "DAF072E43700F71A76537843507C578FEA38679AA15DC9A0C783090B29D5D0E8"
)

PROBE_CONFIGURATION = balanced.PrivateBindingConfiguration(
    profile_id=DESIGN_ID,
    preregistration_path=PREREGISTRATION_PATH.as_posix(),
    secret_path=PRIVATE_ROOT_PATH.as_posix(),
    creation_receipt_path=PRIVATE_RECEIPT_PATH.as_posix(),
    run_modes={request_id: "transform-only" for request_id in REQUEST_IDS},
    domain_separation_identity="ck0-rank-head-v2-relational-operation-probe-v1",
    protected_starting_sha=STARTING_PROTECTED_MAIN,
)

GEOMETRY_ORDER_DOMAIN = b"ck0-rank-head-v2/relational-operation-probe/geometry-order-v1\0"
GEOMETRY_COMMITMENT_DOMAIN = b"ck0-rank-head-v2/relational-operation-probe/geometry-v1\0"
CANDIDATE_COMMITMENT_DOMAIN = b"ck0-rank-head-v2/relational-operation-probe/candidate-v1\0"
PARENT_COMMITMENT_DOMAIN = b"ck0-rank-head-v2/relational-operation-probe/parent-v1\0"
EXPERIMENT_KEY_DOMAIN = b"ck0-rank-head-v2/relational-operation-probe/experiment-key-v1\0"
AUTHORITY_ID_DOMAIN = b"ck0-rank-head-v2/relational-operation-probe/authority-id-v1\0"
AUTHORITY_HMAC_DOMAIN = b"ck0-rank-head-v2/relational-operation-probe/authority-hmac-v1\0"
JOURNAL_HMAC_DOMAIN = b"ck0-rank-head-v2/relational-operation-probe/journal-hmac-v1\0"
AUTHORITY_SCHEMA_VERSION = "rank-head-v2-relational-operation-probe-authority-v1"
AUTHORITY_RECEIPT_SCHEMA_VERSION = "rank-head-v2-relational-operation-probe-consumption-v1"
AUTHORITY_KIND = "external-one-shot-relational-operation-probe"
PREREGISTRATION_SCHEMA_VERSION = 1
JOURNAL_SCHEMA_VERSION = 1
SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
AUTHORITY_ID_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
GENESIS_HASH = "0" * 64
FORBIDDEN_PUBLIC_ID_RE = re.compile(rb'"(?:K|C)[0-9]{2}"')

LOCKED_CLAIMS = {
    "formal_algebra": "locked",
    "position_independent_bilateral_dependence": "locked",
    "general_two_parent_necessity": "locked",
    "cross_binding_generalization": "locked",
    "general_catalytic_inference": "locked",
    "transfer": "locked",
    "task_advantage": "locked",
    "superiority": "locked",
    "sota": "locked",
    "broader_process_local_holostate": "locked",
    "restart_persistence": "locked",
    "deep": "locked",
    "automatic_promotion": False,
}

NORMALIZED_READINESS_FAILURE_FIELDS = (
    "poll_count",
    "readiness_seconds",
    "process_alive",
    "stable_health_ok",
    "sidecar_health_ok",
    "wddm_attributed",
    "wddm_fresh",
    "wddm_snapshot",
    "stable_listener",
    "sidecar_listener",
    "stable_listener_confirmation",
    "stable_health_recovery",
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RelationalOperationProbeError(message)


def _require_regular(
    path: Path,
    label: str,
    *,
    exact: int | None = None,
    maximum: int = 8 * 1024 * 1024,
) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise RelationalOperationProbeError(f"{label} is not a regular file")
        data = path.read_bytes()
    except OSError as exc:
        raise RelationalOperationProbeError(f"{label} is unreadable") from exc
    if exact is not None:
        _require(len(data) == exact, f"{label} byte length changed")
    else:
        _require(0 < len(data) <= maximum, f"{label} has an unsafe size")
    return data


def _json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(_require_regular(path, label))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RelationalOperationProbeError(f"{label} is malformed") from exc
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
        _require(_require_regular(path, path.name) == data, f"{path.name} differs from frozen bytes")
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
    data = canonical_json_bytes(value)
    _require(not FORBIDDEN_PUBLIC_ID_RE.search(data), "private candidate identity entered public metadata")
    lowered = data.lower()
    for forbidden in (
        b'"private_root"',
        b'"alias_map"',
        b'"ranking"',
        b'"raw_authority_id"',
        b'"support_aliases"',
    ):
        _require(forbidden not in lowered, "private or model-authored content entered public metadata")


def _lifecycle_failure(exc: BaseException) -> dict[str, Any]:
    failure: dict[str, Any] = {
        "request_id": None,
        "failure_sha256": sha256_bytes(str(exc).encode("utf-8")),
        "retry_allowed": False,
    }
    evidence = getattr(exc, "evidence", None)
    if isinstance(evidence, Mapping):
        normalized = {
            field: evidence[field]
            for field in NORMALIZED_READINESS_FAILURE_FIELDS
            if field in evidence
        }
        if normalized:
            failure["readiness_evidence"] = normalized
    _assert_public_no_smuggle(failure)
    return failure


def _probe_binding(root: bytes) -> balanced.PrivateBinding:
    _require(len(root) == 32, "private binding root length changed")
    return balanced.PrivateBinding.from_secret(root, PROBE_CONFIGURATION)


def _load_private(repository: Path) -> tuple[bytes, balanced.PrivateBinding]:
    root = _require_regular(repository / PRIVATE_ROOT_PATH, "private binding root", exact=32)
    return root, _probe_binding(root)


def _experiment_key(root: bytes) -> bytes:
    return hmac.new(root, EXPERIMENT_KEY_DOMAIN + DESIGN_ID.encode("utf-8"), hashlib.sha256).digest()


def _private_hmac(root: bytes, domain: bytes, value: Any) -> str:
    return hmac.new(root, domain + canonical_json_bytes(value), hashlib.sha256).hexdigest().upper()


def _candidate_commitment(root: bytes, geometry_id: str, alias: str) -> str:
    return _private_hmac(root, CANDIDATE_COMMITMENT_DOMAIN, [geometry_id, alias])


def _alias_order(root: bytes, counter: int) -> list[str]:
    _require(0 <= counter < MAXIMUM_SELECTION_ATTEMPTS, "geometry selection counter changed")
    prefix = GEOMETRY_ORDER_DOMAIN + counter.to_bytes(4, "big")
    return sorted(
        balanced.ALIASES,
        key=lambda alias: hmac.new(root, prefix + alias.encode("ascii"), hashlib.sha256).digest(),
    )


def _build_geometry(geometry_id: str, aliases: Sequence[str]) -> dict[str, Any]:
    _require(geometry_id in GEOMETRY_IDS, "geometry identity changed")
    _require(len(aliases) == 9 and len(set(aliases)) == 9, "geometry candidate cardinality changed")
    lexical = min(aliases)
    remaining = [alias for alias in aliases if alias != lexical]
    shared, a_head, b_head, a_mid, a_tail, b_mid, b_tail, b_last = remaining
    parent_a = [a_head, a_mid, lexical, shared, a_tail]
    parent_b = [b_head, b_mid, shared, b_tail, b_last]
    _require(len(set(parent_a) & set(parent_b)) == 1, "geometry does not have one unique intersection")
    _require(parent_a[3] == shared and parent_b[2] == shared, "shared candidate position changed")
    _require(
        len({shared, lexical, parent_a[0], parent_b[0]}) == 4,
        "geometry does not discriminate intersection from surface and parent priorities",
    )
    return {
        "geometry_id": geometry_id,
        "parent-a": parent_a,
        "parent-b": parent_b,
        "unique-intersection": shared,
        "lexical-first": lexical,
    }


def private_geometries(root: bytes, counter: int) -> dict[str, dict[str, Any]]:
    order = _alias_order(root, counter)
    geometries = {
        "G0": _build_geometry("G0", order[:9]),
        "G1": _build_geometry("G1", order[9:18]),
    }
    _require(
        set(geometries["G0"]["parent-a"] + geometries["G0"]["parent-b"]).isdisjoint(
            geometries["G1"]["parent-a"] + geometries["G1"]["parent-b"]
        ),
        "matched geometries are not identity-disjoint",
    )
    _require(
        geometries["G0"]["unique-intersection"] != geometries["G1"]["unique-intersection"],
        "matched geometries share the same intersection candidate",
    )
    return geometries


def _request_parts(request_id: str) -> tuple[str, str]:
    _require(request_id in REQUEST_IDS, "request identity changed")
    geometry_id, order = request_id.split("-", 1)
    return geometry_id, order


def _parent_artifact(root: bytes, geometry: Mapping[str, Any], role: str) -> dict[str, Any]:
    _require(role in {"parent-a", "parent-b"}, "parent role changed")
    support = list(geometry[role])
    body = {
        "artifact_role": role,
        "geometry_id": geometry["geometry_id"],
        "support_aliases": support,
        "support_cardinality": 5,
    }
    return {
        **body,
        "relation_commitment": _private_hmac(root, PARENT_COMMITMENT_DOMAIN, body),
    }


def build_assignment(
    root: bytes,
    geometries: Mapping[str, Mapping[str, Any]],
    request_id: str,
) -> dict[str, Any]:
    geometry_id, order = _request_parts(request_id)
    geometry = geometries[geometry_id]
    parent_a = _parent_artifact(root, geometry, "parent-a")
    parent_b = _parent_artifact(root, geometry, "parent-b")
    parents = [parent_a, parent_b] if order == "AB" else [parent_b, parent_a]
    _require(order in PRESENTATION_ORDERS, "parent presentation order changed")
    assignment = {
        "stage": "transform",
        "instruction": (
            "Operate only on the two supplied opaque parent relations. Author one allowed "
            "operator and rank exactly three supplied opaque candidates."
        ),
        "parent_artifacts": parents,
    }
    balanced._assert_no_internal_identity(assignment)
    balanced.validate_metadata_only(assignment)
    return assignment


def build_request(
    root: bytes,
    geometries: Mapping[str, Mapping[str, Any]],
    request_id: str,
) -> dict[str, Any]:
    carrier = v2.build_v2_carrier()
    _require(carrier["carrier_root_sha256"] == CARRIER_ROOT_SHA256, "carrier root changed")
    assignment = build_assignment(root, geometries, request_id)
    payload = {
        "model": balanced.MODEL_ALIAS,
        "messages": [
            {"role": "system", "content": carrier["carrier_root"]},
            {"role": "user", "content": canonical_json_text(assignment)},
        ],
        "temperature": 0.0,
        "seed": FIXED_TRANSFORM_SEED,
        "max_tokens": 64,
        "stream": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "ck0_rank_head_v2_relational_operation_probe_transform",
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


def _private_predictions(geometry: Mapping[str, Any], request_id: str) -> dict[str, str]:
    _geometry_id, order = _request_parts(request_id)
    first_parent = "parent-a" if order == "AB" else "parent-b"
    return {
        "unique-intersection": str(geometry["unique-intersection"]),
        "lexical-first": str(geometry["lexical-first"]),
        "first-listed": str(geometry[first_parent][0]),
        "parent-a-priority": str(geometry["parent-a"][0]),
        "parent-b-priority": str(geometry["parent-b"][0]),
    }


def _prediction_commitments(
    root: bytes,
    geometries: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, str]]:
    return {
        request_id: {
            mechanism: _candidate_commitment(root, geometry_id, alias)
            for mechanism, alias in _private_predictions(geometries[geometry_id], request_id).items()
        }
        for request_id in REQUEST_IDS
        for geometry_id, _order in [_request_parts(request_id)]
    }


def _public_geometry_commitments(
    root: bytes,
    geometries: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    public: dict[str, Any] = {}
    for geometry_id in GEOMETRY_IDS:
        geometry = geometries[geometry_id]
        public[geometry_id] = {
            "geometry_commitment_sha256": _private_hmac(
                root, GEOMETRY_COMMITMENT_DOMAIN, geometry
            ),
            "support_cardinality_per_parent": 5,
            "unique_intersection_cardinality": 1,
            "shared_candidate_positions_1_based": {"parent-a": 4, "parent-b": 3},
            "identity_disjoint_from_other_geometry": True,
            "different_unique_shared_candidate": True,
            "semantic_parent_commitments": {
                role: _private_hmac(
                    root,
                    PARENT_COMMITMENT_DOMAIN,
                    {
                        "artifact_role": role,
                        "geometry_id": geometry_id,
                        "support_aliases": list(geometry[role]),
                        "support_cardinality": 5,
                    },
                )
                for role in ("parent-a", "parent-b")
            },
        }
    return public


def _contrast_report(
    root: bytes,
    geometries: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    commitments = _prediction_commitments(root, geometries)
    per_request = {}
    for request_id in REQUEST_IDS:
        values = commitments[request_id]
        per_request[request_id] = {
            "prediction_commitments": values,
            "unique_prediction_count": len(set(values.values())),
            "expected_only_overlap": (
                "first-listed=parent-a-priority"
                if request_id.endswith("-AB")
                else "first-listed=parent-b-priority"
            ),
            "intersection_distinct_from_all_surface_and_parent_priorities": True,
        }
        _require(len(set(values.values())) == 4, "prediction contrast cardinality changed")
    return {
        "mechanisms": list(MECHANISMS),
        "per_request": per_request,
        "parent_order_swap_changes_first_listed_prediction": True,
        "parent_role_predictions_invariant_under_swap": True,
        "unique_intersection_prediction_invariant_under_swap": True,
        "lexical_prediction_invariant_under_swap": True,
        "intersection_vs_parent_order_and_surface_discriminated": True,
    }


def _selection_candidate(
    root: bytes,
    counter: int,
    tokenizer: asymmetry.OfflineTokenizer,
) -> dict[str, Any]:
    geometries = private_geometries(root, counter)
    assignments = {
        request_id: build_assignment(root, geometries, request_id)
        for request_id in REQUEST_IDS
    }
    serialized_lengths = {
        request_id: len(canonical_json_bytes(value))
        for request_id, value in assignments.items()
    }
    tokenizer_lengths = {
        request_id: tokenizer.length(canonical_json_text(value))
        for request_id, value in assignments.items()
    }
    eligible = (
        len(set(serialized_lengths.values())) == 1
        and len(set(tokenizer_lengths.values())) == 1
        and _contrast_report(root, geometries)[
            "intersection_vs_parent_order_and_surface_discriminated"
        ]
    )
    return {
        "counter": counter,
        "eligible": eligible,
        "geometries": geometries,
        "serialized_assignment_byte_lengths": serialized_lengths,
        "tokenizer_assignment_lengths": tokenizer_lengths,
    }


def select_first_eligible(
    root: bytes,
    tokenizer: asymmetry.OfflineTokenizer,
) -> dict[str, Any]:
    for counter in range(MAXIMUM_SELECTION_ATTEMPTS):
        candidate = _selection_candidate(root, counter, tokenizer)
        if candidate["eligible"]:
            return candidate
    raise RelationalOperationProbeError(
        "no contrastive geometry matched the frozen length and discrimination gates"
    )


def _file_binding(repository: Path, paths: Sequence[str]) -> dict[str, Any]:
    files = []
    for relative in paths:
        data = _require_regular(repository / relative, f"bound source {relative}")
        files.append({"path": relative, "byte_size": len(data), "sha256": sha256_bytes(data)})
    body = {"files": files}
    return {**body, "sha256": json_sha256(body)}


def _source_evidence(repository: Path) -> dict[str, Any]:
    artifact = _require_regular(repository / SOURCE_ADJUDICATION_PATH, "source adjudication")
    _require(sha256_bytes(artifact) == SOURCE_ADJUDICATION_SHA256, "source adjudication changed")
    records = [line for line in (repository / "lab/results.jsonl").read_bytes().splitlines() if line]
    matches = []
    for line in records:
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RelationalOperationProbeError("results ledger is malformed") from exc
        if isinstance(value, dict) and value.get("id") == SOURCE_RESULT_RECORD_ID:
            matches.append(line)
    _require(len(matches) == 1, "source result record multiplicity changed")
    _require(sha256_bytes(matches[0]) == SOURCE_RESULT_RECORD_SHA256, "source result record changed")
    return {
        "source_adjudication_path": SOURCE_ADJUDICATION_PATH.as_posix(),
        "source_adjudication_sha256": SOURCE_ADJUDICATION_SHA256,
        "source_result_record_id": SOURCE_RESULT_RECORD_ID,
        "source_result_record_sha256": SOURCE_RESULT_RECORD_SHA256,
        "source_supported_panel_classification": "SINGLETON_PRESENTATION_POSITION_EFFECT_SUPPORTED",
        "source_scope": "transform-causal-core-one-matched-private-binding",
    }


def _scientific_contract(
    private: balanced.PrivateBinding,
    geometry_commitments: Mapping[str, Any],
    prediction_commitments: Mapping[str, Any],
    request_hashes: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "design_id": DESIGN_ID,
        "request_ids": list(REQUEST_IDS),
        "execution_order": list(EXECUTION_ORDER),
        "request_sha256": dict(request_hashes),
        "private_binding_commitments": {
            "root_commitment_sha256": private.secret_commitment,
            "profile_binding_sha256": private.profile_binding_sha256,
            "alias_map_commitment_sha256": private.alias_map_commitment,
        },
        "geometry_commitments": dict(geometry_commitments),
        "prediction_commitments": dict(prediction_commitments),
        "fixed_transform_seed": FIXED_TRANSFORM_SEED,
        "model_sha256": MODEL_SHA256,
        "binary_sha256": BINARY_SHA256,
        "carrier_root_sha256": CARRIER_ROOT_SHA256,
        "response_schema_sha256": json_sha256(v2.v2_response_schema("transform")),
        "physical_slots": 1,
        "sidecar_epochs": 1,
        "maximum_model_generations_per_request": 1,
        "maximum_total_model_generations": 4,
        "request_dispatch": "frozen-scientific-module-exact-hash-gate-before-contact",
        "raw_response_recording": "authenticated-capture-before-controller-parse",
    }


def build_preregistration_document(repository: Path, model_path: Path) -> dict[str, Any]:
    repository = repository.resolve(strict=False)
    crossover.validate_private_binding(repository, model_path)
    root, private = _load_private(repository)
    tokenizer = asymmetry.OfflineTokenizer(model_path)
    selection = select_first_eligible(root, tokenizer)
    geometries = selection["geometries"]
    payloads = {
        request_id: build_request(root, geometries, request_id)
        for request_id in REQUEST_IDS
    }
    request_hashes = {
        request_id: json_sha256(payloads[request_id]) for request_id in REQUEST_IDS
    }
    geometry_commitments = _public_geometry_commitments(root, geometries)
    contrast = _contrast_report(root, geometries)
    prediction_commitments = {
        request_id: dict(contrast["per_request"][request_id]["prediction_commitments"])
        for request_id in REQUEST_IDS
    }
    contract = _scientific_contract(
        private, geometry_commitments, prediction_commitments, request_hashes
    )
    scientific_binding = scientific.frozen_scientific_binding(
        repository, contract=contract, payloads=payloads
    )
    controller_binding = _file_binding(
        repository,
        ("scripts/catalytic_kernel_0_balanced_rank_head_v2_relational_operation_probe.py",),
    )
    document = {
        "schema_version": PREREGISTRATION_SCHEMA_VERSION,
        "design_id": DESIGN_ID,
        "starting_protected_main": STARTING_PROTECTED_MAIN,
        "scientific_question": (
            "Does the joint-parent transform implement commutative unique-intersection-like "
            "recovery, parent-order or parent-role composition, a preregistered surface "
            "heuristic, generic rank stabilization, or no identifiable operation?"
        ),
        "source_evidence": _source_evidence(repository),
        "intervention": (
            "Exactly four transform-only requests over two pre-outcome matched private "
            "geometries, each presented in AB and BA order under one fixed seed."
        ),
        "private_binding": {
            "source_root": "existing-ignored-position-crossover-private-root",
            "fresh_private_root_created": False,
            "root_commitment_sha256": private.secret_commitment,
            "profile_binding_sha256": private.profile_binding_sha256,
            "alias_map_commitment_sha256": private.alias_map_commitment,
            "private_root_published": False,
            "private_mapping_published": False,
        },
        "geometry_selection": {
            "method": "first-outcome-independent-HMAC-order-matching-frozen-contrast-and-length-gates",
            "selected_counter": selection["counter"],
            "maximum_attempts": MAXIMUM_SELECTION_ATTEMPTS,
            "first_match_verified": True,
            "geometry_commitments": geometry_commitments,
            "serialized_assignment_byte_lengths": selection[
                "serialized_assignment_byte_lengths"
            ],
            "tokenizer_assignment_lengths": selection["tokenizer_assignment_lengths"],
            "serialized_lengths_matched": True,
            "tokenizer_lengths_matched": True,
            "same_field_structure": True,
            "same_support_cardinalities": True,
            "different_decoy_identities_and_orderings": True,
            "selected_before_model_outcomes": True,
        },
        "request_set": {
            "request_ids": list(REQUEST_IDS),
            "execution_order": list(EXECUTION_ORDER),
            "request_sha256": request_hashes,
            "request_count": 4,
            "unique_request_count": len(set(request_hashes.values())),
            "transform_only": True,
            "borrow_requests": 0,
            "branch_requests": 0,
            "model_authored_extraction_requests": 0,
            "restore_requests": 0,
            "fixed_transform_seed": FIXED_TRANSFORM_SEED,
            "maximum_generations_per_request": 1,
            "maximum_total_generations": 4,
            "deterministic_rank_zero_extraction": True,
        },
        "frozen_predictions": contrast,
        "decision_law": {
            "intersection_refinement_like_supported": (
                "rank zero matches the unique-intersection commitment in all four requests; "
                "AB and BA select the same semantic candidate within each geometry; G0 and G1 both pass"
            ),
            "bounded_classification": (
                "COMMUTATIVE_UNIQUE_INTERSECTION_LIKE_TRANSFORM_SUPPORTED_ON_TWO_MATCHED_GEOMETRIES"
            ),
            "parent_order_sensitive_supported": (
                "AB and BA differ systematically in both geometries without following a frozen surface rule"
            ),
            "surface_heuristic_supported": (
                "one preregistered lexical-first or first-listed prediction matches all four requests"
            ),
            "parent_role_priority_supported": (
                "one preregistered Parent-A or Parent-B priority prediction matches all four requests"
            ),
            "context_stabilization_only": (
                "rank zero remains order-stable and inside the supplied parent union but no frozen semantic or surface operation transfers"
            ),
            "operation_unidentified": (
                "no preregistered mechanism explains all four outcomes coherently"
            ),
            "formal_algebra_claimed": False,
        },
        "evidence_law": {
            "exact_request_hash_gate_before_contact": True,
            "authenticated_raw_capture_before_parsing": True,
            "duplicate_generation_rejected": True,
            "private_mapping_isolated_from_selection": True,
            "captured_response_replay_without_model_contact": True,
            "clean_cleanup_and_evidence_custody_required": True,
            "retry_after_started_request": False,
        },
        "bindings": {
            "frozen_scientific": scientific_binding,
            "controller": controller_binding,
        },
        "claim_limits": dict(LOCKED_CLAIMS),
        "execution_state": {
            "authority_created": False,
            "authority_consumed": False,
            "sidecar_launched": False,
            "model_requests_issued": 0,
            "model_generations": 0,
            "scientific_result_created": False,
            "live_execution_performed": False,
            "follow_on_architecture_designed": False,
        },
        "future_live_command_shape": (
            "python scripts/catalytic_kernel_0_balanced_rank_head_v2_relational_operation_probe.py "
            "run --repository <repository> --binary <verified-binary> --model <verified-model> "
            f"--design-id {DESIGN_ID} --external-authority-id <fresh-64-hex> "
            "--authorized-commit <published-static-commit>"
        ),
    }
    _assert_public_no_smuggle(document)
    return document


def write_preregistration(repository: Path, model_path: Path) -> Path:
    path = repository.resolve(strict=False) / PREREGISTRATION_PATH
    data = canonical_json_bytes(build_preregistration_document(repository, model_path)) + b"\n"
    if path.exists() or path.is_symlink():
        _require(_require_regular(path, "relational-operation preregistration") == data, "preregistration differs from exact reconstruction")
        return path
    _exclusive_write(path, data)
    return path


def validate_preregistration(repository: Path, model_path: Path) -> dict[str, Any]:
    path = repository.resolve(strict=False) / PREREGISTRATION_PATH
    observed_data = _require_regular(path, "relational-operation preregistration")
    observed = _json_object(path, "relational-operation preregistration")
    expected = build_preregistration_document(repository, model_path)
    _require(observed == expected, "preregistration differs from exact private reconstruction")
    _require(observed_data == canonical_json_bytes(expected) + b"\n", "preregistration is not canonical")
    state = observed["execution_state"]
    _require(
        state == {
            "authority_created": False,
            "authority_consumed": False,
            "sidecar_launched": False,
            "model_requests_issued": 0,
            "model_generations": 0,
            "scientific_result_created": False,
            "live_execution_performed": False,
            "follow_on_architecture_designed": False,
        },
        "static execution boundary changed",
    )
    return {
        "status": "pass",
        "design_id": DESIGN_ID,
        "artifact_sha256": sha256_bytes(observed_data),
        "selected_counter": observed["geometry_selection"]["selected_counter"],
        "request_sha256": dict(observed["request_set"]["request_sha256"]),
        "frozen_scientific_binding_sha256": observed["bindings"]["frozen_scientific"]["sha256"],
        "controller_binding_sha256": observed["bindings"]["controller"]["sha256"],
        "future_model_generations": 4,
        "authority_created": False,
        "authority_consumed": False,
        "model_requests_issued": 0,
        "sidecar_launched": False,
        "live_execution_performed": False,
    }


def authority_id_sha256(raw_authority_id: str) -> str:
    _require(
        isinstance(raw_authority_id, str) and AUTHORITY_ID_RE.fullmatch(raw_authority_id) is not None,
        "external authority ID is malformed",
    )
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
    _require(GIT_COMMIT_RE.fullmatch(authorized_commit) is not None, "authorized commit is malformed")
    _require(current_commit == authorized_commit, "authority commit differs from protected HEAD")
    _require(observed_model_sha256 == MODEL_SHA256, "authority model identity changed")
    _require(observed_binary_sha256 == BINARY_SHA256, "authority binary identity changed")
    prereg = validate_preregistration(repository, model_path)
    return {
        "schema_version": AUTHORITY_SCHEMA_VERSION,
        "authority_kind": AUTHORITY_KIND,
        "design_id": DESIGN_ID,
        "authority_id_sha256": authority_id_sha256(raw_authority_id),
        "authorized_commit": authorized_commit,
        "preregistration_artifact_sha256": prereg["artifact_sha256"],
        "frozen_scientific_binding_sha256": prereg[
            "frozen_scientific_binding_sha256"
        ],
        "controller_binding_sha256": prereg["controller_binding_sha256"],
        "request_sha256": prereg["request_sha256"],
        "fixed_transform_seed": FIXED_TRANSFORM_SEED,
        "maximum_invocations": 1,
        "maximum_generations_per_request": 1,
        "maximum_total_generations": 4,
        "model_sha256": MODEL_SHA256,
        "binary_sha256": BINARY_SHA256,
        "carrier_root_sha256": CARRIER_ROOT_SHA256,
        "retry_allowed": False,
        "automatic_follow_on": False,
        "automatic_promotion": False,
    }


def _authority_hmac(root: bytes, authority: Mapping[str, Any]) -> str:
    return hmac.new(
        _experiment_key(root),
        AUTHORITY_HMAC_DOMAIN + canonical_json_bytes(authority),
        hashlib.sha256,
    ).hexdigest().upper()


def consume_authority_once(
    repository: Path,
    root: bytes,
    authority: Mapping[str, Any],
) -> dict[str, Any]:
    path = repository.resolve(strict=False) / AUTHORITY_RECEIPT_PATH
    _require(not path.exists() and not path.is_symlink(), "relational-operation authority is already consumed")
    body = {
        "schema_version": AUTHORITY_RECEIPT_SCHEMA_VERSION,
        "authority": dict(authority),
        "consumed_at_utc": _utc_now(),
        "consuming_commit": str(authority["authorized_commit"]),
        "raw_authority_id_persisted": False,
    }
    receipt = {**body, "receipt_hmac_sha256": _authority_hmac(root, body["authority"])}
    _exclusive_write(path, canonical_json_bytes(receipt) + b"\n")
    return receipt


def verify_authority_receipt(repository: Path, root: bytes) -> dict[str, Any]:
    receipt = _json_object(
        repository.resolve(strict=False) / AUTHORITY_RECEIPT_PATH,
        "relational-operation authority receipt",
    )
    authority = receipt.get("authority")
    _require(isinstance(authority, dict), "authority receipt body changed")
    _require(
        receipt.get("schema_version") == AUTHORITY_RECEIPT_SCHEMA_VERSION
        and receipt.get("raw_authority_id_persisted") is False
        and receipt.get("receipt_hmac_sha256") == _authority_hmac(root, authority),
        "authority receipt verification failed",
    )
    return receipt


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
        "receipt": repository.resolve(strict=False) / AUTHORITY_RECEIPT_PATH,
    }
    for request_id in REQUEST_IDS:
        paths[f"capture-{request_id}"] = captures / f"{request_id}.json"
        paths[f"partial-{request_id}"] = captures / f"{request_id}.raw.partial"
    return paths


def _runtime_allowed_paths(paths: Mapping[str, Path]) -> tuple[Path, ...]:
    return tuple(
        path for name, path in paths.items() if name not in {"run_root", "receipt"}
    )


class JournalWriter:
    """Minimal authenticated append-only journal for one non-resumable invocation."""

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
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "design_id": DESIGN_ID,
            "event_index": len(self.events) + 1,
            "timestamp_utc": _utc_now(),
            "state": state,
            "request_id": request_id,
            "facts": dict(facts or {}),
            "previous_event_sha256": (
                self.events[-1]["event_sha256"] if self.events else GENESIS_HASH
            ),
        }
        event_without_hmac = {**body, "event_sha256": json_sha256(body)}
        event = {
            **event_without_hmac,
            "event_hmac_sha256": hmac.new(
                self.key,
                JOURNAL_HMAC_DOMAIN + canonical_json_bytes(event_without_hmac),
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
    for index, line in enumerate(_require_regular(path, "probe journal").splitlines(), start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RelationalOperationProbeError("probe journal is malformed") from exc
        _require(isinstance(event, dict), "probe journal event is malformed")
        event_hmac = event.pop("event_hmac_sha256", None)
        event_sha = event.get("event_sha256")
        body = {key_name: value for key_name, value in event.items() if key_name != "event_sha256"}
        _require(
            event.get("event_index") == index
            and event.get("previous_event_sha256") == previous
            and event_sha == json_sha256(body),
            "probe journal hash chain changed",
        )
        expected_hmac = hmac.new(
            key,
            JOURNAL_HMAC_DOMAIN + canonical_json_bytes(event),
            hashlib.sha256,
        ).hexdigest().upper()
        _require(event_hmac == expected_hmac, "probe journal authentication changed")
        event["event_hmac_sha256"] = event_hmac
        events.append(event)
        previous = str(event_sha)
    return events


def assert_can_start(started: Sequence[str], request_id: str) -> None:
    _require(request_id in REQUEST_IDS, "generation request identity changed")
    _require(len(started) < 4, "four-generation ceiling reached")
    _require(request_id not in started, "duplicate generation rejected")
    _require(request_id == EXECUTION_ORDER[len(started)], "generation order changed")


def _runtime_for_request(
    repository: Path,
    private: balanced.PrivateBinding,
    request_id: str,
) -> Any:
    runtime_private = replace(
        private,
        run_keys={request_id: private.run_key(request_id)},
    )
    spec = transaction.integration.V2RunSpec(
        run_id=request_id,
        ordinal=EXECUTION_ORDER.index(request_id) + 1,
        source_binding="within-binding-relational-operation-probe",
        source_profile_id=DESIGN_ID,
        source_full_run_id=request_id,
        authorization_state="external-one-shot-relational-operation-probe-authority-required",
    )
    return transaction.integration.RankHeadV2Runtime(
        repository=repository,
        spec=spec,
        private=runtime_private,
        run_design={"design_id": DESIGN_ID},
    )


def _rendered_tokens(events: Sequence[Mapping[str, Any]], request_id: str) -> int:
    matches = [
        event
        for event in events
        if event.get("state") == "request-started" and event.get("request_id") == request_id
    ]
    _require(len(matches) == 1, "request-start journal event multiplicity changed")
    value = matches[0].get("facts", {}).get("rendered_prompt_tokens")
    _require(isinstance(value, int) and value > 0, "rendered token evidence changed")
    return value


def capture_outcome(
    repository: Path,
    root: bytes,
    private: balanced.PrivateBinding,
    geometries: Mapping[str, Mapping[str, Any]],
    request_id: str,
    capture: Mapping[str, Any],
    rendered_tokens: int,
) -> tuple[dict[str, Any], str]:
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
    except (
        runtime_support.CatalyticInferenceRuntimeError,
        balanced.BalancedOpaqueError,
        transaction.integration.RankHeadV2IntegrationError,
        v2.RankHeadDesignError,
    ) as exc:
        raise RelationalOperationProbeError("captured transform is scientifically invalid") from exc
    geometry_id, order = _request_parts(request_id)
    selected = frozen.candidate_alias
    predictions = _private_predictions(geometries[geometry_id], request_id)
    parent_union = set(geometries[geometry_id]["parent-a"]) | set(
        geometries[geometry_id]["parent-b"]
    )
    selected_commitment = _candidate_commitment(root, geometry_id, selected)
    outcome = {
        "request_id": request_id,
        "geometry_id": geometry_id,
        "presentation_order": order,
        "transform_operator": transform["operator"],
        "transform_artifact_commitment": transform["artifact_commitment"],
        "transform_ranking_length": len(transform["ranking"]),
        "selected_rank": 0,
        "selection_frozen_before_private_mapping": True,
        "private_mapping_consulted_before_selection": False,
        "selected_candidate_commitment": selected_commitment,
        "selected_from_parent_union": selected in parent_union,
        "mechanism_matches": {
            mechanism: selected == prediction
            for mechanism, prediction in predictions.items()
        },
    }
    _assert_public_no_smuggle(outcome)
    return outcome, selected


def adjudicate_outcomes(
    outcomes: Mapping[str, Mapping[str, Any]],
    private_selections: Mapping[str, str],
) -> dict[str, Any]:
    _require(set(outcomes) == set(REQUEST_IDS), "adjudication requires all four outcomes")
    _require(set(private_selections) == set(REQUEST_IDS), "private selection set changed")
    all_match = {
        mechanism: all(
            outcomes[request_id]["mechanism_matches"][mechanism]
            for request_id in REQUEST_IDS
        )
        for mechanism in MECHANISMS
    }
    order_invariance = {
        geometry_id: private_selections[f"{geometry_id}-AB"]
        == private_selections[f"{geometry_id}-BA"]
        for geometry_id in GEOMETRY_IDS
    }
    if all_match["unique-intersection"] and all(order_invariance.values()):
        classification = (
            "COMMUTATIVE_UNIQUE_INTERSECTION_LIKE_TRANSFORM_SUPPORTED_ON_TWO_MATCHED_GEOMETRIES"
        )
    elif all_match["lexical-first"] or all_match["first-listed"]:
        classification = "PREREGISTERED_SURFACE_HEURISTIC_SUPPORTED"
    elif all_match["parent-a-priority"] or all_match["parent-b-priority"]:
        classification = "PARENT_ROLE_PRIORITY_OPERATION_SUPPORTED"
    elif not any(order_invariance.values()):
        classification = "PARENT_ORDER_SENSITIVE_OPERATION_SUPPORTED"
    elif (
        all(order_invariance.values())
        and all(outcomes[request_id]["selected_from_parent_union"] for request_id in REQUEST_IDS)
    ):
        classification = "CONTEXT_STABILIZATION_ONLY"
    else:
        classification = "OPERATION_UNIDENTIFIED"
    result = {
        "classification": classification,
        "mechanism_matches_all_four": all_match,
        "semantic_selection_order_invariant_by_geometry": order_invariance,
        "transferred_across_two_matched_geometries": (
            classification
            == "COMMUTATIVE_UNIQUE_INTERSECTION_LIKE_TRANSFORM_SUPPORTED_ON_TWO_MATCHED_GEOMETRIES"
        ),
        "formal_algebra_claimed": False,
        "scope": "two-matched-geometries-one-private-binding-one-fixed-seed-transform-only",
    }
    _assert_public_no_smuggle(result)
    return result


def _manifest(
    prereg: Mapping[str, Any],
    authority: Mapping[str, Any],
    public_preflight: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "authority": dict(authority),
        "preregistration_artifact_sha256": prereg["artifact_sha256"],
        "request_sha256": prereg["request_sha256"],
        "execution_order": list(EXECUTION_ORDER),
        "fixed_transform_seed": FIXED_TRANSFORM_SEED,
        "preflight": dict(public_preflight),
        "claiming": False,
    }


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
        data = _require_regular(path, f"archive source {name}")
        entries.append({"path": name, "byte_size": len(data), "sha256": sha256_bytes(data)})
    body = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "files": entries,
        "content_addressed": True,
    }
    bundle_sha = json_sha256(body)
    destination = repository / ARCHIVE_ROOT / DESIGN_ID / bundle_sha
    _require(not destination.exists() and not destination.is_symlink(), "archive destination already exists")
    destination.mkdir(parents=True)
    for name, source in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        _exclusive_write(target, _require_regular(source, f"archive source {name}"))
    _exclusive_write(
        destination / "bundle.json",
        canonical_json_bytes({**body, "bundle_sha256": bundle_sha}) + b"\n",
    )
    return {
        "bundle_sha256": bundle_sha,
        "file_count": len(entries),
        "relative_path": destination.relative_to(repository).as_posix(),
        "verified": True,
    }


def run_probe(
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
    _require(isinstance(raw_authority_id, str), "live probe requires external authority")
    _require(isinstance(authorized_commit, str), "live probe requires an authorized commit")
    model_path = Path(str(getattr(args, "model"))).resolve()
    prereg = validate_preregistration(repository, model_path)
    root, private = _load_private(repository)
    tokenizer = asymmetry.OfflineTokenizer(model_path)
    selection = select_first_eligible(root, tokenizer)
    geometries = selection["geometries"]
    paths = state_paths(repository)
    _require(not paths["receipt"].exists() and not paths["receipt"].is_symlink(), "authority already consumed")
    _require(not paths["run_root"].exists() and not paths["run_root"].is_symlink(), "probe runtime state already exists")
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
    manifest = _manifest(prereg, authority, public_preflight)
    manifest_data = canonical_json_bytes(manifest) + b"\n"
    paths["run_root"].mkdir(parents=True)
    _exclusive_write(paths["manifest"], manifest_data)
    consume_authority_once(repository, root, authority)
    verify_authority_receipt(repository, root)
    journal = JournalWriter(paths["journal"], _experiment_key(root))
    journal.append(
        "authority-consumed",
        facts={
            "authority_receipt_sha256": sha256_bytes(
                _require_regular(paths["receipt"], "authority receipt")
            ),
            "authorized_commit": authorized_commit,
        },
    )
    started: list[str] = []
    captures: dict[str, dict[str, Any]] = {}
    failure: dict[str, Any] | None = None
    cleanup: dict[str, Any] = {"passed": False}
    postflight: dict[str, Any] = {"passed": False}
    sidecar: Any | None = None
    with transaction.run_lock(paths["run_lock"]):
        pool = live.create_lease_pool(1)
        try:
            sidecar, _readiness = live.launch_sidecar(
                preflight=full_preflight,
                run_id=DESIGN_ID,
            )
            for request_id in EXECUTION_ORDER:
                assert_can_start(started, request_id)
                payload = build_request(root, geometries, request_id)
                started.append(request_id)
                try:
                    captures[request_id] = scientific.execute_and_capture_request(
                        experiment_key=_experiment_key(root),
                        frozen_binding_sha256=authority[
                            "frozen_scientific_binding_sha256"
                        ],
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
                except BaseException as exc:
                    failure = {
                        "request_id": request_id,
                        "failure_sha256": sha256_bytes(str(exc).encode("utf-8")),
                        "retry_allowed": False,
                    }
                    journal.append("request-failed", request_id=request_id, facts=failure)
                    break
        except BaseException as exc:
            if failure is None:
                failure = _lifecycle_failure(exc)
                journal.append("lifecycle-failed", facts=failure)
        finally:
            try:
                cleanup = dict(live.cleanup(sidecar=sidecar, preflight=full_preflight))
            except BaseException as exc:
                cleanup = {"passed": False, "failure_sha256": sha256_bytes(str(exc).encode("utf-8"))}
            try:
                postflight = dict(live.postflight(preflight=full_preflight))
            except BaseException as exc:
                postflight = {"passed": False, "failure_sha256": sha256_bytes(str(exc).encode("utf-8"))}
    journal.append("finalization-observed", facts={"cleanup": cleanup, "postflight": postflight})
    outcomes: dict[str, dict[str, Any]] = {}
    private_selections: dict[str, str] = {}
    if failure is None and set(captures) == set(REQUEST_IDS):
        for request_id in REQUEST_IDS:
            try:
                outcome, selected = capture_outcome(
                    repository,
                    root,
                    private,
                    geometries,
                    request_id,
                    captures[request_id],
                    _rendered_tokens(journal.events, request_id),
                )
                outcomes[request_id] = outcome
                private_selections[request_id] = selected
                journal.append("adjudicated", request_id=request_id, facts=outcome)
            except RelationalOperationProbeError as exc:
                failure = {
                    "request_id": request_id,
                    "failure_sha256": sha256_bytes(str(exc).encode("utf-8")),
                    "retry_allowed": False,
                }
                journal.append("adjudication-failed", request_id=request_id, facts=failure)
                break
    adjudication = (
        adjudicate_outcomes(outcomes, private_selections)
        if set(outcomes) == set(REQUEST_IDS)
        else {
            "classification": "INCONCLUSIVE",
            "formal_algebra_claimed": False,
            "scope": "four-request-transform-only-probe",
        }
    )
    status = (
        "complete"
        if set(outcomes) == set(REQUEST_IDS)
        and cleanup.get("passed") is True
        and postflight.get("passed") is True
        else "inconclusive"
    )
    started_requests = {
        str(event["request_id"])
        for event in journal.events
        if event.get("state") == "request-started"
    }
    result = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "status": status,
        "completed_model_generations": len(started_requests),
        "maximum_model_generations": 4,
        "request_dispositions": [
            outcomes.get(
                request_id,
                {
                    "request_id": request_id,
                    "disposition": (
                        "captured-unadjudicated"
                        if request_id in captures
                        else "started-no-capture"
                        if request_id in started_requests
                        else "not-started"
                    ),
                },
            )
            for request_id in REQUEST_IDS
        ],
        "adjudication": adjudication,
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
        "authority_receipt_sha256": sha256_bytes(
            _require_regular(paths["receipt"], "authority receipt")
        ),
        "journal_head_before_terminal": journal.events[-1]["event_sha256"],
        "run_lock_absent_at_terminal_publication": not paths["run_lock"].exists(),
        "retry_allowed": False,
        "claiming": False,
    }
    _assert_public_no_smuggle(closure)
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
    verify_journal(paths["journal"], _experiment_key(root))
    archive = _archive_terminal(repository, paths)
    journal.append(
        "archived",
        facts={"archive_sha256": archive["bundle_sha256"], "claiming": False},
    )
    verify_journal(paths["journal"], _experiment_key(root))
    return {**result, "evidence_archive_sha256": archive["bundle_sha256"]}


def validate_static(repository: Path, model_path: Path) -> dict[str, Any]:
    prereg = validate_preregistration(repository, model_path)
    root, _private = _load_private(repository)
    paths = state_paths(repository)
    _require(not paths["receipt"].exists() and not paths["receipt"].is_symlink(), "live authority already exists")
    _require(not paths["run_root"].exists() and not paths["run_root"].is_symlink(), "live probe state already exists")
    return {
        "status": "pass",
        "design_id": DESIGN_ID,
        "preregistration": prereg,
        "experiment_key_commitment_sha256": sha256_bytes(_experiment_key(root)),
        "request_count": 4,
        "future_model_generations": 4,
        "authority_created": False,
        "authority_consumed": False,
        "model_requests_issued": 0,
        "sidecar_launched": False,
        "live_execution_performed": False,
        "scientific_result_created": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="operation", required=True)
    for name in ("generate", "validate"):
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
        if args.operation == "generate":
            path = write_preregistration(repository, model_path)
            result = {
                "status": "written",
                "path": path.relative_to(repository).as_posix(),
                "artifact_sha256": sha256_bytes(path.read_bytes()),
                "future_model_generations": 4,
                "authority_created": False,
                "model_requests_issued": 0,
            }
        elif args.operation == "validate":
            result = validate_static(repository, model_path)
        else:
            result = run_probe(args, repository_root=repository)
    except (
        OSError,
        subprocess.SubprocessError,
        RelationalOperationProbeError,
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
