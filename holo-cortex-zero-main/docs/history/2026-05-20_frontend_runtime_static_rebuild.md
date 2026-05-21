# 2026-05-20 前端运行态静态包修复

## 现象

用户反馈前端崩溃，浏览器显示：

```text
Unexpected Application Error!
Can't find variable: DeepNebulaBackground
```

## 复查证据

- `docker compose ps` 显示 `holo_cortex_zero` 为 `Up` 且 `healthy`，端口 `20261` 正常发布。
- 短尾日志显示后端已挂载 `/app/frontend/dist` 到 `/webui`，未读取全量日志。
- `GET http://127.0.0.1:20261/webui/` 返回 `200`，入口 HTML 为 709 字节。
- `GET /webui/assets/index-KqQlFhYm.js` 返回 `200`，JS 为 445272 字节。
- `pnpm --dir frontend build` 成功，生产构建耗时 36.54s，刷新了 bind mount 的 `frontend/dist`。
- `pnpm exec eslint src/pages/dashboard/index.tsx src/services/api/utils/stream.ts src/services/api/axios.ts` 暴露 `LatestMessage` 未使用的前端 lint 错误。
- `rg -n "function (DeepNebulaBackground|NeuralMeshBackground)|<(DeepNebulaBackground|NeuralMeshBackground)" frontend/src/pages/login/index.tsx` 复现到定义与调用不一致：第 16 行定义 `NeuralMeshBackground`，第 316 行调用 `DeepNebulaBackground`。

## 根因判断

当前后端与静态挂载链路可用；登录页背景组件改名后调用点未同步，导致浏览器运行时引用不存在的 `DeepNebulaBackground`。额外发现 Dashboard 页存在死类型引用，会导致局部 lint 检查失败，但不改变运行逻辑。

## 修改

- 删除 `frontend/src/pages/dashboard/index.tsx` 中未使用的 `LatestMessage` 类型导入。
- 将 `frontend/src/pages/login/index.tsx` 的登录页背景组件调用从 `DeepNebulaBackground` 改为现存的 `NeuralMeshBackground`。
- 删除登录页旧背景组件遗留的 `useCallback`、`GlobalStyles` 未使用导入。
- 重新构建 `frontend/dist`，利用现有 bind mount 同步到运行态。

## 影响范围

- 只影响前端 Dashboard 源码导入清理与静态产物刷新。
- 不修改后端接口、适配器、LLM 协议链路、Docker Compose 配置。
- 不重启家庭服务器，不触碰 frp。

## 验证命令

```bash
pnpm --dir frontend build
pnpm --dir frontend exec eslint src/pages/login/index.tsx src/pages/dashboard/index.tsx src/services/api/utils/stream.ts src/services/api/axios.ts
curl -sS -D - --max-time 5 http://127.0.0.1:20261/webui/ -o /tmp/hcz_webui_index.html
rg -n "DeepNebulaBackground" frontend/dist/assets
```
