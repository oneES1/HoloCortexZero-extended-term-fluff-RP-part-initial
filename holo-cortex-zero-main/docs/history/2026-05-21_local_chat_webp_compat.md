# 2026-05-21 universal WEBP compatibility fix

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

## Initial Local Chat Change

The first repair treated WEBP as a local chat image compatibility case:

- WEBP is decoded through Pillow and emitted as JPEG when opaque.
- WEBP with alpha/transparency is emitted as PNG.
- Existing `local_chat_image_max_long_edge` resizing is preserved in the same
  path.
- Local chat resize logs keep the existing `reason=oversized` marker.

No provider-specific branch was added. The protocol mainline remains the
existing chat image normalization function.

## Follow-up Generalization

The WEBP normalization is now moved from `OpenAIChatEmitter` to the router media
preparation mainline so every model group and protocol gets the same behavior:

- Location: `LLMRouter._normalize_image_bytes_for_compat_target`
- Scope: all image parts after materialization, regardless of message role,
  model group, or wire protocol
- Output: `image/webp` is converted to `image/jpeg`
- Alpha handling: transparent WEBP is composited on a white background before
  JPEG encoding
- Existing branch compatibility remains separate: uni-grok GIF still converts
  to PNG only for that target

The chat emitter no longer carries a WEBP-specific branch. It only keeps its
existing oversized-image resize behavior.

## Verification

- Function-level probe against the failed WEBP data URI returns `image/jpeg`.
- Replayed the previously failing dumped payload through the router plus chat
  emitter; the local llama.cpp endpoint returned HTTP 200 instead of HTTP 400.
- Router-level probes confirmed `chat`, `responses`, and `gemini` protocols all
  receive `MessagePart(mime_type="image/jpeg")` before emitter serialization.

## Rollback

Revert the commit that modifies:

- `holo_cortex_zero/services/llm/openai_chat.py`
- `holo_cortex_zero/services/llm/router.py`
- `docs/history/2026-05-21_local_chat_webp_compat.md`
