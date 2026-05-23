# Tool Development

这份文档写给第一次接触本项目的人。

如果你只想先记住一句话，请记住这句：

> Tool 负责做事并返回结构化结果；框架负责权限、上下文注入、协议兼容、UI 管理和执行拦截。

所以，在这个仓库里开发 Tool，不是去拼某个模型厂商的 payload，也不是去写一段会直接往聊天框乱发消息的脚本；而是写一段**纯 Tool 逻辑**，然后把它接到现有主干里，让框架替你处理后面的脏活。

如需看更偏系统实现与主干拓扑的说明，请同时阅读 `docs/guides/tool-integration.md`。

## 1. 先建立正确心智

当前项目里的“扩展能力”，已经统一收口为 Tool。

你可以把它理解为三层：

1. `tool_runtime/`：纯 Tool Runtime，只放 Tool 抽象、返回结构、配置语义、宿主接口声明。
2. `tool_runtime/tools/*.py`：具体 Tool 实现。这里禁止直接依赖 `holo_cortex_zero.*`。
3. `holo_cortex_zero/services/tools/*`：宿主注册层、权限控制层、执行层、上下文回流层。

换句话说：

- Tool 写在 `tool_runtime/tools/*.py`
- Tool 暴露给模型、能否启用、能否执行，由 `holo_cortex_zero` 主干控制
- Tool 作者不用关心 Gemini / Responses / OpenAI Chat 的 payload 差异

这也是为什么我们要求 Tool 保持“纯洁”和“可迁移”：

- 以后你换模型、换协议、换上层框架，Tool 本体尽量不用跟着重写
- 真正容易变化的东西，集中留在宿主桥接层处理

## 2. 开发 Tool 前必须知道的硬规则

### 2.1 代码边界

`tool_runtime/tools/*.py` 内：

- 不要 `import holo_cortex_zero.*`
- 不要直接读取框架内部对象
- 不要拼任何供应商请求体
- 不要根据某个模型厂商写特化返回结构

Tool 如果需要访问宿主能力，只能通过 `tool_runtime/host.py` 里的 `ToolHostBridge`。

### 2.2 权限边界

Tool 的权限控制不是“前面隐藏一下就算了”，而是**双重硬限制**：

1. 暴露阶段：当前上下文不允许的 Tool，不会出现在给模型的 `ToolSpec` 列表里。
2. 执行阶段：即使模型“发疯”构造了一个未暴露的 tool call，`tool_registry.execute(...)` 仍会拒绝执行。

所以你不需要在 Tool 自己内部再复制一套权限判断；主干已经负责硬拦截。

### 2.3 行为边界

默认 user-facing Tool 的职责是：

- 接受参数
- 执行动作
- 返回 `ToolOutcome`

默认**不应该**：

- 直接向聊天框发送文本
- 直接向聊天框发送图片
- 直接构造某家模型的媒体段
- 把“协议兼容负担”推给 Tool 作者

如果一个功能确实需要直接发送消息，那是少数特例，应优先考虑是否应该交给框架层或系统 Tool，而不是让普通 Tool 乱发。

## 3. 你会用到的核心文件

第一次开发时，先看这几个位置：

- `tool_runtime/result.py`：Tool 返回值定义
- `tool_runtime/host.py`：Tool 可调用的宿主能力接口
- `tool_runtime/tools/__init__.py`：当前已有 Tool 的导出入口
- `holo_cortex_zero/services/tools/registry.py`：Tool 注册、暴露、执行期硬拒
- `holo_cortex_zero/services/tools/migrated/__init__.py`：普通公开 Tool 的宿主注册入口
- `holo_cortex_zero/services/tools/advanced/file_ops.py`：高级维护 Tool 的宿主注册入口
- `holo_cortex_zero/routers/tools.py`：Tool 管理 API
- `docs/guides/tool-integration.md`：Tool 主干集成、运行时合同与多模态流转说明

如果你只是要写一个新 Tool，绝大多数时候你只需要改：

- `tool_runtime/tools/你的工具.py`
- `tool_runtime/tools/__init__.py`
- 对应的宿主注册入口

## 4. Tool 的完整生命周期

一个 Tool 从开发到可用，通常经过这五步。

### 4.1 在 `tool_runtime/tools/` 写纯实现

