# 2026-04-01 workspace 路径规范化

## 本次收口
- 自设图唯一真相：`<CONTAINER_WORKSPACE_DIR>/self_image`
- emoji 对外路径：`<CONTAINER_WORKSPACE_DIR>/emoji`
- 高级用户媒体提示：`海泡菜发送 <CONTAINER_WORKSPACE_DIR>/...`
- 普通用户媒体提示：`{发送者}发送的图/音频/视频/文件`

## 代码调整
- `holo_cortex_zero/services/agent/run_agent_v2.py`
  - 自设图参考路径只导出纯路径行
- `holo_cortex_zero/services/context_window/manager.py`
  - 媒体注入文本收口为最小口径
  - 高级用户仅暴露 `<CONTAINER_WORKSPACE_DIR>/...`
  - 普通用户不暴露路径
  - 音频 / 视频继续保留本地文件、远端 URL、字节态三条主干
- `holo_cortex_zero/services/ai_reply/service.py`
  - 回复判断过滤新媒体提示格式
- `holo_cortex_zero/services/llm/responses.py`
  - 历史图片降级文本不再带本地绝对路径

## 运行态同步
- `srv/holo_cortex_zero/configs/holo-cortex-zero.yaml`
  - `SELF_IMAGE_*_PATH` 去掉 `assets/`
  - `SYSTEM_EMOJI_HOST_DIR` 改为 `<CONTAINER_WORKSPACE_DIR>/emoji`
- `self_image/`
  - 仓库根保留四张自设图，供容器内 `<CONTAINER_WORKSPACE_DIR>/self_image` 直接使用

## 清理结果
- 自设图目录：`<CONTAINER_WORKSPACE_DIR>/self_image`
- emoji 目录：`<CONTAINER_WORKSPACE_DIR>/emoji`
- 普通用户媒体提示不含路径
