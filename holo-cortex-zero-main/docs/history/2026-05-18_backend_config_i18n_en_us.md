# 2026-05-18 Backend Config i18n en_US 补全

## 问题
用户反馈系统配置、适配器配置、Prompt 配置在切换英文时仍显示中文，且部分字段只有占位符/无切换逻辑。

## 根因
后端 pydantic Field 的 `json_schema_extra` 中未提供 `i18n_title`/`i18n_description`，或仅提供 `zh_CN` 缺少 `en_US`。
前端 `getLocalizedText`  fallback 到 `config.title`（中文）。

## 修复范围
1. **CoreConfig (`holo_cortex_zero/core/config.py`)**
   - 62 个可见字段已在先前提交 `3aa7c6e` 中通过脚本批量补充 `i18n_title`/`i18n_description`。
   - 本次补充 10 个隐藏 Prompt 字段的 i18n：
     - BOT_PERSONA_DISPLAY_NAME
     - MAIN_SYSTEM_PROMPT_NORMAL / ADVANCED / ADVANCED_DEEK / ADVANCED_DEEP
     - AI_REPLY_JUDGE_SYSTEM_PROMPT
     - SUBCONSCIOUS_SYSTEM_PROMPT
     - TIMELINE_SYSTEM_PROMPT
     - MEMORY_ARBITER_SYSTEM_PROMPT
     - AUTO_MEMORY_SYSTEM_PROMPT

2. **Adapter Configs**
   - `adapters/matrix/config.py`：修复 `SYNC_TIMEOUT_MS`、`REQUEST_TIMEOUT_SECONDS` 两个单行 Field 未附加 i18n 且 `json_schema_extra` 被错误放置为独立类变量的问题；补全 English title/description。
   - `adapters/onebot_v11/adapter.py`：补全 `NAPCAT_CONTAINER_NAME` 的 i18n。
   - `adapters/telegram/config.py`：已在 `3aa7c6e` 中完成。

3. **Tool Configs**
   - 外部 `tool_runtime` 提供的 Tool 独立配置字段暂无法在本仓库内补充 i18n，需后续在工具包内完善。

## 验证
- `python3 -m py_compile` 通过所有修改文件。
- 容器内直接调用 `UnifiedConfigService.get_config_list('system', include_hidden=True)`，确认关键字段 `i18n_title` 同时包含 `zh-CN` 与 `en-US`。
- 后端容器已 `--force-recreate` 重启。

## 提交
- commit: `cb161f5`
- 文件：`holo_cortex_zero/core/config.py`, `adapters/matrix/config.py`, `adapters/onebot_v11/adapter.py`
