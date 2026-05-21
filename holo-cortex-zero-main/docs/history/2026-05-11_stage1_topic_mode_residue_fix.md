# 2026-05-11 Stage1 topic_mode 残留修复

## 背景
- 2026-05-09 已关闭潜意识 Stage1 对 Mode A/B 的主动判断，不再要求 LLM 输出 `topic_mode` 或调用 `set_stage1_topic_mode`。
- 2026-05-11 14:38:43 运行态出现告警：`[Stage1] 潜意识路由失败，已自动降级为旧注入逻辑: 'NoneType' object has no attribute 'upper'`。

## 定位证据
- 对应请求文件 `v2_request_responses_doubao-seed-2-0-mini-260215_20260511_143840_172737.json` 中：
  - `topic_mode` 出现 0 次。
  - `set_stage1_topic_mode` 出现 0 次。
  - `Mode A` / `Mode B` / `话题模式` / `严肃度` 均出现 0 次。
- 对应响应文件只包含 `append_stage1_intent` tool call，没有返回 `topic_mode`。
- 本地最小复现：`parse_and_validate({"topic_mode": {}, "intents": [...], "cache_updates": {...}})` 会触发 `AttributeError: 'NoneType' object has no attribute 'upper'`。

## 根因
- `_merge_stage1_tool_payloads()` 仍默认注入空 `topic_mode: {}`。
- `parse_and_validate()` 对历史兼容字段 `topic_mode` 的解析仍假设 `mode` 必然存在，直接对 `_ensure_str(... )` 的返回值调用 `.upper()`。

## 修改
- 删除 tool payload 合并结果里的默认空 `topic_mode`，避免当前主干继续制造残留字段。
- 将 `topic_mode.mode` 解析改为空值安全；历史响应里存在空 `topic_mode` 时直接忽略，不影响 `intents / cache_updates` 主干。

## 风险与回滚
- 影响范围：仅 Stage1 tool payload 合并与历史 `topic_mode` 空值解析。
- 当前 Mode A/B 已不再暴露给 LLM，本修复不改变主干输出协议。
- 回滚点：本次 `fix(memory)` 提交。
