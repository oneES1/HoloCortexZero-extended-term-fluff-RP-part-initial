# HoloCortexZero-fluff-RP-part-2.3

# 2026.5.22 更新context结构，8K上下文时缓存率达到99%以上，是通用更新；顺便增加deepseek user_id 显式缓存隔离提高稳定性

HoloCortexZero fluff RP part 是我在本科毕设空闲时间做的项目，是真正HCZ的起步练习作。从26年1月15号左右上线第一版，快速迭代和维护，特点是：

- 1.只需要18K上下文就可完成至少超过4个月的**无感无缝长期记忆**工程实测验证，内测用户汇报效果超出预期

- 2.上下文在**多人类用户跨群聊/平台**时仍保证连贯；无需担心多群聊私聊并发冲突。无需担心bot不记得刚刚在另一个消息平台的私聊内容

- 3.支持思维链回填，支持多种缓存协议；缓存率平均98%，允许随时切换各个协议： gemini协议 全模态（图片语音视频），deepseek-v4 toolcall（必须开启回填），responses，chat等发射器协议

- 4.为长期RP优化记忆：图谱索引+LLM检索+embedding，代码与仲裁LLM结合保证**复杂多用户鲁棒性**

- 5.权限严格隔离，且普通用户文件不入库。支持LLM状态追踪；payload框架担保回复可用性；tool可扩展可配置；异常兜底强，报错也继续运行；

- 6智能体协作：主RP发言bot，auto_memory, memory_judge, 检索记忆LLM，自动接话，后台静默压缩（根据TTFT，decode速度，KV缓存，智力，思维链，多模态等特性决定）按需求自动编排并发

## HoloCortexZero最终目的在以年为单位长程通用的，可自主发现创新，自主产出落地，自主社交规划的基于序列模型搭建的（当前LLM主流阶段）以agentic框架叙述，共4个阶段

前2阶段：1.陪伴型RP框架，起步练手（已完成） 2.打造24小时短期任务的通用思考元认知agentic框架并显著在思考，推理，研究性benchmark超过现有方案（即将执行）

# HoloCortexZero-Metacognition-part-Prose（还未实施的阶段2）
并没有成熟敢宣称最好的方案，方案仍在探索斟酌和调研。目前正在考虑先创建够用的符号工具再后续开发

基本哲学：（不涉及具体设计）
- 1.**必须隔离分工**必须保证输入输出明确，不能同一上下文有思考与执行或不同任务，隔离，可预测
- 2.追问本质很重要，对本次任务追问本质是为规划服务，对自己追问本质是给更新skill的LLM群服务，对意义追问本质是自主找方向
- 3.同步后台分段审查，对大部分智能体进行并行同步分段**审查幻觉编造**幻觉不直接丢弃，而是交给后台联想part并行加工贮存预备。对分段不合格进行回退/并发推演搜索汇总
- 4.除了“看板”共享，必须有全局监管纠偏，包括协调者也收到监管纠偏，从本质/根本需求审查**防止走歪或走窄**；或许局部TTFT小的模型instant纠偏看情况加入
- 5.整体test time scale需保守，但并行scale要大要敢大，尽量可控的每一节点在更接近**全局最优**审查通过才往下push，极少返工，不拍脑袋（审查知道薄弱点，隐藏条件，且该审查自己也收到全局纠偏压制局部幻觉），但真要返工时不保守
- 6.记忆系统多结构需求**针对性优化**不能通用糊弄
- 7.test time **skill分层快与慢学习与应用**避免token/推理资源浪费，同时固化长期skill习惯，skill相关排布由专门负责，仍然禁止过度污染其他智能体，严格隔离分工
- 8.联想与记忆的注入非常重要，但具体落实时具体务实分析

## Mac/Win 客户端程序下载地址见：（做好了会在这写）
## Linux源码部署文档：[中文](README_DEPLOY.md) and [English](README_DEPLOY_EN.md).


# 目录
- 0.RP part宗旨：
本框架提供了tool支持，但强烈不建议用RP框架干活，工作与陪伴RP混杂体验不会好，这是一件难度远大于表面的事。必须做事请开发**单个极简tool**召唤subagent或代码逻辑做，保持RP上下文不被琐事和工作情绪污染，刻意不添加skill，MCP等强污染心智内容。时机成熟会在未来阶段4打造RP与干活融合

- 1.用户，频道context管理综述

- 2.payload组装，Prompt配置，降级，处理路由设计

- 3.长短期记忆与回忆设计

- 4.缓存设计，图片降级与缓存关系，音频视频逻辑

- 5.tool回路设计，内置tool讲解，tool开发介绍

- 6.辅助功能：自动回复，语音，表情包

- 7.兜底处理逻辑

- 8.效果展示

- 9.开始操作指南（登录，适配器，LLM，Prompt，设置，验证）

# 架构展开

## 0.RP part宗旨：

本框架提供了tool支持，但强烈不建议用RP框架干活，工作与陪伴RP混杂体验不会好，这是一件难度远大于表面的事。必须做事请开发**单个极简tool**召唤subagent或代码逻辑做，保持RP上下文不被琐事和工作情绪污染，刻意不添加skill，MCP等强污染心智内容。时机成熟会在未来阶段4打造RP与干活融合

## 1.用户，频道context管理综述

context 管理由 `services/context_window/manager.py` 负责，核心概念是把“对话窗口”和“上下文窗口”解耦：

