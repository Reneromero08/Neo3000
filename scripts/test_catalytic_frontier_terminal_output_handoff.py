from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_terminal_output_handoff as handoff


def child_receipt(*, action: str, terminal_logits: bool = False) -> dict[str, object]:
    erased = action == "root-erase"
    device_bytes = handoff.EXPECTED_CHILD_DEVICE_BYTES
    return {
        "action": action,
        "root_id": "neo-exp-0085-child-pair-1",
        "id_slot": 0,
        "id_slot_source": 0,
        "device_storage_key": -1,
        "n_tokens": handoff.EXPECTED_CHILD_TOKENS,
        "n_bytes": device_bytes,
        "n_host_bytes": 0,
        "n_device_bytes": device_bytes,
        "n_device_bytes_after": 0 if erased else device_bytes,
        "n_gpu_bytes": device_bytes,
        "n_gpu_bytes_after": 0 if erased else device_bytes,
        "n_checkpoints": 0,
        "n_roots_after": 2 if erased else 3,
        "n_roots_capacity": 5,
        "n_total_bytes_after": (
            handoff.EXPECTED_TWO_ROOT_DEVICE_BYTES
            if erased
            else handoff.EXPECTED_THREE_ROOT_DEVICE_BYTES
        ),
        "n_total_device_bytes_after": (
            handoff.EXPECTED_TWO_ROOT_DEVICE_BYTES
            if erased
            else handoff.EXPECTED_THREE_ROOT_DEVICE_BYTES
        ),
        "n_total_gpu_bytes_after": (
            handoff.EXPECTED_TWO_ROOT_DEVICE_BYTES
            if erased
            else handoff.EXPECTED_THREE_ROOT_DEVICE_BYTES
        ),
        "has_terminal_logits": terminal_logits,
        "n_terminal_logits": 1 if terminal_logits else 0,
        "n_terminal_logits_bytes": 4 if terminal_logits else 0,
        "timings": {"root_ms": 1.0},
    }


