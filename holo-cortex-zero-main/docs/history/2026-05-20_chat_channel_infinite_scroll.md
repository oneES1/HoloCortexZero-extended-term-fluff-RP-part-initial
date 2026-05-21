# 2026-05-20 Chat Channel 无限滚动列表

## 背景

聊天频道列表底部翻页在窄侧栏里占空间，且交互不如连续浏览自然。用户要求去掉 channel 翻页，改为无限滑动列表。

## 变更

- `ChatChannelPage` 从 `useQuery + page/pageSize + TablePaginationStyled` 改为 `useInfiniteQuery`。
- 每页固定加载 `25` 个频道。
- 频道列表滚动到距离底部 `120px` 内时自动请求下一页。
- 搜索、类型筛选、状态筛选变更后滚动回顶部并用新 query key 重新加载。
- `ChatChannelList` 增加已加载数量提示与底部加载提示。
- 启用/停用频道后按当前筛选 key 刷新无限列表。
- 中英文补齐 `loaded / loadingMore / scrollForMore` 文案。

## 影响

- 仅影响聊天频道列表区域。
- 后端 `/chat-channel/list` 接口不变，仍使用现有分页参数。
- 用户管理和 Tool Traces 等其他分页页面不受影响。

## 回滚点

- 还原 `frontend/src/pages/chat-channel/index.tsx` 中 `useInfiniteQuery` 与滚动加载逻辑。
- 还原 `frontend/src/pages/chat-channel/components/ChatChannelList.tsx` 新增 props 与提示。
- 删除本次新增 locale key。
