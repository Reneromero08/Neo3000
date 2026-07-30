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
    // Continuous-role mode retains four unresolved preprojection mixtures as
    // model-input embeddings. The terminal graph derives each mixture from
    // the four public candidate logits and frozen token-embedding rows before
    // any host-selected token can drive the update. A later one-token model
    // forward reads one active slot at a public source-role position.
    std::shared_ptr<void> soft_role_backing;
    ggml_tensor * soft_role_active = nullptr;  // [n_embd, 4]
    ggml_tensor * soft_role_staging = nullptr; // [n_embd, 4]
    std::array<ggml_tensor *, 4> soft_role_active_slots = {};
    std::array<ggml_tensor *, 4> soft_role_staging_slots = {};
    std::array<llama_token, 4> soft_role_candidate_tokens = {};
    int32_t soft_role_capture_destination = -1;
    int32_t soft_role_read_slot = -1;
    uint32_t soft_role_staging_writes = 0;
    uint32_t soft_role_staging_destination_mask = 0;
    // Depth-resolved output memory retains the actual output-token layer
    // input at every full-attention layer for four public query ordinals.
    // Active and staging panels remain device resident. Each graph read
    // receives either the corresponding active layer panel, an exact-zero
    // panel, or the same active bytes under one public cyclic layer
    // permutation.
    std::shared_ptr<void> depth_memory_backing;
    ggml_tensor * depth_active = nullptr;  // [n_embd, 4, n_depth_layers]
    ggml_tensor * depth_staging = nullptr; // [n_embd, 4, n_depth_layers]
    ggml_tensor * depth_zero_layer = nullptr; // [n_embd, 4]
    std::vector<int32_t> depth_layers;
    std::vector<ggml_tensor *> depth_active_layers;
    std::vector<ggml_tensor *> depth_staging_slots;
    uint32_t depth_projected_kv_width = 0;
    int32_t depth_capture_destination = -1;
    uint32_t depth_layer_offset = 0;
    uint32_t depth_staging_writes = 0;
    uint32_t depth_staging_destination_mask = 0;
    // Source-conditioned lifting mode retains four layer-local factor
    // panels. F maps item state toward vault state; G maps the resulting
    // state toward code state. The graph applies each as a rank-four coupling
    // before frozen Q/K/V projections, lets Q/K/V consume the transformed
    // state, then executes an out-of-place reverse computation and reports its
    // joint hidden/ancilla residual. Factors are direct external graph leaves.
    // Active and staging each retain full capacity; after commit, staging is
    // measured zero so no second complete nonzero payload remains.
    std::shared_ptr<void> lifting_backing;
    std::vector<int32_t> lifting_layers;
    ggml_tensor * lifting_f_key_active = nullptr;
    ggml_tensor * lifting_f_key_staging = nullptr;
    ggml_tensor * lifting_f_value_active = nullptr;
    ggml_tensor * lifting_f_value_staging = nullptr;
    ggml_tensor * lifting_g_key_active = nullptr;
    ggml_tensor * lifting_g_key_staging = nullptr;
    ggml_tensor * lifting_g_value_active = nullptr;
    ggml_tensor * lifting_g_value_staging = nullptr;
    std::vector<ggml_tensor *> lifting_f_key_active_layers;
    std::vector<ggml_tensor *> lifting_f_value_active_layers;
    std::vector<ggml_tensor *> lifting_g_key_active_layers;
    std::vector<ggml_tensor *> lifting_g_value_active_layers;
    std::vector<ggml_tensor *> lifting_f_key_staging_slots;
    std::vector<ggml_tensor *> lifting_f_value_staging_slots;
    std::vector<ggml_tensor *> lifting_g_key_staging_slots;
    std::vector<ggml_tensor *> lifting_g_value_staging_slots;
    int32_t lifting_capture_kind = 0; // 0:none, 1:F-key, 2:F-value, 3:G-key, 4:G-value
    int32_t lifting_capture_slot = -1;
    uint32_t lifting_f_key_mask = 0;
    uint32_t lifting_f_value_mask = 0;
    uint32_t lifting_g_key_mask = 0;
    uint32_t lifting_g_value_mask = 0;
    bool source_conditioned_lifting = false;
    bool lifting_update_resident = false;
    bool lifting_poisoned = false;
    uint32_t phase = 0;
    bool enabled = false;
    bool output_written = false;
    bool output_hidden_slots = false;
    bool output_phase_memory = false;
    bool native_phase_orbit = false;
    bool phase_poisoned = false;
    bool continuous_soft_role_memory = false;
    bool soft_role_poisoned = false;
    bool output_depth_memory = false;
    bool depth_memory_poisoned = false;
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
    uint64_t soft_role_backend_bytes = 0;
    uint64_t soft_role_candidate_id_upload_bytes = 0;
    uint64_t soft_role_gate_upload_bytes = 0;
    uint64_t soft_role_capture_device_copy_bytes = 0;
    uint64_t soft_role_commit_device_copy_bytes = 0;
    uint64_t soft_role_read_device_copy_bytes = 0;
    uint64_t soft_role_projection_token_applications = 0;
    uint64_t soft_role_projection_multiply_accumulates = 0;
    uint64_t soft_role_mixture_multiply_accumulates = 0;
    uint64_t soft_role_captures = 0;
    uint64_t soft_role_commits = 0;
    uint64_t soft_role_reads = 0;
    uint64_t depth_memory_backend_bytes = 0;
    uint64_t depth_capture_device_copy_bytes = 0;
    uint64_t depth_commit_device_copy_bytes = 0;
    uint64_t depth_read_device_copy_bytes = 0;
    uint64_t depth_cross_attention_multiply_accumulates = 0;
    uint64_t depth_captures = 0;
    uint64_t depth_commits = 0;
    uint64_t depth_reads = 0;
    uint64_t lifting_backend_bytes = 0;
    uint64_t lifting_capture_device_copy_bytes = 0;
    uint64_t lifting_commit_device_copy_bytes = 0;
    uint64_t lifting_closure_device_zero_bytes = 0;
    uint64_t lifting_token_applications = 0;
    uint64_t lifting_multiply_accumulates = 0;
    uint64_t lifting_captures = 0;
    uint64_t lifting_commits = 0;
    uint64_t lifting_reads = 0;
    double lifting_reverse_branch_residual_sum = 0.0;
    double lifting_reverse_branch_residual_max = 0.0;
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
    // 0 off, 1 F->G, 2 F only, 3 G only, 4 G->F, 5 F->cyclic-G.
    uint32_t neo3000_lifting_control = 0;
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
