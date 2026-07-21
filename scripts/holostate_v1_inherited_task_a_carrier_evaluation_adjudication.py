#!/usr/bin/env python3
"""Zero-contact adjudication of immutable inherited Task-A carrier evidence."""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import struct
import subprocess
from pathlib import Path
from typing import Any, BinaryIO, Mapping, Sequence

import holostate_v1_inherited_task_a_carrier_evaluation as probe
import holostate_v1_warm_trajectory_related_task_evaluation_adjudication as warm_adjudication


class InheritedCarrierAdjudicationError(ValueError):
    """Immutable inherited-carrier evidence cannot support bounded publication."""


SOURCE_COMMIT = "26aa75a27ee17d625c0965a1ccb96373d925f735"
SOURCE_MODULE_PATH = "scripts/holostate_v1_inherited_task_a_carrier_evaluation.py"
ARTIFACT_PATH = Path("lab/holostate_v1_inherited_task_a_carrier_evaluation_v1_adjudication_1.json")
RESULTS_PATH = Path("lab/results.jsonl")
ADJUDICATION_ID = "holostate-v1-inherited-task-a-carrier-evaluation-v1-adjudication-1"
RECORD_ID = "neo-exp-0049"
PREDECESSOR_RECORD_ID = "neo-exp-0048"
EXPECTED_LEDGER_LINE = 62

LIVE_CLASSIFICATION = "PROCESS_LOCAL_INHERITED_TASK_A_CARRIER_EXACT_REUSE_NOT_SUPPORTED"
PARTIAL_REUSE_CLASSIFICATION = "PROCESS_LOCAL_INHERITED_TASK_A_PARTIAL_PREFIX_REUSE_REPLICATED"
EXACT_REUSE_CLASSIFICATION = "EXACT_INHERITED_TASK_A_PREFIX_REUSE_NOT_SUPPORTED"
EFFICIENCY_CLASSIFICATION = (
    "PROCESS_LOCAL_INHERITED_TASK_A_PARTIAL_REUSE_WITH_EQUAL_ACCURACY_AND_FRESH_TOKEN_ADVANTAGE_SUPPORTED"
)
CAUSAL_CLASSIFICATION = (
    "EXECUTABLE_REUSE_LIMITED_BY_MIXED_CHECKPOINT_AND_TOKENIZATION_BOUNDARIES_CONFIRMED"
)
CLOSURE_CLASSIFICATION = "EXACT_INHERITED_TASK_A_CARRIER_RESTORATION_NOT_SUPPORTED"
BOUNDED_INTERPRETATION = (
    "PARTIAL_PROCESS_LOCAL_TASK_A_STATE_WAS_INHERITED_ACROSS_ALL_FOUR_RELATED_TASKS_"
    "WITH_EQUAL_ACCURACY_AND_LOWER_FRESH_TOKEN_COST_BUT_THE_STATIC_LEXICAL_PREFIX_"
    "EXCEEDED_THE_RUNTIME_SAFE_EXECUTABLE_REUSE_BOUNDARY"
)
NEXT_BOUNDARY = "STATICALLY_SELECT_MINIMUM_RESPONSE_TO_EXECUTABLE_REUSE_BOUNDARY"

SOURCE_BINDINGS = {
    "public_corpus_sha256": "A45FF0A6DCD8E3E75CBE0B0F7A572DB023B0E7CE81093F7C82155D0A4DC3D4A9",
    "protected_evaluator_sha256": "AAC8CC0DEE3C748F92A9BA350E8EF32063171F5AF9B24754D55B1A7E71B0BE3E",
    "preregistration_artifact_sha256": "1C34C4FB65569C31984FD8E611D3F95AC344D61CCD594DE02BE4BE856C671F30",
    "preregistration_file_sha256": "C549D1D8700D4316A3F623687EB19D5893F9608308D675F2CE3344EDD3818523",
    "inherited_prefix_derivation_sha256": "4A587BDA2DCD98CDACEB11966B89C03A9B654A814DB8CBDEABA62E1F56832A9D",
    "controller_binding_sha256": "B076CC521D62213768E86BEDEB38F2B2E54611BCAFEFAE823BE7DD4E94CD172B",
    "protected_scorer_binding_sha256": "CD0509280C18C2FA2BCA186ECFD792B657D0AE6D64551BFFBDB379D23D9F01AD",
    "resource_accounting_binding_sha256": "D4C8D21F4D83DF67A8F8A9C58E1EE97C6A28CC9100E21E180D756FDC92FE72ED",
    "closure_binding_sha256": "1D8F15D0E04E34B7604244F3A2D9D4C904766133B722BCCC6C76777CCE007B4E",
    "source_module_sha256": "BF0CFEA28B02364616504AA2BDF8F8B67072EB97A8DD3B9C38B31F9F554DF7DC",
    "runtime_binary_sha256": "EFA521C4DC4189C89CC71B34CDB46079143857A4D49148E2D4411D3F7599FEE5",
    "runtime_version": "160 (89762c0)",
    "model_sha256": "31AEFA25B7E1EDBDE436E643E2B5E3F6E57820A4811D97B131130E48FF0772C2",
    "chat_template_sha256": "A4AEE8AFCF2E0711942CF848899BE66016F8D14A889FF9EDE07BCA099C28F715",
}

SOURCE_EVIDENCE = {
    "authority_id_sha256": "FE2D4E0D1A7333EEA6A33C342B3E7B9955583DA5591E26ABF06566CE01F04044",
    "authority_receipt_sha256": "C96D4C4B23A10ACB520FE632419BE5FF9A706EAF50CF439BDE5774F75F902191",
    "manifest_sha256": "776C42850D94DA539AF556536C9A3397640F52790EA162B150890347AA9BA613",
    "journal_sha256": "18E0E09E24A8B75C48EE67E0CEEBD518E4E5779592C6DECE048487DF3B370162",
    "journal_head_sha256": "642EAD610B04AEBE4428A93DD9750F6247999A0FB45549D97FC2168B6CEF1453",
    "live_result_sha256": "983527C02A3EE1B6F08F8633191E7150F7DE9B07D2884C233A056CF5E0EADE14",
    "closure_sha256": "485634A3E29261517BA698E077C42E4CA136DFE1C916004C286E6402711C0363",
    "archive_sha256": "9BC81ECDC0363B2032E15C94DB28DB7D1E434DCCA1EE86FCB140279DDB20D9E6",
}

