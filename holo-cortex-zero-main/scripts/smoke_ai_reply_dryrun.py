from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from holo_cortex_zero.core import config
from holo_cortex_zero.schemas.ir import GenerationRequest, MessagePart, MessageTurn
from holo_cortex_zero.services.ai_reply import system_ai_reply_service
from holo_cortex_zero.services.llm.router import llm_router


REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_CONTEXT_ID = "10001"


def _default_output_dir() -> Path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    return REPO_ROOT / "stage1_smoke" / f"ai_reply_dryrun_{ts}"


def _serialize_request(request: GenerationRequest) -> Dict[str, Any]:
    return {
        "context_id": request.context_id,
        "model": request.model,
        "messages": [
            {
                "role": turn.role,
                "name": turn.name,
                "tool_call_id": turn.tool_call_id,
                "parts": [
                    {
                        "type": part.type,
                        "text": part.text,
                        "url": part.url,
                        "mime_type": part.mime_type,
                        "data_len": len(part.data) if part.data is not None else 0,
                    }
                    for part in turn.parts
                ],
            }
            for turn in request.messages
        ],
        "extra_params": dict(request.extra_params),
    }


async def _run_reply_case(case_name: str, current_text: str, history_lines: List[str]) -> Dict[str, Any]:
    system_prompt = str(getattr(config, "AI_REPLY_JUDGE_SYSTEM_PROMPT", "") or "").strip()
    judge_meta = {
        "judge_mode": "implicit_group_reply_check",
        "chat_type": "group",
        "chat_key": "dryrun-group",
        "current_sender_id": "42",
        "current_sender_name": "阿青",
        "history_source": "same_chat_plaintext_only_before_current",
        "history_message_count": len(history_lines),
    }
    payload = system_ai_reply_service._build_reply_judge_messages(system_prompt, judge_meta, history_lines, current_text)  # noqa: SLF001
    result: Dict[str, Any] = {
        "case": case_name,
        "history_lines": history_lines,
        "current_text": current_text,
        "payload": payload,
    }

    if not system_prompt:
        result["skipped"] = "missing_system_prompt"
        return result

    decision = await system_ai_reply_service._call_reply_judge_llm(  # noqa: SLF001
        model_group_name=str(getattr(config, "AI_REPLY_JUDGE_MODEL_GROUP", "default") or "default"),
        messages=payload,
        timeout_seconds=int(getattr(config, "AI_REPLY_JUDGE_TIMEOUT_SECONDS", 12) or 12),
    )
    result["decision"] = asdict(decision)
    return result


async def _run_media_case(audio_path: str, video_path: str) -> Dict[str, Any]:
    request = GenerationRequest(
        context_id=TEST_CONTEXT_ID,
        model="dryrun-gemini",
        messages=[
            MessageTurn(
                role="user",
                parts=[
                    MessagePart(type="text", text="测试多模态媒体预处理"),
                    MessagePart(type="text", text=f"测试用户发送 {audio_path}"),
                    MessagePart(type="audio", url=audio_path, mime_type="audio/mpeg"),
                    MessagePart(type="text", text=f"测试用户发送 {video_path}"),
                    MessagePart(type="video", url=video_path, mime_type="video/mp4"),
                ],
            ),
        ],
        stream=False,
    )
    prepared = await llm_router._prepare_request(  # noqa: SLF001
        request,
        protocol="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        proxy=None,
        timeout=60.0,
    )
    return {
        "before": _serialize_request(request),
        "after": _serialize_request(prepared),
    }


async def amain() -> int:
    parser = argparse.ArgumentParser(description="ai_reply 系统化 dry-run（不触发真实群聊）")
    parser.add_argument("--output-dir", default=str(_default_output_dir()), help="产物输出目录")
    parser.add_argument("--reply-false-text", default="路过说一句今晚吃什么", help="普通群聊 should_reply=false 候选文本")
    parser.add_argument("--reply-true-text", default="海菜子，这个报错你帮我看看怎么修", help="普通群聊 should_reply=true 候选文本")
    parser.add_argument("--audio-path", default="", help="可选：本地音频路径，用于媒体预处理 dry-run")
    parser.add_argument("--video-path", default="", help="可选：本地视频路径，用于媒体预处理 dry-run")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    history_lines = [
        "[03-27 22:40:00] user(42|阿青): 我们晚点排查群里的缓存问题",
        "[03-27 22:40:08] bot(-1|海菜子): 好的，我会先看主链日志和请求结构",
        "[03-27 22:40:20] user(43|路人甲): 这两天 TTFT 似乎偏高",
    ]

    summary: Dict[str, Any] = {
        "reply_false": await _run_reply_case("reply_false", str(args.reply_false_text or "").strip(), history_lines),
        "reply_true": await _run_reply_case("reply_true", str(args.reply_true_text or "").strip(), history_lines),
        "multimodal_regex": {
            "patterns": list(getattr(config, "AI_REPLY_MULTIMODAL_TRIGGER_PATTERNS", []) or []),
            "texts": [
                "我刚发了语音你按语音内容继续干活",
                "等会按音频里的要求修代码",
                "这个视频里有我要的内容",
            ],
        },
    }
    matched_pattern = system_ai_reply_service._match_multimodal_regex(  # noqa: SLF001
        summary["multimodal_regex"]["patterns"],
        summary["multimodal_regex"]["texts"],
    )
    summary["multimodal_regex"]["matched_pattern"] = matched_pattern
    summary["multimodal_regex"]["should_route_multimodal"] = bool(matched_pattern)

    audio_path = str(args.audio_path or "").strip()
    video_path = str(args.video_path or "").strip()
    if audio_path and video_path and Path(audio_path).exists() and Path(video_path).exists():
        summary["media_prepare"] = await _run_media_case(audio_path, video_path)
    else:
        summary["media_prepare"] = {
            "skipped": True,
            "reason": "audio/video path missing",
            "audio_path": audio_path,
            "video_path": video_path,
        }

    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir), "summary": str(output_dir / 'summary.json')}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
