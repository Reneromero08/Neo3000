#!/usr/bin/env python3
"""Statically adjudicate and publish the completed position-seed crossover."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import catalytic_kernel_0_balanced_rank_head_v2_position_seed_crossover as crossover
import catalytic_kernel_0_balanced_rank_head_v2_position_seed_crossover_scientific as scientific


class PositionSeedAdjudicationError(ValueError):
    """The archived panel cannot support the bounded publication."""


SOURCE_COMMIT = "27a5188d1aae8fb0944875865a44cb4583fd0352"
ARTIFACT_PATH = Path(
    "lab/ck0_balanced_opaque_rank_head_v2_position_seed_crossover_adjudication_1.json"
)
RESULTS_PATH = Path("lab/results.jsonl")
ADJUDICATION_ID = (
    "ck0-balanced-opaque-rank-head-v2-position-seed-crossover-adjudication-1"
)
RECORD_ID = "neo-exp-0042"

EXPECTED_HASHES = {
    "receipt": "7EE9A98A78100E6675A659A861D899E0AE95FD2FAF65D87449F28EC9BDE804A7",
    "manifest": "C47B16C6F6E6C8EFFE42F5AB7EDD5DC65ED5A327DCC9BD2E96FAB06105DF86EC",
    "result": "008D4FEFE24D6CB4A846A76E832A892BCBBF134F1A1C951FCDA55F0624C0E0FB",
    "closure": "60077B27F2FFAE7FBC02B7FB7B8EC0B803F9086716611A84C88CD4F6AC8D633D",
    "journal": "1BB6E91E9D9E0E767E78D13C19FFCE3F952166A5A914DA2EBB9394E00A2F3100",
    "journal_head": "F6A0CC59A696D818FCFDF5357AB5534F1BD35377C6AB36B870DDC2AACCD7F2FA",
    "archive": "BC9404292F54F5597E0D7BA3AEBC83EF6A95E9C19708164994D515980AEB6B1B",
}
EXPECTED_CAPTURE_HASHES = {
    "P0-S0-full-information": "2FF73937EBC47DC54EAA372F832FDAB8A04DF7AB2D5B579080FE8E19EB4EF7C6",
    "P0-S0-delete-parent-0": "EA396996FE535D8DBCCE28B36357584FEA24925841EC1569550E673FE63EB6CE",
    "P0-S0-delete-parent-1": "10F922CA899B75F6606439D31F18441F5952B06EE09B266A7B24D311E3382B7E",
    "P0-S1-full-information": "E69C8882AB6D1E13AEEC9EE3443871C41372EA15836BE6E5378451B343B3E95A",
    "P0-S1-delete-parent-0": "89B5F7327E999FF443B793534467B4C917F5D8963703127D1D7EE283EDD56570",
    "P0-S1-delete-parent-1": "7EE0ADA96246A57614B7796F070AA1E01F80E12D3B1377EFB87D25CFFD433326",
    "P1-S0-full-information": "C3C323BF83E28E3132A26405D32CB6FDD0EC93B85E2BE105FEFDD5525EFD4D52",
    "P1-S0-delete-parent-0": "8AA1CE14CD2AE1B214DA0AB9B0FE4EB5C12C0D85F7F84D76B8B27A368F2B8CE2",
    "P1-S0-delete-parent-1": "147FEDC09D82E8E84CF870AFBD57D58EE817322EE300D4956F366CF82D6E1AA8",
    "P1-S1-full-information": "A87374FE5D2D7FFAF8D5C89D7374A45EA3EC55C2B4A85799ABF8D8B894EBD408",
    "P1-S1-delete-parent-0": "1A1D96CB1EA790106D5BCACCEB0DDA8B1C6EDEDE989ED2BA4E27C300263D734F",
    "P1-S1-delete-parent-1": "2F52628E4B1A84CFA821A7F8998BC42A92B8DB859C686AEF9AB61243E7E90D5C",
}

SUPPORTED_CLAIMS = (
    "SINGLETON_PRESENTATION_POSITION_EFFECT_SUPPORTED",
    "PARENT_INFORMATION_DEPENDENCE_IS_SINGLETON_PRESENTATION_POSITION_CONDITIONAL_WITHIN_MATCHED_BINDING",
    "JOINT_PARENT_INFORMATION_OVERCOMES_UNFAVORABLE_SINGLETON_PRESENTATION_POSITION_ACROSS_TWO_FIXED_SEEDS",
)
LOCKED_CLAIMS = {
    "POSITION_INDEPENDENT_BILATERAL_DEPENDENCE": "LOCKED",
    "GENERAL_TWO_PARENT_NECESSITY": "LOCKED",
    "CROSS_BINDING_GENERALIZATION_OF_THIS_CROSSOVER": "LOCKED",
    "GENERAL_CATALYTIC_INFERENCE": "LOCKED",
    "TRANSFER": "LOCKED",
    "TASK_ADVANTAGE": "LOCKED",
    "SUPERIORITY": "LOCKED",
    "SOTA": "LOCKED",
    "BROADER_PROCESS_LOCAL_HOLOSTATE": "LOCKED",
    "RESTART_PERSISTENCE": "LOCKED",
    "DEEP": "DISABLED",
    "automatic_promotion": False,
}
FORBIDDEN_KEYS = frozenset(
    {
        "alias_map",
        "alias_mapping",
        "candidate_alias",
        "cross_binding_correspondence",
        "private_root",
        "ranking",
        "raw_authority_id",
        "raw_response",
        "run_key",
        "secret",
        "selection_seed",
        "support_aliases",
    }
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


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PositionSeedAdjudicationError(message)


def _iter_values(value: Any, key: str | None = None) -> Iterable[tuple[str | None, Any]]:
    if isinstance(value, Mapping):
        for nested_key, nested_value in value.items():
            yield from _iter_values(nested_value, str(nested_key))
    elif isinstance(value, list):
        for nested_value in value:
            yield from _iter_values(nested_value, key)
    else:
        yield key, value


def validate_disclosure_boundary(value: Mapping[str, Any]) -> None:
    crossover._assert_public_no_smuggle(value)
    for key, _nested in _iter_values(value):
        if key is not None and key.casefold() in FORBIDDEN_KEYS:
            raise PositionSeedAdjudicationError(
                f"publication disclosure contains forbidden field: {key}"
            )


def _outcome_projection(outcome: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "private_singleton_recovered": outcome.get("selected_private_singleton") is True,
        "public_score": int(outcome.get("private_public_score", -1)),
        "public_total": int(outcome.get("private_public_total", -1)),
        "selected_rank": int(outcome.get("selected_rank", -1)),
        "selection_frozen_before_private_mapping": (
            outcome.get("selection_frozen_before_private_mapping") is True
        ),
    }


def _matrix(outcomes: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    matrix = []
    for presentation in crossover.PRESENTATIONS:
        for seed_block, seed in crossover.SEED_BLOCKS.items():
            cell_id = f"{presentation}-{seed_block}"
            matrix.append(
                {
                    "cell_id": cell_id,
                    "presentation": presentation,
                    "presentation_condition": (
                        "singleton-first" if presentation == "P0" else "singleton-last"
                    ),
                    "seed_block": seed_block,
                    "seed": seed,
                    "full_information": _outcome_projection(
                        outcomes[f"{cell_id}-full-information"]
                    ),
                    "delete_parent_0": _outcome_projection(
                        outcomes[f"{cell_id}-delete-parent-0"]
                    ),
                    "delete_parent_1": _outcome_projection(
                        outcomes[f"{cell_id}-delete-parent-1"]
                    ),
                }
            )
    return matrix


def _require_exact_scientific_pattern(matrix: list[Mapping[str, Any]]) -> None:
    _require(len(matrix) == 4, "the crossover matrix is incomplete")
    for cell in matrix:
        full = cell["full_information"]
        delete_0 = cell["delete_parent_0"]
        delete_1 = cell["delete_parent_1"]
        for outcome in (full, delete_0, delete_1):
            _require(
                outcome["selected_rank"] == 0
                and outcome["selection_frozen_before_private_mapping"] is True
                and outcome["public_total"] == 5,
                "rank-head extraction law changed",
            )
        _require(
            full["private_singleton_recovered"] is True
            and full["public_score"] == 5,
            "a full-information baseline is invalid",
        )
        expected_recovered = cell["presentation"] == "P0"
        expected_score = 5 if expected_recovered else 3
        for outcome in (delete_0, delete_1):
            _require(
                outcome["private_singleton_recovered"] is expected_recovered
                and outcome["public_score"] == expected_score,
                "the observed position-conditional deletion pattern changed",
            )


def _verified_replay(repository: Path) -> dict[str, Any]:
    paths = crossover.state_paths(repository)
    for name in ("receipt", "manifest", "result", "closure", "journal"):
        data = crossover._require_regular(paths[name], name, maximum=8 * 1024 * 1024)
        _require(crossover.sha256_bytes(data) == EXPECTED_HASHES[name], f"{name} hash changed")

    archive = crossover._verify_existing_archive(repository, EXPECTED_HASHES["archive"])
    _require(archive["file_count"] == 17, "archive inventory changed")
    archive_root = (
        repository
        / crossover.ARCHIVE_ROOT
        / crossover.DESIGN_ID
        / EXPECTED_HASHES["archive"]
    )
    for name, member in {
        "receipt": "authority-receipt.json",
        "manifest": "manifest.json",
        "result": "result.json",
        "closure": "closure.json",
    }.items():
        _require(
            paths[name].read_bytes() == (archive_root / member).read_bytes(),
            f"live and archived {name} differ",
        )

    root, private = crossover._load_private(repository)
    key = crossover._experiment_key(root)
    receipt = crossover.verify_authority_receipt(repository)
    authority = receipt.get("authority")
    _require(isinstance(authority, Mapping), "authority body is missing")
    _require(
        authority.get("authorized_commit") == SOURCE_COMMIT
        and receipt.get("consuming_commit") == SOURCE_COMMIT
        and authority.get("maximum_total_generations") == 12
        and authority.get("maximum_generations_per_cell_arm") == 1,
        "consumed authority scope changed",
    )
    events = crossover.read_journal(paths["journal"], key)
    _require(
        len(events) == 52 and events[-1]["event_sha256"] == EXPECTED_HASHES["journal_head"],
        "authenticated journal boundary changed",
    )
    started = {
        event["request_id"]: event
        for event in events
        if event["state"] == "request-started"
    }
    _require(set(started) == set(crossover.REQUEST_IDS), "request-start journal is incomplete")

    outcomes: dict[str, dict[str, Any]] = {}
    capture_hashes: dict[str, str] = {}
    for request_id in crossover.REQUEST_IDS:
        live_path = paths[f"capture-{request_id}"]
        archive_path = archive_root / "captures" / f"{request_id}.json"
        _require(
            live_path.read_bytes() == archive_path.read_bytes(),
            f"live and archived capture differ: {request_id}",
        )
        capture_sha256 = crossover.sha256_bytes(archive_path.read_bytes())
        _require(
            capture_sha256 == EXPECTED_CAPTURE_HASHES[request_id],
            f"capture hash changed: {request_id}",
        )
        capture = scientific.verify_capture(
            archive_path,
            experiment_key=key,
            request_id=request_id,
            model_request_sha256=authority["request_sha256"][request_id],
        )
        outcomes[request_id] = crossover._capture_outcome(
            repository,
            private,
            request_id,
            capture,
            int(started[request_id]["facts"]["rendered_prompt_tokens"]),
        )
        capture_hashes[request_id] = capture_sha256

    panel = crossover.adjudicate_outcomes(outcomes)
    terminal_result = json.loads(paths["result"].read_bytes())
    _require(
        terminal_result.get("request_outcomes")
        == [outcomes[request_id] for request_id in crossover.REQUEST_IDS]
        and terminal_result.get("panel_adjudication") == panel,
        "zero-contact replay differs from the terminal result",
    )
    _require(
        panel.get("supported_panel_classifications")
        == ["SINGLETON_PRESENTATION_POSITION_EFFECT_SUPPORTED"],
        "controller panel classification changed",
    )
    matrix = _matrix(outcomes)
    _require_exact_scientific_pattern(matrix)
    return {
        "authority_id_sha256": authority["authority_id_sha256"],
        "capture_sha256": capture_hashes,
        "event_count": len(events),
        "matrix": matrix,
        "panel": panel,
    }


def render_adjudication(repository: Path) -> dict[str, Any]:
    replay = _verified_replay(repository)
    artifact = {
        "schema_version": 1,
        "adjudication_id": ADJUDICATION_ID,
        "design_id": crossover.DESIGN_ID,
        "status": "POSITION_CONDITIONAL_PARENT_INFORMATION_EFFECT_SUPPORTED",
        "scope": {
            "matched_private_binding_only": True,
            "transform_causal_core_only": True,
            "complete_new_borrow_transform_extract_restore_cycle_tested": False,
            "fixed_seed_count": 2,
            "presentation_count": 2,
            "arms_per_cell": 3,
        },
        "source_execution": {
            "protected_commit": SOURCE_COMMIT,
            "authority_id_sha256": replay["authority_id_sha256"],
            "authority_receipt_sha256": EXPECTED_HASHES["receipt"],
            "manifest_sha256": EXPECTED_HASHES["manifest"],
            "result_sha256": EXPECTED_HASHES["result"],
            "closure_sha256": EXPECTED_HASHES["closure"],
            "journal_sha256": EXPECTED_HASHES["journal"],
            "journal_head_sha256": EXPECTED_HASHES["journal_head"],
            "evidence_archive_sha256": EXPECTED_HASHES["archive"],
            "archive_file_count": 17,
            "capture_sha256": replay["capture_sha256"],
            "completed_model_generations": 12,
            "retry_count": 0,
            "automatic_follow_on": False,
        },
        "zero_contact_reconstruction": {
            "archive_verified": True,
            "authenticated_captures_verified": 12,
            "authenticated_journal_events_verified": replay["event_count"],
            "request_outcomes_replayed": 12,
            "terminal_result_exact_match": True,
            "controller_panel_exact_match": True,
            "model_requests_issued": 0,
            "sidecar_launches": 0,
            "model_generations": 0,
        },
        "observed_matrix": replay["matrix"],
        "supported_claims": list(SUPPORTED_CLAIMS),
        "scientific_interpretation": {
            "full_information_recovered_under_both_presentations_and_both_seeds": True,
            "either_parent_deletion_had_no_observed_effect_when_singleton_presented_first": True,
            "either_parent_deletion_prevented_recovery_when_singleton_presented_last": True,
            "complete_pair_overcame_unfavorable_last_position_across_both_seeds": True,
            "seed_interaction_observed": False,
        },
        "historical_claims": {
            "PARENT_A_ONLY_DIRECTIONAL_ASYMMETRY": {
                "status": "RETIRED_AS_STABLE_EXPLANATION",
                "historical_parent_a_evidence_preserved": True,
                "reinterpretation": "PRESENTATION_CONFOUNDED_NOT_STABLE_PARENT_A_ONLY_MECHANISM",
            }
        },
        "locked_claims": dict(LOCKED_CLAIMS),
        "next_boundary": (
            "Preserve this bounded transform-core adjudication and require separate "
            "authorization before any follow-on design or execution."
        ),
    }
    validate_disclosure_boundary(artifact)
    return artifact


def render_record(repository: Path, artifact: Mapping[str, Any] | None = None) -> dict[str, Any]:
    adjudication = dict(artifact or render_adjudication(repository))
    artifact_sha256 = crossover.sha256_bytes(canonical_json_bytes(adjudication) + b"\n")
    record = {
        "id": RECORD_ID,
        "checkpoint": "2-Catalytic-Kernel-0-position-seed-crossover-adjudication",
        "hypothesis": (
            "Within one matched private binding, parent-information dependence is "
            "conditional on singleton presentation position rather than a stable Parent-A-only asymmetry."
        ),
        "intervention": (
            "Statically verify and replay the completed 2x2x3 transform-only crossover, "
            "publish its position-conditional causal interpretation, and create no model contact."
        ),
        "baseline_commit": SOURCE_COMMIT,
        "candidate_commit": None,
        "model_hash": crossover.MODEL_SHA256,
        "configuration": {
            "design_id": crossover.DESIGN_ID,
            "source_execution_commit": SOURCE_COMMIT,
            "source_binding_scope": "one-matched-private-binding",
            "presentations": ["P0-singleton-first", "P1-singleton-last"],
            "seed_blocks": dict(crossover.SEED_BLOCKS),
            "arms": list(crossover.ARMS),
            "request_count": 12,
            "maximum_generations_per_request": 1,
            "binary_sha256": crossover.BINARY_SHA256,
            "preregistration_artifact_sha256": crossover.sha256_bytes(
                (repository / crossover.PREREGISTRATION_PATH).read_bytes()
            ),
        },
        "metrics_before": {
            "historical_explanation": "PARENT_A_ONLY_DIRECTIONAL_ASYMMETRY",
            "historical_parent_a_evidence_preserved": True,
            "presentation_position_confounded": True,
        },
        "metrics_after": {
            "status": "adjudicated",
            "terminal_execution_status": "complete",
            "completed_model_generations_in_source_execution": 12,
            "zero_contact_replay_generations": 0,
            "observed_matrix": adjudication["observed_matrix"],
            "supported_panel_classification": SUPPORTED_CLAIMS[0],
            "scientific_interpretation": SUPPORTED_CLAIMS[1],
            "bounded_mechanistic_statement": SUPPORTED_CLAIMS[2],
            "seed_interaction_observed": False,
            "authority_receipt_sha256": EXPECTED_HASHES["receipt"],
            "manifest_sha256": EXPECTED_HASHES["manifest"],
            "result_sha256": EXPECTED_HASHES["result"],
            "closure_sha256": EXPECTED_HASHES["closure"],
            "journal_sha256": EXPECTED_HASHES["journal"],
            "journal_head_sha256": EXPECTED_HASHES["journal_head"],
            "evidence_archive_sha256": EXPECTED_HASHES["archive"],
            "adjudication_artifact_sha256": artifact_sha256,
        },
        "quality_gates": {
            "archive_verified": True,
            "all_twelve_captures_authenticated": True,
            "zero_contact_replay_exact": True,
            "controller_classification_supported": True,
            "historical_parent_a_evidence_preserved": True,
            "parent_a_only_explanation_retired": True,
            "matched_binding_only": True,
            "transform_causal_core_only": True,
            "complete_new_cycle_tested": False,
            "no_disclosure": True,
            "general_catalytic_inference_locked": True,
            "automatic_promotion": False,
        },
        "verdict": "accept",
        "next_boundary": (
            "Require separate authorization before any follow-on design or execution; "
            "all broader claims remain locked."
        ),
    }
    validate_disclosure_boundary(record)
    return record


def validate_publication(repository: Path) -> dict[str, Any]:
    artifact = render_adjudication(repository)
    artifact_bytes = canonical_json_bytes(artifact) + b"\n"
    artifact_path = repository / ARTIFACT_PATH
    _require(
        artifact_path.is_file()
        and not artifact_path.is_symlink()
        and artifact_path.read_bytes() == artifact_bytes,
        "tracked adjudication artifact differs from exact reconstruction",
    )
    expected_record = render_record(repository, artifact)
    expected_line = canonical_json_text(expected_record)
    matches: list[tuple[int, str, dict[str, Any]]] = []
    for line_number, line in enumerate((repository / RESULTS_PATH).read_text(encoding="utf-8").splitlines(), 1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PositionSeedAdjudicationError("results ledger is invalid JSONL") from exc
        if isinstance(record, dict) and record.get("id") == RECORD_ID:
            matches.append((line_number, line, record))
    _require(len(matches) == 1, "publication ledger must contain exactly one adjudication record")
    line_number, line, record = matches[0]
    _require(line == expected_line and record == expected_record, "ledger record differs from exact render")
    validate_disclosure_boundary(record)
    return {
        "status": "pass",
        "adjudication_id": ADJUDICATION_ID,
        "adjudication_artifact_sha256": crossover.sha256_bytes(artifact_bytes),
        "record_id": RECORD_ID,
        "ledger_line": line_number,
        "record_sha256": crossover.sha256_bytes(expected_line.encode("utf-8")),
        "archive_verified": True,
        "capture_count": 12,
        "zero_contact_replay": True,
        "model_requests_issued": 0,
        "sidecar_launches": 0,
        "model_generations": 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("render-artifact", "render-record", "validate"))
    parser.add_argument("--repository", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository = Path(args.repository).resolve(strict=False)
    try:
        if args.action == "render-artifact":
            result = render_adjudication(repository)
        elif args.action == "render-record":
            result = render_record(repository)
        else:
            result = validate_publication(repository)
    except (OSError, json.JSONDecodeError, PositionSeedAdjudicationError, crossover.PositionSeedCrossoverError) as exc:
        print(canonical_json_text({"status": "fail", "error": str(exc)}))
        return 1
    print(canonical_json_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
