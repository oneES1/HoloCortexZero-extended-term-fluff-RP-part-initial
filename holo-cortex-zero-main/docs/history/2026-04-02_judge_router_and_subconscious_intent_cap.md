# 2026-04-02 judge 主干归一与潜意识意图收紧

## 背景

- `ai_reply judge` 切到本地 `qwen35-hcz-resident` 后，现网出现 `empty judge response`。
- 根因是 `ai_reply` 仍直连 `AsyncOpenAI.chat.completions.create(...)`，绕过了项目里已经存在的协议发射器兼容层。
- `subconscious` 当前虽然已走 `chat json-only`，但提示词仍允许 `1~10` 条 intents，运行态也放到 `1024` 输出 token，导致经常产出过长 JSON，延迟偏高。

## 本次修改

### judge

- 文件：`holo_cortex_zero/services/ai_reply/service.py`
- 改为走 `llm_router.generate(...)`，统一复用：
  - 模型组协议判定
  - 本地 resident chat 参数兼容
  - 后续通用 chat / responses 发射器主干
- 保留原有 JSON 解析逻辑，不改业务语义。

### subconscious

- 文件：`holo_cortex_zero/services/memory/subconscious.py`
- 将 Stage1 输出约束从 `1~10 intents` 收紧为 `1~5 intents`。
- 解析阶段再加一层硬兜底：即使模型超额输出，也只保留前 `5` 条合法 intents。
- 不直接靠下砍 `SUBCONSCIOUS_MAX_TOKENS` 来赌截断，优先减少无效输出空间。

## 风险与回滚

- judge 改为主干发射器后，请求链路会更接近其它辅助 LLM；若出现异常，可回滚 `service.py` 到上一个提交。
- subconscious 本轮没有改动记忆检索主逻辑，只是减少 Stage1 单次输出规模；若影响召回广度，可把上限从 `5` 调回更高值。
