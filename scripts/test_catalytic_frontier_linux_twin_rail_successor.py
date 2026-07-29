#!/usr/bin/env python3
"""Zero-contact tests for the neo-exp-0094 Linux twin-rail controller."""

from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import catalytic_frontier_linux_twin_rail_successor as candidate


class Codec:
    pieces = {
        4754: "{",
        8944: '"answer"',
        3147: ':"',
        32: "A",
        33: "B",
        34: "C",
        35: "D",
        8934: '"}',
        248046: "<eos>",
    }

    def detokenize(self, tokens):
        return "".join(self.pieces[token] for token in tokens)

    def tokenize(self, text):
        if text == "<eos>":
            return [248046]
        raise AssertionError(f"unexpected tokenize input: {text!r}")


class TwinRailControllerTests(unittest.TestCase):
    def test_preregistered_constants_are_exact(self) -> None:
        self.assertEqual(candidate.EXPERIMENT_ID, "neo-exp-0094")
        self.assertEqual(candidate.ATTEMPT_ID, "frontier-attempt-0139")
        self.assertEqual(
            candidate.PREREGISTRATION_ATTEMPT_ID,
            "frontier-attempt-0138",
        )
        self.assertEqual(candidate.PUBLIC_SCHEMA_PREFIX, (4754, 8944, 3147))
        self.assertEqual(
            candidate.CANDIDATE_TOKEN_IDS,
            {"A": 32, "B": 33, "C": 34, "D": 35},
        )
        self.assertEqual(candidate.HYPOTHESIS_TOKENS, 780)
        self.assertEqual(candidate.HYPOTHESIS_FRESH_TOKENS, 90)

    def test_expanded_successor_changes_only_public_prefix_and_suffix_grammar(self) -> None:
        tokens = list(range(777))
        payload = {
            "prompt": list(tokens),
            "n_predict": 64,
            "cache_prompt": True,
            "grammar": "old",
        }
        expanded, result = candidate.expanded_successor(tokens, payload)
        self.assertEqual(expanded[:777], tokens)
        self.assertEqual(expanded[-3:], [4754, 8944, 3147])
        self.assertEqual(result["prompt"], expanded)
        self.assertEqual(result["grammar"], candidate.SUFFIX_GRAMMAR)
        self.assertEqual(payload["prompt"], tokens)
        self.assertEqual(payload["grammar"], "old")

    def test_contract_is_public_fixed_owner_bound_and_deterministic(self) -> None:
        tokens = list(range(780))
        first = candidate.public_contract(
            trial="trial",
            edge=1,
            tokens=tokens,
            variant=candidate.PRIMARY_VARIANT,
        )
        second = candidate.public_contract(
            trial="trial",
            edge=1,
            tokens=tokens,
            variant=candidate.PRIMARY_VARIANT,
        )
        self.assertEqual(first, second)
        self.assertNotEqual(first["outer_lease"], 0)
        self.assertEqual(first["generation"], 1)
        self.assertEqual(first["module_ordinal"], 1)
        self.assertEqual(first["port_owner"], candidate.PORT_OWNER)
        self.assertEqual(first["port_type"], candidate.PORT_TYPE)
        self.assertEqual(first["module_id"], candidate.MODULE_ID)
        self.assertEqual(
            first["projection_policy"],
            candidate.PROJECTION_POLICY,
        )
        self.assertEqual(
            first["restoration_policy"],
            candidate.SOURCE_RESTORATION_CLASS,
        )
        self.assertEqual(
            first["input_boundary_id"],
            f"fnv1a64:{candidate.prompt_fnv1a64(tokens)}",
        )

    def test_same_carrier_advances_generation_and_lease(self) -> None:
        tokens = list(range(780))
        first = candidate.public_contract(
            trial="r2",
            edge=1,
            tokens=tokens,
            variant=0,
        )
        second = candidate.public_contract(
            trial="r2",
            edge=2,
            tokens=tokens,
            variant=0,
        )
        self.assertEqual(first["carrier_id"], second["carrier_id"])
        self.assertEqual((first["generation"], second["generation"]), (1, 2))
        self.assertEqual(
            (first["module_ordinal"], second["module_ordinal"]),
            (1, 2),
        )
        self.assertNotEqual(first["outer_lease"], second["outer_lease"])

    def test_capture_and_consumer_surfaces_do_not_expose_intermediates(self) -> None:
        contract = candidate.public_contract(
            trial="wire",
            edge=1,
            tokens=list(range(780)),
            variant=0,
        )
        capture = candidate.capture_payload({"prompt": list(range(780))}, contract)
        consumer = candidate.consumer_payload({"prompt": list(range(780))}, contract)
        self.assertEqual(capture["n_predict"], 0)
        self.assertTrue(capture["neo3000_capture_live_terminal_boundary"])
        self.assertTrue(consumer["neo3000_use_live_terminal_boundary"])
        encoded = repr((capture, consumer))
        for forbidden in (
            "probabilities",
            "angles",
            "scores",
            "phase_cells",
            "raw_logits",
        ):
            self.assertNotIn(forbidden, encoded)

    def test_public_prefix_plus_suffix_reconstructs_exact_D_state(self) -> None:
        record = {
            "content": 'D"}',
            "execution": {
                "generated_token_ids": [35, 8934, 248046],
                "finish_reason": "eos",
                "reasoning_content": None,
                "tool_calls": [],
            },
        }
        state = candidate.validate_suffix_state(
            record,
            codec=Codec(),
            props={"eos_token": "<eos>"},
            expected_answer="D",
        )
        self.assertEqual(state["answer"], "D")
        self.assertEqual(state["content"], '{"answer":"D"}')
        self.assertEqual(
            state["generated_token_ids"],
            [4754, 8944, 3147, 35, 8934, 248046],
        )
        self.assertEqual(
            state["generated_token_sha256"],
            candidate.parent.EXPECTED_GENERATED_SHA256["D"],
        )

    def test_single_hypothesis_control_requires_exact_limit_boundary(self) -> None:
        value = candidate.validate_single_hypothesis(
            {
                "content": "A",
                "completion_tokens": 1,
                "execution": {
                    "generated_token_ids": [32],
                    "finish_reason": "limit",
                },
            },
            expected_token=32,
        )
        self.assertEqual(value["token_id"], 32)
        with self.assertRaises(candidate.parent.ExperimentError):
            candidate.validate_single_hypothesis(
                {
                    "content": "B",
                    "completion_tokens": 1,
                    "execution": {
                        "generated_token_ids": [33],
                        "finish_reason": "limit",
                    },
                },
                expected_token=32,
            )

    def test_exact_oracle_is_independent_and_passes(self) -> None:
        value = candidate.exact_oracle.run_oracle()
        self.assertTrue(value["passed"])
        self.assertTrue(all(value["gates"].values()))
        self.assertEqual(
            value["contact"],
            {
                "model_callbacks": 0,
                "server_contacts": 0,
                "cuda_kernel_launches": 0,
            },
        )

    def test_static_audit_passes_without_runtime_contact(self) -> None:
        # Source successors lawfully make the consumed 0094 binary manifest
        # non-current. Exercise source/static gates here; the immutable
        # manifest was validated before 0094 and remains evidence-bound.
        original = candidate.DEFAULT_RUNTIME_MANIFEST
        candidate.DEFAULT_RUNTIME_MANIFEST = (
            candidate.ROOT
            / "lab"
            / "neo-exp-0094-consumed-manifest-not-current-for-static-test.json"
        )
        try:
            value = candidate.static_audit()
        finally:
            candidate.DEFAULT_RUNTIME_MANIFEST = original
        self.assertTrue(all(value["gates"].values()))
        self.assertFalse(value["scientific_contact"])

    def test_controller_freezes_exact_schedule(self) -> None:
        self.assertEqual(candidate.EXPECTED_MODEL_CALLBACKS, 38)
        self.assertEqual(candidate.EXPECTED_DIRECT_PROTOCOL_ACTIONS, 29)
        self.assertEqual(len(candidate.TUPLE_FIELDS), 12)
        self.assertEqual(candidate.INVERSE_FAULT_VARIANTS, (3, 4, 5))
        self.assertEqual(
            (candidate.NULL_VARIANT, candidate.PREMATURE_VARIANT),
            (6, 7),
        )

    def test_structural_hypothesis_device_bytes_include_public_extension(self) -> None:
        self.assertEqual(
            candidate.HYPOTHESIS_DEVICE_BYTES,
            candidate.parent.EXPECTED_CHILD_DEVICE_BYTES
            + candidate.HYPOTHESIS_FRESH_TOKENS
            * candidate.parent.DEVICE_BYTES_PER_TOKEN,
        )

    def test_sampled_process_peaks_uses_intermediate_rss_maximum(self) -> None:
        class Sidecar:
            baseline_rss_bytes = 100

            @staticmethod
            def telemetry():
                return {
                    "peak_dedicated_bytes": 900,
                    "samples": [
                        {"rss_bytes": 110},
                        {"rss_bytes": 500},
                        {"rss_bytes": 200},
                    ],
                }

        value = candidate.sampled_process_peaks(
            Sidecar(),
            evaluation_start_rss_bytes=110,
        )
        self.assertEqual(value["sample_count"], 3)
        self.assertEqual(value["peak_host_rss_bytes"], 500)
        self.assertEqual(
            value["peak_host_rss_growth_from_readiness_bytes"],
            400,
        )
        self.assertEqual(
            value["peak_host_rss_growth_from_evaluation_start_bytes"],
            390,
        )
        self.assertEqual(value["peak_gpu_dedicated_bytes"], 900)


if __name__ == "__main__":
    unittest.main()
