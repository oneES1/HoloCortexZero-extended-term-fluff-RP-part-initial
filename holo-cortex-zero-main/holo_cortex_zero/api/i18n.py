"""国际化 API

为扩展开发者提供国际化相关的工具和类型定义。

Example:
    ```python
    from HoloCortexZero.api.i18n import i18n_text, I18nDict, SupportedLang
    from pydantic import Field

    # 在配置中使用国际化
    MY_CONFIG: str = Field(
        default="value",
        title="我的配置",
        description="这是配置描述",
        json_schema_extra=ExtraField(
            i18n_title=i18n_text(
                zh_CN="我的配置",
                en_US="My Config",
            ),
            i18n_description=i18n_text(
                zh_CN="这是配置描述",
                en_US="This is config description",
            ),
        ).model_dump(),
    )
    ```
"""

from holo_cortex_zero.schemas.i18n import (
    I18nDict,
    SupportedLang,
    get_text,
    i18n_text,
)

__all__ = [
    "I18nDict",
    "SupportedLang",
    "get_text",
    "i18n_text",
]

