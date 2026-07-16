#!/usr/bin/env python3
"""Render and validate bounded rank-head v2 publications and adjudication.

This static-only tool derives every result fact from the completed binding-1
and binding-2 receipts, terminal evidence, private custody, committed
publication, and content-addressed archives. It contains no r2 result constants
and cannot create authority or execute the runtime.
"""
from __future__ import annotations

import argparse
import json
import hmac
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
PUBLICATION_SPECS: dict[str, dict[str, Any]] = {
    integration.BINDING_1_RUN_ID: {
        "record_id": RECORD_ID,
        "source_binding": "binding-1",
        "run_ordinal": 1,
    },
    integration.BINDING_2_RUN_ID: {
        "record_id": "neo-exp-0041",
        "source_binding": "binding-2",
        "run_ordinal": 2,
    },
}
ADJUDICATION_PATH = Path(
    "lab/ck0_balanced_opaque_rank_head_v2_cross_binding_adjudication_1.json"
)
ADJUDICATION_ID = "ck0-balanced-opaque-rank-head-v2-cross-binding-adjudication-1"
ADJUDICATION_STATUS = (
    "BALANCED_OPAQUE_RANK_HEAD_V2_END_TO_END_CROSS_BINDING_REPLICATION_SUPPORTED"
)
SUPPORTED_CLAIMS = (
    "END_TO_END_CROSS_BINDING_REPLICATION",
    "DETERMINISTIC_RANK_HEAD_EXTRACTION_REPLICATED_ACROSS_TWO_PRIVATE_BINDINGS",
)
LOCKED_CLAIMS = {
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


def _publication_spec(run_id: str) -> dict[str, Any]:
    spec = PUBLICATION_SPECS.get(run_id)
    if spec is None:
        raise RankHeadV2PublicationError("unknown rank-head-v2 publication run")
    return spec


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


def _evidence_paths(repository: Path, run_id: str = RUN_ID) -> dict[str, Path]:
    _publication_spec(run_id)
    root = repository / run_design.STATE_ROOT / run_id
    return {
        "receipt": authority.authority_receipt_path(repository, run_id),
        "manifest": root / "manifest.json",
        "result": root / "result.json",
        "closure": root / "closure.json",
        "run_lock": root / "run.lock",
    }


def _git_output(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        raise RankHeadV2PublicationError(
            f"git evidence query failed: {' '.join(args)}"
        )
    return completed.stdout.strip()


def _committed_predecessor_publication(
    repository: Path,
    authority_body: Mapping[str, Any],
) -> dict[str, Any]:
    commit = authority_body.get("predecessor_publication_commit")
    expected_sha256 = authority_body.get("predecessor_publication_record_sha256")
    _require(
        authority_body.get("predecessor_run_id") == integration.BINDING_1_RUN_ID
        and isinstance(commit, str)
        and balanced.GIT_COMMIT_RE.fullmatch(commit) is not None
        and isinstance(expected_sha256, str)
        and balanced.SHA256_RE.fullmatch(expected_sha256) is not None,
        "binding-2 predecessor publication identity is invalid",
    )
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    _require(
        ancestor.returncode == 0,
        "binding-1 publication commit is not an ancestor of the current checkout",
    )
    committed = _git_output(repository, "show", f"{commit}:lab/results.jsonl")
    matches: list[tuple[int, dict[str, Any], str]] = []
    for line_number, line in enumerate(committed.splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RankHeadV2PublicationError(
                "binding-1 committed publication ledger is invalid"
            ) from exc
        if not isinstance(record, dict):
            continue
        configuration = record.get("configuration")
        metrics = record.get("metrics_after")
        if (
            record.get("id") == PUBLICATION_SPECS[integration.BINDING_1_RUN_ID][
                "record_id"
            ]
            and isinstance(configuration, Mapping)
            and isinstance(metrics, Mapping)
            and configuration.get("run_id") == integration.BINDING_1_RUN_ID
            and metrics.get("terminal_classification") == CLASSIFICATION
        ):
            _require(
                line == canonical_json_text(record),
                "binding-1 committed publication is not canonical JSON",
            )
            matches.append((line_number, record, line))
    _require(
        len(matches) == 1,
        "binding-1 committed publication is not exactly one canonical record",
    )
    line_number, observed, line = matches[0]
    _require(
        balanced.sha256_bytes(line.encode("utf-8")) == expected_sha256,
        "binding-1 committed publication hash differs from binding-2 authority",
    )
    rendered = render_publication_record(repository, integration.BINDING_1_RUN_ID)
    _require(
        observed == rendered,
        "binding-1 committed publication differs from byte-exact regression render",
    )
    return {
        "run_id": integration.BINDING_1_RUN_ID,
        "record_id": PUBLICATION_SPECS[integration.BINDING_1_RUN_ID]["record_id"],
        "commit": commit,
        "line": line_number,
        "layout": "split-experiment-record",
        "record_sha256": expected_sha256,
    }


def _verified_authority(
    repository: Path,
    run_id: str = RUN_ID,
) -> dict[str, Any]:
    publication_spec = _publication_spec(run_id)
    try:
        verified = authority.verify_authority_receipt_for_run(
            repository,
            run_id,
            require_current_static=run_id == integration.BINDING_1_RUN_ID,
        )
    except (authority.RankHeadV2AuthorityError, OSError, json.JSONDecodeError) as exc:
        raise RankHeadV2PublicationError(
            "active rank-head-v2 authority receipt did not verify"
        ) from exc
    body = verified.get("authority")
    _require(isinstance(body, Mapping), "verified authority body is missing")
    _require(
        body.get("schema_version") == authority.AUTHORITY_SCHEMA_VERSION
        and body.get("run_id") == run_id
        and body.get("run_ordinal") == publication_spec["run_ordinal"]
        and body.get("source_binding") == publication_spec["source_binding"],
        "rank-head-v2 authority scope changed",
    )
    if run_id == integration.BINDING_1_RUN_ID:
        _require(
            body.get("predecessor_run_id") is None
            and body.get("predecessor_publication_commit") is None
            and body.get("predecessor_publication_record_sha256") is None,
            "binding-1 authority scope changed",
        )
    else:
        _committed_predecessor_publication(repository, body)
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
    run_id: str = RUN_ID,
) -> tuple[dict[str, Any], tuple[balanced.PrivateBinding, balanced.PrivateBinding]]:
    _publication_spec(run_id)
    spec = integration.run_spec(run_id)
    private = integration.runtime_private_from_repository(repository, run_id)
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


def _token_evidence(result: Mapping[str, Any]) -> dict[str, Any]:
    outcomes = [
        item
        for item in result.get("stage_outcomes", [])
        if isinstance(item, Mapping) and item.get("model_request_issued") is True
    ]
    _require(len(outcomes) == 5, "token evidence request count changed")
    transports = [item.get("transport", {}) for item in outcomes]
    _require(
        all(isinstance(item, Mapping) for item in transports),
        "token transport evidence is missing",
    )
    modes = {item.get("generated_token_evidence_mode") for item in transports}
    match_values = {item.get("completion_token_count_match") for item in transports}
    _require(
        modes == {"usage-plus-source-bound-terminal-eos"}
        and match_values <= {True, False}
        and len(match_values) == 1
        and all(
            item.get("terminal_stop_evidence", {}).get("observed") is True
            and item.get("terminal_stop_evidence", {}).get("stop_type") == "eos"
            for item in transports
        ),
        "token evidence qualification changed",
    )
    available = sum(
        int(item.get("nonempty_token_array_event_count", 0)) > 0
        for item in transports
    )
    unavailable = sum(
        item.get("full_generated_sequence_known") is False
        and int(item.get("empty_token_array_event_count", 0)) > 0
        for item in transports
    )
    return {
        "generated_token_array_observations_available": available,
        "generated_token_array_observations_unavailable": unavailable,
        "completion_token_count_match": next(iter(match_values)),
        "acceptance_basis": "authoritative-completion-usage-plus-source-bound-terminal-eos",
        "complete_generated_sequence_confirmation_available": all(
            item.get("full_generated_sequence_known") is True
            for item in transports
        ),
    }


def _resource_evidence(result: Mapping[str, Any]) -> dict[str, Any]:
    outcomes = [
        item for item in result.get("stage_outcomes", []) if isinstance(item, Mapping)
    ]
    _require(len(outcomes) == 6, "resource evidence stage count changed")
    samples: list[Mapping[str, Any]] = []
    for outcome in outcomes:
        resources = outcome.get("resources", {})
        before = resources.get("before") if isinstance(resources, Mapping) else None
        after = resources.get("after") if isinstance(resources, Mapping) else None
        _require(
            isinstance(before, Mapping) and isinstance(after, Mapping),
            "resource boundary evidence is missing",
        )
        samples.extend((before, after))
    private_bytes = [item.get("host_private_bytes") for item in samples]
    _require(
        all(type(item) is int and item >= 0 for item in private_bytes)
        and all(type(item.get("host_private_ceiling_exceeded")) is bool for item in samples),
        "resource boundary measurements are malformed",
    )
    observation_states = sorted({str(item.get("observation_state")) for item in samples})
    readiness = result.get("readiness", {})
    _require(
        isinstance(readiness, Mapping)
        and type(readiness.get("private_bytes")) is int
        and isinstance(readiness.get("readiness_seconds"), (int, float)),
        "resource readiness evidence is malformed",
    )
    unavailable = observation_states == ["unavailable"]
    return {
        "readiness_seconds": readiness["readiness_seconds"],
        "readiness_private_bytes": readiness["private_bytes"],
        "maximum_host_private_bytes": max(private_bytes),
        "measured_resource_ceiling_breach": any(
            item.get("host_private_ceiling_exceeded") is True for item in samples
        ),
        "per_boundary_observation_states": observation_states,
        "wddm_telemetry": "unavailable-advisory" if unavailable else "available-advisory",
        "wddm_or_gpu_memory_peak_claimed": False,
    }


def _private_independence_facts(
    repository: Path,
    authority_bodies: Mapping[str, Mapping[str, Any]],
) -> dict[str, bool]:
    source_1 = balanced._private_binding_from_repository(repository, balanced.BINDING_1)
    source_2 = balanced._private_binding_from_repository(repository, balanced.BINDING_2)
    private_1 = integration.runtime_private_from_repository(
        repository, integration.BINDING_1_RUN_ID
    )
    private_2 = integration.runtime_private_from_repository(
        repository, integration.BINDING_2_RUN_ID
    )
    roots_differ = (
        balanced.private_secret_path(repository, balanced.BINDING_1).resolve()
        != balanced.private_secret_path(repository, balanced.BINDING_2).resolve()
    )
    distinct_custody = (
        roots_differ
        and source_1.configuration is balanced.BINDING_1
        and source_2.configuration is balanced.BINDING_2
        and source_1.secret_commitment != source_2.secret_commitment
        and source_1.creation_receipt_commitment
        != source_2.creation_receipt_commitment
    )
    body_1 = authority_bodies[integration.BINDING_1_RUN_ID]
    body_2 = authority_bodies[integration.BINDING_2_RUN_ID]
    independent_run_keys = (
        body_1.get("run_key_commitment") != body_2.get("run_key_commitment")
        and not hmac.compare_digest(
            private_1.run_key(integration.BINDING_1_RUN_ID),
            private_2.run_key(integration.BINDING_2_RUN_ID),
        )
    )
    _require(distinct_custody, "the two private binding custody roots are not distinct")
    _require(independent_run_keys, "the two completed runs are not independently keyed")
    return {
        "distinct_private_binding_custody": True,
        "independent_run_keys": True,
    }


def _verified_archive(
    repository: Path,
    protected_commit: str,
    hashes: Mapping[str, str],
    run_id: str = RUN_ID,
) -> dict[str, Any]:
    _publication_spec(run_id)
    root = repository / evidence.ARCHIVE_ROOT / run_id
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
            bundle.get("run_id") == run_id
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


def _validate_record_shape(
    record: Mapping[str, Any],
    run_id: str = RUN_ID,
) -> None:
    publication_spec = _publication_spec(run_id)
    _require(
        set(record) == set(TOP_LEVEL_KEYS) and len(record) == len(TOP_LEVEL_KEYS),
        "publication top-level split layout changed",
    )
    configuration = record.get("configuration")
    metrics = record.get("metrics_after")
    gates = record.get("quality_gates")
    _require(
        record.get("id") == publication_spec["record_id"],
        "publication record ID changed",
    )
    _require(isinstance(configuration, Mapping), "publication configuration is missing")
    _require(isinstance(metrics, Mapping), "publication metrics-after is missing")
    _require(configuration.get("run_id") == run_id, "publication run ID changed")
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


def render_publication_record(
    repository: Path,
    run_id: str = RUN_ID,
) -> dict[str, Any]:
    repository = repository.resolve()
    publication_spec = _publication_spec(run_id)
    paths = _evidence_paths(repository, run_id)
    receipt_before = paths["receipt"].read_bytes() if paths["receipt"].is_file() else None
    authority_evidence = _verified_authority(repository, run_id)
    _require(receipt_before is not None, "consumed authority receipt is missing")
    for name in ("receipt", "manifest", "result", "closure"):
        _require(_is_ignored(repository, paths[name]), f"{name} evidence is not ignored")
    _require(
        not paths["run_lock"].exists() and not paths["run_lock"].is_symlink(),
        "rank-head-v2 run lock exists",
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
        manifest.get("run_id") == run_id
        and manifest.get("run_ordinal") == publication_spec["run_ordinal"]
        and manifest.get("source_binding") == publication_spec["source_binding"]
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
        result.get("run_id") == run_id
        and result.get("run_ordinal") == publication_spec["run_ordinal"]
        and result.get("source_binding") == publication_spec["source_binding"]
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
        closure.get("run_id") == run_id
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
    restoration_receipt = restoration.get("receipt_sha256")
    restoration_body = {
        key: value
        for key, value in restoration.items()
        if key not in {"passed", "receipt_sha256"}
    }
    _require(
        isinstance(restoration_receipt, str)
        and balanced.SHA256_RE.fullmatch(restoration_receipt) is not None
        and balanced.json_sha256(restoration_body) == restoration_receipt,
        "restoration receipt binding changed",
    )
    request_outcomes = [
        item
        for item in result.get("stage_outcomes", [])
        if isinstance(item, Mapping) and item.get("model_request_issued") is True
    ]
    _require(
        len(request_outcomes) == 5
        and all(
            isinstance(item.get("cache"), Mapping)
            and item["cache"].get("admitted") is True
            for item in request_outcomes
        ),
        "five-request cache admission changed",
    )
    bounded, private_bindings = _private_reconstruction(
        repository,
        result,
        run_projection,
        run_id,
    )
    archive = _verified_archive(
        repository,
        str(body["authorized_commit"]),
        hashes,
        run_id,
    )
    configuration: dict[str, Any] = {
        "run_id": run_id,
        "profile_id": f"{v2.DESIGN_ID}:{publication_spec['source_binding']}",
        "source_binding": publication_spec["source_binding"],
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
    }
    metrics_after: dict[str, Any] = {
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
    }
    if run_id == integration.BINDING_1_RUN_ID:
        checkpoint = "2-Catalytic-Kernel-0-balanced-rank-head-v2-binding-1-full-information"
        hypothesis = (
            "Under deterministic-rank-head v2 geometry, controller-native rank-zero "
            "extraction on binding-1 completes visibly without private correspondence "
            "influencing selection."
        )
        intervention = (
            "Publish only the consumed one-shot binding-1 r3 terminal result after "
            "independent receipt, raw-evidence, private, and archive verification."
        )
        metrics_before = {
            "status": "static-preregistered",
            "binding_2_executed": False,
            "automatic_follow_on": False,
        }
        quality_gates = {
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
        }
        next_boundary = (
            "Publish only this bounded r3 binding-1 result. Binding-2 remains "
            "unauthorized until a fresh authority binds this committed publication."
        )
    else:
        predecessor = _committed_predecessor_publication(repository, body)
        authority_1 = _verified_authority(repository, integration.BINDING_1_RUN_ID)
        independence = _private_independence_facts(
            repository,
            {
                integration.BINDING_1_RUN_ID: authority_1["authority"],
                integration.BINDING_2_RUN_ID: body,
            },
        )
        configuration.update(
            {
                "binary_sha256": body["binary_sha256"],
                "run_key_commitment": body["run_key_commitment"],
                "predecessor_run_id": predecessor["run_id"],
                "predecessor_publication_commit": predecessor["commit"],
                "predecessor_publication_record_id": predecessor["record_id"],
                "predecessor_publication_record_sha256": predecessor["record_sha256"],
            }
        )
        metrics_after.update(
            {
                "lease_accounting": {
                    "lease_count": 5,
                    "maximum_concurrent_leases": 1,
                    "active_leases": 0,
                },
                "restoration_receipt_sha256": restoration_receipt,
                "token_evidence": _token_evidence(result),
                "resource_evidence": _resource_evidence(result),
            }
        )
        checkpoint = "2-Catalytic-Kernel-0-balanced-rank-head-v2-binding-2-full-information"
        hypothesis = (
            "Under the frozen deterministic-rank-head v2 law, a fresh independently "
            "keyed private binding also completes visibly with rank-zero selection "
            "frozen before private mapping."
        )
        intervention = (
            "Publish only the consumed one-shot binding-2 terminal result after exact "
            "predecessor, authority, raw-evidence, private, and archive verification."
        )
        metrics_before = {
            "status": "static-preregistered",
            "predecessor_publication_record_id": predecessor["record_id"],
            "predecessor_publication_record_sha256": predecessor["record_sha256"],
            "automatic_follow_on": False,
        }
        quality_gates = {
            "authority_receipt_verified": True,
            "predecessor_publication_verified": True,
            "private_classification_recomputed": CLASSIFICATION,
            "byte_exact_evidence_archive_verified": True,
            "all_six_stages_accepted": True,
            "all_five_cache_admissions_passed": True,
            "restoration_passed": True,
            "cleanup_passed": True,
            "postflight_custody_passed": True,
            "historical_cib0_preserved": True,
            "historical_ck0_preserved": True,
            "distinct_private_binding_custody": independence[
                "distinct_private_binding_custody"
            ],
            "independent_run_keys": independence["independent_run_keys"],
            "no_disclosure": True,
            "bounded_metadata_only": True,
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
        }
        next_boundary = (
            "Design the minimum cross-binding causal test required to determine "
            "whether parent dependence replicates under binding-2, without rerunning "
            "either completed full-information experiment."
        )
    record: dict[str, Any] = {
        "id": publication_spec["record_id"],
        "checkpoint": checkpoint,
        "hypothesis": hypothesis,
        "intervention": intervention,
        "baseline_commit": body["authorized_commit"],
        "candidate_commit": None,
        "model_hash": body["model_sha256"],
        "configuration": configuration,
        "metrics_before": metrics_before,
        "metrics_after": metrics_after,
        "quality_gates": quality_gates,
        "verdict": "accept",
        "next_boundary": next_boundary,
    }
    _validate_record_shape(record, run_id)
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
    run_id: str = RUN_ID,
    require_predecessor_gate: bool = True,
) -> dict[str, Any]:
    repository = repository.resolve()
    publication_spec = _publication_spec(run_id)
    _validate_record_shape(rendered, run_id)
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
            and configuration.get("run_id") == run_id
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
                nested.get("run_id") == run_id
                and nested.get("terminal_classification") == CLASSIFICATION
            ):
                legacy_matches.append(line_number)
    _require(not legacy_matches, "legacy co-located rank-head-v2 publication is forbidden")
    _require(
        len(matches) == 1,
        "exactly one selected rank-head-v2 publication is required",
    )
    line_number, observed, line = matches[0]
    _require(observed == dict(rendered), "ledger record differs from independently rendered record")
    gate: dict[str, Any] | None = None
    if require_predecessor_gate:
        binding_2_receipt = authority.authority_receipt_path(
            repository,
            integration.BINDING_2_RUN_ID,
        )
        if binding_2_receipt.is_file():
            binding_2_authority = _verified_authority(
                repository,
                integration.BINDING_2_RUN_ID,
            )
            gate = _committed_predecessor_publication(
                repository,
                binding_2_authority["authority"],
            )
        else:
            gate = run_design.require_binding_1_v2_terminal_visible(repository)
            _require(
                gate.get("publication", {}).get("layout")
                == "split-experiment-record",
                "binding-1 v2 predecessor-publication gate did not pass",
            )
    return {
        "status": "pass",
        "record_id": publication_spec["record_id"],
        "layout": "split-experiment-record",
        "ledger_line": line_number,
        "record_sha256": balanced.sha256_bytes(line.encode("utf-8")),
        "predecessor_gate": gate,
    }


def validate_publication(
    repository: Path,
    run_id: str = RUN_ID,
) -> dict[str, Any]:
    rendered = render_publication_record(repository, run_id)
    return validate_ledger_record(
        repository,
        rendered,
        run_id=run_id,
        require_predecessor_gate=True,
    )


def _binding_adjudication_summary(
    record: Mapping[str, Any],
    ledger: Mapping[str, Any],
) -> dict[str, Any]:
    configuration = record["configuration"]
    metrics = record["metrics_after"]
    extraction = metrics["deterministic_extraction"]
    transform = metrics["transform"]
    return {
        "source_binding": configuration["source_binding"],
        "run_id": configuration["run_id"],
        "publication_record_id": record["id"],
        "publication_record_sha256": ledger["record_sha256"],
        "publication_ledger_line": ledger["ledger_line"],
        "authority_receipt_sha256": configuration["authority_receipt_sha256"],
        "manifest_sha256": metrics["manifest_sha256"],
        "result_sha256": metrics["result_sha256"],
        "closure_sha256": metrics["closure_sha256"],
        "evidence_archive_sha256": metrics["evidence_archive_sha256"],
        "terminal_classification": metrics["terminal_classification"],
        "completed_logical_stages": metrics["completed_logical_stages"],
        "completed_model_responses": metrics["completed_model_responses"],
        "all_model_responses_accepted": all(
            item.get("status") == "accepted" for item in metrics["request_usage"]
        ),
        "transform_operator": transform["operator"],
        "transform_artifact_commitment": transform["artifact_commitment"],
        "transform_artifact_verified": True,
        "transform_ranking_length": transform["ranking_length"],
        "transform_top_matched_own_private_singleton": transform[
            "top_matched_private_singleton"
        ],
        "selected_rank": extraction["selected_rank"],
        "selection_frozen_before_private_mapping": extraction[
            "selection_frozen_before_private_mapping"
        ],
        "selected_own_private_singleton": extraction["selected_private_singleton"],
        "private_public_score": extraction["full_public_score"],
        "private_public_total": extraction["full_public_total"],
        "restoration_passed": metrics["restoration_passed"],
        "cleanup_passed": metrics["cleanup_passed"],
        "archive_verified": True,
        "canonical_publication_record_verified": True,
    }


def render_cross_binding_adjudication(repository: Path) -> dict[str, Any]:
    repository = repository.resolve()
    records = {
        run_id: render_publication_record(repository, run_id)
        for run_id in PUBLICATION_SPECS
    }
    ledgers = {
        run_id: validate_ledger_record(
            repository,
            record,
            run_id=run_id,
            require_predecessor_gate=True,
        )
        for run_id, record in records.items()
    }
    authorities = {
        run_id: _verified_authority(repository, run_id)["authority"]
        for run_id in PUBLICATION_SPECS
    }
    independence = _private_independence_facts(repository, authorities)
    binding_1 = records[integration.BINDING_1_RUN_ID]
    binding_2 = records[integration.BINDING_2_RUN_ID]
    shared_fields = {
        "model_sha256": binding_1["model_hash"],
        "binary_sha256": authorities[integration.BINDING_1_RUN_ID]["binary_sha256"],
        "carrier_id": binding_1["configuration"]["carrier_id"],
        "carrier_root_sha256": binding_1["configuration"]["carrier_root_sha256"],
        "implementation_binding_sha256": binding_1["configuration"]
        ["implementation_binding_sha256"],
        "run_design_artifact_sha256": binding_1["configuration"]
        ["run_design_artifact_sha256"],
        "run_design_document_sha256": binding_1["configuration"]
        ["run_design_document_sha256"],
        "static_design_contract_sha256": binding_1["configuration"]
        ["static_design_contract_sha256"],
    }
    _require(
        binding_2["model_hash"] == shared_fields["model_sha256"]
        and authorities[integration.BINDING_2_RUN_ID]["binary_sha256"]
        == shared_fields["binary_sha256"]
        and all(
            binding_2["configuration"][field] == value
            for field, value in shared_fields.items()
            if field not in {"model_sha256", "binary_sha256"}
        ),
        "cross-binding frozen implementation identity changed",
    )
    summaries = [
        _binding_adjudication_summary(records[run_id], ledgers[run_id])
        for run_id in PUBLICATION_SPECS
    ]
    invariants = {
        "same_frozen_model_binary_carrier_and_runtime_law": True,
        "two_distinct_private_binding_custody_roots": independence[
            "distinct_private_binding_custody"
        ],
        "two_independent_run_keys": independence["independent_run_keys"],
        "both_full_information_runs_completed": all(
            item["terminal_classification"] == CLASSIFICATION for item in summaries
        ),
        "both_completed_six_stages_and_five_accepted_model_responses": all(
            item["completed_logical_stages"] == 6
            and item["completed_model_responses"] == 5
            and item["all_model_responses_accepted"] is True
            for item in summaries
        ),
        "both_transform_artifacts_verified_and_heads_matched_own_private_singletons": all(
            item["transform_operator"] == "reconcile"
            and item["transform_artifact_verified"] is True
            and item["transform_ranking_length"] == 3
            and item["transform_top_matched_own_private_singleton"] is True
            for item in summaries
        ),
        "both_rank_zero_selections_frozen_before_private_mapping": all(
            item["selected_rank"] == 0
            and item["selection_frozen_before_private_mapping"] is True
            for item in summaries
        ),
        "both_extractions_selected_own_private_singletons_at_five_of_five": all(
            item["selected_own_private_singleton"] is True
            and item["private_public_score"] == 5
            and item["private_public_total"] == 5
            for item in summaries
        ),
        "both_restoration_and_cleanup_checks_passed": all(
            item["restoration_passed"] is True and item["cleanup_passed"] is True
            for item in summaries
        ),
        "both_archives_and_canonical_publications_verified": all(
            item["archive_verified"] is True
            and item["canonical_publication_record_verified"] is True
            for item in summaries
        ),
    }
    _require(all(value is True for value in invariants.values()), "replication invariant failed")
    document: dict[str, Any] = {
        "schema_version": 1,
        "adjudication_id": ADJUDICATION_ID,
        "status": ADJUDICATION_STATUS,
        "scope": (
            "The frozen full-information rank-head v2 mechanism completed visibly "
            "under two independently keyed private bindings."
        ),
        "shared_frozen_identity": shared_fields,
        "binding_evidence": summaries,
        "cross_binding_invariants": invariants,
        "supported_claims": list(SUPPORTED_CLAIMS),
        "locked_claims": dict(LOCKED_CLAIMS),
        "next_boundary": (
            "Design the minimum cross-binding causal test required to determine "
            "whether parent dependence replicates under binding-2, without rerunning "
            "either completed full-information experiment."
        ),
    }
    _validate_adjudication_shape(document)
    private_bindings = (
        balanced._private_binding_from_repository(repository, balanced.BINDING_1),
        balanced._private_binding_from_repository(repository, balanced.BINDING_2),
    )
    validate_disclosure_boundary(document, private_bindings)
    balanced.validate_metadata_only(document)
    return document


def _validate_adjudication_shape(document: Mapping[str, Any]) -> None:
    expected_keys = {
        "schema_version",
        "adjudication_id",
        "status",
        "scope",
        "shared_frozen_identity",
        "binding_evidence",
        "cross_binding_invariants",
        "supported_claims",
        "locked_claims",
        "next_boundary",
    }
    _require(set(document) == expected_keys, "adjudication layout changed")
    _require(
        document.get("schema_version") == 1
        and document.get("adjudication_id") == ADJUDICATION_ID
        and document.get("status") == ADJUDICATION_STATUS,
        "adjudication identity changed",
    )
    _require(
        document.get("supported_claims") == list(SUPPORTED_CLAIMS)
        and document.get("locked_claims") == LOCKED_CLAIMS,
        "adjudication claim boundary changed",
    )
    bindings = document.get("binding_evidence")
    invariants = document.get("cross_binding_invariants")
    _require(
        isinstance(bindings, list)
        and len(bindings) == 2
        and isinstance(invariants, Mapping)
        and len(invariants) == 10
        and all(value is True for value in invariants.values()),
        "adjudication replication evidence is incomplete",
    )


def validate_cross_binding_adjudication(repository: Path) -> dict[str, Any]:
    repository = repository.resolve()
    rendered = render_cross_binding_adjudication(repository)
    path = repository / ADJUDICATION_PATH
    _require(
        path.is_file()
        and not path.is_symlink()
        and not balanced._is_reparse(path),
        "cross-binding adjudication artifact is absent or unsafe",
    )
    expected = canonical_json_text(rendered) + "\n"
    observed = path.read_text(encoding="utf-8")
    _require(observed == expected, "adjudication differs from independent render")
    return {
        "status": "pass",
        "adjudication_id": ADJUDICATION_ID,
        "adjudication_status": ADJUDICATION_STATUS,
        "artifact": ADJUDICATION_PATH.as_posix(),
        "artifact_sha256": balanced.sha256_bytes(observed.encode("utf-8")),
        "supported_claims": list(SUPPORTED_CLAIMS),
        "locked_claims": dict(LOCKED_CLAIMS),
        "records": [
            {
                "run_id": item["run_id"],
                "record_id": item["publication_record_id"],
                "record_sha256": item["publication_record_sha256"],
                "ledger_line": item["publication_ledger_line"],
            }
            for item in rendered["binding_evidence"]
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=(
            "render",
            "validate",
            "render-adjudication",
            "validate-adjudication",
        ),
    )
    parser.add_argument("--repository", required=True)
    parser.add_argument(
        "--run-id",
        choices=tuple(PUBLICATION_SPECS),
        default=RUN_ID,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository = Path(args.repository)
    try:
        if args.action == "render":
            output = render_publication_record(repository, args.run_id)
        elif args.action == "validate":
            output = validate_publication(repository, args.run_id)
        elif args.action == "render-adjudication":
            output = render_cross_binding_adjudication(repository)
        else:
            output = validate_cross_binding_adjudication(repository)
        print(canonical_json_text(output))
    except (OSError, RankHeadV2PublicationError) as exc:
        print(canonical_json_text({"status": "fail", "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
