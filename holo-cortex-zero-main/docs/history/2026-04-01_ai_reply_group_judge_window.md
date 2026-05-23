# 2026-04-01 ai_reply 群聊 judge 激活窗口收口

## 背景

群聊 `judge` 之前是“只要消息进来就调用一次 LLM 判断”，即使群已经很久没有主动唤起机器人，也会持续消耗 token。

本次按最小改动收口为：

- 群聊里出现一次主动唤起后，才打开一段可配置的 `judge` 激活窗口
- 激活窗口默认 `1800` 秒（30 分钟）
- 超过窗口后，普通群消息直接跳过 `judge`，不再花这次判断 token
- 显式主动唤起仍然直接触发主流程，不经过 `judge`

## 主链路整理

入口仍在 `holo_cortex_zero/services/message_service.py`：

1. 私聊继续直通，不受本次改动影响
2. 群聊如果命中主动唤起，直接调度 agent，并刷新该群的 judge 激活窗口
3. 群聊如果没有命中主动唤起，则先检查该群 judge 激活窗口是否仍有效
4. 只有窗口有效时，才调用 `holo_cortex_zero/services/ai_reply/service.py` 内的 judge LLM
5. 窗口失效则直接跳过 judge

## 哪些情况会刷新窗口

统一走主干，不给单独来源写并行特化：

- `@` / `is_tome`
- 角色名命中
- `AI_CHAT_TRIGGER_REGEX` 关键词命中
- 系统侧主动调度（`source_scope=system`）
- 显式 `trigger_agent`

## 持久化策略

没有改数据库表结构，避免额外迁移风险。

改为把群聊激活窗口状态持久化到：

- `${APP_SYSTEM_DIR}/ai_reply/group_judge_window.json`

文件内容是 `chat_key -> 最近一次主动唤起 Unix 时间戳`，启动后会继续沿用；过期项会在读取/写入时自动清理。

## 配置项

新增：

- `AI_REPLY_JUDGE_ACTIVE_WINDOW_SECONDS`：默认 `1800`

说明：

- `> 0`：仅在窗口期内允许调用 judge
- `= 0`：恢复旧行为，群聊 judge 始终可调用

## 日志补充

新增日志点：

- 群聊 judge 窗口激活
- 群聊 judge 窗口未开启，跳过 LLM 判断
- 群聊 judge 窗口命中，开始 LLM 判断

## 风险与回滚点

风险较小，改动集中在 ai_reply 和消息分发主链路。

若要快速回滚：

1. 先把 `AI_REPLY_JUDGE_ACTIVE_WINDOW_SECONDS` 设为 `0`
2. 若仍需完全回退，再撤销以下文件改动：
   - `holo_cortex_zero/services/message_service.py`
   - `holo_cortex_zero/services/ai_reply/service.py`
   - `holo_cortex_zero/core/config.py`

## 追加收口

- 当 bot 在群聊实际完成一次回复（含文本影子回复）后，会再次刷新 `judge` 激活窗口；也就是窗口不只由用户主动唤起开启，也会随着 bot 持续参与对话而续期。
