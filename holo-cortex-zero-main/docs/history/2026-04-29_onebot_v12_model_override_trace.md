# 2026-04-29 OneBot V12 模型覆盖 DEBUG 追查与后端启动收口

## 背景

运行日志中出现：

`OneBot V12 | Model for key "" <class 'nonebot.adapters.onebot.v12.event.BotEvent'> is overridden by <class 'nonebot.adapters.onebot.v12.event.Event'>`

该日志来自 `nonebot-adapter-onebot` 的 DEBUG 级内部模型注册逻辑，不代表 HCZ 注册了 OneBot V12 adapter，也不代表 V11 被 V12 覆盖。

## 根因

- `nonebot-adapter-onebot==2.4.6` 的父包 `nonebot.adapters.onebot` 会同时暴露 V11 与 V12 符号。
- 当 `nonebot.init()` 后首次导入 `nonebot.adapters.onebot.v11` 时，父包初始化会连带导入 V12。
- V12 `Collator` 以 `type/detail_type/sub_type` 生成事件模型 key。
- V12 的 `Event` 与 `BotEvent` 都不能生成更细判别 key，因此共同落在空 key `""`，触发依赖包内部 DEBUG 覆盖日志。

本地验证：V12 默认 25 个事件模型中，唯一重复 key 为 `"" -> ['BotEvent', 'Event']`。

## HCZ 侧触发链路

主启动入口 `run_bot.py` 先导入 OneBot V11 adapter，再执行 `nonebot.init()`，该顺序本身不会复现该 V12 DEBUG 日志。

更高风险的触发点是普通业务脚本先执行 `nonebot.init()`，再导入 HCZ 子模块。旧版 `holo_cortex_zero/__init__.py` 存在包级启动副作用：任意 `import holo_cortex_zero.*` 都会挂载 API 路由、加载 adapters API，并动态导入 OneBot V11 适配器，间接触发 OneBot 父包和 V12 模型注册。

示例链路：

1. `scripts/validate_magic_draw_real_tool.py` 先 `nonebot.init()`。
2. 后续导入 `holo_cortex_zero.services...` 时 Python 先执行 `holo_cortex_zero/__init__.py`。
3. 包级初始化调用 `mount_api_routes()`。
4. `mount_api_routes()` 调用 `load_adapters_api()`。
5. `load_adapters_api()` 动态导入 `holo_cortex_zero.adapters.onebot_v11.adapter`。
6. OneBot V11 导入触发父包 `nonebot.adapters.onebot` 初始化，V12 默认模型注册 DEBUG 被输出。

## 修复

- 将 `holo_cortex_zero/__init__.py` 的启动装配收口为显式 `bootstrap_application()`。
- `run_bot.py` 在 NoneBot 初始化和 V11 adapter 注册后显式调用 `bootstrap_application()`。
- 普通业务模块导入 `holo_cortex_zero.*` 不再自动挂载路由、注册生命周期、加载 adapters API。
- `holo_cortex_zero/schemas/agent_ctx.py` 将 OneBot V11 类型导入移动到 `TYPE_CHECKING`，并延迟导入 `adapter_utils`，避免 schema 层导入协议端和 adapters 聚合模块时产生循环副作用。

## 验证

- `LOG_LEVEL=DEBUG .venv/bin/python - <<'PY' ... import holo_cortex_zero.schemas.agent_ctx ... PY`
  - 结果：普通 schema 导入成功，未出现 OneBot V12 模型覆盖 DEBUG。
- `LOG_LEVEL=DEBUG .venv/bin/python - <<'PY' ... bootstrap_application() ... PY`
  - 结果：显式后端装配成功，已注册 adapter 列表仅包含 `OneBot V11`，未出现 OneBot V12 模型覆盖 DEBUG。

## 风险与回滚点

- 风险：若存在其他入口依赖 `import holo_cortex_zero` 自动完成后端装配，需要改为显式调用 `bootstrap_application()`。
- 当前全仓只发现 `run_bot.py` 是正式启动入口，已补显式调用。
- 回滚点：回退本次提交即可恢复旧的包级自动启动行为。

## 入口脚本落地修正

2026-04-29 追加复核时确认：为避免入口路径复杂化，保留原有“镜像重建落地入口脚本”的框架，不再额外挂载 `run_bot.py`，也不让容器从 `<CONTAINER_WORKSPACE_DIR>` 源码目录直接执行入口。

最终规则：

- `run_bot.py` 由 `dockerfile` 中 `COPY run_bot.py ./` 打入镜像。
- 容器启动继续通过 `/app/.venv/bin/bot --env=prod` 进入已安装包。
- `docker-compose.yml` 只热挂载应用包目录 `holo_cortex_zero` 与工具运行目录，不热挂载入口脚本。
- 入口脚本变更必须走 `docker compose up -d --build --force-recreate holo_cortex_zero`，避免“镜像内入口”和“挂载入口”两条路径并存。

验证：

- `bash -n scripts/dev_stack.sh scripts/hcz_runtime_entrypoint.sh`
- `docker compose -f docker-compose.yml config` 确认不存在 `/app/run_bot.py` bind mount。
- 重建后容器内 `/app/run_bot.py` 包含 `bootstrap_application()` 调用，且 `/app/.venv/bin/bot --env=prod` 为唯一生产入口。

新增风险与回滚点：

- 风险：入口脚本变更需要重建镜像后才会进入生产运行态。
- 回滚点：回退本次入口框架修正提交并重新构建后端镜像。