EXPECTED_REUSE = {
    "warm-trajectory-archive-01": {"task_a_prompt_tokens": 901, "expected_lexical_prefix_tokens": 1004, "raw_common_prefix_tokens": 897, "admitted_cached_tokens": 769, "closure_fresh_tokens": 235, "task_a_completion_tokens": 108, "visible_content_tokens": 107, "contextual_visible_extension_tokens": 103, "raw_common_prefix_token_sha256": "D4B8082FA6FE93A710F6FDD7C01115F713B3E81DB983876F880582DA4BD8FF64"},
    "warm-trajectory-refuge-02": {"task_a_prompt_tokens": 921, "expected_lexical_prefix_tokens": 1052, "raw_common_prefix_tokens": 917, "admitted_cached_tokens": 789, "closure_fresh_tokens": 263, "task_a_completion_tokens": 136, "visible_content_tokens": 135, "contextual_visible_extension_tokens": 131, "raw_common_prefix_token_sha256": "53DE6D73A9A5442ADC7469A541732FD97D3FDE262FB1D0D833E5CA0D6A80C42C"},
    "warm-trajectory-observatory-03": {"task_a_prompt_tokens": 876, "expected_lexical_prefix_tokens": 1031, "raw_common_prefix_tokens": 872, "admitted_cached_tokens": 744, "closure_fresh_tokens": 287, "task_a_completion_tokens": 160, "visible_content_tokens": 159, "contextual_visible_extension_tokens": 155, "raw_common_prefix_token_sha256": "1EF58E73C9B66A2F84318FCB93381A765CD704236A6D9174B8A1E318FB9C797D"},
    "warm-trajectory-clinic-04": {"task_a_prompt_tokens": 996, "expected_lexical_prefix_tokens": 1098, "raw_common_prefix_tokens": 992, "admitted_cached_tokens": 864, "closure_fresh_tokens": 234, "task_a_completion_tokens": 107, "visible_content_tokens": 106, "contextual_visible_extension_tokens": 102, "raw_common_prefix_token_sha256": "71947818B290B707F4990408078F545AFFB6C0B7D8CFB58C48FE99C499069220"},
}

EXPECTED_AGGREGATE = {
    "task_a_answer_correct": 4,
    "task_a_textual_latent_state_correct": 3,
    "inherited_task_b_correct": 4,
    "direct_task_b_correct": 4,
}

EXPECTED_RESOURCES = {
    "shared_task_a": {"logical": 3694, "reused": 0, "fresh_prompt": 3694, "completion": 511, "total": 4205},
    "inherited_task_b": {"logical": 4860, "reused": 3166, "fresh_prompt": 1694, "completion": 48, "total": 1742},
    "closure": {"logical": 4185, "reused": 3166, "fresh_prompt": 1019, "completion": 0},
    "inherited_marginal_total": 2761,
    "direct_task_b_total": 4908,
    "inherited_tokens_x_direct_correct": 11044,
    "direct_tokens_x_inherited_correct": 19632,
}

DERIVATION_EXPECTED = {
    "warm-trajectory-archive-01": {"derivation_sha256": "B892100DE5DA7E91EE4E868292D7725086BD9D19162F62512C4F2B487A97CC0C", "dynamic_task_b_request_sha256": "E04F0C358FC2CCB5A0FCC77357D8172A00478716E7D88E054C8651262FF5EB89", "record_sha256": "458B31DAD386167B9F9685B01B5BAD5841766C2BF75A95B248B0B5449DDD30BE"},
    "warm-trajectory-refuge-02": {"derivation_sha256": "E92E5DFCEA05B6077CFB9CAF003326DEC6E03C51829413D55C574EED60B33FA1", "dynamic_task_b_request_sha256": "17A31D658E5B5E9D9BF5908BE9CF248C631A3046A9FD39CC09D8C06D94905019", "record_sha256": "D84920F752AB0475436363322101F91C223EEA278E36256826E082248C3E1A95"},
    "warm-trajectory-observatory-03": {"derivation_sha256": "C2495BA55999CD82A8449EAB7F79E771231D13010B1E16F42486BCC4E42DC7B1", "dynamic_task_b_request_sha256": "FF83AB4F4C81721846B3E69EF777885FCFBA36B3B592D5E34725BB21DDF9489C", "record_sha256": "5A23BFFB1D43D982F971338F1006BB08FE128DD215E1DFB398EA46D9E4E3DC69"},
    "warm-trajectory-clinic-04": {"derivation_sha256": "C69A4C43DEA241B2817A559222F2EAE355A86EFA422DB5EDEFFDD7BFF96B178F", "dynamic_task_b_request_sha256": "2AEAD3B300E88D7D2A730BE2DA51073E6B6C57E582956E709F5B2E6A62D48BFE", "record_sha256": "E0880D133A68925DE9DD80407751020C772E835541033CE87AA18A2167E431CF"},
}

SOURCE_CAUSAL_FILES = {
    "scripts/holostate_live.py": "77E06142E326E9264DEA07FADF058E875D9069E91FD0055788B771602BAAE18F",
    "tools/server/server-context.cpp": "BCDC5EE601CDFFB667FF8E47600DB24E58B02179C770A4FAB467052DECC78B58",
    "common/common.cpp": "4F5CA2EED8EE65C9DEF68DA25DB39DA2145034806C8D4DC5597947E0B062E20D",
    "src/llama-kv-cache-dsv4.cpp": "B6B3E072057AA1672623F16847780D99F1E305C94178E618573640673702B32A",
    "src/unicode.cpp": "AA75C6258A7E0D8DDC05476CBE68CE9BAAE99B8CF9FFAD8A8EE545D176CB97DA",
    "src/llama-vocab.cpp": "38CA4B939C20617A844EAC04680334108367086BA68E8D394BE2E7128CCC4130",
}

