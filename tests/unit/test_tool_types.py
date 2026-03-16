"""Unit tests for Tool and ParameterSchema types."""

from taskmeagents.tools.types import Parameter, ParameterSchema


def test_parameter_schema_to_dict():
    schema = ParameterSchema(
        properties={"name": Parameter(type="string", description="User name")},
        required=["name"],
    )
    d = schema.to_dict()
    assert d["type"] == "object"
    assert d["properties"]["name"]["type"] == "string"
    assert d["required"] == ["name"]
    assert d["additionalProperties"] is False


def test_parameter_schema_nested():
    schema = ParameterSchema(
        properties={
            "address": Parameter(
                type="object",
                properties={"city": Parameter(type="string"), "zip": Parameter(type="string")},
                required=["city"],
            )
        },
    )
    d = schema.to_dict()
    addr = d["properties"]["address"]
    assert addr["type"] == "object"
    assert "city" in addr["properties"]
    assert addr["required"] == ["city"]


def test_parameter_enum():
    schema = ParameterSchema(
        properties={"color": Parameter(type="string", enum=["red", "green", "blue"])},
    )
    d = schema.to_dict()
    assert d["properties"]["color"]["enum"] == ["red", "green", "blue"]
