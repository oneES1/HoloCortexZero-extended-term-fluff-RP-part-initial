# Dashboard 日志历史秒级时间与摘要收口

## 本次调整
- 日志历史列表时间统一显示为秒级时间：`YYYY-MM-DD HH:mm:ss`。
- 列表主摘要不再直接堆完整报错文本，优先抽取错误类型/异常名；抽不出来时再退回首段简述。
- 列表次要信息改为 `source · function:line`，方便快速知道“是什么位置出的什么问题”。
- 详情弹窗仍保留完整日志正文，复制能力不变。

## 影响文件
- `frontend/src/pages/dashboard/index.tsx`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 回滚点
- `374ab33` `feat(dashboard): show full chain and debug logs`
