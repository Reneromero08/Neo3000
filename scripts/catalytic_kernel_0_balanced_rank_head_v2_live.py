#!/usr/bin/env python3
"""Standalone protected lifecycle for deterministic-rank-head CK0 v2.

This is a versioned entrypoint and does not register into the historical CK0 or
HoloState CLI. Live execution remains impossible without a separately supplied
external one-shot authority and an exact protected commit.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping

import catalytic_kernel_0 as kernel
import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2 as v2
import catalytic_kernel_0_balanced_rank_head_v2_authority as authority
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration
import catalytic_kernel_0_balanced_rank_head_v2_run_design as run_design

STATE_SCHEMA_VERSION = 1
CLAIMS = {
    "END_TO_END_CROSS_BINDING_REPLICATION": "LOCKED",
    "BINDING_2_PARENT_DEPENDENCE": "LOCKED",
    "CAUSAL_REPLICATION_ACROSS_BINDINGS": "LOCKED",
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


class RankHeadV2LiveError(ValueError):
    pass


def _arg(args: Any, name: str) -> Any:
    return args.get(name) if isinstance(args, Mapping) else getattr(args, name, None)


def state_paths(repository: Path, run_id: str, state_root: Path | None = None) -> dict[str, Path]:
    integration.run_spec(run_id)
    root = (state_root or (repository / run_design.STATE_ROOT)).resolve() / run_id
    try:
        root.relative_to(repository.resolve())
    except ValueError as exc:
        raise RankHeadV2LiveError("v2 state must remain below the repository") from exc
    return {name: root / name for name in run_design.STATE_FILENAMES}


def logical_execution_plan() -> list[dict[str, Any]]:
    return [
        {
            "stage": stage,
            "ordinal": ordinal,
            "execution_mode": (
                "controller-deterministic"
                if stage == "extract"
                else "model-request"
            ),
            "model_request_issued": stage in integration.MODEL_REQUEST_STAGES,
            "physical_lease_required": stage in integration.MODEL_REQUEST_STAGES,
        }
        for ordinal, stage in enumerate(integration.LOGICAL_STAGES, 1)
    ]


def _predecessor_and_runtime(
    repository: Path,
    run_id: str,
) -> run_design.QualifiedRankHeadV2Runtime:
    return run_design.QualifiedRankHeadV2Runtime.from_repository(
        repository,
        run_id,
        require_final_design=True,
    )


def _prepare_authority(
    repository: Path,
    runtime: run_design.QualifiedRankHeadV2Runtime,
    *,
    raw_authority_id: str,
    authorized_commit: str,
    public_preflight: Mapping[str, Any],
) -> authority.RankHeadV2ExternalAuthority:
    stable = public_preflight.get("stable", {})
    model = public_preflight.get("model_identity", {})
    binary = public_preflight.get("binary_identity", {})
    current_commit = stable.get("head")
    if not isinstance(current_commit, str):
        raise RankHeadV2LiveError("v2 preflight protected commit is missing")
    return authority.build_external_authority(
        private=runtime.private,
        spec=runtime.spec,
        raw_authority_id=raw_authority_id,
        authorized_commit=authorized_commit,
        current_commit=current_commit,
        run_design_projection=run_design.validate_run_design(repository),
        static_preregistration_projection=v2.validate_preregistration(repository),
        model_sha256=str(model.get("sha256", "")),
        binary_sha256=str(binary.get("sha256", "")),
    )


def _manifest(
    runtime: run_design.QualifiedRankHeadV2Runtime,
    *,
    public_preflight: Mapping[str, Any],
    run_design_projection: Mapping[str, Any],
    static_projection: Mapping[str, Any],
    authority_evidence: Mapping[str, Any],
    historical_cib0: Mapping[str, Any],
    historical_ck0: Mapping[str, Any],
) -> dict[str, Any]:
    manifest = {
        "schema_version": STATE_SCHEMA_VERSION,
        "kernel_id": "catalytic-kernel-0-rank-head-v2",
        "run_id": runtime.run_id,
        "run_ordinal": runtime.spec.ordinal,
        "source_binding": runtime.spec.source_binding,
        "mode": "full-information",
        "carrier": {
            "carrier_id": runtime.carrier["carrier_id"],
            "carrier_content_sha256": runtime.carrier["carrier_content_sha256"],
            "carrier_root_sha256": runtime.carrier["carrier_root_sha256"],
        },
        "logical_execution_plan": logical_execution_plan(),
        "logical_stage_count": len(integration.LOGICAL_STAGES),
        "model_request_count": len(integration.MODEL_REQUEST_STAGES),
        "physical_slots": 1,
        "sidecar_epochs": 1,
        "run_design": dict(run_design_projection),
        "static_preregistration": dict(static_projection),
        "external_live_authority": dict(authority_evidence),
        "historical_cib0_tree_sha256": historical_cib0["tree_sha256"],
        "historical_ck0_tree_sha256": historical_ck0["tree_sha256"],
        "preflight": dict(public_preflight),
        "claims": dict(CLAIMS),
        "claiming": False,
        "automatic_promotion": False,
    }
    balanced.validate_metadata_only(manifest)
    return manifest


def _result_projection(
    runtime: run_design.QualifiedRankHeadV2Runtime,
    *,
    public_preflight: Mapping[str, Any],
    readiness: Mapping[str, Any] | None,
    outcomes: list[dict[str, Any]],
    artifacts: Mapping[str, Mapping[str, Any]],
    completed_model_responses: int,
    cleanup: Mapping[str, Any],
    postflight: Mapping[str, Any],
    lease: Mapping[str, Any],
    restoration: Mapping[str, Any] | None,
    failure: Mapping[str, Any] | None,
    authority_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    restoration_passed = (
        isinstance(restoration, Mapping) and restoration.get("passed") is True
    )
    classification = runtime.classify_v2(
        artifacts,
        completed_model_responses=completed_model_responses,
        restoration_passed=restoration_passed,
    )
    complete = (
        len(outcomes) == len(integration.LOGICAL_STAGES)
        and completed_model_responses == len(integration.MODEL_REQUEST_STAGES)
        and failure is None
        and classification != integration.INCONCLUSIVE_CLASSIFICATION
    )
    result = {
        "schema_version": STATE_SCHEMA_VERSION,
        "kernel_id": "catalytic-kernel-0-rank-head-v2",
        "run_id": runtime.run_id,
        "run_ordinal": runtime.spec.ordinal,
        "source_binding": runtime.spec.source_binding,
        "status": "complete" if complete else "failed",
        "terminal_classification": (
            classification if complete else integration.INCONCLUSIVE_CLASSIFICATION
        ),
        "carrier": {
            "carrier_id": runtime.carrier["carrier_id"],
            "carrier_content_sha256": runtime.carrier["carrier_content_sha256"],
            "carrier_root_sha256": runtime.carrier["carrier_root_sha256"],
        },
        "preflight": dict(public_preflight),
        "readiness": dict(readiness) if isinstance(readiness, Mapping) else None,
        "logical_stage_count_required": len(integration.LOGICAL_STAGES),
        "model_request_count_required": len(integration.MODEL_REQUEST_STAGES),
        "completed_model_responses": completed_model_responses,
        "stage_outcomes": [dict(item) for item in outcomes],
        "branch_a": artifacts.get("branch-a"),
        "branch_b": artifacts.get("branch-b"),
        "transform": artifacts.get("transform"),
        "deterministic_extraction": artifacts.get("extract"),
        "restoration": dict(restoration) if isinstance(restoration, Mapping) else None,
        "lease_accounting": dict(lease),
        "cleanup": dict(cleanup),
        "postflight_custody": dict(postflight),
        "failure": dict(failure) if isinstance(failure, Mapping) else None,
        "external_live_authority": dict(authority_evidence),
        "persistence_mode": "bounded-normalized-metadata-only",
        "transport_retention": "none",
        "claims": dict(CLAIMS),
        "claiming": False,
        "automatic_promotion": False,
    }
    balanced.validate_metadata_only(result)
    return result


def run_rank_head_v2(
    args: Any,
    *,
    adapter: kernel.KernelAdapter | None = None,
    repository_root: str | os.PathLike[str] | None = None,
    state_root: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    repository = (
        Path(repository_root).resolve()
        if repository_root is not None
        else Path(__file__).resolve().parents[1]
    )
    run_id = str(_arg(args, "run_id") or "")
    runtime = _predecessor_and_runtime(repository, run_id)
    raw_authority_id = _arg(args, "external_live_authority_id")
    authorized_commit = _arg(args, "authorized_commit")
    if not isinstance(raw_authority_id, str) or not isinstance(
        authorized_commit,
        str,
    ):
        raise RankHeadV2LiveError(
            "v2 live execution requires external authority ID and authorized commit"
        )
    paths = state_paths(
        repository,
        run_id,
        Path(state_root).resolve() if state_root is not None else None,
    )
    run_root = paths["manifest.json"].parent
    if run_root.exists() or run_root.is_symlink():
        raise RankHeadV2LiveError("v2 run ID already exists")
    authority.assert_authority_unconsumed(
        repository,
        run_id,
        authority.authority_id_sha256(raw_authority_id),
    )
    historical_cib0 = kernel._snapshot_tree(
        repository / "state" / "catalytic_inference_bench_0"
    )
    historical_ck0 = kernel._snapshot_historical_ck0(
        repository / "state" / "catalytic_kernel_0"
    )
    live = adapter if adapter is not None else kernel.CatalyticKernel0Adapter(repository)
    full_preflight = live.preflight(
        args=args,
        repository_root=repository,
        run_root=run_root,
        allowed_paths=tuple(paths.values()),
    )
    public_preflight = kernel._public_preflight(full_preflight)
    run_projection = run_design.validate_run_design(repository)
    static_projection = v2.validate_preregistration(repository)
    external_authority = _prepare_authority(
        repository,
        runtime,
        raw_authority_id=raw_authority_id,
        authorized_commit=authorized_commit,
        public_preflight=public_preflight,
    )
    authority.validate_external_authority(
        runtime.private,
        external_authority,
        spec=runtime.spec,
        current_commit=str(public_preflight["stable"]["head"]),
        receipt_hmac=authority.authority_receipt_hmac(
            runtime.private,
            external_authority,
        ),
    )
    authority_evidence = authority.consume_authority_once(
        repository,
        runtime.private,
        external_authority,
    )

    run_root.mkdir(parents=True)
    lock_descriptor = os.open(
        paths["run.lock"],
        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
    )
    os.write(lock_descriptor, (run_id + "\n").encode("ascii"))
    os.fsync(lock_descriptor)
    os.close(lock_descriptor)
    kernel._atomic_json(
        paths["manifest.json"],
        _manifest(
            runtime,
            public_preflight=public_preflight,
            run_design_projection=run_projection,
            static_projection=static_projection,
            authority_evidence=authority_evidence,
            historical_cib0=historical_cib0,
            historical_ck0=historical_ck0,
        ),
    )

    pool = live.create_lease_pool(1)
    sidecar: Any | None = None
    readiness: Mapping[str, Any] | None = None
    outcomes: list[dict[str, Any]] = []
    artifacts: dict[str, dict[str, Any]] = {}
    completed_model_responses = 0
    cleanup: Mapping[str, Any] = {"passed": False}
    postflight: Mapping[str, Any] = {"passed": False}
    restoration: Mapping[str, Any] | None = None
    failure: Mapping[str, Any] | None = None
    warm_tokens: list[int] | None = None
    warm_terminal: int | None = None
    warm_terminal_identity: str | None = None
    restore_terminal: int | None = None
    restore_terminal_identity: str | None = None
    restore_cache_admitted = False
    current_outcome: dict[str, Any] | None = None
    current_stage: str | None = None

    try:
        sidecar, readiness = live.launch_sidecar(
            preflight=full_preflight,
            run_id=run_id,
        )
        for ordinal, stage in enumerate(integration.LOGICAL_STAGES, 1):
            current_stage = stage
            current_outcome = {
                "stage": stage,
                "ordinal": ordinal,
                "status": "started",
                "execution_mode": (
                    "controller-deterministic"
                    if stage == "extract"
                    else "model-request"
                ),
                "model_request_issued": stage in integration.MODEL_REQUEST_STAGES,
                "physical_slot": (
                    kernel.PHYSICAL_SLOT
                    if stage in integration.MODEL_REQUEST_STAGES
                    else None
                ),
            }
            before_resource = kernel._resource_observation(
                live,
                sidecar,
                f"before:{stage}",
            )
            before_custody = dict(
                live.boundary_custody(
                    preflight=full_preflight,
                    sidecar=sidecar,
                    boundary=f"before:{stage}",
                )
            )
            if (
                before_custody.get("passed") is not True
                or kernel._resource_breach(before_resource)
            ):
                raise RankHeadV2LiveError(
                    "v2 pre-stage custody or measured resource ceiling failed"
                )

            if stage == "extract":
                transform = artifacts.get("transform")
                if not isinstance(transform, Mapping):
                    raise RankHeadV2LiveError("v2 extract parent is missing")
                artifacts["extract"] = runtime.deterministic_extract(transform)
                after_resource = kernel._resource_observation(
                    live,
                    sidecar,
                    "after:extract",
                )
                after_custody = dict(
                    live.boundary_custody(
                        preflight=full_preflight,
                        sidecar=sidecar,
                        boundary="after:extract",
                    )
                )
                if (
                    after_custody.get("passed") is not True
                    or kernel._resource_breach(after_resource)
                ):
                    raise RankHeadV2LiveError(
                        "v2 post-extract custody or measured resource ceiling failed"
                    )
                current_outcome.update(
                    {
                        "status": "accepted",
                        "artifact_commitment": artifacts["extract"][
                            "artifact_commitment"
                        ],
                        "custody": {
                            "before": before_custody,
                            "after": after_custody,
                        },
                        "resources": {
                            "before": before_resource,
                            "after": after_resource,
                        },
                    }
                )
                outcomes.append(current_outcome)
                current_outcome = None
                continue

            payload = runtime.build_model_request(stage, artifacts)
            geometry = live.prompt_geometry(sidecar=sidecar, payload=payload)
            token_ids = list(geometry["token_ids"])
            terminal = int(geometry["public_root_terminal_token_index"])
            terminal_identity = kernel._terminal_identity(token_ids, terminal)
            if stage == "borrow":
                warm_tokens = token_ids
                warm_terminal = terminal
                warm_terminal_identity = terminal_identity
            elif (
                warm_tokens is None
                or terminal != warm_terminal
                or terminal_identity != warm_terminal_identity
            ):
                raise RankHeadV2LiveError("v2 immutable carrier root identity changed")
            common_prefix = (
                len(token_ids)
                if stage == "borrow"
                else kernel._common_prefix(warm_tokens, token_ids)
            )
            request = kernel.KernelRequest(request_id=stage, ordinal=ordinal)
            with pool.lease() as lease_id:
                if lease_id != kernel.PHYSICAL_SLOT:
                    raise RankHeadV2LiveError(
                        "v2 one-slot pool returned a nonzero lease"
                    )
                execution = live.execute_request(
                    sidecar=sidecar,
                    payload=payload,
                    request=request,
                )
            completed_model_responses += 1
            after_resource = kernel._resource_observation(
                live,
                sidecar,
                f"after:{stage}",
            )
            after_custody = dict(
                live.boundary_custody(
                    preflight=full_preflight,
                    sidecar=sidecar,
                    boundary=f"after:{stage}",
                )
            )
            if (
                after_custody.get("passed") is not True
                or kernel._resource_breach(after_resource)
            ):
                raise RankHeadV2LiveError(
                    "v2 post-request custody or measured resource ceiling failed"
                )
            transport = kernel._normalized_transport(
                execution,
                rendered_tokens=len(token_ids),
                max_tokens=64,
            )
            structured = runtime.parse_response(
                stage,
                transport["structured_content"],
                transform_artifact=artifacts.get("transform"),
            )
            if stage in {"branch-a", "branch-b"}:
                artifacts[stage] = runtime.normalize_branch(
                    stage,
                    structured["ranking"],
                )
            elif stage == "transform":
                artifacts[stage] = runtime.normalize_transform(
                    structured["operator"],
                    structured["ranking"],
                )

            if stage == "borrow":
                cache_admission = {
                    "classification": "carrier-root-warmed",
                    "admitted": True,
                    "reasons": [
                        "borrow established the immutable v2 process-local root"
                    ],
                }
            else:
                cache_admission = kernel.adjudicate_root_cache(
                    kernel.RootCacheObservation(
                        public_root_terminal_token_index=terminal,
                        common_prefix_tokens=common_prefix,
                        legacy_required_cached_prompt_tokens=common_prefix,
                        actual_cached_prompt_tokens=transport["metadata"][
                            "cached_prompt_tokens"
                        ],
                        branch_prompt_tokens=transport["metadata"][
                            "prompt_tokens"
                        ],
                        fresh_prompt_tokens=transport["metadata"][
                            "fresh_prompt_tokens"
                        ],
                        completion_tokens=transport["metadata"][
                            "completion_tokens"
                        ],
                        response_completed=True,
                        transport_passed=True,
                        token_evidence_passed=True,
                    )
                ).to_dict()
            cache_admitted = cache_admission["admitted"] is True
            if stage != "borrow" and not cache_admitted:
                raise RankHeadV2LiveError(
                    "v2 exact carrier-root cache admission failed"
                )
            if stage == "restore":
                restore_terminal = terminal
                restore_terminal_identity = terminal_identity
                restore_cache_admitted = cache_admitted
            current_outcome.update(
                {
                    "status": "accepted",
                    "model_request_sha256": balanced.json_sha256(payload),
                    "normalized_artifact_commitment": artifacts.get(stage, {}).get(
                        "artifact_commitment"
                    ),
                    "transport": transport["metadata"],
                    "cache": {
                        "required": stage != "borrow",
                        "admitted": cache_admitted,
                        "carrier_terminal_token_index": terminal,
                        "carrier_terminal_identity_sha256": terminal_identity,
                        "common_prefix_tokens": common_prefix,
                        "admission_law": cache_admission,
                    },
                    "custody": {
                        "before": before_custody,
                        "after": after_custody,
                    },
                    "resources": {
                        "before": before_resource,
                        "after": after_resource,
                    },
                }
            )
            outcomes.append(current_outcome)
            current_outcome = None
    except BaseException as exc:
        failure = kernel._safe_failure(exc, boundary=current_stage or "runtime")
        if current_outcome is not None:
            current_outcome["status"] = "rejected"
            current_outcome["failure"] = dict(failure)
            outcomes.append(current_outcome)
            current_outcome = None
    finally:
        try:
            cleanup = dict(
                live.cleanup(sidecar=sidecar, preflight=full_preflight)
            )
        except BaseException as exc:
            cleanup = {
                "passed": False,
                "failure": kernel._safe_failure(exc, boundary="cleanup"),
            }
            failure = failure or cleanup["failure"]
        try:
            postflight = dict(live.postflight(preflight=full_preflight))
        except BaseException as exc:
            postflight = {
                "passed": False,
                "failure": kernel._safe_failure(exc, boundary="postflight"),
            }
            failure = failure or postflight["failure"]

    lease = kernel._lease_accounting(pool)
    historical_cib0_after = kernel._snapshot_tree(
        repository / "state" / "catalytic_inference_bench_0"
    )
    historical_ck0_after = kernel._snapshot_historical_ck0(
        repository / "state" / "catalytic_kernel_0"
    )
    cib0_preserved = historical_cib0_after == historical_cib0
    ck0_preserved = historical_ck0_after == historical_ck0
    if not cib0_preserved or not ck0_preserved:
        failure = failure or kernel._safe_failure(
            RankHeadV2LiveError("v2 historical evidence changed"),
            boundary="historical-custody",
        )

    if (
        completed_model_responses == len(integration.MODEL_REQUEST_STAGES)
        and len(outcomes) == len(integration.LOGICAL_STAGES)
        and outcomes[-1].get("stage") == "restore"
    ):
        extraction = artifacts.get("extract")
        transform = artifacts.get("transform")
        extraction_verified = False
        if isinstance(extraction, Mapping) and isinstance(transform, Mapping):
            try:
                v2.verify_deterministic_extraction_receipt(
                    runtime,
                    extraction,
                    transform,
                )
                extraction_verified = True
            except (v2.RankHeadDesignError, balanced.BalancedOpaqueError):
                extraction_verified = False
        restoration_body = {
            "carrier_id_before": runtime.carrier["carrier_id"],
            "carrier_id_after": runtime.carrier["carrier_id"],
            "carrier_root_sha256_before": runtime.carrier["carrier_root_sha256"],
            "carrier_root_sha256_after": runtime.carrier["carrier_root_sha256"],
            "carrier_terminal_token_index_before": warm_terminal,
            "carrier_terminal_token_index_after": restore_terminal,
            "carrier_terminal_identity_sha256_before": warm_terminal_identity,
            "carrier_terminal_identity_sha256_after": restore_terminal_identity,
            "cache_root_reuse_admitted": restore_cache_admitted,
            "controller_extraction_receipt_verified": extraction_verified,
            "branch_state_absent_from_carrier": runtime.carrier_is_pristine(
                runtime.carrier
            ),
            "active_leases": lease["active_leases"],
            "lease_count": lease["lease_count"],
            "maximum_concurrent_leases": lease["maximum_concurrent_leases"],
            "logical_stage_count": len(integration.LOGICAL_STAGES),
            "model_request_count": completed_model_responses,
            "sidecar_cleanup_passed": cleanup.get("passed") is True,
            "sidecar_port_free": cleanup.get("port_free") is True,
            "stable_preserved": cleanup.get("stable_preserved") is True,
            "candidate_preserved": postflight.get("passed") is True,
            "historical_cib0_preserved": cib0_preserved,
            "historical_ck0_preserved": ck0_preserved,
        }
        restoration = {
            **restoration_body,
            "passed": all(
                (
                    restoration_body["carrier_id_before"]
                    == restoration_body["carrier_id_after"],
                    restoration_body["carrier_root_sha256_before"]
                    == restoration_body["carrier_root_sha256_after"],
                    restoration_body["carrier_terminal_token_index_before"]
                    == restoration_body["carrier_terminal_token_index_after"],
                    restoration_body[
                        "carrier_terminal_identity_sha256_before"
                    ]
                    == restoration_body[
                        "carrier_terminal_identity_sha256_after"
                    ],
                    restoration_body["cache_root_reuse_admitted"],
                    restoration_body[
                        "controller_extraction_receipt_verified"
                    ],
                    restoration_body["branch_state_absent_from_carrier"],
                    restoration_body["active_leases"] == 0,
                    restoration_body["lease_count"] == 5,
                    restoration_body["maximum_concurrent_leases"] == 1,
                    restoration_body["logical_stage_count"] == 6,
                    restoration_body["model_request_count"] == 5,
                    restoration_body["sidecar_cleanup_passed"],
                    restoration_body["sidecar_port_free"],
                    restoration_body["stable_preserved"],
                    restoration_body["candidate_preserved"],
                    restoration_body["historical_cib0_preserved"],
                    restoration_body["historical_ck0_preserved"],
                )
            ),
            "receipt_sha256": balanced.json_sha256(restoration_body),
        }
        if restoration["passed"] is not True:
            failure = failure or kernel._safe_failure(
                RankHeadV2LiveError("v2 trusted restoration did not pass"),
                boundary="restore",
            )

    verified_authority = authority.verify_authority_receipt(
        repository,
        runtime.private,
        external_authority,
    )
    if verified_authority != authority_evidence:
        failure = failure or kernel._safe_failure(
            RankHeadV2LiveError("v2 authority evidence changed"),
            boundary="external-authority",
        )

    result = _result_projection(
        runtime,
        public_preflight=public_preflight,
        readiness=readiness,
        outcomes=outcomes,
        artifacts=artifacts,
        completed_model_responses=completed_model_responses,
        cleanup=cleanup,
        postflight=postflight,
        lease=lease,
        restoration=restoration,
        failure=failure,
        authority_evidence=authority_evidence,
    )
    kernel._atomic_json(paths["result.json"], result)
    if paths["run.lock"].exists():
        paths["run.lock"].unlink()

    try:
        final_postflight = dict(live.postflight(preflight=full_preflight))
        if final_postflight.get("passed") is not True:
            raise RankHeadV2LiveError("v2 final custody did not pass")
        if kernel._snapshot_tree(
            repository / "state" / "catalytic_inference_bench_0"
        ) != historical_cib0:
            raise RankHeadV2LiveError("v2 historical CIB0 changed at closure")
        if kernel._snapshot_historical_ck0(
            repository / "state" / "catalytic_kernel_0"
        ) != historical_ck0:
            raise RankHeadV2LiveError("v2 historical CK0 changed at closure")
        if authority.verify_authority_receipt(
            repository,
            runtime.private,
            external_authority,
        ) != authority_evidence:
            raise RankHeadV2LiveError("v2 authority changed at closure")
    except BaseException as exc:
        result["status"] = "failed"
        result["terminal_classification"] = integration.INCONCLUSIVE_CLASSIFICATION
        result["failure"] = kernel._safe_failure(
            exc,
            boundary="final-postflight",
        )
        kernel._atomic_json(paths["result.json"], result)
        final_postflight = {"passed": False, "failure": result["failure"]}

    closure_body = {
        "schema_version": STATE_SCHEMA_VERSION,
        "run_id": run_id,
        "manifest_sha256": balanced.sha256_bytes(
            paths["manifest.json"].read_bytes()
        ),
        "result_sha256": balanced.sha256_bytes(paths["result.json"].read_bytes()),
        "run_lock_absent": not paths["run.lock"].exists(),
        "terminal_custody": final_postflight,
        "historical_cib0_tree_sha256": historical_cib0["tree_sha256"],
        "historical_ck0_tree_sha256": historical_ck0["tree_sha256"],
        "run_design_document_sha256": run_projection["document_sha256"],
        "static_preregistration_document_sha256": static_projection[
            "document_sha256"
        ],
        "external_live_authority": dict(authority_evidence),
    }
    kernel._atomic_json(paths["closure.json"], closure_body)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", choices=("run",))
    parser.add_argument("--binary", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--run-id", required=True, choices=integration.RUN_ORDER)
    parser.add_argument("--external-live-authority-id", required=True)
    parser.add_argument("--authorized-commit", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run_rank_head_v2(args)
    except BaseException as exc:
        print(
            json.dumps(
                {
                    "status": "fail",
                    "exception_type": type(exc).__name__,
                    "message_sha256": balanced.sha256_bytes(
                        str(exc).encode("utf-8")
                    ),
                },
                sort_keys=True,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "status": result.get("status"),
                "run_id": result.get("run_id"),
                "terminal_classification": result.get(
                    "terminal_classification"
                ),
            },
            sort_keys=True,
        )
    )
    return 0 if result.get("status") == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
