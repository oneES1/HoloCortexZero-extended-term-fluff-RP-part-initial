from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable, List

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger


SAFE_FALLBACK_INSTRUCTION = "我想体验一下自然的语气。"
ALLOWED_INSTRUCTIONS = {
    "请非常生气地说一句话。",
    "请非常开心地说一句话。",
    "请非常恐惧地说一句话。",
    "请非常伤心地说一句话。",
    "请非常惊讶地说一句话。",
    "请尽可能表现出坚定的感觉。",
    "请尽可能表现出愤怒的感觉。",
    "请尝试一下亲和的语调。",
    "请用冷酷的语调讲话。",
    "请用威严的语调讲话。",
    "我想体验一下自然的语气。",
    "我想看看你如何表达威胁。",
    "我想看看你怎么表现智慧。",
    "我想看看你怎么表现诱惑。",
    "我想听听用活泼的方式说话。",
    "我想听听你用激昂的感觉说话。",
    "我想听听用沉稳的方式说话的样子。",
    "我想听听你用自信的感觉说话。",
    "你能用兴奋的感觉和我交流吗？",
    "你能否展示狂傲的情绪表达？",
    "你能展现一下优雅的情绪吗？",
    "你可以用幸福的方式回答问题吗？",
    "你可以做一个温柔的情感演示吗？",
    "能用冷静的语调和我谈谈吗？",
    "能用深沉的方法回答我吗？",
    "能用粗犷的情绪态度和我对话吗？",
    "用阴森的声音告诉我这个答案。",
    "用坚韧的声音告诉我这个答案。",
    "用自然亲切的闲聊风格叙述。",
    "用广播剧博客主的语气讲话。",
}


@dataclass(frozen=True)
class GuidanceProfile:
    id: str
    name: str
    instruction: str
    tags: tuple[str, ...]
    scene_hint: str
    enabled: bool = True


DEFAULT_GUIDANCE_PROFILES: list[GuidanceProfile] = [
    GuidanceProfile("seductive", "诱惑", "我想看看你怎么表现诱惑。", ("暧昧", "诱惑", "心动", "撩"), "暧昧 贴近 轻柔 短句"),
    GuidanceProfile("gentle", "温柔", "你可以做一个温柔的情感演示吗？", ("温柔", "陪伴", "安抚", "哄睡"), "安抚 陪伴 晚安 软语"),
    GuidanceProfile("happy", "开心", "请非常开心地说一句话。", ("开心", "高兴", "幸福", "雀跃"), "轻快 愉悦 分享好消息"),
    GuidanceProfile("sad", "伤心", "请非常伤心地说一句话。", ("伤心", "难过", "委屈", "低落"), "安静 低落 情绪表达"),
    GuidanceProfile("angry", "生气", "请非常生气地说一句话。", ("生气", "愤怒", "不满"), "短促 强烈 情绪"),
    GuidanceProfile("surprised", "惊讶", "请非常惊讶地说一句话。", ("惊讶", "震惊", "意外"), "突然 讶异 反应"),
    GuidanceProfile("fear", "恐惧", "请非常恐惧地说一句话。", ("恐惧", "害怕", "发抖"), "不安 害怕 紧张"),
    GuidanceProfile("cold", "冷酷", "请用冷酷的语调讲话。", ("冷酷", "冷淡", "高冷"), "克制 冷淡 距离感"),
    GuidanceProfile("majestic", "威严", "请用威严的语调讲话。", ("威严", "庄重", "压迫感"), "稳重 权威 庄严"),
    GuidanceProfile("firm", "坚定", "请尽可能表现出坚定的感觉。", ("坚定", "坚决", "笃定"), "干脆 明确 表态"),
    GuidanceProfile("lively", "活泼", "我想听听用活泼的方式说话。", ("活泼", "元气", "俏皮"), "轻快 跳跃 可爱"),
    GuidanceProfile("passionate", "激昂", "我想听听你用激昂的感觉说话。", ("激昂", "热血", "冲劲"), "鼓动 热烈 强烈"),
    GuidanceProfile("calm", "沉稳", "我想听听用沉稳的方式说话的样子。", ("沉稳", "稳重", "平静"), "平稳 冷静 低起伏"),
    GuidanceProfile("confident", "自信", "我想听听你用自信的感觉说话。", ("自信", "笃定", "从容"), "从容 自信 有把握"),
    GuidanceProfile("natural", "自然", "我想体验一下自然的语气。", ("自然", "日常", "闲聊"), "普通 对话 自然 短句"),
]


def default_guidance_library_json() -> str:
    return json.dumps([asdict(profile) for profile in DEFAULT_GUIDANCE_PROFILES], ensure_ascii=False, indent=2)


def _normalize_tags(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",") if item.strip()]
        return tuple(items)
    if isinstance(value, Iterable):
        normalized = [str(item).strip() for item in value if str(item).strip()]
        return tuple(normalized)
    return ()


def normalize_instruction(instruction: str, *, source: str) -> str:
    candidate = str(instruction or "").strip()
    if candidate in ALLOWED_INSTRUCTIONS:
        return candidate
    if candidate:
        logger.warning(
            f"system_voice guidance instruction 非法，已回退安全句式: source={source} instruction={candidate}"
        )
    return SAFE_FALLBACK_INSTRUCTION


def load_guidance_profiles(raw_json: str | None = None) -> List[GuidanceProfile]:
    payload = str(raw_json if raw_json is not None else config.SYSTEM_VOICE_GUIDANCE_LIBRARY_JSON or "").strip()
    if not payload:
        return list(DEFAULT_GUIDANCE_PROFILES)

    try:
        parsed = json.loads(payload)
    except Exception as e:
        logger.warning(f"system_voice guidance JSON 解析失败，回退默认种子: {e}")
        return list(DEFAULT_GUIDANCE_PROFILES)

    if not isinstance(parsed, list):
        logger.warning("system_voice guidance JSON 不是列表，回退默认种子")
        return list(DEFAULT_GUIDANCE_PROFILES)

    profiles: list[GuidanceProfile] = []
    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            logger.warning(f"system_voice guidance 第 {index} 项不是对象，已跳过")
            continue

        identifier = str(item.get("id") or f"guidance_{index}").strip() or f"guidance_{index}"
        name = str(item.get("name") or identifier).strip() or identifier
        scene_hint = str(item.get("scene_hint") or "").strip()
        enabled = bool(item.get("enabled", True))
        profiles.append(
            GuidanceProfile(
                id=identifier,
                name=name,
                instruction=normalize_instruction(str(item.get("instruction") or ""), source=identifier),
                tags=_normalize_tags(item.get("tags") or ()),
                scene_hint=scene_hint,
                enabled=enabled,
            )
        )

    enabled_profiles = [profile for profile in profiles if profile.enabled]
    if enabled_profiles:
        return enabled_profiles

    logger.warning("system_voice guidance 全部被禁用，回退默认种子")
    return list(DEFAULT_GUIDANCE_PROFILES)


def guidance_candidate_text(profile: GuidanceProfile) -> str:
    tag_text = " ".join(profile.tags)
    return " ".join(part for part in (profile.name, tag_text, profile.scene_hint, profile.instruction) if part).strip()


def guidance_fingerprint(profiles: list[GuidanceProfile]) -> str:
    payload = json.dumps([asdict(profile) for profile in profiles], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
