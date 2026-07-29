from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_live_terminal_pipeline as pipeline

_INHERITED_PREDECESSOR_IDENTITY = {
    "EXPERIMENT_ID": pipeline.predecessor.EXPERIMENT_ID,
    "ATTEMPT_ID": pipeline.predecessor.ATTEMPT_ID,
    "BASE_ROOT_ID": pipeline.predecessor.BASE_ROOT_ID,
    "SEED_TERMINAL_ROOT_ID": pipeline.predecessor.SEED_TERMINAL_ROOT_ID,
}


class LiveTerminalPipelineTests(unittest.TestCase):
    def tearDown(self) -> None:
        for name, value in _INHERITED_PREDECESSOR_IDENTITY.items():
            setattr(pipeline.predecessor, name, value)

    def test_frozen_r2_routes_and_orders(self):
        self.assertEqual(pipeline.EXPERIMENT_ID, "neo-exp-0088")
        self.assertEqual(pipeline.ATTEMPT_ID, "frontier-attempt-0125")
        self.assertEqual(
            pipeline.ROUTES,
            ("live-terminal", "root-only", "materialized"),
        )
        self.assertEqual(
            pipeline.TRIAL_ROUTE_ORDERS,
            (
                ("live-terminal", "root-only", "materialized"),
                ("root-only", "materialized", "live-terminal"),
                ("materialized", "live-terminal", "root-only"),
            ),
        )

    def test_predecessor_helpers_are_rebound_to_new_artifact_identity(self):
        pipeline.configure_predecessor_identity()
        self.assertEqual(pipeline.predecessor.EXPERIMENT_ID, "neo-exp-0088")
        self.assertEqual(
            pipeline.predecessor.BASE_ROOT_ID,
            "neo-exp-0088-base-689",
        )
        self.assertEqual(
            pipeline.predecessor.SEED_TERMINAL_ROOT_ID,
            "neo-exp-0088-seed-terminal-690",
        )

    def test_route_dispatch_keeps_live_only_arguments_out_of_controls(self):
        common = {
            "sidecar": object(),
            "codec": object(),
            "props": {},
            "base_root": {},
            "branch_tokens": [],
            "seed_state": {},
            "trial_label": "trial",
            "baseline_private": None,
            "run_successor_negative": False,
        }
        with (
            mock.patch.object(
                pipeline.live,
                "run_live_sequence",
                return_value={
                    "route": "live-terminal",
                    "fully_charged_wall_seconds": 0.0,
                },
            ) as live_route,
            mock.patch.object(
                pipeline.predecessor,
                "run_root_only_sequence",
                return_value={
                    "route": "root-only",
                    "fully_charged_wall_seconds": 0.0,
                },
            ) as root_route,
            mock.patch.object(
                pipeline.predecessor,
                "run_materialized_sequence",
                return_value={
                    "route": "materialized",
                    "fully_charged_wall_seconds": 0.0,
                },
            ) as direct_route,
        ):
            live_result = pipeline.run_sequence("live-terminal", **common)
            root_result = pipeline.run_sequence("root-only", **common)
            direct_result = pipeline.run_sequence("materialized", **common)
        self.assertIn("baseline_private", live_route.call_args.kwargs)
        self.assertNotIn("baseline_private", root_route.call_args.kwargs)
        self.assertNotIn(
            "run_successor_negative",
            root_route.call_args.kwargs,
        )
        self.assertNotIn("base_root", direct_route.call_args.kwargs)
        for result in (live_result, root_result, direct_result):
            self.assertIn("fully_charged_wall_seconds", result)
            self.assertIn("component_accounted_wall_seconds", result)
            self.assertIn("whole-route monotonic wall", result["fully_charged_wall_semantics"])

    def test_controller_requires_cuda_only_at_execution_boundary(self):
        source = Path(pipeline.__file__).read_text(encoding="utf-8")
        self.assertIn(
            'require(cuda_linked(binary), "0088 execution requires a CUDA-linked Linux binary")',
            source,
        )
        self.assertIn('"cuda_linked": cuda_linked(binary)', source)

    def test_result_separates_declared_closure_from_restoration(self):
        source = Path(pipeline.__file__).read_text(encoding="utf-8")
        self.assertIn('"restoration_class": "DECLARED_CLOSURE"', source)
        self.assertIn("declared_closure_not_restoration", source)
        self.assertIn("No inverse restoration", source)
        self.assertNotIn("EXACT_ALGEBRAIC_RESTORATION", source)

    def test_no_destructive_file_cleanup(self):
        source = Path(pipeline.__file__).read_text(encoding="utf-8")
        for token in ("rmtree", ".unlink(", "os.remove", "rmdir("):
            self.assertNotIn(token, source[: source.index("def static_audit(")])
        self.assertIn("path.rename(released)", source)
        self.assertIn('"run_root_preserved"', Path(
            pipeline.linux_sidecar.__file__
        ).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
