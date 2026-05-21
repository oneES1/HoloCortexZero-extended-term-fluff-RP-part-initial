# 超级用户依赖残留清理

## 结论

目标超级用户 FastAPI 依赖函数是未使用残留，已删除。

## 可复现证据

- 工作区：`/path/to/source-root`
- 分支：`codex/tool-scope-yaml-20260512`
- 命令：按目标超级用户依赖函数名、短名和描述词全仓搜索，排除 `*.log`、`logs/**`、`data/**`、`runtime/**`。
- 删除前结果：全仓仅 1 处命中，位于 `holo_cortex_zero/services/user/deps.py:67`，是函数定义本身。
- 命令：按目标依赖的 `Depends(...)` 形式，以及现用用户依赖、权限字段和超级用户描述词搜索源码。
- 删除前结果：路由和权限装饰器均使用 `get_current_active_user`；没有目标依赖的 `Depends(...)` 命中。
- 命令：`rg -n "from holo_cortex_zero\\.services\\.user\\.deps import|services\\.user\\.deps import|import .*deps" holo_cortex_zero --glob '!*.log'`
- 删除前结果：所有导入点只导入 `get_current_active_user`；没有导入目标依赖。

## 修改

- 删除 `holo_cortex_zero/services/user/deps.py` 中未被调用的目标超级用户依赖函数。
- 删除该函数独占的 `PermissionDeniedError` 与 `Role` 导入。

## 影响面

- WebUI 当前依赖链保持为 `get_current_user -> get_current_active_user`。
- `Role.Super` 与 `PermissionDeniedError` 在其他权限模块和路由中仍有真实使用，本次没有删除公共定义。
- 未新增兼容分支、配置项或并行逻辑。
