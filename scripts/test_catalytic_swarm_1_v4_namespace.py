#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from catalytic_swarm_1_v4_namespace import (
    ONE_SHOT_KEYS,
    VersionedPathLawError,
    normalized_relative_paths,
    qualify_versioned_one_shot_paths,
)


def paths(namespace: str = "state/catalytic_swarm_1_v4") -> dict[str, str]:
    return {
        "control": f"{namespace}/control-qualification-v4.json",
        "readiness": f"{namespace}/readiness-v4.json",
        "parser_canary": f"{namespace}/parser-canary-v4.json",
        "attempt": f"{namespace}/attempt-v4.json",
        "result": f"{namespace}/result-v4.json",
        "ledger": f"{namespace}/ledger-v4.jsonl",
        "task_results": f"{namespace}/task-results-v4.json",
    }


class V4NamespaceTests(unittest.TestCase):
    def qualify(self, declared: dict[str, str], active: tuple[Path, ...] | None = None):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            active = active or tuple(root / declared[key] for key in ONE_SHOT_KEYS)
            return qualify_versioned_one_shot_paths(
                repo_root=root,
                contract_paths=declared,
                active_artifact_paths=active,
                required_namespace="state/catalytic_swarm_1_v4",
                forbidden_namespaces=(
                    "state/catalytic_swarm_1",
                    "state/catalytic_swarm_1_cache_diagnostic",
                    "state/catalytic_swarm_1_v2",
                    "state/catalytic_swarm_1_v3",
                ),
            )

    def test_canonical_order_passes(self) -> None:
        self.assertTrue(self.qualify(paths())["passed"])

    def test_alphabetical_order_passes(self) -> None:
        declared = {key: paths()[key] for key in sorted(paths())}
        self.assertTrue(self.qualify(declared)["passed"])

    def test_sorted_json_round_trip_passes(self) -> None:
        declared = json.loads(json.dumps(paths(), sort_keys=True))
        self.assertTrue(self.qualify(declared)["passed"])

    def test_projection_returns_canonical_stage_order(self) -> None:
        declared = {key: paths()[key] for key in reversed(tuple(paths()))}
        self.assertEqual(tuple(normalized_relative_paths(declared)), ONE_SHOT_KEYS)

    def test_exact_path_to_stage_correspondence(self) -> None:
        result = self.qualify({key: paths()[key] for key in sorted(paths())})
        self.assertEqual(tuple(result["relative_paths"]), ONE_SHOT_KEYS)
        self.assertFalse(result["source_mapping_order_authoritative"])

    def test_missing_key_rejects(self) -> None:
        declared = paths(); declared.pop("ledger")
        with self.assertRaisesRegex(VersionedPathLawError, "semantic key set"):
            normalized_relative_paths(declared)

    def test_extra_key_rejects(self) -> None:
        declared = paths(); declared["extra"] = "state/catalytic_swarm_1_v4/extra.json"
        with self.assertRaisesRegex(VersionedPathLawError, "semantic key set"):
            normalized_relative_paths(declared)

    def test_empty_and_nonstring_paths_reject(self) -> None:
        for value in ("", None):
            declared = paths(); declared["result"] = value  # type: ignore[assignment]
            with self.assertRaisesRegex(VersionedPathLawError, "invalid"):
                normalized_relative_paths(declared)

    def test_path_escape_rejects(self) -> None:
        declared = paths(); declared["result"] = "../escape.json"
        with self.assertRaisesRegex(VersionedPathLawError, "escapes"):
            normalized_relative_paths(declared)

    def test_wrong_namespace_rejects(self) -> None:
        declared = paths(); declared["control"] = "state/wrong/control.json"
        with self.assertRaisesRegex(VersionedPathLawError, "outside required namespace"):
            self.qualify(declared)

    def test_every_consumed_namespace_rejects(self) -> None:
        for namespace in (
            "state/catalytic_swarm_1",
            "state/catalytic_swarm_1_cache_diagnostic",
            "state/catalytic_swarm_1_v2",
            "state/catalytic_swarm_1_v3",
        ):
            declared = paths(); declared["control"] = f"{namespace}/control.json"
            with self.assertRaises(VersionedPathLawError):
                self.qualify(declared)

    def test_runtime_tuple_cardinality_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); declared = paths()
            with self.assertRaisesRegex(VersionedPathLawError, "cardinality"):
                qualify_versioned_one_shot_paths(
                    repo_root=root, contract_paths=declared,
                    active_artifact_paths=tuple(root / declared[key] for key in ONE_SHOT_KEYS[:-1]),
                    required_namespace="state/catalytic_swarm_1_v4",
                )

    def test_runtime_tuple_stage_mismatch_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); declared = paths()
            active = [root / declared[key] for key in ONE_SHOT_KEYS]
            active[0], active[1] = active[1], active[0]
            with self.assertRaisesRegex(VersionedPathLawError, "runtime paths differ"):
                qualify_versioned_one_shot_paths(
                    repo_root=root, contract_paths=declared,
                    active_artifact_paths=tuple(active),
                    required_namespace="state/catalytic_swarm_1_v4",
                )


if __name__ == "__main__":
    unittest.main()
