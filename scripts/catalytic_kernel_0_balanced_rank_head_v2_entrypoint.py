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
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration
import catalytic_kernel_0_balanced_rank_head_v2_live as live_core


class RankHeadV2EntrypointError(ValueError):
    pass


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
    balanced._assert_safe_ancestry(repository, path)
    if (
        not path.is_file()
        or balanced._is_reparse(path)
        or path.stat().st_size > 32768
    ):
        raise RankHeadV2EntrypointError(
            "consumed v2 authority receipt is unsafe"
        )
    try:
        document = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        raise RankHeadV2EntrypointError(
            "consumed v2 authority receipt is invalid"
        ) from exc
    return {
        "path": path.relative_to(repository).as_posix(),
        "sha256": balanced.sha256_bytes(path.read_bytes()),
        "authority": document.get("authority"),
        "authority_receipt_hmac": document.get("authority_receipt_hmac"),
        "consumed": document.get("consumed") is True,
        "retry_allowed": document.get("retry_allowed"),
    }


def close_post_consumption_failure(
    repository: Path,
    run_id: str,
    exc: BaseException,
) -> dict[str, Any] | None:
    receipt = _receipt_evidence(repository, run_id)
    if receipt is None:
        return None
    paths = live_core.state_paths(repository, run_id)
    run_root = paths["manifest.json"].parent
    run_root.mkdir(parents=True, exist_ok=True)
    if not paths["manifest.json"].exists():
        kernel._atomic_json(
            paths["manifest.json"],
            {
                "schema_version": 1,
                "kernel_id": "catalytic-kernel-0-rank-head-v2",
                "run_id": run_id,
                "status": "post-consumption-failure-boundary",
                "external_live_authority": receipt,
                "live_model_requests_observed": 0,
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
        "retry_allowed": False,
        "claiming": False,
        "automatic_promotion": False,
    }
    kernel._atomic_json(paths["result.json"], result)
    if paths["run.lock"].exists() and not paths["run.lock"].is_symlink():
        paths["run.lock"].unlink()
    closure = {
        "schema_version": 1,
        "run_id": run_id,
        "manifest_sha256": balanced.sha256_bytes(
            paths["manifest.json"].read_bytes()
        ),
        "result_sha256": balanced.sha256_bytes(paths["result.json"].read_bytes()),
        "run_lock_absent": not paths["run.lock"].exists(),
        "terminal_classification": integration.INCONCLUSIVE_CLASSIFICATION,
        "failure": failure,
        "external_live_authority": receipt,
        "retry_allowed": False,
    }
    kernel._atomic_json(paths["closure.json"], closure)
    return result


def run_rank_head_v2(
    args: Any,
    *,
    adapter: kernel.KernelAdapter | None = None,
    repository_root: str | os.PathLike[str] | None = None,
    state_root: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    repository = (
        Path(repository_root).resolve()
        if repository_root is not None
        else Path(__file__).resolve().parents[1]
    )
    run_id = str(_arg(args, "run_id") or "")
    integration.run_spec(run_id)
    try:
        return live_core.run_rank_head_v2(
            args,
            adapter=adapter,
            repository_root=repository,
            state_root=state_root,
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


if __name__ == "__main__":
    raise SystemExit(main())
