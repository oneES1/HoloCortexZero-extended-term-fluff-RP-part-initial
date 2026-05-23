# Matrix 媒体触发边界修复记录

## 问题

Matrix 私聊媒体接入时曾错误修改 `message_service.py`，把高级私聊媒体-only 消息从“只入库”放宽为“触发回复”。

越界提交：

```text
823480f feat(matrix): support private media messages
```

越界改动：

```text
holo_cortex_zero/services/message_service.py
```

错误规则：

```python
media_segment_types = {"image", "file", "voice", "video"}
```

影响：

- 图片触发回复，错误。
- 普通文件触发回复，错误。
- 音频文件触发回复，错误。
- 视频触发回复，错误。
- 该规则属于业务主干，不应为 Matrix 适配器接入而改。

## 止血

提交：

```text
04ac80e fix(core): revert private media trigger expansion
```

恢复主干行为：

- 私聊是否触发回复只看文本触发。
- 媒体-only 消息可入库和进入后续上下文吸收，但不启动本轮回复。

## Matrix 边界内修复

2026-05-16 更新：voice marker 仍由 Matrix adapter 识别，但触发门禁已上移到统一 collector。adapter 只设置 `PlatformMessageExt.native_voice=True` 并请求 `trigger_agent=True`；collector 只有在统一身份主干确认发送者是主高级用户时才让触发生效。普通用户 native voice 只入库，不触发。

只在适配器入口边界传递触发意图，不改业务回复策略：

- `holo_cortex_zero/adapters/matrix/adapter.py` 负责识别 Matrix voice marker。
- `holo_cortex_zero/adapters/interface/collector.py` 通过通用参数 `trigger_agent` 透传到 `message_service.push_human_message(...)`。
- 不向 `content_data` 或 `content_text` 注入假文本，避免污染上下文和 LLM payload。

Matrix 媒体类型处理：

- `m.image`：下载、托管、入库，`trigger_agent=False`。
- `m.file`：下载、托管、入库，`trigger_agent=False`。
- `m.video`：下载、托管、入库，`trigger_agent=False`。
- 普通 `m.audio`：下载、托管、入库，`trigger_agent=False`。
- Element/Matrix 语音消息：仅当 `m.audio` 事件携带语音标记时，`trigger_agent=True`。

识别的语音标记：

```text
org.matrix.msc3245.voice
org.matrix.msc1767.audio
io.element.voice_message
```

强约束：

- 必须是 `msgtype == "m.audio"`。
- 必须存在上述 marker key。
- marker 值允许是空对象 `{}`，因此判断 key 是否存在，不判断 truthy。
- 不使用文件名、body、mime、duration、waveform 兜底，避免 `voice.mp3` 或伪装音频误触发。
- 该实现不新增业务主干规则，不引入 Matrix 专用主干分支。

被废弃的错误过渡实现：曾向消息段追加 Matrix 语音提示假文本。

该假文本会进入 `content_data`、`content_text`、上下文拼装和 LLM payload，已移除。

## 验证预期

Matrix 发送图片/文件/音频文件/视频：

```text
Matrix 附件接收策略: ... voice=False ...
私聊消息已入库但不触发回复，不启动本轮上下文组装: ... segment_types=image/file ...
```

Matrix 发送 Element 语音：

```text
Matrix 附件接收策略: ... kind=audio voice=True ...
收到语音附件后启动本轮回复；普通音频文件只入库不触发回复。
```

## 回滚

只回滚 Matrix 适配器内语音触发修复时，可回滚本记录对应的 Matrix adapter 提交。

若要恢复业务主干止血前状态，可回滚：

```text
04ac80e fix(core): revert private media trigger expansion
```

但该状态会重新引入图片/文件/视频/音频文件触发回复的问题，不建议回滚。
