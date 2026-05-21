from __future__ import annotations

import json
import math
from typing import List, Optional

import httpx

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.proxy_utils import resolve_model_group_proxy


def _build_embeddings_url(base_url: str) -> str:
    normalized = str(base_url or "").rstrip("/")
    if normalized.endswith("/embeddings"):
        return normalized
    return f"{normalized}/embeddings"


async def embed_text(text: str, *, model_group: str) -> List[float]:
    group = config.get_model_group_info(model_group)
    base_url = str(group.BASE_URL or "").strip()
    model = str(group.CHAT_MODEL or "").strip()
    if not base_url or not model:
        raise RuntimeError(f"system_voice embedding 模型组配置不完整: {model_group}")

    proxy_url = resolve_model_group_proxy(group, group_key=model_group, source="system_voice.embedding")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": config.OPENAI_CLIENT_USER_AGENT,
    }
    api_key = str(group.API_KEY or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = json.dumps({"model": model, "input": text}, ensure_ascii=False).encode("utf-8")
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10, read=30, write=30, pool=10),
        proxy=proxy_url,
        trust_env=False,
    ) as client:
        response = await client.post(_build_embeddings_url(base_url), headers=headers, content=payload)
        response.raise_for_status()
        body = response.json()

    try:
        vector = body["data"][0]["embedding"]
    except Exception as e:
        logger.error(f"system_voice embedding 响应格式异常: {body}")
        raise RuntimeError("system_voice embedding 响应格式异常") from e

    if not isinstance(vector, list) or not vector:
        raise RuntimeError("system_voice embedding 返回空向量")
    return [float(item) for item in vector]


def cosine_similarity(left: List[float], right: List[float]) -> float:
    if not left or not right or len(left) != len(right):
        return -1.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm <= 0.0 or right_norm <= 0.0:
        return -1.0
    return numerator / (left_norm * right_norm)
