from __future__ import annotations

import asyncio
import base64
import mimetypes
import re
import uuid
from collections import Counter
from io import BytesIO
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageOps
from pydantic import BaseModel, ConfigDict, Field

from tool_runtime.host import ToolHostBridge
from tool_runtime.result import ToolOutcome, ToolPart


_GIF_TOOL_ID = "gif_generation"
_PHOTOSHOP_TOOL_ID = "photoshop"
_LIGHTROOM_TOOL_ID = "lightroom"
_DRAW_MANAGED_ROOT = "draw"


_DRAW_MODEL_GROUP_I18N = {
    "GIF 绘图模型组": {"zh-CN": "GIF 绘图模型组", "en-US": "GIF Drawing Model Group"},
    "Photoshop 模型组": {"zh-CN": "Photoshop 模型组", "en-US": "Photoshop Model Group"},
    "Lightroom 模型组": {"zh-CN": "Lightroom 模型组", "en-US": "Lightroom Model Group"},
}


class MagicDrawConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    STREAM_MODE: bool = Field(
        default=False,
        title="使用流式 API",
        json_schema_extra={"i18n_title": {"zh-CN": "使用流式 API", "en-US": "Use Streaming API"}},
    )
    TIMEOUT: int = Field(
        default=300,
        title="请求超时时间",
        json_schema_extra={"i18n_title": {"zh-CN": "请求超时时间", "en-US": "Request Timeout"}},
    )
    DEBUG: bool = Field(
        default=False,
        title="调试模式",
        json_schema_extra={"i18n_title": {"zh-CN": "调试模式", "en-US": "Debug Mode"}},
    )


def _draw_model_group_field(title: str) -> Any:
    return Field(
        default="",
        title=title,
        json_schema_extra={
            "ref_model_groups": True,
            "model_type": "draw",
            "i18n_title": _DRAW_MODEL_GROUP_I18N.get(title, {"zh-CN": title, "en-US": title}),
        },
    )


class _MagicDrawBaseConfig(MagicDrawConfig):
    pass


class GifGenerationConfig(_MagicDrawBaseConfig):
    GIF_MODEL_GROUP: str = _draw_model_group_field("GIF 绘图模型组")
    GIF_EDGE_FILTER_PIXELS: int = Field(
        default=4,
        title="GIF 帧边缘过滤像素数",
        json_schema_extra={"i18n_title": {"zh-CN": "GIF 帧边缘过滤像素数", "en-US": "GIF Edge Filter Pixels"}},
    )


class PhotoshopConfig(_MagicDrawBaseConfig):
    PHOTOSHOP_MODEL_GROUP: str = _draw_model_group_field("Photoshop 模型组")
    PHOTOSHOP_SYSTEM_PROMPT: str = Field(
        default=dedent(
            """
            You are Gemini 3 Pro Image (image-capable, Nano Banana Pro). You are a senior digital artist + Photoshop compositor.
            Your job is to produce exactly ONE final image that satisfies the user's instruction, using the provided reference images when available.

            Core rules (always):
            - Follow the user's instruction with high precision. If something is unclear, make the most reasonable assumption and proceed (do not ask questions).
            - Reference images are hard constraints and may appear in ANY order. Never assume ordering; infer roles
              (identity anchor / scene anchor / style anchor) from the images + the user's instruction.
            - Follow the official Nano Banana image editing pattern internally:
              "Using the provided image(s), please ... Ensure ... integrate ..."
              (Do not output this template. Output the final image only.)
            - High-fidelity detail preservation (important):
              - If any people appear in reference images, preserve their identity by default.
              - Ensure the person's face and features remain completely unchanged (facial geometry, eye shape, nose, mouth,
                moles/freckles, hairline, hairstyle), unless the user explicitly requests an identity change.
              - Wardrobe/outfit edits MUST NOT touch the face/head region. When the user asks to change clothing/wardrobe,
                treat it as a body/clothing edit while keeping the face/head identity-locked and unchanged.
              - Preserve key features: face, hair, body proportions, outfit key features, and recognizable traits.
              - If multiple different people appear across references, keep them as separate individuals. Never blend/average faces or swap identities.
              - Keep body type/proportions/height/build as close as possible; no slimming/reshaping unless explicitly requested.
              - If retouching is requested, only natural retouch (blemish removal, subtle skin smoothing while preserving texture)
                without changing facial geometry.
            - Do not output an unmodified reference image. Always perform the requested change(s).
              When a scene anchor photo is provided, keep everything that the user didn't ask to change as close to the original as possible.
            - No text, no captions, no watermarks, no logos, no borders, no UI, no extra explanation—output image only.
            - Keep details sharp; avoid AI artifacts (extra fingers, melted edges, strange symbols, duplicated items).
            - Prefer a reasonably high resolution, but prioritize edit/drawing quality over chasing resolution. Do not downscale.

            Determine the working mode:
            - If the user explicitly sets the mode (AUTO / PHOTO / ILLUSTRATION), treat it as a hard override.
            1) PHOTO-COMPOSITE MODE (real photo / old photo / inserting a person into a photo / photorealistic request):
               - Treat the main photo as a real photograph. Preserve realism and original vibe.
               - Identity lock (important): if a person appears in the input/reference, keep the same person.
                 No face replacement, no "beauty filter" that changes facial geometry, no slimming/reshaping body, no changing height/build.
                 You may do natural retouching (blemish removal, subtle skin smoothing while keeping texture) if requested.
               - Preserve the original composition and camera framing unless the user explicitly asks to change it.
               - Match perspective, focal length, depth of field, grain/noise, compression artifacts, and color temperature.
               - Match lighting direction, hardness, and shadow/occlusion. Add contact shadows and ambient occlusion where needed.
               - Integrate edges naturally: subtle blur/halo removal, consistent sharpness, consistent noise.
               - Do NOT stylize into anime/illustration unless the user explicitly asks.
               - Do not crop, expand canvas, or change aspect ratio unless the user explicitly asks.
               - After composing, do a final identity-lock pass focusing ONLY on fixing identity drift (faces/heads) while keeping everything else unchanged.

            2) ILLUSTRATION MODE (drawing from scratch / stylized illustration / anime request):
               Default style = “Amagi-like” semi-realistic anime illustration (not chibi):
               - Semi-realistic proportions; refined facial features; expressive eyes; no chibi/super-deformed look.
               - Clean, controlled line art (thin-to-medium line weight).
               - Soft cel shading + gentle painterly gradients, subtle bloom, smooth but not plastic skin texture.
               - Color script inspired by Amagi: vibrant yet clean palette, pastel highlights, rich midtones, cool shadows,
                 strong but harmonious contrast (often teal/cyan vs warm pink/orange accents).
               - Cinematic lighting: clear key light + soft fill, readable silhouettes, tasteful rim light when appropriate.
               - Background: coherent environment with depth (foreground/midground/background), atmospheric perspective.

            Reference image handling (when user doesn’t specify roles):
            - Prefer the clearest character portrait as the identity anchor.
            - Prefer the clearest background/photo as the composition anchor.
            - If multiple style signals conflict, prioritize identity consistency > realism (for photo mode) > user explicit style request.
            """
        ).strip(),
        title="Photoshop 系统提示词",
        json_schema_extra={"i18n_title": {"zh-CN": "Photoshop 系统提示词", "en-US": "Photoshop System Prompt"}},
    )
    PHOTOSHOP_DEFAULT_ASPECT_RATIO: str = Field(
        default="1:1",
        title="Photoshop 默认画面比例",
        json_schema_extra={"i18n_title": {"zh-CN": "Photoshop 默认画面比例", "en-US": "Photoshop Default Aspect Ratio"}},
    )
    PHOTOSHOP_HQ_LONG_SIDE: int = Field(
        default=2048,
        title="Photoshop 高画质目标长边(px)",
        json_schema_extra={"i18n_title": {"zh-CN": "Photoshop 高画质目标长边(px)", "en-US": "Photoshop HQ Target Long Side (px)"}},
    )
    PHOTOSHOP_HQ_MAX_LONG_SIDE: int = Field(
        default=4096,
        title="Photoshop 高画质长边上限(px)",
        json_schema_extra={"i18n_title": {"zh-CN": "Photoshop 高画质长边上限(px)", "en-US": "Photoshop HQ Max Long Side (px)"}},
    )


