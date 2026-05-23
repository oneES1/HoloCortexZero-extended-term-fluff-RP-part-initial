from __future__ import annotations

import json
import time
from typing import Any, Dict

import httpx

from holo_cortex_zero.core.config import ModelConfigGroup, config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.proxy_utils import resolve_model_group_proxy
from holo_cortex_zero.schemas.ir import GenerationRequest, MessagePart, MessageTurn, ToolSpec
from holo_cortex_zero.services.llm.model_group_params import build_model_group_extra_params
from holo_cortex_zero.services.llm.router import detect_model_group_protocol, llm_router


CONNECTIVITY_TIMEOUT_SECONDS = 30.0
CONNECTIVITY_PROBE_TOOL_NAME = "hcz_connectivity_probe"


def _build_embeddings_url(base_url: str) -> str:
    normalized = str(base_url or "").rstrip("/")
    if normalized.endswith("/embeddings"):
        return normalized
    return f"{normalized}/embeddings"


def _build_draw_model_url(base_url: str) -> str:
    normalized = str(base_url or "").rstrip("/")
    if normalized.endswith("/model"):
        return normalized
    return f"{normalized}/model"


def _format_probe_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        status = response.status_code
        body = (response.text or "").strip().replace("\n", " ")
        if len(body) > 300:
            body = f"{body[:300]}..."
        return f"HTTP {status}: {body or response.reason_phrase}"
    if isinstance(exc, httpx.TimeoutException):
        return f"timeout after {int(CONNECTIVITY_TIMEOUT_SECONDS)}s"
    message = str(exc).strip()
    if not message:
        message = type(exc).__name__
    if len(message) > 300:
        message = f"{message[:300]}..."
    return message


async def _probe_embedding_group(
    model_group: ModelConfigGroup,
    *,
    group_name: str,
    proxy: str | None,
) -> Dict[str, Any]:
    base_url = str(model_group.BASE_URL or "").strip()
    model = str(model_group.CHAT_MODEL or "").strip()
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": config.OPENAI_CLIENT_USER_AGENT,
    }
    api_key = str(model_group.API_KEY or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = json.dumps({"model": model, "input": "ping"}, ensure_ascii=False).encode("utf-8")
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10, read=CONNECTIVITY_TIMEOUT_SECONDS, write=10, pool=10),
        proxy=proxy,
        trust_env=False,
    ) as client:
        response = await client.post(_build_embeddings_url(base_url), headers=headers, content=payload)
        response.raise_for_status()
        body = response.json()

    vector = body.get("data", [{}])[0].get("embedding") if isinstance(body, dict) else None
    if not isinstance(vector, list) or not vector:
        raise RuntimeError("embedding response missing non-empty data[0].embedding")
    return {"embedding_dimensions": len(vector), "group_name": group_name}


async def _probe_generation_group(
    model_group: ModelConfigGroup,
    *,
    group_name: str,
    protocol: str,
    proxy: str | None,
) -> Dict[str, Any]:
    tool_spec = ToolSpec(
        name=CONNECTIVITY_PROBE_TOOL_NAME,
        description="Connectivity probe tool. Call it once with ping='ok'.",
        parameters={
            "type": "object",
            "properties": {
                "ping": {
                    "type": "string",
                    "description": "Must be exactly ok.",
                },
            },
            "required": ["ping"],
            "additionalProperties": False,
        },
    )
    messages = [
        MessageTurn(
            role="system",
            parts=[
                MessagePart(
                    type="text",
                    text=(
                        "You are a connectivity probe. You must call the provided tool exactly once. "
                        "Do not answer in plain text before the tool call."
                    ),
                )
            ],
        ),
        MessageTurn(
            role="user",
            parts=[
                MessagePart(
                    type="text",
                    text=f"Call {CONNECTIVITY_PROBE_TOOL_NAME} with ping set to ok.",
                )
            ],
        ),
    ]
    first_request = GenerationRequest(
        context_id=f"model_group_connectivity:{group_name or 'unsaved'}",
        model=str(model_group.CHAT_MODEL or "").strip(),
        messages=messages,
        tools=[tool_spec],
        temperature=0,
        stream=False,
        extra_params=build_model_group_extra_params(
            model_group,
            source_hint=f"model_group_connectivity:{group_name or 'unsaved'}",
        ),
    )
    first_result = await llm_router.generate(
        first_request,
        api_key=str(model_group.API_KEY or ""),
        base_url=str(model_group.BASE_URL or ""),
        protocol=protocol,
        proxy=proxy,
        timeout=CONNECTIVITY_TIMEOUT_SECONDS,
    )
    tool_calls = list(first_result.tool_calls or [])
    if not tool_calls:
        raise RuntimeError("tool probe failed: model returned no tool call")

    probe_call = tool_calls[0]
    if probe_call.name != CONNECTIVITY_PROBE_TOOL_NAME:
        raise RuntimeError(f"tool probe failed: unexpected tool name {probe_call.name!r}")
    unexpected_names = sorted({call.name for call in tool_calls if call.name != CONNECTIVITY_PROBE_TOOL_NAME})
    if unexpected_names:
        raise RuntimeError(f"tool probe failed: unexpected tool names {unexpected_names}")

    second_request = GenerationRequest(
        context_id=f"model_group_connectivity:{group_name or 'unsaved'}",
        model=str(model_group.CHAT_MODEL or "").strip(),
        messages=[
            *messages,
            MessageTurn(
                role="assistant",
                parts=[MessagePart(type="text", text=first_result.text or "")],
                tool_calls=tool_calls,
                reasoning_content=first_result.reasoning_content,
            ),
            *[
                MessageTurn(
                    role="tool",
                    tool_call_id=tool_call.id,
                    parts=[MessagePart(type="text", text='{"ok":true}')],
                )
                for tool_call in tool_calls
            ],
            MessageTurn(
                role="user",
                parts=[MessagePart(type="text", text="Return a final short confirmation.")],
            ),
        ],
        temperature=0,
        stream=False,
        extra_params=build_model_group_extra_params(
            model_group,
            source_hint=f"model_group_connectivity_followup:{group_name or 'unsaved'}",
        ),
    )
    second_result = await llm_router.generate(
        second_request,
        api_key=str(model_group.API_KEY or ""),
        base_url=str(model_group.BASE_URL or ""),
        protocol=protocol,
        proxy=proxy,
        timeout=CONNECTIVITY_TIMEOUT_SECONDS,
    )
    return {
        "first_finish_reason": first_result.finish_reason,
        "second_finish_reason": second_result.finish_reason,
        "first_text_len": len(first_result.text or ""),
        "second_text_len": len(second_result.text or ""),
        "tool_calls": len(tool_calls),
        "tool_call_id": probe_call.id,
        "reasoning_replay_enabled": bool(
            isinstance(second_request.extra_params, dict)
            and second_request.extra_params.get("replay_reasoning_content")
        ),
        "first_reasoning_len": len(str(first_result.reasoning_content or "")),
    }


