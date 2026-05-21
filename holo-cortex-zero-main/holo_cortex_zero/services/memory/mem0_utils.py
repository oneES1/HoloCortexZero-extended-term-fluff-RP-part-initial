import asyncio  # noqa: I001
import json
from typing import Optional, List, Dict, Any

from mem0 import AsyncMemory
from mem0.configs.base import MemoryConfig as Mem0Config
from mem0.embeddings.configs import EmbedderConfig
from mem0.llms.configs import LlmConfig
from mem0.vector_stores.configs import VectorStoreConfig
from holo_cortex_zero.api.core import get_qdrant_config, logger
from holo_cortex_zero.api.schemas import AgentCtx

from holo_cortex_zero.core.config import CoreConfig as MemoryConfig, config
from holo_cortex_zero.core.prompt_defaults import DEFAULT_MEMORY_ARBITER_SYSTEM_PROMPT_TEMPLATE, render_identity_prompt
from holo_cortex_zero.core.runtime_identity import (
    get_bot_persona_display_name,
    get_primary_advanced_user_display_name,
    get_primary_advanced_user_id,
)
from holo_cortex_zero.schemas.ir import GenerationRequest, MessagePart, MessageTurn
from holo_cortex_zero.services.llm.auxiliary import generate_auxiliary
from holo_cortex_zero.services.llm.model_group_params import build_model_group_extra_params
from holo_cortex_zero.services.llm.qwen_compat import _extract_json_object
from holo_cortex_zero.services.llm.router import detect_model_group_protocol

from .payload_logs import dump_memory_json
from .context_env import build_memory_dialog_env_from_ctx
from .graph_cache import HCZ_SELF
from .utils import get_model_group_info

_mem0_instance = None
_last_config_hash = None
MEMORY_COLLECTION_NAME = "holo_cortex_zero_memory"
_mem0_lock: asyncio.Lock = asyncio.Lock()


def _normalize_memory_manage_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    action = str(payload.get("action") or "ADD").strip().upper()
    if action not in {"ADD", "UPDATE", "REJECT"}:
        action = "ADD"

    targets_raw = payload.get("targets")
    targets: List[str] = []
    if isinstance(targets_raw, list):
        targets = [str(item).strip() for item in targets_raw if str(item).strip()]

    result: Dict[str, Any] = {
        "action": action,
        "targets": targets,
        "reason": str(payload.get("reason") or "").strip(),
    }

    new_content = str(payload.get("new_content") or "").strip()
    if new_content:
        result["new_content"] = new_content
    return result


def _messages_to_turns(messages: List[Dict[str, str]]) -> List[MessageTurn]:
    turns: List[MessageTurn] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role_raw = str(msg.get("role") or "user").strip().lower()
        role = role_raw if role_raw in {"system", "user", "assistant", "tool"} else "user"
        turns.append(
            MessageTurn(
                role=role,  # type: ignore[arg-type]
                parts=[MessagePart(type="text", text=str(msg.get("content") or ""))],
            ),
        )
    return turns


def _apply_graph_write_override(
    result: Dict[str, Any],
    *,
    metadata: Dict[str, Any],
    is_graph_write: bool,
    existing_memories: List[Dict[str, Any]],
    new_memory: str,
) -> Dict[str, Any]:
    if not is_graph_write:
        return result

    alias = str(metadata.get("alias") or "").strip()
    keyword = str(metadata.get("keyword") or "").strip()
    signal = alias or keyword

    matched_ids: List[str] = []
    for mem in existing_memories:
        mid = str(mem.get("id") or "").strip()
        content = str(mem.get("memory") or "")
        if not mid:
            continue
        if signal and signal in content:
            matched_ids.append(mid)

    if not matched_ids and len(existing_memories) == 1:
        only_id = str(existing_memories[0].get("id") or "").strip()
        if only_id:
            matched_ids.append(only_id)

    normalized = dict(result or {})
    action = str(normalized.get("action") or "ADD").strip().upper()
    if action == "UPDATE" or not matched_ids:
        if action == "REJECT":
            normalized["action"] = "ADD"
            normalized["reason"] = (
                str(normalized.get("reason") or "").strip()
                + " 图谱类写入禁止 REJECT，已回退为 ADD。"
            ).strip()
        return normalized

    normalized["action"] = "UPDATE"
    normalized["targets"] = matched_ids
    normalized["new_content"] = str(normalized.get("new_content") or new_memory).strip() or str(new_memory or "").strip()
    normalized["reason"] = (
        str(normalized.get("reason") or "").strip()
        + " 图谱类同 alias/keyword 命中旧记录，已按主干规则收敛为 UPDATE。"
    ).strip()
    return normalized