你需要提供：

- Tool ID
- 显示名
- 描述
- 参数 schema
- 配置模型
- `async handler(...) -> ToolOutcome`

### 4.2 在 `tool_runtime/tools/__init__.py` 导出

导出常量与 handler，让宿主注册层可以统一引用。

### 4.3 在宿主注册层挂载

按 Tool 类型选择入口：

- 普通公开 Tool：`holo_cortex_zero/services/tools/migrated/__init__.py`
- 高级维护 Tool：`holo_cortex_zero/services/tools/advanced/file_ops.py`
- 系统内置 Tool：走对应系统服务的注册逻辑

### 4.4 由框架生成配置并托管 UI

Tool 一旦注册，主干会为它生成配置对象，并通过 `/api/tools` 暴露给管理面。

### 4.5 经由主干参与真实调用链

被模型看见、被调用、写回上下文、进入下一轮消息构造、转成具体协议 payload，这些都由主干处理。

## 4.6 Handler 运行时合同

面向外部开发者，公开 Tool 的 handler 必须保持最小、最简、无冗余。

你应该只依赖：

- 业务参数
- `tool_host`
- `tool_config`

推荐的最小形态是：

```python
async def your_tool(
    business_arg: str,
    tool_host: ToolHostBridge | None = None,
    tool_config: CONFIG_MODEL | None = None,
) -> ToolOutcome:
    ...
```

公开 Tool 开发里，明确禁止：

- 声明任何窗口参数
- 声明任何频道参数
- 声明任何用户指定参数
- 沿用 `_ctx` / `ctx` / `ctx_`
- 因为“怕不够用”而预留复杂 runtime 参数

典型禁例包括：

- `context_id`
- `dialog_chat_key`
- `active_dialog_id`
- `chat_key`
- `primary_user_id`
- `channel_id`

如果一个公开 Tool 看起来必须知道窗口或用户是谁，优先判断应该：

- 改走 `tool_host`
- 上移框架层
- 改成内部 / 系统 / 高级维护能力

而不是继续扩 handler 入参。

`docs/guides/tool-integration.md` 里的 `Runtime 合同` 章节提供统一口径；以本节作为外部开发的主说明。

## 5. Tool 返回契约

所有 Tool 都必须返回 `tool_runtime/result.py` 里的 `ToolOutcome`。

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass
class ToolPart:
    type: Literal["text", "image", "audio", "video", "file"]
    text: Optional[str] = None
    url: Optional[str] = None
    data: Optional[bytes] = None
    mime_type: Optional[str] = None
    detail: str = "auto"
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolOutcome:
    parts: List[ToolPart] = field(default_factory=list)
    is_error: bool = False
    history_role: Literal["tool", "user"] = "tool"
    trace_title: str = ""
    trace_summary: str = ""
```

### 5.1 字段怎么理解

- `parts`：Tool 的实际返回内容，可以是文本、图片、音频、视频、文件
- `is_error`：这次执行是否失败
- `history_role`：这次结果写回上下文时，按 `tool` 还是 `user` 角色处理
- `trace_title` / `trace_summary`：给日志、轨迹页、排错看的摘要

### 5.2 最重要的规则：多模态要进上下文，就必须是 `user`

如果你的 Tool 返回里包含：

- 图片
- 音频
- 视频
- 文件

并且你希望这些结果进入下一轮模型上下文，那么必须：

- 使用 `history_role="user"`

这是当前主干的硬约束，不是建议。

如果你把带媒体的结果仍然写成 `history_role="tool"`，那么框架不会按“用户多模态物料”去处理它。

### 5.3 推荐的 `meta` 字段

主干会优先识别这些约定字段：

- `meta.source = "tool"`
- `meta.tool_id = <当前 tool_id>`

建议补充：

- `meta.inject_role`：给调试和展示层看的注入意图
- `meta.ui_notice`：给模型和开发者看的说明文本
- `meta.max_inline_bytes`：Tool 视频的更严格体积上限
- `meta.max_duration_seconds`：Tool 视频的更严格时长上限

不要在 `meta` 里塞供应商特有字段。供应商兼容不是 Tool 层的职责。

## 6. 从零开始写一个最小文本 Tool

下面是一个最小的文本 Tool 形态：

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from tool_runtime.host import ToolHostBridge
from tool_runtime.result import ToolOutcome, ToolPart


TOOL_ID = "hello_tool"
DISPLAY_NAME = "问候工具"
DESCRIPTION = "返回一段简单问候语。"
PARAMETERS = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "要问候的人名"},
    },
    "required": ["name"],
}


class CONFIG_MODEL(BaseModel):
    model_config = ConfigDict(extra="ignore")
    GREETING_PREFIX: str = Field(default="你好", title="问候前缀")


async def hello_tool(
    name: str,
    tool_host: ToolHostBridge | None = None,
    tool_config: CONFIG_MODEL | None = None,
) -> ToolOutcome:
    config = tool_config or CONFIG_MODEL()
    text = f"{config.GREETING_PREFIX}，{str(name or '').strip() or '陌生人'}！"
    return ToolOutcome(
        parts=[
            ToolPart(
                type="text",
                text=text,
                meta={"source": "tool", "tool_id": TOOL_ID, "inject_role": "tool"},
            )
        ],
        is_error=False,
        history_role="tool",
        trace_title="Tool | hello_tool",
        trace_summary=TOOL_ID,
    )
```

