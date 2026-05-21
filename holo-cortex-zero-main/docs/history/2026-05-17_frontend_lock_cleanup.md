# Frontend Lock Cleanup

## 背景

开源友好审查发现前端同时保留 `package-lock.json` 与 `pnpm-lock.yaml`。当前项目开发脚本、Dockerfile 与开发提示均使用 pnpm，`package-lock.json` 属于遗留 npm lock，并固定了大量 `registry.npmmirror.com` 地址。

## 变更

- 删除 `frontend/package-lock.json`。
- 保留 `frontend/pnpm-lock.yaml` 作为唯一前端锁文件。

## 影响

- 避免第三方部署误用 npm lock。
- 避免开源仓库携带由遗留 npm lock 固定的国内镜像源。
- 不改变前端依赖版本来源；Docker 构建仍使用 `pnpm install --frozen-lockfile`。

## 验证

- `pnpm --dir frontend install --frozen-lockfile --offline`
- `pnpm --dir frontend exec tsc --noEmit`
