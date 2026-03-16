Review code changes for the TaskMeAgents project.

**Input**: $ARGUMENTS — file paths, PR description, or "all changed files".

## Review Checklist

### Temporal Workflow Correctness
- [ ] No `uuid.uuid4()` in workflow code (use `workflow.uuid4()`)
- [ ] No `datetime.now()` in workflow code (use `workflow.now()`)
- [ ] No bare imports in workflow files (use `workflow.unsafe.imports_passed_through()`)
- [ ] Update handlers call `await self._wait_for_state()` first
- [ ] Activities pass `result_type=ActivityResult` to `_execute_activity()`
- [ ] No `__import__()` or `random` in workflow code

### Database & Persistence
- [ ] New tables/columns have alembic migration with `schema=SCHEMA`
- [ ] Message writes use `INSERT ON CONFLICT DO NOTHING` for idempotency
- [ ] Session upserts handle both insert and update paths
- [ ] No raw SQL without parameterized queries (SQL injection risk)

### API & WebSocket
- [ ] WebSocket validates API key BEFORE `ws.accept()`
- [ ] REST endpoints use `Depends(get_current_user)` for auth
- [ ] Route ordering: specific paths before `/{param}` catch-alls
- [ ] Pydantic schemas match the data being sent/received

### LLM Providers
- [ ] Streaming properly yields MessageEvent, UsageEvent, ErrorEvent
- [ ] Tool use parameters JSON-parsed with error handling
- [ ] Stop reason correctly mapped from provider-specific values
- [ ] Usage tokens accumulated correctly

### General Python
- [ ] No circular imports (check import graph)
- [ ] Async functions properly awaited
- [ ] No blocking calls in async context
- [ ] Error handling: specific exceptions, not bare `except`
- [ ] Type annotations consistent

### Tests
- [ ] New code has corresponding tests
- [ ] `pytest tests/ -m "not temporal" -v` passes
- [ ] Edge cases covered (empty input, None values, error paths)
