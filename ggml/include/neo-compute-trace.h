#pragma once

// Neo3000 compute-map trace schema v2.
//
// Schema v2 preserves the schema-v1 envelope and event-ID meanings while
// adding explicit placement_reason and bounded aggregate records. Schema-v1
// artifacts remain identifiable by their schema_version value.
//
// Trace mode: diagnostic-only, aggregate-delta JSONL.
// Aggregation: fixed-capacity thread-local table, bounded merge, one persistent
// writer per instrumented module, and one batched write per merge.
// Session limits: 64 MiB and 200,000 serialized records. Each of the two
// instrumented modules uses a stricter 24 MiB / 75,000-record bound.
// Flush policy: 4,096 aggregate slots or 1 MiB, plus a partial periodic flush
// no more than once per second. No file operation or global lock occurs per
// event. Limit pressure sets trace_truncated and records dropped event counts.
//
// NEO_COMPUTE_TRACE is intentionally undefined in normal builds. The macro
// below discards its argument before parsing, so normal builds have no trace
// state, allocation, file, formatting, timestamp, or background-thread cost.

#ifdef NEO_COMPUTE_TRACE

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <mutex>
#include <string>

namespace neo_compute_trace {

static constexpr uint64_t unknown_u64 = UINT64_MAX;
static constexpr uint64_t session_max_output_bytes = 64ull * 1024ull * 1024ull;
static constexpr uint64_t session_max_serialized_records = 200000;
static constexpr size_t batch_record_target = 4096;
static constexpr size_t batch_byte_target = 1024 * 1024;
static constexpr uint64_t periodic_flush_ns = 1000000000ull;
static constexpr size_t local_capacity = 4096;

#ifdef NEO_COMPUTE_TRACE_TESTING
static constexpr uint64_t module_max_output_bytes = 16 * 1024;
static constexpr uint64_t module_max_serialized_records = 24;
#else
static constexpr uint64_t module_max_output_bytes = 24ull * 1024ull * 1024ull;
static constexpr uint64_t module_max_serialized_records = 75000;
#endif

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
    const char * placement_reason = "unknown";
};

inline uint64_t monotonic_timestamp_ns() {
    return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}

template <size_t N>
inline void copy_text(char (&dst)[N], const char * src) {
    if (src == nullptr) {
        dst[0] = '\0';
        return;
    }
    std::strncpy(dst, src, N - 1);
    dst[N - 1] = '\0';
}

inline uint64_t hash_bytes(uint64_t value, const void * data, size_t size) {
    const auto * bytes = static_cast<const unsigned char *>(data);
    for (size_t i = 0; i < size; ++i) {
        value ^= bytes[i];
        value *= 1099511628211ull;
    }
    return value;
}

inline uint64_t hash_text(uint64_t value, const char * text) {
    return text == nullptr ? hash_bytes(value, "", 1) : hash_bytes(value, text, std::strlen(text) + 1);
}

struct aggregate_key {
    uint64_t hash = 0;
    int device_id = -1;
    int layer_index = -1;
    int expert_id = -1;
    int route_rank = -1;
    int mmq_tile_m = -1;
    int mmq_tile_n = -1;
    int mmq_tile_k = -1;
    char event_id[56] = {};
    char phase[24] = {};
    char operator_name[56] = {};
    char backend_expected[32] = {};
    char backend_actual[32] = {};
    char placement_reason[32] = {};
    char tensor_shape[80] = {};
    char cuda_stream[32] = {};
    char sync_kind[32] = {};
    char graph_id[40] = {};
    char graph_action[32] = {};
    char graph_shape_signature[96] = {};
    char recurrent_action[32] = {};
    char transfer_direction[24] = {};
};

