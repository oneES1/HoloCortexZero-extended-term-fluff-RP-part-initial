# 2026-05-20 WebUI 模型组连通性回填测试结果展示

## 背景

用户指出“模型组连通性测试要根据是否放思维链回填决定测试方案”发生在 WebUI 模型组配置页，不是聊天入口。前一轮只把后端 connectivity details 做了回填验证，但 WebUI 仍只显示 `protocol / latency / error`，用户路径看不到回填测试方案与证据。

## 修改

- `frontend/src/pages/settings/model_group.tsx`
  - 读取 `/config/model-groups/test` 返回的 `details.reasoning_replay_*` 字段。
  - 测试按钮下方 Alert 增加紧凑回填测试摘要：
    - 回填测试开启/关闭
    - 是否已使用回填请求
    - 空回填轮次数
    - 最小回填长度
    - 首轮思维长度
  - 保存模型组后的成功通知也追加同一组回填摘要。
- `frontend/src/locales/zh-CN/settings.json`
- `frontend/src/locales/en-US/settings.json`
  - 补齐中英文 WebUI 文案。

## 验证

已执行：

```bash
cd /home/ubuntu/hcz-deploy
HTTP_PROXY=http://127.0.0.1:19192 HTTPS_PROXY=http://127.0.0.1:19192 pnpm --dir holo-cortex-zero-main/frontend exec eslint src/pages/settings/model_group.tsx
HTTP_PROXY=http://127.0.0.1:19192 HTTPS_PROXY=http://127.0.0.1:19192 pnpm --dir holo-cortex-zero-main/frontend build
```

结果：

- eslint：通过。
- build：通过，生成 `dist/assets/model_group-CW18YGGM.js`。
- 仅有既有 Browserslist 过期提示、Tailwind experimental 提示与 chunk 体积警告。

## 影响范围

- 只影响 WebUI 模型组编辑弹窗的连通性测试反馈。
- 不修改模型组配置结构。
- 不修改 LLM 协议发射器。
- 不新增供应商分支。

## 回滚点

回退本次提交即可；不涉及数据库迁移。
