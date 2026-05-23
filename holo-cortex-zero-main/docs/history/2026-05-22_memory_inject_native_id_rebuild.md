# 2026-05-22 memory_inject native-id rebuild

## 摘要

本次只收敛到记忆回填主干：

- `memory_inject` 改为只按原生 memory `id` 去重
- 删除 `recall_text` 反解析、`parts_json` 反解析、`sha1(text)` 去重链
- 普通 context 仅在 recall 真重算轮允许写入 `memory_inject`
- 高级 context 保持每轮 recall 都可增量写入
- 阈值清理后，`memory_recall_seen_items_json` 只按 surviving `memory_inject.memory_digests_json` 重建
- `auto_memory` 的 recall_text 来源与缓存链保持不变

## 修改文件

- `holo_cortex_zero/services/memory/runtime.py`
- `holo_cortex_zero/services/agent/run_agent_v2.py`
- `holo_cortex_zero/services/context_window/manager.py`
- `holo_cortex_zero/models/db_context_window.py`

## 关键行为

### 1. runtime 结构化导出

`inject_memory_prompt()` 不再从最终 recall 文本回推 `prompt_items`。

现在只从真实 mem0 item 抽取这 5 个字段：

- `memory_id`
- `user_id`
- `time_text`
- `text`
- `confidence`

四条 recall 来源都走同一结构化链：

- Stage2 static
- Stage2 intent/context
- legacy static
- legacy dynamic/context

### 2. run_agent_v2 回填门控

`_collect_memory_recall_for_context()` 现在返回：

- `memory_recall_text`
- `memory_recall_meta`
- `recall_recomputed`

约束：

- 高级 context：`recall_recomputed = true`
- 普通 context 首轮/刷新轮：`recall_recomputed = true`
- 普通 context 缓存轮：`recall_recomputed = false`

主流程只在：

- `recall_recomputed = true`
- 且 `prompt_items` 非空

时调用 `record_memory_recall_delta()`。

### 3. manager 去重与账本

`record_memory_recall_delta()` 现在只接受结构化 `prompt_items`，不再吃 `recall_text` 兜底。

去重规则：

- 当前条内去重：原生 `memory_id`
- 当前 context 账本去重：原生 `memory_id`

展示格式固定为：

- `ID 的记忆（日期时间 记忆文本 置信（CONFIDENCE））`
- 同 user 多条：`，` 串接
- 多 user：按首次出现顺序换行

只允许进入展示文本的字段：

- `user_id`
- `time_text`
- `text`
- `confidence`

### 4. cutoff / archive / apply-summary 后的账本重建

三条清理路径统一为：

1. 删 regular history
2. 删 `memory_anchor_context_msg_id <= cutoff_chat_msg_id` 的 `memory_inject`
3. 将 `memory_recall_seen_items_json` 逻辑清空为 `[]`
4. 仅按 surviving `memory_inject.memory_digests_json` 重建最终账本

覆盖路径：

- `_archive_normal_context_history(...)`
- `enforce_history_hard_limit(...)`
- `try_apply_ready_summary(...)`

## 实证验证

### 静态编译

执行：

```bash
cd /home/ubuntu/hcz-deploy/holo-cortex-zero-main
uv run python -m py_compile \
  holo_cortex_zero/services/memory/runtime.py \
  holo_cortex_zero/services/agent/run_agent_v2.py \
  holo_cortex_zero/services/context_window/manager.py \
  holo_cortex_zero/models/db_context_window.py
```

结果：通过。

### 容器内数据库级验证

使用容器内真实代码路径执行针对性脚本，验证结果如下：

- 结构化字段白名单：
  - `normalized_keys = ["confidence", "memory_id", "text", "time_text", "user_id"]`
  - 混入的 `hash / TYPE / foo / score` 未进入结果
- 单用户展示：
  - `541955254 的记忆（2026-05-22 12:00:00 喜欢可乐 置信（HIGH）），（2026-05-22 12:05:00 喜欢雪碧 置信（VERY_HIGH））`
- 多用户展示：
  - `100 的记忆（2026-05-22 12:00:00 A 置信（HIGH）），（2026-05-22 12:02:00 C 置信（MEDIUM））`
  - `200 的记忆（2026-05-22 12:01:00 B 置信（LOW））`
- 普通 context recall 门控：
  - 首轮 `recomputed = true`
  - 第二轮 `recomputed = false`
  - collector 实际只调用 1 次
  - 第二轮 `prompt_items = null`
- 相同文本不同 ID：
  - 首次 `delta_count = 2`
  - 同一 `memory_id` 仅展示变化后再次提交：`delta_count = 0`
- 三条清理路径在 `cutoff_chat_msg_id = M2` 场景下均验证通过：
  - cutoff 后 surviving 仅剩 `memC`
  - `memory_recall_seen_items_json == ["memC"]`
  - 下一轮 recall 再次出现 `memA` 时，允许重新注入
  - 注入后账本变为 `["memA", "memC"]`

## 禁令保持

本次没有引入：

- 文本 hash 去重
- `parts_json` 反解析
- `recall_text` fallback
- 额外 metadata 展示污染
- 新的 auto_memory recall 缓存
