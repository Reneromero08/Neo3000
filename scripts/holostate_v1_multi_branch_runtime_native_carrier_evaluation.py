#!/usr/bin/env python3
"""Prepare, validate, or run the held-out multi-branch runtime-native carrier panel."""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import inspect
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import catalytic_inference_bench_0_runtime as runtime_support
import catalytic_kernel_0 as kernel
import holostate_v1_inherited_task_a_carrier_evaluation as predecessor
import holostate_v1_inherited_task_a_carrier_evaluation_adjudication as predecessor_adjudication
import holostate_v1_warm_trajectory_related_task_evaluation as warm_source


class MultiBranchCarrierEvaluationError(ValueError):
    """The frozen design, exact-token law, evidence custody, or decision law changed."""


FAMILY_ID = "holostate-v1-multi-branch-runtime-native-carrier-family-v1"
DESIGN_ID = "holostate-v1-multi-branch-runtime-native-carrier-evaluation-v1"
STARTING_PROTECTED_MAIN = "71a1dbf18c0f7c5596b792f0134b7f29bc6c9269"
PUBLIC_CORPUS_PATH = Path("lab/holostate_v1_multi_branch_runtime_native_carrier_family_v1_public_tasks.json")
PUBLIC_CORPUS_SHA256 = "81CD66E50A2DA9E0A9D60FC39367CACC0CA81B6EB97A39951E0EB549F6E82920"
PUBLIC_CORPUS_SIZE = 16531
PROTECTED_EVALUATOR_PATH = Path(
    "state/catalytic_kernel_0_private/holostate_v1_multi_branch_runtime_native_carrier_family_v1_evaluator.json"
)
PROTECTED_EVALUATOR_SHA256 = "8114EB04EECF9EDD0865DE3A1C3801770801609BC41D6E89755D710EDD52C476"
PROTECTED_EVALUATOR_SIZE = 1727
CORPUS_BINDING_PATH = Path("lab/holostate_v1_multi_branch_runtime_native_carrier_family_v1_corpus_binding_1.json")
PREREGISTRATION_PATH = Path("lab/holostate_v1_multi_branch_runtime_native_carrier_evaluation_v1.json")
STATE_ROOT = Path("state/catalytic_kernel_0/holostate_v1_multi_branch_runtime_native_carrier_evaluation_v1")
ARCHIVE_ROOT = Path("state/catalytic_kernel_0/holostate_v1_multi_branch_runtime_native_carrier_evidence_archive/v1")
AUTHORITY_RECEIPT_PATH = Path(
    "state/catalytic_kernel_0_authority."
    "holostate-v1-multi-branch-runtime-native-carrier-evaluation-v1.authority.consumed.json"
)

SOURCE_SELECTION_PATH = Path("lab/holostate_v1_executable_reuse_boundary_response_selection_1.json")
SOURCE_SELECTION_SHA256 = "F04325799786F46D8E3180DB9773DED182D38ED1E9D0C92E2CBC2B1D72FD28C1"
SOURCE_ADJUDICATION_PATH = Path("lab/holostate_v1_inherited_task_a_carrier_evaluation_v1_adjudication_1.json")
SOURCE_ADJUDICATION_SHA256 = "CC7658ECA40C4A586FE6AF56B9B8751080BEAA0A53BD1B8C30121F4B9CEB3882"
SOURCE_RECORD_ID = "neo-exp-0049"
SOURCE_RECORD_LINE = 62
SOURCE_RECORD_SHA256 = "B133161184777A50BB90430515CFD74EE4EE9FFC394B720ECA69DDBE2ECE88A6"
SOURCE_EXECUTION_COMMIT = "26aa75a27ee17d625c0965a1ccb96373d925f735"
SOURCE_ARCHIVE_SHA256 = "9BC81ECDC0363B2032E15C94DB28DB7D1E434DCCA1EE86FCB140279DDB20D9E6"

MODEL_SHA256 = warm_source.MODEL_SHA256
BINARY_SHA256 = warm_source.BINARY_SHA256
RUNTIME_VERSION = warm_source.RUNTIME_VERSION
CHAT_TEMPLATE_SHA256 = predecessor_adjudication.SOURCE_BINDINGS["chat_template_sha256"]
EXPECTED_EVIDENCE_ROOT_COMMITMENT = warm_source.EXPECTED_EVIDENCE_ROOT_COMMITMENT
CHAT_TEMPLATE_KWARGS = {"enable_thinking": False}
ROOT_IDS = (
    "mb-runtime-datacenter-01",
    "mb-runtime-coldchain-02",
    "mb-runtime-orbit-03",
    "mb-runtime-water-04",
)
BRANCH_IDS = tuple(f"{root_id}-branch-{branch}" for root_id in ROOT_IDS for branch in (1, 2))
FIRST_BRANCH = {
    ROOT_IDS[0]: 1,
    ROOT_IDS[1]: 2,
    ROOT_IDS[2]: 1,
    ROOT_IDS[3]: 2,
}
ALLOWED_ANSWERS = ("A", "B", "C", "D")
TASK_A_MAX_TOKENS = 384
BRANCH_MAX_TOKENS = 96
MAXIMUM_GENERATIONS = 20
MAXIMUM_INFERENCE_REQUESTS = 24
SNAPSHOT_SAVE_COUNT = 4
SNAPSHOT_RESTORE_COUNT = 8
SNAPSHOT_CONTROL_COUNT = 12
MAX_CAPTURE_BYTES = warm_source.MAX_CAPTURE_BYTES
MAX_STATE_BYTES = warm_source.MAX_STATE_BYTES
N_SWA = 0
N_BATCH = 512
N_UBATCH = 128
CONTEXT_CHECKPOINTS = 8
CHECKPOINT_MIN_STEP = 512
MEMORY_REMOVAL_CAPABILITY = "full-only"
SOURCE_BOUNDARY_SELECTION = "RUNTIME_NATIVE_EXECUTABLE_CARRIER_BOUNDARY_SELECTED"
SOURCE_LAW_PATHS = (
    "tools/server/server-common.cpp",
    "tools/server/server-context.cpp",
    "tools/server/server-task.cpp",
    "common/common.cpp",
    "src/llama-context.cpp",
    "src/llama-kv-cache-dsv4.cpp",
    "src/llama-memory-hybrid.cpp",
    "src/models/qwen35moe.cpp",
    "src/llama-hparams.h",
)

REQUEST_ORDER = tuple(
    request_id
    for root_id in ROOT_IDS
    for request_id in (
        f"{root_id}-task-a",
        f"{root_id}-branch-{FIRST_BRANCH[root_id]}-catalytic",
        f"{root_id}-branch-{3 - FIRST_BRANCH[root_id]}-catalytic",
        f"{root_id}-branch-1-direct",
        f"{root_id}-branch-2-direct",
    )
)
READDRESS_ORDER = tuple(f"{root_id}-root-readdress" for root_id in ROOT_IDS)
INFERENCE_ORDER = tuple(
    operation_id
    for root_id in ROOT_IDS
    for operation_id in (
        f"{root_id}-task-a",
        f"{root_id}-branch-{FIRST_BRANCH[root_id]}-catalytic",
        f"{root_id}-branch-{3 - FIRST_BRANCH[root_id]}-catalytic",
        f"{root_id}-root-readdress",
        f"{root_id}-branch-1-direct",
        f"{root_id}-branch-2-direct",
    )
)
SNAPSHOT_CONTROL_ORDER = tuple(
    operation_id
    for root_id in ROOT_IDS
    for operation_id in (
        f"{root_id}-snapshot-save",
        f"{root_id}-snapshot-restore-1",
        f"{root_id}-snapshot-restore-2",
    )
)

canonical_json_bytes = warm_source.canonical_json_bytes
canonical_json_text = warm_source.canonical_json_text
sha256_bytes = warm_source.sha256_bytes
sha256_file = warm_source.sha256_file
json_sha256 = warm_source.json_sha256
normalized_capture_execution = warm_source.normalized_capture_execution
RunLock = warm_source.RunLock


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MultiBranchCarrierEvaluationError(message)


def _regular_bytes(path: Path, label: str, maximum: int = MAX_STATE_BYTES) -> bytes:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise MultiBranchCarrierEvaluationError(f"{label} is missing") from exc
    _require(path.is_file() and not path.is_symlink(), f"{label} is not a regular file")
    _require(metadata.st_size <= maximum, f"{label} exceeds its byte ceiling")
    return path.read_bytes()


def _exclusive_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _write_or_require_identical(path: Path, data: bytes) -> None:
    if path.exists():
        _require(_regular_bytes(path, str(path)) == data, f"{path} differs from exact reconstruction")
        return
    _exclusive_write(path, data)


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repository, check=True, capture_output=True, text=True, timeout=60
    ).stdout.strip()


def _assert_public_no_smuggle(value: Any) -> None:
    warm_source._assert_public_no_smuggle(value)


def _load_private_root(repository: Path) -> bytes:
    return predecessor._load_private_root(repository)


def load_public_corpus(repository: Path) -> dict[str, Any]:
    data = _regular_bytes(repository / PUBLIC_CORPUS_PATH, "public multi-branch corpus", 128 * 1024)
    _require(len(data) == PUBLIC_CORPUS_SIZE and sha256_bytes(data) == PUBLIC_CORPUS_SHA256, "public corpus identity changed")
    value = json.loads(data)
    _require(isinstance(value, dict), "public corpus is not an object")
    _assert_public_no_smuggle(value)
    roots = value.get("roots")
    _require(isinstance(roots, list) and len(roots) == 4, "public corpus must contain four roots")
    _require(tuple(item.get("root_id") for item in roots) == ROOT_IDS, "root order changed")
    branch_ids: list[str] = []
    for item in roots:
        _require(set(item) == {"root_id", "evidence", "task_a", "branches"}, "public root surface changed")
        _require(len(re.findall(r"\b[\w'-]+\b", str(item["evidence"]))) >= 200, "public root is under-specified")
        task_a = item["task_a"]
        _require(
            isinstance(task_a, Mapping)
            and set(task_a) == {"question", "choices", "response_contract"}
            and tuple(task_a["choices"]) == ALLOWED_ANSWERS,
            "Task-A surface changed",
        )
        branches = item["branches"]
        _require(isinstance(branches, list) and len(branches) == 2, "each root must contain two branches")
        _require(branches[0]["reasoning_type"] != branches[1]["reasoning_type"], "branches must be distinct transformations")
        for branch in branches:
            _require(
                set(branch) == {"branch_id", "reasoning_type", "question", "choices"}
                and tuple(branch["choices"]) == ALLOWED_ANSWERS,
                "branch surface changed",
            )
            branch_ids.append(str(branch["branch_id"]))
    _require(tuple(branch_ids) == BRANCH_IDS and len(set(branch_ids)) == 8, "branch identities changed")
    serialized = canonical_json_text(value).lower()
    for retired in warm_source.PAIR_IDS:
        _require(retired.lower() not in serialized, "retired four-pair panel entered new corpus")
    return value


def protected_evaluator_custody(repository: Path) -> dict[str, Any]:
    path = repository / PROTECTED_EVALUATOR_PATH
    metadata = path.lstat()
    _require(path.is_file() and not path.is_symlink(), "protected evaluator is missing or unsafe")
    _require(metadata.st_size == PROTECTED_EVALUATOR_SIZE, "protected evaluator size changed")
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", PROTECTED_EVALUATOR_PATH.as_posix()],
        cwd=repository,
        timeout=30,
    )
    _require(ignored.returncode == 0, "protected evaluator must remain ignored")
    _require(not _git(repository, "ls-files", "--", PROTECTED_EVALUATOR_PATH.as_posix()), "protected evaluator is tracked")
    return {
        "path": PROTECTED_EVALUATOR_PATH.as_posix(),
        "expected_sha256_from_tracked_binding": PROTECTED_EVALUATOR_SHA256,
        "expected_size_bytes_from_tracked_binding": PROTECTED_EVALUATOR_SIZE,
        "size_bytes_from_filesystem_metadata": int(metadata.st_size),
        "regular": True,
        "symlink": False,
        "ignored": True,
        "tracked": False,
        "bytes_opened": False,
        "bytes_hashed": False,
        "bytes_parsed": False,
    }


def _root_by_id(corpus: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(item["root_id"]): item for item in corpus["roots"]}


def _branch_by_number(root: Mapping[str, Any], number: int) -> Mapping[str, Any]:
    branch_id = f"{root['root_id']}-branch-{number}"
    matches = [item for item in root["branches"] if item["branch_id"] == branch_id]
    _require(len(matches) == 1, "branch lookup is not unique")
    return matches[0]


def _choice_text(task: Mapping[str, Any]) -> str:
    return "\n".join(f"{label}. {task['choices'][label]}" for label in ALLOWED_ANSWERS)


def task_a_messages(root: Mapping[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Use only the supplied evidence. Return exactly one compact JSON object with keys state then answer. "
                "State must contain exactly four short invariant strings. Answer must be A, B, C, or D. "
                "Do not emit rationale, tools, or hidden reasoning."
            ),
        },
        {
            "role": "user",
            "content": (
                f"EVIDENCE\n{root['evidence']}\n\nTASK A\n{root['task_a']['question']}\n"
                f"{_choice_text(root['task_a'])}\n\nReturn only the declared JSON object."
            ),
        },
    ]


def branch_user_content(root: Mapping[str, Any], number: int) -> str:
    branch = _branch_by_number(root, number)
    return (
        "TASK B\nUse the complete preserved Task-A state and the same evidence for this related transformation. "
        "Return only JSON of the form {\"answer\":\"A\"}.\n"
        f"{branch['question']}\n{_choice_text(branch)}"
    )


def verification_user_content(root_id: str) -> str:
    _require(root_id in ROOT_IDS, "unknown root for readdress verification")
    return (
        f"ROOT READDRESS CHECK {root_id}\n"
        "Return only {\"answer\":\"A\"}. This public zero-output suffix verifies addressability; no answer will be sampled."
    )


def derive_seed(root_id: str, role: str) -> int:
    _require(root_id in ROOT_IDS, "unknown seed root")
    _require(role in {"task-a", "branch-1", "branch-2"}, "unknown seed role")
    digest = hashlib.sha256(f"{DESIGN_ID}|{PUBLIC_CORPUS_SHA256}|{root_id}|{role}|seed-v1".encode()).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def task_a_grammar() -> str:
    return (
        'root ::= "{" ws "\\\"state\\\"" ws ":" ws "[" ws string ws "," ws string ws "," ws string ws "," ws string ws "]" ws "," ws "\\\"answer\\\"" ws ":" ws answer ws "}"\n'
        'answer ::= "\\\"A\\\"" | "\\\"B\\\"" | "\\\"C\\\"" | "\\\"D\\\""\n'
        'string ::= "\\\"" chars "\\\""\n'
        'chars ::= char*\n'
        'char ::= [^"\\\\\\x00-\\x1F] | "\\\\" (["\\\\/bfnrt] | "u" hex hex hex hex)\n'
        'hex ::= [0-9a-fA-F]\n'
        'ws ::= [ \\t\\n\\r]*'
    )


