from __future__ import annotations

import re


_CONTROL_CHAR_RE = re.compile(r"[\u0000-\u0008\u000B\u000C\u000E-\u001F]")
_WHITESPACE_RE = re.compile(r"\s+")
_OPEN_TO_CLOSE = {
    "(": ")",
    "[": "]",
    "（": "）",
    "【": "】",
}
_CLOSERS = set(_OPEN_TO_CLOSE.values())


def sanitize_voice_text(text: str) -> str:
    cleaned = _CONTROL_CHAR_RE.sub("", str(text or "")).strip()
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def strip_bracket_content(text: str) -> str:
    source = sanitize_voice_text(text)
    if not source:
        return ""

    remove_flags = [False] * len(source)
    stack: list[tuple[str, int, str]] = []

    for index, char in enumerate(source):
        expected = _OPEN_TO_CLOSE.get(char)
        if expected:
            stack.append((char, index, expected))
            continue

        if char in _CLOSERS:
            if stack and stack[-1][2] == char:
                _, open_index, _ = stack.pop()
                for remove_index in range(open_index, index + 1):
                    remove_flags[remove_index] = True
            else:
                remove_flags[index] = True

    for _, open_index, _ in stack:
        remove_flags[open_index] = True

    result = "".join(char for index, char in enumerate(source) if not remove_flags[index])
    return sanitize_voice_text(result)