async def create_mem0_client(config: Mem0Config) -> AsyncMemory:
    # 创建mem0实例
    return AsyncMemory(config)

async def create_mem0_config() -> Mem0Config:
    # 创建mem0配置实例
    qdrant_config = get_qdrant_config()
    memory_config: MemoryConfig = config
    llm_model = get_model_group_info(memory_config.MEMORY_MANAGE_MODEL)
    embedding_model = get_model_group_info(memory_config.TEXT_EMBEDDING_MODEL)

    # 占位符逻辑：当 model 或 openai_base_url 为空时，用 NEED_INPUT 占位，避免底层依赖直接抛错
    NEED_INPUT = "NEED_INPUT"

    def _fallback(value: Optional[str]) -> str:
        return value if (value is not None and str(value).strip() != "") else NEED_INPUT

    llm_model_name = _fallback(llm_model.CHAT_MODEL)
    llm_base_url = _fallback(llm_model.BASE_URL)
    embedder_model_name = _fallback(embedding_model.CHAT_MODEL)
    embedder_base_url = _fallback(embedding_model.BASE_URL)
    return Mem0Config(
        vector_store=VectorStoreConfig(
            provider="qdrant",
            config={
                "url": qdrant_config.url,
                "api_key": qdrant_config.api_key,
                "collection_name": MEMORY_COLLECTION_NAME,
                "embedding_model_dims": memory_config.TEXT_EMBEDDING_DIMENSION,
            },
        ),
        llm=LlmConfig(
            provider="openai",
            config={
                "api_key": llm_model.API_KEY,
                "model": llm_model_name,
                "openai_base_url": llm_base_url,
                "temperature": 0,
            },
        ),
        embedder=EmbedderConfig(
            provider="openai",
            config={
                "api_key": embedding_model.API_KEY,
                "model": embedder_model_name,
                "openai_base_url": embedder_base_url,
                "embedding_dims": memory_config.TEXT_EMBEDDING_DIMENSION,
            },
        ),
        version="v1.1",
    )

def _config_incomplete() -> bool:
    """检测记忆配置是否完整，若 API_KEY / MODEL / BASE_URL 任何一项为空则判定为不完整。"""
    memory_cfg: MemoryConfig = config
    model_groups = getattr(config, "MODEL_GROUPS", {}) or {}
    if (
        not str(memory_cfg.MEMORY_MANAGE_MODEL or "").strip()
        or not str(memory_cfg.TEXT_EMBEDDING_MODEL or "").strip()
        or memory_cfg.MEMORY_MANAGE_MODEL not in model_groups
        or memory_cfg.TEXT_EMBEDDING_MODEL not in model_groups
    ):
        return True

    llm_model = get_model_group_info(memory_cfg.MEMORY_MANAGE_MODEL)
    embedding_model = get_model_group_info(memory_cfg.TEXT_EMBEDDING_MODEL)

    def _empty(v: Optional[str]) -> bool:
        return v is None or str(v).strip() == ""

    return any(
        [
            _empty(llm_model.API_KEY),
            _empty(llm_model.CHAT_MODEL),
            _empty(llm_model.BASE_URL),
            _empty(embedding_model.API_KEY),
            _empty(embedding_model.CHAT_MODEL),
            _empty(embedding_model.BASE_URL),
        ],
    )


