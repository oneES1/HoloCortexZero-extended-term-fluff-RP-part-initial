# 2026-04-10 主对话历史中的群聊 `@你；` 作用域收口

## 背景
- 主对话 bot 组装历史时，群聊触发消息上的 `@你；` 会随着 `DBContextMessage.parts_json` 一起进入历史。
- 这会让旧触发消息长期留在主对话历史里，形成额外语义污染。
- 本次边界仅限主对话 bot 的历史显示逻辑，不扩散到存储层、自动记忆、归档、timeline、judge 或其他链路。

## 本次最小修改
- 仅修改 `holo_cortex_zero/services/context_window/manager.py` 的 `get_history()` 读取逻辑。
- 新增显示期规范化规则：
  - 当前锚定是私聊时，主对话历史中不保留任何 `@你；`
  - 当前锚定是群聊时，只保留当前 `active_dialog_id` 下最新一条触发消息的 `@你；`
  - 高级 context 下不在 `@` 逻辑层额外做身份特判，只沿用既有历史角色主干；因此群聊里会自然只保留当前高级 context 真实触发的最新那条 `@你；`
- 不修改 `DBChatMessage`、`DBContextMessage`、`context_notice` 的存储内容，只在主对话历史出库时裁剪。

## 结果
- 普通 context 私聊：无 `@你；`
- 普通 context 群聊：只保留最新触发 `@你；`
- 高级 context 私聊：无 `@你；`
- 高级 context 群聊：自然表现为仅当前高级 context 真实触发的最新消息保留 `@你；`

## 涉及文件
- `holo_cortex_zero/services/context_window/manager.py`
- `docs/2026-04-10_main_dialog_group_notice_history_scope.md`

## 风险与回滚
- 风险较低：只影响主对话历史读取结果，不改数据库。
- 回滚点：恢复 `holo_cortex_zero/services/context_window/manager.py` 中本次新增的历史 `@` 规范化 helper 与 `get_history()` 逻辑。
