#include "recurrent-carrier-evidence.h"

#include <algorithm>
#include <array>
#include <cerrno>
#include <chrono>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <limits>
#include <set>
#include <sstream>
#include <stdexcept>
#include <system_error>

#include <fcntl.h>
#include <linux/fs.h>
#include <sys/syscall.h>
#include <unistd.h>

namespace neo3000::evidence {
namespace {

constexpr std::array<uint32_t, 64> SHA256_K = {
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u,
    0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
    0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
    0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
    0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu,
    0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
    0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u,
    0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
    0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
    0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
    0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u,
    0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
    0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u,
    0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
    0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
    0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u,
};

uint32_t rotate_right(uint32_t value, uint32_t amount) {
    return (value >> amount) | (value << (32u - amount));
}

std::array<uint8_t, 32> sha256_bytes(const uint8_t * data, size_t size) {
    std::array<uint32_t, 8> state = {
        0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
        0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u,
    };
    const uint64_t bit_size = static_cast<uint64_t>(size) * 8u;
    const size_t padded_size = ((size + 9u + 63u) / 64u) * 64u;
    std::vector<uint8_t> padded(padded_size, 0);
    if (size != 0) {
        std::memcpy(padded.data(), data, size);
    }
    padded[size] = 0x80u;
    for (size_t i = 0; i < 8; ++i) {
        padded[padded_size - 1u - i] =
            static_cast<uint8_t>((bit_size >> (8u * i)) & 0xffu);
    }

    for (size_t block = 0; block < padded_size; block += 64u) {
        std::array<uint32_t, 64> words = {};
        for (size_t i = 0; i < 16; ++i) {
            const size_t offset = block + i * 4u;
            words[i] =
                (static_cast<uint32_t>(padded[offset]) << 24u) |
                (static_cast<uint32_t>(padded[offset + 1u]) << 16u) |
                (static_cast<uint32_t>(padded[offset + 2u]) << 8u) |
                static_cast<uint32_t>(padded[offset + 3u]);
        }
        for (size_t i = 16; i < words.size(); ++i) {
            const uint32_t s0 =
                rotate_right(words[i - 15u], 7u) ^
                rotate_right(words[i - 15u], 18u) ^
                (words[i - 15u] >> 3u);
            const uint32_t s1 =
                rotate_right(words[i - 2u], 17u) ^
                rotate_right(words[i - 2u], 19u) ^
                (words[i - 2u] >> 10u);
            words[i] =
                words[i - 16u] + s0 + words[i - 7u] + s1;
        }

        uint32_t a = state[0];
        uint32_t b = state[1];
        uint32_t c = state[2];
        uint32_t d = state[3];
        uint32_t e = state[4];
        uint32_t f = state[5];
        uint32_t g = state[6];
        uint32_t h = state[7];
        for (size_t i = 0; i < words.size(); ++i) {
            const uint32_t sum1 =
                rotate_right(e, 6u) ^
                rotate_right(e, 11u) ^
                rotate_right(e, 25u);
            const uint32_t choose = (e & f) ^ (~e & g);
            const uint32_t temporary1 =
                h + sum1 + choose + SHA256_K[i] + words[i];
            const uint32_t sum0 =
                rotate_right(a, 2u) ^
                rotate_right(a, 13u) ^
                rotate_right(a, 22u);
            const uint32_t majority =
                (a & b) ^ (a & c) ^ (b & c);
            const uint32_t temporary2 = sum0 + majority;
            h = g;
            g = f;
            f = e;
            e = d + temporary1;
            d = c;
            c = b;
            b = a;
            a = temporary1 + temporary2;
        }
        state[0] += a;
        state[1] += b;
        state[2] += c;
        state[3] += d;
        state[4] += e;
        state[5] += f;
        state[6] += g;
        state[7] += h;
    }

    std::array<uint8_t, 32> result = {};
    for (size_t i = 0; i < state.size(); ++i) {
        result[i * 4u] = static_cast<uint8_t>(state[i] >> 24u);
        result[i * 4u + 1u] = static_cast<uint8_t>(state[i] >> 16u);
        result[i * 4u + 2u] = static_cast<uint8_t>(state[i] >> 8u);
        result[i * 4u + 3u] = static_cast<uint8_t>(state[i]);
    }
    return result;
}

std::vector<uint8_t> read_all(const std::filesystem::path & path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream.is_open()) {
        throw std::runtime_error(
            "failed to open file for verified read: " + path.string());
    }
    stream.seekg(0, std::ios::end);
    const std::streamoff end = stream.tellg();
    if (end < 0) {
        throw std::runtime_error(
            "failed to size file for verified read: " + path.string());
    }
    stream.seekg(0, std::ios::beg);
    std::vector<uint8_t> bytes(static_cast<size_t>(end));
    if (!bytes.empty()) {
        stream.read(
            reinterpret_cast<char *>(bytes.data()),
            static_cast<std::streamsize>(bytes.size()));
    }
    if (!stream || stream.peek() != std::ifstream::traits_type::eof()) {
        throw std::runtime_error(
            "failed to read complete verified file: " + path.string());
    }
    stream.close();
    if (stream.fail()) {
        throw std::runtime_error(
            "failed to close verified read: " + path.string());
    }
    return bytes;
}

bool looks_like_scientific_mode(const std::string & key) {
    constexpr std::array<const char *, 11> suffixes = {
        "_action",
        "_composition",
        "_construction",
        "_branching",
        "_transfer",
        "_panel",
        "_control",
        "_roots",
        "_validation",
        "_partition",
        "_refresh",
    };
    return std::any_of(
        suffixes.begin(),
        suffixes.end(),
        [&](const char * suffix) {
            const size_t length = std::strlen(suffix);
            return key.size() >= length &&
                key.compare(key.size() - length, length, suffix) == 0;
        });
}

} // namespace

