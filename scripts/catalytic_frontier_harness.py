#!/usr/bin/env python3
"""Retryable discovery harness for process-local catalytic inference.

This intentionally omits one-shot authority, HMAC packaging, preregistration,
claim ledgers, and publication machinery.  It exercises only the mechanism:
exact emitted-token roots, strict-extension branches, slot snapshot/restore,
same-token direct controls, a counted minimal-output closure probe, and actual
runtime accounting.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Sequence

import holostate_live as live_runtime
import holostate_v1_multi_branch_runtime_native_carrier_evaluation as carrier


DEFAULT_BINARY = Path(r"D:\CCC 2.0\AI\Neo3000\build\stable\bin\Release\llama-server.exe")
DEFAULT_MODEL = Path(
    r"D:\Reneshizzle\Apps\LM Studio\InternScience\Agents-A1-Q4_K_M-GGUF\Agents-A1-Q4_K_M.gguf"
)
EXPECTED = {
    "mb-runtime-datacenter-01": {"task_a": "B", "branch-1": "A", "branch-2": "C"},
    "mb-runtime-coldchain-02": {"task_a": "C", "branch-1": "A", "branch-2": "B"},
    "mb-runtime-orbit-03": {"task_a": "C", "branch-1": "A", "branch-2": "B"},
    "mb-runtime-water-04": {"task_a": "C", "branch-1": "B", "branch-2": "A"},
}
HOST_GROWTH_CEILING_BYTES = 4 * 1024**3
WDDM_CEILING_BYTES = 6000 * 1024**2


class FrontierHarnessError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FrontierHarnessError(message)


def load_discovery_sidecar_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    """Load only the executable sidecar contract used by retryable discovery.

    The frozen one-shot evaluator lock also binds task boards, claim ledgers,
    and publication machinery. Those identities are intentionally outside a
    retryable mechanism probe. Runtime/model/template identities and launch
    safety remain validated here and again by ``LiveSidecar`` at launch.
    """
    evaluator = live_runtime.load_json(live_runtime.EVALUATOR_PATH)
    require(isinstance(evaluator, dict), "runtime evaluator is not an object")
    contract = live_runtime.validate_holostate_contract(
        evaluator.get("holostate_live_contract", {})
    )
    model = evaluator.get("model", {})
    require(
        isinstance(model, Mapping)
        and model.get("sha256") == live_runtime.EXPECTED_MODEL_SHA256
        and model.get("size_bytes") == live_runtime.EXPECTED_MODEL_SIZE,
        "runtime evaluator model identity differs from Agents-A1",
    )
    memory = evaluator.get("memory", {})
    require(
        isinstance(memory, Mapping)
        and memory.get("candidate_vram_mib_ceiling") == live_runtime.VRAM_CEILING_MIB
        and isinstance(memory.get("sample_interval_seconds"), (int, float))
        and float(memory["sample_interval_seconds"]) > 0
        and isinstance(memory.get("telemetry_grace_seconds"), (int, float))
        and float(memory["telemetry_grace_seconds"]) >= 0,
        "runtime evaluator memory policy is invalid",
    )
    timeouts = evaluator.get("timeouts", {})
    require(
        isinstance(timeouts, Mapping)
        and isinstance(timeouts.get("candidate_health_seconds"), (int, float))
        and float(timeouts["candidate_health_seconds"]) > 0,
        "runtime evaluator candidate readiness timeout is invalid",
    )
    return evaluator, contract


def discovery_binary_identity(binary: Path) -> dict[str, Any]:
    resolved = binary.resolve()
    require(resolved.is_file(), f"discovery binary is missing: {resolved}")
    sha256 = live_runtime.sha256_file(resolved)
    version = live_runtime.binary_version(resolved)
    require(bool(re.fullmatch(r"[0-9A-F]{64}", sha256)), "discovery binary hash is malformed")
    require(
        bool(re.fullmatch(r"[1-9][0-9]* \([0-9a-f]{7,40}\)", version)),
        "discovery binary runtime version is malformed",
    )
    return {"path": str(resolved), "sha256": sha256, "runtime_version": version}


class DiscoverySidecar(live_runtime.LiveSidecar):
    """LiveSidecar with an exact experimental binary identity frozen at construction."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.discovery_expected_binary = discovery_binary_identity(self.binary)
        if self.readiness_control is not None:
            expected_model = {
                "path": str(self.model),
                "sha256": live_runtime.EXPECTED_MODEL_SHA256,
                "size_bytes": live_runtime.EXPECTED_MODEL_SIZE,
            }
            require(
                self.preverified_binary_identity in (None, self.discovery_expected_binary),
                "controlled discovery binary identity changed before construction",
            )
            require(
                self.preverified_model_identity in (None, expected_model),
                "controlled discovery model identity changed before construction",
            )
            self.preverified_binary_identity = dict(self.discovery_expected_binary)
            self.preverified_model_identity = expected_model

    def runtime_identities(self) -> tuple[dict[str, Any], dict[str, Any]]:
        if self.readiness_control is not None:
            return super().runtime_identities()
        current_binary = discovery_binary_identity(self.binary)
        require(
            current_binary == self.discovery_expected_binary,
            "discovery binary identity changed before launch",
        )
        return current_binary, live_runtime.verify_model(self.model, self.evaluator)



