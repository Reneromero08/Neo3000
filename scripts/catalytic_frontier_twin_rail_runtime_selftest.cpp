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
    value.port_owner = twin_rail_carrier::required_port_owner;
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
        assert(second.same_backing_as_prior_transaction);
        assert(second.completed_transactions == 2);
        assert(second.backing_reuses == 1);
        assert(carrier.take_final_projection() == 33);
    }

    {
        twin_rail_carrier carrier;
        const auto sham = carrier.transform_and_restore(
                logits(0.0, 1.0, 4.0, 2.0),
                contract("dephased", 21, 1, twin_rail_variant::DEPHASED_SHAM));
        assert(sham.accepted && sham.restored && !sham.classical_parity);
        assert(carrier.take_final_projection() == 32);
    }

    {
        twin_rail_carrier carrier;
        const auto reordered = carrier.transform_and_restore(
                logits(0.0, 1.0, 4.0, 2.0),
                contract("reordered-forward", 31, 1, twin_rail_variant::REORDERED_FORWARD));
        assert(reordered.accepted && reordered.restored);
        assert(carrier.take_final_projection() == 32);
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
            << "neo-exp-0094 twin-rail runtime selftest pass: "
            << twin_rail_carrier::cell_count << " cells, "
            << twin_rail_carrier::carrier_bytes << " bytes, "
            << sizeof(twin_rail_carrier) << " object bytes, "
            << "1024 sequential restorations, maximum error "
            << maximum_long_run_error << "\n";
    return 0;
}
