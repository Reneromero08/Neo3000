#include "neo3000-twin-rail-fiber.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace neo3000 {

namespace {

constexpr double inv_sqrt_two = 0.707106781186547524400844362104849039;

bool finite_logits_at_candidates(const std::vector<float> & logits) {
    if (logits.size() <= static_cast<size_t>(twin_rail_carrier::candidate_token_ids.back())) {
        return false;
    }
    for (const int32_t token : twin_rail_carrier::candidate_token_ids) {
        if (!std::isfinite(static_cast<double>(logits[static_cast<size_t>(token)]))) {
            return false;
        }
    }
    return true;
}

bool finite_evidence(const twin_rail_carrier::evidence_array & logits) {
    return std::all_of(logits.begin(), logits.end(), [](float value) {
        return std::isfinite(static_cast<double>(value));
    });
}

} // namespace

std::complex<double> twin_rail_carrier::expected_cell(size_t index) {
    const size_t hypothesis = index / 2;
    static constexpr std::array<std::complex<double>, hypothesis_count> common_modes = {
        std::complex<double>( 1.0,  0.0),
        std::complex<double>( 0.0,  1.0),
        std::complex<double>(-1.0,  0.0),
        std::complex<double>( 0.0, -1.0),
    };
    return common_modes.at(hypothesis) * inv_sqrt_two;
}

twin_rail_carrier::scalar_array twin_rail_carrier::probabilities_from_logits(
        const std::vector<float> & terminal_logits) {
    evidence_array evidence = {};
    for (size_t i = 0; i < hypothesis_count; ++i) {
        evidence[i] =
                terminal_logits[static_cast<size_t>(candidate_token_ids[i])];
    }
    return probabilities_from_evidence(evidence);
}

twin_rail_carrier::scalar_array twin_rail_carrier::probabilities_from_evidence(
        const evidence_array & logits) {
    scalar_array values = {};
    double maximum = -std::numeric_limits<double>::infinity();
    for (size_t i = 0; i < hypothesis_count; ++i) {
        values[i] = static_cast<double>(logits[i]);
        maximum = std::max(maximum, values[i]);
    }

    double denominator = 0.0;
    for (double & value : values) {
        value = std::exp(value - maximum);
        denominator += value;
    }
    if (!(denominator > 0.0) || !std::isfinite(denominator)) {
        throw std::runtime_error("four-hypothesis softmax normalization failed");
    }
    for (double & value : values) {
        value /= denominator;
    }
    return values;
}

twin_rail_carrier::scalar_array twin_rail_carrier::angles_from_probabilities(
        const scalar_array & probabilities) {
    scalar_array angles = {};
    for (size_t i = 0; i < hypothesis_count; ++i) {
        const double cosine = std::clamp(2.0 * probabilities[i] - 1.0, -1.0, 1.0);
        angles[i] = std::acos(cosine);
    }
    return angles;
}

size_t twin_rail_carrier::lowest_argmax(const scalar_array & values) {
    size_t best = 0;
    for (size_t i = 1; i < values.size(); ++i) {
        if (values[i] > values[best]) {
            best = i;
        }
    }
    return best;
}

double twin_rail_carrier::top_two_margin(const scalar_array & values) {
    const size_t best = lowest_argmax(values);
    double runner_up = -std::numeric_limits<double>::infinity();
    for (size_t i = 0; i < values.size(); ++i) {
        if (i != best && values[i] > runner_up) {
            runner_up = values[i];
        }
    }
    return values[best] - runner_up;
}

int32_t twin_rail_carrier::strict_score_projection(
        const score_array & scores) {
    if (!std::all_of(scores.begin(), scores.end(), [](double value) {
            return std::isfinite(value);
        })) {
        return -1;
    }
    return candidate_token_ids[lowest_argmax(scores)];
}

int32_t twin_rail_carrier::canonical_reordered_score_projection(
        const score_array & scores) {
    if (!std::all_of(scores.begin(), scores.end(), [](double value) {
            return std::isfinite(value);
        })) {
        return -1;
    }
    const auto bounds = std::minmax_element(scores.begin(), scores.end());
    if (*bounds.second - *bounds.first > reordered_score_spread_tolerance) {
        return -1;
    }
    return candidate_token_ids.front();
}

void twin_rail_carrier::initialize() {
    for (size_t i = 0; i < cells_.size(); ++i) {
        cells_[i] = expected_cell(i);
    }
    clear_evidence_seed();
    pending_same_backing_ = false;
    buffered_token_ = -1;
    state_ = twin_rail_state::INITIALIZED;
}

