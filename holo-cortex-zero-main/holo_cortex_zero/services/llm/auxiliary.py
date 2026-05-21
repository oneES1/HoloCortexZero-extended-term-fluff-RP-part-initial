from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.config import ModelConfigGroup
from holo_cortex_zero.core.proxy_utils import resolve_model_group_proxy
from holo_cortex_zero.schemas.ir import GenerationRequest, GenerationResult
from holo_cortex_zero.services.llm.model_group_params import build_model_group_extra_params
from holo_cortex_zero.services.llm.router import detect_model_group_protocol, llm_router


@dataclass(frozen=True)
class PreparedAuxiliaryRequest:
    aux_name: str
    source: str
    request: GenerationRequest
    model_group: ModelConfigGroup
    model_group_key: str
    protocol: str
    proxy: Optional[str]


def build_aux_cache_hints(aux_name: str) -> dict[str, str]:
    normalized_aux_name = str(aux_name or "unknown").strip() or "unknown"
    return {
        "cache_control": "ephemeral",
        "stable_prefix": "system_first_text",
        "aux_name": normalized_aux_name,
    }


def _clone_generation_request(
    request: GenerationRequest,
    *,
    aux_name: str,
    model: str,
    extra_params: Dict[str, Any],
    cache_hints: Dict[str, str],
) -> GenerationRequest:
    return GenerationRequest(
        context_id=f"aux:{str(aux_name or 'unknown').strip() or 'unknown'}",
        model=model,
        messages=list(request.messages),
        tools=list(request.tools),
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        stream=False,
        extra_params=extra_params,
        cache_hints=cache_hints,
    )


def prepare_auxiliary_request(
    *,
    aux_name: str,
    model_group_key: str,
    request: GenerationRequest,
    source: str,
) -> PreparedAuxiliaryRequest:
    normalized_aux_name = str(aux_name or "unknown").strip() or "unknown"
    normalized_group_key = str(model_group_key or "").strip()
    if not normalized_group_key:
        raise KeyError(f"辅助 LLM {normalized_aux_name} 缺少模型组配置")

    model_group = config.get_model_group_info(normalized_group_key)
    protocol = detect_model_group_protocol(model_group, allow_legacy_wire_api=True)
    proxy = resolve_model_group_proxy(
        model_group,
        group_key=normalized_group_key,
        source=source,
    )

    group_extra_params = build_model_group_extra_params(
        model_group,
        source_hint=f"{source}:{normalized_group_key}",
    )
    request_extra_params = dict(request.extra_params) if isinstance(request.extra_params, dict) else {}
    merged_extra_params = {**group_extra_params, **request_extra_params}

    merged_cache_hints = build_aux_cache_hints(normalized_aux_name)
    if isinstance(request.cache_hints, dict):
        merged_cache_hints.update({str(k): str(v) for k, v in request.cache_hints.items()})

    prepared_request = _clone_generation_request(
        request,
        aux_name=normalized_aux_name,
        model=str(getattr(model_group, "CHAT_MODEL", "") or ""),
        extra_params=merged_extra_params,
        cache_hints=merged_cache_hints,
    )

    return PreparedAuxiliaryRequest(
        aux_name=normalized_aux_name,
        source=source,
        request=prepared_request,
        model_group=model_group,
        model_group_key=normalized_group_key,
        protocol=protocol,
        proxy=proxy,
    )


async def generate_prepared_auxiliary(
    prepared: PreparedAuxiliaryRequest,
    *,
    timeout: float = 120.0,
) -> GenerationResult:
    return await llm_router.generate(
        prepared.request,
        api_key=prepared.model_group.API_KEY,
        base_url=prepared.model_group.BASE_URL,
        protocol=prepared.protocol,
        proxy=prepared.proxy,
        timeout=timeout,
    )


async def generate_auxiliary(
    *,
    aux_name: str,
    model_group_key: str,
    request: GenerationRequest,
    source: str,
    timeout: float = 120.0,
) -> GenerationResult:
    prepared = prepare_auxiliary_request(
        aux_name=aux_name,
        model_group_key=model_group_key,
        request=request,
        source=source,
    )
    return await generate_prepared_auxiliary(prepared, timeout=timeout)
