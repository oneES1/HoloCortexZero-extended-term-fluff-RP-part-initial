from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.prompt_defaults import (
    DEFAULT_MAIN_SYSTEM_PROMPT_ADVANCED,
    DEFAULT_MAIN_SYSTEM_PROMPT_ADVANCED_DEEP,
    DEFAULT_MAIN_SYSTEM_PROMPT_DEEP_SUFFIX,
    DEFAULT_MAIN_SYSTEM_PROMPT_NORMAL,
    render_identity_prompt,
)
from holo_cortex_zero.core.runtime_identity import is_advanced_user_id
from holo_cortex_zero.models.db_context_window import DBContextWindow
from holo_cortex_zero.services.the_deep import system_the_deep_service


@dataclass(frozen=True, slots=True)
class AdvancedContextModeSpec:
    name: str
    command: str
    ack_text: str
    prompt_config_field: str
    model_group_config_field: str
    fallback_prompt_config_fields: tuple[str, ...] = ()
    fallback_model_group_config_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AdvancedContextModeSelection:
    mode: str
    source: str
    prompt: str
    prompt_key: str
    model_group_key: str
    model_group_source: str
    prompt_fallback_used: bool = False
    model_group_fallback_used: bool = False


class AdvancedContextModeService:
    """高级 context 模式主干。

    主干职责：统一解析 norm/deek/deep 的命令、持久模式、prompt 与模型组。
    分支兼容：system_the_deep_service 只作为 LLM Stage1 的一轮临时 deep 覆盖，不写入持久模式。
    """

    def __init__(self) -> None:
        self._warned_keys: set[str] = set()
        self._specs: dict[str, AdvancedContextModeSpec] = {
            "norm": AdvancedContextModeSpec(
                name="norm",
                command="/norm",
                ack_text="好的喵",
                prompt_config_field="MAIN_SYSTEM_PROMPT_ADVANCED",
                model_group_config_field="USE_MODEL_GROUP",
                fallback_prompt_config_fields=("MAIN_SYSTEM_PROMPT_NORMAL",),
            ),
            "deek": AdvancedContextModeSpec(
                name="deek",
                command="/cute",
                ack_text="(≧▽≦)",
                prompt_config_field="MAIN_SYSTEM_PROMPT_ADVANCED_DEEK",
                model_group_config_field="ADVANCED_CONTEXT_MODE_DEEK_MODEL_GROUP",
                fallback_prompt_config_fields=("MAIN_SYSTEM_PROMPT_ADVANCED", "MAIN_SYSTEM_PROMPT_NORMAL"),
                fallback_model_group_config_fields=("USE_MODEL_GROUP",),
            ),
            "deep": AdvancedContextModeSpec(
                name="deep",
                command="/puss",
                ack_text="变奇怪了…喵",
                prompt_config_field="MAIN_SYSTEM_PROMPT_ADVANCED_DEEP",
                model_group_config_field="SYSTEM_THE_DEEP_MODEL_GROUP",
                fallback_prompt_config_fields=("MAIN_SYSTEM_PROMPT_ADVANCED", "MAIN_SYSTEM_PROMPT_NORMAL"),
                fallback_model_group_config_fields=("USE_MODEL_GROUP",),
            ),
        }
        self._command_to_mode = {spec.command: spec.name for spec in self._specs.values()}

    @property
    def valid_modes(self) -> set[str]:
        return set(self._specs.keys())

    def normalize_mode(self, mode: Any) -> str:
        normalized = str(mode or "").strip().lower()
        return normalized if normalized in self._specs else ""

    def parse_mode_command(self, text: Any) -> Optional[AdvancedContextModeSpec]:
        normalized = str(text or "").strip()
        mode = self._command_to_mode.get(normalized)
        return self._specs.get(mode) if mode else None

    def get_spec(self, mode: Any) -> AdvancedContextModeSpec:
        normalized = self.normalize_mode(mode) or "norm"
        return self._specs[normalized]

    @classmethod
    def is_advanced_context(cls, context_window: DBContextWindow) -> bool:
        return bool(
            str(getattr(context_window, "owner_type", "") or "") == "advanced"
            and is_advanced_user_id(str(getattr(context_window, "context_id", "") or "").strip(), config)
        )

    def get_effective_mode(self, context_window: DBContextWindow) -> tuple[str, str]:
        if self.is_advanced_context(context_window) and system_the_deep_service.is_enabled(context_window.context_id):
            return "deep", "llm"

        mode = self.normalize_mode(getattr(context_window, "advanced_context_mode", ""))
        source = str(getattr(context_window, "advanced_context_mode_source", "") or "default").strip() or "default"
        if not mode:
            return "norm", "fallback"
        if source not in {"default", "manual"}:
            source = "default"
        return mode, source

    def get_ack_text(self, mode: Any) -> str:
        return self.get_spec(mode).ack_text

    def select_prompt(self, context_window: DBContextWindow) -> AdvancedContextModeSelection:
        if not self.is_advanced_context(context_window):
            normal_prompt = self._get_config_text("MAIN_SYSTEM_PROMPT_NORMAL") or DEFAULT_MAIN_SYSTEM_PROMPT_NORMAL
            normal_prompt = render_identity_prompt(normal_prompt, config)
            return AdvancedContextModeSelection(
                mode="normal",
                source="normal",
                prompt=normal_prompt,
                prompt_key="MAIN_SYSTEM_PROMPT_NORMAL",
                model_group_key="",
                model_group_source="normal_context",
            )

        mode, source = self.get_effective_mode(context_window)
        spec = self.get_spec(mode)
        prompt, prompt_key, fallback_used = self._resolve_prompt(spec)
        prompt = render_identity_prompt(prompt, config)
        return AdvancedContextModeSelection(
            mode=mode,
            source=source,
            prompt=prompt,
            prompt_key=prompt_key,
            model_group_key="",
            model_group_source="prompt_only",
            prompt_fallback_used=fallback_used,
        )

    def select_model_group(self, context_window: DBContextWindow) -> AdvancedContextModeSelection:
        mode, source = self.get_effective_mode(context_window)
        spec = self.get_spec(mode)
        model_group_key, model_group_source, fallback_used = self._resolve_model_group(spec)
        prompt, prompt_key, prompt_fallback_used = self._resolve_prompt(spec)
        prompt = render_identity_prompt(prompt, config)
        return AdvancedContextModeSelection(
            mode=mode,
            source=source,
            prompt=prompt,
            prompt_key=prompt_key,
            model_group_key=model_group_key,
            model_group_source=model_group_source,
            prompt_fallback_used=prompt_fallback_used,
            model_group_fallback_used=fallback_used,
        )

    def _resolve_prompt(self, spec: AdvancedContextModeSpec) -> tuple[str, str, bool]:
        prompt = self._get_config_text(spec.prompt_config_field)
        if prompt:
            return prompt, spec.prompt_config_field, False

        if spec.name == "deep":
            advanced_prompt = self._get_config_text("MAIN_SYSTEM_PROMPT_ADVANCED") or self._get_config_text("MAIN_SYSTEM_PROMPT_NORMAL")
            if advanced_prompt:
                return f"{advanced_prompt}\n\n{DEFAULT_MAIN_SYSTEM_PROMPT_DEEP_SUFFIX}", spec.prompt_config_field, True
            default_prompt = DEFAULT_MAIN_SYSTEM_PROMPT_ADVANCED_DEEP
            if default_prompt.strip():
                return default_prompt, spec.prompt_config_field, True

        if spec.name == "deek":
            self._warn_once(
                "missing_deek_prompt",
                "advanced context mode deek prompt 未配置，已回退高级 prompt: field=MAIN_SYSTEM_PROMPT_ADVANCED_DEEK",
            )

        for field_name in spec.fallback_prompt_config_fields:
            fallback = self._get_config_text(field_name)
            if fallback:
                return fallback, field_name, True

        if spec.name in {"norm", "deek", "deep"}:
            default_advanced = DEFAULT_MAIN_SYSTEM_PROMPT_ADVANCED or DEFAULT_MAIN_SYSTEM_PROMPT_NORMAL
            return default_advanced, "DEFAULT_MAIN_SYSTEM_PROMPT_ADVANCED", True
        return DEFAULT_MAIN_SYSTEM_PROMPT_NORMAL, "DEFAULT_MAIN_SYSTEM_PROMPT_NORMAL", True

    def _resolve_model_group(self, spec: AdvancedContextModeSpec) -> tuple[str, str, bool]:
        configured = self._get_config_text(spec.model_group_config_field)
        if configured:
            return configured, spec.model_group_config_field, False

        if spec.name == "deek":
            self._warn_once(
                "missing_deek_model_group",
                "advanced context mode deek 模型组未配置，已回退 USE_MODEL_GROUP: field=ADVANCED_CONTEXT_MODE_DEEK_MODEL_GROUP",
            )

        for field_name in spec.fallback_model_group_config_fields:
            fallback = self._get_config_text(field_name)
            if fallback:
                return fallback, field_name, True
        return "", "", True

    @staticmethod
    def _get_config_text(field_name: str) -> str:
        return str(getattr(config, field_name, "") or "").strip()

    def _warn_once(self, key: str, message: str) -> None:
        if key in self._warned_keys:
            return
        self._warned_keys.add(key)
        logger.warning(message)


advanced_context_mode_service = AdvancedContextModeService()
