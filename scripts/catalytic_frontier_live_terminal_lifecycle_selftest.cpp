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
        assert(lifecycle.cancellation_matches(20));
        lifecycle.poison();
        assert(lifecycle.state() == live_terminal_state::POISONED);
    }

    {
        live_terminal_lifecycle lifecycle;
        assert(lifecycle.begin_capture(3, 30));
        assert(lifecycle.complete_capture(30));
        assert(!lifecycle.admit_for_use(3));
        assert(lifecycle.admit_for_use(4));
        assert(lifecycle.admitted_for_use());
        assert(lifecycle.must_poison_on_release(31));
        lifecycle.poison();
        assert(lifecycle.state() == live_terminal_state::POISONED);
    }

    {
        live_terminal_lifecycle lifecycle;
        assert(lifecycle.begin_capture(4, 40));
        assert(lifecycle.complete_capture(40));
        assert(lifecycle.admit_for_use(5));
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
        assert(lifecycle.admit_for_use(9));
        lifecycle.poison(); // shutdown while consumer is resident
        assert(lifecycle.state() == live_terminal_state::POISONED);
        assert(!lifecycle.resident());
    }

    std::cout
            << "live terminal lifecycle behavioral selftest pass: "
            << "cancel-before-receipt, cancel-after-receipt, admitted-release, "
            << "close-and-recapture, sleep-resident, shutdown-resident\n";
    return 0;
}
