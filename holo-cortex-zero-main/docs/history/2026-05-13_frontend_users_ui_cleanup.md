# 2026-05-13 前端用户页删减

## 目标

- 删除用户列表里的权限展示。
- 删除用户列表里的状态展示。
- 删除用户列表顶部无用表头 UI。

## 改动

- `frontend/src/pages/user-manager/components/UserTable.tsx`
  - 删除表格 `TableHead`，用户列表不再显示顶部表头行。
  - 删除第一列 ID。
  - 删除权限列和状态列。
  - 删除表头排序入口及其失效的辅助代码。
  - 删除已无入口的编辑用户弹窗与权限编辑相关代码。
  - 将用户名、平台、平台用户 ID、创建时间合并为主副信息排版，避免字段均匀平铺。
- `frontend/src/pages/user-manager/components/UserDetail.tsx`
  - 删除详情抽屉里的权限展示。
  - 删除详情抽屉里的状态信息卡片。
- `frontend/src/pages/user-manager/hooks/useUserData.ts`
  - 删除前端排序状态和编辑用户 mutation 暴露。
  - 列表请求仍固定保持 `id desc`，避免删除表头后改变默认顺序。

## 验证

- `pnpm --dir frontend build`
