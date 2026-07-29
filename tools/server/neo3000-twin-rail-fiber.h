#pragma once

#include <array>
#include <complex>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace neo3000 {

enum class twin_rail_state : uint8_t {
    EMPTY,
    INITIALIZED,
    BORROWED,
    STAGE_RESIDENT,
    COMPOSING,
    RESTORING,
    RESTORED,
    FINAL_PROJECTED,
    CLOSED,
    INVALID,
};

enum class twin_rail_variant : uint32_t {
    PRIMARY           = 0,
    DEPHASED_SHAM     = 1,
    REORDERED_FORWARD = 2,
    MISSING_INVERSE   = 3,
    WRONG_INVERSE     = 4,
    REORDERED_INVERSE = 5,
    NULL_CARRIER      = 6,
    PREMATURE_PROJECT = 7,
    COMPACT_CLASSICAL = 8,
};

struct twin_rail_contract {
    std::string carrier_id;
    uint64_t outer_lease = 0;
    uint32_t generation = 0;
    std::string port_owner;
    std::string port_type;
    std::string module_id;
    uint32_t module_variant = 0;
    uint32_t module_ordinal = 0;
    std::string input_boundary_id;
    std::string projection_policy;
    std::string restoration_policy;
};

struct twin_rail_receipt {
    bool accepted = false;
    bool restored = false;
    bool classical_parity = false;
    bool same_backing_as_prior_transaction = false;
    bool failure_was_pre_borrow = false;
    uint64_t completed_transactions = 0;
    uint64_t backing_reuses = 0;
    uint64_t recovery_initializations = 0;
    size_t persistent_object_bytes = 0;
    size_t persistent_dynamic_capacity_bytes = 0;
    double maximum_score_error = 0.0;
    double maximum_restoration_error = 0.0;
    twin_rail_state state = twin_rail_state::EMPTY;
    std::string error;
};

struct twin_rail_fresh_parity_result {
    twin_rail_receipt receipt;
    int32_t projected_token = -1;
};

class twin_rail_carrier {
public:
    static constexpr std::array<int32_t, 4> candidate_token_ids = {32, 33, 34, 35};
    static constexpr size_t hypothesis_count = candidate_token_ids.size();
    static constexpr size_t cell_count = hypothesis_count * 2;
    static constexpr size_t carrier_bytes = cell_count * sizeof(std::complex<double>);
    static constexpr double restoration_tolerance = 1.0e-12;

    static constexpr const char * required_port_owner =
            "neo-exp-0094-four-choice-phase-consumer";
    static constexpr const char * required_port_type =
            "agents-a1-four-choice-logits-to-twinrail-v1";
    static constexpr const char * required_module_id =
            "terminal-softmax-twinrail-hadamard-v1";
    static constexpr const char * required_projection_policy =
            "FINAL_SINGLE_HYPOTHESIS_TOKEN_AFTER_RESTORATION";
    static constexpr const char * required_source_restoration_policy =
            "DECLARED_CLOSURE";

    twin_rail_receipt transform_and_restore(
            const std::vector<float> & terminal_logits,
            const twin_rail_contract & contract);

    static int32_t compact_classical_projection(
            const std::vector<float> & terminal_logits);

    int32_t take_final_projection();
    void poison();

    twin_rail_state state() const;
    bool unresolved() const;
    bool has_buffered_projection() const;
    uint64_t completed_transactions() const;
    uint64_t backing_reuses() const;
    uint64_t recovery_initializations() const;
    size_t persistent_object_bytes() const;
    size_t persistent_dynamic_capacity_bytes() const;

private:
    using cell_array = std::array<std::complex<double>, cell_count>;
    using scalar_array = std::array<double, hypothesis_count>;

    static std::complex<double> expected_cell(size_t index);
    static scalar_array probabilities_from_logits(const std::vector<float> & terminal_logits);
    static scalar_array angles_from_probabilities(const scalar_array & probabilities);
    static size_t lowest_argmax(const scalar_array & values);

    void initialize();
    double restoration_error() const;
    bool contract_is_structurally_valid(const twin_rail_contract & contract) const;
    bool ownership_transition_is_valid(const twin_rail_contract & contract) const;
    void bind_ownership(const twin_rail_contract & contract);
    void apply_phase(const scalar_array & angles, bool inverse);
    void apply_hadamard();

    cell_array cells_ = {};
    twin_rail_state state_ = twin_rail_state::EMPTY;
    int32_t buffered_token_ = -1;

    std::string bound_carrier_id_;
    std::string bound_port_owner_;
    std::string bound_port_type_;
    std::string bound_module_id_;
    uint64_t last_outer_lease_ = 0;
    uint32_t last_generation_ = 0;
    uint32_t last_module_ordinal_ = 0;

    uintptr_t prior_backing_address_ = 0;
    uint64_t completed_transactions_ = 0;
    uint64_t backing_reuses_ = 0;
    uint64_t recovery_initializations_ = 0;
};

twin_rail_fresh_parity_result run_fresh_twin_rail_parity(
        const std::vector<float> & terminal_logits,
        const twin_rail_contract & contract);

} // namespace neo3000
