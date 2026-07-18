#!/usr/bin/env python3
"""Static recovery of authenticated parent-dependence captures.

This module never dispatches a request.  It preserves the original terminal
result as inconclusive, verifies the archived preterminal captures, freezes
both rank heads before either private mapping, and renders a separate bounded
forensic adjudication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Mapping
from unittest import mock

import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2_parent_dependence as parent
import catalytic_kernel_0_balanced_rank_head_v2_parent_dependence_scientific as scientific


ARTIFACT_ID = "ck0-balanced-v2-rank-head-b2-parent-dependence-forensic-recovery-1"
ARTIFACT_PATH = Path(
    "lab/ck0_balanced_opaque_rank_head_v2_binding_2_parent_dependence_forensic_recovery_1.json"
)
RECOVERY_STATUS = "BINDING_2_PARENT_DEPENDENCE_FORENSIC_RECOVERY_SUPPORTED"
ORIGINAL_AUTHORIZED_EXECUTION_COMMIT = "b60ebf06e87da2fb37cb482ef1d11d2584c21c50"
LIVE_CONTROLLER_REPAIR_COMMIT = "29173af5cfc6d69d9095669ad3a9a68084de0d11"
ORIGINAL_FAILURE_SHA256 = "36D3843CE9B6F9A8F14C54CF139F8E505E457145C99847316C38FC2C632F32DF"
ORIGINAL_ARCHIVE_SHA256 = "7BDA5B9EF4CEAA8EEB4157DF2D47644554F11551EB10DF354B4DD59F55693E1C"
FROZEN_SCIENTIFIC_EXECUTION_BINDING_SHA256 = "F084C1BE1FB5E90C33DEB15F60D969F8B24B23DB13E27A6066360B9CC0FFA1F3"
ORIGINAL_EVIDENCE_SHA256 = {
    "authority_receipt": "24A44944305F43C536949F97CE162C62EC7A7587919F9567DDEE7AAD5319C45B",
    "capture_delete_parent_0": "B40EE6AE95C07AD8BBE1DF7D17F54DCF42D71EDC1E1FE0AF2F6B2B534506E0A4",
    "capture_delete_parent_1": "88693E8F8956B4A34C2A8C5F5AE3E4EFE1A449D6FCD2615B41DB55A688D83566",
    "manifest": "D88AD20F6B5F65A27ECF821017C9D562FD7BBBBD5CBB09A38D4FE1417DB752B3",
    "result": "D4398AC9D5D6228F3B12DD35F2A1698A5B10B7B442A28EAC2A20011AD78BC635",
    "closure": "A8699F1A144985EAD347DE9C2ADEDA699BC3EDF31196FAE46C9D87660CCA88E1",
}
ORIGINAL_AUTHORITY_ID_SHA256 = "5F653EF4C660D8C63376D700ED6A7F90F6AF255274939DBBFF46D23C749DB033"
ORIGINAL_AUTHORITY_HMAC_SHA256 = "B543579CE78A496E34B4DD116A99D47845F9DE1D2E0140EE04D03E01C6E11F6B"
JOURNAL_PREFIX_EVENT_COUNT = 9
JOURNAL_PREFIX_HEAD_SHA256 = "6518DF5D9E79E2A65D9A83F162273B71B9883E37A52F0F006856CBE0E2C15940"
ORIGINAL_TERMINAL_EVENT_SHA256 = "A59D60B9C1B3C8A7E5B98E4F51CC731C1CA0D5156DDFE9D07CAA186558C4E87B"

SUPPORTED_CLAIMS = (
    "BINDING_2_PARENT_A_INFORMATION_DEPENDENCE_SUPPORTED",
    "BINDING_2_PARENT_B_INFORMATION_DEPENDENCE_NOT_SHOWN",
    "DIRECTIONAL_PARENT_A_INFORMATION_DEPENDENCE_REPLICATED_ACROSS_TWO_PRIVATE_BINDINGS",
)
LOCKED_CLAIMS = {
    "BINDING_2_PARENT_B_INFORMATION_DEPENDENCE_SUPPORTED": "LOCKED_NOT_SUPPORTED_BY_RECOVERED_ARM",
    "BILATERAL_PARENT_DEPENDENCE_REPLICATED_ON_FROZEN_BALANCED_OPAQUE_GEOMETRY": "LOCKED",
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


class ForensicRecoveryError(RuntimeError):
    """The static recovery evidence is absent, changed, or overclaims."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ForensicRecoveryError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def json_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _json_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ForensicRecoveryError(f"{label} is malformed") from exc
    _require(isinstance(value, dict), f"{label} is not an object")
    return value