inline aggregate_key make_key(const event & value) {
    aggregate_key key;
    key.device_id = value.device_id;
    key.layer_index = value.layer_index;
    key.expert_id = value.expert_id;
    key.route_rank = value.route_rank;
    key.mmq_tile_m = value.mmq_tile_m;
    key.mmq_tile_n = value.mmq_tile_n;
    key.mmq_tile_k = value.mmq_tile_k;
    copy_text(key.event_id, value.event_id);
    copy_text(key.phase, value.phase);
    copy_text(key.operator_name, value.operator_name);
    copy_text(key.backend_expected, value.backend_expected);
    copy_text(key.backend_actual, value.backend_actual);
    copy_text(key.placement_reason, value.placement_reason);
    copy_text(key.tensor_shape, value.tensor_shape);
    copy_text(key.cuda_stream, value.cuda_stream);
    copy_text(key.sync_kind, value.sync_kind);
    copy_text(key.graph_id, value.graph_id);
    copy_text(key.graph_action, value.graph_action);
    copy_text(key.graph_shape_signature, value.graph_shape_signature);
    copy_text(key.recurrent_action, value.recurrent_action);
    const char * direction = value.bytes_host_to_device != unknown_u64 ? "host_to_device" :
        value.bytes_device_to_host != unknown_u64 ? "device_to_host" :
        value.bytes_device_to_device != unknown_u64 ? "device_to_device" : "none";
    copy_text(key.transfer_direction, direction);

    uint64_t hash = 1469598103934665603ull;
    hash = hash_text(hash, key.event_id);
    hash = hash_text(hash, key.phase);
    hash = hash_text(hash, key.operator_name);
    hash = hash_text(hash, key.backend_expected);
    hash = hash_text(hash, key.backend_actual);
    hash = hash_text(hash, key.placement_reason);
    hash = hash_text(hash, key.tensor_shape);
    hash = hash_text(hash, key.cuda_stream);
    hash = hash_text(hash, key.sync_kind);
    hash = hash_text(hash, key.graph_id);
    hash = hash_text(hash, key.graph_action);
    hash = hash_text(hash, key.graph_shape_signature);
    hash = hash_text(hash, key.recurrent_action);
    hash = hash_text(hash, key.transfer_direction);
    hash = hash_bytes(hash, &key.device_id, sizeof(key.device_id));
    hash = hash_bytes(hash, &key.layer_index, sizeof(key.layer_index));
    hash = hash_bytes(hash, &key.expert_id, sizeof(key.expert_id));
    hash = hash_bytes(hash, &key.route_rank, sizeof(key.route_rank));
    hash = hash_bytes(hash, &key.mmq_tile_m, sizeof(key.mmq_tile_m));
    hash = hash_bytes(hash, &key.mmq_tile_n, sizeof(key.mmq_tile_n));
    hash = hash_bytes(hash, &key.mmq_tile_k, sizeof(key.mmq_tile_k));
    key.hash = hash;
    return key;
}

inline bool key_equal(const aggregate_key & lhs, const aggregate_key & rhs) {
    return lhs.hash == rhs.hash && lhs.device_id == rhs.device_id &&
        lhs.layer_index == rhs.layer_index && lhs.expert_id == rhs.expert_id &&
        lhs.route_rank == rhs.route_rank && lhs.mmq_tile_m == rhs.mmq_tile_m &&
        lhs.mmq_tile_n == rhs.mmq_tile_n && lhs.mmq_tile_k == rhs.mmq_tile_k &&
        std::strcmp(lhs.event_id, rhs.event_id) == 0 &&
        std::strcmp(lhs.phase, rhs.phase) == 0 &&
        std::strcmp(lhs.operator_name, rhs.operator_name) == 0 &&
        std::strcmp(lhs.backend_expected, rhs.backend_expected) == 0 &&
        std::strcmp(lhs.backend_actual, rhs.backend_actual) == 0 &&
        std::strcmp(lhs.placement_reason, rhs.placement_reason) == 0 &&
        std::strcmp(lhs.tensor_shape, rhs.tensor_shape) == 0 &&
        std::strcmp(lhs.cuda_stream, rhs.cuda_stream) == 0 &&
        std::strcmp(lhs.sync_kind, rhs.sync_kind) == 0 &&
        std::strcmp(lhs.graph_id, rhs.graph_id) == 0 &&
        std::strcmp(lhs.graph_action, rhs.graph_action) == 0 &&
        std::strcmp(lhs.graph_shape_signature, rhs.graph_shape_signature) == 0 &&
        std::strcmp(lhs.recurrent_action, rhs.recurrent_action) == 0 &&
        std::strcmp(lhs.transfer_direction, rhs.transfer_direction) == 0;
}

