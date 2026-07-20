#!/usr/bin/env python3
"""Zero-contact adjudication of immutable HoloState warm-trajectory Attempt-7 evidence."""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator, Mapping, Sequence

import holostate_v1_warm_trajectory_related_task_evaluation as probe


class WarmTrajectoryAdjudicationError(ValueError):
    """The immutable Attempt-7 evidence cannot support bounded publication."""


SOURCE_COMMIT = "20798cb5712decea8a0acb158ceeaa0a012c7844"
SOURCE_MODULE_PATH = "scripts/holostate_v1_warm_trajectory_related_task_evaluation.py"
ARTIFACT_PATH = Path(
    "lab/holostate_v1_warm_trajectory_related_task_evaluation_v1_attempt_7_adjudication_1.json"
)
RESULTS_PATH = Path("lab/results.jsonl")
ADJUDICATION_ID = "holostate-v1-warm-trajectory-related-task-evaluation-v1-attempt-7-adjudication-1"
RECORD_ID = "neo-exp-0048"
EXPECTED_LEDGER_LINE = 61
PREDECESSOR_RECORD_ID = "neo-exp-0047"

REUSE_CLASSIFICATION = "PROCESS_LOCAL_WARM_TRAJECTORY_EXACT_CHECKPOINT_REUSE_REPLICATED"
CLOSURE_CLASSIFICATION = "IMMEDIATE_EXACT_CHECKPOINT_CLOSURE_NOT_SUPPORTED"
PARTIAL_CLOSURE_CLASSIFICATION = "CONSISTENT_PARTIAL_CHECKPOINT_READDRESS_OBSERVED"
EFFICIENCY_CLASSIFICATION = (
    "SINGLE_BRANCH_COMPLETE_CATALYTIC_CYCLE_FRESH_TOKEN_ADVANTAGE_NOT_SUPPORTED"
)
BOUNDED_INTERPRETATION = (
    "EXACT_PROCESS_LOCAL_EXECUTABLE_CHECKPOINT_REUSE_REPLICATED_ACROSS_FOUR_RELATED_"
    "TASKS_WITH_EQUAL_TASK_B_ACCURACY_BUT_SINGLE_BRANCH_MATERIALIZATION_AND_CLOSURE_"
    "COSTS_PREVENTED_COMPLETE_CYCLE_FRESH_TOKEN_ADVANTAGE"
)
NEXT_BOUNDARY = (
    "STATICALLY_SELECT_MINIMUM_SUCCESSOR_FOR_WARM_TRAJECTORY_AMORTIZATION_OR_INHERITED_CARRIER_STATE"
)

SOURCE_BINDINGS = {
    "public_corpus_sha256": "A45FF0A6DCD8E3E75CBE0B0F7A572DB023B0E7CE81093F7C82155D0A4DC3D4A9",
    "protected_evaluator_sha256": "AAC8CC0DEE3C748F92A9BA350E8EF32063171F5AF9B24754D55B1A7E71B0BE3E",
    "preregistration_artifact_sha256": "9370CD0A2A041BD46A765728B1A93B622BB66BD3EEFF71D45E80189C453C1002",
    "preregistration_file_sha256": "469062E6AEEE953988AF4DC035E4A2155673063B2E3C6D9699294CE7799BE68A",
    "frozen_scientific_binding_sha256": "EB8A386E6453DB0B1948C4542F35AEFDEF58D5EB1CBFAB46FEC4D309101BC6C7",
    "controller_binding_sha256": "AC85A6FDADE3D4515B5C3DF7A9766BF74CC8D0EDF57192D028FF041C5939A8E1",
    "protected_scorer_binding_sha256": "A3FF0CFB35649F24C4517D52B7F770A5A9D19D8648398240FA8C07B2E0C39171",
    "resource_accounting_binding_sha256": "1FB748E2014692AE600AE94EC68FF0F15E9BFFC946F6CB835F6777882B3A77BA",
    "checkpoint_closure_binding_sha256": "71947163A74622DCA8C82068E4E75388E4B4E6A051C8862C5B4ED6774E7DC389",
    "runtime_binary_sha256": "EFA521C4DC4189C89CC71B34CDB46079143857A4D49148E2D4411D3F7599FEE5",
    "runtime_version": "160 (89762c0)",
    "model_sha256": "31AEFA25B7E1EDBDE436E643E2B5E3F6E57820A4811D97B131130E48FF0772C2",
}

SOURCE_EVIDENCE = {
    "authority_id_sha256": "BECA90028A54F8BC7867EB844F7CE84054C24E96B3DA7935CF3F893F8F0CC1B4",
    "authority_receipt_sha256": "2832F52A619665B5AFB2BD1AF94F58E99FC007EAAA9CC98730D8267667C9AC3A",
    "manifest_sha256": "FF98365CFF6DC2AFC286AEF25FF75BDA97E3C5C31B1585FEFF77D5E87BCB54AF",
    "journal_sha256": "368EAA9460A303788B8A9B8431E9FF3294B3BCA58BFFFA6EE7CBD0278E9F6804",
    "journal_head_sha256": "8A823F61B87B928B4E9C63C860D659D78AFAE278EBCBD98BFD3DE16130E0FAB0",
    "live_result_sha256": "2682E35FFA26CB253888DF0022CD8C40CC73E2D5B4425F3073D3164CCE459234",
    "closure_sha256": "47D05C47A6494207361B866252DA9ADECFE213DC343946BB230F6EB4E4FA6A83",
    "archive_sha256": "E48C62DC8F0EDED92FDD543A0A44C3BB740AA46BC7C217D39FBA40EBD8F9714E",
}

CAPTURE_SHA256 = {
    "warm-trajectory-archive-01-task-a": "F958B781E52F9A0BD98F8D4C393D0DB6C110FDC8D02446AB4A97551AE4BA2CC3",
    "warm-trajectory-archive-01-task-b-catalytic": "401B1DF6DE52D30448C0F86E28C1E0EF2DEBDEE0DE00F4193D18DD3294294967",
    "warm-trajectory-archive-01-task-b-direct": "028BFB45013ED73C99DECEE462AD6B78DC427826F168F1C6F61D280B3EC16EFD",
    "warm-trajectory-refuge-02-task-a": "7623A415C1677C32C1E945945D7BAE281B22942445FAB460028CE19BFC0FF120",
    "warm-trajectory-refuge-02-task-b-direct": "FA62A58E567ACE5426266F1BBB214220810DB1D9A6C8805FEB14EF8BA830358B",
    "warm-trajectory-refuge-02-task-b-catalytic": "E98B24FFD425FCBB4F8444700F127185E787367B134869BED9AE4A5FB5C67E29",
    "warm-trajectory-observatory-03-task-a": "29BB667ED77C465B003C33457A777EC454BA309C58CD95EEF66E02B91FF178FA",
    "warm-trajectory-observatory-03-task-b-catalytic": "3F6FA78CEE658521E9B8B3A8F8EEFBCF0E9DE48AE684BCCB7E18E4DADDD61FA8",
    "warm-trajectory-observatory-03-task-b-direct": "3E8402D5D224B71CD0BDEDBBC47DF8BF53509A956E7C3E655A3667DFE72CCA25",
    "warm-trajectory-clinic-04-task-a": "2320C2CA6C2C4D9DCB22CC7053E419BB39185A6B25C852C71FEE19F382CF7C09",
    "warm-trajectory-clinic-04-task-b-direct": "F4BBBD8A990F4BCFC2B6BD7EEA44C02A5E2BE46A228477FA53FE9C1DF20956A7",
    "warm-trajectory-clinic-04-task-b-catalytic": "5B916E1A11473CF6BA3B5FA85D1E14F86B62D174371D551AF67AB037CED784F2",
}

