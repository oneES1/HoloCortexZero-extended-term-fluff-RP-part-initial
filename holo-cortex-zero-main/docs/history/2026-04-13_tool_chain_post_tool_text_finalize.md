# 2026-04-13 tool 返回后首条纯文本直接完成

## 背景
- tool 链原先在拿到真实 tool 返回后，会对下一轮的首条纯文本 assistant 额外加一道“必须再跑一轮”的门槛。
- 这会导致已经正常生成的人类可见解释文本被延后，甚至在后续轮次里被覆盖，表现为 tool 链中间/收尾文本像是“被吞掉”。
- 本次问题只收口在 tool 链编排状态机，不扩散到语音层、adapter、全局文本清洗或协议兼容层。

## 本次最小修改
- 仅修改 `holo_cortex_zero/services/tools/chain_executor.py`。
- 删除“上一轮已收到真实 tool 返回后，首条纯文本 assistant 不能直接视为完成、必须继续下一轮”的残留逻辑。
- 保留既有主干：
  - 未执行控制平面文本仍然拦截
  - 模型若继续产出真实 `tool_calls`，仍然继续执行
  - tool 副作用、上下文记录、最终回复发送路径保持不变
- 顺手删除对应的暂存状态变量，避免残留僵尸代码继续误导排查。
- 保留 debug 静默日志，用于标识“tool 返回后的首条纯文本已直接作为最终回复发送”，不写入工具轨迹事件，避免正常状态被前端误展示为 Error。

## 结果
- tool 已真实执行且已拿到有效返回后：
  - 如果下一轮是正常纯文本 assistant，直接作为最终回复发送
  - 不再强制多跑一轮
- 如果下一轮仍然是新的 `tool_calls`，tool 链照常继续
- 空结果 after tool 的兜底重试逻辑仍保留，避免模型完全没消费 tool 返回时直接静默结束

## 涉及文件
- `holo_cortex_zero/services/tools/chain_executor.py`
- `docs/2026-04-13_tool_chain_post_tool_text_finalize.md`

## 风险与回滚
- 风险较低：仅影响 tool 返回后的首条纯文本完成判定，不改 tool 执行本身。
- 主要行为变化：原先会被延后一轮的首条纯文本，现在会立即对用户可见。
- 回滚点：恢复 `holo_cortex_zero/services/tools/chain_executor.py` 中 tool 后首条纯文本的强制 follow-up 分支。