double twin_rail_carrier::restoration_error() const {
    double maximum = 0.0;
    for (size_t i = 0; i < cells_.size(); ++i) {
        maximum = std::max(maximum, std::abs(cells_[i] - expected_cell(i)));
    }
    return maximum;
}

bool twin_rail_carrier::contract_is_structurally_valid(
        const twin_rail_contract & contract) const {
    return
            !contract.carrier_id.empty() &&
            contract.outer_lease != 0 &&
            contract.generation != 0 &&
            contract.port_owner == required_port_owner &&
            contract.port_type == required_port_type &&
            contract.module_id == required_module_id &&
            contract.module_variant <=
                    static_cast<uint32_t>(twin_rail_variant::COMPACT_CLASSICAL) &&
            contract.module_ordinal == contract.generation &&
            !contract.input_boundary_id.empty() &&
            contract.projection_policy == required_projection_policy &&
            contract.restoration_policy == required_source_restoration_policy;
}

bool twin_rail_carrier::ownership_transition_is_valid(
        const twin_rail_contract & contract) const {
    if (bound_carrier_id_.empty()) {
        return contract.generation == 1 && contract.module_ordinal == 1;
    }
    if (contract.carrier_id == bound_carrier_id_) {
        return
                contract.port_owner == bound_port_owner_ &&
                contract.port_type == bound_port_type_ &&
                contract.module_id == bound_module_id_ &&
                contract.generation == last_generation_ + 1 &&
                contract.module_ordinal == last_module_ordinal_ + 1 &&
                contract.outer_lease != last_outer_lease_;
    }
    return contract.generation == 1 && contract.module_ordinal == 1;
}

bool twin_rail_carrier::two_evidence_ownership_transition_is_valid(
        const twin_rail_contract & contract) const {
    if (bound_carrier_id_.empty()) {
        return contract.generation == 1;
    }
    if (contract.carrier_id == bound_carrier_id_) {
        return
                contract.generation == last_generation_ + 1 &&
                contract.outer_lease != last_outer_lease_;
    }
    return contract.generation == 1;
}

bool twin_rail_carrier::two_evidence_stage_contract_is_valid(
        const twin_rail_contract & contract) const {
    const auto variant = static_cast<twin_rail_variant>(
            contract.module_variant);
    return
            !contract.carrier_id.empty() &&
            contract.outer_lease != 0 &&
            contract.generation != 0 &&
            contract.port_owner == two_evidence_stage_owner &&
            contract.port_type == two_evidence_stage_type &&
            contract.module_id == two_evidence_stage_module &&
            contract.module_variant <=
                    static_cast<uint32_t>(twin_rail_variant::COMPACT_CLASSICAL) &&
            variant != twin_rail_variant::NULL_CARRIER &&
            variant != twin_rail_variant::PREMATURE_PROJECT &&
            variant != twin_rail_variant::COMPACT_CLASSICAL &&
            contract.module_ordinal == 1 &&
            contract.input_boundary_id == two_evidence_stage_boundary &&
            contract.projection_policy == two_evidence_stage_projection &&
            contract.restoration_policy == two_evidence_stage_restoration &&
            contract.causal_position == two_evidence_stage_causal_position;
}

bool twin_rail_carrier::two_evidence_final_contract_is_valid(
        const twin_rail_contract & contract) const {
    return
            state_ == twin_rail_state::STAGE_RESIDENT &&
            first_evidence_seed_valid_ &&
            contract.carrier_id == bound_carrier_id_ &&
            contract.outer_lease == last_outer_lease_ &&
            contract.generation == last_generation_ &&
            contract.port_owner == two_evidence_final_owner &&
            contract.port_type == two_evidence_final_type &&
            contract.module_id == two_evidence_final_module &&
            contract.module_variant == bound_module_variant_ &&
            contract.module_ordinal == 2 &&
            contract.input_boundary_id == two_evidence_final_boundary &&
            contract.projection_policy == two_evidence_final_projection &&
            contract.restoration_policy == two_evidence_final_restoration &&
            contract.causal_position == two_evidence_final_causal_position;
}

void twin_rail_carrier::bind_ownership(const twin_rail_contract & contract) {
    bound_carrier_id_ = contract.carrier_id;
    bound_port_owner_ = contract.port_owner;
    bound_port_type_ = contract.port_type;
    bound_module_id_ = contract.module_id;
    last_outer_lease_ = contract.outer_lease;
    last_generation_ = contract.generation;
    last_module_ordinal_ = contract.module_ordinal;
    bound_module_variant_ = contract.module_variant;
}

