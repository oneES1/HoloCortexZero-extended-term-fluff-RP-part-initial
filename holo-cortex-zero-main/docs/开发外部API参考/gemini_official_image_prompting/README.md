# Google 官方：Gemini / Imagen 图像 Prompt Engineering（离线下载）

下载日期：2026-02-05

说明：本目录仅用于后续优化 `magic_draw` 的提示词方案（photoshop / lightroom 等），文件为网页 HTML 离线保存。

已生成清洗后的 Markdown 版本（更适合本地阅读）：`docs/gemini_official_image_prompting/md/*.md`（文件名与对应 HTML 一致）。

## Gemini API（ai.google.dev）

- `01_ai_google_dev_gemini-api_docs_image-generation.html`
  - https://ai.google.dev/gemini-api/docs/image-generation
- `02_ai_google_dev_gemini-api_docs_imagen-prompt-guide.html`
  - https://ai.google.dev/gemini-api/docs/imagen-prompt-guide
- `03_ai_google_dev_gemini-api_docs_media-resolution.html`
  - https://ai.google.dev/gemini-api/docs/media-resolution
- `04_ai_google_dev_gemini-api_docs_tokens.html`
  - https://ai.google.dev/gemini-api/docs/tokens
- `05_ai_google_dev_gemini-api_docs_prompting-intro.html`
  - https://ai.google.dev/gemini-api/docs/prompting-intro
- `06_ai_google_dev_guide_prompt_best_practices.html`
  - https://ai.google.dev/guide/prompt_best_practices
- `07_ai_google_dev_gemini-api_docs_vision.html`
  - https://ai.google.dev/gemini-api/docs/vision

## Vertex AI（cloud.google.com / docs.cloud.google.com）

- `08_docs_cloud_google_com_vertex-ai_generative-ai_docs_multimodal_image-generation.html`
  - https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/image-generation
- `09_docs_cloud_google_com_vertex-ai_generative-ai_docs_image_img-gen-prompt-guide.html`
  - https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/img-gen-prompt-guide
- `10_docs_cloud_google_com_vertex-ai_generative-ai_docs_image_omit-content-using-a-negative-prompt.html`
  - https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/omit-content-using-a-negative-prompt
- `11_cloud_google_com_vertex-ai_generative-ai_docs_image_use-prompt-rewriter.html`
  - https://cloud.google.com/vertex-ai/generative-ai/docs/image/use-prompt-rewriter
- `12_cloud_google_com_vertex-ai_generative-ai_docs_multimodal_image-understanding.html`
  - https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/image-understanding
- `13_docs_cloud_google_com_vertex-ai_generative-ai_docs_image_subject-customization.html`
  - https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/subject-customization
- `14_docs_cloud_google_com_vertex-ai_generative-ai_docs_model-reference_imagen-api-customization.html`
  - https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/imagen-api-customization

## 建议优先阅读顺序（按“提示词工程”相关度）

1. `09_...img-gen-prompt-guide...`（最直接的提示词/属性指南）
2. `02_...imagen-prompt-guide...`（图像生成提示词总览，含 Gemini Native Image Generation 方向）
3. `01_...image-generation...` / `08_...image-generation...`（图像生成/编辑能力、输入输出约束）
4. `13_...subject-customization...` / `14_...imagen-api-customization...`（参考图/主体一致性/身份保持方向）
5. `03_...media-resolution...` + `04_...tokens...`（解释“图片输入 token 为什么不高/怎么调”）
6. `10_...negative-prompt...` + `11_...prompt-rewriter...`（负面提示与自动改写）
