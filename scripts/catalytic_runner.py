#!/usr/bin/env python3
"""Static declarative runner for calibration and future frontier specifications.

This foundation runner intentionally has no model-execution subcommand. A later
user-authorized catalytic goal may add an execution adapter only after the
carrier-causality and necessity gates in AGENTS.md are represented.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from control_registry import CONTROL_REGISTRY
from result_schema import (
    SpecValidationError,
    require,
    validate_restoration_scope,
    validate_schedule,
)


ROOT = Path(__file__).resolve().parents[1]
SPEC_ROOT = ROOT / "scripts" / "experiment_specs"
LEGACY_CONTROLLER_PREFIXES = (
    "catalytic_frontier_linux_twin_rail_successor",
    "catalytic_frontier_linux_twin_rail_counter_reset_successor",
    "catalytic_frontier_linux_twin_rail_one_token_terminal_successor",
    "catalytic_frontier_linux_twin_rail_numerical_quotient_successor",
    "catalytic_frontier_linux_twin_rail_unrelated_reuse_successor",
    "catalytic_frontier_linux_twin_rail_cache_enabled_consumer_successor",
    "catalytic_frontier_linux_twin_rail_second_unrelated_successor",
    "catalytic_frontier_linux_twin_rail_second_unrelated_audit_repair_successor",
)


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def load_spec(path: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    require(
        resolved.parent == SPEC_ROOT.resolve(strict=True),
        "spec must be an immutable file in scripts/experiment_specs",
    )
    value = json.loads(resolved.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "spec root must be an object")
    return value


def validate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version",
        "identity",
        "scientific_status",
        "classification",
        "model_contact_allowed",
        "prompt_boundaries",
        "route_graph",
        "expected_model_callbacks",
        "callback_schedule",
        "expected_direct_actions",
        "direct_action_schedule",
        "controls",
        "restoration_scope",
        "resource_gates",
        "acceptance_laws",
        "claim_ceiling",
        "legacy_controller_status",
    }
    require(set(spec) == required, "spec fields differ from the immutable schema")
    require(spec["schema_version"] == 1, "unsupported spec schema")
    require(
        spec["scientific_status"] in {"CONSUMED_HISTORICAL", "PRECONTACT_FROZEN"},
        "scientific status is invalid",
    )
    require(
        spec["model_contact_allowed"] is False,
        "realignment specs must forbid model contact",
    )
    require(
        isinstance(spec["prompt_boundaries"], list)
        and spec["prompt_boundaries"],
        "prompt boundaries are required",
    )
    require(
        isinstance(spec["route_graph"], list) and spec["route_graph"],
        "route graph is required",
    )
    validate_schedule(
        spec["callback_schedule"],
        spec["expected_model_callbacks"],
        "callback_schedule",
    )
    validate_schedule(
        spec["direct_action_schedule"],
        spec["expected_direct_actions"],
        "direct_action_schedule",
    )
    require(
        isinstance(spec["controls"], list) and spec["controls"],
        "controls are required",
    )
    unknown_controls = set(spec["controls"]) - set(CONTROL_REGISTRY)
    require(
        not unknown_controls,
        f"unknown controls: {sorted(unknown_controls)}",
    )
    validate_restoration_scope(spec["restoration_scope"])
    require(
        isinstance(spec["resource_gates"], dict) and spec["resource_gates"],
        "resource gates are required",
    )
    require(
        isinstance(spec["acceptance_laws"], list)
        and spec["acceptance_laws"],
        "acceptance laws are required",
    )
    require(
        isinstance(spec["claim_ceiling"], str) and spec["claim_ceiling"],
        "claim ceiling is required",
    )
    require(
        spec["legacy_controller_status"] == "RETIRED_NOT_IMPORTED",
        "legacy controller status must be retired",
    )
    return {
        "valid": True,
        "identity": spec["identity"],
        "classification": spec["classification"],
        "scientific_status": spec["scientific_status"],
        "model_contact_allowed": False,
        "spec_sha256": canonical_sha256(spec),
        "callback_count": spec["expected_model_callbacks"],
        "direct_action_count": spec["expected_direct_actions"],
        "control_count": len(spec["controls"]),
        "legacy_controllers_imported": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("validate", "describe"))
    parser.add_argument("spec", type=Path)
    args = parser.parse_args()
    try:
        spec = load_spec(args.spec)
        receipt = validate_spec(spec)
    except (OSError, json.JSONDecodeError, SpecValidationError) as exc:
        raise SystemExit(str(exc)) from exc
    if args.command == "describe":
        receipt["route_graph"] = spec["route_graph"]
        receipt["restoration_scope"] = spec["restoration_scope"]
        receipt["claim_ceiling"] = spec["claim_ceiling"]
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
