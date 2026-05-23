# Systems 页面清理

## 本次调整
- 删除 `system` 配置中 4 个未消费字段：`ADMIN_CHAT_KEY`、`SAVE_PROMPTS_LOG`、`AI_RESPONSE_PRE_DROP_REGEX`、`AI_REQUEST_STREAM_MODE`。
- 统一导航文案：父级改为 `Settings/设置`，子级 `system` 改为 `System/系统`，避免父子同名都显示为 `Systems`。
- `Manage` 二级页签中的 `Systems` 改为 `System`，与设置页子项保持一致。

## 影响文件
- `holo_cortex_zero/core/config.py`
- `frontend/src/pages/manage/index.tsx`
- `frontend/src/locales/en-US/navigation.json`
- `frontend/src/locales/zh-CN/navigation.json`
- `frontend/src/locales/en-US/settings.json`
- `frontend/src/locales/zh-CN/settings.json`
- `docs/2026-04-03_systems_cleanup.md`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`

## 风险与回滚点
- 风险：若本地 `system` YAML 仍保留已删除字段，加载时会忽略未知字段；再次保存配置后这些旧键会自然消失。
- 回滚点：本次提交完成后可直接按提交哈希回退。
