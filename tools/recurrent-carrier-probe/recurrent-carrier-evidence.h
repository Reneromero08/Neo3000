#pragma once

#include <nlohmann/json.hpp>

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>
#include <vector>

namespace neo3000::evidence {

using json = nlohmann::ordered_json;

struct terminal_numeric_analysis {
    std::string state = "INVALID";
    size_t nonfinite_count = 0;
    std::optional<size_t> first_nonfinite_position;
    size_t candidate_nonfinite_count = 0;
    std::vector<float> candidate_logits;
    std::vector<double> candidate_softmax;
    std::optional<size_t> argmax_index;

    bool valid() const {
        return state == "FINITE";
    }
};

terminal_numeric_analysis analyze_terminal_logits(
    const float * logits,
    size_t logits_count,
    const std::vector<int32_t> & candidate_indices);

std::string sha256_hex(const void * data, size_t size);
std::string sha256_file(const std::filesystem::path & path);

struct atomic_write_receipt {
    std::filesystem::path path;
    size_t bytes = 0;
    std::string sha256;
};

atomic_write_receipt atomic_write_text(
    const std::filesystem::path & path,
    const std::string & payload);

struct mechanism_selection {
    std::string mechanism;
    std::vector<std::string> active_fields;
};

mechanism_selection select_exactly_one_mechanism(const json & spec);

struct predecessor_receipt {
    std::filesystem::path path;
    size_t bytes = 0;
    std::string sha256;
    std::string classification;
};

predecessor_receipt verify_declared_predecessor(
    const json & spec,
    const std::filesystem::path & registry_path);

struct factor_payload_digest {
    uint64_t fnv1a64 = UINT64_C(1469598103934665603);
    size_t bytes = 0;
    size_t nonzero_bytes = 0;
};

void factor_digest_update(
    factor_payload_digest & digest,
    const void * data,
    size_t size,
    uint64_t public_tag);

std::string hex64(uint64_t value);

} // namespace neo3000::evidence
