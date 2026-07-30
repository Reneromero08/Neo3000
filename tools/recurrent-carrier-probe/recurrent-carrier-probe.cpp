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
#include <array>
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

static uint64_t hash_value_subspace_operator(
        const llama_kv_cache::value_subspace_operator & value_operator) {
    uint64_t hash = UINT64_C(1469598103934665603);
    fnv1a64_update(
        hash,
        &value_operator.calibration_samples,
        sizeof(value_operator.calibration_samples));
    fnv1a64_update(
        hash,
        &value_operator.training_contexts,
        sizeof(value_operator.training_contexts));
    fnv1a64_update(
        hash,
        &value_operator.explicit_affine,
        sizeof(value_operator.explicit_affine));
    for (const auto & layer : value_operator.layers) {
        fnv1a64_update(
            hash, &layer.layer_id, sizeof(layer.layer_id));
        fnv1a64_update(
            hash, &layer.key, sizeof(layer.key));
        const auto update_vector =
                [&](const std::vector<float> & values) {
            const uint64_t size = values.size();
            fnv1a64_update(hash, &size, sizeof(size));
            if (!values.empty()) {
                fnv1a64_update(
                    hash,
                    values.data(),
                    values.size() * sizeof(float));
            }
        };
        update_vector(layer.center);
        update_vector(layer.bias);
        for (const auto & basis : layer.basis) {
            update_vector(basis);
        }
        for (const auto & delta : layer.delta) {
            update_vector(delta);
        }
    }
    return hash;
}

static uint64_t refresh_value_subspace_operator_backing(
        llama_kv_cache::value_subspace_operator & value_operator) {
    value_operator.logical_bytes = 0;
    value_operator.vector_backing_bytes =
        sizeof(value_operator) +
        value_operator.layers.capacity() *
            sizeof(llama_kv_cache::value_subspace_layer);
    value_operator.total_rank = 0;
    value_operator.maximum_layer_rank = 0;
    for (const auto & layer : value_operator.layers) {
        const size_t elements = layer.center.size();
        value_operator.logical_bytes +=
            (layer.center.size() +
             layer.bias.size() +
             2 * layer.basis.size() * elements) *
            sizeof(float);
        value_operator.vector_backing_bytes +=
            (layer.center.capacity() +
             layer.bias.capacity()) * sizeof(float) +
            (layer.basis.capacity() +
             layer.delta.capacity()) *
                sizeof(std::vector<float>);
        for (const auto & vector : layer.basis) {
            value_operator.vector_backing_bytes +=
                vector.capacity() * sizeof(float);
        }
        for (const auto & vector : layer.delta) {
            value_operator.vector_backing_bytes +=
                vector.capacity() * sizeof(float);
        }
        value_operator.total_rank += layer.basis.size();
        value_operator.maximum_layer_rank = std::max<uint64_t>(
            value_operator.maximum_layer_rank,
            layer.basis.size());
    }
    return value_operator.vector_backing_bytes;
}

static uint64_t make_value_subspace_operator_explicit_affine(
        llama_kv_cache::value_subspace_operator & value_operator) {
    if (value_operator.explicit_affine) {
        return 0;
    }
    uint64_t peak_scratch_bytes = 0;
    for (auto & layer : value_operator.layers) {
        const size_t elements = layer.center.size();
        if (elements == 0 ||
            layer.basis.size() != layer.delta.size()) {
            throw std::runtime_error(
                "invalid centered operator during affine conversion");
        }
        layer.bias.assign(elements, 0.0f);
        for (size_t basis_index = 0;
             basis_index < layer.basis.size();
             ++basis_index) {
            if (layer.basis[basis_index].size() != elements ||
                layer.delta[basis_index].size() != elements) {
                throw std::runtime_error(
                    "invalid centered operator vector geometry");
            }
            double coefficient = 0.0;
            for (size_t j = 0; j < elements; ++j) {
                coefficient -=
                    static_cast<double>(
                        layer.basis[basis_index][j]) *
                    static_cast<double>(layer.center[j]);
            }
            for (size_t j = 0; j < elements; ++j) {
                layer.bias[j] += static_cast<float>(
                    coefficient *
                    layer.delta[basis_index][j]);
            }
        }
        peak_scratch_bytes = std::max<uint64_t>(
            peak_scratch_bytes,
            layer.bias.size() * sizeof(float));
    }
    value_operator.explicit_affine = true;
    refresh_value_subspace_operator_backing(value_operator);
    return peak_scratch_bytes;
}

