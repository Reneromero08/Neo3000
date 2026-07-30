#!/usr/bin/env python3
"""Linux-native isolated Neo3000 sidecar with preservation-only cleanup."""
from __future__ import annotations

import hashlib
import json
import os
import signal
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping


PORT = 9494
MODEL_SIZE = 21_166_757_632
MODEL_SHA256 = "31AEFA25B7E1EDBDE436E643E2B5E3F6E57820A4811D97B131130E48FF0772C2"
VRAM_CEILING_BYTES = 6_000 * 1024 * 1024
HOST_GROWTH_CEILING_BYTES = 4 * 1024**3


class LinuxSidecarError(RuntimeError):
    pass


class _GuardedCallbackTimeout(BaseException):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LinuxSidecarError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def parse_ldd_paths(output: str) -> set[Path]:
    paths: set[Path] = set()
    for line in output.splitlines():
        payload = line.partition("=>")[2] if "=>" in line else line
        target = payload.rsplit(" (", 1)[0].strip()
        if target.startswith("/"):
            paths.add(Path(target).resolve(strict=True))
    return paths


def linked_library_identities(binary: Path) -> dict[str, dict[str, Any]]:
    completed = subprocess.run(
        ["ldd", str(binary)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    require(completed.returncode == 0, "Unable to resolve candidate libraries")
    paths = parse_ldd_paths(completed.stdout)
    identities = {
        str(path): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(paths)
    }
    require(
        any(Path(path).name == "libllama-server-impl.so" for path in identities),
        "Candidate server implementation library is not linked",
    )
    return identities


def health_ok(port: int, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/health",
            timeout=timeout,
        ) as response:
            return response.status == 200
    except Exception:
        return False


def port_accepts_connections(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.25)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def listener_inodes(port: int) -> set[str]:
    port_hex = f"{port:04X}"
    result: set[str] = set()
    for table in (Path("/proc/net/tcp"), Path("/proc/net/tcp6")):
        if not table.is_file():
            continue
        for line in table.read_text(encoding="utf-8").splitlines()[1:]:
            fields = line.split()
            if (
                len(fields) >= 10
                and fields[1].rsplit(":", 1)[-1].upper() == port_hex
                and fields[3] == "0A"
            ):
                result.add(fields[9])
    return result


def pid_owns_listener(pid: int, port: int) -> bool:
    inodes = listener_inodes(port)
    if not inodes:
        return False
    fd_root = Path(f"/proc/{pid}/fd")
    if not fd_root.is_dir():
        return False
    for descriptor in fd_root.iterdir():
        try:
            target = os.readlink(descriptor)
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if target.startswith("socket:[") and target[8:-1] in inodes:
            return True
    return False


def proc_rss_bytes(pid: int) -> int | None:
    status = Path(f"/proc/{pid}/status")
    if not status.is_file():
        return None
    for line in status.read_text(encoding="utf-8").splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    return None


def nvidia_process_bytes(pid: int) -> int | None:
    completed = subprocess.run(
        [
            "nvidia-smi",
            "--query-compute-apps=pid,used_memory",
            "--format=csv,noheader,nounits",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if completed.returncode != 0:
        return None
    for line in completed.stdout.splitlines():
        values = [value.strip() for value in line.split(",")]
        if len(values) == 2 and values[0].isdigit() and int(values[0]) == pid:
            return int(values[1]) * 1024 * 1024
    return 0


class LinuxSidecar:
    def __init__(
        self,
        *,
        binary: Path,
        model: Path,
        run_root: Path,
        port: int = PORT,
        readiness_seconds: float = 300.0,
    ):
        self.binary = binary.resolve(strict=True)
        self.model = model.resolve(strict=True)
        self.run_root = run_root.resolve(strict=False)
        self.port = port
        self.readiness_seconds = readiness_seconds
        self.process: subprocess.Popen[str] | None = None
        self.log_handle: Any | None = None
        self.readiness: dict[str, Any] = {}
        self.samples: list[dict[str, Any]] = []
        self.baseline_rss_bytes: int | None = None

    def verify_identities(self) -> dict[str, Any]:
        require(self.binary.is_file(), "Linux candidate binary is missing")
        require(self.model.is_file(), "Agents-A1 model is missing")
        require(
            self.model.stat().st_size == MODEL_SIZE,
            "Agents-A1 model size changed",
        )
        model_sha256 = sha256_file(self.model)
        require(model_sha256 == MODEL_SHA256, "Agents-A1 model hash changed")
        version = subprocess.check_output(
            [str(self.binary), "--version"],
            cwd=self.binary.parent,
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
        return {
            "binary": {
                "path": str(self.binary),
                "sha256": sha256_file(self.binary),
                "version": version,
                "linked_libraries": linked_library_identities(self.binary),
            },
            "model": {
                "path": str(self.model),
                "size_bytes": MODEL_SIZE,
                "sha256": model_sha256,
            },
        }

    def launch_args(self) -> list[str]:
        return [
            str(self.binary),
            "--model",
            str(self.model),
            "--alias",
            "agents-a1-holostate",
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "--parallel",
            "1",
            "--ctx-size",
            "16384",
            "--threads",
            "12",
            "--threads-batch",
            "12",
            "--batch-size",
            "512",
            "--ubatch-size",
            "128",
            "--gpu-layers",
            "auto",
            "--flash-attn",
            "auto",
            "--cache-type-k",
            "f16",
            "--cache-type-v",
            "f16",
            "--cpu-moe",
            "--cache-prompt",
            "--metrics",
            "--no-webui",
            "--reasoning",
            "auto",
            "--ctx-checkpoints",
            "0",
            "--checkpoint-min-step",
            "512",
            "--cache-ram",
            "4096",
            "--cache-idle-slots",
            "--cache-ram-root-device",
        ]

    def launch(self) -> dict[str, Any]:
        require(self.process is None, "Linux sidecar already launched")
        require(not port_accepts_connections(self.port), "candidate port is occupied")
        identities = self.verify_identities()
        self.run_root.mkdir(parents=True, exist_ok=False)
        log_path = self.run_root / "server.log"
        self.log_handle = log_path.open("xb")
        env = os.environ.copy()
        env.update(
            {
                "TMP": str(self.run_root),
                "TEMP": str(self.run_root),
                "TMPDIR": str(self.run_root),
                "LLAMA_ARG_LOG_VERBOSITY": "1000",
                "LLAMA_SERVER_SLOTS_DEBUG": "1",
            }
        )
        command = [
            "nice",
            "-n",
            "10",
            "ionice",
            "-c",
            "2",
            "-n",
            "7",
            *self.launch_args(),
        ]
        started = time.monotonic()
        self.process = subprocess.Popen(
            command,
            cwd=self.binary.parent,
            env=env,
            stdout=self.log_handle,
            stderr=subprocess.STDOUT,
            close_fds=True,
        )
        deadline = started + self.readiness_seconds
        try:
            while True:
                require(
                    self.process.poll() is None,
                    "Linux sidecar exited before readiness",
                )
                if (
                    health_ok(self.port)
                    and pid_owns_listener(self.process.pid, self.port)
                ):
                    break
                require(
                    time.monotonic() < deadline,
                    "Linux sidecar readiness timeout",
                )
                time.sleep(0.25)
        except BaseException:
            self.stop()
            raise
        self.baseline_rss_bytes = proc_rss_bytes(self.process.pid)
        self._sample("ready")
        self.readiness = {
            **identities,
            "pid": self.process.pid,
            "port": self.port,
            "readiness_seconds": time.monotonic() - started,
            "log_path": str(log_path),
            "run_root": str(self.run_root),
            "launch_args": self.launch_args(),
            "priority": {"nice": 10, "ionice_class": 2, "ionice_level": 7},
            "listener_owned": True,
        }
        return dict(self.readiness)

    def _sample(self, boundary: str) -> dict[str, Any]:
        require(self.process is not None, "Linux sidecar was not launched")
        sample = {
            "boundary": boundary,
            "monotonic_ns": time.monotonic_ns(),
            "rss_bytes": proc_rss_bytes(self.process.pid),
            "dedicated_gpu_bytes": nvidia_process_bytes(self.process.pid),
        }
        self.samples.append(sample)
        gpu = sample["dedicated_gpu_bytes"]
        rss = sample["rss_bytes"]
        require(
            gpu is None or gpu <= VRAM_CEILING_BYTES,
            "Linux sidecar exceeded the GPU residency ceiling",
        )
        require(
            rss is None
            or self.baseline_rss_bytes is None
            or rss - self.baseline_rss_bytes <= HOST_GROWTH_CEILING_BYTES,
            "Linux sidecar exceeded the host growth ceiling",
        )
        return sample

    def exact_ownership(self, boundary: str) -> dict[str, Any]:
        require(self.process is not None, "Linux sidecar was not launched")
        passed = (
            self.process.poll() is None
            and pid_owns_listener(self.process.pid, self.port)
            and Path(f"/proc/{self.process.pid}/exe").resolve() == self.binary
        )
        require(passed, f"Linux sidecar ownership failed at {boundary}")
        return {
            "passed": True,
            "boundary": boundary,
            "pid": self.process.pid,
            "port": self.port,
            "binary": str(self.binary),
        }

    def guarded(
        self,
        label: str,
        callback: Callable[[], Any],
        *,
        timeout: float,
        **_kwargs: Any,
    ) -> Any:
        require(timeout > 0, "guarded callback timeout must be positive")
        require(
            threading.current_thread() is threading.main_thread(),
            "guarded callback timeout requires the main thread",
        )
        previous_timer = signal.getitimer(signal.ITIMER_REAL)
        require(
            previous_timer == (0.0, 0.0),
            "guarded callback cannot replace an existing process alarm",
        )
        previous_handler = signal.getsignal(signal.SIGALRM)

        def deadline_handler(_signum: int, _frame: Any) -> None:
            raise _GuardedCallbackTimeout()

        self.exact_ownership(f"pre:{label}")
        self._sample(f"pre:{label}")
        signal.signal(signal.SIGALRM, deadline_handler)
        signal.setitimer(signal.ITIMER_REAL, timeout)
        try:
            result = callback()
        except _GuardedCallbackTimeout:
            self._sample(f"timeout:{label}")
            self.exact_ownership(f"timeout:{label}")
            raise LinuxSidecarError(
                f"guarded callback exceeded {timeout} seconds: {label}"
            ) from None
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            signal.signal(signal.SIGALRM, previous_handler)
        self._sample(f"post:{label}")
        self.exact_ownership(f"post:{label}")
        return result

    def guarded_batch_member(
        self,
        label: str,
        callback: Callable[[], Any],
        *,
        timeout: float,
        **kwargs: Any,
    ) -> Any:
        return self.guarded(label, callback, timeout=timeout, **kwargs)

    def guarded_profiled(
        self,
        label: str,
        callback: Callable[[], Any],
        *,
        timeout: float,
        phase_observer: Callable[[str], Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        if phase_observer is not None:
            phase_observer("pre-request")
        result = self.guarded(label, callback, timeout=timeout, **kwargs)
        if phase_observer is not None:
            phase_observer("post-request")
        return result

    def telemetry(self) -> dict[str, Any]:
        gpu = [
            int(sample["dedicated_gpu_bytes"])
            for sample in self.samples
            if isinstance(sample.get("dedicated_gpu_bytes"), int)
        ]
        return {
            "peak_dedicated_bytes": max(gpu, default=None),
            "sample_count": len(self.samples),
            "failure_reason": None,
            "samples": list(self.samples),
        }

    def resource_snapshot(
        self,
        _baseline_private: int | None,
    ) -> dict[str, Any]:
        sample = self._sample("resource-snapshot")
        rss = sample["rss_bytes"]
        growth = (
            int(rss) - self.baseline_rss_bytes
            if isinstance(rss, int) and self.baseline_rss_bytes is not None
            else None
        )
        telemetry = self.telemetry()
        return {
            "host_private_bytes": None,
            "host_private_growth_bytes": None,
            "host_rss_bytes": rss,
            "host_rss_growth_bytes": growth,
            "peak_wddm_bytes": telemetry["peak_dedicated_bytes"],
            "peak_gpu_dedicated_bytes": telemetry["peak_dedicated_bytes"],
            "wddm_sample_count": telemetry["sample_count"],
            "gpu_sample_count": telemetry["sample_count"],
            "wddm_failure_reason": None,
            "gpu_failure_reason": None,
            "resource_semantics": "linux-proc-rss-plus-nvidia-compute-process",
        }

    def stop(self) -> dict[str, Any]:
        pid = self.process.pid if self.process is not None else None
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        if self.log_handle is not None:
            self.log_handle.close()
            self.log_handle = None
        port_free = not port_accepts_connections(self.port)
        return {
            "pid": pid,
            "candidate_stopped": self.process is None
            or self.process.poll() is not None,
            "port_free": port_free,
            "run_root_preserved": self.run_root.is_dir(),
            "run_root": str(self.run_root),
            "telemetry": self.telemetry(),
        }


def static_audit() -> dict[str, Any]:
    source = Path(__file__).read_text(encoding="utf-8")
    runtime_source = source[: source.index("def static_audit(")]
    gates = {
        "linux_proc_listener_ownership": "pid_owns_listener" in runtime_source,
        "loopback_only": '"127.0.0.1"' in runtime_source,
        "single_slot": '"--parallel",\n            "1"' in runtime_source,
        "checkpoint_zero": '"--ctx-checkpoints",\n            "0"' in runtime_source,
        "cuda_root_device": '"--cache-ram-root-device"' in runtime_source,
        "reduced_cpu_priority": '"nice",\n            "-n",\n            "10"' in runtime_source,
        "reduced_io_priority": '"ionice"' in runtime_source,
        "preservation_only_cleanup": (
            "rmtree" not in runtime_source
            and ".unlink(" not in runtime_source
            and "os.remove" not in runtime_source
        ),
        "exact_model_identity": MODEL_SHA256 in runtime_source,
        "exact_linked_runtime_identity": (
            "linked_library_identities(self.binary)" in runtime_source
            and '"libllama-server-impl.so"' in runtime_source
        ),
        "bounded_gpu_residency": "VRAM_CEILING_BYTES" in runtime_source,
        "guards_do_not_issue_intervening_health_requests": (
            "and health_ok(self.port)" not in runtime_source
        ),
    }
    require(
        all(gates.values()),
        "Linux sidecar static audit failed: "
        + ", ".join(key for key, value in gates.items() if not value),
    )
    return {"gates": gates, "contact": False}


if __name__ == "__main__":
    print(json.dumps(static_audit(), indent=2, sort_keys=True))
