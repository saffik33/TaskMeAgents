"""Integration test fixtures — SQLite with type adaptation for JSONB/ARRAY/UUID."""

import asyncio

import pytest
import pytest_asyncio
from sqlalchemy import JSON, String, Text, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from taskmeagents.database import Base


# Patch PostgreSQL-specific types for SQLite compatibility
def _adapt_schema_for_sqlite():
    """Replace PostgreSQL-specific column types with SQLite-compatible ones."""
    import json as json_mod

    from sqlalchemy import TypeDecorator
    from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
    from sqlalchemy.ext.compiler import compiles

    # Type decorator that JSON-serializes lists for SQLite binding
    class JSONArray(TypeDecorator):
        impl = JSON
        cache_ok = True

        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            return value  # JSON column handles list→string

        def process_result_value(self, value, dialect):
            if value is None:
                return []
            if isinstance(value, str):
                return json_mod.loads(value)
            return value

    @compiles(JSONB, "sqlite")
    def compile_jsonb_sqlite(type_, compiler, **kw):
        return "JSON"

    @compiles(ARRAY, "sqlite")
    def compile_array_sqlite(type_, compiler, **kw):
        return "JSON"

    @compiles(UUID, "sqlite")
    def compile_uuid_sqlite(type_, compiler, **kw):
        return "VARCHAR(36)"

    # Monkey-patch ARRAY to behave like JSON in SQLite
    original_array_bind = ARRAY.bind_processor

    def patched_bind_processor(self, dialect):
        if dialect.name == "sqlite":
            def process(value):
                if value is None:
                    return None
                return json_mod.dumps(value)
            return process
        if hasattr(original_array_bind, '__func__'):
            return original_array_bind(self, dialect)
        return None

    ARRAY.bind_processor = patched_bind_processor

    original_array_result = ARRAY.result_processor

    def patched_result_processor(self, dialect, coltype):
        if dialect.name == "sqlite":
            def process(value):
                if value is None:
                    return []
                if isinstance(value, str):
                    return json_mod.loads(value)
                return value
            return process
        if hasattr(original_array_result, '__func__'):
            return original_array_result(self, dialect, coltype)
        return None

    ARRAY.result_processor = patched_result_processor


_adapt_schema_for_sqlite()


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def pg_engine():
    """SQLite engine with PostgreSQL type adaptations for fast integration tests."""
    # Strip schema from metadata � SQLite doesn't support schemas
    for table in list(Base.metadata.tables.values()):
        table.schema = None

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_session(pg_engine):
    """Session with automatic rollback after each test."""
    factory = async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def session_factory(pg_engine):
    """Session factory for stores that need to create their own sessions."""
    return async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def history_store(session_factory):
    from taskmeagents.history.pg_store import PostgresHistoryStore
    return PostgresHistoryStore(session_factory)
