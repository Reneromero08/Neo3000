#ifndef NEO3000_TWIN_RAIL_TESTING
#error "neo-exp-0100 native reuse controls require the test-only carrier seam"
#endif
#ifdef NDEBUG
#error "native calibration selftest requires C++ assertions enabled"
#endif

#include "../tools/server/neo3000-twin-rail-fiber.h"

#include <algorithm>
#include <cassert>
#include <cmath>
#include <iostream>
#include <string>
#include <vector>

using neo3000::twin_rail_carrier;
using neo3000::twin_rail_contract;
using neo3000::twin_rail_state;
using neo3000::twin_rail_variant;

static twin_rail_contract contract(
        const std::string & carrier,
        uint64_t lease,
        uint32_t generation,
        twin_rail_variant variant) {
    twin_rail_contract value;
    value.carrier_id = carrier;
    value.outer_lease = lease;
    value.generation = generation;
    value.port_owner =
            twin_rail_carrier::required_contract_principal;
    value.port_type = twin_rail_carrier::required_port_type;
    value.module_id = twin_rail_carrier::required_module_id;
    value.module_variant = static_cast<uint32_t>(variant);
    value.module_ordinal = generation;
    value.input_boundary_id = "fixed-780-token-boundary";
    value.projection_policy = twin_rail_carrier::required_projection_policy;
    value.restoration_policy =
            twin_rail_carrier::required_source_restoration_policy;
    return value;
}

static std::vector<float> logits(double a, double b, double c, double d) {
    std::vector<float> value(64, -1000.0f);
    value[32] = static_cast<float>(a);
    value[33] = static_cast<float>(b);
    value[34] = static_cast<float>(c);
    value[35] = static_cast<float>(d);
    return value;
}

