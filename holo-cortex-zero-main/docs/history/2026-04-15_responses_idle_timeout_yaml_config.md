# 2026-04-15 `/responses` 空闲超时放宽并改为 YAML 可配置

## 背景
- 当前主聊天链里的 `Uni-grok` 模型组显式配置为 `WIRE_API: responses`，因此超时问题实际命中的是通用 `/responses` 主干，而不是某条 Grok 特化分支。
- 之前 `/responses` 流式空闲超时常量写死为 `30s`，对部分首字慢、事件间隔偏长的上游来说偏紧。

## 本次修改
- 在 `holo_cortex_zero/core/config.py` 新增全局配置项：`LLM_RESPONSES_STREAM_IDLE_TIMEOUT_SECONDS`
  - 默认值：`50`
  - 含义：通用 `/responses` 主干在流式传输时，连续多长时间没有新事件就判定为空闲超时
- 在 `holo_cortex_zero/services/llm/responses.py` 中将 `/responses` 主干读取该配置
  - 默认回退值同步调为 `50s`
  - 对本地 vLLM 目标仍保持原有逻辑：idle timeout 跟随 total timeout，不受该配置影响
  - 实际生效时仍会被 `total_timeout` 上限裁剪，避免配置值大于总超时
- 在运行时配置 `/path/to/runtime-data/configs/holo-cortex-zero.yaml` 中加入：
  - `LLM_RESPONSES_STREAM_IDLE_TIMEOUT_SECONDS: 50`

## 影响范围
- 影响所有走通用 `/responses` 主干的模型组，不只 Grok
- 不新增任何 Grok 专属并行链路，保持主干统一
- `uni-qwen` 的强制非流式分支不受这次修改影响

## 风险
- 空闲等待从 `30s` 放宽到 `50s` 后，真正卡住时的失败返回会更晚一些
- 但总超时主干仍维持现状，因此不会无限等待

## 回滚点
- 回滚代码提交即可恢复旧行为
- 或仅将 YAML 中 `LLM_RESPONSES_STREAM_IDLE_TIMEOUT_SECONDS` 改回 `30`
