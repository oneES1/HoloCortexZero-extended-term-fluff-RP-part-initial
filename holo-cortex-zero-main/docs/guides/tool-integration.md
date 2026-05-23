# Tool Integration

## 当前真实接入路径

当前主干只保留 Tool 接入，分层如下：

1. 纯 Tool 实现在 `tool_runtime/tools/*.py`
2. Tool 运行时协议定义在 `tool_runtime/host.py`
3. Tool 结果结构定义在 `tool_runtime/result.py`
4. Tool 描述与能力分类定义在 `tool_runtime/spec.py`
5. Tool scope 语义定义在 `tool_runtime/config.py`
6. 宿主桥接实现在 `holo_cortex_zero/services/tools/host/bridge.py`
7. 统一注册与执行拦截在 `holo_cortex_zero/services/tools/registry.py`
8. 用户向 Tool 的宿主注册在 `holo_cortex_zero/services/tools/migrated/__init__.py`
9. 高级维护 Tool 的宿主注册在 `holo_cortex_zero/services/tools/advanced/file_ops.py`
10. 系统 Tool 由 `holo_cortex_zero/services/moment/service.py` 管理
11. `add_memory` 等 internal-only Tool 由 `holo_cortex_zero/services/memory/auto_memory.py` 内部使用
12. Tool 管理 API 在 `holo_cortex_zero/routers/tools.py`
13. Tool 轨迹 API 在 `holo_cortex_zero/routers/tool_traces.py`

外部服务默认挂载路径带 `/api` 前缀，因此：

- Tool 管理接口对外路径默认是 `/api/tools*`
- Tool 轨迹接口对外路径默认是 `/api/tool-traces/*`

## 注册一个新 Tool

宿主统一通过 `tool_registry.register(...)` 接入 Tool。

核心参数如下：

- `name`：Tool ID
- `display_name`：展示名称
- `handler`：异步 handler
- `description`：给模型和管理面的说明
- `parameters`：JSON Schema
- `capability_class`：`user_facing` 或 `privileged`
- `default_scope`：推荐初始启用范围，最终以用户 YAML 配置为准
- `supports_multimodal_return`：是否支持多模态返回
- `category`：分类
- `config_model`：配置模型

示例：

```python
tool_registry.register(
    name="weather",
    display_name="天气查询",
    handler=weather,
    description=WEATHER_DESCRIPTION,
    parameters=WEATHER_PARAMETERS,
    capability_class="user_facing",
    default_scope="all",
    supports_multimodal_return=False,
    category="生活服务",
    config_model=WEATHER_CONFIG_MODEL,
)
```

## 注册参数语义

### `capability_class`

- `user_facing`：面向普通 Tool 暴露链路
- `privileged`：高危维护 Tool，默认只允许高级上下文

### `default_scope`

四态之一：

- `disabled`
- `normal_only`
- `advanced_only`
- `all`

它表示 Tool 首次生成配置文件时使用的推荐启用范围。配置文件存在后，运行期以用户 YAML 中的 `SCOPE_MODE` 为准，管理页/API 可以继续修改该值。

### `supports_multimodal_return`

该字段只表示 Tool 可能返回多模态结果，不表示 Tool 自己负责做多模态兼容。

### `config_model`

配置模型会自动生成 Tool 的配置文件与 UI 面板。所有需要运营、排障、配额或行为开关的参数，都应该优先进入这里，而不是写死在代码里。

## Runtime 合同

面向 Tool 作者与接入维护者，当前公开 Tool 的运行时合同统一收口如下。

### 公开 Tool 的最小合同

公开 Tool handler 只应该依赖：

- 业务参数
- `tool_host`
- `tool_config`

推荐形态：

```python
async def your_tool(
    business_arg: str,
    tool_host: ToolHostBridge | None = None,
    tool_config: CONFIG_MODEL | None = None,
) -> ToolOutcome:
    ...
```

### 明确禁止

公开 Tool 明确禁止：

