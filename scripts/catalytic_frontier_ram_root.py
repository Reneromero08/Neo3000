#!/usr/bin/env python3
"""Narrow live discriminator for the bounded native RAM-root carrier."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import catalytic_frontier_fanout as fanout
import catalytic_frontier_harness as harness
import catalytic_frontier_sustained as sustained


DEFAULT_BINARY = Path("build/candidate/bin/Release/llama-server.exe")
ROOT_ID = sustained.ROOT_ID
ROOT_BOUNDARIES = ("completed-generation", "prompt-only")


def validate_root_response(
    response: Mapping[str, Any],
    *,
    action: str,
    expected: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    harness.require(response.get("action") == action, f"RAM-root action mismatch for {action}")
    harness.require(response.get("root_id") == ROOT_ID, f"RAM-root identity mismatch for {action}")
    harness.require(type(response.get("id_slot")) is int, f"RAM-root slot missing for {action}")
    for key in ("n_tokens", "n_bytes", "n_checkpoints"):
        harness.require(type(response.get(key)) is int, f"RAM-root {key} missing for {action}")
        harness.require(int(response[key]) >= 0, f"RAM-root {key} is negative for {action}")
    harness.require(int(response["n_tokens"]) > 0, f"RAM-root is empty for {action}")
    harness.require(int(response["n_bytes"]) > 0, f"RAM-root has no state bytes for {action}")
    if expected is not None:
        for key in ("root_id", "n_tokens", "n_bytes", "n_checkpoints"):
            harness.require(response.get(key) == expected.get(key), f"RAM-root {key} changed at {action}")
    timings = response.get("timings")
    harness.require(
        isinstance(timings, Mapping) and isinstance(timings.get("root_ms"), (int, float)),
        f"RAM-root timing missing for {action}",
    )
    return {
        "action": action,
        "root_id": response["root_id"],
        "id_slot": response["id_slot"],
        "id_slot_source": response.get("id_slot_source"),
        "n_tokens": response["n_tokens"],
        "n_bytes": response["n_bytes"],
        "n_checkpoints": response["n_checkpoints"],
        "server_root_ms": timings["root_ms"],
    }


def classify_live_restore(
    *,
    expected: str,
    live_answer: str,
    restored_answer: str,
    direct_answer: str,
) -> str:
    if direct_answer != expected:
        return "direct-control-failed"
    if live_answer == expected and restored_answer != expected:
        return "restore-divergence"
    if live_answer != expected and live_answer == restored_answer:
        return "live-prefix-state-divergence"
    if live_answer != expected and restored_answer == expected:
        return "live-route-only-divergence"
    if live_answer == expected and restored_answer == expected:
        return "no-live-or-restore-divergence"
    return "multiple-cached-route-divergence"


def prompt_root_materialization_payload(prompt_tokens: Sequence[int]) -> dict[str, Any]:
    return harness.carrier._branch_payload(
        prompt_tokens,
        seed=fanout.derive_seed(ROOT_ID, "prompt-root-materialize"),
        cache_prompt=False,
        n_predict=0,
    )


def run_branch(
    *,
    sidecar: Any,
    codec: Any,
    retained: Mapping[str, Any],
    tick: int,
    route: str,
    cache_prompt: bool,
) -> dict[str, Any]:
    spec = sustained.branch_spec(tick)
    suffix = harness.carrier.derive_continuation_suffix(
        codec,
        terminal_eog_id=int(retained["terminal_stop_identity"]["token_id"]),
        user_content=fanout.branch_user_content(spec),
    )
    tokens = [*retained["retained_root_tokens"], *suffix["suffix_tokens"]]
    payload = harness.carrier._branch_payload(
        tokens,
        seed=fanout.derive_seed(ROOT_ID, f"branch-{tick}"),
        cache_prompt=cache_prompt,
    )
    record = harness.run_completion(sidecar, f"{ROOT_ID}:tick-{tick}:{route}", payload)
    record["answer"] = harness.carrier.parse_branch_output(record["content"])
    record["expected"] = spec["answer"]
    record["correct"] = record["answer"] == spec["answer"]
    record["input_token_sha256"] = harness.sha256_bytes(harness.carrier.canonical_json_bytes(tokens))
    return record


def evaluate(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    baseline_private: int | None,
    root_boundary: str,
) -> dict[str, Any]:
    harness.require(root_boundary in ROOT_BOUNDARIES, "RAM-root boundary mode is invalid")
    prompt_text = codec.render_messages(
        harness.carrier.task_a_messages(sustained.ROOT),
        harness.carrier.CHAT_TEMPLATE_KWARGS,
    )
    prompt_tokens = codec.tokenize(prompt_text)
    task_payload = harness.carrier._task_a_payload(
        prompt_tokens,
        seed=fanout.derive_seed(ROOT_ID, "task-a"),
    )
    task_a = harness.run_completion(sidecar, f"{ROOT_ID}:task-a", task_payload)
    parsed = harness.carrier.parse_task_a_output(task_a["content"])
    harness.require(parsed["answer"] == sustained.TASK_A_ANSWER, "RAM-root Task-A answer is incorrect")
    retained = harness.carrier.derive_retained_root(
        harness.root_capture(task_a, task_payload),
        prompt_tokens,
        codec,
        props,
    )
    retained_count = int(retained["retained_root_token_count"])
    root_count = retained_count
    root_materialization: dict[str, Any] | None = None
    if root_boundary == "prompt-only":
        materialization_payload = prompt_root_materialization_payload(prompt_tokens)
        root_materialization = harness.run_completion(
            sidecar,
            f"{ROOT_ID}:prompt-root-materialize",
            materialization_payload,
            operation_kind="zero-output-root-readdress",
        )
        harness.require(
            root_materialization["prompt_tokens"] == len(prompt_tokens),
            "RAM-root prompt materialization token count changed",
        )
        harness.require(
            root_materialization["cached_prompt_tokens"] == 0,
            "RAM-root prompt materialization was not fresh",
        )
        harness.require(
            root_materialization["completion_tokens"] == 0,
            "RAM-root prompt materialization emitted output",
        )
        root_count = len(prompt_tokens)


    save_raw, save_wall = harness.ram_root_action(action="root-save", root_id=ROOT_ID)
    save = validate_root_response(save_raw, action="root-save")
    harness.require(save["n_tokens"] == root_count, "RAM-root saved token count differs from selected boundary")

    restores: list[dict[str, Any]] = []

    def restore(label: str) -> None:
        response, wall = harness.ram_root_action(action="root-restore", root_id=ROOT_ID)
        validated = validate_root_response(response, action="root-restore", expected=save)
        validated.update(label=label, client_wall_seconds=wall)
        restores.append(validated)

    tick_2_live = run_branch(
        sidecar=sidecar,
        codec=codec,
        retained=retained,
        tick=2,
        route="live-catalytic",
        cache_prompt=True,
    )
    harness.require(tick_2_live["cached_prompt_tokens"] == root_count, "RAM-root live tick 2 missed selected root")

    restore("after-live-tick-2")
    tick_1 = run_branch(
        sidecar=sidecar,
        codec=codec,
        retained=retained,
        tick=1,
        route="catalytic",
        cache_prompt=True,
    )
    harness.require(tick_1["correct"], f"RAM-root catalytic tick 1 is incorrect: {tick_1['answer']}")
    harness.require(tick_1["cached_prompt_tokens"] == root_count, "RAM-root tick 1 missed selected root")

    restore("after-tick-1")
    tick_2 = run_branch(
        sidecar=sidecar,
        codec=codec,
        retained=retained,
        tick=2,
        route="catalytic",
        cache_prompt=True,
    )

    restore("after-first-tick-2")
    tick_2_direct = run_branch(
        sidecar=sidecar,
        codec=codec,
        retained=retained,
        tick=2,
        route="direct",
        cache_prompt=False,
    )

    restore("after-direct-tick-2")
    tick_2_replay = run_branch(
        sidecar=sidecar,
        codec=codec,
        retained=retained,
        tick=2,
        route="catalytic-replay",
        cache_prompt=True,
    )
    restore("final-root-closure")

    harness.require(tick_2["cached_prompt_tokens"] == root_count, "RAM-root tick 2 missed selected root")
    harness.require(tick_2_direct["cached_prompt_tokens"] == 0, "RAM-root direct tick 2 was not fresh")
    harness.require(tick_2_replay["cached_prompt_tokens"] == root_count, "RAM-root replay missed selected root")
    harness.require(
        tick_2_live["input_token_sha256"]
        == tick_2["input_token_sha256"]
        == tick_2_direct["input_token_sha256"]
        == tick_2_replay["input_token_sha256"],
        "RAM-root tick-2 route token arrays differ",
    )
    generated_hashes = [
        item["execution"].get("generated_token_sha256")
        for item in (tick_2_live, tick_2, tick_2_direct, tick_2_replay)
    ]
    harness.require(
        all(isinstance(value, str) and len(value) == 64 for value in generated_hashes),
        "RAM-root tick-2 route lacks exact generated-token evidence",
    )
    generated_hash_equal = len(set(generated_hashes)) == 1

    resources_with_root = harness.process_resources(sidecar, baseline_private)
    erase_raw, erase_wall = harness.ram_root_action(action="root-erase", root_id=ROOT_ID)
    erase = validate_root_response(erase_raw, action="root-erase", expected=save)
    resources_after_erase = harness.process_resources(sidecar, baseline_private)

    catalytic_fresh = sum(
        int(item["fresh_model_tokens"])
        for item in (task_a, tick_2_live, tick_1, tick_2, tick_2_replay)
    )
    if root_materialization is not None:
        catalytic_fresh += int(root_materialization["fresh_model_tokens"])
    direct_fresh = int(tick_2_direct["fresh_model_tokens"])
    all_correct = all(item["correct"] for item in (tick_2_live, tick_1, tick_2, tick_2_direct, tick_2_replay))
    route_classification = classify_live_restore(
        expected=str(tick_2["expected"]),
        live_answer=str(tick_2_live["answer"]),
        restored_answer=str(tick_2["answer"]),
        direct_answer=str(tick_2_direct["answer"]),
    )
    accepted = all_correct and generated_hash_equal and tick_2_replay["answer"] == tick_2["answer"]
    return {
        "status": "complete",
        "mechanism": f"bounded-named-native-ram-root-{root_boundary}",
        "model": "Agents-A1",
        "verdict": "accept" if accepted else "reject",
        "discriminator": (
            "untouched live root versus restored root versus fresh direct tick 2"
            if root_boundary == "completed-generation"
            else "prompt-only root with generated tail re-evaluation versus fresh direct tick 2"
        ),
        "root_boundary": {
            "type": root_boundary,
            "task_a_prompt_tokens": len(prompt_tokens),
            "completed_generation_tokens": retained_count,
            "saved_tokens": root_count,
            "reprocessed_generated_tail_tokens": retained_count - root_count,
            "zero_output_materialized": root_materialization is not None,
        },
        "utility": {
            "tick_1_catalytic": tick_1["answer"],
            "tick_2_live_catalytic": tick_2_live["answer"],
            "tick_2_catalytic": tick_2["answer"],
            "tick_2_direct": tick_2_direct["answer"],
            "tick_2_catalytic_replay": tick_2_replay["answer"],
            "all_correct": all_correct,
            "tick_2_generated_token_hash_equal": generated_hash_equal,
            "route_classification": route_classification,
            "replay_matches_first_catalytic": tick_2_replay["answer"] == tick_2["answer"],
        },
        "fresh_model_compute": {
            "complete_catalytic_path_including_task_a_materialization_and_replay": catalytic_fresh,
            "prompt_root_materialization": (
                int(root_materialization["fresh_model_tokens"])
                if root_materialization is not None else 0
            ),
            "tick_2_direct_control": direct_fresh,
        },
        "carrier": {
            "save": {**save, "client_wall_seconds": save_wall},
            "restores": restores,
            "restore_count": len(restores),
            "non_consuming_repeatable": len(restores) == 5,
            "identity_and_size_invariant": True,
            "final_restore_before_erase": restores[-1]["label"] == "final-root-closure",
            "erase": {**erase, "client_wall_seconds": erase_wall},
        },
        "routes": {
            "task_a": harness.token_summary(task_a),
            **(
                {"prompt_root_materialization": harness.token_summary(root_materialization)}
                if root_materialization is not None
                else {}
            ),
            "tick_2_live_catalytic": {
                "answer": tick_2_live["answer"],
                "generated_token_sha256": tick_2_live["execution"].get("generated_token_sha256"),
                **harness.token_summary(tick_2_live),
            },
            "tick_1_catalytic": {
                "answer": tick_1["answer"],
                "generated_token_sha256": tick_1["execution"].get("generated_token_sha256"),
                **harness.token_summary(tick_1),
            },
            "tick_2_catalytic": {
                "answer": tick_2["answer"],
                "generated_token_sha256": tick_2["execution"].get("generated_token_sha256"),
                **harness.token_summary(tick_2),
            },
            "tick_2_direct": {
                "answer": tick_2_direct["answer"],
                "generated_token_sha256": tick_2_direct["execution"].get("generated_token_sha256"),
                **harness.token_summary(tick_2_direct),
            },
            "tick_2_catalytic_replay": {
                "answer": tick_2_replay["answer"],
                "generated_token_sha256": tick_2_replay["execution"].get("generated_token_sha256"),
                **harness.token_summary(tick_2_replay),
            },
        },
        "resources_with_root": resources_with_root,
        "resources_after_erase": resources_after_erase,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--model", type=Path, default=harness.DEFAULT_MODEL)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--server-log-output", type=Path)
    parser.add_argument("--root-boundary", choices=ROOT_BOUNDARIES, default="completed-generation")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    binary = args.binary.resolve(strict=True)
    model = args.model.resolve(strict=True)
    evaluator, live_contract = harness.load_discovery_sidecar_contract()
    stable_pids = harness.live_runtime.require_stable()
    harness.require(len(stable_pids) == 1, "RAM-root discriminator requires the sole stable listener")
    harness.require(not harness.live_runtime.listener_pids(harness.live_runtime.PORT), "frontier port is occupied")
    state_root = Path(tempfile.mkdtemp(prefix="neo3000-catalytic-ram-root-"))
    sidecar: Any | None = None
    result: dict[str, Any] | None = None
    cleanup: Mapping[str, Any] | None = None
    error: BaseException | None = None
    if args.server_log_output is not None:
        os.environ["LLAMA_ARG_LOG_VERBOSITY"] = "1000"
        os.environ["LLAMA_SERVER_SLOTS_DEBUG"] = "1"

    try:
        sidecar = harness.DiscoverySidecar(
            binary,
            model,
            evaluator,
            live_contract,
            detached=False,
            stable_pids=set(stable_pids),
            state_root=state_root,
            advisory_wddm=True,
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
            baseline_private=baseline_private,
            root_boundary=args.root_boundary,
        )
        result["readiness"] = {
            "pid": readiness.get("pid"),
            "readiness_seconds": readiness.get("readiness_seconds"),
            "binary": readiness.get("binary"),
            "model": readiness.get("model"),
            "baseline_private_bytes": baseline_private,
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
        print(json.dumps({
            "status": "engineering-failure",
            "error_type": type(error).__name__,
            "error": str(error),
            "cleanup": cleanup,
        }, ensure_ascii=False, indent=2))
        return 1
    harness.require(result is not None, "RAM-root result is missing")
    result["cleanup"] = cleanup
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
