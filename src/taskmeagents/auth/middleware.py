from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from taskmeagents.auth.api_key import validate_api_key
from taskmeagents.database import get_db


@dataclass
class AuthUser:
    user_id: str
    key_name: str


async def get_current_user(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> AuthUser:
    """FastAPI dependency that validates the API key and returns the authenticated user."""
    api_key = await validate_api_key(db, x_api_key)
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key")
    return AuthUser(user_id=api_key.user_id, key_name=api_key.name)
