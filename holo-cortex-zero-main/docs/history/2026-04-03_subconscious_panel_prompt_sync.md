# 2026-04-03 潜意识面板提示词同步

## 背景

- `SUBCONSCIOUS_SYSTEM_PROMPT` 在运行态配置里拥有最高优先级。
- 之前为避免旧面板提示词继续污染 Stage1 JSON 输出，运行态一度将该项清空，转而回退到代码内默认提示词。
- 本次将已经清洗过的 Stage1 主干提示词正式写回运行态配置，避免后续误以为“面板为空才正常”。

## 本次更新

- 运行态配置 `/path/to/runtime-data/configs/holo-cortex-zero.yaml`
  - 将 `SUBCONSCIOUS_SYSTEM_PROMPT` 从空串改为当前代码中的干净版 `DEFAULT_SYSTEM_PROMPT`。
- 该提示词明确要求：
  - Stage1 只输出 `topic_mode / intents / cache_updates` 结构。
  - `intents` 最多 5 条。
  - 最终输出方式以文末追加的输出规则为准。
  - 不再包含“优先 tool call / 仅网关不支持 tool 时才输出 JSON”这类冲突指令。

## fallback 说明

- 面板/运行态配置 `SUBCONSCIOUS_SYSTEM_PROMPT` 非空时：优先使用它。
- 面板/运行态配置为空时：`subconscious.py` 会回退到本地 `DEFAULT_SYSTEM_PROMPT`。
- 若本地主提示词未来缺失，才再退到 `core.prompt_defaults.DEFAULT_SUBCONSCIOUS_SYSTEM_PROMPT`。
- 本次同步后，正常情况下已经不依赖“配置为空时的回退”才能拿到干净提示词。

## 风险

- 若后续再次在面板里手改旧版提示词，依然会覆盖代码默认值并重新引入污染。
- 因为这里是运行态配置变更，需重载容器后才能确保现行服务全部使用新提示词。
