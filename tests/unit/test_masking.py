"""Unit tests for observation masking."""

from taskmeagents.conversation.masking import MASKED_PLACEHOLDER, MaskingConfig, apply_observation_masking
from tests.fixtures.messages import make_assistant_message, make_tool_result, make_user_message


def _make_history(turns: int = 5):
    """Create a conversation history with tool results at each turn."""
    msgs = []
    for t in range(1, turns + 1):
        msgs.append(make_user_message(f"Turn {t}", turn=t, msg_id=f"u-{t}"))
        msgs.append(make_tool_result(content=f"Result {t}", turn=t, msg_id=f"tr-{t}"))
        msgs.append(make_assistant_message(f"Reply {t}", turn=t, msg_id=f"a-{t}"))
    return msgs


def test_masking_disabled():
    msgs = _make_history()
    result = apply_observation_masking(msgs, current_turn=5, config=MaskingConfig(enabled=False),
                                       total_tokens=100000, max_context_tokens=128000)
    assert result is msgs  # same object, no copy


def test_masking_below_threshold():
    msgs = _make_history()
    result = apply_observation_masking(msgs, current_turn=5, config=MaskingConfig(enabled=True),
                                       total_tokens=50000, max_context_tokens=128000)
    # 50000 < 128000 * 0.75 = 96000 → no masking
    assert result is msgs


def test_masking_old_tool_results():
    msgs = _make_history(turns=5)
    config = MaskingConfig(enabled=True, recent_window_turns=2)
    result = apply_observation_masking(msgs, current_turn=5, config=config,
                                       total_tokens=100000, max_context_tokens=128000)
    # Turns 1,2,3 are old (age >= 2), turns 4,5 are recent
    masked_results = [m for m in result if m.tool_result and m.tool_result.content == MASKED_PLACEHOLDER]
    assert len(masked_results) == 3  # turns 1, 2, 3


def test_masking_recent_preserved():
    msgs = _make_history(turns=5)
    config = MaskingConfig(enabled=True, recent_window_turns=2)
    result = apply_observation_masking(msgs, current_turn=5, config=config,
                                       total_tokens=100000, max_context_tokens=128000)
    recent_results = [m for m in result if m.tool_result and m.tool_result.content != MASKED_PLACEHOLDER]
    assert len(recent_results) == 2  # turns 4, 5


def test_masking_user_messages_untouched():
    msgs = _make_history(turns=5)
    config = MaskingConfig(enabled=True, recent_window_turns=1)
    result = apply_observation_masking(msgs, current_turn=5, config=config,
                                       total_tokens=100000, max_context_tokens=128000)
    user_msgs = [m for m in result if m.user_message]
    assert all(m.user_message.content.startswith("Turn") for m in user_msgs)


def test_masking_assistant_messages_untouched():
    msgs = _make_history(turns=5)
    config = MaskingConfig(enabled=True, recent_window_turns=1)
    result = apply_observation_masking(msgs, current_turn=5, config=config,
                                       total_tokens=100000, max_context_tokens=128000)
    assistant_msgs = [m for m in result if m.assistant_message]
    assert all(m.assistant_message.content.startswith("Reply") for m in assistant_msgs)


def test_masking_empty_messages():
    result = apply_observation_masking([], current_turn=0, config=MaskingConfig(),
                                       total_tokens=100000, max_context_tokens=128000)
    assert result == []


def test_masking_original_unmodified():
    msgs = _make_history(turns=3)
    original_content = msgs[1].tool_result.content  # turn 1 tool result
    config = MaskingConfig(enabled=True, recent_window_turns=1)
    apply_observation_masking(msgs, current_turn=3, config=config,
                              total_tokens=100000, max_context_tokens=128000)
    assert msgs[1].tool_result.content == original_content  # original unchanged
