"""潜意识层（Stage1 路由）骨架。

Phase A 目标：
- 抽离出独立模块，后续可在 Prompt 注入与消息拦截两处复用。
- 定义统一输出协议：intents[] + cache_updates。
- 提供：prompt 构造、LLM 调用、严格 JSON 解析/校验、失败降级入口。

注意：本文件在 Phase A 不会被现有业务代码引用（不改变现状逻辑）。
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple, TypedDict

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.prompt_defaults import DEFAULT_SUBCONSCIOUS_SYSTEM_PROMPT, render_identity_prompt
from holo_cortex_zero.core.runtime_identity import get_bot_persona_display_name
from holo_cortex_zero.schemas.ir import GenerationRequest, MessagePart, MessageTurn, ToolCall, ToolSpec
from holo_cortex_zero.services.llm.auxiliary import generate_auxiliary
from holo_cortex_zero.services.llm.model_group_params import build_model_group_extra_params
from holo_cortex_zero.services.llm.router import detect_model_group_protocol

from .graph_cache import GraphSnapshot, HCZ_SELF
from .utils import get_model_group_info


# =========================
# 协议定义（runtime schema）
# =========================


class SubconsciousIntent(TypedDict, total=False):
    target_id: str
    query: str
    tags: List[str]
    reason: str
    priority: int


class SubconsciousCacheUpdates(TypedDict, total=False):
    relations: Dict[str, str]
    concepts: Dict[str, str]


class SubconsciousTopicMode(TypedDict, total=False):
    mode: str
    reason: str


class SubconsciousResult(TypedDict, total=False):
    intents: List[SubconsciousIntent]
    cache_updates: SubconsciousCacheUpdates
    topic_mode: SubconsciousTopicMode


_SUBCONSCIOUS_INTENT_TOOL_NAME = "append_stage1_intent"
_SUBCONSCIOUS_CACHE_TOOL_NAME = "update_stage1_cache"
_SUBCONSCIOUS_TOOL_RULES = """
【输出方式（responses 主干，必须执行）】
- 必须使用 tool call，不要输出自然语言正文，也不要输出 JSON。
- 每个检索目标单独调用 `append_stage1_intent` 1 次；一次查多个目标，就连续调用多次。
- 如需写入 alias / 概念热缓存，再调用 `update_stage1_cache`。
"""

_SUBCONSCIOUS_JSON_RULES = """
【输出方式（必须执行）】
- 禁止使用 tool call，不要输出自然语言正文，也不要输出 Markdown 代码块。
- 只能输出一行 JSON，对象结构固定为：
  {"intents":[...],"cache_updates":{"relations":{},"concepts":{}}}