struct aggregate_slot {
    bool used = false;
    aggregate_key key;
    uint64_t count = 0;
    uint64_t first_timestamp_ns = 0;
    uint64_t last_timestamp_ns = 0;
    uint64_t first_sequence = 0;
    uint64_t last_sequence = 0;
    uint64_t duration_count = 0;
    uint64_t total_duration_ns = 0;
    uint64_t min_duration_ns = unknown_u64;
    uint64_t max_duration_ns = 0;
    uint64_t total_bytes = 0;
    uint64_t dropped_events = 0;
    int expert_bucket_tokens = -1;
    int expert_bucket_max = -1;
    uint64_t recurrent_state_bytes = unknown_u64;
    uint64_t recurrent_copy_bytes = unknown_u64;
};

inline void append_json_string(std::string & out, const char * value) {
    if (value == nullptr || value[0] == '\0') {
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
            default: out.push_back(static_cast<char>(ch)); break;
        }
    }
    out.push_back('"');
}

inline void append_key(std::string & out, const char * key) {
    if (out.size() > 1 && out.back() != '{') out.push_back(',');
    append_json_string(out, key);
    out.push_back(':');
}

inline void append_string(std::string & out, const char * key, const char * value) {
    append_key(out, key); append_json_string(out, value);
}

inline void append_u64(std::string & out, const char * key, uint64_t value) {
    append_key(out, key); out += std::to_string(value);
}

inline void append_int_or_null(std::string & out, const char * key, int value) {
    append_key(out, key); if (value < 0) out += "null"; else out += std::to_string(value);
}

struct writer_state {
    std::mutex mutex;
    FILE * file = nullptr;
    uint64_t writer_open_count = 0;
    uint64_t bytes_written = 0;
    uint64_t serialized_records = 0;
    uint64_t raw_event_count = 0;
    uint64_t aggregate_record_count = 0;
    uint64_t dropped_event_count = 0;
    bool trace_truncated = false;
    bool truncation_notice_written = false;
};

inline writer_state & writer() {
    static writer_state * state = new writer_state();
    return *state;
}

inline const char * request_id() {
    const char * value = std::getenv("NEO_COMPUTE_TRACE_REQUEST_ID");
    return value == nullptr || value[0] == '\0' ? "runtime-unscoped" : value;
}

inline bool ensure_open(writer_state & state) {
    if (state.file != nullptr) return true;
    const char * path = std::getenv("NEO_COMPUTE_TRACE_PATH");
    if (path == nullptr || path[0] == '\0') return false;
    state.file = std::fopen(path, "ab");
    if (state.file == nullptr) return false;
    state.writer_open_count++;
    return true;
}

inline std::string header_record(const writer_state & state) {
    std::string out = "{";
    append_u64(out, "schema_version", 2);
    append_string(out, "event_id", "neo.compute.trace.header.v2");
    append_string(out, "trace_mode", "diagnostic");
    append_string(out, "aggregation_mode", "thread_local_fixed_capacity_delta");
    append_u64(out, "max_output_bytes", session_max_output_bytes);
    append_u64(out, "max_serialized_records", session_max_serialized_records);
    append_u64(out, "batch_record_target", batch_record_target);
    append_u64(out, "batch_byte_target", batch_byte_target);
    append_u64(out, "periodic_flush_ns", periodic_flush_ns);
    append_key(out, "trace_truncated"); out += state.trace_truncated ? "true" : "false";
    append_u64(out, "dropped_event_count", state.dropped_event_count);
    append_u64(out, "raw_event_count", state.raw_event_count);
    append_u64(out, "aggregate_record_count", state.aggregate_record_count);
    append_u64(out, "writer_open_count", state.writer_open_count);
    out += "}\n";
    return out;
}

