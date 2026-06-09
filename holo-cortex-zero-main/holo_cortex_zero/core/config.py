import json
import os
from pathlib import Path
from typing import Dict, List, Literal, Optional, TypeVar

import yaml
from pydantic import AliasChoices, Field

from holo_cortex_zero.schemas.i18n import i18n_text

from .core_utils import ConfigBase, ExtraField
from .os_env import OsEnv
from .prompt_defaults import (
    DEFAULT_AUTO_MEMORY_SYSTEM_PROMPT,
    DEFAULT_BOT_PERSONA_DISPLAY_NAME,
    DEFAULT_MAIN_SYSTEM_PROMPT_ADVANCED,
    DEFAULT_MAIN_SYSTEM_PROMPT_ADVANCED_DEEP,
    DEFAULT_MAIN_SYSTEM_PROMPT_DEEP_SUFFIX,
    DEFAULT_MAIN_SYSTEM_PROMPT_NORMAL,
    DEFAULT_MEMORY_ARBITER_SYSTEM_PROMPT_TEMPLATE,
    DEFAULT_SUBCONSCIOUS_SYSTEM_PROMPT,
    DEFAULT_TIMELINE_SYSTEM_PROMPT,
)
from .runtime_identity import (
    DEFAULT_ADVANCED_USER_DISPLAY_NAME,
    DEFAULT_ADVANCED_USER_ID,
    normalize_advanced_user_id,
)

CONFIG_DIR = Path(OsEnv.DATA_DIR) / "configs"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = Path(OsEnv.DATA_DIR) / "configs" / "holo-cortex-zero.yaml"

_CURRENT_RUNTIME_EMOJI_DIR = Path(OsEnv.WORKSPACE_ROOT) / "emoji"
_CURRENT_SHARED_ROOT = Path(OsEnv.WORKSPACE_ROOT) / "shared"


class ModelConfigGroup(ConfigBase):
    """模型配置组"""

    GROUP_NAME: str = Field(default="", title="LLM名称")
    CHAT_MODEL: str = Field(default="", title="聊天模型名称")
    USE_GLOBAL_PROXY: bool = Field(default=False, title="启用全局代理")
    CHAT_PROXY: str = Field(default="", title="聊天模型访问代理")
    BASE_URL: str = Field(default="", title="聊天模型 API 地址")
    API_KEY: str = Field(default="", title="聊天模型 API 密钥")
    MODEL_TYPE: Literal["chat", "embedding", "draw"] = Field(
        default="chat",
        title="模型类型",
        description="模型的用途类型，可以是聊天(chat)、向量嵌入(embedding)或绘图(draw)",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="模型的用途类型，可以是聊天(chat)、向量嵌入(embedding)或绘图(draw)",
                en_US="Model purpose: chat, embedding, or draw",
            ),
        ).model_dump(),
    )
    TOKEN_INPUT_RATE: float = Field(default=1.0, title="输入 Token 倍率")
    TOKEN_COMPLETION_RATE: float = Field(default=1.0, title="补全 Token 倍率")
    MODEL_PRICE_RATE: float = Field(default=1.0, title="模型价格倍率")
    TEMPERATURE: Optional[float] = Field(default=None, title="温度值")
    TOP_P: Optional[float] = Field(default=None, title="Top P")
    TOP_K: Optional[int] = Field(default=None, title="Top K")
    MAX_OUTPUT_TOKENS: Optional[int] = Field(
        default=None,
        title="总输出 Token 上限",
        description="仅新架构 /responses 主链使用；为空表示不显式限制。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="仅新架构 /responses 主链使用；为空表示不显式限制。",
                en_US="New-arch /responses main chain only; empty means no explicit limit.",
            ),
        ).model_dump(),
    )
    IMAGE_MAX_COUNT: Optional[int] = Field(
        default=None,
        ge=0,
        title="图片数量上限",
        description="每次请求允许发送给模型的 user 图片数量上限。为空表示不限，0 表示不向模型发送图片，正整数表示限额。正整数限额下内置系统形象参考图始终优先保留，超出部分按从旧到新降级为文本。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="每次请求允许发送给模型的 user 图片数量上限。为空表示不限，0 表示不向模型发送图片，正整数表示限额。正整数限额下内置系统形象参考图始终优先保留，超出部分按从旧到新降级为文本。",
                en_US="Max user images sent to the model per request. Empty = unlimited, 0 = no images, positive = limit. Built-in system reference images are always kept first; excess images are downgraded to text from oldest to newest.",
            ),
        ).model_dump(),
    )
    REASONING_MODE: Literal["", "default", "off", "minimal", "low", "medium", "high"] = Field(
        default="default",
        title="思维模式",
        description="仅新架构 /responses 主链使用；default=不覆盖，off=关闭思维链。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="仅新架构 /responses 主链使用；default=不覆盖，off=关闭思维链。",
                en_US="New-arch /responses main chain only; default = do not override, off = disable reasoning chain.",
            ),
        ).model_dump(),
    )
    TEXT_VERBOSITY: Literal["", "default", "low", "medium", "high"] = Field(
        default="default",
        title="正文冗长度",
        description="仅新架构 /responses 主链使用；default=不覆盖。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="仅新架构 /responses 主链使用；default=不覆盖。",
                en_US="New-arch /responses main chain only; default = do not override.",
            ),
        ).model_dump(),
    )
    REPLAY_REASONING_CONTENT: bool = Field(
        default=False,
        title="回放思维链",
        description="启用后把模型返回的 reasoning_content 透明带回后续 tool 请求；适用于明确支持该字段的思维链 LLM。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="启用后把模型返回的 reasoning_content 透明带回后续 tool 请求；适用于明确支持该字段的思维链 LLM。",
                en_US="When enabled, transparently carry model reasoning_content into subsequent tool requests; for reasoning LLMs that explicitly support this field.",
            ),
        ).model_dump(),
    )
    PRESENCE_PENALTY: Optional[float] = Field(default=None, title="提示重复惩罚")
    FREQUENCY_PENALTY: Optional[float] = Field(default=None, title="补全重复惩罚")
    EXTRA_BODY: Optional[str] = Field(default=None, title="额外参数 (JSON)")
    WIRE_API: Literal["default", "chat", "responses", "gemini"] = Field(
        default="default",
        title="协议发射器",
        description="显式指定该 LLM 走哪条协议主链；default=保持当前自动判定逻辑，其他值将强制走对应协议。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="显式指定该 LLM 走哪条协议主链；default=保持当前自动判定逻辑，其他值将强制走对应协议。",
                en_US="Explicitly specify which protocol main chain this LLM uses; default = keep current auto-detection, other values force the corresponding protocol.",
            ),
        ).model_dump(),
    )
    CACHE_TRANSPORT_PROFILE: str = Field(
        default="default",
        title="缓存传输策略",
        description="default=保持框架当前自动策略；cache_control=发送顶层 cache_control；prompt_cache_key=发送 OpenAI 格式 prompt_cache_key；cache_prompt=发送本地 cache_prompt=True；off=关闭显式缓存字段。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="default=保持框架当前自动策略；cache_control=发送顶层 cache_control；prompt_cache_key=发送 OpenAI 格式 prompt_cache_key；cache_prompt=发送本地 cache_prompt=True；off=关闭显式缓存字段。",
                en_US="default = keep current framework auto strategy; cache_control = send top-level cache_control; prompt_cache_key = send OpenAI-format prompt_cache_key; cache_prompt = send local cache_prompt=True; off = disable explicit cache fields.",
            ),
        ).model_dump(),
    )
    REASONING_EFFORT: Literal["", "minimal", "low", "medium", "high", "xhigh"] = Field(
        default="",
        title="思维强度",
        description="旧字段，保留兼容；新架构 GUI 请改用思维模式。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="旧字段，保留兼容；新架构 GUI 请改用思维模式。",
                en_US="Legacy field kept for compatibility; new-arch GUI should use Reasoning Mode instead.",
            ),
            is_hidden=True,
        ).model_dump(),
    )


