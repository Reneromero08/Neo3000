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
    PRIMARY                = 0,
    NUMERICAL_DECOHERENCE  = 1,
    // Historical evidence uses numeric variant 1 and the old name. Keep the
    // parser alias while active code uses the corrected classification.
    DEPHASED_SHAM          = NUMERICAL_DECOHERENCE,
    REORDERED_FORWARD      = 2,
    MISSING_INVERSE        = 3,
    WRONG_INVERSE          = 4,
    REORDERED_INVERSE      = 5,
    NULL_CARRIER           = 6,
    PREMATURE_PROJECT      = 7,
    COMPACT_CLASSICAL      = 8,
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
    std::string causal_position;
};

struct twin_rail_receipt {
    bool accepted = false;
    bool restored = false;
    bool classical_parity = false;
    bool canonical_tie_quotient_applied = false;
    bool primary_margin_guard_passed = false;
    bool same_backing_as_prior_transaction = false;
    bool failure_was_pre_borrow = false;
    bool two_evidence_composition = false;
    bool first_evidence_seed_zeroed = true;
    bool numerical_decoherence_applied = false;
    bool metadata_committed = false;
    bool metadata_rolled_back = false;
    uint64_t completed_transactions = 0;
    uint64_t backing_reuses = 0;
    uint64_t recovery_initializations = 0;
    uint64_t server_epoch = 0;
    size_t persistent_object_bytes = 0;
    size_t persistent_dynamic_capacity_bytes = 0;
    size_t retired_carrier_identity_count = 0;
    size_t retained_evidence_bytes = 0;
    size_t retained_evidence_bytes_after_call = 0;
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
    static constexpr const char * backend_classification =
            "REVERSIBLE_TWIN_RAIL_CALIBRATION_BACKEND";
    static constexpr std::array<int32_t, 4> candidate_token_ids = {32, 33, 34, 35};
    static constexpr size_t hypothesis_count = candidate_token_ids.size();
    using score_array = std::array<double, hypothesis_count>;
    using evidence_array = std::array<float, hypothesis_count>;
    static constexpr size_t cell_count = hypothesis_count * 2;
    static constexpr size_t carrier_bytes = cell_count * sizeof(std::complex<double>);
    static constexpr double restoration_tolerance = 1.0e-12;
    static constexpr double primary_minimum_top_two_margin = 2.0e-12;
    static constexpr double reordered_score_spread_tolerance = 6.0e-12;
    static constexpr size_t retired_identity_capacity = 64;

    static constexpr const char * required_contract_principal =
            "neo-exp-0094-four-choice-phase-consumer";
    // Compatibility aliases for the historical JSON field name. These values
    // are public structural contracts, not authenticated ownership.
    static constexpr const char * required_port_owner =
            required_contract_principal;
    static constexpr const char * required_port_type =
            "agents-a1-four-choice-logits-to-twinrail-v1";
    static constexpr const char * required_module_id =
            "terminal-softmax-twinrail-hadamard-v1";
    static constexpr const char * required_projection_policy =
            "FINAL_SINGLE_HYPOTHESIS_TOKEN_AFTER_RESTORATION";
    static constexpr const char * required_source_restoration_policy =
            "DECLARED_CLOSURE";
    static constexpr const char * two_evidence_stage_principal =
            "dual-evidence-stage-owner-v1";
    static constexpr const char * two_evidence_stage_owner =
            two_evidence_stage_principal;
    static constexpr const char * two_evidence_stage_type =
            "live-candidate-logits-row";
    static constexpr const char * two_evidence_stage_module =
            "Ry";
    static constexpr const char * two_evidence_stage_boundary =
            "fnv1a64:4c0d82dcecacca31";
    static constexpr const char * two_evidence_stage_projection =
            "forbidden";
    static constexpr const char * two_evidence_stage_restoration =
            "deferred to final port";
    static constexpr const char * two_evidence_stage_causal_position =
            "FIRST_OF_TWO";
    static constexpr const char * two_evidence_final_principal =
            "dual-evidence-final-owner-v1";
    static constexpr const char * two_evidence_final_owner =
            two_evidence_final_principal;
    static constexpr const char * two_evidence_final_type =
            "live-candidate-logits-row";
    static constexpr const char * two_evidence_final_module =
            "Rx";
    static constexpr const char * two_evidence_final_boundary =
            "fnv1a64:007c44f04d25fd72";
    static constexpr const char * two_evidence_final_projection =
            "final-only-after-restoration";
    static constexpr const char * two_evidence_final_restoration =
            "reverse public descriptors G,F,H";
    static constexpr const char * two_evidence_final_causal_position =
            "SECOND_OF_TWO";
    static constexpr size_t retained_evidence_bytes =
            hypothesis_count * sizeof(float);