async def get_mem0_client() -> Optional[AsyncMemory]:
    """异步获取mem0客户端实例"""
    global _mem0_instance, _last_config_hash

    # 若配置不完整，则跳过初始化，避免底层依赖抛错导致运行时加载失败
    if _config_incomplete():
        logger.warning(
            "记忆模块配置不完整：请在系统配置中补齐 记忆管理模型/向量嵌入模型 的 API_KEY/BASE_URL/MODEL。",
        )
        return None

    # 使用原始可序列化字段构建稳定指纹，避免直接哈希模型对象
    memory_cfg: MemoryConfig = config
    qdrant_cfg = get_qdrant_config()
    llm_model = get_model_group_info(memory_cfg.MEMORY_MANAGE_MODEL)
    embedding_model = get_model_group_info(memory_cfg.TEXT_EMBEDDING_MODEL)
    collection_name = MEMORY_COLLECTION_NAME

    fingerprint_parts = (
        str(qdrant_cfg.url or ""),
        str(qdrant_cfg.api_key or ""),
        str(collection_name or ""),
        str(memory_cfg.TEXT_EMBEDDING_DIMENSION),
        str(llm_model.API_KEY or ""),
        str(llm_model.CHAT_MODEL or ""),
        str(llm_model.BASE_URL or ""),
        str(embedding_model.API_KEY or ""),
        str(embedding_model.CHAT_MODEL or ""),
        str(embedding_model.BASE_URL or ""),
    )
    current_hash = hash("|".join(fingerprint_parts))

    # 如果配置变了或者实例不存在，重新初始化（并发保护）
    if _mem0_instance is None or current_hash != _last_config_hash:
        async with _mem0_lock:
            # 双检，避免重复初始化
            if _mem0_instance is None or current_hash != _last_config_hash:
                memory_config = await create_mem0_config()
                _mem0_instance = await create_mem0_client(memory_config)
                _last_config_hash = current_hash
                logger.info("记忆管理器已重新初始化")

    return _mem0_instance

