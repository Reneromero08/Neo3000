#!/usr/bin/env python3
"""neo-exp-0077 reversible period-four fixed-size CUDA recurrence.

This wrapper changes only the transition law accepted by neo-exp-0076.  The
689-token immutable host base, 695-token replaceable CUDA child, paired direct
controls, sampler schedule, checkpoint-zero runtime, and lifecycle accounting
remain fixed while the state follows A -> B -> C -> D -> A for 16 edges.
"""
from __future__ import annotations

import base64
import json
import zlib
from typing import Sequence

import catalytic_frontier_fixed_size_rebase as fixed_size


EXPERIMENT_ID = "neo-exp-0077"
RECURSIVE_DEPTH = 16
TRANSITION = (("A", "B"), ("B", "C"), ("C", "D"), ("D", "A"))
TRANSITION_CONTENT = (
    "RECURSIVE CATALYTIC STEP\n"
    "Treat the exact JSON answer in the immediately preceding assistant message as the sole input state. "
    "Apply exactly one transition from this table: A -> B; B -> C; C -> D; D -> A. "
    "Return only JSON of the form {\"answer\":\"A\"}, with the transitioned letter and no other text."
)
MINIMUM_FULLY_COUNTED_WALL_SPEEDUP = 3.5
MAXIMUM_CATALYTIC_WALL_SECONDS = 61.715325
EXPECTED_BASE_BRANCH_SHA256 = "A454640FCAE18925F9A4B54672C0A1F681721E9CF72BC19220C940E64B629B12"
BASE_BRANCH_TOKEN_IDS_ZLIB_B64 = (
    "eNqdVkm2JDkIu5AXZvDAWer1/a9REjiGzN9/U6uMtDEGIYT/qO/uo+25dpPYLcJXEzFtuqLJXGJtLJWGX7Mubc4tbQX3zHbzMWeT"
    "sWZz79jkoaHwJfjyvlceFOvw3rVNt1EuNNxwh8w2xoTZXjFpq7jcy9hgZoPhNJf8sSH5D3e6eLruw9tQfE9FdMOjLJf4bbpCO2KY"
    "Whcw45nJXsmfvwZTLLXYXmDomK4teiD6PhW3zcAhwUU6vU2J0VQViFm3XNKQaGsZcBLL61y3KsJAUgYYz9+lgAEweV8aCXX5UfMR"
    "PDamtD1EAX6HI107JO3K797y+MzjeVBn/dlfB9P+MctAGAIvCiKo0lebKBfWdAGucH0dmAGAO1DBHgDjhsMBgFfkLv25lSVhyTQG"
    "7GJJ5ZmGt5HDnTtzdtaEiKBUvMT1VfsliiIbYB2zd+yBZQxdSDWiDV8d55V8G7IrJ1j4+oAwHQI2xAVMRl1P8CbdMqpwv0581EF2"
    "ZCQbltUVoiR9Ig8uABMmuxj1gfRZXlPpotJOJJI+KiS6VOXymgxKhlkCXRhOUtCUrSBg3FWb03q1YX2/vR+fNHDjGR1ElgZvoC5K"
    "LkVyskFV77EKXbbHDlwfPrG0kcAD/QXp4ysNntO8ncW2/oHWXi7l2igrIBeCZfIImYV7wfkDyLNws/yGccuyZMykT+ksJNsUMW4z"
    "nJn4NxDodZ8+951EBOFE5SDgxskSxF3vVrmj+CV+OiYVPVVrc2uCnncKFwsYa7rtSUYWcPpiMahTFCtDgW2xm/LSQAIzQgvWuVPl"
    "hq3Tl+Ik62abxu5fYcVJE6o1qJEz1nP566hDlyeoIuiAXTkk1DQb4BC7w9ZvxSMyb/4tdpibyN1+xUNyovhCDH66SAH5Wla9G/LV"
    "IzKxQHSi274MokMlBgdPt36IhHm2qvnPQeqclvpAEfVpQNmjuu50IUq6rc9LyBITHYNVppQMCD0LsZdgYuYUWFTEYBIrJfe4ToFz"
    "7Rc610kwcyfwpQRVPcpv9Um2sE7gz05NVuWcBNFHHHHlaFLo2ZnBarpHjV2ML8wzPdly5Vbnl67lNMZWYgwfWtTMXGsuLAy7HXtU"
    "1nN7DY3shKc5Eq0XAY6+pG/LL50we4ZfNcVgFyZCxDaRQzfDlaGs76odVwkBWmaeOXqpwg4Oct5fk+KWweVXB1IBsruK+eQ8yb79"
    "FP2DXPVo+c7xBFGy0eMtDoLXxmv2kXmssEFT8kVgc8ZVvuFqr4eVbb5h7sfT/75LkMYY98Lc6Sc/Iz+jHypAMVh7Ww65AWviPF+m"
    "1oaThvX+CjYWM+RYfaD2vb6OaPbhmcTQoaNkKak3lt/HUHXkbvpjhpM7iqL/mNPfHkRYMV9orqpKze4uZzQ+/Xnnjra3+EBic54T"
    "iYzJjy26/ve3X3VXPjOvV3C9cpK6zgKiFSDZyCk77RpJkIFdL2QiSimFITvIh9+P5qx7VtvEDwEgVYPBZLBGLIhbW2MW41w46fke"
    "Ten4HuMc3J99jLd03JP66UE8qfr4XC9N6VSNj/VxPz3Aa/8nUv73FwFfa58="
)
EXPECTED_SUFFIX_TOKEN_COUNT = 87
EXPECTED_SUFFIX_SHA256 = "B8FE7714DBCD04BE2F3D197D522783F959436278FB1CE7E246CCC78ED02454C1"
EXPECTED_SUFFIX_TOKEN_IDS = (
    248046,
    198,
    248045,
    846,
    198,
    762,
    37508,
    50,
    6334,
    351,
    29090,
    75658,
    1271,
    46744,
    198,
    51,
    1180,
    279,
    4581,
    4566,
    4087,
    303,
    279,
    6849,
    36497,
    17313,
    1876,
    430,
    279,
    12924,
    1879,
    1528,
    13,
    19927,
    6681,
    799,
    8869,
    494,
    411,
    1898,
    25,
    357,
    1411,
    417,
    26,
    417,
    1411,
    351,
    26,
    351,
    1411,
    414,
    26,
    414,
    1411,
    357,
    13,
    3301,
    1132,
    4566,
    314,
    279,
    1304,
    5046,
    8944,
    3147,
    32,
    13933,
    440,
    279,
    8869,
    290,
    6321,
    321,
    874,
    975,
    1414,
    13,
    248046,
    198,
    248045,
    74455,
    198,
    248068,
    271,
    248069,
    271,
)
VISIBLE_TOKEN_IDS = {
    "A": (4754, 8944, 3147, 32, 8934),
    "B": (4754, 8944, 3147, 33, 8934),
    "C": (4754, 8944, 3147, 34, 8934),
    "D": (4754, 8944, 3147, 35, 8934),
}
TERMINAL_EOS_ID = 248046
EXPECTED_GENERATED_SHA256 = (
    ("A", "5EEBE0B0798EFA8628F18A581010743AC0E7D09BD58379E10E59B9798F149C28"),
    ("B", "4553BBC00B6AF27C3EBDE8F36EA9237A37B5D9C1AA182FBC65CDA71411A4B888"),
    ("C", "BD33E852EF9FDDEE49A1056501456071169FF3E3C7699C2A5BAAA2D0DF30CABC"),
    ("D", "0CA13167369ED1835BB8938644A7CCEF6EDE0BD65AE31C256931C54D3FA9FB31"),
)
EXPECTED_CHILD_SHA256 = (
    ("A", "8E7AF2646E3C1A2E046370A854D8C95BDA45BDBA986CC678BC698CF6BC93B1BA"),
    ("B", "D636ABA44A0F7DA74C1CA03CD2D0B064D6A2469FA6EBB0BC8F42A0CE9426DEB8"),
    ("C", "1F956F9C177106F0775B3DAA054CA7BF046F980277C8E2CE6029AD78C7E90395"),
    ("D", "5AC4DD8C73E3D4958F9A93C3A9D78B05C0C6C4E6D17A06DA7CF8C72E10FA495B"),
)
EXPECTED_REQUEST_SHA256 = (
    ("A", "7C0F6DE4AE0031C8E952FE2305454088A0CBBC397106B47B582D4285EE40AD2B"),
    ("B", "3480B95753BC8994898ED805E263B18B1295D4FD2962C73E2705590ADA5BA865"),
    ("C", "10EFFFE76C32FA8A84D9F3185C370D9D92DF6F22C118CEF720B6FD8A2630F5DE"),
    ("D", "39C249CBE523F60247D2C0668E9854EACE6C6625C00BB13B3ABF6C1A9D9DC492"),
)


