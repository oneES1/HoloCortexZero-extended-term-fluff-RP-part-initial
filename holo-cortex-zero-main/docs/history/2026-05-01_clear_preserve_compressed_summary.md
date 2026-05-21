# /clear 保留高级 context 压缩历史块

## 背景

`/clear` 设计目标是清空当前短期消息记录，并允许 timeline 计数与运行态重置。高级 context 的已落地压缩历史块存放在 `DBContextWindow.compressed_summary`，属于长期压缩上下文，不应被 `/clear` 删除。

## 根因

`ContextWindowManager.clear_all_message_and_context_records()` 在重置 `DBContextWindow` 时同时执行了两处清空：

- `reset_fields` 包含 `compressed_summary`
- 循环内执行 `item.compressed_summary = ""`

这会导致高级 context 在 `/clear` 后丢失已落地压缩历史块。

## 修复

仅修改 `holo_cortex_zero/services/context_window/manager.py` 的 `clear_all_message_and_context_records()`：

- 从 `reset_fields` 移除 `compressed_summary`
- 删除 `item.compressed_summary = ""`
- 保留 `last_compress_version`、`msg_count_since_compress`、`summary_generating`、`pending_summary`、`pending_summary_ready`、`auto_memory_*` 的原有重置逻辑
- 更新函数注释，明确 `/clear` 保留已落地 `compressed_summary`

## 影响范围

未修改以下主干：

- `timeline.py`
- `try_apply_ready_summary()`
- `set_pending_summary()`
- `resolve_context_window()`
- `assembler.py`

因此不阻断任何新总结生成或应用，只禁止 `/clear` 直接清掉已落地压缩块。

## 验证

静态验证目标：`clear_all_message_and_context_records()` 内不再写空 `compressed_summary`，全仓仍仅保留正常压缩/普通归档写入点。
