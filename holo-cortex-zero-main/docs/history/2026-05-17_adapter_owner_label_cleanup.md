# 2026-05-17 adapter owner label cleanup

## 背景

适配器配置页存在面向用户不够直观的字段名：

- OneBot `机器人 QQ 号` 被标为必填，前端显示红星。
- OneBot owner 字段显示为 `Owner QQ User ID`。
- Telegram owner 字段显示为 `Owner TG User ID`。
- Matrix owner 字段显示为 `Owner Matrix User ID`。

## 修改

- 移除 OneBot `BOT_QQ` 的 `required=True` schema 标记，只保留字段本身。
- OneBot `OWNER_QQ_USER_ID` 标题改为 `你的QQ ID`。
- Telegram `OWNER_TG_USER_ID` 标题改为 `你的 TG ID`。
- Matrix `OWNER_MATRIX_USER_ID` 标题改为 `你的 Element(Matrix客户端) ID`。

## 验证

- `uv run python -m py_compile holo_cortex_zero/adapters/onebot_v11/adapter.py holo_cortex_zero/adapters/telegram/config.py holo_cortex_zero/adapters/matrix/config.py`

## 风险与回滚

- 仅调整配置 schema 展示标题和 OneBot 机器人 QQ 号必填标记，不改运行期身份映射。
- 回滚点：撤销本文件和三个 adapter config 文件的对应改动。
