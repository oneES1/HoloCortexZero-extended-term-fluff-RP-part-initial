# 2026-05-10 本地 qwen 模型组 id_slot 绑定

## 背景

主 LLM qwen35-27b-mm-int4 已经在 chat payload 中携带 `cache_prompt=true`，但真实 trace 仍出现命中不稳定：

- trace `2328`: `prompt_tokens=3680`, `cached_tokens=2640`, `duration_ms=2723`
- trace `2329`: `prompt_tokens=3511`, `cached_tokens=0`, `duration_ms=5535`

同一 `2329` 请求 dump 复放时，本地服务可稳定返回近满命中：

- `noslot-1`: `prompt=3511`, `cached=3510`, `ms=996`
- `noslot-2`: `prompt=3511`, `cached=3510`, `ms=947`
- `slot0-1`: `prompt=3511`, `cached=3510`, `ms=836`
- `slot0-2`: `prompt=3511`, `cached=3510`, `ms=856`

本地 qwen 服务 `/props` 返回 `total_slots=2`，因此当前只能安全使用 `id_slot=0` 与 `id_slot=1`。

## 修改

运行态配置文件：`/path/to/runtime-data/configs/holo-cortex-zero.yaml`

- `meromero-31b-resident` 的 `EXTRA_BODY` 增加 `"id_slot": 0`
- `meromero-31b-resident-think` 的 `EXTRA_BODY` 增加 `"id_slot": 1`

未修改代码主干；仍通过模型组通用 `EXTRA_BODY -> extra_params -> chat payload` 透传。

## 验证

后端按最小范围重载：

```bash
cd /path/to<CONTAINER_WORKSPACE_DIR>
printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --no-deps --force-recreate holo_cortex_zero
```

容器状态：`holo_cortex_zero Up (healthy)`。

运行态解析验证：

- `meromero-31b-resident`: `id_slot=0`, `wire=chat`, `image_max=3`
- `meromero-31b-resident-think`: `id_slot=1`, `wire=chat`, `image_max=0`

## 回滚

备份文件：`/path/to/runtime-data/backups/configs/holo-cortex-zero.yaml.before_id_slot_20260510_184446`

回滚命令：

```bash
cp /path/to/runtime-data/backups/configs/holo-cortex-zero.yaml.before_id_slot_20260510_184446 /path/to/runtime-data/configs/holo-cortex-zero.yaml
cd /path/to<CONTAINER_WORKSPACE_DIR>
printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --no-deps --force-recreate holo_cortex_zero
```

## 风险

- 当前本地 qwen 服务只有 2 个 slot；如果未来要 4 个模型组分别绑定 4 个 `id_slot`，必须先扩 qwen 服务 `total_slots`。
- 主模型固定 `id_slot=0`、think 固定 `id_slot=1` 会提升各自缓存稳定性，但并发请求会固定竞争对应槽位。
