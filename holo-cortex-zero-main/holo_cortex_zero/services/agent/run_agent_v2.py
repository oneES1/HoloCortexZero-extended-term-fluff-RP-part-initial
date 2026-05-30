"""新架构的 Agent 编排器

替代旧的 run_agent.py，使用新的上下文窗口 + tool 链架构。
核心流程：
1. 解析上下文窗口（路由高级/普通用户）
2. 更新锚定
3. 检查 tool 链是否正在运行（如果是，只记录消息不触发新回复）
4. 注入消息到上下文窗口
5. 启动 tool 链执行
"""
from __future__ import annotations

import base64
import json
import re
import time
from typing import Any, Optional

from holo_cortex_zero.adapters.interface.schemas.platform import (
    PlatformSendRequest,
    PlatformSendResponse,
    PlatformSendSegment,
    PlatformSendSegmentType,
)
from holo_cortex_zero.adapters.utils import adapter_utils
from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.runtime_identity import get_bot_persona_display_name
from holo_cortex_zero.core.os_env import OsEnv
from holo_cortex_zero.core.proxy_utils import resolve_model_group_proxy
from holo_cortex_zero.models.db_chat_channel import DBChatChannel
from holo_cortex_zero.models.db_context_window import DBContextWindow
from holo_cortex_zero.schemas.agent_ctx import AgentCtx
from holo_cortex_zero.schemas.chat_message import ChatMessage
from holo_cortex_zero.schemas.ir import MessagePart
from holo_cortex_zero.services.agent.resolver import fix_raw_response
from holo_cortex_zero.services.agent.prompt_selector import select_main_system_prompt
from holo_cortex_zero.services.ai_reply import system_ai_reply_service
from holo_cortex_zero.services.advanced_context_mode import advanced_context_mode_service
from holo_cortex_zero.services.bot_backfill_cleanup import bot_backfill_cleanup_service
from holo_cortex_zero.services.context_window.assembler import context_assembler
from holo_cortex_zero.services.context_window.manager import context_window_manager
from holo_cortex_zero.services.message_service import message_service
from holo_cortex_zero.services.system_emoji import system_emoji_service
from holo_cortex_zero.services.the_deep import system_the_deep_service
from holo_cortex_zero.services.system_voice import system_voice_service
from holo_cortex_zero.services.llm.model_group_params import build_model_group_extra_params
from holo_cortex_zero.services.llm.router import detect_model_group_protocol
from holo_cortex_zero.services.tools.chain_executor import tool_chain_executor


_SELF_IMAGE_SYSTEM_TOKEN = "__SYSTEM_SELF_IMAGE__"

_ID_NAME_PATTERN = re.compile(r'\[[\d]+\|[^\]]+\]\s*')
_SYS_MARKER_PATTERN = re.compile(
    r'(?:¥[^¥\n]*¥(?:\d{4}-\d{2}-\d{2}\s+)?\d{2}:\d{2}:\d{2}¥[^¥\n]*¥说：|(?:\d{4}-\d{2}-\d{2}\s+)?\d{2}:\d{2}:\d{2}¥[^¥\n]*¥[^¥\n]*¥说：)'
)


