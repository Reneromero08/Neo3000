#!/usr/bin/env python3
"""Static private audit of the balanced-opaque parent asymmetry.

The renderer verifies the historical binding-1 controls, the binding-2 source
archive, and the separate zero-contact forensic recovery.  It reconstructs
private diagnostics locally but emits only ordinals, lengths, booleans,
commitments, and bounded category labels.  Token lengths are derived from the
pinned GGUF tokenizer metadata without starting a server or contacting an
inference endpoint.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import struct
from pathlib import Path
from typing import Any, BinaryIO, Mapping, Sequence

import catalytic_kernel_0_balanced_opaque as balanced
import catalytic_kernel_0_balanced_rank_head_v2_parent_dependence as parent
import catalytic_kernel_0_balanced_rank_head_v2_parent_dependence_forensic_recovery as recovery
import catalytic_kernel_0_balanced_rank_head_v2_parent_dependence_scientific as scientific


ARTIFACT_ID = "ck0-balanced-opaque-parent-dependence-cross-binding-asymmetry-audit-1"
ARTIFACT_PATH = Path(
    "lab/ck0_balanced_opaque_parent_dependence_cross_binding_asymmetry_audit_1.json"
)
STATUS = "CROSS_BINDING_PARENT_ASYMMETRY_AUDITED_STATICALLY"
STARTING_MAIN = "b909d93553c0844b7f44efd2d83f66d7364298b4"
CORRECTED_SUPPORTED_CLAIM = (
    "DIRECTIONAL_PARENT_A_INFORMATION_DEPENDENCE_REPRODUCED_ACROSS_TWO_"
    "PRIVATE_BINDINGS_AT_SHARED_TRANSFORM_RANK_HEAD_ENDPOINT"
)
CORRECTED_QUALIFICATION = (
    "Observed across the v1 and v2 extraction variants; not a pure binding-only "
    "replication of an otherwise identical end-to-end process."
)

EXPECTED_MODEL_SIZE = 21_166_757_632
EXPECTED_MODEL_SHA256 = "31AEFA25B7E1EDBDE436E643E2B5E3F6E57820A4811D97B131130E48FF0772C2"
EXPECTED_TOKENIZER_MODEL = "gpt2"
EXPECTED_TOKENIZER_PRE = "qwen35"
TOKENIZER_CANARY_TEXT = "TOKEN ARRAY CANARY"
TOKENIZER_CANARY_IDS = (60738, 30094, 18916, 8378)

V1_EVIDENCE = {
    "full-information": {
        "run_id": balanced.FULL_RUN_ID,
        "classification": "BALANCED_OPAQUE_RELATIONAL_VISIBLE",
        "manifest_sha256": "A129BBD9BA9DEF0842144178B94A0269F66022EF82DB60D517CDD0C423CC2E1D",
        "result_sha256": "B57FE3598A03F7CBB2765F77CE702293F72BBF900424F9592D719CF02DA458F8",
        "closure_sha256": "FE918337A82C7D9D2C59DE56514D284C736A239226F03C91E8025811E92E8DDA",
    },
    "delete-parent-0": {
        "run_id": balanced.DELETE_A_RUN_ID,
        "classification": "PARENT_A_INFORMATION_DEPENDENCE_SUPPORTED",
        "manifest_sha256": "03508F7AE5E5F4A812C43F02FD31A3EE4009530B1CB17E61056213AE1079E74E",
        "result_sha256": "7AE2578A6D48831B5335CE2826424EA375EB169A218502B404BD031507635846",
        "closure_sha256": "4A2DD55ECC2DD03AE272F08FEB611F97E714EB587A28BD0660673E116286C873",
    },
    "delete-parent-1": {
        "run_id": balanced.DELETE_B_RUN_ID,
        "classification": "PARENT_B_INFORMATION_DEPENDENCE_SUPPORTED",
        "manifest_sha256": "EF2160E9CA719A4120FF7F7F226A1AD76F0BF08FE6A5C58CFFADCBCE2AB8B782",
        "result_sha256": "F0E24AAA61A2E8D0EC567F93444E08FD81EB8AFE36E2C01D7397A4D06FD46CB6",
        "closure_sha256": "880E238B877602AE3A869E2071DBDF1B0D3EE0FAF3D0D019C2D133D05C57BF90",
    },
}

V1_CAUSAL_PACKAGE_SHA256 = parent.BINDING_1_CAUSAL_SHA256
V1_PACKAGE_SHA256 = parent.BINDING_1_PACKAGE_SHA256
FORBIDDEN_PUBLIC_VALUE_RE = re.compile(rb'"(?:K|C)[0-9]{2}"')


class AsymmetryAuditError(RuntimeError):
    """The source custody, private reconstruction, or public boundary changed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AsymmetryAuditError(message)


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


def json_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _json_object(path: Path, label: str) -> dict[str, Any]:
    _require(path.is_file() and not path.is_symlink(), f"{label} is absent or unsafe")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AsymmetryAuditError(f"{label} is malformed") from exc
    _require(isinstance(value, dict), f"{label} is not an object")
    return value


