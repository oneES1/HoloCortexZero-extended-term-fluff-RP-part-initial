# 2026-04-10 普通 context 历史角色边界修复

## 问题现象

- 普通 context 下，普通用户历史消息在同步进 `DBContextMessage` 前，会被统一降成 `assistant`。
- 这会让普通私聊 / 普通群聊里的真实人类输入，在上下文历史里失去 `user` 主角色，模型对普通 context 的指令关注度被错误削弱。
- 该问题容易被误判为 `context_id` 或权限主干问题，但真正根因不在 `context_id` 路由，也不在 `permission_level`。

## 根因

- 根因集中在 `holo_cortex_zero/services/context_window/manager.py` 的 `_determine_role_for_db_msg`。
- 旧逻辑采用“全局规则”：
  - 系统消息 → `user`
  - 高级用户 → `user`
  - 其他所有人类 → `assistant`
- 这条规则没有区分“当前消息正在注入哪个 context”，导致普通 context 也沿用了高级 context 的降级策略。

## 本次修复

- 仅修改 `holo_cortex_zero/services/context_window/manager.py`。
- `_determine_role_for_db_msg` 改为按当前 `context_id` 所属窗口类型判定：
  - 系统消息 → `user`
  - 普通 context → 人类消息统一 `user`
  - 高级 context → 仅高级用户 `user`，其他人类 `assistant`
- 新增调试日志：
  - `普通 context 历史消息按 user 注入`
  - `高级 context 非高级用户降级为 assistant`

## 多模态边界（本次明确不动）

- 本次**不修改** `sync_new_chat_messages` 里的多模态 assistant→user 兜底分流主干。
- 现有行为保持：
  - 若消息先被判为 `assistant` 且包含图片段，则整条消息按 `user` 注入。
  - 若消息先被判为 `assistant` 且包含音频 / 视频 / 文件，则文本仍为 `assistant`，媒体段拆成 `user`。
- 因此：
  - 普通 context 修复后，普通用户消息直接按 `user` 进入，不再走“assistant 后置拆分”分支。
  - 高级 context 的多模态兜底链路保持原样，不会误伤高级上下文对图片/媒体的感知。

## 影响范围

- 只影响后续从 `DBChatMessage` 同步进上下文历史时的人类消息角色。
- 不修改：
  - `context_id` 路由
  - `owner_type`
  - `permission_level`
  - tool 暴露 / tool 权限
  - prompt 选择
  - 节日提醒按 `context_id` 收口逻辑

## 验证

### 静态校验

```bash
cd /path/to/source-root && python3 -m py_compile holo_cortex_zero/services/context_window/manager.py
```

### 运行态同步

```bash
cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero
```

### 人工验收

- 普通私聊发送文本后，新的普通 context 历史消息应以 `user` 身份进入模型上下文。
- 普通群聊普通用户消息进入各自普通 context 时，应保持 `user`。
- 高级 context 中，非高级用户文本仍应降为 `assistant`。
- 高级 context 中，非高级用户图片 / 音频 / 视频 / 文件的多模态兜底行为应保持原样。

## 风险

- 本次是逻辑修复，不会自动重写数据库里已经落库的旧 `DBContextMessage.role`；旧普通 context 历史会随着自然回收逐步淡出。
- 若后续引入新的高级用户 ID，需要继续保证“高级 context 的 `context_id` 等于高级用户 ID”这一主干约定，否则该角色判定会失真。

## 回滚点

- 代码回滚点：`holo_cortex_zero/services/context_window/manager.py`
- 文档回滚点：`docs/2026-04-10_normal_context_role_boundary_fix.md`
