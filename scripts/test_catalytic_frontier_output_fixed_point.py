import unittest
from unittest import mock

import catalytic_frontier_output_fixed_point as fixed


class FakeCodec:
    eos = "<eos>"

    def detokenize(self, tokens):
        if tokens == [99]:
            return self.eos
        table = {
            (1, 2): '{"answer":"C"}',
            (3, 4): '{"answer":"D"}',
            (5, 6): '{"answer":"B"}',
        }
        return table[tuple(tokens)]

    def tokenize(self, text):
        if text == self.eos:
            return [99]
        raise AssertionError("visible output must not be retokenized")


class OutputFixedPointTests(unittest.TestCase):
    def test_transition_is_fixed_point_and_not_fanout(self):
        self.assertEqual(fixed.TRANSITION["C"], "D")
        self.assertEqual(fixed.TRANSITION["D"], "B")
        self.assertEqual(fixed.TRANSITION["B"], "B")
        self.assertEqual(fixed.EXPECTED_STATE_SEQUENCE, ("C", "D", "B", "B"))
        self.assertEqual(fixed.PAIR_ROUTE_ORDERS, (
            ("catalytic", "direct"),
            ("direct", "catalytic"),
            ("catalytic", "direct"),
        ))

    def test_generated_state_authenticates_exact_ids_without_retokenizing_visible_output(self):
        codec = FakeCodec()
        generated = [1, 2, 99]
        token_hash = fixed.harness.sha256_bytes(
            fixed.harness.carrier.canonical_json_bytes(generated)
        )
        record = {
            "content": '{"answer":"C"}',
            "execution": {
                "generated_token_ids": generated,
                "generated_token_sha256": token_hash,
                "finish_reason": "eos",
                "reasoning_content": "",
                "tool_calls": [],
            },
        }
        state = fixed.generated_state(record, codec=codec, props={"eos_token": "<eos>"})
        self.assertEqual(state["answer"], "C")
        self.assertEqual(state["visible_token_ids"], [1, 2])
        self.assertEqual(state["terminal_eog_id"], 99)

    def test_transition_request_contains_exact_prior_generated_array_after_root(self):
        codec = FakeCodec()
        root = list(range(fixed.ROOT_TOKEN_COUNT))
        base = [*root, 700]
        prior = {
            "answer": "C",
            "generated_token_ids": [1, 2, 99],
            "visible_token_ids": [1, 2],
            "terminal_eog_id": 99,
            "generated_token_sha256": "A" * 64,
        }
        suffix = {
            "suffix_tokens": [99, 800, 801],
            "suffix_token_count": 3,
            "suffix_token_sha256": "B" * 64,
        }
        with mock.patch.object(
            fixed.harness.carrier,
            "derive_continuation_suffix",
            return_value=suffix,
        ), mock.patch.object(
            fixed.harness.carrier,
            "_branch_payload",
            side_effect=lambda tokens, seed, cache_prompt: {
                "prompt": list(tokens),
                "seed": seed,
                "cache_prompt": cache_prompt,
            },
        ):
            tokens, payload, ancestry = fixed.derive_transition_request(
                codec=codec,
                base_branch_tokens=base,
                root_tokens=root,
                prior_state=prior,
                seed=7,
                cache_prompt=True,
            )
        self.assertEqual(tokens[: fixed.ROOT_TOKEN_COUNT], root)
        self.assertEqual(tokens[len(base) : len(base) + 3], [1, 2, 99])
        self.assertTrue(ancestry["prior_generated_tokens_exact_in_request"])
        self.assertFalse(ancestry["visible_content_retokenized"])
        self.assertTrue(payload["cache_prompt"])

    def test_classification_requires_integrity_saved_work_and_wall_gate(self):
        self.assertEqual(
            fixed.classify(integrity=True, saved_work_law=True, lifecycle_speedup=1.25),
            "cuda-root-output-derived-fixed-point-r3-supported-bounded",
        )
        self.assertEqual(
            fixed.classify(integrity=False, saved_work_law=True, lifecycle_speedup=9.0),
            "output-derived-fixed-point-integrity-failure",
        )
        self.assertEqual(
            fixed.classify(integrity=True, saved_work_law=False, lifecycle_speedup=9.0),
            "output-derived-fixed-point-saved-work-law-failure",
        )
        self.assertEqual(
            fixed.classify(integrity=True, saved_work_law=True, lifecycle_speedup=1.249),
            "output-derived-fixed-point-without-preregistered-wall-gate",
        )


if __name__ == "__main__":
    unittest.main()