这种 Tool：

- 只返回文本
- 不涉及多模态
- 参数保持最小，不引入窗口或用户指定字段
- 通常使用 `history_role="tool"`

## 7. 写一个图片 Tool 的正确方式

图片 Tool 的标准形态不是“直接把图发到聊天框”，而是：

1. 生成图片
2. 交给宿主管理文件
3. 返回“说明文本 + 图片路径”
4. 用 `history_role="user"` 回流给主干

这是当前 `magic_draw` 家族遵循的合同，也是推荐做法。

```python
from tool_runtime.host import ToolHostBridge
from tool_runtime.result import ToolOutcome, ToolPart


TOOL_ID = "demo_image"


async def demo_image_tool(
    prompt: str,
    tool_host: ToolHostBridge | None = None,
) -> ToolOutcome:
    if tool_host is None:
        return ToolOutcome(
            parts=[ToolPart(type="text", text="demo_image 缺少 tool_host")],
            is_error=True,
            history_role="tool",
            trace_title="Tool | demo_image",
            trace_summary="missing_host",
        )

    managed = await tool_host.write_managed_file(
        "/abs/path/to/generated.png",
        file_name="demo_image.png",
        mime_type="image/png",
    )
    notice = f"图片已生成，但未发送到聊天框。产物路径：{managed.managed_path}"
    return ToolOutcome(
        parts=[
            ToolPart(
                type="text",
                text=notice,
                meta={"source": "tool", "tool_id": TOOL_ID, "inject_role": "user", "ui_notice": notice},
            ),
            ToolPart(
                type="image",
                url=managed.managed_path,
                mime_type=managed.mime_type or "image/png",
                meta={"source": "tool", "tool_id": TOOL_ID, "inject_role": "user", "ui_notice": notice},
            ),
        ],
        history_role="user",
        trace_title="Tool | demo_image",
        trace_summary=TOOL_ID,
    )
```

### 7.1 为什么图片 Tool 不自己发图

因为我们希望：

- 模型能“看见”这次 Tool 产物
- 下一轮还能继续围绕这张图做推理或继续调用 Tool
- 聊天发送链不被 Tool 自己打乱

所以 `magic_draw` 现在的标准文案是：

- 已生成
- 未发送到聊天框
- 带真实产物路径

这不是多余描述，而是给模型和开发者都看的关键信号。

## 8. 视频 Tool 的特殊规则

视频 Tool 和图片 Tool 不一样，主干会对它做更严格保护。

### 8.1 默认保护条件

只要某个 `ToolPart` 同时满足：

- `type == "video"`
- `meta.source == "tool"`

主干就会把它视为受保护的 Tool 视频。

如果你明确不想走这条保护链，才需要设置：

- `meta.preserve_video = false`

### 8.2 当前默认限制

当前主干默认限制是：

- 最多只保留最近 `1` 条 Tool 视频
- 大小限制 `<= 8MB`
- 时长限制 `<= 60s`

如果视频超出限制，框架会尝试：

- 先压缩/转码进限制
- 还不行，就降级为带原因和产物路径的文本说明

### 8.3 它和普通聊天视频有什么不同

