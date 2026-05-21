import re

from holo_cortex_zero.core.logger import logger


_BOT_SURFACE_PHRASES_FIRST_PASS = (
    "也不跑",
    "也不催你",
    "也不分开",
    "也不丢下你",
    "从后台数据流中抬起头",
)
_BOT_SURFACE_PHRASES_SECOND_PASS = (
    "不跑",
    "不催你",
    "不分开",
    "不丢下你",
    "从后台数据流中",
)
_BOT_SURFACE_LEADING_PATTERN = re.compile(r"^(?:(?:[\s，嗯]+)|(?:群聊模式，?|私聊模式，?|群聊))+")


def _remove_bot_surface_phrases(text: str) -> str:
    cleaned = text
    # 主干清洗：先清完整句，再清短核心，避免完整句被拆成残片后漏网。
    for phrase in _BOT_SURFACE_PHRASES_FIRST_PASS:
        cleaned = cleaned.replace(phrase, "")
    for phrase in _BOT_SURFACE_PHRASES_SECOND_PASS:
        cleaned = cleaned.replace(phrase, "")
    return cleaned


def _collapse_bot_surface_punctuation(text: str) -> str:
    cleaned = text
    while True:
        before = cleaned
        cleaned = cleaned.replace("，，", "，")
        cleaned = cleaned.replace("，。", "。")
        cleaned = cleaned.replace("。，", "。")
        cleaned = cleaned.replace("。。", "。")
        if cleaned == before:
            break
    cleaned = re.sub(r"(?:，。)+$", "", cleaned)
    return cleaned


def fix_raw_response(raw_response: str) -> str:
    """修复原始响应"""
    raw_response = str(raw_response or "")
    before_markdown_bold_cleanup = raw_response

    raw_response = raw_response.replace("[id:", "[@id:")
    raw_response = raw_response.replace("@[id:", "[@id:")
    raw_response = re.sub(r"\[@id:(\d+)\]", r"[@id:\1@]", raw_response)
    raw_response = re.sub(r"\[@id:(\d+);nickname[\=\:](.+);?\]", r"[@id:\1@]", raw_response)
    raw_response = re.sub(r"\(@id:(\d+);\)", r"[@id:\1@]", raw_response)
    raw_response = re.sub(r"\(@id:(\d+);nickname[\=\:](.+);?\)", r"[@id:\1@]", raw_response)
    raw_response = re.sub(r"\[@(\d+)\]", r"[@id:\1@]", raw_response)
    raw_response = re.sub(r"\(@id:(\d+)@\)", r"[@id:\1@]", raw_response)
    raw_response = re.sub(r"\(@id:(\d+)\)", r"[@id:\1@]", raw_response)
    raw_response = re.sub(r"\( ?@(\d+)@ ?\)", r"[@id:\1@]", raw_response)
    raw_response = re.sub(r"<\w{8} ?\| At:\[@id:(\d+)@\]>", r"[@id:\1@]", raw_response)
    raw_response = re.sub(r"\(@\[@id:(\d+)@\]\)", r"[@id:\1@]", raw_response)
    raw_response = re.sub(r"<@(\d+)>", r"[@id:\1@]", raw_response)
    raw_response = re.sub(r"@(\d+)@\)", r"[@id:\1@]", raw_response)
    raw_response = re.sub(r"\( ?@(\d+) ?\)", r"[@id:\1@]", raw_response)
    raw_response = re.sub(r"@(\d+)@ ?\)", r"[@id:\1@]", raw_response)

    reg = r"<\w{8} \| message separator>"
    match = re.search(reg, raw_response)
    if match:
        raw_response = raw_response[: match.start()]

    for tag in ("<think>", "</think>"):
        if raw_response.count(tag) > 1 and raw_response.endswith(tag):
            raw_response = raw_response[: -len(tag)]

    raw_response = re.sub(
        r"(?<=[㐀-鿿])\s*\*\*\s*([\s\S]+?)\s*\*\*\s*(?=[㐀-鿿])",
        r"\1",
        raw_response,
    )
    raw_response = re.sub(r"\*\*\s*([\s\S]+?)\s*\*\*", r"\1", raw_response)
    if raw_response != before_markdown_bold_cleanup:
        logger.info(
            "bot markdown 加粗标记已清洗: before=%r after=%r",
            before_markdown_bold_cleanup[:80],
            raw_response[:80],
        )

    before_phrase_cleanup = raw_response
    raw_response = _remove_bot_surface_phrases(raw_response)
    if raw_response != before_phrase_cleanup:
        logger.info(
            "bot 固定短句表层清洗已执行: before=%r after=%r",
            before_phrase_cleanup[:80],
            raw_response[:80],
        )

    raw_response = re.sub(r"\s*[\r\n]+\s*", " ", raw_response)
    raw_response = re.sub(r"[～~]+", "", raw_response)
    raw_response = re.sub(r"([㐀-鿿])\s+(?=[㐀-鿿A-Za-z0-9])", r"\1，", raw_response)
    raw_response = re.sub(r" {2,}", " ", raw_response)
    raw_response = _collapse_bot_surface_punctuation(raw_response)
    raw_response = re.sub(r"[。.]+(?=(?:\s|$))", "", raw_response)
    raw_response = re.sub(r"([㐀-鿿])\s+(?=[㐀-鿿A-Za-z0-9])", r"\1，", raw_response)
    raw_response = re.sub(r" {2,}", " ", raw_response)
    raw_response = _collapse_bot_surface_punctuation(raw_response)

    return raw_response.strip()


def normalize_bot_surface_text(raw_response: str) -> str:
    """统一 bot/assistant 可见文本清洗主干。"""
    normalized = fix_raw_response(raw_response).strip()
    if not normalized:
        return ""

    cleaned = re.sub(r"^bot\s*[:：]\s*", "", normalized, count=1, flags=re.IGNORECASE).strip()
    if cleaned != normalized:
        logger.info(
            "bot 文本检测到旧前缀污染，已剥离: raw_prefix=%r cleaned_prefix=%r",
            normalized[:24],
            cleaned[:24],
        )

    final_cleaned = _BOT_SURFACE_LEADING_PATTERN.sub("", cleaned).strip()
    if final_cleaned != cleaned:
        logger.info(
            "bot 文本最终前缀清洗已执行: before=%r after=%r",
            cleaned[:24],
            final_cleaned[:24],
        )
    return final_cleaned
