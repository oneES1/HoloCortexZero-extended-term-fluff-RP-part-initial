from __future__ import annotations

import random
from dataclasses import dataclass

from holo_cortex_zero.core import config

from .text import sanitize_voice_text


@dataclass(frozen=True)
class VoicePolicyDecision:
    should_voice: bool
    reason: str
    text_len: int
    adapter_key: str
    rng_value: float | None = None


def _resolve_adapter_key(chat_key: str) -> str:
    if "-" not in chat_key:
        return ""
    return chat_key.split("-", 1)[0].strip()


def evaluate_voice_policy(chat_key: str, text: str) -> VoicePolicyDecision:
    normalized = sanitize_voice_text(text)
    adapter_key = _resolve_adapter_key(chat_key)
    text_len = len(normalized)

    if not config.SYSTEM_VOICE_ENABLED:
        return VoicePolicyDecision(False, "disabled", text_len, adapter_key)
    if not normalized:
        return VoicePolicyDecision(False, "empty_text", text_len, adapter_key)
    if adapter_key not in set(config.SYSTEM_VOICE_ALLOWED_ADAPTERS or []):
        return VoicePolicyDecision(False, "adapter_not_allowed", text_len, adapter_key)
    if text_len >= int(config.SYSTEM_VOICE_SHORT_TEXT_MAX_LEN or 30):
        return VoicePolicyDecision(False, "text_too_long", text_len, adapter_key)

    probability = float(config.SYSTEM_VOICE_TRIGGER_PROBABILITY or 0.0)
    rng_value = random.random()
    if rng_value >= probability:
        return VoicePolicyDecision(False, "probability_miss", text_len, adapter_key, rng_value)

    return VoicePolicyDecision(True, "probability_hit", text_len, adapter_key, rng_value)
