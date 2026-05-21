# 2026-04-01 ContextWindowManager 清洗主干恢复

## 问题
- `run_agent_v2` 执行时报错：`type object 'ContextWindowManager' has no attribute '_strip_think_artifacts'`
- 实际根因不是单个方法缺失，而是 `ContextWindowManager` 中一整段“上下文文本清洗主干”定义被删残

## 本次定位
- 直接报错点：`holo_cortex_zero/services/context_window/manager.py` 中 `_sanitize_text()`
- 当前文件里缺失的主干定义包括：
  - `_DIRTY_TOOL_CALL`
  - `_DIRTY_FUNCTION`
  - `_DIRTY_TOOL_CALL_TEXT`
  - `_BOT_TRANSPORT_FILE_PROMPT`
  - `_BOT_HISTORY_MEDIA_PLACEHOLDER`
  - `_THINK_TAG_TOKEN`
  - `_strip_think_artifacts()`
- 进一步静态审查还发现：`self._part_to_dict()` 也被调用但未定义
- 对照历史主干，以上定义均曾存在，属于代码收口过程中遗漏，不是当前业务设计本来没有

## 最小修复
- 只修改 `holo_cortex_zero/services/context_window/manager.py`
- 补回清洗正则常量与 `_strip_think_artifacts()`
- 补回 `_part_to_dict()`，避免上下文注入序列化链路继续在下一处断裂

## 影响面
- `run_agent_v2`
- `message_service`
- `ai_reply/service`
- `tools/chain_executor`
- `context_window/timeline`
- `context_window/assembler`

## 审查结果
- 对 `ContextWindowManager` 做类内静态审查后：
  - `self._xxx()` 无剩余悬空调用
  - `ContextWindowManager._XXX` 无剩余缺失引用
- 说明本轮在 `manager.py` 内已补齐当前可见的断点

## 验证
- 静态语法解析通过
- 对 `manager.py` 的类内悬空引用审查通过
- 最小重启 `holo_cortex_zero` 后，通过本地 debug 注入一条群消息触发 `run_agent_v2`
- 本轮注入后未再出现 `_strip_think_artifacts` / `AttributeError` 报错