def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def request_json(method: str, url: str, payload: Mapping[str, Any] | None = None) -> tuple[dict[str, Any], float]:
    data = carrier.canonical_json_bytes(payload) if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=900) as response:
        raw = response.read()
    elapsed = time.monotonic() - started
    value = json.loads(raw.decode("utf-8"))
    require(isinstance(value, dict), "control response is not an object")
    return dict(value), elapsed


def execution_dict(execution: Any) -> dict[str, Any]:
    return {
        name: getattr(execution, name, None)
        for name in carrier.CAPTURE_EXECUTION_FIELDS
    }


def validate_minimal_closure_terminal(execution: Mapping[str, Any]) -> dict[str, Any]:
    generated = execution.get("generated_token_ids")
    stop = execution.get("terminal_stop_evidence")
    require(execution.get("http_status") == 200, "closure HTTP status is invalid")
    require(
        isinstance(stop, Mapping) and stop.get("observed") is True and stop.get("stop") is True,
        "closure terminal stop evidence is invalid",
    )
    require(execution.get("finish_reason") == "limit", "closure finish reason is invalid")
    require(
        execution.get("completion_tokens") == 1
        and execution.get("generated_token_count") == 1
        and isinstance(generated, list)
        and len(generated) == 1
        and type(generated[0]) is int
        and execution.get("completion_token_count_match") is True,
        "closure must emit exactly one counted token",
    )
    expected_hash = carrier.sha256_bytes(carrier.canonical_json_bytes(generated))
    require(execution.get("generated_token_sha256") == expected_hash, "closure token hash is invalid")
    return {
        "terminal_http_status": 200,
        "terminal_stop_evidence": dict(stop),
        "terminal_finish_reason": "limit",
        "terminal_evidence_passed": True,
        "generated_token_count": 1,
        "generated_token_sha256": expected_hash,
        "completion_tokens": 1,
        "operation_kind": "minimal-output-root-readdress",
    }


def run_completion(
    sidecar: Any,
    label: str,
    payload: Mapping[str, Any],
    *,
    operation_kind: str = "model-generation",
    recorder: Any | None = None,
    guard_phase_observer: Any | None = None,
    batch_owned_request: bool = False,
) -> dict[str, Any]:
    print(f"[frontier] start {label}", flush=True)
    started = time.monotonic()
    raw_recorder = recorder if recorder is not None else (lambda _line: None)
    require(
        not (guard_phase_observer is not None and batch_owned_request),
        "profiled and batch-owned guards cannot be combined",
    )
    guarded_kwargs: dict[str, Any] = {"timeout": 1_000}
    if guard_phase_observer is not None:
        guarded_kwargs["phase_observer"] = guard_phase_observer
    guarded_call = (
        sidecar.guarded_batch_member
        if batch_owned_request
        else sidecar.guarded_profiled
        if guard_phase_observer is not None
        else sidecar.guarded
    )
    execution = guarded_call(
        f"frontier:{label}",
        lambda: carrier._stream_raw_completion(
            port=live_runtime.PORT,
            payload=payload,
            recorder=raw_recorder,
        ),
        **guarded_kwargs,
    )
    wall_seconds = time.monotonic() - started
    normalized = execution_dict(execution)
    try:
        if label.endswith(":closure-readdress"):
            terminal = validate_minimal_closure_terminal(normalized)
        else:
            terminal = carrier.validate_inference_terminal_evidence(
                normalized,
                operation_kind=operation_kind,
            )
    except Exception as exc:
        raise FrontierHarnessError(
            f"{label}: terminal validation failed: {exc}; execution="
            f"{json.dumps(normalized, ensure_ascii=False, sort_keys=True)}"
        ) from exc
    prompt = int(normalized["prompt_tokens"])
    cached = int(normalized["cached_prompt_tokens"])
    completion = int(normalized["completion_tokens"])
    require(prompt > 0 and 0 <= cached <= prompt and completion >= 0, f"{label}: invalid token accounting")
    record = {
        "label": label,
        "content": str(normalized.get("content") or ""),
        "execution": normalized,
        "terminal": terminal,
        "prompt_tokens": prompt,
        "cached_prompt_tokens": cached,
        "fresh_prompt_tokens": prompt - cached,
        "completion_tokens": completion,
        "fresh_model_tokens": prompt - cached + completion,
        "wall_seconds": wall_seconds,
    }
    print(
        f"[frontier] done {label}: prompt={prompt} cached={cached} "
        f"completion={completion} wall={wall_seconds:.3f}s",
        flush=True,
    )
    return record


