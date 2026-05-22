# 2026-05-22 memory recall DB seen 同步修正

## 背景

- `run_agent_v2()` 在本轮较早阶段先执行 `sync_new_chat_messages()`。
- 若这一步触发 cutoff，`enforce_history_hard_limit()` 会重建 DB 中 `context_window.memory_recall_seen_items_json`。
- 之后同轮再进入 `record_memory_recall_delta()` 时，不能继续信调用方手里的旧 `window` 账本。

确定性复现链路：

1. cutoff 前旧对象里 `seen = ["digest_A"]`
2. cutoff 后 DB 账本被重建为 `[]`
3. 同轮 recall 又返回 `A`
4. 若 `record_memory_recall_delta()` 仍从旧对象读 seen，就会把 `A` 误判成已见过

## 本次修改

文件：

- `holo_cortex_zero/services/context_window/manager.py`

只改 `record_memory_recall_delta()` 主干：

- 进入事务后先重新读取当前 `DBContextWindow`
- 先把调用者 `window.memory_recall_seen_items_json` 同步成 DB 当前值
- delta 判定严格基于事务内 `db_window` 的账本
- `delta_items=0` 早退前，调用者窗口也已经被同步，不再继续带着旧账本
- 更新 seen 时直接基于本轮事务里已读取的 `seen` 集合扩展

## 影响范围

- 只修 `record_memory_recall_delta()` 的账本读取来源
- 不改 `run_agent_v2.py`
- 不改 recall 定义
- 不改 cutoff 规则

## 验证

静态验证：

- `python3 -m py_compile holo_cortex_zero/services/context_window/manager.py`

可复现预期：

- cutoff 已把 DB seen 从 `["digest_A"]` 重建为 `[]`
- 同轮 recall 再返回 `A`
- `record_memory_recall_delta()` 应按 DB 当前账本判定 `A` 为新项，可继续注入

