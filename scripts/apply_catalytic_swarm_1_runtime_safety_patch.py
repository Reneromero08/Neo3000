#!/usr/bin/env python3
"""Apply the exact CatalyticSwarm-1 runtime safety repair to holostate_live.py.

This temporary integration helper is bound to the protected source blob at
Neo3000 main 1a651b8a80d9135ef676171a0f7ddd8ad64f5e7a. It performs deterministic
text transformations, parses the result, and writes atomically only when every
expected anchor occurs exactly once.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import subprocess
from pathlib import Path

EXPECTED_GIT_BLOB = "22194faab124aa2973fda432347a977e146da637"
TARGET = Path(__file__).resolve().parents[1] / "scripts" / "holostate_live.py"


class PatchError(RuntimeError):
    pass


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise PatchError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


def indent_block(block: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line if line else line for line in block.split("\n"))


def transform(text: str) -> str:
    text = replace_once(
        text,
        """    validate_catalytic_swarm_1_contract,\n)\nfrom holostate_swarm_adapter import (\n""",
        """    validate_catalytic_swarm_1_contract,\n)\nfrom catalytic_swarm_1_runtime_safety import (  # noqa: E402\n    ArmedCleanup,\n    require_custody_snapshot,\n    require_host_memory_growth,\n    require_task_budget_parity,\n)\nfrom holostate_swarm_adapter import (\n""",
        "runtime-safety-import",
    )

    text = replace_once(
        text,
        """    contract_hash = lock[\"catalytic_swarm_1_sha256\"]\n\n    control_record: dict[str, Any] = {\n""",
        """    contract_hash = lock[\"catalytic_swarm_1_sha256\"]\n    runtime_custody_expected = {\n        \"stable\": git_read(\n            ROOT, \"status\", \"--porcelain=v2\", \"--branch\", \"--untracked-files=all\"\n        ),\n        \"candidate\": git_read(\n            preclaim[\"candidate_root\"],\n            \"status\",\n            \"--porcelain=v2\",\n            \"--branch\",\n            \"--untracked-files=all\",\n        ),\n    }\n    runtime_boundary_stats: dict[str, Any] = {\n        \"custody_checks\": 0,\n        \"host_memory_checks\": 0,\n        \"task_parity_checks\": 0,\n        \"maximum_host_private_growth_bytes\": 0,\n        \"last_boundary\": None,\n    }\n\n    def require_live_boundary(boundary: str, *, require_host: bool) -> dict[str, Any]:\n        observed = {\n            \"stable\": git_read(\n                ROOT, \"status\", \"--porcelain=v2\", \"--branch\", \"--untracked-files=all\"\n            ),\n            \"candidate\": git_read(\n                preclaim[\"candidate_root\"],\n                \"status\",\n                \"--porcelain=v2\",\n                \"--branch\",\n                \"--untracked-files=all\",\n            ),\n        }\n        custody = require_custody_snapshot(\n            runtime_custody_expected, observed, boundary=boundary\n        )\n        runtime_boundary_stats[\"custody_checks\"] += 1\n        runtime_boundary_stats[\"last_boundary\"] = boundary\n        evidence: dict[str, Any] = {\n            \"boundary\": boundary,\n            \"custody_passed\": custody[\"passed\"],\n            \"stable_snapshot_sha256\": sha256_bytes(observed[\"stable\"].encode(\"utf-8\")),\n            \"candidate_snapshot_sha256\": sha256_bytes(\n                observed[\"candidate\"].encode(\"utf-8\")\n            ),\n        }\n        if require_host:\n            if sidecar is None or sidecar.process is None or readiness is None:\n                raise NeoLoopError(\n                    f\"{boundary}: CatalyticSwarm-1 host boundary lacks a live sidecar\"\n                )\n            resource = worker_resource_gate(sidecar, readiness, predecessor_contract)\n            if resource.get(\"passed\") is not True:\n                raise NeoLoopError(\n                    f\"{boundary}: CatalyticSwarm-1 per-request resource gate failed\"\n                )\n            info = process_info(sidecar.process.pid)\n            if not isinstance(info, dict):\n                raise NeoLoopError(\n                    f\"{boundary}: CatalyticSwarm-1 process memory is unavailable\"\n                )\n            host = require_host_memory_growth(\n                baseline_private_bytes=int(readiness[\"process_memory\"][\"private_bytes\"]),\n                current_private_bytes=int(info[\"private_bytes\"]),\n                ceiling_bytes=int(predecessor_contract[\"host_cache_mib_ceiling\"]) * MIB,\n                boundary=boundary,\n            )\n            runtime_boundary_stats[\"host_memory_checks\"] += 1\n            runtime_boundary_stats[\"maximum_host_private_growth_bytes\"] = max(\n                int(runtime_boundary_stats[\"maximum_host_private_growth_bytes\"]),\n                int(host[\"growth_bytes\"]),\n            )\n            evidence[\"host_memory\"] = host\n            evidence[\"resource_gate_passed\"] = True\n        return evidence\n\n    control_record: dict[str, Any] = {\n""",
        "runtime-boundary-helpers",
    )

    first_warm_old = """        with lease_pool.lease() as lease_id:\n            (\n                first_warm_summary,\n                first_warm_metadata,\n                first_system_message,\n                first_system_identity,\n            ) = catalytic_swarm_1_warm_request(\n                sidecar,\n                protocol_v4,\n                predecessor_contract,\n                readiness,\n                suite.tasks[0],\n                request_sequence_index=1,\n                lease_id=lease_id,\n            )\n        mark_catalytic_swarm_1_first_warm_executed(parser_record)\n"""
    first_warm_new = """        require_live_boundary(\n            f\"pre-request:{suite.tasks[0].task_id}:common-root-warm\",\n            require_host=False,\n        )\n        with lease_pool.lease() as lease_id:\n            (\n                first_warm_summary,\n                first_warm_metadata,\n                first_system_message,\n                first_system_identity,\n            ) = catalytic_swarm_1_warm_request(\n                sidecar,\n                protocol_v4,\n                predecessor_contract,\n                readiness,\n                suite.tasks[0],\n                request_sequence_index=1,\n                lease_id=lease_id,\n            )\n        require_live_boundary(\n            f\"post-request:{suite.tasks[0].task_id}:common-root-warm\",\n            require_host=True,\n        )\n        mark_catalytic_swarm_1_first_warm_executed(parser_record)\n"""
    text = replace_once(text, first_warm_old, first_warm_new, "first-root-warm-boundary")

    gap_start = text.index(
        "    if any(\n        item is None\n        for item in (\n            first_warm_summary,"
    )
    gap_end_marker = "    execution_error: Exception | None = None\n"
    gap_end = text.index(gap_end_marker, gap_start) + len(gap_end_marker)
    gap_block = text[gap_start:gap_end]
    guarded_gap = """    def cleanup_post_parser_pre_attempt() -> dict[str, Any]:\n        cleanup = safe_sidecar_cleanup(sidecar)\n        parser_record[\"post_parser_pre_attempt_cleanup\"] = cleanup\n        parser_record[\"post_parser_pre_attempt_cleanup_gate\"] = cleanup_integrity(\n            cleanup, stable_pids\n        )\n        parser_record[\"post_parser_pre_attempt_cleanup_at\"] = utc_now()\n        write_catalytic_swarm_1_runtime_json(\n            CATALYTIC_SWARM_1_PARSER_CANARY_PATH, parser_record\n        )\n        return cleanup\n\n    with ArmedCleanup(cleanup_post_parser_pre_attempt) as post_parser_cleanup:\n""" + indent_block(gap_block) + """\n        result[\"runtime_boundary_evidence\"] = runtime_boundary_stats\n        post_parser_cleanup.disarm()\n"""
    text = text[:gap_start] + guarded_gap + text[gap_end:]

    later_warm_old = """                request_sequence_index += 1\n                with lease_pool.lease() as lease_id:\n                    warm_summary, warm_metadata, system_message, system_identity = (\n                        catalytic_swarm_1_warm_request(\n                            sidecar,\n                            protocol_v4,\n                            predecessor_contract,\n                            readiness,\n                            task,\n                            request_sequence_index=request_sequence_index,\n                            lease_id=lease_id,\n                        )\n                    )\n                warm_summaries.append(warm_summary)\n"""
    later_warm_new = """                request_sequence_index += 1\n                require_live_boundary(\n                    f\"pre-request:{task.task_id}:common-root-warm\",\n                    require_host=False,\n                )\n                with lease_pool.lease() as lease_id:\n                    warm_summary, warm_metadata, system_message, system_identity = (\n                        catalytic_swarm_1_warm_request(\n                            sidecar,\n                            protocol_v4,\n                            predecessor_contract,\n                            readiness,\n                            task,\n                            request_sequence_index=request_sequence_index,\n                            lease_id=lease_id,\n                        )\n                    )\n                require_live_boundary(\n                    f\"post-request:{task.task_id}:common-root-warm\",\n                    require_host=True,\n                )\n                warm_summaries.append(warm_summary)\n"""
    text = replace_once(text, later_warm_old, later_warm_new, "later-root-warm-boundary")

    request_pre_old = """                    request_sequence_index += 1\n                    with lease_pool.lease() as lease_id:\n"""
    request_pre_new = """                    request_sequence_index += 1\n                    require_live_boundary(\n                        f\"pre-request:{_task.task_id}:{turn.arm}:{turn.turn_id}\",\n                        require_host=False,\n                    )\n                    with lease_pool.lease() as lease_id:\n"""
    text = replace_once(text, request_pre_old, request_pre_new, "comparison-pre-boundary")

    request_post_old = """                            raise\n                    metadata[\"wddm_freshness_boundary\"] = sidecar.wddm_freshness_boundaries[\n                        -1\n                    ][\"boundary\"]\n"""
    request_post_new = """                            raise\n                    require_live_boundary(\n                        f\"post-request:{_task.task_id}:{turn.arm}:{turn.turn_id}\",\n                        require_host=True,\n                    )\n                    metadata[\"wddm_freshness_boundary\"] = sidecar.wddm_freshness_boundaries[\n                        -1\n                    ][\"boundary\"]\n"""
    text = replace_once(text, request_post_old, request_post_new, "comparison-post-boundary")

    parity_old = """            write_catalytic_swarm_1_runtime_json(\n                CATALYTIC_SWARM_1_RESULT_PATH, result\n            )\n\n        suite_result = classify_suite_advantage(comparisons)\n"""
    parity_new = """            write_catalytic_swarm_1_runtime_json(\n                CATALYTIC_SWARM_1_RESULT_PATH, result\n            )\n            parity_evidence = require_task_budget_parity(\n                comparison, ratio_limit=1.10\n            )\n            runtime_boundary_stats[\"task_parity_checks\"] += 1\n            result[\"last_task_parity\"] = {\n                \"task_id\": task.task_id,\n                **parity_evidence,\n            }\n\n        suite_result = classify_suite_advantage(comparisons)\n"""
    text = replace_once(text, parity_old, parity_new, "task-parity-boundary")

    safety_old = """        safety = (\n            cleanup_gate[\"passed\"] is True\n            and isolation_gate[\"passed\"] is True\n            and result[\"frozen_stage_gate\"][\"passed\"] is True\n            and terminal_wddm[\"passed\"] is True\n            and freshness_gate[\"passed\"] is True\n            and ledger_gate\n            and request_gate\n            and execution_error is None\n            and interruption is None\n        )\n        result[\"protocol_safety_gate\"] = {\n"""
    safety_new = """        live_boundary_gate = {\n            \"passed\": (\n                runtime_boundary_stats[\"custody_checks\"] == 2064\n                and runtime_boundary_stats[\"host_memory_checks\"] == 1032\n                and runtime_boundary_stats[\"task_parity_checks\"] == 8\n            ),\n            \"expected_custody_checks\": 2064,\n            \"expected_host_memory_checks\": 1032,\n            \"expected_task_parity_checks\": 8,\n            **runtime_boundary_stats,\n        }\n        result[\"live_boundary_gate\"] = live_boundary_gate\n        safety = (\n            cleanup_gate[\"passed\"] is True\n            and isolation_gate[\"passed\"] is True\n            and result[\"frozen_stage_gate\"][\"passed\"] is True\n            and terminal_wddm[\"passed\"] is True\n            and freshness_gate[\"passed\"] is True\n            and ledger_gate\n            and request_gate\n            and live_boundary_gate[\"passed\"] is True\n            and execution_error is None\n            and interruption is None\n        )\n        result[\"protocol_safety_gate\"] = {\n"""
    text = replace_once(text, safety_old, safety_new, "terminal-live-boundary-gate")

    text = replace_once(
        text,
        """            \"metadata_ledger\": ledger_gate,\n            \"request_law\": request_gate,\n        }\n""",
        """            \"metadata_ledger\": ledger_gate,\n            \"request_law\": request_gate,\n            \"live_boundaries\": live_boundary_gate,\n        }\n""",
        "protocol-safety-evidence",
    )

    ast.parse(text)
    required_markers = (
        "require_live_boundary(",
        "require_task_budget_parity(",
        "with ArmedCleanup(cleanup_post_parser_pre_attempt)",
        '"expected_host_memory_checks": 1032',
        '"expected_custody_checks": 2064',
    )
    for marker in required_markers:
        if marker not in text:
            raise PatchError(f"patched source omitted marker: {marker}")
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = TARGET.parents[1]
    blob = subprocess.run(
        ["git", "hash-object", str(TARGET)],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    if blob != EXPECTED_GIT_BLOB:
        raise PatchError(f"unexpected holostate_live.py blob: {blob}")
    source = TARGET.read_text(encoding="utf-8")
    patched = transform(source)
    print(hashlib.sha256(patched.encode("utf-8")).hexdigest())
    if args.check:
        return 0
    temporary = TARGET.with_suffix(TARGET.suffix + ".cs1-safety.tmp")
    temporary.write_text(patched, encoding="utf-8", newline="\n")
    temporary.replace(TARGET)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
