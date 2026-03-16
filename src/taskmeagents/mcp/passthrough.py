"""Passthrough header extraction for MCP PASSTHROUGH auth strategy.

Translated from go_companion/internal/mcp/passthrough.go
Adapted for REST/WebSocket headers (replacing gRPC metadata).
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger()

# Headers that should never be forwarded to MCP servers
BLOCKED_HEADERS: set[str] = {
    "host",
    "content-length",
    "transfer-encoding",
    "connection",
    "upgrade",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
}


def is_blocked_header(header: str) -> bool:
    return header.lower() in BLOCKED_HEADERS


def extract_all_mcp_headers(headers: dict[str, str]) -> dict[str, str] | None:
    """Extract all headers starting with 'mcp-' from HTTP request headers.

    Called at the API layer to capture raw MCP headers before filtering by server.

    Example:
        HTTP headers: {"mcp-erp-auth": "Bearer xyz", "mcp-slack-token": "abc", "other": "ignored"}
        Result: {"mcp-erp-auth": "Bearer xyz", "mcp-slack-token": "abc"}
    """
    if not headers:
        return None

    prefix = "mcp-"
    result = {}

    for key, value in headers.items():
        if key.lower().startswith(prefix) and value:
            result[key.lower()] = value

    return result if result else None


def extract_passthrough_headers(raw_headers: dict[str, str], server_name: str) -> dict[str, str] | None:
    """Extract headers for a specific MCP server from raw MCP headers.

    Headers must have the prefix "mcp-{serverName}-" (case-insensitive).
    The prefix is stripped and the header is forwarded to the MCP server.
    Blocked headers (Host, Content-Length, etc.) are never forwarded.

    Example (server_name="erp-tools"):
        raw_headers: {"mcp-erp-tools-authorization": "Bearer xyz"}
        Result: {"authorization": "Bearer xyz"}
    """
    if not raw_headers or not server_name:
        return None

    prefix = f"mcp-{server_name.lower()}-"
    result = {}

    for key, value in raw_headers.items():
        key_lower = key.lower()
        if not key_lower.startswith(prefix):
            continue

        header_name = key_lower[len(prefix):]
        if not header_name:
            continue

        if is_blocked_header(header_name):
            logger.warning(
                "mcp.passthrough.header_blocked",
                server_name=server_name,
                header_name=header_name,
            )
            continue

        result[header_name] = value

    return result if result else None


def get_passthrough_prefix(server_name: str) -> str:
    """Return the HTTP header prefix for a given server name.

    Format: "mcp-{serverName}-" (lowercase)
    Example: get_passthrough_prefix("erp-tools") returns "mcp-erp-tools-"
    """
    return f"mcp-{server_name.lower()}-"
