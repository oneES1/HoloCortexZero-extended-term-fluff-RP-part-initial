# 高级 Context /clear 全局清理命令

## 背景

在高级 context 模式切换命令之外，新增高级用户 `<ADVANCED_USER_ID>` 的手工清理命令 `/clear`。命令只允许高级用户触发，但清理范围按最终确认调整为全局消息与全局 context 消息，避免只清当前高级 context 后残留其他窗口历史。

## 行为

- 高级用户发送精确 `/clear`：
  - 不写入 `chat_message`；
  - 不触发 LLM；
  - 清空所有 `chat_message`；
  - 清空所有 `context_message`；
  - 清空所有 `context_dialog_state` 同步水位；
  - 重置所有 `context_window` 上的 timeline 版本号、timeline 消息计数、待生成摘要、自动记忆计数；
  - 保留所有 `context_window.compressed_summary` 已落地压缩摘要；
  - 清空当前进程内的待触发消息、防抖队列和 context 注入缓存；
  - 返回聊天框文本：`杂乱已清除`。
- 普通用户发送 `/clear`：
  - 直接忽略；
  - 不回复；
  - 不写 `DBChatMessage`；
  - 不触发 LLM。
- 任意 agent 任务或 tool 链运行中发送 `/clear`：
  - 不清理、不切锚点；
  - 返回：`当前还有任务在跑，稍后再清理`；
  - 日志标记 `advanced context clear command ignored by active runtime`。

## 清理范围

`/clear` 的触发权限限定为高级 context，但执行范围是全局消息/context 表：

- `chat_message` 全表；
- `context_message` 全表；
- `context_dialog_state` 全表；
- 所有 `context_window` 的 timeline 版本号、timeline 消息计数、待生成摘要、自动记忆计数。

`/clear` 不清空 `compressed_summary`；需要连 timeline 已落地压缩摘要一起清空时，使用 `/clearall`。

不删除配置、不删除模型组、不删除长期记忆库、不删除 `context_window` 行本身，因此高级模式、锚点和权限窗口仍可继续复用。

## 关键文件

- `holo_cortex_zero/services/message_service.py`：识别 `/clear`，高级 context 空闲时执行全局清理并返回提示。
- `holo_cortex_zero/services/context_window/manager.py`：集中实现全局消息/context 清理和窗口运行计数重置。

## 验证命令

```bash
cd /path/to/source-root
python3 -m py_compile \
  holo_cortex_zero/services/message_service.py \
  holo_cortex_zero/services/context_window/manager.py
uv run poe test
```

## 部署命令

```bash
cd /path/to<CONTAINER_WORKSPACE_DIR>
printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero
```

## 风险与回滚

风险：

- `/clear` 会清空所有本地聊天消息与所有 context 消息，是全局清理命令。
- 清理不触碰长期记忆库；如果需要清长期记忆，应单独设计命令，避免误删。
- 有 agent 任务或 tool 链运行时拒绝清理，防止运行链路继续写入或锚点错乱。

回滚点：

- `fix(context): add advanced clear command`
- `fix(context): clear all messages and contexts`
