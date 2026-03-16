"""Agent management request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AgentCreate(BaseModel):
    agent_id: str
    name: str
    system_prompt: str
    model: str
    max_tokens: int = 4096
    temperature: float = 0.7
    client_tools: list[dict[str, Any]] = []
    mcp_server_ids: list[str] = []
    sub_agents: list[str] = []
    use_prompt_cache: bool = False
    thinking: dict[str, Any] = {}
    observation_masking: dict[str, Any] | None = None
    tool: dict[str, Any] | None = None
    version_comment: str = ""


class AgentUpdate(BaseModel):
    name: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    client_tools: list[dict[str, Any]] | None = None
    mcp_server_ids: list[str] | None = None
    sub_agents: list[str] | None = None
    use_prompt_cache: bool | None = None
    thinking: dict[str, Any] | None = None
    observation_masking: dict[str, Any] | None = None
    tool: dict[str, Any] | None = None
    version_comment: str = ""


class AgentResponse(BaseModel):
    agent_id: str
    name: str
    system_prompt: str
    model: str
    max_tokens: int
    temperature: float
    client_tools: list[dict[str, Any]]
    mcp_server_ids: list[str]
    sub_agents: list[str]
    use_prompt_cache: bool
    thinking: dict[str, Any]
    observation_masking: dict[str, Any] | None
    tool: dict[str, Any] | None
    version: int
    version_comment: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


class AgentVersionResponse(BaseModel):
    agent_id: str
    version: int
    config: dict[str, Any]
    archived_at: datetime


class RollbackRequest(BaseModel):
    version: int
