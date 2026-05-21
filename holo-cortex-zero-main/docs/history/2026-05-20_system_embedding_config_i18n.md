# System Embedding Config I18n

## Problem

Settings showed the system emoji and system voice vector configuration as LLM entries:

- `SYSTEM_EMOJI_EMBEDDING_MODEL_GROUP`: `系统表情向量LLM` / `System Emoji Embedding LLM`
- `SYSTEM_VOICE_EMBEDDING_MODEL_GROUP`: `系统语音向量LLM` / `System Voice Embedding LLM`

Both runtime paths call the embedding model group for vector similarity:

- `holo_cortex_zero/services/system_emoji.py` calls `embed_text(..., model_group=SYSTEM_EMOJI_EMBEDDING_MODEL_GROUP)`.
- `holo_cortex_zero/services/system_voice/service.py` calls `embed_text(..., model_group=SYSTEM_VOICE_EMBEDDING_MODEL_GROUP)`.

## Change

- Renamed the visible Chinese titles to `系统表情嵌入模型` and `系统语音嵌入模型`.
- Renamed the English titles to `System Emoji Embedding Model` and `System Voice Embedding Model`.
- Updated descriptions from `embedding LLM` to `embedding 模型` / `Embedding model`.
- Updated `scripts/fix_i18n.py` so future generated i18n metadata keeps the same wording.

## Impact

- Display text only.
- Config keys, stored values, model routing, and embedding runtime behavior are unchanged.

## Verification

- Compile `holo_cortex_zero/core/config.py`.
- Search confirms no remaining system emoji/system voice `Embedding LLM` display strings.