def _safe_regular_file(path: Path, label: str, *, exact_size: int | None = None) -> None:
    _require(path.is_file() and not path.is_symlink(), f"{label} is absent or unsafe")
    mode = path.lstat().st_mode
    reparse = getattr(path.lstat(), "st_file_attributes", 0) & getattr(
        stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400
    )
    _require(stat.S_ISREG(mode) and not reparse, f"{label} is not a regular file")
    if exact_size is not None:
        _require(path.stat().st_size == exact_size, f"{label} size changed")


_GGUF_SCALAR_FORMAT = {
    0: "B",
    1: "b",
    2: "H",
    3: "h",
    4: "I",
    5: "i",
    6: "f",
    7: "?",
    10: "Q",
    11: "q",
    12: "d",
}


def _read_exact(stream: BinaryIO, size: int, label: str) -> bytes:
    data = stream.read(size)
    _require(len(data) == size, f"GGUF {label} is truncated")
    return data


def _read_u32(stream: BinaryIO) -> int:
    return int(struct.unpack("<I", _read_exact(stream, 4, "u32"))[0])


def _read_u64(stream: BinaryIO) -> int:
    return int(struct.unpack("<Q", _read_exact(stream, 8, "u64"))[0])


def _read_gguf_string(stream: BinaryIO) -> str:
    length = _read_u64(stream)
    _require(length <= 64 * 1024 * 1024, "GGUF metadata string is too large")
    try:
        return _read_exact(stream, length, "string").decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AsymmetryAuditError("GGUF metadata string is invalid UTF-8") from exc


def _read_gguf_value(stream: BinaryIO, value_type: int, *, keep: bool) -> Any:
    if value_type == 8:
        value = _read_gguf_string(stream)
        return value if keep else None
    if value_type == 9:
        element_type = _read_u32(stream)
        count = _read_u64(stream)
        _require(count <= 2_000_000, "GGUF metadata array is too large")
        if keep:
            return [
                _read_gguf_value(stream, element_type, keep=True)
                for _ in range(count)
            ]
        for _ in range(count):
            _read_gguf_value(stream, element_type, keep=False)
        return None
    fmt = _GGUF_SCALAR_FORMAT.get(value_type)
    _require(fmt is not None, "GGUF metadata type is unsupported")
    value = struct.unpack(
        "<" + str(fmt),
        _read_exact(stream, struct.calcsize(str(fmt)), "scalar"),
    )[0]
    return value if keep else None


class OfflineTokenizer:
    """Pinned GGUF tokenizer metadata; no model tensors or endpoint are used."""

    def __init__(self, model_path: Path) -> None:
        _safe_regular_file(model_path, "tokenizer model", exact_size=EXPECTED_MODEL_SIZE)
        wanted = {
            "tokenizer.ggml.model",
            "tokenizer.ggml.pre",
            "tokenizer.ggml.tokens",
            "tokenizer.ggml.merges",
        }
        metadata: dict[str, Any] = {}
        with model_path.open("rb") as stream:
            _require(_read_exact(stream, 4, "magic") == b"GGUF", "model is not GGUF")
            version = _read_u32(stream)
            tensor_count = _read_u64(stream)
            metadata_count = _read_u64(stream)
            _require(version == 3, "GGUF version changed")
            _require(tensor_count == 733, "GGUF tensor count changed")
            _require(metadata_count <= 512, "GGUF metadata count is unsafe")
            for _ in range(metadata_count):
                key = _read_gguf_string(stream)
                value_type = _read_u32(stream)
                value = _read_gguf_value(stream, value_type, keep=key in wanted)
                if key in wanted:
                    metadata[key] = value
        _require(set(metadata) == wanted, "GGUF tokenizer metadata is incomplete")
        _require(
            metadata["tokenizer.ggml.model"] == EXPECTED_TOKENIZER_MODEL
            and metadata["tokenizer.ggml.pre"] == EXPECTED_TOKENIZER_PRE,
            "GGUF tokenizer identity changed",
        )
        tokens = metadata["tokenizer.ggml.tokens"]
        merges = metadata["tokenizer.ggml.merges"]
        _require(
            isinstance(tokens, list)
            and isinstance(merges, list)
            and all(isinstance(item, str) for item in tokens)
            and all(isinstance(item, str) and " " in item for item in merges),
            "GGUF tokenizer tables are malformed",
        )
        try:
            from tokenizers import Tokenizer
            from tokenizers.models import BPE
            from tokenizers.pre_tokenizers import ByteLevel
        except ImportError as exc:
            raise AsymmetryAuditError(
                "the static audit requires the Python tokenizers package"
            ) from exc
        model = BPE(
            vocab={token: index for index, token in enumerate(tokens)},
            merges=[tuple(item.split(" ", 1)) for item in merges],
        )
        tokenizer = Tokenizer(model)
        tokenizer.pre_tokenizer = ByteLevel(add_prefix_space=False, use_regex=True)
        self._tokenizer = tokenizer
        self.metadata_sha256 = json_sha256(
            {
                "model": metadata["tokenizer.ggml.model"],
                "pre": metadata["tokenizer.ggml.pre"],
                "tokens": tokens,
                "merges": merges,
            }
        )
        _require(
            tuple(self.ids(TOKENIZER_CANARY_TEXT)) == TOKENIZER_CANARY_IDS,
            "pinned tokenizer canary changed",
        )
        opaque_lengths = {self.length(item) for item in balanced.ALIASES}
        _require(opaque_lengths == {3}, "opaque symbol token lengths changed")

    def ids(self, text: str) -> list[int]:
        return list(self._tokenizer.encode(text, add_special_tokens=False).ids)

    def length(self, text: str) -> int:
        return len(self.ids(text))

    def public_evidence(self) -> dict[str, Any]:
        return {
            "pinned_model_file_sha256": EXPECTED_MODEL_SHA256,
            "model_file_size_bytes": EXPECTED_MODEL_SIZE,
            "tokenizer_model": EXPECTED_TOKENIZER_MODEL,
            "tokenizer_pre": EXPECTED_TOKENIZER_PRE,
            "tokenizer_metadata_sha256": self.metadata_sha256,
            "tokenizer_canary_ids_sha256": json_sha256(list(TOKENIZER_CANARY_IDS)),
            "tokenizer_canary_length": len(TOKENIZER_CANARY_IDS),
            "opaque_symbol_count": len(balanced.ALIASES),
            "opaque_symbol_scalar_count_each": 1,
            "opaque_symbol_token_id_length_min": 3,
            "opaque_symbol_token_id_length_max": 3,
            "opaque_symbol_token_id_lengths_all_equal": True,
            "model_tensors_loaded": False,
            "full_model_file_rehashed_during_audit": False,
            "tokenizer_metadata_reconstructed_from_supplied_file": True,
            "server_started": False,
            "endpoint_contacted": False,
            "model_generations": 0,
        }


