# 2026-04-02 responses HTTP error 日志收口

## 背景

- QQ 群主链在 `/responses` 收到 400 时，用户侧只看到了 `处理出错: '"error"'`。
- 同批日志里真实上游错误其实是：`At most 6 image(s) may be provided in one prompt.`
- 目标不是在这里修图片数量，而是先把错误日志与 fallback 行为收口，避免日志本身反过来干扰主链。

## 本次修改

- `holo_cortex_zero/services/llm/responses.py`
  - 新增 `_log_http_error`，统一用参数化日志记录上游 HTTP 错误。
  - 避免把原始 JSON 直接拼进日志模板，降低 `error` 花括号干扰日志格式化的风险。
- `holo_cortex_zero/services/llm/router.py`
  - 主模型失败日志外再包一层保护，保证“记录日志失败”不会阻断 fallback 继续执行。

## 预期效果

- 保留真实上游错误信息。
- 即使失败响应体里有复杂 JSON，日志也不应再退化成 `"error"`。
- 即使记录主模型失败日志本身出错，也继续尝试 fallback。
