# 2026-04-06 UniAPI `api` host 兼容分支全覆盖

## 背景
- 先前将多个模型组的 `BASE_URL` 从 `https://hk.uniapi.io/v1` 切到 `https://api.uniapi.io/v1`。
- 随后 `Uni-grok-4-1-fast` 的 `/responses` 链路出现 400：上游提示下载到的图片不是有效的 `JPG/PNG/WebP`。
- 排查发现：旧代码里多处兼容分支只识别 `hk.uniapi.io`，切到 `api.uniapi.io` 后，GIF → PNG 归一化与若干 UniAPI 兼容路径不再命中。

## 本次修复
- 新增共享 helper：`holo_cortex_zero/core/uniapi_hosts.py`
  - 统一维护 `UNIAPI_HOSTS = {"api.uniapi.io", "hk.uniapi.io"}`
  - 提供统一 host/base_url 归一化判断，避免各文件重复写死 host
- 将以下兼容分支统一改为识别 `api.uniapi.io` 与 `hk.uniapi.io`
  - `holo_cortex_zero/services/llm/router.py`
  - `holo_cortex_zero/services/llm/responses.py`
  - `holo_cortex_zero/services/llm/gemini.py`
  - `holo_cortex_zero/services/llm/openai_chat.py`
  - `holo_cortex_zero/services/agent/openai.py`
  - `holo_cortex_zero/services/agent/run_agent_v2.py`（注释说明同步）

## 影响
- `uni-grok` 的 GIF → PNG 图片兼容归一化在 `api.uniapi.io` 下重新生效
- `UniAPI + qwen3.5-plus` 的相关缓存/兼容分支可同时覆盖 `api` / `hk`
- Gemini relay、chat content cache compat、responses 兼容 host 集合不再只认 `hk`

## 验证
- 代码已通过 `python3 -m compileall` 目标文件编译检查
- 已执行 `docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`
- 容器恢复 `healthy`

## 备注
- 本次是主干通用修整，不再为 `api.uniapi.io` 额外复制一份并行兼容逻辑。
- 下一步应在 QQ / TG 内直接发图实测，确认 `responses` 链路不再因 GIF 触发 400。
