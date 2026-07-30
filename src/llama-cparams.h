#pragma once

#include "llama.h"

#include <array>
#include <cstdint>
#include <memory>
#include <vector>

#define LLAMA_MAX_SEQ 256

struct ggml_tensor;

// Experimental fixed-capacity semantic carrier used only by the Neo3000
// frontier probe. The query/output maps are immutable after installation.
struct llama_neo3000_semantic_carrier {
    uint32_t n_embd = 0;
    uint32_t n_expert = 0;
    int32_t read_layer = -1;        // -1: post-norm pre-LM-head
    std::vector<float> query_map;   // [4, n_embd] GGML layout [n_embd, 4]
    std::array<float, 4> query_bias = {};
    std::vector<float> writer_map;  // [4, n_embd] GGML layout [n_embd, 4]
    std::array<float, 4> writer_bias = {};
    std::vector<float> output_map;  // [n_embd, 4] GGML layout [4, n_embd]
    // `port` is the retained role-invariant 4x4 process state. In
    // output-written mode `action` stays zero and acts only as the disabled
    // graph input; the enabled graph input reads `port` directly. Legacy
    // phase mode continues to materialize its 4x4 action here.
    std::array<float, 16> port = {};
    std::array<float, 16> action = {};
    // Hidden-slot mode retains four complete actual-output layer states in
    // one dedicated backend allocation. The graph reads this tensor
    // device-to-device; no retained host mirror of the slot payload exists.
    std::shared_ptr<void> hidden_slot_backing;
    ggml_tensor * hidden_slots = nullptr; // [n_embd, 4]
    // Phase-memory mode retains one shared complex fast-weight vector and a
    // separate staging vector in one backend allocation. Actual projected
    // outputs add public destination/value bindings to staging. A phase
    // commit copies staging to active only after the complete causal panel,
    // so an in-flight panel cannot observe its own partial successor.
    std::shared_ptr<void> phase_memory_backing;
    ggml_tensor * phase_active = nullptr;  // [2 * phase_width]
    ggml_tensor * phase_staging = nullptr; // [2 * phase_width]
    std::vector<float> phase_binding_table; // [16, 2 * phase_width]
    std::vector<float> phase_reader;        // [16, 2 * phase_width]
    std::vector<float> phase_generator;     // [2 * phase_width]
    uint32_t phase_width = 0;
    uint32_t phase_staging_writes = 0;
    uint32_t phase_staging_destination_mask = 0;
    uint32_t phase = 0;
    bool enabled = false;
    bool output_written = false;
    bool output_hidden_slots = false;
    bool output_phase_memory = false;
    bool native_phase_orbit = false;
    bool phase_poisoned = false;
    bool output_map_trainable = false;
    bool moe_router_bias = false;
    bool recurrent_transition_input = false;
    uint64_t generation = 0;
    uint64_t action_backing_id = 0;
    uint64_t graph_input_sets = 0;
    uint64_t host_to_backend_bytes = 0;
    uint64_t backend_to_graph_bytes = 0;
    uint64_t hidden_slot_backend_bytes = 0;
    uint64_t phase_memory_backend_bytes = 0;
    uint64_t phase_binding_upload_bytes = 0;
    uint64_t phase_backend_copy_bytes = 0;
    uint64_t phase_element_operations = 0;
    uint64_t phase_graph_applications = 0;
    uint64_t phase_commits = 0;
    uint64_t phase_rotation_upload_bytes = 0;
    uint64_t phase_rotation_element_operations = 0;
    uint64_t phase_rotations = 0;
    uint64_t writer_host_input_bytes = 0;
    uint64_t port_writes = 0;
    uint64_t router_bias_token_applications = 0;
    uint64_t router_bias_enabled_token_applications = 0;
    uint64_t router_bias_multiply_accumulates = 0;
    uint64_t recurrent_transition_token_applications = 0;
    uint64_t recurrent_transition_enabled_token_applications = 0;
    uint64_t carrier_map_multiply_accumulates = 0;
    uint64_t optimizer_steps = 0;
    uint64_t optimizer_parameter_read_bytes = 0;
    uint64_t optimizer_parameter_write_bytes = 0;
};

struct llama_neo3000_semantic_optimizer_metrics {
    double loss = 0.0;
    int32_t predicted_token = LLAMA_TOKEN_NULL;
    uint64_t parameter_bytes = 0;
    uint64_t scheduler_compute_bytes_before = 0;
    uint64_t scheduler_compute_bytes_after = 0;
};

struct llama_cparams {
    uint32_t n_ctx;           // context size used during inference
    uint32_t n_ctx_seq;       // context for a single sequence
    uint32_t n_batch;
    uint32_t n_ubatch;
    uint32_t n_seq_max;
    uint32_t n_rs_seq;        // number of recurrent-state snapshots per seq for rollback
    uint32_t n_outputs_max;   // max outputs supported by the context
    int32_t  n_threads;       // number of threads to use for generation
    int32_t  n_threads_batch; // number of threads to use for batch processing

    int32_t  nextn_layer_offset = 0;

    float rope_freq_base;
    float rope_freq_scale;

    uint32_t n_ctx_orig_yarn;
    // These hyperparameters are not exposed in GGUF, because all
    // existing YaRN models use the same values for them.
    float yarn_ext_factor;
    float yarn_attn_factor;
    float yarn_beta_fast;
    float yarn_beta_slow;

    // Experimental graph-local paired-complex attention read. A negative
    // layer disables the branch. Kept internal to the Neo3000 probe.
    float   neo3000_paired_complex_attention_mix   = 0.0f;
    int32_t neo3000_paired_complex_attention_layer = -1;
    std::shared_ptr<llama_neo3000_semantic_carrier>
        neo3000_semantic_carrier;

    bool embeddings;
    bool embeddings_nextn;        // also extract the hidden state before the final output norm
    bool embeddings_nextn_masked; // extract for only rows where batch.logits != 0
    bool causal_attn;
    bool offload_kqv;
    bool flash_attn;
    bool auto_fa;
    bool fused_gdn_ar;       // use fused gated delta net (autoregressive)
    bool fused_gdn_ch;       // use fused gated delta net (chunked)
    bool auto_fgdn;
    bool no_perf;
    bool warmup;             // TODO: remove [TAG_LLAMA_GRAPH_NO_WARMUP]
    bool op_offload;
    bool kv_unified;
    bool pipeline_parallel;

    std::vector<bool> embeddings_layer_inp; // [n_layer()] extract input embeddings for layer

    enum llama_context_type ctx_type;
    enum llama_pooling_type pooling_type;

    ggml_backend_sched_eval_callback cb_eval;
    void * cb_eval_user_data;

    llama_context * ctx_other;
};