def _hash_file(path: Path, expected: str, label: str) -> bytes:
    _safe_regular_file(path, label)
    data = path.read_bytes()
    _require(sha256_bytes(data) == expected, f"{label} changed")
    return data


def _verify_v1_evidence(repository: Path) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for arm_id, expected in V1_EVIDENCE.items():
        run_id = str(expected["run_id"])
        root = repository / "state/catalytic_kernel_0" / run_id
        manifest_bytes = _hash_file(
            root / "manifest.json", str(expected["manifest_sha256"]), f"{arm_id} manifest"
        )
        result_bytes = _hash_file(
            root / "result.json", str(expected["result_sha256"]), f"{arm_id} result"
        )
        closure_bytes = _hash_file(
            root / "closure.json", str(expected["closure_sha256"]), f"{arm_id} closure"
        )
        del manifest_bytes
        result = json.loads(result_bytes)
        closure = json.loads(closure_bytes)
        _require(
            isinstance(result, dict)
            and result.get("status") == "complete"
            and result.get("run_id") == run_id
            and result.get("balanced_classification") == expected["classification"],
            f"{arm_id} result truth changed",
        )
        _require(
            isinstance(closure, dict)
            and closure.get("manifest_sha256") == expected["manifest_sha256"]
            and closure.get("result_sha256") == expected["result_sha256"]
            and closure.get("run_lock_absent") is True,
            f"{arm_id} closure binding changed",
        )
        results[arm_id] = result
    _hash_file(
        repository / parent.BINDING_1_CAUSAL_PATH,
        V1_CAUSAL_PACKAGE_SHA256,
        "binding-1 causal adjudication",
    )
    _hash_file(
        repository / parent.BINDING_1_PACKAGE_PATH,
        V1_PACKAGE_SHA256,
        "binding-1 package",
    )
    return results


def _transform_prompt_tokens(result: Mapping[str, Any]) -> int:
    outcomes = result.get("request_outcomes")
    _require(isinstance(outcomes, list), "binding-1 request outcomes are absent")
    matches = [
        item
        for item in outcomes
        if isinstance(item, Mapping) and item.get("request_id") == "transform"
    ]
    _require(len(matches) == 1, "binding-1 transform transport is ambiguous")
    transport = matches[0].get("transport")
    _require(isinstance(transport, Mapping), "binding-1 transform transport is absent")
    tokens = transport.get("prompt_tokens")
    _require(isinstance(tokens, int) and tokens > 0, "binding-1 prompt tokens are invalid")
    return tokens


def _rank_zero_score(
    runtime: balanced.BalancedOpaqueRuntime,
    selected: str,
    transform: Mapping[str, Any],
) -> int:
    receipt = runtime.normalize_extraction(selected, transform)
    score = receipt["controller_private_evaluation"]["full_public_score"]
    _require(isinstance(score, int), "rank-zero private score is invalid")
    return score


