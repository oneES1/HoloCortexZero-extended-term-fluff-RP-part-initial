from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw
import yaml

import nonebot

nonebot.init()

from holo_cortex_zero.schemas.ir import MessageTurn, ToolCall
from holo_cortex_zero.services.llm.openai_chat import OpenAIChatEmitter
from holo_cortex_zero.services.tools.migrated import register_migrated_tools
from holo_cortex_zero.services.tools.registry import ToolRuntimeBinding, tool_registry


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = REPO_ROOT.parent
HOST_WORKSPACE_ROOT = Path(os.environ.get("HCZ_HOST_WORKSPACE_ROOT") or WORKSPACE_ROOT).expanduser().resolve()
EXPECTED_MANAGED_ROOT = "/workspace/draw"
CONTAINER_WORKSPACE_ROOT = Path("/workspace")


def _default_output_dir() -> Path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    return REPO_ROOT / "stage1_smoke" / f"magic_draw_real_tool_{ts}"


_TOOL_CASES: Dict[str, Dict[str, Any]] = {
    "gif_generation": {
        "content": "一个绿色小史莱姆左右弹跳并眨眼的循环动画",
        "style": "pixel art",
        "transparent_background": False,
    },
    "photoshop": {
        "prompt": "基于原图做轻微照片级润色，提亮肤色和层次，保持人物身份完全不变",
        "aspect_ratio": "1:1",
        "mode": "photo",
    },
    "lightroom": {
        "prompt": "轻微提亮曝光，校正白平衡，提升对比和清晰度，保持人物身份完全不变",
    },
}


