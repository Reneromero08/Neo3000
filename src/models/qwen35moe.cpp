#include "models.h"
#include "llama-memory-recurrent.h"

#include <algorithm>

class llm_graph_input_neo3000_soft_role
        : public llm_graph_input_i {
public:
    explicit llm_graph_input_neo3000_soft_role(
            std::shared_ptr<llama_neo3000_semantic_carrier> carrier)
        : carrier(std::move(carrier)) {
    }

    void set_input(const llama_ubatch * ubatch) override {
        GGML_ASSERT(
            carrier &&
            carrier->continuous_soft_role_memory &&
            soft_embedding &&
            soft_gate &&
            candidate_tokens);
        GGML_ASSERT(ubatch);

        ggml_backend_tensor_set(
            candidate_tokens,
            carrier->soft_role_candidate_tokens.data(),
            0,
            carrier->soft_role_candidate_tokens.size() *
                sizeof(llama_token));
        carrier->soft_role_candidate_id_upload_bytes +=
            carrier->soft_role_candidate_tokens.size() *
            sizeof(llama_token);

        const bool read_enabled =
            !carrier->soft_role_poisoned &&
            carrier->soft_role_read_slot >= 0 &&
            carrier->soft_role_read_slot < 4;
        const float gate = read_enabled ? 1.0f : 0.0f;
        ggml_backend_tensor_set(
            soft_gate,
            &gate,
            0,
            sizeof(gate));
        carrier->soft_role_gate_upload_bytes += sizeof(gate);

        if (read_enabled) {
            ggml_tensor * source =
                carrier->soft_role_active_slots.at(
                    static_cast<size_t>(
                        carrier->soft_role_read_slot));
            GGML_ASSERT(
                source &&
                carrier->soft_role_backing &&
                ggml_nbytes(source) ==
                    static_cast<size_t>(carrier->n_embd) *
                        sizeof(float));
            ggml_backend_tensor_copy(source, soft_embedding);
            carrier->soft_role_read_device_copy_bytes +=
                ggml_nbytes(source);
            ++carrier->soft_role_reads;
        }

        carrier->soft_role_projection_token_applications +=
            ubatch->n_tokens;
        carrier->soft_role_projection_multiply_accumulates +=
            static_cast<uint64_t>(carrier->n_embd) * 4 *
            ubatch->n_tokens;
        carrier->soft_role_mixture_multiply_accumulates +=
            static_cast<uint64_t>(carrier->n_embd) * 4 *
            ubatch->n_tokens;
    }

    bool can_reuse(const llm_graph_params & params) override {
        const auto & candidate =
            params.cparams.neo3000_semantic_carrier;
        return candidate.get() == carrier.get() &&
            candidate->continuous_soft_role_memory &&
            soft_embedding &&
            soft_embedding->ne[0] == carrier->n_embd &&
            soft_gate &&
            soft_gate->ne[0] == 1 &&
            candidate_tokens &&
            candidate_tokens->ne[0] == 4;
    }

    std::shared_ptr<llama_neo3000_semantic_carrier> carrier;
    ggml_tensor * soft_embedding = nullptr;
    ggml_tensor * soft_gate = nullptr;
    ggml_tensor * candidate_tokens = nullptr;
};

class llm_graph_input_neo3000_depth_memory
        : public llm_graph_input_i {
public:
    explicit llm_graph_input_neo3000_depth_memory(
            std::shared_ptr<llama_neo3000_semantic_carrier> carrier)
        : carrier(std::move(carrier)) {
    }

    void set_input(const llama_ubatch * ubatch) override {
        GGML_ASSERT(
            carrier &&
            carrier->output_depth_memory &&
            carrier->depth_zero_layer &&
            carrier->depth_active_layers.size() ==
                carrier->depth_layers.size() &&
            layer_memory.size() ==
                carrier->depth_layers.size());
        GGML_ASSERT(ubatch);
        const bool read_enabled =
            carrier->enabled &&
            !carrier->depth_memory_poisoned &&
            carrier->depth_commits > 0;
        const size_t n_layers = layer_memory.size();
        for (size_t layer_index = 0;
             layer_index < n_layers;
             ++layer_index) {
            const size_t source_index =
                (layer_index +
                 carrier->depth_layer_offset) %
                n_layers;
            ggml_tensor * source =
                read_enabled
                    ? carrier->depth_active_layers.at(
                        source_index)
                    : carrier->depth_zero_layer;
            GGML_ASSERT(
                source &&
                layer_memory.at(layer_index) &&
                ggml_nbytes(source) ==
                    ggml_nbytes(
                        layer_memory.at(layer_index)));
            ggml_backend_tensor_copy(
                source,
                layer_memory.at(layer_index));
            carrier->depth_read_device_copy_bytes +=
                ggml_nbytes(source);
        }
        if (read_enabled) {
            carrier->depth_reads += n_layers;
        }
        const uint64_t memory_tokens = 4;
        const uint64_t n_embd = carrier->n_embd;
        const uint64_t kv_width =
            carrier->depth_projected_kv_width;
        const uint64_t query_tokens = ubatch->n_tokens;
        carrier->depth_cross_attention_multiply_accumulates +=
            n_layers *
            (2 * n_embd * kv_width * memory_tokens +
             2 * n_embd * memory_tokens * query_tokens);
        ++carrier->graph_input_sets;
    }

    bool can_reuse(const llm_graph_params & params) override {
        const auto & candidate =
            params.cparams.neo3000_semantic_carrier;
        if (candidate.get() != carrier.get() ||
            !candidate->output_depth_memory ||
            layer_memory.size() !=
                carrier->depth_layers.size()) {
            return false;
        }
        return std::all_of(
            layer_memory.begin(),
            layer_memory.end(),
            [&](const ggml_tensor * tensor) {
                return tensor &&
                    tensor->ne[0] == carrier->n_embd &&
                    tensor->ne[1] == 4;
            });
    }

    std::shared_ptr<llama_neo3000_semantic_carrier> carrier;
    std::vector<ggml_tensor *> layer_memory;
};

class llm_graph_input_neo3000_semantic_carrier
        : public llm_graph_input_i {
public:
    explicit llm_graph_input_neo3000_semantic_carrier(
            std::shared_ptr<llama_neo3000_semantic_carrier> carrier)
        : carrier(std::move(carrier)),
          output_map_trainable(
              this->carrier->output_map_trainable) {
    }

    void set_input(const llama_ubatch * ubatch) override {
        GGML_ASSERT(carrier);
        GGML_ASSERT(
            query_map &&
            query_bias);
        ggml_backend_tensor_set(
            query_map,
            carrier->query_map.data(),
            0,
            carrier->query_map.size() * sizeof(float));
        ggml_backend_tensor_set(
            query_bias,
            carrier->query_bias.data(),
            0,
            carrier->query_bias.size() * sizeof(float));
        if (carrier->output_phase_memory) {
            GGML_ASSERT(
                output_map &&
                action &&
                phase_memory &&
                phase_reader &&
                carrier->phase_active &&
                carrier->phase_memory_backing);
            ggml_backend_tensor_set(
                output_map,
                carrier->output_map.data(),
                0,
                carrier->output_map.size() * sizeof(float));
            ggml_backend_tensor_set(
                action,
                carrier->action.data(),
                0,
                carrier->action.size() * sizeof(float));
            ggml_backend_tensor_copy(
                carrier->phase_active,
                phase_memory);
            ggml_backend_tensor_set(
                phase_reader,
                carrier->phase_reader.data(),
                0,
                carrier->phase_reader.size() * sizeof(float));
            carrier->backend_to_graph_bytes +=
                ggml_nbytes(carrier->phase_active);
        } else if (carrier->output_hidden_slots) {
            GGML_ASSERT(
                hidden_slots &&
                action &&
                carrier->hidden_slots &&
                carrier->hidden_slot_backing);
            ggml_backend_tensor_copy(
                carrier->hidden_slots,
                hidden_slots);
            carrier->backend_to_graph_bytes +=
                ggml_nbytes(carrier->hidden_slots);
            ggml_backend_tensor_set(
                action,
                carrier->action.data(),
                0,
                carrier->action.size() * sizeof(float));
        } else {
            GGML_ASSERT(output_map && action);
            ggml_backend_tensor_set(
                output_map,
                carrier->output_map.data(),
                0,
                carrier->output_map.size() * sizeof(float));
            const float * action_data =
                carrier->output_written &&
                    !carrier->output_phase_memory &&
                    carrier->enabled
                    ? carrier->port.data()
                    : carrier->action.data();
            ggml_backend_tensor_set(
                action,
                action_data,
                0,
                carrier->action.size() * sizeof(float));
        }
        ++carrier->graph_input_sets;
        carrier->host_to_backend_bytes +=
            (carrier->query_map.size() +
             carrier->query_bias.size() +
             (carrier->output_phase_memory
                ? carrier->output_map.size() +
                    carrier->action.size() +
                    carrier->phase_reader.size()
              : carrier->output_hidden_slots
                ? carrier->action.size()
                : carrier->output_map.size() +
                    carrier->action.size())) *
            sizeof(float);
        if (carrier->moe_router_bias) {
            GGML_ASSERT(ubatch);
            carrier->router_bias_token_applications +=
                ubatch->n_tokens;
            if (carrier->enabled) {
                carrier->router_bias_enabled_token_applications +=
                    ubatch->n_tokens;
            }
            carrier->router_bias_multiply_accumulates +=
                static_cast<uint64_t>(carrier->n_embd) *
                carrier->n_expert *
                ubatch->n_tokens;
        }
        if (carrier->recurrent_transition_input) {
            GGML_ASSERT(ubatch);
            carrier->recurrent_transition_token_applications +=
                ubatch->n_tokens;
            if (carrier->enabled) {
                carrier
                    ->recurrent_transition_enabled_token_applications +=
                    ubatch->n_tokens;
            }
        }
        carrier->carrier_map_multiply_accumulates +=
            (static_cast<uint64_t>(carrier->n_embd) * 8 +
             16 +
             (carrier->output_phase_memory
                ? static_cast<uint64_t>(
                    carrier->phase_width) * 2 * 16 + 16
                : 0)) *
            ubatch->n_tokens;
    }

    bool can_reuse(const llm_graph_params & params) override {
        const auto & candidate =
            params.cparams.neo3000_semantic_carrier;
        return candidate.get() == carrier.get() &&
            candidate->output_map_trainable ==
                output_map_trainable &&
            candidate->output_hidden_slots ==
                carrier->output_hidden_slots &&
            candidate->output_phase_memory ==
                carrier->output_phase_memory &&
            query_map &&
            query_map->ne[0] == carrier->n_embd &&
            query_map->ne[1] == 4 &&
            (carrier->output_phase_memory
                ? output_map &&
                    action &&
                    phase_memory &&
                    phase_reader &&
                    output_map->ne[0] == 4 &&
                    output_map->ne[1] == carrier->n_embd &&
                    action->ne[0] == 4 &&
                    action->ne[1] == 4 &&
                    phase_memory->ne[0] ==
                        static_cast<int64_t>(
                            carrier->phase_width) * 2 &&
                    phase_reader->ne[0] ==
                        static_cast<int64_t>(
                            carrier->phase_width) * 2 &&
                    phase_reader->ne[1] == 16
              : carrier->output_hidden_slots
                ? hidden_slots &&
                    action &&
                    hidden_slots->ne[0] == carrier->n_embd &&
                    hidden_slots->ne[1] == 4 &&
                    action->ne[0] == 4 &&
                    action->ne[1] == 4
                : output_map &&
                    output_map->ne[0] == 4 &&
                    output_map->ne[1] == carrier->n_embd);
    }

    std::shared_ptr<llama_neo3000_semantic_carrier> carrier;
    bool output_map_trainable = false;
    ggml_tensor * query_map = nullptr;
    ggml_tensor * query_bias = nullptr;
    ggml_tensor * output_map = nullptr;
    ggml_tensor * action = nullptr;
    ggml_tensor * hidden_slots = nullptr;
    ggml_tensor * phase_memory = nullptr;
    ggml_tensor * phase_reader = nullptr;
};

