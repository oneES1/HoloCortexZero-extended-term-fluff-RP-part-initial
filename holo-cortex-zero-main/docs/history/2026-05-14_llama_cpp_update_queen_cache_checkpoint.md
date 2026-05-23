# 2026-05-14 llama.cpp update and Queen multimodal cache validation

## Scope

- Target host: hcz workstation via `ssh -p <HCZ_SSH_PORT> ubuntu@<PUBLIC_SERVER_IP>`.
- Service touched: user service `meromero-gguf.service` only.
- Host reboot: not performed.
- FRP/tunnel service: not touched.
- HCZ application code: not changed in this step.

## Before update

- llama.cpp repo: `/path/to/services/llama_cpp/llama.cpp`.
- Runtime binary before update reported `version: 1 (07eaf91)`.
- Local llama.cpp HEAD before update: `b2ce4be fix(server): budget visible output separately from reasoning`.
- Local patch purpose: separate visible-output budget from hidden reasoning output.

## Backup and rollback point

- Backup branch: `backup/hcz-llama-before-update-20260514-114838`.
- Patch backup: `/path/to/services/llama_cpp/patches/hcz-reasoning-budget-20260514-114838.patch`.
- Old running binary copy: `/path/to/services/llama_cpp/bin-backups/llama-server-old-running-07eaf91-20260514-115338`.
- Rollback caveat: old binary alone failed after shared libraries were rebuilt; reliable rollback should checkout the backup branch and rebuild instead of replacing only `build/bin/llama-server`.

## Updated state

- Upstream base after fetch/rebase: `253ba110b webui: Move static build output from repo code to HF Bucket (#22937)`.
- Final local commit on hcz llama.cpp: `3452ae693 fix(server): budget visible output separately from reasoning`.
- Final binary version: `version: 114 (3452ae693)`.
- Build command: `cmake --build build --target llama-server -j $(nproc)`.
- Existing CUDA build flags observed during build: `GGML_CUDA=ON`, `GGML_CUDA_FA=ON`, `GGML_CUDA_GRAPHS=ON`.

## Runtime arguments verified

The running service command line contains:

- Model: `/path/to/services/qwen35_stack/models-gguf/Qwen3.6-Queen-27B-Q4_K.gguf`.
- Multimodal projector: `/path/to/services/qwen35_stack/models-gguf/mmproj-Qwen3.6-Queen-27b-BF16.gguf`.
- Alias: `qwen36-queen-27b-mm-q4`.
- Context and slots: `-c 36352`, `-np 2`.
- Batch: `-b 384`, `-ub 384`.
- Cache: `--cache-prompt`, `-cpent 512`.
- Reasoning: `--reasoning auto`, `--reasoning-format deepseek`.

## Regression found and fixed

After rebasing the local reasoning-budget patch, `max_tokens` no longer capped output for non-reasoning or disabled-thinking responses.

Observed failing behavior before the final fix:

- `max_tokens=16` returned `completion_tokens=292`.
- `max_tokens=32` returned `completion_tokens=292`.
- `max_tokens=64` returned `completion_tokens=292`.

Root cause:

- The local patch made `has_budget()` judge the response limit by visible decoded tokens.
- After upstream changes, visible decoded count was not available early enough when no hidden reasoning content existed.
- Result: the budget check could miss the hard output limit path.

Final fix in llama.cpp:

- Keep hard token-budget behavior when no parsed hidden reasoning exists.
- Switch to visible-output budget only after hidden reasoning content is present.
- This preserves the reasoning budget fix without breaking ordinary OpenAI-compatible `max_tokens` behavior.

## Validation after final rebuild

Health after restart:

- `systemctl --user restart meromero-gguf.service` completed.
- `/health` returned `{"status":"ok"}` after model load.

Output limit validation:

| request limit | status | completion_tokens | finish_reason | elapsed |
| --- | ---: | ---: | --- | ---: |
| 16 | 200 | 16 | length | 0.531s |
| 32 | 200 | 32 | length | 0.849s |
| 64 | 200 | 64 | length | 1.674s |

Text cache checkpoint validation:

| slot | tail | prompt_tokens | cached_tokens | elapsed |
| ---: | --- | ---: | ---: | ---: |
| 0 | A | 1103 | 0 | 1.117s |
| 0 | B | 1103 | 719 | 0.558s |
| 1 | B | 1103 | 0 | 1.116s |
| 0 | B | 1103 | 1099 | 0.242s |

Interpretation:

- Same slot with changed tail reused a real common prefix: `719/1103` cached tokens.
- Different slot did not reuse slot 0 cache: `0/1103` cached tokens.
- Same slot with identical payload reused almost all prompt tokens: `1099/1103` cached tokens.

Tool-call validation:

- Status: `200`.
- Finish reason: `tool_calls`.
- Returned OpenAI-compatible tool call:
  - Function: `record_memory`.
  - Arguments: `{"content":"post update tool ok"}`.
- Request used `tool_choice: "auto"`.

Multimodal validation:

- Service command line includes `--mmproj` with the Queen projector path.
- Direct image request using `/tmp/queen27_ocr_test.png` returned `status=200`.
- Multimodal smoke usage: `prompt_tokens=541`, `cached_tokens=0`, `completion_tokens=32`.
- Multimodal cache checkpoint validation with the same real PNG:

| slot | tail | prompt_tokens | cached_tokens | elapsed |
| ---: | --- | ---: | ---: | ---: |
| 0 | A | 549 | 0 | 0.871s |
| 0 | B | 549 | 0 | 0.865s |
| 1 | B | 549 | 0 | 0.862s |
| 0 | B | 549 | 545 | 0.248s |

Interpretation:

- Multimodal payload path is active and accepted by the updated server.
- No cross-slot cache contamination was observed.
- Exact repeated multimodal payload in the same slot hit the checkpoint cache: `545/549` cached tokens.
- The earlier invalid inline generated PNG probe returned `Failed to load image or audio file`; it was a bad test fixture, not a service multimodal failure.

## Result

The hcz Queen local backend is updated to the latest checked upstream base plus the rebased local reasoning-budget patch. The final server binary matches the final local commit, output limits work again, tool calls work, text cache checkpoint behavior works, and multimodal requests remain enabled with same-slot cache checkpoint reuse verified.
