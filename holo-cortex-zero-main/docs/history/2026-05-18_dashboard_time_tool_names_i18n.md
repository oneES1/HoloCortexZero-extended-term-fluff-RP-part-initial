# 2026-05-18 Dashboard time 占位与 Tool 命名 i18n 修复

## 问题
1. Dashboard 页面相对时间仍显示 `time.hoursAgo` 等占位键值。
2. Tool 管理页面所有 Tool `display_name` 为硬编码中文，切换英文无效。

## 根因
1. `frontend/src/pages/dashboard/index.tsx:140` 使用 `useTranslation('dashboard')`，但 `time.*` 键仅存于 `common.json`，`dashboard.json` 缺少同名键。
2. 后端 `RegisteredTool.display_name` 为硬编码中文，API 未返回 i18n 字段；前端 `management.tsx:50` 直接渲染 `tool.display_name`。

## 修复
1. **Dashboard time 占位**
   - `frontend/src/locales/en-US/dashboard.json` 补充 `time: { justNow, minutesAgo, hoursAgo, daysAgo }`
   - `frontend/src/locales/zh-CN/dashboard.json` 同步补充。

2. **Tool 命名 i18n**
   - `frontend/src/locales/en-US/common.json` / `zh-CN/common.json` 新增 `toolNames` 映射，覆盖 14 个 Tool：
     - `weather` / `seek` / `isolate` / `gif_generation` / `photoshop` / `lightroom`
     - `list_files` / `send_file` / `read_file` / `search_code` / `run_command` / `write_file` / `apply_patch`
     - `echo`
   - `frontend/src/pages/tools/management.tsx`：
     - 扩展 `t` prop 类型，支持 `options.defaultValue`
     - 渲染逻辑改为 `t(\`toolNames.${tool.tool_id}\`, { defaultValue: tool.display_name })`

## 验证
- `pnpm --dir frontend build` 通过。
- `docker compose ... --force-recreate holo_cortex_zero` 完成。

## 提交
- 文件：
  - `frontend/src/locales/en-US/dashboard.json`
  - `frontend/src/locales/zh-CN/dashboard.json`
  - `frontend/src/locales/en-US/common.json`
  - `frontend/src/locales/zh-CN/common.json`
  - `frontend/src/pages/tools/management.tsx`