REQUEST_SHA256 = {
    "warm-trajectory-archive-01-task-a": "B8E66591C671B6DEBA97D11B392DB29B727E54FB628787A07156A2284CD17533",
    "warm-trajectory-archive-01-task-b-catalytic": "E04F0C358FC2CCB5A0FCC77357D8172A00478716E7D88E054C8651262FF5EB89",
    "warm-trajectory-archive-01-task-b-direct": "0B4F49809221B4B28453F400751E8E4588326D1243C80D948650C9CDFF692EA8",
    "warm-trajectory-refuge-02-task-a": "18C2ACDFD37A767D9B36A5B775B04A6C03008B173CB5908B26D6E56D5250FA61",
    "warm-trajectory-refuge-02-task-b-direct": "80F6E2729CC79618E83A62239B0DDB9C3664B1840D57FA3783CB51160097D074",
    "warm-trajectory-refuge-02-task-b-catalytic": "17A31D658E5B5E9D9BF5908BE9CF248C631A3046A9FD39CC09D8C06D94905019",
    "warm-trajectory-observatory-03-task-a": "72CBB3D6084622E6CFA7323AFDE19518E847FC093F2236388E5D5C11BFB7CF96",
    "warm-trajectory-observatory-03-task-b-catalytic": "FF83AB4F4C81721846B3E69EF777885FCFBA36B3B592D5E34725BB21DDF9489C",
    "warm-trajectory-observatory-03-task-b-direct": "4319CD445E877EC3DDF926AAB940005722C06FD8ADF29C111F31416DF282559D",
    "warm-trajectory-clinic-04-task-a": "6839C608822F7D759D23D9ADDCFB9E5A29C5597578FF2A4485CEC3E5F89C680C",
    "warm-trajectory-clinic-04-task-b-direct": "5752FA08D2F639DAA9AFD45B1D178D893536FE74B730CB9BF27D1B5012BCF00C",
    "warm-trajectory-clinic-04-task-b-catalytic": "2AEAD3B300E88D7D2A730BE2DA51073E6B6C57E582956E709F5B2E6A62D48BFE",
}

EXPECTED_CHECKPOINTS = {
    "warm-trajectory-archive-01": {"checkpoint_tokens": 1004, "catalytic_cached_tokens": 1004, "direct_cached_tokens": 0, "closure_cached_tokens": 872, "closure_fresh_tokens": 132},
    "warm-trajectory-refuge-02": {"checkpoint_tokens": 1052, "catalytic_cached_tokens": 1052, "direct_cached_tokens": 0, "closure_cached_tokens": 920, "closure_fresh_tokens": 132},
    "warm-trajectory-observatory-03": {"checkpoint_tokens": 1031, "catalytic_cached_tokens": 1031, "direct_cached_tokens": 0, "closure_cached_tokens": 899, "closure_fresh_tokens": 132},
    "warm-trajectory-clinic-04": {"checkpoint_tokens": 1098, "catalytic_cached_tokens": 1098, "direct_cached_tokens": 0, "closure_cached_tokens": 966, "closure_fresh_tokens": 132},
}

EXPECTED_AGGREGATE = {
    "task_a_answer_correct": 4,
    "task_a_latent_state_correct": 3,
    "catalytic_task_b_correct": 4,
    "direct_task_b_correct": 4,
}

EXPECTED_RESOURCE_SUMMARY = {
    "carrier_materialization_fresh_tokens": 4185,
    "catalytic_task_b_suffix_fresh_prompt_plus_completion_tokens": 723,
    "closure_readdress_fresh_tokens": 528,
    "complete_catalytic_marginal_fresh_prompt_plus_completion_tokens": 5436,
    "direct_replay_fresh_prompt_plus_completion_tokens": 4908,
    "complete_catalytic_correct": 4,
    "direct_replay_correct": 4,
    "complete_catalytic_tokens_x_direct_correct": 21744,
    "direct_tokens_x_complete_catalytic_correct": 19632,
}