void twin_rail_carrier::apply_phase(const scalar_array & angles, bool inverse) {
    for (size_t i = 0; i < hypothesis_count; ++i) {
        const double theta = inverse ? -angles[i] : angles[i];
        cells_[2 * i + 1] *= std::polar(1.0, theta);
    }
}

void twin_rail_carrier::apply_hadamard() {
    for (size_t i = 0; i < hypothesis_count; ++i) {
        const std::complex<double> first = cells_[2 * i];
        const std::complex<double> second = cells_[2 * i + 1];
        cells_[2 * i] = (first + second) * inv_sqrt_two;
        cells_[2 * i + 1] = (first - second) * inv_sqrt_two;
    }
}

void twin_rail_carrier::apply_ry(
        const scalar_array & angles,
        bool inverse) {
    for (size_t i = 0; i < hypothesis_count; ++i) {
        const double half = (inverse ? -angles[i] : angles[i]) * 0.5;
        const double cosine = std::cos(half);
        const double sine = std::sin(half);
        const std::complex<double> first = cells_[2 * i];
        const std::complex<double> second = cells_[2 * i + 1];
        cells_[2 * i] = cosine * first - sine * second;
        cells_[2 * i + 1] = sine * first + cosine * second;
    }
}

void twin_rail_carrier::apply_rx(
        const scalar_array & angles,
        bool inverse) {
    static constexpr std::complex<double> negative_i(0.0, -1.0);
    for (size_t i = 0; i < hypothesis_count; ++i) {
        const double half = (inverse ? -angles[i] : angles[i]) * 0.5;
        const double cosine = std::cos(half);
        const std::complex<double> off_diagonal =
                negative_i * std::sin(half);
        const std::complex<double> first = cells_[2 * i];
        const std::complex<double> second = cells_[2 * i + 1];
        cells_[2 * i] = cosine * first + off_diagonal * second;
        cells_[2 * i + 1] = off_diagonal * first + cosine * second;
    }
}

void twin_rail_carrier::clear_evidence_seed() {
    first_evidence_seed_.fill(0.0f);
    first_evidence_seed_valid_ = false;
}

twin_rail_receipt twin_rail_carrier::transform_and_restore(
        const std::vector<float> & terminal_logits,
        const twin_rail_contract & contract) {
    return transform_and_restore_impl(
            terminal_logits,
            contract,
            nullptr);
}

twin_rail_receipt twin_rail_carrier::begin_two_evidence(
        const evidence_array & first_logits,
        const twin_rail_contract & stage_contract) {
    twin_rail_receipt receipt;
    receipt.state = state_;
    receipt.two_evidence_composition = true;
    receipt.first_evidence_seed_zeroed = evidence_seed_is_zero();
    receipt.persistent_object_bytes = sizeof(*this);
    receipt.persistent_dynamic_capacity_bytes =
            persistent_dynamic_capacity_bytes();
    buffered_token_ = -1;

    if (unresolved()) {
        poison();
        receipt.error =
                "duplicate two-evidence stage poisoned the unresolved carrier";
        receipt.state = state_;
        receipt.first_evidence_seed_zeroed = evidence_seed_is_zero();
        return receipt;
    }
    if (!two_evidence_stage_contract_is_valid(stage_contract)) {
        receipt.failure_was_pre_borrow = true;
        receipt.error =
                "two-evidence stage contract has the wrong owner, lease, generation, type, module, variant, ordinal, boundary, projection, restoration, or causal position";
        return receipt;
    }
    if (!finite_evidence(first_logits)) {
        receipt.failure_was_pre_borrow = true;
        receipt.error =
                "two-evidence first candidate logits are absent or non-finite";
        return receipt;
    }
    if (!two_evidence_ownership_transition_is_valid(stage_contract)) {
        receipt.failure_was_pre_borrow = true;
        receipt.error =
                "two-evidence stage ownership, lease, generation, or causal order mismatch";
        return receipt;
    }

    const uintptr_t backing_address =
            reinterpret_cast<uintptr_t>(cells_.data());
    pending_same_backing_ =
            prior_backing_address_ != 0 &&
            prior_backing_address_ == backing_address;

    if (state_ == twin_rail_state::EMPTY ||
            state_ == twin_rail_state::INVALID) {
        if (state_ == twin_rail_state::INVALID) {
            recovery_initializations_ += 1;
        }
        initialize();
        pending_same_backing_ =
                prior_backing_address_ != 0 &&
                prior_backing_address_ == backing_address;
    }
    const double initial_error = restoration_error();
    if (initial_error > restoration_tolerance) {
        state_ = twin_rail_state::INVALID;
        receipt.error =
                "two-evidence carrier did not begin from the sealed state";
        receipt.maximum_restoration_error = initial_error;
        receipt.state = state_;
        return receipt;
    }

    bind_ownership(stage_contract);
    first_evidence_seed_ = first_logits;
    first_evidence_seed_valid_ = true;
    receipt.retained_evidence_bytes = retained_evidence_bytes;
    receipt.retained_evidence_bytes_after_call =
            retained_evidence_bytes;
    receipt.first_evidence_seed_zeroed = false;
    receipt.persistent_dynamic_capacity_bytes =
            persistent_dynamic_capacity_bytes();
    state_ = twin_rail_state::BORROWED;

    const auto variant = static_cast<twin_rail_variant>(
            stage_contract.module_variant);
    apply_hadamard();
    if (variant != twin_rail_variant::REORDERED_FORWARD) {
        const scalar_array probabilities =
                probabilities_from_evidence(first_logits);
        scalar_array angles = {};
        for (size_t i = 0; i < hypothesis_count; ++i) {
            angles[i] = std::acos(
                    std::clamp(probabilities[i], 0.0, 1.0));
        }
        apply_ry(angles, false);
    }
    state_ = twin_rail_state::STAGE_RESIDENT;

    receipt.accepted = true;
    receipt.same_backing_as_prior_transaction = pending_same_backing_;
    receipt.completed_transactions = completed_transactions_;
    receipt.backing_reuses = backing_reuses_;
    receipt.recovery_initializations = recovery_initializations_;
    receipt.state = state_;
    return receipt;
}