_normal_context_recall_snapshot_by_context: dict[str, str] = {}
_normal_context_recall_trigger_count_by_context: dict[str, int] = {}
async def run_agent_v2(
    chat_key: str,
    chat_message: Optional[ChatMessage] = None,
    ctx: Optional[AgentCtx] = None,
) -> None:
    """新架构的 agent 入口"""
    if not ctx:
        ctx = await AgentCtx.create_by_chat_key(chat_key=chat_key)

    db_channel = await DBChatChannel.get_channel(chat_key=chat_key)
    effective_config = config.model_copy(deep=True)

    # 获取用户 ID（用于路由上下文窗口）
    user_id = ""
    if chat_message:
        user_id = chat_message.platform_userid or chat_message.sender_id
    elif ctx:
        user_id = getattr(ctx, "from_user_id", "") or ""

    # 1. 解析上下文窗口
    context_window = await context_window_manager.resolve_context_window(
        user_id=user_id,
        chat_key=chat_key,
        adapter_key=db_channel.adapter_key,
    )

    # 2. 更新锚定（回复目标切换到当前对话窗口）
    await context_window_manager.update_anchor(
        context_window.context_id,
        chat_key,
    )

    # 3. 检查 tool 链是否正在运行
    if context_window_manager.is_tool_chain_active(context_window.context_id):
        logger.info(
            f"上下文窗口 {context_window.context_id} tool 链运行中，"
            f"消息已记录到 DB，等待下一循环吸收"
        )
        return

    # 4. 注入消息到上下文窗口
    max_inject = 12 if "group" in chat_key else 999
    await bot_backfill_cleanup_service.flush_pending_for_context(
        context_window.context_id,
        reason="before_context_sync",
    )
    await context_window_manager.sync_new_chat_messages(
        context_window.context_id,
        chat_key,
        max_inject=max_inject,
    )

    # 5. 获取模型组配置
    # 关键：模型路由基于上下文窗口，不是对话窗口
    # 高级用户 → 主模型组，不管在哪个对话窗口
    # 普通用户群聊 → 群聊模型组
    # 普通用户私聊 → 私聊免费用户模型组
    model_group = await _resolve_model_group_with_route(
        effective_config, context_window, chat_key, ctx,
    )
    if not model_group.get("api_key"):
        logger.error(f"模型组配置为空或缺少 API key，无法执行 agent: {chat_key}")
        await _send_text_to_chat(chat_key, "⚠️ 模型配置异常，请检查模型组设置。")
        return

    # 6. 获取系统数据（主人格 prompt、印象图、记忆等）
    try:
        setattr(
            ctx,
            "_na_context_window_meta",
            {
                "context_id": str(context_window.context_id or "").strip(),
                "owner_type": str(context_window.owner_type or "").strip(),
                "active_dialog_id": str(context_window.active_dialog_id or "").strip(),
            },
        )
    except Exception:
        pass

    memory_recall_text, memory_recall_meta, recall_recomputed = await _collect_memory_recall_for_context(
        ctx=ctx,
        context_window=context_window,
        trigger_user_id=user_id,
    )
    prompt_items = memory_recall_meta.get("prompt_items") if isinstance(memory_recall_meta, dict) else []
    if recall_recomputed and isinstance(prompt_items, list) and prompt_items:
        memory_delta_source_chat_key = str(context_window.active_dialog_id or chat_key or "").strip()
        memory_delta_source_message_id = (
            f"memory_recall:{chat_message.message_id}"
            if chat_message and getattr(chat_message, "message_id", None)
            else f"memory_recall:{int(time.time())}"
        )
        delta_count, delta_context_msg_id = await context_window_manager.record_memory_recall_delta(
            context_window,
            prompt_items,
            source_chat_key=memory_delta_source_chat_key,
            source_message_id=memory_delta_source_message_id,
        )
        if delta_count:
            logger.info(
                f"run_agent_v2 memory delta injected: ctx={context_window.context_id} "
                f"chat={memory_delta_source_chat_key} items={delta_count} context_msg_id={delta_context_msg_id}"
            )
    elif not recall_recomputed:
        logger.info(
            "run_agent_v2 skip memory delta on cached recall round: ctx=%s owner=%s",
            context_window.context_id,
            context_window.owner_type,
        )
    stage1_topic_mode = memory_recall_meta.get("topic_mode") if isinstance(memory_recall_meta, dict) else {}
    if isinstance(stage1_topic_mode, dict) and str(stage1_topic_mode.get("mode") or "").upper() == "B":
        deep_reason = str(stage1_topic_mode.get("reason") or "").strip()
        if context_window.owner_type == "advanced":
            system_the_deep_service.enable_for_context(
                context_window.context_id,
                source=(f"stage1_topic_mode:B:{deep_reason[:80]}" if deep_reason else "stage1_topic_mode:B"),
            )
            logger.info(
                "Stage1 严肃话题判定命中，已开启 the_deep: "
                f"context_id={context_window.context_id}, chat_key={chat_key}, reason={deep_reason or '<empty>'}"
            )
        else:
            reject_user_id = str(user_id or getattr(ctx, "from_user_id", "") or "").strip() or "unknown"
            reject_text = f"{reject_user_id}请求难度超出对外算力许可范围，标记为风险拒绝请求"
            plt_resp = await _send_text_to_chat(chat_key, reject_text)
            try:
                await context_window_manager.inject_messages(
                    context_window.context_id,
                    [
                        {
                            "role": "assistant",
                            "sender_id": -1,
                            "sender_name": get_bot_persona_display_name(config),
                            "parts": [MessagePart(type="text", text=reject_text)],
                            "source_chat_key": chat_key,
                            "source_message_id": f"risk_reject:{chat_message.message_id if chat_message and chat_message.message_id else int(time.time())}",
                            "msg_type": "bot_reply",
                        }
                    ],
                    max_inject=999,
                )
            except Exception as e:
                logger.error(
                    "普通用户风险拒绝消息注入上下文失败: "
                    f"context_id={context_window.context_id}, chat_key={chat_key}, error={type(e).__name__}: {e}",
                    exc_info=True,
                )
            logger.info(
                "Stage1 严肃话题判定命中普通用户，已风险拒绝并中断: "
                f"context_id={context_window.context_id}, owner_type={context_window.owner_type}, "
                f"chat_key={chat_key}, user_id={reject_user_id}, sent={'yes' if plt_resp else 'no'}, "
                f"reason={deep_reason or '<empty>'}"
            )
            try:
                from holo_cortex_zero.services.memory import auto_memory_service

                auto_memory_service.schedule_trigger_nowait(
                    context_id=context_window.context_id,
                    dialog_chat_key=context_window.active_dialog_id or chat_key,
                    recall_text=memory_recall_text,
                )
            except Exception as e:
                logger.error(f"后台调度 auto_memory 失败(风险拒绝分支): {e}", exc_info=True)
            return
    impression_url, ref_paths_text = await _get_self_image_data(ctx)

    # 7. 构建发送回调（使用正确的 forward_message API）
    # 注意：锚定可能在 tool 链期间切换，所以每次发送都读最新的 active_dialog_id
    async def prepare_reply_text(dialog_key: str, text: str) -> tuple[str, str]:
        actual_key = context_window.active_dialog_id or dialog_key
        delivery_text = _normalize_reply_text_for_delivery(text)
        delivery_text = await message_service.cleanup_bot_edge_echo_text(
            chat_key=actual_key,
            text=delivery_text,
        )
        return actual_key, delivery_text

    async def send_reply(
        dialog_key: str,
        text: str,
        *,
        record_to_db: bool = True,
        precleaned: bool = False,
        reasoning_content: Optional[str] = None,
    ) -> None:
        """发送回复到对话窗口；可选是否记录 bot 消息到 DB。"""
        try:
            if precleaned:
                actual_key = dialog_key or context_window.active_dialog_id
                delivery_text = str(text or "").strip()
            else:
                actual_key, delivery_text = await prepare_reply_text(dialog_key, text)
            if not delivery_text:
                logger.warning(f"发送回复被清洗为空，已跳过: ctx={context_window.context_id} chat={actual_key}")
                return

            if not record_to_db:
                await _send_text_to_chat(actual_key, delivery_text)
                logger.info(
                    f"发送 tool 前导文本到聊天但不写 DB: ctx={context_window.context_id} chat={actual_key}"
                )
                return

            voice_result = await system_voice_service.maybe_dispatch_reply(
                chat_key=actual_key,
                text=delivery_text,
            )
            cleanup_enabled = bot_backfill_cleanup_service.is_enabled()
            if voice_result.sent_as_voice:
                plt_resp = voice_result.response if isinstance(voice_result.response, PlatformSendResponse) else None
                db_message = await message_service.push_bot_message_text_shadow(
                    chat_key=actual_key,
                    text=delivery_text,
                    plt_response=plt_resp,
                )
                if cleanup_enabled:
                    await bot_backfill_cleanup_service.schedule_bot_reply_backfill(
                        context_id=context_window.context_id,
                        text=delivery_text,
                        source_chat_key=actual_key,
                        plt_response=plt_resp,
                        chat_message_db_id=int(getattr(db_message, "id", 0) or 0),
                        reasoning_content=reasoning_content,
                    )
                else:
                    await _bind_latest_assistant_source_message_id(
                        context_id=context_window.context_id,
                        actual_key=actual_key,
                        plt_resp=plt_resp,
                    )
                return

            emoji_result = await system_emoji_service.maybe_dispatch_reply(
                chat_key=actual_key,
                text=delivery_text,
            )
            if emoji_result.sent_with_emoji:
                plt_resp = emoji_result.response if isinstance(emoji_result.response, PlatformSendResponse) else None
                db_message = await message_service.push_bot_message_text_shadow(
                    chat_key=actual_key,
                    text=delivery_text,
                    plt_response=plt_resp,
                )
                if cleanup_enabled:
                    await bot_backfill_cleanup_service.schedule_bot_reply_backfill(
                        context_id=context_window.context_id,
                        text=delivery_text,
                        source_chat_key=actual_key,
                        plt_response=plt_resp,
                        chat_message_db_id=int(getattr(db_message, "id", 0) or 0),
                        reasoning_content=reasoning_content,
                    )
                else:
                    await _bind_latest_assistant_source_message_id(
                        context_id=context_window.context_id,
                        actual_key=actual_key,
                        plt_resp=plt_resp,
                    )
                return

            plt_resp = await _send_text_to_chat(actual_key, delivery_text)
            db_message = await message_service.push_bot_message(
                chat_key=actual_key,
                agent_messages=delivery_text,
                plt_response=plt_resp,
            )
            if cleanup_enabled:
                await bot_backfill_cleanup_service.schedule_bot_reply_backfill(
                    context_id=context_window.context_id,
                    text=delivery_text,
                    source_chat_key=actual_key,
                    plt_response=plt_resp,
                    chat_message_db_id=int(getattr(db_message, "id", 0) or 0),
                    reasoning_content=reasoning_content,
                )
            else:
                await _bind_latest_assistant_source_message_id(
                    context_id=context_window.context_id,
                    actual_key=actual_key,
                    plt_resp=plt_resp,
                )
            return
        except Exception as e:
            logger.error(f"发送回复失败: {e}", exc_info=True)
            return

    async def send_error(dialog_key: str, text: str) -> None:
        """发送错误信息到对话窗口"""
        actual_key = context_window.active_dialog_id or dialog_key
        try:
            await _send_text_to_chat(actual_key, f"⚠️ {text}")
        except Exception as e:
            logger.error(f"发送错误信息失败: {e}")

    # 8. 构建组装器闭包
    # 注意：主人格 prompt 必须在 assemble 时按当前 context_id/the_deep 运行态实时解析。
    # 这样 Stage1 本轮刚开启 the_deep 后，后续首轮请求就能立刻切到 deep prompt，
    # 不会因为 run_agent_v2 入口提前冻结 main_system_prompt 而滞后一轮。
    assemble_prompt_log_state = {
        "selected_prompt_key": "",
        "deep_enabled": None,
    }

    async def assemble_fn(cw: DBContextWindow) -> Any:
        main_system_prompt, selected_prompt_key, deep_prompt_enabled = select_main_system_prompt(cw)
        effective_mode, _mode_source = advanced_context_mode_service.get_effective_mode(cw)
        cache_domain = f"main:{str(cw.owner_type or '').strip() or 'unknown'}:{effective_mode or 'default'}"
        if (
            assemble_prompt_log_state["selected_prompt_key"] != selected_prompt_key
            or assemble_prompt_log_state["deep_enabled"] != deep_prompt_enabled
        ):
            logger.info(
                "run_agent_v2 assemble main prompt resolved: ctx=%s owner_type=%s deep_enabled=%s selected_prompt_key=%s prompt_length=%s",
                cw.context_id,
                cw.owner_type,
                deep_prompt_enabled,
                selected_prompt_key,
                len(main_system_prompt),
            )
            assemble_prompt_log_state["selected_prompt_key"] = selected_prompt_key
            assemble_prompt_log_state["deep_enabled"] = deep_prompt_enabled

        return await context_assembler.assemble(
            cw,
            main_system_prompt=main_system_prompt,
            bot_platform_id=getattr(config, "BOT_QQ", ""),
            platform_name=db_channel.adapter_key,
            impression_image_url=impression_url,
            reference_image_paths_text=ref_paths_text,
            cache_domain=cache_domain,
        )

    # 9. 启动 tool 链
    assembler_obj = type("_Asm", (), {"assemble": staticmethod(assemble_fn)})()

    async def resolve_model_group_for_chain() -> dict:
        return await _resolve_model_group_with_route(
            effective_config,
            context_window,
            chat_key,
            ctx,
        )

    try:
        await tool_chain_executor.run(
            context_window=context_window,
            trigger_chat_key=chat_key,
            assembler=assembler_obj,
            send_reply_fn=send_reply,
            send_error_fn=send_error,
            trigger_context=ctx,
            primary_api_key=model_group.get("api_key", ""),
            primary_base_url=model_group.get("base_url", ""),
            primary_protocol=model_group.get("protocol", "responses"),
            primary_proxy=model_group.get("proxy"),
            primary_model=model_group.get("model", ""),
            primary_extra_params=model_group.get("extra_params") or {},
            primary_group_key=model_group.get("primary_group_key"),
            fallback_group_key=model_group.get("fallback_group_key"),
            fallback_model=model_group.get("fallback_model"),
            fallback_api_key=model_group.get("fallback_api_key"),
            fallback_base_url=model_group.get("fallback_base_url"),
            fallback_protocol=model_group.get("fallback_protocol"),
            fallback_proxy=model_group.get("fallback_proxy"),
            fallback_extra_params=model_group.get("fallback_extra_params") or {},
            model_group_resolver=resolve_model_group_for_chain,
            prepare_reply_text_fn=prepare_reply_text,
            trigger_user_id=user_id,
            trigger_user_name=(
                (chat_message.sender_nickname or chat_message.sender_name) if chat_message else ""
            ),
            trigger_message_text=chat_message.content_text if chat_message else "",
        )
    finally:
        system_the_deep_service.disable_for_context(
            context_window.context_id,
            source="tool_chain_finally",
        )
        try:
            from holo_cortex_zero.services.memory import auto_memory_service

            auto_memory_service.schedule_trigger_nowait(
                context_id=context_window.context_id,
                dialog_chat_key=context_window.active_dialog_id or chat_key,
                recall_text=memory_recall_text,
            )
        except Exception as e:
            logger.error(f"后台调度 auto_memory 失败: {e}", exc_info=True)


