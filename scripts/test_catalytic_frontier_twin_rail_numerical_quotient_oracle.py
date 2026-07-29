#!/usr/bin/env python3
"""Zero-contact tests for the neo-exp-0097 numerical quotient oracle."""

from fractions import Fraction
from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_twin_rail_numerical_quotient_oracle as oracle


class NumericalQuotientOracleTests(unittest.TestCase):
    def test_identity_and_public_constants_are_frozen(self) -> None:
        self.assertEqual(oracle.EXPERIMENT_ID, "neo-exp-0097")
        self.assertEqual(
            oracle.PREREGISTRATION_ATTEMPT_ID,
            "frontier-attempt-0144",
        )
        self.assertEqual(
            oracle.EXECUTION_ATTEMPT_ID,
            "frontier-attempt-0145",
        )
        self.assertEqual(
            oracle.REORDERED_SCORE_SPREAD_TOLERANCE,
            Fraction(6, 10**12),
        )
        self.assertEqual(
            oracle.PRIMARY_MINIMUM_TOP_TWO_MARGIN,
            Fraction(2, 10**12),
        )

    def test_strict_and_quotient_routes_separate(self) -> None:
        exact = (Fraction(1),) * 4
        within = (*exact[:3], Fraction(1) + Fraction(3, 10**12))
        outside = (*exact[:3], Fraction(1) + Fraction(7, 10**12))
        self.assertEqual(oracle.strict_lowest_index_argmax(exact), "A")
        self.assertEqual(oracle.strict_lowest_index_argmax(within), "D")
        self.assertEqual(oracle.canonical_reordered_projection(within), "A")
        self.assertIsNone(oracle.canonical_reordered_projection(outside))

    def test_primary_margin_is_strict(self) -> None:
        tolerance = oracle.PRIMARY_MINIMUM_TOP_TWO_MARGIN
        self.assertFalse(
            oracle.primary_margin_guard(
                (Fraction(1), Fraction(1) - tolerance, Fraction(0), Fraction(0))
            )
        )
        self.assertTrue(
            oracle.primary_margin_guard(
                (
                    Fraction(1),
                    Fraction(1) - tolerance - Fraction(1, 10**15),
                    Fraction(0),
                    Fraction(0),
                )
            )
        )

    def test_summary_passes_without_contact(self) -> None:
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

    def test_wrong_dimensions_reject(self) -> None:
        for function in (
            oracle.strict_lowest_index_argmax,
            oracle.canonical_reordered_projection,
            oracle.primary_margin_guard,
        ):
            with self.subTest(function=function.__name__):
                with self.assertRaises(ValueError):
                    function((Fraction(1),))


if __name__ == "__main__":
    unittest.main()
