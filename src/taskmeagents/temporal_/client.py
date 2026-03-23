"""Temporal client connection (self-hosted on Railway).

Translated from go_companion/internal/temporal/client/client.go
"""

from __future__ import annotations

import asyncio
import ssl

import structlog
from temporalio.client import Client

from taskmeagents.config import settings

logger = structlog.get_logger()

_client: Client | None = None


async def connect_temporal() -> Client:
    """Connect to self-hosted Temporal server with retry."""
    global _client
    # Use TLS if connecting via public Railway domain (port 443)
    tls: bool | ssl.SSLContext = False
    if ":443" in settings.temporal_address:
        tls = True

    for attempt in range(1, 6):
        try:
            _client = await asyncio.wait_for(
                Client.connect(
                    settings.temporal_address,
                    namespace=settings.temporal_namespace,
                    tls=tls,
                ),
                timeout=15,
            )
            return _client
        except Exception as e:
            if attempt == 5:
                raise
            logger.warning("taskme.temporal.retry", attempt=attempt, error=str(e))
            await asyncio.sleep(attempt * 2)
    raise RuntimeError("Failed to connect to Temporal")


def get_temporal_client() -> Client:
    """Get the connected Temporal client. Must call connect_temporal() first."""
    if _client is None:
        raise RuntimeError("Temporal client not connected. Call connect_temporal() first.")
    return _client


async def close_temporal() -> None:
    """Close the Temporal client connection."""
    global _client
    if _client:
        await _client.close()
        _client = None
