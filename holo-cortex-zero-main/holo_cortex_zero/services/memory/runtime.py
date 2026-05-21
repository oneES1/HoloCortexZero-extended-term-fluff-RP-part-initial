import time
import json
import re
from typing import Any, Dict, List, Optional
import asyncio
import heapq
from collections import defaultdict
from typing import Tuple
import inspect
from datetime import datetime, timedelta, timezone
from dateutil import parser

from holo_cortex_zero.api.schemas import AgentCtx
from holo_cortex_zero.core import config as core_config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.runtime_identity import (
    get_bot_persona_display_name,
    get_primary_advanced_user_display_name,
    get_primary_advanced_user_id,
)
from holo_cortex_zero.models.db_chat_channel import DBChatChannel
from holo_cortex_zero.models.db_chat_message import DBChatMessage
from .mem0_output_formatter import (
    format_add_output,
    format_get_all_output,
    format_history_output,
    format_search_output,
    _coerce_list,
    _filter_by_tags,
    _filter_by_score,
    format_prompt_grouped_memories,
)
from .mem0_utils import get_mem0_client, analyze_memory_conflict
from holo_cortex_zero.core.config import CoreConfig as MemoryConfig

from .context_env import build_memory_dialog_env_from_ctx
from .graph_cache import graph_cache, HCZ_SELF
from .payload_logs import dump_memory_json
from .subconscious import run_subconscious
from .utils import decode_id


FIXED_MEM0_AGENT_ID = "default"

