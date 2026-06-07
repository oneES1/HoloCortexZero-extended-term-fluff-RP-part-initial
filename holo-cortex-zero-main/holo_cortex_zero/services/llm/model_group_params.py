from __future__ import annotations

import json
from typing import Any, Dict

from holo_cortex_zero.core.logger import logger


MODEL_GROUP_IMAGE_MAX_COUNT_EXTRA_KEY = "__hcz_image_max_count"
MODEL_GROUP_CACHE_TRANSPORT_PROFILE_EXTRA_KEY = "__hcz_cache_transport_profile"
MODEL_GROUP_IMAGE_MAX_LONG_EDGE_EXTRA_KEY = "__hcz_image_max_long_edge"
MODEL_GROUP_REPLAY_REASONING_CONTENT_EXTRA_KEY = "replay_reasoning_content"


def parse_model_group_extra_body(raw_extra: Any, *, source_hint: str) -> Dict[str, Any]:
    if raw_extra is None:
        return {}
    if isinstance(raw_extra, dict):
        return dict(raw_extra)
    if isinstance(raw_extra, str):
        text = raw_extra.strip()
        if not text:
            return {}
        try:
            payload = json.loads(text)
        except Exception as exc:
            truncated_body = text[:100] + "..." if len(text) > 100 else text
            logger.error(f"解析模型组 EXTRA_BODY 失败 ({source_hint}): {exc} | Original: {truncated_body}")
            return {}
        if isinstance(payload, dict):
            logger.info(
                "模型组 EXTRA_BODY 已解析: "
                f"source={source_hint}, keys={sorted(payload.keys())}"
            )
            return dict(payload)
        logger.warning(
            "模型组 EXTRA_BODY 不是 JSON object，已忽略: "
            f"source={source_hint} | type={type(payload).__name__}"
        )
    return {}


def build_model_group_extra_params(model_group: Any, *, source_hint: str) -> Dict[str, Any]:
    """构建模型组通用额外参数。

    主干说明：
    - GUI 字段优先于 EXTRA_BODY。
    - EXTRA_BODY 仅作为低优先级兼容扩展入口。
    - 所有辅助 LLM 与主 LLM 统一复用同一套模型组参数主干，避免分叉。
    """
    extra_params = parse_model_group_extra_body(
        getattr(model_group, "EXTRA_BODY", None),
        source_hint=source_hint,
    )
    applied_fields: list[str] = []

    max_output_tokens = getattr(model_group, "MAX_OUTPUT_TOKENS", None)
    if max_output_tokens is not None:
        extra_params["max_output_tokens"] = int(max_output_tokens)
        applied_fields.append(f"MAX_OUTPUT_TOKENS={int(max_output_tokens)}")

    image_max_count = getattr(model_group, "IMAGE_MAX_COUNT", None)
    if image_max_count is not None:
        parsed_image_max_count = max(int(image_max_count), 0)
        extra_params[MODEL_GROUP_IMAGE_MAX_COUNT_EXTRA_KEY] = parsed_image_max_count
        applied_fields.append(f"IMAGE_MAX_COUNT={parsed_image_max_count}")

    cache_transport_profile = str(getattr(model_group, "CACHE_TRANSPORT_PROFILE", "default") or "default").strip().lower()
    if cache_transport_profile:
        extra_params[MODEL_GROUP_CACHE_TRANSPORT_PROFILE_EXTRA_KEY] = cache_transport_profile
        applied_fields.append(f"CACHE_TRANSPORT_PROFILE={cache_transport_profile}")

    reasoning_mode = str(getattr(model_group, "REASONING_MODE", "default") or "default").strip().lower()
    if reasoning_mode == "off":
        extra_params["thinking"] = {"type": "disabled"}
        extra_params.pop("reasoning", None)
        applied_fields.append("REASONING_MODE=off")
    elif reasoning_mode in {"minimal", "low", "medium", "high"}:
        reasoning = dict(extra_params.get("reasoning") or {}) if isinstance(extra_params.get("reasoning"), dict) else {}
        reasoning["effort"] = reasoning_mode
        extra_params["reasoning"] = reasoning
        extra_params.pop("thinking", None)
        applied_fields.append(f"REASONING_MODE={reasoning_mode}")
    else:
        reasoning_effort = str(getattr(model_group, "REASONING_EFFORT", "") or "").strip().lower()
        if reasoning_effort:
            reasoning = dict(extra_params.get("reasoning") or {}) if isinstance(extra_params.get("reasoning"), dict) else {}
            reasoning["effort"] = reasoning_effort
            extra_params["reasoning"] = reasoning
            applied_fields.append(f"REASONING_EFFORT={reasoning_effort}")

    text_verbosity = str(getattr(model_group, "TEXT_VERBOSITY", "default") or "default").strip().lower()
    if text_verbosity in {"low", "medium", "high"}:
        text = dict(extra_params.get("text") or {}) if isinstance(extra_params.get("text"), dict) else {}
        text["verbosity"] = text_verbosity
        extra_params["text"] = text
        applied_fields.append(f"TEXT_VERBOSITY={text_verbosity}")

    replay_reasoning_content = bool(getattr(model_group, "REPLAY_REASONING_CONTENT", False))
    if replay_reasoning_content:
        extra_params[MODEL_GROUP_REPLAY_REASONING_CONTENT_EXTRA_KEY] = True
        applied_fields.append("REPLAY_REASONING_CONTENT=true")
    else:
        if MODEL_GROUP_REPLAY_REASONING_CONTENT_EXTRA_KEY in extra_params:
            extra_params.pop(MODEL_GROUP_REPLAY_REASONING_CONTENT_EXTRA_KEY, None)
            applied_fields.append("drop:REPLAY_REASONING_CONTENT=false")

    if applied_fields:
        logger.info(
            "模型组 GUI 调参已注入通用 extra_params: "
            f"source={source_hint}, applied={applied_fields}, keys={sorted(extra_params.keys())}"
        )

    return extra_params
