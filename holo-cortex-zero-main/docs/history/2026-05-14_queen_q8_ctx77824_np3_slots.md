# 2026-05-14 Queen Q8 KV 77824 context with three slots

## Scope

- Target model host: hcz workstation user service `meromero-gguf.service`.
- Target HCZ runtime config: `/path/to/runtime-data/configs/holo-cortex-zero.yaml`.
- Host reboot: not performed.
- FRP/tunnel services: not touched.
- HCZ container recreated with `--no-deps --force-recreate holo_cortex_zero` only.

## Remote model service changes

Persistent service files updated:

- `/path/to/services/qwen35_stack/run/start_meromero_gguf.sh`
- `/path/to/systemd-user/meromero-gguf.service.d/10-runtime.conf`

Final runtime parameters verified from `/proc/<pid>/cmdline`:

- `-c 77824`
- `-np 3`
- `-b 384`
- `-ub 384`
- `--cache-prompt`
- `-cpent 512`
- `-ctk q8_0`
- `-ctv q8_0`
- `--mmproj /path/to/services/qwen35_stack/models-gguf/mmproj-Qwen3.6-Queen-27b-BF16.gguf`
- `--alias qwen36-queen-27b-mm-q4`

Interpretation:

- Total server context is `77824`.
- Server parallel slots are `3`.
- `/props` reports per-slot `n_ctx=26112` and `total_slots=3`.
- This is not `38912 * 3`; it is total `77824 / 3` rounded by llama.cpp slot allocation.

Observed GPU memory after launch:

- `19975 / 24576 MiB` used.

## HCZ model groups

Existing local groups remain:

- `qwen36-queen-27b-resident`: `id_slot=0`, images enabled with `local_chat_image_max_long_edge=1024`, `IMAGE_MAX_COUNT=3`.
- `qwen36-queen-27b-resident-think`: `id_slot=1`, `IMAGE_MAX_COUNT=0`, reasoning mode high at model-group level.

New local group added:

- `qwen36-queen-27b-resident-slot2`: same local endpoint/model as resident, `id_slot=2`, images enabled with `local_chat_image_max_long_edge=1024`, `IMAGE_MAX_COUNT=3`.

Runtime config backup:

- `/path/to/runtime-data/backups/configs/holo-cortex-zero.yaml.before_local_slot2_20260514_212727`

## Validation

Remote hcz model service:

- `/health`: `{"status":"ok"}`.
- `/props`: `total_slots=3`, per-slot `n_ctx=26112`.

HCZ container path to model service:

- Container `holo_cortex_zero` is healthy.
- From inside container, `http://<LOCAL_OPENAI_COMPAT_HOST>:18081/health` returns `{"status":"ok"}`.
- From inside container, `/props` reports `total_slots=3`.

Slot smoke tests from inside HCZ container:

| id_slot | status | prompt_tokens | cached_tokens | completion_tokens | elapsed |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 200 | 18 | 0 | 8 | 0.470s |
| 1 | 200 | 18 | 0 | 8 | 0.356s |
| 2 | 200 | 18 | 0 | 8 | 0.354s |

## Notes

- The previous manual kill-based recovery probe left the user service inactive because the signal resulted in a clean stop path rather than an on-failure restart. The service was explicitly restarted during this change.
- The systemd drop-in was updated because it previously pinned `MEROMERO_CTX=36352` and `MEROMERO_PARALLEL=2`, which would have overwritten the startup script defaults.
- Current production service is Q8 KV, not the temporary Q5_1 test state.