- 对话窗口 Dialog Window 是物理收发位置，例如 QQ 群、QQ 私聊、TG 私聊。
- 上下文窗口 Context Window 是 AI 实际看到的逻辑上下文，持久化在 `DBContextWindow`。
- 高级用户：`context_id = user_id`，所以高级用户跨群聊、私聊、平台时共享同一个长期上下文。
- 普通用户：`context_id = chat_key`，普通用户的上下文窗口等同当前物理对话窗口。

入口消息先由各平台 adapter 收到，再统一进入 `adapters/interface/collector.py`。collector 的第一步不是写库，而是调用 `adapters/interface/identity.py` 做身份归一化：平台侧的原始 user/channel 信息只在适配器边界处理一次，进入框架后统一使用 HCZ 规范化后的 `platform_userid`、`channel_id` 和 `chat_key`。这样后续命令、context 路由、权限、附件策略都只面对框架身份，不再为 QQ、Telegram、Matrix 等来源各写一套主干。

用户与频道是两层持久化对象：

- `DBUser` 记录“谁发的”：`adapter_key + platform_userid` 组成用户唯一来源，另外保存权限、封禁、禁止触发等用户状态。
- `DBChatChannel` 记录“从哪里发的”：`adapter_key + channel_id` 组成物理频道，框架内唯一键是 `chat_key = f"{adapter_key}-{channel_id}"`。
- 新频道默认激活规则在 `DBChatChannel._default_active_for_new_channel`：高级用户私聊恒激活，普通群聊/私聊按配置 `SESSION_GROUP_ACTIVE_DEFAULT`、`SESSION_PRIVATE_ACTIVE_DEFAULT` 决定。

`DBContextWindow.active_dialog_id` 是当前回复锚点。高级用户在不同窗口触发时，context 不变，但 `active_dialog_id` 会切到最近一次触发的窗口，bot 最终回复也发回这个窗口。`update_anchor()` 明确规定：tool 链运行中 `tool_chain_active=True` 时不允许切换锚点，避免一个长工具任务执行到一半被另一个群聊/私聊抢走回复目标。

聊天消息会先落到 `DBChatMessage`，再由 `sync_new_chat_messages()` 增量投影进 `DBContextMessage`。投影规则有数值边界：只拉当前 dialog 最近 12 小时内的新消息；人类消息默认最多注入 8 条，bot 自己的消息可同步但不占人类注入名额；每个 `(context_id, dialog_chat_key)` 独立保存 `DBContextDialogState.last_synced_db_id` 水位线，避免跨窗口串读。

高级管理命令走 `MessageService`，例如 `/clear` 清当前上下文，`/clearall` 清高级上下文相关记录，`/test` 触发测试，`/norm`、`/cute`、`/puss` 切换高级上下文模式。这些命令是管理入口，不是普通用户能力；普通用户的同名文本不会进入特权控制路径。

## 2.payload组装，Prompt配置，降级，处理路由设计

HCZ 的 payload 主线是“先组装协议无关 IR，再由 router 发射”。`services/context_window/assembler.py` 输出统一的 `GenerationRequest`，里面只有 `MessageTurn`、`MessagePart`、`ToolSpec`、`cache_hints` 等框架内部结构，不直接绑定 OpenAI chat、Responses 或 Gemini 的 wire shape。

主回复请求的组装顺序固定：

- system：主人格 prompt、参考图路径、框架运行声明；tool 通过原生 function calling 下发，不再把 `<tool_call>` 文本协议塞进 system。
- 可选用户轮：系统形象参考图，标明这是框架内置参考，不是聊天消息。
- 压缩上下文：高级 context 注入 timeline 摘要，普通 context 注入较早历史归档。
- 历史消息：从 `DBContextMessage` 读出 user/assistant/tool 序列。
- 回忆与动态指导：长期记忆召回、环境标注、当前时间。
- 最新用户轮：如果历史最后一条是用户消息，会被挪到整个 payload 末尾，保证模型最后看到的仍是最新触发。

### Prompt配置、默认身份与运行态覆盖逻辑

Prompt 主干不是散落在各业务文件里的硬编码字符串，而是“默认模板 + 运行态配置覆盖 + 身份渲染”的组合。`core/prompt_defaults.py` 保存开源包自带默认模板；`core/config.py` 暴露 WebUI 提示词页和系统设置页可以保存的配置；主回复、潜意识、auto memory、记忆仲裁、timeline 等链路在组装请求前读取运行态配置，配置为空时才回到默认模板。

默认模板里能看到 `541955254` 和 `海泡菜`，这是故意保留的开源 seed 身份，不是误把作者私有身份写死给所有部署者用。系统设置里的“你自己的统一 ID”和“你对智能体的统一昵称”会覆盖它们：`render_identity_prompt()` 会把默认 prompt 里的 seed ID、seed 昵称和默认 bot 昵称替换成当前运行态配置。这样默认 prompt 能保留完整角色语义，新部署者只要在系统设置里改统一 ID/统一昵称，就不会被作者默认身份污染。

主人格 prompt 按上下文模式解析。普通用户走“普通用户人格”；高级用户 `/norm` 走“群聊里回复你的 norm 人格”；`/cute` 优先走“私聊回复你的 cute 人格”，为空就回退 norm，再回退普通人格；`/puss` 优先走 Pro/deep 人格，配置为空时也逐级回退。每次最终选出的 prompt 都会再经过 `render_identity_prompt()`，所以兜底 prompt 不会绕过身份替换。

