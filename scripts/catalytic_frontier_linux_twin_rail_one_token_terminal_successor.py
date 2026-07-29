#!/usr/bin/env python3
"""neo-exp-0096 route-scoped one-token terminal-class successor.

The consumed 0095 mechanism and schedule are inherited unchanged.  The only
intervention gives the already public one-token sham routes an exact terminal
evidence class for their deliberately capped ``n_predict=1`` response.
Ordinary model generation remains EOS-only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import catalytic_frontier_linux_twin_rail_counter_reset_successor as parent


EXPERIMENT_ID = "neo-exp-0096"
ATTEMPT_ID = "frontier-attempt-0143"
PREREGISTRATION_ATTEMPT_ID = "frontier-attempt-0142"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_MANIFEST = ROOT / "lab" / "neo-exp-0096-runtime-manifest.json"
DEFAULT_OUTPUT = ROOT / "lab" / "neo-exp-0096.local.json"
DEFAULT_LOCK = ROOT / "build" / "linux-catalytic" / "neo-exp-0096.active-lock.json"
DEFAULT_CONSUMED_MARKER = (
    ROOT / "build" / "linux-catalytic" / "neo-exp-0096.consumed-marker.json"
)
DEFAULT_RUN_PARENT = ROOT / "build" / "linux-catalytic"
BASE_ROOT_ID = "neo-exp-0096-base-684"

_BASE_INSTALL_IDENTITY = parent.install_identity
_BASE_RESTORE_IDENTITY = parent.restore_identity
_BASE_CONFIGURE_PARENT = parent.configure_parent
_BASE_STATIC_AUDIT = parent.static_audit
_BASE_RUNTIME_MANIFEST_TEMPLATE = parent.runtime_manifest_template
_BASE_VALIDATE_RUNTIME_MANIFEST = parent._BASE_VALIDATE_RUNTIME_MANIFEST
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
_BASE_IDENTITY = {name: getattr(parent, name) for name in _IDENTITY_NAMES}


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
    for name, value in identity_overrides().items():
        setattr(parent, name, value)
        setattr(parent.parent, name, value)


def configure_parent() -> None:
    _BASE_CONFIGURE_PARENT()
    artifacts = parent.parent.parent.RUNTIME_ARTIFACT_PATHS
    artifacts["controller"] = Path(__file__).resolve()
    artifacts["controller_test"] = (
        ROOT
        / "scripts"
        / "test_catalytic_frontier_linux_twin_rail_one_token_terminal_successor.py"
    )
    artifacts["counter_reset_controller_base"] = (
        ROOT
        / "scripts"
        / "catalytic_frontier_linux_twin_rail_counter_reset_successor.py"
    )
    parent.parent.parent.SOURCE_ARTIFACT_NAMES.add(
        "counter_reset_controller_base"
    )


def restore_identity() -> None:
    for name, value in _BASE_IDENTITY.items():
        setattr(parent, name, value)
    _BASE_RESTORE_IDENTITY()


def one_token_terminal_source_gate() -> bool:
    harness = (ROOT / "scripts" / "catalytic_frontier_harness.py").read_text(
        encoding="utf-8"
    )
    controller = (
        ROOT / "scripts" / "catalytic_frontier_linux_twin_rail_successor.py"
    ).read_text(encoding="utf-8")
    return (
        "def validate_one_token_control_terminal(" in harness
        and 'operation_kind == "one-token-control-projection"' in harness
        and 'execution.get("finish_reason") == "limit"' in harness
        and 'execution.get("completion_tokens") == 1' in harness
        and 'execution.get("generated_token_count") == 1' in harness
        and 'execution.get("completion_token_count_match") is True' in harness
        and "generated_token_sha256" in harness
        and '"one-token-control-projection"' in controller
        and "if one_token" in controller
        and 'else "model-generation"' in controller
    )


def static_audit() -> dict[str, Any]:
    value = _BASE_STATIC_AUDIT()
    value["gates"]["route_scoped_one_token_terminal_class"] = (
        one_token_terminal_source_gate()
    )
    parent.parent.require(
        all(value["gates"].values()),
        "0096 route-scoped one-token terminal static gate failed",
    )
    value["id"] = EXPERIMENT_ID
    value["attempt_id"] = ATTEMPT_ID
    value["preregistration_attempt_id"] = PREREGISTRATION_ATTEMPT_ID
    value["predecessor_experiment"] = "neo-exp-0095"
    return value


def runtime_manifest_template(runtime_source_commit: str) -> dict[str, Any]:
    manifest = _BASE_RUNTIME_MANIFEST_TEMPLATE(runtime_source_commit)
    manifest["causal_intervention"] = (
        "Classify only the frozen n_predict=1 sham projections under the "
        "exact one-token-control-projection limit terminal law; ordinary "
        "model generation remains EOS-only."
    )
    manifest["predecessor_experiment"] = "neo-exp-0095"
    manifest["predecessor_result_sha256"] = (
        "511641809FD4840A94E6A3D57BF170002B26CF6EF9B2CF84717C77148CF126DD"
    )
    manifest["one_token_control_projection_terminal_class"] = {
        "finish_reason": "limit",
        "generated_tokens": 1,
        "generic_model_generation_eos_only": True,
        "route_scope": ["dephased", "reordered-forward"],
    }
    return manifest


def validate_runtime_manifest() -> dict[str, Any]:
    receipt = _BASE_VALIDATE_RUNTIME_MANIFEST()
    manifest = json.loads(DEFAULT_RUNTIME_MANIFEST.read_text(encoding="utf-8"))
    terminal_class = manifest.get(
        "one_token_control_projection_terminal_class"
    )
    parent.parent.require(
        manifest.get("predecessor_experiment") == "neo-exp-0095"
        and manifest.get("predecessor_result_sha256")
        == "511641809FD4840A94E6A3D57BF170002B26CF6EF9B2CF84717C77148CF126DD"
        and manifest.get("capture_progress_counter_reset_before_first_progress")
        is True
        and terminal_class
        == {
            "finish_reason": "limit",
            "generated_tokens": 1,
            "generic_model_generation_eos_only": True,
            "route_scope": ["dephased", "reordered-forward"],
        },
        "0096 one-token terminal runtime manifest binding changed",
    )
    return {
        **receipt,
        "capture_progress_counter_reset_before_first_progress": True,
        "one_token_control_projection_terminal_class": dict(terminal_class),
        "predecessor_experiment": "neo-exp-0095",
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
