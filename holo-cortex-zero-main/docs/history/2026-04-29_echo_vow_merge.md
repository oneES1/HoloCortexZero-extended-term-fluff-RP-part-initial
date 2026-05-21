# 2026-04-29 echo / vow 合并

## 背景

用户要求把 `echo` 与 `vow` 合并，保留 `vow` 的持久化与重启补回能力，同时对外只保留 `echo` 定时提醒入口。

## 当前逻辑

- 对外注册的系统 Tool 只保留 `echo`。
- `echo.when` 支持三种语义，`reason` 仅在创建定时时必填：
  - 负数：清空当前 context 下此前持久化定时与运行态定时器。
  - 正整数：解释为距离当前时间的秒数。
  - `YYYY-MM-DD HH:MM[:SS]`：解释为本地绝对时间。
- 新建 `echo` 定时会写入 `data/configs/system_moment/vows.json`，沿用原持久化文件以承接既有记录。
- 后台巡检继续按配置开关与间隔补回持久化定时器，避免重启后丢失。

## 修改点

- `holo_cortex_zero/services/moment/service.py`
  - 删除对外 `vow` tool 注册与 `tool_vow` / `schedule_vow` 主干。
  - `echo` 改为持久化定时，复用原巡检补回机制。
  - 删除 Unix 时间戳阈值与 `+1d/+1w` 等旧分支解析，只保留用户指定的三种 `when` 语义。
- `holo_cortex_zero/core/config.py`
  - 删除不再使用的 `SYSTEM_MOMENT_VOW_MAX_DAYS` 与 `SYSTEM_MOMENT_ECHO_SECONDS_THRESHOLD`。
  - 将巡检配置展示文案改为持久提醒语义。
- `docs/guides/tool-development.md`、`docs/guides/tool-integration.md`
  - 系统 Tool 清单改为只列 `echo`。

## 验证

- `python3 -m py_compile holo_cortex_zero/services/moment/service.py holo_cortex_zero/core/config.py`

## 回滚点

- 修改前快照提交：`67ab8cc backup(moment): snapshot before echo vow merge`