def _bounded_parent_diagnostics(
    *,
    binding_label: str,
    parent_index: int,
    private: balanced.PrivateBinding,
    runtime: balanced.BalancedOpaqueRuntime,
    retained_parent: Mapping[str, Any],
    deletion_receipt: Mapping[str, Any],
    transform: Mapping[str, Any],
    prompt_tokens: int,
    fixed_seed: int,
    observed_final_score: int,
    observed_final_selection_was_rank_zero: bool,
    classification: str,
    tokenizer: OfflineTokenizer,
) -> dict[str, Any]:
    branch_id = "branch-a" if parent_index == 0 else "branch-b"
    support = retained_parent.get("support_aliases")
    ranking = transform.get("ranking")
    _require(
        isinstance(support, list)
        and len(support) == 5
        and isinstance(ranking, list)
        and len(ranking) == 3,
        "private diagnostic geometry changed",
    )
    singleton = private.internal_to_alias[balanced.EXPECTED_FULL_SUPPORT[0]]
    selected = str(ranking[0])
    _require(singleton in support and selected in balanced.ALIASES, "private diagnostic identity changed")
    support_token_lengths = [tokenizer.length(str(item)) for item in support]
    selected_in_support = selected in support
    retained_bytes = canonical_json_bytes(retained_parent)
    receipt_bytes = canonical_json_bytes(deletion_receipt)
    lexical_ordinal = balanced.ALIASES.index(singleton) + 1
    result = {
        "binding": binding_label,
        "parent_role": f"parent-{parent_index}",
        "private_singleton_internal_support_ordinal_1_based": (
            list(balanced.EXPECTED_SUPPORTS[branch_id]).index(
                balanced.EXPECTED_FULL_SUPPORT[0]
            )
            + 1
        ),
        "private_singleton_transform_serialization_ordinal_1_based": support.index(singleton)
        + 1,
        "private_singleton_global_lexical_ordinal_1_based": lexical_ordinal,
        "private_singleton_global_lexical_percentile": round(
            (lexical_ordinal - 1) / (len(balanced.ALIASES) - 1), 6
        ),
        "private_singleton_symbol_count": 1,
        "private_singleton_token_id_length": tokenizer.length(singleton),
        "support_token_id_length_min": min(support_token_lengths),
        "support_token_id_length_max": max(support_token_lengths),
        "support_token_id_lengths_all_equal": len(set(support_token_lengths)) == 1,
        "rank_zero_in_retained_support": selected_in_support,
        "rank_zero_retained_support_ordinal_1_based": (
            support.index(selected) + 1 if selected_in_support else None
        ),
        "rank_zero_selected_private_singleton": selected == singleton,
        "rank_zero_selected_first_serialized_support_member": (
            selected_in_support and selected == support[0]
        ),
        "rank_zero_selected_lexically_smallest_support_symbol": (
            selected_in_support and selected == min(str(item) for item in support)
        ),
        "rank_zero_selected_shortest_token_support_symbol": (
            selected_in_support
            and tokenizer.length(selected) == min(support_token_lengths)
        ),
        "rank_zero_global_lexical_ordinal_1_based": balanced.ALIASES.index(selected) + 1,
        "rank_zero_token_id_length": tokenizer.length(selected),
        "commitment_receipt_field_shape": sorted(str(key) for key in deletion_receipt),
        "commitment_receipt_serialized_bytes": len(receipt_bytes),
        "commitment_receipt_serialized_token_ids": tokenizer.length(
            receipt_bytes.decode("utf-8")
        ),
        "complete_retained_parent_serialized_bytes": len(retained_bytes),
        "complete_retained_parent_serialized_token_ids": tokenizer.length(
            retained_bytes.decode("utf-8")
        ),
        "prompt_tokens": prompt_tokens,
        "fixed_request_seed": fixed_seed,
        "transform_operator": transform.get("operator"),
        "transform_ranking_length": len(ranking),
        "selected_rank": 0,
        "rank_zero_private_public_score": _rank_zero_score(runtime, selected, transform),
        "observed_final_private_public_score": observed_final_score,
        "observed_final_selection_was_rank_zero": observed_final_selection_was_rank_zero,
        "classification": classification,
    }
    _require(
        result["rank_zero_private_public_score"] == observed_final_score,
        "shared transform-rank-head score differs from the observed final score",
    )
    return result