twin_rail_receipt twin_rail_carrier::finish_two_evidence(
        const evidence_array & second_logits,
        const twin_rail_contract & final_contract) {
    twin_rail_receipt receipt;
    receipt.state = state_;
    receipt.two_evidence_composition = true;
    receipt.first_evidence_seed_zeroed = evidence_seed_is_zero();
    receipt.persistent_object_bytes = sizeof(*this);
    receipt.persistent_dynamic_capacity_bytes =
            persistent_dynamic_capacity_bytes();
    receipt.retained_evidence_bytes =
            first_evidence_seed_valid_ ? retained_evidence_bytes : 0;
    receipt.retained_evidence_bytes_after_call =
            receipt.retained_evidence_bytes;

    if (!two_evidence_final_contract_is_valid(final_contract)) {
        receipt.failure_was_pre_borrow =
                state_ != twin_rail_state::STAGE_RESIDENT;
        receipt.error =
                "two-evidence final contract has the wrong stage, owner, lease, generation, type, module, variant, ordinal, boundary, projection, restoration, or causal position";
        if (state_ == twin_rail_state::STAGE_RESIDENT) {
            poison();
            receipt.state = state_;
            receipt.first_evidence_seed_zeroed =
                    evidence_seed_is_zero();
            receipt.retained_evidence_bytes_after_call = 0;
        }
        return receipt;
    }
    if (!finite_evidence(second_logits)) {
        receipt.error =
                "two-evidence second candidate logits are absent or non-finite";
        poison();
        receipt.state = state_;
        receipt.first_evidence_seed_zeroed = evidence_seed_is_zero();
        receipt.retained_evidence_bytes_after_call = 0;
        return receipt;
    }

    scalar_array compact_products = {};
    const auto variant = static_cast<twin_rail_variant>(
            final_contract.module_variant);
    scalar_array scores = {};
    scalar_array expected_scores = {};
    state_ = twin_rail_state::COMPOSING;
    {
        const scalar_array first_probabilities =
                probabilities_from_evidence(first_evidence_seed_);
        const scalar_array second_probabilities =
                probabilities_from_evidence(second_logits);
        scalar_array second_angles = {};
        for (size_t i = 0; i < hypothesis_count; ++i) {
            second_angles[i] = std::asin(
                    std::clamp(second_probabilities[i], 0.0, 1.0));
            compact_products[i] =
                    first_probabilities[i] *
                    second_probabilities[i];
        }
        if (variant == twin_rail_variant::REORDERED_FORWARD) {
            scalar_array first_angles = {};
            for (size_t i = 0; i < hypothesis_count; ++i) {
                first_angles[i] = std::acos(
                        std::clamp(first_probabilities[i], 0.0, 1.0));
            }
            apply_rx(second_angles, false);
            apply_ry(first_angles, false);
        } else {
            apply_rx(second_angles, false);
        }
        for (size_t i = 0; i < hypothesis_count; ++i) {
            if (variant == twin_rail_variant::DEPHASED_SHAM) {
                scores[i] = 0.5;
                expected_scores[i] = 0.5;
            } else if (variant == twin_rail_variant::REORDERED_FORWARD) {
                scores[i] =
                        0.5 -
                        std::imag(
                                std::conj(cells_[2 * i]) *
                                cells_[2 * i + 1]);
                expected_scores[i] =
                        0.5 * (1.0 + second_probabilities[i]);
            } else {
                scores[i] =
                        0.5 -
                        std::imag(
                                std::conj(cells_[2 * i]) *
                                cells_[2 * i + 1]);
                expected_scores[i] =
                        0.5 * (1.0 + compact_products[i]);
            }
        }
    }

    double maximum_score_error = 0.0;
    for (size_t i = 0; i < hypothesis_count; ++i) {
        maximum_score_error = std::max(
                maximum_score_error,
                std::abs(scores[i] - expected_scores[i]));
    }
    const size_t projected_hypothesis = lowest_argmax(scores);
    const size_t compact_hypothesis = lowest_argmax(compact_products);
    receipt.primary_margin_guard_passed =
            variant == twin_rail_variant::PRIMARY &&
            top_two_margin(compact_products) >
                    primary_minimum_top_two_margin;
    receipt.maximum_score_error = maximum_score_error;
    receipt.classical_parity =
            variant == twin_rail_variant::PRIMARY &&
            projected_hypothesis == compact_hypothesis &&
            maximum_score_error <= restoration_tolerance;

    state_ = twin_rail_state::RESTORING;
    {
        const scalar_array inverse_first_probabilities =
                probabilities_from_evidence(first_evidence_seed_);
        const scalar_array inverse_second_probabilities =
                probabilities_from_evidence(second_logits);
        scalar_array inverse_first_angles = {};
        scalar_array inverse_second_angles = {};
        for (size_t i = 0; i < hypothesis_count; ++i) {
            inverse_first_angles[i] = std::acos(
                    std::clamp(
                            inverse_first_probabilities[i],
                            0.0,
                            1.0));
            inverse_second_angles[i] = std::asin(
                    std::clamp(
                            inverse_second_probabilities[i],
                            0.0,
                            1.0));
        }
        if (variant == twin_rail_variant::REORDERED_FORWARD) {
            apply_ry(inverse_first_angles, true);
            apply_rx(inverse_second_angles, true);
            apply_hadamard();
        } else if (variant == twin_rail_variant::MISSING_INVERSE) {
            apply_ry(inverse_first_angles, true);
            apply_hadamard();
        } else if (variant == twin_rail_variant::WRONG_INVERSE) {
            apply_rx(inverse_second_angles, false);
            apply_ry(inverse_first_angles, true);
            apply_hadamard();
        } else if (variant == twin_rail_variant::REORDERED_INVERSE) {
            apply_ry(inverse_first_angles, true);
            apply_rx(inverse_second_angles, true);
            apply_hadamard();
        } else {
            apply_rx(inverse_second_angles, true);
            apply_ry(inverse_first_angles, true);
            apply_hadamard();
        }
    }

    const double maximum_restoration_error = restoration_error();
    receipt.maximum_restoration_error = maximum_restoration_error;
    receipt.same_backing_as_prior_transaction = pending_same_backing_;
    clear_evidence_seed();
    receipt.first_evidence_seed_zeroed = evidence_seed_is_zero();
    receipt.retained_evidence_bytes_after_call = 0;

    if (maximum_restoration_error > restoration_tolerance) {
        state_ = twin_rail_state::INVALID;
        receipt.error =
                "two-evidence inverse did not restore the physical carrier";
        receipt.state = state_;
        receipt.completed_transactions = completed_transactions_;
        receipt.backing_reuses = backing_reuses_;
        receipt.recovery_initializations = recovery_initializations_;
        receipt.persistent_dynamic_capacity_bytes =
                persistent_dynamic_capacity_bytes();
        return receipt;
    }

    state_ = twin_rail_state::RESTORED;
    receipt.restored = true;
    if (variant == twin_rail_variant::PRIMARY &&
            (!receipt.primary_margin_guard_passed ||
             !receipt.classical_parity)) {
        state_ = twin_rail_state::INVALID;
        receipt.error =
                "primary two-evidence score, strict margin, or compact parity failed";
        receipt.state = state_;
        receipt.persistent_dynamic_capacity_bytes =
                persistent_dynamic_capacity_bytes();
        return receipt;
    }

    buffered_token_ = candidate_token_ids[projected_hypothesis];
    completed_transactions_ += 1;
    if (pending_same_backing_) {
        backing_reuses_ += 1;
    }
    prior_backing_address_ =
            reinterpret_cast<uintptr_t>(cells_.data());
    pending_same_backing_ = false;

    receipt.accepted = true;
    receipt.completed_transactions = completed_transactions_;
    receipt.backing_reuses = backing_reuses_;
    receipt.recovery_initializations = recovery_initializations_;
    receipt.persistent_dynamic_capacity_bytes =
            persistent_dynamic_capacity_bytes();
    receipt.state = state_;
    return receipt;
}

