# 2026-04-02 辅助 LLM 协议拆分更新

## 目标

- `SUBCONSCIOUS_MODEL`：固定走 `chat`，关闭思维链，不走工具。
- `AI_REPLY_JUDGE_MODEL_GROUP`：固定走 `chat`，关闭思维链，不走工具。
- `AUTO_MEMORY_MODEL_GROUP`：必须走工具调用；协议允许 `chat` / `responses` 共用主干，但当前运行态显式收敛到 `qwen35-hcz-resident-think -> responses + tool(auto)`。

## 本次修改

### 代码

- `holo_cortex_zero/services/memory/auto_memory.py`
  - 不再把 `AUTO_MEMORY` 协议硬编码成 `chat`。
  - 改为按模型组 `WIRE_API` / 自动判定结果选择 `chat` 或 `responses` 发射器。
  - 保持 `AUTO_MEMORY` 始终携带 `add_memory` 工具定义与 `tool_choice`，不引入 chat-json 分支。
  - 请求日志会标出 `model_group` 与 `protocol`，便于区分缓存前缀与路由行为。

### 运行态配置

- `qwen35-hcz-resident`
  - 保持 `WIRE_API=chat`
  - 保持 `thinking.disabled`
  - 新增 `skip_native_tools=true`
- `AI_REPLY_JUDGE_MODEL_GROUP`
  - 切到 `qwen35-hcz-resident`
- `AUTO_MEMORY_MODEL_GROUP`
  - 切到本地 `qwen35-hcz-resident-think`
  - 显式 `WIRE_API=responses`
  - 去掉 `thinking.disabled`，保留本地 resident 的 responses+tool auto 能力
- `AUTO_MEMORY_TOOL_CHOICE`
  - 保持 `auto`，避免 `required` 带来的兼容性问题

## 设计边界

- `SUBCONSCIOUS` / `JUDGE` 与 `AUTO_MEMORY` 的 system prompt、协议、工具定义都不同，天然形成不同缓存前缀。
- 缓存隔离依赖真实前缀差异，而不是靠额外写死供应商分支。
- 主干仍保持：
  - `chat` 发射器统一处理 OpenAI-compatible chat
  - `responses` 发射器统一处理 responses
  - 业务层只通过模型组协议配置决定走哪条链
