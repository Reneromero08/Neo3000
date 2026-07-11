#!/usr/bin/env python3
"""Frozen executable task suite for CatalyticSwarm-1.

The suite is a deterministic multiple-candidate program-selection benchmark.
Each task exposes a small integer DSL, public input/output examples, and sixteen
candidate programs. Hidden examples and the answer key remain in the protected
task file for the external evaluator only; prompt rendering never includes them.

This module performs no network, subprocess, Git, or model operations.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = 1
SUITE_ID = "catalytic-swarm-1-dsl-selection-v1"
TASK_COUNT = 8
CANDIDATE_COUNT = 16
PROGRAM_LENGTH = 3
PUBLIC_EXAMPLE_COUNT = 7
HIDDEN_EXAMPLE_COUNT = 12
ALLOWED_OPS = {"ADD", "MUL", "NEG", "ABS", "MOD"}
OPS_WITH_ARG = {"ADD", "MUL", "MOD"}
OPS_WITHOUT_ARG = {"NEG", "ABS"}
TASK_ID_PREFIX = "cs1-task-"


class AdvantageTaskError(RuntimeError):
    """The protected task suite or a candidate result is malformed."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


@dataclass(frozen=True)
class Instruction:
    op: str
    arg: int | None = None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {"op": self.op}
        if self.arg is not None:
            value["arg"] = self.arg
        return value


@dataclass(frozen=True)
class CandidateProgram:
    candidate_id: str
    instructions: tuple[Instruction, ...]
    display: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "instructions": [item.to_dict() for item in self.instructions],
            "display": self.display,
        }


@dataclass(frozen=True)
class Example:
    x: int
    y: int

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y}


@dataclass(frozen=True)
class AdvantageTask:
    task_id: str
    public_examples: tuple[Example, ...]
    hidden_examples: tuple[Example, ...]
    candidates: tuple[CandidateProgram, ...]
    answer_candidate_id: str

    def candidate(self, candidate_id: str) -> CandidateProgram:
        for candidate in self.candidates:
            if candidate.candidate_id == candidate_id:
                return candidate
        raise AdvantageTaskError(
            f"{self.task_id} has no candidate {candidate_id!r}"
        )

    def public_projection(self) -> dict[str, Any]:
        """Return the only task material permitted in model prompts."""
        return {
            "task_id": self.task_id,
            "semantics": {
                "instruction_order": "left-to-right",
                "ADD": "y = y + arg",
                "MUL": "y = y * arg",
                "NEG": "y = -y",
                "ABS": "y = abs(y)",
                "MOD": "y = y % arg using non-negative modulo for positive arg",
            },
            "public_examples": [item.to_dict() for item in self.public_examples],
            "candidates": [item.to_dict() for item in self.candidates],
            "response_schema": {"candidate_id": "C00"},
        }