def _host_path_to_container_path(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return value
    if value.startswith(("http://", "https://", "data:")):
        return value
    if value.startswith(f"{CONTAINER_WORKSPACE_ROOT}/"):
        return value
    host_root = str(HOST_WORKSPACE_ROOT)
    if value == host_root or value.startswith(f"{host_root}/"):
        suffix = value[len(host_root) :].lstrip("/")
        return str(CONTAINER_WORKSPACE_ROOT / suffix) if suffix else str(CONTAINER_WORKSPACE_ROOT)
    return value


def _as_str_list(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _extract_front_matter(markdown_text: str) -> Tuple[Dict[str, Any], str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", markdown_text, flags=re.DOTALL)
    if not match:
        return {}, markdown_text
    payload = yaml.safe_load(match.group(1)) or {}
    if not isinstance(payload, dict):
        raise ValueError("markdown front matter 必须是对象")
    return payload, markdown_text[match.end() :]


def _extract_yaml_block(markdown_text: str) -> Dict[str, Any]:
    match = re.search(r"```(?:yaml|yml)\s*\n(.*?)\n```", markdown_text, flags=re.DOTALL | re.IGNORECASE)
    if not match:
        return {}
    payload = yaml.safe_load(match.group(1)) or {}
    if not isinstance(payload, dict):
        raise ValueError("markdown yaml 代码块必须是对象")
    return payload


def _pick_field(payload: Dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
    return None


def _normalize_tool_args(tool_name: str, payload: Dict[str, Any], fallback_text: str) -> Dict[str, Any]:
    body_text = "\n".join(line.strip() for line in fallback_text.splitlines() if line.strip()).strip()
    if tool_name == "photoshop":
        prompt = str(_pick_field(payload, "prompt", "instruction", "content", "需求") or body_text).strip()
        image_paths = _as_str_list(_pick_field(payload, "image_paths", "images", "refs"))
        if not image_paths:
            single_path = str(_pick_field(payload, "image_path", "image", "path") or "").strip()
            if single_path:
                image_paths = [single_path]
        if not prompt:
            raise ValueError("photoshop spec 缺少 prompt")
        tool_args: Dict[str, Any] = {
            "prompt": prompt,
            "image_paths": [_host_path_to_container_path(item) for item in image_paths],
        }
        aspect_ratio = str(_pick_field(payload, "aspect_ratio", "ratio", "比例") or "").strip()
        if aspect_ratio:
            tool_args["aspect_ratio"] = aspect_ratio
        mode = str(_pick_field(payload, "mode", "render_mode", "风格模式") or "").strip()
        if mode:
            tool_args["mode"] = mode
        return tool_args

    if tool_name == "lightroom":
        prompt = str(_pick_field(payload, "prompt", "instruction", "content", "需求") or body_text).strip()
        image_ref = str(_pick_field(payload, "image_path_or_url", "image_path", "image", "path") or "").strip()
        if not prompt:
            raise ValueError("lightroom spec 缺少 prompt")
        if not image_ref:
            raise ValueError("lightroom spec 缺少 image_path_or_url")
        return {
            "prompt": prompt,
            "image_path_or_url": _host_path_to_container_path(image_ref),
        }

    if tool_name == "gif_generation":
        content = str(_pick_field(payload, "content", "prompt", "instruction", "需求") or body_text).strip()
        if not content:
            raise ValueError("gif_generation spec 缺少 content")
        reference_images = []
        for item in _pick_field(payload, "reference_images") or []:
            if not isinstance(item, dict):
                continue
            image_path = str(item.get("image_path") or item.get("image") or "").strip()
            if not image_path:
                continue
            reference_images.append(
                {
                    "image_path": _host_path_to_container_path(image_path),
                    "description": str(item.get("description") or "").strip(),
                }
            )
        tool_args = {
            "content": content,
            "style": str(_pick_field(payload, "style") or "pixel art").strip() or "pixel art",
            "transparent_background": bool(_pick_field(payload, "transparent_background") or False),
        }
        if reference_images:
            tool_args["reference_images"] = reference_images
        return tool_args

    raise ValueError(f"暂不支持的 tool: {tool_name}")


def _parse_simple_markdown_spec(markdown_text: str) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    compact = " ".join(line.strip() for line in markdown_text.splitlines() if line.strip())
    tool_name = ""
    lower_compact = compact.lower()
    for candidate in ("photoshop", "lightroom", "gif_generation"):
        if candidate in lower_compact:
            tool_name = candidate
            break
    if not tool_name:
        raise ValueError("markdown 简写 spec 未识别到 tool，请显式写 tool: photoshop/lightroom/gif_generation")

    path_match = re.search(
        r"(/[^\s,，。；;:'\"`(){}\[\]<>]+?\.(?:png|jpg|jpeg|webp|gif|bmp|tiff|tif))",
        compact,
        flags=re.IGNORECASE,
    )
    first_path = str(path_match.group(1) if path_match else "").strip()

    prompt = re.sub(tool_name, "", compact, flags=re.IGNORECASE).strip()
    if first_path:
        prompt = prompt.replace(first_path, " ").strip()
    prompt = re.sub(r"^(绘制|画|做|处理|修图|编辑)", "", prompt).strip()
    prompt = re.sub(r"^[为把将对基于按用]\s*", "", prompt).strip()
    prompt = re.sub(r"\s+", " ", prompt).strip()
    prompt = prompt or compact

    spec_payload: Dict[str, Any] = {"tool": tool_name, "prompt": prompt}
    ratio_match = re.search(r"(\d+\s*[:：xX×]\s*\d+)", compact)
    if ratio_match:
        spec_payload["aspect_ratio"] = ratio_match.group(1).replace("：", ":").replace("x", ":").replace("X", ":").replace("×", ":").replace(" ", "")
    if first_path:
        if tool_name == "photoshop":
            spec_payload["image_paths"] = [first_path]
        elif tool_name == "lightroom":
            spec_payload["image_path_or_url"] = first_path
    if tool_name == "photoshop":
        if re.search(r"写实|真实|照片|photoreal|realistic|\bphoto\b", prompt, flags=re.IGNORECASE):
            spec_payload["mode"] = "photo"
        elif re.search(r"幻想|插画|动漫|二次元|卡通|立体|风格|illustration|anime", prompt, flags=re.IGNORECASE):
            spec_payload["mode"] = "illustration"
        else:
            spec_payload["mode"] = "auto"
    return tool_name, _normalize_tool_args(tool_name, spec_payload, ""), {"format": "simple_markdown", "payload": spec_payload}


def _load_spec_case(*, spec_path: str = "") -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    raw_text = Path(spec_path).read_text(encoding="utf-8")
    front_matter, body = _extract_front_matter(raw_text)
    yaml_block = _extract_yaml_block(raw_text)
    payload = front_matter or yaml_block
    if payload:
        tool_name = str(_pick_field(payload, "tool", "tool_name") or "").strip().lower()
        if not tool_name:
            raise ValueError("markdown spec 缺少 tool")
        tool_args = _normalize_tool_args(tool_name, payload, body)
        return tool_name, tool_args, {
            "source_type": "file",
            "source": spec_path,
            "format": "structured_markdown",
            "payload": payload,
            "body_preview": body[:400],
        }

    tool_name, tool_args, extra = _parse_simple_markdown_spec(raw_text)
    return tool_name, tool_args, {
        "source_type": "file",
        "source": spec_path,
        **extra,
        "raw_preview": raw_text[:400],
    }


def _build_inputs(inputs_dir: Path) -> Dict[str, str]:
    inputs_dir.mkdir(parents=True, exist_ok=True)
    photo_path = inputs_dir / "photo_input.jpg"
    gif_ref_path = inputs_dir / "gif_reference.png"

    portrait = Image.new("RGB", (768, 768), (234, 230, 226))
    draw = ImageDraw.Draw(portrait)
    draw.ellipse((180, 120, 590, 560), fill=(221, 190, 167))
    draw.ellipse((270, 280, 330, 340), fill=(45, 45, 45))
    draw.ellipse((430, 280, 490, 340), fill=(45, 45, 45))
    draw.rounded_rectangle((290, 420, 480, 448), radius=12, fill=(160, 92, 96))
    draw.rectangle((150, 540, 620, 768), fill=(74, 98, 146))
    draw.rectangle((170, 80, 600, 170), fill=(88, 66, 50))
    portrait.save(photo_path, format="JPEG", quality=92)

    slime = Image.new("RGBA", (192, 192), (0, 0, 0, 0))
    slime_draw = ImageDraw.Draw(slime)
    slime_draw.rounded_rectangle((36, 58, 156, 158), radius=42, fill=(78, 214, 98, 255), outline=(28, 120, 44, 255), width=5)
    slime_draw.ellipse((68, 94, 86, 112), fill=(18, 18, 18, 255))
    slime_draw.ellipse((108, 94, 126, 112), fill=(18, 18, 18, 255))
    slime_draw.arc((76, 112, 118, 138), 10, 170, fill=(18, 18, 18, 255), width=4)
    slime.save(gif_ref_path, format="PNG")

    return {
        "photo": str(photo_path.resolve()),
        "gif_ref": str(gif_ref_path.resolve()),
    }


def _expected_prefix(tool_name: str) -> str:
    mapping = {
        "gif_generation": f"{EXPECTED_MANAGED_ROOT}/gif/",
        "photoshop": f"{EXPECTED_MANAGED_ROOT}/photoshop/",
        "lightroom": f"{EXPECTED_MANAGED_ROOT}/lightroom/",
    }
    return mapping[tool_name]


def _extract_primary_media(result: Any) -> Dict[str, Any]:
    for part in result.parts:
        if part.type in {"image", "audio", "video", "file"} and str(part.url or "").strip():
            path = Path(str(part.url))
            return {
                "url": str(part.url),
                "exists": path.exists(),
                "size": path.stat().st_size if path.exists() else 0,
                "mime_type": str(part.mime_type or ""),
                "host_mirror_path": str(Path(str(part.url).replace("/workspace", str(HOST_WORKSPACE_ROOT), 1))) if str(part.url).startswith("/workspace/") else "",
            }
    return {"url": "", "exists": False, "size": 0, "mime_type": "", "host_mirror_path": ""}


def _build_payload_preview(result: Any) -> Dict[str, Any]:
    emitter = OpenAIChatEmitter()
    message = emitter._turn_to_message(MessageTurn(role=result.history_role, parts=result.parts))
    content = message.get("content")
    content_types: List[str] = []
    image_url_prefix = ""
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or "").strip()
            if item_type:
                content_types.append(item_type)
            if item_type == "image_url":
                url = ""
                image_url = item.get("image_url")
                if isinstance(image_url, dict):
                    url = str(image_url.get("url") or "")
                elif isinstance(image_url, str):
                    url = image_url
                image_url_prefix = url[:64]
    return {
        "role": str(message.get("role") or ""),
        "content_is_list": isinstance(content, list),
        "content_types": content_types,
        "image_url_prefix": image_url_prefix,
        "text_preview": json.dumps(content, ensure_ascii=False)[:400] if not isinstance(content, str) else content[:400],
    }


async def _execute_case(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    call = ToolCall(id=f"validate_{tool_name}_{uuid.uuid4().hex[:8]}", name=tool_name, arguments=arguments)
    result = await tool_registry.execute(
        call,
        permission_level="advanced",
        runtime=ToolRuntimeBinding(
            context_id="tool_validate_magic_draw",
            dialog_chat_key="tool_validate-private_magic_draw",
            primary_user_id="tool_validate_advanced",
            permission_level="advanced",
            adapter_key="tool_validate",
            channel_id="private_magic_draw",
        ),
    )
    media = _extract_primary_media(result)
    payload_preview = _build_payload_preview(result)
    text_parts = [str(part.text or "") for part in result.parts if str(part.text or "").strip()]
    expected_prefix = _expected_prefix(tool_name)
    managed_path = str(media.get("url") or "")
    path_ok = managed_path.startswith(expected_prefix)

    return {
        "tool_name": tool_name,
        "expected_prefix": expected_prefix,
        "path_ok": path_ok,
        "call_id": call.id,
        "arguments": arguments,
        "is_error": bool(result.is_error),
        "history_role": str(result.history_role or ""),
        "trace_title": str(result.trace_title or ""),
        "trace_summary": str(result.trace_summary or ""),
        "parts": [
            {
                "type": part.type,
                "text": str(part.text or "")[:400],
                "url": str(part.url or ""),
                "mime_type": str(part.mime_type or ""),
                "meta": dict(part.meta or {}),
            }
            for part in result.parts
        ],
        "text_parts": text_parts,
        "media": media,
        "payload_preview": payload_preview,
    }


async def amain() -> int:
    parser = argparse.ArgumentParser(description="直接执行真实 magic_draw tool（不走 bot/context/toolcall）")
    parser.add_argument("--output-dir", default=str(_default_output_dir()), help="summary 输出目录")
    parser.add_argument("--spec-md", default="", help="markdown 需求文件路径；传入后只执行该 spec 对应的一个 tool")
    parser.add_argument(
        "--tool",
        action="append",
        choices=["gif_generation", "photoshop", "lightroom"],
        help="仅执行指定工具；可重复传入，多次验证仍按真实调用计费",
    )
    args = parser.parse_args()

    register_migrated_tools()

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs = _build_inputs(output_dir / "inputs")

    cases = []
    spec_summary: Dict[str, Any] = {}
    if args.spec_md:
        tool_name, tool_args, spec_summary = _load_spec_case(spec_path=args.spec_md)
        selected_tools = [tool_name]
        cases.append((tool_name, tool_args))
    else:
        selected_tools = args.tool or ["gif_generation", "photoshop", "lightroom"]
        for tool_name in selected_tools:
            if tool_name == "gif_generation":
                tool_args = {
                    **_TOOL_CASES[tool_name],
                    "reference_images": [
                        {
                            "image_path": inputs["gif_ref"],
                            "description": "green slime reference",
                        }
                    ],
                }
            elif tool_name == "photoshop":
                tool_args = {
                    **_TOOL_CASES[tool_name],
                    "image_paths": [inputs["photo"]],
                }
            else:
                tool_args = {
                    **_TOOL_CASES[tool_name],
                    "image_path_or_url": inputs["photo"],
                }
            cases.append((tool_name, tool_args))

    results = []
    for tool_name, tool_args in cases:
        results.append(await _execute_case(tool_name, tool_args))

    failed_tools = [item["tool_name"] for item in results if item["is_error"] or not item["path_ok"] or not item["media"]["exists"]]

    summary = {
        "mode": "real_tool_only",
        "draw_call_count": len(cases),
        "expected_managed_root": EXPECTED_MANAGED_ROOT,
        "selected_tools": selected_tools,
        "failed_tools": failed_tools,
        "context_id": "tool_validate_magic_draw",
        "dialog_chat_key": "tool_validate-private_magic_draw",
        "primary_user_id": "tool_validate_advanced",
        "workspace_root": str(WORKSPACE_ROOT),
        "host_workspace_root": str(HOST_WORKSPACE_ROOT),
        "inputs": inputs,
        "spec": spec_summary,
        "results": results,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir), "summary": str(output_dir / 'summary.json')}, ensure_ascii=False, indent=2))
    if failed_tools:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
