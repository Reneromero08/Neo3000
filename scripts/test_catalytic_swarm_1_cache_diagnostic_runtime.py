#!/usr/bin/env python3
"""CPU-only tests for the CS1 cache-diagnostic live runtime helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from catalytic_swarm_1_cache_diagnostic_runtime import (
    CacheDiagnosticRuntimeError,
    DiagnosticLedger,
    claim_json_once,
    common_prefix_token_count,
    diagnostic_paths,
    public_root_terminal_token_index,
    reconcile_request_boundaries,
    write_json,
)


class TokenGeometryTests(unittest.TestCase):
    def test_common_prefix_is_exact(self) -> None:
        self.assertEqual(common_prefix_token_count([1, 2, 3], [1, 2, 4]), 2)

    def test_common_prefix_rejects_boolean_token(self) -> None:
        with self.assertRaises(CacheDiagnosticRuntimeError):
            common_prefix_token_count([1, True], [1, 2])

    def test_root_terminal_index_finds_smallest_prefix(self) -> None:
        tokens = [ord(char) for char in "<s>ROOT</s>tail"]
        index = public_root_terminal_token_index(
            tokens,
            "ROOT",
            detokenize=lambda values: "".join(chr(value) for value in values),
        )
        self.assertEqual(index, len("<s>ROOT"))

    def test_root_terminal_index_rejects_missing_root(self) -> None:
        with self.assertRaises(CacheDiagnosticRuntimeError):
            public_root_terminal_token_index(
                [1, 2, 3],
                "ROOT",
                detokenize=lambda _values: "different",
            )


class RuntimePathTests(unittest.TestCase):
    def test_declared_paths_stay_inside_diagnostic_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo" / "state" / "catalytic_swarm_1_cache_diagnostic"
            paths = diagnostic_paths(root)
            self.assertEqual(set(paths), {"control", "readiness", "attempt", "result", "ledger"})
            for path in paths.values():
                path.resolve().relative_to(root.resolve())

    def test_claim_is_exclusive_and_write_is_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "state"
            path = root / "result.json"
            claim_json_once(path, {"status": "running"}, root=root)
            with self.assertRaises(FileExistsError):
                claim_json_once(path, {"status": "other"}, root=root)
            write_json(path, {"status": "complete"}, root=root)
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"status": "complete"},
            )

    def test_writer_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "state"
            with self.assertRaises(CacheDiagnosticRuntimeError):
                write_json(Path(temp) / "outside.json", {"x": 1}, root=root)


class LedgerTests(unittest.TestCase):
    def test_ledger_persists_three_metadata_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "state"
            ledger = DiagnosticLedger(root / "ledger.jsonl", root=root)
            for index in range(3):
                ledger.append({"kind": "probe", "label": str(index)})
            snapshot = ledger.snapshot()
            self.assertEqual(snapshot["record_count"], 3)
            self.assertTrue(snapshot["metadata_only"])
            self.assertTrue(snapshot["within_limits"])

    def test_ledger_rejects_fourth_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "state"
            ledger = DiagnosticLedger(root / "ledger.jsonl", root=root)
            for index in range(3):
                ledger.append({"kind": "probe", "label": str(index)})
            with self.assertRaises(CacheDiagnosticRuntimeError):
                ledger.append({"kind": "probe", "label": "overflow"})

    def test_ledger_rejects_forbidden_payload_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "state"
            ledger = DiagnosticLedger(root / "ledger.jsonl", root=root)
            with self.assertRaises(CacheDiagnosticRuntimeError):
                ledger.append({"kind": "probe", "raw_sse": "forbidden"})


class ReconciliationTests(unittest.TestCase):
    def test_full_three_request_reconciliation(self) -> None:
        labels = []
        for label in ("warm", "minimal", "realistic"):
            labels.extend(
                [
                    f"pre-request:cs1-cache-diagnostic-{label}",
                    f"post-request:cs1-cache-diagnostic-{label}",
                ]
            )
        result = reconcile_request_boundaries(
            labels,
            completed_requests=3,
            custody_checks=6,
            host_memory_checks=3,
            ledger_records=3,
        )
        self.assertTrue(result["passed"])
        self.assertTrue(result["full_schedule_completed"])

    def test_lawful_two_request_early_stop_reconciliation(self) -> None:
        labels = [
            "pre-request:cs1-cache-diagnostic-warm",
            "post-request:cs1-cache-diagnostic-warm",
            "pre-request:cs1-cache-diagnostic-minimal",
            "post-request:cs1-cache-diagnostic-minimal",
        ]
        result = reconcile_request_boundaries(
            labels,
            completed_requests=2,
            custody_checks=4,
            host_memory_checks=2,
            ledger_records=2,
        )
        self.assertTrue(result["passed"])
        self.assertFalse(result["full_schedule_completed"])

    def test_reconciliation_rejects_inherited_worker_labels(self) -> None:
        result = reconcile_request_boundaries(
            [
                "before-each-worker-request:worker-1",
                "after-each-worker-request:worker-1",
            ],
            completed_requests=1,
            custody_checks=2,
            host_memory_checks=1,
            ledger_records=1,
        )
        self.assertFalse(result["passed"])
        self.assertIn("pre-request-boundary-count", result["reasons"])


if __name__ == "__main__":
    unittest.main()
