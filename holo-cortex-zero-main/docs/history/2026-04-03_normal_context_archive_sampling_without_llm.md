# 2026-04-03 普通 context 无 LLM 抽样归档

## 背景

普通 context 当前链路已经切到“达到阈值后直接回收旧历史”，不再默认走 timeline LLM 摘要。

这会带来两个问题：

1. 旧历史被直接删除，完全没有“历史残影”
2. 若重新启用旧 timeline，又会把普通闲聊链路重新拖回 LLM 开销

本轮改为：

- 保持普通 context 不走 LLM timeline
- 保持普通 context 不扫描 `DBChatMessage` 主聊天库
- 仅在普通 context 触发阈值回收时，从当前 `DBContextMessage` 旧前缀中抽样保留纯文本历史
- 抽中的文本保留 `¥昵称¥时间¥ID¥说：正文` 风格，不混入图片、附件、base64、路径
- 归档后再删除旧前缀原始消息，最近尾部原文继续保留

## 现链路落点

入口未变，仍然是：

- `holo_cortex_zero/services/agent/run_agent_v2.py`
- `sync_new_chat_messages -> inject_messages -> enforce_history_hard_limit`

真正改动点：

- `holo_cortex_zero/services/context_window/manager.py`
- `holo_cortex_zero/services/context_window/assembler.py`

说明：

- 没有接回 `timeline.py` 的 LLM 压缩 worker
- 没有新增表
- 没有回扫 `DBChatMessage`
- 继续复用 `DBContextWindow.compressed_summary` 作为普通 context 的“较早历史归档”槽位

## 实现说明

### 1. 普通 context 回收从“直接删”改为“抽样归档后删”

在 `manager.py` 中新增普通 context 归档 helper：

- 仅处理当前 `context_id` 的 `DBContextMessage`
- 仅处理可回收旧前缀，不动最近 `keep_recent`
- 每轮最多处理一个有界批次，批次大小 = `threshold - keep_recent`
- 单容器内同一 `context_id` 进入归档时会先拿进程内锁，避免并发重复归档
- 每个归档批次都在单事务内完成“写归档块 + 删旧消息”，避免写后删前中断造成重复归档
- 若历史意外积压过大，单次最多循环 8 批，避免无限回收

### 2. 只抽取纯文本，不混入媒体路径

归档提取时：

- 只读取 `parts_json` 中 `type == text` 的 part
- 继续复用 `_sanitize_text()` 清洗控制平面脏文本
- 不走 `_parse_parts_json()`，避免把图片降级为 `[历史图片]`
- 不保留 `url / mime / data_b64 / path / meta`

### 3. 抽样规则

普通 context 旧前缀文本采用固定抽样：

- 保留第 1 条
- 每 5 条取 1 条
- 强制保留最后 1 条

被抽中的消息保留全文，不做 LLM 摘要改写。

### 4. 归档文本格式

每条消息归档成纯文本：

- 人类消息：优先保留原有 `¥昵称¥时间¥ID¥说：正文`
- bot / assistant 消息：若原文没有 `¥` 前缀，则按 `sender_name / sender_id / created_at` 补齐同构前缀

块头格式：

- `【较早历史归档 YYYY-MM-DD HH:MM:SS | sampled/source】`

### 5. 组装注入

`assembler.py` 现在改为：

- 普通 context：若存在 `compressed_summary`，按 `【较早历史归档】` 注入
- 高级 context：继续维持 `【长期记忆：对话历史摘要】`

这样普通 context 会稳定读取这份无 LLM 归档，不再依赖旧 timeline 开关。

## 风险与逻辑断点

### 1. bot 时间并非严格原始发送时间

当前普通用户同步到 `DBContextMessage` 后，bot 文本本身通常不带 `¥时间` 前缀；
本轮为保持最小修改，归档时对这类消息使用 `DBContextMessage.created_at` 补齐时间。

这意味着：

- 人类消息时间通常是原始发送时间
- bot 消息时间当前更接近“进入 context 的记录时间”

若后续要求 bot 也必须保留原始发送时间，需要统一主干补齐 bot 注入格式，而不是另开旁路。

### 2. 当前一致性边界

本轮已补：

- 单容器内同一 `context_id` 的归档互斥锁
- 单批次“写归档块 + 删旧消息”的数据库事务
- 若本批存在文本但归档块为空 / 窗口不存在，则中止删除，避免文本缺失

这意味着：

- 单容器内最现实的“重复归档”风险已被收口
- 单次批处理里，文本型旧消息不会再出现“没归档就删掉”的路径

仍未覆盖：

- 多实例 / 多进程横向部署下的跨进程竞争
- bot 时间仍不是严格原始发送时间

### 3. 无文本批次仍允许直接清理

若某个归档批次全部是图片 / 文件 / 被清洗为空的文本，则该批次不会生成归档块，
但仍会直接删除旧消息。

这是当前设计边界：

- 只承诺保留文本历史残影
- 非文本旧消息允许被回收

### 4. 长文本仍可能让归档块变大

本轮只限制“归档块数量”最多保留 6 块，没有再对单条长文本做二次截断，
因为需求明确要求被抽中的文本不要再丢正文信息。

## 修改文件

- `holo_cortex_zero/services/context_window/manager.py`
- `holo_cortex_zero/services/context_window/assembler.py`
- `docs/2026-04-03_normal_context_archive_sampling_without_llm.md`

## 本轮验证

已执行：

- `python3 -m py_compile holo_cortex_zero/services/context_window/manager.py holo_cortex_zero/services/context_window/assembler.py`

未执行：

- docker 重建
- 在线聊天实测

## 回滚点

若需快速回滚本轮行为，可直接撤销：

- `holo_cortex_zero/services/context_window/manager.py`
- `holo_cortex_zero/services/context_window/assembler.py`

回滚后普通 context 会恢复为达到阈值后直接删除旧历史，不保留归档残影。