@dataclass(frozen=True)
class AdvantageTaskSuite:
    schema_version: int
    suite_id: str
    generation_seed: int
    semantics: Mapping[str, Any]
    tasks: tuple[AdvantageTask, ...]
    suite_sha256: str

    def to_dict(self, *, include_answers: bool = True) -> dict[str, Any]:
        tasks: list[dict[str, Any]] = []
        for task in self.tasks:
            item = {
                "task_id": task.task_id,
                "public_examples": [example.to_dict() for example in task.public_examples],
                "hidden_examples": [example.to_dict() for example in task.hidden_examples],
                "candidates": [candidate.to_dict() for candidate in task.candidates],
            }
            if include_answers:
                item["answer_candidate_id"] = task.answer_candidate_id
            tasks.append(item)
        return {
            "schema_version": self.schema_version,
            "suite_id": self.suite_id,
            "generation_seed": self.generation_seed,
            "semantics": dict(self.semantics),
            "tasks": tasks,
        }


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise AdvantageTaskError(
            f"{label} key set mismatch; missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AdvantageTaskError(f"{label} must be an integer")
    return value


def _parse_instruction(value: Any, label: str) -> Instruction:
    if not isinstance(value, Mapping):
        raise AdvantageTaskError(f"{label} must be an object")
    op = value.get("op")
    if not isinstance(op, str) or op not in ALLOWED_OPS:
        raise AdvantageTaskError(f"{label} has unsupported op {op!r}")
    expected = {"op", "arg"} if op in OPS_WITH_ARG else {"op"}
    _require_exact_keys(value, expected, label)
    if op in OPS_WITHOUT_ARG:
        return Instruction(op=op)
    arg = _require_int(value["arg"], f"{label}.arg")
    if op == "MOD" and arg <= 0:
        raise AdvantageTaskError(f"{label}.arg must be positive for MOD")
    if op in {"ADD", "MUL"} and arg == 0:
        raise AdvantageTaskError(f"{label}.arg may not be zero")
    if abs(arg) > 16:
        raise AdvantageTaskError(f"{label}.arg exceeds the bounded DSL")
    return Instruction(op=op, arg=arg)


def _parse_candidate(value: Any, label: str) -> CandidateProgram:
    if not isinstance(value, Mapping):
        raise AdvantageTaskError(f"{label} must be an object")
    _require_exact_keys(value, {"candidate_id", "instructions", "display"}, label)
    candidate_id = value["candidate_id"]
    display = value["display"]
    instructions = value["instructions"]
    if not isinstance(candidate_id, str) or not candidate_id:
        raise AdvantageTaskError(f"{label}.candidate_id is invalid")
    if not isinstance(display, str) or not display:
        raise AdvantageTaskError(f"{label}.display is invalid")
    if not isinstance(instructions, list) or len(instructions) != PROGRAM_LENGTH:
        raise AdvantageTaskError(
            f"{label}.instructions must contain exactly {PROGRAM_LENGTH} items"
        )
    return CandidateProgram(
        candidate_id=candidate_id,
        instructions=tuple(
            _parse_instruction(item, f"{label}.instructions[{index}]")
            for index, item in enumerate(instructions)
        ),
        display=display,
    )


def _parse_examples(value: Any, *, expected_count: int, label: str) -> tuple[Example, ...]:
    if not isinstance(value, list) or len(value) != expected_count:
        raise AdvantageTaskError(f"{label} must contain exactly {expected_count} examples")
    parsed: list[Example] = []
    seen_inputs: set[int] = set()
    for index, item in enumerate(value):
        item_label = f"{label}[{index}]"
        if not isinstance(item, Mapping):
            raise AdvantageTaskError(f"{item_label} must be an object")
        _require_exact_keys(item, {"x", "y"}, item_label)
        x = _require_int(item["x"], f"{item_label}.x")
        y = _require_int(item["y"], f"{item_label}.y")
        if x in seen_inputs:
            raise AdvantageTaskError(f"{label} repeats input {x}")
        seen_inputs.add(x)
        parsed.append(Example(x=x, y=y))
    return tuple(parsed)


def execute_program(program: CandidateProgram, x: int) -> int:
    """Execute the restricted integer DSL without Python eval."""
    y = _require_int(x, "program input")
    for instruction in program.instructions:
        if instruction.op == "ADD":
            assert instruction.arg is not None
            y += instruction.arg
        elif instruction.op == "MUL":
            assert instruction.arg is not None
            y *= instruction.arg
        elif instruction.op == "NEG":
            y = -y
        elif instruction.op == "ABS":
            y = abs(y)
        elif instruction.op == "MOD":
            assert instruction.arg is not None and instruction.arg > 0
            y %= instruction.arg
        else:
            raise AdvantageTaskError(f"unsupported instruction {instruction.op!r}")
        if abs(y) > 1_000_000:
            raise AdvantageTaskError("program output escaped bounded range")
    return y


def score_candidate(task: AdvantageTask, candidate_id: str, *, hidden: bool) -> tuple[int, int]:
    examples = task.hidden_examples if hidden else task.public_examples
    program = task.candidate(candidate_id)
    passed = sum(execute_program(program, example.x) == example.y for example in examples)
    return passed, len(examples)


def candidate_is_exact(task: AdvantageTask, candidate_id: str, *, hidden: bool) -> bool:
    passed, total = score_candidate(task, candidate_id, hidden=hidden)
    return passed == total


def render_public_task(task: AdvantageTask) -> str:
    """Render a canonical prompt root with no hidden examples or answer key."""
    projection = task.public_projection()
    encoded = json.dumps(
        projection,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if "hidden_examples" in encoded or "answer_candidate_id" in encoded:
        raise AdvantageTaskError("public task render leaked protected fields")
    return encoded


def _parse_task(value: Any, index: int) -> AdvantageTask:
    label = f"tasks[{index}]"
    if not isinstance(value, Mapping):
        raise AdvantageTaskError(f"{label} must be an object")
    _require_exact_keys(
        value,
        {"task_id", "public_examples", "hidden_examples", "candidates", "answer_candidate_id"},
        label,
    )
    task_id = value["task_id"]
    if task_id != f"{TASK_ID_PREFIX}{index + 1:02d}":
        raise AdvantageTaskError(f"{label}.task_id is not canonical")
    public_examples = _parse_examples(
        value["public_examples"],
        expected_count=PUBLIC_EXAMPLE_COUNT,
        label=f"{label}.public_examples",
    )
    hidden_examples = _parse_examples(
        value["hidden_examples"],
        expected_count=HIDDEN_EXAMPLE_COUNT,
        label=f"{label}.hidden_examples",
    )
    if set(item.x for item in public_examples) & set(item.x for item in hidden_examples):
        raise AdvantageTaskError(f"{label} public and hidden inputs overlap")
    candidates_raw = value["candidates"]
    if not isinstance(candidates_raw, list) or len(candidates_raw) != CANDIDATE_COUNT:
        raise AdvantageTaskError(
            f"{label}.candidates must contain exactly {CANDIDATE_COUNT} items"
        )
    candidates = tuple(
        _parse_candidate(item, f"{label}.candidates[{candidate_index}]")
        for candidate_index, item in enumerate(candidates_raw)
    )
    expected_ids = tuple(f"C{candidate_index:02d}" for candidate_index in range(CANDIDATE_COUNT))
    actual_ids = tuple(candidate.candidate_id for candidate in candidates)
    if actual_ids != expected_ids:
        raise AdvantageTaskError(f"{label} candidate IDs are not canonical")
    if len({candidate.instructions for candidate in candidates}) != CANDIDATE_COUNT:
        raise AdvantageTaskError(f"{label} contains duplicate programs")
    answer_candidate_id = value["answer_candidate_id"]
    if answer_candidate_id not in expected_ids:
        raise AdvantageTaskError(f"{label}.answer_candidate_id is invalid")
    task = AdvantageTask(
        task_id=task_id,
        public_examples=public_examples,
        hidden_examples=hidden_examples,
        candidates=candidates,
        answer_candidate_id=answer_candidate_id,
    )
    public_exact = [
        candidate.candidate_id
        for candidate in candidates
        if candidate_is_exact(task, candidate.candidate_id, hidden=False)
    ]
    if public_exact != [answer_candidate_id]:
        raise AdvantageTaskError(f"{label} does not have one unique public-example solution")
    if not candidate_is_exact(task, answer_candidate_id, hidden=True):
        raise AdvantageTaskError(f"{label} answer fails hidden examples")
    return task


def load_task_suite(path: Path) -> AdvantageTaskSuite:
    if not path.is_file():
        raise AdvantageTaskError(f"missing task suite: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdvantageTaskError(f"cannot load task suite: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise AdvantageTaskError("task suite must be an object")
    _require_exact_keys(raw, {"schema_version", "suite_id", "generation_seed", "semantics", "tasks"}, "task suite")
    if raw["schema_version"] != SCHEMA_VERSION:
        raise AdvantageTaskError("unsupported task-suite schema version")
    if raw["suite_id"] != SUITE_ID:
        raise AdvantageTaskError("unexpected task-suite identity")
    generation_seed = _require_int(raw["generation_seed"], "generation_seed")
    if not isinstance(raw["semantics"], Mapping):
        raise AdvantageTaskError("semantics must be an object")
    tasks_raw = raw["tasks"]
    if not isinstance(tasks_raw, list) or len(tasks_raw) != TASK_COUNT:
        raise AdvantageTaskError(f"task suite must contain exactly {TASK_COUNT} tasks")
    tasks = tuple(_parse_task(item, index) for index, item in enumerate(tasks_raw))
    suite_hash = sha256_bytes(canonical_json_bytes(raw))
    return AdvantageTaskSuite(
        schema_version=SCHEMA_VERSION,
        suite_id=SUITE_ID,
        generation_seed=generation_seed,
        semantics=dict(raw["semantics"]),
        tasks=tasks,
        suite_sha256=suite_hash,
    )


def validate_public_projection(task: AdvantageTask, rendered: str) -> None:
    """Hard gate that protected evaluation material never enters a model prompt."""
    try:
        payload = json.loads(rendered)
    except json.JSONDecodeError as exc:
        raise AdvantageTaskError("rendered public task is not JSON") from exc
    if payload != task.public_projection():
        raise AdvantageTaskError("rendered public task differs from projection")
    if "hidden_examples" in payload or "answer_candidate_id" in payload:
        raise AdvantageTaskError("protected evaluation fields leaked")


__all__ = [
    "AdvantageTask",
    "AdvantageTaskError",
    "AdvantageTaskSuite",
    "CANDIDATE_COUNT",
    "HIDDEN_EXAMPLE_COUNT",
    "PUBLIC_EXAMPLE_COUNT",
    "SUITE_ID",
    "TASK_COUNT",
    "candidate_is_exact",
    "execute_program",
    "load_task_suite",
    "render_public_task",
    "score_candidate",
    "validate_public_projection",
]