void llama_model_qwen35moe::load_arch_hparams(llama_model_loader & ml) {
    ml.get_key(LLM_KV_EXPERT_FEED_FORWARD_LENGTH,        hparams.n_ff_exp, false);
    ml.get_key(LLM_KV_EXPERT_SHARED_FEED_FORWARD_LENGTH, hparams.n_ff_shexp, false);
    ml.get_key(LLM_KV_ATTENTION_LAYERNORM_RMS_EPS,       hparams.f_norm_rms_eps);

    ml.get_key_or_arr(LLM_KV_ROPE_DIMENSION_SECTIONS,    hparams.rope_sections, 4, true);

    // Load linear attention (gated delta net) parameters
    ml.get_key(LLM_KV_SSM_CONV_KERNEL,    hparams.ssm_d_conv);
    ml.get_key(LLM_KV_SSM_INNER_SIZE,     hparams.ssm_d_inner);
    ml.get_key(LLM_KV_SSM_STATE_SIZE,     hparams.ssm_d_state);
    ml.get_key(LLM_KV_SSM_TIME_STEP_RANK, hparams.ssm_dt_rank);
    ml.get_key(LLM_KV_SSM_GROUP_COUNT,    hparams.ssm_n_group);

    // NextN/MTP (Qwen3.5/3.6): extra decoder block appended beyond the main stack
    ml.get_key(LLM_KV_NEXTN_PREDICT_LAYERS, hparams.n_layer_nextn, false);
    GGML_ASSERT(hparams.n_layer_nextn < hparams.n_layer_all && "n_layer_nextn must be < n_layer_impl");

    // Mark recurrent layers (linear attention layers). MTP layers are dense
    // attention-only and must be flagged non-recurrent.
    if (!ml.get_key_or_arr(LLM_KV_ATTENTION_RECURRENT_LAYERS, hparams.is_recr_impl, hparams.n_layer_all, false)) {
        uint32_t full_attn_interval = 4;
        ml.get_key(LLM_KV_FULL_ATTENTION_INTERVAL, full_attn_interval, false);
        for (uint32_t i = 0; i < hparams.n_layer_all; ++i) {
            hparams.is_recr_impl[i] = (i < hparams.n_layer()) && ((i + 1) % full_attn_interval != 0);
        }
    }

    switch (hparams.n_layer()) {
        case 40: type = LLM_TYPE_35B_A3B; break;
        case 48: type = LLM_TYPE_122B_A10B; break;
        case 60: type = LLM_TYPE_397B_A17B; break;
        default: type = LLM_TYPE_UNKNOWN;
    }
}

