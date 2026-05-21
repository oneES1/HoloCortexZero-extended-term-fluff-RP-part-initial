# Holo Cortex Zero

HoloCortexZero fluff RP part 是我在本科毕设空闲时间做的项目，是真正HCZ的起步练习作。从26年1月15号左右上线第一版，快速迭代和维护，特点是：

1.只需要18K上下文就可完成至少超过4个月的**无感无缝长期记忆**工程实测验证，内测用户汇报效果超出预期
2.上下文在**多人类用户跨群聊/平台**时仍原生保证连贯；无需担心多群聊私聊并发冲突。无需担心bot不记得刚刚在另一个消息平台的私聊内容
3.支持思维链回填，支持多种缓存协议；缓存率80%～95%，允许随时切换gemini全模态 Deepseek v4 toolcall，responses，chat等发射器协议
4.为长期RP优化记忆：图谱索引+LLM检索+embedding，代码与仲裁LLM结合保证**复杂多用户鲁棒性**
5.配置管理简单；payload框架担保回复可用性。支持原生图片语音交互；tool扩展；支持状态追踪；异常兜底强，报错也继续运行
6智能体协作：主RP发言bot，auto_memory, memory_judge, 检索记忆LLM，自动接话，后台静默压缩（根据TTFT，decode速度，KV缓存，智力，思维链，多模态等特性决定）按需求自动编排并发

表情包由embendding; 语音由embendding+TTS

HoloCortexZero最终目的在以年为单位长程通用的，可自主发现创新，自主产出落地，自主社交规划的基于序列模型搭建的（当前LLM主流阶段）以agentic框架叙述，共4个阶段

前2阶段：1.陪伴型RP框架，起步练手（已完成） 2.打造24小时短期任务的通用思考元认知agentic框架并显著在思考，推理，研究性benchmark超过现有方案

# HoloCortexZero-Metacognition-part-Prose（还未实施的阶段2）
并没有成熟敢宣称最好的方案，方案仍在探索斟酌和调研。目前正在考虑先创建够用的符号工具再后续开发

基本哲学：（不涉及具体设计）
1.**必须隔离分工**必须保证输入输出明确，不能同一上下文有思考与执行或不同任务，隔离，可预测
2.追问本质很重要，对本次任务追问本质是为规划服务，对自己追问本质是给更新skill的LLM群服务，对意义追问本质是自主找方向
3.同步后台分段审查，对大部分智能体进行并行同步分段**审查幻觉编造**幻觉不直接丢弃，而是交给后台联想part并行加工贮存预备。对分段不合格进行回退/并发推演搜索汇总（把推理看作世界线，浅显图像类比费曼路径积分定期测量坍缩）
4.除了“看板”共享，必须有全局监管纠偏，包括协调者也收到监管纠偏，从本质/根本需求审查**防止走歪或走窄**；或许局部TTFT小的模型instant纠偏看情况加入
5.整体test time scale需保守，但并行scale要大要敢大，尽量可控的每一节点在更接近**全局最优**审查通过才往下push，极少返工，不拍脑袋（审查知道薄弱点，隐藏条件，且该审查自己也收到全局纠偏压制局部幻觉），但真要返工时不保守
6.记忆系统多结构需求**针对性优化**不能通用糊弄
7.test time **skill分层快与慢学习与应用**避免token/推理资源浪费，同时固化长期skill习惯，skill相关排布由专门负责，仍然禁止过度污染其他智能体，严格隔离分工
8.联想与记忆的注入非常重要，但具体落实时具体务实分析

# 目录
0.RP part宗旨

1.用户，频道context管理综述

入口消息先由各平台 adapter 收到，再统一进入 `adapters/interface/collector.py`。collector 的第一步不是写库，而是调用 `adapters/interface/identity.py` 做身份归一化：平台侧的原始 user/channel 信息只在适配器边界处理一次，进入框架后统一使用 HCZ 规范化后的 `platform_userid`、`channel_id` 和 `chat_key`。这样后续命令、context 路由、权限、附件策略都只面对框架身份，不再为 QQ、Telegram、Matrix 等来源各写一套主干。

用户与频道是两层持久化对象：