LOCKED_CLAIMS = {
    "exact_inherited_prefix_reuse": "LOCKED",
    "exact_restoration": "LOCKED",
    "complete_catalytic_lifecycle": "LOCKED",
    "general_catalytic_inference": "LOCKED",
    "restart_persistent_state": "LOCKED",
    "transfer_beyond_four_matched_pairs": "LOCKED",
    "compute_amplification_beyond_measured_accounting": "LOCKED",
    "reduced_wall_clock_latency": "LOCKED",
    "superiority": "LOCKED",
    "sota": "LOCKED",
    "automatic_promotion": False,
}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_json_text(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InheritedCarrierAdjudicationError(message)


def _no_duplicate_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        _require(key not in value, f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _json_bytes(data: bytes, label: str) -> dict[str, Any]:
    value = json.loads(data, object_pairs_hook=_no_duplicate_object)
    _require(isinstance(value, dict), f"{label} is not an object")
    return value


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _stream_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest().upper()


def _git(repository: Path, *args: str, text: bool = True) -> Any:
    return subprocess.run(["git", "-C", str(repository), *args], check=True, capture_output=True, text=text).stdout.strip() if text else subprocess.run(["git", "-C", str(repository), *args], check=True, capture_output=True).stdout


def validate_disclosure_boundary(value: Mapping[str, Any]) -> None:
    probe._assert_public_no_smuggle(value)
    lowered = canonical_json_bytes(value).lower()
    for forbidden in (
        b'"raw_authority_id"', b'"raw_response_capture"', b'"protected_evaluator_contents"',
        b'"state_required_concepts"', b'"task_a_answer"', b'"task_b_answer"',
        b'"expected_task_a_answer"', b'"expected_task_b_answer"', b'"private_salt_hex"',
        b'"task_to_cell"', b'"private_root"', b'"task_a_state_requirement_matches"',
        b'"raw_output"', b'"generated_token_ids"',
    ):
        _require(forbidden not in lowered, "protected, reversible, or raw material entered publication")


def validate_boundary_arithmetic(reuse: Mapping[str, Mapping[str, Any]] = EXPECTED_REUSE) -> None:
    for pair_id, item in reuse.items():
        _require(int(item["task_a_prompt_tokens"]) - int(item["raw_common_prefix_tokens"]) == 4, f"template boundary changed: {pair_id}")
        _require(int(item["raw_common_prefix_tokens"]) - int(item["admitted_cached_tokens"]) == 128, f"checkpoint rollback changed: {pair_id}")
        _require(int(item["task_a_prompt_tokens"]) - int(item["admitted_cached_tokens"]) == 132, f"mixed boundary changed: {pair_id}")
        _require(int(item["expected_lexical_prefix_tokens"]) - int(item["task_a_prompt_tokens"]) == int(item["task_a_completion_tokens"]) - 5, f"five-token identity changed: {pair_id}")
        _require(int(item["task_a_completion_tokens"]) - int(item["visible_content_tokens"]) == 1, f"terminal-token identity changed: {pair_id}")
        _require(int(item["visible_content_tokens"]) - int(item["contextual_visible_extension_tokens"]) == 4, f"contextual retokenization identity changed: {pair_id}")
    _require(sum(int(item["task_a_prompt_tokens"]) for item in reuse.values()) == 3694, "Task-A prompt aggregate changed")
    _require(sum(int(item["admitted_cached_tokens"]) for item in reuse.values()) == 3166, "admitted cache aggregate changed")
    _require(3694 - 3166 == 528 == 4 * 132, "aggregate rollback identity changed")
    _require(4185 - 3694 == 491 and 511 - 491 == 20 == 4 * 5 and 4185 - 3166 == 1019, "aggregate completion/closure identity changed")


_GGUF_SCALAR_FORMAT = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}


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
    return _read_exact(stream, length, "string").decode("utf-8")


def _read_gguf_value(stream: BinaryIO, value_type: int, *, keep: bool) -> Any:
    if value_type == 8:
        value = _read_gguf_string(stream)
        return value if keep else None
    if value_type == 9:
        element_type = _read_u32(stream)
        count = _read_u64(stream)
        _require(count <= 2_000_000, "GGUF metadata array is too large")
        values = [_read_gguf_value(stream, element_type, keep=keep) for _ in range(count)]
        return values if keep else None
    fmt = _GGUF_SCALAR_FORMAT.get(value_type)
    _require(fmt is not None, "GGUF metadata type is unsupported")
    value = struct.unpack("<" + fmt, _read_exact(stream, struct.calcsize(fmt), "scalar"))[0]
    return value if keep else None


class OfflineQwen35Tokenizer:
    """Read tokenizer metadata only; never load tensors or contact a server."""

    def __init__(self, model_path: Path, *, expected_size: int) -> None:
        _require(model_path.is_file() and not model_path.is_symlink(), "pinned model is absent or unsafe")
        _require(model_path.stat().st_size == expected_size, "pinned model size changed")
        wanted = {
            "general.architecture", "tokenizer.ggml.model", "tokenizer.ggml.pre",
            "tokenizer.ggml.tokens", "tokenizer.ggml.merges", "tokenizer.ggml.token_type",
            "tokenizer.ggml.eos_token_id", "tokenizer.ggml.padding_token_id",
            "tokenizer.ggml.add_bos_token", "tokenizer.chat_template",
        }
        metadata: dict[str, Any] = {}
        with model_path.open("rb") as stream:
            _require(_read_exact(stream, 4, "magic") == b"GGUF", "model is not GGUF")
            version, tensor_count, metadata_count = _read_u32(stream), _read_u64(stream), _read_u64(stream)
            _require(version == 3 and tensor_count == 733 and metadata_count <= 512, "GGUF header changed")
            for _ in range(metadata_count):
                key = _read_gguf_string(stream)
                value_type = _read_u32(stream)
                value = _read_gguf_value(stream, value_type, keep=key in wanted)
                if key in wanted:
                    metadata[key] = value
        _require(set(metadata) == wanted, "GGUF tokenizer metadata is incomplete")
        _require(metadata["general.architecture"] == "qwen35moe" and metadata["tokenizer.ggml.model"] == "gpt2" and metadata["tokenizer.ggml.pre"] == "qwen35", "tokenizer identity changed")
        _require(metadata["tokenizer.ggml.eos_token_id"] == 248046 and metadata["tokenizer.ggml.padding_token_id"] == 248044 and metadata["tokenizer.ggml.add_bos_token"] is False, "tokenizer control identity changed")
        tokens, merges, token_types = metadata["tokenizer.ggml.tokens"], metadata["tokenizer.ggml.merges"], metadata["tokenizer.ggml.token_type"]
        _require(isinstance(tokens, list) and isinstance(merges, list) and isinstance(token_types, list) and len(tokens) == len(token_types) == 248320, "tokenizer tables changed")
        try:
            from tokenizers import AddedToken, Regex, Tokenizer
            from tokenizers.models import BPE
            from tokenizers.pre_tokenizers import ByteLevel, Sequence as TokenizerSequence, Split
            from jinja2.sandbox import ImmutableSandboxedEnvironment
        except ImportError as exc:
            raise InheritedCarrierAdjudicationError("offline tokenizer dependencies are unavailable") from exc
        model = BPE(vocab={str(token): index for index, token in enumerate(tokens)}, merges=[tuple(str(item).split(" ", 1)) for item in merges])
        tokenizer = Tokenizer(model)
        qwen35_regex = r"(?:'[sS]|'[tT]|'[rR][eE]|'[vV][eE]|'[mM]|'[lL][lL]|'[dD])|[^\r\n\p{L}\p{N}]?[\p{L}\p{M}]+|\p{N}| ?[^\s\p{L}\p{M}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"
        tokenizer.pre_tokenizer = TokenizerSequence([Split(Regex(qwen35_regex), "isolated"), ByteLevel(add_prefix_space=False, use_regex=False)])
        tokenizer.add_special_tokens([AddedToken(str(token), special=True, normalized=False) for token, token_type in zip(tokens, token_types) if int(token_type) != 1])
        template_text = str(metadata["tokenizer.chat_template"])
        _require(_sha256(template_text.encode("utf-8")) == SOURCE_BINDINGS["chat_template_sha256"], "chat template identity changed")
        environment = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True, extensions=["jinja2.ext.loopcontrols"])
        self._template = environment.from_string(template_text)
        self._tokenizer = tokenizer
        self._tokens = [str(item) for item in tokens]
        self.eos_token_id = 248046
        self.metadata = {
            "architecture": "qwen35moe", "tokenizer_model": "gpt2", "tokenizer_pre": "qwen35",
            "vocabulary_size": len(tokens), "eos_token_id": 248046, "padding_token_id": 248044,
            "add_bos_token": False, "chat_template_sha256": SOURCE_BINDINGS["chat_template_sha256"],
            "tensor_bytes_opened": 0, "model_evaluation_performed": False,
        }

    def render(self, messages: Sequence[Mapping[str, Any]]) -> str:
        return str(self._template.render(messages=list(messages), tools=None, add_generation_prompt=True, bos_token="", eos_token=self._tokens[self.eos_token_id], enable_thinking=False))

    def ids(self, text: str) -> list[int]:
        return list(self._tokenizer.encode(text, add_special_tokens=False).ids)