void llama_model_qwen35moe::load_arch_tensors(llama_model_loader & ml) {
    LLAMA_LOAD_LOCALS;

    const bool mtp_only = (hparams.n_layer_nextn > 0) && (ml.get_weight("blk.0.attn_norm.weight") == nullptr);
    const int trunk_flags = mtp_only ? TENSOR_NOT_REQUIRED : 0;

    tok_embd = create_tensor(tn(LLM_TENSOR_TOKEN_EMBD, "weight"), { n_embd, n_vocab }, 0);

    // output
    output_norm = create_tensor(tn(LLM_TENSOR_OUTPUT_NORM, "weight"), { n_embd }, 0);
    output = create_tensor(tn(LLM_TENSOR_OUTPUT, "weight"), { n_embd, n_vocab }, TENSOR_NOT_REQUIRED);

    // if output is NULL, init from the input tok embed
    if (output == NULL) {
        output = create_tensor(tn(LLM_TENSOR_TOKEN_EMBD, "weight"), { n_embd, n_vocab }, TENSOR_DUPLICATED);
    }

    auto load_block_trunk = [&](int il, int flags) {
        auto & layer = layers[il];

        const int64_t n_ff_exp   = hparams.n_ff_exp ? hparams.n_ff_exp : n_ff / n_expert_used;
        const int64_t n_ff_shexp = hparams.n_ff_shexp ? hparams.n_ff_shexp : n_ff;

        // Calculate dimensions from hyperparameters
        const int64_t head_k_dim = hparams.ssm_d_state;
        const int64_t head_v_dim = hparams.ssm_d_state;
        const int64_t n_k_heads  = hparams.ssm_n_group;
        const int64_t n_v_heads  = hparams.ssm_dt_rank;
        const int64_t key_dim    = head_k_dim * n_k_heads;
        const int64_t value_dim  = head_v_dim * n_v_heads;
        const int64_t conv_dim   = key_dim * 2 + value_dim;

        layer.attn_norm      = create_tensor(tn(LLM_TENSOR_ATTN_NORM,      "weight", il), { n_embd }, flags);
        layer.attn_post_norm = create_tensor(tn(LLM_TENSOR_ATTN_POST_NORM, "weight", il), { n_embd }, flags);

        if (!hparams.is_recr(il)) {
            // Attention layers
            create_tensor_qkv(layer, il, n_embd, n_embd_head_k * n_head * 2, n_embd_k_gqa, n_embd_v_gqa, flags);
            layer.wo = create_tensor(tn(LLM_TENSOR_ATTN_OUT, "weight", il), { n_embd_head_k * n_head, n_embd }, flags);

            // Q/K normalization for attention layers
            layer.attn_q_norm = create_tensor(tn(LLM_TENSOR_ATTN_Q_NORM, "weight", il), { n_embd_head_k }, flags);
            layer.attn_k_norm = create_tensor(tn(LLM_TENSOR_ATTN_K_NORM, "weight", il), { n_embd_head_k }, flags);
        } else {
            // Linear attention (gated delta net) specific tensors
            // Create tensors with calculated dimensions
            layer.wqkv           = create_tensor(tn(LLM_TENSOR_ATTN_QKV,       "weight", il), { n_embd, key_dim * 2 + value_dim }, TENSOR_NOT_REQUIRED);
            layer.wqkv_gate      = create_tensor(tn(LLM_TENSOR_ATTN_GATE,      "weight", il), { n_embd, value_dim }, TENSOR_NOT_REQUIRED);
            layer.ssm_conv1d     = create_tensor(tn(LLM_TENSOR_SSM_CONV1D,     "weight", il), { hparams.ssm_d_conv, conv_dim }, flags);
            layer.ssm_dt         = create_tensor(tn(LLM_TENSOR_SSM_DT,         "bias",   il), { hparams.ssm_dt_rank }, flags);
            layer.ssm_a          = create_tensor(tn(LLM_TENSOR_SSM_A_NOSCAN,             il), { hparams.ssm_dt_rank }, flags);
            layer.ssm_beta       = create_tensor(tn(LLM_TENSOR_SSM_BETA,       "weight", il), { n_embd, n_v_heads }, flags);
            layer.ssm_alpha      = create_tensor(tn(LLM_TENSOR_SSM_ALPHA,      "weight", il), { n_embd, n_v_heads }, flags);
            layer.ssm_norm       = create_tensor(tn(LLM_TENSOR_SSM_NORM,       "weight", il), { head_v_dim }, flags);
            layer.ssm_out        = create_tensor(tn(LLM_TENSOR_SSM_OUT,        "weight", il), { value_dim, n_embd }, flags);
        }

        // Routed experts
        layer.ffn_gate_inp  = create_tensor(tn(LLM_TENSOR_FFN_GATE_INP,  "weight", il), { n_embd, n_expert }, flags);
        layer.ffn_down_exps = create_tensor(tn(LLM_TENSOR_FFN_DOWN_EXPS, "weight", il), { n_ff_exp, n_embd, n_expert }, flags);
        create_tensor_gate_up_exps(layer, il, n_embd, n_ff_exp, n_expert, flags);

        // Shared experts
        layer.ffn_gate_inp_shexp = create_tensor(tn(LLM_TENSOR_FFN_GATE_INP_SHEXP, "weight", il), { n_embd }, flags);
        layer.ffn_gate_shexp     = create_tensor(tn(LLM_TENSOR_FFN_GATE_SHEXP,     "weight", il), { n_embd, n_ff_shexp }, flags);
        layer.ffn_up_shexp       = create_tensor(tn(LLM_TENSOR_FFN_UP_SHEXP,       "weight", il), { n_embd, n_ff_shexp }, flags);
        layer.ffn_down_shexp     = create_tensor(tn(LLM_TENSOR_FFN_DOWN_SHEXP,     "weight", il), { n_ff_shexp, n_embd }, flags);
    };

    auto load_block_mtp = [&](int il) {
        auto & layer = layers[il];

        const int64_t n_ff_exp   = hparams.n_ff_exp ? hparams.n_ff_exp : n_ff / n_expert_used;
        const int64_t n_ff_shexp = hparams.n_ff_shexp ? hparams.n_ff_shexp : n_ff;

        // MTP block looks like a full-attention Qwen3.5 decoder block with MoE FFN.
        layer.attn_norm      = create_tensor(tn(LLM_TENSOR_ATTN_NORM,      "weight", il), { n_embd }, 0);
        layer.attn_post_norm = create_tensor(tn(LLM_TENSOR_ATTN_POST_NORM, "weight", il), { n_embd }, 0);

        create_tensor_qkv(layer, il, n_embd, n_embd_head_k * n_head * 2, n_embd_k_gqa, n_embd_v_gqa, 0);
        layer.wo          = create_tensor(tn(LLM_TENSOR_ATTN_OUT,    "weight", il), { n_embd_head_k * n_head, n_embd }, 0);
        layer.attn_q_norm = create_tensor(tn(LLM_TENSOR_ATTN_Q_NORM, "weight", il), { n_embd_head_k }, 0);
        layer.attn_k_norm = create_tensor(tn(LLM_TENSOR_ATTN_K_NORM, "weight", il), { n_embd_head_k }, 0);

        // Routed experts
        layer.ffn_gate_inp  = create_tensor(tn(LLM_TENSOR_FFN_GATE_INP,  "weight", il), { n_embd, n_expert }, 0);
        layer.ffn_down_exps = create_tensor(tn(LLM_TENSOR_FFN_DOWN_EXPS, "weight", il), { n_ff_exp, n_embd, n_expert }, 0);
        create_tensor_gate_up_exps(layer, il, n_embd, n_ff_exp, n_expert, 0);

        // Shared experts
        layer.ffn_gate_inp_shexp = create_tensor(tn(LLM_TENSOR_FFN_GATE_INP_SHEXP, "weight", il), { n_embd }, 0);
        layer.ffn_gate_shexp     = create_tensor(tn(LLM_TENSOR_FFN_GATE_SHEXP,     "weight", il), { n_embd, n_ff_shexp }, 0);
        layer.ffn_up_shexp       = create_tensor(tn(LLM_TENSOR_FFN_UP_SHEXP,       "weight", il), { n_embd, n_ff_shexp }, 0);
        layer.ffn_down_shexp     = create_tensor(tn(LLM_TENSOR_FFN_DOWN_SHEXP,     "weight", il), { n_ff_shexp, n_embd }, 0);

        // NextN-specific tensors that define the MTP block.
        layer.nextn.eh_proj          = create_tensor(tn(LLM_TENSOR_NEXTN_EH_PROJ,          "weight", il), { 2 * n_embd, n_embd }, 0);
        layer.nextn.enorm            = create_tensor(tn(LLM_TENSOR_NEXTN_ENORM,            "weight", il), { n_embd },              0);
        layer.nextn.hnorm            = create_tensor(tn(LLM_TENSOR_NEXTN_HNORM,            "weight", il), { n_embd },              0);
        layer.nextn.embed_tokens     = create_tensor(tn(LLM_TENSOR_NEXTN_EMBED_TOKENS,     "weight", il), { n_embd, n_vocab },     TENSOR_NOT_REQUIRED);
        layer.nextn.shared_head_head = create_tensor(tn(LLM_TENSOR_NEXTN_SHARED_HEAD_HEAD, "weight", il), { n_embd, n_vocab },     TENSOR_NOT_REQUIRED);
        layer.nextn.shared_head_norm = create_tensor(tn(LLM_TENSOR_NEXTN_SHARED_HEAD_NORM, "weight", il), { n_embd },              TENSOR_NOT_REQUIRED);
    };

    for (int i = 0; i < n_layer; ++i) {
        load_block_trunk(i, trunk_flags);
    }
    for (int i = n_layer; i < n_layer_all; ++i) {
        load_block_mtp(i);
    }
}

std::unique_ptr<llm_graph_context> llama_model_qwen35moe::build_arch_graph(const llm_graph_params & params) const {
    if (params.gtype == LLM_GRAPH_TYPE_DECODER_MTP) {
        return std::make_unique<graph_mtp>(*this, params);
    }
    return std::make_unique<graph>(*this, params);
}

