# 2026-05-10 llama.cpp SWA checkpoint 缓存修复

## 背景

主 LLM 当时使用的对外模型名 `qwen35-27b-mm-int4` 已经传入 `cache_prompt=true` 与 `id_slot=0`，但真实请求仍出现缓存归零。该服务实际加载的是 MeroMero GGUF，后续已把对外 alias 统一改为 `meromero-31b-mm-int4`，避免继续被历史 qwen 名称误导。

最新 trace 例子：

- `2331`: `prompt_tokens=4521`, `cached_tokens=3227`, `duration_ms=4391`
- `2332`: `prompt_tokens=4118`, `cached_tokens=0`, `duration_ms=6486`

复放控制在同一 `id_slot=0` 上复现：

- 修复前：`2331 -> 2332` 的 `2332` 为 `cached=0`
- 但重复同一个 `2332` 可达 `cached=4117/4118`

## 根因

实际后端不是 vLLM，而是 hcz 工作站上的 llama.cpp `llama-server`：

```text
/path/to/services/llama_cpp/llama.cpp/build/bin/llama-server ... --mmproj ... -np 2 --cache-prompt --alias qwen35-27b-mm-int4
```

服务端日志显示，`llama-server` 已经计算出可复用前缀，但随后因 SWA / checkpoint 缺失强制清零：

```text
n_past = 3311, slot.prompt.tokens.size() = 4549, seq_id = 0, pos_min = 3013, n_swa = 1024
Checking checkpoint ...
forcing full prompt re-processing due to lack of cache data
n_tokens = 0, memory_seq_rm [0, end)
```

因此问题不是 HCZ 没传 `cache_prompt` / `id_slot`，也不是业务动态指导块本身错误；真实失效点是 llama.cpp SWA KV 窗口无法恢复较早的共同前缀。

## 修改

运行态文件：`/path/to/services/qwen35_stack/run/start_meromero_gguf.sh`

- 增加 `-cpent 512`
- 含义：prefill 期间每 512 tokens 创建 context checkpoint，让 SWA 场景下更容易恢复较早共同前缀。

曾尝试 `--swa-full`，但服务启动失败，已自动回滚，不保留该参数。

当前启动参数关键片段：

```text
--cache-prompt \
-cpent 512 \
--alias meromero-31b-mm-int4 \
```

2026-05-10 后续命名修正：

- hcz 工作站 `/path/to/services/qwen35_stack/run/start_meromero_gguf.sh`：`--alias qwen35-27b-mm-int4` 改为 `--alias meromero-31b-mm-int4`。
- HCZ 运行态 `/path/to/runtime-data/configs/holo-cortex-zero.yaml`：`meromero-31b-resident` 与 `meromero-31b-resident-think` 的 `CHAT_MODEL` 改为 `meromero-31b-mm-int4`。
- 保持模型组名、`BASE_URL`、`API_KEY`、`id_slot=0/1` 不变。

## 验证

服务重载后进程参数确认：

```text
llama-server ... --cache-prompt -cpent 512 --alias meromero-31b-mm-int4
```

同一真实 dump 复放结果：

- `2331-seed`: `prompt=4521`, `cached=0`, `ms=7074`
- `2332-probe`: `prompt=4118`, `cached=3311`, `ms=3133`
- `2332-repeat`: `prompt=4118`, `cached=4117`, `ms=1039`

对比修复前 `2332-probe cached=0`，现在同链路达到 `cached=3311/4118`。

命名修正后验证：

- `/v1/models` 返回 `id=meromero-31b-mm-int4`，`aliases=["meromero-31b-mm-int4"]`。
- HCZ 容器内配置读取结果：
  - `meromero-31b-resident CHAT_MODEL=meromero-31b-mm-int4 EXTRA_BODY.id_slot=0`
  - `meromero-31b-resident-think CHAT_MODEL=meromero-31b-mm-int4 EXTRA_BODY.id_slot=1`
- 经 `<HOST_GATEWAY_IP>:18081` 直连新模型名请求成功，响应 `model=meromero-31b-mm-int4`。
- llama.cpp 单模型服务对任意请求 `model` 都会路由到当前唯一加载模型并回显当前 alias；因此旧名请求仍可能成功，但响应模型名已是 `meromero-31b-mm-int4`。

## 回滚

脚本备份：

- `/path/to/services/qwen35_stack/run/start_meromero_gguf.sh.bak_cpent_20260510_144525`
- `/path/to/services/qwen35_stack/run/start_meromero_gguf.sh.bak_swa_cache_20260510_144501`

回滚命令：

```bash
ssh -p <HCZ_SSH_PORT> ubuntu@<PUBLIC_SERVER_IP>
cp /path/to/services/qwen35_stack/run/start_meromero_gguf.sh.bak_cpent_20260510_144525 /path/to/services/qwen35_stack/run/start_meromero_gguf.sh
systemctl --user restart meromero-gguf.service
```

## 风险

- 更密集 checkpoint 会增加内存占用与预填过程中的 checkpoint 维护成本。
- 当前实测目标链路收益明显：`2331 -> 2332` 从 `cached=0` 提升到 `cached=3311`。
- 若后续出现显存/内存压力，可把 `-cpent 512` 放宽为 `1024` 或回滚。
