from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/TaskMeAgents"

    @field_validator("database_url")
    @classmethod
    def ensure_asyncpg_prefix(cls, v: str) -> str:
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v
    database_schema: str = "taskme_agents"

    # Temporal (self-hosted on Railway)
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "taskme-agents"

    # LLM Providers
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Attachments (Railway persistent volume)
    attachment_base_path: str = "/data/attachments"
    max_attachment_size_mb: int = 50

    # MCP
    mcp_idle_timeout_minutes: int = 10
    mcp_max_servers: int = 500

    # Auth
    admin_api_key: str = ""  # Seed admin key on first startup

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["https://taskme-app.com"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
