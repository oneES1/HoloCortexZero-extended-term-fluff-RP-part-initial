import base64
import hashlib
import mimetypes
import random
import re
from pathlib import Path
from typing import Tuple

import httpx
import magic
import toml

from holo_cortex_zero.core import config
from holo_cortex_zero.core.logger import logger
from holo_cortex_zero.core.config import CoreConfig
from holo_cortex_zero.core.os_env import USER_UPLOAD_DIR
from holo_cortex_zero.core.proxy_utils import normalize_proxy_url

_APP_VERSION: str = ""


def is_url_path(path: str) -> bool:
    return str(path or "").startswith(("http://", "https://"))


def get_app_version() -> str:
    """获取当前应用版本号

    Returns:
        str: 应用版本号
    """
    global _APP_VERSION
    if _APP_VERSION:
        return _APP_VERSION
    pyproject = toml.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    try:
        _APP_VERSION = pyproject["project"]["version"]
    except KeyError:
        _APP_VERSION = "unknown"
    return _APP_VERSION


async def download_file(
    url: str,
    file_path: str = "",
    file_name: str = "",
    use_suffix: str = "",
    retry_count: int = 3,
    from_chat_key: str = "",
) -> Tuple[str, str]:
    """下载文件

    Args:
        url (str): 下载链接
        file_path (str): 保存路径

    Returns:
        Tuple[str, str]: 文件路径, 文件名
    """

    try:
        proxy = normalize_proxy_url(str(getattr(config, "DEFAULT_PROXY", "") or "").strip() or None)
        async with httpx.AsyncClient(proxy=proxy, trust_env=False) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content
            if not use_suffix:
                mime = magic.from_buffer(content, mime=True)
                use_suffix = f'.{mime.split("/")[1]}' if mime and len(mime.split("/")) > 1 else ""
            if not file_path:
                file_name = file_name or f"{hashlib.md5(response.content).hexdigest()}{use_suffix}"
                if from_chat_key:
                    save_path = Path(USER_UPLOAD_DIR) / from_chat_key / Path(file_name)
                else:
                    save_path = Path(USER_UPLOAD_DIR) / Path(file_name)
                save_path.parent.mkdir(parents=True, exist_ok=True)
                file_path = str(save_path)
            Path(file_path).write_bytes(content)
            Path(file_path).chmod(0o664)
    except Exception:
        if retry_count > 0:
            return await download_file(
                url,
                file_path,
                file_name,
                use_suffix,
                retry_count=retry_count - 1,
                from_chat_key=from_chat_key,
            )
        raise
    else:
        return file_path, file_name


async def download_file_from_bytes(
    bytes_data: bytes,
    file_path: str = "",
    file_name: str = "",
    use_suffix: str = "",
    from_chat_key: str = "",
) -> Tuple[str, str]:
    """下载文件

    Args:
        url (str): 下载链接
        file_path (str): 保存路径

    Returns:
        Tuple[str, str]: 文件路径, 文件名
    """

    if not file_path:
        file_name = file_name or f"{hashlib.md5(bytes_data).hexdigest()}{use_suffix}"
        if from_chat_key:
            save_path = Path(USER_UPLOAD_DIR) / from_chat_key / Path(file_name)
        else:
            save_path = Path(USER_UPLOAD_DIR) / Path(file_name)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        file_path = str(save_path)
    Path(file_path).write_bytes(bytes_data)
    Path(file_path).chmod(0o664)
    return file_path, file_name


async def download_file_from_base64(
    base64_str: str,
    file_path: str = "",
    file_name: str = "",
    use_suffix: str = "",
    from_chat_key: str = "",
) -> Tuple[str, str]:
    """下载文件(从base64字符串)

    Args:
        base64_str (str): base64字符串
        file_path (str): 保存路径

    Returns:
        Tuple[str, str]: 文件路径, 文件名
    """
    logger.debug(f"下载文件(从base64字符串): {base64_str[:100]}")
    if base64_str.startswith("data:") and not use_suffix:
        mime_type = mimetypes.guess_type(base64_str)[0] or ""
        use_suffix = f".{mime_type.split('/')[1]}" if mime_type and len(mime_type.split("/")) > 1 else ""
    if base64_str.startswith("data:"):
        base64_str = base64_str.split(",")[1]

    if not file_path:
        file_name = file_name or f"{hashlib.md5(base64_str.encode()).hexdigest()}{use_suffix}"
        if from_chat_key:
            save_path = Path(USER_UPLOAD_DIR) / from_chat_key / Path(file_name)
        else:
            save_path = Path(USER_UPLOAD_DIR) / Path(file_name)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        file_path = str(save_path)
    Path(file_path).write_bytes(base64.b64decode(base64_str.encode(encoding="utf-8")))
    Path(file_path).chmod(0o664)
    return file_path, file_name


async def copy_to_upload_dir(
    file_path: str,
    file_name: str = "",
    use_suffix: str = "",
    from_chat_key: str = "",
) -> Tuple[str, str]:
    """复制文件到上传目录

    Args:
        file_path (str): 文件路径
        file_name (str): 文件名

    Returns:
        Tuple[str, str]: 文件路径, 文件名
    """
    if not file_name:
        file_name = f"{hashlib.md5(Path(file_path).read_bytes()).hexdigest()}{use_suffix}"
    if from_chat_key:
        save_path = Path(USER_UPLOAD_DIR) / from_chat_key / Path(file_name)
    else:
        save_path = Path(USER_UPLOAD_DIR) / Path(file_name)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    Path(save_path).write_bytes(Path(file_path).read_bytes())
    Path(save_path).chmod(0o664)
    return str(save_path), file_name


def random_chat_check(config: CoreConfig) -> bool:
    """随机聊天检测

    Returns:
        bool: 是否随机聊天
    """

    return random.random() < config.AI_CHAT_RANDOM_REPLY_PROBABILITY


def check_content_trigger(content: str, config: CoreConfig) -> bool:
    """内容触发检测

    Args:
        content (str): 内容

    Returns:
        bool: 是否触发
    """

    for reg_text in config.AI_CHAT_TRIGGER_REGEX:
        reg = re.compile(reg_text)
        if reg.search(content):
            return True
    return False


def check_forbidden_message(content: str, config: CoreConfig) -> bool:
    """忽略消息检测

    Args:
        content (str): 内容

    Returns:
        bool: 是否忽略
    """

    for reg_text in config.AI_CHAT_IGNORE_REGEX:
        reg = re.compile(reg_text)
        _r = reg.search(content)
        if _r:
            logger.info(f'忽略消息: "{content}" - 命中正则: "{reg_text}" 匹配内容: "{_r.group(0)}"')
            return True
    return False


def limited_text_output(text: str, limit: int = 1000, placeholder: str = "...") -> str:
    """限制文本输出

    Args:
        text (str): 文本
        limit (int): 限制长度
    """

    if len(text) <= limit:
        return text
    left_limit = limit // 2 - len(placeholder) // 2
    right_limit = limit - left_limit
    return text[:left_limit] + placeholder + text[-right_limit:]
