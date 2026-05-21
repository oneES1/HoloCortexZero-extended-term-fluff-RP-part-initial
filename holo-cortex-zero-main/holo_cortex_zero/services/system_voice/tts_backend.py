from __future__ import annotations

import asyncio
import hashlib
import importlib
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.os_env import OsEnv

from .guidance import SAFE_FALLBACK_INSTRUCTION, normalize_instruction
from .text import sanitize_voice_text


@dataclass(frozen=True)
class TTSResult:
    file_path: Path
    instruction: str
    voice: str


_voice_bg_semaphore: asyncio.Semaphore | None = None
_voice_bg_semaphore_loop: asyncio.AbstractEventLoop | None = None


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _cache_dir() -> Path:
    path = Path(OsEnv.DATA_DIR) / "system" / "system_voice" / ".cache"
    _ensure_dir(path)
    return path


def _get_voice_bg_semaphore() -> asyncio.Semaphore:
    global _voice_bg_semaphore, _voice_bg_semaphore_loop
    loop = asyncio.get_running_loop()
    limit = max(int(config.SYSTEM_VOICE_MAX_BG_CONCURRENCY or 2), 1)
    if _voice_bg_semaphore is None or _voice_bg_semaphore_loop is not loop:
        _voice_bg_semaphore = asyncio.Semaphore(limit)
        _voice_bg_semaphore_loop = loop
    return _voice_bg_semaphore


def _write_binary_file(path: Path, payload: bytes) -> None:
    _ensure_dir(path.parent)
    path.write_bytes(payload)


def _write_wav_pcm16_mono(path: Path, pcm: bytes, *, sample_rate: int) -> None:
    _ensure_dir(path.parent)
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(int(sample_rate))
        writer.writeframes(pcm)


def _run_ffmpeg(args: list[str]) -> None:
    subprocess.run(args, check=True, capture_output=True, text=True)


async def _to_thread(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


async def _convert_audio_ffmpeg(src: Path, dst: Path, *, kind: str) -> None:
    _ensure_dir(dst.parent)
    if kind != "telegram_voice_ogg":
        raise ValueError(f"unsupported voice convert kind: {kind}")
    args = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-vn",
        "-ac",
        "1",
        "-c:a",
        "libopus",
        "-b:a",
        "32k",
        str(dst),
    ]
    await _to_thread(_run_ffmpeg, args)


def _parse_language_hints(value: str) -> list[str] | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    hints = [item.strip() for item in raw.split(",") if item.strip()]
    return hints or None


def _build_instruction(instruction: str) -> str:
    prefix = str(config.SYSTEM_VOICE_INSTRUCTION_PREFIX or "").strip()
    if not prefix:
        return instruction
    merged = f"{prefix}\n{instruction}".strip()
    return merged[:299].rstrip() + "…" if len(merged) > 300 else merged


