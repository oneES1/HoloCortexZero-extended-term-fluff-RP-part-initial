# 2026-04-01 system_emoji 宿主资源目录修复

## 问题
- 运行日志出现：`system_emoji 当前宿主机目录无可用资源，跳过`
- 实际宿主目录 `/path/to/runtime-data/system/emoji` 中已有资源文件

## 根因
- 当前配置将 `SYSTEM_EMOJI_HOST_DIR` 指向 `<CONTAINER_WORKSPACE_DIR>/emoji`
- 容器内该路径是软链接，目标为宿主绝对路径 `/path/to/runtime-data/system/emoji`
- 该宿主绝对路径并未以同路径挂进容器，导致容器内看到的是断链
- 真正可见且已有资源的路径是 `<CONTAINER_DATA_DIR>/system/emoji`

## 最小修复
- 仅修改运行配置：
  - `SYSTEM_EMOJI_HOST_DIR: <CONTAINER_WORKSPACE_DIR>/emoji`
  - 改为 `SYSTEM_EMOJI_HOST_DIR: <CONTAINER_DATA_DIR>/system/emoji`
- 仅最小重建 `holo_cortex_zero`

## 验证
- 容器内 `<CONTAINER_DATA_DIR>/system/emoji` 文件数大于 0
- `SystemEmojiService` 初始化后 `host_dir=<CONTAINER_DATA_DIR>/system/emoji`
- `tag_to_paths` 标签数大于 0
- 不再因空库命中 `reason=empty_library`
