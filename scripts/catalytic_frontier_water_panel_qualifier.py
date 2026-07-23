#!/usr/bin/env python3
"""Direct-only N=16 qualification for the unused water-operations root.

This non-retry successor freezes one new panel before model contact and reuses
the proven direct evaluator. It has no carrier, RAM-root, snapshot, restore,
cache-enabled branch, second-attempt, or scaling path.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

import catalytic_frontier_checkpoint_control as checkpoint_control
import catalytic_frontier_harness as harness
import catalytic_frontier_strong_panel_qualifier as base


ROOT_ID = "mb-runtime-water-04"
PANEL_SIZE = 16
PANEL_ORDER = tuple(range(1, PANEL_SIZE + 1))
STARTUP_HEALTH_RECOVERY_SECONDS = 15.0
STARTUP_HEALTH_RECOVERY_SUCCESSES = 3
STARTUP_READINESS_CONTROL_SHA256 = "3A7CD00D378A03325ED83F31CB4F211C50D3FF2242FF9684FD71955C97E63626"
PINNED_BINARY_SHA256 = "E46FCE576B42AB6A4A03F21BDC60B2343F7AB1BCD04B967B92145699C243551E"
PANEL_EXTENSION: list[dict[str, Any]] = [
    {
        "question": "Which service must retain pressure from North throughout the work?",
        "choices": {
            "A": "The school spur.",
            "B": "The meter chamber.",
            "C": "The hospital spur.",
            "D": "The temporary bypass.",
        },
        "answer": "C",
    },
    {
        "question": "From which source can the temporary bypass feed the school?",
        "choices": {
            "A": "The hospital spur.",
            "B": "Valve North.",
            "C": "The isolated meter chamber.",
            "D": "An eastern main.",
        },
        "answer": "D",
    },
    {
        "question": "How long must the temporary bypass be flushed?",
        "choices": {"A": "Ten minutes.", "B": "Five minutes.", "C": "Twenty minutes.", "D": "Sixty minutes."},
        "answer": "A",
    },
    {
        "question": "When may the chlorine test begin?",
        "choices": {
            "A": "As soon as the bypass is connected.",
            "B": "Only after flushing is complete.",
            "C": "Only after the chamber is opened.",
            "D": "After the school begins its day.",
        },
        "answer": "B",
    },
    {
        "question": "How long does the chlorine test take?",
        "choices": {"A": "Ten minutes.", "B": "Twenty minutes.", "C": "Five minutes.", "D": "One minute."},
        "answer": "C",
    },
    {
        "question": "At what time does South reach the field-reported mechanical stop?",
        "choices": {"A": "06:30.", "B": "06:37.", "C": "06:42.", "D": "06:40."},
        "answer": "D",
    },
    {
        "question": "When remote and field valve indications disagree, which evidence governs South physical isolation?",
        "choices": {
            "A": "The field mechanical stop.",
            "B": "The remote status bit.",
            "C": "The chamber pressure sensor alone.",
            "D": "The school start time.",
        },
        "answer": "A",
    },
    {
        "question": "When does the bypass flush complete in the stated timeline?",
        "choices": {"A": "06:37.", "B": "06:42.", "C": "06:40.", "D": "06:47."},
        "answer": "B",
    },
    {
        "question": "When does the inspector stated chlorine-test window end?",
        "choices": {"A": "06:40.", "B": "06:42.", "C": "06:47.", "D": "07:30."},
        "answer": "C",
    },
    {
        "question": "What chamber-pressure reading is required immediately before opening the chamber?",
        "choices": {
            "A": "Normal loop pressure.",
            "B": "North supply pressure.",
            "C": "Any stable nonzero reading.",
            "D": "Zero pressure.",
        },
        "answer": "D",
    },
    {
        "question": "How long does meter replacement take once the chamber is open?",
        "choices": {"A": "Twenty minutes.", "B": "Five minutes.", "C": "Ten minutes.", "D": "Thirty minutes."},
        "answer": "A",
    },
    {
        "question": "What is the temporary bypass status at 06:30?",
        "choices": {
            "A": "Fully certified.",
            "B": "Connected but unflushed.",
            "C": "Disconnected.",
            "D": "Rejected by the chlorine inspector.",
        },
        "answer": "B",
    },
    {
        "question": "Which bypass condition must be satisfied before South closes?",
        "choices": {
            "A": "The school must already be in session.",
            "B": "North must be closed.",
            "C": "Flushing and the chlorine test must both be complete successfully.",
            "D": "Meter replacement must already be complete.",
        },
        "answer": "C",
    },
    {
        "question": "Who performs the chlorine test under the stated crew assignments?",
        "choices": {"A": "The valve crew.", "B": "The bypass crew.", "C": "Hospital staff.", "D": "One inspector."},
        "answer": "D",
    },
]


def panel_for(root: Mapping[str, Any]) -> list[dict[str, Any]]:
    harness.require(str(root["root_id"]) == ROOT_ID, "water qualifier received the wrong root")
    panel: list[dict[str, Any]] = []
    for number, branch in enumerate(root["branches"], start=1):
        panel.append(
            {
                "question": str(branch["question"]),
                "choices": dict(branch["choices"]),
                "answer": harness.EXPECTED[ROOT_ID][f"branch-{number}"],
            }
        )
    panel.extend(PANEL_EXTENSION)
    harness.require(len(panel) == PANEL_SIZE, "water panel must contain sixteen branches")
    harness.require(len({str(item["question"]) for item in panel}) == PANEL_SIZE, "water panel questions must be distinct")
    return panel


def require_pinned_binary(binary: Path) -> None:
    observed = harness.live_runtime.sha256_file(binary)
    harness.require(
        observed == PINNED_BINARY_SHA256,
        f"water qualifier binary identity drifted: {observed}",
    )


def startup_health_recovery_policy() -> Any:
    return harness.live_runtime.StableHealthRecoveryPolicy(
        maximum_consecutive_failure_seconds=STARTUP_HEALTH_RECOVERY_SECONDS,
        required_consecutive_successes=STARTUP_HEALTH_RECOVERY_SUCCESSES,
    )


def startup_readiness_control(evaluator: Mapping[str, Any]) -> dict[str, Any]:
    protocol = evaluator.get("holostate_worker_protocol_v4")
    harness.require(isinstance(protocol, Mapping), "worker-v4 readiness protocol is unavailable")
    control = protocol.get("readiness_control")
    harness.require(isinstance(control, Mapping), "worker-v4 readiness control is unavailable")
    control_copy = dict(control)
    control_hash = harness.sha256_bytes(harness.carrier.canonical_json_bytes(control_copy))
    harness.require(
        control_hash == STARTUP_READINESS_CONTROL_SHA256,
        "worker-v4 readiness control identity changed",
    )
    return control_copy


def build_sidecar(
    *,
    binary: Path,
    model: Path,
    evaluator: dict[str, Any],
    live_contract: dict[str, Any],
    stable_pids: set[int],
    state_root: Path,
    context_checkpoints: int,
    server_launch_args: tuple[str, ...] = (),
    moe_server_args: tuple[str, ...] = checkpoint_control.DEFAULT_MOE_SERVER_ARGS,
) -> Any:
    readiness_control = startup_readiness_control(evaluator)
    return checkpoint_control.ScopedCheckpointDiscoverySidecar(
        binary,
        model,
        evaluator,
        live_contract,
        detached=False,
        stable_pids=stable_pids,
        readiness_control=readiness_control,
        prelaunch_evidence={"stable_pids": sorted(stable_pids)},
        readiness_deadline_at=None,
        state_root=state_root,
        advisory_wddm=True,
        context_checkpoints=context_checkpoints,
        server_launch_args=server_launch_args,
        moe_server_args=moe_server_args,
        readiness_deadline_seconds_after_identity=float(readiness_control["readiness_deadline_seconds"]),
        stable_health_recovery_policy=startup_health_recovery_policy(),
    )


def evaluate(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    root: Mapping[str, Any],
    baseline_private: int | None,
) -> dict[str, Any]:
    panel = base.evaluate_panel(
        sidecar=sidecar,
        codec=codec,
        props=props,
        root=root,
        baseline_private=baseline_private,
        panel_override=panel_for(root),
        branch_order_override=PANEL_ORDER,
    )
    qualified = bool(panel["qualified"])
    return {
        "status": "complete",
        "mechanism": "direct-only-unused-water-panel-qualification",
        "verdict": "accept" if qualified else "reject",
        "classification": "water-direct-panel-qualified" if qualified else "water-direct-panel-rejected",
        "qualification_threshold": {"correct": PANEL_SIZE, "total": PANEL_SIZE},
        "model": "Agents-A1",
        "carrier_operations": 0,
        "snapshot_operations": 0,
        "cache_enabled_branches": 0,
        "panel": panel,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, default=harness.DEFAULT_BINARY)
    parser.add_argument("--model", type=Path, default=harness.DEFAULT_MODEL)
    parser.add_argument("--ctx-checkpoints", type=int, choices=(0,), default=0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--server-log-output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    binary = args.binary.resolve(strict=True)
    require_pinned_binary(binary)
    model = args.model.resolve(strict=True)
    repository = Path(__file__).resolve().parents[1]
    corpus = harness.carrier.load_public_corpus(repository)
    roots = {str(item["root_id"]): item for item in corpus["roots"]}
    evaluator, live_contract = harness.load_discovery_sidecar_contract()
    stable_pids = harness.live_runtime.require_stable()
    harness.require(len(stable_pids) == 1, "water-panel qualifier requires the sole stable listener")
    harness.require(not harness.live_runtime.listener_pids(harness.live_runtime.PORT), "frontier port is occupied")
    state_root = Path(tempfile.mkdtemp(prefix="neo3000-water-panel-qualifier-"))
    sidecar: Any | None = None
    result: dict[str, Any] | None = None
    cleanup: Mapping[str, Any] | None = None
    error: BaseException | None = None
    if args.server_log_output is not None:
        os.environ["LLAMA_ARG_LOG_VERBOSITY"] = "1000"
        os.environ["LLAMA_SERVER_SLOTS_DEBUG"] = "1"
    try:
        sidecar = build_sidecar(
            binary=binary,
            model=model,
            evaluator=evaluator,
            live_contract=live_contract,
            stable_pids=set(stable_pids),
            state_root=state_root,
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
            root=roots[ROOT_ID],
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
    harness.require(result is not None, "water-panel qualifier result is missing")
    result["cleanup"] = cleanup
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