def transition_map() -> dict[str, str]:
    return dict(TRANSITION)


def expected_state_sequence() -> tuple[str, ...]:
    transition = transition_map()
    states = [fixed_size.fixed.SEED_EXPECTED_ANSWER]
    for _unused in range(RECURSIVE_DEPTH):
        states.append(transition[states[-1]])
    return tuple(states)


EXPECTED_STATE_SEQUENCE = expected_state_sequence()


def _canonical_token_sha256(tokens: Sequence[int]) -> str:
    return fixed_size.harness.sha256_bytes(
        fixed_size.harness.carrier.canonical_json_bytes(list(tokens))
    )


def base_branch_token_ids() -> tuple[int, ...]:
    encoded = base64.b64decode(BASE_BRANCH_TOKEN_IDS_ZLIB_B64, validate=True)
    decoded = json.loads(zlib.decompress(encoded))
    fixed_size.require(
        isinstance(decoded, list) and all(type(item) is int for item in decoded),
        "period-four base token binding is malformed",
    )
    return tuple(decoded)


BASE_BRANCH_TOKEN_IDS = base_branch_token_ids()


def validate_static_binding() -> None:
    fixed_size.require(
        len(BASE_BRANCH_TOKEN_IDS) == fixed_size.EXPECTED_COMPLETE_BRANCH_TOKENS,
        "period-four base branch token count changed",
    )
    fixed_size.require(
        _canonical_token_sha256(BASE_BRANCH_TOKEN_IDS) == EXPECTED_BASE_BRANCH_SHA256,
        "period-four base branch token hash changed",
    )
    fixed_size.require(
        len(EXPECTED_SUFFIX_TOKEN_IDS) == EXPECTED_SUFFIX_TOKEN_COUNT,
        "period-four suffix token count changed",
    )
    fixed_size.require(
        _canonical_token_sha256(EXPECTED_SUFFIX_TOKEN_IDS) == EXPECTED_SUFFIX_SHA256,
        "period-four suffix token hash changed",
    )
    expected_generated = dict(EXPECTED_GENERATED_SHA256)
    expected_child = dict(EXPECTED_CHILD_SHA256)
    expected_request = dict(EXPECTED_REQUEST_SHA256)
    for answer, visible in VISIBLE_TOKEN_IDS.items():
        fixed_size.require(
            _canonical_token_sha256((*visible, TERMINAL_EOS_ID))
            == expected_generated[answer],
            f"period-four generated hash changed for {answer}",
        )
        child = (*BASE_BRANCH_TOKEN_IDS, *visible)
        fixed_size.require(
            len(child) == fixed_size.EXPECTED_CHILD_TOKENS,
            f"period-four child count changed for {answer}",
        )
        fixed_size.require(
            _canonical_token_sha256(child) == expected_child[answer],
            f"period-four child hash changed for {answer}",
        )
        request = (*child, *EXPECTED_SUFFIX_TOKEN_IDS)
        fixed_size.require(
            len(request) == fixed_size.EXPECTED_DIRECT_FRESH_TOKENS,
            f"period-four request count changed for {answer}",
        )
        fixed_size.require(
            _canonical_token_sha256(request) == expected_request[answer],
            f"period-four request hash changed for {answer}",
        )
    fixed_size.require(
        EXPECTED_STATE_SEQUENCE
        == ("C", "D", "A", "B", "C", "D", "A", "B", "C", "D", "A", "B", "C", "D", "A", "B", "C"),
        "period-four R16 sequence changed",
    )