def _binding_1_diagnostics(
    repository: Path,
    results: Mapping[str, Mapping[str, Any]],
    tokenizer: OfflineTokenizer,
) -> dict[str, Any]:
    private = balanced._private_binding_from_repository(repository, balanced.BINDING_1)
    records: list[dict[str, Any]] = []
    specifications = (
        ("delete-parent-0", balanced.DELETE_A_RUN_ID, 1),
        ("delete-parent-1", balanced.DELETE_B_RUN_ID, 0),
    )
    for arm_id, run_id, retained_index in specifications:
        result = results[arm_id]
        runtime = balanced.BalancedOpaqueRuntime(
            repository=repository,
            run_id=run_id,
            private=private,
        )
        branch_a = result.get("branch_a")
        branch_b = result.get("branch_b")
        transform = result.get("transform")
        extraction = result.get("extraction")
        _require(
            isinstance(branch_a, Mapping)
            and isinstance(branch_b, Mapping)
            and isinstance(transform, Mapping)
            and isinstance(extraction, Mapping),
            "binding-1 private artifacts are absent",
        )
        runtime.verify_branch_artifact(branch_a)
        runtime.verify_branch_artifact(branch_b)
        runtime.verify_transform_artifact(transform)
        runtime.verify_extraction_artifact(extraction, transform)
        parents = [branch_a, branch_b]
        retained = parents[retained_index]
        deleted = parents[1 - retained_index]
        evaluation = extraction.get("controller_private_evaluation")
        _require(isinstance(evaluation, Mapping), "binding-1 private evaluation is absent")
        records.append(
            _bounded_parent_diagnostics(
                binding_label="binding-1",
                parent_index=retained_index,
                private=private,
                runtime=runtime,
                retained_parent=retained,
                deletion_receipt=runtime.deletion_receipt(deleted),
                transform=transform,
                prompt_tokens=_transform_prompt_tokens(result),
                fixed_seed=balanced._request_seed("transform"),
                observed_final_score=int(evaluation["full_public_score"]),
                observed_final_selection_was_rank_zero=(
                    extraction.get("candidate_alias") == transform["ranking"][0]
                ),
                classification=str(result["balanced_classification"]),
                tokenizer=tokenizer,
            )
        )
    return {
        "binding": "binding-1",
        "private_binding_secret_commitment_sha256": private.secret_commitment,
        "private_mapping_commitment_sha256": private.alias_map_commitment,
        "process_variant": "v1-six-request-model-authored-extraction",
        "transform_rank_head_model_authored": True,
        "extraction_variant": "model-authored",
        "parents": records,
    }


def _binding_2_diagnostics(
    repository: Path,
    tokenizer: OfflineTokenizer,
) -> dict[str, Any]:
    archive, events, _original_result, _receipt = recovery._verify_original_truth(repository)
    source_runtime = parent._source_runtime(repository)
    private = balanced._private_binding_from_repository(repository, balanced.BINDING_2)
    branch_a, branch_b = parent._source_parent_artifacts(repository)
    experiment_key = parent._experiment_key(source_runtime)
    frozen: dict[str, tuple[Any, dict[str, Any], Any, dict[str, Any]]] = {}
    for arm_id in parent.ARM_IDS:
        started = parent._event_for(events, "request-started", arm_id)
        _require(started is not None, "binding-2 request-started evidence is absent")
        request_sha256 = str(started["facts"]["model_request_sha256"])
        capture = scientific.verify_capture(
            archive / f"capture-{arm_id}.json",
            experiment_key=experiment_key,
            arm_id=arm_id,
            model_request_sha256=request_sha256,
        )
        frozen[arm_id] = parent._freeze_captured_arm(
            repository,
            arm_id,
            capture,
            int(started["facts"]["rendered_prompt_tokens"]),
        )
    _require(set(frozen) == set(parent.ARM_IDS), "binding-2 both-head freeze changed")
    records: list[dict[str, Any]] = []
    for arm_id, retained_index in (("delete-parent-0", 1), ("delete-parent-1", 0)):
        runtime, transform, selected_receipt, transport = frozen[arm_id]
        facts = parent._adjudicate_frozen_arm(
            runtime,
            transform,
            selected_receipt,
            arm_id,
        )
        parents = [branch_a, branch_b]
        retained = parents[retained_index]
        deleted = parents[1 - retained_index]
        records.append(
            _bounded_parent_diagnostics(
                binding_label="binding-2",
                parent_index=retained_index,
                private=private,
                runtime=runtime,
                retained_parent=retained,
                deletion_receipt=source_runtime.deletion_receipt(deleted),
                transform=transform,
                prompt_tokens=int(transport["prompt_tokens"]),
                fixed_seed=parent.arm_seed(arm_id),
                observed_final_score=int(facts["private_public_score"]),
                observed_final_selection_was_rank_zero=True,
                classification=str(facts["classification"]),
                tokenizer=tokenizer,
            )
        )
    return {
        "binding": "binding-2",
        "private_binding_secret_commitment_sha256": private.secret_commitment,
        "private_mapping_commitment_sha256": private.alias_map_commitment,
        "process_variant": "v2-transform-only-replay-deterministic-rank-zero-extraction",
        "transform_rank_head_model_authored": True,
        "extraction_variant": "controller-deterministic-rank-zero",
        "parents": records,
    }


