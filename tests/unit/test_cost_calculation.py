"""Unit tests for token cost calculation."""

from taskmeagents.conversation.types import TokenUsage
from taskmeagents.llm.models import calculate_cost


def test_calculate_cost_anthropic():
    usage = TokenUsage(input_tokens=1000, output_tokens=500, cache_read_tokens=200, cache_write_tokens=100)
    cost = calculate_cost("claude-sonnet-4-6", usage)
    # Sonnet 4.6: input=$3/1M, output=$15/1M, cache_read=$0.30/1M, cache_write=$3.75/1M
    expected = (1000 * 3.0 + 500 * 15.0 + 200 * 0.30 + 100 * 3.75) / 1_000_000
    assert abs(cost - expected) < 1e-10


def test_calculate_cost_openai():
    usage = TokenUsage(input_tokens=1000, output_tokens=500)
    cost = calculate_cost("gpt-4o", usage)
    # GPT-4o: input=$2.50/1M, output=$10.00/1M
    expected = (1000 * 2.50 + 500 * 10.0) / 1_000_000
    assert abs(cost - expected) < 1e-10


def test_calculate_cost_unknown_model():
    usage = TokenUsage(input_tokens=1000, output_tokens=500)
    assert calculate_cost("unknown-model-xyz", usage) == 0.0
