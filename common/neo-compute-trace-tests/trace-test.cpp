#include "neo-compute-trace.h"

#include <cstdlib>
#include <string>

static neo_compute_trace::event make_event(const char * op, int layer, int device, const char * shape, const char * reason) {
    neo_compute_trace::event value {
        "neo.compute.test.v2", "test", op, "CUDA0", "CPU", device, 5, -1, layer, shape
    };
    value.bytes_host_to_device = 7;
    value.placement_reason = reason;
    return value;
}

int main(int argc, char ** argv) {
    if (argc != 3) return 2;
#ifdef _WIN32
    _putenv_s("NEO_COMPUTE_TRACE_PATH", argv[2]);
    _putenv_s("NEO_COMPUTE_TRACE_REQUEST_ID", argv[1]);
#else
    setenv("NEO_COMPUTE_TRACE_PATH", argv[2], 1);
    setenv("NEO_COMPUTE_TRACE_REQUEST_ID", argv[1], 1);
#endif

    const std::string mode = argv[1];
    if (mode == "aggregate") {
        for (int i = 0; i < 100; ++i) NEO_COMPUTE_TRACE_EMIT(make_event("MUL_MAT", 2, 0, "[8,8,1,1]", "scheduler_policy"));
    } else if (mode == "distinct") {
        NEO_COMPUTE_TRACE_EMIT(make_event("MUL_MAT", 1, 0, "[8,8,1,1]", "scheduler_policy"));
        NEO_COMPUTE_TRACE_EMIT(make_event("MUL_MAT", 2, 0, "[8,8,1,1]", "scheduler_policy"));
        NEO_COMPUTE_TRACE_EMIT(make_event("MUL_MAT", 2, 1, "[8,8,1,1]", "scheduler_policy"));
        NEO_COMPUTE_TRACE_EMIT(make_event("MUL_MAT", 2, 1, "[16,8,1,1]", "unknown"));
    } else if (mode == "batches") {
        for (int i = 0; i < 10; ++i) NEO_COMPUTE_TRACE_EMIT(make_event("ADD", 3, 0, "[8,1,1,1]", "scheduler_policy"));
        neo_compute_trace::flush_for_test();
        for (int i = 0; i < 15; ++i) NEO_COMPUTE_TRACE_EMIT(make_event("ADD", 3, 0, "[8,1,1,1]", "scheduler_policy"));
    } else if (mode == "limits") {
        for (int i = 0; i < 100; ++i) {
            std::string op = "OP_" + std::to_string(i);
            NEO_COMPUTE_TRACE_EMIT(make_event(op.c_str(), i, i % 2, "[8,8,1,1]", "unknown"));
        }
    } else if (mode == "unknown") {
        NEO_COMPUTE_TRACE_EMIT(make_event("VIEW", 4, 0, "[8,1,1,1]", "unknown"));
    } else {
        return 3;
    }

    neo_compute_trace::flush_for_test();
    return neo_compute_trace::stats_for_test().writer_open_count == 1 ? 0 : 4;
}
