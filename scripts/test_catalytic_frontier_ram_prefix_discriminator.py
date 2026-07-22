#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalytic_frontier_harness as harness
import catalytic_frontier_ram_root as ram_root
import catalytic_frontier_ram_prefix_discriminator as discriminator


class CatalyticFrontierRamPrefixDiscriminatorTests(unittest.TestCase):
    def classify(self, live: str, restored: str, direct: str, replay: str) -> str:
        return discriminator.classify_prefix_routes(
            expected="B",
            live=live,
            restored=restored,
            direct=direct,
            replay=replay,
        )

    def test_exact_live_restore_replay_equivalence(self) -> None:
        self.assertEqual(
            self.classify("B", "B", "B", "B"),
            "exact-live-restore-replay-equivalence",
        )

    def test_equal_answers_still_reject_generated_token_divergence(self) -> None:
        self.assertEqual(
            discriminator.classify_prefix_routes(
                expected="B",
                live="B",
                restored="B",
                direct="B",
                replay="B",
                generated_equal=False,
            ),
            "generated-token-divergence",
        )

    def test_direct_control_failure_has_precedence(self) -> None:
        self.assertEqual(
            self.classify("D", "D", "D", "D"),
            "direct-control-utility-failure",
        )

    def test_live_prompt_prefix_divergence(self) -> None:
        self.assertEqual(
            self.classify("D", "D", "B", "D"),
            "live-prompt-prefix-divergence",
        )

    def test_serialization_restore_divergence(self) -> None:
        self.assertEqual(
            self.classify("B", "D", "B", "D"),
            "serialization-restore-divergence",
        )

    def test_repeated_use_or_replay_divergence(self) -> None:
        self.assertEqual(
            self.classify("B", "B", "B", "D"),
            "repeated-use-or-replay-divergence",
        )

    def test_restore_repeatability_divergence(self) -> None:
        self.assertEqual(
            self.classify("D", "D", "B", "C"),
            "restore-repeatability-divergence",
        )

    def test_mixed_cached_route_divergence(self) -> None:
        self.assertEqual(
            self.classify("D", "C", "B", "C"),
            "mixed-cached-route-divergence",
        )

    def test_default_tick_is_the_n16_carrier_split(self) -> None:
        self.assertEqual(discriminator.DEFAULT_TICK, 11)

    def test_frozen_boundary_rejects_tick_and_token_drift(self) -> None:
        discriminator.validate_frozen_boundary(tick=11, root_count=270, retained_count=285)
        for values in (
            {"tick": 10, "root_count": 270, "retained_count": 285},
            {"tick": 11, "root_count": 271, "retained_count": 286},
            {"tick": 11, "root_count": 270, "retained_count": 286},
        ):
            with self.subTest(values=values), self.assertRaises(harness.FrontierHarnessError):
                discriminator.validate_frozen_boundary(**values)

    def test_restored_root_rejects_slot_metadata_drift(self) -> None:
        base = {
            "root_id": discriminator.ROOT_ID,
            "id_slot": 0,
            "id_slot_source": 0,
            "n_tokens": 270,
            "n_bytes": 137_265_192,
            "n_checkpoints": 1,
            "timings": {"root_ms": 20.0},
        }
        saved = ram_root.validate_root_response(
            {**base, "action": "root-save"},
            action="root-save",
        )
        drifted = {**base, "action": "root-restore", "id_slot_source": 1}
        with self.assertRaises(harness.FrontierHarnessError):
            discriminator.validate_restored_root(drifted, saved=saved)

    def test_evaluate_executes_frozen_route_restore_erase_protocol(self) -> None:
        def root_response(action: str) -> dict[str, object]:
            return {
                "action": action,
                "root_id": discriminator.ROOT_ID,
                "id_slot": 0,
                "id_slot_source": 0,
                "n_tokens": 270,
                "n_bytes": 137_265_192,
                "n_checkpoints": 1,
                "timings": {"root_ms": 20.0},
            }

        def completion(*, cached: int, fresh: int, completion: int, wall: float) -> dict[str, object]:
            return {
                "content": "{}",
                "prompt_tokens": cached + fresh,
                "cached_prompt_tokens": cached,
                "fresh_prompt_tokens": fresh,
                "completion_tokens": completion,
                "fresh_model_tokens": fresh + completion,
                "wall_seconds": wall,
                "execution": {"generated_token_sha256": "A" * 64},
            }

        def route_record(*, cached: int, fresh: int) -> dict[str, object]:
            return {
                **completion(cached=cached, fresh=fresh, completion=6, wall=1.0),
                "answer": "B",
                "expected": "B",
                "correct": True,
                "input_token_sha256": "F" * 64,
            }

        codec = mock.Mock()
        codec.render_messages.return_value = "rendered"
        codec.tokenize.return_value = list(range(270))
        task_a = completion(cached=0, fresh=270, completion=16, wall=2.0)
        materialization = completion(cached=0, fresh=270, completion=0, wall=1.5)
        ram_actions = [
            (root_response("root-save"), 0.01),
            *((root_response("root-restore"), 0.02) for _ in range(4)),
            (root_response("root-erase"), 0.01),
        ]
        branches = [
            route_record(cached=270, fresh=99),
            route_record(cached=270, fresh=99),
            route_record(cached=0, fresh=369),
            route_record(cached=270, fresh=99),
        ]
        events: list[str] = []
        ram_action_iter = iter(ram_actions)

        def run_root_action(*, action: str, root_id: str) -> tuple[dict[str, object], float]:
            self.assertEqual(root_id, discriminator.ROOT_ID)
            events.append(action)
            return next(ram_action_iter)

        branch_iter = iter(branches)

        def run_route(**kwargs: object) -> dict[str, object]:
            events.append(f"branch:{kwargs['route']}")
            return next(branch_iter)

        retained = {
            "retained_root_token_count": 285,
            "retained_root_tokens": list(range(285)),
            "terminal_stop_identity": {"token_id": 1},
        }
        with (
            mock.patch.object(harness.carrier, "task_a_messages", return_value=[]),
            mock.patch.object(harness, "run_completion", side_effect=[task_a, materialization]),
            mock.patch.object(harness.carrier, "parse_task_a_output", return_value={"answer": "B"}),
            mock.patch.object(harness, "root_capture", return_value={}),
            mock.patch.object(harness.carrier, "derive_retained_root", return_value=retained),
            mock.patch.object(harness, "ram_root_action", side_effect=run_root_action) as root_action,
            mock.patch.object(ram_root, "run_branch", side_effect=run_route) as run_branch,
            mock.patch.object(harness, "process_resources", side_effect=[{"sample": 1}, {"sample": 2}]),
        ):
            result = discriminator.evaluate(
                sidecar=mock.Mock(),
                codec=codec,
                props={},
                baseline_private=1,
                tick=11,
            )

        self.assertEqual(
            [call.kwargs["route"] for call in run_branch.call_args_list],
            ["untouched-live", "restored", "fresh-direct", "restored-replay"],
        )
        self.assertEqual(
            [call.kwargs["cache_prompt"] for call in run_branch.call_args_list],
            [True, True, False, True],
        )
        self.assertTrue(all(call.kwargs["tick"] == 11 for call in run_branch.call_args_list))
        self.assertEqual(
            [call.kwargs["action"] for call in root_action.call_args_list],
            ["root-save", "root-restore", "root-restore", "root-restore", "root-restore", "root-erase"],
        )
        self.assertEqual(
            events,
            [
                "root-save",
                "branch:untouched-live",
                "root-restore",
                "branch:restored",
                "root-restore",
                "branch:fresh-direct",
                "root-restore",
                "branch:restored-replay",
                "root-restore",
                "root-erase",
            ],
        )
        self.assertEqual(result["carrier"]["restore_count"], 4)
        self.assertTrue(result["carrier"]["final_restore_before_erase"])
        self.assertTrue(result["carrier"]["response_metadata_invariant"])
        self.assertEqual(result["classification"], "exact-live-restore-replay-equivalence")
        self.assertEqual(result["verdict"], "accept")
        self.assertEqual(result["fresh_model_compute"]["total_measured_run"], 1_246)
        self.assertAlmostEqual(result["wall_seconds"]["accounted_request_and_root_operations"], 7.6)


if __name__ == "__main__":
    unittest.main()
