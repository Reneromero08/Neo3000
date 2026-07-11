#!/usr/bin/env python3
"""Equal-budget task-advantage control substrate for CatalyticSwarm-1.

Four 32-request arms solve the same protected executable task suite:

- serial-chain: one sequential trajectory over 32 bounded Fast turns;
- best-of-n: 32 independent candidates selected by the public verifier;
- sparse-swarm: the proven 16/8/6/2 CatalyticSwarm topology without verifier
  feedback in model context;
- verified-swarm: the same topology with bounded public-example verifier scores
  attached to assigned parent candidates.

Every arm has one physical lease, 32 requests, and a maximum of 32 completion
tokens per request. Hidden examples are never supplied to a worker. This module
contains no network, subprocess, Git, or filesystem mutation.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass, replace
from typing import Any, Callable, Mapping, Sequence

from catalytic_advantage_tasks import (
    AdvantageTask,
    AdvantageTaskError,
    build_frozen_task_suite,
    candidate_is_exact,
    render_public_task,
    score_candidate,
    validate_public_projection,
)
from catalytic_swarm import build_catalytic_swarm_0_plan

SCHEMA_VERSION = 1
PLAN_ID = "catalytic-swarm-1-equal-budget-v1"
ARMS = (
    "serial-chain",
    "best-of-n",
    "sparse-swarm",
    "verified-swarm",
)
REQUESTS_PER_ARM = 32
MAX_TOKENS_PER_REQUEST = 32
MAX_COMPLETION_TOKENS_PER_ARM = REQUESTS_PER_ARM * MAX_TOKENS_PER_REQUEST
MAX_FRESH_PROMPT_TOKENS_PER_ARM = 8192
CONTEXT_SLOTS = 6
BUDGET_RATIO_LIMIT = 1.10
RESPONSE_KEYS = {"candidate_id"}
ACCEPTED_V4_TOKEN_EVIDENCE_SCOPES = {
    "exact-generated-token-sequence",
    "exact-visible-content-tokenization",
    "exact-visible-content-tokenization-plus-one-terminal-eos-token",
}


class AdvantageControlError(RuntimeError):
    """The advantage plan, transport, budget, or result is invalid."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


@dataclass(frozen=True)
class AdvantageTurn:
    turn_id: str
    ordinal: int
    arm: str
    phase: str
    role: str
    parent_turn_ids: tuple[str, ...]
    verifier_feedback_visible: bool
    seed: int
    max_tokens: int

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["parent_turn_ids"] = list(self.parent_turn_ids)
        return value


@dataclass(frozen=True)
class AdvantageArmPlan:
    schema_version: int
    plan_id: str
    arm: str
    turns: tuple[AdvantageTurn, ...]
    physical_slots: int
    request_count: int
    max_tokens_per_request: int
    max_completion_tokens: int
    max_fresh_prompt_tokens: int
    hidden_feedback_visible: bool
    automatic_promotion: bool
    plan_sha256: str

    def to_dict(self) -> dict[str, Any]:
        value = _arm_plan_payload(self)
        value["plan_sha256"] = self.plan_sha256
        return value


@dataclass(frozen=True)
class TurnObservation:
    turn_id: str
    ordinal: int
    arm: str
    task_id: str
    public_root_sha256: str
    phase: str
    role: str
    parent_turn_ids: tuple[str, ...]
    candidate_id: str
    public_passed: int | None
    public_total: int | None
    content_sha256: str
    prompt_tokens: int
    cached_prompt_tokens: int
    required_cached_prompt_tokens: int
    fresh_prompt_tokens: int
    completion_tokens: int
    finish_reason: str
    token_evidence_scope: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["parent_turn_ids"] = list(self.parent_turn_ids)
        return value


@dataclass(frozen=True)
class ArmOutcome:
    task_id: str
    arm: str
    plan_sha256: str
    public_root_sha256: str
    observations: tuple[TurnObservation, ...]
    final_candidate_id: str
    final_public_passed: int
    final_public_total: int
    final_hidden_passed: int | None
    final_hidden_total: int | None
    exact_hidden_success: bool | None
    request_count: int
    total_prompt_tokens: int
    total_cached_prompt_tokens: int
    total_fresh_prompt_tokens: int
    total_completion_tokens: int
    total_model_tokens: int
    completion_budget_ceiling: int
    fresh_prompt_budget_ceiling: int
    automatic_promotion: bool
    verdict: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["observations"] = [item.to_dict() for item in self.observations]
        value["reasons"] = list(self.reasons)
        return value


@dataclass(frozen=True)
class TaskComparison:
    task_id: str
    outcomes: tuple[ArmOutcome, ...]
    budget_parity_passed: bool
    budget_parity_reasons: tuple[str, ...]
    fresh_prompt_ratio: float
    completion_ratio: float
    total_model_token_ratio: float

    def outcome(self, arm: str) -> ArmOutcome:
        for item in self.outcomes:
            if item.arm == arm:
                return item
        raise AdvantageControlError(f"{self.task_id} has no outcome for {arm}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "outcomes": [item.to_dict() for item in self.outcomes],
            "budget_parity_passed": self.budget_parity_passed,
            "budget_parity_reasons": list(self.budget_parity_reasons),
            "fresh_prompt_ratio": self.fresh_prompt_ratio,
            "completion_ratio": self.completion_ratio,
            "total_model_token_ratio": self.total_model_token_ratio,
        }


