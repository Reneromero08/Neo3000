#!/usr/bin/env python3
"""Recompute private CK0 outcome facts before evidence publication."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import catalytic_kernel_0_balanced_opaque as balanced


class PrivateOutcomeEvidenceError(ValueError):
    """Tracked outcome facts differ from the private raw result."""


CLASSIFICATION_KEYS = (
    "terminal_classification",
    "balanced_classification",
    "classification",
)
FACT_KEYS = (
    "transform_operator",
    "transform_artifact_commitment",
    "transform_ranking_length",
    "transform_top_matched_private_singleton",
    "extraction_selected_private_singleton",
    "private_public_score",
    "private_public_total",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise PrivateOutcomeEvidenceError(f"missing or unsafe JSON file: {path}")
    try:
        value = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        raise PrivateOutcomeEvidenceError(f"invalid JSON file: {path}") from exc
    if not isinstance(value, dict):
        raise PrivateOutcomeEvidenceError(f"JSON root is not an object: {path}")
    return value


def classification(value: Mapping[str, Any]) -> str | None:
    for key in CLASSIFICATION_KEYS:
        item = value.get(key)
        if isinstance(item, str):
            return item
    return None


def extract_private_outcome_facts(
    repository: Path,
    *,
    run_id: str,
    carrier_profile: str,
    expected_classification: str,
) -> dict[str, Any]:
    configuration = balanced.binding_configuration(carrier_profile)
    if run_id not in configuration.run_modes:
        raise PrivateOutcomeEvidenceError("run ID does not belong to carrier profile")
    result_path = repository / "state" / "catalytic_kernel_0" / run_id / "result.json"
    result = load_json(result_path)
    if result.get("status") != "complete":
        raise PrivateOutcomeEvidenceError("terminal result is not complete")
    if classification(result) != expected_classification:
        raise PrivateOutcomeEvidenceError("terminal classification mismatch")

    branch_a = result.get("branch_a")
    branch_b = result.get("branch_b")
    transform = result.get("transform")
    extraction = result.get("extraction")
    restoration = result.get("restoration")
    if not all(
        isinstance(item, Mapping)
        for item in (branch_a, branch_b, transform, extraction, restoration)
    ):
        raise PrivateOutcomeEvidenceError("terminal balanced artifacts are incomplete")
    ranking = transform.get("ranking")
    evaluation = extraction.get("controller_private_evaluation")
    if not isinstance(ranking, list) or not ranking or not all(
        isinstance(item, str) for item in ranking
    ):
        raise PrivateOutcomeEvidenceError("terminal transform ranking is invalid")
    if not isinstance(evaluation, Mapping):
        raise PrivateOutcomeEvidenceError("terminal private evaluation is missing")

    private = balanced._private_binding_from_repository(repository, configuration)
    runtime = balanced.BalancedOpaqueRuntime(
        repository=repository,
        run_id=run_id,
        private=private,
    )
    artifacts = {
        "branch-a": branch_a,
        "branch-b": branch_b,
        "transform": transform,
        "extract": extraction,
    }
    try:
        runtime.verify_branch_artifact(branch_a)
        runtime.verify_branch_artifact(branch_b)
        runtime.verify_transform_artifact(transform)
        runtime.verify_extraction_artifact(extraction, transform)
    except balanced.BalancedOpaqueError as exc:
        raise PrivateOutcomeEvidenceError(
            f"private artifact verification failed: {exc}"
        ) from exc

    completed = result.get("completed_model_responses")
    if not isinstance(completed, int):
        raise PrivateOutcomeEvidenceError("completed response count is missing")
    recomputed = runtime.classify(
        artifacts,
        completed_request_count=completed,
        restoration_passed=restoration.get("passed") is True,
    )
    if recomputed != expected_classification:
        raise PrivateOutcomeEvidenceError(
            "classification does not recompute from private artifacts"
        )

    winner_alias = private.internal_to_alias[balanced.EXPECTED_FULL_SUPPORT[0]]
    extraction_selected = extraction.get("candidate_alias") == winner_alias
    if evaluation.get("mapped_to_full_public_support") is not extraction_selected:
        raise PrivateOutcomeEvidenceError(
            "private extraction mapping disagrees with selected alias"
        )
    return {
        "transform_operator": transform.get("operator"),
        "transform_artifact_commitment": transform.get("artifact_commitment"),
        "transform_ranking_length": len(ranking),
        "transform_top_matched_private_singleton": ranking[0] == winner_alias,
        "extraction_selected_private_singleton": extraction_selected,
        "private_public_score": evaluation.get("full_public_score"),
        "private_public_total": evaluation.get("full_public_total"),
    }


def iter_mappings(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for item in value.values():
            yield from iter_mappings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_mappings(item)


def first_present(value: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in value:
            return value[key]
    return None


def tracked_outcome_facts(value: Mapping[str, Any]) -> dict[str, Any]:
    transform = value.get("transform")
    extraction = value.get("extraction")
    transform_map = transform if isinstance(transform, Mapping) else {}
    extraction_map = extraction if isinstance(extraction, Mapping) else {}
    return {
        "transform_operator": first_present(value, ("transform_operator",))
        if "transform_operator" in value
        else transform_map.get("operator"),
        "transform_artifact_commitment": first_present(
            value, ("transform_commitment", "transform_artifact_commitment")
        )
        if any(
            key in value
            for key in ("transform_commitment", "transform_artifact_commitment")
        )
        else transform_map.get("artifact_commitment"),
        "transform_ranking_length": first_present(
            value, ("transform_ranking_length",)
        )
        if "transform_ranking_length" in value
        else transform_map.get("ranking_length"),
        "transform_top_matched_private_singleton": first_present(
            value,
            (
                "transform_top_matched_private_singleton",
                "top_matched_private_singleton",
            ),
        )
        if any(
            key in value
            for key in (
                "transform_top_matched_private_singleton",
                "top_matched_private_singleton",
            )
        )
        else transform_map.get("top_matched_private_singleton"),
        "extraction_selected_private_singleton": first_present(
            value,
            (
                "extraction_selected_private_singleton",
                "selected_private_singleton",
            ),
        )
        if any(
            key in value
            for key in (
                "extraction_selected_private_singleton",
                "selected_private_singleton",
            )
        )
        else extraction_map.get("selected_private_singleton"),
        "private_public_score": first_present(value, ("private_public_score",))
        if "private_public_score" in value
        else extraction_map.get("full_public_score"),
        "private_public_total": first_present(value, ("private_public_total",))
        if "private_public_total" in value
        else extraction_map.get("full_public_total"),
    }


def _record_run_id(record: Mapping[str, Any]) -> str | None:
    direct = record.get("run_id")
    if isinstance(direct, str):
        return direct
    configuration = record.get("configuration")
    if isinstance(configuration, Mapping):
        configured = configuration.get("run_id")
        if isinstance(configured, str):
            return configured
    return None


def _record_classification(record: Mapping[str, Any]) -> str | None:
    direct = classification(record)
    if direct is not None:
        return direct
    for key in ("metrics_after", "result"):
        section = record.get(key)
        if isinstance(section, Mapping):
            observed = classification(section)
            if observed is not None:
                return observed
    return None


def _record_fact_section(record: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("metrics_after", "result"):
        section = record.get(key)
        if isinstance(section, Mapping):
            return section
    return record


def _validate_observed_facts(
    observed: Mapping[str, Any],
    expected_facts: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = tracked_outcome_facts(observed)
    missing = [key for key in FACT_KEYS if normalized.get(key) is None]
    if missing:
        raise PrivateOutcomeEvidenceError(
            "results ledger is missing private outcome facts: " + ", ".join(missing)
        )
    mismatched = [
        key
        for key in FACT_KEYS
        if normalized.get(key) != expected_facts.get(key)
    ]
    if mismatched:
        raise PrivateOutcomeEvidenceError(
            "results ledger private outcome facts mismatch: " + ", ".join(mismatched)
        )
    return normalized


def _legacy_co_located_fact_match(
    record: Mapping[str, Any],
    *,
    run_id: str,
    expected_classification: str,
    expected_facts: Mapping[str, Any],
) -> dict[str, Any] | None:
    for mapping in iter_mappings(record):
        if mapping is record:
            continue
        if (
            mapping.get("run_id") == run_id
            and classification(mapping) == expected_classification
        ):
            return _validate_observed_facts(mapping, expected_facts)
    return None


def validate_results_ledger_facts(
    repository: Path,
    *,
    run_id: str,
    expected_classification: str,
    expected_facts: Mapping[str, Any],
) -> dict[str, Any]:
    path = repository / "lab" / "results.jsonl"
    if not path.is_file() or path.is_symlink():
        raise PrivateOutcomeEvidenceError("results ledger is missing or unsafe")
    matches: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PrivateOutcomeEvidenceError(
                f"invalid results ledger JSON at line {line_number}"
            ) from exc
        if not isinstance(value, Mapping):
            continue
        split_record_match = (
            _record_run_id(value) == run_id
            and _record_classification(value) == expected_classification
        )
        if split_record_match:
            observed = _validate_observed_facts(
                _record_fact_section(value), expected_facts
            )
            matches.append(
                {
                    "line": line_number,
                    "facts": observed,
                    "layout": "split-experiment-record",
                }
            )
            continue
        observed = _legacy_co_located_fact_match(
            value,
            run_id=run_id,
            expected_classification=expected_classification,
            expected_facts=expected_facts,
        )
        if observed is not None:
            matches.append(
                {
                    "line": line_number,
                    "facts": observed,
                    "layout": "legacy-co-located",
                }
            )
    if len(matches) != 1:
        raise PrivateOutcomeEvidenceError(
            f"expected exactly one results-ledger binding, found {len(matches)}"
        )
    return {"path": "lab/results.jsonl", "match": matches[0]}


def validate_private_outcome_publication(
    repository: Path,
    *,
    run_id: str,
    carrier_profile: str,
    expected_classification: str,
) -> dict[str, Any]:
    facts = extract_private_outcome_facts(
        repository,
        run_id=run_id,
        carrier_profile=carrier_profile,
        expected_classification=expected_classification,
    )
    ledger = validate_results_ledger_facts(
        repository,
        run_id=run_id,
        expected_classification=expected_classification,
        expected_facts=facts,
    )
    return {
        "status": "pass",
        "run_id": run_id,
        "carrier_profile": carrier_profile,
        "classification": expected_classification,
        "private_outcome_facts": facts,
        "results_ledger": ledger,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--carrier-profile", required=True)
    parser.add_argument("--expected-classification", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = validate_private_outcome_publication(
            args.repository.resolve(),
            run_id=args.run_id,
            carrier_profile=args.carrier_profile,
            expected_classification=args.expected_classification,
        )
    except (PrivateOutcomeEvidenceError, balanced.BalancedOpaqueError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