辅助 prompt 也走同一套覆盖和兜底逻辑。群聊自动回复 judge 读取 judge prompt，缺失时按 fail-open/fail-close 策略处理；Stage1 潜意识读取潜意识 prompt，空时回默认模板；auto memory 读取自动记忆 prompt，空时回默认模板；记忆仲裁读取仲裁 prompt，模板里的 `{owner_context}`、`{chat_context}`、`{metadata_json}` 是运行时填充占位符，不能删；timeline 读取长对话压缩 prompt，空时回默认模板。这些 prompt 都由提示词页集中配置，不要求用户改源码。

源码里还保留了一次历史配置字段迁移，位置在 `core/config.py` 的 `CoreConfig._migrate_legacy_prompt_fields()`。它只处理历史字段 `AI_CHAT_PRESET_NAME` 和 `AI_CHAT_PRESET_SETTING`：如果新的人格昵称、普通人格、高级人格、deep 人格 prompt 为空，才把历史字段填进去；已有新配置不会被覆盖。也就是说，代码里保留默认 seed、运行态配置覆盖、历史字段迁移和 prompt 兜底都服务于同一条 prompt 主干，不制造第二套 prompt 路由。

`services/llm/router.py` 是 LLM 协议路由唯一主干。它负责 model group 解析、协议识别、媒体策略、缓存 hint 整理、fallback 调用。协议发射器只做最后一公里转换：

- `ResponsesEmitter` 转 `/responses` 请求体。
- `OpenAIChatEmitter` 转 chat completions 请求体。
- `GeminiEmitter` 转 Gemini generateContent/streamGenerateContent 请求体。

fallback 不是重组第二份业务 payload。`LLMRouter.call_with_fallback()` 在主模型组失败后创建新的 `GenerationRequest`，保留同一份 `messages`、`tools`、`temperature`、`max_tokens`、`cache_hints`，只替换 fallback 模型、base url、protocol、proxy、extra params。主模型和 fallback 模型看到的业务语义一致，避免“主链一套逻辑、降级链另一套逻辑”。

### 思维链回填逻辑

思维链回填不是默认泄露模型思考，而是模型组显式能力。`ModelConfigGroup.REPLAY_REASONING_CONTENT` 默认 `false`；只有开启后，`model_group_params.py` 才会向本轮 `GenerationRequest.extra_params` 注入 `replay_reasoning_content=true`。router 以这个字段作为唯一 gate：未开启时，即使供应商返回 `reasoning_content`、Responses `reasoning` item、Gemini `thoughtSignature` 或文本里的 `<think>...</think>`，也会在 `_filter_result_reasoning_content()` 阶段丢弃，不进入历史回放闭环。

IR 主干只承认一个字段：`MessageTurn.reasoning_content` / `GenerationResult.reasoning_content`。不同协议的隐藏思考不会直接互塞 wire 字段，而是由 `services/llm/reasoning_text.py` 统一包成 HCZ envelope：`text` 保存可跨 chat/responses 兜底复用的隐藏思考，`responses_items` 保存 Responses 原生 `reasoning` output item，`gemini_thought_signatures` 保存 Gemini tool 续链需要的签名。旧纯文本、旧 Responses JSON、旧 Gemini JSON 都在解析层兼容读取。

模型返回后，chat emitter 从 `message.reasoning_content` 读取，Responses emitter 从 `output[type=reasoning]` 读取，Gemini emitter 从 tool call part 的 `thoughtSignature` 读取；如果隐藏思考混在可见文本里，`extract_text_reasoning_content()` 会先把 `<think>` 形态剥离成 `reasoning_content`，再让干净的可见文本进入 tool 解析、用户回复和上下文保存。

tool 链持久化时，assistant 纯文本回复会把隐藏思考写到 meta-only `tool_calls_json=[{"_hcz_meta":{"reasoning_content":...}}]`；assistant tool_calls 会把隐藏思考写到第一个 tool call 的 `_hcz_meta.reasoning_content`。恢复历史时 `context_window/manager.py` 只把这段 meta 还原为 `MessageTurn.reasoning_content`，不会把 meta-only 记录误解析成伪 tool_call。

发送下一轮 tool 续链前，`LLMRouter._ensure_reasoning_replay_for_tool_calls()` 会检查 function-call 历史段：如果模型组开启回填，所有 assistant tool-call 历史都必须有非空 `reasoning_content`；缺失真实思维链时写入最小占位，已有真实思维链绝不覆盖。最终各 emitter 按协议回放：chat 写 assistant `reasoning_content`，Responses 优先回放原生 `reasoning` item、只有 text 时才用 `<think>...</think>` assistant history，Gemini 只回放 `thoughtSignature`，没有签名不伪造。

降级主要发生在 router 的媒体策略阶段，而不是散落到各 emitter。图片会先按数量限制裁剪，再物化为协议可接受的数据；WEBP 会全局转 JPEG，特定兼容目标下 GIF 会转 PNG。音频/视频按协议能力处理：Gemini 可保留音频/视频；chat/responses 对不支持的媒体降级成文本说明；tool 产生的视频默认只保留最近 1 个候选，内联上限 8MB、60 秒，必要时用 `ffmpeg` 压缩或提取音频预览。

## 3.长短期记忆与回忆设计

短期记忆就是当前 `DBContextWindow` 下的 `DBContextMessage` 历史。它不是简单复制某个群或私聊的全量聊天记录，而是由当前 context 的 active dialog 增量同步、去重、水位线、历史裁剪、压缩摘要共同维护。高级 context 默认 100 条历史后触发 timeline 压缩，保留最近 10 条；硬读取上限按 1.2 倍冗余计算，冗余触顶但仍未完成压缩会变成滑动窗口。普通 context 默认 48 条触发归档回收，保留最近 10 条，并把较早历史整理成归档块。

