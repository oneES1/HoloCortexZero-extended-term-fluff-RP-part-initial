"""内置 Timeline 压缩服务

盯着 DBContextMessage（上下文窗口历史）的数量，不是 DBChatMessage。
当历史达到阈值（100条）时触发压缩，压缩产物就绪后替换并清理到最近10条。

关键边界：
- 触发条件：DBContextMessage count >= max_history (100)
- 压缩输入：DBContextMessage 的文本内容（只梳理文本，不梳理图片）
- 压缩产物：pending_summary，等下次请求时 try_apply_ready_summary 执行替换+清理
- 缓冲：120 条不截断（assembler 的 get_history 硬限制）
- 压缩 API 报错：单次长等待失败即释放状态，避免重试链路长期占用 timeline
- LLM：走统一辅助 LLM 管道，由模型组协议决定发射器
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.prompt_defaults import DEFAULT_TIMELINE_SYSTEM_PROMPT, render_identity_prompt
from holo_cortex_zero.models.db_context_window import DBContextMessage, DBContextWindow
from holo_cortex_zero.schemas.ir import GenerationRequest, MessagePart, MessageTurn
from holo_cortex_zero.services.llm.auxiliary import generate_auxiliary


@dataclass
class _CompressJob:
    context_id: str
    requested_at: float


class TimelineService:
    """内置 Timeline 压缩服务"""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[_CompressJob] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        # 正在处理的 context_id 集合，防止重复入队
        self._in_flight: set = set()

        # 配置（从 yaml 加载）
        self.summary_model_group: str = ""
        self.llm_max_tokens: int = 2000
        self.llm_timeout_seconds: float = 120.0
        self.time_bucket_minutes: int = 15

    def start(self) -> None:
        """启动后台 worker"""
        if self._worker_task and not self._worker_task.done():
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Timeline 压缩服务已启动")

    def stop(self) -> None:
        """停止后台 worker"""
        self._running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()

    async def maybe_trigger(self, context_id: str, current_count: int, threshold: int) -> bool:
        """检查是否需要触发压缩

        由 chain_executor 或 manager 在每次请求时调用。
        返回 True 如果入队了新任务。
        """
        if not self.summary_model_group:
            return False

        if current_count < threshold:
            return False

        if context_id in self._in_flight:
            return False

        # 检查 window 状态
        window = await DBContextWindow.get_or_none(context_id=context_id)
        if not window:
            return False

        # summary_generating 是持久化 DB 锁，但 _in_flight 是当前进程内队列所有权。
        # 若进程重启或 worker 被取消，DB 锁可能残留；只有当前进程仍持有
        # _in_flight 时才认为是真的正在生成，否则必须清理孤儿锁并允许重新入队。
        if window.summary_generating:
            if context_id in self._in_flight:
                return False
            window.summary_generating = False
            await window.save(update_fields=["summary_generating", "updated_at"])
            logger.warning(
                "Timeline: 清理孤儿生成锁 context=%s current_count=%s threshold=%s",
                context_id,
                current_count,
                threshold,
            )

        # 标记生成中
        window.summary_generating = True
        await window.save(update_fields=["summary_generating", "updated_at"])

        self._in_flight.add(context_id)
        await self._queue.put(_CompressJob(context_id=context_id, requested_at=time.time()))
        logger.info(f"Timeline: 上下文窗口 {context_id} 历史 {current_count} 条，触发压缩")
        return True

    async def _worker_loop(self) -> None:
        """后台 worker：从队列取任务，执行一次压缩"""
        while self._running:
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            try:
                await self._do_compress(job.context_id)
            except Exception as e:
                logger.error(f"Timeline: 压缩失败 context={job.context_id}: {e}")
                # 清除生成中标记
                try:
                    window = await DBContextWindow.get_or_none(context_id=job.context_id)
                    if window:
                        window.summary_generating = False
                        await window.save(update_fields=["summary_generating", "updated_at"])
                except Exception:
                    pass
            finally:
                self._in_flight.discard(job.context_id)
                self._queue.task_done()

    async def _do_compress(self, context_id: str) -> None:
        """执行一次压缩

        1. 从 DBContextMessage 读取历史（只取文本）
        2. 构建时间桶分组的转录
        3. 调用辅助 LLM 生成摘要
        4. 写入 pending_summary
        """
        # 1. 读取所有可压缩历史消息；memory_inject 只参与 live window，不进入长期摘要
        messages = await DBContextMessage.filter(
            context_id=context_id,
        ).exclude(msg_type="memory_inject").order_by("id").all()

        if not messages:
            return

        # 2. 提取纯文本转录
        transcript = self._build_transcript(messages)
        if not transcript.strip():
            logger.warning(f"Timeline: context={context_id} 无文本内容可压缩")
            return

        # 3. 获取上一版摘要作为参考
        window = await DBContextWindow.get_or_none(context_id=context_id)
        previous_summary = ""
        if window and window.compressed_summary:
            from holo_cortex_zero.services.context_window.manager import context_window_manager

            previous_summary = context_window_manager.sanitize_model_output_text(window.compressed_summary)

        # 4. 构建 LLM prompt
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sys_prompt = str(getattr(config, "TIMELINE_SYSTEM_PROMPT", "") or "").strip()
        if not sys_prompt:
            sys_prompt = DEFAULT_TIMELINE_SYSTEM_PROMPT
        sys_prompt = render_identity_prompt(sys_prompt, config)
        logger.debug("timeline system prompt resolved: prompt_length=%s", len(sys_prompt))
        user_prompt = self._build_user_prompt(
            transcript=transcript,
            previous_summary=previous_summary,
            now_str=now_str,
            msg_count=len(messages),
        )
        request = GenerationRequest(
            context_id="aux:timeline",
            model="",
            messages=[
                MessageTurn(role="system", parts=[MessagePart(type="text", text=sys_prompt)]),
                MessageTurn(role="user", parts=[MessagePart(type="text", text=user_prompt)]),
            ],
            temperature=0.2,
            max_tokens=self.llm_max_tokens,
            stream=False,
        )

        # 5. 调用统一辅助 LLM 管道
        result = await generate_auxiliary(
            aux_name="timeline",
            model_group_key=self.summary_model_group,
            request=request,
            source="context_window.timeline",
            timeout=self.llm_timeout_seconds,
        )

        text = str(result.text or "").strip()
        if not text:
            raise RuntimeError("LLM 返回空摘要")

        # 6. 写入 pending_summary
        from holo_cortex_zero.services.context_window.manager import context_window_manager
        await context_window_manager.set_pending_summary(context_id, text)

        logger.info(f"Timeline: 压缩完成 context={context_id} msgs={len(messages)} summary_len={len(text)}")

    def _build_transcript(self, messages: List[Any]) -> str:
        """从 DBContextMessage 构建纯文本转录

        格式：[role] sender: text
        只取文本内容，跳过图片等。
        """
        from holo_cortex_zero.services.context_window.manager import context_window_manager

        lines: List[str] = []
        sanitized_line_count = 0
        dropped_line_count = 0

        for msg in messages:
            role = msg.role or "unknown"
            sender = msg.sender_name or ""
            parts_json = msg.parts_json or "[]"

            try:
                parts = json.loads(parts_json)
            except json.JSONDecodeError:
                continue

            text_parts = []
            for p in parts:
                if isinstance(p, dict) and p.get("type") == "text" and p.get("text"):
                    text_parts.append(str(p["text"]))

            if not text_parts:
                continue

            raw_content = " ".join(text_parts).strip()
            content = context_window_manager.sanitize_model_output_text(raw_content)
            if content != raw_content:
                sanitized_line_count += 1
            if not content:
                dropped_line_count += 1
                continue

            # 时间戳
            ts = ""
            if hasattr(msg, "created_at") and msg.created_at:
                try:
                    ts = msg.created_at.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    ts = ""

            if ts:
                line = f"[{ts}] [{role}] {sender}: {content}" if sender else f"[{ts}] [{role}]: {content}"
            else:
                line = f"[{role}] {sender}: {content}" if sender else f"[{role}]: {content}"

            lines.append(line)

        if sanitized_line_count or dropped_line_count:
            logger.info(
                "Timeline: 构建转录时清洗控制平面/脏文本 "
                f"sanitized_lines={sanitized_line_count} dropped_lines={dropped_line_count}"
            )

        return "\n".join(lines)

    def _build_user_prompt(
        self,
        transcript: str,
        previous_summary: str,
        now_str: str,
        msg_count: int,
    ) -> str:
        prompt = [
            "【较早历史的已压缩结果】",
            previous_summary,
            "【本轮新增原文】",
            transcript,
            "必须输出是**完整新摘要**禁止写成对旧摘要的补充",
        ]

        return "\n".join(prompt)


# 全局单例
timeline_service = TimelineService()
