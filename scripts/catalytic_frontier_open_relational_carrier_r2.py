#!/usr/bin/env python3
"""Build, statically audit, and execute neo-exp-0079 exactly once.

The primary CUDA route composes F: X -> Y and G: Y -> Z without exposing a
Y pointer or storing Y outside registers.  The matched control writes the
same Y to global memory, transfers every Y byte to pinned host memory, reads
the representation without branching on its value, transfers it back
unchanged, and then applies the same G.

Compilation and static audit are pre-science checks.  Only --execute-once
launches the experiment binary and consumes the preregistered identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "neo-exp-0079"
ATTEMPT_ID = "frontier-attempt-0106"
SCHEMA_VERSION = "neo-open-relational-carrier-r2-v1"
CUDA_ARCH = "sm_86"
BATCH_CARRIERS = 1_048_576
LANES_PER_CARRIER = 4
BYTES_PER_LANE = 8
BOUNDARY_BYTES = BATCH_CARRIERS * LANES_PER_CARRIER * BYTES_PER_LANE
WARMUPS = 2
REPETITIONS = 9
MINIMUM_WALL_SPEEDUP = 1.25
STABLE_URL = "http://127.0.0.1:9292/health"
FRONTIER_PORT = 9494

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "cuda_open_relational_carrier_r2.cu"
BUILD_DIR = ROOT / "tmp" / EXPERIMENT_ID
EXECUTABLE = BUILD_DIR / "open_relational_carrier_r2.exe"
PTX = BUILD_DIR / "open_relational_carrier_r2.ptx"
CUBIN = BUILD_DIR / "open_relational_carrier_r2.cubin"
SASS = BUILD_DIR / "open_relational_carrier_r2.sass"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def run(
    command: list[str],
    *,
    check: bool = True,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def find_program(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"required program is unavailable: {name}")
    return path


def find_msvc_compiler_directory() -> str | None:
    if os.name != "nt":
        return None
    path_cl = shutil.which("cl")
    if path_cl is not None:
        return str(Path(path_cl).resolve().parent)
    program_files_x86 = os.environ.get(
        "ProgramFiles(x86)", r"C:\Program Files (x86)"
    )
    roots = (
        Path(program_files_x86)
        / "Microsoft Visual Studio"
        / "2022"
    )
    candidates = sorted(
        roots.glob(
            "*/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe"
        ),
        reverse=True,
    )
    if not candidates:
        raise RuntimeError("MSVC x64 compiler is unavailable for nvcc")
    return str(candidates[0].parent)


def extract_ptx_entry(ptx_text: str, entry: str) -> str:
    marker = f".entry {entry}("
    start = ptx_text.find(marker)
    if start < 0:
        raise RuntimeError(f"PTX entry missing: {entry}")
    next_entry = ptx_text.find(".entry ", start + len(marker))
    return ptx_text[start:] if next_entry < 0 else ptx_text[start:next_entry]


def compile_and_audit() -> dict[str, Any]:
    nvcc = find_program("nvcc")
    cuobjdump = find_program("cuobjdump")
    msvc_compiler_directory = find_msvc_compiler_directory()
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    common = [
        nvcc,
        str(SOURCE),
        "-std=c++17",
        "-O3",
        f"-arch={CUDA_ARCH}",
        "-lineinfo",
    ]
    if msvc_compiler_directory is not None:
        common.extend(["-ccbin", msvc_compiler_directory])
    executable_build = run(
        [*common, "-Xptxas=-v", "-o", str(EXECUTABLE)],
        timeout=240,
    )
    run([*common, "--ptx", "-o", str(PTX)], timeout=240)
    run([*common, "--cubin", "-o", str(CUBIN)], timeout=240)
    sass_dump = run([cuobjdump, "--dump-sass", str(CUBIN)])
    SASS.write_text(sass_dump.stdout, encoding="utf-8")

    source_text = SOURCE.read_text(encoding="utf-8")
    ptx_text = PTX.read_text(encoding="utf-8")
    sass_text = sass_dump.stdout
    primary_ptx = extract_ptx_entry(ptx_text, "open_compose_forward")
    inverse_ptx = extract_ptx_entry(ptx_text, "open_compose_inverse")
    ptxas_text = executable_build.stdout + executable_build.stderr

    primary_source_match = re.search(
        r'extern "C" __global__ void open_compose_forward\((.*?)\)\s*\{',
        source_text,
        flags=re.DOTALL,
    )
    if primary_source_match is None:
        raise RuntimeError("primary kernel signature is not statically visible")
    primary_signature = primary_source_match.group(1)
    barrier_count = primary_ptx.count("xor.b32")
    inverse_barrier_count = inverse_ptx.count("xor.b32")
    ptx_local_ops = re.findall(r"\b(?:ld|st)\.local\b", ptx_text)
    sass_local_ops = re.findall(r"\b(?:LDL|STL)\b", sass_text)
    spill_loads = sum(
        int(value)
        for value in re.findall(r"(\d+) bytes spill loads", ptxas_text)
    )
    spill_stores = sum(
        int(value)
        for value in re.findall(r"(\d+) bytes spill stores", ptxas_text)
    )

    gates = {
        "primary_signature_has_no_y_pointer": (
            primary_signature.count("Carrier4") == 2
            and "device_y" not in primary_signature
            and "__restrict__ y" not in primary_signature
        ),
        "primary_register_boundary_barriers_present": barrier_count >= 8,
        "inverse_register_boundary_barriers_present": inverse_barrier_count >= 8,
        "primary_has_global_output_store": "st.global" in primary_ptx,
        "primary_has_no_local_memory_ops": not ptx_local_ops,
        "sass_has_no_local_memory_ops": not sass_local_ops,
        "ptxas_reports_zero_spill_loads": spill_loads == 0,
        "ptxas_reports_zero_spill_stores": spill_stores == 0,
        "no_phase_lookup_table": "phase_table" not in source_text,
        "control_contains_explicit_host_round_trip": all(
            token in source_text
            for token in (
                "cudaMemcpyDeviceToHost",
                "intermediate_checksum = fnv1a(host_y, bytes)",
                "cudaMemcpyHostToDevice",
            )
        ),
    }
    if not all(gates.values()):
        raise RuntimeError(
            "static CUDA contract failed: "
            + json.dumps(
                {key: value for key, value in gates.items() if not value},
                sort_keys=True,
            )
        )

    return {
        "compiler": run([nvcc, "--version"]).stdout.strip().splitlines()[-1],
        "host_compiler_directory": msvc_compiler_directory,
        "cuda_arch": CUDA_ARCH,
        "source_sha256": sha256_file(SOURCE),
        "executable_sha256": sha256_file(EXECUTABLE),
        "ptx_sha256": sha256_file(PTX),
        "cubin_sha256": sha256_file(CUBIN),
        "sass_sha256": sha256_file(SASS),
        "primary_barrier_count_ptx": barrier_count,
        "inverse_barrier_count_ptx": inverse_barrier_count,
        "ptx_local_memory_op_count": len(ptx_local_ops),
        "sass_local_memory_op_count": len(sass_local_ops),
        "ptxas_spill_load_bytes": spill_loads,
        "ptxas_spill_store_bytes": spill_stores,
        "gates": gates,
    }


def git(*arguments: str) -> str:
    return run(["git", *arguments]).stdout.strip()


def require_clean_pushed_head(expected_commit: str) -> dict[str, str]:
    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    upstream = git("rev-parse", "@{upstream}")
    status = git("status", "--porcelain")
    if head != expected_commit:
        raise RuntimeError(
            f"HEAD {head} does not match preregistered {expected_commit}"
        )
    if branch != "codex/catalytic-frontier":
        raise RuntimeError(f"unexpected branch: {branch}")
    if upstream != head:
        raise RuntimeError(f"pushed head mismatch: {upstream} != {head}")
    if status:
        raise RuntimeError("worktree is not clean at execution boundary")
    return {"head": head, "branch": branch, "upstream": upstream}


def endpoint_health() -> dict[str, Any]:
    try:
        with urllib.request.urlopen(STABLE_URL, timeout=5) as response:
            body = response.read().decode("utf-8")
        return {
            "healthy": response.status == 200,
            "status": response.status,
            "body": json.loads(body),
        }
    except Exception as error:  # pragma: no cover - live-only evidence
        return {"healthy": False, "error": str(error)}


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def classify(
    runtime: dict[str, Any],
    static_audit: dict[str, Any],
    *,
    stable_before: dict[str, Any],
    stable_after: dict[str, Any],
    frontier_free_before: bool,
    frontier_free_after: bool,
    binary_returncode: int,
) -> tuple[str, dict[str, bool]]:
    controls = runtime["controls"]
    metrics = runtime["metrics"]
    gates = {
        "static_contract": all(static_audit["gates"].values()),
        "schema_exact": runtime["schema_version"] == SCHEMA_VERSION,
        "geometry_exact": runtime["geometry"] == {
            "carriers": BATCH_CARRIERS,
            "lanes_per_carrier": LANES_PER_CARRIER,
            "bytes_per_boundary": BOUNDARY_BYTES,
            "warmups": WARMUPS,
            "repetitions": REPETITIONS,
        },
        "typed_ports_exact": runtime["ports"] == {
            "F_domain": "X.complex4@r2-v1",
            "F_codomain": "Y.complex4.z4@r2-v1",
            "G_domain": "Y.complex4.z4@r2-v1",
            "G_codomain": "Z.complex4@r2-v1",
        },
        "primary_y_unmaterialized": (
            metrics["primary_intermediate_materialized_bytes"] == 0
            and controls["primary_final_projection_count"] == 1
        ),
        "matched_control_materializes_y": (
            metrics["control_intermediate_d2h_bytes_per_rep"] == BOUNDARY_BYTES
            and metrics["control_intermediate_h2d_bytes_per_rep"]
            == BOUNDARY_BYTES
            and metrics["control_intermediate_cpu_read_bytes_per_rep"]
            == BOUNDARY_BYTES
        ),
        "exact_composition": (
            controls["primary_reference_mismatches"] == 0
            and controls["route_mismatches"] == 0
        ),
        "wrong_order_negative": (
            controls["wrong_order_equal_count"] == 0
            and controls["wrong_order_negative_law_failures"] == 0
        ),
        "type_mismatch_precontact": (
            controls["type_mismatch_rejected"]
            and controls["launches_at_type_mismatch"] == 0
        ),
        "projection_adversary_rejected": (
            controls["primary_route_admitted"]
            and controls["materialized_route_rejected_as_primary"]
            and controls["control_intermediate_projection_count"] == 1
        ),
        "program_inverse_restores": controls["restoration_mismatches"] == 0,
        "wrong_inverse_order_fails": (
            controls["wrong_inverse_restored_count"] == 0
        ),
        "intermediate_residency_closes": (
            controls["final_intermediate_residency_zero"]
        ),
        "repeated_speed_gate": metrics["wall_speedup"] >= MINIMUM_WALL_SPEEDUP,
        "stable_isolated": (
            stable_before.get("healthy") is True
            and stable_after.get("healthy") is True
            and frontier_free_before
            and frontier_free_after
        ),
        "binary_integrity": runtime["all_integrity_gates"] is True,
        "binary_returncode_zero": binary_returncode == 0,
    }
    if all(gates.values()):
        return "accept-bounded-open-r2-cuda-composition", gates
    if not gates["repeated_speed_gate"] and all(
        value for key, value in gates.items() if key != "repeated_speed_gate"
    ):
        return "reject-speed-open-r2-composition-exact", gates
    return "reject-integrity-open-r2-composition", gates


def execute_once(
    expected_commit: str,
    output: Path,
    static_audit: dict[str, Any],
) -> dict[str, Any]:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite execution evidence: {output}")
    identity = require_clean_pushed_head(expected_commit)
    stable_before = endpoint_health()
    frontier_free_before = port_is_free(FRONTIER_PORT)
    if not stable_before.get("healthy") or not frontier_free_before:
        raise RuntimeError(
            "precontact isolation failed; scientific binary was not launched"
        )

    completed = run(
        [
            str(EXECUTABLE),
            "--carriers",
            str(BATCH_CARRIERS),
            "--warmups",
            str(WARMUPS),
            "--repetitions",
            str(REPETITIONS),
        ],
        check=False,
        timeout=300,
    )
    stable_after = endpoint_health()
    frontier_free_after = port_is_free(FRONTIER_PORT)

    try:
        runtime = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "scientific binary crossed contact but emitted invalid JSON; "
            "the identity is consumed\n"
            f"stdout={completed.stdout!r}\nstderr={completed.stderr!r}"
        ) from error

    verdict, quality_gates = classify(
        runtime,
        static_audit,
        stable_before=stable_before,
        stable_after=stable_after,
        frontier_free_before=frontier_free_before,
        frontier_free_after=frontier_free_after,
        binary_returncode=completed.returncode,
    )
    result = {
        "record_type": "experiment",
        "id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "checkpoint": "catalytic-frontier-r2",
        "hypothesis": (
            "Two typed CUDA morphisms can compose through a register-resident "
            "unprojected Y with exact Z and inverse restoration while avoiding "
            "the causal cost of classical Y materialization."
        ),
        "intervention": (
            "Keep F(X)=Y in registers across an opaque CUDA boundary before "
            "G, versus one matched route that writes, transfers, reads, and "
            "returns every Y byte before applying the same G."
        ),
        "baseline_commit": expected_commit,
        "candidate_commit": expected_commit,
        "model_hash": None,
        "configuration": {
            "schema_version": SCHEMA_VERSION,
            "batch_carriers": BATCH_CARRIERS,
            "lanes_per_carrier": LANES_PER_CARRIER,
            "boundary_bytes": BOUNDARY_BYTES,
            "warmups": WARMUPS,
            "repetitions": REPETITIONS,
            "minimum_wall_speedup": MINIMUM_WALL_SPEEDUP,
            "cuda_arch": CUDA_ARCH,
            "model_contact": False,
        },
        "carrier": {
            "representation": "four complex-f32 lanes per independent carrier",
            "F": "permute xor1 then Z4 phase exponent j",
            "G": "permute xor2 then Z4 phase exponent floor(j/2)+1",
            "shared_port": "Y.complex4.z4@r2-v1",
            "primary_boundary": "register-resident and unprojected",
            "control_boundary": (
                "device-global then pinned-host read then unchanged return"
            ),
            "restoration": "F^-1 after G^-1, derived from the morphism program",
        },
        "static_audit": static_audit,
        "runtime": runtime,
        "metrics_before": {
            "route": "classically-materialized-Y control",
            "median_wall_ms": runtime["metrics"][
                "materialized_wall_median_ms"
            ],
            "median_cuda_timeline_ms": runtime["metrics"][
                "materialized_cuda_timeline_median_ms"
            ],
            "intermediate_d2h_bytes_per_rep": BOUNDARY_BYTES,
            "intermediate_h2d_bytes_per_rep": BOUNDARY_BYTES,
            "intermediate_cpu_read_bytes_per_rep": BOUNDARY_BYTES,
        },
        "metrics_after": {
            "route": "register-resident open-Y primary",
            "median_wall_ms": runtime["metrics"][
                "primary_wall_median_ms"
            ],
            "median_cuda_timeline_ms": runtime["metrics"][
                "primary_cuda_timeline_median_ms"
            ],
            "intermediate_materialized_bytes_per_rep": 0,
            "wall_speedup": runtime["metrics"]["wall_speedup"],
        },
        "quality_gates": quality_gates,
        "verdict": verdict,
        "claim_ceiling": (
            "bounded finite R2 CUDA composition with one unmaterialized "
            "intermediate; not canonical .holo, general categorical trace, "
            "model inference, arbitrary composition, or unbounded compute"
        ),
        "stable_isolation": {
            "before": stable_before,
            "after": stable_after,
            "frontier_port_free_before": frontier_free_before,
            "frontier_port_free_after": frontier_free_after,
        },
        "execution": {
            "identity": identity,
            "returncode": completed.returncode,
            "stderr": completed.stderr,
        },
        "next_boundary": (
            "If accepted, preserve the bounded result and test the same "
            "open/materialized boundary contract inside one existing fused "
            "inference operator; otherwise create one evidence-motivated "
            "successor without retrying neo-exp-0079."
        ),
        "automatic_promotion": False,
        "research_goal_blocked": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--static-only", action="store_true")
    mode.add_argument("--execute-once", action="store_true")
    parser.add_argument("--expected-commit")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    static_audit = compile_and_audit()
    if args.static_only:
        print(json.dumps(static_audit, indent=2, sort_keys=True))
        return 0
    if not args.expected_commit or args.output is None:
        raise RuntimeError(
            "--execute-once requires --expected-commit and --output"
        )
    result = execute_once(
        args.expected_commit,
        args.output.resolve(),
        static_audit,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verdict"].startswith("accept-") else 5


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