def original_archive_path(repository: Path) -> Path:
    return (
        repository
        / parent.ARCHIVE_ROOT
        / parent.EXPERIMENT_ID
        / ORIGINAL_ARCHIVE_SHA256
    )


def _archive_member_map(verified: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    bundle = verified.get("bundle")
    _require(isinstance(bundle, Mapping), "terminal archive bundle is malformed")
    files = bundle.get("files")
    _require(isinstance(files, list), "terminal archive file inventory is malformed")
    return {
        str(item["name"]): dict(item)
        for item in files
        if isinstance(item, Mapping) and isinstance(item.get("name"), str)
    }


def _verify_original_truth(repository: Path) -> tuple[Path, list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    archive = original_archive_path(repository)
    verified = parent.verify_archive(repository, archive)
    _require(
        verified.get("bundle_sha256") == ORIGINAL_ARCHIVE_SHA256,
        "original terminal archive changed",
    )
    members = _archive_member_map(verified)
    expected_members = {
        "receipt": ORIGINAL_EVIDENCE_SHA256["authority_receipt"],
        "capture-delete-parent-0": ORIGINAL_EVIDENCE_SHA256["capture_delete_parent_0"],
        "capture-delete-parent-1": ORIGINAL_EVIDENCE_SHA256["capture_delete_parent_1"],
        "manifest": ORIGINAL_EVIDENCE_SHA256["manifest"],
        "result": ORIGINAL_EVIDENCE_SHA256["result"],
        "closure": ORIGINAL_EVIDENCE_SHA256["closure"],
    }
    for name, expected in expected_members.items():
        _require(
            isinstance(members.get(name), Mapping)
            and members[name].get("sha256") == expected,
            f"original archive member changed: {name}",
        )
    paths = parent.state_paths(repository)
    live_to_archive = {
        paths["receipt"]: archive / "authority-receipt.json",
        paths["manifest"]: archive / "manifest.json",
        paths["result"]: archive / "result.json",
        paths["closure"]: archive / "closure.json",
        paths["capture-delete-parent-0"]: archive / "capture-delete-parent-0.json",
        paths["capture-delete-parent-1"]: archive / "capture-delete-parent-1.json",
    }
    for live, archived in live_to_archive.items():
        _require(
            live.is_file() and not live.is_symlink() and live.read_bytes() == archived.read_bytes(),
            f"live evidence differs from immutable archive: {live.name}",
        )
    archived_journal = (archive / "journal.jsonl").read_bytes()
    live_journal = paths["journal"].read_bytes()
    _require(
        live_journal.startswith(archived_journal),
        "live journal does not preserve the terminal archive prefix",
    )
    events = parent.verify_journal_bytes(
        archived_journal,
        repository=repository,
        allow_archived=False,
    )
    _require(
        len(events) == 13
        and events[-1]["state"] == "terminal-written"
        and events[-1]["event_sha256"] == ORIGINAL_TERMINAL_EVENT_SHA256,
        "original terminal journal boundary changed",
    )
    result = _json_object((archive / "result.json").read_bytes(), "original result")
    closure = _json_object((archive / "closure.json").read_bytes(), "original closure")
    _require(
        result.get("status") == "inconclusive"
        and result.get("custody_gates_passed") is False
        and result.get("postflight_custody", {}).get("failure_sha256")
        == ORIGINAL_FAILURE_SHA256
        and all(
            item.get("classification") == "INCONCLUSIVE"
            and item.get("reason") == "durable-finalization-custody-gate-failed"
            for item in result.get("arm_outcomes", [])
        ),
        "original inconclusive truth changed",
    )
    _require(
        closure.get("result_sha256") == ORIGINAL_EVIDENCE_SHA256["result"]
        and closure.get("postflight_passed") is False,
        "original closure truth changed",
    )
    receipt = _json_object((archive / "authority-receipt.json").read_bytes(), "authority receipt")
    authority = receipt.get("authority")
    _require(
        isinstance(authority, Mapping)
        and authority.get("authority_id_sha256") == ORIGINAL_AUTHORITY_ID_SHA256
        and authority.get("authorized_commit") == ORIGINAL_AUTHORIZED_EXECUTION_COMMIT
        and authority.get("frozen_scientific_execution_binding_sha256")
        == FROZEN_SCIENTIFIC_EXECUTION_BINDING_SHA256
        and receipt.get("authority_hmac") == ORIGINAL_AUTHORITY_HMAC_SHA256,
        "original authority binding changed",
    )
    return archive, events, result, receipt


def _tamper_rejection_facts(
    repository: Path,
    archive: Path,
    events: list[dict[str, Any]],
    experiment_key: bytes,
) -> dict[str, bool]:
    capture_rejections: dict[str, bool] = {}
    for arm_id in parent.ARM_IDS:
        started = parent._event_for(events, "request-started", arm_id)
        _require(started is not None, "request-started event is absent")
        original = (archive / f"capture-{arm_id}.json").read_bytes()
        tampered = bytearray(original)
        tampered[-2] ^= 1
        with tempfile.TemporaryDirectory(prefix="neo3000-parent-capture-tamper-") as temp:
            path = Path(temp) / f"capture-{arm_id}.json"
            path.write_bytes(bytes(tampered))
            try:
                scientific.verify_capture(
                    path,
                    experiment_key=experiment_key,
                    arm_id=arm_id,
                    model_request_sha256=str(started["facts"]["model_request_sha256"]),
                )
            except scientific.ScientificSurfaceError:
                capture_rejections[arm_id] = True
            else:
                capture_rejections[arm_id] = False
    journal_bytes = (archive / "journal.jsonl").read_bytes()
    tampered_journal = bytearray(journal_bytes)
    tampered_journal[0] ^= 1
    try:
        parent.verify_journal_bytes(
            bytes(tampered_journal),
            repository=repository,
            allow_archived=False,
        )
    except parent.ParentDependenceError:
        journal_rejected = True
    else:
        journal_rejected = False
    source_payloads = parent._source_payloads(repository)
    tampered_source_payloads = dict(source_payloads)
    tampered_source_payloads["result"] = source_payloads["result"] + b"x"
    with mock.patch.object(
        parent,
        "_source_payloads",
        return_value=tampered_source_payloads,
    ):
        try:
            parent.verify_source_evidence(repository)
        except parent.ParentDependenceError:
            source_archive_rejected = True
        else:
            source_archive_rejected = False
    publication_projection = parent.publication.validate_publication(
        repository,
        parent.SOURCE_RUN_ID,
    )
    tampered_publication_projection = dict(publication_projection)
    tampered_publication_projection["record_sha256"] = "0" * 64
    with mock.patch.object(
        parent.publication,
        "validate_publication",
        return_value=tampered_publication_projection,
    ):
        try:
            parent.verify_source_evidence(repository)
        except parent.ParentDependenceError:
            source_publication_rejected = True
        else:
            source_publication_rejected = False
    return {
        "capture_delete_parent_0_tamper_rejected": capture_rejections["delete-parent-0"],
        "capture_delete_parent_1_tamper_rejected": capture_rejections["delete-parent-1"],
        "journal_prefix_tamper_rejected": journal_rejected,
        "source_archive_member_tamper_rejected": source_archive_rejected,
        "source_publication_record_tamper_rejected": source_publication_rejected,
    }


def _replay_arms(
    repository: Path,
    archive: Path,
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, bool]]:
    experiment_key = parent._experiment_key(parent._source_runtime(repository))
    frozen: dict[str, tuple[Any, dict[str, Any], Any, dict[str, Any]]] = {}
    capture_facts: dict[str, dict[str, Any]] = {}
    for arm_id in parent.ARM_IDS:
        started = parent._event_for(events, "request-started", arm_id)
        captured = parent._event_for(events, "response-captured", arm_id)
        _require(started is not None and captured is not None, "arm lacks durable request/capture")
        request_sha = str(started["facts"]["model_request_sha256"])
        _require(
            request_sha == scientific.EXPECTED_ARM_REQUEST_SHA256[arm_id],
            "captured arm request identity changed",
        )
        path = archive / f"capture-{arm_id}.json"
        capture = scientific.verify_capture(
            path,
            experiment_key=experiment_key,
            arm_id=arm_id,
            model_request_sha256=request_sha,
        )
        _require(
            capture["capture_sha256"] == captured["facts"].get("capture_sha256"),
            "capture differs from journal binding",
        )
        frozen[arm_id] = parent._freeze_captured_arm(
            repository,
            arm_id,
            capture,
            int(started["facts"]["rendered_prompt_tokens"]),
        )
        capture_facts[arm_id] = {
            "capture_sha256": capture["capture_sha256"],
            "model_request_sha256": request_sha,
            "captured_before_parsing": capture["captured_before_parsing"],
        }
    _require(set(frozen) == set(parent.ARM_IDS), "both-head freeze barrier failed")
    arms: list[dict[str, Any]] = []
    for arm_id in parent.ARM_IDS:
        runtime, transform, selected, transport = frozen[arm_id]
        facts = parent._adjudicate_frozen_arm(
            runtime,
            transform,
            selected,
            arm_id,
        )
        arms.append(
            {
                **capture_facts[arm_id],
                "arm_id": arm_id,
                "classification": facts["classification"],
                "transform_operator": facts["transform_operator"],
                "transform_artifact_commitment": facts[
                    "transform_artifact_commitment"
                ],
                "transform_ranking_length": facts["transform_ranking_length"],
                "selection_frozen_before_private_mapping": facts[
                    "selection_frozen_before_private_mapping"
                ],
                "private_mapping_consulted_before_selection": facts[
                    "private_mapping_consulted_before_selection"
                ],
                "selected_rank": facts["selected_rank"],
                "selected_own_private_singleton": facts[
                    "selected_own_private_singleton"
                ],
                "private_public_score": facts["private_public_score"],
                "private_public_total": facts["private_public_total"],
                "deterministic_extraction_commitment": facts[
                    "deterministic_extraction_commitment"
                ],
                "transport": {
                    "http_status": transport["http_status"],
                    "prompt_tokens": transport["prompt_tokens"],
                    "cached_prompt_tokens": transport["cached_prompt_tokens"],
                    "fresh_prompt_tokens": transport["fresh_prompt_tokens"],
                    "completion_tokens": transport["completion_tokens"],
                    "finish_reason": transport["finish_reason"],
                    "generated_token_evidence_mode": transport[
                        "generated_token_evidence_mode"
                    ],
                },
            }
        )
    return arms, _tamper_rejection_facts(repository, archive, events, experiment_key)


def render_forensic_recovery(repository: Path) -> dict[str, Any]:
    repository = repository.resolve()
    archive, events, original_result, receipt = _verify_original_truth(repository)
    source = parent.verify_source_evidence(repository)
    arms, tamper = _replay_arms(repository, archive, events)
    states = [event["state"] for event in events]
    prefix = events[:JOURNAL_PREFIX_EVENT_COUNT]
    _require(
        prefix[-1]["event_sha256"] == JOURNAL_PREFIX_HEAD_SHA256
        and states.count("request-started") == 2
        and states.count("response-captured") == 2,
        "preterminal generation accounting changed",
    )
    _require(
        arms[0]["classification"]
        == "BINDING_2_PARENT_A_INFORMATION_DEPENDENCE_SUPPORTED"
        and arms[1]["classification"]
        == "BINDING_2_PARENT_B_INFORMATION_DEPENDENCE_NOT_SHOWN",
        "recovered arm classifications changed",
    )
    controller_path = parent.state_paths(repository)["controller_lock"]
    _require(
        controller_path in parent._runtime_allowed_paths(parent.state_paths(repository)),
        "future controller lock is not exactly custody-admitted",
    )
    controller_sources = {
        relative: sha256_bytes((repository / relative).read_bytes())
        for relative in (
            "scripts/catalytic_kernel_0_balanced_rank_head_v2_parent_dependence.py",
            "scripts/catalytic_runtime_custody.py",
        )
    }
    reproduction = {
        "repository_commit": LIVE_CONTROLLER_REPAIR_COMMIT,
        "reconstructed_boundary": "after-two-request-custody-events-before-finalization",
        "journal_prefix_event_count": JOURNAL_PREFIX_EVENT_COUNT,
        "journal_prefix_head_sha256": JOURNAL_PREFIX_HEAD_SHA256,
        "active_run_lock_retained": True,
        "active_controller_lock_retained": True,
        "result_absent_at_reconstruction": True,
        "closure_absent_at_reconstruction": True,
        "original_exception_sha256": ORIGINAL_FAILURE_SHA256,
        "bounded_failure_classification": "CONTROLLER_OWNED_ZERO_BYTE_LOCK_READ_DENIED_DURING_POSTCLAIM_INVENTORY",
        "controller_lock_sole_illegal_changed_path": True,
        "removing_only_controller_lock_made_original_validator_pass": True,
        "unrelated_file_removal_did_not_change_failure_identity": True,
        "corrected_postflight_custody_passed": True,
        "raw_exception_published": False,
        "model_generations": 0,
    }
    reproduction["commitment_sha256"] = json_sha256(reproduction)
    manifest = _json_object((archive / "manifest.json").read_bytes(), "manifest")
    public_preflight = manifest.get("public_preflight")
    _require(isinstance(public_preflight, Mapping), "public preflight is absent")
    document: dict[str, Any] = {
        "schema_version": 1,
        "artifact_id": ARTIFACT_ID,
        "status": RECOVERY_STATUS,
        "scope": (
            "Static adjudication of authenticated preterminal captures after exact "
            "reproduction of a controller-lock custody false negative."
        ),
        "original_execution_truth": {
            "status": "INCONCLUSIVE",
            "reason": "durable-finalization-custody-gate-failed",
            "result_and_archive_rewritten": False,
            "original_authorized_execution_commit": ORIGINAL_AUTHORIZED_EXECUTION_COMMIT,
            "live_controller_repair_commit": LIVE_CONTROLLER_REPAIR_COMMIT,
            "authority_id_sha256": ORIGINAL_AUTHORITY_ID_SHA256,
            "authority_receipt_sha256": ORIGINAL_EVIDENCE_SHA256[
                "authority_receipt"
            ],
            "authority_hmac_sha256": receipt["authority_hmac"],
            "frozen_scientific_execution_binding_sha256": FROZEN_SCIENTIFIC_EXECUTION_BINDING_SHA256,
            "manifest_sha256": ORIGINAL_EVIDENCE_SHA256["manifest"],
            "result_sha256": ORIGINAL_EVIDENCE_SHA256["result"],
            "closure_sha256": ORIGINAL_EVIDENCE_SHA256["closure"],
            "archive_sha256": ORIGINAL_ARCHIVE_SHA256,
            "terminal_event_sha256": ORIGINAL_TERMINAL_EVENT_SHA256,
            "completed_model_generations": original_result[
                "completed_model_generations"
            ],
            "maximum_model_generations": original_result[
                "maximum_model_generations"
            ],
        },
        "failure_isolation": {
            **reproduction,
            "cleanup_passed": original_result["cleanup"]["passed"],
            "request_custody_passed": original_result["cleanup"][
                "request_custody_passed"
            ],
            "stable_preserved": original_result["cleanup"]["stable_preserved"],
            "candidate_head": public_preflight["candidate"]["head"],
            "candidate_status_sha256": public_preflight["candidate"][
                "status_sha256"
            ],
            "stable_head": public_preflight["stable"]["head"],
            "stable_status_sha256": public_preflight["stable"][
                "status_sha256"
            ],
            "historical_custody_sha256": public_preflight[
                "historical_cs1_sha256"
            ],
            "source_archive_verified": source["source_hashes"]["archive"]
            == parent.SOURCE_ARCHIVE_SHA256,
            "source_publication_verified": source["source_publication"][
                "record_sha256"
            ]
            == parent.SOURCE_PUBLICATION_SHA256,
            "tamper_rejections": tamper,
        },
        "future_controller_repair": {
            "strategy": "exact-control-lock-custody-admission-with-stable-empty-file-fingerprint",
            "controller_lock_relative_path": controller_path.relative_to(
                repository
            ).as_posix(),
            "controller_lock_exactly_allowlisted": True,
            "controller_lock_scientific_evidence": False,
            "controller_lock_archived": False,
            "mutual_exclusion_preserved": True,
            "removed_before_final_clean_state": True,
            "broad_directory_authorization_added": False,
            "arbitrary_temporary_path_authorized": False,
            "controller_source_sha256": controller_sources,
            "frozen_scientific_module_sha256": FROZEN_SCIENTIFIC_EXECUTION_BINDING_SHA256,
        },
        "forensic_replay": {
            "source": "authenticated-preterminal-captures",
            "model_generations_during_recovery": 0,
            "http_requests_during_recovery": 0,
            "sidecar_launches_during_recovery": 0,
            "authority_created_or_consumed_during_recovery": False,
            "request_started_event_count": states.count("request-started"),
            "response_captured_event_count": states.count("response-captured"),
            "duplicate_generation_detected": False,
            "both_responses_durably_captured_before_parsing": all(
                item["captured_before_parsing"] is True for item in arms
            ),
            "both_rank_heads_frozen_before_any_private_mapping": True,
            "arms": arms,
        },
        "cross_binding_causal_adjudication": {
            "historical_binding_1_causal_package_sha256": parent.BINDING_1_CAUSAL_SHA256,
            "historical_binding_1_package_sha256": parent.BINDING_1_PACKAGE_SHA256,
            "historical_binding_1_verified_byte_exact": True,
            "qualifier": (
                "Derived from authenticated preterminal captures after a proven "
                "controller-lock custody false negative."
            ),
            "supported_claims": list(SUPPORTED_CLAIMS),
            "bilateral_replication_supported": False,
            "locked_claims": dict(LOCKED_CLAIMS),
        },
        "no_smuggle": {
            "private_alias_persisted": False,
            "transform_rankings_persisted": False,
            "private_mapping_persisted": False,
            "private_root_persisted": False,
            "cross_binding_correspondence_persisted": False,
            "raw_response_persisted_in_tracked_artifact": False,
            "raw_exception_published": False,
            "bounded_metadata_only": True,
        },
        "next_boundary": (
            "Preserve this narrow directional-A recovery; any future independent "
            "causal experiment requires separate static design and fresh authority. "
            "Do not retry either consumed arm."
        ),
    }
    _validate_shape(document)
    parent._assert_public_no_smuggle(document)
    balanced.validate_metadata_only(document)
    return document


def _validate_shape(document: Mapping[str, Any]) -> None:
    _require(
        set(document)
        == {
            "schema_version",
            "artifact_id",
            "status",
            "scope",
            "original_execution_truth",
            "failure_isolation",
            "future_controller_repair",
            "forensic_replay",
            "cross_binding_causal_adjudication",
            "no_smuggle",
            "next_boundary",
        },
        "forensic artifact layout changed",
    )
    _require(
        document.get("schema_version") == 1
        and document.get("artifact_id") == ARTIFACT_ID
        and document.get("status") == RECOVERY_STATUS,
        "forensic artifact identity changed",
    )
    original = document.get("original_execution_truth")
    replay = document.get("forensic_replay")
    cross = document.get("cross_binding_causal_adjudication")
    _require(
        isinstance(original, Mapping)
        and original.get("status") == "INCONCLUSIVE"
        and original.get("result_and_archive_rewritten") is False,
        "original execution truth was rewritten",
    )
    _require(
        isinstance(replay, Mapping)
        and replay.get("model_generations_during_recovery") == 0
        and replay.get("both_rank_heads_frozen_before_any_private_mapping") is True
        and isinstance(replay.get("arms"), list)
        and len(replay["arms"]) == 2,
        "forensic replay boundary changed",
    )
    _require(
        isinstance(cross, Mapping)
        and cross.get("supported_claims") == list(SUPPORTED_CLAIMS)
        and cross.get("locked_claims") == LOCKED_CLAIMS
        and cross.get("bilateral_replication_supported") is False,
        "forensic claim boundary changed",
    )


def validate_forensic_recovery(repository: Path) -> dict[str, Any]:
    repository = repository.resolve()
    rendered = render_forensic_recovery(repository)
    path = repository / ARTIFACT_PATH
    _require(path.is_file() and not path.is_symlink(), "forensic artifact is absent or unsafe")
    expected = canonical_json_bytes(rendered) + b"\n"
    observed = path.read_bytes()
    _require(observed == expected, "forensic artifact differs from independent render")
    return {
        "status": "pass",
        "artifact_id": ARTIFACT_ID,
        "artifact_status": RECOVERY_STATUS,
        "artifact": ARTIFACT_PATH.as_posix(),
        "artifact_sha256": sha256_bytes(observed),
        "original_failure_sha256": ORIGINAL_FAILURE_SHA256,
        "recovered_arm_classifications": {
            item["arm_id"]: item["classification"]
            for item in rendered["forensic_replay"]["arms"]
        },
        "supported_claims": list(SUPPORTED_CLAIMS),
        "locked_claims": dict(LOCKED_CLAIMS),
        "model_generations_during_recovery": 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("render", "validate"))
    parser.add_argument("--repository", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository = Path(args.repository)
    if args.action == "render":
        result = render_forensic_recovery(repository)
    else:
        result = validate_forensic_recovery(repository)
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
