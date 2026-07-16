#!/usr/bin/env python3
"""Authoritative static v2 carrier and preregistration surface.

The versioned core module owns deterministic rank-head selection and receipt
verification. This wrapper adds the v2 model-visible carrier, removing the
model-authored extraction request while preserving the frozen task geometry and
branch/transform schemas.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import catalytic_kernel_0_balanced_rank_head_v2_core as _core
from catalytic_kernel_0_balanced_rank_head_v2_core import *  # noqa: F401,F403

balanced = _core.balanced
V2_CARRIER_ID = "ck0:balanced-opaque-relational-carrier-v2-rank-head"
REQUIRED_IMPLEMENTATION_PATHS = (
    "scripts/catalytic_kernel_0_balanced_rank_head_v2.py",
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_core.py",
    "scripts/test_catalytic_kernel_0_balanced_rank_head_v2.py",
    "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_core.py",
)


def v2_response_schema(request_id: str) -> dict[str, Any]:
    if request_id not in MODEL_REQUEST_STAGES:
        raise RankHeadDesignError("v2 has no model request for this logical stage")
    schema = json.loads(json.dumps(balanced.response_schema(request_id)))
    if request_id in {"borrow", "restore"}:
        schema["properties"]["carrier_id"]["const"] = V2_CARRIER_ID
    return schema


def v2_response_schema_hashes() -> dict[str, str]:
    return {
        request_id: json_sha256(v2_response_schema(request_id))
        for request_id in MODEL_REQUEST_STAGES
    }


def build_v2_carrier() -> dict[str, Any]:
    suite = balanced.build_frozen_task_suite()
    if suite.suite_sha256 != balanced.EXPECTED_SUITE_SHA256:
        raise RankHeadDesignError("frozen task suite identity changed")
    semantics = dict(
        suite.tasks[balanced.TASK_INDEX].public_projection()["semantics"]
    )
    content = {
        "carrier_id": V2_CARRIER_ID,
        "task_semantics": semantics,
        "candidate_aliases": list(balanced.ALIASES),
        "response_schemas": {
            request_id: v2_response_schema(request_id)
            for request_id in MODEL_REQUEST_STAGES
        },
        "kernel_instructions": {
            "cycle": list(LOGICAL_STAGES),
            "model_request_stages": list(MODEL_REQUEST_STAGES),
            "law": (
                "borrow -> branch-a + branch-b -> transform -> "
                "controller-deterministic-rank-head-extract -> restore"
            ),
            "model_authorship": [
                "diagnostic branch rankings",
                "transform operator and ordered opaque ranking",
                "carrier acknowledgements",
            ],
            "controller_authorship": [
                "rank-head selection from committed transform position zero",
                "private mapping and scoring after selection",
                "deterministic extraction receipt",
                "custody and restoration",
            ],
            "extraction_contract": {
                "model_request_present": False,
                "mode": EXTRACTION_MODE,
                "selection_law": SELECTION_LAW,
                "selected_rank": SELECTED_RANK,
                "receipt_schema_sha256": receipt_schema_sha256(),
            },
        },
    }
    content_sha256 = json_sha256(content)
    root_object = {**content, "carrier_content_sha256": content_sha256}
    root = json.dumps(
        root_object,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    balanced._assert_no_internal_identity(root_object)
    balanced.validate_metadata_only(root_object)
    return {
        "carrier_id": V2_CARRIER_ID,
        "carrier_content_sha256": content_sha256,
        "carrier_root": root,
        "carrier_root_sha256": sha256_bytes(root.encode("utf-8")),
    }


def v2_carrier_is_pristine(carrier: Mapping[str, Any]) -> bool:
    return dict(carrier) == build_v2_carrier()


def build_design_contract(repository: Path) -> dict[str, Any]:
    contract = _core.build_design_contract(repository)
    carrier = build_v2_carrier()
    mechanism = contract["frozen_mechanism"]
    mechanism.update(
        {
            "source_v1_carrier_id": mechanism["carrier_id"],
            "carrier_id": carrier["carrier_id"],
            "carrier_content_sha256": carrier["carrier_content_sha256"],
            "carrier_root_sha256": carrier["carrier_root_sha256"],
            "model_request_schema_sha256": v2_response_schema_hashes(),
            "extract_response_schema_present": False,
        }
    )
    contract["model_visible_carrier"] = {
        "carrier_id": carrier["carrier_id"],
        "carrier_content_sha256": carrier["carrier_content_sha256"],
        "carrier_root_sha256": carrier["carrier_root_sha256"],
        "response_schema_sha256": v2_response_schema_hashes(),
        "model_request_stages": list(MODEL_REQUEST_STAGES),
        "logical_stages": list(LOGICAL_STAGES),
        "extract_model_request_present": False,
    }
    balanced.validate_metadata_only(contract)
    return contract


def _require_exact_implementation_paths(implementation_paths: Sequence[str]) -> None:
    observed = tuple(sorted(implementation_paths))
    expected = tuple(sorted(REQUIRED_IMPLEMENTATION_PATHS))
    if observed != expected or len(set(implementation_paths)) != len(implementation_paths):
        raise RankHeadDesignError(
            "v2 implementation binding must contain exactly the four authorized files"
        )


def build_preregistration_document(
    *,
    repository: Path,
    implementation_paths: Sequence[str],
    audit_outcomes: Mapping[str, str] | None = None,
    static_verification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    _require_exact_implementation_paths(implementation_paths)
    document = {
        "schema_version": DESIGN_SCHEMA_VERSION,
        "status": "static-preregistered",
        "design_contract": build_design_contract(repository),
        "implementation_binding": implementation_binding(
            repository, implementation_paths
        ),
        "audits": dict(audit_outcomes or {}),
        "static_verification": dict(
            static_verification or {"status": "pending"}
        ),
        "execution_state": {
            "run_ids_reserved": [],
            "live_authority_created": False,
            "live_execution_performed": False,
            "model_requests_issued": 0,
            "sidecar_launched": False,
            "new_private_secret_created": False,
        },
    }
    balanced.validate_metadata_only(document)
    return document


def validate_preregistration(
    repository: Path,
    *,
    require_final: bool = True,
) -> dict[str, Any]:
    path = _core._required_file(repository, PREREGISTRATION_PATH)
    try:
        document = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        raise RankHeadDesignError("v2 preregistration is invalid JSON") from exc
    if not isinstance(document, dict):
        raise RankHeadDesignError("v2 preregistration root is not an object")
    source_binding = document.get("implementation_binding", {})
    paths = [
        item.get("path")
        for item in source_binding.get("files", [])
        if isinstance(item, Mapping)
    ]
    if not paths:
        raise RankHeadDesignError("v2 implementation binding is empty")
    expected = build_preregistration_document(
        repository=repository,
        implementation_paths=paths,
        audit_outcomes=document.get("audits", {}),
        static_verification=document.get("static_verification", {}),
    )
    if document != expected:
        raise RankHeadDesignError(
            "v2 preregistration differs from exact static reconstruction"
        )
    if document.get("execution_state") != {
        "run_ids_reserved": [],
        "live_authority_created": False,
        "live_execution_performed": False,
        "model_requests_issued": 0,
        "sidecar_launched": False,
        "new_private_secret_created": False,
    }:
        raise RankHeadDesignError("v2 static execution boundary changed")
    if require_final:
        required_audits = {
            "rank_head_no_smuggle_auditor": "PASS",
            "historical_compatibility_auditor": "PASS",
        }
        if document.get("audits") != required_audits:
            raise RankHeadDesignError("v2 read-only audits are not terminal PASS")
        if document.get("static_verification", {}).get("status") != "pass":
            raise RankHeadDesignError("v2 static verification is not terminal PASS")
    projection = {
        "relative_path": PREREGISTRATION_PATH,
        "artifact_sha256": sha256_bytes(path.read_bytes()),
        "document_sha256": json_sha256(document),
        "implementation_binding_sha256": source_binding.get("sha256"),
        "design_contract_sha256": json_sha256(document["design_contract"]),
        "carrier_root_sha256": document["design_contract"][
            "model_visible_carrier"
        ]["carrier_root_sha256"],
        "receipt_schema_sha256": receipt_schema_sha256(),
        "run_ids_reserved": [],
        "live_execution_authorized": False,
        "status": "validated-static-preregistered",
    }
    balanced.validate_metadata_only(projection)
    return projection


def main() -> int:
    args = _core.parse_args()
    repository = args.repository.resolve()
    try:
        if args.operation == "design":
            result = build_design_contract(repository)
        elif args.operation == "generate":
            if not args.implementation_path:
                raise RankHeadDesignError(
                    "generate requires at least one --implementation-path"
                )
            static_verification = {"status": "pending"}
            if args.static_verification_json:
                static_verification = json.loads(
                    args.static_verification_json.read_text(encoding="utf-8")
                )
            document = build_preregistration_document(
                repository=repository,
                implementation_paths=args.implementation_path,
                audit_outcomes=_core._parse_audits(args.audit),
                static_verification=static_verification,
            )
            path = write_preregistration(repository, document)
            result = {
                "status": "written",
                "path": str(path),
                "artifact_sha256": sha256_bytes(path.read_bytes()),
                "document_sha256": json_sha256(document),
            }
        else:
            result = validate_preregistration(
                repository,
                require_final=not args.allow_pending,
            )
    except (
        RankHeadDesignError,
        balanced.BalancedOpaqueError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
