"""Integration tests for model listing endpoint."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def app_client(pg_session, session_factory):
    from taskmeagents.main import create_app
    from taskmeagents.services.agent_factory import init_agent_factory, init_history_store

    app = create_app()
    init_history_store(session_factory)
    init_agent_factory(session_factory)

    async def override_get_db():
        yield pg_session

    from taskmeagents.auth.middleware import AuthUser, get_current_user
    from taskmeagents.database import get_db
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: AuthUser(user_id="test", key_name="test")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_list_models(app_client):
    r = await app_client.get("/api/models")
    assert r.status_code == 200
    models = r.json()
    assert len(models) >= 5  # At least Claude + OpenAI models
    model_ids = {m["id"] for m in models}
    assert "claude-sonnet-4-6" in model_ids
    assert "gpt-4o" in model_ids


@pytest.mark.asyncio
async def test_model_fields(app_client):
    r = await app_client.get("/api/models")
    model = r.json()[0]
    assert "id" in model
    assert "display_name" in model
    assert "vendor" in model
    assert "context_window" in model
    assert "input_price" in model
    assert "thinking_support" in model
