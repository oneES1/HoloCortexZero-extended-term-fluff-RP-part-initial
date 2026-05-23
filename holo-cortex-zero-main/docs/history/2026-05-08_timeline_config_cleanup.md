# 2026-05-08 timeline config cleanup

## 变更
- 删除 `init_new_arch.py` 中对 `context_window_manager.max_history_before_compress` / `keep_recent_after_compress` 的硬编码赋值。
- 让 timeline / context 压缩阈值完全由系统配置读取，避免初始化阶段与配置主干冲突。

## 原因
- 这些值已经改成配置项并在 `ContextWindowManager` 中动态读取。
- 旧初始化硬编码会和新主干相互覆盖，导致配置不生效或初始化抛异常。

## 验证
- 待重启后在运行态确认初始化不再报属性赋值冲突。

x## 压缩实测
- 2026-05-08 在独立测试窗口 `codex_timeline_user` 注入 101 条 `DBContextMessage`，触发阈值 `100`。
- timeline 后台在约 `18.0s` 内生成摘要，`pending_summary_ready=True`，摘要长度 `566`。
- 应用摘要后历史条数从 `101` 清理到 `10`，`compressed_summary` 版本号为 `v1`。
- 生成结果明确保留了主线、关键约束 `keep_recent=10`、以及“只输出全新摘要”的规则，压缩行为与当前配置一致。

## 风险
- 若外部有人仍依赖旧的初始化覆盖逻辑，现在会统一切换到配置值。
