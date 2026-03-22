import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from taskmeagents.database import Base
from taskmeagents.models import *  # noqa: F401, F403 — import all models for metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override URL from environment variable if set
database_url = os.getenv("DATABASE_URL")
if database_url:
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    config.set_main_option("sqlalchemy.url", database_url)
else:
    # Import from app config as fallback (reads .env file + env vars)
    from taskmeagents.config import settings
    config.set_main_option("sqlalchemy.url", settings.database_url)

database_schema = os.getenv("DATABASE_SCHEMA", "taskme_agents")

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=database_schema,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=database_schema,
        include_schemas=True,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    from sqlalchemy import text

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        # Create schema BEFORE alembic tries to create alembic_version table in it
        await connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{database_schema}"'))
        await connection.commit()
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