def _verify_source_and_preregistration(repository: Path) -> dict[str, Any]:
    _git(repository, "cat-file", "-e", f"{SOURCE_COMMIT}^{{commit}}")
    source_bytes = _git(repository, "show", f"{SOURCE_COMMIT}:{SOURCE_MODULE_PATH}", text=False)
    _require(_sha256(source_bytes) == SOURCE_BINDINGS["source_module_sha256"], "source controller hash changed")
    _require(source_bytes == (repository / SOURCE_MODULE_PATH).read_bytes(), "source controller bytes differ from executed commit")
    preregistration = probe.validate_preregistration(repository)
    prereg_path = repository / probe.PREREGISTRATION_PATH
    _require(_stream_sha256(prereg_path) == SOURCE_BINDINGS["preregistration_file_sha256"] and preregistration.get("artifact_sha256") == SOURCE_BINDINGS["preregistration_artifact_sha256"], "preregistration identity changed")
    expected = {
        "inherited_prefix_derivation": SOURCE_BINDINGS["inherited_prefix_derivation_sha256"],
        "controller": SOURCE_BINDINGS["controller_binding_sha256"],
        "protected_scorer": SOURCE_BINDINGS["protected_scorer_binding_sha256"],
        "resource_accounting": SOURCE_BINDINGS["resource_accounting_binding_sha256"],
        "closure": SOURCE_BINDINGS["closure_binding_sha256"],
    }
    for name, digest in expected.items():
        _require(preregistration["bindings"][name]["sha256"] == digest, f"source callable binding changed: {name}")
    _require(_stream_sha256(repository / probe.PUBLIC_CORPUS_PATH) == SOURCE_BINDINGS["public_corpus_sha256"], "public corpus changed")
    return preregistration


def _verify_causal_source(repository: Path) -> dict[str, Any]:
    snippets = {
        "scripts/holostate_live.py": ("CTX_CHECKPOINTS = 8", "CHECKPOINT_MIN_STEP = 512", '"--ubatch-size", "128"'),
        "tools/server/server-context.cpp": ("get_common_prefix(input_tokens)", "slot.n_prompt_tokens_cache = n_past", "checkpoint_offsets[] = {4 + n_ubatch, 4}", "restored context checkpoint"),
        "common/common.cpp": ("common_context_can_seq_rm", "COMMON_CONTEXT_SEQ_RM_TYPE_FULL", "llama_memory_seq_rm(mem, 0, 1, -1)"),
        "src/llama-kv-cache-dsv4.cpp": ("bool llama_kv_cache_dsv4::seq_rm", "if (p0 > 0)", "arbitrary rollback is not reconstructible"),
        "src/unicode.cpp": ("qwen35",),
        "src/llama-vocab.cpp": ("qwen35",),
    }
    for relative, digest in SOURCE_CAUSAL_FILES.items():
        data = _git(repository, "show", f"{SOURCE_COMMIT}:{relative}", text=False)
        _require(_sha256(data) == digest, f"causal source hash changed: {relative}")
        text = data.decode("utf-8")
        _require(all(fragment in text for fragment in snippets[relative]), f"causal source law changed: {relative}")
    return {
        "source_commit": SOURCE_COMMIT,
        "source_file_sha256": SOURCE_CAUSAL_FILES,
        "runtime_configuration": {"batch_size": 512, "n_ubatch": 128, "context_checkpoints": 8, "checkpoint_min_step": 512},
        "common_prefix_is_computed_from_raw_tokens": True,
        "telemetry_reports_post_restore_n_past": True,
        "dsv4_arbitrary_partial_sequence_removal_supported": False,
        "safe_checkpoint_offsets": [132, 4],
    }


def _verify_journal(path: Path, experiment_key: bytes) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    previous = "0" * 64
    for ordinal, line in enumerate(path.read_bytes().splitlines(), start=1):
        event = _json_bytes(line, f"journal event {ordinal}")
        body = {key: value for key, value in event.items() if key != "event_sha256"}
        supplied = str(event.get("event_sha256", ""))
        expected = hmac.new(experiment_key, b"neo3000/holostate-inherited-task-a-carrier/journal-event/v1\0" + canonical_json_bytes(body), hashlib.sha256).hexdigest().upper()
        _require(event.get("ordinal") == ordinal and event.get("previous_event_sha256") == previous and hmac.compare_digest(supplied, expected), f"journal chain changed at event {ordinal}")
        events.append(event)
        previous = supplied
    _require(len(events) == 38 and previous == SOURCE_EVIDENCE["journal_head_sha256"], "journal terminal boundary changed")
    return events


def _verify_archive(repository: Path, paths: Mapping[str, Path]) -> dict[str, Any]:
    archive = repository / probe.ARCHIVE_ROOT / SOURCE_EVIDENCE["archive_sha256"]
    bundle = _json_bytes((archive / "bundle.json").read_bytes(), "archive bundle")
    body = {key: value for key, value in bundle.items() if key != "bundle_sha256"}
    _require(bundle.get("bundle_sha256") == SOURCE_EVIDENCE["archive_sha256"] and probe.json_sha256(body) == SOURCE_EVIDENCE["archive_sha256"], "archive address changed")
    members = bundle.get("members")
    _require(isinstance(members, list) and len(members) == 21, "archive evidence member count changed")
    live_by_source: dict[str, Path] = {key: value for key, value in paths.items() if key not in {"run_root", "run_lock"} and not key.startswith("partial-")}
    for member in members:
        _require(isinstance(member, Mapping), "archive member is malformed")
        archived = archive / str(member["path"])
        _require(archived.is_file() and not archived.is_symlink(), f"archive member missing: {member['path']}")
        data = archived.read_bytes()
        _require(len(data) == member.get("bytes") and _sha256(data) == member.get("sha256"), f"archive member changed: {member['path']}")
        source_name = str(member["source"])
        _require(source_name in live_by_source and live_by_source[source_name].read_bytes() == data, f"live/archive bytes differ: {member['path']}")
    physical = [path for path in archive.rglob("*") if path.is_file() and not path.is_symlink()]
    _require(len(physical) == 22, "archive physical file count changed")
    return {"archive_evidence_member_count": 21, "archive_physical_file_count": 22, "live_archive_equality_verified": True}