长期记忆使用 Mem0/Qdrant，collection 固定为 `holo_cortex_zero_memory`。`services/memory/mem0_utils.py` 负责 memory client、embedding、memory 管理模型配置；`services/memory/runtime.py` 负责运行时写入、冲突仲裁、召回拼装；写入走后台队列，属于并行异步最终一致，不阻塞主回复链。

### 记忆写入仲裁

所有 `add_memory` 写入先进入 `_memory_write_queue`，由后台 worker 调 `_add_memory_impl()` 执行。入队前会把 memory 清洗为最长 2000 字的纯文本形态，并清洗 metadata；空 memory 或空 user_id 直接忽略。真正入库时关闭 mem0 自带 infer 拆解，HCZ 自己负责“原子化输入 + 仲裁 + 写入”，避免 mem0 推理分支把事实拆错或触发版本兼容问题。

仲裁前先用新记忆在同一个 `user_id/agent_id/run_id` 下做 mem0 search，`limit=24`；代码层只把 `score >= 0.74` 的候选送入冲突判断。没有候选时直接 ADD。存在候选时，`analyze_memory_conflict()` 调用配置的 `MEMORY_MANAGE_MODEL`，使用 `MEMORY_ARBITER_SYSTEM_PROMPT` 构造“**写入归属 + 对话环境** + metadata + 现有记忆 + 新记忆”的仲裁请求，要求只返回 JSON：`action`、`targets`、`new_content`、`reason`。

仲裁动作只有三种：`ADD` 表示新事实独立入库；`UPDATE` 表示删除 `targets` 指向的旧记忆，再把 `new_content` 作为合并/修正后的新记忆写入；`REJECT` 表示重复、低价值、主体不清或不该保存的内容被拒绝。非法 action 会归一为 ADD；仲裁模型配置缺失、无返回、JSON 解析失败或调用异常，也全部 fail-soft 为 ADD，保证记忆写入链不断。

图谱类记忆有代码级保护，不完全信任仲裁 LLM。metadata `type/TYPE` 属于 `relation_map`、`knowledge_index` 等图谱写入时，禁止 REJECT；若同 alias/keyword 命中旧记录，会优先收敛为 UPDATE，保证 Stage0 图谱缓存和冷启动恢复需要的映射能落库。每次 ADD/UPDATE 后，如果 `SUBCONSCIOUS_ENABLE=true`，都会对 `graph_cache.write_through_from_memory(metadata)` 做写穿更新；写穿失败只记日志，不影响主写入结果。

仲裁过程会通过 `dump_memory_json("manage", "request/response", ...)` 留下请求、候选、metadata、owner_context、chat_context、模型协议、原始响应与 parsed_result，方便复盘“为什么 ADD/UPDATE/REJECT”。这部分是可调试证据，不参与主回复 payload。

回忆分三层：

- Stage0 图谱缓存：`graph_cache.py` 从 mem0 中提取关系/概念类记忆，放入内存 LRU；默认 `SUBCONSCIOUS_CACHE_SIZE=15`，写图谱记忆时同步更新缓存。
- Stage1 潜意识路由：`subconscious.py` 读取最近消息、图谱快照和上下文 meta，让辅助 LLM 判断本轮要查哪些意图、是否更新图谱缓存。
- Stage2 多路召回：Stage1 成功后，并发执行静态画像、context 主查询、intent 查询、第三方关系回退等 mem0 search，再合成最终 memory prompt。

高级用户上下文会固定注入高级用户静态画像，保证长期 RP 的身份连续性；普通用户上下文优先按当前 `context_id/chat_key` 召回，如果主查询缺失或命中不足，会使用静态 fallback，避免空记忆导致回复突然失去背景。

### 自动记忆 auto_memory

自动记忆由 `services/memory/auto_memory.py` 后台运行，是“静默审阅上下文并决定是否写长期记忆”的辅助链，不直接参与主回复。启动时会自补 `DBContextWindow` 上的 `auto_memory_last_context_msg_id`、`auto_memory_pending_count`、`auto_memory_generating` 三列，并在恢复阶段重新计算 pending、清掉遗留 generating 锁，避免重启后卡死。

触发统计只看同一 `context_id` 下的 `DBContextMessage`，不按 `chat_key/source_chat_key` 分桶；`chat_key` 只用于写入时标注来源环境。可计数类型固定为 `human_chat` 与 `bot_reply`，角色只接受 `user/assistant`。默认 `AUTO_MEMORY_TRIGGER_MESSAGE_COUNT=10`，达到阈值后 `_query_batch_upper_bound_id()` 取“自上次水位后的第 N 条可计数消息”作为本批上界，保证每批有明确可回滚水位。

单次 auto_memory 默认只给辅助 LLM 看最近 `AUTO_MEMORY_RECENT_MESSAGE_COUNT=10` 条上下文消息，可复用主链最近一次 recall 快照；没有 recall 快照时也允许运行，只是不带回忆提示。请求使用独立 `AUTO_MEMORY_MODEL_GROUP`，`context_id="aux:auto_memory"`，`temperature=0.1`，`stream=false`，只暴露一个 `add_memory` tool；`parallel_tool_calls=false`，`AUTO_MEMORY_TOOL_CHOICE` 默认 `auto`，不默认强制 `required`。