# ── 适配器消息发送 ──


def _normalize_reply_text_for_delivery(text: str) -> str:
    normalized = context_window_manager.sanitize_model_output_text(text)
    normalized = fix_raw_response(normalized)
    return _SYS_MARKER_PATTERN.sub('', normalized).strip()


async def _bind_latest_assistant_source_message_id(
    *,
    context_id: str,
    actual_key: str,
    plt_resp: Optional[PlatformSendResponse],
) -> None:
    if plt_resp and plt_resp.message_id:
        from holo_cortex_zero.models.db_context_window import DBContextMessage

        latest = await DBContextMessage.filter(
            context_id=context_id,
            role="assistant",
            msg_type="bot_reply",
            source_message_id="",
        ).order_by("-id").first()
        if latest:
            latest.source_message_id = str(plt_resp.message_id)
            latest.source_chat_key = actual_key
            await latest.save()
        else:
            logger.warning(
                "assistant source_message_id 回写失败: "
                f"ctx={context_id} chat={actual_key} msg_id={plt_resp.message_id}"
            )
    else:
        logger.warning(
            "发送回复后缺少平台 message_id，无法回写 source_message_id: "
            f"ctx={context_id} chat={actual_key}"
        )

async def _send_text_to_chat(
    chat_key: str, text: str
) -> Optional[PlatformSendResponse]:
    """通过适配器发送文本到对话窗口"""
    try:
        text = _normalize_reply_text_for_delivery(text)

        adapter = await adapter_utils.get_adapter_for_chat(chat_key)
        request = PlatformSendRequest(
            chat_key=chat_key,
            segments=[
                PlatformSendSegment(
                    type=PlatformSendSegmentType.TEXT,
                    content=text,
                )
            ],
        )
        return await adapter.forward_message(request)
    except Exception as e:
        logger.error(f"发送文本到 {chat_key} 失败: {e}", exc_info=True)
        return None


