# 节假日提醒按 context_id 收口修复

## 问题定位
- 节假日提醒此前按活跃对话窗口 `active_dialog_id/chat_key` 收集目标，而不是按逻辑上下文 `context_id` 收集。
- 这会让高级用户在存在 TG/QQ 多个历史私聊窗口时，被节假日提醒按不同窗口重复扫描，出现 TG 和 QQ 都触发的问题。
- 主干设计里，高级用户应固定复用同一个 `context_id`，`active_dialog_id` 只负责回复落点；节假日提醒应先按 `context_id` 确认权威上下文，再落到当前锚定窗口。

## 本次调整
- 保留群聊原有的“同一对话窗口命中多个上下文时优先高级上下文”逻辑，避免同一群里重复发两份提醒。
- 对私聊改为先读取该私聊最近一条人类消息，按当前主干路由重新解析权威 `context_id`，不再直接信任历史窗口残留。
- 仅当该权威上下文的 `active_dialog_id` 仍然指向当前私聊窗口时，才把该窗口纳入节假日提醒目标。
- 最终对节假日提醒目标按 `context_id` 再做一次去重，确保同一逻辑上下文只触发一次。

## 影响文件
- `holo_cortex_zero/services/festival_service.py`
- `docs/2026-04-05_festival_reminder_context_binding_fix.md`

## 验证
- `cd /path/to/source-root && python -m compileall holo_cortex_zero/services/festival_service.py`

## 风险与回滚点
- 风险：私聊若没有任何历史人类消息，节假日提醒现在会明确跳过该窗口，而不是继续信任可能失真的历史上下文残留。
- 回滚点：本次提交完成后可直接按提交哈希回退。
