# Monitor / Traces / Channels 滚动与视口适配修复

## 问题定位
- `MainLayoutNew` 已将主内容区高度固定为 `calc(var(--hcz-viewport-height, 100vh) - 52px)`，但 `MonitorPage` 仍使用 `minHeight: calc(100vh - 52px)`，没有形成可继承的 `height: 100%` 高度链。
- `Traces` 与 `Channels` 页面都依赖父级提供稳定高度，并把实际滚动交给内部容器；父级高度链断裂后，内部 `overflow: auto` 在 macOS 浏览器上更容易表现为“内容存在但无法滚动”。
- `Traces` 页自身根容器、`Paper`、`TableContainer` 的纵向 flex 链缺少 `minHeight: 0`，在父级高度紧约束下会放大滚动失效问题。

## 本次调整
- 将 `frontend/src/pages/monitor/index.tsx` 对齐 `ManagePage` 的容器写法：改为 `height: '100%'`、`minHeight: 0`、`overflow: 'hidden'`，并给 `Outlet` 包裹层补 `overflow: 'hidden'`。
- 给 `frontend/src/pages/tool-traces/index.tsx` 的页根容器、主 `Paper`、`TableContainer` 补上 `minHeight: 0`，确保折叠列表的独立滚动容器在监控壳层内可正常收缩。
- 本次不做 macOS/Safari 特化，不改业务逻辑，只修复监控主干高度链与滚动容器约束。

## 影响文件
- `frontend/src/pages/monitor/index.tsx`
- `frontend/src/pages/tool-traces/index.tsx`
- `docs/2026-04-04_monitor_traces_channels_scroll_fix.md`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 风险与回滚点
- 风险：本次仅调整监控路由壳层与 `Traces` 页滚动容器的高度链，不改接口和渲染结构；若个别监控页依赖旧的自撑高行为，可能出现局部空白高度变化。
- 回滚点：本次提交完成后可直接按提交哈希回退。
