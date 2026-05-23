from __future__ import annotations

from holo_cortex_zero.schemas.ir import GenerationRequest, GenerationResult, MessagePart, MessageTurn
from holo_cortex_zero.services.llm.router import LLMRouter


def request(*, replay: bool) -> GenerationRequest:
    return GenerationRequest(
        context_id="validate-reasoning-persistence-gate",
        model="gate-model",
        messages=[MessageTurn(role="user", parts=[MessagePart(type="text", text="hi")])],
        extra_params={"replay_reasoning_content": True} if replay else {},
    )


def result(reasoning: str | None) -> GenerationResult:
    return GenerationResult(text="ok", reasoning_content=reasoning)


def main() -> None:
    router = LLMRouter()

    no_replay = request(replay=False)
    no_replay_result = result("hidden reasoning from provider")
    filtered = router._filter_result_reasoning_content(no_replay_result, request=no_replay)
    if filtered.reasoning_content is not None:
        raise AssertionError("no-replay model group must not expose reasoning_content to persistence")

    replay = request(replay=True)
    replay_result = result("hidden reasoning from provider")
    kept = router._filter_result_reasoning_content(replay_result, request=replay)
    if kept.reasoning_content != "hidden reasoning from provider":
        raise AssertionError("replay-enabled model group must keep reasoning_content")

    no_reasoning = result(None)
    same = router._filter_result_reasoning_content(no_reasoning, request=no_replay)
    if same.reasoning_content is not None:
        raise AssertionError("empty reasoning should stay empty")

    print("OK reasoning persistence gate: no_replay=dropped replay=kept empty=unchanged")


if __name__ == "__main__":
    main()