def _token_decomposition(repository: Path, manifest: Mapping[str, Any], captures: Mapping[str, Mapping[str, Any]], derivations: Mapping[str, Mapping[str, Any]], request_hashes: Mapping[str, str]) -> dict[str, Any]:
    model_identity = manifest["preflight"]["model_identity"]
    model_path = Path(str(model_identity["path"]))
    _require(_stream_sha256(model_path) == SOURCE_BINDINGS["model_sha256"], "model identity changed")
    tokenizer = OfflineQwen35Tokenizer(model_path, expected_size=int(model_identity["size_bytes"]))
    corpus = probe.load_public_corpus(repository)
    by_id = {str(item["pair_id"]): item for item in corpus["task_pairs"]}
    observed: dict[str, Any] = {}
    for pair_id in probe.PAIR_IDS:
        task_a_id = f"{pair_id}-task-a"
        inherited_id = f"{pair_id}-task-b-inherited"
        direct_id = f"{pair_id}-task-b-direct"
        capture = captures[task_a_id]
        task_a_content = str(capture["execution"]["content"])
        task_a_prompt = tokenizer.render(probe.task_a_messages(by_id[pair_id]))
        task_b_prompt = tokenizer.render(probe.task_b_messages(by_id[pair_id], task_a_content))
        task_a_ids = tokenizer.ids(task_a_prompt)
        task_b_ids = tokenizer.ids(task_b_prompt)
        visible_ids = tokenizer.ids(task_a_content)
        common = 0
        while common < min(len(task_a_ids), len(task_b_ids)) and task_a_ids[common] == task_b_ids[common]:
            common += 1
        derivation = derivations[pair_id]
        expected_prefix = int(derivation["expected_inherited_prefix_token_count"])
        _require(_sha256(task_b_prompt.encode("utf-8")) == derivation["full_task_b_prompt_sha256"], f"Task-B prompt reconstruction changed: {pair_id}")
        _require(len(task_b_ids) == derivation["full_token_count"] and _sha256(canonical_json_bytes(task_b_ids)) == derivation["full_token_sha256"], f"Task-B token reconstruction changed: {pair_id}")
        _require(_sha256(canonical_json_bytes(task_b_ids[:expected_prefix])) == derivation["inherited_terminal_prefix_token_sha256"], f"derived lexical prefix changed: {pair_id}")
        _require(_sha256(canonical_json_bytes(task_b_ids[expected_prefix:])) == derivation["suffix_token_sha256"], f"derived suffix changed: {pair_id}")
        direct_payload = probe.source._raw_completion_payload(task_b_prompt, seed=probe.derive_seed(pair_id, "task-b"), cache_prompt=False, n_predict=probe.TASK_B_MAX_TOKENS)
        _require(probe.json_sha256(direct_payload) == request_hashes[direct_id] and derivation["dynamic_task_b_request_sha256"] == request_hashes[inherited_id], f"dynamic Task-B request changed: {pair_id}")
        expected = EXPECTED_REUSE[pair_id]
        actual = {
            "task_a_prompt_tokens": len(task_a_ids),
            "task_a_prompt_token_sha256": _sha256(canonical_json_bytes(task_a_ids)),
            "task_a_completion_tokens": int(capture["execution"]["completion_tokens"]),
            "captured_generated_token_ids_available": bool(capture["execution"]["generated_token_ids"]),
            "visible_content_tokens": len(visible_ids),
            "visible_content_token_sha256": _sha256(canonical_json_bytes(visible_ids)),
            "terminal_eog_tokens_inferred_from_usage": int(capture["execution"]["completion_tokens"]) - len(visible_ids),
            "terminal_eog_token_id": tokenizer.eos_token_id,
            "expected_lexical_prefix_tokens": expected_prefix,
            "contextual_visible_extension_tokens": expected_prefix - len(task_a_ids),
            "raw_common_prefix_tokens": common,
            "raw_common_prefix_token_sha256": _sha256(canonical_json_bytes(task_a_ids[:common])),
            "first_divergent_task_a_token_id": task_a_ids[common],
            "first_divergent_task_b_token_id": task_b_ids[common],
            "first_divergence": "disabled-thinking scaffold versus captured assistant JSON",
            "admitted_cached_tokens": int(captures[inherited_id]["execution"]["cached_prompt_tokens"]),
            "raw_prefix_minus_admitted_tokens": common - int(captures[inherited_id]["execution"]["cached_prompt_tokens"]),
            "task_a_prompt_minus_admitted_tokens": len(task_a_ids) - int(captures[inherited_id]["execution"]["cached_prompt_tokens"]),
            "generated_token_disclosure": "Exact model-emitted token IDs were not present in authenticated chat SSE; reversible offline visible-content IDs are bound by count and SHA-256, not disclosed.",
        }
        for key in ("task_a_prompt_tokens", "task_a_completion_tokens", "visible_content_tokens", "expected_lexical_prefix_tokens", "contextual_visible_extension_tokens", "raw_common_prefix_tokens", "raw_common_prefix_token_sha256", "admitted_cached_tokens"):
            _require(actual[key] == expected[key], f"token boundary changed: {pair_id}:{key}")
        _require(actual["captured_generated_token_ids_available"] is False and actual["terminal_eog_tokens_inferred_from_usage"] == 1 and actual["raw_prefix_minus_admitted_tokens"] == 128 and actual["task_a_prompt_minus_admitted_tokens"] == 132, f"token/cached-state decomposition changed: {pair_id}")
        _require(actual["first_divergent_task_a_token_id"] == 248068 and actual["first_divergent_task_b_token_id"] == 90, f"first divergent tokens changed: {pair_id}")
        observed[pair_id] = actual
    validate_boundary_arithmetic(observed)
    return {"offline_tokenizer": tokenizer.metadata, "per_pair": observed}


def _resource_projection(resources: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "shared_task_a": {"logical": resources["shared_task_a_counted_once"]["logical_prompt_tokens"], "reused": resources["shared_task_a_counted_once"]["reused_prompt_tokens"], "fresh_prompt": resources["shared_task_a_counted_once"]["fresh_prompt_tokens"], "completion": resources["shared_task_a_counted_once"]["completion_tokens"], "total": resources["shared_task_a_counted_once"]["fresh_prompt_plus_completion_tokens"]},
        "inherited_task_b": {"logical": resources["inherited_task_b"]["logical_prompt_tokens"], "reused": resources["inherited_task_b"]["reused_prompt_tokens"], "fresh_prompt": resources["inherited_task_b"]["fresh_prompt_tokens"], "completion": resources["inherited_task_b"]["completion_tokens"], "total": resources["inherited_task_b"]["fresh_prompt_plus_completion_tokens"]},
        "closure": {"logical": resources["closure_readdress"]["logical_prompt_tokens"], "reused": resources["closure_readdress"]["reused_prompt_tokens"], "fresh_prompt": resources["closure_readdress"]["fresh_prompt_tokens"], "completion": resources["closure_readdress"]["completion_tokens"]},
        "inherited_marginal_total": resources["primary_inherited_marginal_including_closure"]["fresh_prompt_plus_completion_tokens"],
        "direct_task_b_total": resources["direct_task_b"]["fresh_prompt_plus_completion_tokens"],
        "inherited_tokens_x_direct_correct": resources["integer_cross_products"]["inherited_tokens_x_direct_correct"],
        "direct_tokens_x_inherited_correct": resources["integer_cross_products"]["direct_tokens_x_inherited_correct"],
    }


