#!/usr/bin/env python3
"""Pure typed-artifact contract for Catalytic Inference Bench 0.

The module defines a deterministic, public-only 13-request experiment over
``cs1-task-06``.  It performs no I/O, inference, process control, persistence,
or mutation.  Runtime code can use its builders, strict parsers, normalized
metadata projection, lineage checks, metrics, classification, and summaries.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass, replace
from typing import Any, Mapping, Sequence

try:
    from catalytic_advantage_tasks import (
        AdvantageTask,
        build_frozen_task_suite,
        render_public_task,
        score_candidate,
        validate_public_projection,
    )
except ModuleNotFoundError:
    from .catalytic_advantage_tasks import (  # type: ignore[no-redef]
        AdvantageTask,
        build_frozen_task_suite,
        render_public_task,
        score_candidate,
        validate_public_projection,
    )


SCHEMA_VERSION = 2
BENCH_ID = "catalytic-inference-bench-0"
FROZEN_TASK_INDEX = 5
FROZEN_TASK_ID = "cs1-task-06"
EXPECTED_TASK_SUITE_SHA256 = (
    "4B9961D5054BE5D98EF315D2DEAE9D1604E0042A69CB02A8B81FDF513BC1FC92"
)
EXPECTED_PUBLIC_SYSTEM_ROOT_SHA256 = (
    "E1F38ED8E9CBC6E47A413B31F8A435BE35E84469439426D31470A9617436F4F5"
)
PHYSICAL_SLOT_COUNT = 1
PHYSICAL_SLOT = 0
MAX_TOKENS_PER_REQUEST = 640
MAX_TOKENS_BY_PHASE = {
    "warm": 128,
    "direct": 192,
    "seed": 192,
    "transform": 640,
    "verify": 384,
    "extract": 384,
    "restore": 128,
}
MAX_STRUCTURED_RESPONSE_BYTES = 4096
REQUEST_SEED_BASE = 60600

WARM_ID = "warm"
DIRECT_ID = "direct"
SEED_IDS = ("seed-1", "seed-2", "seed-3")
TRANSFORM_IDS = ("transform-1", "transform-2", "transform-3")
VERIFY_IDS = ("verify-1", "verify-2", "verify-3")
EXTRACT_ID = "extract"
RESTORE_ID = "restore"
REQUEST_IDS = (
    WARM_ID,
    DIRECT_ID,
    *SEED_IDS,
    *TRANSFORM_IDS,
    *VERIFY_IDS,
    EXTRACT_ID,
    RESTORE_ID,
)
RANKING_REQUEST_IDS = (
    DIRECT_ID,
    *SEED_IDS,
    *TRANSFORM_IDS,
    *VERIFY_IDS,
)
CANDIDATE_REQUEST_IDS = (*RANKING_REQUEST_IDS, EXTRACT_ID)
CANDIDATE_IDS = tuple(f"C{index:02d}" for index in range(64))

CONFIDENCE_BUCKETS = ("low", "medium", "high")
PUBLIC_EVIDENCE_REFS = tuple(
    f"public-example-{index}" for index in range(1, 6)
)
RELATION_OPERATORS = (
    "combine",
    "oppose",
    "eliminate",
    "refine",
    "reconcile",
)
RELATIONAL_CHANGE_KINDS = (
    "introduced",
    "promoted",
    "demoted",
    "reconciled",
    "retained",
)
RELATION_EFFECT_BY_OPERATOR = {
    "combine": "support",
    "oppose": "conflict",
    "eliminate": "exclusion",
    "refine": "refinement",
    "reconcile": "reconciliation",
}
STRUCTURAL_REASON_CODES = (
    "candidate-added",
    "candidate-eliminated",
    "evidence-conflict",
    "evidence-consensus",
    "parent-agreement",
    "parent-disagreement",
    "public-test-improved",
    "public-test-regressed",
    "public-test-tied",
    "rank-reordered",
)
CHECKED_CLAIMS = (
    "candidate-public-fit",
    "evidence-support",
    "parent-lineage",
    "ranking-consistency",
    "structural-change",
)
VERIFIER_REASON_CODES = (
    "lineage-consistent",
    "parent-conflict",
    "parent-consensus",
    "public-tests-fail",
    "public-tests-partial",
    "public-tests-pass",
    "ranking-rejected",
    "ranking-survived",
)
EXTRACTION_REASON_CODES = (
    "cross-transform-support",
    "lineage-complete",
    "public-evidence-consistent",
    "ranking-convergence",
    "verifier-consensus",
    "verifier-majority",
)

MECHANISM_VISIBLE = "MECHANISM_VISIBLE"
MECHANISM_COLLAPSED = "MECHANISM_COLLAPSED"
MECHANISM_WEAK = "MECHANISM_WEAK"
MECHANISM_INCONCLUSIVE = "INCONCLUSIVE"
MECHANISM_CLASSIFICATIONS = (
    MECHANISM_VISIBLE,
    MECHANISM_COLLAPSED,
    MECHANISM_WEAK,
    MECHANISM_INCONCLUSIVE,
)

_FORBIDDEN_PRIVATE_MARKERS = (
    "hidden_examples",
    "answer_candidate_id",
    "answer_key",
)
_FORBIDDEN_RAW_KEYS = {
    "content",
    "delta",
    "events",
    "freeform",
    "freeform_output",
    "raw",
    "raw_output",
    "raw_sse",
    "reasoning",
    "reasoning_content",
    "sse",
    "text",
}
_FINISH_REASONS = {"stop", "length", "error", "cancelled", "not-started"}


class CatalyticInferenceBench0Error(RuntimeError):
    """The frozen plan, typed artifact, context, or metadata is malformed."""


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CatalyticInferenceBench0Error("value is not canonical JSON") from exc


def canonical_json_text(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def _require_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise CatalyticInferenceBench0Error(f"{label} must be a boolean")
    return value


def _require_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CatalyticInferenceBench0Error(
            f"{label} must be a non-negative integer"
        )
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CatalyticInferenceBench0Error(f"{label} must be a non-empty string")
    return value


def _require_sha256(value: Any, label: str) -> str:
    value = _require_string(value, label)
    if (
        len(value) != 64
        or value != value.upper()
        or any(character not in "0123456789ABCDEF" for character in value)
    ):
        raise CatalyticInferenceBench0Error(f"{label} must be uppercase SHA-256")
    return value


def frozen_task() -> AdvantageTask:
    suite = build_frozen_task_suite()
    if suite.suite_sha256 != EXPECTED_TASK_SUITE_SHA256:
        raise CatalyticInferenceBench0Error("frozen task-suite identity drift")
    try:
        task = suite.tasks[FROZEN_TASK_INDEX]
    except IndexError as exc:
        raise CatalyticInferenceBench0Error("frozen task index is unavailable") from exc
    if task.task_id != FROZEN_TASK_ID:
        raise CatalyticInferenceBench0Error(
            f"frozen task identity drift: expected {FROZEN_TASK_ID}, got {task.task_id}"
        )
    if len(task.public_examples) != len(PUBLIC_EVIDENCE_REFS):
        raise CatalyticInferenceBench0Error("public evidence reference count drift")
    return task


def build_public_system_root() -> str:
    task = frozen_task()
    rendered = render_public_task(task)
    validate_public_projection(task, rendered)
    validate_no_hidden_leak(rendered)
    if sha256_bytes(rendered.encode("utf-8")) != EXPECTED_PUBLIC_SYSTEM_ROOT_SHA256:
        raise CatalyticInferenceBench0Error("frozen public-root identity drift")
    return rendered


def validate_no_hidden_leak(value: Any) -> None:
    """Reject protected evaluator names anywhere in public or persisted data."""

    def walk(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise CatalyticInferenceBench0Error("non-string metadata key")
                lowered = key.casefold()
                if any(marker in lowered for marker in _FORBIDDEN_PRIVATE_MARKERS):
                    raise CatalyticInferenceBench0Error(
                        f"protected evaluator field leaked: {key}"
                    )
                walk(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                walk(child)
        elif isinstance(item, str):
            lowered = item.casefold()
            if any(marker in lowered for marker in _FORBIDDEN_PRIVATE_MARKERS):
                raise CatalyticInferenceBench0Error(
                    "protected evaluator marker leaked"
                )

    walk(value)


def validate_metadata_only(value: Any) -> None:
    """Recursively reject raw transport, output, and reasoning field names."""

    def walk(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise CatalyticInferenceBench0Error("non-string metadata key")
                if key.casefold() in _FORBIDDEN_RAW_KEYS:
                    raise CatalyticInferenceBench0Error(
                        f"raw output field is forbidden: {key}"
                    )
                walk(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                walk(child)

    validate_no_hidden_leak(value)
    walk(value)
    canonical_json_bytes(value)


_PARENTS: dict[str, tuple[str, ...]] = {
    WARM_ID: (),
    DIRECT_ID: (),
    "seed-1": (),
    "seed-2": (),
    "seed-3": (),
    "transform-1": ("seed-1", "seed-2"),
    "transform-2": ("seed-2", "seed-3"),
    "transform-3": ("seed-1", "seed-3"),
    "verify-1": ("transform-1", "transform-2"),
    "verify-2": ("transform-2", "transform-3"),
    "verify-3": ("transform-1", "transform-3"),
    EXTRACT_ID: VERIFY_IDS,
    RESTORE_ID: (EXTRACT_ID,),
}

_PHASES = {
    WARM_ID: "warm",
    DIRECT_ID: "direct",
    **{request_id: "seed" for request_id in SEED_IDS},
    **{request_id: "transform" for request_id in TRANSFORM_IDS},
    **{request_id: "verify" for request_id in VERIFY_IDS},
    EXTRACT_ID: "extract",
    RESTORE_ID: "restore",
}


def _expected_ancestors(request_id: str) -> tuple[str, ...]:
    if request_id not in _PARENTS:
        raise CatalyticInferenceBench0Error(f"unknown request ID {request_id!r}")
    discovered: set[str] = set()
    pending = list(_PARENTS[request_id])
    while pending:
        parent = pending.pop()
        if parent in discovered:
            continue
        discovered.add(parent)
        pending.extend(_PARENTS[parent])
    return tuple(item for item in REQUEST_IDS if item in discovered)


def _expected_depth(request_id: str) -> int:
    parents = _PARENTS[request_id]
    if not parents:
        return 0
    return 1 + max(_expected_depth(parent) for parent in parents)


def required_context_ids(request_id: str) -> tuple[str, ...]:
    if request_id in (*TRANSFORM_IDS, *VERIFY_IDS):
        return _PARENTS[request_id]
    if request_id == EXTRACT_ID:
        return _expected_ancestors(EXTRACT_ID)
    return ()


def _enum_array_schema(
    values: Sequence[str],
    *,
    minimum: int,
    maximum: int,
) -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string", "enum": list(values)},
        "minItems": minimum,
        "maxItems": maximum,
        "uniqueItems": True,
    }


def _candidate_ranking_schema() -> dict[str, Any]:
    return _enum_array_schema(CANDIDATE_IDS, minimum=1, maximum=3)


def _sha256_schema() -> dict[str, Any]:
    return {"type": "string", "pattern": "^[A-F0-9]{64}$"}


def _consumption_binding_properties(request_id: str) -> dict[str, Any]:
    return {
        "assignment_body_sha256": _sha256_schema(),
    }


def _relational_changes_schema(request_id: str) -> dict[str, Any]:
    return {
        "type": "array",
        "minItems": 1,
        "maxItems": 3,
        "uniqueItems": True,
        "items": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "candidate_id": {"type": "string", "enum": list(CANDIDATE_IDS)},
                "parent_rank_positions": {
                    "type": "array",
                    "minItems": len(_PARENTS[request_id]),
                    "maxItems": len(_PARENTS[request_id]),
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "parent_artifact_id": {
                                "type": "string",
                                "enum": list(_PARENTS[request_id]),
                            },
                            "rank_position": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 3,
                            },
                        },
                        "required": ["parent_artifact_id", "rank_position"],
                    },
                },
                "resulting_rank_position": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 3,
                },
                "change_kind": {
                    "type": "string",
                    "enum": list(RELATIONAL_CHANGE_KINDS),
                },
                "public_evidence_refs": _enum_array_schema(
                    PUBLIC_EVIDENCE_REFS,
                    minimum=1,
                    maximum=len(PUBLIC_EVIDENCE_REFS),
                ),
            },
            "required": [
                "candidate_id",
                "parent_rank_positions",
                "resulting_rank_position",
                "change_kind",
                "public_evidence_refs",
            ],
        },
    }


def _relation_edges_schema(request_id: str) -> dict[str, Any]:
    return {
        "type": "array",
        "minItems": 1,
        "maxItems": 3,
        "uniqueItems": True,
        "items": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "edge_id": {
                    "type": "string",
                    "pattern": f"^{request_id}-edge-[1-3]$",
                },
                "subject_candidate_id": {
                    "type": "string",
                    "enum": list(CANDIDATE_IDS),
                },
                "object_candidate_id": {
                    "type": "string",
                    "enum": list(CANDIDATE_IDS),
                },
                "relation_operator": {
                    "type": "string",
                    "enum": list(RELATION_OPERATORS),
                },
                "structural_effect": {
                    "type": "string",
                    "enum": list(RELATION_EFFECT_BY_OPERATOR.values()),
                },
                "parent_artifact_ids": {
                    "type": "array",
                    "const": list(_PARENTS[request_id]),
                },
                "public_evidence_refs": _enum_array_schema(
                    PUBLIC_EVIDENCE_REFS,
                    minimum=1,
                    maximum=len(PUBLIC_EVIDENCE_REFS),
                ),
            },
            "required": [
                "edge_id",
                "subject_candidate_id",
                "object_candidate_id",
                "relation_operator",
                "structural_effect",
                "parent_artifact_ids",
                "public_evidence_refs",
            ],
        },
    }


def _proposal_properties(request_id: str) -> dict[str, Any]:
    return {
        "artifact_id": {"type": "string", "const": request_id},
        "candidate_ranking": _candidate_ranking_schema(),
        "confidence_bucket": {
            "type": "string",
            "enum": list(CONFIDENCE_BUCKETS),
        },
        "public_evidence_refs": _enum_array_schema(
            PUBLIC_EVIDENCE_REFS,
            minimum=1,
            maximum=len(PUBLIC_EVIDENCE_REFS),
        ),
    }


def _response_schema(request_id: str, root_sha256: str) -> dict[str, Any]:
    if request_id == WARM_ID:
        properties = {
            "artifact_id": {"type": "string", "const": WARM_ID},
            "root_status": {"type": "string", "const": "ready"},
            "public_system_root_sha256": {
                "type": "string",
                "const": root_sha256,
            },
        }
    elif request_id in (DIRECT_ID, *SEED_IDS):
        properties = _proposal_properties(request_id)
    elif request_id in TRANSFORM_IDS:
        properties = {
            "artifact_id": {"type": "string", "const": request_id},
            "parent_artifact_ids": {
                "type": "array",
                "const": list(_PARENTS[request_id]),
            },
            "relation_operator": {
                "type": "string",
                "enum": list(RELATION_OPERATORS),
            },
            "candidate_ranking": _candidate_ranking_schema(),
            "confidence_bucket": {
                "type": "string",
                "enum": list(CONFIDENCE_BUCKETS),
            },
            "public_evidence_refs": _enum_array_schema(
                PUBLIC_EVIDENCE_REFS,
                minimum=1,
                maximum=len(PUBLIC_EVIDENCE_REFS),
            ),
            "structural_reason_codes": _enum_array_schema(
                STRUCTURAL_REASON_CODES,
                minimum=1,
                maximum=4,
            ),
            "changed_from_parents": {"type": "boolean"},
            "relational_changes": _relational_changes_schema(request_id),
            "relation_edges": _relation_edges_schema(request_id),
            **_consumption_binding_properties(request_id),
        }
    elif request_id in VERIFY_IDS:
        properties = {
            "artifact_id": {"type": "string", "const": request_id},
            "parent_artifact_ids": {
                "type": "array",
                "const": list(_PARENTS[request_id]),
            },
            "checked_claims": _enum_array_schema(
                CHECKED_CLAIMS,
                minimum=1,
                maximum=len(CHECKED_CLAIMS),
            ),
            "surviving_candidates": _candidate_ranking_schema(),
            "rejected_candidates": _enum_array_schema(
                CANDIDATE_IDS,
                minimum=0,
                maximum=6,
            ),
            "public_test_summary": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "passed": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": len(PUBLIC_EVIDENCE_REFS),
                    },
                    "total": {
                        "type": "integer",
                        "const": len(PUBLIC_EVIDENCE_REFS),
                    },
                },
                "required": ["passed", "total"],
            },
            "reason_codes": _enum_array_schema(
                VERIFIER_REASON_CODES,
                minimum=1,
                maximum=5,
            ),
            "candidate_ranking": _candidate_ranking_schema(),
            **_consumption_binding_properties(request_id),
        }
    elif request_id == EXTRACT_ID:
        properties = {
            "artifact_id": {"type": "string", "const": EXTRACT_ID},
            "selected_candidate_id": {
                "type": "string",
                "enum": list(CANDIDATE_IDS),
            },
            "complete_parent_lineage": {
                "type": "array",
                "const": list(_expected_ancestors(EXTRACT_ID)),
            },
            "transformation_ids_used": _enum_array_schema(
                TRANSFORM_IDS,
                minimum=1,
                maximum=len(TRANSFORM_IDS),
            ),
            "verifier_ids_used": _enum_array_schema(
                VERIFY_IDS,
                minimum=1,
                maximum=len(VERIFY_IDS),
            ),
            "final_confidence_bucket": {
                "type": "string",
                "enum": list(CONFIDENCE_BUCKETS),
            },
            "extraction_reason_codes": _enum_array_schema(
                EXTRACTION_REASON_CODES,
                minimum=1,
                maximum=4,
            ),
            "relation_edge_ids_used": {
                "type": "array",
                "items": {
                    "type": "string",
                    "pattern": "^transform-[1-3]-edge-[1-3]$",
                },
                "minItems": 1,
                "maxItems": 9,
                "uniqueItems": True,
            },
            **_consumption_binding_properties(request_id),
        }
    elif request_id == RESTORE_ID:
        properties = {
            "artifact_id": {"type": "string", "const": RESTORE_ID},
            "restoration_status": {
                "type": "string",
                "enum": ["failed", "restored"],
            },
            "restored_public_system_root_sha256": {
                "type": "string",
                "const": root_sha256,
            },
            "slot": {"type": "integer", "const": PHYSICAL_SLOT},
            "slot_state": {"type": "string", "const": "public-root"},
        }
    else:
        raise CatalyticInferenceBench0Error(f"unknown request ID {request_id!r}")
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


def _assignment(request_id: str) -> dict[str, Any]:
    objectives = {
        WARM_ID: "Acknowledge the exact public system root.",
        DIRECT_ID: "Produce one independent baseline ranking from public evidence.",
        "seed-1": "Produce parentless proposal artifact one from public evidence.",
        "seed-2": "Produce parentless proposal artifact two from public evidence.",
        "seed-3": "Produce parentless proposal artifact three from public evidence.",
        "transform-1": "Relationally transform the two supplied seed artifacts.",
        "transform-2": "Relationally transform the two supplied seed artifacts.",
        "transform-3": "Relationally transform the two supplied seed artifacts.",
        "verify-1": "Check and reconcile the two supplied transform artifacts.",
        "verify-2": "Check and reconcile the two supplied transform artifacts.",
        "verify-3": "Check and reconcile the two supplied transform artifacts.",
        EXTRACT_ID: "Extract from the complete supplied transformed lineage.",
        RESTORE_ID: "Return slot zero to the exact public root and report restoration state only.",
    }
    operations = {
        WARM_ID: "warm-root",
        DIRECT_ID: "direct-baseline",
        **{item: "seed-proposal" for item in SEED_IDS},
        **{item: "relational-transform" for item in TRANSFORM_IDS},
        **{item: "verify-reconcile" for item in VERIFY_IDS},
        EXTRACT_ID: "extract-lineage",
        RESTORE_ID: "restore-root",
    }
    return {
        "artifact_id": request_id,
        "operation": operations[request_id],
        "objective": objectives[request_id],
        "parent_artifact_ids": list(_PARENTS[request_id]),
        "ancestor_artifact_ids": list(_expected_ancestors(request_id)),
        "depth": _expected_depth(request_id),
        "required_context_ids": list(required_context_ids(request_id)),
        "response_mode": "strict-json-only",
    }


@dataclass(frozen=True)
class BenchRequestSpec:
    ordinal: int
    request_id: str
    phase: str
    physical_slot: int
    system_root: str
    system_root_sha256: str
    parent_ids: tuple[str, ...]
    ancestor_ids: tuple[str, ...]
    depth: int
    required_context_ids: tuple[str, ...]
    assignment: Mapping[str, Any]
    response_schema: Mapping[str, Any]
    max_tokens: int
    seed: int
    temperature: float
    thinking_enabled: bool

    @property
    def logical_id(self) -> str:
        return self.request_id

    @property
    def assignment_json(self) -> str:
        return canonical_json_text(self.assignment)

    def to_dict(self, *, include_system_root: bool = False) -> dict[str, Any]:
        result = {
            "ordinal": self.ordinal,
            "request_id": self.request_id,
            "phase": self.phase,
            "physical_slot": self.physical_slot,
            "system_root_sha256": self.system_root_sha256,
            "parent_ids": list(self.parent_ids),
            "ancestor_ids": list(self.ancestor_ids),
            "depth": self.depth,
            "required_context_ids": list(self.required_context_ids),
            "assignment": json.loads(canonical_json_text(self.assignment)),
            "response_schema": json.loads(canonical_json_text(self.response_schema)),
            "max_tokens": self.max_tokens,
            "seed": self.seed,
            "temperature": self.temperature,
            "thinking_enabled": self.thinking_enabled,
        }
        if include_system_root:
            result["system_root"] = self.system_root
        return result


@dataclass(frozen=True)
class CatalyticInferenceBench0Plan:
    schema_version: int
    bench_id: str
    task_id: str
    task_suite_sha256: str
    physical_slot_count: int
    public_system_root: str
    public_system_root_sha256: str
    requests: tuple[BenchRequestSpec, ...]
    plan_sha256: str

    @property
    def logical_requests(self) -> tuple[BenchRequestSpec, ...]:
        return self.requests

    @property
    def request_count(self) -> int:
        return len(self.requests)

    def request(self, request_id: str) -> BenchRequestSpec:
        for request in self.requests:
            if request.request_id == request_id:
                return request
        raise CatalyticInferenceBench0Error(f"plan has no request {request_id!r}")

    def to_dict(self, *, include_public_system_root: bool = False) -> dict[str, Any]:
        result = _plan_payload(self)
        result["plan_sha256"] = self.plan_sha256
        if include_public_system_root:
            result["public_system_root"] = self.public_system_root
        return result


@dataclass(frozen=True)
class LineageReport:
    parent_order_valid: bool
    ancestor_closure_valid: bool
    depth_valid: bool
    branching_valid: bool
    convergence_valid: bool
    acyclic: bool
    artifact_parent_integrity: bool
    extraction_lineage_valid: bool
    max_depth: int
    reasons: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return all(
            (
                self.parent_order_valid,
                self.ancestor_closure_valid,
                self.depth_valid,
                self.branching_valid,
                self.convergence_valid,
                self.acyclic,
                self.artifact_parent_integrity,
                self.extraction_lineage_valid,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "parent_order_valid": self.parent_order_valid,
            "ancestor_closure_valid": self.ancestor_closure_valid,
            "depth_valid": self.depth_valid,
            "branching_valid": self.branching_valid,
            "convergence_valid": self.convergence_valid,
            "acyclic": self.acyclic,
            "artifact_parent_integrity": self.artifact_parent_integrity,
            "extraction_lineage_valid": self.extraction_lineage_valid,
            "max_depth": self.max_depth,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class NormalizedObservation:
    request_id: str
    ordinal: int
    phase: str
    completed: bool
    safety_passed: bool
    hidden_leak_detected: bool
    physical_slot: int
    public_system_root_sha256: str
    public_root_terminal_token_index: int
    root_reused: bool
    parent_ids: tuple[str, ...]
    ancestor_ids: tuple[str, ...]
    depth: int
    artifact: Mapping[str, Any] | None
    artifact_sha256: str | None
    assignment_body_sha256: str | None
    consumed_artifact_sha256: tuple[str, ...]
    restoration_model_acknowledged: bool | None
    restoration_passed: bool | None
    restoration_receipt: Mapping[str, Any] | None
    restoration_receipt_sha256: str | None
    prompt_tokens: int
    cached_prompt_tokens: int
    fresh_prompt_tokens: int
    completion_tokens: int
    finish_reason: str

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["parent_ids"] = list(self.parent_ids)
        result["ancestor_ids"] = list(self.ancestor_ids)
        result["consumed_artifact_sha256"] = list(
            self.consumed_artifact_sha256
        )
        if self.artifact is not None:
            result["artifact"] = json.loads(canonical_json_text(self.artifact))
        if self.restoration_receipt is not None:
            result["restoration_receipt"] = json.loads(
                canonical_json_text(self.restoration_receipt)
            )
        return result


@dataclass(frozen=True)
class MechanismMetrics:
    unique_candidate_ids: tuple[str, ...]
    candidate_occurrence_count: int
    candidate_entropy_bits: float
    candidate_diversity_ratio: float
    distinct_ranking_count: int
    ranking_artifact_count: int
    ranking_diversity_ratio: float
    transform_changed_artifact_count: int
    transform_parent_edge_count: int
    transform_changed_parent_edge_count: int
    relational_transform_count: int
    relational_change_record_count: int
    transform_introduced_candidate_count: int
    relation_operator_count: int
    relation_edge_count: int
    nonself_relation_edge_count: int
    ranking_change_edge_count: int
    ranking_edge_count: int
    verifier_rejected_candidate_count: int
    verifier_restored_candidate_count: int
    extraction_transform_count: int
    extraction_verifier_count: int
    extraction_relation_edge_count: int
    final_differs_from_direct: bool
    candidate_entropy_bits_by_phase: tuple[tuple[str, float], ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["unique_candidate_ids"] = list(self.unique_candidate_ids)
        result["candidate_entropy_bits_by_phase"] = dict(
            self.candidate_entropy_bits_by_phase
        )
        return result


@dataclass(frozen=True)
class MechanismAssessment:
    status: str
    mechanism_classification: str
    gates: tuple[tuple[str, bool], ...]
    reasons: tuple[str, ...]
    completed_request_count: int
    restoration_passed: bool
    lineage: LineageReport
    metrics: MechanismMetrics

    @property
    def gate_map(self) -> dict[str, bool]:
        return dict(self.gates)

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        return self.metrics.unique_candidate_ids

    @property
    def distinct_candidate_count(self) -> int:
        return len(self.metrics.unique_candidate_ids)

    @property
    def transform_change_count(self) -> int:
        return self.metrics.transform_changed_artifact_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mechanism_classification": self.mechanism_classification,
            "gates": dict(self.gates),
            "reasons": list(self.reasons),
            "completed_request_count": self.completed_request_count,
            "restoration_passed": self.restoration_passed,
            "lineage": self.lineage.to_dict(),
            "metrics": self.metrics.to_dict(),
        }


def _request_payload(request: BenchRequestSpec) -> dict[str, Any]:
    return request.to_dict(include_system_root=False)


def _plan_payload(plan: CatalyticInferenceBench0Plan) -> dict[str, Any]:
    return {
        "schema_version": plan.schema_version,
        "bench_id": plan.bench_id,
        "task_id": plan.task_id,
        "task_suite_sha256": plan.task_suite_sha256,
        "physical_slot_count": plan.physical_slot_count,
        "public_system_root_sha256": plan.public_system_root_sha256,
        "request_count": len(plan.requests),
        "requests": [_request_payload(request) for request in plan.requests],
    }


def build_catalytic_inference_bench_0_plan() -> CatalyticInferenceBench0Plan:
    task = frozen_task()
    suite = build_frozen_task_suite()
    root = build_public_system_root()
    root_sha256 = sha256_bytes(root.encode("utf-8"))
    requests: list[BenchRequestSpec] = []
    for ordinal, request_id in enumerate(REQUEST_IDS, start=1):
        requests.append(
            BenchRequestSpec(
                ordinal=ordinal,
                request_id=request_id,
                phase=_PHASES[request_id],
                physical_slot=PHYSICAL_SLOT,
                system_root=root,
                system_root_sha256=root_sha256,
                parent_ids=_PARENTS[request_id],
                ancestor_ids=_expected_ancestors(request_id),
                depth=_expected_depth(request_id),
                required_context_ids=required_context_ids(request_id),
                assignment=_assignment(request_id),
                response_schema=_response_schema(request_id, root_sha256),
                max_tokens=MAX_TOKENS_BY_PHASE[_PHASES[request_id]],
                seed=REQUEST_SEED_BASE + ordinal,
                temperature=0.0,
                thinking_enabled=False,
            )
        )
    provisional = CatalyticInferenceBench0Plan(
        schema_version=SCHEMA_VERSION,
        bench_id=BENCH_ID,
        task_id=task.task_id,
        task_suite_sha256=suite.suite_sha256,
        physical_slot_count=PHYSICAL_SLOT_COUNT,
        public_system_root=root,
        public_system_root_sha256=root_sha256,
        requests=tuple(requests),
        plan_sha256="",
    )
    digest = sha256_bytes(canonical_json_bytes(_plan_payload(provisional)))
    return CatalyticInferenceBench0Plan(
        schema_version=provisional.schema_version,
        bench_id=provisional.bench_id,
        task_id=provisional.task_id,
        task_suite_sha256=provisional.task_suite_sha256,
        physical_slot_count=provisional.physical_slot_count,
        public_system_root=provisional.public_system_root,
        public_system_root_sha256=provisional.public_system_root_sha256,
        requests=provisional.requests,
        plan_sha256=digest,
    )


def build_catalytic_inference_bench_0() -> CatalyticInferenceBench0Plan:
    return build_catalytic_inference_bench_0_plan()


def build_bench_plan() -> CatalyticInferenceBench0Plan:
    return build_catalytic_inference_bench_0_plan()


def _canonical_enum_list(
    value: Any,
    allowed: Sequence[str],
    *,
    minimum: int,
    maximum: int,
    label: str,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise CatalyticInferenceBench0Error(f"{label} must be an array")
    if not minimum <= len(value) <= maximum or len(set(value)) != len(value):
        raise CatalyticInferenceBench0Error(f"{label} is not bounded and unique")
    if any(not isinstance(item, str) or item not in allowed for item in value):
        raise CatalyticInferenceBench0Error(f"{label} contains an invalid value")
    return tuple(value)


def _candidate_ranking(value: Any, label: str = "candidate_ranking") -> tuple[str, ...]:
    if not isinstance(value, list):
        raise CatalyticInferenceBench0Error(f"{label} must be an array")
    if not 1 <= len(value) <= 3 or len(set(value)) != len(value):
        raise CatalyticInferenceBench0Error(f"{label} is not bounded and unique")
    if any(not isinstance(item, str) or item not in CANDIDATE_IDS for item in value):
        raise CatalyticInferenceBench0Error(f"{label} contains an invalid candidate")
    return tuple(value)


def _public_evidence(value: Any) -> tuple[str, ...]:
    return _canonical_enum_list(
        value,
        PUBLIC_EVIDENCE_REFS,
        minimum=1,
        maximum=len(PUBLIC_EVIDENCE_REFS),
        label="public_evidence_refs",
    )


def _ranking_from_artifact(artifact: Mapping[str, Any]) -> tuple[str, ...]:
    ranking = artifact.get("candidate_ranking")
    return _candidate_ranking(ranking)


def _validate_consumption_binding_static(
    request: BenchRequestSpec,
    value: Mapping[str, Any],
) -> None:
    _require_sha256(value.get("assignment_body_sha256"), "assignment_body_sha256")


def _expected_relational_change_kind(
    parent_positions: Sequence[int],
    result_position: int,
) -> str:
    present = [position for position in parent_positions if position > 0]
    if not present:
        return "introduced"
    if result_position < min(present):
        return "promoted"
    if result_position > max(present):
        return "demoted"
    if len(set(present)) > 1 or any(position != result_position for position in present):
        return "reconciled"
    return "retained"


def _validate_response_static(
    request: BenchRequestSpec,
    response: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(response, Mapping):
        raise CatalyticInferenceBench0Error("structured response is not an object")
    canonical = canonical_json_bytes(response)
    if len(canonical) > MAX_STRUCTURED_RESPONSE_BYTES:
        raise CatalyticInferenceBench0Error("structured response exceeds byte bound")
    validate_metadata_only(response)
    properties = request.response_schema.get("properties")
    if not isinstance(properties, Mapping) or set(response) != set(properties):
        raise CatalyticInferenceBench0Error("structured response key set mismatch")
    value = json.loads(canonical.decode("utf-8"))
    if value.get("artifact_id") != request.request_id:
        raise CatalyticInferenceBench0Error("artifact ID mismatch")

    if request.request_id == WARM_ID:
        expected = {
            "artifact_id": WARM_ID,
            "root_status": "ready",
            "public_system_root_sha256": request.system_root_sha256,
        }
        if value != expected:
            raise CatalyticInferenceBench0Error("warm artifact mismatch")
    elif request.request_id in (DIRECT_ID, *SEED_IDS):
        _candidate_ranking(value.get("candidate_ranking"))
        if value.get("confidence_bucket") not in CONFIDENCE_BUCKETS:
            raise CatalyticInferenceBench0Error("confidence bucket is invalid")
        _public_evidence(value.get("public_evidence_refs"))
    elif request.request_id in TRANSFORM_IDS:
        if value.get("parent_artifact_ids") != list(request.parent_ids):
            raise CatalyticInferenceBench0Error("transform parent artifacts mismatch")
        if value.get("relation_operator") not in RELATION_OPERATORS:
            raise CatalyticInferenceBench0Error("relation operator is invalid")
        _candidate_ranking(value.get("candidate_ranking"))
        if value.get("confidence_bucket") not in CONFIDENCE_BUCKETS:
            raise CatalyticInferenceBench0Error("confidence bucket is invalid")
        _public_evidence(value.get("public_evidence_refs"))
        _canonical_enum_list(
            value.get("structural_reason_codes"),
            STRUCTURAL_REASON_CODES,
            minimum=1,
            maximum=4,
            label="structural_reason_codes",
        )
        _require_bool(value.get("changed_from_parents"), "changed_from_parents")
        changes = value.get("relational_changes")
        if not isinstance(changes, list) or not 1 <= len(changes) <= 3:
            raise CatalyticInferenceBench0Error("relational changes are malformed")
        edges = value.get("relation_edges")
        if (
            not isinstance(edges, list)
            or not 1 <= len(edges) <= 3
            or len({item.get("edge_id") for item in edges if isinstance(item, Mapping)})
            != len(edges)
        ):
            raise CatalyticInferenceBench0Error("relation edges are malformed")
        _validate_consumption_binding_static(request, value)
    elif request.request_id in VERIFY_IDS:
        if value.get("parent_artifact_ids") != list(request.parent_ids):
            raise CatalyticInferenceBench0Error("verifier parent artifacts mismatch")
        _canonical_enum_list(
            value.get("checked_claims"),
            CHECKED_CLAIMS,
            minimum=1,
            maximum=len(CHECKED_CLAIMS),
            label="checked_claims",
        )
        survivors = _candidate_ranking(
            value.get("surviving_candidates"),
            "surviving_candidates",
        )
        rejected = _canonical_enum_list(
            value.get("rejected_candidates"),
            CANDIDATE_IDS,
            minimum=0,
            maximum=6,
            label="rejected_candidates",
        )
        if set(survivors) & set(rejected):
            raise CatalyticInferenceBench0Error("verifier candidate sets overlap")
        ranking = _candidate_ranking(value.get("candidate_ranking"))
        if ranking != survivors:
            raise CatalyticInferenceBench0Error(
                "verifier ranking must equal surviving candidates"
            )
        summary = value.get("public_test_summary")
        if not isinstance(summary, Mapping) or set(summary) != {"passed", "total"}:
            raise CatalyticInferenceBench0Error("public test summary is malformed")
        passed = _require_nonnegative_int(summary.get("passed"), "public passed")
        total = _require_nonnegative_int(summary.get("total"), "public total")
        if total != len(PUBLIC_EVIDENCE_REFS) or passed > total:
            raise CatalyticInferenceBench0Error("public test summary is out of bounds")
        _canonical_enum_list(
            value.get("reason_codes"),
            VERIFIER_REASON_CODES,
            minimum=1,
            maximum=5,
            label="reason_codes",
        )
        _validate_consumption_binding_static(request, value)
    elif request.request_id == EXTRACT_ID:
        if value.get("selected_candidate_id") not in CANDIDATE_IDS:
            raise CatalyticInferenceBench0Error("selected candidate is invalid")
        if value.get("complete_parent_lineage") != list(request.ancestor_ids):
            raise CatalyticInferenceBench0Error("extraction lineage is incomplete")
        _canonical_enum_list(
            value.get("transformation_ids_used"),
            TRANSFORM_IDS,
            minimum=1,
            maximum=len(TRANSFORM_IDS),
            label="transformation_ids_used",
        )
        _canonical_enum_list(
            value.get("verifier_ids_used"),
            VERIFY_IDS,
            minimum=1,
            maximum=len(VERIFY_IDS),
            label="verifier_ids_used",
        )
        if value.get("final_confidence_bucket") not in CONFIDENCE_BUCKETS:
            raise CatalyticInferenceBench0Error("final confidence bucket is invalid")
        _canonical_enum_list(
            value.get("extraction_reason_codes"),
            EXTRACTION_REASON_CODES,
            minimum=1,
            maximum=4,
            label="extraction_reason_codes",
        )
        edge_ids = value.get("relation_edge_ids_used")
        if (
            not isinstance(edge_ids, list)
            or not 1 <= len(edge_ids) <= 9
            or len(set(edge_ids)) != len(edge_ids)
            or any(
                not isinstance(edge_id, str)
                or not edge_id.startswith("transform-")
                or "-edge-" not in edge_id
                for edge_id in edge_ids
            )
        ):
            raise CatalyticInferenceBench0Error(
                "extraction relation edge IDs are malformed"
            )
        _validate_consumption_binding_static(request, value)
    elif request.request_id == RESTORE_ID:
        if value.get("restoration_status") not in {"failed", "restored"}:
            raise CatalyticInferenceBench0Error("restoration status is invalid")
        if value.get("restored_public_system_root_sha256") != request.system_root_sha256:
            raise CatalyticInferenceBench0Error("restoration root hash mismatch")
        slot = _require_nonnegative_int(value.get("slot"), "slot")
        if slot != PHYSICAL_SLOT or value.get("slot_state") != "public-root":
            raise CatalyticInferenceBench0Error("restoration slot state mismatch")
    return value


def _observation_registry(
    observations: Sequence[NormalizedObservation],
) -> dict[str, NormalizedObservation]:
    registry: dict[str, NormalizedObservation] = {}
    for observation in observations:
        validate_normalized_metadata(observation)
        if observation.request_id in registry:
            raise CatalyticInferenceBench0Error("duplicate context artifact")
        registry[observation.request_id] = observation
    return registry


def _required_observations(
    request: BenchRequestSpec,
    observations: Sequence[NormalizedObservation],
) -> tuple[NormalizedObservation, ...]:
    required = request.required_context_ids
    if not required:
        return ()
    registry = _observation_registry(observations)
    selected: list[NormalizedObservation] = []
    for request_id in required:
        observation = registry.get(request_id)
        if (
            observation is None
            or not observation.completed
            or observation.artifact is None
            or not observation.safety_passed
            or observation.hidden_leak_detected
        ):
            raise CatalyticInferenceBench0Error(
                f"required actual artifact unavailable: {request_id}"
            )
        if observation.ordinal >= request.ordinal:
            raise CatalyticInferenceBench0Error("context artifact is not prior")
        selected.append(observation)
    return tuple(selected)


def build_dynamic_parent_context(
    request: BenchRequestSpec,
    observations: Sequence[NormalizedObservation] = (),
) -> tuple[dict[str, Any], ...]:
    """Project exact bounded prior artifacts into the next model request."""
    context = []
    for observation in _required_observations(request, observations):
        assert observation.artifact is not None
        context.append(
            {
                "request_id": observation.request_id,
                "phase": observation.phase,
                "parent_ids": list(observation.parent_ids),
                "ancestor_ids": list(observation.ancestor_ids),
                "depth": observation.depth,
                "artifact_sha256": observation.artifact_sha256,
                "artifact": json.loads(canonical_json_text(observation.artifact)),
            }
        )
    result = tuple(context)
    validate_metadata_only(result)
    return result


def build_bound_assignment(
    request: BenchRequestSpec,
    observations: Sequence[NormalizedObservation] = (),
) -> dict[str, Any]:
    body = {
        "request": json.loads(canonical_json_text(request.assignment)),
        "actual_parent_context": list(
            build_dynamic_parent_context(request, observations)
        ),
    }
    result = {
        **body,
        "binding": {
            "assignment_body_sha256": sha256_bytes(canonical_json_bytes(body)),
            "consumed_artifact_sha256": [
                item["artifact_sha256"]
                for item in body["actual_parent_context"]
            ],
        },
    }
    validate_metadata_only(result)
    return result


def validate_structured_response(
    request: BenchRequestSpec,
    response: Mapping[str, Any],
    *,
    parent_observations: Sequence[NormalizedObservation] = (),
) -> dict[str, Any]:
    value = _validate_response_static(request, response)
    actual = _required_observations(request, parent_observations)
    actual_by_id = {item.request_id: item for item in actual}

    if request.request_id in TRANSFORM_IDS:
        ranking = _candidate_ranking(value["candidate_ranking"])
        parent_rankings = tuple(
            _ranking_from_artifact(actual_by_id[parent].artifact or {})
            for parent in request.parent_ids
        )
        changed = all(ranking != parent_ranking for parent_ranking in parent_rankings)
        # Parent-bound rankings are authoritative.  The model-provided boolean
        # is redundant metadata and is normalized to the measured relation so
        # an unchanged transform remains valid collapsed evidence.
        value["changed_from_parents"] = changed
        changes = value["relational_changes"]
        if [item.get("candidate_id") for item in changes] != list(ranking):
            raise CatalyticInferenceBench0Error(
                "relational changes do not cover the resulting ranking in order"
            )
        top_level_evidence = set(value["public_evidence_refs"])
        for result_position, item in enumerate(changes, start=1):
            candidate_id = item["candidate_id"]
            expected_positions = [
                {
                    "parent_artifact_id": parent_id,
                    "rank_position": (
                        parent_rankings[index].index(candidate_id) + 1
                        if candidate_id in parent_rankings[index]
                        else 0
                    ),
                }
                for index, parent_id in enumerate(request.parent_ids)
            ]
            if item.get("parent_rank_positions") != expected_positions:
                raise CatalyticInferenceBench0Error(
                    "relational change parent ranks differ from actual parents"
                )
            parent_positions = [entry["rank_position"] for entry in expected_positions]
            if (
                item.get("resulting_rank_position") != result_position
                or item.get("change_kind")
                != _expected_relational_change_kind(
                    parent_positions, result_position
                )
                or not set(item.get("public_evidence_refs", ())).issubset(
                    top_level_evidence
                )
            ):
                raise CatalyticInferenceBench0Error(
                    "relational change is not evidence-bound to rank deltas"
                )
        parent_union = set().union(*(set(parent) for parent in parent_rankings))
        result_set = set(ranking)
        relation_edges = value["relation_edges"]
        covered_results: set[str] = set()
        for edge_index, edge in enumerate(relation_edges, start=1):
            subject = edge.get("subject_candidate_id")
            obj = edge.get("object_candidate_id")
            operator = edge.get("relation_operator")
            if (
                edge.get("edge_id") != f"{request.request_id}-edge-{edge_index}"
                or operator != value["relation_operator"]
                or edge.get("structural_effect")
                != RELATION_EFFECT_BY_OPERATOR[value["relation_operator"]]
                or edge.get("parent_artifact_ids") != list(request.parent_ids)
                or subject not in parent_union | result_set
                or obj not in parent_union | result_set
                or not ({subject, obj} & result_set)
                or not ({subject, obj} & parent_union)
                or not set(edge.get("public_evidence_refs", ())).issubset(
                    top_level_evidence
                )
            ):
                raise CatalyticInferenceBench0Error(
                    "relation edge is not bound to operator, parents, and evidence"
                )
            covered_results.update({subject, obj} & result_set)
        if covered_results != result_set:
            raise CatalyticInferenceBench0Error(
                "relation edges do not cover the transformed ranking"
            )
    elif request.request_id in VERIFY_IDS:
        parent_union = {
            candidate
            for parent in request.parent_ids
            for candidate in _ranking_from_artifact(
                actual_by_id[parent].artifact or {}
            )
        }
        survivors = set(value["surviving_candidates"])
        rejected = set(value["rejected_candidates"])
        if survivors | rejected != parent_union:
            raise CatalyticInferenceBench0Error(
                "verifier candidates do not partition actual parent rankings"
            )
        passed, total = score_candidate(
            frozen_task(), value["candidate_ranking"][0], hidden=False
        )
        if value["public_test_summary"] != {"passed": passed, "total": total}:
            raise CatalyticInferenceBench0Error(
                "public test summary differs from actual public score"
            )
    elif request.request_id == EXTRACT_ID:
        transforms_used = tuple(value["transformation_ids_used"])
        verifiers_used = tuple(value["verifier_ids_used"])
        for verifier_id in verifiers_used:
            verifier = actual_by_id[verifier_id]
            if not set(verifier.parent_ids).issubset(transforms_used):
                raise CatalyticInferenceBench0Error(
                    "extraction omitted a transform parent used by a verifier"
                )
        selected = value["selected_candidate_id"]
        if not any(
            selected in _ranking_from_artifact(actual_by_id[item].artifact or {})
            for item in transforms_used
        ):
            raise CatalyticInferenceBench0Error(
                "extraction candidate is absent from used transforms"
            )
        if not any(
            selected in _ranking_from_artifact(actual_by_id[item].artifact or {})
            for item in verifiers_used
        ):
            raise CatalyticInferenceBench0Error(
                "extraction candidate is absent from used verifiers"
            )
        available_edges = {
            edge["edge_id"]: edge
            for transform_id in transforms_used
            for edge in actual_by_id[transform_id].artifact.get(
                "relation_edges", ()
            )
        }
        used_edges = value["relation_edge_ids_used"]
        if any(edge_id not in available_edges for edge_id in used_edges):
            raise CatalyticInferenceBench0Error(
                "extraction references an unavailable relation edge"
            )
        if not any(
            selected
            in {
                available_edges[edge_id]["subject_candidate_id"],
                available_edges[edge_id]["object_candidate_id"],
            }
            for edge_id in used_edges
        ):
            raise CatalyticInferenceBench0Error(
                "extraction candidate is not supported by a used relation edge"
            )
    if request.request_id in (*TRANSFORM_IDS, *VERIFY_IDS, EXTRACT_ID):
        expected_binding = build_bound_assignment(request, parent_observations)[
            "binding"
        ]
        if (
            value.get("assignment_body_sha256")
            != expected_binding["assignment_body_sha256"]
        ):
            raise CatalyticInferenceBench0Error(
                "response consumption binding differs from the sent parent context"
            )
    return value


def parse_structured_response(
    request: BenchRequestSpec,
    content: str,
    *,
    parent_observations: Sequence[NormalizedObservation] = (),
) -> dict[str, Any]:
    if not isinstance(content, str) or not content:
        raise CatalyticInferenceBench0Error("structured response content is empty")
    if len(content.encode("utf-8")) > MAX_STRUCTURED_RESPONSE_BYTES:
        raise CatalyticInferenceBench0Error("structured response exceeds byte bound")
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise CatalyticInferenceBench0Error("structured response is not JSON") from exc
    validated = validate_structured_response(
        request,
        value,
        parent_observations=parent_observations,
    )
    return validated


def build_model_request(
    request: BenchRequestSpec,
    *,
    parent_observations: Sequence[NormalizedObservation] = (),
    model: str | None = None,
    stream: bool = True,
) -> dict[str, Any]:
    stream = _require_bool(stream, "stream")
    bound_assignment = build_bound_assignment(request, parent_observations)
    payload: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": request.system_root},
            {"role": "user", "content": canonical_json_text(bound_assignment)},
        ],
        "temperature": request.temperature,
        "seed": request.seed,
        "max_tokens": request.max_tokens,
        "stream": stream,
        "chat_template_kwargs": {"enable_thinking": request.thinking_enabled},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": f"cib0_{request.request_id.replace('-', '_')}",
                "strict": True,
                "schema": json.loads(canonical_json_text(request.response_schema)),
            },
        },
    }
    if model is not None:
        payload["model"] = _require_string(model, "model")
    validate_model_request(
        request,
        payload,
        parent_observations=parent_observations,
    )
    return payload


def build_request_payload(
    request: BenchRequestSpec,
    *,
    parent_observations: Sequence[NormalizedObservation] = (),
    model: str | None = None,
    stream: bool = True,
) -> dict[str, Any]:
    return build_model_request(
        request,
        parent_observations=parent_observations,
        model=model,
        stream=stream,
    )


def validate_model_request(
    request: BenchRequestSpec,
    payload: Mapping[str, Any],
    *,
    parent_observations: Sequence[NormalizedObservation] = (),
) -> None:
    if not isinstance(payload, Mapping):
        raise CatalyticInferenceBench0Error("model request is not an object")
    validate_no_hidden_leak(payload)
    required_keys = {
        "messages",
        "temperature",
        "seed",
        "max_tokens",
        "stream",
        "chat_template_kwargs",
        "response_format",
    }
    if not required_keys.issubset(payload) or set(payload) - (required_keys | {"model"}):
        raise CatalyticInferenceBench0Error("model request key set mismatch")
    if "model" in payload:
        _require_string(payload["model"], "model")
    messages = payload.get("messages")
    expected_assignment = canonical_json_text(
        build_bound_assignment(request, parent_observations)
    )
    if not isinstance(messages, list) or messages != [
        {"role": "system", "content": request.system_root},
        {"role": "user", "content": expected_assignment},
    ]:
        raise CatalyticInferenceBench0Error("model request messages are not exact")
    response_format = payload.get("response_format")
    if (
        not isinstance(response_format, Mapping)
        or set(response_format) != {"type", "json_schema"}
    ):
        raise CatalyticInferenceBench0Error("model request response format mismatch")
    envelope = response_format.get("json_schema")
    if (
        response_format.get("type") != "json_schema"
        or not isinstance(envelope, Mapping)
        or set(envelope) != {"name", "strict", "schema"}
        or envelope.get("name") != f"cib0_{request.request_id.replace('-', '_')}"
        or envelope.get("strict") is not True
        or envelope.get("schema") != request.response_schema
    ):
        raise CatalyticInferenceBench0Error("model request schema is not exact and strict")
    if payload.get("max_tokens") != request.max_tokens:
        raise CatalyticInferenceBench0Error("model request token bound drift")
    if isinstance(payload.get("temperature"), bool) or payload.get("temperature") != 0.0:
        raise CatalyticInferenceBench0Error("model request temperature drift")
    if isinstance(payload.get("seed"), bool) or payload.get("seed") != request.seed:
        raise CatalyticInferenceBench0Error("model request seed drift")
    if type(payload.get("stream")) is not bool:
        raise CatalyticInferenceBench0Error("model request stream flag is not boolean")
    kwargs = payload.get("chat_template_kwargs")
    if (
        not isinstance(kwargs, Mapping)
        or set(kwargs) != {"enable_thinking"}
        or kwargs.get("enable_thinking") is not False
    ):
        raise CatalyticInferenceBench0Error("model request thinking mode drift")


def normalize_observation(
    request: BenchRequestSpec,
    structured_response: Mapping[str, Any] | str | None,
    *,
    parent_observations: Sequence[NormalizedObservation] = (),
    completed: bool,
    safety_passed: bool,
    root_reused: bool,
    public_root_terminal_token_index: int,
    hidden_leak_detected: bool = False,
    physical_slot: int = PHYSICAL_SLOT,
    public_system_root_sha256: str | None = None,
    prompt_tokens: int | None = None,
    cached_prompt_tokens: int | None = None,
    fresh_prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    finish_reason: str | None = None,
) -> NormalizedObservation:
    completed = _require_bool(completed, "completed")
    safety_passed = _require_bool(safety_passed, "safety_passed")
    root_reused = _require_bool(root_reused, "root_reused")
    hidden_leak_detected = _require_bool(
        hidden_leak_detected,
        "hidden_leak_detected",
    )
    physical_slot = _require_nonnegative_int(physical_slot, "physical_slot")
    root_sha256 = public_system_root_sha256 or request.system_root_sha256
    _require_sha256(root_sha256, "public_system_root_sha256")
    root_terminal = _require_nonnegative_int(
        public_root_terminal_token_index,
        "public_root_terminal_token_index",
    )
    if root_terminal <= 0:
        raise CatalyticInferenceBench0Error("public root terminal must be positive")
    if finish_reason is None:
        finish_reason = "stop" if completed else "not-started"
    if finish_reason not in _FINISH_REASONS:
        raise CatalyticInferenceBench0Error("finish reason is not bounded")
    if prompt_tokens is None:
        prompt_tokens = 1
    if cached_prompt_tokens is None:
        cached_prompt_tokens = 1 if root_reused else 0
    if fresh_prompt_tokens is None:
        fresh_prompt_tokens = prompt_tokens - cached_prompt_tokens
    if completion_tokens is None:
        completion_tokens = 1 if completed else 0
    prompt_tokens = _require_nonnegative_int(prompt_tokens, "prompt_tokens")
    cached_prompt_tokens = _require_nonnegative_int(
        cached_prompt_tokens,
        "cached_prompt_tokens",
    )
    fresh_prompt_tokens = _require_nonnegative_int(
        fresh_prompt_tokens,
        "fresh_prompt_tokens",
    )
    completion_tokens = _require_nonnegative_int(
        completion_tokens,
        "completion_tokens",
    )
    if (
        cached_prompt_tokens > prompt_tokens
        or cached_prompt_tokens + fresh_prompt_tokens != prompt_tokens
    ):
        raise CatalyticInferenceBench0Error("prompt token accounting mismatch")
    if completion_tokens > request.max_tokens:
        raise CatalyticInferenceBench0Error("completion token bound exceeded")
    if request.request_id != WARM_ID and root_reused is not (
        root_terminal <= prompt_tokens and cached_prompt_tokens >= root_terminal
    ):
        raise CatalyticInferenceBench0Error(
            "root reuse flag differs from root-terminal evidence"
        )

    artifact: Mapping[str, Any] | None = None
    artifact_sha256: str | None = None
    assignment_body_sha256: str | None = None
    consumed_artifact_sha256: tuple[str, ...] = ()
    restoration_model_acknowledged: bool | None = None
    restoration_passed: bool | None = None
    restoration_receipt: Mapping[str, Any] | None = None
    restoration_receipt_sha256: str | None = None
    if completed:
        if structured_response is None:
            raise CatalyticInferenceBench0Error(
                "completed observation lacks structured response"
            )
        if isinstance(structured_response, str):
            value = parse_structured_response(
                request,
                structured_response,
                parent_observations=parent_observations,
            )
        else:
            value = validate_structured_response(
                request,
                structured_response,
                parent_observations=parent_observations,
            )
        artifact = json.loads(canonical_json_text(value))
        artifact_sha256 = sha256_bytes(canonical_json_bytes(artifact))
        binding = build_bound_assignment(request, parent_observations)["binding"]
        assignment_body_sha256 = binding["assignment_body_sha256"]
        consumed_artifact_sha256 = tuple(binding["consumed_artifact_sha256"])
        if request.request_id == RESTORE_ID:
            restoration_model_acknowledged = (
                value["restoration_status"] == "restored"
                and value["restored_public_system_root_sha256"]
                == request.system_root_sha256
                and value["slot"] == PHYSICAL_SLOT
                and value["slot_state"] == "public-root"
            )
        if safety_passed and finish_reason != "stop":
            raise CatalyticInferenceBench0Error(
                "safe completed response must finish normally"
            )
    elif structured_response is not None:
        raise CatalyticInferenceBench0Error(
            "incomplete observation may not retain response output"
        )

    result = NormalizedObservation(
        request_id=request.request_id,
        ordinal=request.ordinal,
        phase=request.phase,
        completed=completed,
        safety_passed=safety_passed,
        hidden_leak_detected=hidden_leak_detected,
        physical_slot=physical_slot,
        public_system_root_sha256=root_sha256,
        public_root_terminal_token_index=root_terminal,
        root_reused=root_reused,
        parent_ids=request.parent_ids,
        ancestor_ids=request.ancestor_ids,
        depth=request.depth,
        artifact=artifact,
        artifact_sha256=artifact_sha256,
        assignment_body_sha256=assignment_body_sha256,
        consumed_artifact_sha256=consumed_artifact_sha256,
        restoration_model_acknowledged=restoration_model_acknowledged,
        restoration_passed=restoration_passed,
        restoration_receipt=restoration_receipt,
        restoration_receipt_sha256=restoration_receipt_sha256,
        prompt_tokens=prompt_tokens,
        cached_prompt_tokens=cached_prompt_tokens,
        fresh_prompt_tokens=fresh_prompt_tokens,
        completion_tokens=completion_tokens,
        finish_reason=finish_reason,
    )
    validate_normalized_metadata(result)
    return result


_NORMALIZED_TRANSPORT_KEYS = {
    "completed",
    "safety_passed",
    "root_reused",
    "public_root_terminal_token_index",
    "hidden_leak_detected",
    "physical_slot",
    "public_system_root_sha256",
    "prompt_tokens",
    "cached_prompt_tokens",
    "fresh_prompt_tokens",
    "completion_tokens",
    "finish_reason",
}


def normalize_observation_from_metadata(
    request: BenchRequestSpec,
    structured_response: Mapping[str, Any] | str | None,
    metadata: Mapping[str, Any],
    *,
    parent_observations: Sequence[NormalizedObservation] = (),
) -> NormalizedObservation:
    if not isinstance(metadata, Mapping):
        raise CatalyticInferenceBench0Error("transport metadata is not an object")
    if set(metadata) & _FORBIDDEN_RAW_KEYS:
        raise CatalyticInferenceBench0Error(
            "transport metadata contains raw output or reasoning"
        )
    if set(metadata) != _NORMALIZED_TRANSPORT_KEYS:
        raise CatalyticInferenceBench0Error("transport metadata key set mismatch")
    return normalize_observation(
        request,
        structured_response,
        parent_observations=parent_observations,
        **dict(metadata),
    )


def validate_normalized_metadata(observation: NormalizedObservation) -> None:
    if not isinstance(observation, NormalizedObservation):
        raise CatalyticInferenceBench0Error("observation has wrong type")
    if observation.request_id not in REQUEST_IDS:
        raise CatalyticInferenceBench0Error("normalized request ID is unknown")
    request_id = observation.request_id
    expected_ordinal = REQUEST_IDS.index(request_id) + 1
    if (
        _require_nonnegative_int(observation.ordinal, "ordinal") != expected_ordinal
        or observation.phase != _PHASES[request_id]
    ):
        raise CatalyticInferenceBench0Error("normalized request identity drift")
    for value, label in (
        (observation.completed, "completed"),
        (observation.safety_passed, "safety_passed"),
        (observation.hidden_leak_detected, "hidden_leak_detected"),
        (observation.root_reused, "root_reused"),
    ):
        _require_bool(value, label)
    _require_nonnegative_int(observation.physical_slot, "physical_slot")
    _require_sha256(
        observation.public_system_root_sha256,
        "public_system_root_sha256",
    )
    if observation.public_system_root_sha256 != EXPECTED_PUBLIC_SYSTEM_ROOT_SHA256:
        raise CatalyticInferenceBench0Error(
            "normalized public-root identity differs from the frozen root"
        )
    root_terminal = _require_nonnegative_int(
        observation.public_root_terminal_token_index,
        "public_root_terminal_token_index",
    )
    if root_terminal <= 0:
        raise CatalyticInferenceBench0Error("normalized root terminal is invalid")
    if not isinstance(observation.parent_ids, tuple) or any(
        item not in REQUEST_IDS for item in observation.parent_ids
    ):
        raise CatalyticInferenceBench0Error("normalized parent IDs are invalid")
    if not isinstance(observation.ancestor_ids, tuple) or any(
        item not in REQUEST_IDS for item in observation.ancestor_ids
    ):
        raise CatalyticInferenceBench0Error("normalized ancestor IDs are invalid")
    _require_nonnegative_int(observation.depth, "depth")
    prompt = _require_nonnegative_int(observation.prompt_tokens, "prompt_tokens")
    cached = _require_nonnegative_int(
        observation.cached_prompt_tokens,
        "cached_prompt_tokens",
    )
    fresh = _require_nonnegative_int(
        observation.fresh_prompt_tokens,
        "fresh_prompt_tokens",
    )
    completion = _require_nonnegative_int(
        observation.completion_tokens,
        "completion_tokens",
    )
    if cached > prompt or cached + fresh != prompt or completion > MAX_TOKENS_PER_REQUEST:
        raise CatalyticInferenceBench0Error("normalized token accounting mismatch")
    if request_id != WARM_ID and observation.root_reused is not (
        root_terminal <= prompt and cached >= root_terminal
    ):
        raise CatalyticInferenceBench0Error(
            "normalized root reuse differs from terminal evidence"
        )
    if observation.finish_reason not in _FINISH_REASONS:
        raise CatalyticInferenceBench0Error("normalized finish reason is invalid")

    if observation.completed:
        if observation.artifact is None or observation.artifact_sha256 is None:
            raise CatalyticInferenceBench0Error("completed metadata lacks artifact")
        _require_sha256(
            observation.assignment_body_sha256,
            "assignment_body_sha256",
        )
        if (
            not isinstance(observation.consumed_artifact_sha256, tuple)
            or len(observation.consumed_artifact_sha256)
            != len(required_context_ids(request_id))
            or len(set(observation.consumed_artifact_sha256))
            != len(observation.consumed_artifact_sha256)
        ):
            raise CatalyticInferenceBench0Error(
                "normalized consumed artifact hashes are malformed"
            )
        for digest in observation.consumed_artifact_sha256:
            _require_sha256(digest, "consumed_artifact_sha256")
        root = build_public_system_root()
        request = BenchRequestSpec(
            ordinal=expected_ordinal,
            request_id=request_id,
            phase=_PHASES[request_id],
            physical_slot=PHYSICAL_SLOT,
            system_root=root,
            system_root_sha256=sha256_bytes(root.encode("utf-8")),
            parent_ids=_PARENTS[request_id],
            ancestor_ids=_expected_ancestors(request_id),
            depth=_expected_depth(request_id),
            required_context_ids=required_context_ids(request_id),
            assignment=_assignment(request_id),
            response_schema=_response_schema(
                request_id,
                sha256_bytes(root.encode("utf-8")),
            ),
            max_tokens=MAX_TOKENS_BY_PHASE[_PHASES[request_id]],
            seed=REQUEST_SEED_BASE + expected_ordinal,
            temperature=0.0,
            thinking_enabled=False,
        )
        _validate_response_static(request, observation.artifact)
        if observation.artifact_sha256 != sha256_bytes(
            canonical_json_bytes(observation.artifact)
        ):
            raise CatalyticInferenceBench0Error("artifact hash mismatch")
        if request_id == RESTORE_ID:
            if type(observation.restoration_model_acknowledged) is not bool:
                raise CatalyticInferenceBench0Error(
                    "restoration model acknowledgement is empty"
                )
            if observation.restoration_passed is None:
                if (
                    observation.restoration_receipt is not None
                    or observation.restoration_receipt_sha256 is not None
                ):
                    raise CatalyticInferenceBench0Error(
                        "unbound restoration retained a trusted receipt"
                    )
            elif type(observation.restoration_passed) is not bool:
                raise CatalyticInferenceBench0Error(
                    "trusted restoration result is not boolean"
                )
            else:
                receipt = observation.restoration_receipt
                expected_keys = {
                    "run_id",
                    "request_id",
                    "public_system_root_sha256",
                    "active_leases",
                    "model_acknowledged",
                    "root_identity_passed",
                    "cache_terminal_admitted",
                    "cleanup_passed",
                    "custody_passed",
                    "sidecar_port_free",
                    "stable_preserved",
                }
                if not isinstance(receipt, Mapping) or set(receipt) != expected_keys:
                    raise CatalyticInferenceBench0Error(
                        "trusted restoration receipt is malformed"
                    )
                if (
                    not isinstance(receipt["run_id"], str)
                    or not receipt["run_id"]
                    or receipt["request_id"] != RESTORE_ID
                    or receipt["public_system_root_sha256"]
                    != observation.public_system_root_sha256
                ):
                    raise CatalyticInferenceBench0Error(
                        "trusted restoration receipt identity mismatch"
                    )
                active_leases = _require_nonnegative_int(
                    receipt["active_leases"], "receipt active_leases"
                )
                receipt_booleans = [
                    receipt[key]
                    for key in (
                        "model_acknowledged",
                        "root_identity_passed",
                        "cache_terminal_admitted",
                        "cleanup_passed",
                        "custody_passed",
                        "sidecar_port_free",
                        "stable_preserved",
                    )
                ]
                if any(type(value) is not bool for value in receipt_booleans):
                    raise CatalyticInferenceBench0Error(
                        "trusted restoration receipt has non-boolean boundaries"
                    )
                derived_pass = all(receipt_booleans) and active_leases == 0
                if observation.restoration_passed is not derived_pass:
                    raise CatalyticInferenceBench0Error(
                        "trusted restoration pass differs from its receipt"
                    )
                _require_sha256(
                    observation.restoration_receipt_sha256,
                    "restoration_receipt_sha256",
                )
                if observation.restoration_receipt_sha256 != sha256_bytes(
                    canonical_json_bytes(receipt)
                ):
                    raise CatalyticInferenceBench0Error(
                        "trusted restoration receipt hash mismatch"
                    )
        elif any(
            value is not None
            for value in (
                observation.restoration_model_acknowledged,
                observation.restoration_passed,
                observation.restoration_receipt,
                observation.restoration_receipt_sha256,
            )
        ):
            raise CatalyticInferenceBench0Error(
                "restoration metadata escaped restoration"
            )
        if observation.safety_passed and observation.finish_reason != "stop":
            raise CatalyticInferenceBench0Error(
                "safe completed metadata did not finish normally"
            )
    elif any(
        value is not None
        for value in (
            observation.artifact,
            observation.artifact_sha256,
            observation.assignment_body_sha256,
            observation.restoration_model_acknowledged,
            observation.restoration_passed,
            observation.restoration_receipt_sha256,
        )
    ):
        raise CatalyticInferenceBench0Error(
            "incomplete metadata retained artifact output"
        )
    if not observation.completed and observation.consumed_artifact_sha256:
        raise CatalyticInferenceBench0Error(
            "incomplete metadata retained consumed artifact hashes"
        )
    validate_metadata_only(observation.to_dict())


def bind_runtime_restoration(
    observation: NormalizedObservation,
    *,
    run_id: str,
    root_identity_passed: bool,
    cache_terminal_admitted: bool,
    active_leases: int,
    cleanup_passed: bool,
    custody_passed: bool,
    sidecar_port_free: bool,
    stable_preserved: bool,
) -> NormalizedObservation:
    validate_normalized_metadata(observation)
    if observation.request_id != RESTORE_ID or not observation.completed:
        raise CatalyticInferenceBench0Error(
            "trusted restoration receipt requires a completed restore observation"
        )
    if not isinstance(run_id, str) or not run_id:
        raise CatalyticInferenceBench0Error("restoration receipt run ID is invalid")
    booleans = {
        "model_acknowledged": observation.restoration_model_acknowledged,
        "root_identity_passed": root_identity_passed,
        "cache_terminal_admitted": cache_terminal_admitted,
        "cleanup_passed": cleanup_passed,
        "custody_passed": custody_passed,
        "sidecar_port_free": sidecar_port_free,
        "stable_preserved": stable_preserved,
    }
    if any(type(value) is not bool for value in booleans.values()):
        raise CatalyticInferenceBench0Error(
            "restoration receipt has a non-boolean boundary"
        )
    active_leases = _require_nonnegative_int(active_leases, "active_leases")
    receipt = {
        "run_id": run_id,
        "request_id": RESTORE_ID,
        "public_system_root_sha256": observation.public_system_root_sha256,
        "active_leases": active_leases,
        **booleans,
    }
    passed = all(booleans.values()) and active_leases == 0
    result = replace(
        observation,
        restoration_passed=passed,
        restoration_receipt=json.loads(canonical_json_text(receipt)),
        restoration_receipt_sha256=sha256_bytes(canonical_json_bytes(receipt)),
    )
    validate_normalized_metadata(result)
    return result


def _lineage_report_from_nodes(
    nodes: Sequence[BenchRequestSpec | NormalizedObservation],
) -> LineageReport:
    ids = tuple(node.request_id for node in nodes)
    positions = {request_id: index for index, request_id in enumerate(ids)}
    by_id = {node.request_id: node for node in nodes}
    reasons: list[str] = []
    acyclic = len(ids) == len(positions)
    parent_order_valid = acyclic
    ancestor_closure_valid = True
    depth_valid = True
    if not acyclic:
        reasons.append("duplicate-request-id")
    for request_id, node in by_id.items():
        if request_id not in _PARENTS:
            parent_order_valid = ancestor_closure_valid = depth_valid = False
            reasons.append("unknown-request-id")
            continue
        if tuple(node.parent_ids) != _PARENTS[request_id]:
            parent_order_valid = False
        if any(
            parent not in positions or positions[parent] >= positions[request_id]
            for parent in node.parent_ids
        ):
            parent_order_valid = False
        if tuple(node.ancestor_ids) != _expected_ancestors(request_id):
            ancestor_closure_valid = False
        if node.depth != _expected_depth(request_id):
            depth_valid = False
    if not parent_order_valid:
        reasons.append("parent-order")
    if not ancestor_closure_valid:
        reasons.append("ancestor-closure")
    if not depth_valid:
        reasons.append("dag-depth")
    branching_valid = (
        all(item in by_id and not by_id[item].parent_ids for item in SEED_IDS)
        and all(
            item in by_id and tuple(by_id[item].parent_ids) == _PARENTS[item]
            for item in TRANSFORM_IDS
        )
    )
    convergence_valid = (
        all(
            item in by_id and tuple(by_id[item].parent_ids) == _PARENTS[item]
            for item in VERIFY_IDS
        )
        and EXTRACT_ID in by_id
        and tuple(by_id[EXTRACT_ID].parent_ids) == VERIFY_IDS
        and RESTORE_ID in by_id
        and tuple(by_id[RESTORE_ID].parent_ids) == (EXTRACT_ID,)
    )
    if not branching_valid:
        reasons.append("dag-branching")
    if not convergence_valid:
        reasons.append("dag-convergence")
    max_depth = max((node.depth for node in nodes), default=0)
    if max_depth > _expected_depth(RESTORE_ID):
        depth_valid = False
        reasons.append("dag-depth-bound")
    return LineageReport(
        parent_order_valid=parent_order_valid,
        ancestor_closure_valid=ancestor_closure_valid,
        depth_valid=depth_valid,
        branching_valid=branching_valid,
        convergence_valid=convergence_valid,
        acyclic=acyclic,
        artifact_parent_integrity=True,
        extraction_lineage_valid=True,
        max_depth=max_depth,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def validate_dag(plan: CatalyticInferenceBench0Plan) -> LineageReport:
    report = _lineage_report_from_nodes(plan.requests)
    if not report.valid or report.max_depth != _expected_depth(RESTORE_ID):
        raise CatalyticInferenceBench0Error(
            "bench request DAG is invalid: " + ",".join(report.reasons)
        )
    return report


def validate_lineage(
    plan: CatalyticInferenceBench0Plan,
    observations: Sequence[NormalizedObservation],
) -> LineageReport:
    validate_catalytic_inference_bench_0_plan(plan)
    observations = tuple(observations)
    for observation in observations:
        validate_normalized_metadata(observation)
    structural = _lineage_report_from_nodes(observations)
    artifact_integrity = True
    extraction_valid = EXTRACT_ID in {
        observation.request_id for observation in observations
    }
    reasons = list(structural.reasons)
    prior: list[NormalizedObservation] = []
    for observation in observations:
        if observation.completed and observation.artifact is not None:
            try:
                validate_structured_response(
                    plan.request(observation.request_id),
                    observation.artifact,
                    parent_observations=prior,
                )
                expected_binding = build_bound_assignment(
                    plan.request(observation.request_id), prior
                )["binding"]
                if (
                    observation.assignment_body_sha256
                    != expected_binding["assignment_body_sha256"]
                    or list(observation.consumed_artifact_sha256)
                    != expected_binding["consumed_artifact_sha256"]
                ):
                    raise CatalyticInferenceBench0Error(
                        "normalized sent-context binding mismatch"
                    )
            except CatalyticInferenceBench0Error:
                artifact_integrity = False
                reasons.append(f"artifact-integrity:{observation.request_id}")
                if observation.request_id == EXTRACT_ID:
                    extraction_valid = False
        prior.append(observation)
    if not artifact_integrity:
        reasons.append("artifact-parent-integrity")
    if not extraction_valid:
        reasons.append("extraction-lineage")
    return LineageReport(
        parent_order_valid=structural.parent_order_valid,
        ancestor_closure_valid=structural.ancestor_closure_valid,
        depth_valid=structural.depth_valid,
        branching_valid=structural.branching_valid,
        convergence_valid=structural.convergence_valid,
        acyclic=structural.acyclic,
        artifact_parent_integrity=artifact_integrity,
        extraction_lineage_valid=extraction_valid,
        max_depth=structural.max_depth,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def validate_restoration_request(request: BenchRequestSpec) -> None:
    if request.request_id != RESTORE_ID or request.phase != "restore":
        raise CatalyticInferenceBench0Error("restoration request identity drift")
    if request.required_context_ids:
        raise CatalyticInferenceBench0Error("restoration consumes artifact context")
    properties = request.response_schema.get("properties")
    if not isinstance(properties, Mapping):
        raise CatalyticInferenceBench0Error("restoration schema is malformed")
    forbidden_fragments = (
        "candidate",
        "ranking",
        "selected",
        "surviving",
        "rejected",
        "relation",
        "evidence",
    )
    if any(
        fragment in key.casefold()
        for key in properties
        for fragment in forbidden_fragments
    ):
        raise CatalyticInferenceBench0Error(
            "restoration response contains selection work"
        )
    objective = request.assignment.get("objective")
    if request.assignment.get("operation") != "restore-root" or not isinstance(
        objective,
        str,
    ):
        raise CatalyticInferenceBench0Error("restoration assignment is malformed")
    forbidden_terms = (
        "candidate",
        "select",
        "rank",
        "score",
        "verify",
        "reconcile",
        "extract",
    )
    if any(term in objective.casefold() for term in forbidden_terms):
        raise CatalyticInferenceBench0Error(
            "restoration assignment contains selection work"
        )


def validate_catalytic_inference_bench_0_plan(
    plan: CatalyticInferenceBench0Plan,
) -> None:
    if not isinstance(plan, CatalyticInferenceBench0Plan):
        raise CatalyticInferenceBench0Error("bench plan has wrong type")
    expected = build_catalytic_inference_bench_0_plan()
    actual_payload = canonical_json_bytes(_plan_payload(plan))
    expected_payload = canonical_json_bytes(_plan_payload(expected))
    if (
        actual_payload != expected_payload
        or plan.plan_sha256 != sha256_bytes(actual_payload)
        or plan.plan_sha256 != expected.plan_sha256
    ):
        raise CatalyticInferenceBench0Error("bench plan differs from canonical")
    if tuple(item.request_id for item in plan.requests) != REQUEST_IDS:
        raise CatalyticInferenceBench0Error("bench request order drift")
    if len(plan.requests) != 13:
        raise CatalyticInferenceBench0Error("bench must contain exactly 13 requests")
    if plan.physical_slot_count != 1 or any(
        item.physical_slot != PHYSICAL_SLOT for item in plan.requests
    ):
        raise CatalyticInferenceBench0Error("bench must use one physical slot")
    validate_public_projection(frozen_task(), plan.public_system_root)
    if sha256_bytes(plan.public_system_root.encode("utf-8")) != plan.public_system_root_sha256:
        raise CatalyticInferenceBench0Error("public root hash mismatch")
    if any(
        item.system_root != plan.public_system_root
        or item.system_root_sha256 != plan.public_system_root_sha256
        for item in plan.requests
    ):
        raise CatalyticInferenceBench0Error("requests do not share exact public root")
    for request in plan.requests:
        if request.required_context_ids != required_context_ids(request.request_id):
            raise CatalyticInferenceBench0Error("required context drift")
        if request.response_schema.get("additionalProperties") is not False:
            raise CatalyticInferenceBench0Error("response schema is not strict")
        if request.max_tokens != MAX_TOKENS_BY_PHASE[request.phase]:
            raise CatalyticInferenceBench0Error("request token bound drift")
        validate_metadata_only(request.assignment)
        validate_metadata_only(request.response_schema)
        if not request.required_context_ids:
            build_model_request(request)
    if plan.request(EXTRACT_ID).ordinal >= plan.request(RESTORE_ID).ordinal:
        raise CatalyticInferenceBench0Error("extraction must precede restoration")
    validate_restoration_request(plan.request(RESTORE_ID))
    validate_dag(plan)


def validate_bench_plan(plan: CatalyticInferenceBench0Plan) -> None:
    validate_catalytic_inference_bench_0_plan(plan)


def _ranking_artifacts(
    observations: Sequence[NormalizedObservation],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    result = []
    for observation in observations:
        if (
            observation.completed
            and observation.request_id in RANKING_REQUEST_IDS
            and observation.artifact is not None
        ):
            result.append(
                (
                    observation.request_id,
                    _ranking_from_artifact(observation.artifact),
                )
            )
    return tuple(result)


def compute_mechanism_metrics(
    plan: CatalyticInferenceBench0Plan,
    observations: Sequence[NormalizedObservation],
) -> MechanismMetrics:
    validate_catalytic_inference_bench_0_plan(plan)
    observations = tuple(observations)
    for observation in observations:
        validate_normalized_metadata(observation)
    rankings = _ranking_artifacts(observations)
    occurrences = [candidate for _, ranking in rankings for candidate in ranking]
    by_id = {item.request_id: item for item in observations}
    extract = by_id.get(EXTRACT_ID)
    if extract is not None and extract.artifact is not None:
        selected = extract.artifact.get("selected_candidate_id")
        if selected in CANDIDATE_IDS:
            occurrences.append(selected)
    counts = Counter(occurrences)
    total_occurrences = sum(counts.values())
    entropy = 0.0
    if total_occurrences:
        entropy = -sum(
            (count / total_occurrences) * math.log2(count / total_occurrences)
            for count in counts.values()
        )
    unique = tuple(item for item in CANDIDATE_IDS if item in counts)
    distinct_rankings = len({ranking for _, ranking in rankings})
    ranking_count = len(rankings)
    phase_entropy: list[tuple[str, float]] = []
    for phase in ("direct", "seed", "transform", "verify", "extract"):
        phase_candidates: list[str] = []
        for observation in observations:
            if observation.phase != phase or observation.artifact is None:
                continue
            if observation.request_id == EXTRACT_ID:
                selected = observation.artifact.get("selected_candidate_id")
                if isinstance(selected, str):
                    phase_candidates.append(selected)
            else:
                phase_candidates.extend(_ranking_from_artifact(observation.artifact))
        phase_counts = Counter(phase_candidates)
        phase_total = sum(phase_counts.values())
        value = 0.0
        if phase_total:
            value = -sum(
                (count / phase_total) * math.log2(count / phase_total)
                for count in phase_counts.values()
            )
        phase_entropy.append((phase, round(value, 6)))

    transform_changed_count = 0
    transform_parent_edges = 0
    transform_changed_edges = 0
    relational_transform_count = 0
    relational_change_record_count = 0
    transform_introduced_candidate_count = 0
    relation_operators: set[str] = set()
    relation_edge_count = 0
    nonself_relation_edge_count = 0
    ranking_edges = 0
    ranking_changed_edges = 0
    for request_id in (*TRANSFORM_IDS, *VERIFY_IDS):
        observation = by_id.get(request_id)
        if observation is None or observation.artifact is None:
            continue
        ranking = _ranking_from_artifact(observation.artifact)
        if request_id in TRANSFORM_IDS and observation.artifact.get(
            "changed_from_parents"
        ) is True:
            transform_changed_count += 1
        if request_id in TRANSFORM_IDS:
            changes = observation.artifact.get("relational_changes", [])
            if isinstance(changes, list) and len(changes) == len(ranking):
                relational_transform_count += 1
                relational_change_record_count += len(changes)
                transform_introduced_candidate_count += sum(
                    item.get("change_kind") == "introduced"
                    for item in changes
                    if isinstance(item, Mapping)
                )
            operator = observation.artifact.get("relation_operator")
            edges = observation.artifact.get("relation_edges", [])
            if isinstance(operator, str):
                relation_operators.add(operator)
            if isinstance(edges, list):
                relation_edge_count += len(edges)
                nonself_relation_edge_count += sum(
                    edge.get("subject_candidate_id")
                    != edge.get("object_candidate_id")
                    for edge in edges
                    if isinstance(edge, Mapping)
                )
        for parent_id in observation.parent_ids:
            parent = by_id.get(parent_id)
            if parent is None or parent.artifact is None:
                continue
            parent_ranking = _ranking_from_artifact(parent.artifact)
            changed = ranking != parent_ranking
            ranking_edges += 1
            ranking_changed_edges += int(changed)
            if request_id in TRANSFORM_IDS:
                transform_parent_edges += 1
                transform_changed_edges += int(changed)

    verifier_rejected = sum(
        len(observation.artifact.get("rejected_candidates", []))
        for observation in observations
        if observation.request_id in VERIFY_IDS and observation.artifact is not None
    )
    rejected_so_far: set[str] = set()
    verifier_restored = 0
    for request_id in VERIFY_IDS:
        observation = by_id.get(request_id)
        if observation is None or observation.artifact is None:
            continue
        survivors = set(observation.artifact.get("surviving_candidates", ()))
        verifier_restored += len(survivors & rejected_so_far)
        rejected_so_far.update(observation.artifact.get("rejected_candidates", ()))
    transform_use_count = 0
    verifier_use_count = 0
    extraction_relation_edge_count = 0
    if extract is not None and extract.artifact is not None:
        transform_use_count = len(extract.artifact.get("transformation_ids_used", []))
        verifier_use_count = len(extract.artifact.get("verifier_ids_used", []))
        extraction_relation_edge_count = len(
            extract.artifact.get("relation_edge_ids_used", [])
        )
    direct = by_id.get(DIRECT_ID)
    final_differs_from_direct = False
    if (
        direct is not None
        and direct.artifact is not None
        and extract is not None
        and extract.artifact is not None
    ):
        final_differs_from_direct = (
            extract.artifact.get("selected_candidate_id")
            != _ranking_from_artifact(direct.artifact)[0]
        )
    return MechanismMetrics(
        unique_candidate_ids=unique,
        candidate_occurrence_count=total_occurrences,
        candidate_entropy_bits=round(entropy, 6),
        candidate_diversity_ratio=round(len(unique) / len(CANDIDATE_IDS), 6),
        distinct_ranking_count=distinct_rankings,
        ranking_artifact_count=ranking_count,
        ranking_diversity_ratio=(
            round(distinct_rankings / ranking_count, 6) if ranking_count else 0.0
        ),
        transform_changed_artifact_count=transform_changed_count,
        transform_parent_edge_count=transform_parent_edges,
        transform_changed_parent_edge_count=transform_changed_edges,
        relational_transform_count=relational_transform_count,
        relational_change_record_count=relational_change_record_count,
        transform_introduced_candidate_count=transform_introduced_candidate_count,
        relation_operator_count=len(relation_operators),
        relation_edge_count=relation_edge_count,
        nonself_relation_edge_count=nonself_relation_edge_count,
        ranking_change_edge_count=ranking_changed_edges,
        ranking_edge_count=ranking_edges,
        verifier_rejected_candidate_count=verifier_rejected,
        verifier_restored_candidate_count=verifier_restored,
        extraction_transform_count=transform_use_count,
        extraction_verifier_count=verifier_use_count,
        extraction_relation_edge_count=extraction_relation_edge_count,
        final_differs_from_direct=final_differs_from_direct,
        candidate_entropy_bits_by_phase=tuple(phase_entropy),
    )


def classify_catalytic_inference_bench_0(
    plan: CatalyticInferenceBench0Plan,
    observations: Sequence[NormalizedObservation],
) -> MechanismAssessment:
    validate_catalytic_inference_bench_0_plan(plan)
    observations = tuple(observations)
    for observation in observations:
        validate_normalized_metadata(observation)
    observed_ids = tuple(item.request_id for item in observations)
    exact_order = observed_ids == REQUEST_IDS
    complete_13 = exact_order and all(item.completed for item in observations)
    completed_count = sum(item.completed for item in observations)
    nonwarm = observations[1:] if exact_order else tuple(
        item for item in observations if item.request_id != WARM_ID
    )
    shared_root = len(observations) == 13 and all(
        item.public_system_root_sha256 == plan.public_system_root_sha256
        for item in observations
    )
    one_slot = plan.physical_slot_count == 1 and all(
        item.physical_slot == PHYSICAL_SLOT for item in observations
    )
    warm_terminal = (
        observations[0].public_root_terminal_token_index
        if exact_order and observations
        else None
    )
    root_reuse = (
        len(nonwarm) == 12
        and shared_root
        and warm_terminal is not None
        and all(
            item.root_reused
            and item.public_root_terminal_token_index == warm_terminal
            and item.cached_prompt_tokens >= item.public_root_terminal_token_index
            for item in nonwarm
        )
    )
    no_hidden_leak = all(not item.hidden_leak_detected for item in observations)
    safety = (
        bool(observations)
        and all(item.safety_passed for item in observations)
        and shared_root
        and one_slot
        and no_hidden_leak
    )
    lineage = validate_lineage(plan, observations)
    valid_lineage = complete_13 and lineage.valid
    metrics = compute_mechanism_metrics(plan, observations)
    at_least_two = len(metrics.unique_candidate_ids) >= 2
    transform_change = metrics.transform_changed_artifact_count >= 1
    by_id = {item.request_id: item for item in observations}
    extract = by_id.get(EXTRACT_ID)
    extraction_uses_transforms = bool(
        extract is not None
        and extract.completed
        and extract.artifact is not None
        and set(extract.artifact.get("transformation_ids_used", ()))
        == set(TRANSFORM_IDS)
        and len(extract.artifact.get("transformation_ids_used", ()))
        == len(TRANSFORM_IDS)
        and set(extract.artifact.get("verifier_ids_used", ()))
        == set(VERIFY_IDS)
        and len(extract.artifact.get("verifier_ids_used", ()))
        == len(VERIFY_IDS)
        and tuple(extract.artifact.get("complete_parent_lineage", ()))
        == _expected_ancestors(EXTRACT_ID)
        and lineage.extraction_lineage_valid
    )
    restore = by_id.get(RESTORE_ID)
    restoration_pass = bool(
        restore is not None
        and restore.completed
        and restore.restoration_passed is True
    )
    all_transform_relations_bound = (
        metrics.relational_transform_count == len(TRANSFORM_IDS)
    )
    all_verifiers_bound = all(
        request_id in by_id
        and by_id[request_id].completed
        and by_id[request_id].artifact is not None
        for request_id in VERIFY_IDS
    )
    controls_parentless = all(
        request_id in by_id and not by_id[request_id].parent_ids
        for request_id in (DIRECT_ID, *SEED_IDS)
    )
    consumption_bound = all(
        request_id in by_id
        and by_id[request_id].artifact is not None
        and isinstance(by_id[request_id].assignment_body_sha256, str)
        and len(by_id[request_id].consumed_artifact_sha256)
        == len(required_context_ids(request_id))
        for request_id in (*TRANSFORM_IDS, *VERIFY_IDS, EXTRACT_ID)
    )
    relation_graph_bound = (
        metrics.relation_edge_count >= len(TRANSFORM_IDS)
        and metrics.nonself_relation_edge_count >= 1
        and metrics.extraction_relation_edge_count >= 1
    )
    relation_operator_diversity = metrics.relation_operator_count >= 2
    gates = (
        ("complete_13_requests", complete_13),
        ("exact_request_order", exact_order),
        ("shared_public_system_root", shared_root),
        ("one_physical_slot", one_slot),
        ("root_reuse_requests_2_13", root_reuse),
        ("valid_lineage", valid_lineage),
        ("dag_depth", complete_13 and lineage.depth_valid),
        ("dag_branching", complete_13 and lineage.branching_valid),
        ("dag_convergence", complete_13 and lineage.convergence_valid),
        ("artifact_parent_integrity", lineage.artifact_parent_integrity),
        ("at_least_two_candidate_ids", at_least_two),
        ("transform_change", transform_change),
        ("all_transform_relations_bound", all_transform_relations_bound),
        ("all_verifiers_bound", all_verifiers_bound),
        ("controls_parentless", controls_parentless),
        ("consumption_bound", consumption_bound),
        ("relation_graph_bound", relation_graph_bound),
        ("relation_operator_diversity", relation_operator_diversity),
        ("extraction_uses_transforms", extraction_uses_transforms),
        ("final_differs_from_direct", metrics.final_differs_from_direct),
        ("restoration_pass", restoration_pass),
        ("no_hidden_leak", no_hidden_leak),
        ("safety", safety),
    )
    gate_map = dict(gates)
    visible_gate_names = (
        "complete_13_requests",
        "root_reuse_requests_2_13",
        "valid_lineage",
        "at_least_two_candidate_ids",
        "transform_change",
        "all_transform_relations_bound",
        "all_verifiers_bound",
        "controls_parentless",
        "consumption_bound",
        "relation_graph_bound",
        "relation_operator_diversity",
        "extraction_uses_transforms",
        "restoration_pass",
        "no_hidden_leak",
        "safety",
    )
    visible = all(gate_map[name] for name in visible_gate_names)
    relational_effect = (
        at_least_two
        and transform_change
        and metrics.ranking_change_edge_count > 0
        and metrics.candidate_entropy_bits > 0.0
    )
    reasons: list[str] = []
    core_cycle_gate_names = (
        "complete_13_requests",
        "exact_request_order",
        "shared_public_system_root",
        "one_physical_slot",
        "root_reuse_requests_2_13",
        "valid_lineage",
        "extraction_uses_transforms",
        "restoration_pass",
        "no_hidden_leak",
        "safety",
    )
    core_cycle_closed = all(gate_map[name] for name in core_cycle_gate_names)
    if not core_cycle_closed:
        classification = MECHANISM_INCONCLUSIVE
        reasons.extend(
            f"core-gate-failed:{name}"
            for name in core_cycle_gate_names
            if not gate_map[name]
        )
    elif visible:
        classification = MECHANISM_VISIBLE
    elif not relational_effect:
        classification = MECHANISM_COLLAPSED
        reasons.append("no-relational-effect")
    else:
        classification = MECHANISM_WEAK
        reasons.extend(
            f"gate-failed:{name}"
            for name in visible_gate_names
            if not gate_map[name]
        )
    return MechanismAssessment(
        status="complete" if complete_13 else "incomplete",
        mechanism_classification=classification,
        gates=gates,
        reasons=tuple(reasons),
        completed_request_count=completed_count,
        restoration_passed=restoration_pass,
        lineage=lineage,
        metrics=metrics,
    )


def classify_mechanism(
    plan: CatalyticInferenceBench0Plan,
    observations: Sequence[NormalizedObservation],
) -> MechanismAssessment:
    return classify_catalytic_inference_bench_0(plan, observations)


def score_extraction(observation: NormalizedObservation) -> dict[str, Any]:
    validate_normalized_metadata(observation)
    if (
        observation.request_id != EXTRACT_ID
        or not observation.completed
        or observation.artifact is None
    ):
        raise CatalyticInferenceBench0Error(
            "scoring is permitted only after completed extraction"
        )
    candidate_id = observation.artifact.get("selected_candidate_id")
    if candidate_id not in CANDIDATE_IDS:
        raise CatalyticInferenceBench0Error("extraction selected candidate is invalid")
    task = frozen_task()
    public_passed, public_total = score_candidate(task, candidate_id, hidden=False)
    hidden_passed, hidden_total = score_candidate(task, candidate_id, hidden=True)
    result = {
        "candidate_id": candidate_id,
        "public_score": {"passed": public_passed, "total": public_total},
        "post_extraction_hidden_diagnostic": {
            "passed": hidden_passed,
            "total": hidden_total,
        },
    }
    validate_metadata_only(result)
    return result


def summarize_catalytic_inference_bench_0(
    plan: CatalyticInferenceBench0Plan,
    observations: Sequence[NormalizedObservation],
    assessment: MechanismAssessment | None = None,
) -> dict[str, Any]:
    observations = tuple(observations)
    canonical_assessment = classify_catalytic_inference_bench_0(
        plan,
        observations,
    )
    if assessment is not None and assessment != canonical_assessment:
        raise CatalyticInferenceBench0Error(
            "summary assessment differs from normalized observations"
        )
    assessment = canonical_assessment
    artifact_trace = [
        {
            "request_id": item.request_id,
            "artifact_sha256": item.artifact_sha256,
            "artifact": json.loads(canonical_json_text(item.artifact)),
        }
        for item in observations
        if item.artifact is not None
    ]
    artifact_dag = {
        "nodes": [
            {
                "request_id": item.request_id,
                "phase": item.phase,
                "parent_artifact_ids": list(item.parent_ids),
                "parent_count": len(item.parent_ids),
                "depth": item.depth,
                "artifact_sha256": item.artifact_sha256,
                "assignment_body_sha256": item.assignment_body_sha256,
                "consumed_artifact_sha256": list(
                    item.consumed_artifact_sha256
                ),
            }
            for item in observations
        ],
        "edges": [
            {"parent": parent_id, "child": item.request_id}
            for item in observations
            for parent_id in item.parent_ids
        ],
    }
    artifact_dag["sha256"] = sha256_bytes(canonical_json_bytes(artifact_dag))
    extracted = next(
        (
            item
            for item in observations
            if item.request_id == EXTRACT_ID and item.artifact is not None
        ),
        None,
    )
    extraction_score = score_extraction(extracted) if extracted is not None else None
    direct = next(
        (
            item
            for item in observations
            if item.request_id == DIRECT_ID and item.artifact is not None
        ),
        None,
    )
    direct_score: dict[str, Any] | None = None
    score_difference: dict[str, int] | None = None
    if extraction_score is not None and direct is not None and direct.artifact is not None:
        direct_candidate_id = _ranking_from_artifact(direct.artifact)[0]
        task = frozen_task()
        direct_public_passed, direct_public_total = score_candidate(
            task, direct_candidate_id, hidden=False
        )
        direct_hidden_passed, direct_hidden_total = score_candidate(
            task, direct_candidate_id, hidden=True
        )
        direct_score = {
            "candidate_id": direct_candidate_id,
            "public_score": {
                "passed": direct_public_passed,
                "total": direct_public_total,
            },
            "post_extraction_hidden_diagnostic": {
                "passed": direct_hidden_passed,
                "total": direct_hidden_total,
            },
        }
        score_difference = {
            "public_passed": (
                extraction_score["public_score"]["passed"] - direct_public_passed
            ),
            "hidden_passed": (
                extraction_score["post_extraction_hidden_diagnostic"]["passed"]
                - direct_hidden_passed
            ),
        }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "bench_id": BENCH_ID,
        "task_id": FROZEN_TASK_ID,
        "plan_sha256": plan.plan_sha256,
        "public_system_root_sha256": plan.public_system_root_sha256,
        "physical_slot_count": PHYSICAL_SLOT_COUNT,
        "logical_request_count": len(REQUEST_IDS),
        "ordered_request_ids": list(REQUEST_IDS),
        "status": assessment.status,
        "mechanism_classification": assessment.mechanism_classification,
        "completed_request_count": assessment.completed_request_count,
        "artifact_trace": artifact_trace,
        "artifact_dag": artifact_dag,
        "metrics": assessment.metrics.to_dict(),
        "restoration_passed": assessment.restoration_passed,
        "direct_baseline_score": direct_score,
        "final_catalytic_score": extraction_score,
        "direct_to_catalytic_score_difference": score_difference,
        "extracted_public_score": (
            {
                "candidate_id": extraction_score["candidate_id"],
                **extraction_score["public_score"],
            }
            if extraction_score is not None
            else None
        ),
        "post_extraction_hidden_diagnostic": (
            {
                "candidate_id": extraction_score["candidate_id"],
                **extraction_score["post_extraction_hidden_diagnostic"],
            }
            if extraction_score is not None
            else None
        ),
        "gates": assessment.gate_map,
        "lineage": assessment.lineage.to_dict(),
        "reasons": list(assessment.reasons),
        "metadata_only": True,
    }
    validate_metadata_only(summary)
    return summary


def summarize_bench(
    plan: CatalyticInferenceBench0Plan,
    observations: Sequence[NormalizedObservation],
    assessment: MechanismAssessment | None = None,
) -> dict[str, Any]:
    return summarize_catalytic_inference_bench_0(
        plan,
        observations,
        assessment,
    )


__all__ = [
    "BENCH_ID",
    "CANDIDATE_IDS",
    "CANDIDATE_REQUEST_IDS",
    "CHECKED_CLAIMS",
    "CONFIDENCE_BUCKETS",
    "CatalyticInferenceBench0Error",
    "CatalyticInferenceBench0Plan",
    "BenchRequestSpec",
    "DIRECT_ID",
    "EXTRACT_ID",
    "EXTRACTION_REASON_CODES",
    "FROZEN_TASK_ID",
    "FROZEN_TASK_INDEX",
    "LineageReport",
    "MAX_STRUCTURED_RESPONSE_BYTES",
    "MAX_TOKENS_PER_REQUEST",
    "MECHANISM_CLASSIFICATIONS",
    "MECHANISM_COLLAPSED",
    "MECHANISM_INCONCLUSIVE",
    "MECHANISM_VISIBLE",
    "MECHANISM_WEAK",
    "MechanismAssessment",
    "MechanismMetrics",
    "NormalizedObservation",
    "PHYSICAL_SLOT",
    "PHYSICAL_SLOT_COUNT",
    "PUBLIC_EVIDENCE_REFS",
    "RANKING_REQUEST_IDS",
    "RELATION_OPERATORS",
    "REQUEST_IDS",
    "RESTORE_ID",
    "SCHEMA_VERSION",
    "SEED_IDS",
    "STRUCTURAL_REASON_CODES",
    "TRANSFORM_IDS",
    "VERIFIER_REASON_CODES",
    "VERIFY_IDS",
    "WARM_ID",
    "build_bench_plan",
    "build_bound_assignment",
    "build_catalytic_inference_bench_0",
    "build_catalytic_inference_bench_0_plan",
    "build_dynamic_parent_context",
    "build_model_request",
    "build_public_system_root",
    "build_request_payload",
    "canonical_json_bytes",
    "canonical_json_text",
    "classify_catalytic_inference_bench_0",
    "classify_mechanism",
    "compute_mechanism_metrics",
    "frozen_task",
    "normalize_observation",
    "normalize_observation_from_metadata",
    "parse_structured_response",
    "required_context_ids",
    "score_extraction",
    "sha256_bytes",
    "summarize_bench",
    "summarize_catalytic_inference_bench_0",
    "validate_bench_plan",
    "validate_catalytic_inference_bench_0_plan",
    "validate_dag",
    "validate_lineage",
    "validate_metadata_only",
    "validate_model_request",
    "validate_no_hidden_leak",
    "validate_normalized_metadata",
    "validate_restoration_request",
    "validate_structured_response",
]
