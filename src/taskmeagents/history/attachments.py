"""Attachment storage on Railway persistent volume.

Replaces S3-based storage from go_companion/internal/history/attachments.go
"""

from __future__ import annotations

import os
from pathlib import Path

import aiofiles

from taskmeagents.config import settings
from taskmeagents.conversation.types import Attachment


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks."""
    safe = os.path.basename(filename)
    if not safe or safe.startswith("."):
        raise ValueError(f"Invalid filename: {filename}")
    return safe


def _attachment_dir(user_id: str, session_id: str, message_id: str) -> Path:
    return Path(settings.attachment_base_path) / user_id / session_id / message_id


async def upload_and_strip(
    user_id: str, session_id: str, message_id: str, attachments: list[Attachment]
) -> None:
    """Save attachment data to volume and nil out binary data."""
    base = _attachment_dir(user_id, session_id, message_id)
    base.mkdir(parents=True, exist_ok=True)
    for att in attachments:
        if att.data is None:
            continue
        safe_name = _sanitize_filename(att.filename)
        file_path = base / safe_name
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(att.data)
        att.uri = str(file_path)
        att.data = None  # strip binary before sending through Temporal


async def rehydrate(
    user_id: str, session_id: str, message_id: str, attachments: list[Attachment]
) -> None:
    """Read attachment data back from volume."""
    base = _attachment_dir(user_id, session_id, message_id)
    for att in attachments:
        if att.data is not None:
            continue
        safe_name = _sanitize_filename(att.filename)
        file_path = base / safe_name
        if file_path.exists():
            async with aiofiles.open(file_path, "rb") as f:
                att.data = await f.read()


async def delete_attachments(user_id: str, session_id: str, message_id: str) -> None:
    """Delete all attachments for a message."""
    base = _attachment_dir(user_id, session_id, message_id)
    if base.exists():
        for f in base.iterdir():
            f.unlink()
        base.rmdir()
