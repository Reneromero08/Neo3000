#include "arg.h"
#include "common.h"
#include "llama.h"
#include "log.h"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using json = nlohmann::ordered_json;

namespace {

struct probe_result {
    json record;
    std::vector<float> candidate_logits;
    uint64_t full_logits_fnv1a64 = 0;
};

static void print_usage(int, char ** argv) {
    LOG("\nusage:\n");
    LOG("\n  %s -m MODEL --control-vector-scaled VECTOR:SCALE \\\n", argv[0]);
    LOG("      --control-vector-layer-range START END -f CASES.json -o RESULT.json\n\n");
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

static std::string hex64(uint64_t value) {
    std::ostringstream stream;
    stream << std::hex << std::setfill('0') << std::setw(16) << value;
    return stream.str();
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

static probe_result run_prompt(
        llama_context * ctx,
        const llama_vocab * vocab,
        const std::vector<llama_token> & candidates,
        const std::string & case_id,
        const std::string & arm,
        const std::string & prompt,
        bool carrier_enabled) {
    if (llama_set_adapter_cvec_enabled(ctx, carrier_enabled) != 0) {
        throw std::runtime_error("failed to change resident carrier state");
    }
    if (llama_adapter_cvec_enabled(ctx) != carrier_enabled) {
        throw std::runtime_error("resident carrier state did not change");
    }

    llama_memory_clear(llama_get_memory(ctx), true);

    auto tokens = common_tokenize(ctx, prompt, true, true);
    if (tokens.empty()) {
        throw std::runtime_error("prompt tokenization produced no tokens");
    }
    if (tokens.size() > llama_n_ctx(ctx)) {
        throw std::runtime_error("prompt exceeds context");
    }

    const auto started = std::chrono::steady_clock::now();
    auto batch = llama_batch_init(static_cast<int32_t>(tokens.size()), 0, 1);
    for (size_t i = 0; i < tokens.size(); ++i) {
        common_batch_add(batch, tokens[i], static_cast<llama_pos>(i), {0}, i + 1 == tokens.size());
    }
    const int decode_status = llama_decode(ctx, batch);
    llama_batch_free(batch);
    if (decode_status != 0) {
        throw std::runtime_error("llama_decode failed with status " + std::to_string(decode_status));
    }
    const float * logits = llama_get_logits_ith(ctx, -1);
    if (!logits) {
        throw std::runtime_error("no terminal logits");
    }
    const auto finished = std::chrono::steady_clock::now();

    const int32_t n_vocab = llama_vocab_n_tokens(vocab);
    probe_result result;
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

    double probability_sum = 0.0;
    std::vector<double> probabilities;
    probabilities.reserve(candidates.size());
    for (float value : result.candidate_logits) {
        const double probability = std::exp(static_cast<double>(value - max_logit));
        probabilities.push_back(probability);
        probability_sum += probability;
    }
    for (double & value : probabilities) {
        value /= probability_sum;
    }

    result.record = {
        {"case_id", case_id},
        {"arm", arm},
        {"carrier_enabled", carrier_enabled},
        {"prompt_fnv1a64", hex64(fnv1a64(prompt.data(), prompt.size()))},
        {"token_count", tokens.size()},
        {"candidate_token_ids", candidates},
        {"candidate_logits", result.candidate_logits},
        {"candidate_softmax", probabilities},
        {"candidate_argmax", std::string(1, static_cast<char>('A' + max_index))},
        {"full_logits_fnv1a64", hex64(result.full_logits_fnv1a64)},
        {"wall_ms", std::chrono::duration<double, std::milli>(finished - started).count()},
        {"carrier_backing_id", hex64(llama_adapter_cvec_backing_id(ctx))},
        {"carrier_resident_bytes", llama_adapter_cvec_resident_bytes(ctx)},
        {"carrier_upload_count", llama_adapter_cvec_upload_count(ctx)},
    };
    return result;
}

static json candidate_interaction(
        const probe_result & f0g0,
        const probe_result & f1g0,
        const probe_result & f0g1,
        const probe_result & f1g1) {
    json result = json::object();
    for (size_t i = 0; i < 4; ++i) {
        const double interaction =
            static_cast<double>(f1g1.candidate_logits[i])
            - static_cast<double>(f1g0.candidate_logits[i])
            - static_cast<double>(f0g1.candidate_logits[i])
            + static_cast<double>(f0g0.candidate_logits[i]);
        result[std::string(1, static_cast<char>('A' + i))] = interaction;
    }
    return result;
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
    if (params.prompt_file.empty() || params.out_file.empty() || params.control_vectors.empty()) {
        print_usage(argc, argv);
        return 1;
    }

    std::ifstream cases_stream(params.prompt_file);
    if (!cases_stream) {
        LOG_ERR("failed to open cases file: %s\n", params.prompt_file.c_str());
        return 1;
    }
    json spec;
    cases_stream >> spec;
    if (!spec.contains("cases") || !spec["cases"].is_array() || spec["cases"].empty()) {
        LOG_ERR("cases file contains no cases\n");
        return 1;
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
        const llama_vocab * vocab = llama_model_get_vocab(model);
        const auto candidates = candidate_tokens(vocab);

        const uint64_t initial_backing_id = llama_adapter_cvec_backing_id(ctx);
        const size_t initial_resident_bytes = llama_adapter_cvec_resident_bytes(ctx);
        const uint64_t initial_upload_count = llama_adapter_cvec_upload_count(ctx);
        if (initial_backing_id == 0 || initial_resident_bytes == 0 || initial_upload_count != 1) {
            throw std::runtime_error("control vector was not initialized exactly once");
        }

        json records = json::array();
        json adjudication = json::array();
        size_t joint_correct = 0;
        size_t f_only_correct = 0;
        size_t g_only_correct = 0;
        bool restoration_exact = true;
        bool backing_stable = true;
        bool upload_count_stable = true;

        for (const auto & test_case : spec["cases"]) {
            const std::string id = test_case.at("id").get<std::string>();
            const std::string expected = test_case.at("expected").get<std::string>();
            const std::string prompt_g0 = test_case.at("prompt_g0").get<std::string>();
            const std::string prompt_g1 = test_case.at("prompt_g1").get<std::string>();
            const std::string prompt_g_mut = test_case.at("prompt_g_mut").get<std::string>();

            auto f0g0 = run_prompt(ctx, vocab, candidates, id, "F0_G0", prompt_g0, false);
            auto f1g0 = run_prompt(ctx, vocab, candidates, id, "F1_G0", prompt_g0, true);
            auto f0g1 = run_prompt(ctx, vocab, candidates, id, "F0_G1", prompt_g1, false);
            auto f1g1 = run_prompt(ctx, vocab, candidates, id, "F1_G1", prompt_g1, true);
            auto f1g_mut = run_prompt(ctx, vocab, candidates, id, "F1_G_MUT", prompt_g_mut, true);
            auto f0g1_after = run_prompt(ctx, vocab, candidates, id, "F0_G1_AFTER", prompt_g1, false);

            for (const auto * result : {&f0g0, &f1g0, &f0g1, &f1g1, &f1g_mut, &f0g1_after}) {
                records.push_back(result->record);
                backing_stable &= llama_adapter_cvec_backing_id(ctx) == initial_backing_id;
                upload_count_stable &= llama_adapter_cvec_upload_count(ctx) == initial_upload_count;
            }

            const bool restored =
                f0g1.full_logits_fnv1a64 == f0g1_after.full_logits_fnv1a64
                && f0g1.candidate_logits == f0g1_after.candidate_logits;
            restoration_exact &= restored;

            const std::string f1g1_argmax = f1g1.record.at("candidate_argmax").get<std::string>();
            const std::string f1g0_argmax = f1g0.record.at("candidate_argmax").get<std::string>();
            const std::string f0g1_argmax = f0g1.record.at("candidate_argmax").get<std::string>();
            joint_correct += f1g1_argmax == expected;
            f_only_correct += f1g0_argmax == expected;
            g_only_correct += f0g1_argmax == expected;

            adjudication.push_back({
                {"case_id", id},
                {"expected", expected},
                {"joint_argmax", f1g1_argmax},
                {"f_only_argmax", f1g0_argmax},
                {"g_only_argmax", f0g1_argmax},
                {"mutated_relation_argmax", f1g_mut.record.at("candidate_argmax")},
                {"restoration_exact", restored},
                {"candidate_logit_interaction", candidate_interaction(f0g0, f1g0, f0g1, f1g1)},
            });
        }

        const bool disabled_at_close = llama_set_adapter_cvec_enabled(ctx, false) == 0
            && !llama_adapter_cvec_enabled(ctx);
        const auto & acceptance = spec.at("acceptance_law");
        const size_t joint_correct_minimum = acceptance.at("joint_correct_minimum").get<size_t>();
        const bool accepted =
            joint_correct >= joint_correct_minimum
            && (!acceptance.value("joint_must_exceed_f_only", false) || joint_correct > f_only_correct)
            && (!acceptance.value("joint_must_exceed_g_only", false) || joint_correct > g_only_correct)
            && (!acceptance.value("carrier_disable_restore_exact", false) || restoration_exact)
            && (!acceptance.value("same_backing_all_arms", false) || backing_stable)
            && initial_upload_count == acceptance.value("carrier_upload_count", initial_upload_count)
            && upload_count_stable
            && disabled_at_close;

        json result = {
            {"schema_version", 1},
            {"mechanism", "MODEL_NATIVE_RESIDUAL_CONTROL_VECTOR_CARRIER_CAUSALITY_PROBE"},
            {"spec_id", spec.value("id", "unknown")},
            {"model_path_supplied", true},
            {"model_arch", "qwen35moe"},
            {"candidate_labels", {"A", "B", "C", "D"}},
            {"configuration", {
                {"control_vector_path", params.control_vectors.front().fname},
                {"control_vector_strength", params.control_vectors.front().strength},
                {"control_vector_layer_start", params.control_vector_layer_start},
                {"control_vector_layer_end", params.control_vector_layer_end},
                {"ctx_size", llama_n_ctx(ctx)},
            }},
            {"carrier", {
                {"dimension_per_layer", llama_model_n_embd(model)},
                {"resident_bytes", initial_resident_bytes},
                {"backing_id", hex64(initial_backing_id)},
                {"upload_count", initial_upload_count},
                {"same_backing_all_arms", backing_stable},
                {"upload_count_stable", upload_count_stable},
                {"disabled_at_close", disabled_at_close},
            }},
            {"records", records},
            {"adjudication", adjudication},
            {"summary", {
                {"case_count", spec["cases"].size()},
                {"joint_correct", joint_correct},
                {"f_only_correct", f_only_correct},
                {"g_only_correct", g_only_correct},
                {"restoration_exact_all", restoration_exact},
            }},
            {"verdict", accepted ? "accept" : "reject"},
            {"claim_ceiling",
             "This probe can establish only that a fixed device-resident residual vector is read before logits, "
             "changes a held-out useful boundary, survives disable/enable cycles on the same allocated backing, "
             "and exhibits a measured joint interaction with prompt evidence. It does not establish an unresolved "
             "relational carrier, noncommuting composition, phase-native advantage, reduced fresh compute, or "
             "constructively unbounded catalytic inference."},
        };

        std::ofstream result_stream(params.out_file);
        result_stream << result.dump(2) << '\n';
        result_stream.close();
        LOG_INF("wrote %s\n", params.out_file.c_str());
    } catch (const std::exception & error) {
        LOG_ERR("carrier probe failed: %s\n", error.what());
        llama_backend_free();
        return 1;
    }

    llama_backend_free();
    return 0;
}
