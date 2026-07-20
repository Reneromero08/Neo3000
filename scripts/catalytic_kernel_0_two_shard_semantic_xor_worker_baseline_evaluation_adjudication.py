#!/usr/bin/env python3
"""Statically adjudicate immutable semantic-XOR Attempt-3 evidence."""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator, Mapping, Sequence

import catalytic_kernel_0_two_shard_semantic_xor_worker_baseline_evaluation as probe
import catalytic_kernel_0_two_shard_semantic_xor_worker_baseline_evaluation_scientific as scientific


class SemanticXorAdjudicationError(ValueError):
    """The frozen Attempt-3 evidence cannot support the bounded publication."""


SOURCE_COMMIT = "957aa19339e539145572671f3f8c0be9c070b535"
REPAIR_COMMIT = "339d90cabb9b00f8714c5412ba269b24dae47940"
SOURCE_MODULE_PATH = "scripts/catalytic_kernel_0_two_shard_semantic_xor_worker_baseline_evaluation.py"
SOURCE_PREREGISTRATION_PATH = Path(
    "lab/ck0_two_shard_semantic_xor_worker_baseline_evaluation_v1_attempt_3.json"
)
ARTIFACT_PATH = Path(
    "lab/ck0_two_shard_semantic_xor_worker_baseline_evaluation_v1_attempt_3_adjudication_1.json"
)
RESULTS_PATH = Path("lab/results.jsonl")
ADJUDICATION_ID = "ck0-two-shard-semantic-xor-worker-baseline-attempt-3-adjudication-1"
RECORD_ID = "neo-exp-0047"
EXPECTED_LEDGER_LINE = 60

CAPABILITY_CLASSIFICATION = (
    "NON_CONTROLLER_RECONSTRUCTIBLE_SEMANTIC_XOR_WORKER_SYNTHESIS_SUPPORTED"
)
ADVANTAGE_CLASSIFICATION = "SEMANTIC_XOR_WORKER_SYNTHESIS_ADVANTAGE_NOT_SUPPORTED"
BOUNDED_INTERPRETATION = (
    "TWO_ISOLATED_MODEL_GENERATED_SEMANTIC_JUDGMENT_STREAMS_WERE_COMBINED_THROUGH_"
    "XOR_INTO_CORRECT_FINAL_LABELS_ON_ALL_FOUR_FROZEN_TASKS_WHILE_THE_SAME_EVIDENCE_"
    "DIRECT_BASELINE_SOLVED_THREE_OF_FOUR"
)
NEXT_BOUNDARY = "STATICALLY_EVALUATE_WORKER_PLUS_CONTROLLER_XOR_ROUTE_FROM_ATTEMPT_3_CAPTURES"

SOURCE_BINDINGS = {
    "preregistration_artifact_sha256": "650B72BD09ED153505B867AD33FAF6F1D7EE96FA2C76F2A84189975440CB8A66",
    "preregistration_file_sha256": "E5D690D89D0E2F7CB00F3031524E6DD481D4D670EA5DB3FCC7EC8C8C05088ABC",
    "frozen_scientific_binding_sha256": "39182B20C74A0B804774CA9E4A0D54FA52E1970A7564DE82A28C98C38925B8A3",
    "controller_binding_sha256": "0604A058E4715EF3A9E23E5E14A61F7E5CD9CACB654AFF98E4CE39256F855351",
    "synthesis_derivation_law_sha256": "80A68493FE5F2F10501F091F1E0DDCC04165A039E52B298DD862013D4CB0F08D",
    "protected_scorer_binding_sha256": "8BF9146886167545CFA7A3C34980614407A5C5BF02D7229F47209FB7F22B0F04",
    "resource_accounting_binding_sha256": "978F5586138AB759D56573B93B7F81313C530D608EE268CEFB23920F56179545",
    "protected_evaluator_sha256": "437112DC9A06E4CB3CF1824A738BB13887212B23A38E2AF12A94374A9259D163",
    "public_corpus_sha256": "DE4D822424EFE5B6B5FAB1A65F5D2A1E5A87FC60D64A2DD84812BC300A246C41",
}
REPAIR_BINDINGS = {
    "preregistration_artifact_sha256": "3C0D97B767C4B426FB6D919A4DC2A867EC977809B38F1856175E5ED884979D01",
    "preregistration_file_sha256": "7DEA4056B706ADFFD0C020E7887D21B0C03B85F53769F7E8E5ABAA833979195C",
    "controller_binding_sha256": "25885ECA37DD7E70AC1D216EBE411E85E4514763B0FAB983F7D564148B20CE55",
    "protected_scorer_binding_sha256": "FC5CF38976F40A521684FCC2F9A25A3C85C29ADA5BEBF8A3133E586C6B924B05",
    "frozen_scientific_binding_sha256": SOURCE_BINDINGS["frozen_scientific_binding_sha256"],
    "resource_accounting_binding_sha256": SOURCE_BINDINGS["resource_accounting_binding_sha256"],
}
SOURCE_EVIDENCE = {
    "authority_id_sha256": "9284373AD2A5E0CFB83DE37570B3C9511FA8D11179E417FB64F515200174E985",
    "authority_receipt_sha256": "53F76D646C30803346AAFC8E4934C645AA9149997EBF2052CD890BDCDABB97FC",
    "manifest_sha256": "6408820E958B6877DAD19B4DABBE18E9551952BFB000AFD3173F9E6B6257BA09",
    "live_result_sha256": "AA1A9F22A45C8B6F5CAFFE5FDFE409458C25E80B9BAFB4A7B2E1D8AE696087CF",
    "closure_sha256": "9123B3E882BABFE1B887ADFA0AA464ED446F64BBF3008E63BC736B2A7B619CD1",
    "journal_sha256": "203038539C79859389C7B83F0513807DDBEECD7D8EB4E043278FA727F34C76DA",
    "journal_head_sha256": "469E42A183D11F1F2A5BA85F97115D82814797646E6A71144D696514024D77D2",
    "live_scorer_failure_sha256": "B8CC47CFA8CB7D8B5914A6703502887C4DA2F251F8E035675BB87ABE1C33A444",
    "archive_sha256": "9FE208E22A0810E84B24AF495D9694C832A2CF1FB3BB3F9EB3545BE0E7371173",
}
ATTEMPT_HISTORIES = [
    {
        "attempt": 1,
        "source_commit": "5605c5d28a6fdbc7e1e7ee855c0515f88ad50997",
        "terminal_classification": "INCONCLUSIVE",
        "archive_sha256": "4447C61747E89084EE9882B238575AF1BF8E21589CDAB78532BD381A1C5741D8",
        "reason": "eight-token ceiling exhausted before valid JSON closure",
        "consumed_history": True,
    },
    {
        "attempt": 2,
        "source_commit": "21c0449524b82db96d5e9826cbe743f0a7c7c9d9",
        "terminal_classification": "INCONCLUSIVE",
        "archive_sha256": "9E5F9D89B5FAAA71B550B465CF5EDAF99399FEEF3D56786A733527C9CEF74628",
        "reason": "complete JSON reached sixteen tokens but transport ended length before stop",
        "consumed_history": True,
    },
    {
        "attempt": 3,
        "source_commit": SOURCE_COMMIT,
        "terminal_classification": "INCONCLUSIVE",
        "archive_sha256": SOURCE_EVIDENCE["archive_sha256"],
        "reason": "all requests completed; protected scorer expected the wrong aggregate witness shape",
        "consumed_history": True,
        "scientific_source_for_adjudication": True,
    },
    {
        "attempt": 4,
        "source_commit": REPAIR_COMMIT,
        "live_execution": False,
        "static_repair_only": True,
        "authority_created": False,
    },
]

