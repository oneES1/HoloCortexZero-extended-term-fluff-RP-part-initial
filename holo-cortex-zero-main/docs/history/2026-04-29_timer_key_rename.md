# 2026-04-29 Timer Key 命名收口

## 背景

`echo` 已改为按 `context_id` 绑定定时，但底层 `timer_service.py` 仍以 `chat_key` 命名定时器分区键，容易误解为定时直接绑定回复窗口。

## 当前逻辑

- `timer_service` 的分区键统一命名为 `timer_key`。
- `moment echo` 传入的 `timer_key` 是 `context_id`。
- 旧 fallback 仍保留：当没有 callback 且 `trigger_time == 0` 或只有 `event_desc` 时，`timer_key` 会被当作旧 `chat_key` 使用以触发窗口或推送系统消息。
- 节日提醒专用公共定时分区改名为 `FESTIVAL_TIMER_KEY`。

## 修改点

- `holo_cortex_zero/services/timer_service.py`
  - `TimerTask.chat_key` 改为 `TimerTask.timer_key`。
  - `set_timer(chat_key=...)` / `get_timers(chat_key)` 参数改为 `timer_key`。
  - 日志和注释改为“分区 / timer_key”，并标明旧 `chat_key` fallback。
- `holo_cortex_zero/services/festival_service.py`
  - `FESTIVAL_CHAT_KEY` 改为 `FESTIVAL_TIMER_KEY`。
  - 调用 `timer_service.set_timer` 时使用 `timer_key=`。

## 验证

- `python3 -m py_compile holo_cortex_zero/services/timer_service.py holo_cortex_zero/services/festival_service.py holo_cortex_zero/services/moment/service.py`

## 回滚点

- 上一提交：`ba73a6d fix(moment): merge vow persistence into echo`
