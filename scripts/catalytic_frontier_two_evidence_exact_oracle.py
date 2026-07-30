#!/usr/bin/env python3
"""Exact bounded calibration oracle for the precontact two-row fixture.

The production calibration backend uses fixed-width complex doubles. This
oracle uses fractions.Fraction for every probability, product, score, operator,
and inverse check. Its first four-lane fixture supplies the exact p and q used
by the one-lane SO(3) operator proof; the integrated products are never supplied
as a detached tuple.
"""
from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction
import json
from typing import Iterable


Vector = tuple[Fraction, Fraction, Fraction]
Matrix = tuple[Vector, Vector, Vector]
ProbabilityVector = tuple[Fraction, Fraction, Fraction, Fraction]


def matrix_vector(matrix: Matrix, vector: Vector) -> Vector:
    return tuple(
        sum((row[index] * vector[index] for index in range(3)), Fraction())
        for row in matrix
    )  # type: ignore[return-value]


def ry(cosine: Fraction, sine: Fraction) -> Matrix:
    return (
        (cosine, Fraction(), sine),
        (Fraction(), Fraction(1), Fraction()),
        (-sine, Fraction(), cosine),
    )


def rx(cosine: Fraction, sine: Fraction) -> Matrix:
    return (
        (Fraction(1), Fraction(), Fraction()),
        (Fraction(), cosine, -sine),
        (Fraction(), sine, cosine),
    )


def transpose(matrix: Matrix) -> Matrix:
    return tuple(zip(*matrix))  # type: ignore[return-value]


def strict_argmax(values: Iterable[Fraction]) -> int:
    sequence = tuple(values)
    best = 0
    for index in range(1, len(sequence)):
        if sequence[index] > sequence[best]:
            best = index
    return best


def validate_probability_vector(values: ProbabilityVector) -> bool:
    return all(value >= 0 for value in values) and sum(values) == 1


def products(
    first: ProbabilityVector,
    second: ProbabilityVector,
) -> tuple[Fraction, Fraction, Fraction, Fraction]:
    return tuple(
        first[index] * second[index] for index in range(4)
    )  # type: ignore[return-value]


def phase_scores(
    compact_products: tuple[Fraction, Fraction, Fraction, Fraction],
) -> tuple[Fraction, Fraction, Fraction, Fraction]:
    return tuple(
        (Fraction(1) + value) / 2 for value in compact_products
    )  # type: ignore[return-value]


def normalized_factor_condition(
    compact_products: Iterable[Fraction],
) -> Decimal:
    with localcontext() as context:
        context.prec = 80
        return sum(
            (
                (
                    Decimal(value.numerator)
                    / Decimal(value.denominator)
                ).sqrt()
                for value in compact_products
            ),
            Decimal(),
        )


def dephase_z(vector: Vector) -> Vector:
    # Complete state-level decoherence in the computational basis removes both
    # off-diagonal Bloch components. Measurement still uses the same y
    # observable below.
    return (Fraction(), Fraction(), vector[2])


def negative_y_score(vector: Vector) -> Fraction:
    return (Fraction(1) - vector[1]) / 2


FIXTURES: tuple[
    tuple[str, ProbabilityVector, ProbabilityVector],
    ...,
] = (
    (
        "operator-linked-order-sensitive",
        (Fraction(3, 5), Fraction(1, 5), Fraction(1, 10), Fraction(1, 10)),
        (Fraction(5, 13), Fraction(1, 13), Fraction(1, 13), Fraction(6, 13)),
    ),
    (
        "near-tie",
        (Fraction(1, 4),) * 4,
        (
            Fraction(1, 4),
            Fraction(1, 4),
            Fraction(2501, 10000),
            Fraction(2499, 10000),
        ),
    ),
    (
        "highly-peaked",
        (
            Fraction(97, 100),
            Fraction(1, 100),
            Fraction(1, 100),
            Fraction(1, 100),
        ),
        (
            Fraction(97, 100),
            Fraction(1, 100),
            Fraction(1, 100),
            Fraction(1, 100),
        ),
    ),
)


def fixture_receipt(
    name: str,
    first: ProbabilityVector,
    second: ProbabilityVector,
) -> dict[str, object]:
    if not validate_probability_vector(first):
        raise AssertionError(f"{name}: first probability vector is invalid")
    if not validate_probability_vector(second):
        raise AssertionError(f"{name}: second probability vector is invalid")

    compact = products(first, second)
    scores = phase_scores(compact)
    compact_argmax = strict_argmax(compact)
    score_argmax = strict_argmax(scores)
    factor_sum = normalized_factor_condition(compact)
    if factor_sum > Decimal(1):
        raise AssertionError(
            f"{name}: normalized factor condition failed: {factor_sum}"
        )
    if compact_argmax != score_argmax:
        raise AssertionError(f"{name}: phase/compact argmax mismatch")

    ordered = sorted(compact, reverse=True)
    return {
        "name": name,
        "first": [str(value) for value in first],
        "second": [str(value) for value in second],
        "first_sum": str(sum(first)),
        "second_sum": str(sum(second)),
        "products": [str(value) for value in compact],
        "phase_scores": [str(value) for value in scores],
        "compact_argmax": compact_argmax,
        "phase_argmax": score_argmax,
        "reordered_q_only_argmax": strict_argmax(second),
        "top_two_product_margin": str(ordered[0] - ordered[1]),
        "sum_sqrt_products": str(factor_sum),
        "normalized_factor_condition": True,
    }


