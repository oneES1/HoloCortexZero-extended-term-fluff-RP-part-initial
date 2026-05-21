# 2026-05-09 潜意识 Stage1 Mode A/B 提示关闭

## 背景
- 需求：关闭潜意识 LLM 对 Mode A/B 的主动判断，不再要求 Stage1 输出或传参 mode。
- 约束：不删除 deep / topic_mode 运行态代码，保留后续扩展参考作用。

## 修改
- `holo_cortex_zero/core/prompt_defaults.py`
  - 删除默认潜意识系统提示词里的 Mode A/B 判定段。
  - 输出约束从 `topic_mode / intents / cache_updates` 改为只要求 `intents / cache_updates`。
- `holo_cortex_zero/services/memory/subconscious.py`
  - 删除 Stage1 responses 工具规则里必须调用 `set_stage1_topic_mode` 的要求。
  - 删除 chat JSON 输出规则里必须返回 `topic_mode` 的要求。
  - 删除暴露给 LLM 的 `set_stage1_topic_mode` ToolSpec。
  - 保留 `topic_mode` 解析与运行态透传兼容逻辑，不改 `runtime.py` 与 `run_agent_v2.py` 的 deep 链路。

## 可复现证据
- 搜索提示入口：`rg -n "Mode A|Mode B|话题模式|严肃度|判定 Mode" holo_cortex_zero/core/prompt_defaults.py holo_cortex_zero/services/memory/subconscious.py`
  - 结果应为空。
- 搜索运行态兼容：`rg -n "topic_mode|set_stage1_topic_mode" holo_cortex_zero/services/memory/subconscious.py holo_cortex_zero/services/memory/runtime.py holo_cortex_zero/services/agent/run_agent_v2.py`
  - 仍可看到兼容解析与原 deep 运行态链路，符合“不动这个”。

## 风险与回滚点
- 风险：如果线上配置项 `SUBCONSCIOUS_SYSTEM_PROMPT` 已持久化旧文本，默认 prompt 修改不会覆盖该持久化配置，需要另行清配置。
- 回滚点：本次提交即可整体回退；未修改 Dockerfile、依赖、入口脚本。
