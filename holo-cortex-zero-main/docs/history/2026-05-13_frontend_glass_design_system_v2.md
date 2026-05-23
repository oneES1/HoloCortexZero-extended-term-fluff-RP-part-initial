# 前端 Glass Design System V2 重构日志

## 日期
2026-05-13

## 提交哈希
69df1de

## 变更范围
23 个文件，+209/-336 行

## 目标
融合 macOS System Settings 暗色模式（实色面板、清晰层级）与 MacBook Pro 官网（纯黑虚空 + Glass Pill 导航）的 UI 语言，彻底统一前端视觉系统。

## 核心改动

### 1. 设计系统常量 (`theme/glass.ts`)
- 新增 `LOG_TABLE_STYLES`、`metricColors`
- 单一事实来源：VOID、GLASS_PILL、SIDEBAR_GLASS、TOP_BAR、PANEL、PANEL_NESTED、INPUT、COLORS、SHADOWS、RADIUS、MOTION

### 2. 零图标政策
- 删除全部 `@mui/icons-material` 引用（跨 8+ 个页面）
- 所有 IconButton + 图标替换为文字 Button

### 3. 旧主题系统清理
- `theme/variants.ts`、`theme/themeApi.ts`、`theme/themeConfig.ts`、`theme/gradients.ts` 已清空为兼容桩（待后续彻底删除）
- 所有页面不再引用上述文件

### 4. 组件级重写
- **ConfigTable**: 主内容区包裹 `PANEL` 实色卡片（`#1c1c1e`），行边框改为 `rgba(255,255,255,0.06)`，hover 背景 `#252528`
- **HCZDialog**: `SIDEBAR_GLASS` 材质 + 深阴影
- **HCZNotification**: `PANEL` 实色 + 左侧 4px 强调色竖条
- **ThemedTooltip**: `SIDEBAR_GLASS` 轻量版

### 5. 页面级重写
- **Dashboard**: 移除所有 `alpha()`，静态 macOS 系统色
- **Logs**: 移除 `UNIFIED_TABLE_STYLES`，静态 severity 色
- **ChatChannel**: 移除所有图标，文字操作
- **UserManager**: 移除所有图标，文字操作（View/Ban/Lock/Delete）
- **ToolTraces**: 移除所有图标，暗色语法高亮固定为 `vscDarkPlus`
- **Settings/ModelGroup**: 移除旧表格样式

### 6. 构建与部署
- `npx tsc --noEmit`: 零错误
- `pnpm build`: 成功（29.99s）
- Docker 部署：`docker compose up -d --no-deps --force-recreate holo_cortex_zero`

## 2026-05-14 Dashboard 极简排版

### 提交哈希
b061878

### 变更范围
1 个文件，+140/-82 行

### 目标
彻底移除 Dashboard 的「玩具感」，以 Typography + Whitespace 驱动层级，不再依赖卡片容器。

### 核心改动

#### Dashboard (`pages/dashboard/index.tsx`)
- **删除全部 MUI Card / CardContent** — 终结卡片堆砌感
- **Stat 行**：纯数字 + 标签，仅用 `1px solid rgba(255,255,255,0.06)` 底边分隔
- **Chart 区**：`rgba(255,255,255,0.02)` 极淡背景 + `borderRadius: 14px`，无边框
- **底部面板**：macOS 系统设置风格列表，用 `1px` 细线分隔项，hover `rgba(255,255,255,0.025)`
- **布局**：`flex-direction: column` + `height: calc(100vh - offset)` + `overflow: hidden`，彻底修复无限滚动
- **排版**：`letterSpacing: -0.03em` / `fontWeight: 600` 建立信息层级

### 验证
- `pnpm build`：成功（30.39s）
- `npx tsc --noEmit`：零错误
- Docker 部署：`docker compose up -d --no-deps --force-recreate holo_cortex_zero`

## 2026-05-14 Dashboard 左右分栏 + 移除 Logs

### 提交哈希
074d96e

### 变更范围
2 个文件，+66/-282 行

### 目标
从「三层堆叠」改为「左右分栏」，Logs 回归独立页面，Chain Traces 成为 Dashboard 绝对主角。

### 核心改动

#### Dashboard (`pages/dashboard/index.tsx`)
- **删除 LogHistoryPanel 及其所有依赖** — `logsApi`、`LogEntry`、`useNotification`、`getLogHeadline`、`getLogMeta`、`mergeLogs` 等全部移除
- **左右分栏布局**：
  - 左栏（固定 400px）：2×2 紧凑 Stats + Chart（纵向堆叠）
  - 右栏（flex: 1）：ChainMonitorPanel（全高，主角位）
