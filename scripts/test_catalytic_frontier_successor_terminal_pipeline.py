from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_successor_terminal_pipeline as pipeline


def root_receipt(
    *,
    action: str,
    root_id: str,
    n_tokens: int,
    n_device_bytes: int,
    terminal_logits: bool,
    n_roots_after: int,
    total_device_bytes_after: int,
) -> dict[str, object]:
    erased = action == "root-erase"
    n_logits = pipeline.EXPECTED_TERMINAL_LOGITS if terminal_logits else 0
    logits_bytes = pipeline.EXPECTED_TERMINAL_LOGITS_BYTES if terminal_logits else 0
    host_bytes = 20_000 + logits_bytes
    return {
        "action": action,
        "root_id": root_id,
        "id_slot": 0,
        "id_slot_source": 0,
        "device_storage_key": -1,
        "n_tokens": n_tokens,
        "n_bytes": n_device_bytes + host_bytes,
        "n_host_bytes": host_bytes,
        "n_device_bytes": n_device_bytes,
        "n_device_bytes_after": 0 if erased else n_device_bytes,
        "n_gpu_bytes": n_device_bytes,
        "n_gpu_bytes_after": 0 if erased else n_device_bytes,
        "n_checkpoints": 0,
        "n_roots_after": n_roots_after,
        "n_roots_capacity": 5,
        "n_total_bytes_after": total_device_bytes_after + 20_000,
        "n_total_device_bytes_after": total_device_bytes_after,
        "n_total_gpu_bytes_after": total_device_bytes_after,
        "has_terminal_logits": terminal_logits,
        "n_terminal_logits": n_logits,
        "n_terminal_logits_bytes": logits_bytes,
        "terminal_logits_fnv64": "1" * 16 if terminal_logits else "",
        "terminal_prompt_fnv64": "2" * 16 if terminal_logits else "",
        "terminal_sampler_fnv64": "3" * 16 if terminal_logits else "",
        "terminal_position": n_tokens - 1 if terminal_logits else -1,
        "timings": {"root_ms": 1.0},
    }


