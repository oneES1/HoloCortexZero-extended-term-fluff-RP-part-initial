# 2026-04-01 自设图系统 OsEnv 导入热修

## 现象

- 运行日志出现：`自设图系统集成获取失败: name 'OsEnv' is not defined`
- 自设图印象图注入与参考路径导出失效

## 根因

- `holo_cortex_zero/services/agent/run_agent_v2.py` 中的 `_get_self_image_system_root()` 使用了 `OsEnv.WORKSPACE_ROOT`
- 该文件顶部未导入 `OsEnv`
- 运行到自设图系统路径展开主干时触发 `NameError`，随后被外层捕获并记录错误日志

## 修复

- 仅在 `holo_cortex_zero/services/agent/run_agent_v2.py` 补充 `from holo_cortex_zero.core.os_env import OsEnv`
- 不改动自设图配置结构、不新增兼容分支、不改动消息主链路

## 验证

- `python -m py_compile /path/to/source-root/holo_cortex_zero/services/agent/run_agent_v2.py`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`
- 重放或再次触发自设图链路，确认不再出现 `OsEnv is not defined`

## 回滚点

- 本次修复应独立提交，可按提交哈希单独回退