辅助 LLM 的合法行为只有两种：调用 `add_memory` 写入少量高价值记忆，或保持沉默表示本批已审阅但无可写内容。单轮最多执行 `AUTO_MEMORY_MAX_TOOL_CALLS=8` 个 tool call；非 `add_memory` tool 会被忽略。每个有效 tool call 会解析 `memory/user_id/metadata`，用当前批次来源 `dialog_chat_key` 构造 `AgentCtx`，再进入正常 `add_memory -> 记忆仲裁 -> mem0 写入` 主干。

水位推进很严格：如果模型没有产出 tool_call，表示“审阅完成但无可写记忆”，会推进到本批上界；如果执行了至少 1 个 `add_memory`，也推进到本批上界；如果返回了 tool_calls 但没有成功执行任何 `add_memory`，不推进水位，保留 pending 让后续重试。每次完成后重新计算 pending；如果剩余 pending 仍达到阈值，会自动链式触发下一批。

auto_memory 会通过 `dump_memory_json("auto_memory", "request/response/tool_call", ...)` 保存请求 wire payload、上下文源消息、recall_text、模型返回、执行过的 tool calls 和 resolved env。`AUTO_MEMORY_DEBUG_LOG_PAYLOAD=true` 时还会打印截断预览，默认日志上限 `AUTO_MEMORY_PAYLOAD_LOG_MAX_CHARS=12000`。这些证据只用于调试，不进入主聊天 payload。

## 4.缓存设计，图片降级与缓存关系，音频视频逻辑

缓存设计同样走统一主干：assembler 只声明语义 hint，router 计算稳定前缀，emitter 再映射到具体协议字段。主回复默认携带：

- `cache_control=ephemeral`
- `stable_prefix=system_first_text`
- `cache_domain=main:{owner_type}:{mode}` 这一类调用方传入的域信息

router 会把结构化请求切成 canonical units，计算稳定前缀 LCP，并维护最多 128 个 prefix snapshot。这样同一 context 的 system/persona/摘要/历史稳定部分可以尽量命中缓存，而最新用户输入仍保持在 payload 末尾。不同供应商的差异被限制在 emitter：Responses 可映射 `cache_control`，chat 可按 cache profile 映射 `cache_control` 或 `prompt_cache_key`，uni-grok 可用 `prompt_cache_key` 兼容，deepseek/local 等按各自能力跳过或调整字段。

### 图片降级与缓存关系

图片降级发生在缓存计算前，不是 emitter 临时拼协议时才处理。`LLMRouter.generate()` 和 `generate_stream()` 都先跑 `_prepare_request()`，在这里完成 `IMAGE_MAX_COUNT` 数量限制、单图内联 `25_000_000 bytes` 上限检查、远程/本地图片物化、WEBP -> JPEG、uni-grok GIF -> PNG 兼容；随后才进入 `_apply_canonical_cache_prefix_hints()` 计算 canonical LCP 和 prefix snapshot，最后交给 emitter 序列化。

因此缓存绑定的是“模型实际看到的后策略 IR”，不是原始附件状态。超出数量、读不到、超过 `25_000_000 bytes` 或格式兼容失败的图片，会先变成 `[图片...降级]` 文本 part；这些文本 part 会正常进入 canonical units。相同历史在“图片仍保留”和“图片已降级”两种状态下不应共用缓存，因为模型看到的上下文已经不同；反过来，重复出现的同一降级结果可以命中稳定前缀，避免缓存被不稳定 URL、过大原图字节或 emitter 差异污染。

图片限额分两层：`IMAGE_MAX_COUNT` 只管每次请求送入模型的 user 图片数量，正数限额下内置系统形象参考图优先保留，普通图片按从旧到新降级；单图字节由 router 的 `25_000_000 bytes` 内联上限兜底。接收/适配器层还有 `MAX_UPLOAD_SIZE_MB=10` 这类上传限制，但主回复缓存只认 router 处理后的 `GenerationRequest`。

附件进入框架前先走 `services/file_system/policy.py`：

- 高级用户附件进入 managed 文件系统，后续可被工具和上下文引用。
- 普通用户图片进入 quarantine 隔离区，默认 48 小时清理，不暴露高级文件路径。
- 普通用户 file/audio/video 默认 disabled，生成文本占位而不是把任意文件交给模型或工具。

音频和视频在 LLM 侧由 router 统一处理。`AI_REPLY_MULTIMODAL_AUDIO_MAX_COUNT` 默认 4，超出数量会降级为文本说明。视频优先按协议能力保留：Gemini 支持的情况下可传视频；不支持时尝试用 `ffmpeg` 提取音频预览；tool 视频候选默认只保留最近 1 个，并受 8MB/60 秒上限约束。`ffprobe` 用于时长探测，`ffmpeg` 用于压缩、转码、音频预览，以及 Telegram 语音输出时的 WAV 到 OGG 转换。

多媒体兜底原则是“降级可读，不打断主链”。图片读取失败、媒体过大、协议不支持、系统工具缺失时，框架会尽量把该媒体替换成明确文本说明，让 LLM 知道这里发生了附件降级，而不是让整次回复报错退出。

## 5.tool回路设计，内置tool讲解，tool开发介绍

tool 主循环在 `services/tools/chain_executor.py`。它不是一次 LLM 调用后直接结束，而是一个闭环：

- 标记 `DBContextWindow.tool_chain_active=True`，清理当前 context 的 pending human trigger，也就是
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

