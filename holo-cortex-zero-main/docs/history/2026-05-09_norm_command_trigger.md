# 2026-05-09 高级 norm 指令触发名修正

## 背景

高级 context 模式主干仍是 `norm / deek / deep`，文档与状态机约定 `norm` 模式由 `/norm` 精确触发。

## 定位

- 真实命令注册表在 `holo_cortex_zero/services/advanced_context_mode.py`。
- 当前 `norm` 模式实际绑定为 `/kitty`，导致用户发送 `/norm` 无法命中 `advanced_context_mode_service.parse_mode_command()`。
- 本次没有改动群聊类型 `group`、`chat_key`、窗口路由或模型组选择逻辑。

## 修改

- 将 `norm` 模式的 `command` 从 `/kitty` 改为 `/norm`。
- 保持 `deek`、`deep`、ack 文案、prompt 字段、模型组字段不变。

## 影响

- 高级用户发送 `/norm` 会切换到 `advanced_context_mode=norm`。
- `/kitty` 不再作为 `norm` 模式命令入口。
- 普通用户发送 `/norm` 仍按既有逻辑忽略，不写聊天历史、不触发 LLM。

## 验证

```bash
.venv/bin/python -m py_compile holo_cortex_zero/services/advanced_context_mode.py
python3 - <<'PY'
from pathlib import Path
source = Path('holo_cortex_zero/services/advanced_context_mode.py').read_text()
assert 'name="norm"' in source
assert 'command="/norm"' in source
assert 'command="/kitty"' not in source
print('ok')
PY
```

说明：直接导入 `AdvancedContextModeService` 会触发当前包初始化链路中的既有循环导入，故本次用 `py_compile` + 源码断言验证命令名。

## 回滚点

- Git 提交：恢复 `holo_cortex_zero/services/advanced_context_mode.py` 中 `norm.command` 为 `/kitty`。
