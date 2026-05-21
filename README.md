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

2.payload组装，降级，处理路由设计

3.长短期记忆与回忆设计

4.缓存设计，音频视频逻辑

5.tool回路设计，内置tool讲解，tool开发介绍

6.辅助功能：自动回复，语音，表情包

7.兜底处理逻辑

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
