#ifndef NEO3000_TWIN_RAIL_TESTING
#error "neo-exp-0102 native two-evidence controls require the test-only carrier seam"
#endif

#include "../tools/server/neo3000-twin-rail-fiber.h"

#include <cassert>
#include <iostream>
#include <string>
#include <vector>

using neo3000::twin_rail_carrier;
using neo3000::twin_rail_contract;
using neo3000::twin_rail_state;
using neo3000::twin_rail_variant;

static twin_rail_contract stage_contract(
        const std::string & carrier,
        uint64_t lease,
        uint32_t generation,
        twin_rail_variant variant) {
    twin_rail_contract value;
    value.carrier_id = carrier;
    value.outer_lease = lease;
    value.generation = generation;
    value.port_owner = twin_rail_carrier::two_evidence_stage_owner;
    value.port_type = twin_rail_carrier::two_evidence_stage_type;
    value.module_id = twin_rail_carrier::two_evidence_stage_module;
    value.module_variant = static_cast<uint32_t>(variant);
    value.module_ordinal = 1;
    value.input_boundary_id =
            twin_rail_carrier::two_evidence_stage_boundary;
    value.projection_policy =
            twin_rail_carrier::two_evidence_stage_projection;
    value.restoration_policy =
            twin_rail_carrier::two_evidence_stage_restoration;
    value.causal_position =
            twin_rail_carrier::two_evidence_stage_causal_position;
    return value;
}

static twin_rail_contract final_contract(
        const twin_rail_contract & stage) {
    twin_rail_contract value = stage;
    value.port_owner = twin_rail_carrier::two_evidence_final_owner;
    value.port_type = twin_rail_carrier::two_evidence_final_type;
    value.module_id = twin_rail_carrier::two_evidence_final_module;
    value.module_ordinal = 2;
    value.input_boundary_id =
            twin_rail_carrier::two_evidence_final_boundary;
    value.projection_policy =
            twin_rail_carrier::two_evidence_final_projection;
    value.restoration_policy =
            twin_rail_carrier::two_evidence_final_restoration;
    value.causal_position =
            twin_rail_carrier::two_evidence_final_causal_position;
    return value;
}

static twin_rail_contract legacy_contract(
        const std::string & carrier,
        uint64_t lease,
        uint32_t generation) {
    twin_rail_contract value;
    value.carrier_id = carrier;
    value.outer_lease = lease;
    value.generation = generation;
    value.port_owner = twin_rail_carrier::required_port_owner;
    value.port_type = twin_rail_carrier::required_port_type;
    value.module_id = twin_rail_carrier::required_module_id;
    value.module_variant =
            static_cast<uint32_t>(twin_rail_variant::PRIMARY);
    value.module_ordinal = generation;
    value.input_boundary_id = "fnv1a64:1fd89d3051f37e58";
    value.projection_policy =
            twin_rail_carrier::required_projection_policy;
    value.restoration_policy =
            twin_rail_carrier::required_source_restoration_policy;
    return value;
}

static std::vector<float> legacy_logits(
        double a,
        double b,
        double c,
        double d) {
    std::vector<float> result(64, -1000.0f);
    result[32] = static_cast<float>(a);
    result[33] = static_cast<float>(b);
    result[34] = static_cast<float>(c);
    result[35] = static_cast<float>(d);
    return result;
}

