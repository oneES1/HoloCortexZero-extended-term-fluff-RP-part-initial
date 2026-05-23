# OneBot 通知路由 group_0 修复

## 背景

运行日志出现 `ValueError: 聊天频道不存在: onebot_v11-group_0`，触发事件为 OneBot V11 `notice.notify.input_status`：

- `notice_type=notify`
- `sub_type=input_status`
- `group_id=0`
- `status_text` 为 `对方正在输入...` 或空字符串

该事件不是可投递到聊天上下文的群通知，但旧链路在识别具体通知类型前，先调用 `get_chat_info_old(event)` 并查 `DBChatChannel`，导致 `group_id=0` 被伪造成 `onebot_v11-group_0`。

## 根因

旧路由顺序为：

1. 所有 `NoticeEvent` 进入通用 notice matcher。
2. `get_chat_info_old()` 将泛化 `NoticeEvent` 无条件视为群事件。
3. `group_id=0` 被拼成 `onebot_v11-group_0`。
4. 在未判断是否为支持的业务通知前，先查频道并抛出不存在异常。

问题不是日志等级错误，也不是数据库缺频道，而是非会话通知进入了会话投递链。

## 修复原则

保留有用通知功能，不删除：

- 戳一戳
- 入群/退群
- 禁言/解禁
- 群消息撤回
- 群管理员变动

真实后端语义修复：

1. 先匹配是否为支持的业务通知。
2. 再解析该业务通知是否存在真实可投递会话。
3. 只有解析出真实 `chat_key` 后才查 `DBChatChannel` 并写入消息/上下文。
4. `input_status` 这类非业务通知不进入 DB 频道链路。
5. 支持的通知如果缺少有效 `group_id` 或对应频道尚未注册，记录原因并跳过，不伪造 `group_0`。

## 改动

- `holo_cortex_zero/adapters/onebot_v11/matchers/notice.py`
  - notice matcher 改为先 `notice_manager.handle(event_dict)`，再解析会话。
  - 新增 `_resolve_notice_chat_info()`，只把已匹配业务通知投递到真实群聊或私聊 poke 会话。
  - `input_status` 不匹配任何业务 handler，因此不会查 `onebot_v11-group_0`。
  - 系统通知推送时透传已查询到的 `db_chat_channel`，避免重复查库。
- `holo_cortex_zero/adapters/onebot_v11/tools/onebot_util.py`
  - 收窄 `get_chat_info_old()` 为消息事件旧工具，不再承接泛化 `NoticeEvent`。
  - `get_chat_info()` 仅保留消息与群文件上传事件用途。

## 保留能力

群文件上传仍由 `holo_cortex_zero/adapters/onebot_v11/matchers/message.py` 的 `GroupUploadNoticeEvent` matcher 处理，不受本次改动影响。

已支持的群通知仍会在目标群频道已注册时写入系统消息或普通消息，并按原配置决定是否触发 agent。

## 验证

已执行：

```bash
cd /path/to/source-root
python3 -m py_compile \
  holo_cortex_zero/services/notice_service.py \
  holo_cortex_zero/adapters/onebot_v11/tools/onebot_util.py \
  holo_cortex_zero/adapters/onebot_v11/matchers/notice.py
```

结果：编译通过。

## 风险与回滚

- 风险：私聊戳一戳只在对应私聊频道已经存在时投递；不会因 notice 自动创建新会话，避免无消息会话污染。
- 风险：支持的群通知如果协议端上报 `group_id=0`，会被视为不可投递并跳过，这是避免伪造 `group_0` 的预期行为。
- 回滚点：回退本次提交即可恢复旧 notice 路由。

## 复查验证

2026-04-29 追加边界复核：

- `input_status`：`notice_manager.handle()` 不匹配 handler，因此不会解析 `chat_key`，不会查 DB。
- 群戳一戳：`group_id > 0` 时路由到 `onebot_v11-group_<group_id>`。
- 私聊戳一戳：无有效 `group_id` 但有 `user_id > 0` 时路由到 `onebot_v11-private_<user_id>`；仅在频道已注册时投递，不自动创建新会话。
- 群成员增加：`group_id > 0` 时路由到对应群频道。
- 群撤回缺失有效 `group_id`：判定为不可投递，不伪造 `group_0`。
- 戳一戳目标比较：`BOT_QQ` 配置类型为字符串，和 `target_id` 字符串一致，不存在 int/str 比较导致不触发的问题。
- 群文件上传：仍走 `matchers/message.py` 的 `GroupUploadNoticeEvent` 链路，`get_chat_info()` 保留该事件支持。
- 命令 guard：`get_chat_info_old()` 只服务消息事件，`GroupMessageEvent` 仍是 `MessageEvent` 子类，不影响命令路径。

已执行离线断言与编译：

```bash
cd /path/to/source-root
./.venv/bin/python - <<'PY'
# 覆盖 input_status / 群 poke / 私聊 poke / group_increase / 缺 group_id 的 group_recall
PY
./.venv/bin/python -m py_compile \
  holo_cortex_zero/services/notice_service.py \
  holo_cortex_zero/adapters/onebot_v11/tools/onebot_util.py \
  holo_cortex_zero/adapters/onebot_v11/matchers/notice.py \
  holo_cortex_zero/adapters/onebot_v11/matchers/message.py \
  holo_cortex_zero/adapters/onebot_v11/matchers/guard.py
```

运行态复核：

- `holo_cortex_zero` 容器为 `healthy`。
- `/api/health` 返回 200。
- 部署后日志窗口未再出现 `onebot_v11-group_0`、`聊天频道不存在` 或 `notice.notify.input_status` 相关失败。
