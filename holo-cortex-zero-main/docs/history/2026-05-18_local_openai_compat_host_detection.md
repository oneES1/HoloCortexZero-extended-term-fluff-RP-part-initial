# 2026-05-18 Local OpenAI-compatible host detection

## Problem

Local Queen/Qwen chat groups use `BASE_URL=http://<LOCAL_OPENAI_COMPAT_HOST>:<LOCAL_OPENAI_COMPAT_PORT>/v1` from the HCZ container to the host-side local model tunnel.

After the runtime network cleanup, `openai_chat._is_local_vllm_chat_target()` only recognized `127.0.0.1` and `localhost` on port `<LOCAL_OPENAI_COMPAT_PORT>`. As a result, `thinking: {"type": "disabled"}` was not rewritten to the llama.cpp chat-compatible `chat_template_kwargs.enable_thinking=false` for the real runtime URL.

Reproduction against the local model endpoint:

- Payload with only `thinking.disabled`: `reasoning_len=232`, `content=''`, `completion_tokens=80`.
- Payload with `chat_template_kwargs.enable_thinking=false`: `reasoning_len=0`, `content='323'`, `completion_tokens=4`.

## Change

- Treat local OpenAI-compatible targets by local host identity instead of fixed port identity.
- Recognized local hosts now include:
  - `127.0.0.1`
  - `::1`
  - `localhost`
  - `host.docker.internal`
  - `<HOST_GATEWAY_IP>`
- Apply the same host-based local detection to chat.completions and `/responses`.

## Files

- `holo_cortex_zero/services/llm/openai_chat.py`
- `holo_cortex_zero/services/llm/responses.py`

## Validation

- `python3 -m py_compile holo_cortex_zero/services/llm/openai_chat.py holo_cortex_zero/services/llm/responses.py`

## Rollback

Revert this commit to restore the previous port-bound local target detection.
