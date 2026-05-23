# 2026-05-14 Queen slot2 reasoning off

## Scope

- Runtime config changed: `/path/to/runtime-data/configs/holo-cortex-zero.yaml`.
- HCZ container recreated with `--no-deps --force-recreate holo_cortex_zero`.
- Remote Queen llama.cpp service was not restarted in this step.
- Host reboot and FRP services were not touched.

## Change

The local model group `qwen36-queen-27b-resident-slot2` was made explicitly non-thinking:

- `REASONING_MODE: 'off'`
- Existing wire extra body remains non-thinking:
  - `thinking: {type: disabled}`
  - `id_slot: 2`
  - `local_chat_image_max_long_edge: 1024`

Backup created:

- `/path/to/runtime-data/backups/configs/holo-cortex-zero.yaml.before_slot2_reasoning_off_20260514_214701`

## Verification

After recreating the HCZ container, the running config inside the container at `<CONTAINER_DATA_DIR>/configs/holo-cortex-zero.yaml` shows:

- `qwen36-queen-27b-resident-slot2.REASONING_MODE = 'off'`
- `qwen36-queen-27b-resident-slot2.EXTRA_BODY` still contains `"thinking": {"type": "disabled"}` and `"id_slot": 2`.

Container status:

- `holo_cortex_zero` health: healthy.