class LightroomConfig(_MagicDrawBaseConfig):
    LIGHTROOM_MODEL_GROUP: str = _draw_model_group_field("Lightroom 模型组")
    LIGHTROOM_SYSTEM_PROMPT: str = Field(
        default=dedent(
            """
            You are Gemini 3 Pro Image (image-capable, Nano Banana Pro). You are a professional Lightroom-style photo retoucher and colorist.
            Your job is to improve ONE input photo with realistic Lightroom-style edits. Edits can be moderate/noticeable; do not be overly conservative—aim for a strong aesthetic improvement while keeping it photographic.

            Hard constraints (must follow):
            - Work from the provided photo (edit it). Do not invent a new scene.
            - Keep the same aspect ratio as the input image. Avoid borders and rotation. If you crop/expand, the aspect ratio must stay identical.
            - Keep resolution at least the original (prefer same or higher). Do not downscale.
            - Preserve geometry: do not change camera viewpoint, perspective, or reshape subjects unless the user explicitly requests it.
            - Preserve the main subject identity. You may remove minor distractions and do local repairs when it improves aesthetics; avoid adding new major objects/people unless the user requests.
            - Identity lock for people (important):
              - Ensure the person's face and features remain completely unchanged. No face swap, no replacing a person with a different person.
              - Do not change body type/proportions (no slimming/reshaping). Keep height/build and recognizable body features as close as possible.
              - Do not change age/ethnicity/gender. Keep hair/skin tone believable (unless user explicitly requests a style change).
            - Output image only. No text, no captions, no watermarks, no UI overlays.
            - Prefer a reasonably high resolution, but prioritize retouch quality over chasing resolution.

            Allowed operations (Lightroom-like):
            - Global: exposure/contrast, highlights/shadows, whites/blacks, tone curve, WB, HSL, color grading, clarity/texture, dehaze,
              sharpening, realistic noise reduction.
            - Optical: lens correction, remove chromatic aberration.
            - Local masks: dodge & burn, selective saturation, selective sharpening, local contrast—keep it believable.
            - Spot/heal: remove small blemishes, dust spots, minor distractions (only if the user asks or it clearly improves aesthetics).

            Quality targets:
            - Natural skin texture (avoid plastic/waxy look).
            - Clean but realistic noise reduction; avoid over-smoothing.
            - Correct color cast; balanced whites; controlled highlights; detailed shadows.

            When the user asks for a look (e.g., “Amagi-like colors”):
            - Apply it as a COLOR GRADING / TONE CURVE style while keeping it photographic and plausible.
            - Keep skin tones healthy and avoid extreme neon unless explicitly requested.
            """
        ).strip(),
        title="Lightroom 系统提示词",
        json_schema_extra={"i18n_title": {"zh-CN": "Lightroom 系统提示词", "en-US": "Lightroom System Prompt"}},
    )
    LIGHTROOM_HQ_LONG_SIDE: int = Field(
        default=2048,
        title="Lightroom 高画质目标长边(px)",
        json_schema_extra={"i18n_title": {"zh-CN": "Lightroom 高画质目标长边(px)", "en-US": "Lightroom HQ Target Long Side (px)"}},
    )
    LIGHTROOM_HQ_MAX_LONG_SIDE: int = Field(
        default=4096,
        title="Lightroom 高画质长边上限(px)",
        json_schema_extra={"i18n_title": {"zh-CN": "Lightroom 高画质长边上限(px)", "en-US": "Lightroom HQ Max Long Side (px)"}},
    )


GIF_GENERATION_CONFIG_MODEL = GifGenerationConfig
PHOTOSHOP_CONFIG_MODEL = PhotoshopConfig
LIGHTROOM_CONFIG_MODEL = LightroomConfig
MAGIC_DRAW_SHARED_CATEGORY = "magic_draw"


