# 2026-05-12 删除旧 /exec 与 NA 前缀命令残留

## 背景

当前高级上下文手工命令主干已经收口到 `MessageService.push_human_message()`：

- `/clear`
- `/clearall`
- `/norm`
- `/cute`
- `/puss`

这些命令在消息入库前精确匹配并处理，回执统一走 `MessageService._send_plain_text_to_chat()`，不经过旧 OneBot `finish_with()`，也不依赖 `AI_COMMAND_OUTPUT_PREFIX`。

## 删除范围

- 删除 OneBot v11 旧 `exec` matcher 注册文件。
- 删除 OneBot v11 旧命令 guard。
- 删除通用旧 `/exec tool(...)` 命令处理器。
- 删除 `run_agent_v2` 里的 `/exec` 旁路。
- 删除 OneBot 普通消息入口中的私有前缀忽略表。
- 删除旧配置项：
  - `AI_IGNORED_PREFIXES`
  - `AI_COMMAND_OUTPUT_PREFIX`

## 判断

`≡NA≡` 只服务旧 OneBot 命令输出防回流，不属于当前高级上下文命令主干。通用消息忽略继续由 `AI_CHAT_IGNORE_REGEX` 负责，避免在 OneBot 适配器内保留并行过滤主干。

## 验证

执行残留搜索：

```bash
rg -n '≡NA≡|AI_COMMAND_OUTPUT_PREFIX|AI_IGNORED_PREFIXES|command_guard|finish_with|handle_command|/exec' holo_cortex_zero
```

执行编译验证：

```bash
uv run python -m compileall holo_cortex_zero
```