terminal_numeric_analysis analyze_terminal_logits(
        const float * logits,
        size_t logits_count,
        const std::vector<int32_t> & candidate_indices) {
    terminal_numeric_analysis result;
    result.state = "NONFINITE_LOGITS";
    if (!logits || logits_count == 0 || candidate_indices.empty()) {
        result.state = "INVALID_LOGIT_BUFFER";
        return result;
    }

    for (size_t i = 0; i < logits_count; ++i) {
        if (!std::isfinite(logits[i])) {
            if (!result.first_nonfinite_position.has_value()) {
                result.first_nonfinite_position = i;
            }
            ++result.nonfinite_count;
        }
    }
    result.candidate_logits.reserve(candidate_indices.size());
    for (int32_t index : candidate_indices) {
        if (index < 0 || static_cast<size_t>(index) >= logits_count) {
            result.state = "INVALID_CANDIDATE_INDEX";
            return result;
        }
        const float value = logits[index];
        result.candidate_logits.push_back(value);
        result.candidate_nonfinite_count += !std::isfinite(value);
    }
    if (result.nonfinite_count != 0) {
        return result;
    }

    const auto maximum = std::max_element(
        result.candidate_logits.begin(),
        result.candidate_logits.end());
    if (maximum == result.candidate_logits.end() ||
        !std::isfinite(*maximum)) {
        result.state = "NONFINITE_SOFTMAX_INPUT";
        return result;
    }
    result.argmax_index = static_cast<size_t>(
        std::distance(result.candidate_logits.begin(), maximum));
    double sum = 0.0;
    for (float value : result.candidate_logits) {
        const double term =
            std::exp(static_cast<double>(value - *maximum));
        if (!std::isfinite(term)) {
            result.state = "NONFINITE_SOFTMAX_TERM";
            result.argmax_index.reset();
            result.candidate_softmax.clear();
            return result;
        }
        result.candidate_softmax.push_back(term);
        sum += term;
    }
    if (!std::isfinite(sum) || sum <= 0.0) {
        result.state = "NONFINITE_SOFTMAX_SUM";
        result.argmax_index.reset();
        result.candidate_softmax.clear();
        return result;
    }
    for (double & value : result.candidate_softmax) {
        value /= sum;
        if (!std::isfinite(value)) {
            result.state = "NONFINITE_SOFTMAX_OUTPUT";
            result.argmax_index.reset();
            result.candidate_softmax.clear();
            return result;
        }
    }
    result.state = "FINITE";
    return result;
}

