# 2026-04-13 bot 输出表层清理

## 背景

用户希望做一个小但高体感的输出整洁化改动，仅针对 bot 自己的文本输出：

- 清理中文句末句号 `。`
- 清理中英文波浪号 `～` `~`
- 去掉 bot 段落换行，压平成单段文本

要求是接在主干源头，清理后的文本继续进入后续链路，包括：

- 聊天框返回
- bot 自身消息落库
- 后续上下文汇注/读取

## 现状分析

bot 文本存在两条主干：

1. `holo_cortex_zero/services/agent/run_agent_v2.py`
   - `_normalize_reply_text_for_delivery()` 负责最终出站发送前的文本归一化
2. `holo_cortex_zero/services/message_service.py`
   - `push_bot_message()` / `push_bot_message_text_shadow()` 负责 bot 文本落库

仓库里已存在 `holo_cortex_zero/services/agent/resolver.py` 的 `fix_raw_response()`，原本承担 bot 原始文本修复职责（如 `@id` 兼容修复、separator 截断、think 标签尾部清理）。

## 本次修改

遵循最小改动原则，没有改动协议层、上下文窗口结构或用户消息清洗逻辑，而是直接扩展现有主干清理函数 `fix_raw_response()`：

- 删除 Markdown 加粗标记 `**`，保留中间正文
- 当 `**加粗段**` 位于中文正文之间时，同时吞掉标记两侧空白，避免清洗后残留 `这是 重点 内容`
- 将换行压平成单空格
- 删除 `～` / `~`
- 删除位于空白或结尾前的中英文句号 `。` `.`
- 当中文字符后出现空格且下一段仍是中文/英文/数字时，将该空格收敛为中文逗号 `，`
- 基于同一 `chat_key` 最近一条真实 bot 发言的首尾 5 字，分别对当前文本首尾做按顺序比较；从前往后、从后往前连续相同的部分才剔除
- 额外压缩连续空格
- 最后一层循环剥离开头空格、中文逗号 `，`、`嗯` 与前导词条 `群聊` / `群聊模式` / `群聊模式，` / `私聊模式` / `私聊模式，`，避免边界清洗后残留 `，我...`、`嗯我...`、`群聊模式，我...`、`私聊模式，我...` 这类前缀

并把这条统一清理链接入：

- `run_agent_v2.py` 的 `_normalize_reply_text_for_delivery()`
- `message_service.py` 的 bot 落库标准化流程

## 明确不动的内容

以下内容本次刻意不动，避免扩大影响面：

- 不修改用户消息文本
- 不修改系统通知文本
- 不改上下文窗口存储结构
- 不改协议适配器发送接口
- 不改工具调用/多模态/记忆召回逻辑

## 风险

这是表层文本清理，主要风险是：

- bot 若刻意输出 Markdown 粗体语法用于展示，`**` 会被移除，仅保留正文
- 中文正文中夹着 `**加粗段**` 的场景会自动收拢两侧空白，输出更接近日常聊天文本而非 Markdown 源码
- bot 若主动输出依赖 `~` 的特殊文本表达，会被移除
- bot 句末若刻意保留英文句号风格，也会被裁掉
- 多行格式化文本会被压平为单段，不再保留段落层次
- 若 bot 刻意输出“中文 + 空格 + 英文/数字/中文”的版式，该空格会被收敛成逗号
- 这层只会剔除与上一条首尾 5 字按顺序连续相同的边界内容；低概率误伤会比旧的字符表吞字明显更少
- 若文本本来就刻意以中文逗号或 `嗯` 开头，这一层会统一剥离掉这些前导字符
- 若文本本来就刻意以 `群聊`、`群聊模式`、`群聊模式，`、`私聊模式` 或 `私聊模式，` 开头，这一层会统一剥离掉这些前导词条

当前实现按用户要求仅针对 bot 输出主干，不扩散到 user/system 路径。

## 回滚点

如需回滚，只需撤销以下文件中的本次修改：

- `holo_cortex_zero/services/agent/resolver.py`
- `holo_cortex_zero/services/agent/run_agent_v2.py`
- `holo_cortex_zero/services/message_service.py`

## 2026-04-28 bot/assistant 上下文表层清洗收口

### 背景