class TerminalOutputHandoffTests(unittest.TestCase):
    def test_preregistered_geometry_and_identities_are_exact(self):
        self.assertEqual(handoff.WARMUP_PAIRS, 1)
        self.assertEqual(handoff.COUNTED_PAIRS, 4)
        self.assertEqual(
            handoff.PAIR_ORDERS,
            (
                ("catalytic", "direct"),
                ("direct", "catalytic"),
                ("catalytic", "direct"),
                ("direct", "catalytic"),
            ),
        )
        self.assertEqual(handoff.EXPECTED_TERMINAL_TOKENS, 690)
        self.assertEqual(handoff.EXPECTED_CHILD_TOKENS, 695)
        self.assertEqual(handoff.EXPECTED_SUCCESSOR_TOKENS, 782)
        self.assertEqual(handoff.EXPECTED_SUCCESSOR_FRESH_TOKENS, 87)
        self.assertEqual(
            handoff.EXPECTED_BRANCH_TOKEN_SHA256,
            "A454640FCAE18925F9A4B54672C0A1F681721E9CF72BC19220C940E64B629B12",
        )
        self.assertEqual(
            handoff.EXPECTED_THREE_ROOT_DEVICE_BYTES,
            240_066_560,
        )
        self.assertEqual(handoff.MIN_HANDOFF_LIFECYCLE_SPEEDUP, 1.25)
        self.assertEqual(handoff.MIN_PAIR_DOMINANCE, 0.75)

    def test_child_receipt_requires_no_terminal_logits_and_preserves_evidence(self):
        receipt = child_receipt(action="root-save")
        with mock.patch.object(
            handoff.harness,
            "ram_root_action",
            return_value=(receipt, 0.25),
        ):
            record = handoff.child_root_action(
                action="root-save",
                root_id="neo-exp-0085-child-pair-1",
                expected_roots_after=3,
                expected_total_device_bytes_after=handoff.EXPECTED_THREE_ROOT_DEVICE_BYTES,
            )
        self.assertFalse(record["has_terminal_logits"])
        self.assertEqual(record["n_terminal_logits"], 0)
        self.assertEqual(record["n_terminal_logits_bytes"], 0)
        self.assertEqual(record["client_wall_seconds"], 0.25)

        with mock.patch.object(
            handoff.harness,
            "ram_root_action",
            return_value=(child_receipt(action="root-save", terminal_logits=True), 0.25),
        ):
            with self.assertRaises(handoff.ExperimentError):
                handoff.child_root_action(
                    action="root-save",
                    root_id="neo-exp-0085-child-pair-1",
                    expected_roots_after=3,
                    expected_total_device_bytes_after=handoff.EXPECTED_THREE_ROOT_DEVICE_BYTES,
                )

    def test_seed_restores_the_0085_terminal_root(self):
        terminal_saved = {"terminal_logits_fnv64": "1" * 16}
        generated_state = {
            "answer": "C",
            "generated_token_sha256": handoff.EXPECTED_SEED_GENERATED_SHA256,
        }
        run_record = {
            "wall_seconds": 1.0,
            "prompt_tokens": handoff.EXPECTED_TERMINAL_TOKENS,
            "cached_prompt_tokens": handoff.EXPECTED_TERMINAL_TOKENS,
            "fresh_prompt_tokens": 0,
        }
        with (
            mock.patch.object(
                handoff,
                "terminal_root_action",
                return_value=({"root_id": handoff.TERMINAL_ROOT_ID}, 0.1),
            ) as restore,
            mock.patch.object(
                handoff.terminal,
                "completion_payload",
                return_value={},
            ),
            mock.patch.object(
                handoff.harness,
                "run_completion",
                return_value=run_record,
            ),
            mock.patch.object(
                handoff.latency.TimingRecorder,
                "summary",
                return_value={"server_prompt_n": 0},
            ),
            mock.patch.object(
                handoff.fixed,
                "generated_state",
                return_value=generated_state,
            ),
            mock.patch.object(
                handoff.rebase,
                "compact_child_tokens",
                return_value=[0] * handoff.EXPECTED_CHILD_TOKENS,
            ),
            mock.patch.object(
                handoff,
                "canonical_sha256",
                side_effect=lambda value: (
                    handoff.EXPECTED_CHILD_TOKEN_SHA256
                    if len(value) == handoff.EXPECTED_CHILD_TOKENS
                    else "unused"
                ),
            ),
        ):
            record, state, child = handoff.run_seed(
                sidecar=object(),
                codec=object(),
                props={},
                branch_tokens=[0] * handoff.EXPECTED_TERMINAL_TOKENS,
                terminal_saved=terminal_saved,
                label="pair-1",
            )
        self.assertEqual(
            restore.call_args.kwargs["root_id"],
            handoff.TERMINAL_ROOT_ID,
        )
        self.assertEqual(record["restore"]["root_id"], handoff.TERMINAL_ROOT_ID)
        self.assertEqual(state["answer"], "C")
        self.assertEqual(len(child), handoff.EXPECTED_CHILD_TOKENS)

    def test_pair_charges_child_save_and_erase_and_samples_live_three_root_state(self):
        child_tokens = [0] * handoff.EXPECTED_CHILD_TOKENS
        seed_state = {"answer": "C"}
        root_records = [
            {
                "root_id": "neo-exp-0085-child-pair-1",
                "client_wall_seconds": 0.25,
            },
            {
                "root_id": "neo-exp-0085-child-pair-1",
                "client_wall_seconds": 0.25,
            },
        ]

        def successor(**kwargs):
            route = kwargs["route"]
            return {
                "input_token_sha256": handoff.EXPECTED_SUCCESSOR_REQUEST_SHA256,
                "state": {"generated_token_ids": [1, 2]},
                "effective_wall_seconds": 1.0 if route == "catalytic" else 5.0,
                "fresh_prompt_tokens": (
                    handoff.EXPECTED_SUCCESSOR_FRESH_TOKENS
                    if route == "catalytic"
                    else handoff.EXPECTED_SUCCESSOR_TOKENS
                ),
            }

        with (
            mock.patch.object(
                handoff,
                "run_seed",
                return_value=({"cached_prompt_tokens": 690}, seed_state, child_tokens),
            ),
            mock.patch.object(
                handoff,
                "child_root_action",
                side_effect=root_records,
            ),
            mock.patch.object(
                handoff,
                "run_successor",
                side_effect=successor,
            ),
            mock.patch.object(
                handoff.harness,
                "process_resources",
                return_value={"peak_wddm_bytes": 123},
            ) as resources,
        ):
            pair = handoff.run_pair(
                sidecar=object(),
                codec=object(),
                props={},
                branch_tokens=[0] * handoff.EXPECTED_TERMINAL_TOKENS,
                terminal_saved={},
                pair_label="pair-1",
                route_order=("catalytic", "direct"),
                contract=mock.Mock(),
                baseline_private=7,
            )
        resources.assert_called_once()
        self.assertEqual(
            pair["catalytic_handoff_lifecycle_seconds"],
            1.5,
        )
        self.assertEqual(pair["direct_materialized_lifecycle_seconds"], 5.0)
        self.assertTrue(pair["catalytic_won"])
        self.assertEqual(pair["avoided_fresh_prompt_tokens"], 695)
        self.assertEqual(pair["resources_with_child"]["peak_wddm_bytes"], 123)

    def test_consumption_marker_is_exclusive_and_forbids_retry_or_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "consumed.json"
            handoff.create_consumed_marker(marker, "a" * 40)
            value = json.loads(marker.read_text(encoding="utf-8"))
            self.assertFalse(value["retry_allowed"])
            self.assertFalse(value["automatic_promotion"])
            with self.assertRaises(Exception):
                handoff.create_consumed_marker(marker, "a" * 40)

    def test_controller_composes_existing_primitives_without_server_changes(self):
        source = Path(handoff.__file__).read_text(encoding="utf-8")
        self.assertNotIn("terminal.run_route(", source)
        self.assertNotIn("terminal.task_and_branch(", source)
        self.assertIn("neo3000_use_terminal_logits=True", source)
        self.assertIn("rolling.derive_promoted_successor(", source)
        self.assertIn("operation_kind=\"zero-output-root-readdress\"", source)
        self.assertIn("child accidentally retained terminal logits", source)


if __name__ == "__main__":
    unittest.main()
