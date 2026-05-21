# JWT 验签失败日志级别调整

## 背景

API 鉴权依赖在解析请求 token 后，会使用 `JWT_SECRET_KEY` 和配置算法进行 JWT 验签。浏览器携带旧 token、服务重启后默认密钥变化、`.env` 密钥不一致，或外部请求携带无效 token 时，都会进入 `JWTError` 分支。

## 当前逻辑

- `holo_cortex_zero/services/user/deps.py` 优先读取 URL 参数 `token`，没有时读取 `Authorization: Bearer ...`。
- `jwt.decode(...)` 验签失败会统一抛出 `InvalidCredentialsError`。
- 失败原因只用于运行日志定位，不改变对客户端返回的鉴权错误行为。

## 本次最小修改

- 将 `JWT validation failed: ...` 从 `debug` 提升为 `info`。
- 不修改 token 来源解析、JWT 密钥、算法、异常类型和接口鉴权行为。

## 影响范围

- 只影响 JWT 验签失败时的日志可见性。
- 无效 token 请求可能比以前更容易在 info 级别日志中被看到。
- 不影响正常登录、签发 token、用户查询或权限判断。

## 验证记录

- `python3 -m py_compile holo_cortex_zero/services/user/deps.py`
- `git diff --check`

## 回滚点

回滚本次提交即可恢复为 debug 级别；无需数据库或配置回滚。
