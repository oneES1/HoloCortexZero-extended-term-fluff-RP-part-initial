# Models 页面模型组显示与表头清理修复

## 问题定位
- `Models` 页面直接假设 `/config/model-groups` 返回值一定是 `Record<string, ModelGroupConfig>`，前端没有做返回结构归一化；一旦接口返回出现嵌套字段或数组形态，表格就会落成空白，看起来像“模型组没显示”。
- 页面顶部新增按钮仍使用高亮蓝色主按钮，不符合当前需要的低调工具位风格。
- 表头单元格复用了统一表格头样式，带有较强的高亮背景与强调感，视觉上容易被看成一条蓝色条带。

## 本次调整
- 在 `frontend/src/services/api/unified-config.ts` 为模型组接口补上通用归一化，兼容对象、嵌套对象与数组返回，统一转换为 `Record<string, ModelGroupConfig>`。
- 在 `frontend/src/pages/settings/model_group.tsx` 增加模型组加载态与空态，避免接口尚未返回时页面表现成“无内容”。
- 删除 `Models` 页顶部表头整行，不再显示 `组名 / 模型名称 / 模型类型 / API地址 / 代理策略 / 操作` 这一排文字。
- 修正列表列映射：第一列恢复显示真实组名，第二列显示模型名称，后续列保持类型 / API 地址 / 代理策略 / 操作。
- 将“新增模型组”按钮改成低调灰色工具按钮，不再使用显眼蓝色主按钮。
- 收紧列表行高、类型 Chip 高度与操作按钮内边距，减少整表行距。

## 影响文件
- `frontend/src/services/api/unified-config.ts`
- `frontend/src/pages/settings/model_group.tsx`
- `frontend/src/locales/zh-CN/settings.json`
- `docs/2026-04-04_model_groups_display_and_header_cleanup.md`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 风险与回滚点
- 风险：本次只调整模型组接口解析与 `Models` 页面表头/按钮风格，不改模型组保存、删除、编辑逻辑；若后端未来返回全新结构，仍需补充归一化分支。
- 回滚点：本次提交完成后可直接按提交哈希回退。
