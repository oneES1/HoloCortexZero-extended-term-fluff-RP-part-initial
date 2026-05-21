# 2026-05-20 登录页位置恢复

## 问题

登录页动效重做时越界修改了 UI 位置：将原本基于绝对坐标的 logo、品牌文案、登录框改成了响应式 grid，超出了“重做动画表现力”的范围。

## 恢复原则

- 保留本次动效背景层 `CortexFieldBackground`。
- 恢复登录页主体元素的原始位置关系。
- 不修改登录鉴权逻辑、不修改后端、不重启 Docker。

## 恢复内容

- logo 恢复为 `left: 7vw; top: 10vh`。
- 品牌文案恢复为 `left: 42vw; top: 40vh`。
- 登录框恢复为 `right: 12vw; bottom: 5vh`。
- 登录框恢复为外层全屏内容层的直接绝对定位子节点，避免坐标相对品牌文案容器生效。

## 验证

```bash
pnpm --dir frontend exec eslint src/pages/login/index.tsx
pnpm --dir frontend build
curl -sS -D - --max-time 5 http://127.0.0.1:20261/webui/ -o /tmp/hcz_webui_login_position_restore.html
```
