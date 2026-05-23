"""HoloCortexZero API

此包提供了 HoloCortexZero 的公共 API 接口，用于扩展开发。

Example:
    ```python
    from holo_cortex_zero.api import message, core, i18n

    # 发送消息
    await message.send_text(_ck, "你好，世界！", ctx)

    # 使用核心功能
    core.logger.info("这是一条日志")

    ```
"""

from holo_cortex_zero.api import core, i18n, message, schemas

__all__ = [
    "core",
    "i18n",
    "message",
    "schemas",
]
