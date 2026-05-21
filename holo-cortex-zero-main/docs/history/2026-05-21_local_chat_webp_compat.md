# 2026-05-21 local chat WEBP compatibility fix

## Problem

`qwen36-queen-27b-resident` failed through the local OpenAI-compatible
`chat.completions` endpoint:

- Group: `qwen36-queen-27b-resident`
- Model: `qwen36-queen-27b-mm-q4`
- Endpoint: `http://172.19.0.1:18081/v1/chat/completions`
- Error body from replay: `Failed to load image or audio file`

The exact dumped request was 672 KB, had 48 messages, and included 4 historical
user images. Single-image probes showed:

- image 0: `data:image/webp`, 504x495, 4654 decoded bytes -> HTTP 400
- image 1: JPEG -> HTTP 200
- image 2: JPEG -> HTTP 200
- image 3: PNG -> HTTP 200

Converting image 0 from WEBP to JPEG made the same local model return HTTP 200.

## Change

`OpenAIChatEmitter._normalize_image_bytes` now treats WEBP as a chat image
compatibility case in the existing normalization path:

- WEBP is decoded through Pillow and emitted as JPEG when opaque.
- WEBP with alpha/transparency is emitted as PNG.
- Existing `local_chat_image_max_long_edge` resizing is preserved in the same
  path.
- Logs now include a `reason` field such as `webp_compat`,
  `oversized`, or `oversized+webp_compat`.

No provider-specific branch was added. The protocol mainline remains the
existing chat image normalization function.

## Verification

- Function-level probe against the failed WEBP data URI returns
  `data:image/jpeg`.
- Replayed the previously failing dumped payload after normalizing through
  `OpenAIChatEmitter._build_payload`; the local llama.cpp endpoint returned
  HTTP 200 instead of HTTP 400.

## Rollback

Revert the commit that modifies:

- `holo_cortex_zero/services/llm/openai_chat.py`
- `docs/history/2026-05-21_local_chat_webp_compat.md`
