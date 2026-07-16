#!/usr/bin/env python3
"""Authoritative fail-closed entrypoint for the rank-head v2 live core.

Before authority consumption, failures propagate without mutation. After a
receipt exists, any uncaught core failure is converted into bounded terminal
INCONCLUSIVE evidence while preserving the receipt and removing the run lock.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping

import catalytic_kernel_0 as kernel
import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2_authority as authority
import catalytic_kernel_0_balanced_rank_head_v2_evidence as evidence
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration
import catalytic_kernel_0_balanced_rank_head_v2_live as live_core
import catalytic_kernel_0_balanced_rank_head_v2_run_design as run_design


class RankHeadV2EntrypointError(ValueError):
    pass


DIRECT_EXECUTION_ERROR = (
    "direct execution is forbidden; use "
    "scripts/catalytic_kernel_0_balanced_rank_head_v2_cli.py"
)


def _arg(args: Any, name: str) -> Any:
    return args.get(name) if isinstance(args, Mapping) else getattr(args, name, None)


def _safe_failure(exc: BaseException, boundary: str) -> dict[str, str]:
    return {
        "boundary": boundary,
        "exception_type": type(exc).__name__[:80],
        "message_sha256": balanced.sha256_bytes(str(exc).encode("utf-8")),
    }


def _receipt_evidence(repository: Path, run_id: str) -> dict[str, Any] | None:
    path = authority.authority_receipt_path(repository, run_id)
    if not path.exists() and not path.is_symlink():
        return None
    try:
        return authority.verify_authority_receipt_for_run(
            repository,
            run_id,
            require_current_static=False,
        )
    except (authority.RankHeadV2AuthorityError, OSError, json.JSONDecodeError) as exc:
        raise RankHeadV2EntrypointError(
            "consumed v2 authority receipt failed cryptographic verification"
        ) from exc


def _terminal_evidence_exists(
    repository: Path,
    state_root: Path,
    run_id: str,
) -> bool:
    paths = live_core.state_paths(repository, run_id, state_root)
    required = (paths["manifest.json"], paths["result.json"], paths["closure.json"])
    if any(not path.is_file() or balanced._is_reparse(path) for path in required):
        return False
    try:
        result = json.loads(paths["result.json"].read_bytes())
        closure = json.loads(paths["closure.json"].read_bytes())
    except json.JSONDecodeError:
        return False
    return bool(
        isinstance(result, Mapping)
        and isinstance(closure, Mapping)
        and result.get("run_id") == run_id
        and closure.get("run_id") == run_id
        and result.get("status") in {"complete", "failed"}
        and closure.get("status") == result.get("status")
        and closure.get("run_lock_absent") is True
        and closure.get("manifest_sha256")
        == balanced.sha256_bytes(paths["manifest.json"].read_bytes())
        and closure.get("result_sha256")
        == balanced.sha256_bytes(paths["result.json"].read_bytes())
    )


def close_post_consumption_failure(
    repository: Path,
    state_root: Path,
    run_id: str,
    exc: BaseException,
) -> dict[str, Any] | None:
    authority.assert_test_repository_isolated(repository)
    if _terminal_evidence_exists(repository, state_root, run_id):
        raise RankHeadV2EntrypointError(
            "refusing to overwrite terminal v2 evidence"
        )
    receipt_path = authority.authority_receipt_path(repository, run_id)
    receipt_before = (
        receipt_path.read_bytes()
        if receipt_path.is_file() and not balanced._is_reparse(receipt_path)
        else None
    )
    receipt = _receipt_evidence(repository, run_id)
    if receipt is None:
        return None
    if receipt_before is None:
        raise RankHeadV2EntrypointError("verified v2 authority receipt disappeared")
    paths = live_core.state_paths(repository, run_id, state_root)
    run_root = paths["manifest.json"].parent
    run_root_existed = run_root.exists()
    run_root.mkdir(parents=True, exist_ok=True)
    manifest_is_valid = False
    if paths["manifest.json"].is_file() and not balanced._is_reparse(
        paths["manifest.json"]
    ):
        try:
            existing_manifest = json.loads(paths["manifest.json"].read_bytes())
            manifest_is_valid = (
                isinstance(existing_manifest, Mapping)
                and existing_manifest.get("run_id") == run_id
                and existing_manifest.get("external_live_authority") == receipt
            )
        except json.JSONDecodeError:
            manifest_is_valid = False
    elif paths["manifest.json"].exists() or paths["manifest.json"].is_symlink():
        raise RankHeadV2EntrypointError("v2 failure manifest path is unsafe")
    model_request_observation: int | str = (
        "unknown-post-mutation" if run_root_existed else 0
    )
    if not manifest_is_valid:
        kernel._atomic_json(
            paths["manifest.json"],
            {
                "schema_version": 1,
                "kernel_id": "catalytic-kernel-0-rank-head-v2",
                "run_id": run_id,
                "status": "post-consumption-failure-boundary",
                "external_live_authority": receipt,
                "model_request_count_observation": model_request_observation,
                "authority_receipt_cryptographically_verified": True,
                "claiming": False,
                "automatic_promotion": False,
            },
        )
    failure = _safe_failure(exc, "uncaught-post-consumption")
    result = {
        "schema_version": 1,
        "kernel_id": "catalytic-kernel-0-rank-head-v2",
        "run_id": run_id,
        "status": "failed",
        "terminal_classification": integration.INCONCLUSIVE_CLASSIFICATION,
        "failure": failure,
        "external_live_authority": receipt,
        "model_request_count_observation": model_request_observation,
        "authority_receipt_cryptographically_verified": True,
        "retry_allowed": False,
        "claiming": False,
        "automatic_promotion": False,
    }
    kernel._atomic_json(paths["result.json"], result)
    if paths["run.lock"].exists() or paths["run.lock"].is_symlink():
        if paths["run.lock"].is_file() and not balanced._is_reparse(
            paths["run.lock"]
        ):
            paths["run.lock"].unlink()
    closure = {
        "schema_version": 1,
        "run_id": run_id,
        "manifest_sha256": balanced.sha256_bytes(
            paths["manifest.json"].read_bytes()
        ),
        "result_sha256": balanced.sha256_bytes(paths["result.json"].read_bytes()),
        "run_lock_absent": not paths["run.lock"].exists(),
        "status": "failed",
        "terminal_classification": integration.INCONCLUSIVE_CLASSIFICATION,
        "failure": failure,
        "external_live_authority": receipt,
        "authority_receipt_cryptographically_verified": True,
        "retry_allowed": False,
    }
    kernel._atomic_json(paths["closure.json"], closure)
    receipt_after = receipt_path.read_bytes()
    if receipt_after != receipt_before:
        raise RankHeadV2EntrypointError(
            "v2 authority receipt changed during failure closure"
        )
    if authority.verify_authority_receipt_for_run(
        repository,
        run_id,
        require_current_static=False,
    ) != receipt:
        raise RankHeadV2EntrypointError(
            "v2 authority receipt failed final cryptographic verification"
        )
    return result


def run_rank_head_v2(
    args: Any,
    *,
    repository_root: str | os.PathLike[str],
    state_root: str | os.PathLike[str],
) -> dict[str, Any]:
    repository = Path(repository_root).resolve()
    runtime_state_root = Path(state_root).resolve()
    authority.assert_test_repository_isolated(repository)
    expected_state_root = (repository / run_design.STATE_ROOT).resolve()
    if runtime_state_root != expected_state_root:
        raise RankHeadV2EntrypointError(
            "v2 state root must be the repository-owned isolated runtime root"
        )
    run_id = str(_arg(args, "run_id") or "")
    integration.run_spec(run_id)
    try:
        result = live_core._run_rank_head_v2_protected(
            args,
            repository_root=repository,
            state_root=runtime_state_root,
        )
    except BaseException as exc:
        result = close_post_consumption_failure(
            repository,
            runtime_state_root,
            run_id,
            exc,
        )
        if result is None:
            raise
    external = result.get("external_live_authority", {})
    authority_body = external.get("authority", {}) if isinstance(external, Mapping) else {}
    protected_commit = (
        str(authority_body.get("authorized_commit", ""))
        if isinstance(authority_body, Mapping)
        else ""
    )
    archive = evidence.archive_terminal_evidence(
        repository,
        run_id,
        protected_commit=protected_commit,
    )
    return {**result, "evidence_archive": archive}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", choices=("run",))
    parser.add_argument("--binary", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--run-id", required=True, choices=integration.RUN_ORDER)
    parser.add_argument("--external-live-authority-id", required=True)
    parser.add_argument("--authorized-commit", required=True)
    return parser.parse_args()


def main(
    *,
    repository_root: str | os.PathLike[str],
    state_root: str | os.PathLike[str],
) -> int:
    args = parse_args()
    try:
        result = run_rank_head_v2(
            args,
            repository_root=repository_root,
            state_root=state_root,
        )
    except BaseException as exc:
        print(
            json.dumps(
                {
                    "status": "fail",
                    "exception_type": type(exc).__name__,
                    "message_sha256": balanced.sha256_bytes(
                        str(exc).encode("utf-8")
                    ),
                },
                sort_keys=True,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "status": result.get("status"),
                "run_id": result.get("run_id"),
                "terminal_classification": result.get(
                    "terminal_classification"
                ),
            },
            sort_keys=True,
        )
    )
    return 0 if result.get("status") == "complete" else 1


def reject_direct_execution() -> int:
    print(
        json.dumps(
            {
                "status": "fail",
                "error": DIRECT_EXECUTION_ERROR,
            },
            sort_keys=True,
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(reject_direct_execution())