inline std::string aggregate_record(const aggregate_slot & slot) {
    std::string out = "{";
    append_u64(out, "schema_version", 2);
    append_string(out, "event_id", slot.key.event_id);
    append_string(out, "record_type", "aggregate_delta");
    append_string(out, "request_id", request_id());
    append_string(out, "phase", slot.key.phase);
    append_string(out, "operator", slot.key.operator_name);
    append_string(out, "backend_expected", slot.key.backend_expected);
    append_string(out, "backend_actual", slot.key.backend_actual);
    append_string(out, "placement_reason", slot.key.placement_reason);
    append_int_or_null(out, "device_id", slot.key.device_id);
    append_int_or_null(out, "layer_index", slot.key.layer_index);
    append_string(out, "tensor_shape", slot.key.tensor_shape);
    append_string(out, "cuda_stream", slot.key.cuda_stream);
    append_string(out, "sync_kind", slot.key.sync_kind);
    append_string(out, "graph_id", slot.key.graph_id);
    append_string(out, "graph_action", slot.key.graph_action);
    append_string(out, "graph_shape_signature", slot.key.graph_shape_signature);
    append_string(out, "transfer_direction", slot.key.transfer_direction);
    append_string(out, "recurrent_action", slot.key.recurrent_action);
    append_int_or_null(out, "expert_id", slot.key.expert_id);
    append_int_or_null(out, "route_rank", slot.key.route_rank);
    append_int_or_null(out, "mmq_tile_m", slot.key.mmq_tile_m);
    append_int_or_null(out, "mmq_tile_n", slot.key.mmq_tile_n);
    append_int_or_null(out, "mmq_tile_k", slot.key.mmq_tile_k);
    append_u64(out, "count", slot.count);
    append_u64(out, "first_timestamp_ns", slot.first_timestamp_ns);
    append_u64(out, "last_timestamp_ns", slot.last_timestamp_ns);
    append_u64(out, "first_sequence", slot.first_sequence);
    append_u64(out, "last_sequence", slot.last_sequence);
    append_u64(out, "duration_count", slot.duration_count);
    append_u64(out, "total_duration_ns", slot.total_duration_ns);
    append_key(out, "min_duration_ns");
    if (slot.min_duration_ns == unknown_u64) out += "null"; else out += std::to_string(slot.min_duration_ns);
    append_key(out, "max_duration_ns");
    if (slot.duration_count == 0) out += "null"; else out += std::to_string(slot.max_duration_ns);
    append_u64(out, "total_bytes", slot.total_bytes);
    append_u64(out, "dropped_events", slot.dropped_events);
    append_int_or_null(out, "expert_bucket_tokens", slot.expert_bucket_tokens);
    append_int_or_null(out, "expert_bucket_max", slot.expert_bucket_max);
    append_key(out, "recurrent_state_bytes");
    if (slot.recurrent_state_bytes == unknown_u64) out += "null"; else out += std::to_string(slot.recurrent_state_bytes);
    append_key(out, "recurrent_copy_bytes");
    if (slot.recurrent_copy_bytes == unknown_u64) out += "null"; else out += std::to_string(slot.recurrent_copy_bytes);
    append_key(out, "raw_sample_preserved"); out += "true";
    out += "}\n";
    return out;
}

inline void write_batch(aggregate_slot * slots, size_t used) {
    writer_state & state = writer();
    std::lock_guard<std::mutex> lock(state.mutex);
    if (!ensure_open(state)) {
        for (size_t i = 0; i < used; ++i) state.dropped_event_count += slots[i].count;
        state.trace_truncated = true;
        return;
    }

    std::string batch;
    batch.reserve(std::max(batch_byte_target, used * size_t(512)));
    uint64_t accepted_records = 0;
    uint64_t accepted_raw = 0;
    for (size_t i = 0; i < used; ++i) {
        std::string record = aggregate_record(slots[i]);
        const bool record_limit = state.serialized_records + accepted_records + 2 > module_max_serialized_records;
        const bool byte_limit = state.bytes_written + batch.size() + record.size() + 4096 > module_max_output_bytes;
        if (record_limit || byte_limit) {
            state.trace_truncated = true;
            state.dropped_event_count += slots[i].count;
            continue;
        }
        batch += record;
        accepted_records++;
        accepted_raw++;
    }
    state.serialized_records += accepted_records;
    state.aggregate_record_count += accepted_records;
    state.raw_event_count += accepted_raw;

    if (state.trace_truncated && !state.truncation_notice_written) {
        std::string notice = "{\"schema_version\":2,\"event_id\":\"neo.compute.trace.truncation.v2\",\"trace_truncated\":true,\"dropped_event_count\":" +
            std::to_string(state.dropped_event_count) + "}\n";
        if (state.bytes_written + batch.size() + notice.size() + 2048 <= module_max_output_bytes) {
            batch += notice;
            state.serialized_records++;
            state.truncation_notice_written = true;
        }
    }
    std::string summary = header_record(state);
    if (state.bytes_written + batch.size() + summary.size() <= module_max_output_bytes) {
        batch += summary;
        state.serialized_records++;
    }
    if (!batch.empty()) {
        std::fwrite(batch.data(), 1, batch.size(), state.file);
        std::fflush(state.file);
        state.bytes_written += batch.size();
    }
}

