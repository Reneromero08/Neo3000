#include "arg.h"
#include "common.h"
#include "llama.h"
#include "llama-context.h"
#include "llama-memory-hybrid.h"
#include "llama-model.h"
#include "log.h"

#include "ggml-backend.h"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using json = nlohmann::ordered_json;

namespace {

constexpr llama_state_seq_flags RECURRENT_DEVICE_FLAGS =
    LLAMA_STATE_SEQ_FLAGS_PARTIAL_ONLY | LLAMA_STATE_SEQ_FLAGS_ON_DEVICE;
constexpr llama_state_seq_flags FULL_DEVICE_FLAGS =
    LLAMA_STATE_SEQ_FLAGS_ON_DEVICE;
constexpr llama_state_seq_flags ATTENTION_DEVICE_FLAGS =
    LLAMA_STATE_SEQ_FLAGS_ATTENTION_ONLY | LLAMA_STATE_SEQ_FLAGS_ON_DEVICE;

struct boundary_result {
    json record;
    std::vector<float> candidate_logits;
    std::string argmax;
    uint64_t full_logits_fnv1a64 = 0;
};

struct device_root {
    std::string variant;
    llama_seq_id key = -1;
    llama_state_seq_flags flags = 0;
    size_t source_tokens = 0;
    std::vector<uint8_t> metadata;
    size_t resident_bytes = 0;
    size_t gpu_bytes = 0;
    size_t allocation_bytes = 0;
    size_t allocation_gpu_bytes = 0;
    uint64_t backing_id = 0;
};

static void print_usage(int, char ** argv) {
    LOG("\nusage:\n");
    LOG("\n  %s -m MODEL -f SPEC.json -o RESULT.json\n\n", argv[0]);
}

static uint64_t fnv1a64(const void * data, size_t len) {
    const auto * bytes = static_cast<const uint8_t *>(data);
    uint64_t hash = UINT64_C(1469598103934665603);
    for (size_t i = 0; i < len; ++i) {
        hash ^= bytes[i];
        hash *= UINT64_C(1099511628211);
    }
    return hash;
}

static void fnv1a64_update(uint64_t & hash, const void * data, size_t len) {
    const auto * bytes = static_cast<const uint8_t *>(data);
    for (size_t i = 0; i < len; ++i) {
        hash ^= bytes[i];
        hash *= UINT64_C(1099511628211);
    }
}

static void fnv_mix_u64(uint64_t & hash, uint64_t value) {
    for (size_t i = 0; i < sizeof(value); ++i) {
        hash ^= (value >> (i * 8)) & UINT64_C(0xff);
        hash *= UINT64_C(1099511628211);
    }
}

static std::string hex64(uint64_t value) {
    std::ostringstream stream;
    stream << std::hex << std::setfill('0') << std::setw(16) << value;
    return stream.str();
}

static llama_memory_hybrid * require_hybrid_memory(llama_context * ctx) {
    auto * hybrid = dynamic_cast<llama_memory_hybrid *>(ctx->get_memory());
    if (!hybrid) {
        throw std::runtime_error("model context is not the non-SWA hybrid memory required by this probe");
    }
    return hybrid;
}

static uint64_t active_recurrent_backing_id(llama_context * ctx) {
    auto * recurrent = require_hybrid_memory(ctx)->get_mem_recr();
    std::set<ggml_backend_buffer_t> unique;
    for (ggml_tensor * tensor : recurrent->r_l) {
        if (tensor && tensor->buffer) {
            unique.insert(tensor->buffer);
        }
    }
    for (ggml_tensor * tensor : recurrent->s_l) {
        if (tensor && tensor->buffer) {
            unique.insert(tensor->buffer);
        }
    }

    uint64_t hash = UINT64_C(1469598103934665603);
    for (ggml_backend_buffer_t buffer : unique) {
        fnv_mix_u64(hash, reinterpret_cast<uintptr_t>(buffer));
        fnv_mix_u64(hash, ggml_backend_buffer_get_size(buffer));
    }
    return hash;
}

static uint64_t active_attention_backing_id(llama_context * ctx) {
    auto * attention = require_hybrid_memory(ctx)->get_mem_attn();
    std::set<ggml_backend_buffer_t> unique;
    for (const uint32_t il : attention->get_layer_ids()) {
        ggml_tensor * tensor = attention->get_k_storage(static_cast<int32_t>(il));
        if (tensor && tensor->buffer) {
            unique.insert(tensor->buffer);
        }
    }

    uint64_t hash = UINT64_C(1469598103934665603);
    for (ggml_backend_buffer_t buffer : unique) {
        fnv_mix_u64(hash, reinterpret_cast<uintptr_t>(buffer));
        fnv_mix_u64(hash, ggml_backend_buffer_get_size(buffer));
    }
    return hash;
}

static uint64_t retained_root_backing_id(llama_context * ctx, llama_seq_id key) {
    return llama_state_seq_get_device_backing_id(ctx, key);
}

static std::vector<llama_token> candidate_tokens(const llama_vocab * vocab) {
    std::vector<llama_token> result;
    for (const char * label : {"A", "B", "C", "D"}) {
        auto tokens = common_tokenize(vocab, label, false, false);
        if (tokens.size() != 1) {
            throw std::runtime_error(std::string("candidate label is not one token: ") + label);
        }
        result.push_back(tokens[0]);
    }
    return result;
}

static void decode_tokens(
        llama_context * ctx,
        const std::vector<llama_token> & tokens,
        llama_pos start_pos,
        bool terminal_logits) {
    if (tokens.empty()) {
        return;
    }
    auto batch = llama_batch_init(static_cast<int32_t>(tokens.size()), 0, 1);
    for (size_t i = 0; i < tokens.size(); ++i) {
        common_batch_add(
            batch,
            tokens[i],
            start_pos + static_cast<llama_pos>(i),
            {0},
            terminal_logits && i + 1 == tokens.size());
    }
    const int status = llama_decode(ctx, batch);
    llama_batch_free(batch);
    if (status != 0) {
        throw std::runtime_error("llama_decode failed with status " + std::to_string(status));
    }
}

static std::vector<llama_token> tokenize_piece(
        const llama_vocab * vocab,
        const std::string & text,
        bool add_special,
        bool parse_special = true) {
    auto tokens = common_tokenize(vocab, text, add_special, parse_special);
    if (tokens.empty() && !text.empty()) {
        throw std::runtime_error("nonempty source piece tokenized to zero tokens");
    }
    return tokens;
}

static std::vector<llama_token> prepare_source(
        llama_context * ctx,
        const llama_vocab * vocab,
        const json & source) {
    llama_memory_clear(llama_get_memory(ctx), true);

    std::vector<llama_token> all;
    llama_pos pos = 0;
    bool first = true;
    for (const char * field : {"prefix", "module_f", "module_g", "closure"}) {
        const std::string text = source.at(field).get<std::string>();
        auto tokens = tokenize_piece(vocab, text, first, true);
        decode_tokens(ctx, tokens, pos, false);
        pos += static_cast<llama_pos>(tokens.size());
        all.insert(all.end(), tokens.begin(), tokens.end());
        first = false;
    }
    llama_synchronize(ctx);
    return all;
}

static device_root save_root(
        llama_context * ctx,
        const std::string & variant,
        llama_seq_id key,
        llama_state_seq_flags flags,
        size_t source_tokens) {
    device_root root;
    root.variant = variant;
    root.key = key;
    root.flags = flags;
    root.source_tokens = source_tokens;
    const size_t metadata_size = llama_state_seq_get_size_ext(ctx, 0, flags);
    if (metadata_size == 0) {
        throw std::runtime_error("state metadata size is zero for " + variant);
    }
    root.metadata.resize(metadata_size);
    const size_t written = llama_state_seq_get_data_ext_keyed(
        ctx, root.metadata.data(), root.metadata.size(), 0, key, flags);
    llama_synchronize(ctx);
    if (written != root.metadata.size()) {
        llama_state_seq_clear_device_data(ctx, key);
        throw std::runtime_error("state metadata write mismatch for " + variant);
    }
    root.resident_bytes = llama_state_seq_get_device_data_size(ctx, key);
    root.gpu_bytes = llama_state_seq_get_device_data_gpu_size(ctx, key);
    root.allocation_bytes = llama_state_seq_get_device_allocation_size(ctx, key);
    root.allocation_gpu_bytes =
        llama_state_seq_get_device_allocation_gpu_size(ctx, key);
    root.backing_id = retained_root_backing_id(ctx, key);
    if (root.resident_bytes == 0 ||
        root.gpu_bytes == 0 ||
        root.allocation_bytes == 0 ||
        root.allocation_gpu_bytes == 0 ||
        root.backing_id == 0) {
        llama_state_seq_clear_device_data(ctx, key);
        throw std::runtime_error("device root is not physically resident for " + variant);
    }
    return root;
}

static void restore_root(llama_context * ctx, const device_root & root) {
    llama_memory_clear(llama_get_memory(ctx), true);
    const size_t read = llama_state_seq_set_data_ext(
        ctx, root.metadata.data(), root.metadata.size(), 0, root.flags);
    llama_synchronize(ctx);
    if (read != root.metadata.size()) {
        llama_memory_clear(llama_get_memory(ctx), true);
        llama_synchronize(ctx);
        throw std::runtime_error("state metadata restore mismatch for " + root.variant);
    }
    if (llama_state_seq_get_device_data_size(ctx, root.key) != root.resident_bytes ||
        llama_state_seq_get_device_data_gpu_size(ctx, root.key) != root.gpu_bytes ||
        llama_state_seq_get_device_allocation_size(ctx, root.key) != root.allocation_bytes ||
        llama_state_seq_get_device_allocation_gpu_size(ctx, root.key) != root.allocation_gpu_bytes ||
        retained_root_backing_id(ctx, root.key) != root.backing_id) {
        llama_memory_clear(llama_get_memory(ctx), true);
        llama_synchronize(ctx);
        throw std::runtime_error("retained root backing changed during restore for " + root.variant);
    }
}

static void restore_attention_root(llama_context * ctx, const device_root & root) {
    if (root.flags != ATTENTION_DEVICE_FLAGS) {
        llama_memory_clear(llama_get_memory(ctx), true);
        llama_synchronize(ctx);
        throw std::runtime_error("non-attention root passed to attention-only restore");
    }
    const size_t read = llama_state_seq_set_data_ext(
        ctx, root.metadata.data(), root.metadata.size(), 0, root.flags);
    llama_synchronize(ctx);
    if (read != root.metadata.size()) {
        llama_memory_clear(llama_get_memory(ctx), true);
        llama_synchronize(ctx);
        throw std::runtime_error(
            "attention state metadata restore mismatch for " + root.variant);
    }
    if (llama_state_seq_get_device_data_size(ctx, root.key) != root.resident_bytes ||
        llama_state_seq_get_device_data_gpu_size(ctx, root.key) != root.gpu_bytes ||
        llama_state_seq_get_device_allocation_size(ctx, root.key) != root.allocation_bytes ||
        llama_state_seq_get_device_allocation_gpu_size(ctx, root.key) != root.allocation_gpu_bytes ||
        retained_root_backing_id(ctx, root.key) != root.backing_id) {
        llama_memory_clear(llama_get_memory(ctx), true);
        llama_synchronize(ctx);
        throw std::runtime_error(
            "attention root backing changed during restore for " + root.variant);
    }
}

static boundary_result decode_query(
        llama_context * ctx,
        const llama_vocab * vocab,
        const std::vector<llama_token> & candidates,
        const std::string & route,
        const std::string & variant,
        const json & query,
        size_t source_tokens,
        uint64_t root_backing_id,
        size_t root_gpu_bytes) {
    const std::string text = query.at("suffix").get<std::string>();
    auto tokens = tokenize_piece(vocab, text, false, true);

    const auto started = std::chrono::steady_clock::now();
    decode_tokens(ctx, tokens, static_cast<llama_pos>(source_tokens), true);
    llama_synchronize(ctx);
    const auto finished = std::chrono::steady_clock::now();

    const float * logits = llama_get_logits_ith(ctx, -1);
    if (!logits) {
        throw std::runtime_error("query produced no terminal logits");
    }

    const int32_t n_vocab = llama_vocab_n_tokens(vocab);
    boundary_result result;
    result.full_logits_fnv1a64 = fnv1a64(logits, static_cast<size_t>(n_vocab) * sizeof(float));
    result.candidate_logits.reserve(candidates.size());

    float max_logit = -std::numeric_limits<float>::infinity();
    size_t max_index = 0;
    for (size_t i = 0; i < candidates.size(); ++i) {
        const float value = logits[candidates[i]];
        result.candidate_logits.push_back(value);
        if (value > max_logit) {
            max_logit = value;
            max_index = i;
        }
    }
    result.argmax = std::string(1, static_cast<char>('A' + max_index));

    double probability_sum = 0.0;
    std::vector<double> probabilities;
    for (float value : result.candidate_logits) {
        const double probability = std::exp(static_cast<double>(value - max_logit));
        probabilities.push_back(probability);
        probability_sum += probability;
    }
    for (double & value : probabilities) {
        value /= probability_sum;
    }

    result.record = {
        {"query_id", query.at("id")},
        {"route", route},
        {"source_variant", variant},
        {"expected", query.at("expected")},
        {"expected_mutated", query.value(
            "expected_mutated",
            query.at("expected").get<std::string>())},
        {"source_tokens", source_tokens},
        {"query_tokens", tokens.size()},
        {"candidate_logits", result.candidate_logits},
        {"candidate_softmax", probabilities},
        {"candidate_argmax", result.argmax},
        {"full_logits_fnv1a64", hex64(result.full_logits_fnv1a64)},
        {"root_backing_id", hex64(root_backing_id)},
        {"root_gpu_bytes", root_gpu_bytes},
        {"active_recurrent_backing_id", hex64(active_recurrent_backing_id(ctx))},
        {"wall_ms", std::chrono::duration<double, std::milli>(finished - started).count()},
    };
    return result;
}

static json interaction_record(
        const boundary_result & f0g0,
        const boundary_result & f1g0,
        const boundary_result & f0g1,
        const boundary_result & f1g1) {
    json values = json::object();
    double norm2 = 0.0;
    for (size_t i = 0; i < 4; ++i) {
        const double value =
            static_cast<double>(f1g1.candidate_logits[i])
            - static_cast<double>(f1g0.candidate_logits[i])
            - static_cast<double>(f0g1.candidate_logits[i])
            + static_cast<double>(f0g0.candidate_logits[i]);
        values[std::string(1, static_cast<char>('A' + i))] = value;
        norm2 += value * value;
    }
    return {
        {"candidate_logit_interaction", values},
        {"l2_norm", std::sqrt(norm2)},
    };
}

struct hybrid_tensor_reference {
    std::map<uint32_t, std::vector<uint8_t>> attention_k;
    std::map<uint32_t, std::vector<uint8_t>> attention_v;
    std::map<uint32_t, std::vector<uint8_t>> recurrent_r;
    std::map<uint32_t, std::vector<uint8_t>> recurrent_s;
    size_t host_bytes = 0;
};

static std::vector<uint8_t> read_tensor(ggml_tensor * tensor) {
    if (!tensor) {
        return {};
    }
    std::vector<uint8_t> bytes(ggml_nbytes(tensor));
    ggml_backend_tensor_get(tensor, bytes.data(), 0, bytes.size());
    return bytes;
}

static void write_tensor(ggml_tensor * tensor, const std::vector<uint8_t> & bytes) {
    if (!tensor && bytes.empty()) {
        return;
    }
    if (!tensor || bytes.size() != ggml_nbytes(tensor)) {
        throw std::runtime_error("matched tensor reference shape mismatch");
    }
    ggml_backend_tensor_set(tensor, bytes.data(), 0, bytes.size());
}

static hybrid_tensor_reference capture_hybrid_reference(llama_context * ctx) {
    auto * hybrid = require_hybrid_memory(ctx);
    auto * attention = hybrid->get_mem_attn();
    auto * recurrent = hybrid->get_mem_recr();
    hybrid_tensor_reference reference;

    for (const uint32_t il : attention->get_layer_ids()) {
        reference.attention_k[il] =
            read_tensor(attention->get_k_storage(static_cast<int32_t>(il)));
        reference.attention_v[il] =
            read_tensor(attention->get_v_storage(static_cast<int32_t>(il)));
        reference.host_bytes +=
            reference.attention_k.at(il).size() +
            reference.attention_v.at(il).size();
    }
    for (uint32_t il = 0; il < recurrent->r_l.size(); ++il) {
        if (recurrent->r_l[il]) {
            reference.recurrent_r[il] = read_tensor(recurrent->r_l[il]);
            reference.host_bytes += reference.recurrent_r.at(il).size();
        }
        if (recurrent->s_l[il]) {
            reference.recurrent_s[il] = read_tensor(recurrent->s_l[il]);
            reference.host_bytes += reference.recurrent_s.at(il).size();
        }
    }
    return reference;
}

struct streamed_tensor_hash {
    uint64_t value = UINT64_C(1469598103934665603);
    size_t transferred_bytes = 0;
    size_t peak_host_work_bytes = 0;
};

static void hash_tensor_streamed(
        streamed_tensor_hash & hash,
        ggml_tensor * tensor,
        uint64_t layer,
        uint64_t kind) {
    if (!tensor) {
        return;
    }
    const size_t chunk_capacity = 1024 * 1024;
    std::vector<uint8_t> work(std::min(chunk_capacity, ggml_nbytes(tensor)));
    fnv_mix_u64(hash.value, layer);
    fnv_mix_u64(hash.value, kind);
    fnv_mix_u64(hash.value, ggml_nbytes(tensor));
    if (ggml_nbytes(tensor) == 0) {
        return;
    }
    for (size_t offset = 0; offset < ggml_nbytes(tensor); offset += work.size()) {
        const size_t size = std::min(work.size(), ggml_nbytes(tensor) - offset);
        ggml_backend_tensor_get(tensor, work.data(), offset, size);
        fnv1a64_update(hash.value, work.data(), size);
        hash.transferred_bytes += size;
    }
    hash.peak_host_work_bytes = std::max(hash.peak_host_work_bytes, work.size());
}

static streamed_tensor_hash hash_recurrent_state_streamed(llama_context * ctx) {
    llama_synchronize(ctx);
    auto * recurrent = require_hybrid_memory(ctx)->get_mem_recr();
    streamed_tensor_hash hash;
    for (uint32_t il = 0; il < recurrent->r_l.size(); ++il) {
        hash_tensor_streamed(hash, recurrent->r_l[il], il, 0);
        hash_tensor_streamed(hash, recurrent->s_l[il], il, 1);
    }
    return hash;
}

static std::set<uint32_t> parse_layer_selection(
        const json & arm,
        const char * field,
        const std::vector<uint32_t> & available) {
    const auto & value = arm.at(field);
    if (value.is_string() && value.get<std::string>() == "ALL") {
        return {available.begin(), available.end()};
    }
    if (!value.is_array()) {
        throw std::runtime_error(std::string(field) + " must be ALL or an array");
    }

    const std::set<uint32_t> allowed(available.begin(), available.end());
    std::set<uint32_t> selected;
    for (const auto & item : value) {
        const uint32_t il = item.get<uint32_t>();
        if (allowed.find(il) == allowed.end()) {
            throw std::runtime_error(
                std::string(field) + " contains unavailable layer " + std::to_string(il));
        }
        if (!selected.insert(il).second) {
            throw std::runtime_error(
                std::string(field) + " contains duplicate layer " + std::to_string(il));
        }
    }
    return selected;
}

static size_t attention_source_bytes(
        llama_kv_cache * attention,
        const std::set<uint32_t> & selected,
        size_t source_tokens) {
    const size_t cache_size = attention->get_size();
    size_t bytes = 0;
    for (const uint32_t il : selected) {
        for (ggml_tensor * tensor : {
                attention->get_k_storage(static_cast<int32_t>(il)),
                attention->get_v_storage(static_cast<int32_t>(il))}) {
            if (!tensor || ggml_nbytes(tensor) % cache_size != 0) {
                throw std::runtime_error("attention storage is not row-divisible");
            }
            bytes += ggml_nbytes(tensor) / cache_size * source_tokens;
        }
    }
    return bytes;
}

static size_t recurrent_source_bytes(
        llama_memory_recurrent * recurrent,
        const std::set<uint32_t> & selected) {
    size_t bytes = 0;
    for (const uint32_t il : selected) {
        if (recurrent->r_l[il]) {
            bytes += ggml_nbytes(recurrent->r_l[il]);
        }
        if (recurrent->s_l[il]) {
            bytes += ggml_nbytes(recurrent->s_l[il]);
        }
    }
    return bytes;
}

static size_t apply_matched_layer_substitution(
        llama_context * ctx,
        const hybrid_tensor_reference & reference,
        const std::set<uint32_t> & attention_selected,
        const std::set<uint32_t> & recurrent_selected) {
    auto * hybrid = require_hybrid_memory(ctx);
    auto * attention = hybrid->get_mem_attn();
    auto * recurrent = hybrid->get_mem_recr();
    size_t transferred_bytes = 0;

    for (const uint32_t il : attention->get_layer_ids()) {
        if (attention_selected.find(il) == attention_selected.end()) {
            write_tensor(
                attention->get_k_storage(static_cast<int32_t>(il)),
                reference.attention_k.at(il));
            write_tensor(
                attention->get_v_storage(static_cast<int32_t>(il)),
                reference.attention_v.at(il));
            transferred_bytes +=
                reference.attention_k.at(il).size() +
                reference.attention_v.at(il).size();
        }
    }
    for (uint32_t il = 0; il < recurrent->r_l.size(); ++il) {
        if ((recurrent->r_l[il] || recurrent->s_l[il]) &&
            recurrent_selected.find(il) == recurrent_selected.end()) {
            if (recurrent->r_l[il]) {
                write_tensor(recurrent->r_l[il], reference.recurrent_r.at(il));
                transferred_bytes += reference.recurrent_r.at(il).size();
            }
            if (recurrent->s_l[il]) {
                write_tensor(recurrent->s_l[il], reference.recurrent_s.at(il));
                transferred_bytes += reference.recurrent_s.at(il).size();
            }
        }
    }
    llama_synchronize(ctx);
    return transferred_bytes;
}

static json run_layer_localization(
        llama_context * ctx,
        const llama_vocab * vocab,
        const std::vector<llama_token> & candidates,
        const json & spec,
        uint64_t active_recurrent_backing_initial,
        uint64_t active_attention_backing_initial) {
    auto * hybrid = require_hybrid_memory(ctx);
    auto * attention = hybrid->get_mem_attn();
    auto * recurrent = hybrid->get_mem_recr();

    const std::vector<uint32_t> attention_layers = attention->get_layer_ids();
    std::vector<uint32_t> recurrent_layers;
    for (uint32_t il = 0; il < recurrent->r_l.size(); ++il) {
        if (recurrent->r_l[il] || recurrent->s_l[il]) {
            recurrent_layers.push_back(il);
        }
    }
    if (attention_layers != spec.at("expected_attention_layers").get<std::vector<uint32_t>>() ||
        recurrent_layers != spec.at("expected_recurrent_layers").get<std::vector<uint32_t>>()) {
        throw std::runtime_error("model hybrid layer topology differs from frozen spec");
    }

    const auto & source = spec.at("source");
    const auto substitution_tokens =
        prepare_source(ctx, vocab, spec.at("substitution_source"));
    if (attention->seq_pos_max(0) !=
            static_cast<llama_pos>(substitution_tokens.size() - 1) ||
        recurrent->seq_pos_max(0) !=
            static_cast<llama_pos>(substitution_tokens.size() - 1)) {
        throw std::runtime_error("matched substitution source position mismatch");
    }
    const hybrid_tensor_reference reference = capture_hybrid_reference(ctx);
    llama_memory_clear(llama_get_memory(ctx), true);
    llama_synchronize(ctx);
    const auto & queries = spec.at("queries");
    const auto & arms = spec.at("localization_arms");
    json arm_results = json::array();
    json records = json::array();
    llama_seq_id key = 2000;
    size_t common_source_tokens = 0;
    size_t maximum_root_gpu_bytes = 0;
    size_t cleared_root_bytes = 0;
    size_t full_correct = 0;
    size_t best_strict_correct = 0;
    size_t best_strict_source_bytes = std::numeric_limits<size_t>::max();
    std::string best_strict_arm;

    for (const auto & arm : arms) {
        const std::string arm_id = arm.at("id").get<std::string>();
        const auto attention_selected =
            parse_layer_selection(arm, "attention_layers", attention_layers);
        const auto recurrent_selected =
            parse_layer_selection(arm, "recurrent_layers", recurrent_layers);
        const auto source_tokens = prepare_source(ctx, vocab, source);
        if (attention->seq_pos_max(0) !=
                static_cast<llama_pos>(source_tokens.size() - 1) ||
            recurrent->seq_pos_max(0) !=
                static_cast<llama_pos>(source_tokens.size() - 1)) {
            throw std::runtime_error("joint source position mismatch");
        }
        if (common_source_tokens == 0) {
            common_source_tokens = source_tokens.size();
            if (common_source_tokens != substitution_tokens.size()) {
                throw std::runtime_error(
                    "matched substitution source token count differs");
            }
        } else if (common_source_tokens != source_tokens.size()) {
            throw std::runtime_error("localization source token count changed");
        }

        const size_t substitution_h2d_bytes = apply_matched_layer_substitution(
            ctx, reference, attention_selected, recurrent_selected);
        auto root = save_root(
            ctx, arm_id, key++, FULL_DEVICE_FLAGS, source_tokens.size());
        maximum_root_gpu_bytes = std::max(maximum_root_gpu_bytes, root.gpu_bytes);

        size_t correct = 0;
        std::vector<std::string> answers;
        for (const auto & query : queries) {
            restore_root(ctx, root);
            auto boundary = decode_query(
                ctx, vocab, candidates, "hybrid-layer-subset-root", arm_id, query,
                root.source_tokens, root.backing_id, root.gpu_bytes);
            correct += boundary.argmax == query.at("expected").get<std::string>();
            answers.push_back(boundary.argmax);
            records.push_back(boundary.record);
        }

        const size_t attention_bytes =
            attention_source_bytes(attention, attention_selected, source_tokens.size());
        const size_t recurrent_bytes =
            recurrent_source_bytes(recurrent, recurrent_selected);
        const size_t selected_bytes = attention_bytes + recurrent_bytes;
        const bool strict_subset =
            attention_selected.size() < attention_layers.size() ||
            recurrent_selected.size() < recurrent_layers.size();

        arm_results.push_back({
            {"id", arm_id},
            {"attention_layers", attention_selected},
            {"recurrent_layers", recurrent_selected},
            {"attention_source_bytes", attention_bytes},
            {"recurrent_source_bytes", recurrent_bytes},
            {"selected_joint_source_bytes_above_matched_baseline", selected_bytes},
            {"serialized_root_device_tensor_bytes", root.gpu_bytes},
            {"serialized_root_metadata_bytes", root.metadata.size()},
            {"matched_substitution_h2d_bytes", substitution_h2d_bytes},
            {"strict_subset", strict_subset},
            {"correct", correct},
            {"answers", answers},
        });

        if (arm_id == "full") {
            full_correct = correct;
        } else if (strict_subset &&
                   (correct > best_strict_correct ||
                    (correct == best_strict_correct &&
                     selected_bytes < best_strict_source_bytes))) {
            best_strict_correct = correct;
            best_strict_source_bytes = selected_bytes;
            best_strict_arm = arm_id;
        }

        llama_memory_clear(llama_get_memory(ctx), true);
        cleared_root_bytes += llama_state_seq_clear_device_data(ctx, root.key);
        if (llama_state_seq_get_device_data_size(ctx, root.key) != 0) {
            throw std::runtime_error("localization root did not close");
        }
    }

    llama_memory_clear(llama_get_memory(ctx), true);
    llama_synchronize(ctx);
    if (llama_state_seq_get_device_root_count(ctx) != 0 ||
        active_recurrent_backing_id(ctx) != active_recurrent_backing_initial ||
        active_attention_backing_id(ctx) != active_attention_backing_initial) {
        throw std::runtime_error("localization close invariant failed");
    }

    const bool localized = full_correct == queries.size() &&
        best_strict_correct == queries.size();
    return {
        {"schema_version", 1},
        {"mechanism", "QUERY_SEPARATED_HYBRID_LAYER_SUBSET_SCREEN"},
        {"spec_id", spec.at("id")},
        {"model_arch", "qwen35moe"},
        {"configuration", {
            {"source_tokens", common_source_tokens},
            {"substitution_source_tokens", substitution_tokens.size()},
            {"query_count", queries.size()},
            {"arm_count", arms.size()},
            {"attention_layers", attention_layers},
            {"recurrent_layers", recurrent_layers},
        }},
        {"carrier", {
            {"maximum_serialized_root_device_tensor_bytes", maximum_root_gpu_bytes},
            {"cleared_root_bytes", cleared_root_bytes},
            {"all_retained_roots_closed", llama_state_seq_get_device_root_count(ctx) == 0},
            {"active_recurrent_backing_stable",
                active_recurrent_backing_id(ctx) == active_recurrent_backing_initial},
            {"active_attention_backing_stable",
                active_attention_backing_id(ctx) == active_attention_backing_initial},
            {"restoration_class", "SNAPSHOT_RELOAD"},
            {"physical_reduction_implemented", false},
            {"backend_allocation_bytes_measured", false},
            {"matched_reference_host_bytes", reference.host_bytes},
            {"omitted_layer_law", "F0_G0 full-tensor substitution at identical source positions"},
        }},
        {"arms", arm_results},
        {"records", records},
        {"summary", {
            {"full_correct", full_correct},
            {"best_strict_correct", best_strict_correct},
            {"best_strict_arm", best_strict_arm},
            {"best_strict_selected_joint_source_bytes_above_matched_baseline",
                best_strict_source_bytes == std::numeric_limits<size_t>::max() ?
                    0 : best_strict_source_bytes},
            {"strict_subset_localized", localized},
        }},
        {"verdict", localized ? "screen-pass" : "screen-no-sufficient-subset"},
        {"claim_ceiling", spec.at("claim_ceiling")},
    };
}

static size_t semantic_correct_count(
        const std::vector<boundary_result> & results,
        const json & queries,
        bool mutated) {
    size_t correct = 0;
    for (size_t i = 0; i < results.size(); ++i) {
        const std::string expected = mutated
            ? queries.at(i).at("expected_mutated").get<std::string>()
            : queries.at(i).at("expected").get<std::string>();
        correct += results.at(i).argmax == expected;
    }
    return correct;
}

static json semantic_route_summary(
        const std::map<std::string, std::vector<boundary_result>> & route,
        const json & queries) {
    json summary = json::object();
    for (const auto & [variant, results] : route) {
        std::vector<std::string> answers;
        for (const auto & result : results) {
            answers.push_back(result.argmax);
        }
        summary[variant] = {
            {"answers", answers},
            {"correct", semantic_correct_count(
                results, queries, variant == "F1_G_MUT")},
        };
    }
    return summary;
}

static size_t boundary_changes(
        const std::vector<boundary_result> & lhs,
        const std::vector<boundary_result> & rhs) {
    if (lhs.size() != rhs.size()) {
        throw std::runtime_error("boundary comparison cardinality mismatch");
    }
    size_t changes = 0;
    for (size_t i = 0; i < lhs.size(); ++i) {
        changes += lhs.at(i).argmax != rhs.at(i).argmax;
    }
    return changes;
}

static size_t boundary_matches(
        const std::vector<boundary_result> & lhs,
        const std::vector<boundary_result> & rhs) {
    return lhs.size() - boundary_changes(lhs, rhs);
}

static json run_matched_semantic_validation(
        llama_context * ctx,
        const llama_vocab * vocab,
        const std::vector<llama_token> & candidates,
        const json & spec,
        uint64_t active_recurrent_backing_initial,
        uint64_t active_attention_backing_initial) {
    auto * hybrid = require_hybrid_memory(ctx);
    auto * attention = hybrid->get_mem_attn();
    auto * recurrent = hybrid->get_mem_recr();

    const std::vector<uint32_t> attention_layers = attention->get_layer_ids();
    std::vector<uint32_t> recurrent_layers;
    for (uint32_t il = 0; il < recurrent->r_l.size(); ++il) {
        if (recurrent->r_l[il] || recurrent->s_l[il]) {
            recurrent_layers.push_back(il);
        }
    }
    if (attention_layers != spec.at("expected_attention_layers").get<std::vector<uint32_t>>() ||
        recurrent_layers != spec.at("expected_recurrent_layers").get<std::vector<uint32_t>>()) {
        throw std::runtime_error("model hybrid layer topology differs from semantic spec");
    }

    const auto & sources = spec.at("sources");
    const std::vector<std::string> variants = {
        "F0_G0", "F1_G0", "F0_G1", "F1_G1", "F1_G_MUT", "F1_G_PRESENTATION"
    };
    for (const auto & variant : variants) {
        if (!sources.contains(variant)) {
            throw std::runtime_error("semantic spec missing source variant " + variant);
        }
    }

    const auto reference_tokens = prepare_source(ctx, vocab, sources.at("F0_G0"));
    if (attention->seq_pos_max(0) !=
            static_cast<llama_pos>(reference_tokens.size() - 1) ||
        recurrent->seq_pos_max(0) !=
            static_cast<llama_pos>(reference_tokens.size() - 1)) {
        throw std::runtime_error("semantic reference position mismatch");
    }
    const hybrid_tensor_reference reference = capture_hybrid_reference(ctx);
    llama_memory_clear(llama_get_memory(ctx), true);
    llama_synchronize(ctx);

    const std::set<uint32_t> all_attention(
        attention_layers.begin(), attention_layers.end());
    const std::set<uint32_t> all_recurrent(
        recurrent_layers.begin(), recurrent_layers.end());
    const std::set<uint32_t> no_layers;
    const auto & queries = spec.at("queries");
    std::map<std::string, std::vector<boundary_result>> full_results;
    std::map<std::string, std::vector<boundary_result>> attention_delta_results;
    std::map<std::string, std::vector<boundary_result>> recurrent_delta_results;
    json records = json::array();
    json roots = json::array();
    llama_seq_id key = 3000;
    size_t common_source_tokens = 0;
    size_t maximum_simultaneous_root_device_tensor_bytes = 0;
    size_t cleared_root_bytes = 0;
    size_t recurrent_substitution_h2d_bytes = 0;
    size_t attention_substitution_h2d_bytes = 0;

    for (const auto & variant : variants) {
        const auto source_tokens = prepare_source(ctx, vocab, sources.at(variant));
        if (attention->seq_pos_max(0) !=
                static_cast<llama_pos>(source_tokens.size() - 1) ||
            recurrent->seq_pos_max(0) !=
                static_cast<llama_pos>(source_tokens.size() - 1)) {
            throw std::runtime_error("semantic source position mismatch");
        }
        if (common_source_tokens == 0) {
            common_source_tokens = source_tokens.size();
            if (common_source_tokens != reference_tokens.size()) {
                throw std::runtime_error("semantic source/reference token count mismatch");
            }
        } else if (common_source_tokens != source_tokens.size()) {
            throw std::runtime_error("semantic source token count changed");
        }

        auto full_root = save_root(
            ctx, variant + ":full", key++, FULL_DEVICE_FLAGS, source_tokens.size());
        restore_root(ctx, full_root);
        recurrent_substitution_h2d_bytes += apply_matched_layer_substitution(
            ctx, reference, all_attention, no_layers);
        auto attention_delta_root = save_root(
            ctx, variant + ":attention-delta", key++, FULL_DEVICE_FLAGS,
            source_tokens.size());
        restore_root(ctx, full_root);
        attention_substitution_h2d_bytes += apply_matched_layer_substitution(
            ctx, reference, no_layers, all_recurrent);
        auto recurrent_delta_root = save_root(
            ctx, variant + ":recurrent-delta", key++, FULL_DEVICE_FLAGS,
            source_tokens.size());

        maximum_simultaneous_root_device_tensor_bytes = std::max(
            maximum_simultaneous_root_device_tensor_bytes,
            full_root.gpu_bytes +
                attention_delta_root.gpu_bytes +
                recurrent_delta_root.gpu_bytes);

        const std::vector<std::pair<std::string, device_root *>> route_roots = {
            {"full-hybrid", &full_root},
            {"attention-delta-fixed-recurrent", &attention_delta_root},
            {"recurrent-delta-fixed-attention", &recurrent_delta_root},
        };
        for (const auto & [route, root] : route_roots) {
            auto * destination = route == "full-hybrid"
                ? &full_results
                : route == "attention-delta-fixed-recurrent"
                    ? &attention_delta_results
                    : &recurrent_delta_results;
            for (const auto & query : queries) {
                restore_root(ctx, *root);
                auto boundary = decode_query(
                    ctx, vocab, candidates, route, variant, query,
                    root->source_tokens, root->backing_id, root->gpu_bytes);
                records.push_back(boundary.record);
                (*destination)[variant].push_back(std::move(boundary));
            }
        }

        llama_memory_clear(llama_get_memory(ctx), true);
        for (const auto & [route, root] : route_roots) {
            roots.push_back({
                {"route", route},
                {"source_variant", variant},
                {"serialized_root_device_tensor_bytes", root->gpu_bytes},
                {"serialized_root_metadata_bytes", root->metadata.size()},
                {"root_backing_id", hex64(root->backing_id)},
            });
            cleared_root_bytes += llama_state_seq_clear_device_data(ctx, root->key);
            if (llama_state_seq_get_device_data_size(ctx, root->key) != 0) {
                throw std::runtime_error("semantic validation root did not close");
            }
        }
    }

    llama_memory_clear(llama_get_memory(ctx), true);
    llama_synchronize(ctx);
    if (llama_state_seq_get_device_root_count(ctx) != 0 ||
        active_recurrent_backing_id(ctx) != active_recurrent_backing_initial ||
        active_attention_backing_id(ctx) != active_attention_backing_initial) {
        throw std::runtime_error("semantic validation close invariant failed");
    }

    const auto & acceptance = spec.at("acceptance_law");
    const size_t attention_joint_correct = semantic_correct_count(
        attention_delta_results.at("F1_G1"), queries, false);
    const size_t attention_f_only_correct = semantic_correct_count(
        attention_delta_results.at("F1_G0"), queries, false);
    const size_t attention_g_only_correct = semantic_correct_count(
        attention_delta_results.at("F0_G1"), queries, false);
    const size_t attention_null_correct = semantic_correct_count(
        attention_delta_results.at("F0_G0"), queries, false);
    const size_t attention_mutated_correct = semantic_correct_count(
        attention_delta_results.at("F1_G_MUT"), queries, true);
    const size_t attention_presentation_correct = semantic_correct_count(
        attention_delta_results.at("F1_G_PRESENTATION"), queries, false);
    const size_t attention_mutation_changes = boundary_changes(
        attention_delta_results.at("F1_G1"),
        attention_delta_results.at("F1_G_MUT"));
    const size_t attention_presentation_matches = boundary_matches(
        attention_delta_results.at("F1_G1"),
        attention_delta_results.at("F1_G_PRESENTATION"));
    const size_t recurrent_joint_correct = semantic_correct_count(
        recurrent_delta_results.at("F1_G1"), queries, false);
    const size_t full_joint_correct = semantic_correct_count(
        full_results.at("F1_G1"), queries, false);

    const bool accepted =
        attention_joint_correct >= acceptance.at("attention_joint_correct_minimum").get<size_t>() &&
        attention_f_only_correct <= acceptance.at("attention_f_only_correct_maximum").get<size_t>() &&
        attention_g_only_correct <= acceptance.at("attention_g_only_correct_maximum").get<size_t>() &&
        attention_null_correct <= acceptance.at("attention_null_correct_maximum").get<size_t>() &&
        attention_mutated_correct >= acceptance.at("attention_mutated_correct_minimum").get<size_t>() &&
        attention_presentation_correct >= acceptance.at("attention_presentation_correct_minimum").get<size_t>() &&
        attention_mutation_changes >= acceptance.at("attention_mutation_changes_minimum").get<size_t>() &&
        attention_presentation_matches >= acceptance.at("attention_presentation_matches_minimum").get<size_t>() &&
        recurrent_joint_correct <= acceptance.at("recurrent_joint_correct_maximum").get<size_t>() &&
        full_joint_correct >= acceptance.at("full_joint_correct_minimum").get<size_t>();

    return {
        {"schema_version", 1},
        {"mechanism", "MATCHED_BACKGROUND_ATTENTION_DELTA_SEMANTIC_VALIDATION"},
        {"spec_id", spec.at("id")},
        {"model_arch", "qwen35moe"},
        {"configuration", {
            {"source_tokens", common_source_tokens},
            {"reference_source_tokens", reference_tokens.size()},
            {"query_count", queries.size()},
            {"source_variant_count", variants.size()},
            {"routes_per_variant", 3},
            {"attention_layers", attention_layers},
            {"recurrent_layers", recurrent_layers},
        }},
        {"carrier", {
            {"logical_attention_delta_source_bytes",
                attention_source_bytes(attention, all_attention, common_source_tokens)},
            {"fixed_recurrent_scaffold_tensor_bytes",
                recurrent_source_bytes(recurrent, all_recurrent)},
            {"maximum_simultaneous_serialized_root_device_tensor_bytes",
                maximum_simultaneous_root_device_tensor_bytes},
            {"cleared_root_bytes", cleared_root_bytes},
            {"matched_reference_host_bytes", reference.host_bytes},
            {"recurrent_substitution_h2d_bytes", recurrent_substitution_h2d_bytes},
            {"attention_substitution_h2d_bytes", attention_substitution_h2d_bytes},
            {"all_retained_roots_closed", llama_state_seq_get_device_root_count(ctx) == 0},
            {"active_recurrent_backing_stable",
                active_recurrent_backing_id(ctx) == active_recurrent_backing_initial},
            {"active_attention_backing_stable",
                active_attention_backing_id(ctx) == active_attention_backing_initial},
            {"restoration_class", "SNAPSHOT_RELOAD"},
            {"physical_reduction_implemented", false},
            {"backend_allocation_bytes_measured", false},
        }},
        {"route_summaries", {
            {"full_hybrid", semantic_route_summary(full_results, queries)},
            {"attention_delta_fixed_recurrent",
                semantic_route_summary(attention_delta_results, queries)},
            {"recurrent_delta_fixed_attention",
                semantic_route_summary(recurrent_delta_results, queries)},
        }},
        {"summary", {
            {"attention_joint_correct", attention_joint_correct},
            {"attention_f_only_correct", attention_f_only_correct},
            {"attention_g_only_correct", attention_g_only_correct},
            {"attention_null_correct", attention_null_correct},
            {"attention_mutated_correct", attention_mutated_correct},
            {"attention_presentation_correct", attention_presentation_correct},
            {"attention_mutation_changes", attention_mutation_changes},
            {"attention_presentation_matches", attention_presentation_matches},
            {"recurrent_joint_correct", recurrent_joint_correct},
            {"full_joint_correct", full_joint_correct},
            {"semantic_validation_passed", accepted},
        }},
        {"roots", roots},
        {"records", records},
        {"verdict", accepted ? "accept" : "reject"},
        {"claim_ceiling", spec.at("claim_ceiling")},
    };
}

static json run_physical_attention_roots(
        llama_context * ctx,
        const llama_vocab * vocab,
        const std::vector<llama_token> & candidates,
        const json & spec,
        uint64_t active_recurrent_backing_initial,
        uint64_t active_attention_backing_initial) {
    auto * hybrid = require_hybrid_memory(ctx);
    auto * attention = hybrid->get_mem_attn();
    auto * recurrent = hybrid->get_mem_recr();

    const std::vector<uint32_t> attention_layers = attention->get_layer_ids();
    std::vector<uint32_t> recurrent_layers;
    for (uint32_t il = 0; il < recurrent->r_l.size(); ++il) {
        if (recurrent->r_l[il] || recurrent->s_l[il]) {
            recurrent_layers.push_back(il);
        }
    }
    if (attention_layers != spec.at("expected_attention_layers").get<std::vector<uint32_t>>() ||
        recurrent_layers != spec.at("expected_recurrent_layers").get<std::vector<uint32_t>>()) {
        throw std::runtime_error("model hybrid layer topology differs from physical-root spec");
    }

    const auto & sources = spec.at("sources");
    const std::vector<std::string> variants = {
        "F0_G0", "F1_G0", "F0_G1", "F1_G1", "F1_G_MUT", "F1_G_PRESENTATION"
    };
    for (const auto & variant : variants) {
        if (!sources.contains(variant)) {
            throw std::runtime_error("physical-root spec missing source variant " + variant);
        }
    }

    const auto scaffold_tokens = prepare_source(ctx, vocab, sources.at("F0_G0"));
    if (attention->seq_pos_max(0) !=
            static_cast<llama_pos>(scaffold_tokens.size() - 1) ||
        recurrent->seq_pos_max(0) !=
            static_cast<llama_pos>(scaffold_tokens.size() - 1)) {
        throw std::runtime_error("physical recurrent scaffold position mismatch");
    }
    auto scaffold_root = save_root(
        ctx, "F0_G0:recurrent-scaffold", 4000,
        RECURRENT_DEVICE_FLAGS, scaffold_tokens.size());
    const auto scaffold_hash_before = hash_recurrent_state_streamed(ctx);

    const auto & queries = spec.at("queries");
    std::map<std::string, std::vector<boundary_result>> results;
    json records = json::array();
    json roots = json::array();
    llama_seq_id key = 4001;
    size_t common_source_tokens = 0;
    size_t maximum_simultaneous_logical_tensor_bytes = 0;
    size_t maximum_simultaneous_backend_allocation_bytes = 0;
    size_t maximum_simultaneous_gpu_allocation_bytes = 0;
    size_t cleared_attention_root_bytes = 0;
    size_t scaffold_restore_count = 0;
    size_t attention_restore_count = 0;
    size_t attention_metadata_peak_bytes = 0;

    for (const auto & variant : variants) {
        const auto source_tokens = prepare_source(ctx, vocab, sources.at(variant));
        if (attention->seq_pos_max(0) !=
                static_cast<llama_pos>(source_tokens.size() - 1) ||
            recurrent->seq_pos_max(0) !=
                static_cast<llama_pos>(source_tokens.size() - 1)) {
            throw std::runtime_error("physical attention source position mismatch");
        }
        if (common_source_tokens == 0) {
            common_source_tokens = source_tokens.size();
            if (common_source_tokens != scaffold_tokens.size()) {
                throw std::runtime_error("physical source/scaffold token count mismatch");
            }
        } else if (common_source_tokens != source_tokens.size()) {
            throw std::runtime_error("physical attention source token count changed");
        }

        auto attention_root = save_root(
            ctx, variant + ":attention-delta", key++,
            ATTENTION_DEVICE_FLAGS, source_tokens.size());
        if (attention_root.gpu_bytes >= scaffold_root.gpu_bytes) {
            throw std::runtime_error("attention root did not physically exclude recurrent tensors");
        }
        attention_metadata_peak_bytes =
            std::max(attention_metadata_peak_bytes, attention_root.metadata.size());
        maximum_simultaneous_logical_tensor_bytes = std::max(
            maximum_simultaneous_logical_tensor_bytes,
            scaffold_root.resident_bytes + attention_root.resident_bytes);
        maximum_simultaneous_backend_allocation_bytes = std::max(
            maximum_simultaneous_backend_allocation_bytes,
            scaffold_root.allocation_bytes + attention_root.allocation_bytes);
        maximum_simultaneous_gpu_allocation_bytes = std::max(
            maximum_simultaneous_gpu_allocation_bytes,
            scaffold_root.allocation_gpu_bytes + attention_root.allocation_gpu_bytes);

        for (const auto & query : queries) {
            restore_root(ctx, scaffold_root);
            ++scaffold_restore_count;
            if (recurrent->seq_pos_max(0) !=
                static_cast<llama_pos>(scaffold_tokens.size() - 1)) {
                throw std::runtime_error("restored scaffold position changed");
            }
            restore_attention_root(ctx, attention_root);
            ++attention_restore_count;
            if (attention->seq_pos_max(0) !=
                    static_cast<llama_pos>(source_tokens.size() - 1) ||
                recurrent->seq_pos_max(0) !=
                    static_cast<llama_pos>(scaffold_tokens.size() - 1) ||
                active_recurrent_backing_id(ctx) != active_recurrent_backing_initial ||
                active_attention_backing_id(ctx) != active_attention_backing_initial) {
                throw std::runtime_error("assembled physical carrier invariant failed");
            }
            auto boundary = decode_query(
                ctx, vocab, candidates, "physical-attention-root-fixed-recurrent",
                variant, query, attention_root.source_tokens,
                attention_root.backing_id, attention_root.gpu_bytes);
            records.push_back(boundary.record);
            results[variant].push_back(std::move(boundary));
        }

        roots.push_back({
            {"source_variant", variant},
            {"logical_tensor_bytes", attention_root.resident_bytes},
            {"gpu_tensor_bytes", attention_root.gpu_bytes},
            {"backend_allocation_bytes", attention_root.allocation_bytes},
            {"gpu_allocation_bytes", attention_root.allocation_gpu_bytes},
            {"metadata_bytes", attention_root.metadata.size()},
            {"root_backing_id", hex64(attention_root.backing_id)},
        });
        llama_memory_clear(llama_get_memory(ctx), true);
        cleared_attention_root_bytes +=
            llama_state_seq_clear_device_data(ctx, attention_root.key);
        if (llama_state_seq_get_device_data_size(ctx, attention_root.key) != 0 ||
            llama_state_seq_get_device_root_count(ctx) != 1) {
            throw std::runtime_error("attention root closure damaged recurrent scaffold custody");
        }
    }

    restore_root(ctx, scaffold_root);
    ++scaffold_restore_count;
    const auto scaffold_hash_after = hash_recurrent_state_streamed(ctx);
    if (scaffold_hash_after.value != scaffold_hash_before.value ||
        scaffold_hash_after.transferred_bytes != scaffold_hash_before.transferred_bytes) {
        throw std::runtime_error("recurrent scaffold content changed after reuse");
    }

    const auto & acceptance = spec.at("acceptance_law");
    const size_t joint_correct =
        semantic_correct_count(results.at("F1_G1"), queries, false);
    const size_t f_only_correct =
        semantic_correct_count(results.at("F1_G0"), queries, false);
    const size_t g_only_correct =
        semantic_correct_count(results.at("F0_G1"), queries, false);
    const size_t null_correct =
        semantic_correct_count(results.at("F0_G0"), queries, false);
    const size_t mutated_correct =
        semantic_correct_count(results.at("F1_G_MUT"), queries, true);
    const size_t presentation_correct =
        semantic_correct_count(results.at("F1_G_PRESENTATION"), queries, false);
    const size_t mutation_changes =
        boundary_changes(results.at("F1_G1"), results.at("F1_G_MUT"));
    const size_t presentation_matches =
        boundary_matches(results.at("F1_G1"), results.at("F1_G_PRESENTATION"));
    const bool accepted =
        joint_correct >= acceptance.at("joint_correct_minimum").get<size_t>() &&
        f_only_correct <= acceptance.at("f_only_correct_maximum").get<size_t>() &&
        g_only_correct <= acceptance.at("g_only_correct_maximum").get<size_t>() &&
        null_correct <= acceptance.at("null_correct_maximum").get<size_t>() &&
        mutated_correct >= acceptance.at("mutated_correct_minimum").get<size_t>() &&
        presentation_correct >= acceptance.at("presentation_correct_minimum").get<size_t>() &&
        mutation_changes >= acceptance.at("mutation_changes_minimum").get<size_t>() &&
        presentation_matches >= acceptance.at("presentation_matches_minimum").get<size_t>();

    llama_memory_clear(llama_get_memory(ctx), true);
    const size_t cleared_scaffold_bytes =
        llama_state_seq_clear_device_data(ctx, scaffold_root.key);
    llama_synchronize(ctx);
    if (llama_state_seq_get_device_root_count(ctx) != 0 ||
        active_recurrent_backing_id(ctx) != active_recurrent_backing_initial ||
        active_attention_backing_id(ctx) != active_attention_backing_initial) {
        throw std::runtime_error("physical attention-root close invariant failed");
    }

    return {
        {"schema_version", 1},
        {"mechanism", "PHYSICAL_ATTENTION_ROOTS_ON_REUSED_RECURRENT_SCAFFOLD"},
        {"spec_id", spec.at("id")},
        {"model_arch", "qwen35moe"},
        {"configuration", {
            {"source_tokens", common_source_tokens},
            {"scaffold_tokens", scaffold_tokens.size()},
            {"query_count", queries.size()},
            {"source_variant_count", variants.size()},
            {"attention_layers", attention_layers},
            {"recurrent_layers", recurrent_layers},
        }},
        {"carrier", {
            {"scaffold", {
                {"logical_tensor_bytes", scaffold_root.resident_bytes},
                {"gpu_tensor_bytes", scaffold_root.gpu_bytes},
                {"backend_allocation_bytes", scaffold_root.allocation_bytes},
                {"gpu_allocation_bytes", scaffold_root.allocation_gpu_bytes},
                {"metadata_bytes", scaffold_root.metadata.size()},
                {"root_backing_id", hex64(scaffold_root.backing_id)},
                {"restore_count", scaffold_restore_count},
                {"content_hash_before", hex64(scaffold_hash_before.value)},
                {"content_hash_after", hex64(scaffold_hash_after.value)},
                {"hash_d2h_bytes",
                    scaffold_hash_before.transferred_bytes +
                    scaffold_hash_after.transferred_bytes},
                {"hash_peak_host_work_bytes", std::max(
                    scaffold_hash_before.peak_host_work_bytes,
                    scaffold_hash_after.peak_host_work_bytes)},
                {"cleared_bytes", cleared_scaffold_bytes},
            }},
            {"attention_roots", {
                {"root_count", roots.size()},
                {"restore_count", attention_restore_count},
                {"metadata_peak_bytes", attention_metadata_peak_bytes},
                {"cleared_tensor_bytes", cleared_attention_root_bytes},
            }},
            {"maximum_simultaneous_logical_tensor_bytes",
                maximum_simultaneous_logical_tensor_bytes},
            {"maximum_simultaneous_backend_allocation_bytes",
                maximum_simultaneous_backend_allocation_bytes},
            {"maximum_simultaneous_gpu_allocation_bytes",
                maximum_simultaneous_gpu_allocation_bytes},
            {"complete_host_scaffold_copy_retained", false},
            {"all_retained_roots_closed", llama_state_seq_get_device_root_count(ctx) == 0},
            {"active_recurrent_backing_stable",
                active_recurrent_backing_id(ctx) == active_recurrent_backing_initial},
            {"active_attention_backing_stable",
                active_attention_backing_id(ctx) == active_attention_backing_initial},
            {"restoration_class", "SNAPSHOT_RELOAD"},
        }},
        {"route_summary", semantic_route_summary(results, queries)},
        {"summary", {
            {"joint_correct", joint_correct},
            {"f_only_correct", f_only_correct},
            {"g_only_correct", g_only_correct},
            {"null_correct", null_correct},
            {"mutated_correct", mutated_correct},
            {"presentation_correct", presentation_correct},
            {"mutation_changes", mutation_changes},
            {"presentation_matches", presentation_matches},
            {"semantic_validation_passed", accepted},
        }},
        {"attention_roots", roots},
        {"records", records},
        {"verdict", accepted ? "accept" : "reject"},
        {"claim_ceiling", spec.at("claim_ceiling")},
    };
}

} // namespace