class SuccessorTerminalPipelineTests(unittest.TestCase):
    def test_preregistered_r2_geometry_and_controls_are_exact(self):
        self.assertEqual(pipeline.EXPECTED_STATES, ("C", "D", "B"))
        self.assertEqual(
            pipeline.ROUTES,
            ("terminal", "root-only", "materialized"),
        )
        self.assertEqual(pipeline.WARMUP_TRIALS, 1)
        self.assertEqual(pipeline.COUNTED_TRIALS, 3)
        self.assertEqual(
            pipeline.TRIAL_ROUTE_ORDERS,
            (
                ("terminal", "root-only", "materialized"),
                ("root-only", "materialized", "terminal"),
                ("materialized", "terminal", "root-only"),
            ),
        )
        self.assertEqual(pipeline.EXPECTED_SUCCESSOR_TOKENS, 782)
        self.assertEqual(pipeline.EXPECTED_SUCCESSOR_FRESH_TOKENS, 87)
        self.assertEqual(pipeline.EXPECTED_REBASE_FRESH_TOKENS, 6)
        self.assertEqual(pipeline.EXPECTED_AVOIDED_PER_EDGE, 689)
        self.assertEqual(pipeline.EXPECTED_AVOIDED_PER_TRIAL, 1378)
        self.assertEqual(
            pipeline.EXPECTED_MAX_PIPELINE_DEVICE_BYTES,
            241_950_720,
        )

    def test_exact_absorbing_request_and_output_identities_are_frozen(self):
        self.assertEqual(
            pipeline.EXPECTED_REQUEST_SHA256,
            {
                "C": "5F80CECB28FC4336A9630C092A215F75C52EFFE03EBB8CECAE6D63832341B962",
                "D": "D7ACDEE41EDF7366F98154246E17A54CD13D4DB1830FB295CF8E02DB10D87862",
            },
        )
        self.assertEqual(
            pipeline.EXPECTED_CHILD_SHA256["D"],
            "5AC4DD8C73E3D4958F9A93C3A9D78B05C0C6C4E6D17A06DA7CF8C72E10FA495B",
        )
        self.assertEqual(
            pipeline.EXPECTED_CHILD_SHA256["B"],
            "D636ABA44A0F7DA74C1CA03CD2D0B064D6A2469FA6EBB0BC8F42A0CE9426DEB8",
        )
        self.assertEqual(
            pipeline.EXPECTED_GENERATED_SHA256["D"],
            "0CA13167369ED1835BB8938644A7CCEF6EDE0BD65AE31C256931C54D3FA9FB31",
        )
        self.assertEqual(
            pipeline.EXPECTED_GENERATED_SHA256["B"],
            "4553BBC00B6AF27C3EBDE8F36EA9237A37B5D9C1AA182FBC65CDA71411A4B888",
        )

    def test_generalized_terminal_validator_accepts_position_781(self):
        receipt = root_receipt(
            action="root-save",
            root_id="successor-terminal",
            n_tokens=pipeline.EXPECTED_SUCCESSOR_TOKENS,
            n_device_bytes=pipeline.EXPECTED_SUCCESSOR_TERMINAL_DEVICE_BYTES,
            terminal_logits=True,
            n_roots_after=3,
            total_device_bytes_after=pipeline.EXPECTED_MAX_PIPELINE_DEVICE_BYTES,
        )
        record = pipeline.validate_device_root(
            receipt,
            action="root-save",
            root_id="successor-terminal",
            n_tokens=pipeline.EXPECTED_SUCCESSOR_TOKENS,
            n_device_bytes=pipeline.EXPECTED_SUCCESSOR_TERMINAL_DEVICE_BYTES,
            terminal_logits=True,
            expected_roots_after=3,
            expected_total_device_bytes_after=pipeline.EXPECTED_MAX_PIPELINE_DEVICE_BYTES,
        )
        self.assertEqual(record["terminal_position"], 781)
        self.assertEqual(
            record["n_terminal_logits_bytes"],
            pipeline.EXPECTED_TERMINAL_LOGITS_BYTES,
        )

        broken = dict(receipt)
        broken["terminal_position"] = 689
        with self.assertRaises(pipeline.ExperimentError):
            pipeline.validate_device_root(
                broken,
                action="root-save",
                root_id="successor-terminal",
                n_tokens=pipeline.EXPECTED_SUCCESSOR_TOKENS,
                n_device_bytes=pipeline.EXPECTED_SUCCESSOR_TERMINAL_DEVICE_BYTES,
                terminal_logits=True,
                expected_roots_after=3,
                expected_total_device_bytes_after=pipeline.EXPECTED_MAX_PIPELINE_DEVICE_BYTES,
            )

    def test_nonterminal_child_validator_rejects_terminal_logits(self):
        receipt = root_receipt(
            action="root-save",
            root_id="child",
            n_tokens=pipeline.EXPECTED_CHILD_TOKENS,
            n_device_bytes=pipeline.EXPECTED_CHILD_DEVICE_BYTES,
            terminal_logits=False,
            n_roots_after=2,
            total_device_bytes_after=pipeline.EXPECTED_BASE_CHILD_DEVICE_BYTES,
        )
        pipeline.validate_device_root(
            receipt,
            action="root-save",
            root_id="child",
            n_tokens=pipeline.EXPECTED_CHILD_TOKENS,
            n_device_bytes=pipeline.EXPECTED_CHILD_DEVICE_BYTES,
            terminal_logits=False,
            expected_roots_after=2,
            expected_total_device_bytes_after=pipeline.EXPECTED_BASE_CHILD_DEVICE_BYTES,
        )
        broken = dict(receipt)
        broken.update(
            has_terminal_logits=True,
            n_terminal_logits=pipeline.EXPECTED_TERMINAL_LOGITS,
            n_terminal_logits_bytes=pipeline.EXPECTED_TERMINAL_LOGITS_BYTES,
        )
        with self.assertRaises(pipeline.ExperimentError):
            pipeline.validate_device_root(
                broken,
                action="root-save",
                root_id="child",
                n_tokens=pipeline.EXPECTED_CHILD_TOKENS,
                n_device_bytes=pipeline.EXPECTED_CHILD_DEVICE_BYTES,
                terminal_logits=False,
                expected_roots_after=2,
                expected_total_device_bytes_after=pipeline.EXPECTED_BASE_CHILD_DEVICE_BYTES,
            )

    def test_root_ids_depend_on_trial_route_and_edge_not_answer(self):
        self.assertEqual(
            pipeline.terminal_root_id("trial-1-terminal", 1),
            "neo-exp-0086-trial-1-terminal-terminal-edge-1",
        )
        self.assertEqual(
            pipeline.child_root_id("trial-1-root-only", "root-only", 2),
            "neo-exp-0086-trial-1-root-only-root-only-child-2",
        )
        self.assertNotIn(
            "answer",
            pipeline.terminal_root_id("trial-1-terminal", 2),
        )
        with self.assertRaises(pipeline.ExperimentError):
            pipeline.terminal_root_id("trial", 3)

    def test_route_dispatch_strips_terminal_only_arguments_from_controls(self):
        common = {
            "sidecar": object(),
            "codec": object(),
            "props": {},
            "base_root": {},
            "branch_tokens": [],
            "seed_state": {},
            "trial_label": "trial",
            "baseline_private": 1,
            "run_successor_negative": False,
        }
        with (
            mock.patch.object(
                pipeline,
                "run_terminal_sequence",
                return_value={"route": "terminal"},
            ) as terminal_route,
            mock.patch.object(
                pipeline,
                "run_root_only_sequence",
                return_value={"route": "root-only"},
            ) as root_route,
            mock.patch.object(
                pipeline,
                "run_materialized_sequence",
                return_value={"route": "materialized"},
            ) as direct_route,
        ):
            pipeline.run_sequence("terminal", **common)
            pipeline.run_sequence("root-only", **common)
            pipeline.run_sequence("materialized", **common)
        self.assertIn("baseline_private", terminal_route.call_args.kwargs)
        self.assertNotIn("baseline_private", root_route.call_args.kwargs)
        self.assertNotIn("run_successor_negative", root_route.call_args.kwargs)
        self.assertNotIn("base_root", direct_route.call_args.kwargs)

    def test_source_separates_ttft_from_fully_charged_compute(self):
        source = Path(pipeline.__file__).read_text(encoding="utf-8")
        self.assertIn("consumer_ttft_speedup_at_least_5", source)
        self.assertIn(
            "terminal_vs_root_only_fully_charged_ratio_at_least_0_80",
            source,
        )
        self.assertIn(
            "terminal_vs_materialized_fully_charged_speedup_at_least_2_5",
            source,
        )
        self.assertIn("Terminal capture moves 87-token evaluation", source)
        self.assertIn("one_consumer_per_unique_terminal_root", source)
        self.assertIn("cache_prompt=False", source)
        self.assertIn("neo3000_capture_terminal_logits", source)
        self.assertIn("neo3000_use_terminal_logits", source)
        self.assertEqual(source.count('float(timing["ttft_seconds"])'), 3)
        self.assertNotIn('timing["first_event_seconds"]', source)
        self.assertNotIn('"observed_states": list(EXPECTED_STATES)', source)
        self.assertIn('edge_record["consumer"]["state"]["answer"]', source)
        self.assertIn('edge_record["successor"]["state"]["answer"]', source)


if __name__ == "__main__":
    unittest.main()
