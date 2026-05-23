# Debug Inject Removal

## 背景

开源友好审查发现 `/api/debug/inject-onebot-group-message` 是早期手工注入 OneBot 群消息的调试入口。仓内没有前端、脚本或业务服务调用该接口，只有 FastAPI 路由注册。

## 变更

- 删除 `holo_cortex_zero/routers/debug_inject.py`。
- 删除 API 路由注册中的 `debug_inject_router` import/include。

## 影响

- 移除 `/api/debug/inject-onebot-group-message`。
- 正常适配器入站、消息服务、WebUI 管理接口不受影响。
- 不新增开关或兼容分支，避免保留未使用调试攻击面。

## 验证

- `python -m compileall holo_cortex_zero/routers`
