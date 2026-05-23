# Manage / Tools 右栏连续滚动板块修复

## 问题定位
- `Manage -> Tools` 右栏需要保持为一个整体可滚动的大板块，而不是上下两个彼此独立滚动的分区。
- 此前为了快速止血把配置调控区与参数 JSON 区拆成了两个固定分区，虽然能避免重叠，但破坏了右栏作为连续内容板块的整体性。
- 真正需要修复的是：在保持单一滚动链的前提下，让配置区与 JSON 区按自然文档流紧挨排列、互不覆盖。

## 本次调整
- 将 `Manage -> Tools` 右栏恢复为单一纵向滚动容器，配置区与参数 JSON 区共用同一条滚动链。
- 保留两部分的顺序关系，但移除独立分区做法；参数 JSON 作为同一大板块中的连续内容，紧跟在配置区后方展示。
- 将参数 JSON 区改为同板块内的自然内容段，只保留轻量分隔线，不再渲染成独立卡片，避免视觉上被切成两个区域。
- 将该页 `ConfigTable` 恢复为自然撑高模式 `fillHeight={false}`，使配置区高度由内容决定，JSON 区被自然推到其后而不重叠。

## 影响文件
- `frontend/src/pages/tools/management.tsx`
- `docs/2026-04-04_manage_tools_pane_split_fix.md`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 风险与回滚点
- 风险：本次调整仅影响 `Manage -> Tools` 右栏的视觉结构与滚动归属；配置表内容极长时，JSON 区会顺延到更靠下的位置，但整体仍为单一连续滚动板块。
- 回滚点：本次提交完成后可直接按提交哈希回退。
