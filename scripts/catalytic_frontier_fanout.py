#!/usr/bin/env python3
"""Reusable Agents-A1 fanout probe for the catalytic frontier.

One exact emitted-token root is saved once. Distinct strict-extension branches
borrow that executable root, extract a bounded answer, and restore it. Recurrent
minimal-output closure probes run at N=2,4,8 and are fully counted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import catalytic_frontier_harness as harness


MILESTONES = (2, 4, 8)
EXTRA_PANELS: dict[str, list[dict[str, Any]]] = {
    "mb-runtime-datacenter-01": [
        {
            "question": "Which two preparatory actions may run concurrently before East isolation?",
            "choices": {
                "A": "The breaker inspection and East isolation.",
                "B": "The leader move to W1 and the replication-queue drain.",
                "C": "Transfers of both row pairs during the same five-minute interval.",
                "D": "Creating a replica from E1 after East is isolated.",
            },
            "answer": "B",
        },
        {
            "question": "Immediately after W2 is disabled and before further routing or promotion, which healthy replica set is stated by the evidence?",
            "choices": {
                "A": "E1, E2, and W1.",
                "B": "W1 and W2 only.",
                "C": "E1 and W2 only.",
                "D": "W1 only.",
            },
            "answer": "A",
        },
        {
            "question": "Which transfer-controller action is explicitly forbidden?",
            "choices": {
                "A": "Temporarily placing E2 on West.",
                "B": "Moving one row pair during a five-minute interval.",
                "C": "Restoring normal routing after an abandoned inspection.",
                "D": "Moving both row pairs during the same five-minute interval.",
            },
            "answer": "D",
        },
        {
            "question": "Why must a second healthy replica be preserved before East is electrically isolated?",
            "choices": {
                "A": "The maintenance window requires every row to be on battery.",
                "B": "W1 cannot host a database leader.",
                "C": "Policy requires two healthy replicas and no new replica may be created from an isolated source.",
                "D": "The transfer controller can never place E2 on West.",
            },
            "answer": "C",
        },
        {
            "question": "If replication draining starts at 21:58 and takes six minutes, when is that prerequisite first complete?",
            "choices": {"A": "22:04.", "B": "22:02.", "C": "22:06.", "D": "22:20."},
            "answer": "A",
        },
        {
            "question": "Which reserve condition explicitly forces the team to abandon the inspection and restore normal routing?",
            "choices": {
                "A": "Any use of the battery room.",
                "B": "Projected battery reserve falling below four minutes.",
                "C": "A leader move lasting four minutes.",
                "D": "The cooling alarm on W2 by itself.",
            },
            "answer": "B",
        },
    ],
    "mb-runtime-coldchain-02": [
        {
            "question": "Which lots are allowed to share the sealed chilled tote under the stated transport controls?",
            "choices": {
                "A": "Amber and Coral only.",
                "B": "Blue and Coral only.",
                "C": "All three lots.",
                "D": "Amber and Blue only.",
            },
            "answer": "D",
        },
        {
            "question": "If Coral's old vehicle field is left uncorrected, what does the evidence say is invalidated?",
            "choices": {
                "A": "Only the dry-ice temperature.",
                "B": "The chilled tote's logger.",
                "C": "Coral's documentary chain of custody, not its medicine temperature.",
                "D": "Every transfer for the entire day.",
            },
            "answer": "C",
        },
        {
            "question": "What inspection condition must be satisfied before any container leaves the clinic?",
            "choices": {
                "A": "The pharmacist and receiving nurse inspect the same tamper seal.",
                "B": "Only the courier looks at the lot number.",
                "C": "The hospital receiver opens the container first.",
                "D": "Both vehicles occupy the loading bay simultaneously.",
            },
            "answer": "A",
        },
        {
            "question": "What happens if a container arrives before its correct hospital receiver is ready?",
            "choices": {
                "A": "It is automatically accepted by any available employee.",
                "B": "It remains under its original transport control until the correct receiver accepts it.",
                "C": "Its custody record becomes valid without a signature.",
                "D": "It must be moved into the other vehicle.",
            },
            "answer": "B",
        },
        {
            "question": "Why does Blue's twenty-five-minute limit not set the shared tote's governing deadline?",
            "choices": {
                "A": "Blue is frozen and uses dry ice.",
                "B": "The tote logger is invalid at 7.6 degrees.",
                "C": "Vehicle paperwork replaces thermal limits.",
                "D": "Amber shares the tote and has the tighter eighteen-minute limit.",
            },
            "answer": "D",
        },
        {
            "question": "Which transport choice violates an explicit thermal-control boundary even if its paperwork is corrected?",
            "choices": {
                "A": "Keeping Coral in its validated dry-ice chest.",
                "B": "Keeping Amber and Blue in their sealed chilled tote.",
                "C": "Putting Coral into the chilled van.",
                "D": "Waiting under original transport control for the correct receiver.",
            },
            "answer": "C",
        },
    ],
}


def derive_seed(root_id: str, role: str) -> int:
    digest = hashlib.sha256(f"catalytic-frontier-v1|{root_id}|{role}".encode()).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def panel_for(root: Mapping[str, Any]) -> list[dict[str, Any]]:
    root_id = str(root["root_id"])
    panel: list[dict[str, Any]] = []
    for number, branch in enumerate(root["branches"], start=1):
        panel.append(
            {
                "question": str(branch["question"]),
                "choices": dict(branch["choices"]),
                "answer": harness.EXPECTED[root_id][f"branch-{number}"],
            }
        )
    panel.extend(EXTRA_PANELS[root_id])
    harness.require(len(panel) == 8, "frontier panel must contain eight projections")
    harness.require(len({item["question"] for item in panel}) == 8, "frontier questions must be distinct")
    return panel


def branch_user_content(spec: Mapping[str, Any]) -> str:
    choices = "\n".join(f"{label}. {spec['choices'][label]}" for label in ("A", "B", "C", "D"))
    return (
        "TASK B\nUse the complete preserved Task-A state and the same evidence for this related transformation. "
        "Return only JSON of the form {\"answer\":\"A\"}.\n"
        f"{spec['question']}\n{choices}"
    )


def prefix_metrics(
    *,
    task_a: Mapping[str, Any],
    catalytic: Mapping[int, Mapping[str, Any]],
    direct: Mapping[int, Mapping[str, Any]],
    closures: Mapping[int, Mapping[str, Any]],
    branch_order: Sequence[int],
    milestones: Sequence[int],
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    previous_average: float | None = None
    for fanout in milestones:
        selected = branch_order[:fanout]
        carrier_cost = int(task_a["fresh_model_tokens"])
        branch_cost = sum(int(catalytic[number]["fresh_model_tokens"]) for number in selected)
        closure_cost = sum(
            int(closures[milestone]["fresh_model_tokens"])
            for milestone in milestones
            if milestone <= fanout
        )
        catalytic_total = carrier_cost + branch_cost + closure_cost
        direct_total = sum(int(direct[number]["fresh_model_tokens"]) for number in selected)
        average = catalytic_total / fanout
        output[str(fanout)] = {
            "carrier_creation": carrier_cost,
            "branch_compute": branch_cost,
            "closure_compute": closure_cost,
            "catalytic_total": catalytic_total,
            "direct_total": direct_total,
            "compute_amplification": direct_total / catalytic_total,
            "average_fresh_compute_per_branch": average,
            "average_decreased": previous_average is None or average < previous_average,
        }
        previous_average = average
    return output


def _compact(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "branch": record["branch"],
        "answer": record["answer"],
        "correct": record["correct"],
        **harness.token_summary(record),
    }


def evaluate_root(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    snapshot_root: Path,
    root: Mapping[str, Any],
    fanout: int,
    baseline_private: int | None,
) -> dict[str, Any]:
    root_id = str(root["root_id"])
    panel = panel_for(root)
    branch_order = list(range(1, fanout + 1))
    if root_id == "mb-runtime-coldchain-02" and fanout >= 2:
        branch_order[:2] = [2, 1]
    milestones = tuple(value for value in MILESTONES if value <= fanout)

    prompt_text = codec.render_messages(harness.carrier.task_a_messages(root), harness.carrier.CHAT_TEMPLATE_KWARGS)
    prompt_tokens = codec.tokenize(prompt_text)
    task_payload = harness.carrier._task_a_payload(prompt_tokens, seed=derive_seed(root_id, "task-a"))
    task_a = harness.run_completion(sidecar, f"{root_id}:task-a", task_payload)
    parsed = harness.carrier.parse_task_a_output(task_a["content"])
    harness.require(parsed["answer"] == harness.EXPECTED[root_id]["task_a"], "Task-A answer is incorrect")
    retained = harness.carrier.derive_retained_root(
        harness.root_capture(task_a, task_payload),
        prompt_tokens,
        codec,
        props,
    )
    retained_count = int(retained["retained_root_token_count"])

    snapshot_name = f"{root_id}.fanout.bin"
    save_response, save_seconds = harness.snapshot_action(action="save", filename=snapshot_name)
    harness.require(save_response.get("n_saved") == retained_count, "snapshot save count differs")
    snapshot_path = snapshot_root / snapshot_name
    initial_snapshot = snapshot_path.read_bytes()
    initial_hash = harness.sha256_bytes(initial_snapshot)

    complete_tokens: dict[int, list[int]] = {}
    catalytic: dict[int, dict[str, Any]] = {}
    direct: dict[int, dict[str, Any]] = {}
    closures: dict[int, dict[str, Any]] = {}
    restore_count = 0

    for ordinal, number in enumerate(branch_order, start=1):
        if ordinal > 1:
            response, _seconds = harness.snapshot_action(action="restore", filename=snapshot_name)
            harness.require(response.get("n_restored") == retained_count, "branch restore count differs")
            restore_count += 1
        spec = panel[number - 1]
        suffix = harness.carrier.derive_continuation_suffix(
            codec,
            terminal_eog_id=int(retained["terminal_stop_identity"]["token_id"]),
            user_content=branch_user_content(spec),
        )
        tokens = [*retained["retained_root_tokens"], *suffix["suffix_tokens"]]
        complete_tokens[number] = tokens
        payload = harness.carrier._branch_payload(
            tokens,
            seed=derive_seed(root_id, f"branch-{number}"),
            cache_prompt=True,
        )
        record = harness.run_completion(sidecar, f"{root_id}:branch-{number}:catalytic", payload)
        answer = harness.carrier.parse_branch_output(record["content"])
        record.update(branch=number, answer=answer, correct=answer == spec["answer"])
        harness.require(record["correct"], f"catalytic branch {number} is incorrect: {answer}")
        harness.require(record["cached_prompt_tokens"] == retained_count, f"branch {number} missed complete root")
        catalytic[number] = record
        harness.process_resources(sidecar, baseline_private)

        if ordinal in milestones:
            response, _seconds = harness.snapshot_action(action="restore", filename=snapshot_name)
            harness.require(response.get("n_restored") == retained_count, "checkpoint restore count differs")
            restore_count += 1
            closure_text = (
                f"ROOT READDRESS CHECK {root_id} AT FANOUT {ordinal}\n"
                "Return only {\"answer\":\"A\"}. This minimal-output suffix verifies addressability."
            )
            closure_suffix = harness.carrier.derive_continuation_suffix(
                codec,
                terminal_eog_id=int(retained["terminal_stop_identity"]["token_id"]),
                user_content=closure_text,
            )
            closure_tokens = [*retained["retained_root_tokens"], *closure_suffix["suffix_tokens"]]
            closure_payload = harness.carrier._branch_payload(
                closure_tokens,
                seed=derive_seed(root_id, f"closure-{ordinal}"),
                cache_prompt=True,
                n_predict=1,
            )
            closure = harness.run_completion(sidecar, f"{root_id}:closure-readdress", closure_payload)
            harness.require(closure["cached_prompt_tokens"] == retained_count, f"closure N={ordinal} missed root")
            closures[ordinal] = closure
            response, _seconds = harness.snapshot_action(action="restore", filename=snapshot_name)
            harness.require(response.get("n_restored") == retained_count, "post-closure restore count differs")
            restore_count += 1

    closed_name = f"{root_id}.fanout.closed.bin"
    closed_response, closed_save_seconds = harness.snapshot_action(action="save", filename=closed_name)
    harness.require(closed_response.get("n_saved") == retained_count, "closed snapshot count differs")
    closed_path = snapshot_root / closed_name
    closed_snapshot = closed_path.read_bytes()
    byte_exact = closed_snapshot == initial_snapshot
    closed_path.unlink()

    for number in branch_order:
        spec = panel[number - 1]
        payload = harness.carrier._branch_payload(
            complete_tokens[number],
            seed=derive_seed(root_id, f"branch-{number}"),
            cache_prompt=False,
        )
        record = harness.run_completion(sidecar, f"{root_id}:branch-{number}:direct", payload)
        answer = harness.carrier.parse_branch_output(record["content"])
        record.update(branch=number, answer=answer, correct=answer == spec["answer"])
        harness.require(record["correct"], f"direct branch {number} is incorrect: {answer}")
        harness.require(record["cached_prompt_tokens"] == 0, f"direct branch {number} was not fresh")
        direct[number] = record
        harness.process_resources(sidecar, baseline_private)

    metrics = prefix_metrics(
        task_a=task_a,
        catalytic=catalytic,
        direct=direct,
        closures=closures,
        branch_order=branch_order,
        milestones=milestones,
    )
    return {
        "status": "complete",
        "root_id": root_id,
        "model": "Agents-A1",
        "fanout": fanout,
        "distinct_projection_count": fanout,
        "retained_root_tokens": retained_count,
        "complete_root_reuse": all(
            catalytic[number]["cached_prompt_tokens"] == retained_count for number in branch_order
        ),
        "utility": {
            "catalytic_correct": sum(bool(catalytic[number]["correct"]) for number in branch_order),
            "direct_correct": sum(bool(direct[number]["correct"]) for number in branch_order),
            "route_answers_equal": all(
                catalytic[number]["answer"] == direct[number]["answer"] for number in branch_order
            ),
        },
        "prefixes": metrics,
        "recurrent_closures": {
            "milestones": list(milestones),
            "fresh_model_tokens": {
                str(milestone): closures[milestone]["fresh_model_tokens"] for milestone in milestones
            },
            "cached_root_tokens": {
                str(milestone): closures[milestone]["cached_prompt_tokens"] for milestone in milestones
            },
            "restore_count": restore_count,
        },
        "snapshot": {
            "bytes": len(initial_snapshot),
            "sha256": initial_hash,
            "byte_exact_after_final_closure": byte_exact,
            "save_wall_seconds": save_seconds,
            "closed_save_wall_seconds": closed_save_seconds,
            "durable_snapshot_count_during_run": 1,
        },
        "catalytic_branches": [_compact(catalytic[number]) for number in branch_order],
        "direct_branches": [_compact(direct[number]) for number in branch_order],
        "task_a": harness.token_summary(task_a),
        "resources": harness.process_resources(sidecar, baseline_private),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, default=harness.DEFAULT_BINARY)
    parser.add_argument("--model", type=Path, default=harness.DEFAULT_MODEL)
    parser.add_argument("--root-id", choices=tuple(EXTRA_PANELS), default="mb-runtime-datacenter-01")
    parser.add_argument("--fanout", type=int, choices=MILESTONES, default=8)
    parser.add_argument("--output", type=Path)
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
    harness.require(len(stable_pids) == 1, "frontier fanout requires the existing sole stable listener")
    harness.require(not harness.live_runtime.listener_pids(harness.live_runtime.PORT), "frontier port is occupied")
    state_root = Path(tempfile.mkdtemp(prefix="neo3000-catalytic-fanout-"))
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
        baseline_private = None
        process_memory = readiness.get("process_memory")
        if isinstance(process_memory, Mapping) and isinstance(process_memory.get("private_bytes"), int):
            baseline_private = int(process_memory["private_bytes"])
        codec = harness.carrier.SidecarPromptCodec(harness.live_runtime.PORT)
        props = codec.props()
        result = evaluate_root(
            sidecar=sidecar,
            codec=codec,
            props=props,
            snapshot_root=snapshots,
            root=roots[args.root_id],
            fanout=args.fanout,
            baseline_private=baseline_private,
        )
        result["readiness"] = {
            "pid": readiness.get("pid"),
            "readiness_seconds": readiness.get("readiness_seconds"),
            "baseline_private_bytes": baseline_private,
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
    harness.require(result is not None, "frontier fanout result is missing")
    result["cleanup"] = cleanup
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