# ── 模型组解析（含上下文窗口路由） ──

async def _resolve_model_group_with_route(
    effective_config: Any,
    context_window: DBContextWindow,
    chat_key: str,
    ctx: Any,
) -> dict:
    """解析模型组配置，基于上下文窗口（不是对话窗口）进行路由

    路由逻辑：
    - 高级用户 → 主模型组 USE_MODEL_GROUP，可被系统多模态正则临时切到 MULTIMODAL_MODEL_GROUP
    - 普通用户 → 保留通用 request_route 决策，回复判断已完全由系统 ai_reply 主干负责
    """
    if context_window.owner_type == "advanced":
        system_config = config.model_copy(deep=True)
        mode_selection = advanced_context_mode_service.select_model_group(context_window)
        deep_enabled = mode_selection.mode == "deep"
        multimodal_decision = await system_ai_reply_service.should_route_multimodal_for_context(
            context_window=context_window,
            chat_key=chat_key,
            user_id=context_window.context_id,
        )
        multimodal_route_applied = False
        if multimodal_decision.should_route_multimodal:
            multimodal_group_key = str(getattr(system_config, "MULTIMODAL_MODEL_GROUP", "") or "").strip()
            if multimodal_group_key and multimodal_group_key in getattr(system_config, "MODEL_GROUPS", {}):
                system_config.USE_MODEL_GROUP = multimodal_group_key
                multimodal_route_applied = True
                logger.info(
                    "高级用户多模态正则命中，主模型组切换到多模态组: context_id={} chat_key={} matched_pattern={!r} route_group={} scanned_messages={}",
                    context_window.context_id,
                    chat_key,
                    multimodal_decision.matched_pattern,
                    multimodal_group_key,
                    multimodal_decision.scanned_messages,
                )
            else:
                logger.warning(
                    "高级用户多模态正则命中，但 MULTIMODAL_MODEL_GROUP 无效，保持原主模型组: context_id={} chat_key={} matched_pattern={!r} route_group={!r}",
                    context_window.context_id,
                    chat_key,
                    multimodal_decision.matched_pattern,
                    multimodal_group_key or "<empty>",
                )
        if multimodal_route_applied:
            logger.info(
                "高级用户路由保持多模态优先，跳过高级模式模型组覆盖: context_id={} chat_key={} mode={} mode_source={} matched_pattern={!r}",
                context_window.context_id,
                chat_key,
                mode_selection.mode,
                mode_selection.source,
                multimodal_decision.matched_pattern or "<none>",
            )
        else:
            if mode_selection.model_group_key:
                system_config.USE_MODEL_GROUP = mode_selection.model_group_key
            else:
                logger.warning(
                    "高级 context 模式模型组解析为空，保持 USE_MODEL_GROUP: "
                    f"ctx={context_window.context_id} chat={chat_key} mode={mode_selection.mode} source={mode_selection.source}"
                )
        system_group = _resolve_model_group(system_config)
        if system_group:
            logger.info(
                "模型路由: routing_mode=advanced_context_bound, "
                f"config_scope=system_context_window, context_id={context_window.context_id}, "
                f"chat_key={chat_key}, effective_mode={mode_selection.mode}, mode_source={mode_selection.source}, "
                f"deep_enabled={deep_enabled}, mode_model_group_key={mode_selection.model_group_key}, "
                f"mode_model_group_source={mode_selection.model_group_source}, "
                f"system_use_model_group={getattr(system_config, 'USE_MODEL_GROUP', '')}, "
                f"system_multimodal_model_group={getattr(system_config, 'MULTIMODAL_MODEL_GROUP', '')}, "
                f"system_fallback_model_group={getattr(system_config, 'FALLBACK_MODEL_GROUP', '')}, "
                f"system_the_deep_model_group={getattr(system_config, 'SYSTEM_THE_DEEP_MODEL_GROUP', '')}, "
                f"primary_group={system_group.get('primary_group_key', '')}, "
                f"fallback_group={system_group.get('fallback_group_key', '')}, "
                f"protocol={system_group.get('protocol', '')}, "
                f"multimodal_pattern={repr(multimodal_decision.matched_pattern or '<none>')}, "
                f"multimodal_scanned_messages={multimodal_decision.scanned_messages}"
            )
        else:
            logger.error(
                "高级用户系统主模型解析失败: "
                f"context_id={context_window.context_id}, chat_key={chat_key}, effective_mode={mode_selection.mode}, mode_source={mode_selection.source}"
            )
        return system_group

    # 普通用户：只走系统配置主干，不再保留窗口/频道级覆盖残留
    normal_config = effective_config.model_copy(deep=True)
    if normal_config.NORMAL_USER_MODEL_GROUP:
        normal_config.USE_MODEL_GROUP = normal_config.NORMAL_USER_MODEL_GROUP
    base_group = _resolve_model_group(normal_config)
    if not base_group:
        return {}

    logger.info(
        "模型路由: routing_mode=dialog_window, "
        f"config_scope=dialog_window, chat_key={chat_key}, context_id={context_window.context_id}, "
        f"owner_type={context_window.owner_type}, base_use_model_group={getattr(normal_config, 'USE_MODEL_GROUP', '')}, "
        f"base_fallback_model_group={getattr(normal_config, 'FALLBACK_MODEL_GROUP', '')}, "
        f"primary_group={base_group.get('primary_group_key', '')}, fallback_group={base_group.get('fallback_group_key', '')}, "
        f"protocol={base_group.get('protocol', '')}"
    )
    return base_group


