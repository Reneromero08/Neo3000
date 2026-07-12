#!/usr/bin/env python3
"""CPU-only controller checks for the CS1-v3 active-version path repair."""

from __future__ import annotations

import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import holostate_live as holo
from catalytic_swarm_advantage import _parse_transport
from catalytic_swarm_1_v2_protocol import build_catalytic_swarm_1_v2_contract
from catalytic_swarm_1_v3_namespace import VersionedPathLawError, qualify_versioned_one_shot_paths
from catalytic_swarm_1_v3_protocol import build_catalytic_swarm_1_v3_contract


ROOT = Path(__file__).resolve().parents[1]


class CatalyticSwarm1V3ControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.v2 = build_catalytic_swarm_1_v2_contract()
        self.v3 = build_catalytic_swarm_1_v3_contract(self.v2)

    def test_inherited_v1_comparison_reproduces_consumed_v2_failure(self) -> None:
        with self.assertRaisesRegex(holo.NeoLoopError, "one-shot path law changed"):
            holo.qualify_catalytic_swarm_1_control(
                holo.load_json(ROOT / "lab" / "EVALUATOR.json")["catalytic_swarm_1"],
                contract_paths=holo.CATALYTIC_SWARM_1_ONE_SHOT_PATHS,
                active_artifact_paths=holo.CATALYTIC_SWARM_1_V2_ARTIFACT_PATHS,
                required_namespace="state/catalytic_swarm_1",
            )

    def test_historical_v3_path_qualification_does_not_mutate_consumed_evidence(self) -> None:
        before = tuple(path.exists() for path in holo.CATALYTIC_SWARM_1_V3_ARTIFACT_PATHS)
        base = holo.load_json(ROOT / "lab" / "EVALUATOR.json")["catalytic_swarm_1"]
        with holo.catalytic_swarm_1_v3_runtime_namespace(self.v3):
            result = holo.qualify_active_catalytic_swarm_1_control(base)
        self.assertTrue(result["passed"])
        self.assertFalse(result["generation_executed"])
        self.assertEqual(before, (True, False, False, False, False, False, False))
        self.assertEqual(
            before,
            tuple(path.exists() for path in holo.CATALYTIC_SWARM_1_V3_ARTIFACT_PATHS),
        )

    def test_live_control_requalification_cannot_fall_back_to_v1_paths(self) -> None:
        base = holo.load_json(ROOT / "lab" / "EVALUATOR.json")["catalytic_swarm_1"]
        with holo.catalytic_swarm_1_v3_runtime_namespace(self.v3), mock.patch.object(
            holo,
            "qualify_catalytic_swarm_1_control",
            return_value={"passed": True},
        ) as qualify:
            holo.qualify_active_catalytic_swarm_1_control(
                base, stable_tokenizer=True
            )
        kwargs = qualify.call_args.kwargs
        self.assertTrue(kwargs["stable_tokenizer"])
        self.assertEqual(kwargs["contract_paths"], self.v3["one_shot"]["paths"])
        self.assertEqual(kwargs["required_namespace"], "state/catalytic_swarm_1_v3")
        self.assertEqual(
            tuple(kwargs["active_artifact_paths"]),
            holo.CATALYTIC_SWARM_1_V3_ARTIFACT_PATHS,
        )

    def test_v3_runner_is_a_consumed_tombstone(self) -> None:
        with mock.patch.object(holo, "LiveSidecar") as sidecar:
            with self.assertRaisesRegex(holo.NeoLoopError, "consumed / no retry"):
                holo.run_catalytic_swarm_1_v3_audit(object())
        sidecar.assert_not_called()

    def test_v3_public_handler_is_retired_before_runtime(self) -> None:
        with mock.patch.object(holo, "run_catalytic_swarm_1_audit") as shared:
            with self.assertRaisesRegex(holo.NeoLoopError, "consumed / no retry"):
                holo.command_audit_catalytic_swarm_1_v3(object())
        shared.assert_not_called()

    def test_runtime_path_mismatch_fails_closed(self) -> None:
        paths = list(holo.CATALYTIC_SWARM_1_V3_ARTIFACT_PATHS)
        paths[0] = holo.CATALYTIC_SWARM_1_V2_CONTROL_PATH
        with self.assertRaises(VersionedPathLawError):
            qualify_versioned_one_shot_paths(
                repo_root=ROOT,
                contract_paths=self.v3["one_shot"]["paths"],
                active_artifact_paths=paths,
                required_namespace="state/catalytic_swarm_1_v3",
            )

    def test_namespace_escape_fails_closed(self) -> None:
        paths = dict(self.v3["one_shot"]["paths"])
        paths["control"] = "state/escaped/control.json"
        with self.assertRaises(VersionedPathLawError):
            qualify_versioned_one_shot_paths(
                repo_root=ROOT,
                contract_paths=paths,
                active_artifact_paths=holo.CATALYTIC_SWARM_1_V3_ARTIFACT_PATHS,
                required_namespace="state/catalytic_swarm_1_v3",
            )

    def test_consumed_namespaces_are_forbidden(self) -> None:
        paths = dict(self.v3["one_shot"]["paths"])
        paths["control"] = "state/catalytic_swarm_1_v2/control-qualification-v3.json"
        with self.assertRaises(VersionedPathLawError):
            qualify_versioned_one_shot_paths(
                repo_root=ROOT,
                contract_paths=paths,
                active_artifact_paths=holo.CATALYTIC_SWARM_1_V3_ARTIFACT_PATHS,
                required_namespace="state/catalytic_swarm_1_v3",
                forbidden_namespaces=("state/catalytic_swarm_1_v2",),
            )

    def test_v2_is_retired_before_any_later_operation(self) -> None:
        with self.assertRaisesRegex(holo.NeoLoopError, "consumed and must not be rerun"):
            holo.command_audit_catalytic_swarm_1_v2(object())

    def test_v3_command_parses_only_to_explicit_retirement(self) -> None:
        parser = holo.build_parser()
        args = parser.parse_args(["audit-catalytic-swarm-1-v3"])
        with self.assertRaisesRegex(holo.NeoLoopError, "consumed / no retry"):
            args.handler(args)

    def test_v2_absent_and_v3_has_only_consumed_control(self) -> None:
        self.assertFalse(holo.CATALYTIC_SWARM_1_V2_STATE_ROOT.exists())
        self.assertTrue(holo.CATALYTIC_SWARM_1_V3_STATE_ROOT.exists())
        self.assertEqual(
            tuple(path.exists() for path in holo.CATALYTIC_SWARM_1_V3_ARTIFACT_PATHS),
            (True, False, False, False, False, False, False),
        )

    def test_v2_and_v3_path_maps_are_disjoint(self) -> None:
        self.assertTrue(
            set(self.v2["one_shot"]["paths"].values()).isdisjoint(
                self.v3["one_shot"]["paths"].values()
            )
        )

    def test_root_law_geometry_and_claim_limits_are_unchanged(self) -> None:
        self.assertEqual(self.v2["frozen_geometry"], self.v3["frozen_geometry"])
        self.assertEqual(self.v2["cache_admission_law"], self.v3["cache_admission_law"])
        self.assertEqual(self.v2["claim_limits"], self.v3["claim_limits"])
        self.assertEqual(self.v3["frozen_geometry"]["total_model_requests"], 1032)
        self.assertFalse(self.v3["claim_limits"]["automatic_promotion"])

    def test_root_terminal_transport_projects_into_immutable_scheduler_schema(self) -> None:
        transport = {
            "content": '{"candidate_id":"C00"}',
            "prompt_tokens": 4830,
            "cached_prompt_tokens": 4822,
            "required_cached_prompt_tokens": 4825,
            "fresh_prompt_tokens": 8,
            "completion_tokens": 7,
            "finish_reason": "stop",
            "reasoning_content": "",
            "tool_calls": [],
            "transport_passed": True,
            "token_evidence_scope": "exact-visible-content-tokenization-plus-one-terminal-eos-token",
            "public_root_terminal_token_index": 4820,
            "common_prefix_tokens": 4822,
            "cache_admission": {"admitted": True},
        }
        with holo.catalytic_swarm_1_v3_runtime_namespace(self.v3):
            projected = holo.adapt_catalytic_swarm_1_transport_for_scheduler(
                transport
            )
        self.assertEqual(
            set(projected),
            {
                "content",
                "prompt_tokens",
                "cached_prompt_tokens",
                "required_cached_prompt_tokens",
                "fresh_prompt_tokens",
                "completion_tokens",
                "finish_reason",
                "reasoning_content",
                "tool_calls",
                "transport_passed",
                "token_evidence_scope",
            },
        )
        self.assertEqual(projected["required_cached_prompt_tokens"], 4820)
        self.assertLess(
            projected["required_cached_prompt_tokens"],
            transport["required_cached_prompt_tokens"],
        )
        task = holo.build_frozen_task_suite().tasks[0]
        turn = holo.build_all_arm_plans()[0].turns[0]
        observation = _parse_transport(
            projected,
            turn=turn,
            task=task,
            public_root_sha256="0" * 64,
            score_public=False,
        )
        self.assertEqual(observation.candidate_id, "C00")


if __name__ == "__main__":
    unittest.main()