GIF_GENERATION_DISPLAY_NAME = "GIF 生成"
GIF_GENERATION_DESCRIPTION = "生成循环 GIF 动画，返回成品路径不发送到聊天"
GIF_GENERATION_PARAMETERS = {
    "type": "object",
    "properties": {
        "content": {"type": "string", "description": "动画内容的极其详细描述"},
        "style": {"type": "string", "description": "画面风格，默认 pixel art"},
        "transparent_background": {"type": "boolean", "description": "是否输出透明背景 GIF"},
        "reference_images": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "image_path": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
            "description": "最多 1 张参考图",
        },
    },
    "required": ["content"],
}

PHOTOSHOP_DISPLAY_NAME = "Photoshop"
PHOTOSHOP_DESCRIPTION = "多图融合或再创作，返回成品路径不发送到聊天"
PHOTOSHOP_PARAMETERS = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string", "description": "最终编辑要求"},
        "image_paths": {"type": "array", "items": {"type": "string"}, "description": "0~3 张参考图"},
        "aspect_ratio": {"type": "string", "description": "目标画面比例，如 1:1、16:9"},
        "mode": {"type": "string", "description": "auto | photo（真实照片编辑/合成） | illustration（虚拟创作用图）"},
    },
    "required": ["prompt"],
}

LIGHTROOM_DISPLAY_NAME = "Lightroom"
LIGHTROOM_DESCRIPTION = "对单张照片做轻度修缮和调色，返回成品路径不发送到聊天"
LIGHTROOM_PARAMETERS = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string", "description": "修图要求"},
        "image_path_or_url": {"type": "string", "description": "输入图片路径或 URL"},
    },
    "required": ["prompt", "image_path_or_url"],
}

def _guess_mime_from_bytes(data: bytes, *, fallback_name: str = "image.bin") -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return "image/webp"
    return mimetypes.guess_type(fallback_name)[0] or "application/octet-stream"


def _data_uri_from_bytes(data: bytes, mime_type: str) -> str:
    return f"data:{mime_type};base64,{base64.b64encode(data).decode('utf-8')}"


def _parse_data_uri(uri: str) -> tuple[str, bytes]:
    header, payload = str(uri or "").split(",", 1)
    mime_type = header[5:].split(";", 1)[0].strip() or "application/octet-stream"
    return mime_type, base64.b64decode(payload.encode("utf-8"), validate=False)


async def _resolve_ref_bytes(tool_host: ToolHostBridge, ref: str) -> tuple[bytes, str]:
    raw = str(ref or "").strip()
    if not raw:
        raise ValueError("图片引用为空")
    if raw.startswith("data:"):
        return _parse_data_uri(raw)[1], _parse_data_uri(raw)[0]
    if raw.startswith(("http://", "https://")):
        response = await tool_host.http_request(method="GET", url=raw, timeout=60.0)
        data = bytes(response.content)
        mime_type = str(response.headers.get("content-type") or "").split(";", 1)[0].strip() or _guess_mime_from_bytes(data, fallback_name=raw)
        return data, mime_type
    resolved = await tool_host.resolve_media_ref(raw)
    data = await tool_host.read_local_bytes(resolved)
    return data, _guess_mime_from_bytes(data, fallback_name=resolved)


async def _resolve_ref_data_uri(tool_host: ToolHostBridge, ref: str) -> str:
    raw = str(ref or "").strip()
    if raw.startswith("data:"):
        return raw
    data, mime_type = await _resolve_ref_bytes(tool_host, raw)
    return _data_uri_from_bytes(data, mime_type)


async def _write_managed_media(tool_host: ToolHostBridge, raw_ref: str, *, file_name_hint: str, managed_subdir: str = "") -> tuple[str, str]:
    raw = str(raw_ref or "").strip()
    if raw.startswith("data:"):
        mime_type, data = _parse_data_uri(raw)
        ext = mimetypes.guess_extension(mime_type or "") or ".bin"
        managed = await tool_host.write_managed_file(data, file_name=f"{file_name_hint}{ext}", mime_type=mime_type, managed_subdir=managed_subdir, managed_root=_DRAW_MANAGED_ROOT)
        return managed.managed_path, managed.mime_type
    if raw.startswith(("http://", "https://")):
        data, mime_type = await _resolve_ref_bytes(tool_host, raw)
        ext = mimetypes.guess_extension(mime_type or "") or ".bin"
        managed = await tool_host.write_managed_file(data, file_name=f"{file_name_hint}{ext}", mime_type=mime_type, managed_subdir=managed_subdir, managed_root=_DRAW_MANAGED_ROOT)
        return managed.managed_path, managed.mime_type
    resolved = await tool_host.resolve_media_ref(raw)
    mime_type = mimetypes.guess_type(resolved)[0] or "application/octet-stream"
    managed = await tool_host.write_managed_file(resolved, file_name=Path(resolved).name or file_name_hint, mime_type=mime_type, managed_subdir=managed_subdir, managed_root=_DRAW_MANAGED_ROOT)
    return managed.managed_path, managed.mime_type


def _final_product_subdir(tool_id: str) -> str:
    mapping = {
        _GIF_TOOL_ID: "gif",
        _PHOTOSHOP_TOOL_ID: "photoshop",
        _LIGHTROOM_TOOL_ID: "lightroom",
    }
    return mapping.get(str(tool_id or "").strip(), "")


def _save_image_as_jpeg(image: Image.Image, output_path: str, quality: int = 80) -> None:
    q = max(1, min(int(quality), 95))
    try:
        if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
            rgba = image.convert("RGBA")
            bg = Image.new("RGB", rgba.size, (255, 255, 255))
            bg.paste(rgba, mask=rgba.getchannel("A"))
            image = bg
        else:
            image = image.convert("RGB")
    except Exception:
        image = image.convert("RGB")
    image.save(output_path, format="JPEG", quality=q, optimize=True)


