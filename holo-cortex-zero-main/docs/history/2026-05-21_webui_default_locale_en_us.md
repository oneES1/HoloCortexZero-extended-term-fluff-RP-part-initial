# 2026-05-21 WebUI 默认语言切到 English

## 背景

- 当前 WebUI 初始化语言 `lng`、回退语言 `fallbackLng`、本地持久化默认值 `currentLocale` 都写死为 `zh-CN`。
- 结果是首次打开 WebUI 的新浏览器会直接进入中文界面，不符合“框架默认英文”要求。

## 本次最小修改

- `frontend/src/config/i18n.ts`
  - 将 `fallbackLng` 从 `zh-CN` 改为 `en-US`
  - 将 `lng` 从 `zh-CN` 改为 `en-US`
  - 将默认命名空间来源从 `resources['zh-CN']` 改为 `resources['en-US']`
- `frontend/src/stores/locale.ts`
  - 将持久化状态默认值 `currentLocale` 从 `zh-CN` 改为 `en-US`

## 影响范围

- 只影响“首次进入且本地还没有 `holo-cortex-zero-locale` 持久化值”的浏览器会话。
- 已经手动切换过语言、且浏览器本地已有持久化值的用户，不会被强制改回英文。
- 不改语言切换按钮，不改翻译资源内容，不改后端 `Accept-Language` 透传机制。

## 风险

- 风险低：仅切换前端默认语言，不改路由、接口、状态结构。
- 若某个命名空间只存在于 `zh-CN` 而不存在于 `en-US`，默认命名空间推断可能受影响；当前前端 i18n 目录是中英双目录并行，预期风险可控。

## 回滚点

- 回滚 `frontend/src/config/i18n.ts` 与 `frontend/src/stores/locale.ts` 本次 `en-US` 默认值修改即可。
