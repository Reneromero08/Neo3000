#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2 as v2
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration


class RankHeadV2IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_private = balanced.PrivateBinding.from_secret(
            bytes(range(32)),
            balanced.BINDING_1,
        )
        cls.spec = integration.RUN_SPECS[integration.BINDING_1_RUN_ID]
        cls.private = integration.runtime_private_from_source(
            cls.source_private,
            cls.spec,
        )
        cls.runtime = integration.RankHeadV2Runtime(
            repository=Path("."),
            spec=cls.spec,
            private=cls.private,
        )
        cls.winner = cls.private.internal_to_alias[
            balanced.EXPECTED_FULL_SUPPORT[0]
        ]
        cls.alternatives = [
            alias for alias in balanced.ALIASES if alias != cls.winner
        ]

    def executor(self, winner: bool):
        calls: list[str] = []

        def execute(stage: str, payload):
            calls.append(stage)
            self.assertNotEqual(stage, "extract")
            root = json.loads(payload["messages"][0]["content"])
            self.assertEqual(root["carrier_id"], v2.V2_CARRIER_ID)
            if stage in {"borrow", "restore"}:
                return json.dumps(
                    {"accepted": True, "carrier_id": v2.V2_CARRIER_ID}
                )
            if stage in {"branch-a", "branch-b"}:
                return json.dumps({"ranking": ["K00", "K01", "K02"]})
            ranking = (
                [self.winner, *self.alternatives[:2]]
                if winner
                else [self.alternatives[0], self.winner, self.alternatives[1]]
            )
            return json.dumps({"operator": "refine", "ranking": ranking})

        return calls, execute

    def test_six_logical_stages_five_model_requests(self) -> None:
        calls, executor = self.executor(True)
        result = integration.execute_logical_cycle(self.runtime, executor)
        self.assertEqual(calls, list(integration.MODEL_REQUEST_STAGES))
        self.assertEqual(result["logical_stage_count"], 6)
        self.assertEqual(result["model_request_count"], 5)
        self.assertFalse(result["outcomes"][4]["model_request_issued"])
        self.assertEqual(
            result["terminal_classification"],
            integration.VISIBLE_CLASSIFICATION,
        )

    def test_nonwinner_rank_head_remains_collapsed(self) -> None:
        _, executor = self.executor(False)
        result = integration.execute_logical_cycle(self.runtime, executor)
        self.assertEqual(
            result["terminal_classification"],
            integration.COLLAPSED_CLASSIFICATION,
        )
        evaluation = result["artifacts"]["extract"][
            "controller_private_evaluation"
        ]
        self.assertFalse(evaluation["mapped_to_full_public_support"])
        self.assertLess(evaluation["full_public_score"], 5)

    def test_extract_model_request_is_forbidden(self) -> None:
        with self.assertRaises(integration.RankHeadV2IntegrationError):
            self.runtime.build_model_request("extract", {})

    def test_existing_alias_mapping_is_preserved_and_run_key_changes(self) -> None:
        self.assertEqual(
            self.private.alias_to_internal,
            self.source_private.alias_to_internal,
        )
        self.assertNotEqual(
            self.private.run_key(self.spec.run_id),
            self.source_private.run_key(self.spec.source_full_run_id),
        )

    def test_ordered_two_run_gate(self) -> None:
        first = integration.RUN_SPECS[integration.BINDING_1_RUN_ID]
        second = integration.RUN_SPECS[integration.BINDING_2_RUN_ID]
        self.assertEqual(first.authorization_state, "separately-authorizable")
        self.assertEqual(second.predecessor_run_id, first.run_id)
        self.assertIn("unauthorized", second.authorization_state)

    def test_v2_carrier_contains_no_extract_schema(self) -> None:
        root = json.loads(v2.build_v2_carrier()["carrier_root"])
        self.assertNotIn("extract", root["response_schemas"])
        self.assertEqual(
            set(root["response_schemas"]),
            set(integration.MODEL_REQUEST_STAGES),
        )

    def test_repository_constructor_requires_authoritative_wrapper(self) -> None:
        with self.assertRaisesRegex(
            integration.RankHeadV2IntegrationError,
            "authoritative run-design module",
        ):
            integration.RankHeadV2Runtime.from_repository(
                Path("."),
                integration.BINDING_1_RUN_ID,
            )

    def test_alternate_run_design_surfaces_fail_closed(self) -> None:
        for function in (
            integration.build_run_design,
            integration.write_run_design,
            integration.validate_run_design,
        ):
            with self.assertRaisesRegex(
                integration.RankHeadV2IntegrationError,
                "authoritative run-design module",
            ):
                function()


if __name__ == "__main__":
    unittest.main()