def _resolve_model_group(effective_config: Any) -> dict:
    """解析模型组配置为 dict

    effective_config.MODEL_GROUPS 是 Dict[str, ModelConfigGroup]
    effective_config.USE_MODEL_GROUP 是主模型组的 key
    effective_config.FALLBACK_MODEL_GROUP 是备用模型组的 key
    """
    try:
        groups = effective_config.MODEL_GROUPS  # Dict[str, ModelConfigGroup]
        if not groups:
            return {}

        # 主模型组
        primary_key = str(getattr(effective_config, "USE_MODEL_GROUP", "") or "").strip()
        if not primary_key:
            logger.error("USE_MODEL_GROUP 为空，请在配置中显式指定有效主模型组")
            return {}

        primary = groups.get(primary_key)
        if not primary:
            logger.error(f"找不到主模型组: {primary_key}, 可用组: {list(groups.keys())}")
            return {}

        result = {
            "primary_group_key": str(primary_key or ""),
            "model": primary.CHAT_MODEL,
            "api_key": primary.API_KEY,
            "base_url": primary.BASE_URL,
            "proxy": resolve_model_group_proxy(primary, group_key=str(primary_key or ""), source="agent.primary"),
            "protocol": _detect_protocol(primary),
            "extra_params": build_model_group_extra_params(
                primary,
                source_hint=f"primary:{primary_key}",
            ),
            "fallback_group_key": "",
            "fallback_model": "",
            "fallback_extra_params": {},
        }

        # Fallback 组
        fallback_key = getattr(effective_config, "FALLBACK_MODEL_GROUP", "")
        if fallback_key and fallback_key != primary_key:
            fallback = groups.get(fallback_key)
            if fallback:
                result["fallback_group_key"] = str(fallback_key or "")
                result["fallback_model"] = fallback.CHAT_MODEL
                result["fallback_api_key"] = fallback.API_KEY
                result["fallback_base_url"] = fallback.BASE_URL
                result["fallback_protocol"] = _detect_protocol(fallback)
                result["fallback_proxy"] = resolve_model_group_proxy(
                    fallback,
                    group_key=str(fallback_key or ""),
                    source="agent.fallback",
                )
                result["fallback_extra_params"] = build_model_group_extra_params(
                    fallback,
                    source_hint=f"fallback:{fallback_key}",
                )

        logger.info(
            "模型组解析: "
            f"primary={primary_key}, fallback={result.get('fallback_group_key', '')}, "
            f"model={result['model']}, fallback_model={result.get('fallback_model', '')}, "
            f"base={str(result['base_url'])[:40]}..."
        )
        return result
    except Exception as e:
        logger.error(f"解析模型组配置失败: {e}", exc_info=True)
        return {}


