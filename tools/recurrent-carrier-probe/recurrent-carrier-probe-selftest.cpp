#include "recurrent-carrier-evidence.h"
#include "neo3000-lifting-lifecycle.h"

#include "ggml-backend.h"
#include "ggml-cpu.h"
#include "ggml.h"

#include <nlohmann/json.hpp>

#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#include <unistd.h>

using json = nlohmann::ordered_json;

namespace {

void require(bool condition, const std::string & message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

struct lifting_state {
    int32_t lifting_capture_kind = 0;
    int32_t lifting_capture_slot = -1;
    uint32_t lifting_f_key_mask = 0;
    uint32_t lifting_f_value_mask = 0;
    uint32_t lifting_g_key_mask = 0;
    uint32_t lifting_g_value_mask = 0;
    bool lifting_update_resident = false;
    bool lifting_poisoned = false;
    bool enabled = false;
    uint64_t lifting_commits = 0;
};

void complete_panel(lifting_state & state) {
    for (int32_t kind = 1; kind <= 4; ++kind) {
        for (int32_t slot = 0; slot < 4; ++slot) {
            require(
                neo3000::lifting_try_arm_capture(
                    state, kind, slot),
                "complete panel arm failed");
            require(
                neo3000::lifting_mark_capture_complete(state),
                "complete panel capture failed");
        }
    }
}

void test_terminal_numeric_boundary() {
    const std::vector<int32_t> candidates = {0, 1, 2, 3};
    const std::array<float, 4> finite = {1.0f, 2.0f, 3.0f, 4.0f};
    const auto finite_result =
        neo3000::evidence::analyze_terminal_logits(
            finite.data(), finite.size(), candidates);
    require(finite_result.valid(), "finite logits rejected");
    require(
        finite_result.argmax_index == 3,
        "finite argmax incorrect");
    require(
        finite_result.candidate_softmax.size() == 4,
        "finite softmax absent");

    for (float invalid : {
             std::numeric_limits<float>::quiet_NaN(),
             std::numeric_limits<float>::infinity(),
             -std::numeric_limits<float>::infinity()}) {
        std::array<float, 4> values = finite;
        values[2] = invalid;
        const auto result =
            neo3000::evidence::analyze_terminal_logits(
                values.data(), values.size(), candidates);
        require(!result.valid(), "nonfinite logits admitted");
        require(
            !result.argmax_index.has_value(),
            "nonfinite logits emitted argmax");
        require(
            result.nonfinite_count == 1 &&
                result.first_nonfinite_position == 2,
            "nonfinite position accounting incorrect");
    }

    const std::array<float, 4> mixed = {
        std::numeric_limits<float>::quiet_NaN(),
        1.0f,
        std::numeric_limits<float>::infinity(),
        -std::numeric_limits<float>::infinity(),
    };
    const auto mixed_result =
        neo3000::evidence::analyze_terminal_logits(
            mixed.data(), mixed.size(), candidates);
    require(
        !mixed_result.valid() &&
            mixed_result.nonfinite_count == 3 &&
            mixed_result.candidate_nonfinite_count == 3 &&
            mixed_result.first_nonfinite_position == 0 &&
            !mixed_result.argmax_index.has_value(),
        "mixed finite/nonfinite case did not fail closed");

    const std::array<float, 4> all_nonfinite = {
        std::numeric_limits<float>::quiet_NaN(),
        std::numeric_limits<float>::infinity(),
        -std::numeric_limits<float>::infinity(),
        std::numeric_limits<float>::quiet_NaN(),
    };
    const auto all_result =
        neo3000::evidence::analyze_terminal_logits(
            all_nonfinite.data(), all_nonfinite.size(), candidates);
    require(
        !all_result.valid() &&
            all_result.nonfinite_count == 4 &&
            !all_result.argmax_index.has_value(),
        "all-nonfinite case did not fail closed");
}

void test_atomic_result_boundary() {
    require(
        neo3000::evidence::sha256_hex("abc", 3) ==
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        "SHA-256 implementation failed known vector");
    const auto nonce =
        std::to_string(getpid()) + "-" +
        std::to_string(
            std::chrono::steady_clock::now()
                .time_since_epoch().count());
    const auto path =
        std::filesystem::temp_directory_path() /
        ("neo3000-evidence-selftest-" + nonce + ".json");
    const std::string payload = "{\"status\":\"verified\"}\n";
    const auto receipt =
        neo3000::evidence::atomic_write_text(path, payload);
    require(
        receipt.bytes == payload.size() &&
            receipt.sha256 ==
                neo3000::evidence::sha256_hex(
                    payload.data(), payload.size()) &&
            std::filesystem::exists(path),
        "atomic result success receipt invalid");
    bool overwrite_rejected = false;
    try {
        neo3000::evidence::atomic_write_text(
            path, "{\"status\":\"overwritten\"}\n");
    } catch (const std::exception &) {
        overwrite_rejected = true;
    }
    std::ifstream committed(path, std::ios::binary);
    const std::string committed_payload{
        std::istreambuf_iterator<char>(committed),
        std::istreambuf_iterator<char>()};
    require(
        overwrite_rejected && committed_payload == payload,
        "atomic result overwrite was not rejected intact");

    bool failed_closed = false;
    try {
        neo3000::evidence::atomic_write_text(
            "/proc/neo3000-evidence-selftest/result.json",
            payload);
    } catch (const std::exception &) {
        failed_closed = true;
    }
    require(
        failed_closed,
        "unwritable terminal result path did not fail closed");
}

void test_mechanism_exclusivity() {
    json spec = {
        {"sources", json::object()},
        {"queries", json::array()},
        {"sparse_g_label_refresh", true},
        {"value_orbit_attention_action", true},
        {"source_conditioned_lifting_action", false},
    };
    const auto selection =
        neo3000::evidence::select_exactly_one_mechanism(spec);
    require(
        selection.mechanism ==
            "sparse_g_label_refresh:"
            "value_orbit_attention_action",
        "lifting mechanism selection incorrect");

    spec["source_conditioned_lifting_action"] = true;
    bool incompatible_rejected = false;
    try {
        neo3000::evidence::select_exactly_one_mechanism(spec);
    } catch (const std::exception &) {
        incompatible_rejected = true;
    }
    require(
        incompatible_rejected,
        "incompatible sparse actions were admitted");

    spec["source_conditioned_lifting_action"] = false;
    spec["unknown_scientific_action"] = true;
    bool unknown_rejected = false;
    try {
        neo3000::evidence::select_exactly_one_mechanism(spec);
    } catch (const std::exception &) {
        unknown_rejected = true;
    }
    require(
        unknown_rejected,
        "unknown scientific action was admitted");
}

void test_lifting_lifecycle_and_factor_zeroing() {
    lifting_state partial;
    require(
        neo3000::lifting_try_arm_capture(partial, 1, 0),
        "partial capture did not arm");
    require(
        neo3000::lifting_mark_capture_complete(partial),
        "partial capture did not complete");
    neo3000::lifting_mark_poisoned(partial);
    require(
        partial.lifting_poisoned &&
            !partial.lifting_update_resident &&
            partial.lifting_f_key_mask == 0 &&
            partial.lifting_capture_kind == 0 &&
            partial.lifting_capture_slot == -1,
        "partial capture poisoning did not close state");

    lifting_state complete;
    complete_panel(complete);
    require(
        neo3000::lifting_can_commit(complete, 0),
        "complete masks did not admit commit");
    neo3000::lifting_mark_committed(complete);
    require(
        complete.lifting_commits == 1 &&
            !complete.lifting_update_resident &&
            complete.lifting_f_key_mask == 0 &&
            complete.lifting_g_value_mask == 0,
        "commit did not close masks");
    require(
        neo3000::lifting_can_begin_g_update(complete, 0),
        "next G update was not admitted");
    neo3000::lifting_mark_g_update_started(complete);
    require(
        complete.lifting_f_key_mask == 0x0fu &&
            complete.lifting_f_value_mask == 0x0fu &&
            complete.lifting_g_key_mask == 0 &&
            complete.lifting_update_resident,
        "G update did not preserve F custody");

    std::vector<uint8_t> active(128, 0);
    std::vector<uint8_t> staging(128, 0);
    active[7] = 9;
    staging[11] = 5;
    neo3000::evidence::factor_payload_digest before;
    neo3000::evidence::factor_digest_update(
        before, active.data(), active.size(), 1);
    neo3000::evidence::factor_digest_update(
        before, staging.data(), staging.size(), 2);
    require(
        before.nonzero_bytes == 2,
        "preclose factor digest missed payload");
    std::fill(active.begin(), active.end(), 0);
    std::fill(staging.begin(), staging.end(), 0);
    neo3000::evidence::factor_payload_digest after;
    neo3000::evidence::factor_digest_update(
        after, active.data(), active.size(), 1);
    neo3000::evidence::factor_digest_update(
        after, staging.data(), staging.size(), 2);
    require(
        after.nonzero_bytes == 0 &&
            after.bytes == active.size() + staging.size() &&
            after.fnv1a64 != before.fnv1a64,
        "factor zero closure digest failed");
}

void test_out_prod_numerics() {
    ggml_backend_t backend = ggml_backend_cpu_init();
    require(backend != nullptr, "CPU backend init failed");
    ggml_init_params params = {
        /*.mem_size   =*/ 1024 * 1024,
        /*.mem_buffer =*/ nullptr,
        /*.no_alloc   =*/ true,
    };
    ggml_context * ctx = ggml_init(params);
    require(ctx != nullptr, "GGML context init failed");
    ggml_tensor * values =
        ggml_new_tensor_2d(ctx, GGML_TYPE_F32, 3, 2);
    ggml_tensor * coefficients =
        ggml_new_tensor_2d(ctx, GGML_TYPE_F32, 4, 2);
    ggml_tensor * output =
        ggml_out_prod(ctx, values, coefficients);
    require(
        output->ne[0] == 3 && output->ne[1] == 4,
        "OUT_PROD output shape is not [n_embd,n_tokens]");
    ggml_cgraph * graph = ggml_new_graph_custom(ctx, 32, false);
    ggml_build_forward_expand(graph, output);
    ggml_backend_buffer_t buffer =
        ggml_backend_alloc_ctx_tensors(ctx, backend);
    require(buffer != nullptr, "GGML tensor allocation failed");

    const std::array<float, 6> value_data = {
        1.0f, 2.0f, 3.0f,
        -1.0f, 0.5f, 4.0f,
    };
    const std::array<float, 8> coefficient_data = {
        2.0f, 0.0f, -1.0f, 3.0f,
        1.0f, -2.0f, 0.5f, 4.0f,
    };
    ggml_backend_tensor_set(
        values, value_data.data(), 0, sizeof(value_data));
    ggml_backend_tensor_set(
        coefficients,
        coefficient_data.data(),
        0,
        sizeof(coefficient_data));
    require(
        ggml_backend_graph_compute(backend, graph) ==
            GGML_STATUS_SUCCESS,
        "OUT_PROD graph compute failed");
    std::array<float, 12> actual = {};
    ggml_backend_tensor_get(
        output, actual.data(), 0, sizeof(actual));
    for (size_t token = 0; token < 4; ++token) {
        for (size_t embd = 0; embd < 3; ++embd) {
            const float expected =
                value_data[embd] * coefficient_data[token] +
                value_data[3 + embd] *
                    coefficient_data[4 + token];
            require(
                std::abs(actual[token * 3 + embd] - expected) <
                    1e-6f,
                "OUT_PROD numerical value mismatch");
        }
    }
    ggml_backend_buffer_free(buffer);
    ggml_free(ctx);
    ggml_backend_free(backend);
}

void test_predecessor_admission(const std::filesystem::path & root) {
    std::ifstream stream(
        root /
        "lab/source-conditioned-low-rank-out-product-fast-weight-v1.json");
    require(stream.is_open(), "failed to open frozen 0162 spec");
    json spec;
    stream >> spec;
    const auto selection =
        neo3000::evidence::select_exactly_one_mechanism(spec);
    require(
        selection.mechanism ==
            "sparse_g_label_refresh:"
            "source_conditioned_lifting_action",
        "frozen 0162 mechanism selection failed");
    const auto receipt =
        neo3000::evidence::verify_declared_predecessor(
            spec, root / "lab/predecessor-evidence-locks.json");
    require(
        receipt.bytes == 2964 &&
            receipt.sha256 ==
                "71c906be8f25a8f29525be1f7fadae8e73879287f5ced4b4c397a92132eac573" &&
            receipt.classification ==
                "GGML_TRANSPOSED_LEFT_MUL_MAT_ASSERT_BEFORE_ENABLED_LIFTING_COMPUTE",
        "0161 predecessor admission receipt mismatch");

    spec["predecessor_evidence"]["classification"] = "WRONG";
    bool mismatch_rejected = false;
    try {
        neo3000::evidence::verify_declared_predecessor(
            spec, root / "lab/predecessor-evidence-locks.json");
    } catch (const std::exception &) {
        mismatch_rejected = true;
    }
    require(
        mismatch_rejected,
        "predecessor classification mismatch was admitted");

    spec["predecessor_evidence"]["classification"] =
        "GGML_TRANSPOSED_LEFT_MUL_MAT_ASSERT_BEFORE_ENABLED_LIFTING_COMPUTE";
    spec["mystery_geometry"] = 7;
    bool unknown_field_rejected = false;
    try {
        neo3000::evidence::select_exactly_one_mechanism(spec);
    } catch (const std::exception &) {
        unknown_field_rejected = true;
    }
    require(
        unknown_field_rejected,
        "unknown lifting scientific field was admitted");
}

} // namespace

int main(int argc, char ** argv) {
    try {
        const std::filesystem::path root =
            argc > 1 ? argv[1] : std::filesystem::current_path();
        test_terminal_numeric_boundary();
        test_atomic_result_boundary();
        test_mechanism_exclusivity();
        test_lifting_lifecycle_and_factor_zeroing();
        test_out_prod_numerics();
        test_predecessor_admission(root);
        std::cout
            << "PASS terminal_numeric_cases=6"
            << " atomic_result_cases=3"
            << " mechanism_exclusivity_cases=4"
            << " lifting_lifecycle_cases=2"
            << " factor_digest_cases=2"
            << " out_prod_shape_cases=1"
            << " out_prod_value_cases=12"
            << " predecessor_cases=2\n";
        return 0;
    } catch (const std::exception & error) {
        std::cerr << "FAIL " << error.what() << '\n';
        return 1;
    }
}
