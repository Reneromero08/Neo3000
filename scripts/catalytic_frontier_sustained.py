#!/usr/bin/env python3
"""Sustained fixed-residency catalytic inference over an unbounded task family.

The task family is defined for every finite tick. The controller streams one
branch at a time and retains only constant-size running summaries; request,
answer, and audit storage are declared separately from the executable carrier.
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

import catalytic_frontier_fanout as fanout
import catalytic_frontier_harness as harness


ROOT_ID = "frontier-phase-rotor-infinite-01"
PHASE_CYCLE = ("A", "C", "D", "B")
FANOUT_CHOICES = (16, 32, 64, 128)
ROOT = {
    "root_id": ROOT_ID,
    "evidence": (
        "A phase rotor has exactly four named states A, B, C, and D. At tick 0 its state is A. "
        "Each tick applies the same total transition A to C, C to D, D to B, and B to A. "
        "The transition law never changes, so the state at every nonnegative finite tick is fixed "
        "by the tick modulo four. A branch may ask for any finite tick. The carrier is valid only "
        "if the same transition law, phase labels, tick origin, and model/runtime identity are preserved."
    ),
    "task_a": {
        "question": "Which compact state captures the invariant needed to answer every finite tick query?",
        "choices": {
            "A": "The rotor stops after tick four, so later states are undefined.",
            "B": "Tick 0 is A and the fixed cycle A to C to D to B to A repeats by tick modulo four.",
            "C": "Each query may choose a new transition law.",
            "D": "Only the immediately preceding tick may be answered.",
        },
        "response_contract": {"state_items": 4, "answer_choices": ["A", "B", "C", "D"]},
    },
    "branches": [],
}
TASK_A_ANSWER = "B"


class OnlineStats:
    def __init__(self) -> None:
        self.count = 0
        self.total = 0.0
        self.minimum: float | None = None
        self.maximum: float | None = None

    def add(self, value: float) -> None:
        self.count += 1
        self.total += value
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)

    def as_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "mean": self.total / self.count if self.count else None,
            "minimum": self.minimum,
            "maximum": self.maximum,
        }


def phase_at(tick: int) -> str:
    if tick < 0:
        raise ValueError("tick must be nonnegative")
    return PHASE_CYCLE[tick % len(PHASE_CYCLE)]


def branch_spec(tick: int) -> dict[str, Any]:
    return {
        "question": f"At finite tick {tick}, which named phase is the rotor in?",
        "choices": {
            "A": "Phase A.",
            "B": "Phase B.",
            "C": "Phase C.",
            "D": "Phase D.",
        },
        "answer": phase_at(tick),
    }


def geometric_milestones(limit: int) -> tuple[int, ...]:
    if limit < 2 or limit & (limit - 1):
        raise ValueError("fanout must be a power of two at least two")
    values: list[int] = []
    current = 2
    while current <= limit:
        values.append(current)
        current *= 2
    return tuple(values)


def private_bytes(pid: int) -> int | None:
    value = harness.live_runtime.process_info(pid)
    if isinstance(value, Mapping) and isinstance(value.get("private_bytes"), int):
        return int(value["private_bytes"])
    return None


def _digest_tokens(digest: Any, tick: int, tokens: list[int]) -> None:
    digest.update(str(tick).encode())
    digest.update(b":")
    digest.update(harness.carrier.canonical_json_bytes(tokens))
    digest.update(b"\n")


def _digest_answer(digest: Any, tick: int, answer: str) -> None:
    digest.update(f"{tick}:{answer}\n".encode())


def evaluate(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    snapshot_root: Path,
    fanout_count: int,
    baseline_sidecar_private: int | None,
    baseline_controller_private: int | None,
) -> dict[str, Any]:
    milestones = geometric_milestones(fanout_count)
    prompt_text = codec.render_messages(harness.carrier.task_a_messages(ROOT), harness.carrier.CHAT_TEMPLATE_KWARGS)
    prompt_tokens = codec.tokenize(prompt_text)
    task_payload = harness.carrier._task_a_payload(prompt_tokens, seed=fanout.derive_seed(ROOT_ID, "task-a"))
    task_a = harness.run_completion(sidecar, f"{ROOT_ID}:task-a", task_payload)
    parsed = harness.carrier.parse_task_a_output(task_a["content"])
    harness.require(parsed["answer"] == TASK_A_ANSWER, "procedural Task-A answer is incorrect")
    retained = harness.carrier.derive_retained_root(
        harness.root_capture(task_a, task_payload),
        prompt_tokens,
        codec,
        props,
    )
    retained_count = int(retained["retained_root_token_count"])

    snapshot_name = f"{ROOT_ID}.root.bin"
    save_response, save_seconds = harness.snapshot_action(action="save", filename=snapshot_name)
    harness.require(save_response.get("n_saved") == retained_count, "root snapshot count differs")
    snapshot_path = snapshot_root / snapshot_name
    initial_snapshot = snapshot_path.read_bytes()
    initial_hash = harness.sha256_bytes(initial_snapshot)

    restore_count = 0
    restore_bytes = 0
    restore_wall_seconds = 0.0
    audit_snapshot_bytes = 0
    audit_snapshot_wall_seconds = 0.0

    def restore_root() -> None:
        nonlocal restore_count, restore_bytes, restore_wall_seconds
        response, seconds = harness.snapshot_action(action="restore", filename=snapshot_name)
        harness.require(response.get("n_restored") == retained_count, "root restore count differs")
        restore_count += 1
        restore_bytes += int(response.get("n_read") or 0)
        restore_wall_seconds += seconds

    catalytic_token_digest = hashlib.sha256()
    catalytic_answer_digest = hashlib.sha256()
    direct_token_digest = hashlib.sha256()
    direct_answer_digest = hashlib.sha256()
    catalytic_fresh = 0
    closure_fresh = 0
    catalytic_correct = 0
    direct_correct = 0
    catalytic_times = OnlineStats()
    direct_times = OnlineStats()
    catalytic_prefix: dict[int, dict[str, Any]] = {}
    direct_prefix: dict[int, int] = {}
    resource_samples: dict[int, dict[str, Any]] = {}

    for tick in range(1, fanout_count + 1):
        if tick > 1:
            restore_root()
        spec = branch_spec(tick)
        suffix = harness.carrier.derive_continuation_suffix(
            codec,
            terminal_eog_id=int(retained["terminal_stop_identity"]["token_id"]),
            user_content=fanout.branch_user_content(spec),
        )
        tokens = [*retained["retained_root_tokens"], *suffix["suffix_tokens"]]
        _digest_tokens(catalytic_token_digest, tick, tokens)
        payload = harness.carrier._branch_payload(
            tokens,
            seed=fanout.derive_seed(ROOT_ID, f"branch-{tick}"),
            cache_prompt=True,
        )
        record = harness.run_completion(sidecar, f"{ROOT_ID}:branch-{tick}:catalytic", payload)
        answer = harness.carrier.parse_branch_output(record["content"])
        harness.require(answer == spec["answer"], f"catalytic tick {tick} is incorrect: {answer}")
        harness.require(record["cached_prompt_tokens"] == retained_count, f"tick {tick} missed full root")
        catalytic_correct += 1
        catalytic_fresh += int(record["fresh_model_tokens"])
        catalytic_times.add(float(record["wall_seconds"]))
        _digest_answer(catalytic_answer_digest, tick, answer)

        if tick in milestones:
            restore_root()
            closure_text = (
                f"ROOT READDRESS CHECK {ROOT_ID} AT FANOUT {tick}\n"
                "Return only {\"answer\":\"A\"}. This one-token suffix verifies retained-root addressability."
            )
            closure_suffix = harness.carrier.derive_continuation_suffix(
                codec,
                terminal_eog_id=int(retained["terminal_stop_identity"]["token_id"]),
                user_content=closure_text,
            )
            closure_tokens = [*retained["retained_root_tokens"], *closure_suffix["suffix_tokens"]]
            closure_payload = harness.carrier._branch_payload(
                closure_tokens,
                seed=fanout.derive_seed(ROOT_ID, f"closure-{tick}"),
                cache_prompt=True,
                n_predict=1,
            )
            closure = harness.run_completion(sidecar, f"{ROOT_ID}:closure-readdress", closure_payload)
            harness.require(closure["cached_prompt_tokens"] == retained_count, f"closure N={tick} missed root")
            closure_fresh += int(closure["fresh_model_tokens"])
            restore_root()

            audit_name = f"{ROOT_ID}.audit.bin"
            audit_response, audit_seconds = harness.snapshot_action(action="save", filename=audit_name)
            harness.require(audit_response.get("n_saved") == retained_count, "audit snapshot count differs")
            audit_path = snapshot_root / audit_name
            audit_bytes = audit_path.read_bytes()
            harness.require(harness.sha256_bytes(audit_bytes) == initial_hash, f"root changed at N={tick}")
            audit_snapshot_bytes += len(audit_bytes)
            audit_snapshot_wall_seconds += audit_seconds
            audit_path.unlink()

            sidecar_resources = harness.process_resources(sidecar, baseline_sidecar_private)
            controller_now = private_bytes(os.getpid())
            resource_samples[tick] = {
                **sidecar_resources,
                "controller_private_bytes": controller_now,
                "controller_private_growth_bytes": (
                    controller_now - baseline_controller_private
                    if controller_now is not None and baseline_controller_private is not None
                    else None
                ),
            }
            catalytic_prefix[tick] = {
                "branch_compute": catalytic_fresh,
                "closure_compute": closure_fresh,
            }

    direct_fresh = 0
    for tick in range(1, fanout_count + 1):
        spec = branch_spec(tick)
        suffix = harness.carrier.derive_continuation_suffix(
            codec,
            terminal_eog_id=int(retained["terminal_stop_identity"]["token_id"]),
            user_content=fanout.branch_user_content(spec),
        )
        tokens = [*retained["retained_root_tokens"], *suffix["suffix_tokens"]]
        _digest_tokens(direct_token_digest, tick, tokens)
        payload = harness.carrier._branch_payload(
            tokens,
            seed=fanout.derive_seed(ROOT_ID, f"branch-{tick}"),
            cache_prompt=False,
        )
        record = harness.run_completion(sidecar, f"{ROOT_ID}:branch-{tick}:direct", payload)
        answer = harness.carrier.parse_branch_output(record["content"])
        harness.require(answer == spec["answer"], f"direct tick {tick} is incorrect: {answer}")
        harness.require(record["cached_prompt_tokens"] == 0, f"direct tick {tick} was not fresh")
        direct_correct += 1
        direct_fresh += int(record["fresh_model_tokens"])
        direct_times.add(float(record["wall_seconds"]))
        _digest_answer(direct_answer_digest, tick, answer)
        if tick in milestones:
            direct_prefix[tick] = direct_fresh

    harness.require(catalytic_token_digest.digest() == direct_token_digest.digest(), "route token arrays differ")
    harness.require(catalytic_answer_digest.digest() == direct_answer_digest.digest(), "route answers differ")

    prefixes: dict[str, dict[str, Any]] = {}
    previous_average: float | None = None
    carrier_cost = int(task_a["fresh_model_tokens"])
    for milestone in milestones:
        catalytic_total = (
            carrier_cost
            + int(catalytic_prefix[milestone]["branch_compute"])
            + int(catalytic_prefix[milestone]["closure_compute"])
        )
        direct_total = direct_prefix[milestone]
        average = catalytic_total / milestone
        prefixes[str(milestone)] = {
            "carrier_creation": carrier_cost,
            **catalytic_prefix[milestone],
            "catalytic_total": catalytic_total,
            "direct_total": direct_total,
            "cumulative_saved_fresh_tokens": direct_total - catalytic_total,
            "compute_amplification": direct_total / catalytic_total,
            "average_fresh_compute_per_branch": average,
            "average_decreased": previous_average is None or average < previous_average,
        }
        previous_average = average

    final_sidecar_resources = harness.process_resources(sidecar, baseline_sidecar_private)
    final_controller_private = private_bytes(os.getpid())
    return {
        "status": "complete",
        "root_id": ROOT_ID,
        "model": "Agents-A1",
        "task_family": {
            "domain": "every nonnegative finite tick",
            "transition": "A->C->D->B->A",
            "inductive_law": "phase_at(t+1) is the fixed successor of phase_at(t)",
            "finite_fanout_executed": fanout_count,
        },
        "utility": {
            "catalytic_correct": catalytic_correct,
            "direct_correct": direct_correct,
            "route_answers_equal": True,
            "token_array_digest_equal": True,
        },
        "prefixes": prefixes,
        "carrier": {
            "retained_root_tokens": retained_count,
            "snapshot_bytes": len(initial_snapshot),
            "snapshot_sha256": initial_hash,
            "active_root_snapshot_count": 1,
            "full_root_reuse_every_branch": True,
            "byte_exact_at_every_milestone": True,
        },
        "streaming_controller": {
            "stores_per_branch_records": False,
            "running_digest_bytes": 64,
            "audit_growth_declared_separately": "O(log N) milestone summaries plus external outputs",
            "controller_private_bytes_final": final_controller_private,
            "controller_private_growth_bytes_final": (
                final_controller_private - baseline_controller_private
                if final_controller_private is not None and baseline_controller_private is not None
                else None
            ),
        },
        "snapshot_io": {
            "initial_save_wall_seconds": save_seconds,
            "restore_count": restore_count,
            "restore_bytes": restore_bytes,
            "restore_wall_seconds": restore_wall_seconds,
            "audit_snapshot_bytes": audit_snapshot_bytes,
            "audit_snapshot_wall_seconds": audit_snapshot_wall_seconds,
        },
        "timings": {
            "catalytic_branch_wall_seconds": catalytic_times.as_dict(),
            "direct_branch_wall_seconds": direct_times.as_dict(),
        },
        "resource_samples": {str(key): value for key, value in resource_samples.items()},
        "resources_final": final_sidecar_resources,
        "task_a": harness.token_summary(task_a),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, default=harness.DEFAULT_BINARY)
    parser.add_argument("--model", type=Path, default=harness.DEFAULT_MODEL)
    parser.add_argument("--fanout", type=int, choices=FANOUT_CHOICES, default=64)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    binary = args.binary.resolve(strict=True)
    model = args.model.resolve(strict=True)
    evaluator, live_contract = harness.load_discovery_sidecar_contract()
    stable_pids = harness.live_runtime.require_stable()
    harness.require(len(stable_pids) == 1, "sustained frontier requires the sole stable listener")
    harness.require(not harness.live_runtime.listener_pids(harness.live_runtime.PORT), "frontier port is occupied")
    state_root = Path(tempfile.mkdtemp(prefix="neo3000-catalytic-sustained-"))
    snapshots = state_root / "snapshots"
    sidecar: Any | None = None
    result: dict[str, Any] | None = None
    cleanup: Mapping[str, Any] | None = None
    error: BaseException | None = None
    try:
        sidecar = harness.live_runtime.LiveSidecar(
            binary,
            model,
            evaluator,
            live_contract,
            detached=False,
            stable_pids=set(stable_pids),
            state_root=state_root,
            slot_save_path=snapshots,
            advisory_wddm=True,
        )
        readiness = sidecar.launch()
        baseline_sidecar_private = None
        process_memory = readiness.get("process_memory")
        if isinstance(process_memory, Mapping) and isinstance(process_memory.get("private_bytes"), int):
            baseline_sidecar_private = int(process_memory["private_bytes"])
        baseline_controller_private = private_bytes(os.getpid())
        codec = harness.carrier.SidecarPromptCodec(harness.live_runtime.PORT)
        props = codec.props()
        result = evaluate(
            sidecar=sidecar,
            codec=codec,
            props=props,
            snapshot_root=snapshots,
            fanout_count=args.fanout,
            baseline_sidecar_private=baseline_sidecar_private,
            baseline_controller_private=baseline_controller_private,
        )
        result["readiness"] = {
            "pid": readiness.get("pid"),
            "readiness_seconds": readiness.get("readiness_seconds"),
            "baseline_sidecar_private_bytes": baseline_sidecar_private,
            "baseline_controller_private_bytes": baseline_controller_private,
        }
    except BaseException as exc:
        error = exc
    finally:
        cleanup = harness.live_runtime.safe_sidecar_cleanup(sidecar)
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
    harness.require(result is not None, "sustained result is missing")
    result["cleanup"] = cleanup
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
