#include "neo-compute-trace.h"

int main() {
    NEO_COMPUTE_TRACE_EMIT(this_symbol_must_not_be_parsed_in_normal_builds());
    return 0;
}