- `DBUser` 记录“谁发的”：`adapter_key + platform_userid` 组成用户唯一来源，另外保存权限、封禁、禁止触发等用户状态。
- `DBChatChannel` 记录“从哪里发的”：`adapter_key + channel_id` 组成物理频道，框架内唯一键是 `chat_key = f"{adapter_key}-{channel_id}"`。
- 新频道默认激活规则在 `DBChatChannel._default_active_for_new_channel`：高级用户私聊恒激活，普通群聊/私聊按配置 `SESSION_GROUP_ACTIVE_DEFAULT`、`SESSION_PRIVATE_ACTIVE_DEFAULT` 决定。

context 管理由 `services/context_window/manager.py` 负责，核心概念是把“对话窗口”和“上下文窗口”解耦：

- 对话窗口 Dialog Window 是物理收发位置，例如 QQ 群、QQ 私聊、TG 私聊。
- 上下文窗口 Context Window 是 AI 实际看到的逻辑上下文，持久化在 `DBContextWindow`。
- 高级用户：`context_id = user_id`，所以高级用户跨群聊、私聊、平台时共享同一个长期上下文。
- 普通用户：`context_id = chat_key`，普通用户的上下文窗口等同当前物理对话窗口。

`DBContextWindow.active_dialog_id` 是当前回复锚点。高级用户在不同窗口触发时，context 不变，但 `active_dialog_id` 会切到最近一次触发的窗口，bot 最终回复也发回这个窗口。`update_anchor()` 明确规定：tool 链运行中 `tool_chain_active=True` 时不允许切换锚点，避免一个长工具任务执行到一半被另一个群聊/私聊抢走回复目标。

聊天消息会先落到 `DBChatMessage`，再由 `sync_new_chat_messages()` 增量投影进 `DBContextMessage`。投影规则有数值边界：只拉当前 dialog 最近 12 小时内的新消息；人类消息默认最多注入 8 条，bot 自己的消息可同步但不占人类注入名额；每个 `(context_id, dialog_chat_key)` 独立保存 `DBContextDialogState.last_synced_db_id` 水位线，避免跨窗口串读。

高级管理命令走 `MessageService`，例如 `/clear` 清当前上下文，`/clearall` 清高级上下文相关记录，`/test` 触发测试，`/norm`、`/cute`、`/puss` 切换高级上下文模式。这些命令是管理入口，不是普通用户能力；普通用户的同名文本不会进入特权控制路径。

2.payload组装，降级，处理路由设计

HCZ 的 payload 主线是“先组装协议无关 IR，再由 router 发射”。`services/context_window/assembler.py` 输出统一的 `GenerationRequest`，里面只有 `MessageTurn`、`MessagePart`、`ToolSpec`、`cache_hints` 等框架内部结构，不直接绑定 OpenAI chat、Responses 或 Gemini 的 wire shape。

主回复请求的组装顺序固定：

- system：主人格 prompt、参考图路径、框架运行声明；tool 通过原生 function calling 下发，不再把 `<tool_call>` 文本协议塞进 system。
- 可选用户轮：系统形象参考图，标明这是框架内置参考，不是聊天消息。
- 压缩上下文：高级 context 注入 timeline 摘要，普通 context 注入较早历史归档。
- 历史消息：从 `DBContextMessage` 读出 user/assistant/tool 序列。
- 回忆与动态指导：长期记忆召回、环境标注、当前时间。
- 最新用户轮：如果历史最后一条是用户消息，会被挪到整个 payload 末尾，保证模型最后看到的仍是最新触发。

`services/llm/router.py` 是 LLM 协议路由唯一主干。它负责 model group 解析、协议识别、媒体策略、缓存 hint 整理、fallback 调用。协议发射器只做最后一公里转换：

- `ResponsesEmitter` 转 `/responses` 请求体。
- `OpenAIChatEmitter` 转 chat completions 请求体。
- `GeminiEmitter` 转 Gemini generateContent/streamGenerateContent 请求体。

fallback 不是重组第二份业务 payload。`LLMRouter.call_with_fallback()` 在主模型组失败后创建新的 `GenerationRequest`，保留同一份 `messages`、`tools`、`temperature`、`max_tokens`、`cache_hints`，只替换 fallback 模型、base url、protocol、proxy、extra params。主模型和 fallback 模型看到的业务语义一致，避免“主链一套逻辑、降级链另一套逻辑”。

