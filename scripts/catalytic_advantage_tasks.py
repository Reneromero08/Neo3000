#!/usr/bin/env python3
"""Frozen executable task suite for CatalyticSwarm-1.

The suite is a deterministic multiple-candidate program-selection benchmark.
Each task exposes a small integer DSL, public input/output examples, and sixteen
candidate programs. Hidden examples and answer keys are generated only inside
this protected evaluator module; prompt rendering exposes only public material.

This module performs no network, subprocess, Git, model, or filesystem writes.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import random
from dataclasses import dataclass
from typing import Any, Mapping

SCHEMA_VERSION = 1
SUITE_ID = "catalytic-swarm-1-dsl-selection-v1"
GENERATION_SEED = 13001
EXPECTED_SUITE_SHA256 = "511315F206889D0194ECB7076380A8D6F43170F7D9564BA0DA008ACE538F049C"
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
            "semantics": {
                "input_domain": "signed integers",
                "instruction_order": "left-to-right",
                "ADD": "y = y + arg",
                "MUL": "y = y * arg",
                "NEG": "y = -y",
                "ABS": "y = abs(y)",
                "MOD": "y = y % arg using Python non-negative modulo for positive arg",
                "program_length": PROGRAM_LENGTH,
            },
            "tasks": tasks,
        }


def _require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AdvantageTaskError(f"{label} must be an integer")
    return value


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


def _instruction_pool() -> tuple[Instruction, ...]:
    items: list[Instruction] = []
    for arg in (-9, -7, -5, -3, -2, 2, 3, 5, 7, 9):
        items.append(Instruction("ADD", arg))
    for arg in (-3, -2, 2, 3):
        items.append(Instruction("MUL", arg))
    items.extend((Instruction("NEG"), Instruction("ABS")))
    for arg in (5, 7, 9, 11):
        items.append(Instruction("MOD", arg))
    return tuple(items)


def _program_display(program: tuple[Instruction, ...]) -> str:
    parts: list[str] = []
    for instruction in program:
        if instruction.op in OPS_WITHOUT_ARG:
            parts.append(instruction.op)
        elif instruction.op in {"ADD", "MUL"}:
            assert instruction.arg is not None
            parts.append(f"{instruction.op}:{instruction.arg:+d}")
        else:
            assert instruction.arg is not None
            parts.append(f"{instruction.op}:{instruction.arg}")
    return "|".join(parts)


def _execute_tuple(program: tuple[Instruction, ...], x: int) -> int:
    return execute_program(CandidateProgram("TMP", program, _program_display(program)), x)


def _generate_raw_suite() -> dict[str, Any]:
    rng = random.Random(GENERATION_SEED)
    public_pool = list(range(-9, 10))
    hidden_pool = list(range(-20, 21))
    programs = tuple(itertools.product(_instruction_pool(), repeat=PROGRAM_LENGTH))
    used_targets: set[tuple[Instruction, ...]] = set()
    tasks: list[dict[str, Any]] = []

    for task_index in range(TASK_COUNT):
        while True:
            public_inputs = sorted(rng.sample(public_pool, PUBLIC_EXAMPLE_COUNT))
            if (
                0 in public_inputs
                and any(value < 0 for value in public_inputs)
                and any(value > 0 for value in public_inputs)
            ):
                break
        hidden_inputs = sorted(
            rng.sample(
                [value for value in hidden_pool if value not in public_inputs],
                HIDDEN_EXAMPLE_COUNT,
            )
        )

        while True:
            target = rng.choice(programs)
            if target in used_targets:
                continue
            target_values = [_execute_tuple(target, value) for value in public_inputs]
            if len(set(target_values)) >= 4 and max(target_values) - min(target_values) >= 5:
                used_targets.add(target)
                break

        target_vector = tuple(_execute_tuple(target, value) for value in public_inputs)
        scored: list[tuple[int, int, int, str, tuple[Instruction, ...], tuple[int, ...]]] = []
        for program in programs:
            if program == target:
                continue
            vector = tuple(_execute_tuple(program, value) for value in public_inputs)
            matches = sum(actual == expected for actual, expected in zip(vector, target_vector))
            distance = sum(abs(actual - expected) for actual, expected in zip(vector, target_vector))
            instruction_matches = sum(left == right for left, right in zip(program, target))
            scored.append((-matches, distance, -instruction_matches, _program_display(program), program, vector))
        scored.sort(key=lambda item: item[:4])

        selected: list[tuple[Instruction, ...]] = []
        seen_vectors = {target_vector}
        for _matches, _distance, _ops, _display, program, vector in scored:
            if vector in seen_vectors:
                continue
            selected.append(program)
            seen_vectors.add(vector)
            if len(selected) == CANDIDATE_COUNT - 1:
                break
        if len(selected) != CANDIDATE_COUNT - 1:
            raise AdvantageTaskError("could not generate distinct distractors")

        candidates = [target, *selected]
        rng.shuffle(candidates)
        answer_index = candidates.index(target)
        candidate_items = []
        for candidate_index, program in enumerate(candidates):
            candidate_items.append(
                {
                    "candidate_id": f"C{candidate_index:02d}",
                    "instructions": [instruction.to_dict() for instruction in program],
                    "display": _program_display(program),
                }
            )
        tasks.append(
            {
                "task_id": f"{TASK_ID_PREFIX}{task_index + 1:02d}",
                "public_examples": [
                    {"x": value, "y": _execute_tuple(target, value)}
                    for value in public_inputs
                ],
                "hidden_examples": [
                    {"x": value, "y": _execute_tuple(target, value)}
                    for value in hidden_inputs
                ],
                "candidates": candidate_items,
                "answer_candidate_id": f"C{answer_index:02d}",
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "suite_id": SUITE_ID,
        "generation_seed": GENERATION_SEED,
        "semantics": {
            "input_domain": "signed integers",
            "instruction_order": "left-to-right",
            "ADD": "y = y + arg",
            "MUL": "y = y * arg",
            "NEG": "y = -y",
            "ABS": "y = abs(y)",
            "MOD": "y = y % arg using Python non-negative modulo for positive arg",
            "program_length": PROGRAM_LENGTH,
        },
        "tasks": tasks,
    }


def _parse_instruction(value: Mapping[str, Any]) -> Instruction:
    op = value.get("op")
    if not isinstance(op, str) or op not in ALLOWED_OPS:
        raise AdvantageTaskError(f"unsupported op {op!r}")
    expected = {"op", "arg"} if op in OPS_WITH_ARG else {"op"}
    if set(value) != expected:
        raise AdvantageTaskError("instruction key set mismatch")
    if op in OPS_WITHOUT_ARG:
        return Instruction(op)
    arg = _require_int(value["arg"], f"{op}.arg")
    if op == "MOD" and arg <= 0:
        raise AdvantageTaskError("MOD arg must be positive")
    if op in {"ADD", "MUL"} and arg == 0:
        raise AdvantageTaskError(f"{op} arg may not be zero")
    if abs(arg) > 16:
        raise AdvantageTaskError("instruction arg exceeds bounded DSL")
    return Instruction(op, arg)


def _parse_raw_task(value: Mapping[str, Any], index: int) -> AdvantageTask:
    expected_keys = {"task_id", "public_examples", "hidden_examples", "candidates", "answer_candidate_id"}
    if set(value) != expected_keys:
        raise AdvantageTaskError("task key set mismatch")
    if value["task_id"] != f"{TASK_ID_PREFIX}{index + 1:02d}":
        raise AdvantageTaskError("task identity mismatch")
    public_examples = tuple(
        Example(_require_int(item["x"], "public.x"), _require_int(item["y"], "public.y"))
        for item in value["public_examples"]
    )
    hidden_examples = tuple(
        Example(_require_int(item["x"], "hidden.x"), _require_int(item["y"], "hidden.y"))
        for item in value["hidden_examples"]
    )
    if len(public_examples) != PUBLIC_EXAMPLE_COUNT:
        raise AdvantageTaskError("public example count mismatch")
    if len(hidden_examples) != HIDDEN_EXAMPLE_COUNT:
        raise AdvantageTaskError("hidden example count mismatch")
    if set(item.x for item in public_examples) & set(item.x for item in hidden_examples):
        raise AdvantageTaskError("public and hidden inputs overlap")

    candidates = tuple(
        CandidateProgram(
            candidate_id=item["candidate_id"],
            instructions=tuple(_parse_instruction(instruction) for instruction in item["instructions"]),
            display=item["display"],
        )
        for item in value["candidates"]
    )
    if len(candidates) != CANDIDATE_COUNT:
        raise AdvantageTaskError("candidate count mismatch")
    expected_ids = tuple(f"C{candidate_index:02d}" for candidate_index in range(CANDIDATE_COUNT))
    if tuple(item.candidate_id for item in candidates) != expected_ids:
        raise AdvantageTaskError("candidate IDs are not canonical")
    if any(len(item.instructions) != PROGRAM_LENGTH for item in candidates):
        raise AdvantageTaskError("program length mismatch")
    if len({item.instructions for item in candidates}) != CANDIDATE_COUNT:
        raise AdvantageTaskError("duplicate candidate programs")
    answer_candidate_id = value["answer_candidate_id"]
    if answer_candidate_id not in expected_ids:
        raise AdvantageTaskError("answer candidate is invalid")
    task = AdvantageTask(
        task_id=value["task_id"],
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
        raise AdvantageTaskError("task lacks one unique public solution")
    if not candidate_is_exact(task, answer_candidate_id, hidden=True):
        raise AdvantageTaskError("answer fails hidden examples")
    return task


def build_frozen_task_suite() -> AdvantageTaskSuite:
    raw = _generate_raw_suite()
    digest = sha256_bytes(canonical_json_bytes(raw))
    if digest != EXPECTED_SUITE_SHA256:
        raise AdvantageTaskError(
            f"task suite hash drift: expected {EXPECTED_SUITE_SHA256}, actual {digest}"
        )
    tasks = tuple(_parse_raw_task(item, index) for index, item in enumerate(raw["tasks"]))
    return AdvantageTaskSuite(
        schema_version=SCHEMA_VERSION,
        suite_id=SUITE_ID,
        generation_seed=GENERATION_SEED,
        tasks=tasks,
        suite_sha256=digest,
    )


def render_public_task(task: AdvantageTask) -> str:
    """Render a canonical prompt root with no hidden examples or answer key."""
    encoded = json.dumps(
        task.public_projection(),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if "hidden_examples" in encoded or "answer_candidate_id" in encoded:
        raise AdvantageTaskError("public task render leaked protected fields")
    return encoded


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
    "EXPECTED_SUITE_SHA256",
    "GENERATION_SEED",
    "HIDDEN_EXAMPLE_COUNT",
    "PUBLIC_EXAMPLE_COUNT",
    "SUITE_ID",
    "TASK_COUNT",
    "build_frozen_task_suite",
    "candidate_is_exact",
    "execute_program",
    "render_public_task",
    "score_candidate",
    "validate_public_projection",
]
