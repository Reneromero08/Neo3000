from pathlib import Path

import pytest


SERVER_DIR = Path(__file__).resolve().parents[2]
CONTEXT = (SERVER_DIR / "server-context.cpp").read_text(encoding="utf-8")
TASK_H = (SERVER_DIR / "server-task.h").read_text(encoding="utf-8")
LLAMA_CONTEXT = (SERVER_DIR.parents[1] / "src" / "llama-context.cpp").read_text(encoding="utf-8")


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
    assert save.count("llama_state_seq_get_data_ext") == 2
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

    assert "slot_ram_root.reset()" not in restore
    assert "slot_ram_root.reset()" in erase
    assert "clear_ram_root_device_data(*slot_ram_root)" in erase
    assert "n_device_bytes_after != 0" in erase
    assert "n_gpu_bytes_after != 0" in erase
    assert "positions_ok" in restore
    assert "common_context_seq_rm" in restore
    assert '"Unable to erase the complete RAM-root device state"' in erase


def test_one_root_refuses_implicit_overwrite():
    save = _case("SERVER_TASK_TYPE_SLOT_ROOT_SAVE")

    assert "if (slot_ram_root)" in save
    assert "erase it before saving another root" in save
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
    assert '"n_device_bytes"' in (SERVER_DIR / "server-task.cpp").read_text(encoding="utf-8")
    assert '"n_gpu_bytes"' in (SERVER_DIR / "server-task.cpp").read_text(encoding="utf-8")
