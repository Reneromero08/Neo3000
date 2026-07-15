#!/usr/bin/env python3
"""Validate CK0 balanced-opaque publication packages before staging.

The static preregistration is immutable. Terminal observations belong in raw
runtime evidence and tracked evidence ledgers, never inside the preregistration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import catalytic_kernel_0_balanced_opaque as balanced


class PublicationEvidenceError(ValueError):
    """A balanced-opaque publication package violates its evidence contract."""


OBSERVED_RESULT_KEYS = frozenset(
    {
        "full_information_observed_result",
        "delete_a_observed_result",
        "delete_b_observed_result",
        "observed_result",
        "observed_results",
    }
)
CLASSIFICATION_KEYS = (
    "terminal_classification",
    "balanced_classification",
    "classification",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise PublicationEvidenceError(f"missing or unsafe JSON file: {path}")
    try:
        value = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        raise PublicationEvidenceError(f"invalid JSON file: {path}") from exc
    if not isinstance(value, dict):
        raise PublicationEvidenceError(f"JSON root is not an object: {path}")
    return value


def forbidden_observed_result_keys(document: Mapping[str, Any]) -> list[str]:
    return sorted(
        key
        for key in document
        if key in OBSERVED_RESULT_KEYS or key.endswith("_observed_result")
    )


def validate_static_preregistration(
    repository: Path,
    *,
    run_id: str,
    carrier_profile: str,
) -> dict[str, Any]:
    configuration = balanced.binding_configuration(carrier_profile)
    if run_id not in configuration.run_modes:
        raise PublicationEvidenceError("run ID does not belong to carrier profile")
    path = repository / configuration.preregistration_path
    document = load_json(path)
    forbidden = forbidden_observed_result_keys(document)
    if forbidden:
        raise PublicationEvidenceError(
            "terminal observations were inserted into immutable preregistration: "
            + ", ".join(forbidden)
        )
    private = balanced._private_binding_from_repository(repository, configuration)
    projection = balanced.validate_preregistration(
        repository,
        private,
        run_id=run_id,
        require_final=True,
        configuration=configuration,
        for_execution=False,
    )
    return {
        "path": configuration.preregistration_path,
        "sha256": sha256_bytes(path.read_bytes()),
        "document_sha256": balanced.json_sha256(document),
        "validation": projection,
    }


def _classification(value: Mapping[str, Any]) -> str | None:
    for key in CLASSIFICATION_KEYS:
        item = value.get(key)
        if isinstance(item, str):
            return item
    return None


def validate_terminal_raw_evidence(
    repository: Path,
    *,
    run_id: str,
    expected_classification: str | None,
    carrier_profile: str | None = None,
) -> dict[str, Any]:
    root = repository / "state" / "catalytic_kernel_0" / run_id
    paths = {name: root / name for name in ("manifest.json", "result.json", "closure.json")}
    documents = {name: load_json(path) for name, path in paths.items()}
    result = documents["result.json"]
    closure = documents["closure.json"]
    manifest = documents["manifest.json"]

    for name, document in documents.items():
        observed_run = document.get("run_id")
        if observed_run is not None and observed_run != run_id:
            raise PublicationEvidenceError(f"{name} run ID mismatch")

    if result.get("status") != "complete":
        raise PublicationEvidenceError("terminal result is not complete")
    classification = _classification(result)
    if not classification:
        raise PublicationEvidenceError("terminal classification is missing")
    if expected_classification and classification != expected_classification:
        raise PublicationEvidenceError("terminal classification mismatch")

    result_sha = sha256_bytes(paths["result.json"].read_bytes())
    manifest_sha = sha256_bytes(paths["manifest.json"].read_bytes())
    closure_sha = sha256_bytes(paths["closure.json"].read_bytes())
    if closure.get("result_sha256") not in (None, result_sha):
        raise PublicationEvidenceError("closure result binding mismatch")
    if closure.get("manifest_sha256") not in (None, manifest_sha):
        raise PublicationEvidenceError("closure manifest binding mismatch")
    if closure.get("run_lock_absent") is not True:
        raise PublicationEvidenceError("closure does not prove run-lock absence")
    if (root / "run.lock").exists():
        raise PublicationEvidenceError("run lock still exists")

    authority_evidence = None
    if carrier_profile is not None:
        configuration = balanced.binding_configuration(carrier_profile)
        if configuration is balanced.BINDING_2:
            private = balanced._private_binding_from_repository(repository, configuration)
            receipt_path = balanced.authority_receipt_path(repository, run_id)
            receipt = load_json(receipt_path)
            authority_body = receipt.get("authority")
            if not isinstance(authority_body, Mapping):
                raise PublicationEvidenceError("authority receipt body is missing")
            try:
                external_authority = balanced.ExternalLiveAuthority(**dict(authority_body))
            except TypeError as exc:
                raise PublicationEvidenceError("authority receipt body is malformed") from exc
            authority_evidence = balanced.verify_external_live_authority_receipt(
                repository, private, external_authority
            )
            if result.get("external_live_authority") != authority_evidence:
                raise PublicationEvidenceError(
                    "terminal result authority binding differs from consumed receipt"
                )

    token_evidence = []
    for outcome in result.get("request_outcomes", []):
        if not isinstance(outcome, Mapping):
            continue
        token_evidence.append(
            {
                "request_id": outcome.get("request_id"),
                "completion_token_count_match": outcome.get(
                    "completion_token_count_match"
                ),
                "generated_token_array_state": outcome.get(
                    "generated_token_array_state",
                    outcome.get("verbose_token_array_state"),
                ),
            }
        )

    return {
        "run_id": run_id,
        "classification": classification,
        "manifest_sha256": manifest_sha,
        "result_sha256": result_sha,
        "closure_sha256": closure_sha,
        "manifest_schema_version": manifest.get("schema_version"),
        "authority_evidence": authority_evidence,
        "token_evidence": token_evidence,
    }


def _iter_mappings(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for item in value.values():
            yield from _iter_mappings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_mappings(item)


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
    direct = _classification(record)
    if direct is not None:
        return direct
    for key in ("metrics_after", "result"):
        section = record.get(key)
        if isinstance(section, Mapping):
            observed = _classification(section)
            if observed is not None:
                return observed
    return None


def _legacy_co_located_match(
    record: Mapping[str, Any],
    *,
    run_id: str,
    expected_classification: str,
) -> bool:
    for mapping in _iter_mappings(record):
        if mapping is record:
            continue
        if (
            mapping.get("run_id") == run_id
            and _classification(mapping) == expected_classification
        ):
            return True
    return False


def validate_results_ledger(
    repository: Path,
    *,
    run_id: str,
    expected_classification: str,
) -> dict[str, Any]:
    path = repository / "lab" / "results.jsonl"
    if not path.is_file() or path.is_symlink():
        raise PublicationEvidenceError("results ledger is missing or unsafe")
    matches: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PublicationEvidenceError(
                f"invalid results ledger JSON at line {line_number}"
            ) from exc
        if not isinstance(value, Mapping):
            continue
        split_record_match = (
            _record_run_id(value) == run_id
            and _record_classification(value) == expected_classification
        )
        if split_record_match or _legacy_co_located_match(
            value,
            run_id=run_id,
            expected_classification=expected_classification,
        ):
            matches.append(
                {
                    "line": line_number,
                    "classification": expected_classification,
                    "layout": "split-experiment-record"
                    if split_record_match
                    else "legacy-co-located",
                }
            )
    if len(matches) != 1:
        raise PublicationEvidenceError(
            f"expected exactly one results-ledger binding, found {len(matches)}"
        )
    return {"path": "lab/results.jsonl", "match": matches[0]}


def validate_publication_package(
    repository: Path,
    *,
    run_id: str,
    carrier_profile: str,
    expected_classification: str,
) -> dict[str, Any]:
    preregistration = validate_static_preregistration(
        repository,
        run_id=run_id,
        carrier_profile=carrier_profile,
    )
    raw = validate_terminal_raw_evidence(
        repository,
        run_id=run_id,
        expected_classification=expected_classification,
        carrier_profile=carrier_profile,
    )
    ledger = validate_results_ledger(
        repository,
        run_id=run_id,
        expected_classification=expected_classification,
    )
    return {
        "status": "pass",
        "run_id": run_id,
        "carrier_profile": carrier_profile,
        "expected_classification": expected_classification,
        "preregistration": preregistration,
        "raw_evidence": raw,
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
        result = validate_publication_package(
            args.repository.resolve(),
            run_id=args.run_id,
            carrier_profile=args.carrier_profile,
            expected_classification=args.expected_classification,
        )
    except (PublicationEvidenceError, balanced.BalancedOpaqueError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
