#!/usr/bin/env python3
from __future__ import annotations

import base64
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import holostate_v1_warm_trajectory_related_task_evaluation_adjudication as adjudication


def sample_resources() -> dict[str, object]:
    return {
        "carrier_materialization": {
            "fresh_prompt_plus_completion_tokens": 4185,
        },
        "catalytic_task_b_suffix": {
            "fresh_prompt_plus_completion_tokens": 723,
        },
        "carrier_closure_readdress": {
            "fresh_prompt_plus_completion_tokens": 528,
        },
        "complete_catalytic_marginal": {
            "fresh_prompt_plus_completion_tokens": 5436,
            "correct_answers": 4,
        },
        "direct_task_b": {
            "fresh_prompt_plus_completion_tokens": 4908,
            "correct_answers": 4,
        },
        "integer_cross_products": {
            "complete_catalytic_tokens_x_direct_correct": 21744,
            "direct_tokens_x_complete_catalytic_correct": 19632,
        },
        "complete_catalytic_fresh_tokens_per_correct_strictly_lower": False,
        "secondary_suffix_only_diagnostic": {"decision_authority": False},
    }


class WarmTrajectoryAdjudicationTests(unittest.TestCase):
    def test_live_terminal_and_component_conclusion_remain_distinct(self) -> None:
        self.assertEqual(
            adjudication.ATTEMPT_LINEAGE[-1]["terminal_classification"],
            "INCONCLUSIVE",
        )
        self.assertEqual(
            adjudication.REUSE_CLASSIFICATION,
            "PROCESS_LOCAL_WARM_TRAJECTORY_EXACT_CHECKPOINT_REUSE_REPLICATED",
        )

    def test_exact_scientific_summary_passes(self) -> None:
        adjudication.validate_scientific_summary(
            adjudication.EXPECTED_AGGREGATE,
            adjudication.EXPECTED_CHECKPOINTS,
            sample_resources(),
        )

    def test_scoring_drift_is_rejected(self) -> None:
        aggregate = dict(adjudication.EXPECTED_AGGREGATE)
        aggregate["catalytic_task_b_correct"] = 3
        with self.assertRaisesRegex(
            adjudication.WarmTrajectoryAdjudicationError,
            "aggregate scoring changed",
        ):
            adjudication.validate_scientific_summary(
                aggregate,
                adjudication.EXPECTED_CHECKPOINTS,
                sample_resources(),
            )

    def test_complete_cycle_accounting_preserves_negative_advantage(self) -> None:
        self.assertEqual(4185 + 723, 4908)
        self.assertEqual(4908 + 528, 5436)
        self.assertGreater(5436 * 4, 4908 * 4)
        self.assertEqual(
            adjudication.EFFICIENCY_CLASSIFICATION,
            "SINGLE_BRANCH_COMPLETE_CATALYTIC_CYCLE_FRESH_TOKEN_ADVANTAGE_NOT_SUPPORTED",
        )

    def test_native_sse_zero_cache_is_not_replaced_by_terminal_counter(self) -> None:
        events = [
            {"prompt_progress": {"total": 1, "cache": 0}},
            {"content": "X", "tokens": [7]},
            {
                "stop": True,
                "stop_type": "eos",
                "tokens_evaluated": 1,
                "tokens_cached": 99,
                "tokens_predicted": 1,
                "timings": {"predicted_n": 1},
            },
        ]
        raw = b"".join(
            b"data: "
            + json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
            + b"\n\n"
            for event in events
        )
        capture = {
            "raw_response_capture": {
                "bytes": base64.b64encode(raw).decode("ascii"),
                "sha256": hashlib.sha256(raw).hexdigest().upper(),
            },
            "execution": {
                "content": "X",
                "prompt_tokens": 1,
                "cached_prompt_tokens": 0,
                "completion_tokens": 1,
                "generated_token_ids": [7],
                "generated_token_count": 1,
                "finish_reason": "eos",
                "event_count": 3,
                "http_status": 200,
                "terminal_stop_evidence": {"observed": True, "stop": True},
            },
        }
        replay = adjudication._replay_raw_sse(capture, "synthetic-task-b-direct")
        self.assertEqual(replay["event_count"], 3)

    def test_disclosure_boundary_rejects_protected_material(self) -> None:
        for field in (
            "expected_task_a_answer",
            "expected_task_b_answer",
            "private_salt_hex",
            "task_to_cell",
            "private_root",
            "raw_authority_id",
        ):
            with self.subTest(field=field), self.assertRaises(Exception):
                adjudication.validate_disclosure_boundary({field: "hidden"})

    def test_ledger_append_boundary_requires_neo_exp_0047_at_line_sixty(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / "lab").mkdir()
            lines = [
                adjudication.canonical_json_text({"id": f"prior-{index:04d}"})
                for index in range(1, 61)
            ]
            lines[-1] = adjudication.canonical_json_text(
                {"id": adjudication.PREDECESSOR_RECORD_ID}
            )
            (repository / adjudication.RESULTS_PATH).write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )
            adjudication.validate_ledger_append_boundary(repository)

    def test_publication_requires_exact_record_at_line_sixty_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / "lab").mkdir()
            artifact = {"schema_version": 1, "safe": True}
            record = {"id": adjudication.RECORD_ID, "safe": True}
            (repository / adjudication.ARTIFACT_PATH).write_bytes(
                adjudication.canonical_json_bytes(artifact) + b"\n"
            )
            prior = [
                adjudication.canonical_json_text({"id": f"prior-{index:04d}"})
                for index in range(1, 61)
            ]
            prior.append(adjudication.canonical_json_text(record))
            (repository / adjudication.RESULTS_PATH).write_text(
                "\n".join(prior) + "\n", encoding="utf-8"
            )
            original_artifact = adjudication.render_adjudication
            original_record = adjudication.render_record
            try:
                adjudication.render_adjudication = lambda _repository: copy.deepcopy(artifact)
                adjudication.render_record = (
                    lambda _repository, _artifact=None: copy.deepcopy(record)
                )
                result = adjudication.validate_publication(repository)
            finally:
                adjudication.render_adjudication = original_artifact
                adjudication.render_record = original_record
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["ledger_line"], 61)


if __name__ == "__main__":
    unittest.main(verbosity=2)
