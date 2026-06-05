from __future__ import annotations

import base64
import hashlib
import html
import json
import random
import re
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import parse_qs, urlparse

import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.schemas.chat_message import ChatMessageSegmentFile
from holo_cortex_zero.services.file_system.policy import AttachmentIngestMode, resolve_incoming_attachment_mode

_NETEASE_HOSTS = {"163cn.tv", "music.163.com", "y.music.163.com"}
_URL_RE = re.compile(r"https?://[^\s<>'\"，。！？；、]+")
_SONG_ID_PATTERNS = (
    re.compile(r"(?:[?&]id=|/song/)(\d{3,})"),
    re.compile(r"song\?[^\"'<>]*id=(\d{3,})"),
    re.compile(r'"id"\s*:\s*(\d{3,})'),
)
_EAPI_KEY = b"e82ckenh8dichen8"
_DFS_KEY = "3go8&$8*3*3h0k(2)2"
_MUSIC_FIELDS = ("bMusic", "lMusic", "mMusic", "hMusic")
_AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".oga", ".opus", ".webm"}
_METING_REDIRECT_URL = "https://api.injahow.cn/meting/"
_DEFAULT_HEADERS = {
    "User-Agent": "NeteaseMusic/9.2.0.231100 CFNetwork/1490.0.4 Darwin/23.2.0",
    "Accept": "*/*",
}


@dataclass(frozen=True)
class NeteaseShare:
    song_id: str
    source_url: str


@dataclass(frozen=True)
class NeteaseAudioCandidate:
    url: str
    file_name: str
    mime_type: str
    bitrate: int
    size: int
    source: str


@dataclass(frozen=True)
class NeteaseResolveResult:
    share: Optional[NeteaseShare]
    candidate: Optional[NeteaseAudioCandidate]
    reason: str


def _segment_value(segment: Any, key: str) -> str:
    if isinstance(segment, dict):
        return str(segment.get(key) or "").strip()
    return str(getattr(segment, key, "") or "").strip()


def _is_netease_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host in _NETEASE_HOSTS or host.endswith(".music.163.com")


def _clean_url(raw_url: str) -> str:
    cleaned = html.unescape(str(raw_url or "").strip())
    return cleaned.rstrip(").,，。!！?？;；")


def extract_netease_urls(platform_message: Any) -> list[str]:
    texts: list[str] = [str(getattr(platform_message, "content_text", "") or "")]
    for segment in list(getattr(platform_message, "content_data", []) or []):
        texts.append(_segment_value(segment, "text"))
        texts.append(_segment_value(segment, "card_url"))

    urls: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for match in _URL_RE.findall(text or ""):
            url = _clean_url(match)
            if not url or url in seen or not _is_netease_url(url):
                continue
            seen.add(url)
            urls.append(url)
    return urls


def _extract_song_id_from_text(text: str) -> Optional[str]:
    source = html.unescape(str(text or ""))
    for pattern in _SONG_ID_PATTERNS:
        match = pattern.search(source)
        if match:
            return match.group(1)
    return None


def _extract_song_id_from_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    query_id = parse_qs(parsed.query).get("id", [""])[0]
    if str(query_id).isdigit():
        return str(query_id)
    return _extract_song_id_from_text(url)


async def resolve_share_url(url: str, client: httpx.AsyncClient) -> Optional[NeteaseShare]:
    cleaned = _clean_url(url)
    song_id = _extract_song_id_from_url(cleaned)
    if song_id:
        return NeteaseShare(song_id=song_id, source_url=cleaned)

    try:
        response = await client.get(cleaned, follow_redirects=True)
    except httpx.RequestError:
        return None

    final_url = str(response.url)
    song_id = _extract_song_id_from_url(final_url) or _extract_song_id_from_text(response.text[:200_000])
    if not song_id:
        return None
    return NeteaseShare(song_id=song_id, source_url=cleaned)


