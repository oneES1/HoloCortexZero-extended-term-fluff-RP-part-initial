# 2026-04-08 上下文入口“海泡菜”昵称防伪装清洗

## 背景

当前系统已在提示词层声明：

- `<ADVANCED_USER_ID>` 才是唯一真实的“海泡菜”

但提示词纠偏发生在模型使用上下文之后，仍然存在一个更早的污染窗口：

- 外部用户若把昵称伪装成“海泡菜”
- 该昵称可能先写入聊天记录
- 再被同步进 `context_id` 对应的上下文窗口
- 最终造成记忆、短上下文、触发提示前缀中的身份误导

本次处理目标不是改历史脏数据，而是对未来新入站消息做输入侧防护。

## 当前逻辑梳理

人类消息主干入口：

- `holo_cortex_zero/services/message_service.py`
  - `push_human_message()`：人类消息统一入库，并在这里解析 `context_id`
- `holo_cortex_zero/adapters/interface/collector.py`
  - `collect_message()`：适配器标准入口，首次注册 `DBUser.username` 的位置
- `holo_cortex_zero/services/user/util.py`
  - `user_register()`：通用注册入口，后台创建用户与适配器注册最终都走这里

上下文同步主干：

- `holo_cortex_zero/services/context_window/manager.py`
  - `sync_new_chat_messages()`：把 `DBChatMessage` 投影进 `DBContextMessage`
  - `_build_db_msg_prefix()`：生成 `¥昵称¥时间¥ID¥说：` 前缀
  - `_resolve_sender_name()`：生成媒体/附件提示里的发送者名称
  - `_build_reference_header()`：生成引用消息头里的发送者名称

## 本次最小修改

只加“受保护昵称清洗”，不改 `context_id` 路由，不改高级用户主干，不改适配器协议分支。

规则固定为：

- 当 `sender_name == "海泡菜"` 或 `sender_nickname == "海泡菜"`
- 且 `user_id != <ADVANCED_USER_ID>`
- 则将该发送者名称统一改写为 `风险用户`

落点分两层：

1. 主入口清洗
   - 文件：`holo_cortex_zero/services/message_service.py`
   - 在 `push_human_message()` 中、`DBChatMessage.create()` 之前执行
   - 作用：保证新收到的人类消息在进入任何 `context_id` 解析前已经被清洗

1.5 注册入口清洗
   - 文件：`holo_cortex_zero/adapters/interface/collector.py`
   - 在 `user_register()` 前执行
   - 作用：避免新用户首次注册时把伪装昵称写进 `DBUser.username`

2. 上下文兜底清洗
   - 文件：`holo_cortex_zero/services/context_window/manager.py`
   - 在聊天记录投影到上下文、以及生成发送者前缀/媒体提示、引用消息头、引用多媒体/文件提示时再次清洗
   - 作用：即使未来有人绕过主入口，只要消息进入上下文，也不会再带着伪装昵称进入 prompt

3. 工具/审计展示清洗
   - 文件：`holo_cortex_zero/services/tools/chain_executor.py`
   - 对 `trigger_user_name` 做统一清洗后再写入 tool trace / dashboard
   - 文件：`holo_cortex_zero/services/tools/host/bridge.py`
   - `lookup_user()` 返回给工具的 `username` 先清洗，避免 `block` 等工具把伪装昵称回显给 bot
   - 文件：`holo_cortex_zero/services/memory/runtime.py`
   - memory write payload 日志里的 `from_user_name` 做同规则清洗

4. 后台手工改名清洗
   - 文件：`holo_cortex_zero/routers/user_manager.py`
   - 后台修改 `DBUser.username` 时做同规则清洗

## 影响分析

正向影响：

- 新消息进入上下文前会阻断“海泡菜”昵称伪装
- 群聊触发前缀、上下文 `¥昵称¥ID¥说：` 前缀、媒体提示文案会保持一致
- 保持主干通用修整，没有为 Telegram / OneBot 单独复制一套逻辑

兼容影响：

- 只处理昵称等于 `海泡菜` 的情况
- 唯一真实 ID `<ADVANCED_USER_ID>` 不受影响
- 不改历史数据，因为当前确认没有脏数据
- 不影响 `context_id` 本身生成规则，仍然是“高级用户走 user_id，普通用户走 chat_key”

## 日志

本次新增了多处告警日志：

- 上下文入口前检测到受保护昵称伪装
- 适配器注册入口检测到受保护昵称伪装
- 用户注册命中受保护昵称清洗
- 后台更新用户命中受保护昵称清洗
- 上下文同步阶段命中兜底清洗

这样后续如果再有人尝试伪装，可以直接从业务日志里看到命中点。

## 风险与回滚点

风险较低：

- 仅对特定昵称做精确清洗
- 不改数据库结构
- 不改上下文路由主干
- 不改模型协议与工具链

回滚点：

- 删除 `message_service.py` 中的人类消息入口清洗
- 删除 `context_window/manager.py` 中的上下文兜底清洗
