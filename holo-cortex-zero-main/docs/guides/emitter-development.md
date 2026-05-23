# API 协议兼容发射器开发指南

本文是给未来维护者的“从 0 到 1”文档：即使你完全不熟海菜子（HCZ）当前主干，也应该能靠这份文档自己增加一个新的模型 API 发射器（emitter），并知道该把逻辑放在哪一层、不能越界到哪一层。

## 1. 先建立正确心智：什么是 emitter

在 HCZ 里，**emitter 不是“模型组”**，也不是“某个供应商专用分支整套复制”。

它的职责只有两件事：
- 把内部统一 IR（`GenerationRequest`）序列化成某个协议真正要发出去的 payload
- 把该协议返回的数据解析回统一 IR（`GenerationResult`）

换句话说：
- **主干负责**：上下文组装、多模态限额、tool 视频保护、图片物料化、通用路由边界
- **emitter 负责**：协议字段名、请求/流式响应格式、tool call 编码/解析、该协议独有兼容补丁

如果你想新增一个 emitter，请先牢记：

> 不要在 emitter 里再复制一份上下文主干。
> 不要把“某家支持什么媒体”的判断硬写回主干业务逻辑。
> 不要为了一个供应商，再写一套并行主干。

## 2. 整体信息流：一条请求是怎么走的

先看最关键的主链：

1. 上下文系统把聊天消息、tool 返回、系统注入内容组装成 `GenerationRequest`
2. `LLMRouter` 根据当前模型组配置选中某个 emitter
3. `LLMRouter` 在真正发请求前做主干统一归一化：
   - 图片数量限制
   - 图片物料化
   - 音频数量限制
   - 普通视频 `video -> audio/text` rewrite
   - `tool` 视频保护、8MB / 60s 限额、只保留最近 1 条
4. emitter 收到“已经归一化过”的 IR，再序列化成协议 payload
5. 下游返回后，emitter 把结果解析回 `GenerationResult`
6. 上层再决定回复、tool 续链、历史写回

最重要的边界在这里：

- `LLMRouter` 负责 **统一规范化**
- emitter 负责 **协议兼容**

如果你加了新 emitter，但为了图快把媒体预算、tool 视频保护、图片上限这些逻辑写进 emitter，本质上就是把边界搞坏了。

## 3. 先认识内部 IR（这是所有 emitter 的共同语言）

IR 定义在：`holo_cortex_zero/schemas/ir.py:1`

新增 emitter 之前，先把这些类型看懂：

- `MessagePart`
  - 最细粒度消息片段，支持 `text / image / audio / video / file`
  - `url` 可能是宿主机路径，也可能是 URL
  - `data` 是内联二进制
  - `meta` 用于主干携带额外语义，例如 `tool` 媒体标记
- `MessageTurn`
  - 一轮消息，角色是 `system / user / assistant / tool`
  - `tool_calls` 挂在 assistant turn 上
- `ToolSpec`
  - 给模型看的函数 schema
- `GenerationRequest`
  - 发给 emitter 的完整统一请求
- `GenerationResult`
  - emitter 解析后的统一返回

你真正要做的，是实现：
- `GenerationRequest -> 协议 payload`
- `协议响应 -> GenerationResult`

而不是跳过这层直接让上游/下游侵入业务逻辑。

## 4. 现有发射器结构在哪里

### 4.1 抽象基类
基类在：`holo_cortex_zero/services/llm/base.py:1`

关键接口：
- `BaseEmitter.get_media_capabilities()`
- `BaseEmitter.generate()`
- `BaseEmitter.generate_stream()`

同时这里还定义了：
- `EmitterMediaCapabilities`

它是 emitter 对主干公开的**只读能力声明**，当前字段有：
- `name`
- `accepts_image_parts`
- `accepts_audio_parts`
- `accepts_video_parts`
- `native_tool_calling`
- `notes`

### 4.2 路由层
路由主干在：`holo_cortex_zero/services/llm/router.py:1`

最关键的几个点：
- `LLMRouter.__init__()`：持有当前已注册的 emitter 实例
- `LLMRouter._select_emitter()`：根据 `protocol` 选择发射器，见 `holo_cortex_zero/services/llm/router.py:73`
- `LLMRouter._prepare_request()`：统一做主干多模态归一化，见 `holo_cortex_zero/services/llm/router.py:846`
- `LLMRouter.generate()` / `generate_stream()`：先取 emitter 能力声明，再调用 `_prepare_request()`，见 `holo_cortex_zero/services/llm/router.py:930`、`holo_cortex_zero/services/llm/router.py:968`
- `LLMRouter.call_with_fallback()`：主模型组失败时切备用组，见 `holo_cortex_zero/services/llm/router.py:996`

