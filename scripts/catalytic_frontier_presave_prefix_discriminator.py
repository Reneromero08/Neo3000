#!/usr/bin/env python3
"""Tick-11 prompt-prefix discriminator that contacts no RAM-root endpoint."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

import catalytic_frontier_checkpoint_control as checkpoint_control
import catalytic_frontier_fanout as fanout
import catalytic_frontier_harness as harness
import catalytic_frontier_ram_prefix_discriminator as prefix
import catalytic_frontier_ram_root as ram_root
import catalytic_frontier_sustained as sustained


DEFAULT_TICK = prefix.DEFAULT_TICK
ROOT_ID = prefix.ROOT_ID
FROZEN_CONTEXT_CHECKPOINTS = checkpoint_control.FROZEN_CONTEXT_CHECKPOINTS
ScopedCheckpointDiscoverySidecar = checkpoint_control.ScopedCheckpointDiscoverySidecar


def classify_presave_routes(
    *,
    expected: str,
    presave: str,
    direct: str,
    generated_equal: bool,
) -> str:
    if direct != expected:
        return "direct-control-utility-failure"
    if presave == direct:
        return "exact-presave-prefix-equivalence" if generated_equal else "generated-token-divergence"
    return "pre-save-materialized-prefix-divergence"


def validate_route_accounting(
    record: Mapping[str, Any],
    *,
    label: str,
    cached: int,
    fresh: int,
) -> None:
    harness.require(record["prompt_tokens"] == 370, f"{label} prompt count changed from 370")
    harness.require(record["cached_prompt_tokens"] == cached, f"{label} cached count changed")
    harness.require(record["fresh_prompt_tokens"] == fresh, f"{label} fresh prompt count changed")
    harness.require(record["completion_tokens"] == 6, f"{label} completion count changed")
    harness.require(record["fresh_model_tokens"] == fresh + 6, f"{label} fresh compute is inconsistent")


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
    harness.require(parsed["answer"] == sustained.TASK_A_ANSWER, "pre-save discriminator Task-A answer is incorrect")
    retained = harness.carrier.derive_retained_root(
        harness.root_capture(task_a, task_payload),
        prompt_tokens,
        codec,
        props,
    )
    retained_count = int(retained["retained_root_token_count"])
    root_count = len(prompt_tokens)
    prefix.validate_frozen_boundary(tick=tick, root_count=root_count, retained_count=retained_count)

    materialization_payload = ram_root.prompt_root_materialization_payload(prompt_tokens)
    root_materialization = harness.run_completion(
        sidecar,
        f"{ROOT_ID}:prompt-root-materialize",
        materialization_payload,
        operation_kind="zero-output-root-readdress",
    )
    harness.require(root_materialization["prompt_tokens"] == root_count, "prompt-root token count changed")
    harness.require(root_materialization["cached_prompt_tokens"] == 0, "prompt-root materialization was not fresh")
    harness.require(root_materialization["fresh_prompt_tokens"] == root_count, "prompt-root materialization fresh count changed")
    harness.require(root_materialization["completion_tokens"] == 0, "prompt-root materialization emitted output")
    harness.require(root_materialization["fresh_model_tokens"] == root_count, "prompt-root materialization compute changed")
    resources_after_materialization = harness.process_resources(sidecar, baseline_private)

    presave = ram_root.run_branch(
        sidecar=sidecar,
        codec=codec,
        retained=retained,
        tick=tick,
        route="pre-save-live",
        cache_prompt=True,
    )
    direct = ram_root.run_branch(
        sidecar=sidecar,
        codec=codec,
        retained=retained,
        tick=tick,
        route="fresh-direct",
        cache_prompt=False,
    )
    validate_route_accounting(presave, label="pre-save live", cached=root_count, fresh=100)
    validate_route_accounting(direct, label="fresh direct", cached=0, fresh=370)
    harness.require(
        presave["input_token_sha256"] == direct["input_token_sha256"],
        "pre-save and direct route token arrays differ",
    )
    presave_hash = prefix.generated_hash(presave, "pre-save live")
    direct_hash = prefix.generated_hash(direct, "fresh direct")
    generated_equal = presave_hash == direct_hash
    classification = classify_presave_routes(
        expected=str(direct["expected"]),
        presave=str(presave["answer"]),
        direct=str(direct["answer"]),
        generated_equal=generated_equal,
    )
    accepted = classification == "exact-presave-prefix-equivalence"
    resources_after_routes = harness.process_resources(sidecar, baseline_private)
    route_records = (presave, direct)
    route_wall = sum(float(record["wall_seconds"]) for record in route_records)
    accounted_wall = (
        float(task_a["wall_seconds"])
        + float(root_materialization["wall_seconds"])
        + route_wall
    )
    route_fresh = sum(int(record["fresh_model_tokens"]) for record in route_records)
    total_fresh = (
        int(task_a["fresh_model_tokens"])
        + int(root_materialization["fresh_model_tokens"])
        + route_fresh
    )
    return {
        "status": "complete",
        "mechanism": "prompt-only-pre-save-no-root-single-tick-discriminator",
        "verdict": "accept" if accepted else "reject",
        "classification": classification,
        "tick": tick,
        "expected": direct["expected"],
        "root_boundary": {
            "task_a_prompt_tokens": root_count,
            "completed_generation_tokens": retained_count,
            "materialized_tokens": root_count,
            "reprocessed_generated_tail_tokens": retained_count - root_count,
        },
        "root_endpoint_contacted": False,
        "ram_root_operations": {
            "root_save": 0,
            "root_restore": 0,
            "root_erase": 0,
            "total": 0,
        },
        "route_equivalence": {
            "input_token_arrays_equal": True,
            "generated_tokens_equal": generated_equal,
            "presave_matches_direct_answer": presave["answer"] == direct["answer"],
            "presave_matches_direct_generated_tokens": generated_equal,
        },
        "routes": {
            "pre_save_live": prefix.route_summary(presave, "pre-save live"),
            "fresh_direct": prefix.route_summary(direct, "fresh direct"),
        },
        "fresh_model_compute": {
            "total_measured_run": total_fresh,
            "task_a": int(task_a["fresh_model_tokens"]),
            "prompt_root_materialization": int(root_materialization["fresh_model_tokens"]),
            "both_routes": route_fresh,
        },
        "wall_seconds": {
            "accounted_request_operations": accounted_wall,
            "both_routes": route_wall,
        },
        "closure": {
            "root_restore_required": False,
            "root_erase_required": False,
            "terminal_mechanism": "sidecar-process-teardown",
        },
        "task_a": harness.token_summary(task_a),
        "prompt_root_materialization": harness.token_summary(root_materialization),
        "resources_after_materialization": resources_after_materialization,
        "resources_after_routes": resources_after_routes,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, default=ram_root.DEFAULT_BINARY)
    parser.add_argument("--model", type=Path, default=harness.DEFAULT_MODEL)
    parser.add_argument("--tick", type=int, default=DEFAULT_TICK)
    parser.add_argument("--ctx-checkpoints", type=int, choices=(0, 8), default=FROZEN_CONTEXT_CHECKPOINTS)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--server-log-output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    binary = args.binary.resolve(strict=True)
    model = args.model.resolve(strict=True)
    evaluator, live_contract = harness.load_discovery_sidecar_contract()
    stable_pids = harness.live_runtime.require_stable()
    harness.require(len(stable_pids) == 1, "pre-save discriminator requires the sole stable listener")
    harness.require(not harness.live_runtime.listener_pids(harness.live_runtime.PORT), "frontier port is occupied")
    state_root = Path(tempfile.mkdtemp(prefix="neo3000-catalytic-presave-discriminator-"))
    sidecar: Any | None = None
    result: dict[str, Any] | None = None
    cleanup: Mapping[str, Any] | None = None
    error: BaseException | None = None
    experiment_started = time.monotonic()
    if args.server_log_output is not None:
        os.environ["LLAMA_ARG_LOG_VERBOSITY"] = "1000"
        os.environ["LLAMA_SERVER_SLOTS_DEBUG"] = "1"
    try:
        sidecar = ScopedCheckpointDiscoverySidecar(
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
            baseline_private=baseline_private,
            tick=args.tick,
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
    harness.require(result is not None, "pre-save discriminator result is missing")
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
