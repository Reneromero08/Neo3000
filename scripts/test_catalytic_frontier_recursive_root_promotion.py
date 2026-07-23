import unittest
from unittest import mock

import catalytic_frontier_recursive_root_promotion as rolling


class FakeCodec:
    pass


class RecursiveRootPromotionTests(unittest.TestCase):
    def response(self, action, root_id, tokens, after=None):
        device = 79_974_400
        gpu = 79_974_400
        host = 17_540 + tokens * 4
        return {
            "action": action,
            "root_id": root_id,
            "id_slot": 0,
            "n_tokens": tokens,
            "n_bytes": host + device,
            "n_host_bytes": host,
            "n_device_bytes": device,
            "n_device_bytes_after": device if after is None else after,
            "n_gpu_bytes": gpu,
            "n_gpu_bytes_after": gpu if after is None else after,
            "n_checkpoints": 0,
            "timings": {"root_ms": 2.0},
        }

    def test_root_ids_are_distinct_across_recurrence(self):
        ids = [rolling.PARENT_ROOT_ID]
        ids.extend(
            rolling.child_root_id(step, answer)
            for step, answer in enumerate(("C", "D", "B", "B"))
        )
        self.assertEqual(len(ids), len(set(ids)))

    def test_named_root_validator_requires_exact_identity_and_erase_closure(self):
        saved = rolling.validate_named_root(
            self.response("root-save", "r0", 695),
            action="root-save",
            root_id="r0",
            expected_tokens=695,
        )
        restored = rolling.validate_named_root(
            self.response("root-restore", "r0", 695),
            action="root-restore",
            root_id="r0",
            expected=saved,
        )
        self.assertEqual(restored["n_tokens"], 695)
        erased = rolling.validate_named_root(
            self.response("root-erase", "r0", 695, after=0),
            action="root-erase",
            root_id="r0",
            expected=saved,
        )
        self.assertEqual(erased["n_device_bytes_after"], 0)
        with self.assertRaises(Exception):
            rolling.validate_named_root(
                self.response("root-erase", "r0", 695),
                action="root-erase",
                root_id="r0",
                expected=saved,
            )

    def test_promoted_successor_reconstructs_generated_ids_across_root_boundary(self):
        root = [10, 11, 1, 2]
        prior = {
            "answer": "C",
            "visible_token_ids": [1, 2],
            "generated_token_ids": [1, 2, 99],
            "terminal_eog_id": 99,
            "generated_token_sha256": "A" * 64,
        }
        suffix = {
            "suffix_tokens": [99, 800, 801],
            "suffix_token_count": 3,
            "suffix_token_sha256": "B" * 64,
        }
        with mock.patch.object(
            rolling.harness.carrier,
            "derive_continuation_suffix",
            return_value=suffix,
        ), mock.patch.object(
            rolling.harness.carrier,
            "_branch_payload",
            side_effect=lambda tokens, seed, cache_prompt: {
                "prompt": list(tokens),
                "seed": seed,
                "cache_prompt": cache_prompt,
            },
        ):
            tokens, payload, ancestry = rolling.derive_promoted_successor(
                codec=FakeCodec(),
                root_tokens=root,
                prior_state=prior,
                seed=7,
                cache_prompt=True,
            )
        self.assertEqual(tokens, [10, 11, 1, 2, 99, 800, 801])
        self.assertTrue(ancestry["prior_generated_tokens_exact_across_root_boundary"])
        self.assertFalse(ancestry["visible_output_retokenized"])
        self.assertTrue(payload["cache_prompt"])

    def test_promotion_erases_parent_before_saving_child(self):
        parent = rolling.validate_named_root(
            self.response("root-save", "parent", 689),
            action="root-save",
            root_id="parent",
        )
        calls = []

        def action(*, action, root_id):
            calls.append((action, root_id))
            if action == "root-erase":
                return self.response(action, root_id, 689, after=0), 0.01
            return self.response(action, root_id, 695), 0.02

        with mock.patch.object(rolling.harness, "ram_root_action", side_effect=action):
            child, operations = rolling.promote_live_root(
                current_root=parent,
                next_root_id="child",
                next_root_tokens=list(range(695)),
                label="test",
            )
        self.assertEqual(calls, [("root-erase", "parent"), ("root-save", "child")])
        self.assertEqual([item["action"] for item in operations], ["root-erase", "root-save"])
        self.assertEqual(child["n_tokens"], 695)

    def test_classification_requires_integrity_growth_and_full_lifecycle_speed(self):
        self.assertEqual(
            rolling.classify(integrity=True, boundary_growth=True, lifecycle_speedup=1.25),
            "rolling-output-bearing-cuda-root-promotion-r3-supported-bounded",
        )
        self.assertEqual(
            rolling.classify(integrity=False, boundary_growth=True, lifecycle_speedup=9.0),
            "rolling-output-root-promotion-integrity-failure",
        )
        self.assertEqual(
            rolling.classify(integrity=True, boundary_growth=False, lifecycle_speedup=9.0),
            "rolling-output-root-promotion-without-boundary-growth",
        )


if __name__ == "__main__":
    unittest.main()
