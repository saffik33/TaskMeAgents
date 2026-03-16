"""Test agent configurations."""

SAMPLE_AGENT_CONFIG = {
    "agent_id": "test-agent-001",
    "name": "Test Agent",
    "system_prompt": "You are a helpful test assistant.",
    "model": "claude-sonnet-4-6",
    "max_tokens": 4096,
    "temperature": 0.7,
    "client_tools": [],
    "mcp_server_ids": [],
    "sub_agents": [],
    "use_prompt_cache": False,
    "thinking": {"mode": "disabled"},
    "observation_masking": {"enabled": True, "recent_window_turns": 3},
    "tool": None,
    "version_comment": "initial",
}

SAMPLE_AGENT_WITH_TOOLS = {
    **SAMPLE_AGENT_CONFIG,
    "agent_id": "test-agent-tools",
    "client_tools": [
        {
            "name": "get_weather",
            "description": "Get weather for a city",
            "input_schema": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "City name"}},
                "required": ["city"],
            },
        }
    ],
}

SAMPLE_SUB_AGENT_CONFIG = {
    **SAMPLE_AGENT_CONFIG,
    "agent_id": "test-sub-agent",
    "name": "Test Sub Agent",
    "tool": {
        "name": "research",
        "description": "Research a topic",
        "input_schema": {
            "type": "object",
            "properties": {"topic": {"type": "string"}},
            "required": ["topic"],
        },
    },
}

SAMPLE_PARENT_AGENT_CONFIG = {
    **SAMPLE_AGENT_CONFIG,
    "agent_id": "test-parent-agent",
    "name": "Test Parent Agent",
    "sub_agents": ["test-sub-agent"],
}
