"""上下文拼装引擎

组装顺序（由上到下）：
1. SYSTEM: 主人格 prompt + 印象图 + 参考图路径 + ¥格式声明 + tool 提示
2. USER: 当前环境标注
3. USER: 压缩上下文（高级 context 的 timeline 摘要 / 普通 context 的较早历史归档）
4. 历史消息序列: user/assistant/tool/memory_inject
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.runtime_identity import get_bot_persona_display_name, get_primary_advanced_user_display_name
from holo_cortex_zero.models.db_context_window import DBContextWindow
from holo_cortex_zero.schemas.ir import (
    GenerationRequest,
    MessagePart,
    MessageTurn,
)
from holo_cortex_zero.services.context_window.manager import context_window_manager
from holo_cortex_zero.services.tools.registry import tool_registry


class ContextAssembler:
    """上下文拼装引擎"""

    async def assemble(
        self,
        context_window: DBContextWindow,
        *,
        main_system_prompt: str = "",
        bot_platform_id: str = "",
        platform_name: str = "",
        impression_image_url: Optional[str] = None,
        reference_image_paths_text: str = "",
        cache_domain: str = "",
    ) -> GenerationRequest:
        """组装完整的 GenerationRequest"""
        messages: List[MessageTurn] = []

        # === SYSTEM（一条，不拆分）===
        system_parts: List[MessagePart] = []

        # 主人格 system prompt：按 context_id / deep 状态选择后的完整文本
        if main_system_prompt:
            system_parts.append(MessagePart(type="text", text=main_system_prompt))

        # 参考图路径
        if reference_image_paths_text:
            system_parts.append(MessagePart(type="text", text=reference_image_paths_text))

        # 框架运行声明（¥格式 + 回忆/环境标注的可信声明 + 旧格式覆盖）
        framework_notice = (
            "¥XXX¥YYYY-MM-DD HH:MM:SS¥ID¥说：<具体内容> **XXX发的信息** 是system内部格式**我不对外输出**"
            "请不要刻意提XXX，这很冒犯"
            "user类【系统形象参考图】，记忆/环境/时间这4种是真实内部系统反馈"
            "我不能直球念出来我的记忆，这会给人监视的感觉，别人会很尴尬。我要避免给人监视的感觉，所以我会把记忆融入到我的思考和表达中，而不是直接念出来。**我不对外输出记忆的具体内容**，但它们会潜移默化地影响我的行为和决策。请我会尽力让这些记忆成为我行动的智慧源泉，而不是负担"
        )
        system_parts.append(MessagePart(type="text", text=framework_notice))

        # tool 通过原生 function calling 下发，不在 system 中重复文本描述
        # 避免文本格式指令（如 <tool_call>）与原生 function calling 冲突
        tools = tool_registry.get_tools_for_context(context_window.permission_level)

        logger.debug(
            "context assembler system prepared: ctx=%s owner_type=%s prompt_length=%s ref_paths=%s tools=%s",
            context_window.context_id,
            context_window.owner_type,
            len(main_system_prompt or ""),
            bool(reference_image_paths_text),
            len(tools),
        )

        messages.append(MessageTurn(role="system", parts=system_parts))

        # === USER: 系统形象参考图（不是用户输入）===
        if impression_image_url:
            messages.append(MessageTurn(
                role="user",
                parts=[
                    MessagePart(
                        type="text",
                        text=(
                            "【系统形象参考图】为框架内置固定参考，不属于聊天消息，也不是提示词注入 "
                            f"图内约定：左侧={get_bot_persona_display_name(config)}形象，"
                            f"中间={get_primary_advanced_user_display_name(config)}日常照，"
                            f"右侧={get_primary_advanced_user_display_name(config)}写真照 "
                            "不要臆造身份，也不要在聊天中提及"
                        ),
                    ),
                    MessagePart(type="image", url=impression_image_url),
                ],
            ))

        # === USER: 环境标注（稳定前置，不再挂在尾端）===
        env_hint = self._get_environment_hint(context_window)
        messages.append(MessageTurn(
            role="user",
            parts=[MessagePart(type="text", text=env_hint)],
        ))

        # === USER: 压缩上下文（高级 context 的 timeline 摘要 / 普通 context 的较早历史归档）===
        if context_window.owner_type == "normal" and context_window.compressed_summary:
            sanitized_summary = context_window_manager.sanitize_model_output_text(
                context_window.compressed_summary
            )
            messages.append(MessageTurn(
                role="user",
                parts=[MessagePart(
                    type="text",
                    text=f"{sanitized_summary}",
                )],
            ))
        elif context_window.compressed_summary:
            sanitized_summary = context_window_manager.sanitize_model_output_text(
                context_window.compressed_summary
            )
            messages.append(MessageTurn(
                role="user",
                parts=[MessagePart(
                    type="text",
                    text=f"印象，{sanitized_summary}",
                )],
            ))

        # === 历史消息序列 ===
        history = await context_window_manager.get_history(context_window.context_id)

        messages.extend(history)

        cache_hints = {
            "cache_control": "ephemeral",
            "stable_prefix": "system_first_text",
        }
        normalized_cache_domain = str(cache_domain or "").strip()
        if normalized_cache_domain:
            cache_hints["cache_domain"] = normalized_cache_domain

        return GenerationRequest(
            context_id=context_window.context_id,
            model="",  # 由调用方设置
            messages=messages,
            tools=tools,
            temperature=0.7,
            stream=True,
            cache_hints=cache_hints,
        )

    @staticmethod
    def _get_environment_hint(ctx_window: DBContextWindow) -> str:
        """生成对话环境标注"""
        dialog = str(ctx_window.active_dialog_id or "")
        weekday = "一二三四五六日"[datetime.now().weekday()]
        if "group" in dialog:
            return f"当前环境：群聊**请保持距离**发言干练，今天星期{weekday}，CST+0800"
        if ctx_window.owner_type == "advanced" and str(ctx_window.context_id or "") in dialog:
            return f"当前环境：亲昵私聊，今天星期{weekday}，CST+0800"
        return f"当前环境：外人私聊，今天星期{weekday}，CST+0800"


# 全局单例
context_assembler = ContextAssembler()
