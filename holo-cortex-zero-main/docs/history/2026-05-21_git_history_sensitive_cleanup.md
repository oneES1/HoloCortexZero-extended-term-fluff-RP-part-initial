# 2026-05-21 Git 历史敏感信息清理记录

## 背景

HCZ 部署工作区长期承载开发、部署、运行排障和开源整理工作，旧 Git 历史中可能混有较多敏感信息痕迹与运行环境痕迹。继续保留旧历史会带来后续传播、误推送、误打包和审计遗漏风险。

本次按用户明确指令执行：不做备份，直接清理旧 Git 历史，重建清爽 `main` 基线，防止历史敏感信息后患。

## 执行范围

- 目标工作区：`/home/ubuntu/hcz-deploy`
- 清理对象：该工作区旧 `.git` 历史
- 未处理对象：运行容器、数据库、日志文件、`.env` 实际配置、缓存目录
- 未读取对象：大日志文件

执行前探测到的 HCZ 相关 Git 工作区只有：

```text
/home/ubuntu/hcz-deploy/.git
```

## 执行动作

执行的核心动作：

```bash
rm -rf .git
git init -b main
git add -A
git commit -m "chore(git): rebuild clean main baseline"
```

## 新基线

- 新分支：`main`
- 新提交：`eaad3de8c7b7cf8d89c30ac21043c9cfb21bf4d8`
- 提交信息：`chore(git): rebuild clean main baseline`
- 新仓库提交数：`1`
- 新基线入库文件数：`756`

## 入库排除验收

新基线没有纳入以下高风险运行产物：

- `*.log`
- 根 `.env`
- `.venv`
- `.pytest_cache`
- `node_modules`
- `frontend/dist`
- `data/logs`
- `data/runtime`
- `data/postgres`
- `data/qdrant`
- `data/napcat`
- `data/uploads`

忽略区仍可见但未入库的典型运行文件/目录包括：

```text
.env
.pytest_cache/
.venv/
holo-cortex-zero-main/.venv/
holo-cortex-zero-main/frontend/.env
holo-cortex-zero-main/frontend/dist/
holo-cortex-zero-main/frontend/node_modules/
```

## 结论

本次不是功能修复，而是 Git 历史风险处置。由于旧历史中敏感信息和环境痕迹风险过高，采用直接删除旧 `.git` 并重建 `main` 的方式，避免后续误传播旧提交历史。

回滚点为新根提交：

```text
eaad3de8c7b7cf8d89c30ac21043c9cfb21bf4d8
```
