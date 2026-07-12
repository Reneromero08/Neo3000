#!/usr/bin/env python3
"""CPU-only controller checks for the CS1-v3 active-version path repair."""

from __future__ import annotations

import unittest
from pathlib import Path

import holostate_live as holo
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

    def test_v3_controller_path_qualification_passes_without_live_access(self) -> None:
        before = tuple(path.exists() for path in holo.CATALYTIC_SWARM_1_V3_ARTIFACT_PATHS)
        base = holo.load_json(ROOT / "lab" / "EVALUATOR.json")["catalytic_swarm_1"]
        with holo.catalytic_swarm_1_v3_runtime_namespace(self.v3):
            result = holo.qualify_catalytic_swarm_1_control(
                base,
                contract_paths=self.v3["one_shot"]["paths"],
                active_artifact_paths=holo.CATALYTIC_SWARM_1_ARTIFACT_PATHS,
                required_namespace="state/catalytic_swarm_1_v3",
                forbidden_namespaces=(
                    "state/catalytic_swarm_1",
                    "state/catalytic_swarm_1_cache_diagnostic",
                    "state/catalytic_swarm_1_v2",
                ),
                protocol_label="CatalyticSwarm-1 v3",
            )
        self.assertTrue(result["passed"])
        self.assertFalse(result["generation_executed"])
        self.assertFalse(any(before))
        self.assertFalse(any(path.exists() for path in holo.CATALYTIC_SWARM_1_V3_ARTIFACT_PATHS))

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

    def test_v3_command_requires_exact_model_and_main_flags(self) -> None:
        parser = holo.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["audit-catalytic-swarm-1-v3"])

    def test_v2_and_v3_state_roots_remain_absent(self) -> None:
        self.assertFalse(holo.CATALYTIC_SWARM_1_V2_STATE_ROOT.exists())
        self.assertFalse(holo.CATALYTIC_SWARM_1_V3_STATE_ROOT.exists())

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


if __name__ == "__main__":
    unittest.main()