## 6.辅助功能：自动回复，语音，表情包

自动回复服务在 `services/ai_reply/service.py` 和 `MessageService.push_human_message()` 周边工作。私聊可以直接触发；群聊触发来源包括 @/is_tome、人格关键词、随机触发、内容规则，以及 group judge window。group judge window 会持久化到 `APP_SYSTEM_DIR/ai_reply/group_judge_window.json`，在配置的 TTL 内让 LLM 判断是否接话；判断失败按 fail-close 处理，不主动打扰群聊。

高级上下文还支持多模态路由：当输入命中特定多模态条件时，可以临时切到 `MULTIMODAL_MODEL_GROUP`，让图片/音频/视频能力跟随本轮请求，而不是长期污染普通文本主模型组。

语音服务在 `services/system_voice/`。它按配置限制适配器、随机概率、最大短文本长度，再用 embedding 选择合适的 voice guidance/profile，最后通过 DashScope CosyVoice 生成音频。生成结果会落到 `data/system/system_voice/.cache` 复用；Telegram 语音需要时会用 `ffmpeg` 转 OGG。语音发送失败时回退为文本，不影响主回复已经生成的内容。

表情包服务在 `services/system_emoji.py`。启动后扫描 `SYSTEM_EMOJI_HOST_DIR`，从文件名 stem 去掉尾部数字后抽取 tag，按需生成 tag embedding。回复阶段用 bot 文本 embedding 匹配最接近的表情，通常先发送原始文本，再附加图片/文件资源。MIME 不支持、目录为空、embedding 失败、发送失败时都退回纯文本。

这些辅助功能都属于“发送层增强”：主 LLM 回复、记忆、tool 链是主干；自动接话、语音、表情包只在合适时机增强表现力，失败时不得破坏主回复链。

## 7.兜底处理逻辑

启动期兜底分为 fail-fast 和恢复两类。`run_bot.py`/初始化流程会检查数据库、adapter、新架构组件、系统依赖；`init_new_architecture()` 会先注册 tool，再补 context schema，初始化 memory，清理过期 quarantine，恢复 context window 状态。重启后会释放遗留的 `tool_chain_active`、`summary_generating` 等锁，避免旧进程中断导致新进程一直认为任务还在跑。

LLM 兜底由 router 和 tool executor 共同完成。主模型组异常时记录错误并尝试 fallback；fallback 也失败后抛出 `LLMAPIChainExhaustedError`，用户侧收到明确的“所有 API 模型组均不可用，请稍后再试。”模型组动态解析为空、缺 key、缺模型名时也会返回配置异常文本，而不是静默吞掉。

tool 兜底遵循结构化失败：缺工具、越权、参数错误、runtime 缺失、宿主桥异常都应该变成 tool result 错误，写入上下文后让 LLM 有机会解释或换路。tool 主循环还记录 `DBToolChainTrace`，包括 stop type、LLM 轮次、tool 次数、耗时、token、cache 命中等诊断字段，方便复盘。

输出清理是最后一道安全线。发送前会清理 `<think>`、未执行的 `<tool_call>`/function 残留、旧的 `[id|name]` 前缀、`¥...说：` 内部运行格式、bot 传输路径等内容。若模型把控制面文本当普通回复输出，框架会丢弃这类文本并注入系统警告，强制下一轮重新给自然语言或原生 tool call。

媒体兜底遵循可读替代：附件禁用、隔离、读取失败、超过限制、协议不支持、`ffmpeg/ffprobe` 不存在时，尽量生成文本 placeholder 或降级说明。这样模型仍能知道“用户发了一个无法直接读取的视频/文件”，但不会拿到不该暴露的宿主路径或中断回复。

记忆兜底遵循不推进水位线原则。Stage1 潜意识路由失败时回到 legacy recall；Stage2 某一路 mem0 search 失败时保留其他召回；auto memory 只有在审核完成或 `add_memory` 成功后才推进处理水位。写入失败会留在后台队列/日志中，不把失败伪装成已记住。

## 8.效果展示

### 记忆效果演示

“男娘”与巧克力的玩笑，喜欢讲地狱笑话的用户画像长期持久记忆。

![记忆效果演示 1](img/memory1.png)

![记忆效果演示 2](img/memory2.png)

### 群聊自主回复与语音

群聊自主回复演示，附带语音发送效果。

![群聊自主回复演示](img/auto_reply.png)

![语音演示](img/voice.png)

### 工具可用性

![工具调用演示 1](img/tool1.png)

![工具调用演示 2](img/tool2.png)

### LLM 踪迹追踪

![LLM 踪迹追踪](img/trace.png)

## 9.开始操作指南

本节只讲 Docker 部署已经启动后的 WebUI 配置顺序；首次安装、端口、密码生成、数据目录和离线发布包仍看 `README_DEPLOY.md`。bilibili 视频教学如果后续补，会放在这里。

### 9.0 登录与配置入口

WebUI 登录使用 `.env` 里的 `HCZ_ADMIN_USERNAME` 和 `HCZ_ADMIN_PASSWORD`；安装脚本会生成或要求设置强密码，容器入口会拒绝空值、`change_me_*` 和 `123456` 这类公开弱默认。登录后左上角 Logo / 顶部导航可进入配置区，主要关注三块：消息平台适配器、LLM、系统设置。

配置保存后，不是所有字段都需要重启。一般 LLM 和系统运行配置可直接保存后测试；适配器凭证、Bot Token、QQ/NapCat 登录状态、Telegram 代理这类初始化参数，保存后如果页面提示或适配器仍未初始化，就只重启 HCZ 后端本体，不要重建数据库/Qdrant。

