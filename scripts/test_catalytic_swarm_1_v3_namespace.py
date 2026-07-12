#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from catalytic_swarm_1_v3_namespace import (
    ONE_SHOT_KEYS,
    VersionedPathLawError,
    qualify_versioned_one_shot_paths,
)


def paths(namespace: str) -> dict[str, str]:
    version = namespace.rsplit("_v", 1)[-1]
    return {
        "control": f"{namespace}/control-qualification-v{version}.json",
        "readiness": f"{namespace}/readiness-v{version}.json",
        "parser_canary": f"{namespace}/parser-canary-v{version}.json",
        "attempt": f"{namespace}/attempt-v{version}.json",
        "result": f"{namespace}/result-v{version}.json",
        "ledger": f"{namespace}/ledger-v{version}.jsonl",
        "task_results": f"{namespace}/task-results-v{version}.json",
    }


class VersionedNamespaceTests(unittest.TestCase):
    def test_v3_active_contract_and_runtime_paths_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            declared = paths("state/catalytic_swarm_1_v3")
            active = tuple(root / declared[key] for key in ONE_SHOT_KEYS)
            result = qualify_versioned_one_shot_paths(
                repo_root=root,
                contract_paths=declared,
                active_artifact_paths=active,
                required_namespace="state/catalytic_swarm_1_v3",
                forbidden_namespaces=(
                    "state/catalytic_swarm_1",
                    "state/catalytic_swarm_1_cache_diagnostic",
                    "state/catalytic_swarm_1_v2",
                ),
            )
            self.assertTrue(result["passed"])
            self.assertFalse(result["inherited_v1_map_consulted"])

    def test_reproduces_inherited_v1_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            v1 = paths("state/catalytic_swarm_1_v1")
            v2 = paths("state/catalytic_swarm_1_v2")
            active_v2 = tuple(root / v2[key] for key in ONE_SHOT_KEYS)
            with self.assertRaisesRegex(
                VersionedPathLawError, "outside required namespace"
            ):
                qualify_versioned_one_shot_paths(
                    repo_root=root,
                    contract_paths=v1,
                    active_artifact_paths=active_v2,
                    required_namespace="state/catalytic_swarm_1_v2",
                )

    def test_active_tuple_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            declared = paths("state/catalytic_swarm_1_v3")
            active = [root / declared[key] for key in ONE_SHOT_KEYS]
            active[-1] = root / "state/catalytic_swarm_1_v3/wrong.json"
            with self.assertRaisesRegex(
                VersionedPathLawError, "runtime paths differ"
            ):
                qualify_versioned_one_shot_paths(
                    repo_root=root,
                    contract_paths=declared,
                    active_artifact_paths=tuple(active),
                    required_namespace="state/catalytic_swarm_1_v3",
                )

    def test_consumed_namespace_overlap_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            declared = paths("state/catalytic_swarm_1_v2")
            active = tuple(root / declared[key] for key in ONE_SHOT_KEYS)
            with self.assertRaisesRegex(
                VersionedPathLawError, "consumed namespace"
            ):
                qualify_versioned_one_shot_paths(
                    repo_root=root,
                    contract_paths=declared,
                    active_artifact_paths=active,
                    required_namespace="state/catalytic_swarm_1_v2",
                    forbidden_namespaces=("state/catalytic_swarm_1_v2",),
                )

    def test_path_escape_rejects(self) -> None:
        declared = paths("state/catalytic_swarm_1_v3")
        declared["result"] = "../escaped.json"
        with self.assertRaisesRegex(VersionedPathLawError, "escapes"):
            qualify_versioned_one_shot_paths(
                repo_root=Path("."),
                contract_paths=declared,
                active_artifact_paths=tuple(Path(declared[key]) for key in ONE_SHOT_KEYS),
                required_namespace="state/catalytic_swarm_1_v3",
            )

    def test_key_order_is_frozen(self) -> None:
        declared = paths("state/catalytic_swarm_1_v3")
        reordered = {"readiness": declared["readiness"], "control": declared["control"]}
        reordered.update({key: declared[key] for key in ONE_SHOT_KEYS if key not in reordered})
        with self.assertRaisesRegex(VersionedPathLawError, "key order"):
            qualify_versioned_one_shot_paths(
                repo_root=Path("."),
                contract_paths=reordered,
                active_artifact_paths=tuple(Path(declared[key]) for key in ONE_SHOT_KEYS),
                required_namespace="state/catalytic_swarm_1_v3",
            )


if __name__ == "__main__":
    unittest.main()