def _detect_protocol(group: Any) -> str:
    """检测模型组应该使用的协议

    主干规则：
    - 优先尊重新增模型组字段 `WIRE_API`。
    - `WIRE_API=default` 时保持当前自动判定逻辑不变。

    分支兼容：
    - 已知 `api.uniapi.io/v1` / `hk.uniapi.io/v1` + `gemini-*` 仍会自动命中 Gemini native relay
    """
    return detect_model_group_protocol(group, allow_legacy_wire_api=False)


# ── 系统数据获取 ──

async def _collect_memory_recall(ctx: AgentCtx) -> tuple[str, dict[str, Any]]:
    """系统层收集 memory recall。"""
    try:
        from holo_cortex_zero.services.memory import collect_memory_recall_with_meta

        return await collect_memory_recall_with_meta(ctx)
    except Exception as e:
        logger.error(f"收集 memory recall 失败: {e}", exc_info=True)
        return "", {}


def _is_normal_context_user_trigger(trigger_user_id: str) -> bool:
    normalized = str(trigger_user_id or "").strip()
    return bool(normalized and normalized not in {"0", "-1"})


async def _collect_memory_recall_for_context(
    *,
    ctx: AgentCtx,
    context_window: DBContextWindow,
    trigger_user_id: str,
) -> tuple[str, dict[str, Any], bool]:
    """按上下文类型收集回忆。

    主干约束：
    - 高级 context 保持现状，每轮实时计算。
    - 普通 context 的 recall 门控只放在编排层，避免污染 memory / auto_memory 主干。
    - 普通 context 命中缓存时不复用旧 topic_mode，避免旧判定误伤。
    """
    from holo_cortex_zero.services.memory import auto_memory_service

    if context_window.owner_type != "normal":
        memory_recall_text, memory_recall_meta = await _collect_memory_recall(ctx)
        try:
            auto_memory_service.update_recall_snapshot(
                context_id=context_window.context_id,
                recall_text=memory_recall_text,
            )
        except Exception as e:
            logger.error(f"缓存 auto_memory recall 快照失败: {e}", exc_info=True)
        return memory_recall_text, memory_recall_meta, True

    if not _is_normal_context_user_trigger(trigger_user_id):
        memory_recall_text, memory_recall_meta = await _collect_memory_recall(ctx)
        _normal_context_recall_snapshot_by_context[context_window.context_id] = str(memory_recall_text or "").strip()
        _normal_context_recall_trigger_count_by_context[context_window.context_id] = 0
        try:
            auto_memory_service.update_recall_snapshot(
                context_id=context_window.context_id,
                recall_text=memory_recall_text,
            )
        except Exception as e:
            logger.error(f"缓存普通 context recall 快照失败: {e}", exc_info=True)
        logger.info(
            "普通 context 非用户触发，直接实时刷新 recall: ctx=%s recall_chars=%s",
            context_window.context_id,
            len(str(memory_recall_text or "")),
        )
        return memory_recall_text, memory_recall_meta, True

    refresh_every = max(1, int(getattr(config, "NORMAL_CONTEXT_MEMORY_RECALL_REFRESH_EVERY", 4) or 4))
    cached_recall_text = str(_normal_context_recall_snapshot_by_context.get(context_window.context_id, "") or "").strip()
    if not cached_recall_text:
        memory_recall_text, memory_recall_meta = await _collect_memory_recall(ctx)
        _normal_context_recall_snapshot_by_context[context_window.context_id] = str(memory_recall_text or "").strip()
        _normal_context_recall_trigger_count_by_context[context_window.context_id] = 0
        try:
            auto_memory_service.update_recall_snapshot(
                context_id=context_window.context_id,
                recall_text=memory_recall_text,
            )
        except Exception as e:
            logger.error(f"缓存普通 context recall 快照失败: {e}", exc_info=True)
        logger.info(
            "普通 context recall 缓存缺失，已立即刷新: ctx=%s refresh_every=%s recall_chars=%s",
            context_window.context_id,
            refresh_every,
            len(str(memory_recall_text or "")),
        )
        return memory_recall_text, memory_recall_meta, True

    trigger_count = int(_normal_context_recall_trigger_count_by_context.get(context_window.context_id, 0) or 0) + 1
    if trigger_count < refresh_every:
        _normal_context_recall_trigger_count_by_context[context_window.context_id] = trigger_count
        logger.info(
            "普通 context recall 复用缓存: ctx=%s trigger_count=%s refresh_every=%s recall_chars=%s",
            context_window.context_id,
            trigger_count,
            refresh_every,
            len(cached_recall_text),
        )
        return cached_recall_text, {}, False

    memory_recall_text, memory_recall_meta = await _collect_memory_recall(ctx)
    _normal_context_recall_snapshot_by_context[context_window.context_id] = str(memory_recall_text or "").strip()
    _normal_context_recall_trigger_count_by_context[context_window.context_id] = 0
    try:
        auto_memory_service.update_recall_snapshot(
            context_id=context_window.context_id,
            recall_text=memory_recall_text,
        )
    except Exception as e:
        logger.error(f"刷新普通 context recall 快照失败: {e}", exc_info=True)
    logger.info(
        "普通 context recall 达到刷新阈值，已重算: ctx=%s refresh_every=%s recall_chars=%s",
        context_window.context_id,
        refresh_every,
        len(str(memory_recall_text or "")),
    )
    return memory_recall_text, memory_recall_meta, True


