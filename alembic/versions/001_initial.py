"""Initial schema - sessions, messages, agents, mcp_server_configs, api_keys

Revision ID: 001
Revises:
Create Date: 2026-03-14
"""

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = os.getenv("DATABASE_SCHEMA", "taskme_agents")


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    # --- sessions ---
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("agent_id", sa.String(255), nullable=False),
        sa.Column("parent_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.sessions.id"), nullable=True),
        sa.Column("status", sa.String(20), server_default="running"),
        sa.Column("message_count", sa.Integer, server_default="0"),
        sa.Column("turn_count", sa.Integer, server_default="0"),
        sa.Column("token_usage", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("delegation_depth", sa.Integer, server_default="0"),
        schema=SCHEMA,
    )
    op.create_index("idx_sessions_user", "sessions", ["user_id", sa.text("last_activity_at DESC")], schema=SCHEMA)
    op.create_index("idx_sessions_agent", "sessions", ["agent_id"], schema=SCHEMA)
    op.create_index("idx_sessions_status", "sessions", ["status"], postgresql_where=sa.text("status = 'running'"), schema=SCHEMA)

    # --- messages ---
    op.create_table(
        "messages",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.sessions.id"), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", postgresql.JSONB, nullable=False),
        sa.Column("turn_number", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", "sequence"),
        schema=SCHEMA,
    )
    op.create_index("idx_messages_session", "messages", ["session_id", "sequence"], schema=SCHEMA)
    op.create_index("idx_messages_content", "messages", ["content"], postgresql_using="gin", schema=SCHEMA)

    # --- agents ---
    op.create_table(
        "agents",
        sa.Column("agent_id", sa.String(255), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("client_tools", postgresql.JSONB, server_default="[]"),
        sa.Column("mcp_server_ids", postgresql.ARRAY(sa.Text), server_default="{}"),
        sa.Column("sub_agents", postgresql.ARRAY(sa.Text), server_default="{}"),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("max_tokens", sa.Integer, server_default="4096"),
        sa.Column("temperature", sa.Float, server_default="0.7"),
        sa.Column("use_prompt_cache", sa.Boolean, server_default="false"),
        sa.Column("thinking", postgresql.JSONB, server_default="{}"),
        sa.Column("observation_masking", postgresql.JSONB, server_default='{"enabled": true, "recent_window_turns": 3}'),
        sa.Column("tool", postgresql.JSONB, nullable=True),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("version_comment", sa.String(500), server_default=""),
        sa.Column("updated_by", sa.String(255), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema=SCHEMA,
    )

    # --- agent_versions ---
    op.create_table(
        "agent_versions",
        sa.Column("agent_id", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("config", postgresql.JSONB, nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("agent_id", "version"),
        schema=SCHEMA,
    )

    # --- mcp_server_configs ---
    op.create_table(
        "mcp_server_configs",
        sa.Column("mcp_server_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(63), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.String(10), nullable=False),
        sa.Column("path", sa.Text, nullable=False),
        sa.Column("use_tls", sa.Boolean, server_default="true"),
        sa.Column("auth_strategy", sa.String(20), server_default="NONE"),
        sa.Column("headers", postgresql.JSONB, server_default="{}"),
        sa.Column("auto_approve", sa.Boolean, server_default="false"),
        sa.Column("passthrough_headers", postgresql.ARRAY(sa.Text), server_default="{}"),
        sa.Column("included_tools", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(255), nullable=True),
        schema=SCHEMA,
    )

    # --- api_keys ---
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("idx_api_keys_hash", "api_keys", ["key_hash"], postgresql_where=sa.text("is_active = true"), schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("api_keys", schema=SCHEMA)
    op.drop_table("mcp_server_configs", schema=SCHEMA)
    op.drop_table("agent_versions", schema=SCHEMA)
    op.drop_table("agents", schema=SCHEMA)
    op.drop_table("messages", schema=SCHEMA)
    op.drop_table("sessions", schema=SCHEMA)
