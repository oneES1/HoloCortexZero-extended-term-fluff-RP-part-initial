# 2026-05-12 旧配置项清理

## 背景

系统设置里存在一组已经误导或只剩旧链路含义的配置项。按“删除优先”原则收口，避免 WebUI 继续暴露不可解释开关。

## 删除项

- `ALLOW_SUPER_USERS_LOGIN`
- `SUPER_USERS`
- `DEBUG_IN_CHAT`
- `ENABLE_COMMAND_UNAUTHORIZED_OUTPUT`
- `ENABLE_ADVANCED_COMMAND`

## 改动

- 删除 `CoreConfig` 中上述旧字段。
- 删除聊天窗口内 debug 回显开关；发送失败只写日志并抛错。
- 登录逻辑移除 `ALLOW_SUPER_USERS_LOGIN` 分支与 `SUPER_USERS` 配置提权，WebUI 权限只走用户表 `perm_level`。
- 2026-05-12 追加恢复：`REFERENCE_TEXT_MAX_LEN` 与 `AI_CHAT_RANDOM_REPLY_PROBABILITY` 仍作为有效后端配置保留。

## 运行态配置

真实运行配置 `/path/to/runtime-data/configs/holo-cortex-zero.yaml` 已确认不含已删除旧键，并保留：

- `REFERENCE_TEXT_MAX_LEN: 120`
- `AI_CHAT_RANDOM_REPLY_PROBABILITY: 0.0`

## 验证

```bash
rg -n 'ALLOW_SUPER_USERS_LOGIN|SUPER_USERS|DEBUG_IN_CHAT|ENABLE_COMMAND_UNAUTHORIZED_OUTPUT|ENABLE_ADVANCED_COMMAND|require_advanced_command' holo_cortex_zero docs /path/to/runtime-data/configs/holo-cortex-zero.yaml
uv run python -m compileall holo_cortex_zero
```