### 4.3 三个现有 emitter
- `OpenAIChatEmitter`：`holo_cortex_zero/services/llm/openai_chat.py:1`
- `ResponsesEmitter`：`holo_cortex_zero/services/llm/responses.py:1`
- `GeminiEmitter`：`holo_cortex_zero/services/llm/gemini.py:1`

它们的共同点是都实现了：
- 能力声明
- 非流式 generate
- 流式 generate_stream
- 协议 payload 构建
- 响应解析

## 5. 现在主干已经帮你做了什么，不要再重复

### 5.1 图片处理
主干在 `LLMRouter` 统一做：
- 图片数量上限
- 超限老图降级为文本
- 物料化（把图片读成内联 bytes / data uri）

对应位置：
- `holo_cortex_zero/services/llm/router.py:846`
- `holo_cortex_zero/services/llm/router.py:730`
- `holo_cortex_zero/services/llm/router.py:828`

因此新增 emitter 时：
- 你只要决定这个协议如何吃 image part
- 不要再写一套自己的图片预算逻辑

### 5.2 音频处理
主干统一做音频数量限制，见：
- `holo_cortex_zero/services/llm/router.py:623`

因此新增 emitter 时：
- 如果支持音频，就序列化 `audio`
- 如果不支持音频，就在 emitter 内降级文本
- 不要在 emitter 自己再砍音频上限

### 5.3 普通视频处理
主干统一做普通视频改写：
- 默认走 `video -> audio preview`
- 如果提取失败，再降级为文本 notice

对应位置：
- `holo_cortex_zero/services/llm/router.py:540`
- `holo_cortex_zero/services/llm/router.py:571`

因此新增 emitter 时：
- 普通视频不是你来判断要不要抽音频
- 你只处理主干已经改写后的 part

### 5.4 tool 视频保护
这是最容易误写的地方。

主干已经统一做：
- 只对 `meta.source == "tool"` 的 video 生效
- 默认保护，除非 `meta.preserve_video = false`
- 只保留最近 1 条 tool 视频
- 限制 `<= 8MB` 且 `<= 60s`
- 不可保留时，统一降级为 notice 文本

对应位置：
- `holo_cortex_zero/services/llm/router.py:273`
- `holo_cortex_zero/services/llm/router.py:339`
- `holo_cortex_zero/services/llm/router.py:440`
- `holo_cortex_zero/services/llm/router.py:540`

新增 emitter 时：
- 如果你的协议支持 video，能力声明写 `accepts_video_parts=True`
- 如果不支持，能力声明写 `False`
- 主干会按能力声明决定是保留还是降级
- 你不需要在 emitter 内再判断“tool 视频特殊逻辑”

## 6. 现有三种 emitter 的最小差异

### 6.1 `OpenAIChatEmitter`
文件：`holo_cortex_zero/services/llm/openai_chat.py:1`

当前能力声明：
- 图片：支持
- 音频：不支持
- 视频：不支持
- tool calling：支持原生 function calling

典型实现点：
- `_turn_to_message()`：IR -> chat.completions message，见 `holo_cortex_zero/services/llm/openai_chat.py:73`
- `_spec_to_function()`：ToolSpec -> function schema，见 `holo_cortex_zero/services/llm/openai_chat.py:164`
- `_parse_response()`：响应 -> GenerationResult，见 `holo_cortex_zero/services/llm/openai_chat.py:177`

适合什么：
- 标准 OpenAI ChatCompletions
- 大多数 OpenAI-compatible chat 网关

### 6.2 `ResponsesEmitter`
文件：`holo_cortex_zero/services/llm/responses.py:1`

当前能力声明：
- 图片：支持
- 音频：不支持
- 视频：不支持
- tool calling：支持原生 tool calling

典型实现点：
- `_turn_to_input_items()`：IR -> `/responses` input item 数组，见 `holo_cortex_zero/services/llm/responses.py:1342`
- `_parse_response()`：响应 -> GenerationResult，见 `holo_cortex_zero/services/llm/responses.py:1496`
- `_responses_compat_reason()`：决定是否套最小兼容补丁，见 `holo_cortex_zero/services/llm/responses.py:138`

适合什么：
- 本地 vLLM `/responses`
- OpenAI Responses 风格网关

### 6.3 `GeminiEmitter`
文件：`holo_cortex_zero/services/llm/gemini.py:1`

当前能力声明：
- 图片：支持
- 音频：支持
- 视频：支持
- tool calling：支持原生 tool calling

典型实现点：
- `_turn_to_content()`：IR -> Gemini content，见 `holo_cortex_zero/services/llm/gemini.py:489`
- `_parse_response()`：响应 -> GenerationResult，见 `holo_cortex_zero/services/llm/gemini.py:645`
- `is_gemini_target()` / `_normalize_base_url()`：Gemini 目标识别与 URL 归一化

