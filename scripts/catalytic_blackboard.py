#!/usr/bin/env python3
"""Append-only, phase-routed blackboard for CatalyticSwarm-0.

The blackboard is deliberately small and deterministic. Workers never exchange
full transcripts or communicate pairwise. They publish compact claim objects to
an append-only hash chain, and later phases receive only bounded entries from
earlier phases.

The phase codes are exact Walsh/Hadamard routing identities. They are a logical
routing device only; they do not claim physical superposition of model state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

PHASES = ("proposal", "evidence", "critique", "synthesis")
PHASE_INDEX = {phase: index for index, phase in enumerate(PHASES)}
PHASE_CODES: dict[str, tuple[int, int, int, int]] = {
    "proposal":  (1,  1,  1,  1),
    "evidence":  (1, -1,  1, -1),
    "critique":  (1,  1, -1, -1),
    "synthesis": (1, -1, -1,  1),
}
GENESIS_HASH = "0" * 64


class BlackboardError(RuntimeError):
    """A blackboard integrity, phase, or size law was violated."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def phase_dot(left: str, right: str) -> int:
    try:
        a = PHASE_CODES[left]
        b = PHASE_CODES[right]
    except KeyError as exc:
        raise BlackboardError(f"unknown phase: {exc.args[0]}") from exc
    return sum(x * y for x, y in zip(a, b, strict=True))


def verify_phase_codes() -> bool:
    for phase in PHASES:
        if phase_dot(phase, phase) != 4:
            return False
    for index, left in enumerate(PHASES):
        for right in PHASES[index + 1:]:
            if phase_dot(left, right) != 0:
                return False
    return True


@dataclass(frozen=True)
class BlackboardEntry:
    schema_version: int
    sequence: int
    entry_id: str
    phase: str
    kind: str
    author_worker_id: str
    phase_code: tuple[int, int, int, int]
    body: Mapping[str, Any]
    references: tuple[str, ...]
    parent_ids: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    previous_hash: str
    entry_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "sequence": self.sequence,
            "entry_id": self.entry_id,
            "phase": self.phase,
            "kind": self.kind,
            "author_worker_id": self.author_worker_id,
            "phase_code": list(self.phase_code),
            "body": _thaw_json(self.body),
            "references": list(self.references),
            "parent_ids": list(self.parent_ids),
            "artifact_refs": list(self.artifact_refs),
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
        }


