# 2026-05-14 Qwen3.6-Queen-27B 替换 MeroMero 本地多模态后端

## 目标

按用户要求直接将现有 `meromero-gguf.service` 生产入口从 `G4-MeroMero-31B` 切换为 `Qwen3.6-Queen-27B` 多模态 GGUF，不新建并行生产服务，不改变 HCZ 原有本地模型组路由结构。

## 下载权重

远端服务器：`hcz`，SSH：`ubuntu@<PUBLIC_SERVER_IP>:<HCZ_SSH_PORT>`。

目录：`/path/to/services/qwen35_stack/models-gguf`

新增文件：

- `Qwen3.6-Queen-27B-Q4_K.gguf`
  - 来源：`aifeifei798/Qwen3.6-Queen-27B-GGUF`
  - 实际大小：`16547398752` bytes
  - 约 `15.41 GiB`
- `mmproj-Qwen3.6-Queen-27b-BF16.gguf`
  - 来源：`aifeifei798/Qwen3.6-Queen-27B-GGUF`
  - 实际大小：`931145856` bytes
  - 约 `0.87 GiB`

下载前 HEAD 证据：

- 主模型 `Content-Length: 16547398752`
- mmproj `Content-Length: 931145856`

磁盘空间证据：

- `/dev/mapper/ubuntu--vg-ubuntu--lv` 总量 `936G`，下载前可用约 `790G`。

## 远端服务变更

文件：`/path/to/services/qwen35_stack/run/start_meromero_gguf.sh`

保留参数：

- `HOST=<REMOTE_MODEL_LOOPBACK_HOST>`
- `PORT=<REMOTE_MODEL_LOOPBACK_PORT>`
- `CTX=36352`
- `BATCH=384`
- `UBATCH=384`
- `PARALLEL=2`
- `--cache-prompt`
- `-cpent 512`
- `--reasoning auto`
- `--reasoning-format deepseek`
- `--api-key <LOCAL_MODEL_API_KEY>`

替换参数：

```bash
MODEL_PATH=/path/to/services/qwen35_stack/models-gguf/Qwen3.6-Queen-27B-Q4_K.gguf
MMPROJ_PATH=/path/to/services/qwen35_stack/models-gguf/mmproj-Qwen3.6-Queen-27b-BF16.gguf
--alias qwen36-queen-27b-mm-q4
```

启动后进程证据：

```text
llama-server -m /path/to/services/qwen35_stack/models-gguf/Qwen3.6-Queen-27B-Q4_K.gguf \
  --mmproj /path/to/services/qwen35_stack/models-gguf/mmproj-Qwen3.6-Queen-27b-BF16.gguf \
  --host <REMOTE_MODEL_LOOPBACK_HOST> --port <REMOTE_MODEL_LOOPBACK_PORT> -ngl 999 -fa on -c 36352 -b 384 -ub 384 -np 2 \
  --jinja --reasoning auto --reasoning-format deepseek --cache-prompt -cpent 512 \
  --alias qwen36-queen-27b-mm-q4 --api-key <LOCAL_MODEL_API_KEY>
```

## HCZ 配置变更

文件：`/path/to/runtime-data/configs/holo-cortex-zero.yaml`

仅替换两个本地组的 `CHAT_MODEL`：

- `meromero-31b-resident.CHAT_MODEL`
  - `meromero-31b-mm-int4` -> `qwen36-queen-27b-mm-q4`
- `meromero-31b-resident-think.CHAT_MODEL`
  - `meromero-31b-mm-int4` -> `qwen36-queen-27b-mm-q4`

保留关键业务参数：

- `BASE_URL: http://<LOCAL_OPENAI_COMPAT_HOST>:<LOCAL_OPENAI_COMPAT_PORT>/v1`
- `API_KEY: <LOCAL_MODEL_API_KEY>`
- `IMAGE_MAX_COUNT: 3`（普通 resident）
- `local_chat_image_max_long_edge: 1024`（普通 resident）
- `id_slot: 0` / `id_slot: 1` 隔离不变
- `meromero-31b-resident-think.REASONING_MODE: high` 不变
- `meromero-31b-resident-think.MAX_OUTPUT_TOKENS: 4500` 不变

## 生效命令

远端模型服务：

```bash
systemctl --user restart meromero-gguf.service
```

HCZ 本体：

```bash
cd /path/to/deploy-root
sudo docker compose -f docker-compose.yml up -d --no-deps --force-recreate holo_cortex_zero
```

## 验证结果

远端模型服务：

```text
systemctl --user is-active meromero-gguf.service -> active
```

模型列表：

```text
GET http://<REMOTE_MODEL_LOOPBACK_HOST>:<REMOTE_MODEL_LOOPBACK_PORT>/v1/models -> HTTP 200
id: qwen36-queen-27b-mm-q4
capabilities: completion, multimodal
meta.n_params: 26895998464
meta.size: 16536406016
```

HCZ 容器：

```text
holo_cortex_zero -> Up, healthy
```

## 回滚点

远端脚本已备份：

```text
/path/to/services/qwen35_stack/run/start_meromero_gguf.sh.bak-queen-YYYYMMDD-HHMMSS
```

回滚方式：

1. 恢复远端脚本中的 `MODEL_PATH`、`MMPROJ_PATH`、`--alias` 为 MeroMero 旧值。
2. 恢复 HCZ YAML 中两个本地组的 `CHAT_MODEL: meromero-31b-mm-int4`。
3. 重启 `meromero-gguf.service`。
4. 仅重建 `holo_cortex_zero` 容器，不动依赖服务。

## 风险

- 服务名仍叫 `meromero-gguf.service`，这是为了不新增生产入口和 systemd 主干；实际模型已由 `/v1/models` 证明确认为 Queen。
- HCZ 模型组 key 仍叫 `meromero-31b-resident*`，这是为了不改业务引用；缓存键中的 `CHAT_MODEL` 已改为 `qwen36-queen-27b-mm-q4`，避免与旧 MeroMero 模型身份混用。
- 未做生成质量测试；用户已明确表示已经测试过很好用，本次只执行替换更新与存活验证。