### 9.1 适配器

配置好你要用的适配器就行，不用就不管
适配器只负责平台接入与平台侧身份声明，不决定最终上下文主键。必须先分清两个 ID：

- 你的平台用户 ID（高级用户）
- 智能体/机器人自己的平台账号：QQ/OneBot 填 `BOT_QQ`，Telegram 填 `BOT_TOKEN` 对应的 Bot，Matrix 填机器人 Matrix 账号与 token/password。

常用适配器检查点：

- OneBot/QQ：进入 `onebot_v11` 适配器，配置 `BOT_QQ`、`你的ID`，再处理 NapCat 登录
- Telegram：配置 `BOT_TOKEN`、`你的ID`，必要时填 `PROXY_URL`
- Matrix：配置机器人账号/token/password 与 `你的ID`

首次接入建议先让目标平台账号给 bot 发一条普通消息，让系统创建。然后到监控里的**聊天频道**列表确认消息可入库，绿色意味着打开了消息服务

### 9.2 LLM

LLM 页面就是“模型供应商配置”。新手先不要管所有高级项，按下面顺序填到能测试通过：

- 先起一个好认的 LLM 名字，例如“主聊天模型”“记忆向量模型”“画图模型”。
- 模型类型要选对：聊天用 `chat`，记忆/表情/语音匹配用 `embedding`，绘图用 `draw`。
- 填模型名称、API 地址、API Key；连不通时基本先查这三项。
- 如果访问供应商需要代理，优先打开“启用全局代理”；只有这个 LLM 要特殊代理时，再单独填聊天模型访问代理。
- 协议发射器新手保持默认；明确知道供应商必须走 `chat`、`responses` 或 `gemini` 时再手动指定。

建议先建一个能正常回复的聊天 LLM，再建一个能正常返回向量的 embedding LLM。记忆检索强依赖 embedding LLM；不配置或维度不匹配时，长期记忆、表情匹配、语音 guidance 匹配都会受影响。记忆嵌入维度默认 1024，必须和实际 embedding 模型输出维度一致。

如果要完整使用记忆、自动接话、自动记忆、语音和表情，LLM 页面建议至少准备这些模型名字，后面系统设置会用下拉框引用它们：

- 主聊天模型：类型选 `chat`，用于日常直接回复。
- 备用聊天模型：类型选 `chat`，主聊天模型失败时兜底。
- 辅助小模型：类型选 `chat`，用于群聊回复判断、潜意识路由、记忆整理、自动记忆、Timeline 压缩；可以和主聊天模型复用，但更推荐用便宜稳定的小模型。
- 记忆向量模型：类型选 `embedding`，用于长期记忆检索，也可以给语音和表情匹配复用。
- 多模态模型：类型选 `chat`，协议发射器明确走 Gemini 类全模态协议时，用来承载音频、视频和强图片理解。
- 绘图模型：类型选 `draw`，只有使用绘图工具时才需要。

模型连不通时，优先检查 API 地址、API Key、模型名称、代理和协议。DeepSeek 这类会返回 `reasoning_content` 且参与 tool 链的思考模型，需要在该 LLM 上开启“回放思维链”，否则后续 tool 请求可能丢失必要的思维链回填；不明确支持该能力的模型不要随手开启。

图片相关配置分两层看，新手主要改界面里的“图片数量上限”：

- “图片数量上限”是单次请求送给模型的用户图片数量；空表示不限，0 表示不发图，正整数表示超出部分按从旧到新降级为文本。
- 单图字节上限由 router 兜底为 `25_000_000 bytes`；上传入口还可能受 `MAX_UPLOAD_SIZE_MB=10` 影响。

如果某个供应商在图片上下文中频繁失败，先把该 LLM 的“图片数量上限”调小，而不是改代码。图片降级发生在缓存计算前，降级后的文本说明会参与 canonical cache，因此“图片保留”和“图片降级”不会误共用缓存。

“额外参数 (JSON)”适合放供应商特有字段；先用最小字段跑通连通性，再逐项加入。“缓存传输策略”只控制 cache hint 如何映射到协议字段，不改变主 payload 组装语义。

### 9.3 系统设置

系统设置里先配置“你是谁”。这里的“你”是高级用户，也就是长期陪伴/RP 的主用户：

- “对智能体的统一 ID 标识”：填一个稳定 ID。它会成为高级上下文的长期记忆锚点，不要今天填 QQ 号、明天填 TG 号来回换。
- “你对智能体的统一昵称”：填 bot 在 prompt、附件提示、身份纠偏里称呼你的名字。
- 消息平台里的“你的 ID”要在适配器页填；系统设置里的统一 ID 是 HCZ 内部长期上下文身份。两者可以映射，但不是同一个配置位。

然后配置“谁来回复”。这些都是下拉选择前面 LLM 页面里已经建好的模型：

- “群聊里回复你的 LLM”：你在群里触发，或发送 `/norm` 后使用的主模型。
- “私聊回复你的 LLM”：你在私聊触发，或发送 `/cute` 后使用的模型；不填就回退到群聊主模型。
- “你专用的高级 LLM”：发送 `/puss` 后使用的 Pro/deep 模型。
- “回复其他人的 LLM”：普通用户触发时使用的模型。
- “备用 LLM”：主模型失败时自动切过去的兜底模型。
- “多模态 LLM”：处理音频、视频更强的**Gemini发射器协议**全模态模型。

