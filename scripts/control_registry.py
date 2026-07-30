"""Declarative control definitions for the repaired catalytic runner."""
from __future__ import annotations

from types import MappingProxyType


CONTROL_REGISTRY = MappingProxyType(
    {
        "compact_classical_recurrence": {
            "classification": "STRONGEST_COMPACT_BASELINE",
            "proof_required": "BEHAVIORAL_PARITY",
            "meaning": (
                "Identical compact softmax/product recurrence; parity is "
                "calibration and never a phase-resource claim."
            ),
        },
        "forced_equal_score_sham": {
            "classification": "RETIRED_HISTORICAL_SHAM",
            "proof_required": "HISTORICAL_INTERPRETATION_ONLY",
            "meaning": (
                "Historical direct assignment of equal scores. It is not "
                "dephasing and cannot satisfy a coherence-control gate."
            ),
        },
        "numerical_decoherence": {
            "classification": "STATE_LEVEL_DECOHERENCE_CONTROL",
            "proof_required": "BEHAVIORAL_STATE_TRANSFORM",
            "meaning": (
                "Zero off-diagonal density terms, then use the same "
                "measurement function as the primary route."
            ),
        },
        "fresh_calibration_backing": {
            "classification": "FRESH_WORKSPACE_CONTROL",
            "proof_required": "BEHAVIORAL_PARITY",
            "meaning": "Fresh eight-cell numerical calibration object.",
        },
        "fully_materialized_inference": {
            "classification": "MODEL_FACING_MATERIALIZED_BASELINE",
            "proof_required": "MODEL_RUNTIME",
            "meaning": "Cache-disabled full inference route.",
        },
        "null_calibration_state": {
            "classification": "PRE_BORROW_REJECTION",
            "proof_required": "BEHAVIORAL_FAULT_INJECTION",
            "meaning": "Reject before numerical state borrow.",
        },
        "wrong_structural_contract": {
            "classification": "STRUCTURAL_CONTRACT_REJECTION",
            "proof_required": "BEHAVIORAL_FAULT_INJECTION",
            "meaning": (
                "Reject wrong public principal, lease, generation, type, "
                "module, ordinal, boundary, projection, or restoration field."
            ),
        },
        "missing_inverse": {
            "classification": "RESTORATION_FAULT",
            "proof_required": "BEHAVIORAL_FAULT_INJECTION",
            "meaning": "Missing inverse must fail restoration and projection.",
        },
        "wrong_inverse": {
            "classification": "RESTORATION_FAULT",
            "proof_required": "BEHAVIORAL_FAULT_INJECTION",
            "meaning": "Wrong inverse must fail restoration and projection.",
        },
        "reordered_inverse": {
            "classification": "RESTORATION_FAULT",
            "proof_required": "BEHAVIORAL_FAULT_INJECTION",
            "meaning": "Reordered inverse must fail restoration and projection.",
        },
        "premature_projection": {
            "classification": "CUSTODY_FAULT",
            "proof_required": "BEHAVIORAL_FAULT_INJECTION",
            "meaning": "Projection before restoration must poison or reject.",
        },
        "resident_cancellation": {
            "classification": "LIFECYCLE_FAULT",
            "proof_required": "BEHAVIORAL_STATE_TRANSITION",
            "meaning": "Cancellation closes or poisons resident state.",
        },
        "resident_sleep": {
            "classification": "LIFECYCLE_FAULT",
            "proof_required": "BEHAVIORAL_STATE_TRANSITION",
            "meaning": "Sleep poisons custody before model/context destruction.",
        },
        "resident_shutdown": {
            "classification": "LIFECYCLE_FAULT",
            "proof_required": "BEHAVIORAL_STATE_TRANSITION",
            "meaning": "Shutdown leaves no resident live/calibration state.",
        },
        "carrier_mutation_ablation": {
            "classification": "CARRIER_CAUSALITY_ABLATION",
            "proof_required": "MATCHED_MODEL_RUNTIME",
            "meaning": (
                "A true carrier mutation must change a useful downstream "
                "inference boundary before any inference-bearing claim."
            ),
        },
        "evidence_f_only": {
            "classification": "NECESSITY_ABLATION",
            "proof_required": "MATCHED_MODEL_RUNTIME",
            "meaning": "F alone is insufficient or yields a different boundary.",
        },
        "evidence_g_only": {
            "classification": "NECESSITY_ABLATION",
            "proof_required": "MATCHED_MODEL_RUNTIME",
            "meaning": "G alone is insufficient or yields a different boundary.",
        },
    }
)


LEGACY_INTERPRETATION_ALIASES = MappingProxyType(
    {
        "owner-bound": "structurally contract-bound",
        "dephased": "forced-equal-score sham",
        "phase-relational inference": (
            "reversible scalar-score encoding calibration"
        ),
    }
)
