#!/usr/bin/env python3
"""neo-exp-0090: qualify the Linux 607-bound C -> D -> B chain identities."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence, TextIO

import catalytic_frontier_fanout as shared_tasks
import catalytic_frontier_harness as harness
import catalytic_frontier_linux_cuda_identity_qualifier as runtime
import catalytic_frontier_linux_sidecar as linux_sidecar
import catalytic_frontier_output_fixed_point as fixed
import catalytic_frontier_recursive_root_promotion as rolling
import catalytic_frontier_single_request_latency as latency
import catalytic_frontier_successor_terminal_pipeline as predecessor
import catalytic_frontier_terminal_logits_continuation as terminal


EXPERIMENT_ID = "neo-exp-0090"
ATTEMPT_ID = "frontier-attempt-0131"
PREREGISTRATION_ATTEMPT_ID = "frontier-attempt-0130"
ROOT = Path(__file__).resolve().parents[1]
RESTORATION_CLASS = "NO_RESTORATION_CLAIM"
DEFAULT_BINARY = runtime.DEFAULT_BINARY
DEFAULT_MODEL = runtime.DEFAULT_MODEL
DEFAULT_OUTPUT = ROOT / "lab" / f"{EXPERIMENT_ID}.local.json"
DEFAULT_LOCK = (
    ROOT / "build" / "linux-catalytic" / f"{EXPERIMENT_ID}.active-lock.json"
)
DEFAULT_CONSUMED_MARKER = (
    ROOT / "build" / "linux-catalytic" / f"{EXPERIMENT_ID}.consumed-marker.json"
)
DEFAULT_RUN_PARENT = ROOT / "build" / "linux-catalytic"

TASK_A_CONTENT = (
    "{\n"
    '  "state": [\n'
    '    "North must remain open for hospital pressure",\n'
    '    "South must be fully closed at field stop",\n'
    '    "Bypass must be flushed and tested",\n'
    '    "Chamber pressure must read zero"\n'
    "  ],\n"
    '  "answer": "C"\n'
    "}"
)
EXPECTED_PROMPT_COUNT = 543
EXPECTED_PROMPT_SHA256 = (
    "17CC9100104C5C2C91E2BB3AA14143515F465B584427B91C4B757F5CB35336D2"
)
EXPECTED_TASK_A_GENERATED_SHA256 = (
    "CE01CEBADD2BB6454B5860B9AAFB6A2B15D34FE8D9C894825D0E6BF102481E72"
)
EXPECTED_RETAINED_COUNT = 607
EXPECTED_RETAINED_SHA256 = (
    "7DDBEEB8BFE78E0808307A53D5579800E38D2B813032DE2A881CB4375A7B8B00"
)
EXPECTED_BASE_COUNT = 684
EXPECTED_BASE_SHA256 = (
    "63E7B639BC96EEAFBE30A00D929E67105EEEAC4D9A30C33526C96B1F5F419783"
)
EXPECTED_BRANCH_COUNT = 685
EXPECTED_BRANCH_SHA256 = (
    "F1F5D9AC2DECB6439970BA4B13CB716428E059BDD457F36518F462CD4A604EFF"
)
EXPECTED_BRANCH_PAYLOAD_SHA256 = (
    "8BB7CCB9F403734CE887BAED134B1D7C90696706F8D1F706032EBA6A3EF9DD63"
)
EXPECTED_ANSWERS = ("C", "D", "B")
EXPECTED_GENERATED_SHA256 = {
    "C": "BD33E852EF9FDDEE49A1056501456071169FF3E3C7699C2A5BAAA2D0DF30CABC",
    "D": "0CA13167369ED1835BB8938644A7CCEF6EDE0BD65AE31C256931C54D3FA9FB31",
    "B": "4553BBC00B6AF27C3EBDE8F36EA9237A37B5D9C1AA182FBC65CDA71411A4B888",
}
EXPECTED_CHILD_SHA256 = {
    "C": "41DE1090B0BA1FBDAC8662F1AD8BDEBA8BFE1CC1069CD35EDF865D1E8B8E8EC1",
    "D": "1E30AAC3DD2D295292E649E6CE06F54CF0897CB4B1A5497AE826A04A664D6C55",
    "B": "D0B9225B2CBBA1434E65707DF728602B5A674A410A2CEC1D7A79408341A5BA5F",
}
EXPECTED_REQUEST_SHA256 = {
    1: "E1DDA7CD5DCE70BE9857CF26076596ACBA151A6FC7F9D862822BD9AEFA4A3B84",
    2: "4E421D91AA1916ACB1D6F735ED1FDFD989BF73B7A7EF199645079D35E4D65995",
}
EXPECTED_REQUEST_PAYLOAD_SHA256 = {
    1: "9BBDF760B204908CB414A53944254F8D1B582733BAE99F75082D49DE67AB1AA0",
    2: "87B9E12526D9B03ECFDE906BA90A970A6C33AE358ED942DB34835CC3764FBAD9",
}
EXPECTED_SUCCESSOR_COUNT = 777
EXPECTED_SUFFIX_COUNT = 87
EXPECTED_SUFFIX_SHA256 = (
    "7A0CC84CF953A11BA7780E5660346598117372EB71F460CF8DA3B545E6499BA0"
)
MAX_GPU_BYTES = 6000 * 1024 * 1024
MAX_HOST_GROWTH_BYTES = 4 * 1024 * 1024 * 1024


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


class StageAttemptSidecar:
    def __init__(
        self,
        sidecar: linux_sidecar.LinuxSidecar,
        progress: dict[str, Any],
        ordinal: int,
        consumed_marker: Path,
        expected_commit: str,
    ):
        self.sidecar = sidecar
        self.progress = progress
        self.ordinal = ordinal
        self.consumed_marker = consumed_marker
        self.expected_commit = expected_commit

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
                self.sidecar.run_root
                / f"stage-{self.ordinal}-transport-attempt.json",
                {
                    "id": EXPERIMENT_ID,
                    "attempt_id": ATTEMPT_ID,
                    "ordinal": self.ordinal,
                    "created_unix_ns": time.time_ns(),
                    "meaning": (
                        "the fixed ordinal completion transport is next; "
                        "any later ambiguity consumes this experiment"
                    ),
                },
            )
            if self.ordinal == 0:
                consumption = terminal.write_exclusive_json(
                    self.consumed_marker,
                    {
                        "id": EXPERIMENT_ID,
                        "attempt_id": ATTEMPT_ID,
                        "expected_commit": self.expected_commit,
                        "created_unix_ns": time.time_ns(),
                        "first_ordinal": 0,
                        "meaning": (
                            "stage-0 completion callback is next; this exact "
                            "experiment is conservatively consumed and may "
                            "never be launched again"
                        ),
                    },
                )
                self.progress["consumption_marker"] = consumption
            else:
                require(
                    self.consumed_marker.is_file(),
                    "later stage lost the durable consumption marker",
                )
            attempts = self.progress.setdefault("transport_attempts", [])
            attempts.append(marker)
            return callback()

        return self.sidecar.guarded(
            label,
            attempt_transport,
            timeout=timeout,
            **kwargs,
        )


def acquire_lock(path: Path, expected_commit: str) -> dict[str, Any]:
    return terminal.write_exclusive_json(
        path,
        {
            "id": EXPERIMENT_ID,
            "attempt_id": ATTEMPT_ID,
            "expected_commit": expected_commit,
            "pid": os.getpid(),
            "created_unix_ns": time.time_ns(),
            "meaning": "exclusive three-stage Linux identity-qualification custody",
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


def exact_state(codec: Any, props: Mapping[str, Any], answer: str) -> dict[str, Any]:
    require(answer in EXPECTED_ANSWERS, "expected state answer changed")
    content = f'{{"answer":"{answer}"}}'
    visible = codec.tokenize(content)
    eos_piece = str(props.get("eos_token") or "")
    eos = codec.tokenize(eos_piece)
    require(len(visible) == 5, "expected visible state width changed")
    require(len(eos) == 1 and codec.detokenize(eos) == eos_piece, "EOS changed")
    generated = [*visible, eos[0]]
    require(
        canonical_sha256(generated) == EXPECTED_GENERATED_SHA256[answer],
        f"expected {answer} generated identity changed",
    )
    return {
        "answer": answer,
        "content": content,
        "visible_token_ids": visible,
        "generated_token_ids": generated,
        "terminal_eog_id": eos[0],
        "generated_token_sha256": canonical_sha256(generated),
        "visible_token_sha256": canonical_sha256(visible),
    }


def derive_plan(
    codec: Any,
    props: Mapping[str, Any],
    prepared: Mapping[str, Any],
) -> dict[str, Any]:
    prompt_tokens = list(prepared["prompt_tokens"])
    require(
        len(prompt_tokens) == EXPECTED_PROMPT_COUNT
        and canonical_sha256(prompt_tokens) == EXPECTED_PROMPT_SHA256,
        "Task-A prompt identity changed",
    )
    visible_task = codec.tokenize(TASK_A_CONTENT)
    eos_piece = str(props.get("eos_token") or "")
    eos = codec.tokenize(eos_piece)
    require(len(eos) == 1, "Task-A EOS identity changed")
    task_generated = [*visible_task, eos[0]]
    require(
        canonical_sha256(task_generated) == EXPECTED_TASK_A_GENERATED_SHA256,
        "qualified Task-A generated identity changed",
    )
    retained_tokens = [*prompt_tokens, *visible_task]
    require(
        len(retained_tokens) == EXPECTED_RETAINED_COUNT
        and canonical_sha256(retained_tokens) == EXPECTED_RETAINED_SHA256,
        "qualified retained carrier identity changed",
    )
    retained = {
        "retained_root_tokens": retained_tokens,
        "terminal_stop_identity": {"token_id": eos[0]},
    }
    branch_tokens, branch_payload = latency.branch_request(
        codec,
        retained,
        prepared["spec"],
        cache_prompt=False,
    )
    require(
        len(branch_tokens) == EXPECTED_BRANCH_COUNT
        and canonical_sha256(branch_tokens) == EXPECTED_BRANCH_SHA256
        and canonical_sha256(branch_payload) == EXPECTED_BRANCH_PAYLOAD_SHA256,
        "Linux 607-bound branch identity changed",
    )
    require(
        len(branch_tokens[:-1]) == EXPECTED_BASE_COUNT
        and canonical_sha256(branch_tokens[:-1]) == EXPECTED_BASE_SHA256,
        "Linux base identity changed",
    )
    expected_states = {
        answer: exact_state(codec, props, answer)
        for answer in EXPECTED_ANSWERS
    }
    expected_children: dict[str, list[int]] = {}
    for answer, state in expected_states.items():
        child = [*branch_tokens, *state["visible_token_ids"]]
        require(
            len(child) == 690
            and canonical_sha256(child) == EXPECTED_CHILD_SHA256[answer],
            f"expected ordinal child {answer} changed",
        )
        expected_children[answer] = child
    successor_requests: dict[int, dict[str, Any]] = {}
    for ordinal, prior_answer in enumerate(("C", "D"), 1):
        tokens, payload, ancestry = rolling.derive_promoted_successor(
            codec=codec,
            root_tokens=expected_children[prior_answer],
            prior_state=expected_states[prior_answer],
            seed=shared_tasks.derive_seed(
                predecessor.ROOT_ID,
                f"fixed-size-rebase-step-{ordinal}",
            ),
            cache_prompt=False,
            transition_content=fixed.transition_user_content(),
        )
        require(
            len(tokens) == EXPECTED_SUCCESSOR_COUNT
            and canonical_sha256(tokens) == EXPECTED_REQUEST_SHA256[ordinal]
            and canonical_sha256(payload)
            == EXPECTED_REQUEST_PAYLOAD_SHA256[ordinal],
            f"expected ordinal {ordinal} successor identity changed",
        )
        require(
            ancestry["suffix_token_count"] == EXPECTED_SUFFIX_COUNT
            and ancestry["suffix_token_sha256"] == EXPECTED_SUFFIX_SHA256,
            f"expected ordinal {ordinal} suffix changed",
        )
        successor_requests[ordinal] = {
            "tokens": tokens,
            "payload": payload,
            "ancestry": ancestry,
        }
    return {
        "prompt_tokens": prompt_tokens,
        "retained_tokens": retained_tokens,
        "branch_tokens": branch_tokens,
        "branch_payload": branch_payload,
        "expected_states": expected_states,
        "expected_children": expected_children,
        "successor_requests": successor_requests,
        "summary": {
            "prompt": {
                "count": len(prompt_tokens),
                "sha256": canonical_sha256(prompt_tokens),
            },
            "retained": {
                "count": len(retained_tokens),
                "sha256": canonical_sha256(retained_tokens),
            },
            "base": {
                "count": len(branch_tokens) - 1,
                "sha256": canonical_sha256(branch_tokens[:-1]),
            },
            "branch": {
                "count": len(branch_tokens),
                "sha256": canonical_sha256(branch_tokens),
                "payload_sha256": canonical_sha256(branch_payload),
            },
            "children": {
                answer: {
                    "count": len(tokens),
                    "sha256": canonical_sha256(tokens),
                }
                for answer, tokens in expected_children.items()
            },
            "successors": {
                str(ordinal): {
                    "count": len(item["tokens"]),
                    "sha256": canonical_sha256(item["tokens"]),
                    "payload_sha256": canonical_sha256(item["payload"]),
                    "suffix_count": item["ancestry"]["suffix_token_count"],
                    "suffix_sha256": item["ancestry"]["suffix_token_sha256"],
                }
                for ordinal, item in successor_requests.items()
            },
        },
    }


def run_stage(
    *,
    sidecar: linux_sidecar.LinuxSidecar,
    codec: Any,
    props: Mapping[str, Any],
    progress: dict[str, Any],
    ordinal: int,
    payload: Mapping[str, Any],
    expected_prompt_count: int,
    consumed_marker: Path,
    expected_commit: str,
) -> dict[str, Any]:
    recorder = runtime.RawResponseRecorder(
        sidecar.run_root / f"stage-{ordinal}.raw.sse",
        progress,
    )
    try:
        record = harness.run_completion(
            StageAttemptSidecar(
                sidecar,
                progress,
                ordinal,
                consumed_marker,
                expected_commit,
            ),
            f"{EXPERIMENT_ID}:stage-{ordinal}",
            payload,
            recorder=recorder,
        )
    finally:
        raw = recorder.close()
    progress.setdefault("stage_captures", {})[str(ordinal)] = record
    require(
        record["prompt_tokens"] == expected_prompt_count
        and record["cached_prompt_tokens"] == 0
        and record["fresh_prompt_tokens"] == expected_prompt_count,
        f"stage {ordinal} materialized prompt geometry changed",
    )
    state_error: dict[str, str] | None = None
    try:
        state = fixed.generated_state(record, codec=codec, props=props)
    except Exception as exc:
        state = None
        state_error = {
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    return {
        "ordinal": ordinal,
        "record": record,
        "state": state,
        "state_error": state_error,
        "raw": raw,
    }


def stage_exact(stage: Mapping[str, Any], ordinal: int) -> bool:
    state = stage.get("state")
    return (
        isinstance(state, Mapping)
        and state.get("answer") == EXPECTED_ANSWERS[ordinal]
        and state.get("generated_token_sha256")
        == EXPECTED_GENERATED_SHA256[EXPECTED_ANSWERS[ordinal]]
    )


def classify_stages(stages: Sequence[Mapping[str, Any]]) -> str:
    for ordinal, stage in enumerate(stages):
        state = stage.get("state")
        if not isinstance(state, Mapping):
            return f"STAGE_{ordinal}_UTILITY_OR_TERMINAL_FAILURE"
        if state.get("answer") != EXPECTED_ANSWERS[ordinal]:
            return f"STAGE_{ordinal}_UTILITY_FAILURE"
        if (
            state.get("generated_token_sha256")
            != EXPECTED_GENERATED_SHA256[EXPECTED_ANSWERS[ordinal]]
        ):
            return f"STAGE_{ordinal}_NOVEL_CORRECT_IDENTITY_REQUIRES_REPLICATION"
    if len(stages) == 3:
        return "NATIVE_LINUX_607_BOUND_C_TO_D_TO_B_IDENTITIES_QUALIFIED"
    return "CHAIN_STOPPED_BEFORE_ALL_ORDINALS"


def evaluate(
    *,
    sidecar: linux_sidecar.LinuxSidecar,
    codec: Any,
    props: Mapping[str, Any],
    plan: Mapping[str, Any],
    progress: dict[str, Any],
    consumed_marker: Path,
    expected_commit: str,
) -> dict[str, Any]:
    stages: list[dict[str, Any]] = []
    stage0 = run_stage(
        sidecar=sidecar,
        codec=codec,
        props=props,
        progress=progress,
        ordinal=0,
        payload=plan["branch_payload"],
        expected_prompt_count=EXPECTED_BRANCH_COUNT,
        consumed_marker=consumed_marker,
        expected_commit=expected_commit,
    )
    stages.append(stage0)
    for ordinal in (1, 2):
        if not stage_exact(stages[-1], ordinal - 1):
            break
        prior_state = stages[-1]["state"]
        child = [*plan["branch_tokens"], *prior_state["visible_token_ids"]]
        require(
            canonical_sha256(child)
            == EXPECTED_CHILD_SHA256[EXPECTED_ANSWERS[ordinal - 1]],
            f"actual ordinal {ordinal - 1} child identity changed",
        )
        tokens, payload, ancestry = rolling.derive_promoted_successor(
            codec=codec,
            root_tokens=child,
            prior_state=prior_state,
            seed=shared_tasks.derive_seed(
                predecessor.ROOT_ID,
                f"fixed-size-rebase-step-{ordinal}",
            ),
            cache_prompt=False,
            transition_content=fixed.transition_user_content(),
        )
        require(
            len(tokens) == EXPECTED_SUCCESSOR_COUNT
            and canonical_sha256(tokens) == EXPECTED_REQUEST_SHA256[ordinal]
            and canonical_sha256(payload)
            == EXPECTED_REQUEST_PAYLOAD_SHA256[ordinal]
            and ancestry["suffix_token_sha256"] == EXPECTED_SUFFIX_SHA256,
            f"actual ordinal {ordinal} request identity changed",
        )
        stages.append(
            run_stage(
                sidecar=sidecar,
                codec=codec,
                props=props,
                progress=progress,
                ordinal=ordinal,
                payload=payload,
                expected_prompt_count=EXPECTED_SUCCESSOR_COUNT,
                consumed_marker=consumed_marker,
                expected_commit=expected_commit,
            )
        )
    classification = classify_stages(stages)
    resources = sidecar.resource_snapshot(None)
    log_path = Path(str(sidecar.readiness["log_path"]))
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    forbidden = {
        "root_save": "root-save" in log_text,
        "root_restore": "root-restore" in log_text,
        "root_erase": "root-erase" in log_text,
        "live_capture": "one-use live terminal boundary captured" in log_text,
        "live_sample": "one-use live terminal boundary sampled" in log_text,
    }
    request_count = log_text.count("new prompt, n_ctx_slot")
    require(
        request_count == len(stages)
        and not any(forbidden.values())
        and isinstance(resources.get("peak_gpu_dedicated_bytes"), int)
        and 0 < int(resources["peak_gpu_dedicated_bytes"]) <= MAX_GPU_BYTES
        and (
            resources.get("host_rss_growth_bytes") is None
            or int(resources["host_rss_growth_bytes"]) <= MAX_HOST_GROWTH_BYTES
        ),
        "0090 evidence-integrity or resource gate failed",
    )
    accepted = (
        classification
        == "NATIVE_LINUX_607_BOUND_C_TO_D_TO_B_IDENTITIES_QUALIFIED"
    )
    return {
        "id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "complete",
        "verdict": "accept" if accepted else "inconclusive",
        "classification": classification,
        "hypothesis": (
            "The prospectively reconstructed Linux 607-bound materialized "
            "branch and fixed ordinal successor requests reproduce the exact "
            "C, D, and B generated identities needed by a later live-terminal "
            "successor."
        ),
        "restoration_class": RESTORATION_CLASS,
        "plan": plan["summary"],
        "stages": stages,
        "requests_executed": len(stages),
        "forbidden_operation_markers": forbidden,
        "resources_before_process_closure": resources,
        "automatic_promotion": False,
        "research_goal_blocked": False,
        "claim_ceiling": (
            "At most one fully materialized native-Linux 607-bound C-to-D-to-B "
            "identity qualification. No root, live-terminal, restoration, "
            "phase-resource, speed, catalytic-leverage, or unbounded claim."
        ),
        "next_boundary": (
            "PREREGISTER_DISTINCT_OWNER_BOUND_LINUX_LIVE_TERMINAL_SUCCESSOR_"
            "WITH_POSITIONAL_PORTS_AND_AUDIO_CUSTODY_LAWS"
            if accepted
            else "PRESERVE_0090_AND_SELECT_A_PROSPECTIVE_IDENTITY_SUCCESSOR"
        ),
    }


def static_audit() -> dict[str, Any]:
    source = Path(__file__).read_text(encoding="utf-8")
    runtime_source = source[: source.index("def static_audit()")]
    main_source = source[source.rindex("def main() -> int:") :]
    gates = {
        "three_stage_maximum": runtime_source.count("run_stage(") == 3,
        "fully_materialized_only": "cache_prompt=False" in runtime_source,
        "no_root_operation": "root_action(" not in runtime_source,
        "no_live_boundary_operation": "run_live_sequence" not in runtime_source,
        "positional_stage_ids": "stage-{self.ordinal}" in runtime_source,
        "stops_before_unpinned_successor": (
            "if not stage_exact(stages[-1], ordinal - 1):" in runtime_source
        ),
        "expected_outputs_do_not_select_operator": (
            'f"fixed-size-rebase-step-{ordinal}"' in runtime_source
            and "transition_content=fixed.transition_user_content()"
            in runtime_source
        ),
        "raw_response_fsync": "runtime.RawResponseRecorder(" in runtime_source,
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
        "output_after_cleanup": (
            main_source.index("cleanup = sidecar.stop()")
            < main_source.index("terminal.write_exclusive_json(output, result)")
        ),
        "no_permanent_file_deletion": all(
            token not in runtime_source
            for token in ("rmtree", ".unlink(", "os.remove", "rmdir(")
        ),
    }
    require(all(gates.values()), "0090 static source audit failed")
    return {
        "id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "gates": gates,
        "reused_0089_runtime": runtime.static_audit(
            runtime.DEFAULT_BINARY.resolve(strict=True),
            runtime.DEFAULT_COMPILER_CONTRACT.resolve(strict=True),
            runtime.DEFAULT_RUNTIME_MANIFEST.resolve(strict=True),
        ),
        "scientific_contact": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--static-only", action="store_true")
    mode.add_argument("--execute-once", action="store_true")
    parser.add_argument("--expected-commit")
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
    static = static_audit()
    if args.static_only:
        print(json.dumps(static, indent=2, sort_keys=True))
        return 0
    require(args.expected_commit is not None, "--expected-commit is required")
    terminal.require_clean_head(ROOT, args.expected_commit)
    runtime.require_pushed_frontier_head(args.expected_commit)
    output = args.output.resolve(strict=False)
    lock_path = args.active_lock.resolve(strict=False)
    consumed_marker = args.consumed_marker.resolve(strict=False)
    require(
        output == DEFAULT_OUTPUT.resolve(strict=False),
        "0090 output path is identity-canonical and cannot be overridden",
    )
    require(
        consumed_marker == DEFAULT_CONSUMED_MARKER.resolve(strict=False),
        "0090 durable consumption path is identity-canonical and cannot be "
        "overridden",
    )
    require(not output.exists(), "0090 result already exists")
    require(
        not consumed_marker.exists(),
        "0090 durable consumption marker already exists",
    )
    run_root = (
        args.run_parent.resolve(strict=False)
        / f"{EXPERIMENT_ID}-{time.time_ns()}"
    )
    sidecar = linux_sidecar.LinuxSidecar(
        binary=DEFAULT_BINARY,
        model=DEFAULT_MODEL,
        run_root=run_root,
    )
    lock = acquire_lock(lock_path, args.expected_commit)
    original_stdout = sys.stdout
    sys.stdout = FailureProofTextIO(original_stdout)
    progress: dict[str, Any] = {
        "scientific_contact": False,
        "transport_attempts": [],
    }
    result: dict[str, Any] | None = None
    caught: BaseException | None = None
    cleanup: dict[str, Any] = {}
    lock_release: dict[str, Any] = {}
    try:
        prelaunch_static = static_audit()
        require(
            canonical_sha256(prelaunch_static) == canonical_sha256(static),
            "0090 runtime identity changed before launch",
        )
        readiness = sidecar.launch()
        codec = harness.carrier.SidecarPromptCodec(linux_sidecar.PORT)
        props = codec.props()
        corpus = harness.carrier.load_public_corpus(ROOT)
        roots = {str(item["root_id"]): item for item in corpus["roots"]}
        prepared = terminal.prepare_task_and_branch(
            codec,
            roots[terminal.ROOT_ID],
        )
        plan = derive_plan(codec, props, prepared)
        intent = terminal.write_exclusive_json(
            run_root / "request-intent.json",
            {
                "id": EXPERIMENT_ID,
                "attempt_id": ATTEMPT_ID,
                "expected_commit": args.expected_commit,
                "created_unix_ns": time.time_ns(),
                "maximum_requests": 3,
                "stage_order": [0, 1, 2],
                "meaning": (
                    "fixed stage 0 is next; later stages may run only after "
                    "the prior generated identity matches its preregistered "
                    "ordinal boundary"
                ),
                "plan": plan["summary"],
            },
        )
        progress["request_intent"] = intent
        progress["plan"] = plan["summary"]
        result = evaluate(
            sidecar=sidecar,
            codec=codec,
            props=props,
            plan=plan,
            progress=progress,
            consumed_marker=consumed_marker,
            expected_commit=args.expected_commit,
        )
        result["candidate_commit"] = args.expected_commit
        result["readiness"] = readiness
        result["static_evidence"] = static
        result["prelaunch_static_evidence"] = prelaunch_static
        result["launch_lock"] = lock
        result["request_intent"] = intent
    except BaseException as exc:
        caught = exc
    finally:
        try:
            cleanup = sidecar.stop()
        except BaseException as exc:
            cleanup = {
                "candidate_stopped": False,
                "port_free": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            if caught is None:
                caught = exc
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
        sys.stdout = original_stdout

    closure = (
        cleanup.get("candidate_stopped") is True
        and cleanup.get("port_free") is True
        and lock_release.get("released") is True
    )
    if caught is None and not closure:
        caught = ExperimentError("0090 process or lock closure failed")
    scientific_contact = bool(progress.get("transport_attempts"))
    if caught is not None:
        full_failure = {
            "id": EXPERIMENT_ID,
            "attempt_id": ATTEMPT_ID,
            "status": "failed",
            "error_type": type(caught).__name__,
            "error": str(caught),
            "scientific_contact": scientific_contact,
            "progress": progress,
            "cleanup": cleanup,
            "launch_lock": lock,
            "launch_lock_release": lock_release,
            "result_before_cleanup": result,
            "automatic_promotion": False,
        }
        custody_failure = {
            "id": EXPERIMENT_ID,
            "attempt_id": ATTEMPT_ID,
            "status": "poisoned-before-closure",
            "error_type": type(caught).__name__,
            "error": str(caught),
            "scientific_contact": scientific_contact,
            "transport_attempt_count": len(
                progress.get("transport_attempts") or []
            ),
            "consumption_marker": progress.get("consumption_marker"),
            "cleanup": cleanup,
            "launch_lock": lock,
            "launch_lock_release": lock_release,
            "outcome_projection_withheld": True,
            "automatic_promotion": False,
        }
        failure = full_failure if closure else custody_failure
        failure_path = (
            output
            if scientific_contact
            else args.run_parent.resolve(strict=False)
            / f"{EXPERIMENT_ID}-precontact-{time.time_ns()}.json"
        )
        terminal.write_exclusive_json(failure_path, failure)
        raise ExperimentError(
            f"0090 failed; evidence preserved at {failure_path}"
        ) from caught
    require(result is not None, "0090 result is missing")
    result["cleanup"] = cleanup
    result["launch_lock_release"] = lock_release
    result["scientific_contact"] = {
        "observed": scientific_contact,
        "transport_attempts": len(progress["transport_attempts"]),
    }
    result["consumption_marker"] = progress.get("consumption_marker")
    result["artifact"] = terminal.write_exclusive_json(output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
