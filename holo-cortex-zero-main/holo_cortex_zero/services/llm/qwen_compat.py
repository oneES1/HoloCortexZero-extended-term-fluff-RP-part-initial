"""Qwen tool_call 格式兼容层

Qwen (通过 vLLM) 的 tool_call 可能走以下格式之一：
1. 标准 OpenAI function_call 字段（vLLM 0.17+ 支持，推荐）
2. XML 标签 <tool_call>{"name":"xxx","arguments":{...}}</tool_call> 内嵌 JSON
3. Qwen 原生格式 <tool_call><function=name><parameter=key>value</parameter></function></tool_call>
4. 内联标签 <|tool_call|>{JSON}<|/tool_call|>
5. 兼容标签 <|tool_call>call:name{key: value}<tool_call|>

本模块负责从 LLM 输出中提取出标准 ToolCall 对象。
"""
from __future__ import annotations

import json
import re
import uuid
from typing import List, Optional, Tuple

from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.schemas.ir import ToolCall

# ── 格式 1: <tool_call>{JSON}</tool_call> ──
# 不用正则匹配 JSON 内容，改用标签定位 + json.loads 提取

_TOOL_CALL_TAG_PATTERN = re.compile(
    r"<tool_call>\s*(.*?)(?:\s*</tool_call>|$)",
    re.DOTALL,
)

# ── 格式 2: <|tool_call|>{JSON}<|/tool_call|> ──

_TOOL_CALL_INLINE_PATTERN = re.compile(
    r'<\|tool_call\|>\s*(.*?)\s*(?:<\|/tool_call\|>|$)',
    re.DOTALL,
)

# ── 格式 2b: <|tool_call>call:name{key: value}<tool_call|> ──
# 主干仍输出标准 ToolCall；该分支只兼容模型把 tool_call 作为可见文本吐出的标签方言。

_TOOL_CALL_COMPAT_INLINE_PATTERN = re.compile(
    r'<\|tool_call>\s*(.*?)\s*(?:<tool_call\|>|<\|/tool_call\|>|</tool_call>|$)',
    re.DOTALL,
)

_CALL_STYLE_PATTERN = re.compile(
    r'^\s*call\s*:\s*([A-Za-z_][\w.-]*)\s*(\{.*\})?\s*$',
    re.DOTALL,
)

_LOOSE_OBJECT_KEY_PATTERN = re.compile(r'([\{,]\s*)([A-Za-z_][\w.-]*)(\s*:)', re.DOTALL)

# ── 格式 3: Qwen 原生 <tool_call><function=name><parameter=key>value</parameter></function></tool_call> ──

_QWEN_NATIVE_PATTERN = re.compile(
    r"<tool_call>\s*<function=([^>]+)>(.*?)</function>\s*</tool_call>",
    re.DOTALL,
)

_QWEN_PARAM_PATTERN = re.compile(
    r"<parameter=(\w+)>\s*(.*?)\s*</parameter>",
    re.DOTALL,
)


