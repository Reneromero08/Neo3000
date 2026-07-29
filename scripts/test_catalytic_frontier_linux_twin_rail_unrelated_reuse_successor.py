#!/usr/bin/env python3
"""Zero-contact tests for neo-exp-0098 unrelated restored-fiber reuse."""

from pathlib import Path
import sys
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_linux_twin_rail_unrelated_reuse_successor as candidate


class _Sidecar:
    readiness = {"log_path": "/nonexistent/neo-exp-0098-server.log"}


def _route(
        *,
        carrier_id: str,
        variant: int,
        capture_cached: int = 0,
        consumer_cached: int = 91,
        answer: str = "B",
) -> dict:
    return {
        "contract": {
            "carrier_id": carrier_id,
            "generation": 1,
            "module_ordinal": 1,
            "module_variant": variant,
            "input_boundary_id": candidate.UNRELATED_INPUT_BOUNDARY_ID,
        },
        "ancestry": {
            "answer_mapping_selected_after_model_output": False,
        },
        "capture": {
            "summary": {
                "prompt_tokens": 91,
                "cached_prompt_tokens": capture_cached,
                "fresh_prompt_tokens": 91 - capture_cached,
                "completion_tokens": 0,
            },
        },
        "consumer": {
            "prompt_tokens": 91,
            "cached_prompt_tokens": consumer_cached,
            "fresh_prompt_tokens": 91 - consumer_cached,
            "completion_tokens": 3,
        },
        "boundary": {
            "answer": answer,
            "actual_suffix_token_ids": [
                33 if answer == "B" else 32,
                8934,
                248046,
            ],
        },
    }


def _materialized(*, answer: str = "B") -> dict:
    return {
        "ancestry": {
            "answer_mapping_selected_after_model_output": False,
        },
        "record": {
            "prompt_tokens": 91,
            "cached_prompt_tokens": 0,
            "fresh_prompt_tokens": 91,
            "completion_tokens": 3,
        },
        "boundary": {
            "answer": answer,
            "actual_suffix_token_ids": [
                33 if answer == "B" else 32,
                8934,
                248046,
            ],
        },
    }


def _success_line(
        carrier: str,
        *,
        generation: int,
        ordinal: int,
        variant: int,
        transactions: int,
        reuses: int,
        margin: bool,
        quotient: bool,
        fresh: bool,
        backing: bool,
        recoveries: int = 0,
) -> str:
    return (
        "neo3000 twin-rail carrier restored and live source declared-closed "
        f"before response boundary=boundary carrier={carrier} lease=1 "
        f"generation={generation} ordinal={ordinal} variant={variant} "
        "cells=8 bytes=128 object_bytes=312 dynamic_capacity_bytes=180 "
        "receipt_bytes=96 contract_bytes=224 fresh_result_bytes=104 "
        f"fresh_object_bytes={312 if fresh else 0} "
        f"fresh_dynamic_capacity_bytes={180 if fresh else 0} "
        "score_error=1e-16 restoration_error=2e-16 "
        f"classical_parity={'true' if variant == 0 else 'false'} "
        f"canonical_tie_quotient={'true' if quotient else 'false'} "
        f"primary_margin_guard={'true' if margin else 'false'} "
        f"backing_reused={'true' if backing else 'false'} "
        f"fresh_parity={'true' if fresh else 'false'} "
        "fresh_restoration_error=3e-16 "
        f"transactions={transactions} reuses={reuses} "
        f"recoveries={recoveries}"
    )


def _complete_log() -> str:
    lines = [
        _success_line(
            "primary",
            generation=1,
            ordinal=1,
            variant=0,
            transactions=1,
            reuses=0,
            margin=True,
            quotient=False,
            fresh=True,
            backing=False,
        ),
        _success_line(
            "primary",
            generation=2,
            ordinal=2,
            variant=0,
            transactions=2,
            reuses=1,
            margin=True,
            quotient=False,
            fresh=True,
            backing=True,
        ),
        _success_line(
            "unrelated",
            generation=1,
            ordinal=1,
            variant=0,
            transactions=3,
            reuses=2,
            margin=True,
            quotient=False,
            fresh=True,
            backing=True,
        ),
        _success_line(
            "dephased",
            generation=1,
            ordinal=1,
            variant=1,
            transactions=4,
            reuses=3,
            margin=False,
            quotient=False,
            fresh=False,
            backing=True,
        ),
        _success_line(
            "reordered",
            generation=1,
            ordinal=1,
            variant=2,
            transactions=5,
            reuses=4,
            margin=False,
            quotient=True,
            fresh=False,
            backing=True,
        ),
    ]
    lines.extend(
        [
            "neo3000 twin-rail transaction rejected and live source poisoned"
            for _ in range(3)
        ]
    )
    return "\n".join(lines)


