# 2026-05-12 meromero 本地组启用 native tools 压测

## 背景

5/11 auto_memory 产出 `<|tool_call>call:add_memory{content: ...}<tool_call|>`，但没有进入 write/仲裁链。追查确认当时 auto_memory 使用 `meromero-31b-resident-think`，该模型组 `EXTRA_BODY.skip_native_tools=true` 导致 chat.completions payload 未携带 native `tools` schema，模型退化为文本 tool-call 方言并使用 `content` 字段。

本轮按要求先从本地 meromero 运行态模型组移除 `skip_native_tools`，再压测 native tool 调用可用性，验证不只 memory 工具。

## 配置修改

运行态配置文件：`/path/to/runtime-data/configs/holo-cortex-zero.yaml`

移除字段的模型组：

- `meromero-31b-resident`
- `meromero-31b-resident-think`

修改后 `EXTRA_BODY`：

```yaml
meromero-31b-resident:
  EXTRA_BODY: '{"wire_api": "chat", "thinking": {"type": "disabled"}, "local_chat_image_max_long_edge": 1024, "id_slot": 0}'

meromero-31b-resident-think:
  EXTRA_BODY: '{"wire_api": "chat", "thinking": {"type": "disabled"}, "id_slot": 1}'
```

运行态校验结果：

- `remaining_skip_native_tools_true=[]`
- 容器内 `config.MODEL_GROUPS` 两个 meromero 组均不再包含 `skip_native_tools`。

备份文件：`/path/to/runtime-data/configs/holo-cortex-zero.yaml.bak_20260512_105652_remove_skip_native_tools`

## 生效方式

仅重建后端本体，不动 postgres/qdrant/napcat：

```bash
cd /path/to<CONTAINER_WORKSPACE_DIR>
printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --no-deps --force-recreate holo_cortex_zero
```

## 单点验证

### 最小 add_memory native tool

请求：本地 `http://<LOCAL_OPENAI_COMPAT_HOST>:18081/v1/chat/completions`，携带 `tools=[add_memory]`，`tool_choice=auto`，`chat_template_kwargs.enable_thinking=false`。

结果：

- HTTP 200
- 耗时 `2.24s`
- `finish_reason=tool_calls`
- `message.tool_calls[0].function.name=add_memory`
- arguments 为 JSON 字符串，字段为 `memory/metadata/user_id`
- `content=''`

### auto_memory 构造请求验证

容器内用 `AutoMemoryService._build_generation_request()` 构造真实 auto_memory prompt，移除 `skip_native_tools` 后请求本地 meromero。

结果：

- HTTP 200
- 耗时 `4.79s`
- `payload tools=True`
- `tool_schema_required=['memory', 'user_id', 'metadata']`
- `finish=tool_calls`
- `tool_calls=1`
- arguments 字段为 `memory/metadata/user_id`
- `content_len=0`

## 多工具压测

压测脚本：临时脚本 `/tmp/meromero_tool_stress.py`，不写入仓库。

压测设置：

- 模型：`meromero-31b-mm-int4`
- 端点：`http://<LOCAL_OPENAI_COMPAT_HOST>:18081/v1/chat/completions`
- 并发：`2`
- 轮数：`5`
- 总请求：`30`
- 每次携带 6 个工具 schema，让模型选择目标工具。
- `tool_choice=auto`
- `parallel_tool_calls=false`
- `temperature=0.0`
- `chat_template_kwargs.enable_thinking=false`
- `id_slot` 在 `0/1` 间分配。

工具类型：

- `add_memory`
- `seek`
- `get_weather`
- `create_todo`
- `calculate`
- `send_message`

压测结果：

```json
{
  "total": 30,
  "ok": 30,
  "success_rate": 1.0,
  "elapsed_seconds": 21.42,
  "finish": {
    "tool_calls": 30
  },
  "by_tool": {
    "add_memory": {"ok": 5, "total": 5, "rate": 1.0},
    "calculate": {"ok": 5, "total": 5, "rate": 1.0},
    "create_todo": {"ok": 5, "total": 5, "rate": 1.0},
    "get_weather": {"ok": 5, "total": 5, "rate": 1.0},
    "seek": {"ok": 5, "total": 5, "rate": 1.0},
    "send_message": {"ok": 5, "total": 5, "rate": 1.0}
  },
  "failures": []
}
```

成功判定：

- HTTP 成功。
- `finish_reason=tool_calls`。
- 返回标准 `message.tool_calls`。
- 选择的工具名等于预期工具名。
- `function.arguments` 可 JSON 解析。
- `message.content` 为空。

## 结论

- 当前本地 meromero chat 服务 native tools 可用。
- 去掉 `skip_native_tools` 后，多工具压测 `30/30` 成功。
- 5/11 的 `content` 字段事故不是 meromero 必然不能工具调用，而是 `skip_native_tools=true` 让 schema 没有发送，模型退化为文本 tool-call 方言。
- auto_memory 这类强依赖工具 schema 的链路不应继承 `skip_native_tools`。

## 风险与回滚

风险：

- 早期 `skip_native_tools=true` 是为本地 chat 无工具快路/一行 JSON 辅助链路准备的。移除后，若某些链路带 tools，会改走 native tools；本轮压测显示 native tools 可用，但仍需观察主对话、timeline、subconscious 的实际表现。
- 未执行真实业务工具，只验证了 LLM native tool selection 和参数 JSON 结构。

回滚：

```bash
cp /path/to/runtime-data/configs/holo-cortex-zero.yaml.bak_20260512_105652_remove_skip_native_tools \
  /path/to/runtime-data/configs/holo-cortex-zero.yaml
cd /path/to<CONTAINER_WORKSPACE_DIR>
printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --no-deps --force-recreate holo_cortex_zero
```
