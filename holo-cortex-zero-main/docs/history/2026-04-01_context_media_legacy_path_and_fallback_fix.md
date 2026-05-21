# 2026-04-01 上下文媒体旧路径兼容与 fallback 错误显式化热修

## 现象

- 新一轮报错不再是 OneBot 发送链路
- 上下文组装阶段出现：`LLM media policy image materialize failed ... image path not found: /path/to<CONTAINER_WORKSPACE_DIR>/hpc_shared/...`
- 主模型组返回空结果后，fallback 仅打印 `Fallback 模型组也失败:`，错误正文缺失，排障信息不足

## 根因

- 历史消息 / 记忆中的图片段 `local_path` 仍保留旧宿主绝对路径，例如 `/path/to<CONTAINER_WORKSPACE_DIR>/hpc_shared/...`
- `ContextWindowManager` 在构造 `MessagePart(type=image, url=...)` 时，提示文案已归一化为 `<CONTAINER_WORKSPACE_DIR>/...`，但真正交给 LLM 路由读取的仍是旧绝对路径
- 运行态容器无法直接访问该旧宿主绝对路径，因此媒体物化降级
- `LLMRouter.call_with_fallback()` 对异常只打印 `str(exc)`，当上游异常字符串为空时，日志没有足够上下文

## 修复

- 仅修改：
  - `holo_cortex_zero/services/context_window/manager.py`
  - `holo_cortex_zero/services/llm/router.py`
- 在上下文管理器增加单一兼容 helper：
  - 主干：优先使用当前运行态可访问路径
  - 兼容：仅当命中旧绝对路径且文件不存在时，按工作区锚点 `holo-cortex-zero-main` / `hpc_shared` / `self_image` / `emoji` 重写到当前 `WORKSPACE_ROOT`
  - 若命中历史运行态媒体目录 `uploads` / `quarantine_uploads` / `tmp` / `backups` / `system` / `napcat_data`，则重写到当前 `DATA_DIR`
- 图片与文件段共用同一套路径重写 helper，避免每条链路各写一份兼容分支
- fallback / primary 调用失败日志改为显式打印 `group`、`model`、`protocol`、异常类型与 `repr(exc)`，并带 `exc_info=True`

## 验证

- `python3 -m py_compile holo_cortex_zero/services/context_window/manager.py holo_cortex_zero/services/llm/router.py`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`
- 在 QQ/TG 直接发起一次包含历史图片上下文的对话，确认不再出现旧 `hpc_shared` 绝对路径找不到
- 若 fallback 再失败，日志应至少带出异常类型与 `repr`

## 回滚点

- 本次热修应独立提交，可按提交哈希单独回退
