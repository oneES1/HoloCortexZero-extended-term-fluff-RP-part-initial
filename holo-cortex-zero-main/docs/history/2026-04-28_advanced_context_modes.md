# 高级 Context 模式体系（norm / deek / deep）

## 背景

本次把旧的 `the_deep` 临时运行态收口为“高级 context 模式体系”。高级用户 `<ADVANCED_USER_ID>` 的 context 仍固定为 `context_id=<ADVANCED_USER_ID>`；普通 context 不具备模式切换能力。

旧逻辑里：

- prompt 只分普通、高级、高级 deep；
- deep 状态由 `system_the_deep_service` 的内存状态控制；
- 普通 context 也存在一条 deep 模型组覆盖路径，容易形成误用。

新逻辑里：

- 持久模式在 `context_window.advanced_context_mode`；
- LLM Stage1 自动 deep 只作为当前 tool 链的一轮临时覆盖；
- 普通 context 不读取、不保存、不响应模式。

## 模式表

| 模式 | 命令 | 聊天框提示 | Prompt 字段 | 模型组字段 |
| --- | --- | --- | --- | --- |
| norm | `/norm` | 我会尽量用最helpful和honest的方式回应你 | `MAIN_SYSTEM_PROMPT_ADVANCED` | `USE_MODEL_GROUP` |
| deek | `/deek` | 好的，我们需要更深度一些 | `MAIN_SYSTEM_PROMPT_ADVANCED_DEEK` → `MAIN_SYSTEM_PROMPT_ADVANCED` | `ADVANCED_CONTEXT_MODE_DEEK_MODEL_GROUP` → `USE_MODEL_GROUP` |
| deep | `/deep` | 我可以帮你做，需要我接住你吗 | `MAIN_SYSTEM_PROMPT_ADVANCED_DEEP` | `SYSTEM_THE_DEEP_MODEL_GROUP` → `USE_MODEL_GROUP` |

`deek` 的 prompt 和模型组刻意不写死供应商或模型名，必须通过配置手填；未配置时系统保持可用并写 warning。
`norm` 直接复用主模型组，`deep` 直接复用现有 the_deep 专用模型组，避免为同一语义保留并行配置项。

## 状态机

1. 高级用户发送精确命令 `/norm`、`/deek`、`/deep`：
   - 不写聊天历史；
   - 不触发 LLM；
   - 空闲时写入 `advanced_context_mode=<mode>`、`advanced_context_mode_source=manual`，并把 `active_dialog_id` 切到命令所在聊天框；
   - tool 链运行中只发提示，不写模式、不切锚点。
2. 高级用户发送普通消息：
   - 如果从私聊切入，默认覆盖为 `deek/default`；
   - 如果从群聊切入，默认覆盖为 `norm/default`；
   - 如果仍在同一聊天框，保留当前手工或默认模式。
3. LLM Stage1 判定 `topic_mode=B`：
   - 只开启 `system_the_deep_service` 的临时 deep 覆盖；
   - 不写 DB 持久模式；
   - tool 链结束后恢复 DB 中的模式。
4. 普通用户发送 `/norm`、`/deek`、`/deep`：
   - 直接忽略；
   - 不回复；
   - 不写 `DBChatMessage`；
   - 不创建普通 context 模式状态。

## 数据库字段

`context_window` 新增：

- `advanced_context_mode VARCHAR(32) NOT NULL DEFAULT 'norm'`
- `advanced_context_mode_source VARCHAR(32) NOT NULL DEFAULT 'default'`

启动时由 `context_window_manager.ensure_schema_columns()` 自补列，并对高级窗口做轻量回填：私聊默认 `deek`，群聊默认 `norm`。

## 关键文件

- `holo_cortex_zero/services/advanced_context_mode.py`：高级模式主干注册表与选择逻辑。
- `holo_cortex_zero/services/context_window/manager.py`：schema 自补、默认模式、手工模式落库。
- `holo_cortex_zero/services/message_service.py`：手工命令入口。
- `holo_cortex_zero/services/agent/prompt_selector.py`：prompt 选择委托。
- `holo_cortex_zero/services/agent/run_agent_v2.py`：高级模式模型组路由，普通 context 不再消费 deep 覆盖。
- `holo_cortex_zero/services/the_deep/service.py`：仅保留 LLM 一轮临时 deep 覆盖。
- `frontend/src/pages/prompt-management/index.tsx`：Prompt 管理页显式展示 `MAIN_SYSTEM_PROMPT_ADVANCED_DEEK`。

## 验证命令

```bash
cd /path/to/source-root
python3 -m py_compile \
  holo_cortex_zero/models/db_context_window.py \
  holo_cortex_zero/services/context_window/manager.py \
  holo_cortex_zero/services/advanced_context_mode.py \
  holo_cortex_zero/services/message_service.py \
  holo_cortex_zero/services/agent/prompt_selector.py \
  holo_cortex_zero/services/agent/run_agent_v2.py \
  holo_cortex_zero/services/the_deep/service.py \
  holo_cortex_zero/core/config.py \
  holo_cortex_zero/services/init_new_arch.py
uv run poe test
```

## 部署命令

后端热更新当前运行态：

```bash
cd /path/to<CONTAINER_WORKSPACE_DIR>
printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero
```

## 风险与回滚点

风险：

- 新增 DB 列依赖启动自补，若启动早期顺序被改动，旧表可能缺列；因此自补放在 memory runtime 前。
- `deek` 未配置 prompt/model 时会回退高级 prompt/主模型组，行为可用但不代表最终 deek 风格。
- tool 链运行中的命令只提示不落库，用户需要链路结束后重发命令。

回滚点：

- `backup(init): snapshot before advanced context modes`
- `feat(context): add advanced context mode state`
- `feat(agent): route advanced context modes`
- `chore(docs): document advanced context modes`

DB 新列可安全保留，旧代码不会读取。
