# 前端可用性修复记录

## 背景
- 新版前端已经切到 `src/router/new.tsx`，但新布局里仍保留旧路由入口。
- `Monitor` / `Manage` 页面在接口返回空列表或未返回 `items` 时，存在空白态缺失与潜在白屏风险。
- 顶部主导航使用局部状态维护选中态，刷新、直达路由或浏览器回退后会与 URL 脱节。

## 根因
1. `MainLayoutNew` 菜单残留旧主干中的 `/adapters` 与 `/settings/*` 入口，和当前新路由不一致。
2. 顶部导航把“当前页面”拆成了额外的本地状态，导致可视状态不可信。
3. 多个列表组件默认假设 `data.items` 一定存在且非空，没有做兜底展示。

## 本次最小修改
- 删除 `MainLayoutNew` 中当前新路由不存在的菜单项，仅保留可用登出入口。
- 顶部 `Monitor / Manage` 高亮改为直接根据 `location.pathname` 派生，不再维护重复状态。
- 为 `Monitor` 与 `Manage` 中的日志、工具追踪、频道、用户、工具列表补齐空数组与空态展示。

## 影响面
- 仅影响新版前端布局与两个新页面：`monitor`、`manage`。
- 不改后端接口，不改旧版路由，不引入新配置项。

## 验证计划
- 执行 `pnpm build` 验证前端构建。
- 将前端产物同步到当前运行容器：`sudo docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`。
- 请在 QQ 或 TG 内直接触发相关使用路径，确认新版前端导航、空列表页面与登出行为正常。

## 回滚点
- 修改前快照提交：`4e6ef74` `backup(frontend): snapshot before usability fix`