FIXED_REQUEST_SHA256 = {
    "sx-016fb6886053-baseline": "5FC1AA351BD7D561ADB5421B57F739546EFB8908DC7EA68FFD0F1863A79AC9B8",
    "sx-016fb6886053-worker-A": "9582B0E6074AB2F06FE73D1EB0D30B075379042FE50FA0D958748271B338769A",
    "sx-016fb6886053-worker-B": "C77F2E6EA3D6BCEEB8EFD70DDC3E8E64AF91CA06927213F807F93A448C0FEB58",
    "sx-24d6ac75de2d-worker-A": "9FC0E0B60CFB0A91911BD583FF575FDB9FEBFEAEC3B9E1DDF420FC712C5C808B",
    "sx-24d6ac75de2d-worker-B": "6CAC6BEB462CFACD01AC0AC2DD7236FDD20DBF65E599D2103BB2C5E349C550DF",
    "sx-24d6ac75de2d-baseline": "AC24615201BC5A1576B60AD2522B56BE6237C408CD4B614771F821131DAAD6F4",
    "sx-362389035ea1-baseline": "E15E8BBE0CD6CEFC727DA5A0C3BBBFAD312610F1FF23ADC4ACE2AD25A893D6FB",
    "sx-362389035ea1-worker-A": "7314DACC509512C10AD1357565F70B03E377E08D11C1B4ECF7FAB5B001FBF557",
    "sx-362389035ea1-worker-B": "7E1127E32342347E9E9D6212D1EE5264D7C67C8F0F26A46DC9823A4254A41E37",
    "sx-528f806d07bc-worker-A": "4DF7339E9ECB88831D509C3FD555E235CF23E8C2364B731501EABC191107E1AB",
    "sx-528f806d07bc-worker-B": "2558D230F7AF7403894776E84EA07E494292E81AF846ED2EB8EBDC74C260EC8F",
    "sx-528f806d07bc-baseline": "44C0FB4959EF5EC710B776665F7A078FFC0F0EEC03C30C0DF70088FFA2409083",
}
DERIVED_REQUEST_SHA256 = {
    "sx-016fb6886053-synthesis": "232F3AE7D68CEB270D90B187132F0D48688424BC3FD94BC8790FFDBB25716078",
    "sx-24d6ac75de2d-synthesis": "B83BB53EA48EBA56FBE2344CA6DC4E858344D3C33875E351FADD1B282889CFD2",
    "sx-362389035ea1-synthesis": "9BC793721DDE1C11415AC3CA72E1A630B2F7B480A03F589D93A4773EDE389736",
    "sx-528f806d07bc-synthesis": "C9E4FB76F3295EB7C3C56E33D421B28D63518C19294EA169DE96DC6CAFE1D067",
}
CAPTURE_SHA256 = {
    "sx-016fb6886053-baseline": "A9AE88197697AAC5AD6227CCBE102594D5BE7D127B1638BA88FBAC7F4D4B073B",
    "sx-016fb6886053-worker-A": "E7422B5B95273C279019845489C6460ED3CFD6F5A62B050289A39D9580B24EC2",
    "sx-016fb6886053-worker-B": "D3A7C447AA0957E979B8E8DD1B195110704029813E657380598D8B169208068C",
    "sx-016fb6886053-synthesis": "815E2BFC2F3F792F382267D9F3F528A5DE3B211D0594FD4FD379E4C57D2F669A",
    "sx-24d6ac75de2d-worker-A": "BA626E046ECDEB7946A69A951ECB3425262F6928057E53AA5D26C88DC3C14DB1",
    "sx-24d6ac75de2d-worker-B": "171BF8DF0147A945F5A09377D33000231AD6F584737EDD8B3D3E29B31F419AD6",
    "sx-24d6ac75de2d-synthesis": "CFF04113EF5921CE18EF3DCA54C4B54B9716564611220C4F45E8A2DB1D6A9BA2",
    "sx-24d6ac75de2d-baseline": "C92C55F9CFE09E1E7A6CBC13E600C6FCE1A0E9EDB075D475BD63A5CA64A4BE31",
    "sx-362389035ea1-baseline": "483C8326E31B8350090A38551F6CDB3206857AADD9D2113A95CF7E62D6724C4F",
    "sx-362389035ea1-worker-A": "7C52AF33B938EBDA0F2266CD9F8713E33938817A6A409B67D217A020AFB65717",
    "sx-362389035ea1-worker-B": "5C1A20C7A18482E7F9BABCC9C44B72087D77BC9153DDB58F0FF88FDF9D7039C0",
    "sx-362389035ea1-synthesis": "FE5E757E758E4499301139AC4E6A4CB0A7DD0CE4C19A455D3D26E997C143A017",
    "sx-528f806d07bc-worker-A": "3195D732857D438A308553A6C36F5120595887948B519187AFE61C403EED4BF0",
    "sx-528f806d07bc-worker-B": "B642F6CEA55DE75076AADC0ECD8642AD28DAA3F5CD96A79444B6DCE87004E109",
    "sx-528f806d07bc-synthesis": "CB68D8F03C091E96DDAA7C69C8550F39BB5FBE21EC7D697F0F1431F619DD2E33",
    "sx-528f806d07bc-baseline": "0D3B475EC72A1FE95CF10DE846459FE91FEF44ABC52D4E45A667C8D7E45C3F5A",
}

