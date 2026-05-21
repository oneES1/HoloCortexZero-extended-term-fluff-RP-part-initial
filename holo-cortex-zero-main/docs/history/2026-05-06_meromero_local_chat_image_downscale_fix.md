# 2026-05-06 MeroMero 本地 chat 图片缩放与 UBATCH 修复

## 背景

- `meromero-31b-resident` 走本地 `chat.completions` resident 链路：`<HOST_GATEWAY_IP>:18081 -> hcz:18000`
- 2026-05-06 晚间出现 `RemoteProtocolError('Server disconnected without sending a response.')`
- 远端 `llama-server` 实际为 `status=6/ABRT`

## 根因

- 崩溃发生在图片处理阶段，而不是纯文本阶段。
- 远端断言为：
  - `non-causal attention requires n_ubatch >= n_tokens`
- 现场数据：
  - 图片批次 `n_tokens_batch = 256 / 276`
  - resident 当时 `UBATCH = 64`
- 因此图片模态在本地 resident 链路上会触发 `UBATCH` 不足而中止进程。

## 修改

### HCZ 侧

- 仅对模型组 `meromero-31b-resident` 增加本地 chat 图片缩放开关：
  - `local_chat_image_max_long_edge = 768`
- 仅在 `openai_chat.py` 中读取该开关。
- 仅对本地 resident `chat` 图片 data URI 进行缩放，不影响其他模型组，不影响 `/responses` 主链。

### 远端 resident 侧

- 将 `run/start_meromero_gguf.sh` 的默认 `UBATCH`：
  - 从 `64` 提高到 `384`

## 风险

- `UBATCH` 提高后显存压力会上升。
- 图片会被压到长边不超过 `768`，极端细节图可能损失局部识别能力。
- 修复范围刻意收敛到单模型组 resident chat，不扩散到别的链路。

## 回滚

- HCZ：移除 `local_chat_image_max_long_edge` 开关，并撤回 `openai_chat.py` 的本地 resident 图片缩放逻辑。
- 远端：将 `UBATCH` 改回 `64`，然后重启 `meromero-gguf.service`。