def branch_grammar() -> str:
    return (
        'root ::= "{" ws "\\\"answer\\\"" ws ":" ws answer ws "}"\n'
        'answer ::= "\\\"A\\\"" | "\\\"B\\\"" | "\\\"C\\\"" | "\\\"D\\\""\n'
        'ws ::= [ \\t\\n\\r]*'
    )


def parse_task_a_output(text: str) -> dict[str, Any]:
    value = json.loads(text)
    _require(isinstance(value, dict) and tuple(value) == ("state", "answer"), "Task-A output shape changed")
    state = value["state"]
    _require(isinstance(state, list) and len(state) == 4, "Task-A state must contain four items")
    _require(all(isinstance(item, str) and item.strip() == item and item for item in state), "Task-A state item is invalid")
    _require(value["answer"] in ALLOWED_ANSWERS, "Task-A answer is invalid")
    return {"state": list(state), "answer": value["answer"]}


def parse_branch_output(text: str) -> str:
    value = json.loads(text)
    _require(isinstance(value, dict) and tuple(value) == ("answer",) and value["answer"] in ALLOWED_ANSWERS, "branch output shape changed")
    return str(value["answer"])


class SidecarPromptCodec(predecessor.SidecarPromptCodec):
    def props(self) -> dict[str, Any]:
        value = _request_json("GET", f"http://127.0.0.1:{self.port}/props")
        _require(isinstance(value, dict), "sidecar props are malformed")
        return dict(value)


def _task_a_payload(prompt_tokens: Sequence[int], *, seed: int) -> dict[str, Any]:
    _require(bool(prompt_tokens) and all(isinstance(item, int) for item in prompt_tokens), "Task-A prompt tokens are invalid")
    return {
        "prompt": list(prompt_tokens),
        "n_predict": TASK_A_MAX_TOKENS,
        "temperature": 0,
        "seed": seed,
        "stream": True,
        "cache_prompt": False,
        "id_slot": kernel.PHYSICAL_SLOT,
        "return_tokens": True,
        "return_progress": True,
        "grammar": task_a_grammar(),
    }


def _branch_payload(prompt_tokens: Sequence[int], *, seed: int, cache_prompt: bool, n_predict: int = BRANCH_MAX_TOKENS) -> dict[str, Any]:
    _require(bool(prompt_tokens) and all(isinstance(item, int) for item in prompt_tokens), "branch prompt tokens are invalid")
    payload = {
        "prompt": list(prompt_tokens),
        "n_predict": n_predict,
        "temperature": 0,
        "seed": seed,
        "stream": True,
        "cache_prompt": cache_prompt,
        "id_slot": kernel.PHYSICAL_SLOT,
        "return_tokens": True,
        "return_progress": True,
    }
    if n_predict > 0:
        payload["grammar"] = branch_grammar()
    return payload


def _stream_raw_completion(
    *, port: int, payload: Mapping[str, Any], recorder: Callable[[bytes], None], timeout: float = 900
) -> Any:
    return predecessor._stream_raw_completion(port=port, payload=payload, recorder=recorder, timeout=timeout)


def fixed_request_templates(corpus: Mapping[str, Any]) -> dict[str, str]:
    templates: dict[str, str] = {}
    for root in corpus["roots"]:
        root_id = str(root["root_id"])
        templates[f"{root_id}-task-a"] = json_sha256({
            "messages": task_a_messages(root), "grammar": task_a_grammar(), "seed": derive_seed(root_id, "task-a"),
            "maximum_completion_tokens": TASK_A_MAX_TOKENS, "exact_prompt_token_array": True,
        })
        for number in (1, 2):
            branch_template = {
                "branch_content": branch_user_content(root, number), "grammar": branch_grammar(),
                "seed": derive_seed(root_id, f"branch-{number}"), "maximum_completion_tokens": BRANCH_MAX_TOKENS,
                "dynamic_prefix": "authenticated exact retained-root token array", "same_tokens_between_routes": True,
            }
            templates[f"{root_id}-branch-{number}"] = json_sha256(branch_template)
        templates[f"{root_id}-root-readdress"] = json_sha256({
            "content": verification_user_content(root_id), "n_predict": 0, "cache_prompt": True,
            "dynamic_prefix": "authenticated exact restored-root token array",
        })
    return templates


def derive_retained_root(
    capture: Mapping[str, Any], prompt_tokens: Sequence[int], codec: SidecarPromptCodec, props: Mapping[str, Any]
) -> dict[str, Any]:
    execution = normalized_capture_execution(capture)
    generated = execution.get("generated_token_ids")
    _require(isinstance(generated, list) and generated and all(isinstance(item, int) for item in generated), "exact emitted token array is unavailable")
    _require(execution.get("generated_token_count") == len(generated), "generated token count changed")
    _require(execution.get("completion_token_count_match") is True, "completion and emitted token counts differ")
    _require(execution.get("completion_tokens") == len(generated), "authoritative completion count differs")
    _require(execution.get("prompt_tokens") == len(prompt_tokens), "Task-A prompt token count differs")
    _require(execution.get("cached_prompt_tokens") == 0, "Task-A prompt was not fresh")
    _require(execution.get("reasoning_content") in {"", None} and not execution.get("tool_calls"), "hidden reasoning or tools entered Task A")
    _require(execution.get("finish_reason") == "eos", "Task-A terminal stop is not canonical EOS")
    stop = execution.get("terminal_stop_evidence")
    _require(isinstance(stop, Mapping) and stop.get("observed") is True and stop.get("stop") is True, "terminal stop is absent")
    terminal_eog = int(generated[-1])
    eos_piece = str(props.get("eos_token") or "")
    _require(bool(eos_piece), "runtime EOG identity is absent")
    _require(codec.detokenize([terminal_eog]) == eos_piece, "terminal token is not the bound EOG")
    _require(codec.tokenize(eos_piece) == [terminal_eog], "EOG tokenizer identity changed")
    visible_ids = list(generated[:-1])
    _require(bool(visible_ids), "Task-A produced no retained generated tokens")
    visible_text = codec.detokenize(visible_ids)
    content = str(execution.get("content") or "")
    _require(visible_text == content, "exact emitted visible tokens do not reconstruct Task-A content")
    parse_task_a_output(content)
    retained = [*prompt_tokens, *visible_ids]
    _require(len(retained) == len(prompt_tokens) + len(generated) - 1, "retained-root arithmetic changed")
    return {
        "task_a_request_sha256": str(capture["model_request_sha256"]),
        "task_a_capture_sha256": str(capture["capture_sha256"]),
        "prompt_token_sha256": sha256_bytes(canonical_json_bytes(list(prompt_tokens))),
        "prompt_token_count": len(prompt_tokens),
        "generated_token_sha256": sha256_bytes(canonical_json_bytes(generated)),
        "generated_token_count": len(generated),
        "terminal_stop_identity": {"token_id": terminal_eog, "token_piece_sha256": sha256_bytes(eos_piece.encode()), "decoded_into_retained_state": False},
        "retained_root_token_sha256": sha256_bytes(canonical_json_bytes(retained)),
        "retained_root_token_count": len(retained),
        "retained_root_tokens": retained,
        "derivation_mode": "exact-prompt-array-plus-exact-emitted-array-minus-source-proven-undecoded-terminal-eog",
        "visible_content_retokenized": False,
    }


def derive_continuation_suffix(
    codec: SidecarPromptCodec, *, terminal_eog_id: int, user_content: str
) -> dict[str, Any]:
    sentinels = ("NEO3000_SENTINEL_ALPHA_7F4C", "NEO3000_SENTINEL_BETA_9A21")
    suffix_texts: list[str] = []
    for sentinel in sentinels:
        rendered = codec.render_messages(
            [{"role": "assistant", "content": sentinel}, {"role": "user", "content": user_content}],
            CHAT_TEMPLATE_KWARGS,
        )
        _require(rendered.count(sentinel) == 1, "continuation sentinel is not unique")
        suffix_texts.append(rendered.split(sentinel, 1)[1])
    _require(suffix_texts[0] == suffix_texts[1] and suffix_texts[0], "chat-template continuation depends on assistant content")
    suffix_tokens = codec.tokenize(suffix_texts[0])
    _require(bool(suffix_tokens) and suffix_tokens[0] == terminal_eog_id, "continuation does not begin with captured terminal EOG")
    return {
        "continuation_text_sha256": sha256_bytes(suffix_texts[0].encode()),
        "suffix_token_sha256": sha256_bytes(canonical_json_bytes(suffix_tokens)),
        "suffix_token_count": len(suffix_tokens),
        "suffix_tokens": suffix_tokens,
        "terminal_eog_reintroduced_as_first_suffix_token": True,
        "generated_visible_content_retokenized": False,
    }


def common_prefix_count(first: Sequence[int], second: Sequence[int]) -> int:
    count = 0
    for left, right in zip(first, second):
        if left != right:
            break
        count += 1
    return count


def predict_runtime_native_boundary(
    *, retained_root_tokens: Sequence[int], requested_tokens: Sequence[int], retained_pos_min: int,
    retained_pos_next: int, n_swa: int, memory_removal_capability: str,
    checkpoint_inventory: Sequence[Mapping[str, int]] = (), same_slot: bool = True,
    no_intervening_mutation: bool = True, unchanged_runtime: bool = True,
) -> dict[str, Any]:
    root = list(retained_root_tokens)
    requested = list(requested_tokens)
    raw_common = common_prefix_count(root, requested)
    strict_extension = len(requested) > len(root) and raw_common == len(root)
    _require(strict_extension, "requested token array is not a strict retained-root extension")
    _require(same_slot and no_intervening_mutation and unchanged_runtime, "runtime-native preconditions changed")
    _require(memory_removal_capability in {"full", "full-only", "partial"}, "memory removal capability is unknown")
    _require(retained_pos_next == len(root) and retained_pos_min == retained_pos_next - 1, "retained position geometry changed")
    has_new_tokens = len(requested) > raw_common
    threshold = max(0, retained_pos_next - n_swa - (0 if has_new_tokens else 1))
    rollback_required = retained_pos_min >= threshold
    selected_checkpoint: Mapping[str, int] | None = None
    predicted = raw_common
    if rollback_required:
        for checkpoint in reversed(tuple(checkpoint_inventory)):
            if int(checkpoint["pos_max"]) <= retained_pos_next and (
                int(checkpoint["pos_min"]) < threshold or int(checkpoint["pos_min"]) == 0
            ):
                selected_checkpoint = checkpoint
                break
        if selected_checkpoint is None:
            predicted = 0
        else:
            restored_pos = min(
                retained_pos_next,
                max(int(selected_checkpoint["pos_min"]) + 1, int(selected_checkpoint["pos_max"])),
            )
            predicted = min(int(selected_checkpoint["token_count_up_to_restored_pos"]), int(selected_checkpoint["n_tokens"]))
    _require(predicted >= 0, "predicted carrier count is invalid")
    return {
        "raw_common_prefix_count": raw_common,
        "raw_common_prefix_sha256": sha256_bytes(canonical_json_bytes(requested[:raw_common])),
        "strict_extension": strict_extension,
        "retained_pos_min": retained_pos_min,
        "retained_pos_next": retained_pos_next,
        "n_swa": n_swa,
        "pos_min_threshold": threshold,
        "memory_removal_capability": memory_removal_capability,
        "rollback_required": rollback_required,
        "selected_checkpoint": dict(selected_checkpoint) if selected_checkpoint is not None else None,
        "one_token_prompt_logits_correction_applies": len(requested) == len(root),
        "predicted_executable_carrier_count": predicted,
        "observed_cache_telemetry_used": False,
        "same_slot": same_slot,
        "no_intervening_mutation": no_intervening_mutation,
        "unchanged_runtime": unchanged_runtime,
    }


def build_branch_derivation(
    *, root_record: Mapping[str, Any], suffix_record: Mapping[str, Any], branch_id: str,
    route: str, snapshot_identity: Mapping[str, Any] | None,
) -> dict[str, Any]:
    _require(branch_id in BRANCH_IDS and route in {"live-root", "snapshot-restored-root"}, "branch derivation identity changed")
    root_tokens = list(root_record["retained_root_tokens"])
    suffix_tokens = list(suffix_record["suffix_tokens"])
    complete = [*root_tokens, *suffix_tokens]
    boundary = predict_runtime_native_boundary(
        retained_root_tokens=root_tokens,
        requested_tokens=complete,
        retained_pos_min=len(root_tokens) - 1,
        retained_pos_next=len(root_tokens),
        n_swa=N_SWA,
        memory_removal_capability=MEMORY_REMOVAL_CAPABILITY,
    )
    body = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "branch_id": branch_id,
        "route": route,
        "root_token_sha256": root_record["retained_root_token_sha256"],
        "root_token_count": len(root_tokens),
        "branch_suffix_sha256": suffix_record["suffix_token_sha256"],
        "branch_suffix_count": len(suffix_tokens),
        "complete_branch_token_sha256": sha256_bytes(canonical_json_bytes(complete)),
        "complete_branch_token_count": len(complete),
        "raw_common_prefix_sha256": boundary["raw_common_prefix_sha256"],
        "raw_common_prefix_count": boundary["raw_common_prefix_count"],
        "source_predicted_executable_boundary": boundary,
        "strict_extension": True,
        "snapshot_identity": dict(snapshot_identity) if snapshot_identity is not None else None,
        "source_and_runtime_binding": {
            "selection_sha256": SOURCE_SELECTION_SHA256,
            "binary_sha256": BINARY_SHA256,
            "model_sha256": MODEL_SHA256,
            "chat_template_sha256": CHAT_TEMPLATE_SHA256,
            "n_swa": N_SWA,
            "n_batch": N_BATCH,
            "n_ubatch": N_UBATCH,
            "context_checkpoints": CONTEXT_CHECKPOINTS,
            "checkpoint_min_step": CHECKPOINT_MIN_STEP,
        },
        "dynamic_request_sha256": json_sha256(_branch_payload(complete, seed=derive_seed(branch_id.rsplit("-branch-", 1)[0], f"branch-{branch_id[-1]}"), cache_prompt=route != "direct")),
        "complete_branch_tokens": complete,
        "observed_cache_telemetry_used": False,
    }
    return {**body, "derivation_sha256": json_sha256(body)}


CAPTURE_EXECUTION_FIELDS = warm_source.CAPTURE_EXECUTION_FIELDS


def _capture_hmac(key: bytes, body: Mapping[str, Any]) -> str:
    return hmac.new(
        key,
        b"neo3000/holostate-multi-branch-runtime-native-carrier/capture-hmac/v1\0"
        + canonical_json_bytes(body),
        hashlib.sha256,
    ).hexdigest().upper()