async def synthesize_voice(text: str, *, instruction: str, adapter_key: str) -> TTSResult:
    normalized_text = sanitize_voice_text(text)
    if not normalized_text:
        raise RuntimeError("system_voice 合成文本为空")

    api_key = str(config.SYSTEM_VOICE_API_KEY or "").strip()
    model = str(config.SYSTEM_VOICE_MODEL or "").strip()
    voice = str(config.SYSTEM_VOICE_DEFAULT_VOICE_ID or "").strip()
    ws_url = str(config.SYSTEM_VOICE_WS_URL or "").strip()
    sample_rate = int(config.SYSTEM_VOICE_SAMPLE_RATE or 24000)
    timeout_ms = int(config.SYSTEM_VOICE_TIMEOUT_MS or 120000)
    speech_rate = float(config.SYSTEM_VOICE_SPEECH_RATE or 1.1)
    pitch_rate = float(config.SYSTEM_VOICE_PITCH_RATE or 1.02)
    language_hints = _parse_language_hints(str(config.SYSTEM_VOICE_LANGUAGE_HINTS or ""))
    final_instruction = _build_instruction(normalize_instruction(instruction, source="runtime"))

    if not api_key:
        raise RuntimeError("SYSTEM_VOICE_API_KEY 未配置")
    if not model:
        raise RuntimeError("SYSTEM_VOICE_MODEL 未配置")
    if not voice:
        raise RuntimeError("SYSTEM_VOICE_DEFAULT_VOICE_ID 未配置")

    cache_src = (
        f"{model}|{voice}|{final_instruction}|{speech_rate}|{pitch_rate}|{language_hints}|"
        f"{sample_rate}|{timeout_ms}|{ws_url}|{normalized_text}|{adapter_key}"
    )
    cache_key = hashlib.sha256(cache_src.encode("utf-8")).hexdigest()[:32]
    wav_dir = _cache_dir() / "cosyvoice"
    _ensure_dir(wav_dir)
    wav_path = wav_dir / f"{cache_key}.wav"

    async with _get_voice_bg_semaphore():
        if not wav_path.exists():
            try:
                importlib.import_module("dashscope")
                import dashscope  # type: ignore
                from dashscope.audio.tts_v2 import AudioFormat, SpeechSynthesizer  # type: ignore
            except ImportError as e:
                raise RuntimeError("system_voice 依赖 dashscope，当前环境未安装") from e

            dashscope.api_key = api_key

            def _synthesize_once(active_instruction: str | None) -> bytes:
                synthesizer = SpeechSynthesizer(
                    model=model,
                    voice=voice,
                    format=AudioFormat.WAV_24000HZ_MONO_16BIT,
                    instruction=active_instruction,
                    speech_rate=speech_rate,
                    pitch_rate=pitch_rate,
                    language_hints=language_hints,
                    url=ws_url or None,
                )
                try:
                    audio_bytes = synthesizer.call(normalized_text, timeout_millis=timeout_ms)
                    return bytes(audio_bytes or b"")
                finally:
                    try:
                        synthesizer.close()
                    except Exception:
                        pass

            attempts = [final_instruction]
            if final_instruction != SAFE_FALLBACK_INSTRUCTION:
                attempts.append(SAFE_FALLBACK_INSTRUCTION)
            attempts.append(None)

            audio = b""
            last_error: Exception | None = None
            used_instruction = final_instruction
            for candidate in attempts:
                try:
                    audio = await _to_thread(_synthesize_once, candidate)
                except Exception as e:
                    last_error = e
                    logger.warning(f"system_voice CosyVoice 合成失败，重试下一候选: instruction={candidate!r} err={e}")
                    continue
                if audio:
                    used_instruction = candidate or ""
                    break

            if not audio and last_error is not None:
                raise RuntimeError(f"system_voice CosyVoice 合成失败: {last_error}") from last_error
            if not audio:
                raise RuntimeError("system_voice CosyVoice 未返回音频")

            if audio[:4] == b"RIFF":
                await _to_thread(_write_binary_file, wav_path, audio)
            else:
                await _to_thread(_write_wav_pcm16_mono, wav_path, audio, sample_rate=sample_rate)
            final_instruction = used_instruction

        if adapter_key != "telegram":
            return TTSResult(file_path=wav_path, instruction=final_instruction, voice=voice)

        converted_dir = _cache_dir() / "converted" / adapter_key
        _ensure_dir(converted_dir)
        ogg_path = converted_dir / f"{wav_path.stem}.ogg"
        if not ogg_path.exists():
            try:
                await _convert_audio_ffmpeg(wav_path, ogg_path, kind="telegram_voice_ogg")
            except Exception as e:
                logger.warning(f"system_voice Telegram 语音转码失败，降级使用 WAV: {e}")
                return TTSResult(file_path=wav_path, instruction=final_instruction, voice=voice)
        return TTSResult(file_path=ogg_path, instruction=final_instruction, voice=voice)
