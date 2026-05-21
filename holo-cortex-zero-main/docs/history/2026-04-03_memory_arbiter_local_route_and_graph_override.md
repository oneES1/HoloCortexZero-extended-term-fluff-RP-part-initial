# 2026-04-03 记忆仲裁切本地组并接入主干路由

## 本次修改

- `MEMORY_MANAGE_MODEL` 切到 `qwen35-hcz-resident-think`
- `holo_cortex_zero/services/memory/mem0_utils.py` 不再直连 `AsyncOpenAI`
- 改为走统一 `llm_router` + 模型组协议判定
- 对 `relation_map / knowledge_index` 补一层主干规则修正：
  - 命中同 alias / keyword 的旧记录时
  - 将模型给出的 `ADD` / `REJECT` 收敛成 `UPDATE`

## 验证目标

- 本地组走最新发射器路由
- 普通偏好/事实仲裁仍能正常 UPDATE
- 图谱覆盖类写入不再停留在 ADD，而是按主规则收敛为 UPDATE
