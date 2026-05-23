# 辅助 LLM 统一丐版管道与缓存主干迁移

日期：2026-04-28

## 背景

本次改造把 5 条辅助 LLM 链路收敛到统一的轻量主干：

- `ai_reply_judge`
- `memory_manage`
- `auto_memory`
- `subconscious`
- `timeline`

迁移前旧依赖重点：

- `timeline -> gen_openai_chat_response`，绕过新版 `llm_router.generate`、模型组协议识别、代理解析与缓存提示。
- 其余 4 条链路虽已接入 `llm_router.generate`，但模型组解析、协议识别、缓存提示与调用逻辑散落在业务文件中。

## 新主干

新增模块：`holo_cortex_zero/services/llm/auxiliary.py`

职责只包含公共发射主干：

1. `config.get_model_group_info(model_group_key)` 获取模型组。
2. `detect_model_group_protocol(..., allow_legacy_wire_api=True)` 判定协议。
3. `resolve_model_group_proxy(...)` 解析模型组代理。
4. 解析模型组 `EXTRA_BODY`。
5. 合并 `EXTRA_BODY` 与业务 `GenerationRequest.extra_params`，业务显式参数覆盖模型组默认参数。
6. 归一化 `GenerationRequest`：
   - `context_id="aux:<aux_name>"`
   - `model=model_group.CHAT_MODEL`
   - `stream=False`
7. 注入辅助 LLM 缓存提示。
8. 调用 `llm_router.generate(...)` 返回原始 `GenerationResult`。

新主干不负责 JSON 解析、tool call 业务判断、记忆写入、timeline 落库、judge fail-open/fail-close 等业务语义。

## 缓存策略

统一注入：

```python
{
    "cache_control": "ephemeral",
    "stable_prefix": "system_first_text",
    "aux_name": "<aux_name>",
}
```

约束：

- `cache_control` 与 `stable_prefix` 是发射器实际消费字段。
- `aux_name` 只作为日志/调试/未来扩展标记，不直接映射到 provider payload。
- 不引入 `cache_marker`。
- 不引入 `cache_salt`。
- 不按 `chat_key` 或业务原始 `context_id` 切碎 provider system prompt 缓存。
- `context_id="aux:<aux_name>"` 仅用于辅助用途命名空间与 Responses 内部 prefix snapshot 隔离。
- 不支持缓存的 API 继续由现有发射器 no-op，不在业务层发送 provider 专用字段。

## 迁移清单

- `holo_cortex_zero/services/context_window/timeline.py`
  - 删除旧 `gen_openai_chat_response` 调用。
  - 改为构造 `GenerationRequest` + `MessageTurn`。
  - 调用 `generate_auxiliary(aux_name="timeline", source="context_window.timeline")`。
  - 保持空摘要抛错与 `pending_summary` 写入逻辑不变。

- `holo_cortex_zero/services/memory/mem0_utils.py`
  - `memory_manage` 继续保留 owner/chat/metadata prompt 与 JSON 解析逻辑。
  - `response_format={"type": "json_object"}` 仍仅在 `protocol == "chat"` 时加入业务 `extra_params`。
  - LLM 调用改为 `generate_auxiliary(aux_name="memory_manage")`。

- `holo_cortex_zero/services/memory/auto_memory.py`
  - 保留 `add_memory` tool schema、`parallel_tool_calls=False`、`tool_choice`、无 tool call 不推进水位等语义。
  - 通过 `prepare_auxiliary_request(...)` 获取已合并的 request/protocol/model_group，用于现有 wire payload 预览。
  - 真正请求改为 `generate_prepared_auxiliary(...)`。
  - 清理迁移后不再使用的本地协议解析方法。

- `holo_cortex_zero/services/memory/subconscious.py`
  - 保留 `chat -> json`、非 chat/responses -> tool 的输出模式。
  - tool 模式仍要求 tool call，缺失则按原逻辑降级失败。
  - json 模式仍解析 `result.text`。
  - LLM 调用改为 `generate_auxiliary(aux_name="subconscious")`。

- `holo_cortex_zero/services/ai_reply/service.py`
  - 保留 judge prompt、`max_tokens=64`、`temperature=0.0`、外层 `asyncio.wait_for`、JSON 解析、fail-open/fail-close 语义。
  - LLM 调用改为 `generate_auxiliary(aux_name="ai_reply_judge")`。

## 输出约束

本次未改变任何辅助链路输出协议：

- `ai_reply_judge`：仍要求 JSON 文本 `{"should_reply": true/false}`。
- `memory_manage`：仍解析 JSON 文本并归一化为 `ADD/UPDATE/REJECT`。
- `auto_memory`：仍要求 `add_memory` tool call。
- `subconscious`：仍按协议选择 JSON 文本或 tool call。
- `timeline`：仍读取纯文本摘要写入 `pending_summary`。

## 风险与回滚点

- 风险：`timeline` 返回对象从旧 `response.response_content` 切换为 `GenerationResult.text`。
  - 控制：只改读取字段，prompt 与 pending 写入语义不变。
  - 回滚：恢复 `timeline.py` 中旧 `gen_openai_chat_response` 调用。

- 风险：模型组 `EXTRA_BODY` 合并顺序影响业务显式参数。
  - 控制：模型组 extra 先合并，业务 request extra 后覆盖。
  - 回滚：在受影响业务侧临时保留原 extra 解析，但仍可继续走 `auxiliary.py`。

