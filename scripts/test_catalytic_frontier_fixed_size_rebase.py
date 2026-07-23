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


if __name__ == "__main__":
    unittest.main()
