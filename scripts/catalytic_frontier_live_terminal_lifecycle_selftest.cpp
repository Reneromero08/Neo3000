#include "../tools/server/neo3000-live-terminal-lifecycle.h"

#ifdef NDEBUG
#error "live terminal lifecycle selftest requires C++ assertions enabled"
#endif

#include <cassert>
#include <iostream>

using neo3000::live_terminal_lifecycle;
using neo3000::live_terminal_state;

int main() {
    {
        live_terminal_lifecycle lifecycle;
        assert(lifecycle.begin_capture(1, 10));
        assert(lifecycle.state() == live_terminal_state::CAPTURING);
        assert(lifecycle.capture_cancellation_matches(10));
        assert(lifecycle.must_poison_on_release(10));
        lifecycle.poison();
        assert(lifecycle.state() == live_terminal_state::POISONED);
    }

    {
        live_terminal_lifecycle lifecycle;
        assert(lifecycle.begin_capture(2, 20));
        assert(lifecycle.complete_capture(20));
        assert(lifecycle.ready_for_consumer());
        assert(lifecycle.preserve_on_release(20));
        assert(!lifecycle.must_poison_on_release(20));
        assert(lifecycle.capture_cancellation_matches(20));
        lifecycle.poison();
        assert(lifecycle.state() == live_terminal_state::POISONED);
    }

    {
        live_terminal_lifecycle lifecycle;
        assert(lifecycle.begin_capture(3, 30));
        assert(lifecycle.complete_capture(30));
        assert(!lifecycle.admit_for_use(3, 31));
        lifecycle.poison(); // malformed immediate consumer
        assert(lifecycle.state() == live_terminal_state::POISONED);
    }

    {
        live_terminal_lifecycle lifecycle;
        assert(lifecycle.begin_capture(3, 30));
        assert(lifecycle.complete_capture(30));
        assert(lifecycle.admit_for_use(4, 31));
        assert(lifecycle.admitted_for_use());
        assert(!lifecycle.capture_cancellation_matches(30));
        assert(lifecycle.consumer_owns_custody(31));
        assert(lifecycle.must_poison_on_release(31));
        lifecycle.poison(); // decode exception after admission
        assert(lifecycle.state() == live_terminal_state::POISONED);
    }

    {
        live_terminal_lifecycle lifecycle;
        assert(lifecycle.begin_capture(4, 40));
        assert(lifecycle.complete_capture(40));
        assert(lifecycle.admit_for_use(5, 41));
        lifecycle.close();
        assert(lifecycle.state() == live_terminal_state::CLOSED);
        assert(!lifecycle.resident());
        assert(lifecycle.begin_capture(6, 41));
    }

    {
        live_terminal_lifecycle lifecycle;
        assert(lifecycle.begin_capture(7, 50));
        assert(lifecycle.complete_capture(50));
        lifecycle.poison(); // sleep while capture is resident
        assert(lifecycle.state() == live_terminal_state::POISONED);
        assert(!lifecycle.resident());
    }

    {
        live_terminal_lifecycle lifecycle;
        assert(lifecycle.begin_capture(8, 60));
        assert(lifecycle.complete_capture(60));
        assert(lifecycle.admit_for_use(9, 61));
        lifecycle.poison(); // shutdown while consumer is resident
        assert(lifecycle.state() == live_terminal_state::POISONED);
        assert(!lifecycle.resident());
    }

    {
        constexpr int capture_task = 70;
        constexpr int consumer_task = 71;
        live_terminal_lifecycle lifecycle;
        assert(lifecycle.begin_capture(10, capture_task));
        assert(lifecycle.capture_cancellation_matches(capture_task));
        assert(lifecycle.complete_capture(capture_task));
        assert(lifecycle.state() ==
                live_terminal_state::CAPTURED_RESIDENT);
        assert(lifecycle.preserve_on_release(capture_task));
        assert(lifecycle.capture_cancellation_matches(capture_task));
        assert(lifecycle.admit_for_use(11, consumer_task));
        assert(lifecycle.state() ==
                live_terminal_state::ADMITTED_FOR_USE);
        assert(!lifecycle.capture_cancellation_matches(capture_task));
        assert(lifecycle.consumer_task_id() == consumer_task);
        assert(lifecycle.consumer_owns_custody(consumer_task));
        assert(!lifecycle.consumer_owns_custody(capture_task));
        assert(lifecycle.must_poison_on_release(consumer_task));
        lifecycle.poison(); // normal consumer cancellation releases custody
        assert(lifecycle.state() == live_terminal_state::POISONED);
        assert(!lifecycle.resident());
        assert(!lifecycle.capture_cancellation_matches(capture_task));
        assert(!lifecycle.consumer_owns_custody(consumer_task));
    }

    std::cout
            << "live terminal lifecycle behavioral selftest pass: "
            << "cancel-before-receipt, cancel-after-receipt, admitted-release, "
            << "malformed-immediate-consumer, decode-exception, "
            << "close-and-recapture, sleep-resident, shutdown-resident, "
            << "late-capture-cancel-does-not-steal-admitted-consumer\n";
    return 0;
}