- 声明任何窗口参数
- 声明任何频道参数
- 声明任何用户指定参数
- 沿用 `_ctx` / `ctx` / `ctx_`
- 把窗口 / 频道 / 用户指定放进 `parameters` schema 让模型来传

如果某个公开 Tool 看起来“必须知道窗口是谁”，优先结论应该是：

- 改走 `tool_host`
- 上移框架层
- 改成内部 / 系统 / 高级维护能力

而不是继续扩 handler 入参。

### 为什么禁止窗口指定

因为在当前架构里：

- 逻辑上下文窗口由框架决定
- 当前回复窗口由框架锚定
- 高级用户与普通用户的窗口路由规则由框架维护
- Tool 作者不应该重新实现一套窗口路由

所以对公开 Tool 的口径必须是：

> Tool 只做业务动作，不参与窗口选择。

### 执行期主干约束

Tool 执行统一通过：

- `tool_registry.execute(call, permission_level, ...)`

执行期运行时约束：

- 对外公开 Tool 继续保持最小签名，只声明业务参数
- `context_id` / `dialog_chat_key` / `chat_key` 等字段属于框架内部运行时合同
- 它们可以存在于执行主干内部，但不是对外推荐的公开 Tool handler 接口
- 窗口、路由、权限与协议兼容属于框架内部责任

## 四态启用与执行期硬拒

### 暴露给模型

Tool 暴露统一通过：

- `tool_registry.get_tools_for_context(permission_level)`

只有当前上下文 `scope` 允许的 Tool，才会进入模型可见的 `ToolSpec` 列表。

### 实际执行

Tool 执行统一通过：

- `tool_registry.execute(call, permission_level, ...)`

运行时参数与公开 Tool 合同见上文 `Runtime 合同`。这里强调的是：

这一步与“暴露给模型”共用同一套 scope 判定。结论是：

- 即使 bot 发疯，碰巧构造出一个未暴露的 tool call
- 只要当前上下文 scope 不允许
- 执行期仍会被硬拦截，并返回 `tool_disabled_or_forbidden`

这条规则是当前 Tool 主干的安全底线，不能只做“前面不展示，后面放行”的软限制。

## 开发接口可见性

### Tool 管理 API

对外默认路径：

- `GET /api/tools`
- `GET /api/tools/{tool_id}`
- `POST /api/tools/{tool_id}/scope`

其中：

- 列表接口返回启用范围、能力分类、配置 key、是否支持多模态
- 详情接口额外返回 `parameters_schema`、`hard_limit_notice`、轨迹行为信息
- scope 更新接口只允许修改非锁定 Tool 的四态开关

### Tool 轨迹

Tool 轨迹页面与 API 用于查看 Tool 调用、结果预览和执行问题。

- API：`/api/tool-traces/*`
- 前端页：当前仓库中的 `frontend/src/pages/tool-traces/index.tsx`

## 多模态主干

### 基本原则

- Tool 统一返回 `ToolOutcome` / `ToolPart`
- 框架统一把 `ToolPart` 转成上下文消息、日志和协议请求
- Tool 不自己拼供应商 payload

### 为什么多模态要走 `user` 历史

当前上下文装配与媒体 rewrite 主干按 `user` turn 处理图片、音频、视频、文件。结论是：

- 如果多模态 Tool 想让产物进入下一轮模型上下文，必须使用 `history_role="user"`
- 如果继续保留 `history_role="tool"`，框架不会把它当作需要进入多模态主干的用户物料

这是当前主干约束，不是“建议”。

### Tool 视频自动保护

当前框架在 `holo_cortex_zero/services/llm/router.py` 中统一处理 Tool 视频：

- 只要 `MessagePart.type == "video"` 且 `meta.source == "tool"`
- 默认进入 Tool 视频保护主干
- 仅当 `meta.preserve_video = false` 时显式关闭

默认规则：

- 最近 `1` 条 Tool 视频保留
- 默认大小上限 `8MB`
- 默认时长上限 `60s`

行为：

