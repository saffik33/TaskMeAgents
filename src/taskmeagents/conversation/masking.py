"""Observation masking for context window optimization.

Translated from go_companion/internal/conversation/masking/masking.go

Replaces stale tool results (older than recent_window_turns) with a compact
placeholder when context usage exceeds 75% of the model's context window.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from taskmeagents.conversation.types import Message, TokenUsage

MASKED_PLACEHOLDER = "[Tool result omitted -- outside recent context window]"
CONTEXT_THRESHOLD = 0.75


@dataclass
class MaskingConfig:
    enabled: bool = True
    recent_window_turns: int = 3


def apply_observation_masking(
    messages: list[Message],
    current_turn: int,
    config: MaskingConfig,
    total_tokens: int,
    max_context_tokens: int,
) -> list[Message]:
    """Apply observation masking to conversation history.

    Returns a new list with stale tool results replaced by placeholders.
    Original messages are not modified.
    """
    if not config.enabled:
        return messages

    if max_context_tokens <= 0:
        return messages

    if total_tokens < max_context_tokens * CONTEXT_THRESHOLD:
        return messages

    result = []
    for msg in messages:
        if msg.tool_result is not None:
            age = current_turn - msg.turn_number
            if age >= config.recent_window_turns:
                masked = copy.copy(msg)
                masked.tool_result = copy.copy(msg.tool_result)
                masked.tool_result.content = MASKED_PLACEHOLDER
                masked.tool_result.data = None
                masked.tool_result.attachments = None
                result.append(masked)
                continue
        result.append(msg)

    return result