std::string sha256_hex(const void * data, size_t size) {
    const auto digest = sha256_bytes(
        static_cast<const uint8_t *>(data), size);
    std::ostringstream stream;
    stream << std::hex << std::setfill('0');
    for (uint8_t byte : digest) {
        stream << std::setw(2) << static_cast<unsigned>(byte);
    }
    return stream.str();
}

std::string sha256_file(const std::filesystem::path & path) {
    const auto bytes = read_all(path);
    return sha256_hex(bytes.data(), bytes.size());
}

atomic_write_receipt atomic_write_text(
        const std::filesystem::path & path,
        const std::string & payload) {
    if (path.empty()) {
        throw std::runtime_error("terminal result path is empty");
    }
    std::error_code error;
    if (std::filesystem::exists(path, error)) {
        throw std::runtime_error(
            "terminal result already exists; refusing overwrite: " +
            path.string());
    }
    if (error) {
        throw std::runtime_error(
            "failed to inspect terminal result path: " + error.message());
    }
    const auto nonce =
        std::chrono::steady_clock::now().time_since_epoch().count();
    const std::filesystem::path temporary =
        path.string() + ".tmp." + std::to_string(getpid()) + "." +
        std::to_string(nonce);

    std::ofstream stream(
        temporary,
        std::ios::binary | std::ios::out | std::ios::trunc);
    if (!stream.is_open()) {
        throw std::runtime_error(
            "failed to open terminal result temporary file: " +
            temporary.string());
    }
    stream.write(payload.data(), static_cast<std::streamsize>(payload.size()));
    if (!stream) {
        throw std::runtime_error(
            "failed to write terminal result temporary file: " +
            temporary.string());
    }
    stream.flush();
    if (!stream) {
        throw std::runtime_error(
            "failed to flush terminal result temporary file: " +
            temporary.string());
    }
    stream.close();
    if (stream.fail()) {
        throw std::runtime_error(
            "failed to close terminal result temporary file: " +
            temporary.string());
    }

    const auto verified_temporary = read_all(temporary);
    if (verified_temporary.size() != payload.size() ||
        !std::equal(
            verified_temporary.begin(),
            verified_temporary.end(),
            reinterpret_cast<const uint8_t *>(payload.data()))) {
        throw std::runtime_error(
            "terminal result temporary verification mismatch: " +
            temporary.string());
    }
    const std::string expected_hash = sha256_hex(
        verified_temporary.data(), verified_temporary.size());

    const long rename_status = syscall(
        SYS_renameat2,
        AT_FDCWD,
        temporary.c_str(),
        AT_FDCWD,
        path.c_str(),
        RENAME_NOREPLACE);
    if (rename_status != 0) {
        throw std::runtime_error(
            "failed atomic terminal result commit: " +
            std::string(std::strerror(errno)));
    }

    const auto committed = read_all(path);
    const std::string committed_hash =
        sha256_hex(committed.data(), committed.size());
    if (committed.size() != payload.size() ||
        committed_hash != expected_hash ||
        !std::equal(
            committed.begin(),
            committed.end(),
            reinterpret_cast<const uint8_t *>(payload.data()))) {
        throw std::runtime_error(
            "committed terminal result verification mismatch: " +
            path.string());
    }
    return {path, committed.size(), committed_hash};
}

