---
description: Use when writing tests, creating test fixtures, setting up test infrastructure, or discussing test coverage for TaskMeAgents.
---

# Testing Patterns — TaskMeAgents

## Test Structure
```
tests/
  unit/          Pure functions, no I/O, no mocking (48 tests)
  integration/   Real DB (SQLite), FastAPI TestClient (15 tests)
  mock/          Mocked externals: LLM, Temporal, WebSocket (19 tests)
  workflow/      Temporal test environment (3 tests, @pytest.mark.temporal)
  e2e/           Full stack (1 test, @pytest.mark.temporal)
  fixtures/      Shared test data
    agents.py    SAMPLE_AGENT_CONFIG, etc.
    messages.py  make_user_message(), make_tool_request(), etc.
```

## Run Commands
```bash
pytest tests/ -m "not temporal" -v          # All except Temporal-dependent
pytest tests/unit/ -v                        # Unit only (fast)
pytest tests/ --cov=taskmeagents            # With coverage
```

## Unit Test Pattern
```python
from tests.fixtures.messages import make_user_message, make_tool_result

def test_my_pure_function():
    msg = make_user_message("Hello", turn=1)
    result = my_function(msg)
    assert result == expected
```

## Integration Test Pattern (FastAPI + SQLite)
```python
@pytest_asyncio.fixture
async def app_client(pg_session, session_factory):
    app = create_app()
    init_history_store(session_factory)
    init_agent_factory(session_factory)
    app.dependency_overrides[get_db] = lambda: pg_session  # Override DB
    app.dependency_overrides[get_current_user] = lambda: AuthUser(user_id="test", key_name="test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_create_item(app_client):
    r = await app_client.post("/api/items", json={...})
    assert r.status_code == 201
```

## Mock LLM Provider Pattern
```python
# Anthropic: use MockStreamContext (async iterable + get_final_message)
class MockStreamContext:
    def __aiter__(self): return self._async_iter()
    async def _async_iter(self):
        for e in self.events: yield e
    def get_final_message(self): return self._final

# OpenAI: use _MockAsyncStream (awaitable + async iterable)
class _MockAsyncStream:
    def __await__(self): ...     # returns self
    def __aiter__(self): ...     # yields chunks
```

## Workflow Test Pattern
```python
pytestmark = pytest.mark.temporal

from temporalio import activity as activity_mod

@activity_mod.defn(name="ProcessUserMessage")  # MUST have decorator + name
async def mock_activity(*args) -> ActivityResult:
    return ActivityResult(messages=[...])

async def test_workflow():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(env.client, task_queue="q", workflows=[...], activities=[mock_activity]):
            ...
```

## Key Rule
Mock activities MUST be decorated with `@activity.defn(name="...")` — Temporal requires it for registration.
