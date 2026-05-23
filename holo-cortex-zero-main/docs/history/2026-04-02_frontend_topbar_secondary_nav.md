# 前端顶栏二级导航上移记录

## 本次调整
- 将 `Monitor` / `Manage` 的二级导航从页面内容区上移到顶栏，并放到顶栏靠右位置。
- `Monitor` / `Manage` 页面本身只保留内容出口，避免重复出现两层导航。
- 内容区顶部偏移恢复为单顶栏高度，避免因原二级导航占位导致页面可视区域变矮。

## 影响文件
- `frontend/src/layouts/MainLayoutNew.tsx`
- `frontend/src/pages/monitor/index.tsx`
- `frontend/src/pages/manage/index.tsx`

## 验证
- `cd /path/to/source-root/frontend && pnpm build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 回滚点
- `1178d87` `fix(frontend): trim dashboard clutter`