static uint64_t merge_value_subspace_context_action(
        llama_kv_cache::value_subspace_operator & aggregate,
        const llama_kv_cache::value_subspace_operator & context_operator) {
    if (!aggregate.explicit_affine ||
        context_operator.explicit_affine ||
        aggregate.layers.size() != context_operator.layers.size() ||
        aggregate.training_contexts == 0 ||
        context_operator.training_contexts != 1) {
        throw std::runtime_error(
            "invalid multi-context operator merge state");
    }
    const double old_weight =
        static_cast<double>(aggregate.training_contexts);
    const double new_weight = old_weight + 1.0;
    uint64_t peak_scratch_bytes = 0;
    for (size_t layer_index = 0;
         layer_index < aggregate.layers.size();
         ++layer_index) {
        auto & target = aggregate.layers[layer_index];
        const auto & source = context_operator.layers[layer_index];
        const size_t elements = target.center.size();
        if (target.layer_id != source.layer_id ||
            target.key != source.key ||
            elements == 0 ||
            source.center.size() != elements ||
            target.bias.size() != elements ||
            target.basis.size() != target.delta.size() ||
            source.basis.size() != source.delta.size()) {
            throw std::runtime_error(
                "multi-context operator layer mismatch");
        }
        std::vector<float> source_bias(elements, 0.0f);
        for (size_t source_index = 0;
             source_index < source.basis.size();
             ++source_index) {
            if (source.basis[source_index].size() != elements ||
                source.delta[source_index].size() != elements) {
                throw std::runtime_error(
                    "multi-context source vector mismatch");
            }
            double coefficient = 0.0;
            for (size_t j = 0; j < elements; ++j) {
                coefficient -=
                    static_cast<double>(
                        source.basis[source_index][j]) *
                    static_cast<double>(source.center[j]);
            }
            for (size_t j = 0; j < elements; ++j) {
                source_bias[j] += static_cast<float>(
                    coefficient *
                    source.delta[source_index][j]);
            }
        }
        for (size_t j = 0; j < elements; ++j) {
            target.bias[j] = static_cast<float>(
                (old_weight * target.bias[j] +
                 source_bias[j]) /
                new_weight);
        }

        std::vector<float> projected_delta(elements);
        for (size_t target_index = 0;
             target_index < target.basis.size();
             ++target_index) {
            if (target.basis[target_index].size() != elements ||
                target.delta[target_index].size() != elements) {
                throw std::runtime_error(
                    "multi-context target vector mismatch");
            }
            std::fill(
                projected_delta.begin(),
                projected_delta.end(),
                0.0f);
            for (size_t source_index = 0;
                 source_index < source.basis.size();
                 ++source_index) {
                double coefficient = 0.0;
                for (size_t j = 0; j < elements; ++j) {
                    coefficient +=
                        static_cast<double>(
                            source.basis[source_index][j]) *
                        static_cast<double>(
                            target.basis[target_index][j]);
                }
                for (size_t j = 0; j < elements; ++j) {
                    projected_delta[j] += static_cast<float>(
                        coefficient *
                        source.delta[source_index][j]);
                }
            }
            for (size_t j = 0; j < elements; ++j) {
                target.delta[target_index][j] = static_cast<float>(
                    (old_weight *
                        target.delta[target_index][j] +
                     projected_delta[j]) /
                    new_weight);
            }
        }
        peak_scratch_bytes = std::max<uint64_t>(
            peak_scratch_bytes,
            (source_bias.size() +
             projected_delta.size()) *
                sizeof(float));
    }
    aggregate.training_contexts += 1;
    aggregate.calibration_samples +=
        context_operator.calibration_samples;
    aggregate.calibration_max_abs_error = std::max(
        aggregate.calibration_max_abs_error,
        context_operator.calibration_max_abs_error);
    aggregate.subspace_closure_max_abs_error = std::max(
        aggregate.subspace_closure_max_abs_error,
        context_operator.subspace_closure_max_abs_error);
    refresh_value_subspace_operator_backing(aggregate);
    return peak_scratch_bytes;
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

static size_t active_hybrid_backend_allocation_bytes(llama_context * ctx) {
    auto * hybrid = require_hybrid_memory(ctx);
    auto * attention = hybrid->get_mem_attn();
    auto * recurrent = hybrid->get_mem_recr();
    std::set<ggml_backend_buffer_t> unique;
    for (const uint32_t il : attention->get_layer_ids()) {
        for (ggml_tensor * tensor : {
                attention->get_k_storage(static_cast<int32_t>(il)),
                attention->get_v_storage(static_cast<int32_t>(il))}) {
            if (tensor && tensor->buffer) {
                unique.insert(tensor->buffer);
            }
        }
    }
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

    size_t bytes = 0;
    for (ggml_backend_buffer_t buffer : unique) {
        bytes += ggml_backend_buffer_get_size(buffer);
    }
    return bytes;
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
        bool terminal_logits,
        llama_seq_id seq_id = 0) {
    if (tokens.empty()) {
        return;
    }
    auto batch = llama_batch_init(static_cast<int32_t>(tokens.size()), 0, 1);
    for (size_t i = 0; i < tokens.size(); ++i) {
        common_batch_add(
            batch,
            tokens[i],
            start_pos + static_cast<llama_pos>(i),
            {seq_id},
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

static std::vector<llama_token> tokenize_source(
        const llama_vocab * vocab,
        const json & source) {
    std::vector<llama_token> all;
    bool first = true;
    for (const char * field : {"prefix", "module_f", "module_g", "closure"}) {
        const std::string text = source.at(field).get<std::string>();
        auto tokens = tokenize_piece(vocab, text, first, true);
        all.insert(all.end(), tokens.begin(), tokens.end());
        first = false;
    }
    return all;
}

static std::vector<llama_token> prepare_source_prefix(
        llama_context * ctx,
        const llama_vocab * vocab,
        const json & source) {
    llama_memory_clear(llama_get_memory(ctx), true);
    auto tokens = tokenize_piece(
        vocab, source.at("prefix").get<std::string>(), true, true);
    decode_tokens(ctx, tokens, 0, false);
    llama_synchronize(ctx);
    return tokens;
}

static size_t decode_source_suffix(
        llama_context * ctx,
        const llama_vocab * vocab,
        const json & source,
        size_t prefix_tokens) {
    llama_pos pos = static_cast<llama_pos>(prefix_tokens);
    size_t suffix_tokens = 0;
    for (const char * field : {"module_f", "module_g", "closure"}) {
        auto tokens = tokenize_piece(
            vocab, source.at(field).get<std::string>(), false, true);
        decode_tokens(ctx, tokens, pos, false);
        pos += static_cast<llama_pos>(tokens.size());
        suffix_tokens += tokens.size();
    }
    llama_synchronize(ctx);
    return suffix_tokens;
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
        size_t root_gpu_bytes,
        llama_seq_id seq_id = 0) {
    const std::string text = query.at("suffix").get<std::string>();
    auto tokens = tokenize_piece(vocab, text, false, true);

    const auto started = std::chrono::steady_clock::now();
    decode_tokens(
        ctx, tokens, static_cast<llama_pos>(source_tokens), true, seq_id);
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
        {"sequence_id", seq_id},
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

struct streamed_sequence_hash {
    streamed_tensor_hash tensor;
    int32_t physical_row = -1;
    llama_pos position = -1;
};

static void hash_tensor_row_streamed(
        streamed_tensor_hash & hash,
        ggml_tensor * tensor,
        uint64_t layer,
        uint64_t kind,
        uint32_t row,
        uint32_t row_count) {
    if (!tensor) {
        return;
    }
    if (row_count == 0 || row >= row_count ||
        ggml_nbytes(tensor) % row_count != 0) {
        throw std::runtime_error(
            "recurrent sequence tensor is not row-divisible");
    }
    const size_t row_bytes = ggml_nbytes(tensor) / row_count;
    const size_t chunk_capacity = 1024 * 1024;
    std::vector<uint8_t> work(std::min(chunk_capacity, row_bytes));
    fnv_mix_u64(hash.value, layer);
    fnv_mix_u64(hash.value, kind);
    fnv_mix_u64(hash.value, row_bytes);
    for (size_t offset = 0; offset < row_bytes; offset += work.size()) {
        const size_t size = std::min(work.size(), row_bytes - offset);
        ggml_backend_tensor_get(
            tensor,
            work.data(),
            static_cast<size_t>(row) * row_bytes + offset,
            size);
        fnv1a64_update(hash.value, work.data(), size);
        hash.transferred_bytes += size;
    }
    hash.peak_host_work_bytes =
        std::max(hash.peak_host_work_bytes, work.size());
}

static streamed_sequence_hash hash_recurrent_sequence_streamed(
        llama_context * ctx,
        llama_seq_id seq_id) {
    llama_synchronize(ctx);
    auto * recurrent = require_hybrid_memory(ctx)->get_mem_recr();
    if (seq_id < 0 ||
        static_cast<size_t>(seq_id) >= recurrent->cells.size()) {
        throw std::runtime_error("recurrent sequence hash id is invalid");
    }
    const int32_t tail = recurrent->cells.at(seq_id).tail;
    if (tail < 0 ||
        static_cast<size_t>(tail) >= recurrent->cells.size() ||
        !recurrent->cells.at(tail).has_seq_id(seq_id)) {
        throw std::runtime_error("recurrent sequence has no live tail");
    }
    const auto & cell = recurrent->cells.at(tail);
    const int32_t physical_row = cell.src >= 0 ? cell.src : tail;
    const uint32_t row_count =
        recurrent->size * (1 + recurrent->n_rs_seq);
    if (physical_row < 0 ||
        static_cast<uint32_t>(physical_row) >= row_count) {
        throw std::runtime_error("recurrent sequence physical row is invalid");
    }

    streamed_sequence_hash result;
    result.physical_row = physical_row;
    result.position = cell.pos;
    fnv_mix_u64(result.tensor.value, static_cast<uint64_t>(cell.pos));
    for (uint32_t il = 0; il < recurrent->r_l.size(); ++il) {
        hash_tensor_row_streamed(
            result.tensor, recurrent->r_l[il], il, 0,
            static_cast<uint32_t>(physical_row), row_count);
        hash_tensor_row_streamed(
            result.tensor, recurrent->s_l[il], il, 1,
            static_cast<uint32_t>(physical_row), row_count);
    }
    return result;
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
    const size_t active_cache_backend_allocation_bytes =
        active_hybrid_backend_allocation_bytes(ctx);

    const auto & queries = spec.at("queries");
    std::map<std::string, std::vector<boundary_result>> results;
    std::map<std::string, std::vector<boundary_result>> reuse_results;
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
    size_t source_transaction_count = 0;

    const auto execute_attention_transaction = [&](
            const std::string & family,
            const std::string & variant,
            const json & source,
            const json & transaction_queries,
            std::map<std::string, std::vector<boundary_result>> & destination) {
        const auto source_tokens = prepare_source(ctx, vocab, source);
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
            ctx, family + ":" + variant + ":attention-delta", key++,
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

        for (const auto & query : transaction_queries) {
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
                ctx, vocab, candidates,
                "physical-attention-root-fixed-recurrent:" + family,
                variant, query, attention_root.source_tokens,
                attention_root.backing_id, attention_root.gpu_bytes);
            records.push_back(boundary.record);
            destination[variant].push_back(std::move(boundary));
        }

        roots.push_back({
            {"transaction_family", family},
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
        ++source_transaction_count;
    };

    for (const auto & variant : variants) {
        execute_attention_transaction(
            "primary", variant, sources.at(variant), queries, results);
    }

    const bool has_reuse_task = spec.contains("reuse_sources");
    if (has_reuse_task) {
        const auto & reuse_sources = spec.at("reuse_sources");
        const auto & reuse_queries = spec.at("reuse_queries");
        for (const std::string variant : {"R_F1_G0", "R_F0_G1", "R_F1_G1"}) {
            if (!reuse_sources.contains(variant)) {
                throw std::runtime_error("reuse task missing source variant " + variant);
            }
            execute_attention_transaction(
                "unrelated-reuse", variant, reuse_sources.at(variant),
                reuse_queries, reuse_results);
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

    size_t reuse_joint_correct = 0;
    size_t reuse_f_only_correct = 0;
    size_t reuse_g_only_correct = 0;
    bool reuse_accepted = !has_reuse_task;
    if (has_reuse_task) {
        const auto & reuse_queries = spec.at("reuse_queries");
        const auto & reuse_acceptance = spec.at("reuse_acceptance_law");
        reuse_joint_correct = semantic_correct_count(
            reuse_results.at("R_F1_G1"), reuse_queries, false);
        reuse_f_only_correct = semantic_correct_count(
            reuse_results.at("R_F1_G0"), reuse_queries, false);
        reuse_g_only_correct = semantic_correct_count(
            reuse_results.at("R_F0_G1"), reuse_queries, false);
        reuse_accepted =
            reuse_joint_correct >=
                reuse_acceptance.at("joint_correct_minimum").get<size_t>() &&
            reuse_f_only_correct <=
                reuse_acceptance.at("f_only_correct_maximum").get<size_t>() &&
            reuse_g_only_correct <=
                reuse_acceptance.at("g_only_correct_maximum").get<size_t>();
    }
    const bool complete_acceptance = accepted && reuse_accepted;

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
            {"source_transaction_count", source_transaction_count},
            {"unrelated_reuse_task_present", has_reuse_task},
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
            {"active_cache_backend_allocation_bytes",
                active_cache_backend_allocation_bytes},
            {"active_plus_retained_backend_allocation_bytes",
                active_cache_backend_allocation_bytes +
                maximum_simultaneous_backend_allocation_bytes},
            {"complete_host_scaffold_copy_retained", false},
            {"all_retained_roots_closed", llama_state_seq_get_device_root_count(ctx) == 0},
            {"active_recurrent_backing_stable",
                active_recurrent_backing_id(ctx) == active_recurrent_backing_initial},
            {"active_attention_backing_stable",
                active_attention_backing_id(ctx) == active_attention_backing_initial},
            {"restoration_class", "SNAPSHOT_RELOAD"},
        }},
        {"route_summary", semantic_route_summary(results, queries)},
        {"unrelated_reuse_summary", has_reuse_task
            ? semantic_route_summary(reuse_results, spec.at("reuse_queries"))
            : json::object()},
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
            {"unrelated_reuse_joint_correct", reuse_joint_correct},
            {"unrelated_reuse_f_only_correct", reuse_f_only_correct},
            {"unrelated_reuse_g_only_correct", reuse_g_only_correct},
            {"unrelated_reuse_passed", reuse_accepted},
        }},
        {"attention_roots", roots},
        {"records", records},
        {"verdict", complete_acceptance ? "accept" : "reject"},
        {"claim_ceiling", spec.at("claim_ceiling")},
    };
}

static json run_full_hybrid_capability_control(
        llama_context * ctx,
        const llama_vocab * vocab,
        const std::vector<llama_token> & candidates,
        const json & spec,
        uint64_t active_recurrent_backing_initial,
        uint64_t active_attention_backing_initial) {
    const uint32_t actual_context_size = llama_n_ctx(ctx);
    if (spec.contains("expected_context_size") &&
        actual_context_size != spec.at("expected_context_size").get<uint32_t>()) {
        throw std::runtime_error(
            "full-hybrid capability control context mismatch: " +
            std::to_string(actual_context_size));
    }
    const auto source_tokens = prepare_source(ctx, vocab, spec.at("source"));
    const auto & queries = spec.at("queries");
    const size_t active_cache_backend_allocation_bytes =
        active_hybrid_backend_allocation_bytes(ctx);
    auto root = save_root(
        ctx, "frozen-unrelated:full-hybrid", 5000,
        FULL_DEVICE_FLAGS, source_tokens.size());

    std::vector<boundary_result> results;
    json records = json::array();
    for (const auto & query : queries) {
        restore_root(ctx, root);
        if (active_recurrent_backing_id(ctx) != active_recurrent_backing_initial ||
            active_attention_backing_id(ctx) != active_attention_backing_initial) {
            throw std::runtime_error(
                "full-hybrid capability control changed active backing");
        }
        auto boundary = decode_query(
            ctx, vocab, candidates, "untouched-full-hybrid-capability-control",
            "R_F1_G1", query, source_tokens.size(), root.backing_id,
            root.gpu_bytes);
        records.push_back(boundary.record);
        results.push_back(std::move(boundary));
    }

    const size_t correct = semantic_correct_count(results, queries, false);
    const bool accepted =
        correct >= spec.at("acceptance_law").at("correct_minimum").get<size_t>();
    const auto summary = semantic_route_summary(
        std::map<std::string, std::vector<boundary_result>>{
            {"R_F1_G1_FULL", results}}, queries);

    llama_memory_clear(llama_get_memory(ctx), true);
    const size_t cleared_root_bytes =
        llama_state_seq_clear_device_data(ctx, root.key);
    llama_synchronize(ctx);
    if (llama_state_seq_get_device_root_count(ctx) != 0 ||
        active_recurrent_backing_id(ctx) != active_recurrent_backing_initial ||
        active_attention_backing_id(ctx) != active_attention_backing_initial) {
        throw std::runtime_error("full-hybrid capability control close invariant failed");
    }

    return {
        {"schema_version", 1},
        {"mechanism", "FROZEN_UNRELATED_FULL_HYBRID_CAPABILITY_CONTROL"},
        {"spec_id", spec.at("id")},
        {"model_arch", "qwen35moe"},
        {"configuration", {
            {"source_tokens", source_tokens.size()},
            {"query_count", queries.size()},
            {"context_size", actual_context_size},
            {"restoration_class", "SNAPSHOT_RELOAD"},
        }},
        {"root", {
            {"logical_tensor_bytes", root.resident_bytes},
            {"gpu_tensor_bytes", root.gpu_bytes},
            {"backend_allocation_bytes", root.allocation_bytes},
            {"gpu_allocation_bytes", root.allocation_gpu_bytes},
            {"metadata_bytes", root.metadata.size()},
            {"root_backing_id", hex64(root.backing_id)},
            {"restore_count", queries.size()},
            {"cleared_bytes", cleared_root_bytes},
        }},
        {"active_cache_backend_allocation_bytes",
            active_cache_backend_allocation_bytes},
        {"active_plus_retained_backend_allocation_bytes",
            active_cache_backend_allocation_bytes + root.allocation_bytes},
        {"route_summary", summary.at("R_F1_G1_FULL")},
        {"summary", {
            {"correct", correct},
            {"accepted", accepted},
        }},
        {"records", records},
        {"all_retained_roots_closed",
            llama_state_seq_get_device_root_count(ctx) == 0},
        {"active_recurrent_backing_stable",
            active_recurrent_backing_id(ctx) == active_recurrent_backing_initial},
        {"active_attention_backing_stable",
            active_attention_backing_id(ctx) == active_attention_backing_initial},
        {"verdict", accepted ? "accept" : "reject"},
        {"claim_ceiling", spec.at("claim_ceiling")},
    };
}

static json run_full_hybrid_capability_panel(
        llama_context * ctx,
        const llama_vocab * vocab,
        const std::vector<llama_token> & candidates,
        const json & spec,
        uint64_t active_recurrent_backing_initial,
        uint64_t active_attention_backing_initial) {
    const uint32_t actual_context_size = llama_n_ctx(ctx);
    if (actual_context_size != spec.at("expected_context_size").get<uint32_t>()) {
        throw std::runtime_error(
            "full-hybrid capability panel context mismatch: " +
            std::to_string(actual_context_size));
    }
    const size_t expected_source_tokens =
        spec.at("expected_source_tokens").get<size_t>();
    const auto & tasks = spec.at("tasks");
    if (!tasks.is_array() || tasks.empty()) {
        throw std::runtime_error("full-hybrid capability panel has no tasks");
    }

    std::set<std::string> task_ids;
    for (const auto & task : tasks) {
        const std::string id = task.at("id");
        if (!task_ids.insert(id).second) {
            throw std::runtime_error("duplicate capability-panel task id " + id);
        }
        const auto tokens = tokenize_source(vocab, task.at("source"));
        if (tokens.size() != expected_source_tokens) {
            throw std::runtime_error(
                "capability-panel source token mismatch for " + id + ": " +
                std::to_string(tokens.size()));
        }
    }

    const size_t active_cache_backend_allocation_bytes =
        active_hybrid_backend_allocation_bytes(ctx);
    json records = json::array();
    json roots = json::array();
    json task_summary = json::object();
    llama_seq_id key = 6000;
    size_t task_passes = 0;
    size_t root_restore_count = 0;
    size_t root_save_device_copy_bytes = 0;
    size_t root_restore_device_copy_bytes = 0;
    size_t maximum_retained_root_backend_allocation_bytes = 0;

    for (const auto & task : tasks) {
        const std::string id = task.at("id");
        const auto source_tokens = prepare_source(ctx, vocab, task.at("source"));
        auto root = save_root(
            ctx, id + ":full-hybrid", key++, FULL_DEVICE_FLAGS,
            source_tokens.size());
        root_save_device_copy_bytes += root.gpu_bytes;
        maximum_retained_root_backend_allocation_bytes = std::max(
            maximum_retained_root_backend_allocation_bytes,
            root.allocation_bytes);

        std::vector<boundary_result> results;
        for (const auto & query : task.at("queries")) {
            restore_root(ctx, root);
            ++root_restore_count;
            root_restore_device_copy_bytes += root.gpu_bytes;
            if (active_recurrent_backing_id(ctx) != active_recurrent_backing_initial ||
                active_attention_backing_id(ctx) != active_attention_backing_initial) {
                throw std::runtime_error(
                    "capability-panel full root changed active backing");
            }
            auto boundary = decode_query(
                ctx, vocab, candidates, "untouched-full-hybrid-capability-panel",
                id, query, source_tokens.size(), root.backing_id,
                root.gpu_bytes);
            records.push_back(boundary.record);
            results.push_back(std::move(boundary));
        }

        const size_t correct =
            semantic_correct_count(results, task.at("queries"), false);
        std::vector<std::string> answers;
        for (const auto & result : results) {
            answers.push_back(result.argmax);
        }
        const bool passed =
            correct >= task.at("correct_minimum").get<size_t>();
        task_passes += passed;
        task_summary[id] = {
            {"answers", answers},
            {"correct", correct},
            {"passed", passed},
        };
        roots.push_back({
            {"task_id", id},
            {"logical_tensor_bytes", root.resident_bytes},
            {"backend_allocation_bytes", root.allocation_bytes},
            {"metadata_bytes", root.metadata.size()},
            {"root_backing_id", hex64(root.backing_id)},
        });

        llama_memory_clear(llama_get_memory(ctx), true);
        const size_t cleared =
            llama_state_seq_clear_device_data(ctx, root.key);
        if (cleared != root.resident_bytes ||
            llama_state_seq_get_device_root_count(ctx) != 0) {
            throw std::runtime_error(
                "capability-panel full root did not close for " + id);
        }
    }

    llama_synchronize(ctx);
    const size_t required_passes =
        spec.at("acceptance_law").at("task_passes_minimum").get<size_t>();
    const bool accepted = task_passes >= required_passes;
    if (active_recurrent_backing_id(ctx) != active_recurrent_backing_initial ||
        active_attention_backing_id(ctx) != active_attention_backing_initial) {
        throw std::runtime_error("capability-panel close changed active backing");
    }

    return {
        {"schema_version", 1},
        {"mechanism", "DETERMINISTIC_DISJOINT_FULL_HYBRID_CAPABILITY_PANEL"},
        {"spec_id", spec.at("id")},
        {"model_arch", "qwen35moe"},
        {"configuration", {
            {"context_size", actual_context_size},
            {"source_tokens", expected_source_tokens},
            {"task_count", tasks.size()},
            {"queries_per_task", tasks.at(0).at("queries").size()},
            {"restoration_class", "SNAPSHOT_RELOAD"},
        }},
        {"task_summary", task_summary},
        {"summary", {
            {"task_passes", task_passes},
            {"task_count", tasks.size()},
            {"accepted", accepted},
        }},
        {"carrier", {
            {"active_cache_backend_allocation_bytes",
                active_cache_backend_allocation_bytes},
            {"maximum_retained_root_backend_allocation_bytes",
                maximum_retained_root_backend_allocation_bytes},
            {"active_plus_retained_backend_allocation_bytes",
                active_cache_backend_allocation_bytes +
                maximum_retained_root_backend_allocation_bytes},
            {"root_restore_count", root_restore_count},
            {"all_retained_roots_closed",
                llama_state_seq_get_device_root_count(ctx) == 0},
            {"active_recurrent_backing_stable",
                active_recurrent_backing_id(ctx) == active_recurrent_backing_initial},
            {"active_attention_backing_stable",
                active_attention_backing_id(ctx) == active_attention_backing_initial},
        }},
        {"resource_accounting", {
            {"root_save_device_copy_bytes", root_save_device_copy_bytes},
            {"root_restore_device_copy_bytes", root_restore_device_copy_bytes},
        }},
        {"roots", roots},
        {"records", records},
        {"verdict", accepted ? "accept" : "reject"},
        {"claim_ceiling", spec.at("claim_ceiling")},
    };
}

static json run_physical_attention_capability_panel(
        llama_context * ctx,
        const llama_vocab * vocab,
        const std::vector<llama_token> & candidates,
        const json & spec,
        uint64_t active_recurrent_backing_initial,
        uint64_t active_attention_backing_initial) {
    auto * hybrid = require_hybrid_memory(ctx);
    auto * attention = hybrid->get_mem_attn();
    auto * recurrent = hybrid->get_mem_recr();
    const uint32_t actual_context_size = llama_n_ctx(ctx);
    if (actual_context_size != spec.at("expected_context_size").get<uint32_t>()) {
        throw std::runtime_error(
            "physical capability panel context mismatch: " +
            std::to_string(actual_context_size));
    }
    const size_t expected_source_tokens =
        spec.at("expected_source_tokens").get<size_t>();
    const auto & tasks = spec.at("tasks");
    if (!tasks.is_array() || tasks.empty()) {
        throw std::runtime_error("physical capability panel has no tasks");
    }

    const std::vector<uint32_t> attention_layers = attention->get_layer_ids();
    std::vector<uint32_t> recurrent_layers;
    for (uint32_t il = 0; il < recurrent->r_l.size(); ++il) {
        if (recurrent->r_l[il] || recurrent->s_l[il]) {
            recurrent_layers.push_back(il);
        }
    }
    if (attention_layers !=
            spec.at("expected_attention_layers").get<std::vector<uint32_t>>() ||
        recurrent_layers !=
            spec.at("expected_recurrent_layers").get<std::vector<uint32_t>>()) {
        throw std::runtime_error(
            "model hybrid layer topology differs from physical panel spec");
    }

    if (tokenize_source(vocab, spec.at("scaffold_source")).size() !=
        expected_source_tokens) {
        throw std::runtime_error("physical capability panel scaffold token mismatch");
    }
    std::set<std::string> task_ids;
    for (const auto & task : tasks) {
        const std::string id = task.at("id");
        if (!task_ids.insert(id).second) {
            throw std::runtime_error("duplicate physical-panel task id " + id);
        }
        for (const char * arm : {"F_only", "G_only", "joint"}) {
            const auto tokens = tokenize_source(
                vocab, task.at("sources").at(arm));
            if (tokens.size() != expected_source_tokens) {
                throw std::runtime_error(
                    "physical-panel source token mismatch for " + id + ":" +
                    arm + ": " + std::to_string(tokens.size()));
            }
        }
    }

    const auto scaffold_tokens =
        prepare_source(ctx, vocab, spec.at("scaffold_source"));
    auto scaffold_root = save_root(
        ctx, "panel:F0_G0:recurrent-scaffold", 7000,
        RECURRENT_DEVICE_FLAGS, scaffold_tokens.size());
    const auto scaffold_hash_before = hash_recurrent_state_streamed(ctx);
    const size_t active_cache_backend_allocation_bytes =
        active_hybrid_backend_allocation_bytes(ctx);

    using arm_results = std::map<std::string, std::vector<boundary_result>>;
    std::map<std::string, arm_results> results;
    json records = json::array();
    json roots = json::array();
    llama_seq_id key = 7001;
    size_t scaffold_restore_count = 0;
    size_t attention_restore_count = 0;
    size_t cleared_attention_root_bytes = 0;
    size_t attention_metadata_peak_bytes = 0;
    size_t maximum_retained_root_backend_allocation_bytes =
        scaffold_root.allocation_bytes;
    size_t root_save_device_copy_bytes = scaffold_root.gpu_bytes;
    size_t scaffold_restore_device_copy_bytes = 0;
    size_t attention_restore_device_copy_bytes = 0;

    for (const auto & task : tasks) {
        const std::string id = task.at("id");
        for (const char * arm : {"F_only", "G_only", "joint"}) {
            const auto source_tokens =
                prepare_source(ctx, vocab, task.at("sources").at(arm));
            auto attention_root = save_root(
                ctx, id + ":" + arm + ":attention", key++,
                ATTENTION_DEVICE_FLAGS, source_tokens.size());
            root_save_device_copy_bytes += attention_root.gpu_bytes;
            attention_metadata_peak_bytes = std::max(
                attention_metadata_peak_bytes, attention_root.metadata.size());
            maximum_retained_root_backend_allocation_bytes = std::max(
                maximum_retained_root_backend_allocation_bytes,
                scaffold_root.allocation_bytes + attention_root.allocation_bytes);

            for (const auto & query : task.at("queries")) {
                restore_root(ctx, scaffold_root);
                ++scaffold_restore_count;
                scaffold_restore_device_copy_bytes += scaffold_root.gpu_bytes;
                restore_attention_root(ctx, attention_root);
                ++attention_restore_count;
                attention_restore_device_copy_bytes += attention_root.gpu_bytes;
                if (attention->seq_pos_max(0) !=
                        static_cast<llama_pos>(source_tokens.size() - 1) ||
                    recurrent->seq_pos_max(0) !=
                        static_cast<llama_pos>(scaffold_tokens.size() - 1) ||
                    active_recurrent_backing_id(ctx) !=
                        active_recurrent_backing_initial ||
                    active_attention_backing_id(ctx) !=
                        active_attention_backing_initial) {
                    throw std::runtime_error(
                        "assembled physical panel carrier invariant failed");
                }
                auto boundary = decode_query(
                    ctx, vocab, candidates,
                    "physical-attention-capability-panel",
                    id + ":" + arm, query, source_tokens.size(),
                    attention_root.backing_id, attention_root.gpu_bytes);
                records.push_back(boundary.record);
                results[id][arm].push_back(std::move(boundary));
            }

            roots.push_back({
                {"task_id", id},
                {"arm", arm},
                {"logical_tensor_bytes", attention_root.resident_bytes},
                {"backend_allocation_bytes", attention_root.allocation_bytes},
                {"metadata_bytes", attention_root.metadata.size()},
                {"root_backing_id", hex64(attention_root.backing_id)},
            });
            llama_memory_clear(llama_get_memory(ctx), true);
            cleared_attention_root_bytes +=
                llama_state_seq_clear_device_data(ctx, attention_root.key);
            if (llama_state_seq_get_device_root_count(ctx) != 1) {
                throw std::runtime_error(
                    "physical panel attention closure damaged scaffold");
            }
        }
    }

    restore_root(ctx, scaffold_root);
    ++scaffold_restore_count;
    scaffold_restore_device_copy_bytes += scaffold_root.gpu_bytes;
    const auto scaffold_hash_after = hash_recurrent_state_streamed(ctx);
    if (scaffold_hash_after.value != scaffold_hash_before.value ||
        scaffold_hash_after.transferred_bytes !=
            scaffold_hash_before.transferred_bytes) {
        throw std::runtime_error(
            "physical panel recurrent scaffold changed after reuse");
    }

    json task_summary = json::object();
    size_t task_passes = 0;
    for (const auto & task : tasks) {
        const std::string id = task.at("id");
        const auto & task_results = results.at(id);
        const auto & queries = task.at("queries");
        const size_t joint_correct = semantic_correct_count(
            task_results.at("joint"), queries, false);
        const size_t f_only_correct = semantic_correct_count(
            task_results.at("F_only"), queries, false);
        const size_t g_only_correct = semantic_correct_count(
            task_results.at("G_only"), queries, false);
        std::vector<std::string> joint_answers;
        std::vector<std::string> f_only_answers;
        std::vector<std::string> g_only_answers;
        for (const auto & result : task_results.at("joint")) {
            joint_answers.push_back(result.argmax);
        }
        for (const auto & result : task_results.at("F_only")) {
            f_only_answers.push_back(result.argmax);
        }
        for (const auto & result : task_results.at("G_only")) {
            g_only_answers.push_back(result.argmax);
        }
        const bool passed =
            joint_correct >= task.at("joint_correct_minimum").get<size_t>() &&
            f_only_correct <= task.at("f_only_correct_maximum").get<size_t>() &&
            g_only_correct <= task.at("g_only_correct_maximum").get<size_t>();
        task_passes += passed;
        task_summary[id] = {
            {"joint", {
                {"answers", joint_answers},
                {"correct", joint_correct},
            }},
            {"F_only", {
                {"answers", f_only_answers},
                {"correct", f_only_correct},
            }},
            {"G_only", {
                {"answers", g_only_answers},
                {"correct", g_only_correct},
            }},
            {"passed", passed},
        };
    }
    const bool accepted =
        task_passes >=
        spec.at("acceptance_law").at("task_passes_minimum").get<size_t>();

    llama_memory_clear(llama_get_memory(ctx), true);
    const size_t cleared_scaffold_bytes =
        llama_state_seq_clear_device_data(ctx, scaffold_root.key);
    llama_synchronize(ctx);
    if (llama_state_seq_get_device_root_count(ctx) != 0 ||
        active_recurrent_backing_id(ctx) != active_recurrent_backing_initial ||
        active_attention_backing_id(ctx) != active_attention_backing_initial) {
        throw std::runtime_error("physical capability panel close invariant failed");
    }

    return {
        {"schema_version", 1},
        {"mechanism", "DISJOINT_PHYSICAL_ATTENTION_CAPABILITY_PANEL"},
        {"spec_id", spec.at("id")},
        {"model_arch", "qwen35moe"},
        {"configuration", {
            {"context_size", actual_context_size},
            {"source_tokens", expected_source_tokens},
            {"task_count", tasks.size()},
            {"arms_per_task", 3},
            {"queries_per_arm", tasks.at(0).at("queries").size()},
            {"attention_layers", attention_layers},
            {"recurrent_layers", recurrent_layers},
            {"restoration_class", "SNAPSHOT_RELOAD"},
        }},
        {"task_summary", task_summary},
        {"summary", {
            {"task_passes", task_passes},
            {"task_count", tasks.size()},
            {"accepted", accepted},
        }},
        {"carrier", {
            {"scaffold", {
                {"logical_tensor_bytes", scaffold_root.resident_bytes},
                {"backend_allocation_bytes", scaffold_root.allocation_bytes},
                {"metadata_bytes", scaffold_root.metadata.size()},
                {"root_backing_id", hex64(scaffold_root.backing_id)},
                {"restore_count", scaffold_restore_count},
                {"content_hash_before", hex64(scaffold_hash_before.value)},
                {"content_hash_after", hex64(scaffold_hash_after.value)},
                {"cleared_bytes", cleared_scaffold_bytes},
            }},
            {"attention_roots", {
                {"root_count", roots.size()},
                {"restore_count", attention_restore_count},
                {"logical_tensor_bytes_each",
                    roots.empty() ? 0 :
                    roots.at(0).at("logical_tensor_bytes").get<size_t>()},
                {"metadata_peak_bytes", attention_metadata_peak_bytes},
                {"cleared_tensor_bytes", cleared_attention_root_bytes},
            }},
            {"active_cache_backend_allocation_bytes",
                active_cache_backend_allocation_bytes},
            {"maximum_retained_root_backend_allocation_bytes",
                maximum_retained_root_backend_allocation_bytes},
            {"active_plus_retained_backend_allocation_bytes",
                active_cache_backend_allocation_bytes +
                maximum_retained_root_backend_allocation_bytes},
            {"complete_host_scaffold_copy_retained", false},
            {"all_retained_roots_closed",
                llama_state_seq_get_device_root_count(ctx) == 0},
            {"active_recurrent_backing_stable",
                active_recurrent_backing_id(ctx) ==
                active_recurrent_backing_initial},
            {"active_attention_backing_stable",
                active_attention_backing_id(ctx) ==
                active_attention_backing_initial},
        }},
        {"resource_accounting", {
            {"root_save_device_copy_bytes", root_save_device_copy_bytes},
            {"scaffold_restore_device_copy_bytes",
                scaffold_restore_device_copy_bytes},
            {"attention_restore_device_copy_bytes",
                attention_restore_device_copy_bytes},
            {"scaffold_hash_d2h_bytes",
                scaffold_hash_before.transferred_bytes +
                scaffold_hash_after.transferred_bytes},
            {"scaffold_hash_peak_host_work_bytes", std::max(
                scaffold_hash_before.peak_host_work_bytes,
                scaffold_hash_after.peak_host_work_bytes)},
        }},
        {"roots", roots},
        {"records", records},
        {"verdict", accepted ? "accept" : "reject"},
        {"claim_ceiling", spec.at("claim_ceiling")},
    };
}

static json run_attention_operator_composition(
        llama_context * ctx,
        const llama_vocab * vocab,
        const std::vector<llama_token> & candidates,
        const json & spec,
        uint64_t active_recurrent_backing_initial,
        uint64_t active_attention_backing_initial) {
    auto * hybrid = require_hybrid_memory(ctx);
    auto * attention = hybrid->get_mem_attn();
    auto * recurrent = hybrid->get_mem_recr();
    const bool affine_mode =
        spec.value("affine_attention_composition", false);
    const bool position_splice_mode =
        spec.value("position_splice_attention_composition", false);
    if (affine_mode == position_splice_mode) {
        throw std::runtime_error(
            "attention composition spec must select exactly one operator");
    }
    const std::string operator_name = affine_mode
        ? "active_attention = F_only + G_only - neutral"
        : "neutral attention with F and G causal-position splices";
    const std::string candidate_key =
        affine_mode ? "affine" : "position_splice";
    const std::string candidate_route = affine_mode
        ? "affine-attention-composition"
        : "causal-position-attention-splice";
    const std::string candidate_variant = affine_mode
        ? "F_plus_G_minus_neutral"
        : "neutral_with_F_and_G_position_segments";
    const uint32_t actual_context_size = llama_n_ctx(ctx);
    if (actual_context_size != spec.at("expected_context_size").get<uint32_t>()) {
        throw std::runtime_error(
            "attention operator composition context mismatch: " +
            std::to_string(actual_context_size));
    }
    const size_t expected_source_tokens =
        spec.at("expected_source_tokens").get<size_t>();
    const auto & tasks = spec.at("tasks");
    if (!tasks.is_array() || tasks.empty()) {
        throw std::runtime_error("attention operator composition has no tasks");
    }
    if (spec.contains("joint_source")) {
        throw std::runtime_error(
            "attention operator composition must not contain a joint source");
    }

    const std::vector<uint32_t> attention_layers = attention->get_layer_ids();
    std::vector<uint32_t> recurrent_layers;
    for (uint32_t il = 0; il < recurrent->r_l.size(); ++il) {
        if (recurrent->r_l[il] || recurrent->s_l[il]) {
            recurrent_layers.push_back(il);
        }
    }
    if (attention_layers !=
            spec.at("expected_attention_layers").get<std::vector<uint32_t>>() ||
        recurrent_layers !=
            spec.at("expected_recurrent_layers").get<std::vector<uint32_t>>()) {
        throw std::runtime_error(
            "model hybrid layer topology differs from operator composition spec");
    }

    const auto source_piece_sizes =
            [&](const json & source) -> std::vector<size_t> {
        std::vector<size_t> result;
        bool first = true;
        for (const char * field :
                {"prefix", "module_f", "module_g", "closure"}) {
            result.push_back(tokenize_piece(
                vocab, source.at(field).get<std::string>(), first, true).size());
            first = false;
        }
        return result;
    };
    const auto expected_piece_sizes =
        source_piece_sizes(spec.at("neutral_source"));
    if (expected_piece_sizes.size() != 4) {
        throw std::runtime_error("invalid source piece count");
    }
    const size_t f_position_begin = expected_piece_sizes[0];
    const size_t f_position_end =
        f_position_begin + expected_piece_sizes[1];
    const size_t g_position_begin = f_position_end;
    const size_t g_position_end =
        g_position_begin + expected_piece_sizes[2];
    if (g_position_end >= expected_source_tokens) {
        throw std::runtime_error(
            "source causal-position layout leaves no closure");
    }

    for (const char * source_name : {"neutral_source", "shared_g_source"}) {
        const auto tokens = tokenize_source(vocab, spec.at(source_name));
        if (tokens.size() != expected_source_tokens) {
            throw std::runtime_error(
                std::string("operator composition source token mismatch for ") +
                source_name + ": " + std::to_string(tokens.size()));
        }
        if (source_piece_sizes(spec.at(source_name)) != expected_piece_sizes) {
            throw std::runtime_error(
                std::string("operator source piece layout mismatch for ") +
                source_name);
        }
    }
    std::set<std::string> task_ids;
    for (const auto & task : tasks) {
        const std::string id = task.at("id");
        if (!task_ids.insert(id).second) {
            throw std::runtime_error(
                "duplicate operator-composition task id " + id);
        }
        if (task.contains("joint") ||
            task.contains("joint_source") ||
            task.contains("sources")) {
            throw std::runtime_error(
                "operator composition task exposes a forbidden joint/source map");
        }
        if (tokenize_source(vocab, task.at("f_source")).size() !=
            expected_source_tokens) {
            throw std::runtime_error(
                "operator composition F source token mismatch for " + id);
        }
        if (source_piece_sizes(task.at("f_source")) != expected_piece_sizes) {
            throw std::runtime_error(
                "operator composition F source piece layout mismatch for " + id);
        }
    }

    const auto neutral_tokens =
        prepare_source(ctx, vocab, spec.at("neutral_source"));
    auto scaffold_root = save_root(
        ctx, candidate_key + ":F0_G0:recurrent-scaffold", 9000,
        RECURRENT_DEVICE_FLAGS, neutral_tokens.size());
    auto neutral_root = save_root(
        ctx, candidate_key + ":F0_G0:attention", 9001,
        ATTENTION_DEVICE_FLAGS, neutral_tokens.size());
    const auto scaffold_hash_before = hash_recurrent_state_streamed(ctx);

    const auto g_tokens =
        prepare_source(ctx, vocab, spec.at("shared_g_source"));
    auto g_root = save_root(
        ctx, candidate_key + ":F0_G1:attention", 9002,
        ATTENTION_DEVICE_FLAGS, g_tokens.size());
    const size_t active_cache_backend_allocation_bytes =
        active_hybrid_backend_allocation_bytes(ctx);

    using route_results = std::map<std::string, std::vector<boundary_result>>;
    std::map<std::string, route_results> results;
    json records = json::array();
    json roots = json::array({
        {
            {"role", "recurrent-scaffold"},
            {"logical_tensor_bytes", scaffold_root.resident_bytes},
            {"backend_allocation_bytes", scaffold_root.allocation_bytes},
            {"root_backing_id", hex64(scaffold_root.backing_id)},
        },
        {
            {"role", "neutral-attention"},
            {"logical_tensor_bytes", neutral_root.resident_bytes},
            {"backend_allocation_bytes", neutral_root.allocation_bytes},
            {"root_backing_id", hex64(neutral_root.backing_id)},
        },
        {
            {"role", "shared-G-attention"},
            {"logical_tensor_bytes", g_root.resident_bytes},
            {"backend_allocation_bytes", g_root.allocation_bytes},
            {"root_backing_id", hex64(g_root.backing_id)},
        },
    });
    llama_seq_id f_key = 9003;
    size_t scaffold_restore_count = 0;
    size_t attention_restore_count = 0;
    size_t source_decode_tokens =
        neutral_tokens.size() + g_tokens.size();
    size_t query_decode_tokens = 0;
    size_t root_save_device_copy_bytes =
        scaffold_root.gpu_bytes + neutral_root.gpu_bytes + g_root.gpu_bytes;
    size_t scaffold_restore_device_copy_bytes = 0;
    size_t attention_restore_device_copy_bytes = 0;
    size_t cleared_f_root_bytes = 0;
    size_t maximum_retained_root_backend_allocation_bytes =
        scaffold_root.allocation_bytes +
        neutral_root.allocation_bytes +
        g_root.allocation_bytes;
    uint64_t affine_root_bytes_read = 0;
    uint64_t affine_active_bytes_written = 0;
    uint64_t affine_peak_host_work_bytes = 0;
    uint64_t affine_tensor_count_total = 0;
    size_t affine_apply_count = 0;
    bool affine_metrics_stable = true;
    llama_state_seq_affine_metrics first_affine_metrics = {};
    bool have_first_affine_metrics = false;
    uint64_t splice_backend_bytes_copied = 0;
    uint64_t splice_tensor_count_total = 0;
    uint64_t splice_host_metadata_bytes_peak = 0;
    size_t splice_range_apply_count = 0;
    bool splice_metrics_stable = true;
    llama_state_seq_splice_metrics first_f_splice_metrics = {};
    llama_state_seq_splice_metrics first_g_splice_metrics = {};
    bool have_first_splice_metrics = false;

    for (const auto & task : tasks) {
        const std::string id = task.at("id");
        const auto f_tokens =
            prepare_source(ctx, vocab, task.at("f_source"));
        source_decode_tokens += f_tokens.size();
        auto f_root = save_root(
            ctx, id + ":F1_G0:attention", f_key++,
            ATTENTION_DEVICE_FLAGS, f_tokens.size());
        root_save_device_copy_bytes += f_root.gpu_bytes;
        maximum_retained_root_backend_allocation_bytes = std::max(
            maximum_retained_root_backend_allocation_bytes,
            scaffold_root.allocation_bytes +
            neutral_root.allocation_bytes +
            g_root.allocation_bytes +
            f_root.allocation_bytes);
        roots.push_back({
            {"role", "task-F-attention"},
            {"task_id", id},
            {"logical_tensor_bytes", f_root.resident_bytes},
            {"backend_allocation_bytes", f_root.allocation_bytes},
            {"root_backing_id", hex64(f_root.backing_id)},
        });

        for (const auto & query : task.at("queries")) {
            restore_root(ctx, scaffold_root);
            ++scaffold_restore_count;
            scaffold_restore_device_copy_bytes += scaffold_root.gpu_bytes;
            restore_attention_root(ctx, f_root);
            ++attention_restore_count;
            attention_restore_device_copy_bytes += f_root.gpu_bytes;
            auto f_boundary = decode_query(
                ctx, vocab, candidates, "F-only-control",
                id + ":F_only", query, expected_source_tokens,
                f_root.backing_id, f_root.gpu_bytes);
            query_decode_tokens +=
                f_boundary.record.at("query_tokens").get<size_t>();
            records.push_back(f_boundary.record);
            results[id]["F_only"].push_back(std::move(f_boundary));

            restore_root(ctx, scaffold_root);
            ++scaffold_restore_count;
            scaffold_restore_device_copy_bytes += scaffold_root.gpu_bytes;
            restore_attention_root(ctx, g_root);
            ++attention_restore_count;
            attention_restore_device_copy_bytes += g_root.gpu_bytes;
            auto g_boundary = decode_query(
                ctx, vocab, candidates, "G-only-control",
                id + ":G_only", query, expected_source_tokens,
                g_root.backing_id, g_root.gpu_bytes);
            query_decode_tokens +=
                g_boundary.record.at("query_tokens").get<size_t>();
            records.push_back(g_boundary.record);
            results[id]["G_only"].push_back(std::move(g_boundary));

            restore_root(ctx, scaffold_root);
            ++scaffold_restore_count;
            scaffold_restore_device_copy_bytes += scaffold_root.gpu_bytes;
            const auto & construction_base =
                affine_mode ? f_root : neutral_root;
            restore_attention_root(ctx, construction_base);
            ++attention_restore_count;
            attention_restore_device_copy_bytes +=
                construction_base.gpu_bytes;
            if (affine_mode) {
                llama_state_seq_affine_metrics affine_metrics = {};
                if (!llama_state_seq_apply_device_affine(
                        ctx,
                        f_root.key,
                        g_root.key,
                        neutral_root.key,
                        &affine_metrics)) {
                    throw std::runtime_error(
                        "in-place affine attention construction failed for " +
                        id);
                }
                if (!have_first_affine_metrics) {
                    first_affine_metrics = affine_metrics;
                    have_first_affine_metrics = true;
                } else {
                    affine_metrics_stable =
                        affine_metrics_stable &&
                        first_affine_metrics.root_bytes_read ==
                            affine_metrics.root_bytes_read &&
                        first_affine_metrics.active_bytes_written ==
                            affine_metrics.active_bytes_written &&
                        first_affine_metrics.peak_host_work_bytes ==
                            affine_metrics.peak_host_work_bytes &&
                        first_affine_metrics.tensor_count ==
                            affine_metrics.tensor_count;
                }
                affine_root_bytes_read += affine_metrics.root_bytes_read;
                affine_active_bytes_written +=
                    affine_metrics.active_bytes_written;
                affine_peak_host_work_bytes = std::max(
                    affine_peak_host_work_bytes,
                    affine_metrics.peak_host_work_bytes);
                affine_tensor_count_total += affine_metrics.tensor_count;
                ++affine_apply_count;
            } else {
                llama_state_seq_splice_metrics f_metrics = {};
                llama_state_seq_splice_metrics g_metrics = {};
                if (!llama_state_seq_splice_device_positions(
                        ctx, f_root.key, expected_source_tokens,
                        f_position_begin, f_position_end, &f_metrics) ||
                    !llama_state_seq_splice_device_positions(
                        ctx, g_root.key, expected_source_tokens,
                        g_position_begin, g_position_end, &g_metrics)) {
                    throw std::runtime_error(
                        "causal-position attention splice failed for " + id);
                }
                if (!have_first_splice_metrics) {
                    first_f_splice_metrics = f_metrics;
                    first_g_splice_metrics = g_metrics;
                    have_first_splice_metrics = true;
                } else {
                    const auto metrics_equal =
                            [](const llama_state_seq_splice_metrics & lhs,
                               const llama_state_seq_splice_metrics & rhs) {
                        return
                            lhs.backend_bytes_copied ==
                                rhs.backend_bytes_copied &&
                            lhs.tensor_count == rhs.tensor_count &&
                            lhs.host_metadata_bytes ==
                                rhs.host_metadata_bytes &&
                            lhs.total_positions == rhs.total_positions &&
                            lhs.position_begin == rhs.position_begin &&
                            lhs.position_end == rhs.position_end;
                    };
                    splice_metrics_stable =
                        splice_metrics_stable &&
                        metrics_equal(first_f_splice_metrics, f_metrics) &&
                        metrics_equal(first_g_splice_metrics, g_metrics);
                }
                splice_backend_bytes_copied +=
                    f_metrics.backend_bytes_copied +
                    g_metrics.backend_bytes_copied;
                splice_tensor_count_total +=
                    f_metrics.tensor_count + g_metrics.tensor_count;
                splice_host_metadata_bytes_peak = std::max({
                    splice_host_metadata_bytes_peak,
                    f_metrics.host_metadata_bytes,
                    g_metrics.host_metadata_bytes,
                });
                splice_range_apply_count += 2;
            }
            if (attention->seq_pos_max(0) !=
                    static_cast<llama_pos>(expected_source_tokens - 1) ||
                recurrent->seq_pos_max(0) !=
                    static_cast<llama_pos>(expected_source_tokens - 1) ||
                active_recurrent_backing_id(ctx) !=
                    active_recurrent_backing_initial ||
                active_attention_backing_id(ctx) !=
                    active_attention_backing_initial) {
                throw std::runtime_error(
                    "operator active-carrier invariant failed for " + id);
            }
            auto candidate_boundary = decode_query(
                ctx, vocab, candidates, candidate_route,
                id + ":" + candidate_variant, query,
                expected_source_tokens, construction_base.backing_id,
                construction_base.gpu_bytes);
            query_decode_tokens +=
                candidate_boundary.record.at("query_tokens").get<size_t>();
            records.push_back(candidate_boundary.record);
            results[id][candidate_key].push_back(
                std::move(candidate_boundary));
        }

        llama_memory_clear(llama_get_memory(ctx), true);
        cleared_f_root_bytes +=
            llama_state_seq_clear_device_data(ctx, f_root.key);
        if (llama_state_seq_get_device_root_count(ctx) != 3) {
            throw std::runtime_error(
                "operator task-root closure damaged shared roots");
        }
    }

    restore_root(ctx, scaffold_root);
    ++scaffold_restore_count;
    scaffold_restore_device_copy_bytes += scaffold_root.gpu_bytes;
    const auto scaffold_hash_after = hash_recurrent_state_streamed(ctx);
    const bool scaffold_tensor_digest_match =
        scaffold_hash_before.value == scaffold_hash_after.value &&
        scaffold_hash_before.transferred_bytes ==
            scaffold_hash_after.transferred_bytes;

    json task_summary = json::object();
    size_t task_passes = 0;
    for (const auto & task : tasks) {
        const std::string id = task.at("id");
        const auto & task_results = results.at(id);
        const auto & queries = task.at("queries");
        const size_t candidate_correct = semantic_correct_count(
            task_results.at(candidate_key), queries, false);
        const size_t f_only_correct = semantic_correct_count(
            task_results.at("F_only"), queries, false);
        const size_t g_only_correct = semantic_correct_count(
            task_results.at("G_only"), queries, false);
        std::vector<std::string> candidate_answers;
        std::vector<std::string> f_only_answers;
        std::vector<std::string> g_only_answers;
        for (const auto & result : task_results.at(candidate_key)) {
            candidate_answers.push_back(result.argmax);
        }
        for (const auto & result : task_results.at("F_only")) {
            f_only_answers.push_back(result.argmax);
        }
        for (const auto & result : task_results.at("G_only")) {
            g_only_answers.push_back(result.argmax);
        }
        const char * candidate_minimum_field = affine_mode
            ? "affine_correct_minimum"
            : "position_splice_correct_minimum";
        const bool passed =
            candidate_correct >=
                task.at(candidate_minimum_field).get<size_t>() &&
            f_only_correct <=
                task.at("f_only_correct_maximum").get<size_t>() &&
            g_only_correct <=
                task.at("g_only_correct_maximum").get<size_t>();
        task_passes += passed;
        task_summary[id] = {
            {candidate_key, {
                {"answers", candidate_answers},
                {"correct", candidate_correct},
            }},
            {"F_only", {
                {"answers", f_only_answers},
                {"correct", f_only_correct},
            }},
            {"G_only", {
                {"answers", g_only_answers},
                {"correct", g_only_correct},
            }},
            {"passed", passed},
        };
    }
    const bool accepted =
        task_passes >=
            spec.at("acceptance_law")
                .at("task_passes_minimum").get<size_t>() &&
        scaffold_tensor_digest_match &&
        (affine_mode
            ? affine_metrics_stable && have_first_affine_metrics
            : splice_metrics_stable && have_first_splice_metrics);

    llama_memory_clear(llama_get_memory(ctx), true);
    const size_t cleared_neutral_root_bytes =
        llama_state_seq_clear_device_data(ctx, neutral_root.key);
    const size_t cleared_g_root_bytes =
        llama_state_seq_clear_device_data(ctx, g_root.key);
    const size_t cleared_scaffold_bytes =
        llama_state_seq_clear_device_data(ctx, scaffold_root.key);
    llama_synchronize(ctx);
    if (llama_state_seq_get_device_root_count(ctx) != 0 ||
        active_recurrent_backing_id(ctx) != active_recurrent_backing_initial ||
        active_attention_backing_id(ctx) != active_attention_backing_initial) {
        throw std::runtime_error(
            "attention operator composition close invariant failed");
    }

    json construction;
    if (affine_mode) {
        construction = {
            {"operator_apply_count", affine_apply_count},
            {"root_bytes_read", affine_root_bytes_read},
            {"active_bytes_written", affine_active_bytes_written},
            {"peak_host_work_bytes", affine_peak_host_work_bytes},
            {"tensor_visits", affine_tensor_count_total},
            {"per_apply", {
                {"root_bytes_read", first_affine_metrics.root_bytes_read},
                {"active_bytes_written",
                    first_affine_metrics.active_bytes_written},
                {"peak_host_work_bytes",
                    first_affine_metrics.peak_host_work_bytes},
                {"tensor_count", first_affine_metrics.tensor_count},
            }},
        };
    } else {
        construction = {
            {"operator_apply_count", splice_range_apply_count / 2},
            {"range_copy_count", splice_range_apply_count},
            {"backend_bytes_copied", splice_backend_bytes_copied},
            {"tensor_visits", splice_tensor_count_total},
            {"peak_host_payload_work_bytes", 0},
            {"peak_host_metadata_bytes", splice_host_metadata_bytes_peak},
            {"position_layout", {
                {"prefix", {
                    {"begin", 0},
                    {"end", f_position_begin},
                }},
                {"module_f", {
                    {"begin", f_position_begin},
                    {"end", f_position_end},
                }},
                {"module_g", {
                    {"begin", g_position_begin},
                    {"end", g_position_end},
                }},
                {"closure", {
                    {"begin", g_position_end},
                    {"end", expected_source_tokens},
                }},
            }},
            {"F_range_per_apply", {
                {"backend_bytes_copied",
                    first_f_splice_metrics.backend_bytes_copied},
                {"tensor_count", first_f_splice_metrics.tensor_count},
                {"position_begin", first_f_splice_metrics.position_begin},
                {"position_end", first_f_splice_metrics.position_end},
            }},
            {"G_range_per_apply", {
                {"backend_bytes_copied",
                    first_g_splice_metrics.backend_bytes_copied},
                {"tensor_count", first_g_splice_metrics.tensor_count},
                {"position_begin", first_g_splice_metrics.position_begin},
                {"position_end", first_g_splice_metrics.position_end},
            }},
        };
    }

    return {
        {"schema_version", 1},
        {"mechanism", affine_mode
            ? "IN_PLACE_AFFINE_ATTENTION_COMPOSITION_SHAM"
            : "DIRECT_CAUSAL_POSITION_ATTENTION_SPLICE"},
        {"spec_id", spec.at("id")},
        {"model_arch", "qwen35moe"},
        {"configuration", {
            {"context_size", actual_context_size},
            {"source_tokens", expected_source_tokens},
            {"task_count", tasks.size()},
            {"queries_per_task", tasks.at(0).at("queries").size()},
            {"attention_layers", attention_layers},
            {"recurrent_layers", recurrent_layers},
            {"operator", operator_name},
            {"joint_source_available_to_candidate", false},
            {"restoration_class", "SNAPSHOT_RELOAD"},
        }},
        {"summary", {
            {"task_passes", task_passes},
            {"task_count", tasks.size()},
            {"scaffold_recurrent_tensor_digest_match",
                scaffold_tensor_digest_match},
            {"operator_metrics_stable", affine_mode
                ? affine_metrics_stable
                : splice_metrics_stable},
            {"accepted", accepted},
        }},
        {"task_summary", task_summary},
        {"carrier", {
            {"scaffold", {
                {"logical_tensor_bytes", scaffold_root.resident_bytes},
                {"backend_allocation_bytes",
                    scaffold_root.allocation_bytes},
                {"root_backing_id", hex64(scaffold_root.backing_id)},
                {"restore_count", scaffold_restore_count},
                {"recurrent_tensor_digest_before",
                    hex64(scaffold_hash_before.value)},
                {"recurrent_tensor_digest_after",
                    hex64(scaffold_hash_after.value)},
            }},
            {"neutral_attention_root_bytes", neutral_root.resident_bytes},
            {"shared_g_attention_root_bytes", g_root.resident_bytes},
            {"attention_restore_count", attention_restore_count},
            {"active_cache_backend_allocation_bytes",
                active_cache_backend_allocation_bytes},
            {"maximum_retained_root_backend_allocation_bytes",
                maximum_retained_root_backend_allocation_bytes},
            {"active_plus_retained_backend_allocation_bytes",
                active_cache_backend_allocation_bytes +
                maximum_retained_root_backend_allocation_bytes},
            {"active_recurrent_backing_stable",
                active_recurrent_backing_id(ctx) ==
                active_recurrent_backing_initial},
            {"active_attention_backing_stable",
                active_attention_backing_id(ctx) ==
                active_attention_backing_initial},
            {"complete_host_attention_copy_retained", false},
            {"joint_attention_root_constructed", false},
            {"all_retained_roots_closed",
                llama_state_seq_get_device_root_count(ctx) == 0},
        }},
        {"construction", construction},
        {"resource_accounting", {
            {"fresh_source_decode_tokens", source_decode_tokens},
            {"fresh_query_decode_tokens", query_decode_tokens},
            {"fresh_input_tokens_total",
                source_decode_tokens + query_decode_tokens},
            {"root_save_device_copy_bytes", root_save_device_copy_bytes},
            {"scaffold_restore_device_copy_bytes",
                scaffold_restore_device_copy_bytes},
            {"attention_restore_device_copy_bytes",
                attention_restore_device_copy_bytes},
            {"scaffold_digest_d2h_bytes",
                scaffold_hash_before.transferred_bytes +
                scaffold_hash_after.transferred_bytes},
            {"scaffold_digest_peak_host_work_bytes", std::max(
                scaffold_hash_before.peak_host_work_bytes,
                scaffold_hash_after.peak_host_work_bytes)},
            {"cleared_f_root_bytes", cleared_f_root_bytes},
            {"cleared_neutral_root_bytes", cleared_neutral_root_bytes},
            {"cleared_g_root_bytes", cleared_g_root_bytes},
            {"cleared_scaffold_bytes", cleared_scaffold_bytes},
        }},
        {"roots", roots},
        {"records", records},
        {"verdict", accepted ? "accept" : "reject"},
        {"claim_ceiling", spec.at("claim_ceiling")},
    };
}

static json run_active_f_sequence_branching(
        llama_context * ctx,
        const llama_vocab * vocab,
        const std::vector<llama_token> & candidates,
        const json & spec,
        uint64_t active_recurrent_backing_initial,
        uint64_t active_attention_backing_initial) {
    const uint32_t actual_context_size = llama_n_ctx(ctx);
    const uint32_t actual_n_seq_max = llama_n_seq_max(ctx);
    const uint32_t actual_context_per_sequence =
        actual_context_size / actual_n_seq_max;
    if (actual_context_size !=
            spec.at("expected_context_size").get<uint32_t>() ||
        actual_n_seq_max !=
            spec.at("expected_n_seq_max").get<uint32_t>() ||
        actual_context_per_sequence !=
            spec.at("expected_context_per_sequence").get<uint32_t>()) {
        throw std::runtime_error(
            "active-F sequence geometry mismatch: ctx=" +
            std::to_string(actual_context_size) + " seqs=" +
            std::to_string(actual_n_seq_max) + " per-seq=" +
            std::to_string(actual_context_per_sequence));
    }

    const size_t expected_source_tokens =
        spec.at("expected_source_tokens").get<size_t>();
    const auto prefix_tokens = tokenize_piece(
        vocab, spec.at("prefix").get<std::string>(), true, true);
    const auto f_tokens = tokenize_piece(
        vocab, spec.at("module_f").get<std::string>(), false, true);
    const auto neutral_f_tokens = tokenize_piece(
        vocab, spec.at("neutral_module_f").get<std::string>(), false, true);
    const auto neutral_g_tokens = tokenize_piece(
        vocab, spec.at("neutral_module_g").get<std::string>(), false, true);
    const auto closure_tokens = tokenize_piece(
        vocab, spec.at("closure").get<std::string>(), false, true);
    const size_t f_boundary_tokens =
        prefix_tokens.size() + f_tokens.size();
    if (prefix_tokens.size() !=
            spec.at("expected_prefix_tokens").get<size_t>() ||
        f_tokens.size() != spec.at("expected_f_tokens").get<size_t>() ||
        neutral_f_tokens.size() != f_tokens.size() ||
        neutral_g_tokens.size() !=
            spec.at("expected_g_tokens").get<size_t>() ||
        closure_tokens.size() !=
            spec.at("expected_closure_tokens").get<size_t>() ||
        f_boundary_tokens + neutral_g_tokens.size() +
            closure_tokens.size() != expected_source_tokens) {
        throw std::runtime_error(
            "active-F public token geometry mismatch");
    }

    const auto & variants = spec.at("g_variants");
    if (!variants.is_array() || variants.empty()) {
        throw std::runtime_error("active-F sequence branch has no G variants");
    }
    std::set<std::string> variant_ids;
    for (const auto & variant : variants) {
        const std::string id = variant.at("id");
        const auto g_tokens = tokenize_piece(
            vocab, variant.at("module_g").get<std::string>(), false, true);
        if (!variant_ids.insert(id).second ||
            g_tokens.size() != neutral_g_tokens.size() ||
            variant.at("queries").size() !=
                spec.at("queries_per_variant").get<size_t>()) {
            throw std::runtime_error(
                "active-F G variant geometry mismatch for " + id);
        }
    }

    auto * hybrid = require_hybrid_memory(ctx);
    llama_memory_t memory = llama_get_memory(ctx);
    const size_t active_cache_backend_allocation_bytes =
        active_hybrid_backend_allocation_bytes(ctx);
    const uint64_t active_recurrent_backing =
        active_recurrent_backing_id(ctx);
    const uint64_t active_attention_backing =
        active_attention_backing_id(ctx);
    const llama_seq_id carrier_seq = 0;
    const llama_seq_id branch_seq = 1;
    const llama_seq_id query_seq = 2;
    const llama_pos f_boundary_pos =
        static_cast<llama_pos>(f_boundary_tokens - 1);
    const llama_pos source_boundary_pos =
        static_cast<llama_pos>(expected_source_tokens - 1);

    const auto require_sequence_position =
            [&](llama_seq_id seq_id,
                llama_pos expected,
                const std::string & stage) {
        const llama_pos attention_pos =
            hybrid->get_mem_attn()->seq_pos_max(seq_id);
        const llama_pos recurrent_pos =
            hybrid->get_mem_recr()->seq_pos_max(seq_id);
        if (attention_pos != expected || recurrent_pos != expected) {
            throw std::runtime_error(
                stage + " sequence " + std::to_string(seq_id) +
                " position mismatch: attention=" +
                std::to_string(attention_pos) + " recurrent=" +
                std::to_string(recurrent_pos) + " expected=" +
                std::to_string(expected));
        }
    };
    const auto close_sequence =
            [&](llama_seq_id seq_id, const std::string & stage) {
        if (!llama_memory_seq_rm(memory, seq_id, -1, -1)) {
            throw std::runtime_error(
                stage + " failed to close sequence " +
                std::to_string(seq_id));
        }
        llama_synchronize(ctx);
        require_sequence_position(seq_id, -1, stage + ":closed");
    };
    const auto copy_sequence =
            [&](llama_seq_id src,
                llama_seq_id dst,
                llama_pos expected,
                const std::string & stage) {
        require_sequence_position(dst, -1, stage + ":destination-empty");
        llama_memory_seq_cp(memory, src, dst, -1, -1);
        llama_synchronize(ctx);
        require_sequence_position(dst, expected, stage + ":copied");
    };

    json records = json::array();
    std::map<std::string, std::vector<boundary_result>> candidate_results;
    std::map<std::string, std::vector<boundary_result>> reference_results;
    std::map<std::string, std::vector<boundary_result>> g_only_results;
    size_t query_decode_tokens = 0;
    size_t sequence_copy_count = 0;
    size_t sequence_close_count = 0;
    const auto query_from_anchor =
            [&](llama_seq_id anchor,
                llama_seq_id scratch,
                const std::string & route,
                const std::string & variant_id,
                const json & queries,
                std::vector<boundary_result> & outputs) {
        for (const auto & query : queries) {
            copy_sequence(
                anchor, scratch, source_boundary_pos,
                route + ":query-copy");
            ++sequence_copy_count;
            auto boundary = decode_query(
                ctx,
                vocab,
                candidates,
                route,
                variant_id,
                query,
                expected_source_tokens,
                active_recurrent_backing,
                active_cache_backend_allocation_bytes,
                scratch);
            query_decode_tokens +=
                boundary.record.at("query_tokens").get<size_t>();
            records.push_back(boundary.record);
            outputs.push_back(std::move(boundary));
            close_sequence(scratch, route + ":query-close");
            ++sequence_close_count;
            require_sequence_position(
                anchor, source_boundary_pos,
                route + ":anchor-survives-query");
        }
    };

    llama_memory_clear(memory, true);
    decode_tokens(ctx, prefix_tokens, 0, false, carrier_seq);
    decode_tokens(
        ctx, f_tokens,
        static_cast<llama_pos>(prefix_tokens.size()),
        false, carrier_seq);
    llama_synchronize(ctx);
    require_sequence_position(
        carrier_seq, f_boundary_pos, "active-F-created");
    require_sequence_position(branch_seq, -1, "active-F-branch-empty");
    require_sequence_position(query_seq, -1, "active-F-query-empty");
    if (llama_state_seq_get_device_root_count(ctx) != 0) {
        throw std::runtime_error(
            "active-F candidate unexpectedly has retained roots");
    }

    const auto f_recurrent_before =
        hash_recurrent_sequence_streamed(ctx, carrier_seq);
    const size_t candidate_primary_source_tokens =
        prefix_tokens.size() + f_tokens.size() +
        variants.size() *
            (neutral_g_tokens.size() + closure_tokens.size());
    size_t candidate_suffix_decode_tokens = 0;
    size_t repeat_sentinel_source_tokens = 0;
    size_t f_only_source_tokens = 0;

    for (const auto & variant : variants) {
        const std::string id = variant.at("id");
        const auto g_tokens = tokenize_piece(
            vocab, variant.at("module_g").get<std::string>(), false, true);
        copy_sequence(
            carrier_seq, branch_seq, f_boundary_pos,
            id + ":F-to-G-branch");
        ++sequence_copy_count;
        decode_tokens(
            ctx, g_tokens,
            static_cast<llama_pos>(f_boundary_tokens),
            false, branch_seq);
        decode_tokens(
            ctx, closure_tokens,
            static_cast<llama_pos>(
                f_boundary_tokens + g_tokens.size()),
            false, branch_seq);
        llama_synchronize(ctx);
        candidate_suffix_decode_tokens +=
            g_tokens.size() + closure_tokens.size();
        require_sequence_position(
            carrier_seq, f_boundary_pos,
            id + ":F-survives-G-forward");
        require_sequence_position(
            branch_seq, source_boundary_pos,
            id + ":G-forward-complete");
        query_from_anchor(
            branch_seq,
            query_seq,
            "active-F-copy-on-write-branch",
            id + ":candidate",
            variant.at("queries"),
            candidate_results[id]);
        close_sequence(branch_seq, id + ":G-branch-close");
        ++sequence_close_count;
        require_sequence_position(
            carrier_seq, f_boundary_pos,
            id + ":F-survives-branch-close");
    }

    const auto & repeat_variant = variants.at(0);
    const std::string repeat_id = repeat_variant.at("id");
    const auto repeat_g_tokens = tokenize_piece(
        vocab,
        repeat_variant.at("module_g").get<std::string>(),
        false,
        true);
    copy_sequence(
        carrier_seq, branch_seq, f_boundary_pos,
        "repeat-sentinel:F-to-G-branch");
    ++sequence_copy_count;
    decode_tokens(
        ctx, repeat_g_tokens,
        static_cast<llama_pos>(f_boundary_tokens),
        false, branch_seq);
    decode_tokens(
        ctx, closure_tokens,
        static_cast<llama_pos>(
            f_boundary_tokens + repeat_g_tokens.size()),
        false, branch_seq);
    llama_synchronize(ctx);
    repeat_sentinel_source_tokens =
        repeat_g_tokens.size() + closure_tokens.size();
    std::vector<boundary_result> repeat_results;
    query_from_anchor(
        branch_seq,
        query_seq,
        "active-F-repeat-reuse-sentinel",
        repeat_id + ":repeat",
        repeat_variant.at("queries"),
        repeat_results);
    close_sequence(branch_seq, "repeat-sentinel:G-branch-close");
    ++sequence_close_count;

    copy_sequence(
        carrier_seq, branch_seq, f_boundary_pos,
        "F-only:F-to-neutral-G-branch");
    ++sequence_copy_count;
    decode_tokens(
        ctx, neutral_g_tokens,
        static_cast<llama_pos>(f_boundary_tokens),
        false, branch_seq);
    decode_tokens(
        ctx, closure_tokens,
        static_cast<llama_pos>(
            f_boundary_tokens + neutral_g_tokens.size()),
        false, branch_seq);
    llama_synchronize(ctx);
    f_only_source_tokens +=
        neutral_g_tokens.size() + closure_tokens.size();
    std::vector<boundary_result> f_only_results;
    query_from_anchor(
        branch_seq,
        query_seq,
        "active-F-F-only-control",
        "F_only",
        spec.at("f_only_queries"),
        f_only_results);
    close_sequence(branch_seq, "F-only:branch-close");
    ++sequence_close_count;

    const auto f_recurrent_after =
        hash_recurrent_sequence_streamed(ctx, carrier_seq);
    const bool f_recurrent_content_exact =
        f_recurrent_before.tensor.value ==
            f_recurrent_after.tensor.value &&
        f_recurrent_before.tensor.transferred_bytes ==
            f_recurrent_after.tensor.transferred_bytes &&
        f_recurrent_before.position == f_recurrent_after.position;
    const bool f_recurrent_physical_row_stable =
        f_recurrent_before.physical_row ==
            f_recurrent_after.physical_row;
    require_sequence_position(
        carrier_seq, f_boundary_pos,
        "active-F-before-reference-close");
    close_sequence(carrier_seq, "active-F-final-close");
    ++sequence_close_count;

    size_t reference_full_source_tokens = 0;
    size_t g_only_full_source_tokens = 0;
    for (const auto & variant : variants) {
        const std::string id = variant.at("id");
        const auto g_tokens = tokenize_piece(
            vocab, variant.at("module_g").get<std::string>(), false, true);

        llama_memory_clear(memory, true);
        decode_tokens(ctx, prefix_tokens, 0, false, carrier_seq);
        decode_tokens(
            ctx, f_tokens,
            static_cast<llama_pos>(prefix_tokens.size()),
            false, carrier_seq);
        decode_tokens(
            ctx, g_tokens,
            static_cast<llama_pos>(f_boundary_tokens),
            false, carrier_seq);
        decode_tokens(
            ctx, closure_tokens,
            static_cast<llama_pos>(
                f_boundary_tokens + g_tokens.size()),
            false, carrier_seq);
        llama_synchronize(ctx);
        reference_full_source_tokens += expected_source_tokens;
        require_sequence_position(
            carrier_seq, source_boundary_pos,
            id + ":reference-source");
        query_from_anchor(
            carrier_seq,
            branch_seq,
            "isolated-full-replay-active-sequence-control",
            id + ":reference",
            variant.at("queries"),
            reference_results[id]);

        llama_memory_clear(memory, true);
        decode_tokens(ctx, prefix_tokens, 0, false, carrier_seq);
        decode_tokens(
            ctx, neutral_f_tokens,
            static_cast<llama_pos>(prefix_tokens.size()),
            false, carrier_seq);
        decode_tokens(
            ctx, g_tokens,
            static_cast<llama_pos>(f_boundary_tokens),
            false, carrier_seq);
        decode_tokens(
            ctx, closure_tokens,
            static_cast<llama_pos>(
                f_boundary_tokens + g_tokens.size()),
            false, carrier_seq);
        llama_synchronize(ctx);
        g_only_full_source_tokens += expected_source_tokens;
        require_sequence_position(
            carrier_seq, source_boundary_pos,
            id + ":G-only-source");
        query_from_anchor(
            carrier_seq,
            branch_seq,
            "isolated-G-only-active-sequence-control",
            id + ":G_only",
            variant.at("queries"),
            g_only_results[id]);
    }

    size_t variant_passes = 0;
    size_t full_logit_hash_matches = 0;
    size_t boundary_matches = 0;
    size_t comparisons = 0;
    double maximum_candidate_logit_absolute_difference = 0.0;
    json variant_summary = json::object();
    for (const auto & variant : variants) {
        const std::string id = variant.at("id");
        const auto & candidate = candidate_results.at(id);
        const auto & reference = reference_results.at(id);
        const auto & g_only = g_only_results.at(id);
        const size_t candidate_correct =
            semantic_correct_count(candidate, variant.at("queries"), false);
        const size_t reference_correct =
            semantic_correct_count(reference, variant.at("queries"), false);
        const size_t g_only_correct =
            semantic_correct_count(g_only, variant.at("queries"), false);
        size_t variant_hash_matches = 0;
        size_t variant_boundary_matches = 0;
        double variant_maximum_difference = 0.0;
        std::vector<std::string> candidate_answers;
        std::vector<std::string> reference_answers;
        std::vector<std::string> g_only_answers;
        for (size_t i = 0; i < candidate.size(); ++i) {
            candidate_answers.push_back(candidate.at(i).argmax);
            reference_answers.push_back(reference.at(i).argmax);
            g_only_answers.push_back(g_only.at(i).argmax);
            variant_hash_matches +=
                candidate.at(i).full_logits_fnv1a64 ==
                reference.at(i).full_logits_fnv1a64;
            variant_boundary_matches +=
                candidate.at(i).argmax == reference.at(i).argmax;
            for (size_t c = 0;
                 c < candidate.at(i).candidate_logits.size();
                 ++c) {
                variant_maximum_difference = std::max(
                    variant_maximum_difference,
                    std::abs(
                        static_cast<double>(
                            candidate.at(i).candidate_logits.at(c)) -
                        static_cast<double>(
                            reference.at(i).candidate_logits.at(c))));
            }
        }
        const bool passed =
            candidate_correct >=
                variant.at("joint_correct_minimum").get<size_t>() &&
            reference_correct >=
                variant.at("joint_correct_minimum").get<size_t>() &&
            g_only_correct <=
                variant.at("g_only_correct_maximum").get<size_t>() &&
            variant_hash_matches == candidate.size() &&
            variant_maximum_difference == 0.0;
        variant_passes += passed;
        full_logit_hash_matches += variant_hash_matches;
        boundary_matches += variant_boundary_matches;
        comparisons += candidate.size();
        maximum_candidate_logit_absolute_difference = std::max(
            maximum_candidate_logit_absolute_difference,
            variant_maximum_difference);
        variant_summary[id] = {
            {"candidate_answers", candidate_answers},
            {"reference_answers", reference_answers},
            {"G_only_answers", g_only_answers},
            {"candidate_correct", candidate_correct},
            {"reference_correct", reference_correct},
            {"G_only_correct", g_only_correct},
            {"full_logit_hash_matches", variant_hash_matches},
            {"boundary_matches", variant_boundary_matches},
            {"maximum_candidate_logit_absolute_difference",
                variant_maximum_difference},
            {"passed", passed},
        };
    }

    size_t repeat_full_logit_hash_matches = 0;
    size_t repeat_boundary_matches = 0;
    double repeat_maximum_candidate_logit_absolute_difference = 0.0;
    const auto & first_results = candidate_results.at(repeat_id);
    for (size_t i = 0; i < repeat_results.size(); ++i) {
        repeat_full_logit_hash_matches +=
            repeat_results.at(i).full_logits_fnv1a64 ==
            first_results.at(i).full_logits_fnv1a64;
        repeat_boundary_matches +=
            repeat_results.at(i).argmax == first_results.at(i).argmax;
        for (size_t c = 0;
             c < repeat_results.at(i).candidate_logits.size();
             ++c) {
            repeat_maximum_candidate_logit_absolute_difference = std::max(
                repeat_maximum_candidate_logit_absolute_difference,
                std::abs(
                    static_cast<double>(
                        repeat_results.at(i).candidate_logits.at(c)) -
                    static_cast<double>(
                        first_results.at(i).candidate_logits.at(c))));
        }
    }
    const size_t f_only_correct = semantic_correct_count(
        f_only_results, spec.at("f_only_queries"), false);

    llama_memory_clear(memory, true);
    llama_synchronize(ctx);
    require_sequence_position(carrier_seq, -1, "final-carrier-close");
    require_sequence_position(branch_seq, -1, "final-branch-close");
    require_sequence_position(query_seq, -1, "final-query-close");
    const bool no_retained_roots =
        llama_state_seq_get_device_root_count(ctx) == 0;
    const bool active_backings_stable =
        active_recurrent_backing_id(ctx) ==
            active_recurrent_backing_initial &&
        active_attention_backing_id(ctx) ==
            active_attention_backing_initial;

    const auto & acceptance = spec.at("acceptance_law");
    const bool accepted =
        variant_passes >=
            acceptance.at("variant_passes_minimum").get<size_t>() &&
        f_only_correct <=
            acceptance.at("f_only_correct_maximum").get<size_t>() &&
        comparisons == acceptance.at("comparisons").get<size_t>() &&
        full_logit_hash_matches ==
            acceptance.at("full_logit_hash_matches").get<size_t>() &&
        boundary_matches ==
            acceptance.at("boundary_matches").get<size_t>() &&
        maximum_candidate_logit_absolute_difference <=
            acceptance.at(
                "maximum_candidate_logit_absolute_difference").get<double>() &&
        repeat_full_logit_hash_matches ==
            acceptance.at(
                "repeat_full_logit_hash_matches").get<size_t>() &&
        repeat_boundary_matches ==
            acceptance.at("repeat_boundary_matches").get<size_t>() &&
        repeat_maximum_candidate_logit_absolute_difference <=
            acceptance.at(
                "repeat_maximum_candidate_logit_absolute_difference").get<double>() &&
        f_recurrent_content_exact &&
        f_recurrent_physical_row_stable &&
        no_retained_roots &&
        active_backings_stable;

    return {
        {"schema_version", 1},
        {"mechanism", "ACTIVE_F_SEQUENCE_COPY_ON_WRITE_BRANCHING"},
        {"spec_id", spec.at("id")},
        {"model_arch", "qwen35moe"},
        {"configuration", {
            {"context_size", actual_context_size},
            {"context_per_sequence", actual_context_per_sequence},
            {"n_seq_max", actual_n_seq_max},
            {"source_tokens", expected_source_tokens},
            {"prefix_tokens", prefix_tokens.size()},
            {"F_tokens", f_tokens.size()},
            {"G_tokens", neutral_g_tokens.size()},
            {"closure_tokens", closure_tokens.size()},
            {"carrier_sequence", carrier_seq},
            {"branch_sequence", branch_seq},
            {"query_sequence", query_seq},
            {"retained_device_roots_used", false},
            {"restoration_class", "DECLARED_CLOSURE"},
        }},
        {"summary", {
            {"variant_passes", variant_passes},
            {"variant_count", variants.size()},
            {"F_only_correct", f_only_correct},
            {"full_logit_hash_matches", full_logit_hash_matches},
            {"boundary_matches", boundary_matches},
            {"comparisons", comparisons},
            {"maximum_candidate_logit_absolute_difference",
                maximum_candidate_logit_absolute_difference},
            {"repeat_full_logit_hash_matches",
                repeat_full_logit_hash_matches},
            {"repeat_boundary_matches", repeat_boundary_matches},
            {"repeat_maximum_candidate_logit_absolute_difference",
                repeat_maximum_candidate_logit_absolute_difference},
            {"F_recurrent_content_exact", f_recurrent_content_exact},
            {"F_recurrent_physical_row_stable",
                f_recurrent_physical_row_stable},
            {"accepted", accepted},
        }},
        {"variant_summary", variant_summary},
        {"carrier", {
            {"active_cache_backend_allocation_bytes",
                active_cache_backend_allocation_bytes},
            {"maximum_retained_root_backend_allocation_bytes", 0},
            {"active_plus_retained_backend_allocation_bytes",
                active_cache_backend_allocation_bytes},
            {"active_recurrent_backing_id",
                hex64(active_recurrent_backing)},
            {"active_attention_backing_id",
                hex64(active_attention_backing)},
            {"F_recurrent_hash_before",
                hex64(f_recurrent_before.tensor.value)},
            {"F_recurrent_hash_after",
                hex64(f_recurrent_after.tensor.value)},
            {"F_recurrent_physical_row_before",
                f_recurrent_before.physical_row},
            {"F_recurrent_physical_row_after",
                f_recurrent_after.physical_row},
            {"F_position_before", f_recurrent_before.position},
            {"F_position_after", f_recurrent_after.position},
            {"complete_host_state_copy_retained", false},
            {"all_sequences_closed", true},
            {"all_retained_roots_closed", no_retained_roots},
            {"active_backings_stable", active_backings_stable},
        }},
        {"resource_accounting", {
            {"candidate_primary_source_decode_tokens",
                candidate_primary_source_tokens},
            {"candidate_suffix_decode_tokens",
                candidate_suffix_decode_tokens},
            {"repeat_sentinel_source_decode_tokens",
                repeat_sentinel_source_tokens},
            {"F_only_source_decode_tokens", f_only_source_tokens},
            {"reference_full_source_decode_tokens",
                reference_full_source_tokens},
            {"G_only_full_source_decode_tokens",
                g_only_full_source_tokens},
            {"all_route_source_decode_tokens",
                candidate_primary_source_tokens +
                repeat_sentinel_source_tokens +
                f_only_source_tokens +
                reference_full_source_tokens +
                g_only_full_source_tokens},
            {"query_decode_tokens", query_decode_tokens},
            {"all_route_input_tokens",
                candidate_primary_source_tokens +
                repeat_sentinel_source_tokens +
                f_only_source_tokens +
                reference_full_source_tokens +
                g_only_full_source_tokens +
                query_decode_tokens},
            {"sequence_copy_count", sequence_copy_count},
            {"sequence_close_count", sequence_close_count},
            {"snapshot_root_save_device_copy_bytes", 0},
            {"snapshot_root_restore_device_copy_bytes", 0},
            {"F_hash_d2h_bytes",
                f_recurrent_before.tensor.transferred_bytes +
                f_recurrent_after.tensor.transferred_bytes},
            {"F_hash_peak_host_work_bytes", std::max(
                f_recurrent_before.tensor.peak_host_work_bytes,
                f_recurrent_after.tensor.peak_host_work_bytes)},
        }},
        {"records", records},
        {"verdict", accepted ? "accept" : "reject"},
        {"claim_ceiling", spec.at("claim_ceiling")},
    };
}

static json run_g_forward_state_partition(
        llama_context * ctx,
        const llama_vocab * vocab,
        const std::vector<llama_token> & candidates,
        const json & spec,
        uint64_t active_recurrent_backing_initial,
        uint64_t active_attention_backing_initial) {
    const uint32_t actual_context_size = llama_n_ctx(ctx);
    const uint32_t actual_n_seq_max = llama_n_seq_max(ctx);
    const uint32_t actual_context_per_sequence =
        actual_context_size / actual_n_seq_max;
    if (actual_context_size !=
            spec.at("expected_context_size").get<uint32_t>() ||
        actual_n_seq_max !=
            spec.at("expected_n_seq_max").get<uint32_t>() ||
        actual_context_per_sequence !=
            spec.at("expected_context_per_sequence").get<uint32_t>()) {
        throw std::runtime_error(
            "G-forward partition context geometry mismatch");
    }

    const size_t expected_source_tokens =
        spec.at("expected_source_tokens").get<size_t>();
    const bool closure_scaffold_advance =
        spec.value("closure_scaffold_advance", false);
    const auto prefix_tokens = tokenize_piece(
        vocab, spec.at("prefix").get<std::string>(), true, true);
    const auto f_tokens = tokenize_piece(
        vocab, spec.at("module_f").get<std::string>(), false, true);
    const auto neutral_f_tokens = tokenize_piece(
        vocab, spec.at("neutral_module_f").get<std::string>(), false, true);
    const auto neutral_g_tokens = tokenize_piece(
        vocab, spec.at("neutral_module_g").get<std::string>(), false, true);
    const auto closure_tokens = tokenize_piece(
        vocab, spec.at("closure").get<std::string>(), false, true);
    const size_t f_boundary_tokens =
        prefix_tokens.size() + f_tokens.size();
    if (prefix_tokens.size() !=
            spec.at("expected_prefix_tokens").get<size_t>() ||
        f_tokens.size() != spec.at("expected_f_tokens").get<size_t>() ||
        neutral_f_tokens.size() != f_tokens.size() ||
        neutral_g_tokens.size() !=
            spec.at("expected_g_tokens").get<size_t>() ||
        closure_tokens.size() !=
            spec.at("expected_closure_tokens").get<size_t>() ||
        f_boundary_tokens + neutral_g_tokens.size() +
            closure_tokens.size() != expected_source_tokens) {
        throw std::runtime_error(
            "G-forward partition token geometry mismatch");
    }

    const auto & variants = spec.at("g_variants");
    if (!variants.is_array() || variants.empty()) {
        throw std::runtime_error(
            "G-forward partition has no G variants");
    }
    for (const auto & variant : variants) {
        const auto g_tokens = tokenize_piece(
            vocab, variant.at("module_g").get<std::string>(), false, true);
        if (g_tokens.size() != neutral_g_tokens.size() ||
            variant.at("queries").size() !=
                spec.at("queries_per_variant").get<size_t>()) {
            throw std::runtime_error(
                "G-forward partition variant geometry mismatch");
        }
    }

    auto * hybrid = require_hybrid_memory(ctx);
    auto * attention = hybrid->get_mem_attn();
    auto * recurrent = hybrid->get_mem_recr();
    const uint32_t attention_stream_count =
        attention->get_n_stream();
    if (attention_stream_count !=
        spec.at("expected_attention_stream_count").get<uint32_t>()) {
        throw std::runtime_error(
            "G-forward partition attention stream mismatch: " +
            std::to_string(attention_stream_count));
    }
    llama_memory_t memory = llama_get_memory(ctx);
    const llama_seq_id f_seq = 0;
    const llama_seq_id neutral_seq = 1;
    const llama_seq_id exact_g_seq = 2;
    const llama_seq_id scratch_seq = 3;
    const llama_pos f_boundary_pos =
        static_cast<llama_pos>(f_boundary_tokens - 1);
    const llama_pos source_boundary_pos =
        static_cast<llama_pos>(expected_source_tokens - 1);

    const auto require_component_positions =
            [&](llama_seq_id seq_id,
                llama_pos expected_attention,
                llama_pos expected_recurrent,
                const std::string & stage) {
        const llama_pos attention_pos =
            attention->seq_pos_max(seq_id);
        const llama_pos recurrent_pos =
            recurrent->seq_pos_max(seq_id);
        if (attention_pos != expected_attention ||
            recurrent_pos != expected_recurrent) {
            throw std::runtime_error(
                stage + " sequence " + std::to_string(seq_id) +
                " positions attention=" +
                std::to_string(attention_pos) + " recurrent=" +
                std::to_string(recurrent_pos));
        }
    };
    const auto close_sequence =
            [&](llama_seq_id seq_id, const std::string & stage) {
        if (!llama_memory_seq_rm(memory, seq_id, -1, -1)) {
            throw std::runtime_error(stage + " sequence close failed");
        }
        llama_synchronize(ctx);
        require_component_positions(seq_id, -1, -1, stage + ":closed");
    };
    const auto copy_full_sequence =
            [&](llama_seq_id src,
                llama_seq_id dst,
                llama_pos expected,
                const std::string & stage) {
        require_component_positions(dst, -1, -1, stage + ":empty");
        llama_memory_seq_cp(memory, src, dst, -1, -1);
        llama_synchronize(ctx);
        require_component_positions(
            dst, expected, expected, stage + ":copied");
    };
    const auto timed_decode =
            [&](const std::vector<llama_token> & tokens,
                llama_pos start_pos,
                llama_seq_id seq_id) {
        const auto started = std::chrono::steady_clock::now();
        decode_tokens(ctx, tokens, start_pos, false, seq_id);
        llama_synchronize(ctx);
        return std::chrono::duration<double, std::milli>(
            std::chrono::steady_clock::now() - started).count();
    };

    llama_memory_clear(memory, true);
    const double f_prefix_wall_ms =
        timed_decode(prefix_tokens, 0, f_seq);
    const double f_module_wall_ms = timed_decode(
        f_tokens,
        static_cast<llama_pos>(prefix_tokens.size()),
        f_seq);
    require_component_positions(
        f_seq, f_boundary_pos, f_boundary_pos, "partition:F-created");

    const double neutral_prefix_wall_ms =
        timed_decode(prefix_tokens, 0, neutral_seq);
    const double neutral_f_wall_ms = timed_decode(
        neutral_f_tokens,
        static_cast<llama_pos>(prefix_tokens.size()),
        neutral_seq);
    const double neutral_g_wall_ms = timed_decode(
        neutral_g_tokens,
        static_cast<llama_pos>(f_boundary_tokens),
        neutral_seq);
    const double neutral_closure_wall_ms = timed_decode(
        closure_tokens,
        static_cast<llama_pos>(
            f_boundary_tokens + neutral_g_tokens.size()),
        neutral_seq);
    require_component_positions(
        neutral_seq,
        source_boundary_pos,
        source_boundary_pos,
        "partition:neutral-scaffold-created");
    require_component_positions(
        exact_g_seq, -1, -1, "partition:exact-empty");
    require_component_positions(
        scratch_seq, -1, -1, "partition:scratch-empty");
    if (llama_state_seq_get_device_root_count(ctx) != 0) {
        throw std::runtime_error(
            "G-forward partition unexpectedly has retained roots");
    }

    const auto f_hash_before =
        hash_recurrent_sequence_streamed(ctx, f_seq);
    const auto neutral_hash_before =
        hash_recurrent_sequence_streamed(ctx, neutral_seq);
    const size_t active_cache_backend_allocation_bytes =
        active_hybrid_backend_allocation_bytes(ctx);
    const auto attention_layer_ids = attention->get_layer_ids();
    const std::set<uint32_t> all_attention_layers(
        attention_layer_ids.begin(),
        attention_layer_ids.end());
    const size_t F_attention_logical_bytes =
        attention_source_bytes(
            attention, all_attention_layers, f_boundary_tokens);
    const size_t G_closure_attention_logical_bytes =
        attention_source_bytes(
            attention,
            all_attention_layers,
            neutral_g_tokens.size() + closure_tokens.size());
    const size_t G_attention_logical_bytes =
        attention_source_bytes(
            attention, all_attention_layers, neutral_g_tokens.size());
    const size_t closure_attention_logical_bytes =
        attention_source_bytes(
            attention, all_attention_layers, closure_tokens.size());
    const size_t complete_attention_logical_bytes =
        F_attention_logical_bytes +
        G_closure_attention_logical_bytes;

    const std::vector<std::string> routes =
        closure_scaffold_advance
        ? std::vector<std::string>{
            "exact_full_state",
            "exact_G_attention_plus_scaffold_closure",
        }
        : std::vector<std::string>{
            "exact_full_state",
            "exact_attention_tail_on_F_recurrent",
            "exact_attention_tail_on_neutral_recurrent",
            "exact_recurrent_on_F_attention",
        };
    std::map<
        std::string,
        std::map<std::string, std::vector<boundary_result>>> outputs;
    json records = json::array();
    json forward_timings = json::array();
    size_t sequence_copy_count = 0;
    size_t component_copy_count = 0;
    size_t sequence_close_count = 0;
    size_t query_decode_tokens = 0;

    const auto project_and_close =
            [&](const std::string & route,
                const std::string & variant_id,
                const json & query) {
        auto boundary = decode_query(
            ctx,
            vocab,
            candidates,
            "G-forward-state-partition:" + route,
            variant_id,
            query,
            expected_source_tokens,
            active_recurrent_backing_initial,
            active_cache_backend_allocation_bytes,
            scratch_seq);
        query_decode_tokens +=
            boundary.record.at("query_tokens").get<size_t>();
        records.push_back(boundary.record);
        outputs[route][variant_id].push_back(std::move(boundary));
        close_sequence(scratch_seq, route + ":projection-close");
        ++sequence_close_count;
    };

    for (const auto & variant : variants) {
        const std::string id = variant.at("id");
        const auto g_tokens = tokenize_piece(
            vocab, variant.at("module_g").get<std::string>(), false, true);
        copy_full_sequence(
            f_seq, exact_g_seq, f_boundary_pos,
            id + ":exact-G-branch");
        ++sequence_copy_count;
        const double g_wall_ms = timed_decode(
            g_tokens,
            static_cast<llama_pos>(f_boundary_tokens),
            exact_g_seq);
        const llama_pos g_boundary_pos = static_cast<llama_pos>(
            f_boundary_tokens + g_tokens.size() - 1);
        require_component_positions(
            exact_g_seq,
            g_boundary_pos,
            g_boundary_pos,
            id + ":exact-G-module-complete");

        if (closure_scaffold_advance) {
            for (const auto & query : variant.at("queries")) {
                copy_full_sequence(
                    f_seq,
                    scratch_seq,
                    f_boundary_pos,
                    id + ":closure-reuse-F-base");
                ++sequence_copy_count;
                attention->seq_cp(
                    exact_g_seq,
                    scratch_seq,
                    static_cast<llama_pos>(f_boundary_tokens),
                    static_cast<llama_pos>(
                        f_boundary_tokens + g_tokens.size()));
                attention->seq_cp(
                    neutral_seq,
                    scratch_seq,
                    static_cast<llama_pos>(
                        f_boundary_tokens + g_tokens.size()),
                    static_cast<llama_pos>(expected_source_tokens));
                recurrent->seq_cp(
                    neutral_seq, scratch_seq, -1, -1);
                llama_synchronize(ctx);
                component_copy_count += 3;
                require_component_positions(
                    scratch_seq,
                    source_boundary_pos,
                    source_boundary_pos,
                    id + ":exact-G-with-scaffold-closure");
                project_and_close(
                    "exact_G_attention_plus_scaffold_closure",
                    id,
                    query);
            }
        }

        const double closure_wall_ms = timed_decode(
            closure_tokens,
            static_cast<llama_pos>(
                f_boundary_tokens + g_tokens.size()),
            exact_g_seq);
        require_component_positions(
            exact_g_seq,
            source_boundary_pos,
            source_boundary_pos,
            id + ":exact-G-complete");
        forward_timings.push_back({
            {"variant", id},
            {"G_tokens", g_tokens.size()},
            {"G_wall_ms", g_wall_ms},
            {"closure_tokens", closure_tokens.size()},
            {"closure_wall_ms", closure_wall_ms},
        });

        if (closure_scaffold_advance) {
            for (const auto & query : variant.at("queries")) {
                copy_full_sequence(
                    exact_g_seq,
                    scratch_seq,
                    source_boundary_pos,
                    id + ":exact-full-copy");
                ++sequence_copy_count;
                project_and_close("exact_full_state", id, query);
            }
        } else {
            for (const auto & query : variant.at("queries")) {
                copy_full_sequence(
                    exact_g_seq,
                    scratch_seq,
                    source_boundary_pos,
                    id + ":exact-full-copy");
                ++sequence_copy_count;
                project_and_close("exact_full_state", id, query);

                copy_full_sequence(
                    f_seq,
                    scratch_seq,
                    f_boundary_pos,
                    id + ":F-recurrent-base");
                ++sequence_copy_count;
                attention->seq_cp(
                    exact_g_seq,
                    scratch_seq,
                    static_cast<llama_pos>(f_boundary_tokens),
                    static_cast<llama_pos>(expected_source_tokens));
                llama_synchronize(ctx);
                ++component_copy_count;
                require_component_positions(
                    scratch_seq,
                    source_boundary_pos,
                    f_boundary_pos,
                    id + ":attention-tail-on-F-recurrent");
                project_and_close(
                    "exact_attention_tail_on_F_recurrent", id, query);

                copy_full_sequence(
                    f_seq,
                    scratch_seq,
                    f_boundary_pos,
                    id + ":neutral-recurrent-base");
                ++sequence_copy_count;
                attention->seq_cp(
                    exact_g_seq,
                    scratch_seq,
                    static_cast<llama_pos>(f_boundary_tokens),
                    static_cast<llama_pos>(expected_source_tokens));
                recurrent->seq_cp(
                    neutral_seq, scratch_seq, -1, -1);
                llama_synchronize(ctx);
                component_copy_count += 2;
                require_component_positions(
                    scratch_seq,
                    source_boundary_pos,
                    source_boundary_pos,
                    id + ":attention-tail-on-neutral-recurrent");
                project_and_close(
                    "exact_attention_tail_on_neutral_recurrent", id, query);

                copy_full_sequence(
                    f_seq,
                    scratch_seq,
                    f_boundary_pos,
                    id + ":exact-recurrent-base");
                ++sequence_copy_count;
                recurrent->seq_cp(
                    exact_g_seq, scratch_seq, -1, -1);
                llama_synchronize(ctx);
                ++component_copy_count;
                require_component_positions(
                    scratch_seq,
                    f_boundary_pos,
                    source_boundary_pos,
                    id + ":exact-recurrent-on-F-attention");
                project_and_close(
                    "exact_recurrent_on_F_attention", id, query);
            }
        }

        close_sequence(exact_g_seq, id + ":exact-G-close");
        ++sequence_close_count;
        require_component_positions(
            f_seq, f_boundary_pos, f_boundary_pos,
            id + ":F-survives");
        require_component_positions(
            neutral_seq, source_boundary_pos, source_boundary_pos,
            id + ":neutral-survives");
    }

    const auto f_hash_after =
        hash_recurrent_sequence_streamed(ctx, f_seq);
    const auto neutral_hash_after =
        hash_recurrent_sequence_streamed(ctx, neutral_seq);
    const bool f_exact =
        f_hash_before.tensor.value == f_hash_after.tensor.value &&
        f_hash_before.physical_row == f_hash_after.physical_row &&
        f_hash_before.position == f_hash_after.position;
    const bool neutral_exact =
        neutral_hash_before.tensor.value ==
            neutral_hash_after.tensor.value &&
        neutral_hash_before.physical_row ==
            neutral_hash_after.physical_row &&
        neutral_hash_before.position ==
            neutral_hash_after.position;

    json route_summary = json::object();
    const size_t comparisons =
        variants.size() *
        spec.at("queries_per_variant").get<size_t>();
    for (const auto & route : routes) {
        size_t correct = 0;
        size_t full_logit_hash_matches = 0;
        size_t boundary_matches = 0;
        double maximum_candidate_logit_absolute_difference = 0.0;
        for (const auto & variant : variants) {
            const std::string id = variant.at("id");
            const auto & route_outputs = outputs.at(route).at(id);
            const auto & reference =
                outputs.at("exact_full_state").at(id);
            correct += semantic_correct_count(
                route_outputs, variant.at("queries"), false);
            for (size_t i = 0; i < route_outputs.size(); ++i) {
                full_logit_hash_matches +=
                    route_outputs.at(i).full_logits_fnv1a64 ==
                    reference.at(i).full_logits_fnv1a64;
                boundary_matches +=
                    route_outputs.at(i).argmax ==
                    reference.at(i).argmax;
                for (size_t c = 0;
                     c < route_outputs.at(i).candidate_logits.size();
                     ++c) {
                    maximum_candidate_logit_absolute_difference = std::max(
                        maximum_candidate_logit_absolute_difference,
                        std::abs(
                            static_cast<double>(
                                route_outputs.at(i).candidate_logits.at(c)) -
                            static_cast<double>(
                                reference.at(i).candidate_logits.at(c))));
                }
            }
        }
        route_summary[route] = {
            {"correct", correct},
            {"comparisons", comparisons},
            {"full_logit_hash_matches", full_logit_hash_matches},
            {"boundary_matches", boundary_matches},
            {"maximum_candidate_logit_absolute_difference",
                maximum_candidate_logit_absolute_difference},
        };
    }

    double G_wall_ms_total = 0.0;
    double closure_wall_ms_total = 0.0;
    for (const auto & timing : forward_timings) {
        G_wall_ms_total += timing.at("G_wall_ms").get<double>();
        closure_wall_ms_total +=
            timing.at("closure_wall_ms").get<double>();
    }
    const auto & acceptance = spec.at("acceptance_law");
    const std::string primary_route = closure_scaffold_advance
        ? "exact_G_attention_plus_scaffold_closure"
        : "exact_attention_tail_on_neutral_recurrent";
    const auto & primary = route_summary.at(primary_route);
    bool accepted =
        primary.at("correct").get<size_t>() ==
            acceptance.at("primary_correct").get<size_t>() &&
        primary.at("boundary_matches").get<size_t>() ==
            acceptance.at("primary_boundary_matches").get<size_t>() &&
        f_exact &&
        neutral_exact;
    if (acceptance.contains("primary_full_logit_hash_matches")) {
        accepted =
            accepted &&
            primary.at("full_logit_hash_matches").get<size_t>() ==
                acceptance.at(
                    "primary_full_logit_hash_matches").get<size_t>();
    }
    if (acceptance.contains(
            "primary_maximum_candidate_logit_absolute_difference")) {
        accepted =
            accepted &&
            primary.at(
                "maximum_candidate_logit_absolute_difference").get<double>() <=
                acceptance.at(
                    "primary_maximum_candidate_logit_absolute_difference").get<double>();
    }

    close_sequence(f_seq, "partition:F-close");
    ++sequence_close_count;
    close_sequence(neutral_seq, "partition:neutral-close");
    ++sequence_close_count;
    llama_memory_clear(memory, true);
    llama_synchronize(ctx);
    const bool all_sequences_closed =
        attention->seq_pos_max(f_seq) == -1 &&
        attention->seq_pos_max(neutral_seq) == -1 &&
        attention->seq_pos_max(exact_g_seq) == -1 &&
        attention->seq_pos_max(scratch_seq) == -1 &&
        recurrent->seq_pos_max(f_seq) == -1 &&
        recurrent->seq_pos_max(neutral_seq) == -1 &&
        recurrent->seq_pos_max(exact_g_seq) == -1 &&
        recurrent->seq_pos_max(scratch_seq) == -1;
    const bool all_roots_closed =
        llama_state_seq_get_device_root_count(ctx) == 0;
    const bool active_backings_stable =
        active_recurrent_backing_id(ctx) ==
            active_recurrent_backing_initial &&
        active_attention_backing_id(ctx) ==
            active_attention_backing_initial;
    if (!all_sequences_closed ||
        !all_roots_closed ||
        !active_backings_stable) {
        throw std::runtime_error(
            "G-forward partition close invariant failed");
    }

    const size_t fixed_carrier_preparation_tokens =
        f_boundary_tokens + expected_source_tokens;
    const size_t candidate_variable_source_tokens =
        variants.size() * neutral_g_tokens.size();
    const size_t candidate_source_tokens =
        fixed_carrier_preparation_tokens +
        (closure_scaffold_advance
            ? candidate_variable_source_tokens
            : variants.size() *
                (neutral_g_tokens.size() + closure_tokens.size()));
    const size_t reference_closure_tokens =
        variants.size() * closure_tokens.size();
    const size_t source_decode_tokens =
        prefix_tokens.size() + f_tokens.size() +
        prefix_tokens.size() + neutral_f_tokens.size() +
        neutral_g_tokens.size() + closure_tokens.size() +
        variants.size() *
            (neutral_g_tokens.size() + closure_tokens.size());
    return {
        {"schema_version", 1},
        {"mechanism", closure_scaffold_advance
            ? "ACTIVE_G_CLOSURE_SCAFFOLD_ADVANCE"
            : "ACTIVE_G_FORWARD_STATE_PARTITION"},
        {"spec_id", spec.at("id")},
        {"model_arch", "qwen35moe"},
        {"configuration", {
            {"context_size", actual_context_size},
            {"context_per_sequence", actual_context_per_sequence},
            {"n_seq_max", actual_n_seq_max},
            {"source_tokens", expected_source_tokens},
            {"F_boundary_tokens", f_boundary_tokens},
            {"G_tokens", neutral_g_tokens.size()},
            {"closure_tokens", closure_tokens.size()},
            {"G_closure_tokens",
                neutral_g_tokens.size() + closure_tokens.size()},
            {"closure_scaffold_advance", closure_scaffold_advance},
            {"retained_device_roots_used", false},
            {"attention_stream_count", attention_stream_count},
            {"partial_attention_sequence_copy_metadata_only",
                attention_stream_count == 1},
            {"restoration_class", "DECLARED_CLOSURE"},
        }},
        {"summary", {
            {"route_summary", route_summary},
            {"F_recurrent_content_and_row_exact", f_exact},
            {"neutral_recurrent_content_and_row_exact", neutral_exact},
            {"primary_route", primary_route},
            {"accepted", accepted},
        }},
        {"carrier", {
            {"active_cache_backend_allocation_bytes",
                active_cache_backend_allocation_bytes},
            {"maximum_retained_root_backend_allocation_bytes", 0},
            {"active_plus_retained_backend_allocation_bytes",
                active_cache_backend_allocation_bytes},
            {"F_recurrent_hash_before",
                hex64(f_hash_before.tensor.value)},
            {"F_recurrent_hash_after",
                hex64(f_hash_after.tensor.value)},
            {"F_recurrent_physical_row",
                f_hash_before.physical_row},
            {"neutral_recurrent_hash_before",
                hex64(neutral_hash_before.tensor.value)},
            {"neutral_recurrent_hash_after",
                hex64(neutral_hash_after.tensor.value)},
            {"neutral_recurrent_physical_row",
                neutral_hash_before.physical_row},
            {"F_attention_logical_bytes",
                F_attention_logical_bytes},
            {"G_closure_attention_logical_bytes",
                G_closure_attention_logical_bytes},
            {"G_attention_logical_bytes",
                G_attention_logical_bytes},
            {"closure_attention_logical_bytes",
                closure_attention_logical_bytes},
            {"complete_attention_logical_bytes",
                complete_attention_logical_bytes},
            {"complete_host_state_copy_retained", false},
            {"all_sequences_closed", all_sequences_closed},
            {"all_retained_roots_closed", all_roots_closed},
            {"active_backings_stable", active_backings_stable},
        }},
        {"forward_timings", forward_timings},
        {"resource_accounting", {
            {"F_prefix_wall_ms", f_prefix_wall_ms},
            {"F_module_wall_ms", f_module_wall_ms},
            {"neutral_prefix_wall_ms", neutral_prefix_wall_ms},
            {"neutral_F_wall_ms", neutral_f_wall_ms},
            {"neutral_G_wall_ms", neutral_g_wall_ms},
            {"neutral_closure_wall_ms",
                neutral_closure_wall_ms},
            {"exact_G_wall_ms_total", G_wall_ms_total},
            {"exact_closure_wall_ms_total",
                closure_wall_ms_total},
            {"source_decode_tokens", source_decode_tokens},
            {"fixed_carrier_preparation_tokens",
                fixed_carrier_preparation_tokens},
            {"candidate_variable_source_tokens",
                candidate_variable_source_tokens},
            {"candidate_source_tokens",
                candidate_source_tokens},
            {"reference_closure_tokens",
                reference_closure_tokens},
            {"predecessor_active_F_candidate_source_tokens",
                f_boundary_tokens +
                variants.size() *
                    (neutral_g_tokens.size() + closure_tokens.size())},
            {"crossover_branch_count",
                (expected_source_tokens + closure_tokens.size() - 1) /
                    closure_tokens.size()},
            {"asymptotic_candidate_source_ratio",
                static_cast<double>(neutral_g_tokens.size()) /
                    static_cast<double>(expected_source_tokens)},
            {"query_decode_tokens", query_decode_tokens},
            {"all_route_input_tokens",
                source_decode_tokens + query_decode_tokens},
            {"sequence_copy_count", sequence_copy_count},
            {"component_copy_count", component_copy_count},
            {"sequence_close_count", sequence_close_count},
            {"snapshot_root_save_device_copy_bytes", 0},
            {"snapshot_root_restore_device_copy_bytes", 0},
            {"carrier_hash_d2h_bytes",
                f_hash_before.tensor.transferred_bytes +
                f_hash_after.tensor.transferred_bytes +
                neutral_hash_before.tensor.transferred_bytes +
                neutral_hash_after.tensor.transferred_bytes},
            {"carrier_hash_peak_host_work_bytes", std::max({
                f_hash_before.tensor.peak_host_work_bytes,
                f_hash_after.tensor.peak_host_work_bytes,
                neutral_hash_before.tensor.peak_host_work_bytes,
                neutral_hash_after.tensor.peak_host_work_bytes,
            })},
        }},
        {"records", records},
        {"verdict", accepted ? "accept" : "reject"},
        {"claim_ceiling", spec.at("claim_ceiling")},
    };
}

static json run_sparse_g_label_refresh(
        llama_context * ctx,
        const llama_vocab * vocab,
        const std::vector<llama_token> & candidates,
        const json & spec,
        uint64_t active_recurrent_backing_initial,
        uint64_t active_attention_backing_initial,
        llama_kv_cache::value_subspace_operator *
            shared_subspace_operator = nullptr,
        bool build_subspace_operator = true) {
    const bool position_orbit_mode =
        spec.value("label_orbit_attention_action", false);
    const bool value_orbit_mode =
        spec.value("value_orbit_attention_action", false);
    const bool key_value_orbit_mode =
        spec.value("key_value_orbit_attention_action", false);
    const bool complex_phase_orbit_mode =
        spec.value("complex_phase_quarter_turn_action", false);
    const bool fourier_value_orbit_mode =
        spec.value("fourier_value_orbit_action", false);
    const bool subspace_value_orbit_mode =
        spec.value("subspace_value_orbit_action", false);
    const bool subspace_include_keys =
        spec.value("subspace_include_keys", false);
    if (subspace_include_keys &&
        !subspace_value_orbit_mode) {
        throw std::runtime_error(
            "subspace key action requires subspace value action");
    }
    const bool orbit_mode =
        position_orbit_mode ||
        value_orbit_mode ||
        key_value_orbit_mode ||
        complex_phase_orbit_mode ||
        fourier_value_orbit_mode ||
        subspace_value_orbit_mode;
    if (static_cast<int>(position_orbit_mode) +
            static_cast<int>(value_orbit_mode) +
            static_cast<int>(key_value_orbit_mode) +
            static_cast<int>(complex_phase_orbit_mode) +
            static_cast<int>(fourier_value_orbit_mode) +
            static_cast<int>(subspace_value_orbit_mode) > 1) {
        throw std::runtime_error(
            "label orbit action modes are mutually exclusive");
    }
    const uint32_t actual_context_size = llama_n_ctx(ctx);
    const uint32_t actual_n_seq_max = llama_n_seq_max(ctx);
    const uint32_t actual_context_per_sequence =
        actual_context_size / actual_n_seq_max;
    if (actual_context_size !=
            spec.at("expected_context_size").get<uint32_t>() ||
        actual_n_seq_max !=
            spec.at("expected_n_seq_max").get<uint32_t>() ||
        actual_context_per_sequence !=
            spec.at("expected_context_per_sequence").get<uint32_t>()) {
        throw std::runtime_error(
            "sparse G refresh context geometry mismatch");
    }

    const auto prefix_tokens = tokenize_piece(
        vocab, spec.at("prefix").get<std::string>(), true, true);
    const auto f_tokens = tokenize_piece(
        vocab, spec.at("module_f").get<std::string>(), false, true);
    const auto structural_g_tokens = tokenize_piece(
        vocab,
        spec.at("structural_module_g").get<std::string>(),
        false,
        true);
    const auto closure_tokens = tokenize_piece(
        vocab, spec.at("closure").get<std::string>(), false, true);
    const size_t expected_source_tokens =
        spec.at("expected_source_tokens").get<size_t>();
    const size_t f_boundary_tokens =
        prefix_tokens.size() + f_tokens.size();
    const auto label_offsets =
        spec.at("label_token_offsets").get<std::vector<size_t>>();
    if (prefix_tokens.size() !=
            spec.at("expected_prefix_tokens").get<size_t>() ||
        f_tokens.size() != spec.at("expected_f_tokens").get<size_t>() ||
        structural_g_tokens.size() !=
            spec.at("expected_g_tokens").get<size_t>() ||
        closure_tokens.size() !=
            spec.at("expected_closure_tokens").get<size_t>() ||
        f_boundary_tokens + structural_g_tokens.size() +
            closure_tokens.size() != expected_source_tokens ||
        label_offsets.size() != 4 ||
        !std::is_sorted(label_offsets.begin(), label_offsets.end()) ||
        label_offsets.back() >= structural_g_tokens.size()) {
        throw std::runtime_error(
            "sparse G refresh token geometry mismatch");
    }

    const auto & variants = spec.at("g_variants");
    if (!variants.is_array() || variants.empty()) {
        throw std::runtime_error(
            "sparse G refresh has no G variants");
    }
    if (orbit_mode && variants.size() != 4) {
        throw std::runtime_error(
            "label orbit requires the frozen four-element cycle");
    }
    std::vector<std::vector<llama_token>> variant_g_tokens;
    for (const auto & variant : variants) {
        auto tokens = tokenize_piece(
            vocab, variant.at("module_g").get<std::string>(), false, true);
        if (tokens.size() != structural_g_tokens.size() ||
            variant.at("queries").size() !=
                spec.at("queries_per_variant").get<size_t>()) {
            throw std::runtime_error(
                "sparse G refresh variant geometry mismatch");
        }
        for (size_t i = 0; i < tokens.size(); ++i) {
            const bool is_label =
                std::find(
                    label_offsets.begin(), label_offsets.end(), i) !=
                label_offsets.end();
            if (!is_label && tokens[i] != structural_g_tokens[i]) {
                throw std::runtime_error(
                    "sparse G refresh found non-label token difference");
            }
            if (is_label && tokens[i] == structural_g_tokens[i]) {
                throw std::runtime_error(
                    "sparse G refresh label equals structural placeholder");
            }
        }
        variant_g_tokens.push_back(std::move(tokens));
    }
    std::vector<std::vector<uint32_t>> fourier_label_ordinals;
    if (fourier_value_orbit_mode ||
        subspace_value_orbit_mode) {
        fourier_label_ordinals =
            spec.at("fourier_label_ordinals")
                .get<std::vector<std::vector<uint32_t>>>();
        if (fourier_label_ordinals.size() != variants.size()) {
            throw std::runtime_error(
                "Fourier label ordinal variant count mismatch");
        }
        for (const auto & row : fourier_label_ordinals) {
            if (row.size() != label_offsets.size()) {
                throw std::runtime_error(
                    "Fourier label ordinal position count mismatch");
            }
            for (const uint32_t ordinal : row) {
                if (ordinal >= 4) {
                    throw std::runtime_error(
                        "Fourier label ordinal out of range");
                }
            }
        }
        for (size_t position = 0;
             position < label_offsets.size();
             ++position) {
            std::set<uint32_t> column;
            for (size_t variant = 0;
                 variant < variants.size();
                 ++variant) {
                column.insert(
                    fourier_label_ordinals[variant][position]);
                if (variant > 0 &&
                    fourier_label_ordinals[variant][position] !=
                        (fourier_label_ordinals[variant - 1][position] + 1) %
                            4) {
                    throw std::runtime_error(
                        "Fourier label variants are not one public Z4 step");
                }
            }
            if (column.size() != 4) {
                throw std::runtime_error(
                    "Fourier label ordinal column is not a permutation");
            }
        }
    }

    auto * hybrid = require_hybrid_memory(ctx);
    auto * attention = hybrid->get_mem_attn();
    auto * recurrent = hybrid->get_mem_recr();
    const uint32_t attention_stream_count =
        attention->get_n_stream();
    if (attention_stream_count !=
        spec.at("expected_attention_stream_count").get<uint32_t>()) {
        throw std::runtime_error(
            "sparse G refresh attention stream mismatch");
    }
    llama_memory_t memory = llama_get_memory(ctx);
    const llama_seq_id f_seq = 0;
    const std::vector<llama_seq_id> stage_seqs = {1, 2, 3, 4};
    const llama_seq_id scaffold_seq = 5;
    const llama_seq_id work_seq = 6;
    const llama_seq_id candidate_seq = 7;
    const llama_pos f_boundary_pos =
        static_cast<llama_pos>(f_boundary_tokens - 1);
    const llama_pos source_boundary_pos =
        static_cast<llama_pos>(expected_source_tokens - 1);

    const auto require_component_positions =
            [&](llama_seq_id seq_id,
                llama_pos expected_attention,
                llama_pos expected_recurrent,
                const std::string & stage) {
        const llama_pos attention_pos =
            attention->seq_pos_max(seq_id);
        const llama_pos recurrent_pos =
            recurrent->seq_pos_max(seq_id);
        if (attention_pos != expected_attention ||
            recurrent_pos != expected_recurrent) {
            throw std::runtime_error(
                stage + " sequence " + std::to_string(seq_id) +
                " positions attention=" +
                std::to_string(attention_pos) + " recurrent=" +
                std::to_string(recurrent_pos));
        }
    };
    const auto close_sequence =
            [&](llama_seq_id seq_id, const std::string & stage) {
        if (!llama_memory_seq_rm(memory, seq_id, -1, -1)) {
            throw std::runtime_error(stage + " sequence close failed");
        }
        llama_synchronize(ctx);
        require_component_positions(
            seq_id, -1, -1, stage + ":closed");
    };
    const auto copy_full_sequence =
            [&](llama_seq_id src,
                llama_seq_id dst,
                llama_pos expected,
                const std::string & stage) {
        require_component_positions(dst, -1, -1, stage + ":empty");
        llama_memory_seq_cp(memory, src, dst, -1, -1);
        llama_synchronize(ctx);
        require_component_positions(
            dst, expected, expected, stage + ":copied");
    };
    const auto token_slice =
            [](const std::vector<llama_token> & tokens,
               size_t begin,
               size_t end) {
        return std::vector<llama_token>(
            tokens.begin() + static_cast<std::ptrdiff_t>(begin),
            tokens.begin() + static_cast<std::ptrdiff_t>(end));
    };
    const auto timed_decode =
            [&](const std::vector<llama_token> & tokens,
                llama_pos start_pos,
                llama_seq_id seq_id) {
        const auto started = std::chrono::steady_clock::now();
        decode_tokens(ctx, tokens, start_pos, false, seq_id);
        llama_synchronize(ctx);
        return std::chrono::duration<double, std::milli>(
            std::chrono::steady_clock::now() - started).count();
    };

    llama_memory_clear(memory, true);
    const double f_prefix_wall_ms =
        timed_decode(prefix_tokens, 0, f_seq);
    const double f_module_wall_ms = timed_decode(
        f_tokens,
        static_cast<llama_pos>(prefix_tokens.size()),
        f_seq);
    require_component_positions(
        f_seq, f_boundary_pos, f_boundary_pos, "sparse:F-created");

    size_t sequence_copy_count = 0;
    size_t sequence_close_count = 0;
    size_t label_refresh_count = 0;
    size_t attention_label_remove_count = 0;
    size_t attention_label_alias_count = 0;
    size_t orbit_action_count = 0;
    size_t orbit_position_shift_count = 0;
    size_t fourier_calibration_sample_count = 0;
    size_t subspace_calibration_sample_count = 0;
    uint64_t orbit_backend_copy_bytes = 0;
    uint64_t orbit_host_read_bytes = 0;
    uint64_t orbit_host_write_bytes = 0;
    uint64_t orbit_peak_host_work_bytes = 0;
    uint64_t orbit_tensor_visits = 0;
    uint64_t orbit_position_visits = 0;
    uint64_t fourier_operator_logical_bytes = 0;
    uint64_t fourier_operator_vector_backing_bytes = 0;
    uint64_t subspace_builder_peak_bytes = 0;
    uint64_t subspace_operator_logical_bytes = 0;
    uint64_t subspace_operator_vector_backing_bytes = 0;
    uint64_t subspace_operator_total_rank = 0;
    uint64_t subspace_operator_maximum_layer_rank = 0;
    double subspace_operator_calibration_max_abs_error = 0.0;
    double subspace_operator_closure_max_abs_error = 0.0;
    size_t query_decode_tokens = 0;
    double scaffold_G_wall_ms = 0.0;
    double scaffold_closure_wall_ms = 0.0;
    double label_refresh_wall_ms_total = 0.0;
    double fourier_calibration_wall_ms_total = 0.0;
    double subspace_calibration_wall_ms_total = 0.0;
    double reference_G_wall_ms_total = 0.0;
    double reference_closure_wall_ms_total = 0.0;

    copy_full_sequence(
        f_seq,
        stage_seqs[0],
        f_boundary_pos,
        "sparse:stage0-F-copy");
    ++sequence_copy_count;
    const auto before_first_label = token_slice(
        structural_g_tokens, 0, label_offsets[0]);
    scaffold_G_wall_ms += timed_decode(
        before_first_label,
        static_cast<llama_pos>(f_boundary_tokens),
        stage_seqs[0]);
    require_component_positions(
        stage_seqs[0],
        static_cast<llama_pos>(
            f_boundary_tokens + label_offsets[0] - 1),
        static_cast<llama_pos>(
            f_boundary_tokens + label_offsets[0] - 1),
        "sparse:stage0-ready");

    for (size_t i = 0; i + 1 < label_offsets.size(); ++i) {
        copy_full_sequence(
            stage_seqs[i],
            stage_seqs[i + 1],
            static_cast<llama_pos>(
                f_boundary_tokens + label_offsets[i] - 1),
            "sparse:stage-copy-" + std::to_string(i));
        ++sequence_copy_count;
        const auto segment = token_slice(
            structural_g_tokens,
            label_offsets[i],
            label_offsets[i + 1]);
        scaffold_G_wall_ms += timed_decode(
            segment,
            static_cast<llama_pos>(
                f_boundary_tokens + label_offsets[i]),
            stage_seqs[i + 1]);
        require_component_positions(
            stage_seqs[i + 1],
            static_cast<llama_pos>(
                f_boundary_tokens + label_offsets[i + 1] - 1),
            static_cast<llama_pos>(
                f_boundary_tokens + label_offsets[i + 1] - 1),
            "sparse:stage-ready-" + std::to_string(i + 1));
    }

    copy_full_sequence(
        stage_seqs.back(),
        scaffold_seq,
        static_cast<llama_pos>(
            f_boundary_tokens + label_offsets.back() - 1),
        "sparse:scaffold-copy");
    ++sequence_copy_count;
    const auto final_G_segment = token_slice(
        structural_g_tokens,
        label_offsets.back(),
        structural_g_tokens.size());
    scaffold_G_wall_ms += timed_decode(
        final_G_segment,
        static_cast<llama_pos>(
            f_boundary_tokens + label_offsets.back()),
        scaffold_seq);
    scaffold_closure_wall_ms = timed_decode(
        closure_tokens,
        static_cast<llama_pos>(
            f_boundary_tokens + structural_g_tokens.size()),
        scaffold_seq);
    require_component_positions(
        scaffold_seq,
        source_boundary_pos,
        source_boundary_pos,
        "sparse:scaffold-complete");
    require_component_positions(
        work_seq, -1, -1, "sparse:work-empty");
    require_component_positions(
        candidate_seq, -1, -1, "sparse:candidate-empty");
    if (llama_state_seq_get_device_root_count(ctx) != 0) {
        throw std::runtime_error(
            "sparse G refresh unexpectedly has retained roots");
    }

    const auto f_hash_before =
        hash_recurrent_sequence_streamed(ctx, f_seq);
    const auto scaffold_hash_before =
        hash_recurrent_sequence_streamed(ctx, scaffold_seq);
    streamed_sequence_hash carrier_recurrent_hash_before =
        scaffold_hash_before;
    const size_t active_cache_backend_allocation_bytes =
        active_hybrid_backend_allocation_bytes(ctx);
    const std::vector<uint32_t> attention_layer_ids =
        attention->get_layer_ids();
    const std::set<uint32_t> all_attention_layers(
        attention_layer_ids.begin(),
        attention_layer_ids.end());
    const std::set<uint32_t> orbit_attention_layers =
        (value_orbit_mode ||
         key_value_orbit_mode ||
         complex_phase_orbit_mode ||
         fourier_value_orbit_mode ||
         subspace_value_orbit_mode)
            ? spec.contains("orbit_attention_layers")
                ? parse_layer_selection(
                    spec, "orbit_attention_layers", attention_layer_ids)
                : all_attention_layers
            : all_attention_layers;
    const bool layer_selective_value_orbit =
        (value_orbit_mode ||
         fourier_value_orbit_mode ||
         subspace_value_orbit_mode) &&
        orbit_attention_layers != all_attention_layers;
    const size_t refreshed_attention_logical_bytes =
        attention_source_bytes(
            attention, all_attention_layers, label_offsets.size());
    const size_t scaffold_attention_logical_bytes =
        attention_source_bytes(
            attention,
            all_attention_layers,
            expected_source_tokens);

    std::map<
        std::string,
        std::map<std::string, std::vector<boundary_result>>> outputs;
    json records = json::array();
    json variant_timings = json::array();

    const auto project_from_source =
            [&](llama_seq_id source_seq,
                llama_seq_id scratch_seq,
                const std::string & route,
                const std::string & variant_id,
                const json & query) {
        copy_full_sequence(
            source_seq,
            scratch_seq,
            source_boundary_pos,
            route + ":query-copy");
        ++sequence_copy_count;
        auto boundary = decode_query(
            ctx,
            vocab,
            candidates,
            "sparse-G-label-refresh:" + route,
            variant_id,
            query,
            expected_source_tokens,
            active_recurrent_backing_initial,
            active_cache_backend_allocation_bytes,
            scratch_seq);
        query_decode_tokens +=
            boundary.record.at("query_tokens").get<size_t>();
        records.push_back(boundary.record);
        outputs[route][variant_id].push_back(std::move(boundary));
        close_sequence(scratch_seq, route + ":query-close");
        ++sequence_close_count;
    };

    const auto refresh_candidate_labels =
            [&](const std::vector<llama_token> & target_g_tokens,
                const std::string & id) {
        double variant_label_wall_ms = 0.0;
        for (size_t label_index = 0;
             label_index < label_offsets.size();
             ++label_index) {
            const size_t label_offset = label_offsets[label_index];
            const llama_pos label_pos = static_cast<llama_pos>(
                f_boundary_tokens + label_offset);
            copy_full_sequence(
                stage_seqs[label_index],
                work_seq,
                label_pos - 1,
                id + ":label-stage-" +
                    std::to_string(label_index));
            ++sequence_copy_count;
            const std::vector<llama_token> label_token = {
                target_g_tokens.at(label_offset),
            };
            const double label_wall_ms = timed_decode(
                label_token, label_pos, work_seq);
            variant_label_wall_ms += label_wall_ms;
            label_refresh_wall_ms_total += label_wall_ms;
            ++label_refresh_count;
            require_component_positions(
                work_seq,
                label_pos,
                label_pos,
                id + ":label-decoded-" +
                    std::to_string(label_index));
            if (!attention->seq_rm(
                    candidate_seq, label_pos, label_pos + 1)) {
                throw std::runtime_error(
                    id + " structural label removal failed");
            }
            ++attention_label_remove_count;
            attention->seq_cp(
                work_seq,
                candidate_seq,
                label_pos,
                label_pos + 1);
            llama_synchronize(ctx);
            ++attention_label_alias_count;
            require_component_positions(
                candidate_seq,
                source_boundary_pos,
                source_boundary_pos,
                id + ":label-patched-" +
                    std::to_string(label_index));
            close_sequence(
                work_seq,
                id + ":label-work-close-" +
                    std::to_string(label_index));
            ++sequence_close_count;
        }
        return variant_label_wall_ms;
    };

    llama_kv_cache::value_fourier_operator fourier_operator;
    std::vector<uint32_t> fourier_current_ordinals =
        fourier_value_orbit_mode
            ? fourier_label_ordinals.at(0)
            : std::vector<uint32_t>{};
    const auto calibrate_fourier_operator =
            [&](const std::string & id) {
        static constexpr std::array<
            std::array<float, 3>, 4> basis_coefficients = {{
            {{ 0.5f,  0.0f,  0.25f}},
            {{ 0.0f,  0.5f, -0.25f}},
            {{-0.5f,  0.0f,  0.25f}},
            {{ 0.0f, -0.5f, -0.25f}},
        }};
        const float position_average =
            1.0f / static_cast<float>(label_offsets.size());
        double wall_ms = 0.0;
        for (size_t position_index = 0;
             position_index < label_offsets.size();
             ++position_index) {
            const size_t label_offset =
                label_offsets[position_index];
            const llama_pos label_pos = static_cast<llama_pos>(
                f_boundary_tokens + label_offset);
            for (uint32_t ordinal = 0; ordinal < 4; ++ordinal) {
                size_t source_variant = variants.size();
                for (size_t variant_index = 0;
                     variant_index < variants.size();
                     ++variant_index) {
                    if (fourier_label_ordinals[variant_index]
                            [position_index] == ordinal) {
                        source_variant = variant_index;
                        break;
                    }
                }
                if (source_variant == variants.size()) {
                    throw std::runtime_error(
                        id + ": missing Fourier calibration label");
                }
                copy_full_sequence(
                    stage_seqs[position_index],
                    work_seq,
                    label_pos - 1,
                    id + ":stage-" +
                        std::to_string(position_index) +
                        ":ordinal-" + std::to_string(ordinal));
                ++sequence_copy_count;
                const std::vector<llama_token> label_token = {
                    variant_g_tokens[source_variant].at(label_offset),
                };
                const double label_wall_ms = timed_decode(
                    label_token, label_pos, work_seq);
                wall_ms += label_wall_ms;
                label_refresh_wall_ms_total += label_wall_ms;
                ++label_refresh_count;
                require_component_positions(
                    work_seq,
                    label_pos,
                    label_pos,
                    id + ":decoded-" +
                        std::to_string(position_index) +
                        "-" + std::to_string(ordinal));

                std::array<float, 3> coefficients = {};
                for (size_t component = 0;
                     component < coefficients.size();
                     ++component) {
                    coefficients[component] =
                        basis_coefficients[ordinal][component] *
                        position_average;
                }
                llama_kv_cache::value_fourier_metrics metrics = {};
                const auto calibration_started =
                    std::chrono::steady_clock::now();
                if (!attention->seq_accumulate_value_fourier_sample(
                        work_seq,
                        label_pos,
                        orbit_attention_layers,
                        coefficients,
                        &fourier_operator,
                        &metrics)) {
                    throw std::runtime_error(
                        id + ": Fourier calibration failed");
                }
                llama_synchronize(ctx);
                fourier_calibration_wall_ms_total +=
                    std::chrono::duration<double, std::milli>(
                        std::chrono::steady_clock::now() -
                        calibration_started).count();
                orbit_host_read_bytes += metrics.host_read_bytes;
                orbit_peak_host_work_bytes = std::max(
                    orbit_peak_host_work_bytes,
                    metrics.peak_host_work_bytes);
                orbit_tensor_visits += metrics.tensor_visits;
                orbit_position_visits += metrics.position_visits;
                fourier_operator_logical_bytes =
                    fourier_operator.logical_bytes;
                fourier_operator_vector_backing_bytes =
                    metrics.operator_bytes;
                ++fourier_calibration_sample_count;

                if (ordinal ==
                    fourier_label_ordinals.at(0)
                        .at(position_index)) {
                    if (!attention->seq_rm(
                            candidate_seq,
                            label_pos,
                            label_pos + 1)) {
                        throw std::runtime_error(
                            id +
                            ": canonical label removal failed");
                    }
                    ++attention_label_remove_count;
                    attention->seq_cp(
                        work_seq,
                        candidate_seq,
                        label_pos,
                        label_pos + 1);
                    llama_synchronize(ctx);
                    ++attention_label_alias_count;
                }
                close_sequence(
                    work_seq,
                    id + ":work-close-" +
                        std::to_string(position_index) +
                        "-" + std::to_string(ordinal));
                ++sequence_close_count;
            }
        }
        require_component_positions(
            candidate_seq,
            source_boundary_pos,
            source_boundary_pos,
            id + ":candidate-calibrated");
        if (fourier_operator.calibration_samples !=
                label_offsets.size() * 4 ||
            fourier_calibration_sample_count !=
                label_offsets.size() * 4 ||
            fourier_operator.layers.size() !=
                orbit_attention_layers.size()) {
            throw std::runtime_error(
                id + ": incomplete Fourier operator");
        }
        return wall_ms;
    };

    llama_kv_cache::value_subspace_builder subspace_builder;
    llama_kv_cache::value_subspace_operator
        local_subspace_operator;
    llama_kv_cache::value_subspace_operator *
        subspace_operator = shared_subspace_operator
            ? shared_subspace_operator
            : &local_subspace_operator;
    if (subspace_value_orbit_mode &&
        !build_subspace_operator &&
        !shared_subspace_operator) {
        throw std::runtime_error(
            "subspace reuse requires an imported operator");
    }
    const auto calibrate_subspace_operator =
            [&](const std::string & id) {
        if (!build_subspace_operator ||
            !subspace_operator ||
            !subspace_operator->layers.empty()) {
            throw std::runtime_error(
                id + ": invalid subspace calibration state");
        }
        double wall_ms = 0.0;
        const uint32_t sample_count =
            static_cast<uint32_t>(
                label_offsets.size() * 4);
        for (size_t position_index = 0;
             position_index < label_offsets.size();
             ++position_index) {
            const size_t label_offset =
                label_offsets[position_index];
            const llama_pos label_pos = static_cast<llama_pos>(
                f_boundary_tokens + label_offset);
            for (uint32_t ordinal = 0; ordinal < 4; ++ordinal) {
                size_t source_variant = variants.size();
                for (size_t variant_index = 0;
                     variant_index < variants.size();
                     ++variant_index) {
                    if (fourier_label_ordinals[variant_index]
                            [position_index] == ordinal) {
                        source_variant = variant_index;
                        break;
                    }
                }
                if (source_variant == variants.size()) {
                    throw std::runtime_error(
                        id + ": missing subspace calibration label");
                }
                copy_full_sequence(
                    stage_seqs[position_index],
                    work_seq,
                    label_pos - 1,
                    id + ":stage-" +
                        std::to_string(position_index) +
                        ":ordinal-" + std::to_string(ordinal));
                ++sequence_copy_count;
                const std::vector<llama_token> label_token = {
                    variant_g_tokens[source_variant].at(label_offset),
                };
                const double label_wall_ms = timed_decode(
                    label_token, label_pos, work_seq);
                wall_ms += label_wall_ms;
                label_refresh_wall_ms_total += label_wall_ms;
                ++label_refresh_count;
                require_component_positions(
                    work_seq,
                    label_pos,
                    label_pos,
                    id + ":decoded-" +
                        std::to_string(position_index) +
                        "-" + std::to_string(ordinal));

                llama_kv_cache::value_subspace_metrics metrics = {};
                const auto calibration_started =
                    std::chrono::steady_clock::now();
                if (!attention->seq_collect_value_subspace_sample(
                        work_seq,
                        label_pos,
                        orbit_attention_layers,
                        subspace_include_keys,
                        static_cast<uint32_t>(
                            position_index * 4 + ordinal),
                        sample_count,
                        &subspace_builder,
                        &metrics)) {
                    throw std::runtime_error(
                        id + ": subspace sample collection failed");
                }
                llama_synchronize(ctx);
                subspace_calibration_wall_ms_total +=
                    std::chrono::duration<double, std::milli>(
                        std::chrono::steady_clock::now() -
                        calibration_started).count();
                orbit_host_read_bytes += metrics.host_read_bytes;
                orbit_peak_host_work_bytes = std::max(
                    orbit_peak_host_work_bytes,
                    metrics.peak_host_work_bytes);
                subspace_builder_peak_bytes = std::max(
                    subspace_builder_peak_bytes,
                    metrics.builder_bytes);
                orbit_tensor_visits += metrics.tensor_visits;
                orbit_position_visits += metrics.position_visits;
                ++subspace_calibration_sample_count;

                if (ordinal ==
                    fourier_label_ordinals.at(0)
                        .at(position_index)) {
                    if (!attention->seq_rm(
                            candidate_seq,
                            label_pos,
                            label_pos + 1)) {
                        throw std::runtime_error(
                            id +
                            ": canonical label removal failed");
                    }
                    ++attention_label_remove_count;
                    attention->seq_cp(
                        work_seq,
                        candidate_seq,
                        label_pos,
                        label_pos + 1);
                    llama_synchronize(ctx);
                    ++attention_label_alias_count;
                }
                close_sequence(
                    work_seq,
                    id + ":work-close-" +
                        std::to_string(position_index) +
                        "-" + std::to_string(ordinal));
                ++sequence_close_count;
            }
        }
        llama_kv_cache::value_subspace_metrics
            finalize_metrics = {};
        const auto finalize_started =
            std::chrono::steady_clock::now();
        if (!attention->finalize_value_subspace_operator(
                &subspace_builder,
                static_cast<uint32_t>(label_offsets.size()),
                4,
                subspace_operator,
                &finalize_metrics)) {
            throw std::runtime_error(
                id + ": subspace operator finalization failed");
        }
        subspace_calibration_wall_ms_total +=
            std::chrono::duration<double, std::milli>(
                std::chrono::steady_clock::now() -
                finalize_started).count();
        orbit_peak_host_work_bytes = std::max(
            orbit_peak_host_work_bytes,
            finalize_metrics.peak_host_work_bytes);
        subspace_builder_peak_bytes = std::max(
            subspace_builder_peak_bytes,
            finalize_metrics.builder_bytes);
        subspace_operator_logical_bytes =
            subspace_operator->logical_bytes;
        subspace_operator_vector_backing_bytes =
            subspace_operator->vector_backing_bytes;
        subspace_operator_total_rank =
            subspace_operator->total_rank;
        subspace_operator_maximum_layer_rank =
            subspace_operator->maximum_layer_rank;
        subspace_operator_calibration_max_abs_error =
            subspace_operator->calibration_max_abs_error;
        subspace_operator_closure_max_abs_error =
            subspace_operator->subspace_closure_max_abs_error;
        require_component_positions(
            candidate_seq,
            source_boundary_pos,
            source_boundary_pos,
            id + ":candidate-calibrated");
        if (subspace_operator->calibration_samples !=
                label_offsets.size() * 4 ||
            subspace_calibration_sample_count !=
                label_offsets.size() * 4 ||
            subspace_operator->layers.size() !=
                orbit_attention_layers.size() *
                    (subspace_include_keys ? 2 : 1)) {
            throw std::runtime_error(
                id + ": incomplete subspace operator");
        }
        return wall_ms;
    };

    const auto advance_label_orbit =
            [&](const std::string & stage) {
        std::vector<llama_pos> label_positions;
        label_positions.reserve(label_offsets.size());
        for (const size_t label_offset : label_offsets) {
            label_positions.push_back(static_cast<llama_pos>(
                f_boundary_tokens + label_offset));
        }
        if (subspace_value_orbit_mode) {
            llama_kv_cache::value_subspace_metrics metrics = {};
            if (!attention->seq_apply_value_subspace_step(
                    candidate_seq,
                    label_positions,
                    *subspace_operator,
                    &metrics)) {
                throw std::runtime_error(
                    stage + ": subspace value action failed");
            }
            llama_synchronize(ctx);
            orbit_host_read_bytes += metrics.host_read_bytes;
            orbit_host_write_bytes += metrics.host_write_bytes;
            orbit_peak_host_work_bytes = std::max(
                orbit_peak_host_work_bytes,
                metrics.peak_host_work_bytes);
            orbit_tensor_visits += metrics.tensor_visits;
            orbit_position_visits += metrics.position_visits;
            subspace_operator_vector_backing_bytes =
                metrics.operator_bytes;
            ++orbit_action_count;
            require_component_positions(
                candidate_seq,
                source_boundary_pos,
                source_boundary_pos,
                stage + ":subspace-value-advanced");
            return;
        }
        if (fourier_value_orbit_mode) {
            llama_kv_cache::value_fourier_metrics metrics = {};
            if (!attention->seq_apply_value_fourier_step(
                    candidate_seq,
                    label_positions,
                    fourier_current_ordinals,
                    fourier_operator,
                    &metrics)) {
                throw std::runtime_error(
                    stage + ": Fourier value action failed");
            }
            llama_synchronize(ctx);
            for (uint32_t & ordinal : fourier_current_ordinals) {
                ordinal = (ordinal + 1) % 4;
            }
            orbit_host_read_bytes += metrics.host_read_bytes;
            orbit_host_write_bytes += metrics.host_write_bytes;
            orbit_peak_host_work_bytes = std::max(
                orbit_peak_host_work_bytes,
                metrics.peak_host_work_bytes);
            orbit_tensor_visits += metrics.tensor_visits;
            orbit_position_visits += metrics.position_visits;
            fourier_operator_logical_bytes =
                fourier_operator.logical_bytes;
            fourier_operator_vector_backing_bytes =
                metrics.operator_bytes;
            ++orbit_action_count;
            require_component_positions(
                candidate_seq,
                source_boundary_pos,
                source_boundary_pos,
                stage + ":Fourier-value-advanced");
            return;
        }
        if (complex_phase_orbit_mode) {
            llama_kv_cache::value_orbit_metrics metrics = {};
            if (!attention->seq_apply_complex_phase_quarter_turn(
                    candidate_seq,
                    label_positions,
                    orbit_attention_layers,
                    true,
                    &metrics)) {
                throw std::runtime_error(
                    stage + ": complex K/V phase action failed");
            }
            llama_synchronize(ctx);
            orbit_host_read_bytes += metrics.host_read_bytes;
            orbit_host_write_bytes += metrics.host_write_bytes;
            orbit_peak_host_work_bytes = std::max(
                orbit_peak_host_work_bytes,
                metrics.peak_host_work_bytes);
            orbit_tensor_visits += metrics.tensor_count;
            orbit_position_visits += metrics.position_count;
            ++orbit_action_count;
            require_component_positions(
                candidate_seq,
                source_boundary_pos,
                source_boundary_pos,
                stage + ":complex-phase-advanced");
            return;
        }
        if (value_orbit_mode || key_value_orbit_mode) {
            llama_kv_cache::value_orbit_metrics metrics = {};
            if (!attention->seq_rotate_attention_positions(
                    candidate_seq,
                    label_positions,
                    orbit_attention_layers,
                    key_value_orbit_mode,
                    &metrics)) {
                throw std::runtime_error(
                    stage + ": value orbit action failed");
            }
            llama_synchronize(ctx);
            orbit_backend_copy_bytes +=
                metrics.backend_copy_bytes;
            orbit_host_read_bytes += metrics.host_read_bytes;
            orbit_host_write_bytes += metrics.host_write_bytes;
            orbit_peak_host_work_bytes = std::max(
                orbit_peak_host_work_bytes,
                metrics.peak_host_work_bytes);
            orbit_tensor_visits += metrics.tensor_count;
            orbit_position_visits += metrics.position_count;
            ++orbit_action_count;
            require_component_positions(
                candidate_seq,
                source_boundary_pos,
                source_boundary_pos,
                stage + ":value-orbit-advanced");
            return;
        }

        const llama_pos temporary_begin =
            source_boundary_pos + 65;
        if (temporary_begin +
                static_cast<llama_pos>(label_offsets.size()) >=
            static_cast<llama_pos>(actual_context_per_sequence)) {
            throw std::runtime_error(
                "label orbit temporary topology exceeds sequence context");
        }
        for (size_t i = 0; i < label_positions.size(); ++i) {
            const llama_pos temporary =
                temporary_begin + static_cast<llama_pos>(i);
            attention->seq_add(
                candidate_seq,
                label_positions[i],
                label_positions[i] + 1,
                temporary - label_positions[i]);
            ++orbit_position_shift_count;
        }
        for (size_t i = 0; i < label_positions.size(); ++i) {
            const llama_pos temporary =
                temporary_begin + static_cast<llama_pos>(i);
            const llama_pos destination =
                label_positions[
                    (i + label_positions.size() - 1) %
                    label_positions.size()];
            attention->seq_add(
                candidate_seq,
                temporary,
                temporary + 1,
                destination - temporary);
            ++orbit_position_shift_count;
        }
        ++orbit_action_count;
        require_component_positions(
            candidate_seq,
            source_boundary_pos,
            source_boundary_pos,
            stage + ":orbit-advanced");
    };

    bool fixed_preparation_sequences_closed = false;
    if (orbit_mode) {
        const auto & canonical_variant = variants.at(0);
        const std::string canonical_id =
            canonical_variant.at("id");
        copy_full_sequence(
            scaffold_seq,
            candidate_seq,
            source_boundary_pos,
            canonical_id + ":orbit-scaffold-copy");
        ++sequence_copy_count;
        if (subspace_value_orbit_mode &&
            !build_subspace_operator) {
            if (!subspace_operator ||
                subspace_operator->layers.size() !=
                    orbit_attention_layers.size() *
                        (subspace_include_keys ? 2 : 1) ||
                subspace_operator->calibration_samples <
                    label_offsets.size() * 4 ||
                subspace_operator->training_contexts == 0) {
                throw std::runtime_error(
                    canonical_id +
                    ": imported subspace operator mismatch");
            }
            subspace_operator_logical_bytes =
                subspace_operator->logical_bytes;
            subspace_operator_vector_backing_bytes =
                subspace_operator->vector_backing_bytes;
            subspace_operator_total_rank =
                subspace_operator->total_rank;
            subspace_operator_maximum_layer_rank =
                subspace_operator->maximum_layer_rank;
            subspace_operator_calibration_max_abs_error =
                subspace_operator->calibration_max_abs_error;
            subspace_operator_closure_max_abs_error =
                subspace_operator->subspace_closure_max_abs_error;
        }
        const double canonical_label_wall_ms =
            subspace_value_orbit_mode &&
                build_subspace_operator
                ? calibrate_subspace_operator(
                    canonical_id + ":subspace-calibration")
            : fourier_value_orbit_mode
                ? calibrate_fourier_operator(
                    canonical_id + ":Fourier-calibration")
                : refresh_candidate_labels(
                    variant_g_tokens.at(0),
                    canonical_id + ":orbit-initialization");
        carrier_recurrent_hash_before =
            hash_recurrent_sequence_streamed(ctx, candidate_seq);
        variant_timings.push_back({
            {"variant", canonical_id},
            {"role", "fixed_orbit_initialization"},
            {"label_refresh_count",
                (fourier_value_orbit_mode ||
                 (subspace_value_orbit_mode &&
                  build_subspace_operator))
                    ? label_offsets.size() * 4
                    : label_offsets.size()},
            {"label_refresh_wall_ms", canonical_label_wall_ms},
            {"fourier_operator_logical_bytes",
                fourier_operator_logical_bytes},
            {"fourier_operator_vector_backing_bytes",
                fourier_operator_vector_backing_bytes},
            {"subspace_operator_vector_backing_bytes",
                subspace_operator_vector_backing_bytes},
            {"subspace_operator_total_rank",
                subspace_operator_total_rank},
            {"subspace_operator_training_contexts",
                subspace_operator
                    ? subspace_operator->training_contexts
                    : 0},
            {"subspace_operator_explicit_affine",
                subspace_operator
                    ? subspace_operator->explicit_affine
                    : false},
            {"subspace_operator_calibration_max_abs_error",
                subspace_operator_calibration_max_abs_error},
            {"subspace_operator_closure_max_abs_error",
                subspace_operator_closure_max_abs_error},
        });
        for (size_t i = 0; i < stage_seqs.size(); ++i) {
            close_sequence(
                stage_seqs[i],
                "orbit:stage-close-" + std::to_string(i));
            ++sequence_close_count;
        }
        close_sequence(scaffold_seq, "orbit:scaffold-close");
        ++sequence_close_count;
        fixed_preparation_sequences_closed = true;
    }

    for (size_t variant_index = 0;
         variant_index < variants.size();
         ++variant_index) {
        const auto & variant = variants.at(variant_index);
        const std::string id = variant.at("id");
        const auto & target_g_tokens = variant_g_tokens.at(variant_index);
        double variant_label_wall_ms = 0.0;
        if (orbit_mode) {
            if (variant_index > 0) {
                advance_label_orbit(id);
            }
        } else {
            copy_full_sequence(
                scaffold_seq,
                candidate_seq,
                source_boundary_pos,
                id + ":candidate-scaffold-copy");
            ++sequence_copy_count;
            variant_label_wall_ms =
                refresh_candidate_labels(target_g_tokens, id);
        }

        for (const auto & query : variant.at("queries")) {
            project_from_source(
                candidate_seq,
                orbit_mode ? stage_seqs[0] : work_seq,
                orbit_mode
                    ? "label_orbit_candidate"
                    : "sparse_label_refresh_candidate",
                id,
                query);
        }
        if (!orbit_mode) {
            close_sequence(candidate_seq, id + ":candidate-close");
            ++sequence_close_count;
        }

        copy_full_sequence(
            f_seq,
            work_seq,
            f_boundary_pos,
            id + ":reference-F-copy");
        ++sequence_copy_count;
        const double reference_G_wall_ms = timed_decode(
            target_g_tokens,
            static_cast<llama_pos>(f_boundary_tokens),
            work_seq);
        const double reference_closure_wall_ms = timed_decode(
            closure_tokens,
            static_cast<llama_pos>(
                f_boundary_tokens + target_g_tokens.size()),
            work_seq);
        reference_G_wall_ms_total += reference_G_wall_ms;
        reference_closure_wall_ms_total +=
            reference_closure_wall_ms;
        require_component_positions(
            work_seq,
            source_boundary_pos,
            source_boundary_pos,
            id + ":reference-complete");
        for (const auto & query : variant.at("queries")) {
            project_from_source(
                work_seq,
                orbit_mode ? stage_seqs[0] : candidate_seq,
                "exact_full_state",
                id,
                query);
        }
        close_sequence(work_seq, id + ":reference-close");
        ++sequence_close_count;
        variant_timings.push_back({
            {"variant", id},
            {"label_refresh_count",
                orbit_mode ? 0 : label_offsets.size()},
            {"label_refresh_wall_ms", variant_label_wall_ms},
            {"orbit_action_count_before_projection",
                orbit_action_count},
            {"reference_G_tokens", target_g_tokens.size()},
            {"reference_G_wall_ms", reference_G_wall_ms},
            {"reference_closure_tokens", closure_tokens.size()},
            {"reference_closure_wall_ms",
                reference_closure_wall_ms},
        });

        require_component_positions(
            f_seq,
            f_boundary_pos,
            f_boundary_pos,
            id + ":F-survives");
        require_component_positions(
            scaffold_seq,
            fixed_preparation_sequences_closed ? -1 :
                source_boundary_pos,
            fixed_preparation_sequences_closed ? -1 :
                source_boundary_pos,
            id + ":scaffold-lifecycle");
    }

    size_t return_boundary_matches = 0;
    size_t return_full_logit_hash_matches = 0;
    double return_maximum_candidate_logit_absolute_difference = 0.0;
    if (orbit_mode) {
        advance_label_orbit("orbit-return-G0");
        for (const auto & query : variants.at(0).at("queries")) {
            project_from_source(
                candidate_seq,
                stage_seqs[0],
                "label_orbit_return_G0",
                variants.at(0).at("id"),
                query);
        }
        const auto & initial =
            outputs.at("label_orbit_candidate")
                .at(variants.at(0).at("id").get<std::string>());
        const auto & returned =
            outputs.at("label_orbit_return_G0")
                .at(variants.at(0).at("id").get<std::string>());
        for (size_t i = 0; i < initial.size(); ++i) {
            return_boundary_matches +=
                initial.at(i).argmax == returned.at(i).argmax;
            return_full_logit_hash_matches +=
                initial.at(i).full_logits_fnv1a64 ==
                returned.at(i).full_logits_fnv1a64;
            for (size_t c = 0;
                 c < initial.at(i).candidate_logits.size();
                 ++c) {
                return_maximum_candidate_logit_absolute_difference =
                    std::max(
                        return_maximum_candidate_logit_absolute_difference,
                        std::abs(
                            static_cast<double>(
                                initial.at(i).candidate_logits.at(c)) -
                            static_cast<double>(
                                returned.at(i).candidate_logits.at(c))));
            }
        }
    }

    const auto f_hash_after =
        hash_recurrent_sequence_streamed(ctx, f_seq);
    const auto carrier_recurrent_hash_after =
        hash_recurrent_sequence_streamed(
            ctx, orbit_mode ? candidate_seq : scaffold_seq);
    const bool f_exact =
        f_hash_before.tensor.value == f_hash_after.tensor.value &&
        f_hash_before.physical_row == f_hash_after.physical_row &&
        f_hash_before.position == f_hash_after.position;
    const bool scaffold_exact =
        carrier_recurrent_hash_before.tensor.value ==
            carrier_recurrent_hash_after.tensor.value &&
        carrier_recurrent_hash_before.physical_row ==
            carrier_recurrent_hash_after.physical_row &&
        carrier_recurrent_hash_before.position ==
            carrier_recurrent_hash_after.position;

    const std::vector<std::string> routes = {
        "exact_full_state",
        orbit_mode
            ? "label_orbit_candidate"
            : "sparse_label_refresh_candidate",
    };
    json route_summary = json::object();
    const size_t comparisons =
        variants.size() *
        spec.at("queries_per_variant").get<size_t>();
    for (const auto & route : routes) {
        size_t correct = 0;
        size_t full_logit_hash_matches = 0;
        size_t boundary_matches = 0;
        double maximum_candidate_logit_absolute_difference = 0.0;
        for (const auto & variant : variants) {
            const std::string id = variant.at("id");
            const auto & route_outputs = outputs.at(route).at(id);
            const auto & reference =
                outputs.at("exact_full_state").at(id);
            correct += semantic_correct_count(
                route_outputs, variant.at("queries"), false);
            for (size_t i = 0; i < route_outputs.size(); ++i) {
                full_logit_hash_matches +=
                    route_outputs.at(i).full_logits_fnv1a64 ==
                    reference.at(i).full_logits_fnv1a64;
                boundary_matches +=
                    route_outputs.at(i).argmax ==
                    reference.at(i).argmax;
                for (size_t c = 0;
                     c < route_outputs.at(i).candidate_logits.size();
                     ++c) {
                    maximum_candidate_logit_absolute_difference = std::max(
                        maximum_candidate_logit_absolute_difference,
                        std::abs(
                            static_cast<double>(
                                route_outputs.at(i).candidate_logits.at(c)) -
                            static_cast<double>(
                                reference.at(i).candidate_logits.at(c))));
                }
            }
        }
        route_summary[route] = {
            {"correct", correct},
            {"comparisons", comparisons},
            {"full_logit_hash_matches", full_logit_hash_matches},
            {"boundary_matches", boundary_matches},
            {"maximum_candidate_logit_absolute_difference",
                maximum_candidate_logit_absolute_difference},
        };
    }

    const auto & acceptance = spec.at("acceptance_law");
    const auto & primary =
        route_summary.at(
            orbit_mode
                ? "label_orbit_candidate"
                : "sparse_label_refresh_candidate");
    const bool accepted =
        primary.at("correct").get<size_t>() ==
            acceptance.at("primary_correct").get<size_t>() &&
        primary.at("boundary_matches").get<size_t>() ==
            acceptance.at("primary_boundary_matches").get<size_t>() &&
        (!orbit_mode ||
            return_boundary_matches ==
                acceptance.at(
                    "return_boundary_matches").get<size_t>()) &&
        f_exact &&
        scaffold_exact;

    if (orbit_mode) {
        close_sequence(candidate_seq, "orbit:carrier-close");
        ++sequence_close_count;
    }
    close_sequence(f_seq, "sparse:F-close");
    ++sequence_close_count;
    if (!fixed_preparation_sequences_closed) {
        for (size_t i = 0; i < stage_seqs.size(); ++i) {
            close_sequence(
                stage_seqs[i],
                "sparse:stage-close-" + std::to_string(i));
            ++sequence_close_count;
        }
        close_sequence(scaffold_seq, "sparse:scaffold-close");
        ++sequence_close_count;
    }
    llama_memory_clear(memory, true);
    llama_synchronize(ctx);
    bool all_sequences_closed = true;
    for (llama_seq_id seq_id = 0;
         seq_id < static_cast<llama_seq_id>(actual_n_seq_max);
         ++seq_id) {
        all_sequences_closed =
            all_sequences_closed &&
            attention->seq_pos_max(seq_id) == -1 &&
            recurrent->seq_pos_max(seq_id) == -1;
    }
    const bool all_roots_closed =
        llama_state_seq_get_device_root_count(ctx) == 0;
    const bool active_backings_stable =
        active_recurrent_backing_id(ctx) ==
            active_recurrent_backing_initial &&
        active_attention_backing_id(ctx) ==
            active_attention_backing_initial;
    if (!all_sequences_closed ||
        !all_roots_closed ||
        !active_backings_stable) {
        throw std::runtime_error(
            "sparse G refresh close invariant failed");
    }

    const size_t fixed_carrier_preparation_tokens =
        f_boundary_tokens +
        structural_g_tokens.size() +
        closure_tokens.size();
    const size_t candidate_initialization_source_tokens =
        orbit_mode &&
            !fourier_value_orbit_mode &&
            !(subspace_value_orbit_mode &&
              build_subspace_operator)
            ? label_offsets.size()
            : 0;
    const size_t fourier_calibration_source_tokens =
        fourier_value_orbit_mode
            ? label_offsets.size() * 4
            : 0;
    const size_t subspace_calibration_source_tokens =
        subspace_value_orbit_mode &&
            build_subspace_operator
            ? label_offsets.size() * 4
            : 0;
    const size_t candidate_variable_source_tokens =
        orbit_mode ? 0 :
            variants.size() * label_offsets.size();
    const size_t candidate_source_tokens =
        fixed_carrier_preparation_tokens +
        candidate_initialization_source_tokens +
        fourier_calibration_source_tokens +
        subspace_calibration_source_tokens +
        candidate_variable_source_tokens;
    const size_t reference_source_tokens =
        variants.size() *
        (structural_g_tokens.size() + closure_tokens.size());
    const size_t source_decode_tokens =
        candidate_source_tokens + reference_source_tokens;
    return {
        {"schema_version", 1},
        {"mechanism", subspace_value_orbit_mode
            ? subspace_include_keys
                ? build_subspace_operator
                    ? "IN_PLACE_STATE_CONDITIONED_LOW_RANK_KEY_VALUE_ACTION"
                    : "TRANSFERRED_STATE_CONDITIONED_LOW_RANK_KEY_VALUE_ACTION"
                : build_subspace_operator
                    ? "IN_PLACE_STATE_CONDITIONED_LOW_RANK_VALUE_ACTION"
                    : "TRANSFERRED_STATE_CONDITIONED_LOW_RANK_VALUE_ACTION"
            : fourier_value_orbit_mode
            ? "IN_PLACE_RANK3_FOURIER_LABEL_VALUE_ACTION"
            : complex_phase_orbit_mode
            ? "IN_PLACE_COMPLEX_KV_PHASE_QUARTER_TURN"
            : key_value_orbit_mode
            ? "IN_PLACE_LABEL_KEY_VALUE_ORBIT_ACTION"
            : layer_selective_value_orbit
                ? "IN_PLACE_LAYER_SELECTIVE_LABEL_VALUE_ORBIT_ACTION"
            : value_orbit_mode
                ? "IN_PLACE_LABEL_VALUE_ORBIT_ACTION"
            : orbit_mode
                ? "IN_PLACE_LABEL_ORBIT_ATTENTION_ACTION"
                : "SPARSE_G_LABEL_REFRESH_ADVANCE"},
        {"spec_id", spec.at("id")},
        {"model_arch", "qwen35moe"},
        {"configuration", {
            {"context_size", actual_context_size},
            {"context_per_sequence", actual_context_per_sequence},
            {"n_seq_max", actual_n_seq_max},
            {"source_tokens", expected_source_tokens},
            {"F_boundary_tokens", f_boundary_tokens},
            {"G_tokens", structural_g_tokens.size()},
            {"closure_tokens", closure_tokens.size()},
            {"label_token_offsets", label_offsets},
            {"label_refresh_tokens_per_variant",
                orbit_mode ? 0 : label_offsets.size()},
            {"fixed_label_initialization_tokens",
                candidate_initialization_source_tokens},
            {"label_orbit_action", orbit_mode},
            {"value_only_orbit_action", value_orbit_mode},
            {"key_value_orbit_action", key_value_orbit_mode},
            {"complex_phase_quarter_turn_action",
                complex_phase_orbit_mode},
            {"fourier_value_orbit_action",
                fourier_value_orbit_mode},
            {"subspace_value_orbit_action",
                subspace_value_orbit_mode},
            {"subspace_include_keys",
                subspace_include_keys},
            {"subspace_operator_built_in_this_panel",
                subspace_value_orbit_mode &&
                build_subspace_operator},
            {"fourier_label_ordinals",
                fourier_label_ordinals},
            {"orbit_attention_layers", orbit_attention_layers},
            {"stage_sequence_count", stage_seqs.size()},
            {"retained_device_roots_used", false},
            {"attention_stream_count", attention_stream_count},
            {"partial_attention_sequence_copy_metadata_only",
                attention_stream_count == 1},
            {"restoration_class", "DECLARED_CLOSURE"},
        }},
        {"summary", {
            {"route_summary", route_summary},
            {"F_recurrent_content_and_row_exact", f_exact},
            {"scaffold_recurrent_content_and_row_exact",
                scaffold_exact},
            {"orbit_return_boundary_matches",
                return_boundary_matches},
            {"orbit_return_full_logit_hash_matches",
                return_full_logit_hash_matches},
            {"orbit_return_maximum_candidate_logit_absolute_difference",
                return_maximum_candidate_logit_absolute_difference},
            {"accepted", accepted},
        }},
        {"carrier", {
            {"active_cache_backend_allocation_bytes",
                active_cache_backend_allocation_bytes},
            {"maximum_retained_root_backend_allocation_bytes", 0},
            {"active_plus_retained_backend_allocation_bytes",
                active_cache_backend_allocation_bytes},
            {"F_recurrent_hash_before",
                hex64(f_hash_before.tensor.value)},
            {"F_recurrent_hash_after",
                hex64(f_hash_after.tensor.value)},
            {"F_recurrent_physical_row",
                f_hash_before.physical_row},
            {"scaffold_recurrent_hash_before",
                hex64(carrier_recurrent_hash_before.tensor.value)},
            {"scaffold_recurrent_hash_after",
                hex64(carrier_recurrent_hash_after.tensor.value)},
            {"scaffold_recurrent_physical_row",
                carrier_recurrent_hash_before.physical_row},
            {"scaffold_attention_logical_bytes",
                scaffold_attention_logical_bytes},
            {"refreshed_attention_logical_bytes",
                refreshed_attention_logical_bytes},
            {"complete_host_state_copy_retained", false},
            {"all_sequences_closed", all_sequences_closed},
            {"all_retained_roots_closed", all_roots_closed},
            {"active_backings_stable", active_backings_stable},
        }},
        {"variant_timings", variant_timings},
        {"resource_accounting", {
            {"F_prefix_wall_ms", f_prefix_wall_ms},
            {"F_module_wall_ms", f_module_wall_ms},
            {"scaffold_G_wall_ms", scaffold_G_wall_ms},
            {"scaffold_closure_wall_ms",
                scaffold_closure_wall_ms},
            {"label_refresh_wall_ms_total",
                label_refresh_wall_ms_total},
            {"fourier_calibration_wall_ms_total",
                fourier_calibration_wall_ms_total},
            {"subspace_calibration_wall_ms_total",
                subspace_calibration_wall_ms_total},
            {"reference_G_wall_ms_total",
                reference_G_wall_ms_total},
            {"reference_closure_wall_ms_total",
                reference_closure_wall_ms_total},
            {"fixed_carrier_preparation_tokens",
                fixed_carrier_preparation_tokens},
            {"candidate_initialization_source_tokens",
                candidate_initialization_source_tokens},
            {"fourier_calibration_source_tokens",
                fourier_calibration_source_tokens},
            {"subspace_calibration_source_tokens",
                subspace_calibration_source_tokens},
            {"candidate_variable_source_tokens",
                candidate_variable_source_tokens},
            {"candidate_source_tokens",
                candidate_source_tokens},
            {"predecessor_closure_scaffold_candidate_source_tokens",
                f_boundary_tokens + expected_source_tokens +
                variants.size() * structural_g_tokens.size()},
            {"predecessor_active_F_candidate_source_tokens",
                f_boundary_tokens +
                variants.size() *
                    (structural_g_tokens.size() +
                     closure_tokens.size())},
            {"reference_source_tokens",
                reference_source_tokens},
            {"source_decode_tokens", source_decode_tokens},
            {"query_decode_tokens", query_decode_tokens},
            {"all_route_input_tokens",
                source_decode_tokens + query_decode_tokens},
            {"sequence_copy_count", sequence_copy_count},
            {"sequence_close_count", sequence_close_count},
            {"label_refresh_count", label_refresh_count},
            {"attention_label_remove_count",
                attention_label_remove_count},
            {"attention_label_alias_count",
                attention_label_alias_count},
            {"orbit_action_count", orbit_action_count},
            {"orbit_position_shift_count",
                orbit_position_shift_count},
            {"orbit_backend_copy_bytes",
                orbit_backend_copy_bytes},
            {"orbit_host_read_bytes", orbit_host_read_bytes},
            {"orbit_host_write_bytes", orbit_host_write_bytes},
            {"orbit_peak_host_work_bytes",
                orbit_peak_host_work_bytes},
            {"orbit_tensor_visits", orbit_tensor_visits},
            {"orbit_position_visits", orbit_position_visits},
            {"fourier_calibration_sample_count",
                fourier_calibration_sample_count},
            {"fourier_operator_logical_bytes",
                fourier_operator_logical_bytes},
            {"fourier_operator_vector_backing_bytes",
                fourier_operator_vector_backing_bytes},
            {"subspace_calibration_sample_count",
                subspace_calibration_sample_count},
            {"subspace_builder_peak_bytes",
                subspace_builder_peak_bytes},
            {"subspace_operator_logical_bytes",
                subspace_operator_logical_bytes},
            {"subspace_operator_vector_backing_bytes",
                subspace_operator_vector_backing_bytes},
            {"subspace_operator_total_rank",
                subspace_operator_total_rank},
            {"subspace_operator_maximum_layer_rank",
                subspace_operator_maximum_layer_rank},
            {"subspace_operator_training_contexts",
                subspace_operator
                    ? subspace_operator->training_contexts
                    : 0},
            {"subspace_operator_explicit_affine",
                subspace_operator
                    ? subspace_operator->explicit_affine
                    : false},
            {"subspace_operator_calibration_max_abs_error",
                subspace_operator_calibration_max_abs_error},
            {"subspace_operator_closure_max_abs_error",
                subspace_operator_closure_max_abs_error},
            {"snapshot_root_save_device_copy_bytes", 0},
            {"snapshot_root_restore_device_copy_bytes", 0},
            {"carrier_hash_d2h_bytes",
                f_hash_before.tensor.transferred_bytes +
                f_hash_after.tensor.transferred_bytes +
                carrier_recurrent_hash_before.tensor.transferred_bytes +
                carrier_recurrent_hash_after.tensor.transferred_bytes},
            {"carrier_hash_peak_host_work_bytes", std::max({
                f_hash_before.tensor.peak_host_work_bytes,
                f_hash_after.tensor.peak_host_work_bytes,
                carrier_recurrent_hash_before.tensor.peak_host_work_bytes,
                carrier_recurrent_hash_after.tensor.peak_host_work_bytes,
            })},
            {"asymptotic_candidate_source_ratio",
                orbit_mode ? 0.0 :
                    static_cast<double>(label_offsets.size()) /
                        static_cast<double>(expected_source_tokens)},
        }},
        {"records", records},
        {"verdict", accepted ? "accept" : "reject"},
        {"claim_ceiling", spec.at("claim_ceiling")},
    };
}

static json run_open_f_prefix_nonlinear_composition(
        llama_context * ctx,
        const llama_vocab * vocab,
        const std::vector<llama_token> & candidates,
        const json & spec,
        uint64_t active_recurrent_backing_initial,
        uint64_t active_attention_backing_initial) {
    const uint32_t actual_context_size = llama_n_ctx(ctx);
    if (actual_context_size != spec.at("expected_context_size").get<uint32_t>()) {
        throw std::runtime_error(
            "open-F composition context mismatch: " +
            std::to_string(actual_context_size));
    }
    const size_t expected_source_tokens =
        spec.at("expected_source_tokens").get<size_t>();
    const std::string prefix = spec.at("prefix");
    const std::string module_f = spec.at("module_f");
    const std::string neutral_module_f = spec.at("neutral_module_f");
    const std::string neutral_module_g = spec.at("neutral_module_g");
    const std::string closure = spec.at("closure");
    const auto prefix_tokens =
        tokenize_piece(vocab, prefix, true, true);
    const auto f_tokens =
        tokenize_piece(vocab, module_f, false, true);
    const auto neutral_f_tokens =
        tokenize_piece(vocab, neutral_module_f, false, true);
    const auto neutral_g_tokens =
        tokenize_piece(vocab, neutral_module_g, false, true);
    const auto closure_tokens =
        tokenize_piece(vocab, closure, false, true);
    if (prefix_tokens.size() != spec.at("expected_prefix_tokens").get<size_t>() ||
        f_tokens.size() != spec.at("expected_f_tokens").get<size_t>() ||
        neutral_f_tokens.size() != f_tokens.size() ||
        neutral_g_tokens.size() != spec.at("expected_g_tokens").get<size_t>() ||
        closure_tokens.size() !=
            spec.at("expected_closure_tokens").get<size_t>() ||
        prefix_tokens.size() + f_tokens.size() +
            neutral_g_tokens.size() + closure_tokens.size() !=
            expected_source_tokens) {
        throw std::runtime_error("open-F public token geometry mismatch");
    }
    const size_t f_boundary_tokens =
        prefix_tokens.size() + f_tokens.size();
    const auto & variants = spec.at("g_variants");
    if (!variants.is_array() || variants.empty()) {
        throw std::runtime_error("open-F composition has no G variants");
    }
    std::set<std::string> variant_ids;
    for (const auto & variant : variants) {
        const std::string id = variant.at("id");
        if (!variant_ids.insert(id).second) {
            throw std::runtime_error("duplicate open-F G variant " + id);
        }
        const auto g_tokens = tokenize_piece(
            vocab, variant.at("module_g").get<std::string>(), false, true);
        if (g_tokens.size() != neutral_g_tokens.size() ||
            variant.at("queries").size() !=
                spec.at("queries_per_variant").get<size_t>()) {
            throw std::runtime_error(
                "open-F G variant geometry mismatch for " + id);
        }
    }

    llama_memory_clear(llama_get_memory(ctx), true);
    decode_tokens(ctx, prefix_tokens, 0, false);
    llama_synchronize(ctx);
    auto prefix_root = save_root(
        ctx, "open-F:common-prefix", 10000, FULL_DEVICE_FLAGS,
        prefix_tokens.size());

    restore_root(ctx, prefix_root);
    decode_tokens(
        ctx, f_tokens, static_cast<llama_pos>(prefix_tokens.size()), false);
    llama_synchronize(ctx);
    auto f_root = save_root(
        ctx, "open-F:F-carrier", 10001, FULL_DEVICE_FLAGS,
        f_boundary_tokens);

    restore_root(ctx, prefix_root);
    decode_tokens(
        ctx, neutral_f_tokens,
        static_cast<llama_pos>(prefix_tokens.size()), false);
    llama_synchronize(ctx);
    auto neutral_f_root = save_root(
        ctx, "open-F:neutral-F-control", 10002, FULL_DEVICE_FLAGS,
        f_boundary_tokens);

    const size_t cleared_prefix_root_bytes =
        llama_state_seq_clear_device_data(ctx, prefix_root.key);
    if (llama_state_seq_get_device_root_count(ctx) != 2) {
        throw std::runtime_error(
            "open-F prefix closure damaged branch roots");
    }

    restore_root(ctx, f_root);
    const auto f_recurrent_digest_before =
        hash_recurrent_state_streamed(ctx);
    const size_t active_cache_backend_allocation_bytes =
        active_hybrid_backend_allocation_bytes(ctx);

    llama_seq_id final_key = 10003;
    size_t source_decode_tokens_all =
        prefix_tokens.size() + f_tokens.size() + neutral_f_tokens.size();
    size_t query_decode_tokens = 0;
    size_t candidate_suffix_decode_tokens = 0;
    size_t reference_full_decode_tokens = 0;
    size_t g_only_suffix_decode_tokens = 0;
    size_t f_only_suffix_decode_tokens = 0;
    size_t f_root_restore_count = 1;
    size_t neutral_f_root_restore_count = 0;
    size_t final_root_restore_count = 0;
    size_t root_save_device_copy_bytes =
        prefix_root.gpu_bytes + f_root.gpu_bytes + neutral_f_root.gpu_bytes;
    size_t f_root_restore_device_copy_bytes = f_root.gpu_bytes;
    size_t neutral_f_root_restore_device_copy_bytes = 0;
    size_t final_root_restore_device_copy_bytes = 0;
    size_t cleared_final_root_bytes = 0;
    size_t maximum_retained_root_backend_allocation_bytes = std::max(
        prefix_root.allocation_bytes +
            f_root.allocation_bytes +
            neutral_f_root.allocation_bytes,
        f_root.allocation_bytes + neutral_f_root.allocation_bytes);
    json records = json::array();
    json variant_summary = json::object();
    size_t variant_passes = 0;
    size_t full_logit_hash_matches = 0;
    size_t boundary_matches = 0;
    size_t comparisons = 0;
    double maximum_candidate_logit_absolute_difference = 0.0;

    const auto decode_tail =
            [&](const std::vector<llama_token> & g_tokens) {
        decode_tokens(
            ctx, g_tokens, static_cast<llama_pos>(f_boundary_tokens), false);
        decode_tokens(
            ctx, closure_tokens,
            static_cast<llama_pos>(
                f_boundary_tokens + g_tokens.size()), false);
        llama_synchronize(ctx);
        return g_tokens.size() + closure_tokens.size();
    };
    const auto query_final_root =
            [&](const std::string & route,
                const std::string & variant_id,
                const device_root & root,
                const json & queries,
                std::vector<boundary_result> & outputs) {
        for (const auto & query : queries) {
            restore_root(ctx, root);
            ++final_root_restore_count;
            final_root_restore_device_copy_bytes += root.gpu_bytes;
            auto boundary = decode_query(
                ctx, vocab, candidates, route, variant_id, query,
                expected_source_tokens, root.backing_id, root.gpu_bytes);
            query_decode_tokens +=
                boundary.record.at("query_tokens").get<size_t>();
            records.push_back(boundary.record);
            outputs.push_back(std::move(boundary));
        }
    };
    const auto close_final_root =
            [&](const device_root & root) {
        llama_memory_clear(llama_get_memory(ctx), true);
        cleared_final_root_bytes +=
            llama_state_seq_clear_device_data(ctx, root.key);
        if (llama_state_seq_get_device_root_count(ctx) != 2) {
            throw std::runtime_error(
                "open-F final-root closure damaged branch roots");
        }
    };

    for (const auto & variant : variants) {
        const std::string id = variant.at("id");
        const auto g_tokens = tokenize_piece(
            vocab, variant.at("module_g").get<std::string>(), false, true);
        const auto & queries = variant.at("queries");

        restore_root(ctx, f_root);
        ++f_root_restore_count;
        f_root_restore_device_copy_bytes += f_root.gpu_bytes;
        const size_t candidate_tail_tokens = decode_tail(g_tokens);
        candidate_suffix_decode_tokens += candidate_tail_tokens;
        source_decode_tokens_all += candidate_tail_tokens;
        auto candidate_root = save_root(
            ctx, id + ":open-F-G-result", final_key++,
            FULL_DEVICE_FLAGS, expected_source_tokens);
        root_save_device_copy_bytes += candidate_root.gpu_bytes;
        maximum_retained_root_backend_allocation_bytes = std::max(
            maximum_retained_root_backend_allocation_bytes,
            f_root.allocation_bytes +
                neutral_f_root.allocation_bytes +
                candidate_root.allocation_bytes);
        std::vector<boundary_result> candidate_results;
        query_final_root(
            "open-F-causal-G-forward", id + ":candidate",
            candidate_root, queries, candidate_results);
        close_final_root(candidate_root);

        llama_memory_clear(llama_get_memory(ctx), true);
        decode_tokens(ctx, prefix_tokens, 0, false);
        decode_tokens(
            ctx, f_tokens,
            static_cast<llama_pos>(prefix_tokens.size()), false);
        decode_tokens(
            ctx, g_tokens,
            static_cast<llama_pos>(f_boundary_tokens), false);
        decode_tokens(
            ctx, closure_tokens,
            static_cast<llama_pos>(
                f_boundary_tokens + g_tokens.size()), false);
        llama_synchronize(ctx);
        reference_full_decode_tokens += expected_source_tokens;
        source_decode_tokens_all += expected_source_tokens;
        auto reference_root = save_root(
            ctx, id + ":isolated-full-replay-control", final_key++,
            FULL_DEVICE_FLAGS, expected_source_tokens);
        root_save_device_copy_bytes += reference_root.gpu_bytes;
        maximum_retained_root_backend_allocation_bytes = std::max(
            maximum_retained_root_backend_allocation_bytes,
            f_root.allocation_bytes +
                neutral_f_root.allocation_bytes +
                reference_root.allocation_bytes);
        std::vector<boundary_result> reference_results;
        query_final_root(
            "isolated-full-replay-control", id + ":reference",
            reference_root, queries, reference_results);
        close_final_root(reference_root);

        restore_root(ctx, neutral_f_root);
        ++neutral_f_root_restore_count;
        neutral_f_root_restore_device_copy_bytes += neutral_f_root.gpu_bytes;
        const size_t g_only_tail_tokens = decode_tail(g_tokens);
        g_only_suffix_decode_tokens += g_only_tail_tokens;
        source_decode_tokens_all += g_only_tail_tokens;
        auto g_only_root = save_root(
            ctx, id + ":G-only-control", final_key++,
            FULL_DEVICE_FLAGS, expected_source_tokens);
        root_save_device_copy_bytes += g_only_root.gpu_bytes;
        maximum_retained_root_backend_allocation_bytes = std::max(
            maximum_retained_root_backend_allocation_bytes,
            f_root.allocation_bytes +
                neutral_f_root.allocation_bytes +
                g_only_root.allocation_bytes);
        std::vector<boundary_result> g_only_results;
        query_final_root(
            "G-only-causal-forward-control", id + ":G_only",
            g_only_root, queries, g_only_results);
        close_final_root(g_only_root);

        const size_t candidate_correct =
            semantic_correct_count(candidate_results, queries, false);
        const size_t reference_correct =
            semantic_correct_count(reference_results, queries, false);
        const size_t g_only_correct =
            semantic_correct_count(g_only_results, queries, false);
        size_t variant_hash_matches = 0;
        size_t variant_boundary_matches = 0;
        double variant_maximum_difference = 0.0;
        std::vector<std::string> candidate_answers;
        std::vector<std::string> reference_answers;
        std::vector<std::string> g_only_answers;
        for (size_t i = 0; i < queries.size(); ++i) {
            const auto & candidate = candidate_results.at(i);
            const auto & reference = reference_results.at(i);
            candidate_answers.push_back(candidate.argmax);
            reference_answers.push_back(reference.argmax);
            g_only_answers.push_back(g_only_results.at(i).argmax);
            variant_hash_matches +=
                candidate.full_logits_fnv1a64 ==
                reference.full_logits_fnv1a64;
            variant_boundary_matches +=
                candidate.argmax == reference.argmax;
            for (size_t c = 0; c < candidate.candidate_logits.size(); ++c) {
                variant_maximum_difference = std::max(
                    variant_maximum_difference,
                    std::abs(
                        static_cast<double>(
                            candidate.candidate_logits.at(c)) -
                        static_cast<double>(
                            reference.candidate_logits.at(c))));
            }
        }
        full_logit_hash_matches += variant_hash_matches;
        boundary_matches += variant_boundary_matches;
        comparisons += queries.size();
        maximum_candidate_logit_absolute_difference = std::max(
            maximum_candidate_logit_absolute_difference,
            variant_maximum_difference);
        const bool passed =
            candidate_correct >=
                variant.at("joint_correct_minimum").get<size_t>() &&
            reference_correct >=
                variant.at("joint_correct_minimum").get<size_t>() &&
            g_only_correct <=
                variant.at("g_only_correct_maximum").get<size_t>() &&
            variant_hash_matches == queries.size() &&
            variant_maximum_difference == 0.0;
        variant_passes += passed;
        variant_summary[id] = {
            {"candidate", {
                {"answers", candidate_answers},
                {"correct", candidate_correct},
            }},
            {"isolated_full_replay", {
                {"answers", reference_answers},
                {"correct", reference_correct},
            }},
            {"G_only", {
                {"answers", g_only_answers},
                {"correct", g_only_correct},
            }},
            {"full_logit_hash_matches", variant_hash_matches},
            {"boundary_matches", variant_boundary_matches},
            {"maximum_candidate_logit_absolute_difference",
                variant_maximum_difference},
            {"passed", passed},
        };
    }

    restore_root(ctx, f_root);
    ++f_root_restore_count;
    f_root_restore_device_copy_bytes += f_root.gpu_bytes;
    const size_t f_only_tail_tokens = decode_tail(neutral_g_tokens);
    f_only_suffix_decode_tokens += f_only_tail_tokens;
    source_decode_tokens_all += f_only_tail_tokens;
    auto f_only_root = save_root(
        ctx, "open-F:F-only-control", final_key++,
        FULL_DEVICE_FLAGS, expected_source_tokens);
    root_save_device_copy_bytes += f_only_root.gpu_bytes;
    maximum_retained_root_backend_allocation_bytes = std::max(
        maximum_retained_root_backend_allocation_bytes,
        f_root.allocation_bytes +
            neutral_f_root.allocation_bytes +
            f_only_root.allocation_bytes);
    std::vector<boundary_result> f_only_results;
    query_final_root(
        "F-only-causal-forward-control", "F_only",
        f_only_root, spec.at("f_only_queries"), f_only_results);
    close_final_root(f_only_root);
    const size_t f_only_correct = semantic_correct_count(
        f_only_results, spec.at("f_only_queries"), false);

    restore_root(ctx, f_root);
    ++f_root_restore_count;
    f_root_restore_device_copy_bytes += f_root.gpu_bytes;
    const auto f_recurrent_digest_after =
        hash_recurrent_state_streamed(ctx);
    const bool f_recurrent_tensor_digest_match =
        f_recurrent_digest_before.value == f_recurrent_digest_after.value &&
        f_recurrent_digest_before.transferred_bytes ==
            f_recurrent_digest_after.transferred_bytes;
    const auto & acceptance = spec.at("acceptance_law");
    const bool accepted =
        variant_passes >=
            acceptance.at("variant_passes_minimum").get<size_t>() &&
        f_only_correct <=
            acceptance.at("f_only_correct_maximum").get<size_t>() &&
        comparisons ==
            acceptance.at("comparisons").get<size_t>() &&
        full_logit_hash_matches ==
            acceptance.at("full_logit_hash_matches").get<size_t>() &&
        boundary_matches ==
            acceptance.at("boundary_matches").get<size_t>() &&
        maximum_candidate_logit_absolute_difference <=
            acceptance.at(
                "maximum_candidate_logit_absolute_difference").get<double>() &&
        f_recurrent_tensor_digest_match;

    llama_memory_clear(llama_get_memory(ctx), true);
    const size_t cleared_f_root_bytes =
        llama_state_seq_clear_device_data(ctx, f_root.key);
    const size_t cleared_neutral_f_root_bytes =
        llama_state_seq_clear_device_data(ctx, neutral_f_root.key);
    llama_synchronize(ctx);
    if (llama_state_seq_get_device_root_count(ctx) != 0 ||
        active_recurrent_backing_id(ctx) != active_recurrent_backing_initial ||
        active_attention_backing_id(ctx) != active_attention_backing_initial) {
        throw std::runtime_error(
            "open-F composition close invariant failed");
    }

    const size_t candidate_construction_tokens =
        prefix_tokens.size() + f_tokens.size() +
        candidate_suffix_decode_tokens;
    const size_t full_replay_candidate_tokens =
        variants.size() * expected_source_tokens;
    const size_t prefix_dag_candidate_tokens =
        prefix_tokens.size() +
        variants.size() * (expected_source_tokens - prefix_tokens.size());
    return {
        {"schema_version", 1},
        {"mechanism", "OPEN_F_PREFIX_MODEL_NATIVE_NONLINEAR_G_COMPOSITION"},
        {"spec_id", spec.at("id")},
        {"model_arch", "qwen35moe"},
        {"configuration", {
            {"context_size", actual_context_size},
            {"source_tokens", expected_source_tokens},
            {"prefix_tokens", prefix_tokens.size()},
            {"F_tokens", f_tokens.size()},
            {"G_tokens", neutral_g_tokens.size()},
            {"closure_tokens", closure_tokens.size()},
            {"F_boundary_tokens", f_boundary_tokens},
            {"G_variant_count", variants.size()},
            {"queries_per_variant", spec.at("queries_per_variant")},
            {"prebuilt_joint_root_available_to_candidate", false},
            {"isolated_full_replay_control", true},
            {"restoration_class", "SNAPSHOT_RELOAD"},
        }},
        {"summary", {
            {"variant_passes", variant_passes},
            {"variant_count", variants.size()},
            {"F_only_correct", f_only_correct},
            {"full_logit_hash_matches", full_logit_hash_matches},
            {"boundary_matches", boundary_matches},
            {"comparisons", comparisons},
            {"maximum_candidate_logit_absolute_difference",
                maximum_candidate_logit_absolute_difference},
            {"F_recurrent_tensor_digest_match",
                f_recurrent_tensor_digest_match},
            {"accepted", accepted},
        }},
        {"variant_summary", variant_summary},
        {"construction", {
            {"candidate_source_tokens", candidate_construction_tokens},
            {"full_replay_candidate_source_tokens",
                full_replay_candidate_tokens},
            {"prefix_DAG_candidate_source_tokens",
                prefix_dag_candidate_tokens},
            {"avoided_vs_full_replay",
                full_replay_candidate_tokens -
                candidate_construction_tokens},
            {"avoided_vs_prefix_DAG",
                prefix_dag_candidate_tokens -
                candidate_construction_tokens},
            {"asymptotic_fresh_source_ratio",
                static_cast<double>(
                    neutral_g_tokens.size() + closure_tokens.size()) /
                static_cast<double>(expected_source_tokens)},
            {"open_F_root_logical_bytes", f_root.resident_bytes},
            {"open_F_root_backend_allocation_bytes",
                f_root.allocation_bytes},
            {"open_F_root_backing_id", hex64(f_root.backing_id)},
            {"open_F_restore_count", f_root_restore_count},
            {"neutral_F_restore_count", neutral_f_root_restore_count},
            {"constructed_final_root_restore_count",
                final_root_restore_count},
        }},
        {"carrier", {
            {"active_cache_backend_allocation_bytes",
                active_cache_backend_allocation_bytes},
            {"maximum_retained_root_backend_allocation_bytes",
                maximum_retained_root_backend_allocation_bytes},
            {"active_plus_retained_backend_allocation_bytes",
                active_cache_backend_allocation_bytes +
                maximum_retained_root_backend_allocation_bytes},
            {"F_recurrent_tensor_digest_before",
                hex64(f_recurrent_digest_before.value)},
            {"F_recurrent_tensor_digest_after",
                hex64(f_recurrent_digest_after.value)},
            {"complete_host_state_copy_retained", false},
            {"all_retained_roots_closed",
                llama_state_seq_get_device_root_count(ctx) == 0},
            {"active_recurrent_backing_stable",
                active_recurrent_backing_id(ctx) ==
                active_recurrent_backing_initial},
            {"active_attention_backing_stable",
                active_attention_backing_id(ctx) ==
                active_attention_backing_initial},
        }},
        {"resource_accounting", {
            {"all_route_source_decode_tokens", source_decode_tokens_all},
            {"candidate_suffix_decode_tokens",
                candidate_suffix_decode_tokens},
            {"reference_full_decode_tokens",
                reference_full_decode_tokens},
            {"G_only_suffix_decode_tokens",
                g_only_suffix_decode_tokens},
            {"F_only_suffix_decode_tokens",
                f_only_suffix_decode_tokens},
            {"query_decode_tokens", query_decode_tokens},
            {"all_route_input_tokens",
                source_decode_tokens_all + query_decode_tokens},
            {"root_save_device_copy_bytes", root_save_device_copy_bytes},
            {"F_root_restore_device_copy_bytes",
                f_root_restore_device_copy_bytes},
            {"neutral_F_root_restore_device_copy_bytes",
                neutral_f_root_restore_device_copy_bytes},
            {"final_root_restore_device_copy_bytes",
                final_root_restore_device_copy_bytes},
            {"F_digest_d2h_bytes",
                f_recurrent_digest_before.transferred_bytes +
                f_recurrent_digest_after.transferred_bytes},
            {"F_digest_peak_host_work_bytes", std::max(
                f_recurrent_digest_before.peak_host_work_bytes,
                f_recurrent_digest_after.peak_host_work_bytes)},
            {"cleared_prefix_root_bytes", cleared_prefix_root_bytes},
            {"cleared_final_root_bytes", cleared_final_root_bytes},
            {"cleared_F_root_bytes", cleared_f_root_bytes},
            {"cleared_neutral_F_root_bytes",
                cleared_neutral_f_root_bytes},
        }},
        {"records", records},
        {"verdict", accepted ? "accept" : "reject"},
        {"claim_ceiling", spec.at("claim_ceiling")},
    };
}

static json run_prefix_dag_attention_construction(
        llama_context * ctx,
        const llama_vocab * vocab,
        const std::vector<llama_token> & candidates,
        const json & spec,
        uint64_t active_recurrent_backing_initial,
        uint64_t active_attention_backing_initial) {
    const uint32_t actual_context_size = llama_n_ctx(ctx);
    if (actual_context_size != spec.at("expected_context_size").get<uint32_t>()) {
        throw std::runtime_error(
            "prefix-DAG context mismatch: " +
            std::to_string(actual_context_size));
    }
    const size_t expected_source_tokens =
        spec.at("expected_source_tokens").get<size_t>();
    const auto & tasks = spec.at("tasks");
    if (!tasks.is_array() || tasks.empty()) {
        throw std::runtime_error("prefix-DAG spec has no tasks");
    }

    for (const auto & task : tasks) {
        for (const char * arm : {"F_only", "G_only", "joint"}) {
            if (tokenize_source(vocab, task.at("sources").at(arm)).size() !=
                expected_source_tokens) {
                throw std::runtime_error(
                    "prefix-DAG source token mismatch for " +
                    task.at("id").get<std::string>() + ":" + arm);
            }
        }
    }
    if (tokenize_source(vocab, spec.at("scaffold_source")).size() !=
        expected_source_tokens) {
        throw std::runtime_error("prefix-DAG scaffold token mismatch");
    }

    const auto prefix_tokens = prepare_source_prefix(
        ctx, vocab, tasks.at(0).at("sources").at("joint"));
    if (prefix_tokens.empty() ||
        prefix_tokens.size() >= expected_source_tokens) {
        throw std::runtime_error("prefix-DAG common prefix has invalid length");
    }
    for (const auto & task : tasks) {
        for (const char * arm : {"F_only", "G_only", "joint"}) {
            const auto tokens = tokenize_piece(
                vocab,
                task.at("sources").at(arm).at("prefix").get<std::string>(),
                true, true);
            if (tokens != prefix_tokens) {
                throw std::runtime_error(
                    "prefix-DAG source prefixes are not token-identical");
            }
        }
    }
    auto prefix_root = save_root(
        ctx, "common-prefix:full-hybrid", 8000, FULL_DEVICE_FLAGS,
        prefix_tokens.size());

    const auto scaffold_tokens =
        prepare_source(ctx, vocab, spec.at("scaffold_source"));
    auto scaffold_root = save_root(
        ctx, "prefix-DAG:F0_G0:recurrent-scaffold", 8001,
        RECURRENT_DEVICE_FLAGS, scaffold_tokens.size());
    const auto scaffold_hash_before = hash_recurrent_state_streamed(ctx);
    const size_t active_cache_backend_allocation_bytes =
        active_hybrid_backend_allocation_bytes(ctx);

    const llama_seq_id attention_key = 8002;
    bool attention_root_initialized = false;
    uint64_t fixed_attention_backing_id = 0;
    size_t fixed_attention_allocation_bytes = 0;
    size_t fixed_attention_logical_bytes = 0;
    size_t attention_root_write_count = 0;
    size_t prefix_restore_count = 0;
    size_t scaffold_restore_count = 0;
    size_t attention_restore_count = 0;
    size_t reference_source_tokens = 0;
    size_t prefix_candidate_source_tokens = prefix_tokens.size();
    size_t prefix_candidate_suffix_tokens = 0;
    size_t root_save_device_copy_bytes =
        prefix_root.gpu_bytes + scaffold_root.gpu_bytes;
    size_t prefix_restore_device_copy_bytes = 0;
    size_t scaffold_restore_device_copy_bytes = 0;
    size_t attention_restore_device_copy_bytes = 0;
    json records = json::array();
    json construction_records = json::array();
    json task_summary = json::object();
    size_t full_logit_hash_matches = 0;
    size_t boundary_matches_total = 0;
    size_t comparisons = 0;
    double maximum_candidate_logit_absolute_difference = 0.0;
    bool fixed_backing_stable = true;

    for (const auto & task : tasks) {
        const std::string id = task.at("id");
        json arm_summary = json::object();
        for (const char * arm : {"F_only", "G_only", "joint"}) {
            const auto & source = task.at("sources").at(arm);
            const auto & queries = task.at("queries");

            const auto full_source_tokens = prepare_source(ctx, vocab, source);
            reference_source_tokens += full_source_tokens.size();
            auto reference_root = save_root(
                ctx, id + ":" + arm + ":full-replay-attention",
                attention_key, ATTENTION_DEVICE_FLAGS,
                full_source_tokens.size());
            ++attention_root_write_count;
            root_save_device_copy_bytes += reference_root.gpu_bytes;
            if (!attention_root_initialized) {
                attention_root_initialized = true;
                fixed_attention_backing_id = reference_root.backing_id;
                fixed_attention_allocation_bytes =
                    reference_root.allocation_bytes;
                fixed_attention_logical_bytes = reference_root.resident_bytes;
            } else {
                fixed_backing_stable =
                    fixed_backing_stable &&
                    reference_root.backing_id == fixed_attention_backing_id &&
                    reference_root.allocation_bytes ==
                        fixed_attention_allocation_bytes &&
                    reference_root.resident_bytes ==
                        fixed_attention_logical_bytes;
            }

            std::vector<boundary_result> reference_results;
            for (const auto & query : queries) {
                restore_root(ctx, scaffold_root);
                ++scaffold_restore_count;
                scaffold_restore_device_copy_bytes += scaffold_root.gpu_bytes;
                restore_attention_root(ctx, reference_root);
                ++attention_restore_count;
                attention_restore_device_copy_bytes += reference_root.gpu_bytes;
                auto boundary = decode_query(
                    ctx, vocab, candidates, "full-source-replay",
                    id + ":" + arm, query, full_source_tokens.size(),
                    reference_root.backing_id, reference_root.gpu_bytes);
                records.push_back(boundary.record);
                reference_results.push_back(std::move(boundary));
            }

            restore_root(ctx, prefix_root);
            ++prefix_restore_count;
            prefix_restore_device_copy_bytes += prefix_root.gpu_bytes;
            const size_t suffix_tokens = decode_source_suffix(
                ctx, vocab, source, prefix_tokens.size());
            prefix_candidate_suffix_tokens += suffix_tokens;
            if (prefix_tokens.size() + suffix_tokens !=
                expected_source_tokens) {
                throw std::runtime_error(
                    "prefix-DAG constructed source length changed");
            }
            auto candidate_root = save_root(
                ctx, id + ":" + arm + ":prefix-DAG-attention",
                attention_key, ATTENTION_DEVICE_FLAGS,
                expected_source_tokens);
            ++attention_root_write_count;
            root_save_device_copy_bytes += candidate_root.gpu_bytes;
            fixed_backing_stable =
                fixed_backing_stable &&
                candidate_root.backing_id == fixed_attention_backing_id &&
                candidate_root.allocation_bytes ==
                    fixed_attention_allocation_bytes &&
                candidate_root.resident_bytes ==
                    fixed_attention_logical_bytes;

            std::vector<boundary_result> candidate_results;
            for (const auto & query : queries) {
                restore_root(ctx, scaffold_root);
                ++scaffold_restore_count;
                scaffold_restore_device_copy_bytes += scaffold_root.gpu_bytes;
                restore_attention_root(ctx, candidate_root);
                ++attention_restore_count;
                attention_restore_device_copy_bytes += candidate_root.gpu_bytes;
                auto boundary = decode_query(
                    ctx, vocab, candidates, "common-prefix-DAG",
                    id + ":" + arm, query, expected_source_tokens,
                    candidate_root.backing_id, candidate_root.gpu_bytes);
                records.push_back(boundary.record);
                candidate_results.push_back(std::move(boundary));
            }

            size_t arm_hash_matches = 0;
            size_t arm_boundary_matches = 0;
            double arm_maximum_difference = 0.0;
            for (size_t i = 0; i < queries.size(); ++i) {
                const auto & reference = reference_results.at(i);
                const auto & candidate = candidate_results.at(i);
                arm_hash_matches +=
                    reference.full_logits_fnv1a64 ==
                    candidate.full_logits_fnv1a64;
                arm_boundary_matches +=
                    reference.argmax == candidate.argmax;
                for (size_t c = 0; c < reference.candidate_logits.size(); ++c) {
                    arm_maximum_difference = std::max(
                        arm_maximum_difference,
                        std::abs(
                            static_cast<double>(
                                reference.candidate_logits.at(c)) -
                            static_cast<double>(
                                candidate.candidate_logits.at(c))));
                }
            }
            full_logit_hash_matches += arm_hash_matches;
            boundary_matches_total += arm_boundary_matches;
            comparisons += queries.size();
            maximum_candidate_logit_absolute_difference = std::max(
                maximum_candidate_logit_absolute_difference,
                arm_maximum_difference);
            arm_summary[arm] = {
                {"full_logit_hash_matches", arm_hash_matches},
                {"boundary_matches", arm_boundary_matches},
                {"comparisons", queries.size()},
                {"maximum_candidate_logit_absolute_difference",
                    arm_maximum_difference},
            };
            construction_records.push_back({
                {"task_id", id},
                {"arm", arm},
                {"prefix_tokens", prefix_tokens.size()},
                {"suffix_tokens", suffix_tokens},
                {"full_source_tokens", full_source_tokens.size()},
                {"fixed_attention_backing_id",
                    hex64(candidate_root.backing_id)},
            });
        }
        task_summary[id] = arm_summary;
    }

    restore_root(ctx, scaffold_root);
    ++scaffold_restore_count;
    scaffold_restore_device_copy_bytes += scaffold_root.gpu_bytes;
    const auto scaffold_hash_after = hash_recurrent_state_streamed(ctx);
    const bool scaffold_exact =
        scaffold_hash_before.value == scaffold_hash_after.value &&
        scaffold_hash_before.transferred_bytes ==
            scaffold_hash_after.transferred_bytes;
    const auto & acceptance = spec.at("acceptance_law");
    const size_t expected_comparisons =
        acceptance.at("comparisons").get<size_t>();
    const size_t expected_hash_matches =
        acceptance.at("full_logit_hash_matches").get<size_t>();
    const size_t expected_boundary_matches =
        acceptance.at("boundary_matches").get<size_t>();
    const double maximum_allowed_difference =
        acceptance.at(
            "maximum_candidate_logit_absolute_difference").get<double>();
    const size_t minimum_avoided_source_tokens =
        acceptance.at("source_tokens_avoided_minimum").get<size_t>();
    const size_t avoided_source_tokens =
        reference_source_tokens -
        (prefix_candidate_source_tokens +
         prefix_candidate_suffix_tokens);
    const bool accepted =
        comparisons == expected_comparisons &&
        full_logit_hash_matches == expected_hash_matches &&
        boundary_matches_total == expected_boundary_matches &&
        maximum_candidate_logit_absolute_difference <=
            maximum_allowed_difference &&
        fixed_backing_stable ==
            acceptance.at("fixed_attention_backing_stable").get<bool>() &&
        scaffold_exact &&
        avoided_source_tokens >= minimum_avoided_source_tokens;

    llama_memory_clear(llama_get_memory(ctx), true);
    const size_t cleared_attention_bytes =
        llama_state_seq_clear_device_data(ctx, attention_key);
    const size_t cleared_scaffold_bytes =
        llama_state_seq_clear_device_data(ctx, scaffold_root.key);
    const size_t cleared_prefix_bytes =
        llama_state_seq_clear_device_data(ctx, prefix_root.key);
    llama_synchronize(ctx);
    if (llama_state_seq_get_device_root_count(ctx) != 0 ||
        active_recurrent_backing_id(ctx) != active_recurrent_backing_initial ||
        active_attention_backing_id(ctx) != active_attention_backing_initial) {
        throw std::runtime_error("prefix-DAG close invariant failed");
    }

    const size_t maximum_retained_root_backend_allocation_bytes =
        prefix_root.allocation_bytes +
        scaffold_root.allocation_bytes +
        fixed_attention_allocation_bytes;
    return {
        {"schema_version", 1},
        {"mechanism", "COMMON_PREFIX_DAG_FIXED_ATTENTION_ALLOCATION"},
        {"spec_id", spec.at("id")},
        {"model_arch", "qwen35moe"},
        {"configuration", {
            {"context_size", actual_context_size},
            {"source_tokens", expected_source_tokens},
            {"prefix_tokens", prefix_tokens.size()},
            {"task_count", tasks.size()},
            {"arms_per_task", 3},
            {"queries_per_arm", tasks.at(0).at("queries").size()},
            {"restoration_class", "SNAPSHOT_RELOAD"},
        }},
        {"summary", {
            {"full_logit_hash_matches", full_logit_hash_matches},
            {"boundary_matches", boundary_matches_total},
            {"comparisons", comparisons},
            {"maximum_candidate_logit_absolute_difference",
                maximum_candidate_logit_absolute_difference},
            {"expected_comparisons", expected_comparisons},
            {"expected_full_logit_hash_matches", expected_hash_matches},
            {"expected_boundary_matches", expected_boundary_matches},
            {"maximum_allowed_candidate_logit_absolute_difference",
                maximum_allowed_difference},
            {"fixed_attention_backing_stable", fixed_backing_stable},
            {"scaffold_content_exact", scaffold_exact},
            {"accepted", accepted},
        }},
        {"task_summary", task_summary},
        {"construction", {
            {"full_replay_source_tokens", reference_source_tokens},
            {"prefix_candidate_one_time_tokens",
                prefix_candidate_source_tokens},
            {"prefix_candidate_suffix_tokens",
                prefix_candidate_suffix_tokens},
            {"prefix_candidate_source_tokens_total",
                prefix_candidate_source_tokens +
                prefix_candidate_suffix_tokens},
            {"avoided_source_tokens",
                avoided_source_tokens},
            {"attention_root_write_count", attention_root_write_count},
            {"fixed_attention_root_logical_bytes",
                fixed_attention_logical_bytes},
            {"fixed_attention_root_backend_allocation_bytes",
                fixed_attention_allocation_bytes},
            {"fixed_attention_root_backing_id",
                hex64(fixed_attention_backing_id)},
            {"prefix_root_logical_bytes", prefix_root.resident_bytes},
            {"prefix_root_backend_allocation_bytes",
                prefix_root.allocation_bytes},
            {"prefix_restore_count", prefix_restore_count},
        }},
        {"carrier", {
            {"scaffold", {
                {"logical_tensor_bytes", scaffold_root.resident_bytes},
                {"backend_allocation_bytes", scaffold_root.allocation_bytes},
                {"root_backing_id", hex64(scaffold_root.backing_id)},
                {"restore_count", scaffold_restore_count},
                {"content_hash_before", hex64(scaffold_hash_before.value)},
                {"content_hash_after", hex64(scaffold_hash_after.value)},
            }},
            {"attention_restore_count", attention_restore_count},
            {"active_cache_backend_allocation_bytes",
                active_cache_backend_allocation_bytes},
            {"maximum_retained_root_backend_allocation_bytes",
                maximum_retained_root_backend_allocation_bytes},
            {"active_plus_retained_backend_allocation_bytes",
                active_cache_backend_allocation_bytes +
                maximum_retained_root_backend_allocation_bytes},
            {"complete_host_state_copy_retained", false},
            {"all_retained_roots_closed",
                llama_state_seq_get_device_root_count(ctx) == 0},
            {"active_recurrent_backing_stable",
                active_recurrent_backing_id(ctx) ==
                active_recurrent_backing_initial},
            {"active_attention_backing_stable",
                active_attention_backing_id(ctx) ==
                active_attention_backing_initial},
        }},
        {"resource_accounting", {
            {"root_save_device_copy_bytes", root_save_device_copy_bytes},
            {"prefix_restore_device_copy_bytes",
                prefix_restore_device_copy_bytes},
            {"scaffold_restore_device_copy_bytes",
                scaffold_restore_device_copy_bytes},
            {"attention_restore_device_copy_bytes",
                attention_restore_device_copy_bytes},
            {"scaffold_hash_d2h_bytes",
                scaffold_hash_before.transferred_bytes +
                scaffold_hash_after.transferred_bytes},
            {"cleared_attention_bytes", cleared_attention_bytes},
            {"cleared_scaffold_bytes", cleared_scaffold_bytes},
            {"cleared_prefix_bytes", cleared_prefix_bytes},
        }},
        {"construction_records", construction_records},
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
    if (spec.value("require_unified_kv", false)) {
        params.kv_unified = true;
    }

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

        if (spec.value("prefix_dag_attention_construction", false)) {
            const json result = run_prefix_dag_attention_construction(
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

        if (spec.value("affine_attention_composition", false) ||
            spec.value("position_splice_attention_composition", false)) {
            const json result = run_attention_operator_composition(
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

        if (spec.value("open_f_prefix_nonlinear_composition", false)) {
            const json result = run_open_f_prefix_nonlinear_composition(
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

        if (spec.value("active_f_sequence_branching", false)) {
            const json result = run_active_f_sequence_branching(
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

        if (spec.value(
                "multi_context_subspace_operator_transfer",
                false)) {
            const auto load_panel =
                    [](const std::string & path) {
                std::ifstream stream(path);
                if (!stream) {
                    throw std::runtime_error(
                        "failed to open multi-context panel: " +
                        path);
                }
                json panel;
                stream >> panel;
                return panel;
            };
            const auto calibration_paths =
                spec.at("calibration_panel_paths")
                    .get<std::vector<std::string>>();
            if (calibration_paths.size() < 2) {
                throw std::runtime_error(
                    "multi-context action requires at least two "
                    "calibration contexts");
            }
            const size_t maximum_rank =
                spec.at("maximum_rank_per_tensor")
                    .get<size_t>();
            if (maximum_rank == 0) {
                throw std::runtime_error(
                    "multi-context action rank must be nonzero");
            }
            json construction_results = json::array();
            json replay_results = json::array();
            llama_kv_cache::value_subspace_operator
                aggregate_operator;
            uint64_t fixed_operator_bytes = 0;
            uint64_t maximum_merge_scratch_bytes = 0;
            bool construction_capability_passed = true;
            size_t all_route_input_tokens = 0;
            for (size_t context_index = 0;
                 context_index < calibration_paths.size();
                 ++context_index) {
                const json panel =
                    load_panel(calibration_paths[context_index]);
                llama_kv_cache::value_subspace_operator
                    context_operator;
                const json construction =
                    run_sparse_g_label_refresh(
                        ctx,
                        vocab,
                        candidates,
                        panel,
                        active_backing_initial,
                        active_attention_backing_initial,
                        &context_operator,
                        true);
                construction_capability_passed =
                    construction_capability_passed &&
                    construction.at("summary")
                        .at("route_summary")
                        .at("exact_full_state")
                        .at("correct").get<size_t>() ==
                        panel.at("acceptance_law")
                            .at("primary_correct")
                            .get<size_t>();
                all_route_input_tokens +=
                    construction.at("resource_accounting")
                        .at("all_route_input_tokens")
                        .get<size_t>();
                construction_results.push_back(construction);
                if (context_index == 0) {
                    aggregate_operator =
                        std::move(context_operator);
                    maximum_merge_scratch_bytes = std::max(
                        maximum_merge_scratch_bytes,
                        make_value_subspace_operator_explicit_affine(
                            aggregate_operator));
                    fixed_operator_bytes =
                        aggregate_operator.vector_backing_bytes;
                    if (aggregate_operator.maximum_layer_rank >
                        maximum_rank) {
                        throw std::runtime_error(
                            "anchor operator exceeds fixed rank");
                    }
                } else {
                    if (context_operator.maximum_layer_rank >
                        maximum_rank) {
                        throw std::runtime_error(
                            "context operator exceeds fixed rank");
                    }
                    maximum_merge_scratch_bytes = std::max(
                        maximum_merge_scratch_bytes,
                        merge_value_subspace_context_action(
                            aggregate_operator,
                            context_operator));
                    if (aggregate_operator.vector_backing_bytes !=
                        fixed_operator_bytes ||
                        aggregate_operator.maximum_layer_rank >
                            maximum_rank) {
                        throw std::runtime_error(
                            "multi-context operator capacity grew");
                    }
                }
            }
            if (aggregate_operator.training_contexts !=
                    calibration_paths.size() ||
                aggregate_operator.maximum_layer_rank >
                    maximum_rank ||
                aggregate_operator.vector_backing_bytes !=
                    fixed_operator_bytes ||
                !aggregate_operator.explicit_affine) {
                throw std::runtime_error(
                    "multi-context operator final invariant failed");
            }
            const uint64_t operator_hash_after_training =
                hash_value_subspace_operator(
                    aggregate_operator);
            bool replay_accepted = true;
            for (const auto & path : calibration_paths) {
                const json panel = load_panel(path);
                const json replay =
                    run_sparse_g_label_refresh(
                        ctx,
                        vocab,
                        candidates,
                        panel,
                        active_backing_initial,
                        active_attention_backing_initial,
                        &aggregate_operator,
                        false);
                replay_accepted =
                    replay_accepted &&
                    replay.at("summary")
                        .at("accepted").get<bool>();
                all_route_input_tokens +=
                    replay.at("resource_accounting")
                        .at("all_route_input_tokens")
                        .get<size_t>();
                replay_results.push_back(replay);
            }
            const std::string transfer_path =
                spec.at("transfer_panel_path");
            const json transfer_spec =
                load_panel(transfer_path);
            const json transfer_result =
                run_sparse_g_label_refresh(
                    ctx,
                    vocab,
                    candidates,
                    transfer_spec,
                    active_backing_initial,
                    active_attention_backing_initial,
                    &aggregate_operator,
                    false);
            all_route_input_tokens +=
                transfer_result.at("resource_accounting")
                    .at("all_route_input_tokens")
                    .get<size_t>();
            const uint64_t operator_hash_after_evaluation =
                hash_value_subspace_operator(
                    aggregate_operator);
            const bool transfer_accepted =
                transfer_result.at("summary")
                    .at("accepted").get<bool>();
            const bool fixed_capacity =
                aggregate_operator.vector_backing_bytes ==
                    fixed_operator_bytes &&
                aggregate_operator.maximum_layer_rank <=
                    maximum_rank;
            const bool operator_unchanged =
                operator_hash_after_training ==
                operator_hash_after_evaluation;
            const bool accepted =
                construction_capability_passed &&
                replay_accepted &&
                transfer_accepted &&
                fixed_capacity &&
                operator_unchanged;
            const json result = {
                {"schema_version", 1},
                {"mechanism",
                    "FIXED_CAPACITY_MULTI_CONTEXT_COMPLETE_ATTENTION_ACTION"},
                {"spec_id", spec.at("id")},
                {"experiment_id", spec.at("experiment_id")},
                {"calibration_panel_paths",
                    calibration_paths},
                {"transfer_panel_path", transfer_path},
                {"operator", {
                    {"training_contexts",
                        aggregate_operator.training_contexts},
                    {"calibration_samples",
                        aggregate_operator.calibration_samples},
                    {"layers",
                        aggregate_operator.layers.size()},
                    {"logical_bytes",
                        aggregate_operator.logical_bytes},
                    {"vector_backing_bytes",
                        aggregate_operator.vector_backing_bytes},
                    {"fixed_operator_bytes",
                        fixed_operator_bytes},
                    {"total_rank",
                        aggregate_operator.total_rank},
                    {"maximum_layer_rank",
                        aggregate_operator.maximum_layer_rank},
                    {"maximum_rank_gate", maximum_rank},
                    {"explicit_affine",
                        aggregate_operator.explicit_affine},
                    {"maximum_merge_scratch_bytes",
                        maximum_merge_scratch_bytes},
                    {"hash_after_training",
                        hex64(operator_hash_after_training)},
                    {"hash_after_evaluation",
                        hex64(operator_hash_after_evaluation)},
                    {"unchanged_during_evaluation",
                        operator_unchanged},
                    {"fixed_capacity", fixed_capacity},
                }},
                {"construction_capability_passed",
                    construction_capability_passed},
                {"training_replay_accepted",
                    replay_accepted},
                {"transfer_accepted",
                    transfer_accepted},
                {"all_route_input_tokens",
                    all_route_input_tokens},
                {"construction_results",
                    construction_results},
                {"training_replay_results",
                    replay_results},
                {"transfer_result", transfer_result},
                {"summary", {
                    {"accepted", accepted},
                    {"fixed_capacity", fixed_capacity},
                    {"operator_unchanged",
                        operator_unchanged},
                    {"construction_capability_passed",
                        construction_capability_passed},
                    {"training_replay_accepted",
                        replay_accepted},
                    {"transfer_accepted",
                        transfer_accepted},
                }},
                {"verdict", accepted ? "accept" : "reject"},
                {"claim_ceiling", spec.at("claim_ceiling")},
            };
            std::ofstream result_stream(params.out_file);
            result_stream << result.dump(2) << '\n';
            result_stream.close();
            LOG_INF(
                "wrote %s\n",
                params.out_file.c_str());
            llama_backend_free();
            return 0;
        }

        if (spec.value("subspace_operator_transfer", false)) {
            const auto load_panel =
                    [](const std::string & path) {
                std::ifstream stream(path);
                if (!stream) {
                    throw std::runtime_error(
                        "failed to open subspace panel: " + path);
                }
                json panel;
                stream >> panel;
                return panel;
            };
            const std::string calibration_path =
                spec.at("calibration_panel_path");
            const std::string transfer_path =
                spec.at("transfer_panel_path");
            const json calibration_spec =
                load_panel(calibration_path);
            const json transfer_spec =
                load_panel(transfer_path);
            llama_kv_cache::value_subspace_operator
                value_operator;
            const json calibration_result =
                run_sparse_g_label_refresh(
                    ctx,
                    vocab,
                    candidates,
                    calibration_spec,
                    active_backing_initial,
                    active_attention_backing_initial,
                    &value_operator,
                    true);
            const uint64_t operator_hash_before =
                hash_value_subspace_operator(value_operator);
            const json transfer_result =
                run_sparse_g_label_refresh(
                    ctx,
                    vocab,
                    candidates,
                    transfer_spec,
                    active_backing_initial,
                    active_attention_backing_initial,
                    &value_operator,
                    false);
            const uint64_t operator_hash_after =
                hash_value_subspace_operator(value_operator);
            const bool calibration_accepted =
                calibration_result.at("summary")
                    .at("accepted").get<bool>();
            const bool transfer_accepted =
                transfer_result.at("summary")
                    .at("accepted").get<bool>();
            const bool accepted =
                calibration_accepted &&
                transfer_accepted &&
                operator_hash_before == operator_hash_after;
            const bool includes_keys =
                calibration_spec.value(
                    "subspace_include_keys", false);
            const json result = {
                {"schema_version", 1},
                {"mechanism", includes_keys
                    ? "PROSPECTIVE_TRANSFERRED_STATE_CONDITIONED_LOW_RANK_KEY_VALUE_ACTION"
                    : "PROSPECTIVE_TRANSFERRED_STATE_CONDITIONED_LOW_RANK_VALUE_ACTION"},
                {"spec_id", spec.at("id")},
                {"experiment_id", spec.at("experiment_id")},
                {"calibration_panel_path", calibration_path},
                {"transfer_panel_path", transfer_path},
                {"operator", {
                    {"calibration_samples",
                        value_operator.calibration_samples},
                    {"layers", value_operator.layers.size()},
                    {"logical_bytes",
                        value_operator.logical_bytes},
                    {"vector_backing_bytes",
                        value_operator.vector_backing_bytes},
                    {"total_rank", value_operator.total_rank},
                    {"maximum_layer_rank",
                        value_operator.maximum_layer_rank},
                    {"calibration_max_abs_error",
                        value_operator.calibration_max_abs_error},
                    {"subspace_closure_max_abs_error",
                        value_operator.subspace_closure_max_abs_error},
                    {"hash_before",
                        hex64(operator_hash_before)},
                    {"hash_after",
                        hex64(operator_hash_after)},
                    {"unchanged_during_transfer",
                        operator_hash_before ==
                            operator_hash_after},
                }},
                {"summary", {
                    {"calibration_accepted",
                        calibration_accepted},
                    {"transfer_accepted",
                        transfer_accepted},
                    {"accepted", accepted},
                }},
                {"calibration_panel", calibration_result},
                {"transfer_panel", transfer_result},
                {"verdict", accepted ? "accept" : "reject"},
                {"claim_ceiling", spec.at("claim_ceiling")},
            };
            std::ofstream result_stream(params.out_file);
            result_stream << result.dump(2) << '\n';
            result_stream.close();
            LOG_INF("wrote %s\n", params.out_file.c_str());
            llama_backend_free();
            return 0;
        }

        if (spec.value("sparse_g_label_refresh", false)) {
            const json result = run_sparse_g_label_refresh(
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

        if (spec.value("g_forward_state_partition", false)) {
            const json result = run_g_forward_state_partition(
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

        if (spec.value("physical_attention_capability_panel", false)) {
            const json result = run_physical_attention_capability_panel(
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

        if (spec.value("full_hybrid_capability_panel", false)) {
            const json result = run_full_hybrid_capability_panel(
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

        if (spec.value("full_hybrid_capability_control", false)) {
            const json result = run_full_hybrid_capability_control(
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