def _verified_replay(repository: Path) -> dict[str, Any]:
    paths = probe.state_paths(repository)
    expected_hashes = {"receipt": SOURCE_EVIDENCE["authority_receipt_sha256"], "manifest": SOURCE_EVIDENCE["manifest_sha256"], "journal": SOURCE_EVIDENCE["journal_sha256"], "result": SOURCE_EVIDENCE["live_result_sha256"], "closure": SOURCE_EVIDENCE["closure_sha256"]}
    for name, digest in expected_hashes.items():
        _require(_stream_sha256(paths[name]) == digest, f"source {name} changed")
    preregistration = _verify_source_and_preregistration(repository)
    causal_source = _verify_causal_source(repository)
    manifest = _json_bytes(paths["manifest"].read_bytes(), "manifest")
    live_result = _json_bytes(paths["result"].read_bytes(), "result")
    closure = _json_bytes(paths["closure"].read_bytes(), "closure")
    _require(manifest.get("authorized_commit") == SOURCE_COMMIT and manifest.get("authority_id_sha256") == SOURCE_EVIDENCE["authority_id_sha256"], "manifest authority identity changed")
    _require(manifest.get("preregistration_artifact_sha256") == SOURCE_BINDINGS["preregistration_artifact_sha256"] and manifest.get("preregistration_file_sha256") == SOURCE_BINDINGS["preregistration_file_sha256"], "manifest preregistration identity changed")
    _require(manifest.get("request_order") == list(probe.REQUEST_ORDER) and manifest.get("inference_order") == list(probe.INFERENCE_ORDER), "manifest execution order changed")
    _require(manifest.get("maximum_model_generations") == 12 and manifest.get("maximum_inference_requests") == 16 and manifest.get("retry_allowed") is False and manifest.get("raw_authority_id_persisted") is False, "manifest execution law changed")
    _require(manifest["preflight"]["binary_identity"]["sha256"] == SOURCE_BINDINGS["runtime_binary_sha256"] and manifest["preflight"]["binary_identity"]["runtime_version"] == SOURCE_BINDINGS["runtime_version"], "runtime binary identity changed")
    root = probe._load_private_root(repository)
    experiment_key = probe._experiment_key(root)
    receipt = probe.verify_authority_receipt(repository, root)
    _require(receipt["receipt_sha256"] == SOURCE_EVIDENCE["authority_receipt_sha256"] and receipt["authority"]["authority_id_sha256"] == SOURCE_EVIDENCE["authority_id_sha256"] and receipt["authority"]["authorized_commit"] == SOURCE_COMMIT, "authority receipt identity changed")
    _require(receipt.get("raw_authority_id_persisted") is False and b'"raw_authority_id"' not in paths["receipt"].read_bytes(), "raw authority persistence changed")
    events = _verify_journal(paths["journal"], experiment_key)
    started = [event for event in events if event.get("state") == "request-started"]
    captured_events = [event for event in events if event.get("state") == "request-captured"]
    closure_events = [event for event in events if event.get("state") == "closure-operation-captured"]
    _require([event["request_id"] for event in started] == list(probe.REQUEST_ORDER) and [event["request_id"] for event in captured_events] == list(probe.REQUEST_ORDER), "request journal order changed")
    _require(all(event["facts"].get("maximum_generations_for_request") == 1 for event in started), "one-generation request law changed")
    inference_order = [str(event["request_id"]) for event in events if event.get("state") in {"request-started", "closure-operation-captured"}]
    _require(inference_order == list(probe.INFERENCE_ORDER), "16-operation inference order changed")
    request_hashes = {str(event["request_id"]): str(event["facts"]["model_request_sha256"]) for event in started}
    captures: dict[str, Mapping[str, Any]] = {}
    outcomes: dict[str, dict[str, Any]] = {pair_id: {} for pair_id in probe.PAIR_IDS}
    resource_records: list[dict[str, Any]] = []
    raw_sse: list[dict[str, Any]] = []
    for ordinal, request_id in enumerate(probe.REQUEST_ORDER, start=1):
        capture = probe.verify_capture(paths[f"capture-{request_id}"], experiment_key=experiment_key, request_id=request_id, model_request_sha256=request_hashes[request_id], generation_ordinal=ordinal)
        _require(capture["capture_sha256"] == live_result["capture_sha256"][request_id] == captured_events[ordinal - 1]["facts"]["capture_sha256"], f"capture binding changed: {request_id}")
        raw_sse.append(warm_adjudication._replay_raw_sse(capture, request_id))
        captures[request_id] = capture
        resource_records.append(probe.resource_record(capture, request_id))
        pair_id = request_id.rsplit("-task-", 1)[0]
        content = probe.structured_content_from_capture(capture)
        if request_id.endswith("task-a"):
            outcomes[pair_id]["task_a"] = probe.parse_task_a_output(content)
        elif request_id.endswith("task-b-inherited"):
            outcomes[pair_id]["inherited_answer"] = probe.parse_task_b_output(content)
        else:
            outcomes[pair_id]["direct_answer"] = probe.parse_task_b_output(content)
    derivations: dict[str, Mapping[str, Any]] = {}
    for pair_id in probe.PAIR_IDS:
        derivation = probe.verify_derivation_record(paths[f"derivation-{pair_id}"], experiment_key)
        expected = DERIVATION_EXPECTED[pair_id]
        _require({key: derivation[key] for key in expected} == expected and live_result["derivation_records"][pair_id] == {**expected, "expected_inherited_prefix_token_count": EXPECTED_REUSE[pair_id]["expected_lexical_prefix_tokens"]}, f"derivation changed: {pair_id}")
        derivations[pair_id] = derivation
    closure_records = [dict(event["facts"]) for event in closure_events]
    _require(closure_records == live_result["closure_records"] and [item["operation_id"] for item in closure_records] == list(probe.CLOSURE_OPERATION_ORDER), "closure records changed")
    archive = _verify_archive(repository, paths)
    token_decomposition = _token_decomposition(repository, manifest, captures, derivations, request_hashes)
    corpus = probe.load_public_corpus(repository)
    scoring = probe.score_protected(repository, corpus, outcomes, completed_capture_ids=probe.REQUEST_ORDER, completed_closure_ids=probe.CLOSURE_OPERATION_ORDER, cleanup_passed=True, postflight_passed=True)
    aggregate = {key: int(scoring[source_key]) for key, source_key in (("task_a_answer_correct", "task_a_correct"), ("task_a_textual_latent_state_correct", "task_a_textual_latent_state_correct"), ("inherited_task_b_correct", "inherited_task_b_correct"), ("direct_task_b_correct", "direct_task_b_correct"))}
    _require(aggregate == EXPECTED_AGGREGATE, "protected score replay changed")
    _require(all(live_result["scoring"].get(key) == scoring.get(key) for key in ("task_a_correct", "task_a_textual_latent_state_correct", "inherited_task_b_correct", "direct_task_b_correct")), "live/protected scoring differs")
    resources = probe.account_resources(resource_records, closure_records, scoring)
    _require(_resource_projection(resources) == EXPECTED_RESOURCES and resources.get("inherited_fresh_tokens_per_correct_strictly_lower") is True, "resource replay changed")
    _require(live_result.get("terminal_classification") == LIVE_CLASSIFICATION and live_result.get("status") == "complete", "immutable live terminal classification changed")
    _require(live_result.get("completed_model_generations") == 12 and live_result.get("completed_inference_requests") == 16 and live_result.get("retry_count") == 0, "source completion counts changed")
    _require(live_result.get("cleanup", {}).get("passed") is True and live_result.get("postflight", {}).get("passed") is True, "cleanup/postflight changed")
    _require(closure.get("status") == "complete" and closure.get("result_sha256") == SOURCE_EVIDENCE["live_result_sha256"] and closure.get("journal_sha256") == SOURCE_EVIDENCE["journal_sha256"] and closure.get("journal_head_sha256") == SOURCE_EVIDENCE["journal_head_sha256"] and closure.get("retry_allowed") is False, "terminal closure changed")
    return {
        "preregistration": preregistration,
        "capture_sha256": live_result["capture_sha256"],
        "derivation_records": {pair_id: {key: derivations[pair_id][key] for key in ("derivation_sha256", "dynamic_task_b_request_sha256", "record_sha256")} for pair_id in probe.PAIR_IDS},
        "request_sha256": request_hashes,
        "seeds": preregistration["execution"]["seeds"],
        "aggregate": aggregate,
        "resources": resources,
        "reuse": live_result["inherited_prefix_reports"],
        "closure_records": closure_records,
        "token_decomposition": token_decomposition,
        "causal_source": causal_source,
        "archive": archive,
        "verification_counts": {"journal_events": len(events), "captures": len(captures), "raw_sse_streams": len(raw_sse), "derivations": len(derivations), "closure_records": len(closure_records), "inference_operations": len(inference_order)},
    }