class TwinRailUnrelatedReuseSuccessorTests(unittest.TestCase):
    def test_identity_and_schedule_propagate_and_restore(self) -> None:
        self.assertEqual(candidate.EXPERIMENT_ID, "neo-exp-0098")
        self.assertEqual(candidate.ATTEMPT_ID, "frontier-attempt-0147")
        self.assertEqual(candidate.EXPECTED_MODEL_CALLBACKS, 43)
        self.assertEqual(candidate.EXPECTED_DIRECT_PROTOCOL_ACTIONS, 29)
        candidate.install_identity()
        try:
            for module in candidate._IDENTITY_MODULES:
                self.assertEqual(module.EXPERIMENT_ID, "neo-exp-0098")
            self.assertEqual(candidate.BASE.EXPECTED_MODEL_CALLBACKS, 43)
            self.assertEqual(
                candidate.BASE.EXPECTED_DIRECT_PROTOCOL_ACTIONS,
                29,
            )
        finally:
            candidate.restore_identity()
        self.assertEqual(candidate.parent.EXPERIMENT_ID, "neo-exp-0097")
        self.assertEqual(candidate.BASE.EXPECTED_MODEL_CALLBACKS, 38)

    def test_fixed_boundary_payload_is_exact_and_cache_disabled(self) -> None:
        tokens, payload, ancestry = candidate.fixed_unrelated_payload()
        self.assertEqual(len(tokens), 91)
        self.assertEqual(
            candidate.BASE.prompt_fnv1a64(tokens),
            "1fd89d3051f37e58",
        )
        self.assertEqual(tuple(tokens[-3:]), candidate.BASE.PUBLIC_SCHEMA_PREFIX)
        self.assertFalse(payload["cache_prompt"])
        self.assertEqual(payload["grammar"], candidate.BASE.SUFFIX_GRAMMAR)
        self.assertEqual(
            ancestry["expected_answer_predeclared"],
            "B",
        )
        wrong = list(tokens)
        wrong[0] += 1
        self.assertNotEqual(
            candidate.BASE.prompt_fnv1a64(wrong),
            "1fd89d3051f37e58",
        )

    def test_local_schedule_passes_only_with_all_exact_routes(self) -> None:
        restored = _route(
            carrier_id="neo-exp-0098/unrelated/slot-0",
            variant=0,
        )
        compact = _route(
            carrier_id="neo-exp-0098/compact/slot-0",
            variant=8,
        )
        with (
            mock.patch.object(
                candidate,
                "run_unrelated_live_route",
                side_effect=[restored, compact],
            ),
            mock.patch.object(
                candidate,
                "run_unrelated_materialized",
                return_value=_materialized(),
            ),
        ):
            value = candidate.run_post_primary_successor(
                sidecar=object(),
                codec=object(),
                props={},
                setup={},
                primary={"carrier_id": "neo-exp-0098/primary/slot-0"},
                transaction_nonce="nonce",
                progress={},
            )
        self.assertTrue(value["passed"])
        self.assertEqual(value["passed"], all(value["local_gates"].values()))
        self.assertEqual(value["resource_additions"]["model_callbacks"], 5)
        self.assertEqual(
            value["fixed_operation_count_deltas"]["softmax_reductions"],
            5,
        )

    def test_cache_drift_or_wrong_output_rejects(self) -> None:
        bad_restored = _route(
            carrier_id="neo-exp-0098/unrelated/slot-0",
            variant=0,
            capture_cached=1,
        )
        compact = _route(
            carrier_id="neo-exp-0098/compact/slot-0",
            variant=8,
        )
        with (
            mock.patch.object(
                candidate,
                "run_unrelated_live_route",
                side_effect=[bad_restored, compact],
            ),
            mock.patch.object(
                candidate,
                "run_unrelated_materialized",
                return_value=_materialized(answer="A"),
            ),
            self.assertRaises(Exception),
        ):
            candidate.run_post_primary_successor(
                sidecar=object(),
                codec=object(),
                props={},
                setup={},
                primary={"carrier_id": "neo-exp-0098/primary/slot-0"},
                transaction_nonce="nonce",
                progress={},
            )

    def test_complete_lifetime_log_is_bound(self) -> None:
        with (
            mock.patch.object(Path, "read_text", return_value=_complete_log()),
            mock.patch.object(
                candidate.BASE.harness.live_runtime,
                "sha256_file",
                return_value="LOGHASH",
            ),
        ):
            value = candidate.BASE.phase_log_evidence(
                sidecar=_Sidecar(),
                primary_carrier_id="primary",
                unrelated_carrier_id="unrelated",
            )
        self.assertEqual(value["success_count"], 5)
        self.assertEqual(value["unrelated_primary_count"], 1)
        self.assertEqual(value["maximum_recovery_initializations"], 0)
        self.assertLessEqual(
            value["unrelated_numerical_metrics"][
                "maximum_restoration_error"
            ],
            1.0e-12,
        )

    def test_wrong_recovery_or_control_order_rejects(self) -> None:
        wrong_recovery = _complete_log().replace(
            "transactions=3 reuses=2 recoveries=0",
            "transactions=3 reuses=2 recoveries=1",
        )
        lines = _complete_log().splitlines()
        lines[3], lines[4] = lines[4], lines[3]
        for text in (wrong_recovery, "\n".join(lines)):
            with (
                mock.patch.object(Path, "read_text", return_value=text),
                mock.patch.object(
                    candidate.BASE.harness.live_runtime,
                    "sha256_file",
                    return_value="LOGHASH",
                ),
                self.assertRaises(Exception),
            ):
                candidate.BASE.phase_log_evidence(
                    sidecar=_Sidecar(),
                    primary_carrier_id="primary",
                    unrelated_carrier_id="unrelated",
                )

    def test_static_audit_has_no_scientific_contact(self) -> None:
        candidate.install_identity()
        try:
            value = candidate.static_audit()
        finally:
            candidate.restore_identity()
        self.assertTrue(all(value["gates"].values()))
        self.assertTrue(value["gates"]["actual_unrelated_reuse_source_law"])
        self.assertEqual(value["id"], "neo-exp-0098")
        self.assertFalse(value["scientific_contact"])


if __name__ == "__main__":
    unittest.main()
