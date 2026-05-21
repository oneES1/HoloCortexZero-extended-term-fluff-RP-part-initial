# 2026-05-08 辅助 LLM 模型组参数主干修复

## 目标

- 全面修复辅助 LLM 未统一吃模型组 GUI 参数的问题。
- 保留 `EXTRA_BODY` 作为低优先级兼容逃生口，不删除已有透传机制。
- 让 GUI 字段成为主干，覆盖 `EXTRA_BODY` 中冲突项：`REASONING_MODE`、`TEXT_VERBOSITY`、`IMAGE_MAX_COUNT`、`MAX_OUTPUT_TOKENS`、`REPLAY_REASONING_CONTENT`。
- 保留本地图片压缩字段 `local_chat_image_max_long_edge: 768`，该字段对本地多模态模型有效。

## 修改

- 新增 `holo_cortex_zero/services/llm/model_group_params.py`：集中构造模型组通用 `extra_params`。
- 主对话 `run_agent_v2.py`、辅助入口 `auxiliary.py`、记忆仲裁 `mem0_utils.py`、潜意识 `subconscious.py`、AI 回复判断 `ai_reply/service.py` 统一复用该主干。
- `auto_memory.py` 通过 `prepare_auxiliary_request()` 自动合并模型组参数，请求级 `tool_choice` / `parallel_tool_calls` 仍覆盖或追加。
- `openai_chat.py` 增加 DeepSeek 官方 chat 工具调用兼容：当目标是 DeepSeek 官方且请求包含 tools，删除不兼容的 `tool_choice=required`，保留 `reasoning_effort=high` 和 `thinking.enabled`。

## 证据

- 编译：`uv run python -m py_compile ...` 通过 8 个相关文件。
- 参数断言：`meromero-31b-resident-think` 从旧 `EXTRA_BODY.thinking.disabled` 被 GUI `REASONING_MODE=high` 覆盖，最终 `reasoning={"effort":"high"}`，无 `thinking`。
- 图片字段断言：`meromero-31b-resident` 保留 `local_chat_image_max_long_edge=768`。
- `memory_manage` 真调用：模型组 `deepseek-v4-flash`，返回 `action=UPDATE`、`targets=['1']`。
- `subconscious` 真调用：模型组 `doubao-nonthinking2`，返回 JSON 文本长度 `92`。
- `timeline` 真调用：模型组 `meromero-31b-resident-think`，返回正文长度 `8`，日志显示 `reasoning content dropped before persistence`，说明模型产生过思维链但因 `REPLAY_REASONING_CONTENT=false` 未持久化。
- `auto_memory` 真调用：模型组 `deepseek-v4-flash`，归一化后删除 `tool_choice=required`，保留 `reasoning_effort=high` 和 `thinking={"type":"enabled"}`；返回 `tool_calls=1`、`text_len=0`、`reasoning_len=170`、`finish=tool_calls`。
- `AI_REPLY_JUDGE_MODEL_GROUP` 当前运行配置为空字符串，业务链路未启用，因此无真实外呼可测。

## 已定位的兼容问题

DeepSeek 官方 reasoner 在 tool 请求中不支持 `tool_choice=required`。最小重放结果：

- 原请求：HTTP 400，错误 `deepseek-reasoner does not support this tool_choice`。
- 仅删除 `tool_choice`：HTTP 200，保留 reasoning，并返回 `tool_calls`。
- 仅删除 reasoning：仍 HTTP 400。
- 同时删除二者：HTTP 200。

因此主干修复选择只在 DeepSeek 官方 + tools + `tool_choice=required` 时删除 `tool_choice`，不关闭思维链。

## 回滚点

- 修改提交：`085f110 fix(llm): unify auxiliary model group params`。
- 前置快照：`73347c1 backup(llm): snapshot auxiliary params unification`。

## 追加修复：禁止默认 tool_choice=required

- 将 `CoreConfig.AUTO_MEMORY_TOOL_CHOICE` 默认值从 `required` 改为 `auto`。
- 将 auto_memory 请求构造的空值兜底从 `required` 改为 `auto`。
- 当前运行配置已是 `AUTO_MEMORY_TOOL_CHOICE: auto`，本次修复消除新配置/缺省配置回落到 `required` 的潜在风险。
- 保留 `openai_chat` 对外部误配 `tool_choice=required` 的 DeepSeek 官方防御性删除分支；该分支不是来源，只是避免已实证的 HTTP 400。

验证：

- `uv run python -m py_compile holo_cortex_zero/core/config.py holo_cortex_zero/services/memory/auto_memory.py holo_cortex_zero/services/llm/openai_chat.py` 通过。
- `CoreConfig.model_fields['AUTO_MEMORY_TOOL_CHOICE'].default == 'auto'`。
- 运行配置 `AUTO_MEMORY_TOOL_CHOICE == 'auto'`。
- `AutoMemoryService()._build_generation_request(...).extra_params['tool_choice'] == 'auto'`。
