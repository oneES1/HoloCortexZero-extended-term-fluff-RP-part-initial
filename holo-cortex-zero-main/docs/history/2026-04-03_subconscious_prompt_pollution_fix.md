# 2026-04-03 subconscious 提示词污染修正

## 背景

- `subconscious` 已经按协议区分为：
  - `chat -> json-only`
  - `responses -> tool-only`
- 但 `DEFAULT_SYSTEM_PROMPT` 主体里仍残留“优先走 tool call”“通过 set_stage1_topic_mode 返回”等老文案。
- 这会和 `chat/json-only` 路径的末尾输出规则发生自相矛盾，导致模型有概率混出 tool 语义、JSON 包装噪声或并行格式残留。

## 本次修正

- 文件：`holo_cortex_zero/services/memory/subconscious.py`
- 只修提示词主干，不动解析逻辑：
  - 把 `topic_mode` 描述改成协议无关的结果字段语义
  - 把“硬性输出约束”改成协议无关表述
  - 明确声明：最终输出格式以文末追加的 `【输出方式】规则` 为准
- 保留 `chat/json-only` 与 `responses/tool-only` 的分支规则入口不变，由 `output_mode` 追加

## 预期效果

- `chat` 路径不再被提示词主干污染成 tool-first 心智
- `responses` 路径仍可通过末尾追加规则稳定产出 tool calls
- 若之后仍有解析失败，再针对格式噪声补通用兜底，而不是先放松业务语义约束
