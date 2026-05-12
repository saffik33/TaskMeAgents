FROM python:3.12-slim

WORKDIR /app

# System deps for asyncpg + cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency installation
RUN pip install --no-cache-dir uv

# Copy project metadata first (busts stale install cache on dependency changes)
COPY pyproject.toml .
# Copy source and install
COPY . .
RUN uv pip install --system .

# Create attachment volume mount point
RUN mkdir -p /data/attachments

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python -m taskmeagents.main"]
