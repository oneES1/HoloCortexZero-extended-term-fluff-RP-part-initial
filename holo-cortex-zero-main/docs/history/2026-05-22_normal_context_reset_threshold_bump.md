# 2026-05-22 普通 context 重置阈值上调

## 背景

- 真实业务排查表明，普通群 context 在 `NORMAL_CONTEXT_RESET_THRESHOLD_MESSAGES=18` 下，
  容易因为单轮批量同步的新消息过多而触发 archive reset。
- reset 一旦发生，`compressed_summary` 之后的 regular history 会整体换血，
  从而让 provider 侧已落盘的 cache prefix unit 失效，出现 `cached_tokens=0`。

## 本次修改

- 文件：`data/configs/holo-cortex-zero.yaml`
- 调整：
  - `NORMAL_CONTEXT_RESET_THRESHOLD_MESSAGES: 18 -> 32`
- 其余普通 context 主干逻辑不变：
  - `NORMAL_CONTEXT_RESET_KEEP_MESSAGES` 仍为 `10`
  - 裁剪统计口径仍为 countable chat（`human_chat + bot_reply`）
  - payload 读取 regular history 的方式不变

## 预期影响

- 普通 context 更不容易在高频群聊下过早触发 archive reset。
- 在不改 provider 协议和 payload 排布的前提下，可减少“前缀在较早 message 处整体换血”的发生频率。

## 风险说明

- 阈值调大后，普通 context 在 reset 前会保留更多原始上下文。
- 这是部署默认值调优，不改变代码主干；若后续发现上下文膨胀副作用，可单独回退该配置值。