再配置“后台辅助 LLM”。这些模型不直接和用户聊天，但会决定记忆、自动接话、语音和表情是否完整工作：

- “群聊回复判断 LLM”：普通群聊里判断“这句话该不该接”。只影响普通群聊，私聊和高级用户触发不靠它。
- “Timeline 压缩 LLM”：长上下文摘要压缩专用。这里必须显式选一个有效聊天 LLM；不选就不会启用 timeline 压缩。
- “记忆管理模型”：记忆写入前做整理、冲突仲裁、合并旧记忆。要开长期记忆就必须配。
- “记忆向量嵌入模型”：把记忆文本转成向量用于检索。要和“记忆嵌入维度”匹配，维度不对时 Qdrant 检索会异常。
- “潜意识 LLM”：Stage1 回忆路由，负责判断本轮应该去记忆里查谁、查什么。要用新的潜意识召回就配它。推荐用doubao-mini,如果总是降级就加容忍秒数，可能是你的模型太慢了
- “自动记忆 LLM”：后台累计到阈值后，自动判断哪些聊天值得调用 `add_memory` 写入。开启自动记忆时必须配。
- “系统表情嵌入模型”：把回复文本和表情包文件名标签做语义匹配。可以直接复用记忆向量模型。
- “系统语音嵌入模型”：给语音 guidance 做语义匹配。可以直接复用记忆向量模型。

辅助 LLM 不是越强越好。回复判断、潜意识、auto memory、记忆仲裁更看重稳定 JSON、稳定 tool call 和低延迟；embedding 模型更看重维度固定、服务稳定。先用少量模型复用跑通，等主链稳定后再拆成不同供应商。


### Prompt 也值得你单独配置，不然bot身份，昵称不明朗

提示词页优先填“主人格”相关内容：智能体昵称、群聊回复你的 norm 人格、私聊回复你的 cute 人格、`/puss` 的 Pro 人格、普通用户人格。先把这些写成符合你角色设定的版本，再配辅助链 prompt。

如果提示词里看到默认示例 ID 或昵称，不需要手动全局搜索替换；系统设置里的统一 ID 和统一昵称会在运行时做身份替换。

不要把工作流、tool 使用规则、记忆仲裁规则全部塞进主人格 prompt；tool、记忆、judge、timeline 已经有各自 prompt，混在一起会污染 RP 主上下文，也会降低缓存稳定性。记忆仲裁 prompt 这类模板如果看到 `{owner_context}`、`{chat_context}`、`{metadata_json}` 这种占位符，不要删。

### 其他小功能

语音和表情是发送层增强，失败不会破坏主回复链，但也请配置来获得完整体验

工具页面单独配置工具。天气、seek 搜索、magic draw、文件操作、屏蔽用户、Docker/系统辅助等工具都有自己的 schema、权限 scope 和 API key；工具配置缺失时应返回结构化错误，不应让主回复链崩溃。

### 9.4 验证顺序

推荐按这个顺序验证：

1. LLM 页面保存一个 `chat` LLM，点连通性测试，确认返回正常。
2. LLM 页面保存一个 `embedding` LLM，然后在系统设置里把“记忆向量嵌入模型”选成它。
3. 系统设置里填你的统一 ID、统一昵称，并选择“群聊里回复你的 LLM”“回复其他人的 LLM”“备用 LLM”。
4. 系统设置里继续选择辅助 LLM：记忆管理、记忆向量、潜意识、自动记忆、Timeline 压缩；要用群聊自动接话、语音、表情时，再补对应 judge/embedding 模型。
5. 提示词页先填主人格 prompt：高级 norm/cute/deep、普通用户 prompt，以及智能体昵称。
6. 配好一个消息平台适配器，让你的真实平台账号先私聊 bot 一句，确认用户和频道被创建。
7. 到监控里的聊天频道列表确认该频道是开启状态。
8. 私聊发送普通文本测试主回复；群聊先用 @ 或触发词测试，不要一开始依赖随机回复。
9. 再测图片；如果失败，先调该 LLM 的“图片数量上限”，再检查模型是否支持图像协议。
10. 最后测试自动记忆、语音、表情包和工具。

排错优先级：

- 没有入库：查适配器凭证、Bot 是否在线、平台是否真的把消息送到适配器。
- 入库但不回复：查聊天频道是否开启、用户是否被封禁/禁止触发、群聊触发条件、tool 链是否正在运行。
- 回复报模型错误：查 LLM 连通性、协议、API key、代理、图片数量上限、是否误开/漏开“回放思维链”。
- 人设不对或模式错乱：查提示词页的智能体昵称、群聊/私聊/Pro/普通用户人格，再查 `/norm`、`/cute`、`/puss` 当前模式和 LLM 路由。
- 记忆不生效：查记忆向量嵌入模型、向量维度、Qdrant、auto_memory 水位和记忆仲裁日志。
- 记忆写入奇怪：查自动记忆 prompt 和记忆仲裁 prompt，确认仲裁模板占位符没有被删。
- 语音/表情不生效：查对应开关、概率、embedding LLM、表情目录、CosyVoice key，以及当前适配器是否在允许列表内。

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) and
[NOTICE](NOTICE).

Commercial use, modification, redistribution, and derivative works are allowed
under the license. Please retain attribution to the original HCZ source when
publishing modified, redistributed, or commercial versions.

Initial source attribution: Haicaizi / Holo Cortex Zero.
