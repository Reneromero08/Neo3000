#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from catalytic_runtime_custody import (
    DEFAULT_HISTORICAL_CS1_ROOTS,
    CustodyViolation,
    capture_preclaim_custody,
    validate_postclaim_custody,
)


ROOT = Path(__file__).resolve().parents[1]
AUTHORIZED_ROOT = "state/catalytic_swarm_1_v6"
ALLOWED_PATHS = (
    f"{AUTHORIZED_ROOT}/control-qualification-v6.json",
    f"{AUTHORIZED_ROOT}/readiness-v6.json",
    f"{AUTHORIZED_ROOT}/parser-canary-v6.json",
    f"{AUTHORIZED_ROOT}/attempt-v6.json",
    f"{AUTHORIZED_ROOT}/result-v6.json",
    f"{AUTHORIZED_ROOT}/ledger-v6.jsonl",
    f"{AUTHORIZED_ROOT}/task-results-v6.json",
)


class TemporaryCustodyRepository:
    def __init__(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.git("init", "--quiet")
        self.git("config", "user.name", "Custody Test")
        self.git("config", "user.email", "custody@example.invalid")
        self.write(".gitignore", (ROOT / ".gitignore").read_text(encoding="utf-8"))
        self.write("tracked.txt", "baseline\n")
        self.git("add", ".gitignore", "tracked.txt")
        self.git("commit", "--quiet", "-m", "baseline")

    def close(self) -> None:
        self.temporary_directory.cleanup()

    def git(
        self,
        *arguments: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.root), *arguments],
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
        )

    def write(self, relative: str, value: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
        return path

    def seed_historical_evidence(self) -> None:
        self.write("state/catalytic_swarm_1/control-v1.json", "v1\n")
        self.write(
            "state/catalytic_swarm_1_cache_diagnostic/result-v1.json",
            "diagnostic\n",
        )
        # V2 intentionally stays absent; absence is part of its consumed boundary.
        self.write("state/catalytic_swarm_1_v3/control-v3.json", "v3\n")
        self.write("state/catalytic_swarm_1_v4/result-v4.json", "v4\n")
        self.write("state/catalytic_swarm_1_v5/result-v5.json", "v5\n")


class CatalyticRuntimeCustodyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = TemporaryCustodyRepository()
        self.addCleanup(self.repository.close)

    def capture(self):
        return capture_preclaim_custody(
            self.repository.root,
            authorized_root=AUTHORIZED_ROOT,
            allowed_paths=ALLOWED_PATHS,
        )

    # Prompt case 1: generic version ignore, preserved base/diagnostic ignores,
    # and no blanket state ignore.
    def test_ignore_policy_is_generic_but_not_blanket(self) -> None:
        ignore_lines = {
            line.strip()
            for line in (self.repository.root / ".gitignore")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertIn("/state/catalytic_swarm_1_v*/", ignore_lines)
        self.assertIn("/state/catalytic_inference_bench_0/", ignore_lines)
        self.assertIn("state/catalytic_swarm_1/", ignore_lines)
        self.assertIn("state/catalytic_swarm_1_cache_diagnostic/", ignore_lines)
        for version in range(2, 6):
            self.assertNotIn(f"state/catalytic_swarm_1_v{version}/", ignore_lines)
        self.assertNotIn("state/", ignore_lines)
        self.assertNotIn("/state/", ignore_lines)

        ignored = (
            "state/catalytic_swarm_1/base.json",
            "state/catalytic_swarm_1_cache_diagnostic/diagnostic.json",
            "state/catalytic_swarm_1_v2/v2.json",
            "state/catalytic_swarm_1_v5/v5.json",
            "state/catalytic_swarm_1_v6/v6.json",
            "state/catalytic_swarm_1_v99/v99.json",
            "state/catalytic_inference_bench_0/result.json",
        )
        for path in ignored:
            self.repository.write(path, "ignored\n")
            result = self.repository.git("check-ignore", "--quiet", "--", path)
            self.assertEqual(result.returncode, 0, path)

        ordinary = "state/ordinary-evidence.txt"
        self.repository.write(ordinary, "must remain visible\n")
        result = self.repository.git(
            "check-ignore", "--quiet", "--", ordinary, check=False
        )
        self.assertEqual(result.returncode, 1)

    # Prompt case 2: clean ordinary and tracked status plus every predecessor
    # namespace are captured before claim.
    def test_clean_preclaim_captures_status_and_historical_hashes(self) -> None:
        self.repository.seed_historical_evidence()
        snapshot = self.capture()
        self.assertTrue(snapshot.status_before_inventory.clean)
        self.assertTrue(snapshot.status_after_inventory.clean)
        self.assertEqual(snapshot.status_before_inventory.untracked_paths, ())
        self.assertEqual(snapshot.status_before_inventory.tracked_worktree_paths, ())
        self.assertEqual(snapshot.status_before_inventory.staged_paths, ())
        self.assertEqual(snapshot.historical_roots, DEFAULT_HISTORICAL_CS1_ROOTS)
        historical = {value.root: value for value in snapshot.historical_namespaces}
        self.assertEqual(set(historical), set(DEFAULT_HISTORICAL_CS1_ROOTS))
        self.assertFalse(historical["state/catalytic_swarm_1_v2"].exists)
        self.assertTrue(historical["state/catalytic_swarm_1_v5"].exists)
        self.assertEqual(len(historical["state/catalytic_swarm_1_v5"].sha256), 64)
        self.assertIn(
            "state/catalytic_swarm_1_v5/result-v5.json",
            snapshot.ignored_evidence_paths,
        )

    # Prompt case 3: preclaim ordinary untracked dirt is rejected.
    def test_preclaim_rejects_untracked_change(self) -> None:
        self.repository.write("outside.txt", "untracked\n")
        with self.assertRaisesRegex(CustodyViolation, "preclaim worktree is not clean"):
            self.capture()

    # Prompt case 4: preclaim tracked unstaged dirt is rejected explicitly.
    def test_preclaim_rejects_tracked_unstaged_change(self) -> None:
        self.repository.write("tracked.txt", "changed\n")
        with self.assertRaisesRegex(CustodyViolation, "preclaim worktree is not clean"):
            self.capture()

    # Prompt case 5: preclaim staged dirt is rejected explicitly.
    def test_preclaim_rejects_staged_change(self) -> None:
        self.repository.write("tracked.txt", "staged\n")
        self.repository.git("add", "tracked.txt")
        with self.assertRaisesRegex(CustodyViolation, "preclaim worktree is not clean"):
            self.capture()

    # Prompt case 6: an ignored claim artifact is accepted only at an exact
    # allowed path and is inventoried with its byte hash.
    def test_postclaim_accepts_exact_allowed_ignored_artifact(self) -> None:
        self.repository.seed_historical_evidence()
        snapshot = self.capture()
        payload = "{\"claimed\":true}\n"
        claimed = self.repository.write(ALLOWED_PATHS[0], payload)
        report = validate_postclaim_custody(snapshot)
        self.assertTrue(report.status.clean)
        self.assertIn(ALLOWED_PATHS[0], report.changed_evidence_paths)
        self.assertIn(ALLOWED_PATHS[0], report.ignored_evidence_paths)
        expected_hash = hashlib.sha256(claimed.read_bytes()).hexdigest()
        observed = next(
            entry
            for namespace in report.evidence_namespaces
            if namespace.root == AUTHORIZED_ROOT
            for entry in namespace.entries
            if entry.path == ALLOWED_PATHS[0]
        )
        self.assertEqual(observed.sha256, expected_hash)
        self.assertTrue(observed.ignored)

    # Prompt case 7: outside untracked postclaim dirt is rejected.
    def test_postclaim_rejects_outside_untracked_change(self) -> None:
        snapshot = self.capture()
        self.repository.write("outside.txt", "untracked\n")
        with self.assertRaisesRegex(CustodyViolation, "Git changes escaped"):
            validate_postclaim_custody(snapshot)

    # Prompt case 8: staged postclaim dirt is rejected even when its path is
    # otherwise an exact runtime allowlist member.
    def test_postclaim_rejects_staged_change_at_allowed_path(self) -> None:
        snapshot = self.capture()
        self.repository.write(ALLOWED_PATHS[0], "tracked runtime smuggle\n")
        self.repository.git("add", "-f", ALLOWED_PATHS[0])
        with self.assertRaisesRegex(CustodyViolation, "tracked or staged"):
            validate_postclaim_custody(snapshot)

    def test_postclaim_rejects_tracked_unstaged_change_at_allowed_path(self) -> None:
        self.repository.write(ALLOWED_PATHS[0], "tracked baseline\n")
        self.repository.git("add", "-f", ALLOWED_PATHS[0])
        self.repository.git("commit", "--quiet", "-m", "tracked runtime baseline")
        snapshot = self.capture()
        self.repository.write(ALLOWED_PATHS[0], "tracked mutation\n")
        with self.assertRaisesRegex(CustodyViolation, "tracked or staged"):
            validate_postclaim_custody(snapshot)

    # Prompt case 9: outside staged postclaim dirt is rejected.
    def test_postclaim_rejects_outside_staged_change(self) -> None:
        snapshot = self.capture()
        self.repository.write("tracked.txt", "staged\n")
        self.repository.git("add", "tracked.txt")
        with self.assertRaisesRegex(CustodyViolation, "tracked or staged"):
            validate_postclaim_custody(snapshot)

    # Prompt case 10: ignored predecessor evidence is hash-bound and immutable.
    def test_postclaim_rejects_predecessor_root_change(self) -> None:
        self.repository.seed_historical_evidence()
        snapshot = self.capture()
        self.repository.write("state/catalytic_swarm_1_v5/result-v5.json", "mutated\n")
        self.assertEqual(
            self.repository.git("status", "--porcelain=v1").stdout,
            "",
            "the test must prove ordinary Git status cannot see ignored mutation",
        )
        with self.assertRaisesRegex(CustodyViolation, "predecessor namespace changed"):
            validate_postclaim_custody(snapshot)

    def test_postclaim_rejects_unlisted_path_inside_authorized_root(self) -> None:
        snapshot = self.capture()
        self.repository.write(f"{AUTHORIZED_ROOT}/unexpected.json", "unexpected\n")
        with self.assertRaisesRegex(CustodyViolation, "ignored evidence escaped"):
            validate_postclaim_custody(snapshot)

    def test_postclaim_rejects_ignored_unknown_successor_namespace(self) -> None:
        snapshot = self.capture()
        self.repository.write(ALLOWED_PATHS[0], "authorized\n")
        path = "state/catalytic_swarm_1_v99/control-v99.json"
        self.repository.write(path, "unauthorized successor\n")
        self.assertEqual(
            self.repository.git("status", "--porcelain=v1").stdout,
            "",
            "the generic ignore must hide the successor from ordinary status",
        )
        with self.assertRaisesRegex(CustodyViolation, "ignored evidence escaped"):
            validate_postclaim_custody(snapshot)

    def test_preexisting_discovered_namespace_is_historical_and_immutable(self) -> None:
        path = "state/catalytic_swarm_1_v99/control-v99.json"
        self.repository.write(path, "preexisting successor\n")
        snapshot = self.capture()
        self.assertIn("state/catalytic_swarm_1_v99", snapshot.historical_roots)
        self.repository.write(path, "mutated historical namespace\n")
        with self.assertRaisesRegex(CustodyViolation, "predecessor namespace changed"):
            validate_postclaim_custody(snapshot)

    def test_postclaim_rejects_directory_at_exact_artifact_path(self) -> None:
        snapshot = self.capture()
        (self.repository.root / ALLOWED_PATHS[0]).mkdir(parents=True)
        with self.assertRaisesRegex(CustodyViolation, "not a regular file"):
            validate_postclaim_custody(snapshot)


if __name__ == "__main__":
    unittest.main()
