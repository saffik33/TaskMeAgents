import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from taskmeagents.database import Base


class McpServerConfig(Base):
    __tablename__ = "mcp_server_configs"

    mcp_server_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    use_tls: Mapped[bool | None] = mapped_column(Boolean, default=True)
    auth_strategy: Mapped[str] = mapped_column(String(20), default="NONE")
    headers: Mapped[dict] = mapped_column(JSONB, default=dict)
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=False)
    passthrough_headers: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    included_tools: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