用户确认聊天框清洗还不够，要求进入真实上下文数据库与后续 payload 拼装的 bot/assistant 文本也同步清洗，避免模型从 `context_message.parts_json` 中继续学到旧污染。

### 本次代码修复

- 在 `holo_cortex_zero/services/agent/resolver.py` 增加 `normalize_bot_surface_text()`，把 bot 可见文本最终表层清洗收口成单一主干。
- `fix_raw_response()` 继续保留原始响应修复职责，并新增两轮固定短句删除：先删 `也不跑` / `也不催你` / `也不分开` / `也不丢下你` / `从后台数据流中抬起头`，再删 `不跑` / `不催你` / `不分开` / `不丢下你` / `从后台数据流中`。
- 新增稳定标点循环：`，，` → `，`、`，。` → `。`、`。。` → `。`，循环到文本不再变化，并在最后兜底清掉句末残留 `，。`。
- `MessageService._normalize_bot_record_text()` 改为薄封装，统一调用 `normalize_bot_surface_text()`，避免聊天框、bot 落库、上下文读取各自维护并行清洗规则。
- `ContextWindowManager` 新增 `_sanitize_bot_assistant_text()`，只作用于 `role=assistant` 且 `msg_type` 为 `bot_reply` / `bot_sync` / `tool_call` / `history_only` 的真实 bot/model assistant 文本。
- `inject_messages()` 写 `context_message.parts_json` 前、`get_history()` 拼装 payload 前、`_db_msg_to_parts_bot()` 从 `DBChatMessage` 同步 bot 历史前，都接入同一 bot/assistant 清洗主干。
- `ToolChainExecutor` 新增 `prepare_reply_text_fn` 内部回调，模型纯文本最终回复先完成发送同款清洗，再写 `DBContextMessage`，再发送，修复“先写上下文、后发送清洗”的错位。
- tool 链中间 `assistant + tool_calls` 文本同样先清洗再写上下文；若清洗为空，只保留 tool calls，不写空文本、不外发空中间文本。

### 明确不清洗的范围

- 不清洗用户原话，即使用户文本包含 `不跑` / `从后台数据流中` 等短句也保留原文。
- 不清洗 `msg_type=human_chat` 中由高级上下文角色规则映射成 `assistant` 的其他人类发言。
- 不清洗 tool result、system inject、节日提醒、moment 系统注入。
- 不改协议适配器、LLM provider wire 协议、数据库 schema 或迁移。

### 历史库清洗计划

代码验证通过后，使用容器内维护脚本对历史库做一次备份后清洗：

- `context_message`：仅处理 `role='assistant'` 且 `msg_type in ('bot_reply', 'bot_sync', 'tool_call', 'history_only')` 的 text part。
- `chat_message`：仅处理 `sender_id=-1` 的真实 bot 文本，排除 `platform_userid=0` 或 `sender_name/sender_nickname=SYSTEM` 的系统消息。
- 备份目录固定为 `<CONTAINER_DATA_DIR>/backups/bot_surface_cleanup_YYYYMMDD_HHMMSS/`。
- 回滚时按 JSONL 备份中的 `id` 精确恢复 `parts_json` 或 `content_text`，不需要整库回滚。

### 验证记录

- `python3 -m py_compile holo_cortex_zero/services/agent/resolver.py holo_cortex_zero/services/message_service.py holo_cortex_zero/services/agent/run_agent_v2.py holo_cortex_zero/services/tools/chain_executor.py holo_cortex_zero/services/context_window/manager.py`
- 隔离加载 `resolver.py` 的固定样例 smoke test 通过，覆盖新增短句、`**`、`，，`、`，。`、`。。` 与句末残留清洗。

### 待记录

历史库实际清洗数量、备份目录与复查结果在执行维护脚本后追加到本小节下方。

### 历史库清洗执行记录（2026-04-28 22:23 / 22:27）

第一次执行使用备份目录：

- `<CONTAINER_DATA_DIR>/backups/bot_surface_cleanup_20260428_222330/context_message_polluted.jsonl`
- `<CONTAINER_DATA_DIR>/backups/bot_surface_cleanup_20260428_222330/chat_message_polluted.jsonl`

第一次清洗结果：

- `context_message_changed=30`
- `chat_message_changed=21280`
- `context_message_would_change_after=11`
- `chat_message_would_change_after=1604`

