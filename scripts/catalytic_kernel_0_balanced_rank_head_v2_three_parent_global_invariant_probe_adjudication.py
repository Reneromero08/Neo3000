#!/usr/bin/env python3
"""Statically adjudicate the completed three-parent global-invariant probe."""
from __future__ import annotations

import argparse
import base64
import binascii
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import catalytic_kernel_0_balanced_rank_head_v2_three_parent_global_invariant_probe as probe
import catalytic_kernel_0_balanced_rank_head_v2_three_parent_global_invariant_probe_scientific as scientific


class ThreeParentGlobalInvariantAdjudicationError(ValueError):
    """The completed probe cannot support the bounded publication."""


SOURCE_COMMIT = "467ee0d1381292a795765b2334976b17ba07feae"
ARTIFACT_PATH = Path(
    "lab/ck0_balanced_opaque_rank_head_v2_three_parent_global_invariant_probe_adjudication_1.json"
)
RESULTS_PATH = Path("lab/results.jsonl")
ADJUDICATION_ID = (
    "ck0-balanced-opaque-rank-head-v2-three-parent-global-invariant-probe-adjudication-1"
)
RECORD_ID = "neo-exp-0045"
EXPECTED_LEDGER_LINE = 58
PREDECESSOR_RECORD_ID = "neo-exp-0044"
PAIRWISE_RECORD_ID = "neo-exp-0043"
POSITION_RECORD_ID = "neo-exp-0042"
POSITION_RECORD_SHA256 = (
    "DAF072E43700F71A76537843507C578FEA38679AA15DC9A0C783090B29D5D0E8"
)
PAIRWISE_RECORD_SHA256 = (
    "C47DE48658E0C044AB676F584FF6030C0CB0A2AD5C84553B70B43EBC863C9423"
)

