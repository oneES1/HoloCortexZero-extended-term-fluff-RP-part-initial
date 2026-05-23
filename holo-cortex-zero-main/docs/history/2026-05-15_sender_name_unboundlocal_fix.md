# 2026-05-15 sender_name UnboundLocalError 修复记录

## 现象

运行态日志报错：

```text
run_agent_v2 执行失败: cannot access local variable 'sender_name' where it is not associated with a value
```

## 根因

`holo_cortex_zero/services/context_window/manager.py` 的 `_build_context_msg_prefix()` 中，`sender_name` 的赋值缩进到了 `if not sender_id:` 分支内部。

当 `sender_id` 非空时，代码会直接执行后续：

```python
if not sender_name:
```

此时 `sender_name` 尚未定义，触发 `UnboundLocalError`，导致上下文文本组装中断，最终让消息链路回不了消息。

## 影响面

- 普通 context 归档文本补前缀失败
- 上下文注入链路中断
- 触发 `run_agent_v2` 上游任务失败，表现为消息不回复

## 修复

将 `sender_name` 提前到函数级别赋值，保证无论 `sender_id` 是否为空都先获得稳定初值。

## 回滚点

如需回滚，只需恢复 `holo_cortex_zero/services/context_window/manager.py` 中 `_build_context_msg_prefix()` 的这次缩进修正。