llama_model_qwen35moe::graph::graph(const llama_model & model, const llm_graph_params & params) :
    llm_build_delta_net_base(params), model(model) {
    const int64_t n_embd_head = hparams.n_embd_head_v();

    GGML_ASSERT(n_embd_head == hparams.n_embd_head_k());

    int sections[4];
    std::copy(std::begin(hparams.rope_sections), std::begin(hparams.rope_sections) + 4, sections);

    ggml_tensor * cur;
    ggml_tensor * inpL;

    inpL = build_inp_embd(model.tok_embd);

    llm_graph_input_neo3000_soft_role * soft_role_input = nullptr;
    const auto & soft_role_state =
        cparams.neo3000_semantic_carrier;
    if (soft_role_state &&
        soft_role_state->continuous_soft_role_memory) {
        auto input =
            std::make_unique<
                llm_graph_input_neo3000_soft_role>(
                    soft_role_state);
        input->soft_embedding = ggml_new_tensor_1d(
            ctx0,
            GGML_TYPE_F32,
            n_embd);
        input->soft_gate = ggml_new_tensor_1d(
            ctx0,
            GGML_TYPE_F32,
            1);
        input->candidate_tokens = ggml_new_tensor_1d(
            ctx0,
            GGML_TYPE_I32,
            4);
        ggml_set_input(input->soft_embedding);
        ggml_set_input(input->soft_gate);
        ggml_set_input(input->candidate_tokens);
        ggml_set_name(
            input->soft_embedding,
            "neo3000_soft_role_active_slot");
        ggml_set_name(
            input->soft_gate,
            "neo3000_soft_role_read_gate");
        ggml_set_name(
            input->candidate_tokens,
            "neo3000_soft_role_candidate_tokens");
        soft_role_input = static_cast<
            llm_graph_input_neo3000_soft_role *>(
                res->add_input(std::move(input)));
        ggml_tensor * repeated_soft = ggml_repeat(
            ctx0,
            soft_role_input->soft_embedding,
            inpL);
        ggml_tensor * repeated_gate = ggml_repeat(
            ctx0,
            soft_role_input->soft_gate,
            inpL);
        inpL = ggml_add(
            ctx0,
            inpL,
            ggml_mul(
                ctx0,
                repeated_gate,
                ggml_sub(
                    ctx0,
                    repeated_soft,
                    inpL)));
        cb(inpL, "neo3000_soft_role_input_override", -1);
    }

    llm_graph_input_neo3000_depth_memory *
        depth_memory_input = nullptr;
    const auto & depth_memory_state =
        cparams.neo3000_semantic_carrier;
    if (depth_memory_state &&
        depth_memory_state->output_depth_memory) {
        auto input =
            std::make_unique<
                llm_graph_input_neo3000_depth_memory>(
                    depth_memory_state);
        input->layer_memory.reserve(
            depth_memory_state->depth_layers.size());
        for (size_t layer_index = 0;
             layer_index <
                depth_memory_state->depth_layers.size();
             ++layer_index) {
            ggml_tensor * layer_memory =
                ggml_new_tensor_2d(
                    ctx0,
                    GGML_TYPE_F32,
                    n_embd,
                    4);
            ggml_set_input(layer_memory);
            ggml_set_name(
                layer_memory,
                "neo3000_depth_memory_layer_panel");
            input->layer_memory.push_back(
                layer_memory);
        }
        depth_memory_input = static_cast<
            llm_graph_input_neo3000_depth_memory *>(
                res->add_input(std::move(input)));
    }

    cb(inpL, "model.input_embed", -1);

    auto * inp = build_inp_mem_hybrid();

    ggml_tensor * inp_pos     = build_inp_pos();
    ggml_tensor * inp_out_ids = build_inp_out_ids();

    const auto apply_semantic_carrier =
            [&](ggml_tensor * hidden, int32_t read_layer) {
        const auto & state = cparams.neo3000_semantic_carrier;
        if (!state || state->read_layer != read_layer) {
            return std::make_pair(
                hidden,
                static_cast<ggml_tensor *>(nullptr));
        }
        auto carrier_input =
            std::make_unique<
                llm_graph_input_neo3000_semantic_carrier>(state);
        carrier_input->query_map =
            ggml_new_tensor_2d(
                ctx0,
                GGML_TYPE_F32,
                n_embd,
                4);
        carrier_input->query_bias =
            ggml_new_tensor_1d(
                ctx0,
                GGML_TYPE_F32,
                4);
        ggml_set_input(carrier_input->query_map);
        ggml_set_input(carrier_input->query_bias);
        if (state->output_phase_memory) {
            carrier_input->output_map =
                ggml_new_tensor_2d(
                    ctx0,
                    GGML_TYPE_F32,
                    4,
                    n_embd);
            carrier_input->action =
                ggml_new_tensor_2d(
                    ctx0,
                    GGML_TYPE_F32,
                    4,
                    4);
            carrier_input->phase_memory =
                ggml_new_tensor_1d(
                    ctx0,
                    GGML_TYPE_F32,
                    static_cast<int64_t>(
                        state->phase_width) * 2);
            carrier_input->phase_reader =
                ggml_new_tensor_2d(
                    ctx0,
                    GGML_TYPE_F32,
                    static_cast<int64_t>(
                        state->phase_width) * 2,
                    16);
            ggml_set_input(carrier_input->output_map);
            ggml_set_input(carrier_input->action);
            ggml_set_input(carrier_input->phase_memory);
            ggml_set_input(carrier_input->phase_reader);
            ggml_set_name(
                carrier_input->output_map,
                "neo3000_phase_memory_output_map");
            ggml_set_name(
                carrier_input->action,
                "neo3000_phase_memory_query_gate");
            ggml_set_name(
                carrier_input->phase_memory,
                "neo3000_phase_memory_active");
            ggml_set_name(
                carrier_input->phase_reader,
                "neo3000_phase_memory_reader");
        } else if (state->output_hidden_slots) {
            carrier_input->hidden_slots =
                ggml_new_tensor_2d(
                    ctx0,
                    GGML_TYPE_F32,
                    n_embd,
                    4);
            carrier_input->action =
                ggml_new_tensor_2d(
                    ctx0,
                    GGML_TYPE_F32,
                    4,
                    4);
            ggml_set_input(carrier_input->hidden_slots);
            ggml_set_input(carrier_input->action);
            ggml_set_name(
                carrier_input->hidden_slots,
                "neo3000_carrier_hidden_slots");
            ggml_set_name(
                carrier_input->action,
                "neo3000_carrier_hidden_slot_gate");
        } else {
            carrier_input->output_map =
                ggml_new_tensor_2d(
                    ctx0,
                    GGML_TYPE_F32,
                    4,
                    n_embd);
            carrier_input->action =
                ggml_new_tensor_2d(
                    ctx0,
                    GGML_TYPE_F32,
                    4,
                    4);
            if (state->output_map_trainable) {
                ggml_set_param(carrier_input->output_map);
            } else {
                ggml_set_input(carrier_input->output_map);
            }
            ggml_set_input(carrier_input->action);
            ggml_set_name(
                carrier_input->output_map,
                "neo3000_carrier_output_map");
            ggml_set_name(
                carrier_input->action,
                "neo3000_carrier_action");
        }
        ggml_set_name(
            carrier_input->query_map,
            "neo3000_carrier_query_map");
        ggml_set_name(
            carrier_input->query_bias,
            "neo3000_carrier_query_bias");
        auto * carrier = static_cast<
            llm_graph_input_neo3000_semantic_carrier *>(
                res->add_input(std::move(carrier_input)));
        ggml_tensor * carrier_code =
            ggml_mul_mat(ctx0, carrier->query_map, hidden);
        carrier_code =
            ggml_add(
                ctx0,
                carrier_code,
                carrier->query_bias);
        ggml_tensor * carrier_delta = nullptr;
        if (state->output_phase_memory) {
            carrier_code =
                ggml_mul_mat(
                    ctx0,
                    carrier->action,
                    carrier_code);
            ggml_tensor * relation =
                ggml_mul_mat(
                    ctx0,
                    carrier->phase_reader,
                    carrier->phase_memory);
            relation = ggml_reshape_2d(
                ctx0,
                relation,
                4,
                4);
            carrier_code =
                ggml_mul_mat(
                    ctx0,
                    relation,
                    carrier_code);
            carrier_delta =
                ggml_mul_mat(
                    ctx0,
                    carrier->output_map,
                    carrier_code);
        } else if (state->output_hidden_slots) {
            carrier_code =
                ggml_mul_mat(
                    ctx0,
                    carrier->action,
                    carrier_code);
            // The resident tensor is slot-major so that one complete actual
            // output state can be written into one contiguous column. GGML's
            // left matrix convention requires the slot axis to be ne[0].
            // Materialize only this bounded graph-local transpose; the
            // persistent carrier remains the same four CUDA-resident slots.
            ggml_tensor * hidden_slot_reader =
                ggml_cont(
                    ctx0,
                    ggml_transpose(
                        ctx0,
                        carrier->hidden_slots));
            carrier_delta =
                ggml_mul_mat(
                    ctx0,
                    hidden_slot_reader,
                    carrier_code);
        } else {
            carrier_code =
                ggml_mul_mat(
                    ctx0,
                    carrier->action,
                    carrier_code);
            carrier_delta =
                ggml_mul_mat(
                    ctx0,
                    carrier->output_map,
                    carrier_code);
        }
        if (state->moe_router_bias ||
            state->recurrent_transition_input) {
            cb(
                carrier_delta,
                state->moe_router_bias
                    ? "neo3000_semantic_carrier_router_delta"
                    : "neo3000_semantic_carrier_recurrent_delta",
                read_layer);
            return std::make_pair(hidden, carrier_delta);
        }
        hidden = ggml_add(ctx0, hidden, carrier_delta);
        cb(hidden, "neo3000_semantic_carrier_read", read_layer);
        return std::make_pair(
            hidden,
            static_cast<ggml_tensor *>(nullptr));
    };

    size_t depth_memory_layer_index = 0;
    size_t lifting_layer_index = 0;
    ggml_tensor * lifting_reverse_branch_residual = nullptr;

    struct lifting_step {
        ggml_tensor * key = nullptr;
        ggml_tensor * coefficients = nullptr;
        ggml_tensor * delta = nullptr;
    };
    const auto lifting_coefficients =
            [&](ggml_tensor * key, ggml_tensor * hidden) {
        GGML_ASSERT(
            key &&
            hidden &&
            key->ne[0] == n_embd &&
            key->ne[1] == 4 &&
            hidden->ne[0] == n_embd);
        ggml_tensor * coefficients =
            ggml_mul_mat(ctx0, key, hidden);
        ggml_tensor * denominator =
            ggml_sum_rows(ctx0, ggml_sqr(ctx0, key));
        denominator = ggml_reshape_2d(
            ctx0, denominator, 4, 1);
        denominator = ggml_clamp(
            ctx0, denominator, 1e-6f, 1e30f);
        denominator = ggml_repeat(
            ctx0, denominator, coefficients);
        return ggml_div(ctx0, coefficients, denominator);
    };
    const auto lifting_forward_step =
            [&](ggml_tensor * hidden,
                ggml_tensor * key,
                ggml_tensor * value,
                const char * name,
                int32_t il) {
        GGML_ASSERT(
            value &&
            value->ne[0] == n_embd &&
            value->ne[1] == 4);
        ggml_tensor * coefficients =
            lifting_coefficients(key, hidden);
        ggml_tensor * factor_delta =
            ggml_sub(ctx0, value, key);
        // factor_delta is [n_embd, rank] and coefficients are
        // [rank, n_tokens]. ggml_mul_mat cannot accept a transposed left
        // operand. OUT_PROD(delta, transpose(coefficients)) computes the
        // required [n_embd, n_tokens] product with a native legal topology.
        ggml_tensor * delta = ggml_out_prod(
            ctx0,
            factor_delta,
            ggml_transpose(ctx0, coefficients));
        ggml_tensor * transformed =
            ggml_add(ctx0, hidden, delta);
        cb(transformed, name, il);
        return std::make_pair(
            transformed,
            lifting_step{key, coefficients, delta});
    };
    const auto cyclic_value_panel =
            [&](ggml_tensor * panel) {
        GGML_ASSERT(
            panel &&
            panel->ne[0] == n_embd &&
            panel->ne[1] == 4);
        std::array<ggml_tensor *, 4> slots = {};
        for (size_t destination = 0;
             destination < slots.size();
             ++destination) {
            const size_t source =
                (destination + 1) % slots.size();
            slots[destination] = ggml_view_2d(
                ctx0,
                panel,
                n_embd,
                1,
                panel->nb[1],
                source * panel->nb[1]);
        }
        ggml_tensor * result =
            ggml_concat(ctx0, slots[0], slots[1], 1);
        result = ggml_concat(ctx0, result, slots[2], 1);
        return ggml_concat(ctx0, result, slots[3], 1);
    };
    const auto apply_lifting =
            [&](ggml_tensor * hidden,
                size_t layer_index,
                int32_t il) {
        const auto & state =
            cparams.neo3000_semantic_carrier;
        const uint32_t control =
            cparams.neo3000_lifting_control;
        GGML_ASSERT(
            state &&
            state->source_conditioned_lifting &&
            control > 0 &&
            control <= 5 &&
            layer_index < state->lifting_layers.size() &&
            state->lifting_layers.at(layer_index) == il);
        ggml_tensor * f_key =
            state->lifting_f_key_active_layers.at(layer_index);
        ggml_tensor * f_value =
            state->lifting_f_value_active_layers.at(layer_index);
        ggml_tensor * g_key =
            state->lifting_g_key_active_layers.at(layer_index);
        ggml_tensor * g_value =
            state->lifting_g_value_active_layers.at(layer_index);
        if (control == 5) {
            g_value = cyclic_value_panel(g_value);
        }

        const bool use_f =
            control == 1 || control == 2 ||
            control == 4 || control == 5;
        const bool use_g =
            control == 1 || control == 3 ||
            control == 4 || control == 5;
        const bool reverse = control == 4;
        std::array<lifting_step, 2> steps = {};
        size_t step_count = 0;
        ggml_tensor * transformed = hidden;
        const auto add_f = [&]() {
            auto result = lifting_forward_step(
                transformed,
                f_key,
                f_value,
                "neo3000_lifting_F_forward",
                il);
            transformed = result.first;
            steps[step_count++] = result.second;
        };
        const auto add_g = [&]() {
            auto result = lifting_forward_step(
                transformed,
                g_key,
                g_value,
                control == 5
                    ? "neo3000_lifting_G_mutated_forward"
                    : "neo3000_lifting_G_forward",
                il);
            transformed = result.first;
            steps[step_count++] = result.second;
        };
        if (reverse) {
            if (use_g) {
                add_g();
            }
            if (use_f) {
                add_f();
            }
        } else {
            if (use_f) {
                add_f();
            }
            if (use_g) {
                add_g();
            }
        }

        // Q/K/V consume `transformed`. The reverse path is a declared graph
        // output so the hidden state and both rank-four ancillas are actually
        // uncomputed after that read.
        ggml_tensor * restored = transformed;
        ggml_tensor * error = nullptr;
        for (size_t reverse_index = step_count;
             reverse_index > 0;
             --reverse_index) {
            const lifting_step & step =
                steps[reverse_index - 1];
            restored = ggml_sub(ctx0, restored, step.delta);
            ggml_tensor * restored_coefficients =
                lifting_coefficients(step.key, restored);
            ggml_tensor * ancilla_residual = ggml_sub(
                ctx0,
                step.coefficients,
                restored_coefficients);
            ggml_tensor * ancilla_error = ggml_sum(
                ctx0,
                ggml_sqr(ctx0, ancilla_residual));
            error = error
                ? ggml_add(ctx0, error, ancilla_error)
                : ancilla_error;
        }
        ggml_tensor * hidden_error = ggml_sum(
            ctx0,
            ggml_sqr(
                ctx0,
                ggml_sub(ctx0, restored, hidden)));
        error = error
            ? ggml_add(ctx0, error, hidden_error)
            : hidden_error;
        cb(restored, "neo3000_lifting_restored_hidden", il);
        cb(error, "neo3000_lifting_reverse_branch_residual", il);
        return std::make_pair(transformed, error);
    };

    // MTP/NextN layers are loaded as extra decoder blocks but not executed in the main pass.
    for (int il = 0; il < n_layer; ++il) {
        res->t_layer_inp[il] = inpL;
        auto carrier_read = apply_semantic_carrier(inpL, il);
        inpL = carrier_read.first;
        ggml_tensor * carrier_dynamic_delta = carrier_read.second;

        ggml_tensor * inpSA = inpL;
        ggml_tensor * transition_input = inpL;
        const auto & carrier_state =
            cparams.neo3000_semantic_carrier;
        if (carrier_dynamic_delta &&
            carrier_state &&
            carrier_state->recurrent_transition_input) {
            transition_input =
                ggml_add(
                    ctx0,
                    transition_input,
                    carrier_dynamic_delta);
            cb(
                transition_input,
                "neo3000_semantic_carrier_recurrent_transition_input",
                il);
        }

        cur = build_norm(
            transition_input,
            model.layers[il].attn_norm,
            nullptr,
            LLM_NORM_RMS,
            il);
        cb(cur, "attn_norm", il);

        const auto & lifting_state =
            cparams.neo3000_semantic_carrier;
        if (!hparams.is_recr(il) &&
            lifting_state &&
            lifting_state->source_conditioned_lifting) {
            GGML_ASSERT(
                lifting_layer_index <
                    lifting_state->lifting_layers.size() &&
                lifting_state->lifting_layers.at(
                    lifting_layer_index) == il);
            res->t_neo3000_lifting_state[il] = cur;
            if (cparams.neo3000_lifting_control != 0) {
                auto lifting = apply_lifting(
                    cur, lifting_layer_index, il);
                cur = lifting.first;
                lifting_reverse_branch_residual =
                    lifting_reverse_branch_residual
                        ? ggml_add(
                            ctx0,
                            lifting_reverse_branch_residual,
                            lifting.second)
                        : lifting.second;
            }
        }

        ggml_build_forward_expand(gf, cur);

        // Determine layer type and build appropriate attention mechanism
        if (hparams.is_recr(il)) {
            // Linear attention layer (gated delta net)
            cur = build_layer_attn_linear(inp->get_recr(), cur, il);
        } else {
            // Full attention layer
            ggml_tensor * depth_layer_memory = nullptr;
            if (depth_memory_input) {
                GGML_ASSERT(
                    depth_memory_layer_index <
                        depth_memory_input
                            ->layer_memory.size());
                GGML_ASSERT(
                    depth_memory_state
                        ->depth_layers.at(
                            depth_memory_layer_index) ==
                        il);
                depth_layer_memory =
                    depth_memory_input
                        ->layer_memory.at(
                            depth_memory_layer_index);
            }
            cur = build_layer_attn(
                inp->get_attn(),
                cur,
                inp_pos,
                sections,
                il,
                depth_layer_memory);
            ++depth_memory_layer_index;
            ++lifting_layer_index;
        }

        if (il == n_layer - 1 && inp_out_ids && cparams.embeddings_nextn_masked) {
            cur   = ggml_get_rows(ctx0, cur, inp_out_ids);
            inpSA = ggml_get_rows(ctx0, inpSA, inp_out_ids);
        }

        // Residual connection
        cur = ggml_add(ctx0, cur, inpSA);
        cb(cur, "attn_residual", il);

        // Save the tensor before post-attention norm for residual connection
        ggml_tensor * ffn_residual = cur;

        // Post-attention norm
        ggml_tensor * attn_post_norm = build_norm(cur, model.layers[il].attn_post_norm, nullptr, LLM_NORM_RMS, il);
        cb(attn_post_norm, "attn_post_norm", il);

        // MOE FFN layer
        cur = build_layer_ffn(
            attn_post_norm,
            carrier_state && carrier_state->moe_router_bias
                ? carrier_dynamic_delta
                : nullptr,
            il);
        cb(cur, "ffn_out", il);

        // Residual connection for FFN - add to the tensor from before post_attention_layernorm
        cur = ggml_add(ctx0, cur, ffn_residual);
        cb(cur, "post_moe", il);

        cur = build_cvec(cur, il);
        cb(cur, "l_out", il);

        // Input for next layer
        inpL = cur;
    }
    if (cparams.neo3000_lifting_control != 0) {
        GGML_ASSERT(lifting_reverse_branch_residual);
        // This branch is not a dependency of the transformed Q/K/V path.
        // Expand it explicitly so the reverse computation and residual are
        // executed rather than merely marked as an output after graph build.
        ggml_build_forward_expand(gf, lifting_reverse_branch_residual);
        res->t_neo3000_lifting_reverse_branch_residual =
            lifting_reverse_branch_residual;
    }
    cur = inpL;

    // post-norm hidden state feeds both the LM head and the MTP seed below
    cur = build_norm(cur, model.output_norm, nullptr, LLM_NORM_RMS, -1);

    cb(cur, "h_nextn", -1);
    res->t_h_nextn = cur;

    if (!cparams.embeddings_nextn_masked && inp_out_ids) {
        cur = ggml_get_rows(ctx0, cur, inp_out_ids);
    }

    cur = apply_semantic_carrier(cur, -1).first;

    cb(cur, "result_norm", -1);
    res->t_embd = cur;

    if (soft_role_input) {
        ggml_tensor * candidate_output_rows = ggml_get_rows(
            ctx0,
            model.output,
            soft_role_input->candidate_tokens);
        ggml_tensor * candidate_logits = ggml_mul_mat(
            ctx0,
            candidate_output_rows,
            cur);
        if (model.output_s) {
            candidate_logits = ggml_mul(
                ctx0,
                candidate_logits,
                model.output_s);
        }
        ggml_tensor * candidate_probabilities = ggml_soft_max(
            ctx0,
            candidate_logits);
        ggml_tensor * candidate_input_rows = ggml_get_rows(
            ctx0,
            model.tok_embd,
            soft_role_input->candidate_tokens);
        ggml_tensor * candidate_input_reader = ggml_cont(
            ctx0,
            ggml_transpose(
                ctx0,
                candidate_input_rows));
        ggml_tensor * soft_output_embedding = ggml_mul_mat(
            ctx0,
            candidate_input_reader,
            candidate_probabilities);
        cb(
            candidate_probabilities,
            "neo3000_soft_role_candidate_probabilities",
            -1);
        cb(
            soft_output_embedding,
            "neo3000_soft_role_output_embedding",
            -1);
        res->t_neo3000_soft_role_output =
            soft_output_embedding;
        ggml_build_forward_expand(
            gf,
            soft_output_embedding);
    }

    // LM head
    cur = build_lora_mm(model.output, cur, model.output_s);

    cb(cur, "result_output", -1);
    res->t_logits = cur;

    ggml_build_forward_expand(gf, cur);
}

