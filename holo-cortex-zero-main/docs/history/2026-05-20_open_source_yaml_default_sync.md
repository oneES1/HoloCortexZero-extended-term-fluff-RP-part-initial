## 目标

在开源前审查阶段，把当前运行态业务 YAML 同步到源码树内的默认 YAML 位置，避免默认模板长期过时、开关缺失或结构不一致。

## 实际来源与目标

- 运行态业务 YAML 来源：`/srv/holo_cortex_zero/configs`
- 源码默认 YAML 目标：`/home/ubuntu/hcz-deploy/holo-cortex-zero-main/data/configs`

## 本次同步范围

共同步 24 个 YAML 文件：

- 系统主配置：`holo-cortex-zero.yaml`
- 适配器配置：
  - `matrix/config.yaml`
  - `onebot_v11/config.yaml`
  - `telegram/config.yaml`
- Tool 配置：
  - `tools/apply_patch.yaml`
  - `tools/block_full.yaml`
  - `tools/block_prevent_trigger.yaml`
  - `tools/costume_design.yaml`
  - `tools/echo.yaml`
  - `tools/gif_generation.yaml`
  - `tools/isolate.yaml`
  - `tools/lightroom.yaml`
  - `tools/list_blocked_users.yaml`
  - `tools/list_files.yaml`
  - `tools/photoshop.yaml`
  - `tools/read_file.yaml`
  - `tools/run_command.yaml`
  - `tools/search_code.yaml`
  - `tools/seek.yaml`
  - `tools/send_file.yaml`
  - `tools/unblock_user.yaml`
  - `tools/vow.yaml`
  - `tools/weather.yaml`
  - `tools/write_file.yaml`

## 校验事实

- `diff -rq /srv/holo_cortex_zero/configs /home/ubuntu/hcz-deploy/holo-cortex-zero-main/data/configs`
- 结果显示 YAML 主文件已对齐；剩余差异仅为运行态备份文件：
  - `holo-cortex-zero.yaml.bak-*`
  - `onebot_v11/config.yaml.bak-20260520-napcat-web-login`
- 非 YAML 运行态持久化目录未同步到源码默认目录：
  - `matrix/crypto_store`
  - `matrix/room_map.json`
  - `system_moment`
  - `instance.json`

## 注意

当前源码树 `holo-cortex-zero-main/.gitignore` 第 162 行忽略了 `data` 目录，因此这批默认 YAML 虽已落盘，但不会进入 `git status`。若后续决定把这批默认 YAML 纳入开源仓库，还需要单独调整忽略规则。
