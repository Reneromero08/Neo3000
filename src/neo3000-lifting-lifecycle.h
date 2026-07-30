#pragma once

#include <cstdint>

namespace neo3000 {

template <typename State>
bool lifting_try_arm_capture(
        State & state,
        int32_t capture_kind,
        int32_t public_slot) {
    if (state.lifting_poisoned ||
        capture_kind < 1 ||
        capture_kind > 4 ||
        public_slot < 0 ||
        public_slot >= 4 ||
        state.lifting_capture_kind != 0 ||
        state.lifting_capture_slot != -1) {
        return false;
    }
    uint32_t * mask = nullptr;
    switch (capture_kind) {
        case 1: mask = &state.lifting_f_key_mask; break;
        case 2: mask = &state.lifting_f_value_mask; break;
        case 3: mask = &state.lifting_g_key_mask; break;
        case 4: mask = &state.lifting_g_value_mask; break;
        default: return false;
    }
    if ((*mask & (1u << public_slot)) != 0) {
        return false;
    }
    state.lifting_update_resident = true;
    state.lifting_capture_kind = capture_kind;
    state.lifting_capture_slot = public_slot;
    return true;
}

template <typename State>
bool lifting_mark_capture_complete(State & state) {
    uint32_t * mask = nullptr;
    switch (state.lifting_capture_kind) {
        case 1: mask = &state.lifting_f_key_mask; break;
        case 2: mask = &state.lifting_f_value_mask; break;
        case 3: mask = &state.lifting_g_key_mask; break;
        case 4: mask = &state.lifting_g_value_mask; break;
        default: return false;
    }
    if (state.lifting_capture_slot < 0 ||
        state.lifting_capture_slot >= 4 ||
        (*mask & (1u << state.lifting_capture_slot)) != 0) {
        return false;
    }
    *mask |= 1u << state.lifting_capture_slot;
    state.lifting_capture_kind = 0;
    state.lifting_capture_slot = -1;
    return true;
}

template <typename State>
void lifting_mark_poisoned(State & state) {
    state.enabled = false;
    state.lifting_poisoned = true;
    state.lifting_update_resident = false;
    state.lifting_capture_kind = 0;
    state.lifting_capture_slot = -1;
    state.lifting_f_key_mask = 0;
    state.lifting_f_value_mask = 0;
    state.lifting_g_key_mask = 0;
    state.lifting_g_value_mask = 0;
}

template <typename State>
bool lifting_can_begin_g_update(const State & state, uint32_t control) {
    return !state.lifting_poisoned &&
        !state.lifting_update_resident &&
        state.lifting_commits != 0 &&
        state.lifting_capture_kind == 0 &&
        state.lifting_capture_slot == -1 &&
        control == 0;
}

template <typename State>
void lifting_mark_g_update_started(State & state) {
    state.lifting_f_key_mask = 0x0fu;
    state.lifting_f_value_mask = 0x0fu;
    state.lifting_g_key_mask = 0;
    state.lifting_g_value_mask = 0;
    state.lifting_update_resident = true;
}

template <typename State>
bool lifting_can_commit(const State & state, uint32_t control) {
    return !state.lifting_poisoned &&
        state.lifting_update_resident &&
        state.lifting_capture_kind == 0 &&
        state.lifting_capture_slot == -1 &&
        state.lifting_f_key_mask == 0x0fu &&
        state.lifting_f_value_mask == 0x0fu &&
        state.lifting_g_key_mask == 0x0fu &&
        state.lifting_g_value_mask == 0x0fu &&
        control == 0;
}

template <typename State>
void lifting_mark_committed(State & state) {
    state.lifting_f_key_mask = 0;
    state.lifting_f_value_mask = 0;
    state.lifting_g_key_mask = 0;
    state.lifting_g_value_mask = 0;
    state.lifting_update_resident = false;
    ++state.lifting_commits;
}

template <typename State>
void lifting_mark_reset(State & state) {
    state.lifting_capture_kind = 0;
    state.lifting_capture_slot = -1;
    state.lifting_f_key_mask = 0;
    state.lifting_f_value_mask = 0;
    state.lifting_g_key_mask = 0;
    state.lifting_g_value_mask = 0;
    state.lifting_update_resident = false;
    state.lifting_poisoned = false;
    state.enabled = false;
}

} // namespace neo3000
