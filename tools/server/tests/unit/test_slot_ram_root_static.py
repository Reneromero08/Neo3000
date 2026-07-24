from pathlib import Path

import pytest


SERVER_DIR = Path(__file__).resolve().parents[2]
CONTEXT = (SERVER_DIR / "server-context.cpp").read_text(encoding="utf-8")
TASK_H = (SERVER_DIR / "server-task.h").read_text(encoding="utf-8")
TASK_CPP = (SERVER_DIR / "server-task.cpp").read_text(encoding="utf-8")
LLAMA_CONTEXT = (SERVER_DIR.parents[1] / "src" / "llama-context.cpp").read_text(encoding="utf-8")
LLAMA_CONTEXT_H = (SERVER_DIR.parents[1] / "src" / "llama-context.h").read_text(encoding="utf-8")
LLAMA_H = (SERVER_DIR.parents[1] / "include" / "llama.h").read_text(encoding="utf-8")


@pytest.fixture(scope="module", autouse=True)
def do_something():
    """Override the server-wide fixture: these source-only tests must not launch a model."""
    yield


def _case(name: str) -> str:
    start = CONTEXT.index(f"case {name}:")
    end = CONTEXT.index("\n            case ", start + 1)
    return CONTEXT[start:end]


def test_ram_root_actions_are_explicit_and_cache_ram_gated():
    for action in ("root-save", "root-restore", "root-erase"):
        assert f'action == "{action}"' in CONTEXT
    assert "params.cache_ram_mib == 0" in CONTEXT
    assert "RAM-root slot actions require --cache-ram" in CONTEXT


def test_ram_root_uses_selectable_full_polymorphic_sequence_state():
    save = _case("SERVER_TASK_TYPE_SLOT_ROOT_SAVE")
    restore = _case("SERVER_TASK_TYPE_SLOT_ROOT_RESTORE")

    assert save.count("llama_state_seq_get_size_ext") == 2
    assert save.count("llama_state_seq_get_data_ext_keyed") == 2
    assert restore.count("llama_state_seq_set_data_ext") == 2
    assert "params_base.cache_ram_root_device" in save
    assert "LLAMA_STATE_SEQ_FLAGS_ON_DEVICE" in save
    assert save.count("root->state_flags") >= 5
    assert restore.count("slot_ram_root->state_flags") >= 2
    assert "PARTIAL_ONLY" not in save
    assert "seq_cp" in save and "not an exact RAM root" in save
    assert "Qwen35MoE is hybrid" in save
    assert "llama_state_seq_get_device_data_size" in save
    assert "llama_state_seq_get_device_data_gpu_size" in save
    assert "clear_ram_root_device_data(*root)" in save
    assert "ggml_backend_buft_is_host(buft)" in LLAMA_CONTEXT
    assert LLAMA_CONTEXT.index("ggml_backend_buft_is_host(buft)") < LLAMA_CONTEXT.index("ggml_backend_dev_type(dev)", LLAMA_CONTEXT.index("state_seq_get_device_data_gpu_size"))


def test_ram_root_preserves_prompt_checkpoints_and_speculative_state():
    save = _case("SERVER_TASK_TYPE_SLOT_ROOT_SAVE")
    restore = _case("SERVER_TASK_TYPE_SLOT_ROOT_RESTORE")

    assert "slot->prompt.clone()" in save
    assert "common_speculative_get_state" in save
    assert "slot_ram_root->prompt.clone()" in restore
    assert "common_speculative_set_state" in restore
    assert "slot->prompt = std::move(restored_prompt)" in restore
    assert "slot->prompt.checkpoints.size()" in restore


def test_restore_is_non_consuming_and_erase_is_explicit():
    restore = _case("SERVER_TASK_TYPE_SLOT_ROOT_RESTORE")
    erase = _case("SERVER_TASK_TYPE_SLOT_ROOT_ERASE")

    assert "slot_ram_roots.erase" not in restore
    assert "slot_ram_roots.erase(root_it)" in erase
    assert "clear_ram_root_device_data(*slot_ram_root)" in erase
    assert "n_device_bytes_after != 0" in erase
    assert "n_gpu_bytes_after != 0" in erase
    assert "positions_ok" in restore
    assert "common_context_seq_rm" in restore
    assert '"Unable to erase the complete RAM-root device state"' in erase


def test_keyed_device_capture_separates_source_sequence_from_storage():
    start = LLAMA_CONTEXT.index("size_t llama_context::state_seq_get_data_keyed(")
    end = LLAMA_CONTEXT.index("\nsize_t llama_context::state_seq_set_data(", start)
    keyed = LLAMA_CONTEXT[start:end]

    assert "mem_storage[state_storage_key]" in keyed
    assert "io->write(&state_storage_key, sizeof(state_storage_key))" in keyed
    assert "state_seq_write_data(*io, seq_id, flags)" in keyed
    assert "state_seq_get_data_keyed(seq_id, seq_id, dst, size, flags)" in LLAMA_CONTEXT
    assert "llama_state_seq_get_data_ext_keyed" in LLAMA_H
    assert "state_seq_get_data_keyed" in LLAMA_CONTEXT_H

    restore_start = LLAMA_CONTEXT.index("size_t llama_context::state_seq_set_data(")
    restore_end = LLAMA_CONTEXT.index(
        "\nsize_t llama_context::state_seq_get_device_data_size", restore_start
    )
    restore = LLAMA_CONTEXT[restore_start:restore_end]
    assert "mem_storage[device_storage_key]" in restore
    assert "state_seq_read_data(*io, seq_id, flags)" in restore


