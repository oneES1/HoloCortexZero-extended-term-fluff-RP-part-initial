# 2026-04-06 bot 回复 `bot:` 语义污染修复

## 问题现象

主模型历史回复在落库时被强行写成 `bot: xxx`，随后该文本进入上下文、记忆与部分判断链路，造成模型把 `bot:` 学成聊天正文的一部分，形成格式自污染。

目标是：

- 停止后续继续写入 `bot:` 污染
- 保持现有主干身份表达不变：`role=assistant` + `sender_name=海菜子`
- 不额外引入 provider/adapter 特化分支
- 不直接改旧库数据，只给出可选清洗方案

## 根因定位

根因位于 `holo_cortex_zero/services/message_service.py`：

- `_normalize_bot_record_text()` 以前会把 bot 文本强行改写成 `bot: {normalized}`
- `push_bot_message()` / `push_bot_message_text_shadow()` 都会调用它
- 结果是 `DBChatMessage.content_text` 被污染
- 后续污染会继续进入：
  - `context_window/manager.py` 的 bot 历史同步
  - `memory/subconscious.py` 的 recent messages
  - `ai_reply/service.py` 的部分明文历史判断链

## 本次最小修复

只修改 `holo_cortex_zero/services/message_service.py`：

- 删除“自动追加 `bot:` 前缀”逻辑
- 对新写入路径增加旧污染剥离：若文本以 `bot:` / `bot：` 开头，则在落库前剥离
- 保留日志，便于确认是否仍有上游污染文本流入

这次修复**不**改变 `¥昵称¥YYYY-MM-DD HH:MM:SS¥ID¥说：` 主干格式规则；该格式仍用于人类/归档文本主干。assistant 主干仍由 `role=assistant` 与 `sender_name=海菜子` 表达身份，不再额外并行引入 `bot:` 伪前缀。

## 网状影响分析

### 直接改善

- 新 bot 回复不再把 `bot:` 写入 `DBChatMessage.content_text`
- 后续进入 prompt / memory / recall 的 assistant 文本污染停止扩散
- 若模型由于旧污染偶发输出 `bot:` 开头，新写入也会被剥离，减少自我强化

### 本次明确不做

- 不批量改写历史数据库中的旧 `bot:` 脏数据
- 不调整 assistant 在上下文中的 role 主干
- 不把 assistant 文本改写为 `¥海菜子¥时间¥ID¥说：...`，避免与现有 assistant role 主干并行冲突

## 可选历史清洗方案（本次未执行）

仅建议作为后续单独操作，先备份后执行。

### 清洗目标

对 `DBChatMessage` 中满足以下条件的历史 bot 回复，剥离开头的 `bot:` / `bot：`：

- `sender_id = -1`
- 非真正 system 消息（排除 `platform_userid=0` 或 `sender_name=SYSTEM`）
- `content_text` 以 `bot:` 或 `bot：` 开头

### 建议步骤

1. 先导出命中行做审计备份
2. 只对命中行做前缀剥离，不改其余正文
3. 抽样检查 prompt 日志与一轮真实对话回放
4. 最小重建当前容器，验证 QQ/TG 实际收发

### 风险点

- 若极少数历史消息正文本来就真的想以 `bot:` 开头，清洗会改变其原文
- 因此建议先统计命中数并人工抽样，再决定是否执行

## 回滚点

单文件回滚即可：

- `holo_cortex_zero/services/message_service.py`

若需要整体回滚，可直接回退到本次修复前一提交。

## 本次执行记录（2026-04-06 17:35 CST+0800）

### 实际执行内容

已按最小范围执行历史清理：

- 清理 `chat_message.content_text` 中 bot 历史开头的 `bot:` / `bot：`
- 清理 `context_message.parts_json` 中 assistant 文本段开头的 `bot:` / `bot：`
- 仅处理命中污染特征且排除真正 system 消息的记录

### 备份文件

- `/path/to/runtime-data/backups/bot_prefix_cleanup_20260406_173516/chat_message_polluted.jsonl`
- `/path/to/runtime-data/backups/bot_prefix_cleanup_20260406_173516/context_message_polluted.jsonl`

### 执行结果

- `chat_message` 备份并清理：`180` 条
- `context_message` 备份并清理：`4` 条
- 清理后复查剩余命中：
  - `chat_message`：`0`
  - `context_message`：`0`

### 回滚抓手

若发现极少数消息原文确实需要以 `bot:` 开头，可基于以上两份 `jsonl` 备份按 `id` 精确回填，不需要整库回滚。