适合什么：
- Google Gemini 原生 API
- Gemini relay / gateway

## 7. 新增一个 emitter，最少要改哪些文件

假设你要加一个新协议 `foo`，最小变更面通常是下面几处：

### 必改 1：新增 emitter 文件
例如新增：
- `holo_cortex_zero/services/llm/foo.py`

这个文件至少实现：
- `class FooEmitter(BaseEmitter)`
- `get_media_capabilities()`
- `generate()`
- `generate_stream()`
- 协议 payload 构建函数
- 协议响应解析函数

### 必改 2：在 router 中注册 emitter
文件：`holo_cortex_zero/services/llm/router.py:58`

你需要：
- 在 `LLMRouter.__init__()` 中实例化 `FooEmitter`
- 在 `_select_emitter()` 中加上 `protocol == "foo"` 的返回分支

### 必改 3：让模型组能路由到这个 protocol
文件：`holo_cortex_zero/services/agent/run_agent_v2.py:701`

新增 protocol 最常见做法，是在 `_detect_protocol(group)` 中增加一个**通用可读、可配置**的识别规则，例如：
- 看 `CACHE_TRANSPORT_PROFILE`
- 看 `BASE_URL`
- 看模型族命名

优先顺序建议：
1. 显式配置优先（例如 `CACHE_TRANSPORT_PROFILE`）
2. 明确 host/path 特征
3. 最后才是模型名兜底

### 常见可改 4：需要新的模型组配置提示时，更新配置说明
文件：`holo_cortex_zero/core/config.py:73`

如果你的新协议需要新的 transport profile 名称，至少要保证：
- 配置说明能看懂
- UI/配置文案不会误导别人

### 文档必补 5：补一份专项 MD
因为你这个系统明确要求日志/文档留痕，所以加 emitter 后必须至少补一份文档，写清：
- 为什么要加
- 走哪条路由
- 支持哪些媒体 / tool
- 已做了哪些验证
- 回滚点是什么

## 8. 一个新 emitter 的开发步骤（按顺序做）

这里给一套可直接照抄的顺序。

### 第一步：先定义边界，不要上来就写 payload
先问自己 4 个问题：
- 这个协议支持哪些媒体：image / audio / video / file？
- 这个协议是否原生支持 tool calling？
- 它的请求体是 message 列表、input item 数组、还是 content block？
- 它的流式响应是 delta 文本、event stream、还是整块返回？

这一步的产物应该先写进 `get_media_capabilities()` 和类头注释。

### 第二步：先做非流式 generate
先把最小闭环打通：
- `GenerationRequest -> payload`
- `httpx` 发请求
- `response.json() -> GenerationResult`

不要一上来就做 streaming。非流式先跑通以后，再补流式。

### 第三步：实现流式 generate_stream
你需要保证：
- 流式增量文本能持续 yield
- tool call 如果协议支持，也能在结束时还原出来
- 中途中断 / 超时 / 非法 chunk 不会直接把主线程炸掉

### 第四步：只做协议兼容，不做主干策略
如果你发现自己在 emitter 里想加这些逻辑，请先停一下：
- 图片上限
- 音频上限
- 普通视频抽音频
- tool 视频 8MB / 60s 保护
- 某个高级用户才可见 tool

这些都不是 emitter 该做的事。

### 第五步：补日志
新增 emitter 至少建议加下面几类日志：
- 最终请求目标：`protocol / base_url / model`
- 是否命中兼容分支
- payload 中是否携带 tools
- 流式结束原因
- 解析失败时的摘要，不要整包全量打印大响应

注意：日志要精准，不要无脑全量打大响应。

## 9. 一个最小 emitter 骨架（照着抄）

