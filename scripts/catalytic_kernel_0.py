#!/usr/bin/env python3
"""Minimal six-request borrow -> transform -> extract -> restore kernel.

This is a process-local catalytic computing primitive, not a benchmark or a
claim protocol.  The model authors only branch rankings, one relation operator,
one transformed ranking, and one extracted candidate.  The controller derives
all bookkeeping and persists bounded normalized metadata only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from catalytic_advantage_tasks import (
    EXPECTED_SUITE_SHA256,
    CandidateProgram,
    Example,
    build_frozen_task_suite,
    execute_program,
)
from catalytic_kernel_0_carrier_scan import (
    PROFILE_ID as UNRESOLVED_PROFILE_ID,
    selected_unresolved_public_profile,
)
from catalytic_inference_bench_0 import validate_metadata_only
from catalytic_inference_bench_0_runtime import (
    MODEL_ALIAS,
    _HoloStateAdapter,
    _normalized_transport,
    _public_preflight,
    validate_run_id,
)
from catalytic_swarm_1_v2_root_law import RootCacheObservation, adjudicate_root_cache


KERNEL_ID = "catalytic-kernel-0"
TASK_ID = "cs1-task-06"
CARRIER_ID = "ck0:cs1-task-06:public-carrier"
STATE_SCHEMA_VERSION = 1
PHYSICAL_SLOT = 0
REQUEST_IDS = ("borrow", "branch-a", "branch-b", "transform", "extract", "restore")
BRANCH_SHARDS = {"branch-a": (0, 1, 2), "branch-b": (2, 3, 4)}
ALLOWED_OPERATORS = frozenset({"combine", "oppose", "eliminate", "refine", "reconcile"})
MAX_STRUCTURED_BYTES = 1024
MAX_CARRIER_BYTES = 12 * 1024
MAX_ARTIFACT_BYTES = 4 * 1024
MAX_STATE_FILE_BYTES = 256 * 1024
EXPECTED_CIB0_RUN_IDS = (
    "cib0-20260713T065856Z-a1",
    "cib0-20260713T071048Z-a2",
    "cib0-20260713T072640Z-a3",
    "cib0-20260713T081348Z-a4",
    "cib0-20260713T082917Z-a5",
    "cib0-20260713T092633Z-a6",
)
EXPECTED_CIB0_TREE_SHA256 = "57CE7FFFEBBB925BBD3B37F55A9394037720018748776C2C42DD17961D8ECCBD"
EXPECTED_CK0_HISTORY = {
    "ck0-20260713T230841Z-a1": {
        "closure.json": "95C1F19309E293EB1421EE4E1941C411AAA670F659F6236EEE31EB1DABE18DAA",
        "manifest.json": "DC7E1B045BE85C0513A73AF22E5718F73F36753B271E874E5EFBB0FE05E6E2CD",
        "result.json": "2C8A3B05EAC4829A903FAAD43C4D602737B0D86C0720291901D2D241D4AB9402",
    },
    "ck0-20260713T234035Z-a2": {
        "closure.json": "6F179087C48F98A0E0BF88B7D264AD55D9068E74643C6C9EAB1C56ACA3335AD4",
        "manifest.json": "3E2FB2040513EF44CA02A5D0EFFE91A1AC60C3D0357E18820526402C12409E8E",
        "result.json": "3161D42296E6CEB4E2803D00ADB790A23E98CD7556FDBD17FA1C4EC4B44EC85F",
    },
}
EXPECTED_CK0_HISTORY_SHA256 = "BB15C248EFBF075F77899161FC6EEDCD28830097CB6D0B67D7BB7F368ADCC249"
STATE_FILENAMES = ("manifest.json", "result.json", "closure.json", "run.lock")
FORBIDDEN_PRIVATE_FIELDS = frozenset(
    {"hidden_examples", "answer_candidate_id", "hidden_score", "private_evaluator_data"}
)
CLAIMS = {
    "CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN": "LOCKED",
    "SOTA_SWARM_CLAIM": "LOCKED",
    "PROCESS_LOCAL_HOLOSTATE_AVAILABLE": "LOCKED",
    "RESTART_PERSISTENT_HOLOSTATE_AVAILABLE": "LOCKED",
    "DEEP": "DISABLED",
    "automatic_promotion": False,
}
PARENT_A_INFORMATION_DELETION_CONTROL = "parent-a-information-deletion"
PARENT_A_CONTROL_RUN_ID = "ck0-20260714T215806Z-a5"
PARENT_A_CONTROL_PREREGISTRATION = "lab/ck0_parent_a_information_deletion_1.json"
PARENT_A_CONTROL_STARTING_MAIN = "97d406ccdbb0e219cb5935ce9386c230337c1d3a"
PARENT_A_CONTROL_FROZEN_IMPLEMENTATION = "b19a4b4d6147bc10459c7d1d144021a1ff3d8eed"
PARENT_A_CONTROL_CLASSIFICATIONS = (
    "PARENT_A_INFORMATION_NECESSITY_SUPPORTED",
    "PARENT_A_INFORMATION_NOT_SHOWN_NECESSARY",
    "CAUSAL_CONTROL_INCONCLUSIVE",
)
CONTROL_TRANSFORM_INSTRUCTION = (
    "Operate on the supplied parent projections. Author one allowed operator and one candidate ranking."
)
BLINDED_PARENT_RECEIPT_FIELDS = frozenset(
    {
        "artifact_id",
        "artifact_sha256",
        "carrier_profile_id",
        "projection_mode",
        "informative_content_withheld",
    }
)


class CatalyticKernel0Error(ValueError):
    """The kernel boundary is malformed, unsafe, or incomplete."""


class KernelAdapter(Protocol):
    def preflight(
        self,
        *,
        args: Any,
        repository_root: Path,
        run_root: Path,
        allowed_paths: Sequence[Path],
    ) -> Mapping[str, Any]: ...

    def create_lease_pool(self, physical_slots: int) -> Any: ...

    def launch_sidecar(
        self, *, preflight: Mapping[str, Any], run_id: str
    ) -> tuple[Any, Mapping[str, Any]]: ...

    def prompt_geometry(
        self, *, sidecar: Any, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...

    def execute_request(
        self, *, sidecar: Any, payload: Mapping[str, Any], request: Any
    ) -> Any: ...

    def boundary_custody(
        self,
        *,
        preflight: Mapping[str, Any],
        sidecar: Any,
        boundary: str,
    ) -> Mapping[str, Any]: ...

    def resource_summary(
        self, *, sidecar: Any, boundary: str
    ) -> Mapping[str, Any]: ...

    def cleanup(
        self, *, sidecar: Any | None, preflight: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...

    def postflight(self, *, preflight: Mapping[str, Any]) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class KernelRequest:
    request_id: str
    ordinal: int
    max_tokens: int = 64


@dataclass(frozen=True)
class PublicKernelTask:
    task_id: str
    semantics: Mapping[str, Any]
    public_examples: tuple[Example, ...]
    candidates: tuple[CandidateProgram, ...]

    def candidate(self, candidate_id: str) -> CandidateProgram:
        for candidate in self.candidates:
            if candidate.candidate_id == candidate_id:
                return candidate
        raise CatalyticKernel0Error(f"{self.task_id} has no candidate {candidate_id!r}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_json_text(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def json_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _safe_failure(exc: BaseException, *, boundary: str) -> dict[str, str]:
    message = str(exc)
    return {
        "boundary": boundary[:80],
        "exception_type": type(exc).__name__[:80],
        "message_sha256": sha256_bytes(message.encode("utf-8")),
    }


def _arg(args: Any, name: str) -> Any:
    return args.get(name) if isinstance(args, Mapping) else getattr(args, name, None)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    validate_metadata_only(value)
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        indent=2,
    ).encode("utf-8") + b"\n"
    if len(encoded) > MAX_STATE_FILE_BYTES:
        raise CatalyticKernel0Error("bounded kernel state file exceeds its byte ceiling")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


class CatalyticKernel0Adapter(_HoloStateAdapter):
    """CK0 adapter: existing lifecycle with request telemetry made advisory."""

    def launch_sidecar(
        self, *, preflight: Mapping[str, Any], run_id: str
    ) -> tuple[Any, Mapping[str, Any]]:
        runtime = preflight["runtime"]
        readiness_control = runtime["predecessor"]["readiness_control"]
        temp_root = Path(tempfile.mkdtemp(prefix=f"neo3000-ck0-{run_id}-"))
        runtime["temp_root"] = temp_root
        deadline = time.monotonic() + float(readiness_control["readiness_deadline_seconds"])
        sidecar = self.h.LiveSidecar(
            runtime["binary"],
            runtime["model"],
            runtime["evaluator"],
            runtime["live_contract"],
            detached=False,
            stable_pids=runtime["stable_pids"],
            readiness_control=readiness_control,
            prelaunch_evidence={"stable_pids": sorted(runtime["stable_pids"])},
            readiness_deadline_at=deadline,
            preverified_binary_identity=preflight["metadata"]["binary_identity"],
            preverified_model_identity=preflight["metadata"]["model_identity"],
            state_root=temp_root,
            wddm_policy=None,
            advisory_wddm=True,
            stable_health_recovery_policy=self.h.StableHealthRecoveryPolicy(
                maximum_consecutive_failure_seconds=15.0,
                required_consecutive_successes=3,
            ),
        )
        try:
            readiness = sidecar.launch()
        except BaseException:
            self.h.safe_sidecar_cleanup(sidecar)
            raise
        readiness_private = readiness.get("process_memory", {}).get("private_bytes")
        self._host_private_baseline_bytes = (
            int(readiness_private) if isinstance(readiness_private, int) else None
        )
        recovery = readiness.get("readiness_ownership", {}).get(
            "stable_health_recovery", {}
        )
        return sidecar, {
            "sidecar_pid": int(readiness["pid"]),
            "readiness_seconds": float(readiness["readiness_seconds"]),
            "private_bytes": self._host_private_baseline_bytes,
            "stable_pids": list(readiness["stable_pids"]),
            "chat_template_sha256": str(readiness["chat_template_sha256"]),
            "stable_health_recovery": dict(recovery),
            "resource_telemetry_mode": "advisory-except-valid-measured-ceiling-breach",
        }

    def cleanup(
        self, *, sidecar: Any | None, preflight: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        runtime = preflight["runtime"]
        cleanup = self.h.safe_sidecar_cleanup(sidecar)
        temp_root = runtime.get("temp_root")
        if isinstance(temp_root, Path):
            shutil.rmtree(temp_root, ignore_errors=True)
        temp_removed = not isinstance(temp_root, Path) or not temp_root.exists()
        stable_preserved = cleanup.get("stable_after", {}).get("listener_pids") == sorted(
            runtime["stable_pids"]
        )
        process_stopped = cleanup.get(
            "process_stopped", cleanup.get("not_launched") is True
        )
        runtime_removed = cleanup.get(
            "runtime_removed", cleanup.get("not_launched") is True
        )
        structural_pass = all(
            (
                process_stopped is True,
                cleanup.get("port_free") is True,
                runtime_removed is True,
                stable_preserved,
                temp_removed,
            )
        )
        return {
            "passed": structural_pass,
            "process_stopped": process_stopped is True,
            "port_free": cleanup.get("port_free") is True,
            "runtime_removed": runtime_removed is True,
            "stable_preserved": stable_preserved,
            "temporary_state_removed": temp_removed,
            "resource_telemetry_mode": "advisory",
        }


def _snapshot_tree(root: Path) -> dict[str, Any]:
    if not root.is_dir() or root.is_symlink():
        raise CatalyticKernel0Error("CIB0 evidence root is missing or unsafe")
    run_ids = tuple(sorted(path.name for path in root.iterdir() if path.is_dir()))
    if run_ids != EXPECTED_CIB0_RUN_IDS:
        raise CatalyticKernel0Error("historical CIB0 run set differs from a1 through a6")
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink():
            raise CatalyticKernel0Error("historical CIB0 evidence contains a link")
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            entries.append({"path": relative + "/", "kind": "directory"})
        elif path.is_file():
            data = path.read_bytes()
            entries.append(
                {
                    "path": relative,
                    "kind": "file",
                    "size_bytes": len(data),
                    "sha256": sha256_bytes(data),
                }
            )
        else:
            raise CatalyticKernel0Error("historical CIB0 evidence contains a special file")
    snapshot = {
        "run_ids": list(run_ids),
        "entry_count": len(entries),
        "tree_sha256": json_sha256(entries),
    }
    if snapshot["tree_sha256"] != EXPECTED_CIB0_TREE_SHA256:
        raise CatalyticKernel0Error("historical CIB0 evidence differs from the admitted a1-a6 tree")
    return snapshot


def _snapshot_historical_ck0(root: Path) -> dict[str, Any]:
    if not root.is_dir() or root.is_symlink():
        raise CatalyticKernel0Error("CK0 evidence root is missing or unsafe")
    entries: list[dict[str, Any]] = []
    for run_id, files in EXPECTED_CK0_HISTORY.items():
        run_root = root / run_id
        if not run_root.is_dir() or run_root.is_symlink():
            raise CatalyticKernel0Error("historical CK0 run is missing or unsafe")
        if {path.name for path in run_root.iterdir()} != set(files):
            raise CatalyticKernel0Error("historical CK0 file set changed")
        for filename, expected_sha256 in files.items():
            path = run_root / filename
            if not path.is_file() or path.is_symlink():
                raise CatalyticKernel0Error("historical CK0 evidence file is unsafe")
            data = path.read_bytes()
            actual_sha256 = sha256_bytes(data)
            if actual_sha256 != expected_sha256:
                raise CatalyticKernel0Error("historical CK0 evidence changed")
            entries.append(
                {
                    "path": f"{run_id}/{filename}",
                    "bytes": len(data),
                    "sha256": actual_sha256,
                }
            )
    entries.sort(key=lambda item: item["path"])
    snapshot = {
        "run_ids": list(EXPECTED_CK0_HISTORY),
        "file_count": len(entries),
        "tree_sha256": json_sha256(entries),
    }
    if snapshot["tree_sha256"] != EXPECTED_CK0_HISTORY_SHA256:
        raise CatalyticKernel0Error("historical CK0 tree identity changed")
    return snapshot


def _validated_profile(profile: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    expected = selected_unresolved_public_profile()
    supplied = dict(profile)
    supplied.pop("carrier_content_sha256", None)
    supplied.pop("carrier_root_sha256", None)
    if supplied != expected:
        raise CatalyticKernel0Error("unresolved carrier profile identity drift")
    return expected


def _validated_control(
    control: str | None, profile: Mapping[str, Any] | None
) -> str | None:
    if control is None:
        return None
    if control != PARENT_A_INFORMATION_DELETION_CONTROL:
        raise CatalyticKernel0Error("unknown or unauthorized CK0 control")
    validated = _validated_profile(profile)
    if validated is None or validated["profile_id"] != UNRESOLVED_PROFILE_ID:
        raise CatalyticKernel0Error(
            "parent-A information deletion requires the frozen unresolved profile"
        )
    return control


def _profile_indices(profile: Mapping[str, Any] | None) -> dict[str, tuple[int, ...]]:
    if profile is None:
        return {key: tuple(value) for key, value in BRANCH_SHARDS.items()}
    validated = _validated_profile(profile)
    assert validated is not None
    return {
        branch_id: tuple(int(index) for index in validated["branch_indices"][branch_id])
        for branch_id in BRANCH_SHARDS
    }


def _profile_carrier_id(profile: Mapping[str, Any] | None) -> str:
    if profile is None:
        return CARRIER_ID
    validated = _validated_profile(profile)
    assert validated is not None
    return f"ck0:{validated['task_id']}:{validated['profile_id']}:public-carrier"


def _model_visible_profile_identity(profile: Mapping[str, Any]) -> dict[str, Any]:
    validated = _validated_profile(profile)
    assert validated is not None
    return {
        "profile_id": validated["profile_id"],
        "task_suite_sha256": validated["task_suite_sha256"],
        "task_id": validated["task_id"],
        "branch_shards": dict(validated["branch_shards"]),
        "shared_calibration_example_id": validated["shared_calibration_example_id"],
        "eligibility_tier": validated["eligibility_tier"],
        "public_score_matrix_sha256": validated["public_score_matrix_sha256"],
        "scan_sha256": validated["scan_sha256"],
    }


def public_task(profile: Mapping[str, Any] | None = None) -> PublicKernelTask:
    profile = _validated_profile(profile)
    suite = build_frozen_task_suite()
    if suite.suite_sha256 != EXPECTED_SUITE_SHA256:
        raise CatalyticKernel0Error("task-suite identity drift")
    task_index = 5 if profile is None else int(profile["task_index"])
    expected_task_id = TASK_ID if profile is None else profile["task_id"]
    task = suite.tasks[task_index]
    if task.task_id != expected_task_id or len(task.public_examples) != 5 or len(task.candidates) != 64:
        raise CatalyticKernel0Error("kernel task geometry drift")
    projection = task.public_projection()
    if "hidden_examples" in projection or "answer_candidate_id" in projection:
        raise CatalyticKernel0Error("protected task material entered the public projection")
    return PublicKernelTask(
        task_id=task.task_id,
        semantics=dict(projection["semantics"]),
        public_examples=tuple(task.public_examples),
        candidates=tuple(task.candidates),
    )


def build_carrier(profile: Mapping[str, Any] | None = None) -> dict[str, Any]:
    profile = _validated_profile(profile)
    task = public_task(profile)
    carrier_id = _profile_carrier_id(profile)
    content = {
        "carrier_id": carrier_id,
        "task_definition": {
            "task_id": task.task_id,
            "semantics": dict(task.semantics),
        },
        "candidate_ids": [item.candidate_id for item in task.candidates],
        "candidate_programs": [
            {
                "candidate_id": item.candidate_id,
                "instructions": [instruction.to_dict() for instruction in item.instructions],
            }
            for item in task.candidates
        ],
        "kernel_instructions": {
            "cycle": list(REQUEST_IDS),
            "law": "borrow -> transform -> extract -> restore",
            "model_authorship": [
                "branch candidate rankings",
                "transform relation operator and ranking",
                "extracted candidate ID",
                "minimal carrier acknowledgements",
            ],
            "controller_authorship": "all hashes, edges, rank deltas, scores, bindings, and restoration gates",
        },
    }
    if profile is not None:
        content["profile_identity"] = _model_visible_profile_identity(profile)
    content_sha256 = json_sha256(content)
    root_object = {**content, "carrier_content_sha256": content_sha256}
    root = canonical_json_text(root_object)
    if len(root.encode("utf-8")) > MAX_CARRIER_BYTES:
        raise CatalyticKernel0Error("immutable carrier root exceeds its bound")
    validate_metadata_only(root_object)
    carrier = {
        "carrier_id": carrier_id,
        "carrier_content_sha256": content_sha256,
        "carrier_root": root,
        "carrier_root_sha256": sha256_bytes(root.encode("utf-8")),
    }
    if profile is not None:
        carrier["profile"] = {
            **profile,
            "carrier_content_sha256": content_sha256,
            "carrier_root_sha256": carrier["carrier_root_sha256"],
        }
    return carrier


def _carrier_is_pristine(carrier: Mapping[str, Any]) -> bool:
    root_text = carrier.get("carrier_root")
    if not isinstance(root_text, str):
        return False
    try:
        root = json.loads(root_text)
    except json.JSONDecodeError:
        return False
    expected_keys = {
        "carrier_id",
        "task_definition",
        "candidate_ids",
        "candidate_programs",
        "kernel_instructions",
        "carrier_content_sha256",
    }
    profile = carrier.get("profile")
    if profile is not None:
        expected_keys.add("profile_identity")
    if not isinstance(root, dict) or set(root) != expected_keys:
        return False
    claimed_content_sha = root.pop("carrier_content_sha256")
    programs = root.get("candidate_programs")
    task_definition = root.get("task_definition")
    return bool(
        claimed_content_sha == json_sha256(root)
        and claimed_content_sha == carrier.get("carrier_content_sha256")
        and sha256_bytes(root_text.encode("utf-8"))
        == carrier.get("carrier_root_sha256")
        and root.get("carrier_id") == carrier.get("carrier_id")
        and isinstance(task_definition, dict)
        and set(task_definition) == {"task_id", "semantics"}
        and isinstance(programs, list)
        and len(programs) == 64
        and all(
            isinstance(item, dict)
            and set(item) == {"candidate_id", "instructions"}
            for item in programs
        )
        and root.get("candidate_ids") == [item["candidate_id"] for item in programs]
        and (
            profile is None
            or root.get("profile_identity") == _model_visible_profile_identity(profile)
        )
    )


def build_public_shard(
    branch_id: str, profile: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    if branch_id not in BRANCH_SHARDS:
        raise CatalyticKernel0Error("unknown branch shard")
    profile = _validated_profile(profile)
    task = public_task(profile)
    ordinals = _profile_indices(profile)[branch_id]
    return {
        "branch_id": branch_id,
        "example_ids": [f"public-example-{index + 1}" for index in ordinals],
        "public_examples": [task.public_examples[index].to_dict() for index in ordinals],
    }


def _ranking_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["ranking"],
        "properties": {
            "ranking": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "uniqueItems": True,
                "items": {"type": "string", "pattern": "^C(?:[0-5][0-9]|6[0-3])$"},
            }
        },
    }


def response_schema(request_id: str, *, carrier_id: str = CARRIER_ID) -> dict[str, Any]:
    if request_id in {"borrow", "restore"}:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["carrier_id"],
            "properties": {"carrier_id": {"type": "string", "const": carrier_id}},
        }
    if request_id in BRANCH_SHARDS:
        return _ranking_schema()
    if request_id == "transform":
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["operator", "ranking"],
            "properties": {
                "operator": {"type": "string", "enum": sorted(ALLOWED_OPERATORS)},
                "ranking": _ranking_schema()["properties"]["ranking"],
            },
        }
    if request_id == "extract":
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["candidate_id"],
            "properties": {
                "candidate_id": {"type": "string", "pattern": "^C(?:[0-5][0-9]|6[0-3])$"}
            },
        }
    raise CatalyticKernel0Error("unknown kernel request")


def _require_ranking(
    value: Any, profile: Mapping[str, Any] | None = None
) -> list[str]:
    valid_ids = {item.candidate_id for item in public_task(profile).candidates}
    if (
        not isinstance(value, list)
        or not 1 <= len(value) <= 3
        or any(not isinstance(item, str) or item not in valid_ids for item in value)
        or len(set(value)) != len(value)
    ):
        raise CatalyticKernel0Error("ranking must contain one to three unique valid candidate IDs")
    return list(value)


def parse_response(
    request_id: str,
    content: str,
    *,
    transform_artifact: Mapping[str, Any] | None = None,
    profile: Mapping[str, Any] | None = None,
    carrier_id: str = CARRIER_ID,
) -> dict[str, Any]:
    profile = _validated_profile(profile)
    if not isinstance(content, str) or not content or len(content.encode("utf-8")) > MAX_STRUCTURED_BYTES:
        raise CatalyticKernel0Error("structured response is empty or over its bound")
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise CatalyticKernel0Error("structured response is not JSON") from exc
    if not isinstance(value, dict):
        raise CatalyticKernel0Error("structured response is not an object")
    if request_id in {"borrow", "restore"}:
        if set(value) != {"carrier_id"} or value["carrier_id"] != carrier_id:
            raise CatalyticKernel0Error("carrier acknowledgement is invalid")
    elif request_id in BRANCH_SHARDS:
        if set(value) != {"ranking"}:
            raise CatalyticKernel0Error("branch response field set changed")
        value = {"ranking": _require_ranking(value["ranking"], profile)}
    elif request_id == "transform":
        if set(value) != {"operator", "ranking"} or value.get("operator") not in ALLOWED_OPERATORS:
            raise CatalyticKernel0Error("transform response is invalid")
        value = {
            "operator": value["operator"],
            "ranking": _require_ranking(value["ranking"], profile),
        }
    elif request_id == "extract":
        if set(value) != {"candidate_id"} or not isinstance(value.get("candidate_id"), str):
            raise CatalyticKernel0Error("extraction response is invalid")
        if not isinstance(transform_artifact, Mapping) or value["candidate_id"] not in transform_artifact.get("ranking", []):
            raise CatalyticKernel0Error("extraction candidate is absent from transform ranking")
    else:
        raise CatalyticKernel0Error("unknown kernel request")
    validate_metadata_only(value)
    return value


def _score_examples(
    task: PublicKernelTask,
    candidate_id: str,
    examples: Sequence[tuple[int, Example]],
) -> dict[str, Any]:
    program = task.candidate(candidate_id)
    observations = [
        {
            "example_id": f"public-example-{index + 1}",
            "passed": execute_program(program, example.x) == example.y,
        }
        for index, example in examples
    ]
    return {
        "candidate_id": candidate_id,
        "passed": sum(item["passed"] for item in observations),
        "total": len(observations),
        "example_results": observations,
    }


def normalize_branch(
    branch_id: str,
    ranking: Sequence[str],
    profile: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    profile = _validated_profile(profile)
    ranking = _require_ranking(list(ranking), profile)
    task = public_task(profile)
    indices = _profile_indices(profile)[branch_id]
    examples = [(index, task.public_examples[index]) for index in indices]
    body = {
        "artifact_id": branch_id,
        "artifact_kind": "public-evidence-branch",
        "ranking": ranking,
        "public_shard_ids": [f"public-example-{index + 1}" for index in indices],
        "shard_scores": [_score_examples(task, candidate_id, examples) for candidate_id in ranking],
    }
    if profile is not None:
        all_scores = [
            _score_examples(task, candidate.candidate_id, examples)
            for candidate in task.candidates
        ]
        top_score = max(score["passed"] for score in all_scores)
        public_argmax_set = [
            score["candidate_id"] for score in all_scores if score["passed"] == top_score
        ]
        lower_scores = [score["passed"] for score in all_scores if score["passed"] < top_score]
        plateau_gap = top_score - max(lower_scores) if lower_scores else 0
        if (
            public_argmax_set != profile["public_argmax_sets"][branch_id]
            or top_score != profile["public_top_scores"][branch_id]
            or plateau_gap != profile["public_plateau_gaps"][branch_id]
        ):
            raise CatalyticKernel0Error("branch unresolved-support identity drift")
        body.update(
            {
                "carrier_profile_id": profile["profile_id"],
                "shared_calibration_example_id": profile["shared_calibration_example_id"],
                "public_argmax_set": public_argmax_set,
                "public_top_score": top_score,
                "public_plateau_gap": plateau_gap,
                "public_argmax_evidence": [
                    score for score in all_scores if score["candidate_id"] in public_argmax_set
                ],
                "model_ranking_contains_public_argmax_set": set(public_argmax_set).issubset(ranking),
            }
        )
    artifact = {**body, "artifact_sha256": json_sha256(body)}
    if len(canonical_json_bytes(artifact)) > MAX_ARTIFACT_BYTES:
        raise CatalyticKernel0Error("branch artifact exceeds its bound")
    validate_metadata_only(artifact)
    return artifact


def shared_example_consistency(branch_a: Mapping[str, Any], branch_b: Mapping[str, Any]) -> dict[str, Any]:
    shared_ids = sorted(set(branch_a["public_shard_ids"]) & set(branch_b["public_shard_ids"]))
    if len(shared_ids) != 1:
        raise CatalyticKernel0Error("branch artifacts do not share exactly one calibration example")
    shared_id = shared_ids[0]

    def shared(artifact: Mapping[str, Any]) -> dict[str, bool]:
        result: dict[str, bool] = {}
        for score in artifact["shard_scores"]:
            for example in score["example_results"]:
                if example["example_id"] == shared_id:
                    result[score["candidate_id"]] = example["passed"]
        return result

    left, right = shared(branch_a), shared(branch_b)
    common = sorted(set(left) & set(right))
    return {
        "shared_example_id": shared_id,
        "overlapping_candidate_ids": common,
        "overlap_consistent": all(left[item] == right[item] for item in common),
        "branch_a_top_passed": left[branch_a["ranking"][0]],
        "branch_b_top_passed": right[branch_b["ranking"][0]],
    }


def derive_rank_delta(parent: Sequence[str], output: Sequence[str]) -> dict[str, Any]:
    parent_positions = {candidate_id: index for index, candidate_id in enumerate(parent, 1)}
    output_positions = {candidate_id: index for index, candidate_id in enumerate(output, 1)}
    rows: list[dict[str, Any]] = []
    for candidate_id in sorted(set(parent_positions) | set(output_positions)):
        before = parent_positions.get(candidate_id)
        after = output_positions.get(candidate_id)
        if before is None:
            change = "introduced"
            delta = None
        elif after is None:
            change = "removed"
            delta = None
        else:
            delta = after - before
            change = "promoted" if delta < 0 else "demoted" if delta > 0 else "retained"
        rows.append(
            {
                "candidate_id": candidate_id,
                "parent_rank": before,
                "result_rank": after,
                "rank_delta": delta,
                "change": change,
            }
        )
    return {
        "changes": rows,
        "introduced": [item["candidate_id"] for item in rows if item["change"] == "introduced"],
        "removed": [item["candidate_id"] for item in rows if item["change"] == "removed"],
        "promoted": [item["candidate_id"] for item in rows if item["change"] == "promoted"],
        "demoted": [item["candidate_id"] for item in rows if item["change"] == "demoted"],
        "retained": [item["candidate_id"] for item in rows if item["change"] == "retained"],
    }


def normalize_transform(
    branch_a: Mapping[str, Any],
    branch_b: Mapping[str, Any],
    *,
    operator: str,
    ranking: Sequence[str],
    profile: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    profile = _validated_profile(profile)
    if operator not in ALLOWED_OPERATORS:
        raise CatalyticKernel0Error("unknown transform operator")
    ranking = _require_ranking(list(ranking), profile)
    parents = (branch_a, branch_b)
    for expected, parent in zip(BRANCH_SHARDS, parents):
        if parent.get("artifact_id") != expected or parent.get("artifact_sha256") != json_sha256(
            {key: value for key, value in parent.items() if key != "artifact_sha256"}
        ):
            raise CatalyticKernel0Error("transform parent artifact binding is invalid")
    deltas = {
        parent["artifact_id"]: derive_rank_delta(parent["ranking"], ranking)
        for parent in parents
    }
    edges = []
    for result_rank, candidate_id in enumerate(ranking, 1):
        for parent in parents:
            parent_rank = (
                parent["ranking"].index(candidate_id) + 1
                if candidate_id in parent["ranking"]
                else None
            )
            edge_body = {
                "parent_artifact_id": parent["artifact_id"],
                "parent_artifact_sha256": parent["artifact_sha256"],
                "candidate_id": candidate_id,
                "parent_rank": parent_rank,
                "result_rank": result_rank,
            }
            edges.append({**edge_body, "edge_id": "edge-" + json_sha256(edge_body)[:16]})
    body = {
        "artifact_id": "transform",
        "artifact_kind": "two-parent-relational-transform",
        "parent_artifact_ids": [parent["artifact_id"] for parent in parents],
        "parent_artifact_sha256": [parent["artifact_sha256"] for parent in parents],
        "operator": operator,
        "ranking": ranking,
        "rank_deltas": deltas,
        "dag_edges": edges,
        "rankings_differ": branch_a["ranking"] != branch_b["ranking"],
        "differs_from_parent": {
            parent["artifact_id"]: ranking != parent["ranking"] for parent in parents
        },
        "identity_transform": ranking == branch_a["ranking"] == branch_b["ranking"],
        "candidate_set_changed": any(set(ranking) != set(parent["ranking"]) for parent in parents),
    }
    artifact = {**body, "artifact_sha256": json_sha256(body)}
    if len(canonical_json_bytes(artifact)) > MAX_ARTIFACT_BYTES:
        raise CatalyticKernel0Error("transform artifact exceeds its bound")
    validate_metadata_only(artifact)
    return artifact


def normalize_extraction(
    candidate_id: str,
    transform: Mapping[str, Any],
    profile: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    profile = _validated_profile(profile)
    if candidate_id not in transform.get("ranking", []):
        raise CatalyticKernel0Error("extraction candidate is absent from transform")
    task = public_task(profile)
    examples = list(enumerate(task.public_examples))
    score = _score_examples(task, candidate_id, examples)
    body = {
        "artifact_id": "extract",
        "artifact_kind": "transform-bound-extraction",
        "candidate_id": candidate_id,
        "transform_artifact_sha256_consumed": transform["artifact_sha256"],
        "transform_rank_consumed": transform["ranking"].index(candidate_id) + 1,
        "all_public_score": score,
    }
    artifact = {**body, "artifact_sha256": json_sha256(body)}
    if len(canonical_json_bytes(artifact)) > MAX_ARTIFACT_BYTES:
        raise CatalyticKernel0Error("extraction artifact exceeds its bound")
    validate_metadata_only(artifact)
    return artifact


def unresolved_relation_observables(
    profile: Mapping[str, Any],
    branch_a: Mapping[str, Any],
    branch_b: Mapping[str, Any],
    transform: Mapping[str, Any],
    extraction: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    profile = _validated_profile(profile)
    assert profile is not None
    support_a = tuple(branch_a.get("public_argmax_set", ()))
    support_b = tuple(branch_b.get("public_argmax_set", ()))
    intersection = tuple(sorted(set(support_a) & set(support_b)))
    union = tuple(sorted(set(support_a) | set(support_b)))
    a_only = tuple(sorted(set(support_a) - set(support_b)))
    b_only = tuple(sorted(set(support_b) - set(support_a)))
    full_support = tuple(profile["full_public_argmax_set"])
    winner = full_support[0]
    transform_top = transform["ranking"][0] if transform.get("ranking") else None
    extracted = extraction.get("candidate_id") if isinstance(extraction, Mapping) else None
    parent_binding = transform.get("parent_artifact_sha256") == [
        branch_a.get("artifact_sha256"),
        branch_b.get("artifact_sha256"),
    ]
    extraction_binding = (
        isinstance(extraction, Mapping)
        and extraction.get("transform_artifact_sha256_consumed")
        == transform.get("artifact_sha256")
    )
    profile_valid = all(
        (
            branch_a.get("carrier_profile_id") == profile["profile_id"],
            branch_b.get("carrier_profile_id") == profile["profile_id"],
            list(support_a) == profile["public_argmax_sets"]["branch-a"],
            list(support_b) == profile["public_argmax_sets"]["branch-b"],
            len(full_support) == 1,
            2 <= len(support_a) <= 3,
            2 <= len(support_b) <= 3,
            support_a != support_b,
            bool(a_only),
            bool(b_only),
            branch_a.get("public_plateau_gap", 0) > 0,
            branch_b.get("public_plateau_gap", 0) > 0,
        )
    )
    if profile["eligibility_tier"] == 1:
        resolution_law_satisfied = intersection == full_support
        resolution_law = "tier-1-singleton-intersection"
    else:
        resolution_law_satisfied = (
            set(full_support) < set(intersection)
            and tuple(profile["joint_public_argmax_set"]) == full_support
            and all(profile["branch_exclusive_contribution"].values())
        )
        resolution_law = "tier-2-deduplicated-joint-score"
    output_recovers_resolution = transform_top == winner and extracted == winner
    uncertainty_reduced = all(
        (
            profile_valid,
            parent_binding,
            extraction_binding,
            resolution_law_satisfied,
            output_recovers_resolution,
        )
    )
    exclusive = tuple(sorted(set(a_only) | set(b_only)))
    return {
        "carrier_profile_valid": profile_valid,
        "eligibility_tier": profile["eligibility_tier"],
        "resolution_law": resolution_law,
        "resolution_law_satisfied": resolution_law_satisfied,
        "branch_support_sets_differ": support_a != support_b,
        "branch_support_intersection": list(intersection),
        "branch_support_union": list(union),
        "branch_a_exclusive_support": list(a_only),
        "branch_b_exclusive_support": list(b_only),
        "transform_consumed_both_branches": parent_binding,
        "extraction_consumed_transform": extraction_binding,
        "transform_top_candidate": transform_top,
        "unique_full_public_winner": winner,
        "transform_top_equals_full_public_winner": transform_top == winner,
        "extracted_candidate": extracted,
        "full_public_winner_recovered": output_recovers_resolution,
        "branch_exclusive_alternatives_suppressed_from_top": all(
            candidate_id != transform_top for candidate_id in exclusive
        ),
        "branch_exclusive_alternatives_absent_from_transform": all(
            candidate_id not in transform.get("ranking", []) for candidate_id in exclusive
        ),
        "uncertainty_before": {
            "branch_a_support_size": len(support_a),
            "branch_b_support_size": len(support_b),
            "support_union_size": len(union),
        },
        "uncertainty_after": {
            "resolved_support_size": 1 if uncertainty_reduced else len(union),
            "resolved_to_full_public_winner": uncertainty_reduced,
        },
        "relational_uncertainty_reduced": uncertainty_reduced,
    }


def _profile_diagnostics(observables: Mapping[str, Any]) -> list[str]:
    diagnostics = ["CARRIER_COMPLEMENTARITY_PRESENT", "BRANCH_SUPPORT_SETS_DIFFER"]
    diagnostics.append(
        "MODEL_BRANCH_RANKINGS_DIFFER"
        if observables.get("model_branch_rankings_differ") is True
        else "MODEL_BRANCH_RANKINGS_COLLAPSE"
    )
    diagnostics.append(
        "TIER_1_INTERSECTION_RESOLUTION"
        if observables.get("eligibility_tier") == 1
        else "TIER_2_JOINT_SCORE_RESOLUTION"
    )
    diagnostics.append(
        "RELATIONAL_UNCERTAINTY_REDUCED"
        if observables.get("relational_uncertainty_reduced") is True
        else "RELATIONAL_UNCERTAINTY_NOT_REDUCED"
    )
    diagnostics.append(
        "FULL_PUBLIC_WINNER_RECOVERED"
        if observables.get("full_public_winner_recovered") is True
        else "FULL_PUBLIC_WINNER_NOT_RECOVERED"
    )
    return diagnostics


def classify_kernel(
    branch_a: Mapping[str, Any] | None,
    branch_b: Mapping[str, Any] | None,
    transform: Mapping[str, Any] | None,
    extraction: Mapping[str, Any] | None,
    *,
    restoration_passed: bool,
    completed_request_count: int,
    profile: Mapping[str, Any] | None = None,
) -> str:
    profile = _validated_profile(profile)
    if (
        completed_request_count != 6
        or not restoration_passed
        or not all(isinstance(item, Mapping) for item in (branch_a, branch_b, transform, extraction))
    ):
        return "INCONCLUSIVE"
    assert branch_a is not None and branch_b is not None and transform is not None and extraction is not None
    if transform.get("parent_artifact_sha256") != [
        branch_a.get("artifact_sha256"),
        branch_b.get("artifact_sha256"),
    ] or extraction.get("transform_artifact_sha256_consumed") != transform.get("artifact_sha256"):
        return "INCONCLUSIVE"
    if profile is not None:
        observables = unresolved_relation_observables(
            profile,
            branch_a,
            branch_b,
            transform,
            extraction,
        )
        if observables["relational_uncertainty_reduced"] is True:
            return "CATALYTIC_KERNEL_VISIBLE"
        return "CATALYTIC_KERNEL_COLLAPSED"
    selected = extraction["candidate_id"]
    result_rank = transform["ranking"].index(selected) + 1
    selected_relation_changed = any(
        selected not in parent["ranking"] or parent["ranking"].index(selected) + 1 != result_rank
        for parent in (branch_a, branch_b)
    )
    if transform.get("identity_transform") is True or not selected_relation_changed:
        return "CATALYTIC_KERNEL_COLLAPSED"
    if any(transform.get("differs_from_parent", {}).values()):
        return "CATALYTIC_KERNEL_VISIBLE"
    return "CATALYTIC_KERNEL_COLLAPSED"


def build_parent_a_commitment_receipt(
    branch_a: Mapping[str, Any], profile: Mapping[str, Any]
) -> dict[str, Any]:
    profile = _validated_profile(profile)
    assert profile is not None
    if branch_a.get("artifact_id") != "branch-a" or branch_a.get(
        "artifact_sha256"
    ) != json_sha256(
        {key: value for key, value in branch_a.items() if key != "artifact_sha256"}
    ):
        raise CatalyticKernel0Error("Branch-A artifact binding is invalid")
    if branch_a.get("carrier_profile_id") != profile["profile_id"]:
        raise CatalyticKernel0Error("Branch-A carrier profile identity drift")
    receipt = {
        "artifact_id": "branch-a",
        "artifact_sha256": branch_a["artifact_sha256"],
        "carrier_profile_id": profile["profile_id"],
        "projection_mode": "commitment-only",
        "informative_content_withheld": True,
    }
    if set(receipt) != BLINDED_PARENT_RECEIPT_FIELDS:
        raise CatalyticKernel0Error("blinded Branch-A receipt field set changed")
    validate_metadata_only(receipt)
    return receipt


def validate_parent_a_information_deletion_projection(
    payload: Mapping[str, Any],
    *,
    carrier: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    profile = _validated_profile(carrier.get("profile"))
    _validated_control(PARENT_A_INFORMATION_DELETION_CONTROL, profile)
    if profile is None or not all(key in artifacts for key in ("branch-a", "branch-b")):
        raise CatalyticKernel0Error("control transform parents are incomplete")
    branch_a = artifacts["branch-a"]
    branch_b = artifacts["branch-b"]
    receipt = build_parent_a_commitment_receipt(branch_a, profile)
    messages = payload.get("messages")
    try:
        assignment = json.loads(messages[1]["content"])
    except (IndexError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise CatalyticKernel0Error("control transform assignment is invalid") from exc
    expected_keys = {"request_id", "instruction", "parent_artifacts"}
    parents = assignment.get("parent_artifacts")
    if (
        set(assignment) != expected_keys
        or assignment.get("request_id") != "transform"
        or assignment.get("instruction") != CONTROL_TRANSFORM_INSTRUCTION
        or not isinstance(parents, list)
        or len(parents) != 2
        or parents[0] != receipt
        or parents[1] != branch_b
    ):
        raise CatalyticKernel0Error("control transform projection differs from preregistration")
    if set(parents[0]) != BLINDED_PARENT_RECEIPT_FIELDS:
        raise CatalyticKernel0Error("Branch-A informative fields entered the control projection")
    winner = profile["full_public_argmax_set"][0]
    if winner in assignment["instruction"] or any(
        value == winner
        for key, value in parents[0].items()
        if key != "artifact_sha256"
    ):
        raise CatalyticKernel0Error("expected winner entered the blinded control projection")
    if branch_b.get("artifact_sha256") != json_sha256(
        {key: value for key, value in branch_b.items() if key != "artifact_sha256"}
    ):
        raise CatalyticKernel0Error("full Branch-B artifact binding changed")
    evidence = {
        "control_id": PARENT_A_INFORMATION_DELETION_CONTROL,
        "deleted_parent": "branch-a",
        "retained_informative_parent": "branch-b",
        "blinded_parent_receipt": receipt,
        "blinded_parent_receipt_sha256": json_sha256(receipt),
        "branch_a_artifact_sha256": branch_a["artifact_sha256"],
        "branch_b_artifact_sha256": branch_b["artifact_sha256"],
        "model_visible_parent_projection_sha256": json_sha256(parents),
        "branch_a_informative_content_withheld": True,
        "branch_b_full_artifact_unchanged": True,
        "neutral_instruction_verified": True,
        "projection_verified": True,
    }
    validate_metadata_only(evidence)
    return evidence


def classify_parent_a_information_control(
    branch_a: Mapping[str, Any] | None,
    branch_b: Mapping[str, Any] | None,
    transform: Mapping[str, Any] | None,
    extraction: Mapping[str, Any] | None,
    intervention: Mapping[str, Any] | None,
    *,
    restoration_passed: bool,
    completed_request_count: int,
    profile: Mapping[str, Any],
) -> str:
    profile = _validated_profile(profile)
    assert profile is not None
    if (
        completed_request_count != 6
        or not restoration_passed
        or not all(
            isinstance(item, Mapping)
            for item in (branch_a, branch_b, transform, extraction, intervention)
        )
    ):
        return "CAUSAL_CONTROL_INCONCLUSIVE"
    assert branch_a is not None
    assert branch_b is not None
    assert transform is not None
    assert extraction is not None
    assert intervention is not None
    if not all(
        (
            intervention.get("control_id") == PARENT_A_INFORMATION_DELETION_CONTROL,
            intervention.get("projection_verified") is True,
            intervention.get("branch_a_informative_content_withheld") is True,
            intervention.get("branch_b_full_artifact_unchanged") is True,
            intervention.get("branch_a_artifact_sha256")
            == branch_a.get("artifact_sha256"),
            intervention.get("branch_b_artifact_sha256")
            == branch_b.get("artifact_sha256"),
            transform.get("parent_artifact_sha256")
            == [branch_a.get("artifact_sha256"), branch_b.get("artifact_sha256")],
            extraction.get("transform_artifact_sha256_consumed")
            == transform.get("artifact_sha256"),
        )
    ):
        return "CAUSAL_CONTROL_INCONCLUSIVE"
    winner = profile["full_public_argmax_set"][0]
    score = extraction.get("all_public_score", {})
    fully_recovered = all(
        (
            transform.get("ranking", [None])[0] == winner,
            extraction.get("candidate_id") == winner,
            score.get("candidate_id") == winner,
            score.get("passed") == 5,
            score.get("total") == 5,
        )
    )
    return (
        "PARENT_A_INFORMATION_NOT_SHOWN_NECESSARY"
        if fully_recovered
        else "PARENT_A_INFORMATION_NECESSITY_SUPPORTED"
    )


def _assignment(
    request_id: str,
    *,
    carrier: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
    control: str | None = None,
) -> dict[str, Any]:
    profile = _validated_profile(carrier.get("profile"))
    control = _validated_control(control, profile)
    if request_id == "borrow":
        return {
            "request_id": request_id,
            "carrier_id": carrier["carrier_id"],
            "instruction": "Acknowledge the immutable carrier exactly.",
        }
    if request_id in BRANCH_SHARDS:
        instruction = "Rank one to three candidate programs using only this branch's public evidence shard."
        return {
            "request_id": request_id,
            "instruction": instruction,
            "evidence_shard": build_public_shard(request_id, profile),
        }
    if request_id == "transform":
        if control == PARENT_A_INFORMATION_DELETION_CONTROL:
            assert profile is not None
            return {
                "request_id": request_id,
                "instruction": CONTROL_TRANSFORM_INSTRUCTION,
                "parent_artifacts": [
                    build_parent_a_commitment_receipt(artifacts["branch-a"], profile),
                    artifacts["branch-b"],
                ],
            }
        return {
            "request_id": request_id,
            "instruction": "Reconcile the exact two normalized parent artifacts. Author only one allowed operator and one candidate ranking.",
            "parent_artifacts": [artifacts["branch-a"], artifacts["branch-b"]],
        }
    if request_id == "extract":
        return {
            "request_id": request_id,
            "instruction": "Select one candidate from the exact normalized transform ranking.",
            "transform_artifact": artifacts["transform"],
        }
    if request_id == "restore":
        return {
            "request_id": request_id,
            "carrier_id": carrier["carrier_id"],
            "instruction": "Acknowledge the original immutable carrier only.",
        }
    raise CatalyticKernel0Error("unknown request assignment")


def build_model_request(
    request_id: str,
    *,
    carrier: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
    control: str | None = None,
) -> dict[str, Any]:
    if request_id not in REQUEST_IDS:
        raise CatalyticKernel0Error("unknown kernel request")
    assignment = _assignment(
        request_id, carrier=carrier, artifacts=artifacts, control=control
    )
    payload = {
        "model": MODEL_ALIAS,
        "messages": [
            {"role": "system", "content": carrier["carrier_root"]},
            {"role": "user", "content": canonical_json_text(assignment)},
        ],
        "temperature": 0.0,
        "seed": int.from_bytes(hashlib.sha256(f"ck0:{request_id}".encode()).digest()[:4], "big"),
        "max_tokens": 64,
        "stream": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": f"ck0_{request_id.replace('-', '_')}",
                "strict": True,
                "schema": response_schema(
                    request_id,
                    carrier_id=str(carrier["carrier_id"]),
                ),
            },
        },
        "stream_options": {"include_usage": True},
        "cache_prompt": True,
        "return_tokens": True,
        "return_progress": True,
        "verbose": True,
    }
    validate_model_request(
        request_id,
        payload,
        carrier=carrier,
        artifacts=artifacts,
        control=control,
    )
    return payload


def _reject_private_prompt_fields(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in FORBIDDEN_PRIVATE_FIELDS:
                raise CatalyticKernel0Error("protected task material entered a model request")
            _reject_private_prompt_fields(item)
    elif isinstance(value, list):
        for item in value:
            _reject_private_prompt_fields(item)


def validate_model_request(
    request_id: str,
    payload: Mapping[str, Any],
    *,
    carrier: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
    control: str | None = None,
) -> None:
    if not _carrier_is_pristine(carrier):
        raise CatalyticKernel0Error("model request carrier is not the exact public-only root")
    messages = payload.get("messages")
    if not isinstance(messages, list) or len(messages) != 2 or messages[0] != {
        "role": "system",
        "content": carrier["carrier_root"],
    }:
        raise CatalyticKernel0Error("model request changed the immutable carrier root")
    expected = _assignment(
        request_id, carrier=carrier, artifacts=artifacts, control=control
    )
    try:
        actual = json.loads(messages[1]["content"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise CatalyticKernel0Error("model request assignment is invalid") from exc
    if actual != expected:
        raise CatalyticKernel0Error("model request assignment differs from its exact projection")
    if request_id == "branch-b" and "disagree" in messages[1]["content"].casefold():
        raise CatalyticKernel0Error("branch B was forced to disagree")
    if request_id == "restore" and set(actual) != {"request_id", "carrier_id", "instruction"}:
        raise CatalyticKernel0Error("restore request contains branch state")
    if payload.get("chat_template_kwargs") != {"enable_thinking": False}:
        raise CatalyticKernel0Error("kernel requests must remain thinking-disabled")
    if (
        request_id == "transform"
        and control == PARENT_A_INFORMATION_DELETION_CONTROL
    ):
        validate_parent_a_information_deletion_projection(
            payload,
            carrier=carrier,
            artifacts=artifacts,
        )
    _reject_private_prompt_fields(payload)
    validate_metadata_only(expected)


def validate_parent_a_control_preregistration(
    repository: Path,
    *,
    run_id: str,
    carrier: Mapping[str, Any],
) -> dict[str, Any]:
    path = repository / PARENT_A_CONTROL_PREREGISTRATION
    if not path.is_file() or path.is_symlink():
        raise CatalyticKernel0Error("control preregistration is missing or unsafe")
    raw = path.read_bytes()
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CatalyticKernel0Error("control preregistration is invalid JSON") from exc
    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "preregistered",
    }:
        raise CatalyticKernel0Error(
            "control preregistration must remain pre-execution only"
        )
    preregistered = document.get("preregistered")
    if not isinstance(preregistered, dict):
        raise CatalyticKernel0Error("control preregistration body is invalid")
    profile = _validated_profile(carrier.get("profile"))
    assert profile is not None
    expected_requests = [
        {
            "max_tokens": 64,
            "ordinal": ordinal,
            "request_id": request_id,
            "response_schema": response_schema(
                request_id, carrier_id=str(carrier["carrier_id"])
            ),
            "seed": int.from_bytes(
                hashlib.sha256(f"ck0:{request_id}".encode()).digest()[:4],
                "big",
            ),
        }
        for ordinal, request_id in enumerate(REQUEST_IDS, 1)
    ]
    frozen_carrier = preregistered.get("frozen_carrier")
    transform_projection = preregistered.get("transform_projection")
    deletion_direction = preregistered.get("deletion_direction")
    classifications = preregistered.get("control_classifications")
    expected_receipt_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "artifact_id",
            "artifact_sha256",
            "carrier_profile_id",
            "projection_mode",
            "informative_content_withheld",
        ],
        "properties": {
            "artifact_id": {"const": "branch-a", "type": "string"},
            "artifact_sha256": {
                "pattern": "^[0-9A-F]{64}$",
                "type": "string",
            },
            "carrier_profile_id": {
                "const": UNRESOLVED_PROFILE_ID,
                "type": "string",
            },
            "projection_mode": {"const": "commitment-only", "type": "string"},
            "informative_content_withheld": {"const": True, "type": "boolean"},
        },
    }
    expected_references = {
        "discovery": {
            "closure_sha256": "34825DE4069B63E5A03E380A9580926EEFFE4746611FADC49757524CF3EA6B4D",
            "manifest_sha256": "CA4B5781F9023380AA218E6E881F98706A2077BB420359095E0C0C2043FEF389",
            "result_sha256": "EB6BA8376D2B594D31A86478BC409E7EB4734C5AF3B6082F6292721B26BDFD4B",
            "run_id": "ck0-20260714T002941Z-a3",
        },
        "replication": {
            "artifact_sha256": "1CEF59F1C19774568AAD0910622BA4C53E216A9FE3FBFA8F7EF2D571505F7234",
            "closure_sha256": "58B0A40BD676D008A8D25098435F4B8E26E485BE0595AB9FE8E93F3FA1029925",
            "manifest_sha256": "D72BD718D5E6798DA065342C717963AF0797CF48AEE69AE32DC4EA19AC46BFA3",
            "preregistered_sha256": "6BAA531FA1DF58FB22FCD6ED7A7052E90E5B85ED749C5D0C282BA8E6FB8BCA6D",
            "result_sha256": "A4353263BDDDE0FC7A7A8CBDEA47C3224448919D56E1B15D18AE530D98C6A3FD",
            "run_id": "ck0-20260714T005256Z-a4",
        },
    }
    if not all(
        (
            document.get("schema_version") == 1,
            preregistered.get("schema_version") == 1,
            preregistered.get("status") == "preregistered",
            preregistered.get("starting_protected_main")
            == PARENT_A_CONTROL_STARTING_MAIN,
            preregistered.get("frozen_implementation_sha")
            == PARENT_A_CONTROL_FROZEN_IMPLEMENTATION,
            preregistered.get("execution_run_id") == PARENT_A_CONTROL_RUN_ID,
            run_id == PARENT_A_CONTROL_RUN_ID,
            preregistered.get("authorized_invocations") == 1,
            preregistered.get("retry_count") == 0,
            preregistered.get("request_sequence") == expected_requests,
            isinstance(frozen_carrier, Mapping),
            frozen_carrier.get("profile_id") == profile["profile_id"],
            frozen_carrier.get("task_id") == profile["task_id"],
            frozen_carrier.get("scan_sha256") == profile["scan_sha256"],
            frozen_carrier.get("public_score_matrix_sha256")
            == profile["public_score_matrix_sha256"],
            frozen_carrier.get("carrier_content_sha256")
            == carrier["carrier_content_sha256"],
            frozen_carrier.get("carrier_root_sha256")
            == carrier["carrier_root_sha256"],
            isinstance(deletion_direction, Mapping),
            deletion_direction.get("deleted_parent") == "branch-a",
            deletion_direction.get("retained_informative_parent") == "branch-b",
            deletion_direction.get("frozen_before_output") is True,
            isinstance(transform_projection, Mapping),
            transform_projection.get("instruction")
            == CONTROL_TRANSFORM_INSTRUCTION,
            transform_projection.get("blinded_branch_a_receipt_schema")
            == expected_receipt_schema,
            transform_projection.get("ordinary_mechanism_classifier_applied")
            is False,
            isinstance(classifications, Mapping),
            set(classifications) == set(PARENT_A_CONTROL_CLASSIFICATIONS),
            preregistered.get("reference_runs") == expected_references,
        )
    ):
        raise CatalyticKernel0Error("control preregistration identity drift")
    for reference in expected_references.values():
        run_root = repository / "state" / "catalytic_kernel_0" / reference["run_id"]
        for filename in ("manifest.json", "result.json", "closure.json"):
            expected_hash = reference[f"{filename.removesuffix('.json')}_sha256"]
            evidence_path = run_root / filename
            if (
                not evidence_path.is_file()
                or evidence_path.is_symlink()
                or sha256_bytes(evidence_path.read_bytes()) != expected_hash
            ):
                raise CatalyticKernel0Error("frozen CK0 reference evidence changed")
    replication_artifact = repository / "lab" / "ck0_unresolved_replication_1.json"
    if (
        not replication_artifact.is_file()
        or replication_artifact.is_symlink()
        or sha256_bytes(replication_artifact.read_bytes())
        != expected_references["replication"]["artifact_sha256"]
    ):
        raise CatalyticKernel0Error("frozen CK0 replication artifact changed")
    projection = {
        "relative_path": PARENT_A_CONTROL_PREREGISTRATION,
        "artifact_sha256": sha256_bytes(raw),
        "preregistered_sha256": json_sha256(preregistered),
        "execution_run_id": run_id,
        "status": "validated-preregistered",
    }
    validate_metadata_only(projection)
    return projection


def _common_prefix(left: Sequence[int], right: Sequence[int]) -> int:
    count = 0
    for a, b in zip(left, right):
        if a != b:
            break
        count += 1
    return count


def _terminal_identity(tokens: Sequence[int], terminal: int) -> str:
    if terminal <= 0 or terminal >= len(tokens):
        raise CatalyticKernel0Error("carrier terminal token index is out of bounds")
    return json_sha256(list(tokens[: terminal + 1]))


def _resource_breach(value: Mapping[str, Any]) -> bool:
    if value.get("observation_state") != "measured":
        return False
    host_breach = (
        isinstance(value.get("host_private_bytes"), int)
        and value.get("host_private_ceiling_exceeded") is True
    )
    wddm_breach = (
        isinstance(value.get("wddm_peak_bytes"), int)
        and value.get("wddm_ceiling_exceeded") is True
    )
    return host_breach or wddm_breach


def _resource_observation(adapter: KernelAdapter, sidecar: Any, boundary: str) -> dict[str, Any]:
    try:
        value = dict(adapter.resource_summary(sidecar=sidecar, boundary=boundary))
    except BaseException as exc:
        value = {"boundary": boundary, "observation_state": "observation-error", **_safe_failure(exc, boundary=boundary)}
    validate_metadata_only(value)
    return value


def _lease_accounting(pool: Any) -> dict[str, int]:
    return {
        "physical_slots": 1,
        "lease_count": int(getattr(pool, "lease_count", 0)),
        "active_leases": int(getattr(pool, "active_count", 0)),
        "maximum_concurrent_leases": int(getattr(pool, "max_concurrent", 0)),
    }


def _result_projection(
    *,
    run_id: str,
    implementation_sha: str | None,
    carrier: Mapping[str, Any],
    preflight: Mapping[str, Any],
    cib0_snapshot: Mapping[str, Any],
    ck0_snapshot: Mapping[str, Any],
    readiness: Mapping[str, Any] | None,
    outcomes: Sequence[Mapping[str, Any]],
    artifacts: Mapping[str, Mapping[str, Any]],
    completed_responses: int,
    cleanup: Mapping[str, Any],
    postflight: Mapping[str, Any],
    lease: Mapping[str, Any],
    restoration: Mapping[str, Any] | None,
    failure: Mapping[str, Any] | None,
    control: str | None = None,
    control_intervention: Mapping[str, Any] | None = None,
    control_preregistration: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    profile = _validated_profile(carrier.get("profile"))
    control = _validated_control(control, profile)
    classification = None
    control_classification = None
    if control == PARENT_A_INFORMATION_DELETION_CONTROL:
        assert profile is not None
        control_classification = classify_parent_a_information_control(
            artifacts.get("branch-a"),
            artifacts.get("branch-b"),
            artifacts.get("transform"),
            artifacts.get("extract"),
            control_intervention,
            restoration_passed=isinstance(restoration, Mapping)
            and restoration.get("passed") is True,
            completed_request_count=len(outcomes),
            profile=profile,
        )
    else:
        classification = classify_kernel(
            artifacts.get("branch-a"),
            artifacts.get("branch-b"),
            artifacts.get("transform"),
            artifacts.get("extract"),
            restoration_passed=isinstance(restoration, Mapping)
            and restoration.get("passed") is True,
            completed_request_count=len(outcomes),
            profile=profile,
        )
    complete = len(outcomes) == 6 and completed_responses == 6 and failure is None
    terminal_classification = control_classification or classification
    inconclusive = (
        "CAUSAL_CONTROL_INCONCLUSIVE"
        if control is not None
        else "INCONCLUSIVE"
    )
    status = (
        "complete"
        if complete and terminal_classification != inconclusive
        else "failed"
    )
    branch_relation = None
    relational_observables = None
    diagnostics = None
    if "branch-a" in artifacts and "branch-b" in artifacts:
        branch_relation = {
            "rankings_differ": artifacts["branch-a"]["ranking"] != artifacts["branch-b"]["ranking"],
            "shared_example_consistency": shared_example_consistency(artifacts["branch-a"], artifacts["branch-b"]),
        }
    if (
        profile is not None
        and control is None
        and all(key in artifacts for key in ("branch-a", "branch-b", "transform"))
    ):
        relational_observables = unresolved_relation_observables(
            profile,
            artifacts["branch-a"],
            artifacts["branch-b"],
            artifacts["transform"],
            artifacts.get("extract"),
        )
        relational_observables["model_branch_rankings_differ"] = (
            artifacts["branch-a"]["ranking"] != artifacts["branch-b"]["ranking"]
        )
        diagnostics = _profile_diagnostics(relational_observables)
    carrier_projection = {
        "carrier_id": carrier["carrier_id"],
        "carrier_content_sha256": carrier["carrier_content_sha256"],
        "carrier_root_sha256": carrier["carrier_root_sha256"],
    }
    if profile is not None:
        carrier_projection["profile"] = dict(carrier["profile"])
    result = {
        "schema_version": STATE_SCHEMA_VERSION,
        "kernel_id": KERNEL_ID,
        "run_id": run_id,
        "implementation_sha": implementation_sha,
        "status": status,
        "mechanism_classification": (
            classification
            if status == "complete" and control is None
            else "INCONCLUSIVE"
            if control is None
            else None
        ),
        "carrier": carrier_projection,
        "historical_cib0": dict(cib0_snapshot),
        "historical_ck0": dict(ck0_snapshot),
        "preflight": dict(preflight),
        "readiness": dict(readiness) if isinstance(readiness, Mapping) else None,
        "request_count_required": 6,
        "completed_model_responses": completed_responses,
        "request_outcomes": [dict(item) for item in outcomes],
        "branch_relation": branch_relation,
        "carrier_suitability": dict(carrier["profile"]) if profile is not None else None,
        "relational_observables": relational_observables,
        "diagnostics": diagnostics,
        "branch_a": artifacts.get("branch-a"),
        "branch_b": artifacts.get("branch-b"),
        "transform": artifacts.get("transform"),
        "extraction": artifacts.get("extract"),
        "restoration": dict(restoration) if isinstance(restoration, Mapping) else None,
        "lease_accounting": dict(lease),
        "cleanup": dict(cleanup),
        "postflight_custody": dict(postflight),
        "failure": dict(failure) if isinstance(failure, Mapping) else None,
        "persistence_mode": "bounded-normalized-metadata-only",
        "transport_retention": "none",
        "claims": dict(CLAIMS),
        "claiming": False,
        "automatic_promotion": False,
    }
    if control is not None:
        result.update(
            {
                "control_mode": control,
                "control_classification": (
                    control_classification
                    if status == "complete"
                    else "CAUSAL_CONTROL_INCONCLUSIVE"
                ),
                "control_intervention": (
                    dict(control_intervention)
                    if isinstance(control_intervention, Mapping)
                    else None
                ),
                "control_preregistration": (
                    dict(control_preregistration)
                    if isinstance(control_preregistration, Mapping)
                    else None
                ),
                "non_production": True,
            }
        )
    validate_metadata_only(result)
    return result


def run_catalytic_kernel_0(
    args: Any,
    *,
    adapter: KernelAdapter | None = None,
    repository_root: str | os.PathLike[str] | None = None,
    state_root: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    run_id = validate_run_id(_arg(args, "run_id"))
    requested_profile = _arg(args, "carrier_profile")
    if requested_profile not in {None, UNRESOLVED_PROFILE_ID}:
        raise CatalyticKernel0Error("unknown or unauthorized carrier profile")
    profile = (
        selected_unresolved_public_profile()
        if requested_profile == UNRESOLVED_PROFILE_ID
        else None
    )
    control = _validated_control(_arg(args, "control"), profile)
    repository = Path(repository_root).resolve() if repository_root is not None else Path(__file__).resolve().parents[1]
    state_base = Path(state_root).resolve() if state_root is not None else repository / "state" / "catalytic_kernel_0"
    run_root = state_base / run_id
    try:
        run_root.relative_to(repository)
    except ValueError as exc:
        raise CatalyticKernel0Error("kernel state must remain below the repository") from exc
    if run_root.exists():
        raise CatalyticKernel0Error("kernel run ID already exists")
    carrier = build_carrier(profile)
    control_preregistration = (
        validate_parent_a_control_preregistration(
            repository,
            run_id=run_id,
            carrier=carrier,
        )
        if control == PARENT_A_INFORMATION_DELETION_CONTROL
        else None
    )
    cib0_before = _snapshot_tree(repository / "state" / "catalytic_inference_bench_0")
    ck0_before = _snapshot_historical_ck0(repository / "state" / "catalytic_kernel_0")
    paths = {name: run_root / name for name in STATE_FILENAMES}
    live = adapter if adapter is not None else CatalyticKernel0Adapter(repository)
    preflight_full = live.preflight(
        args=args,
        repository_root=repository,
        run_root=run_root,
        allowed_paths=tuple(paths.values()),
    )
    preflight = _public_preflight(preflight_full)
    run_root.mkdir(parents=True)
    lock_fd = os.open(paths["run.lock"], os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(lock_fd, (run_id + "\n").encode("ascii"))
    os.fsync(lock_fd)
    os.close(lock_fd)
    manifest = {
        "schema_version": STATE_SCHEMA_VERSION,
        "kernel_id": KERNEL_ID,
        "run_id": run_id,
        "task_id": TASK_ID if profile is None else profile["task_id"],
        "carrier_id": carrier["carrier_id"],
        "carrier_content_sha256": carrier["carrier_content_sha256"],
        "carrier_root_sha256": carrier["carrier_root_sha256"],
        "task_suite_sha256": EXPECTED_SUITE_SHA256,
        "request_ids": list(REQUEST_IDS),
        "physical_slots": 1,
        "historical_cib0_tree_sha256": cib0_before["tree_sha256"],
        "historical_ck0_tree_sha256": ck0_before["tree_sha256"],
        "preflight": preflight,
        "claims": dict(CLAIMS),
        "claiming": False,
        "automatic_promotion": False,
    }
    if profile is not None:
        manifest["carrier_profile"] = dict(carrier["profile"])
    if control is not None:
        manifest["control"] = {
            "control_id": control,
            "deleted_parent": "branch-a",
            "retained_informative_parent": "branch-b",
            "ordinary_mechanism_classifier_applied": False,
        }
        manifest["control_preregistration"] = dict(control_preregistration)
    _atomic_json(paths["manifest.json"], manifest)

    pool = live.create_lease_pool(1)
    sidecar: Any | None = None
    readiness: Mapping[str, Any] | None = None
    artifacts: dict[str, dict[str, Any]] = {}
    outcomes: list[dict[str, Any]] = []
    completed_responses = 0
    cleanup: Mapping[str, Any] = {"passed": False}
    postflight: Mapping[str, Any] = {"passed": False}
    failure: Mapping[str, Any] | None = None
    restoration: Mapping[str, Any] | None = None
    control_intervention: Mapping[str, Any] | None = None
    warm_tokens: list[int] | None = None
    warm_terminal: int | None = None
    warm_terminal_identity: str | None = None
    restore_terminal: int | None = None
    restore_terminal_identity: str | None = None
    restore_cache_admitted = False
    current_request: str | None = None
    current_outcome: dict[str, Any] | None = None

    try:
        sidecar, readiness = live.launch_sidecar(preflight=preflight_full, run_id=run_id)
        for ordinal, request_id in enumerate(REQUEST_IDS, 1):
            current_request = request_id
            current_outcome = {
                "request_id": request_id,
                "ordinal": ordinal,
                "status": "started",
                "model_response_completed": False,
                "physical_slot": PHYSICAL_SLOT,
            }
            payload = build_model_request(
                request_id,
                carrier=carrier,
                artifacts=artifacts,
                control=control,
            )
            if (
                request_id == "transform"
                and control == PARENT_A_INFORMATION_DELETION_CONTROL
            ):
                control_intervention = (
                    validate_parent_a_information_deletion_projection(
                        payload,
                        carrier=carrier,
                        artifacts=artifacts,
                    )
                )
            geometry = live.prompt_geometry(sidecar=sidecar, payload=payload)
            token_ids = list(geometry["token_ids"])
            terminal = int(geometry["public_root_terminal_token_index"])
            terminal_identity = _terminal_identity(token_ids, terminal)
            if request_id == "borrow":
                warm_tokens = token_ids
                warm_terminal = terminal
                warm_terminal_identity = terminal_identity
            elif warm_tokens is None or terminal != warm_terminal or terminal_identity != warm_terminal_identity:
                raise CatalyticKernel0Error("carrier root-terminal identity drifted")
            common_prefix = len(token_ids) if request_id == "borrow" else _common_prefix(warm_tokens, token_ids)
            before_custody = dict(
                live.boundary_custody(
                    preflight=preflight_full,
                    sidecar=sidecar,
                    boundary=f"before:{request_id}",
                )
            )
            before_resource = _resource_observation(live, sidecar, f"before:{request_id}")
            if before_custody.get("passed") is not True or _resource_breach(before_resource):
                raise CatalyticKernel0Error("pre-request custody or measured resource ceiling failed")
            request = KernelRequest(request_id=request_id, ordinal=ordinal)
            with pool.lease() as lease_id:
                if lease_id != PHYSICAL_SLOT:
                    raise CatalyticKernel0Error("one-slot pool returned a nonzero lease")
                execution = live.execute_request(sidecar=sidecar, payload=payload, request=request)
            completed_responses += 1
            current_outcome["model_response_completed"] = True
            after_resource = _resource_observation(live, sidecar, f"after:{request_id}")
            after_custody = dict(
                live.boundary_custody(
                    preflight=preflight_full,
                    sidecar=sidecar,
                    boundary=f"after:{request_id}",
                )
            )
            if after_custody.get("passed") is not True or _resource_breach(after_resource):
                raise CatalyticKernel0Error("post-request custody or measured resource ceiling failed")
            transport = _normalized_transport(execution, rendered_tokens=len(token_ids), max_tokens=64)
            structured = parse_response(
                request_id,
                transport["structured_content"],
                transform_artifact=artifacts.get("transform"),
                profile=profile,
                carrier_id=carrier["carrier_id"],
            )
            if request_id in BRANCH_SHARDS:
                artifacts[request_id] = normalize_branch(
                    request_id,
                    structured["ranking"],
                    profile,
                )
            elif request_id == "transform":
                artifacts[request_id] = normalize_transform(
                    artifacts["branch-a"],
                    artifacts["branch-b"],
                    operator=structured["operator"],
                    ranking=structured["ranking"],
                    profile=profile,
                )
            elif request_id == "extract":
                artifacts[request_id] = normalize_extraction(
                    structured["candidate_id"], artifacts["transform"], profile
                )
            if request_id == "borrow":
                cache_admission = {
                    "classification": "carrier-root-warmed",
                    "admitted": True,
                    "reasons": ["borrow established the immutable process-local root"],
                }
            else:
                cache_admission = adjudicate_root_cache(
                    RootCacheObservation(
                        public_root_terminal_token_index=terminal,
                        common_prefix_tokens=common_prefix,
                        legacy_required_cached_prompt_tokens=common_prefix,
                        actual_cached_prompt_tokens=transport["metadata"]["cached_prompt_tokens"],
                        branch_prompt_tokens=transport["metadata"]["prompt_tokens"],
                        fresh_prompt_tokens=transport["metadata"]["fresh_prompt_tokens"],
                        completion_tokens=transport["metadata"]["completion_tokens"],
                        response_completed=True,
                        transport_passed=True,
                        token_evidence_passed=True,
                    )
                ).to_dict()
            cache_admitted = cache_admission["admitted"] is True
            if request_id != "borrow" and not cache_admitted:
                raise CatalyticKernel0Error("exact carrier-root cache admission failed")
            if request_id == "restore":
                restore_terminal = terminal
                restore_terminal_identity = terminal_identity
                restore_cache_admitted = cache_admitted
            current_outcome.update(
                {
                    "status": "accepted",
                    "model_request_sha256": json_sha256(payload),
                    "normalized_artifact_sha256": artifacts.get(request_id, {}).get("artifact_sha256"),
                    "transport": transport["metadata"],
                    "cache": {
                        "required": request_id != "borrow",
                        "admitted": cache_admitted,
                        "carrier_terminal_token_index": terminal,
                        "carrier_terminal_identity_sha256": terminal_identity,
                        "common_prefix_tokens": common_prefix,
                        "admission_law": cache_admission,
                    },
                    "custody": {"before": before_custody, "after": after_custody},
                    "resources": {"before": before_resource, "after": after_resource},
                }
            )
            outcomes.append(current_outcome)
            current_outcome = None
    except BaseException as exc:
        failure = _safe_failure(exc, boundary=current_request or "runtime")
        if current_outcome is not None:
            current_outcome["status"] = "rejected"
            current_outcome["failure"] = dict(failure)
            outcomes.append(current_outcome)
            current_outcome = None
    finally:
        try:
            cleanup = dict(live.cleanup(sidecar=sidecar, preflight=preflight_full))
        except BaseException as exc:
            cleanup = {"passed": False, "failure": _safe_failure(exc, boundary="cleanup")}
            failure = failure or cleanup["failure"]
        try:
            postflight = dict(live.postflight(preflight=preflight_full))
        except BaseException as exc:
            postflight = {"passed": False, "failure": _safe_failure(exc, boundary="postflight")}
            failure = failure or postflight["failure"]

    lease = _lease_accounting(pool)
    cib0_after = _snapshot_tree(repository / "state" / "catalytic_inference_bench_0")
    ck0_after = _snapshot_historical_ck0(repository / "state" / "catalytic_kernel_0")
    cib0_preserved = cib0_after == cib0_before
    ck0_preserved = ck0_after == ck0_before
    if not cib0_preserved:
        failure = failure or _safe_failure(
            CatalyticKernel0Error("historical CIB0 evidence changed"),
            boundary="historical-cib0",
        )
    if not ck0_preserved:
        failure = failure or _safe_failure(
            CatalyticKernel0Error("historical CK0 evidence changed"),
            boundary="historical-ck0",
        )
    if completed_responses == 6 and outcomes and outcomes[-1].get("request_id") == "restore":
        restoration_body = {
            "carrier_id_before": carrier["carrier_id"],
            "carrier_id_after": carrier["carrier_id"],
            "carrier_root_sha256_before": carrier["carrier_root_sha256"],
            "carrier_root_sha256_after": carrier["carrier_root_sha256"],
            "carrier_terminal_token_index_before": warm_terminal,
            "carrier_terminal_token_index_after": restore_terminal,
            "carrier_terminal_identity_sha256_before": warm_terminal_identity,
            "carrier_terminal_identity_sha256_after": restore_terminal_identity,
            "cache_root_reuse_admitted": restore_cache_admitted,
            "branch_state_absent_from_carrier": _carrier_is_pristine(carrier),
            "active_leases": lease["active_leases"],
            "lease_count": lease["lease_count"],
            "maximum_concurrent_leases": lease["maximum_concurrent_leases"],
            "sidecar_cleanup_passed": cleanup.get("passed") is True,
            "sidecar_port_free": cleanup.get("port_free") is True,
            "stable_preserved": cleanup.get("stable_preserved") is True,
            "candidate_preserved": (
                postflight.get("passed") is True
                and isinstance(postflight.get("candidate_head"), str)
                and isinstance(postflight.get("candidate_status_sha256"), str)
            ),
            "historical_cib0_preserved": cib0_preserved,
            "historical_ck0_preserved": ck0_preserved,
        }
        restoration = {
            **restoration_body,
            "passed": all(
                (
                    restoration_body["carrier_id_before"] == restoration_body["carrier_id_after"],
                    restoration_body["carrier_root_sha256_before"] == restoration_body["carrier_root_sha256_after"],
                    restoration_body["carrier_terminal_token_index_before"] == restoration_body["carrier_terminal_token_index_after"],
                    restoration_body["carrier_terminal_identity_sha256_before"] == restoration_body["carrier_terminal_identity_sha256_after"],
                    restoration_body["cache_root_reuse_admitted"],
                    restoration_body["branch_state_absent_from_carrier"],
                    restoration_body["active_leases"] == 0,
                    restoration_body["lease_count"] == 6,
                    restoration_body["maximum_concurrent_leases"] == 1,
                    restoration_body["sidecar_cleanup_passed"],
                    restoration_body["sidecar_port_free"],
                    restoration_body["stable_preserved"],
                    restoration_body["candidate_preserved"],
                    restoration_body["historical_cib0_preserved"],
                    restoration_body["historical_ck0_preserved"],
                )
            ),
            "receipt_sha256": json_sha256(restoration_body),
        }
        if restoration["passed"] is not True:
            failure = failure or _safe_failure(
                CatalyticKernel0Error("trusted carrier restoration did not pass"),
                boundary="restore",
            )

    implementation_sha = preflight.get("stable", {}).get("head") if isinstance(preflight.get("stable"), Mapping) else None
    result = _result_projection(
        run_id=run_id,
        implementation_sha=implementation_sha,
        carrier=carrier,
        preflight=preflight,
        cib0_snapshot=cib0_before,
        ck0_snapshot=ck0_before,
        readiness=readiness,
        outcomes=outcomes,
        artifacts=artifacts,
        completed_responses=completed_responses,
        cleanup=cleanup,
        postflight=postflight,
        lease=lease,
        restoration=restoration,
        failure=failure,
        control=control,
        control_intervention=control_intervention,
        control_preregistration=control_preregistration,
    )
    _atomic_json(paths["result.json"], result)
    if paths["run.lock"].exists():
        paths["run.lock"].unlink()
    try:
        final_postflight = dict(live.postflight(preflight=preflight_full))
        if final_postflight.get("passed") is not True:
            raise CatalyticKernel0Error("final custody did not pass")
        if _snapshot_tree(repository / "state" / "catalytic_inference_bench_0") != cib0_before:
            raise CatalyticKernel0Error("historical CIB0 evidence changed at closure")
        if _snapshot_historical_ck0(repository / "state" / "catalytic_kernel_0") != ck0_before:
            raise CatalyticKernel0Error("historical CK0 evidence changed at closure")
    except BaseException as exc:
        result["status"] = "failed"
        result["mechanism_classification"] = "INCONCLUSIVE"
        result["failure"] = _safe_failure(exc, boundary="final-postflight")
        _atomic_json(paths["result.json"], result)
        final_postflight = {"passed": False, "failure": result["failure"]}
    closure_body = {
        "schema_version": STATE_SCHEMA_VERSION,
        "run_id": run_id,
        "manifest_sha256": sha256_bytes(paths["manifest.json"].read_bytes()),
        "result_sha256": sha256_bytes(paths["result.json"].read_bytes()),
        "run_lock_absent": not paths["run.lock"].exists(),
        "terminal_custody": final_postflight,
        "historical_cib0_tree_sha256": cib0_before["tree_sha256"],
        "historical_ck0_tree_sha256": ck0_before["tree_sha256"],
    }
    if control_preregistration is not None:
        closure_body["control_preregistered_sha256"] = control_preregistration[
            "preregistered_sha256"
        ]
    _atomic_json(paths["closure.json"], closure_body)
    return result


__all__ = [
    "ALLOWED_OPERATORS",
    "BRANCH_SHARDS",
    "CARRIER_ID",
    "PARENT_A_CONTROL_CLASSIFICATIONS",
    "PARENT_A_INFORMATION_DELETION_CONTROL",
    "PARENT_A_CONTROL_RUN_ID",
    "CatalyticKernel0Error",
    "KERNEL_ID",
    "REQUEST_IDS",
    "build_carrier",
    "build_parent_a_commitment_receipt",
    "build_model_request",
    "build_public_shard",
    "classify_kernel",
    "classify_parent_a_information_control",
    "derive_rank_delta",
    "normalize_branch",
    "normalize_extraction",
    "normalize_transform",
    "parse_response",
    "response_schema",
    "run_catalytic_kernel_0",
    "shared_example_consistency",
    "validate_model_request",
    "validate_parent_a_information_deletion_projection",
    "validate_parent_a_control_preregistration",
]