def _extract_json_object(text: str) -> Optional[dict]:
    """从文本中提取第一个完整的 JSON 对象（括号平衡匹配）

    解决 .*? 非贪心正则在嵌套 JSON 时截断的问题。
    例如 {"name":"weather","arguments":{"city":"北京"}} 不会在第一个 } 截断。
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError as e:
                    logger.warning(f"Qwen compat: JSON 解析失败 (pos {start}-{i+1}): {e}")
                    return None

    logger.warning(f"Qwen compat: JSON 括号不平衡，无法提取完整对象")
    return None


def _parse_loose_object(text: str) -> Optional[dict]:
    content = str(text or "").strip()
    if not content:
        return {}

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        normalized = _LOOSE_OBJECT_KEY_PATTERN.sub(r'\1"\2"\3', content)
        try:
            data = json.loads(normalized)
        except json.JSONDecodeError as exc:
            logger.warning(f"Qwen compat: call 风格参数解析失败: {exc}")
            return None

    if isinstance(data, dict):
        return data
    return {"value": data}


def _parse_call_style_tool_call(raw_content: str) -> Optional[ToolCall]:
    match = _CALL_STYLE_PATTERN.match(str(raw_content or ""))
    if not match:
        return None

    name = match.group(1).strip()
    arguments_raw = str(match.group(2) or "").strip()
    arguments = _parse_loose_object(arguments_raw)
    if arguments is None:
        return None

    return ToolCall(
        id=f"call_{uuid.uuid4().hex[:8]}",
        name=name,
        arguments=arguments,
    )


def _remove_spans(text: str, spans: List[Tuple[int, int]]) -> str:
    if not spans:
        return text.strip()

    merged_spans: List[Tuple[int, int]] = []
    for start, end in sorted(spans):
        if not merged_spans or start > merged_spans[-1][1]:
            merged_spans.append((start, end))
            continue
        merged_spans[-1] = (merged_spans[-1][0], max(merged_spans[-1][1], end))

    parts: List[str] = []
    last = 0
    for start, end in merged_spans:
        if start > last:
            parts.append(text[last:start])
        last = max(last, end)
    if last < len(text):
        parts.append(text[last:])

    cleaned = "".join(parts)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def parse_qwen_tool_calls(text: str) -> Tuple[List[ToolCall], str]:
    """从 Qwen 的输出文本中提取 tool_call

    Returns:
        (tool_calls, cleaned_text) - 提取到的 tool 调用列表，以及去除 tool 标签后的剩余文本
    """
    calls: List[ToolCall] = []
    matched_spans: List[Tuple[int, int]] = []

    # 尝试 Qwen 原生格式: <function=name><parameter=key>value</parameter></function>
    for match in _QWEN_NATIVE_PATTERN.finditer(text):
        func_name = match.group(1)
        params_block = match.group(2)

        arguments = {}
        for param_match in _QWEN_PARAM_PATTERN.finditer(params_block):
            key = param_match.group(1)
            value = param_match.group(2).strip()
            # 尝试解析为 JSON 值
            try:
                arguments[key] = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                arguments[key] = value

        if func_name:
            calls.append(ToolCall(
                id=f"call_{uuid.uuid4().hex[:8]}",
                name=func_name,
                arguments=arguments,
            ))
            matched_spans.append(match.span())

    # 尝试 JSON 标签格式（使用括号平衡匹配，不依赖正则捕获 JSON）
    for pattern in (_TOOL_CALL_TAG_PATTERN, _TOOL_CALL_INLINE_PATTERN):
        for match in pattern.finditer(text):
            raw_content = match.group(1)
            if raw_content.lstrip().startswith("<function="):
                continue
            data = _extract_json_object(raw_content)
            if data is None:
                logger.warning(
                    f"Qwen compat: 标签内 JSON 提取失败，原文: {raw_content[:200]}"
                )
                continue

            name = data.get("name") or data.get("function", "")
            arguments = data.get("arguments", data.get("parameters", {}))

            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {"raw": arguments}

            if name:
                calls.append(ToolCall(
                    id=f"call_{uuid.uuid4().hex[:8]}",
                    name=name,
                    arguments=arguments if isinstance(arguments, dict) else {},
                ))
                matched_spans.append(match.span())
            else:
                logger.warning(f"Qwen compat: tool_call 缺少 name 字段: {data}")

    # 尝试 call:name{...} 兼容标签格式。
    for match in _TOOL_CALL_COMPAT_INLINE_PATTERN.finditer(text):
        raw_content = match.group(1)
        call = _parse_call_style_tool_call(raw_content)
        if call is None:
            logger.warning(f"Qwen compat: call 风格 tool_call 提取失败，原文: {raw_content[:200]}")
            continue
        calls.append(call)
        matched_spans.append(match.span())

    cleaned = _remove_spans(text, matched_spans)
    return calls, cleaned


def merge_tool_calls(
    standard_calls: Optional[List[ToolCall]],
    text_calls: List[ToolCall],
) -> List[ToolCall]:
    """合并标准 function_call 字段和从文本中提取的 tool_call

    优先使用标准字段，仅当标准字段为空时才使用文本提取的结果。
    """
    if not standard_calls:
        return text_calls
    if not text_calls:
        return standard_calls

    merged: List[ToolCall] = []
    used_text_indexes: set[int] = set()

    for idx, std_call in enumerate(standard_calls):
        call = ToolCall(
            id=std_call.id,
            name=std_call.name,
            arguments=dict(std_call.arguments or {}),
        )

        if idx < len(text_calls):
            txt_call = text_calls[idx]
            same_name = bool(call.name) and call.name == txt_call.name

            if not call.name and txt_call.name:
                call.name = txt_call.name
                same_name = True

            if same_name and isinstance(txt_call.arguments, dict) and txt_call.arguments:
                merged_args = dict(txt_call.arguments)
                merged_args.update(call.arguments or {})
                call.arguments = merged_args
                used_text_indexes.add(idx)

        merged.append(call)

    existing_signatures = {(c.name, json.dumps(c.arguments or {}, ensure_ascii=False, sort_keys=True)) for c in merged}
    for idx, txt_call in enumerate(text_calls):
        if idx in used_text_indexes:
            continue
        signature = (txt_call.name, json.dumps(txt_call.arguments or {}, ensure_ascii=False, sort_keys=True))
        if signature in existing_signatures:
            continue
        merged.append(txt_call)
        existing_signatures.add(signature)

    return merged