#ifdef NEO3000_TWIN_RAIL_TESTING
twin_rail_receipt twin_rail_carrier::transform_and_restore_with_test_scores(
        const std::vector<float> & terminal_logits,
        const twin_rail_contract & contract,
        const score_array & forced_scores) {
    return transform_and_restore_impl(
            terminal_logits,
            contract,
            &forced_scores);
}
#endif

twin_rail_receipt twin_rail_carrier::transform_and_restore_impl(
        const std::vector<float> & terminal_logits,
        const twin_rail_contract & contract,
        const score_array * forced_scores) {
    twin_rail_receipt receipt;
    receipt.state = state_;
    receipt.persistent_object_bytes = sizeof(*this);
    receipt.persistent_dynamic_capacity_bytes =
            persistent_dynamic_capacity_bytes();
    buffered_token_ = -1;

    if (!contract_is_structurally_valid(contract)) {
        receipt.failure_was_pre_borrow = true;
        receipt.error = "twin-rail contract is incomplete or has the wrong owner, type, module, order, projection, or source-closure policy";
        return receipt;
    }

    const auto variant = static_cast<twin_rail_variant>(contract.module_variant);
    if (variant == twin_rail_variant::NULL_CARRIER) {
        receipt.failure_was_pre_borrow = true;
        receipt.error = "null twin-rail carrier rejected before borrow";
        return receipt;
    }
    if (variant == twin_rail_variant::PREMATURE_PROJECT) {
        receipt.failure_was_pre_borrow = true;
        receipt.error = "premature twin-rail projection rejected before borrow";
        return receipt;
    }
    if (variant == twin_rail_variant::COMPACT_CLASSICAL) {
        receipt.failure_was_pre_borrow = true;
        receipt.error = "compact classical control is not a twin-rail carrier transaction";
        return receipt;
    }
    if (!finite_logits_at_candidates(terminal_logits)) {
        receipt.failure_was_pre_borrow = true;
        receipt.error = "fixed A/B/C/D terminal logits are absent or non-finite";
        return receipt;
    }
    if (state_ != twin_rail_state::EMPTY &&
            state_ != twin_rail_state::CLOSED &&
            state_ != twin_rail_state::INVALID) {
        receipt.error = "twin-rail carrier is unresolved or not closed";
        return receipt;
    }
    if (!ownership_transition_is_valid(contract)) {
        receipt.failure_was_pre_borrow = true;
        receipt.error = "twin-rail ownership, lease, generation, or causal order mismatch";
        return receipt;
    }

    const scalar_array forward_probabilities =
            probabilities_from_logits(terminal_logits);
    const scalar_array forward_angles =
            angles_from_probabilities(forward_probabilities);
    if (variant == twin_rail_variant::PRIMARY) {
        receipt.primary_margin_guard_passed =
                top_two_margin(forward_probabilities) >
                primary_minimum_top_two_margin;
        if (!receipt.primary_margin_guard_passed) {
            receipt.failure_was_pre_borrow = true;
            receipt.error =
                    "primary twin-rail probability margin is not strictly separated";
            receipt.state = state_;
            return receipt;
        }
    }

    const uintptr_t backing_address =
            reinterpret_cast<uintptr_t>(cells_.data());
    const bool same_backing =
            prior_backing_address_ != 0 &&
            prior_backing_address_ == backing_address;

    if (state_ == twin_rail_state::EMPTY || state_ == twin_rail_state::INVALID) {
        if (state_ == twin_rail_state::INVALID) {
            recovery_initializations_ += 1;
        }
        initialize();
    }
    const double initial_error = restoration_error();
    if (initial_error > restoration_tolerance) {
        state_ = twin_rail_state::INVALID;
        receipt.error = "twin-rail carrier did not begin from the rematerialized sealed state";
        receipt.maximum_restoration_error = initial_error;
        receipt.state = state_;
        return receipt;
    }

    bind_ownership(contract);
    receipt.persistent_dynamic_capacity_bytes =
            persistent_dynamic_capacity_bytes();
    state_ = twin_rail_state::BORROWED;

    scalar_array scores = {};

    if (variant == twin_rail_variant::REORDERED_FORWARD) {
        apply_hadamard();
        state_ = twin_rail_state::STAGE_RESIDENT;
        apply_phase(forward_angles, false);
    } else {
        apply_phase(forward_angles, false);
        state_ = twin_rail_state::STAGE_RESIDENT;
        apply_hadamard();
    }
    state_ = twin_rail_state::COMPOSING;

    for (size_t i = 0; i < hypothesis_count; ++i) {
        scores[i] = variant == twin_rail_variant::DEPHASED_SHAM
                ? 0.5
                : std::norm(cells_[2 * i]);
    }
    if (forced_scores != nullptr) {
        scores = *forced_scores;
    }
    double maximum_score_error = 0.0;
    if (variant == twin_rail_variant::PRIMARY ||
            variant == twin_rail_variant::MISSING_INVERSE ||
            variant == twin_rail_variant::WRONG_INVERSE ||
            variant == twin_rail_variant::REORDERED_INVERSE) {
        for (size_t i = 0; i < hypothesis_count; ++i) {
            maximum_score_error = std::max(
                    maximum_score_error,
                    std::abs(scores[i] - forward_probabilities[i]));
        }
    }
    const size_t classical_hypothesis =
            lowest_argmax(forward_probabilities);
    size_t projected_hypothesis = 0;
    bool reordered_quotient_admitted = true;
    if (variant == twin_rail_variant::REORDERED_FORWARD) {
        const int32_t canonical_token =
                canonical_reordered_score_projection(scores);
        reordered_quotient_admitted = canonical_token >= 0;
        receipt.canonical_tie_quotient_applied =
                reordered_quotient_admitted;
        projected_hypothesis = 0;
    } else {
        projected_hypothesis = lowest_argmax(scores);
    }

    state_ = twin_rail_state::RESTORING;
    const scalar_array inverse_probabilities =
            probabilities_from_logits(terminal_logits);
    const scalar_array inverse_angles =
            angles_from_probabilities(inverse_probabilities);
    if (variant == twin_rail_variant::REORDERED_FORWARD) {
        apply_phase(inverse_angles, true);
        apply_hadamard();
    } else if (variant == twin_rail_variant::MISSING_INVERSE) {
        apply_hadamard();
    } else if (variant == twin_rail_variant::WRONG_INVERSE) {
        apply_hadamard();
        apply_phase(inverse_angles, false);
    } else if (variant == twin_rail_variant::REORDERED_INVERSE) {
        apply_phase(inverse_angles, true);
        apply_hadamard();
    } else {
        apply_hadamard();
        apply_phase(inverse_angles, true);
    }

    const double maximum_restoration_error = restoration_error();
    receipt.maximum_score_error = maximum_score_error;
    receipt.maximum_restoration_error = maximum_restoration_error;
    receipt.classical_parity =
            variant == twin_rail_variant::PRIMARY &&
            projected_hypothesis == classical_hypothesis &&
            maximum_score_error <= restoration_tolerance;
    receipt.same_backing_as_prior_transaction = same_backing;

    if (maximum_restoration_error > restoration_tolerance) {
        state_ = twin_rail_state::INVALID;
        receipt.error = "twin-rail inverse did not restore the physical carrier";
        receipt.state = state_;
        receipt.completed_transactions = completed_transactions_;
        receipt.backing_reuses = backing_reuses_;
        receipt.recovery_initializations = recovery_initializations_;
        receipt.persistent_dynamic_capacity_bytes =
                persistent_dynamic_capacity_bytes();
        return receipt;
    }

    state_ = twin_rail_state::RESTORED;
    receipt.restored = true;
    if (variant == twin_rail_variant::REORDERED_FORWARD &&
            !reordered_quotient_admitted) {
        state_ = twin_rail_state::INVALID;
        receipt.error =
                "reordered-forward scores exceeded the canonical numerical quotient";
        receipt.state = state_;
        receipt.completed_transactions = completed_transactions_;
        receipt.backing_reuses = backing_reuses_;
        receipt.recovery_initializations = recovery_initializations_;
        receipt.persistent_dynamic_capacity_bytes =
                persistent_dynamic_capacity_bytes();
        return receipt;
    }
    if (variant == twin_rail_variant::PRIMARY &&
            !receipt.classical_parity) {
        state_ = twin_rail_state::INVALID;
        receipt.error =
                "primary twin-rail score error or strict classical parity failed";
        receipt.state = state_;
        receipt.completed_transactions = completed_transactions_;
        receipt.backing_reuses = backing_reuses_;
        receipt.recovery_initializations = recovery_initializations_;
        receipt.persistent_dynamic_capacity_bytes =
                persistent_dynamic_capacity_bytes();
        return receipt;
    }

    buffered_token_ = candidate_token_ids[projected_hypothesis];
    completed_transactions_ += 1;
    if (same_backing) {
        backing_reuses_ += 1;
    }
    prior_backing_address_ = backing_address;

    receipt.accepted = true;
    receipt.completed_transactions = completed_transactions_;
    receipt.backing_reuses = backing_reuses_;
    receipt.recovery_initializations = recovery_initializations_;
    receipt.persistent_dynamic_capacity_bytes =
            persistent_dynamic_capacity_bytes();
    receipt.state = state_;
    return receipt;
}

