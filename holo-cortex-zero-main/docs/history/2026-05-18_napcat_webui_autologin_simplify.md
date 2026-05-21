# 2026-05-18 NapCat WebUI 自动登录与误导按钮清理

## 问题

NapCat 管理页顶部同时展示：

- `前往 NapCat`
- `复制 OneBot Key`
- `复制 NapCat Token`

其中 `复制 OneBot Key` 面向的是 OneBot 反向 WebSocket 鉴权，不是用户进入 NapCat WebUI 的登录凭据。对普通用户来说，这个按钮只会制造误导。

同时，页面 iframe 直接加载 `NAPCAT_ACCESS_URL`，没有自动拼入 WebUI token，导致用户仍需理解 token 并手动复制。

## 现状证据

- 页面文件：`frontend/src/pages/adapter/onebot_v11/napcat.tsx`
- 误导来源：页面主动查询 `getOneBotToken()` 并渲染 `copyOnebotKey`
- WebUI token 来源：`/adapters/onebot_v11/container/napcat-token`

## 修改

1. 删除 NapCat 页面上的 OneBot key 查询与按钮展示。
2. 使用 `napcat-token` 自动为 `NAPCAT_ACCESS_URL` 追加 `?token=...`。
3. iframe 与“前往 NapCat”按钮统一使用自动登录后的 URL。
4. 删除页面上的 `复制 NapCat Token` 旧交互，只保留直接进入 WebUI。
5. 删除已无前端使用的 `getOneBotToken()` API 封装。
6. 清理中英文 locale 中对应的 OneBot key 与复制 token 文案。

## 结果

- 用户进入 NapCat 页时，默认直接进入带 token 的 WebUI。
- 新窗口打开 NapCat 时，同样直接进入带 token 的 WebUI。
- 页面不再出现与 WebUI 登录无关的 OneBot key 按钮。

## 验证

- 前端构建通过。
- 页面源码只保留 NapCat WebUI token 相关交互。
- 不修改 OneBot 协议主干与后端容器运行参数。
