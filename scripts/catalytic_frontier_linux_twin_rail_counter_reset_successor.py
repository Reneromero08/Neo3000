#!/usr/bin/env python3
"""neo-exp-0095 request-local capture-progress counter successor.

The consumed 0094 mechanism and full schedule are inherited unchanged.  The
only runtime intervention clears the request-local decoded-token count before
the first current-request prompt-progress response, so a zero-output capture
cannot expose the preceding request's completion count.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import catalytic_frontier_linux_twin_rail_successor as parent


EXPERIMENT_ID = "neo-exp-0095"
ATTEMPT_ID = "frontier-attempt-0141"
PREREGISTRATION_ATTEMPT_ID = "frontier-attempt-0140"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_MANIFEST = ROOT / "lab" / "neo-exp-0095-runtime-manifest.json"
DEFAULT_OUTPUT = ROOT / "lab" / "neo-exp-0095.local.json"
DEFAULT_LOCK = ROOT / "build" / "linux-catalytic" / "neo-exp-0095.active-lock.json"
DEFAULT_CONSUMED_MARKER = (
    ROOT / "build" / "linux-catalytic" / "neo-exp-0095.consumed-marker.json"
)
DEFAULT_RUN_PARENT = ROOT / "build" / "linux-catalytic"
BASE_ROOT_ID = "neo-exp-0095-base-684"

_BASE_STATIC_AUDIT = parent.static_audit
_BASE_CONFIGURE_PARENT = parent.configure_parent
_BASE_RUNTIME_MANIFEST_TEMPLATE = parent.runtime_manifest_template
_BASE_VALIDATE_RUNTIME_MANIFEST = parent.validate_runtime_manifest
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


def install_identity() -> None:
    overrides = {
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
    for name, value in overrides.items():
        setattr(parent, name, value)


def configure_parent() -> None:
    _BASE_CONFIGURE_PARENT()
    artifacts = parent.parent.RUNTIME_ARTIFACT_PATHS
    artifacts["controller"] = Path(__file__).resolve()
    artifacts["controller_test"] = (
        ROOT
        / "scripts"
        / "test_catalytic_frontier_linux_twin_rail_counter_reset_successor.py"
    )
    artifacts["twin_rail_controller_base"] = (
        ROOT / "scripts" / "catalytic_frontier_linux_twin_rail_successor.py"
    )
    artifacts["request_lifecycle_header"] = (
        ROOT / "tools" / "server" / "neo3000-request-lifecycle.h"
    )
    artifacts["request_lifecycle_selftest"] = (
        ROOT / "scripts" / "catalytic_frontier_request_lifecycle_selftest.cpp"
    )
    artifacts["request_lifecycle_selftest_binary"] = (
        ROOT
        / "build"
        / "linux-catalytic"
        / "neo-exp-0095-static"
        / "request-lifecycle-selftest"
    )
    parent.parent.SOURCE_ARTIFACT_NAMES.update(
        {
            "twin_rail_controller_base",
            "request_lifecycle_header",
            "request_lifecycle_selftest",
        }
    )


def restore_identity() -> None:
    for name, value in _BASE_IDENTITY.items():
        setattr(parent, name, value)


def counter_reset_source_gate() -> bool:
    source = (ROOT / "tools" / "server" / "server-context.cpp").read_text(
        encoding="utf-8"
    )
    header = (
        ROOT / "tools" / "server" / "neo3000-request-lifecycle.h"
    ).read_text(encoding="utf-8")
    start = source.index("slot.n_prompt_tokens_cache = n_past;")
    processed = source.index(
        "slot.n_prompt_tokens_processed = 0;",
        start,
    )
    reset = source.index(
        "neo3000::begin_current_request_progress(slot.n_decoded);",
        processed,
    )
    first_progress = source.index(
        "send_partial_response(slot, {}, true);",
        reset,
    )
    later_prompt_reset = source.index(
        "slot.n_decoded = 0;",
        first_progress,
    )
    return (
        start < processed < reset < first_progress < later_prompt_reset
        and "inline void begin_current_request_progress" in header
        and "n_decoded = 0;" in header
    )


def static_audit() -> dict[str, Any]:
    value = _BASE_STATIC_AUDIT()
    value["gates"]["capture_progress_current_request_counter_reset"] = (
        counter_reset_source_gate()
    )
    parent.require(
        all(value["gates"].values()),
        "0095 capture-progress counter reset static gate failed",
    )
    value["id"] = EXPERIMENT_ID
    value["attempt_id"] = ATTEMPT_ID
    value["preregistration_attempt_id"] = PREREGISTRATION_ATTEMPT_ID
    value["predecessor_experiment"] = "neo-exp-0094"
    return value


def runtime_manifest_template(runtime_source_commit: str) -> dict[str, Any]:
    manifest = _BASE_RUNTIME_MANIFEST_TEMPLATE(runtime_source_commit)
    manifest["causal_intervention"] = (
        "Clear server_slot.n_decoded at new-prompt initialization before "
        "the first current prompt-progress response; inherit the complete "
        "0094 twin-rail mechanism and schedule unchanged."
    )
    manifest["predecessor_experiment"] = "neo-exp-0094"
    manifest["predecessor_result_sha256"] = (
        "A7A5B20C283B3DDD5E1EF023996350934A53A5FBBB940BC40F7FBF56997ADCCA"
    )
    manifest["capture_progress_counter_reset_before_first_progress"] = True
    return manifest


def validate_runtime_manifest() -> dict[str, Any]:
    receipt = _BASE_VALIDATE_RUNTIME_MANIFEST()
    manifest = json.loads(DEFAULT_RUNTIME_MANIFEST.read_text(encoding="utf-8"))
    parent.require(
        manifest.get("predecessor_experiment") == "neo-exp-0094"
        and manifest.get("predecessor_result_sha256")
        == "A7A5B20C283B3DDD5E1EF023996350934A53A5FBBB940BC40F7FBF56997ADCCA"
        and manifest.get("capture_progress_counter_reset_before_first_progress")
        is True,
        "0095 counter-reset runtime manifest binding changed",
    )
    return {
        **receipt,
        "capture_progress_counter_reset_before_first_progress": True,
        "predecessor_experiment": "neo-exp-0094",
    }


def main() -> int:
    install_identity()
    parent.configure_parent = configure_parent
    parent.static_audit = static_audit
    parent.runtime_manifest_template = runtime_manifest_template
    parent.validate_runtime_manifest = validate_runtime_manifest
    return parent.main()


if __name__ == "__main__":
    raise SystemExit(main())