普通聊天视频会继续走框架已有的主干：

- 优先尝试 `video -> audio preview`
- 失败则降级为文本说明

但是 Tool 视频会被特殊保护，不会误走普通视频链路。

### 8.4 各协议下的最终效果

当前主干的能力声明是：

- `gemini`：接受 `image/audio/video`
- `responses`：接受 `image`，`audio/video/file` 会在发射器层降级为文本
- `openai_chat`：接受 `image`，`audio/video/file` 会在发射器层降级为文本

所以你写视频 Tool 时，不需要在 Tool 内部分叉：

- “如果是 Gemini 就返回 video”
- “如果是别家就返回 file 或 text”

这类判断都不该出现在 Tool 里。你只需要返回统一的 `ToolOutcome`。

## 9. `ToolHostBridge`：Tool 能向宿主要什么

Tool 对宿主的依赖全部走 `tool_runtime/host.py` 中的 `ToolHostBridge`。

常见能力包括：

- `log(...)`：写结构化日志
- `http_request(...)`：发起 HTTP 请求
- `read_local_bytes(...)`：读取本地文件字节
- `write_managed_file(...)`：把产物写入宿主管理文件区
- `resolve_media_ref(...)`：把引用解析为可读媒体路径/引用
- `invoke_model(...)`：调用模型能力
- `list_files(...)` / `read_text_file(...)` / `search_text(...)`
- `run_command(...)`
- `write_text_file(...)` / `apply_text_patch(...)`
- `send_text(...)` / `send_file(...)`
- `read_state_json(...)` / `write_state_json(...)`

### 9.1 选择宿主接口时的原则

- 需要持久状态：优先用 `read_state_json(...)` / `write_state_json(...)`
- 需要文件产物：优先用 `write_managed_file(...)`
- 需要模型能力：优先用 `invoke_model(...)`
- 需要项目读写：优先复用已有文件操作能力，而不是自己乱拼系统命令

### 9.2 不要把 Tool 写成“框架特化插件”

虽然 Tool 理论上可以很强，甚至可以修改宿主项目文件，但它仍然应该遵守统一边界：

- Tool 专注业务动作
- 宿主负责安全边界、权限边界、协议边界、管理边界

这能保证未来新 Tool 不会因为 payload 兼容问题反复返工。

## 10. 什么时候注册到哪里

### 10.1 普通公开 Tool

放到：`holo_cortex_zero/services/tools/migrated/__init__.py`

适合：

- 天气
- 搜索
- 绘图
- 公开可见的用户能力

### 10.2 高级维护 Tool

放到：`holo_cortex_zero/services/tools/advanced/file_ops.py`

适合：

- 看文件
- 读文件
- 搜索代码
- 跑命令
- 写文件
- 打补丁

这一类 Tool 通常固定为 `advanced_only`，不会暴露给普通上下文。

### 10.3 系统 Tool

放到对应系统服务内部注册。

例如：

- `echo`

这种 Tool 是系统能力的一部分，不等同于普通业务 Tool。

## 11. 注册时常用的参数该怎么选

宿主注册统一走 `tool_registry.register(...)`。

你最常用到的字段是：

- `name`：Tool ID
- `display_name`：展示给管理面的名称
- `handler`：你的异步处理函数
- `description`：给模型看的描述
- `parameters`：JSON Schema
- `source_kind`：来源类型
- `capability_class`：`user_facing` 或 `privileged`
- `default_scope`：推荐初始启用范围，最终以用户 YAML 配置为准
- `supports_multimodal_return`：是否支持多模态返回
- `config_model`：配置模型

### 11.1 最常见的两类配置

普通 Tool 常见配置：

- `capability_class="user_facing"`
- `default_scope="all"`

高级维护 Tool 常见配置：

- `capability_class="privileged"`
- `default_scope="advanced_only"`

如果你不确定，就先参考现有同类 Tool 的注册方式，不要发明新的权限心智。

## 12. 如何做非污染式验证

我们推荐的验证方式是：**进程内仿真**。

不要为了验证 Tool，直接去真实群聊或私聊试错。

### 12.1 建议的验证方法

