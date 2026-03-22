"""API key management REST endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from taskmeagents.auth.api_key import create_api_key
from taskmeagents.auth.middleware import AuthUser, get_current_user
from taskmeagents.database import get_db

router = APIRouter(prefix="/api/keys", tags=["keys"])


class CreateKeyRequest(BaseModel):
    user_id: str
    name: str


class CreateKeyResponse(BaseModel):
    key: str
    key_id: str


@router.post("", response_model=CreateKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    body: CreateKeyRequest,
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(get_current_user),
):
    """Create a new API key. The plaintext key is returned once and cannot be retrieved again."""
    raw_key, api_key = await create_api_key(db, body.name, body.user_id)
    return CreateKeyResponse(key=raw_key, key_id=str(api_key.id))
