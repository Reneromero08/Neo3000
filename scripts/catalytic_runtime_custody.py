#!/usr/bin/env python3
"""Fail-closed Git and ignored-evidence custody for catalytic runtimes.

The ordinary Git status is necessary but insufficient for one-shot runtime
evidence because the evidence namespaces are intentionally ignored.  This
module therefore freezes both ordinary and tracked status plus a byte-level
inventory of every CS1 evidence namespace before a claim.  After a claim, only
the exact authorized artifact paths may differ.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import stat
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence


DEFAULT_HISTORICAL_CS1_ROOTS = (
    "state/catalytic_swarm_1",
    "state/catalytic_swarm_1_cache_diagnostic",
    "state/catalytic_swarm_1_v2",
    "state/catalytic_swarm_1_v3",
    "state/catalytic_swarm_1_v4",
    "state/catalytic_swarm_1_v5",
)

DEFAULT_CS1_EVIDENCE_ROOT_PATTERNS = (
    "state/catalytic_swarm_1",
    "state/catalytic_swarm_1_cache_diagnostic",
    "state/catalytic_swarm_1_v*",
)


class CustodyViolation(RuntimeError):
    """Raised when preclaim or postclaim custody cannot be proven."""


@dataclass(frozen=True)
class GitStatusEntry:
    code: str
    path: str
    original_path: str | None = None

    @property
    def paths(self) -> tuple[str, ...]:
        if self.original_path is None:
            return (self.path,)
        return (self.path, self.original_path)


@dataclass(frozen=True)
class GitStatusSnapshot:
    ordinary: tuple[GitStatusEntry, ...]
    tracked: tuple[GitStatusEntry, ...]
    untracked_paths: tuple[str, ...]
    tracked_worktree_paths: tuple[str, ...]
    staged_paths: tuple[str, ...]

    @property
    def clean(self) -> bool:
        return not (
            self.ordinary
            or self.tracked
            or self.untracked_paths
            or self.tracked_worktree_paths
            or self.staged_paths
        )


@dataclass(frozen=True)
class EvidenceEntry:
    path: str
    kind: str
    size_bytes: int | None
    sha256: str | None
    ignored: bool


@dataclass(frozen=True)
class NamespaceSnapshot:
    root: str
    exists: bool
    root_kind: str
    entries: tuple[EvidenceEntry, ...]
    sha256: str

    @property
    def ignored_paths(self) -> tuple[str, ...]:
        return tuple(entry.path for entry in self.entries if entry.ignored)


@dataclass(frozen=True)
class PreclaimCustodySnapshot:
    repository_root: str
    authorized_root: str
    allowed_paths: tuple[str, ...]
    historical_roots: tuple[str, ...]
    evidence_root_patterns: tuple[str, ...]
    status_before_inventory: GitStatusSnapshot
    status_after_inventory: GitStatusSnapshot
    historical_namespaces: tuple[NamespaceSnapshot, ...]
    evidence_namespaces: tuple[NamespaceSnapshot, ...]

    @property
    def ignored_evidence_paths(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    path
                    for namespace in self.evidence_namespaces
                    for path in namespace.ignored_paths
                }
            )
        )


@dataclass(frozen=True)
class PostclaimCustodyReport:
    status: GitStatusSnapshot
    changed_evidence_paths: tuple[str, ...]
    ignored_evidence_paths: tuple[str, ...]
    historical_namespace_hashes: tuple[tuple[str, str], ...]
    evidence_namespaces: tuple[NamespaceSnapshot, ...]


def _run_git(
    repository_root: Path,
    arguments: Sequence[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    completed = subprocess.run(
        ["git", "-C", str(repository_root), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=environment,
    )
    if check and completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise CustodyViolation(
            f"Git custody command failed ({' '.join(arguments)}): {stderr}"
        )
    return completed


def _normalize_repo_path(value: str | os.PathLike[str], *, label: str) -> str:
    raw = os.fspath(value).replace("\\", "/")
    if not raw or raw.startswith("/") or ":" in raw:
        raise ValueError(f"{label} must be a nonempty repository-relative path")
    parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{label} must be canonical and cannot traverse directories")
    normalized = PurePosixPath(*parts).as_posix()
    if normalized != raw:
        raise ValueError(f"{label} must already be canonical: {raw!r}")
    return normalized


def _normalize_pattern(value: str, *, label: str) -> str:
    raw = value.replace("\\", "/")
    if not raw or raw.startswith("/") or ":" in raw:
        raise ValueError(f"{label} must be a repository-relative pattern")
    parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{label} must be canonical and cannot traverse directories")
    return raw


def _is_same_or_descendant(path: str, root: str) -> bool:
    return path == root or path.startswith(f"{root}/")


def _paths_overlap(left: str, right: str) -> bool:
    return _is_same_or_descendant(left, right) or _is_same_or_descendant(
        right, left
    )


def _resolve_repository_root(value: str | os.PathLike[str]) -> Path:
    requested = Path(value).resolve()
    completed = _run_git(requested, ["rev-parse", "--show-toplevel"])
    observed_text = completed.stdout.decode("utf-8", errors="strict").strip()
    observed = Path(observed_text).resolve()
    if observed != requested:
        raise CustodyViolation(
            f"custody root must be the Git worktree root: {requested} != {observed}"
        )
    return requested


def _decode_git_path(value: bytes) -> str:
    return value.decode("utf-8", errors="surrogateescape").replace("\\", "/")


def _parse_porcelain_z(payload: bytes) -> tuple[GitStatusEntry, ...]:
    tokens = payload.split(b"\0")
    entries: list[GitStatusEntry] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if not token:
            continue
        if len(token) < 4 or token[2:3] != b" ":
            raise CustodyViolation("malformed NUL-delimited Git status entry")
        code = token[:2].decode("ascii", errors="strict")
        path = _decode_git_path(token[3:])
        original_path: str | None = None
        if "R" in code or "C" in code:
            if index >= len(tokens) or not tokens[index]:
                raise CustodyViolation("malformed Git rename/copy status entry")
            original_path = _decode_git_path(tokens[index])
            index += 1
        entries.append(GitStatusEntry(code, path, original_path))
    return tuple(entries)


def capture_git_status(
    repository_root: str | os.PathLike[str],
) -> GitStatusSnapshot:
    """Capture ordinary status and an explicit tracked-only status."""

    root = _resolve_repository_root(repository_root)
    ordinary = _parse_porcelain_z(
        _run_git(
            root,
            [
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=all",
                "--ignore-submodules=none",
            ],
        ).stdout
    )
    tracked = _parse_porcelain_z(
        _run_git(
            root,
            [
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=no",
                "--ignore-submodules=none",
            ],
        ).stdout
    )
    worktree_paths: set[str] = set()
    staged_paths: set[str] = set()
    untracked_paths: set[str] = set()
    for entry in ordinary:
        if entry.code == "??":
            untracked_paths.update(entry.paths)
    for entry in tracked:
        if entry.code[1] not in {" ", "?"}:
            worktree_paths.update(entry.paths)
        if entry.code[0] not in {" ", "?"}:
            staged_paths.update(entry.paths)
    return GitStatusSnapshot(
        ordinary=ordinary,
        tracked=tracked,
        untracked_paths=tuple(sorted(untracked_paths)),
        tracked_worktree_paths=tuple(sorted(worktree_paths)),
        staged_paths=tuple(sorted(staged_paths)),
    )


def _status_summary(status_snapshot: GitStatusSnapshot) -> str:
    ordinary = [f"{entry.code} {entry.path}" for entry in status_snapshot.ordinary]
    tracked = [f"{entry.code} {entry.path}" for entry in status_snapshot.tracked]
    return (
        f"ordinary={ordinary}; tracked={tracked}; "
        f"untracked={list(status_snapshot.untracked_paths)}; "
        f"worktree={list(status_snapshot.tracked_worktree_paths)}; "
        f"staged={list(status_snapshot.staged_paths)}"
    )


def _is_ignored(repository_root: Path, path: str) -> bool:
    completed = _run_git(
        repository_root,
        ["check-ignore", "--no-index", "--quiet", "--", path],
        check=False,
    )
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    stderr = completed.stderr.decode("utf-8", errors="replace").strip()
    raise CustodyViolation(f"could not classify ignored evidence {path}: {stderr}")


def _stable_file_hash(path: Path) -> tuple[int, str]:
    before = path.stat(follow_symlinks=False)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    after = path.stat(follow_symlinks=False)
    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    )
    if before_identity != after_identity:
        raise CustodyViolation(f"evidence changed while hashing: {path}")
    return before.st_size, digest.hexdigest()


def _entry_for_path(repository_root: Path, path: Path) -> EvidenceEntry:
    relative = path.relative_to(repository_root).as_posix()
    metadata = path.lstat()
    mode = metadata.st_mode
    if stat.S_ISLNK(mode):
        target = os.readlink(path)
        encoded = os.fsencode(target)
        return EvidenceEntry(
            path=relative,
            kind="symlink",
            size_bytes=len(encoded),
            sha256=hashlib.sha256(encoded).hexdigest(),
            ignored=_is_ignored(repository_root, relative),
        )
    if stat.S_ISDIR(mode):
        return EvidenceEntry(
            path=relative,
            kind="directory",
            size_bytes=None,
            sha256=None,
            ignored=_is_ignored(repository_root, relative),
        )
    if stat.S_ISREG(mode):
        size_bytes, digest = _stable_file_hash(path)
        return EvidenceEntry(
            path=relative,
            kind="file",
            size_bytes=size_bytes,
            sha256=digest,
            ignored=_is_ignored(repository_root, relative),
        )
    raise CustodyViolation(f"unsupported evidence file type: {relative}")


def _namespace_digest(
    root: str,
    exists: bool,
    root_kind: str,
    entries: Sequence[EvidenceEntry],
) -> str:
    value = {
        "root": root,
        "exists": exists,
        "root_kind": root_kind,
        "entries": [asdict(entry) for entry in entries],
    }
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def snapshot_namespace(
    repository_root: str | os.PathLike[str],
    namespace_root: str,
) -> NamespaceSnapshot:
    """Hash a namespace directly, including files hidden by Git ignores."""

    root = _resolve_repository_root(repository_root)
    normalized_root = _normalize_repo_path(namespace_root, label="namespace root")
    absolute = root / PurePosixPath(normalized_root)
    exists = os.path.lexists(absolute)
    entries: list[EvidenceEntry] = []
    root_kind = "absent"
    if exists:
        metadata = absolute.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            root_kind = "symlink"
            entries.append(_entry_for_path(root, absolute))
        elif stat.S_ISREG(metadata.st_mode):
            root_kind = "file"
            entries.append(_entry_for_path(root, absolute))
        elif stat.S_ISDIR(metadata.st_mode):
            root_kind = "directory"
            for current, directories, files in os.walk(absolute, followlinks=False):
                directories.sort()
                files.sort()
                current_path = Path(current)
                for name in directories:
                    entries.append(_entry_for_path(root, current_path / name))
                for name in files:
                    entries.append(_entry_for_path(root, current_path / name))
        else:
            raise CustodyViolation(
                f"unsupported evidence namespace type: {normalized_root}"
            )
    entries.sort(key=lambda entry: entry.path)
    frozen_entries = tuple(entries)
    return NamespaceSnapshot(
        root=normalized_root,
        exists=exists,
        root_kind=root_kind,
        entries=frozen_entries,
        sha256=_namespace_digest(
            normalized_root,
            exists,
            root_kind,
            frozen_entries,
        ),
    )


def _discover_evidence_roots(
    repository_root: Path,
    patterns: Sequence[str],
    fixed_roots: Iterable[str],
) -> tuple[str, ...]:
    roots = set(fixed_roots)
    for pattern in patterns:
        if not any(character in pattern for character in "*?["):
            roots.add(pattern)
            continue
        pattern_path = PurePosixPath(pattern)
        parent = repository_root / pattern_path.parent
        if not parent.is_dir():
            continue
        for child in parent.iterdir():
            relative = child.relative_to(repository_root).as_posix()
            if fnmatch.fnmatchcase(relative, pattern):
                roots.add(relative)
    return tuple(sorted(roots))


def _snapshot_namespaces(
    repository_root: Path,
    roots: Iterable[str],
) -> tuple[NamespaceSnapshot, ...]:
    return tuple(
        snapshot_namespace(repository_root, root) for root in sorted(set(roots))
    )


def _namespace_map(
    values: Iterable[NamespaceSnapshot],
) -> dict[str, NamespaceSnapshot]:
    return {value.root: value for value in values}


def _evidence_fingerprints(
    namespaces: Iterable[NamespaceSnapshot],
) -> dict[str, tuple[object, ...]]:
    fingerprints: dict[str, tuple[object, ...]] = {}
    for namespace in namespaces:
        fingerprints[f"{namespace.root}/"] = (
            "namespace",
            namespace.exists,
            namespace.root_kind,
        )
        for entry in namespace.entries:
            fingerprints[entry.path] = (
                entry.kind,
                entry.size_bytes,
                entry.sha256,
                entry.ignored,
            )
    return fingerprints


def _changed_paths(
    before: dict[str, tuple[object, ...]],
    after: dict[str, tuple[object, ...]],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            path
            for path in before.keys() | after.keys()
            if before.get(path) != after.get(path)
        )
    )


def _prepare_contract(
    authorized_root: str,
    allowed_paths: Iterable[str],
    historical_roots: Iterable[str],
    evidence_root_patterns: Iterable[str],
) -> tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    normalized_authorized = _normalize_repo_path(
        authorized_root, label="authorized root"
    )
    normalized_allowed = tuple(
        sorted(
            {
                _normalize_repo_path(path, label="allowed path")
                for path in allowed_paths
            }
        )
    )
    if not normalized_allowed:
        raise ValueError("at least one exact allowed path is required")
    for path in normalized_allowed:
        if path == normalized_authorized or not _is_same_or_descendant(
            path, normalized_authorized
        ):
            raise ValueError(
                f"allowed path must be a file below the authorized root: {path}"
            )
    normalized_historical = tuple(
        sorted(
            {
                _normalize_repo_path(path, label="historical root")
                for path in historical_roots
            }
        )
    )
    for historical in normalized_historical:
        if _paths_overlap(historical, normalized_authorized):
            raise ValueError(
                "historical roots must be disjoint from the authorized root: "
                f"{historical}"
            )
    normalized_patterns = tuple(
        sorted(
            {
                _normalize_pattern(pattern, label="evidence root pattern")
                for pattern in evidence_root_patterns
            }
        )
    )
    return (
        normalized_authorized,
        normalized_allowed,
        normalized_historical,
        normalized_patterns,
    )


def capture_preclaim_custody(
    repository_root: str | os.PathLike[str],
    *,
    authorized_root: str,
    allowed_paths: Iterable[str],
    historical_roots: Iterable[str] = DEFAULT_HISTORICAL_CS1_ROOTS,
    evidence_root_patterns: Iterable[str] = DEFAULT_CS1_EVIDENCE_ROOT_PATTERNS,
) -> PreclaimCustodySnapshot:
    """Freeze clean preclaim status and all historical/ignored CS1 evidence."""

    root = _resolve_repository_root(repository_root)
    (
        normalized_authorized,
        normalized_allowed,
        normalized_historical,
        normalized_patterns,
    ) = _prepare_contract(
        authorized_root,
        allowed_paths,
        historical_roots,
        evidence_root_patterns,
    )

    status_before = capture_git_status(root)
    if not status_before.clean:
        raise CustodyViolation(
            "preclaim worktree is not clean: " + _status_summary(status_before)
        )

    evidence_roots = _discover_evidence_roots(
        root,
        normalized_patterns,
        (*normalized_historical, normalized_authorized),
    )
    discovered_historical = tuple(
        candidate
        for candidate in evidence_roots
        if candidate != normalized_authorized
    )
    for historical_root in discovered_historical:
        if _paths_overlap(historical_root, normalized_authorized):
            raise CustodyViolation(
                "discovered historical namespace overlaps the authorized root: "
                f"{historical_root}"
            )
    resolved_historical = tuple(
        sorted(set(normalized_historical) | set(discovered_historical))
    )
    historical = _snapshot_namespaces(root, resolved_historical)
    evidence = _snapshot_namespaces(root, evidence_roots)

    status_after = capture_git_status(root)
    if not status_after.clean or status_after != status_before:
        raise CustodyViolation(
            "preclaim status changed while evidence was inventoried: "
            + _status_summary(status_after)
        )

    return PreclaimCustodySnapshot(
        repository_root=str(root),
        authorized_root=normalized_authorized,
        allowed_paths=normalized_allowed,
        historical_roots=resolved_historical,
        evidence_root_patterns=normalized_patterns,
        status_before_inventory=status_before,
        status_after_inventory=status_after,
        historical_namespaces=historical,
        evidence_namespaces=evidence,
    )


def _illegal_status_paths(
    status_snapshot: GitStatusSnapshot,
    allowed_paths: set[str],
) -> tuple[str, ...]:
    observed: set[str] = set()
    for entry in (*status_snapshot.ordinary, *status_snapshot.tracked):
        observed.update(entry.paths)
    observed.update(status_snapshot.tracked_worktree_paths)
    observed.update(status_snapshot.staged_paths)
    return tuple(sorted(path for path in observed if path not in allowed_paths))


def _allowed_evidence_change(
    path: str,
    *,
    authorized_root: str,
    allowed_paths: set[str],
) -> bool:
    marker = path[:-1] if path.endswith("/") else path
    if marker == authorized_root:
        return True
    if path in allowed_paths:
        return True
    return any(allowed.startswith(f"{marker}/") for allowed in allowed_paths)


def _validate_authorized_change_kinds(
    changed_paths: Iterable[str],
    after_fingerprints: dict[str, tuple[object, ...]],
    *,
    authorized_root: str,
    allowed_paths: set[str],
) -> None:
    """Reject type tricks at exact files or their newly created ancestors."""

    for path in changed_paths:
        marker = path[:-1] if path.endswith("/") else path
        if marker == authorized_root:
            continue
        fingerprint = after_fingerprints.get(path)
        if fingerprint is None:
            # Deleting a previously present allowlisted file changes only that
            # exact path.  Existence requirements belong to the caller's claim
            # contract, while this primitive owns mutation custody.
            continue
        if path in allowed_paths:
            if fingerprint[0] != "file":
                raise CustodyViolation(
                    "postclaim authorized artifact is not a regular file: " + path
                )
            continue
        if any(allowed.startswith(f"{marker}/") for allowed in allowed_paths):
            if fingerprint[0] != "directory":
                raise CustodyViolation(
                    "postclaim authorized artifact ancestor is not a directory: "
                    + marker
                )


def validate_postclaim_custody(
    preclaim: PreclaimCustodySnapshot,
) -> PostclaimCustodyReport:
    """Require all postclaim changes to be exact authorized evidence paths."""

    root = _resolve_repository_root(preclaim.repository_root)
    allowed_paths = set(preclaim.allowed_paths)
    status_before_inventory = capture_git_status(root)
    if (
        status_before_inventory.tracked
        or status_before_inventory.tracked_worktree_paths
        or status_before_inventory.staged_paths
    ):
        raise CustodyViolation(
            "postclaim tracked or staged changes are never authorized runtime state: "
            + _status_summary(status_before_inventory)
        )
    illegal_status = _illegal_status_paths(status_before_inventory, allowed_paths)
    if illegal_status:
        raise CustodyViolation(
            "postclaim Git changes escaped the exact allowed paths: "
            + ", ".join(illegal_status)
        )

    historical_after = _snapshot_namespaces(root, preclaim.historical_roots)
    historical_before_map = _namespace_map(preclaim.historical_namespaces)
    for observed in historical_after:
        expected = historical_before_map[observed.root]
        if observed != expected:
            raise CustodyViolation(
                "historical CS1 predecessor namespace changed: "
                f"{observed.root} ({expected.sha256} != {observed.sha256})"
            )

    authorized_absolute = root / PurePosixPath(preclaim.authorized_root)
    if not authorized_absolute.is_dir() or authorized_absolute.is_symlink():
        raise CustodyViolation(
            "postclaim authorized runtime root must be a real directory: "
            + preclaim.authorized_root
        )

    evidence_roots = _discover_evidence_roots(
        root,
        preclaim.evidence_root_patterns,
        (*preclaim.historical_roots, preclaim.authorized_root),
    )
    evidence_after = _snapshot_namespaces(root, evidence_roots)
    before_fingerprints = _evidence_fingerprints(preclaim.evidence_namespaces)
    after_fingerprints = _evidence_fingerprints(evidence_after)
    changed_evidence = _changed_paths(before_fingerprints, after_fingerprints)
    illegal_evidence = tuple(
        path
        for path in changed_evidence
        if not _allowed_evidence_change(
            path,
            authorized_root=preclaim.authorized_root,
            allowed_paths=allowed_paths,
        )
    )
    if illegal_evidence:
        raise CustodyViolation(
            "postclaim ignored evidence escaped the exact authorized root/paths: "
            + ", ".join(illegal_evidence)
        )
    _validate_authorized_change_kinds(
        changed_evidence,
        after_fingerprints,
        authorized_root=preclaim.authorized_root,
        allowed_paths=allowed_paths,
    )

    status_after_inventory = capture_git_status(root)
    if status_after_inventory != status_before_inventory:
        raise CustodyViolation("postclaim Git status changed during custody inventory")

    ignored_paths = tuple(
        sorted(
            {
                path
                for namespace in evidence_after
                for path in namespace.ignored_paths
            }
        )
    )
    return PostclaimCustodyReport(
        status=status_after_inventory,
        changed_evidence_paths=changed_evidence,
        ignored_evidence_paths=ignored_paths,
        historical_namespace_hashes=tuple(
            (namespace.root, namespace.sha256) for namespace in historical_after
        ),
        evidence_namespaces=evidence_after,
    )


# Short aliases for controller call sites while retaining explicit public names.
capture_preclaim = capture_preclaim_custody
validate_postclaim = validate_postclaim_custody
