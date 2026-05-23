# Settings English Translation Alignment

## Problem

The Settings UI had English copy that did not strictly follow the Chinese display fields.

Two sources are used by the Settings page:

- `frontend/src/locales/*/settings.json` supplies fixed Settings / LLM management page text.
- `holo_cortex_zero/core/config.py` supplies dynamic System settings titles and descriptions through `i18n_title` / `i18n_description`.

## Evidence

- `frontend/src/pages/settings/model_group.tsx` uses the `settings` namespace for LLM management labels, helpers, validation messages, notifications, and dialogs.
- `frontend/src/pages/settings/system.tsx` renders `ConfigTable`, and `ConfigTable` resolves each config title with `getLocalizedText(config.i18n_title, config.title, i18n.language)`.
- The English Settings locale and Chinese Settings locale both contain 135 leaf translation keys, so the fixed-page correction can be checked key-for-key.
- Several English strings drifted from the Chinese fields:
  - Chinese consistently used `LLM`, while English used `Model Group` in visible labels.
  - `API地址` helper had a typo-like `OpenAl` and did not match the Chinese base-address wording.
  - `群聊里回复你的LLM` was translated as `Primary Model Group`, losing the "reply to you in group chats" meaning.
  - `/norm`, `/cute`, and `/puss` descriptions were either too generic or expanded beyond the Chinese display field.
  - Memory and self-image titles such as `记忆向量嵌入模型` and `启用系统自设图` used looser English titles.

## Change

- Aligned `frontend/src/locales/en-US/settings.json` with the Chinese Settings locale, preserving the existing key structure and variable placeholders.
- Aligned the most visible mismatched backend config schema English titles/descriptions with the Chinese display fields.
- Kept all runtime config keys, persistence behavior, LLM protocol behavior, and frontend component logic unchanged.

## Impact

- English UI text changes only.
- No settings values are changed.
- No protocol, model routing, or save/restart behavior is changed.

## Verification

- Validate `settings.json` as JSON.
- Compile `holo_cortex_zero/core/config.py`.
- Run frontend production build.