def _eapi_params(path: str, payload: dict[str, Any]) -> dict[str, str]:
    text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.md5(f"nobody{path}use{text}md5forencrypt".encode("utf-8")).hexdigest()
    raw = f"{path}-36cd479b6b5-{text}-36cd479b6b5-{digest}"
    encrypted = AES.new(_EAPI_KEY, AES.MODE_ECB).encrypt(pad(raw.encode("utf-8"), AES.block_size))
    return {"params": encrypted.hex().upper()}


async def _post_eapi_song_url(song_id: str, client: httpx.AsyncClient) -> Iterable[NeteaseAudioCandidate]:
    path = "/api/song/enhance/player/url/v1"
    device_id = "".join(random.choice(string.hexdigits.lower()) for _ in range(32))
    payload = {
        "ids": f"[{song_id}]",
        "level": "standard",
        "encodeType": "mp3",
        "csrf_token": "",
        "header": json.dumps(
            {"os": "ios", "appver": "9.2.0", "deviceId": device_id},
            separators=(",", ":"),
        ),
    }
    response = await client.post(
        "https://interface3.music.163.com/eapi/song/enhance/player/url/v1",
        data=_eapi_params(path, payload),
        headers={**_DEFAULT_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
    )
    response.raise_for_status()
    return _candidates_from_player_payload(song_id, response.json(), source="eapi")


async def _get_public_player_candidates(song_id: str, client: httpx.AsyncClient) -> Iterable[NeteaseAudioCandidate]:
    candidates: list[NeteaseAudioCandidate] = []
    for bitrate in (64_000, 128_000):
        response = await client.get(
            "https://music.163.com/api/song/enhance/player/url",
            params={"ids": f"[{song_id}]", "br": str(bitrate)},
            headers=_DEFAULT_HEADERS,
        )
        response.raise_for_status()
        candidates.extend(_candidates_from_player_payload(song_id, response.json(), source=f"public_{bitrate}"))
    return candidates


async def _get_legacy_detail_candidates(song_id: str, client: httpx.AsyncClient) -> Iterable[NeteaseAudioCandidate]:
    response = await client.get(
        "https://music.163.com/api/song/detail/",
        params={"id": song_id, "ids": f"[{song_id}]"},
        headers=_DEFAULT_HEADERS,
    )
    response.raise_for_status()
    payload = response.json()
    songs = payload.get("songs") if isinstance(payload, dict) else None
    if not songs:
        return []

    song = songs[0] if isinstance(songs[0], dict) else {}
    candidates: list[NeteaseAudioCandidate] = []
    for field in _MUSIC_FIELDS:
        item = song.get(field)
        if not isinstance(item, dict):
            continue
        dfs_id = str(item.get("dfsId") or item.get("id") or "").strip()
        if not dfs_id.isdigit():
            continue
        ext = str(item.get("extension") or "mp3").strip().lower().lstrip(".") or "mp3"
        bitrate = int(item.get("bitrate") or 0)
        size = int(item.get("size") or 0)
        url = _build_legacy_dfs_url(dfs_id, ext)
        candidates.append(
            NeteaseAudioCandidate(
                url=url,
                file_name=f"netease_{song_id}_{bitrate or 'lowest'}.{ext}",
                mime_type="audio/mpeg" if ext == "mp3" else f"audio/{ext}",
                bitrate=bitrate,
                size=size,
                source=f"legacy_{field}",
            )
        )
    return candidates


async def _get_meting_redirect_candidates(song_id: str, client: httpx.AsyncClient) -> Iterable[NeteaseAudioCandidate]:
    response = await client.get(
        _METING_REDIRECT_URL,
        params={"server": "netease", "type": "url", "id": song_id},
        follow_redirects=False,
        headers=_DEFAULT_HEADERS,
    )
    if response.status_code not in {301, 302, 303, 307, 308}:
        return []

    url = str(response.headers.get("location") or "").strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not url.startswith(("http://", "https://")) or not host.endswith(".music.126.net"):
        return []

    ext = Path(parsed.path).suffix.lower().lstrip(".") or "mp3"
    return [
        NeteaseAudioCandidate(
            url=url,
            file_name=f"netease_{song_id}_preview.{ext}",
            mime_type="audio/mpeg" if ext == "mp3" else f"audio/{ext}",
            bitrate=0,
            size=0,
            source="meting_netease_redirect",
        )
    ]


def _candidates_from_player_payload(song_id: str, payload: Any, *, source: str) -> list[NeteaseAudioCandidate]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    candidates: list[NeteaseAudioCandidate] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        bitrate = int(item.get("br") or 0)
        size = int(item.get("size") or 0)
        ext = str(item.get("type") or item.get("encodeType") or "mp3").strip().lower().lstrip(".") or "mp3"
        candidates.append(
            NeteaseAudioCandidate(
                url=url,
                file_name=f"netease_{song_id}_{bitrate or 'lowest'}.{ext}",
                mime_type="audio/mpeg" if ext == "mp3" else f"audio/{ext}",
                bitrate=bitrate,
                size=size,
                source=source,
            )
        )
    return candidates


def _build_legacy_dfs_url(dfs_id: str, ext: str) -> str:
    mixed = "".join(chr(ord(dfs_id[index]) ^ ord(_DFS_KEY[index % len(_DFS_KEY)])) for index in range(len(dfs_id)))
    digest = base64.b64encode(hashlib.md5(mixed.encode("utf-8")).digest()).decode("ascii")
    encoded = digest.replace("/", "_").replace("+", "-")
    return f"https://m10.music.126.net/{encoded}/{dfs_id}.{ext}"


def _looks_like_audio(candidate: NeteaseAudioCandidate, content_type: str) -> bool:
    mime = str(content_type or "").split(";", 1)[0].strip().lower()
    if mime.startswith("audio/"):
        return True
    return Path(urlparse(candidate.url).path).suffix.lower() in _AUDIO_EXTS


def _content_starts_like_audio(content: bytes) -> bool:
    if not content:
        return True
    stripped = content.lstrip()
    if stripped.lower().startswith((b"<html", b"<!doctype")) or stripped.startswith((b"{", b"[")):
        return False
    return content.startswith((b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"OggS", b"fLaC", b"RIFF"))


async def _verify_candidate(
    candidate: NeteaseAudioCandidate,
    client: httpx.AsyncClient,
    *,
    max_bytes: int,
) -> Optional[NeteaseAudioCandidate]:
    if candidate.size and candidate.size > max_bytes:
        return None

    try:
        response = await client.head(candidate.url, follow_redirects=True, headers=_DEFAULT_HEADERS)
        if response.status_code == 405:
            raise httpx.HTTPStatusError("HEAD not allowed", request=response.request, response=response)
        response.raise_for_status()
    except Exception:
        response = await client.get(
            candidate.url,
            follow_redirects=True,
            headers={**_DEFAULT_HEADERS, "Range": "bytes=0-4095"},
        )
        if response.status_code not in {200, 206}:
            return None
        if not _content_starts_like_audio(response.content):
            return None

    length = response.headers.get("content-length")
    if length and length.isdigit() and int(length) > max_bytes:
        return None

    content_type = response.headers.get("content-type", "")
    if not _looks_like_audio(candidate, content_type):
        return None

    mime_type = str(content_type).split(";", 1)[0].strip() or candidate.mime_type
    size = candidate.size or (int(length) if length and length.isdigit() else 0)
    return NeteaseAudioCandidate(
        url=candidate.url,
        file_name=candidate.file_name,
        mime_type=mime_type,
        bitrate=candidate.bitrate,
        size=size,
        source=candidate.source,
    )


async def fetch_lowest_audio_candidate(
    song_id: str,
    client: httpx.AsyncClient,
    *,
    max_bytes: int,
) -> NeteaseResolveResult:
    share = NeteaseShare(song_id=song_id, source_url="")
    providers = (
        _post_eapi_song_url,
        _get_public_player_candidates,
        _get_legacy_detail_candidates,
        _get_meting_redirect_candidates,
    )
    rejected = 0

    for provider in providers:
        try:
            raw_candidates = list(await provider(song_id, client))
        except httpx.RequestError:
            return NeteaseResolveResult(share=share, candidate=None, reason="network_unavailable")
        except Exception as exc:
            logger.info("netease candidate provider failed: provider=%s err=%s", provider.__name__, type(exc).__name__)
            continue

        raw_candidates.sort(key=lambda item: ((item.bitrate or 10**9), (item.size or 10**12)))
        for candidate in raw_candidates:
            verified = await _verify_candidate(candidate, client, max_bytes=max_bytes)
            if verified:
                return NeteaseResolveResult(share=share, candidate=verified, reason="ok")
            rejected += 1

    return NeteaseResolveResult(
        share=share,
        candidate=None,
        reason="no_valid_audio_candidate" if rejected else "no_candidate",
    )


async def _download_candidate_bytes(
    candidate: NeteaseAudioCandidate,
    client: httpx.AsyncClient,
    *,
    max_bytes: int,
) -> bytes:
    response = await client.get(candidate.url, follow_redirects=True, headers=_DEFAULT_HEADERS)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if not _looks_like_audio(candidate, content_type):
        raise ValueError("netease candidate response is not audio")
    content = response.content
    if not _content_starts_like_audio(content[:4096]):
        raise ValueError("netease candidate response is not audio")
    if len(content) > max_bytes:
        raise ValueError("netease audio exceeds max size")
    return content


async def fetch_netease_audio_from_message(
    platform_message: Any,
    *,
    from_chat_key: str,
    max_bytes: int,
    ingest_mode: AttachmentIngestMode = "managed",
) -> Optional[ChatMessageSegmentFile]:
    urls = extract_netease_urls(platform_message)
    if not urls:
        return None

    timeout = httpx.Timeout(connect=8.0, read=30.0, write=10.0, pool=5.0)
    async with httpx.AsyncClient(
        timeout=timeout,
        proxy=None,
        trust_env=False,
        follow_redirects=True,
    ) as client:
        for url in urls:
            share = await resolve_share_url(url, client)
            if not share:
                continue
            result = await fetch_lowest_audio_candidate(share.song_id, client, max_bytes=max_bytes)
            if not result.candidate:
                logger.info("netease audio unavailable: song_id=%s reason=%s", share.song_id, result.reason)
                continue
            try:
                data = await _download_candidate_bytes(result.candidate, client, max_bytes=max_bytes)
                return await ChatMessageSegmentFile.create_from_bytes(
                    data,
                    from_chat_key=from_chat_key,
                    file_name=result.candidate.file_name,
                    ingest_mode=ingest_mode,
                    mime_type=result.candidate.mime_type,
                )
            except Exception as exc:
                logger.info(
                    "netease audio download failed: song_id=%s source=%s err=%s",
                    share.song_id,
                    result.candidate.source,
                    type(exc).__name__,
                )
                continue
    return None


async def append_netease_audio_from_message(
    platform_message: Any,
    *,
    adapter_key: str,
    chat_key: str,
    chat_type: str,
    sender_id: str,
    platform_userid: str,
    max_bytes: int,
) -> bool:
    ingest_mode, _ = resolve_incoming_attachment_mode(
        adapter_key=adapter_key,
        chat_key=chat_key,
        chat_type=chat_type,
        sender_id=sender_id,
        platform_userid=platform_userid,
        attachment_kind="audio",
        channel_type=chat_type,
    )
    if ingest_mode == "disabled":
        return False

    audio_segment = await fetch_netease_audio_from_message(
        platform_message,
        from_chat_key=chat_key,
        max_bytes=max_bytes,
        ingest_mode=ingest_mode,
    )
    if not audio_segment:
        return False
    platform_message.content_data.append(audio_segment)
    return True
