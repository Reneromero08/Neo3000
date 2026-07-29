#!/usr/bin/env python3
"""neo-exp-0088 one-use live terminal boundary route.

This module changes only the successor-terminal route from neo-exp-0087.  The
87-token successor suffix is evaluated once against the exact live CUDA child,
but the resulting CUDA KV/recurrent state and host-F32 terminal logits are not
serialized into a RAM root.  A typed public contract admits one immediately
following consumer, then the server clears the boundary before projecting the
sampled token.

The route claims DECLARED_CLOSURE, not restoration.  The existing root-only
and cache-disabled materialized routes remain the matched controls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import catalytic_frontier_harness as harness
import catalytic_frontier_single_request_latency as latency
import catalytic_frontier_successor_terminal_pipeline as predecessor
import catalytic_frontier_terminal_logits_continuation as terminal


EXPERIMENT_ID = "neo-exp-0088"
ATTEMPT_ID = "frontier-attempt-0125"
RESTORATION_CLASS = "DECLARED_CLOSURE"
PROJECTION_POLICY = "FINAL_TOKEN_STREAM_ONLY"
PORT_OWNER = "neo-exp-0088-successor-terminal-consumer"
PORT_TYPE = "agents-a1-live-kv-recurrent-plus-f32-terminal-logits-v1"
MODULE_ID = "successor-terminal-sample"
ROOT = Path(__file__).resolve().parents[1]


class ExperimentError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ExperimentError(message)


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def public_contract(
    *,
    trial_label: str,
    edge: int,
    input_boundary_id: str,
    purpose: str = "counted",
) -> dict[str, Any]:
    require(edge in (1, 2), "live boundary edge must be 1 or 2")
    require(purpose in {"counted", "wrong-owner-negative"}, "unknown contract purpose")
    require(
        input_boundary_id
        == predecessor.EXPECTED_REQUEST_SHA256[
            predecessor.EDGE_PRIORS[edge - 1]
        ],
        "live boundary input identity changed",
    )
    public_label = (
        f"{EXPERIMENT_ID}/{trial_label}/edge-{edge}/{purpose}/generation-{edge}"
    )
    lease = int.from_bytes(
        hashlib.sha256(
            b"neo3000/live-terminal-outer-lease/v1\0"
            + public_label.encode("utf-8")
        ).digest()[:8],
        "big",
    ) or 1
    return {
        "boundary_id": f"{public_label}/terminal",
        "carrier_id": f"{EXPERIMENT_ID}/{trial_label}/slot-0",
        "outer_lease": lease,
        "generation": edge,
        "port_owner": PORT_OWNER,
        "port_type": PORT_TYPE,
        "module_id": MODULE_ID,
        "module_variant": 0,
        "module_ordinal": edge,
        "input_boundary_id": input_boundary_id,
        "projection_policy": PROJECTION_POLICY,
        "restoration_policy": RESTORATION_CLASS,
    }


def capture_payload(
    payload: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    result = dict(payload)
    result.update(
        n_predict=0,
        response_fields=[
            "content",
            "tokens",
            "stop",
            "tokens_predicted",
            "tokens_evaluated",
            "stop_type",
            "tokens_cached",
            "timings",
        ],
        neo3000_capture_live_terminal_boundary=True,
        neo3000_live_terminal=dict(contract),
    )
    return result


def consumer_payload(
    payload: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    result = dict(payload)
    result.update(
        neo3000_use_live_terminal_boundary=True,
        neo3000_live_terminal=dict(contract),
    )
    return result


def wrong_owner_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(contract)
    result["port_owner"] = f"{PORT_OWNER}-wrong"
    return result


class LiveCaptureWireRecorder:
    """Retain a bounded capture response only until its no-leak audit."""

    MAX_BYTES = 256 * 1024

    def __init__(self) -> None:
        self.lines: list[bytes] = []
        self.n_bytes = 0

    def __call__(self, line: bytes) -> None:
        require(isinstance(line, bytes), "live capture wire line is not bytes")
        self.n_bytes += len(line)
        require(
            self.n_bytes <= self.MAX_BYTES,
            "live capture response exceeded the receipt byte ceiling",
        )
        self.lines.append(bytes(line))


def validate_capture_receipt(
    record: Mapping[str, Any],
    recorder: LiveCaptureWireRecorder,
) -> dict[str, Any]:
    """Prove that capture returned metadata plus an empty output surface."""
    execution = record.get("execution")
    require(isinstance(execution, Mapping), "capture execution is absent")
    require(
        set(execution) == set(harness.carrier.CAPTURE_EXECUTION_FIELDS),
        "capture execution surface changed",
    )
    require(
        record.get("content") == ""
        and execution.get("content") in (None, "")
        and execution.get("reasoning_content") in (None, "")
        and execution.get("tool_calls") in (None, [], ()),
        "capture released content, reasoning, or tool output",
    )
    require(
        execution.get("generated_token_ids") == []
        and execution.get("generated_token_count") == 0
        and execution.get("completion_tokens") == 0
        and execution.get("nonempty_token_array_event_count") == 0,
        "capture released generated token state",
    )

    progress_fields = {
        "index",
        "content",
        "tokens",
        "stop",
        "id_slot",
        "tokens_predicted",
        "tokens_evaluated",
        "timings",
        "prompt_progress",
    }
    final_fields = {
        "content",
        "tokens",
        "stop",
        "tokens_predicted",
        "tokens_evaluated",
        "stop_type",
        "tokens_cached",
        "timings",
    }
    timing_fields = {
        "cache_n",
        "prompt_n",
        "prompt_ms",
        "prompt_per_token_ms",
        "prompt_per_second",
        "predicted_n",
        "predicted_ms",
        "predicted_per_token_ms",
        "predicted_per_second",
        "draft_n",
        "draft_n_accepted",
    }
    prompt_progress_fields = {"total", "cache", "processed", "time_ms"}
    events: list[Mapping[str, Any]] = []
    surface_fields: set[str] = set()
    terminal_events = 0
    progress_sentinel_events = 0
    try:
        for line in recorder.lines:
            stripped = line.decode("utf-8", errors="strict").strip()
            if not stripped:
                continue
            require(
                stripped.startswith("data:"),
                "capture wire contained a non-SSE data line",
            )
            data = stripped[5:].strip()
            if not data or data == "[DONE]":
                continue
            value = json.loads(data)
            require(
                isinstance(value, Mapping),
                "capture SSE event is not an object",
            )
            is_progress = "prompt_progress" in value
            allowed_fields = progress_fields if is_progress else final_fields
            if is_progress:
                require(
                    set(value)
                    in (
                        progress_fields,
                        progress_fields - {"timings"},
                    ),
                    "capture prompt-progress response surface changed",
                )
            else:
                require(
                    set(value) == allowed_fields,
                    "capture final response surface changed",
                )
            progress_tokens = value.get("tokens") if is_progress else None
            final_tokens = value.get("tokens") if not is_progress else None
            require(
                value.get("content") == ""
                and (
                    progress_tokens == [0]
                    if is_progress
                    else final_tokens == []
                )
                and value.get("stop") is (not is_progress)
                and value.get("tokens_predicted") == 0,
                "capture wire exposed output or malformed lifecycle state",
            )
            integer_fields = {
                "index",
                "id_slot",
                "tokens_predicted",
                "tokens_evaluated",
                "tokens_cached",
            }
            require(
                all(
                    key not in value or type(value[key]) is int
                    for key in integer_fields
                ),
                "capture wire exposed malformed public counters",
            )
            timings = value.get("timings")
            require(
                timings is None
                or (
                    isinstance(timings, Mapping)
                    and set(timings)
                    in (
                        timing_fields - {"draft_n", "draft_n_accepted"},
                        timing_fields,
                    )
                    and all(
                        isinstance(item, (int, float))
                        and not isinstance(item, bool)
                        for item in timings.values()
                    )
                    and timings.get("predicted_n") == 0
                ),
                "capture wire exposed an unapproved timings field",
            )
            if is_progress:
                progress_sentinel_events += 1
                progress = value["prompt_progress"]
                require(
                    isinstance(progress, Mapping)
                    and set(progress) == prompt_progress_fields,
                    "capture prompt-progress surface changed",
                )
                require(
                    all(
                        isinstance(item, (int, float))
                        and not isinstance(item, bool)
                        for item in progress.values()
                    ),
                    "capture prompt-progress counters are malformed",
                )
            else:
                terminal_events += 1
                require(
                    value.get("stop_type")
                    in {"none", "limit", "eos", "word"},
                    "capture final stop type is malformed",
                )
            events.append(value)
            surface_fields.update(str(key) for key in value)
        require(events, "capture produced no auditable SSE receipt event")
        require(
            terminal_events == 1,
            "capture produced an invalid terminal event count",
        )
        return {
            "receipt_type": "EMPTY_LIVE_CAPTURE_WIRE_RECEIPT_V2",
            "wire_bytes": recorder.n_bytes,
            "wire_event_count": len(events),
            "prompt_progress_sentinel_zero_events": (
                progress_sentinel_events
            ),
            "wire_surface_fields": sorted(surface_fields),
            "content_empty": True,
            "generated_token_ids_empty": True,
            "hidden_value_fields_absent": True,
            "raw_wire_retained": False,
        }
    finally:
        recorder.lines.clear()


def child_root_id(trial_label: str, generation: int) -> str:
    require(generation in (0, 1, 2), "child generation changed")
    return f"{EXPERIMENT_ID}-{trial_label}-live-child-{generation}"


def materialize_child(
    *,
    sidecar: Any,
    base_root: Mapping[str, Any],
    branch_tokens: Sequence[int],
    state: Mapping[str, Any],
    root_id: str,
    label: str,
) -> tuple[dict[str, Any], list[int], dict[str, Any]]:
    restored = predecessor.root_action(
        action="root-restore",
        root_id=str(base_root["root_id"]),
        n_tokens=predecessor.EXPECTED_BASE_TOKENS,
        n_device_bytes=predecessor.EXPECTED_BASE_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=1,
        expected_total_device_bytes_after=predecessor.EXPECTED_BASE_DEVICE_BYTES,
        expected=base_root,
    )
    child_tokens = predecessor.rebase.compact_child_tokens(branch_tokens, state)
    answer = str(state["answer"])
    require(
        predecessor.canonical_sha256(child_tokens)
        == predecessor.EXPECTED_CHILD_SHA256[answer],
        "child hash changed",
    )
    payload = harness.carrier._branch_payload(
        child_tokens,
        seed=predecessor.shared_tasks.derive_seed(
            predecessor.ROOT_ID,
            f"{label}:materialize-child",
        ),
        cache_prompt=True,
        n_predict=0,
    )
    materialized = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:{label}:materialize-child",
        payload,
        operation_kind="zero-output-root-readdress",
        batch_owned_request=True,
    )
    require(
        materialized["prompt_tokens"] == predecessor.EXPECTED_CHILD_TOKENS
        and materialized["cached_prompt_tokens"]
        == predecessor.EXPECTED_BASE_TOKENS
        and materialized["fresh_prompt_tokens"]
        == predecessor.EXPECTED_REBASE_FRESH_TOKENS
        and materialized["completion_tokens"] == 0,
        "child rebase geometry changed",
    )
    saved = predecessor.root_action(
        action="root-save",
        root_id=root_id,
        n_tokens=predecessor.EXPECTED_CHILD_TOKENS,
        n_device_bytes=predecessor.EXPECTED_CHILD_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=2,
        expected_total_device_bytes_after=predecessor.EXPECTED_BASE_CHILD_DEVICE_BYTES,
    )
    lifecycle = {
        "base_restore": restored,
        "materialization": harness.token_summary(materialized),
        "materialization_wall_seconds": float(materialized["wall_seconds"]),
        "child_save": saved,
        "wall_seconds": (
            float(restored["client_wall_seconds"])
            + float(materialized["wall_seconds"])
            + float(saved["client_wall_seconds"])
        ),
        "fresh_prompt_tokens": predecessor.EXPECTED_REBASE_FRESH_TOKENS,
    }
    return saved, child_tokens, lifecycle


def erase_child(child: Mapping[str, Any]) -> dict[str, Any]:
    return predecessor.root_action(
        action="root-erase",
        root_id=str(child["root_id"]),
        n_tokens=predecessor.EXPECTED_CHILD_TOKENS,
        n_device_bytes=predecessor.EXPECTED_CHILD_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=1,
        expected_total_device_bytes_after=predecessor.EXPECTED_BASE_DEVICE_BYTES,
        expected=child,
    )


def run_wrong_owner_negative(
    *,
    sidecar: Any,
    payload: Mapping[str, Any],
    contract: Mapping[str, Any],
    trial_label: str,
    edge: int,
) -> dict[str, Any]:
    wire = LiveCaptureWireRecorder()
    capture = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:{trial_label}:live:edge-{edge}:wrong-owner-capture",
        capture_payload(payload, contract),
        operation_kind="zero-output-root-readdress",
        recorder=wire,
        batch_owned_request=True,
    )
    require(
        capture["prompt_tokens"] == predecessor.EXPECTED_SUCCESSOR_TOKENS
        and capture["cached_prompt_tokens"] == predecessor.EXPECTED_CHILD_TOKENS
        and capture["fresh_prompt_tokens"]
        == predecessor.EXPECTED_SUCCESSOR_FRESH_TOKENS
        and capture["completion_tokens"] == 0,
        "wrong-owner capture geometry changed",
    )
    receipt = validate_capture_receipt(capture, wire)
    denied = terminal.expect_http_error(
        f"http://127.0.0.1:{harness.live_runtime.PORT}/completion",
        consumer_payload(payload, wrong_owner_contract(contract)),
        "Live terminal boundary identity or causal-order mismatch",
    )
    return {
        "capture": harness.token_summary(capture),
        "capture_receipt": receipt,
        "contract_sha256": canonical_sha256(contract),
        "wrong_owner_contract_sha256": canonical_sha256(
            wrong_owner_contract(contract)
        ),
        "denial": denied,
        "boundary_poisoned": True,
        "retry_same_boundary_allowed": False,
    }


def run_live_successor(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    child_root: Mapping[str, Any],
    child_tokens: Sequence[int],
    prior_state: Mapping[str, Any],
    edge: int,
    trial_label: str,
    run_negative: bool,
    baseline_private: int | None,
) -> dict[str, Any]:
    restored = predecessor.root_action(
        action="root-restore",
        root_id=str(child_root["root_id"]),
        n_tokens=predecessor.EXPECTED_CHILD_TOKENS,
        n_device_bytes=predecessor.EXPECTED_CHILD_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=2,
        expected_total_device_bytes_after=predecessor.EXPECTED_BASE_CHILD_DEVICE_BYTES,
        expected=child_root,
    )
    tokens, payload, ancestry = predecessor.derive_successor(
        codec=codec,
        child_tokens=child_tokens,
        prior_state=prior_state,
        edge=edge,
        cache_prompt=True,
    )
    contract = public_contract(
        trial_label=trial_label,
        edge=edge,
        input_boundary_id=str(ancestry["request_token_sha256"]),
    )
    negative: dict[str, Any] | None = None
    if run_negative:
        negative_contract = public_contract(
            trial_label=trial_label,
            edge=edge,
            input_boundary_id=str(ancestry["request_token_sha256"]),
            purpose="wrong-owner-negative",
        )
        negative = run_wrong_owner_negative(
            sidecar=sidecar,
            payload=payload,
            contract=negative_contract,
            trial_label=trial_label,
            edge=edge,
        )
        restored = predecessor.root_action(
            action="root-restore",
            root_id=str(child_root["root_id"]),
            n_tokens=predecessor.EXPECTED_CHILD_TOKENS,
            n_device_bytes=predecessor.EXPECTED_CHILD_DEVICE_BYTES,
            terminal_logits=False,
            expected_roots_after=2,
            expected_total_device_bytes_after=predecessor.EXPECTED_BASE_CHILD_DEVICE_BYTES,
            expected=child_root,
        )

    wire = LiveCaptureWireRecorder()
    capture = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:{trial_label}:live:edge-{edge}:capture",
        capture_payload(payload, contract),
        operation_kind="zero-output-root-readdress",
        recorder=wire,
        batch_owned_request=True,
    )
    require(
        capture["prompt_tokens"] == predecessor.EXPECTED_SUCCESSOR_TOKENS
        and capture["cached_prompt_tokens"] == predecessor.EXPECTED_CHILD_TOKENS
        and capture["fresh_prompt_tokens"]
        == predecessor.EXPECTED_SUCCESSOR_FRESH_TOKENS
        and capture["completion_tokens"] == 0,
        f"live edge {edge} capture geometry changed",
    )
    capture_receipt = validate_capture_receipt(capture, wire)
    resources_resident = harness.process_resources(sidecar, baseline_private)

    recorder = latency.TimingRecorder()
    consumer = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:{trial_label}:live:edge-{edge}:consumer",
        consumer_payload(payload, contract),
        recorder=recorder,
        batch_owned_request=True,
    )
    timing = recorder.summary(
        request_wall_seconds=float(consumer["wall_seconds"])
    )
    require(
        consumer["prompt_tokens"] == predecessor.EXPECTED_SUCCESSOR_TOKENS
        and consumer["cached_prompt_tokens"]
        == predecessor.EXPECTED_SUCCESSOR_TOKENS
        and consumer["fresh_prompt_tokens"] == 0,
        f"live edge {edge} consumer geometry changed",
    )
    require(timing["server_prompt_n"] == 0, "live consumer prompt timing changed")
    state = predecessor.validate_generated_state(
        consumer,
        codec=codec,
        props=props,
        expected_answer=predecessor.EDGE_SUCCESSORS[edge - 1],
    )
    consumer.update(
        route="live-terminal",
        state=state,
        ancestry=ancestry,
        timing=timing,
        restore_inclusive_ttft_seconds=float(timing["ttft_seconds"]),
        effective_wall_seconds=float(consumer["wall_seconds"]),
        input_token_sha256=ancestry["request_token_sha256"],
    )
    return {
        "restore": restored,
        "capture": harness.token_summary(capture),
        "capture_receipt": capture_receipt,
        "capture_wall_seconds": float(capture["wall_seconds"]),
        "contract": contract,
        "contract_sha256": canonical_sha256(contract),
        "consumer": consumer,
        "resident_resources": resources_resident,
        "negative": negative,
        "restoration_class": RESTORATION_CLASS,
        "consumer_count": 1,
    }


def run_live_sequence(
    *,
    sidecar: Any,
    codec: Any,
    props: Mapping[str, Any],
    base_root: Mapping[str, Any],
    branch_tokens: Sequence[int],
    seed_state: Mapping[str, Any],
    trial_label: str,
    baseline_private: int | None,
    run_successor_negative: bool,
) -> dict[str, Any]:
    child, child_tokens, reset = materialize_child(
        sidecar=sidecar,
        base_root=base_root,
        branch_tokens=branch_tokens,
        state=seed_state,
        root_id=child_root_id(trial_label, 0),
        label=f"{trial_label}:live:initial",
    )
    prior_state = dict(seed_state)
    edges: list[dict[str, Any]] = []
    total_wall = 0.0

    for edge in (1, 2):
        live = run_live_successor(
            sidecar=sidecar,
            codec=codec,
            props=props,
            child_root=child,
            child_tokens=child_tokens,
            prior_state=prior_state,
            edge=edge,
            trial_label=trial_label,
            run_negative=run_successor_negative and edge == 1,
            baseline_private=baseline_private,
        )
        child_erased = erase_child(child)
        next_child, next_child_tokens, rebase = materialize_child(
            sidecar=sidecar,
            base_root=base_root,
            branch_tokens=branch_tokens,
            state=live["consumer"]["state"],
            root_id=child_root_id(trial_label, edge),
            label=f"{trial_label}:live:edge-{edge}:next",
        )
        edge_wall = (
            float(live["restore"]["client_wall_seconds"])
            + float(live["capture_wall_seconds"])
            + float(live["consumer"]["effective_wall_seconds"])
            + float(child_erased["client_wall_seconds"])
            + float(rebase["wall_seconds"])
        )
        total_wall += edge_wall
        edges.append(
            {
                "edge": edge,
                "transition": (
                    f"{predecessor.EDGE_PRIORS[edge - 1]}"
                    f"->{predecessor.EDGE_SUCCESSORS[edge - 1]}"
                ),
                "child_root": child,
                "child_token_sha256": canonical_sha256(list(child_tokens)),
                "live": live,
                "capture": live["capture"],
                "consumer": live["consumer"],
                "child_erase": child_erased,
                "next_child": next_child,
                "next_child_token_sha256": canonical_sha256(
                    list(next_child_tokens)
                ),
                "rebase": rebase,
                "fully_charged_edge_wall_seconds": edge_wall,
                "fully_charged_edge_fresh_prompt_tokens": (
                    predecessor.EXPECTED_SUCCESSOR_FRESH_TOKENS
                    + predecessor.EXPECTED_REBASE_FRESH_TOKENS
                ),
                "consumer_count": 1,
            }
        )
        child = next_child
        child_tokens = next_child_tokens
        prior_state = live["consumer"]["state"]

    final_erase = erase_child(child)
    total_wall += float(final_erase["client_wall_seconds"])
    require(prior_state["answer"] == "B", "live sequence final state changed")
    return {
        "route": "live-terminal",
        "trial_label": trial_label,
        "initial_child_reset": reset,
        "edges": edges,
        "observed_states": [
            str(seed_state["answer"]),
            *[str(edge["consumer"]["state"]["answer"]) for edge in edges],
        ],
        "final_child_erase": final_erase,
        "fully_charged_wall_seconds": total_wall,
        "fully_charged_fresh_prompt_tokens": (
            2
            * (
                predecessor.EXPECTED_SUCCESSOR_FRESH_TOKENS
                + predecessor.EXPECTED_REBASE_FRESH_TOKENS
            )
        ),
        "restoration_class": RESTORATION_CLASS,
    }


def static_audit(binary: Path) -> dict[str, Any]:
    context = (ROOT / "tools" / "server" / "server-context.cpp").read_text(
        encoding="utf-8"
    )
    source = Path(__file__).read_text(encoding="utf-8")
    route_source = source[: source.index("def static_audit(")]
    gates = {
        "native_binary_exists": binary.is_file(),
        "owner_bound_contract": all(
            field in source
            for field in (
                "outer_lease",
                "generation",
                "port_owner",
                "port_type",
                "module_id",
                "module_variant",
                "module_ordinal",
                "input_boundary_id",
            )
        ),
        "public_pre_output_lease_derivation": (
            "live-terminal-outer-lease/v1" in source
        ),
        "one_use_live_capture": "neo3000_capture_live_terminal_boundary" in source,
        "one_use_live_consumer": "neo3000_use_live_terminal_boundary" in source,
        "wrong_owner_negative": "wrong_owner_contract" in source,
        "exact_prompt_progress_sentinel_receipt": (
            "progress_tokens == [0]" in source
            and "final_tokens == []" in source
            and "EMPTY_LIVE_CAPTURE_WIRE_RECEIPT_V2" in source
        ),
        "declared_closure_only": RESTORATION_CLASS in source,
        "no_terminal_root_in_live_route": (
            "include_terminal_logits=True" not in route_source
            and "require_terminal_logits=True" not in route_source
        ),
        "server_closes_before_projection": (
            context.index("slot.terminal_logits.clear();", context.index("const bool live_source ="))
            < context.index("process_token(result, slot)", context.index("const bool live_source ="))
        ),
        "r2_state_sequence": "for edge in (1, 2):" in source,
        "output_derived_child_rebase": "materialize_child(" in source,
        "automatic_promotion_true_absent": (
            '"automatic_promotion": True' not in route_source
        ),
    }
    require(
        all(gates.values()),
        "0088 live terminal static audit failed: "
        + ", ".join(key for key, value in gates.items() if not value),
    )
    return {
        "id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "gates": gates,
        "binary": {
            "path": str(binary),
            "sha256": harness.live_runtime.sha256_file(binary),
        },
        "controller_sha256": harness.live_runtime.sha256_file(Path(__file__)),
        "restoration_class": RESTORATION_CLASS,
        "scientific_contact": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--static-only", action="store_true", required=True)
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            static_audit(args.binary.resolve(strict=True)),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
