"""MCP server management request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


class McpServerCreate(BaseModel):
    name: str
    host: str
    port: str
    path: str
    description: str | None = None
    use_tls: bool = True
    auth_strategy: str = "NONE"
    headers: dict[str, str] = {}
    auto_approve: bool = False
    passthrough_headers: list[str] = []
    included_tools: dict[str, bool] = {}

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        import re
        if not re.match(r"^[a-z][a-z\-]{0,62}$", v):
            raise ValueError("Name must be 1-63 chars, lowercase letters and hyphens, starting with a letter")
        return v

    @field_validator("auth_strategy")
    @classmethod
    def validate_auth_strategy(cls, v: str) -> str:
        if v not in ("NONE", "PASSTHROUGH"):
            raise ValueError("auth_strategy must be NONE or PASSTHROUGH")
        return v


class McpServerUpdate(BaseModel):
    name: str | None = None
    host: str | None = None
    port: str | None = None
    path: str | None = None
    description: str | None = None
    use_tls: bool | None = None
    auth_strategy: str | None = None
    headers: dict[str, str] | None = None
    auto_approve: bool | None = None
    passthrough_headers: list[str] | None = None
    included_tools: dict[str, bool] | None = None


class McpServerResponse(BaseModel):
    mcp_server_id: str
    name: str
    description: str | None
    host: str
    port: str
    path: str
    use_tls: bool | None
    auth_strategy: str
    headers: dict[str, str]
    auto_approve: bool
    passthrough_headers: list[str]
    included_tools: dict[str, bool]
    created_at: datetime
    updated_at: datetime
    updated_by: str | None


class McpTestResult(BaseModel):
    connected: bool
    tools: list[dict[str, Any]] = []
    error: str | None = None
