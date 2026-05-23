# 2026-04-03 普通 context 回忆门控与 48→10 窗口回收

## 背景

普通 context 之前每轮都会重跑潜意识 / Stage1 / Stage2 回忆，并继续参与 timeline 压缩，普通链路算力开销偏高。

本轮按最小改动收口为：

- 只改普通 context
- 高级 context 完全不动
- 普通 context 的 recall 改为每 `N` 次用户触发刷新一次，默认 `N=4`
- 非刷新轮直接复用上次 recall 缓存
- 普通 context 关闭 timeline 触发、摘要应用与摘要注入
- 普通 context 原始上下文累计到 `48` 后，不做滑动窗口，而是一次性回收到最近 `10` 条

## 主链路整理

### 1. recall 门控只放编排层

普通 context 的“这轮重算 recall 还是复用缓存”属于 agent 编排策略，因此只放在：

- `holo_cortex_zero/services/agent/run_agent_v2.py`

没有把普通用户门控逻辑塞进：

- `memory/runtime.py`
- `memory/recall.py`
- `memory/auto_memory.py`

### 2. automemory 保持原逻辑

`automemory` 的按消息数触发逻辑未改。

本轮只是在普通 context 真实刷新 recall 时，继续更新现有的 recall snapshot，让 auto_memory 自然沿用主链这份 snapshot；并未修改其 worker、计数阈值与写记忆主链。

### 3. 普通 context 的 48→10

普通 context 的历史窗口不是滑动 48，也不是压缩成摘要，而是：

- 小于 48：正常累计
- 达到 48：一次性删除旧上下文，只保留最近 10 条
- 再从 10 条继续往后增长

### 4. 普通 context 关闭 timeline

本轮同时做了三层收口：

1. 不触发 timeline 任务
2. 不应用 pending summary
3. 不注入 `compressed_summary`

这样避免旧摘要继续影响普通 context payload。

## 配置项

新增：

- `NORMAL_CONTEXT_MEMORY_RECALL_REFRESH_EVERY`：默认 `4`
- `NORMAL_CONTEXT_RESET_THRESHOLD_MESSAGES`：默认 `48`
- `NORMAL_CONTEXT_RESET_KEEP_MESSAGES`：默认 `10`

## 日志补充

新增日志点：

- 普通 context recall 缓存缺失，立即刷新
- 普通 context recall 复用缓存
- 普通 context recall 达到阈值后重算
- 普通 context 达到阈值时执行 `48 -> 10` 历史回收

## 风险与回滚点

风险较小，改动集中在普通 context 的编排与窗口管理层。

若要快速回滚：

1. 将 `NORMAL_CONTEXT_MEMORY_RECALL_REFRESH_EVERY` 设为 `1`
2. 将 `NORMAL_CONTEXT_RESET_THRESHOLD_MESSAGES` 调大，或将 `NORMAL_CONTEXT_RESET_KEEP_MESSAGES` 调整为更高值
3. 若仍需完全回退，再撤销以下文件改动：
   - `holo_cortex_zero/core/config.py`
   - `holo_cortex_zero/services/agent/run_agent_v2.py`
   - `holo_cortex_zero/services/context_window/manager.py`
   - `holo_cortex_zero/services/context_window/assembler.py`

## 本轮验证

已执行：

- `python3 -m py_compile holo_cortex_zero/core/config.py holo_cortex_zero/services/agent/run_agent_v2.py holo_cortex_zero/services/context_window/manager.py holo_cortex_zero/services/context_window/assembler.py`

本轮未执行：

- 容器重建
- 线上真实聊天验证
