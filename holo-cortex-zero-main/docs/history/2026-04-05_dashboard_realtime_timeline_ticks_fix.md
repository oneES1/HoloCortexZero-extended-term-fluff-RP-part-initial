# Dashboard 运行概览时间线刻度修复记录

## 背景
- 前端 `Dashboard` 的运行概览图在 `1小时`、`1天` 视图下勉强可读。
- 当时间窗切到 `1周`、`1月`、`4月` 后，底部刻度仍只显示时分秒，日期信息缺失，导致刻度语义明显错误。

## 根因
1. `frontend/src/pages/dashboard/components/RealTimeStats.tsx` 的 `XAxis` 一直复用固定的时间格式化函数。
2. `frontend/src/utils/time.ts` 中原有格式化逻辑始终输出 `HH:MM:SS`，没有按时间窗做主干分级展示。
3. tooltip 与坐标轴都依赖同一类时间输出，导致长时间窗下信息重复且误导。

## 本次最小修改
- 保持后端流数据与聚合逻辑不变，只修前端展示主干。
- 为时间轴新增按 `granularity` 分级的时间格式化：
  - `1小时` -> `HH:mm`
  - `1天` -> `MM-DD HH:mm`
  - `1周及以上` -> `MM-DD`
- tooltip 改为展示完整时间 `YYYY-MM-DD HH:mm:ss`，避免细节丢失。

## 影响面
- 仅影响 `Dashboard` 运行概览图的横轴刻度与 tooltip 时间展示。
- 不改接口、不改数据结构、不改其它页面时间格式。

## 验证计划
- 执行 `pnpm --dir frontend build` 验证前端构建通过。
- 执行 `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero` 将前端改动同步到当前运行容器。
- 请在 QQ 或 TG 内直接打开 `Dashboard`，切换 `1小时 / 1天 / 1周 / 1月 / 4月` 观察底部刻度是否合理。
