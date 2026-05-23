# 节日提醒关闭普通私聊通知

## 需求
- 节日提醒不再给普通用户私聊发送。
- 仅保留高级 `context_id` 私聊与群聊通知。

## 问题定位
- 节日提醒目标收集逻辑会遍历所有活跃频道。
- 私聊分支此前只要能解析出当前锚定的 `context_window`，就会纳入发送目标。
- 这会导致普通用户私聊也收到系统节日提醒，不符合当前策略。

## 本次调整
- 在 `holo_cortex_zero/services/festival_service.py` 的节日目标筛选私聊分支增加主干判断。
- 私聊仅当 `owner_type == "advanced"` 时才允许进入节日提醒目标集合。
- 普通私聊直接跳过，并补充明确日志，便于后续排查发送范围。
- 群聊分支、按 `context_id` 去重逻辑、锚定回复窗口逻辑保持不变。

## 影响文件
- `holo_cortex_zero/services/festival_service.py`
- `docs/2026-04-20_festival_reminder_disable_normal_private.md`

## 验证
- `cd /path/to/source-root && python3 -m compileall holo_cortex_zero/services/festival_service.py`

## 风险与回滚点
- 风险：若某些本应视作高级用户的私聊上下文未被正确标记为 `advanced`，本次会一并跳过，不再发送节日提醒。
- 回滚点：回退本次提交即可恢复此前普通私聊也会收到提醒的行为。
