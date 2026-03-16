"""Unit tests for Message ↔ MessageDocument conversion."""

from taskmeagents.activities.persistence import _message_to_doc
from tests.fixtures.messages import (
    make_assistant_message,
    make_tool_request,
    make_tool_result,
    make_user_message,
)


def test_message_to_doc_user():
    msg = make_user_message("Hello world")
    doc = _message_to_doc(msg, "session-1", 0)
    assert doc.role == "user"
    assert doc.content["content"] == "Hello world"
    assert doc.id == "msg-u-1"


def test_message_to_doc_assistant():
    msg = make_assistant_message("Hi!", is_final=True)
    msg.assistant_message.thinking = "Let me think..."
    doc = _message_to_doc(msg, "session-1", 1)
    assert doc.role == "assistant"
    assert doc.content["content"] == "Hi!"
    assert doc.content["thinking"] == "Let me think..."
    assert doc.content["is_final"] is True


def test_message_to_doc_tool_request():
    msg = make_tool_request(tool_name="search", parameters={"q": "test"})
    doc = _message_to_doc(msg, "session-1", 2)
    assert doc.role == "tool_request"
    assert doc.content["tool_name"] == "search"
    assert doc.content["parameters"] == {"q": "test"}


def test_message_to_doc_tool_result():
    msg = make_tool_result(tool_name="search", content="Found 5 items", success=True)
    doc = _message_to_doc(msg, "session-1", 3)
    assert doc.role == "tool_result"
    assert doc.content["tool_name"] == "search"
    assert doc.content["content"] == "Found 5 items"
    assert doc.content["success"] is True
