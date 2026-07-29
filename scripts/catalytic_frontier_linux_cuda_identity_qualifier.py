#!/usr/bin/env python3
"""neo-exp-0089: qualify one corrected native-Linux CUDA output identity."""
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
import catalytic_frontier_live_terminal_pipeline as live_pipeline
import catalytic_frontier_single_request_latency as latency
import catalytic_frontier_terminal_logits_continuation as terminal


EXPERIMENT_ID = "neo-exp-0089"
ATTEMPT_ID = "frontier-attempt-0129"
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
RESTORATION_CLASS = "NO_RESTORATION_CLAIM"
DEFAULT_BINARY = ROOT / "build" / "linux-cuda-0089-gpufast" / "bin" / "llama-server"
DEFAULT_MODEL = live_pipeline.DEFAULT_MODEL
DEFAULT_COMPILER_CONTRACT = (
    ROOT / "build" / "linux-toolchain-0088" / "cuda-clang-gpufast++"
)
DEFAULT_OUTPUT = ROOT / "lab" / f"{EXPERIMENT_ID}.local.json"
DEFAULT_LOCK = (
    ROOT / "build" / "linux-catalytic" / f"{EXPERIMENT_ID}.active-lock.json"
)
DEFAULT_RUN_PARENT = ROOT / "build" / "linux-catalytic"


class ExperimentError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ExperimentError(message)


def canonical_sha256(value: Any) -> str:
    return harness.sha256_bytes(harness.carrier.canonical_json_bytes(value))


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


def compiler_contract_identity(binary: Path, compiler_contract: Path) -> dict[str, Any]:
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
    }


def acquire_lock(path: Path, expected_commit: str) -> dict[str, Any]:
    payload = {
        "id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "expected_commit": expected_commit,
        "pid": os.getpid(),
        "created_unix_ns": time.time_ns(),
        "meaning": "exclusive Task-A identity-qualification launch custody",
        "retry_allowed": False,
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


def evaluate(
    *,
    sidecar: linux_sidecar.LinuxSidecar,
    codec: Any,
    props: Mapping[str, Any],
    prepared: Mapping[str, Any],
    progress: dict[str, Any],
) -> dict[str, Any]:
    task = harness.run_completion(
        sidecar,
        f"{EXPERIMENT_ID}:task-a",
        prepared["payload"],
    )
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


def static_audit(binary: Path, compiler_contract: Path) -> dict[str, Any]:
    source = Path(__file__).read_text(encoding="utf-8")
    runtime_source = source[: source.index("def static_audit(")]
    main_source = source[source.index("def main()") :]
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
        ),
        "properties_resolved_before_consumption_marker": (
            main_source.index("props = codec.props()")
            < main_source.index(
                'run_root / "scientific-contact.json"',
            )
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
        "compiler_contract": compiler_contract_identity(binary, compiler_contract),
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
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument(
        "--compiler-contract",
        type=Path,
        default=DEFAULT_COMPILER_CONTRACT,
    )
    parser.add_argument("--expected-commit")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--active-lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--run-parent", type=Path, default=DEFAULT_RUN_PARENT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    binary = args.binary.resolve(strict=True)
    compiler_contract = args.compiler_contract.resolve(strict=True)
    static = static_audit(binary, compiler_contract)
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
    lock = acquire_lock(lock_path, args.expected_commit)
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
    progress: dict[str, Any] = {"scientific_contact": False}
    try:
        terminal.require_clean_head(ROOT, args.expected_commit)
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
        contact = terminal.write_exclusive_json(
            run_root / "scientific-contact.json",
            {
                "id": EXPERIMENT_ID,
                "attempt_id": ATTEMPT_ID,
                "expected_commit": args.expected_commit,
                "created_unix_ns": time.time_ns(),
                "meaning": "Task-A model request is next; identity is consumed",
                "retry_allowed": False,
                "prepared_identity": prepared_identity,
            },
        )
        progress = {
            "scientific_contact": True,
            "contact": contact,
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
        result["scientific_contact"] = contact
    except BaseException as exc:
        caught = exc
    finally:
        cleanup = sidecar.stop()
        lock_release = release_lock(lock_path)

    if caught is not None:
        failure = {
            "id": EXPERIMENT_ID,
            "attempt_id": ATTEMPT_ID,
            "status": "failed",
            "error_type": type(caught).__name__,
            "error": str(caught),
            "progress": progress,
            "cleanup": cleanup,
            "launch_lock": lock,
            "launch_lock_release": lock_release,
            "scientific_contact_requires_log_adjudication": progress[
                "scientific_contact"
            ],
            "automatic_promotion": False,
        }
        failure_output = (
            output
            if progress["scientific_contact"]
            else args.run_parent.resolve(strict=False)
            / f"{EXPERIMENT_ID}-precontact-{time.time_ns()}.json"
        )
        terminal.write_exclusive_json(failure_output, failure)
        raise ExperimentError(
            f"0089 failed; evidence preserved at {failure_output}"
        ) from caught

    require(result is not None, "0089 result is missing")
    require(
        cleanup.get("candidate_stopped") is True
        and cleanup.get("port_free") is True,
        "0089 process closure failed",
    )
    result["cleanup"] = cleanup
    result["launch_lock_release"] = lock_release
    result["artifact"] = terminal.write_exclusive_json(output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
