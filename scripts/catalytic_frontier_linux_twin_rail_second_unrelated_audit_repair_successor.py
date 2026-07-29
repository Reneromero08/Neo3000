#!/usr/bin/env python3
"""neo-exp-0101 controller-audit repair for the unchanged B/D successor.

The model-facing mechanism is inherited byte-for-byte from 0100.  This thin
successor binds two public controller audit corrections:

* capture summaries require their four declared counters fieldwise while
  preserving additional resource fields;
* shutdown expects one live-source poison iff the public shutdown-resident
  capture was scheduled, and otherwise expects zero.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import catalytic_frontier_linux_twin_rail_second_unrelated_successor as parent


EXPERIMENT_ID = "neo-exp-0101"
ATTEMPT_ID = "frontier-attempt-0153"
PREREGISTRATION_ATTEMPT_ID = "frontier-attempt-0152"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_MANIFEST = ROOT / "lab" / "neo-exp-0101-runtime-manifest.json"
DEFAULT_OUTPUT = ROOT / "lab" / "neo-exp-0101.local.json"
DEFAULT_LOCK = ROOT / "build" / "linux-catalytic" / "neo-exp-0101.active-lock.json"
DEFAULT_CONSUMED_MARKER = (
    ROOT / "build" / "linux-catalytic" / "neo-exp-0101.consumed-marker.json"
)
DEFAULT_RUN_PARENT = ROOT / "build" / "linux-catalytic"
BASE_ROOT_ID = "neo-exp-0101-base-684"

EXPECTED_MODEL_CALLBACKS = 48
EXPECTED_DIRECT_PROTOCOL_ACTIONS = 29
BASE = parent.BASE
RUNTIME_OWNER = parent.RUNTIME_OWNER

_BASE_INSTALL_IDENTITY = parent.install_identity
_BASE_RESTORE_IDENTITY = parent.restore_identity
_BASE_CONFIGURE_PARENT = parent.configure_parent
_BASE_STATIC_AUDIT = parent.static_audit
_BASE_RUNTIME_MANIFEST_TEMPLATE = parent.runtime_manifest_template
_BASE_VALIDATE_RUNTIME_MANIFEST = parent.validate_runtime_manifest
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
        / "test_catalytic_frontier_linux_twin_rail_second_unrelated_audit_repair_successor.py"
    )
    artifacts["second_unrelated_controller_base"] = (
        ROOT
        / "scripts"
        / "catalytic_frontier_linux_twin_rail_second_unrelated_successor.py"
    )
    RUNTIME_OWNER.SOURCE_ARTIFACT_NAMES.add(
        "second_unrelated_controller_base"
    )


def controller_audit_repair_source_gate() -> bool:
    source = (
        ROOT
        / "scripts"
        / "catalytic_frontier_linux_twin_rail_second_unrelated_successor.py"
    ).read_text(encoding="utf-8")
    base = (
        ROOT / "scripts" / "catalytic_frontier_linux_twin_rail_successor.py"
    ).read_text(encoding="utf-8")
    forbidden_exact = (
        'restored["capture"]["summary"]\n'
        '            == {'
    )
    return (
        forbidden_exact not in source
        and 'restored["capture"]["summary"]["prompt_tokens"] == 91'
                in source
        and 'compact["capture"]["summary"]["completion_tokens"] == 0'
                in source
        and "shutdown_resident_capture_scheduled = re.search(" in base
        and "expected_live_poisoned = int(" in base
        and 'receipt["poisoned_boundaries"] == expected_live_poisoned'
                in base
        and 'receipt["unresolved_boundaries"] == 0' in base
    )


def static_audit() -> dict[str, Any]:
    value = _BASE_STATIC_AUDIT()
    value["gates"]["fieldwise_capture_summary_contract"] = (
        controller_audit_repair_source_gate()
    )
    value["gates"]["shutdown_poison_matches_public_capture_lifecycle"] = (
        controller_audit_repair_source_gate()
    )
    require(
        all(value["gates"].values()),
        "0101 controller-audit repair static gate failed",
    )
    value["id"] = EXPERIMENT_ID
    value["attempt_id"] = ATTEMPT_ID
    value["preregistration_attempt_id"] = PREREGISTRATION_ATTEMPT_ID
    value["predecessor_experiment"] = "neo-exp-0100"
    return value


def runtime_manifest_template(runtime_source_commit: str) -> dict[str, Any]:
    manifest = _BASE_RUNTIME_MANIFEST_TEMPLATE(runtime_source_commit)
    manifest["causal_intervention"] = (
        "Change only controller audit normalization: validate the four "
        "required capture counters fieldwise while retaining extra resource "
        "fields, and require one shutdown poison iff the public shutdown-"
        "resident capture lifecycle event exists. Preserve every model-facing "
        "B/D request, carrier operation, control, and resource law."
    )
    manifest["predecessor_experiment"] = "neo-exp-0100"
    manifest["predecessor_result_sha256"] = (
        "F90FF5AA9E832AC036052B91EB811E12C02422E1903A44D1E9754D2EF3E62208"
    )
    manifest["controller_audit_repair"] = {
        "capture_required_fields": {
            "prompt_tokens": 91,
            "cached_prompt_tokens": 0,
            "fresh_prompt_tokens": 91,
            "completion_tokens": 0,
        },
        "capture_extra_accounting_fields_retained": [
            "fresh_model_tokens",
            "wall_seconds",
        ],
        "capture_dictionary_exact_equality": False,
        "shutdown_poison_expected_if_public_shutdown_capture_scheduled": 1,
        "shutdown_poison_expected_before_public_shutdown_capture": 0,
        "shutdown_unresolved_required": 0,
        "model_facing_requests_changed": 0,
        "model_callbacks_changed": 0,
        "direct_protocol_actions_changed": 0,
        "configured_cuda_units_changed": 0,
    }
    return manifest


def validate_runtime_manifest() -> dict[str, Any]:
    receipt = _BASE_VALIDATE_RUNTIME_MANIFEST()
    manifest = json.loads(DEFAULT_RUNTIME_MANIFEST.read_text(encoding="utf-8"))
    repair = manifest.get("controller_audit_repair")
    require(
        manifest.get("predecessor_experiment") == "neo-exp-0100"
        and manifest.get("predecessor_result_sha256")
                == "F90FF5AA9E832AC036052B91EB811E12C02422E1903A44D1E9754D2EF3E62208"
        and repair == {
            "capture_required_fields": {
                "prompt_tokens": 91,
                "cached_prompt_tokens": 0,
                "fresh_prompt_tokens": 91,
                "completion_tokens": 0,
            },
            "capture_extra_accounting_fields_retained": [
                "fresh_model_tokens",
                "wall_seconds",
            ],
            "capture_dictionary_exact_equality": False,
            "shutdown_poison_expected_if_public_shutdown_capture_scheduled": 1,
            "shutdown_poison_expected_before_public_shutdown_capture": 0,
            "shutdown_unresolved_required": 0,
            "model_facing_requests_changed": 0,
            "model_callbacks_changed": 0,
            "direct_protocol_actions_changed": 0,
            "configured_cuda_units_changed": 0,
        },
        "0101 controller-audit runtime binding changed",
    )
    return {
        **receipt,
        "predecessor_experiment": "neo-exp-0100",
        "controller_audit_repair": dict(repair),
    }


def main() -> int:
    parent.install_identity = install_identity
    parent.configure_parent = configure_parent
    parent.static_audit = static_audit
    parent.runtime_manifest_template = runtime_manifest_template
    parent.validate_runtime_manifest = validate_runtime_manifest
    return parent.main()


if __name__ == "__main__":
    raise SystemExit(main())