降级主要发生在 router 的媒体策略阶段，而不是散落到各 emitter。图片会先按数量限制裁剪，再物化为协议可接受的数据；WEBP 会全局转 JPEG，特定兼容目标下 GIF 会转 PNG。音频/视频按协议能力处理：Gemini 可保留音频/视频；chat/responses 对不支持的媒体降级成文本说明；tool 产生的视频默认只保留最近 1 个候选，内联上限 8MB、60 秒，必要时用 `ffmpeg` 压缩或提取音频预览。

3.长短期记忆与回忆设计

短期记忆就是当前 `DBContextWindow` 下的 `DBContextMessage` 历史。它不是简单复制某个群或私聊的全量聊天记录，而是由当前 context 的 active dialog 增量同步、去重、水位线、历史裁剪、压缩摘要共同维护。高级 context 默认 100 条历史后触发 timeline 压缩，保留最近 10 条；硬读取上限按 1.2 倍冗余计算。普通 context 默认 48 条触发归档回收，保留最近 10 条，并把较早历史整理成归档块。

长期记忆使用 Mem0/Qdrant，collection 固定为 `holo_cortex_zero_memory`。`services/memory/mem0_utils.py` 负责 memory client、embedding、memory 管理模型配置；`services/memory/runtime.py` 负责运行时写入、冲突仲裁、召回拼装；写入走后台队列，属于异步最终一致，不阻塞主回复链。

回忆分三层：

- Stage0 图谱缓存：`graph_cache.py` 从 mem0 中提取关系/概念类记忆，放入内存 LRU；默认 `SUBCONSCIOUS_CACHE_SIZE=15`，写图谱记忆时同步更新缓存。
- Stage1 潜意识路由：`subconscious.py` 读取最近消息、图谱快照和上下文 meta，让辅助 LLM 判断本轮要查哪些意图、是否更新图谱缓存、是否切换 topic mode。
- Stage2 多路召回：Stage1 成功后，并发执行静态画像、context 主查询、intent 查询、第三方关系回退等 mem0 search，再合成最终 memory prompt。

高级用户上下文会固定注入高级用户静态画像，保证长期 RP 的身份连续性；普通用户上下文优先按当前 `context_id/chat_key` 召回，如果主查询缺失或命中不足，会使用静态 fallback，避免空记忆导致回复突然失去背景。

自动记忆由 `services/memory/auto_memory.py` 后台运行，统计 `human_chat` 与 `bot_reply` 两类可计数消息。默认 `AUTO_MEMORY_TRIGGER_MESSAGE_COUNT=10`，达到阈值后构造一个只暴露 `add_memory` tool 的辅助 LLM 请求。只有辅助 LLM 完成审核，或实际执行了 `add_memory`，才推进 `auto_memory_last_context_msg_id` 水位；如果没有成功写入，就保留 pending 状态，下一轮继续尝试。

4.缓存设计，音频视频逻辑

缓存设计同样走统一主干：assembler 只声明语义 hint，router 计算稳定前缀，emitter 再映射到具体协议字段。主回复默认携带：

- `cache_control=ephemeral`
- `stable_prefix=system_first_text`
- `cache_domain=main:{owner_type}:{mode}` 这一类调用方传入的域信息

router 会把结构化请求切成 canonical units，计算稳定前缀 LCP，并维护最多 128 个 prefix snapshot。这样同一 context 的 system/persona/摘要/历史稳定部分可以尽量命中缓存，而最新用户输入仍保持在 payload 末尾。不同供应商的差异被限制在 emitter：Responses 可映射 `cache_control`，chat 可按 cache profile 映射 `cache_control` 或 `prompt_cache_key`，uni-grok 可用 `prompt_cache_key` 兼容，deepseek/local 等按各自能力跳过或调整字段。

附件进入框架前先走 `services/file_system/policy.py`：

- 高级用户附件进入 managed 文件系统，后续可被工具和上下文引用。
- 普通用户图片进入 quarantine 隔离区，默认 48 小时清理，不暴露高级文件路径。
- 普通用户 file/audio/video 默认 disabled，生成文本占位而不是把任意文件交给模型或工具。

