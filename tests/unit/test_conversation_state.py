"""Unit tests for ConversationState."""

from taskmeagents.conversation.types import TokenUsage
from taskmeagents.workflow.state import ConversationState
from tests.fixtures.messages import make_tool_request


def test_find_pending_tool_by_id():
    state = ConversationState()
    msg = make_tool_request(tool_use_id="tu-123")
    state.pending_tool_ids["tu-123"] = msg

    found, exists = state.find_pending_tool_by_id("tu-123")
    assert exists is True
    assert found.tool_request.tool_use_id == "tu-123"


def test_find_pending_tool_by_name():
    state = ConversationState()
    msg = make_tool_request(tool_name="get_weather", tool_use_id="tu-456")
    state.pending_tool_ids["tu-456"] = msg

    tid, found, exists = state.find_pending_tool_by_name("get_weather")
    assert exists is True
    assert tid == "tu-456"
    assert found.tool_request.tool_name == "get_weather"


def test_find_pending_tool_not_found():
    state = ConversationState()
    found, exists = state.find_pending_tool_by_id("missing")
    assert exists is False
    assert found is None

    tid, found, exists = state.find_pending_tool_by_name("missing")
    assert exists is False


def test_accumulate_usage():
    state = ConversationState()
    usage = TokenUsage(input_tokens=100, output_tokens=50, request_cost=0.005)
    state.accumulate_usage(usage)

    assert state.cumulative_usage.total_input_tokens == 100
    assert state.cumulative_usage.total_output_tokens == 50
    assert state.cumulative_usage.total_cost == 0.005
    # Totals copied back to message usage
    assert usage.total_input_tokens == 100
    assert usage.total_cost == 0.005

    # Accumulate again
    usage2 = TokenUsage(input_tokens=200, output_tokens=100, request_cost=0.01)
    state.accumulate_usage(usage2)
    assert state.cumulative_usage.total_input_tokens == 300
    assert usage2.total_input_tokens == 300