def _to_plain_text(raw: Any, *, strict: bool = False, max_len: int = 2000) -> str:
    """将任意输入归一为可安全入库的纯文本。"""
    text = str(raw or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    # 兼容模型常见双重转义
    text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    # 去掉不可见控制字符
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", text)
    text = text.replace("\u200b", "").replace("\ufeff", "")

    if strict:
        # 严格兜底：仅保留中英数字、空白与常见自然语言标点
        text = re.sub(r"[^0-9A-Za-z_\u4e00-\u9fff \n，。！？；：、,.!?;:()（）《》“”‘’\-_/+]", " ", text)
    else:
        # 轻量清洗：去掉高风险结构符号，尽量不损失语义
        text = re.sub(r"[`$^|<>{}\[\]]", " ", text)

    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    if max_len > 0 and len(text) > max_len:
        text = text[:max_len].rstrip()
    return text


def _sanitize_metadata_for_storage(metadata: Any, *, strict: bool = False) -> Dict[str, Any]:
    """清洗 metadata，避免特殊符号或复杂对象导致入库异常。"""
    if not isinstance(metadata, dict):
        return {}

    cleaned: Dict[str, Any] = {}
    for k, v in metadata.items():
        key = _to_plain_text(k, strict=True, max_len=64)
        if not key:
            continue

        if isinstance(v, (bool, int, float)) or v is None:
            cleaned[key] = v
            continue

        if isinstance(v, (list, tuple, set)):
            items: List[str] = []
            for item in v:
                s = _to_plain_text(item, strict=strict, max_len=256)
                if s:
                    items.append(s)
            if items:
                cleaned[key] = items[:20]
            continue

        cleaned_val = _to_plain_text(v, strict=strict, max_len=512)
        if cleaned_val:
            cleaned[key] = cleaned_val

    return cleaned


def _is_true_system_db_chat_message(msg: Any) -> bool:
    """识别 DBChatMessage 中的真正系统消息。"""
    sender_id = str(getattr(msg, "sender_id", "") or "").strip()
    if sender_id != "-1":
        return False

    platform_userid = str(getattr(msg, "platform_userid", "") or "").strip()
    sender_name = str(getattr(msg, "sender_name", "") or "").strip().upper()
    sender_nickname = str(getattr(msg, "sender_nickname", "") or "").strip().upper()
    return platform_userid == "0" or (sender_name == "SYSTEM" and sender_nickname == "SYSTEM")


def _stage1_sender_id(msg: Any) -> str:
    """为 Stage1 暴露稳定主体 ID；bot 回复统一映射为 HCZ_SELF。"""
    if _is_true_system_db_chat_message(msg):
        return ""

    sender_id = str(getattr(msg, "sender_id", "") or "").strip()
    if sender_id == "-1":
        return HCZ_SELF
    return sender_id


def _get_mem0_run_id(_ctx: AgentCtx, *, memory_config: "MemoryConfig") -> Optional[str]:
    """获取 mem0 run_id。

    当前主干固定为全局记忆分区，run_id 始终关闭。
    保留函数仅为兼容现有调用点。
    """
    return None


async def _get_mem0_agent_id(_ctx: AgentCtx, *, is_self: bool, memory_config: "MemoryConfig") -> Optional[str]:
    """获取 mem0 agent_id（记忆仲裁/检索使用）。

    当前主干固定绑定到核心 bot 的 default 分区。
    保留函数仅为兼容现有调用点。
    """
    return FIXED_MEM0_AGENT_ID


# =========================
# 背景写入队列(方案 C)
# =========================
# 目标：add_memory 调用即刻返回，不阻塞 agent 主流程
# 代价：写入变为最终一致(可能稍后才落库)，失败只能靠日志观测

_memory_write_queue: "asyncio.Queue[Tuple[AgentCtx, str, str, Dict[str, Any]]]" = asyncio.Queue()
_memory_worker_task: Optional[asyncio.Task] = None


def _memory_log_preview(memory: Any, limit: int = 160) -> str:
    raw = str(memory or "")
    if len(raw) <= limit:
        return raw
    return raw[:limit] + "...(truncated)"


def _memory_log_metadata(metadata: Dict[str, Any]) -> str:
    try:
        return json.dumps(metadata, ensure_ascii=False, default=str)
    except Exception:
        return repr(metadata)


def _log_add_memory_event(event: str, *, _ctx: AgentCtx, user_id: str, metadata: Dict[str, Any], memory: Any) -> None:
    _dump_add_memory_log(
        kind="event",
        stage=event,
        _ctx=_ctx,
        user_id=user_id,
        metadata=metadata,
        memory=memory,
        detail="",
    )
    logger.info(
        f"🧠 [海菜子记忆库] {event} chat_key={getattr(_ctx, 'chat_key', None)} user_id={user_id} "
        f"metadata={_memory_log_metadata(metadata)} memory_preview={_memory_log_preview(memory)!r} "
        f"queue_size={_memory_write_queue.qsize()}"
    )


def _log_add_memory_final(status: str, *, _ctx: AgentCtx, user_id: str, metadata: Dict[str, Any], memory: Any, detail: str = "") -> None:
    _dump_add_memory_log(
        kind="final",
        stage=status,
        _ctx=_ctx,
        user_id=user_id,
        metadata=metadata,
        memory=memory,
        detail=detail,
    )
    logger.info(
        f"🧠 [海菜子记忆库] add_memory_final status={status} chat_key={getattr(_ctx, 'chat_key', None)} "
        f"user_id={user_id} metadata={_memory_log_metadata(metadata)} "
        f"memory_preview={_memory_log_preview(memory)!r} detail={detail}"
    )


def _dump_add_memory_log(
    *,
    kind: str,
    stage: str,
    _ctx: AgentCtx,
    user_id: str,
    metadata: Dict[str, Any],
    memory: Any,
    detail: str,
) -> None:
    try:
        env = build_memory_dialog_env_from_ctx(_ctx)
    except Exception:
        env = None
    from holo_cortex_zero.services.context_window.manager import context_window_manager

    sanitized_from_user_name = context_window_manager._sanitize_sender_name_for_context(
        str(getattr(_ctx, "from_user_id", "") or ""),
        str(getattr(_ctx, "from_user_name", "") or ""),
    )

    dump_memory_json(
        "write",
        kind,
        {
            "kind": f"memory_write_{kind}",
            "stage": stage,
            "user_id": str(user_id or ""),
            "metadata": metadata,
            "memory": str(memory or ""),
            "detail": detail,
            "chat_key": str(getattr(_ctx, "chat_key", "") or ""),
            "from_chat_key": str(getattr(_ctx, "from_chat_key", "") or ""),
            "from_user_id": str(getattr(_ctx, "from_user_id", "") or ""),
            "from_user_name": sanitized_from_user_name,
            "adapter_key": str(getattr(_ctx, "adapter_key", "") or ""),
            "channel_type": str(getattr(_ctx, "channel_type", "") or ""),
            "channel_id": str(getattr(_ctx, "channel_id", "") or ""),
            "dialog_env": {
                "chat_env_system": str(getattr(env, "chat_env_system", "") or ""),
                "chat_env_note": str(getattr(env, "chat_env_note", "") or ""),
                "source_chat_key": str(getattr(env, "source_chat_key", "") or ""),
            },
        },
    )


async def _add_memory_impl(_ctx: AgentCtx, memory: str, user_id: str, metadata: Dict[str, Any]) -> None:
    """原 add_memory 的实际实现(被 worker 调用)"""
    mem0 = await get_mem0_client()
    memory_config: MemoryConfig = core_config
    if not mem0:
        logger.error("无法获取 mem0 客户端实例，无法添加记忆")
        return

    # 入库前先做轻量纯文本清洗，防止特殊符号污染持久化层
    memory = _to_plain_text(memory, strict=False, max_len=2000)
    metadata = _sanitize_metadata_for_storage(metadata, strict=False)
    user_id = str(user_id or "").strip()
    if not memory:
        logger.warning("⚠️ [海菜子记忆库] memory 为空(清洗后)，已跳过写入")
        return
    if not user_id:
        logger.warning("⚠️ [海菜子记忆库] user_id 为空，已跳过写入")
        return

    # ====== 高级用户强制匹配（受保护别名映射纠偏） ======
    # 只在“关系图谱”写入场景做硬纠偏，避免把错误 alias->ID 写进 HCZ_SELF 图谱缓存/记忆库。
    try:
        primary_advanced_user_id = get_primary_advanced_user_id(memory_config)
        primary_advanced_user_display_name = get_primary_advanced_user_display_name(memory_config)
        md_type_norm = str(metadata.get("type") or metadata.get("TYPE") or "").strip().lower()
        if md_type_norm in {"relation_map", "relationmap", "relation"}:
            alias = str(metadata.get("alias") or metadata.get("name") or "").strip()
            if alias == primary_advanced_user_display_name:
                target = str(metadata.get("target") or metadata.get("target_id") or "").strip()
                if target != primary_advanced_user_id:
                    metadata = dict(metadata)
                    metadata["target"] = primary_advanced_user_id
                    if "target_id" in metadata:
                        metadata["target_id"] = primary_advanced_user_id
                    if isinstance(memory, str) and (primary_advanced_user_display_name in memory) and ("->" in memory):
                        memory = re.sub(
                            rf"({re.escape(primary_advanced_user_display_name)}\s*->\s*)\d+",
                            rf"\g<1>{primary_advanced_user_id}",
                            memory,
                        )
    except Exception:
        pass

    # ====== 分区策略(非常重要) ======
    # 当前主干：所有分区统一使用全局 run_id=None + agent_id=default。
    is_self = str(user_id or "").strip() == HCZ_SELF

    run_id: Optional[str] = _get_mem0_run_id(_ctx, memory_config=memory_config)

    # 记忆仲裁逻辑 (Memory Arbitration)
    agent_id: Optional[str] = await _get_mem0_agent_id(_ctx, is_self=is_self, memory_config=memory_config)

    # 兼容性：不同 mem0 版本对 add(...) 的参数可能不一致(例如 infer=True/False)
    # 我们用一次性 signature 探测，支持则传 infer=False，不支持则不传，保证线上“写入不崩”
    _supports_infer: Optional[bool] = getattr(_add_memory_impl, "_supports_infer", None)  # type: ignore[attr-defined]
    if _supports_infer is None:
        try:
            sig = inspect.signature(mem0.add)
            _supports_infer = "infer" in sig.parameters
        except Exception:
            # 保守策略：探测失败时，默认支持(若不支持，后续会在调用时报 TypeError，再二次兜底)
            _supports_infer = True
        setattr(_add_memory_impl, "_supports_infer", _supports_infer)  # type: ignore[attr-defined]

    async def _mem0_add(*, content: str, metadata_payload: Optional[Dict[str, Any]] = None) -> Any:
        kwargs: Dict[str, Any] = {
            "user_id": user_id,
            "agent_id": agent_id,
            "run_id": run_id,
            "metadata": metadata if metadata_payload is None else metadata_payload,
        }
        if _supports_infer:
            kwargs["infer"] = False
        try:
            return await mem0.add(content, **kwargs)
        except TypeError:
            # 二次兜底：如果我们误判支持 infer(或 mem0 版本变更)，去掉 infer 重试一次
            if "infer" in kwargs:
                kwargs.pop("infer", None)
                try:
                    setattr(_add_memory_impl, "_supports_infer", False)  # type: ignore[attr-defined]
                except Exception:
                    pass
                return await mem0.add(content, **kwargs)
            raise

    async def _mem0_add_safe(*, content: str) -> Any:
        """入库兜底：失败时降级为严格纯文本 + 清洗 metadata 再试一次。"""
        try:
            return await _mem0_add(content=content)
        except Exception as e:
            strict_content = _to_plain_text(content, strict=True, max_len=2000)
            strict_metadata = _sanitize_metadata_for_storage(metadata, strict=True)
            if not strict_content:
                strict_content = "空白记忆"

            if strict_content == content and strict_metadata == metadata:
                raise

            logger.warning(
                "⚠️ [海菜子记忆库] 首次入库失败，启用纯文本兜底重试: user_id=%s err=%r content_preview=%r",
                user_id,
                e,
                strict_content[:160],
            )
            return await _mem0_add(content=strict_content, metadata_payload=strict_metadata)

    # 1. 搜索相关记忆
    existing_memories = await mem0.search(
        memory,
        user_id=user_id,
        agent_id=agent_id,
        run_id=run_id,
        limit=24,  # 限制召回数量
    )

    # 转换 mem0 search 结果为字典列表 (如果它是对象)
    raw_results = []
    if isinstance(existing_memories, dict) and "results" in existing_memories:
        raw_results = existing_memories["results"]
    elif isinstance(existing_memories, list):
        raw_results = existing_memories

    # 手动过滤相似度 (阈值 0.35)
    existing_memories_list = []
    for item in raw_results:
        score = item.get("score")
        if score is not None:
            try:
                if float(score) >= 0.74:
                    existing_memories_list.append(item)
            except (ValueError, TypeError):
                # 如果没有分数或转换失败，保守起见保留它
                existing_memories_list.append(item)
        else:
            existing_memories_list.append(item)

    # 2. 如果没有相关记忆，直接添加
    if not existing_memories_list:
        # 重要：关闭 mem0 的 infer 流程
        # mem0 1.1.x 当前在 async infer 分支存在 UnboundLocalError：
        # `new_memories_with_actions referenced before assignment`(当 fact extraction 为空时触发)
        # 我们在框架侧已经做了记忆原子化与仲裁，因此不依赖 mem0 的推理拆解
        res = await _mem0_add_safe(content=memory)
        msg = format_add_output(res)
        logger.info(f"✨ [海菜子记忆库] 新增记忆 (无冲突): {msg}")
        _log_add_memory_final("added_no_conflict", _ctx=_ctx, user_id=user_id, metadata=metadata, memory=memory, detail=msg)

        # Phase B: 写穿更新图谱缓存(仅内存，不落库，不影响主流程)
        try:
            if getattr(memory_config, "SUBCONSCIOUS_ENABLE", True):
                graph_cache.write_through_from_memory(metadata)
        except Exception:
            pass
        return

    # 3. 召唤 DeepSeek 仲裁官
    logger.info(f"🤔 [记忆仲裁] 正在分析新记忆与 {len(existing_memories_list)} 条现有记忆的关系...")
    decision = await analyze_memory_conflict(memory, existing_memories_list, user_id=user_id, metadata=metadata, ctx=_ctx)
    action = decision.get("action", "ADD")

    # 图谱类写入(relation_map / knowledge_index)必须保证落库，避免冷启动 HCZ_SELF 为空
    # 即使 LLM 仲裁“发疯”给了 REJECT，也在代码层强制改为 ADD
    try:
        md_type = (metadata.get("type") or metadata.get("TYPE") or "").strip().lower()
        if md_type in {"relation_map", "relationmap", "relation", "knowledge_index", "knowledgeindex", "knowledge"}:
            if action == "REJECT":
                logger.warning("⚠️ [记忆仲裁] 图谱写入不允许 REJECT，已强制改为 ADD")
                action = "ADD"
    except Exception:
        pass

    if action == "REJECT":
        reason = decision.get("reason", "无理由")
        logger.info(f"🛑 [记忆仲裁] 拒绝重复记忆: {reason}")
        _log_add_memory_final("rejected", _ctx=_ctx, user_id=user_id, metadata=metadata, memory=memory, detail=str(reason))
        return

    elif action == "UPDATE":
        targets = decision.get("targets", [])
        new_content = _to_plain_text(decision.get("new_content", memory), strict=False, max_len=2000) or memory
        reason = decision.get("reason", "记忆合并更新")

        # 删除旧记忆
        if targets:
            for old_id in targets:
                try:
                    await mem0.delete(old_id)
                except Exception as e:
                    logger.warning(f"删除旧记忆 {old_id} 失败: {e}")

        # 添加新记忆 (合并后的)
        res = await _mem0_add_safe(content=new_content)
        msg = format_add_output(res)
        logger.info(f"🔄 [记忆仲裁] 记忆已进化 (Reason: {reason}): {msg}")
        _log_add_memory_final("updated", _ctx=_ctx, user_id=user_id, metadata=metadata, memory=new_content, detail=f"reason={reason}; {msg}")

        # Phase B: 写穿更新图谱缓存(仅内存，不落库，不影响主流程)
        try:
            if getattr(memory_config, "SUBCONSCIOUS_ENABLE", True):
                graph_cache.write_through_from_memory(metadata)
        except Exception:
            pass

    else:  # ADD
        res = await _mem0_add_safe(content=memory)
        msg = format_add_output(res)
        logger.info(f"✨ [海菜子记忆库] 新增记忆 (仲裁通过): {msg}")
        _log_add_memory_final("added", _ctx=_ctx, user_id=user_id, metadata=metadata, memory=memory, detail=msg)

        # Phase B: 写穿更新图谱缓存(仅内存，不落库，不影响主流程)
        try:
            if getattr(memory_config, "SUBCONSCIOUS_ENABLE", True):
                graph_cache.write_through_from_memory(metadata)
        except Exception:
            pass


async def _memory_worker() -> None:
    """后台消费队列，顺序写入"""
    while True:
        _ctx, memory, user_id, metadata = await _memory_write_queue.get()
        try:
            _log_add_memory_event("add_memory_worker_consume", _ctx=_ctx, user_id=user_id, metadata=metadata, memory=memory)
            await _add_memory_impl(_ctx, memory, user_id, metadata)
        except Exception as e:
            # 重要：这里必须打印完整 traceback
            # 目前线上仅看到 `Invalid format specifier` 字符串，无法定位是 mem0 抛错还是 logger 格式化抛错
            # 使用 logger.exception 让我们拿到堆栈，再针对性修
            try:
                logger.exception(
                    "❌ [海菜子记忆库] 后台写入失败 (worker exception). "
                    "ctx_chat_key=%s user_id=%s metadata=%s memory_preview=%r",
                    getattr(_ctx, "chat_key", None),
                    user_id,
                    metadata,
                    (str(memory)[:200] + "..." if isinstance(memory, str) and len(memory) > 200 else memory),
                )
            except Exception:
                # 兜底：极端情况下 logger 本身也可能因格式化崩溃，确保 worker 不会死循环崩掉
                try:
                    logger.error("❌ [海菜子记忆库] 后台写入失败 (logger.exception fallback): %r", e)
                except Exception:
                    pass
        finally:
            _memory_write_queue.task_done()


def _ensure_memory_worker_started() -> None:
    global _memory_worker_task
    if _memory_worker_task is None or _memory_worker_task.done():
        _memory_worker_task = asyncio.create_task(_memory_worker())


async def initialize_memory_runtime() -> None:
    """初始化记忆运行时"""
    global _mem0_instance, _last_config_hash
    await get_mem0_client()

    # Phase B: Stage0 图谱缓存热加载(best-effort，不影响启动)
    try:
        cfg: MemoryConfig = core_config
        if not getattr(cfg, "SUBCONSCIOUS_ENABLE", True):
            return

        # 调整缓存容量(默认 15，可配置)
        cache_size = int(getattr(cfg, "SUBCONSCIOUS_CACHE_SIZE", 15) or 15)
        if cache_size <= 0:
            cache_size = 15
        graph_cache.set_cache_size(cache_size)

        mem0 = await get_mem0_client()
        load_limit = min(cache_size, 50)
        logger.info(
            "🧠 [Stage0] 图谱缓存热加载开始: "
            f"scope=user_id:{HCZ_SELF} agent_id:{FIXED_MEM0_AGENT_ID} run_id:none limit={load_limit}"
        )
        await graph_cache.load_hot_data_from_mem0(
            mem0,
            user_id=HCZ_SELF,
            agent_id=FIXED_MEM0_AGENT_ID,
            run_id=None,
            limit=load_limit,
        )

        logger.info(
            "🧠 [Stage0] 图谱缓存热加载完成: "
            f"scope=user_id:{HCZ_SELF} agent_id:{FIXED_MEM0_AGENT_ID} run_id:none "
            f"cache_size={cache_size}, relations={len(graph_cache.snapshot().relations)}, concepts={len(graph_cache.snapshot().concepts)}"
        )
    except Exception as e:
        logger.warning(f"⚠️ [Stage0] 图谱缓存热加载失败(忽略，不影响启动): {e}")


async def add_memory(_ctx: AgentCtx, memory: str, user_id: str, metadata: Dict[str, Any]) -> None:
    # 方案 C：进入后台队列，立即返回
    memory = _to_plain_text(memory, strict=False, max_len=2000)
    metadata = _sanitize_metadata_for_storage(metadata, strict=False)
    user_id = str(user_id or "").strip()
    if not memory:
        logger.warning("⚠️ [海菜子记忆库] add_memory 忽略空内容(清洗后为空)")
        return
    if not user_id:
        logger.warning("⚠️ [海菜子记忆库] add_memory 忽略空 user_id")
        return

    _ensure_memory_worker_started()
    try:
        _memory_write_queue.put_nowait((_ctx, memory, user_id, metadata))
        _log_add_memory_event("add_memory_enqueue_success", _ctx=_ctx, user_id=user_id, metadata=metadata, memory=memory)
    except Exception as e:
        logger.exception(f"❌ [海菜子记忆库] 入队失败，已放弃本次写入: {e}")
        raise RuntimeError("add_memory enqueue failed") from e
    return

async def inject_memory_prompt(_ctx: AgentCtx) -> str:
    try:
        _ctx._na_memory_recall_meta = {}
    except Exception:
        pass
    # 重要：在群聊@/转发等场景下，_ctx.chat_key 与 _ctx.from_chat_key 可能不同；
    # recent_messages 必须从“来源 chat_key”取，否则会出现“无有效对话”导致 Stage1 潜意识误判。
    _ctx_chat_key = str(getattr(_ctx, "chat_key", "") or "").strip()
    _ctx_from_chat_key = str(getattr(_ctx, "from_chat_key", "") or "").strip()
    _context_chat_key = _ctx_from_chat_key or _ctx_chat_key

    db_chat_channel: DBChatChannel = await DBChatChannel.get_channel(
        chat_key=_context_chat_key,
    )
    
    # 获取最近消息,用于识别用户和上下文
    raw_recent_messages: List[DBChatMessage] = await (
        DBChatMessage.filter(
            send_timestamp__gte=int(db_chat_channel.conversation_start_time.timestamp()),
            chat_key=_context_chat_key,
        )
        .order_by("-send_timestamp")
        .limit(core_config.AI_CHAT_CONTEXT_MAX_LENGTH * 3)
    )
    try:
        setattr(
            _ctx,
            "_na_recent_messages_prefetch",
            {
                "chat_key": _context_chat_key,
                "messages": raw_recent_messages,
                "fetched_at": time.monotonic(),
            },
        )
    except Exception:
        pass
    recent_messages = [
        msg
        for msg in raw_recent_messages
        if str(getattr(msg, "sender_id", "") or "").strip() != "0" and not _is_true_system_db_chat_message(msg)
    ]  # 去除真正的系统发言，但保留 bot 自己的回复供 Stage1 观察
    recent_messages = recent_messages[: core_config.AI_CHAT_CONTEXT_MAX_LENGTH]

    # 兜底：如果来源 chat_key 拿不到历史（常见于某些适配器/路由字段未同步），再尝试用 _ctx.chat_key。
    # 这样能避免 Stage1/Stage2 全链路都因 recent_messages 为空而退化。
    if not recent_messages and _ctx_chat_key and _context_chat_key != _ctx_chat_key:
        try:
            _fallback_channel: DBChatChannel = await DBChatChannel.get_channel(chat_key=_ctx_chat_key)
            raw_recent_messages = await (
                DBChatMessage.filter(
                    send_timestamp__gte=int(_fallback_channel.conversation_start_time.timestamp()),
                    chat_key=_ctx_chat_key,
                )
                .order_by("-send_timestamp")
                .limit(core_config.AI_CHAT_CONTEXT_MAX_LENGTH * 3)
            )
            try:
                setattr(
                    _ctx,
                    "_na_recent_messages_prefetch",
                    {
                        "chat_key": _ctx_chat_key,
                        "messages": raw_recent_messages,
                        "fetched_at": time.monotonic(),
                    },
                )
            except Exception:
                pass
            recent_messages = [
                msg
                for msg in raw_recent_messages
                if str(getattr(msg, "sender_id", "") or "").strip() != "0" and not _is_true_system_db_chat_message(msg)
            ]
            recent_messages = recent_messages[: core_config.AI_CHAT_CONTEXT_MAX_LENGTH]
            _context_chat_key = _ctx_chat_key
        except Exception:
            pass

    #获取所有发言用户
    user_ids = set()

    for msg in recent_messages:
        stage1_sender_id = _stage1_sender_id(msg)
        if stage1_sender_id:
            user_ids.add(stage1_sender_id)
    
    user_id_list = list(user_ids)

    # ====== 最高System指令：当前聊天环境（供记忆写入/检索纠偏） ======
    env = build_memory_dialog_env_from_ctx(_ctx, context_chat_key=_context_chat_key or _ctx_chat_key)
    _channel_type = env.channel_type
    _channel_id = env.channel_id
    chat_env_system = env.chat_env_system
    chat_env_note = env.chat_env_note

    memory_context = "【当前暂无检索结果，是一片虚无的量子真空...】"
    
    # 定义核心记忆类型(静态画像)
    STATIC_TAGS = ["FACTS", "PREFERENCES", "TRAITS"]

    mem0 = await get_mem0_client()
    memory_config = core_config

    max_items_per_user_cfg = 16
    try:
        max_items_per_user_cfg = int(getattr(memory_config, "PROMPT_INJECT_MAX_ITEMS_PER_USER", 16) or 16)
    except Exception:
        max_items_per_user_cfg = 16
    if max_items_per_user_cfg <= 0:
        max_items_per_user_cfg = 16

    recent_future_grace_minutes = 10
    try:
        recent_future_grace_minutes = int(
            getattr(memory_config, "PROMPT_INJECT_RECENT_FUTURE_GRACE_MINUTES", 10) or 10
        )
    except Exception:
        recent_future_grace_minutes = 10
    if recent_future_grace_minutes < 0:
        recent_future_grace_minutes = 10

    recent_max_hours = 4.0
    try:
        recent_max_hours = float(getattr(memory_config, "PROMPT_INJECT_RECENT_MAX_HOURS", 4.0) or 4.0)
    except Exception:
        recent_max_hours = 4.0
    if recent_max_hours <= 0:
        recent_max_hours = 4.0

    # 当前主干固定使用全局 run_id=None。
    run_id_ctx: Optional[str] = _get_mem0_run_id(_ctx, memory_config=memory_config)

    # 提前获取 agent_id(避免在循环里重复 await)
    agent_id = await _get_mem0_agent_id(_ctx, is_self=False, memory_config=memory_config)

    # Phase C: Stage1 潜意识路由(best-effort；失败/超时直接降级，不影响注入)
    subconscious_result = None
    stage1_snapshot = None
    graph_known_target_ids: set[str] = set()
    if mem0 and getattr(memory_config, "SUBCONSCIOUS_ENABLE", True):
        try:
            cache_size = int(getattr(memory_config, "SUBCONSCIOUS_CACHE_SIZE", 15) or 15)
            if cache_size <= 0:
                cache_size = 15

            snapshot = graph_cache.snapshot(max_items=cache_size)
            stage1_snapshot = snapshot
            try:
                # 仅收集“图谱里能解析到的 target_id(纯数字)”，用于判断第三方提及时的兜底逻辑
                graph_known_target_ids = {
                    str(tid).strip()
                    for tid in (snapshot.relations or {}).values()
                    if str(tid or "").strip().isdigit()
                }
            except Exception:
                graph_known_target_ids = set()

            # 允许潜意识输出的 target_id 集合：
            # - 当前对话里出现过的发言者(sender_id，纯数字)
            # - Stage0 关系缓存里指向的 target_id(纯数字)
            # 这样既能“锁定发言者本人”，也允许检索“老王”这类没发言但被提及的人
            allowed_target_ids_set = set()
            try:
                for uid in user_id_list:
                    suid = str(uid or "").strip()
                    if suid.isdigit():
                        allowed_target_ids_set.add(suid)
            except Exception:
                pass
            try:
                for _alias, tid in (snapshot.relations or {}).items():
                    stid = str(tid or "").strip()
                    if stid.isdigit():
                        allowed_target_ids_set.add(stid)
            except Exception:
                pass
            allowed_target_ids = sorted(allowed_target_ids_set)

            latest_sender_id = ""
            try:
                trigger_user_id = str(getattr(_ctx, "from_user_id", "") or "").strip()
                if recent_messages:
                    latest_sender_id = next(
                        (
                            _stage1_sender_id(msg)
                            for msg in recent_messages
                            if _stage1_sender_id(msg)
                        ),
                        _stage1_sender_id(recent_messages[0]),
                    )
                elif trigger_user_id and trigger_user_id not in {"0", "-1"}:
                    latest_sender_id = trigger_user_id
            except Exception:
                latest_sender_id = ""

            def _trunc(s: Any, n: int = 80) -> str:
                try:
                    t = str(s).replace("\n", " ").strip()
                    if len(t) > n:
                        return t[:n] + "..."
                    return t
                except Exception:
                    return ""

            subconscious_result = await run_subconscious(
                model_group_name=str(getattr(memory_config, "SUBCONSCIOUS_MODEL", "grok") or "grok"),
                recent_messages=list(reversed(recent_messages)),  # recent_messages 当前为倒序，这里改为正序给潜意识
                graph_snapshot=snapshot,
                meta={
                    "chat_key": _ctx_chat_key or _context_chat_key,
                    "from_chat_key": _context_chat_key,
                    "channel_type": _channel_type,
                    "latest_sender_id": latest_sender_id,
                    "trigger_user_id": str(getattr(_ctx, "from_user_id", "") or "").strip(),
                    "allowed_target_ids": allowed_target_ids,
                    "chat_env": chat_env_note,
                },
                timeout_seconds=float(getattr(memory_config, "SUBCONSCIOUS_TIMEOUT_SECONDS", 15.0) or 15.0),
                max_tokens=int(getattr(memory_config, "SUBCONSCIOUS_MAX_TOKENS", 512) or 512),
            )

            if subconscious_result:
                # 仅写内存 cache，不落库
                graph_cache.apply_cache_updates(subconscious_result.get("cache_updates"))

                # 二次兜底：过滤潜意识输出的非法 target_id，避免检索错人(尤其是昵称撞车/模型幻觉)
                # 注意：不再强制 target_id 必须属于 allowed_target_ids(由 Stage2 再做效果兜底)
                try:
                    intents_raw = subconscious_result.get("intents") or []
                    if not isinstance(intents_raw, list):
                        intents_raw = []
                    filtered_intents = []
                    for it in intents_raw:
                        if not isinstance(it, dict):
                            continue
                        tid = str(it.get("target_id") or "").strip()
                        if not tid:
                            continue
                        if tid == HCZ_SELF:
                            filtered_intents.append(it)
                            continue
                        if tid.isdigit():
                            filtered_intents.append(it)
                    subconscious_result["intents"] = filtered_intents
                except Exception:
                    pass

                # 私聊硬兜底：确保至少有一条 intent 指向“当前对端用户”(用于身份/外号/关系检索)。
                # 否则模型在 recent_messages 为空或不确定时，容易只打到 HCZ_SELF，导致“我是谁”反复走自我分区。
                try:
                    _ch_type = str(_channel_type or "").strip().lower()
                    _peer_id_fallback = ""
                    if _ch_type == "private":
                        _cid = str(getattr(_ctx, "channel_id", "") or "").strip() or str(_channel_id or "").strip()
                        _digits = "".join([c for c in _cid if c.isdigit()])
                        _peer_id_fallback = _digits if _digits else ""
                        if not _peer_id_fallback:
                            # 再兜底：从 chat_key 里抠 private_<digits>
                            try:
                                _ck2 = str(_context_chat_key or _ctx_chat_key or "").strip()
                                _ck2_low = _ck2.lower()
                                if "-private_" in _ck2_low:
                                    _peer_id_fallback = "".join([c for c in _ck2_low.split("-private_", 1)[1] if c.isdigit()])
                            except Exception:
                                pass
                        if not _peer_id_fallback and str(latest_sender_id).strip().isdigit():
                            _peer_id_fallback = str(latest_sender_id).strip()

                    if _peer_id_fallback and _peer_id_fallback.isdigit():
                        intents_now = subconscious_result.get("intents") or []
                        if not isinstance(intents_now, list):
                            intents_now = []
                        has_peer = any(
                            isinstance(it, dict)
                            and str(it.get("target_id") or "").strip() == _peer_id_fallback
                            for it in intents_now
                        )
                        if not has_peer:
                            intents_now.insert(
                                0,
                                {
                                    "target_id": _peer_id_fallback,
                                    "query": "用户身份 外号 关系 状态",
                                    "reason": "私聊默认先确认对端身份与关系映射(防止误判外人/错分区)",
                                    "priority": 1,
                                    "tags": ["RELATIONSHIPS", "FACTS", "TRAITS"],
                                },
                            )
                            subconscious_result["intents"] = intents_now
                except Exception:
                    pass

                intents_preview_lines: List[str] = []
                intents = []
                try:
                    if isinstance(subconscious_result, dict):
                        intents = subconscious_result.get("intents") or []
                except Exception:
                    intents = []
                if not isinstance(intents, list):
                    intents = []

                for idx, it in enumerate([x for x in intents if isinstance(x, dict)][:8], 1):
                    intents_preview_lines.append(
                        ""
                        + f"[{idx}] target={_trunc(it.get('target_id'), 32)} "
                        + f"priority={it.get('priority', '')} "
                        + f"tags={_trunc(it.get('tags'), 60)} "
                        + f"query={_trunc(it.get('query'), 80)} "
                        + (f"reason={_trunc(it.get('reason'), 120)}" if it.get("reason") else "")
                    )

                topic_mode = {}
                try:
                    if isinstance(subconscious_result, dict):
                        raw_topic_mode = subconscious_result.get("topic_mode") or {}
                        if isinstance(raw_topic_mode, dict):
                            topic_mode = raw_topic_mode
                except Exception:
                    topic_mode = {}
                try:
                    _ctx._na_memory_recall_meta = {
                        "topic_mode": dict(topic_mode) if isinstance(topic_mode, dict) else {},
                    }
                except Exception:
                    pass

                logger.info(
                    "🧠 [Stage1] 潜意识路由完成："
                    + f"intents={len(intents)}, "
                    + f"topic_mode={str((topic_mode or {}).get('mode') or '<none>')}, "
                    + f"snapshot(relations={len(snapshot.relations)}, concepts={len(snapshot.concepts)})"
                    + ("\n" + "\n".join(intents_preview_lines) if intents_preview_lines else "")
                )
        except Exception as e:
            logger.warning(f"⚠️ [Stage1] 潜意识路由失败，已自动降级为旧注入逻辑: {e}")

    # 记忆模块不可用时，直接注入“空记忆”提示，避免抛错导致主流程崩溃
    if not mem0:
        memory_context = "【记忆系统当前不可用：mem0 客户端未初始化或配置不完整】"
        PROMPT = f"""
    ### 🔮 当前记忆投影
    {memory_context}
    """
        return PROMPT

    # 用于跨多路检索统一去重的 ID 集合
    collected_ids_global = set()

    # =========================
    # Phase D: Stage2 并发检索(Static / Social / Self)
    # 当 Stage1 潜意识成功时：走新三路并发检索
    # 当 Stage1 失败/超时：完全降级为旧注入逻辑(不破坏原有功能)
    # =========================

    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            if v is None:
                return default
            return float(v)
        except (ValueError, TypeError):
            return default

    def _sort_by_score_desc(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(items, key=lambda x: _safe_float(x.get("score"), 0.0), reverse=True)

    def _build_query_text(uid: str) -> str:
        if not uid:
            return ""
        try:
            user_msgs = [m for m in recent_messages if m.sender_id == uid]
            last_msgs = user_msgs[:3]
            query_parts: List[str] = []
            for m in last_msgs:
                content = getattr(m, "content", getattr(m, "content_text", ""))
                if content:
                    query_parts.append(str(content))
            if query_parts:
                return " ".join(reversed(query_parts))
        except Exception:
            pass
        return ""

    def _single_line_text(v: Any, max_len: int = 120) -> str:
        try:
            s = str(v or "").replace("\n", " ").strip()
            s = " ".join(s.split())
            if max_len and len(s) > max_len:
                return s[:max_len] + "..."
            return s
        except Exception:
            return ""

    def _format_item_time(item: Dict[str, Any]) -> str:
        ts = item.get("updated_at") or item.get("created_at")
        if not ts:
            return ""
        try:
            if isinstance(ts, str):
                dt = parser.parse(ts)
            else:
                dt = ts
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt_local = dt.astimezone()
            return dt_local.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return _single_line_text(ts, max_len=32)

    def _format_prompt_bullets(items: List[Dict[str, Any]], max_items: int = 16) -> str:
        lines: List[str] = []
        try:
            n = max(0, int(max_items or 0))
        except Exception:
            n = 16
        for item in (items or [])[:n]:
            mem = _single_line_text(item.get("memory", ""), max_len=240)
            if mem:
                ts_s = _format_item_time(item)
                confidence = ""
                md = item.get("metadata", {})
                if isinstance(md, dict):
                    confidence = _single_line_text(md.get("CONFIDENCE") or md.get("confidence") or "", max_len=24)

                prefix = ""
                if ts_s:
                    prefix += f"[{ts_s}] "
                if confidence:
                    prefix += f"(置信度:{confidence}) "
                lines.append(f"{prefix}{mem}" if prefix else f"{mem}")
        return "\n".join(lines)

    def _cap_prompt_items(items: List[Dict[str, Any]], *, limit: int, cap_label: str) -> List[Dict[str, Any]]:
        try:
            normalized_limit = int(limit or 0)
        except Exception:
            normalized_limit = 0
        if normalized_limit <= 0 or len(items) <= normalized_limit:
            return items

        capped_items = items[:normalized_limit]
        try:
            logger.info(
                f"🧠 [memory.inject] prompt cap applied: label={cap_label}, before={len(items)}, after={len(capped_items)}"
            )
        except Exception:
            pass
        return capped_items

    primary_user_id = ""
    try:
        trigger_user_id = str(getattr(_ctx, "from_user_id", "") or "").strip()
        if trigger_user_id and trigger_user_id not in {"0", "-1"}:
            primary_user_id = trigger_user_id
    except Exception:
        primary_user_id = ""

    if not primary_user_id and recent_messages:
        try:
            primary_user_id = next(
                (
                    _stage1_sender_id(msg)
                    for msg in recent_messages
                    if _stage1_sender_id(msg)
                ),
                _stage1_sender_id(recent_messages[0]),
            )
        except Exception:
            primary_user_id = ""

    try:
        if recent_messages:
            latest_sender = next(
                (
                    _stage1_sender_id(msg)
                    for msg in recent_messages
                    if _stage1_sender_id(msg)
                ),
                _stage1_sender_id(recent_messages[0]),
            )
            if primary_user_id and latest_sender and primary_user_id != latest_sender:
                logger.info(
                    "memory recall 主用户已按触发者纠偏: "
                    f"trigger_user_id={primary_user_id} latest_sender={latest_sender}"
                )
    except Exception:
        pass

    context_window_meta = getattr(_ctx, "_na_context_window_meta", {}) or {}
    context_owner_type = str(context_window_meta.get("owner_type") or "").strip().lower()
    is_advanced_context = context_owner_type == "advanced"

    # Stage1 成功的判定：subconscious_result 不是 None(允许为空 dict，但至少说明调用/解析成功)
    use_new_stage2 = bool(mem0 and getattr(memory_config, "SUBCONSCIOUS_ENABLE", True) and subconscious_result is not None)

    if use_new_stage2:
        # 新 Stage2 为当前主链；只有 Stage1 失败/不可用时，才回落到下面的 legacy 检索参数。
        # ---Phase D: 新并发检索路径 ----
        _stage2_t0 = time.perf_counter()
        query_text_primary = _build_query_text(primary_user_id)
        static_prompt_cap = 5
        intent_prompt_cap = 2

        # tags 仅对旧体系的 TYPE 生效；新体系(INNER_THOUGHT/WORLD_KNOWLEDGE 等)先不强过滤，避免误伤
        KNOWN_TYPE_TAGS = {"FACTS", "PREFERENCES", "TRAITS", "GOALS", "RELATIONSHIPS", "EVENTS", "TOPICS"}

        def _pick_known_tags(tags: Any) -> Optional[List[str]]:
            if not tags or not isinstance(tags, list):
                return None
            out = [str(t).strip() for t in tags if isinstance(t, str) and str(t).strip() in KNOWN_TYPE_TAGS]
            return out or None

        # 阈值：沿用你动态检索里的保守策略
        default_threshold = memory_config.MEMORY_SEARCH_SCORE_THRESHOLD
        unset_threshold_lt = float(getattr(memory_config, "PROMPT_INJECT_STAGE2_UNSET_THRESHOLD_LT", 0.1) or 0.1)
        default_threshold_fallback = float(
            getattr(memory_config, "PROMPT_INJECT_STAGE2_DEFAULT_THRESHOLD_FALLBACK", 0.5) or 0.5
        )
        if default_threshold < unset_threshold_lt:
            default_threshold = default_threshold_fallback
        intent_threshold = default_threshold
        recent_threshold = float(getattr(memory_config, "PROMPT_INJECT_STAGE2_RECENT_THRESHOLD", 0.4) or 0.4)

        # token 风控：避免记忆投影爆炸
        MAX_STATIC_ITEMS = int(getattr(memory_config, "PROMPT_INJECT_STAGE2_MAX_STATIC_ITEMS", 36) or 36)
        MAX_CONTEXT_ITEMS = int(getattr(memory_config, "PROMPT_INJECT_STAGE2_MAX_CONTEXT_ITEMS", 36) or 36)
        MAX_INTENT_ITEMS = int(getattr(memory_config, "PROMPT_INJECT_STAGE2_MAX_INTENT_ITEMS", 20) or 20)
        MAX_INTENTS = int(getattr(memory_config, "PROMPT_INJECT_STAGE2_MAX_INTENTS", 16) or 16)
        CONCURRENT_SEARCH = int(getattr(memory_config, "PROMPT_INJECT_STAGE2_CONCURRENT_SEARCH", 12) or 12)
        if MAX_STATIC_ITEMS <= 0:
            MAX_STATIC_ITEMS = 36
        if MAX_CONTEXT_ITEMS <= 0:
            MAX_CONTEXT_ITEMS = 36
        if MAX_INTENT_ITEMS <= 0:
            MAX_INTENT_ITEMS = 20
        if MAX_INTENTS <= 0:
            MAX_INTENTS = 16
        if CONCURRENT_SEARCH <= 0:
            CONCURRENT_SEARCH = 12
        sem = asyncio.Semaphore(CONCURRENT_SEARCH)

        # 上下文中出现过的发言者集合(纯数字)
        context_sender_ids_set: set[str] = set()
        try:
            context_sender_ids_set = {
                str(uid).strip() for uid in user_id_list if str(uid or "").strip().isdigit()
            }
        except Exception:
            context_sender_ids_set = set()

        async def _mem0_search(*, query: str, user_id: str, run_id: Optional[str], limit: int):
            async with sem:
                return await mem0.search(
                    query,
                    user_id=user_id,
                    agent_id=FIXED_MEM0_AGENT_ID,
                    run_id=run_id,
                    limit=limit,
                )

        async def _mem0_get_all(*, user_id: str, run_id: Optional[str]):
            async with sem:
                return await mem0.get_all(user_id=user_id, agent_id=FIXED_MEM0_AGENT_ID, run_id=run_id)

        async def _fetch_static_snapshot(*, user_id: str, source_kind: str) -> Dict[str, Any]:
            """Static 画像保底路：固定读取某个用户的静态画像分区。"""
            normalized_user_id = str(user_id or "").strip()
            if not normalized_user_id:
                return {"type": "static", "used_search": False, "items": []}

            run_id = run_id_ctx
            raw = await _mem0_get_all(user_id=normalized_user_id, run_id=run_id)
            items = _coerce_list(raw)
            items = _filter_by_tags(items, STATIC_TAGS)

            return {
                "type": "static",
                "used_search": False,
                "items": items[:MAX_STATIC_ITEMS],
                "user_id": normalized_user_id,
                "source_kind": source_kind,
            }

        async def _fetch_context_primary() -> Dict[str, Any]:
            """给主用户补一条“上下文动态检索”(保持旧能力，但只对主用户做，减少 token/耗时)"""
            if not primary_user_id or not query_text_primary:
                return {"type": "context", "query": query_text_primary, "items": []}

            raw = await _mem0_search(
                query=query_text_primary,
                user_id=primary_user_id,
                run_id=run_id_ctx,
                limit=int(getattr(memory_config, "PROMPT_INJECT_STAGE2_SEARCH_LIMIT_CONTEXT", 128) or 128),
            )
            results_list = _coerce_list(raw)

            filtered_results: List[Dict[str, Any]] = []
            now_utc = datetime.now(timezone.utc)

            for item in results_list:
                mid = item.get("id")
                if mid and mid in collected_ids_global:
                    continue

                score_val = _safe_float(item.get("score"), 0.0)

                is_recent = False
                created_at_str = item.get("created_at") or item.get("updated_at")
                if created_at_str:
                    try:
                        if isinstance(created_at_str, str):
                            dt = parser.parse(created_at_str)
                        else:
                            dt = created_at_str

                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        else:
                            dt = dt.astimezone(timezone.utc)

                        diff = now_utc - dt
                        if timedelta(minutes=-recent_future_grace_minutes) <= diff <= timedelta(hours=recent_max_hours):
                            is_recent = True
                    except Exception:
                        pass

                passed = (score_val >= recent_threshold) if is_recent else (score_val >= default_threshold)
                if passed:
                    filtered_results.append(item)

            filtered_results = _sort_by_score_desc(filtered_results)
            return {"type": "context", "query": query_text_primary, "items": filtered_results[:MAX_CONTEXT_ITEMS]}

        async def _fetch_intent(it: Dict[str, Any]) -> Dict[str, Any]:
            target_id = str(it.get("target_id") or "").strip()
            query = str(it.get("query") or "").strip()
            if not target_id or not query:
                return {"type": "intent", "it": it, "items": []}

            tags = _pick_known_tags(it.get("tags"))

            # ===============
            # 新增兜底机制：第三方近况(不删旧逻辑，只新增)
            #
            # 触发条件(严格)：
            # target_id 不在当前上下文发言者里(上下文没出现过这个人)
            # 但它存在于 Stage0 图谱 relations 指向集合中(说明“图谱能解析到这个人”)
            # 且 Stage1 已经产出了针对该 target_id 的意图(说明用户确实在问他)
            #
            # 行为：
            # 1) 检索分区当前统一为全局 run_id=None
            # 2) 若相关度检索仍为空：注入该用户最近 6 条记忆(按时间倒序，不看关联度)
            # ===============
            is_third_party_from_graph = (
                target_id != HCZ_SELF
                and target_id.isdigit()
                and target_id not in context_sender_ids_set
                and target_id in graph_known_target_ids
            )

            # 当前主干统一使用全局 run_id=None + agent_id=default；仅保留 target_id 维度区分。
            if target_id == HCZ_SELF or is_third_party_from_graph:
                run_id = None
            else:
                run_id = run_id_ctx

            raw = await _mem0_search(
                query=query,
                user_id=target_id,
                run_id=run_id,
                limit=int(getattr(memory_config, "PROMPT_INJECT_STAGE2_SEARCH_LIMIT_INTENT", 64) or 64),
            )

            items = _coerce_list(raw)
            if tags:
                items = _filter_by_tags(items, tags)
            items = _filter_by_score(items, intent_threshold)
            items = _sort_by_score_desc(items)

            # 第三方保底：无论相关度检索是否命中，都注入“最近 6 条记忆”(按时间，不看关联度)
            # 同时剔除重复记忆(以 id 为主，缺 id 时退化为 memory 文本)
            if is_third_party_from_graph:
                try:
                    MAX_THIRD_PARTY_RECENT = int(
                        getattr(memory_config, "PROMPT_INJECT_STAGE2_THIRD_PARTY_RECENT", 6) or 6
                    )
                    MAX_THIRD_PARTY_TOTAL = int(
                        getattr(memory_config, "PROMPT_INJECT_STAGE2_THIRD_PARTY_TOTAL", 16) or 16
                    )
                    if MAX_THIRD_PARTY_RECENT <= 0:
                        MAX_THIRD_PARTY_RECENT = 6
                    if MAX_THIRD_PARTY_TOTAL <= 0:
                        MAX_THIRD_PARTY_TOTAL = 16  # 6 条近期 + 若干相关度结果(去重后截断)

                    raw_all = await _mem0_get_all(user_id=target_id, run_id=None)
                    all_items = _coerce_list(raw_all)
                    logger.info(
                        "🧠 [Stage2] 第三方保底最近记忆仅读 default 分区: "
                        f"source=third_party_recent target_user_id={target_id} agent_id={FIXED_MEM0_AGENT_ID} "
                        f"run_id=none count={len(all_items)}"
                    )

                    def _dt_key(x: Dict[str, Any]) -> float:
                        ts = x.get("updated_at") or x.get("created_at")
                        if not ts:
                            return 0.0
                        try:
                            dt = parser.parse(ts) if isinstance(ts, str) else ts
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            else:
                                dt = dt.astimezone(timezone.utc)
                            return dt.timestamp()
                        except Exception:
                            return 0.0

                    # 取最近 6 条，并按时间倒序稳定排序
                    newest = heapq.nlargest(MAX_THIRD_PARTY_RECENT, all_items, key=_dt_key)
                    newest = sorted(newest, key=_dt_key, reverse=True)

                    def _dedup_key(x: Dict[str, Any]) -> str:
                        mid = x.get("id")
                        if mid is not None and str(mid).strip() != "":
                            return "id:" + str(mid)
                        return "mem:" + str(x.get("memory") or "")

                    merged: List[Dict[str, Any]] = []
                    seen: set[str] = set()

                    for x in newest:
                        k = _dedup_key(x)
                        if k in seen:
                            continue
                        seen.add(k)
                        merged.append(x)

                    # 再拼上相关度检索结果(去重后截断)
                    for x in items:
                        k = _dedup_key(x)
                        if k in seen:
                            continue
                        seen.add(k)
                        merged.append(x)
                        if len(merged) >= MAX_THIRD_PARTY_TOTAL:
                            break

                    # 如果既没有 recent 也没有 relevance，就返回空(但这种情况很少)
                    mode = "third_party_recent" if newest else "third_party_relevance"
                    return {
                        "type": "intent",
                        "it": it,
                        "items": merged,
                        "mode": mode,
                        "third_party": True,
                    }
                except Exception:
                    # 异常时退回原相关度结果
                    return {
                        "type": "intent",
                        "it": it,
                        "items": items[:MAX_INTENT_ITEMS],
                        "mode": "normal",
                        "third_party": True,
                    }

            return {
                "type": "intent",
                "it": it,
                "items": items[:MAX_INTENT_ITEMS],
                "mode": "normal",
                "third_party": False,
            }

        # 组装并发任务
        tasks: List[asyncio.Task] = []
        if is_advanced_context:
            tasks.append(
                asyncio.create_task(
                    _fetch_static_snapshot(
                        user_id=get_primary_advanced_user_id(memory_config),
                        source_kind="advanced_fixed",
                    )
                )
            )
        tasks.append(asyncio.create_task(_fetch_context_primary()))

        intents_raw: Any = []
        try:
            if isinstance(subconscious_result, dict):
                intents_raw = subconscious_result.get("intents") or []
        except Exception:
            intents_raw = []
        if not isinstance(intents_raw, list):
            intents_raw = []
        intents: List[Dict[str, Any]] = [it for it in intents_raw if isinstance(it, dict)]

        # 去掉“主用户保底画像”重复检索：
        # Stage2 会在高级 context 固定注入配置主用户的 static，普通 context 则在
        # 当前主用户 query 缺席/落空时补 static，避免再跑一次冗余画像检索造成耗时/浪费。
        def _is_redundant_primary_profile_intent(it: Dict[str, Any]) -> bool:
            try:
                if str(it.get("target_id") or "").strip() != str(primary_user_id or "").strip():
                    return False
                q = str(it.get("query") or "").strip()
                if not q:
                    return False
                qn = re.sub(r"\s+", "", q)
                if "用户画像" in qn or "用户身份" in qn:
                    return True
                if "用户" in qn and ("画像" in qn or "身份" in qn) and ("外号" in qn or "关系" in qn or "状态" in qn):
                    return True
            except Exception:
                return False
            return False

        intents = [it for it in intents if not _is_redundant_primary_profile_intent(it)]
        intents_sorted = sorted(intents, key=lambda x: int(x.get("priority", 999)) if isinstance(x, dict) else 999)[:MAX_INTENTS]

        for it in intents_sorted:
            tasks.append(asyncio.create_task(_fetch_intent(it)))

        # 执行并发检索
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 整理结果(按固定顺序拼接，确保稳定)
        static_res: Optional[Dict[str, Any]] = None
        context_res: Optional[Dict[str, Any]] = None
        intent_res_list: List[Dict[str, Any]] = []

        for r in results:
            if isinstance(r, Exception):
                continue
            if not isinstance(r, dict):
                continue
            if r.get("type") == "static":
                static_res = r
            elif r.get("type") == "context":
                context_res = r
            elif r.get("type") == "intent":
                intent_res_list.append(r)

        blocks: List[str] = []

        # Stage2 统计日志(避免打爆：只输出命中数+前几条 ID)
        stage2_stats: List[str] = []
        stage2_stats.append(
            "🧠 [Stage2] 并发检索完成："
            + f"primary_user_id={primary_user_id or '(none)'}, "
            + f"owner_type={context_owner_type or '(unknown)'}, "
            + f"threshold(intent={intent_threshold:.2f}, recent={recent_threshold:.2f}, default={default_threshold:.2f}), "
            + f"intents={len(intents_sorted)}"
        )

        if not is_advanced_context:
            primary_user_intent_checked = False
            primary_user_intent_hits = 0
            for intent_res in intent_res_list:
                if not isinstance(intent_res, dict):
                    continue
                it = intent_res.get("it") or {}
                target_id = str(it.get("target_id") or "").strip()
                if not target_id or target_id == HCZ_SELF:
                    continue
                if target_id != str(primary_user_id or "").strip():
                    continue
                if bool(intent_res.get("third_party")):
                    continue
                primary_user_intent_checked = True
                primary_user_intent_hits += len(intent_res.get("items") or [])

            should_inject_normal_static = bool(primary_user_id) and (
                (not primary_user_intent_checked) or primary_user_intent_hits <= 0
            )
            if should_inject_normal_static:
                static_reason = "no_primary_user_query" if not primary_user_intent_checked else "primary_user_query_miss"
                static_res = await _fetch_static_snapshot(
                    user_id=primary_user_id,
                    source_kind=static_reason,
                )
                stage2_stats.append(
                    "static fallback for normal context: "
                    + f"reason={static_reason}, user_id={primary_user_id or '(none)'}, "
                    + f"hits={len((static_res or {}).get('items') or [])}"
                )
            else:
                stage2_stats.append(
                    "static suppressed for normal context: "
                    + f"user_id={primary_user_id or '(none)'}, primary_user_query_hits={primary_user_intent_hits}"
                )

        def _top_ids(items: List[Dict[str, Any]], n: int = 3) -> str:
            pairs = []
            for x in items[:n]:
                mid = x.get("id")
                sc = x.get("score")
                try:
                    scf = float(sc) if sc is not None else 0.0
                    pairs.append(f"{mid}:{scf:.2f}")
                except Exception:
                    pairs.append(f"{mid}:{sc}")
            return ", ".join([p for p in pairs if p and p != "None:0.00"]) or "(none)"

        # 1) Static
        try:
            if static_res:
                static_items = static_res.get("items") or []
                used_search = bool(static_res.get("used_search"))
                static_source_kind = str(static_res.get("source_kind") or "").strip()
                static_user_id = str(static_res.get("user_id") or primary_user_id or "").strip()

                stage2_stats.append(
                    f"static: used_search={used_search}, source={static_source_kind or 'default'}, user_id={static_user_id or '(none)'}, hits={len(static_items)}"
                    + (f", top={_top_ids(static_items)}" if static_items else "")
                )

                deduped_static: List[Dict[str, Any]] = []
                for item in static_items:
                    mid = item.get("id")
                    if mid and mid in collected_ids_global:
                        continue
                    deduped_static.append(item)

                deduped_static = _cap_prompt_items(
                    deduped_static,
                    limit=static_prompt_cap,
                    cap_label=f"static user={static_user_id or '(unknown)'}",
                )

                for item in deduped_static:
                    mid = item.get("id")
                    if mid:
                        collected_ids_global.add(mid)

                if deduped_static:
                    header =  "全部记忆"
                    full_header = f"Static 画像 {header}({len(deduped_static)} 条)"
                    parts = [full_header]
                    parts.extend(
                        format_prompt_grouped_memories(deduped_static, max_items_per_user=max_items_per_user_cfg)
                    )
                    blocks.append("\n\n".join(parts))
        except Exception:
            pass

        # 2) Intents (Social/Self)
        try:
            intent_blocks: List[str] = []
            for idx, r in enumerate(intent_res_list, 1):
                it = r.get("it") or {}
                items = r.get("items") or []
                mode = str(r.get("mode") or "normal")
                is_third_party = bool(r.get("third_party"))

                try:
                    stage2_stats.append(
                        "intent["
                        + str(idx)
                        + "]: target="
                        + str(it.get("target_id") or "")
                        + " query="
                        + str(it.get("query") or "")
                        + (" hits=" + str(len(items)))
                        + (" mode=" + mode if mode else "")
                        + (f" top={_top_ids(items)}" if items else "")
                    )
                except Exception:
                    pass

                deduped: List[Dict[str, Any]] = []
                for item in items:
                    mid = item.get("id")
                    if mid and mid in collected_ids_global:
                        continue
                    deduped.append(item)

                target_id = str(it.get("target_id") or "").strip()
                query = str(it.get("query") or "").strip()

                deduped = _cap_prompt_items(
                    deduped,
                    limit=intent_prompt_cap,
                    cap_label=f"intent[{idx}] target={target_id or '(unknown)'} query={_single_line_text(query, max_len=48)}",
                )

                for item in deduped:
                    mid = item.get("id")
                    if mid:
                        collected_ids_global.add(mid)
                if not deduped:
                    continue

                reason = str(it.get("reason") or "").strip()
                title = f"意图[{idx}] target={target_id} query={query}" + (f" | reason={reason}" if reason else "")
                if is_third_party:
                    title += "(当前对话未出现的人类)"
                    # 只要是第三方，就会注入最近 6 条记忆作为保底(去重后与相关度结果合并)
                parts = [title]
                parts.extend(format_prompt_grouped_memories(deduped, max_items_per_user=max_items_per_user_cfg))
                intent_blocks.append(" ".join(parts))

            if intent_blocks:
                blocks.append(" " .join(intent_blocks))
        except Exception:
            pass

        memory_context = " ".join([b for b in blocks if b.strip()])
        if not memory_context.strip():
            memory_context = "【当前暂无检索结果，是一片虚无的量子真空...】"

        try:
            elapsed = time.perf_counter() - _stage2_t0
            stage2_stats.append(f"elapsed={elapsed:.3f}s")
            logger.info("\n".join(stage2_stats))
        except Exception:
            pass

    else:
        # ---降级：旧注入逻辑(保持你原有“多用户遍历 + 静态画像 + 动态检索”行为不变) ----
        if user_id_list:
            memory_context = ""
            static_prompt_cap = 5
            dynamic_prompt_cap = 2
            for uid in user_id_list:

                # --构造 query_text (复用后续逻辑) ---
                query_text = ""
                try:
                    user_msgs = [m for m in recent_messages if m.sender_id == uid]
                    last_msgs = user_msgs[:3]
                    query_parts = []
                    for m in last_msgs:
                        content = getattr(m, "content", getattr(m, "content_text", ""))
                        if content:
                            query_parts.append(str(content))
                    if query_parts:
                        query_text = " ".join(reversed(query_parts))
                except Exception:
                    pass

                # 当前用户维度统一使用全局 run_id 主干
                run_id = run_id_ctx

                # 用于去重的 ID 集合(全局共享，避免多轮检索重复注入)
                collected_ids = collected_ids_global

                # 1. 获取核心静态记忆 (Get All with Filter)
                try:
                    static_mem = ""
                    used_search = False
                    static_items = []

                    if query_text and mem0:
                        # 使用 mem0.search 搜索，阈值 0.5
                        raw_results = await mem0.search(
                            query_text,
                            user_id=uid,
                            agent_id=agent_id,
                            run_id=run_id,
                            limit=int(getattr(memory_config, "PROMPT_INJECT_STAGE2_SEARCH_LIMIT_STATIC", 42) or 42),
                        )

                        # 手动预处理以获取 ID 和格式化
                        items = _coerce_list(raw_results)
                        items = _filter_by_tags(items, STATIC_TAGS)
                        items = _filter_by_score(
                            items,
                            float(getattr(memory_config, "PROMPT_INJECT_LEGACY_STATIC_SCORE_THRESHOLD", 0.47) or 0.47),
                        )

                        static_items = items
                        used_search = True

                    # Fallback to get_all if query_text is missing or search yielded nothing (optional?)
                    # 原逻辑是: if not used_search. 也就是说如果 query_text 存在就只用 search
                    if not used_search:
                        raw_results = await mem0.get_all(
                            user_id=uid,
                            agent_id=agent_id,
                            run_id=run_id,
                        )
                        items = _coerce_list(raw_results)
                        items = _filter_by_tags(items, STATIC_TAGS)
                        static_items = items

                    # 格式化静态记忆
                    if static_items:
                        static_items = _cap_prompt_items(
                            static_items,
                            limit=static_prompt_cap,
                            cap_label=f"legacy_static user={uid}",
                        )

                        for item in static_items:
                            if item.get("id"):
                                collected_ids.add(item["id"])

                        header = "搜索结果" if used_search else "全部记忆"
                        title = f"【静态画像】用户 {uid} {header}({len(static_items)} 条)"
                        bullets = _format_prompt_bullets(static_items, max_items=max_items_per_user_cfg)
                        static_mem = f"{title}\n{bullets}" if bullets else "(无结果)"
                    else:
                        static_mem = "(无结果)"

                    if "(无结果)" not in static_mem:
                        memory_context += f"{static_mem}\n"
                        logger.info(
                            f"📚 为用户 {uid} 注入核心记忆 (Filtered={used_search}, Count={len(static_items)}):\n{static_mem[:100]}...",
                        )
                except Exception as e:
                    logger.error(f"❌ 获取用户 {uid} 核心记忆时发生坍缩: {e}")

                # 2. 基于上下文搜索动态记忆 (Search with Context)
                # 说明：这里仍在使用 legacy 阈值参数，它们是当前降级链路的现役配置，先保留不删。
                try:
                    if query_text:
                        # 执行搜索 (自定义分层检索逻辑)
                        # 目标：24小时内的新记忆使用较低阈值 (0.45)，旧记忆保持原阈值

                        default_threshold_legacy = memory_config.MEMORY_SEARCH_SCORE_THRESHOLD
                        # 如果未配置阈值(默认0)，强制设为0.55以防大量旧记忆涌入导致token爆炸
                        floor = float(getattr(memory_config, "PROMPT_INJECT_LEGACY_DEFAULT_THRESHOLD_FLOOR", 0.57) or 0.57)
                        if default_threshold_legacy < floor:
                            default_threshold_legacy = floor

                        recent_threshold_legacy = float(
                            getattr(memory_config, "PROMPT_INJECT_LEGACY_RECENT_THRESHOLD", 0.5) or 0.5
                        )

                        # 扩大 limit 以确保包含足够的近期和远期候选
                        raw_results = await mem0.search(
                            query_text,
                            user_id=uid,
                            agent_id=agent_id,
                            run_id=run_id,
                            limit=int(getattr(memory_config, "PROMPT_INJECT_STAGE2_SEARCH_LIMIT_CONTEXT", 128) or 128),
                        )

                        # 统一转为列表
                        results_list = _coerce_list(raw_results)

                        filtered_results = []
                        now_utc = datetime.now(timezone.utc)

                        for item in results_list:
                            # 1. 去重检查：如果已经在静态记忆中出现，则跳过
                            if item.get("id") in collected_ids:
                                continue

                            # 安全获取分数，如果无分数或转换失败则默认为0，防止直接穿透筛选
                            score = item.get("score")
                            score_val = 0.0
                            if score is not None:
                                try:
                                    score_val = float(score)
                                except (ValueError, TypeError):
                                    score_val = 0.0

                            # 判断是否为24小时内的记忆
                            is_recent = False
                            created_at_str = item.get("created_at") or item.get("updated_at")
                            if created_at_str:
                                try:
                                    if isinstance(created_at_str, str):
                                        dt = parser.parse(created_at_str)
                                    else:
                                        dt = created_at_str

                                    if dt.tzinfo is None:
                                        dt = dt.replace(tzinfo=timezone.utc)
                                    else:
                                        dt = dt.astimezone(timezone.utc)

                                    # 计算时间差，加上下限判断防止未来时间(或时区转换偏差导致的时间倒流)被误判为recent
                                    diff = now_utc - dt
                                    if timedelta(minutes=-recent_future_grace_minutes) <= diff <= timedelta(hours=recent_max_hours):
                                        is_recent = True
                                except Exception:
                                    pass  # 解析失败按旧记忆处理

                            # 应用分层阈值
                            passed = False
                            if is_recent:
                                if score_val >= recent_threshold_legacy:
                                    passed = True
                            else:
                                if score_val >= default_threshold_legacy:
                                    passed = True

                            if passed:
                                filtered_results.append(item)
                                collected_ids.add(item.get("id"))

                        # Prompt 注入需精简：不注入 ID / 标签(TYPE) / 相关度
                        if filtered_results:
                            filtered_results = _cap_prompt_items(
                                filtered_results,
                                limit=dynamic_prompt_cap,
                                cap_label=f"legacy_dynamic user={uid} query={_single_line_text(query_text, max_len=48)}",
                            )
                            q = _single_line_text(query_text, max_len=120)
                            title = f"【动态检索】用户 {uid}" + (f" query={q}" if q else "") + f"({len(filtered_results)} 条)"
                            bullets = _format_prompt_bullets(filtered_results, max_items=max_items_per_user_cfg)
                            if bullets:
                                memory_context += f"{title}\n{bullets}\n"
                            logger.info(
                                f"🔍 为用户 {uid} 检索关联记忆 (分层阈值+去重生效, Query: {query_text[:20]}...): {len(filtered_results)} hits",
                            )
                except Exception as e:
                    logger.error(f"❌ 搜索用户 {uid} 记忆时发生坍缩: {e}")

            if not memory_context.strip():
                memory_context = "【当前暂无检索结果，是一片虚无的量子真空...】"
    
    PROMPT = f"""
    {chat_env_system}
    我不能直球念出来我的记忆，这会给人监视的感觉，别人会很尴尬。我要避免给人监视的感觉，所以我会把记忆融入到我的思考和表达中，而不是直接念出来。**我不对外输出记忆的具体内容**，但它们会潜移默化地影响我的行为和决策。请我会尽力让这些记忆成为我行动的智慧源泉，而不是负担
    {memory_context}
    """
    return PROMPT  # noqa: RET504


async def cleanup_memory_runtime() -> None:
    """清理记忆运行时"""
    global _mem0_instance, _last_config_hash, _memory_inject_cache
    _mem0_instance = None
    _last_config_hash = None
    _memory_inject_cache = {}