def _mechanistic_adjudication() -> dict[str, Any]:
    return {
        "explanations": {
            "PARENT_A_DIRECTIONAL_DEPENDENCE_STABLE_ACROSS_OBSERVED_BINDINGS": (
                "SUPPORTED_AT_SHARED_TRANSFORM_RANK_HEAD_ENDPOINT_WITH_PROCESS_QUALIFIER"
            ),
            "PARENT_B_DEPENDENCE_PRIVATE_BINDING_SENSITIVE": "OBSERVED",
            "SINGLETON_PRESENTATION_POSITION_CONFOUND_PLAUSIBLE": (
                "PLAUSIBLE_AND_DIAGNOSTICALLY_ALIGNED"
            ),
            "LEXICAL_OR_TOKENIZATION_BIAS_CONFOUND_PLAUSIBLE": (
                "LEXICAL_IDENTITY_OR_POSITION_PLAUSIBLE_TOKEN_LENGTH_NOT_DISCRIMINATING"
            ),
            "FIXED_SEED_INTERACTION_CONFOUND_PLAUSIBLE": (
                "PLAUSIBLE_BECAUSE_BINDING_2_CONTROL_SEEDS_DIFFER"
            ),
            "COMMITMENT_RECEIPT_SHAPE_CONFOUND_PLAUSIBLE": (
                "FIELD_AND_BYTE_SHAPE_REJECTED_TOKEN_SEQUENCE_LENGTH_REMAINS_PLAUSIBLE"
            ),
            "TRUE_DIRECTIONAL_PARENT_ASYMMETRY_PLAUSIBLE": "PLAUSIBLE",
            "INSUFFICIENT_EVIDENCE_TO_DISTINGUISH": True,
        },
        "rejected_explanations": {
            "OPAQUE_SYMBOL_TOKEN_LENGTH_ADVANTAGE": (
                "REJECTED_ALL_64_SYMBOLS_HAVE_THREE_TOKEN_IDS"
            ),
            "DELETION_RECEIPT_FIELD_OR_BYTE_SHAPE_DIFFERENCE": (
                "REJECTED_ALL_CONTROLS_HAVE_FOUR_FIELDS_AND_189_CANONICAL_BYTES"
            ),
            "MODEL_AUTHORED_EXTRACTION_CAUSED_BINDING_2_PARENT_B_HIT": (
                "REJECTED_BINDING_2_SELECTION_WAS_DETERMINISTIC_RANK_ZERO"
            ),
            "LEXICALLY_FIRST_SELECTION_FULLY_EXPLAINS_BOTH_BINDING_2_ARMS": (
                "REJECTED_AS_COMPLETE_EXPLANATION_PARENT_A_SELECTED_SERIALIZED_POSITION_TWO"
            ),
            "CUSTODY_FAILURE_EXPLAINS_RECOVERED_ARM_DIFFERENCE": (
                "REJECTED_BY_AUTHENTICATED_ZERO_CONTACT_REPLAY"
            ),
        },
        "synthesis": (
            "The binding-2 Parent-B hit is aligned with the private singleton being "
            "the first serialized and lexically smallest retained support member. "
            "That alignment did not force a Parent-A hit, so presentation luck and "
            "true directional asymmetry both remain viable. Differing control seeds "
            "and commitment token sequences remain unresolved nuisance channels."
        ),
    }


def _follow_on_design() -> dict[str, Any]:
    seed_0 = parent.arm_seed("delete-parent-0")
    seed_1 = parent.arm_seed("delete-parent-1")
    return {
        "design_id": "balanced-opaque-transform-only-position-seed-panel-v1",
        "scientific_decision": "COUNTERBALANCED_PANEL_REQUIRED",
        "one_new_binding_scientifically_adequate": False,
        "reason": (
            "One binding cannot independently separate singleton presentation from "
            "deterministic seed interaction at the shared transform-rank-head endpoint."
        ),
        "fresh_private_binding_count": 2,
        "binding_selection_before_model_outcomes": True,
        "binding_selection_law": {
            "low_position_binding": (
                "singleton is first in both exact serialized five-member supports and "
                "lies in the lowest preregistered global lexical quartile"
            ),
            "high_position_binding": (
                "singleton is last in both exact serialized five-member supports and "
                "lies in the highest preregistered global lexical quartile"
            ),
            "selection_inputs": (
                "private commitments, ordinals, lengths, and booleans only"
            ),
            "selection_after_model_outcomes": False,
            "private_correspondence_published": False,
        },
        "seed_blocks": [
            {
                "seed_block": 0,
                "fixed_transform_seed": seed_0,
                "source": "historical-binding-2-delete-parent-0-seed",
            },
            {
                "seed_block": 1,
                "fixed_transform_seed": seed_1,
                "source": "historical-binding-2-delete-parent-1-seed",
            },
        ],
        "seed_law": (
            "Within each binding and seed block, full-information, delete-parent-0, "
            "and delete-parent-1 use the same exact transform seed."
        ),
        "arms_per_binding_seed_cell": [
            "full-information",
            "delete-parent-0",
            "delete-parent-1",
        ],
        "model_generation_stage": "transform-only",
        "deterministic_rank_head_extraction_all_arms": True,
        "borrow_model_requests": 0,
        "branch_model_requests": 0,
        "model_authored_extraction_requests": 0,
        "restore_model_requests": 0,
        "future_model_generations": 12,
        "generation_count_derivation": "2 bindings x 2 seed blocks x 3 transform arms",
        "serialization_controls": {
            "opaque_symbol_token_id_lengths_equal": True,
            "parent_support_cardinality": 5,
            "commitment_receipt_field_shape_identical": True,
            "commitment_receipt_canonical_byte_length_identical": True,
            "pairwise_delete_arm_prompt_token_lengths_must_match": True,
            "pairwise_retained_parent_token_lengths_must_match": True,
            "pairwise_commitment_receipt_token_lengths_must_match": True,
            "failure_to_find_preoutcome_matched_bindings": "STOP_WITHOUT_AUTHORITY",
        },
        "adjudication_law": {
            "parent_b_dependence_across_both_positions_and_seeds": (
                "presentation-luck explanation weakened; bilateral replication may be "
                "prepared only for separate static adjudication"
            ),
            "parent_b_hit_tracks_low_first_position": (
                "private-binding presentation confound supported"
            ),
            "either_parent_outcome_flips_by_seed_within_binding": (
                "deterministic seed interaction supported"
            ),
            "parent_b_hit_across_positions_and_seeds_while_parent_a_dependence_holds": (
                "true directional asymmetry strengthened but not generalized"
            ),
            "full_information_failure_in_any_cell": (
                "cell inconclusive; no deletion claim from that cell"
            ),
        },
        "implementation_in_this_operation": False,
        "authority_created_or_consumed": False,
        "live_execution_authorized": False,
        "next_action": (
            "Separately authorize static implementation and preregistration of the "
            "two-binding two-seed transform-only panel; no live execution."
        ),
    }


