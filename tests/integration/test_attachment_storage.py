"""Integration tests for attachment file storage."""

import pytest
import pytest_asyncio

from taskmeagents.conversation.types import Attachment
from taskmeagents.history.attachments import _sanitize_filename, rehydrate, upload_and_strip


@pytest.fixture
def attachment_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("taskmeagents.history.attachments.settings.attachment_base_path", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_upload_and_strip(attachment_dir):
    att = Attachment(filename="test.txt", mime_type="text/plain", data=b"hello world")
    await upload_and_strip("user1", "session1", "msg1", [att])

    assert att.data is None
    assert att.uri is not None
    assert (attachment_dir / "user1" / "session1" / "msg1" / "test.txt").exists()


@pytest.mark.asyncio
async def test_rehydrate(attachment_dir):
    att = Attachment(filename="test.txt", mime_type="text/plain", data=b"hello world")
    await upload_and_strip("user1", "session1", "msg1", [att])

    att2 = Attachment(filename="test.txt", mime_type="text/plain", data=None)
    await rehydrate("user1", "session1", "msg1", [att2])
    assert att2.data == b"hello world"


@pytest.mark.asyncio
async def test_rehydrate_missing_file(attachment_dir):
    att = Attachment(filename="missing.txt", mime_type="text/plain", data=None)
    await rehydrate("user1", "session1", "msg1", [att])
    assert att.data is None  # no crash


@pytest.mark.asyncio
async def test_path_traversal_blocked(attachment_dir):
    # Empty or dot-prefixed filenames are rejected
    att = Attachment(filename=".env", mime_type="text/plain", data=b"bad")
    with pytest.raises(ValueError):
        await upload_and_strip("user1", "session1", "msg1", [att])
    # Traversal paths get basename-stripped (safe), but empty results raise
    att2 = Attachment(filename="../../", mime_type="text/plain", data=b"bad")
    with pytest.raises(ValueError):
        await upload_and_strip("user1", "session1", "msg1", [att2])
