# Dashboard 红错历史尾追窗口调整为 5MB

## 本次调整
- 将日志文件尾追窗口从 `2MB` 提升到 `5MB`。
- 保持“只追尾部、不全量读取”的安全策略不变。
- 这样 Dashboard 红错历史能覆盖更长一段时间的文件日志，而不是只看到较短的最近窗口。

## 影响文件
- `holo_cortex_zero/core/logger.py`

## 验证
- `python3 -m py_compile holo_cortex_zero/core/logger.py holo_cortex_zero/routers/logs.py`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 回滚点
- `26a847f` `fix(logs): document file-tail history fix`