EXPECTED_AGGREGATE = {
    "worker_a_correct": 4,
    "worker_b_correct": 4,
    "semantic_worker_bits_correct": 8,
    "xor_relation_fidelity": 4,
    "worker_route_final_correct": 4,
    "baseline_final_correct": 3,
}
EXPECTED_ROUTE_RESOURCES = {
    "worker_route": {
        "route": "worker-synthesis",
        "request_count": 12,
        "generation_count": 12,
        "logical_prompt_tokens": 2861,
        "fresh_prompt_tokens": 2861,
        "cached_prompt_tokens": 0,
        "completion_tokens": 144,
        "fresh_prompt_plus_completion_tokens": 3005,
        "correct_final_labels": 4,
        "tokens_per_correct_final_label": {
            "kind": "exact-ratio",
            "numerator": 3005,
            "denominator": 4,
        },
        "maximum_per_request_context": 335,
    },
    "direct_route": {
        "route": "direct-baseline",
        "request_count": 4,
        "generation_count": 4,
        "logical_prompt_tokens": 1373,
        "fresh_prompt_tokens": 1373,
        "cached_prompt_tokens": 0,
        "completion_tokens": 57,
        "fresh_prompt_plus_completion_tokens": 1430,
        "correct_final_labels": 3,
        "tokens_per_correct_final_label": {
            "kind": "exact-ratio",
            "numerator": 1430,
            "denominator": 3,
        },
        "maximum_per_request_context": 380,
    },
    "exact_integer_cross_products": {
        "worker_tokens_x_baseline_correct": 9015,
        "baseline_tokens_x_worker_correct": 5720,
    },
}
LOCKED_CLAIMS = {
    "general_worker_synthesis": "locked",
    "general_semantic_reasoning": "locked",
    "transfer_beyond_four_frozen_tasks": "locked",
    "reduced_fresh_computation": "locked",
    "compute_amplification": "locked",
    "reduced_wall_clock_latency": "locked",
    "prompt_cache_advantage": "locked",
    "persistent_blackboard_value": "locked",
    "complete_catalytic_lifecycle": "locked",
    "general_catalytic_inference": "locked",
    "superiority": "locked",
    "sota": "locked",
    "automatic_promotion": False,
}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_json_text(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SemanticXorAdjudicationError(message)


def validate_disclosure_boundary(value: Mapping[str, Any]) -> None:
    probe._assert_public_no_smuggle(value)
    data = canonical_json_bytes(value).lower()
    for forbidden in (
        b'"per_task"',
        b'"private_root"',
        b'"evaluator_contents"',
        b'"task_to_cell"',
        b'"raw_capture_output"',
        b'"rationale"',
    ):
        _require(forbidden not in data, "protected or task-specific material entered publication")


def validate_scientific_summary(
    aggregate: Mapping[str, Any], resources: Mapping[str, Any]
) -> None:
    _require(dict(aggregate) == EXPECTED_AGGREGATE, "recovered aggregate changed")
    for key in ("worker_route", "direct_route", "exact_integer_cross_products"):
        _require(
            resources.get(key) == EXPECTED_ROUTE_RESOURCES[key],
            f"resource accounting changed: {key}",
        )
    _require(
        resources.get("advantage_classification") == ADVANTAGE_CLASSIFICATION
        and resources.get("worker_tokens_per_correct_strictly_lower") is False,
        "negative efficiency classification changed",
    )


def _git_bytes(repository: Path, commit: str, relative: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repository), "show", f"{commit}:{relative}"],
        check=True,
        capture_output=True,
    )
    return completed.stdout