mechanism_selection select_exactly_one_mechanism(const json & spec) {
    static const std::set<std::string> outer_fields = {
        "prefix_dag_attention_construction",
        "affine_attention_composition",
        "position_splice_attention_composition",
        "open_f_prefix_nonlinear_composition",
        "active_f_sequence_branching",
        "multi_context_subspace_operator_transfer",
        "subspace_operator_transfer",
        "sparse_g_label_refresh",
        "g_forward_state_partition",
        "physical_attention_capability_panel",
        "full_hybrid_capability_panel",
        "full_hybrid_capability_control",
        "physical_attention_roots",
        "matched_semantic_validation",
    };
    static const std::set<std::string> sparse_action_fields = {
        "label_orbit_attention_action",
        "value_orbit_attention_action",
        "key_value_orbit_attention_action",
        "complex_phase_quarter_turn_action",
        "fourier_value_orbit_action",
        "subspace_value_orbit_action",
        "model_weight_value_orbit_action",
        "output_promoted_value_carrier_action",
        "output_role_transport_action",
        "output_role_generator_action",
        "output_attention_kernel_writer_action",
        "output_source_position_rematerialization_action",
        "output_source_position_fixed_cell_rematerialization_action",
        "output_continuous_soft_role_rematerialization_action",
        "output_written_semantic_port_action",
        "output_written_hidden_slot_action",
        "output_depth_resolved_cross_attention_memory_action",
        "output_phase_memory_action",
        "output_phase_orbit_memory_action",
        "output_recurrent_delta_advance_action",
        "trained_semantic_carrier_action",
        "source_conditioned_lifting_action",
    };
    std::set<std::string> known = outer_fields;
    known.insert(sparse_action_fields.begin(), sparse_action_fields.end());

    mechanism_selection result;
    for (const auto & [key, value] : spec.items()) {
        if (value.is_boolean() && value.get<bool>() &&
            looks_like_scientific_mode(key) &&
            known.find(key) == known.end()) {
            throw std::runtime_error(
                "unknown enabled scientific mode field: " + key);
        }
        if (outer_fields.find(key) != outer_fields.end() &&
            value.is_boolean() && value.get<bool>()) {
            result.active_fields.push_back(key);
        }
    }
    if (spec.contains("localization_arms")) {
        result.active_fields.push_back("localization_arms");
    }
    if (result.active_fields.empty() &&
        spec.contains("sources") && spec.contains("queries")) {
        result.active_fields.push_back(
            "default_hybrid_root_decomposition");
    }
    if (result.active_fields.size() != 1) {
        throw std::runtime_error(
            "spec must select exactly one top-level mechanism; selected=" +
            std::to_string(result.active_fields.size()));
    }
    result.mechanism = result.active_fields.front();

    std::vector<std::string> sparse_actions;
    for (const std::string & field : sparse_action_fields) {
        if (spec.value(field, false)) {
            sparse_actions.push_back(field);
        }
    }
    if (sparse_actions.size() > 1) {
        throw std::runtime_error(
            "sparse mechanism has incompatible active action fields");
    }
    if (!sparse_actions.empty()) {
        if (result.mechanism != "sparse_g_label_refresh") {
            throw std::runtime_error(
                "sparse action enabled outside sparse_g_label_refresh");
        }
        result.active_fields.push_back(sparse_actions.front());
        result.mechanism += ":" + sparse_actions.front();
    }
    if (spec.value("source_conditioned_lifting_action", false)) {
        static const std::set<std::string> lifting_fields = {
            "acceptance_law",
            "claim_ceiling",
            "closure",
            "complex_phase_quarter_turn_action",
            "description",
            "expected_attention_stream_count",
            "expected_closure_tokens",
            "expected_context_per_sequence",
            "expected_context_size",
            "expected_f_tokens",
            "expected_g_tokens",
            "expected_n_seq_max",
            "expected_prefix_tokens",
            "expected_source_tokens",
            "experiment_id",
            "fourier_value_orbit_action",
            "g_variants",
            "id",
            "key_value_orbit_attention_action",
            "label_orbit_attention_action",
            "label_token_offsets",
            "lifting_f_key_offsets",
            "lifting_f_value_offsets",
            "lifting_g_key_offsets",
            "lifting_g_value_offsets",
            "model_weight_value_orbit_action",
            "module_f",
            "open_f_prefix_nonlinear_composition",
            "orbit_attention_layers",
            "output_continuous_soft_role_rematerialization_action",
            "output_depth_resolved_cross_attention_memory_action",
            "output_promoted_value_carrier_action",
            "output_promotion_label_indices",
            "output_role_generator_action",
            "output_role_transport_action",
            "output_source_position_fixed_cell_rematerialization_action",
            "output_source_position_rematerialization_action",
            "physical_operator",
            "predecessor_evidence",
            "prefix",
            "queries_per_variant",
            "require_unified_kv",
            "schema_version",
            "source_conditioned_lifting_action",
            "sparse_g_label_refresh",
            "structural_module_f",
            "structural_module_g",
            "subspace_value_orbit_action",
            "trained_semantic_carrier_action",
            "unrelated_query",
            "unrelated_source",
            "value_orbit_attention_action",
        };
        for (const auto & [key, value] : spec.items()) {
            (void) value;
            if (lifting_fields.find(key) == lifting_fields.end()) {
                throw std::runtime_error(
                    "unknown source-conditioned lifting field: " + key);
            }
        }
    }
    return result;
}

