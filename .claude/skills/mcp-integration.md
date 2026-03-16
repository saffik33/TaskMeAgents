---
description: Use when creating or modifying MCP (Model Context Protocol) server integration, tool discovery, tool execution, passthrough headers, or the MCP registry in TaskMeAgents.
---

# MCP Integration — TaskMeAgents

## Architecture
- Global singleton `MCPRegistry` with TTL-cached connections
- Connections shared across all agents
- Tool names prefixed: `"{serverName}_{toolName}"`
- Passthrough headers for auth delegation

## Registry Usage
```python
from taskmeagents.mcp.registry import get_mcp_registry

registry = get_mcp_registry()

# Get server (connects if not cached)
entry = await registry.get_server(server_id, mcp_headers)

# Execute tool (3-minute timeout)
text, data, is_error = await registry.execute_tool(server_id, tool_name, args, mcp_headers)

# Discover tools from multiple servers
tools = await registry.discover_tools_for_servers(server_ids, mcp_headers)

# Invalidate on config change
registry.invalidate_server(server_id)
```

## Tool Name Convention
MCP tools are prefixed with server name for uniqueness:
- Server name: `erp-tools`, Tool name: `search` → `erp-tools_search`
- Parsing in activities: `tool_name.split("_", 1)` → `(server_name, actual_tool_name)`

## Passthrough Headers
```python
# Client sends: MCP-{serverName}-{headerName}
# Example: MCP-erp-tools-Authorization: Bearer xyz
# Extracted as: Authorization: Bearer xyz (forwarded to MCP server)

from taskmeagents.mcp.passthrough import extract_passthrough_headers
headers = extract_passthrough_headers(raw_headers, "erp-tools")
```

## Blocked Headers (never forwarded)
`host`, `content-length`, `transfer-encoding`, `connection`, `upgrade`, `keep-alive`, `proxy-authenticate`, `proxy-authorization`, `te`, `trailer`

## MCP Server Config (PostgreSQL)
```python
class McpServerConfig(Base):
    mcp_server_id: UUID (PK)
    name: str (unique, regex: ^[a-z][a-z-]{0,62}$)
    host, port, path, use_tls
    auth_strategy: "NONE" | "PASSTHROUGH"
    headers: JSONB (static headers)
    auto_approve: bool
    included_tools: JSONB (filter map)
```

## Key Files
- `src/taskmeagents/mcp/registry.py` — MCPRegistry singleton
- `src/taskmeagents/mcp/converters.py` — tool schema conversion
- `src/taskmeagents/mcp/passthrough.py` — header extraction
- `src/taskmeagents/models/mcp_server.py` — DB model
