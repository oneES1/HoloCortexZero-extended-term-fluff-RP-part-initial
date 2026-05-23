from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger

@dataclass(slots=True)
class DeepRouteState:
    context_id: str
    source: str
    set_at: float


class SystemTheDeepService:
    """LLM Stage1 一轮 deep 覆盖运行态。

    主干持久模式由 advanced_context_mode_service 管理并落库到 context_window。
    本服务只保留 LLM 自主插手入口：Stage1 判定需要 deep 时，当前 tool 链临时覆盖为 deep，finally 后恢复。
    普通 context 不消费该运行态，避免给普通用户引入模式切换能力。
    """

    def __init__(self) -> None:
        self._init_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._initialized = False
        self._states: Dict[str, DeepRouteState] = {}

    async def initialize_runtime(self) -> None:
        with self._init_lock:
            if self._initialized:
                return
            self.clear_runtime_states(reason="service_init")
            self._initialized = True

        logger.info("system_the_deep 运行时初始化完成")

    def clear_runtime_states(self, *, reason: str) -> None:
        with self._state_lock:
            cleared = len(self._states)
            self._states.clear()
        logger.info(f"system_the_deep 已清空运行态: reason={reason} cleared={cleared}")

    def enable_for_context(
        self,
        context_id: str,
        *,
        source: str,
    ) -> bool:
        normalized_context_id = str(context_id or "").strip()
        if not normalized_context_id:
            logger.warning(
                "system_the_deep enable 跳过: context_id 为空 "
                f"source={source}"
            )
            return False

        state = DeepRouteState(
            context_id=normalized_context_id,
            source=str(source or "manual"),
            set_at=time.time(),
        )
        with self._state_lock:
            self._states[normalized_context_id] = state
        logger.info(
            "system_the_deep 已开启: "
            f"ctx={normalized_context_id} source={state.source}"
        )
        return True

    def disable_for_context(
        self,
        context_id: str,
        *,
        source: str,
    ) -> bool:
        normalized_context_id = str(context_id or "").strip()
        if not normalized_context_id:
            logger.warning(
                "system_the_deep disable 跳过: context_id 为空 "
                f"source={source}"
            )
            return False

        removed: DeepRouteState | None = None
        with self._state_lock:
            removed = self._states.pop(normalized_context_id, None)

        if removed:
            logger.info(
                "system_the_deep 已关闭: "
                f"ctx={normalized_context_id} source={source} previous_source={removed.source}"
            )
            return True

        logger.debug(
            "system_the_deep disable 命中空状态: "
            f"ctx={normalized_context_id} source={source}"
        )
        return False

    def is_enabled(self, context_id: str) -> bool:
        normalized_context_id = str(context_id or "").strip()
        if not normalized_context_id:
            return False
        with self._state_lock:
            return normalized_context_id in self._states

    def apply_runtime_override(self, config_copy: Any, context_id: str) -> Any:
        normalized_context_id = str(context_id or "").strip()
        if not normalized_context_id or not self.is_enabled(normalized_context_id):
            return config_copy

        target_group = str(getattr(config_copy, "SYSTEM_THE_DEEP_MODEL_GROUP", "") or "").strip()
        model_groups = getattr(config_copy, "MODEL_GROUPS", {}) or {}
        if not target_group:
            logger.warning(
                f"system_the_deep 路由跳过: ctx={normalized_context_id} SYSTEM_THE_DEEP_MODEL_GROUP 为空"
            )
            return config_copy
        if target_group not in model_groups:
            logger.warning(
                "system_the_deep 路由跳过: "
                f"ctx={normalized_context_id} 模型组不存在 target={target_group}"
            )
            return config_copy

        original_group = str(getattr(config_copy, "USE_MODEL_GROUP", "") or "").strip()
        if original_group != target_group:
            logger.info(
                "system_the_deep 覆盖主模型组: "
                f"ctx={normalized_context_id} use_model_group {original_group or '<empty>'} -> {target_group}"
            )
        config_copy.USE_MODEL_GROUP = target_group
        return config_copy



system_the_deep_service = SystemTheDeepService()