def capture_request_once(
    path: Path,
    partial_path: Path,
    *,
    experiment_key: bytes,
    request_id: str,
    model_request_sha256: str,
    generation_ordinal: int,
    invoke: Callable[[Callable[[bytes], None]], Any],
) -> dict[str, Any]:
    _require(request_id in REQUEST_ORDER, "capture request is outside frozen order")
    _require(1 <= generation_ordinal <= MAXIMUM_GENERATIONS, "capture ordinal changed")
    _require(not path.exists() and not partial_path.exists(), "request evidence already exists")
    partial_path.parent.mkdir(parents=True, exist_ok=True)
    byte_count = 0
    with partial_path.open("xb") as raw_handle:
        def record(line: bytes) -> None:
            nonlocal byte_count
            _require(isinstance(line, bytes) and bool(line), "raw response line is invalid")
            byte_count += len(line)
            _require(byte_count <= MAX_CAPTURE_BYTES, "raw response exceeds capture ceiling")
            raw_handle.write(line)
            raw_handle.flush()
            os.fsync(raw_handle.fileno())

        execution = invoke(record)
    raw = _regular_bytes(partial_path, "raw response spool", MAX_CAPTURE_BYTES)
    body = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "request_id": request_id,
        "model_request_sha256": model_request_sha256,
        "generation_ordinal": generation_ordinal,
        "captured_before_parsing": True,
        "raw_response_capture": {
            "encoding": "base64",
            "byte_size": len(raw),
            "sha256": sha256_bytes(raw),
            "bytes": base64.b64encode(raw).decode("ascii"),
        },
        "execution": {name: warm_source._capture_value(execution, name) for name in CAPTURE_EXECUTION_FIELDS},
    }
    body["execution"] = normalized_capture_execution(body)
    document = {**body, "capture_hmac_sha256": _capture_hmac(experiment_key, body)}
    _exclusive_write(path, canonical_json_bytes(document) + b"\n")
    partial_path.unlink()
    return verify_capture(
        path,
        experiment_key=experiment_key,
        request_id=request_id,
        model_request_sha256=model_request_sha256,
        generation_ordinal=generation_ordinal,
    )


def verify_capture(
    path: Path,
    *,
    experiment_key: bytes,
    request_id: str,
    model_request_sha256: str,
    generation_ordinal: int,
) -> dict[str, Any]:
    data = _regular_bytes(path, "authenticated response capture", MAX_CAPTURE_BYTES)
    value = json.loads(data)
    _require(isinstance(value, dict), "capture is not an object")
    body = {key: item for key, item in value.items() if key != "capture_hmac_sha256"}
    _require(
        value.get("design_id") == DESIGN_ID
        and value.get("request_id") == request_id
        and value.get("model_request_sha256") == model_request_sha256
        and value.get("generation_ordinal") == generation_ordinal
        and value.get("captured_before_parsing") is True,
        "capture identity changed",
    )
    _require(hmac.compare_digest(str(value.get("capture_hmac_sha256", "")), _capture_hmac(experiment_key, body)), "capture HMAC changed")
    raw = value.get("raw_response_capture")
    _require(isinstance(raw, Mapping), "capture raw response is malformed")
    raw_bytes = base64.b64decode(str(raw.get("bytes", "")), validate=True)
    _require(
        raw.get("encoding") == "base64"
        and raw.get("byte_size") == len(raw_bytes)
        and raw.get("sha256") == sha256_bytes(raw_bytes)
        and bool(raw_bytes),
        "capture raw response identity changed",
    )
    _require(isinstance(value.get("execution"), Mapping) and set(value["execution"]) == set(CAPTURE_EXECUTION_FIELDS), "capture execution surface changed")
    return {**value, "capture_sha256": sha256_bytes(data)}


def _record_hmac(key: bytes, domain: bytes, body: Mapping[str, Any]) -> str:
    return hmac.new(key, domain + b"\0" + canonical_json_bytes(body), hashlib.sha256).hexdigest().upper()


def write_authenticated_record(path: Path, key: bytes, domain: str, body: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(body)
    document = {
        **normalized,
        "record_hmac_sha256": _record_hmac(key, domain.encode("ascii"), normalized),
    }
    _exclusive_write(path, canonical_json_bytes(document) + b"\n")
    return {**document, "record_sha256": sha256_file(path)}


def verify_authenticated_record(path: Path, key: bytes, domain: str) -> dict[str, Any]:
    data = _regular_bytes(path, "authenticated operation record")
    value = json.loads(data)
    _require(isinstance(value, dict), "authenticated operation record is malformed")
    body = {name: item for name, item in value.items() if name != "record_hmac_sha256"}
    _require(hmac.compare_digest(str(value.get("record_hmac_sha256", "")), _record_hmac(key, domain.encode("ascii"), body)), "operation record HMAC changed")
    return {**value, "record_sha256": sha256_bytes(data)}


def _request_json_with_identity(
    method: str,
    url: str,
    payload: Mapping[str, Any] | None = None,
    timeout: float = 120,
) -> tuple[dict[str, Any], dict[str, Any]]:
    data = canonical_json_bytes(payload) if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    value = json.loads(raw.decode("utf-8"))
    _require(isinstance(value, dict), "control response is not an object")
    return dict(value), {"byte_size": len(raw), "sha256": sha256_bytes(raw)}


def _request_json(method: str, url: str, payload: Mapping[str, Any] | None = None, timeout: float = 120) -> dict[str, Any]:
    value, _identity = _request_json_with_identity(method, url, payload, timeout)
    return value


def _memory_snapshot(live: kernel.CatalyticKernel0Adapter, sidecar: Any, boundary: str) -> dict[str, Any]:
    try:
        value = live.resource_summary(sidecar=sidecar, boundary=boundary)
    except BaseException as exc:
        return {"available": False, "error_sha256": sha256_bytes(str(exc).encode())}
    return {"available": True, "evidence": dict(value)}


def save_snapshot(
    *, live: kernel.CatalyticKernel0Adapter, sidecar: Any, path: Path, filename: str,
    root_id: str, retained_root_count: int, experiment_key: bytes, record_path: Path,
) -> dict[str, Any]:
    _require(root_id in ROOT_IDS and re.fullmatch(r"[a-z0-9.-]+\.bin", filename) is not None, "snapshot identity is unsafe")
    _require(not path.exists(), "snapshot path already exists")
    request_body = {"filename": filename}
    request_hash = json_sha256(request_body)
    before_memory = _memory_snapshot(live, sidecar, f"before:{root_id}:snapshot-save")
    started_at = _utc_now()
    started = time.monotonic()
    response, raw_response = _request_json_with_identity(
        "POST", f"http://127.0.0.1:{live.h.PORT}/slots/{kernel.PHYSICAL_SLOT}?action=save", request_body
    )
    finished = time.monotonic()
    finished_at = _utc_now()
    after_memory = _memory_snapshot(live, sidecar, f"after:{root_id}:snapshot-save")
    data = _regular_bytes(path, "slot snapshot", 8 * 1024 * 1024 * 1024)
    _require(response.get("id_slot") == kernel.PHYSICAL_SLOT and response.get("filename") == filename, "snapshot save response identity changed")
    _require(response.get("n_saved") == retained_root_count, "snapshot token count differs from retained root")
    _require(response.get("n_written") == len(data), "snapshot byte count differs from file")
    body = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "operation_id": f"{root_id}-snapshot-save",
        "operation_kind": "snapshot-control-save",
        "inference_request": False,
        "model_generation": False,
        "root_id": root_id,
        "source_slot": kernel.PHYSICAL_SLOT,
        "snapshot_filename": filename,
        "snapshot_relative_path": f"snapshots/{filename}",
        "snapshot_size_bytes": len(data),
        "snapshot_sha256": sha256_bytes(data),
        "retained_root_token_count": retained_root_count,
        "request_sha256": request_hash,
        "response_sha256": json_sha256(response),
        "raw_response": raw_response,
        "response": response,
        "started_at": started_at,
        "completed_at": finished_at,
        "wall_clock_ms": (finished - started) * 1000.0,
        "filesystem_bytes_written": len(data),
        "host_memory_before": before_memory,
        "host_memory_after": after_memory,
    }
    return write_authenticated_record(record_path, experiment_key, "snapshot-control-v1", body)


def restore_snapshot(
    *, live: kernel.CatalyticKernel0Adapter, sidecar: Any, path: Path, filename: str,
    root_id: str, ordinal: int, retained_root_count: int, expected_sha256: str,
    experiment_key: bytes, record_path: Path,
) -> dict[str, Any]:
    _require(ordinal in {1, 2}, "snapshot restore ordinal changed")
    before = _regular_bytes(path, "slot snapshot", 8 * 1024 * 1024 * 1024)
    _require(sha256_bytes(before) == expected_sha256, "snapshot bytes changed before restore")
    request_body = {"filename": filename}
    request_hash = json_sha256(request_body)
    before_memory = _memory_snapshot(live, sidecar, f"before:{root_id}:snapshot-restore-{ordinal}")
    started_at = _utc_now()
    started = time.monotonic()
    response, raw_response = _request_json_with_identity(
        "POST", f"http://127.0.0.1:{live.h.PORT}/slots/{kernel.PHYSICAL_SLOT}?action=restore", request_body
    )
    finished = time.monotonic()
    finished_at = _utc_now()
    after_memory = _memory_snapshot(live, sidecar, f"after:{root_id}:snapshot-restore-{ordinal}")
    after = _regular_bytes(path, "slot snapshot", 8 * 1024 * 1024 * 1024)
    _require(before == after and sha256_bytes(after) == expected_sha256, "snapshot bytes changed during restore")
    _require(response.get("id_slot") == kernel.PHYSICAL_SLOT and response.get("filename") == filename, "snapshot restore response identity changed")
    _require(response.get("n_restored") == retained_root_count, "restored token count differs from root")
    _require(response.get("n_read") == len(after), "restored byte count differs from snapshot")
    body = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "operation_id": f"{root_id}-snapshot-restore-{ordinal}",
        "operation_kind": "snapshot-control-restore",
        "inference_request": False,
        "model_generation": False,
        "root_id": root_id,
        "target_slot": kernel.PHYSICAL_SLOT,
        "snapshot_filename": filename,
        "snapshot_size_bytes": len(after),
        "snapshot_sha256_before": expected_sha256,
        "snapshot_sha256_after": sha256_bytes(after),
        "snapshot_bytes_unchanged": True,
        "retained_root_token_count": retained_root_count,
        "request_sha256": request_hash,
        "response_sha256": json_sha256(response),
        "raw_response": raw_response,
        "response": response,
        "started_at": started_at,
        "completed_at": finished_at,
        "wall_clock_ms": (finished - started) * 1000.0,
        "filesystem_bytes_read": int(response["n_read"]),
        "host_memory_before": before_memory,
        "host_memory_after": after_memory,
    }
    return write_authenticated_record(record_path, experiment_key, "snapshot-control-v1", body)


def resource_record(capture: Mapping[str, Any], request_id: str) -> dict[str, Any]:
    execution = normalized_capture_execution(capture)
    logical = int(execution.get("prompt_tokens") or 0)
    reused = int(execution.get("cached_prompt_tokens") or 0)
    completion = int(execution.get("completion_tokens") or 0)
    _require(logical > 0 and 0 <= reused <= logical and completion > 0, "generation resource accounting is invalid")
    return {
        "request_id": request_id,
        "operation_kind": "model-generation",
        "request_count": 1,
        "generation_count": 1,
        "logical_prompt_tokens": logical,
        "reused_prompt_tokens": reused,
        "fresh_prompt_tokens": logical - reused,
        "completion_tokens": completion,
        "fresh_prompt_plus_completion_tokens": logical - reused + completion,
        "maximum_request_context": logical + (TASK_A_MAX_TOKENS if request_id.endswith("task-a") else BRANCH_MAX_TOKENS),
    }


def root_readdress_record(
    execution: Any,
    *,
    root_id: str,
    payload: Mapping[str, Any],
    predicted_boundary: int,
    snapshot_sha256: str,
) -> dict[str, Any]:
    logical = int(warm_source._capture_value(execution, "prompt_tokens") or 0)
    reused = int(warm_source._capture_value(execution, "cached_prompt_tokens") or 0)
    completion = int(warm_source._capture_value(execution, "completion_tokens") or 0)
    stop = warm_source._capture_value(execution, "terminal_stop_evidence")
    _require(logical > 0 and 0 <= reused <= logical and completion == 0, "root-readdress accounting is invalid")
    _require(payload.get("cache_prompt") is True and payload.get("n_predict") == 0, "root-readdress request law changed")
    _require(len(payload.get("prompt", [])) > predicted_boundary, "root-readdress suffix is empty")
    return {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "operation_id": f"{root_id}-root-readdress",
        "operation_kind": "zero-output-root-readdress",
        "inference_request_count": 1,
        "generation_count": 0,
        "model_output_tokens": 0,
        "logical_prompt_tokens": logical,
        "reused_prompt_tokens": reused,
        "fresh_prompt_tokens": logical - reused,
        "completion_tokens": completion,
        "fresh_prompt_plus_completion_tokens": logical - reused,
        "maximum_request_context": logical,
        "predicted_carrier_count": predicted_boundary,
        "observed_cached_prompt_tokens": reused,
        "root_readdress_gate": reused == predicted_boundary,
        "snapshot_sha256": snapshot_sha256,
        "terminal_stop_evidence": stop,
        "request_sha256": json_sha256(payload),
    }


def evaluate_reuse(derivation: Mapping[str, Any], capture: Mapping[str, Any]) -> dict[str, Any]:
    execution = normalized_capture_execution(capture)
    predicted = int(derivation["source_predicted_executable_boundary"]["predicted_executable_carrier_count"])
    observed = int(execution.get("cached_prompt_tokens") or 0)
    logical = int(execution.get("prompt_tokens") or 0)
    return {
        "branch_id": derivation["branch_id"],
        "route": derivation["route"],
        "predicted_executable_carrier_count": predicted,
        "observed_cached_prompt_tokens": observed,
        "logical_prompt_tokens": logical,
        "fresh_prompt_tokens": logical - observed,
        "runtime_native_carrier_gate": observed == predicted,
        "prediction_bound_before_contact": True,
        "observed_cache_telemetry_used_for_prediction": False,
        "continue_panel": True,
    }


def _duplicate_rejecting_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        _require(key not in value, "protected evaluator contains duplicate keys")
        value[key] = item
    return value


