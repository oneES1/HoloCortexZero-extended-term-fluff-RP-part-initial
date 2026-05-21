# 2026-05-12 registry method_type cleanup

## 背景

`holo_cortex_zero/services/tools/registry.py` 内残留旧版 `method_type` 字段/参数，并在注册日志中输出 `type=%s`。

## 证据

- `rg -n "method_type\\s*=|method_type\\b|\\.method_type\\b" holo-cortex-zero-main/holo_cortex_zero holo-cortex-zero-main/tool_runtime -g '*.py'`
- 命中仅限 `RegisteredTool` 字段、`ToolRegistry.register` 参数、构造赋值、注册日志参数。
- 没有调用方传入 `method_type`，没有运行路径读取 `RegisteredTool.method_type`。
- `ToolSpec` 只暴露 `name`、`description`、`parameters`、`permission_level`，不包含 `method_type`。

## 修改

- 删除 `RegisteredTool.method_type`。
- 删除 `ToolRegistry.register(..., method_type=...)` 参数。
- 删除 `RegisteredTool(...)` 构造中的 `method_type=...`。
- 删除注册日志中的 `type=%s` 与对应参数。

## 影响面

- 注册调用方无需调整：当前仓库没有调用方传入 `method_type`。
- Tool 上下文暴露、运行时执行、权限/作用域判断不变。
- 日志减少一个无实际语义的旧字段，保留 `source_kind`、`capability`、`default_scope`、`inject_context`。

## 回滚点

- 本次修改提交可独立回滚。
- 修改前工作区快照提交：`14b6326 backup(runtime): snapshot before registry cleanup`。
