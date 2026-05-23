# 2026-04-10 自设图直传路径仅高级 context 注入

## 现象

普通用户对话里也可能拿到自设图三张参考图路径，且路径作为纯文本直接拼进 system prompt，不符合预期边界。

## 根因

`holo_cortex_zero/services/agent/run_agent_v2.py` 中 `_get_self_image_data()` 只判断了 `SELF_IMAGE_ENABLE_DIRECT_PATH_PROMPT`，没有读取当前上下文窗口的 `owner_type`。

## 修改

- 保持印象图注入逻辑不变。
- 仅当 `owner_type == "advanced"` 时导出三张参考图路径。
- 普通用户在 `SELF_IMAGE_ENABLE_DIRECT_PATH_PROMPT=true` 下也不再注入路径，并补充日志说明跳过原因。

## 影响范围

- 高级 context：仍注入三张参考图路径。
- 普通 context：不注入路径，其他 prompt 结构不变。

## 风险与回滚点

- 风险很小，仅收紧路径提示注入边界。
- 如需回滚，只需恢复 `holo_cortex_zero/services/agent/run_agent_v2.py` 中 `allow_direct_path_prompt` 这段判断。
