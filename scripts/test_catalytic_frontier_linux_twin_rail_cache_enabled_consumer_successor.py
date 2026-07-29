#!/usr/bin/env python3
"""Zero-contact tests for neo-exp-0099 live-consumer cache admission."""

from pathlib import Path
import sys
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_linux_twin_rail_cache_enabled_consumer_successor as candidate


class TwinRailCacheEnabledConsumerSuccessorTests(unittest.TestCase):
    def test_identity_and_schedule_propagate_and_restore(self) -> None:
        self.assertEqual(candidate.EXPERIMENT_ID, "neo-exp-0099")
        self.assertEqual(candidate.ATTEMPT_ID, "frontier-attempt-0149")
        self.assertEqual(
            candidate.PREREGISTRATION_ATTEMPT_ID,
            "frontier-attempt-0148",
        )
        candidate.install_identity()
        try:
            for module in candidate._IDENTITY_MODULES:
                self.assertEqual(module.EXPERIMENT_ID, "neo-exp-0099")
            self.assertEqual(candidate.BASE.EXPECTED_MODEL_CALLBACKS, 43)
            self.assertEqual(
                candidate.BASE.EXPECTED_DIRECT_PROTOCOL_ACTIONS,
                29,
            )
        finally:
            candidate.restore_identity()
        self.assertEqual(candidate.parent.EXPERIMENT_ID, "neo-exp-0098")

    def test_only_consumer_copy_enables_cache(self) -> None:
        payload = {
            "prompt": [1, 2, 3],
            "cache_prompt": False,
            "grammar": candidate.BASE.SUFFIX_GRAMMAR,
        }
        contract = {"boundary_id": "fixed"}
        result = candidate.cache_enabled_consumer_payload(payload, contract)
        self.assertFalse(payload["cache_prompt"])
        self.assertTrue(result["cache_prompt"])
        self.assertEqual(result["prompt"], payload["prompt"])
        self.assertEqual(
            result["neo3000_live_terminal"],
            contract,
        )
        self.assertTrue(result["neo3000_use_live_terminal_boundary"])

    def test_live_route_sends_true_after_false_capture(self) -> None:
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
                candidate.parent,
                "fixed_unrelated_payload",
                return_value=(list(range(91)), payload, ancestry),
            ),
            mock.patch.object(
                candidate.parent,
                "capture_unrelated_boundary",
                return_value=capture,
            ) as capture_call,
            mock.patch.object(
                candidate.BASE,
                "public_contract",
                return_value={"carrier_id": "new", "module_variant": 0},
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
                    "answer": "B",
                    "actual_suffix_token_ids": [33, 8934, 248046],
                },
            ),
        ):
            value = candidate.run_unrelated_live_route(
                sidecar=object(),
                codec=object(),
                props={},
                trial="unrelated-restored",
                variant=0,
            )
        self.assertFalse(
            capture_call.call_args.kwargs["payload"]["cache_prompt"]
        )
        self.assertTrue(seen[0]["cache_prompt"])
        self.assertTrue(value["consumer_request"]["cache_prompt"])
        self.assertEqual(value["boundary"]["answer"], "B")

    def test_false_consumer_or_true_capture_is_forbidden(self) -> None:
        with self.assertRaises(Exception):
            candidate.cache_enabled_consumer_payload(
                {"cache_prompt": True},
                {},
            )
        result = candidate.cache_enabled_consumer_payload(
            {"cache_prompt": False},
            {},
        )
        result["cache_prompt"] = False
        self.assertFalse(result["cache_prompt"])
        self.assertNotEqual(
            result["cache_prompt"],
            True,
        )

    def test_source_proves_admission_without_sampler_drift(self) -> None:
        self.assertTrue(candidate.consumer_admission_source_gate())
        task_source = (
            candidate.ROOT / "tools" / "server" / "server-task.cpp"
        ).read_text(encoding="utf-8")
        start = task_source.index(
            "json task_params::to_json(bool only_metrics) const"
        )
        end = task_source.index(
            "task_result_state::task_result_state",
            start,
        )
        self.assertNotIn("cache_prompt", task_source[start:end])

    def test_manifest_freezes_only_consumer_admission_change(self) -> None:
        original = candidate._BASE_RUNTIME_MANIFEST_TEMPLATE
        candidate._BASE_RUNTIME_MANIFEST_TEMPLATE = lambda _commit: {}
        try:
            manifest = candidate.runtime_manifest_template("source")
        finally:
            candidate._BASE_RUNTIME_MANIFEST_TEMPLATE = original
        repair = manifest["independent_consumer_admission_repair"]
        self.assertFalse(repair["restored_capture_cache_prompt"])
        self.assertTrue(repair["restored_consumer_cache_prompt"])
        self.assertFalse(repair["compact_capture_cache_prompt"])
        self.assertTrue(repair["compact_consumer_cache_prompt"])
        self.assertFalse(repair["materialized_cache_prompt"])
        self.assertFalse(
            repair["cache_prompt_serialized_in_sampler_contract"]
        )
        self.assertEqual(repair["added_model_callbacks"], 0)

    def test_static_audit_has_no_scientific_contact(self) -> None:
        candidate.install_identity()
        try:
            value = candidate.static_audit()
        finally:
            candidate.restore_identity()
        self.assertTrue(all(value["gates"].values()))
        self.assertTrue(
            value["gates"]["consumer_only_cache_enabled_admission"]
        )
        self.assertEqual(value["id"], "neo-exp-0099")
        self.assertFalse(value["scientific_contact"])


if __name__ == "__main__":
    unittest.main()
