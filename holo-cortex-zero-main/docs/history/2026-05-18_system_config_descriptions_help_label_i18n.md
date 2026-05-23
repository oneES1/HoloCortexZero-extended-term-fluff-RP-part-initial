# 2026-05-18 System Config description 与 help_label i18n 补全

## 问题
1. "获取 Key 指南" / "获取 Token 指南" 等 help_label 切换英文后仍显示中文。
2. `core/config.py` 中大量字段的 `description` 为中文且无 `i18n_description`。

## 根因
1. `ExtraField` 未定义 `i18n_help_label` / `i18n_help_text`；前端 `ConfigTable` 直接渲染 `help_label`/`help_text`。
2. 先前批量脚本仅补充了部分可见字段的 `i18n_title`/`i18n_description`，仍有 48 个字段（含 `is_hidden=True` 及模型组配置）遗漏。

## 修复

### help_label / help_text
- `holo_cortex_zero/core/core_utils.py`：`ExtraField` 新增 `i18n_help_label` / `i18n_help_text`。
- `frontend/src/components/common/config-table/types.ts`：`ConfigItem` 新增对应字段。
- `frontend/src/components/common/ConfigTable.tsx`：help 按钮条件改为 `(help_text || i18n_help_text)`；文案与弹窗内容均走 `getLocalizedText`。
- `tool_runtime/tools/seek.py` / `weather.py`：`help_label` 补充 `i18n_help_label`，并新增英文版 `_TAVILY_KEY_HELP_EN` / `_QWEATHER_KEY_HELP_EN`，`API_KEY` 字段补充 `i18n_help_text`。
- `holo_cortex_zero/adapters/telegram/config.py`：新增 `_TELEGRAM_BOT_TOKEN_HELP_EN`，`BOT_TOKEN` 补充 `i18n_help_text` / `i18n_help_label`。

### system config descriptions
- `holo_cortex_zero/core/config.py`：通过脚本为全部 48 个遗漏字段补充 `i18n_description`，覆盖：
  - `ModelConfigGroup`：MODEL_TYPE、MAX_OUTPUT_TOKENS、IMAGE_MAX_COUNT、REASONING_MODE、TEXT_VERBOSITY、REPLAY_REASONING_CONTENT、WIRE_API、CACHE_TRANSPORT_PROFILE、REASONING_EFFORT
  - `CoreConfig`：ADVANCED_CONTEXT_MODE_NORM/DEEEK/PUSS/NORMAL_USER/SYSTEM_THE_DEEP_MODEL_GROUP、ADVANCED_CONTEXT_PRIVATE/GROUP_DEFAULT_MODE、AI_REPLY_JUDGE_FAIL_OPEN、LLM_RESPONSES_STREAM_IDLE_TIMEOUT、MULTIMODAL_TRIGGER_REGEX、MEM_SEARCH_THRESHOLD、SUBCONSCIOUS_MAX_TOKENS、PROMPT_INJECT 系列 Stage2 阈值、AUTO_MEMORY 系列、MOMENT_PERSIST_ECHO 等

## 验证
- `python3 -m py_compile holo_cortex_zero/core/config.py` 通过。
- `pnpm --dir frontend build` 通过。
- `docker compose ... --force-recreate holo_cortex_zero` 完成。

## 提交
- 文件：
  - `holo_cortex_zero/core/core_utils.py`
  - `holo_cortex_zero/core/config.py`
  - `tool_runtime/tools/seek.py`
  - `tool_runtime/tools/weather.py`
  - `holo_cortex_zero/adapters/telegram/config.py`
  - `frontend/src/components/common/config-table/types.ts`
  - `frontend/src/components/common/ConfigTable.tsx`
