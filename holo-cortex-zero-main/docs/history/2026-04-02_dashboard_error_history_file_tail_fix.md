# Dashboard 红错历史补齐文件尾追

## 根因
- `/logs` 原先只读取进程内存中的 `deque(maxlen=1000)`。
- 容器重建后，内存日志会清空，Dashboard 上的红错历史即使文件里还在，也查不到。
- 当前 `app.log` 实际存在历史红错，但 `/logs` 未回溯到文件尾部。

## 本次修复
- 在 `core/logger.py` 中增加安全尾读：只读取 `app.log` 尾部最多 `2MB`，不做全量读取。
- 使用统一正则解析日志行，并兼容多行消息拼接。
- `get_log_records()` 改为合并：`文件尾部日志 + 进程内存日志`，再统一做去重、过滤、分页。
- 这样 Dashboard 的红错历史面板可以显示“之前就已经写进日志文件”的错误，而不再只看当前进程内存。

## 影响文件
- `holo_cortex_zero/core/logger.py`

## 验证
- `python3 -m py_compile holo_cortex_zero/core/logger.py holo_cortex_zero/routers/logs.py`
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 回滚点
- `2ade8f8` `chore(dashboard): tighten panel density`
