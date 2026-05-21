# 2026-04-02 潜意识协议绑定输出模式

## 背景

- 潜意识 Stage1 之前共用一套混合提示词：主干优先 tool，失败再回退 JSON。
- 这种写法虽然能跑，但 `chat` 链路实际上只是因为不发 tools 才被迫走 JSON，语义不够清晰。
- 当前模型组已经支持显式传协议，因此 Stage1 也应直接按协议绑定输出模式，而不是继续依赖隐式 fallback。

## 本次修改

- `holo_cortex_zero/services/memory/subconscious.py`
  - 新增输出模式概念：`tool` / `json`。
  - `protocol=responses` 时，Stage1 只走 tool call 主干，不再跨协议回退到 JSON。
  - `protocol=chat` 时，Stage1 只走一行 JSON 主干，不再先打一遍 tool-first。
  - `build_subconscious_prompt()` 按输出模式生成不同规则：
    - `responses -> tool-only`
    - `chat -> json-only`
- 运行态配置
  - 本地 `qwen35-hcz-resident` 只保留显式 `wire_api=chat` 与 `thinking={type:disabled}`。
  - 删除多余的 `skip_native_tools` 控制字段，避免继续依赖隐式行为。

## 预期效果

- 潜意识协议与输出模式一一对应：
  - `chat = JSON`
  - `responses = tool`
- 模型组显式传协议即可决定 Stage1 主干，不再靠“不给工具逼 fallback”。
- 调试与日志语义更清晰，后续切换模型组时也更可控。
