# 2026-05-16 adapter config surface cleanup

## 结论

- Matrix 不再有 `ENABLED` 配置。适配器被主干加载即初始化，是否处理/回复消息仍由频道 `is_active`、触发逻辑和 Matrix 入群策略决定。
- `SESSION_ENABLE_AT` 只保留在 OneBot 配置。当前只有 OneBot 富文本转换和 OneBot `@` 解析消费该字段。
- `SESSION_PROCESSING_WITH_EMOJI` 只保留在 OneBot 配置。当前只有 OneBot 实现了可用的消息 emoji reaction；主干调用前按字段存在性判断，TG/Matrix 不再暴露假开关。
- SSE 聊天适配器已移除：取消后端适配器注册、删除 `holo_cortex_zero/adapters/sse`、删除前端适配器入口。`sse-starlette` 仍保留，因为日志流和 dashboard 仍使用服务端 SSE 推流。

## 可复现证据

- `rg "adapters\\.sse|SSEAdapter|names\\.sse" holo_cortex_zero frontend pyproject.toml` 无结果。
- `rg "SESSION_ENABLE_AT|SESSION_PROCESSING_WITH_EMOJI" holo_cortex_zero frontend` 只剩 OneBot 配置/消费点和 `message_service` 的存在性判断。
- 运行配置中 Matrix/TG 不再包含 `ENABLED`、`SESSION_ENABLE_AT`、`SESSION_PROCESSING_WITH_EMOJI`；OneBot 保留两个真实消费字段。

## 回滚点

- 代码回滚本次提交即可恢复旧配置面和 SSE 适配器。
- 运行配置回滚只涉及重新创建 `configs/sse/config.yaml`，以及把 Matrix/TG 的旧无效键写回；这些键已不参与当前代码运行。
