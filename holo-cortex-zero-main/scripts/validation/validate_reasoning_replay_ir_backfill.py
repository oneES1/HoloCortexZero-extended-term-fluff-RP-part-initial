from __future__ import annotations

from holo_cortex_zero.schemas.ir import GenerationRequest, MessagePart, MessageTurn, ToolCall
from holo_cortex_zero.services.llm.router import LLMRouter
from holo_cortex_zero.services.llm.reasoning_text import build_reasoning_content


def tool_call(call_id: str, name: str = "weather") -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments={"location": "北京"})


def assistant_tool(call_id: str, reasoning_content: str | None = None) -> MessageTurn:
    return MessageTurn(
        role="assistant",
        parts=[],
        tool_calls=[tool_call(call_id)],
        reasoning_content=reasoning_content,
    )


def tool_result(call_id: str) -> MessageTurn:
    return MessageTurn(
        role="tool",
        parts=[MessagePart(type="text", text="晴，20℃")],
        tool_call_id=call_id,
    )


def user(text: str) -> MessageTurn:
    return MessageTurn(role="user", parts=[MessagePart(type="text", text=text)])


def request(messages: list[MessageTurn], replay: bool, model: str) -> GenerationRequest:
    return GenerationRequest(
        context_id="validate-reasoning-replay-ir",
        model=model,
        messages=messages,
        tools=[tool_call("tool_template")],
        stream=False,
        extra_params={"replay_reasoning_content": True} if replay else {},
    )


def assert_reasoning(turn: MessageTurn, expected: str | None, label: str) -> None:
    actual = turn.reasoning_content
    if actual != expected:
        raise AssertionError(f"{label}: expected reasoning={expected!r}, got {actual!r}")


def assert_same_object(actual: GenerationRequest, original: GenerationRequest, label: str) -> None:
    if actual is not original:
        raise AssertionError(f"{label}: request should not be cloned")


def assert_cloned(actual: GenerationRequest, original: GenerationRequest, label: str) -> None:
    if actual is original:
        raise AssertionError(f"{label}: request should be cloned")


