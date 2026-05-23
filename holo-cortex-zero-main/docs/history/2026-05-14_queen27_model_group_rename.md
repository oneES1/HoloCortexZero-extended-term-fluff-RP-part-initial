# 2026-05-14 Queen27 本地模型组重命名

## 目标

用户要求不只替换底层权重，也同步修改 HCZ 模型组名称，避免继续以 `meromero-31b-*` 暴露当前 Queen 后端。

## 变更

运行态配置文件：`/path/to/runtime-data/configs/holo-cortex-zero.yaml`

重命名：

- `meromero-31b-resident` -> `qwen36-queen-27b-resident`
- `meromero-31b-resident-think` -> `qwen36-queen-27b-resident-think`
- `TIMELINE_MODEL_GROUP` 同步改为 `qwen36-queen-27b-resident-think`

保留参数不变：

- `CHAT_MODEL: qwen36-queen-27b-mm-q4`
- `BASE_URL: http://<LOCAL_OPENAI_COMPAT_HOST>:18081/v1`
- `API_KEY: <LOCAL_MODEL_API_KEY>`
- resident 普通组：`IMAGE_MAX_COUNT=3`
- resident 普通组：`local_chat_image_max_long_edge=1024`
- 普通组：`id_slot=0`
- think 组：`id_slot=1`
- think 组：`IMAGE_MAX_COUNT=0`
- think 组：`REASONING_MODE=high`

## 生效命令

只重建 HCZ 本体，不动依赖服务：

```bash
cd /path/to<CONTAINER_WORKSPACE_DIR>
sudo docker compose -f docker-compose.yml up -d --no-deps --force-recreate holo_cortex_zero
```

## 验证

容器健康：

```text
holo_cortex_zero -> Up, healthy
```

容器内配置加载结果：

```text
qwen36-queen-27b-resident qwen36-queen-27b-mm-q4 http://<LOCAL_OPENAI_COMPAT_HOST>:18081/v1 3 {"wire_api": "chat", "thinking": {"type": "disabled"}, "local_chat_image_max_long_edge": 1024, "id_slot": 0}
qwen36-queen-27b-resident-think qwen36-queen-27b-mm-q4 http://<LOCAL_OPENAI_COMPAT_HOST>:18081/v1 0 {"wire_api": "chat", "thinking": {"type": "disabled"}, "id_slot": 1}
TIMELINE_MODEL_GROUP qwen36-queen-27b-resident-think
old_present False
```

## 回滚

如需回滚名称：

- `qwen36-queen-27b-resident` -> `meromero-31b-resident`
- `qwen36-queen-27b-resident-think` -> `meromero-31b-resident-think`
- `TIMELINE_MODEL_GROUP` 同步恢复旧组名
- 重建 `holo_cortex_zero` 本体即可

## 风险

- 旧模型组 key 不再存在；任何外部脚本如果硬编码 `meromero-31b-resident*` 会失败。
- HCZ 主配置内当前已同步 `TIMELINE_MODEL_GROUP`，本次未发现主配置仍引用旧 key。