@contextmanager
def _source_probe(repository: Path) -> Iterator[ModuleType]:
    source_bytes = _git_bytes(repository, SOURCE_COMMIT, SOURCE_MODULE_PATH)
    module_name = "_semantic_xor_attempt_3_source_controller"
    with tempfile.TemporaryDirectory(prefix="neo3000-semantic-xor-source-") as temporary:
        module_path = Path(temporary) / Path(SOURCE_MODULE_PATH).name
        module_path.write_bytes(source_bytes)
        specification = importlib.util.spec_from_file_location(module_name, module_path)
        _require(specification is not None and specification.loader is not None, "source controller import failed")
        module = importlib.util.module_from_spec(specification)
        sys.modules[module_name] = module
        specification.loader.exec_module(module)
        original_file_binding = module._file_binding

        def source_file_binding(bound_repository: Path, paths: Sequence[str]) -> dict[str, Any]:
            if list(paths) == [SOURCE_MODULE_PATH]:
                files = [{
                    "path": SOURCE_MODULE_PATH,
                    "byte_size": len(source_bytes),
                    "sha256": module.sha256_bytes(source_bytes),
                }]
                body = {"files": files}
                return {**body, "sha256": module.json_sha256(body)}
            return original_file_binding(bound_repository, paths)

        module._file_binding = source_file_binding
        try:
            yield module
        finally:
            sys.modules.pop(module_name, None)


def _archive_path(repository: Path, archive_sha256: str) -> Path:
    return repository / probe.ARCHIVE_ROOT / probe.DESIGN_ID / archive_sha256


def _verify_archive(repository: Path, archive_sha256: str) -> dict[str, Any]:
    archive = _archive_path(repository, archive_sha256)
    bundle_data = probe._regular_bytes(archive / "bundle.json", "semantic-XOR archive bundle")
    bundle = json.loads(bundle_data)
    _require(isinstance(bundle, dict), "archive bundle is not an object")
    body = {key: value for key, value in bundle.items() if key != "bundle_sha256"}
    _require(
        bundle.get("bundle_sha256") == archive_sha256
        and probe.json_sha256(body) == archive_sha256,
        "archive content address changed",
    )
    entries = bundle.get("files")
    _require(isinstance(entries, list) and entries, "archive inventory changed")
    for entry in entries:
        _require(isinstance(entry, Mapping), "archive entry changed")
        relative = entry.get("path")
        _require(isinstance(relative, str), "archive member path changed")
        data = probe._regular_bytes(archive / relative, f"archive member {relative}")
        _require(
            len(data) == entry.get("byte_size") and probe.sha256_bytes(data) == entry.get("sha256"),
            f"archive member changed: {relative}",
        )
    physical = [path for path in archive.rglob("*") if path.is_file() and not path.is_symlink()]
    _require(len(physical) == len(entries) + 1, "archive physical file count changed")
    return {"evidence_member_count": len(entries), "physical_file_count": len(physical)}


def _verify_live_archive_equality(
    repository: Path, source: ModuleType, paths: Mapping[str, Path]
) -> dict[str, Any]:
    archive = _archive_path(repository, SOURCE_EVIDENCE["archive_sha256"])
    for key, member in {
        "receipt": "authority-receipt.json",
        "manifest": "manifest.json",
        "result": "result.json",
        "closure": "closure.json",
        "journal": "journal.jsonl",
    }.items():
        _require(paths[key].read_bytes() == (archive / member).read_bytes(), f"live and archived {key} differ")
    for request_id in source.REQUEST_IDS:
        _require(
            paths[f"capture-{request_id}"].read_bytes()
            == (archive / "captures" / f"{request_id}.json").read_bytes(),
            f"live and archived capture differ: {request_id}",
        )
    return _verify_archive(repository, SOURCE_EVIDENCE["archive_sha256"])


def _request_hashes_from_journal(
    source: ModuleType, events: Sequence[Mapping[str, Any]]
) -> dict[str, str]:
    started = [event for event in events if event.get("state") == "request-started"]
    _require([event.get("request_id") for event in started] == list(source.REQUEST_IDS), "request-start order changed")
    derived_events = [
        event for event in events if event.get("state") == "derived-synthesis-request-bound"
    ]
    _require(
        [event.get("request_id") for event in derived_events] == list(source.DERIVED_REQUEST_IDS),
        "derived synthesis journal order changed",
    )
    derived = {
        str(event["request_id"]): str(event.get("facts", {}).get("model_request_sha256"))
        for event in derived_events
    }
    _require(derived == DERIVED_REQUEST_SHA256, "derived synthesis precontact hash changed")
    return {**FIXED_REQUEST_SHA256, **derived}


