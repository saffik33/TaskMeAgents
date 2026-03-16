"""Integration tests for API key authentication middleware."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from taskmeagents.auth.api_key import create_api_key


@pytest_asyncio.fixture
async def app_with_auth(pg_session, session_factory):
    from taskmeagents.main import create_app
    from taskmeagents.services.agent_factory import init_agent_factory, init_history_store

    app = create_app()
    init_history_store(session_factory)
    init_agent_factory(session_factory)

    # Override DB dependency only (NOT auth — we test auth here)
    async def override_get_db():
        yield pg_session

    from taskmeagents.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    return app


@pytest_asyncio.fixture
async def auth_client(app_with_auth):
    async with AsyncClient(transport=ASGITransport(app=app_with_auth), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_valid_api_key(auth_client, pg_session):
    raw_key, _ = await create_api_key(pg_session, "test-key", "user-1")
    r = await auth_client.get("/api/agents", headers={"X-API-Key": raw_key})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_invalid_api_key(auth_client):
    r = await auth_client.get("/api/agents", headers={"X-API-Key": "tma_bad_key_12345"})
    assert r.status_code == 401
