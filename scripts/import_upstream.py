#!/usr/bin/env python3
"""Materialize the pinned llama.cpp source import for Neo3000."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "upstream" / "IMPORT_MANIFEST.json"
PIN_PATH = ROOT / "upstream" / "LLAMA_CPP_COMMIT"
IMPORTED_PATH = ROOT / "upstream" / "IMPORTED.json"
LOCAL_SCRIPT_NAMES = {"import_upstream.py", "build_cuda.ps1", "run_server.ps1"}


class ImportError(RuntimeError):
    pass


def run(command: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def load_manifest() -> dict[str, Any]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    commit = PIN_PATH.read_text(encoding="utf-8").strip()
    if data.get("commit") != commit:
        raise ImportError("IMPORT_MANIFEST.json and LLAMA_CPP_COMMIT disagree")
    paths = data.get("paths")
    if not isinstance(paths, list) or not paths:
        raise ImportError("import manifest must contain a non-empty paths list")
    return data


def remove_destination(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def copy_directory(source: Path, destination: Path, force: bool) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        target = destination / child.name
        if destination == ROOT / "scripts" and child.name in LOCAL_SCRIPT_NAMES:
            raise ImportError(f"upstream unexpectedly collides with Neo3000 script: {child.name}")
        if target.exists():
            if not force:
                raise ImportError(f"destination already exists: {target}; rerun with --force")
            remove_destination(target)
        if child.is_dir():
            shutil.copytree(child, target)
        else:
            shutil.copy2(child, target)


def copy_path(source_root: Path, relative: str, force: bool, dry_run: bool) -> None:
    source = source_root / relative
    destination = ROOT / relative
    if not source.exists():
        raise ImportError(f"pinned upstream path does not exist: {relative}")

    print(f"import {relative}")
    if dry_run:
        return

    if source.is_dir():
        if relative == "scripts":
            copy_directory(source, destination, force=force)
            return
        if destination.exists():
            if not force:
                raise ImportError(f"destination already exists: {destination}; rerun with --force")
            remove_destination(destination)
        shutil.copytree(source, destination)
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        raise ImportError(f"destination already exists: {destination}; rerun with --force")
    shutil.copy2(source, destination)


def clone_pinned_source(repository: str, commit: str, destination: Path) -> None:
    run(["git", "clone", "--filter=blob:none", "--no-checkout", repository, str(destination)])
    run(["git", "checkout", "--detach", commit], cwd=destination)
    resolved = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=destination,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    if resolved != commit:
        raise ImportError(f"resolved upstream commit {resolved} does not match pin {commit}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="existing llama.cpp checkout at the pinned commit")
    parser.add_argument("--force", action="store_true", help="replace previously imported upstream paths")
    parser.add_argument("--dry-run", action="store_true", help="validate and print without copying")
    args = parser.parse_args()

    manifest = load_manifest()
    repository = str(manifest["source_repository"])
    commit = str(manifest["commit"])

    temporary: tempfile.TemporaryDirectory[str] | None = None
    if args.source:
        source_root = args.source.resolve()
        resolved = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=source_root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        if resolved != commit:
            raise ImportError(f"source checkout is {resolved}, expected {commit}")
    else:
        temporary = tempfile.TemporaryDirectory(prefix="neo3000_upstream_")
        source_root = Path(temporary.name) / "llama.cpp"
        clone_pinned_source(repository, commit, source_root)

    try:
        for relative in manifest["paths"]:
            copy_path(source_root, str(relative), force=args.force, dry_run=args.dry_run)

        if not args.dry_run:
            receipt = {
                "commit": commit,
                "paths": manifest["paths"],
                "source_repository": repository,
            }
            IMPORTED_PATH.write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(f"wrote {IMPORTED_PATH.relative_to(ROOT)}")
    finally:
        if temporary is not None:
            temporary.cleanup()

    print("Neo3000 upstream import complete" if not args.dry_run else "Neo3000 import dry run complete")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ImportError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"import_upstream: {exc}")
        raise SystemExit(1)
