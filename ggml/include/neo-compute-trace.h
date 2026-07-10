#pragma once

// Neo3000 compute-map trace schema v1.
//
// NEO_COMPUTE_TRACE is intentionally undefined in normal builds. In that
// configuration NEO_COMPUTE_TRACE_EMIT discards its argument before parsing,
// so there is no trace state, allocation, file, timestamp, or formatting cost.
// Trace-enabled diagnostic builds set NEO_COMPUTE_TRACE and provide an ignored
// local output path through NEO_COMPUTE_TRACE_PATH.

#ifdef NEO_COMPUTE_TRACE

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <mutex>
#include <string>

namespace neo_compute_trace {

static constexpr uint64_t unknown_u64 = UINT64_MAX;

struct event {
    const char * event_id;
    const char * phase;
    const char * operator_name;
    const char * backend_expected;
    const char * backend_actual;

    int device_id = -1;
    uint64_t duration_ns = unknown_u64;
    int token_index = -1;
    int layer_index = -1;

    const char * tensor_shape = nullptr;
    uint64_t bytes_host_to_device = unknown_u64;
    uint64_t bytes_device_to_host = unknown_u64;
    uint64_t bytes_device_to_device = unknown_u64;
    const char * cuda_stream = nullptr;
    const char * sync_kind = nullptr;
    const char * graph_id = nullptr;
    const char * graph_action = nullptr;
    const char * graph_shape_signature = nullptr;
    int expert_id = -1;
    int route_rank = -1;
    int expert_bucket_tokens = -1;
    int expert_bucket_max = -1;
    int mmq_tile_m = -1;
    int mmq_tile_n = -1;
    int mmq_tile_k = -1;
    uint64_t recurrent_state_bytes = unknown_u64;
    uint64_t recurrent_copy_bytes = unknown_u64;
    const char * recurrent_action = nullptr;
};

inline uint64_t monotonic_timestamp_ns() {
    return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}

inline void append_json_string(std::string & out, const char * value) {
    if (value == nullptr) {
        out += "null";
        return;
    }
    out.push_back('"');
    for (const unsigned char ch : std::string(value)) {
        switch (ch) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (ch < 0x20) {
                    char escaped[7];
                    std::snprintf(escaped, sizeof(escaped), "\\u%04x", static_cast<unsigned>(ch));
                    out += escaped;
                } else {
                    out.push_back(static_cast<char>(ch));
                }
        }
    }
    out.push_back('"');
}

inline void append_key(std::string & out, const char * key) {
    if (out.size() > 1) {
        out.push_back(',');
    }
    append_json_string(out, key);
    out.push_back(':');
}

inline void append_optional_u64(std::string & out, const char * key, uint64_t value) {
    if (value == unknown_u64) {
        return;
    }
    append_key(out, key);
    out += std::to_string(value);
}

inline void append_optional_int(std::string & out, const char * key, int value) {
    if (value < 0) {
        return;
    }
    append_key(out, key);
    out += std::to_string(value);
}

inline void append_optional_string(std::string & out, const char * key, const char * value) {
    if (value == nullptr) {
        return;
    }
    append_key(out, key);
    append_json_string(out, value);
}

inline void emit(const event & value) {
    const char * path = std::getenv("NEO_COMPUTE_TRACE_PATH");
    if (path == nullptr || path[0] == '\0') {
        return;
    }

    const uint64_t timestamp_ns = monotonic_timestamp_ns();
    const char * request_id = std::getenv("NEO_COMPUTE_TRACE_REQUEST_ID");
    if (request_id == nullptr || request_id[0] == '\0') {
        request_id = "runtime-unscoped";
    }

    std::string out = "{";
    append_key(out, "schema_version"); out += "1";
    append_key(out, "event_id"); append_json_string(out, value.event_id);
    append_key(out, "monotonic_timestamp_ns"); out += std::to_string(timestamp_ns);
    append_key(out, "request_id"); append_json_string(out, request_id);
    append_key(out, "sequence"); out += std::to_string(timestamp_ns);
    append_key(out, "phase"); append_json_string(out, value.phase);
    append_key(out, "token_index");
    if (value.token_index < 0) out += "null"; else out += std::to_string(value.token_index);
    append_key(out, "layer_index");
    if (value.layer_index < 0) out += "null"; else out += std::to_string(value.layer_index);
    append_key(out, "operator"); append_json_string(out, value.operator_name);
    append_key(out, "backend_expected"); append_json_string(out, value.backend_expected);
    append_key(out, "backend_actual"); append_json_string(out, value.backend_actual);
    append_key(out, "device_id");
    if (value.device_id < 0) out += "null"; else out += std::to_string(value.device_id);
    append_key(out, "duration_ns");
    if (value.duration_ns == unknown_u64) out += "null"; else out += std::to_string(value.duration_ns);

    append_optional_string(out, "tensor_shape", value.tensor_shape);
    append_optional_u64(out, "bytes_host_to_device", value.bytes_host_to_device);
    append_optional_u64(out, "bytes_device_to_host", value.bytes_device_to_host);
    append_optional_u64(out, "bytes_device_to_device", value.bytes_device_to_device);
    append_optional_string(out, "cuda_stream", value.cuda_stream);
    append_optional_string(out, "sync_kind", value.sync_kind);
    append_optional_string(out, "graph_id", value.graph_id);
    append_optional_string(out, "graph_action", value.graph_action);
    append_optional_string(out, "graph_shape_signature", value.graph_shape_signature);
    append_optional_int(out, "expert_id", value.expert_id);
    append_optional_int(out, "route_rank", value.route_rank);
    append_optional_int(out, "expert_bucket_tokens", value.expert_bucket_tokens);
    append_optional_int(out, "expert_bucket_max", value.expert_bucket_max);
    append_optional_int(out, "mmq_tile_m", value.mmq_tile_m);
    append_optional_int(out, "mmq_tile_n", value.mmq_tile_n);
    append_optional_int(out, "mmq_tile_k", value.mmq_tile_k);
    append_optional_u64(out, "recurrent_state_bytes", value.recurrent_state_bytes);
    append_optional_u64(out, "recurrent_copy_bytes", value.recurrent_copy_bytes);
    append_optional_string(out, "recurrent_action", value.recurrent_action);
    out += "}\n";

    static std::mutex write_mutex;
    std::lock_guard<std::mutex> lock(write_mutex);
    if (FILE * file = std::fopen(path, "ab")) {
        std::fwrite(out.data(), 1, out.size(), file);
        std::fclose(file);
    }
}

} // namespace neo_compute_trace

#define NEO_COMPUTE_TRACE_EMIT(value) ::neo_compute_trace::emit(value)

#else

#define NEO_COMPUTE_TRACE_EMIT(value) ((void) 0)

#endif
