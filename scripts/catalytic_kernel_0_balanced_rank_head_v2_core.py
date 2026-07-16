#!/usr/bin/env python3
"""Static design and deterministic readout helpers for balanced opaque CK0 v2.

This module does not launch a process, contact a model, create a secret, reserve a
run, or grant live authority. It preserves the frozen v1 transform mechanism and
defines only the controller-native rank-head extraction boundary selected by the
published transform/extraction adjudication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import catalytic_kernel_0_balanced_opaque as balanced


DESIGN_ID = "balanced-opaque-relational-carrier-v2-deterministic-rank-head-extraction"
DESIGN_SCHEMA_VERSION = 1
STARTING_PROTECTED_MAIN = "a774ab44c42e31ac500d13bba9accdceb5ef5b9b"
PREREGISTRATION_PATH = (
    "lab/ck0_balanced_opaque_relational_carrier_v2_"
    "deterministic_rank_head_extraction.json"
)
ADJUDICATION_PATH = "lab/ck0_balanced_opaque_transform_extraction_adjudication_2.md"
COUNTERFACTUAL_PATH = "lab/ck0_balanced_opaque_rank_head_counterfactual_1.json"
FORENSIC_PATH = "lab/ck0_binding2_preregistration_byte_forensics_1.json"
FROZEN_RUNTIME_PATH = "scripts/catalytic_kernel_0_balanced_opaque.py"
BINDING_1_PREREGISTRATION_PATH = "lab/ck0_balanced_opaque_relational_carrier_v1.json"
BINDING_2_PREREGISTRATION_PATH = (
    "lab/ck0_balanced_opaque_relational_carrier_v1_binding_2.json"
)
CUSTODY_QUALIFIER = (
    "EXECUTION_PREREGISTRATION_SEMANTIC_IDENTITY_VERIFIED_"
    "BYTE_SERIALIZATION_UNRECOVERED"
)
SELECTED_OUTCOME = "IMPLEMENT_DETERMINISTIC_RANK_HEAD_EXTRACTION"
SELECTED_LANE = "LANE_A_CONTROLLER_NATIVE_DETERMINISTIC_RANK_HEAD_EXTRACTION"
NO_SMUGGLE_STATUS = "DETERMINISTIC_RANK_HEAD_EXTRACTION_NO_SMUGGLE_PASS"
EXTRACTION_CONTRACT_FINDING = (
    "EXTRACTION_CONTRACT_UNDERSPECIFIED_RELATIVE_TO_ACCEPTANCE_LAW"
)
STAGE_SPECIFIC_STATUS = (
    "BALANCED_OPAQUE_TRANSFORM_STAGE_SINGLETON_RESOLUTION_REPLICATED_"
    "ACROSS_TWO_PRIVATE_BINDINGS_ON_FROZEN_GEOMETRY"
)
EXTRACTION_STAGE_STATUS = (
    "MODEL_AUTHORED_EXTRACTION_CLOSURE_NOT_REPLICATED_ACROSS_PRIVATE_BINDINGS"
)

LOGICAL_STAGES = (
    "borrow",
    "branch-a",
    "branch-b",
    "transform",
    "extract",
    "restore",
)
MODEL_REQUEST_STAGES = (
    "borrow",
    "branch-a",
    "branch-b",
    "transform",
    "restore",
)
SELECTION_LAW = "verified-transform-ranking-position-zero-before-private-mapping"
SELECTION_ORDER = (
    "verify-transform-artifact-shape",
    "verify-transform-run-bound-commitment",
    "freeze-ranking-position-zero",
    "bind-frozen-alias-rank-transform-commitment-and-ranking-length",
    "consult-private-mapping-after-selection",
    "score-frozen-alias-only",
    "construct-deterministic-extraction-receipt",
    "verify-deterministic-extraction-receipt",
)
EXTRACTION_MODE = "controller-deterministic-rank-head"
RECEIPT_SCHEMA_VERSION = "deterministic-rank-head-extraction-v2"
RECEIPT_STAGE_ID = "extract-rank-head-v2"
SELECTED_RANK = 0
SHA256_RE = balanced.SHA256_RE

DETERMINISTIC_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "stage_id",
        "extraction_mode",
        "selection_law",
        "selected_rank",
        "candidate_alias",
        "transform_artifact_commitment_consumed",
        "transform_ranking_length",
        "selection_frozen_before_private_mapping",
        "private_mapping_consulted_before_selection",
        "controller_private_evaluation",
        "artifact_commitment",
    }
)


class RankHeadDesignError(ValueError):
    """The deterministic rank-head design or receipt is malformed."""


@dataclass(frozen=True)
class FrozenRankHeadSelection:
    """Rank-head selection frozen before any private alias mapping or scoring."""

    candidate_alias: str
    selected_rank: int
    transform_artifact_commitment_consumed: str
    transform_ranking_length: int
    selection_law: str = SELECTION_LAW
    selection_frozen_before_private_mapping: bool = True
    private_mapping_consulted_before_selection: bool = False

    def body(self) -> dict[str, Any]:
        return {
            "candidate_alias": self.candidate_alias,
            "selected_rank": self.selected_rank,
            "transform_artifact_commitment_consumed": (
                self.transform_artifact_commitment_consumed
            ),
            "transform_ranking_length": self.transform_ranking_length,
            "selection_law": self.selection_law,
            "selection_frozen_before_private_mapping": (
                self.selection_frozen_before_private_mapping
            ),
            "private_mapping_consulted_before_selection": (
                self.private_mapping_consulted_before_selection
            ),
        }


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def json_sha256(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def deterministic_extraction_receipt_schema() -> dict[str, Any]:
    alias_schema = {"enum": list(balanced.ALIASES), "type": "string"}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(DETERMINISTIC_RECEIPT_FIELDS),
        "properties": {
            "schema_version": {"const": RECEIPT_SCHEMA_VERSION, "type": "string"},
            "stage_id": {"const": RECEIPT_STAGE_ID, "type": "string"},
            "extraction_mode": {"const": EXTRACTION_MODE, "type": "string"},
            "selection_law": {"const": SELECTION_LAW, "type": "string"},
            "selected_rank": {"const": SELECTED_RANK, "type": "integer"},
            "candidate_alias": alias_schema,
            "transform_artifact_commitment_consumed": {
                "pattern": "^[0-9A-F]{64}$",
                "type": "string",
            },
            "transform_ranking_length": {
                "minimum": 1,
                "maximum": 3,
                "type": "integer",
            },
            "selection_frozen_before_private_mapping": {
                "const": True,
                "type": "boolean",
            },
            "private_mapping_consulted_before_selection": {
                "const": False,
                "type": "boolean",
            },
            "controller_private_evaluation": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "mapped_to_full_public_support",
                    "full_public_score",
                    "full_public_total",
                ],
                "properties": {
                    "mapped_to_full_public_support": {"type": "boolean"},
                    "full_public_score": {
                        "minimum": 0,
                        "maximum": 5,
                        "type": "integer",
                    },
                    "full_public_total": {"const": 5, "type": "integer"},
                },
            },
            "artifact_commitment": {
                "pattern": "^[0-9A-F]{64}$",
                "type": "string",
            },
        },
    }


def receipt_schema_sha256() -> str:
    return json_sha256(deterministic_extraction_receipt_schema())


def freeze_rank_head_selection(
    runtime: "balanced.BalancedOpaqueRuntime",
    transform: Mapping[str, Any],
) -> FrozenRankHeadSelection:
    """Verify the transform commitment, then freeze position zero without mapping."""

    runtime.verify_transform_artifact(transform)
    ranking = transform.get("ranking")
    if not isinstance(ranking, list) or not ranking:
        raise RankHeadDesignError("verified transform ranking is empty")
    commitment = transform.get("artifact_commitment")
    if not isinstance(commitment, str) or not SHA256_RE.fullmatch(commitment):
        raise RankHeadDesignError("verified transform commitment is invalid")
    candidate_alias = ranking[SELECTED_RANK]
    if candidate_alias not in balanced.ALIASES:
        raise RankHeadDesignError("rank-head alias is outside the opaque vocabulary")
    frozen = FrozenRankHeadSelection(
        candidate_alias=str(candidate_alias),
        selected_rank=SELECTED_RANK,
        transform_artifact_commitment_consumed=commitment,
        transform_ranking_length=len(ranking),
    )
    balanced.validate_metadata_only(frozen.body())
    return frozen


def _private_evaluation(
    runtime: "balanced.BalancedOpaqueRuntime",
    candidate_alias: str,
) -> dict[str, Any]:
    task = balanced.build_frozen_task_suite().tasks[balanced.TASK_INDEX]
    try:
        internal = runtime.private.alias_to_internal[candidate_alias]
    except KeyError as exc:
        raise RankHeadDesignError("frozen alias is absent from the private binding") from exc
    candidate = next(
        (item for item in task.candidates if item.candidate_id == internal),
        None,
    )
    if candidate is None:
        raise RankHeadDesignError("private candidate is absent from the frozen suite")
    score = sum(
        balanced.execute_program(candidate, example.x) == example.y
        for example in task.public_examples
    )
    return {
        "mapped_to_full_public_support": (
            internal == balanced.EXPECTED_FULL_SUPPORT[0]
        ),
        "full_public_score": score,
        "full_public_total": 5,
    }


def build_deterministic_extraction_receipt(
    runtime: "balanced.BalancedOpaqueRuntime",
    transform: Mapping[str, Any],
    *,
    frozen: FrozenRankHeadSelection | None = None,
) -> dict[str, Any]:
    """Bind deterministic extraction after the rank head has been frozen."""

    selected = frozen or freeze_rank_head_selection(runtime, transform)
    runtime.verify_transform_artifact(transform)
    ranking = transform.get("ranking")
    if (
        not isinstance(ranking, list)
        or selected.selected_rank != SELECTED_RANK
        or selected.candidate_alias != ranking[SELECTED_RANK]
        or selected.transform_ranking_length != len(ranking)
        or selected.transform_artifact_commitment_consumed
        != transform.get("artifact_commitment")
        or selected.selection_law != SELECTION_LAW
        or selected.selection_frozen_before_private_mapping is not True
        or selected.private_mapping_consulted_before_selection is not False
    ):
        raise RankHeadDesignError("frozen rank-head selection no longer matches transform")

    # Private correspondence is consulted only after the complete selection above
    # has been frozen and checked against the committed transform.
    evaluation = _private_evaluation(runtime, selected.candidate_alias)
    commitment_body = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "stage_id": RECEIPT_STAGE_ID,
        "extraction_mode": EXTRACTION_MODE,
        **selected.body(),
        "controller_private_evaluation": evaluation,
    }
    receipt = {
        **commitment_body,
        "artifact_commitment": balanced.artifact_commitment(
            runtime.run_key,
            RECEIPT_STAGE_ID,
            commitment_body,
            runtime.configuration,
        ),
    }
    verify_deterministic_extraction_receipt(runtime, receipt, transform)
    balanced.validate_metadata_only(receipt)
    return receipt


def verify_deterministic_extraction_receipt(
    runtime: "balanced.BalancedOpaqueRuntime",
    receipt: Mapping[str, Any],
    transform: Mapping[str, Any],
) -> None:
    runtime.verify_transform_artifact(transform)
    if set(receipt) != DETERMINISTIC_RECEIPT_FIELDS:
        raise RankHeadDesignError("deterministic extraction receipt field set changed")
    ranking = transform.get("ranking")
    candidate_alias = receipt.get("candidate_alias")
    if (
        not isinstance(ranking, list)
        or not ranking
        or receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION
        or receipt.get("stage_id") != RECEIPT_STAGE_ID
        or receipt.get("extraction_mode") != EXTRACTION_MODE
        or receipt.get("selection_law") != SELECTION_LAW
        or receipt.get("selected_rank") != SELECTED_RANK
        or candidate_alias != ranking[SELECTED_RANK]
        or receipt.get("transform_ranking_length") != len(ranking)
        or receipt.get("transform_artifact_commitment_consumed")
        != transform.get("artifact_commitment")
        or receipt.get("selection_frozen_before_private_mapping") is not True
        or receipt.get("private_mapping_consulted_before_selection") is not False
    ):
        raise RankHeadDesignError("deterministic extraction selection law changed")
    expected_evaluation = _private_evaluation(runtime, str(candidate_alias))
    if receipt.get("controller_private_evaluation") != expected_evaluation:
        raise RankHeadDesignError("deterministic extraction private evaluation changed")
    commitment_body = {
        key: receipt[key] for key in receipt if key != "artifact_commitment"
    }
    if not balanced.verify_artifact_commitment(
        runtime.run_key,
        RECEIPT_STAGE_ID,
        commitment_body,
        str(receipt.get("artifact_commitment")),
        runtime.configuration,
    ):
        raise RankHeadDesignError("deterministic extraction receipt commitment is invalid")
    balanced.validate_metadata_only(receipt)


def _required_file(repository: Path, relative_path: str) -> Path:
    path = repository / relative_path
    if not path.is_file() or path.is_symlink():
        raise RankHeadDesignError(f"required design evidence is missing: {relative_path}")
    return path


def _adjudication_evidence(repository: Path) -> dict[str, Any]:
    adjudication_path = _required_file(repository, ADJUDICATION_PATH)
    adjudication_text = adjudication_path.read_text(encoding="utf-8")
    required_markers = (
        SELECTED_OUTCOME,
        NO_SMUGGLE_STATUS,
        EXTRACTION_CONTRACT_FINDING,
        STAGE_SPECIFIC_STATUS,
        CUSTODY_QUALIFIER,
    )
    missing = [marker for marker in required_markers if marker not in adjudication_text]
    if missing:
        raise RankHeadDesignError(
            "published adjudication lacks required design findings: "
            + ", ".join(missing)
        )
    counterfactual_path = _required_file(repository, COUNTERFACTUAL_PATH)
    try:
        counterfactual = json.loads(counterfactual_path.read_bytes())
    except json.JSONDecodeError as exc:
        raise RankHeadDesignError("rank-head counterfactual is invalid JSON") from exc
    if not isinstance(counterfactual, Mapping):
        raise RankHeadDesignError("rank-head counterfactual root is not an object")
    decision = counterfactual.get("decision_law", {})
    no_smuggle = counterfactual.get("no_smuggle", {})
    selection_law = counterfactual.get("selection_law", {})
    evidence_custody = counterfactual.get("evidence_custody", {})
    if (
        not isinstance(decision, Mapping)
        or decision.get("selected_outcome") != SELECTED_OUTCOME
        or decision.get("selected_lane") != SELECTED_LANE
        or decision.get("lane_a_selected") is not True
        or decision.get("custody_qualifier") != CUSTODY_QUALIFIER
        or decision.get("stage_specific_status") != STAGE_SPECIFIC_STATUS
        or not isinstance(no_smuggle, Mapping)
        or no_smuggle.get("status") != NO_SMUGGLE_STATUS
        or not isinstance(selection_law, Mapping)
        or selection_law.get("selected_position") != SELECTED_RANK
        or selection_law.get("order")
        != [
            "verify-transform-artifact-and-commitment",
            "freeze-ranking-position-zero",
            "private-map-frozen-selection",
            "score-frozen-selection",
            "bind-deterministic-extraction-receipt",
        ]
    ):
        raise RankHeadDesignError("rank-head counterfactual decision law changed")

    forensic_path = _required_file(repository, FORENSIC_PATH)
    forensic_sha256 = sha256_bytes(forensic_path.read_bytes())
    try:
        forensic = json.loads(forensic_path.read_bytes())
    except json.JSONDecodeError as exc:
        raise RankHeadDesignError("binding-2 forensic report is invalid JSON") from exc
    custody_adjudication = (
        forensic.get("custody_adjudication", {})
        if isinstance(forensic, Mapping)
        else {}
    )
    if (
        not isinstance(evidence_custody, Mapping)
        or evidence_custody.get("forensic_report_path") != FORENSIC_PATH
        or evidence_custody.get("forensic_report_sha256") != forensic_sha256
        or evidence_custody.get("custody_qualifier") != CUSTODY_QUALIFIER
        or evidence_custody.get(
            "semantic_identity_accepted_for_narrow_transform_stage_adjudication"
        )
        is not True
        or not isinstance(forensic, Mapping)
        or forensic.get("read_only") is not True
        or forensic.get("status") != "complete"
        or forensic.get("semantic_document_identity_matches") is not True
        or not isinstance(custody_adjudication, Mapping)
        or custody_adjudication.get("custody_qualifier") != CUSTODY_QUALIFIER
        or custody_adjudication.get("accepted_for_narrow_transform_stage_adjudication")
        is not True
        or custody_adjudication.get("semantic_preregistration_identity_independently_verified")
        is not True
        or custody_adjudication.get("exact_execution_bytes_recovered") is not False
    ):
        raise RankHeadDesignError("binding-2 forensic custody binding changed")
    return {
        "adjudication_path": ADJUDICATION_PATH,
        "adjudication_sha256": sha256_bytes(adjudication_path.read_bytes()),
        "counterfactual_path": COUNTERFACTUAL_PATH,
        "counterfactual_sha256": sha256_bytes(counterfactual_path.read_bytes()),
        "forensic_path": FORENSIC_PATH,
        "forensic_sha256": forensic_sha256,
        "selected_outcome": SELECTED_OUTCOME,
        "selected_lane": SELECTED_LANE,
        "no_smuggle_status": NO_SMUGGLE_STATUS,
        "extraction_contract_finding": EXTRACTION_CONTRACT_FINDING,
        "custody_qualifier": CUSTODY_QUALIFIER,
        "stage_specific_status": STAGE_SPECIFIC_STATUS,
        "extraction_status": EXTRACTION_STAGE_STATUS,
    }


def _frozen_source_custody(repository: Path) -> dict[str, Any]:
    runtime_path = _required_file(repository, FROZEN_RUNTIME_PATH)
    preregistrations: dict[str, Any] = {}
    for label, relative_path in (
        ("binding-1", BINDING_1_PREREGISTRATION_PATH),
        ("binding-2", BINDING_2_PREREGISTRATION_PATH),
    ):
        path = _required_file(repository, relative_path)
        try:
            document = json.loads(path.read_bytes())
        except json.JSONDecodeError as exc:
            raise RankHeadDesignError(
                f"{label} preregistration is invalid JSON"
            ) from exc
        preregistrations[label] = {
            "relative_path": relative_path,
            "artifact_sha256": sha256_bytes(path.read_bytes()),
            "document_sha256": json_sha256(document),
        }
    custody = {
        "runtime_relative_path": FROZEN_RUNTIME_PATH,
        "runtime_sha256": sha256_bytes(runtime_path.read_bytes()),
        "preregistrations": preregistrations,
        "historical_runtime_modified": False,
        "historical_preregistrations_modified": False,
    }
    balanced.validate_metadata_only(custody)
    return custody


def build_design_contract(repository: Path) -> dict[str, Any]:
    evidence = _adjudication_evidence(repository)
    contract = {
        "schema_version": DESIGN_SCHEMA_VERSION,
        "status": "static-design-only",
        "design_id": DESIGN_ID,
        "protected_starting_main": STARTING_PROTECTED_MAIN,
        "published_adjudication": evidence,
        "frozen_source_custody": _frozen_source_custody(repository),
        "frozen_mechanism": {
            "source_profile_ids": [
                balanced.BINDING_1_PROFILE_ID,
                balanced.BINDING_2_PROFILE_ID,
            ],
            "carrier_id": balanced.CARRIER_ID,
            "task_suite_sha256": balanced.EXPECTED_SUITE_SHA256,
            "task_index": balanced.TASK_INDEX,
            "task_id": balanced.TASK_ID,
            "branch_indices": {
                key: list(value) for key, value in balanced.BRANCH_INDICES.items()
            },
            "support_cardinalities": [5, 5],
            "relational_intersection_cardinality": 1,
            "parent_order": ["parent-0", "parent-1"],
            "allowed_transform_operators": sorted(balanced.ALLOWED_OPERATORS),
            "logical_stages": list(LOGICAL_STAGES),
            "model_request_stages": list(MODEL_REQUEST_STAGES),
            "model_request_count": len(MODEL_REQUEST_STAGES),
            "physical_slots": 1,
            "sidecar_epochs": 1,
        },
        "extraction_contract": {
            "mode": EXTRACTION_MODE,
            "model_request_present": False,
            "selection_law": SELECTION_LAW,
            "selection_order": list(SELECTION_ORDER),
            "selected_rank": SELECTED_RANK,
            "transform_commitment_verified_before_selection": True,
            "selection_frozen_before_private_mapping": True,
            "private_mapping_after_selection_only": True,
            "private_score_after_selection_only": True,
            "same_law_for_full_and_control_modes": True,
            "receipt_stage_id": RECEIPT_STAGE_ID,
            "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
            "receipt_schema_sha256": receipt_schema_sha256(),
            "receipt_schema": deterministic_extraction_receipt_schema(),
        },
        "authorship_boundary": {
            "model_authored": [
                "branch diagnostic rankings",
                "transform operator",
                "ordered opaque transform ranking",
                "carrier acknowledgements",
            ],
            "controller_authored": [
                "deterministic rank-head projection",
                "private mapping after selection",
                "public score after selection",
                "deterministic extraction receipt",
                "custody and restoration",
            ],
            "new_relational_information_added_by_extraction": False,
        },
        "no_smuggle_invariants": {
            "ranking_order_model_authored": True,
            "selection_profile_independent": True,
            "selection_binding_independent": True,
            "selection_mode_independent": True,
            "selection_uses_private_identity": False,
            "selection_uses_private_score": False,
            "selection_uses_support_intersection": False,
            "selection_uses_branch_identities": False,
            "selection_uses_mode": False,
            "selection_uses_binding_identity": False,
            "selection_uses_expected_classification": False,
            "selection_uses_historical_result": False,
            "selection_uses_counterfactual_result": False,
            "failed_transform_top_cannot_be_privately_repaired": True,
            "transform_commitment_consumed_exactly": True,
        },
        "static_boundary": {
            "new_private_secret_created": False,
            "existing_private_roots_modified": False,
            "run_reservations": [],
            "live_authority_created": False,
            "live_execution_authorized": False,
            "runtime_integration_authorized": False,
            "historical_reclassification": False,
        },
        "future_boundary": {
            "runtime_integration_requires_separate_static_authorization": True,
            "run_reservation_requires_separate_static_authorization": True,
            "live_execution_requires_separate_authorization": True,
        },
        "claim_boundary": {
            "unlocked_stage_specific_status": STAGE_SPECIFIC_STATUS,
            "required_custody_qualifier": CUSTODY_QUALIFIER,
            "historical_binding_2_terminal_classification": (
                "BALANCED_OPAQUE_RELATIONAL_COLLAPSED"
            ),
            "locked": [
                "end-to-end-cross-binding-replication",
                "binding-2-parent-dependence",
                "causal-dependence-replicated-across-bindings",
                "general-two-parent-necessity",
                "transfer",
                "general-catalytic-inference",
                "task-advantage",
                "superiority",
                "sota",
                "broader-process-local-holostate",
                "restart-persistence",
                "deep",
                "automatic-promotion",
            ],
        },
    }
    balanced.validate_metadata_only(contract)
    return contract


def implementation_binding(
    repository: Path,
    implementation_paths: Sequence[str],
) -> dict[str, Any]:
    return balanced.implementation_binding(repository, implementation_paths)


def build_preregistration_document(
    *,
    repository: Path,
    implementation_paths: Sequence[str],
    audit_outcomes: Mapping[str, str] | None = None,
    static_verification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    del repository, implementation_paths, audit_outcomes, static_verification
    raise RankHeadDesignError(
        "v2 preregistration requires the authoritative rank-head v2 wrapper"
    )


def write_preregistration(
    repository: Path,
    document: Mapping[str, Any],
) -> Path:
    path = repository / PREREGISTRATION_PATH
    if path.exists() or path.is_symlink():
        raise RankHeadDesignError("v2 preregistration already exists")
    balanced.validate_metadata_only(document)
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
    fd, temporary_name = tempfile.mkstemp(prefix=".ck0-rank-head-v2-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        written = os.write(fd, payload)
        if written != len(payload):
            raise RankHeadDesignError("v2 preregistration write was incomplete")
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


def validate_preregistration(
    repository: Path,
    *,
    require_final: bool = True,
) -> dict[str, Any]:
    del repository, require_final
    raise RankHeadDesignError(
        "v2 preregistration requires the authoritative rank-head v2 wrapper"
    )


def _parse_audits(values: Sequence[str]) -> dict[str, str]:
    audits: dict[str, str] = {}
    for value in values:
        name, separator, outcome = value.partition("=")
        if not separator or not name or not outcome:
            raise RankHeadDesignError("audit values must use NAME=OUTCOME")
        audits[name] = outcome
    return audits


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("design", "generate", "validate"))
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--implementation-path", action="append", default=[])
    parser.add_argument("--audit", action="append", default=[])
    parser.add_argument("--static-verification-json", type=Path)
    parser.add_argument("--allow-pending", action="store_true")
    return parser.parse_args()


def main() -> int:
    print(
        json.dumps(
            {
                "status": "fail",
                "error": (
                    "v2 preregistration requires the authoritative "
                    "catalytic_kernel_0_balanced_rank_head_v2.py wrapper"
                ),
            },
            sort_keys=True,
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
