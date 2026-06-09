from __future__ import annotations

import asyncio
import json
import random
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.os_env import OsEnv
from holo_cortex_zero.core.runtime_identity import get_primary_advanced_user_id
from holo_cortex_zero.services.timer_service import timer_service
from holo_cortex_zero.services.tools.registry import tool_registry



_MOMENT_TAG_PREFIX = "[[moment:echo:"
_MOMENT_TAG_SUFFIX = "]]"
_INTEGER_RE = re.compile(r"^[+-]?\d+$")


@dataclass(frozen=True)
class _MomentWakePayload:
    context_id: str
    primary_user_id: str
    purpose_text: str
    kind: str
    created_at: int


@dataclass(frozen=True)
class _MomentRecord:
    record_id: str
    context_id: str
    primary_user_id: str
    purpose_text: str
    trigger_time: int
    created_at: int


class SystemMomentService:
    def __init__(self) -> None:
        self._init_lock = asyncio.Lock()
        self._initialized = False
        self._tools_registered = False
        self._moment_patrol_task: asyncio.Task | None = None
        self._moment_patrol_running = False
        self._advanced_auto_echo_task: asyncio.Task | None = None
        self._advanced_auto_echo_running = False
        self._advanced_auto_echo_lock = asyncio.Lock()

    def register_tools_once(self) -> None:
        self._register_tools_once()

    async def initialize_runtime(self) -> None:
        async with self._init_lock:
            if self._initialized:
                await self._ensure_moment_patrol_state()
                await self._ensure_advanced_auto_echo_state()
                return
            self.register_tools_once()
            await self._ensure_moment_patrol_state()
            await self._ensure_advanced_auto_echo_state()
            if bool(config.SYSTEM_MOMENT_ENABLE_VOW_PATROL):
                try:
                    await self._moment_patrol_once()
                except Exception as e:
                    logger.warning(f"system_moment 启动时首次持久提醒补回失败: {e}")
            self._initialized = True
            logger.info("system_moment 运行时初始化完成")


    async def schedule_echo(
        self,
        *,
        context_id: str,
        primary_user_id: str,
        when: int | str,
        purpose_text: str = "",
        ensure_runtime: bool = True,
        silent: bool = False,
    ) -> bool:
        if ensure_runtime:
            await self.initialize_runtime()

        normalized_context_id = str(context_id or "").strip()
        normalized_primary_user_id = self._normalize_primary_user_id(primary_user_id)
        if not normalized_context_id:
            raise ValueError("echo.context_id 不能为空")

        trigger_time = self._parse_echo_when(when)
        if trigger_time < 0:
            removed = self._remove_records_for_context(normalized_context_id)
            result = await timer_service.set_timer(normalized_context_id, -1, "", override=False, temporary=None)
            if not silent:
                logger.info(
                    "system_moment echo 清空定时器: context=%s persistent_removed=%s result=%s",
                    normalized_context_id,
                    removed,
                    result,
                )
            return result

        normalized_purpose_text = self._normalize_purpose_text(purpose_text, field_name="echo.reason")
        now = int(time.time())
        if trigger_time <= now:
            raise ValueError("echo 只能设定在未来的时间点")

        record_id = uuid4().hex
        record = _MomentRecord(
            record_id=record_id,
            context_id=normalized_context_id,
            primary_user_id=normalized_primary_user_id,
            purpose_text=normalized_purpose_text,
            trigger_time=trigger_time,
            created_at=now,
        )
        records = self._load_records()
        records.append(record)
        self._save_records(records)

        payload = _MomentWakePayload(
            context_id=normalized_context_id,
            primary_user_id=normalized_primary_user_id,
            purpose_text=normalized_purpose_text,
            kind="echo",
            created_at=now,
        )

        result = await timer_service.set_timer(
            normalized_context_id,
            trigger_time,
            self._build_moment_tag(record_id),
            override=False,
            silent=silent,
            callback=self._build_wake_callback(payload, record_id=record_id),
        )
        if not result:
            self._remove_record(record_id)
            if not silent:
                logger.warning(
                    "system_moment echo 创建失败并已回滚: context=%s when=%s trigger_time=%s primary_user_id=%s reason=%r",
                    normalized_context_id,
                    when,
                    trigger_time,
                    normalized_primary_user_id,
                    self._log_preview(normalized_purpose_text),
                )
            return False

        if not silent:
            logger.info(
                "system_moment echo 已创建: context=%s when=%s trigger_time=%s record_id=%s persistent=%s result=%s primary_user_id=%s reason=%r",
                normalized_context_id,
                when,
                trigger_time,
                record_id,
                True,
                result,
                normalized_primary_user_id,
                self._log_preview(normalized_purpose_text),
            )
        return result

    async def tool_echo(
        self,
        context_id: str,
        primary_user_id: str,
        when: int | str | None = None,
        reason: str = "",
        **kwargs: Any,
    ) -> bool:
        """把回声放进未来。

        Args:
            when: 负数清空此前定时；正整数按“距离现在的秒数”解释；字符串按 `YYYY-MM-DD HH:MM[:SS]` 解释。
            reason: 设定该提醒的原因；清空此前定时时可省略。

        Returns:
            bool: 是否成功处理。

        Example:
            echo(when=600, reason="十分钟后提醒我收衣服")
        """
        resolved_when, resolved_reason = self._resolve_echo_tool_args(when=when, reason=reason, extra_args=kwargs)
        return await self.schedule_echo(
            context_id=context_id,
            primary_user_id=primary_user_id,
            when=resolved_when,
            purpose_text=resolved_reason,
        )

    def _register_tools_once(self) -> None:
        if self._tools_registered:
            return

        tool_registry.register(
            name="echo",
            display_name="定时提醒",
            category="系统提醒",
            handler=self.tool_echo,
            description=(
                "当你打算 echo 定时提醒时，请用：负数=清空之前的定时；正整数=距离现在的秒数；或直接传入 YYYY-MM-DD HH:MM"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "when": {
                        "type": "string",
                        "description": "请传整数或 YYYY-MM-DD HH:MM 格式的字符串",
                    },
                    "reason": {
                        "type": "string",
                        "description": "该echo的原因",
                    },
                },
                "required": ["when"],
            },
            permission_level="normal",
        )

        self._tools_registered = True
        logger.info("system_moment 已注册 1 个系统 tool: echo")

    async def _ensure_moment_patrol_state(self) -> None:
        moment_config = config
        if not bool(moment_config.SYSTEM_MOMENT_ENABLE_VOW_PATROL):
            await self._stop_moment_patrol()
            logger.info("system_moment persistent patrol 已禁用")
            return

        if self._moment_patrol_task and not self._moment_patrol_task.done():
            return

        self._moment_patrol_running = True
        self._moment_patrol_task = asyncio.create_task(self._moment_patrol_loop())
        logger.info(
            "system_moment persistent patrol 已启用: interval=%ss",
            int(moment_config.SYSTEM_MOMENT_VOW_PATROL_INTERVAL_SECONDS),
        )

    async def _stop_moment_patrol(self) -> None:
        self._moment_patrol_running = False
        if self._moment_patrol_task and not self._moment_patrol_task.done():
            self._moment_patrol_task.cancel()
            try:
                await self._moment_patrol_task
            except asyncio.CancelledError:
                pass
        self._moment_patrol_task = None


    async def _ensure_advanced_auto_echo_state(self) -> None:
        if not bool(getattr(config, "ADVANCED_AUTO_ECHO_ENABLED", False)):
            await self._stop_advanced_auto_echo()
            return

        if self._advanced_auto_echo_task and not self._advanced_auto_echo_task.done():
            return

        self._advanced_auto_echo_running = True
        try:
            await self._advanced_auto_echo_once()
        except Exception as e:
            logger.warning("advanced_auto_echo 启动巡检失败: %s", e)
        self._advanced_auto_echo_task = asyncio.create_task(self._advanced_auto_echo_loop())
        logger.info("advanced_auto_echo 巡检已启用: interval=%ss", self._advanced_auto_echo_interval_seconds())

    async def _stop_advanced_auto_echo(self) -> None:
        self._advanced_auto_echo_running = False
        if self._advanced_auto_echo_task and not self._advanced_auto_echo_task.done():
            self._advanced_auto_echo_task.cancel()
            try:
                await self._advanced_auto_echo_task
            except asyncio.CancelledError:
                pass
        self._advanced_auto_echo_task = None

    async def _advanced_auto_echo_loop(self) -> None:
        await asyncio.sleep(2)
        while self._advanced_auto_echo_running:
            try:
                await self._advanced_auto_echo_once()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("advanced_auto_echo 巡检异常: %s", e, exc_info=True)
            await asyncio.sleep(self._advanced_auto_echo_interval_seconds())

    async def mark_advanced_user_activity(self, *, context_id: str, message_ts: int | None = None) -> None:
        if not self._advanced_auto_echo_is_target_context(context_id):
            return
        async with self._advanced_auto_echo_lock:
            state = self._load_advanced_auto_echo_state()
            if not state:
                return
            state["last_user_message_ts"] = int(message_ts or time.time())
            self._save_advanced_auto_echo_state(state)

    async def mark_advanced_human_agent_scheduled(self, *, context_id: str) -> None:
        if not self._advanced_auto_echo_is_target_context(context_id):
            return
        async with self._advanced_auto_echo_lock:
            state = self._load_advanced_auto_echo_state()
            if state.get("phase") != "wait_user_activity":
                return
            now = int(time.time())
            state["phase"] = "wait_agent_done"
            state["last_human_agent_scheduled_ts"] = now
            self._save_advanced_auto_echo_state(state)

    async def mark_advanced_agent_finished(self, *, context_id: str, success: bool) -> None:
        if not self._advanced_auto_echo_is_target_context(context_id):
            return
        async with self._advanced_auto_echo_lock:
            state = self._load_advanced_auto_echo_state()
            if state.get("phase") != "wait_agent_done":
                return
            if not bool(success):
                state["phase"] = "wait_user_activity"
                self._clear_advanced_auto_echo_pending(state)
                self._save_advanced_auto_echo_state(state)
                return
            await self._advanced_auto_echo_schedule_after_human_reply(state)

    async def _advanced_auto_echo_once(self) -> None:
        async with self._advanced_auto_echo_lock:
            if not bool(getattr(config, "ADVANCED_AUTO_ECHO_ENABLED", False)):
                return
            context_id = self._advanced_auto_echo_context_id()
            if not context_id:
                return

            now = int(time.time())
            now_dt = datetime.fromtimestamp(now)
            try:
                start_dt, end_dt, day_key = self._advanced_auto_echo_today_window(now_dt)
            except ValueError as e:
                self._save_advanced_auto_echo_state({"phase": "disabled", "reason": str(e)})
                logger.warning("advanced_auto_echo 配置非法，已跳过")
                return

            state = self._load_advanced_auto_echo_state()
            if state.get("context_id") != context_id or state.get("day") != day_key:
                state = {"context_id": context_id, "day": day_key, "phase": "day_wait_start"}

            if now_dt > end_dt:
                state["phase"] = "day_finished"
                self._clear_advanced_auto_echo_pending(state)
                self._save_advanced_auto_echo_state(state)
                return
            if now_dt < start_dt:
                state["phase"] = "day_wait_start"
                self._save_advanced_auto_echo_state(state)
                return

            if state.get("phase") == "pending_echo":
                pending_ts = int(state.get("pending_trigger_ts") or 0)
                if pending_ts > now:
                    if self._advanced_auto_echo_has_record(state):
                        return
                    await self._advanced_auto_echo_schedule_at(state, pending_ts)
                    return
                state["phase"] = "wait_user_activity"
                self._clear_advanced_auto_echo_pending(state)
                self._save_advanced_auto_echo_state(state)
                return

            if state.get("phase") in {"wait_user_activity", "wait_agent_done", "day_finished"}:
                self._save_advanced_auto_echo_state(state)
                return

            lower_ts = max(int(start_dt.timestamp()), now + 60)
            upper_ts = min(
                int(start_dt.timestamp()) + self._advanced_auto_echo_sample_window_seconds(),
                int(end_dt.timestamp()),
            )
            trigger_ts = self._advanced_auto_echo_sample_timestamp(lower_ts, upper_ts)
            if trigger_ts <= 0:
                state["phase"] = "day_finished"
                self._save_advanced_auto_echo_state(state)
                return
            await self._advanced_auto_echo_schedule_at(state, trigger_ts)

    async def _advanced_auto_echo_schedule_after_human_reply(self, state: dict[str, Any]) -> None:
        now = int(time.time())
        now_dt = datetime.fromtimestamp(now)
        try:
            _, end_dt, day_key = self._advanced_auto_echo_today_window(now_dt)
            min_interval = self._advanced_auto_echo_min_interval_seconds()
            sample_window = self._advanced_auto_echo_sample_window_seconds()
        except ValueError:
            state["phase"] = "disabled"
            self._clear_advanced_auto_echo_pending(state)
            self._save_advanced_auto_echo_state(state)
            return

        if state.get("day") != day_key or now_dt > end_dt:
            state["context_id"] = self._advanced_auto_echo_context_id()
            state["day"] = day_key
            state["phase"] = "day_finished"
            self._clear_advanced_auto_echo_pending(state)
            self._save_advanced_auto_echo_state(state)
            return

        base_ts = max(
            int(state.get("last_user_message_ts") or 0),
            int(state.get("last_human_agent_scheduled_ts") or 0),
        )
        if base_ts <= 0:
            state["phase"] = "wait_user_activity"
            self._save_advanced_auto_echo_state(state)
            return

        lower_ts = max(base_ts + min_interval, now + 60)
        upper_ts = min(base_ts + min_interval + sample_window, int(end_dt.timestamp()))
        trigger_ts = self._advanced_auto_echo_sample_timestamp(lower_ts, upper_ts)
        if trigger_ts <= 0:
            state["phase"] = "day_finished"
            self._clear_advanced_auto_echo_pending(state)
            self._save_advanced_auto_echo_state(state)
            return
        await self._advanced_auto_echo_schedule_at(state, trigger_ts)

    async def _advanced_auto_echo_schedule_at(self, state: dict[str, Any], trigger_ts: int) -> None:
        context_id = self._advanced_auto_echo_context_id()
        reason = self._format_advanced_auto_echo_reason(trigger_ts)
        ok = await self.schedule_echo(
            context_id=context_id,
            primary_user_id=context_id,
            when=reason,
            purpose_text=reason,
            ensure_runtime=False,
            silent=True,
        )
        if not ok:
            state["phase"] = "day_finished"
            self._clear_advanced_auto_echo_pending(state)
            self._save_advanced_auto_echo_state(state)
            return

        record_id = self._find_advanced_auto_echo_record_id(
            context_id=context_id,
            trigger_ts=trigger_ts,
            reason=reason,
        )
        state.update(
            {
                "context_id": context_id,
                "day": datetime.fromtimestamp(trigger_ts).strftime("%Y-%m-%d"),
                "phase": "pending_echo",
                "pending_trigger_ts": int(trigger_ts),
                "pending_reason": reason,
                "pending_record_id": record_id,
            }
        )
        self._save_advanced_auto_echo_state(state)

    def _advanced_auto_echo_should_block_payload(self, payload: _MomentWakePayload, *, record_id: str = "") -> bool:
        if not self._advanced_auto_echo_payload_matches(payload, record_id=record_id):
            return False
        if not bool(getattr(config, "ADVANCED_AUTO_ECHO_ENABLED", False)):
            state = self._load_advanced_auto_echo_state()
            state["phase"] = "disabled"
            self._clear_advanced_auto_echo_pending(state)
            self._save_advanced_auto_echo_state(state)
            return True
        try:
            _, end_dt, _ = self._advanced_auto_echo_today_window(datetime.fromtimestamp(time.time()))
        except ValueError:
            return True
        trigger_ts = int(self._load_advanced_auto_echo_state().get("pending_trigger_ts") or 0)
        return bool(trigger_ts and datetime.fromtimestamp(trigger_ts) > end_dt)

    async def _advanced_auto_echo_mark_payload_emitted(
        self,
        payload: _MomentWakePayload,
        *,
        record_id: str = "",
    ) -> None:
        if not self._advanced_auto_echo_payload_matches(payload, record_id=record_id):
            return
        state = self._load_advanced_auto_echo_state()
        state["phase"] = "wait_user_activity"
        state["last_auto_trigger_ts"] = int(time.time())
        self._clear_advanced_auto_echo_pending(state)
        self._save_advanced_auto_echo_state(state)

    def _advanced_auto_echo_payload_matches(self, payload: _MomentWakePayload, *, record_id: str = "") -> bool:
        state = self._load_advanced_auto_echo_state()
        if state.get("phase") != "pending_echo":
            return False
        state_record_id = str(state.get("pending_record_id") or "").strip()
        if record_id and state_record_id and record_id == state_record_id:
            return True
        return (
            str(payload.context_id or "").strip() == str(state.get("context_id") or "").strip()
            and str(payload.purpose_text or "").strip() == str(state.get("pending_reason") or "").strip()
        )

    def _advanced_auto_echo_has_record(self, state: dict[str, Any]) -> bool:
        record_id = str(state.get("pending_record_id") or "").strip()
        trigger_ts = int(state.get("pending_trigger_ts") or 0)
        reason = str(state.get("pending_reason") or "").strip()
        context_id = str(state.get("context_id") or "").strip()
        for record in self._load_records():
            if record_id and record.record_id == record_id:
                return True
            if record.context_id == context_id and record.trigger_time == trigger_ts and record.purpose_text == reason:
                return True
        return False

    def _find_advanced_auto_echo_record_id(self, *, context_id: str, trigger_ts: int, reason: str) -> str:
        matched = ""
        for record in self._load_records():
            if record.context_id == context_id and record.trigger_time == trigger_ts and record.purpose_text == reason:
                matched = record.record_id
        return matched

    @staticmethod
    def _clear_advanced_auto_echo_pending(state: dict[str, Any]) -> None:
        state.pop("pending_trigger_ts", None)
        state.pop("pending_reason", None)
        state.pop("pending_record_id", None)

    @staticmethod
    def _advanced_auto_echo_interval_seconds() -> int:
        return max(10, int(getattr(config, "ADVANCED_AUTO_ECHO_PATROL_INTERVAL_SECONDS", 60) or 60))

    @staticmethod
    def _advanced_auto_echo_sample_window_seconds() -> int:
        return max(0, int(getattr(config, "ADVANCED_AUTO_ECHO_SAMPLE_WINDOW_SECONDS", 14400) or 0))

    @staticmethod
    def _advanced_auto_echo_min_interval_seconds() -> int:
        value = int(getattr(config, "ADVANCED_AUTO_ECHO_MIN_INTERVAL_SECONDS", 3600) or 0)
        if value < 0:
            raise ValueError("min_interval_negative")
        return value

    @staticmethod
    def _advanced_auto_echo_sample_timestamp(lower_ts: int, upper_ts: int) -> int:
        lower_minute = (int(lower_ts) + 59) // 60
        upper_minute = int(upper_ts) // 60
        if upper_minute < lower_minute:
            return 0
        return random.randint(lower_minute, upper_minute) * 60

    @staticmethod
    def _format_advanced_auto_echo_reason(trigger_ts: int) -> str:
        return datetime.fromtimestamp(int(trigger_ts)).strftime("%Y-%m-%d %H:%M")

    def _advanced_auto_echo_context_id(self) -> str:
        return str(get_primary_advanced_user_id(config) or "").strip()

    def _advanced_auto_echo_is_target_context(self, context_id: str) -> bool:
        normalized = str(context_id or "").strip()
        return bool(normalized and normalized == self._advanced_auto_echo_context_id())

    @staticmethod
    def _advanced_auto_echo_today_window(now_dt: datetime) -> tuple[datetime, datetime, str]:
        start_hour, start_minute = SystemMomentService._parse_advanced_auto_echo_hhmm(
            getattr(config, "ADVANCED_AUTO_ECHO_START_TIME", "06:00"),
            field_name="start",
        )
        end_hour, end_minute = SystemMomentService._parse_advanced_auto_echo_hhmm(
            getattr(config, "ADVANCED_AUTO_ECHO_END_TIME", "23:00"),
            field_name="end",
        )
        start_dt = now_dt.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        end_dt = now_dt.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        if end_dt <= start_dt:
            raise ValueError("invalid_day_window")
        return start_dt, end_dt, now_dt.strftime("%Y-%m-%d")

    @staticmethod
    def _parse_advanced_auto_echo_hhmm(value: Any, *, field_name: str) -> tuple[int, int]:
        text = str(value or "").strip()
        parts = text.split(":")
        if len(parts) != 2:
            raise ValueError(f"invalid_{field_name}_time")
        hour = int(parts[0])
        minute = int(parts[1])
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError(f"invalid_{field_name}_time")
        return hour, minute

    @staticmethod
    def _advanced_auto_echo_state_path() -> Path:
        return Path(OsEnv.DATA_DIR) / "configs" / "system_moment" / "advanced_auto_echo.json"

    def _load_advanced_auto_echo_state(self) -> dict[str, Any]:
        path = self._advanced_auto_echo_state_path()
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("advanced_auto_echo 状态读取失败")
            return {}
        return raw if isinstance(raw, dict) else {}

    def _save_advanced_auto_echo_state(self, state: dict[str, Any]) -> None:
        path = self._advanced_auto_echo_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    async def _moment_patrol_loop(self) -> None:
        await asyncio.sleep(2)
        while self._moment_patrol_running:
            try:
                await self._moment_patrol_once()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"system_moment persistent patrol 异常: {e}", exc_info=True)
            interval = max(10, int(config.SYSTEM_MOMENT_VOW_PATROL_INTERVAL_SECONDS))
            await asyncio.sleep(interval)

    async def _moment_patrol_once(self) -> None:
        now = int(time.time())
        records = self._prune_records(self._load_records(), now=now)
        if not records:
            return

        active = [record for record in records if record.trigger_time > now]
        if not active:
            self._save_records(records)
            return

        by_context: dict[str, list[_MomentRecord]] = {}
        for record in active:
            by_context.setdefault(record.context_id, []).append(record)

        for context_id, chat_records in by_context.items():
            try:
                existing = timer_service.get_timers(context_id)
                existing_descs = {str(item.event_desc) for item in existing}

                restored = 0
                for record in chat_records:
                    event_desc = self._build_moment_tag(record.record_id)
                    if event_desc in existing_descs:
                        continue
                    ok = await timer_service.set_timer(
                        context_id,
                        record.trigger_time,
                        event_desc,
                        callback=self._build_wake_callback(self._payload_from_record(record), record_id=record.record_id),
                    )
                    if ok:
                        restored += 1

                if restored:
                    logger.info("system_moment patrol 补回定时器: context=%s restored=%s", context_id, restored)
            except Exception as e:
                logger.warning(f"system_moment patrol 补回失败: context={context_id} err={e}")

        self._save_records(records)

    @staticmethod
    def _record_store_path() -> Path:
        return Path(OsEnv.DATA_DIR) / "configs" / "system_moment" / "vows.json"

    def _load_records(self) -> list[_MomentRecord]:
        path = self._record_store_path()
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"system_moment 读取持久提醒失败: {e}")
            return []
        if not isinstance(raw, list):
            logger.warning("system_moment 持久提醒格式异常：顶层不是 list")
            return []

        records: list[_MomentRecord] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                raw_record_id = item.get("record_id") or item.get("vow_id")
                if not raw_record_id:
                    raise ValueError("record_id 不能为空")
                records.append(
                    _MomentRecord(
                        record_id=str(raw_record_id),
                        context_id=str(item["context_id"]),
                        primary_user_id=str(item["primary_user_id"]),
                        purpose_text=str(item["purpose_text"]),
                        trigger_time=int(item["trigger_time"]),
                        created_at=int(item.get("created_at", 0)),
                    )
                )
            except Exception as e:
                logger.warning(f"system_moment 解析持久提醒记录失败: {e}")
        return records

    def _save_records(self, records: list[_MomentRecord]) -> None:
        path = self._record_store_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: list[dict[str, Any]] = [asdict(record) for record in records]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _remove_record(self, record_id: str) -> None:
        records = [record for record in self._load_records() if record.record_id != record_id]
        self._save_records(records)

    def _remove_records_for_context(self, context_id: str) -> int:
        normalized_context_id = str(context_id or "").strip()
        records = self._load_records()
        kept = [record for record in records if record.context_id != normalized_context_id]
        removed = len(records) - len(kept)
        if removed:
            self._save_records(kept)
        return removed

    @staticmethod
    def _normalize_primary_user_id(primary_user_id: str) -> str:
        normalized = str(primary_user_id or "").strip()
        if not normalized or not normalized.isdigit():
            raise ValueError("moment.primary_user_id 缺失或非法，已拒绝创建定时器")
        return normalized

    @staticmethod
    def _normalize_purpose_text(purpose_text: str, *, field_name: str) -> str:
        normalized = str(purpose_text or "").strip()
        if not normalized:
            raise ValueError(f"{field_name} 不能为空")
        return normalized

    @staticmethod
    def _build_moment_tag(record_id: str) -> str:
        return f"{_MOMENT_TAG_PREFIX}{record_id}{_MOMENT_TAG_SUFFIX}"

    @staticmethod
    def _payload_from_record(record: _MomentRecord) -> _MomentWakePayload:
        return _MomentWakePayload(
            context_id=record.context_id,
            primary_user_id=record.primary_user_id,
            purpose_text=record.purpose_text,
            kind="echo",
            created_at=record.created_at,
        )

    def _build_wake_callback(self, payload: _MomentWakePayload, *, record_id: str = ""):
        async def _callback() -> None:
            await self._emit_wake_event(payload, record_id=record_id)
            if record_id:
                self._remove_record(record_id)

        return _callback

    async def _emit_wake_event(self, payload: _MomentWakePayload, *, record_id: str = "") -> bool:
        from holo_cortex_zero.models.db_chat_channel import DBChatChannel
        from holo_cortex_zero.models.db_context_window import DBContextMessage, DBContextWindow
        from holo_cortex_zero.schemas.chat_message import ChatMessage, ChatType
        from holo_cortex_zero.services.context_window.manager import context_window_manager
        from holo_cortex_zero.services.message_service import message_service

        is_advanced_auto_echo = self._advanced_auto_echo_payload_matches(payload, record_id=record_id)
        if self._advanced_auto_echo_should_block_payload(payload, record_id=record_id):
            return False

        notice_text = self._build_wake_notice(payload.kind, payload.purpose_text)
        source_message_id = f"moment:{payload.kind}:{payload.created_at}:{uuid4().hex[:8]}"

        await DBContextMessage.create(
            context_id=payload.context_id,
            role="user",
            sender_id="system",
            sender_name="system",
            parts_json=json.dumps([{"type": "text", "text": notice_text}], ensure_ascii=False),
            source_message_id=source_message_id,
            msg_type="system_inject",
        )
        await context_window_manager.enforce_history_hard_limit(payload.context_id)

        window = await DBContextWindow.get_or_none(context_id=payload.context_id)
        active_dialog_id = str(getattr(window, "active_dialog_id", "") or "").strip()
        if not active_dialog_id:
            if is_advanced_auto_echo:
                logger.warning("advanced_auto_echo 到点后缺少有效锚定窗口，已跳过 agent 触发")
            else:
                logger.warning(
                    "system_moment 到点后未找到有效锚定窗口，仅写入上下文不触发 agent: context=%s kind=%s primary_user_id=%s",
                    payload.context_id,
                    payload.kind,
                    payload.primary_user_id,
                )
            return False

        channel = await DBChatChannel.get_channel(active_dialog_id)
        synthetic_message = ChatMessage(
            message_id=source_message_id,
            sender_id=payload.primary_user_id,
            sender_name="SYSTEM_MOMENT",
            sender_nickname="SYSTEM_MOMENT",
            adapter_key=channel.adapter_key,
            platform_userid=payload.primary_user_id,
            is_tome=1,
            is_recalled=False,
            chat_key=active_dialog_id,
            chat_type=channel.chat_type if isinstance(channel.chat_type, ChatType) else ChatType(channel.channel_type),
            content_text="",
            content_data=[],
            ext_data={"system_moment": {"kind": payload.kind, "reason": payload.purpose_text}},
            send_timestamp=int(time.time()),
        )
        await message_service.schedule_agent_task(
            message=synthetic_message,
            execution_key=payload.context_id,
            source_scope="system",
        )
        await self._advanced_auto_echo_mark_payload_emitted(payload, record_id=record_id)
        if is_advanced_auto_echo:
            logger.info("advanced_auto_echo 到点已唤醒")
        else:
            logger.info(
                "system_moment 到点已唤醒: context=%s dialog=%s kind=%s primary_user_id=%s reason=%r",
                payload.context_id,
                active_dialog_id,
                payload.kind,
                payload.primary_user_id,
                self._log_preview(payload.purpose_text),
            )
        return True

    @staticmethod
    def _build_wake_notice(kind: str, purpose_text: str) -> str:
        return f"⏰ 已到此前设定的 echo 时间。原因：{str(purpose_text or '').strip()}"

    @staticmethod
    def _prune_records(records: list[_MomentRecord], *, now: int | None = None) -> list[_MomentRecord]:
        now_ts = int(time.time()) if now is None else int(now)
        return [record for record in records if record.trigger_time > now_ts - 86400]

    @classmethod
    def _resolve_echo_tool_args(cls, *, when: Any, reason: Any, extra_args: dict[str, Any]) -> tuple[Any, str]:
        candidates: list[tuple[str, Any]] = [("when", when)]
        preferred_time_keys = (
            "echo",
            "seconds",
            "time",
            "datetime",
            "date",
            "at",
            "when_at",
            "remind_at",
            "reminder_time",
            "delay",
            "after",
        )
        for key in preferred_time_keys:
            if key in extra_args:
                candidates.append((key, extra_args[key]))
        for key, value in extra_args.items():
            if key not in preferred_time_keys:
                candidates.append((key, value))

        selected_key = ""
        selected_when: Any = None
        first_error: Exception | None = None
        for key, value in candidates:
            if value is None or str(value).strip() == "":
                continue
            try:
                cls._parse_echo_when(value)
            except ValueError as exc:
                if first_error is None:
                    first_error = exc
                continue
            selected_key = key
            selected_when = value
            break

        if selected_when is None:
            if first_error is not None:
                raise first_error
            raise ValueError("echo.when 不能为空")

        resolved_reason = str(reason or "").strip()
        if not resolved_reason:
            reason_keys = ("reason", "purpose", "purpose_text", "message", "text", "content", "note")
            for key in reason_keys:
                value = extra_args.get(key)
                if key == selected_key or value is None:
                    continue
                text = str(value).strip()
                if text:
                    resolved_reason = text
                    break

        if selected_key != "when":
            logger.info(f"system_moment echo 使用鲁棒字段解析 when: field={selected_key}")
        return selected_when, resolved_reason

    @staticmethod
    def _log_preview(text: str, limit: int = 120) -> str:
        raw = str(text or "")
        if len(raw) <= limit:
            return raw
        return raw[:limit] + "...(truncated)"

    @staticmethod
    def _parse_echo_when(when: int | str) -> int:
        text = "" if when is None else str(when).strip()
        if not text:
            raise ValueError("echo.when 不能为空")

        if _INTEGER_RE.fullmatch(text):
            seconds = int(text)
            if seconds < 0:
                return seconds
            if seconds == 0:
                raise ValueError("echo.when 为整数时只接受负数清空或正整数秒数")
            return int(time.time()) + seconds

        normalized = text.replace("T", " ").replace("/", "-")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                dt = datetime.strptime(normalized, fmt)
                return int(dt.timestamp())
            except ValueError:
                continue

        raise ValueError(
            "无法解析 echo.when。支持：负数清空之前的定时、"
            "正整数表示距离现在的秒数、或绝对时间（YYYY-MM-DD HH:MM[:SS]）。"
        )

system_moment_service = SystemMomentService()
