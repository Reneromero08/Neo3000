#!/usr/bin/env python3
"""neo-exp-0099 cache-enabled independent live-consumer successor.

The consumed 0098 mechanism is inherited unchanged except for one controller
admission field.  Both independent captures and the materialized control stay
cache-disabled.  Only the restored-fiber and compact live consumers set
``cache_prompt=true``, as required by the existing resident-boundary preflight.
The field is not part of ``task_params::to_json(false)``, so the bound sampler
fingerprint remains identical.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import catalytic_frontier_linux_twin_rail_unrelated_reuse_successor as parent


EXPERIMENT_ID = "neo-exp-0099"
ATTEMPT_ID = "frontier-attempt-0149"
PREREGISTRATION_ATTEMPT_ID = "frontier-attempt-0148"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_MANIFEST = ROOT / "lab" / "neo-exp-0099-runtime-manifest.json"
DEFAULT_OUTPUT = ROOT / "lab" / "neo-exp-0099.local.json"
DEFAULT_LOCK = ROOT / "build" / "linux-catalytic" / "neo-exp-0099.active-lock.json"
DEFAULT_CONSUMED_MARKER = (
    ROOT / "build" / "linux-catalytic" / "neo-exp-0099.consumed-marker.json"
)
DEFAULT_RUN_PARENT = ROOT / "build" / "linux-catalytic"
BASE_ROOT_ID = "neo-exp-0099-base-684"

EXPECTED_MODEL_CALLBACKS = 43
EXPECTED_DIRECT_PROTOCOL_ACTIONS = 29
BASE = parent.BASE
RUNTIME_OWNER = parent.RUNTIME_OWNER

_BASE_INSTALL_IDENTITY = parent.install_identity
_BASE_RESTORE_IDENTITY = parent.restore_identity
_BASE_CONFIGURE_PARENT = parent.configure_parent
_BASE_STATIC_AUDIT = parent.static_audit
_BASE_RUNTIME_MANIFEST_TEMPLATE = parent.runtime_manifest_template
_BASE_VALIDATE_RUNTIME_MANIFEST = parent._BASE_VALIDATE_RUNTIME_MANIFEST
_BASE_RUN_UNRELATED_LIVE_ROUTE = parent.run_unrelated_live_route
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
        / "test_catalytic_frontier_linux_twin_rail_cache_enabled_consumer_successor.py"
    )
    artifacts["unrelated_reuse_controller_base"] = (
        ROOT
        / "scripts"
        / "catalytic_frontier_linux_twin_rail_unrelated_reuse_successor.py"
    )
    RUNTIME_OWNER.SOURCE_ARTIFACT_NAMES.add(
        "unrelated_reuse_controller_base"
    )


def cache_enabled_consumer_payload(
        payload: Mapping[str, Any],
        contract: Mapping[str, Any],
) -> dict[str, Any]:
    result = BASE.consumer_payload(payload, contract)
    result["cache_prompt"] = True
    require(
        payload.get("cache_prompt") is False
        and result.get("cache_prompt") is True,
        "0099 consumer-only cache admission field changed",
    )
    return result


def run_unrelated_live_route(
        *,
        sidecar: Any,
        codec: Any,
        props: Mapping[str, Any],
        trial: str,
        variant: int,
) -> dict[str, Any]:
    tokens, payload, ancestry = parent.fixed_unrelated_payload()
    contract = BASE.public_contract(
        trial=trial,
        edge=1,
        tokens=tokens,
        variant=variant,
    )
    capture = parent.capture_unrelated_boundary(
        sidecar=sidecar,
        payload=payload,
        contract=contract,
        label=f"{EXPERIMENT_ID}:{trial}:capture",
    )
    consumer_wire = cache_enabled_consumer_payload(payload, contract)
    consumer = BASE.harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:{trial}:consumer",
        consumer_wire,
        batch_owned_request=True,
    )
    require(
        consumer_wire["cache_prompt"] is True
        and consumer["prompt_tokens"] == parent.UNRELATED_TOKEN_COUNT
        and consumer["cached_prompt_tokens"] == parent.UNRELATED_TOKEN_COUNT
        and consumer["fresh_prompt_tokens"] == 0,
        "0099 cache-enabled unrelated live-consumer geometry changed",
    )
    boundary = BASE.validate_suffix_state(
        consumer,
        codec=codec,
        props=props,
        expected_answer=parent.UNRELATED_EXPECTED_ANSWER,
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


def consumer_admission_source_gate() -> bool:
    context = (
        ROOT / "tools" / "server" / "server-context.cpp"
    ).read_text(encoding="utf-8")
    task_source = (
        ROOT / "tools" / "server" / "server-task.cpp"
    ).read_text(encoding="utf-8")
    predecessor = (
        ROOT
        / "scripts"
        / "catalytic_frontier_linux_twin_rail_unrelated_reuse_successor.py"
    ).read_text(encoding="utf-8")
    source = Path(__file__).read_text(encoding="utf-8")
    to_json_start = task_source.index(
        "json task_params::to_json(bool only_metrics) const"
    )
    to_json_end = task_source.index(
        "task_result_state::task_result_state",
        to_json_start,
    )
    to_json_source = task_source[to_json_start:to_json_end]
    preflight_start = context.index(
        "server_slot * preflight_live_terminal_before_slot_selection("
    )
    preflight_end = context.index(
        "std::vector<common_adapter_lora_info> construct_lora_list",
        preflight_start,
    )
    preflight_source = context[preflight_start:preflight_end]
    return (
        "task.params.cache_prompt &&" in preflight_source
        and "neo3000_sampler_fnv1a64(task.params)" in preflight_source
        and "cache_prompt" not in to_json_source
        and 'result["cache_prompt"] = True' in source
        and 'payload.get("cache_prompt") is False' in source
        and 'payload["cache_prompt"] = False' in predecessor
        and "run_unrelated_materialized(" in predecessor
        and "run_unrelated_live_route(" in predecessor
    )


def static_audit() -> dict[str, Any]:
    value = _BASE_STATIC_AUDIT()
    value["gates"]["consumer_only_cache_enabled_admission"] = (
        consumer_admission_source_gate()
    )
    require(
        all(value["gates"].values()),
        "0099 consumer-only cache admission static gate failed",
    )
    value["id"] = EXPERIMENT_ID
    value["attempt_id"] = ATTEMPT_ID
    value["preregistration_attempt_id"] = PREREGISTRATION_ATTEMPT_ID
    value["predecessor_experiment"] = "neo-exp-0098"
    return value


def runtime_manifest_template(runtime_source_commit: str) -> dict[str, Any]:
    manifest = _BASE_RUNTIME_MANIFEST_TEMPLATE(runtime_source_commit)
    manifest["causal_intervention"] = (
        "Set cache_prompt=true only on the two independent resident live "
        "consumers. Keep their captures and the materialized control "
        "cache-disabled; change no server, CUDA, carrier, sampler, task, "
        "route, output, control, or resource law."
    )
    manifest["predecessor_experiment"] = "neo-exp-0098"
    manifest["predecessor_result_sha256"] = (
        "9889F39DF8A1EDB339B7A5A12DA27FFE813741ADE7259F7803E2E491D46BEFF3"
    )
    manifest["independent_consumer_admission_repair"] = {
        "restored_capture_cache_prompt": False,
        "restored_consumer_cache_prompt": True,
        "compact_capture_cache_prompt": False,
        "compact_consumer_cache_prompt": True,
        "materialized_cache_prompt": False,
        "cache_prompt_serialized_in_sampler_contract": False,
        "consumer_sampler_fingerprint_changed": False,
        "server_resident_live_preflight_requires_cache_prompt": True,
        "added_model_callbacks": 0,
        "added_direct_protocol_actions": 0,
        "configured_cuda_units_changed": 0,
    }
    return manifest


def validate_runtime_manifest() -> dict[str, Any]:
    receipt = _BASE_VALIDATE_RUNTIME_MANIFEST()
    manifest = json.loads(DEFAULT_RUNTIME_MANIFEST.read_text(encoding="utf-8"))
    repair = manifest.get("independent_consumer_admission_repair")
    boundary = manifest.get("unrelated_boundary")
    schedule = manifest.get("unrelated_reuse_schedule")
    resources = manifest.get("unrelated_resource_preregistration")
    require(
        manifest.get("predecessor_experiment") == "neo-exp-0098"
        and manifest.get("predecessor_result_sha256")
                == "9889F39DF8A1EDB339B7A5A12DA27FFE813741ADE7259F7803E2E491D46BEFF3"
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
            "file_sha256": parent.UNRELATED_BOUNDARY_FILE_SHA256,
            "token_count": parent.UNRELATED_TOKEN_COUNT,
            "token_sha256": parent.UNRELATED_TOKEN_SHA256,
            "input_boundary_id": parent.UNRELATED_INPUT_BOUNDARY_ID,
            "rendered_prompt_sha256":
                    parent.UNRELATED_RENDERED_PROMPT_SHA256,
            "full_prompt_sha256": parent.UNRELATED_FULL_PROMPT_SHA256,
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
                    parent.UNRELATED_ADDED_HOST_LOGIT_BYTES_CUMULATIVE,
            "structural_boundary_device_bytes":
                    parent.UNRELATED_STRUCTURAL_DEVICE_BYTES,
            "additional_persistent_phase_cells": 0,
        }
        and repair
        == {
            "restored_capture_cache_prompt": False,
            "restored_consumer_cache_prompt": True,
            "compact_capture_cache_prompt": False,
            "compact_consumer_cache_prompt": True,
            "materialized_cache_prompt": False,
            "cache_prompt_serialized_in_sampler_contract": False,
            "consumer_sampler_fingerprint_changed": False,
            "server_resident_live_preflight_requires_cache_prompt": True,
            "added_model_callbacks": 0,
            "added_direct_protocol_actions": 0,
            "configured_cuda_units_changed": 0,
        },
        "0099 consumer-only cache admission runtime binding changed",
    )
    return {
        **receipt,
        "predecessor_experiment": "neo-exp-0098",
        "unrelated_boundary": dict(boundary),
        "unrelated_reuse_schedule": dict(schedule),
        "unrelated_resource_preregistration": dict(resources),
        "independent_consumer_admission_repair": dict(repair),
    }


def main() -> int:
    parent.install_identity = install_identity
    parent.configure_parent = configure_parent
    parent.static_audit = static_audit
    parent.runtime_manifest_template = runtime_manifest_template
    parent.validate_runtime_manifest = validate_runtime_manifest
    parent.run_unrelated_live_route = run_unrelated_live_route
    return parent.main()


if __name__ == "__main__":
    raise SystemExit(main())
