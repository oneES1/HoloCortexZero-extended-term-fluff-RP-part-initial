from __future__ import annotations

import asyncio

from holo_cortex_zero.core.config import ModelConfigGroup
from holo_cortex_zero.schemas.ir import GenerationResult, ToolCall
from holo_cortex_zero.services.llm import connectivity


async def main() -> None:
    seen_max_tokens: list[object] = []

    async def fake_generate(request, **_: object):
        seen_max_tokens.append(request.max_tokens)
        if len(seen_max_tokens) == 1:
            return GenerationResult(
                tool_calls=[
                    ToolCall(
                        id="probe_call_1",
                        name=connectivity.CONNECTIVITY_PROBE_TOOL_NAME,
                        arguments={"ping": "ok"},
                    )
                ],
                finish_reason="tool_calls",
                reasoning_content="real reasoning",
            )
        return GenerationResult(text="ok", finish_reason="stop")

    original_generate = connectivity.llm_router.generate
    connectivity.llm_router.generate = fake_generate
    try:
        details = await connectivity._probe_generation_group(
            ModelConfigGroup(
                CHAT_MODEL="test-model",
                BASE_URL="https://example.test/v1",
                API_KEY="test-key",
                MODEL_TYPE="chat",
            ),
            group_name="validate-no-forced-max-tokens",
            protocol="chat",
            proxy=None,
        )
    finally:
        connectivity.llm_router.generate = original_generate

    if seen_max_tokens != [None, None]:
        raise AssertionError(f"connectivity probe must not force max_tokens, got {seen_max_tokens!r}")
    if details["tool_calls"] != 1:
        raise AssertionError(f"expected one probe tool call, got {details!r}")
    print("OK connectivity no forced max_tokens: first=None second=None tool_calls=1")


if __name__ == "__main__":
    asyncio.run(main())
