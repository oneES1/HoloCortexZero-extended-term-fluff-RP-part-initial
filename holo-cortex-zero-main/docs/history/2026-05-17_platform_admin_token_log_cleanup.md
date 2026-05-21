# Platform Admin Token Log Cleanup

## 背景

开源友好与安全审查发现 WebUI 管理员认证会在 debug 日志中打印 URL token 原文和处理后的 token。即使 debug 日志默认不一定开启，排障时也可能造成 token 泄漏。

## 变更

- 删除 URL token 原文 debug 日志。
- 删除处理后 token debug 日志。
- 保留不含密钥内容的认证失败排障日志。

## 影响

- 管理员 token 解析逻辑不变。
- URL `token=Bearer ...` 与 `Authorization: Bearer ...` 两种输入路径行为不变。
- 降低 debug 日志泄漏管理员 token 的风险。

## 验证

- `rg` 确认不再存在 `Raw token from URL` 与 `Processed token from URL`。
- `uv run python -m compileall holo_cortex_zero/services/platform_admin.py`
