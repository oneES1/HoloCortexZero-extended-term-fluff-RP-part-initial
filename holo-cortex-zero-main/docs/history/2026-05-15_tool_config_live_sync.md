# 2026-05-15 Tool 配置前端保存后运行态即时同步

## 背景

Tool 启用范围已改为 YAML 用户配置优先，但仍存在运行态旧配置实例被复用的风险：

- Tool 注册时会把配置实例挂到 `RegisteredTool.config`。
- 配置服务 `reload_config()` 会把新实例注册进 `ConfigManager`。
- 如果后续 Tool 路径继续使用旧的 `RegisteredTool.config`，旧值可能再次写回 YAML，表现为前端改过的权限/启用范围被“修回去”。

## 修改

- `RegisteredTool.get_config()` 优先读取 `ConfigManager` 中当前配置实例。
- 当 `ConfigManager` 中实例与 registry 缓存不同步时，同步刷新 `RegisteredTool.config`。
- `resolve_scope_mode()`、Tool 执行期 `tool_config` 注入、`/tools/{tool_id}/scope` 更新接口均改为使用当前配置实例。

## 结果

- 前端通过通用配置表保存 Tool 配置后，后端 Tool 暴露、执行、详情查询会读取最新配置实例。
- 配置重载后不会因为 registry 旧对象继续参与执行或保存而把旧权限写回 YAML。
- 仍保留 `default_scope` 作为首次生成配置文件的推荐初始值。

## 验证

- `uv run python -m compileall holo_cortex_zero/services/tools holo_cortex_zero/routers/tools.py`
- 源码断言：
  - `update_tool_scope()` 不再直接写 `tool.config`。
  - Tool 执行期注入 `tool_config` 时使用 `tool.get_config()` 解析后的当前实例。

## 回滚点

- Git 提交：待提交后记录。
