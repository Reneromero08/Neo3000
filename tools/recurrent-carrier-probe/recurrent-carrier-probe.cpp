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

static llama_memory_hybrid * require_hybrid_memory(llama_context * ctx);

constexpr llama_state_seq_flags RECURRENT_DEVICE_FLAGS =
    LLAMA_STATE_SEQ_FLAGS_PARTIAL_ONLY | LLAMA_STATE_SEQ_FLAGS_ON_DEVICE;
constexpr llama_state_seq_flags FULL_DEVICE_FLAGS =
    LLAMA_STATE_SEQ_FLAGS_ON_DEVICE;
constexpr llama_state_seq_flags ATTENTION_DEVICE_FLAGS =
    LLAMA_STATE_SEQ_FLAGS_ATTENTION_ONLY | LLAMA_STATE_SEQ_FLAGS_ON_DEVICE;

struct boundary_result {
    json record;
    std::vector<float> candidate_logits;
    std::vector<float> embedding;
    std::vector<float> layer_embedding;
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

struct model_weight_value_operator_build {
    llama_kv_cache::value_subspace_operator value_operator;
    std::vector<llama_token> semantic_tokens;
    std::map<uint32_t, std::vector<double>> code_norms;
    uint64_t source_tensor_read_bytes = 0;
    uint64_t peak_host_work_bytes = 0;
    uint64_t builder_bytes = 0;
    uint64_t operator_hash = 0;
};

struct semantic_carrier_training_sample {
    std::vector<float> embedding;
    std::vector<float> target_delta;
    uint32_t vault_ordinal = 0;
    std::array<float, 4> candidate_logits = {};
    uint32_t port_destination = 0;
    uint32_t next_output_ordinal = 0;
    uint32_t output_code_ordinal = 0;
};

struct semantic_carrier_writer_sample {
    std::vector<float> embedding;
    uint32_t output_ordinal = 0;
};

struct semantic_linear_decoder_build {
    std::vector<float> map;
    std::array<float, 4> bias = {};
    double ridge_lambda = 0.0;
    double training_max_abs_error = 0.0;
    size_t training_correct = 0;
    uint64_t peak_host_work_bytes = 0;
};

struct semantic_carrier_adapter_build {
    std::vector<float> query_map;
    std::array<float, 4> query_bias = {};
    std::vector<float> writer_map;
    std::array<float, 4> writer_bias = {};
    std::vector<float> output_map;
    std::vector<float> phase_binding_table;
    std::vector<float> phase_reader;
    std::vector<float> phase_generator;
    uint32_t phase_width = 0;
    uint64_t phase_seed = 0;
    uint64_t source_tensor_read_bytes = 0;
    uint64_t peak_host_work_bytes = 0;
    uint64_t logical_bytes = 0;
    uint64_t hash = 0;
    double ridge_lambda = 0.0;
    double training_max_abs_error = 0.0;
    double output_dual_max_abs_error = 0.0;
    double output_delta_training_max_abs_error = 0.0;
    double writer_ridge_lambda = 0.0;
    double writer_training_max_abs_error = 0.0;
    double coupled_output_gain = 0.0;
    double coupled_training_minimum_margin = 0.0;
    double phase_self_score_max_abs_error = 0.0;
    double phase_cross_score_max_abs = 0.0;
    double phase_rotation_four_step_max_abs_error = 0.0;
    double phase_training_retrieval_minimum_margin = 0.0;
    size_t training_correct = 0;
    size_t writer_training_correct = 0;
    size_t coupled_training_correct = 0;
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

static std::vector<float> read_model_tensor_row_f32(
        const ggml_tensor * tensor,
        int64_t row,
        uint64_t & transferred_bytes,
        uint64_t & peak_host_work_bytes) {
    if (!tensor ||
        !tensor->buffer ||
        row < 0 ||
        row >= tensor->ne[1] ||
        tensor->ne[2] != 1 ||
        tensor->ne[3] != 1) {
        throw std::runtime_error(
            "model semantic-code tensor row is unavailable");
    }
    const ggml_type_traits * traits =
        ggml_get_type_traits(tensor->type);
    if (!traits ||
        (tensor->type != GGML_TYPE_F32 && !traits->to_float) ||
        tensor->ne[0] <= 0 ||
        tensor->ne[0] % traits->blck_size != 0) {
        throw std::runtime_error(
            "model semantic-code tensor type cannot be decoded");
    }
    const size_t elements =
        static_cast<size_t>(tensor->ne[0]);
    const size_t row_bytes =
        ggml_row_size(tensor->type, tensor->ne[0]);
    if (tensor->nb[1] < row_bytes) {
        throw std::runtime_error(
            "model semantic-code tensor row stride is invalid");
    }
    std::vector<uint8_t> raw(row_bytes);
    std::vector<float> values(elements);
    ggml_backend_tensor_get(
        tensor,
        raw.data(),
        static_cast<size_t>(row) * tensor->nb[1],
        raw.size());
    if (tensor->type == GGML_TYPE_F32) {
        std::memcpy(
            values.data(),
            raw.data(),
            elements * sizeof(float));
    } else {
        traits->to_float(raw.data(), values.data(), elements);
    }
    transferred_bytes += raw.size();
    peak_host_work_bytes = std::max<uint64_t>(
        peak_host_work_bytes,
        raw.size() + values.size() * sizeof(float));
    return values;
}

static model_weight_value_operator_build
build_model_weight_value_operator(
        llama_context * ctx,
        const std::set<uint32_t> & layer_ids,
        const std::vector<llama_token> & semantic_tokens) {
    if (!ctx ||
        layer_ids.empty() ||
        semantic_tokens.size() != 4 ||
        std::set<llama_token>(
            semantic_tokens.begin(),
            semantic_tokens.end()).size() !=
            semantic_tokens.size()) {
        throw std::runtime_error(
            "weight-derived semantic operator geometry is invalid");
    }
    const llama_model & model = ctx->get_model();
    if (model.arch != LLM_ARCH_QWEN35MOE ||
        !model.tok_embd ||
        !model.loras.empty()) {
        throw std::runtime_error(
            "weight-derived semantic operator requires unadapted qwen35moe");
    }
    const size_t n_embd =
        static_cast<size_t>(model.hparams.n_embd);
    if (model.tok_embd->ne[0] !=
        static_cast<int64_t>(n_embd)) {
        throw std::runtime_error(
            "semantic token embedding width mismatch");
    }

    model_weight_value_operator_build result;
    result.semantic_tokens = semantic_tokens;
    std::vector<std::vector<float>> token_embeddings;
    token_embeddings.reserve(semantic_tokens.size());
    for (const llama_token token : semantic_tokens) {
        token_embeddings.push_back(
            read_model_tensor_row_f32(
                model.tok_embd,
                token,
                result.source_tensor_read_bytes,
                result.peak_host_work_bytes));
    }

    llama_kv_cache::value_subspace_builder builder;
    builder.layers.reserve(layer_ids.size());
    for (const uint32_t layer_id : layer_ids) {
        if (layer_id >= model.layers.size()) {
            throw std::runtime_error(
                "semantic operator layer is out of range");
        }
        const llama_layer & layer = model.layers[layer_id];
        if (!layer.attn_norm ||
            !layer.wv ||
            layer.wv_s ||
            layer.attn_norm->ne[0] !=
                static_cast<int64_t>(n_embd) ||
            layer.wv->ne[0] !=
                static_cast<int64_t>(n_embd) ||
            layer.wv->ne[1] <= 0 ||
            layer.wv->ne[2] != 1 ||
            layer.wv->ne[3] != 1) {
            throw std::runtime_error(
                "semantic operator layer weights are unsupported");
        }

        const auto norm_weight =
            read_model_tensor_row_f32(
                layer.attn_norm,
                0,
                result.source_tensor_read_bytes,
                result.peak_host_work_bytes);
        std::vector<std::vector<float>> normalized(
            semantic_tokens.size(),
            std::vector<float>(n_embd));
        for (size_t token_index = 0;
             token_index < semantic_tokens.size();
             ++token_index) {
            double mean_square = 0.0;
            for (const float value :
                 token_embeddings[token_index]) {
                mean_square +=
                    static_cast<double>(value) *
                    static_cast<double>(value);
            }
            mean_square /= static_cast<double>(n_embd);
            const double inverse_rms =
                1.0 /
                std::sqrt(
                    mean_square +
                    model.hparams.f_norm_rms_eps);
            for (size_t j = 0; j < n_embd; ++j) {
                normalized[token_index][j] =
                    static_cast<float>(
                        static_cast<double>(
                            token_embeddings[token_index][j]) *
                        inverse_rms *
                        static_cast<double>(norm_weight[j]));
            }
        }

        const size_t value_elements =
            static_cast<size_t>(layer.wv->ne[1]);
        std::vector<std::vector<float>> codes(
            semantic_tokens.size(),
            std::vector<float>(value_elements, 0.0f));
        for (size_t output_index = 0;
             output_index < value_elements;
             ++output_index) {
            const auto weights =
                read_model_tensor_row_f32(
                    layer.wv,
                    static_cast<int64_t>(output_index),
                    result.source_tensor_read_bytes,
                    result.peak_host_work_bytes);
            for (size_t token_index = 0;
                 token_index < semantic_tokens.size();
                 ++token_index) {
                double value = 0.0;
                for (size_t j = 0; j < n_embd; ++j) {
                    value +=
                        static_cast<double>(weights[j]) *
                        static_cast<double>(
                            normalized[token_index][j]);
                }
                codes[token_index][output_index] =
                    static_cast<float>(value);
            }
        }

        std::vector<double> norms;
        norms.reserve(codes.size());
        for (const auto & code : codes) {
            double norm_squared = 0.0;
            for (const float value : code) {
                norm_squared +=
                    static_cast<double>(value) *
                    static_cast<double>(value);
            }
            norms.push_back(std::sqrt(norm_squared));
        }
        result.code_norms[layer_id] = std::move(norms);

        llama_kv_cache::value_subspace_builder_layer item;
        item.layer_id = layer_id;
        item.key = false;
        item.samples = std::move(codes);
        item.present.assign(semantic_tokens.size(), true);
        builder.layers.push_back(std::move(item));
    }
    builder.sample_count = semantic_tokens.size();
    builder.vector_backing_bytes =
        sizeof(builder) +
        builder.layers.capacity() *
            sizeof(llama_kv_cache::value_subspace_builder_layer);
    for (const auto & item : builder.layers) {
        builder.vector_backing_bytes +=
            item.samples.capacity() *
                sizeof(std::vector<float>) +
            item.present.capacity() / 8 + 1;
        for (const auto & sample : item.samples) {
            builder.vector_backing_bytes +=
                sample.capacity() * sizeof(float);
        }
    }

    auto * attention =
        require_hybrid_memory(ctx)->get_mem_attn();
    llama_kv_cache::value_subspace_metrics metrics = {};
    if (!attention->finalize_value_subspace_operator(
            &builder,
            1,
            semantic_tokens.size(),
            &result.value_operator,
            &metrics)) {
        throw std::runtime_error(
            "weight-derived semantic operator construction failed");
    }
    result.builder_bytes = metrics.builder_bytes;
    result.peak_host_work_bytes = std::max<uint64_t>(
        result.peak_host_work_bytes,
        metrics.peak_host_work_bytes);
    result.operator_hash =
        hash_value_subspace_operator(result.value_operator);
    return result;
}

static std::vector<double> solve_dense_system(
        std::vector<double> matrix,
        std::vector<double> rhs,
        size_t dimension) {
    if (dimension == 0 ||
        matrix.size() != dimension * dimension ||
        rhs.size() != dimension) {
        throw std::runtime_error(
            "semantic carrier solve geometry is invalid");
    }
    for (size_t column = 0; column < dimension; ++column) {
        size_t pivot = column;
        double pivot_magnitude =
            std::abs(matrix[column * dimension + column]);
        for (size_t row = column + 1; row < dimension; ++row) {
            const double magnitude =
                std::abs(matrix[row * dimension + column]);
            if (magnitude > pivot_magnitude) {
                pivot = row;
                pivot_magnitude = magnitude;
            }
        }
        if (!std::isfinite(pivot_magnitude) ||
            pivot_magnitude <= 1e-12) {
            throw std::runtime_error(
                "semantic carrier solve is singular");
        }
        if (pivot != column) {
            for (size_t j = 0; j < dimension; ++j) {
                std::swap(
                    matrix[column * dimension + j],
                    matrix[pivot * dimension + j]);
            }
            std::swap(rhs[column], rhs[pivot]);
        }
        const double diagonal =
            matrix[column * dimension + column];
        for (size_t j = column; j < dimension; ++j) {
            matrix[column * dimension + j] /= diagonal;
        }
        rhs[column] /= diagonal;
        for (size_t row = 0; row < dimension; ++row) {
            if (row == column) {
                continue;
            }
            const double factor =
                matrix[row * dimension + column];
            if (factor == 0.0) {
                continue;
            }
            for (size_t j = column; j < dimension; ++j) {
                matrix[row * dimension + j] -=
                    factor *
                    matrix[column * dimension + j];
            }
            rhs[row] -= factor * rhs[column];
        }
    }
    return rhs;
}

static semantic_linear_decoder_build build_semantic_linear_decoder(
        const std::vector<std::vector<float>> & embeddings,
        const std::vector<uint32_t> & ordinals,
        double ridge_fraction) {
    if (embeddings.size() < 8 ||
        embeddings.size() != ordinals.size() ||
        embeddings.front().empty() ||
        !std::isfinite(ridge_fraction) ||
        ridge_fraction <= 0.0) {
        throw std::runtime_error(
            "semantic linear decoder training law is invalid");
    }
    const size_t n_samples = embeddings.size();
    const size_t n_embd = embeddings.front().size();
    std::array<size_t, 4> class_counts = {};
    for (size_t i = 0; i < n_samples; ++i) {
        if (embeddings[i].size() != n_embd ||
            ordinals[i] >= 4) {
            throw std::runtime_error(
                "semantic linear decoder sample is invalid");
        }
        ++class_counts[ordinals[i]];
    }
    if (*std::min_element(
            class_counts.begin(),
            class_counts.end()) == 0) {
        throw std::runtime_error(
            "semantic linear decoder classes are incomplete");
    }

    semantic_linear_decoder_build result;
    std::vector<double> feature_mean(n_embd, 0.0);
    std::array<double, 4> target_mean = {};
    const auto target = [](uint32_t output, uint32_t ordinal) {
        return output == ordinal ? 0.75 : -0.25;
    };
    for (size_t i = 0; i < n_samples; ++i) {
        for (size_t j = 0; j < n_embd; ++j) {
            feature_mean[j] +=
                static_cast<double>(embeddings[i][j]) /
                static_cast<double>(n_samples);
        }
        for (uint32_t output = 0; output < 4; ++output) {
            target_mean[output] +=
                target(output, ordinals[i]) /
                static_cast<double>(n_samples);
        }
    }

    std::vector<double> centered(n_samples * n_embd);
    for (size_t i = 0; i < n_samples; ++i) {
        for (size_t j = 0; j < n_embd; ++j) {
            centered[i * n_embd + j] =
                static_cast<double>(embeddings[i][j]) -
                feature_mean[j];
        }
    }
    std::vector<double> kernel(
        n_samples * n_samples,
        0.0);
    double trace = 0.0;
    for (size_t i = 0; i < n_samples; ++i) {
        for (size_t k = i; k < n_samples; ++k) {
            double value = 0.0;
            for (size_t j = 0; j < n_embd; ++j) {
                value +=
                    centered[i * n_embd + j] *
                    centered[k * n_embd + j];
            }
            kernel[i * n_samples + k] = value;
            kernel[k * n_samples + i] = value;
        }
        trace += kernel[i * n_samples + i];
    }
    result.ridge_lambda =
        ridge_fraction * trace /
        static_cast<double>(n_samples);
    if (!std::isfinite(result.ridge_lambda) ||
        result.ridge_lambda <= 0.0) {
        throw std::runtime_error(
            "semantic linear decoder ridge is invalid");
    }
    for (size_t i = 0; i < n_samples; ++i) {
        kernel[i * n_samples + i] +=
            result.ridge_lambda;
    }

    result.map.assign(4 * n_embd, 0.0f);
    for (uint32_t output = 0; output < 4; ++output) {
        std::vector<double> rhs(n_samples);
        for (size_t i = 0; i < n_samples; ++i) {
            rhs[i] =
                target(output, ordinals[i]) -
                target_mean[output];
        }
        const auto alpha =
            solve_dense_system(kernel, rhs, n_samples);
        for (size_t j = 0; j < n_embd; ++j) {
            double value = 0.0;
            for (size_t i = 0; i < n_samples; ++i) {
                value +=
                    centered[i * n_embd + j] *
                    alpha[i];
            }
            result.map[
                static_cast<size_t>(output) * n_embd + j] =
                static_cast<float>(value);
        }
        double bias = target_mean[output];
        for (size_t j = 0; j < n_embd; ++j) {
            bias -=
                static_cast<double>(
                    result.map[
                        static_cast<size_t>(output) *
                            n_embd + j]) *
                feature_mean[j];
        }
        result.bias[output] = static_cast<float>(bias);
    }

    for (size_t i = 0; i < n_samples; ++i) {
        std::array<double, 4> prediction = {};
        for (uint32_t output = 0; output < 4; ++output) {
            prediction[output] = result.bias[output];
            for (size_t j = 0; j < n_embd; ++j) {
                prediction[output] +=
                    static_cast<double>(
                        result.map[
                            static_cast<size_t>(output) *
                                n_embd + j]) *
                    static_cast<double>(embeddings[i][j]);
            }
            result.training_max_abs_error = std::max(
                result.training_max_abs_error,
                std::abs(
                    prediction[output] -
                    target(output, ordinals[i])));
        }
        result.training_correct +=
            static_cast<uint32_t>(
                std::distance(
                    prediction.begin(),
                    std::max_element(
                        prediction.begin(),
                        prediction.end()))) ==
            ordinals[i];
    }
    result.peak_host_work_bytes =
        (feature_mean.size() +
         centered.size() +
         kernel.size()) * sizeof(double) +
        result.map.size() * sizeof(float);
    return result;
}

static semantic_carrier_adapter_build
build_semantic_carrier_adapter(
        llama_context * ctx,
        const std::vector<llama_token> & candidates,
        const std::vector<semantic_carrier_training_sample> & samples,
        double ridge_fraction,
        double output_gain,
        bool layer_delta_mode) {
    if (!ctx ||
        candidates.size() != 4 ||
        samples.size() < 8 ||
        !std::isfinite(ridge_fraction) ||
        ridge_fraction <= 0.0 ||
        !std::isfinite(output_gain) ||
        output_gain <= 0.0) {
        throw std::runtime_error(
            "semantic carrier training law is invalid");
    }
    const llama_model & model = ctx->get_model();
    const size_t n_embd = model.hparams.n_embd_out();
    if (model.arch != LLM_ARCH_QWEN35MOE ||
        !model.output ||
        n_embd == 0) {
        throw std::runtime_error(
            "semantic carrier requires qwen35moe output geometry");
    }
    std::array<size_t, 4> class_counts = {};
    for (const auto & sample : samples) {
        if (sample.embedding.size() != n_embd ||
            sample.vault_ordinal >= 4) {
            throw std::runtime_error(
                "semantic carrier training sample is invalid");
        }
        ++class_counts[sample.vault_ordinal];
    }
    if (*std::min_element(
            class_counts.begin(),
            class_counts.end()) == 0) {
        throw std::runtime_error(
            "semantic carrier training classes are incomplete");
    }

    semantic_carrier_adapter_build result;
    const size_t n_samples = samples.size();
    const auto code_target =
            [&](uint32_t output, uint32_t ordinal) {
        if (layer_delta_mode) {
            return output == ordinal ? 1.0 : 0.0;
        }
        return output == ordinal ? 0.75 : -0.25;
    };
    std::vector<double> feature_mean(n_embd, 0.0);
    std::array<double, 4> target_mean = {};
    for (const auto & sample : samples) {
        for (size_t j = 0; j < n_embd; ++j) {
            feature_mean[j] +=
                static_cast<double>(sample.embedding[j]) /
                static_cast<double>(n_samples);
        }
        for (uint32_t output = 0; output < 4; ++output) {
            const double target =
                code_target(output, sample.vault_ordinal);
            target_mean[output] +=
                target / static_cast<double>(n_samples);
        }
    }

    std::vector<double> centered(
        n_samples * n_embd);
    for (size_t i = 0; i < n_samples; ++i) {
        for (size_t j = 0; j < n_embd; ++j) {
            centered[i * n_embd + j] =
                static_cast<double>(samples[i].embedding[j]) -
                feature_mean[j];
        }
    }
    std::vector<double> kernel(
        n_samples * n_samples,
        0.0);
    double kernel_trace = 0.0;
    for (size_t i = 0; i < n_samples; ++i) {
        for (size_t k = i; k < n_samples; ++k) {
            double value = 0.0;
            for (size_t j = 0; j < n_embd; ++j) {
                value +=
                    centered[i * n_embd + j] *
                    centered[k * n_embd + j];
            }
            kernel[i * n_samples + k] = value;
            kernel[k * n_samples + i] = value;
        }
        kernel_trace += kernel[i * n_samples + i];
    }
    result.ridge_lambda =
        ridge_fraction *
        kernel_trace /
        static_cast<double>(n_samples);
    if (!std::isfinite(result.ridge_lambda) ||
        result.ridge_lambda <= 0.0) {
        throw std::runtime_error(
            "semantic carrier ridge scale is invalid");
    }
    for (size_t i = 0; i < n_samples; ++i) {
        kernel[i * n_samples + i] += result.ridge_lambda;
    }

    result.query_map.assign(4 * n_embd, 0.0f);
    for (uint32_t output = 0; output < 4; ++output) {
        std::vector<double> rhs(n_samples);
        for (size_t i = 0; i < n_samples; ++i) {
            const double target =
                code_target(output, samples[i].vault_ordinal);
            rhs[i] = target - target_mean[output];
        }
        const std::vector<double> alpha =
            solve_dense_system(kernel, rhs, n_samples);
        for (size_t j = 0; j < n_embd; ++j) {
            double value = 0.0;
            for (size_t i = 0; i < n_samples; ++i) {
                value +=
                    centered[i * n_embd + j] *
                    alpha[i];
            }
            result.query_map[
                static_cast<size_t>(output) * n_embd + j] =
                static_cast<float>(value);
        }
        double bias = target_mean[output];
        for (size_t j = 0; j < n_embd; ++j) {
            bias -=
                static_cast<double>(
                    result.query_map[
                        static_cast<size_t>(output) *
                            n_embd +
                        j]) *
                feature_mean[j];
        }
        result.query_bias[output] =
            static_cast<float>(bias);
    }

    for (const auto & sample : samples) {
        std::array<double, 4> prediction = {};
        for (uint32_t output = 0; output < 4; ++output) {
            prediction[output] =
                result.query_bias[output];
            for (size_t j = 0; j < n_embd; ++j) {
                prediction[output] +=
                    static_cast<double>(
                        result.query_map[
                            static_cast<size_t>(output) *
                                n_embd +
                            j]) *
                    static_cast<double>(sample.embedding[j]);
            }
            const double target =
                code_target(output, sample.vault_ordinal);
            result.training_max_abs_error = std::max(
                result.training_max_abs_error,
                std::abs(prediction[output] - target));
        }
        result.training_correct +=
            static_cast<uint32_t>(
                std::distance(
                    prediction.begin(),
                    std::max_element(
                        prediction.begin(),
                        prediction.end()))) ==
            sample.vault_ordinal;
    }

    result.output_map.assign(n_embd * 4, 0.0f);
    if (layer_delta_mode) {
        std::array<size_t, 4> output_counts = {};
        for (const auto & sample : samples) {
            if (sample.target_delta.size() != n_embd) {
                throw std::runtime_error(
                    "semantic carrier layer delta is absent");
            }
            if (sample.output_code_ordinal >= 4) {
                throw std::runtime_error(
                    "semantic carrier output code is invalid");
            }
            ++output_counts[sample.output_code_ordinal];
            for (size_t j = 0; j < n_embd; ++j) {
                result.output_map[
                    j * 4 + sample.output_code_ordinal] +=
                    sample.target_delta[j];
            }
        }
        for (size_t code = 0; code < 4; ++code) {
            for (size_t j = 0; j < n_embd; ++j) {
                result.output_map[j * 4 + code] =
                    static_cast<float>(
                        static_cast<double>(
                            result.output_map[j * 4 + code]) /
                        static_cast<double>(output_counts[code]) *
                        output_gain);
            }
        }
        for (const auto & sample : samples) {
            for (size_t j = 0; j < n_embd; ++j) {
                const double predicted =
                    result.output_map[
                        j * 4 + sample.output_code_ordinal];
                const double expected =
                    static_cast<double>(
                        sample.target_delta[j]) *
                    output_gain;
                result.output_delta_training_max_abs_error =
                    std::max(
                        result.output_delta_training_max_abs_error,
                        std::abs(predicted - expected));
            }
        }
    } else {
        std::array<std::vector<float>, 4> output_rows;
        for (size_t token_index = 0;
             token_index < candidates.size();
             ++token_index) {
            output_rows[token_index] =
                read_model_tensor_row_f32(
                    model.output,
                    candidates[token_index],
                    result.source_tensor_read_bytes,
                    result.peak_host_work_bytes);
            if (output_rows[token_index].size() != n_embd) {
                throw std::runtime_error(
                    "semantic carrier output row width mismatch");
            }
        }
        std::vector<double> gram(16, 0.0);
        for (size_t i = 0; i < 4; ++i) {
            for (size_t k = 0; k < 4; ++k) {
                for (size_t j = 0; j < n_embd; ++j) {
                    gram[i * 4 + k] +=
                        static_cast<double>(output_rows[i][j]) *
                        static_cast<double>(output_rows[k][j]);
                }
            }
        }
        std::array<std::array<double, 4>, 4> gram_inverse = {};
        for (size_t column = 0; column < 4; ++column) {
            std::vector<double> rhs(4, 0.0);
            rhs[column] = 1.0;
            const auto solution =
                solve_dense_system(gram, rhs, 4);
            for (size_t row = 0; row < 4; ++row) {
                gram_inverse[row][column] = solution[row];
            }
        }
        for (size_t j = 0; j < n_embd; ++j) {
            for (size_t code = 0; code < 4; ++code) {
                double value = 0.0;
                for (size_t token = 0; token < 4; ++token) {
                    value +=
                        static_cast<double>(output_rows[token][j]) *
                        gram_inverse[token][code];
                }
                result.output_map[j * 4 + code] =
                    static_cast<float>(value * output_gain);
            }
        }
        for (size_t token = 0; token < 4; ++token) {
            for (size_t code = 0; code < 4; ++code) {
                double value = 0.0;
                for (size_t j = 0; j < n_embd; ++j) {
                    value +=
                        static_cast<double>(output_rows[token][j]) *
                        static_cast<double>(
                            result.output_map[j * 4 + code]);
                }
                const double expected =
                    token == code ? output_gain : 0.0;
                result.output_dual_max_abs_error = std::max(
                    result.output_dual_max_abs_error,
                    std::abs(value - expected));
            }
        }
    }

    result.logical_bytes =
        (result.query_map.size() +
         result.query_bias.size() +
         result.output_map.size() +
         16) *
        sizeof(float);
    uint64_t hash = UINT64_C(1469598103934665603);
    const auto mix = [&](const void * data, size_t bytes) {
        const auto * values =
            static_cast<const uint8_t *>(data);
        for (size_t i = 0; i < bytes; ++i) {
            hash ^= values[i];
            hash *= UINT64_C(1099511628211);
        }
    };
    mix(
        result.query_map.data(),
        result.query_map.size() * sizeof(float));
    mix(
        result.query_bias.data(),
        result.query_bias.size() * sizeof(float));
    mix(
        result.output_map.data(),
        result.output_map.size() * sizeof(float));
    result.hash = hash;
    result.peak_host_work_bytes = std::max<uint64_t>(
        result.peak_host_work_bytes,
        (feature_mean.size() +
         centered.size() +
         kernel.size() +
         result.query_map.size() +
         result.output_map.size()) *
            sizeof(double));
    return result;
}

static void complete_output_written_semantic_port(
        llama_context * ctx,
        const std::vector<llama_token> & candidates,
        const std::vector<semantic_carrier_training_sample> & query_samples,
        const std::vector<semantic_carrier_writer_sample> & writer_samples,
        double ridge_fraction,
        bool layer_delta_mode,
        double training_margin,
        double maximum_output_gain,
        semantic_carrier_adapter_build * adapter) {
    if (!ctx ||
        !adapter ||
        candidates.size() != 4 ||
        query_samples.size() < 8 ||
        query_samples.size() != writer_samples.size() ||
        query_samples.size() % 4 != 0 ||
        (!layer_delta_mode &&
         (!std::isfinite(training_margin) ||
          training_margin <= 0.0 ||
          !std::isfinite(maximum_output_gain) ||
          maximum_output_gain <= 0.0))) {
        throw std::runtime_error(
            "output-written semantic port training law is invalid");
    }
    const size_t n_embd =
        ctx->get_model().hparams.n_embd_out();
    std::vector<std::vector<float>> writer_embeddings;
    std::vector<uint32_t> writer_ordinals;
    writer_embeddings.reserve(writer_samples.size());
    writer_ordinals.reserve(writer_samples.size());
    for (const auto & sample : writer_samples) {
        writer_embeddings.push_back(sample.embedding);
        writer_ordinals.push_back(sample.output_ordinal);
    }
    auto writer = build_semantic_linear_decoder(
        writer_embeddings,
        writer_ordinals,
        ridge_fraction);
    adapter->writer_map = std::move(writer.map);
    adapter->writer_bias = writer.bias;
    adapter->writer_ridge_lambda = writer.ridge_lambda;
    adapter->writer_training_max_abs_error =
        writer.training_max_abs_error;
    adapter->writer_training_correct =
        writer.training_correct;
    adapter->peak_host_work_bytes = std::max(
        adapter->peak_host_work_bytes,
        writer.peak_host_work_bytes +
            writer_embeddings.size() *
                n_embd * sizeof(float) +
            writer_embeddings.capacity() *
                sizeof(std::vector<float>) +
            writer_ordinals.capacity() *
                sizeof(uint32_t));

    const auto decode = [n_embd](
            const std::vector<float> & map,
            const std::array<float, 4> & bias,
            const std::vector<float> & embedding) {
        if (map.size() != n_embd * 4 ||
            embedding.size() != n_embd) {
            throw std::runtime_error(
                "semantic port decoder geometry changed");
        }
        std::array<double, 4> code = {};
        for (uint32_t output = 0; output < 4; ++output) {
            code[output] = bias[output];
            for (size_t j = 0; j < n_embd; ++j) {
                code[output] +=
                    static_cast<double>(
                        map[
                            static_cast<size_t>(output) *
                                n_embd + j]) *
                    static_cast<double>(embedding[j]);
            }
        }
        return code;
    };

    if (layer_delta_mode) {
        adapter->coupled_output_gain = 1.0;
        adapter->coupled_training_correct = 0;
        adapter->coupled_training_minimum_margin =
            std::numeric_limits<double>::infinity();
        for (size_t group = 0;
             group < query_samples.size();
             group += 4) {
            std::array<double, 16> port = {};
            for (size_t i = 0; i < 4; ++i) {
                const auto writer_code = decode(
                    adapter->writer_map,
                    adapter->writer_bias,
                    writer_samples[group + i].embedding);
                const uint32_t destination =
                    query_samples[group + i].port_destination;
                if (destination >= 4) {
                    throw std::runtime_error(
                        "semantic port destination is invalid");
                }
                for (size_t output = 0; output < 4; ++output) {
                    port[output * 4 + destination] =
                        writer_code[output];
                }
            }
            for (size_t i = 0; i < 4; ++i) {
                const auto query_code = decode(
                    adapter->query_map,
                    adapter->query_bias,
                    query_samples[group + i].embedding);
                std::array<double, 4> retrieved = {};
                for (size_t output = 0; output < 4; ++output) {
                    for (size_t source = 0; source < 4; ++source) {
                        retrieved[output] +=
                            port[output * 4 + source] *
                            query_code[source];
                    }
                }
                const uint32_t target =
                    query_samples[group + i].output_code_ordinal;
                if (target >= 4) {
                    throw std::runtime_error(
                        "semantic port layer target is invalid");
                }
                const size_t predicted = static_cast<size_t>(
                    std::distance(
                        retrieved.begin(),
                        std::max_element(
                            retrieved.begin(),
                            retrieved.end())));
                adapter->coupled_training_correct +=
                    predicted == target;
                for (size_t competitor = 0;
                     competitor < 4;
                     ++competitor) {
                    if (competitor != target) {
                        adapter->coupled_training_minimum_margin =
                            std::min(
                                adapter
                                    ->coupled_training_minimum_margin,
                                retrieved[target] -
                                    retrieved[competitor]);
                    }
                }
            }
        }
    } else {
        std::array<std::array<double, 4>, 4>
            unit_candidate_response = {};
        for (size_t token = 0; token < candidates.size(); ++token) {
            uint64_t read_bytes = 0;
            uint64_t peak_bytes = 0;
            const auto row = read_model_tensor_row_f32(
                ctx->get_model().output,
                candidates[token],
                read_bytes,
                peak_bytes);
            adapter->source_tensor_read_bytes += read_bytes;
            adapter->peak_host_work_bytes = std::max(
                adapter->peak_host_work_bytes,
                peak_bytes);
            for (size_t code = 0; code < 4; ++code) {
                for (size_t j = 0; j < n_embd; ++j) {
                    unit_candidate_response[token][code] +=
                        static_cast<double>(row[j]) *
                        static_cast<double>(
                            adapter->output_map[j * 4 + code]);
                }
            }
        }

        struct coupled_sample {
            std::array<double, 4> base = {};
            std::array<double, 4> unit_delta = {};
            uint32_t target = 0;
        };
        std::vector<coupled_sample> coupled;
        coupled.reserve(query_samples.size());
        double required_gain = 1.0;
        for (size_t group = 0;
             group < query_samples.size();
             group += 4) {
            std::array<double, 16> port = {};
            for (size_t i = 0; i < 4; ++i) {
                const auto writer_code = decode(
                    adapter->writer_map,
                    adapter->writer_bias,
                    writer_samples[group + i].embedding);
                const uint32_t destination =
                    query_samples[group + i].port_destination;
                if (destination >= 4) {
                    throw std::runtime_error(
                        "semantic port destination is invalid");
                }
                for (size_t output = 0; output < 4; ++output) {
                    port[output * 4 + destination] =
                        writer_code[output];
                }
            }
            for (size_t i = 0; i < 4; ++i) {
                const auto query_code = decode(
                    adapter->query_map,
                    adapter->query_bias,
                    query_samples[group + i].embedding);
                std::array<double, 4> retrieved = {};
                for (size_t output = 0; output < 4; ++output) {
                    for (size_t source = 0; source < 4; ++source) {
                        retrieved[output] +=
                            port[output * 4 + source] *
                            query_code[source];
                    }
                }
                coupled_sample sample;
                sample.target =
                    query_samples[group + i].next_output_ordinal;
                if (sample.target >= 4) {
                    throw std::runtime_error(
                        "semantic port utility target is invalid");
                }
                for (size_t token = 0; token < 4; ++token) {
                    sample.base[token] =
                        query_samples[group + i]
                            .candidate_logits[token];
                    for (size_t code = 0; code < 4; ++code) {
                        sample.unit_delta[token] +=
                            unit_candidate_response[token][code] *
                            retrieved[code];
                    }
                }
                for (size_t competitor = 0;
                     competitor < 4;
                     ++competitor) {
                    if (competitor == sample.target) {
                        continue;
                    }
                    const double denominator =
                        sample.unit_delta[sample.target] -
                        sample.unit_delta[competitor];
                    if (!std::isfinite(denominator) ||
                        denominator <= 1e-9) {
                        throw std::runtime_error(
                            "semantic port cannot separate a training target");
                    }
                    required_gain = std::max(
                        required_gain,
                        (sample.base[competitor] -
                         sample.base[sample.target] +
                         training_margin) /
                            denominator);
                }
                coupled.push_back(sample);
            }
        }
        if (!std::isfinite(required_gain) ||
            required_gain > maximum_output_gain) {
            throw std::runtime_error(
                "semantic port utility gain exceeds the frozen bound");
        }
        adapter->coupled_output_gain = required_gain;
        for (float & value : adapter->output_map) {
            value = static_cast<float>(
                static_cast<double>(value) * required_gain);
        }
        adapter->output_dual_max_abs_error *=
            required_gain;

        adapter->coupled_training_correct = 0;
        adapter->coupled_training_minimum_margin =
            std::numeric_limits<double>::infinity();
        for (const auto & sample : coupled) {
            std::array<double, 4> logits = {};
            for (size_t token = 0; token < 4; ++token) {
                logits[token] =
                    sample.base[token] +
                    required_gain * sample.unit_delta[token];
            }
            const size_t predicted = static_cast<size_t>(
                std::distance(
                    logits.begin(),
                    std::max_element(logits.begin(), logits.end())));
            adapter->coupled_training_correct +=
                predicted == sample.target;
            for (size_t competitor = 0;
                 competitor < 4;
                 ++competitor) {
                if (competitor != sample.target) {
                    adapter->coupled_training_minimum_margin =
                        std::min(
                            adapter->coupled_training_minimum_margin,
                            logits[sample.target] -
                                logits[competitor]);
                }
            }
        }
    }

    adapter->logical_bytes =
        (adapter->query_map.size() +
         adapter->query_bias.size() +
         adapter->writer_map.size() +
         adapter->writer_bias.size() +
         adapter->output_map.size() +
         32) * sizeof(float);
    uint64_t hash = UINT64_C(1469598103934665603);
    const auto mix = [&](const void * data, size_t bytes) {
        fnv1a64_update(hash, data, bytes);
    };
    mix(
        adapter->query_map.data(),
        adapter->query_map.size() * sizeof(float));
    mix(
        adapter->query_bias.data(),
        adapter->query_bias.size() * sizeof(float));
    mix(
        adapter->writer_map.data(),
        adapter->writer_map.size() * sizeof(float));
    mix(
        adapter->writer_bias.data(),
        adapter->writer_bias.size() * sizeof(float));
    mix(
        adapter->output_map.data(),
        adapter->output_map.size() * sizeof(float));
    adapter->hash = hash;
}

static uint64_t neo3000_splitmix64(uint64_t value) {
    value += UINT64_C(0x9e3779b97f4a7c15);
    value =
        (value ^ (value >> 30)) *
        UINT64_C(0xbf58476d1ce4e5b9);
    value =
        (value ^ (value >> 27)) *
        UINT64_C(0x94d049bb133111eb);
    return value ^ (value >> 31);
}

static void complete_output_phase_memory(
        llama_context * ctx,
        const std::vector<llama_token> & candidates,
        const std::vector<semantic_carrier_training_sample> & query_samples,
        const std::vector<semantic_carrier_writer_sample> & writer_samples,
        uint32_t phase_width,
        uint64_t phase_seed,
        bool native_phase_orbit,
        double training_margin,
        double maximum_output_gain,
        semantic_carrier_adapter_build * adapter) {
    if (!ctx ||
        !adapter ||
        candidates.size() != 4 ||
        query_samples.size() < 8 ||
        query_samples.size() != writer_samples.size() ||
        query_samples.size() % 4 != 0 ||
        phase_width < 16 ||
        phase_width > 4096 ||
        !std::isfinite(training_margin) ||
        training_margin <= 0.0 ||
        !std::isfinite(maximum_output_gain) ||
        maximum_output_gain <= 0.0) {
        throw std::runtime_error(
            "phase-memory construction law is invalid");
    }
    const size_t n_embd =
        ctx->get_model().hparams.n_embd_out();
    const size_t vector_size =
        static_cast<size_t>(phase_width) * 2;
    adapter->phase_width = phase_width;
    adapter->phase_seed = phase_seed;
    adapter->phase_binding_table.assign(
        vector_size * 16,
        0.0f);
    adapter->phase_reader.assign(
        vector_size * 16,
        0.0f);
    adapter->phase_generator.assign(
        native_phase_orbit ? vector_size : 0,
        0.0f);

    std::array<std::vector<double>, 4> key_real;
    std::array<std::vector<double>, 4> key_imag;
    std::array<std::vector<double>, 4> value_real;
    std::array<std::vector<double>, 4> value_imag;
    for (uint32_t ordinal = 0; ordinal < 4; ++ordinal) {
        key_real[ordinal].resize(phase_width);
        key_imag[ordinal].resize(phase_width);
        value_real[ordinal].resize(phase_width);
        value_imag[ordinal].resize(phase_width);
        for (uint32_t j = 0; j < phase_width; ++j) {
            const auto phase_component =
                    [&](uint64_t domain) {
                const uint64_t bits = neo3000_splitmix64(
                    phase_seed ^
                    (domain << 56) ^
                    (static_cast<uint64_t>(ordinal) << 32) ^
                    j);
                const double unit =
                    static_cast<double>(bits >> 11) /
                    static_cast<double>(UINT64_C(1) << 53);
                return 2.0 * M_PI * unit;
            };
            const double key_phase = phase_component(1);
            key_real[ordinal][j] = std::cos(key_phase);
            key_imag[ordinal][j] = std::sin(key_phase);
            if (native_phase_orbit) {
                const uint32_t generator_exponent =
                    static_cast<uint32_t>(
                        (j + phase_seed) & UINT64_C(3));
                const uint32_t value_exponent =
                    (generator_exponent * ordinal) & 3u;
                constexpr std::array<double, 4> root_real = {
                    1.0, 0.0, -1.0, 0.0,
                };
                constexpr std::array<double, 4> root_imag = {
                    0.0, 1.0, 0.0, -1.0,
                };
                value_real[ordinal][j] =
                    root_real[value_exponent];
                value_imag[ordinal][j] =
                    root_imag[value_exponent];
                if (ordinal == 0) {
                    adapter->phase_generator[j] =
                        static_cast<float>(
                            root_real[generator_exponent]);
                    adapter->phase_generator[
                        phase_width + j] =
                        static_cast<float>(
                            root_imag[generator_exponent]);
                }
            } else {
                const double value_phase = phase_component(2);
                value_real[ordinal][j] = std::cos(value_phase);
                value_imag[ordinal][j] = std::sin(value_phase);
            }
        }
    }
    for (uint32_t output = 0; output < 4; ++output) {
        for (uint32_t destination = 0;
             destination < 4;
             ++destination) {
            const size_t relation =
                static_cast<size_t>(output) * 4 +
                destination;
            const uint32_t binding_output =
                native_phase_orbit
                    ? (output + 1) % 4
                    : output;
            for (uint32_t j = 0; j < phase_width; ++j) {
                const double real =
                    key_real[destination][j] *
                        value_real[binding_output][j] -
                    key_imag[destination][j] *
                        value_imag[binding_output][j];
                const double imag =
                    key_real[destination][j] *
                        value_imag[binding_output][j] +
                    key_imag[destination][j] *
                        value_real[binding_output][j];
                adapter->phase_binding_table[
                    relation * vector_size + j] =
                    static_cast<float>(real);
                adapter->phase_binding_table[
                    relation * vector_size +
                    phase_width + j] =
                    static_cast<float>(imag);
                adapter->phase_reader[
                    relation * vector_size + j] =
                    static_cast<float>(
                        (key_real[destination][j] *
                             value_real[output][j] -
                         key_imag[destination][j] *
                             value_imag[output][j]) /
                        static_cast<double>(phase_width));
                adapter->phase_reader[
                    relation * vector_size +
                    phase_width + j] =
                    static_cast<float>(
                        (key_real[destination][j] *
                             value_imag[output][j] +
                         key_imag[destination][j] *
                             value_real[output][j]) /
                        static_cast<double>(phase_width));
            }
        }
    }
    for (size_t left = 0; left < 16; ++left) {
        for (size_t right = 0; right < 16; ++right) {
            double score = 0.0;
            for (size_t j = 0; j < vector_size; ++j) {
                score +=
                    static_cast<double>(
                        adapter->phase_reader[
                            left * vector_size + j]) *
                    static_cast<double>(
                        adapter->phase_binding_table[
                            right * vector_size + j]);
            }
            const size_t left_output = left / 4;
            const size_t left_destination = left % 4;
            const size_t right_output = right / 4;
            const size_t right_destination = right % 4;
            const bool intended =
                native_phase_orbit
                    ? left_destination == right_destination &&
                        left_output == (right_output + 1) % 4
                    : left == right;
            if (intended) {
                adapter->phase_self_score_max_abs_error =
                    std::max(
                        adapter->phase_self_score_max_abs_error,
                        std::abs(score - 1.0));
            } else {
                adapter->phase_cross_score_max_abs =
                    std::max(
                        adapter->phase_cross_score_max_abs,
                        std::abs(score));
            }
        }
    }
    if (adapter->phase_self_score_max_abs_error > 1e-5 ||
        adapter->phase_cross_score_max_abs > 0.25) {
        throw std::runtime_error(
            "frozen phase-memory geometry is not separable");
    }
    if (native_phase_orbit) {
        for (uint32_t j = 0; j < phase_width; ++j) {
            double real = 1.0;
            double imag = 0.0;
            const double generator_real =
                adapter->phase_generator[j];
            const double generator_imag =
                adapter->phase_generator[phase_width + j];
            for (uint32_t step = 0; step < 4; ++step) {
                const double next_real =
                    real * generator_real -
                    imag * generator_imag;
                const double next_imag =
                    real * generator_imag +
                    imag * generator_real;
                real = next_real;
                imag = next_imag;
            }
            adapter->phase_rotation_four_step_max_abs_error =
                std::max({
                    adapter->phase_rotation_four_step_max_abs_error,
                    std::abs(real - 1.0),
                    std::abs(imag),
                });
        }
        if (adapter->phase_rotation_four_step_max_abs_error >
                1e-7) {
            throw std::runtime_error(
                "native phase orbit does not close in four steps");
        }
    }

    std::array<std::array<double, 4>, 4>
        unit_candidate_response = {};
    for (size_t token = 0; token < candidates.size(); ++token) {
        uint64_t read_bytes = 0;
        uint64_t peak_bytes = 0;
        const auto row = read_model_tensor_row_f32(
            ctx->get_model().output,
            candidates[token],
            read_bytes,
            peak_bytes);
        adapter->source_tensor_read_bytes += read_bytes;
        adapter->peak_host_work_bytes = std::max(
            adapter->peak_host_work_bytes,
            peak_bytes);
        for (size_t code = 0; code < 4; ++code) {
            for (size_t j = 0; j < n_embd; ++j) {
                unit_candidate_response[token][code] +=
                    static_cast<double>(row[j]) *
                    static_cast<double>(
                        adapter->output_map[j * 4 + code]);
            }
        }
    }

    struct coupled_sample {
        std::array<double, 4> base = {};
        std::array<double, 4> unit_delta = {};
        uint32_t target = 0;
    };
    std::vector<coupled_sample> coupled;
    coupled.reserve(query_samples.size());
    double required_gain = 1.0;
    adapter->phase_training_retrieval_minimum_margin =
        std::numeric_limits<double>::infinity();
    const auto decode_query_code =
            [&](const semantic_carrier_training_sample & sample) {
        std::array<double, 4> code = {};
        for (uint32_t output = 0; output < 4; ++output) {
            code[output] = adapter->query_bias[output];
            for (size_t j = 0; j < n_embd; ++j) {
                code[output] +=
                    static_cast<double>(
                        adapter->query_map[
                            static_cast<size_t>(output) *
                                n_embd + j]) *
                    static_cast<double>(sample.embedding[j]);
            }
        }
        return code;
    };
    for (size_t group = 0;
         group < query_samples.size();
         group += 4) {
        std::vector<double> memory(vector_size, 0.0);
        for (size_t i = 0; i < 4; ++i) {
            const auto & query = query_samples[group + i];
            const uint32_t output =
                writer_samples[group + i].output_ordinal;
            if (query.port_destination >= 4 ||
                output >= 4) {
                throw std::runtime_error(
                    "phase-memory construction topology is invalid");
            }
            const size_t relation =
                static_cast<size_t>(output) * 4 +
                query.port_destination;
            for (size_t j = 0; j < vector_size; ++j) {
                memory[j] +=
                    adapter->phase_binding_table[
                        relation * vector_size + j];
            }
        }
        for (size_t i = 0; i < 4; ++i) {
            const auto & query = query_samples[group + i];
            const auto query_code = decode_query_code(query);
            std::array<double, 4> retrieved = {};
            for (uint32_t output = 0; output < 4; ++output) {
                for (uint32_t destination = 0;
                     destination < 4;
                     ++destination) {
                    const size_t relation =
                        static_cast<size_t>(output) * 4 +
                        destination;
                    double relation_score = 0.0;
                    for (size_t j = 0; j < vector_size; ++j) {
                        relation_score +=
                            static_cast<double>(
                                adapter->phase_reader[
                                    relation * vector_size + j]) *
                            memory[j];
                    }
                    retrieved[output] +=
                        relation_score *
                        query_code[destination];
                }
            }
            const uint32_t target =
                query.next_output_ordinal;
            if (target >= 4) {
                throw std::runtime_error(
                    "phase-memory target is invalid");
            }
            for (size_t competitor = 0;
                 competitor < 4;
                 ++competitor) {
                if (competitor != target) {
                    adapter
                        ->phase_training_retrieval_minimum_margin =
                        std::min(
                            adapter
                                ->phase_training_retrieval_minimum_margin,
                            retrieved[target] -
                                retrieved[competitor]);
                }
            }
            coupled_sample sample;
            sample.target = target;
            for (size_t token = 0; token < 4; ++token) {
                sample.base[token] =
                    query.candidate_logits[token];
                for (size_t code = 0; code < 4; ++code) {
                    sample.unit_delta[token] +=
                        unit_candidate_response[token][code] *
                        retrieved[code];
                }
            }
            for (size_t competitor = 0;
                 competitor < 4;
                 ++competitor) {
                if (competitor == target) {
                    continue;
                }
                const double denominator =
                    sample.unit_delta[target] -
                    sample.unit_delta[competitor];
                if (!std::isfinite(denominator) ||
                    denominator <= 1e-9) {
                    throw std::runtime_error(
                        "phase memory cannot separate a construction target");
                }
                required_gain = std::max(
                    required_gain,
                    (sample.base[competitor] -
                     sample.base[target] +
                     training_margin) /
                        denominator);
            }
            coupled.push_back(sample);
        }
    }
    if (!std::isfinite(required_gain) ||
        !std::isfinite(
            adapter->phase_training_retrieval_minimum_margin) ||
        adapter->phase_training_retrieval_minimum_margin <= 0.0 ||
        required_gain > maximum_output_gain) {
        throw std::runtime_error(
            "phase-memory utility gain exceeds the frozen bound");
    }
    adapter->coupled_output_gain = required_gain;
    for (float & value : adapter->output_map) {
        value = static_cast<float>(
            static_cast<double>(value) * required_gain);
    }
    adapter->output_dual_max_abs_error *= required_gain;
    adapter->coupled_training_correct = 0;
    adapter->coupled_training_minimum_margin =
        std::numeric_limits<double>::infinity();
    for (const auto & sample : coupled) {
        std::array<double, 4> logits = {};
        for (size_t token = 0; token < 4; ++token) {
            logits[token] =
                sample.base[token] +
                required_gain * sample.unit_delta[token];
        }
        const size_t predicted = static_cast<size_t>(
            std::distance(
                logits.begin(),
                std::max_element(
                    logits.begin(),
                    logits.end())));
        adapter->coupled_training_correct +=
            predicted == sample.target;
        for (size_t competitor = 0;
             competitor < 4;
             ++competitor) {
            if (competitor != sample.target) {
                adapter->coupled_training_minimum_margin =
                    std::min(
                        adapter->coupled_training_minimum_margin,
                        logits[sample.target] -
                            logits[competitor]);
            }
        }
    }

    adapter->writer_map.clear();
    adapter->writer_bias.fill(0.0f);
    adapter->logical_bytes =
        (adapter->query_map.size() +
         adapter->query_bias.size() +
         adapter->output_map.size() +
         adapter->phase_binding_table.size() +
         adapter->phase_reader.size() +
         adapter->phase_generator.size() +
         16) * sizeof(float);
    uint64_t hash = UINT64_C(1469598103934665603);
    fnv1a64_update(
        hash,
        adapter->query_map.data(),
        adapter->query_map.size() * sizeof(float));
    fnv1a64_update(
        hash,
        adapter->query_bias.data(),
        adapter->query_bias.size() * sizeof(float));
    fnv1a64_update(
        hash,
        adapter->output_map.data(),
        adapter->output_map.size() * sizeof(float));
    fnv1a64_update(
        hash,
        adapter->phase_binding_table.data(),
        adapter->phase_binding_table.size() * sizeof(float));
    fnv1a64_update(
        hash,
        adapter->phase_reader.data(),
        adapter->phase_reader.size() * sizeof(float));
    fnv1a64_update(
        hash,
        adapter->phase_generator.data(),
        adapter->phase_generator.size() * sizeof(float));
    fnv1a64_update(hash, &phase_width, sizeof(phase_width));
    fnv1a64_update(hash, &phase_seed, sizeof(phase_seed));
    adapter->hash = hash;
    adapter->peak_host_work_bytes = std::max<uint64_t>(
        adapter->peak_host_work_bytes,
        (adapter->phase_binding_table.capacity() +
         adapter->phase_reader.capacity() +
         adapter->phase_generator.capacity()) *
            sizeof(float) +
        vector_size * sizeof(double));
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
        llama_seq_id seq_id = 0,
        bool capture_embedding = false,
        int32_t capture_layer = -1,
        bool split_terminal_carrier = false,
        bool enable_terminal_carrier = false) {
    const std::string text = query.at("suffix").get<std::string>();
    auto tokens = tokenize_piece(vocab, text, false, true);
    if (tokens.empty()) {
        throw std::runtime_error("query suffix is empty");
    }

    const auto started = std::chrono::steady_clock::now();
    size_t layer_embedding_row = tokens.size() - 1;
    if (split_terminal_carrier) {
        const auto * carrier =
            ctx->get_neo3000_semantic_carrier();
        if (!carrier && enable_terminal_carrier) {
            throw std::runtime_error(
                "terminal-only carrier enable has no installed carrier");
        }
        const bool previous_enabled =
            carrier ? carrier->enabled : false;
        if (carrier &&
            !ctx->set_neo3000_semantic_carrier_enabled(false)) {
            throw std::runtime_error(
                "failed to disable carrier before terminal split");
        }
        try {
            if (tokens.size() > 1) {
                decode_tokens(
                    ctx,
                    std::vector<llama_token>(
                        tokens.begin(),
                        tokens.end() - 1),
                    static_cast<llama_pos>(source_tokens),
                    false,
                    seq_id);
            }
            if (carrier &&
                !ctx->set_neo3000_semantic_carrier_enabled(
                    enable_terminal_carrier)) {
                throw std::runtime_error(
                    "failed to select terminal carrier state");
            }
            decode_tokens(
                ctx,
                std::vector<llama_token>{tokens.back()},
                static_cast<llama_pos>(
                    source_tokens + tokens.size() - 1),
                true,
                seq_id);
            llama_synchronize(ctx);
        } catch (...) {
            if (carrier) {
                ctx->set_neo3000_semantic_carrier_enabled(
                    previous_enabled);
            }
            throw;
        }
        if (carrier &&
            !ctx->set_neo3000_semantic_carrier_enabled(
                previous_enabled)) {
            throw std::runtime_error(
                "failed to restore carrier after terminal split");
        }
        layer_embedding_row = 0;
    } else {
        decode_tokens(
            ctx,
            tokens,
            static_cast<llama_pos>(source_tokens),
            true,
            seq_id);
        llama_synchronize(ctx);
    }
    const auto finished = std::chrono::steady_clock::now();

    const float * logits = llama_get_logits_ith(ctx, -1);
    if (!logits) {
        throw std::runtime_error("query produced no terminal logits");
    }

    const int32_t n_vocab = llama_vocab_n_tokens(vocab);
    boundary_result result;
    result.full_logits_fnv1a64 = fnv1a64(logits, static_cast<size_t>(n_vocab) * sizeof(float));
    result.candidate_logits.reserve(candidates.size());
    if (capture_embedding) {
        const float * embedding =
            llama_get_embeddings_ith(ctx, -1);
        if (!embedding) {
            throw std::runtime_error(
                "query produced no terminal embedding");
        }
        const size_t n_embd =
            ctx->get_model().hparams.n_embd_out();
        result.embedding.assign(
            embedding,
            embedding + n_embd);
    }
    if (capture_layer >= 0) {
        const float * layer_embeddings =
            llama_get_embeddings_layer_inp(
                ctx,
                static_cast<uint32_t>(capture_layer));
        if (!layer_embeddings) {
            throw std::runtime_error(
                "query produced no requested layer input");
        }
        const size_t n_embd =
            ctx->get_model().hparams.n_embd;
        const float * layer_embedding =
            layer_embeddings + layer_embedding_row * n_embd;
        result.layer_embedding.assign(
            layer_embedding,
            layer_embedding + n_embd);
    }

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
        {"carrier_terminal_only", split_terminal_carrier},
        {"carrier_enabled_for_terminal", enable_terminal_carrier},
        {"captured_layer", capture_layer},
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

static json run_source_conditioned_lifting(
        llama_context * ctx,
        const llama_vocab * vocab,
        const std::vector<llama_token> & candidates,
        const json & spec,
        uint64_t active_recurrent_backing_initial) {
    if (candidates.size() != 4 ||
        !spec.value("source_conditioned_lifting_action", false)) {
        throw std::runtime_error(
            "source-conditioned lifting mode is not frozen");
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
            "source-conditioned lifting context geometry mismatch");
    }

    const auto prefix_tokens = tokenize_piece(
        vocab, spec.at("prefix").get<std::string>(), true, true);
    const auto f_tokens = tokenize_piece(
        vocab, spec.at("module_f").get<std::string>(), false, true);
    const auto neutral_f_tokens = tokenize_piece(
        vocab,
        spec.at("structural_module_f").get<std::string>(),
        false,
        true);
    const auto structural_g_tokens = tokenize_piece(
        vocab,
        spec.at("structural_module_g").get<std::string>(),
        false,
        true);
    const auto closure_tokens = tokenize_piece(
        vocab, spec.at("closure").get<std::string>(), false, true);
    const size_t expected_source_tokens =
        spec.at("expected_source_tokens").get<size_t>();
    if (prefix_tokens.size() !=
            spec.at("expected_prefix_tokens").get<size_t>() ||
        f_tokens.size() !=
            spec.at("expected_f_tokens").get<size_t>() ||
        neutral_f_tokens.size() != f_tokens.size() ||
        structural_g_tokens.size() !=
            spec.at("expected_g_tokens").get<size_t>() ||
        closure_tokens.size() !=
            spec.at("expected_closure_tokens").get<size_t>() ||
        prefix_tokens.size() + f_tokens.size() +
            structural_g_tokens.size() + closure_tokens.size() !=
            expected_source_tokens) {
        throw std::runtime_error(
            "source-conditioned lifting token geometry mismatch");
    }

    const auto f_key_offsets =
        spec.at("lifting_f_key_offsets")
            .get<std::vector<size_t>>();
    const auto f_value_offsets =
        spec.at("lifting_f_value_offsets")
            .get<std::vector<size_t>>();
    const auto g_key_offsets =
        spec.at("lifting_g_key_offsets")
            .get<std::vector<size_t>>();
    const auto g_value_offsets =
        spec.at("lifting_g_value_offsets")
            .get<std::vector<size_t>>();
    for (const auto * offsets :
         {&f_key_offsets, &f_value_offsets,
          &g_key_offsets, &g_value_offsets}) {
        if (offsets->size() != 4 ||
            !std::is_sorted(offsets->begin(), offsets->end())) {
            throw std::runtime_error(
                "source-conditioned lifting capture offsets invalid");
        }
    }
    if (f_key_offsets.back() >= f_tokens.size() ||
        f_value_offsets.back() >= f_tokens.size() ||
        g_key_offsets.back() >= structural_g_tokens.size() ||
        g_value_offsets.back() >= structural_g_tokens.size()) {
        throw std::runtime_error(
            "source-conditioned lifting capture offset out of range");
    }

    const auto & variants = spec.at("g_variants");
    if (!variants.is_array() || variants.size() != 4) {
        throw std::runtime_error(
            "source-conditioned lifting requires four frozen variants");
    }
    std::vector<std::vector<llama_token>> variant_g_tokens;
    for (const auto & variant : variants) {
        auto tokens = tokenize_piece(
            vocab,
            variant.at("module_g").get<std::string>(),
            false,
            true);
        if (tokens.size() != structural_g_tokens.size() ||
            variant.at("queries").size() != 4) {
            throw std::runtime_error(
                "source-conditioned lifting variant geometry mismatch");
        }
        variant_g_tokens.push_back(std::move(tokens));
    }

    auto * hybrid = require_hybrid_memory(ctx);
    auto * attention = hybrid->get_mem_attn();
    auto * recurrent = hybrid->get_mem_recr();
    if (attention->get_n_stream() !=
            spec.at("expected_attention_stream_count")
                .get<uint32_t>()) {
        throw std::runtime_error(
            "source-conditioned lifting attention stream mismatch");
    }
    llama_memory_t memory = llama_get_memory(ctx);
    const llama_seq_id f_source_seq = 0;
    const llama_seq_id scaffold_seq = 1;
    const llama_seq_id factor_source_seq = 2;
    const llama_seq_id candidate_scratch_seq = 3;
    const llama_seq_id exact_source_seq = 4;
    const llama_seq_id exact_scratch_seq = 5;
    const llama_seq_id unrelated_seq = 6;
    const llama_pos source_boundary_pos =
        static_cast<llama_pos>(expected_source_tokens - 1);

    const auto require_positions =
            [&](llama_seq_id seq_id,
                llama_pos expected,
                const std::string & stage) {
        const llama_pos attention_pos =
            attention->seq_pos_max(seq_id);
        const llama_pos recurrent_pos =
            recurrent->seq_pos_max(seq_id);
        if (attention_pos != expected ||
            recurrent_pos != expected) {
            throw std::runtime_error(
                stage + " sequence " +
                std::to_string(seq_id) +
                " positions attention=" +
                std::to_string(attention_pos) +
                " recurrent=" +
                std::to_string(recurrent_pos));
        }
    };
    const auto close_sequence =
            [&](llama_seq_id seq_id, const std::string & stage) {
        if (!llama_memory_seq_rm(memory, seq_id, -1, -1)) {
            throw std::runtime_error(
                stage + " sequence close failed");
        }
        llama_synchronize(ctx);
        require_positions(seq_id, -1, stage + ":closed");
    };
    const auto copy_sequence =
            [&](llama_seq_id source,
                llama_seq_id destination,
                llama_pos expected,
                const std::string & stage) {
        require_positions(
            destination, -1, stage + ":destination-empty");
        llama_memory_seq_cp(
            memory, source, destination, -1, -1);
        llama_synchronize(ctx);
        require_positions(
            destination, expected, stage + ":copied");
    };
    const auto token_slice =
            [](const std::vector<llama_token> & tokens,
               size_t begin,
               size_t end) {
        return std::vector<llama_token>(
            tokens.begin() +
                static_cast<std::ptrdiff_t>(begin),
            tokens.begin() +
                static_cast<std::ptrdiff_t>(end));
    };
    uint64_t source_decode_tokens = 0;
    uint64_t query_decode_tokens = 0;
    uint64_t sequence_copies = 0;
    uint64_t sequence_closes = 0;
    double source_decode_wall_ms = 0.0;
    const auto timed_decode =
            [&](const std::vector<llama_token> & tokens,
                llama_pos start_pos,
                llama_seq_id seq_id) {
        const auto started = std::chrono::steady_clock::now();
        decode_tokens(
            ctx, tokens, start_pos, false, seq_id);
        llama_synchronize(ctx);
        source_decode_tokens += tokens.size();
        source_decode_wall_ms +=
            std::chrono::duration<double, std::milli>(
                std::chrono::steady_clock::now() -
                started).count();
    };

    struct capture_event {
        size_t offset = 0;
        int32_t kind = 0;
        int32_t slot = 0;
    };
    const auto decode_captured_module =
            [&](const std::vector<llama_token> & tokens,
                llama_pos start_pos,
                llama_seq_id seq_id,
                std::vector<capture_event> events,
                const std::string & stage) {
        std::sort(
            events.begin(),
            events.end(),
            [](const capture_event & lhs,
               const capture_event & rhs) {
                return lhs.offset < rhs.offset;
            });
        for (size_t i = 1; i < events.size(); ++i) {
            if (events[i - 1].offset == events[i].offset) {
                throw std::runtime_error(
                    stage + " has two captures on one token");
            }
        }
        size_t cursor = 0;
        for (const auto & event : events) {
            if (event.offset >= tokens.size()) {
                throw std::runtime_error(
                    stage + " capture is out of range");
            }
            if (event.offset > cursor) {
                timed_decode(
                    token_slice(tokens, cursor, event.offset),
                    start_pos +
                        static_cast<llama_pos>(cursor),
                    seq_id);
            }
            if (!ctx->set_neo3000_lifting_capture(
                    event.kind, event.slot)) {
                throw std::runtime_error(
                    stage + " failed to arm capture");
            }
            timed_decode(
                std::vector<llama_token>{
                    tokens.at(event.offset)},
                start_pos +
                    static_cast<llama_pos>(event.offset),
                seq_id);
            cursor = event.offset + 1;
        }
        if (cursor < tokens.size()) {
            timed_decode(
                token_slice(tokens, cursor, tokens.size()),
                start_pos + static_cast<llama_pos>(cursor),
                seq_id);
        }
    };

    if (!ctx->install_neo3000_source_conditioned_lifting()) {
        throw std::runtime_error(
            "source-conditioned lifting installation failed");
    }
    const auto * installed =
        ctx->get_neo3000_semantic_carrier();
    if (!installed ||
        !installed->source_conditioned_lifting ||
        installed->lifting_poisoned ||
        installed->lifting_update_resident ||
        installed->lifting_layers.size() != 10 ||
        installed->lifting_f_key_active_layers.size() != 10 ||
        installed->lifting_f_key_staging_slots.size() != 40 ||
        installed->lifting_backend_bytes == 0 ||
        installed->action_backing_id == 0) {
        throw std::runtime_error(
            "source-conditioned lifting install invariant failed");
    }
    const uint64_t backing_id_initial =
        installed->action_backing_id;
    ctx->sched_reserve();

    try {
        llama_memory_clear(memory, true);
        llama_synchronize(ctx);

        // Candidate inference receives a matched neutral scaffold. It never
        // receives the actual F or G relation text.
        std::vector<llama_token> scaffold_tokens;
        scaffold_tokens.reserve(expected_source_tokens);
        scaffold_tokens.insert(
            scaffold_tokens.end(),
            prefix_tokens.begin(), prefix_tokens.end());
        scaffold_tokens.insert(
            scaffold_tokens.end(),
            neutral_f_tokens.begin(), neutral_f_tokens.end());
        scaffold_tokens.insert(
            scaffold_tokens.end(),
            structural_g_tokens.begin(),
            structural_g_tokens.end());
        scaffold_tokens.insert(
            scaffold_tokens.end(),
            closure_tokens.begin(), closure_tokens.end());
        timed_decode(scaffold_tokens, 0, scaffold_seq);
        require_positions(
            scaffold_seq,
            source_boundary_pos,
            "lifting:neutral-scaffold");

        timed_decode(prefix_tokens, 0, f_source_seq);
        std::vector<capture_event> f_events;
        for (size_t slot = 0; slot < 4; ++slot) {
            f_events.push_back(
                {f_key_offsets[slot], 1,
                 static_cast<int32_t>(slot)});
            f_events.push_back(
                {f_value_offsets[slot], 2,
                 static_cast<int32_t>(slot)});
        }
        decode_captured_module(
            f_tokens,
            static_cast<llama_pos>(prefix_tokens.size()),
            f_source_seq,
            std::move(f_events),
            "lifting:F");
        close_sequence(
            f_source_seq, "lifting:F-source");
        ++sequence_closes;

        const size_t active_cache_backend_allocation_bytes =
            active_hybrid_backend_allocation_bytes(ctx);
        json records = json::array();
        json route_summaries = json::array();
        std::array<std::vector<boundary_result>, 4> joint = {};
        size_t exact_correct = 0;
        size_t joint_correct = 0;
        std::map<std::string, size_t> control_correct;
        std::map<std::string, size_t> control_joint_matches;

        const auto run_query =
                [&](llama_seq_id source_seq,
                    llama_seq_id scratch_seq,
                    size_t route_source_tokens,
                    uint32_t control,
                    const std::string & route,
                    const std::string & variant_id,
                    const json & query) {
            copy_sequence(
                source_seq,
                scratch_seq,
                static_cast<llama_pos>(
                    route_source_tokens - 1),
                route + ":copy");
            ++sequence_copies;
            if (!ctx->set_neo3000_lifting_control(control)) {
                throw std::runtime_error(
                    route + ": failed to select lifting control");
            }
            boundary_result result;
            try {
                result = decode_query(
                    ctx,
                    vocab,
                    candidates,
                    "source-conditioned-lifting:" + route,
                    variant_id,
                    query,
                    route_source_tokens,
                    active_recurrent_backing_initial,
                    active_cache_backend_allocation_bytes,
                    scratch_seq);
            } catch (...) {
                ctx->set_neo3000_lifting_control(0);
                throw;
            }
            if (!ctx->set_neo3000_lifting_control(0)) {
                throw std::runtime_error(
                    route + ": failed to close lifting read");
            }
            query_decode_tokens +=
                result.record.at("query_tokens")
                    .get<size_t>();
            result.record["lifting_control"] = control;
            result.record["factor_backing_id"] =
                backing_id_initial;
            records.push_back(result.record);
            close_sequence(
                scratch_seq, route + ":query");
            ++sequence_closes;
            return result;
        };

        size_t variant_index = 0;
        for (const auto & variant : variants) {
            const std::string variant_id =
                variant.at("id").get<std::string>();
            if (variant_index > 0 &&
                !ctx->begin_neo3000_lifting_g_update()) {
                throw std::runtime_error(
                    variant_id +
                    ": failed to begin G factor update");
            }

            timed_decode(
                prefix_tokens, 0, factor_source_seq);
            timed_decode(
                neutral_f_tokens,
                static_cast<llama_pos>(prefix_tokens.size()),
                factor_source_seq);
            std::vector<capture_event> g_events;
            for (size_t slot = 0; slot < 4; ++slot) {
                g_events.push_back(
                    {g_key_offsets[slot], 3,
                     static_cast<int32_t>(slot)});
                g_events.push_back(
                    {g_value_offsets[slot], 4,
                     static_cast<int32_t>(slot)});
            }
            decode_captured_module(
                variant_g_tokens.at(variant_index),
                static_cast<llama_pos>(
                    prefix_tokens.size() +
                    neutral_f_tokens.size()),
                factor_source_seq,
                std::move(g_events),
                variant_id + ":G");
            timed_decode(
                closure_tokens,
                static_cast<llama_pos>(
                    prefix_tokens.size() +
                    neutral_f_tokens.size() +
                    variant_g_tokens.at(
                        variant_index).size()),
                factor_source_seq);
            close_sequence(
                factor_source_seq,
                variant_id + ":factor-source");
            ++sequence_closes;
            if (!ctx->commit_neo3000_source_conditioned_lifting()) {
                throw std::runtime_error(
                    variant_id +
                    ": complete factor panel failed to commit");
            }
            const auto * committed =
                ctx->get_neo3000_semantic_carrier();
            if (!committed ||
                committed->action_backing_id !=
                    backing_id_initial ||
                committed->lifting_update_resident ||
                committed->lifting_poisoned) {
                throw std::runtime_error(
                    variant_id +
                    ": committed factor backing changed");
            }

            std::vector<llama_token> exact_source;
            exact_source.reserve(expected_source_tokens);
            exact_source.insert(
                exact_source.end(),
                prefix_tokens.begin(), prefix_tokens.end());
            exact_source.insert(
                exact_source.end(),
                f_tokens.begin(), f_tokens.end());
            exact_source.insert(
                exact_source.end(),
                variant_g_tokens.at(variant_index).begin(),
                variant_g_tokens.at(variant_index).end());
            exact_source.insert(
                exact_source.end(),
                closure_tokens.begin(), closure_tokens.end());
            timed_decode(
                exact_source, 0, exact_source_seq);
            require_positions(
                exact_source_seq,
                source_boundary_pos,
                variant_id + ":exact-source");

            size_t query_index = 0;
            for (const auto & query : variant.at("queries")) {
                auto exact = run_query(
                    exact_source_seq,
                    exact_scratch_seq,
                    expected_source_tokens,
                    0,
                    "exact_full_state",
                    variant_id,
                    query);
                exact_correct +=
                    exact.argmax ==
                    query.at("expected").get<std::string>();
                auto candidate = run_query(
                    scaffold_seq,
                    candidate_scratch_seq,
                    expected_source_tokens,
                    1,
                    "lifting_F_then_G",
                    variant_id,
                    query);
                joint_correct +=
                    candidate.argmax ==
                    query.at("expected").get<std::string>();
                joint.at(variant_index).push_back(
                    std::move(candidate));
                ++query_index;
            }
            close_sequence(
                exact_source_seq,
                variant_id + ":exact-source");
            ++sequence_closes;

            if (variant_index == 1) {
                const std::array<
                    std::pair<const char *, uint32_t>, 5>
                    controls = {{
                        {"carrier_off", 0},
                        {"F_only", 2},
                        {"G_only", 3},
                        {"G_then_F", 4},
                        {"cyclic_G_relation_mutation", 5},
                    }};
                for (const auto & [route, control] : controls) {
                    size_t control_index = 0;
                    for (const auto & query :
                         variant.at("queries")) {
                        auto boundary = run_query(
                            scaffold_seq,
                            candidate_scratch_seq,
                            expected_source_tokens,
                            control,
                            route,
                            variant_id,
                            query);
                        control_correct[route] +=
                            boundary.argmax ==
                            query.at("expected")
                                .get<std::string>();
                        control_joint_matches[route] +=
                            boundary.argmax ==
                            joint.at(variant_index)
                                .at(control_index).argmax;
                        ++control_index;
                    }
                }
            }
            route_summaries.push_back({
                {"variant", variant_id},
                {"exact_query_records", 4},
                {"joint_query_records", 4},
                {"control_query_records",
                    variant_index == 1 ? 20 : 0},
                {"factor_backing_id", backing_id_initial},
            });
            ++variant_index;
        }

        const auto * before_close =
            ctx->get_neo3000_semantic_carrier();
        if (!before_close ||
            before_close->lifting_captures != 40 ||
            before_close->lifting_commits != 4 ||
            before_close->lifting_reads == 0 ||
            before_close->action_backing_id !=
                backing_id_initial) {
            throw std::runtime_error(
                "source-conditioned lifting accounting invariant failed");
        }
        const uint64_t lifting_backend_bytes =
            before_close->lifting_backend_bytes;
        const uint64_t capture_copy_bytes =
            before_close->lifting_capture_device_copy_bytes;
        const uint64_t commit_copy_bytes =
            before_close->lifting_commit_device_copy_bytes;
        const uint64_t lifting_token_applications =
            before_close->lifting_token_applications;
        const uint64_t lifting_multiply_accumulates =
            before_close->lifting_multiply_accumulates;
        const uint64_t lifting_reads =
            before_close->lifting_reads;
        const uint64_t lifting_captures =
            before_close->lifting_captures;
        const uint64_t lifting_commits =
            before_close->lifting_commits;
        const double restoration_error_max =
            before_close->lifting_restoration_error_max;
        const double restoration_error_sum =
            before_close->lifting_restoration_error_sum;

        if (!ctx->reset_neo3000_semantic_port()) {
            throw std::runtime_error(
                "source-conditioned lifting factor close failed");
        }
        const auto * closed =
            ctx->get_neo3000_semantic_carrier();
        if (!closed ||
            closed->action_backing_id != backing_id_initial ||
            closed->lifting_update_resident ||
            closed->lifting_poisoned ||
            closed->enabled) {
            throw std::runtime_error(
                "source-conditioned lifting close invariant failed");
        }
        const uint64_t closure_zero_bytes =
            closed->lifting_closure_device_zero_bytes;

        const auto unrelated_source_tokens = tokenize_piece(
            vocab,
            spec.at("unrelated_source").get<std::string>(),
            true,
            true);
        timed_decode(
            unrelated_source_tokens, 0, unrelated_seq);
        const auto unrelated = run_query(
            unrelated_seq,
            candidate_scratch_seq,
            unrelated_source_tokens.size(),
            0,
            "post_close_unrelated_reuse",
            "unrelated",
            spec.at("unrelated_query"));
        const bool unrelated_useful =
            unrelated.argmax ==
            spec.at("unrelated_query")
                .at("expected").get<std::string>();
        close_sequence(
            unrelated_seq, "lifting:unrelated-source");
        ++sequence_closes;
        close_sequence(
            scaffold_seq, "lifting:neutral-scaffold");
        ++sequence_closes;

        const auto & acceptance = spec.at("acceptance_law");
        const bool control_gate =
            std::all_of(
                control_correct.begin(),
                control_correct.end(),
                [&](const auto & entry) {
                    return entry.second <=
                        acceptance.at(
                            "control_correct_maximum")
                            .get<size_t>();
                }) &&
            std::all_of(
                control_joint_matches.begin(),
                control_joint_matches.end(),
                [&](const auto & entry) {
                    return entry.second <=
                        acceptance.at(
                            "control_joint_matches_maximum")
                            .get<size_t>();
                });
        const bool accepted =
            exact_correct ==
                acceptance.at("exact_correct")
                    .get<size_t>() &&
            joint_correct ==
                acceptance.at("joint_correct")
                    .get<size_t>() &&
            control_gate &&
            restoration_error_max <=
                acceptance.at(
                    "restoration_error_maximum")
                    .get<double>() &&
            unrelated_useful;

        ctx->clear_neo3000_semantic_carrier();
        const bool carrier_released =
            ctx->get_neo3000_semantic_carrier() == nullptr;
        if (!carrier_released) {
            throw std::runtime_error(
                "source-conditioned lifting backing release failed");
        }
        llama_memory_clear(memory, true);
        llama_synchronize(ctx);

        return {
            {"mode",
                "source_conditioned_reversible_low_rank_lifting"},
            {"mechanism", {
                {"forward",
                    "cF=(KF^T*x)/rowsum(KF^2); "
                    "xF=x+(VF-KF)*cF; "
                    "cG=(KG^T*xF)/rowsum(KG^2); "
                    "xFG=xF+(VG-KG)*cG"},
                {"reverse_check",
                    "xF'=xFG-(VG-KG)*cG; "
                    "x'=xF'-(VF-KF)*cF; "
                    "compare x' with x and recomputed cF,cG "
                    "with retained graph ancillas"},
                {"effective_transition",
                    "frozen Q/K/V consume transformed x before inverse"},
                {"factor_source_separated", true},
                {"second_complete_factor_panel_retained", false},
                {"reverse_check_out_of_place", true},
                {"restoration_class",
                    "NO_RESTORATION_CLAIM"},
                {"factor_disposition",
                    "DECLARED_CLOSURE_BY_ZERO_AND_RELEASE"},
            }},
            {"summary", {
                {"exact_correct", exact_correct},
                {"joint_correct", joint_correct},
                {"control_correct", control_correct},
                {"control_joint_matches",
                    control_joint_matches},
                {"restoration_error_max",
                    restoration_error_max},
                {"restoration_error_sum",
                    restoration_error_sum},
                {"unrelated_useful_after_close",
                    unrelated_useful},
                {"same_backing_before_close",
                    backing_id_initial},
                {"carrier_released", carrier_released},
                {"accepted", accepted},
            }},
            {"carrier", {
                {"backing_id", backing_id_initial},
                {"backend_bytes", lifting_backend_bytes},
                {"captures", lifting_captures},
                {"commits", lifting_commits},
                {"reads", lifting_reads},
                {"capture_device_copy_bytes",
                    capture_copy_bytes},
                {"commit_device_copy_bytes",
                    commit_copy_bytes},
                {"closure_device_zero_bytes",
                    closure_zero_bytes},
                {"partial_update_resident_after_close", false},
                {"second_complete_factor_panel_retained", false},
            }},
            {"resource_accounting", {
                {"source_decode_tokens", source_decode_tokens},
                {"query_decode_tokens", query_decode_tokens},
                {"all_route_input_tokens",
                    source_decode_tokens + query_decode_tokens},
                {"source_decode_wall_ms",
                    source_decode_wall_ms},
                {"sequence_copies", sequence_copies},
                {"sequence_closes", sequence_closes},
                {"lifting_token_applications",
                    lifting_token_applications},
                {"lifting_multiply_accumulates",
                    lifting_multiply_accumulates},
                {"active_cache_backend_allocation_bytes",
                    active_cache_backend_allocation_bytes},
            }},
            {"route_summaries", route_summaries},
            {"records", records},
            {"verdict", accepted ? "accept" : "reject"},
            {"claim_ceiling", spec.at("claim_ceiling")},
        };
    } catch (...) {
        ctx->poison_neo3000_source_conditioned_lifting();
        ctx->clear_neo3000_semantic_carrier();
        llama_memory_clear(memory, true);
        llama_synchronize(ctx);
        throw;
    }
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
    if (spec.value(
            "source_conditioned_lifting_action",
            false)) {
        return run_source_conditioned_lifting(
            ctx,
            vocab,
            candidates,
            spec,
            active_recurrent_backing_initial);
    }
    const bool position_orbit_mode =
        spec.value("label_orbit_attention_action", false);
    const bool value_orbit_mode =
        spec.value("value_orbit_attention_action", false);
    const bool key_value_orbit_mode =
        spec.value("key_value_orbit_attention_action", false);
    const bool complex_phase_orbit_mode =
        spec.value("complex_phase_quarter_turn_action", false);
    const bool paired_complex_attention_read =
        spec.value("paired_complex_attention_read", false);
    const bool complex_phase_include_keys =
        spec.value("complex_phase_include_keys", true);
    const float paired_complex_attention_mix =
        spec.value("paired_complex_attention_mix", 0.0f);
    const int32_t paired_complex_attention_layer =
        spec.value("paired_complex_attention_layer", -1);
    const bool fourier_value_orbit_mode =
        spec.value("fourier_value_orbit_action", false);
    const bool subspace_value_orbit_mode =
        spec.value("subspace_value_orbit_action", false);
    const bool model_weight_value_orbit_mode =
        spec.value("model_weight_value_orbit_action", false);
    const bool output_promoted_value_carrier_mode =
        spec.value("output_promoted_value_carrier_action", false);
    const bool output_role_transport_mode =
        spec.value("output_role_transport_action", false);
    const bool output_role_generator_mode =
        spec.value("output_role_generator_action", false);
    const bool output_attention_kernel_writer_mode =
        spec.value(
            "output_attention_kernel_writer_action",
            false);
    const bool output_source_relink_rematerialization_mode =
        spec.value(
            "output_source_position_rematerialization_action",
            false);
    const bool output_source_fixed_cell_rematerialization_mode =
        spec.value(
            "output_source_position_fixed_cell_rematerialization_action",
            false);
    const bool output_continuous_soft_role_rematerialization_mode =
        spec.value(
            "output_continuous_soft_role_rematerialization_action",
            false);
    const bool output_source_rematerialization_mode =
        output_source_relink_rematerialization_mode ||
        output_source_fixed_cell_rematerialization_mode ||
        output_continuous_soft_role_rematerialization_mode;
    const bool output_written_semantic_port_mode =
        spec.value(
            "output_written_semantic_port_action",
            false);
    const bool output_written_hidden_slot_mode =
        spec.value(
            "output_written_hidden_slot_action",
            false);
    const bool output_depth_memory_mode =
        spec.value(
            "output_depth_resolved_cross_attention_memory_action",
            false);
    const bool output_phase_feedback_memory_mode =
        spec.value(
            "output_phase_memory_action",
            false);
    const bool output_phase_orbit_memory_mode =
        spec.value(
            "output_phase_orbit_memory_action",
            false);
    if (output_phase_feedback_memory_mode &&
        output_phase_orbit_memory_mode) {
        throw std::runtime_error(
            "phase feedback and native phase orbit actions are exclusive");
    }
    const bool output_phase_memory_mode =
        output_phase_feedback_memory_mode ||
        output_phase_orbit_memory_mode;
    const bool output_written_carrier_mode =
        output_written_semantic_port_mode ||
        output_written_hidden_slot_mode ||
        output_phase_memory_mode ||
        output_depth_memory_mode;
    const bool end_to_end_semantic_carrier_training =
        spec.value(
            "end_to_end_semantic_carrier_training",
            false);
    const bool output_recurrent_delta_advance_mode =
        spec.value(
            "output_recurrent_delta_advance_action",
            false);
    const bool output_driven_carrier_mode =
        output_promoted_value_carrier_mode ||
        output_role_transport_mode ||
        output_role_generator_mode ||
        output_attention_kernel_writer_mode ||
        output_source_rematerialization_mode ||
        output_written_carrier_mode ||
        output_recurrent_delta_advance_mode;
    const bool legacy_trained_semantic_carrier_mode =
        spec.value("trained_semantic_carrier_action", false);
    const bool trained_semantic_carrier_mode =
        legacy_trained_semantic_carrier_mode ||
        output_written_semantic_port_mode ||
        output_written_hidden_slot_mode ||
        output_phase_memory_mode;
    const bool semantic_carrier_layer_delta_mode =
        trained_semantic_carrier_mode &&
        spec.value(
            "semantic_carrier_layer_delta_training",
            false);
    const bool semantic_carrier_moe_router_bias_mode =
        semantic_carrier_layer_delta_mode &&
        spec.value(
            "semantic_carrier_moe_router_bias",
            false);
    const bool semantic_carrier_recurrent_transition_mode =
        semantic_carrier_layer_delta_mode &&
        spec.value(
            "semantic_carrier_recurrent_transition_input",
            false);
    const int32_t semantic_carrier_read_layer =
        trained_semantic_carrier_mode
            ? spec.value("semantic_carrier_read_layer", -1)
            : -1;
    const bool subspace_include_keys =
        spec.value("subspace_include_keys", false);
    if (subspace_include_keys &&
        !subspace_value_orbit_mode) {
        throw std::runtime_error(
            "subspace key action requires subspace value action");
    }
    if (paired_complex_attention_read &&
        (!complex_phase_orbit_mode ||
         complex_phase_include_keys ||
         paired_complex_attention_mix <= 0.0f ||
         paired_complex_attention_mix > 1.0f ||
         paired_complex_attention_layer < 0)) {
        throw std::runtime_error(
            "paired-complex read requires a value-only complex phase "
            "orbit and one valid frozen graph layer/mix");
    }
    const bool orbit_mode =
        position_orbit_mode ||
        value_orbit_mode ||
        key_value_orbit_mode ||
        complex_phase_orbit_mode ||
        fourier_value_orbit_mode ||
        subspace_value_orbit_mode ||
        model_weight_value_orbit_mode ||
        output_driven_carrier_mode ||
        trained_semantic_carrier_mode;
    if (static_cast<int>(position_orbit_mode) +
            static_cast<int>(value_orbit_mode) +
            static_cast<int>(key_value_orbit_mode) +
            static_cast<int>(complex_phase_orbit_mode) +
            static_cast<int>(fourier_value_orbit_mode) +
            static_cast<int>(subspace_value_orbit_mode) +
            static_cast<int>(model_weight_value_orbit_mode) +
            static_cast<int>(output_promoted_value_carrier_mode) +
            static_cast<int>(output_role_transport_mode) +
            static_cast<int>(output_role_generator_mode) +
            static_cast<int>(
                output_attention_kernel_writer_mode) +
            static_cast<int>(
                output_source_relink_rematerialization_mode) +
            static_cast<int>(
                output_source_fixed_cell_rematerialization_mode) +
            static_cast<int>(
                output_continuous_soft_role_rematerialization_mode) +
            static_cast<int>(
                legacy_trained_semantic_carrier_mode) +
            static_cast<int>(
                output_written_semantic_port_mode) +
            static_cast<int>(
                output_written_hidden_slot_mode) +
            static_cast<int>(
                output_depth_memory_mode) +
            static_cast<int>(
                output_phase_memory_mode) +
            static_cast<int>(
                output_recurrent_delta_advance_mode) > 1) {
        throw std::runtime_error(
            "label orbit action modes are mutually exclusive");
    }
    if (trained_semantic_carrier_mode) {
        if (end_to_end_semantic_carrier_training &&
            !output_written_semantic_port_mode) {
            throw std::runtime_error(
                "end-to-end carrier training requires the "
                "output-written port");
        }
        if ((semantic_carrier_moe_router_bias_mode ||
             semantic_carrier_recurrent_transition_mode) &&
            !output_written_semantic_port_mode) {
            throw std::runtime_error(
                "dynamic semantic transition requires the "
                "output-written port");
        }
        if (semantic_carrier_moe_router_bias_mode &&
            semantic_carrier_recurrent_transition_mode) {
            throw std::runtime_error(
                "dynamic semantic transition modes are exclusive");
        }
        if (semantic_carrier_layer_delta_mode) {
            if (semantic_carrier_read_layer < 0 ||
                semantic_carrier_read_layer >=
                    static_cast<int32_t>(
                        ctx->get_model().hparams.n_layer())) {
                throw std::runtime_error(
                    "semantic carrier read layer is invalid");
            }
            ctx->set_embeddings_layer_inp(
                static_cast<uint32_t>(
                    semantic_carrier_read_layer),
                true);
        } else {
            if (semantic_carrier_read_layer != -1) {
                throw std::runtime_error(
                    "terminal semantic carrier has a layer read");
            }
            ctx->set_embeddings(true);
        }
        if (output_phase_memory_mode &&
            (semantic_carrier_layer_delta_mode ||
             semantic_carrier_read_layer != -1 ||
             spec.at("phase_memory_width").get<uint32_t>() < 16 ||
             spec.at("phase_memory_width").get<uint32_t>() > 4096)) {
            throw std::runtime_error(
                "phase memory requires one bounded terminal reader");
        }
        ctx->sched_reserve();
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
    if (model_weight_value_orbit_mode ||
        output_driven_carrier_mode ||
        trained_semantic_carrier_mode) {
        std::vector<llama_token> canonical_labels;
        canonical_labels.reserve(label_offsets.size());
        for (const size_t offset : label_offsets) {
            canonical_labels.push_back(
                variant_g_tokens.at(0).at(offset));
        }
        if (std::set<llama_token>(
                canonical_labels.begin(),
                canonical_labels.end()).size() !=
                canonical_labels.size()) {
            throw std::runtime_error(
                "semantic carrier labels are not distinct");
        }
        for (size_t variant = 0;
             variant < variant_g_tokens.size();
             ++variant) {
            for (size_t position = 0;
                 position < label_offsets.size();
                 ++position) {
                if (variant_g_tokens[variant]
                        [label_offsets[position]] !=
                    canonical_labels[
                        (position + variant) %
                        canonical_labels.size()]) {
                    throw std::runtime_error(
                        "semantic carrier labels do not follow "
                        "the frozen public Z4 cycle");
                }
            }
        }
    }
    std::vector<size_t> output_promotion_label_indices;
    if (output_driven_carrier_mode &&
        !output_recurrent_delta_advance_mode) {
        output_promotion_label_indices =
            spec.at("output_promotion_label_indices")
                .get<std::vector<size_t>>();
        if (output_promotion_label_indices.size() !=
                spec.at("queries_per_variant").get<size_t>() ||
            output_promotion_label_indices.size() !=
                label_offsets.size() ||
            std::set<size_t>(
                output_promotion_label_indices.begin(),
                output_promotion_label_indices.end()).size() !=
                label_offsets.size() ||
            *std::max_element(
                output_promotion_label_indices.begin(),
                output_promotion_label_indices.end()) >=
                label_offsets.size()) {
            throw std::runtime_error(
                "output promotion label mapping is not one public "
                "four-position permutation");
        }
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
         subspace_value_orbit_mode ||
         model_weight_value_orbit_mode ||
         output_driven_carrier_mode)
            ? spec.contains("orbit_attention_layers")
                ? parse_layer_selection(
                    spec, "orbit_attention_layers", attention_layer_ids)
                : all_attention_layers
            : all_attention_layers;
    if (paired_complex_attention_read &&
        orbit_attention_layers !=
            std::set<uint32_t>{
                static_cast<uint32_t>(
                    paired_complex_attention_layer)}) {
        throw std::runtime_error(
            "paired-complex read requires the value-phase action and "
            "read to share one frozen attention layer");
    }
    const bool layer_selective_value_orbit =
        (value_orbit_mode ||
         fourier_value_orbit_mode ||
         subspace_value_orbit_mode ||
         model_weight_value_orbit_mode) &&
        orbit_attention_layers != all_attention_layers;
    model_weight_value_operator_build
        model_weight_operator_build;
    if (model_weight_value_orbit_mode) {
        std::vector<llama_token> semantic_tokens;
        semantic_tokens.reserve(label_offsets.size());
        for (const size_t offset : label_offsets) {
            semantic_tokens.push_back(
                variant_g_tokens.at(0).at(offset));
        }
        model_weight_operator_build =
            build_model_weight_value_operator(
                ctx,
                orbit_attention_layers,
                semantic_tokens);
        if (model_weight_operator_build.value_operator.layers.size() !=
                orbit_attention_layers.size() ||
            model_weight_operator_build.value_operator
                .calibration_samples != semantic_tokens.size() ||
            model_weight_operator_build.value_operator
                .maximum_layer_rank > 3 ||
            model_weight_operator_build.value_operator
                .training_contexts != 1) {
            throw std::runtime_error(
                "weight-derived semantic operator invariant failed");
        }
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
    const auto timed_decode_terminal =
            [&](const std::vector<llama_token> & tokens,
                llama_pos start_pos,
                llama_seq_id seq_id) {
        const auto started = std::chrono::steady_clock::now();
        decode_tokens(ctx, tokens, start_pos, true, seq_id);
        llama_synchronize(ctx);
        return std::chrono::duration<double, std::milli>(
            std::chrono::steady_clock::now() - started).count();
    };

    semantic_carrier_adapter_build semantic_adapter_build;
    json semantic_training_records = json::array();
    size_t semantic_training_sample_count = 0;
    size_t semantic_training_source_tokens = 0;
    size_t semantic_training_query_tokens = 0;
    size_t semantic_training_output_tokens = 0;
    uint64_t semantic_training_feature_peak_bytes = 0;
    uint64_t semantic_carrier_backing_initial = 0;
    json semantic_optimizer_records = json::array();
    uint64_t semantic_optimizer_steps = 0;
    uint64_t semantic_optimizer_parameter_bytes = 0;
    uint64_t semantic_optimizer_scheduler_compute_bytes_initial = 0;
    uint64_t semantic_optimizer_scheduler_compute_bytes_peak = 0;
    double semantic_optimizer_loss_first = 0.0;
    double semantic_optimizer_loss_last = 0.0;
    size_t semantic_optimizer_predicted_target_count = 0;
    size_t semantic_optimizer_source_tokens = 0;
    size_t semantic_optimizer_query_tokens = 0;
    size_t semantic_optimizer_output_tokens = 0;
    uint64_t semantic_optimizer_output_map_initial_hash = 0;
    uint64_t semantic_optimizer_output_map_hash = 0;
    if (trained_semantic_carrier_mode) {
        const auto & training_contexts =
            spec.at(
                output_written_carrier_mode
                    ? "output_written_port_training_contexts"
                    : "carrier_adapter_training_contexts");
        const double ridge_fraction =
            spec.at("carrier_adapter_ridge_fraction").get<double>();
        const double output_gain =
            output_written_carrier_mode
                ? 1.0
                : spec.at("carrier_adapter_output_gain").get<double>();
        if (!training_contexts.is_array() ||
            training_contexts.size() < 2) {
            throw std::runtime_error(
                "semantic carrier requires multiple training contexts");
        }
        std::vector<semantic_carrier_training_sample>
            training_samples;
        std::vector<semantic_carrier_writer_sample>
            writer_samples;
        for (const auto & training_context : training_contexts) {
            llama_memory_clear(memory, true);
            llama_synchronize(ctx);
            const std::string training_id =
                training_context.at("id").get<std::string>();
            const auto training_f_tokens = tokenize_piece(
                vocab,
                training_context.at("module_f").get<std::string>(),
                false,
                true);
            std::vector<llama_token> training_source;
            training_source.reserve(
                prefix_tokens.size() +
                training_f_tokens.size() +
                structural_g_tokens.size() +
                closure_tokens.size());
            training_source.insert(
                training_source.end(),
                prefix_tokens.begin(),
                prefix_tokens.end());
            training_source.insert(
                training_source.end(),
                training_f_tokens.begin(),
                training_f_tokens.end());
            training_source.insert(
                training_source.end(),
                output_written_carrier_mode
                    ? variant_g_tokens.at(0).begin()
                    : structural_g_tokens.begin(),
                output_written_carrier_mode
                    ? variant_g_tokens.at(0).end()
                    : structural_g_tokens.end());
            training_source.insert(
                training_source.end(),
                closure_tokens.begin(),
                closure_tokens.end());
            if (training_source.size() != expected_source_tokens ||
                training_context.at("queries").size() != 4) {
                throw std::runtime_error(
                    "semantic carrier training token geometry mismatch");
            }
            timed_decode(training_source, 0, f_seq);
            semantic_training_source_tokens +=
                training_source.size();
            require_component_positions(
                f_seq,
                source_boundary_pos,
                source_boundary_pos,
                training_id + ":training-source");
            const size_t context_sample_begin =
                training_samples.size();
            size_t query_index = 0;
            for (const auto & query :
                 training_context.at("queries")) {
                const uint32_t vault_ordinal =
                    query.at("vault_ordinal").get<uint32_t>();
                if (vault_ordinal >= 4) {
                    throw std::runtime_error(
                        "semantic carrier training ordinal is invalid");
                }
                copy_full_sequence(
                    f_seq,
                    work_seq,
                    source_boundary_pos,
                    training_id + ":training-query-copy");
                const auto boundary = decode_query(
                    ctx,
                    vocab,
                    candidates,
                    "semantic-carrier-training-base",
                    training_id,
                    query,
                    expected_source_tokens,
                    active_recurrent_backing_initial,
                    active_hybrid_backend_allocation_bytes(ctx),
                    work_seq,
                    !semantic_carrier_layer_delta_mode,
                    semantic_carrier_read_layer,
                    semantic_carrier_layer_delta_mode,
                    false);
                semantic_training_query_tokens +=
                    boundary.record.at("query_tokens")
                        .get<size_t>();
                semantic_training_records.push_back(
                    boundary.record);
                semantic_carrier_training_sample sample;
                sample.embedding =
                    semantic_carrier_layer_delta_mode
                        ? boundary.layer_embedding
                        : boundary.embedding;
                sample.vault_ordinal = vault_ordinal;
                sample.output_code_ordinal = vault_ordinal;
                if (output_written_carrier_mode) {
                    const auto destinations =
                        training_context.at(
                            "output_promotion_label_indices")
                            .get<std::vector<uint32_t>>();
                    if (destinations.size() != 4 ||
                        destinations[query_index] >= 4) {
                        throw std::runtime_error(
                            "semantic port training topology is invalid");
                    }
                    sample.port_destination =
                        destinations[query_index];
                    if (semantic_carrier_layer_delta_mode) {
                        sample.next_output_ordinal = 0;
                    } else {
                        sample.next_output_ordinal =
                            query.at("next_output_ordinal")
                                .get<uint32_t>();
                    }
                    if ((!semantic_carrier_layer_delta_mode &&
                         sample.next_output_ordinal >= 4) ||
                        boundary.argmax.size() != 1 ||
                        boundary.argmax[0] < 'A' ||
                        boundary.argmax[0] > 'D' ||
                        (!semantic_carrier_layer_delta_mode &&
                         boundary.argmax !=
                            query.at("expected")
                                .get<std::string>())) {
                        throw std::runtime_error(
                            "semantic port construction capability failed");
                    }
                    for (size_t i = 0; i < 4; ++i) {
                        sample.candidate_logits[i] =
                            boundary.candidate_logits.at(i);
                    }
                    const uint32_t output_ordinal =
                        static_cast<uint32_t>(
                            boundary.argmax[0] - 'A');
                    semantic_carrier_writer_sample writer_sample;
                    writer_sample.output_ordinal =
                        output_ordinal;
                    if (!output_phase_memory_mode) {
                        const llama_pos output_position =
                            static_cast<llama_pos>(
                                expected_source_tokens +
                                boundary.record.at("query_tokens")
                                    .get<size_t>());
                        timed_decode_terminal(
                            std::vector<llama_token>{
                                candidates.at(output_ordinal)},
                            output_position,
                            work_seq);
                        ++semantic_training_output_tokens;
                        const float * output_embedding =
                            semantic_carrier_layer_delta_mode
                                ? llama_get_embeddings_layer_inp(
                                    ctx,
                                    static_cast<uint32_t>(
                                        semantic_carrier_read_layer))
                                : llama_get_embeddings_ith(ctx, -1);
                        if (!output_embedding) {
                            throw std::runtime_error(
                                "semantic port writer state is absent");
                        }
                        writer_sample.embedding.assign(
                            output_embedding,
                            output_embedding +
                                ctx->get_model().hparams.n_embd_out());
                    }
                    writer_samples.push_back(
                        std::move(writer_sample));
                }
                training_samples.push_back(std::move(sample));
                semantic_training_feature_peak_bytes =
                    std::max<uint64_t>(
                        semantic_training_feature_peak_bytes,
                        training_samples.capacity() *
                            sizeof(
                                semantic_carrier_training_sample) +
                        training_samples.size() *
                            (semantic_carrier_layer_delta_mode
                                ? boundary.layer_embedding.size()
                                : boundary.embedding.size()) *
                            sizeof(float));
                close_sequence(
                    work_seq,
                    training_id + ":training-query-close");
                ++query_index;
            }
            if (output_written_carrier_mode &&
                semantic_carrier_layer_delta_mode) {
                std::array<uint32_t, 4> output_by_destination = {};
                std::array<bool, 4> destination_present = {};
                for (size_t i = 0; i < 4; ++i) {
                    const auto & sample =
                        training_samples.at(
                            context_sample_begin + i);
                    const auto & writer =
                        writer_samples.at(
                            context_sample_begin + i);
                    if (sample.port_destination >= 4 ||
                        writer.output_ordinal >= 4 ||
                        destination_present[
                            sample.port_destination]) {
                        throw std::runtime_error(
                            "semantic port construction topology is not "
                            "one public permutation");
                    }
                    output_by_destination[
                        sample.port_destination] =
                        writer.output_ordinal;
                    destination_present[
                        sample.port_destination] = true;
                }
                if (!std::all_of(
                        destination_present.begin(),
                        destination_present.end(),
                        [](bool present) { return present; })) {
                    throw std::runtime_error(
                        "semantic port construction topology is incomplete");
                }
                for (size_t i = 0; i < 4; ++i) {
                    auto & sample =
                        training_samples.at(
                            context_sample_begin + i);
                    sample.output_code_ordinal =
                        output_by_destination[
                            sample.vault_ordinal];
                    sample.next_output_ordinal =
                        sample.output_code_ordinal;
                }
            }
            close_sequence(
                f_seq,
                training_id + ":training-source-close");
            if (semantic_carrier_layer_delta_mode &&
                (end_to_end_semantic_carrier_training ||
                 output_written_hidden_slot_mode)) {
                for (size_t i = 0; i < 4; ++i) {
                    auto & sample =
                        training_samples.at(
                            context_sample_begin + i);
                    sample.target_delta.assign(
                        sample.embedding.size(),
                        0.0f);
                }
            } else if (semantic_carrier_layer_delta_mode) {
                std::vector<llama_token> target_source;
                target_source.reserve(expected_source_tokens);
                target_source.insert(
                    target_source.end(),
                    prefix_tokens.begin(),
                    prefix_tokens.end());
                target_source.insert(
                    target_source.end(),
                    training_f_tokens.begin(),
                    training_f_tokens.end());
                target_source.insert(
                    target_source.end(),
                    variant_g_tokens.at(
                            output_written_carrier_mode
                            ? spec.at(
                                "output_written_port_target_variant_index")
                                .get<size_t>()
                            : 0).begin(),
                    variant_g_tokens.at(
                        output_written_carrier_mode
                            ? spec.at(
                                "output_written_port_target_variant_index")
                                .get<size_t>()
                            : 0).end());
                target_source.insert(
                    target_source.end(),
                    closure_tokens.begin(),
                    closure_tokens.end());
                if (target_source.size() != expected_source_tokens) {
                    throw std::runtime_error(
                        "semantic carrier target token geometry mismatch");
                }
                timed_decode(target_source, 0, f_seq);
                semantic_training_source_tokens +=
                    target_source.size();
                require_component_positions(
                    f_seq,
                    source_boundary_pos,
                    source_boundary_pos,
                    training_id + ":target-source");
                size_t query_index = 0;
                for (const auto & query :
                     training_context.at("queries")) {
                    copy_full_sequence(
                        f_seq,
                        work_seq,
                        source_boundary_pos,
                        training_id + ":target-query-copy");
                    const auto boundary = decode_query(
                        ctx,
                        vocab,
                        candidates,
                        "semantic-carrier-training-target",
                        training_id,
                        query,
                        expected_source_tokens,
                        active_recurrent_backing_initial,
                        active_hybrid_backend_allocation_bytes(ctx),
                        work_seq,
                        false,
                        semantic_carrier_read_layer,
                        true,
                        false);
                    semantic_training_query_tokens +=
                        boundary.record.at("query_tokens")
                            .get<size_t>();
                    semantic_training_records.push_back(
                        boundary.record);
                    auto & sample =
                        training_samples.at(
                            context_sample_begin + query_index);
                    if (boundary.layer_embedding.size() !=
                            sample.embedding.size()) {
                        throw std::runtime_error(
                            "semantic carrier layer delta width mismatch");
                    }
                    sample.target_delta.resize(
                        sample.embedding.size());
                    for (size_t j = 0;
                         j < sample.embedding.size();
                         ++j) {
                        sample.target_delta[j] =
                            boundary.layer_embedding[j] -
                            sample.embedding[j];
                    }
                    ++query_index;
                    close_sequence(
                        work_seq,
                        training_id + ":target-query-close");
                }
                close_sequence(
                    f_seq,
                    training_id + ":target-source-close");
                uint64_t sample_bytes = 0;
                for (const auto & sample : training_samples) {
                    sample_bytes +=
                        (sample.embedding.capacity() +
                         sample.target_delta.capacity()) *
                        sizeof(float);
                }
                semantic_training_feature_peak_bytes =
                    std::max<uint64_t>(
                        semantic_training_feature_peak_bytes,
                        training_samples.capacity() *
                            sizeof(
                                semantic_carrier_training_sample) +
                        sample_bytes);
            }
        }
        uint64_t retained_training_feature_bytes =
            training_samples.capacity() *
                sizeof(semantic_carrier_training_sample) +
            writer_samples.capacity() *
                sizeof(semantic_carrier_writer_sample);
        for (const auto & sample : training_samples) {
            retained_training_feature_bytes +=
                (sample.embedding.capacity() +
                 sample.target_delta.capacity()) *
                sizeof(float);
        }
        for (const auto & sample : writer_samples) {
            retained_training_feature_bytes +=
                sample.embedding.capacity() * sizeof(float);
        }
        semantic_training_feature_peak_bytes =
            std::max(
                semantic_training_feature_peak_bytes,
                retained_training_feature_bytes);
        semantic_training_sample_count =
            training_samples.size();
        semantic_adapter_build =
            build_semantic_carrier_adapter(
                ctx,
                candidates,
                training_samples,
                ridge_fraction,
                output_gain,
                semantic_carrier_layer_delta_mode);
        if (output_written_semantic_port_mode) {
            complete_output_written_semantic_port(
                ctx,
                candidates,
                training_samples,
                writer_samples,
                ridge_fraction,
                semantic_carrier_layer_delta_mode,
                semantic_carrier_layer_delta_mode
                    ? 0.0
                    : spec.at(
                        "output_written_port_training_margin")
                        .get<double>(),
                semantic_carrier_layer_delta_mode
                    ? 0.0
                    : spec.at(
                        "output_written_port_maximum_gain")
                        .get<double>(),
                &semantic_adapter_build);
        }
        if (output_phase_memory_mode) {
            complete_output_phase_memory(
                ctx,
                candidates,
                training_samples,
                writer_samples,
                spec.at("phase_memory_width")
                    .get<uint32_t>(),
                spec.at("phase_memory_seed")
                    .get<uint64_t>(),
                output_phase_orbit_memory_mode,
                spec.at(
                    "output_written_port_training_margin")
                    .get<double>(),
                spec.at(
                    "output_written_port_maximum_gain")
                    .get<double>(),
                &semantic_adapter_build);
        }
        if (output_written_hidden_slot_mode) {
            semantic_adapter_build.writer_map.clear();
            semantic_adapter_build.writer_map.shrink_to_fit();
            semantic_adapter_build.writer_bias.fill(0.0f);
            semantic_adapter_build.output_map.clear();
            semantic_adapter_build.output_map.shrink_to_fit();
            semantic_adapter_build.logical_bytes =
                (semantic_adapter_build.query_map.size() +
                 semantic_adapter_build.query_bias.size()) *
                sizeof(float);
            uint64_t hidden_slot_hash =
                UINT64_C(1469598103934665603);
            fnv1a64_update(
                hidden_slot_hash,
                semantic_adapter_build.query_map.data(),
                semantic_adapter_build.query_map.size() *
                    sizeof(float));
            fnv1a64_update(
                hidden_slot_hash,
                semantic_adapter_build.query_bias.data(),
                semantic_adapter_build.query_bias.size() *
                    sizeof(float));
            semantic_adapter_build.hash = hidden_slot_hash;
        }
        const bool installed =
            output_phase_memory_mode
                ? ctx->install_neo3000_output_phase_memory(
                    std::move(semantic_adapter_build.query_map),
                    semantic_adapter_build.query_bias,
                    std::move(semantic_adapter_build.output_map),
                    std::move(
                        semantic_adapter_build.phase_binding_table),
                    std::move(
                        semantic_adapter_build.phase_reader),
                    std::move(
                        semantic_adapter_build.phase_generator),
                    semantic_adapter_build.phase_width)
            : output_written_hidden_slot_mode
                ? ctx->install_neo3000_output_written_hidden_slots(
                    std::move(semantic_adapter_build.query_map),
                    semantic_adapter_build.query_bias,
                    semantic_carrier_read_layer)
            : output_written_semantic_port_mode
                ? ctx->install_neo3000_output_written_semantic_port(
                    std::move(semantic_adapter_build.query_map),
                    semantic_adapter_build.query_bias,
                    std::move(semantic_adapter_build.writer_map),
                    semantic_adapter_build.writer_bias,
                    std::move(semantic_adapter_build.output_map),
                    semantic_carrier_read_layer,
                    semantic_carrier_moe_router_bias_mode,
                    semantic_carrier_recurrent_transition_mode)
                : ctx->install_neo3000_semantic_carrier(
                    std::move(semantic_adapter_build.query_map),
                    semantic_adapter_build.query_bias,
                    std::move(semantic_adapter_build.output_map),
                    semantic_carrier_read_layer);
        if (!installed ||
            (!output_written_carrier_mode &&
             !ctx->set_neo3000_semantic_carrier_phase(0)) ||
            !ctx->set_neo3000_semantic_carrier_enabled(false)) {
            throw std::runtime_error(
                "semantic carrier installation failed");
        }
        const auto * carrier =
            ctx->get_neo3000_semantic_carrier();
        if (!carrier ||
            carrier->phase != 0 ||
            carrier->enabled ||
            carrier->output_written !=
                output_written_carrier_mode ||
            carrier->output_hidden_slots !=
                output_written_hidden_slot_mode ||
            carrier->output_phase_memory !=
                output_phase_memory_mode ||
            carrier->native_phase_orbit !=
                output_phase_orbit_memory_mode ||
            carrier->moe_router_bias !=
                semantic_carrier_moe_router_bias_mode ||
            carrier->recurrent_transition_input !=
                semantic_carrier_recurrent_transition_mode ||
            carrier->read_layer != semantic_carrier_read_layer ||
            carrier->action_backing_id == 0) {
            throw std::runtime_error(
                "semantic carrier installation invariant failed");
        }
        semantic_carrier_backing_initial =
            carrier->action_backing_id;
        if (end_to_end_semantic_carrier_training) {
            semantic_optimizer_output_map_initial_hash =
                fnv1a64(
                    carrier->output_map.data(),
                    carrier->output_map.size() * sizeof(float));
        }
        if (end_to_end_semantic_carrier_training) {
            const uint32_t epochs =
                spec.at("semantic_carrier_optimizer_epochs")
                    .get<uint32_t>();
            const float learning_rate =
                spec.at("semantic_carrier_optimizer_learning_rate")
                    .get<float>();
            const uint32_t target_variant =
                spec.at(
                    "semantic_carrier_optimizer_target_variant")
                    .get<uint32_t>();
            if (epochs == 0 ||
                epochs > 16 ||
                !std::isfinite(learning_rate) ||
                learning_rate <= 0.0f ||
                target_variant == 0 ||
                target_variant >= variants.size()) {
                throw std::runtime_error(
                    "semantic carrier optimizer schedule is invalid");
            }

            const auto & optimizer_contexts =
                spec.at("output_written_port_training_contexts");
            for (uint32_t epoch = 0; epoch < epochs; ++epoch) {
                size_t context_index = 0;
                for (const auto & training_context :
                     optimizer_contexts) {
                    llama_memory_clear(memory, true);
                    llama_synchronize(ctx);
                    if (!ctx->set_neo3000_semantic_carrier_enabled(
                            false) ||
                        !ctx->reset_neo3000_semantic_port()) {
                        throw std::runtime_error(
                            "semantic carrier optimizer reset failed");
                    }
                    const std::string training_id =
                        training_context.at("id")
                            .get<std::string>();
                    const auto training_f_tokens = tokenize_piece(
                        vocab,
                        training_context.at("module_f")
                            .get<std::string>(),
                        false,
                        true);
                    std::vector<llama_token> training_source;
                    training_source.reserve(expected_source_tokens);
                    training_source.insert(
                        training_source.end(),
                        prefix_tokens.begin(),
                        prefix_tokens.end());
                    training_source.insert(
                        training_source.end(),
                        training_f_tokens.begin(),
                        training_f_tokens.end());
                    training_source.insert(
                        training_source.end(),
                        variant_g_tokens.at(0).begin(),
                        variant_g_tokens.at(0).end());
                    training_source.insert(
                        training_source.end(),
                        closure_tokens.begin(),
                        closure_tokens.end());
                    if (training_source.size() !=
                        expected_source_tokens) {
                        throw std::runtime_error(
                            training_id +
                            ": optimizer source geometry mismatch");
                    }
                    timed_decode(training_source, 0, f_seq);
                    semantic_optimizer_source_tokens +=
                        training_source.size();
                    require_component_positions(
                        f_seq,
                        source_boundary_pos,
                        source_boundary_pos,
                        training_id +
                            ":optimizer-source");

                    const auto destinations =
                        training_context.at(
                            "output_promotion_label_indices")
                            .get<std::vector<uint32_t>>();
                    const auto & queries =
                        training_context.at("queries");
                    if (destinations.size() != queries.size() ||
                        queries.size() != 4) {
                        throw std::runtime_error(
                            training_id +
                            ": optimizer topology mismatch");
                    }
                    size_t query_index = 0;
                    for (const auto & query : queries) {
                        copy_full_sequence(
                            f_seq,
                            work_seq,
                            source_boundary_pos,
                            training_id +
                                ":optimizer-writer-copy");
                        const auto boundary = decode_query(
                            ctx,
                            vocab,
                            candidates,
                            "semantic-carrier-optimizer-writer",
                            training_id,
                            query,
                            expected_source_tokens,
                            active_recurrent_backing_initial,
                            active_hybrid_backend_allocation_bytes(ctx),
                            work_seq,
                            false,
                            semantic_carrier_read_layer,
                            true,
                            false);
                        const std::string expected =
                            query.at("expected")
                                .get<std::string>();
                        if (boundary.argmax != expected ||
                            destinations.at(query_index) >= 4) {
                            throw std::runtime_error(
                                training_id +
                                ": optimizer writer capability failed");
                        }
                        semantic_optimizer_query_tokens +=
                            boundary.record.at("query_tokens")
                                .get<size_t>();
                        const size_t output_ordinal =
                            static_cast<size_t>(
                                boundary.argmax[0] - 'A');
                        const llama_pos output_position =
                            static_cast<llama_pos>(
                                expected_source_tokens +
                                boundary.record.at("query_tokens")
                                    .get<size_t>());
                        timed_decode_terminal(
                            std::vector<llama_token>{
                                candidates.at(output_ordinal)},
                            output_position,
                            work_seq);
                        ++semantic_optimizer_output_tokens;
                        const float * output_state =
                            llama_get_embeddings_layer_inp(
                                ctx,
                                static_cast<uint32_t>(
                                    semantic_carrier_read_layer));
                        if (!output_state ||
                            !ctx->write_neo3000_semantic_port(
                                output_state,
                                ctx->get_model().hparams.n_embd_out(),
                                destinations.at(query_index))) {
                            throw std::runtime_error(
                                training_id +
                                ": optimizer writer state failed");
                        }
                        close_sequence(
                            work_seq,
                            training_id +
                                ":optimizer-writer-close");
                        ++query_index;
                    }
                    query_index = 0;
                    for (const auto & query : queries) {
                        copy_full_sequence(
                            f_seq,
                            work_seq,
                            source_boundary_pos,
                            training_id +
                                ":optimizer-reader-copy");
                        const auto suffix_tokens = tokenize_piece(
                            vocab,
                            query.at("suffix")
                                .get<std::string>(),
                            false,
                            true);
                        if (suffix_tokens.empty()) {
                            throw std::runtime_error(
                                training_id +
                                ": optimizer query is empty");
                        }
                        if (suffix_tokens.size() > 1) {
                            timed_decode(
                                token_slice(
                                    suffix_tokens,
                                    0,
                                    suffix_tokens.size() - 1),
                                static_cast<llama_pos>(
                                    expected_source_tokens),
                                work_seq);
                        }
                        semantic_optimizer_query_tokens +=
                            suffix_tokens.size();
                        const std::string expected_g0 =
                            query.at("expected")
                                .get<std::string>();
                        if (expected_g0.size() != 1 ||
                            expected_g0[0] < 'A' ||
                            expected_g0[0] > 'D') {
                            throw std::runtime_error(
                                training_id +
                                ": optimizer target is invalid");
                        }
                        const size_t target_ordinal =
                            (static_cast<size_t>(
                                 expected_g0[0] - 'A') +
                             target_variant) %
                            candidates.size();
                        auto batch = llama_batch_init(1, 0, 1);
                        common_batch_add(
                            batch,
                            suffix_tokens.back(),
                            static_cast<llama_pos>(
                                expected_source_tokens +
                                suffix_tokens.size() - 1),
                            {work_seq},
                            true);
                        if (!ctx->set_neo3000_semantic_carrier_enabled(
                                true)) {
                            llama_batch_free(batch);
                            throw std::runtime_error(
                                training_id +
                                ": optimizer carrier enable failed");
                        }
                        llama_neo3000_semantic_optimizer_metrics
                            metrics = {};
                        const auto step_started =
                            std::chrono::steady_clock::now();
                        const int status =
                            ctx
                                ->optimize_neo3000_semantic_carrier_output_map(
                                    batch,
                                    candidates.at(target_ordinal),
                                    learning_rate,
                                    &metrics);
                        llama_batch_free(batch);
                        if (!ctx->set_neo3000_semantic_carrier_enabled(
                                false)) {
                            throw std::runtime_error(
                                training_id +
                                ": optimizer carrier disable failed");
                        }
                        const double wall_ms =
                            std::chrono::duration<double, std::milli>(
                                std::chrono::steady_clock::now() -
                                step_started).count();
                        if (status != 0 ||
                            !std::isfinite(metrics.loss) ||
                            metrics.parameter_bytes == 0) {
                            throw std::runtime_error(
                                training_id +
                                ": semantic carrier optimizer failed "
                                "with status " +
                                std::to_string(status));
                        }
                        if (semantic_optimizer_steps == 0) {
                            semantic_optimizer_loss_first =
                                metrics.loss;
                            semantic_optimizer_parameter_bytes =
                                metrics.parameter_bytes;
                            semantic_optimizer_scheduler_compute_bytes_initial =
                                metrics
                                    .scheduler_compute_bytes_before;
                        } else if (
                            semantic_optimizer_parameter_bytes !=
                                metrics.parameter_bytes) {
                            throw std::runtime_error(
                                "semantic carrier optimizer parameter "
                                "size changed");
                        }
                        semantic_optimizer_loss_last = metrics.loss;
                        semantic_optimizer_scheduler_compute_bytes_peak =
                            std::max(
                                semantic_optimizer_scheduler_compute_bytes_peak,
                                metrics
                                    .scheduler_compute_bytes_after);
                        semantic_optimizer_predicted_target_count +=
                            metrics.predicted_token ==
                                candidates.at(target_ordinal);
                        ++semantic_optimizer_steps;
                        semantic_optimizer_records.push_back({
                            {"epoch", epoch},
                            {"training_context", training_id},
                            {"context_index", context_index},
                            {"query_id", query.at("id")},
                            {"query_index", query_index},
                            {"target_variant", target_variant},
                            {"target",
                                std::string(
                                    1,
                                    static_cast<char>(
                                        'A' + target_ordinal))},
                            {"predicted_token",
                                metrics.predicted_token},
                            {"target_token",
                                candidates.at(target_ordinal)},
                            {"loss", metrics.loss},
                            {"learning_rate", learning_rate},
                            {"parameter_bytes",
                                metrics.parameter_bytes},
                            {"scheduler_compute_bytes_before",
                                metrics
                                    .scheduler_compute_bytes_before},
                            {"scheduler_compute_bytes_after",
                                metrics
                                    .scheduler_compute_bytes_after},
                            {"wall_ms", wall_ms},
                        });
                        close_sequence(
                            work_seq,
                            training_id +
                                ":optimizer-reader-close");
                        ++query_index;
                    }
                    if (!ctx->set_neo3000_semantic_carrier_enabled(
                            false) ||
                        !ctx->reset_neo3000_semantic_port()) {
                        throw std::runtime_error(
                            training_id +
                            ": optimizer close failed");
                    }
                    close_sequence(
                        f_seq,
                        training_id +
                            ":optimizer-source-close");
                    ++context_index;
                }
            }
            const auto * optimized =
                ctx->get_neo3000_semantic_carrier();
            if (!optimized ||
                optimized->optimizer_steps !=
                    semantic_optimizer_steps) {
                throw std::runtime_error(
                    "semantic carrier optimizer accounting mismatch");
            }
            semantic_optimizer_output_map_hash =
                fnv1a64(
                    optimized->output_map.data(),
                    optimized->output_map.size() *
                        sizeof(float));
        }
        training_samples.clear();
        training_samples.shrink_to_fit();
        llama_memory_clear(memory, true);
        llama_synchronize(ctx);
    }
    if (output_depth_memory_mode) {
        if (candidates.size() != 4 ||
            !ctx->install_neo3000_output_depth_memory() ||
            !ctx->set_neo3000_semantic_carrier_enabled(false) ||
            !ctx->set_neo3000_depth_layer_offset(0)) {
            throw std::runtime_error(
                "depth-resolved output memory installation failed");
        }
        const auto * carrier =
            ctx->get_neo3000_semantic_carrier();
        if (!carrier ||
            !carrier->output_depth_memory ||
            !carrier->output_written ||
            carrier->enabled ||
            carrier->depth_memory_poisoned ||
            carrier->depth_capture_destination != -1 ||
            carrier->depth_staging_writes != 0 ||
            carrier->depth_staging_destination_mask != 0 ||
            carrier->depth_layers.size() != 10 ||
            carrier->depth_active_layers.size() != 10 ||
            carrier->depth_staging_slots.size() != 40 ||
            carrier->depth_memory_backend_bytes == 0 ||
            carrier->action_backing_id == 0) {
            throw std::runtime_error(
                "depth-resolved output memory invariant failed");
        }
        semantic_carrier_backing_initial =
            carrier->action_backing_id;
        ctx->sched_reserve();
    }
    if (output_continuous_soft_role_rematerialization_mode) {
        if (candidates.size() != 4) {
            throw std::runtime_error(
                "continuous soft-role carrier requires four candidates");
        }
        const std::array<llama_token, 4> candidate_array = {
            candidates.at(0),
            candidates.at(1),
            candidates.at(2),
            candidates.at(3),
        };
        if (!ctx->install_neo3000_continuous_soft_role_memory(
                candidate_array)) {
            throw std::runtime_error(
                "continuous soft-role carrier installation failed");
        }
        const auto * carrier =
            ctx->get_neo3000_semantic_carrier();
        if (!carrier ||
            !carrier->continuous_soft_role_memory ||
            carrier->soft_role_poisoned ||
            carrier->soft_role_capture_destination != -1 ||
            carrier->soft_role_read_slot != -1 ||
            carrier->soft_role_backend_bytes == 0 ||
            carrier->action_backing_id == 0) {
            throw std::runtime_error(
                "continuous soft-role carrier invariant failed");
        }
        semantic_carrier_backing_initial =
            carrier->action_backing_id;
        ctx->sched_reserve();
    }

    llama_kv_cache::role_transport_operator
        role_transport_operator;
    llama_kv_cache::role_generator_operator
        role_generator_operator;
    llama_kv_cache::role_generator_metrics
        role_generator_finalize_metrics = {};
    llama_kv_cache::attention_kernel_writer_operator
        attention_kernel_writer_operator;
    llama_kv_cache::attention_kernel_writer_metrics
        attention_kernel_writer_finalize_metrics = {};
    uint64_t role_generator_runtime_parameter_upload_bytes = 0;
    uint64_t role_generator_runtime_graph_applications = 0;
    uint64_t role_generator_runtime_generated_rows = 0;
    uint64_t role_generator_runtime_multiply_accumulates = 0;
    uint64_t attention_kernel_writer_runtime_parameter_upload_bytes = 0;
    uint64_t attention_kernel_writer_runtime_graph_applications = 0;
    uint64_t attention_kernel_writer_runtime_generated_rows = 0;
    uint64_t attention_kernel_writer_runtime_multiply_accumulates = 0;
    json role_transport_training_records = json::array();
    size_t role_transport_training_source_tokens = 0;
    size_t role_transport_training_query_tokens = 0;
    size_t role_transport_training_output_tokens = 0;
    size_t role_transport_training_correct = 0;
    uint64_t role_transport_training_host_read_bytes = 0;
    uint64_t role_transport_training_peak_host_work_bytes = 0;
    uint64_t role_transport_builder_peak_bytes = 0;
    uint64_t role_transport_finalize_peak_host_work_bytes = 0;
    if (output_role_transport_mode ||
        output_role_generator_mode ||
        output_attention_kernel_writer_mode) {
        const char * training_context_key =
            output_attention_kernel_writer_mode
                ? "attention_kernel_writer_training_contexts"
            : output_role_generator_mode
                ? "role_generator_training_contexts"
                : "role_transport_training_contexts";
        const char * ridge_key =
            output_attention_kernel_writer_mode
                ? "attention_kernel_writer_ridge_fraction"
            : output_role_generator_mode
                ? "role_generator_ridge_fraction"
                : "role_transport_ridge_fraction";
        const auto & training_contexts =
            spec.at(training_context_key);
        const double ridge_fraction =
            spec.at(ridge_key)
                .get<double>();
        if (!training_contexts.is_array() ||
            training_contexts.size() < 2) {
            throw std::runtime_error(
                "role transport requires multiple construction contexts");
        }
        const uint32_t destination_count =
            static_cast<uint32_t>(label_offsets.size());
        const uint32_t samples_per_destination =
            static_cast<uint32_t>(
                training_contexts.size() *
                variants.size());
        std::vector<uint32_t> samples_by_destination(
            destination_count, 0);
        llama_kv_cache::role_transport_builder builder;
        for (const auto & training_context : training_contexts) {
            const std::string training_id =
                training_context.at("id").get<std::string>();
            const auto training_f_tokens = tokenize_piece(
                vocab,
                training_context.at("module_f")
                    .get<std::string>(),
                false,
                true);
            const auto training_mapping =
                training_context.at(
                    "output_promotion_label_indices")
                    .get<std::vector<size_t>>();
            const auto & training_queries =
                training_context.at("queries");
            if (training_f_tokens.size() != f_tokens.size() ||
                training_queries.size() != label_offsets.size() ||
                training_mapping.size() != label_offsets.size() ||
                std::set<size_t>(
                    training_mapping.begin(),
                    training_mapping.end()).size() !=
                    label_offsets.size() ||
                *std::max_element(
                    training_mapping.begin(),
                    training_mapping.end()) >=
                    label_offsets.size()) {
                throw std::runtime_error(
                    training_id +
                    ": role transport construction geometry mismatch");
            }
            for (size_t phase = 0;
                 phase < variants.size();
                 ++phase) {
                llama_memory_clear(memory, true);
                llama_synchronize(ctx);
                const size_t next_phase =
                    (phase + 1) % variants.size();
                std::vector<llama_token> current_source;
                std::vector<llama_token> target_source;
                for (auto * source :
                     {&current_source, &target_source}) {
                    source->reserve(expected_source_tokens);
                    source->insert(
                        source->end(),
                        prefix_tokens.begin(),
                        prefix_tokens.end());
                    source->insert(
                        source->end(),
                        training_f_tokens.begin(),
                        training_f_tokens.end());
                }
                current_source.insert(
                    current_source.end(),
                    variant_g_tokens.at(phase).begin(),
                    variant_g_tokens.at(phase).end());
                target_source.insert(
                    target_source.end(),
                    variant_g_tokens.at(next_phase).begin(),
                    variant_g_tokens.at(next_phase).end());
                current_source.insert(
                    current_source.end(),
                    closure_tokens.begin(),
                    closure_tokens.end());
                target_source.insert(
                    target_source.end(),
                    closure_tokens.begin(),
                    closure_tokens.end());
                if (current_source.size() != expected_source_tokens ||
                    target_source.size() != expected_source_tokens) {
                    throw std::runtime_error(
                        training_id +
                        ": role transport source size mismatch");
                }
                timed_decode(current_source, 0, f_seq);
                timed_decode(
                    target_source, 0, stage_seqs.at(0));
                role_transport_training_source_tokens +=
                    current_source.size() +
                    target_source.size();
                require_component_positions(
                    f_seq,
                    source_boundary_pos,
                    source_boundary_pos,
                    training_id +
                        ":role-current-" +
                        std::to_string(phase));
                require_component_positions(
                    stage_seqs.at(0),
                    source_boundary_pos,
                    source_boundary_pos,
                    training_id +
                        ":role-target-" +
                        std::to_string(next_phase));

                size_t query_index = 0;
                for (const auto & query : training_queries) {
                    copy_full_sequence(
                        f_seq,
                        work_seq,
                        source_boundary_pos,
                        training_id +
                            ":role-query-copy-" +
                            std::to_string(phase) + "-" +
                            std::to_string(query_index));
                    const boundary_result boundary = decode_query(
                        ctx,
                        vocab,
                        candidates,
                        "role-transport-training",
                        training_id + "-phase-" +
                            std::to_string(phase),
                        query,
                        expected_source_tokens,
                        active_recurrent_backing_initial,
                        active_hybrid_backend_allocation_bytes(ctx),
                        work_seq);
                    const size_t query_tokens =
                        boundary.record.at("query_tokens")
                            .get<size_t>();
                    role_transport_training_query_tokens +=
                        query_tokens;
                    const size_t candidate_index =
                        static_cast<size_t>(
                            boundary.argmax.at(0) - 'A');
                    if (candidate_index >= candidates.size()) {
                        throw std::runtime_error(
                            training_id +
                            ": role training output is not a candidate");
                    }
                    const size_t destination_index =
                        training_mapping.at(query_index);
                    const size_t current_vault_index =
                        (destination_index + 1) %
                            label_offsets.size();
                    const size_t expected_candidate_index =
                        (current_vault_index + phase) %
                            candidates.size();
                    const bool model_correct =
                        candidate_index ==
                        expected_candidate_index;
                    role_transport_training_correct +=
                        model_correct;
                    if (!model_correct) {
                        throw std::runtime_error(
                            training_id +
                            ": full-state construction output is wrong");
                    }
                    const llama_pos output_position =
                        static_cast<llama_pos>(
                            expected_source_tokens +
                            query_tokens);
                    timed_decode(
                        std::vector<llama_token>{
                            candidates.at(candidate_index)},
                        output_position,
                        work_seq);
                    ++role_transport_training_output_tokens;
                    const llama_pos target_position =
                        static_cast<llama_pos>(
                            f_boundary_tokens +
                            label_offsets.at(
                                destination_index));
                    llama_kv_cache::role_transport_metrics
                        collect_metrics = {};
                    const uint32_t sample_index =
                        samples_by_destination.at(
                            destination_index);
                    if (!attention->seq_collect_attention_role_pair(
                            work_seq,
                            output_position,
                            stage_seqs.at(0),
                            target_position,
                            orbit_attention_layers,
                            true,
                            static_cast<uint32_t>(
                                destination_index),
                            sample_index,
                            samples_per_destination,
                            &builder,
                            &collect_metrics)) {
                        throw std::runtime_error(
                            training_id +
                            ": role pair collection failed");
                    }
                    ++samples_by_destination.at(
                        destination_index);
                    role_transport_training_host_read_bytes +=
                        collect_metrics.host_read_bytes;
                    role_transport_training_peak_host_work_bytes =
                        std::max(
                            role_transport_training_peak_host_work_bytes,
                            collect_metrics.peak_host_work_bytes);
                    role_transport_builder_peak_bytes =
                        std::max(
                            role_transport_builder_peak_bytes,
                            collect_metrics.builder_bytes);
                    role_transport_training_records.push_back({
                        {"training_context", training_id},
                        {"phase", phase},
                        {"query_id", query.at("id")},
                        {"actual_output", boundary.argmax},
                        {"destination_index",
                            destination_index},
                        {"sample_index", sample_index},
                        {"model_correct", model_correct},
                    });
                    close_sequence(
                        work_seq,
                        training_id +
                            ":role-query-close-" +
                            std::to_string(phase) + "-" +
                            std::to_string(query_index));
                    ++query_index;
                }
                close_sequence(
                    f_seq,
                    training_id +
                        ":role-current-close-" +
                        std::to_string(phase));
                close_sequence(
                    stage_seqs.at(0),
                    training_id +
                        ":role-target-close-" +
                        std::to_string(next_phase));
            }
        }
        if (!std::all_of(
                samples_by_destination.begin(),
                samples_by_destination.end(),
                [samples_per_destination](uint32_t value) {
                    return value == samples_per_destination;
                })) {
            throw std::runtime_error(
                "role transport construction is incomplete");
        }
        if (output_attention_kernel_writer_mode) {
            if (!attention->finalize_attention_kernel_writer(
                    &builder,
                    destination_count,
                    samples_per_destination,
                    ridge_fraction,
                    &attention_kernel_writer_operator,
                    &attention_kernel_writer_finalize_metrics)) {
                throw std::runtime_error(
                    "attention kernel writer finalization failed");
            }
            role_transport_finalize_peak_host_work_bytes =
                attention_kernel_writer_finalize_metrics
                    .peak_training_host_work_bytes;
            if (attention_kernel_writer_operator.training_samples !=
                    static_cast<uint64_t>(destination_count) *
                        samples_per_destination ||
                attention_kernel_writer_operator.layers.size() !=
                    destination_count *
                        orbit_attention_layers.size() * 2 ||
                attention_kernel_writer_operator.maximum_rank !=
                    samples_per_destination) {
                throw std::runtime_error(
                    "attention kernel writer invariant failed");
            }
        } else if (output_role_generator_mode) {
            if (!attention->finalize_attention_role_generator(
                    &builder,
                    destination_count,
                    samples_per_destination,
                    spec.at("role_generator_hidden_width")
                        .get<uint32_t>(),
                    spec.at("role_generator_seed")
                        .get<uint64_t>(),
                    ridge_fraction,
                    &role_generator_operator,
                    &role_generator_finalize_metrics)) {
                throw std::runtime_error(
                    "role generator finalization failed");
            }
            role_transport_finalize_peak_host_work_bytes =
                role_generator_finalize_metrics
                    .peak_training_host_work_bytes;
            if (role_generator_operator.training_pairs !=
                    static_cast<uint64_t>(destination_count) *
                        samples_per_destination ||
                role_generator_operator.training_rows !=
                    static_cast<uint64_t>(destination_count) *
                        samples_per_destination *
                        orbit_attention_layers.size() * 2 ||
                role_generator_operator.layer_ids.size() !=
                    orbit_attention_layers.size()) {
                throw std::runtime_error(
                    "role generator invariant failed");
            }
        } else {
            llama_kv_cache::role_transport_metrics
                finalize_metrics = {};
            if (!attention->finalize_attention_role_transport(
                    &builder,
                    destination_count,
                    samples_per_destination,
                    ridge_fraction,
                    &role_transport_operator,
                    &finalize_metrics)) {
                throw std::runtime_error(
                    "role transport finalization failed");
            }
            role_transport_finalize_peak_host_work_bytes =
                finalize_metrics.peak_host_work_bytes;
            if (role_transport_operator.training_samples !=
                    static_cast<uint64_t>(destination_count) *
                        samples_per_destination ||
                role_transport_operator.layers.size() !=
                    destination_count *
                        orbit_attention_layers.size() * 2) {
                throw std::runtime_error(
                    "role transport operator invariant failed");
            }
        }
        llama_memory_clear(memory, true);
        llama_synchronize(ctx);
    }

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
    size_t output_promotion_row_count = 0;
    size_t recurrent_output_delta_extraction_count = 0;
    size_t recurrent_output_delta_accumulation_count = 0;
    size_t useful_output_decode_tokens = 0;
    size_t source_role_rematerialization_tokens = 0;
    double useful_output_decode_wall_ms_total = 0.0;
    double source_role_rematerialization_wall_ms_total = 0.0;
    size_t fourier_calibration_sample_count = 0;
    size_t subspace_calibration_sample_count = 0;
    uint64_t orbit_backend_copy_bytes = 0;
    uint64_t orbit_host_read_bytes = 0;
    uint64_t orbit_host_write_bytes = 0;
    uint64_t orbit_peak_host_work_bytes = 0;
    uint64_t orbit_tensor_visits = 0;
    uint64_t orbit_position_visits = 0;
    uint64_t recurrent_output_delta_logical_row_bytes = 0;
    uint64_t recurrent_output_delta_backend_read_bytes = 0;
    uint64_t recurrent_output_delta_backend_write_bytes = 0;
    uint64_t recurrent_output_delta_arithmetic_element_operations = 0;
    uint64_t recurrent_output_delta_tensor_visits = 0;
    uint64_t recurrent_output_delta_graph_applications = 0;
    uint64_t recurrent_output_delta_scheduler_compute_bytes_initial = 0;
    uint64_t recurrent_output_delta_scheduler_compute_bytes_peak = 0;
    int32_t recurrent_output_delta_candidate_physical_row_initial = -1;
    int32_t recurrent_output_delta_candidate_physical_row_final = -1;
    bool recurrent_output_delta_candidate_physical_row_stable = true;
    double recurrent_output_delta_extraction_wall_ms_total = 0.0;
    double recurrent_output_delta_accumulation_wall_ms_total = 0.0;
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
    json output_promotion_records = json::array();
    json recurrent_output_delta_records = json::array();
    json source_role_rematerialization_records = json::array();
    json fixed_cell_identity_records = json::array();
    std::vector<uint32_t> initial_destination_cell_ids;
    std::vector<uint32_t> final_destination_cell_ids;
    bool all_destination_cell_identities_stable = true;
    const std::string candidate_route =
        output_driven_carrier_mode
            ? output_recurrent_delta_advance_mode
                ? "actual_output_recurrent_delta_carrier"
            : output_phase_memory_mode
                ? output_phase_orbit_memory_mode
                    ? "output_phase_orbit_memory_carrier"
                    : "output_phase_memory_carrier"
            : output_depth_memory_mode
                ? "output_depth_resolved_cross_attention_memory_carrier"
            : output_written_hidden_slot_mode
                ? "output_written_hidden_slot_carrier"
            : output_written_semantic_port_mode
                ? "output_written_semantic_port_carrier"
                : output_source_fixed_cell_rematerialization_mode
                ? "output_source_position_fixed_cell_carrier"
                : output_continuous_soft_role_rematerialization_mode
                    ? "continuous_soft_output_source_role_carrier"
                : output_source_relink_rematerialization_mode
                    ? "output_source_position_rematerialization_carrier"
                : output_attention_kernel_writer_mode
                ? "output_attention_kernel_writer_carrier"
                : output_role_generator_mode
                ? "shared_nonlinear_role_generator_carrier"
                : output_role_transport_mode
                    ? "output_role_transport_carrier"
                    : "output_promoted_value_carrier"
            : orbit_mode
                ? "label_orbit_candidate"
                : "sparse_label_refresh_candidate";
    const std::string return_route =
        output_driven_carrier_mode
            ? output_recurrent_delta_advance_mode
                ? "actual_output_recurrent_delta_carrier_return_G0"
            : output_phase_memory_mode
                ? output_phase_orbit_memory_mode
                    ? "output_phase_orbit_memory_carrier_return_G0"
                    : "output_phase_memory_carrier_return_G0"
            : output_depth_memory_mode
                ? "output_depth_resolved_cross_attention_memory_carrier_return_G0"
            : output_written_hidden_slot_mode
                ? "output_written_hidden_slot_carrier_return_G0"
            : output_written_semantic_port_mode
                ? "output_written_semantic_port_carrier_return_G0"
                : output_source_fixed_cell_rematerialization_mode
                ? "output_source_position_fixed_cell_carrier_return_G0"
                : output_continuous_soft_role_rematerialization_mode
                    ? "continuous_soft_output_source_role_carrier_return_G0"
                : output_source_relink_rematerialization_mode
                    ? "output_source_position_rematerialization_carrier_return_G0"
                : output_attention_kernel_writer_mode
                ? "output_attention_kernel_writer_carrier_return_G0"
                : output_role_generator_mode
                ? "shared_nonlinear_role_generator_carrier_return_G0"
                : output_role_transport_mode
                    ? "output_role_transport_carrier_return_G0"
                    : "output_promoted_value_carrier_return_G0"
            : "label_orbit_return_G0";

    const auto project_from_source =
            [&](llama_seq_id source_seq,
                llama_seq_id scratch_seq,
                const std::string & route,
                const std::string & variant_id,
                const json & query,
                bool close_after_projection = true)
                    -> boundary_result {
        copy_full_sequence(
            source_seq,
            scratch_seq,
            source_boundary_pos,
            route + ":query-copy");
        ++sequence_copy_count;
        const bool enable_paired_complex_read =
            paired_complex_attention_read &&
            route != "exact_full_state";
        const bool managed_semantic_carrier =
            trained_semantic_carrier_mode ||
            output_depth_memory_mode;
        const bool enable_semantic_carrier =
            managed_semantic_carrier &&
            route != "exact_full_state" &&
            route != "carrier_disabled";
        bool semantic_carrier_was_enabled = false;
        uint32_t depth_layer_offset_before = 0;
        if (managed_semantic_carrier) {
            const auto * carrier =
                ctx->get_neo3000_semantic_carrier();
            if (!carrier) {
                throw std::runtime_error(
                    route + ": semantic carrier is absent");
            }
            semantic_carrier_was_enabled = carrier->enabled;
            depth_layer_offset_before =
                carrier->depth_layer_offset;
            if (output_depth_memory_mode &&
                !ctx->set_neo3000_depth_layer_offset(
                    route == "wrong_layer_assignment"
                        ? 1u
                        : 0u)) {
                throw std::runtime_error(
                    route +
                    ": failed to select depth-memory layer law");
            }
            if (!ctx->set_neo3000_semantic_carrier_enabled(
                    enable_semantic_carrier &&
                    !semantic_carrier_layer_delta_mode)) {
                throw std::runtime_error(
                    route + ": failed to select semantic carrier");
            }
        }
        if (enable_paired_complex_read &&
            !ctx->set_neo3000_paired_complex_attention(
                paired_complex_attention_mix,
                paired_complex_attention_layer)) {
            throw std::runtime_error(
                route + ": failed to enable paired-complex read");
        }
        boundary_result boundary;
        try {
            boundary = decode_query(
                ctx,
                vocab,
                candidates,
                "sparse-G-label-refresh:" + route,
                variant_id,
                query,
                expected_source_tokens,
                active_recurrent_backing_initial,
                active_cache_backend_allocation_bytes,
                scratch_seq,
                false,
                -1,
                semantic_carrier_layer_delta_mode,
                enable_semantic_carrier);
        } catch (...) {
            if (enable_paired_complex_read) {
                ctx->set_neo3000_paired_complex_attention(0.0f, -1);
            }
            if (managed_semantic_carrier) {
                ctx->set_neo3000_semantic_carrier_enabled(
                    semantic_carrier_was_enabled);
                if (output_depth_memory_mode) {
                    ctx->set_neo3000_depth_layer_offset(
                        depth_layer_offset_before);
                }
            }
            throw;
        }
        if (enable_paired_complex_read &&
            !ctx->set_neo3000_paired_complex_attention(0.0f, -1)) {
            throw std::runtime_error(
                route + ": failed to disable paired-complex read");
        }
        if (managed_semantic_carrier &&
            !ctx->set_neo3000_semantic_carrier_enabled(
                semantic_carrier_was_enabled)) {
            throw std::runtime_error(
                route + ": failed to restore semantic carrier state");
        }
        if (output_depth_memory_mode &&
            !ctx->set_neo3000_depth_layer_offset(
                depth_layer_offset_before)) {
            throw std::runtime_error(
                route +
                ": failed to restore depth-memory layer law");
        }
        query_decode_tokens +=
            boundary.record.at("query_tokens").get<size_t>();
        records.push_back(boundary.record);
        outputs[route][variant_id].push_back(boundary);
        if (close_after_projection) {
            close_sequence(scratch_seq, route + ":query-close");
            ++sequence_close_count;
        }
        return boundary;
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
        if (trained_semantic_carrier_mode) {
            if (!ctx->advance_neo3000_semantic_carrier()) {
                throw std::runtime_error(
                    stage + ": semantic carrier advance failed");
            }
            const auto * carrier =
                ctx->get_neo3000_semantic_carrier();
            if (!carrier ||
                carrier->action_backing_id !=
                    semantic_carrier_backing_initial) {
                throw std::runtime_error(
                    stage + ": semantic carrier backing changed");
            }
            ++orbit_action_count;
            require_component_positions(
                candidate_seq,
                source_boundary_pos,
                source_boundary_pos,
                stage + ":semantic-carrier-advanced");
            return;
        }
        if (model_weight_value_orbit_mode) {
            llama_kv_cache::value_subspace_metrics metrics = {};
            if (!attention->seq_apply_value_subspace_step(
                    candidate_seq,
                    label_positions,
                    model_weight_operator_build.value_operator,
                    &metrics)) {
                throw std::runtime_error(
                    stage +
                    ": weight-derived semantic value action failed");
            }
            llama_synchronize(ctx);
            orbit_host_read_bytes += metrics.host_read_bytes;
            orbit_host_write_bytes += metrics.host_write_bytes;
            orbit_peak_host_work_bytes = std::max(
                orbit_peak_host_work_bytes,
                metrics.peak_host_work_bytes);
            orbit_tensor_visits += metrics.tensor_visits;
            orbit_position_visits += metrics.position_visits;
            ++orbit_action_count;
            require_component_positions(
                candidate_seq,
                source_boundary_pos,
                source_boundary_pos,
                stage + ":weight-semantic-value-advanced");
            return;
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
                    complex_phase_include_keys,
                    &metrics)) {
                throw std::runtime_error(
                    stage + ": complex phase action failed");
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
    bool scaffold_preparation_sequence_closed = false;
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
            legacy_trained_semantic_carrier_mode
                ? 0.0
            : subspace_value_orbit_mode &&
                build_subspace_operator
                ? calibrate_subspace_operator(
                    canonical_id + ":subspace-calibration")
            : fourier_value_orbit_mode
                ? calibrate_fourier_operator(
                    canonical_id + ":Fourier-calibration")
                : refresh_candidate_labels(
                    variant_g_tokens.at(0),
                    canonical_id + ":orbit-initialization");
        if (output_source_fixed_cell_rematerialization_mode) {
            initial_destination_cell_ids.reserve(
                label_offsets.size());
            for (size_t label_index = 0;
                 label_index < label_offsets.size();
                 ++label_index) {
                const llama_pos label_position =
                    static_cast<llama_pos>(
                        f_boundary_tokens +
                        label_offsets.at(label_index));
                uint32_t cell_id = 0;
                if (!attention->seq_attention_cell_identity(
                        candidate_seq,
                        label_position,
                        &cell_id)) {
                    throw std::runtime_error(
                        canonical_id +
                        ": initial destination cell identity is absent");
                }
                initial_destination_cell_ids.push_back(cell_id);
                fixed_cell_identity_records.push_back({
                    {"stage", "initial"},
                    {"variant", canonical_id},
                    {"destination_label_index", label_index},
                    {"destination_label_position", label_position},
                    {"destination_cell_id", cell_id},
                });
            }
        }
        carrier_recurrent_hash_before =
            hash_recurrent_sequence_streamed(ctx, candidate_seq);
        variant_timings.push_back({
            {"variant", canonical_id},
            {"role", "fixed_orbit_initialization"},
            {"label_refresh_count",
                legacy_trained_semantic_carrier_mode
                    ? 0
                : (fourier_value_orbit_mode ||
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
        if (output_source_rematerialization_mode) {
            // Keep the four public structural prefixes resident. The
            // completed scaffold slot becomes the one sequential query and
            // role-rematerialization scratch sequence.
            close_sequence(
                scaffold_seq,
                "orbit:rematerialization-scaffold-close");
            ++sequence_close_count;
            scaffold_preparation_sequence_closed = true;
        } else {
            for (size_t i = 0; i < stage_seqs.size(); ++i) {
                close_sequence(
                    stage_seqs[i],
                    "orbit:stage-close-" + std::to_string(i));
                ++sequence_close_count;
            }
            close_sequence(scaffold_seq, "orbit:scaffold-close");
            ++sequence_close_count;
            fixed_preparation_sequences_closed = true;
            scaffold_preparation_sequence_closed = true;
        }
    }

    if (output_recurrent_delta_advance_mode) {
        recurrent_output_delta_candidate_physical_row_initial =
            carrier_recurrent_hash_before.physical_row;
        recurrent_output_delta_candidate_physical_row_final =
            carrier_recurrent_hash_before.physical_row;
    }

    if (legacy_trained_semantic_carrier_mode) {
        for (const auto & query :
             variants.at(0).at("queries")) {
            project_from_source(
                candidate_seq,
                stage_seqs[0],
                "carrier_disabled",
                variants.at(0).at("id"),
                query);
        }
    }
    if (output_recurrent_delta_advance_mode) {
        for (const auto & query :
             variants.at(1).at("queries")) {
            project_from_source(
                candidate_seq,
                stage_seqs[0],
                "carrier_disabled",
                variants.at(1).at("id"),
                query);
        }
    }

    for (size_t variant_index = 0;
         variant_index < variants.size();
         ++variant_index) {
        const auto & variant = variants.at(variant_index);
        const std::string id = variant.at("id");
        const auto & target_g_tokens = variant_g_tokens.at(variant_index);
        double variant_label_wall_ms = 0.0;
        if (orbit_mode) {
            if (variant_index > 0 &&
                !output_driven_carrier_mode) {
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

        if (output_written_carrier_mode &&
            variant_index == 1) {
            for (const auto & query : variant.at("queries")) {
                project_from_source(
                    candidate_seq,
                    stage_seqs[0],
                    "carrier_disabled",
                    id,
                    query);
            }
            if (output_depth_memory_mode) {
                for (const auto & query :
                     variant.at("queries")) {
                    project_from_source(
                        candidate_seq,
                        stage_seqs[0],
                        "wrong_layer_assignment",
                        id,
                        query);
                }
            }
        }
        if (output_continuous_soft_role_rematerialization_mode &&
            variant_index == 1) {
            for (const auto & query : variant.at("queries")) {
                project_from_source(
                    work_seq,
                    scaffold_seq,
                    "carrier_disabled",
                    id,
                    query);
            }
            close_sequence(
                work_seq,
                id + ":soft-role-disabled-G1-close");
            ++sequence_close_count;
        }

        if (output_driven_carrier_mode) {
            std::vector<llama_pos> output_positions;
            output_positions.reserve(stage_seqs.size());
            std::vector<llama_token> rematerialization_tokens(
                label_offsets.size(), LLAMA_TOKEN_NULL);
            size_t query_index = 0;
            for (const auto & query : variant.at("queries")) {
                const size_t public_destination =
                    output_recurrent_delta_advance_mode
                        ? query_index
                        : output_promotion_label_indices.at(
                            query_index);
                if (output_continuous_soft_role_rematerialization_mode &&
                    !ctx
                        ->set_neo3000_soft_role_capture_destination(
                            static_cast<int32_t>(
                                public_destination))) {
                    throw std::runtime_error(
                        id +
                        ": failed to arm continuous soft-role capture");
                }
                const llama_seq_id stage_seq =
                    output_source_rematerialization_mode
                        ? scaffold_seq
                        : stage_seqs.at(query_index);
                const boundary_result boundary =
                    project_from_source(
                        candidate_seq,
                        stage_seq,
                        candidate_route,
                        id,
                        query,
                        false);
                const size_t candidate_index =
                    static_cast<size_t>(
                        boundary.argmax.at(0) - 'A');
                if (candidate_index >= candidates.size()) {
                    throw std::runtime_error(
                        id + ": projected output is not a candidate");
                }
                const size_t query_tokens =
                    boundary.record.at("query_tokens")
                        .get<size_t>();
                const llama_pos output_position =
                    static_cast<llama_pos>(
                        expected_source_tokens + query_tokens);
                require_component_positions(
                    stage_seq,
                    output_position - 1,
                    output_position - 1,
                    id + ":output-promotion-query-ready-" +
                        std::to_string(query_index));
                if (output_recurrent_delta_advance_mode) {
                    copy_full_sequence(
                        stage_seq,
                        work_seq,
                        output_position - 1,
                        id + ":pre-output-state-copy-" +
                            std::to_string(query_index));
                    ++sequence_copy_count;
                }
                if (output_depth_memory_mode &&
                    (!ctx->set_neo3000_depth_capture_destination(
                         static_cast<int32_t>(
                             public_destination)) ||
                     !ctx->set_neo3000_depth_layer_offset(0) ||
                     !ctx->set_neo3000_semantic_carrier_enabled(
                         true))) {
                    throw std::runtime_error(
                        id +
                        ": failed to arm depth-resolved output capture");
                }
                double output_wall_ms = 0.0;
                try {
                    output_wall_ms =
                        output_continuous_soft_role_rematerialization_mode
                            ? 0.0
                        : output_written_carrier_mode
                            ? timed_decode_terminal(
                                std::vector<llama_token>{
                                    candidates.at(candidate_index)},
                                output_position,
                                stage_seq)
                            : timed_decode(
                                std::vector<llama_token>{
                                    candidates.at(candidate_index)},
                                output_position,
                                stage_seq);
                } catch (...) {
                    if (output_depth_memory_mode) {
                        ctx->set_neo3000_semantic_carrier_enabled(
                            false);
                    }
                    throw;
                }
                if (output_depth_memory_mode &&
                    !ctx->set_neo3000_semantic_carrier_enabled(
                        false)) {
                    throw std::runtime_error(
                        id +
                        ": failed to release depth-memory output read");
                }
                useful_output_decode_wall_ms_total +=
                    output_wall_ms;
                if (!output_continuous_soft_role_rematerialization_mode) {
                    ++useful_output_decode_tokens;
                    require_component_positions(
                        stage_seq,
                        output_position,
                        output_position,
                        id + ":output-token-resident-" +
                            std::to_string(query_index));
                }
                if (output_recurrent_delta_advance_mode) {
                    llama_memory_recurrent::neo3000_output_delta_metrics
                        metrics = {};
                    const auto delta_started =
                        std::chrono::steady_clock::now();
                    if (!recurrent->neo3000_seq_make_output_delta(
                            ctx,
                            stage_seq,
                            work_seq,
                            &metrics)) {
                        throw std::runtime_error(
                            id +
                            ": actual-output recurrent delta "
                            "extraction failed for query " +
                            std::to_string(query_index));
                    }
                    const double delta_wall_ms =
                        std::chrono::duration<double, std::milli>(
                            std::chrono::steady_clock::now() -
                            delta_started).count();
                    if (recurrent_output_delta_logical_row_bytes != 0 &&
                        recurrent_output_delta_logical_row_bytes !=
                            metrics.logical_row_bytes) {
                        throw std::runtime_error(
                            id +
                            ": recurrent delta row size changed");
                    }
                    recurrent_output_delta_logical_row_bytes =
                        metrics.logical_row_bytes;
                    recurrent_output_delta_backend_read_bytes +=
                        metrics.backend_read_bytes;
                    recurrent_output_delta_backend_write_bytes +=
                        metrics.backend_write_bytes;
                    recurrent_output_delta_arithmetic_element_operations +=
                        metrics.arithmetic_element_operations;
                    recurrent_output_delta_tensor_visits +=
                        metrics.tensor_visits;
                    recurrent_output_delta_graph_applications +=
                        metrics.graph_applications;
                    if (recurrent_output_delta_graph_applications == 1) {
                        recurrent_output_delta_scheduler_compute_bytes_initial =
                            metrics.scheduler_compute_bytes_before;
                    }
                    recurrent_output_delta_scheduler_compute_bytes_peak =
                        std::max(
                            recurrent_output_delta_scheduler_compute_bytes_peak,
                            metrics.scheduler_compute_bytes_after);
                    recurrent_output_delta_extraction_wall_ms_total +=
                        delta_wall_ms;
                    ++recurrent_output_delta_extraction_count;
                    recurrent_output_delta_records.push_back({
                        {"operation", "post_output_minus_pre_output"},
                        {"variant", id},
                        {"query_id", query.at("id")},
                        {"query_index", query_index},
                        {"actual_projected_output", boundary.argmax},
                        {"delta_sequence", stage_seq},
                        {"pre_output_sequence", work_seq},
                        {"delta_physical_row",
                            metrics.destination_physical_row},
                        {"pre_output_physical_rows",
                            metrics.source_physical_rows},
                        {"logical_row_bytes",
                            metrics.logical_row_bytes},
                        {"backend_read_bytes",
                            metrics.backend_read_bytes},
                        {"backend_write_bytes",
                            metrics.backend_write_bytes},
                        {"arithmetic_element_operations",
                            metrics.arithmetic_element_operations},
                        {"tensor_visits", metrics.tensor_visits},
                        {"graph_applications",
                            metrics.graph_applications},
                        {"scheduler_compute_bytes_before",
                            metrics.scheduler_compute_bytes_before},
                        {"scheduler_compute_bytes_after",
                            metrics.scheduler_compute_bytes_after},
                        {"wall_ms", delta_wall_ms},
                        {"host_recurrent_payload_bytes", 0},
                        {"expected_answer_consulted", false},
                        {"public_phase_table_consulted", false},
                    });
                    close_sequence(
                        work_seq,
                        id + ":pre-output-state-close-" +
                            std::to_string(query_index));
                    ++sequence_close_count;
                }
                output_positions.push_back(output_position);
                const size_t destination_label_index =
                    public_destination;
                if (output_depth_memory_mode) {
                    ++output_promotion_row_count;
                } else if (output_written_carrier_mode &&
                    (!output_phase_orbit_memory_mode ||
                     variant_index == 0)) {
                    const bool wrote =
                        output_phase_memory_mode
                            ? ctx->stage_neo3000_phase_binding(
                                static_cast<uint32_t>(
                                    candidate_index),
                                static_cast<uint32_t>(
                                    destination_label_index))
                            : [&]() {
                                const float * output_state =
                                    semantic_carrier_layer_delta_mode
                                        ? llama_get_embeddings_layer_inp(
                                            ctx,
                                            static_cast<uint32_t>(
                                                semantic_carrier_read_layer))
                                        : llama_get_embeddings_ith(
                                            ctx,
                                            -1);
                                return output_state &&
                                    ctx->write_neo3000_semantic_port(
                                        output_state,
                                        ctx->get_model()
                                            .hparams.n_embd_out(),
                                        static_cast<uint32_t>(
                                            destination_label_index));
                            }();
                    if (!wrote) {
                        throw std::runtime_error(
                            id +
                            ": actual output failed to write semantic port");
                    }
                    ++output_promotion_row_count;
                }
                if (output_source_rematerialization_mode) {
                    rematerialization_tokens.at(
                        destination_label_index) =
                        candidates.at(candidate_index);
                }
                if (output_recurrent_delta_advance_mode) {
                    output_promotion_records.push_back({
                        {"variant", id},
                        {"query_id", query.at("id")},
                        {"query_index", query_index},
                        {"source_sequence", stage_seq},
                        {"source_output_position", output_position},
                        {"actual_projected_output", boundary.argmax},
                        {"actual_projected_token",
                            candidates.at(candidate_index)},
                        {"output_decode_wall_ms", output_wall_ms},
                        {"state_action",
                            "complete_recurrent_row_delta"},
                        {"source_role_model_forward_tokens", 0},
                    });
                } else {
                    output_promotion_records.push_back({
                        {"variant", id},
                        {"query_id", query.at("id")},
                        {"query_index", query_index},
                        {"source_sequence", stage_seq},
                        {"source_output_position", output_position},
                        {"actual_projected_output", boundary.argmax},
                        {"actual_projected_token",
                            candidates.at(candidate_index)},
                        {"destination_label_index",
                            destination_label_index},
                        {"destination_label_position",
                            static_cast<llama_pos>(
                                f_boundary_tokens +
                                label_offsets.at(
                                    output_promotion_label_indices.at(
                                        query_index)))},
                        {"output_decode_wall_ms", output_wall_ms},
                        {"output_written_semantic_port",
                            output_written_semantic_port_mode},
                        {"output_written_hidden_slot",
                            output_written_hidden_slot_mode},
                        {"output_depth_resolved_cross_attention_memory",
                            output_depth_memory_mode},
                        {"output_phase_memory",
                            output_phase_memory_mode},
                        {"output_phase_orbit_memory",
                            output_phase_orbit_memory_mode},
                        {"continuous_soft_output_capture",
                            output_continuous_soft_role_rematerialization_mode},
                        {"output_written_to_carrier",
                            output_continuous_soft_role_rematerialization_mode ||
                            !output_phase_orbit_memory_mode ||
                                variant_index == 0},
                        {"source_role_model_forward_tokens", 0},
                    });
                }
                if (output_source_rematerialization_mode) {
                    close_sequence(
                        stage_seq,
                        id + ":projected-output-close-" +
                            std::to_string(query_index));
                    ++sequence_close_count;
                }
                ++query_index;
            }
            if (output_phase_memory_mode) {
                const bool phase_action_ok =
                    output_phase_orbit_memory_mode
                        ? variant_index == 0
                            ? ctx->commit_neo3000_phase_memory()
                            : ctx->advance_neo3000_phase_memory()
                        : ctx->commit_neo3000_phase_memory();
                if (!phase_action_ok) {
                    throw std::runtime_error(
                        id +
                        (output_phase_orbit_memory_mode
                            ? ": native phase carrier advance failed"
                            : ": complete output panel failed to commit "
                              "phase memory"));
                }
            }
            if (output_continuous_soft_role_rematerialization_mode &&
                !ctx->commit_neo3000_soft_role_memory()) {
                throw std::runtime_error(
                    id +
                    ": complete continuous output panel failed "
                    "to commit");
            }
            if (output_depth_memory_mode &&
                !ctx->commit_neo3000_depth_memory()) {
                throw std::runtime_error(
                    id +
                    ": complete depth-resolved output panel "
                    "failed to commit");
            }
            if (output_recurrent_delta_advance_mode) {
                llama_memory_recurrent::neo3000_output_delta_metrics
                    metrics = {};
                const auto accumulation_started =
                    std::chrono::steady_clock::now();
                if (!recurrent->neo3000_seq_accumulate_output_deltas(
                        ctx,
                        candidate_seq,
                        stage_seqs,
                        &metrics)) {
                    throw std::runtime_error(
                        id +
                        ": actual-output recurrent delta "
                        "accumulation failed");
                }
                const double accumulation_wall_ms =
                    std::chrono::duration<double, std::milli>(
                        std::chrono::steady_clock::now() -
                        accumulation_started).count();
                if (recurrent_output_delta_logical_row_bytes != 0 &&
                    recurrent_output_delta_logical_row_bytes !=
                        metrics.logical_row_bytes) {
                    throw std::runtime_error(
                        id +
                        ": recurrent accumulation row size changed");
                }
                recurrent_output_delta_logical_row_bytes =
                    metrics.logical_row_bytes;
                recurrent_output_delta_backend_read_bytes +=
                    metrics.backend_read_bytes;
                recurrent_output_delta_backend_write_bytes +=
                    metrics.backend_write_bytes;
                recurrent_output_delta_arithmetic_element_operations +=
                    metrics.arithmetic_element_operations;
                recurrent_output_delta_tensor_visits +=
                    metrics.tensor_visits;
                recurrent_output_delta_graph_applications +=
                    metrics.graph_applications;
                recurrent_output_delta_scheduler_compute_bytes_peak =
                    std::max(
                        recurrent_output_delta_scheduler_compute_bytes_peak,
                        metrics.scheduler_compute_bytes_after);
                recurrent_output_delta_accumulation_wall_ms_total +=
                    accumulation_wall_ms;
                ++recurrent_output_delta_accumulation_count;
                recurrent_output_delta_candidate_physical_row_final =
                    metrics.destination_physical_row;
                recurrent_output_delta_candidate_physical_row_stable =
                    recurrent_output_delta_candidate_physical_row_stable &&
                    metrics.destination_physical_row ==
                        recurrent_output_delta_candidate_physical_row_initial;
                recurrent_output_delta_records.push_back({
                    {"operation", "accumulate_into_active_candidate"},
                    {"variant", id},
                    {"destination_sequence", candidate_seq},
                    {"destination_physical_row",
                        metrics.destination_physical_row},
                    {"delta_sequences", stage_seqs},
                    {"delta_physical_rows",
                        metrics.source_physical_rows},
                    {"logical_row_bytes",
                        metrics.logical_row_bytes},
                    {"backend_read_bytes",
                        metrics.backend_read_bytes},
                    {"backend_write_bytes",
                        metrics.backend_write_bytes},
                    {"arithmetic_element_operations",
                        metrics.arithmetic_element_operations},
                    {"tensor_visits", metrics.tensor_visits},
                    {"graph_applications",
                        metrics.graph_applications},
                    {"scheduler_compute_bytes_before",
                        metrics.scheduler_compute_bytes_before},
                    {"scheduler_compute_bytes_after",
                        metrics.scheduler_compute_bytes_after},
                    {"wall_ms", accumulation_wall_ms},
                    {"host_recurrent_payload_bytes", 0},
                    {"destination_sequence_metadata_relinked", false},
                    {"expected_answer_consulted", false},
                    {"public_phase_table_consulted", false},
                });
            }
            if (output_source_rematerialization_mode) {
                for (size_t label_index = 0;
                     label_index < label_offsets.size();
                     ++label_index) {
                    const llama_token actual_output =
                        rematerialization_tokens.at(label_index);
                    if (actual_output == LLAMA_TOKEN_NULL) {
                        throw std::runtime_error(
                            id +
                            ": rematerialization output is absent");
                    }
                    const llama_pos label_position =
                        static_cast<llama_pos>(
                            f_boundary_tokens +
                            label_offsets.at(label_index));
                    copy_full_sequence(
                        stage_seqs.at(label_index),
                        scaffold_seq,
                        label_position - 1,
                        id + ":source-role-prefix-" +
                            std::to_string(label_index));
                    ++sequence_copy_count;
                    if (output_continuous_soft_role_rematerialization_mode &&
                        !ctx->set_neo3000_soft_role_read_slot(
                            static_cast<int32_t>(label_index))) {
                        throw std::runtime_error(
                            id +
                            ": continuous source-role slot read failed");
                    }
                    const llama_token forwarded_token =
                        output_continuous_soft_role_rematerialization_mode
                            ? candidates.at(0)
                            : actual_output;
                    const double role_wall_ms = timed_decode(
                        std::vector<llama_token>{forwarded_token},
                        label_position,
                        scaffold_seq);
                    if (output_continuous_soft_role_rematerialization_mode &&
                        !ctx->set_neo3000_soft_role_read_slot(-1)) {
                        throw std::runtime_error(
                            id +
                            ": continuous source-role slot release failed");
                    }
                    variant_label_wall_ms += role_wall_ms;
                    label_refresh_wall_ms_total += role_wall_ms;
                    source_role_rematerialization_wall_ms_total +=
                        role_wall_ms;
                    ++label_refresh_count;
                    ++source_role_rematerialization_tokens;
                    require_component_positions(
                        scaffold_seq,
                        label_position,
                        label_position,
                        id + ":source-role-token-" +
                            std::to_string(label_index));
                    uint32_t source_cell_id = 0;
                    uint32_t destination_cell_id_before = 0;
                    if (!attention->seq_attention_cell_identity(
                            scaffold_seq,
                            label_position,
                            &source_cell_id) ||
                        !attention->seq_attention_cell_identity(
                            candidate_seq,
                            label_position,
                            &destination_cell_id_before)) {
                        throw std::runtime_error(
                            id +
                            ": rematerialized cell identity is absent");
                    }
                    llama_kv_cache::value_orbit_metrics
                        fixed_cell_copy_metrics = {};
                    if (output_source_fixed_cell_rematerialization_mode) {
                        if (!attention
                                ->seq_copy_attention_key_value_row(
                                    scaffold_seq,
                                    label_position,
                                    candidate_seq,
                                    label_position,
                                    orbit_attention_layers,
                                    &fixed_cell_copy_metrics)) {
                            throw std::runtime_error(
                                id +
                                ": fixed-cell source-role K/V copy failed");
                        }
                        llama_synchronize(ctx);
                        orbit_backend_copy_bytes +=
                            fixed_cell_copy_metrics.backend_copy_bytes;
                        orbit_host_read_bytes +=
                            fixed_cell_copy_metrics.host_read_bytes;
                        orbit_host_write_bytes +=
                            fixed_cell_copy_metrics.host_write_bytes;
                        orbit_peak_host_work_bytes = std::max(
                            orbit_peak_host_work_bytes,
                            fixed_cell_copy_metrics
                                .peak_host_work_bytes);
                        orbit_tensor_visits +=
                            fixed_cell_copy_metrics.tensor_count;
                        orbit_position_visits +=
                            fixed_cell_copy_metrics.position_count;
                    } else {
                        if (!attention->seq_rm(
                                candidate_seq,
                                label_position,
                                label_position + 1)) {
                            throw std::runtime_error(
                                id +
                                ": prior source-role label removal failed");
                        }
                        ++attention_label_remove_count;
                        attention->seq_cp(
                            scaffold_seq,
                            candidate_seq,
                            label_position,
                            label_position + 1);
                        llama_synchronize(ctx);
                        ++attention_label_alias_count;
                    }
                    uint32_t destination_cell_id_after = 0;
                    if (!attention->seq_attention_cell_identity(
                            candidate_seq,
                            label_position,
                            &destination_cell_id_after)) {
                        throw std::runtime_error(
                            id +
                            ": updated destination cell identity is absent");
                    }
                    const bool destination_cell_identity_stable =
                        destination_cell_id_before ==
                            destination_cell_id_after &&
                        (!output_source_fixed_cell_rematerialization_mode ||
                         destination_cell_id_after ==
                            initial_destination_cell_ids.at(
                                label_index));
                    all_destination_cell_identities_stable =
                        all_destination_cell_identities_stable &&
                        destination_cell_identity_stable;
                    ++output_promotion_row_count;
                    source_role_rematerialization_records.push_back({
                        {"variant", id},
                        {"destination_label_index", label_index},
                        {"destination_label_position", label_position},
                        {"actual_projected_token", actual_output},
                        {"forwarded_placeholder_token",
                            output_continuous_soft_role_rematerialization_mode
                                ? forwarded_token
                                : LLAMA_TOKEN_NULL},
                        {"continuous_soft_embedding_override",
                            output_continuous_soft_role_rematerialization_mode},
                        {"model_forward_tokens", 1},
                        {"wall_ms", role_wall_ms},
                        {"source_cell_id", source_cell_id},
                        {"destination_cell_id_before",
                            destination_cell_id_before},
                        {"destination_cell_id_after",
                            destination_cell_id_after},
                        {"destination_cell_identity_stable",
                            destination_cell_identity_stable},
                        {"fixed_cell_key_value_copy",
                            output_source_fixed_cell_rematerialization_mode},
                        {"backend_copy_bytes",
                            fixed_cell_copy_metrics.backend_copy_bytes},
                        {"host_tensor_read_bytes",
                            fixed_cell_copy_metrics.host_read_bytes},
                        {"host_tensor_write_bytes",
                            fixed_cell_copy_metrics.host_write_bytes},
                        {"expected_answer_consulted", false},
                        {"public_phase_table_consulted", false},
                    });
                    if (output_source_fixed_cell_rematerialization_mode) {
                        fixed_cell_identity_records.push_back({
                            {"stage", "advance"},
                            {"variant", id},
                            {"destination_label_index", label_index},
                            {"destination_label_position", label_position},
                            {"source_cell_id", source_cell_id},
                            {"destination_cell_id_before",
                                destination_cell_id_before},
                            {"destination_cell_id_after",
                                destination_cell_id_after},
                            {"stable",
                                destination_cell_identity_stable},
                        });
                    }
                    require_component_positions(
                        candidate_seq,
                        source_boundary_pos,
                        source_boundary_pos,
                        id + ":source-role-patched-" +
                            std::to_string(label_index));
                    close_sequence(
                        scaffold_seq,
                        id + ":source-role-scratch-close-" +
                            std::to_string(label_index));
                    ++sequence_close_count;
                }
            }
            if (output_role_generator_mode ||
                output_attention_kernel_writer_mode) {
                std::vector<llama_pos> destination_positions;
                std::vector<uint32_t> destination_indices;
                destination_positions.reserve(stage_seqs.size());
                destination_indices.reserve(stage_seqs.size());
                for (size_t i = 0; i < stage_seqs.size(); ++i) {
                    const size_t label_index =
                        output_promotion_label_indices.at(i);
                    destination_positions.push_back(
                        static_cast<llama_pos>(
                            f_boundary_tokens +
                            label_offsets.at(label_index)));
                    destination_indices.push_back(
                        static_cast<uint32_t>(label_index));
                }
                if (output_attention_kernel_writer_mode) {
                    llama_kv_cache::attention_kernel_writer_metrics
                        metrics = {};
                    if (!attention
                            ->seq_apply_attention_kernel_writer(
                                stage_seqs,
                                output_positions,
                                candidate_seq,
                                destination_positions,
                                destination_indices,
                                attention_kernel_writer_operator,
                                ctx,
                                &metrics)) {
                        throw std::runtime_error(
                            id +
                            ": output-conditioned attention "
                            "kernel writer failed");
                    }
                    attention_kernel_writer_runtime_parameter_upload_bytes +=
                        metrics.host_parameter_upload_bytes;
                    attention_kernel_writer_runtime_graph_applications +=
                        metrics.graph_applications;
                    attention_kernel_writer_runtime_generated_rows +=
                        metrics.generated_rows;
                    attention_kernel_writer_runtime_multiply_accumulates +=
                        metrics.multiply_accumulates;
                    orbit_host_read_bytes +=
                        metrics.host_carrier_read_bytes;
                    orbit_host_write_bytes +=
                        metrics.host_carrier_write_bytes;
                    orbit_tensor_visits +=
                        metrics.tensor_visits;
                    orbit_position_visits +=
                        metrics.position_visits;
                } else {
                    llama_kv_cache::role_generator_metrics
                        metrics = {};
                    if (!attention
                            ->seq_apply_attention_role_generator(
                                stage_seqs,
                                output_positions,
                                candidate_seq,
                                destination_positions,
                                destination_indices,
                                role_generator_operator,
                                ctx,
                                &metrics)) {
                        throw std::runtime_error(
                            id +
                            ": shared nonlinear output-role "
                            "generator failed");
                    }
                    role_generator_runtime_parameter_upload_bytes +=
                        metrics.host_parameter_upload_bytes;
                    role_generator_runtime_graph_applications +=
                        metrics.graph_applications;
                    role_generator_runtime_generated_rows +=
                        metrics.generated_rows;
                    role_generator_runtime_multiply_accumulates +=
                        metrics.multiply_accumulates;
                    orbit_host_read_bytes +=
                        metrics.host_carrier_read_bytes;
                    orbit_host_write_bytes +=
                        metrics.host_carrier_write_bytes;
                    orbit_tensor_visits += metrics.tensor_visits;
                    orbit_position_visits +=
                        metrics.position_visits;
                }
            }
            for (size_t i = 0;
                 !output_role_generator_mode &&
                    !output_attention_kernel_writer_mode &&
                    !output_source_rematerialization_mode &&
                    !output_written_carrier_mode &&
                    !output_recurrent_delta_advance_mode &&
                    i < stage_seqs.size();
                 ++i) {
                const size_t label_index =
                    output_promotion_label_indices.at(i);
                const llama_pos label_position =
                    static_cast<llama_pos>(
                        f_boundary_tokens +
                        label_offsets.at(label_index));
                if (output_role_transport_mode) {
                    llama_kv_cache::role_transport_metrics
                        metrics = {};
                    if (!attention
                            ->seq_apply_attention_role_transport(
                                stage_seqs.at(i),
                                output_positions.at(i),
                                candidate_seq,
                                label_position,
                                static_cast<uint32_t>(
                                    label_index),
                                role_transport_operator,
                                &metrics)) {
                        throw std::runtime_error(
                            id +
                            ": output role transport failed for query " +
                            std::to_string(i));
                    }
                    llama_synchronize(ctx);
                    orbit_host_read_bytes +=
                        metrics.host_read_bytes;
                    orbit_host_write_bytes +=
                        metrics.host_write_bytes;
                    orbit_peak_host_work_bytes = std::max(
                        orbit_peak_host_work_bytes,
                        metrics.peak_host_work_bytes);
                    orbit_tensor_visits +=
                        metrics.tensor_visits;
                    orbit_position_visits +=
                        metrics.position_visits;
                } else {
                    llama_kv_cache::value_orbit_metrics
                        metrics = {};
                    if (!attention->seq_copy_attention_value_row(
                            stage_seqs.at(i),
                            output_positions.at(i),
                            candidate_seq,
                            label_position,
                            orbit_attention_layers,
                            &metrics)) {
                        throw std::runtime_error(
                            id +
                            ": output value promotion failed for query " +
                            std::to_string(i));
                    }
                    llama_synchronize(ctx);
                    orbit_backend_copy_bytes +=
                        metrics.backend_copy_bytes;
                    orbit_host_read_bytes +=
                        metrics.host_read_bytes;
                    orbit_host_write_bytes +=
                        metrics.host_write_bytes;
                    orbit_peak_host_work_bytes = std::max(
                        orbit_peak_host_work_bytes,
                        metrics.peak_host_work_bytes);
                    orbit_tensor_visits += metrics.tensor_count;
                    orbit_position_visits +=
                        metrics.position_count;
                }
                ++output_promotion_row_count;
            }
            ++orbit_action_count;
            require_component_positions(
                candidate_seq,
                source_boundary_pos,
                source_boundary_pos,
                id + ":output-promoted-carrier-advanced");
            if (!output_source_rematerialization_mode) {
                for (size_t i = 0; i < stage_seqs.size(); ++i) {
                    close_sequence(
                        stage_seqs.at(i),
                        id + ":output-stage-close-" +
                            std::to_string(i));
                    ++sequence_close_count;
                }
            }
        } else {
            for (const auto & query : variant.at("queries")) {
                project_from_source(
                    candidate_seq,
                    orbit_mode ? stage_seqs[0] : work_seq,
                    candidate_route,
                    id,
                    query);
            }
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
                orbit_mode
                    ? output_source_rematerialization_mode
                        ? scaffold_seq
                        : stage_seqs[0]
                    : candidate_seq,
                "exact_full_state",
                id,
                query);
        }
        if (output_continuous_soft_role_rematerialization_mode &&
            variant_index == 0) {
            for (size_t label_index = 0;
                 label_index < label_offsets.size();
                 ++label_index) {
                const llama_pos label_position =
                    static_cast<llama_pos>(
                        f_boundary_tokens +
                        label_offsets.at(label_index));
                copy_full_sequence(
                    stage_seqs.at(label_index),
                    scaffold_seq,
                    label_position - 1,
                    id + ":soft-role-disabled-prefix-" +
                        std::to_string(label_index));
                ++sequence_copy_count;
                const double role_wall_ms = timed_decode(
                    std::vector<llama_token>{
                        candidates.at(0)},
                    label_position,
                    scaffold_seq);
                source_role_rematerialization_wall_ms_total +=
                    role_wall_ms;
                label_refresh_wall_ms_total += role_wall_ms;
                ++source_role_rematerialization_tokens;
                ++label_refresh_count;
                if (!attention->seq_rm(
                        work_seq,
                        label_position,
                        label_position + 1)) {
                    throw std::runtime_error(
                        id +
                        ": disabled soft-role prior row removal failed");
                }
                ++attention_label_remove_count;
                attention->seq_cp(
                    scaffold_seq,
                    work_seq,
                    label_position,
                    label_position + 1);
                llama_synchronize(ctx);
                ++attention_label_alias_count;
                ++output_promotion_row_count;
                source_role_rematerialization_records.push_back({
                    {"variant", id},
                    {"control", "carrier_read_gate_zero"},
                    {"destination_label_index", label_index},
                    {"destination_label_position", label_position},
                    {"forwarded_placeholder_token",
                        candidates.at(0)},
                    {"continuous_soft_embedding_override", false},
                    {"model_forward_tokens", 1},
                    {"wall_ms", role_wall_ms},
                    {"expected_answer_consulted", false},
                    {"public_phase_table_consulted", false},
                });
                close_sequence(
                    scaffold_seq,
                    id + ":soft-role-disabled-scratch-close-" +
                        std::to_string(label_index));
                ++sequence_close_count;
            }
            require_component_positions(
                work_seq,
                source_boundary_pos,
                source_boundary_pos,
                id + ":soft-role-disabled-G1-ready");
        } else {
            close_sequence(work_seq, id + ":reference-close");
            ++sequence_close_count;
        }
        variant_timings.push_back({
            {"variant", id},
            {"label_refresh_count",
                orbit_mode ? 0 : label_offsets.size()},
            {"label_refresh_wall_ms", variant_label_wall_ms},
            {"orbit_action_count_after_candidate_transaction",
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
            scaffold_preparation_sequence_closed ? -1 :
                source_boundary_pos,
            scaffold_preparation_sequence_closed ? -1 :
                source_boundary_pos,
            id + ":scaffold-lifecycle");
    }

    size_t return_boundary_matches = 0;
    size_t return_full_logit_hash_matches = 0;
    double return_maximum_candidate_logit_absolute_difference = 0.0;
    if (orbit_mode) {
        if (!output_driven_carrier_mode) {
            advance_label_orbit("orbit-return-G0");
        }
        for (const auto & query : variants.at(0).at("queries")) {
            project_from_source(
                candidate_seq,
                output_source_rematerialization_mode
                    ? scaffold_seq
                    : stage_seqs[0],
                return_route,
                variants.at(0).at("id"),
                query);
        }
        const auto & initial =
            outputs.at(candidate_route)
                .at(variants.at(0).at("id").get<std::string>());
        const auto & returned =
            outputs.at(return_route)
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

    if (output_source_fixed_cell_rematerialization_mode) {
        final_destination_cell_ids.reserve(label_offsets.size());
        for (size_t label_index = 0;
             label_index < label_offsets.size();
             ++label_index) {
            const llama_pos label_position =
                static_cast<llama_pos>(
                    f_boundary_tokens +
                    label_offsets.at(label_index));
            uint32_t cell_id = 0;
            if (!attention->seq_attention_cell_identity(
                    candidate_seq,
                    label_position,
                    &cell_id)) {
                throw std::runtime_error(
                    "final destination cell identity is absent");
            }
            final_destination_cell_ids.push_back(cell_id);
            const bool stable =
                cell_id ==
                    initial_destination_cell_ids.at(label_index);
            all_destination_cell_identities_stable =
                all_destination_cell_identities_stable && stable;
            fixed_cell_identity_records.push_back({
                {"stage", "final"},
                {"variant", variants.at(0).at("id")},
                {"destination_label_index", label_index},
                {"destination_label_position", label_position},
                {"destination_cell_id", cell_id},
                {"stable", stable},
            });
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
        candidate_route,
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

    size_t carrier_disabled_correct = 0;
    size_t carrier_disabled_boundary_matches = 0;
    if (trained_semantic_carrier_mode ||
        output_depth_memory_mode ||
        output_continuous_soft_role_rematerialization_mode ||
        output_recurrent_delta_advance_mode) {
        const size_t disabled_variant_index =
            output_written_carrier_mode ||
                output_continuous_soft_role_rematerialization_mode ||
                output_recurrent_delta_advance_mode
                ? 1
                : 0;
        const std::string canonical_id =
            variants.at(disabled_variant_index)
                .at("id").get<std::string>();
        const auto & disabled =
            outputs.at("carrier_disabled").at(canonical_id);
        const auto & enabled =
            outputs.at(candidate_route).at(canonical_id);
        carrier_disabled_correct =
            semantic_correct_count(
                disabled,
                variants.at(disabled_variant_index).at("queries"),
                false);
        for (size_t i = 0; i < disabled.size(); ++i) {
            carrier_disabled_boundary_matches +=
                disabled.at(i).argmax == enabled.at(i).argmax;
        }
    }
    size_t wrong_layer_correct = 0;
    size_t wrong_layer_boundary_matches = 0;
    if (output_depth_memory_mode) {
        const size_t control_variant_index = 1;
        const std::string canonical_id =
            variants.at(control_variant_index)
                .at("id").get<std::string>();
        const auto & wrong =
            outputs.at("wrong_layer_assignment").at(canonical_id);
        const auto & enabled =
            outputs.at(candidate_route).at(canonical_id);
        wrong_layer_correct =
            semantic_correct_count(
                wrong,
                variants.at(control_variant_index).at("queries"),
                false);
        for (size_t i = 0; i < wrong.size(); ++i) {
            wrong_layer_boundary_matches +=
                wrong.at(i).argmax == enabled.at(i).argmax;
        }
    }
    uint64_t semantic_carrier_graph_input_sets = 0;
    uint64_t semantic_carrier_host_to_backend_bytes = 0;
    uint64_t semantic_carrier_backend_to_graph_bytes = 0;
    uint64_t semantic_carrier_hidden_slot_backend_bytes = 0;
    uint64_t semantic_carrier_phase_memory_backend_bytes = 0;
    uint64_t semantic_carrier_phase_binding_upload_bytes = 0;
    uint64_t semantic_carrier_phase_backend_copy_bytes = 0;
    uint64_t semantic_carrier_phase_element_operations = 0;
    uint64_t semantic_carrier_phase_graph_applications = 0;
    uint64_t semantic_carrier_phase_commits = 0;
    uint64_t semantic_carrier_phase_rotation_upload_bytes = 0;
    uint64_t semantic_carrier_phase_rotation_element_operations = 0;
    uint64_t semantic_carrier_phase_rotations = 0;
    uint64_t semantic_carrier_soft_role_backend_bytes = 0;
    uint64_t semantic_carrier_soft_role_candidate_id_upload_bytes = 0;
    uint64_t semantic_carrier_soft_role_gate_upload_bytes = 0;
    uint64_t semantic_carrier_soft_role_capture_device_copy_bytes = 0;
    uint64_t semantic_carrier_soft_role_commit_device_copy_bytes = 0;
    uint64_t semantic_carrier_soft_role_read_device_copy_bytes = 0;
    uint64_t semantic_carrier_soft_role_projection_token_applications = 0;
    uint64_t semantic_carrier_soft_role_projection_multiply_accumulates = 0;
    uint64_t semantic_carrier_soft_role_mixture_multiply_accumulates = 0;
    uint64_t semantic_carrier_soft_role_captures = 0;
    uint64_t semantic_carrier_soft_role_commits = 0;
    uint64_t semantic_carrier_soft_role_reads = 0;
    uint64_t semantic_carrier_depth_memory_backend_bytes = 0;
    uint64_t semantic_carrier_depth_capture_device_copy_bytes = 0;
    uint64_t semantic_carrier_depth_commit_device_copy_bytes = 0;
    uint64_t semantic_carrier_depth_read_device_copy_bytes = 0;
    uint64_t semantic_carrier_depth_cross_attention_multiply_accumulates = 0;
    uint64_t semantic_carrier_depth_captures = 0;
    uint64_t semantic_carrier_depth_commits = 0;
    uint64_t semantic_carrier_depth_reads = 0;
    uint64_t semantic_carrier_writer_host_input_bytes = 0;
    uint64_t semantic_carrier_port_writes = 0;
    uint64_t semantic_carrier_router_bias_token_applications = 0;
    uint64_t semantic_carrier_router_bias_enabled_token_applications = 0;
    uint64_t semantic_carrier_router_bias_multiply_accumulates = 0;
    uint64_t semantic_carrier_recurrent_transition_token_applications = 0;
    uint64_t semantic_carrier_recurrent_transition_enabled_token_applications = 0;
    uint64_t semantic_carrier_map_multiply_accumulates = 0;
    uint64_t semantic_carrier_optimizer_parameter_read_bytes = 0;
    uint64_t semantic_carrier_optimizer_parameter_write_bytes = 0;
    uint64_t semantic_carrier_port_hash = 0;
    uint64_t semantic_carrier_generation = 0;
    bool semantic_carrier_quiescent = true;
    bool semantic_carrier_restored = true;
    if (trained_semantic_carrier_mode ||
        output_depth_memory_mode ||
        output_continuous_soft_role_rematerialization_mode) {
        const auto * carrier =
            ctx->get_neo3000_semantic_carrier();
        semantic_carrier_quiescent =
            carrier &&
            carrier->action_backing_id ==
                semantic_carrier_backing_initial &&
            carrier->phase == 0 &&
            !carrier->enabled &&
            std::all_of(
                carrier->action.begin(),
                carrier->action.end(),
                [](float value) { return value == 0.0f; }) &&
            (!carrier->output_phase_memory ||
                (!carrier->phase_poisoned &&
                 carrier->phase_staging_writes == 0 &&
                 carrier->phase_staging_destination_mask == 0)) &&
            (!carrier->continuous_soft_role_memory ||
                (!carrier->soft_role_poisoned &&
                 carrier->soft_role_capture_destination == -1 &&
                 carrier->soft_role_read_slot == -1 &&
                 carrier->soft_role_staging_writes == 0 &&
                 carrier->soft_role_staging_destination_mask == 0)) &&
            (!carrier->output_depth_memory ||
                (!carrier->depth_memory_poisoned &&
                 carrier->depth_capture_destination == -1 &&
                 carrier->depth_layer_offset == 0 &&
                 carrier->depth_staging_writes == 0 &&
                 carrier->depth_staging_destination_mask == 0));
        semantic_carrier_restored =
            semantic_carrier_quiescent &&
            !output_written_carrier_mode &&
            !output_continuous_soft_role_rematerialization_mode;
        if (carrier) {
            semantic_carrier_graph_input_sets =
                carrier->graph_input_sets;
            semantic_carrier_host_to_backend_bytes =
                carrier->host_to_backend_bytes;
            semantic_carrier_backend_to_graph_bytes =
                carrier->backend_to_graph_bytes;
            semantic_carrier_hidden_slot_backend_bytes =
                carrier->hidden_slot_backend_bytes;
            semantic_carrier_phase_memory_backend_bytes =
                carrier->phase_memory_backend_bytes;
            semantic_carrier_phase_binding_upload_bytes =
                carrier->phase_binding_upload_bytes;
            semantic_carrier_phase_backend_copy_bytes =
                carrier->phase_backend_copy_bytes;
            semantic_carrier_phase_element_operations =
                carrier->phase_element_operations;
            semantic_carrier_phase_graph_applications =
                carrier->phase_graph_applications;
            semantic_carrier_phase_commits =
                carrier->phase_commits;
            semantic_carrier_phase_rotation_upload_bytes =
                carrier->phase_rotation_upload_bytes;
            semantic_carrier_phase_rotation_element_operations =
                carrier->phase_rotation_element_operations;
            semantic_carrier_phase_rotations =
                carrier->phase_rotations;
            semantic_carrier_soft_role_backend_bytes =
                carrier->soft_role_backend_bytes;
            semantic_carrier_soft_role_candidate_id_upload_bytes =
                carrier->soft_role_candidate_id_upload_bytes;
            semantic_carrier_soft_role_gate_upload_bytes =
                carrier->soft_role_gate_upload_bytes;
            semantic_carrier_soft_role_capture_device_copy_bytes =
                carrier->soft_role_capture_device_copy_bytes;
            semantic_carrier_soft_role_commit_device_copy_bytes =
                carrier->soft_role_commit_device_copy_bytes;
            semantic_carrier_soft_role_read_device_copy_bytes =
                carrier->soft_role_read_device_copy_bytes;
            semantic_carrier_soft_role_projection_token_applications =
                carrier->soft_role_projection_token_applications;
            semantic_carrier_soft_role_projection_multiply_accumulates =
                carrier->soft_role_projection_multiply_accumulates;
            semantic_carrier_soft_role_mixture_multiply_accumulates =
                carrier->soft_role_mixture_multiply_accumulates;
            semantic_carrier_soft_role_captures =
                carrier->soft_role_captures;
            semantic_carrier_soft_role_commits =
                carrier->soft_role_commits;
            semantic_carrier_soft_role_reads =
                carrier->soft_role_reads;
            semantic_carrier_depth_memory_backend_bytes =
                carrier->depth_memory_backend_bytes;
            semantic_carrier_depth_capture_device_copy_bytes =
                carrier->depth_capture_device_copy_bytes;
            semantic_carrier_depth_commit_device_copy_bytes =
                carrier->depth_commit_device_copy_bytes;
            semantic_carrier_depth_read_device_copy_bytes =
                carrier->depth_read_device_copy_bytes;
            semantic_carrier_depth_cross_attention_multiply_accumulates =
                carrier
                    ->depth_cross_attention_multiply_accumulates;
            semantic_carrier_depth_captures =
                carrier->depth_captures;
            semantic_carrier_depth_commits =
                carrier->depth_commits;
            semantic_carrier_depth_reads =
                carrier->depth_reads;
            semantic_carrier_writer_host_input_bytes =
                carrier->writer_host_input_bytes;
            semantic_carrier_port_writes =
                carrier->port_writes;
            semantic_carrier_router_bias_token_applications =
                carrier->router_bias_token_applications;
            semantic_carrier_router_bias_enabled_token_applications =
                carrier->router_bias_enabled_token_applications;
            semantic_carrier_router_bias_multiply_accumulates =
                carrier->router_bias_multiply_accumulates;
            semantic_carrier_recurrent_transition_token_applications =
                carrier->recurrent_transition_token_applications;
            semantic_carrier_recurrent_transition_enabled_token_applications =
                carrier
                    ->recurrent_transition_enabled_token_applications;
            semantic_carrier_map_multiply_accumulates =
                carrier->carrier_map_multiply_accumulates;
            semantic_carrier_optimizer_parameter_read_bytes =
                carrier->optimizer_parameter_read_bytes;
            semantic_carrier_optimizer_parameter_write_bytes =
                carrier->optimizer_parameter_write_bytes;
            semantic_carrier_port_hash =
                fnv1a64(
                    carrier->port.data(),
                    carrier->port.size() * sizeof(float));
            semantic_carrier_generation =
                carrier->generation;
        }
    }

    const auto & acceptance = spec.at("acceptance_law");
    const auto & primary =
        route_summary.at(candidate_route);
    bool all_candidate_logits_finite = true;
    for (const auto & [route, variants_by_id] : outputs) {
        (void) route;
        for (const auto & [variant_id, boundaries] :
             variants_by_id) {
            (void) variant_id;
            for (const auto & boundary : boundaries) {
                all_candidate_logits_finite =
                    all_candidate_logits_finite &&
                    std::all_of(
                        boundary.candidate_logits.begin(),
                        boundary.candidate_logits.end(),
                        [](float value) {
                            return std::isfinite(value);
                        });
            }
        }
    }
    const bool accepted =
        all_candidate_logits_finite &&
        primary.at("correct").get<size_t>() ==
            acceptance.at("primary_correct").get<size_t>() &&
        primary.at("boundary_matches").get<size_t>() ==
            acceptance.at("primary_boundary_matches").get<size_t>() &&
        (!orbit_mode ||
            return_boundary_matches ==
                acceptance.at(
                    "return_boundary_matches").get<size_t>()) &&
        (!trained_semantic_carrier_mode ||
            (semantic_adapter_build.training_correct ==
                 semantic_training_sample_count &&
             (!output_written_semantic_port_mode ||
                 (semantic_adapter_build.writer_training_correct ==
                     semantic_training_sample_count &&
                 semantic_adapter_build.coupled_training_correct ==
                     semantic_training_sample_count &&
                 semantic_carrier_port_writes ==
                     comparisons +
                         (end_to_end_semantic_carrier_training
                             ? semantic_optimizer_steps
                             : 0))) &&
             (!output_written_hidden_slot_mode ||
                 semantic_carrier_port_writes == comparisons) &&
             (!output_phase_memory_mode ||
                 (semantic_adapter_build.coupled_training_correct ==
                      semantic_training_sample_count &&
                  (output_phase_orbit_memory_mode
                    ? semantic_carrier_port_writes ==
                          spec.at("queries_per_variant")
                              .get<size_t>() &&
                      semantic_carrier_phase_graph_applications ==
                          spec.at("queries_per_variant")
                              .get<size_t>() +
                          variants.size() - 1 &&
                      semantic_carrier_phase_commits == 1 &&
                      semantic_carrier_phase_rotations ==
                          variants.size() - 1
                    : semantic_carrier_port_writes ==
                          comparisons &&
                      semantic_carrier_phase_graph_applications ==
                          comparisons &&
                      semantic_carrier_phase_commits ==
                          variants.size()))) &&
             carrier_disabled_boundary_matches <=
                 acceptance.at(
                     "carrier_disabled_boundary_matches_maximum")
                     .get<size_t>() &&
             (!end_to_end_semantic_carrier_training ||
                (semantic_optimizer_steps ==
                     static_cast<uint64_t>(
                         spec.at(
                             "semantic_carrier_optimizer_epochs")
                             .get<uint32_t>()) *
                         spec.at(
                             "output_written_port_training_contexts")
                             .size() *
                         spec.at("queries_per_variant")
                             .get<size_t>() &&
                 semantic_optimizer_output_map_hash !=
                     semantic_optimizer_output_map_initial_hash)) &&
             (output_written_carrier_mode
                ? semantic_carrier_quiescent
                : semantic_carrier_restored))) &&
        (!output_depth_memory_mode ||
            (semantic_carrier_quiescent &&
             semantic_carrier_port_writes == comparisons &&
             semantic_carrier_depth_captures == comparisons &&
             semantic_carrier_depth_commits == variants.size() &&
             semantic_carrier_depth_reads > 0 &&
             carrier_disabled_boundary_matches <=
                 acceptance.at(
                     "carrier_disabled_boundary_matches_maximum")
                     .get<size_t>() &&
             wrong_layer_boundary_matches <=
                 acceptance.at(
                     "wrong_layer_boundary_matches_maximum")
                     .get<size_t>())) &&
        (!output_continuous_soft_role_rematerialization_mode ||
            (semantic_carrier_quiescent &&
             semantic_carrier_port_writes == comparisons &&
             semantic_carrier_soft_role_captures == comparisons &&
             semantic_carrier_soft_role_commits == variants.size() &&
             semantic_carrier_soft_role_reads == comparisons &&
             carrier_disabled_boundary_matches <=
                 acceptance.at(
                     "carrier_disabled_boundary_matches_maximum")
                     .get<size_t>())) &&
        (!output_recurrent_delta_advance_mode ||
            (recurrent_output_delta_extraction_count == comparisons &&
             recurrent_output_delta_accumulation_count ==
                 variants.size() &&
             recurrent_output_delta_graph_applications ==
                 comparisons + variants.size() &&
             recurrent_output_delta_logical_row_bytes > 0 &&
             recurrent_output_delta_candidate_physical_row_stable &&
             carrier_disabled_boundary_matches <=
                 acceptance.at(
                     "carrier_disabled_boundary_matches_maximum")
                     .get<size_t>())) &&
        (!output_role_transport_mode ||
            (role_transport_training_correct ==
                 spec.at("role_transport_training_contexts").size() *
                 variants.size() *
                 spec.at("queries_per_variant").get<size_t>() &&
             role_transport_operator.training_samples ==
                 spec.at("role_transport_training_contexts").size() *
                 variants.size() *
                 spec.at("queries_per_variant").get<size_t>())) &&
        (!output_role_generator_mode ||
            (role_transport_training_correct ==
                 spec.at("role_generator_training_contexts").size() *
                 variants.size() *
                 spec.at("queries_per_variant").get<size_t>() &&
             role_generator_operator.training_pairs ==
                 spec.at("role_generator_training_contexts").size() *
                 variants.size() *
                 spec.at("queries_per_variant").get<size_t>())) &&
        (!output_attention_kernel_writer_mode ||
            (role_transport_training_correct ==
                 spec.at(
                     "attention_kernel_writer_training_contexts").size() *
                 variants.size() *
                 spec.at("queries_per_variant").get<size_t>() &&
             attention_kernel_writer_operator.training_samples ==
                 spec.at(
                     "attention_kernel_writer_training_contexts").size() *
                 variants.size() *
                 spec.at("queries_per_variant").get<size_t>())) &&
        (!output_source_fixed_cell_rematerialization_mode ||
            (all_destination_cell_identities_stable &&
             initial_destination_cell_ids ==
                final_destination_cell_ids)) &&
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
        if (!scaffold_preparation_sequence_closed) {
            close_sequence(scaffold_seq, "sparse:scaffold-close");
            ++sequence_close_count;
        }
    }
    llama_memory_clear(memory, true);
    llama_synchronize(ctx);
    if (trained_semantic_carrier_mode ||
        output_depth_memory_mode ||
        output_continuous_soft_role_rematerialization_mode) {
        ctx->clear_neo3000_semantic_carrier();
        if (ctx->get_neo3000_semantic_carrier()) {
            throw std::runtime_error(
                "semantic carrier close failed");
        }
    }
    const bool semantic_carrier_closed =
        !ctx->get_neo3000_semantic_carrier();
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
            !legacy_trained_semantic_carrier_mode &&
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
        orbit_mode
            ? output_source_rematerialization_mode
                ? source_role_rematerialization_tokens
                : 0
            : variants.size() * label_offsets.size();
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
        candidate_source_tokens +
        reference_source_tokens +
        semantic_training_source_tokens +
        semantic_optimizer_source_tokens +
        role_transport_training_source_tokens;
    return {
        {"schema_version", 1},
        {"mechanism", output_recurrent_delta_advance_mode
            ? "ACTUAL_OUTPUT_RECURRENT_DELTA_COMPOSITION"
            : output_phase_memory_mode
            ? output_phase_orbit_memory_mode
                ? "OUTPUT_INITIALIZED_NATIVE_CYCLIC_PHASE_ORBIT"
                : "ACTUAL_OUTPUT_SHARED_PHASE_FAST_WEIGHT_MEMORY"
            : output_depth_memory_mode
            ? "OUTPUT_FED_DEPTH_RESOLVED_MODEL_NATIVE_CROSS_ATTENTION_MEMORY"
            : output_written_hidden_slot_mode
            ? "ACTUAL_OUTPUT_WRITTEN_RESIDENT_HIDDEN_SLOT_CARRIER"
            : output_written_semantic_port_mode
            ? end_to_end_semantic_carrier_training
                ? "END_TO_END_LEARNED_OUTPUT_WRITTEN_MODEL_NATIVE_CARRIER_READER"
            : semantic_carrier_layer_delta_mode
                ? semantic_carrier_recurrent_transition_mode
                    ? "ACTUAL_OUTPUT_WRITTEN_RECURRENT_STATE_TRANSITION"
                    : semantic_carrier_moe_router_bias_mode
                        ? "ACTUAL_OUTPUT_WRITTEN_MOE_ROUTER_STATE_TRANSITION"
                        : "ACTUAL_OUTPUT_WRITTEN_LAYER_LOCAL_NONLINEAR_SEMANTIC_PORT"
                : "ACTUAL_OUTPUT_WRITTEN_ROLE_INVARIANT_SEMANTIC_PORT"
            : output_source_fixed_cell_rematerialization_mode
            ? "ACTUAL_OUTPUT_SOURCE_ROLE_FIXED_CELL_KV_ADVANCE"
            : output_continuous_soft_role_rematerialization_mode
                ? "CONTINUOUS_PREPROJECTION_SOURCE_ROLE_REMATERIALIZATION"
            : output_source_relink_rematerialization_mode
                ? "ACTUAL_OUTPUT_TOKEN_SOURCE_POSITION_REMATERIALIZATION"
            : subspace_value_orbit_mode
            ? subspace_include_keys
                ? build_subspace_operator
                    ? "IN_PLACE_STATE_CONDITIONED_LOW_RANK_KEY_VALUE_ACTION"
                    : "TRANSFERRED_STATE_CONDITIONED_LOW_RANK_KEY_VALUE_ACTION"
                : build_subspace_operator
                    ? "IN_PLACE_STATE_CONDITIONED_LOW_RANK_VALUE_ACTION"
                    : "TRANSFERRED_STATE_CONDITIONED_LOW_RANK_VALUE_ACTION"
            : fourier_value_orbit_mode
            ? "IN_PLACE_RANK3_FOURIER_LABEL_VALUE_ACTION"
            : trained_semantic_carrier_mode
            ? semantic_carrier_layer_delta_mode
                ? "TRAINED_LAYER_LOCAL_NONLINEAR_SEMANTIC_CARRIER"
                : "TRAINED_FIXED_CAPACITY_PRELOGIT_SEMANTIC_CARRIER"
            : model_weight_value_orbit_mode
            ? "MODEL_WEIGHT_DERIVED_SEMANTIC_VALUE_CYCLE"
            : output_attention_kernel_writer_mode
            ? "OUTPUT_CONDITIONED_REDUCED_RANK_ATTENTION_STATE_WRITER"
            : output_role_generator_mode
            ? "SHARED_NONLINEAR_OUTPUT_ROLE_ATTENTION_GENERATOR"
            : output_role_transport_mode
            ? "TRAINED_OUTPUT_TO_SOURCE_ATTENTION_ROLE_TRANSPORT"
            : output_promoted_value_carrier_mode
            ? "OUTPUT_PROMOTED_IN_PLACE_ATTENTION_VALUE_CARRIER"
            : complex_phase_orbit_mode
            ? paired_complex_attention_read
                ? "IN_PLACE_VALUE_PHASE_WITH_LAYER_LOCAL_PAIRED_COMPLEX_ATTENTION_READ"
                : "IN_PLACE_COMPLEX_KV_PHASE_QUARTER_TURN"
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
            {"complex_phase_include_keys",
                complex_phase_include_keys},
            {"paired_complex_attention_read",
                paired_complex_attention_read},
            {"paired_complex_attention_layer",
                paired_complex_attention_layer},
            {"paired_complex_attention_mix",
                paired_complex_attention_mix},
            {"fourier_value_orbit_action",
                fourier_value_orbit_mode},
            {"subspace_value_orbit_action",
                subspace_value_orbit_mode},
            {"model_weight_value_orbit_action",
                model_weight_value_orbit_mode},
            {"output_promoted_value_carrier_action",
                output_promoted_value_carrier_mode},
            {"output_role_transport_action",
                output_role_transport_mode},
            {"output_role_generator_action",
                output_role_generator_mode},
            {"output_attention_kernel_writer_action",
                output_attention_kernel_writer_mode},
            {"output_source_position_rematerialization_action",
                output_source_relink_rematerialization_mode},
            {"output_source_position_fixed_cell_rematerialization_action",
                output_source_fixed_cell_rematerialization_mode},
            {"output_continuous_soft_role_rematerialization_action",
                output_continuous_soft_role_rematerialization_mode},
            {"output_written_semantic_port_action",
                output_written_semantic_port_mode},
            {"output_written_hidden_slot_action",
                output_written_hidden_slot_mode},
            {"output_depth_resolved_cross_attention_memory_action",
                output_depth_memory_mode},
            {"output_phase_memory_action",
                output_phase_feedback_memory_mode},
            {"output_phase_orbit_memory_action",
                output_phase_orbit_memory_mode},
            {"phase_memory_width",
                output_phase_memory_mode
                    ? spec.at("phase_memory_width")
                    : json(0)},
            {"phase_memory_seed",
                output_phase_memory_mode
                    ? spec.at("phase_memory_seed")
                    : json(0)},
            {"end_to_end_semantic_carrier_training",
                end_to_end_semantic_carrier_training},
            {"semantic_carrier_optimizer_epochs",
                end_to_end_semantic_carrier_training
                    ? spec.at(
                        "semantic_carrier_optimizer_epochs")
                    : json(0)},
            {"semantic_carrier_optimizer_learning_rate",
                end_to_end_semantic_carrier_training
                    ? spec.at(
                        "semantic_carrier_optimizer_learning_rate")
                    : json(0.0)},
            {"semantic_carrier_optimizer_flash_attention",
                end_to_end_semantic_carrier_training
                    ? json(false)
                    : json(nullptr)},
            {"semantic_carrier_optimizer_target_variant",
                end_to_end_semantic_carrier_training
                    ? spec.at(
                        "semantic_carrier_optimizer_target_variant")
                    : json(0)},
            {"output_recurrent_delta_advance_action",
                output_recurrent_delta_advance_mode},
            {"output_promotion_label_indices",
                output_promotion_label_indices},
            {"role_transport_training_contexts",
                output_role_transport_mode
                    ? spec.at(
                        "role_transport_training_contexts").size()
                    : 0},
            {"role_transport_ridge_fraction",
                output_role_transport_mode
                    ? spec.at(
                        "role_transport_ridge_fraction")
                    : json(0.0)},
            {"role_generator_training_contexts",
                output_role_generator_mode
                    ? spec.at(
                        "role_generator_training_contexts").size()
                    : 0},
            {"role_generator_hidden_width",
                output_role_generator_mode
                    ? spec.at(
                        "role_generator_hidden_width")
                    : json(0)},
            {"role_generator_seed",
                output_role_generator_mode
                    ? spec.at("role_generator_seed")
                    : json(0)},
            {"role_generator_ridge_fraction",
                output_role_generator_mode
                    ? spec.at(
                        "role_generator_ridge_fraction")
                    : json(0.0)},
            {"attention_kernel_writer_training_contexts",
                output_attention_kernel_writer_mode
                    ? spec.at(
                        "attention_kernel_writer_training_contexts").size()
                    : 0},
            {"attention_kernel_writer_ridge_fraction",
                output_attention_kernel_writer_mode
                    ? spec.at(
                        "attention_kernel_writer_ridge_fraction")
                    : json(0.0)},
            {"trained_semantic_carrier_action",
                legacy_trained_semantic_carrier_mode},
            {"semantic_carrier_layer_delta_training",
                semantic_carrier_layer_delta_mode},
            {"semantic_carrier_moe_router_bias",
                semantic_carrier_moe_router_bias_mode},
            {"semantic_carrier_recurrent_transition_input",
                semantic_carrier_recurrent_transition_mode},
            {"semantic_carrier_read_layer",
                semantic_carrier_read_layer},
            {"carrier_adapter_training_contexts",
                legacy_trained_semantic_carrier_mode
                    ? spec.at(
                        "carrier_adapter_training_contexts").size()
                    : 0},
            {"output_written_port_training_contexts",
                trained_semantic_carrier_mode &&
                    output_written_carrier_mode
                    ? spec.at(
                        "output_written_port_training_contexts").size()
                    : 0},
            {"carrier_adapter_ridge_fraction",
                trained_semantic_carrier_mode
                    ? spec.at(
                        "carrier_adapter_ridge_fraction")
                    : json(0.0)},
            {"carrier_adapter_output_gain",
                legacy_trained_semantic_carrier_mode
                    ? spec.at(
                        "carrier_adapter_output_gain")
                    : json(0.0)},
            {"output_written_port_training_margin",
                (output_written_semantic_port_mode ||
                 output_phase_memory_mode)
                    ? spec.at(
                        "output_written_port_training_margin")
                    : json(0.0)},
            {"output_written_port_maximum_gain",
                (output_written_semantic_port_mode ||
                 output_phase_memory_mode)
                    ? spec.at(
                        "output_written_port_maximum_gain")
                    : json(0.0)},
            {"output_written_port_target_variant_index",
                output_written_semantic_port_mode &&
                    semantic_carrier_layer_delta_mode
                    ? spec.at(
                        "output_written_port_target_variant_index")
                    : json(0)},
            {"subspace_include_keys",
                subspace_include_keys},
            {"subspace_operator_built_in_this_panel",
                subspace_value_orbit_mode &&
                build_subspace_operator},
            {"model_weight_semantic_tokens",
                model_weight_operator_build.semantic_tokens},
            {"model_weight_code_norms",
                model_weight_operator_build.code_norms},
            {"model_weight_operator_hash",
                model_weight_value_orbit_mode
                    ? hex64(
                        model_weight_operator_build.operator_hash)
                    : ""},
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
            {"semantic_training_samples",
                semantic_training_sample_count},
            {"semantic_training_correct",
                semantic_adapter_build.training_correct},
            {"semantic_training_max_abs_error",
                semantic_adapter_build.training_max_abs_error},
            {"semantic_writer_training_correct",
                semantic_adapter_build.writer_training_correct},
            {"semantic_writer_training_max_abs_error",
                semantic_adapter_build
                    .writer_training_max_abs_error},
            {"semantic_coupled_training_correct",
                semantic_adapter_build.coupled_training_correct},
            {"semantic_coupled_output_gain",
                semantic_adapter_build.coupled_output_gain},
            {"semantic_coupled_training_minimum_margin",
                semantic_adapter_build
                    .coupled_training_minimum_margin},
            {"phase_self_score_max_abs_error",
                semantic_adapter_build
                    .phase_self_score_max_abs_error},
            {"phase_cross_score_max_abs",
                semantic_adapter_build
                    .phase_cross_score_max_abs},
            {"phase_rotation_four_step_max_abs_error",
                semantic_adapter_build
                    .phase_rotation_four_step_max_abs_error},
            {"phase_training_retrieval_minimum_margin",
                semantic_adapter_build
                    .phase_training_retrieval_minimum_margin},
            {"semantic_optimizer_steps",
                semantic_optimizer_steps},
            {"semantic_optimizer_loss_first",
                semantic_optimizer_loss_first},
            {"semantic_optimizer_loss_last",
                semantic_optimizer_loss_last},
            {"semantic_optimizer_predicted_target_count",
                semantic_optimizer_predicted_target_count},
            {"semantic_optimizer_output_map_changed",
                semantic_optimizer_output_map_hash !=
                    semantic_optimizer_output_map_initial_hash},
            {"carrier_disabled_correct",
                carrier_disabled_correct},
            {"carrier_disabled_boundary_matches",
                carrier_disabled_boundary_matches},
            {"all_candidate_logits_finite",
                all_candidate_logits_finite},
            {"wrong_layer_correct",
                wrong_layer_correct},
            {"wrong_layer_boundary_matches",
                wrong_layer_boundary_matches},
            {"recurrent_output_delta_extractions",
                recurrent_output_delta_extraction_count},
            {"recurrent_output_delta_accumulations",
                recurrent_output_delta_accumulation_count},
            {"recurrent_output_delta_candidate_physical_row_stable",
                recurrent_output_delta_candidate_physical_row_stable},
            {"semantic_carrier_restored",
                semantic_carrier_restored},
            {"semantic_carrier_quiescent_on_same_backing",
                semantic_carrier_quiescent},
            {"semantic_carrier_closed",
                semantic_carrier_closed},
            {"role_transport_training_samples",
                role_transport_operator.training_samples},
            {"role_transport_training_correct",
                role_transport_training_correct},
            {"role_transport_training_max_abs_error",
                role_transport_operator.training_max_abs_error},
            {"role_generator_training_pairs",
                role_generator_operator.training_pairs},
            {"role_generator_training_rows",
                role_generator_operator.training_rows},
            {"role_generator_training_max_abs_error",
                role_generator_operator.training_max_abs_error},
            {"role_generator_training_root_mean_squared_error",
                role_generator_operator
                    .training_root_mean_squared_error},
            {"attention_kernel_writer_training_samples",
                attention_kernel_writer_operator.training_samples},
            {"attention_kernel_writer_samples_per_destination",
                attention_kernel_writer_operator
                    .samples_per_destination},
            {"attention_kernel_writer_maximum_rank",
                attention_kernel_writer_operator.maximum_rank},
            {"attention_kernel_writer_training_max_abs_error",
                attention_kernel_writer_operator
                    .training_max_abs_error},
            {"accepted", accepted},
        }},
        {"carrier", {
            {"active_cache_backend_allocation_bytes",
                active_cache_backend_allocation_bytes},
            {"maximum_retained_root_backend_allocation_bytes", 0},
            {"active_plus_retained_backend_allocation_bytes",
                active_cache_backend_allocation_bytes +
                    semantic_carrier_depth_memory_backend_bytes},
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
            {"semantic_carrier_action_backing_id",
                trained_semantic_carrier_mode ||
                    output_depth_memory_mode ||
                    output_continuous_soft_role_rematerialization_mode
                    ? hex64(
                        semantic_carrier_backing_initial)
                    : ""},
            {"semantic_carrier_same_backing_restored",
                semantic_carrier_restored},
            {"semantic_carrier_reader_quiescent_on_same_backing",
                semantic_carrier_quiescent},
            {"semantic_port_final_hash",
                output_written_semantic_port_mode
                    ? hex64(semantic_carrier_port_hash)
                    : ""},
            {"semantic_port_writes",
                semantic_carrier_port_writes},
            {"phase_memory_backend_bytes",
                semantic_carrier_phase_memory_backend_bytes},
            {"phase_memory_commits",
                semantic_carrier_phase_commits},
            {"phase_memory_rotations",
                semantic_carrier_phase_rotations},
            {"semantic_carrier_closed",
                semantic_carrier_closed},
            {"recurrent_output_delta_candidate_physical_row_initial",
                recurrent_output_delta_candidate_physical_row_initial},
            {"recurrent_output_delta_candidate_physical_row_final",
                recurrent_output_delta_candidate_physical_row_final},
            {"recurrent_output_delta_candidate_physical_row_stable",
                recurrent_output_delta_candidate_physical_row_stable},
            {"initial_destination_cell_ids",
                initial_destination_cell_ids},
            {"final_destination_cell_ids",
                final_destination_cell_ids},
            {"all_destination_cell_identities_stable",
                all_destination_cell_identities_stable},
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
            {"semantic_training_source_tokens",
                semantic_training_source_tokens},
            {"semantic_training_query_tokens",
                semantic_training_query_tokens},
            {"semantic_training_output_tokens",
                semantic_training_output_tokens},
            {"semantic_optimizer_source_tokens",
                semantic_optimizer_source_tokens},
            {"semantic_optimizer_query_tokens",
                semantic_optimizer_query_tokens},
            {"semantic_optimizer_output_tokens",
                semantic_optimizer_output_tokens},
            {"all_route_input_tokens",
                source_decode_tokens +
                query_decode_tokens +
                semantic_training_query_tokens +
                semantic_training_output_tokens +
                semantic_optimizer_query_tokens +
                semantic_optimizer_output_tokens +
                useful_output_decode_tokens +
                role_transport_training_query_tokens +
                role_transport_training_output_tokens},
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
            {"output_promotion_row_count",
                output_promotion_row_count},
            {"recurrent_output_delta_extractions",
                recurrent_output_delta_extraction_count},
            {"recurrent_output_delta_accumulations",
                recurrent_output_delta_accumulation_count},
            {"recurrent_output_delta_logical_row_bytes",
                recurrent_output_delta_logical_row_bytes},
            {"recurrent_output_delta_backend_read_bytes",
                recurrent_output_delta_backend_read_bytes},
            {"recurrent_output_delta_backend_write_bytes",
                recurrent_output_delta_backend_write_bytes},
            {"recurrent_output_delta_arithmetic_element_operations",
                recurrent_output_delta_arithmetic_element_operations},
            {"recurrent_output_delta_tensor_visits",
                recurrent_output_delta_tensor_visits},
            {"recurrent_output_delta_graph_applications",
                recurrent_output_delta_graph_applications},
            {"recurrent_output_delta_scheduler_compute_bytes_initial",
                recurrent_output_delta_scheduler_compute_bytes_initial},
            {"recurrent_output_delta_scheduler_compute_bytes_peak",
                recurrent_output_delta_scheduler_compute_bytes_peak},
            {"recurrent_output_delta_extraction_wall_ms_total",
                recurrent_output_delta_extraction_wall_ms_total},
            {"recurrent_output_delta_accumulation_wall_ms_total",
                recurrent_output_delta_accumulation_wall_ms_total},
            {"recurrent_output_delta_host_payload_bytes", 0},
            {"useful_output_decode_tokens",
                useful_output_decode_tokens},
            {"useful_output_decode_wall_ms_total",
                useful_output_decode_wall_ms_total},
            {"source_role_rematerialization_tokens",
                source_role_rematerialization_tokens},
            {"source_role_rematerialization_wall_ms_total",
                source_role_rematerialization_wall_ms_total},
            {"source_role_rematerialization_projected_token_bytes",
                output_continuous_soft_role_rematerialization_mode
                    ? 0
                    : source_role_rematerialization_tokens *
                        sizeof(llama_token)},
            {"source_role_rematerialization_expected_answer_consulted",
                false},
            {"source_role_rematerialization_phase_table_consulted",
                false},
            {"fixed_cell_complete_key_value_copy",
                output_source_fixed_cell_rematerialization_mode},
            {"role_transport_training_source_tokens",
                role_transport_training_source_tokens},
            {"role_transport_training_query_tokens",
                role_transport_training_query_tokens},
            {"role_transport_training_output_tokens",
                role_transport_training_output_tokens},
            {"role_transport_training_correct",
                role_transport_training_correct},
            {"role_transport_training_host_read_bytes",
                role_transport_training_host_read_bytes},
            {"role_transport_training_peak_host_work_bytes",
                role_transport_training_peak_host_work_bytes},
            {"role_transport_builder_peak_bytes",
                role_transport_builder_peak_bytes},
            {"role_transport_finalize_peak_host_work_bytes",
                role_transport_finalize_peak_host_work_bytes},
            {"role_transport_logical_bytes",
                role_transport_operator.logical_bytes},
            {"role_transport_vector_backing_bytes",
                role_transport_operator.vector_backing_bytes},
            {"role_transport_layer_operators",
                role_transport_operator.layers.size()},
            {"role_transport_training_max_abs_error",
                role_transport_operator.training_max_abs_error},
            {"role_generator_logical_bytes",
                role_generator_operator.logical_bytes},
            {"role_generator_vector_backing_bytes",
                role_generator_operator.vector_backing_bytes},
            {"role_generator_training_pairs",
                role_generator_operator.training_pairs},
            {"role_generator_training_rows",
                role_generator_operator.training_rows},
            {"role_generator_training_max_abs_error",
                role_generator_operator.training_max_abs_error},
            {"role_generator_training_root_mean_squared_error",
                role_generator_operator
                    .training_root_mean_squared_error},
            {"role_generator_training_peak_host_work_bytes",
                role_generator_finalize_metrics
                    .peak_training_host_work_bytes},
            {"role_generator_runtime_parameter_upload_bytes",
                role_generator_runtime_parameter_upload_bytes},
            {"role_generator_runtime_host_carrier_read_bytes",
                uint64_t(0)},
            {"role_generator_runtime_host_carrier_write_bytes",
                uint64_t(0)},
            {"role_generator_runtime_graph_applications",
                role_generator_runtime_graph_applications},
            {"role_generator_runtime_generated_rows",
                role_generator_runtime_generated_rows},
            {"role_generator_runtime_multiply_accumulates",
                role_generator_runtime_multiply_accumulates},
            {"attention_kernel_writer_logical_bytes",
                attention_kernel_writer_operator.logical_bytes},
            {"attention_kernel_writer_vector_backing_bytes",
                attention_kernel_writer_operator
                    .vector_backing_bytes},
            {"attention_kernel_writer_layer_operators",
                attention_kernel_writer_operator.layers.size()},
            {"attention_kernel_writer_total_rank",
                attention_kernel_writer_operator.total_rank},
            {"attention_kernel_writer_maximum_rank",
                attention_kernel_writer_operator.maximum_rank},
            {"attention_kernel_writer_training_max_abs_error",
                attention_kernel_writer_operator
                    .training_max_abs_error},
            {"attention_kernel_writer_training_peak_host_work_bytes",
                attention_kernel_writer_finalize_metrics
                    .peak_training_host_work_bytes},
            {"attention_kernel_writer_runtime_parameter_upload_bytes",
                attention_kernel_writer_runtime_parameter_upload_bytes},
            {"attention_kernel_writer_runtime_host_carrier_read_bytes",
                uint64_t(0)},
            {"attention_kernel_writer_runtime_host_carrier_write_bytes",
                uint64_t(0)},
            {"attention_kernel_writer_runtime_graph_applications",
                attention_kernel_writer_runtime_graph_applications},
            {"attention_kernel_writer_runtime_generated_rows",
                attention_kernel_writer_runtime_generated_rows},
            {"attention_kernel_writer_runtime_multiply_accumulates",
                attention_kernel_writer_runtime_multiply_accumulates},
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
            {"model_weight_source_tensor_read_bytes",
                model_weight_operator_build
                    .source_tensor_read_bytes},
            {"model_weight_builder_bytes",
                model_weight_operator_build.builder_bytes},
            {"model_weight_operator_logical_bytes",
                model_weight_operator_build
                    .value_operator.logical_bytes},
            {"model_weight_operator_vector_backing_bytes",
                model_weight_operator_build
                    .value_operator.vector_backing_bytes},
            {"model_weight_operator_total_rank",
                model_weight_operator_build
                    .value_operator.total_rank},
            {"model_weight_operator_maximum_layer_rank",
                model_weight_operator_build
                    .value_operator.maximum_layer_rank},
            {"model_weight_operator_calibration_max_abs_error",
                model_weight_operator_build
                    .value_operator.calibration_max_abs_error},
            {"model_weight_operator_closure_max_abs_error",
                model_weight_operator_build
                    .value_operator
                    .subspace_closure_max_abs_error},
            {"model_weight_operator_construction_peak_host_work_bytes",
                model_weight_operator_build
                    .peak_host_work_bytes},
            {"semantic_carrier_training_samples",
                semantic_training_sample_count},
            {"semantic_carrier_ridge_lambda",
                semantic_adapter_build.ridge_lambda},
            {"semantic_carrier_training_max_abs_error",
                semantic_adapter_build.training_max_abs_error},
            {"semantic_carrier_writer_training_samples",
                output_written_semantic_port_mode
                    ? semantic_training_sample_count
                    : 0},
            {"semantic_carrier_writer_ridge_lambda",
                semantic_adapter_build.writer_ridge_lambda},
            {"semantic_carrier_writer_training_correct",
                semantic_adapter_build.writer_training_correct},
            {"semantic_carrier_writer_training_max_abs_error",
                semantic_adapter_build
                    .writer_training_max_abs_error},
            {"semantic_carrier_coupled_training_correct",
                semantic_adapter_build.coupled_training_correct},
            {"semantic_carrier_coupled_output_gain",
                semantic_adapter_build.coupled_output_gain},
            {"semantic_carrier_coupled_training_minimum_margin",
                semantic_adapter_build
                    .coupled_training_minimum_margin},
            {"semantic_carrier_output_dual_max_abs_error",
                semantic_adapter_build
                    .output_dual_max_abs_error},
            {"semantic_carrier_output_delta_training_max_abs_error",
                semantic_adapter_build
                    .output_delta_training_max_abs_error},
            {"semantic_carrier_model_tensor_read_bytes",
                semantic_adapter_build
                    .source_tensor_read_bytes},
            {"semantic_carrier_logical_bytes",
                semantic_adapter_build.logical_bytes +
                    semantic_carrier_hidden_slot_backend_bytes +
                    semantic_carrier_phase_memory_backend_bytes +
                    semantic_carrier_soft_role_backend_bytes +
                    semantic_carrier_depth_memory_backend_bytes},
            {"semantic_carrier_hash",
                trained_semantic_carrier_mode
                    ? hex64(semantic_adapter_build.hash)
                    : ""},
            {"semantic_carrier_training_feature_peak_bytes",
                semantic_training_feature_peak_bytes},
            {"semantic_carrier_training_peak_host_work_bytes",
                semantic_adapter_build
                    .peak_host_work_bytes},
            {"semantic_carrier_optimizer_steps",
                semantic_optimizer_steps},
            {"semantic_carrier_optimizer_parameter_bytes",
                semantic_optimizer_parameter_bytes},
            {"semantic_carrier_optimizer_parameter_read_bytes",
                semantic_carrier_optimizer_parameter_read_bytes},
            {"semantic_carrier_optimizer_parameter_write_bytes",
                semantic_carrier_optimizer_parameter_write_bytes},
            {"semantic_carrier_optimizer_scheduler_compute_bytes_initial",
                semantic_optimizer_scheduler_compute_bytes_initial},
            {"semantic_carrier_optimizer_scheduler_compute_bytes_peak",
                semantic_optimizer_scheduler_compute_bytes_peak},
            {"semantic_carrier_optimizer_loss_first",
                semantic_optimizer_loss_first},
            {"semantic_carrier_optimizer_loss_last",
                semantic_optimizer_loss_last},
            {"semantic_carrier_optimizer_predicted_target_count",
                semantic_optimizer_predicted_target_count},
            {"semantic_carrier_optimizer_output_map_initial_hash",
                end_to_end_semantic_carrier_training
                    ? hex64(
                        semantic_optimizer_output_map_initial_hash)
                    : ""},
            {"semantic_carrier_optimizer_output_map_final_hash",
                end_to_end_semantic_carrier_training
                    ? hex64(
                        semantic_optimizer_output_map_hash)
                    : ""},
            {"semantic_carrier_graph_input_sets",
                semantic_carrier_graph_input_sets},
            {"semantic_carrier_host_to_backend_bytes",
                semantic_carrier_host_to_backend_bytes},
            {"semantic_carrier_backend_to_graph_bytes",
                semantic_carrier_backend_to_graph_bytes},
            {"semantic_carrier_hidden_slot_backend_bytes",
                semantic_carrier_hidden_slot_backend_bytes},
            {"semantic_carrier_phase_memory_backend_bytes",
                semantic_carrier_phase_memory_backend_bytes},
            {"semantic_carrier_phase_binding_upload_bytes",
                semantic_carrier_phase_binding_upload_bytes},
            {"semantic_carrier_phase_backend_copy_bytes",
                semantic_carrier_phase_backend_copy_bytes},
            {"semantic_carrier_phase_element_operations",
                semantic_carrier_phase_element_operations},
            {"semantic_carrier_phase_graph_applications",
                semantic_carrier_phase_graph_applications},
            {"semantic_carrier_phase_commits",
                semantic_carrier_phase_commits},
            {"semantic_carrier_phase_rotation_upload_bytes",
                semantic_carrier_phase_rotation_upload_bytes},
            {"semantic_carrier_phase_rotation_element_operations",
                semantic_carrier_phase_rotation_element_operations},
            {"semantic_carrier_phase_rotations",
                semantic_carrier_phase_rotations},
            {"semantic_carrier_soft_role_backend_bytes",
                semantic_carrier_soft_role_backend_bytes},
            {"semantic_carrier_soft_role_candidate_id_upload_bytes",
                semantic_carrier_soft_role_candidate_id_upload_bytes},
            {"semantic_carrier_soft_role_gate_upload_bytes",
                semantic_carrier_soft_role_gate_upload_bytes},
            {"semantic_carrier_soft_role_capture_device_copy_bytes",
                semantic_carrier_soft_role_capture_device_copy_bytes},
            {"semantic_carrier_soft_role_commit_device_copy_bytes",
                semantic_carrier_soft_role_commit_device_copy_bytes},
            {"semantic_carrier_soft_role_read_device_copy_bytes",
                semantic_carrier_soft_role_read_device_copy_bytes},
            {"semantic_carrier_soft_role_projection_token_applications",
                semantic_carrier_soft_role_projection_token_applications},
            {"semantic_carrier_soft_role_projection_multiply_accumulates",
                semantic_carrier_soft_role_projection_multiply_accumulates},
            {"semantic_carrier_soft_role_mixture_multiply_accumulates",
                semantic_carrier_soft_role_mixture_multiply_accumulates},
            {"semantic_carrier_soft_role_captures",
                semantic_carrier_soft_role_captures},
            {"semantic_carrier_soft_role_commits",
                semantic_carrier_soft_role_commits},
            {"semantic_carrier_soft_role_reads",
                semantic_carrier_soft_role_reads},
            {"semantic_carrier_depth_memory_backend_bytes",
                semantic_carrier_depth_memory_backend_bytes},
            {"semantic_carrier_depth_capture_device_copy_bytes",
                semantic_carrier_depth_capture_device_copy_bytes},
            {"semantic_carrier_depth_commit_device_copy_bytes",
                semantic_carrier_depth_commit_device_copy_bytes},
            {"semantic_carrier_depth_read_device_copy_bytes",
                semantic_carrier_depth_read_device_copy_bytes},
            {"semantic_carrier_depth_cross_attention_multiply_accumulates",
                semantic_carrier_depth_cross_attention_multiply_accumulates},
            {"semantic_carrier_depth_captures",
                semantic_carrier_depth_captures},
            {"semantic_carrier_depth_commits",
                semantic_carrier_depth_commits},
            {"semantic_carrier_depth_reads",
                semantic_carrier_depth_reads},
            {"semantic_carrier_writer_host_input_bytes",
                semantic_carrier_writer_host_input_bytes},
            {"semantic_carrier_port_writes",
                semantic_carrier_port_writes},
            {"semantic_carrier_router_bias_token_applications",
                semantic_carrier_router_bias_token_applications},
            {"semantic_carrier_router_bias_enabled_token_applications",
                semantic_carrier_router_bias_enabled_token_applications},
            {"semantic_carrier_router_bias_multiply_accumulates",
                semantic_carrier_router_bias_multiply_accumulates},
            {"semantic_carrier_recurrent_transition_token_applications",
                semantic_carrier_recurrent_transition_token_applications},
            {"semantic_carrier_recurrent_transition_enabled_token_applications",
                semantic_carrier_recurrent_transition_enabled_token_applications},
            {"semantic_carrier_map_multiply_accumulates",
                semantic_carrier_map_multiply_accumulates},
            {"semantic_carrier_port_final_hash",
                output_written_semantic_port_mode
                    ? hex64(semantic_carrier_port_hash)
                    : ""},
            {"semantic_carrier_generation",
                semantic_carrier_generation},
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
        {"training_records", semantic_training_records},
        {"semantic_optimizer_records",
            semantic_optimizer_records},
        {"role_transport_training_records",
            role_transport_training_records},
        {"output_promotion_records",
            output_promotion_records},
        {"recurrent_output_delta_records",
            recurrent_output_delta_records},
        {"source_role_rematerialization_records",
            source_role_rematerialization_records},
        {"fixed_cell_identity_records",
            fixed_cell_identity_records},
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
