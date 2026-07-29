#!/usr/bin/env python3
"""neo-exp-0091: Linux-qualified owner-bound live-terminal successor.

The experiment keeps the existing generic C++ one-use live CUDA KV/recurrent
state plus exact terminal-logits mechanism fixed.  It replaces only the stale
Windows-era controller geometry with the prospectively qualified native-Linux
607-bound C -> D -> B identities from neo-exp-0090.

This route declares closure.  It does not claim inverse restoration, restored
carrier reuse, phase advantage, or unbounded catalytic inference.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence, TextIO

import catalytic_frontier_harness as harness
import catalytic_frontier_linux_chain_identity_qualifier as geometry
import catalytic_frontier_linux_cuda_identity_qualifier as runtime
import catalytic_frontier_linux_sidecar as linux_sidecar
import catalytic_frontier_live_terminal_boundary as live
import catalytic_frontier_single_request_latency as latency
import catalytic_frontier_successor_terminal_pipeline as predecessor
import catalytic_frontier_terminal_logits_continuation as terminal


EXPERIMENT_ID = "neo-exp-0091"
ATTEMPT_ID = "frontier-attempt-0133"
PREREGISTRATION_ATTEMPT_ID = "frontier-attempt-0132"
ROOT = Path(__file__).resolve().parents[1]
RESTORATION_CLASS = "DECLARED_CLOSURE"
PROJECTION_POLICY = "FINAL_TOKEN_STREAM_ONLY"
PORT_OWNER = "neo-exp-0091-linux-successor-terminal-consumer"
PORT_TYPE = "agents-a1-live-kv-recurrent-plus-f32-terminal-logits-v1"
MODULE_ID = "successor-terminal-sample"

DEFAULT_BINARY = (
    ROOT / "build" / "linux-cuda-0091-custody" / "bin" / "llama-server"
)
DEFAULT_MODEL = runtime.DEFAULT_MODEL
DEFAULT_COMPILER_CONTRACT = runtime.DEFAULT_COMPILER_CONTRACT
DEFAULT_RUNTIME_MANIFEST = ROOT / "lab" / "neo-exp-0091-runtime-manifest.json"
DEFAULT_OUTPUT = ROOT / "lab" / f"{EXPERIMENT_ID}.local.json"
DEFAULT_LOCK = (
    ROOT / "build" / "linux-catalytic" / f"{EXPERIMENT_ID}.active-lock.json"
)
DEFAULT_CONSUMED_MARKER = (
    ROOT / "build" / "linux-catalytic" / f"{EXPERIMENT_ID}.consumed-marker.json"
)
DEFAULT_RUN_PARENT = ROOT / "build" / "linux-catalytic"
BUILD_ROOT = DEFAULT_BINARY.parent.parent
CUDA_OBJECT_ROOT = (
    BUILD_ROOT / "ggml" / "src" / "ggml-cuda" / "CMakeFiles"
    / "ggml-cuda.dir"
)
CUDA_LINK_COMMAND = CUDA_OBJECT_ROOT / "link.txt"
SERVER_LINK_COMMAND = (
    BUILD_ROOT / "tools" / "server" / "CMakeFiles"
    / "llama-server.dir" / "link.txt"
)

BASE_ROOT_ID = f"{EXPERIMENT_ID}-base-684"
ROUTES = ("live-terminal", "root-only", "materialized")
TRIAL_ROUTE_ORDERS = (
    ("live-terminal", "root-only", "materialized"),
    ("root-only", "materialized", "live-terminal"),
    ("materialized", "live-terminal", "root-only"),
)
WARMUP_TRIALS = 1
COUNTED_TRIALS = 3
EXPECTED_MODEL_CALLBACKS = 74
EXPECTED_DIRECT_PROTOCOL_ACTIONS = 27

EXPECTED_RETAINED_TOKENS = geometry.EXPECTED_RETAINED_COUNT
EXPECTED_BASE_TOKENS = geometry.EXPECTED_BASE_COUNT
EXPECTED_BRANCH_TOKENS = geometry.EXPECTED_BRANCH_COUNT
EXPECTED_CHILD_TOKENS = 690
EXPECTED_SUCCESSOR_TOKENS = geometry.EXPECTED_SUCCESSOR_COUNT
EXPECTED_SUCCESSOR_FRESH_TOKENS = geometry.EXPECTED_SUFFIX_COUNT
EXPECTED_REBASE_FRESH_TOKENS = EXPECTED_CHILD_TOKENS - EXPECTED_BASE_TOKENS
EXPECTED_FRESH_PER_CATALYTIC_EDGE = (
    EXPECTED_SUCCESSOR_FRESH_TOKENS + EXPECTED_REBASE_FRESH_TOKENS
)
EXPECTED_AVOIDED_PER_EDGE = (
    EXPECTED_SUCCESSOR_TOKENS - EXPECTED_FRESH_PER_CATALYTIC_EDGE
)
EXPECTED_AVOIDED_PER_TRIAL = EXPECTED_AVOIDED_PER_EDGE * 2
EXPECTED_COUNTED_AVOIDED_TOKENS = COUNTED_TRIALS * EXPECTED_AVOIDED_PER_TRIAL

# The accepted native root law adds exactly 20,480 CUDA bytes per token.
DEVICE_BYTES_PER_TOKEN = 20_480
EXPECTED_BASE_DEVICE_BYTES = 79_872_000
EXPECTED_BRANCH_DEVICE_BYTES = 79_892_480
EXPECTED_CHILD_DEVICE_BYTES = 79_994_880
EXPECTED_SUCCESSOR_TERMINAL_DEVICE_BYTES = 81_776_640
EXPECTED_BASE_CHILD_DEVICE_BYTES = (
    EXPECTED_BASE_DEVICE_BYTES + EXPECTED_CHILD_DEVICE_BYTES
)
EXPECTED_MAX_LIVE_DEVICE_BYTES = EXPECTED_BASE_CHILD_DEVICE_BYTES

EXPECTED_TERMINAL_LOGITS = 248_320
EXPECTED_TERMINAL_LOGITS_BYTES = 993_280
MAX_GPU_BYTES = 6000 * 1024 * 1024
MAX_HOST_GROWTH_BYTES = 4 * 1024 * 1024 * 1024

EXPECTED_TASK_A_GENERATED_SHA256 = geometry.EXPECTED_TASK_A_GENERATED_SHA256
EXPECTED_RETAINED_SHA256 = geometry.EXPECTED_RETAINED_SHA256
EXPECTED_BASE_SHA256 = geometry.EXPECTED_BASE_SHA256
EXPECTED_BRANCH_SHA256 = geometry.EXPECTED_BRANCH_SHA256
EXPECTED_GENERATED_SHA256 = dict(geometry.EXPECTED_GENERATED_SHA256)
EXPECTED_CHILD_SHA256 = dict(geometry.EXPECTED_CHILD_SHA256)
EXPECTED_REQUEST_SHA256 = {
    "C": geometry.EXPECTED_REQUEST_SHA256[1],
    "D": geometry.EXPECTED_REQUEST_SHA256[2],
}
EXPECTED_SUFFIX_SHA256 = geometry.EXPECTED_SUFFIX_SHA256

# These are zero-contact tokenizer-derived payload identities.  They are filled
# prospectively before preregistration and must remain exact at execution.
EXPECTED_SEED_PAYLOAD_SHA256 = (
    "FB137945B3D90D507AE927EA26D8C8F1C5284555EE572C177B14712EAD69D8CC"
)
EXPECTED_SUCCESSOR_PAYLOAD_SHA256 = {
    True: {
        "C": "B74E270387098557DE132260F34645A194E2F74A34E7D5CBD105DED59C438B8B",
        "D": "A72562FA937E0D8B03F483333681DEC3FCC8578E734FF167C9EF37DFD075501C",
    },
    False: {
        "C": geometry.EXPECTED_REQUEST_PAYLOAD_SHA256[1],
        "D": geometry.EXPECTED_REQUEST_PAYLOAD_SHA256[2],
    },
}

MIN_CONSUMER_TTFT_SPEEDUP = 5.0
MIN_LIVE_VS_MATERIALIZED_WALL_SPEEDUP = 2.5
MIN_LIVE_VS_ROOT_ONLY_WALL_RATIO = 0.80

TUPLE_MUTATION_FIELDS = (
    "boundary_id",
    "carrier_id",
    "outer_lease",
    "generation",
    "port_owner",
    "port_type",
    "module_id",
    "module_variant",
    "module_ordinal",
    "input_boundary_id",
    "projection_policy",
    "restoration_policy",
)
INHERITED_DERIVE_SUCCESSOR = predecessor.derive_successor
_INHERITED_PREDECESSOR = {
    name: getattr(predecessor, name)
    for name in (
        "EXPERIMENT_ID",
        "ATTEMPT_ID",
        "BASE_ROOT_ID",
        "EXPECTED_BASE_TOKENS",
        "EXPECTED_BRANCH_TOKENS",
        "EXPECTED_CHILD_TOKENS",
        "EXPECTED_SUCCESSOR_TOKENS",
        "EXPECTED_SUCCESSOR_FRESH_TOKENS",
        "EXPECTED_REBASE_FRESH_TOKENS",
        "EXPECTED_BASE_DEVICE_BYTES",
        "EXPECTED_SEED_TERMINAL_DEVICE_BYTES",
        "EXPECTED_CHILD_DEVICE_BYTES",
        "EXPECTED_SUCCESSOR_TERMINAL_DEVICE_BYTES",
        "EXPECTED_BASE_CHILD_DEVICE_BYTES",
        "EXPECTED_MAX_PIPELINE_DEVICE_BYTES",
        "EXPECTED_SETUP_THREE_ROOT_DEVICE_BYTES",
        "EXPECTED_FRESH_PER_CATALYTIC_EDGE",
        "EXPECTED_AVOIDED_PER_EDGE",
        "EXPECTED_AVOIDED_PER_TRIAL",
        "EXPECTED_BRANCH_SHA256",
        "EXPECTED_SUFFIX_SHA256",
        "EXPECTED_GENERATED_SHA256",
        "EXPECTED_CHILD_SHA256",
        "EXPECTED_REQUEST_SHA256",
        "erase_child",
        "derive_successor",
    )
}
_INHERITED_LIVE = {
    name: getattr(live, name)
    for name in (
        "EXPERIMENT_ID",
        "ATTEMPT_ID",
        "RESTORATION_CLASS",
        "PROJECTION_POLICY",
        "PORT_OWNER",
        "PORT_TYPE",
        "MODULE_ID",
    )
}
_INHERITED_TERMINAL_RETAINED = terminal.EXPECTED_RETAINED_TOKENS

RUNTIME_ARTIFACT_PATHS = {
    "binary": DEFAULT_BINARY,
    "server_impl_library": (
        DEFAULT_BINARY.parent / "libllama-server-impl.so"
    ),
    "cmake_cache": DEFAULT_BINARY.parent.parent / "CMakeCache.txt",
    "compile_commands": DEFAULT_BINARY.parent.parent / "compile_commands.json",
    "build_log": ROOT / "build" / "linux-cuda-0091-custody-build.log",
    "cuda_link_command": CUDA_LINK_COMMAND,
    "server_link_command": SERVER_LINK_COMMAND,
    "compiler_contract": DEFAULT_COMPILER_CONTRACT,
    "compiler_executable": (
        DEFAULT_COMPILER_CONTRACT.parent
        / "clang-root"
        / "usr"
        / "bin"
        / "clang++-21"
    ),
    "cuda_ptxas": (
        DEFAULT_COMPILER_CONTRACT.parent
        / "cuda13-compat2-toolkit"
        / "bin"
        / "ptxas"
    ),
    "cuda_fatbinary": (
        DEFAULT_COMPILER_CONTRACT.parent
        / "cuda13-compat2-toolkit"
        / "bin"
        / "fatbinary"
    ),
    "cuda_libdevice": (
        DEFAULT_COMPILER_CONTRACT.parent
        / "cuda13-compat2-toolkit"
        / "nvvm"
        / "libdevice"
        / "libdevice.10.bc"
    ),
    "server_context_source": ROOT / "tools" / "server" / "server-context.cpp",
    "server_context_header": ROOT / "tools" / "server" / "server-context.h",
    "server_entrypoint_source": ROOT / "tools" / "server" / "server.cpp",
    "server_schema_source": ROOT / "tools" / "server" / "server-schema.cpp",
    "server_task_header": ROOT / "tools" / "server" / "server-task.h",
    "server_task_implementation": ROOT / "tools" / "server" / "server-task.cpp",
    "live_boundary_source": (
        ROOT / "scripts" / "catalytic_frontier_live_terminal_boundary.py"
    ),
    "controller": Path(__file__),
    "controller_test": (
        ROOT
        / "scripts"
        / "test_catalytic_frontier_linux_live_terminal_successor.py"
    ),
    "live_boundary_test": (
        ROOT / "scripts" / "test_catalytic_frontier_live_terminal_boundary.py"
    ),
    "harness_source": ROOT / "scripts" / "catalytic_frontier_harness.py",
    "pipeline_source": (
        ROOT / "scripts" / "catalytic_frontier_successor_terminal_pipeline.py"
    ),
    "sidecar_source": ROOT / "scripts" / "catalytic_frontier_linux_sidecar.py",
}
SOURCE_ARTIFACT_NAMES = {
    "server_context_source",
    "server_context_header",
    "server_entrypoint_source",
    "server_schema_source",
    "server_task_header",
    "server_task_implementation",
    "live_boundary_source",
    "controller",
    "controller_test",
    "live_boundary_test",
    "harness_source",
    "pipeline_source",
    "sidecar_source",
}
EXPECTED_LIVE_LOG_SURFACE = {
    "capture_logit_fingerprint_absent": True,
    "sample_logit_fingerprint_absent": True,
    "raw_logits_absent": True,
    "shutdown_poison_marker_present": True,
}


class ExperimentError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ExperimentError(message)


def canonical_sha256(value: Any) -> str:
    return harness.sha256_bytes(harness.carrier.canonical_json_bytes(value))


class FailureProofTextIO:
    def __init__(self, inner: TextIO):
        self.inner = inner

    def write(self, value: str) -> int:
        try:
            return self.inner.write(value)
        except (OSError, ValueError):
            return len(value)

    def flush(self) -> None:
        try:
            self.inner.flush()
        except (OSError, ValueError):
            return None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


def dynamic_erase_child(
    child: Mapping[str, Any],
    *,
    expected_roots_after: int = 1,
    expected_total_device_bytes_after: int | None = None,
) -> dict[str, Any]:
    expected_bytes = (
        EXPECTED_BASE_DEVICE_BYTES
        if expected_total_device_bytes_after is None
        else expected_total_device_bytes_after
    )
    return predecessor.root_action(
        action="root-erase",
        root_id=str(child["root_id"]),
        n_tokens=EXPECTED_CHILD_TOKENS,
        n_device_bytes=EXPECTED_CHILD_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=expected_roots_after,
        expected_total_device_bytes_after=expected_bytes,
        expected=child,
    )


def configure_linux_geometry() -> dict[str, Any]:
    """Bind inherited route helpers to the exact public 0091 geometry."""
    values = {
        "EXPERIMENT_ID": EXPERIMENT_ID,
        "ATTEMPT_ID": ATTEMPT_ID,
        "BASE_ROOT_ID": BASE_ROOT_ID,
        "EXPECTED_BASE_TOKENS": EXPECTED_BASE_TOKENS,
        "EXPECTED_BRANCH_TOKENS": EXPECTED_BRANCH_TOKENS,
        "EXPECTED_CHILD_TOKENS": EXPECTED_CHILD_TOKENS,
        "EXPECTED_SUCCESSOR_TOKENS": EXPECTED_SUCCESSOR_TOKENS,
        "EXPECTED_SUCCESSOR_FRESH_TOKENS": EXPECTED_SUCCESSOR_FRESH_TOKENS,
        "EXPECTED_REBASE_FRESH_TOKENS": EXPECTED_REBASE_FRESH_TOKENS,
        "EXPECTED_BASE_DEVICE_BYTES": EXPECTED_BASE_DEVICE_BYTES,
        "EXPECTED_SEED_TERMINAL_DEVICE_BYTES": EXPECTED_BRANCH_DEVICE_BYTES,
        "EXPECTED_CHILD_DEVICE_BYTES": EXPECTED_CHILD_DEVICE_BYTES,
        "EXPECTED_SUCCESSOR_TERMINAL_DEVICE_BYTES": (
            EXPECTED_SUCCESSOR_TERMINAL_DEVICE_BYTES
        ),
        "EXPECTED_BASE_CHILD_DEVICE_BYTES": EXPECTED_BASE_CHILD_DEVICE_BYTES,
        "EXPECTED_MAX_PIPELINE_DEVICE_BYTES": (
            EXPECTED_BASE_CHILD_DEVICE_BYTES
            + EXPECTED_SUCCESSOR_TERMINAL_DEVICE_BYTES
        ),
        "EXPECTED_SETUP_THREE_ROOT_DEVICE_BYTES": (
            EXPECTED_BASE_DEVICE_BYTES
            + EXPECTED_BRANCH_DEVICE_BYTES
            + EXPECTED_CHILD_DEVICE_BYTES
        ),
        "EXPECTED_FRESH_PER_CATALYTIC_EDGE": (
            EXPECTED_FRESH_PER_CATALYTIC_EDGE
        ),
        "EXPECTED_AVOIDED_PER_EDGE": EXPECTED_AVOIDED_PER_EDGE,
        "EXPECTED_AVOIDED_PER_TRIAL": EXPECTED_AVOIDED_PER_TRIAL,
        "EXPECTED_BRANCH_SHA256": EXPECTED_BRANCH_SHA256,
        "EXPECTED_SUFFIX_SHA256": EXPECTED_SUFFIX_SHA256,
        "EXPECTED_GENERATED_SHA256": EXPECTED_GENERATED_SHA256,
        "EXPECTED_CHILD_SHA256": EXPECTED_CHILD_SHA256,
        "EXPECTED_REQUEST_SHA256": EXPECTED_REQUEST_SHA256,
    }
    for name, value in values.items():
        setattr(predecessor, name, value)
    predecessor.erase_child = dynamic_erase_child
    predecessor.derive_successor = derive_successor
    terminal.EXPECTED_RETAINED_TOKENS = EXPECTED_RETAINED_TOKENS

    live.EXPERIMENT_ID = EXPERIMENT_ID
    live.ATTEMPT_ID = ATTEMPT_ID
    live.RESTORATION_CLASS = RESTORATION_CLASS
    live.PROJECTION_POLICY = PROJECTION_POLICY
    live.PORT_OWNER = PORT_OWNER
    live.PORT_TYPE = PORT_TYPE
    live.MODULE_ID = MODULE_ID
    return values


def restore_inherited_geometry() -> None:
    for name, value in _INHERITED_PREDECESSOR.items():
        setattr(predecessor, name, value)
    for name, value in _INHERITED_LIVE.items():
        setattr(live, name, value)
    terminal.EXPECTED_RETAINED_TOKENS = _INHERITED_TERMINAL_RETAINED


class ContactJournalSidecar:
    """Persist transport intent before every model-bearing callback."""

    def __init__(
        self,
        sidecar: linux_sidecar.LinuxSidecar,
        progress: dict[str, Any],
        consumed_marker: Path,
        expected_commit: str,
    ):
        self.sidecar = sidecar
        self.progress = progress
        self.consumed_marker = consumed_marker
        self.expected_commit = expected_commit

    def _guard(
        self,
        method_name: str,
        label: str,
        callback: Callable[[], Any],
        *,
        timeout: float,
        **kwargs: Any,
    ) -> Any:
        ordinal = len(self.progress.setdefault("transport_attempts", []))

        def attempt_transport() -> Any:
            marker = terminal.write_exclusive_json(
                self.sidecar.run_root
                / f"model-transport-{ordinal:03d}.json",
                {
                    "id": EXPERIMENT_ID,
                    "attempt_id": ATTEMPT_ID,
                    "ordinal": ordinal,
                    "label": label,
                    "created_unix_ns": time.time_ns(),
                    "meaning": (
                        "the fixed model callback is next; no output has been "
                        "inspected to choose this request"
                    ),
                },
            )
            if ordinal == 0:
                require(
                    label == f"frontier:{EXPERIMENT_ID}:task-a",
                    "first model callback is not the frozen Task-A qualifier",
                )
                consumption = terminal.write_exclusive_json(
                    self.consumed_marker,
                    {
                        "id": EXPERIMENT_ID,
                        "attempt_id": ATTEMPT_ID,
                        "expected_commit": self.expected_commit,
                        "created_unix_ns": time.time_ns(),
                        "first_transport_ordinal": 0,
                        "meaning": (
                            "the first 0091 model callback is next; this exact "
                            "experiment is conservatively consumed and cannot "
                            "be launched again"
                        ),
                    },
                )
                self.progress["consumption_marker"] = consumption
                self.progress["scientific_contact"] = True
            else:
                require(
                    self.consumed_marker.is_file(),
                    "later transport lost the durable consumption marker",
                )
            self.progress["transport_attempts"].append(marker)
            return callback()

        method = getattr(self.sidecar, method_name)
        return method(
            label,
            attempt_transport,
            timeout=timeout,
            **kwargs,
        )

    def guarded(
        self,
        label: str,
        callback: Callable[[], Any],
        *,
        timeout: float,
        **kwargs: Any,
    ) -> Any:
        return self._guard(
            "guarded",
            label,
            callback,
            timeout=timeout,
            **kwargs,
        )

    def guarded_batch_member(
        self,
        label: str,
        callback: Callable[[], Any],
        *,
        timeout: float,
        **kwargs: Any,
    ) -> Any:
        return self._guard(
            "guarded_batch_member",
            label,
            callback,
            timeout=timeout,
            **kwargs,
        )

    def guarded_profiled(
        self,
        label: str,
        callback: Callable[[], Any],
        *,
        timeout: float,
        **kwargs: Any,
    ) -> Any:
        return self._guard(
            "guarded_profiled",
            label,
            callback,
            timeout=timeout,
            **kwargs,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self.sidecar, name)


def acquire_lock(path: Path, expected_commit: str) -> dict[str, Any]:
    return terminal.write_exclusive_json(
        path,
        {
            "id": EXPERIMENT_ID,
            "attempt_id": ATTEMPT_ID,
            "expected_commit": expected_commit,
            "pid": os.getpid(),
            "created_unix_ns": time.time_ns(),
            "meaning": "exclusive owner-bound Linux live-terminal custody",
        },
    )


def release_lock(path: Path) -> dict[str, Any]:
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


def audit_shutdown_live_terminal_custody(
    sidecar: linux_sidecar.LinuxSidecar,
    cleanup: Mapping[str, Any],
) -> dict[str, Any]:
    candidate_started = (
        cleanup.get("candidate_started") is True
        or cleanup.get("pid") is not None
    )
    if not candidate_started:
        return {
            "candidate_started": False,
            "shutdown_summary_count": 0,
            "poisoned_boundaries": 0,
            "unresolved_boundaries": 0,
            "passed": True,
            "meaning": "no candidate process existed and no boundary could reside",
        }
    log_path = sidecar.run_root / "server.log"
    require(
        log_path.is_file() and not log_path.is_symlink(),
        "0091 shutdown log is absent or unsafe",
    )
    log_text = log_path.read_text(encoding="utf-8")
    matches = re.findall(
        r"neo3000 one-use live terminal shutdown custody "
        r"poisoned=(\d+) unresolved=(\d+)",
        log_text,
    )
    require(
        len(matches) == 1,
        "0091 shutdown did not emit exactly one live-boundary custody summary",
    )
    poisoned, unresolved = (int(item) for item in matches[0])
    require(
        unresolved == 0,
        "0091 shutdown left an unresolved live terminal boundary",
    )
    return {
        "candidate_started": True,
        "shutdown_summary_count": 1,
        "poisoned_boundaries": poisoned,
        "unresolved_boundaries": unresolved,
        "server_log_sha256": harness.live_runtime.sha256_file(log_path),
        "passed": True,
        "meaning": (
            "after request admission stopped and before backend destruction, "
            "the server explicitly poisoned every unresolved one-use boundary"
        ),
    }


def mutate_contract(
    contract: Mapping[str, Any],
    field: str,
) -> dict[str, Any]:
    require(field in TUPLE_MUTATION_FIELDS, "unknown tuple mutation")
    mutated = dict(contract)
    value = mutated[field]
    if type(value) is int:
        mutated[field] = value + 1
    else:
        mutated[field] = f"{value}-wrong"
    return mutated


def protocol_attempt(
    *,
    run_root: Path,
    progress: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    ordinal = len(progress.setdefault("protocol_attempts", []))
    marker = terminal.write_exclusive_json(
        run_root / f"protocol-attempt-{ordinal:03d}.json",
        {
            "id": EXPERIMENT_ID,
            "attempt_id": ATTEMPT_ID,
            "ordinal": ordinal,
            "label": label,
            "created_unix_ns": time.time_ns(),
            "meaning": "the fixed custody protocol action is next",
        },
    )
    progress["protocol_attempts"].append(marker)
    return marker


def exact_task_and_branch(
    *,
    sidecar: ContactJournalSidecar,
    codec: Any,
    props: Mapping[str, Any],
    prepared: Mapping[str, Any],
) -> tuple[dict[str, Any], list[int], Mapping[str, Any]]:
    task, branch_tokens, retained = predecessor.task_and_branch(
        sidecar,
        codec,
        props,
        prepared,
    )
    require(
        task["execution"]["generated_token_sha256"]
        == EXPECTED_TASK_A_GENERATED_SHA256
        and task["execution"]["finish_reason"] == "eos",
        "qualified Task-A generated identity changed",
    )
    require(
        canonical_sha256(retained["retained_root_tokens"])
        == EXPECTED_RETAINED_SHA256,
        "qualified retained carrier identity changed",
    )
    require(
        canonical_sha256(branch_tokens) == EXPECTED_BRANCH_SHA256
        and canonical_sha256(branch_tokens[:-1]) == EXPECTED_BASE_SHA256,
        "qualified branch/base identity changed",
    )
    return task, branch_tokens, retained


def derive_seed_payload(
    *,
    codec: Any,
    retained: Mapping[str, Any],
    prepared: Mapping[str, Any],
) -> tuple[list[int], dict[str, Any]]:
    tokens, payload = latency.branch_request(
        codec,
        retained,
        prepared["spec"],
        cache_prompt=True,
    )
    require(
        len(tokens) == EXPECTED_BRANCH_TOKENS
        and canonical_sha256(tokens) == EXPECTED_BRANCH_SHA256
        and canonical_sha256(payload) == EXPECTED_SEED_PAYLOAD_SHA256,
        "cache-enabled seed payload identity changed",
    )
    return tokens, payload


def derive_successor(
    *,
    codec: Any,
    child_tokens: Sequence[int],
    prior_state: Mapping[str, Any],
    edge: int,
    cache_prompt: bool,
) -> tuple[list[int], dict[str, Any], dict[str, Any]]:
    tokens, payload, ancestry = INHERITED_DERIVE_SUCCESSOR(
        codec=codec,
        child_tokens=child_tokens,
        prior_state=prior_state,
        edge=edge,
        cache_prompt=cache_prompt,
    )
    prior = predecessor.EDGE_PRIORS[edge - 1]
    require(
        canonical_sha256(payload)
        == EXPECTED_SUCCESSOR_PAYLOAD_SHA256[cache_prompt][prior],
        f"successor payload {edge} changed for cache={cache_prompt}",
    )
    return tokens, payload, ancestry


def setup_seed(
    *,
    sidecar: ContactJournalSidecar,
    codec: Any,
    props: Mapping[str, Any],
    prepared: Mapping[str, Any],
) -> dict[str, Any]:
    task, branch_tokens, retained = exact_task_and_branch(
        sidecar=sidecar,
        codec=codec,
        props=props,
        prepared=prepared,
    )
    base_tokens = list(branch_tokens[:-1])
    require(
        len(base_tokens) == EXPECTED_BASE_TOKENS
        and canonical_sha256(base_tokens) == EXPECTED_BASE_SHA256,
        "base token identity changed",
    )
    base_materialization = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:base-materialize",
        terminal.completion_payload(
            base_tokens,
            cache_prompt=False,
            n_predict=0,
        ),
        operation_kind="zero-output-root-readdress",
    )
    require(
        base_materialization["prompt_tokens"] == EXPECTED_BASE_TOKENS
        and base_materialization["cached_prompt_tokens"] == 0
        and base_materialization["fresh_prompt_tokens"] == EXPECTED_BASE_TOKENS
        and base_materialization["completion_tokens"] == 0,
        "base materialization geometry changed",
    )
    base_root = predecessor.root_action(
        action="root-save",
        root_id=BASE_ROOT_ID,
        n_tokens=EXPECTED_BASE_TOKENS,
        n_device_bytes=EXPECTED_BASE_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=1,
        expected_total_device_bytes_after=EXPECTED_BASE_DEVICE_BYTES,
    )
    base_restore = predecessor.root_action(
        action="root-restore",
        root_id=BASE_ROOT_ID,
        n_tokens=EXPECTED_BASE_TOKENS,
        n_device_bytes=EXPECTED_BASE_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=1,
        expected_total_device_bytes_after=EXPECTED_BASE_DEVICE_BYTES,
        expected=base_root,
    )
    seed_tokens, seed_payload = derive_seed_payload(
        codec=codec,
        retained=retained,
        prepared=prepared,
    )
    seed_record = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:seed-C",
        seed_payload,
        batch_owned_request=True,
    )
    require(
        seed_record["prompt_tokens"] == EXPECTED_BRANCH_TOKENS
        and seed_record["cached_prompt_tokens"] == EXPECTED_BASE_TOKENS
        and seed_record["fresh_prompt_tokens"] == 1,
        "seed C geometry changed",
    )
    seed_state = predecessor.validate_generated_state(
        seed_record,
        codec=codec,
        props=props,
        expected_answer="C",
    )
    child = predecessor.rebase.compact_child_tokens(
        branch_tokens,
        seed_state,
    )
    require(
        len(child) == EXPECTED_CHILD_TOKENS
        and canonical_sha256(child) == EXPECTED_CHILD_SHA256["C"],
        "seed C child identity changed",
    )
    return {
        "task": task,
        "retained": {
            "count": retained["retained_root_token_count"],
            "sha256": canonical_sha256(retained["retained_root_tokens"]),
        },
        "branch_tokens": branch_tokens,
        "base_materialization": harness.token_summary(base_materialization),
        "base_root": base_root,
        "base_restore": base_restore,
        "seed_tokens_sha256": canonical_sha256(seed_tokens),
        "seed_payload_sha256": canonical_sha256(seed_payload),
        "seed_record": seed_record,
        "seed_state": seed_state,
        "seed_child_sha256": canonical_sha256(child),
    }


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
        "whole-route monotonic wall including carrier preparation, protocol, "
        "resident custody, projection, and declared closure"
    )
    return result


def capture_for_negative(
    *,
    sidecar: ContactJournalSidecar,
    payload: Mapping[str, Any],
    contract: Mapping[str, Any],
    label: str,
) -> dict[str, Any]:
    wire = live.LiveCaptureWireRecorder()
    capture = harness.run_completion(
        sidecar,
        label,
        live.capture_payload(payload, contract),
        operation_kind="zero-output-root-readdress",
        recorder=wire,
        batch_owned_request=True,
    )
    require(
        capture["prompt_tokens"] == EXPECTED_SUCCESSOR_TOKENS
        and capture["cached_prompt_tokens"] == EXPECTED_CHILD_TOKENS
        and capture["fresh_prompt_tokens"] == EXPECTED_SUCCESSOR_FRESH_TOKENS
        and capture["completion_tokens"] == 0
        and capture["execution"]["generated_token_count"] == 0,
        "negative capture leaked or changed geometry",
    )
    capture["capture_receipt"] = live.validate_capture_receipt(capture, wire)
    return capture


def run_tuple_controls(
    *,
    sidecar: ContactJournalSidecar,
    codec: Any,
    props: Mapping[str, Any],
    base_root: Mapping[str, Any],
    branch_tokens: Sequence[int],
    seed_state: Mapping[str, Any],
    transaction_nonce: str,
    progress: dict[str, Any],
) -> dict[str, Any]:
    child, child_tokens, reset = live.materialize_child(
        sidecar=sidecar,
        base_root=base_root,
        branch_tokens=branch_tokens,
        state=seed_state,
        root_id=f"{EXPERIMENT_ID}-{transaction_nonce}-tuple-controls-child",
        label=f"{transaction_nonce}:tuple-controls:initial",
    )
    _, payload, ancestry = derive_successor(
        codec=codec,
        child_tokens=child_tokens,
        prior_state=seed_state,
        edge=1,
        cache_prompt=True,
    )
    controls: list[dict[str, Any]] = []
    endpoint = (
        f"http://127.0.0.1:{harness.live_runtime.PORT}/completion"
    )
    for field in TUPLE_MUTATION_FIELDS:
        restored = predecessor.root_action(
            action="root-restore",
            root_id=str(child["root_id"]),
            n_tokens=EXPECTED_CHILD_TOKENS,
            n_device_bytes=EXPECTED_CHILD_DEVICE_BYTES,
            terminal_logits=False,
            expected_roots_after=2,
            expected_total_device_bytes_after=EXPECTED_BASE_CHILD_DEVICE_BYTES,
            expected=child,
        )
        contract = live.public_contract(
            trial_label=f"{transaction_nonce}-negative-{field}",
            edge=1,
            input_boundary_id=str(ancestry["request_token_sha256"]),
            purpose="wrong-owner-negative",
        )
        capture = capture_for_negative(
            sidecar=sidecar,
            payload=payload,
            contract=contract,
            label=f"{EXPERIMENT_ID}:negative-{field}:capture",
        )
        protocol_attempt(
            run_root=sidecar.run_root,
            progress=progress,
            label=f"wrong-{field}-consumer",
        )
        denied = terminal.expect_http_error(
            endpoint,
            live.consumer_payload(
                payload,
                mutate_contract(contract, field),
            ),
            "Live terminal boundary identity or causal-order mismatch",
        )
        protocol_attempt(
            run_root=sidecar.run_root,
            progress=progress,
            label=f"poisoned-boundary-replay-{field}",
        )
        replay = terminal.expect_http_error(
            endpoint,
            live.consumer_payload(payload, contract),
            "Live terminal boundary identity or causal-order mismatch",
        )
        controls.append(
            {
                "field": field,
                "restore": restored,
                "capture": harness.token_summary(capture),
                "capture_receipt": capture["capture_receipt"],
                "contract_sha256": canonical_sha256(contract),
                "mutated_contract_sha256": canonical_sha256(
                    mutate_contract(contract, field)
                ),
                "denial": denied,
                "exact_replay_after_poison": replay,
                "closed_by_custody_violation": (
                    denied["http_status"] == 400
                    and replay["http_status"] == 400
                ),
            }
        )

    intervening_restore = predecessor.root_action(
        action="root-restore",
        root_id=str(child["root_id"]),
        n_tokens=EXPECTED_CHILD_TOKENS,
        n_device_bytes=EXPECTED_CHILD_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=2,
        expected_total_device_bytes_after=EXPECTED_BASE_CHILD_DEVICE_BYTES,
        expected=child,
    )
    intervening_contract = live.public_contract(
        trial_label=f"{transaction_nonce}-negative-intervening-root",
        edge=1,
        input_boundary_id=str(ancestry["request_token_sha256"]),
        purpose="wrong-owner-negative",
    )
    intervening_capture = capture_for_negative(
        sidecar=sidecar,
        payload=payload,
        contract=intervening_contract,
        label=f"{EXPERIMENT_ID}:negative-intervening-root:capture",
    )
    protocol_attempt(
        run_root=sidecar.run_root,
        progress=progress,
        label="intervening-root-restore",
    )
    intervening = terminal.expect_http_error(
        (
            f"http://127.0.0.1:{harness.live_runtime.PORT}"
            "/slots/0?action=root-restore"
        ),
        {"root_id": str(child["root_id"])},
        "root-restore rejected while a one-use live terminal boundary is resident",
    )
    protocol_attempt(
        run_root=sidecar.run_root,
        progress=progress,
        label="intervening-poison-replay",
    )
    intervening_replay = terminal.expect_http_error(
        endpoint,
        live.consumer_payload(payload, intervening_contract),
        "Live terminal boundary identity or causal-order mismatch",
    )

    premature_restore = predecessor.root_action(
        action="root-restore",
        root_id=str(child["root_id"]),
        n_tokens=EXPECTED_CHILD_TOKENS,
        n_device_bytes=EXPECTED_CHILD_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=2,
        expected_total_device_bytes_after=EXPECTED_BASE_CHILD_DEVICE_BYTES,
        expected=child,
    )
    premature_contract = live.public_contract(
        trial_label=f"{transaction_nonce}-negative-premature-projection",
        edge=1,
        input_boundary_id=str(ancestry["request_token_sha256"]),
        purpose="wrong-owner-negative",
    )
    premature_payload = live.capture_payload(payload, premature_contract)
    premature_payload["n_predict"] = 1
    protocol_attempt(
        run_root=sidecar.run_root,
        progress=progress,
        label="premature-projection-capture",
    )
    premature = terminal.expect_http_error(
        endpoint,
        premature_payload,
        "Terminal-logits capture requires one zero-output",
    )
    final_restore = predecessor.root_action(
        action="root-restore",
        root_id=str(child["root_id"]),
        n_tokens=EXPECTED_CHILD_TOKENS,
        n_device_bytes=EXPECTED_CHILD_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=2,
        expected_total_device_bytes_after=EXPECTED_BASE_CHILD_DEVICE_BYTES,
        expected=child,
    )
    child_erase = live.erase_child(child)
    return {
        "initial_reset": reset,
        "child_sha256": canonical_sha256(child_tokens),
        "tuple_controls": controls,
        "intervening_action": {
            "restore": intervening_restore,
            "capture": harness.token_summary(intervening_capture),
            "capture_receipt": intervening_capture["capture_receipt"],
            "denial": intervening,
            "exact_replay_after_poison": intervening_replay,
        },
        "premature_projection": {
            "restore": premature_restore,
            "denial": premature,
        },
        "final_restore": final_restore,
        "child_erase": child_erase,
        "idle_capture_disconnect_control": "NOT_AVAILABLE_STATELESS_HTTP_LEASE",
        "authorized_stop_control": "NOT_IMPLEMENTED_BY_CURRENT_SERVER_PROTOCOL",
    }


def generated_state(
    route: Mapping[str, Any],
    edge: Mapping[str, Any],
) -> Mapping[str, Any]:
    if route["route"] == "live-terminal":
        return edge["consumer"]["state"]
    return edge["successor"]["state"]


def request_identity(
    route: Mapping[str, Any],
    edge: Mapping[str, Any],
) -> str:
    if route["route"] == "live-terminal":
        return str(edge["live"]["contract"]["input_boundary_id"])
    return str(edge["successor"]["ancestry"]["request_token_sha256"])


def evaluate(
    *,
    sidecar: ContactJournalSidecar,
    codec: Any,
    props: Mapping[str, Any],
    prepared: Mapping[str, Any],
    transaction_nonce: str,
    progress: dict[str, Any],
) -> dict[str, Any]:
    setup = setup_seed(
        sidecar=sidecar,
        codec=codec,
        props=props,
        prepared=prepared,
    )
    tuple_controls = run_tuple_controls(
        sidecar=sidecar,
        codec=codec,
        props=props,
        base_root=setup["base_root"],
        branch_tokens=setup["branch_tokens"],
        seed_state=setup["seed_state"],
        transaction_nonce=transaction_nonce,
        progress=progress,
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
            trial_label=f"{transaction_nonce}-warmup-{route}",
            run_successor_negative=False,
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
                trial_label=(
                    f"{transaction_nonce}-trial-{trial}-{route}"
                ),
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
        n_tokens=EXPECTED_BASE_TOKENS,
        n_device_bytes=EXPECTED_BASE_DEVICE_BYTES,
        terminal_logits=False,
        expected_roots_after=0,
        expected_total_device_bytes_after=0,
        expected=setup["base_root"],
    )
    resources_after = harness.process_resources(sidecar, None)

    ownership_total = sum(float(item["wall_seconds"]) for item in ownership)
    ownership_share = ownership_total / (COUNTED_TRIALS * len(ROUTES))
    for trial in counted:
        for route in ROUTES:
            trial["routes"][route]["fully_charged_wall_seconds"] += (
                ownership_share
            )

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
    expected_valid_samples = (WARMUP_TRIALS + COUNTED_TRIALS) * 2
    expected_control_captures = len(TUPLE_MUTATION_FIELDS) + 1
    expected_live_captures = expected_valid_samples + expected_control_captures

    gates = {
        "task_a_exact_linux_identity": (
            setup["task"]["execution"]["generated_token_sha256"]
            == EXPECTED_TASK_A_GENERATED_SHA256
            and setup["retained"]["sha256"] == EXPECTED_RETAINED_SHA256
        ),
        "all_state_sequences_C_D_B": all(
            route["observed_states"] == list(predecessor.EXPECTED_STATES)
            for route in all_routes
        ),
        "all_request_output_and_child_identities_exact": all(
            request_identity(route, edge)
            == EXPECTED_REQUEST_SHA256[
                predecessor.EDGE_PRIORS[edge["edge"] - 1]
            ]
            and generated_state(route, edge)["generated_token_sha256"]
            == EXPECTED_GENERATED_SHA256[
                predecessor.EDGE_SUCCESSORS[edge["edge"] - 1]
            ]
            and edge["child_token_sha256"]
            == EXPECTED_CHILD_SHA256[
                predecessor.EDGE_PRIORS[edge["edge"] - 1]
            ]
            and edge["next_child_token_sha256"]
            == EXPECTED_CHILD_SHA256[
                predecessor.EDGE_SUCCESSORS[edge["edge"] - 1]
            ]
            for route, edge in all_edges
        ),
        "live_consumers_777_cached_0_fresh": all(
            edge["consumer"]["cached_prompt_tokens"]
            == EXPECTED_SUCCESSOR_TOKENS
            and edge["consumer"]["fresh_prompt_tokens"] == 0
            for route in all_live
            for edge in route["edges"]
        ),
        "matched_root_only_690_cached_87_fresh": all(
            edge["successor"]["cached_prompt_tokens"]
            == EXPECTED_CHILD_TOKENS
            and edge["successor"]["fresh_prompt_tokens"]
            == EXPECTED_SUCCESSOR_FRESH_TOKENS
            for route in [
                warmup["root-only"],
                *[trial["routes"]["root-only"] for trial in counted],
            ]
            for edge in route["edges"]
        ),
        "matched_materialized_0_cached_777_fresh": all(
            edge["successor"]["cached_prompt_tokens"] == 0
            and edge["successor"]["fresh_prompt_tokens"]
            == EXPECTED_SUCCESSOR_TOKENS
            for route in [
                warmup["materialized"],
                *[trial["routes"]["materialized"] for trial in counted],
            ]
            for edge in route["edges"]
        ),
        "full_tuple_controls_reject_and_poison": (
            {
                item["field"]
                for item in tuple_controls["tuple_controls"]
                if item["denial"]["http_status"] == 400
                and item["closed_by_custody_violation"] is True
                and item["exact_replay_after_poison"]["http_status"] == 400
            }
            == set(TUPLE_MUTATION_FIELDS)
        ),
        "intervening_action_rejected_and_poisoned": (
            tuple_controls["intervening_action"]["denial"]["http_status"]
            == 400
            and tuple_controls["intervening_action"][
                "exact_replay_after_poison"
            ]["http_status"]
            == 400
        ),
        "premature_projection_rejected": (
            tuple_controls["premature_projection"]["denial"]["http_status"]
            == 400
        ),
        "contracts_unique_and_owner_bound": (
            len({str(contract["boundary_id"]) for contract in contracts})
            == len(contracts)
            and all(
                contract["port_owner"] == PORT_OWNER
                and contract["port_type"] == PORT_TYPE
                and contract["module_id"] == MODULE_ID
                and contract["module_variant"] == 0
                and contract["generation"] == contract["module_ordinal"]
                and contract["projection_policy"] == PROJECTION_POLICY
                and contract["restoration_policy"] == RESTORATION_CLASS
                for contract in contracts
            )
        ),
        "resident_capture_releases_zero_generated_tokens": all(
            edge["capture"]["completion_tokens"] == 0
            for route in all_live
            for edge in route["edges"]
        ),
        "one_consumer_per_boundary": all(
            edge["consumer_count"] == 1
            for route in all_live
            for edge in route["edges"]
        ),
        "declared_closure_not_restoration": all(
            route["restoration_class"] == RESTORATION_CLASS
            for route in all_live
        ),
        "live_marker_counts_exact": (
            live_capture_count == expected_live_captures
            and live_sample_count == expected_valid_samples
        ),
        "maximum_two_roots_in_live_route": all(
            edge["child_root"]["n_roots_after"] == 2
            for route in all_live
            for edge in route["edges"]
        ),
        "fresh_compute_law_preserved": all(
            trial["routes"]["live-terminal"][
                "fully_charged_fresh_prompt_tokens"
            ]
            == EXPECTED_FRESH_PER_CATALYTIC_EDGE * 2
            and trial["routes"]["root-only"][
                "fully_charged_fresh_prompt_tokens"
            ]
            == EXPECTED_FRESH_PER_CATALYTIC_EDGE * 2
            and trial["routes"]["materialized"][
                "fully_charged_fresh_prompt_tokens"
            ]
            == EXPECTED_SUCCESSOR_TOKENS * 2
            for trial in counted
        ),
        "counted_avoided_tokens_4104": (
            EXPECTED_COUNTED_AVOIDED_TOKENS == 4_104
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
            ttft_speedup >= MIN_CONSUMER_TTFT_SPEEDUP
        ),
        "consumer_ttft_live_wins_all_edges": all(
            live_value < root_value
            for live_value, root_value in zip(live_ttft, root_ttft)
        ),
        "live_vs_materialized_speedup_at_least_2_5": (
            live_vs_direct >= MIN_LIVE_VS_MATERIALIZED_WALL_SPEEDUP
        ),
        "live_vs_root_only_ratio_at_least_0_80": (
            live_vs_root >= MIN_LIVE_VS_ROOT_ONLY_WALL_RATIO
        ),
        "root_bank_closed": (
            base_erase["n_total_bytes_after"] == 0
            and base_erase["n_total_device_bytes_after"] == 0
            and base_erase["n_total_gpu_bytes_after"] == 0
        ),
        "linux_gpu_residency_bounded": (
            isinstance(resources_after.get("peak_gpu_dedicated_bytes"), int)
            and 0 < int(resources_after["peak_gpu_dedicated_bytes"])
            <= MAX_GPU_BYTES
            and (
                resources_after.get("host_rss_growth_bytes") is None
                or int(resources_after["host_rss_growth_bytes"])
                <= MAX_HOST_GROWTH_BYTES
            )
        ),
        "batch_ownership_exact": (
            len(ownership) == 2
            and all(item["evidence"]["passed"] is True for item in ownership)
        ),
        "unrelated_useful_inference_after_declared_closure": (
            tool_canary["validation"]["passed"] is True
        ),
        "restored_carrier_reuse_not_claimed": True,
        "exact_bounded_model_callback_count": (
            len(progress["transport_attempts"]) == EXPECTED_MODEL_CALLBACKS
        ),
        "exact_bounded_direct_protocol_action_count": (
            len(progress["protocol_attempts"])
            == EXPECTED_DIRECT_PROTOCOL_ACTIONS
        ),
    }
    accepted = all(gates.values())
    return {
        "id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "complete",
        "verdict": "accept" if accepted else "reject",
        "classification": (
            "BOUNDED_LINUX_607_OWNER_BOUND_LIVE_TERMINAL_DECLARED_CLOSURE"
            if accepted
            else "LINUX_607_LIVE_TERMINAL_WITHOUT_ALL_PREREGISTERED_GATES"
        ),
        "hypothesis": (
            "The qualified Linux 607-bound C-to-D-to-B geometry can borrow "
            "the resident CUDA child plus exact terminal logits, sample each "
            "successor without root serialization or fresh prompt work at "
            "the consumer, close before projection, and preserve useful "
            "same-process inference after closure."
        ),
        "restoration_class": RESTORATION_CLASS,
        "setup": setup,
        "tuple_controls": tuple_controls,
        "warmup": warmup,
        "counted_trials": counted,
        "metrics": {
            "live_fully_charged_wall_seconds": predecessor.distribution(
                live_walls
            ),
            "root_only_fully_charged_wall_seconds": predecessor.distribution(
                root_walls
            ),
            "materialized_fully_charged_wall_seconds": predecessor.distribution(
                direct_walls
            ),
            "aggregate_live_seconds": sum(live_walls),
            "aggregate_root_only_seconds": sum(root_walls),
            "aggregate_materialized_seconds": sum(direct_walls),
            "consumer_ttft_speedup": ttft_speedup,
            "live_vs_root_only_ratio": live_vs_root,
            "live_vs_materialized_speedup": live_vs_direct,
            "counted_avoided_fresh_prompt_tokens": (
                EXPECTED_COUNTED_AVOIDED_TOKENS
            ),
        },
        "runtime_markers": {
            "live_capture_count": live_capture_count,
            "expected_live_capture_count": expected_live_captures,
            "live_sample_count": live_sample_count,
            "expected_live_sample_count": expected_valid_samples,
        },
        "resources_after_closure": resources_after,
        "root_closure": base_erase,
        "tool_canary": tool_canary,
        "batch_ownership": ownership,
        "quality_gates": gates,
        "claim_ceiling": (
            "One bounded native-Linux Agents-A1 R2 one-use live-terminal "
            "pipeline with full-tuple equality custody, exact C-to-D-to-B "
            "utility, consumer zero-fresh-prompt sampling, DECLARED_CLOSURE, "
            "and unrelated useful same-process inference after closure. "
            "No inverse restoration, restored-carrier reuse, idle-owner "
            "disconnect cleanup, authorized STOP, phase advantage, or "
            "unbounded catalytic inference claim."
        ),
        "automatic_promotion": False,
        "research_goal_blocked": False,
        "next_boundary": (
            "ATTACH_A_FIXED_PUBLIC_NONCOMMUTING_RELATIONAL_FIBER_TO_THE_"
            "QUALIFIED_LIVE_TERMINAL_HYPOTHESIS_BOUNDARY"
            if accepted
            else "PRESERVE_0091_AND_LOCALIZE_THE_FAILED_CUSTODY_OR_WALL_GATE"
        ),
    }


def current_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
    ).strip()


def manifest_artifacts() -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for name, path in RUNTIME_ARTIFACT_PATHS.items():
        resolved = path.resolve(strict=True)
        require(
            resolved.is_relative_to(ROOT),
            f"runtime artifact escapes repository: {name}",
        )
        artifacts[name] = {
            "relative_path": resolved.relative_to(ROOT).as_posix(),
            **runtime.file_identity(resolved),
        }
    return artifacts


def validate_runtime_source_commit(
    source_commit: str,
    *,
    require_current: bool,
) -> None:
    require(
        re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None,
        "runtime source commit must be a lowercase full-length Git object ID",
    )
    exists = subprocess.run(
        ["git", "cat-file", "-e", f"{source_commit}^{{commit}}"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    require(exists.returncode == 0, "runtime source commit does not exist")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_commit, "HEAD"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    require(
        ancestor.returncode == 0,
        "runtime source commit is not an ancestor of current HEAD",
    )
    if require_current:
        require(
            current_head() == source_commit,
            "runtime manifest must be generated from its exact source commit",
        )


def cuda_object_identities(build_root: Path) -> list[dict[str, Any]]:
    object_root = (
        build_root / "ggml" / "src" / "ggml-cuda" / "CMakeFiles"
        / "ggml-cuda.dir"
    )
    objects = sorted(
        object_root.glob("**/*.cu.o"),
        key=lambda path: path.relative_to(build_root).as_posix(),
    )
    compile_database = json.loads(
        (build_root / "compile_commands.json").read_text(encoding="utf-8")
    )
    require(
        isinstance(compile_database, list),
        "0091 compile database is not an array",
    )
    compile_entries = {
        Path(str(entry.get("output") or "")).as_posix(): entry
        for entry in compile_database
        if isinstance(entry, Mapping)
        and str(entry.get("file") or "").endswith(".cu")
    }
    require(
        len(compile_entries) == 139,
        "0091 compile database does not bind 139 CUDA outputs",
    )
    records = [
        {
            "relative_path": path.resolve(strict=True)
            .relative_to(build_root.resolve(strict=True))
            .as_posix(),
            **runtime.file_identity(path.resolve(strict=True)),
            **cuda_source_and_command_identity(
                build_root,
                path,
                compile_entries,
            ),
        }
        for path in objects
    ]
    validate_cuda_object_records(records, records)
    return records


def cuda_source_and_command_identity(
    build_root: Path,
    object_path: Path,
    compile_entries: Mapping[str, Any],
) -> dict[str, Any]:
    relative_object = (
        object_path.resolve(strict=True)
        .relative_to(build_root.resolve(strict=True))
        .as_posix()
    )
    entry = compile_entries.get(relative_object)
    require(
        isinstance(entry, Mapping),
        f"0091 CUDA object lacks a compile command: {relative_object}",
    )
    source = Path(str(entry.get("file") or "")).resolve(strict=True)
    require(
        source.is_relative_to(ROOT)
        and source.suffix == ".cu",
        f"0091 CUDA source escapes the repository: {relative_object}",
    )
    source_relative = source.relative_to(ROOT).as_posix()
    object_suffix = object_path.resolve(strict=True).relative_to(
        (
            build_root / "ggml" / "src" / "ggml-cuda" / "CMakeFiles"
            / "ggml-cuda.dir"
        ).resolve(strict=True)
    ).as_posix()
    require(
        source_relative == f"ggml/src/ggml-cuda/{object_suffix[:-2]}",
        f"0091 CUDA source/object mapping changed: {relative_object}",
    )
    command = str(entry.get("command") or "")
    require(
        command
        and str(entry.get("output") or "") == relative_object
        and str(source) in command
        and relative_object.split("ggml/src/ggml-cuda/", 1)[1] in command,
        f"0091 CUDA compile command is malformed: {relative_object}",
    )
    git_blob_oid = subprocess.check_output(
        [
            "git",
            "hash-object",
            f"--path={source_relative}",
            source_relative,
        ],
        cwd=ROOT,
        text=True,
    ).strip()
    require(
        re.fullmatch(r"[0-9a-f]{40}", git_blob_oid) is not None,
        f"0091 CUDA source Git blob is invalid: {source_relative}",
    )
    git_blob = subprocess.check_output(
        ["git", "cat-file", "blob", git_blob_oid],
        cwd=ROOT,
    )
    return {
        "source_relative_path": source_relative,
        "source_bytes": runtime.file_identity(source)["bytes"],
        "source_sha256": runtime.file_identity(source)["sha256"],
        "source_git_blob_oid": git_blob_oid,
        "source_git_bytes": len(git_blob),
        "source_git_sha256": hashlib.sha256(git_blob).hexdigest().upper(),
        "compile_command_sha256": hashlib.sha256(
            command.encode("utf-8")
        ).hexdigest().upper(),
    }


def validate_cuda_object_records(
    expected: Any,
    observed: Any,
) -> None:
    require(
        isinstance(expected, list)
        and isinstance(observed, list)
        and len(expected) == 139
        and len(observed) == 139,
        "0091 CUDA object closure must contain exactly 139 identities",
    )
    for label, records in (("expected", expected), ("observed", observed)):
        require(
            all(
                isinstance(item, Mapping)
                and re.fullmatch(
                    r"ggml/src/ggml-cuda/CMakeFiles/"
                    r"ggml-cuda\.dir/.+\.cu\.o",
                    str(item.get("relative_path") or ""),
                )
                is not None
                and type(item.get("bytes")) is int
                and int(item["bytes"]) > 0
                and re.fullmatch(
                    r"[0-9A-F]{64}",
                    str(item.get("sha256") or ""),
                )
                is not None
                and re.fullmatch(
                    r"ggml/src/ggml-cuda/.+\.cu",
                    str(item.get("source_relative_path") or ""),
                )
                is not None
                and type(item.get("source_bytes")) is int
                and int(item["source_bytes"]) > 0
                and re.fullmatch(
                    r"[0-9A-F]{64}",
                    str(item.get("source_sha256") or ""),
                )
                is not None
                and re.fullmatch(
                    r"[0-9a-f]{40}",
                    str(item.get("source_git_blob_oid") or ""),
                )
                is not None
                and type(item.get("source_git_bytes")) is int
                and int(item["source_git_bytes"]) > 0
                and re.fullmatch(
                    r"[0-9A-F]{64}",
                    str(item.get("source_git_sha256") or ""),
                )
                is not None
                and re.fullmatch(
                    r"[0-9A-F]{64}",
                    str(item.get("compile_command_sha256") or ""),
                )
                is not None
                for item in records
            ),
            f"0091 {label} CUDA object identity is malformed",
        )
        paths = [str(item["relative_path"]) for item in records]
        require(
            paths == sorted(paths) and len(set(paths)) == 139,
            f"0091 {label} CUDA object paths are not exact and unique",
        )
    runtime.require_exact_identity(
        {"cuda_objects": expected},
        {"cuda_objects": observed},
        "0091 CUDA object identity closure",
    )


def validate_cuda_link_commands(
    build_root: Path,
    cuda_objects: Sequence[Mapping[str, Any]],
) -> None:
    cuda_link = (
        build_root / "ggml" / "src" / "ggml-cuda" / "CMakeFiles"
        / "ggml-cuda.dir" / "link.txt"
    ).read_text(encoding="utf-8")
    object_prefix = "ggml/src/ggml-cuda/"
    linked = []
    for item in cuda_objects:
        relative = str(item["relative_path"])
        require(
            relative.startswith(object_prefix),
            "0091 CUDA object path escaped its linker directory",
        )
        linker_relative = relative[len(object_prefix) :]
        if (
            f'"{linker_relative}"' in cuda_link
            or f" {linker_relative} " in cuda_link
        ):
            linked.append(linker_relative)
    require(
        len(linked) == 139 and len(set(linked)) == 139,
        "0091 CUDA linker command does not consume all 139 CUDA objects",
    )
    server_link = (
        build_root / "tools" / "server" / "CMakeFiles"
        / "llama-server.dir" / "link.txt"
    ).read_text(encoding="utf-8")
    require(
        "libggml-cuda.so" in server_link,
        "0091 server linker command does not consume the CUDA library",
    )


def validate_cuda_build_log(
    build_log: Path,
    cuda_objects: Sequence[Mapping[str, Any]],
) -> None:
    text = build_log.read_text(encoding="utf-8")
    observed = [
        str(item["relative_path"])
        for item in cuda_objects
        if f"Building CUDA object {item['relative_path']}" in text
    ]
    require(
        len(observed) == 139 and len(set(observed)) == 139,
        "0091 build log does not prove all 139 CUDA compile actions",
    )


def scan_live_log_surface(binary: Path) -> dict[str, bool]:
    surfaces = (
        binary,
        binary.parent / "libllama-server-impl.so",
    )
    binary_strings = "\n".join(
        subprocess.check_output(
            ["strings", str(surface.resolve(strict=True))],
            text=True,
            errors="replace",
        )
        for surface in surfaces
    )
    return {
        "capture_logit_fingerprint_absent": (
            (
                "neo3000 one-use live terminal boundary captured "
                "boundary=%s carrier=%s lease=%"
            )
            in binary_strings
            and "contract=%s logits=%s prompt=%s sampler=%s"
            not in binary_strings
        ),
        "sample_logit_fingerprint_absent": (
            "sampled and declared-closed boundary=%s logits=%s"
            not in binary_strings
        ),
        "raw_logits_absent": (
            "neo3000 one-use live terminal raw logits" not in binary_strings
        ),
        "shutdown_poison_marker_present": (
            "neo3000 one-use live terminal shutdown custody "
            "poisoned=%zu unresolved=%zu"
            in binary_strings
        ),
    }


def require_exact_live_log_surface(value: Any) -> None:
    require(
        type(value) is dict and value == EXPECTED_LIVE_LOG_SURFACE,
        "0091 live log-surface proof changed",
    )


def validate_source_artifacts_at_commit(
    source_commit: str,
    artifacts: Mapping[str, Any],
) -> None:
    for name in sorted(SOURCE_ARTIFACT_NAMES):
        expected = artifacts.get(name)
        require(
            isinstance(expected, Mapping),
            f"0091 committed source artifact is absent: {name}",
        )
        relative_path = str(expected.get("relative_path") or "")
        committed = subprocess.check_output(
            ["git", "show", f"{source_commit}:{relative_path}"],
            cwd=ROOT,
        )
        require(
            len(committed) == expected.get("bytes")
            and hashlib.sha256(committed).hexdigest().upper()
            == expected.get("sha256"),
            f"0091 source artifact does not match source commit: {name}",
        )


def validate_cuda_sources_at_commit(
    source_commit: str,
    cuda_objects: Sequence[Mapping[str, Any]],
) -> None:
    require(
        len(cuda_objects) == 139,
        "0091 committed CUDA source closure changed",
    )
    for item in cuda_objects:
        relative_path = str(item.get("source_relative_path") or "")
        committed_oid = subprocess.check_output(
            ["git", "rev-parse", f"{source_commit}:{relative_path}"],
            cwd=ROOT,
            text=True,
        ).strip()
        committed = subprocess.check_output(
            ["git", "show", f"{source_commit}:{relative_path}"],
            cwd=ROOT,
        )
        require(
            committed_oid == item.get("source_git_blob_oid")
            and len(committed) == item.get("source_git_bytes")
            and hashlib.sha256(committed).hexdigest().upper()
            == item.get("source_git_sha256"),
            "0091 CUDA object source does not match source commit: "
            + relative_path,
        )


def runtime_manifest_template(runtime_source_commit: str) -> dict[str, Any]:
    validate_runtime_source_commit(
        runtime_source_commit,
        require_current=True,
    )
    binary = DEFAULT_BINARY.resolve(strict=True)
    compiler = DEFAULT_COMPILER_CONTRACT.resolve(strict=True)
    build_root = binary.parent.parent
    cuda_objects = cuda_object_identities(build_root)
    validate_cuda_link_commands(build_root, cuda_objects)
    validate_cuda_build_log(
        RUNTIME_ARTIFACT_PATHS["build_log"].resolve(strict=True),
        cuda_objects,
    )
    validate_cuda_sources_at_commit(runtime_source_commit, cuda_objects)
    live_log_surface = scan_live_log_surface(binary)
    require_exact_live_log_surface(live_log_surface)
    artifacts = manifest_artifacts()
    validate_source_artifacts_at_commit(runtime_source_commit, artifacts)
    return {
        "schema": "neo3000-linux-live-terminal-runtime-manifest-v1",
        "experiment_id": EXPERIMENT_ID,
        "execution_attempt_id": ATTEMPT_ID,
        "runtime_source_commit": runtime_source_commit,
        "causal_intervention": (
            "Remove the unresolved terminal-logit fingerprint from live "
            "capture and live declared-closure logs; retain public contract, "
            "prompt, sampler, geometry, and resource receipts."
        ),
        "build_descriptor": runtime.observed_build_descriptor(
            build_root=build_root,
            compiler_contract=compiler,
        ),
        "compiler_semantics_gates": runtime.compiler_semantics_probe(
            compiler,
            (
                DEFAULT_COMPILER_CONTRACT.parent
                / "cuda-smoke.cu"
            ).resolve(strict=True),
        ),
        "artifacts": artifacts,
        "linked_libraries": runtime.linked_library_identities(binary),
        "cuda_driver_libraries": runtime.cuda_driver_library_identities(),
        "gpu_identity": runtime.gpu_identity(),
        "binary_version_identity": runtime.binary_version_identity(binary),
        "cuda_translation_units": len(cuda_objects),
        "cuda_objects": cuda_objects,
        "live_log_surface": live_log_surface,
        "restoration_class": RESTORATION_CLASS,
        "scientific_contact": False,
    }


def validate_runtime_manifest() -> dict[str, Any]:
    manifest_file = DEFAULT_RUNTIME_MANIFEST.resolve(strict=True)
    relative = manifest_file.relative_to(ROOT).as_posix()
    tracked = subprocess.check_output(
        ["git", "ls-files", "--error-unmatch", relative],
        cwd=ROOT,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()
    require(tracked == relative, "0091 runtime manifest is not tracked")
    committed = subprocess.check_output(
        ["git", "show", f"HEAD:{relative}"],
        cwd=ROOT,
    )
    worktree = manifest_file.read_bytes()
    require(
        committed == worktree,
        "0091 runtime manifest differs from current commit",
    )
    manifest = json.loads(worktree)
    require(
        manifest.get("schema")
        == "neo3000-linux-live-terminal-runtime-manifest-v1"
        and manifest.get("experiment_id") == EXPERIMENT_ID
        and manifest.get("execution_attempt_id") == ATTEMPT_ID
        and manifest.get("restoration_class") == RESTORATION_CLASS
        and manifest.get("scientific_contact") is False,
        "0091 runtime manifest identity changed",
    )
    source_commit = str(manifest.get("runtime_source_commit") or "")
    validate_runtime_source_commit(source_commit, require_current=False)
    artifacts = manifest.get("artifacts")
    require(
        isinstance(artifacts, Mapping)
        and set(artifacts) == set(RUNTIME_ARTIFACT_PATHS),
        "0091 runtime artifact closure changed",
    )
    for name, expected in artifacts.items():
        require(
            isinstance(expected, Mapping),
            f"0091 runtime artifact is invalid: {name}",
        )
        relative_path = expected.get("relative_path")
        require(
            isinstance(relative_path, str) and relative_path,
            f"0091 runtime artifact path is invalid: {name}",
        )
        path = (ROOT / relative_path).resolve(strict=True)
        require(
            path == RUNTIME_ARTIFACT_PATHS[name].resolve(strict=True),
            f"0091 runtime artifact path changed: {name}",
        )
        runtime.require_exact_identity(
            {
                "bytes": expected.get("bytes"),
                "sha256": expected.get("sha256"),
            },
            runtime.file_identity(path),
            f"0091 runtime artifact {name}",
        )
    validate_source_artifacts_at_commit(source_commit, artifacts)
    binary = DEFAULT_BINARY.resolve(strict=True)
    compiler = DEFAULT_COMPILER_CONTRACT.resolve(strict=True)
    build_descriptor = runtime.observed_build_descriptor(
        build_root=binary.parent.parent,
        compiler_contract=compiler,
    )
    runtime.require_exact_identity(
        {"build_descriptor": manifest.get("build_descriptor")},
        {"build_descriptor": build_descriptor},
        "0091 runtime build descriptor",
    )
    compiler_semantics = runtime.compiler_semantics_probe(
        compiler,
        (
            DEFAULT_COMPILER_CONTRACT.parent / "cuda-smoke.cu"
        ).resolve(strict=True),
    )
    runtime.require_exact_identity(
        {"compiler_semantics_gates": manifest.get("compiler_semantics_gates")},
        {"compiler_semantics_gates": compiler_semantics},
        "0091 compiler semantics",
    )
    runtime.require_exact_identity(
        {"linked_libraries": manifest.get("linked_libraries")},
        {"linked_libraries": runtime.linked_library_identities(binary)},
        "0091 linked-library closure",
    )
    runtime.require_exact_identity(
        {
            "cuda_driver_libraries": manifest.get(
                "cuda_driver_libraries"
            )
        },
        {
            "cuda_driver_libraries": (
                runtime.cuda_driver_library_identities()
            )
        },
        "0091 CUDA driver-library closure",
    )
    runtime.require_exact_identity(
        {"gpu_identity": manifest.get("gpu_identity")},
        {"gpu_identity": runtime.gpu_identity()},
        "0091 GPU identity",
    )
    runtime.require_exact_identity(
        {"binary_version_identity": manifest.get("binary_version_identity")},
        {"binary_version_identity": runtime.binary_version_identity(binary)},
        "0091 binary version identity",
    )
    observed_cuda_objects = cuda_object_identities(binary.parent.parent)
    validate_cuda_object_records(
        manifest.get("cuda_objects"),
        observed_cuda_objects,
    )
    validate_cuda_link_commands(binary.parent.parent, observed_cuda_objects)
    validate_cuda_build_log(
        RUNTIME_ARTIFACT_PATHS["build_log"].resolve(strict=True),
        observed_cuda_objects,
    )
    validate_cuda_sources_at_commit(source_commit, observed_cuda_objects)
    require(
        manifest.get("cuda_translation_units") == 139,
        "0091 CUDA translation-unit count changed",
    )
    live_log_surface = manifest.get("live_log_surface")
    require_exact_live_log_surface(live_log_surface)
    observed_log_surface = scan_live_log_surface(binary)
    require_exact_live_log_surface(observed_log_surface)
    runtime.require_exact_identity(
        {"live_log_surface": live_log_surface},
        {"live_log_surface": observed_log_surface},
        "0091 independently scanned live log surface",
    )
    return {
        "path": str(manifest_file),
        "sha256": runtime.file_identity(manifest_file)["sha256"],
        "runtime_source_commit": source_commit,
        "binary": runtime.file_identity(binary),
        "binary_path": str(binary),
        "build_descriptor": build_descriptor,
        "compiler_semantics_gates": compiler_semantics,
        "cuda_translation_units": 139,
        "artifact_count": len(artifacts),
        "linked_library_count": len(manifest["linked_libraries"]),
        "gpu_identity": manifest["gpu_identity"],
        "live_log_surface": dict(live_log_surface),
        "validated": True,
    }


def static_audit() -> dict[str, Any]:
    configure_linux_geometry()
    source = Path(__file__).read_text(encoding="utf-8")
    runtime_source = source[: source.index("def static_audit()")]
    main_source = source[source.rindex("def main() -> int:") :]
    context = (ROOT / "tools" / "server" / "server-context.cpp").read_text(
        encoding="utf-8"
    )
    server_entrypoint = (
        ROOT / "tools" / "server" / "server.cpp"
    ).read_text(encoding="utf-8")
    shutdown_cleanup_start = server_entrypoint.index(
        "clean_up = [&ctx_http, &ctx_server]()"
    )
    shutdown_cleanup = server_entrypoint[
        shutdown_cleanup_start :
        server_entrypoint.index("};", shutdown_cleanup_start)
    ]
    preflight_start = context.index(
        "server_slot * preflight_live_terminal_before_slot_selection"
    )
    preflight_end = context.index(
        "std::vector<common_adapter_lora_info> construct_lora_list",
        preflight_start,
    )
    preflight_source = context[preflight_start:preflight_end]
    live_capture_log_start = context.index(
        '"neo3000 one-use live terminal boundary captured'
    )
    live_capture_log_end = context.index(
        ");",
        live_capture_log_start,
    )
    live_sample_log_start = context.index(
        '"neo3000 one-use live terminal boundary sampled and declared-closed'
    )
    live_sample_log_end = context.index(
        ");",
        live_sample_log_start,
    )
    gates = {
        "linux_geometry_exact": (
            EXPECTED_RETAINED_TOKENS == 607
            and EXPECTED_BASE_TOKENS == 684
            and EXPECTED_BRANCH_TOKENS == 685
            and EXPECTED_CHILD_TOKENS == 690
            and EXPECTED_SUCCESSOR_TOKENS == 777
            and EXPECTED_COUNTED_AVOIDED_TOKENS == 4_104
            and EXPECTED_MODEL_CALLBACKS == 74
            and EXPECTED_DIRECT_PROTOCOL_ACTIONS == 27
        ),
        "device_byte_law_exact": (
            EXPECTED_BRANCH_DEVICE_BYTES - EXPECTED_BASE_DEVICE_BYTES
            == DEVICE_BYTES_PER_TOKEN
            and EXPECTED_CHILD_DEVICE_BYTES
            - EXPECTED_BRANCH_DEVICE_BYTES
            == 5 * DEVICE_BYTES_PER_TOKEN
            and EXPECTED_SUCCESSOR_TERMINAL_DEVICE_BYTES
            - EXPECTED_CHILD_DEVICE_BYTES
            == 87 * DEVICE_BYTES_PER_TOKEN
        ),
        "payload_hashes_prospectively_pinned": (
            len(EXPECTED_SEED_PAYLOAD_SHA256) == 64
            and all(
                len(value) == 64
                for mapping in EXPECTED_SUCCESSOR_PAYLOAD_SHA256.values()
                for value in mapping.values()
            )
        ),
        "three_matched_routes": (
            ROUTES == ("live-terminal", "root-only", "materialized")
        ),
        "latin_route_orders": len(TRIAL_ROUTE_ORDERS) == 3,
        "all_twelve_contract_fields_reject_and_poison": (
            len(TUPLE_MUTATION_FIELDS) == 12
            and "full_tuple_controls_reject_and_poison" in runtime_source
            and 'label=f"poisoned-boundary-replay-{field}"'
            in runtime_source
        ),
        "no_terminal_root_in_live_route": (
            "neo3000_capture_terminal_logits" not in runtime_source
            and "neo3000_use_terminal_logits" not in runtime_source
        ),
        "server_exact_contract_before_sampling": (
            preflight_source.index("neo3000_live_terminal_contract_equal(")
            < preflight_source.index("return &slot;")
            and preflight_source.index("return &slot;")
            < preflight_source.index("slot.prompt_clear(false);")
        ),
        "capture_surface_empty_and_receipt_checked": (
            "live.validate_capture_receipt(capture, wire)" in runtime_source
            and "capture_receipt" in runtime_source
            and '"response_fields"' in Path(
                live.__file__
            ).read_text(encoding="utf-8")
        ),
        "unresolved_logit_hash_absent_from_live_logs": (
            "logits=" not in context[
                live_capture_log_start:live_capture_log_end
            ]
            and "logits=" not in context[
                live_sample_log_start:live_sample_log_end
            ]
        ),
        "server_closes_before_projection": (
            context.index(
                "slot.terminal_logits.clear();",
                context.index("const bool live_source ="),
            )
            < context.index(
                "process_token(result, slot)",
                context.index("const bool live_source ="),
            )
        ),
        "shutdown_poisons_resident_boundary_before_backend_free": (
            "void poison_live_terminal_boundaries_for_shutdown()"
            in context
            and (
                "neo3000 one-use live terminal shutdown custody "
                "poisoned=%zu unresolved=%zu"
            )
            in context
            and shutdown_cleanup.index(
                "ctx_server.poison_live_terminal_boundaries_for_shutdown();"
            )
            < shutdown_cleanup.index("llama_backend_free();")
            and "audit_shutdown_live_terminal_custody(" in main_source
            and 'shutdown_custody.get("passed") is True' in main_source
        ),
        "closure_not_restoration": (
            '"restored_carrier_reuse_not_claimed": True' in runtime_source
            and "NOT_AVAILABLE_STATELESS_HTTP_LEASE" in runtime_source
            and "NOT_IMPLEMENTED_BY_CURRENT_SERVER_PROTOCOL"
            in runtime_source
        ),
        "durable_consumption_before_callback": (
            runtime_source.index('self.progress["consumption_marker"]')
            < runtime_source.index("return callback()")
        ),
        "canonical_identity_paths": (
            "output == DEFAULT_OUTPUT.resolve(strict=False)" in main_source
            and (
                "consumed_marker "
                "== DEFAULT_CONSUMED_MARKER.resolve(strict=False)"
            )
            in main_source
        ),
        "runtime_revalidated_immediately_before_launch": (
            main_source.index("prelaunch_static = static_audit()")
            < main_source.index("readiness = raw_sidecar.launch()")
        ),
        "output_after_cleanup": (
            main_source.index("cleanup = raw_sidecar.stop()")
            < main_source.index("terminal.write_exclusive_json(output, result)")
        ),
        "precontact_failure_preserves_identity": (
            "run_root / \"precontact-failure.json\"" in main_source
            and (
                "if caught is not None and not consumed_marker.is_file():"
                in main_source
            )
            and "candidate_started" in main_source
        ),
        "no_permanent_file_deletion": all(
            token not in runtime_source
            for token in ("rmtree", ".unlink(", "os.remove", "rmdir(")
        ),
    }
    require(
        all(gates.values()),
        "0091 static audit failed: "
        + ", ".join(key for key, value in gates.items() if not value),
    )
    return {
        "id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "gates": gates,
        "runtime": validate_runtime_manifest(),
        "live_route": live.static_audit(DEFAULT_BINARY.resolve(strict=True)),
        "scientific_contact": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--static-only", action="store_true")
    mode.add_argument("--execute-once", action="store_true")
    mode.add_argument("--write-runtime-manifest", action="store_true")
    parser.add_argument("--expected-commit")
    parser.add_argument("--runtime-source-commit")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--active-lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument(
        "--consumed-marker",
        type=Path,
        default=DEFAULT_CONSUMED_MARKER,
    )
    parser.add_argument("--run-parent", type=Path, default=DEFAULT_RUN_PARENT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.write_runtime_manifest:
        require(
            args.runtime_source_commit is not None,
            "--runtime-source-commit is required",
        )
        terminal.require_clean_head(ROOT, args.runtime_source_commit)
        runtime.require_pushed_frontier_head(args.runtime_source_commit)
        require(
            not DEFAULT_RUNTIME_MANIFEST.exists(),
            "0091 runtime manifest already exists",
        )
        manifest = runtime_manifest_template(args.runtime_source_commit)
        artifact = terminal.write_exclusive_json(
            DEFAULT_RUNTIME_MANIFEST,
            manifest,
        )
        print(json.dumps(artifact, indent=2, sort_keys=True))
        return 0
    if args.static_only:
        static = static_audit()
        print(json.dumps(static, indent=2, sort_keys=True))
        return 0

    output = DEFAULT_OUTPUT.resolve(strict=False)
    lock_path = DEFAULT_LOCK.resolve(strict=False)
    consumed_marker = DEFAULT_CONSUMED_MARKER.resolve(strict=False)
    run_parent = DEFAULT_RUN_PARENT.resolve(strict=False)
    run_created_ns = time.time_ns()
    run_root = run_parent / f"{EXPERIMENT_ID}-{run_created_ns}"
    expected_commit = str(args.expected_commit or "missing")
    transaction_nonce = hashlib.sha256(
        (
            f"{EXPERIMENT_ID}\n{expected_commit}\n"
            f"{run_created_ns}\n"
        ).encode("utf-8")
    ).hexdigest()[:16]
    original_stdout = sys.stdout
    stdout_wrapped = False
    progress: dict[str, Any] = {
        "scientific_contact": False,
        "transport_attempts": [],
        "protocol_attempts": [],
    }
    static: dict[str, Any] | None = None
    raw_sidecar: linux_sidecar.LinuxSidecar | None = None
    lock: dict[str, Any] = {"acquired": False}
    lock_acquired = False
    result: dict[str, Any] | None = None
    caught: BaseException | None = None
    cleanup: dict[str, Any] = {}
    shutdown_custody: dict[str, Any] = {}
    lock_release: dict[str, Any] = {}
    try:
        static = static_audit()
        require(
            args.expected_commit is not None,
            "--expected-commit is required",
        )
        terminal.require_clean_head(ROOT, expected_commit)
        runtime.require_pushed_frontier_head(expected_commit)
        require(
            args.output.resolve(strict=False) == output,
            "0091 output path is identity-canonical and cannot be overridden",
        )
        require(
            args.active_lock.resolve(strict=False) == lock_path,
            "0091 active-lock path is identity-canonical and cannot be "
            "overridden",
        )
        require(
            args.consumed_marker.resolve(strict=False) == consumed_marker,
            "0091 durable consumption path is identity-canonical and cannot "
            "be overridden",
        )
        require(
            args.run_parent.resolve(strict=False) == run_parent,
            "0091 run-parent path is identity-canonical and cannot be "
            "overridden",
        )
        require(not output.exists(), "0091 result already exists")
        require(
            not consumed_marker.exists(),
            "0091 durable consumption marker already exists",
        )
        raw_sidecar = linux_sidecar.LinuxSidecar(
            binary=DEFAULT_BINARY,
            model=DEFAULT_MODEL,
            run_root=run_root,
        )
        lock = acquire_lock(lock_path, expected_commit)
        lock_acquired = True
        sys.stdout = FailureProofTextIO(original_stdout)
        stdout_wrapped = True
        sidecar = ContactJournalSidecar(
            raw_sidecar,
            progress,
            consumed_marker,
            expected_commit,
        )
        prelaunch_static = static_audit()
        require(
            canonical_sha256(prelaunch_static) == canonical_sha256(static),
            "0091 runtime identity changed before launch",
        )
        readiness = raw_sidecar.launch()
        codec = harness.carrier.SidecarPromptCodec(linux_sidecar.PORT)
        props = codec.props()
        corpus = harness.carrier.load_public_corpus(ROOT)
        roots = {str(item["root_id"]): item for item in corpus["roots"]}
        prepared = terminal.prepare_task_and_branch(
            codec,
            roots[predecessor.ROOT_ID],
        )
        zero_contact_plan = geometry.derive_plan(codec, props, prepared)
        intent = terminal.write_exclusive_json(
            run_root / "request-intent.json",
            {
                "id": EXPERIMENT_ID,
                "attempt_id": ATTEMPT_ID,
                "expected_commit": expected_commit,
                "created_unix_ns": run_created_ns,
                "transaction_nonce": transaction_nonce,
                "routes": list(ROUTES),
                "trial_route_orders": [
                    list(order) for order in TRIAL_ROUTE_ORDERS
                ],
                "tuple_mutations": list(TUPLE_MUTATION_FIELDS),
                "restoration_class": RESTORATION_CLASS,
                "projection_policy": PROJECTION_POLICY,
                "geometry": zero_contact_plan["summary"],
                "meaning": (
                    "all request geometry, route order, tuple mutations, "
                    "policies, and transaction identity are fixed before "
                    "the first model callback"
                ),
            },
        )
        result = evaluate(
            sidecar=sidecar,
            codec=codec,
            props=props,
            prepared=prepared,
            transaction_nonce=transaction_nonce,
            progress=progress,
        )
        result["candidate_commit"] = expected_commit
        result["transaction_nonce"] = transaction_nonce
        result["readiness"] = readiness
        result["request_intent"] = intent
        result["static_evidence"] = static
        result["prelaunch_static_evidence"] = prelaunch_static
        result["launch_lock"] = lock
        result["consumption_marker"] = progress.get("consumption_marker")
        result["transport_attempts"] = progress["transport_attempts"]
        result["protocol_attempts"] = progress["protocol_attempts"]
        progress["scientific_contact"] = True
    except BaseException as exc:
        caught = exc
    finally:
        if raw_sidecar is None:
            cleanup = {
                "candidate_started": False,
                "candidate_stopped": True,
                "port_free": not linux_sidecar.port_accepts_connections(
                    linux_sidecar.PORT
                ),
            }
        else:
            try:
                cleanup = raw_sidecar.stop()
            except BaseException as exc:
                cleanup = {
                    "candidate_started": True,
                    "candidate_stopped": False,
                    "port_free": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                if caught is None:
                    caught = exc
        if raw_sidecar is None:
            shutdown_custody = {
                "candidate_started": False,
                "shutdown_summary_count": 0,
                "poisoned_boundaries": 0,
                "unresolved_boundaries": 0,
                "passed": True,
                "meaning": (
                    "no candidate process existed and no boundary could reside"
                ),
            }
        else:
            try:
                shutdown_custody = audit_shutdown_live_terminal_custody(
                    raw_sidecar,
                    cleanup,
                )
            except BaseException as exc:
                shutdown_custody = {
                    "candidate_started": (
                        cleanup.get("candidate_started") is True
                        or cleanup.get("pid") is not None
                    ),
                    "passed": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                if caught is None:
                    caught = exc
        cleanup["live_terminal_shutdown_custody"] = shutdown_custody
        if lock_acquired:
            try:
                lock_release = release_lock(lock_path)
            except BaseException as exc:
                lock_release = {
                    "released": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                if caught is None:
                    caught = exc
        else:
            lock_release = {
                "released": False,
                "reason": "launch-lock-not-acquired",
            }
        if stdout_wrapped:
            sys.stdout = original_stdout

    closure = (
        cleanup.get("candidate_stopped") is True
        and cleanup.get("port_free") is True
        and shutdown_custody.get("passed") is True
        and lock_release.get("released") is True
        and "error" not in cleanup
        and "error" not in lock_release
    )
    if caught is None and not closure:
        caught = ExperimentError(
            "0091 process, port, or launch-lock closure failed"
        )
    if caught is not None and not consumed_marker.is_file():
        precontact_failure = {
            "id": EXPERIMENT_ID,
            "attempt_id": ATTEMPT_ID,
            "status": "precontact-failure",
            "error_type": type(caught).__name__,
            "error": str(caught),
            "scientific_contact": False,
            "cleanup": cleanup,
            "launch_lock": lock,
            "launch_lock_release": lock_release,
            "canonical_identity_consumed": False,
            "automatic_promotion": False,
        }
        receipt = terminal.write_exclusive_json(
            run_root / "precontact-failure.json",
            precontact_failure,
        )
        raise ExperimentError(
            "0091 failed before model contact; canonical identity remains "
            f"unconsumed and evidence is preserved at {receipt['path']}"
        ) from caught
    if caught is not None:
        full_failure = {
            "id": EXPERIMENT_ID,
            "attempt_id": ATTEMPT_ID,
            "status": "failed-after-closure",
            "error_type": type(caught).__name__,
            "error": str(caught),
            "scientific_contact": progress.get("scientific_contact"),
            "transport_attempts": progress.get("transport_attempts"),
            "protocol_attempts": progress.get("protocol_attempts"),
            "result_before_cleanup": result,
            "cleanup": cleanup,
            "launch_lock": lock,
            "launch_lock_release": lock_release,
            "automatic_promotion": False,
        }
        custody_failure = {
            "id": EXPERIMENT_ID,
            "attempt_id": ATTEMPT_ID,
            "status": "poisoned-before-closure",
            "error_type": type(caught).__name__,
            "error": str(caught),
            "scientific_contact": bool(progress.get("scientific_contact")),
            "transport_attempt_count": len(
                progress.get("transport_attempts", [])
            ),
            "protocol_attempt_count": len(
                progress.get("protocol_attempts", [])
            ),
            "cleanup": cleanup,
            "launch_lock_release": lock_release,
            "outcome_projection_withheld": True,
            "automatic_promotion": False,
        }
        failure = full_failure if closure else custody_failure
        terminal.write_exclusive_json(output, failure)
        raise ExperimentError(
            f"0091 failed; evidence preserved at {output}"
        ) from caught

    require(result is not None, "0091 result is missing")
    require(closure, "0091 process/port/lock closure failed")
    result["cleanup"] = cleanup
    result["launch_lock_release"] = lock_release
    result["artifact"] = terminal.write_exclusive_json(output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
