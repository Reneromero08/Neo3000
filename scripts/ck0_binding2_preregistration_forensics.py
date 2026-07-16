#!/usr/bin/env python3
"""Read-only forensic audit for CK0 binding-2 preregistration byte custody."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

SHA256_HEX = set("0123456789ABCDEF")


class ForensicError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_json_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def run_git(repository: Path, *args: str, check: bool = True) -> bytes:
    completed = subprocess.run(["git", *args], cwd=repository, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=120)
    if check and completed.returncode != 0:
        raise ForensicError(f"git {' '.join(args)} failed: " + completed.stderr.decode("utf-8", errors="replace").strip())
    return completed.stdout


def validate_sha256(value: str, label: str) -> str:
    normalized = value.upper()
    if len(normalized) != 64 or any(ch not in SHA256_HEX for ch in normalized):
        raise ForensicError(f"{label} is not a SHA-256 value")
    return normalized


def load_json_bytes(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ForensicError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ForensicError(f"{label} JSON root is not an object")
    return value


def normalize_lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def with_final_newline(data: bytes, newline: bytes) -> bytes:
    return data.rstrip(b"\r\n") + newline


def without_final_newline(data: bytes) -> bytes:
    return data.rstrip(b"\r\n")


def serialization_candidates(commit_blob: bytes) -> dict[str, bytes]:
    document = load_json_bytes(commit_blob, "execution commit preregistration")
    lf = normalize_lf(commit_blob)
    crlf = lf.replace(b"\n", b"\r\n")
    cr = lf.replace(b"\n", b"\r")
    candidates: dict[str, bytes] = {
        "commit-blob-exact": commit_blob,
        "commit-blob-lf": lf,
        "commit-blob-crlf": crlf,
        "commit-blob-cr": cr,
        "commit-blob-lf-no-final-newline": without_final_newline(lf),
        "commit-blob-crlf-no-final-newline": without_final_newline(crlf),
        "commit-blob-cr-no-final-newline": without_final_newline(cr),
        "commit-blob-lf-final-newline": with_final_newline(lf, b"\n"),
        "commit-blob-crlf-final-newline": with_final_newline(crlf, b"\r\n"),
        "commit-blob-cr-final-newline": with_final_newline(cr, b"\r"),
        "canonical-compact": canonical_json_bytes(document),
    }
    for sort_keys in (False, True):
        order = "sorted" if sort_keys else "preserve-order"
        text = json.dumps(document, ensure_ascii=False, allow_nan=False, sort_keys=sort_keys, indent=2).encode("utf-8")
        for newline_name, newline in (("lf", b"\n"), ("crlf", b"\r\n"), ("cr", b"\r")):
            rendered = normalize_lf(text).replace(b"\n", newline)
            candidates[f"pretty-{order}-{newline_name}-no-final-newline"] = without_final_newline(rendered)
            candidates[f"pretty-{order}-{newline_name}-final-newline"] = with_final_newline(rendered, newline)
    for name, data in list(candidates.items()):
        candidates[f"utf8-bom:{name}"] = b"\xef\xbb\xbf" + data
    return candidates


def candidate_report(candidates: Mapping[str, bytes], expected_sha256: str) -> dict[str, Any]:
    rows = [{"name": name, "sha256": sha256_bytes(data), "size_bytes": len(data)} for name, data in candidates.items()]
    matches = [row for row in rows if row["sha256"] == expected_sha256]
    return {"candidate_count": len(rows), "matches": matches, "candidates": rows}


def git_text_state(repository: Path, relative_path: str) -> dict[str, Any]:
    def optional(*args: str) -> str | None:
        completed = subprocess.run(["git", *args], cwd=repository, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30)
        if completed.returncode != 0:
            return None
        return completed.stdout.decode("utf-8", errors="replace").strip()
    return {
        "check_attr": optional("check-attr", "-a", "--", relative_path),
        "ls_files_eol": optional("ls-files", "--eol", "--", relative_path),
        "core_autocrlf": optional("config", "--get", "core.autocrlf"),
        "core_eol": optional("config", "--get", "core.eol"),
        "working_tree_encoding": optional("check-attr", "working-tree-encoding", "--", relative_path),
        "status_porcelain": optional("status", "--porcelain=v1", "--", relative_path),
    }


def manifest_binding(manifest: Mapping[str, Any]) -> tuple[str, str]:
    projection = manifest.get("balanced_preregistration")
    if not isinstance(projection, Mapping):
        raise ForensicError("manifest lacks balanced_preregistration projection")
    artifact = validate_sha256(str(projection.get("artifact_sha256", "")), "manifest artifact hash")
    document = validate_sha256(str(projection.get("document_sha256", "")), "manifest document hash")
    return artifact, document


def scan_git_object_database(repository: Path, expected_sha256: str) -> list[dict[str, Any]]:
    listing = run_git(repository, "cat-file", "--batch-all-objects", "--batch-check=%(objectname) %(objecttype) %(objectsize)")
    matches: list[dict[str, Any]] = []
    for line in listing.decode("ascii", errors="replace").splitlines():
        parts = line.split()
        if len(parts) != 3 or parts[1] != "blob":
            continue
        oid, _, size_text = parts
        try:
            size = int(size_text)
        except ValueError:
            continue
        if size < 1024 or size > 2_000_000:
            continue
        data = run_git(repository, "cat-file", "blob", oid)
        if sha256_bytes(data) == expected_sha256:
            matches.append({"object_id": oid, "size_bytes": size})
    return matches


def audit(repository: Path, execution_commit: str, relative_path: str, manifest_path: Path, *, scan_object_db: bool) -> dict[str, Any]:
    repository = repository.resolve()
    manifest_bytes = manifest_path.read_bytes()
    manifest = load_json_bytes(manifest_bytes, "manifest")
    expected_artifact, expected_document = manifest_binding(manifest)
    commit_blob = run_git(repository, "show", f"{execution_commit}:{relative_path}")
    commit_document = load_json_bytes(commit_blob, "execution commit preregistration")
    commit_blob_sha = sha256_bytes(commit_blob)
    commit_document_sha = canonical_json_sha256(commit_document)
    index_blob: bytes | None = None
    try:
        index_blob = run_git(repository, "show", f":{relative_path}")
    except ForensicError:
        pass
    worktree_path = repository / relative_path
    worktree_blob = worktree_path.read_bytes() if worktree_path.is_file() else None
    candidates = serialization_candidates(commit_blob)
    if index_blob is not None:
        candidates["current-index-blob"] = index_blob
    if worktree_blob is not None:
        candidates["current-worktree-bytes"] = worktree_blob
    report = candidate_report(candidates, expected_artifact)
    object_matches = scan_git_object_database(repository, expected_artifact) if scan_object_db else []
    semantic_match = commit_document_sha == expected_document
    if commit_blob_sha == expected_artifact:
        verdict = "BYTE_EXACT_MATCH_EXECUTION_COMMIT_BLOB"
    elif report["matches"]:
        verdict = "BYTE_EXACT_MATCH_KNOWN_LOCAL_VARIANT"
    elif object_matches:
        verdict = "BYTE_EXACT_MATCH_GIT_OBJECT_DATABASE"
    elif semantic_match:
        verdict = "SEMANTIC_IDENTITY_ONLY_BYTE_STATE_UNRECOVERED"
    else:
        verdict = "SEMANTIC_IDENTITY_MISMATCH"
    return {
        "schema_version": 1,
        "status": "complete",
        "read_only": True,
        "repository": str(repository),
        "execution_commit": execution_commit,
        "relative_path": relative_path,
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "expected_artifact_sha256": expected_artifact,
        "expected_document_sha256": expected_document,
        "execution_commit_blob": {"sha256": commit_blob_sha, "size_bytes": len(commit_blob), "canonical_document_sha256": commit_document_sha},
        "current_index_blob": None if index_blob is None else {"sha256": sha256_bytes(index_blob), "size_bytes": len(index_blob)},
        "current_worktree": None if worktree_blob is None else {"sha256": sha256_bytes(worktree_blob), "size_bytes": len(worktree_blob)},
        "git_text_state": git_text_state(repository, relative_path),
        "candidate_reconstruction": report,
        "object_database_scan_enabled": scan_object_db,
        "object_database_matches": object_matches,
        "semantic_document_identity_matches": semantic_match,
        "verdict": verdict,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--execution-commit", required=True)
    parser.add_argument("--preregistration-path", required=True)
    parser.add_argument("--manifest-path", type=Path, required=True)
    parser.add_argument("--scan-object-db", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = audit(args.repository, args.execution_commit, args.preregistration_path, args.manifest_path, scan_object_db=args.scan_object_db)
    except (ForensicError, OSError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, sort_keys=True))
        return 1
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8", newline="\n")
    print(encoded, end="")
    return 0 if result["verdict"] != "SEMANTIC_IDENTITY_MISMATCH" else 2


if __name__ == "__main__":
    raise SystemExit(main())
