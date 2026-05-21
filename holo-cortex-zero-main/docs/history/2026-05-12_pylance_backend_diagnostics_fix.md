# 2026-05-12 Pylance backend diagnostics fix

## 背景

用户反馈 Pylance 在后端文件中集中报错，主要包含：

- `logger` 作为 `holo_cortex_zero.core` 包级导入符号未知。
- `services/context_window/manager.py` 多处 `List` 未定义。
- `manager.py` 两处 `MessagePart(type=part_type, ...)` 无法收窄到 IR 允许的 literal 类型。
- `services/memory/runtime.py` 潜意识 TypedDict 输出与普通 dict 类型标注混用。
- `tortoise` / `tortoise.transactions` / `tortoise.expressions` 无法解析。

## 证据

- `uv run python -c "import tortoise, tortoise.transactions, tortoise.expressions; print(tortoise.__version__)"` 返回 `0.24.0`。
- `.venv/bin/python -c "import sys, tortoise; print(sys.executable); print(tortoise.__version__)"` 返回 `.venv/bin/python` 与 `0.24.0`。
- 因此 `tortoise` 解析失败不是后端依赖缺失，而是 Pylance 当前解释器没有指向项目 `.venv`。

## 修改

- `manager.py` 补回 `typing.List` 导入。
- `manager.py` 将音频/视频文件段构造从 `part_type` 动态字符串改为明确的 `"audio"` / `"video"` literal，保持原分支行为不变。
- `graph_cache.py` 将 `apply_cache_updates` 参数从 `Dict` 放宽为只读 `Mapping`，匹配 TypedDict 输出的只读访问用法。
- `runtime.py` 将潜意识 `intents` 先落到 `Any` 原始值，再过滤成 `List[Dict[str, Any]]`，消除 TypedDict 与普通 dict 的静态类型混淆。

## 验证

- `uv run python -m compileall holo_cortex_zero` 通过。

## 备注

VS Code / Pylance 仍需选择解释器：

- `/path/to/source-root/.venv/bin/python`

若窗口打开在仓库父目录或 `/path/to<CONTAINER_WORKSPACE_DIR>`，需要在对应工作区手动选择该解释器，否则第三方包解析仍可能报错。
