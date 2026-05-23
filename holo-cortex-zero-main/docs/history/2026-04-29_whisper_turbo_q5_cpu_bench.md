# hcz Whisper large-v3-turbo Q5 CPU 实测

## 环境

- 机器：hcz
- CPU：Intel Core i9-12900K
- 线程：8
- GPU：禁用
- 后端：whisper.cpp
- 模型：Whisper large-v3-turbo Q5_0
- 模型大小：573.40 MB
- 测试音频：中文 10s / 30s / 60s wav

## 命令主干

```bash
build/bin/whisper-cli \
  -m models/ggml-large-v3-turbo-q5_0.bin \
  -f <wav> \
  -l zh \
  -t 8 \
  -ng \
  -nt
```

## 无 VAD

| 音频 | wall | RTF | 速度 |
|---|---:|---:|---:|
| 10s | 6.23s | 0.623 | 1.61x |
| 30s | 6.20s | 0.207 | 4.84x |
| 60s | 12.99s | 0.217 | 4.62x |

## ASR 专用 VAD

参数：`--vad -vt 0.25 -vspd 250 -vsd 800 -vp 800`

| 音频 | wall | RTF | 速度 |
|---|---:|---:|---:|
| 10s | 6.95s | 0.695 | 1.44x |
| 30s | 13.39s | 0.446 | 2.24x |
| 60s | 20.24s | 0.337 | 2.96x |

## 当前结论

- hcz 8 线程跑 `large-v3-turbo Q5_0` 可实时以上。
- 当前中文样本近似连续语音，VAD 切段反而变慢。
- 文本提取主干先用无 VAD。
- ASR 专用 VAD 只适合长静音多的语音，不作为默认强制路径。

## 远端日志

- `/path/to/benchmarks/hcz_whisper_turbo_cpu_bench/logs/q5_8threads_20260429_124004.log`