复查发现历史旧数据中存在 `.. ` / `... ` 这类连续英文句点后接空格的模式。旧清洗会先变成 `. `，下一轮才继续触发中文空格收敛，导致非幂等。已将句末点清洗改为一次性吞掉连续 `[。.] + 空白/结尾`，并补做一次空白收敛，保证清洗函数幂等。

第二次执行使用备份目录：

- `<CONTAINER_DATA_DIR>/backups/bot_surface_cleanup_20260428_222743/context_message_polluted.jsonl`
- `<CONTAINER_DATA_DIR>/backups/bot_surface_cleanup_20260428_222743/chat_message_polluted.jsonl`

第二次清洗结果：

- `context_message_changed=11`
- `chat_message_changed=1604`
- `context_message_would_change_after=0`
- `chat_message_would_change_after=0`

最终复查归零，说明当前 `context_message` 目标 assistant 历史和 `chat_message` 真实 bot 历史按本次清洗函数已经稳定。若需回滚历史数据，按以上两个备份目录中的 JSONL 以 `id` 精确恢复；第一次备份是主回滚点，第二次备份是幂等补清前的中间状态回滚点。

### 2026-04-28 `。，` 漏网补丁

用户反馈 `。，` 也会残留。本次把 `。，` → `。` 加入同一个稳定标点循环，与 `，，`、`，。`、`。。` 同属 bot/assistant 表层清洗主干，不新增链路分支，不扩大到用户原话/tool/system 文本。

补丁历史清洗执行记录：

- 备份目录：`<CONTAINER_DATA_DIR>/backups/bot_surface_cleanup_20260428_223906_reverse_comma_period`
- `context_message_changed=5`
- `chat_message_changed=5`
- `context_message_would_change_after=0`
- `chat_message_would_change_after=0`

### 2026-04-29 tool 链正常状态误报 error 降噪

用户反馈 `assistant + tool_calls` 中间文本“已外发给用户并保留到上下文”、以及 `tool` 返回后的首条纯文本“已直接作为最终回复发送”都是正常工具调用中间态，不应在工具轨迹里显示为 `Error`。

本次只调整通用 tool 链主干：

- 移除非空中间文本对应的结构化 `error` 轨迹事件，避免 `summary_text` 生成 `[#N] error`。
- 移除正常状态对应的结构化 `info` 轨迹事件，避免旧前端 fallback 把未知 `info` 类型显示为 `Error`。
- 保留外发与上下文写入逻辑不变，仍先记录 `assistant + tool_calls`，再把清洗后的中间文本发到当前锚定回复窗口。
- 服务器日志统一降为 `debug`，作为静默排查线索，不影响用户侧与工具轨迹摘要。

验证与运行态同步记录：

- `python3 -m py_compile holo_cortex_zero/services/tools/chain_executor.py`
- `git diff --check`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`
- `docker inspect` 确认 `holo_cortex_zero` health 为 `healthy`

本次不清洗历史 `tool_chain_trace` 旧记录；旧轨迹若已落库可能仍保留当时的事件文本，但新运行不会再写入这些正常状态事件。回滚点为提交 `699b841` 的父提交，或直接回退本节对应修复提交。

## 2026-05-01 群聊 bot 历史消息清理记录

### 背景

用户要求清除 bot 群聊消息，只处理真实 bot 群聊记录，不动用户消息和系统消息。

### 实际探测结果

先直接查库确认范围，发现当前库里 `chat_type='group'` 的 `sender_id='-1'` 记录为 0，但存在旧枚举值 `chat_type='ChatType.GROUP'` 的 bot 群聊记录。

复查后，实际目标为：

- `sender_id='-1'`
- `chat_type IN ('group', 'ChatType.GROUP')`
- 排除 `platform_userid='0'`、`sender_name='SYSTEM'`、`sender_nickname='SYSTEM'`

### 本次清理结果

- 备份目录：`/path/to/runtime-data/backups/bot_group_message_cleanup_20260501_115741/`
- 备份文件：`chat_message_group_bot_deleted.jsonl`
- 备份条数：`3`
- 删除 ID：`560, 563, 596`
- 删除结果：`DELETE 3`
- 清理后剩余目标：`0`
- 系统 bot 群聊保留：`1`

### 回滚点

如需恢复，直接按备份目录中的 `chat_message_group_bot_deleted.jsonl` 以 `id` 精确回填即可，不需要整库回滚。