def _verified_replay(repository: Path) -> dict[str, Any]:
    with _source_probe(repository) as source:
        paths = source.state_paths(repository)
        expected_path_hashes = {
            "receipt": SOURCE_EVIDENCE["authority_receipt_sha256"],
            "manifest": SOURCE_EVIDENCE["manifest_sha256"],
            "result": SOURCE_EVIDENCE["live_result_sha256"],
            "closure": SOURCE_EVIDENCE["closure_sha256"],
            "journal": SOURCE_EVIDENCE["journal_sha256"],
        }
        for key, expected in expected_path_hashes.items():
            data = source._regular_bytes(paths[key], f"Attempt-3 {key}")
            _require(source.sha256_bytes(data) == expected, f"Attempt-3 {key} changed")

        archive = _verify_live_archive_equality(repository, source, paths)
        _require(
            archive == {"evidence_member_count": 21, "physical_file_count": 22},
            "Attempt-3 archive inventory changed",
        )
        for history in ATTEMPT_HISTORIES[:2]:
            _verify_archive(repository, str(history["archive_sha256"]))

        root = source._load_evidence_root(repository)
        experiment_key = source._experiment_key(root)
        receipt = source.verify_authority_receipt(repository, root)
        authority = receipt.get("authority")
        _require(isinstance(authority, Mapping), "Attempt-3 authority body is missing")
        _require(
            authority.get("authorized_commit") == SOURCE_COMMIT
            and authority.get("authority_id_sha256") == SOURCE_EVIDENCE["authority_id_sha256"]
            and authority.get("maximum_model_generations") == 16
            and authority.get("retry_allowed") is False
            and receipt.get("raw_authority_id_persisted") is False
            and "raw_authority_id" not in receipt,
            "Attempt-3 consumed authority changed",
        )

        manifest = json.loads(paths["manifest"].read_bytes())
        result = json.loads(paths["result"].read_bytes())
        closure = json.loads(paths["closure"].read_bytes())
        _require(
            manifest.get("execution_order") == list(source.REQUEST_IDS)
            and manifest.get("preregistration_artifact_sha256")
            == SOURCE_BINDINGS["preregistration_artifact_sha256"]
            and manifest.get("fixed_request_sha256") == FIXED_REQUEST_SHA256
            and manifest.get("synthesis_derivation_law_sha256")
            == SOURCE_BINDINGS["synthesis_derivation_law_sha256"],
            "Attempt-3 manifest identity changed",
        )
        _require(
            result.get("status") == "inconclusive"
            and result.get("terminal_classification") == "INCONCLUSIVE"
            and result.get("completed_model_generations") == 16
            and result.get("failure", {}).get("failure_sha256")
            == SOURCE_EVIDENCE["live_scorer_failure_sha256"]
            and result.get("cleanup", {}).get("passed") is True
            and result.get("postflight", {}).get("passed") is True,
            "Attempt-3 live terminal truth changed",
        )
        _require(
            closure.get("status") == "inconclusive"
            and closure.get("result_sha256") == SOURCE_EVIDENCE["live_result_sha256"]
            and closure.get("manifest_sha256") == SOURCE_EVIDENCE["manifest_sha256"]
            and closure.get("authority_receipt_sha256")
            == SOURCE_EVIDENCE["authority_receipt_sha256"]
            and closure.get("run_lock_absent_at_terminal_publication") is True
            and closure.get("retry_allowed") is False,
            "Attempt-3 closure changed",
        )

        events = source.verify_journal(paths["journal"], experiment_key)
        _require(
            len(events) == 70
            and events[-1].get("state") == "terminal-written"
            and events[-1].get("event_sha256") == SOURCE_EVIDENCE["journal_head_sha256"],
            "Attempt-3 authenticated journal boundary changed",
        )
        request_hashes = _request_hashes_from_journal(source, events)
        _require(request_hashes == {**FIXED_REQUEST_SHA256, **DERIVED_REQUEST_SHA256}, "request hashes changed")

        model_path_text = manifest.get("preflight", {}).get("model_identity", {}).get("path")
        _require(isinstance(model_path_text, str), "Attempt-3 model identity is unavailable")
        model_path = Path(model_path_text)
        source_prereg = source.validate_preregistration(repository, model_path)
        prereg_data = source._regular_bytes(repository / SOURCE_PREREGISTRATION_PATH, "Attempt-3 preregistration")
        _require(
            source.sha256_bytes(prereg_data) == SOURCE_BINDINGS["preregistration_file_sha256"]
            and source_prereg.get("artifact_sha256") == SOURCE_BINDINGS["preregistration_artifact_sha256"]
            and source_prereg.get("bindings", {}).get("frozen_scientific", {}).get("sha256")
            == SOURCE_BINDINGS["frozen_scientific_binding_sha256"]
            and source_prereg.get("bindings", {}).get("controller", {}).get("sha256")
            == SOURCE_BINDINGS["controller_binding_sha256"]
            and source_prereg.get("bindings", {}).get("protected_scorer", {}).get("sha256")
            == SOURCE_BINDINGS["protected_scorer_binding_sha256"]
            and source_prereg.get("bindings", {}).get("resource_accounting", {}).get("sha256")
            == SOURCE_BINDINGS["resource_accounting_binding_sha256"],
            "Attempt-3 preregistration or source binding changed",
        )
        repair_prereg = probe.validate_preregistration(repository, model_path)
        repair_data = probe._regular_bytes(repository / probe.PREREGISTRATION_PATH, "Attempt-4 repair preregistration")
        _require(
            probe.sha256_bytes(repair_data) == REPAIR_BINDINGS["preregistration_file_sha256"]
            and repair_prereg.get("artifact_sha256") == REPAIR_BINDINGS["preregistration_artifact_sha256"]
            and repair_prereg.get("bindings", {}).get("controller", {}).get("sha256")
            == REPAIR_BINDINGS["controller_binding_sha256"]
            and repair_prereg.get("bindings", {}).get("protected_scorer", {}).get("sha256")
            == REPAIR_BINDINGS["protected_scorer_binding_sha256"],
            "Attempt-4 corrected binding changed",
        )

        corpus = source.load_public_tasks(repository)
        outcomes = {
            task_id: {
                "worker_a_bit": None,
                "worker_b_bit": None,
                "synthesis_label": None,
                "baseline_label": None,
            }
            for task_id in source.TASK_IDS
        }
        worker_artifacts: dict[str, dict[str, dict[str, Any]]] = {
            task_id: {} for task_id in source.TASK_IDS
        }
        request_records = []
        observed_capture_hashes: dict[str, str] = {}
        for ordinal, request_id in enumerate(source.REQUEST_IDS, start=1):
            capture_path = paths[f"capture-{request_id}"]
            capture = scientific.verify_capture(
                capture_path,
                experiment_key=experiment_key,
                request_id=request_id,
                model_request_sha256=request_hashes[request_id],
                generation_ordinal=ordinal,
            )
            _require(capture["capture_sha256"] == CAPTURE_SHA256[request_id], f"capture changed: {request_id}")
            replay = scientific.replay_capture(capture)
            terminal = replay.terminal_stop_evidence
            _require(
                replay.http_status == 200
                and replay.finish_reason == "stop"
                and isinstance(terminal, Mapping)
                and terminal.get("observed") is True
                and terminal.get("stop") is True,
                f"raw SSE terminal boundary changed: {request_id}",
            )
            structured = source._structured_from_capture(
                capture, source._rendered_tokens(events, request_id)
            )
            task_id = source.request_task_id(request_id)
            role = source.request_role(request_id)
            if role == "worker-A":
                bit = source.parse_worker_output(structured)
                outcomes[task_id]["worker_a_bit"] = bit
                worker_artifacts[task_id][role] = source.build_worker_artifact(
                    root,
                    task_id=task_id,
                    worker_role=role,
                    worker_request_sha256=request_hashes[request_id],
                    authenticated_capture_sha256=capture["capture_sha256"],
                    captured_bit=bit,
                    generation_ordinal=ordinal,
                )
            elif role == "worker-B":
                bit = source.parse_worker_output(structured)
                outcomes[task_id]["worker_b_bit"] = bit
                worker_artifacts[task_id][role] = source.build_worker_artifact(
                    root,
                    task_id=task_id,
                    worker_role=role,
                    worker_request_sha256=request_hashes[request_id],
                    authenticated_capture_sha256=capture["capture_sha256"],
                    captured_bit=bit,
                    generation_ordinal=ordinal,
                )
            elif role == "synthesis":
                verified = source.verify_worker_artifacts_before_synthesis(
                    paths=paths,
                    experiment_key=experiment_key,
                    root=root,
                    task_id=task_id,
                    artifacts=worker_artifacts[task_id],
                    outcome=outcomes[task_id],
                    fixed_request_hashes=FIXED_REQUEST_SHA256,
                )
                derived_payload = source.build_synthesis_request(corpus, task_id, verified)
                _require(
                    source.verify_synthesis_payload(corpus, task_id, verified, derived_payload)
                    == DERIVED_REQUEST_SHA256[request_id],
                    f"derived synthesis request changed: {request_id}",
                )
                outcomes[task_id]["synthesis_label"] = source.parse_label_output(structured)
            else:
                outcomes[task_id]["baseline_label"] = source.parse_label_output(structured)
            request_records.append(source._resource_record(capture, request_id))
            observed_capture_hashes[request_id] = capture["capture_sha256"]

        _require(observed_capture_hashes == CAPTURE_SHA256, "capture inventory changed")
        try:
            source.score_protected_outcomes(
                repository,
                outcomes,
                completed_capture_ids=source.REQUEST_IDS,
                cleanup_passed=True,
                postflight_passed=True,
            )
        except source.SemanticXorEvaluationError as exc:
            old_failure_sha256 = source.sha256_bytes(str(exc).encode("utf-8"))
        else:
            raise SemanticXorAdjudicationError("original scorer unexpectedly passed")
        _require(
            old_failure_sha256 == SOURCE_EVIDENCE["live_scorer_failure_sha256"],
            "original scorer failure did not reproduce",
        )

        scoring = probe.score_protected_outcomes(
            repository,
            outcomes,
            completed_capture_ids=probe.REQUEST_IDS,
            cleanup_passed=True,
            postflight_passed=True,
        )
        capability = probe.capability_classification(
            scoring,
            evidence_complete=True,
            cleanup_passed=True,
            postflight_passed=True,
        )
        resources = probe.account_resources(request_records, scoring, capability)
        _require(capability == CAPABILITY_CLASSIFICATION, "forensic capability classification changed")
        validate_scientific_summary(scoring["aggregate"], resources)
        return {
            "aggregate": dict(scoring["aggregate"]),
            "resources": resources,
            "archive": archive,
            "capture_sha256": observed_capture_hashes,
            "journal_event_count": len(events),
            "raw_sse_reconstruction_count": len(observed_capture_hashes),
            "old_scorer_failure_sha256": old_failure_sha256,
        }


