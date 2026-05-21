## 目标

修复开源前默认配置无法进入仓库的问题，并去掉 Matrix 默认配置中的现网域名绑定。

## 修改

- 删除 `holo-cortex-zero-main/.gitignore` 中对 `data` 目录的忽略规则。
- 保留源码树当前 `data/configs/**` 作为开源默认配置来源。
- 将 `data/configs/matrix/config.yaml` 中的 `HOMESERVER_URL` 从现网域名改为示例域名 `https://matrix.example.com`。

## 为什么

- 当前 `data/configs/**` 已经是人工审过的源码默认 YAML，但此前被 `.gitignore` 忽略，无法进入开源仓库。
- `matrix/config.yaml` 中原值 `https://holocortexzero.com` 属于现网域名绑定，不适合作为开源默认模板。
- `POSTGRES_HOST` / `QDRANT_URL` 与 `onebot_v11` 中的 NapCat 内网配置保持不动，因为它们承载当前源码主干的可执行默认语义，不在本次最小开源收口范围内。

## 边界

- 不修改 `holo-cortex-zero.yaml` 中 `POSTGRES_HOST` / `QDRANT_URL`。
- 不修改 `onebot_v11/config.yaml` 中 `NAPCAT_PROXY_BASE_URL` / `NAPCAT_CONTAINER_NAME`。
- 不补回源码主干未注册的旧 Tool YAML。
