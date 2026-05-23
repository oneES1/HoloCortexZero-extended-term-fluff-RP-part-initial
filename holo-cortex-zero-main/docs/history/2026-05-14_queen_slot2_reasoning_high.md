# 2026-05-14 Queen slot2 reasoning high

## Scope

- Runtime config changed: `/path/to/runtime-data/configs/holo-cortex-zero.yaml`.
- HCZ container recreated with `--no-deps --force-recreate holo_cortex_zero`.
- Remote Queen llama.cpp service was not restarted in this step.
- Host reboot and FRP services were not touched.

## Change

The local model group `qwen36-queen-27b-resident-slot2` was switched from explicit non-thinking to thinking mode:

- `REASONING_MODE: high`
- Removed wire-level `thinking: {type: disabled}` from `EXTRA_BODY` to avoid contradicting the model-group reasoning mode.
- Kept slot and image controls:
  - `id_slot: 2`
  - `wire_api: chat`
  - `local_chat_image_max_long_edge: 1024`
  - `IMAGE_MAX_COUNT: 3`

Backup created:

- `/path/to/runtime-data/backups/configs/holo-cortex-zero.yaml.before_slot2_reasoning_on_20260514_215706`

## Verification

Host YAML parse confirms:

- `REASONING_MODE = high`
- `EXTRA_BODY = {"wire_api": "chat", "local_chat_image_max_long_edge": 1024, "id_slot": 2}`

After recreating the HCZ container:

- `holo_cortex_zero` health: healthy.
- Remote `meromero-gguf.service` remained active.
- Remote `/health`: `{"status":"ok"}`.