ATTEMPT_LINEAGE = [
    {"attempt": 1, "source_commit": "242b190aa6923f697a93efab062be547b4bb944c", "terminal_classification": "INCONCLUSIVE", "authority_receipt_sha256": "88E7AEA3486FEC2CF4996393A48AB301D78A6CAE241FD006D5D5C2CE4DD6AF12", "model_generations": 0, "carrier_operations": 0, "archive_sha256": None},
    {"attempt": 2, "source_commit": "c442269a187cc228ef39cc54e779f223a178964e", "terminal_classification": "INCONCLUSIVE", "authority_receipt_sha256": "01744A976F84F57DEE2C91EF3817DB6ED2794BBA32AB6AE612D0498E6BE100F3", "result_sha256": "B00234F96CF61FB6C7298FD3B39C52A2CB3745A1D8833E77AF3C45CEDDB2FBBA", "closure_sha256": "5E61DAF6F8EE56F2A1C60DEA0899325D63F2C7493FD214BB7F3C11946C187981", "archive_sha256": "E7B7EB7FB097C5A2BEDE1602FBFC74D650E064D54E6C8DCDD832AD6F9EFFACC4", "model_generations": 1, "carrier_operations": 0},
    {"attempt": 3, "source_commit": "f74529479bbdef386d70a666a9c4ae36b600075f", "terminal_classification": "INCONCLUSIVE", "authority_receipt_sha256": "352B9EAE0CFBD13E009928EED4A9E300E6C114B2A205F7AC4C9B3C10D34C721A", "result_sha256": "B4D3F6C08586A4233A16BD5951A3F10E90414F1B200801A0EB14AE70F5E60AA1", "closure_sha256": "EBF5EBC86DE64F23F9B7EB0117D747DF0C52370422CCA69711673719D7D508B9", "archive_sha256": "EBDDE88262BA24D0659988BB69051101CA99E584EDF1CBFBD8647E092D403B13", "model_generations": 1, "carrier_operations": 0},
    {"attempt": 4, "source_commit": "748b3fff8ef59fc78069fe21a463a8eb282a48af", "terminal_classification": "INCONCLUSIVE", "authority_receipt_sha256": "9631B4F62528B6D099255E5B22F34A77F2A9F733DE7F74877CD2BA57B65B4E4B", "result_sha256": "05840E52327BE306D5781C6FFE81A040A50E89301C3860C6945F58CC97A59207", "closure_sha256": "3E3FF03DA99FAED8BA19650B7E6D42A9B30E77902FE57F9186E8BB75679093A0", "archive_sha256": "BEF9D3E36080D29CDE8F33A7C5CE842F1D774E46093E2F740784A7C4F18768DD", "model_generations": 1, "carrier_operations": 0},
    {"attempt": 5, "source_commit": "a38e86e45e0cfc20e2882167755a8d7df91ecd51", "terminal_classification": "INCONCLUSIVE", "authority_receipt_sha256": "DB7C0C334429500F4E1C8B813D0BF68704BD9E8692CD7201B0917971E451BC79", "result_sha256": "13CE78DD00182BD74D05AFE94134A6BEEB6B8BBA8618419C588637F184802825", "closure_sha256": "A2F314E7AF5B4255B75673A1AF9F611AD8A0764CD0CB93D4845E8D460F3A6162", "archive_sha256": "AA40B8BBA2F4872C84FA7104264BBD9162F4196777FF071DFF7F0006D972D494", "model_generations": 1, "carrier_operations": 0},
    {"attempt": 6, "source_commit": "3eaa86ffb690611f3549272bdd367c778ddf8da2", "terminal_classification": "INCONCLUSIVE", "authority_receipt_sha256": "E89D45A5093F6BB0AE164BC585550172E210F84CE2CA36BE759DEF403091CD7B", "result_sha256": "33DCC2DBB750D956C12E879FF03DE5F56010E7652AA1C493E2B35E88CBA9CB4D", "closure_sha256": "EE1BA952241BA824457DDDFA192DAA47078FF8C2482CE1ABA26CC8DC0800EC42", "archive_sha256": "6AC053C53C48C9552283D6D3F75CFC635CDCF40540AA5369A2342ABE21C49AD5", "model_generations": 3, "carrier_operations": 2},
    {"attempt": 7, "source_commit": SOURCE_COMMIT, "terminal_classification": "INCONCLUSIVE", "authority_receipt_sha256": SOURCE_EVIDENCE["authority_receipt_sha256"], "result_sha256": SOURCE_EVIDENCE["live_result_sha256"], "closure_sha256": SOURCE_EVIDENCE["closure_sha256"], "archive_sha256": SOURCE_EVIDENCE["archive_sha256"], "model_generations": 12, "carrier_operations": 8, "scientific_source_for_adjudication": True},
]

LOCKED_CLAIMS = {
    "exact_immediate_restoration": "locked",
    "complete_catalytic_lifecycle": "locked",
    "restart_persistent_state": "locked",
    "general_catalytic_inference": "locked",
    "arbitrary_task_transfer": "locked",
    "compute_amplification_beyond_observed_accounting": "locked",
    "reduced_wall_clock_latency": "locked",
    "persistent_blackboard_value": "locked",
    "adaptive_swarms": "locked",
    "superiority": "locked",
    "sota": "locked",
    "automatic_promotion": False,
}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_json_text(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise WarmTrajectoryAdjudicationError(message)


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


def _stream_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest().upper()


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repository), *args], check=True, capture_output=True, text=True).stdout.strip()


def _git_bytes(repository: Path, commit: str, relative: str) -> bytes:
    return subprocess.run(["git", "-C", str(repository), "show", f"{commit}:{relative}"], check=True, capture_output=True).stdout


def validate_disclosure_boundary(value: Mapping[str, Any]) -> None:
    probe._assert_public_no_smuggle(value)
    lowered = canonical_json_bytes(value).lower()
    for forbidden in (
        b'"raw_authority_id"', b'"raw_response_capture"', b'"protected_evaluator_contents"',
        b'"state_required_concepts"', b'"task_a_answer"', b'"task_b_answer"',
        b'"expected_task_a_answer"', b'"expected_task_b_answer"',
        b'"private_salt_hex"', b'"task_to_cell"', b'"private_root"',
        b'"task_a_state_requirement_matches"', b'"per_pair"', b'"raw_output"',
    ):
        _require(forbidden not in lowered, "protected or raw material entered publication")


@contextmanager
def _source_probe(repository: Path) -> Iterator[ModuleType]:
    source_bytes = _git_bytes(repository, SOURCE_COMMIT, SOURCE_MODULE_PATH)
    _require(source_bytes == (repository / SOURCE_MODULE_PATH).read_bytes(), "source controller bytes changed")
    with tempfile.TemporaryDirectory(prefix="neo3000-warm-adjudication-") as temporary:
        module_path = Path(temporary) / Path(SOURCE_MODULE_PATH).name
        module_path.write_bytes(source_bytes)
        spec = importlib.util.spec_from_file_location("_warm_trajectory_attempt_7_source", module_path)
        _require(spec is not None and spec.loader is not None, "source controller import failed")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        try:
            yield module
        finally:
            sys.modules.pop(spec.name, None)


def _verify_source_bindings(repository: Path, source: ModuleType, manifest: Mapping[str, Any]) -> dict[str, Any]:
    _git(repository, "cat-file", "-e", f"{SOURCE_COMMIT}^{{commit}}")
    _require(_git(repository, "merge-base", "--is-ancestor", SOURCE_COMMIT, "HEAD") == "", "source commit is not an ancestor")
    prereg_path = repository / probe.PREREGISTRATION_PATH
    _require(_stream_sha256(prereg_path) == SOURCE_BINDINGS["preregistration_file_sha256"], "preregistration file changed")
    original_state_root = source.STATE_ROOT
    original_receipt = source.AUTHORITY_RECEIPT_PATH
    source.STATE_ROOT = Path("state/adjudication-preregistration-absence-proof")
    source.AUTHORITY_RECEIPT_PATH = Path("state/adjudication-preregistration-absence-proof.receipt")
    try:
        expected = source.build_preregistration_document(repository)
    finally:
        source.STATE_ROOT = original_state_root
        source.AUTHORITY_RECEIPT_PATH = original_receipt
    actual = _json_bytes(prereg_path.read_bytes(), "preregistration")
    _require(actual == expected, "preregistration exact reconstruction changed")
    _require(actual.get("artifact_sha256") == SOURCE_BINDINGS["preregistration_artifact_sha256"], "preregistration artifact changed")
    bindings = actual.get("bindings", {})
    expected_bindings = {
        "frozen_scientific": SOURCE_BINDINGS["frozen_scientific_binding_sha256"],
        "controller": SOURCE_BINDINGS["controller_binding_sha256"],
        "protected_scorer": SOURCE_BINDINGS["protected_scorer_binding_sha256"],
        "resource_accounting": SOURCE_BINDINGS["resource_accounting_binding_sha256"],
        "checkpoint_closure": SOURCE_BINDINGS["checkpoint_closure_binding_sha256"],
    }
    for key, expected_sha in expected_bindings.items():
        _require(bindings.get(key, {}).get("sha256") == expected_sha, f"source binding changed: {key}")
    corpus = source.load_public_corpus(repository)
    _require(_stream_sha256(repository / source.PUBLIC_CORPUS_PATH) == SOURCE_BINDINGS["public_corpus_sha256"], "public corpus changed")
    binary_path = Path(str(manifest["preflight"]["binary_identity"]["path"]))
    model_path = Path(str(manifest["preflight"]["model_identity"]["path"]))
    _require(_stream_sha256(binary_path) == SOURCE_BINDINGS["runtime_binary_sha256"], "runtime binary changed")
    _require(manifest["preflight"]["binary_identity"].get("runtime_version") == SOURCE_BINDINGS["runtime_version"], "runtime version changed")
    _require(_stream_sha256(model_path) == SOURCE_BINDINGS["model_sha256"], "model changed")
    return {"preregistration": actual, "corpus": corpus}