int32_t twin_rail_carrier::compact_classical_projection(
        const std::vector<float> & terminal_logits) {
    if (!finite_logits_at_candidates(terminal_logits)) {
        return -1;
    }
    const scalar_array probabilities =
            probabilities_from_logits(terminal_logits);
    return candidate_token_ids[lowest_argmax(probabilities)];
}

int32_t twin_rail_carrier::compact_two_evidence_projection(
        const evidence_array & first_logits,
        const evidence_array & second_logits) {
    if (!finite_evidence(first_logits) || !finite_evidence(second_logits)) {
        return -1;
    }
    const scalar_array first_probabilities =
            probabilities_from_evidence(first_logits);
    const scalar_array second_probabilities =
            probabilities_from_evidence(second_logits);
    scalar_array products = {};
    for (size_t i = 0; i < hypothesis_count; ++i) {
        products[i] =
                first_probabilities[i] * second_probabilities[i];
    }
    return candidate_token_ids[lowest_argmax(products)];
}

int32_t twin_rail_carrier::take_final_projection() {
    if (state_ != twin_rail_state::RESTORED || buffered_token_ < 0) {
        if (unresolved()) {
            poison();
        }
        return -1;
    }
    state_ = twin_rail_state::FINAL_PROJECTED;
    const int32_t token = buffered_token_;
    buffered_token_ = -1;
    state_ = twin_rail_state::CLOSED;
    return token;
}

