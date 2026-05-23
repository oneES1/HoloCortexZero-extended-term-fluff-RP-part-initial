# Matrix 适配器

Matrix 适配器使用 `matrix-nio[e2e]` SDK 处理 Matrix Client-Server 通信和 E2EE。HCZ 仍只接收适配器输出的统一 `PlatformMessage`。

## 身份规则

Matrix 真实账号只在适配器边界使用。平台侧高级用户由 `OWNER_MATRIX_USER_ID` 声明；进入 HCZ 后由统一身份主干映射为 `ADVANCED_USER_ID` 和 `ADVANCED_USER_DISPLAY_NAME`。

- 高级私聊：`matrix-private_<ADVANCED_USER_ID>`
- 高级群聊：`matrix-group_<room_hash>`，只映射 sender，不改群聊 channel
- 普通私聊：`matrix-private_<room_hash>`
- 普通群聊：`matrix-group_<room_hash>`

真实 Matrix `room_id` 保存在适配器状态文件，不写入 HCZ 主身份字段。

## 会话接入

```yaml
HOMESERVER_URL: https://your-matrix-homeserver.example
BOT_USER_ID: '@bot:example.com'
BOT_PASSWORD: ''
BOT_ACCESS_TOKEN: ''
AUTO_JOIN_PRIVATE_INVITE: true
AUTO_JOIN_GROUP_INVITE: false
```

Matrix 默认自动加入私聊邀请，默认不自动加入群聊邀请。开启 `AUTO_JOIN_GROUP_INVITE` 后才会自动加入群聊邀请。是否回复由 HCZ 聊天频道 `is_active`、触发逻辑和 context 规则决定。

Owner 发来的无 `is_direct=true`、且房间无 name/alias 的邀请，会按高级私聊邀请处理并自动加入。群聊邀请默认不加入。

## SDK / E2EE 配置

```yaml
PROXY_URL: ''
DEVICE_ID: HCZ_MATRIX_ADAPTER
CRYPTO_STORE_PATH: crypto_store
IGNORE_UNVERIFIED_DEVICES: true
```

- `DEVICE_ID`：Matrix SDK 登录设备 ID，也用于 E2EE crypto store 关联。
- `CRYPTO_STORE_PATH`：`matrix-nio` E2EE 持久化目录；相对路径位于 Matrix 适配器配置目录下。
- `IGNORE_UNVERIFIED_DEVICES`：向加密房间发送消息时是否允许发送给未验证设备。默认开启，适合外部 Matrix 服务器和未手动验证设备的开源部署；严格安全部署可改为 `false`。

## 限制

- 运行环境必须安装 `matrix-nio[e2e]` 及其 E2EE 依赖。
- 启动时会先执行一次 timeline limit 为 0 的 bootstrap sync，只建立 sync token 和学习 joined rooms，不回放旧 timeline。
- 图片、音频、视频、文件入站会通过 SDK 下载/解密 Matrix `mxc://` 媒体并交给 HCZ 统一附件接收策略。
- Bot 出站图片、文件和语音会通过 SDK 上传；加密房间中上传媒体会使用 SDK 加密附件元数据。若目标 room 未同步，媒体发送会失败，不做明文降级。
- 编辑消息、撤回消息后续再接。

## 高级模式命令

高级用户在 Matrix 私聊或群聊中沿用框架主干命令：

- `/cute`：切到 deek 模式。
- `/puss`：切到 deep 模式。
- `/norm`：切回普通高级模式。
- `/clear`：清空当前上下文消息记录。
- `/clearall`：清空当前上下文消息记录和压缩摘要。
