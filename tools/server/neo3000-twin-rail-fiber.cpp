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
    scalar_array values = {};
    double maximum = -std::numeric_limits<double>::infinity();
    for (size_t i = 0; i < hypothesis_count; ++i) {
        values[i] = static_cast<double>(
                terminal_logits[static_cast<size_t>(candidate_token_ids[i])]);
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

void twin_rail_carrier::initialize() {
    for (size_t i = 0; i < cells_.size(); ++i) {
        cells_[i] = expected_cell(i);
    }
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

void twin_rail_carrier::bind_ownership(const twin_rail_contract & contract) {
    bound_carrier_id_ = contract.carrier_id;
    bound_port_owner_ = contract.port_owner;
    bound_port_type_ = contract.port_type;
    bound_module_id_ = contract.module_id;
    last_outer_lease_ = contract.outer_lease;
    last_generation_ = contract.generation;
    last_module_ordinal_ = contract.module_ordinal;
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

twin_rail_receipt twin_rail_carrier::transform_and_restore(
        const std::vector<float> & terminal_logits,
        const twin_rail_contract & contract) {
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

    const scalar_array forward_probabilities =
            probabilities_from_logits(terminal_logits);
    const scalar_array forward_angles =
            angles_from_probabilities(forward_probabilities);
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
    const size_t projected_hypothesis = lowest_argmax(scores);
    const size_t classical_hypothesis =
            lowest_argmax(forward_probabilities);

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
    buffered_token_ = candidate_token_ids[projected_hypothesis];
    completed_transactions_ += 1;
    if (same_backing) {
        backing_reuses_ += 1;
    }
    prior_backing_address_ = backing_address;

    receipt.accepted = true;
    receipt.restored = true;
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

int32_t twin_rail_carrier::take_final_projection() {
    if (state_ != twin_rail_state::RESTORED || buffered_token_ < 0) {
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