int main(int argc, char ** argv) {
    common_params params;
    params.escape = false;
    params.warmup = false;

    common_init();
    if (!common_params_parse(argc, argv, params, LLAMA_EXAMPLE_RESULTS, print_usage)) {
        return 1;
    }
    if (params.prompt_file.empty() || params.out_file.empty()) {
        print_usage(argc, argv);
        return 1;
    }

    std::ifstream spec_stream(params.prompt_file);
    if (!spec_stream) {
        LOG_ERR("failed to open spec: %s\n", params.prompt_file.c_str());
        return 1;
    }
    json spec;
    spec_stream >> spec;

    llama_backend_init();
    llama_numa_init(params.numa);

    try {
        auto llama_init = common_init_from_params(params);
        llama_model * model = llama_init->model();
        llama_context * ctx = llama_init->context();
        if (!model || !ctx) {
            throw std::runtime_error("failed to load model or context");
        }
        if (model->arch != LLM_ARCH_QWEN35MOE) {
            throw std::runtime_error("probe requires qwen35moe");
        }
        auto * hybrid = require_hybrid_memory(ctx);
        if (hybrid->get_mem_recr()->n_rs_seq != 0) {
            throw std::runtime_error("probe requires n_rs_seq=0");
        }

        const llama_vocab * vocab = llama_model_get_vocab(model);
        const auto candidates = candidate_tokens(vocab);
        const uint64_t active_backing_initial = active_recurrent_backing_id(ctx);
        const uint64_t active_attention_backing_initial = active_attention_backing_id(ctx);
        if (active_backing_initial == 0) {
            throw std::runtime_error("active recurrent backing identity is zero");
        }
        if (active_attention_backing_initial == 0) {
            throw std::runtime_error("active attention backing identity is zero");
        }

        if (spec.value("physical_attention_roots", false)) {
            const json result = run_physical_attention_roots(
                ctx,
                vocab,
                candidates,
                spec,
                active_backing_initial,
                active_attention_backing_initial);
            std::ofstream result_stream(params.out_file);
            result_stream << result.dump(2) << '\n';
            result_stream.close();
            LOG_INF("wrote %s\n", params.out_file.c_str());
            llama_backend_free();
            return 0;
        }

        if (spec.value("matched_semantic_validation", false)) {
            const json result = run_matched_semantic_validation(
                ctx,
                vocab,
                candidates,
                spec,
                active_backing_initial,
                active_attention_backing_initial);
            std::ofstream result_stream(params.out_file);
            result_stream << result.dump(2) << '\n';
            result_stream.close();
            LOG_INF("wrote %s\n", params.out_file.c_str());
            llama_backend_free();
            return 0;
        }

        if (spec.contains("localization_arms")) {
            const json result = run_layer_localization(
                ctx,
                vocab,
                candidates,
                spec,
                active_backing_initial,
                active_attention_backing_initial);
            std::ofstream result_stream(params.out_file);
            result_stream << result.dump(2) << '\n';
            result_stream.close();
            LOG_INF("wrote %s\n", params.out_file.c_str());
            llama_backend_free();
            return 0;
        }

        const auto & sources = spec.at("sources");
        const auto & queries = spec.at("queries");
        const std::vector<std::string> required_variants = {
            "F0_G0", "F1_G0", "F0_G1", "F1_G1", "F1_G_MUT", "F1_G_PRESENTATION"
        };
        for (const auto & variant : required_variants) {
            if (!sources.contains(variant)) {
                throw std::runtime_error("missing source variant " + variant);
            }
        }

        json records = json::array();
        json roots = json::array();
        std::map<std::string, std::vector<boundary_result>> recurrent_results;
        std::map<std::string, std::vector<boundary_result>> attention_results;
        std::map<std::string, std::vector<boundary_result>> full_root_results;
        std::vector<boundary_result> direct_results;
        std::vector<boundary_result> null_results;
        size_t common_source_tokens = 0;
        llama_seq_id key = 1000;
        size_t maximum_simultaneous_root_gpu_bytes = 0;
        size_t cleared_root_bytes = 0;

        for (const auto & variant : required_variants) {
            auto source_tokens = prepare_source(ctx, vocab, sources.at(variant));
            if (common_source_tokens == 0) {
                common_source_tokens = source_tokens.size();
            } else if (source_tokens.size() != common_source_tokens) {
                throw std::runtime_error(
                    "source token count mismatch for " + variant + ": " +
                    std::to_string(source_tokens.size()) + " != " +
                    std::to_string(common_source_tokens));
            }

            auto recurrent_root = save_root(
                ctx, variant + ":recurrent", key++, RECURRENT_DEVICE_FLAGS, source_tokens.size());
            device_root full_root;
            const bool save_full =
                spec.value("full_hybrid_all_variants", false) ||
                variant == "F1_G1";
            if (save_full) {
                full_root = save_root(
                    ctx, variant + ":full", key++, FULL_DEVICE_FLAGS, source_tokens.size());
            }

            hybrid->get_mem_recr()->clear(true);
            llama_synchronize(ctx);
            if (hybrid->get_mem_recr()->used != 0 ||
                hybrid->get_mem_recr()->seq_pos_max(0) != -1 ||
                hybrid->get_mem_attn()->seq_pos_max(0) !=
                    static_cast<llama_pos>(source_tokens.size() - 1)) {
                throw std::runtime_error(
                    "failed to isolate attention KV for " + variant);
            }
            auto attention_root = save_root(
                ctx, variant + ":attention", key++, FULL_DEVICE_FLAGS, source_tokens.size());

            size_t simultaneous_gpu_bytes =
                recurrent_root.gpu_bytes + attention_root.gpu_bytes;
            if (save_full) {
                simultaneous_gpu_bytes += full_root.gpu_bytes;
            }
            maximum_simultaneous_root_gpu_bytes = std::max(
                maximum_simultaneous_root_gpu_bytes, simultaneous_gpu_bytes);

            roots.push_back({
                {"variant", variant},
                {"kind", "recurrent-only"},
                {"storage_key", recurrent_root.key},
                {"metadata_bytes", recurrent_root.metadata.size()},
                {"resident_bytes", recurrent_root.resident_bytes},
                {"gpu_bytes", recurrent_root.gpu_bytes},
                {"backing_id", hex64(recurrent_root.backing_id)},
                {"source_tokens", recurrent_root.source_tokens},
            });
            roots.push_back({
                {"variant", variant},
                {"kind", "attention-only"},
                {"storage_key", attention_root.key},
                {"metadata_bytes", attention_root.metadata.size()},
                {"resident_bytes", attention_root.resident_bytes},
                {"gpu_bytes", attention_root.gpu_bytes},
                {"backing_id", hex64(attention_root.backing_id)},
                {"source_tokens", attention_root.source_tokens},
            });
            if (save_full) {
                roots.push_back({
                    {"variant", variant},
                    {"kind", "full-hybrid"},
                    {"storage_key", full_root.key},
                    {"metadata_bytes", full_root.metadata.size()},
                    {"resident_bytes", full_root.resident_bytes},
                    {"gpu_bytes", full_root.gpu_bytes},
                    {"backing_id", hex64(full_root.backing_id)},
                    {"source_tokens", full_root.source_tokens},
                });
            }

            for (const auto & query : queries) {
                restore_root(ctx, recurrent_root);
                auto recurrent = decode_query(
                    ctx, vocab, candidates, "recurrent-only-root", variant, query,
                    recurrent_root.source_tokens, recurrent_root.backing_id, recurrent_root.gpu_bytes);
                if (active_recurrent_backing_id(ctx) != active_backing_initial) {
                    throw std::runtime_error("active recurrent cache backing changed");
                }
                records.push_back(recurrent.record);
                recurrent_results[variant].push_back(std::move(recurrent));

                restore_root(ctx, attention_root);
                auto attention = decode_query(
                    ctx, vocab, candidates, "attention-only-root", variant, query,
                    attention_root.source_tokens, attention_root.backing_id, attention_root.gpu_bytes);
                if (active_attention_backing_id(ctx) != active_attention_backing_initial) {
                    throw std::runtime_error("active attention cache backing changed");
                }
                records.push_back(attention.record);
                attention_results[variant].push_back(std::move(attention));

                if (save_full) {
                    restore_root(ctx, full_root);
                    auto full = decode_query(
                        ctx, vocab, candidates, "full-hybrid-root", variant, query,
                        full_root.source_tokens, full_root.backing_id, full_root.gpu_bytes);
                    records.push_back(full.record);
                    full_root_results[variant].push_back(std::move(full));
                }
            }

            llama_memory_clear(llama_get_memory(ctx), true);
            cleared_root_bytes += llama_state_seq_clear_device_data(ctx, recurrent_root.key);
            if (llama_state_seq_get_device_data_size(ctx, recurrent_root.key) != 0) {
                throw std::runtime_error("recurrent root did not close");
            }
            cleared_root_bytes += llama_state_seq_clear_device_data(ctx, attention_root.key);
            if (llama_state_seq_get_device_data_size(ctx, attention_root.key) != 0) {
                throw std::runtime_error("attention root did not close");
            }
            if (save_full) {
                cleared_root_bytes += llama_state_seq_clear_device_data(ctx, full_root.key);
                if (llama_state_seq_get_device_data_size(ctx, full_root.key) != 0) {
                    throw std::runtime_error("full root did not close");
                }
            }
        }

        // Strong conventional control: re-evaluate the complete joint source,
        // leave ordinary hybrid memory live, then decode the same delayed query.
        for (const auto & query : queries) {
            auto source_tokens = prepare_source(ctx, vocab, sources.at("F1_G1"));
            auto direct = decode_query(
                ctx, vocab, candidates, "direct-live-hybrid", "F1_G1", query,
                source_tokens.size(), 0, 0);
            records.push_back(direct.record);
            direct_results.push_back(std::move(direct));
        }

        // Null carrier control: preserve absolute query position but provide no
        // source attention or recurrent state.
        for (const auto & query : queries) {
            llama_memory_clear(llama_get_memory(ctx), true);
            auto null = decode_query(
                ctx, vocab, candidates, "null-carrier", "F0_G0", query,
                common_source_tokens, 0, 0);
            records.push_back(null.record);
            null_results.push_back(std::move(null));
        }

        auto accuracy = [&](const std::vector<boundary_result> & values, const char * expected_field) {
            size_t correct = 0;
            for (size_t i = 0; i < values.size(); ++i) {
                correct += values[i].argmax == queries.at(i).at(expected_field).get<std::string>();
            }
            return correct;
        };
        auto differences = [](const std::vector<boundary_result> & a, const std::vector<boundary_result> & b) {
            size_t count = 0;
            for (size_t i = 0; i < a.size(); ++i) {
                count += a[i].argmax != b[i].argmax;
            }
            return count;
        };

        const size_t recurrent_joint = accuracy(recurrent_results.at("F1_G1"), "expected");
        const size_t recurrent_f_only = accuracy(recurrent_results.at("F1_G0"), "expected");
        const size_t recurrent_g_only = accuracy(recurrent_results.at("F0_G1"), "expected");
        const size_t recurrent_null = accuracy(recurrent_results.at("F0_G0"), "expected");
        const size_t explicit_null = accuracy(null_results, "expected");
        const size_t recurrent_mutated = accuracy(recurrent_results.at("F1_G_MUT"), "expected_mutated");
        const size_t recurrent_presentation = accuracy(recurrent_results.at("F1_G_PRESENTATION"), "expected");
        const size_t attention_joint = accuracy(attention_results.at("F1_G1"), "expected");
        const size_t attention_f_only = accuracy(attention_results.at("F1_G0"), "expected");
        const size_t attention_g_only = accuracy(attention_results.at("F0_G1"), "expected");
        const size_t attention_null = accuracy(attention_results.at("F0_G0"), "expected");
        const size_t attention_mutated = accuracy(attention_results.at("F1_G_MUT"), "expected_mutated");
        const size_t attention_presentation = accuracy(attention_results.at("F1_G_PRESENTATION"), "expected");
        const size_t full_joint = accuracy(full_root_results.at("F1_G1"), "expected");
        const size_t full_f_only =
            full_root_results.find("F1_G0") != full_root_results.end() ?
                accuracy(full_root_results.at("F1_G0"), "expected") : 0;
        const size_t full_g_only =
            full_root_results.find("F0_G1") != full_root_results.end() ?
                accuracy(full_root_results.at("F0_G1"), "expected") : 0;
        const size_t full_null =
            full_root_results.find("F0_G0") != full_root_results.end() ?
                accuracy(full_root_results.at("F0_G0"), "expected") : 0;
        const size_t full_mutated =
            full_root_results.find("F1_G_MUT") != full_root_results.end() ?
                accuracy(full_root_results.at("F1_G_MUT"), "expected_mutated") : 0;
        const size_t full_presentation =
            full_root_results.find("F1_G_PRESENTATION") != full_root_results.end() ?
                accuracy(full_root_results.at("F1_G_PRESENTATION"), "expected") : 0;
        const size_t direct_joint = accuracy(direct_results, "expected");
        const size_t mutation_changes = differences(
            recurrent_results.at("F1_G1"), recurrent_results.at("F1_G_MUT"));
        const size_t joint_changes_from_null = differences(
            recurrent_results.at("F1_G1"), null_results);
        const size_t recurrent_matches_full =
            queries.size() - differences(
                recurrent_results.at("F1_G1"), full_root_results.at("F1_G1"));
        const size_t attention_mutation_changes = differences(
            attention_results.at("F1_G1"), attention_results.at("F1_G_MUT"));
        const size_t attention_joint_changes_from_null = differences(
            attention_results.at("F1_G1"), null_results);
        const size_t attention_matches_full =
            queries.size() - differences(
                attention_results.at("F1_G1"), full_root_results.at("F1_G1"));
        const size_t full_mutation_changes =
            full_root_results.find("F1_G_MUT") != full_root_results.end() ?
                differences(
                    full_root_results.at("F1_G1"),
                    full_root_results.at("F1_G_MUT")) : 0;
        const size_t full_joint_changes_from_null =
            full_root_results.find("F0_G0") != full_root_results.end() ?
                differences(
                    full_root_results.at("F1_G1"),
                    full_root_results.at("F0_G0")) : 0;
        const size_t full_matches_direct =
            queries.size() - differences(full_root_results.at("F1_G1"), direct_results);

        json recurrent_interactions = json::array();
        json attention_interactions = json::array();
        for (size_t i = 0; i < queries.size(); ++i) {
            auto recurrent_interaction = interaction_record(
                recurrent_results.at("F0_G0")[i],
                recurrent_results.at("F1_G0")[i],
                recurrent_results.at("F0_G1")[i],
                recurrent_results.at("F1_G1")[i]);
            recurrent_interaction["query_id"] = queries.at(i).at("id");
            recurrent_interactions.push_back(std::move(recurrent_interaction));

            auto attention_interaction = interaction_record(
                attention_results.at("F0_G0")[i],
                attention_results.at("F1_G0")[i],
                attention_results.at("F0_G1")[i],
                attention_results.at("F1_G1")[i]);
            attention_interaction["query_id"] = queries.at(i).at("id");
            attention_interactions.push_back(std::move(attention_interaction));
        }

        const auto & acceptance = spec.at("acceptance_law");
        const bool full_hybrid_gate = spec.value("full_hybrid_all_variants", false);
        const bool accepted =
            (full_hybrid_gate ?
                (full_joint >= acceptance.at("full_joint_correct_minimum").get<size_t>() &&
                 full_joint > full_f_only &&
                 full_joint > full_g_only &&
                 full_joint > explicit_null &&
                 full_mutated >= acceptance.at("mutated_correct_minimum").get<size_t>() &&
                 full_presentation >= acceptance.at("presentation_correct_minimum").get<size_t>() &&
                 full_mutation_changes >= acceptance.at("mutation_changes_minimum").get<size_t>() &&
                 full_joint_changes_from_null >= acceptance.at("joint_changes_from_null_minimum").get<size_t>()) :
                (attention_joint >= acceptance.at("attention_joint_correct_minimum").get<size_t>() &&
                 attention_joint > attention_f_only &&
                 attention_joint > attention_g_only &&
                 attention_joint > explicit_null &&
                 attention_mutated >= acceptance.at("mutated_correct_minimum").get<size_t>() &&
                 attention_presentation >= acceptance.at("presentation_correct_minimum").get<size_t>() &&
                 attention_mutation_changes >= acceptance.at("mutation_changes_minimum").get<size_t>() &&
                 attention_joint_changes_from_null >= acceptance.at("joint_changes_from_null_minimum").get<size_t>())) &&
            full_joint >= acceptance.at("full_joint_correct_minimum").get<size_t>() &&
            direct_joint >= acceptance.at("direct_joint_correct_minimum").get<size_t>() &&
            full_matches_direct >= acceptance.at("full_matches_direct_minimum").get<size_t>();

        llama_memory_clear(llama_get_memory(ctx), true);
        llama_synchronize(ctx);
        if (llama_state_seq_get_device_root_count(ctx) != 0) {
            throw std::runtime_error("retained device-root registry is not empty at close");
        }
        if (active_recurrent_backing_id(ctx) != active_backing_initial) {
            throw std::runtime_error("active recurrent backing changed at close");
        }
        if (active_attention_backing_id(ctx) != active_attention_backing_initial) {
            throw std::runtime_error("active attention backing changed at close");
        }

        json result = {
            {"schema_version", 1},
            {"mechanism", spec.value(
                "mechanism",
                std::string("QUERY_SEPARATED_ATTENTION_ONLY_DEVICE_ROOT"))},
            {"spec_id", spec.at("id")},
            {"model_arch", "qwen35moe"},
            {"configuration", {
                {"ctx_size", llama_n_ctx(ctx)},
                {"n_seq_max", params.n_parallel},
                {"recurrent_state_flags", RECURRENT_DEVICE_FLAGS},
                {"full_state_flags", FULL_DEVICE_FLAGS},
                {"source_tokens", common_source_tokens},
                {"query_count", queries.size()},
            }},
            {"carrier", {
                {"recurrent_layers", 30},
                {"active_recurrent_backing_id", hex64(active_backing_initial)},
                {"active_attention_backing_id", hex64(active_attention_backing_initial)},
                {"active_recurrent_logical_bytes", 65863680},
                {"maximum_simultaneous_root_gpu_bytes", maximum_simultaneous_root_gpu_bytes},
                {"cleared_root_bytes", cleared_root_bytes},
                {"all_retained_roots_closed", llama_state_seq_get_device_root_count(ctx) == 0},
                {"active_backing_stable", active_recurrent_backing_id(ctx) == active_backing_initial},
                {"active_attention_backing_stable",
                    active_attention_backing_id(ctx) == active_attention_backing_initial},
                {"restoration_class", "SNAPSHOT_RELOAD"},
            }},
            {"roots", roots},
            {"records", records},
            {"recurrent_interactions", recurrent_interactions},
            {"attention_interactions", attention_interactions},
            {"summary", {
                {"query_count", queries.size()},
                {"recurrent_joint_correct", recurrent_joint},
                {"recurrent_f_only_correct", recurrent_f_only},
                {"recurrent_g_only_correct", recurrent_g_only},
                {"recurrent_null_source_correct", recurrent_null},
                {"explicit_null_correct", explicit_null},
                {"recurrent_mutated_correct", recurrent_mutated},
                {"recurrent_presentation_correct", recurrent_presentation},
                {"attention_joint_correct", attention_joint},
                {"attention_f_only_correct", attention_f_only},
                {"attention_g_only_correct", attention_g_only},
                {"attention_null_source_correct", attention_null},
                {"attention_mutated_correct", attention_mutated},
                {"attention_presentation_correct", attention_presentation},
                {"full_joint_correct", full_joint},
                {"full_f_only_correct", full_f_only},
                {"full_g_only_correct", full_g_only},
                {"full_null_source_correct", full_null},
                {"full_mutated_correct", full_mutated},
                {"full_presentation_correct", full_presentation},
                {"direct_joint_correct", direct_joint},
                {"mutation_changes", mutation_changes},
                {"joint_changes_from_null", joint_changes_from_null},
                {"attention_mutation_changes", attention_mutation_changes},
                {"attention_joint_changes_from_null", attention_joint_changes_from_null},
                {"full_mutation_changes", full_mutation_changes},
                {"full_joint_changes_from_null", full_joint_changes_from_null},
                {"recurrent_matches_full", recurrent_matches_full},
                {"attention_matches_full", attention_matches_full},
                {"full_matches_direct", full_matches_direct},
            }},
            {"verdict", accepted ? "accept" : "reject"},
            {"claim_ceiling",
             spec.at("claim_ceiling")},
        };

        std::ofstream result_stream(params.out_file);
        result_stream << result.dump(2) << '\n';
        result_stream.close();
        LOG_INF("wrote %s\n", params.out_file.c_str());
    } catch (const std::exception & error) {
        LOG_ERR("recurrent carrier probe failed: %s\n", error.what());
        llama_backend_free();
        return 1;
    }

    llama_backend_free();
    return 0;
}
