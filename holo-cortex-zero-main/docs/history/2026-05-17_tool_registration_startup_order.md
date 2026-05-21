# 2026-05-17 Tool registration startup order

## 结论
- Tool 管理偶发空列表不是 Tool 文件丢失，也不是注册函数本身需要依赖 Qdrant。
- 根因是 `init_new_architecture()` 把 Tool 注册放在 memory/Qdrant/context 恢复/system runtime 初始化之后。
- 当前修复把 Tool 注册提前到启动 Phase 1，保证本地 Tool 描述与 YAML 配置先进入 `tool_registry`。

## 修改
- `holo_cortex_zero/services/moment/service.py`
  - 新增 `SystemMomentService.register_tools_once()`，只注册 `echo`，不启动 moment patrol。
  - `initialize_runtime()` 改为复用该入口，保持幂等。
- `holo_cortex_zero/services/init_new_arch.py`
  - 启动开头先注册 `echo`、高级维护 Tool、迁移 Tool。
  - memory/Qdrant、context 恢复、emoji/voice/moment runtime、timeline 均移动到 Tool 注册之后。

## 影响
- `/api/tools` 不再因 memory/Qdrant 启动抢跑而进入空 registry。
- 如果 memory 或 timeline 后续失败，Tool 管理仍能看到已注册 Tool，便于继续诊断真实失败点。
- Tool 注册本身仍然使用同一条主干 `tool_registry.register(...)`，没有为前端或某个供应来源新增并行注册逻辑。

## 验证
- `uv run python -m py_compile holo_cortex_zero/services/init_new_arch.py holo_cortex_zero/services/moment/service.py`
- `docker compose -f docker-compose.yml up -d --no-deps --force-recreate holo_cortex_zero`
- 启动日志确认顺序：
  - `05-17 23:01:04 Tool 注册阶段完成: total=14`
  - `05-17 23:01:08 记忆管理器已重新初始化`
  - `05-17 23:01:08 新架构初始化完成: 14 total, 3 visible to LLM, skipped=[]`
- 容器状态确认：`holo_cortex_zero Up ... (healthy)`

## 回滚点
- 回滚本次提交即可恢复旧启动顺序。