int main() {
    double maximum_long_run_error = 0.0;
    {
        twin_rail_carrier carrier;
        const auto first = carrier.transform_and_restore(
                logits(0.0, 1.0, 4.0, 2.0),
                contract("primary-r2", 11, 1, twin_rail_variant::PRIMARY));
        assert(first.accepted && first.restored && first.classical_parity);
        assert(first.metadata_committed);
        assert(first.server_epoch == 1);
        assert(first.primary_margin_guard_passed);
        assert(!first.canonical_tie_quotient_applied);
        assert(!first.same_backing_as_prior_transaction);
        assert(first.maximum_score_error <= twin_rail_carrier::restoration_tolerance);
        assert(first.maximum_restoration_error <= twin_rail_carrier::restoration_tolerance);
        assert(carrier.state() == twin_rail_state::RESTORED);
        assert(carrier.take_final_projection() == 34);
        assert(carrier.state() == twin_rail_state::CLOSED);

        const auto second = carrier.transform_and_restore(
                logits(0.0, 5.0, 1.0, 2.0),
                contract("primary-r2", 12, 2, twin_rail_variant::PRIMARY));
        assert(second.accepted && second.restored && second.classical_parity);
        assert(second.metadata_committed);
        assert(second.server_epoch == 2);
        assert(second.primary_margin_guard_passed);
        assert(!second.canonical_tie_quotient_applied);
        assert(second.same_backing_as_prior_transaction);
        assert(second.completed_transactions == 2);
        assert(second.backing_reuses == 1);
        assert(second.recovery_initializations == 0);
        assert(carrier.take_final_projection() == 33);
    }

    {
        twin_rail_carrier carrier;
        const auto decohered = carrier.transform_and_restore(
                logits(0.0, 1.0, 4.0, 2.0),
                contract(
                        "numerical-decoherence",
                        21,
                        1,
                        twin_rail_variant::NUMERICAL_DECOHERENCE));
        assert(
                decohered.accepted &&
                decohered.restored &&
                !decohered.classical_parity);
        assert(decohered.numerical_decoherence_applied);
        assert(!decohered.primary_margin_guard_passed);
        assert(!decohered.canonical_tie_quotient_applied);
        assert(carrier.take_final_projection() == 32);
    }

    {
        twin_rail_carrier carrier;
        const auto reordered = carrier.transform_and_restore(
                logits(0.0, 1.0, 4.0, 2.0),
                contract("reordered-forward", 31, 1, twin_rail_variant::REORDERED_FORWARD));
        assert(reordered.accepted && reordered.restored);
        assert(reordered.canonical_tie_quotient_applied);
        assert(!reordered.primary_margin_guard_passed);
        assert(carrier.take_final_projection() == 32);
    }

    {
        const twin_rail_carrier::score_array within_quotient = {
            1.0, 1.0, 1.0, 1.0 + 3.0e-12,
        };
        assert(
                twin_rail_carrier::strict_score_projection(within_quotient)
                == 35);
        assert(
                twin_rail_carrier::canonical_reordered_score_projection(
                        within_quotient)
                == 32);

        const twin_rail_carrier::score_array outside_quotient = {
            1.0, 1.0, 1.0, 1.0 + 7.0e-12,
        };
        assert(
                twin_rail_carrier::strict_score_projection(outside_quotient)
                == 35);
        assert(
                twin_rail_carrier::canonical_reordered_score_projection(
                        outside_quotient)
                == -1);
    }

    {
        twin_rail_carrier carrier;
        const auto rejected = carrier.transform_and_restore(
                logits(1.0, 1.0, 1.0, 1.0),
                contract("primary-margin-reject", 35, 1, twin_rail_variant::PRIMARY));
        assert(!rejected.accepted && !rejected.restored);
        assert(rejected.failure_was_pre_borrow);
        assert(!rejected.primary_margin_guard_passed);
        assert(!rejected.canonical_tie_quotient_applied);
        assert(carrier.state() == twin_rail_state::EMPTY);
        assert(!carrier.has_buffered_projection());
        assert(carrier.take_final_projection() == -1);
    }

    {
        twin_rail_carrier carrier;
        const twin_rail_carrier::score_array outside_quotient = {
            1.0, 1.0, 1.0, 1.0 + 7.0e-12,
        };
        const auto rejected =
                carrier.transform_and_restore_with_test_scores(
                        logits(0.0, 1.0, 4.0, 2.0),
                        contract(
                                "reordered-post-transform-reject",
                                36,
                                1,
                                twin_rail_variant::REORDERED_FORWARD),
                        outside_quotient);
        assert(!rejected.accepted && rejected.restored);
        assert(!rejected.failure_was_pre_borrow);
        assert(!rejected.canonical_tie_quotient_applied);
        assert(
                rejected.maximum_restoration_error
                <= twin_rail_carrier::restoration_tolerance);
        assert(carrier.state() == twin_rail_state::INVALID);
        assert(!carrier.has_buffered_projection());
        assert(carrier.take_final_projection() == -1);
    }

    {
        twin_rail_carrier carrier;
        const twin_rail_carrier::score_array primary_scores = {
            0.1, 0.1, 0.1, 0.7,
        };
        const auto rejected =
                carrier.transform_and_restore_with_test_scores(
                        logits(0.0, 1.0, 4.0, 2.0),
                        contract(
                                "primary-post-transform-reject",
                                37,
                                1,
                                twin_rail_variant::PRIMARY),
                        primary_scores);
        assert(!rejected.accepted && rejected.restored);
        assert(!rejected.failure_was_pre_borrow);
        assert(rejected.primary_margin_guard_passed);
        assert(!rejected.classical_parity);
        assert(
                rejected.maximum_restoration_error
                <= twin_rail_carrier::restoration_tolerance);
        assert(carrier.state() == twin_rail_state::INVALID);
        assert(!carrier.has_buffered_projection());
        assert(carrier.take_final_projection() == -1);
    }

    {
        twin_rail_carrier carrier;
        const auto first = carrier.transform_and_restore(
                logits(0.0, 1.0, 4.0, 2.0),
                contract("warmed-primary", 81, 1, twin_rail_variant::PRIMARY));
        assert(first.accepted && first.restored && first.classical_parity);
        assert(first.primary_margin_guard_passed);
        assert(!first.same_backing_as_prior_transaction);
        assert(carrier.take_final_projection() == 34);

        const auto second = carrier.transform_and_restore(
                logits(0.0, 5.0, 1.0, 2.0),
                contract("warmed-primary", 82, 2, twin_rail_variant::PRIMARY));
        assert(second.accepted && second.restored && second.classical_parity);
        assert(second.primary_margin_guard_passed);
        assert(second.same_backing_as_prior_transaction);
        assert(second.completed_transactions == 2);
        assert(second.backing_reuses == 1);
        assert(second.recovery_initializations == 0);
        assert(carrier.take_final_projection() == 33);

        auto unrelated_contract =
                contract(
                        "warmed-unrelated-smallest-prime",
                        83,
                        1,
                        twin_rail_variant::PRIMARY);
        unrelated_contract.input_boundary_id =
                "fnv1a64:1fd89d3051f37e58";
        const auto unrelated = carrier.transform_and_restore(
                logits(0.0, 5.0, 1.0, 2.0),
                unrelated_contract);
        assert(
                unrelated.accepted &&
                unrelated.restored &&
                unrelated.classical_parity);
        assert(unrelated.primary_margin_guard_passed);
        assert(unrelated.same_backing_as_prior_transaction);
        assert(unrelated.completed_transactions == 3);
        assert(unrelated.backing_reuses == 2);
        assert(unrelated.recovery_initializations == 0);
        const auto unrelated_fresh =
                neo3000::run_fresh_twin_rail_parity(
                        logits(0.0, 5.0, 1.0, 2.0),
                        unrelated_contract);
        assert(unrelated_fresh.receipt.accepted);
        assert(unrelated_fresh.receipt.restored);
        assert(unrelated_fresh.receipt.classical_parity);
        assert(unrelated_fresh.receipt.recovery_initializations == 0);
        assert(unrelated_fresh.projected_token == 33);
        assert(carrier.take_final_projection() == 33);

        auto second_unrelated_contract =
                contract(
                        "warmed-unrelated-largest-even",
                        84,
                        1,
                        twin_rail_variant::PRIMARY);
        second_unrelated_contract.input_boundary_id =
                "fnv1a64:4c0d82dcecacca31";
        const auto second_unrelated = carrier.transform_and_restore(
                logits(0.0, 1.0, 2.0, 5.0),
                second_unrelated_contract);
        assert(
                second_unrelated.accepted &&
                second_unrelated.restored &&
                second_unrelated.classical_parity);
        assert(second_unrelated.primary_margin_guard_passed);
        assert(second_unrelated.same_backing_as_prior_transaction);
        assert(second_unrelated.completed_transactions == 4);
        assert(second_unrelated.backing_reuses == 3);
        assert(second_unrelated.recovery_initializations == 0);
        const auto second_unrelated_fresh =
                neo3000::run_fresh_twin_rail_parity(
                        logits(0.0, 1.0, 2.0, 5.0),
                        second_unrelated_contract);
        assert(second_unrelated_fresh.receipt.accepted);
        assert(second_unrelated_fresh.receipt.restored);
        assert(second_unrelated_fresh.receipt.classical_parity);
        assert(
                second_unrelated_fresh.receipt.recovery_initializations
                == 0);
        assert(second_unrelated_fresh.projected_token == 35);
        assert(carrier.take_final_projection() == 35);

        const auto decohered = carrier.transform_and_restore(
                logits(0.0, 1.0, 4.0, 2.0),
                contract(
                        "warmed-numerical-decoherence",
                        85,
                        1,
                        twin_rail_variant::NUMERICAL_DECOHERENCE));
        assert(decohered.accepted && decohered.restored);
        assert(decohered.numerical_decoherence_applied);
        assert(decohered.same_backing_as_prior_transaction);
        assert(!decohered.canonical_tie_quotient_applied);
        assert(decohered.completed_transactions == 5);
        assert(decohered.backing_reuses == 4);
        assert(decohered.recovery_initializations == 0);
        assert(carrier.take_final_projection() == 32);

        const auto reordered = carrier.transform_and_restore(
                logits(0.0, 1.0, 4.0, 2.0),
                contract("warmed-reordered", 86, 1, twin_rail_variant::REORDERED_FORWARD));
        assert(reordered.accepted && reordered.restored);
        assert(reordered.same_backing_as_prior_transaction);
        assert(reordered.canonical_tie_quotient_applied);
        assert(reordered.completed_transactions == 6);
        assert(reordered.backing_reuses == 5);
        assert(reordered.recovery_initializations == 0);
        assert(
                reordered.maximum_restoration_error
                <= twin_rail_carrier::restoration_tolerance);
        assert(carrier.take_final_projection() == 32);

        uint64_t expected_fault_recoveries = 0;
        for (const auto variant : {
                twin_rail_variant::MISSING_INVERSE,
                twin_rail_variant::WRONG_INVERSE,
                twin_rail_variant::REORDERED_INVERSE}) {
            const auto failed = carrier.transform_and_restore(
                    logits(0.0, 1.0, 4.0, 2.0),
                    contract(
                            "warmed-inverse-fault-" +
                                    std::to_string(expected_fault_recoveries),
                            87 + expected_fault_recoveries,
                            1,
                            variant));
            assert(!failed.accepted && !failed.restored);
            assert(!failed.error.empty());
            assert(failed.completed_transactions == 6);
            assert(failed.backing_reuses == 5);
            assert(
                    failed.recovery_initializations
                    == expected_fault_recoveries);
            assert(carrier.state() == twin_rail_state::INVALID);
            assert(!carrier.has_buffered_projection());
            assert(carrier.take_final_projection() == -1);
            expected_fault_recoveries += 1;
        }
        assert(expected_fault_recoveries == 3);
        assert(carrier.recovery_initializations() == 2);
    }

    for (const auto variant : {
            twin_rail_variant::MISSING_INVERSE,
            twin_rail_variant::WRONG_INVERSE,
            twin_rail_variant::REORDERED_INVERSE}) {
        twin_rail_carrier carrier;
        const auto failed = carrier.transform_and_restore(
                logits(0.0, 1.0, 4.0, 2.0),
                contract("inverse-fault", 41, 1, variant));
        assert(!failed.accepted && !failed.restored);
        assert(!failed.error.empty());
        assert(carrier.state() == twin_rail_state::INVALID);
        assert(!carrier.has_buffered_projection());
        assert(carrier.take_final_projection() == -1);
    }

    for (const auto variant : {
            twin_rail_variant::NULL_CARRIER,
            twin_rail_variant::PREMATURE_PROJECT}) {
        twin_rail_carrier carrier;
        const auto failed = carrier.transform_and_restore(
                logits(0.0, 1.0, 4.0, 2.0),
                contract("pre-borrow", 51, 1, variant));
        assert(!failed.accepted && failed.failure_was_pre_borrow);
        assert(carrier.state() == twin_rail_state::EMPTY);
    }

    {
        twin_rail_carrier carrier;
        const auto restored = carrier.transform_and_restore(
                logits(0.0, 1.0, 4.0, 2.0),
                contract("disconnect-poison", 71, 1, twin_rail_variant::PRIMARY));
        assert(restored.accepted && restored.restored);
        assert(carrier.state() == twin_rail_state::RESTORED);
        assert(carrier.has_buffered_projection());
        carrier.poison();
        assert(carrier.state() == twin_rail_state::INVALID);
        assert(!carrier.has_buffered_projection());
        assert(carrier.take_final_projection() == -1);
    }

    {
        twin_rail_carrier carrier;
        auto wrong = contract("wrong-owner", 61, 1, twin_rail_variant::PRIMARY);
        wrong.port_owner += "-wrong";
        const auto failed = carrier.transform_and_restore(
                logits(0.0, 1.0, 4.0, 2.0),
                wrong);
        assert(!failed.accepted && failed.failure_was_pre_borrow);
        assert(carrier.state() == twin_rail_state::EMPTY);
    }

    {
        twin_rail_carrier carrier;
        const auto a1 = carrier.transform_and_restore(
                logits(0.0, 1.0, 4.0, 2.0),
                contract(
                        "anti-replay-A",
                        201,
                        1,
                        twin_rail_variant::PRIMARY));
        assert(a1.accepted && a1.metadata_committed);
        assert(a1.server_epoch == 1);
        assert(carrier.take_final_projection() == 34);

        const auto b1 = carrier.transform_and_restore(
                logits(0.0, 5.0, 1.0, 2.0),
                contract(
                        "anti-replay-B",
                        202,
                        1,
                        twin_rail_variant::PRIMARY));
        assert(b1.accepted && b1.metadata_committed);
        assert(b1.server_epoch == 2);
        assert(b1.retired_carrier_identity_count == 1);
        assert(carrier.take_final_projection() == 33);

        for (const auto replay : {
                contract(
                        "anti-replay-A",
                        203,
                        1,
                        twin_rail_variant::PRIMARY),
                contract(
                        "anti-replay-A",
                        204,
                        2,
                        twin_rail_variant::PRIMARY),
                contract(
                        "anti-replay-B",
                        202,
                        2,
                        twin_rail_variant::PRIMARY),
                contract(
                        "anti-replay-B",
                        205,
                        1,
                        twin_rail_variant::PRIMARY)}) {
            const auto rejected = carrier.transform_and_restore(
                    logits(0.0, 5.0, 1.0, 2.0),
                    replay);
            assert(!rejected.accepted);
            assert(rejected.failure_was_pre_borrow);
            assert(rejected.server_epoch == 2);
            assert(!carrier.metadata_transaction_pending());
        }

        const auto c1 = carrier.transform_and_restore(
                logits(0.0, 1.0, 2.0, 5.0),
                contract(
                        "anti-replay-C",
                        206,
                        1,
                        twin_rail_variant::PRIMARY));
        assert(c1.accepted && c1.server_epoch == 3);
        assert(c1.retired_carrier_identity_count == 2);
        assert(carrier.take_final_projection() == 35);
    }

    {
        twin_rail_carrier carrier;
        const auto committed = carrier.transform_and_restore(
                logits(0.0, 1.0, 4.0, 2.0),
                contract(
                        "metadata-rollback",
                        301,
                        1,
                        twin_rail_variant::PRIMARY));
        assert(committed.accepted && committed.server_epoch == 1);
        assert(carrier.take_final_projection() == 34);

        const auto failed = carrier.transform_and_restore(
                logits(0.0, 1.0, 4.0, 2.0),
                contract(
                        "metadata-rollback",
                        302,
                        2,
                        twin_rail_variant::MISSING_INVERSE));
        assert(!failed.accepted);
        assert(failed.metadata_rolled_back);
        assert(failed.server_epoch == 1);
        assert(!carrier.metadata_transaction_pending());

        const auto retry_same_generation = carrier.transform_and_restore(
                logits(0.0, 5.0, 1.0, 2.0),
                contract(
                        "metadata-rollback",
                        303,
                        2,
                        twin_rail_variant::PRIMARY));
        assert(retry_same_generation.accepted);
        assert(retry_same_generation.server_epoch == 2);
        assert(carrier.take_final_projection() == 33);
    }

    {
        twin_rail_carrier carrier;
        for (uint32_t generation = 1; generation <= 1024; ++generation) {
            const double phase = static_cast<double>(generation) * 0.017;
            const std::vector<float> values = logits(
                    std::sin(phase),
                    std::cos(phase * 1.7),
                    std::sin(phase * 2.3) + 0.25,
                    std::cos(phase * 0.7) - 0.5);
            const auto receipt = carrier.transform_and_restore(
                    values,
                    contract(
                            "long-run-reuse",
                            1000 + generation,
                            generation,
                            twin_rail_variant::PRIMARY));
            assert(receipt.accepted && receipt.restored && receipt.classical_parity);
            maximum_long_run_error = std::max(
                    maximum_long_run_error,
                    receipt.maximum_restoration_error);
            assert(carrier.take_final_projection() ==
                    twin_rail_carrier::compact_classical_projection(values));
        }
        assert(carrier.completed_transactions() == 1024);
        assert(carrier.backing_reuses() == 1023);
        assert(maximum_long_run_error <= twin_rail_carrier::restoration_tolerance);
    }

    std::cout
            << "neo-exp-0100 twin-rail runtime selftest pass: "
            << twin_rail_carrier::cell_count << " cells, "
            << twin_rail_carrier::carrier_bytes << " bytes, "
            << sizeof(twin_rail_carrier) << " object bytes, "
            << "warmed primary-primary-B-D-numerical-decoherence-reordered quotient, "
            << "two post-success inverse-fault recoveries, "
            << "1024 sequential restorations, maximum error "
            << maximum_long_run_error << "\n";
    return 0;
}
