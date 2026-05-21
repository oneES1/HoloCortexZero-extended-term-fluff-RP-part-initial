# 2026-05-02 上下文尾部顺序修正

## 问题

主链请求中，最新聊天消息会先同步进 `DBContextMessage`，随后 `ContextAssembler.assemble()` 读取历史并追加回忆与环境标注。

原尾部顺序实际变成：

1. 最新用户真实消息
2. 内部System标注 / 记忆 / 环境注入

这会让内部注入块成为 `messages[-1]`，抢占最新用户真实输入的压轴位置。

## 调研事实

- `run_agent_v2()` 在模型调用前执行 `sync_new_chat_messages()`。
- `sync_new_chat_messages()` 按时间正序注入新聊天消息。
- `get_history()` 按上下文消息 ID 正序返回历史。
- `openai_chat`、`responses`、`router` 均保持 `GenerationRequest.messages` 顺序，不应在协议层特化修复。

## 修改

只修改 `holo_cortex_zero/services/context_window/assembler.py` 的 `ContextAssembler.assemble()`：

- 当 `history[-1]` 是 `role == "user"` 且 `parts` 非空时，临时取出最后一条用户 turn。
- 先追加其余历史。
- 再追加回忆与环境标注 turn。
- 最后追加这条用户 turn。
- 当历史为空或最后一条不是 user turn 时，保持原顺序兜底。

## 验收

有最新用户真实消息时：

- `messages[-2]` 为内部System标注 / 记忆 / 环境注入。
- `messages[-1]` 为最新用户真实消息。

非 user 尾部时：

- 不重排，避免破坏 assistant / tool 序列。

## 验证

- `python3 -m py_compile holo_cortex_zero/services/context_window/assembler.py`