def process_resources(sidecar: Any, baseline_private: int | None) -> dict[str, Any]:
    host_private: int | None = None
    if sidecar.process is not None:
        info = live_runtime.process_info(sidecar.process.pid)
        if isinstance(info, Mapping) and isinstance(info.get("private_bytes"), int):
            host_private = int(info["private_bytes"])
    telemetry = sidecar.telemetry()
    peak_wddm = int(telemetry["peak_bytes"]) if isinstance(telemetry.get("peak_bytes"), int) else None
    growth = (
        host_private - baseline_private
        if host_private is not None and baseline_private is not None
        else None
    )
    require(growth is None or growth <= HOST_GROWTH_CEILING_BYTES, "unsafe host-private growth")
    require(peak_wddm is None or peak_wddm <= WDDM_CEILING_BYTES, "unsafe WDDM residency")
    return {
        "host_private_bytes": host_private,
        "host_private_growth_bytes": growth,
        "peak_wddm_bytes": peak_wddm,
        "wddm_sample_count": telemetry.get("sample_count"),
        "wddm_failure_reason": telemetry.get("failure_reason"),
    }


def snapshot_action(*, action: str, filename: str) -> tuple[dict[str, Any], float]:
    require(action in {"save", "restore"}, "unsupported snapshot action")
    return request_json(
        "POST",
        f"http://127.0.0.1:{live_runtime.PORT}/slots/0?action={action}",
        {"filename": filename},
    )



def ram_root_action(*, action: str, root_id: str) -> tuple[dict[str, Any], float]:
    require(action in {"root-save", "root-restore", "root-erase"}, "unsupported RAM-root action")
    require(bool(root_id), "RAM root ID is empty")
    return request_json(
        "POST",
        f"http://127.0.0.1:{live_runtime.PORT}/slots/0?action={action}",
        {"root_id": root_id},
    )

def token_summary(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: record[key]
        for key in (
            "prompt_tokens",
            "cached_prompt_tokens",
            "fresh_prompt_tokens",
            "completion_tokens",
            "fresh_model_tokens",
            "wall_seconds",
        )
    }


