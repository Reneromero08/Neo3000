#!/usr/bin/env python3
"""Independent exact bounded oracle for neo-exp-0102.

The production carrier uses fixed-width complex doubles.  This oracle uses
only fractions.Fraction and the Bloch-vector action of the same public Ry/Rx
program on one bounded rational Pythagorean instance.
"""
from __future__ import annotations

from fractions import Fraction
import json
from typing import Iterable


Vector = tuple[Fraction, Fraction, Fraction]
Matrix = tuple[Vector, Vector, Vector]


def matrix_vector(matrix: Matrix, vector: Vector) -> Vector:
    return tuple(
        sum((row[index] * vector[index] for index in range(3)), Fraction())
        for row in matrix
    )  # type: ignore[return-value]


def matrix_matrix(lhs: Matrix, rhs: Matrix) -> Matrix:
    columns = tuple(zip(*rhs))
    return tuple(
        tuple(
            sum((lhs_row[index] * rhs_column[index] for index in range(3)), Fraction())
            for rhs_column in columns
        )
        for lhs_row in lhs
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


def run_oracle() -> dict[str, object]:
    # cos(alpha)=p=3/5 and sin(beta)=q=5/13 make every SO(3)
    # coefficient exact and rational.
    p = Fraction(3, 5)
    sin_alpha = Fraction(4, 5)
    q = Fraction(5, 13)
    cos_beta = Fraction(12, 13)
    f = ry(p, sin_alpha)
    g = rx(cos_beta, q)
    sealed: Vector = (Fraction(), Fraction(), Fraction(1))

    fg = matrix_vector(g, matrix_vector(f, sealed))
    gf = matrix_vector(f, matrix_vector(g, sealed))
    fg_score = (Fraction(1) - fg[1]) / 2
    gf_score = (Fraction(1) - gf[1]) / 2
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

    compact_products = (
        Fraction(1, 20),
        Fraction(3, 20),
        Fraction(1, 10),
        Fraction(7, 10),
    )
    phase_scores = tuple((Fraction(1) + value) / 2 for value in compact_products)
    dephased_scores = (Fraction(1, 2),) * 4

    gates = {
        "score_identity_exact": fg_score == (Fraction(1) + p * q) / 2,
        "reordered_q_only_exact": gf_score == (Fraction(1) + q) / 2,
        "noncommuting_order_exact": fg != gf and fg_score != gf_score,
        "inverse_restoration_exact": restored == sealed,
        "missing_inverse_fails": missing_g_inverse != sealed,
        "wrong_inverse_fails": wrong_g_inverse != sealed,
        "reordered_inverse_fails": reordered_inverse != sealed,
        "topology_perturbation_fails": wrong_topology != sealed,
        "phase_compact_argmax_parity": (
            strict_argmax(phase_scores) == strict_argmax(compact_products) == 3
        ),
        "dephased_canonical_a": strict_argmax(dephased_scores) == 0,
    }
    if not all(gates.values()):
        raise AssertionError(
            "neo-exp-0102 exact oracle failed: "
            + ", ".join(name for name, passed in gates.items() if not passed)
        )

    return {
        "id": "neo-exp-0102-two-evidence-exact-oracle",
        "arithmetic": "fractions.Fraction",
        "bounded_instance": {
            "p": str(p),
            "sin_alpha": str(sin_alpha),
            "q": str(q),
            "cos_beta": str(cos_beta),
            "fg_score": str(fg_score),
            "gf_score": str(gf_score),
        },
        "gates": gates,
        "passed": True,
        "contact": {
            "server_contacts": 0,
            "model_callbacks": 0,
            "cuda_kernel_launches": 0,
        },
        "claim_ceiling": (
            "Exact bounded operator/order/inverse oracle only; no production "
            "precision, inference utility, phase advantage, or scaling claim."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(run_oracle(), indent=2, sort_keys=True))