def render_adjudication(repository: Path) -> dict[str, Any]:
    replay = _verified_replay(repository)
    resources = replay["resources"]
    artifact = {
        "schema_version": 1,
        "adjudication_id": ADJUDICATION_ID,
        "design_id": probe.DESIGN_ID,
        "status": "adjudicated",
        "attempt_histories": ATTEMPT_HISTORIES,
        "source_execution": {
            "attempt": 3,
            "protected_commit": SOURCE_COMMIT,
            "live_terminal_classification": "INCONCLUSIVE",
            "completed_model_generations": 16,
            "retry_count": 0,
            **SOURCE_EVIDENCE,
            "capture_sha256": replay["capture_sha256"],
            "archive_evidence_member_count": replay["archive"]["evidence_member_count"],
            "archive_physical_file_count": replay["archive"]["physical_file_count"],
        },
        "bindings": {
            "source_attempt_3": SOURCE_BINDINGS,
            "corrected_static_attempt_4": REPAIR_BINDINGS,
            "fixed_request_sha256": FIXED_REQUEST_SHA256,
            "derived_synthesis_request_sha256": DERIVED_REQUEST_SHA256,
        },
        "zero_contact_reconstruction": {
            "source_preregistration_exact": True,
            "authority_receipt_hmac_verified": True,
            "raw_authority_id_persisted": False,
            "manifest_identity_verified": True,
            "authenticated_journal_events_verified": replay["journal_event_count"],
            "authenticated_captures_verified": 16,
            "raw_sse_reconstructions_verified": replay["raw_sse_reconstruction_count"],
            "fixed_request_hashes_verified": 12,
            "derived_synthesis_hashes_verified": 4,
            "cleanup_verified": True,
            "postflight_verified": True,
            "archive_verified": True,
            "live_archive_equality_verified": True,
            "old_scorer_failure_reproduced": True,
            "old_scorer_failure_sha256": replay["old_scorer_failure_sha256"],
            "corrected_scorer_replay_exact": True,
            "model_requests_issued": 0,
            "sidecar_launches": 0,
            "model_generations": 0,
            "authorities_created_or_consumed": 0,
        },
        "forensic_adjudication": {
            "classification": CAPABILITY_CLASSIFICATION,
            "bounded_interpretation": BOUNDED_INTERPRETATION,
            "workers_are_separate_requests_same_model_and_runtime": True,
            "controller_had_structured_expected_bits_before_protected_scoring": False,
            "xor_operation_is_deterministic": True,
            "aggregate": replay["aggregate"],
            "task_scope": 4,
        },
        "resource_adjudication": {
            "classification": ADVANTAGE_CLASSIFICATION,
            "worker_route": resources["worker_route"],
            "direct_route": resources["direct_route"],
            "exact_integer_cross_products": resources["exact_integer_cross_products"],
            "worker_tokens_per_correct_strictly_lower": False,
            "higher_worker_accuracy_overrides_efficiency_law": False,
        },
        "supported_claims": [
            "bounded non-controller-reconstructible semantic worker judgments on four frozen tasks",
            "bounded XOR synthesis fidelity",
            "worker route final accuracy 4/4",
            "direct baseline final accuracy 3/4",
            "exact observed token comparison",
            "no fresh-inference advantage",
        ],
        "locked_claims": dict(LOCKED_CLAIMS),
        "next_boundary": NEXT_BOUNDARY,
        "next_boundary_qualification": (
            "zero-contact post hoc diagnostic using preserved worker and direct-baseline captures; "
            "exclude all four model-synthesis requests from accounting; separately confirm before claim use"
        ),
    }
    validate_disclosure_boundary(artifact)
    return artifact


