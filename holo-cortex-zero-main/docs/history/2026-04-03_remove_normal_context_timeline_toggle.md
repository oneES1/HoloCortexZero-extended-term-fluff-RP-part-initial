# 2026-04-03 删除普通 context timeline 开关

## 背景

普通 context 当前已经固定走：

- `48 -> 10` 式窗口回收
- 无 LLM 抽样归档
- `compressed_summary` 按 `【较早历史归档】` 注入

此时 `NORMAL_CONTEXT_TIMELINE_ENABLED` 已不再控制普通 context 主链，只会让人误以为“打开后会启用当前归档逻辑”。

## 本轮处理

删除 `NORMAL_CONTEXT_TIMELINE_ENABLED` 配置项，并同步删除普通 context 对该开关的依赖：

- `core/config.py` 不再暴露该 yaml 配置
- `manager.py` 对普通 context 固定不触发旧 timeline worker
- `manager.py` 对普通 context 固定不应用旧 timeline pending 摘要，并在命中时清理残留 pending 状态
- `assembler.py` 对普通 context 固定按 `【较早历史归档】` 注入归档文本

## 边界

本轮没有改高级 context 的 timeline 主链：

- 高级 context 仍会走原有 timeline 摘要触发、应用和注入
- 删除的只是普通 context 的旧开关，不影响高级 context

## 风险与断点

### 1. 旧 normal pending_summary 的处理

如果数据库里遗留了普通 context 的 `pending_summary / pending_summary_ready / summary_generating`，
现在会在 `try_apply_ready_summary()` 命中普通 context 时被清理掉，不再继续积压。

### 2. 普通 context 不再有“切回旧 timeline”的配置回滚点

删除该开关后，普通 context 的回滚只能通过撤销代码版本完成，
而不能靠 yaml 临时切回旧 timeline。

这符合当前主干：普通 context 已明确固定走归档式回收。

## 修改文件

- `holo_cortex_zero/core/config.py`
- `holo_cortex_zero/services/context_window/manager.py`
- `holo_cortex_zero/services/context_window/assembler.py`
- `docs/2026-04-03_normal_context_recall_gate_and_48_to_10.md`
- `docs/2026-04-03_normal_context_archive_sampling_without_llm.md`
- `docs/2026-04-03_remove_normal_context_timeline_toggle.md`

## 验证

建议至少执行：

- `python3 -m py_compile holo_cortex_zero/core/config.py holo_cortex_zero/services/context_window/manager.py holo_cortex_zero/services/context_window/assembler.py`

## 回滚点

若需回滚本轮：

- 撤销 `holo_cortex_zero/core/config.py`
- 撤销 `holo_cortex_zero/services/context_window/manager.py`
- 撤销 `holo_cortex_zero/services/context_window/assembler.py`