def render_adjudication(repository: Path) -> dict[str, Any]:
    replay = _verified_replay(repository)
    resource = replay["resources"]
    artifact = {
        "schema_version": 1,
        "adjudication_id": ADJUDICATION_ID,
        "design_id": probe.DESIGN_ID,
        "status": "adjudicated",
        "source_execution": {"protected_commit": SOURCE_COMMIT, "live_terminal_classification": LIVE_CLASSIFICATION, "completed_model_generations": 12, "completed_inference_requests": 16, "scientific_retries": 0, **SOURCE_EVIDENCE, "capture_sha256": replay["capture_sha256"]},
        "bindings": {**SOURCE_BINDINGS, "request_sha256": replay["request_sha256"], "derivation_records": replay["derivation_records"], "seeds": replay["seeds"], "causal_source": replay["causal_source"]},
        "zero_contact_reconstruction": {"source_commit_verified": True, "preregistration_exact": True, "source_artifact_and_callable_bindings_verified": 5, "authority_receipt_hmac_verified": True, "raw_authority_id_persisted": False, "manifest_verified": True, "authenticated_journal_events_verified": 38, "authenticated_captures_verified": 12, "raw_sse_reconstructions_verified": 12, "authenticated_derivations_verified": 4, "closure_records_verified": 4, "inference_operations_verified": 16, "protected_score_replay_verified": True, "resource_replay_verified": True, "cleanup_verified": True, "postflight_verified": True, **replay["archive"], "model_requests_issued": 0, "sidecar_launches": 0, "model_generations": 0, "scientific_retries": 0, "authorities_created_or_consumed": 0},
        "scientific_observations": {
            "aggregate_scores": {"task_a_answers": {"correct": 4, "total": 4}, "task_a_textual_latent_state": {"correct": 3, "total": 4}, "inherited_task_b": {"correct": 4, "total": 4}, "direct_task_b": {"correct": 4, "total": 4}},
            "partial_reuse": {"classification": PARTIAL_REUSE_CLASSIFICATION, "exact_reuse_classification": EXACT_REUSE_CLASSIFICATION, "pairs": replay["reuse"], "partial_reuse_pairs": 4, "exact_reuse_pairs": 0},
            "closure": {"classification": CLOSURE_CLASSIFICATION, "exact_restoration_pairs": 0, "logical_tokens": 4185, "reused_tokens": 3166, "fresh_tokens": 1019, "records": replay["closure_records"]},
            "resource_advantage": {"classification": EFFICIENCY_CLASSIFICATION, "shared_task_a": resource["shared_task_a_counted_once"], "inherited_task_b": resource["inherited_task_b"], "closure": resource["closure_readdress"], "inherited_marginal": resource["primary_inherited_marginal_including_closure"], "direct_task_b": resource["direct_task_b"], "exact_integer_cross_products": resource["integer_cross_products"], "fresh_token_reduction": {"numerator": 2147, "denominator": 4908, "percent": "43.74490627546862"}, "strictly_lower_with_equal_accuracy": True},
        },
        "causal_prefix_decomposition": {"classification": CAUSAL_CLASSIFICATION, "per_pair": replay["token_decomposition"]["per_pair"], "offline_tokenizer": replay["token_decomposition"]["offline_tokenizer"], "verified_equalities": ["Task-A prompt - raw token common prefix = 4 for each pair", "raw token common prefix - admitted executable cache = 128 = n_ubatch for each pair", "Task-A prompt - admitted executable cache = 132 = n_ubatch + 4 for each pair", "expected lexical prefix - Task-A prompt = Task-A completion - 5 for each pair", "3694 - 3166 = 528 = 4 x 132", "4185 - 3694 = 491", "511 - 491 = 20 = 4 x 5", "4185 - 3166 = 1019"], "five_token_role": {"per_pair": 5, "terminal_eog_token": 1, "contextual_chat_template_retokenization_tokens": 4, "direct_model_generated_ids_captured": False, "claim_ceiling": "Visible-content IDs are reconstructed offline and bound by SHA-256; the exact model-emitted sequence was not authenticated by chat SSE."}, "distinctions": {"lexical_prefix_identity": "The static derivation reaches the end of captured Task-A JSON inside a newly rendered Task-B prompt.", "generated_output_identity": "Visible Task-A content is byte-exact; direct emitted token arrays were absent from chat SSE.", "safe_executable_checkpoint_identity": "DSV4 cannot arbitrarily remove a partial sequence, so reuse restores a prior checkpoint.", "telemetry_identity": "cached_prompt_tokens reports post-restore n_past, not the pre-restore raw common prefix.", "closure_cost": "The exact lexical closure requires 1019 fresh prompt tokens after the same safe rollback."}},
        "bounded_interpretation": BOUNDED_INTERPRETATION,
        "bounded_interpretation_facts": {"carrier_reuse_real": True, "efficiency_advantage_measured_not_projected": True, "exact_lexical_prefix_inherited": False, "exact_restoration_achieved": False, "textual_token_prefix_identity_differs_from_executable_state_identity": True, "general_catalytic_inference_established": False},
        "locked_claims": LOCKED_CLAIMS,
        "next_boundary": NEXT_BOUNDARY,
    }
    validate_boundary_arithmetic()
    validate_disclosure_boundary(artifact)
    return artifact