- **Stats 改为 `StatCompact`**：value + label 纵向微间距，去除居中和大字号，适应窄边栏
- **RealTimeStats**：移除 `Card` / `CardContent`，图表直接浮于黑底

### 设计哲学
- 左栏 = 「控制塔」概览（数字 + 趋势）
- 右栏 = 「主舞台」细节（Chain 事件流）
- 打破之前「所有东西平铺」的死板感，赋予页面明确的信息主次

### 验证
- `pnpm build`：成功（30.21s）
- Docker 部署：`docker compose up -d --no-deps --force-recreate holo_cortex_zero`

## 2026-05-14 Dashboard Sidebar + Detail Pane

### 提交哈希
f30e321

### 变更范围
2 个文件，+274/-259 行

### 目标
采用 Apple Mail / Notes 经典「侧边栏列表 + 右栏详情」范式，彻底根治「排布死板」与「视觉重心烂」。

### 核心改动

#### Dashboard (`pages/dashboard/index.tsx`)
- **左栏（260px）**：
  - 顶部「运行概览」选项（默认选中）
  - 下方 Chain 摘要列表：模型名 + 时间 + 工具数 + 耗时，状态只用 7px 圆点（成功绿/失败红）
  - 选中态：左侧 3px `#5c9dff` 竖条 + `rgba(92,157,255,0.04)` 微弱背景
  - **彻底去掉彩色文字标签**（LLM 蓝、Reply 绿等），列表不再像圣诞树
- **右栏（flex: 1）**：
  - 默认显示 `RealTimeStats` 图表
  - 点击 Chain → 右栏切换为 `TraceDetailContent`（从 tool-traces 页面复用）
- **删除 `ChainMonitorPanel`**：旧的纯文本事件列表被 `TraceDetailContent` 取代
- **删除 `StatCompact`**：统计数字整合到「运行概览」条目的副标题中

#### Tool Traces (`pages/tool-traces/index.tsx`)
- `TraceDetailContent` 与 `TraceEventCard` 加 `export`，供 Dashboard 跨页面复用

### 设计哲学
- 侧边栏 = 导航/选择（窄、暗、低信息密度）
- 右栏 = 内容/详情（宽、主视觉区）
- 默认状态 = 图表（满足「一进来就看到运行概览」）
- 点击后 = 详情（满足「chain 是我老看的」）

### 验证
- `pnpm build`：成功（28.13s）
- Docker 部署：`docker compose up -d --no-deps --force-recreate holo_cortex_zero`

## 2026-05-14 Dashboard 美术排版打磨

### 提交哈希
72691b0

### 变更范围
1 个文件，+161/-64 行

### 目标
解决「方向对了但太粗糙」： typography 层级、动效、色彩统一。

### 核心改动

#### Dashboard (`pages/dashboard/index.tsx`)
- **列表项三层排版**：
  - 模型名：`0.84rem`, `fontWeight: 600`
  - 相对时间：`0.72rem`, `#8e8e93`（刚刚 / 5分钟前 / 1小时前）
  - 工具数+耗时：`0.68rem`, `#636366`
- **运行概览头部**：增加 Live 绿色脉冲圆点动画（CSS keyframes）
- **选中态升级**：3px 竖条增加 `box-shadow: 0 0 8px rgba(92,157,255,0.35)` glow 效果
- **右栏切换动画**：`framer-motion` `AnimatePresence` + `motion.div`，`initial={{ opacity: 0, x: 12 }}`
- **TraceDetailContent 风格覆写**：在 Dashboard 容器内全局覆盖 Paper/Alert/Chip 样式，匹配 glass void：
  - Paper → `rgba(255,255,255,0.025)` 背景 + 极淡边框
  - Alert → 去边框，暗红背景
  - Chip → 更小字号、更低对比度

### 验证
- `pnpm build`：成功（29.50s）
- Docker 部署：`docker compose up -d --no-deps --force-recreate holo_cortex_zero`

## 2026-05-14 Dashboard 实色面板对齐 Prompt 页面

### 提交哈希
6120791

### 变更范围
1 个文件，+178/-164 行

### 目标
根治 Dashboard 图表不显示 + 视觉风格与 Prompt 页面统一。

### 核心改动

