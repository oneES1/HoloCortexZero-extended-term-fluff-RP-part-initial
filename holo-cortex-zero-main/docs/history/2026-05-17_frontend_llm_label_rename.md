# 2026-05-17 前端中文 LLM 文案整理

## 背景

中文 UI 中多处仍使用“模型组”“高级用户”等旧称呼。本次只做展示层词条整理，不修改配置字段名、默认值、运行路由或 LLM 协议逻辑。

## 证据

- `frontend/src/locales/zh-CN/settings.json` 与 `frontend/src/locales/zh-CN/common.json` 中存在多处“模型组”展示文案。
- `holo_cortex_zero/core/config.py` 的配置 schema 标题和描述会通过 `/config/list/system` 返回给前端 `ConfigTable` 与 Manage Prompts 使用。
- `frontend/src/pages/prompt-management/index.tsx` 的 Prompt 列表标题来自后端 schema 的 `title` / `i18n_title`，因此 Prompt 标签必须在 `core/config.py` 的源头修正。

## 修改与核对

- 中文 UI 将“模型组”展示称呼统一为 `LLM`。
- Manage Prompts 中：
  - `主人格显示名` 改为 `智能体昵称`。
  - `高级用户上下文系统提示词` 改为 `群聊回复你的norm模式提示词`。
  - `高级用户 deek 系统提示词` 改为 `私聊回复你的cute模式提示词`。
  - `高级用户 deep 系统提示词` 改为 `你专用的Pro模式提示词/puss触发`。
- 系统配置中：
  - `高级用户 ID` 改为 `对智能体的统一ID标识`。
  - `高级用户显示名` 改为 `你对智能体的统一昵称`。
  - 主 LLM、cute LLM、Pro LLM、普通用户 LLM、备用 LLM 按需求排序。
  - cute LLM 标题前增加 `★`。
  - 主/cute/Pro LLM 的问号提示改为对应 `/norm`、`/cute`、`/puss` 说明。
  - `用户日常照路径` / `用户写真照路径` 改为 `你的日常照路径` / `你的写真照路径`。
  - `默认代理` 字段移动到系统配置列表最后。

本次提交实际补齐的差异：

- `frontend/src/locales/zh-CN/settings.json` 中新建/编辑/复制对话标题从“模型组”改为 `LLM`。
- `holo_cortex_zero/core/config.py` 中 cute 提示词描述的回退目标，从旧的“高级用户上下文系统提示词”改为新的 `群聊回复你的norm模式提示词`。
- `ADVANCED_CONTEXT_MODE_DEEK_MODEL_GROUP` 的强调星号改为配置表独立 `*` 标记，标题文本保持 `私聊回复你的LLM`，避免把星号写入标题文本。
- 其余上述词条在当前基线中已满足，本次重新检索确认。

## 验证

```bash
rg -n '模型组|主人格显示名|高级用户上下文系统提示词|高级用户 deek 系统提示词|高级用户 deep 系统提示词|用户日常照路径|用户写真照路径' frontend/src/locales/zh-CN holo_cortex_zero/core/config.py
```

预期：中文 UI 源头不再出现上述旧称呼。

## 风险与回滚

- 风险：字段顺序调整会改变系统配置页展示顺序；字段名、保存格式和运行逻辑不变。
- 回滚点：本次修复提交。