def root_capture(record: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    execution = dict(record["execution"])
    return {
        "execution": execution,
        "capture_sha256": carrier.json_sha256({"execution": execution}),
        "model_request_sha256": carrier.json_sha256(payload),
    }


def run_root(
    *,
    sidecar: Any,
    codec: carrier.SidecarPromptCodec,
    props: Mapping[str, Any],
    snapshot_root: Path,
    root: Mapping[str, Any],
    baseline_private: int | None,
) -> dict[str, Any]:
    root_id = str(root["root_id"])
    expected = EXPECTED[root_id]
    prompt_text = codec.render_messages(carrier.task_a_messages(root), carrier.CHAT_TEMPLATE_KWARGS)
    prompt_tokens = codec.tokenize(prompt_text)
    task_a_payload = carrier._task_a_payload(prompt_tokens, seed=carrier.derive_seed(root_id, "task-a"))
    task_a = run_completion(sidecar, f"{root_id}:task-a", task_a_payload)
    parsed_task_a = carrier.parse_task_a_output(task_a["content"])
    require(parsed_task_a["answer"] == expected["task_a"], f"{root_id}: Task-A answer is incorrect")
    retained = carrier.derive_retained_root(root_capture(task_a, task_a_payload), prompt_tokens, codec, props)

    snapshot_name = f"{root_id}.bin"
    initial_snapshot_path = snapshot_root / snapshot_name
    save_response, save_seconds = snapshot_action(action="save", filename=snapshot_name)
    require(save_response.get("n_saved") == retained["retained_root_token_count"], "snapshot saved token count differs")
    initial_snapshot = initial_snapshot_path.read_bytes()
    snapshot_sha256 = sha256_bytes(initial_snapshot)

    branch_records: list[dict[str, Any]] = []
    direct_records: list[dict[str, Any]] = []
    restore_controls: list[dict[str, Any]] = []
    suffixes: dict[int, dict[str, Any]] = {}
    complete_tokens: dict[int, list[int]] = {}
    for number in (1, 2):
        suffixes[number] = carrier.derive_continuation_suffix(
            codec,
            terminal_eog_id=int(retained["terminal_stop_identity"]["token_id"]),
            user_content=carrier.branch_user_content(root, number),
        )
        complete_tokens[number] = [*retained["retained_root_tokens"], *suffixes[number]["suffix_tokens"]]

    first = int(carrier.FIRST_BRANCH[root_id])
    branch_order = (first, 3 - first)
    for ordinal, number in enumerate(branch_order, start=1):
        if ordinal > 1:
            response, seconds = snapshot_action(action="restore", filename=snapshot_name)
            require(response.get("n_restored") == retained["retained_root_token_count"], "branch restore token count differs")
            restore_controls.append({"stage": f"before-branch-{number}", "wall_seconds": seconds, **response})
        payload = carrier._branch_payload(
            complete_tokens[number],
            seed=carrier.derive_seed(root_id, f"branch-{number}"),
            cache_prompt=True,
        )
        record = run_completion(sidecar, f"{root_id}:branch-{number}:catalytic", payload)
        answer = carrier.parse_branch_output(record["content"])
        record.update({"branch_number": number, "answer": answer, "correct": answer == expected[f"branch-{number}"]})
        require(record["correct"], f"{root_id}: catalytic branch {number} is incorrect")
        require(
            record["cached_prompt_tokens"] == retained["retained_root_token_count"],
            f"{root_id}: catalytic branch {number} did not reuse the complete retained root",
        )
        branch_records.append(record)
        process_resources(sidecar, baseline_private)

    response, seconds = snapshot_action(action="restore", filename=snapshot_name)
    require(response.get("n_restored") == retained["retained_root_token_count"], "closure restore token count differs")
    restore_controls.append({"stage": "closure-restore", "wall_seconds": seconds, **response})

    closed_snapshot_name = f"{root_id}.closed.bin"
    closed_response, closed_save_seconds = snapshot_action(action="save", filename=closed_snapshot_name)
    closed_snapshot = (snapshot_root / closed_snapshot_name).read_bytes()
    byte_exact_closure = initial_snapshot == closed_snapshot

    verification_suffix = carrier.derive_continuation_suffix(
        codec,
        terminal_eog_id=int(retained["terminal_stop_identity"]["token_id"]),
        user_content=carrier.verification_user_content(root_id),
    )
    verification_tokens = [*retained["retained_root_tokens"], *verification_suffix["suffix_tokens"]]
    closure_payload = carrier._branch_payload(
        verification_tokens,
        seed=carrier.derive_seed(root_id, "branch-1"),
        cache_prompt=True,
        n_predict=1,
    )
    closure = run_completion(sidecar, f"{root_id}:closure-readdress", closure_payload)
    require(
        closure["cached_prompt_tokens"] == retained["retained_root_token_count"],
        f"{root_id}: closure did not readdress the complete executable root",
    )

    final_restore_response, final_restore_seconds = snapshot_action(action="restore", filename=snapshot_name)
    require(final_restore_response.get("n_restored") == retained["retained_root_token_count"], "final restore token count differs")
    restore_controls.append({"stage": "final-root-restore", "wall_seconds": final_restore_seconds, **final_restore_response})

    for number in (1, 2):
        payload = carrier._branch_payload(
            complete_tokens[number],
            seed=carrier.derive_seed(root_id, f"branch-{number}"),
            cache_prompt=False,
        )
        record = run_completion(sidecar, f"{root_id}:branch-{number}:direct", payload)
        answer = carrier.parse_branch_output(record["content"])
        record.update({"branch_number": number, "answer": answer, "correct": answer == expected[f"branch-{number}"]})
        require(record["correct"], f"{root_id}: direct branch {number} is incorrect")
        require(record["cached_prompt_tokens"] == 0, f"{root_id}: direct branch {number} was not fresh")
        direct_records.append(record)
        process_resources(sidecar, baseline_private)

    carrier_fresh = int(task_a["fresh_model_tokens"])
    branch_fresh = sum(int(record["fresh_model_tokens"]) for record in branch_records)
    closure_fresh = int(closure["fresh_model_tokens"])
    catalytic_total = carrier_fresh + branch_fresh + closure_fresh
    direct_total = sum(int(record["fresh_model_tokens"]) for record in direct_records)
    amplification = direct_total / catalytic_total if catalytic_total else None
    resources = process_resources(sidecar, baseline_private)
    return {
        "root_id": root_id,
        "model": "Agents-A1",
        "geometry": root["task_a"]["question"],
        "utility": {
            "task_a_correct": True,
            "catalytic_correct": sum(bool(record["correct"]) for record in branch_records),
            "direct_correct": sum(bool(record["correct"]) for record in direct_records),
            "total_branches": 2,
            "route_answers_equal": all(
                next(item["answer"] for item in branch_records if item["branch_number"] == number)
                == next(item["answer"] for item in direct_records if item["branch_number"] == number)
                for number in (1, 2)
            ),
        },
        "reuse": {
            "retained_root_tokens": retained["retained_root_token_count"],
            "catalytic_cached_tokens": [record["cached_prompt_tokens"] for record in branch_records],
            "closure_cached_tokens": closure["cached_prompt_tokens"],
            "complete_root_reuse": all(
                record["cached_prompt_tokens"] == retained["retained_root_token_count"]
                for record in branch_records
            ),
        },
        "fresh_model_compute": {
            "carrier_creation": carrier_fresh,
            "branches": branch_fresh,
            "closure": closure_fresh,
            "catalytic_total": catalytic_total,
            "same_information_direct_total": direct_total,
            "compute_amplification": amplification,
            "advantage": catalytic_total < direct_total,
        },
        "carrier_controls": {
            "initial_snapshot_bytes": len(initial_snapshot),
            "initial_snapshot_sha256": snapshot_sha256,
            "save_wall_seconds": save_seconds,
            "restore_controls": restore_controls,
            "closed_snapshot_bytes": len(closed_snapshot),
            "closed_snapshot_sha256": sha256_bytes(closed_snapshot),
            "closed_snapshot_save_wall_seconds": closed_save_seconds,
            "closed_snapshot_response": closed_response,
            "byte_exact_snapshot_closure": byte_exact_closure,
        },
        "task_a": token_summary(task_a),
        "catalytic_branches": [
            {"branch_number": item["branch_number"], "answer": item["answer"], **token_summary(item)}
            for item in branch_records
        ],
        "closure": token_summary(closure),
        "direct_branches": [
            {"branch_number": item["branch_number"], "answer": item["answer"], **token_summary(item)}
            for item in direct_records
        ],
        "resources": resources,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--root-id", choices=tuple(EXPECTED), default="mb-runtime-datacenter-01")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    binary = args.binary.resolve(strict=True)
    model = args.model.resolve(strict=True)
    repository = Path(__file__).resolve().parents[1]
    corpus = carrier.load_public_corpus(repository)
    roots = {str(item["root_id"]): item for item in corpus["roots"]}
    evaluator, live_contract = load_discovery_sidecar_contract()
    stable_pids = live_runtime.require_stable()
    require(len(stable_pids) == 1, "frontier harness requires the existing sole stable listener")
    require(not live_runtime.listener_pids(live_runtime.PORT), "frontier sidecar port is occupied")
    state_root = Path(tempfile.mkdtemp(prefix="neo3000-catalytic-frontier-"))
    snapshots = state_root / "snapshots"
    sidecar: Any | None = None
    result: dict[str, Any] | None = None
    cleanup: Mapping[str, Any] | None = None
    error: BaseException | None = None
    try:
        sidecar = live_runtime.LiveSidecar(
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
        codec = carrier.SidecarPromptCodec(live_runtime.PORT)
        props = codec.props()
        result = run_root(
            sidecar=sidecar,
            codec=codec,
            props=props,
            snapshot_root=snapshots,
            root=roots[args.root_id],
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
        cleanup = live_runtime.safe_sidecar_cleanup(sidecar)
        shutil.rmtree(state_root, ignore_errors=True)

    if error is not None:
        print(json.dumps({
            "status": "engineering-failure",
            "error_type": type(error).__name__,
            "error": str(error),
            "cleanup": cleanup,
        }, ensure_ascii=False, indent=2))
        return 1
    require(result is not None, "frontier result is missing")
    result["cleanup"] = cleanup
    result["status"] = "complete"
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
