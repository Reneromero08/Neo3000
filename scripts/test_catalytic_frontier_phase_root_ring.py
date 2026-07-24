from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_fixed_size_rebase as fixed_size
import catalytic_frontier_phase_root_ring as phase_ring
import catalytic_frontier_reversible_period4 as period4


class PhaseRootRingTests(unittest.TestCase):
    def test_contract_changes_only_the_root_lifecycle(self):
        contract = phase_ring.CONTRACT
        self.assertTrue(contract.phase_root_ring)
        self.assertEqual(contract.root_bank_capacity, 5)
        self.assertEqual(contract.recursive_depth, 16)
        self.assertEqual(contract.transition, period4.CONTRACT.transition)
        self.assertEqual(
            contract.expected_state_sequence,
            period4.CONTRACT.expected_state_sequence,
        )
        self.assertEqual(
            contract.expected_generated_sha256,
            period4.CONTRACT.expected_generated_sha256,
        )
        self.assertEqual(
            contract.expected_child_sha256,
            period4.CONTRACT.expected_child_sha256,
        )
        self.assertEqual(
            contract.expected_request_sha256,
            period4.CONTRACT.expected_request_sha256,
        )
        self.assertEqual(
            phase_ring.EXPECTED_POST_FILL_DEVICE_BYTES,
            320_389_120,
        )
        self.assertEqual(
            phase_ring.EXPECTED_CHARGED_AVOIDED_FRESH_PROMPT_TOKENS,
            11_102,
        )
        self.assertEqual(
            dict(contract.expected_cuda_runtime_sha256),
            dict(phase_ring.EXPECTED_CUDA_RUNTIME_SHA256),
        )
        self.assertEqual(
            set(dict(contract.expected_cuda_runtime_sha256)),
            set(fixed_size.latency.CUDA_ROOT_RUNTIME_SHA256),
        )

    def test_classifier_enforces_phase_ring_causal_and_total_wall_gates(self):
        accepted = phase_ring.CONTRACT.accepted_classification
        kwargs = {
            "integrity": True,
            "fixed_size": True,
            "saved_work_law": True,
            "speedup": phase_ring.MINIMUM_FULLY_COUNTED_WALL_SPEEDUP,
            "recursive_depth": 16,
            "catalytic_wall_seconds": phase_ring.MAXIMUM_CATALYTIC_WALL_SECONDS,
            "root_and_rebase_wall_seconds": (
                phase_ring.MAXIMUM_ROOT_AND_REBASE_WALL_SECONDS
            ),
            "ring_overhead_seconds": phase_ring.MAXIMUM_RING_OVERHEAD_SECONDS,
            "contract": phase_ring.CONTRACT,
        }
        self.assertEqual(fixed_size.classify(**kwargs), accepted)
        self.assertEqual(
            fixed_size.classify(
                **{
                    **kwargs,
                    "root_and_rebase_wall_seconds": (
                        phase_ring.MAXIMUM_ROOT_AND_REBASE_WALL_SECONDS + 0.001
                    ),
                }
            ),
            "phase-root-ring-above-preregistered-root-rebase-wall-ceiling",
        )
        self.assertEqual(
            fixed_size.classify(
                **{
                    **kwargs,
                    "ring_overhead_seconds": (
                        phase_ring.MAXIMUM_RING_OVERHEAD_SECONDS + 0.001
                    ),
                }
            ),
            "phase-root-ring-above-preregistered-overhead-ceiling",
        )
        self.assertEqual(
            fixed_size.classify(
                **{
                    **kwargs,
                    "catalytic_wall_seconds": (
                        phase_ring.MAXIMUM_CATALYTIC_WALL_SECONDS + 0.001
                    ),
                }
            ),
            "fixed-size-rebase-above-preregistered-catalytic-wall-ceiling",
        )

    def test_device_root_receipt_requires_an_isolated_negative_storage_key(self):
        response = {
            "action": "root-save",
            "root_id": "phase-D",
            "id_slot": 0,
            "id_slot_source": 0,
            "device_storage_key": -1,
            "n_tokens": fixed_size.EXPECTED_CHILD_TOKENS,
            "n_bytes": fixed_size.EXPECTED_CHILD_DEVICE_BYTES + 100,
            "n_host_bytes": 100,
            "n_device_bytes": fixed_size.EXPECTED_CHILD_DEVICE_BYTES,
            "n_device_bytes_after": fixed_size.EXPECTED_CHILD_DEVICE_BYTES,
            "n_gpu_bytes": fixed_size.EXPECTED_CHILD_DEVICE_BYTES,
            "n_gpu_bytes_after": fixed_size.EXPECTED_CHILD_DEVICE_BYTES,
            "n_checkpoints": 0,
            "n_roots_after": 2,
            "n_roots_capacity": phase_ring.ROOT_BANK_CAPACITY,
            "n_total_bytes_after": 160_000_000,
            "n_total_device_bytes_after": fixed_size.EXPECTED_CHILD_DEVICE_BYTES,
            "n_total_gpu_bytes_after": fixed_size.EXPECTED_CHILD_DEVICE_BYTES,
            "timings": {"root_ms": 1.0},
        }
        record = fixed_size.validate_root(
            response,
            action="root-save",
            root_id="phase-D",
            storage="device",
            expected_tokens=fixed_size.EXPECTED_CHILD_TOKENS,
            expected_roots_after=2,
            expected_total_device_bytes_after=fixed_size.EXPECTED_CHILD_DEVICE_BYTES,
            expected_root_capacity=phase_ring.ROOT_BANK_CAPACITY,
        )
        self.assertEqual(record["device_storage_key"], -1)
        with self.assertRaises(RuntimeError):
            fixed_size.validate_root(
                {**response, "device_storage_key": 0},
                action="root-save",
                root_id="phase-D",
                storage="device",
                expected_tokens=fixed_size.EXPECTED_CHILD_TOKENS,
                expected_roots_after=2,
                expected_total_device_bytes_after=(
                    fixed_size.EXPECTED_CHILD_DEVICE_BYTES
                ),
                expected_root_capacity=phase_ring.ROOT_BANK_CAPACITY,
            )

    def test_cleanup_finalization_preserves_phase_ring_identity(self):
        result = {
            "verdict": "accept",
            "quality_gates": {},
            "metrics": {"residency": {}},
        }
        cleanup = {
            "stable_after": {"healthy": True},
            "port_free": True,
        }
        with (
            mock.patch.object(
                fixed_size.harness.live_runtime,
                "cleanup_integrity",
                return_value={"passed": True},
            ),
            mock.patch.object(
                fixed_size.latency,
                "cleanup_peak_wddm_bytes",
                return_value=1,
            ),
        ):
            finalized = fixed_size.finalize_after_cleanup(
                result,
                cleanup=cleanup,
                cleanup_wall_seconds=0.1,
                stable_pids={3860},
                recursive_depth=16,
                contract=phase_ring.CONTRACT,
            )
        self.assertEqual(
            finalized["classification"],
            phase_ring.CONTRACT.accepted_classification,
        )
        self.assertTrue(
            finalized["quality_gates"][
                "checksum_addressed_cuda_phase_root_ring_supported"
            ]
        )

    def test_wrapper_delegates_exact_contract(self):
        with mock.patch.object(fixed_size, "main", return_value=0) as delegated:
            self.assertEqual(phase_ring.main(), 0)
        delegated.assert_called_once_with(contract=phase_ring.CONTRACT)


if __name__ == "__main__":
    unittest.main()