void twin_rail_carrier::poison() {
    buffered_token_ = -1;
    clear_evidence_seed();
    pending_same_backing_ = false;
    if (unresolved()) {
        state_ = twin_rail_state::INVALID;
    }
}

twin_rail_state twin_rail_carrier::state() const {
    return state_;
}

bool twin_rail_carrier::unresolved() const {
    return
            state_ == twin_rail_state::BORROWED ||
            state_ == twin_rail_state::STAGE_RESIDENT ||
            state_ == twin_rail_state::COMPOSING ||
            state_ == twin_rail_state::RESTORING ||
            state_ == twin_rail_state::RESTORED ||
            state_ == twin_rail_state::FINAL_PROJECTED;
}

bool twin_rail_carrier::has_buffered_projection() const {
    return buffered_token_ >= 0;
}

bool twin_rail_carrier::evidence_seed_is_zero() const {
    return
            !first_evidence_seed_valid_ &&
            std::all_of(
                    first_evidence_seed_.begin(),
                    first_evidence_seed_.end(),
                    [](float value) {
                        return value == 0.0f;
                    });
}

uint64_t twin_rail_carrier::completed_transactions() const {
    return completed_transactions_;
}

uint64_t twin_rail_carrier::backing_reuses() const {
    return backing_reuses_;
}

uint64_t twin_rail_carrier::recovery_initializations() const {
    return recovery_initializations_;
}

size_t twin_rail_carrier::persistent_object_bytes() const {
    return sizeof(*this);
}

size_t twin_rail_carrier::persistent_dynamic_capacity_bytes() const {
    return
            bound_carrier_id_.capacity() +
            bound_port_owner_.capacity() +
            bound_port_type_.capacity() +
            bound_module_id_.capacity();
}

twin_rail_fresh_parity_result run_fresh_twin_rail_parity(
        const std::vector<float> & terminal_logits,
        const twin_rail_contract & contract) {
    // This control carrier exists only while a primary parity transaction is
    // executing. Keeping it in this out-of-line call avoids reserving a full
    // carrier object on ordinary, compact, sham, and fault routes.
    twin_rail_carrier fresh_carrier;
    twin_rail_fresh_parity_result result;
    result.receipt =
            fresh_carrier.transform_and_restore(terminal_logits, contract);
    if (result.receipt.accepted) {
        result.projected_token = fresh_carrier.take_final_projection();
    }
    return result;
}

} // namespace neo3000
