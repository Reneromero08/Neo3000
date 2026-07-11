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
from dataclasses import asdict, dataclass
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
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


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
    body: dict[str, Any]
    references: tuple[str, ...]
    parent_ids: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    previous_hash: str
    entry_hash: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["phase_code"] = list(self.phase_code)
        value["references"] = list(self.references)
        value["parent_ids"] = list(self.parent_ids)
        value["artifact_refs"] = list(self.artifact_refs)
        return value


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
        if not kind or not author_worker_id:
            raise BlackboardError("kind and author_worker_id are required")
        if len(references) > self.max_references:
            raise BlackboardError("reference ceiling exceeded")
        if len(parent_ids) > self.max_parents:
            raise BlackboardError("parent ceiling exceeded")
        if len(artifact_refs) > self.max_artifacts:
            raise BlackboardError("artifact ceiling exceeded")
        if len(set(parent_ids)) != len(parent_ids):
            raise BlackboardError("duplicate parent IDs")
        self._validate_parents(phase, parent_ids)

        normalized_body = json.loads(canonical_json_bytes(dict(body)).decode("utf-8"))
        body_bytes = canonical_json_bytes(normalized_body)
        if len(body_bytes) > self.max_entry_bytes:
            raise BlackboardError(
                f"blackboard entry body exceeds {self.max_entry_bytes} bytes"
            )

        sequence = len(self._entries) + 1
        identity_payload = {
            "schema_version": 1,
            "sequence": sequence,
            "phase": phase,
            "kind": kind,
            "author_worker_id": author_worker_id,
            "phase_code": list(PHASE_CODES[phase]),
            "body": normalized_body,
            "references": list(references),
            "parent_ids": list(parent_ids),
            "artifact_refs": list(artifact_refs),
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
            body=normalized_body,
            references=tuple(references),
            parent_ids=tuple(parent_ids),
            artifact_refs=tuple(artifact_refs),
            previous_hash=self._head_hash,
            entry_hash=entry_hash,
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
        if limit <= 0:
            return ()
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
                continue
            selected.append(entry)
            if len(selected) >= limit:
                break
        return tuple(selected)

    def verify_chain(self) -> bool:
        previous_hash = GENESIS_HASH
        for expected_sequence, entry in enumerate(self._entries, start=1):
            if entry.sequence != expected_sequence:
                return False
            payload = {
                "schema_version": entry.schema_version,
                "sequence": entry.sequence,
                "phase": entry.phase,
                "kind": entry.kind,
                "author_worker_id": entry.author_worker_id,
                "phase_code": list(entry.phase_code),
                "body": entry.body,
                "references": list(entry.references),
                "parent_ids": list(entry.parent_ids),
                "artifact_refs": list(entry.artifact_refs),
                "previous_hash": previous_hash,
            }
            if entry.previous_hash != previous_hash:
                return False
            if sha256_bytes(canonical_json_bytes(payload)) != entry.entry_hash:
                return False
            previous_hash = entry.entry_hash
        return previous_hash == self._head_hash

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