class AppendOnlyBlackboard:
    """Bounded append-only blackboard with a canonical hash chain."""

    def __init__(
        self,
        *,
        max_entries: int = 256,
        max_entry_bytes: int = 2048,
        max_references: int = 8,
        max_parents: int = 8,
        max_artifacts: int = 8,
    ) -> None:
        if max_entries <= 0 or max_entry_bytes <= 0:
            raise ValueError("blackboard limits must be positive")
        if min(max_references, max_parents, max_artifacts) < 0:
            raise ValueError("blackboard list limits must be nonnegative")
        self.max_entries = max_entries
        self.max_entry_bytes = max_entry_bytes
        self.max_references = max_references
        self.max_parents = max_parents
        self.max_artifacts = max_artifacts
        self._entries: list[BlackboardEntry] = []
        self._by_id: dict[str, BlackboardEntry] = {}
        self._head_hash = GENESIS_HASH

    @property
    def head_hash(self) -> str:
        return self._head_hash

    @property
    def sequence(self) -> int:
        return len(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def entries(self) -> tuple[BlackboardEntry, ...]:
        return tuple(self._entries)

    def get(self, entry_id: str) -> BlackboardEntry:
        try:
            return self._by_id[entry_id]
        except KeyError as exc:
            raise BlackboardError(f"unknown blackboard entry: {entry_id}") from exc

    def _validate_phase(self, phase: str) -> None:
        if phase not in PHASE_INDEX:
            raise BlackboardError(f"unknown phase: {phase}")

    def _validate_parents(self, phase: str, parent_ids: Sequence[str]) -> None:
        for parent_id in parent_ids:
            parent = self.get(parent_id)
            if PHASE_INDEX[parent.phase] >= PHASE_INDEX[phase]:
                raise BlackboardError(
                    f"entry in {phase} cannot depend on same/later phase parent "
                    f"{parent_id} ({parent.phase})"
                )

    @staticmethod
    def _normalize_strings(
        name: str,
        values: Sequence[str],
        *,
        ceiling: int,
    ) -> tuple[str, ...]:
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            raise BlackboardError(f"{name} must be a sequence of strings")
        normalized = tuple(values)
        if len(normalized) > ceiling:
            raise BlackboardError(f"{name} ceiling exceeded")
        if any(not isinstance(item, str) or not item for item in normalized):
            raise BlackboardError(f"{name} contains an invalid value")
        if len(set(normalized)) != len(normalized):
            raise BlackboardError(f"duplicate {name}")
        return normalized

    def append(
        self,
        *,
        phase: str,
        kind: str,
        author_worker_id: str,
        body: Mapping[str, Any],
        references: Sequence[str] = (),
        parent_ids: Sequence[str] = (),
        artifact_refs: Sequence[str] = (),
    ) -> BlackboardEntry:
        self._validate_phase(phase)
        if len(self._entries) >= self.max_entries:
            raise BlackboardError("blackboard entry ceiling exceeded")
        if (
            not isinstance(kind, str)
            or not kind
            or not isinstance(author_worker_id, str)
            or not author_worker_id
        ):
            raise BlackboardError("kind and author_worker_id are required")
        if not isinstance(body, Mapping):
            raise BlackboardError("blackboard entry body must be an object")
        normalized_references = self._normalize_strings(
            "references", references, ceiling=self.max_references
        )
        normalized_parents = self._normalize_strings(
            "parent IDs", parent_ids, ceiling=self.max_parents
        )
        normalized_artifacts = self._normalize_strings(
            "artifact references", artifact_refs, ceiling=self.max_artifacts
        )
        self._validate_parents(phase, normalized_parents)

        try:
            normalized_body = json.loads(canonical_json_bytes(dict(body)).decode("utf-8"))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise BlackboardError("blackboard entry body is not strict JSON") from exc

        sequence = len(self._entries) + 1
        identity_payload = {
            "schema_version": 1,
            "sequence": sequence,
            "phase": phase,
            "kind": kind,
            "author_worker_id": author_worker_id,
            "phase_code": list(PHASE_CODES[phase]),
            "body": normalized_body,
            "references": list(normalized_references),
            "parent_ids": list(normalized_parents),
            "artifact_refs": list(normalized_artifacts),
            "previous_hash": self._head_hash,
        }
        entry_hash = sha256_bytes(canonical_json_bytes(identity_payload))
        entry_id = f"bb-{sequence:04d}-{entry_hash[:16].lower()}"
        entry = BlackboardEntry(
            schema_version=1,
            sequence=sequence,
            entry_id=entry_id,
            phase=phase,
            kind=kind,
            author_worker_id=author_worker_id,
            phase_code=PHASE_CODES[phase],
            body=_freeze_json(normalized_body),
            references=normalized_references,
            parent_ids=normalized_parents,
            artifact_refs=normalized_artifacts,
            previous_hash=self._head_hash,
            entry_hash=entry_hash,
        )
        if len(canonical_json_bytes(entry.to_dict())) > self.max_entry_bytes:
            raise BlackboardError(
                f"complete blackboard entry exceeds {self.max_entry_bytes} bytes"
            )
        self._entries.append(entry)
        self._by_id[entry.entry_id] = entry
        self._head_hash = entry.entry_hash
        return entry

    def entries_before_phase(self, phase: str) -> tuple[BlackboardEntry, ...]:
        """Return only entries from strictly earlier phases."""
        self._validate_phase(phase)
        cutoff = PHASE_INDEX[phase]
        return tuple(
            entry for entry in self._entries if PHASE_INDEX[entry.phase] < cutoff
        )

    def select_entries(
        self,
        *,
        phase: str,
        parent_ids: Sequence[str],
        limit: int,
        include_verified_only: bool = False,
        verified_entry_ids: Iterable[str] = (),
    ) -> tuple[BlackboardEntry, ...]:
        """Select bounded prior-phase context without all-to-all broadcast."""
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise BlackboardError("context limit must be a nonnegative integer")
        if len(parent_ids) > limit:
            raise BlackboardError("assigned parent set exceeds the context limit")
        if not parent_ids:
            return ()
        if len(set(parent_ids)) != len(parent_ids):
            raise BlackboardError("duplicate selected parent IDs")
        available = {entry.entry_id: entry for entry in self.entries_before_phase(phase)}
        verified = set(verified_entry_ids)
        selected: list[BlackboardEntry] = []
        for parent_id in parent_ids:
            entry = available.get(parent_id)
            if entry is None:
                raise BlackboardError(
                    f"worker requested unavailable prior-phase parent: {parent_id}"
                )
            if include_verified_only and parent_id not in verified:
                raise BlackboardError(
                    f"assigned synthesis parent is not verifier-accepted: {parent_id}"
                )
            selected.append(entry)
        return tuple(selected)

    def verify_chain(self) -> bool:
        if self._by_id != {entry.entry_id: entry for entry in self._entries}:
            return False
        return verify_blackboard_snapshot(
            self.snapshot(),
            max_entry_bytes=self.max_entry_bytes,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "append_only": True,
            "phase_codes": {key: list(value) for key, value in PHASE_CODES.items()},
            "phase_codes_orthogonal": verify_phase_codes(),
            "entry_count": len(self._entries),
            "head_hash": self._head_hash,
            "entries": [entry.to_dict() for entry in self._entries],
        }


def verify_blackboard_snapshot(
    snapshot: Mapping[str, Any],
    *,
    max_entry_bytes: int = 2048,
) -> bool:
    """Independently verify a complete serialized blackboard snapshot."""
    if max_entry_bytes <= 0 or not isinstance(snapshot, Mapping):
        return False
    required_snapshot_keys = {
        "schema_version",
        "append_only",
        "phase_codes",
        "phase_codes_orthogonal",
        "entry_count",
        "head_hash",
        "entries",
    }
    if set(snapshot) != required_snapshot_keys:
        return False
    expected_codes = {key: list(value) for key, value in PHASE_CODES.items()}
    if (
        snapshot.get("schema_version") != 1
        or snapshot.get("append_only") is not True
        or snapshot.get("phase_codes") != expected_codes
        or snapshot.get("phase_codes_orthogonal") is not True
        or not verify_phase_codes()
    ):
        return False
    entries = snapshot.get("entries")
    count = snapshot.get("entry_count")
    if (
        not isinstance(entries, list)
        or isinstance(count, bool)
        or not isinstance(count, int)
        or count != len(entries)
    ):
        return False

    required_entry_keys = {
        "schema_version",
        "sequence",
        "entry_id",
        "phase",
        "kind",
        "author_worker_id",
        "phase_code",
        "body",
        "references",
        "parent_ids",
        "artifact_refs",
        "previous_hash",
        "entry_hash",
    }
    previous_hash = GENESIS_HASH
    phases_by_entry_id: dict[str, str] = {}
    for expected_sequence, raw in enumerate(entries, start=1):
        if not isinstance(raw, Mapping) or set(raw) != required_entry_keys:
            return False
        try:
            if len(canonical_json_bytes(dict(raw))) > max_entry_bytes:
                return False
        except (TypeError, ValueError):
            return False
        phase = raw.get("phase")
        sequence = raw.get("sequence")
        entry_id = raw.get("entry_id")
        entry_hash = raw.get("entry_hash")
        if (
            raw.get("schema_version") != 1
            or isinstance(sequence, bool)
            or sequence != expected_sequence
            or phase not in PHASE_INDEX
            or raw.get("phase_code") != list(PHASE_CODES[phase])
            or not isinstance(raw.get("kind"), str)
            or not raw.get("kind")
            or not isinstance(raw.get("author_worker_id"), str)
            or not raw.get("author_worker_id")
            or not isinstance(raw.get("body"), Mapping)
            or not isinstance(entry_id, str)
            or not isinstance(entry_hash, str)
            or len(entry_hash) != 64
            or any(character not in "0123456789ABCDEF" for character in entry_hash)
            or raw.get("previous_hash") != previous_hash
        ):
            return False
        normalized_lists: dict[str, list[str]] = {}
        for name in ("references", "parent_ids", "artifact_refs"):
            values = raw.get(name)
            if (
                not isinstance(values, list)
                or any(not isinstance(item, str) or not item for item in values)
                or len(set(values)) != len(values)
            ):
                return False
            normalized_lists[name] = values
        for parent_id in normalized_lists["parent_ids"]:
            parent_phase = phases_by_entry_id.get(parent_id)
            if parent_phase is None or PHASE_INDEX[parent_phase] >= PHASE_INDEX[phase]:
                return False
        payload = {
            "schema_version": 1,
            "sequence": sequence,
            "phase": phase,
            "kind": raw["kind"],
            "author_worker_id": raw["author_worker_id"],
            "phase_code": raw["phase_code"],
            "body": raw["body"],
            "references": normalized_lists["references"],
            "parent_ids": normalized_lists["parent_ids"],
            "artifact_refs": normalized_lists["artifact_refs"],
            "previous_hash": previous_hash,
        }
        try:
            expected_hash = sha256_bytes(canonical_json_bytes(payload))
        except (TypeError, ValueError):
            return False
        expected_id = f"bb-{sequence:04d}-{expected_hash[:16].lower()}"
        if entry_hash != expected_hash or entry_id != expected_id:
            return False
        if entry_id in phases_by_entry_id:
            return False
        phases_by_entry_id[entry_id] = phase
        previous_hash = entry_hash
    return snapshot.get("head_hash") == previous_hash
