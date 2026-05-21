# 2026-04-06 `/responses` 连续前置 system 合并修复

## 问题

- 本地 `vLLM /responses` 链路对 `role=system` 的位置校验更严格。
- 当上游 IR 在开头连续放入多条 `system` turn 时，HCZ 原先会原样序列化到 `/responses` payload。
- 自动记忆链路 `auto_memory` 恰好会在开头放两条 `system`：主 system prompt + 内置 system note。
- 现场报错：`System message must be at the beginning.`

## 原因

- `/responses` 发射器此前只做逐条映射，不会折叠连续前置 `system`。
- 对某些 OpenAI-compatible `/responses` 实现而言，虽然两条 `system` 都在最前面，但仍会把第二条视作非法位置。

## 修复

- 修改 `holo_cortex_zero/services/llm/responses.py`
- 在 `/responses` 主干增加连续前置 `system` 折叠：
  - 仅折叠**开头连续**的 `system` turns
  - 保持上层 IR 与调用方不变
  - 统一在 emitter 主干完成，不为 `auto_memory` 或某个供应商单独分叉

## 影响

- `auto_memory` 这类“多条前置 system”请求会被发射器合并成单条首位 `system message`
- 其他 `/responses` 调用若本来只有一条或没有前置 `system`，行为不变
- 非 `/responses` 协议不受影响

## 回滚点

- 本次改动仅涉及 `holo_cortex_zero/services/llm/responses.py`
- 若需回滚，优先回退本次 `fix(llm): merge leading system turns for responses payload`