std::pair<ggml_tensor *, ggml_tensor *> llama_model_qwen35moe::graph::build_qkvz(
                ggml_tensor * input,
                        int   il) {
    const int64_t n_seqs       = ubatch.n_seqs;
    const int64_t n_seq_tokens = ubatch.n_seq_tokens;

    ggml_tensor * qkv_mixed = build_lora_mm(model.layers[il].wqkv, input, model.layers[il].wqkv_s);
    qkv_mixed = ggml_reshape_3d(ctx0, qkv_mixed, qkv_mixed->ne[0], n_seq_tokens, n_seqs);
    cb(qkv_mixed, "linear_attn_qkv_mixed", il);

    ggml_tensor * z = build_lora_mm(model.layers[il].wqkv_gate, input, model.layers[il].wqkv_gate_s);
    cb(z, "z", il);

    return { qkv_mixed, z };
}

ggml_tensor * llama_model_qwen35moe::graph::build_norm_gated(
        ggml_tensor * input,
        ggml_tensor * weights,
        ggml_tensor * gate,
        int           layer) {
    ggml_tensor * normalized = build_norm(input, weights, nullptr, LLM_NORM_RMS, layer);
    ggml_tensor * gated_silu = ggml_silu(ctx0, gate);

    return ggml_mul(ctx0, normalized, gated_silu);
}

