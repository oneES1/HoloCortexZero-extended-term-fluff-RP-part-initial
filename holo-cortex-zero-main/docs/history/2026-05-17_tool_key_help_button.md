# Tool Key 帮助按钮

## 背景

Seek 和 Weather 的 Tool 配置里只有 API Key 输入项，小白用户不知道去哪里申请 Tavily / QWeather 的服务 Key。

## 修改

- 在通用配置字段元数据 `ExtraField` 中新增 `help_label` / `help_text`。
- 前端通用 `ConfigTable` 在配置项带 `help_text` 时显示帮助按钮，点击后弹出说明窗口。
- 给 `seek.TAVILY_API_KEY` 和 `weather.API_KEY` 补充“获取 Key 指南”说明。
- 将这两个 Key 字段标记为 `is_secret=true`，避免 WebUI 明文展示密钥。

## 验证

- `pnpm --dir frontend build` 成功，构建耗时 31.54s。
- `uv run python` 验证动态 Tool 配置模型输出：
  - `seek TAVILY_API_KEY True 获取 Key 指南 True`
  - `weather API_KEY True 获取 Key 指南 True`

## 风险与回滚

- 风险：前端通用配置表新增一个可选弹窗状态；只有后端返回 `help_text` 的字段才显示按钮，其他配置项不变。
- 回滚点：回退本次提交即可移除按钮、字段元数据和两段 Key 说明。
