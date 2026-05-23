# 2026-04-27 上下文环境提示格式收紧

## 背景

上下文拼装末尾原本追加两行动态指导：

- `对话环境：群聊` / `对话环境：私聊` 等环境标注
- `目前系统时间：YYYY-MM-DD HH:MM:SS CST+0800`

用户要求改成更短、更直接的关系距离提示，并去掉完整时间戳，只保留星期与时区。

## 本次修改

改动集中在 `holo_cortex_zero/services/context_window/assembler.py`：

- 群聊统一输出：`当前环境：群聊**请保持距离**发言干练，今天星期X，CST+0800`
- 高级 context 的高级用户私聊输出：`当前环境：高级用户私聊，今天星期X，CST+0800`
- 其他私聊输出：`当前环境：第三者私聊**请保持距离**发言干练，今天星期X，CST+0800`
- `X` 由运行时 `datetime.now().weekday()` 映射为 `一二三四五六日`
- 不再追加第二行 `目前系统时间：...`

## 边界

- 不改 context 历史消息格式
- 不改发送者归属后缀逻辑
- 不改 prompt 选择器、模型路由、适配器或记忆链
- 不回写旧 `DBContextMessage`

## 风险

- 模型不再直接看到完整日期和时分秒，只看到星期与 `CST+0800`。
- 私聊重新细分为高级用户私聊与第三者私聊；判断依据是高级 context 且当前私聊窗口包含该高级 context_id。

## 回滚点

如需回滚，撤销以下文件中的本次修改：

- `holo_cortex_zero/services/context_window/assembler.py`
- `docs/2026-04-27_context_environment_hint_format.md`
