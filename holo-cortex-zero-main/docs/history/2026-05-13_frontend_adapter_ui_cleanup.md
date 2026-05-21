# 2026-05-13 前端适配器页面删减

## 目标

- 删除 OneBot 适配器页的主页与高级页签，只保留配置、NapCat、容器日志。
- 保留 SSE 与 Telegram 的前端适配器导航入口，但删除其配置页签。
- 删除适配器页面顶部的名称、加载状态、配置类头卡。

## 改动

- `frontend/src/config/adapters.tsx`
  - OneBot 移除主页与高级页签。
  - SSE 与 Telegram 只恢复导航入口，不恢复配置页签。
  - 删除前端不再使用的状态展示和适配器头像生成函数。
- `frontend/src/pages/adapter/AdapterTabPage.tsx`
  - 无页签适配器入口返回空内容，避免 SSE 与 Telegram 入口误显示页面不存在。
- `frontend/src/layouts/AdapterLayout.tsx`
  - 删除适配器顶部头卡。
  - 没有页签时不再渲染空 tab 条。
  - 未登记的适配器直接显示页面不存在，不再请求后端详情。
- `frontend/src/pages/adapter/AdapterTabPage.tsx`
  - 直接访问适配器根路径时回落到该适配器第一个保留页签。
- `frontend/src/router/index.tsx`
  - `/adapters` 默认跳转到 OneBot 配置页。
- 删除旧主页与高级组件文件。
- 删除不再使用的主页/高级翻译键。

## 验证

- `pnpm --dir frontend exec tsc --noEmit`
- `pnpm --dir frontend build`