EXPECTED_PREREGISTRATION_SHA256 = (
    "BF8F42D01701B31A1878B912AB9AD35EA9FDF8E4B5B2E58BF5A04527F9E24067"
)
EXPECTED_SCIENTIFIC_BINDING_SHA256 = (
    "FDDD95661AF4581CB5F05F627E2E3AFE6A4D25F7D1EFFFE59AE17A6A9439FF44"
)
EXPECTED_CONTROLLER_BINDING_SHA256 = (
    "4E5E20F55E663CC6C91133A23B236AF004BA0C2A9D2B21B6D42BE273E1E1C401"
)
EXPECTED_PRIVATE_BINDING_COMMITMENT = (
    "7999FE7862527BE08589EFF15B8AD7CFBC9F81C44C1FB7804E0AF31F34BD72FD"
)
EXPECTED_AUTHORITY_ID_SHA256 = (
    "C48872C8BC362C797B5E4AE4D7F85A9BA33D23C14392CD6896456B23F73D9E54"
)
EXPECTED_HASHES = {
    "receipt": "0FECFB718FF4AF1917B21D5129F70F07CCE5310FBBA58E64255C63FC6F529EB0",
    "manifest": "0579FA2C70F4AEB5D4744FDD218044D37785C3941505741E883512B5BE6F020E",
    "result": "334B49CE4ABAA64724E8740AC7EB9FF92C05DFCFE1EF189F12171F0A17DD2D8B",
    "closure": "7FB247313677BC5F76A97BBA3CF4B00D617F91334870644F328EA4B4750D06AE",
    "journal": "58E28C7C11600869A345066B3D3F74286D15B830054CF05C4C50A4FA7BCC89F9",
    "journal_head": "696D0756197A0E8ECC33C484F7B897E1E7B5AB073D3145FBAA2CABD79886EDB8",
    "archive": "800B08FFC83B5AD8DAD9B5C1D39E351357BADBE0FABAB34561F6EBE1769E48FB",
    "archived_journal": "0542347CB802B9B278217B4955CE149B99E27E958BC90954B01946B46E12660F",
    "archived_journal_head": "4591E9F4D220D7B0A78124C4C18185A12325D215C1EA6D8CAFB5D3142E1176C2",
}
EXPECTED_CAPTURE_HASHES = {
    "T0-ABC": "850B7DC29172AC98E6B167B24E8D2EC24F069B4DD3C151E069D8C94B9463ADEA",
    "T0-BCA": "D7200104E6A57C6430D66C800FE0115CBDF1BD679292D6D7022E30DCB0D0839D",
    "T0-CAB": "C025AF3FB73FB1C0CB78053CC010A56AC9594356B76CB3CCF84BE7D02E7C771B",
    "T1-ABC": "0767B8923D753D9DCA47A4BD3A2C629F5CE75E2980AAFD8DA5B45A2195FF0D45",
    "T1-BCA": "079F63DB8B33797E799B10F62589176AA8209323C7BE5C53CABF88184357E6F9",
    "T1-CAB": "9F7BD270FA29C71A43A9E878F14721D95080F1C63F225072F1903AD9634515BC",
}
SUPPORTED_CLASSIFICATION = (
    "THREE_PARENT_GLOBAL_RELATIONAL_INVARIANT_EXTRACTION_SUPPORTED_ON_TWO_MATCHED_GEOMETRIES"
)
BOUNDED_INTERPRETATION = (
    "TRANSFORM_SELECTS_AN_INVARIANT_IDENTIFIABLE_ONLY_FROM_THE_COMPLETE_THREE_PARENT_"
    "RELATION_AND_NOT_FROM_ANY_SINGLE_PARENT_OR_PARENT_PAIR"
)
NEXT_BOUNDARY = "STATIC DESIGN OF_ONE_BOUNDED_WORKER_TO_SYNTHESIS_MINI_SWARM"
EXPECTED_MECHANISM_MATCHES = {
    "unique-three-way-intersection": True,
    "first-listed": False,
    "lexical-first": False,
    "first-parent-priority": False,
    "last-parent-priority": False,
    "first-presented-pair-decoy": False,
}
EXPECTED_ORDER_INVARIANCE = {"T0": True, "T1": True}
LOCKED_CLAIMS = {
    "FULL_COMMUTATIVITY": "LOCKED",
    "ASSOCIATIVITY": "LOCKED",
    "ARBITRARY_N_PARENT_GENERALIZATION": "LOCKED",
    "FORMAL_ALGEBRA": "LOCKED",
    "INDEPENDENT_SEED_INVARIANCE": "LOCKED",
    "INDEPENDENT_BINDING_INVARIANCE": "LOCKED",
    "GENERAL_TRANSFER": "LOCKED",
    "WORKER_SYNTHESIS": "LOCKED",
    "GENERAL_CATALYTIC_INFERENCE": "LOCKED",
    "COMPLETE_BORROW_TRANSFORM_EXTRACT_RESTORE": "LOCKED",
    "TASK_ADVANTAGE": "LOCKED",
    "REDUCED_FRESH_COMPUTATION": "LOCKED",
    "COMPUTE_AMPLIFICATION": "LOCKED",
    "SUPERIORITY": "LOCKED",
    "SOTA": "LOCKED",
    "automatic_promotion": False,
}
PROGRESSION = [
    "joint-parent information matters",
    "pairwise unique-intersection-like operation identified",
    "operation reproduced under a combined new binding-and-seed condition",
    "complete three-parent relation resolves an invariant unavailable to any parent pair",
]


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
        raise ThreeParentGlobalInvariantAdjudicationError(message)


