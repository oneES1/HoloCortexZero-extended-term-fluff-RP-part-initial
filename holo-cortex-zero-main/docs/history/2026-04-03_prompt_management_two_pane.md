# Prompt 管理页双栏改版

## 本次调整
- 删除页面顶部解释说明，不再显示提示管理说明性文案。
- 将 `BOT_PERSONA_DISPLAY_NAME` 从表格项改为顶部单行输入框，并与 `保存更改 / 重置配置` 放在同一排。
- Prompt 页面移除重启入口，仅保留保存与本地重置。
- 取消原先 `主人格 / 辅助 LLM` 两个分区标题，统一改为左侧 prompt 列表、右侧 prompt 编辑器。
- 左侧改成类似聊天列表的可滚动选项区，右侧改成整块可滚动 textarea 编辑器。
- 去掉 prompt 描述性文字，只保留名称与正文编辑。
- 默认选中 `高级用户上下文系统提示词`（`MAIN_SYSTEM_PROMPT_ADVANCED`）。

## 影响文件
- `frontend/src/pages/prompt-management/index.tsx`
- `frontend/src/locales/zh-CN/prompt-management.json`
- `frontend/src/locales/en-US/prompt-management.json`
- `docs/2026-04-03_prompt_management_two_pane.md`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`

## 风险与回滚点
- 风险：本次仅改 Prompt 页前端布局与交互，不改 system 配置协议；重置按钮仅回退到当前已加载配置，不触发后端 reload。
- 回滚点：本次提交完成后可直接按提交哈希回退。
