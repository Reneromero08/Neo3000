#!/usr/bin/env python3
"""Authoritative fail-closed entrypoint for the rank-head v2 live core.

Before authority consumption, failures propagate without mutation. After a
receipt exists, any uncaught core failure is converted into bounded terminal
INCONCLUSIVE evidence while preserving the receipt and removing the run lock.
A later invocation may never reinterpret or overwrite existing authority or
runtime evidence from an earlier invocation.
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
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration
import catalytic_kernel_0_balanced_rank_head_v2_live as live_core


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


def require_absent_prior_invocation_state(
    repository: Path,
    run_id: str,
    *,
    state_root: Path | None = None,
) -> None:
    """Reject later invocations before their failures can mutate prior evidence."""

    receipt_path = authority.authority_receipt_path(repository, run_id)
    paths = live_core.state_paths(repository, run_id, state_root)
    candidates = (receipt_path, *paths.values())
    if any(path.exists() or path.is_symlink() for path in candidates):
        raise RankHeadV2EntrypointError(
            "v2 run already has authority or runtime evidence; existing evidence is immutable"
        )


def close_post_consumption_failure(
    repository: Path,
    run_id: str,
    exc: BaseException,
) -> dict[str, Any] | None:
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
    paths = live_core.state_paths(repository, run_id)
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
    repository_root: str | os.PathLike[str] | None = None,
    state_root: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    repository = (
        Path(repository_root).resolve()
        if repository_root is not None
        else Path(__file__).resolve().parents[1]
    )
    resolved_state_root = (
        Path(state_root).resolve() if state_root is not None else None
    )
    run_id = str(_arg(args, "run_id") or "")
    integration.run_spec(run_id)
    require_absent_prior_invocation_state(
        repository,
        run_id,
        state_root=resolved_state_root,
    )
    try:
        return live_core._run_rank_head_v2_protected(
            args,
            repository_root=repository,
            state_root=resolved_state_root,
        )
    except BaseException as exc:
        closed = close_post_consumption_failure(repository, run_id, exc)
        if closed is not None:
            return closed
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", choices=("run",))
    parser.add_argument("--binary", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--run-id", required=True, choices=integration.RUN_ORDER)
    parser.add_argument("--external-live-authority-id", required=True)
    parser.add_argument("--authorized-commit", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run_rank_head_v2(args)
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
