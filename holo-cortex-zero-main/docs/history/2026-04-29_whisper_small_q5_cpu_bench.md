# hcz Whisper small Q5 CPU 实测

## 环境

- 机器：hcz
- CPU：Intel Core i9-12900K
- 线程：8
- GPU：禁用
- 后端：whisper.cpp
- 模型：Whisper small Q5_1
- 模型大小：189.49 MB
- 测试音频：中文 10s / 30s / 60s wav

## 命令主干

```bash
build/bin/whisper-cli \
  -m models/ggml-small-q5_1.bin \
  -f <wav> \
  -l zh \
  -t 8 \
  -ng \
  -nt
```

## 无 VAD

| 音频 | wall | RTF | 速度 |
|---|---:|---:|---:|
| 10s | 1.37s | 0.137 | 7.30x |
| 30s | 1.43s | 0.048 | 20.98x |
| 60s | 4.13s | 0.069 | 14.53x |

## 当前结论

- 中文文本提取主模型降级为 `Whisper small Q5_1`。
- hcz 8 线程跑 `small Q5_1` 满足常驻 CPU 低延迟。
- 当前默认不启用 VAD。

## 远端日志

- `/path/to/benchmarks/hcz_whisper_turbo_cpu_bench/logs/small_q5_8threads_20260429_125907.log`
