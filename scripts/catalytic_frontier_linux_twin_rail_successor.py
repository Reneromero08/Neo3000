#!/usr/bin/env python3
"""neo-exp-0094 fixed-public twin-rail inference successor.

The accepted 777-token live successor is extended only by the already-public
JSON prefix tokens [4754, 8944, 3147].  The resulting 780-token boundary has a
fixed A/B/C/D hypothesis set [32, 33, 34, 35].  The server keeps all logits,
probabilities, angles, phase cells, and scores internal, restores the persistent
eight-complex-cell carrier before emitting the selected answer token, and then
continues the ordinary suffix decode.

The fiber is NUMERICAL_PHYSICAL_STATE_RESTORATION.  Its supporting live
CUDA/KV plus host-logit source is separately DECLARED_CLOSURE.  The identical
four-logit softmax/argmax recurrence is mandatory, so this experiment cannot
claim a distinct phase resource or computational advantage.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import time
from typing import Any, Mapping, Sequence

import catalytic_frontier_harness as harness
import catalytic_frontier_linux_live_terminal_successor as parent
import catalytic_frontier_live_terminal_boundary as live
import catalytic_frontier_successor_terminal_pipeline as predecessor
import catalytic_frontier_terminal_logits_continuation as terminal
import catalytic_frontier_twin_rail_exact_oracle as exact_oracle


EXPERIMENT_ID = "neo-exp-0094"
ATTEMPT_ID = "frontier-attempt-0139"
PREREGISTRATION_ATTEMPT_ID = "frontier-attempt-0138"
ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SCHEMA_PREFIX = (4754, 8944, 3147)
CANDIDATE_TOKEN_IDS = {"A": 32, "B": 33, "C": 34, "D": 35}
HYPOTHESIS_TOKENS = 780
HYPOTHESIS_FRESH_TOKENS = 90
HYPOTHESIS_DEVICE_BYTES = 81_838_080
SUFFIX_GRAMMAR = (
    'root ::= answer "\\\"}"\n'
    'answer ::= "A" | "B" | "C" | "D"'
)

FIBER_RESTORATION_CLASS = "NUMERICAL_PHYSICAL_STATE_RESTORATION"
REORDERED_PROJECTION_RESTORATION_CLASS = (
    "INVERSE_PLUS_CANONICAL_NUMERICAL_QUOTIENT"
)
SOURCE_RESTORATION_CLASS = "DECLARED_CLOSURE"
PROJECTION_POLICY = "FINAL_SINGLE_HYPOTHESIS_TOKEN_AFTER_RESTORATION"
PORT_OWNER = "neo-exp-0094-four-choice-phase-consumer"
PORT_TYPE = "agents-a1-four-choice-logits-to-twinrail-v1"
MODULE_ID = "terminal-softmax-twinrail-hadamard-v1"
PRIMARY_VARIANT = 0
DEPHASED_VARIANT = 1
REORDERED_FORWARD_VARIANT = 2
INVERSE_FAULT_VARIANTS = (3, 4, 5)
NULL_VARIANT = 6
PREMATURE_VARIANT = 7
COMPACT_CLASSICAL_VARIANT = 8
EXPECTED_MODEL_CALLBACKS = 38
EXPECTED_DIRECT_PROTOCOL_ACTIONS = 29
TUPLE_FIELDS = parent.TUPLE_MUTATION_FIELDS

DEFAULT_BINARY = parent.DEFAULT_BINARY
DEFAULT_MODEL = parent.DEFAULT_MODEL
DEFAULT_RUNTIME_MANIFEST = ROOT / "lab" / "neo-exp-0094-runtime-manifest.json"
DEFAULT_OUTPUT = ROOT / "lab" / "neo-exp-0094.local.json"
DEFAULT_LOCK = ROOT / "build" / "linux-catalytic" / "neo-exp-0094.active-lock.json"
DEFAULT_CONSUMED_MARKER = (
    ROOT / "build" / "linux-catalytic" / "neo-exp-0094.consumed-marker.json"
)
DEFAULT_RUN_PARENT = ROOT / "build" / "linux-catalytic"
BASE_ROOT_ID = "neo-exp-0094-base-684"

_BASE_RUNTIME_MANIFEST_TEMPLATE = parent.runtime_manifest_template
_BASE_VALIDATE_RUNTIME_MANIFEST = parent.validate_runtime_manifest
_BASE_AUDIT_SHUTDOWN = parent.audit_shutdown_live_terminal_custody
_PARENT_ASSIGNMENT_NAMES = (
    "EXPERIMENT_ID",
    "ATTEMPT_ID",
    "PREREGISTRATION_ATTEMPT_ID",
    "RESTORATION_CLASS",
    "PROJECTION_POLICY",
    "PORT_OWNER",
    "PORT_TYPE",
    "MODULE_ID",
    "BASE_ROOT_ID",
    "EXPECTED_MODEL_CALLBACKS",
    "EXPECTED_DIRECT_PROTOCOL_ACTIONS",
    "DEFAULT_RUNTIME_MANIFEST",
    "DEFAULT_OUTPUT",
    "DEFAULT_LOCK",
    "DEFAULT_CONSUMED_MARKER",
    "DEFAULT_RUN_PARENT",
)
_PARENT_ASSIGNMENTS = {
    name: getattr(parent, name) for name in _PARENT_ASSIGNMENT_NAMES
}
_PARENT_ARTIFACTS = dict(parent.RUNTIME_ARTIFACT_PATHS)
_PARENT_SOURCE_ARTIFACT_NAMES = set(parent.SOURCE_ARTIFACT_NAMES)
_PARENT_INSTALLED_FOR_MAIN = False


def require(condition: bool, message: str) -> None:
    if not condition:
        raise parent.ExperimentError(message)


def canonical_sha256(value: Any) -> str:
    return parent.canonical_sha256(value)


def prompt_fnv1a64(tokens: Sequence[int]) -> str:
    value = 14695981039346656037
    for token in tokens:
        for byte in struct.pack("<i", int(token)):
            value ^= byte
            value = (value * 1099511628211) & ((1 << 64) - 1)
    return f"{value:016x}"


def configure_parent() -> None:
    """Reuse the qualified Linux lifecycle while replacing its identity."""
    assignments = {
        "EXPERIMENT_ID": EXPERIMENT_ID,
        "ATTEMPT_ID": ATTEMPT_ID,
        "PREREGISTRATION_ATTEMPT_ID": PREREGISTRATION_ATTEMPT_ID,
        "RESTORATION_CLASS": FIBER_RESTORATION_CLASS,
        "PROJECTION_POLICY": PROJECTION_POLICY,
        "PORT_OWNER": PORT_OWNER,
        "PORT_TYPE": PORT_TYPE,
        "MODULE_ID": MODULE_ID,
        "BASE_ROOT_ID": BASE_ROOT_ID,
        "EXPECTED_MODEL_CALLBACKS": EXPECTED_MODEL_CALLBACKS,
        "EXPECTED_DIRECT_PROTOCOL_ACTIONS": EXPECTED_DIRECT_PROTOCOL_ACTIONS,
        "DEFAULT_RUNTIME_MANIFEST": DEFAULT_RUNTIME_MANIFEST,
        "DEFAULT_OUTPUT": DEFAULT_OUTPUT,
        "DEFAULT_LOCK": DEFAULT_LOCK,
        "DEFAULT_CONSUMED_MARKER": DEFAULT_CONSUMED_MARKER,
        "DEFAULT_RUN_PARENT": DEFAULT_RUN_PARENT,
    }
    for name, value in assignments.items():
        setattr(parent, name, value)

    artifacts = parent.RUNTIME_ARTIFACT_PATHS
    artifacts["controller"] = Path(__file__)
    artifacts["controller_test"] = (
        ROOT / "scripts" / "test_catalytic_frontier_linux_twin_rail_successor.py"
    )
    artifacts["twin_rail_source"] = (
        ROOT / "tools" / "server" / "neo3000-twin-rail-fiber.cpp"
    )
    artifacts["twin_rail_header"] = (
        ROOT / "tools" / "server" / "neo3000-twin-rail-fiber.h"
    )
    artifacts["server_cmake"] = ROOT / "tools" / "server" / "CMakeLists.txt"
    artifacts["runtime_selftest"] = (
        ROOT / "scripts" / "catalytic_frontier_twin_rail_runtime_selftest.cpp"
    )
    artifacts["runtime_selftest_binary"] = (
        ROOT / "build" / "linux-catalytic" / "neo-exp-0094-static"
        / "twin-rail-selftest"
    )
    artifacts["exact_oracle"] = (
        ROOT / "scripts" / "catalytic_frontier_twin_rail_exact_oracle.py"
    )
    artifacts["exact_oracle_test"] = (
        ROOT / "scripts" / "test_catalytic_frontier_twin_rail_exact_oracle.py"
    )
    parent.SOURCE_ARTIFACT_NAMES.update(
        {
            "twin_rail_source",
            "twin_rail_header",
            "server_cmake",
            "runtime_selftest",
            "exact_oracle",
            "exact_oracle_test",
        }
    )


def restore_parent() -> None:
    for name, value in _PARENT_ASSIGNMENTS.items():
        setattr(parent, name, value)
    parent.RUNTIME_ARTIFACT_PATHS.clear()
    parent.RUNTIME_ARTIFACT_PATHS.update(_PARENT_ARTIFACTS)
    parent.SOURCE_ARTIFACT_NAMES.clear()
    parent.SOURCE_ARTIFACT_NAMES.update(_PARENT_SOURCE_ARTIFACT_NAMES)


def expanded_successor(
        tokens: Sequence[int],
        payload: Mapping[str, Any],
        *,
        n_predict: int | None = None,
        cache_prompt: bool | None = None,
) -> tuple[list[int], dict[str, Any]]:
    require(len(tokens) == parent.EXPECTED_SUCCESSOR_TOKENS, "source successor is not 777 tokens")
    expanded = [*tokens, *PUBLIC_SCHEMA_PREFIX]
    require(
        len(expanded) == HYPOTHESIS_TOKENS
        and tuple(expanded[-3:]) == PUBLIC_SCHEMA_PREFIX,
        "public 780-token hypothesis boundary changed",
    )
    result = dict(payload)
    result["prompt"] = expanded
    result["grammar"] = SUFFIX_GRAMMAR
    if n_predict is not None:
        result["n_predict"] = n_predict
    if cache_prompt is not None:
        result["cache_prompt"] = cache_prompt
    return expanded, result


def public_contract(
        *,
        trial: str,
        edge: int,
        tokens: Sequence[int],
        variant: int,
        special: bool = True,
) -> dict[str, Any]:
    require(edge in (1, 2), "phase edge must be one or two")
    require(0 <= variant <= COMPACT_CLASSICAL_VARIANT, "unknown module variant")
    label = f"{EXPERIMENT_ID}/{trial}/edge-{edge}/variant-{variant}"
    lease = int.from_bytes(
        hashlib.sha256(
            b"neo3000/twin-rail-outer-lease/v1\0" + label.encode("utf-8")
        ).digest()[:8],
        "big",
    ) or 1
    if special:
        owner = PORT_OWNER
        port_type = PORT_TYPE
        module = MODULE_ID
        projection = PROJECTION_POLICY
    else:
        owner = "neo-exp-0094-live-sampler-control"
        port_type = "agents-a1-live-kv-plus-f32-terminal-logits-control-v1"
        module = "ordinary-live-terminal-sampler-control"
        projection = "FINAL_TOKEN_STREAM_ONLY"
    return {
        "boundary_id": f"{label}/terminal",
        "carrier_id": f"{EXPERIMENT_ID}/{trial}/slot-0",
        "outer_lease": lease,
        "generation": edge,
        "port_owner": owner,
        "port_type": port_type,
        "module_id": module,
        "module_variant": variant,
        "module_ordinal": edge,
        "input_boundary_id": f"fnv1a64:{prompt_fnv1a64(tokens)}",
        "projection_policy": projection,
        "restoration_policy": SOURCE_RESTORATION_CLASS,
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


def validate_suffix_state(
        record: Mapping[str, Any],
        *,
        codec: Any,
        props: Mapping[str, Any],
        expected_answer: str,
) -> dict[str, Any]:
    execution = record.get("execution")
    require(isinstance(execution, Mapping), "suffix execution is absent")
    generated = execution.get("generated_token_ids")
    require(
        isinstance(generated, list)
        and len(generated) >= 2
        and all(type(item) is int for item in generated),
        "suffix output lacks exact generated tokens",
    )
    require(execution.get("finish_reason") == "eos", "suffix output did not reach EOS")
    terminal_eog = int(generated[-1])
    eos_piece = str(props.get("eos_token") or "")
    require(
        eos_piece
        and codec.detokenize([terminal_eog]) == eos_piece
        and codec.tokenize(eos_piece) == [terminal_eog],
        "suffix EOS identity changed",
    )
    suffix_visible = list(generated[:-1])
    suffix_content = str(record.get("content") or "")
    require(
        codec.detokenize(suffix_visible) == suffix_content,
        "suffix token IDs do not reconstruct content",
    )
    visible = [*PUBLIC_SCHEMA_PREFIX, *suffix_visible]
    content = codec.detokenize(visible)
    answer = harness.carrier.parse_branch_output(content)
    require(answer == expected_answer, f"expected {expected_answer} suffix changed")
    full_generated = [*visible, terminal_eog]
    full_hash = harness.sha256_bytes(
        harness.carrier.canonical_json_bytes(full_generated)
    )
    require(
        full_hash == parent.EXPECTED_GENERATED_SHA256[expected_answer],
        "public-prefix plus suffix generated identity changed",
    )
    require(
        execution.get("reasoning_content") in {"", None}
        and not execution.get("tool_calls"),
        "hidden reasoning or tools entered suffix state",
    )
    return {
        "answer": answer,
        "content": content,
        "generated_token_ids": full_generated,
        "visible_token_ids": visible,
        "terminal_eog_id": terminal_eog,
        "generated_token_sha256": full_hash,
        "visible_token_sha256": harness.sha256_bytes(
            harness.carrier.canonical_json_bytes(visible)
        ),
        "actual_suffix_token_ids": list(generated),
        "actual_suffix_content": suffix_content,
        "public_prefix_token_ids": list(PUBLIC_SCHEMA_PREFIX),
    }


def validate_single_hypothesis(
        record: Mapping[str, Any],
        *,
        expected_token: int,
) -> dict[str, Any]:
    execution = record.get("execution")
    generated = execution.get("generated_token_ids") if isinstance(execution, Mapping) else None
    require(
        generated == [expected_token]
        and record.get("completion_tokens") == 1
        and execution.get("finish_reason") == "limit",
        "single-hypothesis control boundary changed",
    )
    return {
        "token_id": expected_token,
        "content": record.get("content"),
        "finish_reason": "limit",
    }


def restore_child(child: Mapping[str, Any]) -> dict[str, Any]:
    return predecessor.root_action(
        action="root-restore",
        root_id=str(child["root_id"]),
        n_tokens=parent.EXPECTED_CHILD_TOKENS,
        n_device_bytes=parent.EXPECTED_CHILD_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=2,
        expected_total_device_bytes_after=parent.EXPECTED_BASE_CHILD_DEVICE_BYTES,
        expected=child,
    )


def capture_boundary(
        *,
        sidecar: Any,
        payload: Mapping[str, Any],
        contract: Mapping[str, Any],
        label: str,
) -> dict[str, Any]:
    wire = live.LiveCaptureWireRecorder()
    record = harness.run_completion(
        sidecar,
        label,
        capture_payload(payload, contract),
        operation_kind="zero-output-root-readdress",
        recorder=wire,
        batch_owned_request=True,
    )
    require(
        record["prompt_tokens"] == HYPOTHESIS_TOKENS
        and record["cached_prompt_tokens"] == parent.EXPECTED_CHILD_TOKENS
        and record["fresh_prompt_tokens"] == HYPOTHESIS_FRESH_TOKENS
        and record["completion_tokens"] == 0,
        "780-token capture geometry changed",
    )
    return {
        "summary": harness.token_summary(record),
        "receipt": live.validate_capture_receipt(record, wire),
        "wall_seconds": float(record["wall_seconds"]),
    }


def derive_expanded(
        *,
        codec: Any,
        child_tokens: Sequence[int],
        prior_state: Mapping[str, Any],
        edge: int,
        cache_prompt: bool = True,
) -> tuple[list[int], dict[str, Any], dict[str, Any]]:
    tokens, payload, ancestry = parent.derive_successor(
        codec=codec,
        child_tokens=child_tokens,
        prior_state=prior_state,
        edge=edge,
        cache_prompt=cache_prompt,
    )
    expanded, result = expanded_successor(
        tokens,
        payload,
        cache_prompt=cache_prompt,
    )
    ancestry = {
        **ancestry,
            "source_777_token_sha256": canonical_sha256(tokens),
            "hypothesis_780_token_sha256": canonical_sha256(expanded),
            "hypothesis_780_token_fnv1a64": prompt_fnv1a64(expanded),
        "public_schema_prefix": list(PUBLIC_SCHEMA_PREFIX),
    }
    return expanded, result, ancestry


def run_primary_sequence(
        *,
        sidecar: Any,
        codec: Any,
        props: Mapping[str, Any],
        setup: Mapping[str, Any],
        trial: str,
) -> dict[str, Any]:
    child, child_tokens, reset = live.materialize_child(
        sidecar=sidecar,
        base_root=setup["base_root"],
        branch_tokens=setup["branch_tokens"],
        state=setup["seed_state"],
        root_id=f"{EXPERIMENT_ID}-{trial}-child-0",
        label=f"{trial}:primary:initial",
    )
    prior_state = dict(setup["seed_state"])
    edges: list[dict[str, Any]] = []
    for edge in (1, 2):
        restored = restore_child(child)
        tokens, payload, ancestry = derive_expanded(
            codec=codec,
            child_tokens=child_tokens,
            prior_state=prior_state,
            edge=edge,
        )
        contract = public_contract(
            trial=trial,
            edge=edge,
            tokens=tokens,
            variant=PRIMARY_VARIANT,
        )
        capture = capture_boundary(
            sidecar=sidecar,
            payload=payload,
            contract=contract,
            label=f"{EXPERIMENT_ID}:{trial}:edge-{edge}:phase-capture",
        )
        consumer = harness.run_completion(
            sidecar,
            f"{EXPERIMENT_ID}:{trial}:edge-{edge}:phase-consumer",
            consumer_payload(payload, contract),
            batch_owned_request=True,
        )
        require(
            consumer["prompt_tokens"] == HYPOTHESIS_TOKENS
            and consumer["cached_prompt_tokens"] == HYPOTHESIS_TOKENS
            and consumer["fresh_prompt_tokens"] == 0,
            "primary phase consumer geometry changed",
        )
        expected = predecessor.EDGE_SUCCESSORS[edge - 1]
        state = validate_suffix_state(
            consumer,
            codec=codec,
            props=props,
            expected_answer=expected,
        )
        erased = live.erase_child(child)
        next_child, next_tokens, rebase = live.materialize_child(
            sidecar=sidecar,
            base_root=setup["base_root"],
            branch_tokens=setup["branch_tokens"],
            state=state,
            root_id=f"{EXPERIMENT_ID}-{trial}-child-{edge}",
            label=f"{trial}:primary:edge-{edge}:rebase",
        )
        edges.append(
            {
                "edge": edge,
                "transition": (
                    f"{predecessor.EDGE_PRIORS[edge - 1]}->{expected}"
                ),
                "restore": restored,
                "capture": capture,
                "contract": contract,
                "ancestry": ancestry,
                "consumer": harness.token_summary(consumer),
                "state": state,
                "child_erase": erased,
                "rebase": rebase,
            }
        )
        child, child_tokens, prior_state = next_child, next_tokens, state
    final_erase = live.erase_child(child)
    require(prior_state["answer"] == "B", "primary R2 sequence did not reach B")
    return {
        "carrier_id": f"{EXPERIMENT_ID}/{trial}/slot-0",
        "initial_reset": reset,
        "edges": edges,
        "observed_states": ["C", "D", "B"],
        "final_erase": final_erase,
    }


def run_post_primary_successor(
        *,
        sidecar: Any,
        codec: Any,
        props: Mapping[str, Any],
        setup: Mapping[str, Any],
        primary: Mapping[str, Any],
        transaction_nonce: str,
        progress: dict[str, Any],
) -> dict[str, Any] | None:
    """Optional successor hook, deliberately inert for consumed neo-exp-0094..0097."""
    del sidecar, codec, props, setup, primary, transaction_nonce, progress
    return None


def run_live_or_special_success(
        *,
        sidecar: Any,
        codec: Any,
        props: Mapping[str, Any],
        child: Mapping[str, Any],
        child_tokens: Sequence[int],
        seed_state: Mapping[str, Any],
        trial: str,
        variant: int,
        special: bool,
        one_token: bool,
        expected_answer: str = "D",
        expected_token: int | None = None,
) -> dict[str, Any]:
    restored = restore_child(child)
    tokens, payload, ancestry = derive_expanded(
        codec=codec,
        child_tokens=child_tokens,
        prior_state=seed_state,
        edge=1,
    )
    if one_token:
        payload["n_predict"] = 1
    contract = public_contract(
        trial=trial,
        edge=1,
        tokens=tokens,
        variant=variant,
        special=special,
    )
    capture = capture_boundary(
        sidecar=sidecar,
        payload=payload,
        contract=contract,
        label=f"{EXPERIMENT_ID}:{trial}:capture",
    )
    consumer = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:{trial}:consumer",
        consumer_payload(payload, contract),
        operation_kind=(
            "one-token-control-projection"
            if one_token
            else "model-generation"
        ),
        batch_owned_request=True,
    )
    require(
        consumer["cached_prompt_tokens"] == HYPOTHESIS_TOKENS
        and consumer["fresh_prompt_tokens"] == 0,
        "control live consumer geometry changed",
    )
    boundary = (
        validate_single_hypothesis(
            consumer,
            expected_token=int(expected_token),
        )
        if one_token
        else validate_suffix_state(
            consumer,
            codec=codec,
            props=props,
            expected_answer=expected_answer,
        )
    )
    return {
        "restore": restored,
        "capture": capture,
        "contract": contract,
        "ancestry": ancestry,
        "consumer": harness.token_summary(consumer),
        "boundary": boundary,
    }


def run_fault_controls(
        *,
        sidecar: Any,
        codec: Any,
        child: Mapping[str, Any],
        child_tokens: Sequence[int],
        seed_state: Mapping[str, Any],
        nonce: str,
        progress: dict[str, Any],
) -> dict[str, Any]:
    endpoint = f"http://127.0.0.1:{harness.live_runtime.PORT}/completion"
    inverse: list[dict[str, Any]] = []
    for variant in INVERSE_FAULT_VARIANTS:
        restore = restore_child(child)
        tokens, payload, _ = derive_expanded(
            codec=codec,
            child_tokens=child_tokens,
            prior_state=seed_state,
            edge=1,
        )
        contract = public_contract(
            trial=f"{nonce}-inverse-{variant}",
            edge=1,
            tokens=tokens,
            variant=variant,
        )
        capture = capture_boundary(
            sidecar=sidecar,
            payload=payload,
            contract=contract,
            label=f"{EXPERIMENT_ID}:{nonce}:inverse-{variant}:capture",
        )
        parent.protocol_attempt(
            run_root=sidecar.run_root,
            progress=progress,
            label=f"inverse-fault-{variant}-consumer",
        )
        denial = terminal.expect_http_error(
            endpoint,
            consumer_payload(payload, contract),
            "Twin-rail transaction rejected before final projection",
        )
        inverse.append(
            {
                "variant": variant,
                "restore": restore,
                "capture": capture,
                "denial": denial,
            }
        )

    pre_borrow: list[dict[str, Any]] = []
    for variant in (NULL_VARIANT, PREMATURE_VARIANT):
        tokens, payload, _ = derive_expanded(
            codec=codec,
            child_tokens=child_tokens,
            prior_state=seed_state,
            edge=1,
        )
        contract = public_contract(
            trial=f"{nonce}-pre-borrow-{variant}",
            edge=1,
            tokens=tokens,
            variant=variant,
        )
        parent.protocol_attempt(
            run_root=sidecar.run_root,
            progress=progress,
            label=f"pre-borrow-variant-{variant}-capture",
        )
        denial = terminal.expect_http_error(
            endpoint,
            capture_payload(payload, contract),
            "Twin-rail capture requires an exact admitted fixed public hypothesis boundary",
        )
        pre_borrow.append({"variant": variant, "denial": denial})
    return {"inverse": inverse, "pre_borrow": pre_borrow}


def run_tuple_controls(
        *,
        sidecar: Any,
        codec: Any,
        child: Mapping[str, Any],
        child_tokens: Sequence[int],
        seed_state: Mapping[str, Any],
        nonce: str,
        progress: dict[str, Any],
) -> list[dict[str, Any]]:
    endpoint = f"http://127.0.0.1:{harness.live_runtime.PORT}/completion"
    controls: list[dict[str, Any]] = []
    for field in TUPLE_FIELDS:
        restored = restore_child(child)
        tokens, payload, _ = derive_expanded(
            codec=codec,
            child_tokens=child_tokens,
            prior_state=seed_state,
            edge=1,
        )
        contract = public_contract(
            trial=f"{nonce}-tuple-{field}",
            edge=1,
            tokens=tokens,
            variant=PRIMARY_VARIANT,
        )
        capture = capture_boundary(
            sidecar=sidecar,
            payload=payload,
            contract=contract,
            label=f"{EXPERIMENT_ID}:{nonce}:tuple-{field}:capture",
        )
        mutated = parent.mutate_contract(contract, field)
        parent.protocol_attempt(
            run_root=sidecar.run_root,
            progress=progress,
            label=f"wrong-{field}-consumer",
        )
        denial = terminal.expect_http_error(
            endpoint,
            consumer_payload(payload, mutated),
            "Live terminal boundary identity or causal-order mismatch",
        )
        parent.protocol_attempt(
            run_root=sidecar.run_root,
            progress=progress,
            label=f"poisoned-{field}-replay",
        )
        replay = terminal.expect_http_error(
            endpoint,
            consumer_payload(payload, contract),
            "Live terminal boundary identity or causal-order mismatch",
        )
        controls.append(
            {
                "field": field,
                "restore": restored,
                "capture": capture,
                "denial": denial,
                "exact_replay_after_poison": replay,
            }
        )
    return controls


def run_direct_controls(
        *,
        sidecar: Any,
        codec: Any,
        props: Mapping[str, Any],
        child: Mapping[str, Any],
        child_tokens: Sequence[int],
        seed_state: Mapping[str, Any],
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for route, cache_prompt in (("root-only", True), ("materialized", False)):
        restore = restore_child(child) if cache_prompt else None
        _, payload, ancestry = derive_expanded(
            codec=codec,
            child_tokens=child_tokens,
            prior_state=seed_state,
            edge=1,
            cache_prompt=cache_prompt,
        )
        record = harness.run_completion(
            sidecar,
            f"{EXPERIMENT_ID}:{route}:control",
            payload,
            batch_owned_request=True,
        )
        require(
            record["prompt_tokens"] == HYPOTHESIS_TOKENS
            and record["cached_prompt_tokens"] ==
                    (parent.EXPECTED_CHILD_TOKENS if cache_prompt else 0)
            and record["fresh_prompt_tokens"] ==
                    (HYPOTHESIS_FRESH_TOKENS if cache_prompt else HYPOTHESIS_TOKENS),
            f"{route} 780-token geometry changed",
        )
        results[route] = {
            "restore": restore,
            "ancestry": ancestry,
            "record": harness.token_summary(record),
            "state": validate_suffix_state(
                record,
                codec=codec,
                props=props,
                expected_answer="D",
            ),
        }
    return results


def phase_log_evidence(
        *,
        sidecar: Any,
        primary_carrier_id: str,
        unrelated_carrier_id: str | None = None,
) -> dict[str, Any]:
    log_path = Path(str(sidecar.readiness["log_path"]))
    text = log_path.read_text(encoding="utf-8", errors="replace")
    success_lines = [
        line for line in text.splitlines()
        if "neo3000 twin-rail carrier restored and live source declared-closed before response"
        in line
    ]
    primary = [line for line in success_lines if f"carrier={primary_carrier_id} " in line]
    unrelated = (
        [
            line
            for line in success_lines
            if f"carrier={unrelated_carrier_id} " in line
        ]
        if unrelated_carrier_id is not None
        else []
    )
    rejected = text.count(
        "neo3000 twin-rail transaction rejected and live source poisoned"
    )
    require(
        len(primary) == 2
        and primary[0] == success_lines[0]
        and primary[1] == success_lines[1]
        and "variant=0" in primary[0]
        and "variant=0" in primary[1]
        and "generation=1 ordinal=1" in primary[0]
        and "generation=2 ordinal=2" in primary[1]
        and "classical_parity=true" in primary[0]
        and "classical_parity=true" in primary[1]
        and "canonical_tie_quotient=false" in primary[0]
        and "canonical_tie_quotient=false" in primary[1]
        and "primary_margin_guard=true" in primary[0]
        and "primary_margin_guard=true" in primary[1]
        and "backing_reused=false" in primary[0]
        and "backing_reused=true" in primary[1]
        and "fresh_parity=true" in primary[0]
        and "fresh_parity=true" in primary[1]
        and "transactions=1 reuses=0 recoveries=0" in primary[0]
        and "transactions=2 reuses=1 recoveries=0" in primary[1]
        and rejected == len(INVERSE_FAULT_VARIANTS),
        "phase lifecycle log evidence changed",
    )
    unrelated_metrics: dict[str, float] | None = None
    if unrelated_carrier_id is not None:
        metrics_match = re.search(
            r"score_error=([0-9eE+.-]+) "
            r"restoration_error=([0-9eE+.-]+).* "
            r"fresh_restoration_error=([0-9eE+.-]+)",
            unrelated[0] if unrelated else "",
        )
        if metrics_match is not None:
            unrelated_metrics = {
                "maximum_score_error": float(metrics_match.group(1)),
                "maximum_restoration_error": float(metrics_match.group(2)),
                "fresh_maximum_restoration_error": float(
                    metrics_match.group(3)
                ),
            }
        require(
            len(unrelated) == 1
            and unrelated[0] == success_lines[2]
            and "variant=0" in unrelated[0]
            and "generation=1 ordinal=1" in unrelated[0]
            and "classical_parity=true" in unrelated[0]
            and "canonical_tie_quotient=false" in unrelated[0]
            and "primary_margin_guard=true" in unrelated[0]
            and "backing_reused=true" in unrelated[0]
            and "fresh_parity=true" in unrelated[0]
            and "transactions=3 reuses=2 recoveries=0" in unrelated[0],
            "unrelated restored-fiber lifecycle evidence changed",
        )
        require(
            unrelated_metrics is not None
            and all(
                0.0 <= value <= 1.0e-12
                for value in unrelated_metrics.values()
            ),
            "unrelated restored-fiber numerical restoration evidence changed",
        )
    expected_sequence = (
        (
            (0, 1, 0, True, False, True),
            (0, 2, 1, True, False, True),
            (0, 3, 2, True, False, True),
            (1, 4, 3, False, False, False),
            (2, 5, 4, False, True, False),
        )
        if unrelated_carrier_id is not None
        else (
            (0, 1, 0, True, False, True),
            (0, 2, 1, True, False, True),
            (1, 3, 2, False, False, False),
            (2, 4, 3, False, True, False),
        )
    )
    require(
        len(success_lines) == len(expected_sequence)
        and all(
            f"variant={variant}" in line
            and (
                f"generation={2 if transactions == 2 else 1} "
                f"ordinal={2 if transactions == 2 else 1}"
            ) in line
            and f"transactions={transactions} reuses={reuses} recoveries=0"
                    in line
            and f"primary_margin_guard={'true' if margin else 'false'}"
                    in line
            and f"canonical_tie_quotient={'true' if quotient else 'false'}"
                    in line
            and f"fresh_parity={'true' if fresh else 'false'}" in line
            and (
                "backing_reused=true" in line
                if transactions > 1
                else "backing_reused=false" in line
            )
            for line, (
                variant,
                transactions,
                reuses,
                margin,
                quotient,
                fresh,
            ) in zip(success_lines, expected_sequence, strict=True)
        ),
        "complete twin-rail success order or lifetime counters changed",
    )
    for line in success_lines:
        require(
            "canonical_tie_quotient=" in line
            and "primary_margin_guard=" in line
            and all(term not in line for term in ("logits=[", "probabilities=", "angles=", "scores=", "phase_cells=")),
            "phase log leaked an unresolved intermediate",
        )
    quotient_count = sum(
        "canonical_tie_quotient=true" in line
        for line in success_lines
    )
    primary_margin_count = sum(
        "primary_margin_guard=true" in line
        for line in success_lines
    )
    require(
        quotient_count == 1
        and primary_margin_count == 2 + len(unrelated),
        "numerical quotient or primary margin evidence changed",
    )
    recovery_initializations = [
        int(value)
        for value in re.findall(r" recoveries=(\d+)", "\n".join(success_lines))
    ]
    object_bytes = [
        int(value)
        for value in re.findall(r" object_bytes=(\d+)", "\n".join(success_lines))
    ]
    dynamic_capacity_bytes = [
        int(value)
        for value in re.findall(
            r" dynamic_capacity_bytes=(\d+)",
            "\n".join(success_lines),
        )
    ]
    fresh_object_bytes = [
        int(value)
        for value in re.findall(
            r" fresh_object_bytes=(\d+)",
            "\n".join(success_lines),
        )
    ]
    fresh_dynamic_capacity_bytes = [
        int(value)
        for value in re.findall(
            r" fresh_dynamic_capacity_bytes=(\d+)",
            "\n".join(success_lines),
        )
    ]
    receipt_bytes = [
        int(value)
        for value in re.findall(r" receipt_bytes=(\d+)", "\n".join(success_lines))
    ]
    contract_bytes = [
        int(value)
        for value in re.findall(r" contract_bytes=(\d+)", "\n".join(success_lines))
    ]
    fresh_result_bytes = [
        int(value)
        for value in re.findall(
            r" fresh_result_bytes=(\d+)",
            "\n".join(success_lines),
        )
    ]
    require(
        len(object_bytes) == len(success_lines)
        and len(dynamic_capacity_bytes) == len(success_lines),
        "phase persistent material accounting is absent",
    )
    require(
        len(fresh_object_bytes) == len(success_lines)
        and len(fresh_dynamic_capacity_bytes) == len(success_lines),
        "fresh-parity material accounting is absent",
    )
    require(
        len(receipt_bytes) == len(success_lines)
        and len(contract_bytes) == len(success_lines)
        and len(fresh_result_bytes) == len(success_lines),
        "phase control-object material accounting is absent",
    )
    require(
        len(recovery_initializations) == len(success_lines),
        "phase recovery-initialization accounting is absent",
    )
    return {
        "success_count": len(success_lines),
        "primary_count": len(primary),
        "unrelated_primary_count": len(unrelated),
        "inverse_rejection_count": rejected,
        "primary_generation_1": True,
        "primary_generation_2_same_backing": True,
        "fresh_parity_both_edges": True,
        "canonical_tie_quotient_count": quotient_count,
        "primary_margin_guard_count": primary_margin_count,
        "persistent_object_bytes": max(object_bytes),
        "persistent_dynamic_capacity_bytes": max(dynamic_capacity_bytes),
        "fresh_object_bytes": max(fresh_object_bytes),
        "fresh_dynamic_capacity_bytes": max(fresh_dynamic_capacity_bytes),
        "receipt_bytes": max(receipt_bytes),
        "contract_bytes": max(contract_bytes),
        "fresh_result_bytes": max(fresh_result_bytes),
        "maximum_recovery_initializations": max(recovery_initializations),
        "unrelated_numerical_metrics": unrelated_metrics,
        "server_log_sha256_so_far": harness.live_runtime.sha256_file(log_path),
    }


def sampled_process_peaks(
        sidecar: Any,
        *,
        evaluation_start_rss_bytes: int,
) -> dict[str, Any]:
    telemetry = sidecar.telemetry()
    samples = telemetry.get("samples")
    require(isinstance(samples, list) and samples, "Linux process telemetry is absent")
    rss_values = [
        int(sample["rss_bytes"])
        for sample in samples
        if isinstance(sample, Mapping)
        and type(sample.get("rss_bytes")) is int
    ]
    require(
        len(rss_values) == len(samples),
        "Linux process telemetry contains an unmeasured RSS sample",
    )
    readiness_rss = getattr(sidecar, "baseline_rss_bytes", None)
    require(type(readiness_rss) is int, "Linux readiness RSS baseline is absent")
    peak_rss = max(rss_values)
    return {
        "sample_count": len(samples),
        "peak_host_rss_bytes": peak_rss,
        "readiness_host_rss_bytes": int(readiness_rss),
        "peak_host_rss_growth_from_readiness_bytes": (
            peak_rss - int(readiness_rss)
        ),
        "evaluation_start_host_rss_bytes": evaluation_start_rss_bytes,
        "peak_host_rss_growth_from_evaluation_start_bytes": (
            peak_rss - evaluation_start_rss_bytes
        ),
        "peak_gpu_dedicated_bytes": telemetry.get("peak_dedicated_bytes"),
        "semantics": (
            "maximum of every guarded Linux /proc RSS sample; growth is "
            "reported from both readiness and evaluation-start baselines"
        ),
    }


def evaluate(
        *,
        sidecar: Any,
        codec: Any,
        props: Mapping[str, Any],
        prepared: Mapping[str, Any],
        transaction_nonce: str,
        progress: dict[str, Any],
) -> dict[str, Any]:
    resources_before = harness.process_resources(sidecar, None)
    setup = parent.setup_seed(
        sidecar=sidecar,
        codec=codec,
        props=props,
        prepared=prepared,
    )
    primary_trial = f"{transaction_nonce}-primary-r2"
    primary = run_primary_sequence(
        sidecar=sidecar,
        codec=codec,
        props=props,
        setup=setup,
        trial=primary_trial,
    )
    post_primary = run_post_primary_successor(
        sidecar=sidecar,
        codec=codec,
        props=props,
        setup=setup,
        primary=primary,
        transaction_nonce=transaction_nonce,
        progress=progress,
    )

    control_child, control_tokens, control_reset = live.materialize_child(
        sidecar=sidecar,
        base_root=setup["base_root"],
        branch_tokens=setup["branch_tokens"],
        state=setup["seed_state"],
        root_id=f"{EXPERIMENT_ID}-{transaction_nonce}-controls-child",
        label=f"{transaction_nonce}:controls:initial",
    )
    ordinary_live = run_live_or_special_success(
        sidecar=sidecar,
        codec=codec,
        props=props,
        child=control_child,
        child_tokens=control_tokens,
        seed_state=setup["seed_state"],
        trial=f"{transaction_nonce}-ordinary-live",
        variant=0,
        special=False,
        one_token=False,
    )
    compact = run_live_or_special_success(
        sidecar=sidecar,
        codec=codec,
        props=props,
        child=control_child,
        child_tokens=control_tokens,
        seed_state=setup["seed_state"],
        trial=f"{transaction_nonce}-compact",
        variant=COMPACT_CLASSICAL_VARIANT,
        special=True,
        one_token=False,
    )
    dephased = run_live_or_special_success(
        sidecar=sidecar,
        codec=codec,
        props=props,
        child=control_child,
        child_tokens=control_tokens,
        seed_state=setup["seed_state"],
        trial=f"{transaction_nonce}-dephased",
        variant=DEPHASED_VARIANT,
        special=True,
        one_token=True,
        expected_token=CANDIDATE_TOKEN_IDS["A"],
    )
    reordered = run_live_or_special_success(
        sidecar=sidecar,
        codec=codec,
        props=props,
        child=control_child,
        child_tokens=control_tokens,
        seed_state=setup["seed_state"],
        trial=f"{transaction_nonce}-reordered",
        variant=REORDERED_FORWARD_VARIANT,
        special=True,
        one_token=True,
        expected_token=CANDIDATE_TOKEN_IDS["A"],
    )
    tuple_controls = run_tuple_controls(
        sidecar=sidecar,
        codec=codec,
        child=control_child,
        child_tokens=control_tokens,
        seed_state=setup["seed_state"],
        nonce=transaction_nonce,
        progress=progress,
    )
    fault_controls = run_fault_controls(
        sidecar=sidecar,
        codec=codec,
        child=control_child,
        child_tokens=control_tokens,
        seed_state=setup["seed_state"],
        nonce=transaction_nonce,
        progress=progress,
    )
    direct = run_direct_controls(
        sidecar=sidecar,
        codec=codec,
        props=props,
        child=control_child,
        child_tokens=control_tokens,
        seed_state=setup["seed_state"],
    )
    tool_canary = predecessor.run_tool_canary(sidecar)
    log_evidence = phase_log_evidence(
        sidecar=sidecar,
        primary_carrier_id=primary["carrier_id"],
        unrelated_carrier_id=(
            str(post_primary["carrier_id"])
            if isinstance(post_primary, Mapping)
            else None
        ),
    )
    resources_resident = harness.process_resources(sidecar, None)

    shutdown_restore = restore_child(control_child)
    control_erase = live.erase_child(control_child)
    base_erase = predecessor.root_action(
        action="root-erase",
        root_id=BASE_ROOT_ID,
        n_tokens=parent.EXPECTED_BASE_TOKENS,
        n_device_bytes=parent.EXPECTED_BASE_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=0,
        expected_total_device_bytes_after=0,
        expected=setup["base_root"],
    )
    shutdown_tokens, shutdown_payload, _ = derive_expanded(
        codec=codec,
        child_tokens=control_tokens,
        prior_state=setup["seed_state"],
        edge=1,
    )
    shutdown_contract = public_contract(
        trial=f"{transaction_nonce}-shutdown",
        edge=1,
        tokens=shutdown_tokens,
        variant=PRIMARY_VARIANT,
    )
    shutdown_capture = capture_boundary(
        sidecar=sidecar,
        payload=shutdown_payload,
        contract=shutdown_contract,
        label=f"{EXPERIMENT_ID}:{transaction_nonce}:shutdown-resident-capture",
    )
    resources_shutdown_resident = harness.process_resources(sidecar, None)
    sampled_peaks = sampled_process_peaks(
        sidecar,
        evaluation_start_rss_bytes=int(resources_before["host_rss_bytes"]),
    )

    gates = {
        "primary_exact_C_D_B": primary["observed_states"] == ["C", "D", "B"],
        "primary_two_restored_transactions": (
            log_evidence["primary_count"] == 2
            and log_evidence["primary_generation_2_same_backing"]
        ),
        "post_primary_successor": (
            post_primary is None
            or post_primary.get("passed") is True
        ),
        "unrelated_restored_fiber_same_backing_without_recovery": (
            post_primary is None
            or (
                log_evidence["unrelated_primary_count"]
                        == int(post_primary.get(
                            "expected_unrelated_primary_count",
                            1,
                        ))
                and log_evidence["maximum_recovery_initializations"] == 0
                and log_evidence["unrelated_numerical_metrics"] is not None
            )
        ),
        "post_success_fault_recovery_accounting": (
            post_primary is None
            or "expected_post_success_fault_recovery_initializations"
                    not in post_primary
            or log_evidence.get(
                "post_success_fault_recovery_initializations"
            ) == int(post_primary[
                "expected_post_success_fault_recovery_initializations"
            ])
        ),
        "fresh_carrier_parity": log_evidence["fresh_parity_both_edges"],
        "ordinary_live_boundary_D": ordinary_live["boundary"]["answer"] == "D",
        "compact_recurrence_D": compact["boundary"]["answer"] == "D",
        "dephased_sham_A": dephased["boundary"]["token_id"] == 32,
        "reordered_forward_A": reordered["boundary"]["token_id"] == 32,
        "all_twelve_tuple_fields_reject_and_poison": (
            {item["field"] for item in tuple_controls} == set(TUPLE_FIELDS)
            and all(
                item["denial"]["http_status"] == 400
                and item["exact_replay_after_poison"]["http_status"] == 400
                for item in tuple_controls
            )
        ),
        "all_inverse_faults_reject_without_projection": (
            {item["variant"] for item in fault_controls["inverse"]}
            == set(INVERSE_FAULT_VARIANTS)
            and all(
                item["denial"]["http_status"] == 400
                for item in fault_controls["inverse"]
            )
        ),
        "null_and_premature_reject_pre_borrow": all(
            item["denial"]["http_status"] == 400
            for item in fault_controls["pre_borrow"]
        ),
        "root_only_and_materialized_D": all(
            direct[route]["state"]["answer"] == "D"
            for route in ("root-only", "materialized")
        ),
        "exact_oracle_all_gates": exact_oracle.run_oracle()["passed"],
        "unrelated_pi_tool_canary": (
            tool_canary["validation"]["passed"] is True
        ),
        "bounded_gpu": int(
            resources_shutdown_resident["peak_gpu_dedicated_bytes"]
        )
                <= parent.MAX_GPU_BYTES,
        "bounded_host_peak_growth": (
            int(
                sampled_peaks[
                    "peak_host_rss_growth_from_readiness_bytes"
                ]
            )
            <= parent.MAX_HOST_GROWTH_BYTES
        ),
        "model_callback_count_exact": (
            len(progress["transport_attempts"]) == EXPECTED_MODEL_CALLBACKS
        ),
        "direct_protocol_action_count_exact": (
            len(progress["protocol_attempts"])
            == EXPECTED_DIRECT_PROTOCOL_ACTIONS
        ),
        "shutdown_resident_source_scheduled_after_root_zero": (
            shutdown_capture["summary"]["completion_tokens"] == 0
            and base_erase["n_roots_after"] == 0
        ),
    }
    require(all(gates.values()), "0094 runtime gates failed before shutdown")
    return {
        "id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "preregistration_attempt_id": PREREGISTRATION_ATTEMPT_ID,
        "status": "complete-before-process-closure",
        "classification_candidate": (
            str(post_primary["classification_candidate"])
            if isinstance(post_primary, Mapping)
            and post_primary.get("classification_candidate")
            else (
                "BOUNDED_LINUX_INFERENCE_ATTACHED_OWNER_BOUND_TWIN_RAIL_"
                "NUMERICAL_RESTORATION_AND_DEPENDENT_SAME_BACKING_R2_REUSE"
            )
        ),
        "restoration_class": FIBER_RESTORATION_CLASS,
        "reordered_projection_restoration_class": (
            REORDERED_PROJECTION_RESTORATION_CLASS
        ),
        "supporting_live_source_restoration_class": SOURCE_RESTORATION_CLASS,
        "setup": setup,
        "primary": primary,
        "post_primary_successor": post_primary,
        "controls": {
            "ordinary_live": ordinary_live,
            "compact_classical": compact,
            "dephased": dephased,
            "reordered_forward": reordered,
            "tuple": tuple_controls,
            "faults": fault_controls,
            "direct": direct,
        },
        "exact_oracle": exact_oracle.run_oracle(),
        "phase_log_evidence": log_evidence,
        "tool_canary": tool_canary,
        "resources": {
            "before": resources_before,
            "resident": resources_resident,
            "shutdown_resident": resources_shutdown_resident,
            "sampled_process_peaks": sampled_peaks,
            "host_logit_bytes": parent.EXPECTED_TERMINAL_LOGITS_BYTES,
            "hypothesis_boundary_device_bytes_structural": (
                HYPOTHESIS_DEVICE_BYTES
            ),
            "hypothesis_boundary_device_bytes_basis": {
                "source_child_tokens": parent.EXPECTED_CHILD_TOKENS,
                "source_child_device_bytes": parent.EXPECTED_CHILD_DEVICE_BYTES,
                "public_extension_tokens": HYPOTHESIS_FRESH_TOKENS,
                "device_bytes_per_token": parent.DEVICE_BYTES_PER_TOKEN,
                "formula": (
                    "source_child_device_bytes + "
                    "public_extension_tokens * device_bytes_per_token"
                ),
                "direct_allocation_measurement": False,
            },
            "persistent_phase_carrier_cells": 8,
            "persistent_phase_carrier_bytes": 128,
            "persistent_phase_carrier_object_bytes": (
                log_evidence["persistent_object_bytes"]
            ),
            "persistent_phase_carrier_dynamic_capacity_bytes": (
                log_evidence["persistent_dynamic_capacity_bytes"]
            ),
            "fresh_parity_carrier_cells_per_primary_transaction": 8,
            "fresh_parity_carrier_cell_bytes_per_primary_transaction": 128,
            "fresh_parity_carrier_object_bytes_per_primary_transaction": (
                log_evidence["fresh_object_bytes"]
            ),
            "fresh_parity_carrier_dynamic_capacity_bytes_per_primary_transaction": (
                log_evidence["fresh_dynamic_capacity_bytes"]
            ),
            "runtime_control_object_bytes": {
                "persistent_route_receipt_count": 1,
                "persistent_route_receipt_each": (
                    log_evidence["receipt_bytes"]
                ),
                "persistent_route_receipt_logical_bytes": (
                    log_evidence["receipt_bytes"]
                ),
                "transient_contract_max_simultaneously_live_count": 1,
                "transient_contract_each": log_evidence["contract_bytes"],
                "primary_only_fresh_parity_result_bytes": (
                    log_evidence["fresh_result_bytes"]
                ),
                "note": (
                    "the fresh result is scoped only to the primary helper "
                    "call; whole-process sampled RSS bounds compiler stack "
                    "and allocator backing"
                ),
            },
            "fixed_logical_work_bytes": {
                "four_candidate_float_logits": 16,
                "five_four_double_probability_angle_score_arrays": 160,
                "two_complex_double_hadamard_temporaries": 32,
                "one_projected_token": 4,
                "note": (
                    "logical local work sizes; whole-process sampled RSS "
                    "captures compiler stack, allocator, and library backing"
                ),
            },
            "fixed_operation_counts": {
                "phase_transactions_including_fresh_and_fault_controls": 9,
                "softmax_exponentials": 76,
                "softmax_reductions": 19,
                "softmax_divisions": 76,
                "acos_evaluations": 72,
                "complex_phase_multiplications": 68,
                "hadamard_pair_transforms": 72,
                "magnitude_squares": 36,
                "strict_argmax_comparisons": 54,
                "reordered_finite_score_checks": 4,
                "reordered_minmax_comparisons_upper_bound": 6,
                "reordered_spread_subtractions": 1,
                "reordered_spread_tolerance_comparisons": 1,
                "primary_margin_scan_and_threshold_comparisons": 28,
                "primary_post_transform_acceptance_boolean_checks": 4,
                "restoration_cell_comparisons": 144,
            } if post_primary is None else {
                key: value + int(
                    post_primary.get("fixed_operation_count_deltas", {}).get(
                        key,
                        0,
                    )
                )
                for key, value in {
                    "phase_transactions_including_fresh_and_fault_controls": 9,
                    "softmax_exponentials": 76,
                    "softmax_reductions": 19,
                    "softmax_divisions": 76,
                    "acos_evaluations": 72,
                    "complex_phase_multiplications": 68,
                    "hadamard_pair_transforms": 72,
                    "magnitude_squares": 36,
                    "strict_argmax_comparisons": 54,
                    "reordered_finite_score_checks": 4,
                    "reordered_minmax_comparisons_upper_bound": 6,
                    "reordered_spread_subtractions": 1,
                    "reordered_spread_tolerance_comparisons": 1,
                    "primary_margin_scan_and_threshold_comparisons": 28,
                    "primary_post_transform_acceptance_boolean_checks": 4,
                    "restoration_cell_comparisons": 144,
                }.items()
            },
            "maximum_gpu_bytes": parent.MAX_GPU_BYTES,
            "maximum_host_growth_bytes": parent.MAX_HOST_GROWTH_BYTES,
        },
        "shutdown_control": {
            "restore": shutdown_restore,
            "child_erase": control_erase,
            "base_erase": base_erase,
            "capture": shutdown_capture,
            "contract": shutdown_contract,
            "expected_shutdown_live_poisoned": 1,
            "expected_shutdown_twin_rail_unresolved": 0,
            "fiber_disconnect_poison_control": (
                "bounded C++ selftest only; the HTTP transaction is atomic"
            ),
        },
        "gates": gates,
        "model_callbacks": len(progress["transport_attempts"]),
        "direct_protocol_actions": len(progress["protocol_attempts"]),
        "verdict": "accept-pending-exact-process-closure",
        "automatic_promotion": False,
        "claim_ceiling": (
            str(post_primary["claim_ceiling"])
            if isinstance(post_primary, Mapping)
            and post_primary.get("claim_ceiling")
            else (
                "One bounded inference-attached eight-complex-cell twin-rail "
                "cell array with numerical physical restoration, dependent "
                "same-backing R2 reuse, exact C-to-D-to-B utility, fixed shams, "
                "and separately declared closure of the live CUDA/logit source. "
                "The advancing owner metadata, counters, allocator state, and "
                "full 312-byte object are not restored. The identical compact "
                "recurrence remains cheaper; no unrelated restored-carrier "
                "reuse, distinct phase resource, speed advantage, full model-"
                "carrier restoration, Small Wall, general catalytic inference, "
                "or unbounded claim."
            )
        ),
    }


def twin_rail_host_object_identities() -> dict[str, Any]:
    build_root = parent.BUILD_ROOT
    paths = {
        "server_context_object": (
            build_root / "tools" / "server" / "CMakeFiles"
            / "server-context.dir" / "server-context.cpp.o"
        ),
        "twin_rail_object": (
            build_root / "tools" / "server" / "CMakeFiles"
            / "server-context.dir" / "neo3000-twin-rail-fiber.cpp.o"
        ),
        "server_context_archive": (
            build_root / "tools" / "server" / "libserver-context.a"
        ),
    }
    return {
        name: {
            "relative_path": path.resolve(strict=True)
                    .relative_to(ROOT.resolve(strict=True)).as_posix(),
            **parent.runtime.file_identity(path.resolve(strict=True)),
        }
        for name, path in paths.items()
    }


def runtime_manifest_template(runtime_source_commit: str) -> dict[str, Any]:
    manifest = _BASE_RUNTIME_MANIFEST_TEMPLATE(runtime_source_commit)
    manifest["causal_intervention"] = (
        "Attach one persistent eight-complex-cell twin-rail carrier to the "
        "fixed public 780-token A/B/C/D live-terminal boundary; no CUDA "
        "translation unit or ordinary live-terminal route changes."
    )
    manifest["fiber_restoration_class"] = FIBER_RESTORATION_CLASS
    manifest["supporting_live_source_restoration_class"] = SOURCE_RESTORATION_CLASS
    manifest["host_objects"] = twin_rail_host_object_identities()
    manifest["configured_cuda_units_changed"] = 0
    manifest["exact_oracle"] = exact_oracle.run_oracle()
    return manifest


def validate_runtime_manifest() -> dict[str, Any]:
    receipt = _BASE_VALIDATE_RUNTIME_MANIFEST()
    manifest = json.loads(DEFAULT_RUNTIME_MANIFEST.read_text(encoding="utf-8"))
    require(
        manifest.get("host_objects") == twin_rail_host_object_identities()
        and manifest.get("configured_cuda_units_changed") == 0
        and manifest.get("fiber_restoration_class") == FIBER_RESTORATION_CLASS
        and manifest.get("supporting_live_source_restoration_class")
                == SOURCE_RESTORATION_CLASS
        and manifest.get("exact_oracle", {}).get("passed") is True,
        "0094 host-object or restoration manifest closure changed",
    )
    return {
        **receipt,
        "host_objects": manifest["host_objects"],
        "configured_cuda_units_changed": 0,
        "exact_oracle_passed": True,
    }


def audit_shutdown(
        sidecar: Any,
        cleanup: Mapping[str, Any],
) -> dict[str, Any]:
    receipt = _BASE_AUDIT_SHUTDOWN(sidecar, cleanup)
    if receipt.get("candidate_started") is not True:
        receipt["twin_rail"] = {
            "summary_count": 0,
            "poisoned": 0,
            "unresolved": 0,
            "passed": True,
        }
        return receipt
    log_path = sidecar.run_root / "server.log"
    text = log_path.read_text(encoding="utf-8", errors="replace")
    matches = re.findall(
        r"neo3000 twin-rail shutdown custody poisoned=(\d+) unresolved=(\d+)",
        text,
    )
    require(len(matches) == 1, "0094 twin-rail shutdown summary count changed")
    poisoned, unresolved = (int(item) for item in matches[0])
    require(
        poisoned == 0 and unresolved == 0,
        "0094 shutdown unexpectedly found a resident twin-rail carrier",
    )
    shutdown_resident_capture_scheduled = re.search(
        r"neo3000 one-use live terminal boundary captured "
        r"boundary=neo-exp-\d+/[^ ]+-shutdown/edge-1/variant-0/terminal ",
        text,
    ) is not None
    expected_live_poisoned = int(shutdown_resident_capture_scheduled)
    require(
        receipt["poisoned_boundaries"] == expected_live_poisoned
        and receipt["unresolved_boundaries"] == 0,
        "0094 shutdown live-source poison did not match the public "
        "shutdown-resident capture lifecycle",
    )
    receipt["twin_rail"] = {
        "summary_count": 1,
        "poisoned": poisoned,
        "unresolved": unresolved,
        "passed": True,
    }
    receipt["shutdown_resident_capture_scheduled"] = (
        shutdown_resident_capture_scheduled
    )
    receipt["expected_live_poisoned"] = expected_live_poisoned
    return receipt


def static_audit() -> dict[str, Any]:
    temporary_install = not _PARENT_INSTALLED_FOR_MAIN
    if temporary_install:
        configure_parent()
    try:
        parent.configure_linux_geometry()
        context = (ROOT / "tools" / "server" / "server-context.cpp").read_text(
            encoding="utf-8"
        )
        fiber = (
            ROOT / "tools" / "server" / "neo3000-twin-rail-fiber.cpp"
        ).read_text(encoding="utf-8")
        header = (
            ROOT / "tools" / "server" / "neo3000-twin-rail-fiber.h"
        ).read_text(encoding="utf-8")
        cmake = (ROOT / "tools" / "server" / "CMakeLists.txt").read_text(
            encoding="utf-8"
        )
        source = Path(__file__).read_text(encoding="utf-8")
        oracle = exact_oracle.run_oracle()
        gates = {
        "fixed_public_geometry": (
            parent.EXPECTED_SUCCESSOR_TOKENS == 777
            and PUBLIC_SCHEMA_PREFIX == (4754, 8944, 3147)
            and HYPOTHESIS_TOKENS == 780
            and CANDIDATE_TOKEN_IDS == {"A": 32, "B": 33, "C": 34, "D": 35}
        ),
        "persistent_eight_cell_carrier": (
            "cell_count = hypothesis_count * 2" in header
            and "carrier_bytes = cell_count * sizeof(std::complex<double>)"
            in header
            and "twin_rail_carrier twin_rail;" in context
        ),
        "input_boundary_semantically_bound": (
            '"fnv1a64:" +' in context
            and "neo3000_prompt_fnv1a64(task.tokens)" in context
            and '"input_boundary_id": f"fnv1a64:{prompt_fnv1a64(tokens)}"'
            in source
        ),
        "noncommuting_public_modules": (
            "apply_phase(forward_angles, false);" in fiber
            and "apply_hadamard();" in fiber
            and "REORDERED_FORWARD" in fiber
        ),
        "inverse_rematerialized_from_logits": (
            "inverse_probabilities" in fiber
            and "inverse_angles" in fiber
            and "apply_hadamard();" in fiber
            and "apply_phase(inverse_angles, true);" in fiber
        ),
        "restoration_before_projection_and_response": (
            context.index("slot.twin_rail.transform_and_restore(")
            < context.index("slot.terminal_logits.clear();",
                            context.index("slot.twin_rail.transform_and_restore("))
            < context.index("slot.twin_rail.take_final_projection()")
            < context.index("process_token(result, slot)",
                            context.index("slot.twin_rail.transform_and_restore("))
        ),
        "no_pre_restoration_stream_begin": (
            "slot.task->params.stream && !twin_rail_source" in context
            and "slot.task->params.stream && twin_rail_source" in context
        ),
        "fresh_parity_internal_and_final_only": (
            "run_fresh_twin_rail_parity(" in context
            and "fresh_id != id" in context
        ),
        "shutdown_poison": (
            "neo3000 twin-rail shutdown custody poisoned=%zu unresolved=%zu"
            in context
            and "slot.twin_rail.poison();" in context
        ),
        "all_fault_variants": all(
            name in header
            for name in (
                "DEPHASED_SHAM",
                "REORDERED_FORWARD",
                "MISSING_INVERSE",
                "WRONG_INVERSE",
                "REORDERED_INVERSE",
                "NULL_CARRIER",
                "PREMATURE_PROJECT",
                "COMPACT_CLASSICAL",
            )
        ),
        "server_build_includes_carrier": (
            "neo3000-twin-rail-fiber.cpp" in cmake
            and "neo3000-twin-rail-fiber.h" in cmake
        ),
        "exact_oracle": oracle["passed"] and all(oracle["gates"].values()),
        "controller_full_controls": (
            "run_tuple_controls(" in source
            and "run_fault_controls(" in source
            and "run_direct_controls(" in source
            and "predecessor.run_tool_canary(sidecar)" in source
        ),
        "no_cuda_intervention": (
            ".cu" not in fiber
            and "configured_cuda_units_changed" in source
        ),
        "no_hidden_intermediate_wire_fields": all(
            term not in capture_payload({}, {})
            for term in ("logits", "probabilities", "angles", "scores", "phase_cells")
        ),
        }
        require(all(gates.values()), "0094 static gates failed")
        runtime_evidence = (
            validate_runtime_manifest()
            if DEFAULT_RUNTIME_MANIFEST.is_file()
            else {"pending_exact_clean_pushed_build": True}
        )
        return {
            "id": EXPERIMENT_ID,
            "attempt_id": ATTEMPT_ID,
            "preregistration_attempt_id": PREREGISTRATION_ATTEMPT_ID,
            "gates": gates,
            "exact_oracle": oracle,
            "runtime": runtime_evidence,
            "scientific_contact": False,
        }
    finally:
        if temporary_install:
            parent.restore_inherited_geometry()
            restore_parent()


def main() -> int:
    global _PARENT_INSTALLED_FOR_MAIN
    _PARENT_INSTALLED_FOR_MAIN = True
    configure_parent()
    parent.evaluate = evaluate
    parent.static_audit = static_audit
    parent.runtime_manifest_template = runtime_manifest_template
    parent.validate_runtime_manifest = validate_runtime_manifest
    parent.audit_shutdown_live_terminal_custody = audit_shutdown
    return parent.main()


if __name__ == "__main__":
    raise SystemExit(main())
