# 2026-05-17 Models UI 连通性测试与 DeepSeek 推荐入口

## 背景

用户要求 Models UI 前端增加连通性测试，并把推荐 API 供应商加入 DeepSeek 且放在第一位。

## 修改

- 在模型组编辑弹窗中新增“测试连通性”按钮。
- 连通性测试改为后端真实最小调用：
  - 对话模型组：走现有 LLM router 与协议发射器，发起极小 tool call 请求，拿到 tool call 后喂回 tool 结果，再请求一轮；全链路不报错才判定可用。
  - `embedding`：走 OpenAI-compatible `/embeddings`，验证返回向量非空。
  - `draw`：只访问轻量 `/model` 元信息端点；成功判定可用，失败标记疑似不可用，不发起绘图生成。
  - 输入条件：`BASE_URL` 与 `CHAT_MODEL` 非空，`API_KEY` 按供应商需要传递。
  - 超时：30 秒。
  - 成功反馈：协议路径与耗时毫秒数。
- 模型组保存接口在写入配置后自动执行一次连通性测试，并把结果返回前端。
- 前端保存 / 更新后主动提示：
  - 测试成功：提示已保存且连通性正常。
  - 测试失败：提示已保存但连通性失败，附协议路径与错误摘要。
- 推荐供应商列表首位新增 DeepSeek：
  - `https://api.deepseek.com/v1`
- 补齐中英文 i18n 文案。

## 影响范围

- 改前端表单交互、前端文案与配置路由。
- 不改后端配置结构。
- 不改 LLM 协议发射器。
- 不新增供应商专用请求主干；DeepSeek 只作为推荐地址项出现。

## 验证

- 已执行：`pnpm --dir frontend build`
- 已执行：`python3 -m py_compile holo_cortex_zero/services/llm/connectivity.py holo_cortex_zero/routers/config.py`
- 结果：通过
- 备注：仅有既有 Browserslist 过期提示与 chunk 体积警告，不影响构建产物生成
- 追加修正：对话模型组改为极小 tool call 双轮闭环；`draw` 改为 `/model` 元信息探测，失败只标记“疑似不可用”

## 回滚点

- 本次改动可通过回退提交恢复。
