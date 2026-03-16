"""Extended thinking / reasoning configuration.

Translated from go_companion/internal/llm/thinking.go
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ThinkingSupport(str, Enum):
    NONE = "none"
    MANUAL = "manual"
    ADAPTIVE = "adaptive"


class ThinkingMode(str, Enum):
    DISABLED = "disabled"
    MANUAL = "manual"
    ADAPTIVE = "adaptive"


class EffortLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAX = "max"


@dataclass
class ThinkingConfig:
    mode: ThinkingMode = ThinkingMode.DISABLED
    budget_tokens: int = 0  # For manual mode
    effort: EffortLevel = EffortLevel.MEDIUM  # For adaptive mode

    @property
    def is_enabled(self) -> bool:
        return self.mode != ThinkingMode.DISABLED
