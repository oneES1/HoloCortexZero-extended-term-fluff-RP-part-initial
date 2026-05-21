# 登录页极简下划线样式

## 本次调整
- 登录页输入框改为透明底 + 单条白色下划线，去掉左右包裹感。
- 用户名输入框去掉提示文案，保留输入能力但默认透明展示。
- 登录按钮在未输入密码前保持视觉不可见；输入密码后再淡入显示。
- 页脚文案字号微调放大，保持原有位置与内容。
- 后续微调中收窄两条输入线之间的垂直间距，并将密码框占位居中改为 `于全息智脑深处`。
- 密码框占位颜色与页脚文案颜色对调，保留整体极简对比关系。
- 再次收紧 `User` 与密码输入线之间的专属间距，避免中间留白过空。
- 进一步直接压缩输入框高度与首条输入线的底部外边距，缩短两条横线的实际距离，不调整字体大小。

## 影响文件
- 登录页组件
- `docs/2026-04-03_login_page_minimal_underline.md`

## 验证
- `cd /path/to/source-root/frontend && NODE_OPTIONS='' pnpm build`
- `cd /path/to<CONTAINER_WORKSPACE_DIR> && printf '<SUDO_PASSWORD>\n' | sudo -S docker compose -f docker-compose.yml up -d --force-recreate holo_cortex_zero`

## 回滚点
- `b141c46` `fix(frontend): refine dashboard trace nav labels`