def _get_self_image_system_root() -> Any:
    """返回自设图系统资产根目录。"""
    from pathlib import Path

    return (Path(OsEnv.WORKSPACE_ROOT) / "self_image").resolve()


def _expand_self_image_path(raw_path: str) -> str:
    """展开系统自设图配置中的内置 token。

    主干约束：
    - 只接受系统自设图路径
    """
    text = str(raw_path or "").strip()
    if not text:
        return ""
    if text.startswith(_SELF_IMAGE_SYSTEM_TOKEN):
        return text.replace(_SELF_IMAGE_SYSTEM_TOKEN, str(_get_self_image_system_root()), 1)
    return text


def _resolve_self_image_host_path(ctx: AgentCtx, raw_path: str) -> Any:
    """将系统自设图配置路径解析为宿主机可访问路径。"""
    from pathlib import Path

    from holo_cortex_zero.services.file_system.service import managed_file_service

    expanded = _expand_self_image_path(raw_path)
    if not expanded or expanded.startswith(("http://", "https://", "data:")):
        return None

    if not expanded.startswith("/"):
        expanded = str((_get_self_image_system_root() / expanded).resolve())

    resolved_path, _path_kind = managed_file_service.resolve_outbound_local_path(
        expanded,
        chat_key=ctx.chat_key,
        container_key=getattr(ctx, "container_key", None),
    )
    if resolved_path:
        path_obj = Path(resolved_path)
        if path_obj.exists():
            return path_obj

    direct_path = Path(expanded)
    if direct_path.exists():
        return direct_path
    return None


