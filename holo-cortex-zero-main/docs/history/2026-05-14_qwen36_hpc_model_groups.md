# 2026-05-14 qwen3.6 hpc 本地模型组接入

## 目标

按用户要求只新增 hpc 上已启动的 qwen3.6 本地模型组，保留现有两个 `meromero-31b-*` 本地组不变。

## 事实证据

- hpc qwen3.6 入口经腾讯机本地通道暴露为 `http://<HOST_GATEWAY_IP>:<HPC_MODEL_TUNNEL_PORT>/v1`。
- `/v1/models` 返回模型名：`Qwen3.6-Queen-27B-Q8_0.gguf`。
- 运行态配置文件：`/path/to/runtime-data/configs/holo-cortex-zero.yaml`。
- 原有 mero 组保持：
  - `meromero-31b-resident` -> `http://<LOCAL_OPENAI_COMPAT_HOST>:<LOCAL_OPENAI_COMPAT_PORT>/v1`，`id_slot=0`
  - `meromero-31b-resident-think` -> `http://<LOCAL_OPENAI_COMPAT_HOST>:<LOCAL_OPENAI_COMPAT_PORT>/v1`，`id_slot=1`

## 变更

仅向 `MODEL_GROUPS` 追加 9 个新组：

- `qwen36-queen-27b-hpc-slot0` -> `id_slot=0`
- `qwen36-queen-27b-hpc-slot1` -> `id_slot=1`
- `qwen36-queen-27b-hpc-slot2` -> `id_slot=2`
- `qwen36-queen-27b-hpc-slot3` -> `id_slot=3`
- `qwen36-queen-27b-hpc-slot4` -> `id_slot=4`
- `qwen36-queen-27b-hpc-slot5` -> `id_slot=5`
- `qwen36-queen-27b-hpc-slot6` -> `id_slot=6`
- `qwen36-queen-27b-hpc-slot7` -> `id_slot=7`
- `qwen36-queen-27b-hpc-slot8` -> `id_slot=8`

每个新组统一配置：

- `CHAT_MODEL=Qwen3.6-Queen-27B-Q8_0.gguf`
- `BASE_URL=http://<HOST_GATEWAY_IP>:<HPC_MODEL_TUNNEL_PORT>/v1`
- `WIRE_API=chat`
- `EXTRA_BODY={"wire_api":"chat","id_slot":N,"cache_prompt":true}`
- `REPLAY_REASONING_CONTENT=true`

## 验证

执行：

```bash
curl -sS --max-time 5 http://<HOST_GATEWAY_IP>:<HPC_MODEL_TUNNEL_PORT>/v1/models
```

返回包含：

- `id=Qwen3.6-Queen-27B-Q8_0.gguf`
- `owned_by=llamacpp`
- `n_ctx=262144`
- `n_params=26895998464`

执行 YAML 断言：

```bash
cd /path/to/source-root
uv run python - <<'PY'
import json, yaml
p='/path/to/runtime-data/configs/holo-cortex-zero.yaml'
with open(p,'r',encoding='utf-8') as f:
    cfg=yaml.safe_load(f)
mg=cfg['MODEL_GROUPS']
for i in range(9):
    name=f'qwen36-queen-27b-hpc-slot{i}'
    g=mg[name]
    eb=json.loads(g['EXTRA_BODY'])
    assert g['BASE_URL']=='http://<HOST_GATEWAY_IP>:<HPC_MODEL_TUNNEL_PORT>/v1'
    assert g['CHAT_MODEL']=='Qwen3.6-Queen-27B-Q8_0.gguf'
    assert eb['id_slot']==i
    assert eb['cache_prompt'] is True
print('qwen36_slot_assertions_ok', 9)
PY
```

结果：`qwen36_slot_assertions_ok 9`。

容器内确认：

