#!/usr/bin/env python3
"""Execute neo-exp-0088 on the native Linux sidecar exactly once."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping

import catalytic_frontier_harness as harness
import catalytic_frontier_linux_sidecar as linux_sidecar
import catalytic_frontier_live_terminal_boundary as live
import catalytic_frontier_successor_terminal_pipeline as predecessor
import catalytic_frontier_terminal_logits_continuation as terminal


EXPERIMENT_ID = live.EXPERIMENT_ID
ATTEMPT_ID = live.ATTEMPT_ID
ROOT = Path(__file__).resolve().parents[1]
BASE_ROOT_ID = f"{EXPERIMENT_ID}-base-689"
SEED_TERMINAL_ROOT_ID = f"{EXPERIMENT_ID}-seed-terminal-690"
ROUTES = ("live-terminal", "root-only", "materialized")
TRIAL_ROUTE_ORDERS = (
    ("live-terminal", "root-only", "materialized"),
    ("root-only", "materialized", "live-terminal"),
    ("materialized", "live-terminal", "root-only"),
)
DEFAULT_BINARY = ROOT / "build" / "linux-cuda-0088" / "bin" / "llama-server"
DEFAULT_MODEL = Path(
    "/run/media/reneshizzle/860_1/Reneshizzle/Apps/LM Studio/"
    "InternScience/Agents-A1-Q4_K_M-GGUF/Agents-A1-Q4_K_M.gguf"
)
DEFAULT_OUTPUT = ROOT / "lab" / f"{EXPERIMENT_ID}.local.json"
DEFAULT_LOCK = ROOT / "build" / "linux-catalytic" / f"{EXPERIMENT_ID}.active-lock.json"
DEFAULT_RUN_PARENT = ROOT / "build" / "linux-catalytic"


class ExperimentError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ExperimentError(message)


def configure_predecessor_identity() -> None:
    predecessor.EXPERIMENT_ID = EXPERIMENT_ID
    predecessor.ATTEMPT_ID = ATTEMPT_ID
    predecessor.BASE_ROOT_ID = BASE_ROOT_ID
    predecessor.SEED_TERMINAL_ROOT_ID = SEED_TERMINAL_ROOT_ID


def cuda_linked(binary: Path) -> bool:
    completed = subprocess.run(
        ["ldd", str(binary)],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0 and "libggml-cuda" in completed.stdout


def acquire_preserved_lock(path: Path, expected_commit: str) -> dict[str, Any]:
    payload = {
        "id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "expected_commit": expected_commit,
        "pid": os.getpid(),
        "created_unix_ns": time.time_ns(),
        "meaning": "exclusive native Linux launch custody",
    }
    return {
        **terminal.write_exclusive_json(path, payload),
        "payload": payload,
    }


def release_preserved_lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"released": False, "reason": "active-lock-absent"}
    released = path.with_name(
        path.stem + f".released-{time.time_ns()}" + path.suffix
    )
    path.rename(released)
    return {
        "released": True,
        "active_path": str(path),
        "preserved_path": str(released),
        "sha256": harness.live_runtime.sha256_file(released),
    }


def task_and_branch(
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    prepared: Mapping[str, Any],
) -> tuple[dict[str, Any], list[int], Mapping[str, Any]]:
    return predecessor.task_and_branch(sidecar, codec, props, prepared)


def run_sequence(route: str, **kwargs: Any) -> dict[str, Any]:
    started = time.monotonic()
    if route == "live-terminal":
        result = live.run_live_sequence(**kwargs)
    else:
        common = {
            key: value
            for key, value in kwargs.items()
            if key not in {"baseline_private", "run_successor_negative"}
        }
        if route == "root-only":
            result = predecessor.run_root_only_sequence(**common)
        elif route == "materialized":
            common.pop("base_root", None)
            result = predecessor.run_materialized_sequence(**common)
        else:
            raise ExperimentError(f"unsupported route: {route}")
    result = dict(result)
    result["component_accounted_wall_seconds"] = float(
        result["fully_charged_wall_seconds"]
    )
    result["fully_charged_wall_seconds"] = time.monotonic() - started
    result["fully_charged_wall_semantics"] = (
        "whole-route monotonic wall including initial carrier preparation, "
        "protocol, telemetry, rematerialization, projection, and closure"
    )
    return result


def setup_seed(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    prepared: Mapping[str, Any],
) -> dict[str, Any]:
    task, branch_tokens, retained = task_and_branch(
        sidecar,
        codec,
        props,
        prepared,
    )
    base_tokens = list(branch_tokens[: predecessor.EXPECTED_BASE_TOKENS])
    base_materialization = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:base-materialize",
        terminal.completion_payload(base_tokens, cache_prompt=False, n_predict=0),
        operation_kind="zero-output-root-readdress",
    )
    require(
        base_materialization["cached_prompt_tokens"] == 0
        and base_materialization["fresh_prompt_tokens"]
        == predecessor.EXPECTED_BASE_TOKENS,
        "base materialization geometry changed",
    )
    base_root = predecessor.root_action(
        action="root-save",
        root_id=BASE_ROOT_ID,
        n_tokens=predecessor.EXPECTED_BASE_TOKENS,
        n_device_bytes=predecessor.EXPECTED_BASE_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=1,
        expected_total_device_bytes_after=predecessor.EXPECTED_BASE_DEVICE_BYTES,
    )
    base_restore = predecessor.root_action(
        action="root-restore",
        root_id=BASE_ROOT_ID,
        n_tokens=predecessor.EXPECTED_BASE_TOKENS,
        n_device_bytes=predecessor.EXPECTED_BASE_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=1,
        expected_total_device_bytes_after=predecessor.EXPECTED_BASE_DEVICE_BYTES,
        expected=base_root,
    )
    seed_capture_payload = terminal.completion_payload(
        branch_tokens,
        cache_prompt=True,
        n_predict=0,
    )
    seed_capture_payload["neo3000_capture_terminal_logits"] = True
    seed_capture = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:seed-terminal-capture",
        seed_capture_payload,
        operation_kind="zero-output-root-readdress",
    )
    require(
        seed_capture["cached_prompt_tokens"]
        == predecessor.EXPECTED_BASE_TOKENS
        and seed_capture["fresh_prompt_tokens"] == 1,
        "seed terminal capture geometry changed",
    )
    seed_root = predecessor.root_action(
        action="root-save",
        root_id=SEED_TERMINAL_ROOT_ID,
        n_tokens=predecessor.EXPECTED_BRANCH_TOKENS,
        n_device_bytes=predecessor.EXPECTED_SEED_TERMINAL_DEVICE_BYTES,
        terminal_logits=True,
        expected_roots_after=2,
        expected_total_device_bytes_after=(
            predecessor.EXPECTED_BASE_DEVICE_BYTES
            + predecessor.EXPECTED_SEED_TERMINAL_DEVICE_BYTES
        ),
        include_terminal_logits=True,
    )
    seed_restore = predecessor.root_action(
        action="root-restore",
        root_id=SEED_TERMINAL_ROOT_ID,
        n_tokens=predecessor.EXPECTED_BRANCH_TOKENS,
        n_device_bytes=predecessor.EXPECTED_SEED_TERMINAL_DEVICE_BYTES,
        terminal_logits=True,
        expected_roots_after=2,
        expected_total_device_bytes_after=(
            predecessor.EXPECTED_BASE_DEVICE_BYTES
            + predecessor.EXPECTED_SEED_TERMINAL_DEVICE_BYTES
        ),
        expected=seed_root,
        require_terminal_logits=True,
    )
    seed_payload = terminal.completion_payload(branch_tokens, cache_prompt=True)
    seed_payload.update(
        neo3000_use_terminal_logits=True,
        neo3000_terminal_root_id=SEED_TERMINAL_ROOT_ID,
        neo3000_terminal_logits_fnv64=seed_root["terminal_logits_fnv64"],
    )
    seed_record = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:seed-terminal-consumer",
        seed_payload,
        batch_owned_request=True,
    )
    seed_state = predecessor.validate_generated_state(
        seed_record,
        codec=codec,
        props=props,
        expected_answer="C",
    )
    lineage_child_tokens = predecessor.rebase.compact_child_tokens(
        branch_tokens,
        seed_state,
    )
    require(
        predecessor.canonical_sha256(lineage_child_tokens)
        == predecessor.EXPECTED_CHILD_SHA256["C"],
        "seed child identity changed",
    )
    lineage_child = predecessor.root_action(
        action="root-save",
        root_id=f"{EXPERIMENT_ID}-lineage-child-C",
        n_tokens=predecessor.EXPECTED_CHILD_TOKENS,
        n_device_bytes=predecessor.EXPECTED_CHILD_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=3,
        expected_total_device_bytes_after=predecessor.EXPECTED_SETUP_THREE_ROOT_DEVICE_BYTES,
    )
    lineage_erase = predecessor.root_action(
        action="root-erase",
        root_id=str(lineage_child["root_id"]),
        n_tokens=predecessor.EXPECTED_CHILD_TOKENS,
        n_device_bytes=predecessor.EXPECTED_CHILD_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=2,
        expected_total_device_bytes_after=(
            predecessor.EXPECTED_BASE_DEVICE_BYTES
            + predecessor.EXPECTED_SEED_TERMINAL_DEVICE_BYTES
        ),
        expected=lineage_child,
    )
    seed_erase = predecessor.root_action(
        action="root-erase",
        root_id=SEED_TERMINAL_ROOT_ID,
        n_tokens=predecessor.EXPECTED_BRANCH_TOKENS,
        n_device_bytes=predecessor.EXPECTED_SEED_TERMINAL_DEVICE_BYTES,
        terminal_logits=True,
        expected_roots_after=1,
        expected_total_device_bytes_after=predecessor.EXPECTED_BASE_DEVICE_BYTES,
        expected=seed_root,
    )
    return {
        "task": task,
        "branch_tokens": branch_tokens,
        "retained": retained,
        "base_materialization": base_materialization,
        "base_root": base_root,
        "base_restore": base_restore,
        "seed_capture": seed_capture,
        "seed_root": seed_root,
        "seed_restore": seed_restore,
        "seed_record": seed_record,
        "seed_state": seed_state,
        "lineage_child_sha256": predecessor.canonical_sha256(
            lineage_child_tokens
        ),
        "lineage_child": lineage_child,
        "lineage_erase": lineage_erase,
        "seed_erase": seed_erase,
    }


def generated_state(route: Mapping[str, Any], edge: Mapping[str, Any]) -> Mapping[str, Any]:
    if route["route"] == "live-terminal":
        return edge["consumer"]["state"]
    return edge["successor"]["state"]


def request_identity(route: Mapping[str, Any], edge: Mapping[str, Any]) -> str:
    if route["route"] == "live-terminal":
        return str(edge["live"]["contract"]["input_boundary_id"])
    return str(edge["successor"]["ancestry"]["request_token_sha256"])


def evaluate(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    prepared: Mapping[str, Any],
) -> dict[str, Any]:
    setup = setup_seed(
        sidecar=sidecar,
        codec=codec,
        props=props,
        prepared=prepared,
    )
    ownership: list[dict[str, Any]] = []
    for boundary in ("pre-r2-batch",):
        started = time.monotonic()
        ownership.append(
            {
                "boundary": boundary,
                "evidence": sidecar.exact_ownership(boundary),
                "wall_seconds": time.monotonic() - started,
            }
        )
    common = {
        "sidecar": sidecar,
        "codec": codec,
        "props": props,
        "base_root": setup["base_root"],
        "branch_tokens": setup["branch_tokens"],
        "seed_state": setup["seed_state"],
        "baseline_private": None,
    }
    warmup = {
        route: run_sequence(
            route,
            **common,
            trial_label=f"warmup-{route}",
            run_successor_negative=route == "live-terminal",
        )
        for route in ROUTES
    }
    counted: list[dict[str, Any]] = []
    for trial, order in enumerate(TRIAL_ROUTE_ORDERS, start=1):
        routes: dict[str, Any] = {}
        for route in order:
            routes[route] = run_sequence(
                route,
                **common,
                trial_label=f"trial-{trial}-{route}",
                run_successor_negative=False,
            )
        counted.append(
            {"trial": trial, "route_order": list(order), "routes": routes}
        )
    started = time.monotonic()
    ownership.append(
        {
            "boundary": "post-r2-batch",
            "evidence": sidecar.exact_ownership("post-r2-batch"),
            "wall_seconds": time.monotonic() - started,
        }
    )
    tool_canary = predecessor.run_tool_canary(sidecar)
    base_erase = predecessor.root_action(
        action="root-erase",
        root_id=BASE_ROOT_ID,
        n_tokens=predecessor.EXPECTED_BASE_TOKENS,
        n_device_bytes=predecessor.EXPECTED_BASE_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=0,
        expected_total_device_bytes_after=0,
        expected=setup["base_root"],
    )
    resources_after = harness.process_resources(sidecar, None)

    ownership_total = sum(float(item["wall_seconds"]) for item in ownership)
    ownership_share = ownership_total / (predecessor.COUNTED_TRIALS * len(ROUTES))
    for trial in counted:
        for route in ROUTES:
            trial["routes"][route]["fully_charged_wall_seconds"] += ownership_share

    live_walls = [
        float(trial["routes"]["live-terminal"]["fully_charged_wall_seconds"])
        for trial in counted
    ]
    root_walls = [
        float(trial["routes"]["root-only"]["fully_charged_wall_seconds"])
        for trial in counted
    ]
    direct_walls = [
        float(trial["routes"]["materialized"]["fully_charged_wall_seconds"])
        for trial in counted
    ]
    live_ttft = [
        float(edge["consumer"]["restore_inclusive_ttft_seconds"])
        for trial in counted
        for edge in trial["routes"]["live-terminal"]["edges"]
    ]
    root_ttft = [
        float(edge["successor"]["restore_inclusive_ttft_seconds"])
        for trial in counted
        for edge in trial["routes"]["root-only"]["edges"]
    ]
    ttft_speedup = sum(root_ttft) / sum(live_ttft)
    live_vs_root = sum(root_walls) / sum(live_walls)
    live_vs_direct = sum(direct_walls) / sum(live_walls)
    all_routes = [
        warmup[route] for route in ROUTES
    ] + [
        trial["routes"][route]
        for trial in counted
        for route in ROUTES
    ]
    all_live = [
        warmup["live-terminal"],
        *[trial["routes"]["live-terminal"] for trial in counted],
    ]
    all_edges = [
        (route, edge)
        for route in all_routes
        for edge in route["edges"]
    ]
    contracts = [
        edge["live"]["contract"]
        for route in all_live
        for edge in route["edges"]
    ]
    log_text = Path(str(sidecar.readiness["log_path"])).read_text(
        encoding="utf-8",
        errors="replace",
    )
    live_capture_count = log_text.count(
        "neo3000 one-use live terminal boundary captured"
    )
    live_sample_count = log_text.count(
        "neo3000 one-use live terminal boundary sampled and declared-closed"
    )
    expected_live_samples = (predecessor.WARMUP_TRIALS + predecessor.COUNTED_TRIALS) * 2
    expected_live_captures = expected_live_samples + 1

    gates = {
        "all_state_sequences_C_D_B": all(
            route["observed_states"] == list(predecessor.EXPECTED_STATES)
            for route in all_routes
        ),
        "all_request_output_and_child_identities_exact": all(
            request_identity(route, edge)
            == predecessor.EXPECTED_REQUEST_SHA256[
                predecessor.EDGE_PRIORS[edge["edge"] - 1]
            ]
            and generated_state(route, edge)["generated_token_sha256"]
            == predecessor.EXPECTED_GENERATED_SHA256[
                predecessor.EDGE_SUCCESSORS[edge["edge"] - 1]
            ]
            and edge["child_token_sha256"]
            == predecessor.EXPECTED_CHILD_SHA256[
                predecessor.EDGE_PRIORS[edge["edge"] - 1]
            ]
            and edge["next_child_token_sha256"]
            == predecessor.EXPECTED_CHILD_SHA256[
                predecessor.EDGE_SUCCESSORS[edge["edge"] - 1]
            ]
            for route, edge in all_edges
        ),
        "live_consumers_782_cached_0_fresh": all(
            edge["consumer"]["cached_prompt_tokens"]
            == predecessor.EXPECTED_SUCCESSOR_TOKENS
            and edge["consumer"]["fresh_prompt_tokens"] == 0
            for route in all_live
            for edge in route["edges"]
        ),
        "matched_root_only_695_cached_87_fresh": all(
            edge["successor"]["cached_prompt_tokens"]
            == predecessor.EXPECTED_CHILD_TOKENS
            and edge["successor"]["fresh_prompt_tokens"]
            == predecessor.EXPECTED_SUCCESSOR_FRESH_TOKENS
            for route in [
                warmup["root-only"],
                *[trial["routes"]["root-only"] for trial in counted],
            ]
            for edge in route["edges"]
        ),
        "matched_materialized_0_cached_782_fresh": all(
            edge["successor"]["cached_prompt_tokens"] == 0
            and edge["successor"]["fresh_prompt_tokens"]
            == predecessor.EXPECTED_SUCCESSOR_TOKENS
            for route in [
                warmup["materialized"],
                *[trial["routes"]["materialized"] for trial in counted],
            ]
            for edge in route["edges"]
        ),
        "contracts_unique_and_owner_bound": (
            len({str(contract["boundary_id"]) for contract in contracts})
            == len(contracts)
            and all(
                contract["port_owner"] == live.PORT_OWNER
                and contract["port_type"] == live.PORT_TYPE
                and contract["module_id"] == live.MODULE_ID
                and contract["generation"] == contract["module_ordinal"]
                and contract["restoration_policy"] == live.RESTORATION_CLASS
                for contract in contracts
            )
        ),
        "wrong_owner_rejected_and_poisoned": (
            warmup["live-terminal"]["edges"][0]["live"]["negative"] is not None
            and warmup["live-terminal"]["edges"][0]["live"]["negative"][
                "denial"
            ]["http_status"]
            == 400
        ),
        "one_consumer_per_boundary": all(
            edge["consumer_count"] == 1
            for route in all_live
            for edge in route["edges"]
        ),
        "declared_closure_not_restoration": all(
            route["restoration_class"] == "DECLARED_CLOSURE"
            for route in all_live
        ),
        "live_marker_counts_exact": (
            live_capture_count == expected_live_captures
            and live_sample_count == expected_live_samples
        ),
        "maximum_two_roots_in_live_route": all(
            edge["child_root"]["n_roots_after"] == 2
            for route in all_live
            for edge in route["edges"]
        ),
        "fresh_compute_law_preserved": all(
            trial["routes"]["live-terminal"]["fully_charged_fresh_prompt_tokens"]
            == 186
            and trial["routes"]["root-only"]["fully_charged_fresh_prompt_tokens"]
            == 186
            and trial["routes"]["materialized"]["fully_charged_fresh_prompt_tokens"]
            == 1564
            for trial in counted
        ),
        "whole_route_wall_fully_charged": all(
            route["fully_charged_wall_seconds"]
            >= route["component_accounted_wall_seconds"]
            and route["fully_charged_wall_semantics"].startswith(
                "whole-route monotonic wall"
            )
            for route in all_routes
        ),
        "consumer_ttft_speedup_at_least_5": (
            ttft_speedup >= predecessor.MIN_CONSUMER_TTFT_SPEEDUP
        ),
        "consumer_ttft_live_wins_all_edges": all(
            live_value < root_value
            for live_value, root_value in zip(live_ttft, root_ttft)
        ),
        "live_vs_materialized_speedup_at_least_2_5": (
            live_vs_direct
            >= predecessor.MIN_TERMINAL_VS_MATERIALIZED_WALL_SPEEDUP
        ),
        "live_vs_root_only_ratio_at_least_0_80": (
            live_vs_root >= predecessor.MIN_TERMINAL_VS_ROOT_ONLY_WALL_RATIO
        ),
        "root_bank_closed": (
            base_erase["n_total_bytes_after"] == 0
            and base_erase["n_total_device_bytes_after"] == 0
            and base_erase["n_total_gpu_bytes_after"] == 0
        ),
        "linux_gpu_residency_bounded": (
            isinstance(resources_after.get("peak_gpu_dedicated_bytes"), int)
            and 0 < int(resources_after["peak_gpu_dedicated_bytes"])
            <= linux_sidecar.VRAM_CEILING_BYTES
        ),
        "batch_ownership_exact": (
            len(ownership) == 2
            and all(item["evidence"]["passed"] is True for item in ownership)
        ),
        "unrelated_tool_inference_after_live_closure": (
            tool_canary["validation"]["passed"] is True
        ),
    }
    accepted = all(gates.values())
    return {
        "id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "complete",
        "verdict": "accept" if accepted else "reject",
        "classification": (
            "bounded-r2-live-terminal-declared-closure-supported"
            if accepted
            else "live-terminal-r2-without-all-preregistered-gates"
        ),
        "hypothesis": (
            "Removing successor terminal-root save, restore, and erase while "
            "retaining exact one-use owner-bound live custody will preserve C-to-D-to-B "
            "utility and close the predecessor's fully charged root-only ratio gate."
        ),
        "restoration_class": "DECLARED_CLOSURE",
        "setup": setup,
        "warmup": warmup,
        "counted_trials": counted,
        "metrics": {
            "live_fully_charged_wall_seconds": predecessor.distribution(live_walls),
            "root_only_fully_charged_wall_seconds": predecessor.distribution(root_walls),
            "materialized_fully_charged_wall_seconds": predecessor.distribution(direct_walls),
            "aggregate_live_seconds": sum(live_walls),
            "aggregate_root_only_seconds": sum(root_walls),
            "aggregate_materialized_seconds": sum(direct_walls),
            "consumer_ttft_speedup": ttft_speedup,
            "live_vs_root_only_ratio": live_vs_root,
            "live_vs_materialized_speedup": live_vs_direct,
            "counted_avoided_fresh_prompt_tokens": 4_134,
        },
        "runtime_markers": {
            "live_capture_count": live_capture_count,
            "expected_live_capture_count": expected_live_captures,
            "live_sample_count": live_sample_count,
            "expected_live_sample_count": expected_live_samples,
        },
        "resources_after_closure": resources_after,
        "root_closure": base_erase,
        "tool_canary": tool_canary,
        "batch_ownership": ownership,
        "quality_gates": gates,
        "claim_ceiling": (
            "One bounded process-local Agents-A1 R2 live-terminal pipeline with "
            "owner/lease/generation/type/order custody and DECLARED_CLOSURE. "
            "No inverse restoration, canonical quotient, restart persistence, "
            "phase advantage, or unbounded catalytic inference claim."
        ),
        "automatic_promotion": False,
        "research_goal_blocked": False,
        "next_boundary": (
            "IF_ACCEPTED_ATTACH_THE_FIRST_FIXED_PUBLIC_NONCOMMUTING_RELATIONAL_FIBER; "
            "IF_REJECTED_LOCALIZE_THE_FAILED_LIVE_CUSTODY_OR_FULLY_CHARGED_GATE"
        ),
    }


def static_audit(binary: Path) -> dict[str, Any]:
    source = Path(__file__).read_text(encoding="utf-8")
    runtime_source = source[: source.index("def static_audit(")]
    route = live.static_audit(binary)
    sidecar = linux_sidecar.static_audit()
    gates = {
        "three_matched_routes": (
            'ROUTES = ("live-terminal", "root-only", "materialized")'
            in runtime_source
        ),
        "latin_route_orders": "TRIAL_ROUTE_ORDERS" in runtime_source,
        "same_frozen_speed_gates": (
            "MIN_CONSUMER_TTFT_SPEEDUP" in runtime_source
            and "MIN_TERMINAL_VS_ROOT_ONLY_WALL_RATIO" in runtime_source
            and "MIN_TERMINAL_VS_MATERIALIZED_WALL_SPEEDUP"
            in runtime_source
        ),
        "whole_route_wall_accounting": (
            "whole-route monotonic wall including initial carrier preparation"
            in runtime_source
            and "whole_route_wall_fully_charged" in runtime_source
        ),
        "exact_C_D_B_gate": "all_state_sequences_C_D_B" in runtime_source,
        "wrong_owner_gate": (
            "wrong_owner_rejected_and_poisoned" in runtime_source
        ),
        "declared_closure_gate": (
            "declared_closure_not_restoration" in runtime_source
        ),
        "actual_unrelated_tool_inference": (
            "unrelated_tool_inference_after_live_closure" in runtime_source
        ),
        "preserved_launch_lock": "release_preserved_lock" in runtime_source,
        "no_permanent_file_deletion": all(
            token not in runtime_source
            for token in ("rmtree", ".unlink(", "os.remove", "rmdir(")
        ),
    }
    require(all(gates.values()), "0088 pipeline static audit failed")
    return {
        "id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "gates": gates,
        "live_route": route,
        "linux_sidecar": sidecar,
        "cuda_linked": cuda_linked(binary),
        "controller_sha256": harness.live_runtime.sha256_file(Path(__file__)),
        "scientific_contact": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--static-only", action="store_true")
    mode.add_argument("--execute-once", action="store_true")
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--expected-commit")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--active-lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--run-parent", type=Path, default=DEFAULT_RUN_PARENT)
    return parser.parse_args()


def main() -> int:
    configure_predecessor_identity()
    args = parse_args()
    binary = args.binary.resolve(strict=True)
    static = static_audit(binary)
    if args.static_only:
        print(json.dumps(static, indent=2, sort_keys=True))
        return 0

    require(args.expected_commit is not None, "--expected-commit is required")
    require(cuda_linked(binary), "0088 execution requires a CUDA-linked Linux binary")
    terminal.require_clean_head(ROOT, args.expected_commit)
    output = args.output.resolve(strict=False)
    require(not output.exists(), "0088 result already exists")
    lock_path = args.active_lock.resolve(strict=False)
    lock = acquire_preserved_lock(lock_path, args.expected_commit)
    run_root = (
        args.run_parent.resolve(strict=False)
        / f"{EXPERIMENT_ID}-{time.time_ns()}"
    )
    sidecar = linux_sidecar.LinuxSidecar(
        binary=binary,
        model=args.model,
        run_root=run_root,
    )
    result: dict[str, Any] | None = None
    caught: BaseException | None = None
    cleanup: dict[str, Any] = {}
    try:
        readiness = sidecar.launch()
        codec = harness.carrier.SidecarPromptCodec(linux_sidecar.PORT)
        corpus = harness.carrier.load_public_corpus(ROOT)
        roots = {str(item["root_id"]): item for item in corpus["roots"]}
        prepared = terminal.prepare_task_and_branch(
            codec,
            roots[predecessor.ROOT_ID],
        )
        result = evaluate(
            sidecar=sidecar,
            codec=codec,
            props=codec.props(),
            prepared=prepared,
        )
        result["candidate_commit"] = args.expected_commit
        result["readiness"] = readiness
        result["static_evidence"] = static
        result["launch_lock"] = lock
    except BaseException as exc:
        caught = exc
    finally:
        cleanup = sidecar.stop()
        lock_release = release_preserved_lock(lock_path)

    if caught is not None:
        failure = {
            "id": EXPERIMENT_ID,
            "attempt_id": ATTEMPT_ID,
            "status": "failed",
            "error_type": type(caught).__name__,
            "error": str(caught),
            "cleanup": cleanup,
            "launch_lock": lock,
            "launch_lock_release": lock_release,
            "scientific_contact_requires_log_adjudication": True,
            "automatic_promotion": False,
        }
        terminal.write_exclusive_json(output, failure)
        raise ExperimentError(f"0088 failed; evidence preserved at {output}") from caught

    require(result is not None, "0088 result is missing")
    result["cleanup"] = cleanup
    result["launch_lock_release"] = lock_release
    result["artifact"] = terminal.write_exclusive_json(output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
