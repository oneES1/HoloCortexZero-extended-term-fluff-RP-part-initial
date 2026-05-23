# 2026-04-06 UniAPI `hk` 地址批量切换

## 目标
- 用户确认仅做运行时配置替换，不改代码逻辑。
- 将当前仍指向 `https://hk.uniapi.io/v1` 的模型组批量切到 `https://api.uniapi.io/v1`。

## 本次替换
运行时配置文件：`/path/to/runtime-data/configs/holo-cortex-zero.yaml`

批量替换的模型组：
- `Uni-gemini-3-pro-image`
- `Uni-qwen-3.5-plus`
- `Uni-gemini-3.1-flash-img`
- `Uni-qwen397`
- `Uni-grok-4.20-beta-0309-reasoning`

说明：此前已切过的 `Uni-grok-4-1-fast` 保持为 `https://api.uniapi.io/v1`，本次未回退。

## 验证
- 执行 `docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero` 同步运行态。
- 容器健康检查恢复为 `healthy`。
- 容器内 `GET https://api.uniapi.io/v1/models` 返回 `HTTP/2 200`。
- 返回体包含当前所需的 Gemini / Qwen / Grok 家族模型，说明新地址基础联通性与鉴权正常。

## 风险
- 本次仅验证了统一入口 `api.uniapi.io` 的基础连通性与模型列表，不等同于逐个业务链路全部实测。
- 若某个模型组依赖旧 host 名称上的特殊兼容分支，仍需在真实会话里继续观察。
