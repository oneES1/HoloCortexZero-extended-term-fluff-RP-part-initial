# Matrix E2EE room key request fix

## 背景

Matrix 适配器收到部分 E2EE 消息后，SDK 无法把加密事件解密成普通消息事件，导致消息没有进入 HCZ 的统一消息收集链路，bot 不会回复对应发送者。

## 脱敏证据

- Matrix 适配器运行态已启用，E2EE crypto store 存在且有核心表数据。
- Matrix 频道处于启用状态，Matrix 用户未被封禁。
- 告警时间后仍有 Matrix 消息进入数据库，说明 Matrix 适配器不是整体离线。
- 目标未解密事件对应的 Megolm 入站 session 在本地 store 中不存在。
- 本地 store 中存在同一 session 的 outgoing key request，说明状态层已经进入缺 key/等补钥匙状态。

## 根因

当前 `MegolmEvent` 回调只记录解密失败并跳过事件，没有在适配器层主动调用 SDK 的 room key 请求接口。缺少 room key 时，该事件不会生成 `PlatformMessage`，因此不会进入：

```text
collect_message -> push_human_message -> bot reply
```

## 修复

- 在 Matrix 未解密事件回调中调用 SDK 的通用 `request_room_key(event)`。
- 对已请求过的 room key 做幂等处理，避免重复请求异常影响同步循环。
- 启动登录后立即检查并上传 E2EE device keys，避免等到后续 sync loop 才发布设备密钥。
- 对缺 key 的外部发送者，额外向原发送设备发送一次受控 room key 请求。
- 同一 session 的补钥匙请求做 60 秒内存节流，避免重复未解密事件刷屏请求。
- 常驻日志改为脱敏描述，不记录 room、sender、event、session 等 Matrix 标识。

## 追加验证

后续运行态出现“room key 已请求过但仍跳过当前未解密事件”，说明只请求同账号设备不能闭合外部发送者场景。Matrix 发送端若在加密会话建立时没有把 bot 当前设备包含进去，bot 仍然拿不到该 Megolm session。追加修复后，适配器会同时保证本端 device keys 尽早发布，并向原发送设备发起补钥匙请求。

## 验证

```text
uv run python -m py_compile holo_cortex_zero/adapters/matrix/adapter.py
```

编译检查通过。

## 后续测试

需要让对端在 Matrix 客户端重新发送一条 E2EE 消息测试。若对端客户端拒绝向 bot 设备共享 room key，需要在 Matrix 客户端侧信任/验证 bot 设备或允许补发 room key。
