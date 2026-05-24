# System LLM Select Metadata Fix

## 背景

系统配置页中部分 LLM 相关配置项被渲染成普通文本输入框，实际应复用现有模型组下拉选择能力。

## 定位

通用配置表已经支持 `ref_model_groups` 元数据，并会按 `model_type` 过滤模型组列表。问题字段的业务代码按模型组 key 使用，但配置元数据只包含标题和描述，缺少 `ref_model_groups=True`，因此前端只能按字符串字段渲染。

## 修复

- 为系统级 chat 模型组字段补齐 `ref_model_groups=True` 与 `model_type="chat"`。
- 为系统级 embedding 模型组字段补齐 `ref_model_groups=True` 与 `model_type="embedding"`。
- 未改动前端渲染主干与配置保存逻辑。

## 验证

- `git diff --check`
- `python3 -m py_compile holo_cortex_zero/core/config.py`
- 静态检查确认 8 个系统模型组字段包含 `ref_model_groups` 与对应 `model_type`。
- `pnpm --dir frontend build`
