#pragma once

#include <cstdint>

namespace neo3000 {

// This state machine is intentionally independent of llama/model objects so
// cancellation, release, sleep, and shutdown behavior can be executed in a
// small behavioral test.
enum class live_terminal_state : uint8_t {
    EMPTY,
    CAPTURING,
    CAPTURED_RESIDENT,
    ADMITTED_FOR_USE,
    CLOSED,
    POISONED,
};

class live_terminal_lifecycle {
public:
    bool begin_capture(uint64_t request_epoch, int capture_task_id) {
        if (request_epoch == 0 || capture_task_id < 0 || resident()) {
            return false;
        }
        capture_request_epoch_ = request_epoch;
        capture_task_id_ = capture_task_id;
        state_ = live_terminal_state::CAPTURING;
        return true;
    }

    bool complete_capture(int capture_task_id) {
        if (state_ != live_terminal_state::CAPTURING ||
                capture_task_id != capture_task_id_) {
            return false;
        }
        state_ = live_terminal_state::CAPTURED_RESIDENT;
        return true;
    }

    bool admit_for_use(uint64_t consumer_request_epoch) {
        if (state_ != live_terminal_state::CAPTURED_RESIDENT ||
                consumer_request_epoch != capture_request_epoch_ + 1) {
            return false;
        }
        state_ = live_terminal_state::ADMITTED_FOR_USE;
        return true;
    }

    bool cancellation_matches(int task_id) const {
        return resident() && task_id == capture_task_id_;
    }

    bool preserve_on_release(int releasing_task_id) const {
        return
                state_ == live_terminal_state::CAPTURED_RESIDENT &&
                releasing_task_id == capture_task_id_;
    }

    bool must_poison_on_release(int releasing_task_id) const {
        return resident() && !preserve_on_release(releasing_task_id);
    }

    void close() {
        state_ = live_terminal_state::CLOSED;
    }

    void poison() {
        if (resident()) {
            state_ = live_terminal_state::POISONED;
        }
    }

    bool resident() const {
        return
                state_ == live_terminal_state::CAPTURING ||
                state_ == live_terminal_state::CAPTURED_RESIDENT ||
                state_ == live_terminal_state::ADMITTED_FOR_USE;
    }

    bool ready_for_consumer() const {
        return state_ == live_terminal_state::CAPTURED_RESIDENT;
    }

    bool admitted_for_use() const {
        return state_ == live_terminal_state::ADMITTED_FOR_USE;
    }

    live_terminal_state state() const {
        return state_;
    }

    uint64_t capture_request_epoch() const {
        return capture_request_epoch_;
    }

    int capture_task_id() const {
        return capture_task_id_;
    }

private:
    live_terminal_state state_ = live_terminal_state::EMPTY;
    uint64_t capture_request_epoch_ = 0;
    int capture_task_id_ = -1;
};

} // namespace neo3000
