---
description: Use when creating or modifying database models, SQLAlchemy ORM classes, Alembic migrations, database schema changes, or PostgreSQL queries in TaskMeAgents.
---

# Database & Migration Development — TaskMeAgents

## Schema: `taskme_agents`
ALL tables live in the `taskme_agents` schema, NOT `public`.

## Model Pattern
```python
from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from taskmeagents.database import Base

class MyModel(Base):
    __tablename__ = "my_table"
    # Base already has: metadata = MetaData(schema="taskme_agents")

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

## Migration Pattern
```python
import os
SCHEMA = os.getenv("DATABASE_SCHEMA", "taskme_agents")

def upgrade() -> None:
    op.create_table(
        "my_table",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        schema=SCHEMA,  # REQUIRED — puts table in correct schema
    )
    op.create_index("idx_my_table_name", "my_table", ["name"], schema=SCHEMA)

def downgrade() -> None:
    op.drop_table("my_table", schema=SCHEMA)
```

## ForeignKey References
```python
sa.ForeignKey(f"{SCHEMA}.sessions.id")  # Cross-table FK with schema prefix
```

## Idempotent Writes
```python
from sqlalchemy.dialects.postgresql import insert

stmt = insert(MyModel).values(...).on_conflict_do_nothing(index_elements=["id"])
```

## Commands
```bash
# Create migration
alembic revision --autogenerate -m "add my_table"

# Run migrations
alembic upgrade head

# Check current version
alembic current
```

## Key Files
- `src/taskmeagents/models/` — SQLAlchemy ORM models
- `src/taskmeagents/database.py` — engine, Base, session factory
- `alembic/versions/` — migration scripts
- `alembic/env.py` — migration config (schema-aware)
