# 2026-05-17 修复记忆检索最近消息配置词条

## 背景

前端配置表从后端 schema 的 `title`、`description`、`i18n_title`、`i18n_description` 渲染配置词条。

`AI_CHAT_CONTEXT_MAX_LENGTH` 原词条为“对话上下文最大条数”，容易误解为主对话 context window 的上限。

## 证据

- `holo_cortex_zero/core/config.py` 中 `AI_CHAT_CONTEXT_MAX_LENGTH` 原标题为“对话上下文最大条数”。
- `holo_cortex_zero/services/memory/runtime.py` 仅在 `inject_memory_prompt()` 中使用该字段：
  - 第一次查询 `.limit(core_config.AI_CHAT_CONTEXT_MAX_LENGTH * 3)`。
  - 过滤系统消息后执行 `recent_messages[: core_config.AI_CHAT_CONTEXT_MAX_LENGTH]`。
  - fallback 查询同样只用于 recent messages 取样。
- 全仓库搜索未发现该字段参与主 context window 拼装或高级 context 压缩逻辑。

## 修改

- 中文标题为“记忆检索取样的最近聊天消息数”。
- 英文标题为 `Recent Chat Message Sample Count for Memory Retrieval`。
- 描述清空，避免备注继续扩展或误导词条语义。

## 验证

```bash
rg -n 'AI_CHAT_CONTEXT_MAX_LENGTH|对话上下文最大条数|Max Context Message Count|Maximum number of context messages' . --glob '!*.log' --glob '!logs/**'
```

预期：旧词条不再出现在代码配置中；字段名仍保留，运行逻辑不变。

## 风险与回滚

- 风险：仅修改配置 schema 展示文案，不改字段名、默认值和运行逻辑。
- 回滚点：本次修复提交。
