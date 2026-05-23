# 2026-05-10 auto_memory system turn 合并

## 背景

`auto_memory` 请求此前在 `GenerationRequest.messages` 中构造两个连续 system turn：

1. `AUTO_MEMORY_SYSTEM_PROMPT`
2. `_AUTO_MEMORY_BUILTIN_SYSTEM_NOTE`

在 `chat.completions` wire 层会原样发送为两个 system messages；只有 `/responses` 发射器会合并 leading system。为了让 chat 与 responses 的 system 前缀主干一致，并降低缓存前缀分裂风险，本次在业务构造层合并。

## 变更

- `holo_cortex_zero/services/memory/auto_memory.py`
  - `_build_generation_request()` 中将 `AUTO_MEMORY_SYSTEM_PROMPT` 与 `_AUTO_MEMORY_BUILTIN_SYSTEM_NOTE` 用空行合并成一个 system 文本。
  - `turns` 起始只保留一个 `MessageTurn(role="system")`。

## 影响范围

- 只影响 `aux:auto_memory` 的请求消息形状。
- 不改变 system 文案内容。
- 不改变 tools、tool_choice、记忆写入逻辑、阈值逻辑。
- 对 `/responses` 语义基本等价，因为原来 responses 发射器也会合并连续 leading system。
- 对 `chat.completions` 变为一个 system message，更利于稳定前缀缓存与兼容性。

## 验证

```bash
cd /path/to/source-root
python3 -m py_compile holo_cortex_zero/services/memory/auto_memory.py
```

后续运行态可通过 prompt dump 确认：`aux:auto_memory` 请求开头应只有一个 system message。

## 风险与回滚

- 风险低：只合并相邻 system 文本，内容未删除。
- 回滚点：恢复 `_build_generation_request()` 起始的两个 system `MessageTurn`，并删除本文档。