class CoreConfig(ConfigBase):
    """核心配置"""

    ADVANCED_USER_ID: str = Field(
        default=DEFAULT_ADVANCED_USER_ID,
        title="对智能体的统一ID标识",
        description="高级 context 主用户；高级用户的 context_id 固定为该 user_id。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="对智能体的统一ID标识",
            en_US="Unified ID for the Agent",
        ),
        i18n_description=i18n_text(
            zh_CN="高级 context 主用户；高级用户的 context_id 固定为该 user_id。",
            en_US="Primary advanced user; the context_id for advanced users is fixed to this user_id.",
        ),
    ).model_dump(),
    )
    ADVANCED_USER_DISPLAY_NAME: str = Field(
        default=DEFAULT_ADVANCED_USER_DISPLAY_NAME,
        title="你对智能体的统一昵称",
        description="高级用户在内部身份纠偏、附件提示与 prompt 默认模板中的显示名。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="你对智能体的统一昵称",
            en_US="Your Unified Nickname for the Agent",
        ),
        i18n_description=i18n_text(
            zh_CN="高级用户在内部身份纠偏、附件提示与 prompt 默认模板中的显示名。",
            en_US="Display name for the advanced user in identity correction, attachment hints, and default prompt templates.",
        ),
    ).model_dump(),
    )
    ENSURE_SFW_CONTENT: bool = Field(
        default=True,
        json_schema_extra=ExtraField(is_hidden=True).model_dump(),
    )

    """应用配置"""
    APP_LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        title="应用日志级别",
        description="应用日志级别，需要重启应用后生效",
        json_schema_extra=ExtraField(
            is_hidden=True,
            i18n_title=i18n_text(
                zh_CN="应用日志级别",
                en_US="Application Log Level",
            ),
            i18n_description=i18n_text(
                zh_CN="应用日志级别，需要重启应用后生效",
                en_US="Application log level, requires restart to take effect",
            ),
        ).model_dump(),
    )
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=10,
        title="上传文件大小限制 (MB)",
        json_schema_extra=ExtraField(
            i18n_title=i18n_text(
                zh_CN="上传文件大小限制 (MB)",
                en_US="Upload File Size Limit (MB)",
            ),
        ).model_dump(),
    )
    """OpenAI API 配置"""
    MODEL_GROUPS: Dict[str, ModelConfigGroup] = Field(
        default={

        },
        title="LLM 配置",
        json_schema_extra=ExtraField(is_hidden=True).model_dump(),
    )
    USE_MODEL_GROUP: str = Field(
        default="",
        title="群聊里回复你的LLM",
        json_schema_extra=ExtraField(
            ref_model_groups=True,
            required=True,
            model_type="chat",
            overridable=True,
            i18n_title=i18n_text(
                zh_CN="群聊里回复你的LLM",
                en_US="LLM That Replies to You in Group Chats",
            ),
            i18n_description=i18n_text(
                zh_CN="你本人在任何聊天框发送 /norm，强制在任何窗口切换为该 LLM",
                en_US="When you send /norm in any chat box, force any window to switch to this LLM",
            ),
        ).model_dump(),
        description="你本人在任何聊天框发送 /norm，强制在任何窗口切换为该 LLM。",
    )
    ADVANCED_CONTEXT_MODE_DEEK_MODEL_GROUP: str = Field(
        default="",
        title="私聊回复你的LLM",
        json_schema_extra=ExtraField(
            ref_model_groups=True,
            model_type="chat",
            i18n_title=i18n_text(
                zh_CN="私聊回复你的LLM",
                en_US="LLM That Replies to You in Private Chats",
            ),
            i18n_description=i18n_text(
                zh_CN="你本人在任何聊天框发送 /cute，强制在任何窗口切换为该 LLM",
                en_US="When you send /cute in any chat box, force any window to switch to this LLM",
            ),
        ).model_dump(),
        description="你本人在任何聊天框发送 /cute，强制在任何窗口切换为该 LLM。",
    )
    SYSTEM_THE_DEEP_MODEL_GROUP: str = Field(
        default="",
        title="你专用的高级LLM",
        json_schema_extra=ExtraField(
            ref_model_groups=True,
            model_type="chat",
            i18n_title=i18n_text(
                zh_CN="你专用的高级LLM",
                en_US="Your Dedicated Advanced LLM",
            ),
            i18n_description=i18n_text(
                zh_CN="你本人在任何聊天框发送 /puss，在任何窗口切换为该模型，后续更换聊天窗口后会恢复默认",
                en_US="When you send /puss in any chat box, switch any window to this model; after changing chat windows later, it restores the default",
            ),
        ).model_dump(),
        description="你本人在任何聊天框发送 /puss，在任何窗口切换为该模型，后续更换聊天窗口后会恢复默认。",
    )
    NORMAL_USER_MODEL_GROUP: str = Field(
        default="",
        title="回复其他人的LLM",
        json_schema_extra=ExtraField(
            ref_model_groups=True,
            model_type="chat",
            overridable=True,
            i18n_title=i18n_text(
                zh_CN="回复其他人的LLM",
                en_US="LLM That Replies to Other People",
            ),
            i18n_description=i18n_text(
                zh_CN="回复其他普通用户时使用的 LLM",
                en_US="LLM used when replying to other normal users",
            ),
        ).model_dump(),
        description="回复其他普通用户时使用的 LLM。",
    )
    FALLBACK_MODEL_GROUP: str = Field(
        default="",
        title="备用LLM",
        json_schema_extra=ExtraField(
            ref_model_groups=True,
            model_type="chat",
            overridable=True,
            i18n_title=i18n_text(
                zh_CN="备用LLM",
                en_US="Fallback LLM",
            ),
            i18n_description=i18n_text(
                zh_CN="当主 LLM 不可用时，使用备用 LLM",
                en_US="LLM used when the primary LLM is unavailable",
            ),
        ).model_dump(),
        description="当主 LLM 不可用时，使用备用 LLM。",
    )
    MULTIMODAL_MODEL_GROUP: str = Field(
        default="",
        title="多模态LLM",
        validation_alias=AliasChoices("MULTIMODAL_MODEL_GROUP", "DEBUG_MIGRATION_MODEL_GROUP"),
        json_schema_extra=ExtraField(
            ref_model_groups=True,
            model_type="chat",
            overridable=True,
            i18n_title=i18n_text(
                zh_CN="多模态LLM",
                en_US="Multimodal LLM",
            ),
            i18n_description=i18n_text(
                zh_CN="名义上的多模态优先 LLM，常用于承载 Gemini 等多模态模型；它本身不改变 tool 链或 fallback 主干。",
                en_US="Nominal multimodal-preferred LLM, commonly used for Gemini-class models; it does not change the main tool-chain or fallback routing by itself.",
            ),
        ).model_dump(),
        description="名义上的多模态优先 LLM，常用于承载 Gemini 等多模态模型；它本身不改变 tool 链或 fallback 主干。",
    )

    """聊天配置"""
    BOT_PERSONA_DISPLAY_NAME: str = Field(
        default=DEFAULT_BOT_PERSONA_DISPLAY_NAME,
        title="智能体昵称",
        description="统一用于协议展示、聊天记录落库与界面展示的单人格名称。",
        json_schema_extra=ExtraField(
            is_hidden=True,
            i18n_title=i18n_text(
                zh_CN="智能体昵称",
                en_US="Agent Nickname",
            ),
            i18n_description=i18n_text(
                zh_CN="统一用于协议展示、聊天记录落库与界面展示的单人格名称。",
                en_US="Unified persona display name used for protocol presentation, chat history storage, and UI display.",
            ),
        ).model_dump(),
    )
    BOT_MESSAGE_BACKFILL_CLEANUP_ENABLED: bool = Field(
        default=False,
        title="启用 bot 消息长度回填清理",
        description="开启后，仅对写回框架上下文的长 bot 回复使用辅助 LLM 提炼；不影响对外发送内容。",
        json_schema_extra=ExtraField(
            i18n_title=i18n_text(
                zh_CN="启用 bot 消息长度回填清理",
                en_US="Enable Bot Backfill Cleanup",
            ),
            i18n_description=i18n_text(
                zh_CN="开启后，仅对写回框架上下文的长 bot 回复使用辅助 LLM 提炼；不影响对外发送内容。",
                en_US="When enabled, long bot replies are summarized only for framework context backfill; visible outgoing replies are unchanged.",
            ),
        ).model_dump(),
    )
    BOT_MESSAGE_BACKFILL_CLEANUP_MODEL_GROUP: str = Field(
        default="",
        title="bot 消息长度回填清理 LLM",
        description="用于 bot 上下文回填清理的辅助聊天 LLM；为空时触发清理会降级为原文本回填。",
        json_schema_extra=ExtraField(
            ref_model_groups=True,
            model_type="chat",
            i18n_title=i18n_text(
                zh_CN="bot 消息长度回填清理 LLM",
                en_US="Bot Backfill Cleanup LLM",
            ),
            i18n_description=i18n_text(
                zh_CN="用于 bot 上下文回填清理的辅助聊天 LLM；为空时触发清理会降级为原文本回填。",
                en_US="Auxiliary chat LLM used for bot context backfill cleanup; empty falls back to original text backfill.",
            ),
        ).model_dump(),
    )
    BOT_MESSAGE_BACKFILL_CLEANUP_THRESHOLD_CHARS: int = Field(
        default=120,
        ge=1,
        title="bot 消息长度回填清理阈值",
        description="bot 回填文本超过该字符数时才调用辅助 LLM 清理。",
        json_schema_extra=ExtraField(
            i18n_title=i18n_text(
                zh_CN="bot 消息长度回填清理阈值",
                en_US="Bot Backfill Cleanup Threshold",
            ),
            i18n_description=i18n_text(
                zh_CN="bot 回填文本超过该字符数时才调用辅助 LLM 清理。",
                en_US="Only bot backfill text longer than this character count uses the auxiliary cleanup LLM.",
            ),
        ).model_dump(),
    )
    MAIN_SYSTEM_PROMPT_NORMAL: str = Field(
        default=DEFAULT_MAIN_SYSTEM_PROMPT_NORMAL,
        title="普通用户上下文系统提示词",
        description="普通用户 context_id 使用的主人格 system prompt。",
        json_schema_extra=ExtraField(
            is_textarea=True,
            is_hidden=True,
            i18n_title=i18n_text(
                zh_CN="普通用户上下文系统提示词",
                en_US="Normal User Context System Prompt",
            ),
            i18n_description=i18n_text(
                zh_CN="普通用户 context_id 使用的主人格 system prompt。",
                en_US="Main persona system prompt used by normal user context_id.",
            ),
        ).model_dump(),
    )
    MAIN_SYSTEM_PROMPT_ADVANCED: str = Field(
        default=DEFAULT_MAIN_SYSTEM_PROMPT_ADVANCED,
        title="群聊回复你的norm模式提示词",
        description="高级用户 context_id 在非 deep 状态下使用的主人格 system prompt。",
        json_schema_extra=ExtraField(
            is_textarea=True,
            is_hidden=True,
            i18n_title=i18n_text(
                zh_CN="群聊回复你的norm模式提示词",
                en_US="Group Chat Reply-to-You Norm Mode Prompt",
            ),
            i18n_description=i18n_text(
                zh_CN="高级用户 context_id 在非 deep 状态下使用的主人格 system prompt。",
                en_US="Main persona system prompt for advanced user context_id in non-deep state.",
            ),
        ).model_dump(),
    )
    MAIN_SYSTEM_PROMPT_ADVANCED_DEEK: str = Field(
        default="",
        title="私聊回复你的cute模式提示词",
        description="高级用户 context_id 在 deek 状态下使用的主人格 system prompt；为空时回退群聊回复你的norm模式提示词并写日志提醒手填。",
        json_schema_extra=ExtraField(
            is_textarea=True,
            is_hidden=True,
            i18n_title=i18n_text(
                zh_CN="私聊回复你的cute模式提示词",
                en_US="Private Chat Reply-to-You Cute Mode Prompt",
            ),
            i18n_description=i18n_text(
                zh_CN="高级用户 context_id 在 deek 状态下使用的主人格 system prompt；为空时回退群聊回复你的norm模式提示词并写日志提醒手填。",
                en_US="Main persona system prompt for advanced user context_id in deek state; falls back to norm prompt when empty with a log reminder.",
            ),
        ).model_dump(),
    )
    MAIN_SYSTEM_PROMPT_ADVANCED_DEEP: str = Field(
        default=DEFAULT_MAIN_SYSTEM_PROMPT_ADVANCED_DEEP,
        title="你专用的Pro模式提示词/puss触发",
        description="高级用户 context_id 在 deep 状态下使用的主人格 system prompt。",
        json_schema_extra=ExtraField(
            is_textarea=True,
            is_hidden=True,
            i18n_title=i18n_text(
                zh_CN="你专用的Pro模式提示词/puss触发",
                en_US="Your Dedicated Pro Mode Prompt /puss Trigger",
            ),
            i18n_description=i18n_text(
                zh_CN="高级用户 context_id 在 deep 状态下使用的主人格 system prompt。",
                en_US="Main persona system prompt for advanced user context_id in deep state.",
            ),
        ).model_dump(),
    )
    ADVANCED_CONTEXT_PRIVATE_DEFAULT_MODE: str = Field(
        default="deek",
        title="高级 context 私聊默认模式",
        description="高级用户切换到私聊对话窗口时默认覆盖的模式。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="高级用户切换到私聊对话窗口时默认覆盖的模式。",
                en_US="Default mode override when advanced user switches to private chat window.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    ADVANCED_CONTEXT_GROUP_DEFAULT_MODE: str = Field(
        default="norm",
        title="高级 context 群聊默认模式",
        description="高级用户切换到群聊对话窗口时默认覆盖的模式。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="高级用户切换到群聊对话窗口时默认覆盖的模式。",
                en_US="Default mode override when advanced user switches to group chat window.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    ADVANCED_CONTEXT_MAX_HISTORY_BEFORE_COMPRESS: int = Field(
        default=100,
        ge=1,
        title="高级 context 压缩阈值",
        description="高级 context 累计到多少条历史消息后触发压缩与归档。",
        json_schema_extra=ExtraField(
            overridable=True,
            i18n_title=i18n_text(
                zh_CN="高级 context 压缩阈值",
                en_US="Advanced Context Compression Threshold",
            ),
            i18n_description=i18n_text(
                zh_CN="高级 context 累计到多少条历史消息后触发压缩与归档",
                en_US="Trigger compression and archiving after this many history messages",
            ),
        ).model_dump(),
    )
    ADVANCED_CONTEXT_KEEP_RECENT_AFTER_COMPRESS: int = Field(
        default=10,
        ge=1,
        title="高级 context 压缩后保留条数",
        description="高级 context 触发压缩后保留的最近消息条数。",
        json_schema_extra=ExtraField(
            overridable=True,
            i18n_title=i18n_text(
                zh_CN="高级 context 压缩后保留条数",
                en_US="Advanced Context Keep Recent After Compress",
            ),
            i18n_description=i18n_text(
                zh_CN="高级 context 触发压缩后保留的最近消息条数",
                en_US="Number of recent messages kept after compression",
            ),
        ).model_dump(),
    )
    ADVANCED_CONTEXT_HARD_LIMIT_RATIO: float = Field(
        default=1.2,
        ge=1.0,
        title="高级 context 硬上限倍率",
        description="高级 context 的硬删除上限倍率，通常为压缩阈值的 1.2 倍。",
        json_schema_extra=ExtraField(
            is_hidden=True,
            overridable=True,
            i18n_title=i18n_text(
                zh_CN="高级 context 硬上限倍率",
                en_US="Advanced Context Hard Limit Multiplier",
            ),
            i18n_description=i18n_text(
                zh_CN="高级 context 的硬删除上限倍率，通常为压缩阈值的 1.2 倍",
                en_US="Hard deletion limit multiplier for advanced context, usually 1.2x the compression threshold",
            ),
        ).model_dump(),
    )
    AI_CHAT_CONTEXT_MAX_LENGTH: int = Field(
        default=32,
        title="记忆检索取样的最近聊天消息数",
        json_schema_extra=ExtraField(
            overridable=True,
            i18n_title=i18n_text(
                zh_CN="记忆检索取样的最近聊天消息数",
                en_US="Recent Chat Message Sample Count for Memory Retrieval",
            ),
            i18n_description=i18n_text(
                zh_CN="",
                en_US="",
            ),
        ).model_dump(),
        description="",
    )
    NORMAL_CONTEXT_MEMORY_RECALL_REFRESH_EVERY: int = Field(
        default=4,
        ge=1,
        title="普通 context 回忆刷新间隔",
        description="普通 context 每累计多少次用户触发才重新计算一次潜意识与 Stage1/Stage2 回忆；其余轮次复用上次缓存。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="普通 context 回忆刷新间隔",
            en_US="Normal Context Memory Recall Refresh Interval",
        ),
        i18n_description=i18n_text(
            zh_CN="普通 context 每累计多少次用户触发才重新计算一次潜意识与 Stage1/Stage2 回忆；其余轮次复用上次缓存。",
            en_US="How many user triggers before recalculating subconscious and Stage1/Stage2 memory for normal context; otherwise reuse cached results.",
        ),
    ).model_dump(),
    )
    NORMAL_CONTEXT_RESET_THRESHOLD_MESSAGES: int = Field(
        default=48,
        ge=1,
        title="普通 context 重置阈值",
        description="普通 context 原始上下文累计到多少条后，一次性回收旧历史。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="普通 context 重置阈值",
            en_US="Normal Context Reset Threshold",
        ),
        i18n_description=i18n_text(
            zh_CN="普通 context 原始上下文累计到多少条后，一次性回收旧历史。",
            en_US="Normal context raw history message count threshold before one-time old history cleanup.",
        ),
    ).model_dump(),
    )
    NORMAL_CONTEXT_RESET_KEEP_MESSAGES: int = Field(
        default=10,
        ge=1,
        title="普通 context 重置保留条数",
        description="普通 context 达到重置阈值后保留的最近原始消息条数。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="普通 context 重置保留条数",
            en_US="Normal Context Reset Keep Messages",
        ),
        i18n_description=i18n_text(
            zh_CN="普通 context 达到重置阈值后保留的最近原始消息条数。",
            en_US="Number of recent raw messages kept after normal context reaches reset threshold.",
        ),
    ).model_dump(),
    )
    AI_REPLY_ENABLED: bool = Field(
        default=True,
        title="启用系统 ai_reply",
        description="系统级 ai_reply 入口固定启用；保留字段仅用于兼容旧配置。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="系统级 ai_reply 入口固定启用；保留字段仅用于兼容旧配置。",
                en_US="System-level ai_reply entry is always enabled; kept for backward compatibility.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    AI_REPLY_JUDGE_ENABLED: bool = Field(
        default=True,
        title="启用群聊回复判断",
        description="仅对普通群聊 context 启用 LLM 回复判断；私聊与高级用户 context 不受影响。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="启用群聊回复判断",
            en_US="Enable Group Chat Reply Judgment",
        ),
        i18n_description=i18n_text(
            zh_CN="仅对普通群聊 context 启用 LLM 回复判断；私聊与高级用户 context 不受影响。",
            en_US="Enable LLM reply judgment for normal group chat contexts only; private chats and advanced users are unaffected.",
        ),
    ).model_dump(),
    )
    AI_REPLY_JUDGE_MODEL_GROUP: str = Field(
        default="",
        title="群聊回复判断LLM",
        description="系统级 ai_reply 群聊回复判断专用的 chat.completions LLM。",
        json_schema_extra=ExtraField(
            ref_model_groups=True,
            model_type="chat",
            i18n_title=i18n_text(
                zh_CN="群聊回复判断LLM",
                en_US="Group Chat Reply Judgment LLM",
            ),
            i18n_description=i18n_text(
                zh_CN="系统级 ai_reply 群聊回复判断专用的 chat.completions LLM。",
                en_US="Dedicated chat.completions LLM for system-level ai_reply group chat judgment.",
            ),
        ).model_dump(),
    )
    AI_REPLY_JUDGE_SYSTEM_PROMPT: str = Field(
        default="",
        title="群聊回复判断系统提示词",
        description="普通群聊回复判断使用的原版 system prompt 原文；为空时默认 fail-close。",
        json_schema_extra=ExtraField(
            is_textarea=True,
            is_hidden=True,
            i18n_title=i18n_text(
                zh_CN="群聊回复判断系统提示词",
                en_US="Group Chat Reply Judgment System Prompt",
            ),
            i18n_description=i18n_text(
                zh_CN="普通群聊回复判断使用的原版 system prompt 原文；为空时默认 fail-close。",
                en_US="Original system prompt for normal group chat reply judgment; defaults to fail-close when empty.",
            ),
        ).model_dump(),
    )
    SUBCONSCIOUS_SYSTEM_PROMPT: str = Field(
        default=DEFAULT_SUBCONSCIOUS_SYSTEM_PROMPT,
        title="潜意识系统提示词",
        description="Stage1 潜意识路由使用的 system prompt。",
        json_schema_extra=ExtraField(
            is_textarea=True,
            is_hidden=True,
            i18n_title=i18n_text(
                zh_CN="潜意识系统提示词",
                en_US="Subconscious System Prompt",
            ),
            i18n_description=i18n_text(
                zh_CN="Stage1 潜意识路由使用的 system prompt。",
                en_US="System prompt used for Stage1 subconscious routing.",
            ),
        ).model_dump(),
    )
    TIMELINE_SYSTEM_PROMPT: str = Field(
        default=DEFAULT_TIMELINE_SYSTEM_PROMPT,
        title="Timeline 系统提示词",
        description="时间线摘要压缩使用的 system prompt。",
        json_schema_extra=ExtraField(
            is_textarea=True,
            is_hidden=True,
            i18n_title=i18n_text(
                zh_CN="Timeline 系统提示词",
                en_US="Timeline System Prompt",
            ),
            i18n_description=i18n_text(
                zh_CN="时间线摘要压缩使用的 system prompt。",
                en_US="System prompt used for timeline summary compression.",
            ),
        ).model_dump(),
    )
    TIMELINE_MODEL_GROUP: str = Field(
        default="",
        title="Timeline 压缩LLM",
        description="时间线摘要压缩专用 LLM；必须显式配置有效 LLM，不再隐式回退到 default。",
        json_schema_extra=ExtraField(
            ref_model_groups=True,
            model_type="chat",
            i18n_title=i18n_text(
                zh_CN="Timeline 压缩LLM",
                en_US="Timeline Compression LLM",
            ),
            i18n_description=i18n_text(
                zh_CN="时间线摘要压缩专用 LLM；必须显式配置有效 LLM，不再隐式回退到 default。",
                en_US="Dedicated LLM for timeline summary compression; must be explicitly configured, no implicit fallback to default.",
            ),
        ).model_dump(),
    )
    AI_REPLY_JUDGE_MAX_HISTORY_MESSAGES: int = Field(
        default=12,
        ge=1,
        title="群聊回复判断历史条数",
        description="普通群聊回复判断时，最多读取多少条纯文本聊天历史。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="群聊回复判断历史条数",
            en_US="Group Chat Reply Judgment History Messages",
        ),
        i18n_description=i18n_text(
            zh_CN="普通群聊回复判断时，最多读取多少条纯文本聊天历史。",
            en_US="Maximum number of plain text chat history messages read during normal group chat reply judgment.",
        ),
    ).model_dump(),
    )
    AI_REPLY_JUDGE_TIMEOUT_SECONDS: int = Field(
        default=12,
        ge=1,
        title="群聊回复判断超时秒数",
        description="普通群聊回复判断辅助 LLM 的超时时间（秒）。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="群聊回复判断超时秒数",
            en_US="Group Chat Reply Judgment Timeout (seconds)",
        ),
        i18n_description=i18n_text(
            zh_CN="普通群聊回复判断辅助 LLM 的超时时间（秒）。",
            en_US="Timeout for the auxiliary LLM used in normal group chat reply judgment (seconds).",
        ),
    ).model_dump(),
    )
    LLM_RESPONSES_STREAM_IDLE_TIMEOUT_SECONDS: int = Field(
        default=50,
        ge=1,
        title="Responses 流式空闲超时秒数",
        description="通用 /responses 主干在流式传输下，连续多长时间没有新事件就判定为空闲超时（秒）。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="通用 /responses 主干在流式传输下，连续多长时间没有新事件就判定为空闲超时（秒）。",
                en_US="Generic /responses backbone streaming idle timeout: how many seconds without new events before considered idle.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    AI_REPLY_JUDGE_FAIL_OPEN: bool = Field(
        default=False,
        title="群聊回复判断失败时放行",
        description="为 false 时 fail-close；为 true 时判断异常会放行回复。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="为 false 时 fail-close；为 true 时判断异常会放行回复。",
                en_US="When false, fail-close; when true, exceptions will allow the reply through.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    AI_REPLY_JUDGE_ACTIVE_WINDOW_SECONDS: int = Field(
        default=1800,
        ge=0,
        title="群聊 judge 激活窗口秒数",
        description="群聊出现一次主动唤起（@、关键词、随机或系统触发）后，后续多长时间内才允许调用 judge LLM；设为 0 表示恢复旧行为、始终允许 judge。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="群聊 judge 激活窗口秒数",
            en_US="Group Chat Judge Active Window (seconds)",
        ),
        i18n_description=i18n_text(
            zh_CN="群聊出现一次主动唤起（@、关键词、随机或系统触发）后，后续多长时间内才允许调用 judge LLM；设为 0 表示恢复旧行为、始终允许 judge。",
            en_US="After an active invocation in group chat, how long before judge LLM can be called again; 0 restores old behavior (always allow).",
        ),
    ).model_dump(),
    )
    AI_REPLY_MULTIMODAL_REGEX_ENABLED: bool = Field(
        default=True,
        title="启用多模态正则切组",
        description="仅对高级用户 context 生效；命中正则时切换到多模态 LLM。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="仅对高级用户 context 生效；命中正则时切换到多模态 LLM。",
                en_US="Only affects advanced user context; switches to multimodal LLM when regex matches.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    AI_REPLY_MULTIMODAL_TRIGGER_PATTERNS: List[str] = Field(
        default_factory=list,
        title="多模态切组正则列表",
        description="高级用户多模态切组使用的正则列表，按配置顺序匹配，任一命中即切组。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="多模态切组正则列表",
            en_US="Multimodal Switch Regex List",
        ),
        i18n_description=i18n_text(
            zh_CN="高级用户多模态切组使用的正则列表，按配置顺序匹配，任一命中即切组。",
            en_US="Regex list for advanced user multimodal group switching; matches in order, first hit switches group.",
        ),
    ).model_dump(),
    )
    AI_REPLY_MULTIMODAL_REGEX_MAX_USER_MESSAGES: int = Field(
        default=8,
        ge=1,
        title="多模态正则扫描消息数",
        description="高级用户多模态正则扫描的最近纯文本用户消息条数。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="多模态正则扫描消息数",
            en_US="Multimodal Regex Scan Message Count",
        ),
        i18n_description=i18n_text(
            zh_CN="高级用户多模态正则扫描的最近纯文本用户消息条数。",
            en_US="Number of recent plain text user messages scanned by advanced user multimodal regex.",
        ),
    ).model_dump(),
    )
    AI_REPLY_MULTIMODAL_MEDIA_MAX_SECONDS: int = Field(
        default=60,
        ge=1,
        title="多模态媒体最大秒数",
        description="Gemini 路径下音频转码与视频抽音轨时允许保留的最长秒数。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="多模态媒体最大秒数",
            en_US="Multimodal Media Max Seconds",
        ),
        i18n_description=i18n_text(
            zh_CN="Gemini 路径下音频转码与视频抽音轨时允许保留的最长秒数。",
            en_US="Maximum seconds allowed for audio transcoding and video audio track extraction in Gemini path.",
        ),
    ).model_dump(),
    )
    AI_REPLY_MULTIMODAL_AUDIO_MAX_COUNT: int = Field(
        default=4,
        ge=1,
        title="多模态音频上限",
        description="Gemini 路径下最多保留多少个最近音频 part；超限按时间顺序砍最老的。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="多模态音频上限",
            en_US="Multimodal Audio Max Count",
        ),
        i18n_description=i18n_text(
            zh_CN="Gemini 路径下最多保留多少个最近音频 part；超限按时间顺序砍最老的。",
            en_US="Maximum recent audio parts to retain in Gemini path; excess removed oldest first.",
        ),
    ).model_dump(),
    )
    MEMORY_MANAGE_MODEL: str = Field(
        default="",
        title="记忆管理模型",
        description="用于将传入记忆做整理与仲裁的对话 LLM。",
        json_schema_extra=ExtraField(
            ref_model_groups=True,
            model_type="chat",
            i18n_title=i18n_text(
                zh_CN="记忆管理模型",
                en_US="Memory Management Model",
            ),
            i18n_description=i18n_text(
                zh_CN="用于将传入记忆做整理与仲裁的对话 LLM。",
                en_US="Dialogue LLM used for organizing and arbitrating incoming memories.",
            ),
        ).model_dump(),
    )
    MEMORY_ARBITER_SYSTEM_PROMPT: str = Field(
        default=DEFAULT_MEMORY_ARBITER_SYSTEM_PROMPT_TEMPLATE,
        title="记忆仲裁系统提示词",
        description="记忆整理与冲突仲裁使用的 system prompt 模板。支持 {owner_context} / {chat_context} / {metadata_json} 占位符。",
        json_schema_extra=ExtraField(
            is_textarea=True,
            is_hidden=True,
            i18n_title=i18n_text(
                zh_CN="记忆仲裁系统提示词",
                en_US="Memory Arbiter System Prompt",
            ),
            i18n_description=i18n_text(
                zh_CN="记忆整理与冲突仲裁使用的 system prompt 模板。支持 {owner_context} / {chat_context} / {metadata_json} 占位符。",
                en_US="System prompt template for memory organization and conflict arbitration. Supports {owner_context} / {chat_context} / {metadata_json} placeholders.",
            ),
        ).model_dump(),
    )
    TEXT_EMBEDDING_MODEL: str = Field(
        default="",
        title="记忆向量嵌入模型",
        description="用于记忆嵌入与检索的 embedding LLM。",
        json_schema_extra=ExtraField(
            ref_model_groups=True,
            model_type="embedding",
            i18n_title=i18n_text(
                zh_CN="记忆向量嵌入模型",
                en_US="Memory Vector Embedding Model",
            ),
            i18n_description=i18n_text(
                zh_CN="用于记忆嵌入与检索的 embedding LLM。",
                en_US="Embedding LLM used for memory embedding and retrieval.",
            ),
        ).model_dump(),
    )
    TEXT_EMBEDDING_DIMENSION: int = Field(
        default=1024,
        title="记忆嵌入维度",
        description="记忆向量嵌入维度。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="记忆嵌入维度",
            en_US="Memory Embedding Dimension",
        ),
        i18n_description=i18n_text(
            zh_CN="记忆向量嵌入维度。",
            en_US="Memory vector embedding dimension.",
        ),
    ).model_dump(),
    )
    MEMORY_SEARCH_SCORE_THRESHOLD: float = Field(
        default=0.0,
        title="记忆匹配阈值",
        description="记忆检索时低于该值的结果会被过滤。0 表示保持宽松。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="记忆检索时低于该值的结果会被过滤。0 表示保持宽松。",
                en_US="Results below this score during memory retrieval are filtered. 0 means keep loose.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    SUBCONSCIOUS_ENABLE: bool = Field(
        default=True,
        title="启用潜意识记忆路由",
        description="启用后会加载 Stage0 图谱缓存并执行 Stage1 路由。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="启用潜意识记忆路由",
            en_US="Enable Subconscious Memory Routing",
        ),
        i18n_description=i18n_text(
            zh_CN="启用后会加载 Stage0 图谱缓存并执行 Stage1 路由。",
            en_US="When enabled, loads Stage0 graph cache and executes Stage1 routing.",
        ),
    ).model_dump(),
    )
    SUBCONSCIOUS_MODEL: str = Field(
        default="grok",
        title="潜意识LLM",
        description="用于 Stage1 潜意识路由与意图生成的 LLM。",
        json_schema_extra=ExtraField(
            ref_model_groups=True,
            model_type="chat",
            i18n_title=i18n_text(
                zh_CN="潜意识LLM",
                en_US="Subconscious LLM",
            ),
            i18n_description=i18n_text(
                zh_CN="用于 Stage1 潜意识路由与意图生成的 LLM。",
                en_US="LLM used for Stage1 subconscious routing and intent generation.",
            ),
        ).model_dump(),
    )
    SUBCONSCIOUS_TIMEOUT_SECONDS: float = Field(
        default=15.0,
        title="潜意识超时秒数",
        description="潜意识模型调用超时阈值。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="潜意识超时秒数",
            en_US="Subconscious Timeout (seconds)",
        ),
        i18n_description=i18n_text(
            zh_CN="潜意识模型调用超时阈值。",
            en_US="Subconscious model call timeout threshold.",
        ),
    ).model_dump(),
    )
    SUBCONSCIOUS_MAX_TOKENS: int = Field(
        default=512,
        title="潜意识最大输出 Token",
        description="潜意识模型最大输出 token。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="潜意识模型最大输出 token。",
                en_US="Max output tokens for subconscious model.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    SUBCONSCIOUS_CACHE_SIZE: int = Field(
        default=15,
        title="潜意识缓存大小",
        description="Stage0 图谱缓存容量上限。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="潜意识缓存大小",
            en_US="Subconscious Cache Size",
        ),
        i18n_description=i18n_text(
            zh_CN="Stage0 图谱缓存容量上限。",
            en_US="Stage0 graph cache capacity limit.",
        ),
    ).model_dump(),
    )
    PROMPT_INJECT_MAX_ITEMS_PER_USER: int = Field(
        default=16,
        title="记忆注入每用户最大条数",
        description="最终注入主模型前，每个用户最多保留多少条记忆。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="记忆注入每用户最大条数",
            en_US="Max Memory Injection Items per User",
        ),
        i18n_description=i18n_text(
            zh_CN="最终注入主模型前，每个用户最多保留多少条记忆。",
            en_US="Maximum memories per user before injecting into main model.",
        ),
    ).model_dump(),
    )
    PROMPT_INJECT_RECENT_FUTURE_GRACE_MINUTES: int = Field(
        default=10,
        title="记忆近期未来容忍分钟",
        description="识别近期记忆时允许的时间前瞻容忍窗口。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="识别近期记忆时允许的时间前瞻容忍窗口。",
                en_US="Time lookahead tolerance window when identifying recent memories.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    PROMPT_INJECT_RECENT_MAX_HOURS: float = Field(
        default=4.0,
        title="记忆近期时间窗小时",
        description="识别近期记忆的时间窗大小。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="识别近期记忆的时间窗大小。",
                en_US="Time window size for identifying recent memories.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    PROMPT_INJECT_STAGE2_UNSET_THRESHOLD_LT: float = Field(
        default=0.1,
        title="Stage2 未设置阈值下限",
        description="低于该值视为未设置检索阈值，改用 Stage2 默认兜底阈值。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="低于该值视为未设置检索阈值，改用 Stage2 默认兜底阈值。",
                en_US="Below this value is considered unset; use Stage2 default fallback threshold.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    PROMPT_INJECT_STAGE2_DEFAULT_THRESHOLD_FALLBACK: float = Field(
        default=0.5,
        title="Stage2 默认阈值",
        description="Stage2 的默认相关度阈值。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="Stage2 的默认相关度阈值。",
                en_US="Stage2 default relevance threshold.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    PROMPT_INJECT_STAGE2_RECENT_THRESHOLD: float = Field(
        default=0.4,
        title="Stage2 近期阈值",
        description="Stage2 对近期记忆的相关度阈值。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="Stage2 对近期记忆的相关度阈值。",
                en_US="Stage2 relevance threshold for recent memories.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    PROMPT_INJECT_STAGE2_STATIC_SCORE_THRESHOLD: float = Field(
        default=0.45,
        title="Stage2 静态画像阈值",
        description="Stage2 静态画像检索过滤阈值。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="Stage2 静态画像检索过滤阈值。",
                en_US="Stage2 static portrait retrieval filter threshold.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    PROMPT_INJECT_STAGE2_SEARCH_LIMIT_STATIC: int = Field(
        default=42,
        title="Stage2 静态画像检索上限",
        description="Stage2 静态画像 mem0.search limit。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="Stage2 静态画像 mem0.search limit。",
                en_US="Stage2 static portrait mem0.search limit.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    PROMPT_INJECT_STAGE2_SEARCH_LIMIT_CONTEXT: int = Field(
        default=128,
        title="Stage2 上下文检索上限",
        description="Stage2 主用户上下文动态检索上限。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="Stage2 主用户上下文动态检索上限。",
                en_US="Stage2 main user context dynamic retrieval limit.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    PROMPT_INJECT_STAGE2_SEARCH_LIMIT_INTENT: int = Field(
        default=64,
        title="Stage2 意图检索上限",
        description="Stage2 每条 intent 的检索上限。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="Stage2 每条 intent 的检索上限。",
                en_US="Stage2 per-intent retrieval limit.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    PROMPT_INJECT_STAGE2_MAX_STATIC_ITEMS: int = Field(
        default=36,
        title="Stage2 最大静态条目数",
        description="Stage2 最多保留多少条静态画像结果。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="Stage2 最多保留多少条静态画像结果。",
                en_US="Stage2 max static portrait results to keep.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    PROMPT_INJECT_STAGE2_MAX_CONTEXT_ITEMS: int = Field(
        default=36,
        title="Stage2 最大上下文条目数",
        description="Stage2 最多保留多少条主用户动态上下文结果。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="Stage2 最多保留多少条主用户动态上下文结果。",
                en_US="Stage2 max main user dynamic context results to keep.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    PROMPT_INJECT_STAGE2_MAX_INTENT_ITEMS: int = Field(
        default=20,
        title="Stage2 每意图最大条目数",
        description="Stage2 每条意图最多保留多少条结果。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="Stage2 每条意图最多保留多少条结果。",
                en_US="Stage2 max results per intent.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    PROMPT_INJECT_STAGE2_MAX_INTENTS: int = Field(
        default=16,
        title="Stage2 最大意图数",
        description="Stage2 最多处理多少条意图。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="Stage2 最多处理多少条意图。",
                en_US="Stage2 max intents to process.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    PROMPT_INJECT_STAGE2_CONCURRENT_SEARCH: int = Field(
        default=12,
        title="Stage2 并发检索数",
        description="Stage2 并发 mem0.search/get_all 的最大并发数。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="Stage2 并发 mem0.search/get_all 的最大并发数。",
                en_US="Stage2 max concurrent mem0.search/get_all requests.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    PROMPT_INJECT_STAGE2_THIRD_PARTY_RECENT: int = Field(
        default=6,
        title="Stage2 第三方兜底最近条数",
        description="第三方近况兜底时追加注入的最近记忆条数。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="第三方近况兜底时追加注入的最近记忆条数。",
                en_US="Number of recent memories appended during third-party status fallback.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    PROMPT_INJECT_STAGE2_THIRD_PARTY_TOTAL: int = Field(
        default=16,
        title="Stage2 第三方兜底总条数",
        description="第三方近况兜底后的总条数上限。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="第三方近况兜底后的总条数上限。",
                en_US="Total cap after third-party status fallback.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    # 注意：以下 legacy 阈值仍被 memory recall 的降级链路实际使用，当前只做注释保留，不参与本轮删除。
    PROMPT_INJECT_LEGACY_STATIC_SCORE_THRESHOLD: float = Field(
        default=0.47,
        title="Legacy 静态画像阈值",
        description="旧注入逻辑静态画像检索过滤阈值。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="旧注入逻辑静态画像检索过滤阈值。",
                en_US="Legacy injection logic static portrait retrieval filter threshold.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    PROMPT_INJECT_LEGACY_DEFAULT_THRESHOLD_FLOOR: float = Field(
        default=0.57,
        title="Legacy 默认阈值下限",
        description="旧注入逻辑动态检索默认阈值下限。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="旧注入逻辑动态检索默认阈值下限。",
                en_US="Legacy injection logic dynamic retrieval default threshold lower bound.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    PROMPT_INJECT_LEGACY_RECENT_THRESHOLD: float = Field(
        default=0.5,
        title="Legacy 近期阈值",
        description="旧注入逻辑对近期记忆的动态检索阈值。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="旧注入逻辑对近期记忆的动态检索阈值。",
                en_US="Legacy injection logic dynamic retrieval threshold for recent memories.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    AUTO_MEMORY_ENABLED: bool = Field(
        default=True,
        title="启用系统自动记忆",
        description="开启后，每个上下文窗口累计到阈值消息数时，会用独立辅助 LLM 自动调用 add_memory。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="启用系统自动记忆",
            en_US="Enable Auto Memory",
        ),
        i18n_description=i18n_text(
            zh_CN="开启后，每个上下文窗口累计到阈值消息数时，会用独立辅助 LLM 自动调用 add_memory。",
            en_US="When enabled, an auxiliary LLM automatically calls add_memory when each context window accumulates to the threshold message count.",
        ),
    ).model_dump(),
    )
    AUTO_MEMORY_MODEL_GROUP: str = Field(
        default="",
        title="自动记忆LLM",
        description="系统自动记忆链专用的 chat.completions LLM。",
        json_schema_extra=ExtraField(
            ref_model_groups=True,
            model_type="chat",
            i18n_title=i18n_text(
                zh_CN="自动记忆LLM",
                en_US="Auto Memory LLM",
            ),
            i18n_description=i18n_text(
                zh_CN="系统自动记忆链专用的 chat.completions LLM。",
                en_US="The chat.completions LLM dedicated to the system auto-memory chain.",
            ),
        ).model_dump(),
    )
    AUTO_MEMORY_SYSTEM_PROMPT: str = Field(
        default=DEFAULT_AUTO_MEMORY_SYSTEM_PROMPT,
        title="自动记忆系统提示词",
        description="自动记忆后台写入使用的 system prompt。",
        json_schema_extra=ExtraField(
            is_textarea=True,
            is_hidden=True,
            i18n_title=i18n_text(
                zh_CN="自动记忆系统提示词",
                en_US="Auto Memory System Prompt",
            ),
            i18n_description=i18n_text(
                zh_CN="自动记忆后台写入使用的 system prompt。",
                en_US="System prompt used for auto memory background writes.",
            ),
        ).model_dump(),
    )
    AUTO_MEMORY_TRIGGER_MESSAGE_COUNT: int = Field(
        default=10,
        title="自动记忆触发消息数",
        description="每个上下文窗口累计多少条新聊天消息后触发一次自动记忆。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="自动记忆触发消息数",
            en_US="Auto Memory Trigger Message Count",
        ),
        i18n_description=i18n_text(
            zh_CN="每个上下文窗口累计多少条新聊天消息后触发一次自动记忆。",
            en_US="How many new chat messages each context window must accumulate before triggering an auto-memory call.",
        ),
    ).model_dump(),
    )
    AUTO_MEMORY_RECENT_MESSAGE_COUNT: int = Field(
        default=10,
        title="自动记忆取样消息数",
        description="自动记忆辅助 LLM 每次查看最近多少条上下文聊天消息。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="自动记忆取样消息数",
            en_US="Auto Memory Recent Message Count",
        ),
        i18n_description=i18n_text(
            zh_CN="自动记忆辅助 LLM 每次查看最近多少条上下文聊天消息。",
            en_US="How many recent context chat messages the auto-memory auxiliary LLM reviews each time.",
        ),
    ).model_dump(),
    )
    AUTO_MEMORY_MAX_TOOL_CALLS: int = Field(
        default=8,
        title="自动记忆最大写入条数",
        description="单次自动记忆调用最多执行多少个 add_memory tool call。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="自动记忆最大写入条数",
            en_US="Auto Memory Max Tool Calls",
        ),
        i18n_description=i18n_text(
            zh_CN="单次自动记忆调用最多执行多少个 add_memory tool call。",
            en_US="Maximum number of add_memory tool calls executed per single auto-memory invocation.",
        ),
    ).model_dump(),
    )
    AUTO_MEMORY_TOOL_CHOICE: str = Field(
        default="auto",
        title="自动记忆 tool_choice",
        description="自动记忆 chat.completions 的 tool_choice 原样透传值，默认 auto；禁止默认使用 required。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="自动记忆 tool_choice",
            en_US="Auto Memory Tool Choice",
        ),
        i18n_description=i18n_text(
            zh_CN="自动记忆 chat.completions 的 tool_choice 原样透传值，默认 auto；禁止默认使用 required。",
            en_US="Raw passthrough value for auto-memory chat.completions tool_choice; defaults to auto. Do not default to required.",
        ),
    ).model_dump(),
    )
    AUTO_MEMORY_DEBUG_LOG_PAYLOAD: bool = Field(
        default=True,
        title="记录自动记忆 Payload",
        description="开启后打印自动记忆辅助 LLM 的请求预览与返回工具调用预览。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="记录自动记忆 Payload",
            en_US="Log Auto Memory Payload",
        ),
        i18n_description=i18n_text(
            zh_CN="开启后打印自动记忆辅助 LLM 的请求预览与返回工具调用预览。",
            en_US="When enabled, prints the auto-memory auxiliary LLM request preview and returned tool call preview.",
        ),
    ).model_dump(),
    )
    AUTO_MEMORY_PAYLOAD_LOG_MAX_CHARS: int = Field(
        default=12000,
        title="自动记忆 Payload 日志截断长度",
        description="自动记忆 payload 调试日志的最大字符数。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="自动记忆 payload 调试日志的最大字符数。",
                en_US="Max characters for auto-memory payload debug logs.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    SELF_IMAGE_ENABLE: bool = Field(
        default=True,
        title="启用系统自设图",
        description="控制 system 层自设图能力是否启用。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="启用系统自设图",
            en_US="Enable System Self Image",
        ),
        i18n_description=i18n_text(
            zh_CN="控制 system 层自设图能力是否启用。",
            en_US="Controls whether the system-level self-image capability is enabled.",
        ),
    ).model_dump(),
    )
    SELF_IMAGE_ENABLE_AUTO_IMPRESSION_INJECT: bool = Field(
        default=True,
        title="自动注入印象图",
        description="启用后在 system 层注入固定印象图作为形象锚点。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="自动注入印象图",
            en_US="Auto Inject Impression Image",
        ),
        i18n_description=i18n_text(
            zh_CN="启用后在 system 层注入固定印象图作为形象锚点。",
            en_US="When enabled, injects a fixed impression image at the system layer as an identity anchor.",
        ),
    ).model_dump(),
    )
    SELF_IMAGE_ENABLE_DIRECT_PATH_PROMPT: bool = Field(
        default=True,
        title="显示自设图直传路径",
        description="启用后在 system 层提供 3 张参考图的可直传路径。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="显示自设图直传路径",
            en_US="Show Self Image Direct Upload Path",
        ),
        i18n_description=i18n_text(
            zh_CN="启用后在 system 层提供 3 张参考图的可直传路径。",
            en_US="When enabled, provides directly transmittable paths for 3 reference images at the system layer.",
        ),
    ).model_dump(),
    )
    SELF_IMAGE_IMPRESSION_IMAGE_PATH: str = Field(
        default="__SYSTEM_SELF_IMAGE__/内置印象图.webp",
        title="印象图路径",
        description="系统自设图路径。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="印象图路径",
            en_US="Impression Image Path",
        ),
        i18n_description=i18n_text(
            zh_CN="系统自设图路径。",
            en_US="System self-image path.",
        ),
    ).model_dump(),
    )
    SELF_IMAGE_BOT_PERSONA_IMAGE_PATH: str = Field(
        default="__SYSTEM_SELF_IMAGE__/HCZ.webp",
        title="bot 自设图路径",
        description="系统自设图路径。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="bot 自设图路径",
            en_US="Bot Persona Image Path",
        ),
        i18n_description=i18n_text(
            zh_CN="Bot 人设自设图路径。",
            en_US="Bot persona self-image path.",
        ),
    ).model_dump(),
    )
    SELF_IMAGE_USER_DAILY_IMAGE_PATH: str = Field(
        default="__SYSTEM_SELF_IMAGE__/user_daily.webp",
        title="你的日常照路径",
        description="用户日常照路径。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="你的日常照路径",
            en_US="Your Daily Photo Path",
        ),
        i18n_description=i18n_text(
            zh_CN="用户日常照路径。",
            en_US="User daily photo path.",
        ),
    ).model_dump(),
    )
    SELF_IMAGE_USER_PORTRAIT_IMAGE_PATH: str = Field(
        default="__SYSTEM_SELF_IMAGE__/user_portrait.webp",
        title="你的写真照路径",
        description="用户写真照路径。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="你的写真照路径",
            en_US="Your Portrait Photo Path",
        ),
        i18n_description=i18n_text(
            zh_CN="用户写真照路径。",
            en_US="User portrait photo path.",
        ),
    ).model_dump(),
    )
    SYSTEM_MOMENT_ENABLE_VOW_PATROL: bool = Field(
        default=True,
        title="启用系统 moment 持久提醒巡检",
        description="启用后后台会巡检持久化 echo 定时，并在重启后自动尝试补回缺失定时器。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="启用后后台会巡检持久化 echo 定时，并在重启后自动尝试补回缺失定时器。",
                en_US="When enabled, background patrols persistent echo reminders and auto-recovers missing timers after restart.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    SYSTEM_MOMENT_VOW_PATROL_INTERVAL_SECONDS: int = Field(
        default=60,
        title="系统 moment 持久提醒巡检间隔（秒）",
        description="系统 moment 持久提醒后台巡检的时间间隔。",
        json_schema_extra=ExtraField(
            i18n_description=i18n_text(
                zh_CN="系统 moment 持久提醒后台巡检的时间间隔。",
                en_US="System moment persistent reminder background patrol interval.",
            ),
            is_hidden=True,
        ).model_dump(),
    )
    ADVANCED_AUTO_ECHO_ENABLED: bool = Field(
        default=False,
        title='启用高级用户自动 echo 回复',
        description='启用后仅对高级用户 context_id 自动创建 echo 定时触发回复；从关闭改为开启后需要重启应用。',
        json_schema_extra=ExtraField(
            is_need_restart=True,
            i18n_title=i18n_text(
                zh_CN='启用高级用户自动 echo 回复',
                en_US='Enable Advanced Auto Echo Replies',
            ),
            i18n_description=i18n_text(
                zh_CN='启用后仅对高级用户 context_id 自动创建 echo 定时触发回复；从关闭改为开启后需要重启应用。',
                en_US='Automatically schedules echo wakeups only for the advanced context. Restart the app after enabling it from off.',
            ),
        ).model_dump(),
    )
    ADVANCED_AUTO_ECHO_START_TIME: str = Field(
        default='06:00',
        title='高级用户自动 echo 每日开始时间',
        description='HH:MM，本地时间。',
        json_schema_extra=ExtraField(
            i18n_title=i18n_text(
                zh_CN='高级用户自动 echo 每日开始时间',
                en_US='Advanced Auto Echo Daily Start Time',
            ),
            i18n_description=i18n_text(
                zh_CN='HH:MM，本地时间。',
                en_US='HH:MM in local time.',
            ),
        ).model_dump(),
    )
    ADVANCED_AUTO_ECHO_END_TIME: str = Field(
        default='23:00',
        title='高级用户自动 echo 每日截止时间',
        description='HH:MM，本地时间。',
        json_schema_extra=ExtraField(
            i18n_title=i18n_text(
                zh_CN='高级用户自动 echo 每日截止时间',
                en_US='Advanced Auto Echo Daily End Time',
            ),
            i18n_description=i18n_text(
                zh_CN='HH:MM，本地时间。',
                en_US='HH:MM in local time.',
            ),
        ).model_dump(),
    )
    ADVANCED_AUTO_ECHO_MIN_INTERVAL_SECONDS: int = Field(
        default=3600,
        title='高级用户自动 echo 最小间隔秒数',
        description='后续自动 echo 距离高级用户最近发言的最小等待秒数。',
        json_schema_extra=ExtraField(
            i18n_title=i18n_text(
                zh_CN='高级用户自动 echo 最小间隔秒数',
                en_US='Advanced Auto Echo Minimum Interval Seconds',
            ),
            i18n_description=i18n_text(
                zh_CN='后续自动 echo 距离高级用户最近发言的最小等待秒数。',
                en_US='Minimum delay between the latest advanced-user message and the next automatic echo.',
            ),
        ).model_dump(),
    )
    ADVANCED_AUTO_ECHO_SAMPLE_WINDOW_SECONDS: int = Field(
        default=14400,
        title='高级用户自动 echo 随机采样窗口秒数',
        description='自动 echo 触发点随机采样窗口长度。',
        json_schema_extra=ExtraField(
            i18n_title=i18n_text(
                zh_CN='高级用户自动 echo 随机采样窗口秒数',
                en_US='Advanced Auto Echo Random Sample Window Seconds',
            ),
            i18n_description=i18n_text(
                zh_CN='自动 echo 触发点随机采样窗口长度。',
                en_US='Random sampling window length for automatic echo trigger time.',
            ),
        ).model_dump(),
    )
    ADVANCED_AUTO_ECHO_PATROL_INTERVAL_SECONDS: int = Field(
        default=60,
        title='高级用户自动 echo 巡检间隔秒数',
        description='后台检查是否需要创建下一次自动 echo 的间隔。',
        json_schema_extra=ExtraField(
            i18n_title=i18n_text(
                zh_CN='高级用户自动 echo 巡检间隔秒数',
                en_US='Advanced Auto Echo Patrol Interval Seconds',
            ),
            i18n_description=i18n_text(
                zh_CN='后台检查是否需要创建下一次自动 echo 的间隔。',
                en_US='Background interval for checking whether the next automatic echo should be scheduled.',
            ),
        ).model_dump(),
    )
    SYSTEM_VOICE_ENABLED: bool = Field(
        default=True,
        title="启用系统语音后处理",
        description="启用后，最终纯文本短回复会按概率自动改为发送语音。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="启用系统语音后处理",
            en_US="Enable System Voice Post-processing",
        ),
        i18n_description=i18n_text(
            zh_CN="启用后，最终纯文本短回复会按概率自动改为发送语音。",
            en_US="When enabled, short plain-text replies will be automatically converted to voice messages based on probability.",
        ),
    ).model_dump(),
    )
    SYSTEM_EMOJI_ENABLED: bool = Field(
        default=True,
        title="启用系统表情后处理",
        description="启用后，最终纯文本回复会按概率自动附带宿主机表情资源。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="启用系统表情后处理",
            en_US="Enable System Emoji Post-processing",
        ),
        i18n_description=i18n_text(
            zh_CN="启用后，最终纯文本回复会按概率自动附带宿主机表情资源。",
            en_US="When enabled, plain-text replies will automatically include host emoji resources based on probability.",
        ),
    ).model_dump(),
    )
    SYSTEM_EMOJI_TRIGGER_PROBABILITY: float = Field(
        default=0.02,
        title="系统表情触发概率",
        description="纯文本回复命中系统表情后处理的概率。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="系统表情触发概率",
            en_US="System Emoji Trigger Probability",
        ),
        i18n_description=i18n_text(
            zh_CN="纯文本回复命中系统表情后处理的概率。",
            en_US="Probability that a plain-text reply triggers system emoji post-processing.",
        ),
    ).model_dump(),
    )
    SYSTEM_EMOJI_EMBEDDING_MODEL_GROUP: str = Field(
        default="",
        title="系统表情嵌入模型",
        description="用于表情标签语义匹配的 embedding 模型。",
        json_schema_extra=ExtraField(
            ref_model_groups=True,
            model_type="embedding",
            i18n_title=i18n_text(
                zh_CN="系统表情嵌入模型",
                en_US="System Emoji Embedding Model",
            ),
            i18n_description=i18n_text(
                zh_CN="用于表情标签语义匹配的 embedding 模型。",
                en_US="Embedding model used for semantic matching of emoji labels.",
            ),
        ).model_dump(),
    )
    SYSTEM_EMOJI_HOST_DIR: str = Field(
        default=str(_CURRENT_RUNTIME_EMOJI_DIR),
        title="系统表情宿主机目录",
        description="系统表情目录。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="系统表情宿主机目录",
            en_US="System Emoji Host Directory",
        ),
        i18n_description=i18n_text(
            zh_CN="系统表情目录。",
            en_US="System emoji directory.",
        ),
    ).model_dump(),
    )
    SYSTEM_VOICE_SHORT_TEXT_MAX_LEN: int = Field(
        default=30,
        title="系统语音文本长度阈值",
        description="仅当最终纯文本回复长度小于该值时，才会参与系统语音判定。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="系统语音文本长度阈值",
            en_US="System Voice Short Text Max Length",
        ),
        i18n_description=i18n_text(
            zh_CN="仅当最终纯文本回复长度小于该值时，才会参与系统语音判定。",
            en_US="Only plain-text replies shorter than this value will participate in system voice evaluation.",
        ),
    ).model_dump(),
    )
    SYSTEM_VOICE_TRIGGER_PROBABILITY: float = Field(
        default=0.2,
        title="系统语音触发概率",
        description="短文本命中系统语音后处理的概率。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="系统语音触发概率",
            en_US="System Voice Trigger Probability",
        ),
        i18n_description=i18n_text(
            zh_CN="短文本命中系统语音后处理的概率。",
            en_US="Probability that short text triggers system voice post-processing.",
        ),
    ).model_dump(),
    )
    SYSTEM_VOICE_ALLOWED_ADAPTERS: List[str] = Field(
        default=["onebot_v11", "telegram"],
        title="系统语音允许适配器",
        description="仅这些适配器上的最终回复会参与系统语音后处理。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="系统语音允许适配器",
            en_US="System Voice Allowed Adapters",
        ),
        i18n_description=i18n_text(
            zh_CN="仅这些适配器上的最终回复会参与系统语音后处理。",
            en_US="Only final replies on these adapters will participate in system voice post-processing.",
        ),
    ).model_dump(),
    )
    SYSTEM_VOICE_EMBEDDING_MODEL_GROUP: str = Field(
        default="",
        title="系统语音嵌入模型",
        description="用于 guidance 匹配的 embedding 模型。",
        json_schema_extra=ExtraField(
            ref_model_groups=True,
            model_type="embedding",
            i18n_title=i18n_text(
                zh_CN="系统语音嵌入模型",
                en_US="System Voice Embedding Model",
            ),
            i18n_description=i18n_text(
                zh_CN="用于 guidance 匹配的 embedding 模型。",
                en_US="Embedding model used for guidance matching.",
            ),
        ).model_dump(),
    )
    SYSTEM_VOICE_API_KEY: str = Field(
        default="",
        title="系统语音 API Key",
        description="DashScope CosyVoice 所需的 API Key。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="系统语音 API Key",
            en_US="System Voice API Key",
        ),
        i18n_description=i18n_text(
            zh_CN="DashScope CosyVoice 所需的 API Key。",
            en_US="API Key required for DashScope CosyVoice.",
        ),
    ).model_dump(),
    )
    SYSTEM_VOICE_MODEL: str = Field(
        default="cosyvoice-v3-flash",
        title="系统语音模型",
        description="系统级 TTS 使用的 CosyVoice 模型。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="系统语音模型",
            en_US="System Voice Model",
        ),
        i18n_description=i18n_text(
            zh_CN="系统级 TTS 使用的 CosyVoice 模型。",
            en_US="The CosyVoice model used for system-level TTS.",
        ),
    ).model_dump(),
    )
    SYSTEM_VOICE_DEFAULT_VOICE_ID: str = Field(
        default="",
        title="系统语音默认音色",
        description="系统级 TTS 默认音色 ID。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="系统语音默认音色",
            en_US="System Voice Default Voice ID",
        ),
        i18n_description=i18n_text(
            zh_CN="系统级 TTS 默认音色 ID。",
            en_US="Default voice ID for system-level TTS.",
        ),
    ).model_dump(),
    )
    SYSTEM_VOICE_WS_URL: str = Field(
        default="wss://dashscope.aliyuncs.com/api-ws/v1/inference",
        title="系统语音 WebSocket 地址",
        description="CosyVoice WebSocket 接口地址。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="系统语音 WebSocket 地址",
            en_US="System Voice WebSocket URL",
        ),
        i18n_description=i18n_text(
            zh_CN="CosyVoice WebSocket 接口地址。",
            en_US="CosyVoice WebSocket interface address.",
        ),
    ).model_dump(),
    )
    SYSTEM_VOICE_TIMEOUT_MS: int = Field(
        default=120000,
        title="系统语音超时毫秒",
        description="等待 CosyVoice 合成完成的最大时长。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="系统语音超时毫秒",
            en_US="System Voice Timeout (ms)",
        ),
        i18n_description=i18n_text(
            zh_CN="等待 CosyVoice 合成完成的最大时长。",
            en_US="Maximum wait time for CosyVoice synthesis to complete.",
        ),
    ).model_dump(),
    )
    SYSTEM_VOICE_SAMPLE_RATE: int = Field(
        default=24000,
        title="系统语音采样率",
        description="当服务端返回裸 PCM 时，用于封装 WAV 的采样率。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="系统语音采样率",
            en_US="System Voice Sample Rate",
        ),
        i18n_description=i18n_text(
            zh_CN="当服务端返回裸 PCM 时，用于封装 WAV 的采样率。",
            en_US="Sample rate used to wrap raw PCM into WAV when the server returns bare PCM.",
        ),
    ).model_dump(),
    )
    SYSTEM_VOICE_LANGUAGE_HINTS: str = Field(
        default="zh",
        title="系统语音语言提示",
        description="逗号分隔的语言提示，例如 zh 或 zh,en。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="系统语音语言提示",
            en_US="System Voice Language Hints",
        ),
        i18n_description=i18n_text(
            zh_CN="逗号分隔的语言提示，例如 zh 或 zh,en。",
            en_US="Comma-separated language hints, e.g. zh or zh,en.",
        ),
    ).model_dump(),
    )
    SYSTEM_VOICE_SPEECH_RATE: float = Field(
        default=1.1,
        title="系统语音固定语速",
        description="系统级 TTS 全局固定语速倍率。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="系统语音固定语速",
            en_US="System Voice Speech Rate",
        ),
        i18n_description=i18n_text(
            zh_CN="系统级 TTS 全局固定语速倍率。",
            en_US="Global fixed speech-rate multiplier for system-level TTS.",
        ),
    ).model_dump(),
    )
    SYSTEM_VOICE_PITCH_RATE: float = Field(
        default=1.02,
        title="系统语音固定音调",
        description="系统级 TTS 全局固定音调倍率。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="系统语音固定音调",
            en_US="System Voice Pitch Rate",
        ),
        i18n_description=i18n_text(
            zh_CN="系统级 TTS 全局固定音调倍率。",
            en_US="Global fixed pitch multiplier for system-level TTS.",
        ),
    ).model_dump(),
    )
    SYSTEM_VOICE_INSTRUCTION_PREFIX: str = Field(
        default="",
        title="系统语音前置 instruction",
        description="会拼接在合法 instruction 前方，作为系统级语音风格底座。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="系统语音前置 instruction",
            en_US="System Voice Instruction Prefix",
        ),
        i18n_description=i18n_text(
            zh_CN="会拼接在合法 instruction 前方，作为系统级语音风格底座。",
            en_US="Prepended before valid instructions as the system-level voice style base.",
        ),
    ).model_dump(),
    )
    SYSTEM_VOICE_GUIDANCE_LIBRARY_JSON: str = Field(
        default="",
        title="系统语音 guidance 库 JSON",
        description="用于系统级语音 guidance 匹配的 JSON 配置。instruction 必须使用兼容固定句式。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="系统语音 guidance 库 JSON",
            en_US="System Voice Guidance Library JSON",
        ),
        i18n_description=i18n_text(
            zh_CN="用于系统级语音 guidance 匹配的 JSON 配置。instruction 必须使用兼容固定句式。",
            en_US="JSON configuration for system-level voice guidance matching. Instructions must use compatible fixed sentence patterns.",
        ),
    ).model_dump(),
    )
    SYSTEM_VOICE_MAX_BG_CONCURRENCY: int = Field(
        default=2,
        title="系统语音后台并发",
        description="系统级 TTS 同时允许的最大并发数。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="系统语音后台并发",
            en_US="System Voice Max Background Concurrency",
        ),
        i18n_description=i18n_text(
            zh_CN="系统级 TTS 同时允许的最大并发数。",
            en_US="Maximum concurrent system-level TTS synthesis allowed.",
        ),
    ).model_dump(),
    )
    ADVANCED_FILE_SYSTEM_ROOT: str = Field(
        default=str(_CURRENT_SHARED_ROOT),
        title="高级文件系统根目录",
        description="高级上下文专属文件系统根目录。仅允许接收的附件托管到这里。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="高级文件系统根目录",
            en_US="Advanced File System Root",
        ),
        i18n_description=i18n_text(
            zh_CN="高级上下文专属文件系统根目录。仅允许接收的附件托管到这里。",
            en_US="Root directory for advanced-context exclusive filesystem. Only received attachments are hosted here.",
        ),
    ).model_dump(),
    )
    NORMAL_USER_IMAGE_QUARANTINE_ENABLE: bool = Field(
        default=True,
        title="普通用户图片隔离接收",
        description="开启后，普通用户图片会进入上下文，并写入隔离区临时落盘；关闭后直接降级为文本说明。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="普通用户图片隔离接收",
            en_US="Normal User Image Quarantine",
        ),
        i18n_description=i18n_text(
            zh_CN="开启后，普通用户图片会进入上下文，并写入隔离区临时落盘；关闭后直接降级为文本说明。",
            en_US="When enabled, normal user images enter context and are written to an isolated temp directory; when disabled, they downgrade to text descriptions.",
        ),
    ).model_dump(),
    )
    REFERENCE_INCLUDE_MEDIA: bool = Field(
        default=True,
        title="引用消息保留媒体",
        description="开启后，引用消息中的图片会尽量进入上下文；若资源失效则自动降级为文本说明。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="引用消息保留媒体",
            en_US="Reference Include Media",
        ),
        i18n_description=i18n_text(
            zh_CN="开启后，引用消息中的图片会尽量进入上下文；若资源失效则自动降级为文本说明。",
            en_US="When enabled, images in referenced messages try to enter context; if the resource fails, they automatically downgrade to text descriptions.",
        ),
    ).model_dump(),
    )
    REFERENCE_TEXT_MAX_LEN: int = Field(
        default=120,
        title="引用摘要最大长度",
        description="引用消息正文摘要最大长度，超过后截断并追加省略号。",
        json_schema_extra=ExtraField(
        i18n_title=i18n_text(
            zh_CN="引用摘要最大长度",
            en_US="Reference Text Max Length",
        ),
        i18n_description=i18n_text(
            zh_CN="引用消息正文摘要最大长度，超过后截断并追加省略号。",
            en_US="Maximum length for referenced message body summaries; truncated with ellipsis if exceeded.",
        ),
    ).model_dump(),
    )
    AI_DEBOUNCE_WAIT_SECONDS: float = Field(
        default=0.9,
        title="防抖等待时长 (秒)",
        description="收到触发消息时延迟指定时长再开始回复流程，防抖等待时长中继续收到的消息只会触发最后一条",
        json_schema_extra=ExtraField(
            overridable=True,
            i18n_title=i18n_text(
                zh_CN="防抖等待时长 (秒)",
                en_US="Debounce Wait Time (seconds)",
            ),
            i18n_description=i18n_text(
                zh_CN="收到触发消息时延迟指定时长再开始回复流程，防抖等待时长中继续收到的消息只会触发最后一条",
                en_US="Delay before starting reply process, only last message received during debounce will trigger",
            ),
        ).model_dump(),
    )
    AI_CHAT_RANDOM_REPLY_PROBABILITY: float = Field(
        default=0.0,
        title="随机回复概率",
        json_schema_extra=ExtraField(
            overridable=True,
            i18n_title=i18n_text(
                zh_CN="随机回复概率",
                en_US="Random Reply Probability",
            ),
            i18n_description=i18n_text(
                zh_CN="随机回复概率，任意消息触发 AI 回复的概率，0.0 表示不启用，1.0 表示必定触发",
                en_US="Probability of AI replying to any message, 0.0 = disabled, 1.0 = always",
            ),
        ).model_dump(),
        description="随机回复概率，任意消息触发 AI 回复的概率，0.0 表示不启用，1.0 表示必定触发",
    )
    AI_CHAT_TRIGGER_REGEX: List[str] = Field(
        default=[],
        title="触发正则表达式",
        description="触发正则表达式，当消息匹配到正则表达式时，会触发 AI 回复",
        json_schema_extra=ExtraField(
            sub_item_name="表达式",
            i18n_title=i18n_text(
                zh_CN="触发正则表达式",
                en_US="Trigger Regex Patterns",
            ),
            i18n_description=i18n_text(
                zh_CN="当消息匹配到这些正则表达式时，会触发 AI 回复",
                en_US="AI will reply when message matches these regex patterns",
            ),
        ).model_dump(),
    )
    AI_CHAT_IGNORE_REGEX: List[str] = Field(
        default=[],
        title="忽略正则表达式",
        description="忽略正则表达式，当消息匹配到正则表达式时，不会触发 AI 回复",
        json_schema_extra=ExtraField(
            sub_item_name="表达式",
            i18n_title=i18n_text(
                zh_CN="忽略正则表达式",
                en_US="Ignore Regex Patterns",
            ),
            i18n_description=i18n_text(
                zh_CN="当消息匹配到这些正则表达式时，不会触发 AI 回复",
                en_US="AI will not reply when message matches these regex patterns",
            ),
        ).model_dump(),
    )
    """聊天设置"""
    SESSION_GROUP_ACTIVE_DEFAULT: bool = Field(
        default=False,
        title="新群聊默认启用聊天",
        description="仅控制普通新群聊默认激活状态；高级私聊始终默认启用。",
        json_schema_extra=ExtraField(
            i18n_title=i18n_text(
                zh_CN="新群聊默认启用聊天",
                en_US="Enable Chat for New Groups by Default",
            ),
        i18n_description=i18n_text(
            zh_CN="仅控制普通新群聊默认激活状态；高级私聊始终默认启用。",
            en_US="Controls default activation for new normal group chats only; advanced private chats are always enabled by default.",
        ),
        ).model_dump(),
    )
    SESSION_PRIVATE_ACTIVE_DEFAULT: bool = Field(
        default=False,
        title="新私聊默认启用聊天",
        description="仅控制普通新私聊默认激活状态；高级私聊始终默认启用。",
        json_schema_extra=ExtraField(
            i18n_title=i18n_text(
                zh_CN="新私聊默认启用聊天",
                en_US="Enable Chat for New Private Chats by Default",
            ),
        i18n_description=i18n_text(
            zh_CN="仅控制普通新私聊默认激活状态；高级私聊始终默认启用。",
            en_US="Controls default activation for new normal private chats only; advanced private chats are always enabled by default.",
        ),
        ).model_dump(),
    )
    """Postgresql 配置"""
    POSTGRES_HOST: str = Field(
        default="127.0.0.1",
        title="数据库主机",
        json_schema_extra=ExtraField(is_hidden=True).model_dump(),
    )
    POSTGRES_PORT: int = Field(
        default=5432,
        title="数据库端口",
        json_schema_extra=ExtraField(is_hidden=True).model_dump(),
    )
    POSTGRES_USER: str = Field(
        default="db_username",
        title="数据库用户名",
        json_schema_extra=ExtraField(is_hidden=True).model_dump(),
    )
    POSTGRES_PASSWORD: str = Field(
        default="db_password",
        title="数据库密码",
        json_schema_extra=ExtraField(is_hidden=True).model_dump(),
    )
    POSTGRES_DATABASE: str = Field(
        default="holo_cortex_zero",
        title="数据库名称",
        json_schema_extra=ExtraField(is_hidden=True).model_dump(),
    )

    """Qdrant 配置"""
    QDRANT_URL: str = Field(
        default="http://127.0.0.1:6333",
        title="Qdrant 地址",
        json_schema_extra=ExtraField(is_hidden=True).model_dump(),
    )
    QDRANT_API_KEY: str = Field(
        default="",
        title="Qdrant API Key",
        json_schema_extra=ExtraField(is_hidden=True).model_dump(),
    )


    """其他功能"""
    ENABLE_FESTIVAL_REMINDER: bool = Field(
        default=True,
        title="启用节日祝福提醒",
        description="启用后会在节日时自动向所有活跃聊天发送祝福",
        json_schema_extra=ExtraField(
            i18n_title=i18n_text(
                zh_CN="启用节日祝福提醒",
                en_US="Enable Festival Greeting Reminder",
            ),
            i18n_description=i18n_text(
                zh_CN="启用后会在节日时自动向所有活跃聊天发送祝福",
                en_US="Automatically send greetings to all active chats on festivals",
            ),
        ).model_dump(),
    )
    OPENAI_CLIENT_USER_AGENT: str = Field(
        default="holo-cortex-zero",
        title="OpenAI Client User Agent",
        description="OpenAI Client User Agent",
        json_schema_extra=ExtraField(is_hidden=True).model_dump(),
    )
    DEFAULT_PROXY: str = Field(
        default="",
        title="默认代理",
        json_schema_extra=ExtraField(
            placeholder="例: http://127.0.0.1:7890",
            i18n_title=i18n_text(
                zh_CN="默认代理",
                en_US="Default Proxy",
            ),
            i18n_description=i18n_text(
                zh_CN="默认代理服务器地址，用于网络请求",
                en_US="Default proxy server address for network requests",
            ),
        ).model_dump(),
    )

    def get_model_group_info(self, model_name: str) -> ModelConfigGroup:
        try:
            return self.MODEL_GROUPS[model_name]
        except KeyError as e:
            raise KeyError(f"LLM '{model_name}' 不存在，请确认配置正确") from e

    @classmethod
    def _migrate_legacy_prompt_fields(cls, payload: dict | None) -> dict:
        data = dict(payload or {})
        data["ADVANCED_USER_ID"] = normalize_advanced_user_id(data.get("ADVANCED_USER_ID"))
        legacy_name = str(data.pop("AI_CHAT_PRESET_NAME", "") or "").strip()
        legacy_prompt = str(data.pop("AI_CHAT_PRESET_SETTING", "") or "").strip()

        migrated_fields: list[str] = []
        if legacy_name and not str(data.get("BOT_PERSONA_DISPLAY_NAME", "") or "").strip():
            data["BOT_PERSONA_DISPLAY_NAME"] = legacy_name
            migrated_fields.append("BOT_PERSONA_DISPLAY_NAME")

        if legacy_prompt:
            if not str(data.get("MAIN_SYSTEM_PROMPT_NORMAL", "") or "").strip():
                data["MAIN_SYSTEM_PROMPT_NORMAL"] = legacy_prompt
                migrated_fields.append("MAIN_SYSTEM_PROMPT_NORMAL")
            if not str(data.get("MAIN_SYSTEM_PROMPT_ADVANCED", "") or "").strip():
                data["MAIN_SYSTEM_PROMPT_ADVANCED"] = legacy_prompt
                migrated_fields.append("MAIN_SYSTEM_PROMPT_ADVANCED")
            if not str(data.get("MAIN_SYSTEM_PROMPT_ADVANCED_DEEP", "") or "").strip():
                data["MAIN_SYSTEM_PROMPT_ADVANCED_DEEP"] = f"{legacy_prompt}\n\n{DEFAULT_MAIN_SYSTEM_PROMPT_DEEP_SUFFIX}"
                migrated_fields.append("MAIN_SYSTEM_PROMPT_ADVANCED_DEEP")

        if migrated_fields:
            print(
                "system config 检测到旧 AI_CHAT_PRESET_* 字段，已迁移到单人格 prompt 字段: "
                + ",".join(migrated_fields)
            )

        return data

    @classmethod
    def load_from_path(cls, path: Path):
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            instance = cls()
        else:
            content: str = path.read_text(encoding="utf-8")
            if path.suffix == ".json":
                raw_payload = json.loads(content)
            elif path.suffix in [".yaml", ".yml"]:
                raw_payload = yaml.safe_load(content) or {}
            else:
                raise ValueError(f"Unsupported file type: {path}")

            if not isinstance(raw_payload, dict):
                raw_payload = {}
            raw_payload = cls._migrate_legacy_prompt_fields(raw_payload)
            instance = cls.model_validate(raw_payload)

        instance.set_instance_config_file_path(path)
        return instance

    @classmethod
    def load_config(cls, file_path: Optional[Path] = None, auto_register: bool = True):
        """加载配置文件"""
        config = super().load_config(file_path=file_path, auto_register=auto_register)
        config.load_config_to_env()
        return config


# 设置配置键和文件路径
CoreConfig.set_config_key("system")
CoreConfig.set_config_file_path(CONFIG_PATH)

try:
    config = CoreConfig.load_config()
    config_schema = config.model_json_schema()
except Exception as e:
    print(f"HoloCortexZero 配置文件加载失败: {e} | 请检查配置文件是否符合语法要求")
    print("应用将退出...")
    exit(1)

config.dump_config()


def save_config():
    """保存配置"""
    global config
    config.dump_config()


def reload_config():
    """重新加载配置文件"""
    global config

    new_config = CoreConfig.load_config()
    # 更新配置字段
    for field_name in CoreConfig.model_fields:
        value = getattr(new_config, field_name)
        setattr(config, field_name, value)
