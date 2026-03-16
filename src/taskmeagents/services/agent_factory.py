"""Agent factory — singleton cache for agent instances.

Translated from go_companion/internal/agent/factory.go
Loads agent config from PostgreSQL, creates LLM provider, discovers MCP tools.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from taskmeagents.config import settings
from taskmeagents.history.pg_store import PostgresHistoryStore
from taskmeagents.tools.types import Parameter, ParameterSchema, Tool, ToolType
from taskmeagents.history.store import HistoryStore
from taskmeagents.llm.anthropic_provider import AnthropicProvider
from taskmeagents.llm.models import REGISTRY, ProviderType
from taskmeagents.llm.openai_provider import OpenAIProvider
from taskmeagents.llm.provider import Provider
from taskmeagents.llm.thinking import ThinkingConfig, ThinkingMode
from taskmeagents.mcp.registry import get_mcp_registry
from taskmeagents.models.agent import Agent as AgentModel
logger = structlog.get_logger()


@dataclass
class AgentInstance:
    """A cached agent with its provider and tools."""

    config: dict[str, Any]
    provider: Provider
    all_tools: list[Tool] = field(default_factory=list)
    server_name_to_id: dict[str, str] = field(default_factory=dict)


class AgentFactory:
    """Singleton factory that caches agent instances."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._agents: dict[str, AgentInstance] = {}
        self._lock = asyncio.Lock()
        self._session_factory = session_factory

    async def get_agent(self, agent_id: str, is_sub_agent: bool = False) -> AgentInstance:
        cache_key = f"sub:{agent_id}" if is_sub_agent else agent_id

        if cache_key in self._agents:
            return self._agents[cache_key]

        async with self._lock:
            # Double-check after acquiring lock
            if cache_key in self._agents:
                return self._agents[cache_key]

            agent = await self._create_agent(agent_id, is_sub_agent)
            self._agents[cache_key] = agent
            return agent

    def invalidate(self, agent_id: str) -> None:
        """Remove agent from cache (called on config update)."""
        self._agents.pop(agent_id, None)
        self._agents.pop(f"sub:{agent_id}", None)

    async def shutdown(self) -> None:
        """Close all cached providers."""
        for agent in self._agents.values():
            await agent.provider.close()
        self._agents.clear()

    async def _create_agent(self, agent_id: str, is_sub_agent: bool) -> AgentInstance:
        """Load config, create provider, discover tools."""
        # Load config from PostgreSQL
        async with self._session_factory() as db:
            result = await db.execute(select(AgentModel).where(AgentModel.agent_id == agent_id))
            row = result.scalar_one_or_none()
            if not row:
                raise ValueError(f"Agent not found: {agent_id}")

        config = {
            "agent_id": row.agent_id,
            "name": row.name,
            "system_prompt": row.system_prompt,
            "client_tools": row.client_tools or [],
            "mcp_server_ids": row.mcp_server_ids or [],
            "sub_agents": row.sub_agents or [],
            "model": row.model,
            "max_tokens": row.max_tokens,
            "temperature": row.temperature,
            "use_prompt_cache": row.use_prompt_cache,
            "thinking": row.thinking or {},
            "observation_masking": row.observation_masking or {"enabled": True, "recent_window_turns": 3},
            "tool": row.tool,
        }

        # Create provider
        model_id = config["model"]
        model = REGISTRY.get(model_id)
        if not model:
            raise ValueError(f"Unknown model: {model_id}")

        thinking_data = config.get("thinking", {})
        thinking = ThinkingConfig(
            mode=ThinkingMode(thinking_data.get("mode", "disabled")),
            budget_tokens=thinking_data.get("budget_tokens", 0),
        )

        provider: Provider
        if model.provider_type == ProviderType.ANTHROPIC:
            provider = AnthropicProvider(model, settings.anthropic_api_key, thinking)
        elif model.provider_type == ProviderType.OPENAI:
            provider = OpenAIProvider(model, settings.openai_api_key)
        else:
            raise ValueError(f"Unknown provider type: {model.provider_type}")

        # Discover MCP tools
        all_tools: list[Tool] = []
        server_name_to_id: dict[str, str] = {}

        mcp_server_ids = config.get("mcp_server_ids", [])
        if mcp_server_ids:
            try:
                registry = get_mcp_registry()
                mcp_tools = await registry.discover_tools_for_servers(mcp_server_ids)
                all_tools.extend(mcp_tools)

                # Build server_name → server_id mapping
                for sid in mcp_server_ids:
                    try:
                        entry = await registry.get_server(sid)
                        name = entry.config.get("name", "")
                        if name:
                            server_name_to_id[name] = sid
                    except Exception:
                        pass
            except Exception as e:
                logger.error("agent.mcp.discovery.failed", agent_id=agent_id, error=str(e))
                raise  # Fail fast on MCP errors (same as Go)

        # Add client tools from config
        client_tools = config.get("client_tools", [])
        for ct in client_tools:
            if isinstance(ct, dict):
                tool = Tool(
                    name=ct.get("name", ""),
                    description=ct.get("description", ""),
                    tool_type=ToolType.CLIENT,
                    input_schema=ParameterSchema(**ct.get("input_schema", {})) if ct.get("input_schema") else ParameterSchema(),
                )
                all_tools.append(tool)

        # Inject sub-agent tools (prefix with _ for LLM compatibility)
        sub_agent_ids = config.get("sub_agents", [])
        for sub_id in sub_agent_ids:
            try:
                async with self._session_factory() as db:
                    sub_result = await db.execute(select(AgentModel).where(AgentModel.agent_id == sub_id))
                    sub_row = sub_result.scalar_one_or_none()
                if sub_row and sub_row.tool:
                    tool_def = sub_row.tool
                    agent_tool = Tool(
                        name=f"_{sub_id}",
                        description=tool_def.get("description", f"Delegate to sub-agent {sub_row.name}"),
                        input_schema=ParameterSchema(**tool_def.get("input_schema", {})) if tool_def.get("input_schema") else ParameterSchema(),
                        tool_type=ToolType.AGENT,
                    )
                    all_tools.append(agent_tool)
            except Exception as e:
                logger.warning("agent.sub_agent.load.failed", sub_agent_id=sub_id, error=str(e))

        # Inject return_to_parent_agent tool if this is a sub-agent
        if is_sub_agent:
            from taskmeagents.workflow.constants import RETURN_TO_PARENT_TOOL_NAME
            return_tool = Tool(
                name=RETURN_TO_PARENT_TOOL_NAME,
                description="Call this tool when your task is complete to return results to the parent agent.",
                input_schema=ParameterSchema(
                    properties={
                        "result": Parameter(type="string", description="Summary of what was accomplished"),
                        "data": Parameter(type="object", description="Structured data to return (optional)"),
                    },
                    required=["result"],
                ),
                tool_type=ToolType.AGENT,
            )
            all_tools.append(return_tool)

        logger.info(
            "agent.created",
            agent_id=agent_id,
            model=model_id,
            tool_count=len(all_tools),
            is_sub_agent=is_sub_agent,
        )

        return AgentInstance(
            config=config,
            provider=provider,
            all_tools=all_tools,
            server_name_to_id=server_name_to_id,
        )


# --- Global singletons ---

_factory: AgentFactory | None = None
_history_store: HistoryStore | None = None


def init_agent_factory(session_factory: async_sessionmaker[AsyncSession]) -> AgentFactory:
    global _factory
    _factory = AgentFactory(session_factory)
    return _factory


def get_agent_factory() -> AgentFactory:
    if _factory is None:
        raise RuntimeError("Agent factory not initialized. Call init_agent_factory() first.")
    return _factory


def init_history_store(session_factory: async_sessionmaker[AsyncSession]) -> HistoryStore:
    global _history_store
    _history_store = PostgresHistoryStore(session_factory)
    return _history_store


def get_history_store() -> HistoryStore:
    if _history_store is None:
        raise RuntimeError("History store not initialized. Call init_history_store() first.")
    return _history_store