def run_oracle() -> dict[str, object]:
    receipts = [
        fixture_receipt(name, first, second)
        for name, first, second in FIXTURES
    ]

    # The one-lane operator proof is now an exact slice of the first integrated
    # normalized four-lane instance.
    first = FIXTURES[0][1]
    second = FIXTURES[0][2]
    p = first[0]
    q = second[0]
    sin_alpha = Fraction(4, 5)
    cos_beta = Fraction(12, 13)
    f = ry(p, sin_alpha)
    g = rx(cos_beta, q)
    sealed: Vector = (Fraction(), Fraction(), Fraction(1))

    fg = matrix_vector(g, matrix_vector(f, sealed))
    gf = matrix_vector(f, matrix_vector(g, sealed))
    fg_score = negative_y_score(fg)
    gf_score = negative_y_score(gf)
    restored = matrix_vector(
        transpose(f),
        matrix_vector(transpose(g), fg),
    )
    missing_g_inverse = matrix_vector(transpose(f), fg)
    wrong_g_inverse = matrix_vector(
        transpose(f),
        matrix_vector(g, fg),
    )
    reordered_inverse = matrix_vector(
        transpose(g),
        matrix_vector(transpose(f), fg),
    )
    wrong_topology = matrix_vector(
        transpose(f),
        matrix_vector(
            transpose(rx(Fraction(4, 5), Fraction(3, 5))),
            fg,
        ),
    )
    decohered = dephase_z(fg)

    old_detached_products = (
        Fraction(1, 20),
        Fraction(3, 20),
        Fraction(1, 10),
        Fraction(7, 10),
    )
    old_factor_sum = normalized_factor_condition(
        old_detached_products
    )

    first_products = products(first, second)
    first_scores = phase_scores(first_products)
    gates = {
        "all_probability_vectors_exact_normalized": all(
            validate_probability_vector(fixture[1])
            and validate_probability_vector(fixture[2])
            for fixture in FIXTURES
        ),
        "operator_inputs_come_from_integrated_fixture": (
            p == first[0] and q == second[0]
        ),
        "integrated_products_derived_elementwise": (
            first_products
            == tuple(first[i] * second[i] for i in range(4))
        ),
        "integrated_phase_score_law_exact": (
            first_scores
            == tuple((Fraction(1) + value) / 2 for value in first_products)
        ),
        "score_identity_exact": (
            fg_score == (Fraction(1) + p * q) / 2
        ),
        "reordered_q_only_exact": (
            gf_score == (Fraction(1) + q) / 2
        ),
        "integrated_order_changes_useful_boundary": (
            strict_argmax(first_products)
            != strict_argmax(second)
        ),
        "noncommuting_order_exact": fg != gf and fg_score != gf_score,
        "inverse_restoration_exact": restored == sealed,
        "missing_inverse_fails": missing_g_inverse != sealed,
        "wrong_inverse_fails": wrong_g_inverse != sealed,
        "reordered_inverse_fails": reordered_inverse != sealed,
        "topology_perturbation_fails": wrong_topology != sealed,
        "state_level_decoherence_zeroes_coherence": (
            decohered[0] == 0 and decohered[1] == 0
        ),
        "same_observable_after_decoherence_is_half": (
            negative_y_score(decohered) == Fraction(1, 2)
        ),
        "all_integrated_argmax_parity": all(
            receipt["compact_argmax"] == receipt["phase_argmax"]
            for receipt in receipts
        ),
        "near_tie_fixture_is_strict": (
            receipts[1]["top_two_product_margin"] == "1/40000"
        ),
        "highly_peaked_fixture_selects_first": (
            receipts[2]["compact_argmax"] == 0
        ),
        "old_detached_fixture_rejected_by_factor_condition": (
            old_factor_sum > Decimal(1)
        ),
    }
    if not all(gates.values()):
        raise AssertionError(
            "precontact two-row exact calibration oracle failed: "
            + ", ".join(
                name for name, passed in gates.items() if not passed
            )
        )

    return {
        "id": "neo-exp-0102-two-evidence-exact-calibration-oracle",
        "classification": (
            "PRECONTACT_TWO_ROW_REVERSIBLE_SCORE_COMPOSITION_CALIBRATION"
        ),
        "arithmetic": "fractions.Fraction with Decimal sqrt feasibility certificate",
        "fixtures": receipts,
        "operator_link": {
            "fixture": FIXTURES[0][0],
            "lane": 0,
            "p": str(p),
            "sin_alpha": str(sin_alpha),
            "q": str(q),
            "cos_beta": str(cos_beta),
            "fg_score": str(fg_score),
            "gf_score": str(gf_score),
        },
        "rejected_old_detached_fixture": {
            "products": [str(value) for value in old_detached_products],
            "sum_sqrt_products": str(old_factor_sum),
            "necessary_condition": "sum(sqrt(p_i*q_i)) <= 1",
            "condition_passed": False,
        },
        "gates": gates,
        "passed": True,
        "contact": {
            "server_contacts": 0,
            "model_callbacks": 0,
            "cuda_kernel_launches": 0,
        },
        "claim_ceiling": (
            "Exact integrated normalized-probability calibration oracle only; "
            "no production precision, inference-bearing carrier, phase "
            "resource, inference utility, or scaling claim."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(run_oracle(), indent=2, sort_keys=True))
