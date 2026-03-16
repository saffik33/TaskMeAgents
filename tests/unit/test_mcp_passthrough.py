"""Unit tests for MCP passthrough header extraction."""

from taskmeagents.mcp.passthrough import (
    extract_all_mcp_headers,
    extract_passthrough_headers,
    get_passthrough_prefix,
    is_blocked_header,
)


def test_extract_all_mcp_headers():
    headers = {"mcp-erp-auth": "Bearer xyz", "mcp-slack-token": "abc", "content-type": "json"}
    result = extract_all_mcp_headers(headers)
    assert result == {"mcp-erp-auth": "Bearer xyz", "mcp-slack-token": "abc"}


def test_extract_all_mcp_headers_empty():
    assert extract_all_mcp_headers({"content-type": "json"}) is None
    assert extract_all_mcp_headers({}) is None
    assert extract_all_mcp_headers(None) is None


def test_extract_passthrough_for_server():
    raw = {"mcp-erp-tools-authorization": "Bearer xyz", "mcp-slack-token": "abc"}
    result = extract_passthrough_headers(raw, "erp-tools")
    assert result == {"authorization": "Bearer xyz"}


def test_blocked_headers_rejected():
    raw = {"mcp-s-host": "evil.com", "mcp-s-content-length": "999", "mcp-s-x-custom": "ok"}
    result = extract_passthrough_headers(raw, "s")
    assert result == {"x-custom": "ok"}


def test_case_insensitive_matching():
    raw = {"MCP-Server-Auth": "token"}
    result = extract_all_mcp_headers(raw)
    # Keys are lowercased during extraction
    assert result is not None


def test_get_passthrough_prefix():
    assert get_passthrough_prefix("Erp-Tools") == "mcp-erp-tools-"
