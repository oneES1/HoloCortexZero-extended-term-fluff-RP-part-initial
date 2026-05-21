# 2026-04-03 导出包脱敏加固

## 背景
- 当前仓库支持打 Docker 部署源码包，但原流程会把 `holo-cortex-zero-main/docs/` 与部分非部署脚本一并打包。
- 这些内容中存在开发运维痕迹、主机信息与不应对外分享的命令示例，容易在二次分发时泄露环境细节。

## 本次最小修改
- 收紧 `make_docker_release_bundle.sh`：导出时删除 `holo-cortex-zero-main/docs/`。
- 收紧 `make_docker_release_bundle.sh`：导出时删除 `scripts/hcz_qwen35/` 与 smoke/dev/一次性运维脚本。
- 收紧 `make_docker_release_bundle.sh`：导出时不再包含 `self_image/`，避免打包私人照片与自设图素材。
- 扩展压缩包校验规则：若导出包仍包含上述高风险路径则直接失败。
- 调整 `.env.share.example`：把数据库密码改为纯占位值，并补出空的 `QDRANT_API_KEY` 键。
- 更新 `README_DEPLOY.md`：明确接收方必须重填口令，并增加分享前自检命令。

## 影响
- 导出包仍可用于 Docker 部署。
- 默认产物现在直接落到 `${TMPDIR:-/tmp}/`，不再额外套一层输出子目录。
- 导出包不再携带内部开发文档、高风险基础设施脚本，以及 `self_image/` 私人照片素材。
- 接收方需要自行填写口令，不再能直接沿用示例值。

## 回滚点
- 若要恢复旧行为，可回退本次提交，或手动撤销 `make_docker_release_bundle.sh`、`.env.share.example`、`README_DEPLOY.md` 的改动。