def _encode_image_to_data_uri(image: Image.Image, *, format: str = "JPEG", quality: int = 90, max_long_side: int = 0) -> str:
    img = image
    width, height = img.size
    if max_long_side and width > 0 and height > 0:
        long_side = max(width, height)
        if long_side > max_long_side:
            scale = max_long_side / long_side
            new_size = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
            img = img.resize(new_size, resample=Image.Resampling.LANCZOS)
    fmt = str(format or "JPEG").upper()
    buffer = BytesIO()
    if fmt in {"JPG", "JPEG"}:
        if img.mode in {"RGBA", "LA"} or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            bg = Image.new("RGB", rgba.size, (255, 255, 255))
            bg.paste(rgba, mask=rgba.getchannel("A"))
            img = bg
        else:
            img = img.convert("RGB")
        img.save(buffer, format="JPEG", quality=max(1, min(int(quality), 95)), optimize=True)
        return _data_uri_from_bytes(buffer.getvalue(), "image/jpeg")
    img.save(buffer, format="PNG")
    return _data_uri_from_bytes(buffer.getvalue(), "image/png")


async def _download_image(tool_host: ToolHostBridge, ref: str) -> Image.Image:
    response = await tool_host.http_request(method="GET", url=ref, follow_redirects=True, timeout=60.0)
    image = Image.open(BytesIO(response.content))
    image.load()
    return image


def _decode_base64_image(raw: str) -> Image.Image:
    text = str(raw or "").strip()
    if text.startswith("data:"):
        _, payload = text.split(",", 1)
        data = base64.b64decode(payload.encode("utf-8"), validate=False)
    else:
        data = base64.b64decode(text.encode("utf-8"), validate=False)
    image = Image.open(BytesIO(data))
    image.load()
    return image


async def _load_image_from_ref(tool_host: ToolHostBridge, ref: str) -> Image.Image:
    raw = str(ref or "").strip()
    if raw.startswith(("http://", "https://")):
        return await _download_image(tool_host, raw)
    if raw.startswith("data:"):
        return _decode_base64_image(raw)
    resolved = await tool_host.resolve_media_ref(raw)
    return Image.open(resolved)


def split_sprite_sheet(image: Image.Image, rows: int = 4, cols: int = 4) -> List[Image.Image]:
    width, height = image.size
    frame_width = width // cols
    frame_height = height // rows
    return [image.crop((c * frame_width, r * frame_height, (c + 1) * frame_width, (r + 1) * frame_height)) for r in range(rows) for c in range(cols)]


def create_gif_from_frames(frames: List[Image.Image], output_path: str, duration: int = 100, transparency_color: Optional[Tuple[int, int, int]] = None, tolerance: int = 10) -> None:
    if not frames:
        return
    processed = []
    for frame in frames:
        img = frame.convert("RGBA")
        if transparency_color:
            tr, tg, tb = transparency_color
            new_data = []
            for pixel in img.getdata():
                r, g, b, a = int(pixel[0]), int(pixel[1]), int(pixel[2]), int(pixel[3])
                if abs(r - tr) <= tolerance and abs(g - tg) <= tolerance and abs(b - tb) <= tolerance:
                    new_data.append((255, 255, 255, 0))
                else:
                    new_data.append((r, g, b, a))
            img.putdata(new_data)
        processed.append(img)
    processed[0].save(output_path, save_all=True, append_images=processed[1:], optimize=False, duration=duration, loop=0, disposal=2)


def _filter_frame_edges(frame: Image.Image, edge_pixels: int) -> Image.Image:
    if edge_pixels <= 0:
        return frame
    width, height = frame.size
    return frame.crop((edge_pixels, edge_pixels, width - edge_pixels, height - edge_pixels))


def _extract_common_background_color(frames: List[Image.Image]) -> Optional[Tuple[int, int, int]]:
    if not frames:
        return None
    colors: Counter[Tuple[int, int, int]] = Counter()
    for frame in frames:
        rgb = frame.convert("RGB")
        width, height = rgb.size
        coords = [(x, 0) for x in range(width)] + [(x, height - 1) for x in range(width)]
        coords += [(0, y) for y in range(1, height - 1)] + [(width - 1, y) for y in range(1, height - 1)]
        for coord in coords:
            colors[rgb.getpixel(coord)] += 1
    if not colors:
        return None
    return colors.most_common(1)[0][0]


def _parse_aspect_ratio(value: str) -> Optional[float]:
    raw = str(value or "").strip().lower().replace("×", ":").replace("x", ":").replace("*", ":")
    if ":" not in raw:
        return None
    left, right = raw.split(":", 1)
    try:
        width = float(left)
        height = float(right)
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return width / height


def _simplify_ratio_str(width: int, height: int) -> str:
    import math
    g = math.gcd(max(1, width), max(1, height))
    return f"{width // g}:{height // g}"


async def _get_image_size_from_ref(tool_host: ToolHostBridge, ref: str) -> Optional[Tuple[int, int]]:
    try:
        image = await _load_image_from_ref(tool_host, ref)
        image = ImageOps.exif_transpose(image)
        return image.size
    except Exception:
        return None


