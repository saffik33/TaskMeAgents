from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from taskmeagents.database import Base


class Agent(Base):
    __tablename__ = "agents"

    agent_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    client_tools: Mapped[list] = mapped_column(JSONB, default=list)
    mcp_server_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    sub_agents: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    use_prompt_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    thinking: Mapped[dict] = mapped_column(JSONB, default=dict)
    observation_masking: Mapped[dict] = mapped_column(
        JSONB, default=lambda: {"enabled": True, "recent_window_turns": 3}
    )
    tool: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    version_comment: Mapped[str] = mapped_column(String(500), default="")
    updated_by: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentVersion(Base):
    __tablename__ = "agent_versions"

    agent_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