struct local_state {
    std::array<aggregate_slot, local_capacity> slots{};
    size_t used = 0;
    uint64_t last_flush_ns = 0;
    size_t estimated_bytes = 0;

    ~local_state() { flush(); }

    void flush() {
        if (used == 0) return;
        write_batch(slots.data(), used);
        for (size_t i = 0; i < used; ++i) slots[i] = aggregate_slot{};
        used = 0;
        estimated_bytes = 0;
        last_flush_ns = monotonic_timestamp_ns();
    }

    void add(const event & value, uint64_t timestamp_ns) {
        aggregate_key key = make_key(value);
        aggregate_slot * slot = nullptr;
        for (size_t i = 0; i < used; ++i) {
            if (key_equal(slots[i].key, key)) { slot = &slots[i]; break; }
        }
        if (slot == nullptr) {
            if (used == local_capacity) flush();
            slot = &slots[used++];
            slot->used = true;
            slot->key = key;
            slot->first_timestamp_ns = timestamp_ns;
            slot->first_sequence = timestamp_ns;
            slot->expert_bucket_tokens = value.expert_bucket_tokens;
            slot->expert_bucket_max = value.expert_bucket_max;
            slot->recurrent_state_bytes = value.recurrent_state_bytes;
            slot->recurrent_copy_bytes = value.recurrent_copy_bytes;
            estimated_bytes += sizeof(aggregate_slot);
        }
        slot->count++;
        slot->last_timestamp_ns = timestamp_ns;
        slot->last_sequence = timestamp_ns;
        if (value.duration_ns != unknown_u64) {
            slot->duration_count++;
            slot->total_duration_ns += value.duration_ns;
            slot->min_duration_ns = std::min(slot->min_duration_ns, value.duration_ns);
            slot->max_duration_ns = std::max(slot->max_duration_ns, value.duration_ns);
        }
        if (value.bytes_host_to_device != unknown_u64) slot->total_bytes += value.bytes_host_to_device;
        if (value.bytes_device_to_host != unknown_u64) slot->total_bytes += value.bytes_device_to_host;
        if (value.bytes_device_to_device != unknown_u64) slot->total_bytes += value.bytes_device_to_device;
        if (value.recurrent_copy_bytes != unknown_u64) slot->total_bytes += value.recurrent_copy_bytes;

        const bool periodic = last_flush_ns != 0 && timestamp_ns - last_flush_ns >= periodic_flush_ns;
        if (used >= batch_record_target || estimated_bytes >= batch_byte_target || periodic) flush();
        if (last_flush_ns == 0) last_flush_ns = timestamp_ns;
    }
};

inline local_state & local() {
    static thread_local local_state state;
    return state;
}

inline void emit(const event & value) {
    const char * path = std::getenv("NEO_COMPUTE_TRACE_PATH");
    if (path == nullptr || path[0] == '\0') return;
    local().add(value, monotonic_timestamp_ns());
}

#ifdef NEO_COMPUTE_TRACE_TESTING
inline void flush_for_test() { local().flush(); }
inline writer_state & stats_for_test() { return writer(); }
#endif

} // namespace neo_compute_trace

#define NEO_COMPUTE_TRACE_EMIT(value) ::neo_compute_trace::emit(value)

#else

#define NEO_COMPUTE_TRACE_EMIT(value) ((void) 0)

#endif
