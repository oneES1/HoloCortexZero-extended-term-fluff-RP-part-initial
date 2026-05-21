# 2026-04-10 移除聊天 reset 入口

## 背景

排查普通 context 归档缺失时，确认 `reset` 会直接删除：

- `context_message`
- `context_dialog_state`
- 普通窗口已有的归档/摘要状态

而当前同步主链不会回填旧 backlog，因此一旦执行 reset，聊天上下文会从空状态重新累计，旧归档垫底也随之消失。

现阶段该功能副作用明显，实际收益不足，因此先将聊天 reset 入口整体移除，避免再次误伤上下文状态。

## 本轮改动

### 后端

移除以下 reset 入口：

- OneBot `/reset` 命令
- 管理端 `POST /chat-channel/{chat_key}/reset`
- 调试接口 `POST /debug/reset-chat-channel`

同时删除已无人调用的：

- `DBChatChannel.reset_channel`
- `context_window_manager.reset_dialog`
- `reset_command_guard`

### 前端

移除聊天详情页中的：

- `重置` 按钮
- 重置确认弹窗
- 对应 API 调用与文案

## 影响面

- 聊天频道不再支持“清空上下文重新开始”
- 现有 `conversation_start_time` 统计逻辑保留，不在本轮扩散修改
- `hcz_db_reset` 等数据库级操作不受影响

## 风险

- 如果后续仍需要“只清当前聊天上下文”的能力，需要重新设计成不会删掉历史基底/同步水位的安全版本
- 本轮仅移除入口，不处理历史上已被 reset 清掉的数据

## 回滚点

直接回滚本次提交即可恢复聊天 reset 入口。
