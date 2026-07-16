#!/usr/bin/env python3
"""Authoritative static run design for deterministic-rank-head CK0 v2.

This wrapper binds existing private-root custodians, the versioned protected
lifecycle, exact state and authority namespaces, ordered two-run reservations,
and the terminal-visible predecessor gate. It grants no live authority.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2 as v2
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration

RUN_DESIGN_PATH = integration.RUN_DESIGN_PATH
STATE_ROOT = "state/catalytic_kernel_0_rank_head_v2"
STATE_FILENAMES = ("manifest.json", "result.json", "closure.json", "run.lock")
AUTHORITY_RECEIPT_TEMPLATE = (
    "state/catalytic_kernel_0_rank_head_v2_authority."
    "<run-id>.authority.consumed.json"
)
REQUIRED_IMPLEMENTATION_PATHS = (
    *v2.REQUIRED_IMPLEMENTATION_PATHS,
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_integration.py",
    "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_integration.py",
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_run_design.py",
    "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_run_design.py",
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_authority.py",
    "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_authority.py",
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_live.py",
    "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_live.py",
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_entrypoint.py",
    "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_entrypoint.py",
)
REQUIRED_AUDITS = integration.REQUIRED_AUDITS


class RankHeadV2RunDesignError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return v2.sha256_bytes(data)


def json_sha256(value: Any) -> str:
    return v2.json_sha256(value)


def require_exact_implementation_paths(paths: Sequence[str]) -> None:
    if (
        any(not isinstance(path, str) for path in paths)
        or tuple(sorted(paths)) != tuple(sorted(REQUIRED_IMPLEMENTATION_PATHS))
        or len(set(paths)) != len(paths)
    ):
        raise RankHeadV2RunDesignError(
            "v2 run design binding must contain exactly fourteen files"
        )


def source_binding_custody(
    repository: Path,
    spec: integration.V2RunSpec,
) -> dict[str, Any]:
    configuration = integration.source_configuration(spec)
    private = balanced._private_binding_from_repository(repository, configuration)
    preregistration_path = repository / configuration.preregistration_path
    if not preregistration_path.is_file() or preregistration_path.is_symlink():
        raise RankHeadV2RunDesignError(
            "source preregistration is missing or unsafe"
        )
    try:
        preregistration = json.loads(preregistration_path.read_bytes())
    except json.JSONDecodeError as exc:
        raise RankHeadV2RunDesignError(
            "source preregistration is invalid JSON"
        ) from exc
    creation = private.creation_receipt_commitment
    if not isinstance(creation, str) or not balanced.SHA256_RE.fullmatch(creation):
        raise RankHeadV2RunDesignError(
            "source creation receipt commitment is missing"
        )
    return {
        "source_binding": spec.source_binding,
        "source_profile_id": configuration.profile_id,
        "source_preregistration_path": configuration.preregistration_path,
        "source_preregistration_artifact_sha256": sha256_bytes(
            preregistration_path.read_bytes()
        ),
        "source_preregistration_document_sha256": json_sha256(preregistration),
        "source_secret_commitment": private.secret_commitment,
        "source_alias_map_commitment": private.alias_map_commitment,
        "source_branch_alias_map_commitments": dict(
            private.branch_alias_map_commitments
        ),
        "source_creation_receipt_commitment": creation,
        "source_private_root_modified": False,
        "source_alias_mapping_modified": False,
    }


def predecessor_paths(repository: Path) -> dict[str, Path]:
    root = repository / STATE_ROOT / integration.BINDING_1_RUN_ID
    return {name: root / name for name in STATE_FILENAMES}


def _require_published_visible_record(
    repository: Path,
    *,
    manifest_sha256: str,
    result_sha256: str,
    closure_sha256: str,
) -> dict[str, Any]:
    ledger = repository / "lab" / "results.jsonl"
    if not ledger.is_file() or ledger.is_symlink():
        raise RankHeadV2RunDesignError("binding-1 v2 publication ledger is absent")
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", "lab/results.jsonl"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if tracked.returncode != 0:
        raise RankHeadV2RunDesignError(
            "binding-1 v2 publication record is not tracked"
        )
    matches: list[dict[str, Any]] = []
    for line_number, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RankHeadV2RunDesignError("binding-1 v2 publication ledger is invalid") from exc
        if not isinstance(record, Mapping):
            continue
        configuration = record.get("configuration")
        metrics = record.get("metrics_after")
        if not (
            isinstance(configuration, Mapping)
            and isinstance(metrics, Mapping)
        ):
            if (
                record.get("run_id") == integration.BINDING_1_RUN_ID
                and record.get("terminal_classification")
                == integration.VISIBLE_CLASSIFICATION
            ):
                raise RankHeadV2RunDesignError(
                    "binding-1 v2 publication requires a split experiment record"
                )
            continue
        run_id = configuration.get("run_id")
        classification = metrics.get("terminal_classification")
        facts = metrics
        if (
            run_id == integration.BINDING_1_RUN_ID
            and classification == integration.VISIBLE_CLASSIFICATION
        ):
            if (
                facts.get("manifest_sha256") != manifest_sha256
                or facts.get("result_sha256") != result_sha256
                or facts.get("closure_sha256") != closure_sha256
            ):
                raise RankHeadV2RunDesignError(
                    "binding-1 v2 publication hashes do not bind raw evidence"
                )
            matches.append(
                {"line": line_number, "layout": "split-experiment-record"}
            )
    if len(matches) != 1:
        raise RankHeadV2RunDesignError(
            "binding-1 v2 requires exactly one published visible record"
        )
    return matches[0]


def require_binding_1_v2_terminal_visible(repository: Path) -> dict[str, Any]:
    paths = predecessor_paths(repository)
    for name in ("manifest.json", "result.json", "closure.json"):
        path = paths[name]
        if not path.is_file() or path.is_symlink():
            raise RankHeadV2RunDesignError(
                "binding-1 v2 predecessor evidence is absent"
            )
    if paths["run.lock"].exists() or paths["run.lock"].is_symlink():
        raise RankHeadV2RunDesignError(
            "binding-1 v2 predecessor still has a run lock"
        )
    try:
        manifest = json.loads(paths["manifest.json"].read_bytes())
        result = json.loads(paths["result.json"].read_bytes())
        closure = json.loads(paths["closure.json"].read_bytes())
    except json.JSONDecodeError as exc:
        raise RankHeadV2RunDesignError(
            "binding-1 v2 predecessor JSON is invalid"
        ) from exc
    manifest_sha256 = sha256_bytes(paths["manifest.json"].read_bytes())
    result_sha256 = sha256_bytes(paths["result.json"].read_bytes())
    closure_sha256 = sha256_bytes(paths["closure.json"].read_bytes())
    expected_design = validate_run_design(repository)
    expected_static = v2.validate_preregistration(repository)
    carrier = v2.build_v2_carrier()
    if (
        manifest.get("run_id") != integration.BINDING_1_RUN_ID
        or manifest.get("run_ordinal") != 1
        or manifest.get("source_binding") != "binding-1"
        or manifest.get("run_design") != expected_design
        or manifest.get("static_preregistration") != expected_static
        or manifest.get("carrier")
        != {
            "carrier_id": carrier["carrier_id"],
            "carrier_content_sha256": carrier["carrier_content_sha256"],
            "carrier_root_sha256": carrier["carrier_root_sha256"],
        }
        or result.get("run_id") != integration.BINDING_1_RUN_ID
        or result.get("run_ordinal") != 1
        or result.get("source_binding") != "binding-1"
        or result.get("status") != "complete"
        or result.get("terminal_classification") != integration.VISIBLE_CLASSIFICATION
        or result.get("completed_model_responses") != 5
        or closure.get("run_id") != integration.BINDING_1_RUN_ID
        or closure.get("run_lock_absent") is not True
        or closure.get("terminal_classification") != integration.VISIBLE_CLASSIFICATION
        or closure.get("manifest_sha256") != manifest_sha256
        or closure.get("result_sha256") != result_sha256
        or closure.get("run_design_document_sha256")
        != expected_design["document_sha256"]
        or closure.get("static_preregistration_document_sha256")
        != expected_static["document_sha256"]
    ):
        raise RankHeadV2RunDesignError(
            "binding-1 v2 predecessor is not terminal visible evidence"
        )

    import catalytic_kernel_0_balanced_rank_head_v2_authority as authority

    authority_evidence = authority.verify_authority_receipt_for_run(
        repository,
        integration.BINDING_1_RUN_ID,
    )
    if not (
        manifest.get("external_live_authority")
        == result.get("external_live_authority")
        == closure.get("external_live_authority")
        == authority_evidence
    ):
        raise RankHeadV2RunDesignError(
            "binding-1 v2 authority evidence is not identical"
        )
    authority_body = authority_evidence.get("authority", {})
    preflight = manifest.get("preflight", {})
    if (
        not isinstance(authority_body, Mapping)
        or not isinstance(preflight, Mapping)
        or preflight.get("stable", {}).get("head")
        != authority_body.get("authorized_commit")
        or preflight.get("model_identity", {}).get("sha256")
        != authority_body.get("model_sha256")
        or preflight.get("binary_identity", {}).get("sha256")
        != authority_body.get("binary_sha256")
        or authority_body.get("run_design_artifact_sha256")
        != expected_design["artifact_sha256"]
        or authority_body.get("run_design_document_sha256")
        != expected_design["document_sha256"]
        or authority_body.get("run_design_implementation_binding_sha256")
        != expected_design["implementation_binding_sha256"]
        or authority_body.get("static_preregistration_artifact_sha256")
        != expected_static["artifact_sha256"]
        or authority_body.get("static_preregistration_document_sha256")
        != expected_static["document_sha256"]
        or authority_body.get("static_design_contract_sha256")
        != expected_static["design_contract_sha256"]
        or authority_body.get("carrier_id") != carrier["carrier_id"]
        or authority_body.get("carrier_root_sha256")
        != carrier["carrier_root_sha256"]
    ):
        raise RankHeadV2RunDesignError(
            "binding-1 v2 authority scope does not bind predecessor identities"
        )

    spec = integration.run_spec(integration.BINDING_1_RUN_ID)
    runtime = integration.RankHeadV2Runtime(
        repository=repository,
        spec=spec,
        private=integration.runtime_private_from_repository(repository, spec.run_id),
        run_design=expected_design,
    )
    artifacts = {
        "branch-a": result.get("branch_a"),
        "branch-b": result.get("branch_b"),
        "transform": result.get("transform"),
        "extract": result.get("deterministic_extraction"),
    }
    try:
        runtime.verify_branch_artifact(artifacts["branch-a"])
        runtime.verify_branch_artifact(artifacts["branch-b"])
        runtime.verify_transform_artifact(artifacts["transform"])
        v2.verify_deterministic_extraction_receipt(
            runtime,
            artifacts["extract"],
            artifacts["transform"],
        )
    except (TypeError, balanced.BalancedOpaqueError, v2.RankHeadDesignError) as exc:
        raise RankHeadV2RunDesignError(
            "binding-1 v2 predecessor artifacts do not verify"
        ) from exc
    restoration = result.get("restoration", {})
    cleanup = result.get("cleanup", {})
    postflight = result.get("postflight_custody", {})
    lease = result.get("lease_accounting", {})
    if (
        runtime.classify_v2(
            artifacts,
            completed_model_responses=5,
            restoration_passed=restoration.get("passed") is True,
        )
        != integration.VISIBLE_CLASSIFICATION
        or restoration.get("passed") is not True
        or restoration.get("historical_cib0_preserved") is not True
        or restoration.get("historical_ck0_preserved") is not True
        or cleanup.get("passed") is not True
        or postflight.get("passed") is not True
        or lease.get("lease_count") != 5
        or lease.get("maximum_concurrent_leases") != 1
        or lease.get("active_leases") != 0
        or closure.get("terminal_custody", {}).get("passed") is not True
        or manifest.get("historical_cib0_tree_sha256")
        != closure.get("historical_cib0_tree_sha256")
        or manifest.get("historical_ck0_tree_sha256")
        != closure.get("historical_ck0_tree_sha256")
    ):
        raise RankHeadV2RunDesignError(
            "binding-1 v2 predecessor lifecycle or private classification failed"
        )
    publication = _require_published_visible_record(
        repository,
        manifest_sha256=manifest_sha256,
        result_sha256=result_sha256,
        closure_sha256=closure_sha256,
    )
    return {
        "run_id": integration.BINDING_1_RUN_ID,
        "manifest_sha256": manifest_sha256,
        "result_sha256": result_sha256,
        "closure_sha256": closure_sha256,
        "terminal_classification": integration.VISIBLE_CLASSIFICATION,
        "run_lock_absent": True,
        "authority_receipt_verified": True,
        "private_classification_recomputed": integration.VISIBLE_CLASSIFICATION,
        "publication": publication,
    }


class QualifiedRankHeadV2Runtime(integration.RankHeadV2Runtime):
    @classmethod
    def from_repository(
        cls,
        repository: Path,
        run_id: str,
        *,
        require_final_design: bool = True,
    ) -> "QualifiedRankHeadV2Runtime":
        design = validate_run_design(
            repository,
            require_final=require_final_design,
        )
        spec = integration.run_spec(run_id)
        if spec.predecessor_run_id is not None:
            require_binding_1_v2_terminal_visible(repository)
        return cls(
            repository=repository,
            spec=spec,
            private=integration.runtime_private_from_repository(repository, run_id),
            run_design=design,
        )


def build_run_design(
    repository: Path,
    *,
    implementation_paths: Sequence[str],
    audits: Mapping[str, str],
    static_verification: Mapping[str, Any],
) -> dict[str, Any]:
    import catalytic_kernel_0_balanced_rank_head_v2_authority as authority

    require_exact_implementation_paths(implementation_paths)
    if dict(audits) != REQUIRED_AUDITS:
        raise RankHeadV2RunDesignError(
            "v2 run design audits must be exact terminal PASS"
        )
    if static_verification.get("status") != "pass":
        raise RankHeadV2RunDesignError(
            "v2 run design verification must be terminal PASS"
        )
    v2_projection = v2.validate_preregistration(repository)
    runs = []
    for run_id in integration.RUN_ORDER:
        spec = integration.run_spec(run_id)
        private = integration.runtime_private_from_repository(repository, run_id)
        runs.append(
            {
                **spec.body(),
                "state_root": f"{STATE_ROOT}/{run_id}",
                "state_filenames": list(STATE_FILENAMES),
                "authority_receipt_path": AUTHORITY_RECEIPT_TEMPLATE.replace(
                    "<run-id>",
                    run_id,
                ),
                "source_custody": source_binding_custody(repository, spec),
                "run_key_commitment": balanced.run_key_commitment(
                    private.run_key(run_id),
                    private.configuration,
                ),
            }
        )
    document = {
        "schema_version": 1,
        "status": "static-preregistered",
        "integration_id": integration.INTEGRATION_ID,
        "protected_starting_main": integration.STARTING_PROTECTED_MAIN,
        "v2_static_preregistration": v2_projection,
        "v2_carrier": {
            key: v2.build_v2_carrier()[key]
            for key in (
                "carrier_id",
                "carrier_content_sha256",
                "carrier_root_sha256",
            )
        },
        "logical_stages": list(integration.LOGICAL_STAGES),
        "model_request_stages": list(integration.MODEL_REQUEST_STAGES),
        "controller_stage": "extract",
        "runtime_entrypoint": {
            "module": (
                "scripts/catalytic_kernel_0_balanced_rank_head_v2_entrypoint.py"
            ),
            "function": "run_rank_head_v2",
            "live_core_module": (
                "scripts/catalytic_kernel_0_balanced_rank_head_v2_live.py"
            ),
            "runtime_class": "QualifiedRankHeadV2Runtime",
            "historical_v1_runner_modified": False,
            "holostate_cli_registered": False,
            "protected_sidecar_adapter_integration": "implemented",
            "post_consumption_fail_closed_closure": "implemented",
            "authority_bridge_module": (
                "scripts/catalytic_kernel_0_balanced_rank_head_v2_authority.py"
            ),
        },
        "state_namespace": {
            "root": STATE_ROOT,
            "filenames": list(STATE_FILENAMES),
            "ignored_runtime_required": True,
            "authority_receipt_template": AUTHORITY_RECEIPT_TEMPLATE,
            "ignored_authority_receipts_required": True,
        },
        "authority_contract": {
            "schema_version": authority.AUTHORITY_SCHEMA_VERSION,
            "kind": authority.AUTHORITY_KIND,
            "object_schema_sha256": authority.AUTHORITY_OBJECT_SCHEMA_SHA256,
            "receipt_schema_version": authority.RECEIPT_SCHEMA_VERSION,
            "receipt_schema_sha256": authority.AUTHORITY_RECEIPT_SCHEMA_SHA256,
            "receipt_path_template": authority.RECEIPT_TEMPLATE,
            "authority_id_input": "explicit-raw-64-hex-no-default-no-environment-fallback",
            "authorized_commit_input": "explicit-exact-protected-commit-no-default",
            "maximum_invocations": 1,
            "retry_count": 0,
            "automatic_follow_on": False,
            "raw_authority_id_persisted": False,
            "consumption_point": "immediately-before-v2-runtime-root-creation",
            "global_inventory_across_both_runs": True,
        },
        "lifecycle_contract": {
            "logical_stages": 6,
            "model_requests": 5,
            "physical_leases": 5,
            "physical_slots": 1,
            "sidecar_epochs": 1,
            "controller_extraction_uses_lease": False,
            "completed_model_responses_required": 5,
            "completed_logical_stages_required": 6,
            "maximum_concurrent_leases": 1,
            "active_leases_at_closure": 0,
        },
        "run_order": list(integration.RUN_ORDER),
        "runs": runs,
        "authorization_boundary": {
            "external_one_shot_authority_required_per_run": True,
            "authority_implementation_present": True,
            "authority_consumption_point": (
                "after-complete-nonmutating-admission-before-runtime-root"
            ),
            "authority_reuse_across_runs_allowed": False,
            "first_separately_authorizable_run": integration.BINDING_1_RUN_ID,
            "binding_2_run_requires_binding_1_terminal_visible": True,
            "predecessor_gate_implemented": True,
            "authority_created": False,
            "live_execution_authorized": False,
            "retry_allowed": False,
            "automatic_follow_on": False,
        },
        "binding_2_predecessor_publication_gate": {
            "run_id": integration.BINDING_1_RUN_ID,
            "required_classification": integration.VISIBLE_CLASSIFICATION,
            "raw_manifest_result_closure_required": True,
            "closure_hashes_recomputed": True,
            "run_lock_absent": True,
            "run_design_identity_exact": True,
            "static_preregistration_identity_exact": True,
            "carrier_identity_exact": True,
            "external_authority_evidence_identical_and_cryptographically_verified": True,
            "branch_transform_and_deterministic_extraction_verified": True,
            "private_visible_classification_recomputed": True,
            "restoration_cleanup_and_historical_custody_required": True,
            "lease_count": 5,
            "maximum_concurrency": 1,
            "active_leases": 0,
            "tracked_publication": "exactly-one-lab-results-jsonl-record-with-raw-hashes",
            "raw_ignored_evidence_alone_authorizes_binding_2": False,
        },
        "private_state": {
            "new_secret_created": False,
            "source_private_roots": ["binding-1", "binding-2"],
            "source_commitments_bound_per_run": True,
            "source_alias_mappings_preserved": True,
            "v2_run_keys_domain_separated": True,
            "source_private_roots_modified": False,
        },
        "implementation_binding": balanced.implementation_binding(
            repository,
            implementation_paths,
        ),
        "audits": dict(audits),
        "static_verification": dict(static_verification),
        "claim_boundary": {
            "historical_binding_2_classification": (
                "BALANCED_OPAQUE_RELATIONAL_COLLAPSED"
            ),
            "locked": [
                "v2-live-correctness",
                "end-to-end-cross-binding-replication",
                "binding-2-parent-dependence",
                "causal-replication",
                "general-two-parent-necessity",
                "transfer",
                "general-catalytic-inference",
                "task-advantage",
                "superiority",
                "sota",
                "broader-holostate",
                "restart-persistence",
                "deep",
                "automatic-promotion",
            ],
            "runtime_classifications": {
                "visible": integration.VISIBLE_CLASSIFICATION,
                "collapsed": integration.COLLAPSED_CLASSIFICATION,
                "inconclusive": integration.INCONCLUSIVE_CLASSIFICATION,
            },
        },
    }
    balanced.validate_metadata_only(document)
    return document


def write_run_design(repository: Path, document: Mapping[str, Any]) -> Path:
    path = repository / RUN_DESIGN_PATH
    if path.exists() or path.is_symlink():
        raise RankHeadV2RunDesignError("v2 run design already exists")
    payload = (
        json.dumps(
            document,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".ck0-rank-head-v2-run-design-",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        written = os.write(descriptor, payload)
        if written != len(payload):
            raise RankHeadV2RunDesignError(
                "v2 run design write was incomplete"
            )
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.link(temporary, path, follow_symlinks=False)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()
    return path


def validate_run_design(
    repository: Path,
    *,
    require_final: bool = True,
) -> dict[str, Any]:
    path = repository / RUN_DESIGN_PATH
    if not path.is_file() or path.is_symlink():
        raise RankHeadV2RunDesignError("v2 run design is missing or unsafe")
    try:
        document = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        raise RankHeadV2RunDesignError("v2 run design is invalid JSON") from exc
    if not isinstance(document, Mapping):
        raise RankHeadV2RunDesignError(
            "v2 run design root is not an object"
        )
    binding = document.get("implementation_binding")
    files = binding.get("files") if isinstance(binding, Mapping) else None
    if not isinstance(files, list) or any(
        not isinstance(item, Mapping) for item in files
    ):
        raise RankHeadV2RunDesignError(
            "v2 run design binding is malformed"
        )
    paths = [item.get("path") for item in files]
    require_exact_implementation_paths(paths)
    expected = build_run_design(
        repository,
        implementation_paths=paths,
        audits=document.get("audits", {}),
        static_verification=document.get("static_verification", {}),
    )
    if document != expected:
        raise RankHeadV2RunDesignError(
            "v2 run design differs from exact reconstruction"
        )
    if require_final and (
        document.get("audits") != REQUIRED_AUDITS
        or document.get("static_verification", {}).get("status") != "pass"
    ):
        raise RankHeadV2RunDesignError(
            "v2 run design is not terminally qualified"
        )
    return {
        "relative_path": RUN_DESIGN_PATH,
        "artifact_sha256": sha256_bytes(path.read_bytes()),
        "document_sha256": json_sha256(document),
        "implementation_binding_sha256": binding.get("sha256"),
        "run_ids_reserved": list(integration.RUN_ORDER),
        "first_separately_authorizable_run": integration.BINDING_1_RUN_ID,
        "binding_2_predecessor_gate_implemented": True,
        "authority_bridge_implemented": True,
        "fail_closed_entrypoint_implemented": True,
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
            raise RankHeadV2RunDesignError(
                "audit values must use NAME=OUTCOME"
            )
        result[name] = outcome
    return result


def main() -> int:
    args = parse_args()
    repository = args.repository.resolve()
    try:
        if args.operation == "generate":
            if not args.static_verification_json:
                raise RankHeadV2RunDesignError(
                    "generate requires --static-verification-json"
                )
            verification = json.loads(
                args.static_verification_json.read_text(encoding="utf-8")
            )
            document = build_run_design(
                repository,
                implementation_paths=args.implementation_path,
                audits=parse_audits(args.audit),
                static_verification=verification,
            )
            path = write_run_design(repository, document)
            result = {
                "status": "written",
                "path": str(path),
                "artifact_sha256": sha256_bytes(path.read_bytes()),
                "document_sha256": json_sha256(document),
            }
        else:
            result = validate_run_design(repository)
    except (
        RankHeadV2RunDesignError,
        integration.RankHeadV2IntegrationError,
        balanced.BalancedOpaqueError,
        v2.RankHeadDesignError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
