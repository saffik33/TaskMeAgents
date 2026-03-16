"""Mock tests for AgentFactory."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from taskmeagents.services.agent_factory import AgentFactory


def _mock_agent_row(**overrides):
    row = MagicMock()
    defaults = dict(
        agent_id="test-agent", name="Test", system_prompt="Be helpful.", model="claude-sonnet-4-6",
        max_tokens=4096, temperature=0.7, use_prompt_cache=False, thinking={},
        observation_masking={"enabled": True, "recent_window_turns": 3},
        client_tools=[], mcp_server_ids=[], sub_agents=[], tool=None,
    )
    for k, v in {**defaults, **overrides}.items():
        setattr(row, k, v)
    return row


@pytest.mark.asyncio
async def test_get_agent_cached():
    """Second call returns cached instance without DB query."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = _mock_agent_row()
    mock_session.execute.return_value = mock_result

    mock_factory_session = AsyncMock()
    mock_factory_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory_session.__aexit__ = AsyncMock()

    mock_session_factory = MagicMock(return_value=mock_factory_session)

    factory = AgentFactory(mock_session_factory)

    with patch("taskmeagents.services.agent_factory.get_mcp_registry") as mock_registry:
        mock_registry.return_value.discover_tools_for_servers = AsyncMock(return_value=[])
        agent1 = await factory.get_agent("test-agent")
        agent2 = await factory.get_agent("test-agent")

    assert agent1 is agent2  # same instance
    assert mock_session.execute.call_count == 1  # only 1 DB query


@pytest.mark.asyncio
async def test_invalidate_clears_cache():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = _mock_agent_row()
    mock_session.execute.return_value = mock_result

    mock_factory_session = AsyncMock()
    mock_factory_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory_session.__aexit__ = AsyncMock()
    mock_session_factory = MagicMock(return_value=mock_factory_session)

    factory = AgentFactory(mock_session_factory)

    with patch("taskmeagents.services.agent_factory.get_mcp_registry") as mock_registry:
        mock_registry.return_value.discover_tools_for_servers = AsyncMock(return_value=[])
        await factory.get_agent("test-agent")
        factory.invalidate("test-agent")
        await factory.get_agent("test-agent")

    assert mock_session.execute.call_count == 2  # re-queried after invalidation


@pytest.mark.asyncio
async def test_sub_agent_tools_injected():
    """Sub-agent tools get _ prefix, return_to_parent injected for sub-agents."""
    parent_row = _mock_agent_row(agent_id="parent", sub_agents=["child-1"])
    child_row = _mock_agent_row(
        agent_id="child-1",
        tool={"name": "research", "description": "Research", "input_schema": {"type": "object", "properties": {}}},
    )

    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.scalar_one_or_none.return_value = parent_row
        else:
            result.scalar_one_or_none.return_value = child_row
        return result

    mock_session = AsyncMock()
    mock_session.execute = mock_execute

    mock_factory_session = AsyncMock()
    mock_factory_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory_session.__aexit__ = AsyncMock()
    mock_session_factory = MagicMock(return_value=mock_factory_session)

    factory = AgentFactory(mock_session_factory)

    with patch("taskmeagents.services.agent_factory.get_mcp_registry") as mock_registry:
        mock_registry.return_value.discover_tools_for_servers = AsyncMock(return_value=[])
        agent = await factory.get_agent("parent")

    tool_names = [t.name for t in agent.all_tools]
    assert "_child-1" in tool_names  # sub-agent tool with _ prefix
