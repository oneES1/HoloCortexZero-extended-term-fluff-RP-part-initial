# 2026-05-17 adapter open defaults

## 结论

- Matrix 开源默认值不得携带个人部署信息：`HOMESERVER_URL`、`BOT_USER_ID` 默认改为空。
- Telegram `PROXY_URL` 默认改为空，不再从系统 `DEFAULT_PROXY` 继承。
- Matrix `BOT_ACCESS_TOKEN` 和 `BOT_PASSWORD` 同时为空时，按 Telegram 行为只记录 warning 并跳过初始化，不再抛异常中断适配器启动流程。

## 边界

- 只调整代码默认值和空凭据启动行为，不修改当前运行态 `/path/to/runtime-data/configs/*/config.yaml`。
- 适配器私聊/群聊接入开关不变：TG `AUTO_ACCEPT_PRIVATE_CHAT=true`，Matrix `AUTO_JOIN_PRIVATE_INVITE=true`、`AUTO_JOIN_GROUP_INVITE=false`。
- Matrix 仍不继承系统代理；TG 也收口为不继承系统代理。需要代理时必须在适配器配置里显式填写 `PROXY_URL`。
- Matrix / TG README 同步为开源占位示例，不展示个人部署地址作为默认。

## 验证

- `python3 -m py_compile holo_cortex_zero/adapters/telegram/config.py holo_cortex_zero/adapters/matrix/config.py holo_cortex_zero/adapters/matrix/adapter.py` 通过。
- `rg 'default="https://holocortexzero\.com:9443"|default="@hcz:holocortexzero\.com"|default_factory=_get_default_proxy|def _get_default_proxy' holo_cortex_zero/adapters docs/history/2026-05-17_adapter_open_defaults.md -S --glob '!*.log'` 无结果，确认个人部署值未作为代码默认残留。
