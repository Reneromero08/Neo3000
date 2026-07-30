#!/usr/bin/env python3
"""Build, execute, and bind native realignment selftests without model contact."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def linked_inputs(binary: Path) -> list[dict[str, Any]]:
    completed = subprocess.run(
        ["ldd", str(binary)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    identities: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        payload = line.partition("=>")[2] if "=>" in line else line
        text = payload.rsplit(" (", 1)[0].strip()
        if not text.startswith("/"):
            continue
        path = Path(text).resolve(strict=True)
        identities.append(
            {
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return sorted(identities, key=lambda value: value["path"])


def run_bound_test(
    *,
    compiler: Path,
    build_dir: Path,
    name: str,
    sources: list[Path],
    definitions: list[str],
) -> dict[str, Any]:
    binary = build_dir / name
    command = [
        str(compiler),
        "-std=c++17",
        "-O0",
        "-g",
        "-UNDEBUG",
        "-fno-omit-frame-pointer",
        "-fsanitize=address,undefined",
        *definitions,
        *(
            str(source)
            for source in sources
            if source.suffix in {".cc", ".cpp", ".cxx"}
        ),
        "-o",
        str(binary),
    ]
    compile_result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if compile_result.returncode != 0:
        raise RuntimeError(
            f"{name} compile failed:\n{compile_result.stdout}"
            f"{compile_result.stderr}"
        )

    environment = os.environ.copy()
    environment.update(
        {
            "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
            "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1",
        }
    )
    execution = subprocess.run(
        [str(binary)],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if execution.returncode != 0:
        raise RuntimeError(
            f"{name} execution failed:\n{execution.stdout}"
            f"{execution.stderr}"
        )

    return {
        "name": name,
        "compile_command": command,
        "assertion_mode": {
            "enabled": True,
            "compile_flag": "-UNDEBUG",
            "source_guard": "#ifdef NDEBUG -> #error",
        },
        "sanitizers": ["AddressSanitizer", "UndefinedBehaviorSanitizer"],
        "sources": [
            {
                "path": str(source.relative_to(ROOT)),
                "size_bytes": source.stat().st_size,
                "sha256": sha256_file(source),
            }
            for source in sources
        ],
        "binary": {
            "path": str(binary.relative_to(ROOT)),
            "size_bytes": binary.stat().st_size,
            "sha256": sha256_file(binary),
        },
        "dynamic_link_inputs": linked_inputs(binary),
        "compile_stdout": compile_result.stdout,
        "compile_stderr": compile_result.stderr,
        "execution_stdout": execution.stdout,
        "execution_stderr": execution.stderr,
        "returncode": execution.returncode,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=ROOT / "build" / "realignment" / "native-bound",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "build"
        / "realignment"
        / "native-test-binding.json",
    )
    args = parser.parse_args()

    compiler_text = shutil.which("c++")
    if compiler_text is None:
        raise RuntimeError("c++ compiler not found")
    compiler = Path(compiler_text).resolve(strict=True)
    compiler_version = subprocess.check_output(
        [str(compiler), "--version"],
        text=True,
        stderr=subprocess.STDOUT,
    )

    build_dir = args.build_dir.resolve(strict=False)
    output = args.output.resolve(strict=False)
    build_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)

    carrier_source = ROOT / "tools/server/neo3000-twin-rail-fiber.cpp"
    carrier_header = ROOT / "tools/server/neo3000-twin-rail-fiber.h"
    records = [
        run_bound_test(
            compiler=compiler,
            build_dir=build_dir,
            name="twin-rail-calibration-selftest-asan-ubsan",
            sources=[
                ROOT
                / "scripts"
                / "catalytic_frontier_twin_rail_runtime_selftest.cpp",
                carrier_source,
                carrier_header,
            ],
            definitions=["-DNEO3000_TWIN_RAIL_TESTING"],
        ),
        run_bound_test(
            compiler=compiler,
            build_dir=build_dir,
            name="two-row-calibration-selftest-asan-ubsan",
            sources=[
                ROOT
                / "scripts"
                / "catalytic_frontier_two_evidence_twin_rail_selftest.cpp",
                carrier_source,
                carrier_header,
            ],
            definitions=["-DNEO3000_TWIN_RAIL_TESTING"],
        ),
        run_bound_test(
            compiler=compiler,
            build_dir=build_dir,
            name="live-terminal-lifecycle-selftest-asan-ubsan",
            sources=[
                ROOT
                / "scripts"
                / "catalytic_frontier_live_terminal_lifecycle_selftest.cpp",
                ROOT
                / "tools"
                / "server"
                / "neo3000-live-terminal-lifecycle.h",
            ],
            definitions=[],
        ),
    ]

    manifest = {
        "classification": "NATIVE_REALIGNMENT_BEHAVIORAL_TEST_BINDING",
        "compiler": {
            "path": str(compiler),
            "size_bytes": compiler.stat().st_size,
            "sha256": sha256_file(compiler),
            "version": compiler_version,
        },
        "tests": records,
        "all_passed": all(record["returncode"] == 0 for record in records),
        "contact": {
            "server_contacts": 0,
            "model_callbacks": 0,
            "prompt_evaluations": 0,
            "cuda_kernel_launches": 0,
        },
    }
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output), "all_passed": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
