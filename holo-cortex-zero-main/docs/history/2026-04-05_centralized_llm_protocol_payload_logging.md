# 2026-04-05 新框架各协议集中记录真实出站 payload

## 背景

当前主 LLM payload 日志存在两个问题：

- `/responses` 有单独写盘逻辑，但 `chat` / `gemini` 没有统一覆盖。
- 某些协议存在最终发包前的兼容改写，如果过早落日志，看到的是中间产物，不是实际发出去的请求体。

这会导致排查时“payload 日志是散装的”，不同协议口径不一致，也不容易确认最终 wire body。

## 当前逻辑梳理

- `holo_cortex_zero/services/llm/responses.py`
  - 原本自带 `_dump_payload()` / `_dump_response()`。
  - 已经比较接近真实发包点，但实现散落在协议文件内部。
- `holo_cortex_zero/services/llm/openai_chat.py`
  - 之前没有集中写主 payload 日志。
- `holo_cortex_zero/services/llm/gemini.py`
  - 之前没有集中写主 payload 日志。
  - 且 Gemini 兼容重试会在多种 payload 形状间切换，必须记录每次真正尝试发出的版本。

## 本次最小修改

- 新增共享日志器：`holo_cortex_zero/services/llm/prompt_logging.py`
- 统一把请求日志挂到“真正调用 `httpx.post()` / `httpx.stream()` 之前”
- 覆盖协议：
  - `chat`
  - `responses`
  - `gemini`
- 日志文件根对象直接写最终 JSON body，不额外包一层 envelope，避免把元信息混进 payload 本体
- `responses` 的 response dump 保持可用，但改为复用共享日志器
- Gemini 若触发兼容 style 重试，每次实际尝试都会单独落一份 `styleXX` 请求日志

## 影响分析

正向影响：

- 三条新框架协议的 payload 日志口径统一
- 日志位置集中，后续扩协议时不必再各写一套
- 看到的是最终出站 body，而不是早期中间构造物
- Gemini 兼容重试终于能看到“到底哪一版 payload 被真正发过”

兼容边界：

- 本次只收口请求/响应日志，不改协议判定，不改业务路由，不改供应商兼容分支行为
- 不记录请求头，避免把鉴权头一起打进日志；payload 体仍按原样落盘

## 修改文件

- `holo_cortex_zero/services/llm/prompt_logging.py`
- `holo_cortex_zero/services/llm/openai_chat.py`
- `holo_cortex_zero/services/llm/responses.py`
- `holo_cortex_zero/services/llm/gemini.py`

## 风险与回滚点

风险较低：

- 只改日志收口位置，不改请求内容主干
- 唯一新增行为是 `chat` / `gemini` 会开始写 prompt 日志，磁盘写入量会增加

建议回滚点：

- `fix(llm): centralize outbound payload logging`