int main() {
    static_assert(sizeof(twin_rail_carrier::evidence_array) == 16);
    const twin_rail_carrier::evidence_array first = {
        0.0f, 1.0f, 2.0f, 4.0f,
    };
    const twin_rail_carrier::evidence_array second = {
        0.0f, 1.0f, 2.0f, 5.0f,
    };

    {
        twin_rail_carrier carrier;
        const auto stage = stage_contract(
                "two-evidence-primary",
                101,
                1,
                twin_rail_variant::PRIMARY);
        const auto begun = carrier.begin_two_evidence(first, stage);
        assert(begun.accepted && !begun.restored);
        assert(begun.two_evidence_composition);
        assert(!begun.first_evidence_seed_zeroed);
        assert(begun.retained_evidence_bytes == 16);
        assert(carrier.state() == twin_rail_state::STAGE_RESIDENT);
        assert(carrier.unresolved());

        const auto finished =
                carrier.finish_two_evidence(second, final_contract(stage));
        assert(finished.accepted && finished.restored);
        assert(finished.classical_parity);
        assert(finished.primary_margin_guard_passed);
        assert(finished.maximum_score_error <=
                twin_rail_carrier::restoration_tolerance);
        assert(finished.maximum_restoration_error <=
                twin_rail_carrier::restoration_tolerance);
        assert(finished.first_evidence_seed_zeroed);
        assert(finished.retained_evidence_bytes == 16);
        assert(finished.retained_evidence_bytes_after_call == 0);
        assert(carrier.evidence_seed_is_zero());
        assert(carrier.state() == twin_rail_state::RESTORED);
        assert(carrier.take_final_projection() == 35);
        assert(carrier.state() == twin_rail_state::CLOSED);

        const auto unrelated = carrier.transform_and_restore(
                legacy_logits(0.0, 5.0, 1.0, 2.0),
                legacy_contract("post-restore-unrelated-B", 102, 1));
        assert(unrelated.accepted && unrelated.restored);
        assert(unrelated.classical_parity);
        assert(unrelated.same_backing_as_prior_transaction);
        assert(unrelated.completed_transactions == 2);
        assert(unrelated.backing_reuses == 1);
        assert(unrelated.recovery_initializations == 0);
        assert(carrier.take_final_projection() == 33);
    }

    assert(
            twin_rail_carrier::compact_two_evidence_projection(
                    first,
                    second)
            == 35);

    {
        twin_rail_carrier carrier;
        const auto stage = stage_contract(
                "two-evidence-dephased",
                301,
                1,
                twin_rail_variant::DEPHASED_SHAM);
        assert(carrier.begin_two_evidence(first, stage).accepted);
        const auto dephased =
                carrier.finish_two_evidence(second, final_contract(stage));
        assert(dephased.accepted && dephased.restored);
        assert(carrier.evidence_seed_is_zero());
        assert(carrier.take_final_projection() == 32);
    }

    {
        twin_rail_carrier carrier;
        const twin_rail_carrier::evidence_array p_prefers_a = {
            8.0f, 0.0f, 0.0f, 0.0f,
        };
        assert(
                twin_rail_carrier::compact_two_evidence_projection(
                        p_prefers_a,
                        second)
                == 32);
        const auto stage = stage_contract(
                "two-evidence-reordered",
                401,
                1,
                twin_rail_variant::REORDERED_FORWARD);
        assert(carrier.begin_two_evidence(p_prefers_a, stage).accepted);
        const auto reordered =
                carrier.finish_two_evidence(second, final_contract(stage));
        assert(reordered.accepted && reordered.restored);
        assert(reordered.maximum_score_error <=
                twin_rail_carrier::restoration_tolerance);
        assert(carrier.take_final_projection() == 35);
    }

    {
        const auto mutate = [](twin_rail_contract & value, int field) {
            switch (field) {
                case 0: value.carrier_id.clear(); break;
                case 1: value.outer_lease = 0; break;
                case 2: value.generation += 1; break;
                case 3: value.port_owner += "-wrong"; break;
                case 4: value.port_type += "-wrong"; break;
                case 5: value.module_id += "-wrong"; break;
                case 6: value.module_variant =
                        static_cast<uint32_t>(
                                twin_rail_variant::COMPACT_CLASSICAL); break;
                case 7: value.module_ordinal += 1; break;
                case 8: value.input_boundary_id += "-wrong"; break;
                case 9: value.projection_policy += "-wrong"; break;
                case 10: value.restoration_policy += "-wrong"; break;
                case 11: value.causal_position += "-wrong"; break;
                default: assert(false);
            }
        };

        for (int field = 0; field < 12; ++field) {
            twin_rail_carrier carrier;
            auto stage = stage_contract(
                    "two-evidence-stage-field-" +
                            std::to_string(field),
                    1000 + field,
                    1,
                    twin_rail_variant::PRIMARY);
            mutate(stage, field);
            const auto rejected =
                    carrier.begin_two_evidence(first, stage);
            assert(!rejected.accepted);
            assert(carrier.state() == twin_rail_state::EMPTY);
            assert(carrier.evidence_seed_is_zero());
        }

        for (int field = 0; field < 12; ++field) {
            twin_rail_carrier carrier;
            const auto stage = stage_contract(
                    "two-evidence-final-field-" +
                            std::to_string(field),
                    1100 + field,
                    1,
                    twin_rail_variant::PRIMARY);
            assert(carrier.begin_two_evidence(first, stage).accepted);
            auto final = final_contract(stage);
            mutate(final, field);
            const auto rejected =
                    carrier.finish_two_evidence(second, final);
            assert(!rejected.accepted);
            assert(carrier.state() == twin_rail_state::INVALID);
            assert(carrier.evidence_seed_is_zero());
        }
    }

    {
        twin_rail_carrier carrier;
        const auto first_stage = stage_contract(
                "two-evidence-same-carrier",
                1201,
                1,
                twin_rail_variant::PRIMARY);
        assert(carrier.begin_two_evidence(first, first_stage).accepted);
        assert(
                carrier.finish_two_evidence(
                        second,
                        final_contract(first_stage)).accepted);
        assert(carrier.take_final_projection() == 35);

        const auto second_stage = stage_contract(
                "two-evidence-same-carrier",
                1202,
                2,
                twin_rail_variant::PRIMARY);
        assert(carrier.begin_two_evidence(first, second_stage).accepted);
        const auto second_finished =
                carrier.finish_two_evidence(
                        second,
                        final_contract(second_stage));
        assert(second_finished.accepted);
        assert(second_finished.same_backing_as_prior_transaction);
        assert(second_finished.completed_transactions == 2);
        assert(second_finished.backing_reuses == 1);
        assert(carrier.take_final_projection() == 35);
    }

    for (const auto variant : {
            twin_rail_variant::MISSING_INVERSE,
            twin_rail_variant::WRONG_INVERSE,
            twin_rail_variant::REORDERED_INVERSE}) {
        twin_rail_carrier carrier;
        const auto stage = stage_contract(
                "two-evidence-inverse-fault",
                501 + static_cast<uint32_t>(variant),
                1,
                variant);
        assert(carrier.begin_two_evidence(first, stage).accepted);
        const auto failed =
                carrier.finish_two_evidence(second, final_contract(stage));
        assert(!failed.accepted && !failed.restored);
        assert(!failed.error.empty());
        assert(failed.first_evidence_seed_zeroed);
        assert(carrier.evidence_seed_is_zero());
        assert(carrier.state() == twin_rail_state::INVALID);
        assert(carrier.take_final_projection() == -1);
    }

    {
        twin_rail_carrier carrier;
        auto wrong_stage = stage_contract(
                "two-evidence-wrong-stage-owner",
                601,
                1,
                twin_rail_variant::PRIMARY);
        wrong_stage.port_owner += "-wrong";
        const auto rejected =
                carrier.begin_two_evidence(first, wrong_stage);
        assert(!rejected.accepted && rejected.failure_was_pre_borrow);
        assert(carrier.state() == twin_rail_state::EMPTY);
        assert(carrier.evidence_seed_is_zero());
    }

    {
        twin_rail_carrier carrier;
        const auto stage = stage_contract(
                "two-evidence-wrong-final-owner",
                701,
                1,
                twin_rail_variant::PRIMARY);
        assert(carrier.begin_two_evidence(first, stage).accepted);
        auto wrong_final = final_contract(stage);
        wrong_final.port_owner += "-wrong";
        const auto rejected =
                carrier.finish_two_evidence(second, wrong_final);
        assert(!rejected.accepted);
        assert(carrier.state() == twin_rail_state::INVALID);
        assert(carrier.evidence_seed_is_zero());
    }

    {
        twin_rail_carrier carrier;
        const auto stage = stage_contract(
                "two-evidence-final-before-stage",
                801,
                1,
                twin_rail_variant::PRIMARY);
        const auto rejected =
                carrier.finish_two_evidence(second, final_contract(stage));
        assert(!rejected.accepted && rejected.failure_was_pre_borrow);
        assert(carrier.state() == twin_rail_state::EMPTY);
    }

    {
        twin_rail_carrier carrier;
        const auto stage = stage_contract(
                "two-evidence-duplicate-stage",
                820,
                1,
                twin_rail_variant::PRIMARY);
        assert(carrier.begin_two_evidence(first, stage).accepted);
        const auto rejected =
                carrier.begin_two_evidence(first, stage);
        assert(!rejected.accepted);
        assert(carrier.state() == twin_rail_state::INVALID);
        assert(carrier.evidence_seed_is_zero());
    }

    {
        twin_rail_carrier carrier;
        const auto stage = stage_contract(
                "two-evidence-premature-project",
                850,
                1,
                twin_rail_variant::PRIMARY);
        assert(carrier.begin_two_evidence(first, stage).accepted);
        assert(carrier.take_final_projection() == -1);
        assert(carrier.state() == twin_rail_state::INVALID);
        assert(carrier.evidence_seed_is_zero());
    }

    {
        twin_rail_carrier carrier;
        const auto stage = stage_contract(
                "two-evidence-disconnect",
                901,
                1,
                twin_rail_variant::PRIMARY);
        assert(carrier.begin_two_evidence(first, stage).accepted);
        carrier.poison();
        assert(carrier.state() == twin_rail_state::INVALID);
        assert(carrier.evidence_seed_is_zero());
        assert(carrier.take_final_projection() == -1);
    }

    std::cout
            << "neo-exp-0102 two-evidence twin-rail selftest pass: "
            << twin_rail_carrier::cell_count << " cells, "
            << twin_rail_carrier::carrier_bytes << " cell bytes, "
            << twin_rail_carrier::retained_evidence_bytes
            << " retained evidence bytes, "
            << sizeof(twin_rail_carrier) << " object bytes, "
            << sizeof(twin_rail_contract) << " contract bytes, "
            << sizeof(neo3000::twin_rail_receipt)
            << " receipt bytes\n";
    return 0;
}
