# 2026-05-12 timeline 孤儿生成锁修复

## 背景

主 LLM `meromero-31b-mm-int4` 最近 trace 的缓存率长期低于 25% 左右：

- `2424`: `prompt_tokens=12065`, `cached_tokens=2843`, `cached_pct=23.56`
- `2425`: `prompt_tokens=12113`, `cached_tokens=2843`, `cached_pct=23.47`
- `2426`: `prompt_tokens=12108`, `cached_tokens=2843`, `cached_pct=23.48`

相邻真实请求 payload 比对显示，第 2 条历史消息起已经发生滑窗位移，服务端只能复用 system 与旧摘要前缀。问题根因转向 timeline 压缩未产出。

## 证据

`context_window` 中 `<ADVANCED_USER_ID>` 的状态：

- `summary_chars=3226`
- `last_compress_version=3`
- `msg_count_since_compress=131`
- `summary_generating=true`
- `pending_summary_ready=false`
- `pending_chars=0`

`context_message` 实际状态：

- `total=88`
- `ADVANCED_CONTEXT_MAX_HISTORY_BEFORE_COMPRESS=74`
- `ADVANCED_CONTEXT_KEEP_RECENT_AFTER_COMPRESS=10`

按阈值 `88 >= 74` 应该触发 timeline，但最近没有 `aux:timeline` trace，也没有 `Timeline: 触发压缩` / `压缩完成` 日志。

## 根因

`summary_generating` 是持久化 DB 字段，而 timeline 的 `_queue` / `_in_flight` 是当前进程内存状态。

后端重启、worker 被取消或任务丢失后，内存队列不可能保留，但 DB 里的 `summary_generating=true` 可能残留。原逻辑在 `maybe_trigger()` 中只要看到 `summary_generating=true` 就直接返回，导致该 context 永久不再入队：

```text
DB: summary_generating=true
内存: 无对应 in-flight job
结果: maybe_trigger 永远 return False
```

这会让 timeline 不再产出摘要，历史消息继续累积并滑窗，主 LLM 缓存只能命中固定短前缀。

## 修改

修复 timeline 状态机不变量：

```text
summary_generating=true 只有在当前进程 _in_flight 持有该 context_id 时才代表真实运行中。
否则视为孤儿生成锁，必须清理并允许重新入队。
```

改动文件：

- `holo_cortex_zero/services/context_window/timeline.py`
  - `maybe_trigger()` 遇到 `summary_generating=true` 时，先检查 `context_id in self._in_flight`。
  - 若不在 `_in_flight`，清理 `summary_generating=false` 并继续触发判断。
- `holo_cortex_zero/services/context_window/manager.py`
  - `on_restart_recover()` 启动恢复时清理 `summary_generating=true && pending_summary_ready=false` 的遗留 timeline 生成锁。

## 影响范围

- 不改 timeline prompt。
- 不改压缩阈值。
- 不改历史清理策略。
- 不改主 LLM 缓存逻辑。
- 不为 `<ADVANCED_USER_ID>` 写特化逻辑，所有 context 共用同一状态机修复。

## 验证计划

重建 `holo_cortex_zero` 后验证：

1. 启动恢复日志出现遗留 timeline 生成锁清理。
2. `summary_generating` 从 `true` 恢复为 `false`。
3. 下一轮链路结束后 `context_message=88 >= 74` 重新触发 timeline。
4. timeline 成功后 `pending_summary_ready=true`。
5. 下一轮请求前应用摘要，`context_message` 清理到约 `10` 条。

## 已完成验证

静态检查：

```bash
python3 -m py_compile holo_cortex_zero/services/context_window/timeline.py holo_cortex_zero/services/context_window/manager.py
```

重建前状态：

- `summary_generating=true`
- `pending_summary_ready=false`
- `pending_chars=0`
- `msg_count_since_compress=131`

仅重建 HCZ 后端本体：

```bash
docker compose -f docker-compose.yml up -d --no-deps --force-recreate holo_cortex_zero
```

重建后状态：

- `summary_generating=false`
- `pending_summary_ready=false`
- `pending_chars=0`
- `msg_count_since_compress=131`

启动日志确认：

```text
重启恢复: 清理上下文窗口 <ADVANCED_USER_ID> 的遗留 timeline 生成锁
Timeline 压缩服务已启动
```

这证明孤儿 DB 锁已经由通用启动恢复逻辑清理。下一轮主链结束时，因为 `context_message=88 >= threshold=74`，会重新进入 `check_and_trigger_compress()` 并派发 timeline。

## 2026-05-12 第二层验证：timeline 自然完成耗时

孤儿锁修复后，timeline 已能触发，但真实业务仍失败。日志显示同一 context 两轮压缩均被重试 5 次后放弃：

- `08:54:43` 触发，`08:56:44/08:58:54/09:01:14/09:03:54/09:07:14` 五次失败，`09:09:54` 最终失败。
- `09:18:46` 触发，`09:20:46/09:22:56/09:25:16/09:27:56/09:31:16` 五次失败，`09:33:56` 最终失败。

原样复放最新 timeline 请求，不修改 payload，仅把测试客户端上限放宽到 900s 防止挂死：

- 请求文件：`v2_request_chat_meromero-31b-mm-int4_20260512_092916_635100.json`
- `message_chars=[839, 14368]`
- `prompt_tokens=12077`
- `max_tokens=3000`
- `max_output_tokens=4500`
- `reasoning={"effort":"high"}`
- `id_slot=1`

自然完成结果：

- `seconds=151.311`
- `finish_reason=stop`
- `cached_tokens=4`
- `completion_tokens=4833`
- `total_tokens=16910`
- `text_chars=4171`

结论：timeline 不是挂死，也不是模型速度故障；当前真实压缩任务自然完成时间约 151s，而业务 timeout 固定为 120s，必然被客户端取消。按实测值将 timeline 专用 LLM timeout 调整为 240s。

本次修改：

- `TimelineService.llm_timeout_seconds` 新增默认值 `120.0`，替代 `_do_compress()` 中的硬编码 `timeout=120.0`。
- 新架构初始化时先设置 `timeline_service.llm_timeout_seconds = 240.0`，后按运维余量要求调整为 `320.0`。


## 2026-05-12 timeout 运维余量调整

基于原样复放自然完成时间 `151.311s` 与后续实际手动修复耗时 `135.558s`，为避免高负载或缓存未命中时再次触发 120s 类失败，将 timeline 专用 LLM timeout 从 `240.0s` 调整为 `320.0s`。不修改 `max_tokens` / `max_output_tokens` / prompt / 模型组。

## 2026-05-14 去掉 timeline 重试

后续运维判断：timeline 压缩是后台异步维护任务，不应在一次失败后继续占用同一个 context 的生成锁做长重试。旧配置在 `320s` timeout 下仍保留 `max_retry=5`，最坏链路为：

- `5 * 320s = 1600s` LLM 等待
- retry backoff：`10 + 20 + 40 + 80 + 160 = 310s`
- 合计约 `1910s`，即 `31.8min`

这会导致一次异常压缩长期占用 timeline worker，并延迟下一次自然触发。按当前策略改为：

- 单次请求最长等待 `600s`
- 失败立即清理 `summary_generating=false`
- 不再指数退避重试

本次不修改 prompt、模型组、摘要输出长度或历史清理策略。