async def analyze_memory_conflict(
    new_memory: str,
    existing_memories: List[Dict[str, Any]],
    *,
    user_id: str = "未知",
    metadata: Optional[Dict[str, Any]] = None,
    ctx: Optional[AgentCtx] = None,
) -> Dict[str, Any]:
    """
    使用 DeepSeek (或配置的记忆管理模型) 分析新旧记忆冲突
    """
    memory_config: MemoryConfig = config
    llm_model = get_model_group_info(memory_config.MEMORY_MANAGE_MODEL)
    
    if not llm_model.API_KEY or not llm_model.BASE_URL:
         return {"action": "ADD"}

    metadata = metadata or {}

    def _build_chat_context() -> str:
        """为仲裁 Prompt 构造“对话环境”声明（最高优先级，必须准确）。"""
        if ctx is None:
            return "【对话环境】未知环境"

        env = build_memory_dialog_env_from_ctx(ctx)
        return env.chat_env_note or "【对话环境】未知环境"

    # 格式化现有记忆用于 Prompt
    # 注意：这里必须有换行符，否则多条记忆会粘在一起，LLM 更容易误判为“同一条/同一主体”。
    mem_list_str = ""
    existing_memory_ids: List[str] = []
    for mem in existing_memories:
        mid = mem.get("id")
        content = mem.get("memory")
        score = mem.get("score", 0)
        if mid is not None:
            existing_memory_ids.append(str(mid))
        # 尝试转换 score 为 float 以便显示
        try:
            score_val = float(score)
            score_str = f"{score_val:.2f}"
        except:
            score_str = str(score)
            
        mem_list_str += f"- [ID: {mid}] {content} (Score: {score_str})\n"

    # 图谱类写入：必须保证落库（用于 Stage0 冷启动与重启恢复）。
    # 对 relation_map / knowledge_index：
    # - 默认不允许 REJECT
    # - alias/keyword 相同则倾向 UPDATE（覆盖旧的映射），保证“最新关系”生效
    md_type = None
    try:
        md_type = metadata.get("type") or metadata.get("TYPE")
    except Exception:
        md_type = None
    md_type_norm = str(md_type).strip().lower() if md_type is not None else ""
    is_graph_write = md_type_norm in {"relation_map", "relationmap", "relation", "knowledge_index", "knowledgeindex", "knowledge"}

    # 注意：这里不能在 f-string 里直接写 JSON 示例的 `{}`，否则会触发 Python f-string 格式化解析，
    # 导致 `ValueError: Invalid format specifier`，从而使后台写入 worker 直接失败。
    # 因此：
    # - 变量插值仍用 f-string；
    # - JSON 示例里的花括号必须写成 `{{` / `}}`。

    # 动态构建身份上下文，避免 LLM 对 HCZ_SELF 产生“这是个人类用户”的认知偏差
    if str(user_id) == HCZ_SELF:
        owner_context = f"【当前写入目标】= {get_bot_persona_display_name(memory_config)}潜意识 (HCZ_SELF · 全局分区)"
    else:
        uid = str(user_id or "").strip()
        primary_advanced_user_id = get_primary_advanced_user_id(memory_config)
        primary_advanced_user_display_name = get_primary_advanced_user_display_name(memory_config)
        if uid == primary_advanced_user_id:
            owner_context = (
                f"【当前写入归属】= 高级用户 "
                f"(User_ID: {primary_advanced_user_id} · {primary_advanced_user_display_name})"
            )
        else:
            owner_context = (
                f"【当前写入归属】= 第三方普通用户 "
                f"(User_ID: {uid} · 明确≠{primary_advanced_user_display_name}({primary_advanced_user_id}))"
            )

    chat_context = _build_chat_context()

    metadata_json = json.dumps(metadata, ensure_ascii=False)
    prompt_template = str(getattr(memory_config, "MEMORY_ARBITER_SYSTEM_PROMPT", "") or "").strip()
    if not prompt_template:
        prompt_template = DEFAULT_MEMORY_ARBITER_SYSTEM_PROMPT_TEMPLATE
    prompt_template = render_identity_prompt(prompt_template, memory_config)
    system_prompt = prompt_template.format(
        owner_context=owner_context,
        chat_context=chat_context,
        metadata_json=metadata_json,
    )
    logger.debug("memory arbiter system prompt resolved: prompt_length=%s", len(system_prompt))

    user_prompt = f"""
现有记忆:
{mem_list_str}
新记忆:
{new_memory}
"""

    try:
        protocol = detect_model_group_protocol(llm_model, allow_legacy_wire_api=True)
        request_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        request_extra_params = build_model_group_extra_params(llm_model, source_hint="memory.manage")
        if protocol == "chat":
            request_extra_params.setdefault("response_format", {"type": "json_object"})

        request = GenerationRequest(
            context_id="aux:memory_manage",
            model="",
            messages=_messages_to_turns(request_messages),
            temperature=0.1,
            max_tokens=None,
            stream=False,
            extra_params=request_extra_params,
        )

        dump_memory_json(
            "manage",
            "request",
            {
                "kind": "memory_manage_request",
                "user_id": str(user_id or ""),
                "metadata": metadata,
                "owner_context": owner_context,
                "chat_context": chat_context,
                "is_graph_write": is_graph_write,
                "new_memory": new_memory,
                "existing_memory_ids": existing_memory_ids,
                "existing_memories": existing_memories,
                "chat_key": str(getattr(ctx, "chat_key", "") or "") if ctx else "",
                "from_chat_key": str(getattr(ctx, "from_chat_key", "") or "") if ctx else "",
                "from_user_id": str(getattr(ctx, "from_user_id", "") or "") if ctx else "",
                "protocol": protocol,
                "payload_messages": request_messages,
                "extra_params": request_extra_params,
            },
        )

        result = await generate_auxiliary(
            aux_name="memory_manage",
            model_group_key=str(memory_config.MEMORY_MANAGE_MODEL or ""),
            request=request,
            source="memory.manage",
            timeout=1200.0,
        )

        content = str(result.text or "").strip()
        if not content:
            return {"action": "ADD"}

        if content.startswith("```"):
            first_newline_index = content.find("\n")
            if first_newline_index != -1:
                content = content[first_newline_index + 1 :]
            if content.endswith("```"):
                content = content[:-3].strip()

        parsed_payload = _extract_json_object(content)
        if parsed_payload is None:
            parsed_payload = json.loads(content)
        parsed_result = _normalize_memory_manage_result(parsed_payload)
        parsed_result = _apply_graph_write_override(
            parsed_result,
            metadata=metadata,
            is_graph_write=is_graph_write,
            existing_memories=existing_memories,
            new_memory=new_memory,
        )

        dump_memory_json(
            "manage",
            "response",
            {
                "kind": "memory_manage_response",
                "user_id": str(user_id or ""),
                "metadata": metadata,
                "owner_context": owner_context,
                "chat_context": chat_context,
                "new_memory": new_memory,
                "existing_memory_ids": existing_memory_ids,
                "chat_key": str(getattr(ctx, "chat_key", "") or "") if ctx else "",
                "from_chat_key": str(getattr(ctx, "from_chat_key", "") or "") if ctx else "",
                "from_user_id": str(getattr(ctx, "from_user_id", "") or "") if ctx else "",
                "protocol": protocol,
                "raw_response": result.raw_response,
                "raw_response_content": result.text,
                "parsed_result": parsed_result,
            },
        )
        return parsed_result
    except Exception as e:
        logger.error(f"记忆仲裁失败: {e}")
        return {"action": "ADD"}
