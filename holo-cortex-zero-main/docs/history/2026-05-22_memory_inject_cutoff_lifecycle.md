# 2026-05-22 memory_inject 截断生命周期修正

## 背景

- 前一版“记忆增量历史化”把 recall 增量写成 `msg_type="memory_inject"`。
- 但当时把 `memory_inject` 视为永久保留历史，只在 `/clear` `/clearall` 时清掉。
- 这会造成语义错误：
  - 聊天前缀已经因为普通/高级 context 的压缩阈值被裁掉；
  - 旧 `memory_inject` 仍然保留；
  - `memory_recall_seen_items_json` 也仍然拦住同一 digest 的再次注入。

用户明确要求：

- **阈值水位线仍然只由聊天消息统计**
- **但一旦触发 cutoff，落在 cutoff 之前的 `memory_inject` 必须一起清掉**
- **seen 账本必须同步回退**

## 本次修改

### 1. `memory_inject` 增加结构化生命周期字段

文件：

- `holo_cortex_zero/models/db_context_window.py`
- `holo_cortex_zero/services/context_window/manager.py`

新增字段：

- `DBContextMessage.memory_anchor_context_msg_id`
  - 记录该 `memory_inject` 写入时依附的最新聊天消息 `context_message.id`
- `DBContextMessage.memory_digests_json`
  - 记录该 `memory_inject` 包含的 recall digest 列表

`ensure_schema_columns()` 继续走原有启动自补主干：

- `ALTER TABLE "context_message" ADD COLUMN IF NOT EXISTS "memory_anchor_context_msg_id" INT NOT NULL DEFAULT 0`
- `ALTER TABLE "context_message" ADD COLUMN IF NOT EXISTS "memory_digests_json" TEXT NOT NULL DEFAULT '[]'`

### 2. 账本语义改成“当前仍存活的记忆集合”

`memory_recall_seen_items_json` 不再被视为“这个 context 历史上见过的一切记忆”。

现在它的准确语义是：

- **当前仍存活在该 context 有效窗口里的 `memory_inject` digest 并集**

对应主干：

- 新增 `memory_inject` 时：增量并入新 digest
- cutoff 清理时：基于**剩余 `memory_inject`** 全量重建账本
- `/clear` `/clearall`：直接重置为 `[]`

### 3. cutoff 只按聊天消息统计，但 `memory_inject` 跟随 cutoff 过期

新增统一 helper：

- `_countable_chat_query(...)`
- `_count_countable_chat_messages(...)`
- `_get_countable_chat_cutoff_id(...)`
- `_delete_memory_injects_for_cutoff(...)`
- `_rebuild_memory_recall_seen_items_json(...)`

统计口径固定为：

- `msg_type in ("human_chat", "bot_reply")`

不把以下消息算进 cutoff 触发计数：

- `memory_inject`
- `tool_call`
- `tool_result`
- `system_inject`

### 4. 普通 context

文件：

- `holo_cortex_zero/services/context_window/manager.py`

`_archive_normal_context_history(...)` 现在改为：

1. 用聊天消息数判断是否达到 `NORMAL_CONTEXT_RESET_THRESHOLD_MESSAGES`
2. 用聊天消息计算本次 cutoff
3. 归档并删除 cutoff 之前的普通历史
4. 删除 `memory_anchor_context_msg_id <= cutoff` 的 `memory_inject`
5. 基于剩余 `memory_inject` 重建 `memory_recall_seen_items_json`

`memory_inject` 仍然**不参与**普通 context 的 48/10 阈值计数；
但它不再永久保留，而是随 cutoff 一起过期。

### 5. 高级 context

文件：

- `holo_cortex_zero/services/context_window/manager.py`
- `holo_cortex_zero/services/context_window/timeline.py`

修正点：

- `check_and_trigger_compress(...)`
  - 压缩水位改为只看聊天消息数
- `enforce_history_hard_limit(...)`
  - 高级 context 硬上限触发后，按聊天消息 cutoff 联动清理 `memory_inject`
  - 然后重建 seen 账本
- `try_apply_ready_summary(...)`
  - 应用新摘要时，按聊天消息 cutoff 清旧前缀
  - 同时清掉 cutoff 之前的 `memory_inject`
  - 再重建 seen 账本
- `timeline._do_compress(...)`
  - `memory_inject` 不再进入长期摘要输入
  - 避免“live window 记忆已过期，但摘要又把它长期保存”这个漏口

## 禁止事项落实

本次没有做以下事情：

- 没把 `memory_inject` 纳入普通/高级 context 的阈值计数
- 没改 recall 定义
- 没引入 provider 特化逻辑
- 没新增第二套迁移体系
- 没扩散改动到 auto_memory 主干

## 验证

### 静态

- `python3 -m py_compile` 通过：
  - `models/db_context_window.py`
  - `services/context_window/manager.py`
  - `services/context_window/timeline.py`
  - `services/agent/run_agent_v2.py`

### 容器内真实 DB 函数验证

在运行容器内创建临时 context 做两组验证：

1. **普通 context**
   - 先注入 `digest_A` `digest_B`
   - 再注入 `digest_C`
   - 执行普通 context cutoff 归档
   - 结果：
     - `memory_recall_seen_items_json == ["digest_C"]`
     - 只剩 1 条 `memory_inject`
     - 剩余内容是 `C`

2. **高级 context**
   - 先注入 `digest_X`
   - 再追加新聊天并注入 `digest_Y`
   - 触发高级 context 硬上限清理
   - 结果：
     - `memory_recall_seen_items_json == ["digest_Y"]`
     - 只剩 1 条 `memory_inject`
     - 剩余内容是 `Y`

## 回滚点

主要回滚文件：

- `holo_cortex_zero/models/db_context_window.py`
- `holo_cortex_zero/services/context_window/manager.py`
- `holo_cortex_zero/services/context_window/timeline.py`

若需整体验证前状态，可回退本次功能提交，并删除本文档。
