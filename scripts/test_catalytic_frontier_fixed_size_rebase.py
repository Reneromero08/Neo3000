from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_fixed_size_rebase as fixed_size


class FixedSizeRebaseTests(unittest.TestCase):
    def state(self, visible: list[int] | None = None) -> dict[str, object]:
        visible = visible or [101, 102, 103, 104, 105]
        return {
            "answer": "C",
            "visible_token_ids": visible,
            "generated_token_ids": [*visible, 999],
            "terminal_eog_id": 999,
        }

    def test_compact_child_is_exact_complete_branch_plus_visible_ids(self):
        base = list(range(fixed_size.EXPECTED_COMPLETE_BRANCH_TOKENS))
        state = self.state()

        tokens = fixed_size.compact_child_tokens(base, state)

        self.assertEqual(tokens[: len(base)], base)
        self.assertEqual(tokens[-5:], state["visible_token_ids"])
        self.assertEqual(len(tokens), fixed_size.EXPECTED_CHILD_TOKENS)

    def test_compact_child_rejects_non_exact_generated_terminal(self):
        state = self.state()
        state["generated_token_ids"] = [101, 102, 103, 104, 105, 998]
        with self.assertRaises(RuntimeError):
            fixed_size.compact_child_tokens(
                list(range(fixed_size.EXPECTED_COMPLETE_BRANCH_TOKENS)),
                state,
            )

    def test_classifier_requires_integrity_size_saved_work_and_speed(self):
        accepted = "pinned-base-fixed-output-cuda-capsule-rebase-r3-supported-bounded"
        self.assertEqual(
            fixed_size.classify(
                integrity=True,
                fixed_size=True,
                saved_work_law=True,
                speedup=fixed_size.MIN_FULL_LIFECYCLE_WALL_SPEEDUP,
            ),
            accepted,
        )
        self.assertNotEqual(
            fixed_size.classify(
                integrity=False,
                fixed_size=True,
                saved_work_law=True,
                speedup=2.0,
            ),
            accepted,
        )
        self.assertNotEqual(
            fixed_size.classify(
                integrity=True,
                fixed_size=False,
                saved_work_law=True,
                speedup=2.0,
            ),
            accepted,
        )
        self.assertNotEqual(
            fixed_size.classify(
                integrity=True,
                fixed_size=True,
                saved_work_law=False,
                speedup=2.0,
            ),
            accepted,
        )
        self.assertNotEqual(
            fixed_size.classify(
                integrity=True,
                fixed_size=True,
                saved_work_law=True,
                speedup=1.0,
            ),
            accepted,
        )

    def test_recursive_depth_contract_extends_only_the_accepted_fixed_point(self):
        self.assertEqual(
            fixed_size.experiment_id_for_depth(16),
            "neo-exp-0076",
        )
        sequence = fixed_size.expected_state_sequence_for_depth(16)
        self.assertEqual(len(sequence), 17)
        self.assertEqual(sequence[:3], ("C", "D", "B"))
        self.assertEqual(set(sequence[2:]), {"B"})
        orders = fixed_size.pair_route_orders_for_depth(16)
        self.assertEqual(len(orders), 16)
        self.assertEqual(
            orders,
            tuple(
                fixed_size.PAIR_ROUTE_ORDERS[index % 3]
                for index in range(16)
            ),
        )
        self.assertEqual(
            fixed_size.classify(
                integrity=True,
                fixed_size=True,
                saved_work_law=True,
                speedup=fixed_size.MIN_FULL_LIFECYCLE_WALL_SPEEDUP,
                recursive_depth=16,
            ),
            "pinned-base-fixed-output-cuda-capsule-rebase-r16-supported-bounded",
        )

    def test_capsule_ids_support_preregistered_r16_without_changing_shape(self):
        self.assertEqual(
            fixed_size.child_root_id(16, "B"),
            "mb-runtime-water-04-fixed-capsule-r16-B",
        )
        with self.assertRaises(RuntimeError):
            fixed_size.child_root_id(-1, "B")

    def test_root_validator_binds_bank_and_storage_receipts(self):
        response = {
            "action": "root-save",
            "root_id": "child",
            "id_slot": 0,
            "id_slot_source": 0,
            "n_tokens": fixed_size.EXPECTED_CHILD_TOKENS,
            "n_bytes": fixed_size.EXPECTED_CHILD_DEVICE_BYTES + 100,
            "n_host_bytes": 100,
            "n_device_bytes": fixed_size.EXPECTED_CHILD_DEVICE_BYTES,
            "n_device_bytes_after": fixed_size.EXPECTED_CHILD_DEVICE_BYTES,
            "n_gpu_bytes": fixed_size.EXPECTED_CHILD_DEVICE_BYTES,
            "n_gpu_bytes_after": fixed_size.EXPECTED_CHILD_DEVICE_BYTES,
            "n_checkpoints": 0,
            "n_roots_after": 2,
            "n_roots_capacity": 2,
            "n_total_bytes_after": 160_000_000,
            "n_total_device_bytes_after": fixed_size.EXPECTED_CHILD_DEVICE_BYTES,
            "n_total_gpu_bytes_after": fixed_size.EXPECTED_CHILD_DEVICE_BYTES,
            "timings": {"root_ms": 1.0},
        }
        record = fixed_size.validate_root(
            response,
            action="root-save",
            root_id="child",
            storage="device",
            expected_tokens=fixed_size.EXPECTED_CHILD_TOKENS,
            expected_roots_after=2,
            expected_total_device_bytes_after=fixed_size.EXPECTED_CHILD_DEVICE_BYTES,
        )
        self.assertEqual(record["n_roots_after"], 2)
        broken = dict(response)
        broken["n_total_device_bytes_after"] = 0
        with self.assertRaises(RuntimeError):
            fixed_size.validate_root(
                broken,
                action="root-save",
                root_id="child",
                storage="device",
                expected_tokens=fixed_size.EXPECTED_CHILD_TOKENS,
                expected_roots_after=2,
                expected_total_device_bytes_after=fixed_size.EXPECTED_CHILD_DEVICE_BYTES,
            )

    def test_zero_output_paths_use_supported_terminal_evidence_kind(self):
        source = (SCRIPTS / "catalytic_frontier_fixed_size_rebase.py").read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            source.count('operation_kind="zero-output-root-readdress"'),
            2,
        )
        self.assertNotIn('operation_kind="fixed-output-capsule-rebase"', source)
        self.assertNotIn('operation_kind="zero-output-fixed-base-materialization"', source)


if __name__ == "__main__":
    unittest.main()
