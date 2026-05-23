# 海菜子 · Holo Cortex Zero

海菜子（Holo Cortex Zero，HCZ）是一个由“自我反思”驱动的多模型元认知智能体平台。

“海”是发散与涌现的场域，多个 LLM 智能体如海菜般在知识深海中摇曳交织；
“菜”是元认知觉醒的标志，知道自己哪里菜，才是克服幻觉、走向真正智能的钥匙；
“子”是创造力爆发的奇点，一切复杂规划与思想涌现，皆源于这颗名为 Zero 的元认知种子。

> From the depth of the Holo Cortex, emergence starts at Zero.
>
> 于全息智脑深处，涌现始于原点。

## 文档结构

当前仓库只保留三类活文档：

- 核心指南：`docs/guides/tool-development.md`、`docs/guides/tool-integration.md`
- 协议与运行时参考：`docs/guides/emitter-development.md`、`docs/guides/tool-runtime-contract.md`
- 迁移摘要：`docs/history/refactor-summary.md`

适配器的局部说明保留在各自目录：

- `holo_cortex_zero/adapters/onebot_v11/README.md`
- `holo_cortex_zero/adapters/telegram/README.md`
- `holo_cortex_zero/adapters/matrix/README.md`

## 上下文记忆回填主干

当前 context window 的记忆回填，已经固定为一条主干：

- 主模型 payload 不再依赖“每轮尾端重算的动态记忆块”
- recall 真重算后，只把本 context 尚未注入过的新记忆写入 `memory_inject` 历史
- `memory_inject` 的去重唯一键固定为记忆库原生 `id`

`memory_inject` 的显示格式固定为：

- `ID 的记忆（日期时间 记忆文本 置信（CONFIDENCE））`
- 同一 `user_id` 的多条记忆使用 `，` 串接
- 多个 `user_id` 按本轮首次出现顺序换行

展示字段白名单固定为：

- `user_id`
- `updated_at`，若为空则退回 `created_at`
- `memory`
- `metadata.CONFIDENCE`，若为空则退回 `metadata.confidence`

不会从 recall 文本或展示文本反推结构化记忆，也不会使用文本 hash、`parts_json` 反解析或 metadata 扩散字段做去重。

## 普通与高级 Context 差异

- 高级 context：每轮都真实重算 recall，因此每轮都可能产生新的 `memory_inject`
- 普通 context：recall 按 `NORMAL_CONTEXT_MEMORY_RECALL_REFRESH_EVERY` 节奏真重算；只有真重算轮才允许写入 `memory_inject`
- 普通 context 的缓存轮只复用 `recall_text`，不会补一层独立的记忆去重缓存

## 阈值清理与账本

`memory_recall_seen_items_json` 的语义固定为：

- 当前 context 中，仍然存活的 `memory_inject` 所携带的原生 memory id 集合

发生普通归档、高级硬上限清理、摘要应用清理时，都会按同一顺序处理：

1. 删除 cutoff 之前的普通历史
2. 删除依附于该聊天水位之前的 `memory_inject`
3. 将旧账本逻辑清空
4. 仅依据数据库中仍然存活的 `memory_inject.memory_digests_json` 重建账本

因此，被 cutoff 删除的旧记忆不会永久挡住后续重新回填。

## auto_memory 关系

本次记忆回填主干替换不改变 auto_memory 的 recall 来源：

- auto_memory 继续只读取主链 `recall_text`
- `memory_inject` 的结构化去重链不参与 auto_memory 的 recall 缓存与 payload 构造

相关改造与验证记录见：

- `docs/history/2026-05-22_memory_inject_native_id_rebuild.md`
