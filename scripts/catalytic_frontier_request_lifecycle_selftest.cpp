#include "../tools/server/neo3000-request-lifecycle.h"

#include <array>
#include <cstdint>
#include <iostream>

int main() {
    // The consumed 0094 failure shape: the preceding useful consumer emitted
    // D, suffix-close, and EOS, leaving a completed count of three.
    int32_t current_request_decoded = 3;
    neo3000::begin_current_request_progress(current_request_decoded);

    // A zero-output capture can emit multiple progress receipts before its
    // empty final receipt. Every current-request prediction count must be zero.
    const std::array<int32_t, 3> capture_prediction_counts = {
        current_request_decoded,
        current_request_decoded,
        current_request_decoded,
    };
    for (const int32_t count : capture_prediction_counts) {
        if (count != 0) {
            std::cerr
                    << "request-lifecycle counter reset failed: "
                    << count
                    << '\n';
            return 1;
        }
    }

    std::cout
            << "neo-exp-0095 request-lifecycle selftest pass: "
            << "prior completion=3, current progress/final=0/0/0\n";
    return 0;
}