def test_five_root_bank_refuses_overwrite_and_allocates_distinct_storage_keys():
    save = _case("SERVER_TASK_TYPE_SLOT_ROOT_SAVE")

    assert "SERVER_SLOT_RAM_ROOT_CAPACITY = 5" in CONTEXT
    assert "find_ram_root(task.slot_action.root_id)" in save
    assert "erase it before saving a replacement" in save
    assert "slot_ram_roots.size() >= SERVER_SLOT_RAM_ROOT_CAPACITY" in save
    assert "RAM-root bank is at its fixed capacity" in save
    assert "find_available_ram_root_device_storage_key()" in save
    assert "root->device_storage_key == 0" in save
    assert "An on-device RAM root already owns this source slot" not in save
    assert "const llama_seq_id key = -1 -" in CONTEXT
    assert "root.device_storage_key == key" in CONTEXT
    assert "n_tgt == 0 && n_dft == 0" in CONTEXT
    assert "catch (...)" in save
    assert '"Unable to capture the complete slot state into the RAM root"' in save
    catch_start = save.index("catch (...)")
    catch_end = save.index("\n                    }", catch_start)
    assert "clear_ram_root_device_data(*root)" in save[catch_start:catch_end]
    assert "root_size > root_limit - current_root_size" in save
    assert "RAM-root bank exceeds the configured --cache-ram limit" in save
    for task_name in (
        "SERVER_TASK_TYPE_SLOT_ROOT_SAVE",
        "SERVER_TASK_TYPE_SLOT_ROOT_RESTORE",
        "SERVER_TASK_TYPE_SLOT_ROOT_ERASE",
    ):
        assert task_name in TASK_H


def test_ram_root_receipts_account_host_and_device_bytes():
    save = _case("SERVER_TASK_TYPE_SLOT_ROOT_SAVE")
    restore = _case("SERVER_TASK_TYPE_SLOT_ROOT_RESTORE")
    erase = _case("SERVER_TASK_TYPE_SLOT_ROOT_ERASE")

    for case in (save, restore, erase):
        assert "n_host_bytes" in case
        assert "n_device_bytes" in case
        assert "n_device_bytes_after" in case
        assert "n_gpu_bytes" in case
        assert "n_gpu_bytes_after" in case
        assert "device_storage_key" in case
        assert "set_ram_root_bank_receipt(*res)" in case
    assert "int device_storage_key = 0;" in TASK_H
    assert '"n_device_bytes"' in (SERVER_DIR / "server-task.cpp").read_text(encoding="utf-8")
    assert '"n_gpu_bytes"' in (SERVER_DIR / "server-task.cpp").read_text(encoding="utf-8")
    for key in (
        "device_storage_key",
        "n_roots_after",
        "n_roots_capacity",
        "n_total_bytes_after",
        "n_total_device_bytes_after",
        "n_total_gpu_bytes_after",
    ):
        assert f'"{key}"' in TASK_CPP


def test_five_root_bank_clears_each_device_snapshot_at_shutdown():
    destroy_start = CONTEXT.index("void destroy()")
    destroy_end = CONTEXT.index("\n    void handle_sleeping_state", destroy_start)
    destroy = CONTEXT[destroy_start:destroy_end]

    assert "for (const auto & [_, root] : slot_ram_roots)" in destroy
    assert "clear_ram_root_device_data(*root)" in destroy
    assert "slot_ram_roots.clear()" in destroy


def test_per_save_storage_and_live_aggregate_receipts_are_explicit():
    save = _case("SERVER_TASK_TYPE_SLOT_ROOT_SAVE")

    assert "task.slot_action.root_on_device < 0" in save
    assert "params_base.cache_ram_root_device" in save
    assert "LLAMA_STATE_SEQ_FLAGS_ON_DEVICE" in save
    assert 'storage != "default" && storage != "host" && storage != "device"' in CONTEXT
    assert "type != SERVER_TASK_TYPE_SLOT_ROOT_SAVE" in CONTEXT
    assert 'storage == "device" ? 1 : 0' in CONTEXT

    receipt_start = CONTEXT.index("void set_ram_root_bank_receipt")
    receipt_end = CONTEXT.index("\n    void destroy()", receipt_start)
    receipt = CONTEXT[receipt_start:receipt_end]
    assert "ram_roots_live_device_size()" in receipt
    assert "ram_roots_live_gpu_size()" in receipt
    assert "ram_roots_host_size() + n_device_bytes" in receipt

    live_device_start = CONTEXT.index("size_t ram_roots_live_device_size()")
    live_device_end = CONTEXT.index("\n    size_t ram_roots_live_gpu_size()", live_device_start)
    live_device = CONTEXT[live_device_start:live_device_end]
    assert "llama_state_seq_get_device_data_size(ctx_tgt, root->device_storage_key)" in live_device
