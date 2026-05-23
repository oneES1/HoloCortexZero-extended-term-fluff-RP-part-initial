# 2026-04-03 subconscious 切换到 doubao chat 非思维组

## 背景

- 本地 `qwen35-hcz-resident` 跑 `subconscious` 的 `chat json-only` 链路实测约 `4.6s`。
- 同样的 `subconscious` 输入样本下，豆包两组中：
  - `doubao-nonthinking2` (`chat`) 平均约 `2.1s`
  - `doubao-nonthinking` (`responses`) 平均约 `2.6s`
- 因此当前最优组是 `doubao-nonthinking2`。

## 运行态修改

- `SUBCONSCIOUS_MODEL`：切到 `doubao-nonthinking2`
- 保持 `judge` 与 `auto_memory` 现有拆分不动

## 业务离线验证目标

- 私聊下第 1 条 intent 命中 `latest_sender_id`
- 问海菜子态度时包含 `HCZ_SELF` 检索意图
- 外号建立时能够写出 `cache_updates.relations`
- 严肃代码任务能判到 `Mode B`
