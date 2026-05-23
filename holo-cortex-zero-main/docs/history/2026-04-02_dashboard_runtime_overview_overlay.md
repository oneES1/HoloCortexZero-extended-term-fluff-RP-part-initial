# Dashboard 运行概览改为图上按钮弹层

## 本次调整
- 撤回上一版“整体折叠 Dashboard”的交互。
- 保留实时图表常驻显示，不再折叠图表本体。
- 将 `运行概览` 改成图表头部的可点击按钮，风格与顶栏 Logo 一样作为触发入口。
- 点击 `运行概览` 后，在图表上方弹出概览浮层，显示：`总消息数`、`Tool链运行`、`活跃排名`。
- 活跃排名继续保留“昵称与消息数同一行”的简化展示。
- 点击图表其他区域或页面其他地方，会自动收起浮层，恢复默认界面。
- 移除已不再使用的 `RankingList.tsx` 僵尸组件。

## 影响文件
- `frontend/src/pages/dashboard/index.tsx`
- `frontend/src/pages/dashboard/components/RealTimeStats.tsx`
- 删除：`frontend/src/pages/dashboard/components/RankingList.tsx`

## 验证
- `cd /path/to/source-root/frontend && pnpm build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 回滚点
- `1ca7bb8` `fix(dashboard): collapse runtime overview`