```python
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Optional

import httpx

from holo_cortex_zero.schemas.ir import GenerationRequest, GenerationResult
from .base import BaseEmitter, EmitterMediaCapabilities


class FooEmitter(BaseEmitter):
    def get_media_capabilities(self) -> EmitterMediaCapabilities:
        return EmitterMediaCapabilities(
            name="foo",
            accepts_image_parts=True,
            accepts_audio_parts=False,
            accepts_video_parts=False,
            native_tool_calling=True,
            notes="简要说明这个协议支持什么，不支持什么。",
        )

    def _build_payload(self, request: GenerationRequest) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": request.model,
            "stream": request.stream,
        }
        return payload

    def _parse_response(self, data: Dict[str, Any]) -> GenerationResult:
        return GenerationResult(
            text="",
            tool_calls=[],
            raw_response=data,
        )

    async def generate(
        self,
        request: GenerationRequest,
        *,
        api_key: str,
        base_url: str,
        proxy: Optional[str] = None,
        timeout: float = 120.0,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> GenerationResult:
        payload = self._build_payload(request)
        headers = {"Authorization": f"Bearer {api_key}"}
        if extra_headers:
            headers.update(extra_headers)
        async with httpx.AsyncClient(proxy=proxy, timeout=timeout, verify=False, trust_env=False) as client:
            resp = await client.post(base_url, json=payload, headers=headers)
            resp.raise_for_status()
            return self._parse_response(resp.json())

    async def generate_stream(
        self,
        request: GenerationRequest,
        *,
        api_key: str,
        base_url: str,
        proxy: Optional[str] = None,
        timeout: float = 120.0,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[GenerationResult, None]:
        payload = self._build_payload(request)
        headers = {"Authorization": f"Bearer {api_key}"}
        if extra_headers:
            headers.update(extra_headers)
        async with httpx.AsyncClient(proxy=proxy, timeout=timeout, verify=False, trust_env=False) as client:
            async with client.stream("POST", base_url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    yield GenerationResult(text=line)
```

上面只是骨架。真正落地时，你必须把：
- IR 序列化
- tool spec 编码
- tool call 解析
- finish_reason / usage 解析
补完整。

## 10. 新手最容易踩的坑

### 坑 1：把“供应商兼容”写成“另一套主干”
错误做法：
- 直接复制一个 Gemini 风格主干到新 emitter
- 在 emitter 里再做媒体预算、tool 视频保护、图片限额

正确做法：
- 主干只保留一份，在 `LLMRouter`
- emitter 只做协议层兼容

### 坑 2：不写能力声明，直接在业务里判断供应商名
错误做法：
- `if protocol == "foo": 允许 video`

正确做法：
- 在 `get_media_capabilities()` 明确声明
- 主干统一只看能力，不看供应商私货

### 坑 3：辅助 LLM 路径和主模型路径混淆
`run_agent_v2` 的 `_detect_protocol()` 是主模型链路用的，见：
- `holo_cortex_zero/services/agent/run_agent_v2.py:701`

但 timeline / subconscious / mem0 等辅助 LLM，有些仍走自己的调用路径，不一定全经过这里。

所以新增 emitter 之后，要分别确认：
- 主模型链会不会命中它
- 辅助 LLM 是否也需要接入，还是应该保持原路径不动

### 坑 4：假设某个 base_url 一定等于某协议
现有代码里已经有一个教训：
- `responses` 和 `gemini` 都可能出现在兼容网关上
- 不能简单用“某家 host”就判断一切

因此协议识别时：
- 优先 `CACHE_TRANSPORT_PROFILE`
- 其次 host/path
- 最后才模型名

### 坑 5：全量打印大响应或大日志
这套系统明确不允许随便全量读/打大日志。
新增 emitter 时：
- 调试日志打印摘要即可
- 大 payload / 大响应只截取必要头尾
- 验证尽量用精确 dry-run，不要污染业务窗口

## 11. 开发完成后的验证清单

最少建议按下面顺序验证。

### A. 纯代码级验证
- 文本请求
- 图片请求（如果支持）
- 音频请求（如果支持）
- 视频请求（如果支持或会被主干降级）
- tool spec 注入
- tool call 解析
- 流式文本

### B. 主干边界验证
重点确认新增 emitter 没把边界打坏：
- 普通视频是否仍由主干改写，而不是 emitter 自己抢处理
- `tool` 视频是否只看能力声明来保留/降级
- 图片/音频上限是否仍由主干生效

### C. 无污染 dry-run
优先做：
- 容器内临时文件
- 进程内调用 `LLMRouter._prepare_request(...)`
- 精准抓日志摘要

尽量不要：
- 直接去群聊试
- 直接污染 QQ/TG 正常对话窗口

### D. 上游实测
如果这个 emitter 对接的是真实模型 API，至少做一轮：
- 文本
- tool call
- 一种最关键媒体类型

## 12. 一个新增 emitter 的推荐提交顺序

建议按下面拆提交，便于回滚：

1. `backup(repo): pre foo emitter snapshot`
2. `feat(llm): add foo emitter`
3. `fix(agent): route foo protocol from model groups`
4. `docs(llm): add foo emitter compatibility notes`

如果只是补文档，也至少补一份专项 MD 说明验证结果。

## 13. 最后一句经验话

新增 emitter 最难的不是“把 JSON 拼出来”，而是**忍住不去破坏主干边界**。

你真正应该做的是：
- 尊重 IR
- 尊重 `LLMRouter` 的统一归一化
- 用能力声明把“能不能吃媒体/tool”说清楚
- 把供应商特有问题收口在 emitter 自己内部

这样未来再加第四种、第五种协议时，系统才不会再次退化回“一家一套并行主干”的老路。
