# 2026-04-01 OneBot NapCat 本地文件可达性主干热修

## 现象

- OneBot 图片发送在补完 `file:///...` URI 后，仍出现 `ENOENT`
- NapCat 日志表现为尝试从 `<CONTAINER_DATA_DIR>/system/...` 或其他本地路径复制文件到 `<NAPCAT_CONTAINER_CONFIG_DIR>/temp/...` 时失败
- 这说明问题不再是 URI 格式，而是 NapCat 容器看不到源文件路径

## 根因

- `holo_cortex_zero` 容器能看到的本地文件，不一定等于 `hcz_napcat` 容器能看到的本地文件
- 当前 OneBot 适配器仅做了简单前缀映射：
  - 工作区路径 -> `<CONTAINER_WORKSPACE_DIR>/...`
  - 运行态数据路径 -> `<CONTAINER_DATA_DIR>/...`
- 但 NapCat 实际只稳定挂载了：
  - `<CONTAINER_WORKSPACE_DIR>`
  - `/app/.config/QQ`
  - `<CONTAINER_DATA_DIR>/napcat_data`
- 因此，像 `<CONTAINER_DATA_DIR>/system/emoji/...` 这类路径对 NapCat 并不可见，导致图片发送失败；同类问题也可能波及其他本地文件发送链路

## 修复

- 仅修改 `holo_cortex_zero/adapters/onebot_v11/adapter.py`
- 将 OneBot 本地文件出口统一收口为单一主干：
  - 文件位于 `WORKSPACE_ROOT` 下：直接映射到 NapCat 的 `<CONTAINER_WORKSPACE_DIR>/...`
  - 文件已位于 `napcat_data/QQ` 下：直接映射到 NapCat 的 `/app/.config/QQ/...`
  - 其他任意本地文件：先物化复制到 `NAPCAT_TEMPFILE_DIR`，再交给 NapCat 发送
- 图片富文本发送继续使用 `file:///...` URI
- 文件上传发送改走同一套可达路径解析主干
- 不把数据库、Postgres 数据目录或其他运行态目录整体挂入工作区，不动 Docker 挂载主结构

## 验证

- `python3 - <<'PY'` 对 `adapter.py` 做内存编译校验
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`
- 观察运行日志：
  - 工作区文件应出现 `OneBot 本地文件直连 workspace`
  - 非共享路径文件应出现 `OneBot 本地文件已物化到 NapCat temp`
  - 文件上传应出现 `OneBot 文件上传路径已解析`
- 在 QQ/TG 直接触发图片与文件发送，确认不再出现 `识别URL失败` 或 `ENOENT copyfile`

## 回滚点

- 本次热修应独立提交，可按提交哈希单独回退