def render_record(
    repository: Path, artifact: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    adjudication = dict(artifact or render_adjudication(repository))
    artifact_sha256 = probe.sha256_bytes(canonical_json_bytes(adjudication) + b"\n")
    source_execution = adjudication["source_execution"]
    forensic = adjudication["forensic_adjudication"]
    resources = adjudication["resource_adjudication"]
    record = {
        "id": RECORD_ID,
        "checkpoint": "2-Catalytic-Kernel-0-semantic-XOR-worker-baseline-forensic-adjudication",
        "hypothesis": (
            "Two isolated semantic workers can generate correct task-relevant judgments unavailable "
            "in controller-readable structured form and XOR-synthesize correct labels across the frozen "
            "four-task family, while a same-evidence direct baseline supplies the preregistered fresh-token comparison."
        ),
        "intervention": (
            "Statically authenticate and replay immutable Attempt-3 captures, reproduce the original "
            "scorer failure, and apply only the corrected aggregate-witness predicate."
        ),
        "baseline_commit": SOURCE_COMMIT,
        "candidate_commit": None,
        "model_hash": probe.MODEL_SHA256,
        "configuration": {
            "design_id": probe.DESIGN_ID,
            "source_execution_attempt": 3,
            "source_execution_commit": SOURCE_COMMIT,
            "static_repair_commit": REPAIR_COMMIT,
            "request_count": 16,
            "maximum_generations_per_request": 1,
            "source_bindings": SOURCE_BINDINGS,
            "corrected_scorer_binding_sha256": REPAIR_BINDINGS["protected_scorer_binding_sha256"],
        },
        "metrics_before": {
            "source_live_terminal_classification": "INCONCLUSIVE",
            "source_live_scorer_failure_sha256": SOURCE_EVIDENCE["live_scorer_failure_sha256"],
            "source_live_result_immutable": True,
        },
        "metrics_after": {
            "status": "forensically-adjudicated",
            "source_execution_terminal_classification": "INCONCLUSIVE",
            "forensic_adjudication_classification": CAPABILITY_CLASSIFICATION,
            "efficiency_classification": ADVANTAGE_CLASSIFICATION,
            "bounded_interpretation": BOUNDED_INTERPRETATION,
            "aggregate": forensic["aggregate"],
            "worker_route": resources["worker_route"],
            "direct_route": resources["direct_route"],
            "exact_integer_cross_products": resources["exact_integer_cross_products"],
            "authority_receipt_sha256": source_execution["authority_receipt_sha256"],
            "manifest_sha256": source_execution["manifest_sha256"],
            "live_result_sha256": source_execution["live_result_sha256"],
            "closure_sha256": source_execution["closure_sha256"],
            "journal_sha256": source_execution["journal_sha256"],
            "journal_head_sha256": source_execution["journal_head_sha256"],
            "evidence_archive_sha256": source_execution["archive_sha256"],
            "capture_sha256": source_execution["capture_sha256"],
            "adjudication_artifact_sha256": artifact_sha256,
            "zero_contact_replay_generations": 0,
        },
        "quality_gates": {
            "source_preregistration_exact": True,
            "authority_receipt_hmac_verified": True,
            "journal_events_authenticated": 70,
            "captures_authenticated": 16,
            "raw_sse_reconstruction_exact": True,
            "fixed_request_bindings_verified": 12,
            "derived_request_bindings_verified": 4,
            "old_scorer_failure_reproduced": True,
            "corrected_scorer_replay_exact": True,
            "archive_and_all_twenty_one_members_verified": True,
            "live_terminal_truth_preserved": True,
            "no_disclosure": True,
            "general_catalytic_inference_locked": True,
            "fresh_inference_advantage_not_supported": True,
            "automatic_promotion": False,
        },
        "verdict": "accept",
        "next_boundary": NEXT_BOUNDARY,
    }
    validate_disclosure_boundary(record)
    return record


def validate_publication(repository: Path) -> dict[str, Any]:
    artifact = render_adjudication(repository)
    artifact_bytes = canonical_json_bytes(artifact) + b"\n"
    artifact_path = repository / ARTIFACT_PATH
    _require(
        artifact_path.is_file()
        and not artifact_path.is_symlink()
        and artifact_path.read_bytes() == artifact_bytes,
        "tracked adjudication artifact differs from exact reconstruction",
    )
    expected_record = render_record(repository, artifact)
    expected_line = canonical_json_text(expected_record)
    lines = (repository / RESULTS_PATH).read_text(encoding="utf-8").splitlines()
    matches = [
        (line_number, line, json.loads(line))
        for line_number, line in enumerate(lines, 1)
        if json.loads(line).get("id") == RECORD_ID
    ]
    _require(len(matches) == 1, "publication must contain exactly one record")
    line_number, line, value = matches[0]
    _require(line_number == EXPECTED_LEDGER_LINE, "ledger line changed")
    _require(line == expected_line and value == expected_record, "ledger record differs from exact render")
    return {
        "status": "pass",
        "adjudication_id": ADJUDICATION_ID,
        "adjudication_artifact_sha256": probe.sha256_bytes(artifact_bytes),
        "record_id": RECORD_ID,
        "ledger_line": line_number,
        "record_sha256": probe.sha256_bytes(expected_line.encode("utf-8")),
        "source_live_terminal_classification": "INCONCLUSIVE",
        "forensic_capability_classification": CAPABILITY_CLASSIFICATION,
        "efficiency_classification": ADVANTAGE_CLASSIFICATION,
        "archive_evidence_member_count": 21,
        "archive_physical_file_count": 22,
        "authenticated_capture_count": 16,
        "authenticated_journal_event_count": 70,
        "zero_contact_replay": True,
        "model_requests_issued": 0,
        "sidecar_launches": 0,
        "model_generations": 0,
        "authorities_created_or_consumed": 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("render-artifact", "render-record", "validate"))
    parser.add_argument("--repository", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository = Path(args.repository).resolve(strict=False)
    try:
        if args.action == "render-artifact":
            result = render_adjudication(repository)
        elif args.action == "render-record":
            result = render_record(repository)
        else:
            result = validate_publication(repository)
    except (
        OSError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
        SemanticXorAdjudicationError,
        probe.SemanticXorEvaluationError,
        scientific.ScientificSurfaceError,
    ) as exc:
        print(canonical_json_text({"status": "fail", "error": str(exc)}))
        return 1
    print(canonical_json_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
