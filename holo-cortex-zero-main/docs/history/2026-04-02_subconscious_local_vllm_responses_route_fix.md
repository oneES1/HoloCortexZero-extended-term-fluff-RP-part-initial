# 2026-04-02 潜意识本地 vLLM responses 路由修复

## 背景

- 主聊天链路在未显式指定传输协议时，默认可走 `responses` 主干。
- `Stage1 subconscious` 自己维护了一份协议判定，但兜底默认值仍是 `chat`。
- 当潜意识模型组切到本地 `vllm` 组后，即使 `holo_cortex_zero/services/llm/responses.py` 已有本地 `vllm` 兼容逻辑，潜意识链路也不会命中该发射器。

## 本次修改

- `holo_cortex_zero/services/memory/subconscious.py`
  - 调整 `_detect_subconscious_protocol()` 的主干兜底策略。
  - 保持 `gemini`、显式 `CACHE_TRANSPORT_PROFILE` / `wire_api`、已知兼容分支判定不变。
  - 仅将“无显式 hint 且未命中特殊分支”时的默认返回值从 `chat` 改为 `responses`。

## 影响说明

- 只影响 `Stage1 subconscious` 的协议选择。
- 已显式配置 `wire_api=chat` 或其他 transport hint 的模型组不受影响。
- 未显式写传输 hint 的潜意识模型组，会与主聊天链路保持一致，默认接入 `responses` 发射器主干。