@dataclass(frozen=True)
class SuiteAdvantageResult:
    task_count: int
    success_counts: tuple[tuple[str, int], ...]
    paired_wins: tuple[tuple[str, tuple[int, int, int]], ...]
    all_budget_parity_passed: bool
    verdict: str
    task_advantage: str
    automatic_promotion: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_count": self.task_count,
            "success_counts": dict(self.success_counts),
            "paired_wins": {
                arm: {
                    "verified_wins": values[0],
                    "ties": values[1],
                    "verified_losses": values[2],
                }
                for arm, values in self.paired_wins
            },
            "all_budget_parity_passed": self.all_budget_parity_passed,
            "verdict": self.verdict,
            "CATALYTIC_SWARM_TASK_ADVANTAGE_PROVEN": self.task_advantage,
            "automatic_promotion": self.automatic_promotion,
            "reasons": list(self.reasons),
        }


def _arm_short(arm: str) -> str:
    return {
        "serial-chain": "chain",
        "best-of-n": "best",
        "sparse-swarm": "sparse",
        "verified-swarm": "verified",
    }[arm]


def _turn_id(arm: str, ordinal: int) -> str:
    return f"cs1-{_arm_short(arm)}-t{ordinal:02d}"


def _role_assignment(role: str) -> str:
    if role == "hypothesis":
        action = "derive the most likely candidate from the public examples"
    elif role == "implementation":
        action = "execute candidate programs symbolically and select one"
    elif role == "counterexample":
        action = "search for a public-example contradiction in candidate choices"
    elif role == "measurement":
        action = "tabulate public-example agreement and select one"
    elif role == "evidence-check":
        action = "compare assigned parent candidates against the public examples"
    elif role == "adversarial-critic":
        action = "challenge assigned parent candidates using public examples"
    elif role == "selector":
        action = "select the strongest candidate from assigned parent evidence"
    else:
        action = "select one candidate"
    return (
        f"{action}. Use only the assigned parent slots; a public_score of -- "
        "means unavailable. Hidden tests are unavailable. Return exactly one "
        "candidate ID in the required JSON."
    )


def _build_turns(arm: str) -> tuple[AdvantageTurn, ...]:
    if arm not in ARMS:
        raise ValueError(f"unsupported advantage arm: {arm}")
    control = build_catalytic_swarm_0_plan()
    cs0 = control.logical_workers
    worker_to_ordinal = {worker.worker_id: worker.ordinal for worker in cs0}
    turns: list[AdvantageTurn] = []
    for worker in cs0:
        ordinal = worker.ordinal
        if arm == "serial-chain":
            parents = () if ordinal == 1 else (_turn_id(arm, ordinal - 1),)
            phase = "trajectory"
        elif arm == "best-of-n":
            parents = ()
            phase = "independent"
        else:
            parents = tuple(
                _turn_id(arm, worker_to_ordinal[parent_id])
                for parent_id in worker.parent_worker_ids
            )
            phase = worker.phase
        turns.append(
            AdvantageTurn(
                turn_id=_turn_id(arm, ordinal),
                ordinal=ordinal,
                arm=arm,
                phase=phase,
                role=worker.role,
                parent_turn_ids=parents,
                verifier_feedback_visible=arm == "verified-swarm",
                seed=worker.seed,
                max_tokens=MAX_TOKENS_PER_REQUEST,
            )
        )
    return tuple(turns)


def _arm_plan_payload(plan: AdvantageArmPlan) -> dict[str, Any]:
    return {
        "schema_version": plan.schema_version,
        "plan_id": plan.plan_id,
        "arm": plan.arm,
        "turns": [item.to_dict() for item in plan.turns],
        "physical_slots": plan.physical_slots,
        "request_count": plan.request_count,
        "max_tokens_per_request": plan.max_tokens_per_request,
        "max_completion_tokens": plan.max_completion_tokens,
        "max_fresh_prompt_tokens": plan.max_fresh_prompt_tokens,
        "hidden_feedback_visible": plan.hidden_feedback_visible,
        "automatic_promotion": plan.automatic_promotion,
    }


def build_advantage_arm_plan(arm: str) -> AdvantageArmPlan:
    turns = _build_turns(arm)
    provisional = AdvantageArmPlan(
        schema_version=SCHEMA_VERSION,
        plan_id=PLAN_ID,
        arm=arm,
        turns=turns,
        physical_slots=1,
        request_count=REQUESTS_PER_ARM,
        max_tokens_per_request=MAX_TOKENS_PER_REQUEST,
        max_completion_tokens=MAX_COMPLETION_TOKENS_PER_ARM,
        max_fresh_prompt_tokens=MAX_FRESH_PROMPT_TOKENS_PER_ARM,
        hidden_feedback_visible=False,
        automatic_promotion=False,
        plan_sha256="",
    )
    digest = sha256_bytes(canonical_json_bytes(_arm_plan_payload(provisional)))
    return AdvantageArmPlan(
        schema_version=provisional.schema_version,
        plan_id=provisional.plan_id,
        arm=provisional.arm,
        turns=provisional.turns,
        physical_slots=provisional.physical_slots,
        request_count=provisional.request_count,
        max_tokens_per_request=provisional.max_tokens_per_request,
        max_completion_tokens=provisional.max_completion_tokens,
        max_fresh_prompt_tokens=provisional.max_fresh_prompt_tokens,
        hidden_feedback_visible=provisional.hidden_feedback_visible,
        automatic_promotion=provisional.automatic_promotion,
        plan_sha256=digest,
    )


