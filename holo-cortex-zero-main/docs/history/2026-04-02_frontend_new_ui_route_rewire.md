# 新前端主干可用性收口记录

## 背景
- 入口 `src/App.tsx` 已切到 `src/router/new.tsx`，但新路由只保留了 `login / monitor / manage`。
- `monitor` 与 `manage` 页面仍是占位实现，无法承接旧后台的真实业务能力。
- 用户反馈 UI 实际不可用，根因不是单个按钮，而是新 UI 主干未接回成熟页面。

## 根因分析
1. `router/new.tsx` 没有覆盖旧主干中的日志、频道、工具追踪、用户、提示词、工具、适配器、系统设置等完整入口。
2. `MainLayoutNew` 的菜单一度指向不存在的路由；即使修掉死链，主干能力仍未接上。
3. 当时的并行登录页登录后认证态信息不完整。
4. 部分成熟页面把顶部偏移写死为 `64px`，直接挂到新布局和新分组标签下会出现高度不匹配。

## 本次最小收口
- 保留 `router/new.tsx` 作为入口，不回退到旧主干。
- 将 `Monitor` 接回成熟页面：`Dashboard / Logs / Traces / Channels`。
- 将 `Manage` 接回成熟页面：`Users / Prompts / Tools`。
- 在新布局中补回 `Adapters / System Settings / Model Groups` 入口。
- 保留旧路径跳转兼容，把旧书签路由重定向到新的 `monitor/manage` 分组。
- 修正当时的并行登录页认证态同步。
- 将依赖顶部偏移的页面改为读取统一 CSS 变量，避免新旧布局高度耦合死写。

## 影响面
- `frontend/src/router/new.tsx`
- `frontend/src/layouts/MainLayoutNew.tsx`
- `frontend/src/pages/monitor/index.tsx`
- `frontend/src/pages/manage/index.tsx`
- 当时的并行登录页组件
- `frontend/src/pages/dashboard/index.tsx`
- `frontend/src/pages/logs/index.tsx`
- `frontend/src/pages/user-manager/index.tsx`

## 验证
- 前端构建：`cd /path/to/source-root/frontend && pnpm build`
- 运行态同步：`cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`
- 人工验证：登录后依次检查 `Monitor / Manage / Adapters / System Settings / Model Groups` 是否都可进入，并在 QQ/TG 内发消息验证监控页数据链路。

## 回滚点
- 上一稳定提交：`b0e3874` `fix(frontend): improve new UI usability`
