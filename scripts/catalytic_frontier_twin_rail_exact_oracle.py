#!/usr/bin/env python3
"""Exact bounded oracle for the preregistered neo-exp-0094 twin-rail law.

The production candidate uses complex-double cells, ``acos`` and a normalized
Hadamard.  This independent oracle uses only ``fractions.Fraction`` in the
quadratic quotient Q[q] / (q^2 + 1).  It works projectively: the unnormalized
Hadamard differs from the production Hadamard only by one nonzero common
factor, which cancels in the rail probability, and its exact inverse is H / 2.

No model, server, CUDA runtime, benchmark label, or expected answer is read.
The fixtures are bounded public rational points on the unit circle.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
from typing import Final, Iterable, Mapping, Sequence


EXPERIMENT_ID: Final = "neo-exp-0094"
PREREGISTRATION_ATTEMPT_ID: Final = "frontier-attempt-0138"
EXECUTION_ATTEMPT_ID: Final = "frontier-attempt-0139"

SOURCE_PROMPT_TOKENS: Final = 777
PUBLIC_SCHEMA_PREFIX_TOKEN_IDS: Final = (4754, 8944, 3147)
HYPOTHESIS_PROMPT_TOKENS: Final = 780
CANDIDATE_TOKEN_IDS: Final = {"A": 32, "B": 33, "C": 34, "D": 35}
CANDIDATE_ORDER: Final = tuple(CANDIDATE_TOKEN_IDS)
USEFUL_SEQUENCE: Final = ("C", "D", "B")
PRIMARY_REUSE_EDGES: Final = ("C-to-D", "D-to-B")

CARRIER_CELLS_COMPLEX_DOUBLE: Final = 8
CARRIER_BYTES: Final = 128
INITIAL_LAW: Final = "four public dirty common-mode twin rails"
OBSERVATION_MAP: Final = "stable four-logit softmax only"
MODULE_DESCRIPTOR: Final = (
    "conditional second-rail phase theta_h=acos(2*p_h-1)",
    "normalized two-rail Hadamard",
)
MODULE_ID: Final = "terminal-softmax-twinrail-hadamard-v1"
MODULE_VARIANT_PRIMARY: Final = 0
MODULE_ORDINALS: Final = (1, 2)
GENERATIONS: Final = (1, 2)
PORT_OWNER: Final = "neo-exp-0094-four-choice-phase-consumer"
PORT_TYPE: Final = "agents-a1-four-choice-logits-to-twinrail-v1"
PROJECTION_POLICY: Final = "FINAL_SINGLE_HYPOTHESIS_TOKEN_AFTER_RESTORATION"
FIBER_RESTORATION_CLASS: Final = "NUMERICAL_PHYSICAL_STATE_RESTORATION"
SUPPORTING_LIVE_SOURCE_RESTORATION_CLASS: Final = "DECLARED_CLOSURE"


class NullCarrierError(ValueError):
    """Raised before a carrier operation when no carrier was supplied."""


@dataclass(frozen=True)
class Quadratic:
    """An exact element ``a + b*q`` of Q[q] / (q^2 + 1).

    The quotient generator ``q`` is the exact Gaussian unit.  Keeping this
    implementation local and Fraction-only makes the oracle independent of
    both the numerical runtime and third-party symbolic packages.
    """

    a: Fraction
    b: Fraction = Fraction(0)

    def __init__(self, a: int | Fraction, b: int | Fraction = 0) -> None:
        object.__setattr__(self, "a", Fraction(a))
        object.__setattr__(self, "b", Fraction(b))

    @staticmethod
    def coerce(value: int | Fraction | "Quadratic") -> "Quadratic":
        return value if isinstance(value, Quadratic) else Quadratic(value)

    def __add__(self, other: int | Fraction | "Quadratic") -> "Quadratic":
        rhs = self.coerce(other)
        return Quadratic(self.a + rhs.a, self.b + rhs.b)

    def __radd__(self, other: int | Fraction | "Quadratic") -> "Quadratic":
        return self + other

    def __neg__(self) -> "Quadratic":
        return Quadratic(-self.a, -self.b)

    def __sub__(self, other: int | Fraction | "Quadratic") -> "Quadratic":
        return self + (-self.coerce(other))

    def __rsub__(self, other: int | Fraction | "Quadratic") -> "Quadratic":
        return self.coerce(other) - self

    def __mul__(self, other: int | Fraction | "Quadratic") -> "Quadratic":
        rhs = self.coerce(other)
        return Quadratic(
            self.a * rhs.a - self.b * rhs.b,
            self.a * rhs.b + self.b * rhs.a,
        )

    def __rmul__(self, other: int | Fraction | "Quadratic") -> "Quadratic":
        return self * other

    def conjugate(self) -> "Quadratic":
        return Quadratic(self.a, -self.b)

    def norm(self) -> Fraction:
        return self.a * self.a + self.b * self.b

    def inverse(self) -> "Quadratic":
        denominator = self.norm()
        if denominator == 0:
            raise ZeroDivisionError("zero has no inverse in Q[q]/(q^2+1)")
        conjugate = self.conjugate()
        return Quadratic(conjugate.a / denominator, conjugate.b / denominator)

    def __truediv__(
        self, other: int | Fraction | "Quadratic"
    ) -> "Quadratic":
        return self * self.coerce(other).inverse()


RailPair = tuple[Quadratic, Quadratic]
Carrier = tuple[RailPair, ...]


# Four distinct positive probabilities that sum exactly to one.  Each has a
# rational unit-circle phase z with Re(z) = 2*p - 1.
_PROBABILITY_PHASE_POINTS: Final = (
    (Fraction(1, 17), Quadratic(Fraction(-15, 17), Fraction(8, 17))),
    (Fraction(1, 10), Quadratic(Fraction(-4, 5), Fraction(3, 5))),
    (Fraction(9, 34), Quadratic(Fraction(-8, 17), Fraction(15, 17))),
    (Fraction(49, 85), Quadratic(Fraction(13, 85), Fraction(84, 85))),
)

# The three fixtures follow the preregistered useful C, D, B sequence.  They
# are cyclic public permutations of the same normalized rational spectrum.
PROBABILITY_FIXTURES: Final = {
    "C": (
        _PROBABILITY_PHASE_POINTS[0],
        _PROBABILITY_PHASE_POINTS[1],
        _PROBABILITY_PHASE_POINTS[3],
        _PROBABILITY_PHASE_POINTS[2],
    ),
    "D": (
        _PROBABILITY_PHASE_POINTS[2],
        _PROBABILITY_PHASE_POINTS[0],
        _PROBABILITY_PHASE_POINTS[1],
        _PROBABILITY_PHASE_POINTS[3],
    ),
    "B": (
        _PROBABILITY_PHASE_POINTS[1],
        _PROBABILITY_PHASE_POINTS[3],
        _PROBABILITY_PHASE_POINTS[2],
        _PROBABILITY_PHASE_POINTS[0],
    ),
}

# Nonzero, unequal public common-mode factors ensure restoration is not merely
# a special case of an all-one carrier.  Global pair scale cancels projectively.
DIRTY_COMMON_MODES: Final = (
    Quadratic(1, 1),
    Quadratic(2, -1),
    Quadratic(-1, 2),
    Quadratic(3, 2),
)


def require_carrier(carrier: Carrier | None) -> Carrier:
    if carrier is None:
        raise NullCarrierError("neo-exp-0094 rejects a null twin-rail carrier")
    if len(carrier) != len(CANDIDATE_ORDER):
        raise ValueError("twin-rail carrier must contain exactly four pairs")
    return carrier


def initial_carrier() -> Carrier:
    return tuple((common, common) for common in DIRTY_COMMON_MODES)


def fixture(name: str) -> tuple[tuple[Fraction, ...], tuple[Quadratic, ...]]:
    points = PROBABILITY_FIXTURES[name]
    probabilities = tuple(point[0] for point in points)
    phases = tuple(point[1] for point in points)
    return probabilities, phases


def conditional_second_rail_phase(
    carrier: Carrier | None, phases: Sequence[Quadratic]
) -> Carrier:
    source = require_carrier(carrier)
    if len(phases) != len(source):
        raise ValueError("one public phase is required per hypothesis pair")
    return tuple((first, phase * second) for (first, second), phase in zip(source, phases))


def conditional_second_rail_phase_inverse(
    carrier: Carrier | None,
    phases: Sequence[Quadratic],
    *,
    wrong_variant: bool = False,
) -> Carrier:
    source = require_carrier(carrier)
    if len(phases) != len(source):
        raise ValueError("one public phase is required per hypothesis pair")
    inverses = phases if wrong_variant else tuple(phase.conjugate() for phase in phases)
    return tuple(
        (first, inverse * second)
        for (first, second), inverse in zip(source, inverses)
    )


def hadamard(carrier: Carrier | None) -> Carrier:
    """Apply projective H; production normalization cancels in every score."""

    source = require_carrier(carrier)
    return tuple((first + second, first - second) for first, second in source)


def hadamard_inverse(carrier: Carrier | None) -> Carrier:
    source = require_carrier(carrier)
    half = Fraction(1, 2)
    return tuple(
        ((first + second) * half, (first - second) * half)
        for first, second in source
    )


def forward_program(carrier: Carrier | None, phases: Sequence[Quadratic]) -> Carrier:
    """Execute preregistered order F then G."""

    return hadamard(conditional_second_rail_phase(carrier, phases))


def reordered_forward_program(
    carrier: Carrier | None, phases: Sequence[Quadratic]
) -> Carrier:
    """Execute adversarial order G then F."""

    return conditional_second_rail_phase(hadamard(carrier), phases)


def inverse_program(carrier: Carrier | None, phases: Sequence[Quadratic]) -> Carrier:
    """Reverse-rematerialize public topology as G^-1 then F^-1."""

    return conditional_second_rail_phase_inverse(hadamard_inverse(carrier), phases)


def missing_inverse_program(
    carrier: Carrier | None, phases: Sequence[Quadratic]
) -> Carrier:
    """Omit F^-1 after the correct G^-1."""

    del phases
    return hadamard_inverse(carrier)


def wrong_inverse_variant_program(
    carrier: Carrier | None, phases: Sequence[Quadratic]
) -> Carrier:
    """Use F rather than conjugate F^-1 after G^-1."""

    return conditional_second_rail_phase_inverse(
        hadamard_inverse(carrier), phases, wrong_variant=True
    )


def reordered_inverse_program(
    carrier: Carrier | None, phases: Sequence[Quadratic]
) -> Carrier:
    """Apply F^-1 before G^-1, violating reverse topology."""

    return hadamard_inverse(
        conditional_second_rail_phase_inverse(carrier, phases)
    )


def pair_score(pair: RailPair) -> Fraction:
    first_population = pair[0].norm()
    total_population = first_population + pair[1].norm()
    if total_population == 0:
        raise ValueError("cannot project a zero twin-rail pair")
    return first_population / total_population


def scores(carrier: Carrier | None) -> tuple[Fraction, ...]:
    return tuple(pair_score(pair) for pair in require_carrier(carrier))


def lowest_index_argmax(values: Sequence[Fraction]) -> str:
    if len(values) != len(CANDIDATE_ORDER):
        raise ValueError("projection requires exactly four hypothesis scores")
    winner_index = max(range(len(values)), key=values.__getitem__)
    return CANDIDATE_ORDER[winner_index]


def dephased_score(pair_before_hadamard: RailPair) -> Fraction:
    """Project after deleting the within-pair cross term.

    A Hadamard sends either rail population equally to both output rails.
    With coherence killed, the first output therefore receives exactly half
    the total population.
    """

    total_population = pair_before_hadamard[0].norm() + pair_before_hadamard[1].norm()
    if total_population == 0:
        raise ValueError("cannot dephase a zero twin-rail pair")
    first_output_population = total_population / 2
    return first_output_population / total_population


def dephased_scores(
    carrier: Carrier | None, phases: Sequence[Quadratic]
) -> tuple[Fraction, ...]:
    phased = conditional_second_rail_phase(carrier, phases)
    return tuple(dephased_score(pair) for pair in phased)


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def run_oracle() -> Mapping[str, object]:
    start = initial_carrier()
    fixture_evidence = {}
    all_score_identities = True
    all_restored = True
    all_missing_failed = True
    all_wrong_failed = True
    all_reordered_inverse_failed = True
    all_dephased = True

    for expected_winner in USEFUL_SEQUENCE:
        probabilities, phases = fixture(expected_winner)
        forward = forward_program(start, phases)
        projected_scores = scores(forward)
        restored = inverse_program(forward, phases)

        missing = missing_inverse_program(forward, phases)
        wrong = wrong_inverse_variant_program(forward, phases)
        reordered_inverse = reordered_inverse_program(forward, phases)

        identity = projected_scores == probabilities
        correct_winner = lowest_index_argmax(projected_scores) == expected_winner
        dephased = dephased_scores(start, phases)
        fixture_evidence[expected_winner] = {
            "probabilities": [_fraction_text(value) for value in probabilities],
            "scores": [_fraction_text(value) for value in projected_scores],
            "winner": lowest_index_argmax(projected_scores),
            "restored": restored == start,
            "missing_inverse_fails": missing != start,
            "wrong_inverse_variant_fails": wrong != start,
            "reordered_inverse_fails": reordered_inverse != start,
            "dephased_scores": [_fraction_text(value) for value in dephased],
        }
        all_score_identities &= identity and correct_winner
        all_restored &= restored == start
        all_missing_failed &= missing != start
        all_wrong_failed &= wrong != start
        all_reordered_inverse_failed &= reordered_inverse != start
        all_dephased &= dephased == (Fraction(1, 2),) * 4

    probabilities, phases = fixture("C")
    primary = forward_program(start, phases)
    reordered = reordered_forward_program(start, phases)
    reordered_values = scores(reordered)
    forward_order_sensitive = primary != reordered
    reordered_tied = reordered_values == (Fraction(1),) * 4
    reordered_boundary_distinct = (
        lowest_index_argmax(reordered_values) == "A"
        and lowest_index_argmax(probabilities) == "C"
    )

    null_rejected = False
    try:
        forward_program(None, phases)
    except NullCarrierError:
        null_rejected = True

    gates = {
        "score_identity_p": all_score_identities,
        "correct_reverse_topology_restores": all_restored,
        "missing_inverse_fails": all_missing_failed,
        "wrong_inverse_variant_fails": all_wrong_failed,
        "reordered_inverse_fails": all_reordered_inverse_failed,
        "forward_modules_noncommute": forward_order_sensitive,
        "reordered_forward_fixed_tie": reordered_tied,
        "reordered_forward_boundary_distinct": reordered_boundary_distinct,
        "dephased_sham_score_one_half": all_dephased,
        "null_carrier_rejects": null_rejected,
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "preregistration_attempt_id": PREREGISTRATION_ATTEMPT_ID,
        "arithmetic": "Q[q]/(q^2+1) with fractions.Fraction",
        "candidate_token_ids": CANDIDATE_TOKEN_IDS,
        "module_id": MODULE_ID,
        "module_descriptor": MODULE_DESCRIPTOR,
        "fixtures": fixture_evidence,
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
