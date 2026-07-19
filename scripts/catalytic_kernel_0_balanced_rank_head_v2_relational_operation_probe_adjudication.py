#!/usr/bin/env python3
"""Statically adjudicate and publish the completed relational-operation probe."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import catalytic_kernel_0_balanced_rank_head_v2_relational_operation_probe as probe
import catalytic_kernel_0_balanced_rank_head_v2_relational_operation_probe_scientific as scientific


class RelationalOperationAdjudicationError(ValueError):
    """The archived probe cannot support the bounded publication."""


SOURCE_COMMIT = "9fc7437a2624586da1bf24471bfda551d0a35a34"
ARTIFACT_PATH = Path(
    "lab/ck0_balanced_opaque_rank_head_v2_relational_operation_probe_adjudication_1.json"
)
RESULTS_PATH = Path("lab/results.jsonl")
ADJUDICATION_ID = (
    "ck0-balanced-opaque-rank-head-v2-relational-operation-probe-adjudication-1"
)
RECORD_ID = "neo-exp-0043"

EXPECTED_PREREGISTRATION_SHA256 = (
    "136E9ED06AA9C9A1FF0731F2503378B9108C28DEC19060CBDFFE4F5B4B046CEC"
)
EXPECTED_SCIENTIFIC_BINDING_SHA256 = (
    "D9300869CE6C903D309899F5E9AFF02D4C7F9B0D815EC877CCC3BEA5DB67DE7C"
)
EXPECTED_CONTROLLER_BINDING_SHA256 = (
    "A57EDBE91CF0950BB83268E71132C10EAEA2E93B064E422B6A225715B1F6C2F6"
)
EXPECTED_AUTHORITY_ID_SHA256 = (
    "49F3918185A5C68DFD244EFC014D7C02B8242D990E09BFBE0F871649DB3F140E"
)
EXPECTED_HASHES = {
    "receipt": "7AD4AF03F315F7050E928F3A24C97CC6C7A83787C692D99191D7E64100E75161",
    "manifest": "36D7B4F3F98457AA3A94B7E220C5D7EB234F36316C552A0622B58B6E3AB23D5C",
    "result": "AD863CD4A265E02940F306E5334AA5D59679B599C6413F56593B5F69A209F090",
    "closure": "A7C2848A74F14348B7A43614D01754D3DA4932016CBE8625200956AD1A18D943",
    "journal": "DFCF0B5BA855C5D831D4B2EBA33B630620E4D8D630BF6CC15525E9E4A8FCE1FF",
    "journal_head": "B95D37D97249E2D8C155B2D08183C122D511A0856EE4E742BD0AED51FA893613",
    "archive": "CC3AD55805F0F39C01CC7404B1990B4F778C215E35FFAA9C67588AB83566637E",
    "archived_journal": "E94A94246FA79E8D0B0506DB91C43A844BE1B9564EEC2CEA955B51B2C452F52D",
    "archived_journal_head": "470E7AF196F566C2E39D3352CB1030171D1AC7C386C54CC6D46C6536FBBA4D1C",
}
EXPECTED_CAPTURE_HASHES = {
    "G0-AB": "E950DDE514304875607AC995D726A85A682DA5F1A7C1CBAF97C50915EB50A585",
    "G0-BA": "F98D82F66E3D7084FEF1514D5396ACD05B8312D00CBE79487C6098EB77A1CFCE",
    "G1-AB": "57977EB294BC00B1AB06BFF38A145F6855969437450EFBEB0F3EC520064257DA",
    "G1-BA": "1D616A72D85C7861B808E5F9FC77CEF44B52BED0132C3F90951E30C7930A7D97",
}

SUPPORTED_CLASSIFICATION = (
    "COMMUTATIVE_UNIQUE_INTERSECTION_LIKE_TRANSFORM_SUPPORTED_ON_TWO_MATCHED_GEOMETRIES"
)
SCIENTIFIC_INTERPRETATION = (
    "JOINT_PARENT_TRANSFORM_SELECTS_THE_UNIQUE_RELATIONAL_INVARIANT_INDEPENDENT_"
    "OF_PARENT_PRESENTATION_ORDER_ACROSS_TWO_MATCHED_PRIVATE_GEOMETRIES"
)
EXPECTED_MECHANISM_MATCHES = {
    "unique-intersection": True,
    "lexical-first": False,
    "first-listed": False,
    "parent-a-priority": False,
    "parent-b-priority": False,
}
EXPECTED_ORDER_INVARIANCE = {"G0": True, "G1": True}
LOCKED_CLAIMS = {
    "FORMAL_ALGEBRA": "LOCKED",
    "ASSOCIATIVITY": "LOCKED",
    "IDENTITY": "LOCKED",
    "GENERAL_CLOSURE": "LOCKED",
    "IDEMPOTENCE": "LOCKED",
    "GENERAL_WITHIN_LIST_PERMUTATION_INVARIANCE": "LOCKED",
    "REPLICATION_ACROSS_SEEDS": "LOCKED",
    "REPLICATION_ACROSS_BINDINGS": "LOCKED",
    "TRANSFER": "LOCKED",
    "GENERAL_CATALYTIC_INFERENCE": "LOCKED",
    "COMPLETE_NEW_BORROW_TRANSFORM_EXTRACT_RESTORE_CYCLE": "LOCKED",
    "TASK_ADVANTAGE": "LOCKED",
    "SUPERIORITY": "LOCKED",
    "SOTA": "LOCKED",
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
        raise RelationalOperationAdjudicationError(message)


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
    probe._assert_public_no_smuggle(value)
    for key, _nested in _iter_values(value):
        if key is not None and key.casefold() in FORBIDDEN_KEYS:
            raise RelationalOperationAdjudicationError(
                f"publication disclosure contains forbidden field: {key}"
            )


def _require_exact_scientific_pattern(
    outcomes: Sequence[Mapping[str, Any]],
    adjudication: Mapping[str, Any],
) -> None:
    _require(
        [outcome.get("request_id") for outcome in outcomes]
        == list(probe.REQUEST_IDS),
        "the four-request outcome order changed",
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
            "a frozen mechanism comparison changed",
        )
    _require(
        adjudication.get("classification") == SUPPORTED_CLASSIFICATION,
        "controller classification changed",
    )
    _require(
        adjudication.get("mechanism_matches_all_four")
        == EXPECTED_MECHANISM_MATCHES,
        "all-request mechanism comparison changed",
    )
    _require(
        adjudication.get("semantic_selection_order_invariant_by_geometry")
        == EXPECTED_ORDER_INVARIANCE,
        "AB/BA semantic order invariance changed",
    )
    _require(
        adjudication.get("transferred_across_two_matched_geometries") is True
        and adjudication.get("formal_algebra_claimed") is False
        and adjudication.get("scope")
        == "two-matched-geometries-one-private-binding-one-fixed-seed-transform-only",
        "bounded controller scope changed",
    )


def _verify_archive(
    repository: Path,
    paths: Mapping[str, Path],
    experiment_key: bytes,
) -> dict[str, Any]:
    archive_root = (
        repository
        / probe.ARCHIVE_ROOT
        / probe.DESIGN_ID
        / EXPECTED_HASHES["archive"]
    )
    bundle_path = archive_root / "bundle.json"
    bundle_data = probe._require_regular(bundle_path, "archive bundle")
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
        _require(isinstance(name, str), "archive member identity changed")
        data = probe._require_regular(archive_root / name, f"archive member {name}")
        _require(
            len(data) == entry.get("byte_size")
            and probe.sha256_bytes(data) == entry.get("sha256"),
            f"archive member changed: {name}",
        )
        actual_members.add(name)
    _require(actual_members == expected_members, "archive member set changed")

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
    for request_id in probe.REQUEST_IDS:
        _require(
            paths[f"capture-{request_id}"].read_bytes()
            == (archive_root / "captures" / f"{request_id}.json").read_bytes(),
            f"live and archived capture differ: {request_id}",
        )

    archived_journal_path = archive_root / "journal.jsonl"
    archived_journal_data = archived_journal_path.read_bytes()
    _require(
        probe.sha256_bytes(archived_journal_data) == EXPECTED_HASHES["archived_journal"],
        "archived journal hash changed",
    )
    archived_events = probe.verify_journal(archived_journal_path, experiment_key)
    _require(
        len(archived_events) == 19
        and archived_events[-1].get("state") == "terminal-written"
        and archived_events[-1].get("event_sha256")
        == EXPECTED_HASHES["archived_journal_head"],
        "archived journal terminal boundary changed",
    )
    live_journal_data = paths["journal"].read_bytes()
    _require(
        live_journal_data.startswith(archived_journal_data)
        and len(live_journal_data.splitlines()) == len(archived_events) + 1,
        "live journal is not the exact archived prefix plus final archive event",
    )
    return {"file_count": 9, "archived_journal_event_count": 19}


def _verified_replay(repository: Path) -> dict[str, Any]:
    paths = probe.state_paths(repository)
    for name in ("receipt", "manifest", "result", "closure", "journal"):
        data = probe._require_regular(paths[name], name, maximum=8 * 1024 * 1024)
        _require(
            probe.sha256_bytes(data) == EXPECTED_HASHES[name],
            f"{name} hash changed",
        )

    root, private = probe._load_private(repository)
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
        manifest.get("attempt_id") == probe.ATTEMPT_ID
        and manifest.get("execution_order") == list(probe.EXECUTION_ORDER)
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

    preregistration_data = (repository / probe.PREREGISTRATION_PATH).read_bytes()
    _require(
        probe.sha256_bytes(preregistration_data) == EXPECTED_PREREGISTRATION_SHA256,
        "preregistration bytes changed",
    )
    preregistration = json.loads(preregistration_data)
    _require(
        preregistration.get("bindings", {}).get("frozen_scientific", {}).get("sha256")
        == EXPECTED_SCIENTIFIC_BINDING_SHA256
        and preregistration.get("bindings", {}).get("controller", {}).get("sha256")
        == EXPECTED_CONTROLLER_BINDING_SHA256,
        "preregistration binding changed",
    )
    source_evidence = probe._source_evidence(repository)

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
    captured = {
        event["request_id"]: event
        for event in events
        if event.get("state") == "response-captured"
    }
    _require(
        set(started) == set(probe.REQUEST_IDS)
        and set(captured) == set(probe.REQUEST_IDS),
        "request journal is incomplete",
    )

    archive = _verify_archive(repository, paths, experiment_key)
    model_identity = manifest.get("preflight", {}).get("model_identity", {})
    model_path_text = model_identity.get("path")
    _require(isinstance(model_path_text, str), "captured model path is unavailable")
    tokenizer = probe.asymmetry.OfflineTokenizer(Path(model_path_text))
    selection = probe.select_first_eligible(root, tokenizer)
    geometries = selection["geometries"]

    outcomes: dict[str, dict[str, Any]] = {}
    private_selections: dict[str, str] = {}
    capture_hashes: dict[str, str] = {}
    for request_id in probe.REQUEST_IDS:
        live_path = paths[f"capture-{request_id}"]
        capture_sha256 = probe.sha256_bytes(live_path.read_bytes())
        _require(
            capture_sha256 == EXPECTED_CAPTURE_HASHES[request_id],
            f"capture hash changed: {request_id}",
        )
        capture = scientific.verify_capture(
            live_path,
            experiment_key=experiment_key,
            request_id=request_id,
            model_request_sha256=authority["request_sha256"][request_id],
        )
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
        capture_hashes[request_id] = capture_sha256

    adjudication = probe.adjudicate_outcomes(outcomes, private_selections)
    ordered_outcomes = [outcomes[request_id] for request_id in probe.REQUEST_IDS]
    _require_exact_scientific_pattern(ordered_outcomes, adjudication)
    _require(
        result.get("status") == "complete"
        and result.get("completed_model_generations") == 4
        and result.get("maximum_model_generations") == 4
        and result.get("automatic_follow_on") is False
        and result.get("failure") is None
        and result.get("request_dispositions") == ordered_outcomes
        and result.get("adjudication") == adjudication,
        "zero-contact replay differs from the terminal result",
    )
    _require(
        result.get("cleanup", {}).get("passed") is True
        and result.get("postflight", {}).get("passed") is True,
        "source cleanup or postflight changed",
    )
    predecessor = probe.verify_predecessor_attempt(repository)
    return {
        "authority_id_sha256": authority["authority_id_sha256"],
        "capture_sha256": capture_hashes,
        "event_count": len(events),
        "archive": archive,
        "selection_counter": selection["counter"],
        "outcomes": ordered_outcomes,
        "adjudication": adjudication,
        "predecessor": predecessor,
        "source_evidence": source_evidence,
    }


def render_adjudication(repository: Path) -> dict[str, Any]:
    replay = _verified_replay(repository)
    artifact = {
        "schema_version": 1,
        "adjudication_id": ADJUDICATION_ID,
        "design_id": probe.DESIGN_ID,
        "attempt_id": probe.ATTEMPT_ID,
        "status": SUPPORTED_CLASSIFICATION,
        "scope": {
            "one_private_binding": True,
            "fixed_transform_seed_count": 1,
            "matched_identity_disjoint_geometry_count": 2,
            "presentation_orders": ["AB", "BA"],
            "transform_only": True,
            "complete_new_borrow_transform_extract_restore_cycle_tested": False,
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
            "evidence_archive_sha256": EXPECTED_HASHES["archive"],
            "archive_file_count": replay["archive"]["file_count"],
            "capture_sha256": replay["capture_sha256"],
            "completed_model_generations": 4,
            "retry_count": 0,
            "automatic_follow_on": False,
        },
        "bindings": {
            "preregistration_sha256": EXPECTED_PREREGISTRATION_SHA256,
            "frozen_scientific_sha256": EXPECTED_SCIENTIFIC_BINDING_SHA256,
            "controller_sha256": EXPECTED_CONTROLLER_BINDING_SHA256,
            "source_result_record_id": probe.SOURCE_RESULT_RECORD_ID,
            "source_result_record_sha256": probe.SOURCE_RESULT_RECORD_SHA256,
        },
        "zero_contact_reconstruction": {
            "archive_verified": True,
            "authenticated_captures_verified": 4,
            "authenticated_journal_events_verified": replay["event_count"],
            "request_outcomes_replayed": 4,
            "terminal_result_exact_match": True,
            "controller_adjudication_exact_match": True,
            "predecessor_attempt_preserved": True,
            "model_requests_issued": 0,
            "sidecar_launches": 0,
            "model_generations": 0,
        },
        "observed_outcomes": replay["outcomes"],
        "supported_claims": [SUPPORTED_CLASSIFICATION, SCIENTIFIC_INTERPRETATION],
        "scientific_interpretation": {
            "each_geometry_had_one_unique_shared_candidate": True,
            "shared_candidate_was_not_first_in_either_parent": True,
            "AB_BA_swapped_parent_presentation_order_only": True,
            "rank_zero_selected_the_same_semantic_candidate_under_AB_and_BA": True,
            "identity_disjoint_matched_geometries_agreed": True,
            "all_frozen_competing_mechanisms_rejected": True,
            "context_stabilization_only_not_selected": True,
            "operation_is_intersection_like_not_generic_extra_context_improvement": True,
            "formal_algebra_not_established": True,
        },
        "relationship_to_predecessor_result": {
            "record_id": probe.SOURCE_RESULT_RECORD_ID,
            "record_sha256": probe.SOURCE_RESULT_RECORD_SHA256,
            "position_conditioned_parent_information_dependence_preserved": True,
            "relational_operation_result_is_complementary": True,
            "combined_bounded_interpretation": (
                "The prior panel localized when joint-parent information matters; this "
                "probe identifies the observed joint transform as unique-intersection-like "
                "within its one-binding, one-seed, two-geometry scope."
            ),
        },
        "rejected_frozen_explanations": {
            "lexical_first": True,
            "first_listed": True,
            "parent_a_priority": True,
            "parent_b_priority": True,
            "parent_order": True,
            "context_stabilization_only": True,
        },
        "predecessor_attempt_custody": replay["predecessor"],
        "locked_claims": dict(LOCKED_CLAIMS),
        "next_boundary": (
            "Require separate authorization before the minimum independent replication "
            "needed to test seed and binding stability; do not design or execute it here."
        ),
    }
    validate_disclosure_boundary(artifact)
    return artifact


def render_record(
    repository: Path,
    artifact: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    adjudication = dict(artifact or render_adjudication(repository))
    artifact_sha256 = probe.sha256_bytes(canonical_json_bytes(adjudication) + b"\n")
    record = {
        "id": RECORD_ID,
        "checkpoint": "2-Catalytic-Kernel-0-relational-operation-adjudication",
        "hypothesis": (
            "Across two matched private geometries, the joint-parent transform selects "
            "the unique shared relational candidate independently of AB or BA parent presentation."
        ),
        "intervention": (
            "Statically verify and replay the completed four-request transform-only probe, "
            "publish its bounded intersection-like interpretation, and create no model contact."
        ),
        "baseline_commit": SOURCE_COMMIT,
        "candidate_commit": None,
        "model_hash": probe.MODEL_SHA256,
        "configuration": {
            "design_id": probe.DESIGN_ID,
            "attempt_id": probe.ATTEMPT_ID,
            "source_execution_commit": SOURCE_COMMIT,
            "source_binding_scope": "one-private-binding",
            "geometry_count": 2,
            "geometries_identity_disjoint": True,
            "presentation_orders": ["AB", "BA"],
            "fixed_transform_seed": probe.FIXED_TRANSFORM_SEED,
            "request_count": 4,
            "maximum_generations_per_request": 1,
            "binary_sha256": probe.BINARY_SHA256,
            "preregistration_sha256": EXPECTED_PREREGISTRATION_SHA256,
            "frozen_scientific_binding_sha256": EXPECTED_SCIENTIFIC_BINDING_SHA256,
            "controller_binding_sha256": EXPECTED_CONTROLLER_BINDING_SHA256,
            "predecessor_record_id": probe.SOURCE_RESULT_RECORD_ID,
            "predecessor_record_sha256": probe.SOURCE_RESULT_RECORD_SHA256,
        },
        "metrics_before": {
            "position_conditioned_parent_information_record_id": probe.SOURCE_RESULT_RECORD_ID,
            "position_conditioned_parent_information_record_sha256": probe.SOURCE_RESULT_RECORD_SHA256,
            "relational_operation_identified": False,
        },
        "metrics_after": {
            "status": "adjudicated",
            "terminal_execution_status": "complete",
            "completed_model_generations_in_source_execution": 4,
            "zero_contact_replay_generations": 0,
            "observed_outcomes": adjudication["observed_outcomes"],
            "terminal_classification": SUPPORTED_CLASSIFICATION,
            "scientific_interpretation": SCIENTIFIC_INTERPRETATION,
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
            "archive_verified": True,
            "all_four_captures_authenticated": True,
            "zero_contact_replay_exact": True,
            "controller_classification_supported": True,
            "unique_intersection_prediction_supported": True,
            "all_frozen_competitors_rejected": True,
            "AB_BA_order_invariance_observed_in_both_geometries": True,
            "predecessor_attempt_preserved": True,
            "predecessor_result_record_exact": True,
            "one_binding_one_seed_scope": True,
            "transform_causal_core_only": True,
            "complete_new_cycle_tested": False,
            "formal_algebra_claimed": False,
            "no_disclosure": True,
            "general_catalytic_inference_locked": True,
            "automatic_promotion": False,
        },
        "verdict": "accept",
        "next_boundary": (
            "Require separate authorization before the minimum independent replication "
            "needed to test seed and binding stability; all broader claims remain locked."
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
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RelationalOperationAdjudicationError(
                "results ledger is invalid JSONL"
            ) from exc
        if isinstance(record, dict) and record.get("id") == RECORD_ID:
            matches.append((line_number, line, record))
    _require(
        len(matches) == 1,
        "publication ledger must contain exactly one adjudication record",
    )
    line_number, line, record = matches[0]
    _require(
        line == expected_line and record == expected_record,
        "ledger record differs from exact render",
    )
    validate_disclosure_boundary(record)
    return {
        "status": "pass",
        "adjudication_id": ADJUDICATION_ID,
        "adjudication_artifact_sha256": probe.sha256_bytes(artifact_bytes),
        "record_id": RECORD_ID,
        "ledger_line": line_number,
        "record_sha256": probe.sha256_bytes(expected_line.encode("utf-8")),
        "source_record_id": probe.SOURCE_RESULT_RECORD_ID,
        "source_record_sha256": probe.SOURCE_RESULT_RECORD_SHA256,
        "archive_verified": True,
        "capture_count": 4,
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
        RelationalOperationAdjudicationError,
        probe.RelationalOperationProbeError,
        scientific.ScientificSurfaceError,
    ) as exc:
        print(canonical_json_text({"status": "fail", "error": str(exc)}))
        return 1
    print(canonical_json_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