def _verify_archive(repository: Path, attempt: int, archive_sha256: str) -> dict[str, Any]:
    archive = repository / probe.ARCHIVE_ROOT.parent / f"attempt-{attempt}" / archive_sha256
    bundle = _json_bytes((archive / "bundle.json").read_bytes(), f"Attempt-{attempt} archive bundle")
    body = {key: value for key, value in bundle.items() if key != "bundle_sha256"}
    _require(bundle.get("bundle_sha256") == archive_sha256 and probe.json_sha256(body) == archive_sha256, f"Attempt-{attempt} archive address changed")
    members = bundle.get("members")
    _require(isinstance(members, list) and bool(members), f"Attempt-{attempt} archive inventory changed")
    for member in members:
        _require(isinstance(member, Mapping) and isinstance(member.get("path"), str), "archive member changed")
        path = archive / str(member["path"])
        _require(path.is_file() and not path.is_symlink(), f"archive member missing: {member['path']}")
        data = path.read_bytes()
        _require(len(data) == member.get("bytes") and probe.sha256_bytes(data) == member.get("sha256"), f"archive member changed: {member['path']}")
    physical = [path for path in archive.rglob("*") if path.is_file() and not path.is_symlink()]
    _require(len(physical) == len(members) + 1, f"Attempt-{attempt} archive physical count changed")
    return {"evidence_member_count": len(members), "physical_file_count": len(physical), "path": archive}


def _verify_lineage(repository: Path, source: ModuleType, root: bytes) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    for item in ATTEMPT_LINEAGE:
        attempt = int(item["attempt"])
        if attempt == 1:
            receipt_path = repository / "state/catalytic_kernel_0_authority.holostate-v1-warm-trajectory-related-task-evaluation-v1.authority.consumed.json"
            expected_attempt = None
        else:
            receipt_path = repository / f"state/catalytic_kernel_0_authority.holostate-v1-warm-trajectory-related-task-evaluation-v1-attempt-{attempt}.authority.consumed.json"
            expected_attempt = f"{probe.DESIGN_ID}-attempt-{attempt}"
        _require(_stream_sha256(receipt_path) == item["authority_receipt_sha256"], f"Attempt-{attempt} receipt changed")
        receipt = source._verify_authority_receipt_path(receipt_path, root, expected_attempt_id=expected_attempt)
        _require(receipt.get("authority", {}).get("authorized_commit") == item["source_commit"], f"Attempt-{attempt} authority commit changed")
        _require(receipt.get("raw_authority_id_persisted") is False, f"Attempt-{attempt} raw authority persistence changed")
        summary = {"attempt": attempt, "authority_receipt_hmac_verified": True, "raw_authority_id_persisted": False}
        if item.get("archive_sha256"):
            archive = _verify_archive(repository, attempt, str(item["archive_sha256"]))
            summary.update({"archive_verified": True, **{k: v for k, v in archive.items() if k != "path"}})
        verified.append(summary)
    return verified


def _verify_journal(path: Path, source: ModuleType, experiment_key: bytes) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    previous = "0" * 64
    for ordinal, line in enumerate(path.read_bytes().splitlines(), start=1):
        event = _json_bytes(line, f"journal event {ordinal}")
        verified = source.verify_journal_event(event, experiment_key, expected_previous=previous, expected_ordinal=ordinal)
        events.append(verified)
        previous = str(verified["event_sha256"])
    _require(len(events) == 38 and previous == SOURCE_EVIDENCE["journal_head_sha256"], "journal chain boundary changed")
    return events


