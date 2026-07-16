#!/usr/bin/env python3
"""Render and validate a bounded publication for the active rank-head v2 run.

This static-only tool derives every result fact from the current r3 receipt,
terminal evidence, private custody, and content-addressed archive. It contains
no r2 result constants and cannot create authority or execute the runtime.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping

import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2 as v2
import catalytic_kernel_0_balanced_rank_head_v2_authority as authority
import catalytic_kernel_0_balanced_rank_head_v2_evidence as evidence
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration
import catalytic_kernel_0_balanced_rank_head_v2_live as live
import catalytic_kernel_0_balanced_rank_head_v2_run_design as run_design


class RankHeadV2PublicationError(ValueError):
    """The active rank-head-v2 evidence is not safely publishable."""


RECORD_ID = "neo-exp-0040"
RUN_ID = integration.BINDING_1_RUN_ID
CLASSIFICATION = integration.VISIBLE_CLASSIFICATION
MAX_RECORD_BYTES = 64 * 1024
TOP_LEVEL_KEYS = (
    "id",
    "checkpoint",
    "hypothesis",
    "intervention",
    "baseline_commit",
    "candidate_commit",
    "model_hash",
    "configuration",
    "metrics_before",
    "metrics_after",
    "quality_gates",
    "verdict",
    "next_boundary",
)
FORBIDDEN_KEYS = frozenset(
    {
        "alias_map",
        "candidate_alias",
        "cross_binding_correspondence",
        "internal_candidate_id",
        "private_root",
        "ranking",
        "raw_authority_id",
        "run_key",
        "secret",
        "support_aliases",
    }
)


def canonical_json_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RankHeadV2PublicationError(message)


def _require_source_claim_boundary(
    manifest: Mapping[str, Any],
    result: Mapping[str, Any],
) -> None:
    expected = dict(live.CLAIMS)
    _require(
        manifest.get("claims") == expected
        and result.get("claims") == expected
        and manifest.get("claiming") is False
        and result.get("claiming") is False
        and manifest.get("automatic_promotion") is False
        and result.get("automatic_promotion") is False,
        "source claim boundary differs from the frozen live contract",
    )


def _is_ignored(repository: Path, path: Path) -> bool:
    completed = subprocess.run(
        ["git", "check-ignore", "--", path.relative_to(repository).as_posix()],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.returncode == 0 and bool(completed.stdout.strip())


def _load_regular_json(repository: Path, path: Path) -> dict[str, Any]:
    balanced._assert_safe_ancestry(repository, path)
    if (
        not path.is_file()
        or path.is_symlink()
        or balanced._is_reparse(path)
        or path.stat().st_size > 8_000_000
    ):
        raise RankHeadV2PublicationError(f"missing or unsafe JSON evidence: {path}")
    try:
        value = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        raise RankHeadV2PublicationError(f"invalid JSON evidence: {path}") from exc
    if not isinstance(value, dict):
        raise RankHeadV2PublicationError(
            f"JSON evidence root is not an object: {path}"
        )
    return value


def _evidence_paths(repository: Path) -> dict[str, Path]:
    root = repository / run_design.STATE_ROOT / RUN_ID
    return {
        "receipt": authority.authority_receipt_path(repository, RUN_ID),
        "manifest": root / "manifest.json",
        "result": root / "result.json",
        "closure": root / "closure.json",
        "run_lock": root / "run.lock",
    }


def _verified_authority(repository: Path) -> dict[str, Any]:
    try:
        verified = authority.verify_authority_receipt_for_run(repository, RUN_ID)
    except (authority.RankHeadV2AuthorityError, OSError, json.JSONDecodeError) as exc:
        raise RankHeadV2PublicationError(
            "active rank-head-v2 authority receipt did not verify"
        ) from exc
    body = verified.get("authority")
    _require(isinstance(body, Mapping), "verified authority body is missing")
    _require(
        body.get("schema_version") == authority.AUTHORITY_SCHEMA_VERSION
        and body.get("run_id") == RUN_ID
        and body.get("predecessor_run_id") is None
        and body.get("predecessor_publication_commit") is None
        and body.get("predecessor_publication_record_sha256") is None,
        "binding-1 authority scope changed",
    )
    _require(
        verified.get("consumed") is True
        and verified.get("consumption_occurred_before_live_mutation") is True
        and verified.get("maximum_invocations") == 1
        and verified.get("retry_allowed") is False,
        "authority consumption law changed",
    )
    return verified


def _private_reconstruction(
    repository: Path,
    result: Mapping[str, Any],
    run_projection: Mapping[str, Any],
) -> tuple[dict[str, Any], tuple[balanced.PrivateBinding, balanced.PrivateBinding]]:
    spec = integration.run_spec(RUN_ID)
    private = integration.runtime_private_from_repository(repository, RUN_ID)
    runtime = integration.RankHeadV2Runtime(
        repository=repository,
        spec=spec,
        private=private,
        run_design=run_projection,
    )
    artifacts = {
        "branch-a": result.get("branch_a"),
        "branch-b": result.get("branch_b"),
        "transform": result.get("transform"),
        "extract": result.get("deterministic_extraction"),
    }
    _require(
        all(isinstance(item, Mapping) for item in artifacts.values()),
        "terminal artifact set is incomplete",
    )
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
        raise RankHeadV2PublicationError(
            "private artifact reconstruction failed"
        ) from exc
    classification = runtime.classify_v2(
        artifacts,
        completed_model_responses=int(result.get("completed_model_responses", -1)),
        restoration_passed=result.get("restoration", {}).get("passed") is True,
    )
    transform = artifacts["transform"]
    extraction = artifacts["extract"]
    ranking = transform.get("ranking")
    evaluation = extraction.get("controller_private_evaluation")
    winner = private.internal_to_alias[balanced.EXPECTED_FULL_SUPPORT[0]]
    _require(
        classification == CLASSIFICATION
        and isinstance(ranking, list)
        and len(ranking) == 3
        and ranking[0] == winner
        and transform.get("operator") == "reconcile"
        and isinstance(evaluation, Mapping)
        and extraction.get("candidate_alias") == winner
        and extraction.get("selection_frozen_before_private_mapping") is True
        and extraction.get("private_mapping_consulted_before_selection") is False
        and evaluation.get("full_public_score") == 5
        and evaluation.get("full_public_total") == 5,
        "bounded private facts differ from visible rank-head v2 law",
    )
    facts = {
        "classification": classification,
        "transform_operator": transform.get("operator"),
        "transform_commitment": transform.get("artifact_commitment"),
        "transform_ranking_length": len(ranking),
        "transform_top_matched_private_singleton": True,
        "extraction_mode": extraction.get("extraction_mode"),
        "selected_rank": extraction.get("selected_rank"),
        "selection_frozen_before_private_mapping": True,
        "private_mapping_consulted_before_selection": False,
        "extraction_selected_private_singleton": True,
        "private_public_score": 5,
        "private_public_total": 5,
        "extraction_commitment": extraction.get("artifact_commitment"),
    }
    bindings = (
        balanced._private_binding_from_repository(repository, balanced.BINDING_1),
        balanced._private_binding_from_repository(repository, balanced.BINDING_2),
    )
    return facts, bindings


def _request_usage(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    outcomes = [
        item
        for item in result.get("stage_outcomes", [])
        if isinstance(item, Mapping) and item.get("model_request_issued") is True
    ]
    _require(len(outcomes) == 5, "model-request outcome count changed")
    usage: list[dict[str, Any]] = []
    for outcome in outcomes:
        transport = outcome.get("transport", {})
        terminal = transport.get("terminal_stop_evidence", {})
        values = tuple(
            transport.get(name)
            for name in (
                "prompt_tokens",
                "cached_prompt_tokens",
                "fresh_prompt_tokens",
                "completion_tokens",
            )
        )
        _require(
            outcome.get("status") == "accepted"
            and all(type(value) is int and value >= 0 for value in values)
            and values[0] == values[1] + values[2]
            and transport.get("finish_reason") == "stop"
            and terminal.get("observed") is True
            and terminal.get("stop_type") == "eos",
            f"{outcome.get('stage')} transport evidence is incomplete",
        )
        usage.append(
            {
                "request_id": outcome.get("stage"),
                "status": "accepted",
                "prompt_tokens": values[0],
                "cached_prompt_tokens": values[1],
                "fresh_prompt_tokens": values[2],
                "completion_tokens": values[3],
                "finish_reason": "stop",
                "terminal_stop_observed": True,
            }
        )
    return usage


def _verified_archive(
    repository: Path,
    protected_commit: str,
    hashes: Mapping[str, str],
) -> dict[str, Any]:
    root = repository / evidence.ARCHIVE_ROOT / RUN_ID
    _require(root.is_dir() and not balanced._is_reparse(root), "evidence archive is absent")
    matches: list[dict[str, Any]] = []
    for candidate in root.iterdir():
        if not candidate.is_dir() or balanced._is_reparse(candidate):
            continue
        try:
            verified = evidence.verify_archive(repository, candidate)
        except (evidence.RankHeadV2EvidenceError, OSError):
            continue
        bundle = verified.get("bundle", {})
        archived_hashes = {
            item.get("name"): item.get("sha256")
            for item in bundle.get("files", [])
            if isinstance(item, Mapping)
        }
        if (
            bundle.get("run_id") == RUN_ID
            and bundle.get("protected_commit") == protected_commit
            and archived_hashes == dict(hashes)
        ):
            matches.append(
                {
                    "bundle_sha256": verified["bundle_sha256"],
                    "purpose": bundle.get("purpose"),
                }
            )
    _require(len(matches) == 1, "exactly one byte-exact evidence archive is required")
    return matches[0]


def _iter_values(value: Any) -> Iterable[tuple[str | None, Any]]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key), item
            yield from _iter_values(item)
    elif isinstance(value, list):
        for item in value:
            yield None, item
            yield from _iter_values(item)


def validate_disclosure_boundary(
    record: Mapping[str, Any],
    private_bindings: tuple[balanced.PrivateBinding, ...] = (),
) -> None:
    forbidden_values: set[str] = set()
    for private in private_bindings:
        forbidden_values.update(str(value) for value in private.alias_to_internal)
        forbidden_values.update(str(value) for value in private.alias_to_internal.values())
    for key, value in _iter_values(record):
        if key is not None and key.casefold() in FORBIDDEN_KEYS:
            raise RankHeadV2PublicationError(
                f"publication disclosure contains forbidden field: {key}"
            )
        if isinstance(value, str) and value in forbidden_values:
            raise RankHeadV2PublicationError(
                "publication disclosure contains a private alias or internal candidate"
            )


def _validate_record_shape(record: Mapping[str, Any]) -> None:
    _require(
        set(record) == set(TOP_LEVEL_KEYS) and len(record) == len(TOP_LEVEL_KEYS),
        "publication top-level split layout changed",
    )
    configuration = record.get("configuration")
    metrics = record.get("metrics_after")
    gates = record.get("quality_gates")
    _require(record.get("id") == RECORD_ID, "publication record ID changed")
    _require(isinstance(configuration, Mapping), "publication configuration is missing")
    _require(isinstance(metrics, Mapping), "publication metrics-after is missing")
    _require(configuration.get("run_id") == RUN_ID, "publication run ID changed")
    _require(
        metrics.get("terminal_classification") == CLASSIFICATION,
        "publication classification changed",
    )
    _require(record.get("verdict") == "accept", "publication verdict changed")
    _require(
        isinstance(gates, Mapping)
        and gates.get("binding_2_parent_dependence_locked") is True
        and gates.get("causal_replication_across_bindings_locked") is True,
        "publication omits a frozen cross-binding claim lock",
    )
    line = canonical_json_text(record)
    _require("\n" not in line and "\r" not in line, "publication is not one line")
    _require(
        len(line.encode("utf-8")) <= MAX_RECORD_BYTES,
        "publication record exceeds 64 KiB",
    )


def render_publication_record(repository: Path) -> dict[str, Any]:
    repository = repository.resolve()
    paths = _evidence_paths(repository)
    receipt_before = paths["receipt"].read_bytes() if paths["receipt"].is_file() else None
    authority_evidence = _verified_authority(repository)
    _require(receipt_before is not None, "consumed authority receipt is missing")
    for name in ("receipt", "manifest", "result", "closure"):
        _require(_is_ignored(repository, paths[name]), f"{name} evidence is not ignored")
    _require(
        not paths["run_lock"].exists() and not paths["run_lock"].is_symlink(),
        "r3 run lock exists",
    )
    manifest = _load_regular_json(repository, paths["manifest"])
    result = _load_regular_json(repository, paths["result"])
    closure = _load_regular_json(repository, paths["closure"])
    hashes = {
        "receipt": balanced.sha256_bytes(paths["receipt"].read_bytes()),
        "manifest": balanced.sha256_bytes(paths["manifest"].read_bytes()),
        "result": balanced.sha256_bytes(paths["result"].read_bytes()),
        "closure": balanced.sha256_bytes(paths["closure"].read_bytes()),
    }
    run_projection = run_design.validate_run_design(repository)
    static_projection = v2.validate_preregistration(repository)
    carrier = v2.build_v2_carrier()
    body = authority_evidence["authority"]
    _require(
        manifest.get("run_id") == RUN_ID
        and manifest.get("run_ordinal") == 1
        and manifest.get("source_binding") == "binding-1"
        and manifest.get("mode") == "full-information"
        and manifest.get("logical_stage_count") == 6
        and manifest.get("model_request_count") == 5
        and manifest.get("physical_slots") == 1
        and manifest.get("sidecar_epochs") == 1
        and manifest.get("run_design") == run_projection
        and manifest.get("static_preregistration") == static_projection
        and manifest.get("carrier", {}).get("carrier_root_sha256")
        == carrier["carrier_root_sha256"],
        "manifest identity or geometry changed",
    )
    _require(
        result.get("run_id") == RUN_ID
        and result.get("run_ordinal") == 1
        and result.get("source_binding") == "binding-1"
        and result.get("status") == "complete"
        and result.get("terminal_classification") == CLASSIFICATION
        and result.get("completed_model_responses") == 5
        and result.get("failure") is None,
        "terminal result classification or boundary changed",
    )
    _require_source_claim_boundary(manifest, result)
    stages = [item for item in result.get("stage_outcomes", []) if isinstance(item, Mapping)]
    _require(
        [item.get("stage") for item in stages] == list(integration.LOGICAL_STAGES)
        and all(item.get("status") == "accepted" for item in stages)
        and stages[4].get("execution_mode") == "controller-deterministic"
        and stages[4].get("model_request_issued") is False,
        "logical stage lifecycle changed",
    )
    _require(
        manifest.get("external_live_authority")
        == result.get("external_live_authority")
        == closure.get("external_live_authority")
        == authority_evidence,
        "authority evidence differs across custody files",
    )
    _require(
        closure.get("run_id") == RUN_ID
        and closure.get("status") == "complete"
        and closure.get("terminal_classification") == CLASSIFICATION
        and closure.get("manifest_sha256") == hashes["manifest"]
        and closure.get("result_sha256") == hashes["result"]
        and closure.get("run_lock_absent") is True
        and closure.get("terminal_custody", {}).get("passed") is True
        and closure.get("run_design_document_sha256")
        == run_projection["document_sha256"]
        and closure.get("static_preregistration_document_sha256")
        == static_projection["document_sha256"],
        "terminal closure binding changed",
    )
    restoration = result.get("restoration", {})
    cleanup = result.get("cleanup", {})
    postflight = result.get("postflight_custody", {})
    lease = result.get("lease_accounting", {})
    _require(
        restoration.get("passed") is True
        and restoration.get("historical_cib0_preserved") is True
        and restoration.get("historical_ck0_preserved") is True
        and cleanup.get("passed") is True
        and postflight.get("passed") is True
        and lease.get("lease_count") == 5
        and lease.get("maximum_concurrent_leases") == 1
        and lease.get("active_leases") == 0,
        "restoration, cleanup, custody, or lease accounting changed",
    )
    bounded, private_bindings = _private_reconstruction(
        repository,
        result,
        run_projection,
    )
    archive = _verified_archive(
        repository,
        str(body["authorized_commit"]),
        hashes,
    )
    record: dict[str, Any] = {
        "id": RECORD_ID,
        "checkpoint": "2-Catalytic-Kernel-0-balanced-rank-head-v2-binding-1-full-information",
        "hypothesis": (
            "Under deterministic-rank-head v2 geometry, controller-native rank-zero "
            "extraction on binding-1 completes visibly without private correspondence "
            "influencing selection."
        ),
        "intervention": (
            "Publish only the consumed one-shot binding-1 r3 terminal result after "
            "independent receipt, raw-evidence, private, and archive verification."
        ),
        "baseline_commit": body["authorized_commit"],
        "candidate_commit": None,
        "model_hash": body["model_sha256"],
        "configuration": {
            "run_id": RUN_ID,
            "profile_id": f"{v2.DESIGN_ID}:binding-1",
            "source_binding": "binding-1",
            "run_mode": "full-information",
            "logical_stages": 6,
            "model_requests": 5,
            "physical_slots": 1,
            "sidecar_epochs": 1,
            "maximum_invocations": 1,
            "retry_count": 0,
            "automatic_follow_on": False,
            "automatic_promotion": False,
            "authorized_commit": body["authorized_commit"],
            "authority_schema_version": body["schema_version"],
            "authority_object_schema_sha256": authority.AUTHORITY_OBJECT_SCHEMA_SHA256,
            "receipt_schema_version": authority.RECEIPT_SCHEMA_VERSION,
            "receipt_schema_sha256": authority.AUTHORITY_RECEIPT_SCHEMA_SHA256,
            "authority_id_sha256": body["authority_id_sha256"],
            "authority_receipt_hmac": authority_evidence["authority_receipt_hmac"],
            "authority_receipt_sha256": authority_evidence["authority_receipt_sha256"],
            "implementation_binding_sha256": run_projection["implementation_binding_sha256"],
            "run_design_artifact_sha256": run_projection["artifact_sha256"],
            "run_design_document_sha256": run_projection["document_sha256"],
            "static_preregistration_artifact_sha256": static_projection["artifact_sha256"],
            "static_preregistration_document_sha256": static_projection["document_sha256"],
            "static_design_contract_sha256": static_projection["design_contract_sha256"],
            "carrier_id": carrier["carrier_id"],
            "carrier_root_sha256": carrier["carrier_root_sha256"],
        },
        "metrics_before": {
            "status": "static-preregistered",
            "binding_2_executed": False,
            "automatic_follow_on": False,
        },
        "metrics_after": {
            "status": "complete",
            "completed_logical_stages": 6,
            "completed_model_responses": 5,
            "authority_consumed": True,
            "request_usage": _request_usage(result),
            "transform": {
                "operator": bounded["transform_operator"],
                "artifact_commitment": bounded["transform_commitment"],
                "ranking_length": bounded["transform_ranking_length"],
                "top_matched_private_singleton": True,
            },
            "deterministic_extraction": {
                "mode": bounded["extraction_mode"],
                "selected_rank": bounded["selected_rank"],
                "selection_frozen_before_private_mapping": True,
                "private_mapping_consulted_before_selection": False,
                "selected_private_singleton": True,
                "full_public_score": 5,
                "full_public_total": 5,
                "artifact_commitment": bounded["extraction_commitment"],
            },
            "restoration_passed": True,
            "cleanup_passed": True,
            "postflight_custody_passed": True,
            "terminal_classification": bounded["classification"],
            "manifest_sha256": hashes["manifest"],
            "result_sha256": hashes["result"],
            "closure_sha256": hashes["closure"],
            "evidence_archive_sha256": archive["bundle_sha256"],
        },
        "quality_gates": {
            "authority_receipt_verified": True,
            "private_classification_recomputed": CLASSIFICATION,
            "byte_exact_evidence_archive_verified": True,
            "failed_transform_top_cannot_be_privately_repaired": True,
            "all_six_stages_accepted": True,
            "restoration_passed": True,
            "cleanup_passed": True,
            "postflight_custody_passed": True,
            "historical_cib0_preserved": True,
            "historical_ck0_preserved": True,
            "no_disclosure": True,
            "bounded_metadata_only": True,
            "binding_2_unexecuted": True,
            "cross_binding_replication_locked": True,
            "binding_2_parent_dependence_locked": True,
            "causal_replication_across_bindings_locked": True,
            "general_two_parent_necessity_locked": True,
            "transfer_locked": True,
            "general_catalytic_inference_locked": True,
            "task_advantage_locked": True,
            "superiority_locked": True,
            "sota_locked": True,
            "broader_process_local_holostate_locked": True,
            "restart_persistence_locked": True,
            "deep_disabled": True,
            "automatic_promotion": False,
        },
        "verdict": "accept",
        "next_boundary": (
            "Publish only this bounded r3 binding-1 result. Binding-2 remains "
            "unauthorized until a fresh authority binds this committed publication."
        ),
    }
    _validate_record_shape(record)
    validate_disclosure_boundary(record, private_bindings)
    balanced.validate_metadata_only(record)
    _require(paths["receipt"].read_bytes() == receipt_before, "receipt changed during render")
    return record


def _iter_mappings(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for item in value.values():
            yield from _iter_mappings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_mappings(item)


def validate_ledger_record(
    repository: Path,
    rendered: Mapping[str, Any],
    *,
    require_predecessor_gate: bool = True,
) -> dict[str, Any]:
    repository = repository.resolve()
    _validate_record_shape(rendered)
    validate_disclosure_boundary(rendered)
    ledger = repository / "lab" / "results.jsonl"
    _require(ledger.is_file() and not ledger.is_symlink(), "results ledger is absent")
    matches: list[tuple[int, dict[str, Any], str]] = []
    legacy_matches: list[int] = []
    for line_number, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RankHeadV2PublicationError("results ledger is invalid") from exc
        if not isinstance(value, dict):
            continue
        configuration = value.get("configuration")
        metrics = value.get("metrics_after")
        if (
            isinstance(configuration, Mapping)
            and isinstance(metrics, Mapping)
            and configuration.get("run_id") == RUN_ID
            and metrics.get("terminal_classification") == CLASSIFICATION
        ):
            _require(
                line == canonical_json_text(value),
                "target publication line is not canonical JSON",
            )
            matches.append((line_number, value, line))
        for nested in _iter_mappings(value):
            if nested is value:
                continue
            if (
                nested.get("run_id") == RUN_ID
                and nested.get("terminal_classification") == CLASSIFICATION
            ):
                legacy_matches.append(line_number)
    _require(not legacy_matches, "legacy co-located rank-head-v2 publication is forbidden")
    _require(len(matches) == 1, "exactly one active rank-head-v2 publication is required")
    line_number, observed, line = matches[0]
    _require(observed == dict(rendered), "ledger record differs from independently rendered record")
    gate: dict[str, Any] | None = None
    if require_predecessor_gate:
        gate = run_design.require_binding_1_v2_terminal_visible(repository)
        _require(
            gate.get("publication", {}).get("layout") == "split-experiment-record",
            "binding-1 v2 predecessor-publication gate did not pass",
        )
    return {
        "status": "pass",
        "record_id": RECORD_ID,
        "layout": "split-experiment-record",
        "ledger_line": line_number,
        "record_sha256": balanced.sha256_bytes(line.encode("utf-8")),
        "predecessor_gate": gate,
    }


def validate_publication(repository: Path) -> dict[str, Any]:
    rendered = render_publication_record(repository)
    return validate_ledger_record(repository, rendered, require_predecessor_gate=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("render", "validate"))
    parser.add_argument("--repository", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository = Path(args.repository)
    try:
        if args.action == "render":
            print(canonical_json_text(render_publication_record(repository)))
        else:
            print(canonical_json_text(validate_publication(repository)))
    except (OSError, RankHeadV2PublicationError) as exc:
        print(canonical_json_text({"status": "fail", "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
