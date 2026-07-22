#!/usr/bin/env python3
"""Single-tick live/restored/direct/replay discriminator for a prompt-only RAM root."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

import catalytic_frontier_fanout as fanout
import catalytic_frontier_harness as harness
import catalytic_frontier_ram_root as ram_root
import catalytic_frontier_sustained as sustained


DEFAULT_TICK = 11
ROOT_ID = sustained.ROOT_ID


def classify_prefix_routes(
    *,
    expected: str,
    live: str,
    restored: str,
    direct: str,
    replay: str,
    generated_equal: bool = True,
) -> str:
    if direct != expected:
        return "direct-control-utility-failure"
    if live == restored == replay == direct:
        return (
            "exact-live-restore-replay-equivalence" if generated_equal else "generated-token-divergence"
        )
    if live != direct and restored == live and replay == live:
        return "live-prompt-prefix-divergence"
    if live == direct and restored != direct and replay == restored:
        return "serialization-restore-divergence"
    if live == restored == direct and replay != direct:
        return "repeated-use-or-replay-divergence"
    if restored != replay:
        return "restore-repeatability-divergence"
    return "mixed-cached-route-divergence"


def validate_frozen_boundary(*, tick: int, root_count: int, retained_count: int) -> None:
    harness.require(tick == DEFAULT_TICK, f"discriminator tick must remain frozen at {DEFAULT_TICK}")
    harness.require(root_count == 270, "prompt-root boundary drifted from 270 tokens")
    harness.require(retained_count == 285, "completed-generation boundary drifted from 285 tokens")
    harness.require(retained_count - root_count == 15, "generated Task-A tail count changed")


def validate_restored_root(
    response_raw: Mapping[str, Any],
    *,
    saved: Mapping[str, Any],
) -> dict[str, Any]:
    response = ram_root.validate_root_response(response_raw, action="root-restore", expected=saved)
    for key in ("id_slot", "id_slot_source"):
        harness.require(response.get(key) == saved.get(key), f"prompt RAM-root {key} changed at root-restore")
    return response


def generated_hash(record: Mapping[str, Any], label: str) -> str:
    value = record["execution"].get("generated_token_sha256")
    harness.require(isinstance(value, str) and len(value) == 64, f"{label} lacks generated-token evidence")
    return value


def route_summary(record: Mapping[str, Any], label: str) -> dict[str, Any]:
    return {
        "answer": record["answer"],
        "expected": record["expected"],
        "correct": record["correct"],
        "input_token_sha256": record["input_token_sha256"],
        "generated_token_sha256": generated_hash(record, label),
        **harness.token_summary(record),
    }


def evaluate(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    baseline_private: int | None,
    tick: int,
) -> dict[str, Any]:
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
    harness.require(parsed["answer"] == sustained.TASK_A_ANSWER, "prefix discriminator Task-A answer is incorrect")
    retained = harness.carrier.derive_retained_root(
        harness.root_capture(task_a, task_payload),
        prompt_tokens,
        codec,
        props,
    )
    retained_count = int(retained["retained_root_token_count"])
    root_count = len(prompt_tokens)
    validate_frozen_boundary(tick=tick, root_count=root_count, retained_count=retained_count)

    materialization_payload = ram_root.prompt_root_materialization_payload(prompt_tokens)
    root_materialization = harness.run_completion(
        sidecar,
        f"{ROOT_ID}:prompt-root-materialize",
        materialization_payload,
        operation_kind="zero-output-root-readdress",
    )
    harness.require(root_materialization["prompt_tokens"] == root_count, "prompt-root token count changed")
    harness.require(root_materialization["cached_prompt_tokens"] == 0, "prompt-root materialization was not fresh")
    harness.require(root_materialization["completion_tokens"] == 0, "prompt-root materialization emitted output")

    save_raw, save_wall = harness.ram_root_action(action="root-save", root_id=ROOT_ID)
    save = ram_root.validate_root_response(save_raw, action="root-save")
    harness.require(save["n_tokens"] == root_count, "prompt RAM-root count differs")
    restores: list[dict[str, Any]] = []

    def restore(label: str) -> None:
        response_raw, wall = harness.ram_root_action(action="root-restore", root_id=ROOT_ID)
        response = validate_restored_root(response_raw, saved=save)
        response.update(label=label, client_wall_seconds=wall)
        restores.append(response)

    live = ram_root.run_branch(
        sidecar=sidecar,
        codec=codec,
        retained=retained,
        tick=tick,
        route="untouched-live",
        cache_prompt=True,
    )
    restore("after-untouched-live")
    restored = ram_root.run_branch(
        sidecar=sidecar,
        codec=codec,
        retained=retained,
        tick=tick,
        route="restored",
        cache_prompt=True,
    )
    restore("after-restored")
    direct = ram_root.run_branch(
        sidecar=sidecar,
        codec=codec,
        retained=retained,
        tick=tick,
        route="fresh-direct",
        cache_prompt=False,
    )
    restore("after-fresh-direct")
    replay = ram_root.run_branch(
        sidecar=sidecar,
        codec=codec,
        retained=retained,
        tick=tick,
        route="restored-replay",
        cache_prompt=True,
    )
    restore("final-root-closure")

    cached_routes = (live, restored, replay)
    for label, record in zip(("live", "restored", "replay"), cached_routes, strict=True):
        harness.require(record["cached_prompt_tokens"] == root_count, f"{label} route missed prompt root")
    harness.require(direct["cached_prompt_tokens"] == 0, "fresh direct route was not fresh")
    input_hashes = [record["input_token_sha256"] for record in (live, restored, direct, replay)]
    harness.require(len(set(input_hashes)) == 1, "discriminator route token arrays differ")
    generated_hashes = [
        generated_hash(record, label)
        for label, record in zip(("live", "restored", "direct", "replay"), (live, restored, direct, replay), strict=True)
    ]
    all_generated_equal = len(set(generated_hashes)) == 1
    classification = classify_prefix_routes(
        expected=str(direct["expected"]),
        live=str(live["answer"]),
        restored=str(restored["answer"]),
        direct=str(direct["answer"]),
        replay=str(replay["answer"]),
        generated_equal=all_generated_equal,
    )
    accepted = classification == "exact-live-restore-replay-equivalence" and all_generated_equal

    resources_with_root = harness.process_resources(sidecar, baseline_private)
    erase_raw, erase_wall = harness.ram_root_action(action="root-erase", root_id=ROOT_ID)
    erase = ram_root.validate_root_response(erase_raw, action="root-erase", expected=save)
    resources_after_erase = harness.process_resources(sidecar, baseline_private)
    route_records = (live, restored, direct, replay)
    route_wall = sum(float(record["wall_seconds"]) for record in route_records)
    restore_wall = sum(float(record["client_wall_seconds"]) for record in restores)
    total_wall = (
        float(task_a["wall_seconds"])
        + float(root_materialization["wall_seconds"])
        + save_wall
        + route_wall
        + restore_wall
        + erase_wall
    )
    total_fresh = (
        int(task_a["fresh_model_tokens"])
        + int(root_materialization["fresh_model_tokens"])
        + sum(int(record["fresh_model_tokens"]) for record in route_records)
    )
    return {
        "status": "complete",
        "mechanism": "prompt-only-native-ram-root-single-tick-discriminator",
        "verdict": "accept" if accepted else "reject",
        "classification": classification,
        "tick": tick,
        "expected": direct["expected"],
        "root_boundary": {
            "task_a_prompt_tokens": root_count,
            "completed_generation_tokens": retained_count,
            "saved_tokens": root_count,
            "reprocessed_generated_tail_tokens": retained_count - root_count,
        },
        "route_equivalence": {
            "input_token_arrays_equal": True,
            "generated_tokens_all_equal": all_generated_equal,
            "live_matches_direct": live["answer"] == direct["answer"],
            "restored_matches_direct": restored["answer"] == direct["answer"],
            "replay_matches_direct": replay["answer"] == direct["answer"],
            "restore_repeatable": restored["answer"] == replay["answer"],
        },
        "routes": {
            "untouched_live": route_summary(live, "live"),
            "restored": route_summary(restored, "restored"),
            "fresh_direct": route_summary(direct, "direct"),
            "restored_replay": route_summary(replay, "replay"),
        },
        "fresh_model_compute": {
            "total_measured_run": total_fresh,
            "task_a": int(task_a["fresh_model_tokens"]),
            "prompt_root_materialization": int(root_materialization["fresh_model_tokens"]),
            "all_four_routes": sum(int(record["fresh_model_tokens"]) for record in route_records),
        },
        "wall_seconds": {
            "accounted_request_and_root_operations": total_wall,
            "all_four_routes": route_wall,
            "root_save": save_wall,
            "all_restores": restore_wall,
            "root_erase": erase_wall,
        },
        "carrier": {
            "save": {**save, "client_wall_seconds": save_wall},
            "restores": restores,
            "restore_count": len(restores),
            "non_consuming_repeatable": len(restores) == 4,
            "response_metadata_invariant": True,
            "final_restore_before_erase": restores[-1]["label"] == "final-root-closure",
            "erase": {**erase, "client_wall_seconds": erase_wall},
        },
        "task_a": harness.token_summary(task_a),
        "prompt_root_materialization": harness.token_summary(root_materialization),
        "resources_with_root": resources_with_root,
        "resources_after_erase": resources_after_erase,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, default=ram_root.DEFAULT_BINARY)
    parser.add_argument("--model", type=Path, default=harness.DEFAULT_MODEL)
    parser.add_argument("--tick", type=int, default=DEFAULT_TICK)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--server-log-output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    binary = args.binary.resolve(strict=True)
    model = args.model.resolve(strict=True)
    evaluator, live_contract = harness.load_discovery_sidecar_contract()
    stable_pids = harness.live_runtime.require_stable()
    harness.require(len(stable_pids) == 1, "prefix discriminator requires the sole stable listener")
    harness.require(not harness.live_runtime.listener_pids(harness.live_runtime.PORT), "frontier port is occupied")
    state_root = Path(tempfile.mkdtemp(prefix="neo3000-catalytic-prefix-discriminator-"))
    sidecar: Any | None = None
    result: dict[str, Any] | None = None
    cleanup: Mapping[str, Any] | None = None
    error: BaseException | None = None
    experiment_started = time.monotonic()
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
            tick=args.tick,
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
    experiment_wall_seconds = time.monotonic() - experiment_started

    if error is not None:
        print(json.dumps({
            "status": "engineering-failure",
            "error_type": type(error).__name__,
            "error": str(error),
            "cleanup": cleanup,
            "experiment_wall_seconds": experiment_wall_seconds,
        }, ensure_ascii=False, indent=2))
        return 1
    harness.require(result is not None, "prefix discriminator result is missing")
    result["cleanup"] = cleanup
    result["experiment_wall_seconds"] = experiment_wall_seconds
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