#### Dashboard (`pages/dashboard/index.tsx`)
- **布局重构为 Prompt 页面范式**：
  - 外层 `p: 2, gap: 1.5`，内部 `grid: 260px + minmax(0, 1fr)`
  - 左右均为 `Paper` 实色面板（主题自动应用 `#1c1c1e` + `16px` 圆角 + 边框 + 阴影）
  - 彻底移除 void 风格背景 `rgba(255,255,255,0.01)` 和 `borderRight` 细线
- **修复图表显示**：
  - 删除 `height: '55%'` 和嵌套 `motion.div height: '100%'` 的百分比坍塌链
  - 改用 `flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column'` 让图表可靠填充
  - `RealTimeStats` 的 `height: '100%'` 在 flex 容器中正确解析
- **列表项风格对齐 Prompt**：
  - 删除 `SELECTED_BAR` 伪元素选中态
  - 采用 `border: 1px solid` + `borderRadius: 2` + `bgcolor: action.selected` 方案
  - Hover 态使用 `action.hover`，边框使用 `text.disabled`
  - 所有硬编码色值改为 `text.primary` / `text.secondary` / `text.disabled`
- **Overview 选项**：同样使用边框+背景选中态，与 Chain 列表项视觉统一

### 验证
- `npx tsc --noEmit`：零错误
- `pnpm build`：成功（28.59s）
- Docker 部署：`docker compose up -d --no-deps --force-recreate holo_cortex_zero`

## 2026-05-14 Dashboard 图表上方统计行

### 提交哈希
bff73c7

### 变更范围
1 个文件，+45/-6 行

### 目标
解决用户反馈"单个图表太空了"。

### 核心改动

#### Dashboard (`pages/dashboard/index.tsx`)
- **图表上方添加紧凑统计行**：
  - 四个指标：Messages / Runs / Success Rate / Sessions
  - 纯排版驱动：大字数字 + 小字标签，无卡片背景
  - 用 `Divider orientation="vertical"` 竖线分隔
  - 数字：`fontSize: 1.35rem`, `fontWeight: 700`, `letterSpacing: -0.02em`
  - 标签：`fontSize: 0.72rem`, `color: text.secondary`
- **图表容器**：统计行下方 `Box sx={{ flex: 1, minHeight: 0 }}` 包裹 `RealTimeStats`，确保图表仍可靠填充剩余空间

### 验证
- `npx tsc --noEmit`：零错误
- `pnpm build`：成功（29.09s）
- Docker 部署：`docker compose up -d --no-deps --force-recreate holo_cortex_zero`

## 2026-05-14 Dashboard 图表下方显示最新 LLM 消息

### 提交哈希
3abb5e3

### 变更范围
4 个文件，+141/-40 行

### 目标
用户反馈"图表地下塞最新的LLM消息简要汇报一行"。

### 核心改动

#### 后端 (`holo_cortex_zero/routers/dashboard.py`)
- **新增 `GET /dashboard/latest-message`**：
  - 查询 `DBChatMessage.filter(sender_id="-1")`（Bot 发送的消息）
  - 按 `create_time` 倒序取第一条
  - 返回字段：`id`, `sender_name`, `content`, `create_time`, `chat_key`

#### 前端 (`frontend/src/services/api/dashboard.ts`)
- 新增 `LatestMessage` 接口
- 新增 `dashboardApi.getLatestMessage()` 方法

#### 前端 (`frontend/src/pages/dashboard/index.tsx`)
- **替换底部统计行为最新消息摘要**：
  - 使用 `useQuery` + `refetchInterval: 10000` 每 10 秒刷新
  - 布局：标签 "Latest"（小字灰色大写）+ 相对时间
  - 内容行：`sender_name`（灰色粗体）+ `content`（主文字色，单行截断）
  - 无消息时显示占位文案
  - 用 `borderTop: 1px solid divider` 细线与图表区分隔

### 验证
- `./node_modules/.bin/tsc --noEmit`：零错误
- `pnpm build`：成功（29.82s）
- Docker 部署：`docker compose up -d --no-deps --force-recreate holo_cortex_zero`

## 2026-05-14 删除 theme 兼容桩文件

### 提交哈希
97913f7

### 变更范围
4 个文件删除

### 核心改动
- 删除 `frontend/src/theme/gradients.ts`
- 删除 `frontend/src/theme/themeApi.ts`
- 删除 `frontend/src/theme/themeConfig.ts`
- 删除 `frontend/src/theme/variants.ts`
- 所有设计系统常量已完全迁移至 `glass.ts`
- grep 确认零引用，tsc + build 零错误

## 待办
- [ ] 浏览器实际验证 Dashboard 最终效果