def _raw_sse_events(capture: Mapping[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in probe.raw_sse_bytes(capture).decode("utf-8", errors="strict").splitlines():
        if not line.startswith("data:"):
            continue
        text = line[5:].strip()
        if not text or text == "[DONE]":
            continue
        events.append(_json_bytes(text.encode("utf-8"), "raw SSE event"))
    _require(bool(events), "raw SSE capture contains no events")
    return events


def _replay_raw_sse(capture: Mapping[str, Any], request_id: str) -> dict[str, Any]:
    events = _raw_sse_events(capture)
    execution = capture.get("execution")
    _require(isinstance(execution, Mapping), "capture execution is missing")
    if request_id.endswith("task-a"):
        content: list[str] = []
        reasoning: list[str] = []
        terminal: Mapping[str, Any] | None = None
        for event in events:
            choices = event.get("choices")
            _require(isinstance(choices, list) and choices and isinstance(choices[0], Mapping), "chat SSE choice changed")
            choice = choices[0]
            delta = choice.get("delta")
            if isinstance(delta, Mapping):
                if isinstance(delta.get("content"), str):
                    content.append(str(delta["content"]))
                if isinstance(delta.get("reasoning_content"), str):
                    reasoning.append(str(delta["reasoning_content"]))
            if choice.get("finish_reason") is not None:
                terminal = event
        _require(terminal is not None, "chat SSE terminal event missing")
        timings = terminal.get("timings")
        choice = terminal["choices"][0]
        _require(isinstance(timings, Mapping), "chat SSE timings missing")
        observed = {
            "content": "".join(content),
            "reasoning_content": "".join(reasoning),
            "prompt_tokens": int(timings["prompt_n"]),
            "cached_prompt_tokens": int(timings["cache_n"]),
            "completion_tokens": int(timings["predicted_n"]),
            "finish_reason": choice["finish_reason"],
            "event_count": len(events),
        }
    else:
        content = []
        token_ids: list[int] = []
        progress: list[Mapping[str, Any]] = []
        terminal = None
        for event in events:
            if isinstance(event.get("content"), str):
                content.append(str(event["content"]))
            if isinstance(event.get("prompt_progress"), Mapping):
                progress.append(event["prompt_progress"])
            tokens = event.get("tokens")
            if isinstance(tokens, list) and "prompt_progress" not in event:
                token_ids.extend(int(item) for item in tokens)
            if event.get("stop") is True:
                terminal = event
        _require(terminal is not None and progress, "native SSE terminal evidence changed")
        timings = terminal.get("timings") if isinstance(terminal.get("timings"), Mapping) else {}
        final_progress = progress[-1]
        observed = {
            "content": "".join(content),
            "prompt_tokens": int(
                final_progress["total"]
                if "total" in final_progress
                else terminal.get("tokens_evaluated") or 0
            ),
            "cached_prompt_tokens": int(
                final_progress["cache"]
                if "cache" in final_progress
                else terminal.get("tokens_cached") or 0
            ),
            "completion_tokens": int(timings.get("predicted_n") if "predicted_n" in timings else terminal.get("tokens_predicted") or len(token_ids)),
            "generated_token_ids": token_ids,
            "generated_token_count": len(token_ids),
            "finish_reason": str(terminal.get("stop_type") or "stop"),
            "event_count": len(events),
        }
    for key, value in observed.items():
        _require(execution.get(key) == value, f"raw SSE reconstruction changed: {request_id}:{key}")
    _require(execution.get("http_status") == 200 and execution.get("terminal_stop_evidence") == {"observed": True, "stop": True}, f"terminal capture evidence changed: {request_id}")
    return {"request_id": request_id, "event_count": len(events), "raw_sse_sha256": capture["raw_response_capture"]["sha256"]}


def _carrier_records(events: Sequence[Mapping[str, Any]], live_result: Mapping[str, Any]) -> list[dict[str, Any]]:
    carrier_events = [event for event in events if event.get("state") == "carrier-operation-captured"]
    _require([event.get("request_id") for event in carrier_events] == list(probe.CARRIER_OPERATION_ORDER), "carrier operation order changed")
    records: list[dict[str, Any]] = []
    for expected_ordinal, event in enumerate(carrier_events, start=1):
        record = dict(event.get("facts", {}))
        _require(record.get("operation_ordinal") == expected_ordinal and record.get("operation_id") == probe.CARRIER_OPERATION_ORDER[expected_ordinal - 1], "carrier operation ordinal changed")
        logical = int(record.get("logical_prompt_tokens", -1))
        reused = int(record.get("reused_prompt_tokens", -1))
        fresh = int(record.get("fresh_prompt_tokens", -1))
        _require(logical > 0 and 0 <= reused <= logical and fresh == logical - reused, "carrier arithmetic changed")
        _require(record.get("completion_tokens") == 0 and record.get("fresh_prompt_plus_completion_tokens") == fresh, "carrier zero-output accounting changed")
        _require(record.get("terminal_http_status") == 200 and record.get("terminal_stop_evidence") == {"observed": True, "stop": True}, "carrier terminal evidence changed")
        kind = str(record.get("operation_kind"))
        _require(record.get("cache_prompt") is (kind == "carrier-closure-readdress") and record.get("n_predict") == 0, "carrier payload law changed")
        pair_id = str(record["pair_id"])
        report_key = "materialization" if kind == "carrier-materialization" else "closure_readdress"
        reported = live_result["checkpoint_reports"][pair_id]["carrier_operations"][report_key]
        _require({k: v for k, v in reported.items() if k != "journal_event_sha256"} == record, "carrier result/journal evidence differs")
        _require(reported.get("journal_event_sha256") == event.get("event_sha256"), "carrier journal binding changed")
        records.append(record)
    _require(len(records) == 8, "carrier operation count changed")
    return records


def _resource_summary(resources: Mapping[str, Any]) -> dict[str, int]:
    return {
        "carrier_materialization_fresh_tokens": int(resources["carrier_materialization"]["fresh_prompt_plus_completion_tokens"]),
        "catalytic_task_b_suffix_fresh_prompt_plus_completion_tokens": int(resources["catalytic_task_b_suffix"]["fresh_prompt_plus_completion_tokens"]),
        "closure_readdress_fresh_tokens": int(resources["carrier_closure_readdress"]["fresh_prompt_plus_completion_tokens"]),
        "complete_catalytic_marginal_fresh_prompt_plus_completion_tokens": int(resources["complete_catalytic_marginal"]["fresh_prompt_plus_completion_tokens"]),
        "direct_replay_fresh_prompt_plus_completion_tokens": int(resources["direct_task_b"]["fresh_prompt_plus_completion_tokens"]),
        "complete_catalytic_correct": int(resources["complete_catalytic_marginal"]["correct_answers"]),
        "direct_replay_correct": int(resources["direct_task_b"]["correct_answers"]),
        "complete_catalytic_tokens_x_direct_correct": int(resources["integer_cross_products"]["complete_catalytic_tokens_x_direct_correct"]),
        "direct_tokens_x_complete_catalytic_correct": int(resources["integer_cross_products"]["direct_tokens_x_complete_catalytic_correct"]),
    }


def validate_scientific_summary(aggregate: Mapping[str, Any], checkpoints: Mapping[str, Any], resources: Mapping[str, Any]) -> None:
    _require(dict(aggregate) == EXPECTED_AGGREGATE, "aggregate scoring changed")
    _require(dict(checkpoints) == EXPECTED_CHECKPOINTS, "checkpoint reconstruction changed")
    summary = _resource_summary(resources)
    _require(summary == EXPECTED_RESOURCE_SUMMARY, "complete resource accounting changed")
    _require(4185 + 723 == 4908 and 4908 + 528 == 5436, "resource decomposition identity changed")
    _require(5436 * 4 == 21744 and 4908 * 4 == 19632 and 21744 > 19632, "primary cross-product changed")
    _require(resources.get("complete_catalytic_fresh_tokens_per_correct_strictly_lower") is False, "complete-cycle advantage changed")
    _require(resources.get("secondary_suffix_only_diagnostic", {}).get("decision_authority") is False, "suffix-only diagnostic gained authority")


def _verified_replay(repository: Path) -> dict[str, Any]:
    paths = probe.state_paths(repository)
    expected_hashes = {"receipt": SOURCE_EVIDENCE["authority_receipt_sha256"], "manifest": SOURCE_EVIDENCE["manifest_sha256"], "journal": SOURCE_EVIDENCE["journal_sha256"], "result": SOURCE_EVIDENCE["live_result_sha256"], "closure": SOURCE_EVIDENCE["closure_sha256"]}
    for key, expected in expected_hashes.items():
        _require(_stream_sha256(paths[key]) == expected, f"Attempt-7 {key} changed")
    manifest = _json_bytes(paths["manifest"].read_bytes(), "Attempt-7 manifest")
    live_result = _json_bytes(paths["result"].read_bytes(), "Attempt-7 result")
    closure = _json_bytes(paths["closure"].read_bytes(), "Attempt-7 closure")
    with _source_probe(repository) as source:
        source_data = _verify_source_bindings(repository, source, manifest)
        root = source._load_private_root(repository)
        experiment_key = source._experiment_key(root)
        lineage_verification = _verify_lineage(repository, source, root)
        receipt = source._verify_authority_receipt_path(paths["receipt"], root, expected_attempt_id=probe.ATTEMPT_ID)
        authority = receipt.get("authority", {})
        _require(authority.get("authorized_commit") == SOURCE_COMMIT and authority.get("authority_id_sha256") == SOURCE_EVIDENCE["authority_id_sha256"], "Attempt-7 authority identity changed")
        _require(authority.get("maximum_model_generations") == 12 and authority.get("retry_allowed") is False and receipt.get("raw_authority_id_persisted") is False, "Attempt-7 authority law changed")
        _require(manifest.get("request_order") == list(probe.REQUEST_ORDER) and manifest.get("carrier_operation_order") == list(probe.CARRIER_OPERATION_ORDER), "manifest execution order changed")
        _require(manifest.get("preregistration_artifact_sha256") == SOURCE_BINDINGS["preregistration_artifact_sha256"] and manifest.get("preregistration_file_sha256") == SOURCE_BINDINGS["preregistration_file_sha256"], "manifest preregistration identity changed")
        _require(manifest.get("public_corpus_sha256") == SOURCE_BINDINGS["public_corpus_sha256"] and manifest.get("protected_evaluator_sha256") == SOURCE_BINDINGS["protected_evaluator_sha256"], "manifest corpus/evaluator identity changed")
        _require(manifest.get("maximum_model_generations") == 12 and manifest.get("retry_allowed") is False and manifest.get("raw_authority_id_persisted") is False, "manifest execution law changed")
        events = _verify_journal(paths["journal"], source, experiment_key)
        started = [event for event in events if event.get("state") == "request-started"]
        captured_events = [event for event in events if event.get("state") == "request-captured"]
        _require([event.get("request_id") for event in started] == list(probe.REQUEST_ORDER), "request start order changed")
        _require([event.get("request_id") for event in captured_events] == list(probe.REQUEST_ORDER), "request capture order changed")
        request_hashes = {str(event["request_id"]): str(event["facts"]["model_request_sha256"]) for event in started}
        _require(request_hashes == REQUEST_SHA256, "request hashes changed")
        _require(all(event["facts"].get("maximum_generations_for_request") == 1 for event in started), "one-generation request limit changed")
        carrier_records = _carrier_records(events, live_result)
        outcomes: dict[str, dict[str, Any]] = {pair_id: {} for pair_id in probe.PAIR_IDS}
        resource_records: list[dict[str, Any]] = []
        raw_replays: list[dict[str, Any]] = []
        observed_captures: dict[str, str] = {}
        for ordinal, request_id in enumerate(probe.REQUEST_ORDER, start=1):
            capture = source.verify_capture(paths[f"capture-{request_id}"], experiment_key=experiment_key, request_id=request_id, model_request_sha256=request_hashes[request_id], generation_ordinal=ordinal)
            _require(capture["capture_sha256"] == CAPTURE_SHA256[request_id], f"capture changed: {request_id}")
            _require(captured_events[ordinal - 1]["facts"].get("capture_sha256") == capture["capture_sha256"], f"journal capture binding changed: {request_id}")
            raw_replays.append(_replay_raw_sse(capture, request_id))
            resource_records.append(source.resource_record(capture, request_id))
            pair_id = request_id.rsplit("-task-", 1)[0]
            text = source.structured_content_from_capture(capture)
            if request_id.endswith("task-a"):
                outcomes[pair_id]["task_a"] = source.parse_task_a_output(text)
            elif request_id.endswith("task-b-catalytic"):
                outcomes[pair_id]["catalytic_answer"] = source.parse_task_b_output(text)
            else:
                outcomes[pair_id]["direct_answer"] = source.parse_task_b_output(text)
            observed_captures[request_id] = capture["capture_sha256"]
        _require(observed_captures == CAPTURE_SHA256, "capture inventory changed")
        _require(live_result.get("status") == "complete" and live_result.get("terminal_classification") == "INCONCLUSIVE", "source live terminal truth changed")
        _require(live_result.get("completed_model_generations") == 12 and live_result.get("completed_carrier_inference_operations") == 8 and live_result.get("retry_count") == 0, "source completion counts changed")
        _require(live_result.get("request_dispositions") == {request_id: "captured" for request_id in probe.REQUEST_ORDER}, "source request dispositions changed")
        _require(live_result.get("cleanup", {}).get("passed") is True and live_result.get("postflight", {}).get("passed") is True, "cleanup/postflight changed")
        _require(closure.get("status") == "complete" and closure.get("result_sha256") == SOURCE_EVIDENCE["live_result_sha256"] and closure.get("journal_sha256") == SOURCE_EVIDENCE["journal_sha256"] and closure.get("journal_head_sha256") == SOURCE_EVIDENCE["journal_head_sha256"] and closure.get("retry_allowed") is False, "terminal closure changed")
        checkpoints: dict[str, Any] = {}
        for pair_id in probe.PAIR_IDS:
            report = live_result["checkpoint_reports"][pair_id]
            materialization = report["carrier_operations"]["materialization"]
            closure_record = report["carrier_operations"]["closure_readdress"]
            catalytic = next(item for item in resource_records if item["request_id"] == f"{pair_id}-task-b-catalytic")
            direct = next(item for item in resource_records if item["request_id"] == f"{pair_id}-task-b-direct")
            observed = {"checkpoint_tokens": int(materialization["logical_prompt_tokens"]), "catalytic_cached_tokens": int(catalytic["reused_prompt_tokens"]), "direct_cached_tokens": int(direct["reused_prompt_tokens"]), "closure_cached_tokens": int(closure_record["reused_prompt_tokens"]), "closure_fresh_tokens": int(closure_record["fresh_prompt_tokens"])}
            _require(observed["catalytic_cached_tokens"] == observed["checkpoint_tokens"] and observed["direct_cached_tokens"] == 0, f"exact checkpoint reuse changed: {pair_id}")
            _require(observed["closure_cached_tokens"] < observed["checkpoint_tokens"] and observed["closure_fresh_tokens"] == 132, f"partial closure changed: {pair_id}")
            _require(report["reuse"].get("exact_checkpoint_reuse_observed") is True and report["closure"].get("passed") is False and report["gate_outcome"].get("continue_execution") is True, f"checkpoint adjudication surface changed: {pair_id}")
            checkpoints[pair_id] = observed
        archive = _verify_archive(repository, 7, SOURCE_EVIDENCE["archive_sha256"])
        for member in _json_bytes((archive["path"] / "bundle.json").read_bytes(), "Attempt-7 bundle")["members"]:
            source_name = str(member["source"])
            live_path = paths[source_name]
            _require(live_path.read_bytes() == (archive["path"] / str(member["path"])).read_bytes(), f"live/archive bytes differ: {member['path']}")
        scoring = source.score_protected(repository, source_data["corpus"], outcomes, completed_capture_ids=source.REQUEST_ORDER, cleanup_passed=True, postflight_passed=True)
        aggregate = {"task_a_answer_correct": int(scoring["task_a_correct"]), "task_a_latent_state_correct": int(scoring["task_a_state_correct"]), "catalytic_task_b_correct": int(scoring["catalytic_task_b_correct"]), "direct_task_b_correct": int(scoring["direct_task_b_correct"])}
        resources = source.account_resources(resource_records, carrier_records, scoring)
        validate_scientific_summary(aggregate, checkpoints, resources)
        _require(live_result.get("scoring", {}).get("task_a_correct") == aggregate["task_a_answer_correct"] and live_result.get("scoring", {}).get("task_a_state_correct") == aggregate["task_a_latent_state_correct"] and live_result.get("scoring", {}).get("catalytic_task_b_correct") == 4 and live_result.get("scoring", {}).get("direct_task_b_correct") == 4, "protected scoring replay differs from live result")
        custody = live_result["scoring"].get("protected_evaluator_custody", {})
        _require(custody.get("bytes_opened") is True and custody.get("bytes_hashed") is True and custody.get("bytes_parsed") is True and custody.get("sha256_verified") is True, "terminal evaluator custody changed")
        return {"lineage_verification": lineage_verification, "archive": {k: v for k, v in archive.items() if k != "path"}, "journal_event_count": len(events), "capture_sha256": observed_captures, "raw_sse_reconstruction_count": len(raw_replays), "request_sha256": request_hashes, "carrier_operations": carrier_records, "aggregate": aggregate, "checkpoints": checkpoints, "resources": resources, "seeds": source_data["preregistration"]["execution"]["seeds"], "fixed_request_template_sha256": source_data["preregistration"]["execution"]["fixed_request_template_sha256"]}


def render_adjudication(repository: Path) -> dict[str, Any]:
    replay = _verified_replay(repository)
    resources = replay["resources"]
    artifact = {
        "schema_version": 1,
        "adjudication_id": ADJUDICATION_ID,
        "design_id": probe.DESIGN_ID,
        "attempt_id": probe.ATTEMPT_ID,
        "status": "adjudicated",
        "attempt_lineage": ATTEMPT_LINEAGE,
        "source_execution": {"protected_commit": SOURCE_COMMIT, "status": "complete", "live_terminal_classification": "INCONCLUSIVE", "completed_model_generations": 12, "completed_carrier_inference_operations": 8, "retry_count": 0, **SOURCE_EVIDENCE, "capture_sha256": replay["capture_sha256"], "archive_evidence_member_count": replay["archive"]["evidence_member_count"], "archive_physical_file_count": replay["archive"]["physical_file_count"]},
        "bindings": {**SOURCE_BINDINGS, "request_sha256": replay["request_sha256"], "fixed_request_template_sha256": replay["fixed_request_template_sha256"], "seeds": replay["seeds"]},
        "zero_contact_reconstruction": {"source_preregistration_exact": True, "source_commit_verified": True, "authority_receipt_hmac_verified": True, "lineage_receipts_hmac_verified": 7, "lineage_archives_verified": 6, "raw_authority_id_persisted": False, "manifest_identity_verified": True, "authenticated_journal_events_verified": replay["journal_event_count"], "authenticated_captures_verified": 12, "raw_sse_reconstructions_verified": replay["raw_sse_reconstruction_count"], "carrier_operations_verified": 8, "protected_evaluator_delayed_access_verified": True, "protected_evaluator_duplicate_key_safe_parse_verified": True, "cleanup_verified": True, "postflight_verified": True, "archive_verified": True, "live_archive_equality_verified": True, "model_requests_issued": 0, "sidecar_launches": 0, "model_generations": 0, "scientific_retries": 0, "authorities_created_or_consumed": 0},
        "component_adjudication": {
            "checkpoint_reuse": {"classification": REUSE_CLASSIFICATION, "pairs": replay["checkpoints"], "replicated_pairs": 4},
            "immediate_closure": {"classification": CLOSURE_CLASSIFICATION, "partial_readdress_classification": PARTIAL_CLOSURE_CLASSIFICATION, "checkpoint_tokens": 4185, "closure_cached_tokens": 3657, "closure_fresh_tokens": 528, "fresh_tokens_per_pair": 132, "exact_closure_pairs": 0, "partial_readdress_pairs": 4},
            "task_utility": {"task_a_answer_correct": replay["aggregate"]["task_a_answer_correct"], "task_a_latent_state_correct": replay["aggregate"]["task_a_latent_state_correct"], "catalytic_task_b_correct": 4, "direct_task_b_correct": 4, "equal_task_b_accuracy": True},
            "suffix_only_efficiency": {"decision_authority": False, "catalytic_suffix_tokens_per_correct": {"numerator": 723, "denominator": 4}, "direct_replay_tokens_per_correct": {"numerator": 4908, "denominator": 4}, "strictly_lower": True},
            "complete_cycle_efficiency": {"classification": EFFICIENCY_CLASSIFICATION, "carrier_materialization_fresh_tokens": 4185, "catalytic_suffix_fresh_prompt_plus_completion_tokens": 723, "closure_readdress_fresh_tokens": 528, "complete_catalytic_tokens_per_correct": {"numerator": 5436, "denominator": 4}, "direct_replay_tokens_per_correct": {"numerator": 4908, "denominator": 4}, "arithmetic": ["4185 + 723 = 4908", "4908 + 528 = 5436"], "exact_integer_cross_products": {"complete_catalytic_tokens_x_direct_correct": 21744, "direct_tokens_x_complete_catalytic_correct": 19632}, "fresh_token_advantage": False},
        },
        "carrier_operation_evidence": replay["carrier_operations"],
        "bounded_interpretation": BOUNDED_INTERPRETATION,
        "bounded_interpretation_facts": {"reusable_process_local_execution_carrier_observed": True, "direct_replay_received_equivalent_semantic_information": True, "materialization_plus_catalytic_continuation_equaled_direct_replay_tokens": True, "measured_complete_cycle_disadvantage_tokens": 528, "measured_disadvantage_entirely_from_partial_closure": True, "exact_immediate_restoration_achieved": False, "complete_catalytic_lifecycle_established": False},
        "locked_claims": LOCKED_CLAIMS,
        "next_boundary": NEXT_BOUNDARY,
    }
    validate_disclosure_boundary(artifact)
    return artifact


def render_record(repository: Path, artifact: Mapping[str, Any] | None = None) -> dict[str, Any]:
    adjudication = dict(artifact or render_adjudication(repository))
    artifact_sha256 = probe.sha256_bytes(canonical_json_bytes(adjudication) + b"\n")
    component = adjudication["component_adjudication"]
    record = {
        "id": RECORD_ID,
        "checkpoint": "2-Catalytic-Kernel-0-HoloState-warm-trajectory-Attempt-7-forensic-adjudication",
        "hypothesis": "Process-local executable Task-A state can be exactly reused for related Task B while preserving equal utility and reducing complete single-branch fresh inference after materialization and immediate closure are counted.",
        "intervention": "Statically authenticate, reconstruct, score, and separately adjudicate immutable Attempt-7 evidence without altering its live terminal result.",
        "baseline_commit": SOURCE_COMMIT,
        "candidate_commit": None,
        "model_hash": SOURCE_BINDINGS["model_sha256"],
        "configuration": {"design_id": probe.DESIGN_ID, "attempt_id": probe.ATTEMPT_ID, "source_execution_commit": SOURCE_COMMIT, "request_count": 12, "carrier_operation_count": 8, "maximum_generations_per_request": 1, "bindings": SOURCE_BINDINGS},
        "metrics_before": {"source_live_terminal_classification": "INCONCLUSIVE", "source_live_result_immutable": True, "published_component_adjudication": False},
        "metrics_after": {"status": "adjudicated", "source_live_terminal_classification": "INCONCLUSIVE", "checkpoint_reuse_classification": REUSE_CLASSIFICATION, "closure_classification": CLOSURE_CLASSIFICATION, "partial_closure_classification": PARTIAL_CLOSURE_CLASSIFICATION, "complete_cycle_efficiency_classification": EFFICIENCY_CLASSIFICATION, "bounded_interpretation": BOUNDED_INTERPRETATION, "task_a_aggregate": {"answer_correct": 4, "latent_state_correct": 3, "total": 4}, "task_b_aggregate": {"catalytic_correct": 4, "direct_correct": 4, "total": 4}, "checkpoint_reuse": component["checkpoint_reuse"], "immediate_closure": component["immediate_closure"], "suffix_only_efficiency": component["suffix_only_efficiency"], "complete_cycle_efficiency": component["complete_cycle_efficiency"], "authority_receipt_sha256": SOURCE_EVIDENCE["authority_receipt_sha256"], "manifest_sha256": SOURCE_EVIDENCE["manifest_sha256"], "journal_sha256": SOURCE_EVIDENCE["journal_sha256"], "journal_head_sha256": SOURCE_EVIDENCE["journal_head_sha256"], "live_result_sha256": SOURCE_EVIDENCE["live_result_sha256"], "closure_sha256": SOURCE_EVIDENCE["closure_sha256"], "evidence_archive_sha256": SOURCE_EVIDENCE["archive_sha256"], "capture_sha256": adjudication["source_execution"]["capture_sha256"], "adjudication_artifact_sha256": artifact_sha256},
        "quality_gates": {"source_preregistration_exact": True, "authority_receipt_hmac_verified": True, "authenticated_journal_events": 38, "authenticated_captures": 12, "raw_sse_reconstructions": 12, "authenticated_carrier_operations": 8, "archive_evidence_members": 17, "archive_physical_files": 18, "live_archive_equality_verified": True, "protected_evaluator_delayed_access_verified": True, "protected_evaluator_duplicate_key_safe_parse_verified": True, "cleanup_and_postflight_verified": True, "live_terminal_truth_preserved": True, "no_disclosure": True, "general_catalytic_inference_locked": True, "automatic_promotion": False, "zero_contact_adjudication": True},
        "verdict": "accept-bounded-component-evidence",
        "next_boundary": NEXT_BOUNDARY,
    }
    validate_disclosure_boundary(record)
    return record


def validate_ledger_append_boundary(repository: Path) -> None:
    lines = (repository / RESULTS_PATH).read_text(encoding="utf-8").splitlines()
    _require(len(lines) == 60, "ledger no longer ends at line 60")
    last = _json_bytes(lines[-1].encode("utf-8"), "ledger predecessor")
    _require(last.get("id") == PREDECESSOR_RECORD_ID, "ledger no longer ends at neo-exp-0047")
    _require(not any(_json_bytes(line.encode("utf-8"), "ledger record").get("id") == RECORD_ID for line in lines), "neo-exp-0048 already exists")


def validate_publication(repository: Path) -> dict[str, Any]:
    artifact = render_adjudication(repository)
    artifact_bytes = canonical_json_bytes(artifact) + b"\n"
    artifact_path = repository / ARTIFACT_PATH
    _require(artifact_path.is_file() and not artifact_path.is_symlink() and artifact_path.read_bytes() == artifact_bytes, "tracked adjudication artifact differs from exact reconstruction")
    record = render_record(repository, artifact)
    expected_line = canonical_json_text(record)
    lines = (repository / RESULTS_PATH).read_text(encoding="utf-8").splitlines()
    matches = [(index, line, _json_bytes(line.encode("utf-8"), "ledger record")) for index, line in enumerate(lines, 1) if _json_bytes(line.encode("utf-8"), "ledger record").get("id") == RECORD_ID]
    _require(len(matches) == 1, "publication must contain exactly one neo-exp-0048 record")
    line_number, line, value = matches[0]
    _require(line_number == EXPECTED_LEDGER_LINE, "ledger line changed")
    _require(line == expected_line and value == record, "ledger record differs from exact render")
    return {"status": "pass", "adjudication_id": ADJUDICATION_ID, "adjudication_artifact_sha256": probe.sha256_bytes(artifact_bytes), "record_id": RECORD_ID, "ledger_line": line_number, "record_sha256": probe.sha256_bytes(expected_line.encode("utf-8")), "source_live_terminal_classification": "INCONCLUSIVE", "checkpoint_reuse_classification": REUSE_CLASSIFICATION, "closure_classification": CLOSURE_CLASSIFICATION, "complete_cycle_efficiency_classification": EFFICIENCY_CLASSIFICATION, "authenticated_journal_event_count": 38, "authenticated_capture_count": 12, "authenticated_carrier_operation_count": 8, "archive_evidence_member_count": 17, "archive_physical_file_count": 18, "model_requests_issued": 0, "sidecar_launches": 0, "model_generations": 0, "scientific_retries": 0, "authorities_created_or_consumed": 0}


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
    except (OSError, json.JSONDecodeError, subprocess.CalledProcessError, WarmTrajectoryAdjudicationError, probe.WarmTrajectoryEvaluationError) as exc:
        print(canonical_json_text({"status": "fail", "error": str(exc)}))
        return 1
    print(canonical_json_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
