# 2026-05-06 Qdrant 启动抢跑导致 Tool 丢失修复

## 结论
- 这次不是 Qdrant 配置错误，也不是 Tool 文件丢失。
- 根因是 `holo_cortex_zero` 启动时过早初始化 memory，访问 `hcz_qdrant:6333` 时 Qdrant 还未 ready，触发 `Connection refused`。
- 由于 memory 初始化与 Tool 注册处于同一条新架构启动主干中，首次失败直接中断了后续 Tool 注册，导致 `/api/tools` 返回空数组。

## 本次实证
- `hcz_qdrant` 容器启动时间：`2026-05-02T05:23:25.612Z`
- `holo_cortex_zero` 容器启动时间：`2026-05-02T05:23:26.668Z`
- HCZ 开始新架构初始化：`2026-05-02 13:23:34`
- HCZ 访问 Qdrant 失败：`2026-05-02 13:23:37`
- Qdrant 真正开始监听 HTTP `6333`：`2026-05-02 13:23:39`
- 时间差约 `1.84s`，说明这是明确的启动时序抢跑，不是随机幻觉。

## 本次修改
- 在 `holo_cortex_zero/services/init_new_arch.py` 中，把 memory 运行时初始化收口到单独辅助函数。
- 保持主干不分叉：首次初始化失败时记录 warning，等待 `5s` 后只重试一次。
- 不改 Tool 注册逻辑、不改 Qdrant 配置、不改模型组与上下文拼装。

## 风险
- 风险较低。
- 仅在启动期首次 memory 初始化失败时多等待 `5s` 再重试一次。
- 若 5 秒后依旧失败，仍按原有异常链路报错，不会无限重试，不会掩盖持续性故障。

## 回滚点
- 如需回滚，撤销以下文件中的本次修改：
  - `holo_cortex_zero/services/init_new_arch.py`
  - `docs/2026-05-06_qdrant_startup_race_memory_retry.md`
