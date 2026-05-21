# 2026-05-01 `/test` 调试命令触发普通窗口 context

## 目标

- 增加 `/test` 调试命令，行为仿照 `/clear` 的命令入口拦截。
- 只允许高级用户触发，普通用户发送 `/test` 直接忽略。
- 高级用户在群聊发送 `/test` 时，不触发高级用户固定 context，而是触发当前群聊窗口的普通 context 回复。
- `/test` 本身不得写入 `DBChatMessage`，不得进入上下文消息记录。

## 当前逻辑定位

- 命令入口在 `holo_cortex_zero/services/message_service.py::push_human_message`。
- `/clear` 在消息入库前识别并 `return`，因此命令文本不写入聊天消息表。
- 高级用户判断复用 `context_window_manager._is_advanced_sender(...)`，当前高级用户 ID 由 `ADVANCED_USER_ID` 配置决定，默认例如 `<ADVANCED_USER_ID>`。
- 普通 context 路由规则在 `context_window_manager.resolve_context_window`：`user_id` 不是高级用户时，`context_id = chat_key`。

## 修改

- 新增 `_TEST_COMMAND = "/test"` 与 `_is_test_command()`。
- 在 forbidden check 前识别 `/test`，避免命令被普通文本过滤吞掉后继续走普通消息路径。
- 与 `/clear` 共用高级用户门禁：`not context_window_manager._is_advanced_sender(context_user_id)` 时直接记录日志并返回。
- 高级用户触发 `/test` 时：
  - 调用 `resolve_context_window(user_id="", chat_key=message.chat_key, ...)`，强制解析到当前窗口普通 context。
  - 调用 `update_anchor(normal_window.context_id, message.chat_key)`，确保回复发回当前窗口。
  - 创建 `ChatMessage.create_empty(message.chat_key)`，不填 `adapter_key` / `sender_id` / `content_text`，保持 `is_empty() == True`。
  - 调用 `schedule_agent_task(..., execution_key=normal_window.context_id, source_scope="system")`。

## 无污染证明

- `/test` 分支位于 `DBChatMessage.create(...)` 之前，命令消息不会写入聊天消息表。
- 传给调度器的是空消息；`_debounce_task` 会用 `final_message if not final_message.is_empty() else None`，因此 `run_agent_v2` 收到 `chat_message=None`。
- `run_agent_v2` 在 `chat_message=None` 时不会注入“当前轮用户消息”，只会同步该窗口已有聊天记录并启动回复。
- 普通用户 `/test` 在入库前被高级门禁拦截，也不会写入消息记录。

## 验证

- `python3 -m compileall -q holo_cortex_zero/services/message_service.py`

## 风险与回滚点

- 风险：`/test` 会真实启动当前窗口普通 context 的一次 bot 回复，可能消耗一次普通 context 模型调用。
- 风险：如果当前普通窗口已有未同步历史，触发时会按现有 `sync_new_chat_messages` 规则吸收已有历史，但不会吸收 `/test` 命令本身。
- 回滚点：回退本次提交即可移除 `/test` 命令入口和文档。

## 运行态同步补记

- 现象：首次实现后用户实测无效。
- 复核证据：`docker compose ps` 显示 `holo_cortex_zero` 容器创建时间早于本次修改提交；容器文件中已存在 `_TEST_COMMAND`，但服务进程未重启，Python 模块仍是旧运行态。
- 操作：执行 `docker compose -f docker-compose.yml up -d --no-deps --force-recreate holo_cortex_zero`，只重建后端本体，不重启 `hcz_postgres` / `hcz_qdrant`。
- 健康证据：重建后 `holo_cortex_zero` 状态为 `healthy`，最近日志包含 `Started server process [1]` 与 `Application startup complete.`。
- 下一步验证：请高级用户在目标群聊重新发送 `/test`，期望触发该群聊普通 context 回复，并在日志中出现 `advanced test command scheduled normal context reply without message record`。