def _load_protected_evaluator_after_terminal_gates(repository: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    custody = protected_evaluator_custody(repository)
    data = _regular_bytes(repository / PROTECTED_EVALUATOR_PATH, "protected evaluator", 64 * 1024)
    _require(len(data) == PROTECTED_EVALUATOR_SIZE and sha256_bytes(data) == PROTECTED_EVALUATOR_SHA256, "protected evaluator identity changed")
    value = json.loads(data, object_pairs_hook=_duplicate_rejecting_object)
    _require(
        isinstance(value, dict)
        and value.get("corpus_id") == FAMILY_ID
        and value.get("evaluator_id") == f"{FAMILY_ID}-protected-evaluator"
        and tuple(value.get("roots", {})) == ROOT_IDS,
        "protected evaluator surface changed",
    )
    return value, {**custody, "bytes_opened": True, "bytes_hashed": True, "bytes_parsed": True, "sha256_verified": True}


def score_protected(
    repository: Path,
    captures: Mapping[str, Mapping[str, Any]],
    *,
    completed_capture_ids: Sequence[str],
    completed_readdress_ids: Sequence[str],
    completed_snapshot_control_ids: Sequence[str],
    cleanup_passed: bool,
    postflight_passed: bool,
) -> dict[str, Any]:
    _require(tuple(completed_capture_ids) == REQUEST_ORDER, "protected evaluator opened before all 20 captures")
    _require(tuple(completed_readdress_ids) == READDRESS_ORDER, "protected evaluator opened before all four readdresses")
    _require(tuple(completed_snapshot_control_ids) == SNAPSHOT_CONTROL_ORDER, "protected evaluator opened before all snapshot controls")
    _require(cleanup_passed and postflight_passed, "protected evaluator opened before cleanup/postflight")
    evaluator, custody = _load_protected_evaluator_after_terminal_gates(repository)
    root_truth = evaluator["roots"]
    per_root: dict[str, Any] = {}
    task_a_correct = 0
    task_a_state_correct = 0
    catalytic_branch_1 = 0
    catalytic_branch_2 = 0
    direct_branch_1 = 0
    direct_branch_2 = 0
    for root_id in ROOT_IDS:
        expected = root_truth[root_id]
        task_a = parse_task_a_output(str(captures[f"{root_id}-task-a"]["execution"]["content"]))
        text = "\n".join(task_a["state"]).casefold()
        concept_groups = expected["task_a_state_required_concepts"]
        concept_passes = [all(str(term).casefold() in text for term in group) for group in concept_groups]
        answer_ok = task_a["answer"] == expected["task_a_answer"]
        state_ok = all(concept_passes)
        task_a_correct += int(answer_ok)
        task_a_state_correct += int(state_ok)
        branch_bools: dict[str, Any] = {}
        for number in (1, 2):
            branch_id = f"{root_id}-branch-{number}"
            expected_answer = expected["branch_answers"][branch_id]
            catalytic_answer = parse_branch_output(str(captures[f"{branch_id}-catalytic"]["execution"]["content"]))
            direct_answer = parse_branch_output(str(captures[f"{branch_id}-direct"]["execution"]["content"]))
            catalytic_ok = catalytic_answer == expected_answer
            direct_ok = direct_answer == expected_answer
            branch_bools[f"branch_{number}"] = {"catalytic_correct": catalytic_ok, "direct_correct": direct_ok}
            if number == 1:
                catalytic_branch_1 += int(catalytic_ok)
                direct_branch_1 += int(direct_ok)
            else:
                catalytic_branch_2 += int(catalytic_ok)
                direct_branch_2 += int(direct_ok)
        per_root[root_id] = {
            "task_a_answer_correct": answer_ok,
            "task_a_textual_state_correct": state_ok,
            "task_a_required_concepts_correct": sum(int(value) for value in concept_passes),
            "task_a_required_concepts_total": len(concept_passes),
            **branch_bools,
        }
    return {
        "task_a_answer_accuracy": {"correct": task_a_correct, "total": 4},
        "task_a_textual_latent_state_accuracy": {"correct": task_a_state_correct, "total": 4},
        "catalytic_branch_1_accuracy": {"correct": catalytic_branch_1, "total": 4},
        "catalytic_branch_2_accuracy": {"correct": catalytic_branch_2, "total": 4},
        "direct_branch_1_accuracy": {"correct": direct_branch_1, "total": 4},
        "direct_branch_2_accuracy": {"correct": direct_branch_2, "total": 4},
        "aggregate_catalytic_branch_accuracy": {"correct": catalytic_branch_1 + catalytic_branch_2, "total": 8},
        "aggregate_direct_branch_accuracy": {"correct": direct_branch_1 + direct_branch_2, "total": 8},
        "per_root": per_root,
        "protected_evaluator_custody": custody,
        "protected_answers_disclosed": False,
        "protected_concepts_disclosed": False,
        "evaluator_open_count": 1,
    }


def exact_ratio(tokens: int, correct: int) -> dict[str, Any]:
    return {"numerator": tokens, "denominator": correct, "defined": correct > 0}


def _route_summary(records: Sequence[Mapping[str, Any]], *, correct: int) -> dict[str, Any]:
    fresh = sum(int(item["fresh_prompt_tokens"]) for item in records)
    completion = sum(int(item["completion_tokens"]) for item in records)
    total = fresh + completion
    return {
        "request_count": sum(int(item.get("request_count", item.get("inference_request_count", 0))) for item in records),
        "generation_count": sum(int(item.get("generation_count", 0)) for item in records),
        "logical_prompt_tokens": sum(int(item["logical_prompt_tokens"]) for item in records),
        "reused_prompt_tokens": sum(int(item["reused_prompt_tokens"]) for item in records),
        "fresh_prompt_tokens": fresh,
        "completion_tokens": completion,
        "fresh_prompt_plus_completion_tokens": total,
        "maximum_request_context": max(int(item["maximum_request_context"]) for item in records),
        "correct_branch_answers": correct,
        "fresh_tokens_per_correct": exact_ratio(total, correct),
    }


def account_resources(
    records: Sequence[Mapping[str, Any]],
    readdress_records: Sequence[Mapping[str, Any]],
    scoring: Mapping[str, Any],
    snapshot_controls: Sequence[Mapping[str, Any]],
    deletion_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    by_id = {str(item["request_id"]): item for item in records}
    _require(tuple(by_id) == REQUEST_ORDER, "generation resource order changed")
    _require(tuple(item["operation_id"] for item in readdress_records) == READDRESS_ORDER, "readdress resource order changed")
    _require(tuple(item["operation_id"] for item in snapshot_controls) == SNAPSHOT_CONTROL_ORDER, "snapshot control order changed")
    task_a = [by_id[f"{root_id}-task-a"] for root_id in ROOT_IDS]
    catalytic = [item for key, item in by_id.items() if key.endswith("-catalytic")]
    direct = [item for key, item in by_id.items() if key.endswith("-direct")]
    catalytic_route = [*catalytic, *readdress_records]
    catalytic_correct = int(scoring["aggregate_catalytic_branch_accuracy"]["correct"])
    direct_correct = int(scoring["aggregate_direct_branch_accuracy"]["correct"])
    catalytic_summary = _route_summary(catalytic_route, correct=catalytic_correct)
    direct_summary = _route_summary(direct, correct=direct_correct)
    cross = {
        "catalytic_tokens_x_direct_correct": catalytic_summary["fresh_prompt_plus_completion_tokens"] * direct_correct,
        "direct_tokens_x_catalytic_correct": direct_summary["fresh_prompt_plus_completion_tokens"] * catalytic_correct,
    }
    strict = catalytic_correct > 0 and direct_correct > 0 and cross["catalytic_tokens_x_direct_correct"] < cross["direct_tokens_x_catalytic_correct"]
    save_controls = [item for item in snapshot_controls if item["operation_kind"] == "snapshot-control-save"]
    restore_controls = [item for item in snapshot_controls if item["operation_kind"] == "snapshot-control-restore"]
    return {
        "shared_task_a_reported_once_and_excluded_from_marginal_routes": True,
        "shared_task_a": _route_summary(task_a, correct=int(scoring["task_a_answer_accuracy"]["correct"])),
        "primary_catalytic_route": catalytic_summary,
        "primary_direct_route": direct_summary,
        "exact_integer_cross_products": cross,
        "catalytic_accuracy_at_least_direct": catalytic_correct >= direct_correct,
        "catalytic_fresh_tokens_per_correct_strictly_lower": strict,
        "snapshot_resources": {
            "included_in_fresh_token_accounting": False,
            "save_count": len(save_controls),
            "restore_count": len(restore_controls),
            "control_count": len(snapshot_controls),
            "bytes_written": sum(int(item["filesystem_bytes_written"]) for item in save_controls),
            "bytes_read": sum(int(item["filesystem_bytes_read"]) for item in restore_controls),
            "save_wall_clock_ms": sum(float(item["wall_clock_ms"]) for item in save_controls),
            "restore_wall_clock_ms": sum(float(item["wall_clock_ms"]) for item in restore_controls),
            "host_memory_observations_available": any(item["host_memory_before"].get("available") is True for item in snapshot_controls),
            "deletion_count": len(deletion_records),
            "all_snapshots_deleted": len(deletion_records) == 4 and all(item.get("deleted") is True for item in deletion_records),
        },
        "historical_projection": {"decision_authority": False},
    }


def classify_result(
    *,
    scoring: Mapping[str, Any],
    resources: Mapping[str, Any],
    reuse_reports: Mapping[str, Mapping[str, Any]],
    readdress_records: Sequence[Mapping[str, Any]],
    direct_freshness: Mapping[str, bool],
    complete_panel: bool,
    snapshot_custody_passed: bool,
    cleanup_passed: bool,
    postflight_passed: bool,
) -> str:
    if not (
        complete_panel
        and snapshot_custody_passed
        and cleanup_passed
        and postflight_passed
        and all(direct_freshness.values())
    ):
        return "INCONCLUSIVE"
    live_reports = [value for value in reuse_reports.values() if value["route"] == "live-root"]
    restored_reports = [value for value in reuse_reports.values() if value["route"] == "snapshot-restored-root"]
    _require(len(live_reports) == len(restored_reports) == 4, "reuse-report geometry changed")
    if not all(value["runtime_native_carrier_gate"] for value in live_reports):
        return "PROCESS_LOCAL_MULTI_BRANCH_RUNTIME_NATIVE_CARRIER_REUSE_NOT_SUPPORTED"
    if not all(value["runtime_native_carrier_gate"] for value in restored_reports) or not all(
        value["root_readdress_gate"] for value in readdress_records
    ):
        return "PROCESS_LOCAL_LIVE_ROOT_STRICT_EXTENSION_SUPPORTED_WITHOUT_SNAPSHOT_BRANCH_ISOLATION"
    if (
        resources["catalytic_accuracy_at_least_direct"] is True
        and resources["catalytic_fresh_tokens_per_correct_strictly_lower"] is True
    ):
        return "PROCESS_LOCAL_MULTI_BRANCH_RUNTIME_NATIVE_CARRIER_FRESH_TOKEN_ADVANTAGE_SUPPORTED"
    return "PROCESS_LOCAL_MULTI_BRANCH_RUNTIME_NATIVE_CARRIER_REUSE_SUPPORTED_WITHOUT_FRESH_TOKEN_ADVANTAGE"


def _callable_binding(values: Sequence[Callable[..., Any]]) -> dict[str, Any]:
    module_name = "holostate_v1_multi_branch_runtime_native_carrier_evaluation"
    members = [
        {
            "name": f"{module_name}.{value.__qualname__}",
            "source_sha256": sha256_bytes(inspect.getsource(value).encode()),
        }
        for value in values
    ]
    return {"members": members, "sha256": json_sha256(members)}


def root_derivation_binding() -> dict[str, Any]:
    return _callable_binding([derive_retained_root])


def strict_extension_binding() -> dict[str, Any]:
    return _callable_binding([derive_continuation_suffix, build_branch_derivation])


def boundary_binding() -> dict[str, Any]:
    return _callable_binding([common_prefix_count, predict_runtime_native_boundary, evaluate_reuse])


def snapshot_binding() -> dict[str, Any]:
    return _callable_binding([_request_json_with_identity, save_snapshot, restore_snapshot])


def scorer_binding() -> dict[str, Any]:
    return _callable_binding([_load_protected_evaluator_after_terminal_gates, score_protected])


def resource_binding() -> dict[str, Any]:
    return _callable_binding([resource_record, root_readdress_record, exact_ratio, _route_summary, account_resources])


def closure_binding() -> dict[str, Any]:
    return _callable_binding([root_readdress_record, classify_result])


def scientific_binding(corpus: Mapping[str, Any]) -> dict[str, Any]:
    body = {
        "family_id": FAMILY_ID,
        "design_id": DESIGN_ID,
        "public_corpus_sha256": PUBLIC_CORPUS_SHA256,
        "protected_evaluator_sha256": PROTECTED_EVALUATOR_SHA256,
        "root_ids": list(ROOT_IDS),
        "branch_ids": list(BRANCH_IDS),
        "first_branch": FIRST_BRANCH,
        "request_order": list(REQUEST_ORDER),
        "inference_order": list(INFERENCE_ORDER),
        "snapshot_control_order": list(SNAPSHOT_CONTROL_ORDER),
        "request_template_sha256": fixed_request_templates(corpus),
        "generation_ceiling": MAXIMUM_GENERATIONS,
        "inference_request_ceiling": MAXIMUM_INFERENCE_REQUESTS,
        "snapshot_control_ceiling": SNAPSHOT_CONTROL_COUNT,
        "one_physical_slot": True,
        "one_sidecar_epoch": True,
        "no_materialization": True,
        "no_retry": True,
        "catalytic_before_direct": True,
    }
    return {"body": body, "sha256": json_sha256(body)}


def controller_binding() -> dict[str, Any]:
    return _callable_binding([
        _task_a_payload,
        _branch_payload,
        capture_request_once,
        verify_capture,
        write_authenticated_record,
        verify_authenticated_record,
        run_evaluation,
    ])


def build_corpus_binding_document(repository: Path) -> dict[str, Any]:
    corpus = load_public_corpus(repository)
    custody = protected_evaluator_custody(repository)
    body = {
        "schema_version": 1,
        "family_id": FAMILY_ID,
        "classification": "MULTI_BRANCH_RUNTIME_NATIVE_CARRIER_CORPUS_AND_PROTECTED_EVALUATOR_FROZEN",
        "public_corpus": {
            "path": PUBLIC_CORPUS_PATH.as_posix(),
            "sha256": PUBLIC_CORPUS_SHA256,
            "size_bytes": PUBLIC_CORPUS_SIZE,
            "root_count": 4,
            "branch_count": 8,
        },
        "protected_evaluator": {
            "path": PROTECTED_EVALUATOR_PATH.as_posix(),
            "sha256": PROTECTED_EVALUATOR_SHA256,
            "size_bytes": PROTECTED_EVALUATOR_SIZE,
            "path_ignored": custody["ignored"],
            "tracked": custody["tracked"],
            "answer_disclosure": False,
            "concept_disclosure": False,
        },
        "root_ids": list(ROOT_IDS),
        "branch_ids": list(BRANCH_IDS),
        "reasoning_types": [branch["reasoning_type"] for root in corpus["roots"] for branch in root["branches"]],
        "simultaneous_freeze": {
            "both_surfaces_finalized_before_binding": True,
            "surfaces_frozen_before_model_contact": True,
            "future_outcome_based_mutation_forbidden": True,
            "retained_regardless_of_outcome": True,
        },
        "retired_panel_reused": False,
        "zero_model_contact": True,
    }
    return {**body, "binding_sha256": json_sha256(body)}


def write_corpus_binding(repository: Path) -> Path:
    document = build_corpus_binding_document(repository)
    _write_or_require_identical(repository / CORPUS_BINDING_PATH, canonical_json_bytes(document) + b"\n")
    return repository / CORPUS_BINDING_PATH


def _verify_source_bindings(repository: Path) -> dict[str, Any]:
    _require(sha256_file(repository / SOURCE_SELECTION_PATH) == SOURCE_SELECTION_SHA256, "source selection artifact changed")
    selection = json.loads(_regular_bytes(repository / SOURCE_SELECTION_PATH, "source selection", 256 * 1024))
    _require(selection.get("selection_classification") == SOURCE_BOUNDARY_SELECTION, "source boundary selection changed")
    _require(selection.get("same_panel_line_retired") is True, "retired-panel law changed")
    _require(sha256_file(repository / SOURCE_ADJUDICATION_PATH) == SOURCE_ADJUDICATION_SHA256, "source adjudication changed")
    lines = (repository / "lab/results.jsonl").read_text(encoding="utf-8").splitlines()
    _require(len(lines) == SOURCE_RECORD_LINE, "result ledger line count changed before preparation")
    record = json.loads(lines[SOURCE_RECORD_LINE - 1])
    _require(record.get("id") == SOURCE_RECORD_ID and json_sha256(record) == SOURCE_RECORD_SHA256, "source result record changed")
    paths = predecessor.state_paths(repository)
    archive = predecessor_adjudication._verify_archive(repository, paths)
    _require(
        archive.get("archive_evidence_member_count") == 21
        and archive.get("archive_physical_file_count") == 22
        and archive.get("live_archive_equality_verified") is True,
        "source evidence archive custody changed",
    )
    return {
        "selection_sha256": SOURCE_SELECTION_SHA256,
        "adjudication_sha256": SOURCE_ADJUDICATION_SHA256,
        "record_id": SOURCE_RECORD_ID,
        "record_line": SOURCE_RECORD_LINE,
        "record_sha256": SOURCE_RECORD_SHA256,
        "source_execution_commit": SOURCE_EXECUTION_COMMIT,
        "archive_sha256": SOURCE_ARCHIVE_SHA256,
        "source_law_file_sha256": {path: sha256_file(repository / path) for path in SOURCE_LAW_PATHS},
    }


def build_preregistration_document(repository: Path) -> dict[str, Any]:
    corpus = load_public_corpus(repository)
    source = _verify_source_bindings(repository)
    custody = protected_evaluator_custody(repository)
    scientific = scientific_binding(corpus)
    controller = controller_binding()
    root_derivation = root_derivation_binding()
    strict_extension = strict_extension_binding()
    boundary = boundary_binding()
    snapshot = snapshot_binding()
    scorer = scorer_binding()
    resources = resource_binding()
    closure = closure_binding()
    binding_document = build_corpus_binding_document(repository)
    body = {
        "schema_version": 1,
        "family_id": FAMILY_ID,
        "design_id": DESIGN_ID,
        "status": "preregistered-static-only",
        "starting_protected_main": STARTING_PROTECTED_MAIN,
        "scientific_question": (
            "Can one authenticated runtime-native Task-A carrier support two distinct held-out branches, including one snapshot-reconstituted branch root, with at least direct-control utility and lower marginal fresh-token cost after root readdress?"
        ),
        "source_bindings": source,
        "corpus": {
            "path": PUBLIC_CORPUS_PATH.as_posix(),
            "sha256": PUBLIC_CORPUS_SHA256,
            "size_bytes": PUBLIC_CORPUS_SIZE,
            "binding_path": CORPUS_BINDING_PATH.as_posix(),
            "binding_sha256": binding_document["binding_sha256"],
            "root_ids": list(ROOT_IDS),
            "branch_ids": list(BRANCH_IDS),
            "retired_panel_reused": False,
        },
        "protected_evaluator": custody,
        "runtime_identity": {
            "binary_sha256": BINARY_SHA256,
            "runtime_version": RUNTIME_VERSION,
            "model_sha256": MODEL_SHA256,
            "chat_template_sha256": CHAT_TEMPLATE_SHA256,
            "tokenizer_bound_to_model": True,
            "memory_implementation": "hybrid-dsv4-full-sequence-state",
            "memory_removal_capability": MEMORY_REMOVAL_CAPABILITY,
            "n_swa": N_SWA,
            "n_batch": N_BATCH,
            "n_ubatch": N_UBATCH,
            "context_checkpoints": CONTEXT_CHECKPOINTS,
            "checkpoint_min_step": CHECKPOINT_MIN_STEP,
            "slot_save_path_required": True,
        },
        "root_token_array_law": {
            "endpoint": "/completion",
            "prompt_type": "exact integer token array",
            "task_a_prompt": "pre-rendered by bound chat template then tokenized once before contact",
            "return_tokens": True,
            "return_progress": True,
            "strict_grammar": True,
            "one_generation_maximum": True,
            "completion_count_equals_emitted_count": True,
            "terminal_eog_authenticated": True,
            "retained_root": "exact prompt tokens plus exact emitted token IDs minus only terminal EOG proven not decoded into retained state",
            "visible_content_retokenization_forbidden": True,
            "hidden_reasoning_forbidden": True,
        },
        "strict_extension_law": {
            "construction": "retained root token vector plus independently tokenized frozen chat-template continuation suffix",
            "suffix_begins_with_captured_terminal_eog": True,
            "catalytic_and_direct_complete_token_arrays_identical": True,
            "distinct_suffix_hash_required_per_branch": True,
            "dynamic_derivation_record_authenticated_before_branch_contact": True,
            "observed_cache_telemetry_used_for_prediction": False,
        },
        "source_predicted_boundary_law": {
            "full_law_bound_by": SOURCE_SELECTION_SHA256,
            "raw_common_prefix": "exact old/new token equality",
            "threshold": "max(0, pos_next - n_swa - (0 if has_new_tokens else 1))",
            "preserve_live_state_when": "retained_pos_min < threshold",
            "otherwise": "select newest eligible checkpoint or predict zero",
            "exact_equal_prompt_correction": "subtract one only when request exactly equals retained prompt",
            "strict_extension_expected_result": "complete retained root count only when every source precondition passes",
            "telemetry_gate": "observed cached_prompt_tokens equals precontact predicted count",
            "false_gate_continues_panel": True,
        },
        "snapshot_topology": {
            "physical_slots": 1,
            "sidecar_epochs": 1,
            "per_root": [
                "fresh Task A",
                "authenticate exact retained root",
                "save one full-sequence snapshot",
                "execute counterbalanced live-root branch",
                "restore snapshot",
                "execute second branch from restored root",
                "restore snapshot",
                "perform nonempty zero-output root readdress",
                "execute fresh direct Branch 1",
                "execute fresh direct Branch 2",
            ],
            "branch_first_by_root": FIRST_BRANCH,
            "snapshot_save_count": SNAPSHOT_SAVE_COUNT,
            "snapshot_restore_count": SNAPSHOT_RESTORE_COUNT,
            "snapshot_control_count": SNAPSHOT_CONTROL_COUNT,
            "snapshot_controls_are_inference_requests": False,
            "snapshot_controls_are_model_generations": False,
            "snapshot_files_deleted_during_cleanup": True,
            "snapshot_bytes_archived": False,
            "exact_restoration_claim": "LOCKED",
        },
        "execution": {
            "request_order": list(REQUEST_ORDER),
            "inference_order": list(INFERENCE_ORDER),
            "readdress_order": list(READDRESS_ORDER),
            "snapshot_control_order": list(SNAPSHOT_CONTROL_ORDER),
            "maximum_model_generations": MAXIMUM_GENERATIONS,
            "maximum_inference_requests": MAXIMUM_INFERENCE_REQUESTS,
            "maximum_snapshot_controls": SNAPSHOT_CONTROL_COUNT,
            "materialization_requests": 0,
            "retry_paths": 0,
            "outcome_early_stop": False,
            "catalytic_before_direct_disclosed": True,
            "seeds": {
                root_id: {role: derive_seed(root_id, role) for role in ("task-a", "branch-1", "branch-2")}
                for root_id in ROOT_IDS
            },
            "request_template_sha256": fixed_request_templates(corpus),
        },
        "direct_controls": {
            "same_complete_branch_token_array": True,
            "cache_prompt": False,
            "cached_prompt_tokens_required": 0,
            "same_seed_grammar_temperature_and_completion_ceiling": True,
            "contamination_classification": "INCONCLUSIVE",
        },
        "protected_scoring": {
            "open_count": 1,
            "required_before_open": {
                "captures": MAXIMUM_GENERATIONS,
                "root_readdresses": 4,
                "snapshot_controls": SNAPSHOT_CONTROL_COUNT,
                "cleanup_passed": True,
                "postflight_passed": True,
            },
            "duplicate_keys_rejected": True,
            "publish_only_booleans_and_aggregates": True,
            "task_a_textual_state_is_carrier_gate": False,
        },
        "resource_law": {
            "shared_task_a_reported_once_excluded_from_routes": True,
            "catalytic_route": "eight catalytic branches plus four root-readdress operations",
            "direct_route": "eight fresh direct branches",
            "comparison": "exact integer cross-products of fresh prompt-plus-completion tokens per correct branch answer",
            "snapshot_resources_reported_separately": True,
            "snapshot_resources_treated_as_free_total_compute": False,
            "historical_projection_decision_authority": False,
        },
        "decision_law": {
            "advantage": "PROCESS_LOCAL_MULTI_BRANCH_RUNTIME_NATIVE_CARRIER_FRESH_TOKEN_ADVANTAGE_SUPPORTED",
            "reuse_without_advantage": "PROCESS_LOCAL_MULTI_BRANCH_RUNTIME_NATIVE_CARRIER_REUSE_SUPPORTED_WITHOUT_FRESH_TOKEN_ADVANTAGE",
            "live_only": "PROCESS_LOCAL_LIVE_ROOT_STRICT_EXTENSION_SUPPORTED_WITHOUT_SNAPSHOT_BRANCH_ISOLATION",
            "reuse_not_supported": "PROCESS_LOCAL_MULTI_BRANCH_RUNTIME_NATIVE_CARRIER_REUSE_NOT_SUPPORTED",
            "inconclusive": "custody, incomplete execution, direct contamination, evaluator, cleanup, or postflight failure only",
        },
        "claim_locks": {
            "exact_lexical_prefix_inheritance": "LOCKED",
            "byte_exact_snapshot_restoration": "LOCKED",
            "exact_restoration": "LOCKED",
            "complete_catalytic_lifecycle": "LOCKED",
            "restart_persistent_state": "LOCKED",
            "general_catalytic_inference": "LOCKED",
            "arbitrary_task_transfer": "LOCKED",
            "total_compute_amplification": "LOCKED",
            "wall_clock_advantage": "LOCKED_UNLESS_SEPARATELY_ESTABLISHED",
            "persistent_blackboard_value": "LOCKED",
            "adaptive_swarms": "LOCKED",
            "superiority": "LOCKED",
            "sota": "LOCKED",
            "automatic_promotion": False,
        },
        "bindings": {
            "scientific": scientific,
            "controller": controller,
            "root_derivation": root_derivation,
            "strict_extension": strict_extension,
            "runtime_native_boundary": boundary,
            "snapshot_custody": snapshot,
            "protected_scorer": scorer,
            "resource_accounting": resources,
            "closure_and_decision": closure,
        },
        "execution_absences": {
            "authority": 0,
            "sidecar": 0,
            "model_requests": 0,
            "generations": 0,
            "captures": 0,
            "results": 0,
            "archives": 0,
            "ledger_records": 0,
        },
        "next_action": "AUTHORIZE_ONE_LIVE_MULTI_BRANCH_RUNTIME_NATIVE_CARRIER_EVALUATION",
    }
    return {**body, "artifact_sha256": json_sha256(body)}


def write_preregistration(repository: Path) -> Path:
    write_corpus_binding(repository)
    document = build_preregistration_document(repository)
    _write_or_require_identical(repository / PREREGISTRATION_PATH, canonical_json_bytes(document) + b"\n")
    return repository / PREREGISTRATION_PATH


def validate_preregistration(repository: Path) -> dict[str, Any]:
    expected = build_preregistration_document(repository)
    path = repository / PREREGISTRATION_PATH
    actual = json.loads(_regular_bytes(path, "multi-branch preregistration", 2 * 1024 * 1024))
    _require(actual == expected, "multi-branch preregistration differs from exact reconstruction")
    _require(sha256_file(repository / CORPUS_BINDING_PATH) == sha256_bytes(canonical_json_bytes(build_corpus_binding_document(repository)) + b"\n"), "corpus binding differs from exact reconstruction")
    return actual


def authority_id_sha256(raw_authority_id: str) -> str:
    _require(re.fullmatch(r"[0-9a-f]{64}", raw_authority_id or "") is not None, "external authority ID must be fresh lowercase 64-hex")
    return sha256_bytes(
        b"neo3000/holostate-multi-branch-runtime-native-carrier/authority-id/v1\0"
        + raw_authority_id.encode("ascii")
    )


def build_external_authority(
    raw_authority_id: str,
    *,
    authorized_commit: str,
    current_commit: str,
    preregistration_sha256: str,
) -> dict[str, Any]:
    _require(re.fullmatch(r"[0-9a-f]{40}", authorized_commit or "") is not None, "authority commit identity is malformed")
    _require(authorized_commit == current_commit, "external authority is not bound to current protected main")
    _require(re.fullmatch(r"[0-9A-F]{64}", preregistration_sha256 or "") is not None, "preregistration identity is malformed")
    return {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "authority_id_sha256": authority_id_sha256(raw_authority_id),
        "authorized_commit": authorized_commit,
        "preregistration_file_sha256": preregistration_sha256,
        "maximum_model_generations": MAXIMUM_GENERATIONS,
        "maximum_inference_requests": MAXIMUM_INFERENCE_REQUESTS,
        "maximum_snapshot_controls": SNAPSHOT_CONTROL_COUNT,
        "single_use": True,
        "retry_allowed": False,
        "raw_authority_id_persisted": False,
    }


def _experiment_key(root: bytes) -> bytes:
    return hmac.new(
        root,
        b"neo3000/holostate-multi-branch-runtime-native-carrier/experiment-key/v1\0" + DESIGN_ID.encode(),
        hashlib.sha256,
    ).digest()


def _authority_hmac(root: bytes, body: Mapping[str, Any]) -> str:
    return hmac.new(
        root,
        b"neo3000/holostate-multi-branch-runtime-native-carrier/authority-receipt/v1\0"
        + canonical_json_bytes(body),
        hashlib.sha256,
    ).hexdigest().upper()


def consume_authority_once(repository: Path, root: bytes, authority: Mapping[str, Any]) -> dict[str, Any]:
    path = repository / AUTHORITY_RECEIPT_PATH
    _require(not path.exists(), "multi-branch authority was already consumed")
    body = {
        **dict(authority),
        "consumed": True,
        "consumed_at": _utc_now(),
        "invocation_count": 1,
        "raw_authority_id_persisted": False,
    }
    document = {**body, "receipt_hmac_sha256": _authority_hmac(root, body)}
    _exclusive_write(path, canonical_json_bytes(document) + b"\n")
    return verify_authority_receipt(repository, root)


def verify_authority_receipt(repository: Path, root: bytes) -> dict[str, Any]:
    path = repository / AUTHORITY_RECEIPT_PATH
    data = _regular_bytes(path, "authority receipt", 64 * 1024)
    value = json.loads(data)
    _require(isinstance(value, dict), "authority receipt is malformed")
    body = {key: item for key, item in value.items() if key != "receipt_hmac_sha256"}
    _require(
        value.get("design_id") == DESIGN_ID
        and value.get("consumed") is True
        and value.get("invocation_count") == 1
        and value.get("raw_authority_id_persisted") is False
        and value.get("retry_allowed") is False,
        "authority receipt law changed",
    )
    _require(hmac.compare_digest(str(value.get("receipt_hmac_sha256", "")), _authority_hmac(root, body)), "authority receipt HMAC changed")
    return {**value, "receipt_sha256": sha256_bytes(data)}


class JournalWriter:
    def __init__(self, path: Path, key: bytes) -> None:
        self.path = path
        self.key = key
        self.previous = "0" * 64
        self.ordinal = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = path.open("xb")

    def append(self, event: str, *, request_id: str | None = None, facts: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self.ordinal += 1
        body = {
            "schema_version": 1,
            "design_id": DESIGN_ID,
            "ordinal": self.ordinal,
            "event": event,
            "request_id": request_id,
            "facts": dict(facts or {}),
            "previous_event_sha256": self.previous,
            "timestamp": _utc_now(),
        }
        event_sha = hmac.new(
            self.key,
            b"neo3000/holostate-multi-branch-runtime-native-carrier/journal-event/v1\0"
            + canonical_json_bytes(body),
            hashlib.sha256,
        ).hexdigest().upper()
        document = {**body, "event_sha256": event_sha}
        self.handle.write(canonical_json_bytes(document) + b"\n")
        self.handle.flush()
        os.fsync(self.handle.fileno())
        self.previous = event_sha
        return document

    def close(self) -> None:
        if not self.handle.closed:
            self.handle.close()


def state_paths(repository: Path) -> dict[str, Path]:
    root = repository / STATE_ROOT
    paths: dict[str, Path] = {
        "run_root": root,
        "run_lock": root / ".run.lock",
        "manifest": root / "manifest.json",
        "journal": root / "journal.jsonl",
        "result": root / "result.json",
        "closure": root / "closure.json",
        "snapshots": root / "snapshots",
        "receipt": repository / AUTHORITY_RECEIPT_PATH,
    }
    for request_id in REQUEST_ORDER:
        paths[f"capture-{request_id}"] = root / "captures" / f"{request_id}.json"
        paths[f"partial-{request_id}"] = root / "captures" / f".{request_id}.raw.partial"
    for root_id in ROOT_IDS:
        paths[f"root-{root_id}"] = root / "derivations" / f"{root_id}-retained-root.json"
        paths[f"snapshot-{root_id}"] = root / "snapshots" / f"{root_id}.bin"
        paths[f"readdress-{root_id}"] = root / "operations" / f"{root_id}-root-readdress.json"
        paths[f"delete-{root_id}"] = root / "operations" / f"{root_id}-snapshot-deletion.json"
        for number in (1, 2):
            paths[f"derivation-{root_id}-{number}"] = root / "derivations" / f"{root_id}-branch-{number}.json"
        for action in ("snapshot-save", "snapshot-restore-1", "snapshot-restore-2"):
            paths[f"control-{root_id}-{action}"] = root / "controls" / f"{root_id}-{action}.json"
    return paths


def _runtime_allowed_paths(paths: Mapping[str, Path]) -> tuple[Path, ...]:
    return tuple(path for key, path in paths.items() if key not in {"run_root", "receipt", "snapshots"})


def _public_preflight(full: Mapping[str, Any]) -> dict[str, Any]:
    return runtime_support._public_preflight(full)


def _archive_terminal(repository: Path, paths: Mapping[str, Path]) -> dict[str, Any]:
    members: list[dict[str, Any]] = []
    sources: dict[str, Path] = {}
    for key, path in paths.items():
        if key in {"run_root", "run_lock", "snapshots"} or key.startswith("partial-") or key.startswith("snapshot-"):
            continue
        if path.is_file() and not path.is_symlink():
            data = path.read_bytes()
            relative = path.relative_to(paths["run_root"]).as_posix() if path.is_relative_to(paths["run_root"]) else path.name
            members.append({"source": key, "path": relative, "bytes": len(data), "sha256": sha256_bytes(data)})
            sources[key] = path
    members.sort(key=lambda item: str(item["path"]))
    body = {"schema_version": 1, "design_id": DESIGN_ID, "members": members, "snapshot_binaries_archived": False}
    archive_sha = json_sha256(body)
    archive = repository / ARCHIVE_ROOT / archive_sha
    _require(not archive.exists(), "terminal archive content address already exists")
    for item in members:
        target = archive / str(item["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(sources[str(item["source"])].read_bytes())
    bundle = {**body, "bundle_sha256": archive_sha}
    (archive / "bundle.json").write_bytes(canonical_json_bytes(bundle) + b"\n")
    return {
        "archive_sha256": archive_sha,
        "evidence_member_count": len(members),
        "physical_file_count": len(members) + 1,
        "snapshot_binaries_archived": False,
        "path": str(archive),
    }


def _capture_generation(
    *,
    live: kernel.CatalyticKernel0Adapter,
    full_preflight: Mapping[str, Any],
    sidecar: Any,
    paths: Mapping[str, Path],
    journal: JournalWriter,
    experiment_key: bytes,
    request_id: str,
    payload: Mapping[str, Any],
    generation_ordinal: int,
    extra_facts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    request_hash = json_sha256(payload)
    before = live.boundary_custody(preflight=full_preflight, sidecar=sidecar, boundary=f"before:{request_id}")
    _require(before.get("passed") is True, f"pre-request custody failed: {request_id}")
    journal.append(
        "request-started",
        request_id=request_id,
        facts={
            "generation_ordinal": generation_ordinal,
            "model_request_sha256": request_hash,
            "maximum_generations_for_request": 1,
            **dict(extra_facts or {}),
        },
    )

    def invoke(recorder: Callable[[bytes], None]) -> Any:
        return sidecar.guarded(
            f"multi-branch-runtime-native:{request_id}",
            lambda: _stream_raw_completion(port=live.h.PORT, payload=payload, recorder=recorder),
            timeout=1_000,
        )

    capture = capture_request_once(
        paths[f"capture-{request_id}"],
        paths[f"partial-{request_id}"],
        experiment_key=experiment_key,
        request_id=request_id,
        model_request_sha256=request_hash,
        generation_ordinal=generation_ordinal,
        invoke=invoke,
    )
    journal.append("request-captured", request_id=request_id, facts={"capture_sha256": capture["capture_sha256"]})
    after = live.boundary_custody(preflight=full_preflight, sidecar=sidecar, boundary=f"after:{request_id}")
    _require(after.get("passed") is True, f"post-request custody failed: {request_id}")
    return capture


def _delete_snapshot_record(
    *, path: Path, root_id: str, experiment_key: bytes, record_path: Path
) -> dict[str, Any]:
    present_before = path.is_file() and not path.is_symlink()
    size = 0
    sha = None
    if present_before:
        data = _regular_bytes(path, "slot snapshot", 8 * 1024 * 1024 * 1024)
        size = len(data)
        sha = sha256_bytes(data)
        path.unlink()
    deleted = not path.exists()
    body = {
        "schema_version": 1,
        "design_id": DESIGN_ID,
        "operation_id": f"{root_id}-snapshot-deletion",
        "operation_kind": "snapshot-cleanup-deletion",
        "root_id": root_id,
        "present_before_deletion": present_before,
        "snapshot_size_bytes": size,
        "snapshot_sha256": sha,
        "deleted": deleted,
        "deleted_at": _utc_now(),
        "inference_request": False,
        "model_generation": False,
    }
    return write_authenticated_record(record_path, experiment_key, "snapshot-deletion-v1", body)


def _finalize_scientific_result(
    repository: Path,
    *,
    captures: Mapping[str, Mapping[str, Any]],
    captured: Sequence[str],
    resources: Sequence[Mapping[str, Any]],
    branch_derivations: Mapping[str, Mapping[str, Any]],
    reuse_reports: Mapping[str, Mapping[str, Any]],
    readdress_records: Sequence[Mapping[str, Any]],
    snapshot_controls: Sequence[Mapping[str, Any]],
    deletion_records: Sequence[Mapping[str, Any]],
    cleanup: Mapping[str, Any],
    postflight: Mapping[str, Any],
    receipt: Mapping[str, Any],
    manifest_path: Path,
    journal_head: str,
) -> dict[str, Any]:
    snapshot_custody = (
        tuple(item["operation_id"] for item in snapshot_controls) == SNAPSHOT_CONTROL_ORDER
        and len(deletion_records) == 4
        and all(item.get("deleted") is True and item.get("present_before_deletion") is True for item in deletion_records)
        and cleanup.get("snapshot_directory_removed") is True
    )
    direct_freshness = {
        branch_id: int(normalized_capture_execution(captures[f"{branch_id}-direct"]).get("cached_prompt_tokens") or 0) == 0
        for branch_id in BRANCH_IDS
    }
    complete = (
        tuple(captured) == REQUEST_ORDER
        and tuple(item["operation_id"] for item in readdress_records) == READDRESS_ORDER
        and tuple(item["operation_id"] for item in snapshot_controls) == SNAPSHOT_CONTROL_ORDER
    )
    scoring = score_protected(
        repository,
        captures,
        completed_capture_ids=captured,
        completed_readdress_ids=[str(item["operation_id"]) for item in readdress_records],
        completed_snapshot_control_ids=[str(item["operation_id"]) for item in snapshot_controls],
        cleanup_passed=cleanup.get("passed") is True,
        postflight_passed=postflight.get("passed") is True,
    )
    accounting = account_resources(resources, readdress_records, scoring, snapshot_controls, deletion_records)
    classification = classify_result(
        scoring=scoring,
        resources=accounting,
        reuse_reports=reuse_reports,
        readdress_records=readdress_records,
        direct_freshness=direct_freshness,
        complete_panel=complete,
        snapshot_custody_passed=snapshot_custody,
        cleanup_passed=cleanup.get("passed") is True,
        postflight_passed=postflight.get("passed") is True,
    )
    return {
        "schema_version": 1,
        "family_id": FAMILY_ID,
        "design_id": DESIGN_ID,
        "status": "complete",
        "terminal_classification": classification,
        "completed_model_generations": len(captured),
        "completed_inference_requests": len(captured) + len(readdress_records),
        "completed_snapshot_controls": len(snapshot_controls),
        "retry_count": 0,
        "request_dispositions": {request_id: "captured" for request_id in REQUEST_ORDER},
        "root_readdress_dispositions": {item["operation_id"]: "captured" for item in readdress_records},
        "snapshot_control_dispositions": {item["operation_id"]: "captured" for item in snapshot_controls},
        "scoring": scoring,
        "resources": accounting,
        "runtime_native_reuse_reports": dict(reuse_reports),
        "direct_freshness": direct_freshness,
        "branch_derivation_records": {
            branch_id: {
                "record_sha256": value["record_sha256"],
                "derivation_sha256": value["derivation_sha256"],
                "complete_branch_token_sha256": value["complete_branch_token_sha256"],
                "predicted_executable_carrier_count": value["source_predicted_executable_boundary"]["predicted_executable_carrier_count"],
                "route": value["route"],
            }
            for branch_id, value in branch_derivations.items()
        },
        "root_readdress_records": list(readdress_records),
        "snapshot_custody_passed": snapshot_custody,
        "snapshot_controls": [
            {
                key: value
                for key, value in item.items()
                if key not in {"host_memory_before", "host_memory_after", "response"}
            }
            for item in snapshot_controls
        ],
        "snapshot_deletions": [dict(item) for item in deletion_records],
        "cleanup": dict(cleanup),
        "postflight": dict(postflight),
        "authority_receipt_sha256": receipt["receipt_sha256"],
        "manifest_sha256": sha256_file(manifest_path),
        "journal_head_sha256": journal_head,
        "capture_sha256": {key: value["capture_sha256"] for key, value in captures.items()},
        "claims": {
            "bounded_multi_branch_carrier": classification,
            "exact_lexical_prefix_inheritance": "LOCKED",
            "byte_exact_snapshot_restoration": "LOCKED",
            "exact_restoration": "LOCKED",
            "complete_catalytic_lifecycle": "LOCKED",
            "general_catalytic_inference": "LOCKED",
            "restart_persistent_state": "LOCKED",
            "arbitrary_task_transfer": "LOCKED",
            "superiority": "LOCKED",
            "sota": "LOCKED",
            "automatic_promotion": False,
        },
    }


def run_evaluation(args: argparse.Namespace, *, repository_root: Path | None = None) -> dict[str, Any]:
    repository = (repository_root or Path(args.repository)).resolve(strict=False)
    _require(str(args.design_id) == DESIGN_ID, "design ID changed")
    preregistration = validate_preregistration(repository)
    preregistration_file_sha = sha256_file(repository / PREREGISTRATION_PATH)
    corpus = load_public_corpus(repository)
    roots = _root_by_id(corpus)
    paths = state_paths(repository)
    _require(not paths["run_root"].exists(), "multi-branch runtime root already exists")
    _require(not paths["receipt"].exists(), "multi-branch authority receipt already exists")

    live = kernel.CatalyticKernel0Adapter(repository)
    args.expected_binary_sha256 = BINARY_SHA256
    args.expected_runtime_version = RUNTIME_VERSION
    full_preflight = live.preflight(
        args=args,
        repository_root=repository,
        run_root=paths["run_root"],
        allowed_paths=_runtime_allowed_paths(paths),
    )
    full_preflight["runtime"]["slot_save_path"] = paths["snapshots"]
    full_preflight["runtime"]["slot_save_owner"] = paths["run_root"]
    public_preflight = _public_preflight(full_preflight)
    current_commit = str(public_preflight["stable"]["head"])
    authority = build_external_authority(
        str(args.external_authority_id),
        authorized_commit=str(args.authorized_commit),
        current_commit=current_commit,
        preregistration_sha256=preregistration_file_sha,
    )
    private_root = _load_private_root(repository)
    experiment_key = _experiment_key(private_root)
    receipt = consume_authority_once(repository, private_root, authority)
    paths["run_root"].mkdir(parents=True, exist_ok=False)
    journal = JournalWriter(paths["journal"], experiment_key)
    templates = fixed_request_templates(corpus)
    manifest = {
        "schema_version": 1,
        "family_id": FAMILY_ID,
        "design_id": DESIGN_ID,
        "authorized_commit": current_commit,
        "authority_receipt_sha256": receipt["receipt_sha256"],
        "authority_id_sha256": authority["authority_id_sha256"],
        "preregistration_artifact_sha256": preregistration["artifact_sha256"],
        "preregistration_file_sha256": preregistration_file_sha,
        "public_corpus_sha256": PUBLIC_CORPUS_SHA256,
        "protected_evaluator_sha256": PROTECTED_EVALUATOR_SHA256,
        "request_order": list(REQUEST_ORDER),
        "inference_order": list(INFERENCE_ORDER),
        "readdress_order": list(READDRESS_ORDER),
        "snapshot_control_order": list(SNAPSHOT_CONTROL_ORDER),
        "request_template_sha256": templates,
        "maximum_model_generations": MAXIMUM_GENERATIONS,
        "maximum_inference_requests": MAXIMUM_INFERENCE_REQUESTS,
        "maximum_snapshot_controls": SNAPSHOT_CONTROL_COUNT,
        "materialization_requests": 0,
        "physical_slots": 1,
        "sidecar_epochs": 1,
        "catalytic_before_direct": True,
        "preflight": public_preflight,
        "retry_allowed": False,
        "raw_authority_id_persisted": False,
    }
    _exclusive_write(paths["manifest"], canonical_json_bytes(manifest) + b"\n")

    started: list[str] = []
    captured: list[str] = []
    captures: dict[str, dict[str, Any]] = {}
    resource_records: list[dict[str, Any]] = []
    branch_derivations: dict[str, dict[str, Any]] = {}
    reuse_reports: dict[str, dict[str, Any]] = {}
    snapshot_controls: list[dict[str, Any]] = []
    readdress_records: list[dict[str, Any]] = []
    deletion_records: list[dict[str, Any]] = []
    sidecar: Any | None = None
    cleanup: Mapping[str, Any] = {"passed": False}
    postflight: Mapping[str, Any] = {"passed": False}
    terminal_error: BaseException | None = None

    with RunLock(paths["run_lock"]):
        journal.append("authority-consumed", facts={"authority_id_sha256": authority["authority_id_sha256"]})
        try:
            sidecar, readiness = live.launch_sidecar(preflight=full_preflight, run_id=DESIGN_ID)
            _require(paths["snapshots"].is_dir() and not paths["snapshots"].is_symlink() and not any(paths["snapshots"].iterdir()), "slot-save directory is not safe and empty")
            _require(readiness.get("chat_template_sha256") == CHAT_TEMPLATE_SHA256, "sidecar chat-template identity changed")
            codec = SidecarPromptCodec(live.h.PORT)
            props = codec.props()
            _require(sha256_bytes(str(props.get("chat_template", "")).encode()) == CHAT_TEMPLATE_SHA256, "runtime chat-template bytes changed")
            journal.append("sidecar-ready", facts=dict(readiness))
            pool = live.create_lease_pool(1)
            generation_ordinal = 0
            with pool.lease() as lease_id:
                _require(lease_id == kernel.PHYSICAL_SLOT, "physical slot changed")
                for root_id in ROOT_IDS:
                    root = roots[root_id]
                    task_a_id = f"{root_id}-task-a"
                    _require(REQUEST_ORDER[len(started)] == task_a_id, "Task-A generation order changed")
                    prompt_text = codec.render_messages(task_a_messages(root), CHAT_TEMPLATE_KWARGS)
                    prompt_tokens = codec.tokenize(prompt_text)
                    task_a_payload = _task_a_payload(prompt_tokens, seed=derive_seed(root_id, "task-a"))
                    generation_ordinal += 1
                    started.append(task_a_id)
                    task_a_capture = _capture_generation(
                        live=live, full_preflight=full_preflight, sidecar=sidecar, paths=paths,
                        journal=journal, experiment_key=experiment_key, request_id=task_a_id,
                        payload=task_a_payload, generation_ordinal=generation_ordinal,
                        extra_facts={"request_template_sha256": templates[task_a_id], "exact_prompt_token_array": True},
                    )
                    captured.append(task_a_id)
                    captures[task_a_id] = task_a_capture
                    resource_records.append(resource_record(task_a_capture, task_a_id))
                    root_derived = derive_retained_root(task_a_capture, prompt_tokens, codec, props)
                    root_body = {
                        "schema_version": 1,
                        "family_id": FAMILY_ID,
                        "design_id": DESIGN_ID,
                        "root_id": root_id,
                        **root_derived,
                        "runtime_identity": {
                            "binary_sha256": BINARY_SHA256,
                            "model_sha256": MODEL_SHA256,
                            "chat_template_sha256": CHAT_TEMPLATE_SHA256,
                            "tokenizer_bound_to_model": True,
                            "memory_implementation": "hybrid-dsv4-full-sequence-state",
                            "n_swa": N_SWA,
                            "n_batch": N_BATCH,
                            "n_ubatch": N_UBATCH,
                            "context_checkpoints": CONTEXT_CHECKPOINTS,
                            "checkpoint_min_step": CHECKPOINT_MIN_STEP,
                        },
                    }
                    root_record = write_authenticated_record(paths[f"root-{root_id}"], experiment_key, "retained-root-v1", root_body)
                    journal.append("retained-root-authenticated", facts={
                        "root_id": root_id,
                        "record_sha256": root_record["record_sha256"],
                        "retained_root_token_sha256": root_record["retained_root_token_sha256"],
                        "retained_root_token_count": root_record["retained_root_token_count"],
                    })

                    snapshot_filename = f"{root_id}.bin"
                    save_control = save_snapshot(
                        live=live, sidecar=sidecar, path=paths[f"snapshot-{root_id}"], filename=snapshot_filename,
                        root_id=root_id, retained_root_count=int(root_record["retained_root_token_count"]),
                        experiment_key=experiment_key, record_path=paths[f"control-{root_id}-snapshot-save"],
                    )
                    snapshot_controls.append(save_control)
                    journal.append("snapshot-control-captured", request_id=save_control["operation_id"], facts={
                        "record_sha256": save_control["record_sha256"], "snapshot_sha256": save_control["snapshot_sha256"]
                    })
                    snapshot_identity = {
                        "snapshot_sha256": save_control["snapshot_sha256"],
                        "snapshot_size_bytes": save_control["snapshot_size_bytes"],
                        "save_record_sha256": save_control["record_sha256"],
                        "source_slot": kernel.PHYSICAL_SLOT,
                    }
                    suffixes = {
                        number: derive_continuation_suffix(
                            codec,
                            terminal_eog_id=int(root_record["terminal_stop_identity"]["token_id"]),
                            user_content=branch_user_content(root, number),
                        )
                        for number in (1, 2)
                    }
                    _require(suffixes[1]["suffix_token_sha256"] != suffixes[2]["suffix_token_sha256"], "branch suffixes are not distinct")
                    first_number = FIRST_BRANCH[root_id]
                    second_number = 3 - first_number
                    for number, route in ((first_number, "live-root"), (second_number, "snapshot-restored-root")):
                        branch_id = f"{root_id}-branch-{number}"
                        derivation = build_branch_derivation(
                            root_record=root_record,
                            suffix_record=suffixes[number],
                            branch_id=branch_id,
                            route=route,
                            snapshot_identity=snapshot_identity if route == "snapshot-restored-root" else None,
                        )
                        record = write_authenticated_record(
                            paths[f"derivation-{root_id}-{number}"], experiment_key, "branch-derivation-v1", derivation
                        )
                        branch_derivations[branch_id] = record
                        journal.append("branch-derivation-bound", request_id=branch_id, facts={
                            "record_sha256": record["record_sha256"],
                            "dynamic_request_sha256": record["dynamic_request_sha256"],
                            "predicted_executable_carrier_count": record["source_predicted_executable_boundary"]["predicted_executable_carrier_count"],
                            "route": route,
                        })

                    for execution_index, number in enumerate((first_number, second_number), start=1):
                        if execution_index == 2:
                            restore = restore_snapshot(
                                live=live, sidecar=sidecar, path=paths[f"snapshot-{root_id}"], filename=snapshot_filename,
                                root_id=root_id, ordinal=1, retained_root_count=int(root_record["retained_root_token_count"]),
                                expected_sha256=str(save_control["snapshot_sha256"]), experiment_key=experiment_key,
                                record_path=paths[f"control-{root_id}-snapshot-restore-1"],
                            )
                            snapshot_controls.append(restore)
                            journal.append("snapshot-control-captured", request_id=restore["operation_id"], facts={"record_sha256": restore["record_sha256"]})
                        branch_id = f"{root_id}-branch-{number}"
                        request_id = f"{branch_id}-catalytic"
                        _require(REQUEST_ORDER[len(started)] == request_id, "catalytic branch order changed")
                        derivation = branch_derivations[branch_id]
                        payload = _branch_payload(
                            derivation["complete_branch_tokens"],
                            seed=derive_seed(root_id, f"branch-{number}"),
                            cache_prompt=True,
                        )
                        _require(json_sha256(payload) == derivation["dynamic_request_sha256"], "dynamic catalytic request changed after binding")
                        generation_ordinal += 1
                        started.append(request_id)
                        capture = _capture_generation(
                            live=live, full_preflight=full_preflight, sidecar=sidecar, paths=paths,
                            journal=journal, experiment_key=experiment_key, request_id=request_id,
                            payload=payload, generation_ordinal=generation_ordinal,
                            extra_facts={"derivation_record_sha256": derivation["record_sha256"], "route": derivation["route"]},
                        )
                        captured.append(request_id)
                        captures[request_id] = capture
                        resource_records.append(resource_record(capture, request_id))
                        report = evaluate_reuse(derivation, capture)
                        reuse_reports[branch_id] = report
                        journal.append("scientific-reuse-gate-observed", request_id=request_id, facts=report)

                    restore_two = restore_snapshot(
                        live=live, sidecar=sidecar, path=paths[f"snapshot-{root_id}"], filename=snapshot_filename,
                        root_id=root_id, ordinal=2, retained_root_count=int(root_record["retained_root_token_count"]),
                        expected_sha256=str(save_control["snapshot_sha256"]), experiment_key=experiment_key,
                        record_path=paths[f"control-{root_id}-snapshot-restore-2"],
                    )
                    snapshot_controls.append(restore_two)
                    journal.append("snapshot-control-captured", request_id=restore_two["operation_id"], facts={"record_sha256": restore_two["record_sha256"]})
                    verification_suffix = derive_continuation_suffix(
                        codec,
                        terminal_eog_id=int(root_record["terminal_stop_identity"]["token_id"]),
                        user_content=verification_user_content(root_id),
                    )
                    verification_tokens = [*root_record["retained_root_tokens"], *verification_suffix["suffix_tokens"]]
                    verification_boundary = predict_runtime_native_boundary(
                        retained_root_tokens=root_record["retained_root_tokens"],
                        requested_tokens=verification_tokens,
                        retained_pos_min=int(root_record["retained_root_token_count"]) - 1,
                        retained_pos_next=int(root_record["retained_root_token_count"]),
                        n_swa=N_SWA,
                        memory_removal_capability=MEMORY_REMOVAL_CAPABILITY,
                    )
                    readdress_payload = _branch_payload(
                        verification_tokens,
                        seed=derive_seed(root_id, "branch-1"),
                        cache_prompt=True,
                        n_predict=0,
                    )
                    readdress_id = f"{root_id}-root-readdress"
                    before_readdress = live.boundary_custody(preflight=full_preflight, sidecar=sidecar, boundary=f"before:{readdress_id}")
                    _require(before_readdress.get("passed") is True, "root-readdress pre-request custody failed")
                    journal.append("root-readdress-started", request_id=readdress_id, facts={
                        "request_sha256": json_sha256(readdress_payload),
                        "predicted_executable_carrier_count": verification_boundary["predicted_executable_carrier_count"],
                        "n_predict": 0,
                    })
                    readdress_execution = sidecar.guarded(
                        f"multi-branch-runtime-native:{readdress_id}",
                        lambda: _stream_raw_completion(port=live.h.PORT, payload=readdress_payload, recorder=lambda _line: None),
                        timeout=1_000,
                    )
                    readdress = root_readdress_record(
                        readdress_execution,
                        root_id=root_id,
                        payload=readdress_payload,
                        predicted_boundary=int(verification_boundary["predicted_executable_carrier_count"]),
                        snapshot_sha256=str(save_control["snapshot_sha256"]),
                    )
                    readdress_record = write_authenticated_record(
                        paths[f"readdress-{root_id}"], experiment_key, "root-readdress-v1", readdress
                    )
                    readdress_records.append(readdress_record)
                    journal.append("root-readdress-captured", request_id=readdress_id, facts={
                        "record_sha256": readdress_record["record_sha256"],
                        "root_readdress_gate": readdress_record["root_readdress_gate"],
                        "continue_panel": True,
                    })
                    after_readdress = live.boundary_custody(preflight=full_preflight, sidecar=sidecar, boundary=f"after:{readdress_id}")
                    _require(after_readdress.get("passed") is True, "root-readdress post-request custody failed")

                    for number in (1, 2):
                        branch_id = f"{root_id}-branch-{number}"
                        request_id = f"{branch_id}-direct"
                        _require(REQUEST_ORDER[len(started)] == request_id, "direct branch order changed")
                        derivation = branch_derivations[branch_id]
                        direct_payload = _branch_payload(
                            derivation["complete_branch_tokens"],
                            seed=derive_seed(root_id, f"branch-{number}"),
                            cache_prompt=False,
                        )
                        _require(direct_payload["prompt"] == derivation["complete_branch_tokens"], "direct and catalytic token arrays differ")
                        generation_ordinal += 1
                        started.append(request_id)
                        direct_capture = _capture_generation(
                            live=live, full_preflight=full_preflight, sidecar=sidecar, paths=paths,
                            journal=journal, experiment_key=experiment_key, request_id=request_id,
                            payload=direct_payload, generation_ordinal=generation_ordinal,
                            extra_facts={"cache_prompt": False, "same_information_control": True, "branch_derivation_record_sha256": derivation["record_sha256"]},
                        )
                        captured.append(request_id)
                        captures[request_id] = direct_capture
                        resource_records.append(resource_record(direct_capture, request_id))
                        direct_cached = int(normalized_capture_execution(direct_capture).get("cached_prompt_tokens") or 0)
                        journal.append("direct-freshness-observed", request_id=request_id, facts={"cached_prompt_tokens": direct_cached, "freshness_gate": direct_cached == 0, "continue_panel": True})
            _require(tuple(started) == REQUEST_ORDER and tuple(captured) == REQUEST_ORDER, "execution did not complete frozen generation order")
            _require(tuple(item["operation_id"] for item in readdress_records) == READDRESS_ORDER, "root-readdress order changed")
            _require(tuple(item["operation_id"] for item in snapshot_controls) == SNAPSHOT_CONTROL_ORDER, "snapshot-control order changed")
            _require(len(captured) == MAXIMUM_GENERATIONS and len(captured) + len(readdress_records) == MAXIMUM_INFERENCE_REQUESTS, "execution ceilings changed")
        except BaseException as exc:
            terminal_error = exc
        finally:
            try:
                lifecycle_cleanup = live.cleanup(sidecar=sidecar, preflight=full_preflight)
            except BaseException as exc:
                lifecycle_cleanup = {"passed": False, "error_sha256": sha256_bytes(str(exc).encode())}
                if terminal_error is None:
                    terminal_error = exc
            snapshot_deletion_passed = True
            try:
                for root_id in ROOT_IDS:
                    deletion = _delete_snapshot_record(
                        path=paths[f"snapshot-{root_id}"], root_id=root_id,
                        experiment_key=experiment_key, record_path=paths[f"delete-{root_id}"],
                    )
                    deletion_records.append(deletion)
                    snapshot_deletion_passed = snapshot_deletion_passed and deletion["deleted"] is True and deletion["present_before_deletion"] is True
                    journal.append("snapshot-deleted", request_id=deletion["operation_id"], facts={
                        "record_sha256": deletion["record_sha256"], "deleted": deletion["deleted"],
                    })
                if paths["snapshots"].is_dir() and not any(paths["snapshots"].iterdir()):
                    paths["snapshots"].rmdir()
                snapshot_directory_removed = not paths["snapshots"].exists()
                snapshot_deletion_passed = snapshot_deletion_passed and snapshot_directory_removed
            except BaseException as exc:
                snapshot_directory_removed = not paths["snapshots"].exists()
                snapshot_deletion_passed = False
                if terminal_error is None:
                    terminal_error = exc
            cleanup = {
                **dict(lifecycle_cleanup),
                "snapshot_deletion_passed": snapshot_deletion_passed,
                "snapshot_directory_removed": snapshot_directory_removed,
                "passed": lifecycle_cleanup.get("passed") is True and snapshot_deletion_passed,
            }
            try:
                postflight = live.postflight(preflight=full_preflight)
            except BaseException as exc:
                postflight = {"passed": False, "error_sha256": sha256_bytes(str(exc).encode())}
                if terminal_error is None:
                    terminal_error = exc

        if terminal_error is None:
            try:
                result = _finalize_scientific_result(
                    repository,
                    captures=captures,
                    captured=captured,
                    resources=resource_records,
                    branch_derivations=branch_derivations,
                    reuse_reports=reuse_reports,
                    readdress_records=readdress_records,
                    snapshot_controls=snapshot_controls,
                    deletion_records=deletion_records,
                    cleanup=cleanup,
                    postflight=postflight,
                    receipt=receipt,
                    manifest_path=paths["manifest"],
                    journal_head=journal.previous,
                )
            except BaseException as exc:
                terminal_error = exc
        if terminal_error is not None:
            result = {
                "schema_version": 1,
                "family_id": FAMILY_ID,
                "design_id": DESIGN_ID,
                "status": "inconclusive",
                "terminal_classification": "INCONCLUSIVE",
                "completed_model_generations": len(captured),
                "completed_inference_requests": len(captured) + len(readdress_records),
                "completed_snapshot_controls": len(snapshot_controls),
                "retry_count": 0,
                "started_requests": list(started),
                "captured_requests": list(captured),
                "failure": {"type": type(terminal_error).__name__, "message_sha256": sha256_bytes(str(terminal_error).encode())},
                "cleanup": dict(cleanup),
                "postflight": dict(postflight),
                "authority_receipt_sha256": receipt["receipt_sha256"],
                "manifest_sha256": sha256_file(paths["manifest"]),
                "journal_head_sha256": journal.previous,
                "claims": {"general_catalytic_inference": "LOCKED", "exact_restoration": "LOCKED", "automatic_promotion": False},
            }
        journal.append("terminal-result-bound", facts={
            "status": result["status"], "terminal_classification": result["terminal_classification"],
            "completed_model_generations": result["completed_model_generations"],
        })
        journal.close()
        result["journal_head_sha256"] = journal.previous
        _exclusive_write(paths["result"], canonical_json_bytes(result) + b"\n")
        closure_document = {
            "schema_version": 1,
            "design_id": DESIGN_ID,
            "status": result["status"],
            "result_sha256": sha256_file(paths["result"]),
            "manifest_sha256": sha256_file(paths["manifest"]),
            "authority_receipt_sha256": receipt["receipt_sha256"],
            "journal_sha256": sha256_file(paths["journal"]),
            "journal_head_sha256": journal.previous,
            "run_lock_owned_during_terminal_write": True,
            "retry_allowed": False,
            "snapshot_directory_absent": not paths["snapshots"].exists(),
        }
        _exclusive_write(paths["closure"], canonical_json_bytes(closure_document) + b"\n")

    archive = _archive_terminal(repository, paths)
    return {**result, "closure_sha256": sha256_file(paths["closure"]), "archive": archive}


def _source_text(repository: Path) -> str:
    return (repository / "scripts/holostate_v1_multi_branch_runtime_native_carrier_evaluation.py").read_text(
        encoding="utf-8"
    )


def validate_static(repository: Path) -> dict[str, Any]:
    preregistration = validate_preregistration(repository)
    corpus = load_public_corpus(repository)
    custody = protected_evaluator_custody(repository)
    source_bindings = _verify_source_bindings(repository)
    paths = state_paths(repository)
    source_text = _source_text(repository)
    roots = corpus["roots"]
    branch_ids = [str(branch["branch_id"]) for root in roots for branch in root["branches"]]
    reasoning_types = [str(branch["reasoning_type"]) for root in roots for branch in root["branches"]]
    public_text = canonical_json_text(corpus)

    _require(len(roots) == 4 and tuple(root["root_id"] for root in roots) == ROOT_IDS, "root geometry changed")
    _require(len(branch_ids) == len(set(branch_ids)) == 8 and tuple(branch_ids) == BRANCH_IDS, "branch geometry changed")
    _require(len(set(reasoning_types)) >= 4, "branch reasoning diversity collapsed")
    _require(not any(identifier in public_text for identifier in predecessor.PAIR_IDS), "retired four-pair panel entered corpus")
    _require(custody["ignored"] is True and custody["tracked"] is False, "protected evaluator custody changed")
    _require(
        all(key not in public_text for key in ("task_a_answer", "branch_answers", "task_a_state_required_concepts")),
        "protected evaluator keys entered the public corpus",
    )
    _require(len(REQUEST_ORDER) == MAXIMUM_GENERATIONS == 20, "generation ceiling changed")
    _require(len(INFERENCE_ORDER) == MAXIMUM_INFERENCE_REQUESTS == 24, "inference-request ceiling changed")
    _require(len(SNAPSHOT_CONTROL_ORDER) == SNAPSHOT_CONTROL_COUNT == 12, "snapshot-control ceiling changed")
    _require(sum(item.endswith("snapshot-save") for item in SNAPSHOT_CONTROL_ORDER) == SNAPSHOT_SAVE_COUNT == 4, "snapshot-save count changed")
    _require(sum("snapshot-restore" in item for item in SNAPSHOT_CONTROL_ORDER) == SNAPSHOT_RESTORE_COUNT == 8, "snapshot-restore count changed")
    _require(not any("material" in item.casefold() for item in INFERENCE_ORDER), "materialization entered execution order")
    _require(preregistration["execution"]["retry_paths"] == 0 and preregistration["execution"]["outcome_early_stop"] is False, "retry or early stop entered design")
    _require(preregistration["root_token_array_law"]["prompt_type"] == "exact integer token array", "exact-token Task-A law changed")
    _require(preregistration["root_token_array_law"]["visible_content_retokenization_forbidden"] is True, "visible retokenization became admissible")
    _require(preregistration["strict_extension_law"]["catalytic_and_direct_complete_token_arrays_identical"] is True, "same-token control law changed")
    _require(preregistration["strict_extension_law"]["observed_cache_telemetry_used_for_prediction"] is False, "telemetry entered prediction")
    _require(preregistration["source_predicted_boundary_law"]["false_gate_continues_panel"] is True, "false scientific gate became an early stop")
    topology = preregistration["snapshot_topology"]
    _require(topology["physical_slots"] == 1 and topology["sidecar_epochs"] == 1, "minimal topology changed")
    _require(topology["snapshot_controls_are_inference_requests"] is False, "snapshot controls became inference")
    _require(topology["snapshot_controls_are_model_generations"] is False, "snapshot controls became generations")
    _require(preregistration["direct_controls"]["cache_prompt"] is False and preregistration["direct_controls"]["cached_prompt_tokens_required"] == 0, "direct freshness law changed")
    _require(preregistration["resource_law"]["snapshot_resources_reported_separately"] is True, "snapshot costs disappeared")
    _require(preregistration["protected_scoring"]["required_before_open"] == {
        "captures": 20,
        "root_readdresses": 4,
        "snapshot_controls": 12,
        "cleanup_passed": True,
        "postflight_passed": True,
    }, "protected evaluator delay gate changed")
    _require("route != \"direct\"" in source_text and "cache_prompt=False" in source_text, "route cache construction changed")
    _require("\"continue_panel\": True" in source_text, "false-gate continuation is absent")
    _require("completion == 0" in source_text and "n_predict=0" in source_text, "zero-output readdress law is absent")
    _require("direct_payload[\"prompt\"] == derivation[\"complete_branch_tokens\"]" in source_text, "direct/catalytic token equality check is absent")
    _require("_load_protected_evaluator_after_terminal_gates" in inspect.getsource(score_protected), "protected scoring bypasses delayed loader")
    _require("generated[:-1]" in inspect.getsource(derive_retained_root), "retained-root terminal law changed")
    _require("\"visible_content_retokenized\": False" in inspect.getsource(derive_retained_root), "retokenization became admissible")
    _require("\"observed_cache_telemetry_used_for_prediction\": False" in inspect.getsource(evaluate_reuse), "observed telemetry entered prediction")
    _require("\"snapshot_binaries_archived\": False" in inspect.getsource(_archive_terminal), "snapshot binaries entered archive")
    _require("snapshot_deletion_passed" in inspect.getsource(run_evaluation), "snapshot cleanup is not terminally bound")
    _require(not paths["run_root"].exists(), "runtime root exists before execution")
    _require(not paths["receipt"].exists(), "authority receipt exists before execution")
    _require(not (repository / ARCHIVE_ROOT).exists(), "archive exists before execution")
    _require(len((repository / "lab/results.jsonl").read_text(encoding="utf-8").splitlines()) == SOURCE_RECORD_LINE, "result ledger changed during preparation")

    proofs = {
        "retired_panel_absent": True,
        "four_roots_eight_branches": True,
        "protected_values_absent_from_public_construction": True,
        "authenticated_exact_emitted_tokens_required": True,
        "visible_content_retokenization_rejected": True,
        "only_source_proven_terminal_eog_excluded": True,
        "strict_token_array_extensions": True,
        "catalytic_direct_token_arrays_identical": True,
        "boundary_bound_before_branch_contact": True,
        "observed_telemetry_excluded_from_prediction": True,
        "live_root_branch_count": 4,
        "snapshot_restored_branch_count": 4,
        "nonempty_zero_output_readdress_count": 4,
        "snapshot_controls_are_not_inference": True,
        "maximum_generations": MAXIMUM_GENERATIONS,
        "maximum_inference_requests": MAXIMUM_INFERENCE_REQUESTS,
        "snapshot_save_count": SNAPSHOT_SAVE_COUNT,
        "snapshot_restore_count": SNAPSHOT_RESTORE_COUNT,
        "materialization_requests": 0,
        "retry_paths": 0,
        "false_science_continues_panel": True,
        "direct_requests_cache_disabled_and_zero_reuse_required": True,
        "actual_root_readdress_cost_included": True,
        "snapshot_costs_reported_separately": True,
        "protected_evaluator_delayed": True,
        "runtime_artifacts_absent": True,
    }
    return {
        "status": "pass",
        "family_id": FAMILY_ID,
        "design_id": DESIGN_ID,
        "source_bindings": source_bindings,
        "artifact_sha256": preregistration["artifact_sha256"],
        "preregistration_file_sha256": sha256_file(repository / PREREGISTRATION_PATH),
        "corpus_binding_file_sha256": sha256_file(repository / CORPUS_BINDING_PATH),
        "public_corpus_sha256": PUBLIC_CORPUS_SHA256,
        "protected_evaluator_sha256": PROTECTED_EVALUATOR_SHA256,
        "root_ids": list(ROOT_IDS),
        "branch_ids": list(BRANCH_IDS),
        "request_order": list(REQUEST_ORDER),
        "inference_order": list(INFERENCE_ORDER),
        "snapshot_control_order": list(SNAPSHOT_CONTROL_ORDER),
        "seeds": preregistration["execution"]["seeds"],
        "request_template_sha256": fixed_request_templates(corpus),
        "bindings": {name: value["sha256"] for name, value in preregistration["bindings"].items()},
        "proofs": proofs,
        "authority_receipt_absent": True,
        "sidecar_launches": 0,
        "model_requests_issued": 0,
        "model_generations": 0,
        "captures_created": 0,
        "results_created": 0,
        "archives_created": 0,
        "ledger_records_appended": 0,
        "next_action": "AUTHORIZE_ONE_LIVE_MULTI_BRANCH_RUNTIME_NATIVE_CARRIER_EVALUATION",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write-preregistration", "validate", "run"))
    parser.add_argument("--repository", required=True)
    parser.add_argument("--binary")
    parser.add_argument("--model")
    parser.add_argument("--design-id", default=DESIGN_ID)
    parser.add_argument("--external-authority-id")
    parser.add_argument("--authorized-commit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository = Path(args.repository).resolve(strict=False)
    try:
        if args.action == "write-preregistration":
            result: Any = {"status": "written", "path": str(write_preregistration(repository))}
        elif args.action == "validate":
            result = validate_static(repository)
        else:
            _require(
                all((args.binary, args.model, args.external_authority_id, args.authorized_commit)),
                "live run arguments are incomplete",
            )
            result = run_evaluation(args, repository_root=repository)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(canonical_json_text({"status": "fail", "error": str(exc)}))
        return 1
    print(canonical_json_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