def _assert_no_smuggle(
    repository: Path,
    document: Mapping[str, Any],
) -> None:
    payload = canonical_json_bytes(document)
    _require(
        FORBIDDEN_PUBLIC_VALUE_RE.search(payload) is None,
        "an opaque or internal symbol entered the public audit",
    )
    for configuration in (balanced.BINDING_1, balanced.BINDING_2):
        secret_path = balanced.private_secret_path(repository, configuration)
        _safe_regular_file(secret_path, "private binding root", exact_size=32)
        _require(
            secret_path.read_bytes() not in payload,
            "a private binding root entered the public audit",
        )
    parent._assert_public_no_smuggle(document)


def render_audit(repository: Path, model_path: Path) -> dict[str, Any]:
    repository = repository.resolve()
    tokenizer = OfflineTokenizer(model_path.resolve())
    recovery_report = recovery.validate_forensic_recovery(repository)
    _require(
        recovery_report["artifact_sha256"] == recovery.sha256_bytes(
            (repository / recovery.ARTIFACT_PATH).read_bytes()
        )
        == "110DAE908E4C1F01747C2CBBEA9F3A34BB2ACA61397D55B0648D82453A3DD975",
        "forensic recovery artifact changed",
    )
    v1_results = _verify_v1_evidence(repository)
    parent.verify_source_evidence(repository)
    diagnostics = [
        _binding_1_diagnostics(repository, v1_results, tokenizer),
        _binding_2_diagnostics(repository, tokenizer),
    ]
    document: dict[str, Any] = {
        "schema_version": 1,
        "artifact_id": ARTIFACT_ID,
        "status": STATUS,
        "scope": (
            "Static private reconstruction of the Parent-A and Parent-B asymmetry "
            "at the shared model-authored transform-rank-head endpoint."
        ),
        "source_evidence": {
            "starting_main": STARTING_MAIN,
            "binding_1": {
                "causal_adjudication_sha256": V1_CAUSAL_PACKAGE_SHA256,
                "package_sha256": V1_PACKAGE_SHA256,
                "runs": [
                    {
                        "arm": arm_id,
                        "run_id": facts["run_id"],
                        "classification": facts["classification"],
                        "manifest_sha256": facts["manifest_sha256"],
                        "result_sha256": facts["result_sha256"],
                        "closure_sha256": facts["closure_sha256"],
                    }
                    for arm_id, facts in V1_EVIDENCE.items()
                ],
            },
            "binding_2": {
                "source_full_information": {
                    "run_id": parent.SOURCE_RUN_ID,
                    "authority_receipt_sha256": parent.SOURCE_HASHES["receipt"],
                    "manifest_sha256": parent.SOURCE_HASHES["manifest"],
                    "result_sha256": parent.SOURCE_HASHES["result"],
                    "closure_sha256": parent.SOURCE_HASHES["closure"],
                    "archive_sha256": parent.SOURCE_ARCHIVE_SHA256,
                    "publication_record_id": parent.SOURCE_PUBLICATION_ID,
                    "publication_record_sha256": parent.SOURCE_PUBLICATION_SHA256,
                    "cross_binding_adjudication_sha256": parent.CROSS_BINDING_SHA256,
                },
                "original_terminal_status": "INCONCLUSIVE",
                "original_terminal_reason": "durable-finalization-custody-gate-failed",
                "authority_receipt_sha256": recovery.ORIGINAL_EVIDENCE_SHA256[
                    "authority_receipt"
                ],
                "manifest_sha256": recovery.ORIGINAL_EVIDENCE_SHA256["manifest"],
                "result_sha256": recovery.ORIGINAL_EVIDENCE_SHA256["result"],
                "closure_sha256": recovery.ORIGINAL_EVIDENCE_SHA256["closure"],
                "archive_sha256": recovery.ORIGINAL_ARCHIVE_SHA256,
                "forensic_artifact_sha256": recovery_report["artifact_sha256"],
                "capture_sha256": {
                    "delete-parent-0": recovery.ORIGINAL_EVIDENCE_SHA256[
                        "capture_delete_parent_0"
                    ],
                    "delete-parent-1": recovery.ORIGINAL_EVIDENCE_SHA256[
                        "capture_delete_parent_1"
                    ],
                },
                "execution_evidence_rewritten": False,
            },
            "tokenizer": tokenizer.public_evidence(),
        },
        "claim_correction": {
            "supported_claim": CORRECTED_SUPPORTED_CLAIM,
            "qualification": CORRECTED_QUALIFICATION,
            "prior_wording_narrowed": True,
            "historical_forensic_evidence_removed_or_rewritten": False,
            "pure_binding_only_replication_supported": False,
        },
        "bounded_private_diagnostics": diagnostics,
        "mechanistic_adjudication": _mechanistic_adjudication(),
        "minimum_follow_on": _follow_on_design(),
        "locked_claims": {
            "PURE_BINDING_ONLY_REPLICATION_UNDER_IDENTICAL_END_TO_END_PROCESS": "LOCKED",
            "PARENT_B_CROSS_BINDING_REPLICATION": "LOCKED",
            "BILATERAL_DEPENDENCE": "LOCKED",
            "GENERAL_TWO_PARENT_NECESSITY": "LOCKED",
            "TRANSFER": "LOCKED",
            "GENERAL_CATALYTIC_INFERENCE": "LOCKED",
            "TASK_ADVANTAGE": "LOCKED",
            "SUPERIORITY": "LOCKED",
            "SOTA": "LOCKED",
            "BROADER_PROCESS_LOCAL_HOLOSTATE": "LOCKED",
            "RESTART_PERSISTENCE": "LOCKED",
            "DEEP": "DISABLED",
            "automatic_promotion": False,
        },
        "no_smuggle": {
            "private_symbols_persisted": False,
            "internal_candidate_ids_persisted": False,
            "private_mappings_persisted": False,
            "support_member_identities_persisted": False,
            "transform_rankings_persisted": False,
            "raw_prompts_persisted": False,
            "raw_responses_persisted": False,
            "private_roots_persisted": False,
            "cross_binding_correspondence_persisted": False,
            "bounded_ordinals_lengths_booleans_hashes_and_categories_only": True,
        },
        "operation_boundary": {
            "model_requests": 0,
            "model_generations": 0,
            "http_requests": 0,
            "sidecar_launches": 0,
            "authority_created": False,
            "authority_consumed": False,
            "scientific_retry": False,
            "runtime_modified": False,
            "results_ledger_modified": False,
        },
        "next_boundary": (
            "Separately authorize static implementation and preregistration of the "
            "two-binding two-seed transform-only panel; no live execution."
        ),
    }
    _assert_no_smuggle(repository, document)
    return document


