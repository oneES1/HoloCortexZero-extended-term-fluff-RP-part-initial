# 2026-05-09 高级 deek 指令触发名修正

## 背景

高级 context 模式主干仍是 `norm / deek / deep`，本次只调整 `deek` 的手工触发命令名。

## 定位

- 真实命令注册表在 `holo_cortex_zero/services/advanced_context_mode.py`。
- 当前 `deek` 模式实际绑定为 `/cat`。
- 本次没有改动群聊类型 `group`、`chat_key`、窗口路由、prompt 字段或模型组选择逻辑。

## 修改

- 将 `deek` 模式的 `command` 从 `/cat` 改为 `/cute`。
- 保持 `norm`、`deep`、ack 文案、prompt 字段、模型组字段不变。

## 影响

- 高级用户发送 `/cute` 会切换到 `advanced_context_mode=deek`。
- `/cat` 不再作为 `deek` 模式命令入口。
- 普通用户发送 `/cute` 仍按既有逻辑忽略，不写聊天历史、不触发 LLM。

## 验证

```bash
.venv/bin/python -m py_compile holo_cortex_zero/services/advanced_context_mode.py
python3 - <<'PY'
from pathlib import Path
source = Path('holo_cortex_zero/services/advanced_context_mode.py').read_text()
assert 'name="deek"' in source
assert 'command="/cute"' in source
assert 'command="/cat"' not in source
print('ok')
PY
```

## 回滚点

- Git 提交：恢复 `holo_cortex_zero/services/advanced_context_mode.py` 中 `deek.command` 为 `/cat`。
