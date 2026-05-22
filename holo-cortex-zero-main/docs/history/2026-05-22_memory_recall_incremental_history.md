# 2026-05-22 记忆增量历史化改造

## 背景

- 旧链路把记忆 recall、环境标注、行为说明揉成每轮尾部动态块。
- 这种形态会在 tool 多跳和后续回复里持续漂移，导致 payload 尾端不稳定，也让缓存观测和真实历史语义混在一起。
- 本次改造把“记忆 recall”从动态尾端 user guidance 改成 context 内部历史片段，只对首次出现的新记忆做一次性追加。

## 主干修改

### 1. recall 运行时只产出纯记忆候选

涉及：

- `holo_cortex_zero/services/memory/runtime.py`
- `holo_cortex_zero/services/memory/context_env.py`
- `holo_cortex_zero/services/memory/auto_memory.py`

改动：

- 删除 `chat_env_system` 生成与透传。
- 删除动态注入版“我不能直球念记忆”说明。
- 删除“暂无检索结果”占位文案；无 recall 时直接返回空串。
- 新增 `prompt_items` 切条：
  - 按“分组标题 + bullet”抽取条目
  - 对归一化后的每条生成稳定 `digest`
  - 写入 `ctx._na_memory_recall_meta["prompt_items"]`

### 2. context_window 增加记忆注入账本

涉及：

- `holo_cortex_zero/models/db_context_window.py`
- `holo_cortex_zero/services/context_window/manager.py`

改动：

- `DBContextWindow` 新增 `memory_recall_seen_items_json`
- `ensure_schema_columns()` 启动时自补：
  - `ALTER TABLE "context_window" ADD COLUMN IF NOT EXISTS "memory_recall_seen_items_json" TEXT NOT NULL DEFAULT '[]'`
- 新增 `record_memory_recall_delta(...)`
  - 输入 `prompt_items`
  - 依据 `digest` 去重
  - 只把当前 context 未见过的记忆项写成一条 `msg_type="memory_inject"` 历史消息
  - 文本格式固定为：
    - 第一行 `记忆：`
    - 后续保留原分组标题和 bullet 顺序
  - 成功后更新 `memory_recall_seen_items_json`
  - 失败仅记日志，不中断主回复链

### 3. run_agent_v2 只在顶层用户触发前做一次记忆增量判定

涉及：

- `holo_cortex_zero/services/agent/run_agent_v2.py`

改动：

- 保留原 recall 计算入口。
- 在 recall 返回后，立刻调用 `record_memory_recall_delta(...)`。
- `source_chat_key` 统一取 `context_window.active_dialog_id or chat_key`
- `source_message_id` 固定内部前缀 `memory_recall:*`
- tool 链中间不再重算/重注入动态记忆尾巴

### 4. assembler 去掉尾端 guidance，环境前置

涉及：

- `holo_cortex_zero/services/context_window/assembler.py`

改动：

- 删除 `memory_recall` 参数。
- 删除尾端动态 `guidance user`。
- 组装顺序改为：
  1. `system`
  2. 系统形象参考图
  3. `environment_hint`
  4. `compressed_summary`
  5. `history`
- `memory_inject` 通过历史自然进入 payload，不再作为每轮尾端动态块。

### 5. 历史裁剪 / 清理语义更新

涉及：

- `holo_cortex_zero/services/context_window/manager.py`

改动：

- `get_history()`：
  - 普通历史按窗口限额读取
  - `memory_inject` 全量保留并合并回时间序
  - 不给 `memory_inject` 套 `系统通知。` 前缀
- `enforce_history_hard_limit()`：
  - 只裁非 `memory_inject` 消息
- `_archive_normal_context_history()`：
  - 归档/删除只针对非 `memory_inject`
- `clear_all_message_and_context_records()`：
  - 清消息时同步把 `memory_recall_seen_items_json` 重置为 `[]`
  - 避免“历史清了，账本没清”导致后续不再回注

## 验证

### 静态

- `python3 -m py_compile` 覆盖：
  - `services/memory/runtime.py`
  - `services/memory/context_env.py`
  - `services/memory/auto_memory.py`
  - `services/agent/run_agent_v2.py`
  - `services/context_window/assembler.py`
  - `services/context_window/manager.py`
  - `models/db_context_window.py`

### 函数级

- `record_memory_recall_delta()` 实测：
  - 第一次输入 `1+2`，写入 1 条 `memory_inject`，新增 2 项
  - 第二次输入 `1+3`，仅新增 1 项，即 `3`
- `get_history(limit=1)` 实测：
  - 仍会返回全量 `memory_inject`
  - 普通历史只保留最新 1 条
- `_extract_memory_prompt_items()` 可正确按分组标题和 bullet 切出条目

### payload 排布

- 实测拼装结果不再出现：
  - `**内部System标注`
  - 动态注入版“我不能直球念记忆……”
- `当前环境：...今天星期X，CST+0800` 位于压缩块前
- payload 末尾不再有动态 guidance user

## 影响与边界

- 新记忆只在首次进入该 `context_id` 时落一条内部历史片段。
- `1+2 -> 1+3` 的场景下，不会重复回注 `1`。
- tool 多跳过程不再携带一整块重复动态记忆尾巴。
- `/clear` 或 `/clearall` 后，记忆历史和去重账本都会归零；后续 recall 可重新从头注入。

## 回滚点

- 主要回滚文件：
  - `holo_cortex_zero/services/memory/runtime.py`
  - `holo_cortex_zero/services/memory/context_env.py`
  - `holo_cortex_zero/services/context_window/manager.py`
  - `holo_cortex_zero/services/context_window/assembler.py`
  - `holo_cortex_zero/services/agent/run_agent_v2.py`
  - `holo_cortex_zero/models/db_context_window.py`
- 若需整体撤销，可回退本次功能提交，并删除本历史文档。
