Run tests for the TaskMeAgents project.

**Input**: $ARGUMENTS — test scope or mode (see options below).

## Modes

### By Layer
| Argument | Command | What it runs |
|----------|---------|-------------|
| *(empty)* | `pytest tests/ -m "not temporal" -v` | All tests except Temporal-dependent (82 tests) |
| `all` | `pytest tests/ -v` | Everything including Temporal tests (86 tests, needs Temporal server) |
| `unit` | `pytest tests/unit/ -v` | Pure function tests (48 tests, fastest) |
| `integration` | `pytest tests/integration/ -v` | DB + API tests via SQLite (15 tests) |
| `mock` | `pytest tests/mock/ -v` | Mocked LLM + Temporal + WebSocket (19 tests) |
| `workflow` | `pytest tests/workflow/ -v` | Temporal test environment (3 tests, needs Temporal) |
| `e2e` | `pytest tests/e2e/ -v` | Full stack tests (1 test, needs Temporal) |
| `quick` | `pytest tests/unit/ -v --tb=line` | Unit only, minimal output (fastest CI check) |

### By Feature
| Argument | Command | What it tests |
|----------|---------|--------------|
| `auth` | `pytest tests/unit/test_auth.py tests/integration/test_api_auth.py -v` | API key generation, hashing, validation |
| `masking` | `pytest tests/unit/test_masking.py -v` | Observation masking (8 edge cases) |
| `llm` | `pytest tests/mock/test_anthropic_provider.py tests/mock/test_openai_provider.py -v` | Both LLM providers |
| `mcp` | `pytest tests/unit/test_mcp_converters.py tests/unit/test_mcp_passthrough.py -v` | MCP converters + headers |
| `api` | `pytest tests/integration/test_api_agents.py tests/integration/test_api_auth.py tests/integration/test_api_models.py -v` | All REST endpoints |
| `agents` | `pytest tests/integration/test_api_agents.py tests/mock/test_agent_factory.py -v` | Agent CRUD + factory |
| `streaming` | `pytest tests/mock/test_companion_service.py -v` | Two-phase streaming, auto-approve |
| `attachments` | `pytest tests/integration/test_attachment_storage.py tests/unit/test_attachment_sanitization.py -v` | File storage + sanitization |

### Special Modes
| Argument | Command | Purpose |
|----------|---------|---------|
| `coverage` | `pytest tests/ -m "not temporal" --cov=taskmeagents --cov-report=term-missing` | Coverage report with missing lines |
| `coverage-html` | `pytest tests/ -m "not temporal" --cov=taskmeagents --cov-report=html && open htmlcov/index.html` | HTML coverage report |
| `failing` | `pytest tests/ -m "not temporal" --lf -v` | Re-run only previously failed tests |
| `new` | `pytest tests/ -m "not temporal" --new-first -v` | Run new/modified tests first |

### By File
If $ARGUMENTS is a file path or partial name:
```bash
pytest tests/**/*$ARGUMENTS* -v
```
Example: `/test masking` → finds `tests/unit/test_masking.py`

## After Failures

When tests fail:
1. **Read the failure output** — identify the assertion or exception
2. **Check the source file** referenced in the traceback
3. **Determine root cause**:
   - Import error → check for missing dependency or circular import
   - AttributeError → check Temporal determinism rules (workflow.uuid4, workflow.now)
   - SQLite error → check integration conftest schema stripping
   - Serialization error → check dataclass JSON compatibility
4. **Fix and re-run** only the failing test: `pytest tests/path/to/test.py::test_name -v`
5. **Run full suite** to verify no regressions

## After Code Changes

When source files are modified, run relevant tests:
| Changed file | Tests to run |
|-------------|-------------|
| `workflow/*.py` | `pytest tests/mock/test_companion_service.py tests/unit/test_conversation_state.py -v` |
| `activities/*.py` | `pytest tests/unit/test_message_conversion.py -v` |
| `llm/*.py` | `pytest tests/mock/test_anthropic_provider.py tests/mock/test_openai_provider.py tests/unit/test_cost_calculation.py -v` |
| `mcp/*.py` | `pytest tests/unit/test_mcp_converters.py tests/unit/test_mcp_passthrough.py -v` |
| `api/*.py` | `pytest tests/integration/test_api_agents.py tests/integration/test_api_auth.py tests/integration/test_api_models.py -v` |
| `history/*.py` | `pytest tests/integration/test_attachment_storage.py tests/unit/test_masking.py -v` |
| `auth/*.py` | `pytest tests/unit/test_auth.py tests/integration/test_api_auth.py -v` |
| `models/*.py` | `pytest tests/integration/ -v` |
| `conversation/*.py` | `pytest tests/unit/test_masking.py tests/unit/test_conversation_state.py -v` |

## Test Infrastructure
- **SQLite adapter** in `tests/integration/conftest.py` handles JSONB→JSON, ARRAY→JSON, UUID→VARCHAR
- **Schema stripping**: `Base.metadata` schema set to `None` for SQLite (no schema support)
- **Auth override**: `app.dependency_overrides[get_current_user]` skips API key validation in tests
- **Temporal marker**: `@pytest.mark.temporal` on tests needing Temporal server
