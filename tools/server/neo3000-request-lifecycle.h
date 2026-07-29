#pragma once

#include <cstdint>

namespace neo3000 {

inline void begin_current_request_progress(int32_t & n_decoded) noexcept {
    n_decoded = 0;
}

} // namespace neo3000
