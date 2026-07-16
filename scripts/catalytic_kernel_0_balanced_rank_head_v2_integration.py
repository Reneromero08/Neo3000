#!/usr/bin/env python3
"""Versioned runtime hooks and two-run design for deterministic rank-head CK0 v2.

This module does not modify the frozen v1 runner. It supplies a v2 runtime
surface with six logical stages, five model requests, controller-native extract,
and a static ordered two-run design over the existing binding-1 and binding-2
private roots. It launches no process and grants no live authority by itself.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2 as v2

INTEGRATION_ID = "balanced-opaque-rank-head-v2-runtime-integration-v1"
STARTING_PROTECTED_MAIN = "25b70f649f0e1cd7eedd21ac7a7711fbdfcac8e6"
RUN_DESIGN_PATH = "lab/ck0_balanced_opaque_rank_head_v2_runtime_design_1.json"
BINDING_1_RUN_ID = "ck0-balanced-v2-rank-head-b1-full-r1"
BINDING_2_RUN_ID = "ck0-balanced-v2-rank-head-b2-full-r1"
RUN_ORDER = (BINDING_1_RUN_ID, BINDING_2_RUN_ID)
RUN_KEY_DOMAIN = b"ck0-balanced-rank-head-v2/runtime-key-v1\0"
VISIBLE_CLASSIFICATION = "BALANCED_OPAQUE_RANK_HEAD_V2_VISIBLE"
COLLAPSED_CLASSIFICATION = "BALANCED_OPAQUE_RANK_HEAD_V2_COLLAPSED"
INCONCLUSIVE_CLASSIFICATION = "INCONCLUSIVE"
LOGICAL_STAGES = v2.LOGICAL_STAGES
MODEL_REQUEST_STAGES = v2.MODEL_REQUEST_STAGES
REQUIRED_AUDITS = {
    "v2_runtime_no_smuggle_auditor": "PASS",
    "v2_run_design_and_custody_auditor": "PASS",
}
REQUIRED_IMPLEMENTATION_PATHS = (
    "scripts/catalytic_kernel_0_balanced_rank_head_v2.py",
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_core.py",
    "scripts/test_catalytic_kernel_0_balanced_rank_head_v2.py",
    "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_core.py",
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_integration.py",
    "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_integration.py",
)


class RankHeadV2IntegrationError(ValueError):
    pass


@dataclass(frozen=True)
class V2RunSpec:
    run_id: str
    ordinal: int
    source_binding: str
    source_profile_id: str
    source_full_run_id: str
    authorization_state: str
    predecessor_run_id: str | None = None

    def body(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "ordinal": self.ordinal,
            "mode": "full-information",
            "source_binding": self.source_binding,
            "source_profile_id": self.source_profile_id,
            "source_full_run_id": self.source_full_run_id,
            "reservation_state": "reserved-unconsumed",
            "authorization_state": self.authorization_state,
            "predecessor_run_id": self.predecessor_run_id,
            "maximum_invocations": 1,
            "retry_count": 0,
            "automatic_follow_on": False,
        }


RUN_SPECS = {
    BINDING_1_RUN_ID: V2RunSpec(
        run_id=BINDING_1_RUN_ID,
        ordinal=1,
        source_binding="binding-1",
        source_profile_id=balanced.BINDING_1_PROFILE_ID,
        source_full_run_id=balanced.FULL_RUN_ID,
        authorization_state="separately-authorizable",
    ),
    BINDING_2_RUN_ID: V2RunSpec(
        run_id=BINDING_2_RUN_ID,
        ordinal=2,
        source_binding="binding-2",
        source_profile_id=balanced.BINDING_2_PROFILE_ID,
        source_full_run_id=balanced.BINDING_2_FULL_RUN_ID,
        authorization_state="unauthorized-until-binding-1-v2-terminal-visible",
        predecessor_run_id=BINDING_1_RUN_ID,
    ),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def json_sha256(value: Any) -> str:
    return sha256_bytes(json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def run_spec(run_id: str) -> V2RunSpec:
    try:
        return RUN_SPECS[run_id]
    except KeyError as exc:
        raise RankHeadV2IntegrationError("unknown v2 run ID") from exc


def source_configuration(spec: V2RunSpec) -> balanced.PrivateBindingConfiguration:
    return balanced.BINDING_1 if spec.source_binding == "binding-1" else balanced.BINDING_2


def derive_v2_run_key(source_private: balanced.PrivateBinding, spec: V2RunSpec) -> bytes:
    source_key = source_private.run_key(spec.source_full_run_id)
    return hmac.new(
        source_key,
        RUN_KEY_DOMAIN + v2.DESIGN_ID.encode("ascii") + b"\0" + spec.source_binding.encode("ascii") + b"\0" + spec.run_id.encode("ascii"),
        hashlib.sha256,
    ).digest()


def runtime_private_from_source(source_private: balanced.PrivateBinding, spec: V2RunSpec) -> balanced.PrivateBinding:
    source = source_configuration(spec)
    if source_private.configuration is not source:
        raise RankHeadV2IntegrationError("source private binding does not match run design")
    configuration = balanced.PrivateBindingConfiguration(
        profile_id=f"{v2.DESIGN_ID}:{spec.source_binding}",
        preregistration_path=RUN_DESIGN_PATH,
        secret_path=source.secret_path,
        creation_receipt_path=source.creation_receipt_path,
        run_modes={spec.run_id: "full-information"},
        domain_separation_identity=f"{v2.DESIGN_ID}:{spec.source_binding}:runtime-v1",
        protected_starting_sha=STARTING_PROTECTED_MAIN,
    )
    return replace(
        source_private,
        configuration=configuration,
        run_keys={spec.run_id: derive_v2_run_key(source_private, spec)},
    )


def runtime_private_from_repository(repository: Path, run_id: str) -> balanced.PrivateBinding:
    spec = run_spec(run_id)
    source_private = balanced._private_binding_from_repository(repository, source_configuration(spec))
    return runtime_private_from_source(source_private, spec)


class RankHeadV2Runtime(balanced.BalancedOpaqueRuntime):
    """Pure runtime hooks consumed by a future separately authorized live entrypoint."""

    def __init__(self, *, repository: Path, spec: V2RunSpec, private: balanced.PrivateBinding, run_design: Mapping[str, Any] | None = None) -> None:
        super().__init__(repository=repository, run_id=spec.run_id, private=private, preregistration=run_design)
        self.spec = spec
        self.carrier = v2.build_v2_carrier()

    @classmethod
    def from_repository(cls, repository: Path, run_id: str, *, require_final_design: bool = True) -> "RankHeadV2Runtime":
        design = validate_run_design(repository, require_final=require_final_design)
        spec = run_spec(run_id)
        return cls(repository=repository, spec=spec, private=runtime_private_from_repository(repository, run_id), run_design=design)

    def carrier_is_pristine(self, carrier: Mapping[str, Any]) -> bool:
        return v2.v2_carrier_is_pristine(carrier)

    def assignment(self, request_id: str, artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
        if request_id not in MODEL_REQUEST_STAGES:
            raise RankHeadV2IntegrationError("v2 extract is controller-native and has no model assignment")
        if request_id in {"borrow", "restore"}:
            return {
                "stage": request_id,
                "carrier_id": v2.V2_CARRIER_ID,
                "instruction": "Acknowledge the immutable opaque carrier exactly." if request_id == "borrow" else "Acknowledge the original immutable opaque carrier only.",
            }
        return super().assignment(request_id, artifacts)

    def build_model_request(self, request_id: str, artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
        assignment = self.assignment(request_id, artifacts)
        payload = {
            "model": balanced.MODEL_ALIAS,
            "messages": [
                {"role": "system", "content": self.carrier["carrier_root"]},
                {"role": "user", "content": balanced.canonical_json_text(assignment)},
            ],
            "temperature": 0.0,
            "seed": balanced._request_seed(request_id),
            "max_tokens": 64,
            "stream": True,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_schema", "json_schema": {"name": f"ck0_rank_head_v2_{request_id.replace('-', '_')}", "strict": True, "schema": v2.v2_response_schema(request_id)}},
            "stream_options": {"include_usage": True},
            "cache_prompt": True,
            "return_tokens": True,
            "return_progress": True,
            "verbose": True,
        }
        self.validate_model_request(request_id, payload, artifacts)
        return payload

    def validate_model_request(self, request_id: str, payload: Mapping[str, Any], artifacts: Mapping[str, Mapping[str, Any]]) -> None:
        if request_id not in MODEL_REQUEST_STAGES:
            raise RankHeadV2IntegrationError("v2 extract model request is forbidden")
        if not v2.v2_carrier_is_pristine(self.carrier):
            raise RankHeadV2IntegrationError("v2 carrier root is not pristine")
        messages = payload.get("messages")
        if not isinstance(messages, list) or len(messages) != 2 or messages[0] != {"role": "system", "content": self.carrier["carrier_root"]}:
            raise RankHeadV2IntegrationError("v2 model request changed the immutable carrier")
        try:
            assignment = json.loads(messages[1]["content"])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise RankHeadV2IntegrationError("v2 assignment is invalid") from exc
        if assignment != self.assignment(request_id, artifacts):
            raise RankHeadV2IntegrationError("v2 assignment differs from its projection")
        if payload.get("chat_template_kwargs") != {"enable_thinking": False}:
            raise RankHeadV2IntegrationError("v2 requests must remain thinking-disabled")
        balanced._assert_no_internal_identity(payload)
        balanced.validate_metadata_only(assignment)

    def parse_response(self, request_id: str, text: str, *, transform_artifact: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if request_id not in MODEL_REQUEST_STAGES:
            raise RankHeadV2IntegrationError("v2 extract has no model response")
        if request_id in {"branch-a", "branch-b", "transform"}:
            return super().parse_response(request_id, text, transform_artifact=transform_artifact)
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RankHeadV2IntegrationError("v2 acknowledgement is invalid JSON") from exc
        if value != {"accepted": True, "carrier_id": v2.V2_CARRIER_ID}:
            raise RankHeadV2IntegrationError("v2 carrier acknowledgement is invalid")
        balanced.validate_metadata_only(value)
        return value

    def deterministic_extract(self, transform: Mapping[str, Any]) -> dict[str, Any]:
        return v2.build_deterministic_extraction_receipt(self, transform)

    def classify_v2(self, artifacts: Mapping[str, Mapping[str, Any]], *, completed_model_responses: int, restoration_passed: bool) -> str:
        if completed_model_responses != len(MODEL_REQUEST_STAGES) or not restoration_passed:
            return INCONCLUSIVE_CLASSIFICATION
        try:
            branch_a = artifacts["branch-a"]
            branch_b = artifacts["branch-b"]
            transform = artifacts["transform"]
            extraction = artifacts["extract"]
            self.verify_branch_artifact(branch_a)
            self.verify_branch_artifact(branch_b)
            self.verify_transform_artifact(transform)
            v2.verify_deterministic_extraction_receipt(self, extraction, transform)
        except (KeyError, balanced.BalancedOpaqueError, v2.RankHeadDesignError):
            return INCONCLUSIVE_CLASSIFICATION
        winner = self.private.internal_to_alias[balanced.EXPECTED_FULL_SUPPORT[0]]
        evaluation = extraction["controller_private_evaluation"]
        geometry = set(branch_a["support_aliases"]) & set(branch_b["support_aliases"]) == {winner}
        correct = transform["ranking"][0] == winner and extraction["candidate_alias"] == winner and evaluation == {"mapped_to_full_public_support": True, "full_public_score": 5, "full_public_total": 5}
        return VISIBLE_CLASSIFICATION if geometry and correct else COLLAPSED_CLASSIFICATION


ModelExecutor = Callable[[str, Mapping[str, Any]], str]


def execute_logical_cycle(runtime: RankHeadV2Runtime, executor: ModelExecutor, *, restoration_passed: bool = True) -> dict[str, Any]:
    """Exercise the integrated mechanism through an injected request executor."""
    artifacts: dict[str, dict[str, Any]] = {}
    outcomes: list[dict[str, Any]] = []
    completed = 0
    for ordinal, stage in enumerate(LOGICAL_STAGES, 1):
        if stage == "extract":
            transform = artifacts.get("transform")
            if not isinstance(transform, Mapping):
                raise RankHeadV2IntegrationError("v2 extract parent is missing")
            artifacts["extract"] = runtime.deterministic_extract(transform)
            outcomes.append({"stage": stage, "ordinal": ordinal, "execution_mode": "controller-deterministic", "model_request_issued": False, "artifact_commitment": artifacts["extract"]["artifact_commitment"]})
            continue
        payload = runtime.build_model_request(stage, artifacts)
        structured = runtime.parse_response(stage, executor(stage, payload), transform_artifact=artifacts.get("transform"))
        completed += 1
        if stage in {"branch-a", "branch-b"}:
            artifacts[stage] = runtime.normalize_branch(stage, structured["ranking"])
        elif stage == "transform":
            artifacts[stage] = runtime.normalize_transform(structured["operator"], structured["ranking"])
        outcomes.append({"stage": stage, "ordinal": ordinal, "execution_mode": "model-request", "model_request_issued": True})
    result = {
        "status": "complete",
        "run_id": runtime.run_id,
        "logical_stage_count": len(LOGICAL_STAGES),
        "model_request_count": completed,
        "outcomes": outcomes,
        "artifacts": artifacts,
        "restoration_passed": restoration_passed,
        "terminal_classification": runtime.classify_v2(artifacts, completed_model_responses=completed, restoration_passed=restoration_passed),
    }
    balanced.validate_metadata_only(result)
    return result


def require_exact_implementation_paths(paths: Sequence[str]) -> None:
    if any(not isinstance(path, str) for path in paths) or tuple(sorted(paths)) != tuple(sorted(REQUIRED_IMPLEMENTATION_PATHS)) or len(set(paths)) != len(paths):
        raise RankHeadV2IntegrationError("v2 runtime binding must contain exactly six files")


def build_run_design(repository: Path, *, implementation_paths: Sequence[str], audits: Mapping[str, str], static_verification: Mapping[str, Any]) -> dict[str, Any]:
    require_exact_implementation_paths(implementation_paths)
    if dict(audits) != REQUIRED_AUDITS:
        raise RankHeadV2IntegrationError("v2 runtime audits must be exact terminal PASS")
    if static_verification.get("status") != "pass":
        raise RankHeadV2IntegrationError("v2 runtime static verification must pass")
    static_projection = v2.validate_preregistration(repository)
    runs = []
    for run_id in RUN_ORDER:
        spec = run_spec(run_id)
        private = runtime_private_from_repository(repository, run_id)
        runs.append({**spec.body(), "run_key_commitment": balanced.run_key_commitment(private.run_key(run_id), private.configuration)})
    document = {
        "schema_version": 1,
        "status": "static-preregistered",
        "integration_id": INTEGRATION_ID,
        "protected_starting_main": STARTING_PROTECTED_MAIN,
        "v2_static_preregistration": static_projection,
        "v2_carrier": {key: v2.build_v2_carrier()[key] for key in ("carrier_id", "carrier_content_sha256", "carrier_root_sha256")},
        "logical_stages": list(LOGICAL_STAGES),
        "model_request_stages": list(MODEL_REQUEST_STAGES),
        "controller_stage": "extract",
        "run_order": list(RUN_ORDER),
        "runs": runs,
        "authorization_boundary": {
            "external_one_shot_authority_required_per_run": True,
            "authority_implementation_requires_separate_static_authorization": True,
            "first_separately_authorizable_run": BINDING_1_RUN_ID,
            "binding_2_run_requires_binding_1_terminal_visible": True,
            "authority_created": False,
            "retry_allowed": False,
            "automatic_follow_on": False,
        },
        "private_state": {
            "new_secret_created": False,
            "source_private_roots": ["binding-1", "binding-2"],
            "source_alias_mappings_preserved": True,
            "v2_run_keys_domain_separated": True,
            "source_private_roots_modified": False,
        },
        "runtime_boundary": {
            "standalone_versioned_runtime_hooks": True,
            "historical_v1_runner_modified": False,
            "holostate_cli_registered": False,
            "live_execution_authorized": False,
            "sidecar_launched": False,
            "model_requests_issued": 0,
        },
        "implementation_binding": balanced.implementation_binding(repository, implementation_paths),
        "audits": dict(audits),
        "static_verification": dict(static_verification),
        "claim_boundary": {
            "historical_binding_2_classification": "BALANCED_OPAQUE_RELATIONAL_COLLAPSED",
            "locked": ["v2-live-correctness", "end-to-end-cross-binding-replication", "binding-2-parent-dependence", "causal-replication", "general-two-parent-necessity", "transfer", "general-catalytic-inference", "task-advantage", "superiority", "sota", "broader-holostate", "restart-persistence", "deep", "automatic-promotion"],
        },
    }
    balanced.validate_metadata_only(document)
    return document


def write_run_design(repository: Path, document: Mapping[str, Any]) -> Path:
    path = repository / RUN_DESIGN_PATH
    if path.exists() or path.is_symlink():
        raise RankHeadV2IntegrationError("v2 run design already exists")
    payload = (json.dumps(document, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=".ck0-rank-head-v2-runtime-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        written = os.write(fd, payload)
        if written != len(payload):
            raise RankHeadV2IntegrationError("v2 run design write was incomplete")
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


def validate_run_design(repository: Path, *, require_final: bool = True) -> dict[str, Any]:
    path = repository / RUN_DESIGN_PATH
    if not path.is_file() or path.is_symlink():
        raise RankHeadV2IntegrationError("v2 run design is missing or unsafe")
    try:
        document = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        raise RankHeadV2IntegrationError("v2 run design is invalid JSON") from exc
    if not isinstance(document, Mapping):
        raise RankHeadV2IntegrationError("v2 run design root is not an object")
    binding = document.get("implementation_binding")
    files = binding.get("files") if isinstance(binding, Mapping) else None
    if not isinstance(files, list) or any(not isinstance(item, Mapping) for item in files):
        raise RankHeadV2IntegrationError("v2 run design binding is malformed")
    paths = [item.get("path") for item in files]
    require_exact_implementation_paths(paths)
    expected = build_run_design(repository, implementation_paths=paths, audits=document.get("audits", {}), static_verification=document.get("static_verification", {}))
    if document != expected:
        raise RankHeadV2IntegrationError("v2 run design differs from exact reconstruction")
    if require_final and (document.get("audits") != REQUIRED_AUDITS or document.get("static_verification", {}).get("status") != "pass"):
        raise RankHeadV2IntegrationError("v2 run design is not terminally qualified")
    return {
        "relative_path": RUN_DESIGN_PATH,
        "artifact_sha256": sha256_bytes(path.read_bytes()),
        "document_sha256": json_sha256(document),
        "implementation_binding_sha256": binding.get("sha256"),
        "run_ids_reserved": list(RUN_ORDER),
        "first_separately_authorizable_run": BINDING_1_RUN_ID,
        "second_run_authorized": False,
        "live_execution_authorized": False,
        "status": "validated-static-run-design",
    }