predecessor_receipt verify_declared_predecessor(
        const json & spec,
        const std::filesystem::path & registry_path) {
    if (!spec.contains("predecessor_evidence")) {
        return {};
    }
    const auto registry_bytes = read_all(registry_path);
    const json registry = json::parse(registry_bytes);
    const std::string spec_id = spec.at("id").get<std::string>();
    if (!registry.contains(spec_id)) {
        throw std::runtime_error(
            "predecessor lock registry has no entry for " + spec_id);
    }
    const json & declaration = spec.at("predecessor_evidence");
    const json & lock = registry.at(spec_id);
    for (const char * field : {"path", "classification"}) {
        if (declaration.at(field) != lock.at(field)) {
            throw std::runtime_error(
                std::string("predecessor declaration mismatch: ") + field);
        }
    }
    const std::filesystem::path repository_root =
        registry_path.parent_path().parent_path();
    const std::filesystem::path evidence_path =
        repository_root / declaration.at("path").get<std::string>();
    const auto bytes = read_all(evidence_path);
    const std::string digest = sha256_hex(bytes.data(), bytes.size());
    if (bytes.size() != lock.at("bytes").get<size_t>() ||
        digest != lock.at("sha256").get<std::string>()) {
        throw std::runtime_error(
            "predecessor evidence byte/hash identity mismatch");
    }
    const json predecessor = json::parse(bytes);
    const json::json_pointer pointer(
        lock.at("classification_pointer").get<std::string>());
    if (!predecessor.contains(pointer) ||
        predecessor.at(pointer) != declaration.at("classification")) {
        throw std::runtime_error(
            "predecessor evidence classification mismatch");
    }
    return {
        evidence_path,
        bytes.size(),
        digest,
        declaration.at("classification").get<std::string>(),
    };
}

void factor_digest_update(
        factor_payload_digest & digest,
        const void * data,
        size_t size,
        uint64_t public_tag) {
    const auto mix = [&](uint8_t value) {
        digest.fnv1a64 ^= value;
        digest.fnv1a64 *= UINT64_C(1099511628211);
    };
    for (size_t i = 0; i < sizeof(public_tag); ++i) {
        mix(static_cast<uint8_t>(
            (public_tag >> (8u * i)) & 0xffu));
    }
    const auto * bytes = static_cast<const uint8_t *>(data);
    for (size_t i = 0; i < size; ++i) {
        mix(bytes[i]);
        digest.nonzero_bytes += bytes[i] != 0;
    }
    digest.bytes += size;
}

std::string hex64(uint64_t value) {
    std::ostringstream stream;
    stream << std::hex << std::setfill('0') << std::setw(16) << value;
    return stream.str();
}

} // namespace neo3000::evidence