def validate_audit(repository: Path, model_path: Path) -> dict[str, Any]:
    repository = repository.resolve()
    rendered = render_audit(repository, model_path)
    path = repository / ARTIFACT_PATH
    _safe_regular_file(path, "asymmetry audit artifact")
    expected = canonical_json_bytes(rendered) + b"\n"
    observed = path.read_bytes()
    _require(observed == expected, "asymmetry artifact differs from independent render")
    return {
        "status": "pass",
        "artifact_id": ARTIFACT_ID,
        "artifact_sha256": sha256_bytes(observed),
        "supported_claim": CORRECTED_SUPPORTED_CLAIM,
        "future_model_generations": rendered["minimum_follow_on"][
            "future_model_generations"
        ],
        "private_correspondence_published": False,
        "model_generations_during_audit": 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("render", "validate"))
    parser.add_argument("--repository", required=True)
    parser.add_argument(
        "--model",
        default=os.environ.get("NEO3000_TOKENIZER_MODEL"),
        help="Exact pinned GGUF used only for offline tokenizer metadata.",
    )
    args = parser.parse_args()
    if not args.model:
        parser.error("--model or NEO3000_TOKENIZER_MODEL is required")
    return args


def main() -> int:
    args = parse_args()
    repository = Path(args.repository)
    model_path = Path(args.model)
    if args.action == "render":
        result = render_audit(repository, model_path)
    else:
        result = validate_audit(repository, model_path)
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
