"""Global MCP registry with TTL-cached connections.

Translated from go_companion/internal/mcp/registry.go
Uses cachetools.TTLCache instead of otter, and mcp Python package instead of mcp-go.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog
from cachetools import TTLCache
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from taskmeagents.config import settings
from taskmeagents.mcp.converters import convert_mcp_tool, convert_tool_result
from taskmeagents.mcp.passthrough import extract_passthrough_headers
from taskmeagents.tools.types import Tool

logger = structlog.get_logger()

CONNECTION_TIMEOUT = 30  # seconds
TOOL_EXECUTION_TIMEOUT = 180  # 3 minutes


@dataclass
class MCPServerEntry:
    mcp_server_id: str
    config: dict[str, Any]  # MCPServerConfig from DB
    session: ClientSession | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)
    resources: list[dict[str, Any]] = field(default_factory=list)
    connected: bool = False
    connected_at: datetime | None = None


class MCPRegistry:
    """Global singleton managing cached MCP server connections.

    Connections are shared across all agents. TTL-based eviction closes
    idle connections automatically.
    """

    def __init__(self):
        ttl = settings.mcp_idle_timeout_minutes * 60
        self._cache: TTLCache[str, MCPServerEntry] = TTLCache(
            maxsize=settings.mcp_max_servers, ttl=ttl
        )
        self._lock = asyncio.Lock()
        self._db_loader: Any = None  # Set via set_db_loader

    def set_db_loader(self, loader: Any) -> None:
        """Set the database loader for fetching MCP server configs.

        The loader must implement: async load_config(server_id: str) -> dict | None
        """
        self._db_loader = loader

    async def get_server(self, server_id: str, mcp_headers: dict[str, str] | None = None) -> MCPServerEntry:
        """Get an MCP server connection by ID, connecting if not cached."""
        if server_id in self._cache:
            return self._cache[server_id]

        async with self._lock:
            # Double-check after acquiring lock
            if server_id in self._cache:
                return self._cache[server_id]

            if not self._db_loader:
                raise RuntimeError("MCPRegistry.set_db_loader() must be called before get_server()")

            config = await self._db_loader.load_config(server_id)
            if config is None:
                raise ValueError(f"MCP server not found: {server_id}")

            entry = await self._connect_server(config, mcp_headers)
            self._cache[server_id] = entry

            logger.info(
                "mcp.connection.established",
                server_id=server_id,
                server_name=config.get("name", ""),
                tool_count=len(entry.tools),
            )
            return entry

    async def execute_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        mcp_headers: dict[str, str] | None = None,
    ) -> tuple[str, dict[str, Any], bool]:
        """Execute a tool on the specified MCP server.

        Returns (text_content, result_data, is_error).
        """
        entry = await self.get_server(server_id, mcp_headers)
        if not entry.connected or not entry.session:
            raise RuntimeError(f"MCP server '{entry.config.get('name', server_id)}' is not connected")

        # Apply passthrough headers if needed
        server_name = entry.config.get("name", "")
        if mcp_headers and entry.config.get("auth_strategy") == "PASSTHROUGH":
            server_headers = extract_passthrough_headers(mcp_headers, server_name)
            # Headers would be injected via the transport's header callback
            # For now, they're set at connection time

        result = await asyncio.wait_for(
            entry.session.call_tool(tool_name, arguments),
            timeout=TOOL_EXECUTION_TIMEOUT,
        )

        # Convert result
        is_error = getattr(result, "isError", False)
        content_list = []
        for c in getattr(result, "content", []):
            content_list.append({"type": getattr(c, "type", "text"), "text": getattr(c, "text", str(c))})

        text_content, result_data = convert_tool_result({"content": content_list}, is_error)

        if is_error:
            result_data["is_error"] = True

        return text_content, result_data, is_error

    async def discover_tools_for_servers(
        self,
        server_ids: list[str],
        mcp_headers: dict[str, str] | None = None,
    ) -> list[Tool]:
        """Discover tools from multiple MCP servers, filtered by included_tools."""
        if not server_ids:
            return []

        all_tools: list[Tool] = []

        for server_id in server_ids:
            try:
                entry = await self.get_server(server_id, mcp_headers)
            except Exception as e:
                logger.warning("mcp.discovery.failed", server_id=server_id, error=str(e))
                continue

            config = entry.config
            server_name = config.get("name", "")
            auto_approve = config.get("auto_approve", False)
            included_tools = config.get("included_tools", {})
            has_filter = bool(included_tools)

            for mcp_tool in entry.tools:
                tool_name = mcp_tool.get("name", "")
                # Apply included_tools filter
                if has_filter and tool_name not in included_tools:
                    continue
                tool = convert_mcp_tool(server_name, auto_approve, mcp_tool)
                all_tools.append(tool)

        return all_tools

    async def validate_included_tools(self, config: dict[str, Any], mcp_headers: dict[str, str] | None = None) -> list[str]:
        """Validate that all included_tools exist on the MCP server.

        Returns list of missing tool names (empty if all valid).
        """
        included_tools = config.get("included_tools", {})
        if not included_tools:
            return []

        entry = await self._connect_server(config, mcp_headers)
        try:
            actual_tools = {t.get("name", "") for t in entry.tools}
            return [name for name in included_tools if name not in actual_tools]
        finally:
            if entry.session:
                # Close temporary validation connection
                pass  # Session cleanup handled by context manager

    def invalidate_server(self, server_id: str) -> bool:
        """Remove an MCP server from the cache."""
        if server_id in self._cache:
            del self._cache[server_id]
            logger.info("mcp.connection.invalidated", server_id=server_id)
            return True
        return False

    async def shutdown(self) -> None:
        """Close all cached connections."""
        self._cache.clear()

    async def _connect_server(
        self, config: dict[str, Any], mcp_headers: dict[str, str] | None = None
    ) -> MCPServerEntry:
        """Connect to an MCP server and discover its tools."""
        server_id = str(config.get("mcp_server_id", ""))
        server_name = config.get("name", "")
        host = config.get("host", "")
        port = config.get("port", "")
        path = config.get("path", "")
        use_tls = config.get("use_tls", True)

        scheme = "https" if use_tls else "http"
        url = f"{scheme}://{host}:{port}{path}"

        # Build extra headers (static + passthrough)
        headers: dict[str, str] = dict(config.get("headers", {}))
        if mcp_headers and config.get("auth_strategy") == "PASSTHROUGH":
            passthrough = extract_passthrough_headers(mcp_headers, server_name)
            if passthrough:
                headers.update(passthrough)

        try:
            async with asyncio.timeout(CONNECTION_TIMEOUT):
                # Use mcp Python SDK's streamable HTTP client
                async with streamablehttp_client(url, headers=headers) as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()

                        # Discover tools
                        tools_result = await session.list_tools()
                        tools = [
                            {"name": t.name, "description": t.description or "", "inputSchema": t.inputSchema or {}}
                            for t in tools_result.tools
                        ]

                        # Discover resources (optional, non-fatal)
                        resources = []
                        try:
                            resources_result = await session.list_resources()
                            resources = [{"uri": r.uri, "name": r.name} for r in resources_result.resources]
                        except Exception:
                            pass  # Resources are optional

                        entry = MCPServerEntry(
                            mcp_server_id=server_id,
                            config=config,
                            session=session,
                            tools=tools,
                            resources=resources,
                            connected=True,
                            connected_at=datetime.now(timezone.utc),
                        )
                        return entry

        except Exception as e:
            raise ConnectionError(f"Failed to connect to MCP server {server_name} at {url}: {e}") from e


# --- Global singleton ---

_registry: MCPRegistry | None = None


def init_mcp_registry() -> MCPRegistry:
    global _registry
    _registry = MCPRegistry()
    return _registry


def get_mcp_registry() -> MCPRegistry:
    if _registry is None:
        raise RuntimeError("MCP registry not initialized. Call init_mcp_registry() first.")
    return _registry
