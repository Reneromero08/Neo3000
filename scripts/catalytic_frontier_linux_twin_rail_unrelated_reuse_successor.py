#!/usr/bin/env python3
"""neo-exp-0098 actual unrelated restored-fiber reuse successor.

After the consumed useful C->D->B R2 sequence closes, this successor gives the
same physical eight-complex-cell array a new logical carrier identity and asks
an independently preregistered smallest-prime task.  The task boundary, answer
mapping, candidate tokens, grammar, and route order were fixed before model
contact.  A compact recurrence and a cache-disabled materialized request use
the identical 91-token prompt.

Only the 128-byte cell array has NUMERICAL_PHYSICAL_STATE_RESTORATION.  The
live CUDA/KV and host-logit source remains DECLARED_CLOSURE, and the advancing
carrier object metadata remains outside the restoration claim.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import catalytic_frontier_linux_twin_rail_numerical_quotient_successor as parent


EXPERIMENT_ID = "neo-exp-0098"
ATTEMPT_ID = "frontier-attempt-0147"
PREREGISTRATION_ATTEMPT_ID = "frontier-attempt-0146"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_MANIFEST = ROOT / "lab" / "neo-exp-0098-runtime-manifest.json"
DEFAULT_OUTPUT = ROOT / "lab" / "neo-exp-0098.local.json"
DEFAULT_LOCK = ROOT / "build" / "linux-catalytic" / "neo-exp-0098.active-lock.json"
DEFAULT_CONSUMED_MARKER = (
    ROOT / "build" / "linux-catalytic" / "neo-exp-0098.consumed-marker.json"
)
DEFAULT_RUN_PARENT = ROOT / "build" / "linux-catalytic"
BASE_ROOT_ID = "neo-exp-0098-base-684"

EXPECTED_MODEL_CALLBACKS = 43
EXPECTED_DIRECT_PROTOCOL_ACTIONS = 29
UNRELATED_BOUNDARY_PATH = ROOT / "lab" / "neo-exp-0098-unrelated-boundary.json"
UNRELATED_BOUNDARY_FILE_SHA256 = (
    "E8AE2C871974185B383823EE097EBEC06B822E188AB078487B80DC8C50AC5BCD"
)
UNRELATED_TOKEN_COUNT = 91
UNRELATED_TOKEN_SHA256 = (
    "92255F6F30919211CECC0716A10F1B078590681418FDF20682BF401090CA8DEC"
)
UNRELATED_INPUT_BOUNDARY_ID = "fnv1a64:1fd89d3051f37e58"
UNRELATED_RENDERED_PROMPT_SHA256 = (
    "F9613A2E9DD894F6A55B85CC5549D5E442023D1C23F2B127C17E9CDEF2F6F731"
)
UNRELATED_FULL_PROMPT_SHA256 = (
    "D2D241777CC662491631AB0EAA3876F6925A47EB4E3E32BF9BE5ADCAB38C306B"
)
UNRELATED_EXPECTED_ANSWER = "B"
UNRELATED_EXPECTED_TOKEN_ID = 33
UNRELATED_STRUCTURAL_DEVICE_BYTES = 1_863_680
UNRELATED_ADDED_HOST_LOGIT_BYTES_CUMULATIVE = 1_986_560

BASE = parent.parent.parent.parent
RUNTIME_OWNER = BASE.parent

_BASE_INSTALL_IDENTITY = parent.install_identity
_BASE_RESTORE_IDENTITY = parent.restore_identity
_BASE_CONFIGURE_PARENT = parent.configure_parent
_BASE_STATIC_AUDIT = parent.static_audit
_BASE_RUNTIME_MANIFEST_TEMPLATE = parent.runtime_manifest_template
_BASE_VALIDATE_RUNTIME_MANIFEST = parent._BASE_VALIDATE_RUNTIME_MANIFEST
_BASE_POST_PRIMARY_SUCCESSOR = BASE.run_post_primary_successor
_IDENTITY_NAMES = (
    "EXPERIMENT_ID",
    "ATTEMPT_ID",
    "PREREGISTRATION_ATTEMPT_ID",
    "DEFAULT_RUNTIME_MANIFEST",
    "DEFAULT_OUTPUT",
    "DEFAULT_LOCK",
    "DEFAULT_CONSUMED_MARKER",
    "DEFAULT_RUN_PARENT",
    "BASE_ROOT_ID",
)
_IDENTITY_MODULES = (
    parent,
    parent.parent,
    parent.parent.parent,
    BASE,
)
_BASE_IDENTITIES = {
    module: {name: getattr(module, name) for name in _IDENTITY_NAMES}
    for module in _IDENTITY_MODULES
}
_BASE_EXPECTED_MODEL_CALLBACKS = BASE.EXPECTED_MODEL_CALLBACKS
_BASE_EXPECTED_DIRECT_PROTOCOL_ACTIONS = BASE.EXPECTED_DIRECT_PROTOCOL_ACTIONS


def require(condition: bool, message: str) -> None:
    BASE.require(condition, message)


def identity_overrides() -> dict[str, Any]:
    return {
        "EXPERIMENT_ID": EXPERIMENT_ID,
        "ATTEMPT_ID": ATTEMPT_ID,
        "PREREGISTRATION_ATTEMPT_ID": PREREGISTRATION_ATTEMPT_ID,
        "DEFAULT_RUNTIME_MANIFEST": DEFAULT_RUNTIME_MANIFEST,
        "DEFAULT_OUTPUT": DEFAULT_OUTPUT,
        "DEFAULT_LOCK": DEFAULT_LOCK,
        "DEFAULT_CONSUMED_MARKER": DEFAULT_CONSUMED_MARKER,
        "DEFAULT_RUN_PARENT": DEFAULT_RUN_PARENT,
        "BASE_ROOT_ID": BASE_ROOT_ID,
    }


def install_identity() -> None:
    _BASE_INSTALL_IDENTITY()
    for module in _IDENTITY_MODULES:
        for name, value in identity_overrides().items():
            setattr(module, name, value)
    BASE.EXPECTED_MODEL_CALLBACKS = EXPECTED_MODEL_CALLBACKS
    BASE.EXPECTED_DIRECT_PROTOCOL_ACTIONS = EXPECTED_DIRECT_PROTOCOL_ACTIONS


def restore_identity() -> None:
    _BASE_RESTORE_IDENTITY()
    for module, values in _BASE_IDENTITIES.items():
        for name, value in values.items():
            setattr(module, name, value)
    BASE.EXPECTED_MODEL_CALLBACKS = _BASE_EXPECTED_MODEL_CALLBACKS
    BASE.EXPECTED_DIRECT_PROTOCOL_ACTIONS = (
        _BASE_EXPECTED_DIRECT_PROTOCOL_ACTIONS
    )


def configure_parent() -> None:
    _BASE_CONFIGURE_PARENT()
    artifacts = RUNTIME_OWNER.RUNTIME_ARTIFACT_PATHS
    artifacts["controller"] = Path(__file__).resolve()
    artifacts["controller_test"] = (
        ROOT
        / "scripts"
        / "test_catalytic_frontier_linux_twin_rail_unrelated_reuse_successor.py"
    )
    artifacts["numerical_quotient_controller_base"] = (
        ROOT
        / "scripts"
        / "catalytic_frontier_linux_twin_rail_numerical_quotient_successor.py"
    )
    artifacts["unrelated_boundary"] = UNRELATED_BOUNDARY_PATH
    RUNTIME_OWNER.SOURCE_ARTIFACT_NAMES.update(
        {
            "numerical_quotient_controller_base",
            "unrelated_boundary",
        }
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def unrelated_boundary() -> dict[str, Any]:
    require(
        _file_sha256(UNRELATED_BOUNDARY_PATH)
        == UNRELATED_BOUNDARY_FILE_SHA256,
        "0098 unrelated boundary file identity changed",
    )
    value = json.loads(UNRELATED_BOUNDARY_PATH.read_text(encoding="utf-8"))
    tokens = value.get("tokens")
    require(
        isinstance(tokens, list)
        and len(tokens) == UNRELATED_TOKEN_COUNT
        and all(type(token) is int for token in tokens)
        and BASE.canonical_sha256(tokens) == UNRELATED_TOKEN_SHA256
        and BASE.prompt_fnv1a64(tokens)
                == UNRELATED_INPUT_BOUNDARY_ID.removeprefix("fnv1a64:")
        and tuple(tokens[-3:]) == BASE.PUBLIC_SCHEMA_PREFIX,
        "0098 unrelated token boundary changed",
    )
    require(
        value.get("input_boundary_id") == UNRELATED_INPUT_BOUNDARY_ID
        and value.get("rendered_prompt_sha256")
                == UNRELATED_RENDERED_PROMPT_SHA256
        and value.get("full_prompt_sha256") == UNRELATED_FULL_PROMPT_SHA256
        and value.get("assistant_prefix") == '{"answer":"'
        and value.get("assistant_prefix_token_ids")
                == list(BASE.PUBLIC_SCHEMA_PREFIX)
        and value.get("candidate_order") == ["A", "B", "C", "D"]
        and value.get("candidate_token_ids") == [32, 33, 34, 35]
        and value.get("expected_answer") == UNRELATED_EXPECTED_ANSWER
        and value.get("expected_token_id") == UNRELATED_EXPECTED_TOKEN_ID
        and value.get("expected_answer_basis")
                == "2 is the smallest prime number"
        and value.get("chat_template_kwargs") == {"enable_thinking": False}
        and value.get("contact", {}).get("scientific_contact") is False
        and value.get("contact", {}).get("completion_requests") == 0
        and value.get("contact", {}).get("model_callbacks") == 0,
        "0098 unrelated public task or precontact law changed",
    )
    return value


def fixed_unrelated_payload() -> tuple[list[int], dict[str, Any], dict[str, Any]]:
    boundary = unrelated_boundary()
    tokens = list(boundary["tokens"])
    payload = BASE.terminal.completion_payload(tokens, cache_prompt=False)
    payload["cache_prompt"] = False
    payload["grammar"] = BASE.SUFFIX_GRAMMAR
    require(
        payload.get("prompt") == tokens
        and payload.get("cache_prompt") is False
        and payload.get("grammar") == BASE.SUFFIX_GRAMMAR,
        "0098 cache-disabled unrelated payload changed",
    )
    ancestry = {
        "boundary_artifact": UNRELATED_BOUNDARY_PATH.relative_to(ROOT).as_posix(),
        "boundary_artifact_sha256": UNRELATED_BOUNDARY_FILE_SHA256,
        "token_count": UNRELATED_TOKEN_COUNT,
        "token_sha256": UNRELATED_TOKEN_SHA256,
        "input_boundary_id": UNRELATED_INPUT_BOUNDARY_ID,
        "rendered_prompt_sha256": UNRELATED_RENDERED_PROMPT_SHA256,
        "full_prompt_sha256": UNRELATED_FULL_PROMPT_SHA256,
        "public_schema_prefix": list(BASE.PUBLIC_SCHEMA_PREFIX),
        "candidate_token_ids": dict(BASE.CANDIDATE_TOKEN_IDS),
        "expected_answer_predeclared": UNRELATED_EXPECTED_ANSWER,
        "answer_mapping_selected_after_model_output": False,
    }
    return tokens, payload, ancestry


def capture_unrelated_boundary(
        *,
        sidecar: Any,
        payload: Mapping[str, Any],
        contract: Mapping[str, Any],
        label: str,
) -> dict[str, Any]:
    wire = BASE.live.LiveCaptureWireRecorder()
    record = BASE.harness.run_completion(
        sidecar,
        label,
        BASE.capture_payload(payload, contract),
        operation_kind="zero-output-root-readdress",
        recorder=wire,
        batch_owned_request=True,
    )
    require(
        record["prompt_tokens"] == UNRELATED_TOKEN_COUNT
        and record["cached_prompt_tokens"] == 0
        and record["fresh_prompt_tokens"] == UNRELATED_TOKEN_COUNT
        and record["completion_tokens"] == 0,
        "0098 unrelated capture geometry changed",
    )
    return {
        "summary": BASE.harness.token_summary(record),
        "receipt": BASE.live.validate_capture_receipt(record, wire),
        "wall_seconds": float(record["wall_seconds"]),
    }


def run_unrelated_live_route(
        *,
        sidecar: Any,
        codec: Any,
        props: Mapping[str, Any],
        trial: str,
        variant: int,
) -> dict[str, Any]:
    tokens, payload, ancestry = fixed_unrelated_payload()
    contract = BASE.public_contract(
        trial=trial,
        edge=1,
        tokens=tokens,
        variant=variant,
    )
    capture = capture_unrelated_boundary(
        sidecar=sidecar,
        payload=payload,
        contract=contract,
        label=f"{EXPERIMENT_ID}:{trial}:capture",
    )
    consumer = BASE.harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:{trial}:consumer",
        BASE.consumer_payload(payload, contract),
        batch_owned_request=True,
    )
    require(
        consumer["prompt_tokens"] == UNRELATED_TOKEN_COUNT
        and consumer["cached_prompt_tokens"] == UNRELATED_TOKEN_COUNT
        and consumer["fresh_prompt_tokens"] == 0,
        "0098 unrelated live-consumer geometry changed",
    )
    boundary = BASE.validate_suffix_state(
        consumer,
        codec=codec,
        props=props,
        expected_answer=UNRELATED_EXPECTED_ANSWER,
    )
    return {
        "contract": contract,
        "ancestry": ancestry,
        "capture": capture,
        "consumer": BASE.harness.token_summary(consumer),
        "boundary": boundary,
    }


def run_unrelated_materialized(
        *,
        sidecar: Any,
        codec: Any,
        props: Mapping[str, Any],
        trial: str,
) -> dict[str, Any]:
    _tokens, payload, ancestry = fixed_unrelated_payload()
    record = BASE.harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:{trial}:materialized",
        payload,
        batch_owned_request=True,
    )
    require(
        record["prompt_tokens"] == UNRELATED_TOKEN_COUNT
        and record["cached_prompt_tokens"] == 0
        and record["fresh_prompt_tokens"] == UNRELATED_TOKEN_COUNT,
        "0098 unrelated materialized geometry changed",
    )
    return {
        "ancestry": ancestry,
        "record": BASE.harness.token_summary(record),
        "boundary": BASE.validate_suffix_state(
            record,
            codec=codec,
            props=props,
            expected_answer=UNRELATED_EXPECTED_ANSWER,
        ),
    }


def run_post_primary_successor(
        *,
        sidecar: Any,
        codec: Any,
        props: Mapping[str, Any],
        setup: Mapping[str, Any],
        primary: Mapping[str, Any],
        transaction_nonce: str,
        progress: dict[str, Any],
) -> dict[str, Any]:
    del setup, progress
    restored = run_unrelated_live_route(
        sidecar=sidecar,
        codec=codec,
        props=props,
        trial=f"{transaction_nonce}-unrelated-restored",
        variant=BASE.PRIMARY_VARIANT,
    )
    compact = run_unrelated_live_route(
        sidecar=sidecar,
        codec=codec,
        props=props,
        trial=f"{transaction_nonce}-unrelated-compact",
        variant=BASE.COMPACT_CLASSICAL_VARIANT,
    )
    materialized = run_unrelated_materialized(
        sidecar=sidecar,
        codec=codec,
        props=props,
        trial=f"{transaction_nonce}-unrelated",
    )
    contract = restored["contract"]
    completion_tokens = sum(
        int(route["completion_tokens"])
        for route in (
            restored["consumer"],
            compact["consumer"],
            materialized["record"],
        )
    )
    local_gates = {
        "new_logical_carrier_after_dependent_r2": (
            contract["carrier_id"] != primary["carrier_id"]
            and contract["generation"] == 1
            and contract["module_ordinal"] == 1
            and contract["module_variant"] == BASE.PRIMARY_VARIANT
        ),
        "fixed_independent_input_boundary": (
            contract["input_boundary_id"] == UNRELATED_INPUT_BOUNDARY_ID
            and restored["ancestry"]["answer_mapping_selected_after_model_output"]
                    is False
        ),
        "restored_route_capture_91_0_91": (
            restored["capture"]["summary"]["prompt_tokens"] == 91
            and restored["capture"]["summary"]["cached_prompt_tokens"] == 0
            and restored["capture"]["summary"]["fresh_prompt_tokens"] == 91
            and restored["capture"]["summary"]["completion_tokens"] == 0
        ),
        "restored_route_consumer_91_91_0_B": (
            restored["consumer"]["prompt_tokens"] == 91
            and restored["consumer"]["cached_prompt_tokens"] == 91
            and restored["consumer"]["fresh_prompt_tokens"] == 0
            and restored["boundary"]["answer"] == "B"
            and restored["boundary"]["actual_suffix_token_ids"][0] == 33
        ),
        "compact_capture_91_0_91": (
            compact["capture"]["summary"]["prompt_tokens"] == 91
            and compact["capture"]["summary"]["cached_prompt_tokens"] == 0
            and compact["capture"]["summary"]["fresh_prompt_tokens"] == 91
            and compact["capture"]["summary"]["completion_tokens"] == 0
        ),
        "compact_consumer_91_91_0_B": (
            compact["consumer"]["prompt_tokens"] == 91
            and compact["consumer"]["cached_prompt_tokens"] == 91
            and compact["consumer"]["fresh_prompt_tokens"] == 0
            and compact["boundary"]["answer"] == "B"
            and compact["boundary"]["actual_suffix_token_ids"][0] == 33
        ),
        "materialized_91_0_91_B": (
            materialized["record"]["prompt_tokens"] == 91
            and materialized["record"]["cached_prompt_tokens"] == 0
            and materialized["record"]["fresh_prompt_tokens"] == 91
            and materialized["boundary"]["answer"] == "B"
            and materialized["boundary"]["actual_suffix_token_ids"][0] == 33
        ),
        "all_three_routes_exact_eos_suffix": (
            completion_tokens == 9
            and all(
                route["boundary"]["actual_suffix_token_ids"]
                        == [33, 8934, 248046]
                for route in (restored, compact, materialized)
            )
        ),
        "compact_is_identical_public_recurrence": (
            compact["contract"]["module_variant"]
                    == BASE.COMPACT_CLASSICAL_VARIANT
            and compact["contract"]["input_boundary_id"]
                    == contract["input_boundary_id"]
        ),
    }
    passed = all(local_gates.values())
    require(passed, "0098 unrelated useful route gates failed")
    return {
        "carrier_id": contract["carrier_id"],
        "classification_candidate": (
            "BOUNDED_ACTUAL_UNRELATED_USEFUL_NUMERICALLY_RESTORED_"
            "TWIN_RAIL_CELL_BACKING_REUSE_WITH_FRESH_AND_COMPACT_PARITY"
        ),
        "restored_fiber_route": restored,
        "compact_classical_route": compact,
        "materialized_route": materialized,
        "local_gates": local_gates,
        "passed": passed,
        "fixed_operation_count_deltas": {
            "phase_transactions_including_fresh_and_fault_controls": 2,
            "softmax_exponentials": 20,
            "softmax_reductions": 5,
            "softmax_divisions": 20,
            "acos_evaluations": 16,
            "complex_phase_multiplications": 16,
            "hadamard_pair_transforms": 16,
            "magnitude_squares": 8,
            "strict_argmax_comparisons": 15,
            "primary_margin_scan_and_threshold_comparisons": 14,
            "primary_post_transform_acceptance_boolean_checks": 2,
            "restoration_cell_comparisons": 32,
        },
        "resource_additions": {
            "model_callbacks": 5,
            "direct_protocol_actions": 0,
            "prompt_token_callbacks": 455,
            "fresh_prompt_tokens": 273,
            "cached_prompt_tokens": 182,
            "completion_tokens": completion_tokens,
            "captured_host_logit_buffers": 2,
            "captured_host_logit_bytes_cumulative":
                    UNRELATED_ADDED_HOST_LOGIT_BYTES_CUMULATIVE,
            "structural_boundary_tokens": UNRELATED_TOKEN_COUNT,
            "structural_boundary_device_bytes":
                    UNRELATED_STRUCTURAL_DEVICE_BYTES,
            "additional_persistent_phase_cells": 0,
            "additional_persistent_phase_cell_bytes": 0,
        },
        "claim_ceiling": (
            "One independently preregistered useful smallest-prime Agents-A1 "
            "boundary reused the actual numerically restored 128-byte cell "
            "backing immediately after dependent C-to-D-to-B R2 under a new "
            "logical carrier ID, lease, generation-one boundary, fresh-carrier "
            "parity, and exact compact/materialized B parity. This establishes "
            "bounded actual unrelated restored-cell reuse and one increment of "
            "task breadth. The 312-byte carrier object, owner strings, counters, "
            "allocator state, CUDA/KV state, and host logits are not restored; "
            "the source is DECLARED_CLOSURE. The compact recurrence is matched, "
            "so there is no distinct phase-resource, compute/speed advantage, "
            "Small Wall, general, recursive, or unbounded catalytic claim."
        ),
    }


def unrelated_reuse_source_gate() -> bool:
    context = (
        ROOT / "tools" / "server" / "server-context.cpp"
    ).read_text(encoding="utf-8")
    controller = (
        ROOT / "scripts" / "catalytic_frontier_linux_twin_rail_successor.py"
    ).read_text(encoding="utf-8")
    source = Path(__file__).read_text(encoding="utf-8")
    selftest = (
        ROOT / "scripts" / "catalytic_frontier_twin_rail_runtime_selftest.cpp"
    ).read_text(encoding="utf-8")
    primary_call = controller.index("primary = run_primary_sequence(")
    hook_call = controller.index("post_primary = run_post_primary_successor(")
    control_child = controller.index(
        "control_child, control_tokens, control_reset = live.materialize_child("
    )
    return (
        primary_call < hook_call < control_child
        and 'tokens.size() == 91' in context
        and '"1fd89d3051f37e58"' in context
        and "tokens.size() != 780" in context
        and "neo3000_prompt_fnv1a64(task.tokens)" in context
        and "variant=%u" in context
        and "recoveries=%" in context
        and "twin_rail_receipt.recovery_initializations" in context
        and "payload[\"cache_prompt\"] = False" in source
        and "payload[\"grammar\"] = BASE.SUFFIX_GRAMMAR" in source
        and "answer_mapping_selected_after_model_output" in source
        and "warmed-unrelated-smallest-prime" in selftest
        and "fnv1a64:1fd89d3051f37e58" in selftest
        and "unrelated.completed_transactions == 3" in selftest
        and "unrelated.backing_reuses == 2" in selftest
        and "unrelated.recovery_initializations == 0" in selftest
        and (
            (
                "reordered.completed_transactions == 5" in selftest
                and "reordered.backing_reuses == 4" in selftest
            )
            or (
                "reordered.completed_transactions == 6" in selftest
                and "reordered.backing_reuses == 5" in selftest
                and "warmed-unrelated-largest-even" in selftest
            )
        )
        and all(
            term not in BASE.capture_payload({}, {})
            for term in (
                "logits",
                "probabilities",
                "angles",
                "scores",
                "phase_cells",
            )
        )
    )


def static_audit() -> dict[str, Any]:
    value = _BASE_STATIC_AUDIT()
    boundary = unrelated_boundary()
    value["gates"]["fixed_unrelated_boundary_artifact"] = (
        boundary["token_count"] == UNRELATED_TOKEN_COUNT
        and boundary["expected_answer"] == UNRELATED_EXPECTED_ANSWER
        and boundary["input_boundary_id"] == UNRELATED_INPUT_BOUNDARY_ID
    )
    value["gates"]["actual_unrelated_reuse_source_law"] = (
        unrelated_reuse_source_gate()
    )
    value["gates"]["extended_schedule_exact"] = (
        EXPECTED_MODEL_CALLBACKS == 43
        and EXPECTED_DIRECT_PROTOCOL_ACTIONS == 29
    )
    require(
        all(value["gates"].values()),
        "0098 unrelated restored-fiber reuse static gate failed",
    )
    value["id"] = EXPERIMENT_ID
    value["attempt_id"] = ATTEMPT_ID
    value["preregistration_attempt_id"] = PREREGISTRATION_ATTEMPT_ID
    value["predecessor_experiment"] = "neo-exp-0097"
    value["unrelated_boundary"] = {
        "file_sha256": UNRELATED_BOUNDARY_FILE_SHA256,
        "token_count": UNRELATED_TOKEN_COUNT,
        "token_sha256": UNRELATED_TOKEN_SHA256,
        "input_boundary_id": UNRELATED_INPUT_BOUNDARY_ID,
        "expected_answer": UNRELATED_EXPECTED_ANSWER,
        "expected_token_id": UNRELATED_EXPECTED_TOKEN_ID,
    }
    return value


def runtime_manifest_template(runtime_source_commit: str) -> dict[str, Any]:
    manifest = _BASE_RUNTIME_MANIFEST_TEMPLATE(runtime_source_commit)
    manifest["causal_intervention"] = (
        "Immediately after useful primary R2 closes, reuse the same restored "
        "eight-complex-cell backing for one independently fixed 91-token "
        "smallest-prime boundary under a new logical carrier ID, lease, and "
        "generation one; compare fresh, compact, and materialized parity."
    )
    manifest["predecessor_experiment"] = "neo-exp-0097"
    manifest["predecessor_result_sha256"] = (
        "386364FADD37EE0A8CD474601202D48DC8F537FBE448C49EF26A14C61CD8C426"
    )
    manifest["unrelated_boundary"] = {
        "relative_path": UNRELATED_BOUNDARY_PATH.relative_to(ROOT).as_posix(),
        "file_sha256": UNRELATED_BOUNDARY_FILE_SHA256,
        "token_count": UNRELATED_TOKEN_COUNT,
        "token_sha256": UNRELATED_TOKEN_SHA256,
        "input_boundary_id": UNRELATED_INPUT_BOUNDARY_ID,
        "rendered_prompt_sha256": UNRELATED_RENDERED_PROMPT_SHA256,
        "full_prompt_sha256": UNRELATED_FULL_PROMPT_SHA256,
        "assistant_prefix_token_ids": list(BASE.PUBLIC_SCHEMA_PREFIX),
        "candidate_token_ids": dict(BASE.CANDIDATE_TOKEN_IDS),
        "expected_answer": UNRELATED_EXPECTED_ANSWER,
        "expected_token_id": UNRELATED_EXPECTED_TOKEN_ID,
        "fixed_before_model_output": True,
        "answer_conditioned_operator_selection": False,
    }
    manifest["unrelated_reuse_schedule"] = {
        "insertion": "after-useful-primary-r2-before-all-non-primary-controls",
        "added_model_callbacks": 5,
        "total_model_callbacks": EXPECTED_MODEL_CALLBACKS,
        "total_direct_protocol_actions": EXPECTED_DIRECT_PROTOCOL_ACTIONS,
        "final_successful_fiber_transactions": 5,
        "final_backing_reuses": 4,
        "recovery_initializations": 0,
        "expected_routes": [
            "same-backing-restored-primary",
            "identical-compact-classical",
            "cache-disabled-materialized",
        ],
    }
    manifest["unrelated_resource_preregistration"] = {
        "prompt_token_callbacks": 455,
        "fresh_prompt_tokens": 273,
        "cached_prompt_tokens": 182,
        "completion_tokens": 9,
        "captured_host_logit_buffers": 2,
        "captured_host_logit_bytes_cumulative":
                UNRELATED_ADDED_HOST_LOGIT_BYTES_CUMULATIVE,
        "structural_boundary_device_bytes": UNRELATED_STRUCTURAL_DEVICE_BYTES,
        "additional_persistent_phase_cells": 0,
    }
    return manifest


def validate_runtime_manifest() -> dict[str, Any]:
    receipt = _BASE_VALIDATE_RUNTIME_MANIFEST()
    manifest = json.loads(DEFAULT_RUNTIME_MANIFEST.read_text(encoding="utf-8"))
    boundary = manifest.get("unrelated_boundary")
    schedule = manifest.get("unrelated_reuse_schedule")
    resources = manifest.get("unrelated_resource_preregistration")
    require(
        manifest.get("predecessor_experiment") == "neo-exp-0097"
        and manifest.get("predecessor_result_sha256")
                == "386364FADD37EE0A8CD474601202D48DC8F537FBE448C49EF26A14C61CD8C426"
        and manifest.get("capture_progress_counter_reset_before_first_progress")
                is True
        and manifest.get(
            "one_token_control_projection_terminal_class",
            {},
        ).get("route_scope") == ["dephased", "reordered-forward"]
        and manifest.get("reordered_canonical_numerical_quotient", {}).get(
            "route_variant"
        ) == 2
        and manifest.get("primary_nondegenerate_margin_guard", {}).get(
            "top_two_margin_exclusive"
        ) == 2.0e-12
        and boundary
        == {
            "relative_path":
                    "lab/neo-exp-0098-unrelated-boundary.json",
            "file_sha256": UNRELATED_BOUNDARY_FILE_SHA256,
            "token_count": UNRELATED_TOKEN_COUNT,
            "token_sha256": UNRELATED_TOKEN_SHA256,
            "input_boundary_id": UNRELATED_INPUT_BOUNDARY_ID,
            "rendered_prompt_sha256": UNRELATED_RENDERED_PROMPT_SHA256,
            "full_prompt_sha256": UNRELATED_FULL_PROMPT_SHA256,
            "assistant_prefix_token_ids": list(BASE.PUBLIC_SCHEMA_PREFIX),
            "candidate_token_ids": dict(BASE.CANDIDATE_TOKEN_IDS),
            "expected_answer": "B",
            "expected_token_id": 33,
            "fixed_before_model_output": True,
            "answer_conditioned_operator_selection": False,
        }
        and schedule
        == {
            "insertion":
                    "after-useful-primary-r2-before-all-non-primary-controls",
            "added_model_callbacks": 5,
            "total_model_callbacks": 43,
            "total_direct_protocol_actions": 29,
            "final_successful_fiber_transactions": 5,
            "final_backing_reuses": 4,
            "recovery_initializations": 0,
            "expected_routes": [
                "same-backing-restored-primary",
                "identical-compact-classical",
                "cache-disabled-materialized",
            ],
        }
        and resources
        == {
            "prompt_token_callbacks": 455,
            "fresh_prompt_tokens": 273,
            "cached_prompt_tokens": 182,
            "completion_tokens": 9,
            "captured_host_logit_buffers": 2,
            "captured_host_logit_bytes_cumulative":
                    UNRELATED_ADDED_HOST_LOGIT_BYTES_CUMULATIVE,
            "structural_boundary_device_bytes":
                    UNRELATED_STRUCTURAL_DEVICE_BYTES,
            "additional_persistent_phase_cells": 0,
        },
        "0098 unrelated reuse runtime binding changed",
    )
    return {
        **receipt,
        "predecessor_experiment": "neo-exp-0097",
        "unrelated_boundary": dict(boundary),
        "unrelated_reuse_schedule": dict(schedule),
        "unrelated_resource_preregistration": dict(resources),
    }


def main() -> int:
    parent.install_identity = install_identity
    parent.configure_parent = configure_parent
    parent.static_audit = static_audit
    parent.runtime_manifest_template = runtime_manifest_template
    parent.validate_runtime_manifest = validate_runtime_manifest
    BASE.run_post_primary_successor = run_post_primary_successor
    return parent.main()


if __name__ == "__main__":
    raise SystemExit(main())
