# Validation Script Portability

## 背景

开源友好审查发现部分验证脚本携带作者宿主路径与个人用户 ID。这些脚本不在业务主链路中，但会影响第三方部署者运行验证时的默认行为与输出。

## 变更

- `validate_magic_draw_real_tool.py` 的宿主工作区默认值改为从 `HCZ_HOST_WORKSPACE_ROOT` 读取，未配置时使用当前 repo 的父目录。
- `smoke_ai_reply_dryrun.py` 的 dry-run 上下文 ID 改为通用测试 ID `10001`。
- `validate_weather_real_tool.py` 的 summary 字段去除个人 ID。

## 影响

- 第三方部署不再默认依赖 `/path/to<CONTAINER_WORKSPACE_DIR>`。
- 验证产物不再携带作者个人用户 ID。
- 不影响运行时业务逻辑、适配器逻辑或真实用户身份配置。

## 验证

- `rg` 确认 `scripts/` 中不再包含 `/path/to<CONTAINER_WORKSPACE_DIR>`、`<ADVANCED_USER_ID>`、`user_<ADVANCED_USER_ID>`。
- `uv run python -m compileall scripts/validate_magic_draw_real_tool.py scripts/smoke_ai_reply_dryrun.py scripts/validate_weather_real_tool.py`
