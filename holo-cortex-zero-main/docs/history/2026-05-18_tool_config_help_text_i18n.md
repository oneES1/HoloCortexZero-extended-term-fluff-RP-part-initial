# 2026-05-18 Tool 配置字段、Help Text、Tool 说明 i18n 补全

## 问题
用户反馈 Tool 配置字段（如"项目根目录"、"默认命令超时"、"GIF 绘图模型组"等）、Seek/Weather/TG 的 help_text 说明、以及 Tool 管理页面的 description 均为中文，切换英文无效。

## 根因
1. `tool_runtime` 各 Tool 配置模型的 `Field(title="...")` 未附加 `json_schema_extra` 的 `i18n_title`。
2. `ExtraField` 模型未定义 `i18n_help_text`/`i18n_help_label`，导致 seek/weather/TG 的长篇 help_text 无法国际化。
3. 前端 `ConfigTable` 直接渲染 `help_text`/`help_label`，未走 `getLocalizedText`。
4. 前端 `management.tsx` 直接渲染 `tool.description`，未做翻译映射。

## 修复

### 后端
1. **`holo_cortex_zero/core/core_utils.py`**
   - `ExtraField` 新增 `i18n_help_text` / `i18n_help_label` 字段。

2. **`tool_runtime/tools/file_ops.py`**
   - `AdvancedToolConfig` 4 个字段补充 `i18n_title`：PROJECT_ROOT、DEFAULT_TIMEOUT、ALLOWED_COMMAND_PREFIXES、BLOCKED_PATTERNS。

3. **`tool_runtime/tools/seek.py`**
   - `SeekConfig` 全部 13 个字段补充 `i18n_title`。
   - 新增 `_TAVILY_KEY_HELP_EN`，`TAVILY_API_KEY` 的 `json_schema_extra` 补充 `i18n_help_text`。

4. **`tool_runtime/tools/weather.py`**
   - `WeatherConfig` 全部 6 个字段补充 `i18n_title`。
   - 新增 `_QWEATHER_KEY_HELP_EN`，`API_KEY` 的 `json_schema_extra` 补充 `i18n_help_text`。

5. **`tool_runtime/tools/block.py`**
   - `BlockToolConfig` 2 个字段补充 `i18n_title`：MAX_BLOCK_SECONDS、DEFAULT_BLOCK_SECONDS。

6. **`tool_runtime/tools/magic_draw.py`**
   - `MagicDrawConfig` 3 个字段补充 `i18n_title`：STREAM_MODE、TIMEOUT、DEBUG。
   - `_draw_model_group_field` 返回的 Field 补充 `i18n_title`（GIF/Photoshop/Lightroom 模型组）。
   - `GifGenerationConfig` 补充 GIF_EDGE_FILTER_PIXELS 的 `i18n_title`。
   - `PhotoshopConfig` 补充 4 个字段的 `i18n_title`。
   - `LightroomConfig` 补充 3 个字段的 `i18n_title`。

7. **`holo_cortex_zero/adapters/telegram/config.py`**
   - 新增 `_TELEGRAM_BOT_TOKEN_HELP_EN`。
   - `BOT_TOKEN` 的 `ExtraField` 补充 `i18n_help_text`。

### 前端
8. **`frontend/src/components/common/config-table/types.ts`**
   - `ConfigItem` 新增 `i18n_help_text?` / `i18n_help_label?`。

9. **`frontend/src/components/common/ConfigTable.tsx`**
   - help 按钮显示条件改为 `(config.help_text || config.i18n_help_text)`。
   - `setHelpDialog` 的 `text` 使用 `getLocalizedText(config.i18n_help_text, config.help_text, i18n.language)`。
   - 按钮文案使用 `getLocalizedText(config.i18n_help_label, config.help_label, i18n.language)`。

10. **`frontend/src/locales/en-US/common.json` / `zh-CN/common.json`**
    - 新增 `toolDescriptions` 映射，覆盖 14 个 Tool。

11. **`frontend/src/pages/tools/management.tsx`**
    - description 渲染改为 `t(\`toolDescriptions.${tool.tool_id}\`, { defaultValue: tool.description })`。

## 验证
- `python3 -m py_compile` 通过所有修改的后端文件。
- `pnpm --dir frontend build` 通过。
- `docker compose ... --force-recreate holo_cortex_zero` 完成。

## 提交
- 文件：
  - `holo_cortex_zero/core/core_utils.py`
  - `tool_runtime/tools/file_ops.py`
  - `tool_runtime/tools/seek.py`
  - `tool_runtime/tools/weather.py`
  - `tool_runtime/tools/block.py`
  - `tool_runtime/tools/magic_draw.py`
  - `holo_cortex_zero/adapters/telegram/config.py`
  - `frontend/src/components/common/config-table/types.ts`
  - `frontend/src/components/common/ConfigTable.tsx`
  - `frontend/src/locales/en-US/common.json`
  - `frontend/src/locales/zh-CN/common.json`
  - `frontend/src/pages/tools/management.tsx`
