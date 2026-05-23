from __future__ import annotations

from typing import Any, Optional

from holo_cortex_zero.core.config import config
from holo_cortex_zero.core.logger import logger


def normalize_proxy_url(proxy_url: Optional[str]) -> Optional[str]:
    if not proxy_url:
        return None
    url = str(proxy_url).strip()
    if not url:
        return None
    lower_url = url.lower()
    if lower_url.startswith("socks5h://"):
        return f"socks5://{url[len('socks5h://') :]}"
    if lower_url.startswith("socks://"):
        return f"socks5://{url[len('socks://') :]}"
    return url


def resolve_model_group_proxy(model_group: Any, *, group_key: str = "", source: str = "") -> Optional[str]:
    use_global_proxy = bool(getattr(model_group, "USE_GLOBAL_PROXY", False))
    legacy_proxy = normalize_proxy_url(str(getattr(model_group, "CHAT_PROXY", "") or "").strip() or None)
    if not use_global_proxy:
        return legacy_proxy

    global_proxy = normalize_proxy_url(str(getattr(config, "DEFAULT_PROXY", "") or "").strip() or None)
    if global_proxy:
        logger.debug(
            f"模型组代理解析命中全局代理: group={group_key or getattr(model_group, 'GROUP_NAME', '') or ''} "
            f"source={source or ''} proxy={global_proxy}"
        )
        return global_proxy

    logger.warning(
        f"模型组启用了全局代理，但 DEFAULT_PROXY 为空: "
        f"group={group_key or getattr(model_group, 'GROUP_NAME', '') or ''} source={source or ''}"
    )
    return None
