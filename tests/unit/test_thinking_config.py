"""Unit tests for ThinkingConfig."""

from taskmeagents.llm.thinking import ThinkingConfig, ThinkingMode


def test_thinking_disabled():
    cfg = ThinkingConfig()
    assert cfg.is_enabled is False
    assert cfg.mode == ThinkingMode.DISABLED


def test_thinking_manual():
    cfg = ThinkingConfig(mode=ThinkingMode.MANUAL, budget_tokens=8000)
    assert cfg.is_enabled is True
    assert cfg.budget_tokens == 8000


def test_thinking_adaptive():
    cfg = ThinkingConfig(mode=ThinkingMode.ADAPTIVE)
    assert cfg.is_enabled is True
