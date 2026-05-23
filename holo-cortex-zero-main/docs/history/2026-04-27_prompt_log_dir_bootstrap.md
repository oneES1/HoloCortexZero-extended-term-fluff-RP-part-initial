# 2026-04-27 Prompt 日志目录启动补齐

## 背景

运行态出现“所有 API 模型组不可用”，最近日志显示主模型组与 fallback 模型组都在调用前失败，异常为：

- `FileNotFoundError: [Errno 2] No such file or directory: '<CONTAINER_DATA_DIR>/logs/prompts'`

这不是模型 API key 或代理不可用，而是 prompt dump 目录缺失导致 LLM 调用前日志写入失败，进而被 fallback 链路包装成模型组失败。

## 本次修改

在 `holo_cortex_zero/core/os_env.py` 的运行期目录初始化中补齐：

- `APP_LOG_DIR`
- `PROMPT_LOG_DIR`
- `PROMPT_ERROR_LOG_DIR`
- `MEMORY_LOG_DIR`

其中 `MEMORY_LOG_DIR` 是记忆检索、记忆收集、记忆整理等 payload dump 的根目录，具体 scope 子目录仍由业务写入时按需创建。

保留原有上传目录权限处理，不改模型组、代理、LLM 协议、上下文拼装逻辑。

## 风险

风险很低，只是在启动时确保日志目录存在。若目录已存在，`exist_ok=True` 不会改变既有内容。

## 回滚点

如需回滚，撤销以下文件中的本次修改：

- `holo_cortex_zero/core/os_env.py`
- `docs/2026-04-27_prompt_log_dir_bootstrap.md`
