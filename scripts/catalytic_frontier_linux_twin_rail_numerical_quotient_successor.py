#!/usr/bin/env python3
"""neo-exp-0097 route-scoped canonical numerical quotient successor.

The consumed 0096 mechanism and schedule are inherited unchanged.  The sole
mechanism intervention makes the numerical projection boundary explicit:
primary inference remains strict and margin-guarded, while only the public
reordered-forward exact tie may use the fixed lowest-index quotient.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import catalytic_frontier_linux_twin_rail_one_token_terminal_successor as parent
import catalytic_frontier_twin_rail_numerical_quotient_oracle as quotient_oracle


EXPERIMENT_ID = "neo-exp-0097"
ATTEMPT_ID = "frontier-attempt-0145"
PREREGISTRATION_ATTEMPT_ID = "frontier-attempt-0144"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_MANIFEST = ROOT / "lab" / "neo-exp-0097-runtime-manifest.json"
DEFAULT_OUTPUT = ROOT / "lab" / "neo-exp-0097.local.json"
DEFAULT_LOCK = ROOT / "build" / "linux-catalytic" / "neo-exp-0097.active-lock.json"
DEFAULT_CONSUMED_MARKER = (
    ROOT / "build" / "linux-catalytic" / "neo-exp-0097.consumed-marker.json"
)
DEFAULT_RUN_PARENT = ROOT / "build" / "linux-catalytic"
BASE_ROOT_ID = "neo-exp-0097-base-684"

REORDERED_SCORE_SPREAD_TOLERANCE = 6.0e-12
PRIMARY_MINIMUM_TOP_TWO_MARGIN = 2.0e-12
REORDERED_PROJECTION_RESTORATION_CLASS = (
    "INVERSE_PLUS_CANONICAL_NUMERICAL_QUOTIENT"
)

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
        setattr(parent.parent.parent, name, value)


def configure_parent() -> None:
    _BASE_CONFIGURE_PARENT()
    runtime_owner = parent.parent.parent.parent
    artifacts = runtime_owner.RUNTIME_ARTIFACT_PATHS
    artifacts["controller"] = Path(__file__).resolve()
    artifacts["controller_test"] = (
        ROOT
        / "scripts"
        / "test_catalytic_frontier_linux_twin_rail_numerical_quotient_successor.py"
    )
    artifacts["one_token_terminal_controller_base"] = (
        ROOT
        / "scripts"
        / "catalytic_frontier_linux_twin_rail_one_token_terminal_successor.py"
    )
    artifacts["numerical_quotient_oracle"] = (
        ROOT
        / "scripts"
        / "catalytic_frontier_twin_rail_numerical_quotient_oracle.py"
    )
    artifacts["numerical_quotient_oracle_test"] = (
        ROOT
        / "scripts"
        / "test_catalytic_frontier_twin_rail_numerical_quotient_oracle.py"
    )
    runtime_owner.SOURCE_ARTIFACT_NAMES.update(
        {
            "one_token_terminal_controller_base",
            "numerical_quotient_oracle",
            "numerical_quotient_oracle_test",
        }
    )


def restore_identity() -> None:
    for name, value in _BASE_IDENTITY.items():
        setattr(parent, name, value)
    _BASE_RESTORE_IDENTITY()


def numerical_quotient_source_gate() -> bool:
    fiber = (
        ROOT / "tools" / "server" / "neo3000-twin-rail-fiber.cpp"
    ).read_text(encoding="utf-8")
    header = (
        ROOT / "tools" / "server" / "neo3000-twin-rail-fiber.h"
    ).read_text(encoding="utf-8")
    context = (
        ROOT / "tools" / "server" / "server-context.cpp"
    ).read_text(encoding="utf-8")
    selftest = (
        ROOT / "scripts" / "catalytic_frontier_twin_rail_runtime_selftest.cpp"
    ).read_text(encoding="utf-8")
    return (
        "reordered_score_spread_tolerance = 6.0e-12" in header
        and "primary_minimum_top_two_margin = 2.0e-12" in header
        and "canonical_reordered_score_projection(" in fiber
        and "variant == twin_rail_variant::REORDERED_FORWARD" in fiber
        and "reordered-forward scores exceeded the canonical numerical quotient"
        in fiber
        and "primary twin-rail probability margin is not strictly separated"
        in fiber
        and fiber.index(
            "primary twin-rail probability margin is not strictly separated"
        )
        < fiber.index("bind_ownership(contract);")
        and fiber.index("state_ = twin_rail_state::RESTORING;")
        < fiber.index("receipt.restored = true;")
        < fiber.index(
            "reordered-forward scores exceeded the canonical numerical quotient"
        )
        and "canonical_tie_quotient=%s" in context
        and "primary_margin_guard=%s" in context
        and "score_spread=" not in context
        and "warmed-reordered" in selftest
        and (
            (
                "reordered.completed_transactions == 4" in selftest
                and "reordered.backing_reuses == 3" in selftest
            )
            or (
                "reordered.completed_transactions == 5" in selftest
                and "reordered.backing_reuses == 4" in selftest
                and "warmed-unrelated-smallest-prime" in selftest
            )
            or (
                "reordered.completed_transactions == 6" in selftest
                and "reordered.backing_reuses == 5" in selftest
                and "warmed-unrelated-smallest-prime" in selftest
                and "warmed-unrelated-largest-even" in selftest
            )
        )
        and "outside_quotient" in selftest
        and "primary-margin-reject" in selftest
        and "transform_and_restore_with_test_scores" in selftest
        and "reordered-post-transform-reject" in selftest
        and "primary-post-transform-reject" in selftest
        and "rejected.restored" in selftest
        and "carrier.state() == twin_rail_state::INVALID" in selftest
        and "NEO3000_TWIN_RAIL_TESTING" in selftest
    )


def static_audit() -> dict[str, Any]:
    value = _BASE_STATIC_AUDIT()
    value["gates"]["route_scoped_canonical_numerical_quotient"] = (
        numerical_quotient_source_gate()
    )
    value["gates"]["numerical_quotient_exact_oracle"] = (
        quotient_oracle.run_oracle()["passed"]
    )
    parent.parent.parent.require(
        all(value["gates"].values()),
        "0097 canonical numerical quotient static gate failed",
    )
    value["id"] = EXPERIMENT_ID
    value["attempt_id"] = ATTEMPT_ID
    value["preregistration_attempt_id"] = PREREGISTRATION_ATTEMPT_ID
    value["predecessor_experiment"] = "neo-exp-0096"
    value["numerical_quotient_oracle"] = quotient_oracle.run_oracle()
    return value


def runtime_manifest_template(runtime_source_commit: str) -> dict[str, Any]:
    manifest = _BASE_RUNTIME_MANIFEST_TEMPLATE(runtime_source_commit)
    manifest["causal_intervention"] = (
        "Apply the fixed 6e-12 lowest-index numerical quotient only to "
        "REORDERED_FORWARD, keep primary/compact projection strict, and "
        "require the primary public top-two margin to exceed 2e-12."
    )
    manifest["predecessor_experiment"] = "neo-exp-0096"
    manifest["predecessor_result_sha256"] = (
        "AB735216E5A6F0B33D1772710ACBC53F224D6A491267FF17B5F1363A442FE2C0"
    )
    manifest["reordered_canonical_numerical_quotient"] = {
        "route_variant": 2,
        "score_spread_tolerance_inclusive": REORDERED_SCORE_SPREAD_TOLERANCE,
        "score_spread_bound": (
            "4*sqrt(2)*1e-12+4*(1e-12)^2 rounded upward"
        ),
        "representative": {"answer": "A", "token_id": 32, "public_index": 0},
        "restoration_class": REORDERED_PROJECTION_RESTORATION_CLASS,
        "raw_scores_logged_or_returned": False,
    }
    manifest["primary_nondegenerate_margin_guard"] = {
        "top_two_margin_exclusive": PRIMARY_MINIMUM_TOP_TWO_MARGIN,
        "maximum_score_error_inclusive": 1.0e-12,
        "strict_argmax": True,
        "classical_parity_required": True,
        "pre_borrow_margin_rejection": True,
    }
    manifest["quotient_receipt_fields"] = [
        "canonical_tie_quotient_applied",
        "primary_margin_guard_passed",
    ]
    manifest["numerical_quotient_oracle"] = quotient_oracle.run_oracle()
    return manifest


def validate_runtime_manifest() -> dict[str, Any]:
    receipt = _BASE_VALIDATE_RUNTIME_MANIFEST()
    manifest = json.loads(DEFAULT_RUNTIME_MANIFEST.read_text(encoding="utf-8"))
    terminal_class = manifest.get(
        "one_token_control_projection_terminal_class"
    )
    quotient = manifest.get("reordered_canonical_numerical_quotient")
    primary_guard = manifest.get("primary_nondegenerate_margin_guard")
    parent.parent.parent.require(
        manifest.get("predecessor_experiment") == "neo-exp-0096"
        and manifest.get("predecessor_result_sha256")
        == "AB735216E5A6F0B33D1772710ACBC53F224D6A491267FF17B5F1363A442FE2C0"
        and manifest.get("capture_progress_counter_reset_before_first_progress")
        is True
        and terminal_class
        == {
            "finish_reason": "limit",
            "generated_tokens": 1,
            "generic_model_generation_eos_only": True,
            "route_scope": ["dephased", "reordered-forward"],
        }
        and quotient
        == {
            "route_variant": 2,
            "score_spread_tolerance_inclusive": 6.0e-12,
            "score_spread_bound": (
                "4*sqrt(2)*1e-12+4*(1e-12)^2 rounded upward"
            ),
            "representative": {
                "answer": "A",
                "token_id": 32,
                "public_index": 0,
            },
            "restoration_class":
                "INVERSE_PLUS_CANONICAL_NUMERICAL_QUOTIENT",
            "raw_scores_logged_or_returned": False,
        }
        and primary_guard
        == {
            "top_two_margin_exclusive": 2.0e-12,
            "maximum_score_error_inclusive": 1.0e-12,
            "strict_argmax": True,
            "classical_parity_required": True,
            "pre_borrow_margin_rejection": True,
        }
        and manifest.get("quotient_receipt_fields")
        == [
            "canonical_tie_quotient_applied",
            "primary_margin_guard_passed",
        ]
        and manifest.get("numerical_quotient_oracle", {}).get("passed")
        is True,
        "0097 canonical numerical quotient runtime binding changed",
    )
    return {
        **receipt,
        "capture_progress_counter_reset_before_first_progress": True,
        "one_token_control_projection_terminal_class": dict(terminal_class),
        "reordered_canonical_numerical_quotient": dict(quotient),
        "primary_nondegenerate_margin_guard": dict(primary_guard),
        "numerical_quotient_oracle_passed": True,
        "predecessor_experiment": "neo-exp-0096",
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
