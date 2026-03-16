import hashlib
import secrets

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from taskmeagents.models.api_key import ApiKey


def generate_api_key() -> str:
    """Generate a cryptographically secure API key."""
    return f"tma_{secrets.token_urlsafe(32)}"


def hash_api_key(key: str) -> str:
    """Hash an API key using SHA-256."""
    return hashlib.sha256(key.encode()).hexdigest()


async def validate_api_key(db: AsyncSession, key: str) -> ApiKey | None:
    """Validate an API key and return the associated record, or None if invalid."""
    key_hash = hash_api_key(key)
    result = await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True)))
    api_key = result.scalar_one_or_none()
    if api_key:
        await db.execute(
            update(ApiKey).where(ApiKey.id == api_key.id).values(last_used_at=func.now())
        )
        await db.commit()
    return api_key


async def create_api_key(db: AsyncSession, name: str, user_id: str) -> tuple[str, ApiKey]:
    """Create a new API key. Returns (plaintext_key, api_key_record)."""
    raw_key = generate_api_key()
    api_key = ApiKey(key_hash=hash_api_key(raw_key), name=name, user_id=user_id)
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return raw_key, api_key