def render_record(repository: Path, artifact: Mapping[str, Any] | None = None) -> dict[str, Any]:
    adjudication = dict(artifact or render_adjudication(repository))
    artifact_sha256 = _sha256(canonical_json_bytes(adjudication) + b"\n")
    record = {
        "id": RECORD_ID,
        "checkpoint": "2-Catalytic-Kernel-0-HoloState-inherited-carrier-forensic-adjudication",
        "hypothesis": "Process-local inherited Task-A state can provide reusable executable prefix state with equal Task-B utility and lower measured fresh-token cost even when exact lexical-prefix reuse is not achieved.",
        "intervention": "Authenticate, replay, causally decompose, and separately adjudicate immutable inherited-carrier evidence with zero model or sidecar contact.",
        "baseline_commit": SOURCE_COMMIT,
        "candidate_commit": None,
        "model_hash": SOURCE_BINDINGS["model_sha256"],
        "configuration": {"design_id": probe.DESIGN_ID, "source_execution_commit": SOURCE_COMMIT, "request_count": 12, "inference_operation_count": 16, "maximum_generations_per_request": 1, "bindings": SOURCE_BINDINGS},
        "metrics_before": {"source_live_terminal_classification": LIVE_CLASSIFICATION, "source_live_result_immutable": True, "published_component_adjudication": False},
        "metrics_after": {"status": "adjudicated", "source_live_terminal_classification": LIVE_CLASSIFICATION, "partial_reuse_classification": PARTIAL_REUSE_CLASSIFICATION, "exact_reuse_classification": EXACT_REUSE_CLASSIFICATION, "fresh_token_efficiency_classification": EFFICIENCY_CLASSIFICATION, "causal_attribution_classification": CAUSAL_CLASSIFICATION, "closure_classification": CLOSURE_CLASSIFICATION, "bounded_interpretation": BOUNDED_INTERPRETATION, "aggregate_scores": adjudication["scientific_observations"]["aggregate_scores"], "per_pair_partial_reuse": adjudication["scientific_observations"]["partial_reuse"]["pairs"], "resource_advantage": adjudication["scientific_observations"]["resource_advantage"], "token_boundary_decomposition": adjudication["causal_prefix_decomposition"], "authority_receipt_sha256": SOURCE_EVIDENCE["authority_receipt_sha256"], "manifest_sha256": SOURCE_EVIDENCE["manifest_sha256"], "journal_sha256": SOURCE_EVIDENCE["journal_sha256"], "journal_head_sha256": SOURCE_EVIDENCE["journal_head_sha256"], "live_result_sha256": SOURCE_EVIDENCE["live_result_sha256"], "closure_sha256": SOURCE_EVIDENCE["closure_sha256"], "evidence_archive_sha256": SOURCE_EVIDENCE["archive_sha256"], "capture_sha256": adjudication["source_execution"]["capture_sha256"], "adjudication_artifact_sha256": artifact_sha256},
        "quality_gates": {"source_and_preregistration_exact": True, "authority_receipt_hmac_verified": True, "authenticated_journal_events": 38, "authenticated_captures": 12, "raw_sse_reconstructions": 12, "authenticated_derivations": 4, "closure_records": 4, "inference_operations": 16, "archive_evidence_members": 21, "archive_physical_files": 22, "live_archive_equality_verified": True, "protected_evaluator_delayed_access_verified": True, "cleanup_and_postflight_verified": True, "causal_source_bound": True, "no_disclosure": True, "general_catalytic_inference_locked": True, "automatic_promotion": False, "zero_contact_adjudication": True},
        "verdict": "accept-bounded-partial-reuse-advantage-evidence",
        "next_boundary": NEXT_BOUNDARY,
    }
    validate_disclosure_boundary(record)
    return record


def validate_ledger_append_boundary(repository: Path) -> None:
    lines = (repository / RESULTS_PATH).read_text(encoding="utf-8").splitlines()
    _require(len(lines) == EXPECTED_LEDGER_LINE - 1, "ledger no longer ends at line 61")
    _require(_json_bytes(lines[-1].encode("utf-8"), "ledger predecessor").get("id") == PREDECESSOR_RECORD_ID, "ledger no longer ends at neo-exp-0048")
    _require(not any(_json_bytes(line.encode("utf-8"), "ledger record").get("id") == RECORD_ID for line in lines), "neo-exp-0049 already exists")


def validate_publication(repository: Path) -> dict[str, Any]:
    artifact = render_adjudication(repository)
    artifact_bytes = canonical_json_bytes(artifact) + b"\n"
    path = repository / ARTIFACT_PATH
    _require(path.is_file() and not path.is_symlink() and path.read_bytes() == artifact_bytes, "adjudication artifact differs from exact reconstruction")
    record = render_record(repository, artifact)
    expected_line = canonical_json_text(record)
    lines = (repository / RESULTS_PATH).read_text(encoding="utf-8").splitlines()
    matches = [(number, line) for number, line in enumerate(lines, 1) if _json_bytes(line.encode("utf-8"), "ledger record").get("id") == RECORD_ID]
    _require(len(matches) == 1 and matches[0][0] == EXPECTED_LEDGER_LINE and matches[0][1] == expected_line, "neo-exp-0049 publication differs from exact render")
    return {"status": "pass", "adjudication_id": ADJUDICATION_ID, "adjudication_artifact_sha256": _sha256(artifact_bytes), "record_id": RECORD_ID, "ledger_line": EXPECTED_LEDGER_LINE, "record_sha256": _sha256(expected_line.encode("utf-8")), "source_live_terminal_classification": LIVE_CLASSIFICATION, "partial_reuse_classification": PARTIAL_REUSE_CLASSIFICATION, "fresh_token_efficiency_classification": EFFICIENCY_CLASSIFICATION, "causal_classification": CAUSAL_CLASSIFICATION, "archive_evidence_member_count": 21, "archive_physical_file_count": 22, "model_requests_issued": 0, "sidecar_launches": 0, "model_generations": 0, "scientific_retries": 0, "authorities_created_or_consumed": 0}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("render-package", "render-artifact", "render-record", "validate"))
    parser.add_argument("--repository", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository = Path(args.repository).resolve(strict=False)
    try:
        if args.action == "render-package":
            artifact = render_adjudication(repository)
            result = {"artifact": artifact, "record": render_record(repository, artifact)}
        elif args.action == "render-artifact":
            result = render_adjudication(repository)
        elif args.action == "render-record":
            result = render_record(repository)
        else:
            result = validate_publication(repository)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, subprocess.CalledProcessError, InheritedCarrierAdjudicationError, probe.InheritedCarrierEvaluationError) as exc:
        print(canonical_json_text({"status": "fail", "error": str(exc)}))
        return 1
    print(canonical_json_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
