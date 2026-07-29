#!/usr/bin/env python3
"""neo-exp-0089: qualify one corrected native-Linux CUDA output identity."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping

import catalytic_frontier_harness as harness
import catalytic_frontier_linux_sidecar as linux_sidecar
import catalytic_frontier_live_terminal_pipeline as live_pipeline
import catalytic_frontier_single_request_latency as latency
import catalytic_frontier_terminal_logits_continuation as terminal


EXPERIMENT_ID = "neo-exp-0089"
ATTEMPT_ID = "frontier-attempt-0129"
RUNTIME_SOURCE_COMMIT = "abb85fbd827eabebf1d977a7068dfc062d486e00"
REFERENCE_0088_RUNTIME_COMMIT = "e0a21cdd978a735010c8c0bcf896827a375a542c"
ROOT = Path(__file__).resolve().parents[1]
WINDOWS_GENERATED_SHA256 = (
    "43A87A791BE696333AFC81ED3498DECCDFB4CB582FDC66432CD0FEC35B0F5953"
)
WINDOWS_RETAINED_TOKENS = 612
LINUX_0088_GENERATED_SHA256 = (
    "CE01CEBADD2BB6454B5860B9AAFB6A2B15D34FE8D9C894825D0E6BF102481E72"
)
LINUX_0088_RETAINED_TOKENS = 607
EXPECTED_ANSWER = "C"
EXPECTED_PROMPT_TOKENS = 543
EXPECTED_PROMPT_TOKEN_SHA256 = (
    "17CC9100104C5C2C91E2BB3AA14143515F465B584427B91C4B757F5CB35336D2"
)
EXPECTED_PAYLOAD_SHA256 = (
    "6D24B032682CEF73CA257694CB93EF73E24981B50D15F220B1F777DAC0E674B6"
)
RESTORATION_CLASS = "NO_RESTORATION_CLAIM"
DEFAULT_BINARY = ROOT / "build" / "linux-cuda-0089-gpufast" / "bin" / "llama-server"
DEFAULT_MODEL = live_pipeline.DEFAULT_MODEL
DEFAULT_COMPILER_CONTRACT = (
    ROOT / "build" / "linux-toolchain-0088" / "cuda-clang-gpufast++"
)
DEFAULT_RUNTIME_MANIFEST = ROOT / "lab" / f"{EXPERIMENT_ID}-runtime-manifest.json"
DEFAULT_OUTPUT = ROOT / "lab" / f"{EXPERIMENT_ID}.local.json"
DEFAULT_LOCK = (
    ROOT / "build" / "linux-catalytic" / f"{EXPERIMENT_ID}.active-lock.json"
)
DEFAULT_RUN_PARENT = ROOT / "build" / "linux-catalytic"
REQUIRED_RUNTIME_ARTIFACTS = (
    "binary",
    "build_log",
    "build_control_repair_log",
    "build_ui_repair_log",
    "cmake_cache",
    "carrier_source",
    "compile_commands",
    "compiler_contract",
    "compiler_executable",
    "compiler_driver_proof",
    "compiler_probe_executable",
    "compiler_probe_source",
    "cuda_fatbinary",
    "cuda_fatbinary_real",
    "cuda_libdevice",
    "cuda_ptxas",
    "configure_incident_log",
    "configure_control_repair_log",
    "configure_repair_log",
    "configure_ui_repair_log",
    "controller",
    "controller_test",
    "fanout_source",
    "harness_source",
    "inherited_source",
    "kernel_source",
    "latency_source",
    "live_pipeline_source",
    "reference_0088_compiler_contract",
    "sidecar_source",
    "terminal_source",
    "water_source",
    "warm_source",
)
EXPECTED_BUILD_DESCRIPTOR = {
    "generator": "Unix Makefiles",
    "target": "llama-server",
    "build_type": "Release",
    "shared_libraries": True,
    "ggml_cuda": True,
    "ggml_cuda_no_vmm": True,
    "ggml_native": True,
    "ggml_backend_dl": False,
    "cuda_architectures": "86-real",
    "cuda_translation_units": 139,
    "llama_build_server": True,
    "llama_build_tools": True,
    "llama_build_tests": False,
    "llama_build_examples": False,
    "llama_build_app": False,
    "llama_build_ui": False,
    "llama_use_prebuilt_ui": False,
    "llama_openssl": False,
    "llama_tools_install": False,
    "cmake_build_rpath": (
        "build/linux-toolchain-0088/cuda13-compat2-toolkit/lib64"
    ),
    "cmake_install_rpath": (
        "build/linux-toolchain-0088/cuda13-compat2-toolkit/lib64"
    ),
}
EXPECTED_TASK_A_CONTRACT = {
    "model_bytes": linux_sidecar.MODEL_SIZE,
    "model_sha256": linux_sidecar.MODEL_SHA256,
    "prompt_token_count": EXPECTED_PROMPT_TOKENS,
    "prompt_token_sha256": EXPECTED_PROMPT_TOKEN_SHA256,
    "payload_sha256": EXPECTED_PAYLOAD_SHA256,
    "expected_answer": EXPECTED_ANSWER,
    "model_requests": 1,
    "root_actions": 0,
    "live_boundary_actions": 0,
    "restoration_class": RESTORATION_CLASS,
}


class ExperimentError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ExperimentError(message)


class RawResponseRecorder:
    def __init__(self, path: Path, progress: dict[str, Any]):
        self.path = path
        self.progress = progress
        self.handle = path.open("xb")
        self.bytes_written = 0
        self.lines_written = 0
        self.closed = False

    def __call__(self, line: bytes) -> None:
        require(isinstance(line, bytes), "raw response line is not bytes")
        self.handle.write(line)
        self.handle.flush()
        os.fsync(self.handle.fileno())
        self.bytes_written += len(line)
        self.lines_written += 1
        self.progress["scientific_contact"] = True
        self.progress["response_bytes_observed"] = self.bytes_written
        self.progress["response_lines_observed"] = self.lines_written

    def close(self) -> dict[str, Any]:
        close_error: BaseException | None = None
        if not self.closed:
            try:
                self.handle.close()
            except BaseException as exc:
                close_error = exc
            self.closed = True
        persisted = {
            "bytes": self.path.stat().st_size,
            "sha256": harness.live_runtime.sha256_file(self.path),
        }
        identity = {
            "path": str(self.path),
            "bytes": persisted["bytes"],
            "lines": self.lines_written,
            "sha256": persisted["sha256"],
            "response_observed": int(persisted["bytes"]) > 0,
        }
        self.progress["raw_response_capture"] = identity
        if close_error is not None:
            raise ExperimentError(
                "raw response recorder close failed: "
                f"{type(close_error).__name__}: {close_error}"
            ) from close_error
        return identity


class RequestAttemptSidecar:
    def __init__(
        self,
        sidecar: linux_sidecar.LinuxSidecar,
        progress: dict[str, Any],
    ):
        self.sidecar = sidecar
        self.progress = progress

    def guarded(
        self,
        label: str,
        callback: Any,
        *,
        timeout: float,
        **kwargs: Any,
    ) -> Any:
        def attempt_transport() -> Any:
            marker = terminal.write_exclusive_json(
                self.sidecar.run_root / "request-transport-attempt.json",
                {
                    "id": EXPERIMENT_ID,
                    "attempt_id": ATTEMPT_ID,
                    "created_unix_ns": time.time_ns(),
                    "meaning": (
                        "the completion transport callback is next; any later "
                        "ambiguity is conservatively consuming"
                    ),
                    "prepared_identity": self.progress.get(
                        "prepared_identity"
                    ),
                },
            )
            self.progress["transport_attempted"] = True
            self.progress["transport_attempt_marker"] = marker
            return callback()

        return self.sidecar.guarded(
            label,
            attempt_transport,
            timeout=timeout,
            **kwargs,
        )


def canonical_sha256(value: Any) -> str:
    return harness.sha256_bytes(harness.carrier.canonical_json_bytes(value))


def file_identity(path: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    require(resolved.is_file(), f"runtime artifact is not a file: {path}")
    return {
        "bytes": resolved.stat().st_size,
        "sha256": harness.live_runtime.sha256_file(resolved),
    }


def require_exact_identity(
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
    label: str,
) -> None:
    require(dict(actual) == dict(expected), f"{label} identity changed")


def cmake_cache_values(cache: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in cache.read_text(encoding="utf-8", errors="strict").splitlines():
        if not line or line.startswith(("//", "#")) or "=" not in line:
            continue
        key_with_type, value = line.split("=", 1)
        key = key_with_type.split(":", 1)[0]
        values[key] = value
    return values


def runtime_source_relation() -> dict[str, Any]:
    paths = [
        "CMakeLists.txt",
        "ggml",
        "src",
        "common",
        "tools",
        "vendor",
        "scripts/catalytic_frontier_fanout.py",
        "scripts/catalytic_frontier_harness.py",
        "scripts/catalytic_frontier_linux_sidecar.py",
        "scripts/catalytic_frontier_live_terminal_pipeline.py",
        "scripts/catalytic_frontier_single_request_latency.py",
        "scripts/catalytic_frontier_terminal_logits_continuation.py",
        "scripts/catalytic_frontier_water_panel_qualifier.py",
        "scripts/catalytic_kernel_0.py",
        "scripts/holostate_v1_inherited_task_a_carrier_evaluation.py",
        (
            "scripts/"
            "holostate_v1_multi_branch_runtime_native_carrier_evaluation.py"
        ),
        "scripts/holostate_v1_warm_trajectory_related_task_evaluation.py",
    ]
    completed = subprocess.run(
        [
            "git",
            "diff",
            "--quiet",
            f"{REFERENCE_0088_RUNTIME_COMMIT}..{RUNTIME_SOURCE_COMMIT}",
            "--",
            *paths,
        ],
        cwd=ROOT,
        check=False,
    )
    require(
        completed.returncode == 0,
        "server runtime source changed from 0088",
    )
    current = subprocess.run(
        [
            "git",
            "diff",
            "--quiet",
            RUNTIME_SOURCE_COMMIT,
            "--",
            *paths,
        ],
        cwd=ROOT,
        check=False,
    )
    require(
        current.returncode == 0,
        "current server runtime differs from built source",
    )
    return {
        "reference_0088_runtime_commit": REFERENCE_0088_RUNTIME_COMMIT,
        "build_source_commit": RUNTIME_SOURCE_COMMIT,
        "compared_paths": paths,
        "runtime_source_exactly_unchanged": True,
        "current_runtime_matches_build_source": True,
    }


def observed_build_descriptor(
    *,
    build_root: Path,
    compiler_contract: Path,
) -> dict[str, Any]:
    cache = build_root / "CMakeCache.txt"
    commands_path = build_root / "compile_commands.json"
    cache_values = cmake_cache_values(cache)
    rows = json.loads(commands_path.read_text(encoding="utf-8"))
    require(isinstance(rows, list), "compile database shape changed")
    cuda_rows = [
        row
        for row in rows
        if isinstance(row, Mapping)
        and isinstance(row.get("file"), str)
        and str(row["file"]).endswith(".cu")
        and "/ggml/src/ggml-cuda/" in str(row["file"]).replace("\\", "/")
    ]
    require(len(cuda_rows) == 139, "compile database CUDA unit count changed")
    sources: set[str] = set()
    for row in cuda_rows:
        source = Path(str(row["file"])).resolve(strict=True)
        require(source.is_relative_to(ROOT), "CUDA source escaped repository")
        sources.add(str(source))
        command_value = row.get("command")
        require(isinstance(command_value, str), "CUDA compile command is missing")
        tokens = shlex.split(command_value)
        require(tokens, "CUDA compile command is empty")
        require(
            Path(tokens[0]).resolve(strict=True) == compiler_contract.resolve(),
            "CUDA compile command bypasses compiler contract",
        )
        require(
            tokens.count("-use_fast_math") == 1,
            "CUDA compile command fast-math intent changed",
        )
        require(
            "-ffast-math" not in tokens,
            "CUDA compile database contains unscoped host fast math",
        )
        require(
            "--cuda-gpu-arch=sm_86" in tokens,
            "CUDA compile command architecture changed",
        )
        require(
            "-x" in tokens and tokens[tokens.index("-x") + 1] == "cuda",
            "CUDA compile command language changed",
        )
    require(len(sources) == 139, "CUDA compile database repeats a source")
    require(
        cache_values.get("CMAKE_CUDA_COMPILER")
        == str(compiler_contract.resolve()),
        "CMake CUDA compiler changed",
    )
    build_rpath = Path(str(cache_values.get("CMAKE_BUILD_RPATH"))).resolve(
        strict=True
    )
    install_rpath = Path(str(cache_values.get("CMAKE_INSTALL_RPATH"))).resolve(
        strict=True
    )
    require(
        build_rpath.is_relative_to(ROOT)
        and install_rpath.is_relative_to(ROOT),
        "CMake CUDA rpath escaped repository",
    )
    observed = {
        "generator": cache_values.get("CMAKE_GENERATOR"),
        "target": "llama-server",
        "build_type": cache_values.get("CMAKE_BUILD_TYPE"),
        "shared_libraries": cache_values.get("BUILD_SHARED_LIBS") == "ON",
        "ggml_cuda": cache_values.get("GGML_CUDA") == "ON",
        "ggml_cuda_no_vmm": cache_values.get("GGML_CUDA_NO_VMM") == "ON",
        "ggml_native": cache_values.get("GGML_NATIVE") == "ON",
        "ggml_backend_dl": cache_values.get("GGML_BACKEND_DL") == "ON",
        "cuda_architectures": cache_values.get("CMAKE_CUDA_ARCHITECTURES"),
        "cuda_translation_units": len(cuda_rows),
        "llama_build_server": cache_values.get("LLAMA_BUILD_SERVER") == "ON",
        "llama_build_tools": cache_values.get("LLAMA_BUILD_TOOLS") == "ON",
        "llama_build_tests": cache_values.get("LLAMA_BUILD_TESTS") == "ON",
        "llama_build_examples": cache_values.get("LLAMA_BUILD_EXAMPLES") == "ON",
        "llama_build_app": cache_values.get("LLAMA_BUILD_APP") == "ON",
        "llama_build_ui": cache_values.get("LLAMA_BUILD_UI") == "ON",
        "llama_use_prebuilt_ui": (
            cache_values.get("LLAMA_USE_PREBUILT_UI") == "ON"
        ),
        "llama_openssl": cache_values.get("LLAMA_OPENSSL") == "ON",
        "llama_tools_install": (
            cache_values.get("LLAMA_TOOLS_INSTALL") == "ON"
        ),
        "cmake_build_rpath": build_rpath.relative_to(ROOT).as_posix(),
        "cmake_install_rpath": install_rpath.relative_to(ROOT).as_posix(),
    }
    require_exact_identity(
        EXPECTED_BUILD_DESCRIPTOR,
        observed,
        "observed build descriptor",
    )
    return observed


def linked_library_identities(binary: Path) -> list[dict[str, Any]]:
    completed = subprocess.run(
        ["ldd", str(binary)],
        check=True,
        capture_output=True,
        text=True,
    )
    identities: list[dict[str, Any]] = []
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "=>" in line:
            soname, target = (part.strip() for part in line.split("=>", 1))
            require("not found" not in target, f"linked library missing: {soname}")
            path_text = target.split(" (", 1)[0].strip()
            path = Path(path_text).resolve(strict=True)
            identities.append(
                {
                    "soname": soname,
                    "kind": "file",
                    **file_identity(path),
                }
            )
            continue
        if line.startswith("/"):
            path_text = line.split(" (", 1)[0].strip()
            path = Path(path_text).resolve(strict=True)
            identities.append(
                {
                    "soname": path.name,
                    "kind": "file",
                    **file_identity(path),
                }
            )
            continue
        soname = line.split(" (", 1)[0].strip()
        require(
            soname == "linux-vdso.so.1",
            f"unclassified ldd identity: {line}",
        )
        identities.append({"soname": soname, "kind": "virtual"})
    identities.sort(key=lambda item: str(item["soname"]))
    require(
        len({str(item["soname"]) for item in identities}) == len(identities),
        "duplicate linked-library soname cannot be manifest-bound",
    )
    return identities


def cuda_driver_library_identities() -> list[dict[str, Any]]:
    completed = subprocess.run(
        ["ldconfig", "-p"],
        check=True,
        capture_output=True,
        text=True,
    )
    identities: list[dict[str, Any]] = []
    for soname in ("libcuda.so.1", "libnvidia-ptxjitcompiler.so.1"):
        candidates = [
            line
            for line in completed.stdout.splitlines()
            if line.strip().startswith(f"{soname} ")
            and "(libc6,x86-64)" in line
        ]
        require(len(candidates) == 1, f"CUDA driver library resolution changed: {soname}")
        path_text = candidates[0].split("=>", 1)[1].strip()
        identities.append(
            {
                "soname": soname,
                "kind": "file",
                **file_identity(Path(path_text)),
            }
        )
    return identities


def compiler_cc1_commands(
    compiler_contract: Path,
    probe_source: Path,
) -> tuple[str, str]:
    completed = subprocess.run(
        [
            str(compiler_contract),
            "-###",
            "-x",
            "cuda",
            "-O3",
            "--cuda-gpu-arch=sm_86",
            "-c",
            str(probe_source),
            "-use_fast_math",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    trace = completed.stdout + completed.stderr
    cc1 = [line for line in trace.splitlines() if '"-cc1"' in line]
    device = [
        line
        for line in cc1
        if '"-triple" "nvptx64-nvidia-cuda"' in line
    ]
    host = [
        line
        for line in cc1
        if '"-triple" "x86_64-pc-linux-gnu"' in line
    ]
    require(len(device) == 1, "compiler probe device command changed")
    require(len(host) == 1, "compiler probe host command changed")
    return device[0], host[0]


def canonical_cc1_sha256(command: str) -> str:
    tokens = shlex.split(command)
    normalized: list[str] = []
    path_value_flags = {"-o", "-fcuda-include-gpubinary"}
    normalize_next_path = False
    for token in tokens:
        if normalize_next_path:
            normalized.append("<DRIVER_TEMP_ARTIFACT>")
            normalize_next_path = False
            continue
        normalized_token = token
        if token in path_value_flags:
            normalize_next_path = True
        elif token.startswith("-cuid="):
            normalized_token = "-cuid=<DRIVER_CUID>"
        elif token.startswith(str(ROOT)):
            normalized_token = "<ROOT>" + token[len(str(ROOT)) :]
        elif "/Scratch/" in token or token.startswith("/tmp/"):
            normalized_token = "<DRIVER_TEMP_ARTIFACT>"
        normalized.append(normalized_token)
    require(not normalize_next_path, "compiler cc1 output path is missing")
    return canonical_sha256(normalized)


def compiler_semantics_probe(
    compiler_contract: Path,
    probe_source: Path,
) -> dict[str, Any]:
    device_line, host_line = compiler_cc1_commands(
        compiler_contract,
        probe_source,
    )
    device_fast_flags = (
        '"-ffast-math"',
        '"-fapprox-func"',
        '"-funsafe-math-optimizations"',
        '"-fgpu-approx-transcendentals"',
    )
    forbidden_host_fast_flags = (
        '"-ffast-math"',
        '"-menable-no-infs"',
        '"-menable-no-nans"',
        '"-fapprox-func"',
        '"-funsafe-math-optimizations"',
        '"-fno-signed-zeros"',
        '"-mreassociate"',
        '"-freciprocal-math"',
        '"-ffinite-math-only"',
        '"-fgpu-approx-transcendentals"',
    )
    gates = {
        "one_device_cc1": True,
        "one_host_cc1": True,
        "device_fast_math_exact": all(
            flag in device_line for flag in device_fast_flags
        ),
        "host_fast_math_absent": all(
            flag not in host_line for flag in forbidden_host_fast_flags
        ),
        "host_math_errno_strict": '"-fmath-errno"' in host_line,
        "host_fp_contract_strict": '"-ffp-contract=on"' in host_line,
    }
    require(all(gates.values()), "compiler device-only fast-math probe failed")
    return {
        **gates,
        "device_cc1_canonical_sha256": canonical_cc1_sha256(device_line),
        "host_cc1_canonical_sha256": canonical_cc1_sha256(host_line),
    }


def compiler_reference_relation(
    *,
    compiler_contract: Path,
    reference_0088_compiler: Path,
    probe_source: Path,
) -> dict[str, Any]:
    current_device, current_host = compiler_cc1_commands(
        compiler_contract,
        probe_source,
    )
    reference_device, reference_host = compiler_cc1_commands(
        reference_0088_compiler,
        probe_source,
    )
    current_device_sha = canonical_cc1_sha256(current_device)
    reference_device_sha = canonical_cc1_sha256(reference_device)
    current_host_sha = canonical_cc1_sha256(current_host)
    reference_host_sha = canonical_cc1_sha256(reference_host)
    relation = {
        "device_cc1_exactly_matches_0088": (
            current_device_sha == reference_device_sha
        ),
        "host_cc1_differs_from_0088": current_host_sha != reference_host_sha,
        "reference_0088_host_has_fast_math": '"-ffast-math"' in reference_host,
        "current_device_cc1_canonical_sha256": current_device_sha,
        "reference_device_cc1_canonical_sha256": reference_device_sha,
        "current_host_cc1_canonical_sha256": current_host_sha,
        "reference_host_cc1_canonical_sha256": reference_host_sha,
    }
    require(
        relation["device_cc1_exactly_matches_0088"]
        and relation["host_cc1_differs_from_0088"]
        and relation["reference_0088_host_has_fast_math"],
        "compiler relation to 0088 changed",
    )
    return relation


def gpu_identity() -> list[dict[str, str]]:
    completed = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=uuid,name,compute_cap,driver_version",
            "--format=csv,noheader,nounits",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    result: list[dict[str, str]] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        fields = [field.strip() for field in line.split(",")]
        require(len(fields) == 4, "GPU identity shape changed")
        result.append(
            {
                "uuid": fields[0],
                "name": fields[1],
                "compute_capability": fields[2],
                "driver_version": fields[3],
            }
        )
    require(result, "no CUDA GPU identity available")
    return result


def binary_version_identity(binary: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [str(binary), "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        "stdout_sha256": harness.sha256_bytes(completed.stdout.encode("utf-8")),
        "stderr_sha256": harness.sha256_bytes(completed.stderr.encode("utf-8")),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def runtime_manifest_template(
    *,
    binary: Path,
    compiler_contract: Path,
    runtime_source_commit: str,
) -> dict[str, Any]:
    require(
        runtime_source_commit == RUNTIME_SOURCE_COMMIT,
        "runtime manifest source commit changed",
    )
    build_root = binary.parent.parent.resolve(strict=True)
    toolchain_root = compiler_contract.parent.resolve(strict=True)
    artifact_paths = {
        "binary": binary,
        "cmake_cache": build_root / "CMakeCache.txt",
        "compile_commands": build_root / "compile_commands.json",
        "configure_incident_log": ROOT
        / "build"
        / "linux-cuda-0089-gpufast-configure.log",
        "configure_repair_log": ROOT
        / "build"
        / "linux-cuda-0089-gpufast-configure-repair.log",
        "configure_ui_repair_log": ROOT
        / "build"
        / "linux-cuda-0089-gpufast-configure-ui-repair.log",
        "configure_control_repair_log": ROOT
        / "build"
        / "linux-cuda-0089-gpufast-configure-control-repair.log",
        "build_log": ROOT / "build" / "linux-cuda-0089-gpufast-build.log",
        "build_ui_repair_log": ROOT
        / "build"
        / "linux-cuda-0089-gpufast-build-ui-repair.log",
        "build_control_repair_log": ROOT
        / "build"
        / "linux-cuda-0089-gpufast-build-control-repair.log",
        "compiler_contract": compiler_contract,
        "reference_0088_compiler_contract": toolchain_root / "cuda-clang++",
        "compiler_executable": toolchain_root
        / "clang-root"
        / "usr"
        / "bin"
        / "clang++-21",
        "compiler_driver_proof": ROOT
        / "build"
        / "linux-toolchain-0088"
        / "cuda-clang-gpufast-driver-proof.txt",
        "compiler_probe_source": ROOT
        / "build"
        / "linux-toolchain-0088"
        / "cuda-smoke.cu",
        "compiler_probe_executable": ROOT
        / "build"
        / "linux-toolchain-0088"
        / "cuda-smoke-gpufast",
        "cuda_ptxas": toolchain_root
        / "cuda13-compat2-toolkit"
        / "bin"
        / "ptxas",
        "cuda_fatbinary": toolchain_root
        / "cuda13-compat2-toolkit"
        / "bin"
        / "fatbinary",
        "cuda_fatbinary_real": toolchain_root
        / "cuda13-compat2-toolkit"
        / "bin"
        / "fatbinary.real",
        "cuda_libdevice": toolchain_root
        / "cuda13-compat2-toolkit"
        / "nvvm"
        / "libdevice"
        / "libdevice.10.bc",
        "controller": Path(__file__),
        "controller_test": ROOT
        / "scripts"
        / "test_catalytic_frontier_linux_cuda_identity_qualifier.py",
        "fanout_source": ROOT / "scripts" / "catalytic_frontier_fanout.py",
        "harness_source": ROOT / "scripts" / "catalytic_frontier_harness.py",
        "inherited_source": ROOT
        / "scripts"
        / "holostate_v1_inherited_task_a_carrier_evaluation.py",
        "kernel_source": ROOT / "scripts" / "catalytic_kernel_0.py",
        "sidecar_source": ROOT
        / "scripts"
        / "catalytic_frontier_linux_sidecar.py",
        "live_pipeline_source": ROOT
        / "scripts"
        / "catalytic_frontier_live_terminal_pipeline.py",
        "latency_source": ROOT
        / "scripts"
        / "catalytic_frontier_single_request_latency.py",
        "terminal_source": ROOT
        / "scripts"
        / "catalytic_frontier_terminal_logits_continuation.py",
        "water_source": ROOT
        / "scripts"
        / "catalytic_frontier_water_panel_qualifier.py",
        "warm_source": ROOT
        / "scripts"
        / "holostate_v1_warm_trajectory_related_task_evaluation.py",
        "carrier_source": ROOT
        / "scripts"
        / "holostate_v1_multi_branch_runtime_native_carrier_evaluation.py",
    }
    artifacts: dict[str, Any] = {}
    for name, path in artifact_paths.items():
        resolved = path.resolve(strict=True)
        require(resolved.is_relative_to(ROOT), f"artifact outside repository: {name}")
        artifacts[name] = {
            "relative_path": resolved.relative_to(ROOT).as_posix(),
            **file_identity(resolved),
        }
    probe_source = artifact_paths["compiler_probe_source"].resolve(strict=True)
    cuda_objects = list(
        build_root.glob("ggml/src/ggml-cuda/CMakeFiles/ggml-cuda.dir/**/*.cu.o")
    )
    require(len(cuda_objects) == 139, "manifest CUDA translation-unit count changed")
    return {
        "schema": "neo3000-linux-cuda-runtime-manifest-v1",
        "experiment_id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "runtime_source_commit": runtime_source_commit,
        "meaning": (
            "Prospective ignored-artifact and host runtime binding for the "
            "single neo-exp-0089 Task-A scientific contact"
        ),
        "causal_intervention": (
            "Map upstream -use_fast_math to -Xarch_device -ffast-math so "
            "device semantics remain unchanged from 0088 and host .cu "
            "semantics return to strict Clang defaults"
        ),
        "build_descriptor": observed_build_descriptor(
            build_root=build_root,
            compiler_contract=compiler_contract,
        ),
        "declared_build_invocation": {
            "parallel_jobs": 1,
            "cpu_nice": 10,
            "io_class": "best-effort",
            "io_priority": 7,
            "status": "operator-declared; output binary and compile closure are exact",
        },
        "task_a_contract": dict(EXPECTED_TASK_A_CONTRACT),
        "runtime_source_relation": runtime_source_relation(),
        "compiler_probe_source": probe_source.relative_to(ROOT).as_posix(),
        "compiler_semantics_gates": compiler_semantics_probe(
            compiler_contract,
            probe_source,
        ),
        "compiler_reference_relation": compiler_reference_relation(
            compiler_contract=compiler_contract,
            reference_0088_compiler=artifact_paths[
                "reference_0088_compiler_contract"
            ],
            probe_source=probe_source,
        ),
        "artifacts": artifacts,
        "linked_libraries": linked_library_identities(binary),
        "cuda_driver_libraries": cuda_driver_library_identities(),
        "gpu_identity": gpu_identity(),
        "binary_version_identity": binary_version_identity(binary),
        "restoration_class": RESTORATION_CLASS,
        "scientific_contact": False,
    }


def validate_runtime_manifest(
    *,
    binary: Path,
    compiler_contract: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    manifest_file = manifest_path.resolve(strict=True)
    require(
        manifest_file == DEFAULT_RUNTIME_MANIFEST.resolve(strict=True),
        "0089 runtime manifest path changed",
    )
    relative_manifest = manifest_file.relative_to(ROOT).as_posix()
    tracked = subprocess.check_output(
        ["git", "ls-files", "--error-unmatch", relative_manifest],
        cwd=ROOT,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()
    require(tracked == relative_manifest, "0089 runtime manifest is not tracked")
    committed_bytes = subprocess.check_output(
        ["git", "show", f"HEAD:{relative_manifest}"],
        cwd=ROOT,
    )
    worktree_bytes = manifest_file.read_bytes()
    require(
        committed_bytes == worktree_bytes,
        "0089 runtime manifest differs from current commit",
    )
    manifest = json.loads(worktree_bytes)
    require(
        manifest.get("schema") == "neo3000-linux-cuda-runtime-manifest-v1",
        "0089 runtime manifest schema changed",
    )
    require(manifest.get("experiment_id") == EXPERIMENT_ID, "manifest id changed")
    require(manifest.get("attempt_id") == ATTEMPT_ID, "manifest attempt changed")
    require(
        manifest.get("runtime_source_commit") == RUNTIME_SOURCE_COMMIT,
        "manifest runtime source commit changed",
    )
    require(
        manifest.get("restoration_class") == RESTORATION_CLASS,
        "manifest restoration class changed",
    )
    require(
        manifest.get("scientific_contact") is False,
        "manifest was not created before scientific contact",
    )
    manifest_task_contract = manifest.get("task_a_contract")
    require(
        isinstance(manifest_task_contract, Mapping),
        "manifest Task-A contract missing",
    )
    require_exact_identity(
        EXPECTED_TASK_A_CONTRACT,
        manifest_task_contract,
        "manifest Task-A contract",
    )
    manifest_source_relation = manifest.get("runtime_source_relation")
    require(
        isinstance(manifest_source_relation, Mapping),
        "manifest runtime source relation missing",
    )
    require_exact_identity(
        manifest_source_relation,
        runtime_source_relation(),
        "runtime source relation",
    )
    manifest_build_descriptor = manifest.get("build_descriptor")
    require(
        isinstance(manifest_build_descriptor, Mapping),
        "manifest build descriptor missing",
    )
    require_exact_identity(
        EXPECTED_BUILD_DESCRIPTOR,
        manifest_build_descriptor,
        "manifest build descriptor",
    )
    actual_build_descriptor = observed_build_descriptor(
        build_root=binary.parent.parent.resolve(strict=True),
        compiler_contract=compiler_contract,
    )
    require_exact_identity(
        manifest_build_descriptor,
        actual_build_descriptor,
        "runtime build descriptor",
    )
    artifacts = manifest.get("artifacts")
    require(isinstance(artifacts, Mapping) and artifacts, "manifest artifacts missing")
    require(
        set(artifacts) == set(REQUIRED_RUNTIME_ARTIFACTS),
        "manifest artifact closure changed",
    )
    artifact_results: dict[str, Any] = {}
    for name, expected in artifacts.items():
        require(isinstance(expected, Mapping), f"manifest artifact invalid: {name}")
        relative_path = expected.get("relative_path")
        require(
            isinstance(relative_path, str) and relative_path,
            f"manifest path invalid: {name}",
        )
        path = (ROOT / relative_path).resolve(strict=True)
        require(
            path.is_relative_to(ROOT),
            f"manifest artifact escapes repository: {name}",
        )
        actual = file_identity(path)
        require_exact_identity(
            {"bytes": expected.get("bytes"), "sha256": expected.get("sha256")},
            actual,
            f"manifest artifact {name}",
        )
        artifact_results[str(name)] = actual
    require(
        Path(str(artifacts["binary"]["relative_path"])).name == binary.name
        and (ROOT / str(artifacts["binary"]["relative_path"])).resolve()
        == binary.resolve(),
        "manifest binary path changed",
    )
    require(
        (ROOT / str(artifacts["compiler_contract"]["relative_path"])).resolve()
        == compiler_contract.resolve(),
        "manifest compiler path changed",
    )
    actual_libraries = linked_library_identities(binary)
    expected_libraries = manifest.get("linked_libraries")
    require(
        isinstance(expected_libraries, list),
        "manifest linked libraries missing",
    )
    require_exact_identity(
        {"linked_libraries": expected_libraries},
        {"linked_libraries": actual_libraries},
        "linked-library closure",
    )
    expected_driver_libraries = manifest.get("cuda_driver_libraries")
    require(
        isinstance(expected_driver_libraries, list),
        "manifest CUDA driver libraries missing",
    )
    require_exact_identity(
        {"cuda_driver_libraries": expected_driver_libraries},
        {"cuda_driver_libraries": cuda_driver_library_identities()},
        "CUDA driver-library closure",
    )
    expected_gpu = manifest.get("gpu_identity")
    require(isinstance(expected_gpu, list), "manifest GPU identity missing")
    require(
        len(expected_gpu) == 1,
        "0089 requires exactly one visible CUDA GPU",
    )
    require_exact_identity(
        {"gpu_identity": expected_gpu},
        {"gpu_identity": gpu_identity()},
        "GPU",
    )
    expected_version = manifest.get("binary_version_identity")
    require(
        isinstance(expected_version, Mapping),
        "manifest binary version identity missing",
    )
    require_exact_identity(
        expected_version,
        binary_version_identity(binary),
        "binary version",
    )
    probe_relative = manifest.get("compiler_probe_source")
    require(
        isinstance(probe_relative, str) and probe_relative,
        "compiler probe source missing",
    )
    probe_source = (ROOT / probe_relative).resolve(strict=True)
    compiler_gates = compiler_semantics_probe(compiler_contract, probe_source)
    expected_compiler_gates = manifest.get("compiler_semantics_gates")
    require(
        isinstance(expected_compiler_gates, Mapping),
        "manifest compiler semantics missing",
    )
    require_exact_identity(
        expected_compiler_gates,
        compiler_gates,
        "compiler semantics",
    )
    expected_compiler_relation = manifest.get("compiler_reference_relation")
    require(
        isinstance(expected_compiler_relation, Mapping),
        "manifest compiler reference relation missing",
    )
    actual_compiler_relation = compiler_reference_relation(
        compiler_contract=compiler_contract,
        reference_0088_compiler=(
            ROOT
            / str(
                artifacts["reference_0088_compiler_contract"]["relative_path"]
            )
        ).resolve(strict=True),
        probe_source=probe_source,
    )
    require_exact_identity(
        expected_compiler_relation,
        actual_compiler_relation,
        "compiler reference relation",
    )
    return {
        "path": str(manifest_file),
        "sha256": harness.live_runtime.sha256_file(manifest_file),
        "runtime_source_commit": manifest.get("runtime_source_commit"),
        "artifact_count": len(artifact_results),
        "linked_library_count": len(actual_libraries),
        "cuda_driver_library_count": len(expected_driver_libraries),
        "gpu_identity": expected_gpu,
        "binary_version_identity": expected_version,
        "compiler_semantics_gates": compiler_gates,
        "validated": True,
    }


def classify_identity(
    *,
    answer: str,
    prompt_tokens: int,
    generated_sha256: str,
    retained_tokens: int,
    schema_valid: bool,
    eos_observed: bool,
) -> dict[str, Any]:
    utility_passed = (
        schema_valid
        and eos_observed
        and answer == EXPECTED_ANSWER
        and prompt_tokens == EXPECTED_PROMPT_TOKENS
    )
    if (
        utility_passed
        and generated_sha256 == WINDOWS_GENERATED_SHA256
        and retained_tokens == WINDOWS_RETAINED_TOKENS
    ):
        classification = "HISTORICAL_WINDOWS_TASK_A_TRAJECTORY_RECOVERED"
        prospectively_reusable = True
    elif (
        utility_passed
        and generated_sha256 == LINUX_0088_GENERATED_SHA256
        and retained_tokens == LINUX_0088_RETAINED_TOKENS
    ):
        classification = "NATIVE_LINUX_0088_TASK_A_TRAJECTORY_REPLICATED"
        prospectively_reusable = True
    elif utility_passed:
        classification = "NEW_CORRECT_LINUX_TRAJECTORY_REQUIRES_PROSPECTIVE_REPLICATION"
        prospectively_reusable = False
    else:
        classification = "TASK_A_UTILITY_OR_PROMPT_IDENTITY_FAILED"
        prospectively_reusable = False
    return {
        "classification": classification,
        "utility_passed": utility_passed,
        "prospectively_reusable_for_next_experiment": prospectively_reusable,
    }


def compiler_contract_identity(
    binary: Path,
    compiler_contract: Path,
    runtime_manifest: Path,
) -> dict[str, Any]:
    compiler = compiler_contract.resolve(strict=True)
    require(os.access(compiler, os.X_OK), "compiler contract is not executable")
    build_root = binary.parent.parent.resolve(strict=True)
    cache = build_root / "CMakeCache.txt"
    commands = build_root / "compile_commands.json"
    require(cache.is_file(), "candidate CMake cache is missing")
    require(commands.is_file(), "candidate compile commands are missing")
    cache_text = cache.read_text(encoding="utf-8", errors="replace")
    command_text = commands.read_text(encoding="utf-8", errors="replace")
    require(str(compiler) in cache_text, "candidate compiler contract changed")
    require(str(compiler) in command_text, "CUDA compile commands bypass compiler contract")
    require("-use_fast_math" in command_text, "upstream CUDA fast-math intent changed")
    cuda_objects = list(
        build_root.glob("ggml/src/ggml-cuda/CMakeFiles/ggml-cuda.dir/**/*.cu.o")
    )
    require(len(cuda_objects) == 139, "target CUDA translation-unit count changed")
    manifest = validate_runtime_manifest(
        binary=binary,
        compiler_contract=compiler,
        manifest_path=runtime_manifest,
    )
    return {
        "path": str(compiler),
        "bytes": compiler.stat().st_size,
        "sha256": harness.live_runtime.sha256_file(compiler),
        "cmake_cache_sha256": harness.live_runtime.sha256_file(cache),
        "compile_commands_sha256": harness.live_runtime.sha256_file(commands),
        "cuda_translation_units": len(cuda_objects),
        "causal_change": (
            "Clang -ffast-math remains exact on the CUDA device compilation "
            "but is removed from each .cu host compilation via -Xarch_device"
        ),
        "runtime_manifest": manifest,
    }


def acquire_lock(path: Path, expected_commit: str) -> dict[str, Any]:
    payload = {
        "id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "expected_commit": expected_commit,
        "pid": os.getpid(),
        "created_unix_ns": time.time_ns(),
        "meaning": "exclusive Task-A identity-qualification launch custody",
        "retry_policy": (
            "same identity may be repaired only if post-stop evidence proves "
            "zero scientific contact"
        ),
    }
    return {**terminal.write_exclusive_json(path, payload), "payload": payload}


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


def require_pushed_frontier_head(expected_commit: str) -> None:
    remote_head = subprocess.check_output(
        [
            "git",
            "rev-parse",
            "refs/remotes/origin/codex/catalytic-frontier",
        ],
        cwd=ROOT,
        text=True,
    ).strip()
    require(
        remote_head == expected_commit,
        "0089 execution commit is not the pushed frontier head",
    )


def scientific_contact_from_evidence(
    *,
    response_bytes: int,
    server_prompt_evaluations: int,
    transport_attempted: bool,
) -> bool:
    require(
        response_bytes >= 0 and server_prompt_evaluations >= 0,
        "scientific contact evidence is negative",
    )
    return (
        transport_attempted
        or response_bytes > 0
        or server_prompt_evaluations > 0
    )


def closure_evidence_passed(
    *,
    cleanup: Mapping[str, Any],
    lock_release: Mapping[str, Any],
    cleanup_errors: list[dict[str, str]],
) -> bool:
    return (
        cleanup.get("candidate_stopped") is True
        and cleanup.get("port_free") is True
        and lock_release.get("released") is True
        and not cleanup_errors
    )


def adjudicate_scientific_contact(
    *,
    progress: dict[str, Any],
    sidecar: linux_sidecar.LinuxSidecar,
) -> dict[str, Any]:
    log_path = sidecar.run_root / "server.log"
    log_text = (
        log_path.read_text(encoding="utf-8", errors="replace")
        if log_path.is_file()
        else ""
    )
    prompt_evaluations = log_text.count("new prompt, n_ctx_slot")
    raw_path = sidecar.run_root / "task-a.raw.sse"
    persisted_raw_bytes = raw_path.stat().st_size if raw_path.is_file() else 0
    captured_raw = progress.get("raw_response_capture")
    captured_raw_bytes = (
        int(captured_raw.get("bytes") or 0)
        if isinstance(captured_raw, Mapping)
        else 0
    )
    response_bytes = max(
        int(progress.get("response_bytes_observed") or 0),
        captured_raw_bytes,
        persisted_raw_bytes,
    )
    transport_attempted = progress.get("transport_attempted") is True
    observed = scientific_contact_from_evidence(
        response_bytes=response_bytes,
        server_prompt_evaluations=prompt_evaluations,
        transport_attempted=transport_attempted,
    )
    adjudication = {
        "observed": observed,
        "response_bytes_observed": response_bytes,
        "transport_attempted": transport_attempted,
        "server_prompt_evaluations": prompt_evaluations,
        "meaning": (
            "scientific contact requires attempted completion transport, "
            "response bytes, or server prompt evaluation; request intent "
            "alone does not consume 0089"
        ),
    }
    progress["scientific_contact"] = observed
    progress["scientific_contact_adjudication"] = adjudication
    return adjudication


def evaluate(
    *,
    sidecar: linux_sidecar.LinuxSidecar,
    codec: Any,
    props: Mapping[str, Any],
    prepared: Mapping[str, Any],
    progress: dict[str, Any],
) -> dict[str, Any]:
    raw_path = sidecar.run_root / "task-a.raw.sse"
    recorder = RawResponseRecorder(raw_path, progress)
    try:
        task = harness.run_completion(
            RequestAttemptSidecar(sidecar, progress),
            f"{EXPERIMENT_ID}:task-a",
            prepared["payload"],
            recorder=recorder,
        )
    finally:
        recorder.close()
    progress["task_a_capture"] = {
        "content": task["content"],
        "prompt_tokens": task["prompt_tokens"],
        "cached_prompt_tokens": task["cached_prompt_tokens"],
        "completion_tokens": task["completion_tokens"],
        "wall_seconds": task["wall_seconds"],
        "execution": task["execution"],
    }
    try:
        parsed = {
            **harness.carrier.parse_task_a_output(task["content"]),
            "schema_valid": True,
        }
    except Exception as exc:
        parsed = {
            "state": [],
            "answer": "",
            "schema_valid": False,
            "parse_error_type": type(exc).__name__,
            "parse_error": str(exc),
        }
    retained = harness.carrier.derive_retained_root(
        harness.root_capture(task, prepared["payload"]),
        prepared["prompt_tokens"],
        codec,
        props,
    )
    progress["retained_root_capture"] = {
        "retained_root_token_count": retained["retained_root_token_count"],
        "retained_root_token_sha256": canonical_sha256(
            retained["retained_root_tokens"]
        ),
    }
    execution = task["execution"]
    generated = execution.get("generated_token_ids")
    require(
        isinstance(generated, list)
        and generated
        and all(type(token) is int for token in generated),
        "generated token evidence is invalid",
    )
    generated_sha256 = canonical_sha256(generated)
    require(
        generated_sha256 == execution.get("generated_token_sha256"),
        "generated token hash evidence changed",
    )
    prompt_count = int(task["prompt_tokens"])
    retained_count = int(retained["retained_root_token_count"])
    stop_evidence = execution.get("terminal_stop_evidence")
    eos_observed = (
        isinstance(stop_evidence, Mapping)
        and stop_evidence.get("stop_type") == "eos"
    )
    identity = classify_identity(
        answer=str(parsed["answer"]),
        prompt_tokens=prompt_count,
        generated_sha256=generated_sha256,
        retained_tokens=retained_count,
        schema_valid=bool(parsed["schema_valid"]),
        eos_observed=eos_observed,
    )
    branch_candidate: dict[str, Any]
    if identity["utility_passed"]:
        branch_tokens, _ = latency.branch_request(
            codec,
            retained,
            prepared["spec"],
            cache_prompt=False,
        )
        branch_candidate = {
            "available": True,
            "meaning": (
                "offline identity candidate only; no branch request was sent and "
                "the next experiment must pin this before model contact"
            ),
            "token_count": len(branch_tokens),
            "token_sha256": canonical_sha256(branch_tokens),
        }
    else:
        branch_candidate = {
            "available": False,
            "meaning": "utility failure forbids successor identity derivation",
        }
    resources = sidecar.resource_snapshot(None)
    log_path = Path(str(sidecar.readiness["log_path"]))
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    forbidden_markers = {
        "root_save": "root-save" in log_text,
        "root_restore": "root-restore" in log_text,
        "root_erase": "root-erase" in log_text,
        "live_capture": "one-use live terminal boundary captured" in log_text,
        "live_sample": "one-use live terminal boundary sampled" in log_text,
    }
    evidence_gates = {
        "task_a_prompt_count_exact": prompt_count == EXPECTED_PROMPT_TOKENS,
        "generated_hash_recomputed": True,
        "no_root_or_live_boundary_operation": not any(forbidden_markers.values()),
        "one_model_request_only": log_text.count("new prompt, n_ctx_slot") == 1,
        "bounded_gpu_residency": (
            isinstance(resources.get("peak_gpu_dedicated_bytes"), int)
            and 0 < int(resources["peak_gpu_dedicated_bytes"])
            <= linux_sidecar.VRAM_CEILING_BYTES
        ),
        "bounded_host_growth": (
            resources.get("host_rss_growth_bytes") is None
            or int(resources["host_rss_growth_bytes"])
            <= linux_sidecar.HOST_GROWTH_CEILING_BYTES
        ),
    }
    require(all(evidence_gates.values()), "0089 evidence-integrity gate failed")
    utility_gates = {
        "task_a_schema_valid": bool(parsed["schema_valid"]),
        "task_a_answer_correct": parsed["answer"] == EXPECTED_ANSWER,
        "task_a_state_count_four": (
            isinstance(parsed.get("state"), list) and len(parsed["state"]) == 4
        ),
        "task_a_eos_observed": eos_observed,
    }
    verdict = (
        "accept"
        if identity["prospectively_reusable_for_next_experiment"]
        else "reject"
        if identity["classification"] == "TASK_A_UTILITY_OR_PROMPT_IDENTITY_FAILED"
        else "inconclusive"
    )
    return {
        "id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "complete",
        "verdict": verdict,
        "classification": identity["classification"],
        "hypothesis": (
            "Restricting 0088's unchanged device fast-math flags to the CUDA "
            "device compilation will "
            "determine whether 0088's correct 607-token Task-A trajectory was "
            "caused by broad host/device fast math, repeats as a reusable Linux "
            "identity, or returns to the authenticated Windows Task-A identity."
        ),
        "restoration_class": RESTORATION_CLASS,
        "task_a": {
            "content": task["content"],
            "parsed": parsed,
            "prompt_tokens": prompt_count,
            "prompt_token_sha256": canonical_sha256(
                prepared["prompt_tokens"]
            ),
            "payload_sha256": canonical_sha256(prepared["payload"]),
            "cached_prompt_tokens": task["cached_prompt_tokens"],
            "completion_tokens": task["completion_tokens"],
            "generated_token_ids": generated,
            "generated_token_sha256": generated_sha256,
            "retained_root_token_count": retained_count,
            "retained_root_token_sha256": canonical_sha256(
                retained["retained_root_tokens"]
            ),
            "wall_seconds": task["wall_seconds"],
            "execution": execution,
        },
        "derived_next_request_candidate": branch_candidate,
        "identity_classification": identity,
        "forbidden_operation_markers": forbidden_markers,
        "evidence_integrity_gates": evidence_gates,
        "scientific_utility_gates": utility_gates,
        "resources_before_process_closure": resources,
        "claim_ceiling": (
            "One native-Linux CUDA Task-A output-identity qualification with "
            "correct utility and bounded residency. No live-terminal, root, "
            "restoration, phase-resource, speed, catalytic-leverage, or "
            "unbounded-inference claim."
        ),
        "automatic_promotion": False,
        "research_goal_blocked": False,
        "next_boundary": (
            "PIN_THE_QUALIFIED_LINUX_TASK_AND_DERIVED_BRANCH_IDENTITIES_BEFORE_"
            "A_DISTINCT_LIVE_TERMINAL_SUCCESSOR; IF_NOVEL_FIRST_REPLICATE_IT"
        ),
    }


def static_audit(
    binary: Path,
    compiler_contract: Path,
    runtime_manifest: Path,
) -> dict[str, Any]:
    source = Path(__file__).read_text(encoding="utf-8")
    runtime_source = source[: source.index("def static_audit(")]
    main_source = source[source.rindex("def main() -> int:") :]
    gates = {
        "task_a_only": runtime_source.count("harness.run_completion(") == 1,
        "no_root_operation": "root_action(" not in runtime_source,
        "no_live_boundary_operation": "run_live_sequence" not in runtime_source,
        "two_prior_identities_predeclared": (
            WINDOWS_GENERATED_SHA256 in runtime_source
            and LINUX_0088_GENERATED_SHA256 in runtime_source
        ),
        "novel_identity_requires_replication": (
            "NEW_CORRECT_LINUX_TRAJECTORY_REQUIRES_PROSPECTIVE_REPLICATION"
            in runtime_source
        ),
        "failure_preserves_exact_task_and_retained_capture": (
            'progress["task_a_capture"]' in runtime_source
            and 'progress["retained_root_capture"]' in runtime_source
            and "RawResponseRecorder(raw_path, progress)" in runtime_source
            and "persisted_raw_bytes = raw_path.stat().st_size"
            in runtime_source
        ),
        "transport_attempt_precedes_completion_callback": (
            runtime_source.index('progress["transport_attempted"] = True')
            < runtime_source.index("return callback()")
        ),
        "properties_resolved_before_consumption_marker": (
            main_source.index("props = codec.props()")
            < main_source.index(
                'run_root / "request-intent.json"',
            )
        ),
        "prompt_hash_required_before_request_intent": (
            main_source.index("EXPECTED_PROMPT_TOKEN_SHA256")
            < main_source.index('run_root / "request-intent.json"')
        ),
        "pushed_head_required_before_sidecar": (
            main_source.index("require_pushed_frontier_head(")
            < main_source.index("readiness = sidecar.launch()")
        ),
        "sidecar_constructor_precedes_lock": (
            main_source.index("sidecar = linux_sidecar.LinuxSidecar(")
            < main_source.index("lock = acquire_lock(")
        ),
        "no_restoration_claim": RESTORATION_CLASS in runtime_source,
        "output_after_cleanup": (
            main_source.index("cleanup = sidecar.stop()")
            < main_source.index('result["cleanup"] = cleanup')
            < main_source.index("terminal.write_exclusive_json(output, result)")
        ),
        "no_permanent_file_deletion": all(
            token not in runtime_source
            for token in ("rmtree", ".unlink(", "os.remove", "rmdir(")
        ),
    }
    require(all(gates.values()), "0089 static audit failed")
    return {
        "id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "gates": gates,
        "compiler_contract": compiler_contract_identity(
            binary,
            compiler_contract,
            runtime_manifest,
        ),
        "linux_sidecar": linux_sidecar.static_audit(),
        "cuda_linked": live_pipeline.cuda_linked(binary),
        "controller_sha256": harness.live_runtime.sha256_file(Path(__file__)),
        "scientific_contact": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--static-only", action="store_true")
    mode.add_argument("--execute-once", action="store_true")
    mode.add_argument("--print-runtime-manifest", action="store_true")
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument(
        "--compiler-contract",
        type=Path,
        default=DEFAULT_COMPILER_CONTRACT,
    )
    parser.add_argument(
        "--runtime-manifest",
        type=Path,
        default=DEFAULT_RUNTIME_MANIFEST,
    )
    parser.add_argument("--runtime-source-commit")
    parser.add_argument("--expected-commit")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--active-lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--run-parent", type=Path, default=DEFAULT_RUN_PARENT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    binary = args.binary.resolve(strict=True)
    compiler_contract = args.compiler_contract.resolve(strict=True)
    if args.print_runtime_manifest:
        require(
            args.runtime_source_commit is not None,
            "--runtime-source-commit is required for manifest generation",
        )
        print(
            json.dumps(
                runtime_manifest_template(
                    binary=binary,
                    compiler_contract=compiler_contract,
                    runtime_source_commit=args.runtime_source_commit,
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    runtime_manifest = args.runtime_manifest.resolve(strict=True)
    static = static_audit(binary, compiler_contract, runtime_manifest)
    if args.static_only:
        print(json.dumps(static, indent=2, sort_keys=True))
        return 0

    require(args.expected_commit is not None, "--expected-commit is required")
    require(
        live_pipeline.cuda_linked(binary),
        "0089 execution requires a CUDA-linked Linux binary",
    )
    output = args.output.resolve(strict=False)
    require(not output.exists(), "0089 result already exists")
    lock_path = args.active_lock.resolve(strict=False)
    run_root = (
        args.run_parent.resolve(strict=False)
        / f"{EXPERIMENT_ID}-{time.time_ns()}"
    )
    sidecar = linux_sidecar.LinuxSidecar(
        binary=binary,
        model=args.model,
        run_root=run_root,
    )
    lock = acquire_lock(lock_path, args.expected_commit)
    result: dict[str, Any] | None = None
    caught: BaseException | None = None
    cleanup: dict[str, Any] = {}
    progress: dict[str, Any] = {"scientific_contact": False}
    try:
        terminal.require_clean_head(ROOT, args.expected_commit)
        require_pushed_frontier_head(args.expected_commit)
        readiness = sidecar.launch()
        codec = harness.carrier.SidecarPromptCodec(linux_sidecar.PORT)
        corpus = harness.carrier.load_public_corpus(ROOT)
        roots = {str(item["root_id"]): item for item in corpus["roots"]}
        prepared = terminal.prepare_task_and_branch(
            codec,
            roots[terminal.ROOT_ID],
        )
        props = codec.props()
        prepared_identity = {
            "prompt_token_count": len(prepared["prompt_tokens"]),
            "prompt_token_sha256": canonical_sha256(prepared["prompt_tokens"]),
            "payload_sha256": canonical_sha256(prepared["payload"]),
        }
        require(
            prepared_identity["prompt_token_count"] == EXPECTED_PROMPT_TOKENS
            and prepared_identity["prompt_token_sha256"]
            == EXPECTED_PROMPT_TOKEN_SHA256,
            "Task-A prompt identity changed before contact",
        )
        require(
            prepared_identity["payload_sha256"] == EXPECTED_PAYLOAD_SHA256,
            "Task-A payload identity changed before contact",
        )
        request_intent = terminal.write_exclusive_json(
            run_root / "request-intent.json",
            {
                "id": EXPERIMENT_ID,
                "attempt_id": ATTEMPT_ID,
                "expected_commit": args.expected_commit,
                "created_unix_ns": time.time_ns(),
                "meaning": (
                    "Task-A model request is next; this intent alone is not "
                    "proof of scientific contact"
                ),
                "retry_allowed_if_no_contact_is_adjudicated": True,
                "prepared_identity": prepared_identity,
            },
        )
        progress = {
            "scientific_contact": False,
            "request_intent": request_intent,
            "prepared_identity": prepared_identity,
        }
        result = evaluate(
            sidecar=sidecar,
            codec=codec,
            props=props,
            prepared=prepared,
            progress=progress,
        )
        result["candidate_commit"] = args.expected_commit
        result["readiness"] = readiness
        result["static_evidence"] = static
        result["launch_lock"] = lock
        result["request_intent"] = request_intent
    except BaseException as exc:
        caught = exc
    finally:
        cleanup_errors: list[dict[str, str]] = []
        try:
            cleanup = sidecar.stop()
        except BaseException as exc:
            cleanup = {
                "candidate_stopped": False,
                "port_free": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            cleanup_errors.append(
                {
                    "operation": "sidecar.stop",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
        try:
            lock_release = release_lock(lock_path)
        except BaseException as exc:
            lock_release = {
                "released": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            cleanup_errors.append(
                {
                    "operation": "release_lock",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
        try:
            contact_adjudication = adjudicate_scientific_contact(
                progress=progress,
                sidecar=sidecar,
            )
        except BaseException as exc:
            conservative_contact = (
                progress.get("transport_attempted") is True
                or bool(progress.get("response_bytes_observed"))
            )
            contact_adjudication = {
                "observed": conservative_contact,
                "adjudication_failed": True,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "meaning": (
                    "contact adjudication failure is consuming only after "
                    "transport attempt or observed response bytes"
                ),
            }
            progress["scientific_contact"] = conservative_contact
            progress["scientific_contact_adjudication"] = contact_adjudication
            cleanup_errors.append(
                {
                    "operation": "adjudicate_scientific_contact",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    closure_passed = closure_evidence_passed(
        cleanup=cleanup,
        lock_release=lock_release,
        cleanup_errors=cleanup_errors,
    )
    if caught is None and not closure_passed:
        caught = ExperimentError("0089 process or lock closure failed")

    if caught is not None:
        failure = {
            "id": EXPERIMENT_ID,
            "attempt_id": ATTEMPT_ID,
            "status": "failed",
            "error_type": type(caught).__name__,
            "error": str(caught),
            "progress": progress,
            "cleanup": cleanup,
            "cleanup_errors": cleanup_errors,
            "result_before_cleanup": result,
            "launch_lock": lock,
            "launch_lock_release": lock_release,
            "scientific_contact": contact_adjudication,
            "automatic_promotion": False,
        }
        failure_output = (
            output
            if contact_adjudication["observed"]
            else args.run_parent.resolve(strict=False)
            / f"{EXPERIMENT_ID}-precontact-{time.time_ns()}.json"
        )
        terminal.write_exclusive_json(failure_output, failure)
        raise ExperimentError(
            f"0089 failed; evidence preserved at {failure_output}"
        ) from caught

    require(result is not None, "0089 result is missing")
    result["cleanup"] = cleanup
    result["launch_lock_release"] = lock_release
    result["scientific_contact"] = contact_adjudication
    result["artifact"] = terminal.write_exclusive_json(output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