- 由主干先尝试原样保留或压缩到限制内
- 当前发射器若声明可接受 `video` part，则保留为 `video` IR 下发
- 当前发射器若不接受 `video` part，则主干统一降级为文本说明
- 普通非 Tool 视频：继续沿用框架原有 `video -> audio` / 路径说明 rewrite，不被 Tool 规则误伤

当前三条主链发射器的能力声明是：

- `gemini`：接受 `image/audio/video`，原生 tool calling
- `responses`：接受 `image`，`audio/video/file` 在发射器内降级为文本，原生 tool calling
- `openai_chat`：接受 `image`，`audio/video/file` 在发射器内降级为文本，原生 tool calling

### Magic_draw 一类图片 Tool

`magic_draw` 家族 Tool 的标准行为是：

- 返回 1 条文本说明
- 返回 1 条图片路径
- 使用 `history_role="user"`
- 不自动发聊天框

说明文本必须明确写清楚“已生成，但未发送到聊天框”，因为这条文本既给模型看，也给开发者排查时看。

## 文件系统主干

当前文件系统主干已经切换到宿主绝对路径：

- Tool 返回图片/音频/视频/文件时，统一使用宿主绝对路径
- `write_managed_file(...)` 返回的 `managed_path` 与 `local_path` 当前都是宿主绝对路径
- 不再依赖旧虚拟路径协议

开发文档、日志、调试脚本和 Tool 返回值都应该与这套路径约定保持一致。

## 非污染式验证方案

本轮推荐验证方式是“进程内仿真”，不是去真实群聊发测试消息。

### 允许的验证动作

- 直接调用 `tool_registry.execute(...)` 验证 scope 与硬拒路径
- 直接调用某个 Tool handler，配合 fake `ToolHostBridge` 验证返回契约
- 构造 `GenerationRequest`，调用 `LLMRouter._prepare_request(...)` 验证多模态 rewrite
- 使用临时文件验证图片/视频路径与 `ffmpeg` / `ffprobe` 限制逻辑

### 明确不建议

- 不去真实群里做链路测试
- 不读全量日志
- 不为了验证 Tool 文档去触发真实外发

这套验证方式更适合“校正文档 + 收紧主干行为”的任务，因为它能 1:1 走代码链路，又不污染业务窗口。

## 典型接入模板

### 文本 Tool

- 返回 `ToolOutcome(parts=[ToolPart(type="text", ...)])`
- 通常保持 `history_role="tool"`

### 图片 Tool

- 返回“说明文本 + 图片路径”
- 使用 `history_role="user"`
- `meta.source = "tool"`
- 不直接发聊天框

### 视频 Tool

- 返回 `ToolPart(type="video", ...)`
- `meta.source = "tool"`
- 默认会被框架纳入 Tool 视频保护主干
- 如需收紧限制，再写 `max_inline_bytes` / `max_duration_seconds`
- 不要在 Tool 里根据某家模型 / 协议分叉返回结构，是否真能下发 video 由当前发射器能力决定

### 高级维护 Tool

- 宿主注册入口在 `holo_cortex_zero/services/tools/advanced/file_ops.py`
- 统一固定 `advanced_only`
- 既不会暴露给普通上下文，也不会在执行期放行给普通上下文

## 当前主干里的 Tool 分类

### 系统 Tool

- `echo`

### internal-only Tool

- `add_memory`

### 已迁移到 Tool Runtime 的公开能力

- `weather`
- `seek`
- `isolate`
- `gif_generation`
- `photoshop`
- `lightroom`

### 高级维护 Tool

- `list_files`
- `read_file`
- `search_code`
- `run_command`
- `apply_patch`
- `write_file`
- `send_file`

## 结论

Tool 集成的核心原则只有一句话：

> Tool 负责返回结构化结果，框架负责权限、执行、上下文注入、协议兼容和管理面。

只要按这条主干接入，新 Tool 才能在当前仓库里保持纯洁、可迁移、可调试、可配置、可持久化。
