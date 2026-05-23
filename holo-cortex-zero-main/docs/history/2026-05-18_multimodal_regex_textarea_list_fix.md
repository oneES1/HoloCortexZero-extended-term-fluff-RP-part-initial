# 2026-05-18 多模态切组正则列表点击崩溃修复

## 现象

- 系统设置中的“多模态切组正则列表”使用 `List[str]` 存储，但字段元数据同时声明了 `is_textarea=true`。
- 前端配置表对 `list` 类型统一走嵌套展开渲染，对 `textarea` 的支持只覆盖普通字符串。
- 结果是同一份字段元数据在前端被两套规则解释，点击该项进入编辑时会走错渲染路径。

## 证据

- 字段定义：`holo_cortex_zero/core/config.py`
  - `AI_REPLY_MULTIMODAL_TRIGGER_PATTERNS: List[str]`
  - `json_schema_extra=ExtraField(is_textarea=True).model_dump()`
- 前端旧逻辑：
  - `frontend/src/components/common/ConfigTable.tsx`
  - `frontend/src/components/common/config-table/helpers.tsx`
  - 两处都先判断 `list`，`textarea` 分支永远到不了。

## 修复

- 新增通用规则：`List[str] + is_textarea=true + 非复杂类型` 统一按“逐行文本域”编辑。
- 编辑态显示为一行一个元素，保存时前端再转回 JSON 数组字符串，后端保存主干不变。
- 顶层配置与嵌套字段统一复用同一套判断和转换函数，避免再次分叉。

## 影响面

- 直接修复“多模态切组正则列表”点击即炸问题。
- 同类字段后续若继续使用 `List[str] + is_textarea=true`，会自动按相同规则渲染，无需再写特化。