- 直接调用 Tool handler，配 fake `ToolHostBridge`，检查 `ToolOutcome` 结构
- 直接调用 `tool_registry.execute(...)`，验证 scope 与执行期硬拒
- 构造 `GenerationRequest`，调用 `LLMRouter._prepare_request(...)`，验证多模态 rewrite 是否符合预期
- 对图片、音频、视频使用临时文件验证路径、限额、降级说明

### 12.2 你至少要检查这几件事

- Tool 返回值是否始终是 `ToolOutcome`
- 多模态 Tool 是否使用了 `history_role="user"`
- `meta.source` 和 `meta.tool_id` 是否正确
- 普通用户是否真的无法执行高级 Tool
- 视频 Tool 在非 Gemini 路径下是否仍能被主干稳定降级
- 图片 Tool 是否只回注上下文、不直接发聊天框

## 13. 当前仓库里的推荐参考实现

如果你想模仿现有成熟写法，推荐看这些：

- `tool_runtime/tools/magic_draw.py`：图片 Tool 的标准形态
- `tool_runtime/tools/file_ops.py`：高级维护 Tool 的标准形态
- `tool_runtime/tools/weather.py`：典型文本 Tool
- `tool_runtime/tools/seek.py`：普通公开 Tool 的接入方式
- `holo_cortex_zero/services/tools/migrated/__init__.py`：普通 Tool 注册方式
- `holo_cortex_zero/services/tools/advanced/file_ops.py`：高级 Tool 注册方式

### 13.1 `magic_draw` 应该怎么理解

现在的 `magic_draw` 是一组 Tool，不是历史插件，也不是给模型直呼的旧函数壳。

它的关键合同是：

- 高价值绘图 prompt 保留在 Tool 内部
- Tool 返回“说明文本 + 图片路径”
- 使用 `history_role="user"`
- 明确写“已生成，但未发送到聊天框”
- 不让 Tool 自己擅自往聊天框发图

如果你要开发新的绘图类 Tool，优先沿用这套合同。

## 14. 常见错误

### 错误 1：在 Tool 里直接 `import holo_cortex_zero.*`

后果：

- Tool 失去纯洁性和可迁移性
- 以后脱离当前宿主时很难拆

正确做法：

- 把对宿主的依赖改走 `ToolHostBridge`

### 错误 2：多模态 Tool 还返回 `history_role="tool"`

后果：

- 图片/音频/视频不会按用户多模态物料进入下一轮上下文

正确做法：

- 多模态结果用 `history_role="user"`

### 错误 3：Tool 自己拼 Gemini / Responses / OpenAI Chat payload

后果：

- 未来协议一变，你的 Tool 直接失效
- 同一能力会被迫维护多套分支

正确做法：

- Tool 只返回统一 `ToolOutcome`

### 错误 4：普通 Tool 直接把图片发到聊天框

后果：

- 上下文回流链被绕开
- 模型下一轮未必能“看见”自己的 Tool 产物

正确做法：

- 回传说明文本 + 媒体路径，让主干处理注入

### 错误 5：只做“前面不展示”的软权限控制

后果：

- 模型误构造调用时仍可能打到不该执行的 Tool

正确做法：

- 依赖主干统一的执行期硬拒，不要绕过 `tool_registry.execute(...)`

## 15. 开发完成后的检查清单

交付前，至少逐项确认：

- Tool 代码只依赖 `tool_runtime/*`
- Tool 参数 schema 清晰可读
- Tool 配置模型可以持久化、可在 UI 查看
- Tool 已在正确的宿主注册入口挂载
- Tool 能出现在 `/api/tools`
- 多模态 Tool 的 `history_role` 正确
- 多模态 Tool 的 `meta.source` 与 `meta.tool_id` 正确
- Tool 在不允许的权限下会被硬拒
- Tool 产物路径是宿主绝对路径或受主干支持的有效引用
- 验证过程没有污染真实业务聊天窗口

## 16. 一句话总结

在这个仓库里写 Tool，最重要的不是“写出能跑的 Python”，而是**把功能写进统一主干**。

只要你遵守下面这三条：

1. Tool 保持纯实现，不直接依赖 `holo_cortex_zero.*`
2. Tool 只返回统一的 `ToolOutcome`
3. 权限、回流、协议兼容都交给框架主干

那么这个 Tool 才会真正可维护、可迁移、可调试，也才配得上进入当前系统。
