#!/usr/bin/env python3
"""neo-exp-0078 checksum-addressed CUDA phase-root ring at R16.

This wrapper changes only the CUDA child-root lifecycle accepted structurally
by neo-exp-0077.  The exact period-four recurrence, prompt tokens, paired
direct controls, sampler schedule, checkpoint-zero runtime, and all sixteen
model transitions remain fixed.  The seed phase is saved once, the other
three phases are cold-filled once, and later transitions restore the already
proven checksum-addressed CUDA phase root without another rebase.
"""
from __future__ import annotations

import catalytic_frontier_fixed_size_rebase as fixed_size
import catalytic_frontier_reversible_period4 as period4


EXPERIMENT_ID = "neo-exp-0078"
MINIMUM_FULLY_COUNTED_WALL_SPEEDUP = 3.5
MAXIMUM_CATALYTIC_WALL_SECONDS = 61.715325
MAXIMUM_ROOT_AND_REBASE_WALL_SECONDS = 21.107325
MAXIMUM_RING_OVERHEAD_SECONDS = 3.0
ROOT_BANK_CAPACITY = 5
EXPECTED_PHASE_COLD_FILLS = 3
EXPECTED_PHASE_RING_HITS = 13
EXPECTED_POST_FILL_DEVICE_BYTES = (
    4 * fixed_size.EXPECTED_CHILD_DEVICE_BYTES
)
EXPECTED_CHARGED_AVOIDED_FRESH_PROMPT_TOKENS = (
    EXPECTED_PHASE_COLD_FILLS * fixed_size.EXPECTED_BASE_TOKENS
    + EXPECTED_PHASE_RING_HITS * fixed_size.EXPECTED_CHILD_TOKENS
)
EXPECTED_CUDA_RUNTIME_SHA256 = (
    ("ggml-base.dll", "F648098AB0FCECA45A1EEC2AE147022383DCC6CD31392199F5CD6E5A5277AF3F"),
    ("ggml-cpu.dll", "64B9D97113CC0AB57C8DA0E3237B4EFC0271B4E0AA377080295D138BCABC92A1"),
    ("ggml-cuda.dll", "C4BCC1C7AF82475E1C1CD3A56C3AF9CDA3EE50AE8C7819D9A314C6B6F62DC787"),
    ("ggml.dll", "6E6A8BE1DAFA42356C15DDA9C0A39CC7BA34E4ABA8D402693F0EFCB57CD9E2D1"),
    ("llama-common.dll", "DA143877D73FE09575F6FD48458358A8D09369102FEE17C599CC781ED2CAF0CF"),
    ("llama-server-impl.dll", "4A56DB231DF97F1B93E06DFB4A0ED2FE1590278B23E596FCB352C8B242461785"),
    ("llama-server.exe", "5D795CEB1BD57DC688E55DB0D6EC421F5F0497E0E2597DDD823773D90DBCCE36"),
    ("llama.dll", "E22AD97978A6E88F4D4D1D0E26DD43216BE8F05EB6C39F5D96199B286A56F08B"),
    ("mtmd.dll", "61B837FC6C8160602EFE3E6831CB9794F51E7BF64BFD06762F8406629D0291A2"),
)


CONTRACT = fixed_size.validate_contract(
    fixed_size.RecurrenceContract(
        experiment_id=EXPERIMENT_ID,
        recurrence_id="reversible-period4-phase-root-ring",
        recursive_depth=period4.RECURSIVE_DEPTH,
        transition=period4.TRANSITION,
        transition_content=period4.TRANSITION_CONTENT,
        expected_state_sequence=period4.EXPECTED_STATE_SEQUENCE,
        accepted_classification=(
            "checksum-addressed-cuda-phase-root-ring-r16-"
            "reversible-period4-supported-bounded"
        ),
        next_boundary=(
            "PRESERVE_PHASE_ROOT_RING_R16_AND_ADVANCE_THE_NEXT_FAST_"
            "RECURSIVE_CATALYTIC_BOUNDARY"
        ),
        claim_ceiling=(
            "exact checksum-addressed CUDA phase-root reuse for the bounded "
            "four-state reversible recurrence through R=16; not arbitrary-state "
            "semantics, arbitrary-history compaction, or unbounded inference"
        ),
        minimum_wall_speedup=MINIMUM_FULLY_COUNTED_WALL_SPEEDUP,
        maximum_catalytic_wall_seconds=MAXIMUM_CATALYTIC_WALL_SECONDS,
        exact_cycle_period=4,
        expected_base_branch_sha256=period4.EXPECTED_BASE_BRANCH_SHA256,
        expected_suffix_token_count=period4.EXPECTED_SUFFIX_TOKEN_COUNT,
        expected_suffix_sha256=period4.EXPECTED_SUFFIX_SHA256,
        expected_generated_sha256=period4.EXPECTED_GENERATED_SHA256,
        expected_child_sha256=period4.EXPECTED_CHILD_SHA256,
        expected_request_sha256=period4.EXPECTED_REQUEST_SHA256,
        root_bank_capacity=ROOT_BANK_CAPACITY,
        phase_root_ring=True,
        maximum_root_and_rebase_wall_seconds=(
            MAXIMUM_ROOT_AND_REBASE_WALL_SECONDS
        ),
        maximum_ring_overhead_seconds=MAXIMUM_RING_OVERHEAD_SECONDS,
        expected_cuda_runtime_sha256=EXPECTED_CUDA_RUNTIME_SHA256,
    )
)


def main() -> int:
    return fixed_size.main(contract=CONTRACT)


if __name__ == "__main__":
    raise SystemExit(main())
