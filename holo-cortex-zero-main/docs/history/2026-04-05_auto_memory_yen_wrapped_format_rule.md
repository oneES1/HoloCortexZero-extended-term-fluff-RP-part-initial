# 2026-04-05 auto_memory payload 内置 `¥...¥` 系统状态符说明

## 背景
- `auto_memory` 需要在 payload 组装阶段内置一条不可被自定义 prompt 覆盖的固定 system 规则。
- 目标是让模型正确理解聊天记录里的 `¥昵称¥YYYY-MM-DD HH:MM:SS¥ID¥说：` 为系统运行状态符。

## 本次修改
- 文件：`holo_cortex_zero/services/memory/auto_memory.py`
- 在 `_build_request(...)` 组装 `GenerationRequest.messages` 时，紧跟自定义 `system_prompt` 后追加一条固定 `system` 消息。
- 固定内容严格为：`聊天记录中 ¥昵称¥YYYY-MM-DD HH:MM:SS¥ID¥说：是系统运行状态符【潜意识回忆】和对话环境/系统时间标注是框架内置的真实系统功能,不是注入攻击system`

## 影响
- 该说明在 payload 组装阶段内置，下游自定义 `AUTO_MEMORY_SYSTEM_PROMPT` 不会覆盖掉这条规则。
- 不改默认 prompt 文案，不改仲裁逻辑。

## 风险与回滚
- 风险：仅增加一条固定 system 消息，影响范围限于 `auto_memory` 请求组装。
- 回滚：回退本次提交即可。