def validate_advantage_arm_plan(plan: AdvantageArmPlan) -> None:
    if not isinstance(plan, AdvantageArmPlan):
        raise AdvantageControlError("advantage arm plan has the wrong type")
    if type(plan.turns) is not tuple or any(
        not isinstance(turn, AdvantageTurn) for turn in plan.turns
    ):
        raise AdvantageControlError("advantage arm turns are not a canonical tuple")
    try:
        expected = build_advantage_arm_plan(plan.arm)
        actual_payload = canonical_json_bytes(_arm_plan_payload(plan))
        expected_payload = canonical_json_bytes(_arm_plan_payload(expected))
    except (TypeError, ValueError) as exc:
        raise AdvantageControlError("advantage arm plan is not canonical JSON") from exc
    if (
        actual_payload != expected_payload
        or plan.plan_sha256 != sha256_bytes(actual_payload)
        or plan.plan_sha256 != expected.plan_sha256
    ):
        raise AdvantageControlError(f"{plan.arm} plan differs from canonical")
    if len(plan.turns) != REQUESTS_PER_ARM:
        raise AdvantageControlError("advantage arm request count drift")
    if plan.physical_slots != 1:
        raise AdvantageControlError("advantage arm requires one physical slot")
    if any(turn.max_tokens != MAX_TOKENS_PER_REQUEST for turn in plan.turns):
        raise AdvantageControlError("per-turn completion budget drift")
    if plan.hidden_feedback_visible is not False:
        raise AdvantageControlError("hidden verifier feedback is forbidden")
    if plan.automatic_promotion is not False:
        raise AdvantageControlError("automatic promotion must remain disabled")


def build_all_arm_plans() -> tuple[AdvantageArmPlan, ...]:
    plans = tuple(build_advantage_arm_plan(arm) for arm in ARMS)
    role_seed_sequences = {
        tuple((turn.role, turn.seed) for turn in plan.turns)
        for plan in plans
    }
    if len(role_seed_sequences) != 1:
        raise AdvantageControlError(
            "arms do not share the exact role and seed sequence"
        )
    return plans


def _parent_slot(
    observation: TurnObservation | None,
    *,
    reveal_public_score: bool,
) -> dict[str, str]:
    if observation is None:
        return {"turn_id": "---", "candidate_id": "---", "public_score": "--"}
    score = (
        f"{observation.public_passed:02d}"
        if reveal_public_score and observation.public_passed is not None
        else "--"
    )
    return {
        "turn_id": _visible_turn_id(observation.arm, observation.ordinal),
        "candidate_id": observation.candidate_id,
        "public_score": score,
    }


def _visible_turn_id(arm: str, ordinal: int) -> str:
    if arm in {"sparse-swarm", "verified-swarm"}:
        return f"cs1-swarm-t{ordinal:02d}"
    return _turn_id(arm, ordinal)


def _visible_arm(arm: str) -> str:
    return "swarm" if arm in {"sparse-swarm", "verified-swarm"} else arm


