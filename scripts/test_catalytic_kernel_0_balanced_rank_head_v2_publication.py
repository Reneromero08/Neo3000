#!/usr/bin/env python3

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import catalytic_kernel_0_balanced_rank_head_v2_publication as publication
import catalytic_kernel_0_balanced_rank_head_v2_run_design as run_design


def sample_record() -> dict:
    return {
        "id": publication.RECORD_ID,
        "checkpoint": "test",
        "hypothesis": "test",
        "intervention": "test",
        "baseline_commit": "1" * 40,
        "candidate_commit": None,
        "model_hash": "2" * 64,
        "configuration": {"run_id": publication.RUN_ID},
        "metrics_before": {},
        "metrics_after": {
            "terminal_classification": publication.CLASSIFICATION,
            "manifest_sha256": "3" * 64,
            "result_sha256": "4" * 64,
            "closure_sha256": "5" * 64,
        },
        "quality_gates": {
            "binding_2_parent_dependence_locked": True,
            "causal_replication_across_bindings_locked": True,
        },
        "verdict": "accept",
        "next_boundary": "test",
    }


class RankHeadV2PublicationTests(unittest.TestCase):
    def write_ledger(self, repository: Path, records: list[dict]) -> None:
        lab = repository / "lab"
        lab.mkdir(exist_ok=True)
        (lab / "results.jsonl").write_text(
            "".join(publication.canonical_json_text(item) + "\n" for item in records),
            encoding="utf-8",
        )

    def test_publication_tooling_is_outside_frozen_runtime_binding(self) -> None:
        self.assertNotIn(
            "scripts/catalytic_kernel_0_balanced_rank_head_v2_publication.py",
            run_design.REQUIRED_IMPLEMENTATION_PATHS,
        )
        self.assertNotIn(
            "scripts/test_catalytic_kernel_0_balanced_rank_head_v2_publication.py",
            run_design.REQUIRED_IMPLEMENTATION_PATHS,
        )
        self.assertEqual(len(run_design.REQUIRED_IMPLEMENTATION_PATHS), 18)
        source = Path(publication.__file__).read_text(encoding="utf-8")
        self.assertNotIn("ck0-balanced-v2-rank-head-b1-full-r2", source)
        self.assertNotIn("FE63B84FDFBD", source)

    def test_record_requires_exact_split_layout_and_canonical_size(self) -> None:
        record = sample_record()
        publication._validate_record_shape(record)
        publication.validate_disclosure_boundary(record)
        line = publication.canonical_json_text(record)
        self.assertLessEqual(len(line.encode("utf-8")), publication.MAX_RECORD_BYTES)
        self.assertNotIn("\n", line)

    def test_record_requires_both_cross_binding_claim_locks(self) -> None:
        for field in (
            "binding_2_parent_dependence_locked",
            "causal_replication_across_bindings_locked",
        ):
            with self.subTest(field=field):
                record = sample_record()
                del record["quality_gates"][field]
                with self.assertRaisesRegex(
                    publication.RankHeadV2PublicationError,
                    "cross-binding claim lock",
                ):
                    publication._validate_record_shape(record)

    def test_source_claim_boundary_matches_frozen_live_contract(self) -> None:
        manifest = {
            "claims": dict(publication.live.CLAIMS),
            "claiming": False,
            "automatic_promotion": False,
        }
        result = copy.deepcopy(manifest)
        publication._require_source_claim_boundary(manifest, result)
        result["claims"]["BINDING_2_PARENT_DEPENDENCE"] = "UNLOCKED"
        with self.assertRaisesRegex(
            publication.RankHeadV2PublicationError,
            "source claim boundary",
        ):
            publication._require_source_claim_boundary(manifest, result)

    def test_exact_split_record_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            record = sample_record()
            self.write_ledger(repository, [record])
            result = publication.validate_ledger_record(
                repository,
                record,
                require_predecessor_gate=False,
            )
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["layout"], "split-experiment-record")
        self.assertEqual(result["ledger_line"], 1)

    def test_duplicate_record_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            record = sample_record()
            self.write_ledger(repository, [record, record])
            with self.assertRaisesRegex(
                publication.RankHeadV2PublicationError,
                "exactly one active rank-head-v2 publication",
            ):
                publication.validate_ledger_record(
                    repository,
                    record,
                    require_predecessor_gate=False,
                )

    def test_wrong_raw_hash_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            expected = sample_record()
            observed = copy.deepcopy(expected)
            observed["metrics_after"]["manifest_sha256"] = "0" * 64
            self.write_ledger(repository, [observed])
            with self.assertRaisesRegex(
                publication.RankHeadV2PublicationError,
                "differs from independently rendered",
            ):
                publication.validate_ledger_record(
                    repository,
                    expected,
                    require_predecessor_gate=False,
                )

    def test_wrong_classification_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            expected = sample_record()
            observed = copy.deepcopy(expected)
            observed["metrics_after"]["terminal_classification"] = "INCONCLUSIVE"
            self.write_ledger(repository, [observed])
            with self.assertRaisesRegex(
                publication.RankHeadV2PublicationError,
                "exactly one active rank-head-v2 publication",
            ):
                publication.validate_ledger_record(
                    repository,
                    expected,
                    require_predecessor_gate=False,
                )

    def test_private_alias_and_ranking_are_rejected(self) -> None:
        for field, value in (
            ("candidate_alias", "K07"),
            ("ranking", ["K07", "K08", "K09"]),
            ("alias_map", {"K07": "C34"}),
            ("private_root", "state/private"),
            ("run_key", "secret"),
            ("cross_binding_correspondence", {"left": "right"}),
        ):
            with self.subTest(field=field):
                record = sample_record()
                record["metrics_after"][field] = value
                with self.assertRaisesRegex(
                    publication.RankHeadV2PublicationError,
                    "forbidden field",
                ):
                    publication.validate_disclosure_boundary(record)

    def test_legacy_co_located_match_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            record = sample_record()
            legacy = {
                "result": {
                    "run_id": publication.RUN_ID,
                    "terminal_classification": publication.CLASSIFICATION,
                }
            }
            self.write_ledger(repository, [record, legacy])
            with self.assertRaisesRegex(
                publication.RankHeadV2PublicationError,
                "legacy co-located",
            ):
                publication.validate_ledger_record(
                    repository,
                    record,
                    require_predecessor_gate=False,
                )

    def test_missing_receipt_fails_before_other_reconstruction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                publication.RankHeadV2PublicationError,
                "receipt did not verify",
            ):
                publication.render_publication_record(Path(temporary))

    def test_malformed_authority_receipt_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            receipt = publication.authority.authority_receipt_path(
                repository,
                publication.RUN_ID,
            )
            receipt.parent.mkdir(parents=True)
            receipt.write_text(json.dumps({"malformed": True}), encoding="utf-8")
            with self.assertRaisesRegex(
                publication.RankHeadV2PublicationError,
                "receipt did not verify",
            ):
                publication.render_publication_record(repository)

    def test_noncanonical_target_line_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            record = sample_record()
            lab = repository / "lab"
            lab.mkdir()
            (lab / "results.jsonl").write_text(
                json.dumps(record, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(publication.RankHeadV2PublicationError):
                publication.validate_ledger_record(
                    repository,
                    record,
                    require_predecessor_gate=False,
                )


if __name__ == "__main__":
    unittest.main()
