# Telegram Bot Token 帮助按钮

## 背景

Telegram 适配器配置里只有 `BOT_TOKEN` 输入项，小白用户不知道该去哪里找 Bot Token。用户要求不要写成独立文档，形式参考 `seek` / `weather` 的配置项帮助按钮。

## 修改

- 在 `TelegramConfig.BOT_TOKEN` 字段元数据里补充 `help_label` / `help_text`。
- 帮助内容说明通过官方 `@BotFather` 创建 Bot、复制 Token、粘贴配置、重启后端并发送 `/start` 测试。
- 保持 `BOT_TOKEN` 的 `is_secret=true`，WebUI 仍按密钥字段处理。

## 验证

- `uv run python -m compileall holo_cortex_zero/adapters/telegram/config.py` 成功。
- `uv run python` 验证 `BOT_TOKEN` 字段包含：
  - `help_label=获取 Token 指南`
  - `help_text` 包含 `@BotFather` 和 `/newbot`
  - `is_secret=True`

## 风险与回滚

- 风险：仅新增配置项帮助文案，不改变 Telegram 适配器初始化、收发消息、TG 私聊伪装路由或代理逻辑。
- 回滚点：回退本次提交即可移除 Telegram Token 帮助按钮。