async def _probe_draw_model_metadata(
    model_group: ModelConfigGroup,
    *,
    group_name: str,
    proxy: str | None,
) -> Dict[str, Any]:
    base_url = str(model_group.BASE_URL or "").strip()
    headers = {
        "Accept": "application/json",
        "User-Agent": config.OPENAI_CLIENT_USER_AGENT,
    }
    api_key = str(model_group.API_KEY or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10, read=CONNECTIVITY_TIMEOUT_SECONDS, write=10, pool=10),
        proxy=proxy,
        trust_env=False,
    ) as client:
        response = await client.get(_build_draw_model_url(base_url), headers=headers)
        response.raise_for_status()
        content_type = str(response.headers.get("content-type") or "")
        body = response.json() if "json" in content_type.lower() else None

    return {
        "group_name": group_name,
        "status_code": response.status_code,
        "content_type": content_type,
        "json_object": isinstance(body, dict),
    }


async def test_model_group_connectivity(
    model_group: ModelConfigGroup,
    *,
    group_name: str = "",
) -> Dict[str, Any]:
    """Probe a model group through the same runtime protocol path used by real calls.

    主干：
    - 对话模型组走统一 LLM router 与协议发射器，并验证 tool call -> tool result 回灌闭环。
    - embedding 模型走 OpenAI-compatible `/embeddings` 端点。
    - draw 模型只测轻量 `/model` 元信息端点，避免触发收费绘图。
    这里只做按能力类型选择，不按供应商写分支。
    """
    normalized_group_name = str(group_name or getattr(model_group, "GROUP_NAME", "") or "").strip()
    model = str(model_group.CHAT_MODEL or "").strip()
    base_url = str(model_group.BASE_URL or "").strip()
    model_type = str(getattr(model_group, "MODEL_TYPE", "chat") or "chat").strip().lower()
    if model_type == "embedding":
        protocol = "embeddings"
    elif model_type == "draw":
        protocol = "draw_model_metadata"
    else:
        protocol = detect_model_group_protocol(model_group, allow_legacy_wire_api=True)
    proxy = resolve_model_group_proxy(
        model_group,
        group_key=normalized_group_name,
        source="model_group.connectivity",
    )

    started = time.perf_counter()
    base_result: Dict[str, Any] = {
        "ok": False,
        "suspected": False,
        "group_name": normalized_group_name,
        "model": model,
        "model_type": model_type,
        "protocol": protocol,
        "latency_ms": 0,
        "uses_proxy": bool(proxy),
    }

    try:
        if not base_url:
            raise ValueError("BASE_URL is empty")
        if not model:
            raise ValueError("CHAT_MODEL is empty")

        if model_type == "embedding":
            details = await _probe_embedding_group(
                model_group,
                group_name=normalized_group_name,
                proxy=proxy,
            )
        elif model_type == "draw":
            details = await _probe_draw_model_metadata(
                model_group,
                group_name=normalized_group_name,
                proxy=proxy,
            )
        else:
            details = await _probe_generation_group(
                model_group,
                group_name=normalized_group_name,
                protocol=protocol,
                proxy=proxy,
            )

        latency_ms = int((time.perf_counter() - started) * 1000)
        result = {
            **base_result,
            "ok": True,
            "latency_ms": latency_ms,
            "details": details,
        }
        logger.info(
            "模型组连通性测试成功: "
            f"group={normalized_group_name} model={model} type={model_type} "
            f"protocol={protocol} latency_ms={latency_ms} uses_proxy={bool(proxy)}"
        )
        return result
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        error = _format_probe_error(exc)
        result = {
            **base_result,
            "latency_ms": latency_ms,
            "suspected": model_type == "draw",
            "error": error,
        }
        logger.warning(
            "模型组连通性测试失败: "
            f"group={normalized_group_name} model={model} type={model_type} "
            f"protocol={protocol} latency_ms={latency_ms} uses_proxy={bool(proxy)} error={error}"
        )
        return result
