#!/usr/bin/env python3
"""Zero-contact tests for neo-exp-0100 second unrelated carrier reuse."""

from pathlib import Path
import sys
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_linux_twin_rail_second_unrelated_successor as candidate


class TwinRailSecondUnrelatedSuccessorTests(unittest.TestCase):
    def test_identity_and_schedule_propagate_and_restore(self) -> None:
        self.assertEqual(candidate.EXPERIMENT_ID, "neo-exp-0100")
        self.assertEqual(candidate.ATTEMPT_ID, "frontier-attempt-0151")
        self.assertEqual(
            candidate.PREREGISTRATION_ATTEMPT_ID,
            "frontier-attempt-0150",
        )
        candidate.install_identity()
        try:
            for module in candidate._IDENTITY_MODULES:
                self.assertEqual(module.EXPERIMENT_ID, "neo-exp-0100")
            self.assertEqual(candidate.BASE.EXPECTED_MODEL_CALLBACKS, 48)
            self.assertEqual(
                candidate.BASE.EXPECTED_DIRECT_PROTOCOL_ACTIONS,
                29,
            )
        finally:
            candidate.restore_identity()
        self.assertEqual(candidate.parent.EXPERIMENT_ID, "neo-exp-0099")

    def test_fixed_second_boundary_is_exact_and_precontact(self) -> None:
        boundary = candidate.second_boundary()
        self.assertEqual(boundary["token_count"], 91)
        self.assertEqual(
            boundary["input_boundary_id"],
            "fnv1a64:4c0d82dcecacca31",
        )
        self.assertEqual(boundary["expected_answer"], "D")
        self.assertEqual(boundary["expected_token_id"], 35)
        self.assertFalse(boundary["contact"]["scientific_contact"])
        self.assertEqual(boundary["contact"]["model_callbacks"], 0)

    def test_second_live_route_captures_false_then_consumes_true(self) -> None:
        payload = {
            "prompt": list(range(91)),
            "cache_prompt": False,
            "grammar": candidate.BASE.SUFFIX_GRAMMAR,
        }
        ancestry = {"answer_mapping_selected_after_model_output": False}
        capture = {
            "summary": {
                "prompt_tokens": 91,
                "cached_prompt_tokens": 0,
                "fresh_prompt_tokens": 91,
                "completion_tokens": 0,
            },
        }
        completion = {
            "prompt_tokens": 91,
            "cached_prompt_tokens": 91,
            "fresh_prompt_tokens": 0,
            "completion_tokens": 3,
            "fresh_model_tokens": 3,
            "wall_seconds": 0.1,
        }
        seen: list[dict] = []

        def fake_completion(
                _sidecar,
                _label,
                wire,
                *,
                batch_owned_request,
        ):
            self.assertTrue(batch_owned_request)
            seen.append(dict(wire))
            return completion

        with (
            mock.patch.object(
                candidate,
                "fixed_second_payload",
                return_value=(list(range(91)), payload, ancestry),
            ),
            mock.patch.object(
                candidate.parent.parent,
                "capture_unrelated_boundary",
                return_value=capture,
            ) as capture_call,
            mock.patch.object(
                candidate.BASE,
                "public_contract",
                return_value={"carrier_id": "second", "module_variant": 0},
            ),
            mock.patch.object(
                candidate.BASE.harness,
                "run_completion",
                side_effect=fake_completion,
            ),
            mock.patch.object(
                candidate.BASE,
                "validate_suffix_state",
                return_value={
                    "answer": "D",
                    "actual_suffix_token_ids": [35, 8934, 248046],
                },
            ),
        ):
            value = candidate.run_second_live_route(
                sidecar=object(),
                codec=object(),
                props={},
                trial="second-restored",
                variant=0,
            )
        self.assertFalse(
            capture_call.call_args.kwargs["payload"]["cache_prompt"]
        )
        self.assertTrue(seen[0]["cache_prompt"])
        self.assertEqual(value["boundary"]["answer"], "D")

    @staticmethod
    def _route(carrier: str, variant: int) -> dict:
        return {
            "contract": {
                "carrier_id": carrier,
                "generation": 1,
                "module_ordinal": 1,
                "module_variant": variant,
                "input_boundary_id": candidate.SECOND_INPUT_BOUNDARY_ID,
            },
            "ancestry": {
                "answer_mapping_selected_after_model_output": False,
            },
            "capture": {
                "summary": {
                    "prompt_tokens": 91,
                    "cached_prompt_tokens": 0,
                    "fresh_prompt_tokens": 91,
                    "completion_tokens": 0,
                    "fresh_model_tokens": 91,
                    "wall_seconds": 0.25,
                },
            },
            "consumer": {
                "prompt_tokens": 91,
                "cached_prompt_tokens": 91,
                "fresh_prompt_tokens": 0,
                "completion_tokens": 3,
            },
            "boundary": {
                "answer": "D",
                "actual_suffix_token_ids": [35, 8934, 248046],
            },
        }

    def test_post_primary_aggregates_two_tasks_without_more_cells(self) -> None:
        first = {
            "carrier_id": "first",
            "passed": True,
            "fixed_operation_count_deltas":
                    dict(candidate._SECOND_OPERATION_DELTAS),
            "resource_additions": {
                "model_callbacks": 5,
                "direct_protocol_actions": 0,
                "prompt_token_callbacks": 455,
                "fresh_prompt_tokens": 273,
                "cached_prompt_tokens": 182,
                "completion_tokens": 9,
                "captured_host_logit_buffers": 2,
                "captured_host_logit_bytes_cumulative": 1_986_560,
                "structural_boundary_tokens": 91,
                "structural_boundary_device_bytes": 1_863_680,
                "additional_persistent_phase_cells": 0,
            },
        }
        restored = self._route("second", candidate.BASE.PRIMARY_VARIANT)
        compact = self._route(
            "compact",
            candidate.BASE.COMPACT_CLASSICAL_VARIANT,
        )
        compact["contract"]["input_boundary_id"] = (
            candidate.SECOND_INPUT_BOUNDARY_ID
        )
        materialized = {
            "record": {
                "prompt_tokens": 91,
                "cached_prompt_tokens": 0,
                "fresh_prompt_tokens": 91,
                "completion_tokens": 3,
            },
            "boundary": {
                "answer": "D",
                "actual_suffix_token_ids": [35, 8934, 248046],
            },
        }
        with (
            mock.patch.object(
                candidate,
                "_BASE_RUN_POST_PRIMARY_SUCCESSOR",
                return_value=first,
            ),
            mock.patch.object(
                candidate,
                "run_second_live_route",
                side_effect=[restored, compact],
            ),
            mock.patch.object(
                candidate,
                "run_second_materialized",
                return_value=materialized,
            ),
        ):
            value = candidate.run_post_primary_successor(
                sidecar=object(),
                codec=object(),
                props={},
                setup={},
                primary={},
                transaction_nonce="nonce",
                progress={},
            )
        self.assertTrue(value["passed"])
        self.assertEqual(value["expected_unrelated_primary_count"], 2)
        self.assertEqual(
            value["expected_post_success_fault_recovery_initializations"],
            2,
        )
        self.assertEqual(value["resource_additions"]["model_callbacks"], 10)
        self.assertEqual(
            value["resource_additions"]["additional_persistent_phase_cells"],
            0,
        )
        self.assertEqual(
            value["two_unrelated_task_totals"]["expected_answers"],
            ["B", "D"],
        )

    @staticmethod
    def _success_line(
            *,
            carrier: str,
            variant: int,
            generation: int,
            ordinal: int,
            transactions: int,
            reuses: int,
            margin: bool,
            quotient: bool,
            fresh: bool,
            backing: bool,
    ) -> str:
        return (
            "neo3000 twin-rail carrier restored and live source "
            "declared-closed before response "
            f"boundary=b carrier={carrier} lease=1 "
            f"generation={generation} ordinal={ordinal} variant={variant} "
            "cells=8 bytes=128 object_bytes=312 dynamic_capacity_bytes=128 "
            "receipt_bytes=256 contract_bytes=192 fresh_result_bytes=568 "
            "fresh_object_bytes=312 fresh_dynamic_capacity_bytes=128 "
            "score_error=0 restoration_error=0 classical_parity=true "
            f"canonical_tie_quotient={'true' if quotient else 'false'} "
            f"primary_margin_guard={'true' if margin else 'false'} "
            f"backing_reused={'true' if backing else 'false'} "
            f"fresh_parity={'true' if fresh else 'false'} "
            "fresh_restoration_error=0 "
            f"transactions={transactions} reuses={reuses} recoveries=0"
        )

    def test_log_parser_separates_success_from_fault_recovery(self) -> None:
        lines = [
            self._success_line(
                carrier="primary", variant=0, generation=1, ordinal=1,
                transactions=1, reuses=0, margin=True, quotient=False,
                fresh=True, backing=False,
            ),
            self._success_line(
                carrier="primary", variant=0, generation=2, ordinal=2,
                transactions=2, reuses=1, margin=True, quotient=False,
                fresh=True, backing=True,
            ),
            self._success_line(
                carrier="run-unrelated-restored/slot-0", variant=0,
                generation=1, ordinal=1, transactions=3, reuses=2,
                margin=True, quotient=False, fresh=True, backing=True,
            ),
            self._success_line(
                carrier="second", variant=0, generation=1, ordinal=1,
                transactions=4, reuses=3, margin=True, quotient=False,
                fresh=True, backing=True,
            ),
            self._success_line(
                carrier="dephased", variant=1, generation=1, ordinal=1,
                transactions=5, reuses=4, margin=False, quotient=False,
                fresh=False, backing=True,
            ),
            self._success_line(
                carrier="reordered", variant=2, generation=1, ordinal=1,
                transactions=6, reuses=5, margin=False, quotient=True,
                fresh=False, backing=True,
            ),
        ]
        for recovery in (0, 1, 2):
            lines.append(
                "neo3000 twin-rail transaction rejected and live source "
                "poisoned boundary=b carrier=fault generation=1 ordinal=1 "
                "pre_borrow=false "
                f"transactions=6 reuses=5 recoveries={recovery}"
            )
        sidecar = mock.Mock()
        sidecar.readiness = {"log_path": "/synthetic/server.log"}
        with (
            mock.patch.object(
                Path,
                "read_text",
                return_value="\n".join(lines),
            ),
            mock.patch.object(
                candidate.BASE.harness.live_runtime,
                "sha256_file",
                return_value="LOG",
            ),
        ):
            value = candidate.phase_log_evidence(
                sidecar=sidecar,
                primary_carrier_id="primary",
                unrelated_carrier_id="second",
            )
        self.assertEqual(value["success_count"], 6)
        self.assertEqual(value["unrelated_primary_count"], 2)
        self.assertEqual(value["maximum_recovery_initializations"], 0)
        self.assertEqual(
            value["post_success_fault_recovery_sequence"],
            [0, 1, 2],
        )
        self.assertEqual(
            value["post_success_fault_recovery_initializations"],
            2,
        )

    def test_shutdown_audit_matches_public_capture_lifecycle(self) -> None:
        sidecar = mock.Mock()
        sidecar.run_root = Path("/synthetic/run")
        cleanup = {"candidate_started": True, "pid": 42}
        base_receipt = {
            "candidate_started": True,
            "poisoned_boundaries": 0,
            "unresolved_boundaries": 0,
            "passed": True,
        }
        no_shutdown_capture = (
            "neo3000 twin-rail shutdown custody poisoned=0 unresolved=0\n"
            "neo3000 one-use live terminal shutdown custody "
            "poisoned=0 unresolved=0\n"
        )
        original = candidate.BASE._BASE_AUDIT_SHUTDOWN
        candidate.BASE._BASE_AUDIT_SHUTDOWN = lambda _sidecar, _cleanup: dict(
            base_receipt
        )
        try:
            with mock.patch.object(
                Path,
                "read_text",
                return_value=no_shutdown_capture,
            ):
                receipt = candidate.BASE.audit_shutdown(sidecar, cleanup)
            self.assertFalse(
                receipt["shutdown_resident_capture_scheduled"]
            )
            self.assertEqual(receipt["expected_live_poisoned"], 0)

            scheduled = (
                "neo3000 one-use live terminal boundary captured "
                "boundary=neo-exp-0101/nonce-shutdown/edge-1/"
                "variant-0/terminal carrier=c\n"
                "neo3000 twin-rail shutdown custody poisoned=0 unresolved=0\n"
            )
            candidate.BASE._BASE_AUDIT_SHUTDOWN = (
                lambda _sidecar, _cleanup: {
                    **base_receipt,
                    "poisoned_boundaries": 1,
                }
            )
            with mock.patch.object(Path, "read_text", return_value=scheduled):
                receipt = candidate.BASE.audit_shutdown(sidecar, cleanup)
            self.assertTrue(
                receipt["shutdown_resident_capture_scheduled"]
            )
            self.assertEqual(receipt["expected_live_poisoned"], 1)
        finally:
            candidate.BASE._BASE_AUDIT_SHUTDOWN = original

    def test_manifest_freezes_second_task_and_physical_accounting(self) -> None:
        original = candidate._BASE_RUNTIME_MANIFEST_TEMPLATE
        candidate._BASE_RUNTIME_MANIFEST_TEMPLATE = lambda _commit: {}
        try:
            manifest = candidate.runtime_manifest_template("source")
        finally:
            candidate._BASE_RUNTIME_MANIFEST_TEMPLATE = original
        self.assertEqual(
            manifest["second_unrelated_boundary"]["expected_answer"],
            "D",
        )
        self.assertEqual(
            manifest["second_unrelated_reuse_schedule"][
                "post_success_inverse_fault_recovery_sequence"
            ],
            [0, 1, 2],
        )
        combined = manifest["combined_unrelated_resource_preregistration"]
        self.assertEqual(combined["useful_task_boundaries"], 2)
        self.assertEqual(combined["additional_persistent_phase_cells"], 0)
        self.assertEqual(
            combined["maximum_simultaneously_live_boundary_buffers"],
            1,
        )

    def test_static_audit_has_no_scientific_contact(self) -> None:
        candidate.install_identity()
        original_manifest = candidate.BASE.DEFAULT_RUNTIME_MANIFEST
        candidate.BASE.DEFAULT_RUNTIME_MANIFEST = (
            candidate.ROOT / "lab" / "neo-exp-0100-unit-pending.json"
        )
        try:
            value = candidate.static_audit()
        finally:
            candidate.BASE.DEFAULT_RUNTIME_MANIFEST = original_manifest
            candidate.restore_identity()
        self.assertTrue(all(value["gates"].values()))
        self.assertEqual(value["id"], "neo-exp-0100")
        self.assertTrue(
            value["gates"]["second_restored_backing_reuse_source_law"]
        )
        self.assertFalse(value["scientific_contact"])


if __name__ == "__main__":
    unittest.main()
