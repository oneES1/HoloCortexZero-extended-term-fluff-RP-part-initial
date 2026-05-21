# 2026-05-20 `.env.prod` tracking fix

## 问题

`holo-cortex-zero-main/dockerfile` 需要复制 `holo-cortex-zero-main/.env.prod`：

```dockerfile
COPY .env.prod ./
```

但仓库根部 `.gitignore` 把 `**/.env.*` 统一忽略了，`holo-cortex-zero-main/.env.prod` 在 Git 里没有被跟踪。

这会导致 GitHub 上的干净克隆缺少 `.env.prod`，从而在 `docker build` 阶段直接失败，哪怕这个文件内容只是安全默认值。

## 修复

- 在根 `.gitignore` 增加对 `holo-cortex-zero-main/.env.prod` 的白名单
- 将 `holo-cortex-zero-main/.env.prod` 纳入版本控制

## 证据

- `git check-ignore -v holo-cortex-zero-main/.env.prod` 之前命中的是 `**/.env.*`
- `holo-cortex-zero-main/.env.prod` 内容只有生产默认值，不含敏感信息
- 该文件是 Dockerfile 的直接构建输入，不应依赖本地临时存在

## 验证

- `git check-ignore -v holo-cortex-zero-main/.env.prod`
- `git ls-files --error-unmatch holo-cortex-zero-main/.env.prod`
- `docker build` 构建上下文中不再依赖本地私有未跟踪文件