def validate_disclosure_boundary(value: Mapping[str, Any]) -> None:
    probe._assert_public_no_smuggle(value)
    forbidden_fields = {
        "private_alias",
        "candidate_alias",
        "candidate_identity",
        "private_root",
        "alias_map",
        "correspondence",
    }

    def walk(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                _require(str(key) not in forbidden_fields, "private correspondence entered publication")
                walk(nested)
        elif isinstance(item, list):
            for nested in item:
                walk(nested)

    walk(value)


def _require_exact_pattern(
    outcomes: Sequence[Mapping[str, Any]],
    adjudication: Mapping[str, Any],
    expected_selected_commitments: Mapping[str, str] | None = None,
) -> None:
    _require(
        [outcome.get("request_id") for outcome in outcomes] == list(probe.REQUEST_IDS),
        "request outcome order changed",
    )
    for outcome in outcomes:
        request_id = str(outcome.get("request_id"))
        _require(
            outcome.get("transform_operator") == "reconcile"
            and outcome.get("transform_ranking_length") == 3
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
        if expected_selected_commitments is not None:
            _require(
                outcome.get("selected_candidate_commitment")
                == expected_selected_commitments.get(request_id),
                "selected commitment differs from frozen three-way invariant",
            )
    _require(
        adjudication.get("classification") == SUPPORTED_CLASSIFICATION
        and adjudication.get("supported_interpretation") == BOUNDED_INTERPRETATION
        and adjudication.get("mechanism_matches_all_six")
        == EXPECTED_MECHANISM_MATCHES
        and adjudication.get("semantic_selection_order_invariant_by_geometry")
        == EXPECTED_ORDER_INVARIANCE,
        "bounded three-parent classification changed",
    )
    _require(
        adjudication.get("full_commutativity_claimed") is False
        and adjudication.get("associativity_claimed") is False
        and adjudication.get("general_n_parent_claimed") is False
        and adjudication.get("general_transfer_claimed") is False
        and adjudication.get("automatic_follow_on") is False,
        "claim boundary changed",
    )


def _raw_sse_execution(capture: Mapping[str, Any]) -> dict[str, Any]:
    raw = capture.get("raw_response_capture")
    _require(isinstance(raw, Mapping), "raw SSE capture is unavailable")
    try:
        raw_bytes = base64.b64decode(str(raw.get("bytes", "")), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ThreeParentGlobalInvariantAdjudicationError(
            "raw SSE capture encoding changed"
        ) from exc
    events = list(
        scientific.baseline_harness.iter_sse(raw_bytes.splitlines(keepends=True))
    )
    _require(bool(events), "raw SSE stream has no events")

    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_fragments: dict[int, dict[str, Any]] = {}
    usage: dict[str, Any] = {}
    finish_reason: str | None = None
    generated_token_ids: list[int] = []
    nonempty_token_array_event_count = 0
    empty_token_array_event_count = 0
    token_merge_modes: dict[str, int] = {}
    terminal = None

    for event_index, event in enumerate(events, 1):
        if isinstance(event.get("usage"), dict):
            usage.update(event["usage"])
        incoming_terminal = scientific.baseline_harness.extract_terminal_stop_evidence(
            event, event_index=event_index
        )
        terminal = scientific.baseline_harness.merge_terminal_stop_evidence(
            terminal, incoming_terminal
        )
        event_token_ids = scientific.baseline_harness.extract_generated_token_ids(event)
        if event_token_ids is not None:
            if event_token_ids:
                nonempty_token_array_event_count += 1
            else:
                empty_token_array_event_count += 1
        generated_token_ids, merge_mode = scientific.baseline_harness.merge_generated_token_ids(
            generated_token_ids, event_token_ids
        )
        token_merge_modes[merge_mode] = token_merge_modes.get(merge_mode, 0) + 1

        choices = event.get("choices")
        if not isinstance(choices, list) or not choices:
            continue
        choice = choices[0] if isinstance(choices[0], dict) else {}
        if choice.get("finish_reason") is not None:
            finish_reason = str(choice["finish_reason"])
        delta = choice.get("delta")
        if not isinstance(delta, dict):
            continue
        content = delta.get("content")
        if isinstance(content, str) and content:
            content_parts.append(content)
        reasoning = delta.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning:
            reasoning_parts.append(reasoning)
        fragments = delta.get("tool_calls")
        if isinstance(fragments, list):
            for fragment in fragments:
                if isinstance(fragment, dict):
                    scientific.baseline_harness.merge_tool_call(tool_fragments, fragment)

    completion_tokens = usage.get("completion_tokens")
    prompt_tokens = usage.get("prompt_tokens")
    details = usage.get("prompt_tokens_details")
    cached_prompt_tokens = details.get("cached_tokens") if isinstance(details, dict) else None
    if not isinstance(completion_tokens, int):
        completion_tokens = None
    if not isinstance(prompt_tokens, int):
        prompt_tokens = None
    if not isinstance(cached_prompt_tokens, int):
        cached_prompt_tokens = None
    reconstructed = {
        "content": "".join(content_parts),
        "reasoning_content": "".join(reasoning_parts),
        "tool_calls": [tool_fragments[key] for key in sorted(tool_fragments)],
        "prompt_tokens": prompt_tokens,
        "cached_prompt_tokens": cached_prompt_tokens,
        "completion_tokens": completion_tokens,
        "generated_token_ids": generated_token_ids,
        "generated_token_count": len(generated_token_ids),
        "completion_token_count_match": (
            len(generated_token_ids) == completion_tokens
            if isinstance(completion_tokens, int)
            else None
        ),
        "generated_token_sha256": scientific.baseline_harness.token_array_sha256(
            generated_token_ids
        ),
        "nonempty_token_array_event_count": nonempty_token_array_event_count,
        "empty_token_array_event_count": empty_token_array_event_count,
        "token_merge_modes": token_merge_modes,
        "terminal_stop_evidence": terminal.to_dict() if terminal is not None else None,
        "finish_reason": finish_reason,
        "http_status": 200,
        "event_count": len(events),
    }
    _require(
        reconstructed.get("finish_reason") == "stop"
        and isinstance(reconstructed.get("terminal_stop_evidence"), Mapping)
        and reconstructed["terminal_stop_evidence"].get("observed") is True
        and reconstructed["terminal_stop_evidence"].get("stop") is True
        and reconstructed["terminal_stop_evidence"].get("stop_type") == "eos",
        "raw SSE stream did not reach the valid terminal boundary",
    )
    _require(
        reconstructed == capture.get("execution"),
        "raw SSE reconstruction differs from authenticated execution",
    )
    return reconstructed


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
    _require(isinstance(entries, list) and len(entries) == 11, "archive inventory changed")
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
    physical_files = [path for path in archive_root.rglob("*") if path.is_file()]
    _require(
        len(physical_files) == 12 and all(not path.is_symlink() for path in physical_files),
        "archive physical file count changed",
    )

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
        len(archived_events) == 27
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
    return {
        "evidence_member_count": 11,
        "physical_file_count_including_bundle": 12,
        "archived_journal_event_count": 27,
        "archived_journal_head_sha256": archived_events[-1]["event_sha256"],
        "live_journal_is_archived_prefix_plus_archive_event": True,
    }


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
        and authority.get("maximum_total_generations") == 6
        and authority.get("maximum_generations_per_request") == 1
        and authority.get("automatic_follow_on") is False
        and receipt.get("raw_authority_id_persisted") is False,
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
        len(events) == 28
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
        "request or capture journal is incomplete",
    )
    archive = _verify_archive(repository, paths, experiment_key)

    model_path_text = manifest.get("preflight", {}).get("model_identity", {}).get("path")
    _require(isinstance(model_path_text, str), "captured model identity is unavailable")
    model_path = Path(model_path_text)
    validation = probe.validate_preregistration(repository, model_path)
    _require(
        validation.get("artifact_sha256") == EXPECTED_PREREGISTRATION_SHA256
        and validation.get("frozen_scientific_binding_sha256")
        == EXPECTED_SCIENTIFIC_BINDING_SHA256
        and validation.get("controller_binding_sha256")
        == EXPECTED_CONTROLLER_BINDING_SHA256,
        "exact preregistration reconstruction changed",
    )
    tokenizer = probe.asymmetry.OfflineTokenizer(model_path)
    selection = probe.select_first_eligible(root, tokenizer)
    geometries = selection["geometries"]
    prediction_commitments = probe._prediction_commitments(root, geometries)
    expected_selected_commitments = {
        request_id: prediction_commitments[request_id]["unique-three-way-intersection"]
        for request_id in probe.REQUEST_IDS
    }

    outcomes: dict[str, dict[str, Any]] = {}
    private_selections: dict[str, str] = {}
    capture_hashes: dict[str, str] = {}
    raw_sse_event_counts: dict[str, int] = {}
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
        execution = _raw_sse_execution(capture)
        replay = scientific.replay_capture(capture)
        _require(replay.__dict__ == execution, "deterministic capture replay changed")
        outcome, selected = probe.capture_outcome(
            repository,
            root,
            private,
            geometries,
            request_id,
            capture,
            int(started[request_id]["facts"]["rendered_prompt_tokens"]),
        )
        _require(
            outcome["selected_candidate_commitment"]
            == expected_selected_commitments[request_id],
            f"frozen three-way commitment differs: {request_id}",
        )
        outcomes[request_id] = outcome
        private_selections[request_id] = selected
        capture_hashes[request_id] = capture_hash
        raw_sse_event_counts[request_id] = int(execution["event_count"])

    adjudication = probe.adjudicate_outcomes(outcomes, private_selections)
    ordered_outcomes = [outcomes[request_id] for request_id in probe.REQUEST_IDS]
    _require_exact_pattern(
        ordered_outcomes, adjudication, expected_selected_commitments
    )
    _require(
        result.get("status") == "complete"
        and result.get("completed_model_generations") == 6
        and result.get("maximum_model_generations") == 6
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
        "request_started_count": len(started),
        "capture_completed_count": len(captured),
        "raw_sse_event_counts": raw_sse_event_counts,
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
        "bounded_interpretation": BOUNDED_INTERPRETATION,
        "scope": {
            "matched_identity_disjoint_geometry_count": 2,
            "parent_count_per_geometry": 3,
            "presentation_orders": ["ABC", "BCA", "CAB"],
            "source_private_binding_reused": True,
            "source_seed_reused": True,
            "transform_only_synthetic_relational_probe": True,
            "stronger_than_pairwise_intersection_recovery": True,
            "complete_new_cycle_tested": False,
            "worker_synthesis_tested": False,
        },
        "source_execution": {
            "protected_commit": SOURCE_COMMIT,
            "authority_id_sha256": replay["authority_id_sha256"],
            "raw_authority_id_persisted": False,
            "authority_receipt_sha256": EXPECTED_HASHES["receipt"],
            "manifest_sha256": EXPECTED_HASHES["manifest"],
            "result_sha256": EXPECTED_HASHES["result"],
            "closure_sha256": EXPECTED_HASHES["closure"],
            "final_journal_sha256": EXPECTED_HASHES["journal"],
            "final_journal_head_sha256": EXPECTED_HASHES["journal_head"],
            "archived_journal_sha256": EXPECTED_HASHES["archived_journal"],
            "archived_journal_head_sha256": EXPECTED_HASHES["archived_journal_head"],
            "evidence_archive_sha256": EXPECTED_HASHES["archive"],
            "archive_evidence_member_count": replay["archive"]["evidence_member_count"],
            "archive_physical_file_count": replay["archive"][
                "physical_file_count_including_bundle"
            ],
            "capture_sha256": replay["capture_sha256"],
            "request_started_count": replay["request_started_count"],
            "capture_completed_count": replay["capture_completed_count"],
            "completed_model_generations": 6,
            "retry_count": 0,
            "cleanup_passed": True,
            "postflight_passed": True,
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
            "authenticated_captures_verified": 6,
            "raw_sse_reconstructions_verified": 6,
            "raw_sse_terminal_boundaries_verified": 6,
            "raw_sse_event_counts": replay["raw_sse_event_counts"],
            "authenticated_journal_events_verified": replay["event_count"],
            "archived_journal_events_verified": replay["archive"][
                "archived_journal_event_count"
            ],
            "journal_boundary_reconciled": replay["archive"][
                "live_journal_is_archived_prefix_plus_archive_event"
            ],
            "request_outcomes_replayed": 6,
            "terminal_result_exact_match": True,
            "controller_adjudication_exact_match": True,
            "model_requests_issued": 0,
            "sidecar_launches": 0,
            "model_generations": 0,
        },
        "observed_outcomes": replay["outcomes"],
        "mechanism_matches_all_six": dict(EXPECTED_MECHANISM_MATCHES),
        "cyclic_order_semantic_invariance": dict(EXPECTED_ORDER_INVARIANCE),
        "supported_claims": [SUPPORTED_CLASSIFICATION],
        "evidence_progression": list(PROGRESSION),
        "locked_claims": dict(LOCKED_CLAIMS),
        "next_boundary": NEXT_BOUNDARY,
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
        "checkpoint": "2-Catalytic-Kernel-0-three-parent-global-invariant-adjudication",
        "hypothesis": (
            "The transform selects an invariant identifiable only from the complete "
            "distributed three-parent relation and not from any parent or parent pair."
        ),
        "intervention": (
            "Statically verify, reconstruct, replay, and publish the completed six-request "
            "three-parent transform-only probe."
        ),
        "baseline_commit": SOURCE_COMMIT,
        "candidate_commit": None,
        "model_hash": probe.MODEL_SHA256,
        "configuration": {
            "design_id": probe.DESIGN_ID,
            "source_execution_commit": SOURCE_COMMIT,
            "source_private_binding_commitment_sha256": EXPECTED_PRIVATE_BINDING_COMMITMENT,
            "fixed_transform_seed": probe.FIXED_TRANSFORM_SEED,
            "request_count": 6,
            "request_order": list(probe.REQUEST_IDS),
            "maximum_generations_per_request": 1,
            "binary_sha256": probe.BINARY_SHA256,
            "preregistration_sha256": EXPECTED_PREREGISTRATION_SHA256,
            "frozen_scientific_binding_sha256": EXPECTED_SCIENTIFIC_BINDING_SHA256,
            "controller_binding_sha256": EXPECTED_CONTROLLER_BINDING_SHA256,
            "predecessor_record_id": probe.SOURCE_RESULT_RECORD_ID,
            "predecessor_record_sha256": probe.SOURCE_RESULT_RECORD_SHA256,
            "pairwise_operation_record_id": PAIRWISE_RECORD_ID,
            "pairwise_operation_record_sha256": PAIRWISE_RECORD_SHA256,
            "joint_parent_information_record_id": POSITION_RECORD_ID,
            "joint_parent_information_record_sha256": POSITION_RECORD_SHA256,
            "evidence_progression": list(PROGRESSION),
        },
        "metrics_before": {
            "pairwise_operation_identified": True,
            "combined_new_binding_and_seed_replication_published": True,
            "three_parent_global_invariant_result_published": False,
        },
        "metrics_after": {
            "status": "adjudicated",
            "terminal_execution_status": "complete",
            "completed_model_generations_in_source_execution": 6,
            "zero_contact_replay_generations": 0,
            "terminal_classification": SUPPORTED_CLASSIFICATION,
            "bounded_interpretation": BOUNDED_INTERPRETATION,
            "observed_outcomes": adjudication["observed_outcomes"],
            "mechanism_matches_all_six": dict(EXPECTED_MECHANISM_MATCHES),
            "semantic_selection_order_invariant_by_geometry": dict(
                EXPECTED_ORDER_INVARIANCE
            ),
            "authority_receipt_sha256": EXPECTED_HASHES["receipt"],
            "manifest_sha256": EXPECTED_HASHES["manifest"],
            "result_sha256": EXPECTED_HASHES["result"],
            "closure_sha256": EXPECTED_HASHES["closure"],
            "journal_sha256": EXPECTED_HASHES["journal"],
            "journal_head_sha256": EXPECTED_HASHES["journal_head"],
            "archived_journal_sha256": EXPECTED_HASHES["archived_journal"],
            "evidence_archive_sha256": EXPECTED_HASHES["archive"],
            "archive_evidence_member_count": 11,
            "archive_physical_file_count": 12,
            "capture_sha256": dict(EXPECTED_CAPTURE_HASHES),
            "adjudication_artifact_sha256": artifact_sha256,
        },
        "quality_gates": {
            "authority_receipt_hmac_verified": True,
            "raw_authority_id_not_persisted": True,
            "archive_and_all_eleven_evidence_members_verified": True,
            "all_six_captures_authenticated": True,
            "raw_sse_reconstruction_exact": True,
            "all_six_raw_stream_terminal_boundaries_valid": True,
            "zero_contact_replay_exact": True,
            "frozen_three_way_commitments_matched_all_six": True,
            "controller_classification_supported": True,
            "transform_only_synthetic_relational_probe": True,
            "worker_synthesis_locked": True,
            "general_catalytic_inference_locked": True,
            "complete_new_cycle_locked": True,
            "task_advantage_locked": True,
            "reduced_fresh_computation_locked": True,
            "compute_amplification_locked": True,
            "no_disclosure": True,
            "automatic_promotion": False,
        },
        "verdict": "accept",
        "next_boundary": NEXT_BOUNDARY,
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
    lines = (repository / RESULTS_PATH).read_text(encoding="utf-8").splitlines()
    _require(
        len(lines) == EXPECTED_LEDGER_LINE
        and json.loads(lines[EXPECTED_LEDGER_LINE - 2]).get("id")
        == PREDECESSOR_RECORD_ID
        and json.loads(lines[EXPECTED_LEDGER_LINE - 1]).get("id") == RECORD_ID,
        "ledger predecessor or expected line changed",
    )
    matches: list[tuple[int, str, dict[str, Any]]] = []
    for line_number, line in enumerate(lines, 1):
        value = json.loads(line)
        if isinstance(value, dict) and value.get("id") == RECORD_ID:
            matches.append((line_number, line, value))
    _require(len(matches) == 1, "publication must contain exactly one record")
    line_number, line, value = matches[0]
    _require(
        line_number == EXPECTED_LEDGER_LINE
        and line == expected_line
        and value == expected_record,
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
        "archive_evidence_member_count": 11,
        "archive_physical_file_count": 12,
        "capture_count": 6,
        "raw_sse_reconstruction_count": 6,
        "valid_terminal_boundary_count": 6,
        "zero_contact_replay": True,
        "next_boundary": NEXT_BOUNDARY,
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
        ThreeParentGlobalInvariantAdjudicationError,
        probe.ThreeParentGlobalInvariantProbeError,
        scientific.ScientificSurfaceError,
        scientific.baseline_harness.HarnessError,
    ) as exc:
        print(canonical_json_text({"status": "fail", "error": str(exc)}))
        return 1
    print(canonical_json_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
