# 2026-05-09 高级模式指令反馈文案修正

## 背景

高级 context 手工模式切换命令已经收口为：

- `norm`：`/norm`
- `deek`：`/cute`
- `deep`：`/puss`

本次只调整命令命中后的聊天框反馈文案。

## 定位

- 真实反馈文案在 `holo_cortex_zero/services/advanced_context_mode.py` 的 `AdvancedContextModeSpec.ack_text`。
- `message_service.py` 命中模式命令后直接发送 `mode_command.ack_text`。
- 本次不改命令解析、权限判断、窗口锚定、模式落库、prompt 或模型组路由。

## 修改

- `norm` 反馈从 `我会用最kitty和honest的方式稳稳地接住你` 改为 `好的喵`。
- `deek` 反馈从 `正常了，喵！` 改为 `(≧▽≦)`。
- `deep` 反馈保持不变。

## 影响

- 高级用户发送 `/norm` 后，切换成功反馈为 `好的喵`。
- 高级用户发送 `/cute` 后，切换成功反馈为 `(≧▽≦)`。
- 普通用户发送这些命令仍按既有逻辑忽略，不写聊天历史、不触发 LLM。

## 验证

```bash
.venv/bin/python -m py_compile holo_cortex_zero/services/advanced_context_mode.py
python3 - <<'PY'
from pathlib import Path
source = Path('holo_cortex_zero/services/advanced_context_mode.py').read_text()
assert 'command="/norm"' in source
assert 'ack_text="好的喵"' in source
assert 'command="/cute"' in source
assert 'ack_text="(≧▽≦)"' in source
assert '我会用最kitty和honest的方式稳稳地接住你' not in source
assert '正常了，喵！' not in source
print('ok')
PY
```

## 回滚点

- Git 提交：恢复 `holo_cortex_zero/services/advanced_context_mode.py` 中 `norm` / `deek` 的 `ack_text`。