    twin_rail_receipt transform_and_restore(
            const std::vector<float> & terminal_logits,
            const twin_rail_contract & contract);
    twin_rail_receipt begin_two_evidence(
            const evidence_array & first_logits,
            const twin_rail_contract & stage_contract);
    twin_rail_receipt finish_two_evidence(
            const evidence_array & second_logits,
            const twin_rail_contract & final_contract);
#ifdef NEO3000_TWIN_RAIL_TESTING
    twin_rail_receipt transform_and_restore_with_test_scores(
            const std::vector<float> & terminal_logits,
            const twin_rail_contract & contract,
            const score_array & forced_scores);
#endif

    static int32_t compact_classical_projection(
            const std::vector<float> & terminal_logits);
    static int32_t compact_two_evidence_projection(
            const evidence_array & first_logits,
            const evidence_array & second_logits);
    static int32_t strict_score_projection(const score_array & scores);
    static int32_t canonical_reordered_score_projection(
            const score_array & scores);

    int32_t take_final_projection();
    void poison();

    twin_rail_state state() const;
    bool unresolved() const;
    bool has_buffered_projection() const;
    bool evidence_seed_is_zero() const;
    uint64_t completed_transactions() const;
    uint64_t backing_reuses() const;
    uint64_t recovery_initializations() const;
    uint64_t server_epoch() const;
    size_t retired_carrier_identity_count() const;
    bool metadata_transaction_pending() const;
    size_t persistent_object_bytes() const;
    size_t persistent_dynamic_capacity_bytes() const;

private:
    using cell_array = std::array<std::complex<double>, cell_count>;
    using scalar_array = score_array;
    using density_lane = std::array<std::complex<double>, 4>;
    using density_array = std::array<density_lane, hypothesis_count>;

    struct contract_metadata {
        std::string carrier_id;
        std::string port_principal;
        std::string port_type;
        std::string module_id;
        uint64_t outer_lease = 0;
        uint32_t generation = 0;
        uint32_t module_ordinal = 0;
        uint32_t module_variant = 0;

        bool empty() const {
            return carrier_id.empty();
        }

        void clear() {
            carrier_id.clear();
            port_principal.clear();
            port_type.clear();
            module_id.clear();
            outer_lease = 0;
            generation = 0;
            module_ordinal = 0;
            module_variant = 0;
        }
    };

    static std::complex<double> expected_cell(size_t index);
    static scalar_array probabilities_from_logits(const std::vector<float> & terminal_logits);
    static scalar_array probabilities_from_evidence(const evidence_array & logits);
    static scalar_array angles_from_probabilities(const scalar_array & probabilities);
    static size_t lowest_argmax(const scalar_array & values);
    static double top_two_margin(const scalar_array & values);
    twin_rail_receipt transform_and_restore_impl(
            const std::vector<float> & terminal_logits,
            const twin_rail_contract & contract,
            const score_array * forced_scores);

    void initialize();
    double restoration_error() const;
    bool contract_is_structurally_valid(const twin_rail_contract & contract) const;
    bool structural_transition_is_valid(const twin_rail_contract & contract) const;
    bool two_evidence_structural_transition_is_valid(
            const twin_rail_contract & contract) const;
    bool two_evidence_stage_contract_is_valid(
            const twin_rail_contract & contract) const;
    bool two_evidence_final_contract_is_valid(
            const twin_rail_contract & contract) const;
    static contract_metadata metadata_from_contract(
            const twin_rail_contract & contract);
    static uint64_t carrier_identity_hash(const std::string & identity);
    bool carrier_identity_is_retired(const std::string & identity) const;
    void stage_contract_metadata(const twin_rail_contract & contract);
    void commit_staged_metadata();
    void rollback_staged_metadata();
    void apply_phase(const scalar_array & angles, bool inverse);
    void apply_hadamard();
    void apply_ry(const scalar_array & angles, bool inverse);
    void apply_rx(const scalar_array & angles, bool inverse);
    density_array density_from_cells() const;
    static void apply_complete_decoherence(density_array & density);
    static void apply_hadamard(density_array & density);
    static scalar_array measure_rail_zero(const density_array & density);
    static scalar_array measure_negative_y(const density_array & density);
    void clear_evidence_seed();

    cell_array cells_ = {};
    twin_rail_state state_ = twin_rail_state::EMPTY;
    int32_t buffered_token_ = -1;

    contract_metadata committed_metadata_;
    contract_metadata pending_metadata_;
    bool pending_metadata_valid_ = false;
    std::array<uint64_t, retired_identity_capacity>
            retired_carrier_identity_hashes_ = {};
    size_t retired_carrier_identity_count_ = 0;
    uint64_t server_epoch_ = 0;

    evidence_array first_evidence_seed_ = {};
    bool first_evidence_seed_valid_ = false;
    bool pending_same_backing_ = false;

    uintptr_t prior_backing_address_ = 0;
    uint64_t completed_transactions_ = 0;
    uint64_t backing_reuses_ = 0;
    uint64_t recovery_initializations_ = 0;
};

twin_rail_fresh_parity_result run_fresh_twin_rail_parity(
        const std::vector<float> & terminal_logits,
        const twin_rail_contract & contract);

} // namespace neo3000