def _crop_to_aspect_ratio(image: Image.Image, target_ratio: float) -> Image.Image:
    width, height = image.size
    if width <= 0 or height <= 0 or target_ratio <= 0:
        return image
    current_ratio = width / height
    if abs(current_ratio - target_ratio) < 1e-3:
        return image
    if current_ratio > target_ratio:
        new_width = int(round(height * target_ratio))
        left = max((width - new_width) // 2, 0)
        return image.crop((left, 0, left + new_width, height))
    new_height = int(round(width / target_ratio))
    top = max((height - new_height) // 2, 0)
    return image.crop((0, top, width, top + new_height))


def _upscale_to_long_side(image: Image.Image, long_side: int) -> Image.Image:
    width, height = image.size
    current_long = max(width, height)
    if current_long <= 0 or long_side <= current_long:
        return image
    scale = long_side / current_long
    new_size = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
    return image.resize(new_size, resample=Image.Resampling.LANCZOS)


async def _generate_image(tool_host: ToolHostBridge, model_group: str, prompt: str, *, system_prompt: str, reference_images: Optional[List[Tuple[str, str]]] = None, timeout: int = 300, stream_mode: bool = False, image_detail: Optional[str] = None) -> str:
    return await tool_host.invoke_model(
        model_group,
        {
            "operation": "image_generate",
            "prompt": prompt,
            "system_prompt": system_prompt,
            "reference_images": [{"image": image, "description": desc} for image, desc in (reference_images or [])],
            "timeout": int(timeout),
            "stream_mode": bool(stream_mode),
            "image_detail": image_detail or "",
        },
    )


async def _image_outcome(tool_id: str, tool_host: ToolHostBridge, image_ref: str, *, file_name_hint: str, trace_title: str, text_notice: str, is_error: bool = False) -> ToolOutcome:
    managed_path, mime_type = await _write_managed_media(
        tool_host,
        image_ref,
        file_name_hint=file_name_hint,
        managed_subdir=_final_product_subdir(tool_id),
    )
    visible_notice = f"{text_notice} 产物路径：{managed_path}"
    return ToolOutcome(
        parts=[
            ToolPart(type="text", text=visible_notice, meta={"source": "tool", "tool_id": tool_id, "inject_role": "user", "ui_notice": visible_notice}),
            ToolPart(type="image", url=managed_path, mime_type=mime_type, meta={"source": "tool", "tool_id": tool_id, "inject_role": "user", "ui_notice": visible_notice}),
        ],
        is_error=is_error,
        history_role="user",
        trace_title=trace_title,
        trace_summary=tool_id,
    )


def _merge_notice_into_user_outcome(tool_id: str, outcome: ToolOutcome, notice: str) -> ToolOutcome:
    clean_notice = str(notice or "").strip()
    if not clean_notice:
        return outcome

    merged_text = clean_notice
    if outcome.parts and outcome.parts[0].type == "text":
        base_text = str(outcome.parts[0].text or "").strip()
        merged_text = f"{clean_notice}\n{base_text}" if base_text else clean_notice
        outcome.parts[0].text = merged_text

    for part in outcome.parts:
        meta = dict(part.meta or {})
        if str(meta.get("source") or "") != "tool" or str(meta.get("tool_id") or "") != tool_id:
            continue
        meta["ui_notice"] = merged_text
        part.meta = meta

    return outcome


def _error_outcome(tool_id: str, message: str) -> ToolOutcome:
    return ToolOutcome(
        parts=[ToolPart(type="text", text=message, meta={"source": "tool", "tool_id": tool_id, "inject_role": "tool"})],
        is_error=True,
        history_role="tool",
        trace_title=f"Tool | {tool_id}",
        trace_summary=f"{tool_id}_error",
    )


def _primary_media_path(outcome: ToolOutcome) -> str:
    for part in outcome.parts:
        if part.type in {"image", "audio", "video", "file"} and str(part.url or "").strip():
            return str(part.url or "").strip()
    return ""


async def _log_magic_draw(
    tool_host: ToolHostBridge | None,
    *,
    level: str,
    event: str,
    tool_id: str,
    model_group: str = "",
    product_path: str = "",
    error: str = "",
) -> None:
    if tool_host is None:
        return
    identity = tool_host.get_context_identity()
    await tool_host.log(
        level,
        event,
        tool_id=tool_id,
        context_id=str(identity.context_id or "").strip(),
        primary_user_id=str(identity.user_id or "").strip(),
        dialog_chat_key=str(identity.dialog_chat_key or "").strip(),
        model_group=str(model_group or "").strip(),
        product_path=str(product_path or "").strip(),
        error=str(error or "").strip(),
    )


async def _accept_magic_draw_request(
    tool_id: str,
    tool_host: ToolHostBridge,
    *,
    model_group: str,
) -> None:
    await _log_magic_draw(
        tool_host,
        level="info",
        event="magic_draw accepted",
        tool_id=tool_id,
        model_group=model_group,
    )


async def _finalize_image_success(
    tool_id: str,
    tool_host: ToolHostBridge,
    *,
    image_ref: str,
    file_name_hint: str,
    trace_title: str,
    text_notice: str,
    model_group: str,
    cleanup_path: str = "",
) -> ToolOutcome:
    outcome = await _image_outcome(
        tool_id,
        tool_host,
        image_ref,
        file_name_hint=file_name_hint,
        trace_title=trace_title,
        text_notice=text_notice,
    )
    if cleanup_path:
        Path(cleanup_path).unlink(missing_ok=True)
    await _log_magic_draw(
        tool_host,
        level="info",
        event="magic_draw completed",
        tool_id=tool_id,
        model_group=model_group,
        product_path=_primary_media_path(outcome),
    )
    return outcome


async def _finalize_image_failure(
    tool_id: str,
    tool_host: ToolHostBridge,
    *,
    model_group: str,
    error_prefix: str,
    error: Exception,
) -> ToolOutcome:
    await _log_magic_draw(
        tool_host,
        level="error",
        event="magic_draw failed",
        tool_id=tool_id,
        model_group=model_group,
        error=str(error),
    )
    return _error_outcome(tool_id, f"{error_prefix}: {error}")


async def gif_generation(
    content: str,
    style: str = "pixel art",
    transparent_background: bool = False,
    reference_images: Optional[List[Dict[str, Any]]] = None,
    tool_host: ToolHostBridge | None = None,
    tool_config: GifGenerationConfig | None = None,
) -> ToolOutcome:
    if tool_host is None:
        return _error_outcome(_GIF_TOOL_ID, "gif_generation 缺少 tool_host")
    config = tool_config or GifGenerationConfig()
    try:
        await _accept_magic_draw_request(_GIF_TOOL_ID, tool_host, model_group=config.GIF_MODEL_GROUP)
        prepared_refs: List[Tuple[str, str]] = []
        if reference_images:
            if len(reference_images) > 1:
                return _error_outcome(_GIF_TOOL_ID, "gif_generation 的 reference_images 最多允许 1 张图片")
            for index, ref_img in enumerate(reference_images, 1):
                if not isinstance(ref_img, dict):
                    continue
                ref_path = str(ref_img.get("image_path") or ref_img.get("path") or "").strip()
                if not ref_path:
                    continue
                prepared_refs.append((await _resolve_ref_data_uri(tool_host, ref_path), str(ref_img.get("description") or f"Reference image #{index}")))

        actual_fps = 8
        frame_duration_ms = int(1000 / actual_fps)
        ref_prefix = "基于提供的参考图片，" if prepared_refs else ""
        ref_style_note = "- 严格保持参考图片的视觉风格、色彩方案、角色特征" if prepared_refs else ""
        ref_no_paste_note = "- 禁止将参考图片原样贴入任何一帧（尤其是第 1 帧）；所有帧必须是新绘制的动画帧" if prepared_refs else ""
        if transparent_background:
            background_requirement = dedent(
                """
                **背景必须是纯色**：选择与主体颜色**强烈对比**的单一纯色作为背景
                - 主体暖色调 → 使用冷色背景（如深蓝、深绿）
                - 主体冷色调 → 使用暖色背景（如深红、橙色）
                - 主体多彩 → 使用深灰或深棕背景
                - 背景在**所有 16 帧**中保持**完全相同的纯色**
                - 背景无渐变、无纹理、无装饰、无阴影
                """
            ).strip()
            summary_note = "，背景必须是纯色"
        else:
            background_requirement = "背景元素（环境、装饰物）在所有 16 帧中保持**完全一致**"
            summary_note = ""
        prompt = dedent(
            f"""
            【专业动画序列帧制作任务】

            {ref_prefix}创作一个 {style} 风格的**循环动画**

            ## 动画内容要求
            {content}

            ## 输出格式规范
            输出一张**正方形画布**，精确划分为 4×4 共 16 个**完全相等**的格子：
            - 格子排列：从左到右、从上到下依次为第 1-16 格
            - 间距要求：格子之间**严格 0 像素间隙**，无分割线、无边框、无空隙
            - 尺寸要求：每个格子的宽高必须完全相同（画布尺寸除以 4）

            ## 动画帧制作要求（全部 16 格）
            🎬 **这是逐帧动画，每一帧必须展示不同的动作画面！**
            🔄 **这是循环动画，第 16 帧必须能自然衔接回第 1 帧！**
            - {background_requirement}
            {ref_style_note}
            {ref_no_paste_note}
            - 帧率：{actual_fps} FPS（每帧 {frame_duration_ms}ms）
            - 只输出最终图片，不要输出解释文本

            请严格按照上述要求制作 16 帧**各不相同**且能**循环播放**的动画序列图{summary_note}
            """
        ).strip()
        image_ref = await _generate_image(tool_host, config.GIF_MODEL_GROUP, prompt, reference_images=prepared_refs or None, system_prompt="", timeout=config.TIMEOUT, stream_mode=config.STREAM_MODE)
        sprite = await _load_image_from_ref(tool_host, image_ref)
        sprite = ImageOps.exif_transpose(sprite)
        frames = split_sprite_sheet(sprite, rows=4, cols=4)
        if len(frames) != 16:
            return _error_outcome(_GIF_TOOL_ID, f"GIF 序列图切割失败，期望 16 帧但获得 {len(frames)} 帧")
        filtered_frames = [_filter_frame_edges(frame, int(config.GIF_EDGE_FILTER_PIXELS or 0)) for frame in frames]
        transparency_color = _extract_common_background_color(filtered_frames) if transparent_background else None
        temp_path = f"/tmp/{uuid.uuid4().hex}.gif"
        create_gif_from_frames(filtered_frames, temp_path, duration=frame_duration_ms, transparency_color=transparency_color)
        return await _finalize_image_success(
            _GIF_TOOL_ID,
            tool_host,
            image_ref=temp_path,
            file_name_hint=f"{_GIF_TOOL_ID}_{uuid.uuid4().hex[:8]}",
            trace_title="Tool | gif_generation",
            text_notice="GIF 已生成，但未发送到聊天框",
            model_group=config.GIF_MODEL_GROUP,
            cleanup_path=temp_path,
        )
    except Exception as exc:
        return await _finalize_image_failure(
            _GIF_TOOL_ID,
            tool_host,
            model_group=config.GIF_MODEL_GROUP,
            error_prefix="GIF 生成失败",
            error=exc,
        )


async def photoshop(
    prompt: str,
    image_paths: Optional[List[str]] = None,
    aspect_ratio: str = "",
    mode: str = "auto",
    tool_host: ToolHostBridge | None = None,
    tool_config: PhotoshopConfig | None = None,
) -> ToolOutcome:
    if tool_host is None:
        return _error_outcome(_PHOTOSHOP_TOOL_ID, "photoshop 缺少 tool_host")
    config = tool_config or PhotoshopConfig()
    temp_path = ""
    try:
        await _accept_magic_draw_request(_PHOTOSHOP_TOOL_ID, tool_host, model_group=config.PHOTOSHOP_MODEL_GROUP)
        refs = [str(p).strip() for p in (image_paths or []) if str(p).strip()]
        if len(refs) > 3:
            return _error_outcome(_PHOTOSHOP_TOOL_ID, "photoshop 的 image_paths 最多允许 3 张图片")

        prepared_refs = [(await _resolve_ref_data_uri(tool_host, ref), f"Bot provided image #{i}") for i, ref in enumerate(refs, 1)]

        mode_norm = (mode or "").strip().lower()
        if mode_norm in {"", "auto"}:
            mode_hint = "AUTO (let the model decide)"
        elif mode_norm in {"photo", "real", "realistic", "photorealistic", "composite", "photo-composite"}:
            mode_hint = "PHOTO-COMPOSITE (real photo editing / inserting people into photos)"
        elif mode_norm in {"illustration", "illust", "anime", "draw", "painting"}:
            mode_hint = "ILLUSTRATION (Amagi-like semi-realistic anime illustration)"
        else:
            return _error_outcome(_PHOTOSHOP_TOOL_ID, "mode 仅支持: auto | photo | illustration")

        photo_mode_aliases = {"photo", "real", "realistic", "photorealistic", "composite", "photo-composite"}
        is_photo_mode = mode_norm in photo_mode_aliases

        aspect_raw = (aspect_ratio or "").strip()
        used_aspect_ratio = aspect_raw
        ratio_value: Optional[float] = None

        if aspect_raw:
            ratio_value = _parse_aspect_ratio(aspect_raw) or None
            norm = aspect_raw.replace(" ", "").replace("×", "x").lower()
            matched = re.match(r"^(\d+)(?:x|\*)(\d+)$", norm)
            if matched:
                try:
                    used_aspect_ratio = _simplify_ratio_str(int(matched.group(1)), int(matched.group(2)))
                except Exception:
                    used_aspect_ratio = aspect_raw
        else:
            candidates: List[Tuple[int, int, float, int]] = []
            for ref in refs:
                size = await _get_image_size_from_ref(tool_host, ref)
                if not size:
                    continue
                width, height = size
                if width <= 0 or height <= 0:
                    continue
                ratio = width / height
                candidates.append((width, height, ratio, width * height))

            def _pick_best(items: List[Tuple[int, int, float, int]]) -> Optional[Tuple[int, int, float, int]]:
                if not items:
                    return None
                return max(items, key=lambda item: item[3])

            wide = [item for item in candidates if item[2] >= 1.15]
            tall = [item for item in candidates if item[2] <= 0.87]
            best = _pick_best(wide) or _pick_best(tall) or _pick_best(candidates)
            if best:
                width, height, ratio, _ = best
                ratio_value = ratio
                used_aspect_ratio = _simplify_ratio_str(width, height)

            if not used_aspect_ratio:
                used_aspect_ratio = config.PHOTOSHOP_DEFAULT_ASPECT_RATIO
                ratio_value = _parse_aspect_ratio(used_aspect_ratio) or None

        photo_identity_lock = ""
        if is_photo_mode:
            photo_identity_lock = (
                "- 人物一致性（硬性要求）：若参考图/画面中包含人物，必须保持同一人（禁止换人/换脸/改年龄性别种族），"
                "面部特征/五官骨相必须保持完全不变（remain completely unchanged）；"
                "换衣服/换造型等编辑只允许改身体/服装区域，严禁改动脸/头部区域（脸/发际线/发型/五官骨相必须完全保持不变）；"
                "体格/身材/身高/头身比例尽量不变（除非用户明确要求改变体型）；"
                "若用户要求“变美/修脸/磨皮”，只允许自然修饰（去瑕疵、肤色均匀、轻微磨皮且保留皮肤纹理），禁止“美颜”导致五官骨相变化"
            )

        ref_role_note = ""
        if is_photo_mode and len(refs) >= 2:
            ref_role_note = (
                "参考图说明（顺序不固定，必须自行识别角色）：\n"
                "- 参考图可能包含：1~2 张人物身份锚点 + 1 张目标场景/背景锚点（也可能只有人物或只有场景）\n"
                "- 常见任务：把人物迁移/插入到场景中；若存在两张不同人物锚点，则把两个人都插入同一场景并分别保持身份一致\n"
                "- 即使用户要求换衣服/换姿势/换动作：人物仍必须是同一个人（脸/头部完全不动；骨相/发型/体型不崩、不串脸、不平均脸）"
            )

        full_prompt = dedent(
            f"""
            【Photoshop 合成/再创作】
            工作模式：{mode_hint}
            目标画面比例：{used_aspect_ratio}

            你将收到若干参考图片（可能为 0~3 张，均由 bot 显式传入）请严格根据参考图与用户指令完成合成/再创作：
            {ref_role_note}
            - 执行范式（按官方 Nano Banana 编辑模板思路）：Using the provided image(s), please [add/remove/modify] ... Ensure ... integrate ...（不要输出这些文字，只输出最终图片）
            - 若用户要求“保留/继承”某张图的主体特征，请优先保证主体一致性（脸、发型、服装识别点等）
            - 若用户要求融合多张图，请明确哪些元素来自哪张参考图，并保持画面统一、自然
            - 不要添加水印、文字、边框、logo
            - 输出必须高画质、细节清晰；不要为了追求更大分辨率而牺牲画面质量
            - 只要求画面比例正确：{used_aspect_ratio}
            - 只输出最终图片，不要输出任何解释文本
            {photo_identity_lock}

            用户指令：
            {prompt}
            """
        ).strip()

        image_ref = await _generate_image(
            tool_host,
            config.PHOTOSHOP_MODEL_GROUP,
            full_prompt,
            system_prompt=config.PHOTOSHOP_SYSTEM_PROMPT,
            reference_images=prepared_refs or None,
            timeout=config.TIMEOUT,
            stream_mode=config.STREAM_MODE,
            image_detail="high",
        )
        result_image = await _load_image_from_ref(tool_host, image_ref)
        result_image = ImageOps.exif_transpose(result_image).convert("RGB")

        if is_photo_mode and len(prepared_refs) >= 2:
            try:
                composite_ref = _encode_image_to_data_uri(result_image, format="JPEG", quality=94, max_long_side=2560)
                refine_prompt = dedent(
                    f"""
                    【Photoshop 照片合成 - 身份锁定修复】
                    你将收到多张参考图（顺序不固定），以及 1 张“当前合成结果”（最后一张）
                    参考图可能包含 1~2 个不同人物 + 场景背景，也可能只有人物或只有场景

                    任务（必须遵守）：
                    - 以“当前合成结果”为底稿：尽量保持其构图、背景、光影、色彩、细节、动作与衣服改动不变
                    - 仅修正“人物身份一致性/脸部崩坏/串脸”：
                      - 对合成结果中每一个人物，匹配到参考图中最相似/对应的那个人，并把脸、五官骨相、发型特征严格修回一致
                      - 若参考图中存在两位不同人物，则合成结果中两个人必须分别对应两位人物，禁止平均脸/混合身份/互换脸
                      - 高保真细节保留：确保每个人脸的身份特征保持完全不变（remain completely unchanged），不要美颜改骨相（可保留皮肤纹理与真实瑕疵）
                    - 体格/身材/头身比例尽量不变（除非用户明确要求改变体型）
                    - 不要重做背景；不要引入新人物/新物体；不要添加文字/水印/边框
                    - 只输出最终图片，不要输出任何解释文本

                    原始用户指令（不要丢失其中的编辑目标）：
                    {prompt}
                """
                ).strip()
                refine_refs: List[Tuple[str, str]] = []
                for index, (data, _desc) in enumerate(prepared_refs, 1):
                    refine_refs.append((data, f"Reference #{index} (unordered)"))
                refine_refs.append((composite_ref, "Current composite (keep everything, fix identity drift only)"))
                refined = await _generate_image(
                    tool_host,
                    config.PHOTOSHOP_MODEL_GROUP,
                    refine_prompt,
                    system_prompt=config.PHOTOSHOP_SYSTEM_PROMPT,
                    reference_images=refine_refs,
                    timeout=config.TIMEOUT,
                    stream_mode=config.STREAM_MODE,
                    image_detail="high",
                )
                result_image = await _load_image_from_ref(tool_host, refined)
                result_image = ImageOps.exif_transpose(result_image).convert("RGB")
            except Exception:
                pass

        if ratio_value:
            result_image = _crop_to_aspect_ratio(result_image, ratio_value)

        current_long = max(result_image.width, result_image.height)
        desired_long = current_long
        hq_long = int(config.PHOTOSHOP_HQ_LONG_SIDE or 0)
        if hq_long > 0:
            desired_long = max(desired_long, hq_long)
        max_long = int(config.PHOTOSHOP_HQ_MAX_LONG_SIDE or 0)
        if max_long > 0:
            desired_long = max(current_long, min(desired_long, max_long))
        result_image = _upscale_to_long_side(result_image, desired_long)

        temp_path = f"/tmp/{uuid.uuid4().hex}.jpg"
        _save_image_as_jpeg(result_image, temp_path, quality=80)
        return await _finalize_image_success(
            _PHOTOSHOP_TOOL_ID,
            tool_host,
            image_ref=temp_path,
            file_name_hint=f"{_PHOTOSHOP_TOOL_ID}_{uuid.uuid4().hex[:8]}",
            trace_title="Tool | photoshop",
            text_notice="Photoshop 结果已生成，但未发送到聊天框",
            model_group=config.PHOTOSHOP_MODEL_GROUP,
        )
    except Exception as exc:
        return await _finalize_image_failure(
            _PHOTOSHOP_TOOL_ID,
            tool_host,
            model_group=config.PHOTOSHOP_MODEL_GROUP,
            error_prefix="Photoshop 生成失败",
            error=exc,
        )
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)


async def lightroom(
    prompt: str,
    image_path_or_url: str,
    tool_host: ToolHostBridge | None = None,
    tool_config: LightroomConfig | None = None,
) -> ToolOutcome:
    if tool_host is None:
        return _error_outcome(_LIGHTROOM_TOOL_ID, "lightroom 缺少 tool_host")
    config = tool_config or LightroomConfig()
    try:
        await _accept_magic_draw_request(_LIGHTROOM_TOOL_ID, tool_host, model_group=config.LIGHTROOM_MODEL_GROUP)
        image_ref = str(image_path_or_url or "").strip()
        if not image_ref:
            return _error_outcome(_LIGHTROOM_TOOL_ID, "lightroom 必须显式传入 image_path_or_url")
        source_size = await _get_image_size_from_ref(tool_host, image_ref)
        if not source_size:
            return _error_outcome(_LIGHTROOM_TOOL_ID, f"无法读取原图尺寸: {image_ref}")
        source_w, source_h = source_size
        source_img_data = await _resolve_ref_data_uri(tool_host, image_ref)
        target_ratio = source_w / source_h
        desired_long = max(source_w, source_h, int(config.LIGHTROOM_HQ_LONG_SIDE or 0))
        max_long = int(config.LIGHTROOM_HQ_MAX_LONG_SIDE or 0)
        if max_long > 0:
            desired_long = max(max(source_w, source_h), min(desired_long, max_long))
        full_prompt = dedent(
            f"""
            【Lightroom 照片修缮/美化】
            - 必须保持原图比例：{source_w}:{source_h}
            - 输出分辨率不得低于原图；允许适度超分辨率，但优先修图质量与真实质感
            - 人物一致性：若画面包含人物，禁止换人/换脸/改年龄性别种族；面部特征/五官骨相必须保持完全不变
            - 允许修瑕疵/磨皮/美化，但必须自然真实且保留皮肤纹理
            - 不要添加文字、水印、logo、边框
            - 只输出最终图片，不要输出任何解释文本

            用户修图要求：
            {prompt}
            """
        ).strip()
        generated = await _generate_image(tool_host, config.LIGHTROOM_MODEL_GROUP, full_prompt, system_prompt=config.LIGHTROOM_SYSTEM_PROMPT, reference_images=[(source_img_data, "Input photo (edit this)")], timeout=config.TIMEOUT, stream_mode=config.STREAM_MODE, image_detail="high")
        result_image = await _load_image_from_ref(tool_host, generated)
        result_image = ImageOps.exif_transpose(result_image).convert("RGB")
        result_image = _crop_to_aspect_ratio(result_image, target_ratio)
        if max(result_image.width, result_image.height) < desired_long:
            result_image = _upscale_to_long_side(result_image, desired_long)
        temp_path = f"/tmp/{uuid.uuid4().hex}.jpg"
        _save_image_as_jpeg(result_image, temp_path, quality=80)
        return await _finalize_image_success(
            _LIGHTROOM_TOOL_ID,
            tool_host,
            image_ref=temp_path,
            file_name_hint=f"{_LIGHTROOM_TOOL_ID}_{uuid.uuid4().hex[:8]}",
            trace_title="Tool | lightroom",
            text_notice="Lightroom 结果已生成，但未发送到聊天框",
            model_group=config.LIGHTROOM_MODEL_GROUP,
            cleanup_path=temp_path,
        )
    except Exception as exc:
        return await _finalize_image_failure(
            _LIGHTROOM_TOOL_ID,
            tool_host,
            model_group=config.LIGHTROOM_MODEL_GROUP,
            error_prefix="Lightroom 失败",
            error=exc,
        )
