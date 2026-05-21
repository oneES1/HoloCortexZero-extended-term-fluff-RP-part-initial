# 跨平台高级身份主干映射记录

Date: 2026-05-16

## 问题

旧逻辑把 Telegram / Matrix 的 owner 私聊直接在适配器内伪装成 `<ADVANCED_USER_ID>`，QQ 则因为平台 ID 本身等于 `<ADVANCED_USER_ID>` 而“看起来正常”。这不是成熟主干：

- TG 配置 `OWNER_TG_USER_ID` 后曾只允许 owner 私聊，群聊和陌生人私聊被入口丢弃。
- Matrix 只处理 owner 私聊，群聊和普通私聊不完整。
- 适配器私有字段曾决定 HCZ 内部高级 ID，例如 `IMPERSONATE_PRIVATE_USER_ID`、`PRIVATE_CHANNEL_ID`。
- Matrix native voice 曾由适配器请求触发，但普通 context 也可能被语音触发。

## 主干规则

身份层统一在 `holo_cortex_zero.adapters.interface.identity`：

- 平台真实 ID 只在适配器边界使用。
- HCZ 高级 ID 只来自 `ADVANCED_USER_ID`。
- HCZ 高级显示名只来自 `ADVANCED_USER_DISPLAY_NAME`。
- 适配器只声明平台侧高级用户 ID：
  - QQ / OneBot：`OWNER_QQ_USER_ID`
  - Telegram：`OWNER_TG_USER_ID`
  - Matrix：`OWNER_MATRIX_USER_ID`
- `BaseAdapter` 默认不声明任何平台侧高级用户，禁止再假设“平台 ID 等于框架高级 ID”。
- 高级用户私聊统一映射为 `private_<ADVANCED_USER_ID>`。
- 高级用户群聊只映射 user，不改 group channel。
- 普通用户不映射。

进入框架后的上下文路由仍由现有主干负责：

- 高级用户：`context_id = ADVANCED_USER_ID`
- 普通用户：`context_id = chat_key`
- 回复窗口：`context_window.active_dialog_id`

`/norm`、`/cute`、`/puss` 不在适配器解析，继续由 `message_service` 和 `advanced_context_mode_service` 处理。

## 平台效果

| 场景 | 框架 user_id | chat_key | context_id |
| --- | --- | --- | --- |
| QQ 高级私聊 | `ADVANCED_USER_ID` | `onebot_v11-private_<ADVANCED_USER_ID>` | `ADVANCED_USER_ID` |
| QQ 高级群聊 | `ADVANCED_USER_ID` | `onebot_v11-group_<群号>` | `ADVANCED_USER_ID` |
| TG 高级私聊 | `ADVANCED_USER_ID` | `telegram-private_<ADVANCED_USER_ID>` | `ADVANCED_USER_ID` |
| TG 高级群聊 | `ADVANCED_USER_ID` | `telegram-group_<真实群ID>` | `ADVANCED_USER_ID` |
| TG 普通私聊 | TG 真实 user_id | `telegram-private_<tg_user_id>` | 同 chat_key |
| TG 普通群聊 | TG 真实 user_id | `telegram-group_<真实群ID>` | 同 chat_key |
| Matrix 高级私聊 | `ADVANCED_USER_ID` | `matrix-private_<ADVANCED_USER_ID>` | `ADVANCED_USER_ID` |
| Matrix 高级群聊 | `ADVANCED_USER_ID` | `matrix-group_<room_hash>` | `ADVANCED_USER_ID` |
| Matrix 普通私聊 | Matrix 真实 user_id | `matrix-private_<room_hash>` | 同 chat_key |
| Matrix 普通群聊 | Matrix 真实 user_id | `matrix-group_<room_hash>` | 同 chat_key |

## 开源配置边界

`ADVANCED_USER_ID` 是 HCZ 框架内高级身份，不是 QQ 号、TG 号或 Matrix ID。开源部署必须显式配置各平台 owner：

```yaml
ADVANCED_USER_ID: owner_internal_001
ADVANCED_USER_DISPLAY_NAME: Owner
```