def render_turn_assignment(
    task: AdvantageTask,
    turn: AdvantageTurn,
    parent_observations: Sequence[TurnObservation],
) -> str:
    if tuple(item.turn_id for item in parent_observations) != turn.parent_turn_ids:
        raise AdvantageControlError(
            f"{turn.turn_id} received the wrong parent observations"
        )
    if len(parent_observations) > CONTEXT_SLOTS:
        raise AdvantageControlError("parent context exceeds fixed slot count")
    public_root_sha256 = sha256_bytes(render_public_task(task).encode("utf-8"))
    for observation in parent_observations:
        if observation.task_id != task.task_id:
            raise AdvantageControlError("parent observation crossed task boundary")
        if observation.public_root_sha256 != public_root_sha256:
            raise AdvantageControlError("parent observation crossed root boundary")
        public_passed, public_total = score_candidate(
            task, observation.candidate_id, hidden=False
        )
        if (
            observation.public_passed != public_passed
            or observation.public_total != public_total
        ):
            raise AdvantageControlError("parent public score is not authoritative")
    slots = [
        _parent_slot(
            observation,
            reveal_public_score=turn.verifier_feedback_visible,
        )
        for observation in parent_observations
    ]
    slots.extend(
        _parent_slot(None, reveal_public_score=False)
        for _ in range(CONTEXT_SLOTS - len(slots))
    )
    payload = {
        "task_id": task.task_id,
        "turn_id": _visible_turn_id(turn.arm, turn.ordinal),
        "ordinal": f"{turn.ordinal:02d}",
        "arm": _visible_arm(turn.arm),
        "phase": turn.phase,
        "role": turn.role,
        "assignment": _role_assignment(turn.role),
        "parent_slots": slots,
        "response": {"candidate_id": "C00"},
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if "hidden_examples" in encoded or "answer_candidate_id" in encoded:
        raise AdvantageControlError("turn assignment leaked hidden task data")
    return encoded


def parse_candidate_content(content: str, task: AdvantageTask) -> str:
    if not isinstance(content, str) or not content:
        raise AdvantageControlError("candidate response content is empty")
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AdvantageControlError("candidate response is not JSON") from exc
    if not isinstance(value, Mapping) or set(value) != RESPONSE_KEYS:
        raise AdvantageControlError("candidate response key set mismatch")
    candidate_id = value["candidate_id"]
    if not isinstance(candidate_id, str):
        raise AdvantageControlError("candidate_id is not a string")
    task.candidate(candidate_id)
    canonical = json.dumps(
        {"candidate_id": candidate_id},
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )
    if content != canonical:
        raise AdvantageControlError("candidate response is not canonical JSON")
    return candidate_id


WorkerRunner = Callable[
    [AdvantageTurn, str, str],
    Mapping[str, Any],
]


def _require_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AdvantageControlError(f"{label} must be a non-negative integer")
    return value


def _parse_transport(
    result: Mapping[str, Any],
    *,
    turn: AdvantageTurn,
    task: AdvantageTask,
    public_root_sha256: str,
    score_public: bool,
) -> TurnObservation:
    required = {
        "content",
        "prompt_tokens",
        "cached_prompt_tokens",
        "required_cached_prompt_tokens",
        "fresh_prompt_tokens",
        "completion_tokens",
        "finish_reason",
        "reasoning_content",
        "tool_calls",
        "transport_passed",
        "token_evidence_scope",
    }
    if not isinstance(result, Mapping) or set(result) != required:
        raise AdvantageControlError(
            f"{turn.turn_id} transport key set mismatch"
        )
    if result["transport_passed"] is not True:
        raise AdvantageControlError(f"{turn.turn_id} transport did not pass")
    if result["reasoning_content"] != "":
        raise AdvantageControlError(f"{turn.turn_id} exposed reasoning")
    if result["tool_calls"] != []:
        raise AdvantageControlError(f"{turn.turn_id} emitted a tool call")
    if result["finish_reason"] != "stop":
        raise AdvantageControlError(
            f"{turn.turn_id} finish reason is not stop"
        )
    evidence_scope = result["token_evidence_scope"]
    if evidence_scope not in ACCEPTED_V4_TOKEN_EVIDENCE_SCOPES:
        raise AdvantageControlError(
            f"{turn.turn_id} token evidence scope is not accepted v4 evidence"
        )
    candidate_id = parse_candidate_content(result["content"], task)
    prompt_tokens = _require_nonnegative_int(
        result["prompt_tokens"], f"{turn.turn_id}.prompt_tokens"
    )
    cached = _require_nonnegative_int(
        result["cached_prompt_tokens"],
        f"{turn.turn_id}.cached_prompt_tokens",
    )
    required_cached = _require_nonnegative_int(
        result["required_cached_prompt_tokens"],
        f"{turn.turn_id}.required_cached_prompt_tokens",
    )
    fresh = _require_nonnegative_int(
        result["fresh_prompt_tokens"],
        f"{turn.turn_id}.fresh_prompt_tokens",
    )
    completion = _require_nonnegative_int(
        result["completion_tokens"],
        f"{turn.turn_id}.completion_tokens",
    )
    if cached > prompt_tokens or fresh != prompt_tokens - cached:
        raise AdvantageControlError(
            f"{turn.turn_id} prompt-token accounting mismatch"
        )
    if (
        prompt_tokens <= 0
        or cached <= 0
        or required_cached <= 0
        or cached < required_cached
        or fresh >= prompt_tokens
    ):
        raise AdvantageControlError(
            f"{turn.turn_id} did not demonstrate complete common-root cache reuse"
        )
    if completion > turn.max_tokens:
        raise AdvantageControlError(
            f"{turn.turn_id} exceeded completion budget"
        )
    if score_public:
        public_passed, public_total = score_candidate(
            task, candidate_id, hidden=False
        )
    else:
        public_passed = public_total = None
    return TurnObservation(
        turn_id=turn.turn_id,
        ordinal=turn.ordinal,
        arm=turn.arm,
        task_id=task.task_id,
        public_root_sha256=public_root_sha256,
        phase=turn.phase,
        role=turn.role,
        parent_turn_ids=turn.parent_turn_ids,
        candidate_id=candidate_id,
        public_passed=public_passed,
        public_total=public_total,
        content_sha256=sha256_bytes(result["content"].encode("utf-8")),
        prompt_tokens=prompt_tokens,
        cached_prompt_tokens=cached,
        required_cached_prompt_tokens=required_cached,
        fresh_prompt_tokens=fresh,
        completion_tokens=completion,
        finish_reason="stop",
        token_evidence_scope=evidence_scope,
    )


def _plurality_candidate(observations: Sequence[TurnObservation]) -> str:
    if not observations:
        raise AdvantageControlError("cannot select from empty observations")
    counts = Counter(item.candidate_id for item in observations)
    max_count = max(counts.values())
    tied = {candidate for candidate, count in counts.items() if count == max_count}
    for item in observations:
        if item.candidate_id in tied:
            return item.candidate_id
    raise AssertionError("unreachable plurality selection")


def _best_public_candidate(observations: Sequence[TurnObservation]) -> str:
    """Select the highest public-example score, breaking ties by earliest turn."""
    if not observations:
        raise AdvantageControlError("cannot select from empty observations")
    if any(item.public_passed is None for item in observations):
        raise AdvantageControlError(
            "best-of-N public verifier ran before all responses completed"
        )
    best_score = max(item.public_passed for item in observations)
    for item in observations:
        if item.public_passed == best_score:
            return item.candidate_id
    raise AssertionError("unreachable best-of-N selection")


def select_final_candidate(
    plan: AdvantageArmPlan,
    observations: Sequence[TurnObservation],
) -> str:
    if len(observations) != REQUESTS_PER_ARM:
        raise AdvantageControlError("arm did not complete all requests")
    if plan.arm == "serial-chain":
        return observations[-1].candidate_id
    if plan.arm == "best-of-n":
        return _best_public_candidate(observations)
    synthesis = [
        item for item in observations if item.phase == "synthesis"
    ]
    if len(synthesis) != 2:
        raise AdvantageControlError(
            f"{plan.arm} did not produce two synthesis observations"
        )
    return _plurality_candidate(synthesis)


def run_advantage_arm(
    plan: AdvantageArmPlan,
    task: AdvantageTask,
    *,
    worker_runner: WorkerRunner,
) -> ArmOutcome:
    validate_advantage_arm_plan(plan)
    public_root = render_public_task(task)
    validate_public_projection(task, public_root)
    root_hash = sha256_bytes(public_root.encode("utf-8"))
    observations: list[TurnObservation] = []
    by_id: dict[str, TurnObservation] = {}
    reasons: list[str] = []

    for turn in plan.turns:
        try:
            parents = tuple(by_id[parent_id] for parent_id in turn.parent_turn_ids)
        except KeyError as exc:
            raise AdvantageControlError(
                f"{turn.turn_id} dependency did not execute: {exc}"
            ) from exc
        assignment = render_turn_assignment(task, turn, parents)
        try:
            result = worker_runner(turn, public_root, assignment)
            observation = _parse_transport(
                result,
                turn=turn,
                task=task,
                public_root_sha256=root_hash,
                score_public=plan.arm != "best-of-n",
            )
        except Exception as exc:
            reasons.append(f"{turn.turn_id}: {exc}")
            break
        observations.append(observation)
        by_id[turn.turn_id] = observation
        if sum(item.completion_tokens for item in observations) > plan.max_completion_tokens:
            reasons.append("arm completion-token ceiling exceeded")
            break
        if sum(item.fresh_prompt_tokens for item in observations) > plan.max_fresh_prompt_tokens:
            reasons.append("arm fresh-prompt-token ceiling exceeded")
            break

    completed = len(observations) == plan.request_count and not reasons
    if completed and plan.arm == "best-of-n":
        observations = [
            replace(
                item,
                public_passed=score_candidate(
                    task, item.candidate_id, hidden=False
                )[0],
                public_total=len(task.public_examples),
            )
            for item in observations
        ]
    final_candidate = (
        select_final_candidate(plan, observations)
        if completed
        else observations[-1].candidate_id
        if observations
        else ""
    )
    if final_candidate:
        public_passed, public_total = score_candidate(
            task, final_candidate, hidden=False
        )
    else:
        public_passed = 0
        public_total = len(task.public_examples)

    total_prompt = sum(item.prompt_tokens for item in observations)
    total_cached = sum(item.cached_prompt_tokens for item in observations)
    total_fresh = sum(item.fresh_prompt_tokens for item in observations)
    total_completion = sum(item.completion_tokens for item in observations)
    verdict = "complete" if completed else "inconclusive"
    return ArmOutcome(
        task_id=task.task_id,
        arm=plan.arm,
        plan_sha256=plan.plan_sha256,
        public_root_sha256=root_hash,
        observations=tuple(observations),
        final_candidate_id=final_candidate,
        final_public_passed=public_passed,
        final_public_total=public_total,
        final_hidden_passed=None,
        final_hidden_total=None,
        exact_hidden_success=None,
        request_count=len(observations),
        total_prompt_tokens=total_prompt,
        total_cached_prompt_tokens=total_cached,
        total_fresh_prompt_tokens=total_fresh,
        total_completion_tokens=total_completion,
        total_model_tokens=total_fresh + total_completion,
        completion_budget_ceiling=plan.max_completion_tokens,
        fresh_prompt_budget_ceiling=plan.max_fresh_prompt_tokens,
        automatic_promotion=False,
        verdict=verdict,
        reasons=tuple(reasons),
    )


def _ratio(values: Sequence[int]) -> float:
    if not values or min(values) <= 0:
        return float("inf")
    return max(values) / min(values)


def _validate_unscored_arm_outcome(
    task: AdvantageTask,
    outcome: ArmOutcome,
) -> None:
    if outcome.arm not in ARMS:
        raise AdvantageControlError("task comparison contains an unknown arm")
    if type(outcome.observations) is not tuple:
        raise AdvantageControlError("arm observations are not a canonical tuple")
    if type(outcome.reasons) is not tuple or any(
        not isinstance(reason, str) for reason in outcome.reasons
    ):
        raise AdvantageControlError("arm reasons are not a canonical string tuple")
    plan = build_advantage_arm_plan(outcome.arm)
    validate_advantage_arm_plan(plan)
    root_hash = sha256_bytes(render_public_task(task).encode("utf-8"))
    if outcome.task_id != task.task_id:
        raise AdvantageControlError("arm outcome crossed task boundary")
    if outcome.plan_sha256 != plan.plan_sha256:
        raise AdvantageControlError("arm outcome plan hash differs")
    if outcome.public_root_sha256 != root_hash:
        raise AdvantageControlError("arm outcome public root differs")
    for label, value in (
        ("request_count", outcome.request_count),
        ("final_public_passed", outcome.final_public_passed),
        ("final_public_total", outcome.final_public_total),
        ("total_prompt_tokens", outcome.total_prompt_tokens),
        ("total_cached_prompt_tokens", outcome.total_cached_prompt_tokens),
        ("total_fresh_prompt_tokens", outcome.total_fresh_prompt_tokens),
        ("total_completion_tokens", outcome.total_completion_tokens),
        ("total_model_tokens", outcome.total_model_tokens),
        ("completion_budget_ceiling", outcome.completion_budget_ceiling),
        ("fresh_prompt_budget_ceiling", outcome.fresh_prompt_budget_ceiling),
    ):
        _require_nonnegative_int(value, f"{outcome.arm}.{label}")
    if outcome.automatic_promotion is not False:
        raise AdvantageControlError("arm outcome enabled automatic promotion")
    if (
        outcome.final_hidden_passed is not None
        or outcome.final_hidden_total is not None
        or outcome.exact_hidden_success is not None
    ):
        raise AdvantageControlError("arm outcome was hidden-scored before comparison")
    if outcome.request_count != len(outcome.observations):
        raise AdvantageControlError("arm outcome request count is forged")
    if outcome.request_count > REQUESTS_PER_ARM:
        raise AdvantageControlError("arm outcome exceeds the request ceiling")
    if outcome.verdict == "complete" and outcome.request_count != REQUESTS_PER_ARM:
        raise AdvantageControlError("complete arm omitted requests")
    if outcome.verdict not in {"complete", "inconclusive"}:
        raise AdvantageControlError("arm outcome verdict is invalid")
    if outcome.verdict == "complete" and outcome.reasons != ():
        raise AdvantageControlError("complete arm contains failure reasons")
    if outcome.verdict == "inconclusive" and not outcome.reasons:
        raise AdvantageControlError("inconclusive arm omitted failure reasons")

    for expected_turn, observation in zip(
        plan.turns[: len(outcome.observations)],
        outcome.observations,
        strict=True,
    ):
        _require_nonnegative_int(
            observation.ordinal, f"{outcome.arm}.observation.ordinal"
        )
        for label, value in (
            ("prompt_tokens", observation.prompt_tokens),
            ("cached_prompt_tokens", observation.cached_prompt_tokens),
            (
                "required_cached_prompt_tokens",
                observation.required_cached_prompt_tokens,
            ),
            ("fresh_prompt_tokens", observation.fresh_prompt_tokens),
            ("completion_tokens", observation.completion_tokens),
        ):
            _require_nonnegative_int(
                value, f"{outcome.arm}.observation.{label}"
            )
        if observation.public_passed is not None:
            _require_nonnegative_int(
                observation.public_passed,
                f"{outcome.arm}.observation.public_passed",
            )
        if observation.public_total is not None:
            _require_nonnegative_int(
                observation.public_total,
                f"{outcome.arm}.observation.public_total",
            )
        expected_public = (
            score_candidate(task, observation.candidate_id, hidden=False)
            if outcome.arm != "best-of-n" or outcome.verdict == "complete"
            else (None, None)
        )
        if (
            observation.turn_id != expected_turn.turn_id
            or observation.ordinal != expected_turn.ordinal
            or observation.arm != outcome.arm
            or observation.task_id != task.task_id
            or observation.public_root_sha256 != root_hash
            or observation.phase != expected_turn.phase
            or observation.role != expected_turn.role
            or observation.parent_turn_ids != expected_turn.parent_turn_ids
            or (observation.public_passed, observation.public_total)
            != expected_public
            or observation.finish_reason != "stop"
            or observation.token_evidence_scope
            not in ACCEPTED_V4_TOKEN_EVIDENCE_SCOPES
        ):
            raise AdvantageControlError("arm observation differs from canonical")
        task.candidate(observation.candidate_id)
        if (
            observation.prompt_tokens <= 0
            or observation.cached_prompt_tokens <= 0
            or observation.cached_prompt_tokens > observation.prompt_tokens
            or observation.required_cached_prompt_tokens <= 0
            or observation.cached_prompt_tokens
            < observation.required_cached_prompt_tokens
            or observation.fresh_prompt_tokens
            != observation.prompt_tokens - observation.cached_prompt_tokens
            or observation.fresh_prompt_tokens >= observation.prompt_tokens
            or observation.completion_tokens < 0
            or observation.completion_tokens > expected_turn.max_tokens
            or observation.content_sha256
            != sha256_bytes(
                canonical_json_bytes({"candidate_id": observation.candidate_id})
            )
        ):
            raise AdvantageControlError("arm observation accounting is invalid")

    total_prompt = sum(item.prompt_tokens for item in outcome.observations)
    total_cached = sum(item.cached_prompt_tokens for item in outcome.observations)
    total_fresh = sum(item.fresh_prompt_tokens for item in outcome.observations)
    total_completion = sum(item.completion_tokens for item in outcome.observations)
    if (
        outcome.total_prompt_tokens != total_prompt
        or outcome.total_cached_prompt_tokens != total_cached
        or outcome.total_fresh_prompt_tokens != total_fresh
        or outcome.total_completion_tokens != total_completion
        or outcome.total_model_tokens != total_fresh + total_completion
        or outcome.completion_budget_ceiling != plan.max_completion_tokens
        or outcome.fresh_prompt_budget_ceiling != plan.max_fresh_prompt_tokens
        or total_completion > plan.max_completion_tokens
        or total_fresh > plan.max_fresh_prompt_tokens
    ):
        raise AdvantageControlError("arm outcome totals or ceilings are forged")
    if outcome.verdict == "complete":
        final_candidate = select_final_candidate(plan, outcome.observations)
    else:
        final_candidate = (
            outcome.observations[-1].candidate_id
            if outcome.observations
            else ""
        )
    if outcome.final_candidate_id != final_candidate:
        raise AdvantageControlError("arm outcome final selection is forged")
    if final_candidate:
        public_passed, public_total = score_candidate(
            task, final_candidate, hidden=False
        )
    else:
        public_passed, public_total = 0, len(task.public_examples)
    if (
        outcome.final_public_passed != public_passed
        or outcome.final_public_total != public_total
    ):
        raise AdvantageControlError("arm outcome final public score is forged")


def compare_task_outcomes(
    task: AdvantageTask,
    outcomes: Sequence[ArmOutcome],
) -> TaskComparison:
    if len(outcomes) != len(ARMS):
        raise AdvantageControlError(
            f"{task.task_id} does not contain exactly four arms"
        )
    by_arm = {item.arm: item for item in outcomes}
    if len(by_arm) != len(ARMS) or set(by_arm) != set(ARMS):
        raise AdvantageControlError(
            f"{task.task_id} does not contain all four arms"
        )
    ordered = tuple(by_arm[arm] for arm in ARMS)
    for outcome in ordered:
        _validate_unscored_arm_outcome(task, outcome)
    reasons: list[str] = []
    if any(item.task_id != task.task_id for item in ordered):
        reasons.append("task identity mismatch")
    if any(item.verdict != "complete" for item in ordered):
        reasons.append("one or more arms did not complete")
    if any(item.request_count != REQUESTS_PER_ARM for item in ordered):
        reasons.append("request-count parity failed")
    if len({item.public_root_sha256 for item in ordered}) != 1:
        reasons.append("public task root differs across arms")
    if len({item.completion_budget_ceiling for item in ordered}) != 1:
        reasons.append("completion budget ceiling differs")
    if len({item.fresh_prompt_budget_ceiling for item in ordered}) != 1:
        reasons.append("fresh prompt budget ceiling differs")
    if any(item.automatic_promotion for item in ordered):
        reasons.append("automatic promotion enabled")

    all_arms_complete = all(
        item.verdict == "complete" and item.request_count == REQUESTS_PER_ARM
        for item in ordered
    )
    if all_arms_complete:
        scored: list[ArmOutcome] = []
        for item in ordered:
            hidden_passed, hidden_total = score_candidate(
                task, item.final_candidate_id, hidden=True
            )
            scored.append(
                replace(
                    item,
                    final_hidden_passed=hidden_passed,
                    final_hidden_total=hidden_total,
                    exact_hidden_success=(
                        item.final_public_passed == item.final_public_total
                        and hidden_passed == hidden_total
                    ),
                )
            )
        ordered = tuple(scored)

    fresh_ratio = _ratio([item.total_fresh_prompt_tokens for item in ordered])
    completion_ratio = _ratio([item.total_completion_tokens for item in ordered])
    model_ratio = _ratio([item.total_model_tokens for item in ordered])
    if fresh_ratio > BUDGET_RATIO_LIMIT:
        reasons.append("actual fresh-prompt-token ratio exceeds parity limit")
    if completion_ratio > BUDGET_RATIO_LIMIT:
        reasons.append("actual completion-token ratio exceeds parity limit")
    if model_ratio > BUDGET_RATIO_LIMIT:
        reasons.append("actual total-model-token ratio exceeds parity limit")
    return TaskComparison(
        task_id=task.task_id,
        outcomes=ordered,
        budget_parity_passed=not reasons,
        budget_parity_reasons=tuple(reasons),
        fresh_prompt_ratio=fresh_ratio,
        completion_ratio=completion_ratio,
        total_model_token_ratio=model_ratio,
    )


def classify_suite_advantage(
    comparisons: Sequence[TaskComparison],
) -> SuiteAdvantageResult:
    reasons: list[str] = []
    suite = build_frozen_task_suite()
    if len(comparisons) != 8:
        reasons.append("suite must contain exactly eight task comparisons")
    if len({item.task_id for item in comparisons}) != len(comparisons):
        reasons.append("task comparisons contain duplicate IDs")
    if [item.task_id for item in comparisons] != [
        task.task_id for task in suite.tasks
    ]:
        reasons.append("task comparisons differ from frozen suite order")
    if len(comparisons) == len(suite.tasks):
        for task, comparison in zip(suite.tasks, comparisons, strict=True):
            try:
                if type(comparison.budget_parity_passed) is not bool:
                    raise AdvantageControlError(
                        "task comparison parity flag is not boolean"
                    )
                for label, value in (
                    ("fresh_prompt_ratio", comparison.fresh_prompt_ratio),
                    ("completion_ratio", comparison.completion_ratio),
                    (
                        "total_model_token_ratio",
                        comparison.total_model_token_ratio,
                    ),
                ):
                    if type(value) is not float:
                        raise AdvantageControlError(
                            f"task comparison {label} is not a float"
                        )
                for outcome in comparison.outcomes:
                    if outcome.final_hidden_passed is not None:
                        _require_nonnegative_int(
                            outcome.final_hidden_passed,
                            f"{outcome.arm}.final_hidden_passed",
                        )
                    if outcome.final_hidden_total is not None:
                        _require_nonnegative_int(
                            outcome.final_hidden_total,
                            f"{outcome.arm}.final_hidden_total",
                        )
                    if (
                        outcome.exact_hidden_success is not None
                        and type(outcome.exact_hidden_success) is not bool
                    ):
                        raise AdvantageControlError(
                            f"{outcome.arm}.exact_hidden_success is not boolean"
                        )
                unscored = tuple(
                    replace(
                        outcome,
                        final_hidden_passed=None,
                        final_hidden_total=None,
                        exact_hidden_success=None,
                    )
                    for outcome in comparison.outcomes
                )
                canonical = compare_task_outcomes(task, unscored)
                if canonical != comparison:
                    reasons.append(
                        f"{task.task_id} comparison differs from canonical"
                    )
            except (AdvantageControlError, AdvantageTaskError) as exc:
                reasons.append(f"{task.task_id} comparison invalid: {exc}")
    if any(not item.budget_parity_passed for item in comparisons):
        reasons.append("one or more tasks failed equal-budget parity")
    structure_valid = all(
        len(item.outcomes) == len(ARMS)
        and {outcome.arm for outcome in item.outcomes} == set(ARMS)
        for item in comparisons
    )
    if not structure_valid:
        reasons.append("task comparison arm structure is invalid")
    if structure_valid and any(
        item.outcome(arm).final_hidden_passed is None
        or item.outcome(arm).final_hidden_total is None
        or item.outcome(arm).exact_hidden_success is None
        for item in comparisons
        for arm in ARMS
    ):
        reasons.append("hidden scoring was not completed after all four arms")
    success_counts = {
        arm: (
            sum(
                item.outcome(arm).exact_hidden_success is True
                for item in comparisons
            )
            if structure_valid
            else 0
        )
        for arm in ARMS
    }
    verified_success = success_counts["verified-swarm"]
    paired: dict[str, tuple[int, int, int]] = {}
    for baseline in ARMS[:-1]:
        wins = ties = losses = 0
        for item in (comparisons if structure_valid else ()):
            verified_score = item.outcome("verified-swarm").final_hidden_passed
            baseline_score = item.outcome(baseline).final_hidden_passed
            if verified_score is None or baseline_score is None:
                ties += 1
                continue
            if verified_score > baseline_score:
                wins += 1
            elif verified_score == baseline_score:
                ties += 1
            else:
                losses += 1
        paired[baseline] = (wins, ties, losses)

    complete_and_equal = not reasons
    advantage_gate = (
        complete_and_equal
        and verified_success >= 6
        and all(
            verified_success >= success_counts[baseline] + 2
            for baseline in ARMS[:-1]
        )
        and all(wins > losses for wins, _ties, losses in paired.values())
    )
    if advantage_gate:
        verdict = "reviewable-accept"
        task_advantage = "reviewable-accept"
    elif complete_and_equal:
        verdict = "no-advantage"
        task_advantage = "LOCKED"
        reasons.append("verified swarm did not clear the locked advantage margin")
    else:
        verdict = "inconclusive"
        task_advantage = "LOCKED"

    return SuiteAdvantageResult(
        task_count=len(comparisons),
        success_counts=tuple((arm, success_counts[arm]) for arm in ARMS),
        paired_wins=tuple((arm, paired[arm]) for arm in ARMS[:-1]),
        all_budget_parity_passed=all(
            item.budget_parity_passed for item in comparisons
        ) and len(comparisons) == 8,
        verdict=verdict,
        task_advantage=task_advantage,
        automatic_promotion=False,
        reasons=tuple(reasons),
    )


__all__ = [
    "ACCEPTED_V4_TOKEN_EVIDENCE_SCOPES",
    "ARMS",
    "AdvantageArmPlan",
    "AdvantageControlError",
    "AdvantageTurn",
    "ArmOutcome",
    "BUDGET_RATIO_LIMIT",
    "MAX_COMPLETION_TOKENS_PER_ARM",
    "MAX_FRESH_PROMPT_TOKENS_PER_ARM",
    "MAX_TOKENS_PER_REQUEST",
    "REQUESTS_PER_ARM",
    "SuiteAdvantageResult",
    "TaskComparison",
    "TurnObservation",
    "build_advantage_arm_plan",
    "build_all_arm_plans",
    "classify_suite_advantage",
    "compare_task_outcomes",
    "parse_candidate_content",
    "render_turn_assignment",
    "run_advantage_arm",
    "select_final_candidate",
    "validate_advantage_arm_plan",
]