音频和视频在 LLM 侧由 router 统一处理。`AI_REPLY_MULTIMODAL_AUDIO_MAX_COUNT` 默认 4，超出数量会降级为文本说明。视频优先按协议能力保留：Gemini 支持的情况下可传视频；不支持时尝试用 `ffmpeg` 提取音频预览；tool 视频候选默认只保留最近 1 个，并受 8MB/60 秒上限约束。`ffprobe` 用于时长探测，`ffmpeg` 用于压缩、转码、音频预览，以及 Telegram 语音输出时的 WAV 到 OGG 转换。

多媒体兜底原则是“降级可读，不打断主链”。图片读取失败、媒体过大、协议不支持、系统工具缺失时，框架会尽量把该媒体替换成明确文本说明，让 LLM 知道这里发生了附件降级，而不是让整次回复报错退出。

5.tool回路设计，内置tool讲解，tool开发介绍

tool 主循环在 `services/tools/chain_executor.py`。它不是一次 LLM 调用后直接结束，而是一个闭环：

- 标记 `DBContextWindow.tool_chain_active=True`，清理当前 context 的 pending human trigger。
- 每轮先同步 active dialog 的新聊天消息，再尝试应用已完成的摘要。
- 重新解析 model group，组装 `GenerationRequest`，调用 `LLMRouter.call_with_fallback()`。
- 如果 LLM 返回纯文本，写入 assistant 历史并发送最终回复。
- 如果 LLM 返回 tool calls，写入 assistant tool_call 记录，逐个交给 registry 执行，再把 tool result 写回历史，继续下一轮。
- 循环停止条件：最多 50 轮 callback，总超时 300 秒，连续 3 次空输出，或进入 side-effect/history-only 完成态。

`tool_chain_active` 是并发保护开关。运行期间新的聊天消息仍会正常落库，下一轮 `sync_new_chat_messages()` 可以吸收；但不会抢占当前 tool 链，也不会切换 `active_dialog_id`。这保证长任务的回复窗口和上下文不会被并发触发打乱。

`services/tools/registry.py` 是 tool 暴露和执行的统一入口。注册时声明名称、schema、scope、capability、config model、是否注入 context、历史写入策略。给 LLM 的 schema 会隐藏宿主参数，例如 `chat_key`、`context_id`、`dialog_chat_key`、`tool_host`、`tool_config`；执行时再由 registry 注入。tool 不存在、权限不足、运行时缺失、参数错误都会被封装成 `ToolResult` 错误，不让主循环直接崩掉。

工具逻辑与宿主能力分层：

- `tool_runtime` 是可迁移工具层，工具函数返回 `ToolOutcome`，不直接依赖 HCZ 数据库。
- `HCZToolHostBridge` 是宿主桥，提供 HTTP 请求、托管文件写入、图片生成、用户查询/屏蔽、文件操作、日志等能力。
- YAML 配置位于 `data/configs/tools/*.yaml`，由配置管理器加载到对应 config model。

当前内置工具类型包括天气查询、联网搜索/seek、magic draw 图像/动图/修图、文件读写与命令型文件操作、用户屏蔽、时间工具、Docker/通用辅助、system moment 相关工具。启动时 `init_new_architecture()` 会先注册 system moment、advanced tools、migrated tools，再初始化 memory、context schema、语音、表情、timeline。

开发新 tool 的推荐路径是：先在 `tool_runtime/tools/` 定义纯工具逻辑和 `ToolOutcome`；声明参数 schema 与配置 model；在 HCZ 注册层绑定 scope/capability/history strategy；把默认配置放进 YAML；最后用真实 `tool_registry.execute(...)` 验证成功、失败、越权、配置缺失四类返回。工具主干应复用 registry/bridge，不要绕开它直接读写业务状态。

6.辅助功能：自动回复，语音，表情包

自动回复服务在 `services/ai_reply/service.py` 和 `MessageService.push_human_message()` 周边工作。私聊可以直接触发；群聊触发来源包括 @/is_tome、人格关键词、随机触发、内容规则，以及 group judge window。group judge window 会持久化到 `APP_SYSTEM_DIR/ai_reply/group_judge_window.json`，在配置的 TTL 内让 LLM 判断是否接话；判断失败按 fail-close 处理，不主动打扰群聊。