```bash
docker exec holo_cortex_zero /app/.venv/bin/python - <<'PY'
import json, yaml
p="<CONTAINER_DATA_DIR>/configs/holo-cortex-zero.yaml"
with open(p,"r",encoding="utf-8") as f:
    cfg=yaml.safe_load(f)
mg=cfg["MODEL_GROUPS"]
print("qwen36_groups", sum(1 for k in mg if k.startswith("qwen36-queen-27b-hpc-slot")))
print("slot0", json.loads(mg["qwen36-queen-27b-hpc-slot0"]["EXTRA_BODY"])["id_slot"])
print("slot8", json.loads(mg["qwen36-queen-27b-hpc-slot8"]["EXTRA_BODY"])["id_slot"])
print("mero", mg["meromero-31b-resident"]["BASE_URL"], mg["meromero-31b-resident-think"]["BASE_URL"])
PY
```

结果：

- `qwen36_groups 9`
- `slot0 0`
- `slot8 8`
- `mero http://<LOCAL_OPENAI_COMPAT_HOST>:<LOCAL_OPENAI_COMPAT_PORT>/v1 http://<LOCAL_OPENAI_COMPAT_HOST>:<LOCAL_OPENAI_COMPAT_PORT>/v1`

## 回滚点

- 删除运行态配置中的 `qwen36-queen-27b-hpc-slot0` 到 `qwen36-queen-27b-hpc-slot8`。
- 不需要改动 `meromero-31b-resident` / `meromero-31b-resident-think`。

## 2026-05-14 API 链路收敛为 mero 同型隧道

用户明确要求 hpc qwen3.6 也采用 mero 同型链路：真实 `llama-server` 只绑定远端本机 loopback，腾讯云宿主机通过 SSH 本地端口转发提供给 HCZ 容器访问。

当前链路：

```text
HCZ 容器
-> http://<HOST_GATEWAY_IP>:<HPC_MODEL_TUNNEL_PORT>/v1
-> 腾讯云宿主机 SSH -L 隧道
-> hpc SSH 22
-> hpc 本机 <REMOTE_MODEL_LOOPBACK_HOST>:<REMOTE_MODEL_LOOPBACK_PORT>
-> llama-server / Qwen3.6-Queen-27B-Q8_0.gguf
```

腾讯云宿主机监听：

```text
<HOST_GATEWAY_IP>:<HPC_MODEL_TUNNEL_PORT> users:(("ssh",pid=328968,fd=4))
```

隧道命令：

```text
/usr/bin/ssh -NT -i /path/to/ssh-keys/hcz_qwen36_hpc_tunnel_ed25519 \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -o StrictHostKeyChecking=no \
  -L <HOST_GATEWAY_IP>:<HPC_MODEL_TUNNEL_PORT>:<REMOTE_MODEL_LOOPBACK_HOST>:<REMOTE_MODEL_LOOPBACK_PORT> ubuntu@<PUBLIC_SERVER_IP>
```

hpc 远端 user systemd 服务：

```text
qwen36-queen-27b-gguf.service
Active: active (running)
Main PID: 4096106
```

hpc 远端监听：

```text
<REMOTE_MODEL_LOOPBACK_HOST>:<REMOTE_MODEL_LOOPBACK_PORT> users:(("llama-server",pid=4096106,fd=16))
```

启动核心参数：

```text
--host <REMOTE_MODEL_LOOPBACK_HOST> --port <REMOTE_MODEL_LOOPBACK_PORT>
-c 1048576 -n -1 -np 4 -b 8192 -ub 1024
--threads-http 64
--reasoning on
--reasoning-budget -1
--reasoning-format deepseek
--cache-prompt
--cache-reuse 512
--cache-ram -1
--cache-idle-slots
--ctx-checkpoints 4096
--checkpoint-every-n-tokens 512
--slot-save-path /path/to/cache/llama_cache/qwen3.6-queen-27b-q8-mm
```

保护性验证：

