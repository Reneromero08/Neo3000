#!/usr/bin/env python3
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalytic_frontier_water_panel_qualifier as qualifier


class CatalyticFrontierWaterPanelQualifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        repository = Path(__file__).resolve().parents[1]
        corpus = qualifier.harness.carrier.load_public_corpus(repository)
        cls.root = next(item for item in corpus["roots"] if item["root_id"] == qualifier.ROOT_ID)

    def test_water_panel_preserves_public_branches_and_freezes_sixteen(self) -> None:
        panel = qualifier.panel_for(self.root)
        self.assertEqual(len(panel), 16)
        self.assertEqual(len({item["question"] for item in panel}), 16)
        self.assertEqual(panel[0]["question"], self.root["branches"][0]["question"])
        self.assertEqual(panel[1]["question"], self.root["branches"][1]["question"])

    def test_frozen_sequence_is_balanced(self) -> None:
        panel = qualifier.panel_for(self.root)
        sequence = "".join(panel[number - 1]["answer"] for number in qualifier.PANEL_ORDER)
        self.assertEqual(sequence, "BACDABCDABCDABCD")
        self.assertEqual({label: sequence.count(label) for label in "ABCD"}, {"A": 4, "B": 4, "C": 4, "D": 4})

    def test_evaluate_uses_only_water_panel_and_exact_gate(self) -> None:
        panel_result = {"qualified": True, "correct": 16}
        with mock.patch.object(qualifier.base, "evaluate_panel", return_value=panel_result) as evaluate_panel:
            result = qualifier.evaluate(
                sidecar=object(),
                codec=object(),
                props={},
                root=self.root,
                baseline_private=None,
            )
        self.assertEqual(result["verdict"], "accept")
        self.assertEqual(result["classification"], "water-direct-panel-qualified")
        self.assertEqual(result["carrier_operations"], 0)
        self.assertEqual(result["snapshot_operations"], 0)
        self.assertEqual(result["cache_enabled_branches"], 0)
        self.assertEqual(evaluate_panel.call_count, 1)
        kwargs = evaluate_panel.call_args.kwargs
        self.assertEqual(kwargs["branch_order_override"], qualifier.PANEL_ORDER)
        self.assertEqual(len(kwargs["panel_override"]), 16)

    def test_controller_has_no_carrier_snapshot_retry_or_cache_enabled_path(self) -> None:
        source = inspect.getsource(qualifier)
        self.assertNotIn("ram_root_action", source)
        self.assertNotIn("snapshot_action", source)
        self.assertNotIn("cache_prompt=True", source)
        self.assertNotIn("retry", source.lower().replace("non-retry", ""))

    def test_checkpoint_cli_is_fixed_to_zero(self) -> None:
        with mock.patch.object(sys, "argv", ["catalytic_frontier_water_panel_qualifier.py"]):
            args = qualifier.parse_args()
        self.assertEqual(args.ctx_checkpoints, 0)


    def test_pinned_binary_guard_precedes_stable_contact(self) -> None:
        source = inspect.getsource(qualifier.main)
        self.assertLess(
            source.index("require_pinned_binary(binary)"),
            source.index("require_stable()"),
        )
        with mock.patch.object(
            qualifier.harness.live_runtime,
            "sha256_file",
            return_value=qualifier.PINNED_BINARY_SHA256,
        ):
            qualifier.require_pinned_binary(Path("candidate.exe"))
        with mock.patch.object(
            qualifier.harness.live_runtime,
            "sha256_file",
            return_value="0" * 64,
        ):
            with self.assertRaises(qualifier.harness.FrontierHarnessError):
                qualifier.require_pinned_binary(Path("candidate.exe"))


    def test_startup_health_recovery_is_bounded_startup_only_and_deadline_deferred(self) -> None:
        policy = qualifier.startup_health_recovery_policy()
        self.assertEqual(policy.maximum_consecutive_failure_seconds, 15.0)
        self.assertEqual(policy.required_consecutive_successes, 3)
        evaluator = qualifier.harness.live_runtime.load_json(
            qualifier.harness.live_runtime.EVALUATOR_PATH
        )
        control = qualifier.startup_readiness_control(evaluator)
        self.assertEqual(
            qualifier.harness.sha256_bytes(
                qualifier.harness.carrier.canonical_json_bytes(control)
            ),
            qualifier.STARTUP_READINESS_CONTROL_SHA256,
        )
        with (
            mock.patch.object(
                qualifier.checkpoint_control,
                "ScopedCheckpointDiscoverySidecar",
            ) as sidecar_type,
        ):
            built = qualifier.build_sidecar(
                binary=Path("candidate.exe"),
                model=Path("model.gguf"),
                evaluator=evaluator,
                live_contract={},
                stable_pids={3860},
                state_root=Path("state-root"),
                context_checkpoints=0,
            )
        self.assertIs(built, sidecar_type.return_value)
        kwargs = sidecar_type.call_args.kwargs
        self.assertEqual(kwargs["readiness_control"], control)
        self.assertIsNone(kwargs["readiness_deadline_at"])
        self.assertEqual(kwargs["prelaunch_evidence"], {"stable_pids": [3860]})
        self.assertEqual(kwargs["context_checkpoints"], 0)
        self.assertEqual(
            kwargs["readiness_deadline_seconds_after_identity"], 180.0
        )
        integrated_policy = kwargs["stable_health_recovery_policy"]
        self.assertEqual(integrated_policy.maximum_consecutive_failure_seconds, 15.0)
        self.assertEqual(integrated_policy.required_consecutive_successes, 3)
        launch_source = inspect.getsource(qualifier.harness.live_runtime.LiveSidecar.launch)
        active_source = inspect.getsource(qualifier.harness.live_runtime.LiveSidecar.require_active)
        self.assertIn("if self.readiness_control is None", launch_source)
        self.assertIn("stable_health_recovery_policy=self.stable_health_recovery_policy", launch_source)
        self.assertNotIn("stable_health_recovery_policy", active_source)
        self.assertLess(
            launch_source.index("binary_identity, model_identity = self.runtime_identities()"),
            launch_source.index("self.process = subprocess.Popen"),
        )

    def test_controlled_discovery_seeds_base_runtime_identity_contract(self) -> None:
        binary = Path("candidate.exe").resolve()
        model = Path("model.gguf").resolve()
        evaluator = {"model": {"sha256": qualifier.harness.live_runtime.EXPECTED_MODEL_SHA256}}
        binary_identity = {
            "path": str(binary),
            "sha256": qualifier.PINNED_BINARY_SHA256,
            "runtime_version": "178 (6c63039)",
        }

        def initialize_base(
            sidecar: object,
            binary_arg: Path,
            model_arg: Path,
            evaluator_arg: dict[str, object],
            _contract: dict[str, object],
            _detached: bool,
            **kwargs: object,
        ) -> None:
            sidecar.binary = binary_arg.resolve()
            sidecar.model = model_arg.resolve()
            sidecar.evaluator = evaluator_arg
            sidecar.readiness_control = kwargs.get("readiness_control")
            sidecar.preverified_binary_identity = kwargs.get("preverified_binary_identity")
            sidecar.preverified_model_identity = kwargs.get("preverified_model_identity")

        with (
            mock.patch.object(
                qualifier.harness.live_runtime.LiveSidecar,
                "__init__",
                autospec=True,
                side_effect=initialize_base,
            ),
            mock.patch.object(
                qualifier.harness,
                "discovery_binary_identity",
                return_value=binary_identity,
            ),
        ):
            sidecar = qualifier.harness.DiscoverySidecar(
                binary,
                model,
                evaluator,
                {},
                False,
                readiness_control={"enabled": True},
            )

        self.assertEqual(sidecar.preverified_binary_identity, binary_identity)
        self.assertEqual(
            sidecar.preverified_model_identity,
            {
                "path": str(model),
                "sha256": qualifier.harness.live_runtime.EXPECTED_MODEL_SHA256,
                "size_bytes": qualifier.harness.live_runtime.EXPECTED_MODEL_SIZE,
            },
        )

    def test_controlled_discovery_delegates_runtime_locking_to_base(self) -> None:
        sidecar = object.__new__(qualifier.harness.DiscoverySidecar)
        sidecar.readiness_control = {"enabled": True}
        identities = ({"sha256": "binary"}, {"sha256": "model"})
        with mock.patch.object(
            qualifier.harness.live_runtime.LiveSidecar,
            "runtime_identities",
            autospec=True,
            return_value=identities,
        ) as base_runtime_identities:
            observed = sidecar.runtime_identities()
        self.assertEqual(observed, identities)
        base_runtime_identities.assert_called_once_with(sidecar)

    def test_readiness_deadline_starts_only_after_runtime_identity_hashing(self) -> None:
        sidecar = object.__new__(qualifier.checkpoint_control.ScopedCheckpointDiscoverySidecar)
        sidecar.readiness_control = {"readiness_deadline_seconds": 180.0}
        sidecar.readiness_deadline_at = None
        sidecar.readiness_deadline_seconds_after_identity = 180.0
        identities = (
            {"path": "candidate.exe", "sha256": "binary", "runtime_version": "test"},
            {"path": "model.gguf", "sha256": "model", "size_bytes": 1},
        )
        with (
            mock.patch.object(
                qualifier.harness.DiscoverySidecar,
                "runtime_identities",
                return_value=identities,
            ) as runtime_identities,
            mock.patch.object(qualifier.checkpoint_control.time, "monotonic", return_value=100.0),
        ):
            observed = sidecar.runtime_identities()
        self.assertEqual(observed, identities)
        self.assertEqual(sidecar.readiness_deadline_at, 280.0)
        runtime_identities.assert_called_once_with()

if __name__ == "__main__":
    unittest.main()
