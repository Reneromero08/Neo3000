#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import unittest

import ck0_binding2_preregistration_forensics as forensic


class ForensicTests(unittest.TestCase):
    def document(self) -> dict[str, object]:
        return {"b": [1, 2], "a": {"x": True}}

    def pretty_lf(self) -> bytes:
        return (json.dumps(self.document(), indent=2, sort_keys=True) + "\n").encode()

    def test_candidate_reconstructs_crlf_worktree(self) -> None:
        commit_blob = self.pretty_lf()
        expected = hashlib.sha256(commit_blob.replace(b"\n", b"\r\n")).hexdigest().upper()
        report = forensic.candidate_report(forensic.serialization_candidates(commit_blob), expected)
        self.assertIn("commit-blob-crlf", {item["name"] for item in report["matches"]})

    def test_candidate_reconstructs_pretty_preserve_order(self) -> None:
        commit_blob = self.pretty_lf()
        document = json.loads(commit_blob)
        candidate = (json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()
        expected = forensic.sha256_bytes(candidate)
        report = forensic.candidate_report(forensic.serialization_candidates(commit_blob), expected)
        self.assertTrue(report["matches"])

    def test_manifest_binding(self) -> None:
        manifest = {"balanced_preregistration": {"artifact_sha256": "A" * 64, "document_sha256": "B" * 64}}
        self.assertEqual(forensic.manifest_binding(manifest), ("A" * 64, "B" * 64))

    def test_semantic_hash_ignores_formatting(self) -> None:
        left = json.loads(self.pretty_lf())
        right = json.loads(json.dumps(self.document(), separators=(",", ":")))
        self.assertEqual(forensic.canonical_json_sha256(left), forensic.canonical_json_sha256(right))

    def test_candidate_no_match_is_empty(self) -> None:
        report = forensic.candidate_report(forensic.serialization_candidates(self.pretty_lf()), "F" * 64)
        self.assertEqual(report["matches"], [])


if __name__ == "__main__":
    unittest.main()
