#!/usr/bin/env python3
"""neo-exp-0100 second independent restored-cell reuse successor.

The accepted 0099 smallest-prime B transaction remains unchanged.  This
successor adds one independently frozen largest-even D boundary immediately
after it and before every sham, fault, or direct control.  The restored
128-byte eight-complex-cell backing is the only reused physical substrate.

The successful sequence must reach four useful persistent transactions with
zero recovery initialization.  The later destructive inverse-fault controls
must then expose the exact recovery-initialization sequence 0, 1, 2.  This
distinguishes successful substrate reuse from post-success fault recovery.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

import catalytic_frontier_linux_twin_rail_cache_enabled_consumer_successor as parent


EXPERIMENT_ID = "neo-exp-0100"
ATTEMPT_ID = "frontier-attempt-0151"
PREREGISTRATION_ATTEMPT_ID = "frontier-attempt-0150"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_MANIFEST = ROOT / "lab" / "neo-exp-0100-runtime-manifest.json"
DEFAULT_OUTPUT = ROOT / "lab" / "neo-exp-0100.local.json"
DEFAULT_LOCK = ROOT / "build" / "linux-catalytic" / "neo-exp-0100.active-lock.json"
DEFAULT_CONSUMED_MARKER = (
    ROOT / "build" / "linux-catalytic" / "neo-exp-0100.consumed-marker.json"
)
DEFAULT_RUN_PARENT = ROOT / "build" / "linux-catalytic"
BASE_ROOT_ID = "neo-exp-0100-base-684"

EXPECTED_MODEL_CALLBACKS = 48
EXPECTED_DIRECT_PROTOCOL_ACTIONS = 29
SECOND_BOUNDARY_PATH = (
    ROOT / "lab" / "neo-exp-0100-second-unrelated-boundary.json"
)
SECOND_BOUNDARY_FILE_SHA256 = (
    "728723CCE08711DC48313F0EACD97B3A3F8E20ED3C98FAC88992643695CAC6D4"
)
SECOND_TOKEN_COUNT = 91
SECOND_TOKEN_SHA256 = (
    "7B66B90DBBA9E9EF3A840EAF51D064BF96B7B35057F5F5E0E3C7F61130B0F1A9"
)
SECOND_INPUT_BOUNDARY_ID = "fnv1a64:4c0d82dcecacca31"
SECOND_RENDERED_PROMPT_SHA256 = (
    "4F2AA926DAF38E7F5142743220158F7931E711BC3CF399D3714D1B55835BAAB6"
)
SECOND_FULL_PROMPT_SHA256 = (
    "E3173E01502F51B12D6398882930E39FD6FB04FF02AE0CA1CE45792681C5257D"
)
SECOND_EXPECTED_ANSWER = "D"
SECOND_EXPECTED_TOKEN_ID = 35
SECOND_EXPECTED_SUFFIX = [35, 8934, 248046]
SECOND_STRUCTURAL_DEVICE_BYTES = 1_863_680
SECOND_ADDED_HOST_LOGIT_BYTES_CUMULATIVE = 1_986_560

BASE = parent.BASE
RUNTIME_OWNER = parent.RUNTIME_OWNER

_BASE_INSTALL_IDENTITY = parent.install_identity
_BASE_RESTORE_IDENTITY = parent.restore_identity
_BASE_CONFIGURE_PARENT = parent.configure_parent
_BASE_STATIC_AUDIT = parent.static_audit
_BASE_RUNTIME_MANIFEST_TEMPLATE = parent.runtime_manifest_template
_BASE_VALIDATE_RUNTIME_MANIFEST = parent.validate_runtime_manifest
_BASE_RUN_POST_PRIMARY_SUCCESSOR = parent.parent.run_post_primary_successor
_IDENTITY_NAMES = parent._IDENTITY_NAMES
_IDENTITY_MODULES = (parent, *parent._IDENTITY_MODULES)
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
        / "test_catalytic_frontier_linux_twin_rail_second_unrelated_successor.py"
    )
    artifacts["cache_enabled_consumer_controller_base"] = (
        ROOT
        / "scripts"
        / "catalytic_frontier_linux_twin_rail_cache_enabled_consumer_successor.py"
    )
    artifacts["second_unrelated_boundary"] = SECOND_BOUNDARY_PATH
    artifacts["runtime_selftest_binary"] = (
        ROOT / "build" / "linux-catalytic" / "neo-exp-0100-static"
        / "twin-rail-selftest"
    )
    RUNTIME_OWNER.SOURCE_ARTIFACT_NAMES.update(
        {
            "cache_enabled_consumer_controller_base",
            "second_unrelated_boundary",
        }
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def second_boundary() -> dict[str, Any]:
    require(
        _file_sha256(SECOND_BOUNDARY_PATH) == SECOND_BOUNDARY_FILE_SHA256,
        "0100 second unrelated boundary file identity changed",
    )
    value = json.loads(SECOND_BOUNDARY_PATH.read_text(encoding="utf-8"))
    tokens = value.get("tokens")
    require(
        isinstance(tokens, list)
        and len(tokens) == SECOND_TOKEN_COUNT
        and all(type(token) is int for token in tokens)
        and BASE.canonical_sha256(tokens) == SECOND_TOKEN_SHA256
        and BASE.prompt_fnv1a64(tokens)
                == SECOND_INPUT_BOUNDARY_ID.removeprefix("fnv1a64:")
        and tuple(tokens[-3:]) == BASE.PUBLIC_SCHEMA_PREFIX,
        "0100 second unrelated token boundary changed",
    )
    require(
        value.get("id") == "neo-exp-0100-second-unrelated-boundary"
        and value.get("input_boundary_id") == SECOND_INPUT_BOUNDARY_ID
        and value.get("rendered_prompt_sha256")
                == SECOND_RENDERED_PROMPT_SHA256
        and value.get("full_prompt_sha256") == SECOND_FULL_PROMPT_SHA256
        and value.get("assistant_prefix") == '{"answer":"'
        and value.get("assistant_prefix_token_ids")
                == list(BASE.PUBLIC_SCHEMA_PREFIX)
        and value.get("candidate_order") == ["A", "B", "C", "D"]
        and value.get("candidate_token_ids") == [32, 33, 34, 35]
        and value.get("expected_answer") == SECOND_EXPECTED_ANSWER
        and value.get("expected_token_id") == SECOND_EXPECTED_TOKEN_ID
        and value.get("expected_answer_basis")
                == "6 is the largest even number among 1, 2, 4, and 6"
        and value.get("chat_template_kwargs") == {"enable_thinking": False}
        and value.get("preregistration_attempt_id") == "frontier-attempt-0150"
        and value.get("contact", {}).get("scientific_contact") is False
        and value.get("contact", {}).get("completion_requests") == 0
        and value.get("contact", {}).get("prompt_evaluations") == 0
        and value.get("contact", {}).get("model_callbacks") == 0,
        "0100 second public task or precontact law changed",
    )
    return value


def fixed_second_payload() -> tuple[list[int], dict[str, Any], dict[str, Any]]:
    boundary = second_boundary()
    tokens = list(boundary["tokens"])
    payload = BASE.terminal.completion_payload(tokens, cache_prompt=False)
    payload["cache_prompt"] = False
    payload["grammar"] = BASE.SUFFIX_GRAMMAR
    require(
        payload.get("prompt") == tokens
        and payload.get("cache_prompt") is False
        and payload.get("grammar") == BASE.SUFFIX_GRAMMAR,
        "0100 cache-disabled second unrelated payload changed",
    )
    return tokens, payload, {
        "boundary_artifact":
                SECOND_BOUNDARY_PATH.relative_to(ROOT).as_posix(),
        "boundary_artifact_sha256": SECOND_BOUNDARY_FILE_SHA256,
        "token_count": SECOND_TOKEN_COUNT,
        "token_sha256": SECOND_TOKEN_SHA256,
        "input_boundary_id": SECOND_INPUT_BOUNDARY_ID,
        "rendered_prompt_sha256": SECOND_RENDERED_PROMPT_SHA256,
        "full_prompt_sha256": SECOND_FULL_PROMPT_SHA256,
        "public_schema_prefix": list(BASE.PUBLIC_SCHEMA_PREFIX),
        "candidate_token_ids": dict(BASE.CANDIDATE_TOKEN_IDS),
        "expected_answer_predeclared": SECOND_EXPECTED_ANSWER,
        "answer_mapping_selected_after_model_output": False,
    }


def run_second_live_route(
        *,
        sidecar: Any,
        codec: Any,
        props: Mapping[str, Any],
        trial: str,
        variant: int,
) -> dict[str, Any]:
    tokens, payload, ancestry = fixed_second_payload()
    contract = BASE.public_contract(
        trial=trial,
        edge=1,
        tokens=tokens,
        variant=variant,
    )
    capture = parent.parent.capture_unrelated_boundary(
        sidecar=sidecar,
        payload=payload,
        contract=contract,
        label=f"{EXPERIMENT_ID}:{trial}:capture",
    )
    consumer_wire = parent.cache_enabled_consumer_payload(payload, contract)
    consumer = BASE.harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:{trial}:consumer",
        consumer_wire,
        batch_owned_request=True,
    )
    require(
        consumer_wire["cache_prompt"] is True
        and consumer["prompt_tokens"] == SECOND_TOKEN_COUNT
        and consumer["cached_prompt_tokens"] == SECOND_TOKEN_COUNT
        and consumer["fresh_prompt_tokens"] == 0,
        "0100 cache-enabled second live-consumer geometry changed",
    )
    boundary = BASE.validate_suffix_state(
        consumer,
        codec=codec,
        props=props,
        expected_answer=SECOND_EXPECTED_ANSWER,
    )
    return {
        "contract": contract,
        "ancestry": ancestry,
        "capture": capture,
        "consumer_request": {
            "cache_prompt": True,
            "sampler_fingerprint_changed_by_cache_prompt": False,
        },
        "consumer": BASE.harness.token_summary(consumer),
        "boundary": boundary,
    }


def run_second_materialized(
        *,
        sidecar: Any,
        codec: Any,
        props: Mapping[str, Any],
        trial: str,
) -> dict[str, Any]:
    _tokens, payload, ancestry = fixed_second_payload()
    record = BASE.harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:{trial}:materialized",
        payload,
        batch_owned_request=True,
    )
    require(
        record["prompt_tokens"] == SECOND_TOKEN_COUNT
        and record["cached_prompt_tokens"] == 0
        and record["fresh_prompt_tokens"] == SECOND_TOKEN_COUNT,
        "0100 second unrelated materialized geometry changed",
    )
    return {
        "ancestry": ancestry,
        "record": BASE.harness.token_summary(record),
        "boundary": BASE.validate_suffix_state(
            record,
            codec=codec,
            props=props,
            expected_answer=SECOND_EXPECTED_ANSWER,
        ),
    }


_SECOND_OPERATION_DELTAS = {
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
    first = _BASE_RUN_POST_PRIMARY_SUCCESSOR(
        sidecar=sidecar,
        codec=codec,
        props=props,
        setup=setup,
        primary=primary,
        transaction_nonce=transaction_nonce,
        progress=progress,
    )
    restored = run_second_live_route(
        sidecar=sidecar,
        codec=codec,
        props=props,
        trial=f"{transaction_nonce}-second-unrelated-restored",
        variant=BASE.PRIMARY_VARIANT,
    )
    compact = run_second_live_route(
        sidecar=sidecar,
        codec=codec,
        props=props,
        trial=f"{transaction_nonce}-second-unrelated-compact",
        variant=BASE.COMPACT_CLASSICAL_VARIANT,
    )
    materialized = run_second_materialized(
        sidecar=sidecar,
        codec=codec,
        props=props,
        trial=f"{transaction_nonce}-second-unrelated",
    )
    completion_tokens = sum(
        int(route["completion_tokens"])
        for route in (
            restored["consumer"],
            compact["consumer"],
            materialized["record"],
        )
    )
    contract = restored["contract"]
    local_gates = {
        "first_unrelated_successor_remains_accepted": first["passed"] is True,
        "second_new_logical_carrier": (
            contract["carrier_id"] != first["carrier_id"]
            and contract["generation"] == 1
            and contract["module_ordinal"] == 1
            and contract["module_variant"] == BASE.PRIMARY_VARIANT
        ),
        "fixed_second_input_boundary": (
            contract["input_boundary_id"] == SECOND_INPUT_BOUNDARY_ID
            and restored["ancestry"][
                "answer_mapping_selected_after_model_output"
            ] is False
        ),
        "restored_capture_91_0_91_0": (
            restored["capture"]["summary"]["prompt_tokens"] == 91
            and restored["capture"]["summary"]["cached_prompt_tokens"] == 0
            and restored["capture"]["summary"]["fresh_prompt_tokens"] == 91
            and restored["capture"]["summary"]["completion_tokens"] == 0
        ),
        "restored_consumer_91_91_0_D": (
            restored["consumer"]["prompt_tokens"] == 91
            and restored["consumer"]["cached_prompt_tokens"] == 91
            and restored["consumer"]["fresh_prompt_tokens"] == 0
            and restored["boundary"]["answer"] == "D"
            and restored["boundary"]["actual_suffix_token_ids"]
                    == SECOND_EXPECTED_SUFFIX
        ),
        "compact_capture_91_0_91_0": (
            compact["capture"]["summary"]["prompt_tokens"] == 91
            and compact["capture"]["summary"]["cached_prompt_tokens"] == 0
            and compact["capture"]["summary"]["fresh_prompt_tokens"] == 91
            and compact["capture"]["summary"]["completion_tokens"] == 0
        ),
        "compact_consumer_91_91_0_D": (
            compact["consumer"]["prompt_tokens"] == 91
            and compact["consumer"]["cached_prompt_tokens"] == 91
            and compact["consumer"]["fresh_prompt_tokens"] == 0
            and compact["boundary"]["answer"] == "D"
            and compact["boundary"]["actual_suffix_token_ids"]
                    == SECOND_EXPECTED_SUFFIX
        ),
        "materialized_91_0_91_D": (
            materialized["record"]["prompt_tokens"] == 91
            and materialized["record"]["cached_prompt_tokens"] == 0
            and materialized["record"]["fresh_prompt_tokens"] == 91
            and materialized["boundary"]["answer"] == "D"
            and materialized["boundary"]["actual_suffix_token_ids"]
                    == SECOND_EXPECTED_SUFFIX
        ),
        "all_three_second_routes_exact_eos_suffix": completion_tokens == 9,
        "compact_is_identical_public_recurrence": (
            compact["contract"]["module_variant"]
                    == BASE.COMPACT_CLASSICAL_VARIANT
            and compact["contract"]["input_boundary_id"]
                    == contract["input_boundary_id"]
        ),
    }
    require(all(local_gates.values()), "0100 second unrelated route gates failed")

    first_deltas = first["fixed_operation_count_deltas"]
    combined_deltas = {
        key: int(first_deltas.get(key, 0)) + delta
        for key, delta in _SECOND_OPERATION_DELTAS.items()
    }
    first_resources = first["resource_additions"]
    combined_resources = {
        "model_callbacks": int(first_resources["model_callbacks"]) + 5,
        "direct_protocol_actions":
                int(first_resources["direct_protocol_actions"]),
        "prompt_token_callbacks":
                int(first_resources["prompt_token_callbacks"]) + 455,
        "fresh_prompt_tokens":
                int(first_resources["fresh_prompt_tokens"]) + 273,
        "cached_prompt_tokens":
                int(first_resources["cached_prompt_tokens"]) + 182,
        "completion_tokens":
                int(first_resources["completion_tokens"]) + completion_tokens,
        "captured_host_logit_buffers":
                int(first_resources["captured_host_logit_buffers"]) + 2,
        "captured_host_logit_bytes_cumulative": (
            int(first_resources["captured_host_logit_bytes_cumulative"])
            + SECOND_ADDED_HOST_LOGIT_BYTES_CUMULATIVE
        ),
        "structural_boundary_tokens": (
            int(first_resources["structural_boundary_tokens"])
            + SECOND_TOKEN_COUNT
        ),
        "structural_boundary_device_bytes": (
            int(first_resources["structural_boundary_device_bytes"])
            + SECOND_STRUCTURAL_DEVICE_BYTES
        ),
        "additional_persistent_phase_cells": 0,
    }
    return {
        "carrier_id": contract["carrier_id"],
        "classification_candidate": (
            "BOUNDED_ACTUAL_TWO_UNRELATED_USEFUL_NUMERICALLY_RESTORED_"
            "TWIN_RAIL_CELL_BACKING_REUSES_WITH_B_D_FRESH_AND_COMPACT_PARITY"
        ),
        "first_unrelated_successor": first,
        "second_restored_fiber_route": restored,
        "second_compact_classical_route": compact,
        "second_materialized_route": materialized,
        "local_gates": local_gates,
        "passed": True,
        "expected_unrelated_primary_count": 2,
        "expected_post_success_fault_recovery_initializations": 2,
        "fixed_operation_count_deltas": combined_deltas,
        "resource_additions": combined_resources,
        "two_unrelated_task_totals": {
            "useful_task_boundaries": 2,
            "expected_answers": ["B", "D"],
            "prompt_token_callbacks": 910,
            "fresh_prompt_tokens": 546,
            "cached_prompt_tokens": 364,
            "completion_tokens": 18,
            "captured_host_logit_buffers_sequential": 4,
            "captured_host_logit_bytes_cumulative": 3_973_120,
            "maximum_simultaneously_live_boundary_buffers": 1,
            "additional_persistent_phase_cells": 0,
        },
    }


def _numerical_metrics(line: str) -> dict[str, float]:
    match = re.search(
        r"score_error=([0-9eE+.-]+) "
        r"restoration_error=([0-9eE+.-]+).* "
        r"fresh_restoration_error=([0-9eE+.-]+)",
        line,
    )
    require(match is not None, "0100 unrelated numerical metrics absent")
    metrics = {
        "maximum_score_error": float(match.group(1)),
        "maximum_restoration_error": float(match.group(2)),
        "fresh_maximum_restoration_error": float(match.group(3)),
    }
    require(
        all(0.0 <= value <= 1.0e-12 for value in metrics.values()),
        "0100 unrelated numerical restoration tolerance changed",
    )
    return metrics


def phase_log_evidence(
        *,
        sidecar: Any,
        primary_carrier_id: str,
        unrelated_carrier_id: str | None = None,
) -> dict[str, Any]:
    require(
        unrelated_carrier_id is not None,
        "0100 second unrelated carrier identity absent",
    )
    log_path = Path(str(sidecar.readiness["log_path"]))
    text = log_path.read_text(encoding="utf-8", errors="replace")
    success_lines = [
        line for line in text.splitlines()
        if "neo3000 twin-rail carrier restored and live source "
        "declared-closed before response" in line
    ]
    rejection_lines = [
        line for line in text.splitlines()
        if "neo3000 twin-rail transaction rejected and live source poisoned"
        in line
    ]
    require(
        len(success_lines) == 6 and len(rejection_lines) == 3,
        "0100 success or inverse-fault lifecycle count changed",
    )
    expected = (
        (0, 1, 0, 1, 1, True, False, True, False),
        (0, 2, 1, 2, 2, True, False, True, True),
        (0, 3, 2, 1, 1, True, False, True, True),
        (0, 4, 3, 1, 1, True, False, True, True),
        (1, 5, 4, 1, 1, False, False, False, True),
        (2, 6, 5, 1, 1, False, True, False, True),
    )
    for line, (
        variant,
        transactions,
        reuses,
        generation,
        ordinal,
        margin,
        quotient,
        fresh,
        backing_reused,
    ) in zip(success_lines, expected, strict=True):
        require(
            f"variant={variant}" in line
            and f"generation={generation} ordinal={ordinal}" in line
            and f"transactions={transactions} reuses={reuses} recoveries=0"
                    in line
            and f"primary_margin_guard={'true' if margin else 'false'}"
                    in line
            and f"canonical_tie_quotient={'true' if quotient else 'false'}"
                    in line
            and f"fresh_parity={'true' if fresh else 'false'}" in line
            and (
                f"backing_reused={'true' if backing_reused else 'false'}"
                in line
            ),
            "0100 complete success order or lifetime counters changed",
        )
    require(
        all(f"carrier={primary_carrier_id} " in line for line in success_lines[:2])
        and "-unrelated-restored/slot-0 " in success_lines[2]
        and f"carrier={unrelated_carrier_id} " in success_lines[3],
        "0100 primary or independent carrier identity order changed",
    )
    hidden_terms = ("logits=[", "probabilities=", "angles=", "scores=", "phase_cells=")
    require(
        all(
            "canonical_tie_quotient=" in line
            and "primary_margin_guard=" in line
            and all(term not in line for term in hidden_terms)
            for line in success_lines
        )
        and all(
            all(term not in line for term in hidden_terms)
            for line in rejection_lines
        ),
        "0100 lifecycle log leaked an unresolved intermediate",
    )
    rejection_counters = [
        tuple(int(value) for value in match)
        for match in re.findall(
            r"transactions=(\d+) reuses=(\d+) recoveries=(\d+)",
            "\n".join(rejection_lines),
        )
    ]
    require(
        rejection_counters == [(6, 5, 0), (6, 5, 1), (6, 5, 2)],
        "0100 post-success inverse-fault recovery sequence changed",
    )
    material_patterns = {
        "persistent_object_bytes": r" object_bytes=(\d+)",
        "persistent_dynamic_capacity_bytes":
                r" dynamic_capacity_bytes=(\d+)",
        "fresh_object_bytes": r" fresh_object_bytes=(\d+)",
        "fresh_dynamic_capacity_bytes":
                r" fresh_dynamic_capacity_bytes=(\d+)",
        "receipt_bytes": r" receipt_bytes=(\d+)",
        "contract_bytes": r" contract_bytes=(\d+)",
        "fresh_result_bytes": r" fresh_result_bytes=(\d+)",
    }
    material: dict[str, int] = {}
    success_text = "\n".join(success_lines)
    for name, pattern in material_patterns.items():
        values = [int(value) for value in re.findall(pattern, success_text)]
        require(
            len(values) == len(success_lines),
            f"0100 {name} accounting is absent",
        )
        material[name] = max(values)
    first_metrics = _numerical_metrics(success_lines[2])
    second_metrics = _numerical_metrics(success_lines[3])
    combined_metrics = {
        key: max(first_metrics[key], second_metrics[key])
        for key in first_metrics
    }
    return {
        "success_count": 6,
        "primary_count": 2,
        "unrelated_primary_count": 2,
        "inverse_rejection_count": 3,
        "primary_generation_1": True,
        "primary_generation_2_same_backing": True,
        "fresh_parity_both_edges": True,
        "canonical_tie_quotient_count": 1,
        "primary_margin_guard_count": 4,
        **material,
        "maximum_recovery_initializations": 0,
        "post_success_fault_recovery_initializations": 2,
        "post_success_fault_recovery_sequence": [0, 1, 2],
        "unrelated_numerical_metrics": combined_metrics,
        "first_unrelated_numerical_metrics": first_metrics,
        "second_unrelated_numerical_metrics": second_metrics,
        "server_log_sha256_so_far":
                BASE.harness.live_runtime.sha256_file(log_path),
    }


def second_reuse_source_gate() -> bool:
    context = (
        ROOT / "tools" / "server" / "server-context.cpp"
    ).read_text(encoding="utf-8")
    selftest = (
        ROOT / "scripts" / "catalytic_frontier_twin_rail_runtime_selftest.cpp"
    ).read_text(encoding="utf-8")
    source = Path(__file__).read_text(encoding="utf-8")
    return (
        'neo3000_prompt_fnv1a64(tokens) == "1fd89d3051f37e58" ||'
                in context
        and 'neo3000_prompt_fnv1a64(tokens) == "4c0d82dcecacca31"'
                in context
        and "transactions=%" in context
        and "reuses=%" in context
        and "recoveries=%" in context
        and "warmed-unrelated-largest-even" in selftest
        and "fnv1a64:4c0d82dcecacca31" in selftest
        and "second_unrelated.completed_transactions == 4" in selftest
        and "second_unrelated.backing_reuses == 3" in selftest
        and "carrier.recovery_initializations() == 2" in selftest
        and "expected_unrelated_primary_count" in source
        and "post_success_fault_recovery_sequence" in source
    )


def static_audit() -> dict[str, Any]:
    value = _BASE_STATIC_AUDIT()
    boundary = second_boundary()
    value["gates"]["fixed_second_unrelated_boundary_artifact"] = (
        boundary["token_count"] == SECOND_TOKEN_COUNT
        and boundary["expected_answer"] == SECOND_EXPECTED_ANSWER
        and boundary["input_boundary_id"] == SECOND_INPUT_BOUNDARY_ID
    )
    value["gates"]["second_restored_backing_reuse_source_law"] = (
        second_reuse_source_gate()
    )
    value["gates"]["extended_schedule_exact"] = (
        EXPECTED_MODEL_CALLBACKS == 48
        and EXPECTED_DIRECT_PROTOCOL_ACTIONS == 29
    )
    require(
        all(value["gates"].values()),
        "0100 second unrelated reuse static gate failed",
    )
    value["id"] = EXPERIMENT_ID
    value["attempt_id"] = ATTEMPT_ID
    value["preregistration_attempt_id"] = PREREGISTRATION_ATTEMPT_ID
    value["predecessor_experiment"] = "neo-exp-0099"
    value["second_unrelated_boundary"] = {
        "file_sha256": SECOND_BOUNDARY_FILE_SHA256,
        "token_count": SECOND_TOKEN_COUNT,
        "token_sha256": SECOND_TOKEN_SHA256,
        "input_boundary_id": SECOND_INPUT_BOUNDARY_ID,
        "expected_answer": SECOND_EXPECTED_ANSWER,
        "expected_token_id": SECOND_EXPECTED_TOKEN_ID,
    }
    return value


def runtime_manifest_template(runtime_source_commit: str) -> dict[str, Any]:
    manifest = _BASE_RUNTIME_MANIFEST_TEMPLATE(runtime_source_commit)
    manifest["causal_intervention"] = (
        "After the accepted independently fixed smallest-prime B reuse and "
        "before every non-primary control, reuse the same restored eight-"
        "complex-cell backing for one independently fixed 91-token largest-"
        "even D boundary; change no phase algebra, cell count, inverse, "
        "projection law, sampler, or existing task."
    )
    manifest["predecessor_experiment"] = "neo-exp-0099"
    manifest["predecessor_result_sha256"] = (
        "7A53E171B79B6D726DBA9B6A1E78DB67F869B454C4C9BB9B975EE02C7992B6F9"
    )
    manifest["second_unrelated_boundary"] = {
        "relative_path": SECOND_BOUNDARY_PATH.relative_to(ROOT).as_posix(),
        "file_sha256": SECOND_BOUNDARY_FILE_SHA256,
        "token_count": SECOND_TOKEN_COUNT,
        "token_sha256": SECOND_TOKEN_SHA256,
        "input_boundary_id": SECOND_INPUT_BOUNDARY_ID,
        "rendered_prompt_sha256": SECOND_RENDERED_PROMPT_SHA256,
        "full_prompt_sha256": SECOND_FULL_PROMPT_SHA256,
        "assistant_prefix_token_ids": list(BASE.PUBLIC_SCHEMA_PREFIX),
        "candidate_token_ids": dict(BASE.CANDIDATE_TOKEN_IDS),
        "expected_answer": SECOND_EXPECTED_ANSWER,
        "expected_token_id": SECOND_EXPECTED_TOKEN_ID,
        "fixed_before_model_output": True,
        "answer_conditioned_operator_selection": False,
    }
    manifest["second_unrelated_reuse_schedule"] = {
        "insertion":
                "after-smallest-prime-B-before-all-non-primary-controls",
        "added_model_callbacks": 5,
        "total_model_callbacks": EXPECTED_MODEL_CALLBACKS,
        "total_direct_protocol_actions": EXPECTED_DIRECT_PROTOCOL_ACTIONS,
        "final_successful_fiber_transactions": 6,
        "final_backing_reuses": 5,
        "successful_recovery_initializations": 0,
        "post_success_inverse_fault_recovery_sequence": [0, 1, 2],
        "post_success_recovery_initializations": 2,
        "expected_routes": [
            "same-backing-restored-primary",
            "identical-compact-classical",
            "cache-disabled-materialized",
        ],
    }
    manifest["second_unrelated_resource_preregistration"] = {
        "prompt_token_callbacks": 455,
        "fresh_prompt_tokens": 273,
        "cached_prompt_tokens": 182,
        "completion_tokens": 9,
        "captured_host_logit_buffers": 2,
        "captured_host_logit_bytes_cumulative":
                SECOND_ADDED_HOST_LOGIT_BYTES_CUMULATIVE,
        "structural_boundary_device_bytes": SECOND_STRUCTURAL_DEVICE_BYTES,
        "additional_persistent_phase_cells": 0,
    }
    manifest["combined_unrelated_resource_preregistration"] = {
        "useful_task_boundaries": 2,
        "expected_answers": ["B", "D"],
        "prompt_token_callbacks": 910,
        "fresh_prompt_tokens": 546,
        "cached_prompt_tokens": 364,
        "completion_tokens": 18,
        "captured_host_logit_buffers_sequential": 4,
        "captured_host_logit_bytes_cumulative": 3_973_120,
        "maximum_simultaneously_live_boundary_buffers": 1,
        "structural_boundary_device_bytes_cumulative": 3_727_360,
        "additional_persistent_phase_cells": 0,
    }
    return manifest


def validate_runtime_manifest() -> dict[str, Any]:
    receipt = _BASE_VALIDATE_RUNTIME_MANIFEST()
    manifest = json.loads(DEFAULT_RUNTIME_MANIFEST.read_text(encoding="utf-8"))
    expected_predecessor = (
        "neo-exp-0100"
        if EXPERIMENT_ID == "neo-exp-0101"
        else "neo-exp-0099"
    )
    expected_predecessor_result = (
        "F90FF5AA9E832AC036052B91EB811E12C02422E1903A44D1E9754D2EF3E62208"
        if EXPERIMENT_ID == "neo-exp-0101"
        else "7A53E171B79B6D726DBA9B6A1E78DB67F869B454C4C9BB9B975EE02C7992B6F9"
    )
    boundary = manifest.get("second_unrelated_boundary")
    schedule = manifest.get("second_unrelated_reuse_schedule")
    resources = manifest.get("second_unrelated_resource_preregistration")
    combined = manifest.get("combined_unrelated_resource_preregistration")
    require(
        manifest.get("predecessor_experiment") == expected_predecessor
        and manifest.get("predecessor_result_sha256")
                == expected_predecessor_result
        and boundary == {
            "relative_path":
                    "lab/neo-exp-0100-second-unrelated-boundary.json",
            "file_sha256": SECOND_BOUNDARY_FILE_SHA256,
            "token_count": 91,
            "token_sha256": SECOND_TOKEN_SHA256,
            "input_boundary_id": SECOND_INPUT_BOUNDARY_ID,
            "rendered_prompt_sha256": SECOND_RENDERED_PROMPT_SHA256,
            "full_prompt_sha256": SECOND_FULL_PROMPT_SHA256,
            "assistant_prefix_token_ids": list(BASE.PUBLIC_SCHEMA_PREFIX),
            "candidate_token_ids": dict(BASE.CANDIDATE_TOKEN_IDS),
            "expected_answer": "D",
            "expected_token_id": 35,
            "fixed_before_model_output": True,
            "answer_conditioned_operator_selection": False,
        }
        and schedule == {
            "insertion":
                    "after-smallest-prime-B-before-all-non-primary-controls",
            "added_model_callbacks": 5,
            "total_model_callbacks": 48,
            "total_direct_protocol_actions": 29,
            "final_successful_fiber_transactions": 6,
            "final_backing_reuses": 5,
            "successful_recovery_initializations": 0,
            "post_success_inverse_fault_recovery_sequence": [0, 1, 2],
            "post_success_recovery_initializations": 2,
            "expected_routes": [
                "same-backing-restored-primary",
                "identical-compact-classical",
                "cache-disabled-materialized",
            ],
        }
        and resources == {
            "prompt_token_callbacks": 455,
            "fresh_prompt_tokens": 273,
            "cached_prompt_tokens": 182,
            "completion_tokens": 9,
            "captured_host_logit_buffers": 2,
            "captured_host_logit_bytes_cumulative": 1_986_560,
            "structural_boundary_device_bytes": 1_863_680,
            "additional_persistent_phase_cells": 0,
        }
        and combined == {
            "useful_task_boundaries": 2,
            "expected_answers": ["B", "D"],
            "prompt_token_callbacks": 910,
            "fresh_prompt_tokens": 546,
            "cached_prompt_tokens": 364,
            "completion_tokens": 18,
            "captured_host_logit_buffers_sequential": 4,
            "captured_host_logit_bytes_cumulative": 3_973_120,
            "maximum_simultaneously_live_boundary_buffers": 1,
            "structural_boundary_device_bytes_cumulative": 3_727_360,
            "additional_persistent_phase_cells": 0,
        },
        "0100 second unrelated reuse runtime binding changed",
    )
    return {
        **receipt,
        "predecessor_experiment": expected_predecessor,
        "second_unrelated_boundary": dict(boundary),
        "second_unrelated_reuse_schedule": dict(schedule),
        "second_unrelated_resource_preregistration": dict(resources),
        "combined_unrelated_resource_preregistration": dict(combined),
    }


def main() -> int:
    parent.install_identity = install_identity
    parent.configure_parent = configure_parent
    parent.static_audit = static_audit
    parent.runtime_manifest_template = runtime_manifest_template
    parent.validate_runtime_manifest = validate_runtime_manifest
    parent.parent.run_post_primary_successor = run_post_primary_successor
    BASE.phase_log_evidence = phase_log_evidence
    return parent.main()


if __name__ == "__main__":
    raise SystemExit(main())
