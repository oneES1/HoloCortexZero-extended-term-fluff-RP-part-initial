# 2026-05-08 advanced context compress configurable

## 变更
- 将高级 context 的历史压缩阈值从代码硬编码 `100` 提升为系统配置项 `ADVANCED_CONTEXT_MAX_HISTORY_BEFORE_COMPRESS`。
- 将高级 context 压缩后保留条数从代码硬编码 `10` 提升为系统配置项 `ADVANCED_CONTEXT_KEEP_RECENT_AFTER_COMPRESS`。
- 将高级 context 的硬上限倍率从代码硬编码 `1.2` 提升为系统配置项 `ADVANCED_CONTEXT_HARD_LIMIT_RATIO`。

## 目的
- 让高级 context 的“压缩阈值 / 保留条数 / 硬上限倍率”在前端系统设置中可见、可改。
- 不再把 `100 / 120` 这类行为参数锁死在 `context_window.manager` 的实例初始化里。

## 验证
- 已通过 `python3 -m compileall`。
- 已通过配置 schema 读取验证：新增字段在 `system` 配置列表中可见，且带 `overridable=True`。

## 风险
- 配置值改变后，行为会随配置对象实时读取更新；若前端正在打开旧页面，需刷新后再查看新值。
- 硬上限倍率若设得过低，可能提前触发历史裁剪；若设得过高，会增加单上下文积压压力。
