from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_open_relational_carrier_r2 as r2


class OpenRelationalCarrierR2Tests(unittest.TestCase):
    def valid_runtime(self) -> dict:
        return {
            "schema_version": r2.SCHEMA_VERSION,
            "geometry": {
                "carriers": r2.BATCH_CARRIERS,
                "lanes_per_carrier": r2.LANES_PER_CARRIER,
                "bytes_per_boundary": r2.BOUNDARY_BYTES,
                "warmups": r2.WARMUPS,
                "repetitions": r2.REPETITIONS,
            },
            "ports": {
                "F_domain": "X.complex4@r2-v1",
                "F_codomain": "Y.complex4.z4@r2-v1",
                "G_domain": "Y.complex4.z4@r2-v1",
                "G_codomain": "Z.complex4@r2-v1",
            },
            "metrics": {
                "primary_intermediate_materialized_bytes": 0,
                "control_intermediate_d2h_bytes_per_rep": r2.BOUNDARY_BYTES,
                "control_intermediate_h2d_bytes_per_rep": r2.BOUNDARY_BYTES,
                "control_intermediate_cpu_read_bytes_per_rep": r2.BOUNDARY_BYTES,
                "wall_speedup": r2.MINIMUM_WALL_SPEEDUP,
            },
            "controls": {
                "primary_final_projection_count": 1,
                "control_intermediate_projection_count": 1,
                "type_mismatch_rejected": True,
                "launches_at_type_mismatch": 0,
                "primary_route_admitted": True,
                "materialized_route_rejected_as_primary": True,
                "primary_reference_mismatches": 0,
                "route_mismatches": 0,
                "wrong_order_equal_count": 0,
                "wrong_order_negative_law_failures": 0,
                "restoration_mismatches": 0,
                "wrong_inverse_restored_count": 0,
                "final_intermediate_residency_zero": True,
            },
            "all_integrity_gates": True,
        }

    def classify(self, runtime: dict) -> tuple[str, dict[str, bool]]:
        return r2.classify(
            runtime,
            {"gates": {"static": True}},
            stable_before={"healthy": True},
            stable_after={"healthy": True},
            frontier_free_before=True,
            frontier_free_after=True,
            binary_returncode=0,
        )

    def test_exact_valid_contract_accepts(self):
        verdict, gates = self.classify(self.valid_runtime())
        self.assertEqual(
            verdict, "accept-bounded-open-r2-cuda-composition"
        )
        self.assertTrue(all(gates.values()))

    def test_speed_only_failure_is_bounded_reject(self):
        runtime = self.valid_runtime()
        runtime["metrics"]["wall_speedup"] = (
            r2.MINIMUM_WALL_SPEEDUP - 0.001
        )
        verdict, gates = self.classify(runtime)
        self.assertEqual(
            verdict, "reject-speed-open-r2-composition-exact"
        )
        self.assertFalse(gates["repeated_speed_gate"])

    def test_materialized_primary_cannot_accept(self):
        runtime = self.valid_runtime()
        runtime["metrics"]["primary_intermediate_materialized_bytes"] = 1
        verdict, gates = self.classify(runtime)
        self.assertEqual(
            verdict, "reject-integrity-open-r2-composition"
        )
        self.assertFalse(gates["primary_y_unmaterialized"])

    def test_type_mismatch_after_launch_cannot_accept(self):
        runtime = self.valid_runtime()
        runtime["controls"]["launches_at_type_mismatch"] = 1
        verdict, gates = self.classify(runtime)
        self.assertEqual(
            verdict, "reject-integrity-open-r2-composition"
        )
        self.assertFalse(gates["type_mismatch_precontact"])

    def test_wrong_order_or_wrong_inverse_cannot_accept(self):
        runtime = self.valid_runtime()
        runtime["controls"]["wrong_order_equal_count"] = 1
        runtime["controls"]["wrong_inverse_restored_count"] = 1
        verdict, gates = self.classify(runtime)
        self.assertEqual(
            verdict, "reject-integrity-open-r2-composition"
        )
        self.assertFalse(gates["wrong_order_negative"])
        self.assertFalse(gates["wrong_inverse_order_fails"])

    def test_nonzero_binary_exit_cannot_accept(self):
        verdict, gates = r2.classify(
            self.valid_runtime(),
            {"gates": {"static": True}},
            stable_before={"healthy": True},
            stable_after={"healthy": True},
            frontier_free_before=True,
            frontier_free_after=True,
            binary_returncode=4,
        )
        self.assertEqual(
            verdict, "reject-integrity-open-r2-composition"
        )
        self.assertFalse(gates["binary_returncode_zero"])


if __name__ == "__main__":
    unittest.main()
