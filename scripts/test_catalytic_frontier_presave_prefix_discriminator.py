#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalytic_frontier_harness as harness
import catalytic_frontier_presave_prefix_discriminator as discriminator
import catalytic_frontier_ram_root as ram_root


class CatalyticFrontierPresavePrefixDiscriminatorTests(unittest.TestCase):
    def checkpoint_sidecar(self) -> discriminator.ScopedCheckpointDiscoverySidecar:
        sidecar = object.__new__(discriminator.ScopedCheckpointDiscoverySidecar)
        sidecar.context_checkpoints = 0
        return sidecar

    def test_checkpoint_override_is_zero_during_launch_and_restored_on_success(self) -> None:
        observed: list[int] = []

        def parent_launch(_sidecar: object) -> dict[str, object]:
            observed.append(harness.live_runtime.CTX_CHECKPOINTS)
            return {"pid": 7}

        sidecar = self.checkpoint_sidecar()
        with (
            mock.patch.object(harness.live_runtime, "CTX_CHECKPOINTS", 8),
            mock.patch.object(
                harness.DiscoverySidecar,
                "launch",
                autospec=True,
                side_effect=parent_launch,
            ),
        ):
            readiness = sidecar.launch()
            self.assertEqual(harness.live_runtime.CTX_CHECKPOINTS, 8)

        self.assertEqual(observed, [0])
        self.assertEqual(readiness["pid"], 7)
        self.assertEqual(readiness["launch_configuration"]["context_checkpoints"], 0)
        self.assertTrue(readiness["launch_configuration"]["global_restored_after_launch"])

    def test_checkpoint_override_restores_global_when_launch_fails(self) -> None:
        observed: list[int] = []

        def parent_launch(_sidecar: object) -> dict[str, object]:
            observed.append(harness.live_runtime.CTX_CHECKPOINTS)
            raise RuntimeError("synthetic launch failure")

        sidecar = self.checkpoint_sidecar()
        with mock.patch.object(harness.live_runtime, "CTX_CHECKPOINTS", 8):
            with mock.patch.object(
                harness.DiscoverySidecar,
                "launch",
                autospec=True,
                side_effect=parent_launch,
            ), self.assertRaisesRegex(RuntimeError, "synthetic launch failure"):
                sidecar.launch()
            self.assertEqual(harness.live_runtime.CTX_CHECKPOINTS, 8)

        self.assertEqual(observed, [0])

    def test_exact_presave_prefix_equivalence(self) -> None:
        self.assertEqual(
            discriminator.classify_presave_routes(
                expected="B",
                presave="B",
                direct="B",
                generated_equal=True,
            ),
            "exact-presave-prefix-equivalence",
        )

    def test_generated_token_divergence_rejects_equal_answers(self) -> None:
        self.assertEqual(
            discriminator.classify_presave_routes(
                expected="B",
                presave="B",
                direct="B",
                generated_equal=False,
            ),
            "generated-token-divergence",
        )

    def test_direct_control_failure_has_precedence(self) -> None:
        self.assertEqual(
            discriminator.classify_presave_routes(
                expected="B",
                presave="D",
                direct="D",
                generated_equal=True,
            ),
            "direct-control-utility-failure",
        )

    def test_presave_materialized_prefix_divergence(self) -> None:
        self.assertEqual(
            discriminator.classify_presave_routes(
                expected="B",
                presave="D",
                direct="B",
                generated_equal=False,
            ),
            "pre-save-materialized-prefix-divergence",
        )

    def test_tick_and_boundaries_reuse_the_frozen_tick11_contract(self) -> None:
        self.assertEqual(discriminator.DEFAULT_TICK, 11)
        self.assertEqual(discriminator.ROOT_ID, "frontier-phase-rotor-infinite-01")

    def test_evaluate_contacts_no_root_endpoint_and_accounts_exact_protocol(self) -> None:
        def completion(*, cached: int, fresh: int, completion_tokens: int, wall: float) -> dict[str, object]:
            return {
                "content": "{}",
                "prompt_tokens": cached + fresh,
                "cached_prompt_tokens": cached,
                "fresh_prompt_tokens": fresh,
                "completion_tokens": completion_tokens,
                "fresh_model_tokens": fresh + completion_tokens,
                "wall_seconds": wall,
                "execution": {"generated_token_sha256": "A" * 64},
            }

        def route_record(*, cached: int, fresh: int) -> dict[str, object]:
            return {
                **completion(cached=cached, fresh=fresh, completion_tokens=6, wall=1.0),
                "answer": "B",
                "expected": "B",
                "correct": True,
                "input_token_sha256": "F" * 64,
            }

        codec = mock.Mock()
        codec.render_messages.return_value = "rendered"
        codec.tokenize.return_value = list(range(270))
        task_a = completion(cached=0, fresh=270, completion_tokens=16, wall=2.0)
        materialization = completion(cached=0, fresh=270, completion_tokens=0, wall=1.5)
        completions = iter((task_a, materialization))
        branches = iter((
            route_record(cached=270, fresh=100),
            route_record(cached=0, fresh=370),
        ))
        retained = {
            "retained_root_token_count": 285,
            "retained_root_tokens": list(range(285)),
            "terminal_stop_identity": {"token_id": 1},
        }
        events: list[str] = []

        def run_completion(*args: object, **kwargs: object) -> dict[str, object]:
            operation = kwargs.get("operation_kind")
            events.append(
                f"completion:{operation}" if operation is not None else "completion:task-a"
            )
            return next(completions)

        def run_branch(**kwargs: object) -> dict[str, object]:
            events.append(f"branch:{kwargs['route']}")
            return next(branches)

        with (
            mock.patch.object(harness.carrier, "task_a_messages", return_value=[]),
            mock.patch.object(harness, "run_completion", side_effect=run_completion),
            mock.patch.object(harness.carrier, "parse_task_a_output", return_value={"answer": "B"}),
            mock.patch.object(harness, "root_capture", return_value={}),
            mock.patch.object(harness.carrier, "derive_retained_root", return_value=retained),
            mock.patch.object(
                harness,
                "ram_root_action",
                side_effect=AssertionError("no-root controller contacted a root endpoint"),
            ) as root_action,
            mock.patch.object(ram_root, "run_branch", side_effect=run_branch) as branch_action,
            mock.patch.object(
                harness,
                "process_resources",
                side_effect=[{"sample": "after-materialization"}, {"sample": "after-routes"}],
            ),
        ):
            result = discriminator.evaluate(
                sidecar=mock.Mock(),
                codec=codec,
                props={},
                baseline_private=1,
                tick=11,
            )

        root_action.assert_not_called()
        self.assertEqual(
            events,
            [
                "completion:task-a",
                "completion:zero-output-root-readdress",
                "branch:pre-save-live",
                "branch:fresh-direct",
            ],
        )
        self.assertEqual(
            [call.kwargs["route"] for call in branch_action.call_args_list],
            ["pre-save-live", "fresh-direct"],
        )
        self.assertEqual(
            [call.kwargs["cache_prompt"] for call in branch_action.call_args_list],
            [True, False],
        )
        self.assertTrue(all(call.kwargs["tick"] == 11 for call in branch_action.call_args_list))
        self.assertEqual(result["classification"], "exact-presave-prefix-equivalence")
        self.assertEqual(result["verdict"], "accept")
        self.assertFalse(result["root_endpoint_contacted"])
        self.assertEqual(result["ram_root_operations"]["total"], 0)
        self.assertEqual(result["fresh_model_compute"]["task_a"], 286)
        self.assertEqual(result["fresh_model_compute"]["prompt_root_materialization"], 270)
        self.assertEqual(result["fresh_model_compute"]["both_routes"], 482)
        self.assertEqual(result["fresh_model_compute"]["total_measured_run"], 1_038)
        self.assertAlmostEqual(result["wall_seconds"]["accounted_request_operations"], 5.5)
        self.assertEqual(
            result["resources_after_materialization"],
            {"sample": "after-materialization"},
        )
        self.assertEqual(result["resources_after_routes"], {"sample": "after-routes"})


if __name__ == "__main__":
    unittest.main()
