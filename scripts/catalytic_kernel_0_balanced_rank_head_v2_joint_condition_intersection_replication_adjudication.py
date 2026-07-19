#!/usr/bin/env python3
"""Statically adjudicate the completed joint-condition replication."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import catalytic_kernel_0_balanced_rank_head_v2_joint_condition_intersection_replication as probe
import catalytic_kernel_0_balanced_rank_head_v2_joint_condition_intersection_replication_scientific as scientific


class JointConditionAdjudicationError(ValueError):
    """The completed replication cannot support the bounded publication."""


SOURCE_COMMIT = "5d4d7762fcf1fdaa25a3559d2120929b74ca0099"
ARTIFACT_PATH = Path(
    "lab/ck0_balanced_opaque_rank_head_v2_joint_condition_intersection_replication_adjudication_1.json"
)
RESULTS_PATH = Path("lab/results.jsonl")
ADJUDICATION_ID = (
    "ck0-balanced-opaque-rank-head-v2-joint-condition-intersection-replication-adjudication-1"
)
RECORD_ID = "neo-exp-0044"

EXPECTED_PREREGISTRATION_SHA256 = (
    "A0ABF5C537C4C27429B7B6572986570190731FC90029590E16A0597DF6DEAB74"
)
EXPECTED_SCIENTIFIC_BINDING_SHA256 = (
    "8D00C7D5C57DC2D70E4948EF14E617B8EC4E0B763633F541AE25DDE0C5ADBD26"
)
EXPECTED_CONTROLLER_BINDING_SHA256 = (
    "5900CCE9E516020D2F5D022E1763977463E1668BED2EB11FFEB686CA123927C0"
)
EXPECTED_PRIVATE_BINDING_COMMITMENT = (
    "7999FE7862527BE08589EFF15B8AD7CFBC9F81C44C1FB7804E0AF31F34BD72FD"
)
EXPECTED_AUTHORITY_ID_SHA256 = (
    "0418064587E02A2E0B23A0B4D774645C238AA4999BB067DBD2AA05364AF44CEF"
)
EXPECTED_HASHES = {
    "receipt": "A2CB02AAE10500FC96F996B4E9CD3717241FF36AB422371640CA650DFD511A7D",
    "manifest": "BA68AB949C8C38EC3FF6853871DF62C6E3C423D379F6D8FF85B61A37B5D2B834",
    "result": "7835A4E6838E70B0A896D225D9576034112B30C3DAF6C4698A1D1BFF13879933",
    "closure": "1465A7669DCF096A28C4F092659728B2A619255978D83C5026AD5B6CDEEA6AAC",
    "journal": "91E968D3F42634083CE8F2A8371B70BB2D4923ED07DBAE1BC7708D056AA033B2",
    "journal_head": "102758BF02B568017A11F341D8385960D6A6592AC00B8E5BAF28DC339E4F6A17",
    "archive": "96F010EE89320EA8C7C008B6B7790FA41A753E773738932764828E06ACD20733",
    "archived_journal": "EB6B96485A4CACC3F71639367BD86920739A887A0CA6DA7481E33495B7B42251",
    "archived_journal_head": "E5AEE4FFDABD90CF1EACE2CE2ACD6C5D4FEB423347813ADAF7BDB5ED3EFA186C",
}
EXPECTED_CAPTURE_HASHES = {
    "R0-AB": "4BCA3DB05C4471C04EB881F587AFF2B004650D6AEBE33030578B6E9743C44B5A",
    "R0-BA": "0E458CBB7EBE238EEFF52F643A553B650496E66FD539D1BAAD84E0EB6C095A11",
    "R1-AB": "4373251B58CC3106CEA69FD733B3355DCA58EC578128DEAE30A913E2256DF484",
    "R1-BA": "6D02A183F66B58A32C2899C79580E4DB9C4CC5B2CFBE8711E819532DEF26FC7E",
}
SUPPORTED_CLASSIFICATION = (
    "COMMUTATIVE_UNIQUE_INTERSECTION_LIKE_TRANSFORM_REPRODUCED_UNDER_"
    "JOINTLY_NEW_PRIVATE_BINDING_AND_FIXED_SEED"
)
EXPECTED_MECHANISM_MATCHES = {
    "unique-intersection": True,
    "lexical-first": False,
    "first-listed": False,
    "parent-a-priority": False,
    "parent-b-priority": False,
}
EXPECTED_ORDER_INVARIANCE = {"R0": True, "R1": True}
LOCKED_CLAIMS = {
    "SEED_INVARIANCE": "LOCKED",
    "BINDING_INVARIANCE": "LOCKED",
    "FORMAL_ALGEBRA": "LOCKED",
    "GENERAL_TRANSFER": "LOCKED",
    "GENERAL_CATALYTIC_INFERENCE": "LOCKED",
    "TASK_ADVANTAGE": "LOCKED",
    "COMPUTE_AMPLIFICATION": "LOCKED",
    "automatic_promotion": False,
}


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
        raise JointConditionAdjudicationError(message)


def validate_disclosure_boundary(value: Mapping[str, Any]) -> None:
    probe._assert_public_no_smuggle(value)


def _require_exact_pattern(
    outcomes: Sequence[Mapping[str, Any]], adjudication: Mapping[str, Any]
) -> None:
    _require(
        [outcome.get("request_id") for outcome in outcomes] == list(probe.REQUEST_IDS),
        "request outcome order changed",
    )
    for outcome in outcomes:
        _require(
            outcome.get("transform_operator") == "reconcile"
            and outcome.get("selected_rank") == 0
            and outcome.get("selection_frozen_before_private_mapping") is True
            and outcome.get("private_mapping_consulted_before_selection") is False
            and outcome.get("selected_from_parent_union") is True,
            "rank-zero transform law changed",
        )
        _require(
            outcome.get("mechanism_matches") == EXPECTED_MECHANISM_MATCHES,
            "frozen mechanism comparison changed",
        )
    _require(
        adjudication.get("classification") == SUPPORTED_CLASSIFICATION
        and adjudication.get("mechanism_matches_all_four")
        == EXPECTED_MECHANISM_MATCHES
        and adjudication.get("semantic_selection_order_invariant_by_geometry")
        == EXPECTED_ORDER_INVARIANCE
        and adjudication.get("reproduced_under_combined_new_condition") is True,
        "bounded replication classification changed",
    )
    _require(
        adjudication.get("seed_invariance_independently_established") is False
        and adjudication.get("binding_invariance_independently_established") is False
        and adjudication.get("formal_algebra_claimed") is False
        and adjudication.get("general_transfer_claimed") is False,
        "claim boundary changed",
    )


def _verify_archive(
    repository: Path, paths: Mapping[str, Path], experiment_key: bytes
) -> dict[str, Any]:
    archive_root = (
        repository / probe.ARCHIVE_ROOT / probe.DESIGN_ID / EXPECTED_HASHES["archive"]
    )
    bundle_data = probe._require_regular(archive_root / "bundle.json", "archive bundle")
    bundle = json.loads(bundle_data)
    _require(isinstance(bundle, dict), "archive bundle is not an object")
    body = {key: value for key, value in bundle.items() if key != "bundle_sha256"}
    _require(
        bundle.get("bundle_sha256") == EXPECTED_HASHES["archive"]
        and probe.json_sha256(body) == EXPECTED_HASHES["archive"],
        "archive content address changed",
    )
    entries = bundle.get("files")
    _require(isinstance(entries, list) and len(entries) == 9, "archive inventory changed")
    expected_members = {
        "authority-receipt.json",
        "manifest.json",
        "journal.jsonl",
        "result.json",
        "closure.json",
        *(f"captures/{request_id}.json" for request_id in probe.REQUEST_IDS),
    }
    actual_members: set[str] = set()
    for entry in entries:
        _require(isinstance(entry, Mapping), "archive entry changed")
        name = entry.get("path")
        _require(isinstance(name, str), "archive member name changed")
        data = probe._require_regular(archive_root / name, f"archive member {name}")
        _require(
            len(data) == entry.get("byte_size")
            and probe.sha256_bytes(data) == entry.get("sha256"),
            f"archive member changed: {name}",
        )
        actual_members.add(name)
    _require(actual_members == expected_members, "archive member set changed")

    for key, member in {
        "receipt": "authority-receipt.json",
        "manifest": "manifest.json",
        "result": "result.json",
        "closure": "closure.json",
    }.items():
        _require(
            paths[key].read_bytes() == (archive_root / member).read_bytes(),
            f"live and archived {key} differ",
        )
    for request_id in probe.REQUEST_IDS:
        _require(
            paths[f"capture-{request_id}"].read_bytes()
            == (archive_root / "captures" / f"{request_id}.json").read_bytes(),
            f"live and archived capture differ: {request_id}",
        )

    archived_journal = archive_root / "journal.jsonl"
    archived_data = archived_journal.read_bytes()
    _require(
        probe.sha256_bytes(archived_data) == EXPECTED_HASHES["archived_journal"],
        "archived journal hash changed",
    )
    archived_events = probe.verify_journal(archived_journal, experiment_key)
    _require(
        len(archived_events) == 19
        and archived_events[-1].get("state") == "terminal-written"
        and archived_events[-1].get("event_sha256")
        == EXPECTED_HASHES["archived_journal_head"],
        "archived journal boundary changed",
    )
    live_data = paths["journal"].read_bytes()
    _require(
        live_data.startswith(archived_data)
        and len(live_data.splitlines()) == len(archived_events) + 1,
        "live journal is not the archived prefix plus one archive event",
    )
    return {"file_count": 9, "archived_journal_event_count": 19}


def _verified_replay(repository: Path) -> dict[str, Any]:
    paths = probe.state_paths(repository)
    for name in ("receipt", "manifest", "result", "closure", "journal"):
        data = probe._require_regular(paths[name], name, maximum=8 * 1024 * 1024)
        _require(probe.sha256_bytes(data) == EXPECTED_HASHES[name], f"{name} changed")

    root, private = probe._load_private(repository)
    _require(
        private.secret_commitment == EXPECTED_PRIVATE_BINDING_COMMITMENT,
        "source private binding commitment changed",
    )
    experiment_key = probe._experiment_key(root)
    receipt = probe.verify_authority_receipt(repository, root)
    authority = receipt.get("authority")
    _require(isinstance(authority, Mapping), "authority body is missing")
    _require(
        authority.get("authorized_commit") == SOURCE_COMMIT
        and receipt.get("consuming_commit") == SOURCE_COMMIT
        and authority.get("authority_id_sha256") == EXPECTED_AUTHORITY_ID_SHA256
        and authority.get("maximum_total_generations") == 4
        and authority.get("maximum_generations_per_request") == 1
        and authority.get("automatic_follow_on") is False,
        "consumed authority scope changed",
    )

    manifest = json.loads(paths["manifest"].read_bytes())
    result = json.loads(paths["result"].read_bytes())
    closure = json.loads(paths["closure"].read_bytes())
    _require(
        manifest.get("execution_order") == list(probe.REQUEST_IDS)
        and manifest.get("fixed_transform_seed") == probe.FIXED_TRANSFORM_SEED,
        "manifest scientific identity changed",
    )
    _require(
        closure.get("status") == "complete"
        and closure.get("authority_receipt_sha256") == EXPECTED_HASHES["receipt"]
        and closure.get("manifest_sha256") == EXPECTED_HASHES["manifest"]
        and closure.get("result_sha256") == EXPECTED_HASHES["result"]
        and closure.get("retry_allowed") is False
        and closure.get("run_lock_absent_at_terminal_publication") is True,
        "closure binding changed",
    )

    preregistration_path = repository / probe.PREREGISTRATION_PATH
    preregistration_data = preregistration_path.read_bytes()
    preregistration = json.loads(preregistration_data)
    _require(
        probe.sha256_bytes(preregistration_data) == EXPECTED_PREREGISTRATION_SHA256
        and preregistration.get("bindings", {}).get("frozen_scientific", {}).get("sha256")
        == EXPECTED_SCIENTIFIC_BINDING_SHA256
        and preregistration.get("bindings", {}).get("controller", {}).get("sha256")
        == EXPECTED_CONTROLLER_BINDING_SHA256,
        "source preregistration or binding changed",
    )
    probe._source_evidence(repository)

    events = probe.verify_journal(paths["journal"], experiment_key)
    _require(
        len(events) == 20
        and events[-1].get("state") == "archived"
        and events[-1].get("event_sha256") == EXPECTED_HASHES["journal_head"],
        "authenticated journal boundary changed",
    )
    started = {
        event["request_id"]: event
        for event in events
        if event.get("state") == "request-started"
    }
    _require(set(started) == set(probe.REQUEST_IDS), "request-start journal is incomplete")
    archive = _verify_archive(repository, paths, experiment_key)

    model_path_text = manifest.get("preflight", {}).get("model_identity", {}).get("path")
    _require(isinstance(model_path_text, str), "captured model identity is unavailable")
    model_path = Path(model_path_text)
    validation = probe.validate_preregistration(repository, model_path)
    _require(
        validation.get("artifact_sha256") == EXPECTED_PREREGISTRATION_SHA256,
        "exact preregistration reconstruction changed",
    )
    tokenizer = probe.asymmetry.OfflineTokenizer(model_path)
    selection = probe.select_first_eligible(root, tokenizer)
    geometries = selection["geometries"]

    outcomes: dict[str, dict[str, Any]] = {}
    private_selections: dict[str, str] = {}
    capture_hashes: dict[str, str] = {}
    for request_id in probe.REQUEST_IDS:
        capture_path = paths[f"capture-{request_id}"]
        capture_hash = probe.sha256_bytes(capture_path.read_bytes())
        _require(
            capture_hash == EXPECTED_CAPTURE_HASHES[request_id],
            f"capture identity changed: {request_id}",
        )
        capture = scientific.verify_capture(
            capture_path,
            experiment_key=experiment_key,
            request_id=request_id,
            model_request_sha256=authority["request_sha256"][request_id],
        )
        replay = scientific.replay_capture(capture)
        _require(isinstance(replay.content, str), "raw SSE reconstruction changed")
        outcome, selected = probe.capture_outcome(
            repository,
            root,
            private,
            geometries,
            request_id,
            capture,
            int(started[request_id]["facts"]["rendered_prompt_tokens"]),
        )
        outcomes[request_id] = outcome
        private_selections[request_id] = selected
        capture_hashes[request_id] = capture_hash

    adjudication = probe.adjudicate_outcomes(outcomes, private_selections)
    ordered_outcomes = [outcomes[request_id] for request_id in probe.REQUEST_IDS]
    _require_exact_pattern(ordered_outcomes, adjudication)
    _require(
        result.get("status") == "complete"
        and result.get("completed_model_generations") == 4
        and result.get("maximum_model_generations") == 4
        and result.get("failure") is None
        and result.get("automatic_follow_on") is False
        and result.get("request_dispositions") == ordered_outcomes
        and result.get("adjudication") == adjudication
        and result.get("cleanup", {}).get("passed") is True
        and result.get("postflight", {}).get("passed") is True,
        "deterministic replay differs from terminal result",
    )
    return {
        "authority_id_sha256": authority["authority_id_sha256"],
        "archive": archive,
        "capture_sha256": capture_hashes,
        "event_count": len(events),
        "outcomes": ordered_outcomes,
        "adjudication": adjudication,
        "selection_counter": selection["counter"],
    }


def render_adjudication(repository: Path) -> dict[str, Any]:
    replay = _verified_replay(repository)
    artifact = {
        "schema_version": 1,
        "adjudication_id": ADJUDICATION_ID,
        "design_id": probe.DESIGN_ID,
        "status": SUPPORTED_CLASSIFICATION,
        "scope": {
            "jointly_new_private_binding_and_fixed_seed": True,
            "seed_invariance_separately_established": False,
            "binding_invariance_separately_established": False,
            "matched_identity_disjoint_geometry_count": 2,
            "presentation_orders": ["AB", "BA"],
            "transform_only": True,
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
            "archived_journal_sha256": EXPECTED_HASHES["archived_journal"],
            "archived_journal_head_sha256": EXPECTED_HASHES["archived_journal_head"],
            "evidence_archive_sha256": EXPECTED_HASHES["archive"],
            "archive_file_count": replay["archive"]["file_count"],
            "capture_sha256": replay["capture_sha256"],
            "completed_model_generations": 4,
            "retry_count": 0,
        },
        "bindings": {
            "preregistration_sha256": EXPECTED_PREREGISTRATION_SHA256,
            "frozen_scientific_sha256": EXPECTED_SCIENTIFIC_BINDING_SHA256,
            "controller_sha256": EXPECTED_CONTROLLER_BINDING_SHA256,
            "private_binding_commitment_sha256": EXPECTED_PRIVATE_BINDING_COMMITMENT,
            "source_result_record_id": probe.SOURCE_RESULT_RECORD_ID,
            "source_result_record_sha256": probe.SOURCE_RESULT_RECORD_SHA256,
        },
        "zero_contact_reconstruction": {
            "authority_receipt_hmac_verified": True,
            "archive_verified": True,
            "authenticated_captures_verified": 4,
            "raw_sse_reconstructions_verified": 4,
            "authenticated_journal_events_verified": replay["event_count"],
            "request_outcomes_replayed": 4,
            "terminal_result_exact_match": True,
            "controller_adjudication_exact_match": True,
            "model_requests_issued": 0,
            "sidecar_launches": 0,
            "model_generations": 0,
        },
        "observed_outcomes": replay["outcomes"],
        "supported_claims": [SUPPORTED_CLASSIFICATION],
        "bounded_interpretation": {
            "operation_reproduced_under_combined_new_binding_and_seed": True,
            "R0_AB_BA_semantic_invariance": True,
            "R1_AB_BA_semantic_invariance": True,
            "unique_intersection_matched_all_four": True,
            "lexical_first": False,
            "first_listed": False,
            "parent_a_priority": False,
            "parent_b_priority": False,
            "parent_order_sensitivity_rejected_within_tested_orders": True,
            "context_stabilization_only_not_selected": True,
        },
        "locked_claims": dict(LOCKED_CLAIMS),
        "next_boundary": (
            "Prepare only the bounded three-parent global-invariant probe; require "
            "separate authority before any live execution."
        ),
    }
    validate_disclosure_boundary(artifact)
    return artifact


def render_record(
    repository: Path, artifact: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    adjudication = dict(artifact or render_adjudication(repository))
    artifact_sha256 = probe.sha256_bytes(canonical_json_bytes(adjudication) + b"\n")
    record = {
        "id": RECORD_ID,
        "checkpoint": "2-Catalytic-Kernel-0-joint-condition-intersection-adjudication",
        "hypothesis": (
            "The commutative unique-intersection-like transform reproduces under a "
            "jointly new private binding and fixed seed."
        ),
        "intervention": (
            "Statically verify, replay, and publish the completed four-request "
            "joint-condition transform-only replication."
        ),
        "baseline_commit": SOURCE_COMMIT,
        "candidate_commit": None,
        "model_hash": probe.MODEL_SHA256,
        "configuration": {
            "design_id": probe.DESIGN_ID,
            "source_execution_commit": SOURCE_COMMIT,
            "source_private_binding_commitment_sha256": EXPECTED_PRIVATE_BINDING_COMMITMENT,
            "fixed_transform_seed": probe.FIXED_TRANSFORM_SEED,
            "request_count": 4,
            "request_order": list(probe.REQUEST_IDS),
            "maximum_generations_per_request": 1,
            "binary_sha256": probe.BINARY_SHA256,
            "preregistration_sha256": EXPECTED_PREREGISTRATION_SHA256,
            "frozen_scientific_binding_sha256": EXPECTED_SCIENTIFIC_BINDING_SHA256,
            "controller_binding_sha256": EXPECTED_CONTROLLER_BINDING_SHA256,
            "predecessor_record_id": probe.SOURCE_RESULT_RECORD_ID,
            "predecessor_record_sha256": probe.SOURCE_RESULT_RECORD_SHA256,
        },
        "metrics_before": {
            "source_scope": "one-private-binding-one-fixed-seed-two-geometries",
            "combined_new_condition_replication_published": False,
        },
        "metrics_after": {
            "status": "adjudicated",
            "terminal_execution_status": "complete",
            "completed_model_generations_in_source_execution": 4,
            "zero_contact_replay_generations": 0,
            "terminal_classification": SUPPORTED_CLASSIFICATION,
            "observed_outcomes": adjudication["observed_outcomes"],
            "mechanism_matches_all_four": dict(EXPECTED_MECHANISM_MATCHES),
            "semantic_selection_order_invariant_by_geometry": dict(
                EXPECTED_ORDER_INVARIANCE
            ),
            "authority_receipt_sha256": EXPECTED_HASHES["receipt"],
            "manifest_sha256": EXPECTED_HASHES["manifest"],
            "result_sha256": EXPECTED_HASHES["result"],
            "closure_sha256": EXPECTED_HASHES["closure"],
            "journal_sha256": EXPECTED_HASHES["journal"],
            "journal_head_sha256": EXPECTED_HASHES["journal_head"],
            "evidence_archive_sha256": EXPECTED_HASHES["archive"],
            "capture_sha256": dict(EXPECTED_CAPTURE_HASHES),
            "adjudication_artifact_sha256": artifact_sha256,
        },
        "quality_gates": {
            "authority_receipt_hmac_verified": True,
            "archive_and_all_nine_entries_verified": True,
            "all_four_captures_authenticated": True,
            "raw_sse_reconstruction_exact": True,
            "zero_contact_replay_exact": True,
            "controller_classification_supported": True,
            "combined_new_binding_and_seed_condition": True,
            "seed_invariance_separately_established": False,
            "binding_invariance_separately_established": False,
            "formal_algebra_locked": True,
            "general_transfer_locked": True,
            "general_catalytic_inference_locked": True,
            "task_advantage_locked": True,
            "compute_amplification_locked": True,
            "no_disclosure": True,
            "automatic_promotion": False,
        },
        "verdict": "accept",
        "next_boundary": (
            "Prepare only the bounded three-parent global-invariant probe; require "
            "separate live authority afterward."
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
    for line_number, line in enumerate(
        (repository / RESULTS_PATH).read_text(encoding="utf-8").splitlines(), 1
    ):
        value = json.loads(line)
        if isinstance(value, dict) and value.get("id") == RECORD_ID:
            matches.append((line_number, line, value))
    _require(len(matches) == 1, "publication must contain exactly one record")
    line_number, line, value = matches[0]
    _require(
        line == expected_line and value == expected_record,
        "ledger record differs from exact render",
    )
    return {
        "status": "pass",
        "adjudication_id": ADJUDICATION_ID,
        "adjudication_artifact_sha256": probe.sha256_bytes(artifact_bytes),
        "record_id": RECORD_ID,
        "ledger_line": line_number,
        "record_sha256": probe.sha256_bytes(expected_line.encode("utf-8")),
        "archive_verified": True,
        "capture_count": 4,
        "raw_sse_reconstruction_count": 4,
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
    except (
        OSError,
        json.JSONDecodeError,
        JointConditionAdjudicationError,
        probe.JointConditionIntersectionReplicationError,
        scientific.ScientificSurfaceError,
    ) as exc:
        print(canonical_json_text({"status": "fail", "error": str(exc)}))
        return 1
    print(canonical_json_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
