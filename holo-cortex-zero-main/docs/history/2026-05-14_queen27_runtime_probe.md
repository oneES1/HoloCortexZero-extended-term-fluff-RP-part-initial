# 2026-05-14 Queen27 运行态探测：缓存、速度、多模态、Tool Call

## 环境

远端服务：`hcz` 上的 `meromero-gguf.service`，实际模型已替换为 Queen。

进程关键参数：

```text
-m /path/to/services/qwen35_stack/models-gguf/Qwen3.6-Queen-27B-Q4_K.gguf
--mmproj /path/to/services/qwen35_stack/models-gguf/mmproj-Qwen3.6-Queen-27b-BF16.gguf
-c 36352
-b 384
-ub 384
-np 2
--cache-prompt
-cpent 512
--alias qwen36-queen-27b-mm-q4
```

模型接口：

```text
/v1/models -> qwen36-queen-27b-mm-q4
capabilities: completion, multimodal
n_params: 26895998464
size: 16536406016
```

## 重要探测前提

直连 llama-server 时，如果只传 `max_tokens`，slot 状态显示 `n_predict=-1`，模型会进入长时间 `<think>` 输出。后续受控测试同时传：

```json
{
  "thinking": {"type": "disabled"},
  "chat_template_kwargs": {"enable_thinking": false},
  "max_tokens": N,
  "n_predict": N
}
```

HCZ 正常本地 chat 路径会把模型组 `thinking.disabled` 归一化为 `chat_template_kwargs.enable_thinking=false`，因此该异常属于裸直连测试参数问题，不代表 HCZ 运行态必然无限思考。

## 动态尾端缓存

测试构造：同一 slot 发送约 2939 prompt token 的固定前缀，只改变尾端文本。

结果：

```text
slot0 首次：elapsed=2.542s, prompt_tokens=2939, cached_tokens=0
slot0 改尾：elapsed=0.421s, prompt_tokens=2939, cached_tokens=2555
slot1 同文：elapsed=2.464s, prompt_tokens=2939, cached_tokens=0
slot0 再发：elapsed=0.095s, prompt_tokens=2939, cached_tokens=2935
```

结论：

- 同 slot 动态尾端缓存有效。
- 不同 slot 缓存隔离有效。
- llama-server usage 的 `prompt_tokens_details.cached_tokens` 可直接作为缓存证据。

## Decode 速度

文本生成受控测试，单请求单 slot：

```text
max_tokens=128 -> completion_tokens=103, elapsed=2.621s, decode=39.30 tok/s
max_tokens=256 -> completion_tokens=71,  elapsed=1.811s, decode=39.21 tok/s
max_tokens=512 -> completion_tokens=198, elapsed=4.887s, decode=40.51 tok/s
```

结论：当前 Queen27 Q4_K 在本机单 slot decode 约 `39-40 tok/s`。`-np 2` 理论双路并行上限仍要按业务并发实测，但单槽速度满足此前 Mero 方案量级。

## Tool Call

请求：`tools=[record_memory]`，`tool_choice=auto`，要求记录 `Queen27 tool call works`。

结果：

```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "type": "function",
      "function": {
        "name": "record_memory",
        "arguments": "{\"content\":\"Queen27 tool call works\"}"
      }
    }
  ]
}
```

耗时与 token：

```text
elapsed=1.129s
prompt_tokens=304
completion_tokens=32
```

结论：OpenAI-compatible 标准 tool_call 可用，且不是文本伪 tool_call。

## 多模态

测试图片：本地生成 `1024x512` 白底黑字 PNG：

```text
QUEEN OCR TEST
SAMPLE LINE 02
A9Z8K7 M3R0
```

API 返回不匹配输入：

```text
case OCR -> BUTTERFLY / FISH / AQUARIUM
case describe -> BUTTERFLY / INFLUENCE / AFTERMATH
case largest line -> OUR TEAM
```

服务日志证据显示图片确实进入了后端处理链：

```text
srv process_chun: processing image...
encoding image slice...
image slice encoded in ~115-126 ms
decoding image batch 1/2, n_tokens_batch = 384
image decoded (batch 1/2) in ~175-178 ms
decoding image batch 2/2, n_tokens_batch = 128
image decoded (batch 2/2) in ~188-191 ms
srv process_chun: image processed in ~483-489 ms
prompt eval time ~= 677-707 ms / 531-539 tokens
```

同时日志出现：

```text
find_slot: non-consecutive token position ... for sequence ... with 384 new tokens
```

结论：

- llama-server 确实接收并处理了 image_url，不是 HCZ/测试 payload 没传图。
- 但当前 `Qwen3.6-Queen-27B-Q4_K.gguf + mmproj-Qwen3.6-Queen-27b-BF16.gguf` 的图片结果与输入严重不一致。
- 多模态链路当前不能判定可用，至少 OCR 不可信。
- 该问题更接近 GGUF/mmproj/llama.cpp 对 Qwen3.6-Queen 多模态的兼容问题，而不是 HCZ 图片缩放问题；本测试图片为 1024 长边，未被 HCZ 处理。

## 总结

- 动态尾端缓存：可用，有数值证据。
- slot 隔离：可用，有数值证据。
- decode：单槽约 `39-40 tok/s`。
- tool_call：可用，标准 `tool_calls` 返回。
- 多模态：后端处理了图片，但输出不对应输入，当前不可信，需要单独排查 GGUF/mmproj/llama.cpp 兼容性或更换多模态后端/权重组合。
