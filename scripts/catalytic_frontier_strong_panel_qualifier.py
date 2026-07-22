#!/usr/bin/env python3
"""Direct-first qualification for two strong 16-branch catalytic panels.

The qualifier intentionally performs no carrier save, restore, snapshot, or
cache-enabled branch. It freezes two panel extensions and admits a panel to
later carrier testing only when all sixteen cache-disabled direct controls are
correct under the same checkpoint-free launch intended for the carrier run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

import catalytic_frontier_checkpoint_control as checkpoint_control
import catalytic_frontier_fanout as fanout
import catalytic_frontier_harness as harness


ROOT_IDS = ("mb-runtime-datacenter-01", "mb-runtime-coldchain-02")
PANEL_SIZE = 16
DIRECT_QUALIFICATION_THRESHOLD = 16
PANEL_ORDERS = {
    "mb-runtime-datacenter-01": tuple(range(1, PANEL_SIZE + 1)),
    "mb-runtime-coldchain-02": (2, 1, *range(3, PANEL_SIZE + 1)),
}
PANEL_EXTENSIONS: dict[str, list[dict[str, Any]]] = {
    "mb-runtime-datacenter-01": [
        {
            "question": "If the leader move starts at 21:58 and takes four minutes, when is it first complete?",
            "choices": {"A": "22:04.", "B": "22:06.", "C": "22:02.", "D": "22:20."},
            "answer": "C",
        },
        {
            "question": "How many of the battery room's twelve minutes remain usable before the reserved final four minutes begin?",
            "choices": {"A": "Four minutes.", "B": "Eight minutes.", "C": "Twelve minutes.", "D": "Sixteen minutes."},
            "answer": "B",
        },
        {
            "question": "How long does the East breaker inspection itself take?",
            "choices": {"A": "Three minutes.", "B": "Four minutes.", "C": "Six minutes.", "D": "Twenty minutes."},
            "answer": "D",
        },
        {
            "question": "How long does promotion of a replica on an already healthy row take?",
            "choices": {"A": "Three minutes.", "B": "Five minutes.", "C": "Six minutes.", "D": "Twenty minutes."},
            "answer": "A",
        },
        {
            "question": "What is the direct effect of the 22:01 cooling alarm?",
            "choices": {
                "A": "It disables both West rows.",
                "B": "It electrically isolates East.",
                "C": "It disables W2 but leaves W1 available.",
                "D": "It drains the replication queue.",
            },
            "answer": "C",
        },
        {
            "question": "Where must the database leader run before East isolation may begin?",
            "choices": {"A": "E1.", "B": "W1.", "C": "E2.", "D": "W2."},
            "answer": "B",
        },
        {
            "question": "Which replica-creation restriction applies after a source row is electrically isolated?",
            "choices": {
                "A": "Only a W2 source may be copied.",
                "B": "A new replica must be created immediately.",
                "C": "The restriction disappears during maintenance.",
                "D": "No new replica may be created from that isolated source.",
            },
            "answer": "D",
        },
        {
            "question": "What scheduled maintenance work is assigned to Feed West in the evidence?",
            "choices": {
                "A": "A battery-room replacement.",
                "B": "A W1 breaker inspection.",
                "C": "A replication-controller upgrade.",
                "D": "No scheduled work.",
            },
            "answer": "D",
        },
    ],
    "mb-runtime-coldchain-02": [
        {
            "question": "When is the receiving nurse available according to the evidence?",
            "choices": {
                "A": "Only after 09:35.",
                "B": "Continuously from 09:00 to 09:35.",
                "C": "From 09:00 to 09:12 and again after 09:35.",
                "D": "Only from 09:20 to 09:28.",
            },
            "answer": "C",
        },
        {
            "question": "How long does joint seal inspection take for each container?",
            "choices": {"A": "Two minutes.", "B": "Four minutes.", "C": "Five minutes.", "D": "Twelve minutes."},
            "answer": "B",
        },
        {
            "question": "How long does loading the sealed chilled tote take?",
            "choices": {"A": "Two minutes.", "B": "Four minutes.", "C": "Twelve minutes.", "D": "Five minutes."},
            "answer": "D",
        },
        {
            "question": "How long does loading Coral take?",
            "choices": {"A": "Two minutes.", "B": "Four minutes.", "C": "Five minutes.", "D": "Twelve minutes."},
            "answer": "A",
        },
        {
            "question": "When is the hospital refrigerator ready?",
            "choices": {"A": "09:08.", "B": "09:12.", "C": "09:20.", "D": "09:28."},
            "answer": "C",
        },
        {
            "question": "How long is travel from the clinic to the hospital for either vehicle?",
            "choices": {"A": "Five minutes.", "B": "Twelve minutes.", "C": "Eighteen minutes.", "D": "Twenty-five minutes."},
            "answer": "B",
        },
        {
            "question": "When is the frozen-storage technician ready?",
            "choices": {"A": "09:08.", "B": "09:12.", "C": "09:20.", "D": "09:28."},
            "answer": "D",
        },
        {
            "question": "How does the evidence classify the tote logger reading of 7.6 degrees at 09:03?",
            "choices": {
                "A": "Valid and rising normally.",
                "B": "Invalid because it exceeds 8 degrees.",
                "C": "Irrelevant because only paperwork matters.",
                "D": "Proof that Coral may enter the chilled van.",
            },
            "answer": "A",
        },
    ],
}


def strong_panel_for(root: Mapping[str, Any]) -> list[dict[str, Any]]:
    root_id = str(root["root_id"])
    harness.require(root_id in PANEL_EXTENSIONS, f"unsupported strong-panel root: {root_id}")
    original = fanout.panel_for(root)
    panel = [*original, *PANEL_EXTENSIONS[root_id]]
    harness.require(len(panel) == PANEL_SIZE, "strong panel must contain exactly sixteen branches")
    harness.require(len({str(item["question"]) for item in panel}) == PANEL_SIZE, "strong-panel questions must be distinct")
    harness.require(
        set(PANEL_ORDERS[root_id]) == set(range(1, PANEL_SIZE + 1)),
        "strong-panel order must cover each branch exactly once",
    )
    return panel


def classify_direct_panel(*, correct: int, total: int) -> str:
    harness.require(total == PANEL_SIZE, "direct qualification panel size drifted")
    return "exact-direct-baseline-qualified" if correct == DIRECT_QUALIFICATION_THRESHOLD else "direct-baseline-rejected"


def _generated_hash(record: Mapping[str, Any], label: str) -> str:
    value = record["execution"].get("generated_token_sha256")
    harness.require(isinstance(value, str) and len(value) == 64, f"{label} lacks generated-token evidence")
    return value


def _panel_hash(panel: list[dict[str, Any]]) -> str:
    return harness.sha256_bytes(harness.carrier.canonical_json_bytes(panel))


def evaluate_panel(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    root: Mapping[str, Any],
    baseline_private: int | None,
    panel_override: list[dict[str, Any]] | None = None,
    branch_order_override: tuple[int, ...] | None = None,
) -> dict[str, Any]:
    root_id = str(root["root_id"])
    panel = strong_panel_for(root) if panel_override is None else panel_override
    branch_order = PANEL_ORDERS[root_id] if branch_order_override is None else branch_order_override
    harness.require(len(panel) == PANEL_SIZE, "direct qualification panel must contain sixteen branches")
    harness.require(len({str(item["question"]) for item in panel}) == PANEL_SIZE, "direct panel questions must be distinct")
    harness.require(
        set(branch_order) == set(range(1, PANEL_SIZE + 1)),
        "direct panel order must cover each branch exactly once",
    )
    prompt_text = codec.render_messages(
        harness.carrier.task_a_messages(root),
        harness.carrier.CHAT_TEMPLATE_KWARGS,
    )
    prompt_tokens = codec.tokenize(prompt_text)
    task_payload = harness.carrier._task_a_payload(
        prompt_tokens,
        seed=fanout.derive_seed(root_id, "task-a"),
    )
    task_a = harness.run_completion(sidecar, f"{root_id}:qualifier:task-a", task_payload)
    parsed = harness.carrier.parse_task_a_output(task_a["content"])
    harness.require(parsed["answer"] == harness.EXPECTED[root_id]["task_a"], "qualifier Task-A answer is incorrect")
    retained = harness.carrier.derive_retained_root(
        harness.root_capture(task_a, task_payload),
        prompt_tokens,
        codec,
        props,
    )

    correct = 0
    fresh_model_tokens = 0
    wall_seconds = 0.0
    observed_answers: list[str] = []
    branches: list[dict[str, Any]] = []
    input_digest = hashlib.sha256()
    generated_digest = hashlib.sha256()
    for number in branch_order:
        spec = panel[number - 1]
        suffix = harness.carrier.derive_continuation_suffix(
            codec,
            terminal_eog_id=int(retained["terminal_stop_identity"]["token_id"]),
            user_content=fanout.branch_user_content(spec),
        )
        tokens = [*retained["retained_root_tokens"], *suffix["suffix_tokens"]]
        payload = harness.carrier._branch_payload(
            tokens,
            seed=fanout.derive_seed(root_id, f"branch-{number}"),
            cache_prompt=False,
        )
        record = harness.run_completion(sidecar, f"{root_id}:qualifier:branch-{number}:direct", payload)
        answer = harness.carrier.parse_branch_output(record["content"])
        harness.require(record["cached_prompt_tokens"] == 0, f"direct qualifier branch {number} reused cache")
        is_correct = answer == spec["answer"]
        correct += int(is_correct)
        fresh_model_tokens += int(record["fresh_model_tokens"])
        wall_seconds += float(record["wall_seconds"])
        observed_answers.append(answer)
        token_bytes = harness.carrier.canonical_json_bytes(tokens)
        input_digest.update(token_bytes)
        input_token_hash = harness.sha256_bytes(token_bytes)
        generated_hash = _generated_hash(record, f"{root_id} direct branch {number}")
        generated_digest.update(generated_hash.encode())
        branches.append(
            {
                "branch": number,
                "answer": answer,
                "expected": spec["answer"],
                "correct": is_correct,
                "input_token_sha256": input_token_hash,
                "generated_token_sha256": generated_hash,
                **harness.token_summary(record),
            }
        )

    expected_sequence = "".join(str(panel[number - 1]["answer"]) for number in branch_order)
    observed_sequence = "".join(observed_answers)
    classification = classify_direct_panel(correct=correct, total=len(branch_order))
    return {
        "root_id": root_id,
        "classification": classification,
        "qualified": classification == "exact-direct-baseline-qualified",
        "panel_sha256": _panel_hash(panel),
        "panel_size": len(panel),
        "branch_order": list(branch_order),
        "expected_sequence": expected_sequence,
        "observed_sequence": observed_sequence,
        "correct": correct,
        "input_token_digest_sha256": input_digest.hexdigest(),
        "generated_token_hash_digest_sha256": generated_digest.hexdigest(),
        "fresh_model_tokens": fresh_model_tokens,
        "wall_seconds": wall_seconds,
        "all_branches_cache_disabled": all(item["cached_prompt_tokens"] == 0 for item in branches),
        "task_a": harness.token_summary(task_a),
        "retained_root_tokens_for_future_comparison": int(retained["retained_root_token_count"]),
        "branches": branches,
        "resources": harness.process_resources(sidecar, baseline_private),
    }


def evaluate(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    roots: Mapping[str, Mapping[str, Any]],
    baseline_private: int | None,
) -> dict[str, Any]:
    panels = [
        evaluate_panel(
            sidecar=sidecar,
            codec=codec,
            props=props,
            root=roots[root_id],
            baseline_private=baseline_private,
        )
        for root_id in ROOT_IDS
    ]
    qualified = all(bool(panel["qualified"]) for panel in panels)
    return {
        "status": "complete",
        "mechanism": "direct-only-strong-panel-qualification",
        "verdict": "accept" if qualified else "reject",
        "classification": "both-direct-panels-qualified" if qualified else "one-or-more-direct-panels-rejected",
        "qualification_threshold": {"correct": DIRECT_QUALIFICATION_THRESHOLD, "total": PANEL_SIZE},
        "model": "Agents-A1",
        "carrier_operations": 0,
        "snapshot_operations": 0,
        "cache_enabled_branches": 0,
        "panels": panels,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, default=harness.DEFAULT_BINARY)
    parser.add_argument("--model", type=Path, default=harness.DEFAULT_MODEL)
    parser.add_argument("--ctx-checkpoints", type=int, choices=(0, 8), default=checkpoint_control.FROZEN_CONTEXT_CHECKPOINTS)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--server-log-output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    binary = args.binary.resolve(strict=True)
    model = args.model.resolve(strict=True)
    repository = Path(__file__).resolve().parents[1]
    corpus = harness.carrier.load_public_corpus(repository)
    roots = {str(item["root_id"]): item for item in corpus["roots"]}
    evaluator, live_contract = harness.load_discovery_sidecar_contract()
    stable_pids = harness.live_runtime.require_stable()
    harness.require(len(stable_pids) == 1, "strong-panel qualifier requires the sole stable listener")
    harness.require(not harness.live_runtime.listener_pids(harness.live_runtime.PORT), "frontier port is occupied")
    state_root = Path(tempfile.mkdtemp(prefix="neo3000-strong-panel-qualifier-"))
    sidecar: Any | None = None
    result: dict[str, Any] | None = None
    cleanup: Mapping[str, Any] | None = None
    error: BaseException | None = None
    if args.server_log_output is not None:
        os.environ["LLAMA_ARG_LOG_VERBOSITY"] = "1000"
        os.environ["LLAMA_SERVER_SLOTS_DEBUG"] = "1"
    try:
        sidecar = checkpoint_control.ScopedCheckpointDiscoverySidecar(
            binary,
            model,
            evaluator,
            live_contract,
            detached=False,
            stable_pids=set(stable_pids),
            state_root=state_root,
            advisory_wddm=True,
            context_checkpoints=args.ctx_checkpoints,
        )
        readiness = sidecar.launch()
        baseline_private = None
        process_memory = readiness.get("process_memory")
        if isinstance(process_memory, Mapping) and isinstance(process_memory.get("private_bytes"), int):
            baseline_private = int(process_memory["private_bytes"])
        codec = harness.carrier.SidecarPromptCodec(harness.live_runtime.PORT)
        result = evaluate(
            sidecar=sidecar,
            codec=codec,
            props=codec.props(),
            roots=roots,
            baseline_private=baseline_private,
        )
        result["launch_configuration"] = readiness.get("launch_configuration")
        result["readiness"] = {
            "pid": readiness.get("pid"),
            "readiness_seconds": readiness.get("readiness_seconds"),
            "binary": readiness.get("binary"),
            "model": readiness.get("model"),
            "baseline_private_bytes": baseline_private,
            "launch_configuration": readiness.get("launch_configuration"),
        }
    except BaseException as exc:
        error = exc
    finally:
        cleanup = dict(harness.live_runtime.safe_sidecar_cleanup(sidecar))
        if args.server_log_output is not None:
            trace_record: dict[str, Any] = {"requested": str(args.server_log_output)}
            try:
                log_path = Path(str(sidecar.readiness.get("log_path"))) if sidecar is not None else None
                if log_path is None or not log_path.is_file():
                    raise FileNotFoundError("sidecar log is unavailable")
                args.server_log_output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(log_path, args.server_log_output)
                trace_record.update(copied=True, bytes=args.server_log_output.stat().st_size)
            except BaseException as exc:
                trace_record.update(copied=False, error=f"{type(exc).__name__}: {exc}")
            cleanup["server_log_copy"] = trace_record
        shutil.rmtree(state_root, ignore_errors=True)

    if error is not None:
        print(
            json.dumps(
                {
                    "status": "engineering-failure",
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "cleanup": cleanup,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    harness.require(result is not None, "strong-panel qualifier result is missing")
    result["cleanup"] = cleanup
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