def main() -> None:
    router = LLMRouter()
    placeholder = router.REASONING_REPLAY_TOOL_CALL_PLACEHOLDER
    qwen_real_reasoning = "uniqwen 真实思维链"
    gemini_reasoning = build_reasoning_content(
        text="gemini 文本思维链",
        gemini_thought_signatures=["sig-gemini-1"],
        origin_protocol="gemini",
    )
    if not gemini_reasoning:
        raise AssertionError("gemini reasoning envelope should be non-empty")

    history: list[MessageTurn] = [user("开始严格链式验证")]
    history.append(MessageTurn(role="assistant", parts=[MessagePart(type="text", text="tool 前普通 assistant")]))

    # 1. 不开回填组 tool 调用：不补。
    history.extend([assistant_tool("tool_no_replay_1"), tool_result("tool_no_replay_1")])
    req1 = request(history, replay=False, model="no-replay-a")
    out1 = router._ensure_reasoning_replay_for_tool_calls(req1)
    assert_same_object(out1, req1, "step1 no replay group must not mutate")
    assert_reasoning(out1.messages[1], None, "step1 pre-tool assistant unchanged")
    assert_reasoning(out1.messages[2], None, "step1 no replay tool")

    # 2. 后接 uniqwen 有思维组回填组 tool 调用：历史空 tool 补句号，新 tool 保留真实思维链。
    history.extend([assistant_tool("tool_uniqwen_thinking", qwen_real_reasoning), tool_result("tool_uniqwen_thinking")])
    req2 = request(history, replay=True, model="uniqwen-thinking")
    out2 = router._ensure_reasoning_replay_for_tool_calls(req2)
    assert_cloned(out2, req2, "step2 replay with old blank tool should clone")
    assert_reasoning(out2.messages[1], None, "step2 pre-tool assistant not backfilled")
    assert_reasoning(out2.messages[2], placeholder, "step2 old no-replay tool backfilled")
    assert_reasoning(out2.messages[4], qwen_real_reasoning, "step2 uniqwen real reasoning preserved")
    assert_reasoning(req2.messages[2], None, "step2 original request untouched")

    history = out2.messages

    # 3. uniqwen 无思维组续接回复：tool_result 之后的普通 assistant 也补句号。
    history.append(MessageTurn(role="assistant", parts=[MessagePart(type="text", text="续接回复")]))
    req3 = request(history, replay=True, model="uniqwen-no-thinking-followup")
    out3 = router._ensure_reasoning_replay_for_tool_calls(req3)
    assert_cloned(out3, req3, "step3 post-tool assistant blank should clone")
    assert_reasoning(out3.messages[1], None, "step3 pre-tool assistant still not backfilled")
    assert_reasoning(out3.messages[2], placeholder, "step3 placeholder kept")
    assert_reasoning(out3.messages[4], qwen_real_reasoning, "step3 real reasoning kept")
    assert_reasoning(out3.messages[-1], placeholder, "step3 post-tool assistant backfilled")

    # 4. 再不开回填组再 tool：不开时新增空 tool 不补。
    history = out3.messages + [assistant_tool("tool_no_replay_2"), tool_result("tool_no_replay_2")]
    req4 = request(history, replay=False, model="no-replay-b")
    out4 = router._ensure_reasoning_replay_for_tool_calls(req4)
    assert_same_object(out4, req4, "step4 no replay group must not clone")
    assert_reasoning(out4.messages[-2], None, "step4 new no-replay tool stays blank")

    # 5. 接回填 deepseek 组 tool：之前空白 tool 补句号，deepseek tool 无真实思维链也补句号。
    history.extend([assistant_tool("tool_deepseek_blank"), tool_result("tool_deepseek_blank")])
    req5 = request(history, replay=True, model="deepseek-replay")
    out5 = router._ensure_reasoning_replay_for_tool_calls(req5)
    assert_cloned(out5, req5, "step5 replay deepseek should clone for blank tools")
    assert_reasoning(out5.messages[1], None, "step5 pre-tool assistant still not backfilled")
    assert_reasoning(out5.messages[2], placeholder, "step5 old placeholder preserved")
    assert_reasoning(out5.messages[4], qwen_real_reasoning, "step5 qwen reasoning preserved")
    assert_reasoning(out5.messages[-5], placeholder, "step5 post-tool assistant placeholder preserved")
    assert_reasoning(out5.messages[-4], placeholder, "step5 second no-replay tool backfilled")
    assert_reasoning(out5.messages[-2], placeholder, "step5 deepseek blank tool backfilled")

    history = out5.messages

    # 6. 最后接有思维且回填 gemini 回填 tool，并再调用 gemini：真实 gemini envelope 保留，不被句号覆盖。
    history.extend([assistant_tool("tool_gemini_real", gemini_reasoning), tool_result("tool_gemini_real")])
    req6 = request(history, replay=True, model="gemini-replay-tool")
    out6 = router._ensure_reasoning_replay_for_tool_calls(req6)
    assert_same_object(out6, req6, "step6 all tool calls already have reasoning")
    assert_reasoning(out6.messages[-2], gemini_reasoning, "step6 gemini reasoning preserved")

    req7 = request(out6.messages + [user("再调用 gemini")], replay=True, model="gemini-replay-followup")
    out7 = router._ensure_reasoning_replay_for_tool_calls(req7)
    assert_same_object(out7, req7, "step7 gemini followup no blank tool remains")
    assert_reasoning(out7.messages[-3], gemini_reasoning, "step7 gemini reasoning preserved on next call")

    assistant_after_function_call = []
    function_call_history_active = False
    for turn in out7.messages:
        if turn.role == "tool":
            function_call_history_active = True
            continue
        if turn.role != "assistant":
            continue
        if function_call_history_active or turn.tool_calls:
            function_call_history_active = True
            assistant_after_function_call.append(turn)
    blank_after_replay = [turn for turn in assistant_after_function_call if not str(turn.reasoning_content or "").strip()]
    if blank_after_replay:
        raise AssertionError(f"replay-enabled final chain still has blank function-call assistant reasoning: {len(blank_after_replay)}")
    assert_reasoning(out7.messages[1], None, "final pre-tool assistant remains untouched")

    tool_turns = [turn for turn in out7.messages if turn.role == "assistant" and turn.tool_calls]
    print(
        "OK reasoning replay IR backfill chain: "
        f"function_assistant_turns={len(assistant_after_function_call)} tool_turns={len(tool_turns)} "
        f"placeholder={sum(1 for t in assistant_after_function_call if t.reasoning_content == placeholder)} "
        f"real={sum(1 for t in assistant_after_function_call if t.reasoning_content not in {None, placeholder})}"
    )


if __name__ == "__main__":
    main()
