# photoshop bot 可见提示语最小纠偏

## 本次目的

纠正上一笔误改，恢复 `PHOTOSHOP_DESCRIPTION` 原文，只修改正确的一处：`mode` 参数描述。

## 修改点

文件：`tool_runtime/tools/magic_draw.py`

本次实际改动只有一处：

- `mode` 参数描述改为明确区分：
  - `photo` 用于真实照片编辑/合成
  - `illustration` 用于虚拟创作用图

同时说明：

- “最多支持 3 张参考图”原本已经由 `image_paths` 的 `0~3 张参考图` 描述承载
- 代码本身也已有 `>3` 直接报错的硬限制
- 因此这次不再扩散修改其它描述字段

## 纠偏说明

上一笔误把边界提示写进了 `PHOTOSHOP_DESCRIPTION`。

本次已恢复该字段原文，避免把本应属于参数说明的语义扩散到整体 tool 描述里。
