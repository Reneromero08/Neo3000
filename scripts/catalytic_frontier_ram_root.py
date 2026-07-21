#!/usr/bin/env python3
"""Narrow live discriminator for the bounded native RAM-root carrier."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

import catalytic_frontier_fanout as fanout
import catalytic_frontier_harness as harness
import catalytic_frontier_sustained as sustained


DEFAULT_BINARY = Path("build/candidate/bin/Release/llama-server.exe")
ROOT_ID = sustained.ROOT_ID


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
    harness.require(parsed["answer"] == sustained.TASK_A_ANSWER, "RAM-root Task-A answer is incorrect")
    retained = harness.carrier.derive_retained_root(
        harness.root_capture(task_a, task_payload),
        prompt_tokens,
        codec,
        props,
    )
    retained_count = int(retained["retained_root_token_count"])

    save_raw, save_wall = harness.ram_root_action(action="root-save", root_id=ROOT_ID)
    save = validate_root_response(save_raw, action="root-save")
    harness.require(save["n_tokens"] == retained_count, "RAM-root saved token count differs from retained root")

    restores: list[dict[str, Any]] = []

    def restore(label: str) -> None:
        response, wall = harness.ram_root_action(action="root-restore", root_id=ROOT_ID)
        validated = validate_root_response(response, action="root-restore", expected=save)
        validated.update(label=label, client_wall_seconds=wall)
        restores.append(validated)

    tick_1 = run_branch(
        sidecar=sidecar,
        codec=codec,
        retained=retained,
        tick=1,
        route="catalytic",
        cache_prompt=True,
    )
    harness.require(tick_1["correct"], f"RAM-root catalytic tick 1 is incorrect: {tick_1['answer']}")
    harness.require(tick_1["cached_prompt_tokens"] == retained_count, "RAM-root tick 1 missed full root")

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

    harness.require(tick_2["correct"], f"RAM-root catalytic tick 2 is incorrect: {tick_2['answer']}")
    harness.require(tick_2_direct["correct"], f"RAM-root direct tick 2 is incorrect: {tick_2_direct['answer']}")
    harness.require(tick_2_replay["correct"], f"RAM-root replay tick 2 is incorrect: {tick_2_replay['answer']}")
    harness.require(tick_2["cached_prompt_tokens"] == retained_count, "RAM-root tick 2 missed full root")
    harness.require(tick_2_direct["cached_prompt_tokens"] == 0, "RAM-root direct tick 2 was not fresh")
    harness.require(tick_2_replay["cached_prompt_tokens"] == retained_count, "RAM-root replay missed full root")
    harness.require(
        tick_2["input_token_sha256"] == tick_2_direct["input_token_sha256"] == tick_2_replay["input_token_sha256"],
        "RAM-root tick-2 route token arrays differ",
    )
    generated_hashes = [
        item["execution"].get("generated_token_sha256")
        for item in (tick_2, tick_2_direct, tick_2_replay)
    ]
    harness.require(
        all(isinstance(value, str) and len(value) == 64 for value in generated_hashes),
        "RAM-root tick-2 route lacks exact generated-token evidence",
    )
    harness.require(len(set(generated_hashes)) == 1, "RAM-root tick-2 generated token arrays differ")

    resources_with_root = harness.process_resources(sidecar, baseline_private)
    erase_raw, erase_wall = harness.ram_root_action(action="root-erase", root_id=ROOT_ID)
    erase = validate_root_response(erase_raw, action="root-erase", expected=save)
    resources_after_erase = harness.process_resources(sidecar, baseline_private)

    catalytic_fresh = sum(
        int(item["fresh_model_tokens"])
        for item in (task_a, tick_1, tick_2, tick_2_replay)
    )
    direct_fresh = int(tick_2_direct["fresh_model_tokens"])
    return {
        "status": "complete",
        "mechanism": "bounded-named-native-ram-root",
        "model": "Agents-A1",
        "discriminator": "tick-2 file carrier previously returned C while direct returned D",
        "utility": {
            "tick_1_catalytic": tick_1["answer"],
            "tick_2_catalytic": tick_2["answer"],
            "tick_2_direct": tick_2_direct["answer"],
            "tick_2_catalytic_replay": tick_2_replay["answer"],
            "all_correct": True,
            "tick_2_generated_token_hash_equal": True,
        },
        "fresh_model_compute": {
            "catalytic_path_including_task_a_and_replay": catalytic_fresh,
            "tick_2_direct_control": direct_fresh,
        },
        "carrier": {
            "save": {**save, "client_wall_seconds": save_wall},
            "restores": restores,
            "restore_count": len(restores),
            "non_consuming_repeatable": len(restores) == 4,
            "identity_and_size_invariant": True,
            "final_restore_before_erase": restores[-1]["label"] == "final-root-closure",
            "erase": {**erase, "client_wall_seconds": erase_wall},
        },
        "routes": {
            "task_a": harness.token_summary(task_a),
            "tick_1_catalytic": harness.token_summary(tick_1),
            "tick_2_catalytic": harness.token_summary(tick_2),
            "tick_2_direct": harness.token_summary(tick_2_direct),
            "tick_2_catalytic_replay": harness.token_summary(tick_2_replay),
        },
        "resources_with_root": resources_with_root,
        "resources_after_erase": resources_after_erase,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--model", type=Path, default=harness.DEFAULT_MODEL)
    parser.add_argument("--output", type=Path)
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
        cleanup = harness.live_runtime.safe_sidecar_cleanup(sidecar)
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