```yaml
# onebot_v11/config.yaml
OWNER_QQ_USER_ID: '<OWNER_QQ_USER_ID>'
```

```yaml
# telegram/config.yaml
OWNER_TG_USER_ID: '<OWNER_TG_USER_ID>'
```

```yaml
# matrix/config.yaml
OWNER_MATRIX_USER_ID: '@owner:example.com'
```

若某个平台未配置 owner，则该平台没有高级身份映射；普通用户、普通私聊、普通群聊仍按 raw 平台 ID 和 raw channel 工作。

## 会话接入边界

适配器只负责平台会话接入，不决定是否回复：

- 私聊接入默认开启：
  - QQ / OneBot：`AUTO_ACCEPT_PRIVATE_REQUEST=true`，自动接受好友请求。
  - Telegram：`AUTO_ACCEPT_PRIVATE_CHAT=true`，Telegram Bot 无需接受邀请，表示接收私聊 update。
  - Matrix：`AUTO_JOIN_PRIVATE_INVITE=true`，自动加入未加密私聊邀请。
- 群聊接入默认关闭：
  - QQ / OneBot：`AUTO_ACCEPT_GROUP_REQUEST=false`。
  - Telegram：没有“自动加入/接受群聊邀请”的 Bot API 开关，只有被拉入后接收群消息。
  - Matrix：`AUTO_JOIN_GROUP_INVITE=false`，默认拒绝自动加入群聊邀请。
- 是否回复由 HCZ 主干控制：`DBChatChannel.is_active`、私聊/群聊触发逻辑、高级 context 规则、tool 链状态。
- 新频道默认激活状态：
  - 高级私聊 `private_<ADVANCED_USER_ID>` 始终默认启用。
  - 其他新私聊由 `SESSION_PRIVATE_ACTIVE_DEFAULT` 控制，当前运行值为 `false`。
  - 新群聊由 `SESSION_GROUP_ACTIVE_DEFAULT` 控制，当前运行值为 `false`。

## 文件与语音边界

附件接收仍走 `resolve_incoming_attachment_mode(...)`：

- 高级用户 image/file/audio/video/native voice：`managed`
- 普通用户 image：`quarantine`
- 普通用户 file/audio/video：`disabled`

附件下载前需要使用 `preview_canonical_inbound_identity(...)` 生成 canonical sender/chat_key，再调用 policy；这只是同一身份主干的预览，不允许适配器自行决定文件策略。

native voice 规则：

- TG `message.voice` 和 Matrix 带 voice marker 的 `m.audio` 可向 collector 请求触发。
- collector 统一执行门禁：只有主高级用户的 native voice 请求会变成有效触发。
- 普通用户 native voice 只入库，不触发。
- 普通音频文件不是 native voice，不触发。
- 不向 `content_text` 注入语音假文本。

## 验证

静态验证：

```bash
python3 -m py_compile \
  holo_cortex_zero/adapters/interface/base.py \
  holo_cortex_zero/adapters/interface/collector.py \
  holo_cortex_zero/adapters/interface/identity.py \
  holo_cortex_zero/adapters/interface/schemas/extra.py \
  holo_cortex_zero/adapters/telegram/adapter.py \
  holo_cortex_zero/adapters/telegram/message_processor.py \
  holo_cortex_zero/adapters/telegram/config.py \
  holo_cortex_zero/adapters/matrix/adapter.py \
  holo_cortex_zero/adapters/matrix/config.py \
  holo_cortex_zero/adapters/onebot_v11/adapter.py
```

日志验收：

```text
adapter_identity canonicalized ... raw_user=... canonical_user=<ADVANCED_USER_ID> ... trigger_requested=true trigger_effective=true
adapter_identity canonicalized ... trigger_requested=true trigger_effective=false
```

## 回滚

可按提交顺序独立回滚：

- `refactor(adapter): add canonical inbound identity mapping`
- `fix(telegram): route owner identity through shared mapper`
- `fix(matrix): support normal dialogs via shared mapper`
- `chore(docs): document cross-platform identity mapping`
