#!/usr/bin/env python3

from __future__ import annotations

import json
import unittest

import catalytic_kernel_0_balanced_opaque as balanced
from test_catalytic_kernel_0_balanced_rank_head_v2_core import RankHeadV2Tests
import catalytic_kernel_0_balanced_rank_head_v2 as rank_head


class RankHeadV2CarrierTests(unittest.TestCase):
    def test_v2_carrier_removes_model_authored_extraction(self) -> None:
        carrier = rank_head.build_v2_carrier()
        root = json.loads(carrier["carrier_root"])
        self.assertEqual(carrier["carrier_id"], rank_head.V2_CARRIER_ID)
        self.assertNotEqual(carrier["carrier_id"], balanced.CARRIER_ID)
        self.assertEqual(
            set(root["response_schemas"]),
            set(rank_head.MODEL_REQUEST_STAGES),
        )
        self.assertNotIn("extract", root["response_schemas"])
        self.assertEqual(
            root["kernel_instructions"]["cycle"],
            list(rank_head.LOGICAL_STAGES),
        )
        self.assertFalse(
            root["kernel_instructions"]["extraction_contract"][
                "model_request_present"
            ]
        )
        for request_id in rank_head.MODEL_REQUEST_STAGES:
            schema = rank_head.v2_response_schema(request_id)
            if request_id in {"borrow", "restore"}:
                self.assertEqual(
                    schema["properties"]["carrier_id"]["const"],
                    rank_head.V2_CARRIER_ID,
                )
            else:
                self.assertEqual(schema, balanced.response_schema(request_id))
        with self.assertRaises(rank_head.RankHeadDesignError):
            rank_head.v2_response_schema("extract")
        self.assertEqual(
            set(rank_head.REQUIRED_IMPLEMENTATION_PATHS),
            {
                "scripts/catalytic_kernel_0_balanced_rank_head_v2.py",
                "scripts/catalytic_kernel_0_balanced_rank_head_v2_core.py",
                "scripts/test_catalytic_kernel_0_balanced_rank_head_v2.py",
                "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_core.py",
            },
        )


if __name__ == "__main__":
    unittest.main()
