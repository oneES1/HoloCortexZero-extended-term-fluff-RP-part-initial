# WebUI 单平台管理员登录收口

## 目标

- WebUI 登录只保留平台管理员一条主干：`HCZ_ADMIN_USERNAME` + `HCZ_ADMIN_PASSWORD`。
- 平台管理员只作为 WebUI 鉴权主体存在，不写入 `DBUser`，不占用业务用户管理列表。
- 业务用户继续保留 `adapter_key`、`platform_userid`、`perm_level`、封禁、禁止触发、扩展数据等能力。

## 已删除

- 旧 WebUI 用户登录路由、公开注册、个人信息、注销外壳。
- 旧用户登录服务、旧依赖、旧权限装饰外壳。
- 旧登录 token schema。
- 前端旧登录 API 命名、旧登录响应命名、旧用户信息持久化状态。
- 前端旧认证存储 key 的读取写入和清理钩子。
- 旧用户表密码列和新用户创建时写空密码的逻辑。
- 未使用的旧哈希依赖声明。
- 旧登录模块生成的 Python 缓存文件。

## 当前主干

- 后端平台管理员接口：`/api/admin/login`。
- 前端登录服务：`frontend/src/services/api/auth.ts` 的 `adminAuthApi`。
- 前端登录页：`frontend/src/pages/login/index.tsx`。
- 前端鉴权存储：`frontend/src/stores/auth.ts` 的平台管理员会话持久化 key。
- WebUI 受保护路由依赖：`PlatformAdminPrincipal`，只提供 `username`、`perm_level`、`is_active` 给管理接口鉴权。

## 业务保留边界

- `DBUser` 不是 WebUI 登录账户，是平台消息用户与上下文/记忆业务身份。
- `user_register` 保留，只服务适配器消息入口自动登记平台用户。
- 用户管理中的 `perm_level` 和封禁状态保留，业务接口仍依赖它们。
- 用户管理编辑弹窗里的 `access_key` 是 `SUPER_ACCESS_KEY` 二次确认，不是 WebUI 登录密码。
- OneBot / NapCat 的 WebUI token 是适配器业务令牌，不属于 HCZ WebUI 登录链。

## 2026-05-13 追加残留审查

- 源码排除 `node_modules`、`dist`、`docs` 后扫描：旧 WebUI 登录路由、旧登录 API 名称、旧用户信息状态、旧当前用户参数名均无运行代码命中。
- 反向扫描 `password`：只剩平台管理员登录表单密码、模型供应商密钥遮罩、数据库连接密码、用户管理 `SUPER_ACCESS_KEY` 遮罩等非旧登录用途。
- 实表检查：`public.user` 曾残留旧登录密码列，类型 `varchar(128)`，`NOT NULL`，无默认值；因此源码删字段后必须同步删除运行库列，否则新业务用户注册会失败。
- 运行库清理动作：删除 `public.user` 旧密码列。
- 依赖清理：删除未使用的旧哈希直接依赖，并重算锁文件。

## 验证项

- `uv run python -m compileall -q holo_cortex_zero`
- `pnpm --dir frontend exec tsc --noEmit`
- `pnpm --dir frontend build`
- `GET /api/health` 返回 `200`
- `POST /api/admin/login` 正确密码返回 `200`
- 旧 WebUI 用户登录族接口返回 `404`
- `GET /api/user-manager/list` 返回 `200`

## 回滚点

- 修改前主提交：`bfb2264 fix(auth): purge webui auth storage residue`
