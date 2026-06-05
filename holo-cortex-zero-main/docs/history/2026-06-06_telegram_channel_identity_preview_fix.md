# Telegram channel identity preview 修复

## 背景

Telegram 更新处理链路出现运行时异常：

```text
'TelegramAdapter' object has no attribute '_get_channel_id'
```

该异常发生在附件策略与引用上下文进入共享 identity preview 前，导致对应 Telegram 更新无法继续处理。

## 根因

`MessageProcessor._preview_canonical_attachment_identity()` 调用了 `TelegramAdapter._get_channel_id(message.chat)`。

证据：

- `TelegramAdapter` 没有 `_get_channel_id` 方法。
- Telegram 入站主线已经在 `PlatformChannel.channel_id` 使用 `private_<id>` / `group_<id>` 格式。
- `TelegramAdapter.build_chat_key(chat)` 已公开生成 `telegram-private_<id>` / `telegram-group_<id>`。
- `TelegramAdapter.parse_chat_key(chat_key)` 已公开解析出同一 `channel_id`。

问题不是 Telegram 协议差异，也不是附件策略本身，而是调用了不存在的私有辅助方法。

## 修复原则

- 不新增 Telegram 私有分支方法。
- 不改共享 identity 主干。
- 沿用适配器公开的 chat key 构造与解析规则。
- 只替换错误调用点，保持行为最小变化。

## 改动

- `holo_cortex_zero/adapters/telegram/message_processor.py`
  - 将不存在的 `_get_channel_id(message.chat)` 调用替换为：

```python
_, raw_channel_id = self.adapter.parse_chat_key(self.adapter.build_chat_key(message.chat))
```

该写法复用 Telegram 适配器现有主线规则，得到的 `raw_channel_id` 与入站 `PlatformChannel.channel_id` 保持一致。

## 验证

已执行：

```bash
rg -n "_get_channel_id" holo_cortex_zero/adapters/telegram -g '!*.log'
git diff --check
python3 -m py_compile holo_cortex_zero/adapters/telegram/message_processor.py
```

结果：

- 未发现 `_get_channel_id` 残留调用。
- diff 空白检查通过。
- 目标文件编译通过。
