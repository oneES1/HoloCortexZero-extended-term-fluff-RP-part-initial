# hcz 中文转写 Benchmark 汇总

## 权威中文 ASR Benchmark

来源：FunAudioLLM technical report Table 6。

| 数据集 | 语言 | 指标 | SenseVoice-Small | Whisper-Small | Whisper-Large-V3 | Paraformer-Large |
|---|---|---|---:|---:|---:|---:|
| AISHELL-1 test | Mandarin | CER | 2.96 | 10.04 | 5.14 | 1.95 |
| AISHELL-2 test ios | Mandarin | CER | 3.80 | 8.78 | 4.96 | 2.85 |
| WenetSpeech test meeting | Mandarin | CER | 7.44 | 25.62 | 18.87 | 6.97 |
| WenetSpeech test net | Mandarin | CER | 7.84 | 16.66 | 10.48 | 6.74 |
| CommonVoice zh-CN | Chinese | CER | 10.78 | 19.60 | 12.55 | 10.30 |

## 权威延迟 Benchmark

来源：FunAudioLLM technical report Table 7。

| 模型 | 参数 | RTF | 10s 延迟 |
|---|---:|---:|---:|
| SenseVoice-Small | 234M | 0.007 | 70ms |
| Whisper-Small | 224M | 0.042 | 518ms |
| Whisper-Large-V3 | 1550M | 0.111 | 1281ms |

## 工程可部署版本

| 模型 | 权重 | 量化/格式 | CPU 后端 |
|---|---|---|---|
| SenseVoice-Small | 公开 | INT8 ONNX | sherpa-onnx |
| Whisper small | 公开 | Q5_1 | whisper.cpp |
| Whisper large-v3-turbo | 公开 | Q5_0 | whisper.cpp |

## 环境

- 机器：hcz
- CPU：Intel Core i9-12900K
- 线程：8
- GPU：禁用
- 音频：中文 wav，10s / 30s / 60s

## 速度

| 模型 | 后端 | 量化 | 10s | 30s | 60s |
|---|---|---|---:|---:|---:|
| SenseVoice-Small | sherpa-onnx | INT8 | 79.36ms | 223.38ms | 812.71ms |
| Whisper small | whisper.cpp | Q5_1 | 1.37s | 1.43s | 4.13s |
| Whisper large-v3-turbo | whisper.cpp | Q5_0 | 6.23s | 6.20s | 12.99s |

## RTF

| 模型 | 10s | 30s | 60s |
|---|---:|---:|---:|
| SenseVoice-Small INT8 | 0.0079 | 0.0074 | 0.0135 |
| Whisper small Q5_1 | 0.137 | 0.048 | 0.069 |
| Whisper large-v3-turbo Q5_0 | 0.623 | 0.207 | 0.217 |

## 转写输出

| 模型 | 10s |
|---|---|
| SenseVoice-Small INT8 | 开放时间早上9点至下午5点开放时间早上9点至下午。 |
| Whisper small Q5_1 | 开放时间早上9点至下午5点。 |
| Whisper large-v3-turbo Q5_0 | 开放时间早上9点至下午5点开放时间早上9点至下午5点 |

| 模型 | 30s |
|---|---|
| SenseVoice-Small INT8 | 开放时间早上9点至下午5点开放时间上9点至下午5点开放时间早上9点至下午5点开放时间上9点至下午5点开放时间早上9点至下午5点开放时间。 |
| Whisper small Q5_1 | 开放时间早上九点至下午五点 |
| Whisper large-v3-turbo Q5_0 | 开放时间早上9点至下午5点 |

| 模型 | 60s |
|---|---|
| SenseVoice-Small INT8 | 开放时间早上9点至下午5点开放时间早上9点至下午5点开放时间早上9点至下午5点开放时间上9点至下午5点开放时间早上9点至下午5点开放时间早上9点至下午5点开放时间上9点至下午5点开放时间早上9点至下午5点开放时间上9点至下午5点开放时间早上9点至下午5点开放时间早上9点至下。 |
| Whisper small Q5_1 | 开放时间早上九点至下午五点开放时间早上九点至下午五点 |
| Whisper large-v3-turbo Q5_0 | 开放时间早上9点至下午5点开放时间早上9点至下午5点 |

## 严格准确率：单条原始中文样本

- 样本：`zh.wav`
- 参考文本：`开放时间早上9点至下午5点`
- 内容 CER：去除标点和空白；保留 `9/5` 与 `九/五` 差异。
- 数字归一 CER：去除标点和空白；`九/五` 归一为 `9/5`。

| 模型 | 输出 | 内容 CER | 数字归一 CER |
|---|---|---:|---:|
| SenseVoice-Small INT8 | 开放时间早上9点至下午5点。 | 0.00% | 0.00% |
| Whisper small Q5_1 | 开放时间早上九点至下午五点。 | 15.38% | 0.00% |
| Whisper large-v3-turbo Q5_0 | 开放时间早上九点至下午五点 | 15.38% | 0.00% |

## 数据来源

- SenseVoice：`/path/to/benchmarks/hcz_sensevoice_cpu_bench/logs/bench_threads_8_10s_20runs.json`
- SenseVoice：`/path/to/benchmarks/hcz_sensevoice_cpu_bench/logs/bench_threads_8_30s.json`
- SenseVoice：`/path/to/benchmarks/hcz_sensevoice_cpu_bench/logs/bench_threads_8_60s.json`
- Whisper small：`/path/to/benchmarks/hcz_whisper_turbo_cpu_bench/logs/small_q5_8threads_20260429_125907.log`
- Whisper turbo：`/path/to/benchmarks/hcz_whisper_turbo_cpu_bench/logs/q5_8threads_20260429_124004.log`
- 原始样本准确率：`/path/to/benchmarks/hcz_whisper_turbo_cpu_bench/logs/zh_asr_accuracy_20260429_141624.txt`

## 事实结论

- 主线确认：中文转写使用 SenseVoice-Small INT8 ONNX。
- 权威中文 ASR benchmark：Paraformer-Large 在列出的中文数据集上 CER 最低，但不作为本系统主线。
- 权威中文 ASR benchmark：SenseVoice-Small 在列出的中文数据集上均优于 Whisper-Small 与 Whisper-Large-V3。
- 权威延迟 benchmark：SenseVoice-Small RTF 低于 Whisper-Small 与 Whisper-Large-V3。
- hcz 实测速度：SenseVoice-Small INT8 最快。
- 工程决策依据：统一 ASR/SER/AED 多任务能力、INT8 ONNX CPU 常驻部署、低延迟。
- 10s 输出完整性：Whisper small 少重复，SenseVoice 和 Whisper turbo 保留重复。
- 30s / 60s 输出完整性：SenseVoice 保留最多重复内容；Whisper small 和 Whisper turbo 明显压缩重复内容。
- 当前样本是重复短句拼接，不足以判定真实口语 WER。
- 当前只有 `zh.wav` 有明确参考文本；严格准确率结论只覆盖该单条样本。

## 权威来源

- FunAudioLLM technical report：`https://fun-audio-llm.github.io/pdf/FunAudioLLM.pdf`
- SenseVoice GitHub：`https://github.com/FunAudioLLM/SenseVoice`
- sherpa-onnx SenseVoice：`https://k2-fsa.github.io/sherpa/onnx/sense-voice/pretrained.html`
