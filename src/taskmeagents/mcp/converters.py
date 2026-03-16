"""MCP content and tool converters.

Translated from go_companion/internal/mcp/converters.go
Converts MCP tool schemas to internal Tool format and MCP content to dicts.
"""

from __future__ import annotations

from typing import Any

from taskmeagents.tools.types import Parameter, ParameterSchema, Tool, ToolType


# --- Content Converters ---

def convert_text_content(content: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "text",
        "text": content.get("text", ""),
    }


def convert_image_content(content: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "image",
        "data": content.get("data", ""),
        "mimeType": content.get("mimeType", ""),
    }


def convert_audio_content(content: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "audio",
        "data": content.get("data", ""),
        "mimeType": content.get("mimeType", ""),
    }


def convert_tool_result(result: dict[str, Any], is_error: bool) -> tuple[str, dict[str, Any]]:
    """Convert MCP CallToolResult to (text_content, result_data).

    Returns the extracted text and a dict suitable for ToolResultMessage.data.
    """
    result_data: dict[str, Any] = {}
    contents = result.get("content", [])

    for i, content in enumerate(contents):
        content_type = content.get("type", "unknown")
        if content_type == "text":
            converted = convert_text_content(content)
            text = converted.get("text", "")
            if i == 0:
                result_data["result"] = text
            else:
                result_data[f"result_{i}"] = text
        elif content_type == "image":
            converted = convert_image_content(content)
            result_data[f"content_{i}"] = converted
        elif content_type == "audio":
            converted = convert_audio_content(content)
            result_data[f"content_{i}"] = converted
        else:
            result_data[f"content_{i}"] = {"type": "unknown", "description": f"Unsupported: {content_type}"}

    if not result_data:
        if is_error:
            result_data["result"] = "Tool execution failed with no details"
        else:
            result_data["result"] = "Tool executed successfully with no output"

    text_content = str(result_data.get("result", ""))
    return text_content, result_data


# --- Tool Schema Converters ---

def convert_mcp_tool(server_name: str, auto_approve: bool, mcp_tool: dict[str, Any]) -> Tool:
    """Convert an MCP tool definition to internal Tool format.

    Tool names are prefixed with the server name for uniqueness:
    "{serverName}_{toolName}"
    """
    tool_name = mcp_tool.get("name", "")
    prefixed_name = f"{server_name}_{tool_name}"

    input_schema = _convert_input_schema(mcp_tool.get("inputSchema", {}))

    return Tool(
        name=prefixed_name,
        description=mcp_tool.get("description", ""),
        input_schema=input_schema,
        auto_approve=auto_approve,
        tool_type=ToolType.SERVER,
    )


def _convert_input_schema(schema: dict[str, Any]) -> ParameterSchema:
    """Convert MCP JSON Schema to internal ParameterSchema."""
    if not schema:
        return ParameterSchema()

    properties = {}
    for name, prop_schema in schema.get("properties", {}).items():
        properties[name] = _convert_parameter(prop_schema)

    return ParameterSchema(
        type=schema.get("type", "object"),
        properties=properties,
        required=schema.get("required", []),
        additional_properties=schema.get("additionalProperties", False),
    )


def _convert_parameter(schema: dict[str, Any]) -> Parameter:
    """Convert a JSON Schema property to internal Parameter."""
    # Handle $ref (simplified — treat as object with description)
    if "$ref" in schema:
        return Parameter(type="object", description=f"Reference: {schema['$ref']}")

    # Handle anyOf/oneOf/allOf — infer type from first option
    for composite_key in ("anyOf", "oneOf", "allOf"):
        if composite_key in schema:
            options = schema[composite_key]
            if options:
                # Check for const values
                for opt in options:
                    if "const" in opt:
                        return Parameter(
                            type=opt.get("type", "string"),
                            description=schema.get("description", ""),
                            enum=[o.get("const") for o in options if "const" in o],
                        )
                # Fall back to first option's type
                return _convert_parameter(options[0])

    param_type = schema.get("type", "string")
    param = Parameter(
        type=param_type,
        description=schema.get("description", ""),
    )

    if "enum" in schema:
        param.enum = schema["enum"]

    if param_type == "array" and "items" in schema:
        param.items = schema["items"]

    if param_type == "object" and "properties" in schema:
        param.properties = {k: _convert_parameter(v) for k, v in schema["properties"].items()}
        param.required = schema.get("required")

    return param
