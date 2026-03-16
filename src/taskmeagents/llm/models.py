"""LLM model registry with pricing and capabilities.

Translated from go_companion/internal/llm/models.go
Adapted for direct Anthropic + OpenAI SDKs (replacing Bedrock + Google).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from taskmeagents.conversation.types import TokenUsage
from taskmeagents.llm.thinking import ThinkingSupport


class Vendor(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class ProviderType(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


@dataclass
class Prices:
    input: float = 0.0  # per 1M tokens
    output: float = 0.0
    cache_read: float = 0.0
    cache_write: float = 0.0


@dataclass
class Capabilities:
    streaming: bool = True
    tool_use: bool = True
    vision: bool = False
    prompt_caching: bool = False
    thinking: ThinkingSupport = ThinkingSupport.NONE


@dataclass
class Model:
    id: str
    provider_model_id: str  # actual model ID sent to API
    display_name: str
    vendor: Vendor
    provider_type: ProviderType
    prices: Prices = field(default_factory=Prices)
    capabilities: Capabilities = field(default_factory=Capabilities)
    context_window: int = 128000
    max_output_tokens: int = 4096


# --- Model Registry ---

REGISTRY: dict[str, Model] = {
    # Anthropic models (direct API)
    "claude-opus-4-6": Model(
        id="claude-opus-4-6",
        provider_model_id="claude-opus-4-6-20250801",
        display_name="Claude Opus 4.6",
        vendor=Vendor.ANTHROPIC,
        provider_type=ProviderType.ANTHROPIC,
        prices=Prices(input=15.0, output=75.0, cache_read=1.5, cache_write=18.75),
        capabilities=Capabilities(
            streaming=True, tool_use=True, vision=True, prompt_caching=True, thinking=ThinkingSupport.ADAPTIVE
        ),
        context_window=200000,
        max_output_tokens=128000,
    ),
    "claude-sonnet-4-6": Model(
        id="claude-sonnet-4-6",
        provider_model_id="claude-sonnet-4-6-20250514",
        display_name="Claude Sonnet 4.6",
        vendor=Vendor.ANTHROPIC,
        provider_type=ProviderType.ANTHROPIC,
        prices=Prices(input=3.0, output=15.0, cache_read=0.3, cache_write=3.75),
        capabilities=Capabilities(
            streaming=True, tool_use=True, vision=True, prompt_caching=True, thinking=ThinkingSupport.MANUAL
        ),
        context_window=200000,
        max_output_tokens=64000,
    ),
    "claude-haiku-4-5": Model(
        id="claude-haiku-4-5",
        provider_model_id="claude-haiku-4-5-20251001",
        display_name="Claude Haiku 4.5",
        vendor=Vendor.ANTHROPIC,
        provider_type=ProviderType.ANTHROPIC,
        prices=Prices(input=0.80, output=4.0, cache_read=0.08, cache_write=1.0),
        capabilities=Capabilities(
            streaming=True, tool_use=True, vision=True, prompt_caching=True, thinking=ThinkingSupport.NONE
        ),
        context_window=200000,
        max_output_tokens=8192,
    ),
    # OpenAI models (direct API)
    "gpt-5.2": Model(
        id="gpt-5.2",
        provider_model_id="gpt-5.2",
        display_name="GPT-5.2",
        vendor=Vendor.OPENAI,
        provider_type=ProviderType.OPENAI,
        prices=Prices(input=5.0, output=20.0),
        capabilities=Capabilities(streaming=True, tool_use=True, vision=True),
        context_window=256000,
        max_output_tokens=32768,
    ),
    "gpt-4o": Model(
        id="gpt-4o",
        provider_model_id="gpt-4o",
        display_name="GPT-4o",
        vendor=Vendor.OPENAI,
        provider_type=ProviderType.OPENAI,
        prices=Prices(input=2.50, output=10.0),
        capabilities=Capabilities(streaming=True, tool_use=True, vision=True),
        context_window=128000,
        max_output_tokens=16384,
    ),
    "gpt-4o-mini": Model(
        id="gpt-4o-mini",
        provider_model_id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        vendor=Vendor.OPENAI,
        provider_type=ProviderType.OPENAI,
        prices=Prices(input=0.15, output=0.60),
        capabilities=Capabilities(streaming=True, tool_use=True, vision=True),
        context_window=128000,
        max_output_tokens=16384,
    ),
    "o3": Model(
        id="o3",
        provider_model_id="o3",
        display_name="o3",
        vendor=Vendor.OPENAI,
        provider_type=ProviderType.OPENAI,
        prices=Prices(input=10.0, output=40.0),
        capabilities=Capabilities(streaming=True, tool_use=True, vision=True),
        context_window=200000,
        max_output_tokens=100000,
    ),
    "o3-mini": Model(
        id="o3-mini",
        provider_model_id="o3-mini",
        display_name="o3 Mini",
        vendor=Vendor.OPENAI,
        provider_type=ProviderType.OPENAI,
        prices=Prices(input=1.10, output=4.40),
        capabilities=Capabilities(streaming=True, tool_use=True),
        context_window=200000,
        max_output_tokens=100000,
    ),
}


def get_model(model_id: str) -> Model | None:
    return REGISTRY.get(model_id)


def calculate_cost(model_id: str, usage: TokenUsage) -> float:
    model = REGISTRY.get(model_id)
    if not model:
        return 0.0
    p = model.prices
    cost = 0.0
    cost += usage.input_tokens * p.input / 1_000_000
    cost += usage.output_tokens * p.output / 1_000_000
    cost += usage.cache_read_tokens * p.cache_read / 1_000_000
    cost += usage.cache_write_tokens * p.cache_write / 1_000_000
    return cost
