# 2026-05-12 Tool 启用范围改为 YAML 用户配置优先

## 背景

为便于 HCZ 开源规范化，Tool 的启用范围不应由框架代码硬绑定。注册参数只提供推荐初始值，部署者和管理员通过 YAML / 管理接口自定义最终启用范围。

## 修改

- 删除 `get_tool_config()` 中 `fixed_scope` 启动时覆盖 `SCOPE_MODE` 并写回 YAML 的逻辑。
- 删除 `RegisteredTool.resolve_scope_mode()` 中优先返回 `fixed_scope` 的运行期硬锁。
- 删除 `/api/tools/{tool_id}/scope` 对 `fixed_scope` Tool 的禁改判断。
- 高级维护 Tool 注册保留 `default_scope="advanced_only"`，删除 `fixed_scope="advanced_only"` 和硬限制提示。
- 删除 API 快照、前端类型、ToolDescriptor、注册日志中的 `fixed_scope` 僵尸字段。
- 更新 Tool 开发/集成文档，明确 `default_scope` 是推荐初始值，运行期以用户 YAML `SCOPE_MODE` 为准。

## 影响面

- 当前运行态 `/path/to/runtime-data/configs/tools` 下 20 个 Tool YAML 均可作为最终配置来源。
- 原本 7 个高级维护 Tool（`list_files`、`send_file`、`read_file`、`search_code`、`run_command`、`write_file`、`apply_patch`）不再在启动注册时被强制刷新回 `advanced_only`。
- 管理接口仍只接受四个合法值：`disabled`、`normal_only`、`advanced_only`、`all`。

## 验证

- `uv run python -m compileall holo_cortex_zero/services/tools holo_cortex_zero/routers/tools.py tool_runtime`
- `pnpm --dir frontend exec tsc --noEmit`
- 配置层临时目录验证：
  - 新建缺省配置时，高级维护 Tool 的 `SCOPE_MODE` 初始为 `advanced_only`。
  - 当 YAML 已存在且值为 `disabled` 时，加载后保持 `disabled`，不再被 `fixed_scope` 刷回。
- 源码断言验证：
  - `registry.py` 不再包含 `fixed_scope`。
  - `resolve_scope_mode()` 从 `config.SCOPE_MODE` 读取值，非法值才回退 `default_scope`。

说明：直接导入 `holo_cortex_zero.services.tools.registry` 做进程内实例化时触发了既有 `DBChatChannel` / adapter 循环导入，故本次未把完整 registry 实例化作为验证条件。

## 回滚点

- Git 提交：待提交后记录。
- 回滚该提交即可恢复旧的 `fixed_scope` 硬锁行为。