```text
meromero 隧道未改变：
<HOST_GATEWAY_IP>:<LOCAL_OPENAI_COMPAT_PORT> users:(("ssh",pid=356476,fd=4))

meromero 容器内健康检查：
http://<LOCAL_OPENAI_COMPAT_HOST>:<LOCAL_OPENAI_COMPAT_PORT>/health -> 200 {"status":"ok"}

qwen3.6 容器内健康检查：
http://<HOST_GATEWAY_IP>:<HPC_MODEL_TUNNEL_PORT>/health -> 200 {"status":"ok"}
http://<HOST_GATEWAY_IP>:<HPC_MODEL_TUNNEL_PORT>/v1/models -> 200 Qwen3.6-Queen-27B-Q8_0.gguf
```

## 2026-05-14 可用性检查

执行范围：只做轻量状态与最小请求检查，不重启、不改配置、不读取大日志。

基础状态：

```text
git status: clean
holo_cortex_zero: Up, healthy
hcz_qdrant: Up
hcz_postgres: Up
hcz_napcat: Up
```

隧道状态：

```text
<HOST_GATEWAY_IP>:<LOCAL_OPENAI_COMPAT_PORT> users:(("ssh",pid=356476,fd=4))
<HOST_GATEWAY_IP>:<HPC_MODEL_TUNNEL_PORT> users:(("ssh",pid=328968,fd=4))
```

hpc 远端 qwen3.6 状态：

```text
qwen36-queen-27b-gguf.service: active
<REMOTE_MODEL_LOOPBACK_HOST>:<REMOTE_MODEL_LOOPBACK_PORT> users:(("llama-server",pid=4096106,fd=16))
```

容器内端点：

```text
http://<LOCAL_OPENAI_COMPAT_HOST>:<LOCAL_OPENAI_COMPAT_PORT>/health -> 200 {"status":"ok"}
http://<LOCAL_OPENAI_COMPAT_HOST>:<LOCAL_OPENAI_COMPAT_PORT>/v1/models -> 200 meromero-31b-mm-int4
http://<HOST_GATEWAY_IP>:<HPC_MODEL_TUNNEL_PORT>/health -> 200 {"status":"ok"}
http://<HOST_GATEWAY_IP>:<HPC_MODEL_TUNNEL_PORT>/v1/models -> 200 Qwen3.6-Queen-27B-Q8_0.gguf
```

HCZ 运行态模型组：

```text
qwen36_groups 9
qwen36-queen-27b-hpc-slot0..slot8 -> id_slot 0..8, cache_prompt true, REPLAY_REASONING_CONTENT true
meromero-31b-resident -> http://<LOCAL_OPENAI_COMPAT_HOST>:<LOCAL_OPENAI_COMPAT_PORT>/v1
meromero-31b-resident-think -> http://<LOCAL_OPENAI_COMPAT_HOST>:<LOCAL_OPENAI_COMPAT_PORT>/v1
```

OpenAI-compatible 直连普通生成：

```text
slot: id_slot=1
status: 200
finish_reason: stop
content_prefix: OK
content_len: 2
reasoning_len: 127
prompt_tokens: 19
completion_tokens: 33
predicted_per_second: 38.485
```

OpenAI-compatible 直连 tool call：

```text
slot: id_slot=2
status: 200
finish_reason: tool_calls
tool_calls_len: 1
tool_call: get_gpu_status
arguments: {"detail":"full"}
reasoning_len: 292
completion_tokens: 104
predicted_per_second: 42.169
```

HCZ Router 主干调用：

```text
model_group: qwen36-queen-27b-hpc-slot3
protocol: chat
finish_reason: stop
text_prefix: OK
text_len: 2
reasoning_len: 713
tool_calls_len: 0
```

结论：

```text
qwen3.6 hpc API 链路可用。
HCZ 模型组已加载。
普通生成可用。
reasoning_content 分离可用。
OpenAI-compatible tool_calls 可用。
HCZ Router chat 主干可用。
mero 本地组健康且链路未变。
```
