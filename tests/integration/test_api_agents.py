"""Integration tests for Agent CRUD API endpoints."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.fixtures.agents import SAMPLE_AGENT_CONFIG


@pytest_asyncio.fixture
async def app_client(pg_session, session_factory):
    """FastAPI test client with DB dependency override."""
    from unittest.mock import patch

    from taskmeagents.main import create_app
    from taskmeagents.services.agent_factory import init_agent_factory, init_history_store

    app = create_app()
    init_history_store(session_factory)
    init_agent_factory(session_factory)

    # Override DB dependency
    async def override_get_db():
        yield pg_session

    from taskmeagents.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    # Override auth to skip API key validation
    from taskmeagents.auth.middleware import AuthUser, get_current_user
    app.dependency_overrides[get_current_user] = lambda: AuthUser(user_id="test-user", key_name="test")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_list_agents_empty(app_client):
    r = await app_client.get("/api/agents")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_create_agent(app_client):
    r = await app_client.post("/api/agents", json=SAMPLE_AGENT_CONFIG)
    assert r.status_code == 201
    data = r.json()
    assert data["agent_id"] == SAMPLE_AGENT_CONFIG["agent_id"]
    assert data["version"] == 1


@pytest.mark.asyncio
async def test_create_agent_duplicate(app_client):
    await app_client.post("/api/agents", json=SAMPLE_AGENT_CONFIG)
    r = await app_client.post("/api/agents", json=SAMPLE_AGENT_CONFIG)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_get_agent(app_client):
    await app_client.post("/api/agents", json=SAMPLE_AGENT_CONFIG)
    r = await app_client.get(f"/api/agents/{SAMPLE_AGENT_CONFIG['agent_id']}")
    assert r.status_code == 200
    assert r.json()["name"] == SAMPLE_AGENT_CONFIG["name"]


@pytest.mark.asyncio
async def test_update_agent_version_increment(app_client):
    await app_client.post("/api/agents", json=SAMPLE_AGENT_CONFIG)
    r = await app_client.put(
        f"/api/agents/{SAMPLE_AGENT_CONFIG['agent_id']}",
        json={"name": "Updated Name", "version_comment": "rename"},
    )
    assert r.status_code == 200
    assert r.json()["version"] == 2
    assert r.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_delete_agent(app_client):
    await app_client.post("/api/agents", json=SAMPLE_AGENT_CONFIG)
    r = await app_client.delete(f"/api/agents/{SAMPLE_AGENT_CONFIG['agent_id']}")
    assert r.status_code == 204
    r2 = await app_client.get(f"/api/agents/{SAMPLE_AGENT_CONFIG['agent_id']}")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_rollback_agent(app_client):
    config = {**SAMPLE_AGENT_CONFIG, "agent_id": "rollback-test-agent"}
    await app_client.post("/api/agents", json=config)
    await app_client.put(
        f"/api/agents/{config['agent_id']}",
        json={"name": "V2 Name", "version_comment": "v2"},
    )
    r = await app_client.post(
        f"/api/agents/{config['agent_id']}/rollback",
        json={"version": 1},
    )
    assert r.status_code == 200
    assert r.json()["version"] == 3  # new version after rollback