validate_static_binding()

CONTRACT = fixed_size.validate_contract(
    fixed_size.RecurrenceContract(
        experiment_id=EXPERIMENT_ID,
        recurrence_id="reversible-period4",
        recursive_depth=RECURSIVE_DEPTH,
        transition=TRANSITION,
        transition_content=TRANSITION_CONTENT,
        expected_state_sequence=EXPECTED_STATE_SEQUENCE,
        accepted_classification=(
            "pinned-base-fixed-output-cuda-capsule-rebase-r16-"
            "reversible-period4-supported-bounded"
        ),
        next_boundary=(
            "PRESERVE_REVERSIBLE_PERIOD4_R16_AND_DESIGN_THE_NEXT_FAST_"
            "CATALYTIC_LONG_HORIZON_BOUNDARY"
        ),
        claim_ceiling=(
            "exact fixed-size reversible period-four recurrence through R=16 "
            "with four changing states; not arbitrary-state semantics, "
            "arbitrary-history compaction, or unbounded inference"
        ),
        minimum_wall_speedup=MINIMUM_FULLY_COUNTED_WALL_SPEEDUP,
        maximum_catalytic_wall_seconds=MAXIMUM_CATALYTIC_WALL_SECONDS,
        exact_cycle_period=4,
        expected_base_branch_sha256=EXPECTED_BASE_BRANCH_SHA256,
        expected_suffix_token_count=EXPECTED_SUFFIX_TOKEN_COUNT,
        expected_suffix_sha256=EXPECTED_SUFFIX_SHA256,
        expected_generated_sha256=EXPECTED_GENERATED_SHA256,
        expected_child_sha256=EXPECTED_CHILD_SHA256,
        expected_request_sha256=EXPECTED_REQUEST_SHA256,
    )
)


def main() -> int:
    return fixed_size.main(contract=CONTRACT)


if __name__ == "__main__":
    raise SystemExit(main())
