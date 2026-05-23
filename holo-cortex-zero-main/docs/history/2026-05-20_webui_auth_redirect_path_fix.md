# 2026-05-20 WebUI 登录态失效跳转路径修复

## 问题

修复 NapCat 后继续从 HCZ 主 UI 进入时仍显示白屏。

## 复查证据

短尾日志显示用户点击后：

- `GET /api/config/get/adapter_onebot_v11/NAPCAT_ACCESS_URL` 返回 `401`
- `GET /api/adapters/onebot_v11/container/napcat-token` 返回 `401`
- 浏览器随后请求 `/webui/`

这说明 HCZ WebUI 管理员登录态已经失效，前端无法取得 NapCat iframe 地址与 WebUI token。

## 根因

前端 axios 在非登录接口收到 `401` 时执行：

```ts
window.location.href = '/#/login'
```

但当前生产 WebUI 挂载在 `/webui`，正确登录页是 `/webui/#/login`。跳转到根路径 hash 会经过后端根路径重定向和静态挂载路径差异，容易表现为空白或错误页面。

## 修改

- 将 401 登出跳转改为 `/webui/#/login`。

## 影响范围

- 只影响 WebUI 管理员登录态失效后的跳转路径。
- 不修改 NapCat、OneBot、LLM 协议链路。