async def _get_self_image_data(ctx: AgentCtx) -> tuple[Optional[str], str]:
    """系统级读取自设图配置，不再依赖旧外挂包或历史配置文件。

    Returns:
        (impression_data_uri, ref_paths_text)
    """
    import base64
    import mimetypes

    cfg: dict[str, Any] = {
        "ENABLE": bool(getattr(config, "SELF_IMAGE_ENABLE", True)),
        "ENABLE_AUTO_IMPRESSION_INJECT": bool(getattr(config, "SELF_IMAGE_ENABLE_AUTO_IMPRESSION_INJECT", True)),
        "ENABLE_DIRECT_PATH_PROMPT": bool(getattr(config, "SELF_IMAGE_ENABLE_DIRECT_PATH_PROMPT", True)),
        "IMPRESSION_IMAGE_PATH": str(getattr(config, "SELF_IMAGE_IMPRESSION_IMAGE_PATH", f"{_SELF_IMAGE_SYSTEM_TOKEN}/内置印象图.webp") or "").strip(),
        "BOT_PERSONA_IMAGE_PATH": str(getattr(config, "SELF_IMAGE_BOT_PERSONA_IMAGE_PATH", f"{_SELF_IMAGE_SYSTEM_TOKEN}/HCZ.webp") or "").strip(),
        "USER_DAILY_IMAGE_PATH": str(getattr(config, "SELF_IMAGE_USER_DAILY_IMAGE_PATH", f"{_SELF_IMAGE_SYSTEM_TOKEN}/user_daily.webp") or "").strip(),
        "USER_PORTRAIT_IMAGE_PATH": str(getattr(config, "SELF_IMAGE_USER_PORTRAIT_IMAGE_PATH", f"{_SELF_IMAGE_SYSTEM_TOKEN}/user_portrait.webp") or "").strip(),
    }

    try:
        context_window_meta = getattr(ctx, "_na_context_window_meta", {}) or {}
        context_owner_type = str(context_window_meta.get("owner_type") or "").strip().lower()
        allow_direct_path_prompt = bool(cfg.get("ENABLE_DIRECT_PATH_PROMPT", True)) and context_owner_type == "advanced"

        if not bool(cfg.get("ENABLE", True)):
            logger.info("自设图系统能力已关闭: SELF_IMAGE_ENABLE=false")
            return None, ""

        impression_uri: Optional[str] = None

        if bool(cfg.get("ENABLE_AUTO_IMPRESSION_INJECT", True)):
            raw_impression = str(cfg.get("IMPRESSION_IMAGE_PATH") or "").strip()
            expanded_impression = _expand_self_image_path(raw_impression)
            try:
                if expanded_impression.startswith(("http://", "https://", "data:")):
                    impression_uri = expanded_impression
                else:
                    host_path = _resolve_self_image_host_path(ctx, raw_impression)
                    if not host_path:
                        raise FileNotFoundError(expanded_impression or raw_impression)
                    mime = mimetypes.guess_type(str(host_path))[0] or "image/png"
                    b64 = base64.b64encode(host_path.read_bytes()).decode("ascii")
                    impression_uri = f"data:{mime};base64,{b64}"
            except Exception as e:
                logger.warning(f"自设图系统印象图读取失败: {e}")

        ref_text = ""
        if allow_direct_path_prompt:
            exported_paths: list[str] = []
            for role_key, attr_name in [
                ("bot_persona", "BOT_PERSONA_IMAGE_PATH"),
                ("user_daily", "USER_DAILY_IMAGE_PATH"),
                ("user_portrait", "USER_PORTRAIT_IMAGE_PATH"),
            ]:
                raw = str(cfg.get(attr_name) or "").strip()
                if not raw:
                    continue
                try:
                    expanded = _expand_self_image_path(raw)
                    if expanded.startswith(("http://", "https://", "data:")):
                        exported_path = expanded
                    else:
                        host_path = _resolve_self_image_host_path(ctx, raw)
                        if not host_path:
                            raise FileNotFoundError(expanded)
                        exported_path = str(host_path)
                    exported_paths.append(exported_path)
                except Exception as e:
                    logger.warning(f"自设图参考路径导出失败: {role_key}: {e}")

            if exported_paths:
                ref_text = "印象图调用路径，绘图等可用：" + "  ".join(exported_paths)
        elif bool(cfg.get("ENABLE_DIRECT_PATH_PROMPT", True)):
            logger.info(
                "自设图直传路径提示已跳过: owner_type=%s, chat=%s",
                context_owner_type or "unknown",
                getattr(ctx, "chat_key", ""),
            )

        logger.info(
            "自设图系统集成加载完成: "
            f"impression={'yes' if impression_uri else 'no'}, "
            f"ref_paths={'yes' if ref_text else 'no'}, "
            f"asset_root={_get_self_image_system_root()}"
        )
        return impression_uri, ref_text
    except Exception as e:
        logger.error(f"自设图系统集成获取失败: {e}", exc_info=True)
        return None, ""
