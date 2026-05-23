# 2026-04-05 主 LLM payload 日志文件名改为“模型名 + 时间”

## 背景

主 LLM `/responses` 请求/响应日志原先使用秒级时间戳命名：

- `v2_request_<ts>.json`
- `v2_response_<ts>.json`

当同一秒内出现多次主 LLM 调用时，日志文件会互相覆盖，表现为：

- payload 日志“看不到了”
- request/response 配对错位
- 排查时误以为日志损坏

## 当前逻辑梳理

主链写盘位置：

- `holo_cortex_zero/services/llm/responses.py`
  - `_dump_payload()`：写 `v2_request_*.json`
  - `_dump_response()`：写 `v2_response_*.json`

日志目录：

- `holo_cortex_zero/core/os_env.py`
  - `PROMPT_LOG_DIR = DATA_DIR + "/logs/prompts"`

## 本次最小修改

只修改主链文件名生成规则，不改协议、不改请求内容、不改供应商分支兼容逻辑。

改为：

- 从 payload 中提取 `model`
- 将模型名做文件名安全化
- 与高精度本地时间拼成同一个 `dump_id`
- request/response 共享同一个 `dump_id`

新的文件名形式：

- `v2_request_<safe_model>_<YYYYMMDD_HHMMSS_microseconds>.json`
- `v2_response_<safe_model>_<YYYYMMDD_HHMMSS_microseconds>.json`

示例：

- `v2_request_qwen35-27b-mm-int4_20260405_153012_123456.json`
- `v2_response_qwen35-27b-mm-int4_20260405_153012_123456.json`

## 影响分析

正向影响：

- 同一秒内多次调用不再互相覆盖
- request/response 配对更直观
- 直接从文件名就能看出模型来源

兼容影响：

- 只影响新增日志文件名
- 不影响历史日志读取
- 当前代码库内未发现其他地方硬编码解析旧 `v2_request_<ts>.json` / `v2_response_<ts>.json` 文件名

## 风险与回滚点

风险较低：

- 仅变更日志文件名，不改主 LLM 协议行为
- 若外部人工脚本依赖旧文件名格式，需同步更新筛选规则

回滚点：

- `backup(worktree): snapshot before prompt log rename`

