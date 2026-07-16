#!/usr/bin/env python3
"""Byte-exact archive, verification, and restoration for rank-head v2 evidence."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any, Mapping

import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2_authority as authority
import catalytic_kernel_0_balanced_rank_head_v2_integration as integration
import catalytic_kernel_0_balanced_rank_head_v2_run_design as run_design

ARCHIVE_SCHEMA_VERSION = 1
ARCHIVE_VERSION = "v1"
ARCHIVE_ROOT = Path("state/catalytic_kernel_0_rank_head_v2_evidence_archive") / ARCHIVE_VERSION
ARCHIVE_MANIFEST = "archive.json"
ARCHIVE_NAMES = {
    "receipt": "authority-receipt.json",
    "manifest": "manifest.json",
    "result": "result.json",
    "closure": "closure.json",
}
PURPOSES = frozenset({"terminal-closure", "forensic-test-overwrite"})
MAX_EVIDENCE_BYTES = 8_000_000


class RankHeadV2EvidenceError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return balanced.sha256_bytes(data)


def _source_paths(repository: Path, run_id: str) -> dict[str, Path]:
    integration.known_run_spec(run_id)
    runtime_root = repository / run_design.STATE_ROOT / run_id
    return {
        "receipt": authority.authority_receipt_path(repository, run_id),
        "manifest": runtime_root / "manifest.json",
        "result": runtime_root / "result.json",
        "closure": runtime_root / "closure.json",
    }


def _relative(repository: Path, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(
            repository.resolve(strict=False)
        ).as_posix()
    except ValueError as exc:
        raise RankHeadV2EvidenceError("evidence path escapes repository") from exc


def _require_regular(path: Path, label: str) -> bytes:
    if (
        not path.is_file()
        or balanced._is_reparse(path)
        or path.stat().st_size > MAX_EVIDENCE_BYTES
    ):
        raise RankHeadV2EvidenceError(f"{label} is missing or unsafe")
    return path.read_bytes()


def _json_object(data: bytes, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(data)
    except json.JSONDecodeError as exc:
        raise RankHeadV2EvidenceError(f"{label} is invalid JSON") from exc
    if not isinstance(value, Mapping):
        raise RankHeadV2EvidenceError(f"{label} root is malformed")
    return value


def _validate_terminal_chain(
    repository: Path,
    run_id: str,
    protected_commit: str,
    payloads: Mapping[str, bytes],
) -> None:
    if not balanced.GIT_COMMIT_RE.fullmatch(protected_commit):
        raise RankHeadV2EvidenceError("protected commit is malformed")
    receipt = _json_object(payloads["receipt"], "authority receipt")
    manifest = _json_object(payloads["manifest"], "manifest")
    result = _json_object(payloads["result"], "result")
    closure = _json_object(payloads["closure"], "closure")
    receipt_authority = receipt.get("authority")
    if not isinstance(receipt_authority, Mapping):
        raise RankHeadV2EvidenceError("authority receipt body is malformed")
    try:
        verified_receipt = authority.verify_authority_receipt_bytes_for_run(
            repository,
            run_id,
            payloads["receipt"],
            require_current_static=False,
        )
    except (authority.RankHeadV2AuthorityError, OSError) as exc:
        raise RankHeadV2EvidenceError(
            "archived authority receipt failed cryptographic verification"
        ) from exc
    if not all(
        (
            receipt.get("consumed") is True,
            verified_receipt.get("authority") == receipt_authority,
            receipt_authority.get("run_id") == run_id,
            receipt_authority.get("authorized_commit") == protected_commit,
            manifest.get("run_id") == run_id,
            result.get("run_id") == run_id,
            closure.get("run_id") == run_id,
            closure.get("run_lock_absent") is True,
            closure.get("manifest_sha256") == sha256_bytes(payloads["manifest"]),
            closure.get("result_sha256") == sha256_bytes(payloads["result"]),
            result.get("status") in {"complete", "failed"},
            closure.get("status") in {"complete", "failed"},
            result.get("status") == closure.get("status"),
        )
    ):
        raise RankHeadV2EvidenceError("terminal evidence chain is not exact")


def _require_archive_ignored(repository: Path, target: Path) -> None:
    relative = _relative(repository, target)
    completed = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", relative],
        cwd=repository,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise RankHeadV2EvidenceError("evidence archive path is not ignored")


def _exclusive_write(path: Path, data: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
        stat.S_IRUSR | stat.S_IWUSR,
    )
    try:
        written = os.write(descriptor, data)
        if written != len(data):
            raise RankHeadV2EvidenceError("evidence archive write was incomplete")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def archive_terminal_evidence(
    repository: Path,
    run_id: str,
    *,
    protected_commit: str,
    purpose: str = "terminal-closure",
) -> dict[str, Any]:
    """Create one exclusive content-addressed snapshot of terminal evidence."""
    repository = repository.resolve(strict=False)
    authority.assert_test_repository_isolated(repository)
    if purpose not in PURPOSES:
        raise RankHeadV2EvidenceError("unknown evidence archive purpose")
    source_paths = _source_paths(repository, run_id)
    run_lock = repository / run_design.STATE_ROOT / run_id / "run.lock"
    if run_lock.exists() or run_lock.is_symlink():
        raise RankHeadV2EvidenceError("terminal evidence still has a run lock")
    payloads = {
        name: _require_regular(path, name)
        for name, path in source_paths.items()
    }
    _validate_terminal_chain(repository, run_id, protected_commit, payloads)
    files = [
        {
            "name": name,
            "archive_filename": ARCHIVE_NAMES[name],
            "source_path": _relative(repository, source_paths[name]),
            "byte_size": len(payloads[name]),
            "sha256": sha256_bytes(payloads[name]),
        }
        for name in sorted(payloads)
    ]
    bundle = {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "archive_version": ARCHIVE_VERSION,
        "purpose": purpose,
        "run_id": run_id,
        "protected_commit": protected_commit,
        "files": files,
    }
    bundle_sha256 = balanced.json_sha256(bundle)
    target = repository / ARCHIVE_ROOT / run_id / bundle_sha256
    _require_archive_ignored(repository, target)
    balanced._assert_safe_ancestry(repository, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        raise RankHeadV2EvidenceError("evidence archive already exists")
    staging_parent = target.parent / f".{bundle_sha256}.staging.{os.getpid()}"
    balanced._assert_safe_ancestry(repository, staging_parent)
    try:
        staging_parent.mkdir()
    except FileExistsError as exc:
        raise RankHeadV2EvidenceError("evidence archive staging exists") from exc
    staging_target = staging_parent / bundle_sha256
    try:
        staging_target.mkdir()
        for item in files:
            _exclusive_write(
                staging_target / str(item["archive_filename"]),
                payloads[str(item["name"])],
            )
        document = {"bundle": bundle, "bundle_sha256": bundle_sha256}
        _exclusive_write(
            staging_target / ARCHIVE_MANIFEST,
            balanced.canonical_json_bytes(document),
        )
        verify_archive(repository, staging_target)
        if target.exists() or target.is_symlink():
            raise RankHeadV2EvidenceError("evidence archive already exists")
        os.rename(staging_target, target)
    finally:
        if staging_parent.exists() and not balanced._is_reparse(staging_parent):
            shutil.rmtree(staging_parent)
    verified = verify_archive(repository, target)
    return {
        "archive_path": _relative(repository, target),
        "bundle_sha256": verified["bundle_sha256"],
        "files": verified["bundle"]["files"],
        "status": "verified",
    }


def verify_archive(repository: Path, archive_path: Path) -> dict[str, Any]:
    """Verify a complete content-addressed archive without changing state."""
    repository = repository.resolve(strict=False)
    target = (
        archive_path.resolve(strict=False)
        if archive_path.is_absolute()
        else (repository / archive_path).resolve(strict=False)
    )
    archive_root = (repository / ARCHIVE_ROOT).resolve(strict=False)
    try:
        target.relative_to(archive_root)
    except ValueError as exc:
        raise RankHeadV2EvidenceError("archive path escapes archive root") from exc
    if not target.is_dir() or balanced._is_reparse(target):
        raise RankHeadV2EvidenceError("archive directory is missing or unsafe")
    manifest_path = target / ARCHIVE_MANIFEST
    document = _json_object(
        _require_regular(manifest_path, "archive manifest"),
        "archive manifest",
    )
    if set(document) != {"bundle", "bundle_sha256"}:
        raise RankHeadV2EvidenceError("archive manifest fields changed")
    bundle = document.get("bundle")
    bundle_sha256 = document.get("bundle_sha256")
    if not isinstance(bundle, Mapping) or not isinstance(bundle_sha256, str):
        raise RankHeadV2EvidenceError("archive bundle is malformed")
    if balanced.json_sha256(bundle) != bundle_sha256 or target.name != bundle_sha256:
        raise RankHeadV2EvidenceError("archive content address changed")
    run_id = str(bundle.get("run_id", ""))
    integration.known_run_spec(run_id)
    protected_commit = str(bundle.get("protected_commit", ""))
    files = bundle.get("files")
    if (
        bundle.get("schema_version") != ARCHIVE_SCHEMA_VERSION
        or bundle.get("archive_version") != ARCHIVE_VERSION
        or bundle.get("purpose") not in PURPOSES
        or not isinstance(files, list)
        or len(files) != len(ARCHIVE_NAMES)
    ):
        raise RankHeadV2EvidenceError("archive bundle contract changed")
    source_paths = _source_paths(repository, run_id)
    payloads: dict[str, bytes] = {}
    archive_names: set[str] = set()
    for item in files:
        if not isinstance(item, Mapping):
            raise RankHeadV2EvidenceError("archive file entry is malformed")
        name = str(item.get("name", ""))
        archive_name = str(item.get("archive_filename", ""))
        if (
            name not in ARCHIVE_NAMES
            or archive_name != ARCHIVE_NAMES[name]
            or item.get("source_path") != _relative(repository, source_paths[name])
            or archive_name in archive_names
        ):
            raise RankHeadV2EvidenceError("archive file identity changed")
        archive_names.add(archive_name)
        data = _require_regular(target / archive_name, f"archived {name}")
        if (
            item.get("byte_size") != len(data)
            or item.get("sha256") != sha256_bytes(data)
        ):
            raise RankHeadV2EvidenceError("archived file hash or size changed")
        payloads[name] = data
    expected_children = set(ARCHIVE_NAMES.values()) | {ARCHIVE_MANIFEST}
    if {path.name for path in target.iterdir()} != expected_children:
        raise RankHeadV2EvidenceError("archive contains unexpected paths")
    _validate_terminal_chain(repository, run_id, protected_commit, payloads)
    return {"bundle": dict(bundle), "bundle_sha256": bundle_sha256}


def restore_archive(
    repository: Path,
    archive_path: Path,
) -> dict[str, Any]:
    """Restore missing files only; identical existing files are left untouched."""
    repository = repository.resolve(strict=False)
    authority.assert_test_repository_isolated(repository)
    verified = verify_archive(repository, archive_path)
    bundle = verified["bundle"]
    run_id = str(bundle["run_id"])
    source_paths = _source_paths(repository, run_id)
    target = (
        archive_path.resolve(strict=False)
        if archive_path.is_absolute()
        else (repository / archive_path).resolve(strict=False)
    )
    to_restore: list[tuple[Mapping[str, Any], Path, bytes]] = []
    unchanged: list[str] = []
    for item in bundle["files"]:
        name = str(item["name"])
        destination = source_paths[name]
        balanced._assert_safe_ancestry(repository, destination)
        data = (target / str(item["archive_filename"])).read_bytes()
        if destination.is_symlink() or (
            destination.exists() and not destination.is_file()
        ):
            raise RankHeadV2EvidenceError("restore destination is unsafe")
        if destination.exists():
            if destination.read_bytes() != data:
                raise RankHeadV2EvidenceError(
                    "restore refuses to replace differing evidence"
                )
            unchanged.append(str(item["source_path"]))
        else:
            to_restore.append((item, destination, data))
    staged: list[tuple[Path, Path]] = []
    created: list[tuple[Path, str]] = []
    try:
        for item, destination, data in to_restore:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(
                f".{destination.name}.restore.{verified['bundle_sha256']}.{os.getpid()}"
            )
            _exclusive_write(temporary, data)
            if sha256_bytes(temporary.read_bytes()) != item["sha256"]:
                raise RankHeadV2EvidenceError("staged restore bytes changed")
            staged.append((temporary, destination))
        for temporary, destination in staged:
            try:
                os.link(temporary, destination)
            except FileExistsError as exc:
                raise RankHeadV2EvidenceError(
                    "restore refuses to replace evidence created concurrently"
                ) from exc
            created.append((destination, sha256_bytes(temporary.read_bytes())))
            temporary.unlink()
        staged.clear()
        created.clear()
    except BaseException:
        for destination, expected_sha256 in reversed(created):
            if (
                destination.is_file()
                and not balanced._is_reparse(destination)
                and sha256_bytes(destination.read_bytes()) == expected_sha256
            ):
                destination.unlink()
        raise
    finally:
        for temporary, _ in staged:
            if temporary.is_file() and not balanced._is_reparse(temporary):
                temporary.unlink()
    return {
        "bundle_sha256": verified["bundle_sha256"],
        "restored": [str(item[0]["source_path"]) for item in to_restore],
        "unchanged": unchanged,
        "status": "restored-byte-exact",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)
    archive = subparsers.add_parser("archive")
    archive.add_argument("--repository", required=True)
    archive.add_argument("--run-id", required=True)
    archive.add_argument("--protected-commit", required=True)
    archive.add_argument("--purpose", choices=sorted(PURPOSES), default="terminal-closure")
    for action in ("verify", "restore"):
        command = subparsers.add_parser(action)
        command.add_argument("--repository", required=True)
        command.add_argument("--archive", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository = Path(args.repository)
    try:
        if args.action == "archive":
            result = archive_terminal_evidence(
                repository,
                args.run_id,
                protected_commit=args.protected_commit,
                purpose=args.purpose,
            )
        elif args.action == "verify":
            result = verify_archive(repository, Path(args.archive))
        else:
            result = restore_archive(
                repository,
                Path(args.archive),
            )
    except (OSError, RankHeadV2EvidenceError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps({"status": "pass", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
