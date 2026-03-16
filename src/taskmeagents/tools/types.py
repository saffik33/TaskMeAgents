"""Tool definitions with JSON Schema support.

Translated from go_companion/internal/tools/types.go
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolType(str, Enum):
    SERVER = "server"
    CLIENT = "client"
    AGENT = "agent"


@dataclass
class Parameter:
    type: str  # "string", "number", "boolean", "object", "array"
    description: str = ""
    enum: list[Any] | None = None
    items: dict[str, Any] | None = None  # for array type
    properties: dict[str, Parameter] | None = None  # for object type
    required: list[str] | None = None  # for object type


@dataclass
class ParameterSchema:
    type: str = "object"
    properties: dict[str, Parameter] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)
    additional_properties: bool = False

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"type": self.type}
        if self.properties:
            result["properties"] = {k: _param_to_dict(v) for k, v in self.properties.items()}
        if self.required:
            result["required"] = self.required
        result["additionalProperties"] = self.additional_properties
        return result


@dataclass
class Tool:
    name: str
    description: str
    input_schema: ParameterSchema = field(default_factory=ParameterSchema)
    auto_approve: bool = False
    tool_type: ToolType = ToolType.SERVER


def _param_to_dict(p: Parameter) -> dict[str, Any]:
    d: dict[str, Any] = {"type": p.type}
    if p.description:
        d["description"] = p.description
    if p.enum is not None:
        d["enum"] = p.enum
    if p.items is not None:
        d["items"] = p.items
    if p.properties is not None:
        d["properties"] = {k: _param_to_dict(v) for k, v in p.properties.items()}
    if p.required is not None:
        d["required"] = p.required
    return d
