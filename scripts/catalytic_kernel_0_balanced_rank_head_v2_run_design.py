#!/usr/bin/env python3
"""Authoritative static run design for deterministic rank-head CK0 v2.

This wrapper binds the existing private-root custodians, exact state namespace,
ordered two-run gate, and terminal-visible predecessor requirement. It does not
implement authority consumption or launch a live process.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2 as v2
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration

RUN_DESIGN_PATH = integration.RUN_DESIGN_PATH
STATE_ROOT = "state/catalytic_kernel_0_rank_head_v2"
STATE_FILENAMES = ("manifest.json", "result.json", "closure.json", "run.lock")
REQUIRED_IMPLEMENTATION_PATHS = (
    *v2.REQUIRED_IMPLEMENTATION_PATHS,
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_integration.py",
    "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_integration.py",
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_run_design.py",
    "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_run_design.py",
)
REQUIRED_AUDITS = integration.REQUIRED_AUDITS


class RankHeadV2RunDesignError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return integration.sha256_bytes(data)


def json_sha256(value: Any) -> str:
    return integration.json_sha256(value)


def require_exact_implementation_paths(paths: Sequence[str]) -> None:
    if any(not isinstance(path, str) for path in paths) or tuple(sorted(paths)) != tuple(sorted(REQUIRED_IMPLEMENTATION_PATHS)) or len(set(paths)) != len(paths):
        raise RankHeadV2RunDesignError("v2 run design binding must contain exactly eight files")


def source_binding_custody(repository: Path, spec: integration.V2RunSpec) -> dict[str, Any]:
    configuration = integration.source_configuration(spec)
    private = balanced._private_binding_from_repository(repository, configuration)
    preregistration_path = repository / configuration.preregistration_path
    if not preregistration_path.is_file() or preregistration_path.is_symlink():
        raise RankHeadV2RunDesignError("source preregistration is missing or unsafe")
    try:
        preregistration = json.loads(preregistration_path.read_bytes())
    except json.JSONDecodeError as exc:
        raise RankHeadV2RunDesignError("source preregistration is invalid JSON") from exc
    creation = private.creation_receipt_commitment
    if not isinstance(creation, str) or not balanced.SHA256_RE.fullmatch(creation):
        raise RankHeadV2RunDesignError("source creation receipt commitment is missing")
    return {
        "source_binding": spec.source_binding,
        "source_profile_id": configuration.profile_id,
        "source_preregistration_path": configuration.preregistration_path,
        "source_preregistration_artifact_sha256": sha256_bytes(preregistration_path.read_bytes()),
        "source_preregistration_document_sha256": json_sha256(preregistration),
        "source_secret_commitment": private.secret_commitment,
        "source_alias_map_commitment": private.alias_map_commitment,
        "source_branch_alias_map_commitments": dict(private.branch_alias_map_commitments),
        "source_creation_receipt_commitment": creation,
        "source_private_root_modified": False,
        "source_alias_mapping_modified": False,
    }


def predecessor_paths(repository: Path) -> dict[str, Path]:
    root = repository / STATE_ROOT / integration.BINDING_1_RUN_ID
    return {name: root / name for name in STATE_FILENAMES}


def require_binding_1_v2_terminal_visible(repository: Path) -> dict[str, Any]:
    paths = predecessor_paths(repository)
    for name in ("manifest.json", "result.json", "closure.json"):
        path = paths[name]
        if not path.is_file() or path.is_symlink():
            raise RankHeadV2RunDesignError("binding-1 v2 predecessor evidence is absent")
    if paths["run.lock"].exists() or paths["run.lock"].is_symlink():
        raise RankHeadV2RunDesignError("binding-1 v2 predecessor still has a run lock")
    try:
        manifest = json.loads(paths["manifest.json"].read_bytes())
        result = json.loads(paths["result.json"].read_bytes())
        closure = json.loads(paths["closure.json"].read_bytes())
    except json.JSONDecodeError as exc:
        raise RankHeadV2RunDesignError("binding-1 v2 predecessor JSON is invalid") from exc
    if (
        manifest.get("run_id") != integration.BINDING_1_RUN_ID
        or result.get("run_id") != integration.BINDING_1_RUN_ID
        or result.get("status") != "complete"
        or result.get("terminal_classification") != integration.VISIBLE_CLASSIFICATION
        or closure.get("run_id") != integration.BINDING_1_RUN_ID
        or closure.get("run_lock_absent") is not True
        or closure.get("manifest_sha256") != sha256_bytes(paths["manifest.json"].read_bytes())
        or closure.get("result_sha256") != sha256_bytes(paths["result.json"].read_bytes())
    ):
        raise RankHeadV2RunDesignError("binding-1 v2 predecessor is not terminal visible evidence")
    return {
        "run_id": integration.BINDING_1_RUN_ID,
        "manifest_sha256": sha256_bytes(paths["manifest.json"].read_bytes()),
        "result_sha256": sha256_bytes(paths["result.json"].read_bytes()),
        "closure_sha256": sha256_bytes(paths["closure.json"].read_bytes()),
        "terminal_classification": integration.VISIBLE_CLASSIFICATION,
        "run_lock_absent": True,
    }


class QualifiedRankHeadV2Runtime(integration.RankHeadV2Runtime):
    @classmethod
    def from_repository(cls, repository: Path, run_id: str, *, require_final_design: bool = True) -> "QualifiedRankHeadV2Runtime":
        design = validate_run_design(repository, require_final=require_final_design)
        spec = integration.run_spec(run_id)
        if spec.predecessor_run_id is not None:
            require_binding_1_v2_terminal_visible(repository)
        return cls(
            repository=repository,
            spec=spec,
            private=integration.runtime_private_from_repository(repository, run_id),
            run_design=design,
        )


def build_run_design(repository: Path, *, implementation_paths: Sequence[str], audits: Mapping[str, str], static_verification: Mapping[str, Any]) -> dict[str, Any]:
    require_exact_implementation_paths(implementation_paths)
    if dict(audits) != REQUIRED_AUDITS:
        raise RankHeadV2RunDesignError("v2 run design audits must be exact terminal PASS")
    if static_verification.get("status") != "pass":
        raise RankHeadV2RunDesignError("v2 run design verification must be terminal PASS")
    v2_projection = v2.validate_preregistration(repository)
    runs = []
    for run_id in integration.RUN_ORDER:
        spec = integration.run_spec(run_id)
        private = integration.runtime_private_from_repository(repository, run_id)
        runs.append({
            **spec.body(),
            "state_root": f"{STATE_ROOT}/{run_id}",
            "state_filenames": list(STATE_FILENAMES),
            "source_custody": source_binding_custody(repository, spec),
            "run_key_commitment": balanced.run_key_commitment(private.run_key(run_id), private.configuration),
        })
    document = {
        "schema_version": 1,
        "status": "static-preregistered",
        "integration_id": integration.INTEGRATION_ID,
        "protected_starting_main": integration.STARTING_PROTECTED_MAIN,
        "v2_static_preregistration": v2_projection,
        "v2_carrier": {key: v2.build_v2_carrier()[key] for key in ("carrier_id", "carrier_content_sha256", "carrier_root_sha256")},
        "logical_stages": list(integration.LOGICAL_STAGES),
        "model_request_stages": list(integration.MODEL_REQUEST_STAGES),
        "controller_stage": "extract",
        "runtime_entrypoint": {
            "module": "scripts/catalytic_kernel_0_balanced_rank_head_v2_run_design.py",
            "runtime_class": "QualifiedRankHeadV2Runtime",
            "historical_v1_runner_modified": False,
            "holostate_cli_registered": False,
            "protected_sidecar_adapter_integration": "pending-separate-static-authority-bridge",
        },
        "state_namespace": {
            "root": STATE_ROOT,
            "filenames": list(STATE_FILENAMES),
            "ignored_runtime_required": True,
        },
        "run_order": list(integration.RUN_ORDER),
        "runs": runs,
        "authorization_boundary": {
            "external_one_shot_authority_required_per_run": True,
            "authority_implementation_requires_separate_static_authorization": True,
            "first_separately_authorizable_run": integration.BINDING_1_RUN_ID,
            "binding_2_run_requires_binding_1_terminal_visible": True,
            "predecessor_gate_implemented": True,
            "authority_created": False,
            "live_execution_authorized": False,
            "retry_allowed": False,
            "automatic_follow_on": False,
        },
        "private_state": {
            "new_secret_created": False,
            "source_private_roots": ["binding-1", "binding-2"],
            "source_commitments_bound_per_run": True,
            "source_alias_mappings_preserved": True,
            "v2_run_keys_domain_separated": True,
            "source_private_roots_modified": False,
        },
        "implementation_binding": balanced.implementation_binding(repository, implementation_paths),
        "audits": dict(audits),
        "static_verification": dict(static_verification),
        "claim_boundary": {
            "historical_binding_2_classification": "BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
            "locked": ["v2-live-correctness", "end-to-end-cross-binding-replication", "binding-2-parent-dependence", "causal-replication", "general-two-parent-necessity", "transfer", "general-catalytic-inference", "task-advantage", "superiority", "sota", "broader-holostate", "restart-persistence", "deep", "automatic-promotion"],
        },
    }
    balanced.validate_metadata_only(document)
    return document


def write_run_design(repository: Path, document: Mapping[str, Any]) -> Path:
    path = repository / RUN_DESIGN_PATH
    if path.exists() or path.is_symlink():
        raise RankHeadV2RunDesignError("v2 run design already exists")
    payload = (json.dumps(document, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=".ck0-rank-head-v2-run-design-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        written = os.write(fd, payload)
        if written != len(payload):
            raise RankHeadV2RunDesignError("v2 run design write was incomplete")
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.link(temporary, path, follow_symlinks=False)
    finally:
        if fd >= 0:
            os.close(fd)
        if temporary.exists():
            temporary.unlink()
    return path


def validate_run_design(repository: Path, *, require_final: bool = True) -> dict[str, Any]:
    path = repository / RUN_DESIGN_PATH
    if not path.is_file() or path.is_symlink():
        raise RankHeadV2RunDesignError("v2 run design is missing or unsafe")
    try:
        document = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        raise RankHeadV2RunDesignError("v2 run design is invalid JSON") from exc
    if not isinstance(document, Mapping):
        raise RankHeadV2RunDesignError("v2 run design root is not an object")
    binding = document.get("implementation_binding")
    files = binding.get("files") if isinstance(binding, Mapping) else None
    if not isinstance(files, list) or any(not isinstance(item, Mapping) for item in files):
        raise RankHeadV2RunDesignError("v2 run design binding is malformed")
    paths = [item.get("path") for item in files]
    require_exact_implementation_paths(paths)
    expected = build_run_design(repository, implementation_paths=paths, audits=document.get("audits", {}), static_verification=document.get("static_verification", {}))
    if document != expected:
        raise RankHeadV2RunDesignError("v2 run design differs from exact reconstruction")
    if require_final and (document.get("audits") != REQUIRED_AUDITS or document.get("static_verification", {}).get("status") != "pass"):
        raise RankHeadV2RunDesignError("v2 run design is not terminally qualified")
    return {
        "relative_path": RUN_DESIGN_PATH,
        "artifact_sha256": sha256_bytes(path.read_bytes()),
        "document_sha256": json_sha256(document),
        "implementation_binding_sha256": binding.get("sha256"),
        "run_ids_reserved": list(integration.RUN_ORDER),
        "first_separately_authorizable_run": integration.BINDING_1_RUN_ID,
        "binding_2_predecessor_gate_implemented": True,
        "second_run_authorized": False,
        "live_execution_authorized": False,
        "status": "validated-static-run-design",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("generate", "validate"))
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--implementation-path", action="append", default=[])
    parser.add_argument("--audit", action="append", default=[])
    parser.add_argument("--static-verification-json", type=Path)
    return parser.parse_args()


def parse_audits(values: Sequence[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        name, separator, outcome = value.partition("=")
        if not separator or not name or not outcome:
            raise RankHeadV2RunDesignError("audit values must use NAME=OUTCOME")
        result[name] = outcome
    return result


def main() -> int:
    args = parse_args()
    repository = args.repository.resolve()
    try:
        if args.operation == "generate":
            if not args.static_verification_json:
                raise RankHeadV2RunDesignError("generate requires --static-verification-json")
            verification = json.loads(args.static_verification_json.read_text(encoding="utf-8"))
            document = build_run_design(repository, implementation_paths=args.implementation_path, audits=parse_audits(args.audit), static_verification=verification)
            path = write_run_design(repository, document)
            result = {"status": "written", "path": str(path), "artifact_sha256": sha256_bytes(path.read_bytes()), "document_sha256": json_sha256(document)}
        else:
            result = validate_run_design(repository)
    except (RankHeadV2RunDesignError, integration.RankHeadV2IntegrationError, balanced.BalancedOpaqueError, v2.RankHeadDesignError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
