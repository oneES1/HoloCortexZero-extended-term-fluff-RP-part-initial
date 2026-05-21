from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.config import save_config

from .embedding import cosine_similarity, embed_text
from .guidance import (
    GuidanceProfile,
    default_guidance_library_json,
    guidance_candidate_text,
    guidance_fingerprint,
    load_guidance_profiles,
)
from .policy import VoicePolicyDecision, evaluate_voice_policy
from .text import sanitize_voice_text, strip_bracket_content
from .transport import send_voice_message
from .tts_backend import synthesize_voice




@dataclass(frozen=True)
class VoiceDispatchResult:
    sent_as_voice: bool
    reason: str
    response: Optional[object] = None
    guidance_id: str = ""
    guidance_instruction: str = ""


class SystemVoiceService:
    def __init__(self) -> None:
        self._init_lock = asyncio.Lock()
        self._initialized = False
        self._guidance_cache_key: str = ""
        self._guidance_profiles: list[GuidanceProfile] = []
        self._guidance_embeddings: Dict[str, List[float]] = {}

    async def initialize_runtime(self) -> None:
        async with self._init_lock:
            if self._initialized:
                return
            self._ensure_guidance_seed()
            self._initialized = True
            logger.info("system_voice 运行时初始化完成")

    def _ensure_guidance_seed(self) -> None:
        if str(config.SYSTEM_VOICE_GUIDANCE_LIBRARY_JSON or "").strip():
            return
        config.SYSTEM_VOICE_GUIDANCE_LIBRARY_JSON = default_guidance_library_json()
        save_config()
        logger.info("system_voice guidance 种子已写入系统配置")

    async def _ensure_guidance_embeddings(self) -> list[GuidanceProfile]:
        profiles = load_guidance_profiles()
        fingerprint = guidance_fingerprint(profiles)
        if fingerprint == self._guidance_cache_key and self._guidance_profiles and self._guidance_embeddings:
            return self._guidance_profiles

        embeddings: Dict[str, List[float]] = {}
        for profile in profiles:
            candidate_text = guidance_candidate_text(profile)
            embeddings[profile.id] = await embed_text(candidate_text, model_group=str(config.SYSTEM_VOICE_EMBEDDING_MODEL_GROUP))

        self._guidance_cache_key = fingerprint
        self._guidance_profiles = profiles
        self._guidance_embeddings = embeddings
        logger.info(f"system_voice guidance 向量缓存已刷新: profiles={len(profiles)}")
        return profiles

    async def _select_guidance(self, text: str) -> GuidanceProfile:
        try:
            profiles = await self._ensure_guidance_embeddings()
            query_embedding = await embed_text(text, model_group=str(config.SYSTEM_VOICE_EMBEDDING_MODEL_GROUP))
            best_profile = profiles[0]
            best_score = -1.0
            for profile in profiles:
                score = cosine_similarity(query_embedding, self._guidance_embeddings.get(profile.id, []))
                if score > best_score:
                    best_profile = profile
                    best_score = score
            logger.info(
                "system_voice guidance 匹配完成: "
                f"guidance_id={best_profile.id} score={best_score:.4f}"
            )
            return best_profile
        except Exception as e:
            profiles = load_guidance_profiles()
            logger.warning(f"system_voice guidance 向量匹配失败，回退默认 guidance: {e}")
            return profiles[0]

    async def maybe_dispatch_reply(self, *, chat_key: str, text: str) -> VoiceDispatchResult:
        await self.initialize_runtime()

        normalized_text = sanitize_voice_text(text)
        policy: VoicePolicyDecision = evaluate_voice_policy(chat_key, normalized_text)
        logger.info(
            "system_voice policy checked: "
            f"chat={chat_key} adapter={policy.adapter_key} text_len={policy.text_len} "
            f"rng={policy.rng_value} reason={policy.reason}"
        )
        if not policy.should_voice:
            return VoiceDispatchResult(sent_as_voice=False, reason=policy.reason)

        tts_text = strip_bracket_content(normalized_text)
        if not tts_text:
            logger.info(f"system_voice bracket strip 结果为空，回退文本: chat={chat_key}")
            return VoiceDispatchResult(sent_as_voice=False, reason="empty_after_bracket_strip")

        guidance = await self._select_guidance(normalized_text)
        try:
            logger.info(
                "system_voice TTS started: "
                f"chat={chat_key} guidance_id={guidance.id} speech_rate={config.SYSTEM_VOICE_SPEECH_RATE} "
                f"pitch_rate={config.SYSTEM_VOICE_PITCH_RATE}"
            )
            tts_result = await synthesize_voice(
                tts_text,
                instruction=guidance.instruction,
                adapter_key=policy.adapter_key,
            )
            response = await send_voice_message(chat_key, tts_result.file_path)
            if not response.success:
                logger.warning(
                    f"system_voice 语音发送失败，将回退文本: chat={chat_key} err={response.error_message}"
                )
                return VoiceDispatchResult(sent_as_voice=False, reason="voice_send_failed", response=response)
            logger.info(
                "system_voice 语音发送成功: "
                f"chat={chat_key} guidance_id={guidance.id} instruction={tts_result.instruction} message_id={response.message_id}"
            )
            return VoiceDispatchResult(
                sent_as_voice=True,
                reason="voice_sent",
                response=response,
                guidance_id=guidance.id,
                guidance_instruction=tts_result.instruction,
            )
        except Exception as e:
            logger.error(f"system_voice 语音发送流程失败，将回退文本: chat={chat_key} err={e}", exc_info=True)
            return VoiceDispatchResult(sent_as_voice=False, reason="voice_pipeline_failed")


system_voice_service = SystemVoiceService()
