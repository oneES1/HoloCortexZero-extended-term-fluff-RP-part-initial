# magic_draw markdown spec runner

## 本次目的

把现有 `scripts/validate_magic_draw_real_tool.py` 扩成可吃 markdown 需求文件的真实 tool 验证入口，并在 Codex skill 层补一个宿主机 wrapper，方便后续围绕 prompt 做可复现迭代。

## 真实主干保持不变

- 真实执行仍然走 `tool_registry.execute(...)`
- 真实宿主仍然走 `HCZToolHostBridge`
- 真实 payload 预览仍然走 `OpenAIChatEmitter`
- 没有复制一份并行业务 tool

## 本次改动

### `scripts/validate_magic_draw_real_tool.py`

新增 markdown spec 支持：

- 支持 YAML front matter
- 支持 fenced YAML block
- 支持一行简写 fallback
- 宿主机 `/path/to<CONTAINER_WORKSPACE_DIR>/...` 输入路径会映射到容器 `<CONTAINER_WORKSPACE_DIR>/...`
- `--spec-md` 模式下只执行 spec 对应的单个 tool，并把解析结果写入 `summary.json`

### `~/.codex/skills/hcz-magic-draw-markdown-runner`

新增一个 Codex skill：

- 宿主机读取任意 markdown spec 路径
- 复制 spec 到 repo `stage1_smoke/.../request.md`
- 进入真实容器 `holo_cortex_zero`
- 调用 repo 内的 `scripts/validate_magic_draw_real_tool.py --spec-md ...`

## 适用场景

用于 Photoshop / Lightroom / GIF 生成 prompt 微调时，保证“你看到的效果”就是框架内真实 tool 跑出来的结果，而不是外部脚本另起炉灶。