ggml_tensor * llama_model_qwen35moe::graph::build_layer_attn(
        llm_graph_input_attn_kv * inp,
        ggml_tensor *             cur,
        ggml_tensor *             inp_pos,
        int *                     sections,
        int                       il,
        ggml_tensor *             depth_memory) {
    const int64_t n_embd_head = hparams.n_embd_head_v();
    GGML_ASSERT(n_embd_head == hparams.n_embd_head_k());

    // Order: joint QG projection, QG split, Q norm, KV projection, K norm, RoPE, attention

    // Qwen3Next uses a single Q projection that outputs query + gate
    ggml_tensor * Qcur_full = build_lora_mm(model.layers[il].wq, cur, model.layers[il].wq_s); // [ (n_embd_head * 2) * n_head, n_tokens ]
    cb(Qcur_full, "Qcur_full", il);

    ggml_tensor * Qcur = ggml_view_3d(ctx0, Qcur_full, n_embd_head, n_head, n_tokens,
        ggml_element_size(Qcur_full) * n_embd_head * 2,
        ggml_element_size(Qcur_full) * n_embd_head * 2 * n_head, 0);
    cb(Qcur, "Qcur_reshaped", il);

    // Apply Q normalization
    Qcur = build_norm(Qcur, model.layers[il].attn_q_norm, nullptr, LLM_NORM_RMS, il);
    cb(Qcur, "Qcur_normed", il);
    ggml_tensor * Qcur_depth = Qcur;

    ggml_tensor * Kcur = build_lora_mm(model.layers[il].wk, cur, model.layers[il].wk_s);
    cb(Kcur, "Kcur", il);

    ggml_tensor * Vcur = build_lora_mm(model.layers[il].wv, cur, model.layers[il].wv_s);
    cb(Vcur, "Vcur", il);

    // Apply K normalization
    Kcur = ggml_reshape_3d(ctx0, Kcur, n_embd_head, n_head_kv, n_tokens);
    Kcur = build_norm(Kcur, model.layers[il].attn_k_norm, nullptr, LLM_NORM_RMS, il);
    cb(Kcur, "Kcur_normed", il);

    ggml_tensor * gate = ggml_view_3d(ctx0, Qcur_full, n_embd_head, n_head, n_tokens,
        ggml_element_size(Qcur_full) * n_embd_head * 2,
        ggml_element_size(Qcur_full) * n_embd_head * 2 * n_head,
        ggml_element_size(Qcur_full) * n_embd_head);
    gate = ggml_cont_2d(ctx0, gate, n_embd_head * n_head, n_tokens);
    cb(gate, "gate_reshaped", il);

    Vcur = ggml_reshape_3d(ctx0, Vcur, n_embd_head, n_head_kv, n_tokens);

    // Apply IMRoPE
    Qcur = ggml_rope_multi(
            ctx0, Qcur, inp_pos, nullptr,
            n_rot, sections, rope_type, n_ctx_orig, freq_base, freq_scale,
            ext_factor, attn_factor, beta_fast, beta_slow
            );

    Kcur = ggml_rope_multi(
            ctx0, Kcur, inp_pos, nullptr,
            n_rot, sections, rope_type, n_ctx_orig, freq_base, freq_scale,
            ext_factor, attn_factor, beta_fast, beta_slow
            );

    cb(Qcur, "Qcur", il);
    cb(Kcur, "Kcur", il);
    cb(Vcur, "Vcur", il);

    // Attention computation
    const float kq_scale = hparams.f_attention_scale == 0.0f ? 1.0f / sqrtf(float(n_embd_head)) : hparams.f_attention_scale;

    cur = build_attn(inp,
                nullptr, nullptr, nullptr,
                Qcur, Kcur, Vcur, nullptr, nullptr, nullptr, kq_scale, il);
    cb(cur, "attn_pregate", il);

    if (depth_memory) {
        GGML_ASSERT(
            depth_memory->ne[0] == n_embd &&
            depth_memory->ne[1] == 4);
        ggml_tensor * depth_norm = build_norm(
            depth_memory,
            model.layers[il].attn_norm,
            nullptr,
            LLM_NORM_RMS,
            il);
        ggml_tensor * depth_k = build_lora_mm(
            model.layers[il].wk,
            depth_norm,
            model.layers[il].wk_s);
        ggml_tensor * depth_v = build_lora_mm(
            model.layers[il].wv,
            depth_norm,
            model.layers[il].wv_s);
        depth_k = ggml_reshape_3d(
            ctx0,
            depth_k,
            n_embd_head,
            n_head_kv,
            4);
        depth_k = build_norm(
            depth_k,
            model.layers[il].attn_k_norm,
            nullptr,
            LLM_NORM_RMS,
            il);
        depth_v = ggml_reshape_3d(
            ctx0,
            depth_v,
            n_embd_head,
            n_head_kv,
            4);
        ggml_tensor * depth_read = build_attn_mha(
            Qcur_depth,
            depth_k,
            depth_v,
            nullptr,
            nullptr,
            nullptr,
            nullptr,
            kq_scale,
            il);
        cb(depth_read, "neo3000_depth_memory_read", il);
        cur = ggml_add(ctx0, cur, depth_read);
        cb(cur, "neo3000_depth_memory_attn_pregate", il);
    }

    ggml_tensor * gate_sigmoid = ggml_sigmoid(ctx0, gate);
    cb(gate_sigmoid, "gate_sigmoid", il);

    cur = ggml_mul(ctx0, cur, gate_sigmoid);
    cb(cur, "attn_gated", il);

    cur = build_lora_mm(model.layers[il].wo, cur, model.layers[il].wo_s);
    cb(cur, "attn_output", il);

    return cur;
}