高级上下文还支持多模态路由：当输入命中特定多模态条件时，可以临时切到 `MULTIMODAL_MODEL_GROUP`，让图片/音频/视频能力跟随本轮请求，而不是长期污染普通文本主模型组。

语音服务在 `services/system_voice/`。它按配置限制适配器、随机概率、最大短文本长度，再用 embedding 选择合适的 voice guidance/profile，最后通过 DashScope CosyVoice 生成音频。生成结果会落到 `data/system/system_voice/.cache` 复用；Telegram 语音需要时会用 `ffmpeg` 转 OGG。语音发送失败时回退为文本，不影响主回复已经生成的内容。

表情包服务在 `services/system_emoji.py`。启动后扫描 `SYSTEM_EMOJI_HOST_DIR`，从文件名 stem 去掉尾部数字后抽取 tag，按需生成 tag embedding。回复阶段用 bot 文本 embedding 匹配最接近的表情，通常先发送原始文本，再附加图片/文件资源。MIME 不支持、目录为空、embedding 失败、发送失败时都退回纯文本。

这些辅助功能都属于“发送层增强”：主 LLM 回复、记忆、tool 链是主干；自动接话、语音、表情包只在合适时机增强表现力，失败时不得破坏主回复链。

7.兜底处理逻辑

启动期兜底分为 fail-fast 和恢复两类。`run_bot.py`/初始化流程会检查数据库、adapter、新架构组件、系统依赖；`init_new_architecture()` 会先注册 tool，再补 context schema，初始化 memory，清理过期 quarantine，恢复 context window 状态。重启后会释放遗留的 `tool_chain_active`、`summary_generating` 等锁，避免旧进程中断导致新进程一直认为任务还在跑。

LLM 兜底由 router 和 tool executor 共同完成。主模型组异常时记录错误并尝试 fallback；fallback 也失败后抛出 `LLMAPIChainExhaustedError`，用户侧收到明确的“所有 API 模型组均不可用，请稍后再试。”模型组动态解析为空、缺 key、缺模型名时也会返回配置异常文本，而不是静默吞掉。

tool 兜底遵循结构化失败：缺工具、越权、参数错误、runtime 缺失、宿主桥异常都应该变成 tool result 错误，写入上下文后让 LLM 有机会解释或换路。tool 主循环还记录 `DBToolChainTrace`，包括 stop type、LLM 轮次、tool 次数、耗时、token、cache 命中等诊断字段，方便复盘。

输出清理是最后一道安全线。发送前会清理 `<think>`、未执行的 `<tool_call>`/function 残留、旧的 `[id|name]` 前缀、`¥...说：` 内部运行格式、bot 传输路径等内容。若模型把控制面文本当普通回复输出，框架会丢弃这类文本并注入系统警告，强制下一轮重新给自然语言或原生 tool call。

媒体兜底遵循可读替代：附件禁用、隔离、读取失败、超过限制、协议不支持、`ffmpeg/ffprobe` 不存在时，尽量生成文本 placeholder 或降级说明。这样模型仍能知道“用户发了一个无法直接读取的视频/文件”，但不会拿到不该暴露的宿主路径或中断回复。

记忆兜底遵循不推进水位线原则。Stage1 潜意识路由失败时回到 legacy recall；Stage2 某一路 mem0 search 失败时保留其他召回；auto memory 只有在审核完成或 `add_memory` 成功后才推进处理水位。写入失败会留在后台队列/日志中，不把失败伪装成已记住。

8.效果展示

9.开始操作指南

This repository is the Docker-deployable source tree for HCZ. Full project
documentation is still being prepared; deployment guides are available in
[Chinese](README_DEPLOY.md) and [English](README_DEPLOY_EN.md).



## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) and
[NOTICE](NOTICE).

Commercial use, modification, redistribution, and derivative works are allowed
under the license. Please retain attribution to the original HCZ source when
publishing modified, redistributed, or commercial versions.

Initial source attribution: Haicaizi / Holo Cortex Zero.
