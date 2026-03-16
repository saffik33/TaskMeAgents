"""Unit tests for MCP tool and schema converters."""

from taskmeagents.mcp.converters import (
    _convert_input_schema,
    _convert_parameter,
    convert_mcp_tool,
    convert_tool_result,
)


def test_convert_mcp_tool_name_prefix():
    tool = convert_mcp_tool("erp-tools", False, {"name": "search", "description": "Search", "inputSchema": {}})
    assert tool.name == "erp-tools_search"


def test_convert_mcp_tool_auto_approve():
    tool = convert_mcp_tool("s", True, {"name": "t", "description": "", "inputSchema": {}})
    assert tool.auto_approve is True


def test_convert_input_schema_basic():
    schema = {"type": "object", "properties": {"name": {"type": "string", "description": "Name"}}, "required": ["name"]}
    result = _convert_input_schema(schema)
    assert result.type == "object"
    assert "name" in result.properties
    assert result.properties["name"].type == "string"
    assert result.required == ["name"]


def test_convert_parameter_ref():
    param = _convert_parameter({"$ref": "#/definitions/Foo"})
    assert param.type == "object"
    assert "Reference" in param.description


def test_convert_parameter_anyof():
    param = _convert_parameter({"anyOf": [{"type": "string"}, {"type": "integer"}]})
    assert param.type == "string"  # picks first


def test_convert_parameter_enum():
    param = _convert_parameter({
        "anyOf": [{"const": "a", "type": "string"}, {"const": "b", "type": "string"}],
        "description": "Pick one",
    })
    assert param.enum == ["a", "b"]


def test_convert_tool_result_text():
    text, data = convert_tool_result({"content": [{"type": "text", "text": "Hello"}]}, False)
    assert text == "Hello"
    assert data["result"] == "Hello"


def test_convert_tool_result_error():
    text, data = convert_tool_result({"content": []}, True)
    assert "failed" in data["result"].lower()


def test_convert_tool_result_multi_content():
    text, data = convert_tool_result({
        "content": [
            {"type": "text", "text": "First"},
            {"type": "text", "text": "Second"},
        ]
    }, False)
    assert data["result"] == "First"
    assert data["result_1"] == "Second"