ggml_tensor * llama_model_qwen35moe::graph::build_layer_attn_linear(
        llm_graph_input_rs * inp,
        ggml_tensor *        cur,
        int                  il) {
    const auto * mctx_cur = inp->mctx;

    const int64_t d_inner      = hparams.ssm_d_inner;
    const int64_t n_seqs       = ubatch.n_seqs;
    const int64_t head_k_dim   = hparams.ssm_d_state;
    const int64_t num_k_heads  = hparams.ssm_n_group;
    const int64_t num_v_heads  = hparams.ssm_dt_rank;
    const int64_t head_v_dim   = d_inner / num_v_heads;
    const int64_t n_seq_tokens = ubatch.n_seq_tokens;

    GGML_ASSERT(n_seqs != 0);
    GGML_ASSERT(ubatch.equal_seqs());
    GGML_ASSERT(ubatch.n_tokens == n_seq_tokens * n_seqs);

    // Input projections
    auto qkvz = build_qkvz(cur, il);
    ggml_tensor * qkv_mixed = qkvz.first;
    ggml_tensor * z         = qkvz.second;

    ggml_tensor * beta = build_lora_mm(model.layers[il].ssm_beta, cur, model.layers[il].ssm_beta_s);
    beta = ggml_reshape_4d(ctx0, beta, 1, num_v_heads, n_seq_tokens, n_seqs);
    cb(beta, "beta", il);

    beta = ggml_sigmoid(ctx0, beta);
    cb(beta, "beta_sigmoid", il);

    ggml_tensor * alpha = build_lora_mm(model.layers[il].ssm_alpha, cur, model.layers[il].ssm_alpha_s);
    alpha = ggml_reshape_3d(ctx0, alpha, num_v_heads, n_seq_tokens, n_seqs);
    cb(alpha, "alpha", il);

    ggml_tensor * alpha_biased   = ggml_add(ctx0, alpha, model.layers[il].ssm_dt);
    ggml_tensor * alpha_softplus = ggml_softplus(ctx0, alpha_biased);
    cb(alpha_softplus, "a_softplus", il);

    ggml_tensor * gate = ggml_mul(ctx0, alpha_softplus, model.layers[il].ssm_a);  // -A_log.exp() * softplus
    cb(gate, "gate", il);

    gate = ggml_reshape_4d(ctx0, gate, 1, num_v_heads, n_seq_tokens, n_seqs);

    ggml_tensor * conv_states_all = mctx_cur->get_r_l(il);
    ggml_tensor * ssm_states_all  = mctx_cur->get_s_l(il);

    ggml_tensor * conv_kernel      = model.layers[il].ssm_conv1d;
    const int64_t conv_kernel_size = conv_kernel->ne[0];
    const int64_t conv_channels    = d_inner + 2 * hparams.ssm_n_group * hparams.ssm_d_state;

    ggml_tensor * conv_input = build_conv_state(inp, conv_states_all, qkv_mixed, conv_kernel_size, conv_channels, il);

    ggml_tensor * state = build_rs(inp, ssm_states_all, hparams.n_embd_s(), n_seqs);
    state = ggml_reshape_4d(ctx0, state, head_v_dim, head_v_dim, num_v_heads, n_seqs);
    cb(state, "state_predelta", il);

    ggml_tensor * conv_output_proper = ggml_ssm_conv(ctx0, conv_input, conv_kernel);
    cb(conv_output_proper, "conv_output_raw", il);

    ggml_tensor * conv_output_silu = ggml_silu(ctx0, conv_output_proper);
    cb(conv_output_silu, "conv_output_silu", il);

    ggml_tensor * conv_qkv_mix = conv_output_silu;

    // Calculate the total conv dimension
    int64_t qkv_dim = head_k_dim * num_k_heads * 2 + head_v_dim * num_v_heads;
    int64_t nb1_qkv = ggml_row_size(conv_qkv_mix->type, qkv_dim);

    // Extract the convolved Q, K, V from conv_output
    ggml_tensor * q_conv = ggml_view_4d(ctx0, conv_qkv_mix, head_k_dim, num_k_heads, n_seq_tokens, n_seqs,
            ggml_row_size(conv_qkv_mix->type, head_k_dim),
            nb1_qkv,
            nb1_qkv * n_seq_tokens,
            0);

    ggml_tensor * k_conv = ggml_view_4d(ctx0, conv_qkv_mix, head_k_dim, num_k_heads, n_seq_tokens, n_seqs,
            ggml_row_size(conv_qkv_mix->type, head_k_dim),
            nb1_qkv,
            nb1_qkv * n_seq_tokens,
            head_k_dim * num_k_heads * ggml_element_size(conv_qkv_mix));

    ggml_tensor * v_conv = ggml_view_4d(ctx0, conv_qkv_mix, head_v_dim, num_v_heads, n_seq_tokens, n_seqs,
            ggml_row_size(conv_qkv_mix->type, head_v_dim),
            nb1_qkv,
            nb1_qkv * n_seq_tokens,
            ggml_row_size(conv_qkv_mix->type, 2 * head_k_dim * num_k_heads));

    cb(q_conv, "q_conv", il);
    cb(k_conv, "k_conv", il);
    cb(v_conv, "v_conv", il);

    const float eps_norm = hparams.f_norm_rms_eps;

    q_conv = ggml_l2_norm(ctx0, q_conv, eps_norm);
    k_conv = ggml_l2_norm(ctx0, k_conv, eps_norm);

    //q_conv = ggml_cont_4d(ctx0, q_conv, head_k_dim, num_k_heads, n_seq_tokens, n_seqs);
    //k_conv = ggml_cont_4d(ctx0, k_conv, head_k_dim, num_k_heads, n_seq_tokens, n_seqs);
    //v_conv = ggml_cont_4d(ctx0, v_conv, head_v_dim, num_v_heads, n_seq_tokens, n_seqs);

    // if head keys and value keys are different, repeat to force tensors into matching shapes
    // note: need explicit repeat only if we are not using the fused GDN.
    if (num_k_heads != num_v_heads && (!cparams.fused_gdn_ar || !cparams.fused_gdn_ch)) {
        GGML_ASSERT(num_v_heads % num_k_heads == 0);
        q_conv = ggml_repeat_4d(ctx0, q_conv, head_k_dim, num_v_heads, n_seq_tokens, n_seqs);
        k_conv = ggml_repeat_4d(ctx0, k_conv, head_k_dim, num_v_heads, n_seq_tokens, n_seqs);
    }

    cb(q_conv, "q_conv_predelta", il);
    cb(k_conv, "k_conv_predelta", il);
    cb(v_conv, "v_conv_predelta", il);

    ggml_tensor * output = build_recurrent_attn(inp, ssm_states_all, q_conv, k_conv, v_conv, gate, beta, state, il);

    // z: [head_dim, n_heads, n_tokens, n_seqs] -> [n_heads * n_tokens * n_seqs, head_dim]
    ggml_tensor * z_2d = ggml_reshape_4d(ctx0, z, head_v_dim, num_v_heads, n_seq_tokens, n_seqs);

    // Apply gated normalization: self.norm(core_attn_out, z)
    ggml_tensor * attn_out_norm = build_norm_gated(output, model.layers[il].ssm_norm, z_2d, il);

    // Final reshape: [head_dim, n_heads, n_tokens, n_seqs] -> [n_tokens, n_seqs, n_heads * head_dim]
    ggml_tensor * final_output = ggml_reshape_3d(ctx0, attn_out_norm, head_v_dim * num_v_heads, n_seq_tokens, n_seqs);
    cb(final_output, "final_output", il);

    // Output projection
    cur = build_lora_mm(model.layers[il].ssm_out, final_output, model.layers[il].ssm_out_s);
    cb(cur, "linear_attn_out", il);

    // Reshape back to original dimensions
    cur = ggml_reshape_2d(ctx0, cur, n_embd, n_seq_tokens * n_seqs);

    return cur;
}

ggml_tensor * llama_model_qwen35moe::graph::build_layer_ffn(
        ggml_tensor * cur,
        ggml_tensor * carrier_router_delta,
        const int il) {
    // Check if this is an MoE layer
    GGML_ASSERT(model.layers[il].ffn_gate_inp != nullptr);

    ggml_tensor * carrier_router_bias = nullptr;
    if (carrier_router_delta) {
        carrier_router_bias =
            build_lora_mm(
                model.layers[il].ffn_gate_inp,
                carrier_router_delta);
        cb(
            carrier_router_bias,
            "neo3000_semantic_carrier_router_bias",
            il);
    }

    ggml_tensor * moe_out =
        build_moe_ffn(cur,
            model.layers[il].ffn_gate_inp,
            carrier_router_bias,
            model.layers[il].ffn_up_exps,
            nullptr,
            model.layers[il].ffn_gate_exps,
            nullptr,
            model.layers[il].ffn_down_exps,
            nullptr,
            nullptr,
            n_expert, n_expert_used,
            LLM_FFN_SILU, true,
            hparams.expert_weights_scale,
            LLAMA_EXPERT_GATING_FUNC_TYPE_SOFTMAX, il,
            nullptr, model.layers[il].ffn_gate_up_exps,
            nullptr,
            model.layers[il].ffn_up_exps_s,
            model.layers[il].ffn_gate_exps_s,
            model.layers[il].ffn_down_exps_s);
    cb(moe_out, "ffn_moe_out", il);

    // Add shared experts if present - following Qwen3Next reference implementation
    if (model.layers[il].ffn_up_shexp != nullptr) {
        ggml_tensor * ffn_shexp =
            build_ffn(cur,
                model.layers[il].ffn_up_shexp, NULL, model.layers[il].ffn_up_shexp_s,
                model.layers[il].ffn_gate_shexp, NULL, model.layers[il].ffn_gate_shexp_s,
                model.layers[il].ffn_down_shexp, NULL, model.layers[il].ffn_down_shexp_s,
                NULL,
                LLM_FFN_SILU, LLM_FFN_PAR, il);
        cb(ffn_shexp, "ffn_shexp", il);

        // Apply shared expert gating as in the reference implementation
        // The shared expert has its own gate that is sigmoided
        // Note: ffn_gate_inp_shexp is the shared expert gate (outputs 1 value per token)
        ggml_tensor * shared_gate = build_lora_mm(model.layers[il].ffn_gate_inp_shexp, cur);
        cb(shared_gate, "shared_expert_gate", il);

        // Apply sigmoid to the gate
        shared_gate = ggml_sigmoid(ctx0, shared_gate);
        cb(shared_gate, "shared_expert_gate_sigmoid", il);


        // Apply the gate to the shared expert output
        ffn_shexp = ggml_mul(ctx0, ffn_shexp, shared_gate);
        cb(ffn_shexp, "ffn_shexp_gated", il);

        cur = ggml_add(ctx0, moe_out, ffn_shexp);
        cb(cur, "ffn_out", il);
    } else {
        cur = moe_out;
    }

    return cur;
}

