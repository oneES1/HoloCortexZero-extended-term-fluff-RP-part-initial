from __future__ import annotations

from urllib.parse import urlsplit

UNIAPI_HOSTS = {"api.uniapi.io", "hk.uniapi.io"}


def normalize_target_host(raw: str | None) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    try:
        parsed = urlsplit(value if "://" in value else f"https://{value}")
    except Exception:
        return ""
    return str(parsed.hostname or "").strip().lower()


def is_uniapi_host(host: str | None) -> bool:
    return normalize_target_host(host) in UNIAPI_HOSTS


def is_uniapi_base_url(base_url: str | None) -> bool:
    return is_uniapi_host(base_url)
