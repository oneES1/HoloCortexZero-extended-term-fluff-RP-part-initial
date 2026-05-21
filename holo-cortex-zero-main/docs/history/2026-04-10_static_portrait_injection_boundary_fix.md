# 2026-04-10 Static 画像注入边界修复

## 问题现象

- 普通 context 下，`【潜意识回忆】` 中的 `Static 画像` 子块会在部分轮次消失。
- 高级 context 下，`Static 画像` 与后续检索块通常能同时出现，看起来符合预期。
- 真实问题不是整段 recall 丢失，而是 Stage2 的 `Static 画像` 注入边界与目标主干不一致。

## 目标对齐

### 高级 context

- 必须注入，且只注入 `<ADVANCED_USER_ID>` 的 `Static 画像`。
- `Static 画像` 固定作为前置底座，不再受当前 query 命中与否影响。
- 搜索块继续保留，并放在 `Static 画像` 后面。

### 普通 context

- 若当前轮没有针对当前主用户的人类用户分区检索结果，则补充该主用户的 `Static 画像`。
- 若当前轮已经有当前主用户 ID 的 query 结果命中，则不再额外注入 `Static 画像`，避免重复。
- `HCZ_SELF` 与第三方 target 的检索结果不算“当前主用户的人类用户分区命中”。

## 根因

- 旧实现把 `Static 画像` 默认放进 Stage2 并发任务里统一处理，导致其边界更像“实现上的一条检索路”，而不是“按上下文类型与用户分区命中状态控制的注入块”。
- 对普通 context 来说，旧逻辑没有按“当前主用户 query 是否命中”做显式裁决，因此会出现该补不补、该抑制不抑制的边界漂移。

## 本次修复

- 在 `run_agent_v2` 调用 recall 前，补充上下文窗口元信息到 `ctx`，供 memory runtime 读取当前 `owner_type`。
- `memory/runtime.py` 中：
  - 高级 context：固定对 `<ADVANCED_USER_ID>` 走 `get_all + STATIC_TAGS`，只生成这一份 static。
  - 普通 context：先整理 Stage2 intent 结果；若没有当前主用户的 query 命中，则再补当前主用户的 static；若已有命中，则抑制 static。
- 新增 Stage2 边界日志：
  - `static fallback for normal context`
  - `static suppressed for normal context`
  - `static: used_search=... source=... user_id=... hits=...`

## 影响文件

- `holo_cortex_zero/services/agent/run_agent_v2.py`
- `holo_cortex_zero/services/memory/runtime.py`
- `docs/2026-04-10_static_portrait_injection_boundary_fix.md`

## 验证

### 静态校验

```bash
cd /path/to/source-root && python3 -m py_compile holo_cortex_zero/services/agent/run_agent_v2.py holo_cortex_zero/services/memory/runtime.py
```

### 运行态同步

```bash
cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero
```

### 人工验收

- 高级 context：应固定先出现 `<ADVANCED_USER_ID>` 的 `Static 画像`，后续再追加 query / intent 检索块。
- 普通 context：
  - 若没有当前主用户 ID 命中块，应补 `Static 画像`
  - 若已有当前主用户 ID 命中块，应不再补 `Static 画像`
  - 仅有 `HCZ_SELF` 命中块时，仍应补当前主用户 static

## 风险

- 当前普通 context 的“用户分区命中”判定以 Stage2 已产出的当前主用户 intent 命中为准；未展示到 prompt 的内部检索结果不参与 static 抑制，避免出现“用户看不到 query 结果，却也看不到 static”的空窗。
- 高级 context 现在固定读取 `<ADVANCED_USER_ID>` 的 static 分区，若未来高级用户名单扩展，需要同步明确主用户 static 规则，而不是继续隐式沿用本分支。

## 回滚点

- `holo_cortex_zero/services/agent/run_agent_v2.py`
- `holo_cortex_zero/services/memory/runtime.py`
- `docs/2026-04-10_static_portrait_injection_boundary_fix.md`
