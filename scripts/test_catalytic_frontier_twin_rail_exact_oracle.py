#!/usr/bin/env python3
"""Focused tests for the independent neo-exp-0094 exact oracle."""

from fractions import Fraction
from pathlib import Path
import sys
import unittest


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import catalytic_frontier_twin_rail_exact_oracle as oracle


class QuadraticQuotientTests(unittest.TestCase):
    def test_quadratic_quotient_law_and_inverse(self) -> None:
        q = oracle.Quadratic(0, 1)
        self.assertEqual(q * q, oracle.Quadratic(-1))

        value = oracle.Quadratic(Fraction(3, 5), Fraction(4, 5))
        self.assertEqual(value.norm(), Fraction(1))
        self.assertEqual(value * value.inverse(), oracle.Quadratic(1))

    def test_public_phase_points_are_unit_norm_and_encode_probability(self) -> None:
        for expected_winner in oracle.USEFUL_SEQUENCE:
            probabilities, phases = oracle.fixture(expected_winner)
            self.assertEqual(sum(probabilities, Fraction(0)), Fraction(1))
            self.assertEqual(len(set(probabilities)), 4)
            for probability, phase in zip(probabilities, phases):
                self.assertEqual(phase.norm(), Fraction(1))
                self.assertEqual((Fraction(1) + phase.a) / 2, probability)


class TwinRailProgramTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start = oracle.initial_carrier()

    def test_score_identity_and_fixed_useful_boundaries(self) -> None:
        for expected_winner in oracle.USEFUL_SEQUENCE:
            with self.subTest(expected_winner=expected_winner):
                probabilities, phases = oracle.fixture(expected_winner)
                final = oracle.forward_program(self.start, phases)
                self.assertEqual(oracle.scores(final), probabilities)
                self.assertEqual(
                    oracle.lowest_index_argmax(oracle.scores(final)),
                    expected_winner,
                )

    def test_correct_reverse_topology_restores_exactly(self) -> None:
        for expected_winner in oracle.USEFUL_SEQUENCE:
            with self.subTest(expected_winner=expected_winner):
                _, phases = oracle.fixture(expected_winner)
                final = oracle.forward_program(self.start, phases)
                self.assertEqual(oracle.inverse_program(final, phases), self.start)

    def test_missing_wrong_and_reordered_inverse_fail(self) -> None:
        for expected_winner in oracle.USEFUL_SEQUENCE:
            with self.subTest(expected_winner=expected_winner):
                _, phases = oracle.fixture(expected_winner)
                final = oracle.forward_program(self.start, phases)
                self.assertNotEqual(
                    oracle.missing_inverse_program(final, phases), self.start
                )
                self.assertNotEqual(
                    oracle.wrong_inverse_variant_program(final, phases), self.start
                )
                self.assertNotEqual(
                    oracle.reordered_inverse_program(final, phases), self.start
                )

    def test_forward_order_is_noncommuting_and_changes_boundary(self) -> None:
        probabilities, phases = oracle.fixture("C")
        primary = oracle.forward_program(self.start, phases)
        reordered = oracle.reordered_forward_program(self.start, phases)

        self.assertNotEqual(primary, reordered)
        self.assertEqual(oracle.scores(primary), probabilities)
        self.assertEqual(oracle.scores(reordered), (Fraction(1),) * 4)
        self.assertEqual(oracle.lowest_index_argmax(oracle.scores(primary)), "C")
        self.assertEqual(oracle.lowest_index_argmax(oracle.scores(reordered)), "A")

    def test_dephased_sham_is_exactly_one_half(self) -> None:
        for expected_winner in oracle.USEFUL_SEQUENCE:
            with self.subTest(expected_winner=expected_winner):
                _, phases = oracle.fixture(expected_winner)
                self.assertEqual(
                    oracle.dephased_scores(self.start, phases),
                    (Fraction(1, 2),) * 4,
                )

    def test_null_carrier_rejects_before_transform(self) -> None:
        _, phases = oracle.fixture("C")
        with self.assertRaises(oracle.NullCarrierError):
            oracle.forward_program(None, phases)
        with self.assertRaises(oracle.NullCarrierError):
            oracle.inverse_program(None, phases)
        with self.assertRaises(oracle.NullCarrierError):
            oracle.scores(None)

    def test_frozen_attempt_0138_constants_are_exact(self) -> None:
        self.assertEqual(oracle.EXPERIMENT_ID, "neo-exp-0094")
        self.assertEqual(
            oracle.PREREGISTRATION_ATTEMPT_ID, "frontier-attempt-0138"
        )
        self.assertEqual(oracle.PUBLIC_SCHEMA_PREFIX_TOKEN_IDS, (4754, 8944, 3147))
        self.assertEqual(
            oracle.CANDIDATE_TOKEN_IDS, {"A": 32, "B": 33, "C": 34, "D": 35}
        )
        self.assertEqual(
            oracle.PORT_OWNER, "neo-exp-0094-four-choice-phase-consumer"
        )
        self.assertEqual(
            oracle.PORT_TYPE, "agents-a1-four-choice-logits-to-twinrail-v1"
        )
        self.assertEqual(
            oracle.MODULE_ID, "terminal-softmax-twinrail-hadamard-v1"
        )
        self.assertEqual(oracle.MODULE_VARIANT_PRIMARY, 0)
        self.assertEqual(oracle.MODULE_ORDINALS, (1, 2))
        self.assertEqual(oracle.GENERATIONS, (1, 2))
        self.assertEqual(
            oracle.PROJECTION_POLICY,
            "FINAL_SINGLE_HYPOTHESIS_TOKEN_AFTER_RESTORATION",
        )
        self.assertEqual(oracle.CARRIER_CELLS_COMPLEX_DOUBLE, 8)
        self.assertEqual(oracle.CARRIER_BYTES, 128)

    def test_oracle_summary_passes_without_contact(self) -> None:
        result = oracle.run_oracle()
        self.assertTrue(result["passed"])
        self.assertTrue(all(result["gates"].values()))
        self.assertEqual(
            result["contact"],
            {
                "model_callbacks": 0,
                "server_contacts": 0,
                "cuda_kernel_launches": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
