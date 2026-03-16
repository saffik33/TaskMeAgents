"""Model listing endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from taskmeagents.auth.middleware import AuthUser, get_current_user
from taskmeagents.llm.models import REGISTRY

router = APIRouter(prefix="/api/models", tags=["models"])


class ModelResponse(BaseModel):
    id: str
    display_name: str
    vendor: str
    provider_type: str
    context_window: int
    max_output_tokens: int
    input_price: float
    output_price: float
    supports_tool_use: bool
    supports_vision: bool
    thinking_support: str


@router.get("", response_model=list[ModelResponse])
async def list_models(_: AuthUser = Depends(get_current_user)):
    return [
        ModelResponse(
            id=m.id, display_name=m.display_name, vendor=m.vendor.value,
            provider_type=m.provider_type.value, context_window=m.context_window,
            max_output_tokens=m.max_output_tokens, input_price=m.prices.input,
            output_price=m.prices.output, supports_tool_use=m.capabilities.tool_use,
            supports_vision=m.capabilities.vision, thinking_support=m.capabilities.thinking.value,
        )
        for m in REGISTRY.values()
    ]
