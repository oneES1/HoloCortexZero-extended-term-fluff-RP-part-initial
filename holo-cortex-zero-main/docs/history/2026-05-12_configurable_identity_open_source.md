# 2026-05-12 高级用户与主人格名称配置化

## 背景

为开源化规范，清理业务代码中直接写死高级用户 ID 与 bot 主人格名称的问题。

## 定位事实

- 修改前 `rg` 命中业务硬编码：
  - `context_window_manager.advanced_user_id = "<ADVANCED_USER_ID>"`
  - `MessageService._PROTECTED_ADVANCED_USER_ID = "<ADVANCED_USER_ID>"`
  - `AdvancedContextModeService._DEFAULT_ADVANCED_USER_ID = "<ADVANCED_USER_ID>"`
  - `file_system.policy._OWNER_USER_ID = "<ADVANCED_USER_ID>"`
  - memory 运行时固定 `_ADVANCED_STATIC_USER_ID = "<ADVANCED_USER_ID>"`
- `BOT_PERSONA_DISPLAY_NAME` 已存在，但 prompt 默认文本和部分系统注入文本仍直接使用“海菜子”。

## 改动

- 新增 `holo_cortex_zero/core/runtime_identity.py`，统一提供：
  - `ADVANCED_USER_ID` 归一化
  - 高级用户 ID 读取
  - 高级用户显示名读取
  - 高级用户判定
  - bot 主人格名称读取
- `CoreConfig` 增加 `ADVANCED_USER_ID` 与 `ADVANCED_USER_DISPLAY_NAME`；前者即高级 context 主用户，后者默认仍为 `海泡菜`。
- 新架构初始化、上下文窗口、消息服务、高级模式、附件接收、记忆检索/写入、TG 私聊伪装显示名统一改读 `runtime_identity`。
- prompt 默认文本保留现有默认人格，但在送入模型前通过 `render_identity_prompt(...)` 按当前配置替换 bot 名字、高级用户 ID 与高级用户显示名；默认配置下渲染结果与原字符串完全一致。
- 通用 tool schema 从 handler docstring 提取参数描述时，也先走同一 `render_identity_prompt(...)`；默认配置下 docstring 提取结果与原字符串完全一致，避免未来把含身份字面量的 docstring 暴露给模型时绕过配置。
- 健康检查/OpenAPI 标题、群聊回复判断 prompt、系统形象参考图说明改读 `BOT_PERSONA_DISPLAY_NAME`。
- `.env.example` 与 `docker/.env.example` 补充开源配置说明。

## 验证

- `python3 -m compileall -q holo_cortex_zero`
  - 结果：退出码 0
- `HCZ_DATA_DIR=/tmp/hcz_config_probe uv run python ...`
  - 断言 `CoreConfig` 前 3 个字段为 `ADVANCED_USER_ID / ADVANCED_USER_DISPLAY_NAME / ENSURE_SFW_CONTENT`
  - 断言默认高级用户为 `<ADVANCED_USER_ID>`
  - 断言将配置改为 `ADVANCED_USER_ID="10001"`、`BOT_PERSONA_DISPLAY_NAME="OpenBot"` 后，`render_identity_prompt(...)` 会把旧默认文本中的 `<ADVANCED_USER_ID>` 替换为 `10001`
  - 结果：打印 `config_identity_probe=ok`，退出码 0
- `HCZ_DATA_DIR=/tmp/hcz_identity_name_probe uv run python ...`
  - 断言默认 `ADVANCED_USER_DISPLAY_NAME=海泡菜` 时，`render_identity_prompt("海菜子|<ADVANCED_USER_ID>|海泡菜|海泡菜发送 <CONTAINER_WORKSPACE_DIR>/a.png")` 输出与输入逐字相同
  - 断言改为 `BOT_PERSONA_DISPLAY_NAME=BotX`、`ADVANCED_USER_ID=10001`、`ADVANCED_USER_DISPLAY_NAME=OwnerX` 后，只替换对应身份字面量，输出 `BotX|10001|OwnerX|OwnerX发送 <CONTAINER_WORKSPACE_DIR>/a.png`
  - 结果：打印 `identity_name_probe=ok`，退出码 0
- `python3 -m compileall -q holo_cortex_zero`
  - 在 tool docstring 渲染补丁后复跑，结果：退出码 0
  - 说明：直接 `uv run python -c 'from ...registry import extract_params_schema'` 暴露 registry 既有循环导入问题（`registry -> host -> db_user -> models -> db_chat_channel -> adapters -> platform -> db_chat_channel`），不作为本次身份渲染逻辑的通过证据；本次补丁使用函数内局部 import，避免新增顶层循环依赖。

## 风险与回滚

- 风险：现有运行配置文件中已保存的自定义 prompt 原文仍包含旧名称/旧 ID；当前通过运行时渲染兜底，不直接改用户私有 prompt 文本。
- 回滚点：本次提交。