- `intents` 必须是数组；每个 intent 至少包含 `target_id` 和 `query`。
- `cache_updates` 必须始终返回对象；没有更新时返回空对象结构。
- `target_id` 只能是 `HCZ_SELF` 或纯数字字符串。
"""

SubconsciousOutputMode = Literal["tool", "json"]


# =========================
# Prompt 构造
# =========================


DEFAULT_SYSTEM_PROMPT = DEFAULT_SUBCONSCIOUS_SYSTEM_PROMPT


def _format_recent_messages(recent_messages: Sequence[Any], limit: int = 10) -> str:
    if not recent_messages:
        return "(无)"

    # 关键：必须把“数值型 sender_id”暴露给潜意识模型，否则它看见的只是昵称，
    # 会导致「发言主体 ↔ target_id」无法绑定，从而出现“把别人的话当成受保护别名主体说的”这种错配。
    msgs = list(recent_messages)[-limit:]
    lines: List[str] = []
    for m in msgs:
        raw_sender_id = str(getattr(m, "sender_id", None) or "").strip()
        raw_platform_userid = str(getattr(m, "platform_userid", None) or "").strip()
        raw_sender_name = str(getattr(m, "sender_name", None) or "").strip()
        raw_sender_nickname = str(getattr(m, "sender_nickname", None) or "").strip()

        is_true_system = raw_sender_id == "-1" and (
            raw_platform_userid == "0"
            or (raw_sender_name.upper() == "SYSTEM" and raw_sender_nickname.upper() == "SYSTEM")
        )
        if is_true_system:
            continue

        sender_id = HCZ_SELF if raw_sender_id == "-1" else (raw_sender_id or raw_platform_userid)
        sender_name = raw_sender_nickname or raw_sender_name or (
            get_bot_persona_display_name(config) if sender_id == HCZ_SELF else ""
        )

        if sender_name and sender_id:
            sender = f"{sender_name}({sender_id})"
        else:
            sender = sender_id or sender_name or "unknown"

        text = (
            getattr(m, "content_text", None)
            or getattr(m, "content", None)
            or ""
        )
        text = str(text).strip()
        if not text:
            # 兜底：某些适配器（如 Telegram）媒体消息 content_text 可能为空，但 content_data 里有段文本占位符
            # 例如 ChatMessageSegmentFile.text = "[File: xxx.ogg]"。
            try:
                raw_cd = getattr(m, "content_data", None)
                if raw_cd:
                    if isinstance(raw_cd, str):
                        data = json.loads(raw_cd)
                    else:
                        data = raw_cd
                    seg_texts: List[str] = []
                    if isinstance(data, list):
                        for seg in data:
                            if not isinstance(seg, dict):
                                continue
                            t = str(seg.get("text") or "").strip()
                            if t:
                                seg_texts.append(t)
                    text = " ".join(seg_texts).strip()
            except Exception:
                text = ""

        if not text:
            continue
        lines.append(f"{sender}: {text}")

    return "\n".join(lines) if lines else "(无有效文本)"


def _resolve_system_prompt(system_prompt: Optional[str] = None) -> str:
    prompt = str(system_prompt or getattr(config, "SUBCONSCIOUS_SYSTEM_PROMPT", "") or "").strip()
    if not prompt:
        prompt = DEFAULT_SYSTEM_PROMPT or DEFAULT_SUBCONSCIOUS_SYSTEM_PROMPT
    prompt = render_identity_prompt(prompt, config)
    logger.debug("Stage1 subconscious system prompt resolved: prompt_length=%s", len(prompt))
    return prompt


def _format_trigger_message(recent_messages: Sequence[Any], meta: Optional[Dict[str, Any]] = None) -> str:
    """抽取本轮真正触发 Stage1 的消息，供路由检索优先参考。"""

    meta = meta or {}
    trigger_user_id = str(meta.get("trigger_user_id") or "").strip()
    latest_sender_id = str(meta.get("latest_sender_id") or "").strip()
    preferred_ids = [item for item in [trigger_user_id, latest_sender_id] if item]
    msgs = list(recent_messages or [])

    for preferred_id in preferred_ids:
        for m in reversed(msgs):
            sender_id = str(getattr(m, "sender_id", None) or getattr(m, "platform_userid", None) or "").strip()
            text = str(getattr(m, "content_text", None) or getattr(m, "content", None) or "").strip()
            if sender_id == preferred_id and text:
                sender_name = str(getattr(m, "sender_nickname", None) or getattr(m, "sender_name", None) or sender_id).strip()
                return f"{sender_name}({sender_id}): {text}"

    for m in reversed(msgs):
        sender_id = str(getattr(m, "sender_id", None) or getattr(m, "platform_userid", None) or "").strip()
        text = str(getattr(m, "content_text", None) or getattr(m, "content", None) or "").strip()
        if text:
            sender_name = str(getattr(m, "sender_nickname", None) or getattr(m, "sender_name", None) or sender_id or "unknown").strip()
            if sender_id == "-1":
                sender_id = HCZ_SELF
            return f"{sender_name}({sender_id or 'unknown'}): {text}"
    return "(无)"


def build_subconscious_prompt(
    *,
    recent_messages: Sequence[Any],
    graph_snapshot: GraphSnapshot,
    meta: Optional[Dict[str, Any]] = None,
    system_prompt: Optional[str] = None,
    output_mode: SubconsciousOutputMode = "tool",
) -> List[Dict[str, str]]:
    """构造潜意识 LLM 的 messages。"""

    meta = meta or {}
    meta_lines: List[str] = []
    for k, v in meta.items():
        try:
            # 对 dict/list 做 JSON 序列化，避免 Python repr 里的单引号/None 等干扰模型理解。
            if isinstance(v, (dict, list, tuple)):
                vv = json.dumps(v, ensure_ascii=False)
            else:
                vv = str(v)
            meta_lines.append(f"- {k}: {vv}")
        except Exception:
            pass

    snapshot_text = json.dumps(graph_snapshot.to_dict(), ensure_ascii=False)
    trigger_text = _format_trigger_message(recent_messages, meta)
    recent_text = _format_recent_messages(recent_messages)

    user_return_rule = (
        "\n必须通过 tool call 返回，不要输出 JSON 或自然语言正文。"
        if output_mode == "tool"
        else "\n只输出一行 JSON，不要输出 tool call、自然语言正文或 Markdown 代码块。"
    )
    output_rules = _SUBCONSCIOUS_TOOL_RULES if output_mode == "tool" else _SUBCONSCIOUS_JSON_RULES

    user_prompt = "\n\n".join(
        [
            "### 元信息 ###\n" + ("\n".join(meta_lines) if meta_lines else "(无)"),
            "### 当前触发消息（路由检索时最高优先级）###\n" + trigger_text,
            "### Graph Snapshot (来自 Stage0 cache) ###\n" + snapshot_text,
            "### 最近对话（只用于指代消解 / 路由检索）###\n" + recent_text,
            user_return_rule,
        ]
    )

    resolved_system_prompt = _resolve_system_prompt(system_prompt)

    return [
        {"role": "system", "content": f"{resolved_system_prompt}\n\n{output_rules}"},
        {"role": "user", "content": user_prompt},
    ]


# =========================
# JSON 解析与严格校验
# =========================


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _coerce_bool(v: Any) -> Optional[bool]:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"true", "1", "yes", "y"}:
            return True
        if s in {"false", "0", "no", "n"}:
            return False
    return None


def _ensure_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _ensure_str_list(v: Any) -> Optional[List[str]]:
    if v is None:
        return None
    if isinstance(v, list):
        out: List[str] = []
        for x in v:
            sx = _ensure_str(x)
            if sx:
                out.append(sx)
        return out
    if isinstance(v, str):
        # 容错：逗号分隔
        parts = [p.strip() for p in v.split(",")]
        out = [p for p in parts if p]
        return out
    return None


def _ensure_str_dict(v: Any) -> Optional[Dict[str, str]]:
    if v is None:
        return None
    if not isinstance(v, dict):
        return None
    out: Dict[str, str] = {}
    for k, val in v.items():
        sk = _ensure_str(k)
        sv = _ensure_str(val)
        if sk and sv:
            out[sk] = sv
    return out


def parse_and_validate(raw: Any) -> Optional[SubconsciousResult]:
    """解析潜意识输出，返回“归一化后的”结果。

    - 任何不合格输出返回 None（供上层降级）。
    - 会尽量从杂讯文本中提取 JSON。
    """

    data: Any = None

    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, str):
        text = raw.strip()
        try:
            data = json.loads(text)
        except Exception:
            m = _JSON_RE.search(text)
            if not m:
                return None
            try:
                data = json.loads(m.group(0))
            except Exception:
                return None
    else:
        return None

    if not isinstance(data, dict):
        return None

    topic_mode_raw = data.get("topic_mode")
    topic_mode: SubconsciousTopicMode = {}
    if isinstance(topic_mode_raw, dict):
        mode = (_ensure_str(topic_mode_raw.get("mode")) or "").upper()
        if mode in {"A", "B"}:
            topic_mode["mode"] = mode
            reason = _ensure_str(topic_mode_raw.get("reason"))
            if reason:
                topic_mode["reason"] = reason

    intents_raw = data.get("intents")
    intents: List[SubconsciousIntent] = []
    if intents_raw is None:
        intents_raw = []
    if not isinstance(intents_raw, list):
        return None
    for it in intents_raw:
        if len(intents) >= 5:
            logger.info("🧠 [Stage1] intents 超过上限，已截断到 5 条")
            break
        if not isinstance(it, dict):
            continue
        target_id = _ensure_str(it.get("target_id"))
        query = _ensure_str(it.get("query"))
        if not target_id or not query:
            continue
        intent: SubconsciousIntent = {
            "target_id": target_id,
            "query": query,
        }
        tags = _ensure_str_list(it.get("tags"))
        if tags:
            intent["tags"] = tags
        reason = _ensure_str(it.get("reason"))
        if reason:
            intent["reason"] = reason
        pr = it.get("priority")
        if isinstance(pr, (int, float)):
            intent["priority"] = int(pr)
        intents.append(intent)

    cache_updates_raw = data.get("cache_updates")
    cache_updates: SubconsciousCacheUpdates = {}
    if isinstance(cache_updates_raw, dict):
        rel = _ensure_str_dict(cache_updates_raw.get("relations"))
        con = _ensure_str_dict(cache_updates_raw.get("concepts"))
        if rel:
            cache_updates["relations"] = rel
        if con:
            cache_updates["concepts"] = con

    result: SubconsciousResult = {
        "intents": intents,
        "cache_updates": cache_updates,
    }
    if topic_mode:
        result["topic_mode"] = topic_mode
    return result


# =========================
# LLM 调用
# =========================


def _detect_subconscious_protocol(model_group: Any) -> str:
    """判定潜意识 Stage1 的协议类型。

    主干：优先尊重新增模型组字段 `WIRE_API`，
    未显式指定时与主聊天链路保持一致，默认走 responses。
    分支兼容：对已知 `/responses` 兼容目标（如 Ark `/api/v3`、GPT relay）
    直接走共享 ResponsesEmitter，这样 Stage1 的 tool-first 不需要再分叉一套豆包支线。
    """
    return detect_model_group_protocol(model_group, allow_legacy_wire_api=True)



def _output_mode_for_protocol(protocol: str) -> SubconsciousOutputMode:
    return "json" if protocol == "chat" else "tool"


def _messages_to_turns(messages: List[Dict[str, str]]) -> List[MessageTurn]:
    turns: List[MessageTurn] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role_raw = str(msg.get("role") or "user").strip().lower()
        role = role_raw if role_raw in {"system", "user", "assistant", "tool"} else "user"
        content = str(msg.get("content") or "")
        turns.append(
            MessageTurn(
                role=role,  # type: ignore[arg-type]
                parts=[MessagePart(type="text", text=content)],
            ),
        )
    return turns


def _build_stage1_tool_specs() -> List[ToolSpec]:
    return [
        ToolSpec(
            name=_SUBCONSCIOUS_INTENT_TOOL_NAME,
            description=(
                "追加一条 Stage1 检索意图。一次只写一个目标；"
                "若要查多个目标，请多次调用本工具。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "target_id": {"type": "string"},
                    "query": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                    "priority": {"type": "integer"},
                },
                "required": ["target_id", "query"],
            },
        ),
        ToolSpec(
            name=_SUBCONSCIOUS_CACHE_TOOL_NAME,
            description="更新 Stage1 热缓存映射（relations / concepts）。可选调用。",
            parameters={
                "type": "object",
                "properties": {
                    "relations": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                    "concepts": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                },
            },
        ),
    ]


def _merge_stage1_tool_payloads(tool_calls: List[ToolCall]) -> Optional[Dict[str, Any]]:
    merged: Dict[str, Any] = {
        "intents": [],
        "cache_updates": {"relations": {}, "concepts": {}},
    }
    hit = False

    for call in tool_calls:
        call_name = str(call.name or "").strip()
        args = call.arguments if isinstance(call.arguments, dict) else {}

        if call_name == _SUBCONSCIOUS_INTENT_TOOL_NAME:
            hit = True
            merged["intents"].append(args)
            continue

        if call_name == "set_stage1_topic_mode":
            hit = True
            mode = str(args.get("mode") or "").strip().upper()
            if mode in {"A", "B"}:
                merged["topic_mode"] = {
                    "mode": mode,
                    "reason": str(args.get("reason") or "").strip(),
                }
            continue

        if call_name == _SUBCONSCIOUS_CACHE_TOOL_NAME:
            hit = True
            relations = args.get("relations")
            concepts = args.get("concepts")
            if isinstance(relations, dict):
                merged["cache_updates"]["relations"].update(
                    {str(k): str(v) for k, v in relations.items() if str(k).strip() and str(v).strip()},
                )
            if isinstance(concepts, dict):
                merged["cache_updates"]["concepts"].update(
                    {str(k): str(v) for k, v in concepts.items() if str(k).strip() and str(v).strip()},
                )
            continue

    if not hit:
        return None
    return merged


async def call_subconscious_llm(
    *,
    model_group_name: str,
    messages: List[Dict[str, str]],
    protocol: Optional[str] = None,
    timeout_seconds: float = 15.0,
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """调用潜意识模型组（独立于 MEMORY_MANAGE_MODEL）。

    主干：优先使用工具调用返回结构化路由结果（支持一次多 intents）。
    兼容：若网关不支持 tool call，再降级到旧文本 JSON 输出。
    """

    model_group = get_model_group_info(model_group_name)
    resolved_temperature = (
        model_group.TEMPERATURE if getattr(model_group, "TEMPERATURE", None) is not None else temperature
    )
    resolved_protocol = protocol or _detect_subconscious_protocol(model_group)
    extra_params = build_model_group_extra_params(model_group, source_hint=f"memory.subconscious:{model_group_name}")
    output_mode = _output_mode_for_protocol(resolved_protocol)

    async def _invoke_with_tool_choice(tool_choice: str) -> Tuple[Optional[Dict[str, Any]], str, int]:
        stage_extra_params = dict(extra_params)
        stage_extra_params["tool_choice"] = tool_choice
        request = GenerationRequest(
            context_id="aux:subconscious",
            model="",
            messages=_messages_to_turns(messages),
            tools=_build_stage1_tool_specs(),
            temperature=float(resolved_temperature if resolved_temperature is not None else 0.0),
            max_tokens=max_tokens,
            stream=False,
            extra_params=stage_extra_params,
        )
        result = await generate_auxiliary(
            aux_name="subconscious",
            model_group_key=model_group_name,
            request=request,
            source="memory.subconscious",
            timeout=max(timeout_seconds, 30.0),
        )
        tool_payload = _merge_stage1_tool_payloads(result.tool_calls)
        text_payload = str(result.text or "")
        return tool_payload, text_payload, len(result.tool_calls)

    async def _do_tool_call() -> Tuple[Optional[Dict[str, Any]], str]:
        try:
            logger.debug(
                "🧠 [Stage1] 调用潜意识模型(tool-first): "
                + f"group={model_group_name}, "
                + f"model={model_group.CHAT_MODEL}, "
                + f"protocol={resolved_protocol}, "
                + f"extra_body={'yes' if bool(extra_params) else 'no'}"
            )
        except Exception:
            pass

        tool_payload, text_payload, call_count = await _invoke_with_tool_choice("auto")
        if tool_payload is None or call_count <= 0:
            raise RuntimeError("stage1_tool_required_but_missing")
        logger.info(
            "🧠 [Stage1] tool-only 响应(auto): "
            f"group={model_group_name}, protocol={resolved_protocol}, "
            f"tool_calls={call_count}, text_len={len(text_payload)}"
        )
        return tool_payload, text_payload

    async def _do_json_call() -> str:
        try:
            logger.debug(
                "🧠 [Stage1] 调用潜意识模型(json-only): "
                + f"group={model_group_name}, "
                + f"model={model_group.CHAT_MODEL}, "
                + f"protocol={resolved_protocol}, "
                + f"extra_body={'yes' if bool(extra_params) else 'no'}"
            )
        except Exception:
            pass

        request = GenerationRequest(
            context_id="aux:subconscious",
            model="",
            messages=_messages_to_turns(messages),
            tools=[],
            temperature=float(resolved_temperature if resolved_temperature is not None else 0.0),
            max_tokens=max_tokens,
            stream=False,
            extra_params=dict(extra_params),
        )
        result = await generate_auxiliary(
            aux_name="subconscious",
            model_group_key=model_group_name,
            request=request,
            source="memory.subconscious",
            timeout=max(timeout_seconds, 30.0),
        )
        text_payload = str(result.text or "")
        logger.info(
            "🧠 [Stage1] json-only 响应: "
            f"group={model_group_name}, protocol={resolved_protocol}, text_len={len(text_payload)}"
        )
        return text_payload

    if output_mode == "json":
        text = await asyncio.wait_for(_do_json_call(), timeout=timeout_seconds)
        return None, text

    tool_payload, text = await asyncio.wait_for(_do_tool_call(), timeout=timeout_seconds)
    return tool_payload, text


async def run_subconscious(
    *,
    model_group_name: str,
    recent_messages: Sequence[Any],
    graph_snapshot: GraphSnapshot,
    meta: Optional[Dict[str, Any]] = None,
    system_prompt: Optional[str] = None,
    timeout_seconds: float = 15.0,
    max_tokens: int = 1024,
) -> Optional[SubconsciousResult]:
    """一站式入口：build -> call -> parse&validate。

    失败返回 None，供业务侧直接降级。
    """

    model_group = get_model_group_info(model_group_name)
    protocol = _detect_subconscious_protocol(model_group)
    output_mode = _output_mode_for_protocol(protocol)

    messages = build_subconscious_prompt(
        recent_messages=recent_messages,
        graph_snapshot=graph_snapshot,
        meta=meta,
        system_prompt=system_prompt,
        output_mode=output_mode,
    )
    try:
        tool_payload, raw = await call_subconscious_llm(
            model_group_name=model_group_name,
            messages=messages,
            protocol=protocol,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
        )
    except Exception as e:
        try:
            logger.warning(
                "🧠 [Stage1] 潜意识调用失败，已降级: "
                + f"group={model_group_name}, "
                + f"timeout={timeout_seconds}s, "
                + f"error={type(e).__name__}: {e}"
            )
        except Exception:
            pass
        return None

    if tool_payload is not None:
        parsed_tool = parse_and_validate(tool_payload)
        if parsed_tool is not None:
            return parsed_tool
        logger.warning("🧠 [Stage1] tool 调用返回结构非法，尝试文本兜底解析")

    if not raw or not str(raw).strip():
        return None

    parsed_text = parse_and_validate(raw)
    if parsed_text is None:
        try:
            raw_preview = str(raw).strip().replace("\n", " ")
            if len(raw_preview) > 600:
                raw_preview = raw_preview[:600] + "..."
            logger.warning(f"🧠 [Stage1] 潜意识输出无法解析，已降级。raw_preview={raw_preview!r}")
        except Exception:
            pass
        return None

    return parsed_text
