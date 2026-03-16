"""FastAPI application entry point with Temporal worker.

Initializes all services on startup:
- PostgreSQL (async SQLAlchemy)
- Temporal client (self-hosted on Railway)
- MCP registry (global singleton)
- Agent factory (cached agent instances)
- History store (PostgreSQL)

Runs Temporal worker as a background task alongside the FastAPI server.
"""

from __future__ import annotations

import asyncio
import hashlib

import structlog
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from taskmeagents.config import settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # --- Startup ---
    logger.info("taskme.startup", port=settings.port)

    # 1. Init database
    from taskmeagents.database import async_session_factory, init_db
    await init_db()
    logger.info("taskme.db.connected")

    # 2. Init history store
    from taskmeagents.services.agent_factory import init_history_store
    init_history_store(async_session_factory)

    # 3. Init MCP registry
    from taskmeagents.mcp.registry import init_mcp_registry
    init_mcp_registry()

    # 4. Init agent factory
    from taskmeagents.services.agent_factory import init_agent_factory
    init_agent_factory(async_session_factory)

    # 5. Connect Temporal
    from taskmeagents.temporal_.client import connect_temporal
    temporal_client = await connect_temporal()
    logger.info("taskme.temporal.connected", address=settings.temporal_address)

    # 6. Seed admin API key if configured
    if settings.admin_api_key:
        await _seed_admin_key()

    # 7. Start Temporal worker in background
    from taskmeagents.temporal_.worker import run_worker
    worker_task = asyncio.create_task(run_worker(temporal_client))
    logger.info("taskme.worker.started", task_queue=settings.temporal_task_queue)

    yield

    # --- Shutdown ---
    logger.info("taskme.shutdown")
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

    from taskmeagents.temporal_.client import close_temporal
    await close_temporal()

    from taskmeagents.mcp.registry import get_mcp_registry
    await get_mcp_registry().shutdown()

    from taskmeagents.services.agent_factory import get_agent_factory
    await get_agent_factory().shutdown()

    from taskmeagents.database import close_db
    await close_db()

    logger.info("taskme.shutdown.complete")


async def _seed_admin_key():
    """Seed the admin API key on first startup if ADMIN_API_KEY is set."""
    from sqlalchemy import select
    from taskmeagents.database import async_session_factory
    from taskmeagents.models.api_key import ApiKey

    key_hash = hashlib.sha256(settings.admin_api_key.encode()).hexdigest()
    async with async_session_factory() as db:
        existing = await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
        if not existing.scalar_one_or_none():
            admin_key = ApiKey(key_hash=key_hash, name="admin", user_id="admin")
            db.add(admin_key)
            await db.commit()
            logger.info("taskme.admin_key.seeded")


def create_app() -> FastAPI:
    app = FastAPI(
        title="TaskMe Agents",
        description="AI agents infrastructure for TaskMe",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check
    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # Routers
    from taskmeagents.api.websocket_chat import router as ws_router
    from taskmeagents.api.agents import router as agents_router
    from taskmeagents.api.mcp_servers import router as mcp_router
    from taskmeagents.api.sessions import router as sessions_router
    from taskmeagents.api.models_api import router as models_router

    app.include_router(ws_router)
    app.include_router(agents_router)
    app.include_router(mcp_router)
    app.include_router(sessions_router)
    app.include_router(models_router)

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "taskmeagents.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
