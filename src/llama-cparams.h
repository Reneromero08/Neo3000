#pragma once

#include "llama.h"

#include <array>
#include <cstdint>
#include <memory>
#include <vector>

#define LLAMA_MAX_SEQ 256

// Experimental fixed-capacity semantic carrier used only by the Neo3000
// frontier probe. The query/output maps are immutable after installation.
// The 4x4 carrier action is updated in place on the same host backing and
// supplied to the model graph as a live input.
struct llama_neo3000_semantic_carrier {
    uint32_t n_embd = 0;
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
    uint32_t phase = 0;
    bool enabled = false;
    bool output_written = false;
    uint64_t generation = 0;
    uint64_t action_backing_id = 0;
    uint64_t graph_input_sets = 0;
    uint64_t host_to_backend_bytes = 0;
    uint64_t writer_host_input_bytes = 0;
    uint64_t port_writes = 0;
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