- 风险：缓存字段导致供应商拒绝。
  - 控制：业务层只传 `cache_hints`，provider wire 字段由现有发射器兼容判断决定。
  - 回滚：让 `build_aux_cache_hints(...)` 返回空 dict 即可关闭辅助缓存。

## 验证结果

已执行：

```bash
rg -n "gen_openai_chat_response\\(" holo_cortex_zero/services
```

结果：只剩 `holo_cortex_zero/services/agent/openai.py` 中旧函数定义，`timeline.py` 不再命中。

已执行：

```bash
rg -n "llm_router\\.generate\\(" \
  holo_cortex_zero/services/memory \
  holo_cortex_zero/services/ai_reply \
  holo_cortex_zero/services/context_window
```

结果：无输出，5 条辅助链路不再散写直接调用。

已执行：

```bash
uv run python - <<'PY'
from nonebot import init
init()
from holo_cortex_zero.services.llm.auxiliary import build_aux_cache_hints
hints = build_aux_cache_hints('timeline')
assert hints == {
    'cache_control': 'ephemeral',
    'stable_prefix': 'system_first_text',
    'aux_name': 'timeline',
}
print(hints)
PY
```

结果：构造级缓存提示验证通过，返回 `cache_control=ephemeral`、`stable_prefix=system_first_text`、`aux_name=timeline`。

已执行：

```bash
uv run python -m compileall \
  holo_cortex_zero/services/llm/auxiliary.py \
  holo_cortex_zero/services/context_window/timeline.py \
  holo_cortex_zero/services/memory/auto_memory.py \
  holo_cortex_zero/services/memory/mem0_utils.py \
  holo_cortex_zero/services/memory/subconscious.py \
  holo_cortex_zero/services/ai_reply/service.py
```

结果：编译通过。

已执行：

```bash
HTTP_PROXY=http://<LOCAL_HTTP_PROXY> HTTPS_PROXY=http://<LOCAL_HTTP_PROXY> uv run poe test
```

结果：`bot --load-test` 启动自检通过。

## 未执行事项

- 未重启 HCZ、frp、vLLM 或家庭服务器。
- 未执行 Docker rebuild / force recreate。
- 未改主 LLM tool chain。
- 未改 mem0 记忆分区。
- 未改 prompt 内容与输出 schema。

## 真实辅助 LLM 烟测补充

用户追问后补做真实 LLM 调用验证。验证脚本只构造最小 `GenerationRequest`，不写库、不触发业务水位、不调用 Docker 重建。

已执行 5 条辅助用途真实请求：

- `timeline`
  - 模型组：`deepseek-reason`
  - 协议：`chat`
  - host：`api.deepseek.com`
  - 结果：成功，`finish=stop`，返回 `时间线验证通过`
  - 证明：日志显示 `context_id=aux:timeline`，并落地 DeepSeek 官方 chat 的 `cache_control=ephemeral` content-block 缓存提示。

- `memory_manage`
  - 模型组：`qwen35-hcz-resident-think`
  - 协议：`responses`
  - host：`<HOST_GATEWAY_IP>:18081`
  - 结果：成功，`finish=completed`，返回可解析 JSON：`{"action":"ADD","targets":[],"reason":"smoke"}`
  - 证明：日志显示 `context_id=aux:memory_manage`，进入 `ResponsesEmitter` generic cache path 并更新 prefix snapshot。

- `auto_memory`
  - 模型组：`qwen35-hcz-resident-think`
  - 协议：`responses`
  - host：`<HOST_GATEWAY_IP>:18081`
  - 结果：成功，`finish=completed`，返回 `tool_calls=1`
  - 证明：日志显示 `context_id=aux:auto_memory`，进入 `ResponsesEmitter` generic cache path 并更新 prefix snapshot。

- `subconscious`
  - 模型组：`doubao-nonthinking2`
  - 协议：`chat`
  - host：`ark.cn-beijing.volces.com`
  - 结果：成功，`finish=stop`，返回 JSON：`{"intents": [], "cache_updates": []}`
  - 说明：当前配置为 chat 协议，因此保持原设计的 json-only 模式。

- `ai_reply_judge`
  - 模型组：`qwen35-hcz-resident`
  - 协议：`chat`
  - host：`<HOST_GATEWAY_IP>:18081`
  - 结果：成功，`finish=stop`，返回 JSON：`{"should_reply": true}`

补充说明：第一次烟测为了省 token 将 `timeline` 与 `memory_manage` 的 `max_tokens` 设得过小，分别出现 `finish=length` / `finish=incomplete`。随后按接近业务参数重跑：`timeline max_tokens=256`、`memory_manage max_tokens=None`，两项均真实成功返回。

## 旧 OpenAI 辅助封装移除补充

用户额外清理后确认：`holo_cortex_zero/services/agent/openai.py` 已删除。

确认结果：

- `rg -n "services\\.agent\\.openai|agent\\.openai|gen_openai_chat_response\\(" holo_cortex_zero tests` 无输出，说明旧 `gen_openai_chat_response` 入口已无业务引用。
- `holo_cortex_zero/services/agent/run_agent_v2.py` 中旧注释同步删除，不再描述辅助 LLM 走旧封装。
- `uv run python -m compileall` 覆盖主回复发射入口与 5 条辅助链路目标文件，编译通过。
- `HTTP_PROXY=http://<LOCAL_HTTP_PROXY> HTTPS_PROXY=http://<LOCAL_HTTP_PROXY> uv run poe test` 启动自检通过。

本次仍未修改主 LLM tool chain、mem0 分区、prompt 内容或输出 schema。