// LLM_GRAPH_TYPE_DECODER_MTP draft head for Qwen3.5/3.6 MoE
llama_model_qwen35moe::graph_mtp::graph_mtp(const llama_model & model, const llm_graph_params & params)
    : llm_graph_context(params) {
    GGML_ASSERT(hparams.n_layer_nextn > 0 && "QWEN35MOE MTP requires n_layer_nextn > 0");
    GGML_ASSERT(hparams.n_layer_nextn == 1 && "QWEN35MOE MTP currently only supports a single MTP block");

    const int64_t n_embd_head = hparams.n_embd_head_v();
    GGML_ASSERT(n_embd_head == hparams.n_embd_head_k());

    const int il = hparams.n_layer();
    const auto & layer = model.layers[il];

    GGML_ASSERT(layer.nextn.eh_proj    && "MTP block missing nextn.eh_proj");
    GGML_ASSERT(layer.nextn.enorm      && "MTP block missing nextn.enorm");
    GGML_ASSERT(layer.nextn.hnorm      && "MTP block missing nextn.hnorm");
    GGML_ASSERT(layer.ffn_gate_inp     && "MTP block missing ffn_gate_inp");

    int sections[4];
    std::copy(std::begin(hparams.rope_sections), std::begin(hparams.rope_sections) + 4, sections);

    // TODO: extract in a common llm_graph_context::build_inp_embd_h()
    auto inp = std::make_unique<llm_graph_input_embd_h>(hparams.n_embd);

    inp->tokens = ggml_new_tensor_1d(ctx0, GGML_TYPE_I32, n_tokens);
    ggml_set_input(inp->tokens);

    inp->embd = ggml_new_tensor_2d(ctx0, GGML_TYPE_F32, hparams.n_embd_inp(), n_tokens);
    ggml_set_input(inp->embd);

    // TODO: make static using `ggml_build_forward_select()`
    //       see llm_graph_context::build_inp_embd() for reference
    ggml_tensor * tok_embd;
    if (ubatch.token) {
        ggml_tensor * tok_embd_w = layer.nextn.embed_tokens ? layer.nextn.embed_tokens : model.tok_embd;

        tok_embd = ggml_get_rows(ctx0, tok_embd_w, inp->tokens);
    } else {
        tok_embd = inp->embd;
    }
    cb(tok_embd, "mtp_tok_embd", il);

    inp->h = ggml_new_tensor_2d(ctx0, GGML_TYPE_F32, hparams.n_embd, n_tokens);
    ggml_set_input(inp->h);
    ggml_set_name(inp->h, "mtp_h_input");

    ggml_tensor * h_embd = inp->h;

    res->add_input(std::move(inp));

    ggml_tensor * inp_pos     = build_inp_pos();
    ggml_tensor * inp_out_ids = build_inp_out_ids();

    auto * inp_attn = build_attn_inp_kv();

    ggml_tensor * h_norm = build_norm(h_embd, layer.nextn.hnorm, nullptr, LLM_NORM_RMS, il);
    cb(h_norm, "mtp_hnorm", il);

    ggml_tensor * e_norm = build_norm(tok_embd, layer.nextn.enorm, nullptr, LLM_NORM_RMS, il);
    cb(e_norm, "mtp_enorm", il);

    ggml_tensor * concat = ggml_concat(ctx0, e_norm, h_norm, /*dim=*/ 0);
    cb(concat, "mtp_concat", il);

    ggml_tensor * cur = build_lora_mm(layer.nextn.eh_proj, concat, layer.nextn.eh_proj_s);
    cb(cur, "mtp_eh_proj", il);

    ggml_tensor * inpSA = cur;

    cur = build_norm(cur, layer.attn_norm, nullptr, LLM_NORM_RMS, il);
    cb(cur, "mtp_attn_norm", il);

    ggml_tensor * Qcur_full = build_lora_mm(layer.wq, cur, layer.wq_s);
    cb(Qcur_full, "mtp_Qcur_full", il);

    ggml_tensor * Qcur = ggml_view_3d(ctx0, Qcur_full,
            n_embd_head, n_head, n_tokens,
            ggml_element_size(Qcur_full) * n_embd_head * 2,
            ggml_element_size(Qcur_full) * n_embd_head * 2 * n_head,
            0);
    Qcur = build_norm(Qcur, layer.attn_q_norm, nullptr, LLM_NORM_RMS, il);
    cb(Qcur, "mtp_Qcur_normed", il);

    ggml_tensor * gate = ggml_view_3d(ctx0, Qcur_full,
            n_embd_head, n_head, n_tokens,
            ggml_element_size(Qcur_full) * n_embd_head * 2,
            ggml_element_size(Qcur_full) * n_embd_head * 2 * n_head,
            ggml_element_size(Qcur_full) * n_embd_head);
    gate = ggml_cont_2d(ctx0, gate, n_embd_head * n_head, n_tokens);
    cb(gate, "mtp_gate", il);

    ggml_tensor * Kcur = build_lora_mm(layer.wk, cur, layer.wk_s);
    Kcur = ggml_reshape_3d(ctx0, Kcur, n_embd_head, n_head_kv, n_tokens);
    Kcur = build_norm(Kcur, layer.attn_k_norm, nullptr, LLM_NORM_RMS, il);
    cb(Kcur, "mtp_Kcur_normed", il);

    ggml_tensor * Vcur = build_lora_mm(layer.wv, cur, layer.wv_s);
    Vcur = ggml_reshape_3d(ctx0, Vcur, n_embd_head, n_head_kv, n_tokens);
    cb(Vcur, "mtp_Vcur", il);

    Qcur = ggml_rope_multi(ctx0, Qcur, inp_pos, nullptr,
            n_rot, sections, rope_type, n_ctx_orig, freq_base, freq_scale,
            ext_factor, attn_factor, beta_fast, beta_slow);
    Kcur = ggml_rope_multi(ctx0, Kcur, inp_pos, nullptr,
            n_rot, sections, rope_type, n_ctx_orig, freq_base, freq_scale,
            ext_factor, attn_factor, beta_fast, beta_slow);

    const float kq_scale = hparams.f_attention_scale == 0.0f
            ? 1.0f / sqrtf(float(n_embd_head)) : hparams.f_attention_scale;

    cur = build_attn(inp_attn,
            nullptr, nullptr, nullptr,
            Qcur, Kcur, Vcur, nullptr, nullptr, nullptr, kq_scale, il);
    cb(cur, "mtp_attn_pregate", il);

    cur = ggml_mul(ctx0, cur, ggml_sigmoid(ctx0, gate));
    cur = build_lora_mm(layer.wo, cur, layer.wo_s);
    cb(cur, "mtp_attn_out", il);

    cur = ggml_add(ctx0, cur, inpSA);
    cb(cur, "mtp_attn_residual", il);

    ggml_tensor * ffn_residual = cur;
    cur = build_norm(cur, layer.attn_post_norm, nullptr, LLM_NORM_RMS, il);
    cb(cur, "mtp_attn_post_norm", il);

    // MoE FFN — routed experts plus gated shared expert (mirrors qwen35moe).
    ggml_tensor * moe_out =
        build_moe_ffn(cur,
            layer.ffn_gate_inp,
            layer.ffn_up_exps,
            layer.ffn_gate_exps,
            layer.ffn_down_exps,
            nullptr,
            n_expert, n_expert_used,
            LLM_FFN_SILU, true,
            hparams.expert_weights_scale,
            LLAMA_EXPERT_GATING_FUNC_TYPE_SOFTMAX, il,
            nullptr, layer.ffn_gate_up_exps,
            layer.ffn_up_exps_s,
            layer.ffn_gate_exps_s,
            layer.ffn_down_exps_s);
    cb(moe_out, "mtp_ffn_moe_out", il);

    if (layer.ffn_up_shexp != nullptr) {
        ggml_tensor * ffn_shexp =
            build_ffn(cur,
                layer.ffn_up_shexp,   nullptr, layer.ffn_up_shexp_s,
                layer.ffn_gate_shexp, nullptr, layer.ffn_gate_shexp_s,
                layer.ffn_down_shexp, nullptr, layer.ffn_down_shexp_s,
                nullptr,
                LLM_FFN_SILU, LLM_FFN_PAR, il);
        cb(ffn_shexp, "mtp_ffn_shexp", il);

        ggml_tensor * shared_gate = build_lora_mm(layer.ffn_gate_inp_shexp, cur);
        shared_gate = ggml_sigmoid(ctx0, shared_gate);
        cb(shared_gate, "mtp_shared_expert_gate_sigmoid", il);

        ffn_shexp = ggml_mul(ctx0, ffn_shexp, shared_gate);
        cb(ffn_shexp, "mtp_ffn_shexp_gated", il);

        cur = ggml_add(ctx0, moe_out, ffn_shexp);
    } else {
        cur = moe_out;
    }
    cb(cur, "mtp_ffn_out", il);

    cur = ggml_add(ctx0, cur, ffn_residual);
    cb(cur, "mtp_post_ffn", il);

    ggml_tensor * head_norm_w = layer.nextn.shared_head_norm
            ? layer.nextn.shared_head_norm
            : model.output_norm;
    GGML_ASSERT(head_norm_w && "QWEN35MOE MTP: missing both nextn.shared_head_norm and output_norm");
    cur = build_norm(cur, head_norm_w, nullptr, LLM_NORM_RMS, -1);

    cb(cur, "h_nextn", -1);
    res->t_h_nextn= cur;

    cur = ggml_get_rows(ctx0, cur, inp_out_ids);
    cb(cur, "mtp_shared_head_norm", -1);

    ggml_tensor * head_w = layer.nextn.shared_head_head ? layer.nextn.shared_head_head : model.output;
    ggml_tensor * head_s = layer.nextn.shared_head_head ? layer.nextn.shared_head_head_s : model.output_s;
    GGML_ASSERT(head_w && "QWEN35MOE MTP: missing LM head (nextn.shared_head_head or model.output)");
    cur = build_lora_mm(head_w, cur, head_s);
    cb(cur, "result_output", -1);

    res->t_logits = cur;
    ggml_build_forward_expand(gf, cur);
}
