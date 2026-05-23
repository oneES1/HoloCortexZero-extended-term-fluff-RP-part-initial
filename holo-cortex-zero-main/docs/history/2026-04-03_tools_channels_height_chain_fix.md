# Tools / Channels 高度链与底部不可达修复

## 本次调整
- 对齐 `Prompt` 页的高度链结构，给 `Tools` 页双栏根网格增加 `alignItems: 'stretch'`。
- 给 `Tools` 页左右分栏 `Paper` 明确补上 `height: '100%'`，避免内部滚动容器因父级高度为 `auto` 而失效。
- 给 `Channels` 页根网格补上 `gridTemplateRows: 'minmax(0, 1fr)'` 与 `alignItems: 'stretch'`，确保桌面端内容高度跟随浏览器视口。
- 给 `Channels` 页桌面端左列表卡片、右详情容器，以及移动端详情容器补上 `height: '100%'`，恢复内部独立滚动并保证底部可达。
- 本次不再继续追加 `overflow`/`touch` 类补丁，只修正高度填充链。

## 影响文件
- `frontend/src/pages/tools/management.tsx`
- `frontend/src/pages/chat-channel/index.tsx`
- `docs/2026-04-03_tools_channels_height_chain_fix.md`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 风险与回滚点
- 风险：本次仅调整页面容器高度链与布局伸展方式，不改接口和业务逻辑；若局部卡片依赖旧的自撑高行为，可能出现视觉高度变化。
- 回滚点：本次提交完成后可直接按提交哈希回退。
