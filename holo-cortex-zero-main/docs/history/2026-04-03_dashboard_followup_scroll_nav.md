# Dashboard 自动定位最新与导航简称跟进

## 本次调整
- 链条监测默认落在底部，并在新链路进入时自动滚动到最新。
- 不再在每条链路头部追加模型摘要；仅在 `llm` 气泡的模型名后追加上下文长度与用时。
- `Manage` 顶部次级按钮将 `System Settings` 换成 `Systems` 并放到原 `Users` 位置；`Users` 换到 logo 菜单原 `System Settings` 位置。
- `System Settings` 简称统一为 `Systems`，`Model Groups` 简称统一为 `Models`，`OneBot V11` 简称统一为 `OneBot`。

## 影响文件
- `frontend/src/pages/dashboard/index.tsx`
- `frontend/src/layouts/MainLayoutNew.tsx`
- `frontend/src/pages/manage/index.tsx`
- `frontend/src/locales/en-US/settings.json`
- `frontend/src/locales/zh-CN/settings.json`
- `frontend/src/locales/en-US/navigation.json`
- `frontend/src/locales/zh-CN/navigation.json`
- `frontend/src/locales/en-US/adapter.json`
- `frontend/src/locales/zh-CN/adapter.json`
- `docs/2026-04-03_dashboard_followup_scroll_nav.md`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 回滚点
- `e9e84f2` `backup(dashboard): snapshot before ui follow-up`
