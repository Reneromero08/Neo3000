#!/usr/bin/env python3
"""Exact bounded oracle for the neo-exp-0097 numerical quotient law.

This oracle uses only ``fractions.Fraction`` and public four-score fixtures.
It imports no production carrier code and performs no model, server, CUDA, or
endpoint contact.  The exact twin-rail phase identity remains independently
covered by ``catalytic_frontier_twin_rail_exact_oracle.py``.
"""

from __future__ import annotations

from fractions import Fraction
import json
from typing import Final, Sequence


EXPERIMENT_ID: Final = "neo-exp-0097"
PREREGISTRATION_ATTEMPT_ID: Final = "frontier-attempt-0144"
EXECUTION_ATTEMPT_ID: Final = "frontier-attempt-0145"
CANDIDATE_ORDER: Final = ("A", "B", "C", "D")
REORDERED_SCORE_SPREAD_TOLERANCE: Final = Fraction(6, 10**12)
PRIMARY_MINIMUM_TOP_TWO_MARGIN: Final = Fraction(2, 10**12)


def strict_lowest_index_argmax(values: Sequence[Fraction]) -> str:
    if len(values) != len(CANDIDATE_ORDER):
        raise ValueError("strict projection requires exactly four scores")
    return CANDIDATE_ORDER[max(range(len(values)), key=values.__getitem__)]


def canonical_reordered_projection(
    values: Sequence[Fraction],
) -> str | None:
    if len(values) != len(CANDIDATE_ORDER):
        raise ValueError("canonical projection requires exactly four scores")
    if max(values) - min(values) > REORDERED_SCORE_SPREAD_TOLERANCE:
        return None
    return CANDIDATE_ORDER[0]


def primary_margin_guard(values: Sequence[Fraction]) -> bool:
    if len(values) != len(CANDIDATE_ORDER):
        raise ValueError("primary margin requires exactly four probabilities")
    ordered = sorted(values, reverse=True)
    return ordered[0] - ordered[1] > PRIMARY_MINIMUM_TOP_TWO_MARGIN


def run_oracle() -> dict[str, object]:
    exact_tie = (Fraction(1),) * 4
    within = (
        Fraction(1),
        Fraction(1),
        Fraction(1),
        Fraction(1) + Fraction(3, 10**12),
    )
    outside = (
        Fraction(1),
        Fraction(1),
        Fraction(1),
        Fraction(1) + Fraction(7, 10**12),
    )
    wide_primary = (
        Fraction(1, 10),
        Fraction(2, 10),
        Fraction(3, 10),
        Fraction(4, 10),
    )
    equal_primary = (Fraction(1, 4),) * 4
    gates = {
        "exact_reordered_tie_projects_A": (
            canonical_reordered_projection(exact_tie) == "A"
        ),
        "within_tolerance_strict_argmax_differs": (
            strict_lowest_index_argmax(within) == "D"
            and canonical_reordered_projection(within) == "A"
        ),
        "over_tolerance_rejects": (
            canonical_reordered_projection(outside) is None
        ),
        "primary_wide_margin_passes": primary_margin_guard(wide_primary),
        "primary_equal_margin_rejects": (
            not primary_margin_guard(equal_primary)
        ),
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "preregistration_attempt_id": PREREGISTRATION_ATTEMPT_ID,
        "execution_attempt_id": EXECUTION_ATTEMPT_ID,
        "arithmetic": "fractions.Fraction",
        "candidate_order": list(CANDIDATE_ORDER),
        "reordered_score_spread_tolerance": "6/1000000000000",
        "primary_minimum_top_two_margin_exclusive": "2/1000000000000",
        "gates": gates,
        "passed": all(gates.values()),
        "contact": {
            "model_callbacks": 0,
            "server_contacts": 0,
            "cuda_kernel_launches": 0,
        },
    }


def main() -> int:
    result = run_oracle()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
