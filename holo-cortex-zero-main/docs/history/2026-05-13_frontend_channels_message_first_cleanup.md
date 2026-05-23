# Channels 消息优先界面清理

## 目标

- Channels 右侧详情区域不再展示频道标题、频道 key、类型标签和统计摘要。
- 选中频道后右侧直接显示聊天内容。
- 停用/启用从右侧详情头部迁移到左侧频道列表项内，使用绿色滑动开关。

## 改动

- `frontend/src/pages/chat-channel/components/ChatChannelDetail.tsx`
  - 删除右侧头部卡片、详情标签页、基础信息页签、启停按钮组。
  - 删除频道详情额外查询，右侧只渲染 `MessageHistory`。
  - 移动端保留返回按钮；桌面端不显示右侧标题和返回控件。
- `frontend/src/pages/chat-channel/components/ChatChannelList.tsx`
  - 删除列表项中的统计摘要和小状态圆点。
  - 在左侧列表项内加入 `Switch`，开启态使用绿色。
  - 开关点击只触发启停接口并刷新当前频道列表，不再触发已删除的详情查询。
- `frontend/src/services/api/chat-channel.ts`
  - 删除前端不再使用的频道详情接口类型和请求函数。
- `frontend/src/pages/chat-channel/components/detail-tabs/MessageHistory.tsx`
  - 删除消息列表左侧头像框和首字母头像占位。
- 删除不再使用的基础信息组件。
- `frontend/src/locales/*/chat-channel.json`
  - 删除 Channels 旧显示文案残留。

## 验证

- `pnpm --dir holo-cortex-zero-main/frontend exec tsc --noEmit` 通过。
- `pnpm --dir holo-cortex-zero-main/frontend build` 通过。
- 运行态同步：`docker compose -f docker-compose.yml up -d --no-deps --force-recreate holo_cortex_zero`。
- 运行态健康检查：`GET /api/health` 返回 `200`。
- Channels 范围残留扫描未命中旧详情接口、旧详情组件、旧统计摘要文案和指定频道标识。
- 消息列表残留扫描未命中 `ListItemAvatar`、应用侧 `Avatar`、`sender_name[0]`、`头像`。

## 边界

- 未修改后端聊天消息、频道启停、消息统计采集等业务逻辑。
- 未修改 Channels 搜索、类型过滤、状态过滤、分页逻辑。
- 当前工作区存在 adapter 相关未提交改动，本次记录不纳入这些文件。
