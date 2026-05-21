# 2026-05-09 /clearall timeline reset

## 背景

用户要求新增 `/clearall` 指令：在 `/clear` 全局清理基础上，进一步清空 timeline 已落地压缩内容，并让压缩版本与消息计数从头开始。

## 当前逻辑证据

- `/clear` 入口在 `message_service.py` 消息入库前拦截，普通用户直接忽略，高级用户空闲时执行全局清理。
- 清理主干在 `context_window/manager.py::clear_all_message_and_context_records`，现有 `/clear` 已清空：
  - `chat_message` 全表；
  - `context_message` 全表；
  - `context_dialog_state` 全表；
  - `last_compress_version=0`；
  - `msg_count_since_compress=0`；
  - `summary_generating=False`；
  - `pending_summary=""`；
  - `pending_summary_ready=False`；
  - 自动记忆计数字段。
- 现有 `/clear` 明确保留 `compressed_summary`，因此聊天历史已清空后，旧压缩摘要仍会继续注入高级 context。

## 变更

- 新增精确命令 `/clearall`，与 `/clear` 共用高级用户门禁、运行中拒绝、全局消息清理和运行态队列清理。
- 给 `clear_all_message_and_context_records` 增加参数 `clear_compressed_summary`：
  - `/clear` 传 `False`，保留旧语义；
  - `/clearall` 传 `True`，额外将所有 `context_window.compressed_summary` 置空。
- 返回结果增加 `compressed_summaries_cleared`，日志记录本次清掉多少条非空压缩摘要。
- `/clearall` 回执为 `杂乱与压缩记忆已清除`。

## 从头计数定义

`/clearall` 执行后，每个 `context_window` 的 timeline 相关字段为：

- `compressed_summary=""`
- `last_compress_version=0`
- `msg_count_since_compress=0`
- `summary_generating=False`
- `pending_summary=""`
- `pending_summary_ready=False`

下一轮消息重新进入 `context_message` 后，实际条数从空表开始累计；达到阈值后生成的新摘要会从 `v1` 开始。

## 风险

- `/clearall` 会删除所有聊天消息、所有 context 消息和所有已落地 timeline 摘要，影响是全局的。
- 不删除长期记忆库、配置、模型组、`context_window` 行、高级模式和锚点。
- 运行中 agent/task/tool 链存在时仍拒绝清理，避免边清边写导致状态不一致。

## 验证

```bash
cd /path/to/source-root
python3 -m py_compile \
  holo_cortex_zero/services/message_service.py \
  holo_cortex_zero/services/context_window/manager.py
```

## 部署

仅后端 Python 代码变更，按当前运行态同步：

```bash
cd /path/to<CONTAINER_WORKSPACE_DIR>
printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --no-deps --force-recreate holo_cortex_zero
```
